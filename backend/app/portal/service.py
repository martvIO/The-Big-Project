"""F24's customer session: mint, resolve, revoke.

**The session binds to a `customers` row, not to a bare phone (spec D1).**
`bookings.customer_id` is NOT NULL and F13/F53/F20 built a real row keyed
(tenant, phone) with CRM, consent and erasure fields — so "OTP-verified phone"
is a weaker identity than the one already shipped. Login therefore resolves the
customer and REFUSES when there is none; it never creates one, because
`customers.name` is NOT NULL and only a booking supplies a name.

**An erased subject can never match, by construction.** F20 rewrites `phone` to
`erased:{id}`, so the (tenant, normalized phone) lookup misses and she gets the
same `PORTAL_NO_BOOKINGS` a stranger gets. No branch, no special case.

**One NEW limiter instance for the mint** (spec D3) — never a key on the OTP or
booking budgets: `max_attempts` lives on the LIMITER, so a shared instance would
give this path somebody else's ceiling and let a login flood close the booking
flow (`.memory/limiter-max-is-per-instance`, restated at every limiter in
main.py). The OTP send/verify budgets stay SHARED with the booking flow
deliberately: the metered resource there is the SMS spend and the guess surface,
which is identical whichever flow asks.
"""

import dataclasses
import datetime
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.tokens import generate_session_token, hash_token
from app.booking.manage import ManageBookingTransitions, ManageTenant
from app.booking.schemas import ManageBookingResponse
from app.booking.service import BookingNotFoundError, PhoneNotVerifiedError
from app.db.repositories.bookings import BookingsRepository
from app.db.repositories.customer_sessions import CustomerSessionsRepository
from app.db.repositories.customers import CustomersRepository
from app.db.repositories.message_log import MessageLogRepository
from app.db.tenant import tenant_session
from app.models.booking import Booking
from app.notifications.service import OtpService
from app.notifications.validation import normalize_israeli_mobile
from app.portal.schemas import (
    PortalBellItem,
    PortalBellResponse,
    PortalBookingRow,
    PortalBookingsResponse,
    PortalSessionResponse,
)
from app.storefront.validation import Clock

# The dashboard's ceiling. No pagination and no filter, so this is a HARD cap —
# and the read it rides (`list_recent_for_customer`) orders `starts_at DESC`, so
# what a bride past a hundred appointments at one boutique loses is her OLDEST
# history and never her next fitting. A hundred is roughly a decade of monthly
# visits; the upgrade path if a real tenant ever passes it is a `before` cursor
# on the past section alone.
PORTAL_BOOKING_LIMIT = 100


class PortalNoBookingsError(Exception):
    """The phone is verified and there is no customer row for it under this
    tenant. main.py maps it to 404 PORTAL_NO_BOOKINGS.

    Its OWN code rather than the house 404, because the login panel renders a
    designed state off it — and it is not an enumeration oracle: the caller has
    just proved possession of the number, so «this phone has no bookings here»
    discloses only her own data to herself.
    """


class PortalThrottledError(Exception):
    """The per-tenant mint budget is spent; main.py maps it to the shared 429
    TOO_MANY_ATTEMPTS body.

    Its own class like the throttles before it (unrelated budgets, keys and
    operational meanings); the F21 reparenting note on StorefrontThrottledError
    covers this one too.
    """


