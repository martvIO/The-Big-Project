"""F19 D11/D11a/D11b against real Postgres: the create that owes a deposit, the
hold it opens, and MD4's compensating transaction when the provider is down.

CI-only, like every `db` file here — no Docker on the dev machine. The three
things that cannot be proved without a database are exactly the three things
this file exists for: that the claim really commits as `pending_payment`, that
the compensating transition really writes `confirmed` PLUS A5's `failed`
payments row PLUS MD4's audit row in one transaction, and that a replay
converges onto the FIRST hold instead of minting a second payable page.

Every test hard-deletes its bookings afterwards. Leaked `pending_payment` rows
took out seven unrelated migration round-trip tests earlier in this build —
0015's downgrade now cleans them, but a test that needs the downgrade to cover
for it is a test that will take something else out next time.
"""

import datetime
import secrets
import time
import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.tokens import hash_token
from app.booking.service import BookingClaim, BookingService
from app.booking.validation import jerusalem_day_index
from app.db.repositories.appointment_types import AppointmentTypesRepository
from app.db.repositories.availability import AvailabilityRulesRepository
from app.db.repositories.bookings import BookingsRepository
from app.db.repositories.otp_codes import OtpCodesRepository
from app.db.repositories.payments import GATEWAY_UNAVAILABLE_ERROR
from app.db.repositories.terms import TermsVersionsRepository
from app.db.tenant import tenant_session
from app.models.audit_log import AuditLog
from app.models.constants import (
    AppointmentAudience,
    AuditAction,
    BookingStatus,
    PaymentStatus,
)
from app.models.payment import Payment
from app.notifications.service import NotificationService, OtpService
from app.notifications.unconfigured import UnconfiguredSmsSender
from app.notifications.validation import normalize_israeli_mobile
from app.payments.base import GatewayCredentials, GatewayUnavailableError, PaymentSession
from app.payments.fake import FakeGateway
from app.payments.secretbox import FakeSecretBox
from app.payments.service import GatewayCredentialService, PaymentService
from app.storefront.validation import BOUTIQUE_TIMEZONE

pytestmark = pytest.mark.db

NOW = datetime.datetime(2026, 7, 28, 12, 0, tzinfo=datetime.UTC)
FUTURE = datetime.datetime(2099, 1, 1, tzinfo=datetime.UTC)
TARGET_DATE = datetime.date(2026, 8, 23)
DEPOSIT_AGOROT = 15_000
HOLD_SECONDS = 900
RETURN_URL = "https://bella.localtest.me/"
CREDENTIALS = {"merchant_id": "m-1", "api_key": "k-1", "webhook_secret": "wh-1"}
# D19's master toggle, on. Absent reads as OFF, which is why every test here
# passes it explicitly rather than relying on a seeded tenants row.
DEPOSITS_ON: dict[str, object] = {"toggles": {"deposits_enabled": True}}

SLOT = datetime.datetime.combine(
    TARGET_DATE, datetime.time(10, 0), tzinfo=BOUTIQUE_TIMEZONE
).astimezone(datetime.UTC)


