"""F19's centrepiece: the five interleavings only Postgres can settle.

Interview Q7 is the reason this feature is being built before any merchant
account exists — *"the race most likely to be wrong (hold expiry vs a late
webhook) does not depend on Grow, so it gets built and race-tested now"*. This
file is that test, plus the two windows the adversarial review filed as BLOCKER
because neither had a recoverer at all.

**Why every driver gets its own connection.** `NullPool` + `asyncio.gather`, the
`test_booking_comms_db.py` / `test_payments_service.py` discipline. Both of those
files say so in their own docstrings for the same reason: a sequential loop over
the same connection PASSES while the code is broken, because one transaction
cannot contend with itself. Every gathered pair below opens its own
`tenant_session` off a NullPool engine, so the row locks are real ones.

**Why the clock is frozen and injected on BOTH sides.** `NOW` is a module
constant and `_clock` returns it; `PaymentService`, `BookingService`,
`DepositBookingService` and `DepositSweeper` are all handed the same callable.
The hold is written by `open_deposit` and read by the sweeper's claim 1, so a
test that cannot pin both sides of that comparison cannot pin the race at all
(`sweeper.py`'s constructor says exactly this).

**How an already-expired hold is produced without moving the clock.** The hold
LENGTH is a separate knob from the clock: `BookingService(deposit_hold_seconds=0)`
stores `hold_expires_at = NOW`, and claim 1's predicate is `hold_expires_at <=
now`, so the hold is claimable at `NOW` with nothing unpinned. The sweeper keeps
the production `900 / 60` for claim 2's `hold + poll` grace, so a fresh booking
is never swept as an orphan out from under a live hold — the two knobs are
independent, which `test_deposit_sweeper_db.py::test_the_hold_length_is_what_moves_the_race_width`
establishes and this file relies on.

**Evidence is read off return values and INSERTed rows, never off a re-read of a
row a guarded UPDATE just touched.** `BookingsRepository.cancel`'s own docstring
explains why: ORM-enabled DML with `evaluate` synchronization stamps the SET
values onto the identity-mapped instance whatever the database actually matched,
so "did I win?" is answered by `SweepResult`, by `.returning()`, or by the audit
and `message_log` rows the winning branch appends — one row per winner, and a
row that was never written cannot lie about having been.

**Cleanup is not optional.** This file writes `bookings.status =
'pending_payment'` and `cancelled_by = 'expired'`, and migration 0015's downgrade
narrows both CHECKs — which Postgres refuses while any row still holds them. One
leaked row reds seven unrelated migration round-trip tests, so every test purges
its tenant in a `finally`. `payments` rows are left: 0012 REVOKEs DELETE on that
table from app_user, and every status they carry was already legal there.
"""

import asyncio
import datetime
import secrets
import uuid

import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.tokens import hash_token
from app.booking.comms import BookingCommsService, CommsTenant
from app.booking.service import BookingClaim, BookingService, SlotUnavailableError
from app.booking.validation import jerusalem_day_index
from app.db.repositories.appointment_types import AppointmentTypesRepository
from app.db.repositories.availability import AvailabilityRulesRepository
from app.db.repositories.bookings import BookingsRepository
from app.db.repositories.otp_codes import OtpCodesRepository
from app.db.repositories.payments import PaymentsRepository
from app.db.repositories.terms import TermsVersionsRepository
from app.db.tenant import tenant_session
from app.models.audit_log import AuditLog
from app.models.booking import Booking
from app.models.constants import (
    AppointmentAudience,
    AuditAction,
    BookingStatus,
    MessageKind,
    PaymentStatus,
)
from app.models.customer import Customer
from app.models.message_log import MessageLog
from app.models.payment import Payment
from app.notifications.fake import FakeSmsSender
from app.notifications.service import NotificationService, OtpService
from app.notifications.validation import normalize_israeli_mobile
from app.payments.fake import FakeGateway, fake_webhook_body, sign_fake_webhook
from app.payments.secretbox import FakeSecretBox
from app.payments.service import GatewayCredentialService, PaymentService
from app.payments.sweeper import DepositSweeper, SweepResult
from app.payments.webhook_router import DepositBookingService
from app.storefront.validation import BOUTIQUE_TIMEZONE

