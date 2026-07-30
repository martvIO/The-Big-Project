"""F15's owner console against real Postgres as the non-owner app role.

Everything here is a claim no fake can make. The reschedule protocol's whole
correctness argument is an ORDERING — advisory lock, then read, then the guarded
UPDATE — and an ordering is only provable against a real transaction with a real
second connection racing it. So is the seat arithmetic (two partial unique
indexes are DDL), the 0009 re-point collision (a flush that must be a 409 and
never a 500), the rotation's atomicity (there must be NO committed state in which
the phone is corrected and the old link still resolves), and RLS.

NullPool + asyncio.gather gives every racer its own connection — the
`test_booking_service.py` precedent, and what makes the concurrency tests real
rather than two coroutines sharing one session.

**The post-commit sends are the ROUTER's** (D11), so the tests that care about
send ordering call the seam themselves, immediately after the service returns,
exactly the way `owner_router.py` does. Reversing those two lines is what the
ordering proof exists to fail on.
"""

import asyncio
import datetime
import secrets
import uuid
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.service import StaffContext
from app.auth.tokens import hash_token
from app.booking.comms import BookingCommsService, CommsTenant
from app.booking.manage import (
    BookingLinkInvalidError,
    ManageBookingService,
    ManageTenant,
)
from app.booking.owner import (
    BookingTransitionInvalidError,
    CustomerAlreadyBookedError,
    OwnerBookingService,
    OwnerResendThrottledError,
)
from app.booking.service import BookingNotFoundError, BookingService, SlotUnavailableError
from app.booking.tokens import manage_token_hash
from app.booking.validation import BOOKING_LIST_DEFAULT_LIMIT, jerusalem_day_index
from app.db.repositories.appointment_types import AppointmentTypesRepository
from app.db.repositories.availability import AvailabilityRulesRepository
from app.db.repositories.bookings import BookingsRepository
from app.db.repositories.customers import CustomersRepository
from app.db.repositories.otp_codes import OtpCodesRepository
from app.db.repositories.scheduled_messages import ScheduledMessagesRepository
from app.db.repositories.terms import TermsVersionsRepository
from app.db.tenant import tenant_session
from app.models.audit_log import AuditLog
from app.models.booking import Booking
from app.models.constants import (
    AppointmentAudience,
    AuditAction,
    BookingCancelledBy,
    BookingStatus,
    ScheduledMessageKind,
    StaffRole,
)
from app.notifications.fake import FakeSmsSender
from app.notifications.service import NotificationService, OtpService
from app.notifications.unconfigured import UnconfiguredSmsSender
from app.notifications.validation import normalize_israeli_mobile
from app.storage.memory import InMemoryMediaStorage
from app.storefront.service import StorefrontService
from app.storefront.validation import BOUTIQUE_TIMEZONE

pytestmark = pytest.mark.db

NOW = datetime.datetime(2026, 7, 28, 12, 0, tzinfo=datetime.UTC)
FUTURE = datetime.datetime(2099, 1, 1, tzinfo=datetime.UTC)
# A boutique day a month after the frozen NOW: comfortably future so the engine
# never drops it, comfortably inside the publishable horizon. The weekly rule is
# derived from THIS date's weekday, so the grid always opens it.
TARGET_DATE = datetime.date(2026, 8, 23)
BASE_DOMAIN = "modryn.co.il"
REMINDER = ScheduledMessageKind.REMINDER.value


def _slot(hour: int, minute: int = 0, *, date: datetime.date = TARGET_DATE) -> datetime.datetime:
    return datetime.datetime.combine(
        date, datetime.time(hour, minute), tzinfo=BOUTIQUE_TIMEZONE
    ).astimezone(datetime.UTC)


# Three offered instants inside the seeded 09:00–13:00 window.
SLOT_A = _slot(10, 0)
SLOT_B = _slot(11, 0)
SLOT_C = _slot(12, 0)


