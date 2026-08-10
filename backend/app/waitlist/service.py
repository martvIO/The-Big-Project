"""F22's join: F13's create shape minus the booking (spec D2).

One `tenant_session`, F13's step order — validate, CHECK the budgets, prove the
phone, SPEND the budgets, resolve the type, INSERT — and the whole race answer
is the active-unique index: two concurrent joins for one (tenant, phone, day,
type) collapse to one row and two identical 201 bodies, via IntegrityError ->
re-read under a SAVEPOINT. Zero new error codes.

**The savepoint is what makes D2's token sentence true.** The duplicate's
IntegrityError must not roll back the whole transaction: `consume_verification`
already ran in it, and single-use is the token's contract — a duplicate join
spends her verification. `begin_nested()` confines the rollback to the INSERT,
so the burn commits with the 201 either way.

**The server deliberately does not verify the day is actually full** (D2):
requiring fullness at join is a TOCTOU race against concurrent cancellations,
and the CTA only renders on an empty day. A hand-crafted join for an open day
strands its own author — bounded, accepted, recorded.

**No `customers` write.** A waitlist entry carries its own proven phone and
creates no customer until F23's claim runs the real booking path.
"""

import datetime
import uuid
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.service import StaffContext
from app.booking.service import BookingNotFoundError, PhoneNotVerifiedError
from app.db.repositories.appointment_types import AppointmentTypesRepository
from app.db.repositories.audit_log import AuditLogRepository
from app.db.repositories.scheduled_messages import ScheduledMessagesRepository
from app.db.repositories.waitlist_entries import WaitlistEntriesRepository
from app.db.tenant import tenant_session
from app.models.appointment_type import AppointmentType
from app.models.constants import AuditAction, ScheduledMessageKind
from app.models.customer import Customer
from app.models.waitlist_entry import WaitlistEntry
from app.notifications.service import OtpService
from app.notifications.validation import normalize_israeli_mobile
from app.storefront.validation import Clock, today_jerusalem
from app.waitlist.schemas import (
    ManageWaitlistResponse,
    ManageWaitlistRow,
    WaitlistJoinResponse,
)
from app.waitlist.validation import WaitlistThrottledError, validate_waitlist_day