pytestmark = pytest.mark.db

SECRET = "webhook-secret-1"
GOOD = {"merchant_id": "m-1", "api_key": "k-1", "webhook_secret": SECRET}

TARGET_DATE = datetime.date(2026, 8, 23)
BASE_DOMAIN = "modryn.co.il"
RETURN_URL = "https://bella.modryn.co.il/book/return"
DEPOSIT_AGOROT = 30_000
SETTINGS: dict[str, object] = {"toggles": {"deposits_enabled": True}}

# The frozen clock. Weeks before the slot, so `reminder_send_after` takes the
# >=24h band and D12's immediate-reminder bug is not what any assertion below is
# accidentally measuring.
NOW = datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.UTC)


def _clock() -> datetime.datetime:
    return NOW


# A live hold: `hold_expires_at = NOW + 900`, so claim 1 cannot touch it.
LIVE_HOLD_SECONDS = 900
# An already-expired hold: `hold_expires_at = NOW`, and claim 1's predicate is
# `<= now`. This is how the expiry side of the race is armed without moving a
# clock the webhook side also reads.
EXPIRED_HOLD_SECONDS = 0

# The sweeper's OWN configuration, which drives claim 2's `hold + poll` grace and
# nothing else — claim 1 reads the stored `hold_expires_at`. Production values,
# so a booking created this instant is never mistaken for an orphan.
SWEEP_HOLD_SECONDS = 900
POLL_SECONDS = 60


def _at(hour: int, minute: int = 0) -> datetime.datetime:
    return datetime.datetime.combine(
        TARGET_DATE, datetime.time(hour, minute), tzinfo=BOUTIQUE_TIMEZONE
    ).astimezone(datetime.UTC)


SLOT = _at(10, 0)


# --- wiring -----------------------------------------------------------------


