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
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import delete, select, text, update
from sqlalchemy.exc import IntegrityError
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
    BookingAwaitingPaymentError,
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
from app.db.repositories.bookings import BookingsRepository, CheckInOutcome
from app.db.repositories.customers import CustomersRepository
from app.db.repositories.otp_codes import OtpCodesRepository
from app.db.repositories.payments import PaymentsRepository
from app.db.repositories.scheduled_messages import ScheduledMessagesRepository
from app.db.repositories.terms import TermsVersionsRepository
from app.db.tenant import tenant_session
from app.models.audit_log import AuditLog
from app.models.booking import Booking
from app.models.constants import (
    AppointmentAudience,
    AuditAction,
    BookingCancelledBy,
    BookingSource,
    BookingStatus,
    PaymentStatus,
    ScheduledMessageKind,
    StaffRole,
)
from app.models.customer import Customer
from app.models.payment import Payment
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
    marketing_consent: bool = False,
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
        marketing_consent=marketing_consent,
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


async def test_a_customer_cancel_landing_first_is_a_409_and_writes_no_owner_audit_row(
    app_role_url: str,
) -> None:
    """The race the owner-cancel guard exists for, and it needs real Postgres:
    no fake can produce the ORM state that made the old guard blind.

    The bride cancels on her manage link and commits between the owner's read
    and the owner's guarded UPDATE. That UPDATE now matches zero rows — but the
    row's status IS 'cancelled', which is the owner's target, and SQLAlchemy's
    `evaluate` synchronization has already stamped `cancelled_by = 'owner'` onto
    the in-memory instance. Reading the re-fetched row therefore cannot answer
    "did I do this?", and the only honest signal is `cancel`'s own `.returning()`
    scalar.

    What must not happen: an `audit_log` row asserting a staff member cancelled
    an appointment the customer cancelled herself, plus `changed=True` sending
    her «בוטל על ידי הבוטיק» minutes after she cancelled it.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=1)
        claim = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)
        owner = _owner(factory)
        staff = _staff(tenant_id)
        manage = _manage(factory)

        async def by_owner() -> Any:
            return await owner.cancel(tenant_id, claim.booking.id, staff=staff)

        async def by_customer() -> Any:
            return await manage.cancel(_manage_tenant(tenant_id), token=claim.manage_token)

        await asyncio.gather(by_owner(), by_customer(), return_exceptions=True)

        row = await _row(factory, tenant_id, claim.booking.id)
        assert row is not None
        assert row.status == BookingStatus.CANCELLED.value

        # The only claim that matters, and it holds whichever writer won:
        # `cancelled_by` is the truth, and an owner audit row may exist only if
        # the owner is who the row names. The customer path writes no audit row
        # at all, so a stray one here is not a duplicate — it is the SOLE trail
        # entry for that cancellation, naming the wrong actor.
        cancels = [
            entry
            for entry in await _audit(factory, tenant_id)
            if entry.action == AuditAction.BOOKING_CANCELLED.value
        ]
        if row.cancelled_by == BookingCancelledBy.CUSTOMER.value:
            assert cancels == [], f"an owner audit row for a customer cancel: {cancels!r}"
        else:
            assert len(cancels) == 1
            assert cancels[0].actor_id == staff.id
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


# --- F34: check-in, and the forced interleave the zero-row branch needs -------
#
# `asyncio.gather` is deliberately NOT used for the two headline tests, and the
# reason is above in this very file: the customer-cancel race uses it and then
# asserts outcome-agnostically ("the only claim that matters, and it holds
# whichever writer won") precisely because gather does not ORDER two
# transactions. For F34 that is worse than imprecise. Under gather the loser
# most often loads AFTER the winner commits, takes the service's Python
# pre-check and never reaches the guarded UPDATE at all — so the zero-row branch
# these tests exist to prove would be green without ever executing.
#
# They therefore drive the REPOSITORY directly. At the service layer the
# interleave is unreachable by construction: `check_in`'s step 2
# (`checked_in_at is not None`) and step 3 (`status != 'confirmed'`) both
# short-circuit in Python before the write. A service-level "forced interleave"
# would assert the Python pre-check, which is the same silent vacuity. The
# service's mapping of the three outcomes onto 200/409/404 is proven against
# fakes in test_booking_owner_service.py, where it is a pure branch.
#
# The mechanism: `tenant_session` is `async with session_factory() as session,
# session.begin()`, so EXITING the context manager is the commit, and two nested
# tenant_sessions on one factory take two separate pool connections (NullPool).
# Under READ COMMITTED each statement sees data committed as of statement start,
# which is what lets the loser's UPDATE see the winner's write.

FIRST_ARRIVAL = datetime.datetime(2026, 7, 28, 11, 50, tzinfo=datetime.UTC)
LOSER_ARRIVAL = datetime.datetime(2026, 7, 28, 13, 40, tzinfo=datetime.UTC)


async def test_a_cancel_landing_between_the_read_and_the_write_is_not_confirmed(
    app_role_url: str,
) -> None:
    """Zero rows, cause one: somebody cancelled her in the gap. 409.

    The second assertion is the one that carries the feature. `refreshed` must
    read `checked_in_at IS NULL`, and it FAILS if the discrimination is taken off
    the in-memory instance — because `update(Booking)` is ORM-enabled DML whose
    `evaluate` synchronization has already stamped LOSER_ARRIVAL onto that
    object, whatever the database matched. Without `populate_existing=True` on
    the re-read, this row comes back claiming an arrival that was never written,
    on a booking that is cancelled.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    repo = BookingsRepository()
    try:
        type_id = await _seed(factory, tenant_id, capacity=1)
        claim = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)
        booking_id = claim.booking.id

        # The LOSER's session, held open across the winner's whole transaction.
        async with tenant_session(factory, tenant_id) as loser:
            loaded = await repo.by_id(loser, tenant_id, booking_id)
            assert loaded is not None
            # The service's Python pre-check WOULD pass at this point, which is
            # exactly what makes the guarded UPDATE the only thing standing.
            assert loaded.checked_in_at is None
            assert loaded.status == BookingStatus.CONFIRMED.value

            # The WINNER commits in a SECOND session while the loser holds its
            # read. Exiting this block is the commit.
            async with tenant_session(factory, tenant_id) as winner:
                await repo.cancel(
                    winner,
                    tenant_id,
                    booking_id,
                    at=NOW,
                    by=BookingCancelledBy.CUSTOMER.value,
                )

            # Only now does the loser's guarded UPDATE run. It matches ZERO rows.
            outcome, refreshed = await repo.check_in(loser, tenant_id, booking_id, at=LOSER_ARRIVAL)

        assert outcome is CheckInOutcome.NOT_CONFIRMED
        assert refreshed is not None
        assert refreshed.checked_in_at is None
        assert refreshed.status == BookingStatus.CANCELLED.value

        # …and nothing was written, read back on a fresh connection.
        row = await _row(factory, tenant_id, booking_id)
        assert row is not None
        assert row.checked_in_at is None
    finally:
        await engine.dispose()


