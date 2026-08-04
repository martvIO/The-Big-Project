"""The claim — where a slot the grid offers becomes a booking row, exactly once.

The whole feature's correctness lives in `create_booking`'s ordered steps inside
ONE `tenant_session`: token burn, terms check, snapshots, advisory lock, grid
re-materialization, customer upsert and the seat-indexed INSERT commit or roll
back together. The per-tenant advisory lock is the primary control and 0008's
partial unique index is the structural backstop — losing a race surfaces as
either a full grid or an IntegrityError, and both are the same 409 to a caller.

Exactly once in the other direction too: a create that replays an appointment
this customer already holds at this instant returns that booking rather than a
second one, guarded by 0009's index. See step 4b.
"""

import dataclasses
import datetime
import logging
import uuid
from collections.abc import Mapping

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.rate_limit import FixedWindowRateLimiter
from app.booking.comms import reminder_send_after
from app.booking.slots_io import offered_slot
from app.booking.tokens import manage_token_hash, mint_manage_token
from app.booking.validation import (
    SLOT_WINDOW_MAX_DAYS,
    BookingValidationError,
    validate_booking_request,
)
from app.catalog.validation import normalize_size_label
from app.db.repositories.appointment_types import AppointmentTypesRepository
from app.db.repositories.audit_log import AuditLogRepository
from app.db.repositories.availability import (
    AvailabilityExceptionsRepository,
    AvailabilityRulesRepository,
)
from app.db.repositories.bookings import BookingsRepository
from app.db.repositories.customers import CustomersRepository
from app.db.repositories.dress_variants import DressVariantsRepository
from app.db.repositories.dresses import DressesRepository
from app.db.repositories.payments import PaymentsRepository
from app.db.repositories.scheduled_messages import ScheduledMessagesRepository
from app.db.repositories.terms import TermsVersionsRepository
from app.db.tenant import tenant_session
from app.errors import DomainNotFoundError
from app.models.appointment_type import AppointmentType
from app.models.booking import Booking
from app.models.constants import AuditAction, BookingStatus, ScheduledMessageKind
from app.notifications.service import OtpService
from app.notifications.validation import normalize_israeli_mobile
from app.payments.base import GatewayNotConnectedError, GatewayUnavailableError
from app.payments.secretbox import SecretBoxNotConfiguredError, SecretDecryptError
from app.payments.service import GatewayCredentialService, PaymentService
from app.storefront.validation import Clock

logger = logging.getLogger("app")

# Past the grid's own publishable ceiling, so rejecting anything beyond it can
# never cost a real booking. TWO days of slack, not one: the ceiling is a
# boutique DATE and this is a UTC INSTANT, and an Israeli DST fall-back between
# now and the ceiling shifts every local wall time an hour later in UTC — which
# at +1 day ate the last half-hour of the final day's grid.
BOOKABLE_HORIZON = datetime.timedelta(days=SLOT_WINDOW_MAX_DAYS + 2)

# Spec default (D6). A constructor argument rather than a read of Settings here,
# so this module keeps no opinion about deployment: main.py passes
# `settings.deposit_hold_seconds`.
DEFAULT_DEPOSIT_HOLD_SECONDS = 900

# D11a's compensated set: every way `open_deposit` can fail with the booking
# ALREADY committed as `pending_payment`. `PaymentAlreadyHeldError` is
# deliberately absent — it means a hold exists, which is the converge case D11b
# covers, not a failure to take one.
DEPOSIT_COMPENSATED_ERRORS = (
    GatewayUnavailableError,
    GatewayNotConnectedError,
    SecretDecryptError,
    SecretBoxNotConfiguredError,
)


def deposit_due(
    settings: Mapping[str, object] | None,
    appointment_type: AppointmentType,
    *,
    gateway_connected: bool,
) -> bool:
    """D19's predicate, and the ONLY place it is spelled.

        deposits_enabled AND deposit_required AND amount > 0 AND connected

    Called by the storefront disclosure (`StorefrontService.list_appointment_types`)
    and by `create_booking` below, so the page a customer reads and the flow she
    then enters cannot disagree about whether money is owed.

    The MASTER TOGGLE WINS over the per-type flag and over a working gateway: a
    boutique who switches deposits off keeps taking bookings and stops
    collecting, exactly as F17's Q1 ruled for the not-connected case. An ABSENT
    toggle reads as off — `tenants.settings` starts `{}`, and the direction that
    fails is "took a deposit nobody asked for", not "booked without one".

    `gateway_connected` is `GatewayCredentialService.is_connected`'s answer,
    passed IN rather than read here, so a page listing N types buys one
    statement rather than N. It is the one argument a caller could get wrong,
    and both callers resolve it from `is_connected` inside the session they are
    already in — never from a weaker read (that is D10's whole subject).
    """
    toggles = settings.get("toggles") if settings is not None else None
    enabled = bool(toggles.get("deposits_enabled")) if isinstance(toggles, Mapping) else False
    return (
        enabled
        and appointment_type.deposit_required
        and (appointment_type.deposit_amount_agorot or 0) > 0
        and gateway_connected
    )


