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
from app.booking.service import PhoneNotVerifiedError
from app.db.repositories.customer_sessions import CustomerSessionsRepository
from app.db.repositories.customers import CustomersRepository
from app.db.tenant import tenant_session
from app.notifications.service import OtpService
from app.notifications.validation import normalize_israeli_mobile
from app.portal.schemas import PortalSessionResponse
from app.storefront.validation import Clock


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
                # Includes the erased subject by construction — her phone is
                # `erased:{id}` and can never equal a normalised mobile.
                raise PortalNoBookingsError

            token = generate_session_token()
            await self._sessions.insert(
                session,
                tenant_id=tenant_id,
                customer_id=customer.id,
                token_hash=hash_token(token),
                expires_at=now + datetime.timedelta(seconds=self._session_ttl_seconds),
            )
            return PortalSessionResponse(customer_name=customer.name), token

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