async def test_a_check_in_landing_in_the_gap_keeps_the_first_writers_timestamp(
    app_role_url: str,
) -> None:
    """Zero rows, cause two: she is already checked in. 200 unchanged.

    The same forced interleave, the OTHER cause — and this is the half that
    makes the pair meaningful. Either test alone can be passed by a coin flip;
    together they prove the discrimination is real, because one demands
    NOT_CONFIRMED and the other ALREADY_CHECKED_IN off the identical zero-row
    UPDATE.

    `refreshed.checked_in_at == FIRST_ARRIVAL` is the render guarantee: the
    losing writer must show the FIRST staffer's time. Off the poisoned instance
    it would show LOSER_ARRIVAL — contradicting the exact promise this case
    exists to make.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    repo = BookingsRepository()
    try:
        type_id = await _seed(factory, tenant_id, capacity=1)
        claim = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)
        booking_id = claim.booking.id

        async with tenant_session(factory, tenant_id) as loser:
            loaded = await repo.by_id(loser, tenant_id, booking_id)
            assert loaded is not None
            assert loaded.checked_in_at is None

            async with tenant_session(factory, tenant_id) as winner:
                won, _ = await repo.check_in(winner, tenant_id, booking_id, at=FIRST_ARRIVAL)
                assert won is CheckInOutcome.WROTE

            outcome, refreshed = await repo.check_in(loser, tenant_id, booking_id, at=LOSER_ARRIVAL)

        assert outcome is CheckInOutcome.ALREADY_CHECKED_IN
        assert refreshed is not None
        assert refreshed.checked_in_at == FIRST_ARRIVAL
        assert refreshed.checked_in_at != LOSER_ARRIVAL

        row = await _row(factory, tenant_id, booking_id)
        assert row is not None
        assert row.checked_in_at == FIRST_ARRIVAL
    finally:
        await engine.dispose()


async def test_two_sequential_taps_both_answer_200_and_the_first_timestamp_survives(
    app_role_url: str,
) -> None:
    """The uncontended shape of the same guarantee, at the SERVICE layer, with
    two injected clocks — `test_booking_comms_db.py`'s two-clock idempotency
    pattern.

    Two staffers on two phones, two hours apart. Both get a success, the arrival
    time does not move, and exactly ONE audit row exists: the second tap changed
    nothing, so `{from: checked_in, to: checked_in}` noise in the one trail this
    area has would be worse than silence.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    later = NOW + datetime.timedelta(hours=2)
    try:
        type_id = await _seed(factory, tenant_id, capacity=1)
        claim = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)
        staff = _staff(tenant_id)

        first_tap = await _owner(factory, now=NOW).check_in(
            tenant_id, claim.booking.id, staff=staff
        )
        later_tap = await _owner(factory, now=later).check_in(
            tenant_id, claim.booking.id, staff=staff
        )

        assert first_tap.changed is True
        assert later_tap.changed is False
        assert first_tap.booking.checked_in_at == NOW
        assert later_tap.booking.checked_in_at == NOW

        row = await _row(factory, tenant_id, claim.booking.id)
        assert row is not None
        assert row.checked_in_at == NOW

        check_ins = [
            entry
            for entry in await _audit(factory, tenant_id)
            if entry.action == AuditAction.BOOKING_CHECKED_IN.value
        ]
        assert len(check_ins) == 1
        assert check_ins[0].actor_id == staff.id
        assert check_ins[0].entity == str(claim.booking.id)
        assert check_ins[0].details == {"checked_in_at": NOW.isoformat()}
    finally:
        await engine.dispose()


async def test_check_in_on_a_cancelled_booking_is_a_409_and_writes_no_audit_row(
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

        with pytest.raises(BookingTransitionInvalidError):
            await owner.check_in(tenant_id, claim.booking.id, staff=staff)

        row = await _row(factory, tenant_id, claim.booking.id)
        assert row is not None
        assert row.checked_in_at is None
        assert not [
            entry
            for entry in await _audit(factory, tenant_id)
            if entry.action == AuditAction.BOOKING_CHECKED_IN.value
        ]
    finally:
        await engine.dispose()


@pytest.mark.parametrize("verb", ["no_show", "complete"])
async def test_a_status_transition_never_clears_the_arrival_timestamp(
    app_role_url: str, verb: str
) -> None:
    """Spec D5's declined auto-clear, asserted as a DECISION rather than left as
    an oversight.

    Marking a checked-in bride `no_show` looks contradictory, and the temptation
    is to clear the timestamp inside `set_status`. Declined: it would make F15's
    one status writer do two things, destroy the only record of an arrival as a
    side effect of an unrelated verb, and presume the owner meant the arrival was
    wrong when she may have meant the bride left. The explicit undo is the
    remedy."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    # The attendance verbs are guarded on a PAST starts_at, so the clock has to
    # sit after the slot rather than before it.
    after = SLOT_A + datetime.timedelta(hours=1)
    try:
        type_id = await _seed(factory, tenant_id, capacity=1)
        claim = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)
        staff = _staff(tenant_id)

        await _owner(factory, now=NOW).check_in(tenant_id, claim.booking.id, staff=staff)
        await getattr(_owner(factory, now=after), verb)(tenant_id, claim.booking.id, staff=staff)

        row = await _row(factory, tenant_id, claim.booking.id)
        assert row is not None
        assert row.checked_in_at == NOW
        assert row.status == (
            BookingStatus.NO_SHOW.value if verb == "no_show" else BookingStatus.COMPLETED.value
        )
    finally:
        await engine.dispose()


async def test_the_undo_clears_a_cancelled_bookings_arrival_and_records_what_it_destroyed(
    app_role_url: str,
) -> None:
    """D5's no-status-guard ruling end to end, and the `previous_checked_in_at`
    payload that is the only surviving copy of the value: `bookings` has no
    history table, so once the column is cleared this audit row is the record."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=1)
        claim = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)
        owner = _owner(factory)
        staff = _staff(tenant_id)

        await owner.check_in(tenant_id, claim.booking.id, staff=staff)
        await owner.cancel(tenant_id, claim.booking.id, staff=staff)

        undone = await owner.undo_check_in(tenant_id, claim.booking.id, staff=staff)
        assert undone.changed is True
        assert undone.booking.checked_in_at is None

        row = await _row(factory, tenant_id, claim.booking.id)
        assert row is not None
        assert row.checked_in_at is None
        # The cancellation is untouched — the undo clears the arrival and only
        # the arrival.
        assert row.status == BookingStatus.CANCELLED.value

        undos = [
            entry
            for entry in await _audit(factory, tenant_id)
            if entry.action == AuditAction.BOOKING_CHECK_IN_UNDONE.value
        ]
        assert len(undos) == 1
        assert undos[0].actor_id == staff.id
        assert undos[0].entity == str(claim.booking.id)
        assert undos[0].details == {"previous_checked_in_at": NOW.isoformat()}

        # A repeat undo is a 200 that writes nothing further.
        repeat = await owner.undo_check_in(tenant_id, claim.booking.id, staff=staff)
        assert repeat.changed is False
        assert (
            len(
                [
                    entry
                    for entry in await _audit(factory, tenant_id)
                    if entry.action == AuditAction.BOOKING_CHECK_IN_UNDONE.value
                ]
            )
            == 1
        )
    finally:
        await engine.dispose()


