"""The provider's webhook, the bride's poll, and the booking-side reaction to a
settlement.

**A sibling router on /storefront, not a route on `storefront_router`.** The
`otp_router` / `booking_router` precedent, for a reason of its own: the read
router carries a per-tenant `_throttle`, and a 429 against a provider's retry
burst turns a transient outage into permanently unconfirmed bookings — money
taken, seat held, nobody told. Anonymous, tenant-from-Host, cookie-blind; CSRF
is structurally N/A because no cookie is read here, so there is nothing a
cross-site request could ride. Authenticity is the HMAC signature and nothing
else, which is why the route hands `verify_webhook` the RAW body bytes and never
a re-serialised model.

**The status contract is D9's.** 200 on every non-forgery outcome — paid,
decline, redelivery, duplicate transaction, late settlement — because a provider
reads anything else as "retry". 400 on the three conditions that raise
`GatewayWebhookInvalidError` from `PaymentService`: a bad signature, an amount
mismatch, and a signature-valid webhook matching no payment row. All three
already commit their evidence before raising, and `main.py` already maps the
error.

**The booking-side reaction is a second transaction, and that is unavoidable.**
`settle_from_webhook` commits `payments -> paid` inside its own `tenant_session`
and hands back a `Settlement`; `PaymentService` opens sessions from its own
factory and deliberately does not touch `bookings`. So the confirm below is a
separate transaction whose exactly-once guarantee is its own guarded UPDATE,
evaluated by Postgres under the row lock — never our bookkeeping.
"""

import dataclasses
import datetime
import logging
import uuid
from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.booking.comms import BookingCommsService, CommsTenant, upsert_reminder
from app.booking.slots import materialize_slots
from app.booking.tokens import manage_token_hash, mint_manage_token
from app.db.repositories.audit_log import AuditLogRepository
from app.db.repositories.availability import (
    AvailabilityExceptionsRepository,
    AvailabilityRulesRepository,
)
from app.db.repositories.bookings import BookingsRepository
from app.db.repositories.payments import PaymentsRepository
from app.db.repositories.scheduled_messages import ScheduledMessagesRepository
from app.db.tenant import tenant_session
from app.errors import DomainNotFoundError
from app.models.booking import Booking
from app.models.constants import AuditAction, BookingStatus, PaymentStatus
from app.models.payment import Payment
from app.notifications.service import WallClock
from app.payments.base import GatewayNotConfiguredError, WebhookEvent
from app.payments.service import (
    DECLINE_ERROR,
    GatewayCredentialService,
    PaymentService,
    Settlement,
)
from app.storefront.validation import BOUTIQUE_TIMEZONE
from app.tenancy.middleware import TenantContext, get_current_tenant

logger = logging.getLogger("app")

NO_STORE = "no-store"

# What the shipped LemonSqueezy adapter reads (`lemonsqueezy.py`), so a real
# provider webhook needs no route edit. A missing header arrives as "" and
# simply does not match — the verifier's 400, with its audit row, rather than a
# schema 422 that would leave no evidence at all.
SIGNATURE_HEADER = "x-signature"

# A provider-minted opaque id. The ceiling only stops a megabyte from reaching a
# query; the real check is that it matches a row this tenant owns.
MAX_SESSION_ID_LENGTH = 256


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


class DepositReaction(StrEnum):
    """What F19 does about a settlement (D4)."""

    CONFIRM = "confirm"
    HONOUR = "honour"
    IGNORE = "ignore"


def deposit_reaction(settlement: Settlement) -> DepositReaction:
    """Branch on `settlement.payment.status`, NEVER on `newly_settled`.

    `newly_settled` is False on FIVE distinct outcomes — a redelivery of an
    already-settled transaction, a decline, a concurrent delivery that lost the
    race, a different transaction against a paid row, and a late settlement —
    and two of those five must act. So the row's own status is the discriminator
    and `newly_settled` is not consulted here at all.

    - `paid` -> CONFIRM, whether or not this delivery is the one that settled it.
      Against an already-confirmed booking the guarded UPDATE matches nothing and
      does exactly nothing; against a booking stranded at `pending_payment` by a
      crash between the two transactions it fires once and repairs it. That
      repair is the whole reason this row is not "nothing".
    - `expired` -> HONOUR: her money arrived after the sweeper released the seat.
    - `pending` -> IGNORE: a decline. The sweeper frees the seat on its own clock,
      and a retried card can still settle the same hold.
    - anything else -> IGNORE and log. `failed`, `refund_due`, `refunded` and
      `forfeited` have no writer today; a settlement arriving against one is an
      anomaly worth a line, not an action.
    """
    status = settlement.payment.status
    if status == PaymentStatus.PAID.value:
        return DepositReaction.CONFIRM
    if status == PaymentStatus.EXPIRED.value:
        return DepositReaction.HONOUR
    return DepositReaction.IGNORE


