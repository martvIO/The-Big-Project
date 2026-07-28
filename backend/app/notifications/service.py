"""NotificationService owns the message_log evidence trail above the SmsSender
port; OtpService owns the code lifecycle on top of it. Repositories never see
the adapter, the adapter never sees the database, and no feature code writes
message_log by any other path — F16's scheduler calls the same send_sms.
"""

import datetime
import hmac
import logging
from collections.abc import Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.tokens import generate_session_token, hash_token
from app.db.repositories.message_log import MessageLogRepository
from app.db.repositories.otp_codes import OtpCodesRepository
from app.db.tenant import tenant_session
from app.models.constants import MessageKind, MessageStatus
from app.models.message_log import MessageLog
from app.notifications.base import SmsNotConfiguredError, SmsSender, SmsSendError
from app.notifications.validation import (
    OTP_MAX_VERIFY_ATTEMPTS,
    OTP_TTL_SECONDS,
    VERIFICATION_TOKEN_TTL_SECONDS,
    generate_otp_code,
    mask_otp_body,
    normalize_israeli_mobile,
    otp_sms_body,
)

logger = logging.getLogger("app")

# UTC wall clock, injectable for expiry tests. Distinct from the monotonic
# clocks the rate limiters take — expiry is calendar time, windows are elapsed
# time, and conflating them is how DST bugs are born.
WallClock = Callable[[], datetime.datetime]


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


class OtpInvalidError(Exception):
    """Wrong code, no live code, or attempt cap exceeded — deliberately one
    indistinguishable error: an attacker learns nothing about WHY a guess failed."""


class OtpExpiredError(Exception):
    """Distinguished from invalid deliberately: "request a new code" is real UX,
    and expiry reveals nothing an attacker doesn't know from their own send time."""


class OtpThrottledError(Exception):
    pass


class NotificationService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        sender: SmsSender,
    ) -> None:
        self._session_factory = session_factory
        self._sender = sender
        self._message_log = MessageLogRepository()

    @property
    def is_configured(self) -> bool:
        return self._sender.is_configured

    async def send_sms(
        self,
        tenant_id: UUID,
        *,
        phone: str,
        body: str,
        kind: str,
        booking_id: UUID | None = None,
        log_body: str | None = None,
    ) -> MessageLog:
        """Insert queued → adapter send → mark sent/failed. Two tenant_sessions
        by design: a provider hang must never hold a DB transaction open, and a
        failed send must leave its evidence row behind, not roll it away.
        `log_body` is what message_log stores when the wire body must not be
        retained verbatim (the caller masks OTP codes — it knows the code)."""
        async with tenant_session(self._session_factory, tenant_id) as session:
            row = await self._message_log.insert(
                session,
                tenant_id=tenant_id,
                phone=phone,
                kind=kind,
                body=log_body if log_body is not None else body,
                booking_id=booking_id,
            )
        log_id = row.id

        try:
            result = await self._sender.send(phone=phone, body=body)
        except SmsNotConfiguredError:
            await self._mark(tenant_id, log_id, status=MessageStatus.FAILED, error="not configured")
            raise
        except Exception as exc:
            # Provider text goes to the log row and the server log only —
            # never to the caller (same containment as MediaStorageUnavailableError).
            logger.warning("SMS send failed for message_log %s", log_id, exc_info=exc)
            await self._mark(tenant_id, log_id, status=MessageStatus.FAILED, error=str(exc))
            raise SmsSendError from exc

        marked = await self._mark(
            tenant_id,
            log_id,
            status=MessageStatus.SENT,
            provider_message_id=result.provider_message_id,
        )
        return marked if marked is not None else row

    async def _mark(
        self,
        tenant_id: UUID,
        log_id: UUID,
        *,
        status: MessageStatus,
        provider_message_id: str | None = None,
        error: str | None = None,
    ) -> MessageLog | None:
        async with tenant_session(self._session_factory, tenant_id) as session:
            return await self._message_log.update_status(
                session,
                tenant_id,
                log_id,
                status=status.value,
                provider_message_id=provider_message_id,
                error=error,
            )


class VerifyResult:
    __slots__ = ("expires_at", "verification_token")

    def __init__(self, verification_token: str, expires_at: datetime.datetime) -> None:
        self.verification_token = verification_token
        self.expires_at = expires_at