async def test_the_day_list_carries_the_arrival_timestamp(app_role_url: str) -> None:
    """The board only ever reads the list, so `checked_in_at` has to survive
    `list_day` — the one read this feature adds no query for."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=1)
        claim = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)
        owner = _owner(factory)
        await owner.check_in(tenant_id, claim.booking.id, staff=_staff(tenant_id))

        rows, total = await owner.list_day(
            tenant_id, date=TARGET_DATE, offset=0, limit=BOOKING_LIST_DEFAULT_LIMIT
        )
        assert total == 1
        assert rows[0].checked_in_at == NOW
    finally:
        await engine.dispose()


# --- F19: the owner's payment marker, MD1's button, and the bride's page ----
#
# **Cleanup is not optional below.** `bookings.status = 'pending_payment'` and
# `cancelled_by = 'expired'` are the two values migration 0015's downgrade
# narrows out of their CHECKs, and Postgres refuses that while any row still
# holds one — a leak here reds seven unrelated migration round-trip tests. Every
# test that writes either value deletes its bookings in a `finally`.
# `payments` rows are left: 0012 REVOKEs DELETE on that table from app_user.


async def _pay(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    booking_id: uuid.UUID,
    *,
    status: str = PaymentStatus.PAID.value,
    amount_agorot: int = 50_000,
) -> uuid.UUID:
    async with tenant_session(factory, tenant_id) as session:
        row = await PaymentsRepository().insert(
            session,
            tenant_id=tenant_id,
            booking_id=booking_id,
            provider="fake",
            amount_agorot=amount_agorot,
            provider_session_id=f"sess-{uuid.uuid4().hex[:12]}",
            redirect_url="https://pay.example.test/checkout/abc",
            hold_expires_at=NOW + datetime.timedelta(minutes=15),
        )
        payment_id = row.id
        if status != PaymentStatus.PENDING.value:
            await session.execute(
                update(Payment)
                .where(Payment.id == payment_id)
                .values(status=status)
                .execution_options(synchronize_session=False)
            )
    return payment_id


async def _release(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    booking_id: uuid.UUID,
    *,
    by: str,
) -> None:
    """What the sweeper does to an abandoned hold, minus the sweeper: the seat
    is freed and the cancellation is attributed. Driving the real sweeper is
    `test_deposit_sweeper_db.py`'s job — this file needs the resulting ROW."""
    async with tenant_session(factory, tenant_id) as session:
        await BookingsRepository().cancel(session, tenant_id, booking_id, at=NOW, by=by)


async def _set_status(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    booking_id: uuid.UUID,
    *,
    status: str,
) -> None:
    async with tenant_session(factory, tenant_id) as session:
        await session.execute(
            update(Booking)
            .where(Booking.id == booking_id)
            .values(status=status)
            .execution_options(synchronize_session=False)
        )


async def _purge(
    engine: AsyncEngine, factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID
) -> None:
    try:
        async with tenant_session(factory, tenant_id) as session:
            await session.execute(delete(Booking).where(Booking.tenant_id == tenant_id))
    finally:
        await engine.dispose()


async def test_the_day_list_carries_the_payment_marker_and_the_refund_number(
    app_role_url: str,
) -> None:
    """D18 and A1 together, on the list the owner already loads every morning.

    The number is COMPUTED from the terms version she ACCEPTED (48h / 50% here)
    against `starts_at` — F19 writes no `refund_due` row anywhere, because the
    port ships no `refund()`. This cancel is far outside the window's cutoff, so
    the whole deposit is due back.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=2)
        paid = (await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)).booking
        plain = (await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)).booking
        await _pay(factory, tenant_id, paid.id)

        owner = _owner(factory)
        rows, _ = await owner.list_day(
            tenant_id, date=TARGET_DATE, offset=0, limit=BOOKING_LIST_DEFAULT_LIMIT
        )
        markers = await owner.payments_for(tenant_id, rows)

        assert markers[paid.id].status == PaymentStatus.PAID.value
        assert markers[paid.id].refund_due_agorot == 50_000
        # A booking with no payment row is simply absent — which is every
        # booking a deposits-off boutique takes.
        assert plain.id not in markers
    finally:
        await engine.dispose()


async def test_the_marker_names_no_refund_for_money_that_never_moved(
    app_role_url: str,
) -> None:
    """MD4's `failed` row is a booking that deliberately took NO deposit, so
    "refund due" is not a smaller number on it — it is no number at all."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=1)
        booking = (await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)).booking
        await _pay(factory, tenant_id, booking.id, status=PaymentStatus.FAILED.value)

        markers = await _owner(factory).payments_for(tenant_id, [booking])

        assert markers[booking.id].status == PaymentStatus.FAILED.value
        assert markers[booking.id].refund_due_agorot is None
    finally:
        await engine.dispose()