class BookingNotFoundError(DomainNotFoundError):
    """Unknown/archived appointment type or dress, or a size that is not one of
    the dress's active variants — indistinguishable 404s by design."""


class PhoneNotVerifiedError(Exception):
    """The verification token does not prove possession of this phone — absent,
    expired, already spent, or minted for a different number. Maps to 403
    PHONE_NOT_VERIFIED. Raised FIRST, before any lock is taken."""


class SlotUnavailableError(Exception):
    """The requested instant is not claimable — full, off-grid, past, or a
    closed day. Deliberately ONE error: distinguishing "taken" from "never
    offered" would tell a prober the shape of the boutique's grid. Maps to 409
    SLOT_UNAVAILABLE."""


class TermsStaleError(Exception):
    """The accepted terms version is not the current one — accepting a
    superseded policy is not acceptance. Maps to 409 TERMS_STALE."""


class BookingThrottledError(Exception):
    """A create budget — per phone or per tenant — is spent; main.py maps it to
    the shared 429 body.

    Both budgets are spent only by callers who proved possession of the phone,
    so the OTP send limits really are the outer cost gate. Meter an unproven
    caller and that claim inverts: the cheapest way to close a boutique for an
    hour becomes 60 requests carrying nothing but a hostname."""


@dataclasses.dataclass(frozen=True)
class BookingClaim:
    """What a create returns, and why it is no longer a bare `Booking`.

    Before F16 this method returned the row on BOTH the fresh-insert and the
    0009-replay path, so the caller could not tell them apart. F16 needs that
    distinction twice over: a replay must not resend the confirmation SMS, and
    sha256 is one-way — the raw manage token is unrecoverable the moment the
    transaction ends, so it has to travel out of here or not at all.

    `manage_token` is None on a replay. That is what makes "the replay does not
    resend" structural rather than a remembered `if` at the call site.
    """

    booking: Booking
    created: bool
    manage_token: str | None
    # D19, evaluated against the SAME predicate the storefront disclosed. It
    # rides out on the replay path too: whether money is owed is a property of
    # the booking, not of this request being the first one. Defaulted so a
    # caller that predates deposits reads "nothing to collect" rather than
    # inventing a charge.
    deposit_due: bool = False
    # The type's snapshot at claim time, carried because opening the hold is a
    # POST-COMMIT step outside this transaction and nothing out there has read
    # the appointment type. Meaningless when `deposit_due` is False.
    deposit_amount_agorot: int = 0


@dataclasses.dataclass(frozen=True)
class DepositOutcome:
    """What the post-commit deposit step (D11) tells the create handler.

    `deposit_due` here is the OUTCOME, not the claim's intent: MD4's
    compensating path answers False on a booking whose claim said True, because
    the gateway was unreachable and the appointment now stands with no deposit
    taken. The handler branches on THIS field for both the response and the
    confirmation SMS, so "texted her a confirmation before an agora was taken"
    and "took her deposit and told her nothing" are ruled out by one condition.

    `status` is the booking's status AFTER the step, and it has to travel here
    because the compensating transition wrote `confirmed` in its OWN session —
    the row the handler is holding still reads `pending_payment`.
    """

    status: str
    deposit_due: bool
    redirect_url: str | None = None
    payment_session_id: str | None = None


