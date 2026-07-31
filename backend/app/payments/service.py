"""GatewayCredentialService owns `tenant_gateway_credentials`; PaymentService
owns `payments`. Repositories never see an adapter, adapters never see the
database, and no feature code writes either table by any other path — F18's real
adapter, F19's webhook route and F19's expiry sweeper all come through here.

`DepositHold` and `Settlement` are declared HERE rather than in base.py because
both carry a `Payment` model and the port is not allowed to know one exists.
"""

import dataclasses
import datetime
import logging
from collections.abc import Callable, Mapping
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.rate_limit import FixedWindowRateLimiter
from app.db.repositories.audit_log import AuditLogRepository
from app.db.repositories.gateway_credentials import GatewayCredentialsRepository
from app.db.repositories.payments import PaymentsRepository
from app.db.tenant import tenant_session
from app.errors import DomainNotFoundError
from app.models.constants import AuditAction, GatewayCredentialStatus, PaymentStatus
from app.models.payment import Payment
from app.models.tenant_gateway_credential import TenantGatewayCredential
from app.payments.base import (
    GatewayCredentials,
    GatewayCredentialsRejectedError,
    GatewayNotConfiguredError,
    GatewayNotConnectedError,
    GatewayUnavailableError,
    GatewayWebhookInvalidError,
    PaymentAlreadyHeldError,
    PaymentGateway,
    WebhookEvent,
)
from app.payments.secretbox import SecretBox, SecretBoxNotConfiguredError, SecretDecryptError
from app.payments.validation import (
    ENCRYPTION_CONTEXT_PURPOSE,
    deserialize_credentials,
    scrub_provider_error,
    serialize_credentials,
    validate_credential_fields,
)

logger = logging.getLogger("app")

# UTC wall clock, injectable for expiry tests — the NotificationService.WallClock
# distinction: expiry is calendar time, rate-limit windows are elapsed time.
WallClock = Callable[[], datetime.datetime]


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


class GatewayThrottledError(Exception):
    """The connect or validate budget tripped. Its own class like every other
    throttle in this codebase; the F21 reparenting note on StorefrontThrottledError
    covers this one too."""


class GatewayNotFoundError(DomainNotFoundError):
    """Disconnect with nothing stored. Re-parented onto the shared base so the
    house 404 handler serves it with no new registration."""


@dataclasses.dataclass(frozen=True)
class GatewayStatus:
    """What `GET /manage/gateway` renders, in EVERY state. `connected` is
    tenant-level and `configured` is platform-level: two booleans because the two
    facts have different owners and different remedies — the operator fixes one,
    the boutique fixes the other.

    Carries no ciphertext, no key_ref, no validation_error and no field value.
    Reading status must never touch key material, which is why `status()` never
    decrypts."""

    provider: str | None
    configured: bool
    connected: bool
    status: str | None
    last_validated_at: datetime.datetime | None
    credential_fields: list[str]


@dataclasses.dataclass(frozen=True)
class DepositHold:
    payment: Payment
    # None ONLY on the converged path, and that is a deviation from the spec's
    # `redirect_url: str` worth a reviewer's eye. 0012 stores
    # provider_session_id but not the hosted-page URL, and D23 forbids a gateway
    # call on the converge path — so for a converged hold there is nothing
    # truthful to return. Typing it `str | None` forces F19 to decide what a
    # retry does (re-open from the session id, or wait out the hold) instead of
    # letting an empty string look like a working link.
    redirect_url: str | None
    # False == converged onto an existing live hold (D23). BookingClaim.created's
    # reason: F19 gates its side effects on "did this call actually change
    # anything", and a bare row cannot answer that.
    created: bool


@dataclasses.dataclass(frozen=True)
class Settlement:
    payment: Payment
    # False == a redelivery, a lost race, or a late settlement (D24).
    newly_settled: bool