async def test_md1_a_cancelled_booking_that_still_holds_her_deposit_moves(
    app_role_url: str,
) -> None:
    """MD1, and the assertion that fails if the widened writer forgets to clear
    the evidence: the resulting row is `confirmed` with `cancelled_at` AND
    `cancelled_by` BOTH NULL.

    A row reading `confirmed` while carrying cancel evidence is the exact defect
    D2 declines `set_status` over, and both columns feed F52's attribution and
    F20's compliance read.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=1)
        claim = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)
        booking_id = claim.booking.id
        await _pay(factory, tenant_id, booking_id)
        # Her money landed after the sweeper had already released the seat.
        await _release(factory, tenant_id, booking_id, by=BookingCancelledBy.EXPIRED.value)

        moved = (
            await _owner(factory).reschedule(
                tenant_id, booking_id, new_starts_at=SLOT_B, staff=_staff(tenant_id)
            )
        ).booking

        assert moved.status == BookingStatus.CONFIRMED.value
        assert (moved.cancelled_at, moved.cancelled_by) == (None, None)
        assert moved.starts_at == SLOT_B
        stored = await _row(factory, tenant_id, booking_id)
        assert stored is not None
        assert (stored.status, stored.cancelled_at, stored.cancelled_by) == (
            BookingStatus.CONFIRMED.value,
            None,
            None,
        )
        # The seat is really hers again: 0008's index excludes only `cancelled`.
        async with tenant_session(factory, tenant_id) as session:
            assert await BookingsRepository().active_seats_at(
                session, tenant_id, starts_at=SLOT_B
            ) == {1}
        # The one surviving trace that the row was ever cancelled.
        moves = [
            entry
            for entry in await _audit(factory, tenant_id)
            if entry.action == AuditAction.BOOKING_RESCHEDULED.value
        ]
        assert moves[0].details["restored_from"] == BookingStatus.CANCELLED.value
    finally:
        await _purge(engine, factory, tenant_id)


async def test_md1_her_own_time_is_a_real_move_for_a_cancelled_row(
    app_role_url: str,
) -> None:
    """The common case: nobody took her slot after all. A cancelled row holds
    NOTHING — both partial unique indexes exclude it — so rescheduling onto the
    instant it already names must NOT hit the no-op short-circuit."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=1)
        claim = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)
        booking_id = claim.booking.id
        await _pay(factory, tenant_id, booking_id)
        await _release(factory, tenant_id, booking_id, by=BookingCancelledBy.EXPIRED.value)

        result = await _owner(factory).reschedule(
            tenant_id, booking_id, new_starts_at=SLOT_A, staff=_staff(tenant_id)
        )

        assert result.changed is True
        assert result.booking.starts_at == SLOT_A
        assert (result.booking.status, result.booking.cancelled_by) == (
            BookingStatus.CONFIRMED.value,
            None,
        )
    finally:
        await _purge(engine, factory, tenant_id)


async def test_md1_a_cancelled_booking_with_no_deposit_is_still_terminal(
    app_role_url: str,
) -> None:
    """MD1 widened the guard for ONE case. Undoing an ordinary customer cancel
    is not a scheduling operation, and the seat has been publicly bookable ever
    since."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=1)
        claim = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)
        await _release(factory, tenant_id, claim.booking.id, by=BookingCancelledBy.CUSTOMER.value)

        with pytest.raises(BookingTransitionInvalidError):
            await _owner(factory).reschedule(
                tenant_id, claim.booking.id, new_starts_at=SLOT_B, staff=_staff(tenant_id)
            )
        stored = await _row(factory, tenant_id, claim.booking.id)
        assert stored is not None and stored.status == BookingStatus.CANCELLED.value
    finally:
        await engine.dispose()


async def test_md1_an_unpaid_hold_is_never_rescheduled(app_role_url: str) -> None:
    """`pending_payment` is refused with everything else: the money is not in,
    the sweeper owns that row, and the owner's remedy for a stuck hold is to
    wait one tick."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=1)
        claim = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)
        booking_id = claim.booking.id
        await _set_status(
            factory, tenant_id, booking_id, status=BookingStatus.PENDING_PAYMENT.value
        )
        await _pay(factory, tenant_id, booking_id, status=PaymentStatus.PENDING.value)

        with pytest.raises(BookingTransitionInvalidError):
            await _owner(factory).reschedule(
                tenant_id, booking_id, new_starts_at=SLOT_B, staff=_staff(tenant_id)
            )
        assert await _audit(factory, tenant_id) == []
    finally:
        await _purge(engine, factory, tenant_id)


async def test_md1_a_restore_that_collides_is_a_409_and_never_a_500(
    app_role_url: str,
) -> None:
    """Race row #15: she rebooked the same instant herself before the late
    payment landed. Restoring the cancelled row re-enters 0009's per-customer
    partial unique index, and `main.py` registers NO `IntegrityError` handler —
    so an uncaught flush here is a 500 on the one path this feature exists for.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=2)
        phone = _phone()
        stranded = (
            await _claim(factory, tenant_id, type_id, starts_at=SLOT_A, phone=phone)
        ).booking
        await _pay(factory, tenant_id, stranded.id)
        await _release(factory, tenant_id, stranded.id, by=BookingCancelledBy.EXPIRED.value)
        # She rebooked the very same instant herself, so 0009's index is taken.
        live = (await _claim(factory, tenant_id, type_id, starts_at=SLOT_A, phone=phone)).booking
        assert live.id != stranded.id

        with pytest.raises(SlotUnavailableError):
            await _owner(factory).reschedule(
                tenant_id, stranded.id, new_starts_at=SLOT_B, staff=_staff(tenant_id)
            )
        # Nothing committed: the stranded row is still cancelled, her live one
        # still stands, and the deposit question is F29's, not this button's.
        stored = await _row(factory, tenant_id, stranded.id)
        assert stored is not None and stored.status == BookingStatus.CANCELLED.value
        assert await _audit(factory, tenant_id) == []
    finally:
        await _purge(engine, factory, tenant_id)


# --- A2 / A3: the bride's own tokenized page -------------------------------


async def test_an_unpaid_hold_still_answers_her_page_and_refuses_both_verbs(
    app_role_url: str,
) -> None:
    """A2. `by_manage_token_hash` carries no status predicate on purpose — an
    honest "awaiting payment" beats a dead link for someone re-opening her SMS —
    so the LOOKUP answers and only the two ACTIONS refuse. Shipped, the page
    rendered an unpaid hold as an appointment that stands, with a live cancel
    button, and both verbs would have ACTED on it.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=1)
        claim = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)
        token = claim.manage_token
        assert token is not None
        await _set_status(
            factory, tenant_id, claim.booking.id, status=BookingStatus.PENDING_PAYMENT.value
        )
        manage = _manage(factory)

        answered = await manage.lookup(_manage_tenant(tenant_id), token=token)
        assert answered.booking.status == BookingStatus.PENDING_PAYMENT.value

        with pytest.raises(BookingAwaitingPaymentError):
            await manage.confirm_attendance(_manage_tenant(tenant_id), token=token)
        with pytest.raises(BookingAwaitingPaymentError):
            await manage.cancel(_manage_tenant(tenant_id), token=token)

        # Neither verb wrote: the sweeper owns this row's next transition and
        # attributes it 'expired', not 'customer'.
        stored = await _row(factory, tenant_id, claim.booking.id)
        assert stored is not None
        assert stored.status == BookingStatus.PENDING_PAYMENT.value
        assert (stored.attendance_confirmed_at, stored.cancelled_at) == (None, None)
    finally:
        await _purge(engine, factory, tenant_id)