def _factory(url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(url, poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _phone() -> str:
    return f"+9725{uuid.uuid4().int % 10**8:08d}"


def _loose() -> FixedWindowRateLimiter:
    return FixedWindowRateLimiter(max_attempts=10_000, window_seconds=3600, clock=lambda: 0.0)


def _spent() -> FixedWindowRateLimiter:
    """max_attempts=0, so `is_blocked` is True for every key from the first call."""
    return FixedWindowRateLimiter(max_attempts=0, window_seconds=3600, clock=lambda: 0.0)


def _staff(tenant_id: uuid.UUID) -> StaffContext:
    return StaffContext(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        email="owner@bella.example",
        display_name="בעלת הסלון",
        role=StaffRole.OWNER.value,
    )


def _booking_service(
    factory: async_sessionmaker[AsyncSession], *, now: datetime.datetime = NOW
) -> BookingService:
    otp = OtpService(
        factory,
        notifications=NotificationService(factory, sender=UnconfiguredSmsSender()),
        phone_limiter=_loose(),
        tenant_limiter=_loose(),
        verify_limiter=_loose(),
        clock=lambda: now,
    )
    return BookingService(
        factory, otp=otp, create_limiter=_loose(), phone_limiter=_loose(), clock=lambda: now
    )


def _comms(
    factory: async_sessionmaker[AsyncSession],
    *,
    sender: Any | None = None,
    now: datetime.datetime = NOW,
) -> tuple[BookingCommsService, Any]:
    resolved = sender if sender is not None else FakeSmsSender()
    service = BookingCommsService(
        factory,
        notifications=NotificationService(factory, sender=resolved),
        base_domain=BASE_DOMAIN,
        clock=lambda: now,
    )
    return service, resolved


def _owner(
    factory: async_sessionmaker[AsyncSession],
    *,
    now: datetime.datetime = NOW,
    sms_limiter: FixedWindowRateLimiter | None = None,
    comms: BookingCommsService | None = None,
) -> OwnerBookingService:
    resolved_comms = comms if comms is not None else _comms(factory, now=now)[0]
    return OwnerBookingService(
        factory,
        storefront=StorefrontService(
            factory, media_storage=InMemoryMediaStorage(), clock=lambda: now
        ),
        comms=resolved_comms,
        sms_limiter=sms_limiter if sms_limiter is not None else _loose(),
        clock=lambda: now,
    )


def _manage(
    factory: async_sessionmaker[AsyncSession], *, now: datetime.datetime = NOW
) -> ManageBookingService:
    return ManageBookingService(factory, lookup_limiter=_loose(), clock=lambda: now)


def _comms_tenant(tenant_id: uuid.UUID) -> CommsTenant:
    return CommsTenant(id=tenant_id, slug="bella", name="בלה כלות", phone="052-1234567")


def _manage_tenant(tenant_id: uuid.UUID) -> ManageTenant:
    return ManageTenant(id=tenant_id, name="בלה כלות", settings={})


async def _seed(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    *,
    capacity: int = 1,
    date: datetime.date = TARGET_DATE,
) -> uuid.UUID:
    async with tenant_session(factory, tenant_id) as session:
        await AvailabilityRulesRepository().insert(
            session,
            tenant_id=tenant_id,
            day_of_week=jerusalem_day_index(date),
            open_time=datetime.time(9, 0),
            close_time=datetime.time(13, 0),
            capacity=capacity,
        )
        type_row = await AppointmentTypesRepository().insert(
            session,
            tenant_id=tenant_id,
            name="מדידה ראשונה",
            duration_minutes=60,
            audience=AppointmentAudience.ALL.value,
            deposit_required=False,
            deposit_amount_agorot=None,
            sort_order=0,
        )
        await TermsVersionsRepository().insert(
            session,
            tenant_id=tenant_id,
            version=1,
            terms_text="תנאי ביטול",
            refundable_until_hours_before=48,
            forfeit_percent=50,
            created_by=uuid.uuid4(),
        )
        return type_row.id


async def _token(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, raw_phone: str
) -> str:
    token = secrets.token_urlsafe(16)
    repo = OtpCodesRepository()
    async with tenant_session(factory, tenant_id) as session:
        row = await repo.insert(
            session,
            tenant_id=tenant_id,
            phone=normalize_israeli_mobile(raw_phone),
            code_hash="seed",
            expires_at=FUTURE,
        )
        await repo.mark_consumed(
            session,
            tenant_id,
            row.id,
            verification_token_hash=hash_token(token),
            verification_expires_at=FUTURE,
        )
    return token


async def _claim(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    type_id: uuid.UUID,
    *,
    starts_at: datetime.datetime = SLOT_A,
    now: datetime.datetime = NOW,
    phone: str | None = None,
) -> Any:
    resolved = phone if phone is not None else _phone()
    return await _booking_service(factory, now=now).create_booking(
        tenant_id,
        raw_phone=resolved,
        verification_token=await _token(factory, tenant_id, resolved),
        name="נועה לוי",
        appointment_type_id=type_id,
        starts_at=starts_at,
        terms_version=1,
    )


async def _row(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, booking_id: uuid.UUID
) -> Booking | None:
    async with tenant_session(factory, tenant_id) as session:
        return await BookingsRepository().by_id(session, tenant_id, booking_id)


async def _audit(factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID) -> list[AuditLog]:
    """RLS scopes this to the tenant, and every test mints a fresh tenant id, so
    "the audit rows" is unambiguous without a per-test filter."""
    async with tenant_session(factory, tenant_id) as session:
        stmt = select(AuditLog).order_by(AuditLog.created_at)
        return list((await session.execute(stmt)).scalars().all())


async def _pending(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, booking_id: uuid.UUID
) -> Any:
    async with tenant_session(factory, tenant_id) as session:
        return await ScheduledMessagesRepository().pending_for_booking(
            session, tenant_id, booking_id=booking_id, kind=REMINDER
        )


async def _make_due(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, booking_id: uuid.UUID
) -> None:
    """Pull the pending reminder's send_after into the past so one tick claims it."""
    async with tenant_session(factory, tenant_id) as session:
        pending = await ScheduledMessagesRepository().pending_for_booking(
            session, tenant_id, booking_id=booking_id, kind=REMINDER
        )
        assert pending is not None
        pending.send_after = NOW - datetime.timedelta(minutes=1)


def _link_token(body: str) -> str:
    """The manage link is `https://{slug}.{domain}/b/{token}` and every body puts
    it last, so the tail after the final slash is the raw token."""
    return body.rsplit("/", 1)[-1].strip()


async def _resolves(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, token: str
) -> bool:
    try:
        await _manage(factory).lookup(_manage_tenant(tenant_id), token=token)
    except BookingLinkInvalidError:
        return False
    return True


# --- the headline: reschedule concurrency ----------------------------------


async def test_a_public_create_and_an_owner_reschedule_onto_one_seat_yield_one_winner(
    app_role_url: str,
) -> None:
    """Capacity 1 at SLOT_B, raced by an anonymous claim and an owner move.

    The per-tenant advisory lock serializes them and the slot-seat partial unique
    index is the backstop; either way exactly one takes the seat and the other
    sees SLOT_UNAVAILABLE. Two rows on one seat is the failure this whole
    protocol exists to make impossible.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=1)
        moving = (await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)).booking
        owner = _owner(factory)
        staff = _staff(tenant_id)

        async def creator() -> Any:
            return (await _claim(factory, tenant_id, type_id, starts_at=SLOT_B)).booking

        async def rescheduler() -> Any:
            return (
                await owner.reschedule(tenant_id, moving.id, new_starts_at=SLOT_B, staff=staff)
            ).booking

        results = await asyncio.gather(creator(), rescheduler(), return_exceptions=True)
        winners = [r for r in results if not isinstance(r, BaseException)]
        losers = [r for r in results if isinstance(r, SlotUnavailableError)]
        assert len(winners) == 1, f"expected one winner, got {results!r}"
        assert len(losers) == 1, f"expected one SlotUnavailableError, got {results!r}"

        async with tenant_session(factory, tenant_id) as session:
            seats = await BookingsRepository().active_seats_at(session, tenant_id, starts_at=SLOT_B)
        assert seats == {1}
    finally:
        await engine.dispose()


async def test_two_concurrent_reschedules_of_one_booking_never_self_collide(
    app_role_url: str,
) -> None:
    """The test that fails if the `by_id` read moves back above the advisory lock.

    Both submissions target free instants. With the read outside the lock they
    would both see the ORIGINAL starts_at, the loser would miss the no-op
    short-circuit, and the per-customer collision check would then find THE
    BOOKING ITSELF and answer CUSTOMER_ALREADY_BOOKED against its own row. With
    the read inside, the second sees the moved row and either short-circuits or
    moves again — and the audit rows chain, never recording T0 twice.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=1)
        moving = (await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)).booking
        owner = _owner(factory)
        staff = _staff(tenant_id)

        async def move(target: datetime.datetime) -> Any:
            return await owner.reschedule(tenant_id, moving.id, new_starts_at=target, staff=staff)

        results = await asyncio.gather(move(SLOT_B), move(SLOT_C), return_exceptions=True)
        for result in results:
            assert not isinstance(result, CustomerAlreadyBookedError), (
                f"a booking collided with itself: {results!r}"
            )
            if isinstance(result, BaseException):
                assert isinstance(result, BookingTransitionInvalidError | SlotUnavailableError), (
                    f"unexpected failure: {result!r}"
                )

        final = await _row(factory, tenant_id, moving.id)
        assert final is not None
        assert final.starts_at in (SLOT_B, SLOT_C)

        rows = [
            row
            for row in await _audit(factory, tenant_id)
            if row.action == AuditAction.BOOKING_RESCHEDULED.value
        ]
        # Whatever committed, the chain is honest: every hop's `old_starts_at` is
        # the previous hop's `new_starts_at`, and the first is the original.
        previous = SLOT_A.isoformat()
        for row in rows:
            assert row.details["old_starts_at"] == previous
            previous = row.details["new_starts_at"]
        assert previous == final.starts_at.isoformat()
    finally:
        await engine.dispose()