class GatewayCredentialService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        gateway: PaymentGateway,
        secret_box: SecretBox,
        connect_limiter: FixedWindowRateLimiter,
        validate_limiter: FixedWindowRateLimiter,
        clock: WallClock = _utc_now,
    ) -> None:
        self._session_factory = session_factory
        self._gateway = gateway
        self._secret_box = secret_box
        self._connect_limiter = connect_limiter
        self._validate_limiter = validate_limiter
        self._clock = clock
        self._credentials = GatewayCredentialsRepository()
        self._audit = AuditLogRepository()

    @property
    def gateway(self) -> PaymentGateway:
        return self._gateway

    async def status(self, tenant_id: UUID) -> GatewayStatus:
        """Answers in every state and NEVER decrypts — a route that reports "are
        we connected" must not touch key material. 200 even with no adapter at
        all: a console that cannot read its own status cannot explain to the
        owner why deposits are unavailable."""
        provider = self._gateway.provider
        base = GatewayStatus(
            provider=provider,
            configured=self._gateway.is_configured,
            connected=False,
            status=None,
            last_validated_at=None,
            credential_fields=sorted(self._gateway.credential_fields),
        )
        if provider is None:
            return base
        row = await self._active(tenant_id, provider)
        if row is None:
            return base
        return dataclasses.replace(
            base,
            connected=row.status == GatewayCredentialStatus.VALID.value,
            status=row.status,
            last_validated_at=row.last_validated_at,
        )

    async def connect(
        self, tenant_id: UUID, *, fields: Mapping[str, str], actor_id: UUID
    ) -> GatewayStatus:
        """Validate the shape, ping the provider, encrypt — all OUTSIDE and
        BEFORE the transaction — then one transaction that supersedes, inserts
        and audits.

        The ORDERING is a correctness property, not a style choice (D4). A
        rejected credential set must leave the boutique's previous WORKING one
        untouched: she typed a typo, she did not ask to be disconnected. And the
        NotificationService.send_sms split applies too — a provider hang must
        never hold a DB transaction open."""
        provider = self._require_provider()
        key = f"gateway:connect:{tenant_id}"
        if self._connect_limiter.is_blocked(key):
            raise GatewayThrottledError
        self._connect_limiter.record_failure(key)

        cleaned = validate_credential_fields(fields, expected=self._gateway.credential_fields)
        credentials = GatewayCredentials(provider=provider, fields=cleaned)
        await self._ping(credentials)
        ciphertext = await self._encrypt(tenant_id, cleaned)

        now = self._clock()
        async with tenant_session(self._session_factory, tenant_id) as session:
            await self._credentials.soft_delete_active(
                session, tenant_id, provider=provider, now=now
            )
            await self._credentials.insert(
                session,
                tenant_id=tenant_id,
                provider=provider,
                ciphertext=ciphertext,
                key_ref=self._secret_box.key_ref,
                last_validated_at=now,
                created_by=actor_id,
            )
            # FIELD NAMES ONLY, never values — the containment rule that matters
            # more here than anywhere else in the codebase.
            await self._audit.record(
                session,
                tenant_id=tenant_id,
                action=AuditAction.GATEWAY_CONNECTED.value,
                actor_id=actor_id,
                entity="tenant_gateway_credentials",
                details={"provider": provider, "fields": sorted(cleaned)},
            )
        return await self.status(tenant_id)

    async def revalidate(self, tenant_id: UUID, *, actor_id: UUID) -> GatewayStatus:
        """Decrypt, ping, write the outcome — and audit EVERY outcome (D26).

        `status='invalid'` is written ONLY for GatewayCredentialsRejectedError. A
        GatewayUnavailableError leaves `status` AND `last_validated_at` untouched
        and surfaces 503: a provider blip is not evidence that a merchant account
        is bad, and marking it invalid would take deposits offline for a boutique
        whose credentials are fine. Same asymmetry as the decrypt carve-out."""
        provider = self._require_provider()
        key = f"gateway:validate:{tenant_id}"
        if self._validate_limiter.is_blocked(key):
            raise GatewayThrottledError
        self._validate_limiter.record_failure(key)

        row = await self._active(tenant_id, provider)
        if row is None:
            raise GatewayNotConnectedError
        credentials = await self._decrypt(tenant_id, row.ciphertext, provider=provider)

        try:
            await self._ping(credentials)
        except GatewayCredentialsRejectedError as exc:
            detail = scrub_provider_error(exc, secrets=credentials.fields.values())
            await self._write_outcome(
                tenant_id,
                row.id,
                actor_id=actor_id,
                status=GatewayCredentialStatus.INVALID.value,
                validation_error=detail,
                action=AuditAction.GATEWAY_VALIDATION_FAILED,
                provider=provider,
            )
            return await self.status(tenant_id)

        await self._write_outcome(
            tenant_id,
            row.id,
            actor_id=actor_id,
            status=GatewayCredentialStatus.VALID.value,
            validation_error=None,
            action=AuditAction.GATEWAY_VALIDATED,
            provider=provider,
        )
        return await self.status(tenant_id)

    async def disconnect(self, tenant_id: UUID, *, actor_id: UUID) -> GatewayStatus:
        """No precondition on in-flight payments, deliberately (D20). Refusing a
        disconnect while a payment is pending inverts the incident case — a
        disconnect is precisely what an owner does when a key leaks — and a
        boutique with one stale pending row could never disconnect at all. The
        superseded row keeps its ciphertext so those in-flight charges can still
        be verified."""
        provider = self._require_provider()
        now = self._clock()
        async with tenant_session(self._session_factory, tenant_id) as session:
            removed = await self._credentials.soft_delete_active(
                session, tenant_id, provider=provider, now=now
            )
            if removed == 0:
                raise GatewayNotFoundError
            await self._audit.record(
                session,
                tenant_id=tenant_id,
                action=AuditAction.GATEWAY_DISCONNECTED.value,
                actor_id=actor_id,
                entity="tenant_gateway_credentials",
                details={"provider": provider},
            )
        return await self.status(tenant_id)

    async def credentials_for(self, tenant_id: UUID) -> GatewayCredentials:
        """The USE path: authorisation to move NEW money. Called by open_deposit
        only."""
        provider = self._require_provider()
        row = await self._active(tenant_id, provider)
        if row is None or row.status != GatewayCredentialStatus.VALID.value:
            raise GatewayNotConnectedError
        return await self._decrypt(tenant_id, row.ciphertext, provider=provider)

    async def verification_credentials_for(self, tenant_id: UUID) -> GatewayCredentials:
        """The VERIFICATION path (D20): the newest row for (tenant, provider),
        ignoring deleted_at AND status. Called by settle_from_webhook only.

        Verifying a signature is not authorisation to charge — it is reading
        evidence about money that has ALREADY moved. Resolving this through
        credentials_for would mean a disconnect (or an 'invalid' flip)
        permanently strands every in-flight payment: the charge succeeds at the
        provider, the webhook can never be verified, the row stays pending, the
        sweeper frees the seat, and the webhook secret sits in a soft-deleted row
        no code path reads. That is a money-loss hole, and F18 and F19 would both
        have inherited it."""
        provider = self._require_provider()
        async with tenant_session(self._session_factory, tenant_id) as session:
            row = await self._credentials.newest_for_provider(session, tenant_id, provider=provider)
        if row is None:
            raise GatewayNotConnectedError
        return await self._decrypt(tenant_id, row.ciphertext, provider=provider)

    # --- internals ---

    def _require_provider(self) -> str:
        provider = self._gateway.provider
        if provider is None or not self._gateway.is_configured:
            raise GatewayNotConfiguredError
        if not self._secret_box.is_configured:
            raise SecretBoxNotConfiguredError
        return provider

    async def _active(self, tenant_id: UUID, provider: str) -> TenantGatewayCredential | None:
        async with tenant_session(self._session_factory, tenant_id) as session:
            return await self._credentials.active_for_provider(
                session, tenant_id, provider=provider
            )

    async def _ping(self, credentials: GatewayCredentials) -> None:
        """Everything that is not a clean refusal is GatewayUnavailableError, and
        provider text never escapes: the exception is logged with the CREDENTIAL
        OBJECT, whose __repr__ prints field names only."""
        try:
            await self._gateway.validate_credentials(credentials)
        except (GatewayCredentialsRejectedError, GatewayNotConfiguredError):
            raise
        except Exception as exc:
            logger.warning("gateway credential validation failed for %r", credentials, exc_info=exc)
            raise GatewayUnavailableError from exc

    async def _encrypt(self, tenant_id: UUID, fields: Mapping[str, str]) -> str:
        try:
            return await self._secret_box.encrypt(
                serialize_credentials(fields), context=_context(tenant_id)
            )
        except SecretBoxNotConfiguredError:
            raise
        except Exception as exc:
            logger.warning("secret box encrypt failed for tenant %s", tenant_id, exc_info=exc)
            raise GatewayUnavailableError from exc

    async def _decrypt(
        self, tenant_id: UUID, ciphertext: str, *, provider: str
    ) -> GatewayCredentials:
        """A decrypt failure is GatewayUnavailableError and does NOT flip status
        to 'invalid'. A blob we cannot open is OUR problem — a rotated key, a
        wrong context, an operator error. Marking it invalid would render "your
        merchant account was refused" to an owner whose account is fine and send
        her to a provider's support desk over our bug."""
        try:
            plaintext = await self._secret_box.decrypt(ciphertext, context=_context(tenant_id))
            return GatewayCredentials(provider=provider, fields=deserialize_credentials(plaintext))
        except SecretBoxNotConfiguredError:
            raise
        except (SecretDecryptError, ValueError) as exc:
            logger.warning("secret box decrypt failed for tenant %s", tenant_id, exc_info=exc)
            raise GatewayUnavailableError from exc

    async def _write_outcome(
        self,
        tenant_id: UUID,
        credential_id: UUID,
        *,
        actor_id: UUID,
        status: str,
        validation_error: str | None,
        action: AuditAction,
        provider: str,
    ) -> None:
        now = self._clock()
        async with tenant_session(self._session_factory, tenant_id) as session:
            await self._credentials.mark_status(
                session,
                tenant_id,
                credential_id,
                status=status,
                last_validated_at=now,
                validation_error=validation_error,
            )
            # Same transaction as the write it describes, and a REAL actor_id:
            # AuditLogRepository.record defaults it to None, so an omitted
            # argument is silent rather than a type error and an owner tap would
            # be indistinguishable from a system-initiated sweep (D26).
            await self._audit.record(
                session,
                tenant_id=tenant_id,
                action=action.value,
                actor_id=actor_id,
                entity="tenant_gateway_credentials",
                details={"provider": provider, "status": status},
            )