async def test_her_page_says_a_deposit_was_taken_only_when_one_actually_was(
    app_role_url: str,
) -> None:
    """A3, and MD3 cannot ship without it: `cancelConsequenceDeposit` renders on
    ANY booking that took a deposit — including a `confirmed` one paid weeks ago
    — so `status` alone cannot answer it, and the shipped "cancelling is free"
    sentence survives only where this is False."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=2)
        free = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)
        paid = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)
        assert free.manage_token is not None and paid.manage_token is not None
        await _pay(factory, tenant_id, paid.booking.id)
        manage = _manage(factory)

        assert (
            await manage.lookup(_manage_tenant(tenant_id), token=paid.manage_token)
        ).booking.deposit_taken is True
        assert (
            await manage.lookup(_manage_tenant(tenant_id), token=free.manage_token)
        ).booking.deposit_taken is False
    finally:
        await engine.dispose()


async def test_a_hold_that_was_never_honoured_is_not_a_deposit_taken(
    app_role_url: str,
) -> None:
    """A swept `expired` hold means no money moved, which is exactly when
    "cancelling is free" is still a TRUE sentence — the one case where reading
    `deposit_taken` off the existence of a payments row would be wrong."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=1)
        claim = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)
        assert claim.manage_token is not None
        await _pay(factory, tenant_id, claim.booking.id, status=PaymentStatus.EXPIRED.value)

        answered = await _manage(factory).lookup(
            _manage_tenant(tenant_id), token=claim.manage_token
        )

        assert answered.booking.deposit_taken is False
    finally:
        await engine.dispose()


# --- F50: the owner-created walk-in ---------------------------------------


@pytest.fixture(scope="module", autouse=True)
def _sweep_walk_in_bookings(migrated_db: str) -> Iterator[None]:
    """Remove every walk-in row this module committed, once, after it finishes.

    ⚠ NOT tidiness. `migrated_db` is `scope="session"`, so ONE database is shared
    by every db-marked module — and 0025's downgrade re-imposes two NOT NULLs
    DELIBERATELY WITHOUT a pre-clean, so a single surviving walk-in row makes
    `command.downgrade` past 0025 raise `NotNullViolationError`. That reds all
    EIGHTEEN round-trip tests in this suite, in modules that never heard of F50,
    with an error naming a column their own feature does not own.

    This is verbatim the trap F57 already documented one table over:
    "a committed 'reception' row reddens THREE tests … which is why the
    floor-role half below is rolled back rather than committed"
    (test_migrations.py). Same shape, same fix — the refusal is a real property of
    the migration, so the answer is to leave no row for it to refuse over rather
    than to soften the migration.

    Superuser rather than the app role: RLS is FORCED on `bookings` and these rows
    belong to a dozen throwaway tenant ids, so a tenant-scoped DELETE would
    silently remove none of them.

    Module-scoped, so it costs one statement rather than one per test. pytest runs
    a module's tests contiguously and this suite runs single-process, so nothing
    downgrades in the gap.

    ⚠ **What this fixture depends on, stated rather than left to be discovered.**
    Module scope means the sweep runs when THIS module finishes, so it protects
    only the modules that run AFTER it. That holds today because all five modules
    calling `command.downgrade` (`test_booking_owner_db`, `test_booking_repositories`,
    `test_catalog_integration`, `test_migrations`, `test_notifications_repositories`)
    either are this one or sort after `test_privacy_subject_requests_db.py`, which
    is the only other module that commits a walk-in and imports this fixture for it.
    A NEW db module that commits a walk-in must import this fixture the same way.
    It is NOT promoted to `conftest.py`: an autouse fixture there would request
    `migrated_db` for EVERY module, which starts Postgres under
    `pytest -m "not db"` and turns the fast suite into a slow one that cannot run
    without a database. Session scope is worse still — the sweep would then run
    after the very downgrade tests it exists to protect.
    """
    yield

    async def sweep() -> None:
        engine = create_async_engine(migrated_db)
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text("DELETE FROM bookings WHERE source = :source"),
                    {"source": BookingSource.WALK_IN.value},
                )
        finally:
            await engine.dispose()

    asyncio.run(sweep())


async def _customer_for(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, type_id: uuid.UUID
) -> uuid.UUID:
    """A `customers` row that exists the ONLY way one ever exists — through
    `create_booking`, after an OTP proved possession of the number.

    F50 creates none, deliberately: a `customers` row is proof of phone
    possession, and that proof is precisely what lets a booking with no terms
    evidence be legal at all. So every walk-in test has to reach one the real way,
    and the seeded storefront booking is a by-product rather than the point.
    """
    claim = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)
    return uuid.UUID(str(claim.booking.customer_id))


async def _bookings_of(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID
) -> list[Booking]:
    async with tenant_session(factory, tenant_id) as session:
        stmt = select(Booking).order_by(Booking.created_at)
        return list((await session.execute(stmt)).scalars().all())