# --- the seat arithmetic ---------------------------------------------------


async def test_the_move_takes_the_lowest_free_seat_and_never_carries_the_old_one(
    app_role_url: str,
) -> None:
    """Nothing in the database bounds a seat by its slot's capacity — 0008's
    CHECK is 1..1000 — so carrying seat 3 into a capacity-1 target would satisfy
    both the CHECK and the unique index and silently oversell. Capacity is
    enforced in Python and nowhere else."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=3)
        # Fill seats 1 and 2 at SLOT_A so the third claim lands on seat 3.
        await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)
        await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)
        moving = (await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)).booking
        assert moving.seat_index == 3
        # SLOT_B holds one booking on seat 1... then free it, so seat 1 is the
        # lowest free index at the target rather than the only one.
        neighbour = (await _claim(factory, tenant_id, type_id, starts_at=SLOT_B)).booking
        assert neighbour.seat_index == 1

        moved = (
            await _owner(factory).reschedule(
                tenant_id, moving.id, new_starts_at=SLOT_B, staff=_staff(tenant_id)
            )
        ).booking

        assert (moved.starts_at, moved.seat_index) == (SLOT_B, 2)
        async with tenant_session(factory, tenant_id) as session:
            # The source seat is released with no extra write: both partial
            # unique indexes are re-evaluated over the row's new values.
            assert await BookingsRepository().active_seats_at(
                session, tenant_id, starts_at=SLOT_A
            ) == {1, 2}
    finally:
        await engine.dispose()


async def test_a_full_target_is_slot_unavailable(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=1)
        moving = (await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)).booking
        await _claim(factory, tenant_id, type_id, starts_at=SLOT_B)

        with pytest.raises(SlotUnavailableError):
            await _owner(factory).reschedule(
                tenant_id, moving.id, new_starts_at=SLOT_B, staff=_staff(tenant_id)
            )
        assert await _audit(factory, tenant_id) == []
    finally:
        await engine.dispose()


@pytest.mark.parametrize(
    "target",
    [
        # Off the 30-minute grid: the engine never materializes it.
        pytest.param(_slot(10, 17), id="off-grid"),
        # Before the 09:00 open time on an opened day.
        pytest.param(_slot(7, 0), id="before-open"),
        # A day with no weekly rule at all.
        pytest.param(_slot(10, 0, date=TARGET_DATE + datetime.timedelta(days=1)), id="closed-day"),
        # In the past relative to the frozen clock.
        pytest.param(_slot(10, 0, date=datetime.date(2026, 7, 5)), id="past"),
    ],
)
async def test_an_unoffered_target_is_slot_unavailable(
    app_role_url: str, target: datetime.datetime
) -> None:
    """One `offered_slot` call buys past instants, off-grid times, closed days,
    exception days and the DST rules at once — three implementations of "is this
    bookable" would be three chances to disagree."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=1)
        moving = (await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)).booking

        with pytest.raises(SlotUnavailableError):
            await _owner(factory).reschedule(
                tenant_id, moving.id, new_starts_at=target, staff=_staff(tenant_id)
            )
        unchanged = await _row(factory, tenant_id, moving.id)
        assert unchanged is not None and unchanged.starts_at == SLOT_A
        assert await _audit(factory, tenant_id) == []
    finally:
        await engine.dispose()


