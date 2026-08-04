"""OtpService + NotificationService against real Postgres as the app role."""

import datetime
import re
import time
import uuid

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
from app.db.repositories.message_log import MessageLogRepository
from app.db.repositories.otp_codes import OtpCodesRepository
from app.db.tenant import tenant_session
from app.models.constants import MessageKind, MessageStatus
from app.models.message_log import MessageLog
from app.notifications.base import (
    SendResult,
    SmsNotConfiguredError,
    SmsRecipientErasedError,
    SmsSender,
    SmsSendError,
)
from app.notifications.fake import FakeSmsSender
from app.notifications.service import (
    MAX_PROVIDER_ERROR_LENGTH,
    NotificationService,
    OtpExpiredError,
    OtpInvalidError,
    OtpService,
    OtpThrottledError,
)
from app.notifications.unconfigured import UnconfiguredSmsSender
from app.notifications.validation import OTP_MAX_VERIFY_ATTEMPTS, OTP_TTL_SECONDS
from app.privacy.validation import ERASED_PHONE_PREFIX

pytestmark = pytest.mark.db

PHONE = "050-123-4567"
NORMALIZED = "+972501234567"


class WallClockStub:
    def __init__(self) -> None:
        self.now = datetime.datetime(2026, 7, 28, 12, 0, tzinfo=datetime.UTC)

    def __call__(self) -> datetime.datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += datetime.timedelta(seconds=seconds)


class ExplodingSmsSender:
    @property
    def is_configured(self) -> bool:
        return True

    async def send(self, *, phone: str, body: str) -> SendResult:
        raise RuntimeError("provider says no (with secret internals)")


class EchoingSmsSender:
    """Models the real hazard: an SDK whose exception quotes the request it
    failed to send, body and all. Records the body so the assertion can name
    the exact code that must not survive."""

    def __init__(self) -> None:
        self.last_body: str | None = None

    @property
    def is_configured(self) -> bool:
        return True

    async def send(self, *, phone: str, body: str) -> SendResult:
        self.last_body = body
        raise RuntimeError(f"HTTP 400 from provider; request was To={phone} Body={body!r}")


