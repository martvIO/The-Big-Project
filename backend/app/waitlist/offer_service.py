"""The offer claim (D4) — one guarded UPDATE, then the SHIPPED booking engine.

**The whole race answer is two statements and neither of them is new.** The
guarded `WHERE status='offered' AND offer_expires_at > now` decides claim-vs-claim
and expiry-vs-late-claim in one round trip with no lock; `claim_seat` then decides
claim-vs-direct-booker on the same `pg_advisory_xact_lock(hashtext(tenant_id))`
and the same `idx_bookings_slot_seat_unique` a direct booking contends on. There
is no third mechanism here, and that is the point.

**One transaction, so a lost race un-claims the entry.** If the direct booker
commits first, `claim_seat` raises `SlotUnavailableError` and the rollback covers
the `offered -> claimed` UPDATE too, leaving the entry `offered`. The page renders
«התור הזה נתפס בינתיים» over a still-live offer and a reload re-renders it
(design F-O2). That is correct — the slot is gone, so there is nothing to advance
to, and the offer dies on its own clock.

**No deposit code is written here** (D5). A deposit-on type produces
`pending_payment` through the shipped branch and the router calls the shipped
`open_deposit` post-commit, exactly as `POST /storefront/bookings` does.
"""

import datetime
import logging
import uuid
from collections.abc import Mapping

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.rate_limit import FixedWindowRateLimiter
from app.booking.service import (
    BookingClaim,
    TermsStaleError,
    claim_seat,
    deposit_due,
)
from app.booking.tokens import manage_token_hash, manage_token_matches, mint_manage_token
from app.booking.validation import validate_booking_request
from app.db.repositories.appointment_types import AppointmentTypesRepository
from app.db.repositories.availability import (
    AvailabilityExceptionsRepository,
    AvailabilityRulesRepository,
)
from app.db.repositories.bookings import BookingsRepository
from app.db.repositories.customers import CustomersRepository
from app.db.repositories.scheduled_messages import ScheduledMessagesRepository
from app.db.repositories.terms import TermsVersionsRepository
from app.db.repositories.waitlist_entries import WaitlistEntriesRepository
from app.db.tenant import tenant_session
from app.errors import DomainNotFoundError
from app.models.constants import ScheduledMessageKind, WaitlistEntryStatus
from app.models.waitlist_entry import WaitlistEntry
from app.payments.service import GatewayCredentialService
from app.storefront.validation import Clock
from app.waitlist.schemas import WaitlistOfferResponse
from app.waitlist.validation import WaitlistThrottledError

logger = logging.getLogger("app")

OFFER_KIND = ScheduledMessageKind.WAITLIST_OFFER.value


class OfferNotFoundError(DomainNotFoundError):
    """Unknown token, a token minted for another boutique, an entry the retention
    purge has taken, or a token whose entry has already had it cleared — ONE
    indistinguishable 404, the manage page's rule verbatim. Telling the four
    apart would hand a prober an oracle over a token space it is guessing at."""


class OfferNotClaimableError(Exception):
    """The entry is no longer a live offer. `state` is what it moved to —
    `claimed`, `expired`, `cancelled` or `waiting` — carried for the log and for
    the race tests. The HTTP layer collapses every one of them into the SAME 409
    a direct booker losing a race gets: she is owed the outcome, not a report on
    which internal transition beat her."""

    def __init__(self, state: str) -> None:
        super().__init__(state)
        self.state = state