async def test_the_walk_in_writer_stamps_one_instant_across_starts_at_and_checked_in_at(
    app_role_url: str,
) -> None:
    """`starts_at` and `checked_in_at` are the SAME instant, to the microsecond,
    because the writer takes one `at` rather than reading a clock twice — a writer
    that read it twice could produce a row that was checked in before it started.

    `created_at` is deliberately NOT compared. It is a `now()` SERVER default
    (`models/base.py`), i.e. transaction-start time, and under the injected test
    clock the two are years apart — comparing them would red this test for a
    reason that has nothing to do with the invariant."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    at = NOW + datetime.timedelta(microseconds=7)
    try:
        type_id = await _seed(factory, tenant_id)
        customer_id = await _customer_for(factory, tenant_id, type_id)

        async with tenant_session(factory, tenant_id) as session:
            row = await BookingsRepository().insert_walk_in(
                session,
                tenant_id=tenant_id,
                customer_id=customer_id,
                appointment_type_id=type_id,
                appointment_type_name="מדידה ראשונה",
                at=at,
            )
            booking_id = row.id

        stored = await _row(factory, tenant_id, booking_id)
        assert stored is not None
        assert stored.starts_at == at
        assert stored.checked_in_at == at
    finally:
        await engine.dispose()


async def test_the_walk_in_writer_records_no_terms_evidence_and_no_control_link(
    app_role_url: str,
) -> None:
    """Every absence on the row, asserted together because together is what makes
    the row legal: `source = 'walk_in'` is the only value under which 0025's
    `bookings_terms_evidence_check` admits NULL terms at all, so dropping the
    source kwarg fails this TWICE over — the assertion below and the constraint
    itself.

    `manage_token_hash` NULL is D2's whole point, and `notes` NULL is D3(c)'s: the
    request body is two UUIDs and carries no free text about a person."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id)
        customer_id = await _customer_for(factory, tenant_id, type_id)

        async with tenant_session(factory, tenant_id) as session:
            row = await BookingsRepository().insert_walk_in(
                session,
                tenant_id=tenant_id,
                customer_id=customer_id,
                appointment_type_id=type_id,
                appointment_type_name="מדידה ראשונה",
                at=NOW,
            )
            booking_id = row.id

        stored = await _row(factory, tenant_id, booking_id)
        assert stored is not None
        assert stored.source == BookingSource.WALK_IN.value
        assert stored.terms_version_accepted is None
        assert stored.terms_accepted_at is None
        assert stored.manage_token_hash is None
        assert stored.notes is None
        assert stored.dress_id is None
        assert stored.seat_index == 1
        assert stored.status == BookingStatus.CONFIRMED.value
    finally:
        await engine.dispose()


async def test_two_walk_ins_at_a_forced_identical_instant_collide_on_the_slot_index(
    app_role_url: str,
) -> None:
    """⚠ THE INSTANT IS FORCED, and that is what arms this test.

    `insert_walk_in` stamps a microsecond-precise `starts_at`, so two NATURAL
    calls never share one and neither partial unique index binds. A test that
    built its collision "naturally" would be green forever and prove nothing —
    this project has shipped that failure mode three times.

    Two DIFFERENT customers, so the collision is attributable to
    `idx_bookings_slot_seat_unique` (tenant, starts_at, seat_index) and not to the
    0009 customer index the sibling test below covers."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=2)
        first_customer = await _customer_for(factory, tenant_id, type_id)
        second_customer = (
            await _claim(factory, tenant_id, type_id, starts_at=SLOT_B)
        ).booking.customer_id

        async with tenant_session(factory, tenant_id) as session:
            await BookingsRepository().insert_walk_in(
                session,
                tenant_id=tenant_id,
                customer_id=first_customer,
                appointment_type_id=type_id,
                appointment_type_name="מדידה ראשונה",
                at=NOW,
            )

        with pytest.raises(IntegrityError):
            async with tenant_session(factory, tenant_id) as session:
                await BookingsRepository().insert_walk_in(
                    session,
                    tenant_id=tenant_id,
                    customer_id=second_customer,
                    appointment_type_id=type_id,
                    appointment_type_name="מדידה ראשונה",
                    at=NOW,
                )
    finally:
        await engine.dispose()


async def test_two_walk_ins_for_one_customer_at_a_forced_identical_instant_collide(
    app_role_url: str,
) -> None:
    """The OTHER index — `idx_bookings_tenant_customer_starts_unique` (0009) — and
    it gets its own test rather than sharing the one above so that a future change
    to either cannot be covered for by the other.

    Same forced instant, same customer. The instant is forced for the reason the
    sibling states."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id)
        customer_id = await _customer_for(factory, tenant_id, type_id)

        async with tenant_session(factory, tenant_id) as session:
            await BookingsRepository().insert_walk_in(
                session,
                tenant_id=tenant_id,
                customer_id=customer_id,
                appointment_type_id=type_id,
                appointment_type_name="מדידה ראשונה",
                at=NOW,
            )

        with pytest.raises(IntegrityError):
            async with tenant_session(factory, tenant_id) as session:
                await BookingsRepository().insert_walk_in(
                    session,
                    tenant_id=tenant_id,
                    customer_id=customer_id,
                    appointment_type_id=type_id,
                    appointment_type_name="מדידה ראשונה",
                    at=NOW,
                )
    finally:
        await engine.dispose()


async def test_create_walk_in_answers_a_confirmed_row_that_is_already_checked_in(
    app_role_url: str,
) -> None:
    """The happy path, and the two properties the board depends on: she is
    `confirmed` and she is already in the building, so F34's rules give her the
    arrival line and the undo control with no edit.

    `manage_token is None` on the mutation is what makes the router's
    `_send_rotation` return early — the absence of a link travels out on the
    result, not on a comment."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    staff = _staff(tenant_id)
    try:
        type_id = await _seed(factory, tenant_id)
        customer_id = await _customer_for(factory, tenant_id, type_id)

        result = await _owner(factory).create_walk_in(
            tenant_id, customer_id=customer_id, appointment_type_id=type_id, staff=staff
        )

        assert result.changed is True
        assert result.manage_token is None
        assert result.booking.status == BookingStatus.CONFIRMED.value
        assert result.booking.source == BookingSource.WALK_IN.value
        assert result.booking.checked_in_at == NOW
        assert result.booking.starts_at == NOW
        # The SNAPSHOT, taken from the type at create time — a renamed type must
        # not rewrite history.
        assert result.booking.appointment_type_name == "מדידה ראשונה"
    finally:
        await engine.dispose()


async def test_an_unknown_customer_is_a_404(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id)

        with pytest.raises(BookingNotFoundError):
            await _owner(factory).create_walk_in(
                tenant_id,
                customer_id=uuid.uuid4(),
                appointment_type_id=type_id,
                staff=_staff(tenant_id),
            )
    finally:
        await engine.dispose()


async def test_an_erased_customer_is_the_same_404_and_writes_no_booking(
    app_role_url: str,
) -> None:
    """After a §14 erase there is no data subject here, so creating a booking for
    her would resurrect a processing relationship the erasure record says ended.

    ⚠ THE ROW COUNT IS WHAT ARMS THIS TEST. Without it an implementation that
    creates the booking and THEN notices `erased_at` would pass on the exception
    alone — and the seeded storefront booking is what makes the count meaningful,
    because "one booking, not two" is a claim and "zero bookings" would not be."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id)
        customer_id = await _customer_for(factory, tenant_id, type_id)
        async with tenant_session(factory, tenant_id) as session:
            customer = await session.get(Customer, customer_id)
            assert customer is not None
            customer.erased_at = NOW

        before = await _bookings_of(factory, tenant_id)
        with pytest.raises(BookingNotFoundError):
            await _owner(factory).create_walk_in(
                tenant_id,
                customer_id=customer_id,
                appointment_type_id=type_id,
                staff=_staff(tenant_id),
            )

        assert [row.id for row in await _bookings_of(factory, tenant_id)] == [
            row.id for row in before
        ]
    finally:
        await engine.dispose()


