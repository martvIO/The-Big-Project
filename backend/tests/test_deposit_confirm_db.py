"""F19 Tasks 7 and 8 against real Postgres as the non-owner app role.

Two claims live here and neither is provable without the real engine, because
both are about what a guarded UPDATE's predicate matched:

1. **The confirm transaction is F19's idempotency key.** `set_status` guarded
   `allowed_from=('pending_payment',)` decides exactly-once under the row lock,
   and the interesting case is not the redelivery — it is the CRASH between
   `settle_from_webhook`'s transaction and this one, where a redelivery has to
   REPAIR a booking rather than no-op past it.
2. **The honour path buys back her seat or alerts, never a 500.** Both partial
   unique indexes are DDL, so a rebind that re-enters them can only be exercised
   for real; and `IntegrityError` reaching `main.py` on this path would be
   unrecoverable, because `settle_late` has already committed the transaction id
   and every provider retry then short-circuits.

`NullPool` + a fresh tenant per test, the `test_booking_comms_db.py` discipline.

**Every test purges its own tenant.** `bookings.status = 'pending_payment'` and
`bookings.cancelled_by = 'expired'` are values only F19's migration admits, so a
leaked row of either makes the migration's own down-revision fail and takes
seven unrelated round-trip tests with it. `payments` has DELETE revoked (0012),
so its rows stay — harmless, since 0012 already pinned every status they carry.

**On expiry.** These tests reach `payments.status = 'expired'` by writing it,
because D6's sweeper is a different task and is not in the tree yet. That is the
`test_payments_service.py:921` shortcut the spec's C6 amendment objects to — and
the objection is about the sweeper never being the thing under test, which is
true and is the sweeper's own test's job. Nothing below asserts anything about
how a hold expires; retarget `_expire_hold` at the sweeper once it lands.
"""

import datetime
import secrets
import uuid
from typing import Any

import pytest
from sqlalchemy import delete, select
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
from app.booking.service import BookingClaim, BookingService
from app.booking.tokens import manage_token_hash
from app.booking.validation import jerusalem_day_index
from app.db.repositories.appointment_types import AppointmentTypesRepository
from app.db.repositories.availability import AvailabilityRulesRepository
from app.db.repositories.bookings import BookingsRepository
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
    BookingStatus,
    MessageKind,
    PaymentStatus,
    ScheduledMessageKind,
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
from app.payments.webhook_router import DepositBookingService
from app.storefront.validation import BOUTIQUE_TIMEZONE

pytestmark = pytest.mark.db

SECRET = "webhook-secret-1"
GOOD = {"merchant_id": "m-1", "api_key": "k-1", "webhook_secret": SECRET}

TARGET_DATE = datetime.date(2026, 8, 23)
BASE_DOMAIN = "modryn.co.il"
RETURN_URL = "https://bella.modryn.co.il/book/return"
HOLD_SECONDS = 900
DEPOSIT_AGOROT = 30_000
# Deposits on, which is the toggle `deposit_due` reads first and the reason a
# `pending_payment` row exists at all.
SETTINGS: dict[str, object] = {"toggles": {"deposits_enabled": True}}


def _at(hour: int, minute: int = 0) -> datetime.datetime:
    return datetime.datetime.combine(
        TARGET_DATE, datetime.time(hour, minute), tzinfo=BOUTIQUE_TIMEZONE
    ).astimezone(datetime.UTC)


SLOT = _at(10, 0)
# Weeks out, so `reminder_send_after` takes the >=24h band and D12's bug does
# NOT fire — which is exactly what makes it the kind that ships green.
NOW = datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.UTC)
# Three hours before the slot: the 2-24h band, where the reminder is scheduled
# for `now` and the very next worker tick cancels it.
NEAR = SLOT - datetime.timedelta(hours=3)


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
    body = fake_webhook_body(
        provider_session_id=session_id,
        provider_transaction_id=transaction_id,
        amount_agorot=amount_agorot,
        paid=paid,
    )
    return body, sign_fake_webhook(webhook_secret=SECRET, body=body)


