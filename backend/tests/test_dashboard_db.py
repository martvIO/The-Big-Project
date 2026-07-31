"""F52's dashboard against real Postgres, as the non-owner app role.

`db`-marked at module level: there is no Docker locally, so everything here is
first executed on CI. NullPool engines in try/finally and the `app_role_url`
fixture — never the container superuser, which bypasses RLS unconditionally and
would make every isolation assertion vacuously pass (`conftest.py:26-29`).

The window is taken from `history_window` itself rather than restated as
hand-written instants: these two statements exist to feed that arithmetic, and
a test carrying its own copy of the bounds would pass against a window the
service never asks for.

The service half below the statements is exercised HERE AND NOWHERE ELSE:
`test_dashboard_api.py` swaps in a `FakeDashboardService`, so the
three-reads-and-one-grid assembly inside a single `tenant_session` has no other
proof anywhere.
"""

import datetime
import uuid
from typing import Any

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.booking.validation import jerusalem_day_index
from app.dashboard.service import (
    FORWARD_WINDOW_DAYS,
    HISTORY_WEEKS,
    DashboardService,
    history_window,
)
from app.db.repositories.availability import AvailabilityRulesRepository
from app.db.repositories.bookings import BookingsRepository
from app.db.tenant import tenant_session
from app.models.booking import Booking
from app.models.constants import BookingCancelledBy, BookingStatus
from app.storefront.validation import BOUTIQUE_TIMEZONE

pytestmark = pytest.mark.db

# The spec's normative worked example: 2026-07-31 is a Friday
# (jerusalem_day_index == 5), so the twelve complete weeks run
# [2026-05-03, 2026-07-26) as boutique-midnight instants.
TODAY = datetime.date(2026, 7, 31)
WINDOW = history_window(TODAY)
# 09:00 in Jerusalem on TODAY, so `today_jerusalem(clock)` lands on TODAY and
# every forward slot below is comfortably in the engine's future.
NOW = datetime.datetime(2026, 7, 31, 6, 0, tzinfo=datetime.UTC)

MICROSECOND = datetime.timedelta(microseconds=1)
# Comfortably inside the window, and off every edge it is compared against.
# 2026-06-15 is a Monday, so its Israeli week begins Sunday 2026-06-14.
INSIDE = datetime.datetime(2026, 6, 15, 9, 0, tzinfo=datetime.UTC)
LATER_INSIDE = datetime.datetime(2026, 6, 15, 10, 0, tzinfo=datetime.UTC)
INSIDE_BUCKET = datetime.date(2026, 6, 14)
# Before the floor by months, not microseconds: this is the row that makes
# `history_by_customer` a second statement rather than a fold of the first.
BEFORE_WINDOW = datetime.datetime(2025, 11, 4, 9, 0, tzinfo=datetime.UTC)
ACCEPTED_AT = datetime.datetime(2025, 1, 1, tzinfo=datetime.UTC)

# The LAST day of the forward window, inclusive: today + 6, never today + 7.
# The whole forward suite hangs its booked slot on this date specifically —
# anywhere else in the window and the two off-by-one spellings both pass.
FORWARD_END = TODAY + datetime.timedelta(days=FORWARD_WINDOW_DAYS - 1)
# Seven consecutive days contain each weekday exactly once, so a rule on
# FORWARD_END's weekday opens FORWARD_END and no other day of the window.
FORWARD_DAY_INDEX = jerusalem_day_index(FORWARD_END)
# 09:00–11:00 on a 30-minute grid is four starts; close_time is exclusive.
FORWARD_OPEN = datetime.time(9, 0)
FORWARD_CLOSE = datetime.time(11, 0)
FORWARD_CAPACITY = 2
FORWARD_STARTS = 4

FITTING_ID = uuid.uuid4()
CONSULT_ID = uuid.uuid4()