def _factory(app_role_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(app_role_url, poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _loose_limiter() -> FixedWindowRateLimiter:
    return FixedWindowRateLimiter(max_attempts=10_000, window_seconds=3600, clock=time.monotonic)


def _service(
    factory: async_sessionmaker[AsyncSession],
    sender: SmsSender | None = None,
    *,
    phone_limiter: FixedWindowRateLimiter | None = None,
    tenant_limiter: FixedWindowRateLimiter | None = None,
    verify_limiter: FixedWindowRateLimiter | None = None,
    dev_code: str | None = None,
) -> tuple[OtpService, SmsSender, WallClockStub]:
    actual_sender = sender if sender is not None else FakeSmsSender()
    clock = WallClockStub()
    notifications = NotificationService(factory, sender=actual_sender)
    otp = OtpService(
        factory,
        notifications=notifications,
        phone_limiter=phone_limiter if phone_limiter is not None else _loose_limiter(),
        tenant_limiter=tenant_limiter if tenant_limiter is not None else _loose_limiter(),
        verify_limiter=verify_limiter if verify_limiter is not None else _loose_limiter(),
        dev_code=dev_code,
        clock=clock,
    )
    return otp, actual_sender, clock


def _code_from(body: str) -> str:
    match = re.search(r"\d{6}", body)
    assert match is not None, f"no code in body: {body!r}"
    return match.group()


async def test_full_otp_lifecycle_send_verify_consume(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    otp, sender, clock = _service(factory)
    assert isinstance(sender, FakeSmsSender)
    try:
        await otp.send(tenant_id, PHONE)
        assert len(sender.outbox) == 1
        assert sender.outbox[0].phone == NORMALIZED
        code = _code_from(sender.outbox[0].body)

        result = await otp.verify(tenant_id, PHONE, code)
        assert result.verification_token
        assert result.expires_at > clock()

        async with tenant_session(factory, tenant_id) as session:
            claimed = await otp.consume_verification(
                session, tenant_id, raw_phone=PHONE, verification_token=result.verification_token
            )
            assert claimed is True
            # Single use: the same token never claims twice.
            again = await otp.consume_verification(
                session, tenant_id, raw_phone=PHONE, verification_token=result.verification_token
            )
            assert again is False
    finally:
        await engine.dispose()


async def test_message_log_masks_the_otp_code(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    otp, sender, _ = _service(factory)
    assert isinstance(sender, FakeSmsSender)
    try:
        await otp.send(tenant_id, PHONE)
        code = _code_from(sender.outbox[0].body)
        async with tenant_session(factory, tenant_id) as session:
            rows = await MessageLogRepository().list_by_phone(session, tenant_id, phone=NORMALIZED)
        assert len(rows) == 1
        assert rows[0].status == MessageStatus.SENT.value
        assert rows[0].provider_message_id == "fake-1"
        assert code not in rows[0].body  # the log never retains a live code
        assert "●" in rows[0].body
    finally:
        await engine.dispose()


async def test_verify_is_single_use(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    otp, sender, _ = _service(factory)
    assert isinstance(sender, FakeSmsSender)
    try:
        await otp.send(tenant_id, PHONE)
        code = _code_from(sender.outbox[0].body)
        await otp.verify(tenant_id, PHONE, code)
        with pytest.raises(OtpInvalidError):
            await otp.verify(tenant_id, PHONE, code)
    finally:
        await engine.dispose()


async def test_verify_expires_at_ttl(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    otp, sender, clock = _service(factory)
    assert isinstance(sender, FakeSmsSender)
    try:
        await otp.send(tenant_id, PHONE)
        code = _code_from(sender.outbox[0].body)
        clock.advance(OTP_TTL_SECONDS + 1)
        with pytest.raises(OtpExpiredError):
            await otp.verify(tenant_id, PHONE, code)
    finally:
        await engine.dispose()


async def test_attempt_cap_burns_the_code(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    otp, sender, _ = _service(factory)
    assert isinstance(sender, FakeSmsSender)
    try:
        await otp.send(tenant_id, PHONE)
        code = _code_from(sender.outbox[0].body)
        wrong = "000000" if code != "000000" else "111111"
        for _ in range(OTP_MAX_VERIFY_ATTEMPTS):
            with pytest.raises(OtpInvalidError):
                await otp.verify(tenant_id, PHONE, wrong)
        # The RIGHT code after five wrong guesses still fails — the cap is real.
        with pytest.raises(OtpInvalidError):
            await otp.verify(tenant_id, PHONE, code)
    finally:
        await engine.dispose()


async def test_failed_guesses_persist_their_attempt_increment(app_role_url: str) -> None:
    """The regression test for the review's critical finding. Every failure path
    in verify() raises, and `tenant_session` is `session.begin()` — a raise
    INSIDE the block would roll back the attempts increment with it, leaving the
    counter at 0 forever and making the cap inert (10^6 unlimited guesses per
    code). Behavioural cap tests pass either way; only reading the persisted
    column proves the write survived."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    otp, sender, _ = _service(factory)
    assert isinstance(sender, FakeSmsSender)
    repo = OtpCodesRepository()
    try:
        await otp.send(tenant_id, PHONE)
        code = _code_from(sender.outbox[0].body)
        wrong = "000000" if code != "000000" else "111111"

        for expected in (1, 2, 3):
            with pytest.raises(OtpInvalidError):
                await otp.verify(tenant_id, PHONE, wrong)
            async with tenant_session(factory, tenant_id) as session:
                row = await repo.latest_active_by_phone(session, tenant_id, phone=NORMALIZED)
            assert row is not None
            assert row.attempts == expected, "the increment was rolled back with the raise"
    finally:
        await engine.dispose()


async def test_attempts_stop_climbing_once_locked(app_role_url: str) -> None:
    """otp_codes.attempts carries CHECK (attempts <= 50) as a defensive ceiling.
    Once the service cap locks the code it must stop WRITING, not merely stop
    answering — otherwise sustained guessing walks the counter into an
    IntegrityError 500 on an anonymous endpoint."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    otp, sender, _ = _service(factory, verify_limiter=_loose_limiter())
    assert isinstance(sender, FakeSmsSender)
    repo = OtpCodesRepository()
    try:
        await otp.send(tenant_id, PHONE)
        for _ in range(60):
            with pytest.raises(OtpInvalidError):
                await otp.verify(tenant_id, PHONE, "000000")
        async with tenant_session(factory, tenant_id) as session:
            row = await repo.latest_active_by_phone(session, tenant_id, phone=NORMALIZED)
        assert row is not None
        assert row.attempts == OTP_MAX_VERIFY_ATTEMPTS
    finally:
        await engine.dispose()


async def test_verify_is_rate_limited(app_role_url: str) -> None:
    """The per-code attempt cap burns ONE code; without a verify budget an
    attacker just requests a fresh code and keeps guessing."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    tight = FixedWindowRateLimiter(max_attempts=3, window_seconds=300, clock=time.monotonic)
    otp, sender, _ = _service(factory, verify_limiter=tight)
    assert isinstance(sender, FakeSmsSender)
    try:
        await otp.send(tenant_id, PHONE)
        for _ in range(3):
            with pytest.raises(OtpInvalidError):
                await otp.verify(tenant_id, PHONE, "000000")
        with pytest.raises(OtpThrottledError):
            await otp.verify(tenant_id, PHONE, "000000")
    finally:
        await engine.dispose()


async def test_send_throttles_per_tenant_with_429(app_role_url: str) -> None:
    """The tenant ceiling is the boutique's SMS bill, and an exhausted one is an
    operational fact about the boutique — so unlike the phone budget it 429s."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    tight = FixedWindowRateLimiter(max_attempts=2, window_seconds=3600, clock=time.monotonic)
    otp, sender, _ = _service(factory, tenant_limiter=tight)
    assert isinstance(sender, FakeSmsSender)
    try:
        await otp.send(tenant_id, "050-111-1111")
        await otp.send(tenant_id, "050-222-2222")
        with pytest.raises(OtpThrottledError):
            await otp.send(tenant_id, "050-333-3333")
        assert len(sender.outbox) == 2
    finally:
        await engine.dispose()


async def test_exhausted_phone_budget_stays_silent(app_role_url: str) -> None:
    """A 429 here would answer "is this number mid-booking at this boutique" for
    any anonymous prober. Same 204, no SMS."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    tight = FixedWindowRateLimiter(max_attempts=1, window_seconds=3600, clock=time.monotonic)
    otp, sender, _ = _service(factory, phone_limiter=tight)
    assert isinstance(sender, FakeSmsSender)
    try:
        await otp.send(tenant_id, PHONE)
        await otp.send(tenant_id, PHONE)  # no raise
        assert len(sender.outbox) == 1
    finally:
        await engine.dispose()


async def test_non_ascii_code_is_a_clean_miss_not_a_crash(app_role_url: str) -> None:
    """hmac.compare_digest raises TypeError on non-ASCII, and `code` is
    attacker-supplied — hashing both sides keeps it a 400."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    otp, sender, _ = _service(factory, dev_code="424242")
    assert isinstance(sender, FakeSmsSender)
    try:
        await otp.send(tenant_id, PHONE)
        with pytest.raises(OtpInvalidError):
            await otp.verify(tenant_id, PHONE, "é23456")
    finally:
        await engine.dispose()


async def test_unconfigured_sender_writes_nothing(app_role_url: str) -> None:
    """503 before any write: an unconfigured deployment must not soft-delete a
    live code or accumulate rows per anonymous request."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    otp, _, _ = _service(factory, sender=UnconfiguredSmsSender())
    try:
        with pytest.raises(SmsNotConfiguredError):
            await otp.send(tenant_id, PHONE)
        async with tenant_session(factory, tenant_id) as session:
            assert (
                await OtpCodesRepository().latest_active_by_phone(
                    session, tenant_id, phone=NORMALIZED
                )
                is None
            )
            assert (
                await MessageLogRepository().list_by_phone(session, tenant_id, phone=NORMALIZED)
                == []
            )
    finally:
        await engine.dispose()


async def test_resend_invalidates_the_previous_code(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    otp, sender, _ = _service(factory)
    assert isinstance(sender, FakeSmsSender)
    try:
        await otp.send(tenant_id, PHONE)
        first = _code_from(sender.outbox[0].body)
        await otp.send(tenant_id, PHONE)
        second = _code_from(sender.outbox[1].body)
        if first == second:  # 1-in-a-million collision would void the assertion
            await otp.send(tenant_id, PHONE)
            second = _code_from(sender.outbox[2].body)
        with pytest.raises(OtpInvalidError):
            await otp.verify(tenant_id, PHONE, first)
        assert (await otp.verify(tenant_id, PHONE, second)).verification_token
    finally:
        await engine.dispose()


async def test_send_throttles_per_phone(app_role_url: str) -> None:
    """The phone budget caps sends per number. It does NOT raise — see
    test_exhausted_phone_budget_stays_silent for why 429 here would be an
    oracle. What matters is that the third attempt never reaches the wire."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    tight = FixedWindowRateLimiter(max_attempts=2, window_seconds=3600, clock=time.monotonic)
    otp, sender, _ = _service(factory, phone_limiter=tight)
    assert isinstance(sender, FakeSmsSender)
    try:
        await otp.send(tenant_id, PHONE)
        await otp.send(tenant_id, PHONE)
        await otp.send(tenant_id, PHONE)
        assert len(sender.outbox) == 2
    finally:
        await engine.dispose()


async def test_dev_code_is_accepted_when_configured(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    otp, sender, _ = _service(factory, dev_code="424242")
    assert isinstance(sender, FakeSmsSender)
    try:
        await otp.send(tenant_id, PHONE)
        result = await otp.verify(tenant_id, PHONE, "424242")
        assert result.verification_token
    finally:
        await engine.dispose()


async def test_dev_code_requires_a_live_send(app_role_url: str) -> None:
    """The escape hatch bypasses the code comparison, never the flow: without a
    preceding send there is no row, and verify fails exactly like a wrong code."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    otp, _, _ = _service(factory, dev_code="424242")
    try:
        with pytest.raises(OtpInvalidError):
            await otp.verify(tenant_id, PHONE, "424242")
    finally:
        await engine.dispose()


async def test_provider_explosion_is_contained(app_role_url: str) -> None:
    """An arbitrary provider exception becomes SmsSendError (no provider text
    for the caller) and the evidence row records the failure."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    otp, _, _ = _service(factory, sender=ExplodingSmsSender())
    try:
        with pytest.raises(SmsSendError):
            await otp.send(tenant_id, PHONE)
        async with tenant_session(factory, tenant_id) as session:
            rows = await MessageLogRepository().list_by_phone(session, tenant_id, phone=NORMALIZED)
        assert [row.status for row in rows] == [MessageStatus.FAILED.value]
        assert rows[0].error is not None
        assert "RuntimeError" in rows[0].error
    finally:
        await engine.dispose()


async def test_provider_error_never_persists_the_live_code(app_role_url: str) -> None:
    """Several SMS SDKs echo the failing request — including the body — in their
    exception. Persisting it verbatim would write the unmasked code into the one
    table designed never to hold one."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    sender = EchoingSmsSender()
    otp, _, _ = _service(factory, sender=sender)
    try:
        with pytest.raises(SmsSendError):
            await otp.send(tenant_id, PHONE)
        assert sender.last_body is not None
        code = _code_from(sender.last_body)

        async with tenant_session(factory, tenant_id) as session:
            rows = await MessageLogRepository().list_by_phone(session, tenant_id, phone=NORMALIZED)
        assert len(rows) == 1
        error = rows[0].error
        assert error is not None
        # The CODE, not "any six digits" — the phone number is six-plus digits
        # and is legitimately part of an operator-facing error.
        assert code not in error, f"a live code reached message_log.error: {error!r}"
        assert "●" in error, "the echoed body should survive in masked form"
        assert len(error) <= MAX_PROVIDER_ERROR_LENGTH
    finally:
        await engine.dispose()


async def test_send_sms_refuses_an_erased_phone_before_any_row_or_any_send(
    app_role_url: str,
) -> None:
    """⚠ F20 C7 — ONE guard in the single writer, not one in every caller.

    The spec's first draft claimed an erased customer's placeholder phone was
    "structurally un-sendable". That was FALSE against this code:
    `BookingCommsService._customer_phone` returns `customers.phone` verbatim and
    says so in its own docstring, and `send_sms` validated only `is_configured`
    before handing the string to the adapter. What actually blocked a send was
    F15's confirmed-AND-future `_guard_live` — which is exactly what F50 is
    chartered to widen. So F20 makes the claim true instead of restating it.

    Written against `send_sms` DIRECTLY, never through a booking path, because
    the guard's whole value is that it holds for callers that do not exist yet.
    A booking-path test would prove only that today's callers happen not to
    reach it.

    Both halves of "before" are asserted, and they are different failures:
    * no `message_log` row — otherwise the erasure leaks her placeholder into
      the log the retention job is supposed to be draining, on every retry;
    * no adapter call — otherwise a carrier receives a request derived from a
      record that was supposed to be gone.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    customer_id = uuid.uuid4()
    sender = FakeSmsSender()
    notifications = NotificationService(factory, sender=sender)
    try:
        with pytest.raises(SmsRecipientErasedError):
            await notifications.send_sms(
                tenant_id,
                phone=f"{ERASED_PHONE_PREFIX}{customer_id}",
                body="תזכורת",
                kind=MessageKind.REMINDER.value,
            )

        async with tenant_session(factory, tenant_id) as session:
            rows = (
                (await session.execute(select(MessageLog).where(MessageLog.tenant_id == tenant_id)))
                .scalars()
                .all()
            )
        assert rows == [], "an erased phone reached message_log"
        assert sender.outbox == [], "an erased phone reached the carrier"
    finally:
        await engine.dispose()


async def test_send_sms_still_sends_to_a_real_number(app_role_url: str) -> None:
    """The anti-vacuity half. Without it the guard above could be a `raise` at
    the top of `send_sms` and both assertions would still hold."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    sender = FakeSmsSender()
    notifications = NotificationService(factory, sender=sender)
    try:
        row = await notifications.send_sms(
            tenant_id, phone=NORMALIZED, body="תזכורת", kind=MessageKind.REMINDER.value
        )
        assert row.status == MessageStatus.SENT.value
        assert len(sender.outbox) == 1
    finally:
        await engine.dispose()