@dataclasses.dataclass(frozen=True)
class CustomerContext:
    """What a resolved customer cookie yields — the `StaffContext` shape for the
    other side of the product. `id` is the customer id every portal query
    filters on, over and above RLS."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    phone: str


class PortalService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        otp: OtpService,
        mint_limiter: FixedWindowRateLimiter,
        session_ttl_seconds: int,
        clock: Clock | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._otp = otp
        # ⚠ ITS OWN INSTANCE, never a key on the OTP or booking budgets — see
        # the module docstring. test_portal_api.py pins the wiring.
        self._mint_limiter = mint_limiter
        self._session_ttl_seconds = session_ttl_seconds
        self._clock = clock
        self._customers = CustomersRepository()
        self._sessions = CustomerSessionsRepository()
        self._bookings = BookingsRepository()
        self._messages = MessageLogRepository()
        # The SHARED guard set, not a copy (spec D4). Its clock is this
        # service's, so a frozen-clock test moves both halves together.
        self._transitions = ManageBookingTransitions(clock)

    def _now(self) -> datetime.datetime:
        now = self._clock() if self._clock is not None else datetime.datetime.now(datetime.UTC)
        return now.astimezone(datetime.UTC)

    async def create_session(
        self, tenant_id: uuid.UUID, *, raw_phone: str, verification_token: str
    ) -> tuple[PortalSessionResponse, str]:
        """Returns the body and the RAW token; only the router knows about the
        cookie."""
        # The brake is CHECKED and SPENT on every attempt, hit or miss —
        # `ManageBookingService.lookup`'s posture, not `create_booking`'s. The
        # resource being metered is the mint ATTEMPT itself: each one opens a
        # transaction and issues a guarded UPDATE against `otp_codes`, so a
        # flood of garbage tokens costs the boutique's database whether or not
        # any of them verifies. Metering only proven callers would leave that
        # unbraked, and proven callers are already bounded by the OTP send
        # budget one endpoint upstream.
        key = f"portal:session:{tenant_id}"
        if self._mint_limiter.is_blocked(key):
            raise PortalThrottledError
        self._mint_limiter.record_failure(key)

        phone = normalize_israeli_mobile(raw_phone)
        now = self._now()
        async with tenant_session(self._session_factory, tenant_id) as session:
            # Burn first, exactly as `create_booking` and the waitlist join do:
            # a caller who cannot prove the phone gets no further, and the token
            # is single-use whatever the outcome below.
            verified = await self._otp.consume_verification(
                session, tenant_id, raw_phone=raw_phone, verification_token=verification_token
            )
            if not verified:
                raise PhoneNotVerifiedError

            customer = await self._customers.by_phone(session, tenant_id, phone=phone)
            if customer is None:
                # ⚠ RECORDED, NOT RAISED — AND THAT IS THE WHOLE POINT OF THE
                # BURN ABOVE. `tenant_session` wraps this block in ONE
                # `session.begin()`, so an exception raised HERE unwinds the
                # transaction and takes `consume_verification`'s burn with it:
                # the token would survive its own refusal and the mint would be
                # retryable for free, which is exactly the property
                # `test_an_unknown_phone_still_burns_its_token` denies. The
                # refusal is carried out of the block instead, so the burn
                # commits and the caller is told nothing extra.
                # Includes the erased subject by construction — her phone is
                # `erased:{id}` and can never equal a normalised mobile.
                minted = None
            else:
                token = generate_session_token()
                await self._sessions.insert(
                    session,
                    tenant_id=tenant_id,
                    customer_id=customer.id,
                    token_hash=hash_token(token),
                    expires_at=now + datetime.timedelta(seconds=self._session_ttl_seconds),
                )
                minted = (PortalSessionResponse(customer_name=customer.name), token)

        if minted is None:
            raise PortalNoBookingsError
        return minted

    async def resolve_session(self, tenant_id: uuid.UUID, token: str) -> CustomerContext | None:
        """`AuthService.resolve_session`'s shape for the customer side: the
        customer row is re-read on every request, so an erased or soft-deleted
        subject is a 401 on her very next call rather than at TTL."""
        async with tenant_session(self._session_factory, tenant_id) as session:
            row = await self._sessions.active_by_token_hash(
                session, tenant_id, hash_token(token), self._now()
            )
            if row is None:
                return None
            customer = await self._customers.by_id(session, tenant_id, row.customer_id)
            if customer is None:
                return None
            return CustomerContext(
                id=customer.id,
                tenant_id=tenant_id,
                name=customer.name,
                phone=customer.phone,
            )

    async def logout(self, tenant_id: uuid.UUID, token: str) -> None:
        async with tenant_session(self._session_factory, tenant_id) as session:
            await self._sessions.revoke_by_token_hash(session, tenant_id, hash_token(token))

    # --- "My Bookings" (spec D4) --------------------------------------------

    async def list_bookings(
        self, tenant_id: uuid.UUID, customer: CustomerContext
    ) -> PortalBookingsResponse:
        """HER bookings, and the scope comes from the SESSION — there is no
        customer parameter on the wire for a caller to substitute.

        Reuses F53's `list_recent_for_customer` rather than adding a read: it
        already answers every status with no lower bound on `starts_at`, ordered
        `starts_at DESC, id DESC`. The split happens here because the boundary
        is a clock, and a clock in the browser is a boundary that moves per
        device.
        """
        now = self._now()
        async with tenant_session(self._session_factory, tenant_id) as session:
            rows = await self._bookings.list_recent_for_customer(
                session, tenant_id, customer_id=customer.id, limit=PORTAL_BOOKING_LIMIT
            )
        upcoming = [row for row in rows if row.starts_at > now]
        past = [row for row in rows if row.starts_at <= now]
        return PortalBookingsResponse(
            # The repository hands back DESC; upcoming reads ASC (her next
            # appointment first, which is the one she opened the page for) and
            # past stays DESC (most recent first).
            upcoming=[_to_row(row) for row in reversed(upcoming)],
            past=[_to_row(row) for row in past],
        )

    async def get_booking(
        self, tenant: ManageTenant, customer: CustomerContext, booking_id: uuid.UUID
    ) -> ManageBookingResponse:
        """`ManageBookingResponse` VERBATIM (spec D4) — the mirror guarantee is
        a shared contract, not a second shape that happens to match today."""
        async with tenant_session(self._session_factory, tenant.id) as session:
            booking = await self._hers(session, tenant.id, customer, booking_id)
            return await self._transitions.render(session, tenant, booking)

    async def confirm_attendance(
        self, tenant: ManageTenant, customer: CustomerContext, booking_id: uuid.UUID
    ) -> ManageBookingResponse:
        async with tenant_session(self._session_factory, tenant.id) as session:
            booking = await self._hers(session, tenant.id, customer, booking_id)
            return await self._transitions.confirm_attendance(session, tenant, booking)

    async def cancel(
        self, tenant: ManageTenant, customer: CustomerContext, booking_id: uuid.UUID
    ) -> ManageBookingResponse:
        async with tenant_session(self._session_factory, tenant.id) as session:
            booking = await self._hers(session, tenant.id, customer, booking_id)
            return await self._transitions.cancel(session, tenant, booking)

    # --- the bell (spec D6) --------------------------------------------------

    async def bell(self, tenant_id: uuid.UUID, customer: CustomerContext) -> PortalBellResponse:
        """A READ-SIDE PROJECTION over `message_log` — no new table, no queue and
        no delivery substrate. `message_log` already IS "what the boutique told
        her", with `booking_id` populated since F16.

        Fetched once when the portal mounts (pre-decided #18): no interval, no
        focus-refetch, no websocket. Every event it lists already sent an SMS the
        same second — the bell is a history list, not the alert channel.

        `bell_seen_at` is re-read HERE rather than carried on `CustomerContext`:
        the context is minted per request from the session lookup, and the count
        must reflect the stamp as of this read, not as of whenever the
        dependency happened to resolve.
        """
        async with tenant_session(self._session_factory, tenant_id) as session:
            rows = await self._messages.list_bell_for_customer(session, tenant_id, customer.id)
            row = await self._customers.by_id(session, tenant_id, customer.id)
        seen_at = row.bell_seen_at if row is not None else None
        items = [
            PortalBellItem(
                id=message_id,
                kind=kind,
                created_at=created_at,
                # NOT NULL in practice — the repository's join is on
                # `booking_id`, so a null could not have matched a booking.
                booking_id=booking_id,
                starts_at=starts_at,
                appointment_type_name=type_name,
            )
            for message_id, kind, created_at, booking_id, starts_at, type_name in rows
            if booking_id is not None
        ]
        # Counted over the RETURNED items, not the whole history. The badge caps
        # at «9+» either way, and a number larger than the list she can open
        # would be a count of things this screen refuses to show her. NULL
        # `bell_seen_at` means never opened, so everything is unread.
        unread = (
            len(items) if seen_at is None else sum(1 for item in items if item.created_at > seen_at)
        )
        return PortalBellResponse(unread_count=unread, items=items)

    async def mark_bell_seen(self, tenant_id: uuid.UUID, customer: CustomerContext) -> None:
        """One timestamp is the whole read model (spec D6) — no per-item rows.
        Unconditional: re-opening the bell moves the stamp forward, which is
        what the column means."""
        async with tenant_session(self._session_factory, tenant_id) as session:
            await self._customers.set_bell_seen(session, tenant_id, customer.id, at=self._now())

    async def get_booking_ics(
        self,
        tenant: ManageTenant,
        customer: CustomerContext,
        booking_id: uuid.UUID,
        *,
        slug: str,
        base_domain: str,
    ) -> str:
        async with tenant_session(self._session_factory, tenant.id) as session:
            booking = await self._hers(session, tenant.id, customer, booking_id)
            return await self._transitions.ics(
                session, tenant, booking, slug=slug, base_domain=base_domain
            )

    async def _hers(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        customer: CustomerContext,
        booking_id: uuid.UUID,
    ) -> Booking:
        """`_resolve`'s counterpart on the session side: the ONE place the
        ownership predicate lives, so no route can forget it.

        Unknown and not-hers raise the SAME error and answer the same body —
        distinguishing them would make this endpoint an existence oracle for
        another bride's appointments, which is `BookingLinkInvalidError`'s
        reasoning one identity model over.
        """
        booking = await self._bookings.by_id(session, tenant_id, booking_id)
        if booking is None or booking.customer_id != customer.id:
            raise BookingNotFoundError
        return booking


def _to_row(booking: Booking) -> PortalBookingRow:
    return PortalBookingRow(
        id=booking.id,
        starts_at=booking.starts_at,
        status=booking.status,
        attendance_confirmed_at=booking.attendance_confirmed_at,
        appointment_type_name=booking.appointment_type_name,
        dress_name=booking.dress_name,
        dress_size=booking.dress_size,
    )
