"""F16 against real Postgres as the non-owner app role.

Four claims live here and nowhere else, because none of them is provable without
the real engine:

1. **The poller's claim is safe under two concurrent workers** — `FOR UPDATE SKIP
   LOCKED` is a Postgres behaviour, and a fake would assert the mock.
2. **The pending-unique partial index converges a double-schedule** — the
   idempotency key is DDL, not code.
3. **A cancel frees the seat** — both partial unique indexes exclude
   `status = 'cancelled'`, so the freed time genuinely becomes rebookable.
4. **The failure semantics leave exactly the right evidence** — a refused send
   leaves a `failed` `message_log` row and a 201's worth of booking; an
   unconfigured deployment leaves NO row at all, which is F11's deliberate
   design and the thing the copy has to be honest about.

NullPool + asyncio.gather gives every racer its own connection (the
test_booking_service precedent), which is what makes the concurrency test real.
"""

import asyncio
import datetime
import secrets
import uuid
from typing import Any

import pytest
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.tokens import hash_token
from app.booking.backfill import BackfillResult, ManageLinkBackfill
from app.booking.comms import BookingCommsService, CommsTenant
from app.booking.comms_templates import MASKED_TOKEN
from app.booking.manage import (
    BookingAlreadyStartedError,
    BookingCancelledError,
    BookingLinkInvalidError,
    BookingLookupThrottledError,
    ManageBookingService,
    ManageTenant,
)
from app.booking.service import BookingService, SlotUnavailableError
from app.booking.tokens import manage_token_hash, mint_manage_token
from app.booking.validation import jerusalem_day_index
from app.db.repositories.appointment_types import AppointmentTypesRepository
from app.db.repositories.availability import AvailabilityRulesRepository
from app.db.repositories.bookings import BookingsRepository
from app.db.repositories.message_log import MessageLogRepository
from app.db.repositories.otp_codes import OtpCodesRepository
from app.db.repositories.scheduled_messages import ScheduledMessagesRepository
from app.db.repositories.terms import TermsVersionsRepository
from app.db.tenant import tenant_session
from app.models.constants import (
    AppointmentAudience,
    BookingStatus,
    MessageKind,
    MessageStatus,
    ScheduledMessageKind,
    ScheduledMessageStatus,
)
from app.models.tenant import Tenant
from app.notifications.base import SendResult, SmsSendError
from app.notifications.fake import FakeSmsSender
from app.notifications.service import NotificationService, OtpService
from app.notifications.unconfigured import UnconfiguredSmsSender
from app.notifications.validation import normalize_israeli_mobile
from app.storefront.validation import BOUTIQUE_TIMEZONE

pytestmark = pytest.mark.db

NOW = datetime.datetime(2026, 7, 28, 12, 0, tzinfo=datetime.UTC)
FUTURE = datetime.datetime(2099, 1, 1, tzinfo=datetime.UTC)
TARGET_DATE = datetime.date(2026, 8, 23)
BASE_DOMAIN = "modryn.co.il"
REMINDER = ScheduledMessageKind.REMINDER.value


def _slot(hour: int, minute: int = 0) -> datetime.datetime:
    return datetime.datetime.combine(
        TARGET_DATE, datetime.time(hour, minute), tzinfo=BOUTIQUE_TIMEZONE
    ).astimezone(datetime.UTC)


SLOT = _slot(10, 0)


class RefusingSender:
    """A CONFIGURED provider that refuses. The distinction from
    UnconfiguredSmsSender is the whole point of the evidence tests below."""

    @property
    def is_configured(self) -> bool:
        return True

    async def send(self, *, phone: str, body: str) -> SendResult:
        raise SmsSendError("provider said no")