async def test_a_move_to_the_instant_it_already_holds_is_a_silent_no_op(
    app_role_url: str,
) -> None:
    """Load-bearing rather than a nicety: `active_at` and `active_seats_at` have
    no booking-id exclusion, so without the short-circuit a capacity-1 booking
    would 409 against its own seat."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=1)
        claim = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)
        _, sender = _comms(factory)

        result = await _owner(factory).reschedule(
            tenant_id, claim.booking.id, new_starts_at=SLOT_A, staff=_staff(tenant_id)
        )

        assert result.changed is False
        assert result.booking.starts_at == SLOT_A
        assert await _audit(factory, tenant_id) == []
        assert sender.outbox == []
        pending = await _pending(factory, tenant_id, claim.booking.id)
        # Untouched, so the link in the reminder she already holds still works.
        assert pending is not None and pending.manage_token == claim.manage_token
    finally:
        await engine.dispose()


async def test_a_customer_already_at_the_target_is_its_own_409(app_role_url: str) -> None:
    """Genuinely different from a full slot: the target can have free seats and
    still be unmovable-into for THIS bride (0009's index)."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=3)
        phone = _phone()
        first = (await _claim(factory, tenant_id, type_id, starts_at=SLOT_A, phone=phone)).booking
        await _claim(factory, tenant_id, type_id, starts_at=SLOT_B, phone=phone)

        with pytest.raises(CustomerAlreadyBookedError):
            await _owner(factory).reschedule(
                tenant_id, first.id, new_starts_at=SLOT_B, staff=_staff(tenant_id)
            )
        assert await _audit(factory, tenant_id) == []
    finally:
        await engine.dispose()


async def test_only_a_confirmed_future_booking_moves(app_role_url: str) -> None:
    """A past booking is an attendance question, not a scheduling one: rewriting
    its `starts_at` would overwrite the record D3 forbids lying about and text
    the bride a confirmation for the appointment she missed."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=1)
        claim = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)
        # The clock now sits after SLOT_A, so the booking is confirmed-and-past.
        late = _owner(factory, now=SLOT_A + datetime.timedelta(hours=1))

        with pytest.raises(BookingTransitionInvalidError):
            await late.reschedule(
                tenant_id, claim.booking.id, new_starts_at=SLOT_C, staff=_staff(tenant_id)
            )
        assert await _audit(factory, tenant_id) == []
    finally:
        await engine.dispose()


# --- the D11 ordering proof and the Risk 10 worker race --------------------


async def test_the_reschedule_notice_carries_a_link_that_still_resolves(
    app_role_url: str,
) -> None:
    """The ordering proof, in the branch that actually breaks: a day-of move
    whose prior reminder has already fired, so there is nothing pending to
    inherit a token from.

    Correct order (the upsert inside the transaction, the notice after commit):
    the pending row carrying a live token is already there, `_live_token` finds
    exactly it, and the SMS carries the same link the future reminder will send —
    one rotation. Reverse the two and `_rotate` mints token A, texts it, and the
    upsert then mints token B and rotates the hash to B, leaving the link in the
    message she is reading right now dead. That is what this test fails on.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    # Late enough that the moved appointment is inside the <24h band, so the
    # reminder is due immediately rather than weeks out.
    now = SLOT_A - datetime.timedelta(hours=6)
    try:
        type_id = await _seed(factory, tenant_id, capacity=1)
        claim = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)
        comms, sender = _comms(factory, now=now)
        # Drain the original reminder, so nothing is pending when the move runs.
        await _make_due(factory, tenant_id, claim.booking.id)
        assert (await _comms(factory)[0].drain_due(_comms_tenant(tenant_id))).sent == 1
        sender.outbox.clear()

        result = await _owner(factory, now=now, comms=comms).reschedule(
            tenant_id, claim.booking.id, new_starts_at=SLOT_C, staff=_staff(tenant_id)
        )
        # Exactly what owner_router.py does, in exactly that order.
        assert await comms.notify_owner_reschedule(_comms_tenant(tenant_id), booking=result.booking)

        pending = await _pending(factory, tenant_id, claim.booking.id)
        assert pending is not None
        assert pending.manage_token is not None
        row = await _row(factory, tenant_id, claim.booking.id)
        assert row is not None
        # ONE rotation: the hash on the row is the token the pending reminder
        # carries, which is the token the notice she just received carries.
        assert row.manage_token_hash == manage_token_hash(pending.manage_token)
        assert await _resolves(factory, tenant_id, pending.manage_token)
        assert pending.manage_token in sender.outbox[-1].body
    finally:
        await engine.dispose()