def _factory(url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(url, poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _boutique(day: datetime.date, hour: int, minute: int = 0) -> datetime.datetime:
    return datetime.datetime.combine(
        day, datetime.time(hour, minute), tzinfo=BOUTIQUE_TIMEZONE
    ).astimezone(datetime.UTC)


def _service(factory: async_sessionmaker[AsyncSession]) -> DashboardService:
    """A frozen clock, so `today_jerusalem` lands on TODAY and the fixture dates
    below stay meaningful whatever day CI runs on."""
    return DashboardService(factory, clock=lambda: NOW)


async def _open_the_last_forward_day(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    await AvailabilityRulesRepository().insert(
        session,
        tenant_id=tenant_id,
        day_of_week=FORWARD_DAY_INDEX,
        open_time=FORWARD_OPEN,
        close_time=FORWARD_CLOSE,
        capacity=FORWARD_CAPACITY,
    )


async def _book(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    starts_at: datetime.datetime,
    customer_id: uuid.UUID | None = None,
    appointment_type_id: uuid.UUID | None = None,
    appointment_type_name: str = "מדידה",
    status: str = BookingStatus.CONFIRMED.value,
    cancelled_by: str | None = None,
    deleted: bool = False,
    seat_index: int = 1,
) -> Booking:
    """One row, written through the repository and then stamped with the columns
    `insert` deliberately does not take: status and the cancel evidence have
    their own guarded writers, and nothing in the product writes
    `bookings.deleted_at` at all — which is exactly why the predicate needs a
    test rather than a caller."""
    row = await BookingsRepository().insert(
        session,
        tenant_id=tenant_id,
        customer_id=customer_id if customer_id is not None else uuid.uuid4(),
        appointment_type_id=(
            appointment_type_id if appointment_type_id is not None else uuid.uuid4()
        ),
        starts_at=starts_at,
        seat_index=seat_index,
        terms_version_accepted=1,
        terms_accepted_at=ACCEPTED_AT,
        appointment_type_name=appointment_type_name,
    )
    row.status = status
    row.cancelled_by = cancelled_by
    if deleted:
        row.deleted_at = datetime.datetime.now(datetime.UTC)
    await session.flush()
    return row


def _statements(engine: AsyncEngine) -> list[str]:
    """Every SQL string the engine executes, in order — the only way to assert
    that a short-circuit really issued no statement rather than issuing one that
    happened to return nothing."""
    seen: list[str] = []

    def _record(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        seen.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", _record)
    return seen


# --- the two statements ----------------------------------------------------


async def test_the_window_projection_is_half_open_on_the_right(app_role_url: str) -> None:
    """One microsecond before the floor is out, the floor itself is in, and the
    ceiling instant is out — the same half-open shape `list_day` and
    `count_by_start` already carry, so a caller can pass the next window's floor
    as this window's ceiling without double-counting a booking."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        async with tenant_session(factory, tenant_id) as session:
            for instant in (
                WINDOW.from_instant - MICROSECOND,
                WINDOW.from_instant,
                INSIDE,
                WINDOW.until_instant,
                WINDOW.until_instant + MICROSECOND,
            ):
                await _book(session, tenant_id, starts_at=instant)

        async with tenant_session(factory, tenant_id) as session:
            facts = await BookingsRepository().list_window_facts(
                session,
                tenant_id,
                from_instant=WINDOW.from_instant,
                until_instant=WINDOW.until_instant,
            )

        assert sorted(fact.starts_at for fact in facts) == [WINDOW.from_instant, INSIDE]
    finally:
        await engine.dispose()


async def test_the_projection_carries_every_status_and_drops_soft_deleted_rows(
    app_role_url: str,
) -> None:
    """Every status, cancellations included — this deliberately does NOT inherit
    `count_by_start`'s `status <> 'cancelled'` predicate, under which a
    cancellation rate would be structurally 0% forever."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    type_id = uuid.uuid4()
    customer_id = uuid.uuid4()
    statuses = [
        BookingStatus.CONFIRMED.value,
        BookingStatus.CANCELLED.value,
        BookingStatus.NO_SHOW.value,
        BookingStatus.COMPLETED.value,
    ]
    try:
        async with tenant_session(factory, tenant_id) as session:
            for offset, status in enumerate(statuses):
                await _book(
                    session,
                    tenant_id,
                    starts_at=INSIDE + datetime.timedelta(hours=offset),
                    appointment_type_id=type_id,
                    appointment_type_name="מדידה ראשונה",
                    customer_id=customer_id,
                    status=status,
                    cancelled_by=(
                        BookingCancelledBy.CUSTOMER.value
                        if status == BookingStatus.CANCELLED.value
                        else None
                    ),
                )
            await _book(
                session,
                tenant_id,
                starts_at=INSIDE + datetime.timedelta(hours=len(statuses)),
                deleted=True,
            )

        async with tenant_session(factory, tenant_id) as session:
            facts = await BookingsRepository().list_window_facts(
                session,
                tenant_id,
                from_instant=WINDOW.from_instant,
                until_instant=WINDOW.until_instant,
            )

        assert sorted(fact.status for fact in facts) == sorted(statuses)
        assert {fact.appointment_type_id for fact in facts} == {type_id}
        assert {fact.appointment_type_name for fact in facts} == {"מדידה ראשונה"}
        assert {fact.customer_id for fact in facts} == {customer_id}
        assert [fact.cancelled_by for fact in facts if fact.cancelled_by is not None] == [
            BookingCancelledBy.CUSTOMER.value
        ]
        # `created_at` rides a server_default, so a projection that forgot the
        # column would come back None and D6's label rule would silently pick
        # an arbitrary snapshot.
        assert all(fact.created_at is not None for fact in facts)
    finally:
        await engine.dispose()


async def test_history_counts_a_customers_bookings_on_both_sides_of_the_window_edge(
    app_role_url: str,
) -> None:
    """The whole reason this read cannot fold into the window projection (D7): a
    bride whose first-ever visit predates the window is RETURNING, and the
    projection has no row that says so."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    returning = uuid.uuid4()
    newcomer = uuid.uuid4()
    try:
        async with tenant_session(factory, tenant_id) as session:
            await _book(session, tenant_id, starts_at=BEFORE_WINDOW, customer_id=returning)
            await _book(session, tenant_id, starts_at=INSIDE, customer_id=returning)
            await _book(session, tenant_id, starts_at=LATER_INSIDE, customer_id=newcomer)

        async with tenant_session(factory, tenant_id) as session:
            history = await BookingsRepository().history_by_customer(
                session,
                tenant_id,
                [returning, newcomer],
                until_instant=WINDOW.until_instant,
            )

        assert set(history) == {returning, newcomer}
        assert history[returning].bookings == 2
        assert history[returning].first_starts_at == BEFORE_WINDOW
        assert history[newcomer].bookings == 1
        assert history[newcomer].first_starts_at == LATER_INSIDE
    finally:
        await engine.dispose()


async def test_history_excludes_cancellations_and_anything_at_or_after_the_edge(
    app_role_url: str,
) -> None:
    """A bride who booked and cancelled did not visit, and a fitting booked for
    next month must not retroactively change last quarter's numbers — so the
    right edge is the same half-open bound the projection uses."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    customer_id = uuid.uuid4()
    try:
        async with tenant_session(factory, tenant_id) as session:
            await _book(
                session,
                tenant_id,
                starts_at=INSIDE,
                customer_id=customer_id,
                status=BookingStatus.CANCELLED.value,
                cancelled_by=BookingCancelledBy.OWNER.value,
            )
            await _book(session, tenant_id, starts_at=LATER_INSIDE, customer_id=customer_id)
            await _book(
                session,
                tenant_id,
                starts_at=WINDOW.until_instant,
                customer_id=customer_id,
            )
            await _book(
                session,
                tenant_id,
                starts_at=INSIDE + datetime.timedelta(hours=2),
                customer_id=customer_id,
                deleted=True,
            )

        async with tenant_session(factory, tenant_id) as session:
            history = await BookingsRepository().history_by_customer(
                session, tenant_id, [customer_id], until_instant=WINDOW.until_instant
            )

        assert history[customer_id].bookings == 1
        assert history[customer_id].first_starts_at == LATER_INSIDE
    finally:
        await engine.dispose()


async def test_history_short_circuits_on_an_empty_cohort_without_issuing_a_statement(
    app_role_url: str,
) -> None:
    """`aggregate_by_dress`'s short-circuit, verbatim. An empty tenant's
    dashboard is the console's landing screen on day one, and `IN ()` is both a
    syntax error and a statement nobody needs."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        async with tenant_session(factory, tenant_id) as session:
            # Registered AFTER the session's own set_config, and asserted before
            # the transaction closes, so `issued` sees this call and nothing else.
            issued = _statements(engine)
            history = await BookingsRepository().history_by_customer(
                session, tenant_id, [], until_instant=WINDOW.until_instant
            )
            assert history == {}
            assert issued == []
    finally:
        await engine.dispose()


# --- the forward panel, end to end -----------------------------------------


async def test_a_slot_booked_to_capacity_on_the_last_forward_day_is_in_both_halves(
    app_role_url: str,
) -> None:
    """Two assertions, two different off-by-ones, and both need the booked slot
    on `today + 6` SPECIFICALLY — anywhere else in the window and each wrong
    spelling still passes.

    `capacity` is the DENOMINATOR assertion: the engine DROPS every slot where
    `taken >= capacity` (`slots.py:149-152`), so a grid built from
    `StorefrontService.list_slots` instead of `booked={}` would omit the
    fully-booked 09:00 start and come back three starts short.

    `booked` is the NUMERATOR assertion: `count_by_start` is half-open on the
    right over instants, so its ceiling has to be boutique-midnight of
    `today + 7`. Written as midnight of `today + 6` — which reads correct
    against the sentence "the window is [today, today + 6]" — this day's
    bookings vanish while its capacity stays in the denominator, understating
    utilization by up to a seventh, permanently and silently.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    full_slot = _boutique(FORWARD_END, 9)
    try:
        async with tenant_session(factory, tenant_id) as session:
            await _open_the_last_forward_day(session, tenant_id)
            for seat in range(1, FORWARD_CAPACITY + 1):
                await _book(session, tenant_id, starts_at=full_slot, seat_index=seat)

        forward = (await _service(factory).dashboard(tenant_id)).forward

        assert forward.from_date == TODAY
        assert forward.to_date == FORWARD_END
        assert forward.capacity == FORWARD_STARTS * FORWARD_CAPACITY
        assert forward.booked == FORWARD_CAPACITY
        assert forward.utilization == FORWARD_CAPACITY / (FORWARD_STARTS * FORWARD_CAPACITY)
    finally:
        await engine.dispose()


async def test_a_booking_the_current_rules_no_longer_offer_contributes_nothing(
    app_role_url: str,
) -> None:
    """A booking made under a weekly rule the owner has since deleted, or on a
    date a later exception closed: the row exists and `count_by_start` counts it,
    but it has no capacity behind it. Iterating the GRID rather than the mapping
    is what keeps `booked <= capacity` and utilization at or below 100%."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        async with tenant_session(factory, tenant_id) as session:
            await _open_the_last_forward_day(session, tenant_id)
            await _book(session, tenant_id, starts_at=_boutique(FORWARD_END, 9))
            # Same forward window, no rule opens it: the day before FORWARD_END.
            await _book(
                session,
                tenant_id,
                starts_at=_boutique(FORWARD_END - datetime.timedelta(days=1), 10),
            )
            # On the opened day but after close_time, which is exclusive.
            await _book(session, tenant_id, starts_at=_boutique(FORWARD_END, 12))

        forward = (await _service(factory).dashboard(tenant_id)).forward

        assert forward.capacity == FORWARD_STARTS * FORWARD_CAPACITY
        assert forward.booked == 1
        assert forward.booked <= forward.capacity
    finally:
        await engine.dispose()


# --- the whole response, assembled from real rows --------------------------


async def test_the_dashboard_assembles_every_panel_from_one_projection(
    app_role_url: str,
) -> None:
    """The three-reads-and-one-grid assembly, which `test_dashboard_api.py`
    cannot reach because it swaps in a fake.

    Four brides, deliberately shaped so every fold answers something different:
    ANNA came before the window (returning, lifetime 2), BETH twice inside it
    (new, and a repeat), CARA once and did not show (new, not a repeat), and
    DINA cancelled — so she is in no bucket, in no type count and in no cohort,
    while her row still lands in `status_totals` and in the cancellation rate.

    No availability rule at all, so the forward panel is the zero-hours boutique:
    `capacity == 0` renders as NOT COMPUTABLE and never as 0%.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    anna, beth, cara, dina = (uuid.uuid4() for _ in range(4))
    try:
        async with tenant_session(factory, tenant_id) as session:
            await _book(session, tenant_id, starts_at=BEFORE_WINDOW, customer_id=anna)
            await _book(
                session,
                tenant_id,
                starts_at=INSIDE,
                customer_id=anna,
                appointment_type_id=FITTING_ID,
            )
            await _book(
                session,
                tenant_id,
                starts_at=LATER_INSIDE,
                customer_id=beth,
                appointment_type_id=FITTING_ID,
            )
            await _book(
                session,
                tenant_id,
                starts_at=INSIDE + datetime.timedelta(hours=2),
                customer_id=beth,
                appointment_type_id=FITTING_ID,
                status=BookingStatus.COMPLETED.value,
            )
            await _book(
                session,
                tenant_id,
                starts_at=INSIDE + datetime.timedelta(hours=3),
                customer_id=cara,
                appointment_type_id=FITTING_ID,
                status=BookingStatus.NO_SHOW.value,
            )
            await _book(
                session,
                tenant_id,
                starts_at=INSIDE + datetime.timedelta(hours=4),
                customer_id=dina,
                appointment_type_id=CONSULT_ID,
                appointment_type_name="ייעוץ",
                status=BookingStatus.CANCELLED.value,
                cancelled_by=BookingCancelledBy.CUSTOMER.value,
            )

        response = await _service(factory).dashboard(tenant_id)
        history = response.history

        assert response.generated_on == TODAY
        assert history.from_date == WINDOW.first_week_start
        assert history.to_date == WINDOW.current_week_start - datetime.timedelta(days=1)
        assert len(history.weeks) == HISTORY_WEEKS
        assert [week.week_start for week in history.weeks] == sorted(
            week.week_start for week in history.weeks
        )

        # Five in-window rows; ANNA's pre-window booking is outside the scan.
        assert history.status_totals.confirmed == 2
        assert history.status_totals.cancelled == 1
        assert history.status_totals.no_show == 1
        assert history.status_totals.completed == 1

        filled = {week.week_start: week.bookings for week in history.weeks if week.bookings}
        assert filled == {INSIDE_BUCKET: 4}
        assert sum(week.bookings for week in history.weeks) == (
            history.status_totals.confirmed
            + history.status_totals.no_show
            + history.status_totals.completed
        )

        assert history.cancellation_rate == 1 / 5
        assert history.cancelled_by_customer == 1
        assert history.cancelled_by_owner == 0
        assert history.no_show_rate == 1 / 2

        # DINA's cancelled consultation raises no type count (C2), so the types
        # sum can never exceed the bars above it.
        assert [(row.appointment_type_id, row.bookings) for row in history.appointment_types] == [
            (FITTING_ID, 4)
        ]

        assert history.customers.total == 3  # DINA cancelled, so she is no cohort member
        assert history.customers.new == 2  # BETH and CARA
        assert history.customers.returning == 1  # ANNA, whose first visit predates the window
        assert history.customers.repeat_rate == 2 / 3  # ANNA and BETH hold two each

        assert response.forward.capacity == 0
        assert response.forward.booked == 0
        assert response.forward.utilization is None
    finally:
        await engine.dispose()


# --- RLS -------------------------------------------------------------------


async def test_one_tenants_dashboard_never_counts_anothers_bookings(
    app_role_url: str,
) -> None:
    """Asserted in BOTH directions in one test, and that is the whole point.

    With no tenant context bound, `current_setting('app.tenant_id', true)::uuid`
    is NULL, every comparison is NULL and every row is filtered out — a `by_id`
    then 404s visibly, but an aggregate returns a perfectly plausible all-zeros
    dashboard with nothing in the response and nothing in the logs to say so. A
    test that only checked "B sees nothing" would pass against a service that
    had lost `tenant_session` entirely, so A's own numbers are asserted non-zero
    in the same run.

    B has hours of her own and no bookings, so her zeros are about bookings
    rather than about an empty tenant.
    """
    engine, factory = _factory(app_role_url)
    mine, theirs = uuid.uuid4(), uuid.uuid4()
    try:
        async with tenant_session(factory, mine) as session:
            await _open_the_last_forward_day(session, mine)
            await _book(session, mine, starts_at=INSIDE, appointment_type_id=FITTING_ID)
            await _book(session, mine, starts_at=LATER_INSIDE, appointment_type_id=FITTING_ID)
            await _book(session, mine, starts_at=_boutique(FORWARD_END, 9))
        async with tenant_session(factory, theirs) as session:
            await _open_the_last_forward_day(session, theirs)

        service = _service(factory)
        ours = await service.dashboard(mine)
        yours = await service.dashboard(theirs)

        # Two of the three are in the history window; the third is a week out,
        # which is what makes it the FORWARD panel's row and not this one's.
        assert ours.history.status_totals.confirmed == 2
        assert sum(week.bookings for week in ours.history.weeks) == 2
        assert ours.history.customers.total == 2
        assert ours.history.appointment_types
        assert ours.forward.booked == 1

        assert yours.history.status_totals.confirmed == 0
        assert sum(week.bookings for week in yours.history.weeks) == 0
        assert yours.history.customers.total == 0
        assert yours.history.appointment_types == []
        assert yours.history.cancellation_rate is None
        assert yours.forward.booked == 0
        # Her own hours are visible, so the zeros above are about BOOKINGS.
        assert yours.forward.capacity == FORWARD_STARTS * FORWARD_CAPACITY
    finally:
        await engine.dispose()