async def test_an_unknown_type_and_an_archived_type_are_the_same_404(
    app_role_url: str,
) -> None:
    """Indistinguishable from an unknown customer BY DESIGN, which is
    `BookingNotFoundError`'s own rule — this route must not tell an authenticated
    caller which of the two ids was the bad one.

    The archived half guards a DEPENDENCY rather than F50's own code:
    `AppointmentTypesRepository.by_id` filters `deleted_at IS NULL`, and a
    soft-deleted type IS an archived one here. Deleting that shipped predicate is
    what reds the second half."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id)
        customer_id = await _customer_for(factory, tenant_id, type_id)
        owner = _owner(factory)

        with pytest.raises(BookingNotFoundError):
            await owner.create_walk_in(
                tenant_id,
                customer_id=customer_id,
                appointment_type_id=uuid.uuid4(),
                staff=_staff(tenant_id),
            )

        async with tenant_session(factory, tenant_id) as session:
            assert await AppointmentTypesRepository().soft_delete(session, tenant_id, type_id)

        with pytest.raises(BookingNotFoundError):
            await owner.create_walk_in(
                tenant_id,
                customer_id=customer_id,
                appointment_type_id=type_id,
                staff=_staff(tenant_id),
            )
    finally:
        await engine.dispose()


async def test_the_walk_in_audit_row_carries_both_ids_and_neither_the_phone_nor_the_name(
    app_role_url: str,
) -> None:
    """This row is the ONLY record of who created a booking that carries no terms
    evidence, which is what makes it the audit entry that most earns its place.

    The `details` key set is asserted by EQUALITY, not by membership: the mutation
    that matters is a later well-meaning addition of `customer_name` or a phone,
    and F20's rule for its own rows is `phone_last4` and never the number. Here
    even a last4 is unnecessary, because `customer_id` resolves it."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    staff = _staff(tenant_id)
    try:
        type_id = await _seed(factory, tenant_id)
        customer_id = await _customer_for(factory, tenant_id, type_id)

        result = await _owner(factory).create_walk_in(
            tenant_id, customer_id=customer_id, appointment_type_id=type_id, staff=staff
        )

        rows = [
            row
            for row in await _audit(factory, tenant_id)
            if row.action == AuditAction.BOOKING_WALK_IN_CREATED.value
        ]
        assert len(rows) == 1
        assert rows[0].actor_id == staff.id
        assert rows[0].entity == str(result.booking.id)
        assert rows[0].details == {
            "customer_id": str(customer_id),
            "appointment_type_id": str(type_id),
        }
    finally:
        await engine.dispose()


async def test_the_walk_in_writes_no_customers_column_and_leaves_an_existing_consent_alone(
    app_role_url: str,
) -> None:
    """§30A. The correct `marketing_consent` value on this path is NO FIELD AT ALL,
    not `false` — the CHECK on `customers.marketing_consent_source` admits only
    'booking_form', and `MarketingConsentSource` already refused F33's STRONGER
    case as laundering. A staffer's recollection is less than a box a bride ticked
    herself.

    ⚠ THE CONSENT IS SEEDED, and that is what arms this test. Against a customer
    whose `marketing_consent_at` is NULL, "unchanged" is NULL-to-NULL and the
    assertion passes just as happily on an implementation that CLEARS it — the
    exact vacuity this project has shipped before. So the seeded booking opts in,
    and the assertion is byte-identity on the timestamp plus a still-NULL
    withdrawal.

    Adding any `record_marketing_consent` or `withdraw_marketing_consent` call to
    `create_walk_in` reds this."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A, marketing_consent=True)
        customer_id = claim.booking.customer_id

        async with tenant_session(factory, tenant_id) as session:
            before = await session.get(Customer, customer_id)
            assert before is not None
            consented_at = before.marketing_consent_at
            source = before.marketing_consent_source
            updated_at = before.updated_at
        assert consented_at is not None, "the seed must actually hold a consent"

        await _owner(factory).create_walk_in(
            tenant_id,
            customer_id=customer_id,
            appointment_type_id=type_id,
            staff=_staff(tenant_id),
        )

        async with tenant_session(factory, tenant_id) as session:
            after = await session.get(Customer, customer_id)
            assert after is not None
            assert after.marketing_consent_at == consented_at
            assert after.marketing_consent_source == source
            assert after.marketing_consent_withdrawn_at is None
            # The `customers` row was not written AT ALL — the updated_at trigger
            # is what would say otherwise, and it fires on any UPDATE including one
            # that changes nothing visible.
            assert after.updated_at == updated_at
    finally:
        await engine.dispose()


async def test_the_walk_in_schedules_no_reminder_and_mints_no_manage_token(
    app_role_url: str,
) -> None:
    """No `scheduled_messages` row and no token hash, asserted against a booking
    that EXISTS rather than against an empty table — which is what stops both
    halves passing vacuously.

    The seeded storefront booking is the positive control: it DOES get a pending
    reminder and it DOES carry a hash, so "zero for the walk-in" is a difference
    rather than a property of the fixture."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)
        customer_id = claim.booking.customer_id

        result = await _owner(factory).create_walk_in(
            tenant_id,
            customer_id=customer_id,
            appointment_type_id=type_id,
            staff=_staff(tenant_id),
        )

        assert await _pending(factory, tenant_id, claim.booking.id) is not None
        assert claim.booking.manage_token_hash is not None

        assert await _pending(factory, tenant_id, result.booking.id) is None
        stored = await _row(factory, tenant_id, result.booking.id)
        assert stored is not None
        assert stored.manage_token_hash is None
    finally:
        await engine.dispose()


# --- F50's four disarm assertions: shipped predicates, pinned against a walk-in ---
#
# Each pins a predicate that ALREADY EXISTS against a row F50 creates, so a future
# edit to any of the four collides with a test instead of with a bride. None of
# them assert anything F50 wrote — that is the point. "This feature does not mint
# a link" is a statement about THIS feature; `starts_at = now` is a property of the
# ROW, and it holds against writers this spec never read.