async def test_the_worker_claiming_between_commit_and_notice_still_leaves_a_live_link(
    app_role_url: str,
) -> None:
    """Risk 10, asserted as an OUTCOME rather than as the absence of the race.

    `drain_due` is a third concurrent actor: it can claim, send and `mark()` the
    freshly-committed reminder — clearing `manage_token` — in the milliseconds
    before the notice runs. `_live_token` then returns None and `_rotate` mints
    again, killing the link in the reminder she received seconds ago. Accepted,
    because the message that matters is the NEWER one: the reschedule notice,
    which states the correct time, and it carries the live link.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    now = SLOT_A - datetime.timedelta(hours=6)
    try:
        type_id = await _seed(factory, tenant_id, capacity=1)
        claim = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)
        comms, sender = _comms(factory, now=now)

        result = await _owner(factory, now=now, comms=comms).reschedule(
            tenant_id, claim.booking.id, new_starts_at=SLOT_C, staff=_staff(tenant_id)
        )
        # The worker wins the window: it drains the reminder the transaction just
        # committed, and `mark()` clears the raw token off the terminal row.
        await _make_due(factory, tenant_id, claim.booking.id)
        assert (await comms.drain_due(_comms_tenant(tenant_id))).sent == 1
        assert await comms.notify_owner_reschedule(_comms_tenant(tenant_id), booking=result.booking)

        row = await _row(factory, tenant_id, claim.booking.id)
        assert row is not None and row.manage_token_hash is not None
        # `mark()` cleared the raw token off the terminal row, so there is
        # nothing pending for `_live_token` to inherit — the race really happened.
        assert await _pending(factory, tenant_id, claim.booking.id) is None
        # The outcome that matters: the bride's NEWEST message is the reschedule
        # notice, it states the correct time, and its link resolves.
        newest = _link_token(sender.outbox[-1].body)
        assert "הועבר" in sender.outbox[-1].body
        assert manage_token_hash(newest) == row.manage_token_hash
        assert await _resolves(factory, tenant_id, newest)
    finally:
        await engine.dispose()


# --- owner cancel ----------------------------------------------------------


async def test_owner_cancel_frees_the_seat_kills_the_reminder_and_texts_once(
    app_role_url: str,
) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=1)
        claim = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)
        comms, sender = _comms(factory)
        staff = _staff(tenant_id)

        result = await _owner(factory, comms=comms).cancel(tenant_id, claim.booking.id, staff=staff)
        assert await comms.notify_owner_cancel(_comms_tenant(tenant_id), booking=result.booking)

        row = await _row(factory, tenant_id, claim.booking.id)
        assert row is not None
        assert row.status == BookingStatus.CANCELLED.value
        assert row.cancelled_by == BookingCancelledBy.OWNER.value
        assert row.cancelled_at == NOW

        # `notify_owner_cancel` does not touch scheduled_messages, so without the
        # service's own cancel_pending the bride would get a cancellation SMS and
        # then a reminder for the cancelled appointment.
        assert await _pending(factory, tenant_id, claim.booking.id) is None

        # The seat genuinely re-opens: only cancellation frees one.
        rebooked = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)
        assert rebooked.booking.seat_index == 1

        [audit] = await _audit(factory, tenant_id)
        assert audit.action == AuditAction.BOOKING_CANCELLED.value
        assert audit.actor_id == staff.id
        assert audit.entity == str(claim.booking.id)
        assert audit.details == {"from": "confirmed", "to": "cancelled"}
        assert len(sender.outbox) == 1
    finally:
        await engine.dispose()


async def test_a_second_cancel_is_a_200_that_writes_no_second_audit_row(
    app_role_url: str,
) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=1)
        claim = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)
        owner = _owner(factory)
        staff = _staff(tenant_id)

        await owner.cancel(tenant_id, claim.booking.id, staff=staff)
        repeat = await owner.cancel(tenant_id, claim.booking.id, staff=staff)

        assert repeat.changed is False
        assert len(await _audit(factory, tenant_id)) == 1
    finally:
        await engine.dispose()


async def test_every_transition_writes_exactly_one_audit_row_and_a_refusal_writes_none(
    app_role_url: str,
) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=1)
        claim = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)
        staff = _staff(tenant_id)
        # The clock sits after the appointment, so no-show and complete are legal
        # and cancel is refused by the clock.
        owner = _owner(factory, now=SLOT_A + datetime.timedelta(hours=2))

        await owner.no_show(tenant_id, claim.booking.id, staff=staff)
        await owner.complete(tenant_id, claim.booking.id, staff=staff)
        await owner.confirm(tenant_id, claim.booking.id, staff=staff)
        with pytest.raises(BookingTransitionInvalidError):
            await owner.cancel(tenant_id, claim.booking.id, staff=staff)

        rows = await _audit(factory, tenant_id)
        assert [row.action for row in rows] == [
            AuditAction.BOOKING_NO_SHOW.value,
            AuditAction.BOOKING_COMPLETED.value,
            AuditAction.BOOKING_CONFIRMED.value,
        ]
        assert [row.details for row in rows] == [
            {"from": "confirmed", "to": "no_show"},
            {"from": "no_show", "to": "completed"},
            {"from": "completed", "to": "confirmed"},
        ]
        assert all(row.actor_id == staff.id for row in rows)
        assert all(row.entity == str(claim.booking.id) for row in rows)
    finally:
        await engine.dispose()


# --- phone correction and the rotation -------------------------------------


async def test_the_non_collision_branch_corrects_the_number_and_kills_the_old_link(
    app_role_url: str,
) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=1)
        claim = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)
        corrected = _phone()
        assert await _resolves(factory, tenant_id, claim.manage_token)

        result = await _owner(factory).correct_phone(
            tenant_id, claim.booking.id, phone=corrected, staff=_staff(tenant_id)
        )

        async with tenant_session(factory, tenant_id) as session:
            customer = await CustomersRepository().by_id(
                session, tenant_id, claim.booking.customer_id
            )
        assert customer is not None and customer.phone == corrected
        assert result.manage_token is not None
        assert not await _resolves(factory, tenant_id, claim.manage_token)
        assert await _resolves(factory, tenant_id, result.manage_token)
        pending = await _pending(factory, tenant_id, claim.booking.id)
        assert pending is not None and pending.manage_token == result.manage_token
    finally:
        await engine.dispose()


async def test_correcting_one_booking_revokes_every_sibling_link_on_that_number(
    app_role_url: str,
) -> None:
    """`customers` IS the phone identity, so the correction moves every booking
    that customer holds onto the new number at once — while `manage_token_hash`
    is per-row. Rotating only the edited booking would leave a working
    stranger-held cancel link on the sibling, which is exactly the harm this
    rotation exists to prevent."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=1)
        wrong_number = _phone()
        first = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A, phone=wrong_number)
        second = await _claim(factory, tenant_id, type_id, starts_at=SLOT_B, phone=wrong_number)
        assert first.booking.customer_id == second.booking.customer_id

        result = await _owner(factory).correct_phone(
            tenant_id, first.booking.id, phone=_phone(), staff=_staff(tenant_id)
        )

        # Both old links are dead; only the edited booking's new token came back.
        assert not await _resolves(factory, tenant_id, first.manage_token)
        assert not await _resolves(factory, tenant_id, second.manage_token)
        assert result.manage_token is not None
        assert await _resolves(factory, tenant_id, result.manage_token)

        sibling_pending = await _pending(factory, tenant_id, second.booking.id)
        assert sibling_pending is not None
        assert sibling_pending.manage_token not in (None, second.manage_token)
        assert await _resolves(factory, tenant_id, sibling_pending.manage_token)

        [audit] = await _audit(factory, tenant_id)
        assert audit.action == AuditAction.BOOKING_PHONE_CORRECTED.value
        assert set(audit.details["rotated_booking_ids"]) == {
            str(first.booking.id),
            str(second.booking.id),
        }
        assert audit.details["repointed"] is False
        assert audit.details["attested"] is True
    finally:
        await engine.dispose()


