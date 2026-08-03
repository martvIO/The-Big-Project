"""Round-trips for the two F13 repositories, as the non-owner app role. The
isolation half lives in test_booking_isolation.py; the concurrency proof for
the claim itself is test_booking_service.py's job."""

import asyncio
import datetime
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.db.repositories.bookings import BookingsRepository, CheckInOutcome
from app.db.repositories.customers import CustomersRepository
from app.db.tenant import tenant_session
from app.models.booking import Booking
from app.models.constants import BookingCancelledBy, BookingStatus

pytestmark = pytest.mark.db

BACKEND_DIR = Path(__file__).resolve().parent.parent

# Fixed instants, far future: the repositories do no "is this bookable" math,
# so the only thing that matters is that the values are distinct and tz-aware.
T0 = datetime.datetime(2099, 8, 2, 7, 0, tzinfo=datetime.UTC)
T1 = datetime.datetime(2099, 8, 2, 7, 30, tzinfo=datetime.UTC)
ACCEPTED_AT = datetime.datetime(2099, 8, 1, 12, 0, tzinfo=datetime.UTC)

# F15's writers are the first here that carry a CLOCK bound, so they need their
# own fixture on the other side of "now" from T0/T1 — those are 2099, and
# `set_status(to='no_show', not_after=NOW)` against them would match zero rows.
# The three constants are only ever compared: PAST_SLOT < NOW < T0 < T1.
PAST_SLOT = datetime.datetime(2020, 3, 1, 9, 0, tzinfo=datetime.UTC)
NOW = datetime.datetime(2026, 7, 30, 12, 0, tzinfo=datetime.UTC)
# The Jerusalem day T0 and T1 fall in, as the half-open UTC pair list_day takes.
DAY_START = datetime.datetime(2099, 8, 2, 0, 0, tzinfo=datetime.UTC)
DAY_END = datetime.datetime(2099, 8, 3, 0, 0, tzinfo=datetime.UTC)

# F34's two arrival clocks. Only ever compared, and DISTINCT is the whole point:
# the second-tap assertion is that the row still reads FIRST_ARRIVAL, which a
# single shared constant could pass without meaning anything.
FIRST_ARRIVAL = datetime.datetime(2099, 8, 2, 6, 52, tzinfo=datetime.UTC)
SECOND_ARRIVAL = datetime.datetime(2099, 8, 2, 8, 52, tzinfo=datetime.UTC)