class WaitlistOfferService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        lookup_limiter: FixedWindowRateLimiter,
        gateway_credentials: GatewayCredentialService | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._session_factory = session_factory
        # Its OWN instance, never a second key on the booking-lookup limiter:
        # `max_attempts` lives on the LIMITER, not per key, so two keys on one
        # instance share one ceiling and neither budget can trip first. It would
        # be decoration. Required rather than defaulted, because an unmetered
        # anti-scrape surface is the failure this exists to prevent.
        self._lookup_limiter = lookup_limiter
        # None = this deployment wired no gateway, which reads as NOT connected.
        # `create_booking` takes the identical posture: every branch that could
        # take money is opt-in.
        self._gateway_credentials = gateway_credentials
        self._clock = clock
        self._entries = WaitlistEntriesRepository()
        self._scheduled = ScheduledMessagesRepository()
        self._types = AppointmentTypesRepository()
        self._terms = TermsVersionsRepository()
        self._customers = CustomersRepository()
        self._rules = AvailabilityRulesRepository()
        self._exceptions = AvailabilityExceptionsRepository()
        self._bookings = BookingsRepository()

    def _now(self) -> datetime.datetime:
        now = self._clock() if self._clock is not None else datetime.datetime.now(datetime.UTC)
        return now.astimezone(datetime.UTC)

    def _meter(self, tenant_id: uuid.UUID) -> None:
        """Per TENANT, and all three verbs share the budget.

        The token is 32 random bytes, so this is not guess protection — it is
        scrape and cost protection: a token-shaped body is a free database read
        on an anonymous route, and metering the lookup alone would leave `claim`
        and `decline` as the same read behind a different path. Keyed on the
        tenant rather than the token because a per-token key is a budget an
        attacker mints for free.
        """
        key = f"waitlist:offer:{tenant_id}"
        if self._lookup_limiter.is_blocked(key):
            raise WaitlistThrottledError
        self._lookup_limiter.record_failure(key)

    async def _resolve(
        self, session: AsyncSession, token: str, *, tenant_id: uuid.UUID
    ) -> WaitlistEntry:
        """Hash, look up, then `compare_digest` the raw value back against the
        stored hash. The second step is redundant by construction and shipped
        that way on `/b/{token}` — a lookup keyed on a hash cannot return a row
        whose hash differs — and it is kept because the day the lookup grows a
        prefix index or a cache, it stops being redundant.

        **The lookup carries no tenant predicate and the unique index behind it
        is global**: the caller has no tenant of its own, the token IS the tenant
        resolution. Tenancy is enforced by RLS inside this host-resolved session,
        so a token minted for another boutique is filtered out and answers the
        same 404 an invented one gets.
        """
        entry = await self._entries.by_offer_token_hash(session, manage_token_hash(token))
        if entry is None or entry.offer_token_hash is None:
            raise OfferNotFoundError
        if not manage_token_matches(token, entry.offer_token_hash):
            raise OfferNotFoundError
        if entry.tenant_id != tenant_id:  # pragma: no cover — RLS already refused
            raise OfferNotFoundError
        return entry

    async def _view(
        self, session: AsyncSession, entry: WaitlistEntry, *, now: datetime.datetime
    ) -> WaitlistOfferResponse:
        type_row = await self._types.by_id(session, entry.tenant_id, entry.appointment_type_id)
        status = entry.status
        if (
            status == WaitlistEntryStatus.OFFERED.value
            and entry.offer_expires_at is not None
            and entry.offer_expires_at <= now
        ):
            # The cascade has not swept it yet — up to one poll interval. The
            # page must not render a live offer whose deadline has passed, so the
            # PROJECTION answers the deadline rather than the row's status. The
            # claim's own guard says the same thing in SQL, which is what makes
            # this a display concern and not a second source of truth.
            status = WaitlistEntryStatus.EXPIRED.value
        return WaitlistOfferResponse(
            status=status,
            starts_at=entry.offer_starts_at,
            expires_at=entry.offer_expires_at,
            appointment_type_name=type_row.name if type_row is not None else None,
        )

    async def lookup(self, tenant_id: uuid.UUID, *, token: str) -> WaitlistOfferResponse:
        """The page's first read. It answers a STATE rather than raising for the
        terminal ones, because every one of them has designed copy — expired,
        already claimed, declined — and a 409 would collapse them into the error
        branch."""
        self._meter(tenant_id)
        now = self._now()
        async with tenant_session(self._session_factory, tenant_id) as session:
            entry = await self._resolve(session, token, tenant_id=tenant_id)
            return await self._view(session, entry, now=now)

    async def claim(
        self,
        tenant_id: uuid.UUID,
        *,
        token: str,
        name: str,
        terms_version: int,
        settings: Mapping[str, object] | None = None,
    ) -> BookingClaim:
        """D4's four steps, one transaction.

        `name` comes from the request because `waitlist_entries` has no name
        column and F22 deliberately gave it none — one field, one ask, no prefill
        from `customers`.
        """
        self._meter(tenant_id)
        validate_booking_request(name=name, notes=None, dress_id=None, dress_size=None)
        now = self._now()
        async with tenant_session(self._session_factory, tenant_id) as session:
            entry = await self._resolve(session, token, tenant_id=tenant_id)

            # Before the claim, because accepting a superseded policy is not
            # acceptance and there is no reason to move a row for a request that
            # cannot succeed. The rollback would undo it either way; this just
            # keeps the ordering honest.
            current_terms = await self._terms.current(session, tenant_id)
            if current_terms is None or terms_version != current_terms.version:
                raise TermsStaleError

            type_row = await self._types.by_id(session, tenant_id, entry.appointment_type_id)
            if type_row is None or entry.offer_starts_at is None:
                # An archived type or an entry with no offered instant cannot be
                # claimed and cannot be explained to her either. Same 404.
                raise OfferNotFoundError

            # **THE STATEMENT.** Claim-vs-claim and expiry-vs-late-claim, both
            # decided here, with no lock: zero rows means somebody or something
            # else moved this row first, and the re-read says which.
            if not await self._entries.claim(session, tenant_id, entry.id, now=now):
                current = await self._entries.by_id(session, tenant_id, entry.id)
                raise OfferNotClaimableError(
                    current.status if current is not None else WaitlistEntryStatus.EXPIRED.value
                )
            # She has the seat pending; the text about the offer must not still go
            # out behind it. A no-op once the row is `sent`.
            await self._scheduled.cancel_pending_for_entry(
                session, tenant_id, waitlist_entry_id=entry.id, kind=OFFER_KIND
            )

            due = deposit_due(
                settings,
                type_row,
                gateway_connected=(
                    self._gateway_credentials is not None
                    and await self._gateway_credentials.is_connected(tenant_id, session)
                ),
            )
            # The entry's phone is proven — F22's join burned an OTP for it — so
            # this is the first `customers` row the waitlist has ever written.
            customer = await self._customers.upsert(
                session, tenant_id, phone=entry.phone, name=name.strip()
            )
            manage_token = mint_manage_token()
            booking = await claim_seat(
                session,
                tenant_id=tenant_id,
                starts_at=entry.offer_starts_at,
                now=now,
                customer_id=customer.id,
                appointment_type=type_row,
                terms_version=terms_version,
                manage_token=manage_token,
                due=due,
                rules=self._rules,
                exceptions=self._exceptions,
                bookings=self._bookings,
                scheduled=self._scheduled,
            )
            return BookingClaim(
                booking=booking,
                # Always a fresh insert: `claim_seat` has no replay branch, and
                # the entry's guarded UPDATE above already made a second delivery
                # of this token impossible.
                created=True,
                manage_token=manage_token,
                deposit_due=due,
                deposit_amount_agorot=type_row.deposit_amount_agorot or 0,
            )

    async def decline(self, tenant_id: uuid.UUID, *, token: str) -> WaitlistOfferResponse:
        """«ויתור» — and it is `cancelled`, not "skip this one".

        She leaves the list for that day entirely (D4), which is why the page
        makes it two taps with the consequence spelled out. `cancelled` is the
        state F22 already has for "off the list", and it is what takes her out of
        the active-unique predicate so she can rejoin later if she changes her
        mind. The cascade advances to the next bride on its next tick.
        """
        self._meter(tenant_id)
        now = self._now()
        async with tenant_session(self._session_factory, tenant_id) as session:
            entry = await self._resolve(session, token, tenant_id=tenant_id)
            cancelled = await self._entries.cancel(session, tenant_id, entry.id)
            if cancelled is None:
                # Already terminal. Idempotent by design — a double-tap on a
                # flaky connection answers the state, never an error.
                return await self._view(session, entry, now=now)
            await self._scheduled.cancel_pending_for_entry(
                session, tenant_id, waitlist_entry_id=entry.id, kind=OFFER_KIND
            )
            return await self._view(session, cancelled, now=now)