async def test_the_collision_branch_repoints_the_booking_and_leaves_the_siblings_alone(
    app_role_url: str,
) -> None:
    """The IDENTITY was wrong, not the digits: the booking moves to the customer
    who already holds that number, both customer rows survive, and only THIS
    booking rotates — the original customer's other live bookings are asserted
    unchanged, which is D8's stated ruling and not an accident."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=1)
        wrong_number = _phone()
        right_number = _phone()
        edited = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A, phone=wrong_number)
        sibling = await _claim(factory, tenant_id, type_id, starts_at=SLOT_B, phone=wrong_number)
        target = await _claim(factory, tenant_id, type_id, starts_at=SLOT_C, phone=right_number)

        result = await _owner(factory).correct_phone(
            tenant_id, edited.booking.id, phone=right_number, staff=_staff(tenant_id)
        )

        moved = await _row(factory, tenant_id, edited.booking.id)
        assert moved is not None
        assert moved.customer_id == target.booking.customer_id
        async with tenant_session(factory, tenant_id) as session:
            repo = CustomersRepository()
            original = await repo.by_id(session, tenant_id, edited.booking.customer_id)
            other = await repo.by_id(session, tenant_id, target.booking.customer_id)
        # Both rows intact, and the original keeps the wrong number deliberately:
        # it may be a real other person's, and soft-deleting on a guess is worse.
        assert original is not None and original.phone == wrong_number
        assert other is not None and other.phone == right_number

        assert result.manage_token is not None
        assert not await _resolves(factory, tenant_id, edited.manage_token)
        # Only THIS booking rotated: the sibling still holds its original link.
        assert await _resolves(factory, tenant_id, sibling.manage_token)
        assert await _resolves(factory, tenant_id, target.manage_token)

        [audit] = await _audit(factory, tenant_id)
        assert audit.details["repointed"] is True
        assert audit.details["rotated_booking_ids"] == [str(edited.booking.id)]
        assert audit.details["old_customer_id"] == str(edited.booking.customer_id)
        assert audit.details["new_customer_id"] == str(target.booking.customer_id)
    finally:
        await engine.dispose()


async def test_a_repoint_onto_a_customer_who_already_holds_the_instant_is_a_409_not_a_500(
    app_role_url: str,
) -> None:
    """Two sisters in one capacity-2 slot, the owner corrects the first one's
    number to the second's. The re-point would put two live rows on
    (tenant, customer B, that instant) and 0009's partial unique index refuses —
    which, with no error registry above it, would escape as a bare 500."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=2)
        sister_a = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)
        sister_b_phone = _phone()
        await _claim(factory, tenant_id, type_id, starts_at=SLOT_A, phone=sister_b_phone)

        with pytest.raises(CustomerAlreadyBookedError):
            await _owner(factory).correct_phone(
                tenant_id, sister_a.booking.id, phone=sister_b_phone, staff=_staff(tenant_id)
            )

        # Nothing was written: the link that went to the first number still works
        # and the audit trail records no correction that did not happen.
        assert await _resolves(factory, tenant_id, sister_a.manage_token)
        assert await _audit(factory, tenant_id) == []
    finally:
        await engine.dispose()


