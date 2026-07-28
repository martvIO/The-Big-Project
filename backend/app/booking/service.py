"""The claim — where a slot the grid offers becomes a booking row, exactly once.

The whole feature's correctness lives in `create_booking`'s ordered steps inside
ONE `tenant_session`: token burn, terms check, snapshots, advisory lock, grid
re-materialization, customer upsert and the seat-indexed INSERT commit or roll
back together. The per-tenant advisory lock is the primary control and 0008's
partial unique index is the structural backstop — losing a race surfaces as
either a full grid or an IntegrityError, and both are the same 409 to a caller.
"""

import datetime
import uuid

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.rate_limit import FixedWindowRateLimiter
from app.booking.slots import Slot, materialize_slots
from app.booking.validation import (
    SLOT_WINDOW_MAX_DAYS,
    BookingValidationError,
    validate_booking_request,
)
from app.catalog.validation import normalize_size_label
from app.db.repositories.appointment_types import AppointmentTypesRepository
from app.db.repositories.availability import (
    AvailabilityExceptionsRepository,
    AvailabilityRulesRepository,
)
from app.db.repositories.bookings import BookingsRepository
from app.db.repositories.customers import CustomersRepository
from app.db.repositories.dress_variants import DressVariantsRepository
from app.db.repositories.dresses import DressesRepository
from app.db.repositories.terms import TermsVersionsRepository
from app.db.tenant import tenant_session
from app.errors import DomainNotFoundError
from app.models.booking import Booking
from app.notifications.service import OtpService
from app.notifications.validation import normalize_israeli_mobile
from app.storefront.validation import BOUTIQUE_TIMEZONE, Clock

# Past the grid's own publishable ceiling, so rejecting anything beyond it can
# never cost a real booking. TWO days of slack, not one: the ceiling is a
# boutique DATE and this is a UTC INSTANT, and an Israeli DST fall-back between
# now and the ceiling shifts every local wall time an hour later in UTC — which
# at +1 day ate the last half-hour of the final day's grid.
BOOKABLE_HORIZON = datetime.timedelta(days=SLOT_WINDOW_MAX_DAYS + 2)


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


class BookingService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        otp: OtpService,
        create_limiter: FixedWindowRateLimiter,
        phone_limiter: FixedWindowRateLimiter,
        clock: Clock | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._otp = otp
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
    ) -> Booking:
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

            # 5. Re-materialize the grid and assert the instant is offered —
            #    fed the REAL booked counts, so this also enforces capacity.
            slot = await self._offered_slot(session, tenant_id, starts_at=starts_at, now=now)
            if slot is None:
                raise SlotUnavailableError

            # 6. Attach-or-create the customer for the proven phone.
            customer = await self._customers.upsert(
                session, tenant_id, phone=phone, name=name.strip()
            )

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
            try:
                return await self._bookings.insert(
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
                )
            except IntegrityError as exc:
                # Lost a race the advisory lock should have prevented — the
                # index is the backstop, and to the caller it is the same 409.
                raise SlotUnavailableError from exc

    async def _offered_slot(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        starts_at: datetime.datetime,
        now: datetime.datetime,
    ) -> Slot | None:
        """The requested instant as the grid currently offers it, or None.

        Not a formality: without this a caller books 03:00 on a closed Saturday
        by posting an arbitrary timestamp. One boutique-calendar day is enough —
        a slot's date in the boutique's own zone is the only date whose rules
        and exceptions can produce it."""
        wanted = starts_at.astimezone(datetime.UTC)
        target_date = wanted.astimezone(BOUTIQUE_TIMEZONE).date()
        rules = await self._rules.list_active(session, tenant_id)
        exceptions = await self._exceptions.list_active(
            session, tenant_id, on_or_after=target_date, on_or_before=target_date
        )
        day_start = datetime.datetime.combine(
            target_date, datetime.time.min, tzinfo=BOUTIQUE_TIMEZONE
        ).astimezone(datetime.UTC)
        day_end = datetime.datetime.combine(
            target_date + datetime.timedelta(days=1), datetime.time.min, tzinfo=BOUTIQUE_TIMEZONE
        ).astimezone(datetime.UTC)
        booked = await self._bookings.count_by_start(
            session, tenant_id, from_instant=day_start, until_instant=day_end
        )
        slots = materialize_slots(
            rules=rules,
            exceptions=exceptions,
            booked=booked,
            window_start=target_date,
            window_end=target_date,
            now=now,
        )
        return next((slot for slot in slots if slot.starts_at == wanted), None)