class PaymentService:
    """The single writer of `payments`."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        gateway: PaymentGateway,
        credentials: GatewayCredentialService,
        clock: WallClock = _utc_now,
    ) -> None:
        self._session_factory = session_factory
        self._gateway = gateway
        self._credentials = credentials
        self._clock = clock
        self._payments = PaymentsRepository()
        self._audit = AuditLogRepository()

    async def open_deposit(
        self,
        tenant_id: UUID,
        *,
        booking_id: UUID,
        amount_agorot: int,
        hold_seconds: int,
        return_url: str,
    ) -> DepositHold:
        """The ONLY path that inserts a payment row. The ordering is the whole
        point (D23) — the create_booking sequence, same lock, same key:

        1. credentials_for  — the USE path, so a disconnected or invalid
           credential 409s here and nothing is minted at the provider.
        2. pg_advisory_xact_lock(hashtext(tenant_id)) — everything from here to
           COMMIT holds it.
        3. live_pending_for_booking — READ FIRST, and converge. An existing hold
           is returned unchanged with its stored session id, created=False, and
           NO gateway call at all.
        4. Only NOW create_session, then insert.
        5. IntegrityError -> PaymentAlreadyHeldError, the backstop for a writer
           that skipped the lock, mapped exactly as create_booking maps
           SlotUnavailableError. Never an unhandled 500.

        The gateway call is INSIDE the lock and AFTER the read, not before
        either. Minting a hosted-page session before the row that can refuse the
        insert leaves a live, payable session at the provider with no row behind
        it — and if she pays on it, settle_from_webhook matches no row and the
        charge is unrecorded. A provider hang now holds the per-tenant lock,
        which is the accepted cost: the alternative loses money.
        """
        provider = self._require_provider()
        credentials = await self._credentials.credentials_for(tenant_id)
        now = self._clock()

        async with tenant_session(self._session_factory, tenant_id) as session:
            # ponytail: one lock per tenant serializes all deposit opens, the
            # create_booking key verbatim; per-booking lock keys if pilot
            # throughput ever cares.
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:tenant_id))"),
                {"tenant_id": str(tenant_id)},
            )
            existing = await self._payments.live_pending_for_booking(
                session, tenant_id, booking_id=booking_id
            )
            if existing is not None:
                # No gateway call at ALL on this path (D23) — which is also why
                # redirect_url is None: 0012 stores the session id, not the
                # hosted-page URL, and minting a fresh one here is exactly the
                # orphaned-session bug the ordering exists to prevent.
                return DepositHold(payment=existing, redirect_url=None, created=False)

            payment_session = await self._gateway.create_session(
                credentials,
                amount_agorot=amount_agorot,
                reference=str(booking_id),
                return_url=return_url,
                expires_in=hold_seconds,
            )
            try:
                row = await self._payments.insert(
                    session,
                    tenant_id=tenant_id,
                    booking_id=booking_id,
                    provider=provider,
                    amount_agorot=amount_agorot,
                    provider_session_id=payment_session.provider_session_id,
                    hold_expires_at=now + datetime.timedelta(seconds=hold_seconds),
                )
            except IntegrityError as exc:
                raise PaymentAlreadyHeldError from exc
            return DepositHold(
                payment=row,
                redirect_url=payment_session.redirect_url,
                created=True,
            )

    async def settle_from_webhook(
        self, tenant_id: UUID, *, body: bytes, signature: str
    ) -> Settlement:
        """Verify, then ONE guarded statement (D24).

        Deliberately does NOT touch `bookings`. Flipping a booking to confirmed
        and firing F16's confirmation SMS is F19's transaction; a payments
        service reaching into the booking domain is the coupling that would make
        F19 unable to order its own writes.
        """
        provider = self._require_provider()
        credentials = await self._credentials.verification_credentials_for(tenant_id)

        try:
            event = self._gateway.verify_webhook(credentials, body=body, signature=signature)
        except GatewayWebhookInvalidError:
            # COMMIT BEFORE RAISE. tenant_session is session.begin(), so raising
            # inside the block would roll this row away and a forged signature
            # would leave no trace at all
            # (.memory/patterns/commit-before-raise-in-tenant-session.md).
            async with tenant_session(self._session_factory, tenant_id) as session:
                await self._audit.record(
                    session,
                    tenant_id=tenant_id,
                    action=AuditAction.GATEWAY_WEBHOOK_REJECTED.value,
                    entity="payments",
                    details={"provider": provider},
                )
            raise

        now = self._clock()
        # Set inside the transaction, acted on AFTER it — a mismatch has to
        # leave its evidence in a transaction that commits, and the transaction
        # that reports the failure raises.
        mismatch_id: UUID | None = None
        async with tenant_session(self._session_factory, tenant_id) as session:
            already = await self._payments.by_provider_transaction_id(
                session, tenant_id, provider=provider, transaction_id=event.provider_transaction_id
            )
            if already is not None:
                # The cheap sequential path: a redelivery of something already
                # settled writes nothing.
                return Settlement(payment=already, newly_settled=False)

            row = await self._payments.by_provider_session_id(
                session, tenant_id, provider=provider, session_id=event.provider_session_id
            )
            if row is None:
                raise GatewayWebhookInvalidError

            if event.amount_agorot == row.amount_agorot:
                settled = await self._payments.settle(
                    session,
                    tenant_id,
                    row.id,
                    provider_transaction_id=event.provider_transaction_id,
                    paid_at=now,
                )
                if settled is not None:
                    return Settlement(payment=settled, newly_settled=True)
                return await self._explain_missed_settlement(session, tenant_id, row.id, provider)
            mismatch_id = row.id

        # Outside the transaction above, so the evidence COMMITS (D14): the
        # amount assertion is attacker-reachable input even behind a valid
        # signature — pre-decided #21 makes the amount check doctrine for
        # refunds, and a settlement is the same class of write with the same
        # failure mode.
        await self._record_amount_mismatch(tenant_id, mismatch_id, provider=provider, event=event)
        raise GatewayWebhookInvalidError

    async def _explain_missed_settlement(
        self, session: AsyncSession, tenant_id: UUID, payment_id: UUID, provider: str
    ) -> Settlement:
        """The guarded UPDATE did not fire, and the TWO reasons are not the same
        event (D24)."""
        row = await self._payments.by_id(session, tenant_id, payment_id)
        if row is None:  # pragma: no cover — it was read one statement ago
            raise GatewayWebhookInvalidError
        if row.status == PaymentStatus.PAID.value:
            # A concurrent delivery won the race. Exactly one of two concurrent
            # redeliveries can transition the row, because the guard is evaluated
            # by the database under the row lock, not by us.
            return Settlement(payment=row, newly_settled=False)
        # The hold already expired: REAL MONEY was taken against a hold that no
        # longer exists. Durable and distinguishable is F17's whole obligation
        # here — Gate 1 Q4 rules it HONOURED, and F19 owns the rebind-or-alert.
        # Not silently discarded, not auto-refunded (the port ships no refund()).
        detail = f"late settlement: hold was {row.status}"
        marked = await self._payments.record_error(session, tenant_id, payment_id, error=detail)
        await self._audit.record(
            session,
            tenant_id=tenant_id,
            action=AuditAction.GATEWAY_LATE_SETTLEMENT.value,
            entity="payments",
            details={"provider": provider, "payment_id": str(payment_id), "status": row.status},
        )
        return Settlement(payment=marked if marked is not None else row, newly_settled=False)

    async def _record_amount_mismatch(
        self, tenant_id: UUID, payment_id: UUID, *, provider: str, event: WebhookEvent
    ) -> None:
        """Its own committed transaction, then the caller raises. `status` stays
        'pending' — inventing a 'failed' transition here would pre-empt F19's
        sweeper policy."""
        amount = event.amount_agorot
        async with tenant_session(self._session_factory, tenant_id) as session:
            await self._payments.record_error(
                session, tenant_id, payment_id, error=f"amount mismatch: webhook claimed {amount}"
            )
            await self._audit.record(
                session,
                tenant_id=tenant_id,
                action=AuditAction.GATEWAY_AMOUNT_MISMATCH.value,
                entity="payments",
                details={
                    "provider": provider,
                    "payment_id": str(payment_id),
                    "claimed_agorot": amount,
                },
            )

    def _require_provider(self) -> str:
        provider = self._gateway.provider
        if provider is None or not self._gateway.is_configured:
            raise GatewayNotConfiguredError
        return provider


def _context(tenant_id: UUID) -> dict[str, str]:
    """Every encrypt and decrypt passes this. KMS binds it into the AEAD's
    additional authenticated data, so a ciphertext copied into another tenant's
    row cannot be decrypted — isolation on top of RLS."""
    return {"tenant_id": str(tenant_id), "purpose": ENCRYPTION_CONTEXT_PURPOSE}
