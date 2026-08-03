"""The tokenized manage page's service: lookup, confirm-attendance, cancel.

**Lookup is by token possession only.** This is deliberately NOT a
read-a-booking-by-id endpoint (D8): the booking becomes readable again through
the link she was sent, and nothing else. The token is compared against a stored
sha256 in constant time, and it travels in a POST body so no access log ever
carries it (D7).

**The page stays READABLE after `starts_at`; only the ACTIONS expire.** That is a
recorded amendment of security-checklist row 21's "expire at appointment time"
wording — an honest "this appointment has passed" beats a dead link for someone
re-opening her SMS weeks later.

**The policy comes from the ACCEPTED terms version, never the current one.**
Computing a customer's cancellation consequence from re-published terms is
precisely the bug `bookings.terms_version_accepted` exists to prevent.
"""

import dataclasses
import datetime
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.rate_limit import FixedWindowRateLimiter
from app.booking.schemas import (
    ManageBookingFacts,
    ManageBookingResponse,
    ManageBoutique,
    ManagePolicy,
)
from app.booking.tokens import manage_token_hash, manage_token_matches
from app.db.repositories.bookings import BookingsRepository
from app.db.repositories.payments import PaymentsRepository
from app.db.repositories.scheduled_messages import ScheduledMessagesRepository
from app.db.repositories.terms import TermsVersionsRepository
from app.db.tenant import tenant_session
from app.models.booking import Booking
from app.models.constants import (
    BookingCancelledBy,
    BookingStatus,
    PaymentStatus,
    ScheduledMessageKind,
)
from app.storefront.validation import Clock, profile_text


class BookingLinkInvalidError(Exception):
    """Unknown, rotated or malformed token. ONE error for all of them — 404
    BOOKING_LINK_INVALID — because distinguishing "never existed" from "no longer
    yours" would make this endpoint an oracle."""


class BookingAlreadyStartedError(Exception):
    """The appointment has started. Actions expire at `starts_at`; the lookup
    does not. 409 BOOKING_ALREADY_STARTED."""


class BookingCancelledError(Exception):
    """Confirming attendance at a cancelled appointment. 409 BOOKING_CANCELLED.
    A repeat CANCEL is a 200 instead — idempotent by checklist row 21."""


class BookingAwaitingPaymentError(Exception):
    """An action on a `pending_payment` hold. 409 BOOKING_AWAITING_PAYMENT.

    Its own code rather than a reuse of BOOKING_CANCELLED (F19 D14/A2): the
    appointment is neither cancelled nor standing, and the page renders a third
    state — awaiting payment, carrying the checkout link — off this one.

    The guard lives HERE and not in the repository on purpose:
    `by_manage_token_hash` deliberately carries no status predicate, because the
    LOOKUP must still answer an unpaid hold (an honest "awaiting payment" beats a
    dead link for someone re-opening her SMS). Only the two ACTIONS refuse.
    """


class BookingLookupThrottledError(Exception):
    """The per-tenant lookup budget is spent; main.py maps it to the shared
    TOO_MANY_ATTEMPTS 429.

    Its own class rather than a reuse of another throttle, for the reason the
    other three carry: these budgets have unrelated keys and unrelated
    operational meanings. Reparenting all of them onto one base stays F21's."""


@dataclasses.dataclass(frozen=True)
class ManageTenant:
    """The tenant identity this surface renders: the display name plus the
    profile block the page's ContactPanel needs. Built from the host-resolved
    TenantContext at the router, following the `StorefrontService.get_boutique`
    precedent of passing identity explicitly rather than re-reading it."""

    id: uuid.UUID
    name: str
    settings: dict[str, Any]


