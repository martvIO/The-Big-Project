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

from app.db.repositories.bookings import BookingsRepository
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


async def test_cancel_without_not_before_is_byte_for_byte_todays_behaviour(
    app_role_url: str,
) -> None:
    """F16's ManageBookingService.cancel does not pass `not_before`, and its
    BookingAlreadyStartedError contract depends on cancel still returning the
    row through its trailing by_id whatever the predicate did. Passing the
    keyword adds `starts_at > :not_before`; omitting it changes nothing."""
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

            # F15's owner path passes it, and a past booking is refused — but
            # the row still comes back, un-cancelled, not None.
            refused = await bookings.cancel(
                session,
                tenant_id,
                past.id,
                at=NOW,
                by=BookingCancelledBy.OWNER.value,
                not_before=NOW,
            )
            assert refused is not None
            assert refused.cancelled_by == BookingCancelledBy.CUSTOMER.value

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