class WaitlistService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        otp: OtpService,
        phone_limiter: FixedWindowRateLimiter,
        tenant_limiter: FixedWindowRateLimiter,
        clock: Clock | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._otp = otp
        # ⚠ TWO OWN INSTANCES, never a key on BookingService's create limiter:
        # max_attempts lives on the LIMITER, so a shared instance is one ceiling
        # for both surfaces and waitlist joins could eat the booking budget
        # (.memory/limiter-max-is-per-instance, restated at every limiter in
        # main.py). test_waitlist_api.py pins the wiring.
        self._phone_limiter = phone_limiter
        self._tenant_limiter = tenant_limiter
        self._clock = clock
        self._entries = WaitlistEntriesRepository()
        self._types = AppointmentTypesRepository()
        self._scheduled = ScheduledMessagesRepository()
        self._audit = AuditLogRepository()

    async def join(
        self,
        tenant_id: uuid.UUID,
        *,
        raw_phone: str,
        verification_token: str,
        day: datetime.date,
        appointment_type_id: uuid.UUID,
    ) -> WaitlistJoinResponse:
        # 1. Shape first, so a bad day costs neither budget nor token.
        phone = normalize_israeli_mobile(raw_phone)
        validate_waitlist_day(day, clock=self._clock)

        # 2. CHECK both budgets, SPEND after proof — F13's comment at
        #    booking/service.py:300-313 applied verbatim: metering an unproven
        #    caller would let anyone exhaust a boutique's join allowance with
        #    garbage tokens.
        tenant_key = f"waitlist:join:{tenant_id}"
        phone_key = f"waitlist:join:{tenant_id}:{phone}"
        if self._tenant_limiter.is_blocked(tenant_key) or self._phone_limiter.is_blocked(phone_key):
            raise WaitlistThrottledError

        async with tenant_session(self._session_factory, tenant_id) as session:
            # 3. Prove the phone. First, so a caller who cannot gets no further.
            verified = await self._otp.consume_verification(
                session, tenant_id, raw_phone=raw_phone, verification_token=verification_token
            )
            if not verified:
                raise PhoneNotVerifiedError

            # Proven — spend both. In-memory, so this survives nothing rolling
            # back below: one verified phone gets a bounded number of joins.
            self._tenant_limiter.record_failure(tenant_key)
            self._phone_limiter.record_failure(phone_key)

            # 4. The appointment type — unknown, archived and foreign-tenant are
            #    one indistinguishable 404 (RLS + the explicit predicate).
            type_row = await self._types.by_id(session, tenant_id, appointment_type_id)
            if type_row is None:
                raise BookingNotFoundError

            # 5. INSERT under a savepoint. The duplicate's IntegrityError rolls
            #    back the INSERT alone — the token burn above commits either way
            #    — and the re-read answers the row that refused us: she asked to
            #    be on the list; she is. Same body, same 201, whichever caller
            #    wins the race.
            row = None
            try:
                async with session.begin_nested():
                    row = await self._entries.insert(
                        session,
                        tenant_id=tenant_id,
                        day=day,
                        appointment_type_id=appointment_type_id,
                        phone=phone,
                    )
            except IntegrityError:
                row = await self._entries.by_active_tuple(
                    session,
                    tenant_id,
                    phone=phone,
                    day=day,
                    appointment_type_id=appointment_type_id,
                )
            if row is None:  # pragma: no cover — the index that refused us holds the row
                raise BookingNotFoundError
            return WaitlistJoinResponse(
                day=row.day,
                appointment_type_id=row.appointment_type_id,
                status=row.status,
            )

    # --- the manage half (D5) -------------------------------------------------

    async def list_entries(
        self, tenant_id: uuid.UUID, *, day: datetime.date | None = None
    ) -> ManageWaitlistResponse:
        """Active entries, `(day, created_at)` — the row order IS the position.
        No `day` = all upcoming (`day >= today`, hiding the dead past-day rows
        the retention sweep owns); a given `day` answers exactly that day, past
        days included — an owner filtering backwards sees what was there."""
        async with tenant_session(self._session_factory, tenant_id) as session:
            rows = await self._entries.list_active(
                session,
                tenant_id,
                day=day,
                from_day=None if day is not None else today_jerusalem(self._clock),
            )
            decorated = await self._decorate(session, tenant_id, rows)
            return ManageWaitlistResponse(entries=decorated)

    async def cancel_entry(
        self, tenant_id: uuid.UUID, *, entry_id: uuid.UUID, actor: StaffContext
    ) -> ManageWaitlistRow:
        """The guarded UPDATE — `WHERE status IN ('waiting','offered')` since F23
        D8. Rowcount 0 with the row present is the idempotent double-tap —
        answered with the row as-is, no second audit row; rowcount 0 with no row
        is the shipped 404 (foreign-tenant indistinguishable by design).

        **The widening is why the message cancel is here.** Taking an `offered`
        entry off the list kills a live offer a bride may be holding right now,
        and leaving her queued SMS behind would text her a link to claim a seat
        she has just been removed from. Same transaction as the status change, so
        the two cannot come apart; the repository clears the token with the same
        UPDATE for the same reason.

        The audit row's `details` carry {entry_id, day, appointment_type_id}
        and NO PHONE — F20's `phone_last4` rule made moot by carrying no phone
        at all. It rides the cancel's own transaction."""
        async with tenant_session(self._session_factory, tenant_id) as session:
            cancelled = await self._entries.cancel(session, tenant_id, entry_id)
            if cancelled is None:
                existing = await self._entries.by_id(session, tenant_id, entry_id)
                if existing is None:
                    raise BookingNotFoundError
                return (await self._decorate(session, tenant_id, [existing]))[0]
            await self._scheduled.cancel_pending_for_entry(
                session,
                tenant_id,
                waitlist_entry_id=cancelled.id,
                kind=ScheduledMessageKind.WAITLIST_OFFER.value,
            )
            await self._audit.record(
                session,
                tenant_id=tenant_id,
                action=AuditAction.WAITLIST_ENTRY_CANCELLED,
                actor_id=actor.id,
                entity=str(cancelled.id),
                details={
                    "entry_id": str(cancelled.id),
                    "day": cancelled.day.isoformat(),
                    "appointment_type_id": str(cancelled.appointment_type_id),
                },
            )
            return (await self._decorate(session, tenant_id, [cancelled]))[0]

    async def _decorate(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        rows: Iterable[WaitlistEntry],
    ) -> list[ManageWaitlistRow]:
        """The two name decorations, each ONE batched statement (D5): the
        customer name off `(tenant, phone)` — phone is unique per tenant, an
        app-level join with no FK, null for a phone the boutique has never
        booked — and the type name, resolved without a deleted_at filter
        because an archived type still names what she asked for."""
        entries = list(rows)
        if not entries:
            return []
        phones = {entry.phone for entry in entries}
        names = {
            phone: name
            for phone, name in (
                await session.execute(
                    select(Customer.phone, Customer.name).where(
                        Customer.tenant_id == tenant_id,
                        Customer.phone.in_(phones),
                        Customer.deleted_at.is_(None),
                    )
                )
            ).all()
        }
        type_ids = {entry.appointment_type_id for entry in entries}
        type_names = {
            type_id: name
            for type_id, name in (
                await session.execute(
                    select(AppointmentType.id, AppointmentType.name).where(
                        AppointmentType.tenant_id == tenant_id,
                        AppointmentType.id.in_(type_ids),
                    )
                )
            ).all()
        }
        return [
            ManageWaitlistRow(
                id=entry.id,
                day=entry.day,
                appointment_type_id=entry.appointment_type_id,
                appointment_type_name=type_names.get(entry.appointment_type_id),
                phone=entry.phone,
                customer_name=names.get(entry.phone),
                status=entry.status,
                created_at=entry.created_at,
                offer_starts_at=entry.offer_starts_at,
                offer_expires_at=entry.offer_expires_at,
            )
            for entry in entries
        ]