class _Rig:
    """Everything one test needs, built once from one factory."""

    # Filled by `_rig` after the seed, which needs a session the rig has to
    # exist to open.
    type_id: uuid.UUID

    def __init__(
        self,
        factory: async_sessionmaker[AsyncSession],
        tenant_id: uuid.UUID,
        *,
        now: datetime.datetime,
    ) -> None:
        self.factory = factory
        self.tenant_id = tenant_id
        self.now = now
        self.gateway = FakeGateway()
        self.sender = FakeSmsSender()
        self.credentials = GatewayCredentialService(
            factory,
            gateway=self.gateway,
            secret_box=FakeSecretBox(),
            connect_limiter=_loose(),
            validate_limiter=_loose(),
            clock=lambda: now,
        )
        self.payments = PaymentService(
            factory, gateway=self.gateway, credentials=self.credentials, clock=lambda: now
        )
        self.comms = BookingCommsService(
            factory,
            notifications=NotificationService(factory, sender=self.sender),
            base_domain=BASE_DOMAIN,
            clock=lambda: now,
        )
        self.deposits = DepositBookingService(
            factory,
            payments=self.payments,
            credentials=self.credentials,
            comms=self.comms,
            clock=lambda: now,
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
                clock=lambda: now,
            ),
            create_limiter=_loose(),
            phone_limiter=_loose(),
            clock=lambda: now,
            gateway_credentials=self.credentials,
            payments=self.payments,
            deposit_hold_seconds=HOLD_SECONDS,
        )

    async def settle(self, *, session_id: str, transaction_id: str, paid: bool = True) -> None:
        body, signature = _signed(session_id=session_id, transaction_id=transaction_id, paid=paid)
        await self.deposits.settle(_tenant(self.tenant_id), body=body, signature=signature)