def _factory(app_role_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(app_role_url, poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _phone() -> str:
    return f"+9725{uuid.uuid4().int % 10**8:08d}"


async def _insert_booking(
    repo: BookingsRepository,
    session: AsyncSession,
    tenant_id: uuid.UUID,
    customer_id: uuid.UUID,
    *,
    starts_at: datetime.datetime,
    seat_index: int,
    **overrides: object,
) -> Booking:
    kwargs: dict = {
        "tenant_id": tenant_id,
        "customer_id": customer_id,
        "appointment_type_id": uuid.uuid4(),
        "starts_at": starts_at,
        "seat_index": seat_index,
        "terms_version_accepted": 1,
        "terms_accepted_at": ACCEPTED_AT,
        "appointment_type_name": "מדידת שמלה",
    }
    kwargs.update(overrides)
    return await repo.insert(session, **kwargs)


async def test_customer_upsert_attaches_and_updates_name(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    repo = CustomersRepository()
    phone = _phone()
    try:
        async with tenant_session(factory, tenant_id) as session:
            first = await repo.upsert(session, tenant_id, phone=phone, name="נועה לוי")
            assert first.phone == phone
            assert first.name == "נועה לוי"

            found = await repo.by_phone(session, tenant_id, phone=phone)
            assert found is not None
            assert found.id == first.id

        async with tenant_session(factory, tenant_id) as session:
            # A returning customer ATTACHES — and the name she typed this time wins.
            again = await repo.upsert(session, tenant_id, phone=phone, name="נועה לוי-כהן")
            assert again.id == first.id
            assert again.name == "נועה לוי-כהן"

            assert await repo.by_id(session, tenant_id, first.id) is not None
            assert await repo.by_id(session, tenant_id, uuid.uuid4()) is None
    finally:
        await engine.dispose()


async def test_soft_deleted_customer_does_not_block_return(app_role_url: str) -> None:
    """The unique index is partial on deleted_at IS NULL: a scrubbed customer
    record must not lock her phone number out of the boutique forever."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    repo = CustomersRepository()
    phone = _phone()
    try:
        async with tenant_session(factory, tenant_id) as session:
            first = await repo.upsert(session, tenant_id, phone=phone, name="דנה")
            first.deleted_at = datetime.datetime.now(datetime.UTC)
            await session.flush()

        async with tenant_session(factory, tenant_id) as session:
            assert await repo.by_phone(session, tenant_id, phone=phone) is None
            reborn = await repo.upsert(session, tenant_id, phone=phone, name="דנה")
            assert reborn.id != first.id
    finally:
        await engine.dispose()


async def test_booking_insert_round_trip_and_by_id(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    customers = CustomersRepository()
    bookings = BookingsRepository()
    try:
        async with tenant_session(factory, tenant_id) as session:
            customer = await customers.upsert(session, tenant_id, phone=_phone(), name="שירה")
            dress_id = uuid.uuid4()
            row = await _insert_booking(
                bookings,
                session,
                tenant_id,
                customer.id,
                starts_at=T0,
                seat_index=1,
                dress_id=dress_id,
                dress_name="Aurora",
                dress_size="38",
                notes="מגיעה עם אמא ושתי אחיות",
            )
            assert row.status == BookingStatus.CONFIRMED.value  # server default
            assert row.attendance_confirmed_at is None
            assert row.terms_version_accepted == 1
            assert row.appointment_type_name == "מדידת שמלה"
            assert (row.dress_id, row.dress_name, row.dress_size) == (dress_id, "Aurora", "38")

            fetched = await bookings.by_id(session, tenant_id, row.id)
            assert fetched is not None
            assert fetched.starts_at == T0
            assert await bookings.by_id(session, tenant_id, uuid.uuid4()) is None
    finally:
        await engine.dispose()


async def test_occupancy_queries_ignore_cancelled_and_respect_window(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    customers = CustomersRepository()
    bookings = BookingsRepository()
    try:
        async with tenant_session(factory, tenant_id) as session:
            customer = await customers.upsert(session, tenant_id, phone=_phone(), name="מאיה")
            # Two seats at T0 are two DIFFERENT customers — 0009 forbids one
            # customer holding two live bookings at one instant.
            neighbour = await customers.upsert(session, tenant_id, phone=_phone(), name="רות")
            seat1 = await _insert_booking(
                bookings, session, tenant_id, customer.id, starts_at=T0, seat_index=1
            )
            await _insert_booking(
                bookings, session, tenant_id, neighbour.id, starts_at=T0, seat_index=2
            )
            await _insert_booking(
                bookings, session, tenant_id, customer.id, starts_at=T1, seat_index=1
            )

            assert await bookings.active_seats_at(session, tenant_id, starts_at=T0) == {1, 2}
            assert await bookings.count_by_start(
                session,
                tenant_id,
                from_instant=T0,
                until_instant=T1 + datetime.timedelta(minutes=30),
            ) == {T0: 2, T1: 1}
            # Half-open right edge: a window ending AT T1 excludes T1.
            assert await bookings.count_by_start(
                session, tenant_id, from_instant=T0, until_instant=T1
            ) == {T0: 2}

            # A no-show still occupies its seat; only a cancellation frees it.
            seat1.status = BookingStatus.NO_SHOW.value
            await session.flush()
            assert await bookings.active_seats_at(session, tenant_id, starts_at=T0) == {1, 2}

            seat1.status = BookingStatus.CANCELLED.value
            await session.flush()
            assert await bookings.active_seats_at(session, tenant_id, starts_at=T0) == {2}
            assert await bookings.count_by_start(
                session, tenant_id, from_instant=T0, until_instant=T1
            ) == {T0: 1}
    finally:
        await engine.dispose()


async def test_slot_seat_unique_index_rejects_double_claim_and_frees_on_cancel(
    app_role_url: str,
) -> None:
    """The structural oversell guard, exercised directly at the index: a live
    duplicate (tenant, starts_at, seat) is an IntegrityError, and a CANCELLED
    row leaves the predicate so its seat number is claimable again."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    customers = CustomersRepository()
    bookings = BookingsRepository()
    try:
        async with tenant_session(factory, tenant_id) as session:
            customer = await customers.upsert(session, tenant_id, phone=_phone(), name="רות")
            customer_id = customer.id
            # The double claimant is a SECOND customer, so it is the seat index
            # under test here and not 0009's (tenant, customer, instant) one.
            rival = await customers.upsert(session, tenant_id, phone=_phone(), name="שרה")
            rival_id = rival.id
            first = await _insert_booking(
                bookings, session, tenant_id, customer_id, starts_at=T0, seat_index=1
            )
            first_id = first.id

        with pytest.raises(IntegrityError):
            async with tenant_session(factory, tenant_id) as session:
                await _insert_booking(
                    bookings, session, tenant_id, rival_id, starts_at=T0, seat_index=1
                )

        async with tenant_session(factory, tenant_id) as session:
            row = await bookings.by_id(session, tenant_id, first_id)
            assert row is not None
            row.status = BookingStatus.CANCELLED.value
            await session.flush()

        async with tenant_session(factory, tenant_id) as session:
            reclaimed = await _insert_booking(
                bookings, session, tenant_id, customer_id, starts_at=T0, seat_index=1
            )
            assert reclaimed.id != first_id
    finally:
        await engine.dispose()


async def test_customer_instant_unique_index_and_active_at(app_role_url: str) -> None:
    """0009's structural idempotency guard, at the index: one LIVE booking per
    (tenant, customer, instant) — a different SEAT is not an escape hatch, and
    `active_at` reads exactly the rows the index counts, which is what makes
    the service's pre-check under the advisory lock total."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    customers = CustomersRepository()
    bookings = BookingsRepository()
    try:
        async with tenant_session(factory, tenant_id) as session:
            customer = await customers.upsert(session, tenant_id, phone=_phone(), name="דנה")
            customer_id = customer.id
            first = await _insert_booking(
                bookings, session, tenant_id, customer_id, starts_at=T0, seat_index=1
            )
            first_id = first.id
            found = await bookings.active_at(
                session, tenant_id, customer_id=customer_id, starts_at=T0
            )
            assert found is not None
            assert found.id == first_id
            # Another instant, and another customer, are both hers to book.
            assert (
                await bookings.active_at(session, tenant_id, customer_id=customer_id, starts_at=T1)
                is None
            )
            assert (
                await bookings.active_at(session, tenant_id, customer_id=uuid.uuid4(), starts_at=T0)
                is None
            )

        with pytest.raises(IntegrityError):
            async with tenant_session(factory, tenant_id) as session:
                await _insert_booking(
                    bookings, session, tenant_id, customer_id, starts_at=T0, seat_index=2
                )

        async with tenant_session(factory, tenant_id) as session:
            row = await bookings.by_id(session, tenant_id, first_id)
            assert row is not None
            row.status = BookingStatus.CANCELLED.value
            await session.flush()
            assert (
                await bookings.active_at(session, tenant_id, customer_id=customer_id, starts_at=T0)
                is None
            )

        # …and with the cancelled row out of the predicate she rebooks it.
        async with tenant_session(factory, tenant_id) as session:
            rebooked = await _insert_booking(
                bookings, session, tenant_id, customer_id, starts_at=T0, seat_index=1
            )
            assert rebooked.id != first_id
    finally:
        await engine.dispose()


async def test_set_status_walks_the_reversible_pairs_and_returns_the_reread(
    app_role_url: str,
) -> None:
    """D3's graph, at the writer. `no_show` and `completed` are mutually
    reversible and both revert to `confirmed` — neither frees a seat, so the
    mis-tap undo costs one predicate."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    customers = CustomersRepository()
    bookings = BookingsRepository()
    try:
        async with tenant_session(factory, tenant_id) as session:
            customer = await customers.upsert(session, tenant_id, phone=_phone(), name="נועה")
            booking = await _insert_booking(
                bookings, session, tenant_id, customer.id, starts_at=PAST_SLOT, seat_index=1
            )
            booking_id = booking.id

            walk = [
                (BookingStatus.NO_SHOW.value, (BookingStatus.CONFIRMED.value,)),
                (BookingStatus.COMPLETED.value, (BookingStatus.NO_SHOW.value,)),
                (BookingStatus.NO_SHOW.value, (BookingStatus.COMPLETED.value,)),
                (
                    BookingStatus.CONFIRMED.value,
                    (BookingStatus.NO_SHOW.value, BookingStatus.COMPLETED.value),
                ),
            ]
            for target, allowed_from in walk:
                updated = await bookings.set_status(
                    session,
                    tenant_id,
                    booking_id,
                    to=target,
                    allowed_from=allowed_from,
                    not_after=NOW,
                )
                assert updated is not None
                assert updated.status == target
                # The returned row is the re-read, not the UPDATE's echo.
                reread = await bookings.by_id(session, tenant_id, booking_id)
                assert reread is not None
                assert reread.status == target

            # /confirm writes status ONLY — attendance_confirmed_at is F16's
            # column and means something different (the bride said she is
            # coming), so undoing a mis-tapped no-show must not touch it.
            final = await bookings.by_id(session, tenant_id, booking_id)
            assert final is not None
            assert final.attendance_confirmed_at is None
    finally:
        await engine.dispose()


async def test_set_status_refuses_the_illegal_from_the_clock_and_a_deleted_row(
    app_role_url: str,
) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    customers = CustomersRepository()
    bookings = BookingsRepository()
    try:
        async with tenant_session(factory, tenant_id) as session:
            customer = await customers.upsert(session, tenant_id, phone=_phone(), name="רות")
            past = await _insert_booking(
                bookings, session, tenant_id, customer.id, starts_at=PAST_SLOT, seat_index=1
            )
            future = await _insert_booking(
                bookings, session, tenant_id, customer.id, starts_at=T0, seat_index=1
            )

            # A `from` outside allowed_from writes nothing and returns None.
            assert (
                await bookings.set_status(
                    session,
                    tenant_id,
                    past.id,
                    to=BookingStatus.NO_SHOW.value,
                    allowed_from=(BookingStatus.CANCELLED.value,),
                    not_after=NOW,
                )
                is None
            )
            unchanged = await bookings.by_id(session, tenant_id, past.id)
            assert unchanged is not None
            assert unchanged.status == BookingStatus.CONFIRMED.value

            # not_after is the "this is a PAST appointment" half of the split:
            # a future booking cannot be marked no-show or completed.
            assert (
                await bookings.set_status(
                    session,
                    tenant_id,
                    future.id,
                    to=BookingStatus.NO_SHOW.value,
                    allowed_from=(BookingStatus.CONFIRMED.value,),
                    not_after=NOW,
                )
                is None
            )

            # not_before is the other half — and a past booking fails it.
            assert (
                await bookings.set_status(
                    session,
                    tenant_id,
                    past.id,
                    to=BookingStatus.CANCELLED.value,
                    allowed_from=(BookingStatus.CONFIRMED.value,),
                    not_before=NOW,
                )
                is None
            )

            # Unknown id, and a soft-deleted row, are the same miss.
            assert (
                await bookings.set_status(
                    session,
                    tenant_id,
                    uuid.uuid4(),
                    to=BookingStatus.NO_SHOW.value,
                    allowed_from=(BookingStatus.CONFIRMED.value,),
                )
                is None
            )
            past.deleted_at = datetime.datetime.now(datetime.UTC)
            await session.flush()
            assert (
                await bookings.set_status(
                    session,
                    tenant_id,
                    past.id,
                    to=BookingStatus.NO_SHOW.value,
                    allowed_from=(BookingStatus.CONFIRMED.value,),
                )
                is None
            )
    finally:
        await engine.dispose()


async def test_cancel_answers_none_when_its_own_update_matched_nothing(
    app_role_url: str,
) -> None:
    """`cancel` consumes its `.returning()` scalar, like `set_status` and
    `reschedule` — it is the only signal that can tell the caller whether the
    row was cancelled by THIS call.

    The re-read cannot: `update(Booking)` is ORM-enabled DML whose `evaluate`
    synchronization stamps the SET values onto the identity-mapped instance
    whatever the database matched, and the trailing `by_id` returns that same
    instance. Without the scalar, a customer cancel landing in the owner's
    window comes back reading `cancelled_by = 'owner'`, and the owner path
    commits an audit row for a cancellation it did not perform.

    F16's `ManageBookingService.cancel` passes no `not_before` and already falls
    back to the row it read (`updated if updated is not None else booking`), so
    the `None` costs it nothing — it has ruled out both the cancelled and the
    already-started case before calling.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    customers = CustomersRepository()
    bookings = BookingsRepository()
    try:
        async with tenant_session(factory, tenant_id) as session:
            customer = await customers.upsert(session, tenant_id, phone=_phone(), name="דנה")
            past = await _insert_booking(
                bookings, session, tenant_id, customer.id, starts_at=PAST_SLOT, seat_index=1
            )
            future = await _insert_booking(
                bookings, session, tenant_id, customer.id, starts_at=T0, seat_index=1
            )

            # The customer path: no clock keyword, so a past booking cancels.
            cancelled = await bookings.cancel(
                session, tenant_id, past.id, at=NOW, by=BookingCancelledBy.CUSTOMER.value
            )
            assert cancelled is not None
            assert cancelled.status == BookingStatus.CANCELLED.value
            assert cancelled.cancelled_at == NOW
            assert cancelled.cancelled_by == BookingCancelledBy.CUSTOMER.value

            # F15's owner path passes it, and a past booking is refused. Zero
            # rows, so `None` — and the committed evidence still names the
            # customer, which is exactly what the caller must not overwrite.
            refused = await bookings.cancel(
                session,
                tenant_id,
                past.id,
                at=NOW,
                by=BookingCancelledBy.OWNER.value,
                not_before=NOW,
            )
            assert refused is None
            reread = await bookings.by_id(session, tenant_id, past.id)
            assert reread is not None
            assert reread.cancelled_by == BookingCancelledBy.CUSTOMER.value

            # A repeat cancel is the same zero-row answer: the predicate is
            # `status = 'confirmed'`, so the first cancellation's evidence
            # survives untouched.
            assert (
                await bookings.cancel(
                    session, tenant_id, past.id, at=T1, by=BookingCancelledBy.CUSTOMER.value
                )
                is None
            )

            owner_cancelled = await bookings.cancel(
                session,
                tenant_id,
                future.id,
                at=NOW,
                by=BookingCancelledBy.OWNER.value,
                not_before=NOW,
            )
            assert owner_cancelled is not None
            assert owner_cancelled.status == BookingStatus.CANCELLED.value
            assert owner_cancelled.cancelled_by == BookingCancelledBy.OWNER.value
    finally:
        await engine.dispose()


async def test_reschedule_moves_both_columns_under_its_guard(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    customers = CustomersRepository()
    bookings = BookingsRepository()
    try:
        async with tenant_session(factory, tenant_id) as session:
            customer = await customers.upsert(session, tenant_id, phone=_phone(), name="מאיה")
            booking = await _insert_booking(
                bookings, session, tenant_id, customer.id, starts_at=T0, seat_index=3
            )

            moved = await bookings.reschedule(
                session, tenant_id, booking.id, starts_at=T1, seat_index=1, not_before=NOW
            )
            assert moved is not None
            assert (moved.starts_at, moved.seat_index) == (T1, 1)
            # The source seat is released by the same statement: both partial
            # unique indexes are re-evaluated over the row's new values.
            assert await bookings.active_seats_at(session, tenant_id, starts_at=T0) == set()

            # Only a confirmed FUTURE booking moves.
            past = await _insert_booking(
                bookings, session, tenant_id, customer.id, starts_at=PAST_SLOT, seat_index=1
            )
            assert (
                await bookings.reschedule(
                    session, tenant_id, past.id, starts_at=T0, seat_index=1, not_before=NOW
                )
                is None
            )
            await bookings.set_status(
                session,
                tenant_id,
                booking.id,
                to=BookingStatus.CONFIRMED.value,
                allowed_from=(BookingStatus.CONFIRMED.value,),
            )
            assert (
                await bookings.reschedule(
                    session, tenant_id, uuid.uuid4(), starts_at=T0, seat_index=1, not_before=NOW
                )
                is None
            )
    finally:
        await engine.dispose()


async def test_reschedule_into_an_occupied_seat_raises_integrity_error(
    app_role_url: str,
) -> None:
    """The oversell backstop the service maps to SLOT_UNAVAILABLE. Two
    DIFFERENT customers, so it is 0008's slot-seat index under test and not
    0009's per-customer instant one."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    customers = CustomersRepository()
    bookings = BookingsRepository()
    try:
        async with tenant_session(factory, tenant_id) as session:
            mover = await customers.upsert(session, tenant_id, phone=_phone(), name="שירה")
            sitter = await customers.upsert(session, tenant_id, phone=_phone(), name="תמר")
            moving = await _insert_booking(
                bookings, session, tenant_id, mover.id, starts_at=T0, seat_index=1
            )
            moving_id = moving.id
            await _insert_booking(
                bookings, session, tenant_id, sitter.id, starts_at=T1, seat_index=1
            )

        with pytest.raises(IntegrityError):
            async with tenant_session(factory, tenant_id) as session:
                await bookings.reschedule(
                    session, tenant_id, moving_id, starts_at=T1, seat_index=1, not_before=NOW
                )
    finally:
        await engine.dispose()


async def test_list_day_returns_the_whole_day_cancelled_rows_included(
    app_role_url: str,
) -> None:
    """D17: a cancelled row IS in the owner's list — it is her evidence that the
    slot re-opened — so this does NOT inherit count_by_start's
    `status <> 'cancelled'` reflex."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    customers = CustomersRepository()
    bookings = BookingsRepository()
    try:
        async with tenant_session(factory, tenant_id) as session:
            first = await customers.upsert(session, tenant_id, phone=_phone(), name="אורית")
            second = await customers.upsert(session, tenant_id, phone=_phone(), name="הילה")
            seat1 = await _insert_booking(
                bookings, session, tenant_id, first.id, starts_at=T0, seat_index=1
            )
            seat2 = await _insert_booking(
                bookings, session, tenant_id, second.id, starts_at=T0, seat_index=2
            )
            later = await _insert_booking(
                bookings, session, tenant_id, first.id, starts_at=T1, seat_index=1
            )
            # The next Jerusalem day — outside the half-open right edge.
            await _insert_booking(
                bookings, session, tenant_id, first.id, starts_at=DAY_END, seat_index=1
            )
            await bookings.cancel(
                session, tenant_id, seat2.id, at=NOW, by=BookingCancelledBy.OWNER.value
            )

            rows, total = await bookings.list_day(
                session,
                tenant_id,
                from_instant=DAY_START,
                until_instant=DAY_END,
                offset=0,
                limit=50,
            )
            assert total == 3
            assert [row.id for row in rows] == [seat1.id, seat2.id, later.id]
            assert rows[1].status == BookingStatus.CANCELLED.value

            # total counts the whole day, not the page.
            page, page_total = await bookings.list_day(
                session,
                tenant_id,
                from_instant=DAY_START,
                until_instant=DAY_END,
                offset=1,
                limit=1,
            )
            assert page_total == 3
            assert [row.id for row in page] == [seat2.id]

            seat1.deleted_at = datetime.datetime.now(datetime.UTC)
            await session.flush()
            _, after_delete = await bookings.list_day(
                session,
                tenant_id,
                from_instant=DAY_START,
                until_instant=DAY_END,
                offset=0,
                limit=50,
            )
            assert after_delete == 2
    finally:
        await engine.dispose()


async def test_list_live_for_customer_returns_only_her_future_confirmed_bookings(
    app_role_url: str,
) -> None:
    """D8's rotation set: every booking whose manage link must be re-minted when
    the phone behind it changes."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    customers = CustomersRepository()
    bookings = BookingsRepository()
    try:
        async with tenant_session(factory, tenant_id) as session:
            hers = await customers.upsert(session, tenant_id, phone=_phone(), name="יעל")
            other = await customers.upsert(session, tenant_id, phone=_phone(), name="ליאת")

            early = await _insert_booking(
                bookings, session, tenant_id, hers.id, starts_at=T0, seat_index=1
            )
            late = await _insert_booking(
                bookings, session, tenant_id, hers.id, starts_at=T1, seat_index=1
            )
            # Past, and therefore not a live link.
            await _insert_booking(
                bookings, session, tenant_id, hers.id, starts_at=PAST_SLOT, seat_index=1
            )
            # Future but terminal, and a soft-deleted one.
            cancelled = await _insert_booking(
                bookings, session, tenant_id, hers.id, starts_at=DAY_END, seat_index=1
            )
            cancelled.status = BookingStatus.CANCELLED.value
            scrubbed = await _insert_booking(
                bookings, session, tenant_id, hers.id, starts_at=DAY_END, seat_index=2
            )
            scrubbed.deleted_at = datetime.datetime.now(datetime.UTC)
            # Another customer's future booking is not hers to rotate.
            await _insert_booking(
                bookings, session, tenant_id, other.id, starts_at=T0, seat_index=3
            )
            await session.flush()

            live = await bookings.list_live_for_customer(
                session, tenant_id, customer_id=hers.id, after=NOW
            )
            assert [row.id for row in live] == [early.id, late.id]
    finally:
        await engine.dispose()


async def test_set_phone_rewrites_the_number_and_the_index_is_the_backstop(
    app_role_url: str,
) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    customers = CustomersRepository()
    corrected = _phone()
    try:
        async with tenant_session(factory, tenant_id) as session:
            customer = await customers.upsert(session, tenant_id, phone=_phone(), name="שני")
            customer_id = customer.id

            updated = await customers.set_phone(session, tenant_id, customer_id, phone=corrected)
            assert updated is not None
            assert updated.phone == corrected
            assert (await customers.by_phone(session, tenant_id, phone=corrected)) is not None
            assert (
                await customers.set_phone(session, tenant_id, uuid.uuid4(), phone=_phone()) is None
            )

        # A number already held by another LIVE customer of this tenant is
        # 0008's partial unique index refusing — the service pre-checks and
        # re-points the booking instead of ever reaching this.
        async with tenant_session(factory, tenant_id) as session:
            rival = await customers.upsert(session, tenant_id, phone=_phone(), name="אביגיל")
            rival_id = rival.id

        with pytest.raises(IntegrityError):
            async with tenant_session(factory, tenant_id) as session:
                await customers.set_phone(session, tenant_id, rival_id, phone=corrected)
    finally:
        await engine.dispose()


async def test_set_manage_token_hash_guard_refuses_a_stale_booking(
    app_role_url: str,
) -> None:
    """D8's rotation carries the same predicate the Python guard checked, so it
    cannot go stale mid-operation: a booking that stopped being
    confirmed-and-future between the read and the rotation must not receive a
    fresh live control token.

    Unguarded (no kwargs) is byte-for-byte today's behaviour — the backfill and
    `reissue_manage_token` are the callers that rely on it.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    customers = CustomersRepository()
    bookings = BookingsRepository()
    guard = (BookingStatus.CONFIRMED.value,)
    try:
        async with tenant_session(factory, tenant_id) as session:
            customer = await customers.upsert(session, tenant_id, phone=_phone(), name="נועה")

            live = await _insert_booking(
                bookings, session, tenant_id, customer.id, starts_at=T0, seat_index=1
            )
            past = await _insert_booking(
                bookings, session, tenant_id, customer.id, starts_at=PAST_SLOT, seat_index=1
            )
            gone = await _insert_booking(
                bookings, session, tenant_id, customer.id, starts_at=T1, seat_index=1
            )
            gone.status = BookingStatus.CANCELLED.value
            await session.flush()

            rotated = await bookings.set_manage_token_hash(
                session,
                tenant_id,
                live.id,
                token_hash="a" * 64,
                allowed_from=guard,
                not_before=NOW,
            )
            assert rotated is not None
            assert rotated.manage_token_hash == "a" * 64

            # Past, and cancelled: both refused, and neither hash moves.
            assert (
                await bookings.set_manage_token_hash(
                    session,
                    tenant_id,
                    past.id,
                    token_hash="b" * 64,
                    allowed_from=guard,
                    not_before=NOW,
                )
                is None
            )
            assert (
                await bookings.set_manage_token_hash(
                    session,
                    tenant_id,
                    gone.id,
                    token_hash="b" * 64,
                    allowed_from=guard,
                    not_before=NOW,
                )
                is None
            )
            untouched = await bookings.by_id(session, tenant_id, past.id)
            assert untouched is not None and untouched.manage_token_hash is None

            # No kwargs: the shipped, unguarded contract the backfill uses.
            filled = await bookings.set_manage_token_hash(
                session, tenant_id, past.id, token_hash="c" * 64
            )
            assert filled is not None and filled.manage_token_hash == "c" * 64
    finally:
        await engine.dispose()


async def test_set_customer_id_repoints_the_booking_under_the_same_guard(
    app_role_url: str,
) -> None:
    """D8's collision branch: the number identifies a person and that person
    already has a record, so the booking moves to her rather than the digits
    moving onto a row that is not hers."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    customers = CustomersRepository()
    bookings = BookingsRepository()
    guard = (BookingStatus.CONFIRMED.value,)
    try:
        async with tenant_session(factory, tenant_id) as session:
            wrong = await customers.upsert(session, tenant_id, phone=_phone(), name="מיכל")
            right = await customers.upsert(session, tenant_id, phone=_phone(), name="דנה")

            booking = await _insert_booking(
                bookings, session, tenant_id, wrong.id, starts_at=T0, seat_index=1
            )
            moved = await bookings.set_customer_id(
                session,
                tenant_id,
                booking.id,
                customer_id=right.id,
                allowed_from=guard,
                not_before=NOW,
            )
            assert moved is not None
            assert moved.customer_id == right.id
            # Both customer rows survive — soft-deleting on a guess is worse
            # than leaving a row nobody looks at.
            assert (await customers.by_id(session, tenant_id, wrong.id)) is not None

            past = await _insert_booking(
                bookings, session, tenant_id, wrong.id, starts_at=PAST_SLOT, seat_index=1
            )
            assert (
                await bookings.set_customer_id(
                    session,
                    tenant_id,
                    past.id,
                    customer_id=right.id,
                    allowed_from=guard,
                    not_before=NOW,
                )
                is None
            )
    finally:
        await engine.dispose()


async def test_set_customer_id_onto_a_customer_who_holds_the_instant_raises(
    app_role_url: str,
) -> None:
    """0009's index: two sisters live in one capacity-2 slot, and correcting the
    first one's number onto the second's would put two live rows on
    (tenant, customer B, T0). The service pre-checks with `active_at` so this
    409s rather than 500s; the flush is the backstop."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    customers = CustomersRepository()
    bookings = BookingsRepository()
    try:
        async with tenant_session(factory, tenant_id) as session:
            first = await customers.upsert(session, tenant_id, phone=_phone(), name="שירה")
            second = await customers.upsert(session, tenant_id, phone=_phone(), name="תמר")
            hers = await _insert_booking(
                bookings, session, tenant_id, first.id, starts_at=T0, seat_index=1
            )
            await _insert_booking(
                bookings, session, tenant_id, second.id, starts_at=T0, seat_index=2
            )
            await session.flush()
            booking_id = hers.id
            second_id = second.id

        with pytest.raises(IntegrityError):
            async with tenant_session(factory, tenant_id) as session:
                await bookings.set_customer_id(
                    session,
                    tenant_id,
                    booking_id,
                    customer_id=second_id,
                    allowed_from=(BookingStatus.CONFIRMED.value,),
                    not_before=NOW,
                )
                await session.flush()
    finally:
        await engine.dispose()


async def test_check_in_writes_once_and_a_second_call_keeps_the_first_timestamp(
    app_role_url: str,
) -> None:
    """The two zero-row causes mean opposite things, so the writer answers three
    values and not a bare `Booking | None` (spec D4(5)).

    `ALREADY_CHECKED_IN` carries the FIRST writer's timestamp, and that is the
    guarantee the whole feature exists to make: two staffers tapping the same
    bride both get a success and there is one arrival time."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    customers = CustomersRepository()
    bookings = BookingsRepository()
    try:
        async with tenant_session(factory, tenant_id) as session:
            customer = await customers.upsert(session, tenant_id, phone=_phone(), name="נועה")
            booking = await _insert_booking(
                bookings, session, tenant_id, customer.id, starts_at=T0, seat_index=1
            )

            outcome, row = await bookings.check_in(session, tenant_id, booking.id, at=FIRST_ARRIVAL)
            assert outcome is CheckInOutcome.WROTE
            assert row is not None
            assert row.checked_in_at == FIRST_ARRIVAL

            # The second tap matches zero rows on `checked_in_at IS NULL`…
            outcome, row = await bookings.check_in(
                session, tenant_id, booking.id, at=SECOND_ARRIVAL
            )
            assert outcome is CheckInOutcome.ALREADY_CHECKED_IN
            assert row is not None
            # …and renders the FIRST time, not this request's.
            assert row.checked_in_at == FIRST_ARRIVAL
            assert row.checked_in_at != SECOND_ARRIVAL
    finally:
        await engine.dispose()


async def test_check_in_answers_not_confirmed_on_every_terminal_status(
    app_role_url: str,
) -> None:
    """The other zero-row cause. `cancelled` is the one that matters in
    practice — it is what a concurrent cancel leaves behind — but the predicate
    is `status = 'confirmed'`, so no-show and completed refuse identically and
    all three are asserted rather than assumed from one.

    Nothing is written in any of the three, which is the half a 200 would hide."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    customers = CustomersRepository()
    bookings = BookingsRepository()
    try:
        async with tenant_session(factory, tenant_id) as session:
            customer = await customers.upsert(session, tenant_id, phone=_phone(), name="שירה")
            for seat, status in enumerate(
                (
                    BookingStatus.CANCELLED.value,
                    BookingStatus.NO_SHOW.value,
                    BookingStatus.COMPLETED.value,
                ),
                start=1,
            ):
                booking = await _insert_booking(
                    bookings,
                    session,
                    tenant_id,
                    customer.id,
                    starts_at=PAST_SLOT + datetime.timedelta(days=seat),
                    seat_index=seat,
                )
                # `insert` takes no status — the column carries a server default
                # and every writer that moves it is guarded. Set it directly, the
                # way the deleted_at probes above do.
                booking.status = status
                await session.flush()

                outcome, row = await bookings.check_in(
                    session, tenant_id, booking.id, at=FIRST_ARRIVAL
                )
                assert outcome is CheckInOutcome.NOT_CONFIRMED, status
                assert row is not None, status
                assert row.checked_in_at is None, status
    finally:
        await engine.dispose()


async def test_check_in_answers_missing_for_an_unknown_id_and_a_soft_deleted_row(
    app_role_url: str,
) -> None:
    """`MISSING` is what the service turns into a 404, and a soft-deleted row
    must reach it by the same path as an id that was never real — the two are
    indistinguishable to the caller on purpose, exactly as they are under RLS
    for another tenant's booking."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    customers = CustomersRepository()
    bookings = BookingsRepository()
    try:
        async with tenant_session(factory, tenant_id) as session:
            customer = await customers.upsert(session, tenant_id, phone=_phone(), name="תמר")
            booking = await _insert_booking(
                bookings, session, tenant_id, customer.id, starts_at=T0, seat_index=1
            )

            outcome, row = await bookings.check_in(
                session, tenant_id, uuid.uuid4(), at=FIRST_ARRIVAL
            )
            assert outcome is CheckInOutcome.MISSING
            assert row is None

            booking.deleted_at = datetime.datetime.now(datetime.UTC)
            await session.flush()
            outcome, row = await bookings.check_in(session, tenant_id, booking.id, at=FIRST_ARRIVAL)
            assert outcome is CheckInOutcome.MISSING
            assert row is None
    finally:
        await engine.dispose()


async def test_undo_check_in_clears_it_and_a_second_undo_reads_already_clear(
    app_role_url: str,
) -> None:
    """`ALREADY_CHECKED_IN` reads as "it is already clear" here — the member
    names the fact that the PREDICATE'S TARGET STATE already holds, which is the
    same fact under both verbs and is why both answer 200 unchanged."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    customers = CustomersRepository()
    bookings = BookingsRepository()
    try:
        async with tenant_session(factory, tenant_id) as session:
            customer = await customers.upsert(session, tenant_id, phone=_phone(), name="רות")
            booking = await _insert_booking(
                bookings, session, tenant_id, customer.id, starts_at=T0, seat_index=1
            )
            await bookings.check_in(session, tenant_id, booking.id, at=FIRST_ARRIVAL)

            outcome, row = await bookings.undo_check_in(session, tenant_id, booking.id)
            assert outcome is CheckInOutcome.WROTE
            assert row is not None
            assert row.checked_in_at is None

            outcome, row = await bookings.undo_check_in(session, tenant_id, booking.id)
            assert outcome is CheckInOutcome.ALREADY_CHECKED_IN
            assert row is not None
            assert row.checked_in_at is None
    finally:
        await engine.dispose()


async def test_undo_check_in_takes_no_status_guard_and_clears_a_cancelled_booking(
    app_role_url: str,
) -> None:
    """Spec D5's ruling, asserted rather than left to be inferred from an absent
    predicate: the undo carries NO status guard at all, the `/confirm`
    precedent — a mis-tap is correctable whenever it is noticed.

    A bride checked in and then cancelled must still have the mis-tap undoable.
    Refusing it would leave a permanent wrong arrival record with no remedy, on
    a surface where the tap is one finger wide."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    customers = CustomersRepository()
    bookings = BookingsRepository()
    try:
        async with tenant_session(factory, tenant_id) as session:
            customer = await customers.upsert(session, tenant_id, phone=_phone(), name="מיכל")
            booking = await _insert_booking(
                bookings, session, tenant_id, customer.id, starts_at=T0, seat_index=1
            )
            await bookings.check_in(session, tenant_id, booking.id, at=FIRST_ARRIVAL)
            await bookings.cancel(
                session,
                tenant_id,
                booking.id,
                at=NOW,
                by=BookingCancelledBy.CUSTOMER.value,
            )

            outcome, row = await bookings.undo_check_in(session, tenant_id, booking.id)
            assert outcome is CheckInOutcome.WROTE
            assert row is not None
            assert row.checked_in_at is None
            # …and it cleared ONLY the arrival. The cancellation is untouched.
            assert row.status == BookingStatus.CANCELLED.value

    finally:
        await engine.dispose()


async def test_undo_check_in_answers_missing_for_a_soft_deleted_row(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    customers = CustomersRepository()
    bookings = BookingsRepository()
    try:
        async with tenant_session(factory, tenant_id) as session:
            customer = await customers.upsert(session, tenant_id, phone=_phone(), name="דנה")
            booking = await _insert_booking(
                bookings, session, tenant_id, customer.id, starts_at=T0, seat_index=1
            )
            await bookings.check_in(session, tenant_id, booking.id, at=FIRST_ARRIVAL)
            booking.deleted_at = datetime.datetime.now(datetime.UTC)
            await session.flush()

            outcome, row = await bookings.undo_check_in(session, tenant_id, booking.id)
            assert outcome is CheckInOutcome.MISSING
            assert row is None

            outcome, row = await bookings.undo_check_in(session, tenant_id, uuid.uuid4())
            assert outcome is CheckInOutcome.MISSING
            assert row is None
    finally:
        await engine.dispose()


# --- F19: the deposit hold's two writers ---


async def test_cancel_allowed_from_widens_to_the_deposit_hold(app_role_url: str) -> None:
    """F19 D2: the sweeper's seat release is `cancel` with one widened guard, not
    a second writer of `cancelled_at`/`cancelled_by`.

    The default is `('confirmed',)`, so every shipped caller is byte-identical —
    and that default is exactly what makes the sweeper's row invisible to them:
    no owner or customer path can cancel an unpaid hold out from under the
    gateway.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    customers = CustomersRepository()
    bookings = BookingsRepository()
    try:
        async with tenant_session(factory, tenant_id) as session:
            confirmed_customer = await customers.upsert(
                session, tenant_id, phone=_phone(), name="נועה"
            )
            held_customer = await customers.upsert(session, tenant_id, phone=_phone(), name="רות")
            confirmed = await _insert_booking(
                bookings, session, tenant_id, confirmed_customer.id, starts_at=T0, seat_index=1
            )
            held = await _insert_booking(
                bookings,
                session,
                tenant_id,
                held_customer.id,
                starts_at=T0,
                seat_index=2,
                status=BookingStatus.PENDING_PAYMENT.value,
            )
            assert held.status == BookingStatus.PENDING_PAYMENT.value
            # A held seat is an OCCUPIED seat: every occupancy predicate excludes
            # `cancelled` and nothing else.
            assert await bookings.active_seats_at(session, tenant_id, starts_at=T0) == {1, 2}

            # The default guard refuses the hold...
            assert (
                await bookings.cancel(
                    session, tenant_id, held.id, at=NOW, by=BookingCancelledBy.EXPIRED.value
                )
                is None
            )
            still_held = await bookings.by_id(session, tenant_id, held.id)
            assert still_held is not None
            assert still_held.status == BookingStatus.PENDING_PAYMENT.value

            # ...and the sweeper's guard refuses a confirmed booking, which is
            # what stops a stray sweep from cancelling a paid appointment.
            assert (
                await bookings.cancel(
                    session,
                    tenant_id,
                    confirmed.id,
                    at=NOW,
                    by=BookingCancelledBy.EXPIRED.value,
                    allowed_from=(BookingStatus.PENDING_PAYMENT.value,),
                )
                is None
            )

            swept = await bookings.cancel(
                session,
                tenant_id,
                held.id,
                at=NOW,
                by=BookingCancelledBy.EXPIRED.value,
                allowed_from=(BookingStatus.PENDING_PAYMENT.value,),
            )
            assert swept is not None
            assert swept.status == BookingStatus.CANCELLED.value
            assert swept.cancelled_at == NOW
            # MD5: nobody cancelled it, the hold ran out — and `cancelled_by` is
            # the only column that can keep it out of the cancellation rate.
            assert swept.cancelled_by == BookingCancelledBy.EXPIRED.value
            assert await bookings.active_seats_at(session, tenant_id, starts_at=T0) == {1}

            # The shipped confirmed path is untouched by the new keyword.
            cancelled = await bookings.cancel(
                session, tenant_id, confirmed.id, at=NOW, by=BookingCancelledBy.OWNER.value
            )
            assert cancelled is not None
            assert cancelled.status == BookingStatus.CANCELLED.value
    finally:
        await engine.dispose()


async def test_rebind_reinstates_the_seat_and_clears_the_cancel_evidence(
    app_role_url: str,
) -> None:
    """F19 D5 step 3, as ONE statement. Splitting it would leave a window where
    the row reads `confirmed` at a stale seat index — and because `create_booking`
    hands freed seat numbers back out, that stale index is very likely another
    bride's seat.

    Both `cancelled_at` and `cancelled_by` are cleared, because a row reading
    `confirmed` while carrying cancel evidence is the exact defect that made
    `set_status` wrong for the cancel path, and those two columns feed F52's
    attribution and F20's compliance read.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    customers = CustomersRepository()
    bookings = BookingsRepository()
    try:
        async with tenant_session(factory, tenant_id) as session:
            customer = await customers.upsert(session, tenant_id, phone=_phone(), name="מאיה")
            booking = await _insert_booking(
                bookings, session, tenant_id, customer.id, starts_at=T0, seat_index=1
            )
            swept = await bookings.cancel(
                session, tenant_id, booking.id, at=NOW, by=BookingCancelledBy.EXPIRED.value
            )
            assert swept is not None

            reinstated = await bookings.rebind(
                session,
                tenant_id,
                booking.id,
                seat_index=3,
                allowed_from=(
                    BookingStatus.CANCELLED.value,
                    BookingStatus.PENDING_PAYMENT.value,
                ),
                not_before=NOW,
            )
            assert reinstated is not None
            assert reinstated.status == BookingStatus.CONFIRMED.value
            assert reinstated.seat_index == 3
            assert reinstated.cancelled_at is None
            assert reinstated.cancelled_by is None
            assert await bookings.active_seats_at(session, tenant_id, starts_at=T0) == {3}
    finally:
        await engine.dispose()


async def test_rebind_admits_the_hold_status_for_the_sweeper_ordering_race(
    app_role_url: str,
) -> None:
    """D5's fourth bullet, and D6 race #13. If the sweeper's payments UPDATE has
    committed but its booking cancel has not been observed, the booking is still
    `pending_payment` — a narrow `('cancelled',)` would match nothing and file a
    FALSE "seat taken" alert on a seat that is in fact free."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    customers = CustomersRepository()
    bookings = BookingsRepository()
    try:
        async with tenant_session(factory, tenant_id) as session:
            customer = await customers.upsert(session, tenant_id, phone=_phone(), name="שירה")
            held = await _insert_booking(
                bookings,
                session,
                tenant_id,
                customer.id,
                starts_at=T0,
                seat_index=1,
                status=BookingStatus.PENDING_PAYMENT.value,
            )

            assert (
                await bookings.rebind(
                    session,
                    tenant_id,
                    held.id,
                    seat_index=1,
                    allowed_from=(BookingStatus.CANCELLED.value,),
                    not_before=NOW,
                )
                is None
            )

            honoured = await bookings.rebind(
                session,
                tenant_id,
                held.id,
                seat_index=1,
                allowed_from=(
                    BookingStatus.CANCELLED.value,
                    BookingStatus.PENDING_PAYMENT.value,
                ),
                not_before=NOW,
            )
            assert honoured is not None
            assert honoured.status == BookingStatus.CONFIRMED.value
            assert honoured.seat_index == 1
    finally:
        await engine.dispose()


async def test_rebind_refuses_a_past_booking_and_an_unknown_id(app_role_url: str) -> None:
    """`not_before` is REQUIRED on this writer, unlike on its siblings. The
    provider's retry budget against a 15-minute hold is unknowable until a real
    PSP exists, so without the bound a delivery days late would flip a PAST
    booking to `confirmed`, mint a fresh manage token, and text the bride
    "your appointment is confirmed" for a date that has already gone — while
    silently re-occupying a seat in a past slot.

    Every miss is `None`, never an exception: D5 step 4 is a real branch (alert
    the owner, hold the money), not an error path."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    customers = CustomersRepository()
    bookings = BookingsRepository()
    try:
        async with tenant_session(factory, tenant_id) as session:
            customer = await customers.upsert(session, tenant_id, phone=_phone(), name="תמר")
            past = await _insert_booking(
                bookings, session, tenant_id, customer.id, starts_at=PAST_SLOT, seat_index=1
            )
            await bookings.cancel(
                session, tenant_id, past.id, at=NOW, by=BookingCancelledBy.EXPIRED.value
            )

            assert (
                await bookings.rebind(
                    session,
                    tenant_id,
                    past.id,
                    seat_index=1,
                    allowed_from=(BookingStatus.CANCELLED.value,),
                    not_before=NOW,
                )
                is None
            )
            unchanged = await bookings.by_id(session, tenant_id, past.id)
            assert unchanged is not None
            assert unchanged.status == BookingStatus.CANCELLED.value
            assert unchanged.cancelled_by == BookingCancelledBy.EXPIRED.value

            assert (
                await bookings.rebind(
                    session,
                    tenant_id,
                    uuid.uuid4(),
                    seat_index=1,
                    allowed_from=(BookingStatus.CANCELLED.value,),
                    not_before=NOW,
                )
                is None
            )

            future = await _insert_booking(
                bookings, session, tenant_id, customer.id, starts_at=T0, seat_index=1
            )
            future.deleted_at = datetime.datetime.now(datetime.UTC)
            await session.flush()
            assert (
                await bookings.rebind(
                    session,
                    tenant_id,
                    future.id,
                    seat_index=2,
                    allowed_from=(BookingStatus.CONFIRMED.value,),
                    not_before=NOW,
                )
                is None
            )
    finally:
        await engine.dispose()


def _f13_table_count(url: str) -> int:
    async def count() -> int:
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                result = await conn.execute(
                    text(
                        "SELECT count(*) FROM pg_tables "
                        "WHERE tablename IN ('customers', 'bookings')"
                    )
                )
                return int(result.scalar_one())
        finally:
            await engine.dispose()

    return asyncio.run(count())


def test_migration_0008_round_trips(migrated_db: str) -> None:
    """downgrade drops bookings then customers; upgrade puts both back with
    their indexes, grants and policies. Runs as the migration owner (the app
    role cannot DROP), and destroys rows — so it owns no fixtures and shares no
    state with the tests above."""
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", migrated_db)

    assert _f13_table_count(migrated_db) == 2
    command.downgrade(cfg, "0007")
    assert _f13_table_count(migrated_db) == 0
    command.upgrade(cfg, "head")
    assert _f13_table_count(migrated_db) == 2