def _factory(url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(url, poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _loose() -> FixedWindowRateLimiter:
    return FixedWindowRateLimiter(max_attempts=10_000, window_seconds=3600, clock=lambda: 0.0)


def _phone() -> str:
    return f"+9725{uuid.uuid4().int % 10**8:08d}"


def _tenant(tenant_id: uuid.UUID) -> CommsTenant:
    return CommsTenant(id=tenant_id, slug="bella", name="בלה כלות", phone="052-1234567")


def _signed(
    *, session_id: str, transaction_id: str, amount_agorot: int = DEPOSIT_AGOROT, paid: bool = True
) -> tuple[bytes, str]:
    """Bodies and signatures ONLY through the gateway's own helpers. A hand-built
    JSON blob would drift from what `verify_webhook` parses and the suite would
    be proving a shape no adapter produces."""
    body = fake_webhook_body(
        provider_session_id=session_id,
        provider_transaction_id=transaction_id,
        amount_agorot=amount_agorot,
        paid=paid,
    )
    return body, sign_fake_webhook(webhook_secret=SECRET, body=body)


class _Rig:
    """Every collaborator one test needs, off one factory and one clock."""

    # Filled by `_rig` after the seed, which needs a session the rig must exist
    # to open.
    type_id: uuid.UUID

    def __init__(
        self,
        factory: async_sessionmaker[AsyncSession],
        tenant_id: uuid.UUID,
        *,
        hold_seconds: int,
    ) -> None:
        self.factory = factory
        self.tenant_id = tenant_id
        self.gateway = FakeGateway()
        self.sender = FakeSmsSender()
        self.credentials = GatewayCredentialService(
            factory,
            gateway=self.gateway,
            secret_box=FakeSecretBox(),
            connect_limiter=_loose(),
            validate_limiter=_loose(),
            clock=_clock,
        )
        self.payments = PaymentService(
            factory, gateway=self.gateway, credentials=self.credentials, clock=_clock
        )
        self.comms = BookingCommsService(
            factory,
            notifications=NotificationService(factory, sender=self.sender),
            base_domain=BASE_DOMAIN,
            clock=_clock,
        )
        self.deposits = DepositBookingService(
            factory,
            payments=self.payments,
            credentials=self.credentials,
            comms=self.comms,
            clock=_clock,
        )
        self.bookings = BookingService(
            factory,
            otp=OtpService(
                factory,
                notifications=NotificationService(factory, sender=FakeSmsSender()),
                phone_limiter=_loose(),
                tenant_limiter=_loose(),
                verify_limiter=_loose(),
                ip_limiter=_loose(),
                clock=_clock,
            ),
            create_limiter=_loose(),
            phone_limiter=_loose(),
            clock=_clock,
            gateway_credentials=self.credentials,
            payments=self.payments,
            deposit_hold_seconds=hold_seconds,
        )
        # The SAME injected clock as `open_deposit`. The hold length differs on
        # purpose — see the module docstring.
        self.sweeper = DepositSweeper(
            factory,
            hold_seconds=SWEEP_HOLD_SECONDS,
            poll_interval_seconds=POLL_SECONDS,
            clock=_clock,
        )

    async def settle(self, *, session_id: str, transaction_id: str, paid: bool = True) -> None:
        body, signature = _signed(session_id=session_id, transaction_id=transaction_id, paid=paid)
        await self.deposits.settle(_tenant(self.tenant_id), body=body, signature=signature)


async def _seed(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, *, capacity: int
) -> uuid.UUID:
    async with tenant_session(factory, tenant_id) as session:
        await AvailabilityRulesRepository().insert(
            session,
            tenant_id=tenant_id,
            day_of_week=jerusalem_day_index(TARGET_DATE),
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
            deposit_required=True,
            deposit_amount_agorot=DEPOSIT_AGOROT,
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


async def _rig(url: str, *, hold_seconds: int, capacity: int = 1) -> tuple[AsyncEngine, _Rig]:
    engine, factory = _factory(url)
    tenant_id = uuid.uuid4()
    rig = _Rig(factory, tenant_id, hold_seconds=hold_seconds)
    await rig.credentials.connect(tenant_id, fields=GOOD, actor_id=uuid.uuid4())
    rig.type_id = await _seed(factory, tenant_id, capacity=capacity)
    return engine, rig


async def _verified(rig: _Rig, raw_phone: str) -> str:
    """A consumed OTP, minted outside the gathered section: two racers must
    contend over the SEAT, not over the OTP table."""
    token = secrets.token_urlsafe(16)
    repo = OtpCodesRepository()
    future = datetime.datetime(2099, 1, 1, tzinfo=datetime.UTC)
    async with tenant_session(rig.factory, rig.tenant_id) as session:
        row = await repo.insert(
            session,
            tenant_id=rig.tenant_id,
            phone=normalize_israeli_mobile(raw_phone),
            code_hash="seed",
            expires_at=future,
        )
        await repo.mark_consumed(
            session,
            rig.tenant_id,
            row.id,
            verification_token_hash=hash_token(token),
            verification_expires_at=future,
        )
    return token


async def _create(
    rig: _Rig, *, phone: str, token: str, starts_at: datetime.datetime = SLOT
) -> BookingClaim:
    return await rig.bookings.create_booking(
        rig.tenant_id,
        raw_phone=phone,
        verification_token=token,
        name="נועה לוי",
        appointment_type_id=rig.type_id,
        starts_at=starts_at,
        terms_version=1,
        settings=SETTINGS,
    )


async def _hold(
    rig: _Rig, *, starts_at: datetime.datetime = SLOT, phone: str | None = None
) -> tuple[BookingClaim, str]:
    """A committed `pending_payment` booking with a real hold behind it, through
    the shipped writers — create then pay, which is D11's ordering. Returns the
    provider session id, already narrowed, because every webhook below is keyed
    on it."""
    resolved = phone if phone is not None else _phone()
    claim = await _create(
        rig, phone=resolved, token=await _verified(rig, resolved), starts_at=starts_at
    )
    outcome = await rig.bookings.open_deposit(rig.tenant_id, claim, return_url=RETURN_URL)
    assert outcome.deposit_due is True, "the fixture must produce a real deposit hold"
    assert outcome.payment_session_id is not None
    return claim, outcome.payment_session_id


# --- reads ------------------------------------------------------------------


async def _booking(rig: _Rig, booking_id: uuid.UUID) -> Booking:
    async with tenant_session(rig.factory, rig.tenant_id) as session:
        row = await BookingsRepository().by_id(session, rig.tenant_id, booking_id)
    assert row is not None
    return row


async def _payment_for(rig: _Rig, booking_id: uuid.UUID) -> Payment:
    async with tenant_session(rig.factory, rig.tenant_id) as session:
        rows = await PaymentsRepository().by_booking_ids(session, rig.tenant_id, [booking_id])
    assert booking_id in rows
    return rows[booking_id]


async def _has_payment(rig: _Rig, booking_id: uuid.UUID) -> bool:
    async with tenant_session(rig.factory, rig.tenant_id) as session:
        rows = await PaymentsRepository().by_booking_ids(session, rig.tenant_id, [booking_id])
    return booking_id in rows


async def _kinds(rig: _Rig) -> list[str]:
    async with tenant_session(rig.factory, rig.tenant_id) as session:
        stmt = select(MessageLog.kind).order_by(MessageLog.created_at)
        return list((await session.execute(stmt)).scalars().all())


async def _actions(rig: _Rig) -> list[str]:
    async with tenant_session(rig.factory, rig.tenant_id) as session:
        stmt = select(AuditLog.action).order_by(AuditLog.created_at)
        return list((await session.execute(stmt)).scalars().all())


async def _age(rig: _Rig, booking_id: uuid.UUID, *, created_at: datetime.datetime) -> None:
    """`created_at` is a server default and claim 2's grace is a predicate on
    it, so the crash cases have to be able to age a row. Written explicitly
    rather than by moving the clock, because the DB's `now()` is the real wall
    clock and `NOW` is not."""
    async with tenant_session(rig.factory, rig.tenant_id) as session:
        await session.execute(
            update(Booking)
            .where(Booking.id == booking_id)
            .values(created_at=created_at)
            .execution_options(synchronize_session=False)
        )


async def _purge(rig: _Rig) -> None:
    """MANDATORY — see the module docstring. A leaked `pending_payment` or
    `cancelled_by = 'expired'` row makes migration 0015's own downgrade fail and
    takes the round-trip suite with it."""
    async with tenant_session(rig.factory, rig.tenant_id) as session:
        await session.execute(delete(MessageLog).where(MessageLog.tenant_id == rig.tenant_id))
        await session.execute(delete(Booking).where(Booking.tenant_id == rig.tenant_id))
        await session.execute(delete(Customer).where(Customer.tenant_id == rig.tenant_id))
        await session.execute(delete(AuditLog).where(AuditLog.tenant_id == rig.tenant_id))


# --- race 1: the sweeper and the webhook on the same hold (row #9) ----------


async def test_the_sweeper_and_the_webhook_never_both_win_the_same_hold(
    app_role_url: str,
) -> None:
    """Race row #9, gathered on two connections.

    Both drivers issue a guarded UPDATE against ONE `payments` row: the sweeper's
    `WHERE status='pending' AND hold_expires_at <= now`, and `settle`'s `WHERE
    status='pending'`. Neither carries a locking clause, so the loser BLOCKS on
    the row lock and then matches nothing — which is the serialization D6 wants
    and the reason the outcome is a clean disjunction rather than a coin toss
    over torn state.

    The property: exactly one of {the seat was freed, the booking was confirmed
    inline} — never both, never neither. It is read off `SweepResult` (the
    `.returning()` scalar count) and off the `BOOKING_CONFIRMED` audit row, which
    only the confirm branch appends. Neither is a re-read of the row the UPDATE
    touched, which `cancel()`'s docstring explains cannot answer this question.

    Both arms then converge, and that is the point of the feature: whether her
    money beat the sweeper or lost to it, she ends confirmed at her own seat with
    exactly one SMS — the loser's arm getting there through D5's rebind.
    """
    engine, rig = await _rig(app_role_url, hold_seconds=EXPIRED_HOLD_SECONDS)
    try:
        claim, session_id = await _hold(rig)

        swept, _ = await asyncio.gather(
            rig.sweeper.sweep(rig.tenant_id),
            rig.settle(session_id=session_id, transaction_id="txn-1"),
        )

        seat_freed = swept.released == 1
        confirmed_inline = AuditAction.BOOKING_CONFIRMED.value in await _actions(rig)
        assert seat_freed != confirmed_inline, (
            "exactly one of {seat freed, booking confirmed} must happen — both "
            "means the guarded UPDATEs did not serialize, neither means the hold "
            "was lost between them"
        )
        # The sweeper either claimed the hold AND released its seat, or did
        # neither: a torn claim is its own failure.
        assert swept.expired == swept.released

        payment = await _payment_for(rig, claim.booking.id)
        assert payment.status == PaymentStatus.PAID.value
        booking = await _booking(rig, claim.booking.id)
        assert booking.status == BookingStatus.CONFIRMED.value
        assert booking.starts_at == SLOT
        assert booking.seat_index == claim.booking.seat_index
        assert booking.cancelled_at is None
        assert booking.cancelled_by is None
        assert await _kinds(rig) == [MessageKind.CONFIRMATION.value]
    finally:
        await _purge(rig)
        await engine.dispose()


# --- race 2: two deliveries of the same transaction (row #6) ----------------


async def test_two_concurrent_deliveries_confirm_once_text_once_and_log_once(
    app_role_url: str,
) -> None:
    """Race row #6. A provider that never saw our 200 posts the SAME transaction
    twice, and the two land at once.

    Exactly-once here is not our bookkeeping — it is `set_status`'s
    `allowed_from=('pending_payment',)` evaluated by Postgres under the row lock.
    The loser matches nothing and therefore writes no SMS, no reminder rewrite
    and no audit row, and the three counts below are what prove that: one
    `message_log` row, one `BOOKING_CONFIRMED`, one confirmed booking.
    """
    engine, rig = await _rig(app_role_url, hold_seconds=LIVE_HOLD_SECONDS)
    try:
        claim, session_id = await _hold(rig)

        await asyncio.gather(
            rig.settle(session_id=session_id, transaction_id="txn-1"),
            rig.settle(session_id=session_id, transaction_id="txn-1"),
        )

        assert await _kinds(rig) == [MessageKind.CONFIRMATION.value]
        assert (await _actions(rig)).count(AuditAction.BOOKING_CONFIRMED.value) == 1
        assert (await _booking(rig, claim.booking.id)).status == BookingStatus.CONFIRMED.value
        assert (await _payment_for(rig, claim.booking.id)).status == PaymentStatus.PAID.value
    finally:
        await _purge(rig)
        await engine.dispose()


# --- race 3: two brides for the last seat, one mid-payment ------------------


async def test_two_brides_race_for_the_last_seat_and_the_unpaid_hold_keeps_it(
    app_role_url: str,
) -> None:
    """The seat invariant, unchanged from F13 and now with `pending_payment` in
    it. Capacity 1, two brides, one instant, gathered.

    Seat choice happens under `pg_advisory_xact_lock(hashtext(tenant_id))`
    against `active_seats_at`, whose predicate is `status <> 'cancelled'` — so a
    row that is merely HELD counts, and `idx_bookings_slot_seat_unique` refuses
    the write of any racer that skipped the lock. Exactly one bride gets a claim;
    the other gets `SlotUnavailableError`, which is the 409 the storefront shows.

    The third create is the F19-specific half: the winner is mid-payment, her
    deposit is unpaid, and the seat is STILL hers.
    """
    engine, rig = await _rig(app_role_url, hold_seconds=LIVE_HOLD_SECONDS, capacity=1)
    try:
        first, second = _phone(), _phone()
        first_token = await _verified(rig, first)
        second_token = await _verified(rig, second)

        results = await asyncio.gather(
            _create(rig, phone=first, token=first_token),
            _create(rig, phone=second, token=second_token),
            return_exceptions=True,
        )

        claims = [r for r in results if isinstance(r, BookingClaim)]
        refusals = [r for r in results if isinstance(r, SlotUnavailableError)]
        assert len(claims) == 1
        assert len(refusals) == 1, f"the loser must be a 409, not {results}"

        winner = claims[0]
        assert winner.booking.status == BookingStatus.PENDING_PAYMENT.value
        assert winner.deposit_due is True

        outcome = await rig.bookings.open_deposit(rig.tenant_id, winner, return_url=RETURN_URL)
        assert outcome.deposit_due is True

        third = _phone()
        third_token = await _verified(rig, third)
        with pytest.raises(SlotUnavailableError):
            await _create(rig, phone=third, token=third_token)
    finally:
        await _purge(rig)
        await engine.dispose()


# --- race 4: a late delivery against another bride's create -----------------


async def test_a_late_delivery_racing_a_new_bride_has_exactly_two_outcomes(
    app_role_url: str,
) -> None:
    """The freed seat, contested. Her hold expired and the sweeper released the
    seat; a second bride reaches for it at the same instant her late payment
    lands.

    Both drivers take the SAME advisory lock — `create_booking`'s key and D5's
    rebind key are `hashtext(tenant_id)` verbatim — so they serialize, and there
    are exactly two correct endings:

      * the new bride wins the seat, and the rebind falls to D5 step 4: booking
        stays cancelled, payment stays paid, `DEPOSIT_LATE_UNRESOLVED`, and MD2's
        `PAYMENT_RECEIVED_NO_SLOT` SMS;
      * the rebind wins, and her create is refused with `SlotUnavailableError`.

    A THIRD outcome — both holding the seat, or neither, or a 500 out of the
    honour path — is what this asserts against, which is why the disjunction is
    asserted rather than one arm pinned.
    """
    engine, rig = await _rig(app_role_url, hold_seconds=EXPIRED_HOLD_SECONDS, capacity=1)
    try:
        claim, session_id = await _hold(rig)
        assert await rig.sweeper.sweep(rig.tenant_id) == SweepResult(expired=1, released=1)

        other = _phone()
        other_token = await _verified(rig, other)

        settled, created = await asyncio.gather(
            rig.settle(session_id=session_id, transaction_id="txn-late"),
            _create(rig, phone=other, token=other_token),
            return_exceptions=True,
        )

        assert settled is None, (
            "the honour path must never raise — `settle_late` has already "
            "committed the transaction id, so a 500 here is unrecoverable"
        )
        actions = await _actions(rig)
        honoured = AuditAction.DEPOSIT_LATE_HONOURED.value in actions
        unresolved = AuditAction.DEPOSIT_LATE_UNRESOLVED.value in actions
        assert honoured != unresolved, "the honour path resolves one way or the other, once"

        hers = await _booking(rig, claim.booking.id)
        assert (await _payment_for(rig, claim.booking.id)).status == PaymentStatus.PAID.value

        if isinstance(created, SlotUnavailableError):
            assert honoured
            assert hers.status == BookingStatus.CONFIRMED.value
            assert hers.seat_index == claim.booking.seat_index
            assert hers.cancelled_at is None
            assert hers.cancelled_by is None
            assert await _kinds(rig) == [MessageKind.CONFIRMATION.value]
        else:
            assert isinstance(created, BookingClaim), f"a third outcome: {created!r}"
            assert created.booking.status == BookingStatus.PENDING_PAYMENT.value
            assert created.booking.seat_index == claim.booking.seat_index
            assert unresolved
            assert hers.status == BookingStatus.CANCELLED.value
            assert await _kinds(rig) == [MessageKind.PAYMENT_RECEIVED_NO_SLOT.value]
    finally:
        await _purge(rig)
        await engine.dispose()


# --- race 5: the sweeper against a late webhook (row #13) -------------------


async def test_the_sweeper_racing_a_late_webhook_never_alerts_on_a_free_seat(
    app_role_url: str,
) -> None:
    """**Race row #13 — the one this feature exists to get right.**

    The window: the sweeper's payments UPDATE commits, a webhook blocked on that
    row lock wakes, sees `expired`, honours it — and finds a booking still at
    `pending_payment` because the seat cancel has not landed yet. Under a narrow
    `allowed_from=('cancelled',)` the rebind matches nothing and files a "seat
    taken" alert on a seat that is in fact FREE; then the sweeper cancels the
    booking anyway. The bride is told her time is gone while it is standing empty,
    and the owner is asked to phone her about it.

    Two things make it unreachable and BOTH are needed: D6 puts claim 1 and the
    booking cancel in ONE transaction, so the intermediate state is never
    observable; and D5 widens the rebind's `allowed_from` to
    `('cancelled','pending_payment')` as the belt for the case where it is.

    The forbidden conjunction is asserted directly. Capacity is 1 and nobody else
    ever books, so "the seat is free" is true by construction — which makes
    `paid + cancelled + alerted` a FALSE alert by definition and not a judgement
    call. Three independent rounds on three slots, because a window this narrow
    is not reliably hit once.
    """
    engine, rig = await _rig(app_role_url, hold_seconds=EXPIRED_HOLD_SECONDS, capacity=1)
    try:
        for hour in (9, 10, 11):
            slot = _at(hour)
            claim, session_id = await _hold(rig, starts_at=slot)

            await asyncio.gather(
                rig.sweeper.sweep(rig.tenant_id),
                rig.settle(session_id=session_id, transaction_id=f"txn-late-{hour}"),
            )

            booking = await _booking(rig, claim.booking.id)
            payment = await _payment_for(rig, claim.booking.id)
            assert not (
                payment.status == PaymentStatus.PAID.value
                and booking.status == BookingStatus.CANCELLED.value
            ), (
                f"row #13 at {slot}: paid deposit + cancelled booking while the "
                "seat is free is the false-alert outcome D6's single transaction "
                "and D5's widened allowed_from exist to make unreachable"
            )
            outcome = f"booking={booking.status} payment={payment.status} slot={slot}"
            assert booking.status == BookingStatus.CONFIRMED.value, outcome
            assert booking.starts_at == slot, outcome
            assert payment.status == PaymentStatus.PAID.value, outcome

        kinds = await _kinds(rig)
        assert MessageKind.PAYMENT_RECEIVED_NO_SLOT.value not in kinds, (
            "the owner was alerted about a seat nobody took"
        )
        assert kinds == [MessageKind.CONFIRMATION.value] * 3
        assert AuditAction.DEPOSIT_LATE_UNRESOLVED.value not in await _actions(rig)
    finally:
        await _purge(rig)
        await engine.dispose()


# --- the two BLOCKER recoveries --------------------------------------------


async def test_the_crash_window_is_repaired_exactly_once_by_concurrent_redeliveries(
    app_role_url: str,
) -> None:
    """**Race row #11**, the first of the review's two BLOCKER findings.

    `settle_from_webhook` commits `payments -> paid` inside its OWN
    `tenant_session` and returns a `Settlement`; the booking confirm is therefore
    necessarily a SECOND transaction. This test skips that second transaction
    entirely — the process died, the request was cancelled, the confirm raised —
    and asserts the state that leaves: card charged, seat held forever
    (`active_seats_at` counts a `pending_payment` row), no SMS, no reminder, and
    0009's index blocking her from rebooking her own instant.

    Then the provider retries, TWICE and at once, because a provider that never
    saw a response retries and its retries are not serialized for our benefit.
    The repair must still happen exactly once: one confirm, one SMS, one audit
    row, and the booking must have LEFT `pending_payment` — which is the whole
    claim, since the previous draft's D4 table ruled this row "do nothing".
    """
    engine, rig = await _rig(app_role_url, hold_seconds=LIVE_HOLD_SECONDS)
    try:
        claim, session_id = await _hold(rig)
        body, signature = _signed(session_id=session_id, transaction_id="txn-1")

        # The payments half ONLY. Not `deposits.settle` — that is the crash.
        settlement = await rig.payments.settle_from_webhook(
            rig.tenant_id, body=body, signature=signature
        )
        assert settlement.newly_settled is True
        stranded = await _booking(rig, claim.booking.id)
        assert stranded.status == BookingStatus.PENDING_PAYMENT.value
        assert await _kinds(rig) == []

        await asyncio.gather(
            rig.settle(session_id=session_id, transaction_id="txn-1"),
            rig.settle(session_id=session_id, transaction_id="txn-1"),
        )

        repaired = await _booking(rig, claim.booking.id)
        assert repaired.status == BookingStatus.CONFIRMED.value, (
            "the booking must have LEFT pending_payment — a paid deposit on a "
            "held seat with nothing acting on it is the window itself"
        )
        assert await _kinds(rig) == [MessageKind.CONFIRMATION.value]
        assert (await _actions(rig)).count(AuditAction.BOOKING_CONFIRMED.value) == 1
    finally:
        await _purge(rig)
        await engine.dispose()


async def test_an_orphaned_hold_is_swept_and_the_seat_really_goes_to_another_bride(
    app_role_url: str,
) -> None:
    """**Race row #12**, the second BLOCKER, and the one claim 1 structurally
    cannot see.

    `open_deposit` opens its own session and re-takes the advisory lock
    `create_booking` holds to COMMIT, so folding them is impossible — and
    everything between the two commits leaves a committed `pending_payment`
    booking with NO `payments` row at all. Claim 1 sweeps `payments` and finds
    nothing; every owner and customer verb 409s on an unpaid hold; so without
    claim 2 the seat is held forever and 0009's index also stops the bride
    rebooking her own instant.

    The seat being free is proved by an ACTUAL second create succeeding onto the
    same (starts_at, seat_index) — 0008's partial unique index excludes
    `cancelled`, so this is a DDL fact a status re-read could not establish.
    """
    engine, rig = await _rig(app_role_url, hold_seconds=LIVE_HOLD_SECONDS, capacity=1)
    try:
        phone = _phone()
        # The create commits and `open_deposit` never runs. That IS the crash.
        claim = await _create(rig, phone=phone, token=await _verified(rig, phone))
        assert claim.booking.status == BookingStatus.PENDING_PAYMENT.value
        assert await _has_payment(rig, claim.booking.id) is False

        # Inside the grace it is still claim 1's business, and claim 1 has
        # nothing to find — the seat is leaked until the grace passes.
        assert await rig.sweeper.sweep(rig.tenant_id) == SweepResult()

        await _age(
            rig,
            claim.booking.id,
            created_at=NOW - datetime.timedelta(seconds=SWEEP_HOLD_SECONDS + POLL_SECONDS + 1),
        )
        assert await rig.sweeper.sweep(rig.tenant_id) == SweepResult(orphaned=1)

        other = _phone()
        taken = await _create(rig, phone=other, token=await _verified(rig, other))
        assert taken.booking.seat_index == claim.booking.seat_index
        assert taken.booking.starts_at == claim.booking.starts_at
        assert taken.booking.status == BookingStatus.PENDING_PAYMENT.value
    finally:
        await _purge(rig)
        await engine.dispose()