async def _seed(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, *, capacity: int = 1
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


async def _verification(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, raw_phone: str
) -> str:
    token = secrets.token_urlsafe(16)
    repo = OtpCodesRepository()
    future = datetime.datetime(2099, 1, 1, tzinfo=datetime.UTC)
    async with tenant_session(factory, tenant_id) as session:
        row = await repo.insert(
            session,
            tenant_id=tenant_id,
            phone=normalize_israeli_mobile(raw_phone),
            code_hash="seed",
            expires_at=future,
        )
        await repo.mark_consumed(
            session,
            tenant_id,
            row.id,
            verification_token_hash=hash_token(token),
            verification_expires_at=future,
        )
    return token


async def _claim(
    rig: _Rig, *, starts_at: datetime.datetime = SLOT, phone: str | None = None
) -> BookingClaim:
    resolved = phone if phone is not None else _phone()
    return await rig.bookings.create_booking(
        rig.tenant_id,
        raw_phone=resolved,
        verification_token=await _verification(rig.factory, rig.tenant_id, resolved),
        name="נועה לוי",
        appointment_type_id=rig.type_id,
        starts_at=starts_at,
        terms_version=1,
        settings=SETTINGS,
    )


async def _hold(rig: _Rig, *, starts_at: datetime.datetime = SLOT, phone: str | None = None) -> Any:
    """A committed `pending_payment` booking with a live hold behind it, through
    the shipped writers — create then pay, which is D11's ordering."""
    claim = await _claim(rig, starts_at=starts_at, phone=phone)
    outcome = await rig.bookings.open_deposit(rig.tenant_id, claim, return_url=RETURN_URL)
    assert outcome.deposit_due is True, "the fixture must produce a real deposit hold"
    assert outcome.payment_session_id is not None
    return claim, outcome


# --- reads ------------------------------------------------------------------


async def _booking(rig: _Rig, booking_id: uuid.UUID) -> Booking:
    async with tenant_session(rig.factory, rig.tenant_id) as session:
        row = await BookingsRepository().by_id(session, rig.tenant_id, booking_id)
    assert row is not None
    return row


async def _payment(rig: _Rig, payment_id: uuid.UUID) -> Payment:
    async with tenant_session(rig.factory, rig.tenant_id) as session:
        row = await PaymentsRepository().by_id(session, rig.tenant_id, payment_id)
    assert row is not None
    return row


async def _payment_for(rig: _Rig, booking_id: uuid.UUID) -> Payment:
    async with tenant_session(rig.factory, rig.tenant_id) as session:
        rows = await PaymentsRepository().by_booking_ids(session, rig.tenant_id, [booking_id])
    assert booking_id in rows
    return rows[booking_id]


async def _kinds(rig: _Rig) -> list[str]:
    async with tenant_session(rig.factory, rig.tenant_id) as session:
        stmt = select(MessageLog.kind).order_by(MessageLog.created_at)
        return list((await session.execute(stmt)).scalars().all())


async def _actions(rig: _Rig) -> list[str]:
    async with tenant_session(rig.factory, rig.tenant_id) as session:
        stmt = select(AuditLog.action).order_by(AuditLog.created_at)
        return list((await session.execute(stmt)).scalars().all())


async def _pending_reminder(rig: _Rig, booking_id: uuid.UUID) -> Any:
    async with tenant_session(rig.factory, rig.tenant_id) as session:
        return await ScheduledMessagesRepository().pending_for_booking(
            session,
            rig.tenant_id,
            booking_id=booking_id,
            kind=ScheduledMessageKind.REMINDER.value,
        )


async def _expire_hold(rig: _Rig, *, booking_id: uuid.UUID, payment_id: uuid.UUID) -> None:
    """D6's sweeper's two writes, spelled by hand because the sweeper is a
    different task and is not in the tree yet: the hold expires and the seat is
    released with `cancelled_by = 'expired'` (MD5's attribution, which is what
    keeps an abandoned checkout out of the headline cancellation rate)."""
    async with tenant_session(rig.factory, rig.tenant_id) as session:
        payment = await PaymentsRepository().by_id(session, rig.tenant_id, payment_id)
        assert payment is not None
        payment.status = PaymentStatus.EXPIRED.value
        payment.redirect_url = None
        cancelled = await BookingsRepository().cancel(
            session,
            rig.tenant_id,
            booking_id,
            at=rig.now,
            by=BookingCancelledBy.EXPIRED.value,
            allowed_from=(BookingStatus.PENDING_PAYMENT.value,),
        )
        assert cancelled is not None


async def _purge(factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID) -> None:
    """MANDATORY, not tidiness. A leaked `pending_payment` or `cancelled_by =
    'expired'` row is only legal under F19's migration, so it makes that
    migration's own downgrade fail and takes the round-trip suite with it.
    `payments` is absent on purpose — 0012 revoked DELETE from app_user, and its
    statuses were already legal before this feature."""
    async with tenant_session(factory, tenant_id) as session:
        await session.execute(delete(MessageLog).where(MessageLog.tenant_id == tenant_id))
        await session.execute(delete(Booking).where(Booking.tenant_id == tenant_id))
        await session.execute(delete(Customer).where(Customer.tenant_id == tenant_id))
        await session.execute(delete(AuditLog).where(AuditLog.tenant_id == tenant_id))


async def _rig(url: str, *, capacity: int = 1, now: datetime.datetime = NOW) -> Any:
    engine, factory = _factory(url)
    tenant_id = uuid.uuid4()
    rig = _Rig(factory, tenant_id, now=now)
    await rig.credentials.connect(tenant_id, fields=GOOD, actor_id=uuid.uuid4())
    rig.type_id = await _seed(factory, tenant_id, capacity=capacity)
    return engine, rig


# --- Task 7: the confirm transaction ----------------------------------------


async def test_a_paid_webhook_confirms_the_booking_and_texts_her_once(app_role_url: str) -> None:
    engine, rig = await _rig(app_role_url)
    try:
        claim, outcome = await _hold(rig)
        assert claim.booking.status == BookingStatus.PENDING_PAYMENT.value

        await rig.settle(session_id=outcome.payment_session_id, transaction_id="txn-1")

        row = await _booking(rig, claim.booking.id)
        assert row.status == BookingStatus.CONFIRMED.value
        payment = await _payment_for(rig, claim.booking.id)
        assert payment.status == PaymentStatus.PAID.value
        assert payment.paid_at is not None
        # D8: a live checkout URL must not outlive its hold.
        assert payment.redirect_url is None

        # Exactly one confirmation, and it is the ONLY message so far — the
        # create path suppressed its own on the deposit branch.
        assert await _kinds(rig) == [MessageKind.CONFIRMATION.value]
        assert AuditAction.BOOKING_CONFIRMED.value in await _actions(rig)
    finally:
        await _purge(rig.factory, rig.tenant_id)
        await engine.dispose()


async def test_the_reminder_is_rewritten_and_points_at_the_new_token(app_role_url: str) -> None:
    """D12 and D13 together. The token on the row must be the one whose sha256
    is now on `bookings` — `manage_token_hash` is one-way, so a confirmation
    deferred to webhook time cannot reuse the create-time token, and a reminder
    still carrying the old one would text her a link that no longer resolves."""
    engine, rig = await _rig(app_role_url)
    try:
        claim, outcome = await _hold(rig)
        await rig.settle(session_id=outcome.payment_session_id, transaction_id="txn-1")

        row = await _booking(rig, claim.booking.id)
        pending = await _pending_reminder(rig, claim.booking.id)
        assert pending is not None
        assert pending.manage_token is not None
        assert row.manage_token_hash == manage_token_hash(pending.manage_token)
        assert pending.manage_token != claim.manage_token
        assert pending.send_after == SLOT - datetime.timedelta(seconds=86_400)
    finally:
        await _purge(rig.factory, rig.tenant_id)
        await engine.dispose()


async def test_the_two_to_twenty_four_hour_reminder_survives_the_wait(app_role_url: str) -> None:
    """D12's bug, end to end, and it has no other symptom.

    `create_booking` ALWAYS inserts the reminder row regardless of status, and
    `reminder_send_after` returns `now` for any lead between 2h and 24h. So a
    bride booking three hours out gets a reminder scheduled for immediately, and
    the very next worker tick — long before she has finished paying — sees
    `status != 'confirmed'` and cancels it permanently. Without the rewrite she
    pays, gets confirmed, and silently never gets a reminder.
    """
    engine, rig = await _rig(app_role_url, now=NEAR)
    try:
        claim, outcome = await _hold(rig)
        booked = await _pending_reminder(rig, claim.booking.id)
        assert booked is not None
        assert booked.send_after == NEAR  # immediate — the whole problem

        # The worker tick that lands while she is still on the hosted page.
        drained = await rig.comms.drain_due(_tenant(rig.tenant_id))
        assert drained.cancelled == 1
        assert await _pending_reminder(rig, claim.booking.id) is None

        await rig.settle(session_id=outcome.payment_session_id, transaction_id="txn-1")

        revived = await _pending_reminder(rig, claim.booking.id)
        assert revived is not None
        assert revived.send_after == NEAR
        row = await _booking(rig, claim.booking.id)
        assert row.manage_token_hash == manage_token_hash(revived.manage_token or "")
    finally:
        await _purge(rig.factory, rig.tenant_id)
        await engine.dispose()


async def test_a_redelivery_confirms_once_and_texts_once(app_role_url: str) -> None:
    """Exactly-once is the UPDATE's predicate evaluated by Postgres under the row
    lock, not our bookkeeping — so the second delivery finds nothing to match and
    writes no SMS, no reminder rewrite and no audit row."""
    engine, rig = await _rig(app_role_url)
    try:
        claim, outcome = await _hold(rig)
        await rig.settle(session_id=outcome.payment_session_id, transaction_id="txn-1")
        first = await _pending_reminder(rig, claim.booking.id)

        await rig.settle(session_id=outcome.payment_session_id, transaction_id="txn-1")

        assert await _kinds(rig) == [MessageKind.CONFIRMATION.value]
        actions = await _actions(rig)
        assert actions.count(AuditAction.BOOKING_CONFIRMED.value) == 1
        again = await _pending_reminder(rig, claim.booking.id)
        assert again is not None and first is not None
        assert again.id == first.id
        assert again.manage_token == first.manage_token
    finally:
        await _purge(rig.factory, rig.tenant_id)
        await engine.dispose()


async def test_a_redelivery_repairs_a_booking_the_crash_window_stranded(
    app_role_url: str,
) -> None:
    """Race row #11, and the reason `newly_settled=False` + `paid` is not "do
    nothing".

    `settle_from_webhook` commits `payments -> paid` inside its OWN transaction
    and returns, so the booking-confirm is necessarily a SECOND one. This test
    skips that second transaction entirely — the process died, the request was
    cancelled, the confirm raised — and asserts the state that leaves: card
    charged, seat held forever, no SMS, no reminder, and 0009's index blocking
    her from rebooking. Then it redelivers, and asserts the repair happened
    exactly once.
    """
    engine, rig = await _rig(app_role_url)
    try:
        claim, outcome = await _hold(rig)
        body, signature = _signed(session_id=outcome.payment_session_id, transaction_id="txn-1")

        # The payments half only. NOT deposits.settle — that is the crash.
        settlement = await rig.payments.settle_from_webhook(
            rig.tenant_id, body=body, signature=signature
        )
        assert settlement.newly_settled is True
        stranded = await _booking(rig, claim.booking.id)
        assert stranded.status == BookingStatus.PENDING_PAYMENT.value
        assert await _kinds(rig) == []

        # The provider retries, as every provider does against a request whose
        # response it never saw.
        await rig.settle(session_id=outcome.payment_session_id, transaction_id="txn-1")

        repaired = await _booking(rig, claim.booking.id)
        assert repaired.status == BookingStatus.CONFIRMED.value
        assert await _kinds(rig) == [MessageKind.CONFIRMATION.value]
        assert (await _actions(rig)).count(AuditAction.BOOKING_CONFIRMED.value) == 1
        assert await _pending_reminder(rig, claim.booking.id) is not None
    finally:
        await _purge(rig.factory, rig.tenant_id)
        await engine.dispose()


async def test_a_decline_leaves_the_hold_pending_and_sends_nothing(app_role_url: str) -> None:
    """`paid=false` is the ordinary decline every PSP posts to the SAME url as
    its successes. The booking stays `pending_payment` and the seat stays held —
    the sweeper frees it on its own clock, and a retried card can still settle
    the same hold."""
    engine, rig = await _rig(app_role_url)
    try:
        claim, outcome = await _hold(rig)
        await rig.settle(session_id=outcome.payment_session_id, transaction_id="txn-1", paid=False)

        row = await _booking(rig, claim.booking.id)
        assert row.status == BookingStatus.PENDING_PAYMENT.value
        payment = await _payment_for(rig, claim.booking.id)
        assert payment.status == PaymentStatus.PENDING.value
        assert await _kinds(rig) == []
        assert AuditAction.BOOKING_CONFIRMED.value not in await _actions(rig)
    finally:
        await _purge(rig.factory, rig.tenant_id)
        await engine.dispose()


# --- Task 8: the honour path ------------------------------------------------


async def test_a_late_settlement_rebinds_her_when_the_seat_is_free(app_role_url: str) -> None:
    """D5 step 3, and the cancel-evidence assertion is the one that fails if the
    rebind forgets MD1's property 2: a row reading `confirmed` while still
    carrying `cancelled_at`/`cancelled_by` is the exact defect `set_status` was
    declined over, and both columns feed F52's attribution and F20's compliance
    read."""
    engine, rig = await _rig(app_role_url)
    try:
        claim, outcome = await _hold(rig)
        payment = await _payment_for(rig, claim.booking.id)
        await _expire_hold(rig, booking_id=claim.booking.id, payment_id=payment.id)

        await rig.settle(session_id=outcome.payment_session_id, transaction_id="txn-late")

        row = await _booking(rig, claim.booking.id)
        assert row.status == BookingStatus.CONFIRMED.value
        assert row.starts_at == SLOT  # a late payment buys back HER time or nothing
        assert row.seat_index == claim.booking.seat_index
        assert row.cancelled_at is None
        assert row.cancelled_by is None

        settled = await _payment(rig, payment.id)
        assert settled.status == PaymentStatus.PAID.value
        assert settled.provider_transaction_id == "txn-late"

        assert await _kinds(rig) == [MessageKind.CONFIRMATION.value]
        actions = await _actions(rig)
        assert AuditAction.DEPOSIT_LATE_HONOURED.value in actions
        assert AuditAction.DEPOSIT_LATE_UNRESOLVED.value not in actions
        assert await _pending_reminder(rig, claim.booking.id) is not None
    finally:
        await _purge(rig.factory, rig.tenant_id)
        await engine.dispose()


async def test_a_late_settlement_alerts_her_when_the_seat_is_gone(app_role_url: str) -> None:
    """D5 step 4 plus MD2. The booking stays cancelled, the payment stays paid,
    and she is told within a worker tick — the only path in the flow where a
    customer's money moved and nothing else would tell her."""
    engine, rig = await _rig(app_role_url)
    try:
        claim, outcome = await _hold(rig)
        payment = await _payment_for(rig, claim.booking.id)
        await _expire_hold(rig, booking_id=claim.booking.id, payment_id=payment.id)

        # Capacity 1, and the freed seat goes to somebody else.
        other, _ = await _hold(rig)
        assert other.booking.seat_index == claim.booking.seat_index

        await rig.settle(session_id=outcome.payment_session_id, transaction_id="txn-late")

        row = await _booking(rig, claim.booking.id)
        assert row.status == BookingStatus.CANCELLED.value
        assert row.cancelled_by == BookingCancelledBy.EXPIRED.value
        settled = await _payment(rig, payment.id)
        assert settled.status == PaymentStatus.PAID.value

        assert await _kinds(rig) == [MessageKind.PAYMENT_RECEIVED_NO_SLOT.value]
        actions = await _actions(rig)
        assert AuditAction.DEPOSIT_LATE_UNRESOLVED.value in actions
        assert AuditAction.DEPOSIT_LATE_HONOURED.value not in actions
    finally:
        await _purge(rig.factory, rig.tenant_id)
        await engine.dispose()


async def test_a_late_settlement_refuses_a_past_appointment(app_role_url: str) -> None:
    """`not_before`. The provider's retry budget against a 15-minute hold is
    unknowable until a real PSP exists, so a delivery days late is not a
    hypothetical: without the bound it would flip a PAST booking to `confirmed`,
    mint a fresh manage token, and text her that an appointment which has already
    happened is confirmed."""
    engine, rig = await _rig(app_role_url)
    try:
        claim, outcome = await _hold(rig)
        payment = await _payment_for(rig, claim.booking.id)
        await _expire_hold(rig, booking_id=claim.booking.id, payment_id=payment.id)

        # The same rig, its clock moved past the appointment. Only the honour
        # path's reads and the guarded UPDATE consult it.
        rig.deposits._clock = lambda: SLOT + datetime.timedelta(hours=1)  # noqa: SLF001

        await rig.settle(session_id=outcome.payment_session_id, transaction_id="txn-late")

        row = await _booking(rig, claim.booking.id)
        assert row.status == BookingStatus.CANCELLED.value
        assert await _kinds(rig) == [MessageKind.PAYMENT_RECEIVED_NO_SLOT.value]
        assert AuditAction.DEPOSIT_LATE_UNRESOLVED.value in await _actions(rig)
    finally:
        await _purge(rig.factory, rig.tenant_id)
        await engine.dispose()


async def test_a_late_settlement_refuses_when_she_already_rebooked_that_instant(
    app_role_url: str,
) -> None:
    """Race row #15, and 0009's index is what makes it real: reinstating the
    cancelled row while her own new booking stands would make two live rows for
    (tenant, customer, starts_at). ONE DEPOSIT MUST NOT BUY TWO LIVE
    APPOINTMENTS — and the failure mode this replaces is a 500, which on this
    path is unrecoverable because `settle_late` already committed the
    transaction id."""
    engine, rig = await _rig(app_role_url, capacity=2)
    try:
        phone = _phone()
        claim, outcome = await _hold(rig, phone=phone)
        payment = await _payment_for(rig, claim.booking.id)
        await _expire_hold(rig, booking_id=claim.booking.id, payment_id=payment.id)

        # She rebooks the very same time herself — the ordinary consequence of
        # her seat being freed, and what 0009's own comment describes.
        rebooked, _ = await _hold(rig, phone=phone)
        assert rebooked.booking.id != claim.booking.id

        await rig.settle(session_id=outcome.payment_session_id, transaction_id="txn-late")

        row = await _booking(rig, claim.booking.id)
        assert row.status == BookingStatus.CANCELLED.value
        assert (await _payment(rig, payment.id)).status == PaymentStatus.PAID.value
        assert MessageKind.PAYMENT_RECEIVED_NO_SLOT.value in await _kinds(rig)
        assert AuditAction.DEPOSIT_LATE_UNRESOLVED.value in await _actions(rig)

        async with tenant_session(rig.factory, rig.tenant_id) as session:
            live = await BookingsRepository().active_at(
                session,
                rig.tenant_id,
                customer_id=claim.booking.customer_id,
                starts_at=SLOT,
            )
        assert live is not None and live.id == rebooked.booking.id
    finally:
        await _purge(rig.factory, rig.tenant_id)
        await engine.dispose()


async def test_a_second_late_delivery_neither_rebinds_nor_texts_again(app_role_url: str) -> None:
    """`settle_late` is guarded `WHERE status='expired'`, and writing the
    transaction id re-arms `by_provider_transaction_id` — so the redelivery
    short-circuits inside `settle_from_webhook` and the honour path is never
    re-entered. `None` back from `honour_late_settlement` is the belt for the
    concurrent case."""
    engine, rig = await _rig(app_role_url)
    try:
        claim, outcome = await _hold(rig)
        payment = await _payment_for(rig, claim.booking.id)
        await _expire_hold(rig, booking_id=claim.booking.id, payment_id=payment.id)

        await rig.settle(session_id=outcome.payment_session_id, transaction_id="txn-late")
        await rig.settle(session_id=outcome.payment_session_id, transaction_id="txn-late")

        assert await _kinds(rig) == [MessageKind.CONFIRMATION.value]
        actions = await _actions(rig)
        assert actions.count(AuditAction.DEPOSIT_LATE_HONOURED.value) == 1
        assert AuditAction.DEPOSIT_LATE_UNRESOLVED.value not in actions
    finally:
        await _purge(rig.factory, rig.tenant_id)
        await engine.dispose()


# --- the poll ---------------------------------------------------------------


async def test_the_poll_answers_the_four_facts_across_the_transition(app_role_url: str) -> None:
    engine, rig = await _rig(app_role_url)
    try:
        claim, outcome = await _hold(rig)
        before = await rig.deposits.payment_status(
            rig.tenant_id, provider_session_id=outcome.payment_session_id
        )
        assert before.booking_status == BookingStatus.PENDING_PAYMENT.value
        assert before.payment_status == PaymentStatus.PENDING.value
        assert before.paid_at is None
        # An untouched hold and a declined one share a status; only this field
        # tells them apart, so it has to be False here for it to mean anything
        # when it is True below.
        assert before.declined is False

        await rig.settle(session_id=outcome.payment_session_id, transaction_id="txn-1")

        after = await rig.deposits.payment_status(
            rig.tenant_id, provider_session_id=outcome.payment_session_id
        )
        assert after.booking_status == BookingStatus.CONFIRMED.value
        assert after.payment_status == PaymentStatus.PAID.value
        assert after.paid_at is not None
        assert after.declined is False
        assert claim.booking.id is not None
    finally:
        await _purge(rig.factory, rig.tenant_id)
        await engine.dispose()


async def test_the_poll_reports_a_decline_the_status_column_cannot_report(
    app_role_url: str,
) -> None:
    """The whole path, because the halves prove nothing apart: `_record_decline`
    writes `DECLINE_ERROR` and leaves the status at 'pending', and this is the
    read that turns that column back into the return page's declined screen. A
    fast test can pin either end; only the real engine proves the string survives
    the round trip and that the hold is still hers to retry when it does."""
    engine, rig = await _rig(app_role_url)
    try:
        claim, outcome = await _hold(rig)
        await rig.settle(session_id=outcome.payment_session_id, transaction_id="txn-1", paid=False)

        facts = await rig.deposits.payment_status(
            rig.tenant_id, provider_session_id=outcome.payment_session_id
        )
        assert facts.declined is True
        # The seat is STILL HERS: the screen may offer the same checkout link,
        # and a retried card settles this very hold rather than a second one.
        assert facts.booking_status == BookingStatus.PENDING_PAYMENT.value
        assert facts.payment_status == PaymentStatus.PENDING.value
        assert facts.paid_at is None
        assert claim.booking.id is not None

        # And it stops being a decline the moment the retry lands, without any
        # writer clearing `error`.
        await rig.settle(session_id=outcome.payment_session_id, transaction_id="txn-2")
        retried = await rig.deposits.payment_status(
            rig.tenant_id, provider_session_id=outcome.payment_session_id
        )
        assert retried.declined is False
        assert retried.payment_status == PaymentStatus.PAID.value
    finally:
        await _purge(rig.factory, rig.tenant_id)
        await engine.dispose()
