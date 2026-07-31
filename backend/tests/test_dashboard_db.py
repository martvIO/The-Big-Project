"""F52's dashboard against real Postgres, as the non-owner app role.

`db`-marked at module level: there is no Docker locally, so everything here is
first executed on CI. NullPool engines in try/finally and the `app_role_url`
fixture — never the container superuser, which bypasses RLS unconditionally and
would make every isolation assertion vacuously pass (`conftest.py:26-29`).

The window is taken from `history_window` itself rather than restated as
hand-written instants: these two statements exist to feed that arithmetic, and
a test carrying its own copy of the bounds would pass against a window the
service never asks for.
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

from app.dashboard.service import history_window
from app.db.repositories.bookings import BookingsRepository
from app.db.tenant import tenant_session
from app.models.booking import Booking
from app.models.constants import BookingCancelledBy, BookingStatus

pytestmark = pytest.mark.db

# The spec's normative worked example: 2026-07-31 is a Friday
# (jerusalem_day_index == 5), so the twelve complete weeks run
# [2026-05-03, 2026-07-26) as boutique-midnight instants.
TODAY = datetime.date(2026, 7, 31)
WINDOW = history_window(TODAY)

MICROSECOND = datetime.timedelta(microseconds=1)
# Comfortably inside the window, and off every edge it is compared against.
INSIDE = datetime.datetime(2026, 6, 15, 9, 0, tzinfo=datetime.UTC)
LATER_INSIDE = datetime.datetime(2026, 6, 15, 10, 0, tzinfo=datetime.UTC)
# Before the floor by months, not microseconds: this is the row that makes
# `history_by_customer` a second statement rather than a fold of the first.
BEFORE_WINDOW = datetime.datetime(2025, 11, 4, 9, 0, tzinfo=datetime.UTC)
ACCEPTED_AT = datetime.datetime(2025, 1, 1, tzinfo=datetime.UTC)


def _factory(url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(url, poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


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