def _factory(url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(url, poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _phone() -> str:
    return f"+9725{uuid.uuid4().int % 10**8:08d}"


def _loose() -> FixedWindowRateLimiter:
    return FixedWindowRateLimiter(max_attempts=10_000, window_seconds=3600, clock=lambda: 0.0)


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
        factory,
        otp=otp,
        create_limiter=_loose(),
        phone_limiter=_loose(),
        clock=lambda: now,
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


def _manage(
    factory: async_sessionmaker[AsyncSession],
    *,
    now: datetime.datetime = NOW,
    limiter: FixedWindowRateLimiter | None = None,
) -> ManageBookingService:
    return ManageBookingService(
        factory,
        lookup_limiter=limiter if limiter is not None else _loose(),
        clock=lambda: now,
    )


def _tenant(tenant_id: uuid.UUID) -> CommsTenant:
    return CommsTenant(id=tenant_id, slug="bella", name="בלה כלות", phone="052-1234567")


def _manage_tenant(tenant_id: uuid.UUID) -> ManageTenant:
    return ManageTenant(
        id=tenant_id,
        name="בלה כלות",
        settings={"profile": {"phone": "052-1234567", "address": "דיזנגוף 99", "maps_url": ""}},
    )


async def _seed(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    *,
    capacity: int = 1,
    refundable_hours: int = 48,
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
            deposit_required=False,
            deposit_amount_agorot=None,
            sort_order=0,
        )
        await TermsVersionsRepository().insert(
            session,
            tenant_id=tenant_id,
            version=1,
            terms_text="תנאי ביטול",
            refundable_until_hours_before=refundable_hours,
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
    starts_at: datetime.datetime = SLOT,
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


# --- the claim writes the token hash and the reminder, in one transaction ---


async def test_a_claim_stores_only_the_token_hash_and_schedules_the_reminder(
    app_role_url: str,
) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(factory, tenant_id, type_id)

        assert claim.created is True
        assert claim.manage_token is not None
        async with tenant_session(factory, tenant_id) as session:
            row = await BookingsRepository().by_id(session, tenant_id, claim.booking.id)
            assert row is not None
            # The RAW token is never on the 7-year table — only its sha256.
            assert row.manage_token_hash == manage_token_hash(claim.manage_token)
            assert claim.manage_token not in (row.manage_token_hash or "")

            pending = await ScheduledMessagesRepository().pending_for_booking(
                session, tenant_id, booking_id=claim.booking.id, kind=REMINDER
            )
            assert pending is not None
            # SLOT is weeks out, so the >=24h band applies.
            assert pending.send_after == SLOT - datetime.timedelta(seconds=86_400)
            assert pending.manage_token == claim.manage_token
    finally:
        await engine.dispose()


async def test_a_booking_inside_two_hours_gets_a_token_but_no_reminder_row(
    app_role_url: str,
) -> None:
    """D3's suppression band, end to end: she still gets the link on the
    confirmation, and no second message inside two hours."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id)
        late = SLOT - datetime.timedelta(minutes=90)
        claim = await _claim(factory, tenant_id, type_id, now=late)

        assert claim.manage_token is not None
        async with tenant_session(factory, tenant_id) as session:
            assert (
                await ScheduledMessagesRepository().pending_for_booking(
                    session, tenant_id, booking_id=claim.booking.id, kind=REMINDER
                )
                is None
            )
    finally:
        await engine.dispose()


async def test_a_replayed_claim_returns_the_first_booking_with_no_token(
    app_role_url: str,
) -> None:
    """0009's idempotency path. `manage_token is None` is what makes the router's
    "do not resend" branch structural, and the pending reminder must not be
    duplicated either."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id)
        phone = _phone()
        first = await _claim(factory, tenant_id, type_id, phone=phone)
        replay = await _claim(factory, tenant_id, type_id, phone=phone)

        assert replay.booking.id == first.booking.id
        assert replay.created is False
        assert replay.manage_token is None
        async with tenant_session(factory, tenant_id) as session:
            # scalar_one_or_none would raise if the pending-unique index had let
            # a second row through.
            assert (
                await ScheduledMessagesRepository().pending_for_booking(
                    session, tenant_id, booking_id=first.booking.id, kind=REMINDER
                )
                is not None
            )
    finally:
        await engine.dispose()


async def test_the_pending_unique_index_refuses_a_second_pending_reminder(
    app_role_url: str,
) -> None:
    """The idempotency key is DDL. A double-schedule must converge on one row
    rather than send twice — and it must NOT block a fresh pending row once the
    first has left pending, which is what the reschedule upsert depends on."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    repo = ScheduledMessagesRepository()
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(factory, tenant_id, type_id)

        with pytest.raises(IntegrityError):
            async with tenant_session(factory, tenant_id) as session:
                await repo.insert(
                    session,
                    tenant_id=tenant_id,
                    booking_id=claim.booking.id,
                    kind=REMINDER,
                    send_after=SLOT,
                    manage_token="second",
                )

        async with tenant_session(factory, tenant_id) as session:
            pending = await repo.pending_for_booking(
                session, tenant_id, booking_id=claim.booking.id, kind=REMINDER
            )
            assert pending is not None
            await repo.mark(
                session, tenant_id, pending.id, status=ScheduledMessageStatus.SENT.value
            )
        async with tenant_session(factory, tenant_id) as session:
            # Terminal rows are outside the index predicate, so this succeeds.
            await repo.insert(
                session,
                tenant_id=tenant_id,
                booking_id=claim.booking.id,
                kind=REMINDER,
                send_after=SLOT,
                manage_token="fresh",
            )
    finally:
        await engine.dispose()


# --- the confirmation's evidence, both failure modes -----------------------


async def test_a_refused_confirmation_leaves_a_failed_evidence_row(app_role_url: str) -> None:
    """A CONFIGURED provider that refuses: the booking stands, the send is
    swallowed, and message_log carries the `failed` row — which is the only trace
    a kosher-phone customer's permanent failure ever leaves (spec Risk 3)."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id)
        phone = _phone()
        claim = await _claim(factory, tenant_id, type_id, phone=phone)
        comms, _ = _comms(factory, sender=RefusingSender())

        assert claim.manage_token is not None
        sent = await comms.send_confirmation(
            _tenant(tenant_id), booking=claim.booking, manage_token=claim.manage_token
        )

        assert sent is False
        async with tenant_session(factory, tenant_id) as session:
            rows = await MessageLogRepository().list_by_phone(
                session, tenant_id, phone=normalize_israeli_mobile(phone)
            )
        [row] = [r for r in rows if r.kind == MessageKind.CONFIRMATION.value]
        assert row.status == MessageStatus.FAILED.value
        assert row.booking_id == claim.booking.id
        # D2: the evidence row must not hold the raw token beside its own hash.
        assert claim.manage_token not in row.body
        assert MASKED_TOKEN in row.body
    finally:
        await engine.dispose()


async def test_an_unconfigured_deployment_leaves_no_evidence_row_at_all(
    app_role_url: str,
) -> None:
    """F11 raises BEFORE any insert, deliberately, so the pre-provider window is
    evidence-free by design. Asserted rather than assumed, because the manage-page
    copy and the confirmation screen's wording both depend on it being true."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id)
        phone = _phone()
        claim = await _claim(factory, tenant_id, type_id, phone=phone)
        comms, _ = _comms(factory, sender=UnconfiguredSmsSender())

        assert claim.manage_token is not None
        assert (
            await comms.send_confirmation(
                _tenant(tenant_id), booking=claim.booking, manage_token=claim.manage_token
            )
            is False
        )

        async with tenant_session(factory, tenant_id) as session:
            rows = await MessageLogRepository().list_by_phone(
                session, tenant_id, phone=normalize_israeli_mobile(phone)
            )
        assert [r for r in rows if r.kind == MessageKind.CONFIRMATION.value] == []
    finally:
        await engine.dispose()


async def test_a_delivered_confirmation_carries_the_live_link(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(factory, tenant_id, type_id)
        comms, sender = _comms(factory)

        assert claim.manage_token is not None
        assert (
            await comms.send_confirmation(
                _tenant(tenant_id), booking=claim.booking, manage_token=claim.manage_token
            )
            is True
        )

        [message] = sender.outbox
        assert f"https://bella.{BASE_DOMAIN}/b/{claim.manage_token}" in message.body
        # The wire body carries the real token; only message_log is masked.
        async with tenant_session(factory, tenant_id) as session:
            rows = await MessageLogRepository().list_by_phone(
                session, tenant_id, phone=message.phone
            )
        assert all(claim.manage_token not in row.body for row in rows)
    finally:
        await engine.dispose()


# --- the poller ------------------------------------------------------------


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


async def test_a_due_reminder_sends_once_and_the_row_goes_to_sent(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(factory, tenant_id, type_id)
        await _make_due(factory, tenant_id, claim.booking.id)
        comms, sender = _comms(factory)

        first = await comms.drain_due(_tenant(tenant_id))
        second = await comms.drain_due(_tenant(tenant_id))

        assert (first.sent, first.failed) == (1, 0)
        # The second tick finds nothing: the row left pending, so it is no longer
        # claimable. This is the idempotency the whole design turns on.
        assert second.sent == 0
        assert len(sender.outbox) == 1
        assert "תזכורת" in sender.outbox[0].body
        assert "מחר" not in sender.outbox[0].body

        async with tenant_session(factory, tenant_id) as session:
            row = await ScheduledMessagesRepository().pending_for_booking(
                session, tenant_id, booking_id=claim.booking.id, kind=REMINDER
            )
            assert row is None  # no longer pending
    finally:
        await engine.dispose()


async def test_two_concurrent_claimers_never_send_the_same_reminder_twice(
    app_role_url: str,
) -> None:
    """The SKIP LOCKED proof, and the reason `claim_due` exists at all: a second
    worker replica must be safe to add without a coordination story.

    Each drain gets its OWN connection (NullPool), so the two transactions really
    do overlap. The loser skips the locked row rather than waiting on it — which
    is also why one send never blocks the other tenant's batch."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=3)
        claims = [
            await _claim(factory, tenant_id, type_id, starts_at=_slot(10 + index))
            for index in range(3)
        ]
        for claim in claims:
            await _make_due(factory, tenant_id, claim.booking.id)

        comms_a, sender_a = _comms(factory)
        comms_b, sender_b = _comms(factory)
        results = await asyncio.gather(
            comms_a.drain_due(_tenant(tenant_id)),
            comms_b.drain_due(_tenant(tenant_id)),
        )

        # Every row sent exactly once across both workers, and no row twice.
        assert sum(result.sent for result in results) == 3
        bodies = [m.body for m in sender_a.outbox] + [m.body for m in sender_b.outbox]
        assert len(bodies) == 3
        assert len(set(bodies)) == 3
    finally:
        await engine.dispose()


async def test_the_claim_time_recheck_cancels_a_reminder_for_a_cancelled_booking(
    app_role_url: str,
) -> None:
    """The defence against races the schedule-time bands cannot see. Here the
    cancel path already flips the row, so this asserts the belt AND the braces:
    even a row that somehow survived cancellation sends nothing."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(factory, tenant_id, type_id)
        await _make_due(factory, tenant_id, claim.booking.id)
        async with tenant_session(factory, tenant_id) as session:
            # Cancel the BOOKING only, leaving the reminder pending on purpose.
            await BookingsRepository().cancel(
                session, tenant_id, claim.booking.id, at=NOW, by="owner"
            )
        comms, sender = _comms(factory)

        result = await comms.drain_due(_tenant(tenant_id))

        assert (result.sent, result.cancelled) == (0, 1)
        assert sender.outbox == []
    finally:
        await engine.dispose()


async def test_a_reminder_for_an_already_started_appointment_is_cancelled_not_sent(
    app_role_url: str,
) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(factory, tenant_id, type_id)
        await _make_due(factory, tenant_id, claim.booking.id)
        # A tick running AFTER the appointment: the backlog must not text a bride
        # about a fitting she has already been to.
        comms, sender = _comms(factory, now=SLOT + datetime.timedelta(hours=1))

        result = await comms.drain_due(_tenant(tenant_id))

        assert (result.sent, result.cancelled) == (0, 1)
        assert sender.outbox == []
    finally:
        await engine.dispose()


async def test_an_unconfigured_provider_leaves_the_row_pending_for_the_next_tick(
    app_role_url: str,
) -> None:
    """The pre-provider backlog flushes itself the first tick after the adapter
    lands. Marking these `failed` would be a lie — no send was ever attempted and
    F11 leaves no evidence row to point at."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(factory, tenant_id, type_id)
        await _make_due(factory, tenant_id, claim.booking.id)

        dark, _ = _comms(factory, sender=UnconfiguredSmsSender())
        deferred = await dark.drain_due(_tenant(tenant_id))
        assert (deferred.sent, deferred.failed, deferred.deferred) == (0, 0, 1)

        live, sender = _comms(factory)
        flushed = await live.drain_due(_tenant(tenant_id))
        assert flushed.sent == 1
        assert len(sender.outbox) == 1
    finally:
        await engine.dispose()


async def test_a_refused_reminder_is_marked_failed_with_evidence(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id)
        phone = _phone()
        claim = await _claim(factory, tenant_id, type_id, phone=phone)
        await _make_due(factory, tenant_id, claim.booking.id)
        comms, _ = _comms(factory, sender=RefusingSender())

        result = await comms.drain_due(_tenant(tenant_id))

        assert (result.sent, result.failed) == (0, 1)
        async with tenant_session(factory, tenant_id) as session:
            rows = await MessageLogRepository().list_by_phone(
                session, tenant_id, phone=normalize_israeli_mobile(phone)
            )
            assert [r.status for r in rows if r.kind == MessageKind.REMINDER.value] == [
                MessageStatus.FAILED.value
            ]
            # Not pending any more: a refused send does not retry itself (F15's
            # resend is the remedy surface).
            assert (
                await ScheduledMessagesRepository().pending_for_booking(
                    session, tenant_id, booking_id=claim.booking.id, kind=REMINDER
                )
                is None
            )
    finally:
        await engine.dispose()


# --- the tokenized page ----------------------------------------------------


async def test_lookup_answers_the_facts_the_accepted_policy_and_the_contact_block(
    app_role_url: str,
) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(factory, tenant_id, type_id)
        assert claim.manage_token is not None

        answer = await _manage(factory).lookup(_manage_tenant(tenant_id), token=claim.manage_token)

        assert answer.booking.starts_at == SLOT
        assert answer.booking.status == BookingStatus.CONFIRMED.value
        assert answer.booking.attendance_confirmed_at is None
        assert answer.booking.appointment_type_name == "מדידה ראשונה"
        assert answer.policy is not None
        assert answer.policy.refundable_until_hours_before == 48
        assert answer.boutique.address == "דיזנגוף 99"
        # "" in the fixture profile collapses to null — the shared profile_text rule.
        assert answer.boutique.maps_url is None
    finally:
        await engine.dispose()


async def test_the_policy_comes_from_the_accepted_version_not_the_current_one(
    app_role_url: str,
) -> None:
    """The single most consequential assertion on this surface. A boutique that
    republishes its policy must not retroactively change the terms of an
    appointment already agreed to — which is the entire reason
    `terms_version_accepted` is a column."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, refundable_hours=48)
        claim = await _claim(factory, tenant_id, type_id)
        assert claim.manage_token is not None
        async with tenant_session(factory, tenant_id) as session:
            await TermsVersionsRepository().insert(
                session,
                tenant_id=tenant_id,
                version=2,
                terms_text="מדיניות מחמירה",
                refundable_until_hours_before=120,
                forfeit_percent=100,
                created_by=uuid.uuid4(),
            )

        answer = await _manage(factory).lookup(_manage_tenant(tenant_id), token=claim.manage_token)

        assert answer.policy is not None
        assert answer.policy.refundable_until_hours_before == 48
        assert answer.policy.forfeit_percent == 50
    finally:
        await engine.dispose()


async def test_an_unknown_or_rotated_token_is_one_indistinguishable_404(
    app_role_url: str,
) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(factory, tenant_id, type_id)
        assert claim.manage_token is not None
        service = _manage(factory)

        with pytest.raises(BookingLinkInvalidError):
            await service.lookup(_manage_tenant(tenant_id), token=mint_manage_token())

        # Rotation (F15's edit-phone remedy) kills the old link.
        comms, _ = _comms(factory)
        rotated = await comms.reissue_manage_token(_tenant(tenant_id), booking_id=claim.booking.id)
        assert rotated is not None and rotated != claim.manage_token
        with pytest.raises(BookingLinkInvalidError):
            await service.lookup(_manage_tenant(tenant_id), token=claim.manage_token)
        # ... and the new one works, including for the still-pending reminder.
        await service.lookup(_manage_tenant(tenant_id), token=rotated)
        async with tenant_session(factory, tenant_id) as session:
            pending = await ScheduledMessagesRepository().pending_for_booking(
                session, tenant_id, booking_id=claim.booking.id, kind=REMINDER
            )
            assert pending is not None
            # Re-pointed in the same transaction, or the reminder would send a
            # link the reissue just invalidated.
            assert pending.manage_token == rotated
    finally:
        await engine.dispose()


async def test_a_foreign_tenants_token_never_resolves(app_role_url: str) -> None:
    """RLS plus the explicit tenant predicate. A token is scoped to the boutique
    that issued it, and every storefront host resolves its own tenant."""
    engine, factory = _factory(app_role_url)
    mine, theirs = uuid.uuid4(), uuid.uuid4()
    try:
        type_id = await _seed(factory, mine)
        await _seed(factory, theirs)
        claim = await _claim(factory, mine, type_id)
        assert claim.manage_token is not None

        with pytest.raises(BookingLinkInvalidError):
            await _manage(factory).lookup(_manage_tenant(theirs), token=claim.manage_token)
    finally:
        await engine.dispose()


async def test_confirm_attendance_is_idempotent_and_keeps_the_first_timestamp(
    app_role_url: str,
) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(factory, tenant_id, type_id)
        assert claim.manage_token is not None
        first_tap = _manage(factory, now=NOW)
        later_tap = _manage(factory, now=NOW + datetime.timedelta(hours=2))

        one = await first_tap.confirm_attendance(
            _manage_tenant(tenant_id), token=claim.manage_token
        )
        two = await later_tap.confirm_attendance(
            _manage_tenant(tenant_id), token=claim.manage_token
        )

        assert one.booking.attendance_confirmed_at == NOW
        # She will click the link more than once; the second tap is the same
        # success and must not move the evidence.
        assert two.booking.attendance_confirmed_at == NOW
    finally:
        await engine.dispose()


async def test_actions_expire_at_starts_at_but_the_page_stays_readable(
    app_role_url: str,
) -> None:
    """The recorded amendment of checklist row 21: an honest "this appointment has
    passed" beats a dead link for someone re-opening her SMS."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(factory, tenant_id, type_id)
        assert claim.manage_token is not None
        after = _manage(factory, now=SLOT + datetime.timedelta(minutes=1))

        readable = await after.lookup(_manage_tenant(tenant_id), token=claim.manage_token)
        assert readable.booking.starts_at == SLOT

        with pytest.raises(BookingAlreadyStartedError):
            await after.confirm_attendance(_manage_tenant(tenant_id), token=claim.manage_token)
        with pytest.raises(BookingAlreadyStartedError):
            await after.cancel(_manage_tenant(tenant_id), token=claim.manage_token)
    finally:
        await engine.dispose()


async def test_cancel_frees_the_seat_flips_the_reminder_and_repeats_as_a_success(
    app_role_url: str,
) -> None:
    """Three claims in one transaction's worth of behaviour, because they are one
    transaction: the status write, the reminder flip, and the structural seat
    release that lets her rebook the very same instant."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=1)
        claim = await _claim(factory, tenant_id, type_id)
        assert claim.manage_token is not None
        service = _manage(factory)

        cancelled = await service.cancel(_manage_tenant(tenant_id), token=claim.manage_token)
        assert cancelled.booking.status == BookingStatus.CANCELLED.value

        async with tenant_session(factory, tenant_id) as session:
            row = await BookingsRepository().by_id(session, tenant_id, claim.booking.id)
            assert row is not None
            assert row.cancelled_at == NOW
            assert row.cancelled_by == "customer"
            assert (
                await ScheduledMessagesRepository().pending_for_booking(
                    session, tenant_id, booking_id=claim.booking.id, kind=REMINDER
                )
                is None
            )

        # Repeat cancel: the same success, never an error (checklist row 21).
        again = await service.cancel(_manage_tenant(tenant_id), token=claim.manage_token)
        assert again.booking.status == BookingStatus.CANCELLED.value

        # The seat is genuinely free — both partial unique indexes exclude
        # 'cancelled', so a fresh claim at the SAME instant succeeds at capacity 1.
        rebooked = await _claim(factory, tenant_id, type_id)
        assert rebooked.created is True
        assert rebooked.booking.starts_at == SLOT
    finally:
        await engine.dispose()


async def test_confirming_attendance_on_a_cancelled_booking_is_a_conflict(
    app_role_url: str,
) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(factory, tenant_id, type_id)
        assert claim.manage_token is not None
        service = _manage(factory)
        await service.cancel(_manage_tenant(tenant_id), token=claim.manage_token)

        with pytest.raises(BookingCancelledError):
            await service.confirm_attendance(_manage_tenant(tenant_id), token=claim.manage_token)
    finally:
        await engine.dispose()


async def test_a_cancelled_seat_is_not_double_freed_by_a_second_cancel(
    app_role_url: str,
) -> None:
    """The repeat-cancel guard is `status = 'confirmed'`, so a second tap after a
    REBOOK of the same slot cannot cancel the new booking by accident."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=1)
        first = await _claim(factory, tenant_id, type_id)
        assert first.manage_token is not None
        service = _manage(factory)
        await service.cancel(_manage_tenant(tenant_id), token=first.manage_token)
        second = await _claim(factory, tenant_id, type_id)

        await service.cancel(_manage_tenant(tenant_id), token=first.manage_token)

        async with tenant_session(factory, tenant_id) as session:
            row = await BookingsRepository().by_id(session, tenant_id, second.booking.id)
            assert row is not None
            assert row.status == BookingStatus.CONFIRMED.value
    finally:
        await engine.dispose()


async def test_the_lookup_budget_is_its_own_instance_and_really_trips(
    app_role_url: str,
) -> None:
    """The anti-scrape ceiling on the one public endpoint that answers a secret."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(factory, tenant_id, type_id)
        assert claim.manage_token is not None
        tight = FixedWindowRateLimiter(max_attempts=2, window_seconds=300, clock=lambda: 0.0)
        service = _manage(factory, limiter=tight)

        await service.lookup(_manage_tenant(tenant_id), token=claim.manage_token)
        await service.lookup(_manage_tenant(tenant_id), token=claim.manage_token)
        with pytest.raises(BookingLookupThrottledError):
            await service.lookup(_manage_tenant(tenant_id), token=claim.manage_token)

        # The actions are NOT metered by this budget: a bride who reloaded a few
        # times must still be able to cancel.
        await service.cancel(_manage_tenant(tenant_id), token=claim.manage_token)
    finally:
        await engine.dispose()


# --- the reschedule upsert -------------------------------------------------


async def test_reschedule_replaces_a_pending_reminder_at_the_new_time(
    app_role_url: str,
) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(factory, tenant_id, type_id)
        comms, _ = _comms(factory)
        moved = _slot(12, 0)

        send_after = await comms.reschedule_reminder(
            _tenant(tenant_id), booking_id=claim.booking.id, starts_at=moved
        )

        assert send_after == moved - datetime.timedelta(seconds=86_400)
        async with tenant_session(factory, tenant_id) as session:
            pending = await ScheduledMessagesRepository().pending_for_booking(
                session, tenant_id, booking_id=claim.booking.id, kind=REMINDER
            )
            assert pending is not None
            assert pending.send_after == send_after
            # The SAME link survives the move, which is why the token is carried
            # forward off the row being cancelled instead of being re-minted.
            assert pending.manage_token == claim.manage_token
    finally:
        await engine.dispose()


async def test_reschedule_creates_a_fresh_row_even_when_the_prior_reminder_already_sent(
    app_role_url: str,
) -> None:
    """The reason this is an upsert and never a re-target. A day-of reschedule is
    the COMMON case and its old reminder has already fired, so "update the pending
    row" would be a silent no-op that ships green-tested."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(factory, tenant_id, type_id)
        await _make_due(factory, tenant_id, claim.booking.id)
        comms, _ = _comms(factory)
        assert (await comms.drain_due(_tenant(tenant_id))).sent == 1

        moved = _slot(12, 0)
        send_after = await comms.reschedule_reminder(
            _tenant(tenant_id), booking_id=claim.booking.id, starts_at=moved
        )

        assert send_after == moved - datetime.timedelta(seconds=86_400)
        async with tenant_session(factory, tenant_id) as session:
            pending = await ScheduledMessagesRepository().pending_for_booking(
                session, tenant_id, booking_id=claim.booking.id, kind=REMINDER
            )
            assert pending is not None
            # Nothing pending to inherit a link from, so a fresh token was minted
            # and the booking's hash rotated with it.
            row = await BookingsRepository().by_id(session, tenant_id, claim.booking.id)
            assert row is not None
            assert pending.manage_token is not None
            assert row.manage_token_hash == manage_token_hash(pending.manage_token)
    finally:
        await engine.dispose()


async def test_rescheduling_into_the_suppression_window_leaves_no_pending_row(
    app_role_url: str,
) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(factory, tenant_id, type_id)
        comms, _ = _comms(factory, now=SLOT - datetime.timedelta(minutes=90))

        assert (
            await comms.reschedule_reminder(
                _tenant(tenant_id), booking_id=claim.booking.id, starts_at=SLOT
            )
            is None
        )

        async with tenant_session(factory, tenant_id) as session:
            assert (
                await ScheduledMessagesRepository().pending_for_booking(
                    session, tenant_id, booking_id=claim.booking.id, kind=REMINDER
                )
                is None
            )
    finally:
        await engine.dispose()


async def test_the_owner_seams_send_their_bodies(app_role_url: str) -> None:
    """F15 has no console yet, so these are unit-level proofs of the seams it will
    call. The owner-cancel body carries no money words until E4 #19 exists to
    compute a refund outcome."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(factory, tenant_id, type_id)
        comms, sender = _comms(factory)

        assert await comms.notify_owner_cancel(_tenant(tenant_id), booking=claim.booking) is True
        assert (
            await comms.notify_owner_reschedule(_tenant(tenant_id), booking=claim.booking) is True
        )

        cancel_body, reschedule_body = (m.body for m in sender.outbox)
        assert "בוטל על ידי הבוטיק" in cancel_body
        assert "052-1234567" in cancel_body
        assert "החזר" not in cancel_body
        # The reschedule carries the live link — read off the pending reminder, so
        # it is the same one the confirmation already sent.
        assert claim.manage_token is not None
        assert claim.manage_token in reschedule_body
    finally:
        await engine.dispose()


async def _register_tenant(factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID) -> None:
    """Put the tenant in the registry.

    Every other test here builds a `CommsTenant`/`ManageTenant` value object and
    hands it straight to the service, so a tenant-scoped seed is all they need.
    The backfill is the one path that *discovers* its own tenants, via
    `TenantsRepository.list_active()` — with no `tenants` row it finds nothing and
    mints nothing. Without this the mint assertions fail, and worse, the two
    exclusion tests pass for the wrong reason.

    `tenants` is platform-scoped (no tenant_id, no RLS) and `status` server-defaults
    to active, so a plain insert with an explicit id is enough.
    """
    async with factory() as session, session.begin():
        session.add(Tenant(id=tenant_id, slug=f"bf-{tenant_id.hex[:12]}", name="בלה כלות"))


async def _deregister_tenant(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID
) -> None:
    """Remove the registry row again, so the tenant is invisible to every later
    backfill run in this database.

    `list_active()` is global by design — it is a deploy step, not a per-tenant
    call — so a registered tenant left behind gets rescanned by the next test's
    backfill. That is not hypothetical: a booking one test treats as past
    (relative to its own clock) is future relative to another's, so it gets
    minted a second time and collides on the pending-unique index. Tearing the
    row down keeps these tests order-independent.
    """
    async with factory() as session, session.begin():
        await session.execute(delete(Tenant).where(Tenant.id == tenant_id))


# --- the backfill ---------------------------------------------------------


async def test_the_backfill_mints_links_and_schedules_reminders_and_is_rerunnable(
    app_role_url: str,
) -> None:
    """The D10 deploy step. Pre-F16 rows are simulated by clearing the columns 0010
    added, which is exactly the state F14's merged bookings are in."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        await _register_tenant(factory, tenant_id)
        type_id = await _seed(factory, tenant_id, capacity=2)
        claims = [
            await _claim(factory, tenant_id, type_id, starts_at=_slot(10 + index))
            for index in range(2)
        ]
        async with tenant_session(factory, tenant_id) as session:
            repo = ScheduledMessagesRepository()
            for claim in claims:
                row = await BookingsRepository().by_id(session, tenant_id, claim.booking.id)
                assert row is not None
                row.manage_token_hash = None
                await repo.cancel_pending(
                    session, tenant_id, booking_id=claim.booking.id, kind=REMINDER
                )

        backfill = ManageLinkBackfill(factory, clock=lambda: NOW)
        first = await backfill.run()
        assert (first.tokens_minted, first.reminders_scheduled) == (2, 2)

        async with tenant_session(factory, tenant_id) as session:
            for claim in claims:
                row = await BookingsRepository().by_id(session, tenant_id, claim.booking.id)
                assert row is not None
                assert row.manage_token_hash is not None
                pending = await ScheduledMessagesRepository().pending_for_booking(
                    session, tenant_id, booking_id=claim.booking.id, kind=REMINDER
                )
                assert pending is not None
                assert manage_token_hash(pending.manage_token or "") == row.manage_token_hash

        # Idempotent by predicate: the second run finds nothing to do, which is
        # what makes it safe to re-run after a partial failure.
        assert await backfill.run() == BackfillResult(
            tenants=first.tenants, tokens_minted=0, reminders_scheduled=0
        )
    finally:
        await _deregister_tenant(factory, tenant_id)
        await engine.dispose()


async def test_the_backfill_skips_a_cancelled_booking(app_role_url: str) -> None:
    """Tested with a clock BEFORE the appointment, so the status exclusion is the
    only thing that can be doing the work."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        await _register_tenant(factory, tenant_id)
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(factory, tenant_id, type_id)
        async with tenant_session(factory, tenant_id) as session:
            row = await BookingsRepository().by_id(session, tenant_id, claim.booking.id)
            assert row is not None
            row.manage_token_hash = None
            row.status = BookingStatus.CANCELLED.value

        assert (await ManageLinkBackfill(factory, clock=lambda: NOW).run()).tokens_minted == 0
    finally:
        await _deregister_tenant(factory, tenant_id)
        await engine.dispose()


async def test_the_backfill_skips_a_booking_that_has_already_happened(
    app_role_url: str,
) -> None:
    """Left CONFIRMED, so the future-only predicate is the only exclusion in play.
    No retroactive link for a fitting she has already been to."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        await _register_tenant(factory, tenant_id)
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(factory, tenant_id, type_id)
        async with tenant_session(factory, tenant_id) as session:
            row = await BookingsRepository().by_id(session, tenant_id, claim.booking.id)
            assert row is not None
            row.manage_token_hash = None
            assert row.status == BookingStatus.CONFIRMED.value

        after = SLOT + datetime.timedelta(days=1)
        assert (await ManageLinkBackfill(factory, clock=lambda: after).run()).tokens_minted == 0
    finally:
        await _deregister_tenant(factory, tenant_id)
        await engine.dispose()


async def test_a_backfilled_link_actually_opens_the_page(app_role_url: str) -> None:
    """End to end for the gap F14 opened: an already-existing booking becomes
    manageable, which is the whole point of the deploy step."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        await _register_tenant(factory, tenant_id)
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(factory, tenant_id, type_id)
        async with tenant_session(factory, tenant_id) as session:
            row = await BookingsRepository().by_id(session, tenant_id, claim.booking.id)
            assert row is not None
            row.manage_token_hash = None
            await ScheduledMessagesRepository().cancel_pending(
                session, tenant_id, booking_id=claim.booking.id, kind=REMINDER
            )

        await ManageLinkBackfill(factory, clock=lambda: NOW).run()
        async with tenant_session(factory, tenant_id) as session:
            pending = await ScheduledMessagesRepository().pending_for_booking(
                session, tenant_id, booking_id=claim.booking.id, kind=REMINDER
            )
            assert pending is not None and pending.manage_token is not None
            token = pending.manage_token

        answer = await _manage(factory).lookup(_manage_tenant(tenant_id), token=token)
        assert answer.booking.starts_at == SLOT
    finally:
        await _deregister_tenant(factory, tenant_id)
        await engine.dispose()


async def test_a_slot_freed_by_a_customer_cancel_is_offered_again_by_the_grid(
    app_role_url: str,
) -> None:
    """The e2e spec's last step, proved at the service level: cancelling really
    returns the time to the pool rather than only flipping a status."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id, capacity=1)
        claim = await _claim(factory, tenant_id, type_id)
        assert claim.manage_token is not None

        # Full at capacity 1 ...
        with pytest.raises(SlotUnavailableError):
            await _claim(factory, tenant_id, type_id)

        await _manage(factory).cancel(_manage_tenant(tenant_id), token=claim.manage_token)

        # ... and claimable again the moment it is cancelled.
        assert (await _claim(factory, tenant_id, type_id)).created is True
    finally:
        await engine.dispose()