def is_declined(payment: Payment) -> bool:
    """Her card was refused and the hold is still hers to retry.

    **The discriminator is `error`, not `status`, and that is not a shortcut.**
    F17 leaves a declined hold at 'pending' on purpose — `_record_decline` says
    why at length — so `status` cannot tell "she was declined" apart from "she
    has not paid yet", and the only value that ever means declined ('failed') is
    written solely by `record_unavailable`, which leaves `provider_session_id`
    NULL by construction and so can never be reached by this poll's lookup at
    all. `DECLINE_ERROR` is the one fact on the row that carries the answer.

    `record_error` OVERWRITES the column on every event, which is exactly right
    here: the field means "the last thing that happened to this hold". A decline
    followed by an amount mismatch is no longer a decline, and the equality
    against the constant — rather than a substring — is what keeps the mismatch,
    duplicate-transaction and late-settlement writers out of this answer.
    """
    return payment.status == PaymentStatus.PENDING.value and payment.error == DECLINE_ERROR


@dataclasses.dataclass(frozen=True)
class PaymentStatusFacts:
    """What the return page polls for, and deliberately nothing else: no name,
    no phone, no appointment detail. Possession of the session id authorises a
    status read and nothing more."""

    booking_status: str
    payment_status: str
    paid_at: datetime.datetime | None
    declined: bool


class PaymentStatusRequest(BaseModel):
    """Keyed on the provider session id, NOT the manage token (D13).

    The token cannot work here three times over: `BookingCreateResponse` carries
    no token, the deposit path suppresses the confirmation SMS so she never
    receives the manage link either, and `set_manage_token_hash` overwrites the
    hash unconditionally while `by_manage_token_hash` is the only lookup — so a
    token-keyed poll would start 404-ing at PRECISELY the moment it should
    return paid, and a bride who paid would sit on a spinner forever.

    The session id costs no new column and no rotation hazard: it is already
    client-visible by construction, because it is embedded in the hosted-page URL
    the browser is about to visit.
    """

    payment_session_id: str = Field(min_length=1, max_length=MAX_SESSION_ID_LENGTH)


class PaymentStatusResponse(BaseModel):
    booking_status: str
    payment_status: str
    paid_at: datetime.datetime | None
    declined: bool