async def test_the_manage_link_backfill_feed_never_returns_a_walk_in(
    app_role_url: str,
) -> None:
    """`list_confirmed_without_manage_token` is `confirmed AND source =
    'storefront' AND starts_at > after AND manage_token_hash IS NULL`, and a
    walk-in fails TWO of the four — the clock, which is what `starts_at = now`
    buys, and the source, which is what makes the exclusion hold when the clock
    does not.

    ⚠ THE PRESENT ROW IS WHAT ARMS THIS TEST. Without a future storefront booking
    with a NULL hash in the same tenant, widening or deleting either predicate
    would add no rows to an empty result and this would pass on nothing — the
    seeded-fixture vacuity this project has shipped three times.

    TWO reads, and the SECOND is the one that earns its place. `after=NOW` reds on
    deleting `Booking.starts_at > after`. The second — `after` one second BEFORE
    the walk-in's instant — reproduces the review's once-captured-clock race
    exactly: `ManageLinkBackfill.run()` takes `now` ONCE and passes it to every
    tenant, so a walk-in created after that capture DOES satisfy the clock, and
    only `source` keeps it out. It reds on deleting
    `Booking.source == BookingSource.STOREFRONT.value` and on nothing else.

    The clock predicate keeps a second, independent guardian in the feature that
    owns it — F16's `test_the_backfill_skips_a_booking_that_has_already_happened`
    (`test_booking_comms_db.py`), verified to red on the same deletion — so no past
    row is seeded here to duplicate it."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A)
        # A future storefront booking that HAS no hash — the backfill's real feed,
        # and the positive control.
        async with tenant_session(factory, tenant_id) as session:
            await session.execute(
                update(Booking).where(Booking.id == claim.booking.id).values(manage_token_hash=None)
            )

        walk_in = await _owner(factory).create_walk_in(
            tenant_id,
            customer_id=claim.booking.customer_id,
            appointment_type_id=type_id,
            staff=_staff(tenant_id),
        )

        async with tenant_session(factory, tenant_id) as session:
            feed = await BookingsRepository().list_confirmed_without_manage_token(
                session, tenant_id, after=NOW, limit=50
            )

        found = {row.id for row in feed}
        assert claim.booking.id in found, "the future storefront row must be in the feed"
        assert walk_in.booking.id not in found

        # The race the clock alone does not cover: `after` predates the walk-in,
        # so `starts_at > after` is TRUE for it and only `source` keeps it out.
        async with tenant_session(factory, tenant_id) as session:
            raced = await BookingsRepository().list_confirmed_without_manage_token(
                session, tenant_id, after=NOW - datetime.timedelta(seconds=1), limit=50
            )

        raced_ids = {row.id for row in raced}
        assert claim.booking.id in raced_ids, "the positive control must survive the wider window"
        assert walk_in.booking.id not in raced_ids
    finally:
        await engine.dispose()


async def test_resend_link_on_a_walk_in_is_refused(app_role_url: str) -> None:
    """F15's `_guard_live` refuses link rotation on any booking with
    `starts_at <= now`, so a staffer cannot text an SMS control link for a walk-in
    — by a guard F15 already wrote, against a row F50 creates.

    Its own test rather than one shared with the phone correction below: the two
    routes share `_guard_live` TODAY, and a later feature that gives one of them
    its own guard must not silently take the other's coverage with it."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id)
        customer_id = await _customer_for(factory, tenant_id, type_id)
        owner = _owner(factory)
        walk_in = await owner.create_walk_in(
            tenant_id, customer_id=customer_id, appointment_type_id=type_id, staff=_staff(tenant_id)
        )

        with pytest.raises(BookingTransitionInvalidError):
            await owner.resend_link(tenant_id, walk_in.booking.id, staff=_staff(tenant_id))
    finally:
        await engine.dispose()


async def test_phone_correction_on_a_walk_in_is_refused(app_role_url: str) -> None:
    """The sibling of the resend above, deliberately asserted independently — the
    value here is the PAIR, not the line they currently share."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id)
        customer_id = await _customer_for(factory, tenant_id, type_id)
        owner = _owner(factory)
        walk_in = await owner.create_walk_in(
            tenant_id, customer_id=customer_id, appointment_type_id=type_id, staff=_staff(tenant_id)
        )

        with pytest.raises(BookingTransitionInvalidError):
            await owner.correct_phone(
                tenant_id, walk_in.booking.id, phone=_phone(), staff=_staff(tenant_id)
            )
    finally:
        await engine.dispose()


async def test_a_walk_in_refuses_cancel_and_admits_no_show_and_complete(
    app_role_url: str,
) -> None:
    """F15's clock split, evaluated against a row born at `now`: cancel needs a
    FUTURE `starts_at` and is refused; `no_show` and `complete` need a past one and
    are exactly the verbs a person standing in the shop needs.

    The two successes are what prove the row is a USABLE booking rather than an
    inert one — a test that only asserted the 409 would be satisfied by a row
    nothing at all can act on.

    ⚠ The second walk-in needs its OWN service on a LATER clock, and the reason is
    worth stating because it is the collision D4 accepts, reproduced: `_now()` is
    frozen at NOW under the injected test clock, so two creates through one service
    write the same `starts_at` and the second is refused by
    `idx_bookings_slot_seat_unique` as a SLOT_UNAVAILABLE. In production the clock
    really does move and the instant really is microsecond-unique; here it must be
    moved by hand."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=2)
        first = await _customer_for(factory, tenant_id, type_id)
        second = (await _claim(factory, tenant_id, type_id, starts_at=SLOT_B)).booking.customer_id
        owner = _owner(factory)
        walk_in = await owner.create_walk_in(
            tenant_id, customer_id=first, appointment_type_id=type_id, staff=_staff(tenant_id)
        )

        with pytest.raises(BookingTransitionInvalidError):
            await owner.cancel(tenant_id, walk_in.booking.id, staff=_staff(tenant_id))

        no_show = await owner.no_show(tenant_id, walk_in.booking.id, staff=_staff(tenant_id))
        assert no_show.booking.status == BookingStatus.NO_SHOW.value

        # A second walk-in, because `complete` on the first would now be a
        # transition off `no_show` and would prove less than a clean one.
        later = _owner(factory, now=NOW + datetime.timedelta(seconds=1))
        other = await later.create_walk_in(
            tenant_id, customer_id=second, appointment_type_id=type_id, staff=_staff(tenant_id)
        )
        done = await later.complete(tenant_id, other.booking.id, staff=_staff(tenant_id))
        assert done.booking.status == BookingStatus.COMPLETED.value
    finally:
        await engine.dispose()