async def test_a_correction_that_fails_mid_rotation_leaves_the_phone_uncorrected(
    app_role_url: str,
) -> None:
    """Atomicity, stated as the invariant it protects: there must be no committed
    state in which the phone is corrected and the OLD hash survives — the
    stranger's link would still resolve and still cancel the bride's appointment
    at a route that has no phone check."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=1)
        wrong_number = _phone()
        first = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A, phone=wrong_number)
        second = await _claim(factory, tenant_id, type_id, starts_at=SLOT_B, phone=wrong_number)
        owner = _owner(factory)

        calls = {"n": 0}
        real = BookingsRepository.set_manage_token_hash

        async def flaky(self: Any, *args: Any, **kwargs: Any) -> Any:
            calls["n"] += 1
            # The first sibling rotates; the second blows up mid-transaction.
            if calls["n"] > 1:
                raise RuntimeError("injected failure after the phone write")
            return await real(self, *args, **kwargs)

        BookingsRepository.set_manage_token_hash = flaky  # type: ignore[method-assign]
        try:
            with pytest.raises(RuntimeError):
                await owner.correct_phone(
                    tenant_id, first.booking.id, phone=_phone(), staff=_staff(tenant_id)
                )
        finally:
            BookingsRepository.set_manage_token_hash = real  # type: ignore[method-assign]

        async with tenant_session(factory, tenant_id) as session:
            customer = await CustomersRepository().by_id(
                session, tenant_id, first.booking.customer_id
            )
        assert customer is not None and customer.phone == wrong_number
        # Both links survive together with the un-corrected number.
        assert await _resolves(factory, tenant_id, first.manage_token)
        assert await _resolves(factory, tenant_id, second.manage_token)
        assert await _audit(factory, tenant_id) == []
    finally:
        await engine.dispose()


async def test_resend_rotates_this_booking_and_repoints_its_reminder(app_role_url: str) -> None:
    """Resend is not a re-send: it invalidates the old link. A plain resend is
    impossible anyway once the reminder has fired — `bookings` stores only the
    sha256 — so rotation is the only behaviour available in every case."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=1)
        claim = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)
        staff = _staff(tenant_id)

        result = await _owner(factory).resend_link(tenant_id, claim.booking.id, staff=staff)

        assert result.manage_token is not None and result.manage_token != claim.manage_token
        assert not await _resolves(factory, tenant_id, claim.manage_token)
        assert await _resolves(factory, tenant_id, result.manage_token)
        pending = await _pending(factory, tenant_id, claim.booking.id)
        assert pending is not None and pending.manage_token == result.manage_token
        [audit] = await _audit(factory, tenant_id)
        assert audit.action == AuditAction.BOOKING_LINK_RESENT.value
        assert audit.details == {"customer_id": str(claim.booking.customer_id)}
    finally:
        await engine.dispose()


async def test_no_full_phone_number_reaches_the_audit_row(app_role_url: str) -> None:
    """`audit_log` is retained on the AUDIT clock, not the booking clock, so a
    full number in JSONB is a second uncontrolled copy of the one PII field this
    feature exists to edit."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=1)
        wrong_number = _phone()
        corrected = _phone()
        claim = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A, phone=wrong_number)

        await _owner(factory).correct_phone(
            tenant_id, claim.booking.id, phone=corrected, staff=_staff(tenant_id)
        )

        [audit] = await _audit(factory, tenant_id)
        rendered = str(audit.details)
        assert wrong_number not in rendered
        assert corrected not in rendered
        assert audit.details["old_phone_last4"] == wrong_number[-4:]
        assert audit.details["new_phone_last4"] == corrected[-4:]
    finally:
        await engine.dispose()


# --- the owner-SMS budget --------------------------------------------------


async def test_a_throttled_correction_leaves_the_phone_and_the_hash_untouched(
    app_role_url: str,
) -> None:
    """The limiter is consulted BEFORE the transaction opens, so a 429 writes
    nothing and sends nothing — not a partially-applied correction."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=1)
        wrong_number = _phone()
        claim = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A, phone=wrong_number)
        before = await _row(factory, tenant_id, claim.booking.id)
        assert before is not None

        with pytest.raises(OwnerResendThrottledError):
            await _owner(factory, sms_limiter=_spent()).correct_phone(
                tenant_id, claim.booking.id, phone=_phone(), staff=_staff(tenant_id)
            )

        async with tenant_session(factory, tenant_id) as session:
            customer = await CustomersRepository().by_id(
                session, tenant_id, claim.booking.customer_id
            )
        assert customer is not None and customer.phone == wrong_number
        after = await _row(factory, tenant_id, claim.booking.id)
        assert after is not None and after.manage_token_hash == before.manage_token_hash
        assert await _resolves(factory, tenant_id, claim.manage_token)
        assert await _audit(factory, tenant_id) == []
    finally:
        await engine.dispose()


@pytest.mark.parametrize("operation", ["resend_link", "reschedule"])
async def test_a_spent_budget_refuses_the_metered_operations(
    app_role_url: str, operation: str
) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=1)
        claim = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)
        owner = _owner(factory, sms_limiter=_spent())
        staff = _staff(tenant_id)

        with pytest.raises(OwnerResendThrottledError):
            if operation == "resend_link":
                await owner.resend_link(tenant_id, claim.booking.id, staff=staff)
            else:
                await owner.reschedule(
                    tenant_id, claim.booking.id, new_starts_at=SLOT_B, staff=staff
                )

        unchanged = await _row(factory, tenant_id, claim.booking.id)
        assert unchanged is not None and unchanged.starts_at == SLOT_A
        assert await _resolves(factory, tenant_id, claim.manage_token)
        assert await _audit(factory, tenant_id) == []
    finally:
        await engine.dispose()