class BookingService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        otp: OtpService,
        create_limiter: FixedWindowRateLimiter,
        phone_limiter: FixedWindowRateLimiter,
        clock: Clock | None = None,
        gateway_credentials: GatewayCredentialService | None = None,
        payments: PaymentService | None = None,
        deposit_hold_seconds: int = DEFAULT_DEPOSIT_HOLD_SECONDS,
    ) -> None:
        self._session_factory = session_factory
        self._otp = otp
        # None = this deployment has not wired a gateway service at all, which
        # reads as NOT connected. Unwired must never read as connected: every
        # branch that could take money is opt-in.
        self._gateway_credentials = gateway_credentials
        # None here is NOT the same "opt-in" case: `deposit_due` already said
        # money is owed and the booking is already committed as
        # `pending_payment`, so an unwired PaymentService is a wiring bug, and
        # the safe answer to it is MD4's compensation — not a held seat nobody
        # can pay for.
        self._payments = payments
        self._deposit_hold_seconds = deposit_hold_seconds
        self._create_limiter = create_limiter
        # A SEPARATE instance, not a second key on create_limiter: max_attempts
        # lives on the limiter, not per key, so two keys on one instance share
        # one ceiling and the per-phone budget can never trip first. It would
        # be decoration.
        self._phone_limiter = phone_limiter
        self._clock = clock
        self._customers = CustomersRepository()
        self._bookings = BookingsRepository()
        self._types = AppointmentTypesRepository()
        self._terms = TermsVersionsRepository()
        self._dresses = DressesRepository()
        self._variants = DressVariantsRepository()
        self._rules = AvailabilityRulesRepository()
        self._exceptions = AvailabilityExceptionsRepository()
        self._scheduled = ScheduledMessagesRepository()
        self._payment_rows = PaymentsRepository()
        self._audit = AuditLogRepository()

    async def create_booking(
        self,
        tenant_id: uuid.UUID,
        *,
        raw_phone: str,
        verification_token: str,
        name: str,
        appointment_type_id: uuid.UUID,
        starts_at: datetime.datetime,
        terms_version: int,
        dress_id: uuid.UUID | None = None,
        dress_size: str | None = None,
        notes: str | None = None,
        marketing_consent: bool = False,
        settings: Mapping[str, object] | None = None,
    ) -> BookingClaim:
        """The spec's seven ordered steps. `starts_at` must be timezone-aware
        (the schema boundary enforces it); it is compared as a UTC instant
        against a freshly materialized grid, because the picker is not a
        security boundary.

        Everything happens in one transaction, deliberately: a claim that fails
        at ANY step — including losing the race — rolls back the token burn
        too, so the customer's verification survives to retry another slot.
        That rollback is why the create budget below is spent OUTSIDE the
        transaction's rollback semantics: a reusable token must not also buy
        unlimited attempts.

        F16 adds two writes to the same transaction and no third round trip: the
        manage token's hash lands on the INSERT, and the reminder's
        `scheduled_messages` row is written here rather than post-commit. Leaving
        the schedule to a post-commit block would let a crash between commit and
        block lose the reminder permanently, with nothing sweeping for the gap —
        same-database work belongs in the transaction. The SMS send is the only
        post-commit work, and the router owns it.
        """
        validate_booking_request(name=name, notes=notes, dress_id=dress_id, dress_size=dress_size)
        phone = normalize_israeli_mobile(raw_phone)

        now = self._clock() if self._clock is not None else datetime.datetime.now(datetime.UTC)
        now = now.astimezone(datetime.UTC)
        # BEFORE any arithmetic on starts_at. AwareDatetime accepts the entire
        # datetime range, and `.astimezone()` on a year-9999 instant raises
        # OverflowError — an unhandled 500 on an anonymous route. Comparison
        # itself cannot overflow, so this guard is total. It is the same 409 as
        # any other unoffered time, and leaks nothing.
        if not now < starts_at <= now + BOOKABLE_HORIZON:
            raise SlotUnavailableError

        # Two budgets on two limiters, CHECKED here and SPENT only once the
        # phone is proven (below). Metering an unproven caller would let anyone
        # exhaust a boutique's hourly budget with garbage tokens and lock every
        # real bride out — a denial of service costing the attacker nothing.
        #
        # The per-PHONE budget is the real control: it is what stops one
        # verified number from spending the whole boutique's allowance, which
        # matters because a failed claim rolls its own token burn back and the
        # number can retry. The per-TENANT budget above it is the runaway
        # brake, sized so it cannot fire on organic traffic.
        tenant_key = f"booking:create:{tenant_id}"
        phone_key = f"booking:create:{tenant_id}:{phone}"
        if self._create_limiter.is_blocked(tenant_key) or self._phone_limiter.is_blocked(phone_key):
            raise BookingThrottledError

        async with tenant_session(self._session_factory, tenant_id) as session:
            # 1. Prove the phone. First, so a caller who cannot gets no
            #    further and no lock is taken on their behalf.
            verified = await self._otp.consume_verification(
                session, tenant_id, raw_phone=raw_phone, verification_token=verification_token
            )
            if not verified:
                raise PhoneNotVerifiedError

            # Proven — now spend both budgets. The limiter is in-memory, so
            # this survives the rollback of a failed claim by design: one
            # verified phone gets a bounded number of attempts, not unlimited
            # ones off a single token that keeps un-burning itself.
            self._create_limiter.record_failure(tenant_key)
            self._phone_limiter.record_failure(phone_key)

            # 2. The appointment type and the CURRENT terms version.
            type_row = await self._types.by_id(session, tenant_id, appointment_type_id)
            if type_row is None:
                raise BookingNotFoundError
            current_terms = await self._terms.current(session, tenant_id)
            if current_terms is None or terms_version != current_terms.version:
                raise TermsStaleError

            # 2b. Is money owed? One indexed statement, read HERE — before the
            #     advisory lock, so it never extends the hold — and answered by
            #     the same predicate the storefront disclosed. The replay path
            #     below returns it too. Nothing else in this transaction moves
            #     for it: opening the hold is a later step's work.
            due = deposit_due(
                settings,
                type_row,
                gateway_connected=(
                    self._gateway_credentials is not None
                    and await self._gateway_credentials.is_connected(tenant_id, session)
                ),
            )

            # 3. The dress, on the item-based path — snapshot name, prove size.
            dress_name: str | None = None
            snapshot_size: str | None = None
            if dress_id is not None:
                if dress_size is None:  # unreachable: validate pinned the pair
                    raise BookingValidationError("dress_size is required when dress_id is given")
                dress = await self._dresses.by_id(session, tenant_id, dress_id)
                if dress is None:
                    raise BookingNotFoundError
                snapshot_size = normalize_size_label(dress_size)
                variants = await self._variants.list_active(session, tenant_id, dress_id)
                # Case-INSENSITIVE, matching the dress_variants uniqueness rule
                # itself (0006's partial unique index is on lower(size_label))
                # and CatalogService._reject_duplicate_sizes. "us 6" and "US 6"
                # are one size everywhere else; they must not be two here.
                # The customer's own spelling is never stored — the boutique's
                # label is snapshotted, so the booking reads as the catalog does.
                match = next(
                    (
                        variant.size_label
                        for variant in variants
                        if variant.size_label.lower() == snapshot_size.lower()
                    ),
                    None,
                )
                if match is None:
                    raise BookingNotFoundError
                snapshot_size = match
                dress_name = dress.name

            # 4. Serialize claims for this tenant — the replace_weekly_rules
            #    precedent. Everything from here to COMMIT holds the lock.
            # ponytail: one lock per tenant serializes all claims; per-slot
            # lock keys if pilot throughput ever cares.
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:tenant_id))"),
                {"tenant_id": str(tenant_id)},
            )

            # 4b. Idempotency, and it must come BEFORE availability — that
            #     order is the entire fix. When a claim commits but its 201 dies
            #     on a flaky mobile network, the token is already spent, so the
            #     retry is a 403 whose copy explicitly sends the customer back
            #     with a fresh code to resubmit. At capacity 1 her own booking
            #     now fills the slot, so checking availability first would 409
            #     her and walk her to a second time she does not need; at higher
            #     capacity it simply gave her two seats. A live booking for this
            #     proven phone at this instant IS this request's outcome, so
            #     return it — unchanged, because the first submission is the one
            #     she agreed to, and there is no public read endpoint through
            #     which she could ever discover the row this create replaced.
            #
            #     Read, not catch-the-IntegrityError: a failed flush aborts the
            #     Postgres transaction, so recovering from it would need a
            #     SAVEPOINT around the INSERT, and it would still be reached
            #     only in the capacity>1 case — the 409 above would beat it
            #     otherwise. The read cannot race: every claim for this tenant
            #     takes the advisory lock above before running it, and 0009's
            #     partial unique index is the backstop for a writer that does
            #     not.
            existing_customer = await self._customers.by_phone(session, tenant_id, phone=phone)
            if existing_customer is not None:
                replayed = await self._bookings.active_at(
                    session, tenant_id, customer_id=existing_customer.id, starts_at=starts_at
                )
                if replayed is not None:
                    # ⚠ THE CONSENT IS STAMPED ON THIS PATH TOO, and a single
                    # call site further down would be UNREACHABLE here (D20).
                    # This branch returns before step 6's `upsert`, so a retry of
                    # a submission whose 201 died on a flaky mobile network would
                    # otherwise silently drop the box she ticked — and she has no
                    # way to notice, because the replay renders the same
                    # confirmation screen as the original.
                    #
                    # Safe to issue twice: `record_marketing_consent`'s WHERE
                    # carries `AND marketing_consent_at IS NULL`, so the original
                    # timestamp — the evidence of WHEN she agreed — never moves.
                    if marketing_consent:
                        await self._customers.record_marketing_consent(
                            session, tenant_id, existing_customer.id
                        )
                    # No token: the first submission's raw value is already gone
                    # (only its sha256 survives), and a replay must not resend
                    # the confirmation SMS anyway. Both facts are the same fact.
                    return BookingClaim(
                        booking=replayed,
                        created=False,
                        manage_token=None,
                        deposit_due=due,
                        deposit_amount_agorot=type_row.deposit_amount_agorot or 0,
                    )

            # 5. Re-materialize the grid and assert the instant is offered —
            #    fed the REAL booked counts, so this also enforces capacity.
            slot = await offered_slot(
                session,
                tenant_id=tenant_id,
                starts_at=starts_at,
                now=now,
                rules=self._rules,
                exceptions=self._exceptions,
                bookings=self._bookings,
            )
            if slot is None:
                raise SlotUnavailableError

            # 6. Attach-or-create the customer for the proven phone.
            customer = await self._customers.upsert(
                session, tenant_id, phone=phone, name=name.strip()
            )
            # ⚠ NOT folded into `upsert` (D20), and the ABSENCE of the call is
            # the whole semantics of an unticked box: an empty checkbox on a
            # later booking is not a withdrawal, so no clearing statement is
            # issued. Withdrawal must be an affirmative act — treating an
            # omission as one would silently revoke a consent the boutique can
            # prove it holds.
            if marketing_consent:
                await self._customers.record_marketing_consent(session, tenant_id, customer.id)

            # 7. Claim the lowest free seat. A cancelled booking's seat number
            #    is reusable — counting alone would overflow past a freed seat
            #    into an occupied one.
            seats = await self._bookings.active_seats_at(
                session, tenant_id, starts_at=slot.starts_at
            )
            seat_index = next(
                (index for index in range(1, slot.capacity + 1) if index not in seats), None
            )
            if seat_index is None:
                raise SlotUnavailableError
            # 8. The manage token, minted here so its hash commits atomically
            #    with the row it authorises. The raw value leaves in the result
            #    and is then only ever in an SMS body and (while the reminder is
            #    still pending) on the scheduled_messages row.
            manage_token = mint_manage_token()
            try:
                booking = await self._bookings.insert(
                    session,
                    tenant_id=tenant_id,
                    customer_id=customer.id,
                    appointment_type_id=type_row.id,
                    starts_at=slot.starts_at,
                    seat_index=seat_index,
                    terms_version_accepted=terms_version,
                    terms_accepted_at=now,
                    appointment_type_name=type_row.name,
                    dress_id=dress_id,
                    dress_name=dress_name,
                    dress_size=snapshot_size,
                    notes=notes,
                    manage_token_hash=manage_token_hash(manage_token),
                    # D11: create THEN pay. Paying first cannot hold the seat, so
                    # the row is claimed by the advisory-lock protocol above and
                    # the payment becomes a transition on a row that exists. The
                    # seat is occupied from this instant — every occupancy
                    # predicate excludes only `cancelled`.
                    status=(
                        BookingStatus.PENDING_PAYMENT.value
                        if due
                        else BookingStatus.CONFIRMED.value
                    ),
                )
            except IntegrityError as exc:
                # Lost a race the advisory lock should have prevented — the
                # index is the backstop, and to the caller it is the same 409.
                raise SlotUnavailableError from exc

            # 9. The reminder, under D3's bands. None means the appointment is
            #    inside the two-hour suppression window and the confirmation
            #    seconds old — no row, deliberately.
            send_after = reminder_send_after(starts_at=booking.starts_at, now=now)
            if send_after is not None:
                await self._scheduled.insert(
                    session,
                    tenant_id=tenant_id,
                    booking_id=booking.id,
                    kind=ScheduledMessageKind.REMINDER.value,
                    send_after=send_after,
                    manage_token=manage_token,
                )
            return BookingClaim(
                booking=booking,
                created=True,
                manage_token=manage_token,
                deposit_due=due,
                deposit_amount_agorot=type_row.deposit_amount_agorot or 0,
            )

    async def open_deposit(
        self,
        tenant_id: uuid.UUID,
        claim: BookingClaim,
        *,
        return_url: str,
    ) -> DepositOutcome:
        """D11's post-commit step, called on BOTH claim branches (D11b).

        Post-commit for the same reason `send_confirmation` is: `PaymentService`
        structurally opens its OWN sessions and re-takes the per-tenant advisory
        lock `create_booking` holds until COMMIT, so folding the hold into the
        claim's transaction is not merely unwise, it deadlocks.

        The hold is opened only on a booking that is actually AWAITING payment.
        On the fresh path that is always true; on the 0009 replay path it is the
        guard that matters, because `active_at`'s predicate is
        `status != 'cancelled'` — so a replay can hand back a booking she has
        already PAID for, and `live_pending_for_booking` would find no pending
        row to converge onto and mint a second hosted page. She would be charged
        twice for one appointment. An unpaid hold replays into the converge
        path, gets the stored `redirect_url` back and calls no gateway at all.
        """
        if not claim.deposit_due or claim.booking.status != BookingStatus.PENDING_PAYMENT.value:
            return DepositOutcome(status=claim.booking.status, deposit_due=False)
        if self._payments is None:
            logger.warning(
                "deposit due for booking %s but no payment service is wired", claim.booking.id
            )
            return await self._book_without_deposit(tenant_id, claim)
        try:
            hold = await self._payments.open_deposit(
                tenant_id,
                booking_id=claim.booking.id,
                amount_agorot=claim.deposit_amount_agorot,
                hold_seconds=self._deposit_hold_seconds,
                return_url=return_url,
            )
        except DEPOSIT_COMPENSATED_ERRORS as exc:
            logger.warning(
                "deposit checkout unavailable for booking %s", claim.booking.id, exc_info=exc
            )
            return await self._book_without_deposit(tenant_id, claim)
        return DepositOutcome(
            status=claim.booking.status,
            deposit_due=True,
            redirect_url=hold.redirect_url,
            payment_session_id=hold.payment.provider_session_id,
        )

    async def _book_without_deposit(
        self, tenant_id: uuid.UUID, claim: BookingClaim
    ) -> DepositOutcome:
        """MD4 (a) via D11a, and it is a COMPENSATING transaction, not a tidy-up.

        The booking is already committed as `pending_payment`. Leave it there and
        the seat is held forever: `active_seats_at` counts it, the slot-seat
        index blocks the next bride, 0009's index blocks even this bride
        rebooking her own instant, and D6's sweeper — the only writer that can
        move a row out of `pending_payment` — finds no `payments` row to sweep,
        because `open_deposit` raised before it wrote one.

        Three writes, one session, therefore atomic: the transition back to
        `confirmed`, A5's `failed` payments row (without which the owner console
        cannot tell this booking from an ordinary non-deposit one), and MD4's
        audit row. The caller then sends the ordinary confirmation SMS the
        deposit path had suppressed.
        """
        provider = (
            self._gateway_credentials.gateway.provider
            if self._gateway_credentials is not None
            else None
        )
        async with tenant_session(self._session_factory, tenant_id) as session:
            booking = await self._bookings.set_status(
                session,
                tenant_id,
                claim.booking.id,
                to=BookingStatus.CONFIRMED.value,
                allowed_from=(BookingStatus.PENDING_PAYMENT.value,),
            )
            if provider is not None:
                await self._payment_rows.record_unavailable(
                    session,
                    tenant_id,
                    booking_id=claim.booking.id,
                    provider=provider,
                    amount_agorot=claim.deposit_amount_agorot,
                )
            await self._audit.record(
                session,
                tenant_id=tenant_id,
                action=AuditAction.GATEWAY_UNAVAILABLE_AT_CHECKOUT.value,
                entity="bookings",
                details={
                    "booking_id": str(claim.booking.id),
                    "amount_agorot": claim.deposit_amount_agorot,
                },
            )
        # None back from set_status means a concurrent writer moved the row
        # first, and its status — not the one this request intended — is what
        # the wire must carry. Reporting `confirmed` for a row somebody else
        # cancelled would be the one lie this whole path exists to avoid.
        return DepositOutcome(
            status=booking.status if booking is not None else claim.booking.status,
            deposit_due=False,
        )
