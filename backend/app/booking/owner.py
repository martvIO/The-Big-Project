"""The owner console's booking surface: the day list, the detail, the four
transitions, reschedule, phone correction and the resend.

Session-authed, CSRF-fenced and `no-store`, so unlike the tokenized manage page
this one may carry the customer's phone and her notes — the operational point of
the screen is that the owner can call the bride and read what she wrote (D18).
"""

import datetime
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.rate_limit import FixedWindowRateLimiter
from app.booking.comms import BookingCommsService
from app.booking.service import BookingNotFoundError
from app.booking.slots import Slot
from app.booking.validation import BOOKING_LIST_MAX_LIMIT
from app.db.repositories.audit_log import AuditLogRepository
from app.db.repositories.availability import (
    AvailabilityExceptionsRepository,
    AvailabilityRulesRepository,
)
from app.db.repositories.bookings import BookingsRepository
from app.db.repositories.customers import CustomersRepository
from app.db.repositories.scheduled_messages import ScheduledMessagesRepository
from app.db.tenant import tenant_session
from app.models.booking import Booking
from app.storefront.service import StorefrontService
from app.storefront.validation import BOUTIQUE_TIMEZONE, Clock

# STOREFRONT/CATALOG's MAX_LIST_OFFSET, restated for the same reason it exists
# there: `offset` reaches the driver as `OFFSET $n::BIGINT` (SQLAlchemy's
# asyncpg dialect casts it explicitly), so an unbounded Python int never becomes
# a 400 — it dies in asyncpg's `int8_encode` as a DataError with no handler
# above it, i.e. a 500. Clamped in the service, below the router's Query bound,
# so a non-router caller cannot reach the encoder either.
MAX_LIST_OFFSET = 1_000_000


class BookingTransitionInvalidError(Exception):
    """The booking's current state — or the clock — refuses this change. 409
    BOOKING_TRANSITION_INVALID.

    Deliberately ONE code for an illegal status pair, no-show/complete before
    `starts_at`, cancel after it, and resend/phone/reschedule on a booking that
    is not confirmed-and-future. The console renders one sentence either way and
    the refused pair rides this exception's message (D19).
    """


class CustomerAlreadyBookedError(Exception):
    """This customer already holds a live booking at the target instant — a
    reschedule target, or a phone-correction re-point onto a customer who
    already holds this instant (0009's partial unique index, D8). 409
    CUSTOMER_ALREADY_BOOKED."""


class OwnerResendThrottledError(Exception):
    """The per-tenant owner-SMS budget is spent; main.py maps it to the shared
    TOO_MANY_ATTEMPTS 429 with no new code (D10).

    Its own class for the same reason as StorefrontThrottledError / OtpThrottledError
    / BookingThrottledError: these budgets have unrelated keys and unrelated
    operational meanings. Reparenting all of them onto one base stays F21's.
    """


class NotAuthorizedError(Exception):
    """A live staff session whose StaffRole is not OWNER. 403 NOT_AUTHORIZED.

    A no-op today — StaffRole has exactly one member — which is precisely why it
    ships now: on the day E6 adds ASSISTANT, inheriting the future role model by
    default would hand an assistant the bride's phone with no code change and no
    failing test. 403 and not 401: the caller IS authenticated, she is just not
    an owner.
    """


class OwnerBookingService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        storefront: StorefrontService,
        comms: BookingCommsService,
        sms_limiter: FixedWindowRateLimiter,
        clock: Clock | None = None,
    ) -> None:
        self._session_factory = session_factory
        # Injected rather than re-implemented: GET /manage/slots is
        # StorefrontService.list_slots plus an owner projection (D6), and a
        # second materializer is the one thing slots.py exists to forbid.
        self._storefront = storefront
        self._comms = comms
        # Its OWN instance, never a second key on another limiter: max_attempts
        # lives on the limiter and not per key, so a shared instance would give
        # this budget somebody else's ceiling (house rule).
        self._sms_limiter = sms_limiter
        self._clock = clock
        self._bookings = BookingsRepository()
        self._customers = CustomersRepository()
        self._scheduled = ScheduledMessagesRepository()
        self._audit = AuditLogRepository()
        self._rules = AvailabilityRulesRepository()
        self._exceptions = AvailabilityExceptionsRepository()

    def _now(self) -> datetime.datetime:
        now = self._clock() if self._clock is not None else datetime.datetime.now(datetime.UTC)
        return now.astimezone(datetime.UTC)

    async def list_day(
        self, tenant_id: uuid.UUID, *, date: datetime.date, offset: int, limit: int
    ) -> tuple[list[Booking], int]:
        """One Jerusalem calendar day, every status (D17).

        The date→instant conversion is `StorefrontService.list_slots`'s, for its
        reason: boutique midnight is not UTC midnight, and across a DST boundary
        the day is 23 or 25 hours long — arithmetic that added a fixed 24h would
        drop or duplicate the edge booking. Half-open on the right, so the start
        of the next boutique day is the exclusive bound.

        Clamped here and not only at the router: `Query(ge=0, le=…)` guards the
        HTTP path, but `offset` reaches asyncpg as `OFFSET $n::BIGINT` and a
        non-router caller passing an unbounded Python int would 500 in the
        encoder rather than 400 at the boundary.
        """
        from_instant = datetime.datetime.combine(
            date, datetime.time.min, tzinfo=BOUTIQUE_TIMEZONE
        ).astimezone(datetime.UTC)
        until_instant = datetime.datetime.combine(
            date + datetime.timedelta(days=1), datetime.time.min, tzinfo=BOUTIQUE_TIMEZONE
        ).astimezone(datetime.UTC)
        safe_offset = min(max(offset, 0), MAX_LIST_OFFSET)
        safe_limit = min(max(limit, 1), BOOKING_LIST_MAX_LIMIT)
        async with tenant_session(self._session_factory, tenant_id) as session:
            return await self._bookings.list_day(
                session,
                tenant_id,
                from_instant=from_instant,
                until_instant=until_instant,
                offset=safe_offset,
                limit=safe_limit,
            )

    async def detail(self, tenant_id: uuid.UUID, booking_id: uuid.UUID) -> Booking:
        """`BookingNotFoundError` is a `DomainNotFoundError`, so the app-wide
        handler bound to the base answers it — another tenant's id and an
        unknown one are the same indistinguishable 404."""
        async with tenant_session(self._session_factory, tenant_id) as session:
            booking = await self._bookings.by_id(session, tenant_id, booking_id)
        if booking is None:
            raise BookingNotFoundError
        return booking

    async def list_slots(
        self,
        tenant_id: uuid.UUID,
        *,
        from_date: datetime.date | None = None,
        to_date: datetime.date | None = None,
    ) -> list[Slot]:
        """Full `Slot` objects — capacity and remaining survive, because they
        are only lost in the storefront's projection and the owner picking a
        reschedule target needs to know she is taking the last place (D6).

        `SlotWindowError` from `to < from` propagates untouched: it subclasses
        `DomainValidationError`, so it is already a 400 VALIDATION_ERROR.
        """
        return await self._storefront.list_slots(tenant_id, from_date=from_date, to_date=to_date)