async def test_owner_cancel_is_never_metered(app_role_url: str) -> None:
    """`cancelled` is terminal, so cancel is at most one SMS per booking and its
    ceiling is the number of bookings the boutique has. Reschedule is on the
    budget precisely because it is UNBOUNDED — a booking can be walked A↔B↔A
    between two offered slots forever, one SMS a hop."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=1)
        claim = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)

        result = await _owner(factory, sms_limiter=_spent()).cancel(
            tenant_id, claim.booking.id, staff=_staff(tenant_id)
        )
        assert result.booking.status == BookingStatus.CANCELLED.value
    finally:
        await engine.dispose()


async def test_a_committed_reschedule_spends_one_unit_of_the_budget(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=1)
        claim = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)
        # One attempt in the window: the first move lands, the second is refused.
        limiter = FixedWindowRateLimiter(max_attempts=1, window_seconds=3600, clock=lambda: 0.0)
        owner = _owner(factory, sms_limiter=limiter)
        staff = _staff(tenant_id)

        await owner.reschedule(tenant_id, claim.booking.id, new_starts_at=SLOT_B, staff=staff)
        with pytest.raises(OwnerResendThrottledError):
            await owner.reschedule(tenant_id, claim.booking.id, new_starts_at=SLOT_C, staff=staff)

        row = await _row(factory, tenant_id, claim.booking.id)
        assert row is not None and row.starts_at == SLOT_B
    finally:
        await engine.dispose()


# --- the day list ----------------------------------------------------------


async def test_the_day_list_returns_cancelled_rows_ordered_by_start_then_seat(
    app_role_url: str,
) -> None:
    """A cancelled row is the owner's evidence that the slot re-opened, so it is
    a constant in the query and never a `?status=` parameter (D17)."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=2)
        late = await _claim(factory, tenant_id, type_id, starts_at=SLOT_C)
        first_seat = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)
        second_seat = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)
        # A booking a week later — same weekday, so the same weekly rule opens
        # it — must NOT appear: the window is one Jerusalem calendar day.
        await _claim(
            factory,
            tenant_id,
            type_id,
            starts_at=_slot(10, 0, date=TARGET_DATE + datetime.timedelta(days=7)),
        )

        owner = _owner(factory)
        await owner.cancel(tenant_id, first_seat.booking.id, staff=_staff(tenant_id))

        rows, total = await owner.list_day(
            tenant_id, date=TARGET_DATE, offset=0, limit=BOOKING_LIST_DEFAULT_LIMIT
        )

        assert total == 3
        assert [(row.id, row.seat_index) for row in rows] == [
            (first_seat.booking.id, 1),
            (second_seat.booking.id, 2),
            (late.booking.id, 1),
        ]
        assert rows[0].status == BookingStatus.CANCELLED.value
    finally:
        await engine.dispose()


async def test_the_day_list_pages_without_losing_the_whole_day_total(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=1)
        for instant in (SLOT_A, SLOT_B, SLOT_C):
            await _claim(factory, tenant_id, type_id, starts_at=instant)

        rows, total = await _owner(factory).list_day(tenant_id, date=TARGET_DATE, offset=1, limit=1)
        assert total == 3
        assert [row.starts_at for row in rows] == [SLOT_B]
    finally:
        await engine.dispose()


async def test_the_day_list_resolves_its_customers_in_one_read(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=1)
        claim = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)
        owner = _owner(factory)

        rows, _ = await owner.list_day(
            tenant_id, date=TARGET_DATE, offset=0, limit=BOOKING_LIST_DEFAULT_LIMIT
        )
        customers = await owner.customers_for(tenant_id, [row.customer_id for row in rows])

        assert set(customers) == {claim.booking.customer_id}
        assert customers[claim.booking.customer_id].name == "נועה לוי"
    finally:
        await engine.dispose()


# --- RLS -------------------------------------------------------------------


async def test_a_foreign_tenants_owner_can_neither_read_nor_transition_the_booking(
    app_role_url: str,
) -> None:
    """404, indistinguishable from missing. RLS plus the redundant tenant
    predicate: an owner session is scoped to the boutique that issued it, and
    every console host resolves its own tenant."""
    engine, factory = _factory(app_role_url)
    mine, theirs = uuid.uuid4(), uuid.uuid4()
    try:
        type_id = await _seed(factory, mine, capacity=1)
        await _seed(factory, theirs, capacity=1)
        claim = await _claim(factory, mine, type_id, starts_at=SLOT_A)
        intruder = _owner(factory)
        staff = _staff(theirs)

        with pytest.raises(BookingNotFoundError):
            await intruder.detail(theirs, claim.booking.id)
        for verb in ("confirm", "cancel", "no_show", "complete", "resend_link"):
            with pytest.raises(BookingNotFoundError):
                await getattr(intruder, verb)(theirs, claim.booking.id, staff=staff)
        with pytest.raises(BookingNotFoundError):
            await intruder.reschedule(theirs, claim.booking.id, new_starts_at=SLOT_B, staff=staff)
        with pytest.raises(BookingNotFoundError):
            await intruder.correct_phone(theirs, claim.booking.id, phone=_phone(), staff=staff)

        # Nothing of A's moved, and B wrote no audit trail about it.
        row = await _row(factory, mine, claim.booking.id)
        assert row is not None and row.status == BookingStatus.CONFIRMED.value
        assert await _audit(factory, theirs) == []

        # And the day list is scoped too: B's day is empty on A's date.
        rows, total = await intruder.list_day(
            theirs, date=TARGET_DATE, offset=0, limit=BOOKING_LIST_DEFAULT_LIMIT
        )
        assert (rows, total) == ([], 0)
    finally:
        await engine.dispose()