def _factory(app_role_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(app_role_url, poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _limiter() -> FixedWindowRateLimiter:
    return FixedWindowRateLimiter(max_attempts=10_000, window_seconds=3600, clock=time.monotonic)


def _phone() -> str:
    return f"+9725{uuid.uuid4().int % 10**8:08d}"


class _DownGateway(FakeGateway):
    """Connected, valid credentials, and unreachable at the moment of checkout —
    MD4's exact situation, and the one D19's predicate cannot see coming."""

    async def create_session(
        self,
        credentials: GatewayCredentials,
        *,
        amount_agorot: int,
        reference: str,
        return_url: str,
        expires_in: int,
    ) -> PaymentSession:
        raise GatewayUnavailableError


async def _service(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    *,
    gateway: FakeGateway,
) -> BookingService:
    credentials = GatewayCredentialService(
        factory,
        gateway=gateway,
        secret_box=FakeSecretBox(),
        connect_limiter=_limiter(),
        validate_limiter=_limiter(),
        clock=lambda: NOW,
    )
    await credentials.connect(tenant_id, fields=CREDENTIALS, actor_id=uuid.uuid4())
    otp = OtpService(
        factory,
        notifications=NotificationService(factory, sender=UnconfiguredSmsSender()),
        phone_limiter=_limiter(),
        tenant_limiter=_limiter(),
        verify_limiter=_limiter(),
        ip_limiter=_limiter(),
        clock=lambda: NOW,
    )
    return BookingService(
        factory,
        otp=otp,
        create_limiter=_limiter(),
        phone_limiter=_limiter(),
        clock=lambda: NOW,
        gateway_credentials=credentials,
        payments=PaymentService(
            factory, gateway=gateway, credentials=credentials, clock=lambda: NOW
        ),
        deposit_hold_seconds=HOLD_SECONDS,
    )


async def _seed(factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID) -> uuid.UUID:
    """One open day, one DEPOSIT-REQUIRED type, terms v1."""
    async with tenant_session(factory, tenant_id) as session:
        await AvailabilityRulesRepository().insert(
            session,
            tenant_id=tenant_id,
            day_of_week=jerusalem_day_index(TARGET_DATE),
            open_time=datetime.time(9, 0),
            close_time=datetime.time(13, 0),
            capacity=2,
        )
        type_row = await AppointmentTypesRepository().insert(
            session,
            tenant_id=tenant_id,
            name="מדידת שמלה",
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


async def _verified_token(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, phone: str
) -> str:
    token = secrets.token_urlsafe(16)
    repo = OtpCodesRepository()
    async with tenant_session(factory, tenant_id) as session:
        row = await repo.insert(
            session,
            tenant_id=tenant_id,
            phone=normalize_israeli_mobile(phone),
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
    service: BookingService,
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    type_id: uuid.UUID,
    phone: str,
) -> BookingClaim:
    return await service.create_booking(
        tenant_id,
        raw_phone=phone,
        verification_token=await _verified_token(factory, tenant_id, phone),
        name="נועה לוי",
        appointment_type_id=type_id,
        starts_at=SLOT,
        terms_version=1,
        settings=DEPOSITS_ON,
    )


async def _payments(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID
) -> list[Payment]:
    async with tenant_session(factory, tenant_id) as session:
        stmt = select(Payment).order_by(Payment.created_at)
        return list((await session.execute(stmt)).scalars().all())


async def _actions(factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID) -> list[str]:
    async with tenant_session(factory, tenant_id) as session:
        stmt = select(AuditLog.action).order_by(AuditLog.created_at)
        return list((await session.execute(stmt)).scalars().all())


async def _drop_bookings(factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID) -> None:
    """Hard delete, and bare because RLS already scopes the statement to this
    tenant. A leaked `pending_payment` row is not this test's problem to leave
    for the migration suite to trip over."""
    async with tenant_session(factory, tenant_id) as session:
        await session.execute(text("DELETE FROM scheduled_messages"))
        await session.execute(text("DELETE FROM bookings"))


async def test_a_deposit_claim_commits_pending_payment_and_opens_one_hold(
    app_role_url: str,
) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id, phone = uuid.uuid4(), _phone()
    gateway = FakeGateway()
    try:
        type_id = await _seed(factory, tenant_id)
        service = await _service(factory, tenant_id, gateway=gateway)
        claim = await _claim(service, factory, tenant_id, type_id, phone)

        assert claim.created is True
        assert claim.deposit_due is True
        assert claim.deposit_amount_agorot == DEPOSIT_AGOROT
        # D11: committed BEFORE a single agora is taken, and the seat is held
        # from that instant — every occupancy predicate excludes only cancelled.
        assert claim.booking.status == BookingStatus.PENDING_PAYMENT.value

        outcome = await service.open_deposit(tenant_id, claim, return_url=RETURN_URL)
        assert outcome.deposit_due is True
        assert outcome.status == BookingStatus.PENDING_PAYMENT.value
        assert outcome.redirect_url is not None
        assert outcome.payment_session_id is not None

        [payment] = await _payments(factory, tenant_id)
        assert payment.status == PaymentStatus.PENDING.value
        assert payment.amount_agorot == DEPOSIT_AGOROT
        assert payment.booking_id == claim.booking.id
        assert payment.hold_expires_at == NOW + datetime.timedelta(seconds=HOLD_SECONDS)
        assert len(gateway.sessions) == 1
    finally:
        await _drop_bookings(factory, tenant_id)
        await engine.dispose()


async def test_the_replay_branch_converges_onto_the_first_hold(app_role_url: str) -> None:
    """D11b. The lost-201 retry re-enters through 0009's replay path — same
    booking, no raw token — and `open_deposit` must converge: the SAME hosted
    page, no second gateway call. Two payable pages for one appointment is the
    bug this ordering exists to prevent."""
    engine, factory = _factory(app_role_url)
    tenant_id, phone = uuid.uuid4(), _phone()
    gateway = FakeGateway()
    try:
        type_id = await _seed(factory, tenant_id)
        service = await _service(factory, tenant_id, gateway=gateway)
        first = await _claim(service, factory, tenant_id, type_id, phone)
        opened = await service.open_deposit(tenant_id, first, return_url=RETURN_URL)

        replay = await _claim(service, factory, tenant_id, type_id, phone)
        assert replay.created is False
        assert replay.booking.id == first.booking.id
        assert replay.deposit_due is True

        converged = await service.open_deposit(tenant_id, replay, return_url=RETURN_URL)
        assert converged.redirect_url == opened.redirect_url
        assert converged.payment_session_id == opened.payment_session_id
        assert len(gateway.sessions) == 1
        assert len(await _payments(factory, tenant_id)) == 1
    finally:
        await _drop_bookings(factory, tenant_id)
        await engine.dispose()


async def test_md4_an_unreachable_gateway_books_her_anyway_and_marks_the_row(
    app_role_url: str,
) -> None:
    """MD4 via D11a, and A5's marker is the half with no other failing test.

    Without the compensating transaction the seat is held forever: nothing but
    the sweeper can move a row out of `pending_payment`, and the sweeper reads
    `payments` — where `open_deposit` wrote nothing, because it raised before
    the insert. Without A5's row the booking is byte-identical to an ordinary
    non-deposit one on the single field the owner console reads.
    """
    engine, factory = _factory(app_role_url)
    tenant_id, phone = uuid.uuid4(), _phone()
    try:
        type_id = await _seed(factory, tenant_id)
        service = await _service(factory, tenant_id, gateway=_DownGateway())
        claim = await _claim(service, factory, tenant_id, type_id, phone)
        assert claim.booking.status == BookingStatus.PENDING_PAYMENT.value

        outcome = await service.open_deposit(tenant_id, claim, return_url=RETURN_URL)

        # The appointment stands, with no deposit taken and nowhere to pay.
        assert outcome.deposit_due is False
        assert outcome.status == BookingStatus.CONFIRMED.value
        assert (outcome.redirect_url, outcome.payment_session_id) == (None, None)

        async with tenant_session(factory, tenant_id) as session:
            row = await BookingsRepository().by_id(session, tenant_id, claim.booking.id)
        assert row is not None
        assert row.status == BookingStatus.CONFIRMED.value

        # A5: the marker. `failed` had no writer before this path existed.
        [payment] = await _payments(factory, tenant_id)
        assert payment.status == PaymentStatus.FAILED.value
        assert payment.error == GATEWAY_UNAVAILABLE_ERROR
        assert payment.amount_agorot == DEPOSIT_AGOROT
        assert payment.booking_id == claim.booking.id
        # Nothing was ever minted at the provider, so nothing pretends otherwise.
        assert payment.provider_session_id is None
        assert payment.redirect_url is None
        assert payment.hold_expires_at is None

        assert AuditAction.GATEWAY_UNAVAILABLE_AT_CHECKOUT.value in await _actions(
            factory, tenant_id
        )
    finally:
        await _drop_bookings(factory, tenant_id)
        await engine.dispose()