class ManageBookingService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        lookup_limiter: FixedWindowRateLimiter,
        clock: Clock | None = None,
    ) -> None:
        self._session_factory = session_factory
        # Its OWN instance, never a second key on another limiter: max_attempts
        # lives on the limiter and not per key, so a shared instance would give
        # this budget somebody else's ceiling (house rule).
        self._lookup_limiter = lookup_limiter
        self._clock = clock
        self._bookings = BookingsRepository()
        self._terms = TermsVersionsRepository()
        self._scheduled = ScheduledMessagesRepository()
        self._payments = PaymentsRepository()

    def _now(self) -> datetime.datetime:
        now = self._clock() if self._clock is not None else datetime.datetime.now(datetime.UTC)
        return now.astimezone(datetime.UTC)

    async def lookup(self, tenant: ManageTenant, *, token: str) -> ManageBookingResponse:
        """Read-only, and the only metered call of the three.

        The budget is an anti-scrape ceiling on the one public surface that
        answers a secret: without it an attacker could walk the token space at
        full speed. Per tenant rather than per IP, same posture and same reason
        as the OTP surface — `trust_forwarded_for` is unresolved until F21, and
        behind an untrusted proxy an IP key collapses to one bucket anyway.
        """
        key = f"booking:lookup:{tenant.id}"
        if self._lookup_limiter.is_blocked(key):
            raise BookingLookupThrottledError
        # Recorded on every attempt, hit or miss: the resource being metered is
        # the guess itself (same reasoning as the storefront read throttle, whose
        # limiter would otherwise be inert).
        self._lookup_limiter.record_failure(key)

        async with tenant_session(self._session_factory, tenant.id) as session:
            booking = await self._resolve(session, tenant.id, token)
            return await self._render(session, tenant, booking)

    async def confirm_attendance(
        self, tenant: ManageTenant, *, token: str
    ) -> ManageBookingResponse:
        """Writes `attendance_confirmed_at` — the column F13 shipped with no
        writer, and the whole no-show defence the reminder exists to collect."""
        now = self._now()
        async with tenant_session(self._session_factory, tenant.id) as session:
            booking = await self._resolve(session, tenant.id, token)
            if booking.status == BookingStatus.CANCELLED.value:
                raise BookingCancelledError
            if booking.status == BookingStatus.PENDING_PAYMENT.value:
                # An unpaid hold is not an appointment she can promise to attend
                # (D14): the seat is hers only until the sweeper takes it back.
                raise BookingAwaitingPaymentError
            if booking.starts_at <= now:
                raise BookingAlreadyStartedError
            # Idempotent: the repository's `IS NULL` guard means a second tap
            # keeps the FIRST confirmation's timestamp instead of moving it, and
            # she sees the same success either way. She will click more than once.
            updated = await self._bookings.confirm_attendance(
                session, tenant.id, booking.id, at=now
            )
            return await self._render(session, tenant, updated if updated is not None else booking)

    async def cancel(self, tenant: ManageTenant, *, token: str) -> ManageBookingResponse:
        """One transaction: the status write, the cancel evidence, and the
        pending reminder flipped to 'cancelled'.

        The seat and the idempotency slot free themselves structurally — both
        partial unique indexes (0008, 0009) exclude `status = 'cancelled'` — so
        the freed time reappears in the picker and she can rebook the same
        instant with no extra work here.

        No SMS is sent (D5): the page she is looking at IS the receipt, and every
        body is segment cost plus Amendment-40 legal surface.
        """
        now = self._now()
        async with tenant_session(self._session_factory, tenant.id) as session:
            booking = await self._resolve(session, tenant.id, token)
            if booking.status == BookingStatus.CANCELLED.value:
                # Idempotent, and checked BEFORE the clock: a second tap on an
                # already-cancelled appointment is the same success, even once
                # the appointment time has passed.
                return await self._render(session, tenant, booking)
            if booking.status == BookingStatus.PENDING_PAYMENT.value:
                # NOT the idempotent 200 above, and not a cancel either (D14):
                # this writer frees the seat and attributes the cancellation to
                # the CUSTOMER, and a checkout still in flight is neither her
                # decision nor a released seat. The sweeper owns that transition
                # and attributes it 'expired' (MD5).
                raise BookingAwaitingPaymentError
            if booking.starts_at <= now:
                raise BookingAlreadyStartedError
            updated = await self._bookings.cancel(
                session,
                tenant.id,
                booking.id,
                at=now,
                by=BookingCancelledBy.CUSTOMER.value,
            )
            await self._scheduled.cancel_pending(
                session,
                tenant.id,
                booking_id=booking.id,
                kind=ScheduledMessageKind.REMINDER.value,
            )
            return await self._render(session, tenant, updated if updated is not None else booking)

    async def _resolve(self, session: AsyncSession, tenant_id: uuid.UUID, token: str) -> Booking:
        booking = await self._bookings.by_manage_token_hash(
            session, tenant_id, manage_token_hash(token)
        )
        # The re-check is deliberately redundant against an equality predicate —
        # see `manage_token_matches` for why it is here anyway.
        if booking is None or not manage_token_matches(token, booking.manage_token_hash):
            raise BookingLinkInvalidError
        return booking

    async def _render(
        self, session: AsyncSession, tenant: ManageTenant, booking: Booking
    ) -> ManageBookingResponse:
        accepted = await self._terms.by_version(session, tenant.id, booking.terms_version_accepted)
        # A3: the LATEST payment on this booking, and only `paid` counts as taken
        # — a pending hold, a swept `expired` one and MD4's `failed` marker all
        # mean no money moved, which is exactly when "cancelling is free" is still
        # a true sentence.
        payment = (await self._payments.by_booking_ids(session, tenant.id, [booking.id])).get(
            booking.id
        )
        profile = tenant.settings.get("profile")
        profile = profile if isinstance(profile, dict) else {}
        return ManageBookingResponse(
            booking=ManageBookingFacts(
                starts_at=booking.starts_at,
                status=booking.status,
                attendance_confirmed_at=booking.attendance_confirmed_at,
                appointment_type_name=booking.appointment_type_name,
                dress_name=booking.dress_name,
                dress_size=booking.dress_size,
                deposit_taken=payment is not None and payment.status == PaymentStatus.PAID.value,
            ),
            # None only if the accepted version row has somehow gone — the table
            # is append-only by DB grant, so this is a guard and not a path. The
            # page renders the cancel step without the window sentence rather
            # than showing a number it cannot justify.
            policy=(
                None
                if accepted is None
                else ManagePolicy(
                    refundable_until_hours_before=accepted.refundable_until_hours_before,
                    forfeit_percent=accepted.forfeit_percent,
                )
            ),
            boutique=ManageBoutique(
                name=tenant.name,
                phone=profile_text(profile, "phone"),
                address=profile_text(profile, "address"),
                maps_url=profile_text(profile, "maps_url"),
            ),
        )