class DepositBookingService:
    """The booking-side half of the deposit flow: what happens to a booking when
    its payment settles, and what happens when it settles too late.

    It is not `PaymentService` and must not become it — `models/payment.py` makes
    `PaymentService` the single writer of `payments`, so `settle_late` is reached
    only through `honour_late_settlement` and never from here (D20).
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        payments: PaymentService,
        credentials: GatewayCredentialService,
        comms: BookingCommsService,
        clock: WallClock = _utc_now,
    ) -> None:
        self._session_factory = session_factory
        self._payments = payments
        self._credentials = credentials
        self._comms = comms
        self._clock = clock
        self._bookings = BookingsRepository()
        self._payment_rows = PaymentsRepository()
        self._scheduled = ScheduledMessagesRepository()
        self._rules = AvailabilityRulesRepository()
        self._exceptions = AvailabilityExceptionsRepository()
        self._audit = AuditLogRepository()

    # --- the webhook -------------------------------------------------------

    async def settle(self, tenant: CommsTenant, *, body: bytes, signature: str) -> None:
        settlement = await self._payments.settle_from_webhook(
            tenant.id, body=body, signature=signature
        )
        outcome = deposit_reaction(settlement)
        if outcome is DepositReaction.CONFIRM:
            await self._confirm(tenant, booking_id=settlement.payment.booking_id)
        elif outcome is DepositReaction.HONOUR:
            await self._honour(tenant, payment=settlement.payment, body=body, signature=signature)
        else:
            logger.info(
                "settlement for payment %s left status %s — no booking action",
                settlement.payment.id,
                settlement.payment.status,
            )

    async def payment_status(
        self, tenant_id: uuid.UUID, *, provider_session_id: str
    ) -> PaymentStatusFacts:
        provider = self._credentials.gateway.provider
        if provider is None:
            raise GatewayNotConfiguredError
        async with tenant_session(self._session_factory, tenant_id) as session:
            payment = await self._payment_rows.by_provider_session_id(
                session, tenant_id, provider=provider, session_id=provider_session_id
            )
            if payment is None:
                raise DomainNotFoundError("no payment for that session")
            booking = await self._bookings.by_id(session, tenant_id, payment.booking_id)
            if booking is None:  # pragma: no cover — a payment cannot outlive its booking
                raise DomainNotFoundError("no payment for that session")
            return PaymentStatusFacts(
                booking_status=booking.status,
                payment_status=payment.status,
                paid_at=payment.paid_at,
                declined=is_declined(payment),
            )

    # --- the confirm transaction (D3, D12, D13) ----------------------------

    async def _confirm(self, tenant: CommsTenant, *, booking_id: uuid.UUID) -> None:
        """One guarded UPDATE, and THAT is F19's idempotency key.

        `None` back means a prior delivery already confirmed it: no SMS, no
        reminder rewrite, no audit row. Exactly one delivery of N can win because
        the predicate is evaluated by Postgres under the row lock — not because
        we counted anything.

        The token is minted here and its hash committed in the same transaction:
        `manage_token_hash` is sha256 and `BookingClaim.manage_token` carries the
        raw value only at creation, so a confirmation deferred to webhook time
        cannot reuse it. The reminder row takes the SAME token through
        `upsert_reminder`'s `token` keyword rather than minting a second one.

        The reminder rewrite is not housekeeping — it is a bug fix with no other
        symptom. `create_booking` ALWAYS inserts the reminder row regardless of
        status, and `reminder_send_after` returns `now` for any lead between 2h
        and 24h; `drain_due` then re-reads the booking, sees `pending_payment`,
        and permanently cancels the row within 60 seconds — long before she has
        finished paying. She pays, gets confirmed, and silently never gets her
        reminder. For a >24h appointment the bug does not fire at all, which is
        what makes it the kind that ships green.
        """
        token = mint_manage_token()
        async with tenant_session(self._session_factory, tenant.id) as session:
            booking = await self._bookings.set_status(
                session,
                tenant.id,
                booking_id,
                to=BookingStatus.CONFIRMED.value,
                allowed_from=(BookingStatus.PENDING_PAYMENT.value,),
            )
            if booking is None:
                return
            await self._bookings.set_manage_token_hash(
                session, tenant.id, booking_id, token_hash=manage_token_hash(token)
            )
            await upsert_reminder(
                session,
                tenant_id=tenant.id,
                booking_id=booking_id,
                starts_at=booking.starts_at,
                now=self._clock(),
                bookings=self._bookings,
                scheduled=self._scheduled,
                token=token,
            )
            await self._audit.record(
                session,
                tenant_id=tenant.id,
                action=AuditAction.BOOKING_CONFIRMED.value,
                entity="bookings",
                details={"booking_id": str(booking_id), "via": "deposit_webhook"},
            )
        # Post-commit, and fire-and-forget: `send_confirmation` swallows both
        # provider exceptions after their evidence rows exist, so it cannot turn
        # a committed confirm into a 5xx the provider would retry.
        await self._comms.send_confirmation(tenant, booking=booking, manage_token=token)

    # --- the honour path (D5) ----------------------------------------------

    async def _honour(
        self, tenant: CommsTenant, *, payment: Payment, body: bytes, signature: str
    ) -> None:
        """Her money arrived after the hold expired: rebind if the seat is still
        free, alert if it is not. F17's Gate 1 Q4 ruled it HONOURED and the
        deposit marked paid; this is that ruling's booking half.

        There is one window this cannot repair, and it is stated rather than
        hidden: `honour_late_settlement` commits in its own transaction and
        writes `provider_transaction_id`, so a crash between it and the rebind
        below leaves a paid deposit on a cancelled booking that no redelivery
        re-enters (`by_provider_transaction_id` short-circuits). The
        `GATEWAY_LATE_SETTLEMENT` audit row and `payments.error` are what make it
        findable; the owner's console is where it is fixed.
        """
        event = await self._event(tenant.id, body=body, signature=signature)
        honoured = await self._payments.honour_late_settlement(
            tenant.id,
            payment_id=payment.id,
            transaction_id=event.provider_transaction_id,
            paid_at=self._clock(),
        )
        if honoured is None:
            # A prior delivery already honoured it. Stop rather than run the seat
            # decision — and the SMS — twice.
            return

        async with tenant_session(self._session_factory, tenant.id) as session:
            booking = await self._bookings.by_id(session, tenant.id, honoured.booking_id)
        if booking is None:  # pragma: no cover — a payment cannot outlive its booking
            logger.warning("late settlement %s has no booking to rebind", honoured.id)
            return

        now = self._clock()
        token = mint_manage_token()
        rebound: Booking | None = None
        reason = "seat_taken"
        try:
            async with tenant_session(self._session_factory, tenant.id) as session:
                # The create_booking key, verbatim: every seat decision for this
                # tenant serializes on it, so the two occupancy reads below and
                # the UPDATE that acts on them cannot straddle another claim.
                await session.execute(
                    text("SELECT pg_advisory_xact_lock(hashtext(:tenant_id))"),
                    {"tenant_id": str(tenant.id)},
                )
                rebound = await self._rebind(session, tenant.id, booking, now=now, token=token)
        except IntegrityError:
            # CAUGHT HERE, deliberately, and mapped to the alert branch. There is
            # no IntegrityError handler in main.py, and a 500 on this path is
            # UNRECOVERABLE: `settle_late` already committed the transaction id,
            # so every provider retry now hits `by_provider_transaction_id`'s
            # early return and the money is stranded with nothing acting on it.
            # This is `create_booking`'s IntegrityError backstop applied to a path
            # where the correct answer is not an error at all.
            logger.warning("late rebind of booking %s lost both indexes", booking.id)
            rebound = None
            reason = "index_conflict"

        if rebound is not None:
            await self._comms.send_confirmation(tenant, booking=rebound, manage_token=token)
            return

        # The booking stays cancelled, the payment stays paid, and both facts are
        # owner-visible. What the boutique does with the money from here is MD1 —
        # the deposit is hers and the owner reschedules her off this very row.
        # Its own transaction because the one above may have been poisoned by the
        # IntegrityError caught overhead.
        async with tenant_session(self._session_factory, tenant.id) as session:
            await self._audit.record(
                session,
                tenant_id=tenant.id,
                action=AuditAction.DEPOSIT_LATE_UNRESOLVED.value,
                entity="bookings",
                details={
                    "booking_id": str(booking.id),
                    "payment_id": str(honoured.id),
                    "reason": reason,
                },
            )
        # MD2: within one worker tick she knows her money is safe and a call is
        # coming. This is the only path in the flow where a customer's money moved
        # and nothing else would tell her.
        await self._comms.notify_payment_received_no_slot(tenant, booking=booking)

    async def _rebind(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        booking: Booking,
        *,
        now: datetime.datetime,
        token: str,
    ) -> Booking | None:
        """Both occupancy facts, then one guarded UPDATE. `None` is not an error
        — it is D5 step 4, the honest answer to a seat that is no longer free."""
        seat_index = await self._free_seat(session, tenant_id, booking=booking, now=now)
        if seat_index is None:
            return None
        # 0009's index, and the read a narrower design would skip. If she already
        # rebooked that instant herself after her seat was freed — the ordinary
        # consequence of the abandoned-hold race, and what 0009's own comment
        # describes — reinstating the cancelled row would make two live rows for
        # (tenant, customer, starts_at) and raise. ONE DEPOSIT MUST NOT BUY TWO
        # LIVE APPOINTMENTS.
        other = await self._bookings.active_at(
            session, tenant_id, customer_id=booking.customer_id, starts_at=booking.starts_at
        )
        if other is not None and other.id != booking.id:
            return None
        rebound = await self._bookings.rebind(
            session,
            tenant_id,
            booking.id,
            seat_index=seat_index,
            # `cancelled` is the ordinary case; `pending_payment` is the belt for
            # the sweeper ordering race, where the payments UPDATE has committed
            # but the booking cancel has not yet been observed.
            allowed_from=(BookingStatus.CANCELLED.value, BookingStatus.PENDING_PAYMENT.value),
            # Without the clock bound a delivery hours late would flip a PAST
            # booking to confirmed, mint a fresh manage token, and text her that
            # an appointment which has already happened is confirmed.
            not_before=now,
        )
        if rebound is None:
            return None
        await self._bookings.set_manage_token_hash(
            session, tenant_id, booking.id, token_hash=manage_token_hash(token)
        )
        await upsert_reminder(
            session,
            tenant_id=tenant_id,
            booking_id=booking.id,
            starts_at=rebound.starts_at,
            now=now,
            bookings=self._bookings,
            scheduled=self._scheduled,
            token=token,
        )
        await self._audit.record(
            session,
            tenant_id=tenant_id,
            action=AuditAction.DEPOSIT_LATE_HONOURED.value,
            entity="bookings",
            details={"booking_id": str(booking.id), "seat_index": seat_index},
        )
        return rebound

    async def _free_seat(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        booking: Booking,
        now: datetime.datetime,
    ) -> int | None:
        """The lowest free seat below the slot's capacity, or None.

        `create_booking`'s seat arithmetic, fed from the grid it is fed from —
        but NOT through `offered_slot`, and that is the one deliberate
        difference. `materialize_slots` DROPS a full slot rather than marking it,
        so passing real booked counts would return None in exactly D5's belt
        case: a still-live `pending_payment` hold of HER OWN is what fills the
        slot, and the result would be the FALSE "seat taken" alert that widening
        `allowed_from` exists to prevent. So capacity comes from the grid and
        occupancy comes from `active_seats_at`, which is 0008's index and which
        we can ask about her row specifically.

        A missing slot is the honest None: the day was closed, the rule deleted,
        or the instant is already past — `materialize_slots` filters on
        `instant > now`, which is the same bound `rebind` re-asserts in SQL.
        """
        wanted = booking.starts_at.astimezone(datetime.UTC)
        target_date = wanted.astimezone(BOUTIQUE_TIMEZONE).date()
        slots = materialize_slots(
            rules=await self._rules.list_active(session, tenant_id),
            exceptions=await self._exceptions.list_active(
                session, tenant_id, on_or_after=target_date, on_or_before=target_date
            ),
            booked={},
            window_start=target_date,
            window_end=target_date,
            now=now,
        )
        slot = next((row for row in slots if row.starts_at == wanted), None)
        if slot is None:
            return None
        occupied = await self._bookings.active_seats_at(session, tenant_id, starts_at=wanted)
        if booking.status != BookingStatus.CANCELLED.value:
            # The belt case again: her own hold is still live, so `active_seats_at`
            # counts its seat — and that seat is HERS. Discarding it is only safe
            # while the row is live; once cancelled the number is back in
            # circulation and very likely another bride's.
            occupied.discard(booking.seat_index)
        return next((index for index in range(1, slot.capacity + 1) if index not in occupied), None)

    async def _event(self, tenant_id: uuid.UUID, *, body: bytes, signature: str) -> WebhookEvent:
        """The provider transaction id, which `Settlement` does not carry.

        `settle_from_webhook` returns `Settlement(payment, newly_settled)` and no
        event, so the late branch — the only one that needs a transaction id, for
        `settle_late` to re-arm `by_provider_transaction_id` with — has to
        re-derive it. A second HMAC over bytes that just verified is cheap and it
        is confined to this branch; the proper fix is one field on `Settlement`,
        which belongs to the module that owns it.
        """
        credentials = await self._credentials.verification_credentials_for(tenant_id)
        return self._credentials.gateway.verify_webhook(credentials, body=body, signature=signature)


def get_deposit_service(request: Request) -> DepositBookingService:
    service: DepositBookingService = request.app.state.deposit_booking_service
    return service


def _no_store(response: Response) -> None:
    """Router-level like the OTP and booking surfaces: the poll names a real
    person's appointment status and is read from a phone, where bfcache is the
    default."""
    response.headers["cache-control"] = NO_STORE


router = APIRouter(prefix="/storefront", dependencies=[Depends(_no_store)])

Deposits = Annotated[DepositBookingService, Depends(get_deposit_service)]


def _comms_tenant(tenant: TenantContext) -> CommsTenant:
    return CommsTenant.from_settings(
        tenant_id=tenant.id, slug=tenant.slug, name=tenant.name, settings=tenant.settings
    )


@router.post("/payments/webhook")
async def payments_webhook(request: Request, service: Deposits) -> dict[str, str]:
    """RAW body bytes, never a parsed model: `verify_webhook` HMACs exactly what
    the provider signed, and a re-serialisation would reject every genuine
    delivery. The signature header is read as "" when absent so authenticity
    stays the verifier's call — its 400 leaves an audit row, a schema 422 would
    leave nothing."""
    tenant = get_current_tenant(request)
    await service.settle(
        _comms_tenant(tenant),
        body=await request.body(),
        signature=request.headers.get(SIGNATURE_HEADER, ""),
    )
    return {}


@router.post("/booking/payment-status")
async def payment_status(
    request: Request, service: Deposits, body: PaymentStatusRequest
) -> PaymentStatusResponse:
    """POST for a read, the `/booking/lookup` precedent: a GET would put the
    session id into every access log, proxy trace and Referer header on the
    path."""
    tenant = get_current_tenant(request)
    facts = await service.payment_status(tenant.id, provider_session_id=body.payment_session_id)
    return PaymentStatusResponse(
        booking_status=facts.booking_status,
        payment_status=facts.payment_status,
        paid_at=facts.paid_at,
        declined=facts.declined,
    )