class OtpService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        notifications: NotificationService,
        phone_limiter: FixedWindowRateLimiter,
        tenant_limiter: FixedWindowRateLimiter,
        dev_code: str | None = None,
        clock: WallClock = _utc_now,
    ) -> None:
        self._session_factory = session_factory
        self._notifications = notifications
        self._phone_limiter = phone_limiter
        self._tenant_limiter = tenant_limiter
        self._dev_code = dev_code
        self._clock = clock
        self._otp_codes = OtpCodesRepository()

    async def send(self, tenant_id: UUID, raw_phone: str) -> None:
        phone = normalize_israeli_mobile(raw_phone)
        phone_key = f"otp:phone:{tenant_id}:{phone}"
        tenant_key = f"otp:tenant:{tenant_id}"
        if self._phone_limiter.is_blocked(phone_key) or self._tenant_limiter.is_blocked(tenant_key):
            raise OtpThrottledError
        # Recorded on the ATTEMPT, success or failure — the resource being
        # metered is the send itself (same reasoning as the storefront throttle).
        self._phone_limiter.record_failure(phone_key)
        self._tenant_limiter.record_failure(tenant_key)

        code = generate_otp_code()
        body = otp_sms_body(code)
        now = self._clock()
        async with tenant_session(self._session_factory, tenant_id) as session:
            # One live code per phone: a resend invalidates its predecessor
            # rather than racing it.
            await self._otp_codes.soft_delete_active_for_phone(session, tenant_id, phone=phone)
            await self._otp_codes.insert(
                session,
                tenant_id=tenant_id,
                phone=phone,
                code_hash=hash_token(code),
                expires_at=now + datetime.timedelta(seconds=OTP_TTL_SECONDS),
            )
        # After the row commit, deliberately: if the provider 503s the customer
        # retries and the resend path invalidates this orphan. The reverse order
        # would send an SMS whose code was never stored.
        await self._notifications.send_sms(
            tenant_id,
            phone=phone,
            body=body,
            kind=MessageKind.OTP.value,
            log_body=mask_otp_body(body, code),
        )

    async def verify(self, tenant_id: UUID, raw_phone: str, code: str) -> VerifyResult:
        phone = normalize_israeli_mobile(raw_phone)
        now = self._clock()
        async with tenant_session(self._session_factory, tenant_id) as session:
            row = await self._otp_codes.latest_active_by_phone(session, tenant_id, phone=phone)
            if row is None:
                raise OtpInvalidError
            # Increment BEFORE comparing: a crash between compare and record
            # must never grant a free guess.
            attempts = await self._otp_codes.increment_attempts(session, tenant_id, row.id)
            if attempts > OTP_MAX_VERIFY_ATTEMPTS:
                raise OtpInvalidError
            if row.expires_at <= now:
                raise OtpExpiredError
            if not self._matches(code, row.code_hash):
                raise OtpInvalidError

            token = generate_session_token()
            expires_at = now + datetime.timedelta(seconds=VERIFICATION_TOKEN_TTL_SECONDS)
            consumed = await self._otp_codes.mark_consumed(
                session,
                tenant_id,
                row.id,
                verification_token_hash=hash_token(token),
                verification_expires_at=expires_at,
            )
            if consumed is None:
                # A raced double-verify lost the guarded UPDATE — same outcome
                # as a wrong code, and just as indistinguishable.
                raise OtpInvalidError
            return VerifyResult(verification_token=token, expires_at=expires_at)

    async def consume_verification(
        self, session: AsyncSession, tenant_id: UUID, *, raw_phone: str, verification_token: str
    ) -> bool:
        """Session-taking by design: F13 calls this inside the booking
        transaction so the customer INSERT and the token burn commit or roll
        back together."""
        phone = normalize_israeli_mobile(raw_phone)
        return await self._otp_codes.consume_verification(
            session,
            tenant_id,
            phone=phone,
            verification_token_hash=hash_token(verification_token),
            now=self._clock(),
        )

    def _matches(self, code: str, stored_hash: str) -> bool:
        if hmac.compare_digest(hash_token(code), stored_hash):
            return True
        # Staging-only escape hatch; Settings forbids it in production at boot.
        return self._dev_code is not None and hmac.compare_digest(code, self._dev_code)
