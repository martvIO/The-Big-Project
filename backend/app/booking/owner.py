"""The owner console's booking surface: the day list, the detail, the four
transitions, reschedule, phone correction and the resend.

Session-authed, CSRF-fenced and `no-store`, so unlike the tokenized manage page
this one may carry the customer's phone and her notes — the operational point of
the screen is that the owner can call the bride and read what she wrote (D18).
"""

import dataclasses
import datetime
import uuid
from collections.abc import Iterable

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.service import StaffContext
from app.booking.comms import BookingCommsService, upsert_reminder
from app.booking.service import (
    BOOKABLE_HORIZON,
    BookingNotFoundError,
    SlotUnavailableError,
)
from app.booking.slots import Slot
from app.booking.slots_io import offered_slot
from app.booking.tokens import manage_token_hash, mint_manage_token
from app.booking.validation import BOOKING_LIST_MAX_LIMIT
from app.db.repositories.audit_log import AuditLogRepository
from app.db.repositories.availability import (
    AvailabilityExceptionsRepository,
    AvailabilityRulesRepository,
)
from app.db.repositories.bookings import BookingsRepository, CheckInOutcome
from app.db.repositories.customers import CustomersRepository
from app.db.repositories.payments import PaymentsRepository
from app.db.repositories.scheduled_messages import ScheduledMessagesRepository
from app.db.repositories.terms import TermsVersionsRepository
from app.db.tenant import tenant_session
from app.errors import DomainValidationError
from app.models.booking import Booking
from app.models.constants import (
    AuditAction,
    BookingCancelledBy,
    BookingStatus,
    PaymentStatus,
    ScheduledMessageKind,
)
from app.models.customer import Customer
from app.models.terms_version import TermsVersion
from app.notifications.validation import normalize_israeli_mobile
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


def _last4(phone: str | None) -> str | None:
    """The most of a number that may be written down. See `correct_phone`'s
    audit payload for why the ids beside it are the part that matters."""
    return phone[-4:] if phone else None


def refund_due_agorot(
    *,
    amount_agorot: int,
    starts_at: datetime.datetime,
    at: datetime.datetime,
    refundable_until_hours_before: int,
    forfeit_percent: int,
) -> int:
    """D16, and A1's live consumer is the owner's marker.

    COMPUTED, never stored: the port ships no `refund()` and `forfeit_percent`
    is a percentage, so F19 writes no `refund_due` / `refunded` / `forfeited`
    row anywhere — this number is rendered and nothing else. F29 owns execution.

    Both inputs come from the terms version she ACCEPTED, never the current one:
    a boutique that republishes its policy must not retroactively rewrite what a
    booked bride is owed.

    `at` is the instant the consequence is evaluated at — `cancelled_at` on a
    cancelled booking, `now` on a live one, which is `owner.cancel`'s own stated
    rule. The cutoff hour itself is still INSIDE the window: "refundable until 48
    hours before" includes the 48th, and the alternative silently forfeits half a
    deposit for a bride who cancelled exactly on time.

    The rounding agora goes to the customer: the boutique forfeits the floor of
    its percentage and she is refunded the remainder (D15 — integer agorot end
    to end, so it has to land somewhere and this is the side it lands on).
    """
    cutoff = starts_at - datetime.timedelta(hours=refundable_until_hours_before)
    if at <= cutoff:
        return amount_agorot
    return amount_agorot - amount_agorot * forfeit_percent // 100


@dataclasses.dataclass(frozen=True)
class BookingPayment:
    """What the owner's row says about the money on one booking (D18 + A1).

    ONE field answers every owner-visible case rather than a second
    discriminator sourced from `audit_log` (which no router reads): `paid` on a
    `cancelled` booking is the action-needed marker MD1's reschedule is the
    button behind, and `failed` is MD4's "booked without a deposit, the payment
    provider was unavailable".
    """

    status: str
    refund_due_agorot: int | None


@dataclasses.dataclass(frozen=True)
class OwnerMutation:
    """What every owner mutation answers, and why it is not a bare `Booking` —
    the `BookingClaim` precedent, for the same two reasons.

    `changed` is False for the two no-ops the graph deliberately answers 200 to:
    a repeat of the same transition (D3 step 2) and a reschedule to the instant
    the booking already holds (D5 step 3). The router reads it to decide whether
    to send — nothing happened, so nothing is texted.

    `manage_token` carries the raw token minted INSIDE the transaction for the
    edited booking. sha256 is one-way, so it travels out of here or the
    post-commit `send_confirmation` has no link to put in the message.
    """

    booking: Booking
    changed: bool = True
    manage_token: str | None = None


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
        self._payments = PaymentsRepository()
        self._terms = TermsVersionsRepository()
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
        # Same reason, one line earlier in the pipeline. The router declares a
        # bare `datetime.date`, so pydantic accepts the whole range, and
        # `?date=9999-12-31` is among the first things anyone probes: `date + 1
        # day` raises OverflowError at the top, and at the bottom boutique
        # midnight on `0001-01-01` is `0000-12-31T22:00Z`, which underflows in
        # `.astimezone()`. Either escapes as a bare 500 outside the house error
        # shape (`storefront/service.py`'s `slot_window`, `reschedule` step 0).
        # Comparison cannot overflow, so this guard is total.
        if not datetime.date.min < date < datetime.date.max:
            raise DomainValidationError("date is out of range")
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

    async def customers_for(
        self, tenant_id: uuid.UUID, customer_ids: Iterable[uuid.UUID]
    ) -> dict[uuid.UUID, Customer]:
        """The name on every list row and the phone on the detail.

        `bookings` snapshots the appointment type and the dress but NOT the
        person: `customers` is the phone identity and D8's correction rewrites
        it in place, so a snapshot here would render the number the owner just
        fixed. One statement per request, keyed for the caller.
        """
        ids = list(dict.fromkeys(customer_ids))
        if not ids:
            return {}
        async with tenant_session(self._session_factory, tenant_id) as session:
            rows = await self._customers.by_ids(session, tenant_id, ids)
        return {row.id: row for row in rows}

    async def payments_for(
        self, tenant_id: uuid.UUID, bookings: Iterable[Booking]
    ) -> dict[uuid.UUID, BookingPayment]:
        """The marker on every row that has one (D18), keyed for the caller.

        ONE batch read behind the page, never one per row — the
        `customers_for` precedent, and the reason `by_booking_ids` exists.
        Bookings with no payment row are simply absent from the map, which is
        every booking a deposits-off boutique takes.

        The terms lookup is per DISTINCT accepted version rather than per row,
        and only for the paid ones: a day's bookings almost always share one
        version, so this is one extra statement, not N.
        """
        rows = list(bookings)
        if not rows:
            return {}
        now = self._now()
        facts: dict[uuid.UUID, BookingPayment] = {}
        async with tenant_session(self._session_factory, tenant_id) as session:
            payments = await self._payments.by_booking_ids(
                session, tenant_id, [row.id for row in rows]
            )
            if not payments:
                return {}
            accepted: dict[int, TermsVersion | None] = {}
            for booking in rows:
                payment = payments.get(booking.id)
                if payment is None:
                    continue
                refund: int | None = None
                # Only money actually taken has a refund question. A pending
                # hold, a swept `expired` one and MD4's `failed` marker all mean
                # nothing moved, so the honest answer is no number at all.
                if payment.status == PaymentStatus.PAID.value:
                    version = booking.terms_version_accepted
                    if version not in accepted:
                        accepted[version] = await self._terms.by_version(
                            session, tenant_id, version
                        )
                    terms = accepted[version]
                    if terms is not None:
                        refund = refund_due_agorot(
                            amount_agorot=payment.amount_agorot,
                            starts_at=booking.starts_at,
                            # The consequence is evaluated at the moment she
                            # cancelled, not at the moment the owner opened the
                            # list — `owner.cancel`'s own rule, and the reason a
                            # cancel is refused on an attended booking.
                            at=booking.cancelled_at or now,
                            refundable_until_hours_before=terms.refundable_until_hours_before,
                            forfeit_percent=terms.forfeit_percent,
                        )
                facts[booking.id] = BookingPayment(status=payment.status, refund_due_agorot=refund)
        return facts

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

    # --- the D3 transition graph -------------------------------------------
    #
    # All four verbs run the same five ordered steps inside ONE tenant_session:
    #
    #   1. load          — missing is a 404
    #   2. compare       — already at the target is a 200, unchanged, NO audit row
    #   3. raise         — an illegal pair or an illegal clock is a 409, nothing written
    #   4. guarded write — carrying the same predicate as belt to the Python braces
    #   5. audit         — same transaction, before commit
    #
    # Step 4 is not redundant with step 3: the predicate is what makes the write
    # safe under a concurrent writer, and the Python check above it is what makes
    # the ANSWER honest — a predicate-guarded UPDATE returns zero rows for an
    # illegal transition AND for a legal repeat, so the statement result alone
    # cannot separate the 409 from the 200 step 2 promises.

    async def confirm(
        self, tenant_id: uuid.UUID, booking_id: uuid.UUID, *, staff: StaffContext
    ) -> OwnerMutation:
        """The undo of a mis-tapped no-show or completed.

        No clock bound: a mis-tap is correctable whenever it is noticed. And it
        writes `status` ONLY — `attendance_confirmed_at` is F16's column and
        means the BRIDE said she is coming, so the owner correcting her own
        record of the outcome does not get to speak for her (D3).
        """
        return await self._transition(
            tenant_id,
            booking_id,
            staff=staff,
            to=BookingStatus.CONFIRMED.value,
            allowed_from=(BookingStatus.NO_SHOW.value, BookingStatus.COMPLETED.value),
            action=AuditAction.BOOKING_CONFIRMED,
        )

    async def no_show(
        self, tenant_id: uuid.UUID, booking_id: uuid.UUID, *, staff: StaffContext
    ) -> OwnerMutation:
        return await self._transition(
            tenant_id,
            booking_id,
            staff=staff,
            to=BookingStatus.NO_SHOW.value,
            allowed_from=(BookingStatus.CONFIRMED.value, BookingStatus.COMPLETED.value),
            action=AuditAction.BOOKING_NO_SHOW,
            past_only=True,
        )

    async def complete(
        self, tenant_id: uuid.UUID, booking_id: uuid.UUID, *, staff: StaffContext
    ) -> OwnerMutation:
        return await self._transition(
            tenant_id,
            booking_id,
            staff=staff,
            to=BookingStatus.COMPLETED.value,
            allowed_from=(BookingStatus.CONFIRMED.value, BookingStatus.NO_SHOW.value),
            action=AuditAction.BOOKING_COMPLETED,
            past_only=True,
        )

    async def _transition(
        self,
        tenant_id: uuid.UUID,
        booking_id: uuid.UUID,
        *,
        staff: StaffContext,
        to: str,
        allowed_from: tuple[str, ...],
        action: AuditAction,
        past_only: bool = False,
    ) -> OwnerMutation:
        """The three non-cancel verbs. Cancel keeps its own body below: it uses a
        different writer (the shipped one, shared with the customer path), guards
        the opposite side of `starts_at`, and has a side effect the others do not.

        `past_only` is D3's whole shape. Marking no-show or completed is a thing
        you do to a PAST appointment — both are attendance records; cancelling is
        a thing you do to a future one, because it frees a seat and texts the
        customer. The split falls exactly at `now`.
        """
        now = self._now()
        async with tenant_session(self._session_factory, tenant_id) as session:
            booking = await self._bookings.by_id(session, tenant_id, booking_id)
            if booking is None:
                raise BookingNotFoundError
            if booking.status == to:
                return OwnerMutation(booking=booking, changed=False)
            if booking.status not in allowed_from:
                raise BookingTransitionInvalidError(f"{booking.status} -> {to}")
            if past_only and booking.starts_at > now:
                raise BookingTransitionInvalidError(f"{booking.status} -> {to} before starts_at")
            # Captured BEFORE the write, and that is not style. The repository's
            # UPDATE is ORM-enabled DML: `synchronize_session` defaults to
            # `evaluate` for these predicates, which stamps the SET values onto
            # this very instance, and the writer's trailing `by_id` returns the
            # same object. Reading `booking.status` after the call would record
            # {from: no_show, to: no_show} — `allowed_from` is genuinely
            # two-valued for all three verbs, so `from` carries real information
            # and losing it empties the trail D2 exists for.
            from_status = booking.status
            updated = await self._bookings.set_status(
                session,
                tenant_id,
                booking_id,
                to=to,
                allowed_from=allowed_from,
                not_after=now if past_only else None,
            )
            if updated is None:
                # Another request moved the row between the read and here. The
                # raise rolls the transaction back BEFORE the audit row, rather
                # than committing evidence for a move that did not happen.
                raise BookingTransitionInvalidError(f"{from_status} -> {to}")
            await self._record(
                session,
                tenant_id,
                staff=staff,
                action=action,
                booking_id=booking_id,
                details={"from": from_status, "to": to},
            )
            return OwnerMutation(booking=updated)

    # --- F34's check-in pair -------------------------------------------------
    #
    # The same five ordered steps as the graph above, with one difference that is
    # the whole of spec D4(5): step 4 does not answer `Booking | None`. A guarded
    # UPDATE matches zero rows for two causes that mean OPPOSITE things — she is
    # already checked in (200 unchanged) and somebody cancelled her in the gap
    # (409) — so the repository returns a three-valued outcome and this branches
    # on THAT, never on the row it loaded in step 1.

    async def check_in(
        self, tenant_id: uuid.UUID, booking_id: uuid.UUID, *, staff: StaffContext
    ) -> OwnerMutation:
        """Record that this person is physically in the boutique.

        No clock bound, in either direction: a bride arriving twenty minutes
        early is the ordinary case the board exists for, and `starts_at <= now`
        would refuse it. An early arrival is not a lie, it is a fact with a
        timestamp.

        Steps 2 and 3 are the shipped shape's Python pre-checks and they STAY —
        they are what makes the answer honest in the uncontended case. What is
        new is step 4's aftermath: the REPOSITORY says which of the three things
        happened, because only it holds the `.returning()` scalar and the
        refreshed row at the same moment.
        """
        now = self._now()
        async with tenant_session(self._session_factory, tenant_id) as session:
            booking = await self._bookings.by_id(session, tenant_id, booking_id)
            if booking is None:
                raise BookingNotFoundError
            if booking.checked_in_at is not None:
                # The outcome the caller wanted is the outcome that holds, and
                # the audit row belongs to whoever actually wrote it.
                return OwnerMutation(booking=booking, changed=False)
            if booking.status != BookingStatus.CONFIRMED.value:
                raise BookingTransitionInvalidError(f"{booking.status} -> checked_in")
            outcome, refreshed = await self._bookings.check_in(
                session, tenant_id, booking_id, at=now
            )
            match outcome:
                case CheckInOutcome.MISSING:
                    raise BookingNotFoundError
                case CheckInOutcome.NOT_CONFIRMED:
                    # A cancel landed between the read and the write. The raise
                    # rolls back BEFORE the audit row, rather than committing
                    # evidence for a check-in that did not happen.
                    raise BookingTransitionInvalidError(f"{booking.status} -> checked_in")
                case CheckInOutcome.ALREADY_CHECKED_IN:
                    # Another staffer won the race. `refreshed` carries HER
                    # timestamp, which is the guarantee this case exists to make.
                    assert refreshed is not None
                    return OwnerMutation(booking=refreshed, changed=False)
                case CheckInOutcome.WROTE:
                    assert refreshed is not None
                    await self._record(
                        session,
                        tenant_id,
                        staff=staff,
                        action=AuditAction.BOOKING_CHECKED_IN,
                        booking_id=booking_id,
                        details={"checked_in_at": now.isoformat()},
                    )
                    return OwnerMutation(booking=refreshed)

    async def undo_check_in(
        self, tenant_id: uuid.UUID, booking_id: uuid.UUID, *, staff: StaffContext
    ) -> OwnerMutation:
        """The undo of a mis-tapped check-in. **No status guard at all** (D5, the
        `/confirm` precedent), so its only failure is a 404: a bride checked in
        and then cancelled must still have the mis-tap undoable, or a wrong
        arrival record is permanent on a surface where the tap is one finger
        wide.

        `previous_checked_in_at` is captured BEFORE the write and that is not
        style — it is the same reason `_transition` captures `from_status`
        first. Clearing the column destroys the only copy of the arrival time
        and `bookings` has no history table, so reading it after the write
        (which stamps the in-memory instance) would record the destruction and
        not the value.
        """
        async with tenant_session(self._session_factory, tenant_id) as session:
            booking = await self._bookings.by_id(session, tenant_id, booking_id)
            if booking is None:
                raise BookingNotFoundError
            if booking.checked_in_at is None:
                return OwnerMutation(booking=booking, changed=False)
            previous = booking.checked_in_at
            outcome, refreshed = await self._bookings.undo_check_in(session, tenant_id, booking_id)
            if outcome is CheckInOutcome.MISSING or refreshed is None:
                raise BookingNotFoundError
            if outcome is not CheckInOutcome.WROTE:
                # A concurrent undo got there first. 200 unchanged, no audit
                # row, rendering the DATABASE's NULL rather than this request's.
                return OwnerMutation(booking=refreshed, changed=False)
            await self._record(
                session,
                tenant_id,
                staff=staff,
                action=AuditAction.BOOKING_CHECK_IN_UNDONE,
                booking_id=booking_id,
                details={"previous_checked_in_at": previous.isoformat()},
            )
            return OwnerMutation(booking=refreshed)

    async def cancel(
        self, tenant_id: uuid.UUID, booking_id: uuid.UUID, *, staff: StaffContext
    ) -> OwnerMutation:
        """Owner cancel — and it must kill its own pending reminder.

        `notify_owner_cancel` does not touch `scheduled_messages`
        (`comms.py:187-204`), so without the `cancel_pending` below the customer
        gets a cancellation SMS and then, hours later, a reminder for the
        appointment that was cancelled. `ManageBookingService.cancel` already
        does exactly this for the customer path and F15 mirrors it.

        Not metered by the owner-SMS limiter (D10): `cancelled` is terminal, so
        this is at most one SMS per booking and the ceiling is the number of
        bookings the boutique has.
        """
        now = self._now()
        target = BookingStatus.CANCELLED.value
        async with tenant_session(self._session_factory, tenant_id) as session:
            booking = await self._bookings.by_id(session, tenant_id, booking_id)
            if booking is None:
                raise BookingNotFoundError
            if booking.status == target:
                # Checked BEFORE the clock, the `manage.py:158-161` shape: a
                # second tap on an already-cancelled appointment is the same
                # success even once its time has passed.
                return OwnerMutation(booking=booking, changed=False)
            if booking.status != BookingStatus.CONFIRMED.value:
                # no_show / completed -> cancelled is forbidden for a reason of
                # its own: E4 #19 evaluates refund-due versus forfeit from
                # `cancelled_at`, and writing it on a booking the bride actually
                # attended would make that evaluation lie.
                raise BookingTransitionInvalidError(f"{booking.status} -> {target}")
            if booking.starts_at <= now:
                raise BookingTransitionInvalidError(f"{target} after starts_at")
            from_status = booking.status
            updated = await self._bookings.cancel(
                session,
                tenant_id,
                booking_id,
                at=now,
                by=BookingCancelledBy.OWNER.value,
                not_before=now,
            )
            # `None` is `cancel`'s own `.returning()` scalar and nothing else can
            # substitute for it. Re-reading the row cannot answer this question:
            # a bride cancelling on her manage link in the same window leaves
            # `status = 'cancelled'`, which IS the target, and the ORM's
            # `evaluate` synchronization has already stamped
            # `cancelled_by = 'owner'` onto the in-memory instance regardless of
            # what the database matched — so even the evidence columns lie. The
            # status check below is belt only. The one case still
            # indistinguishable is a concurrent OWNER cancel, whose audit row
            # would be a duplicate of a truthful one.
            if updated is None or updated.status != target:
                raise BookingTransitionInvalidError(f"{from_status} -> {target}")
            await self._scheduled.cancel_pending(
                session,
                tenant_id,
                booking_id=booking_id,
                kind=ScheduledMessageKind.REMINDER.value,
            )
            await self._record(
                session,
                tenant_id,
                staff=staff,
                action=AuditAction.BOOKING_CANCELLED,
                booking_id=booking_id,
                details={"from": from_status, "to": target},
            )
            return OwnerMutation(booking=updated)

    # --- the D5 reschedule protocol ----------------------------------------

    async def reschedule(
        self,
        tenant_id: uuid.UUID,
        booking_id: uuid.UUID,
        *,
        new_starts_at: datetime.datetime,
        staff: StaffContext,
    ) -> OwnerMutation:
        """An in-place UPDATE of `(starts_at, seat_index)` on the same row —
        never a cancel-and-reinsert, which would write `cancelled_at` on a
        booking that was never cancelled, break the customer's manage link,
        orphan the `scheduled_messages` row, re-snapshot the terms evidence and
        break the deposit carry-over the epic promises (D4).

        Eight steps in one transaction, and the ORDER is the correctness
        argument, not an implementation detail.

        **MD1 widened step 2 to admit `cancelled`, and ONLY with her money still
        on the row.** A bride whose deposit landed after the sweeper released her
        seat keeps the deposit and gets a new time; this is the button behind
        D18's marker, and without it that marker tells the owner THAT something
        is wrong with nothing to do about it. Her alternative was rebooking on
        the storefront, which opens a SECOND hold and charges a SECOND deposit.

        Not D5's rebind, which restores her own seat at her own time
        automatically when it is still free. This is what the owner does
        afterwards, by hand and by phone, when it is not.
        """
        now = self._now()
        # 0. Before ANY arithmetic on `new_starts_at`. `AwareDatetime` accepts
        #    the entire datetime range and `.astimezone()` on a year-9999
        #    instant raises OverflowError — an unhandled 500. Comparison itself
        #    cannot overflow, so this guard is total (service.py:180-186).
        if not now < new_starts_at <= now + BOOKABLE_HORIZON:
            raise SlotUnavailableError
        # Consulted BEFORE the transaction opens (D10), so a 429 writes nothing
        # and sends nothing. Reschedule is metered because it is UNBOUNDED: a
        # booking can be walked A<->B<->A between two offered slots forever,
        # each hop a real SMS plus a reminder rewrite plus a token rotation.
        budget = self._sms_budget_key(tenant_id)
        if self._sms_limiter.is_blocked(budget):
            raise OwnerResendThrottledError

        async with tenant_session(self._session_factory, tenant_id) as session:
            # 1. BEFORE any read of the booking. Skipping the lock does not
            #    oversell — the index is the backstop — but reading outside it
            #    races a public create, and worse: two submissions of the same
            #    dialog would both see the ORIGINAL starts_at, the second would
            #    miss the no-op short-circuit below, and step 5 would then find
            #    the booking ITSELF. Every value used below comes from the
            #    post-lock read.
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:tenant_id))"),
                {"tenant_id": str(tenant_id)},
            )

            # 2. Load and guard. A FUTURE booking that is confirmed, or one that
            #    is cancelled and still holds her deposit (MD1). A past one is an
            #    attendance question either way — rewriting its `starts_at` would
            #    overwrite the record D3 forbids lying about and text the bride a
            #    confirmation for the appointment she missed.
            booking = await self._bookings.by_id(session, tenant_id, booking_id)
            if booking is None:
                raise BookingNotFoundError
            if booking.status not in (
                BookingStatus.CONFIRMED.value,
                BookingStatus.CANCELLED.value,
            ):
                # `pending_payment` is refused with everything else: the money is
                # not in, the sweeper owns that row, and moving a live checkout's
                # seat would hand the bride a hosted page for a time she no
                # longer holds.
                raise BookingTransitionInvalidError(f"reschedule from {booking.status}")
            if booking.starts_at <= now:
                raise BookingTransitionInvalidError("reschedule after starts_at")
            restoring = booking.status == BookingStatus.CANCELLED.value
            if restoring and not await self._holds_a_paid_deposit(session, tenant_id, booking_id):
                # A cancellation with no money behind it is terminal, exactly as
                # it was before MD1: undoing an ordinary customer or owner cancel
                # is not a scheduling operation, and the seat has been publicly
                # bookable ever since.
                raise BookingTransitionInvalidError("reschedule from cancelled without a deposit")

            # 3. The no-op, and it is load-bearing rather than a nicety:
            #    `active_at` and `active_seats_at` have no booking-id exclusion,
            #    so a move to the instant this row already holds would find
            #    itself and 409 a capacity-1 booking against its own seat.
            #    A cancelled row holds NOTHING — both partial unique indexes
            #    exclude it — so the same instant is a real move for it, and the
            #    common one: her own time is often free again.
            if new_starts_at == booking.starts_at and not restoring:
                return OwnerMutation(booking=booking, changed=False)

            # 4. One call buys past instants, off-grid times, closed and
            #    exception days, the DST rules — and capacity, because full
            #    slots are dropped rather than marked.
            slot = await offered_slot(
                session,
                tenant_id=tenant_id,
                starts_at=new_starts_at,
                now=now,
                rules=self._rules,
                exceptions=self._exceptions,
                bookings=self._bookings,
            )
            if slot is None:
                raise SlotUnavailableError

            # 5. A genuinely different failure from a full slot: the target can
            #    have free seats and still be unmovable-into for THIS bride
            #    (0009). Step 3 already excluded the row itself, so a hit here
            #    is always another booking.
            collision = await self._bookings.active_at(
                session, tenant_id, customer_id=booking.customer_id, starts_at=slot.starts_at
            )
            if collision is not None:
                raise CustomerAlreadyBookedError

            # 6. The LOWEST FREE seat at the target — never the old one.
            #    Nothing in the database bounds a seat by its slot's capacity
            #    (0008's CHECK is 1..1000), so seat 3 carried into a capacity-1
            #    target satisfies both the CHECK and the unique index and is a
            #    silent oversell. Capacity is enforced in Python and nowhere else.
            seats = await self._bookings.active_seats_at(
                session, tenant_id, starts_at=slot.starts_at
            )
            seat_index = next(
                (index for index in range(1, slot.capacity + 1) if index not in seats), None
            )
            if seat_index is None:
                raise SlotUnavailableError

            # 7. The move. No extra write releases the source seat — both
            #    partial unique indexes are re-evaluated over the row's new
            #    values at statement time.
            #
            #    The `old_*` half of the audit row is captured HERE, before the
            #    write. `reschedule` is ORM-enabled DML and its default
            #    `evaluate` synchronization stamps the new `starts_at` and
            #    `seat_index` onto this instance, which the trailing `by_id`
            #    then hands back — so reading `booking.starts_at` after the call
            #    would record old == new and make the move unrecoverable from
            #    the one trail the epic's reschedule line exists for.
            old_starts_at = booking.starts_at
            old_seat_index = booking.seat_index
            try:
                if restoring:
                    await self._restore(
                        session, tenant_id, booking_id, starts_at=old_starts_at, now=now
                    )
                updated = await self._bookings.reschedule(
                    session,
                    tenant_id,
                    booking_id,
                    starts_at=slot.starts_at,
                    seat_index=seat_index,
                    not_before=now,
                )
            except IntegrityError as exc:
                raise SlotUnavailableError from exc
            if updated is None:
                # The per-tenant lock serializes this against public creates but
                # NOT against the four owner status endpoints, which take no
                # lock — so a concurrent cancel or no-show landed between step 2
                # and here. Roll back rather than commit an audit row for a move
                # that did not happen and render the old time as though it had.
                raise BookingTransitionInvalidError("reschedule lost to a concurrent write")

            # 8. The reminder rewrite belongs in THIS transaction (D11): post-
            #    commit, a crash leaves the OLD send_after on a pending row or
            #    no reminder at all, and `drain_due` can claim the stale row and
            #    clear its token in the window. A None is NOT an error — the
            #    moved appointment is inside the <2h band and legitimately gets
            #    no reminder.
            await upsert_reminder(
                session,
                tenant_id=tenant_id,
                booking_id=booking_id,
                starts_at=slot.starts_at,
                now=now,
                bookings=self._bookings,
                scheduled=self._scheduled,
            )
            await self._record(
                session,
                tenant_id,
                staff=staff,
                action=AuditAction.BOOKING_RESCHEDULED,
                booking_id=booking_id,
                details={
                    # ISO strings, not datetimes: `details` is JSONB and every
                    # other caller in the repo passes JSON-native scalars — a
                    # `datetime` in here is a TypeError at flush, on the audit
                    # row that is the entire point of the epic's reschedule line.
                    "old_starts_at": old_starts_at.isoformat(),
                    "new_starts_at": slot.starts_at.isoformat(),
                    "old_seat_index": old_seat_index,
                    "new_seat_index": seat_index,
                    # Only on MD1's branch, so the confirmed path's row is
                    # unchanged. It is also the ONLY surviving evidence on this
                    # row that the booking was ever cancelled: the restore clears
                    # `cancelled_at` and `cancelled_by` by design (D5), and
                    # `bookings` has no history table.
                    **({"restored_from": BookingStatus.CANCELLED.value} if restoring else {}),
                },
            )
            result = OwnerMutation(booking=updated)

        # Immediately after the commit, before returning to the router (C4).
        # The send is the router's (D11) and reaching back into it would put
        # limiter plumbing in three handlers to move one line; `_deliver`
        # swallows provider failures and returns False, so there is no
        # post-send value to branch on anyway.
        self._sms_limiter.record_failure(budget)
        return result

    async def _holds_a_paid_deposit(
        self, session: AsyncSession, tenant_id: uuid.UUID, booking_id: uuid.UUID
    ) -> bool:
        """MD1's precondition: her money is still on this booking.

        `paid` and nothing else. A pending hold is a checkout in flight, an
        `expired` one is a hold that was never honoured, and MD4's `failed` row
        is a booking that deliberately took no deposit — none of the three is a
        reason to resurrect a cancelled appointment, and doing so on the strength
        of `cancelled_by = 'expired'` alone would resurrect every ABANDONED
        checkout, which is the common case and has no money behind it at all.
        """
        payment = (await self._payments.by_booking_ids(session, tenant_id, [booking_id])).get(
            booking_id
        )
        return payment is not None and payment.status == PaymentStatus.PAID.value

    async def _restore(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        booking_id: uuid.UUID,
        *,
        starts_at: datetime.datetime,
        now: datetime.datetime,
    ) -> None:
        """MD1's first statement: `cancelled` back to `confirmed`, with the
        cancel evidence cleared in the SAME update.

        `rebind` is that writer and F19 already shipped it — a second one would
        be a second place for the "restore without clearing `cancelled_at`"
        defect to live, and a row reading `confirmed` while carrying cancel
        evidence is exactly what D2 refuses `set_status` over. Both columns feed
        F52's attribution and F20's compliance read.

        **The seat it parks on is transient and never commits.** `rebind` cannot
        move `starts_at`, so between it and step 7's move the row is briefly back
        at its ORIGINAL instant — where `idx_bookings_slot_seat_unique` applies
        again the moment it stops being `cancelled`. Parking on her old seat, or
        on the target's, would collide with whoever took her time, which is the
        precise case MD1 exists for: the 409 would land on the only bookings this
        feature can help. One index past the highest seat in use at that instant
        is free by construction; step 7 overwrites it in the same transaction.
        """
        occupied = await self._bookings.active_seats_at(session, tenant_id, starts_at=starts_at)
        restored = await self._bookings.rebind(
            session,
            tenant_id,
            booking_id,
            seat_index=max(occupied, default=0) + 1,
            allowed_from=(BookingStatus.CANCELLED.value,),
            not_before=now,
        )
        if restored is None:
            # Somebody moved the row between step 2 and here. Roll back rather
            # than commit a half-restored booking.
            raise BookingTransitionInvalidError("restore lost to a concurrent write")

    @staticmethod
    def _sms_budget_key(tenant_id: uuid.UUID) -> str:
        return f"booking:owner_sms:{tenant_id}"

    # --- D8's phone correction and D9's resend -----------------------------
    #
    # The corrected number is OWNER-ATTESTED — no OTP — because requiring one
    # would require the bride to be reachable at the number that demonstrably
    # does not work. That narrows an invariant E3 wrote down three times
    # (verified at creation, owner-attested thereafter), so the mechanics below
    # are not optional polish; they are the whole argument for shipping it.
    #
    # `reissue_manage_token` is deliberately NOT the caller here. It bundles
    # mint + rotate + re-point + send across a `tenant_session` of its OWN, and
    # the mint-rotate-repoint half has to be inside ours: two transactions leave
    # a window where the booking carries the corrected phone and the ORIGINAL
    # hash, so the stranger's link still resolves and still cancels the bride's
    # appointment, with nothing sweeping for it. The service calls the public
    # `send_confirmation` post-commit with the token it already minted, which is
    # the same message.

    async def correct_phone(
        self,
        tenant_id: uuid.UUID,
        booking_id: uuid.UUID,
        *,
        phone: str,
        staff: StaffContext,
    ) -> OwnerMutation:
        """Remedy a number that demonstrably does not work, and revoke every
        link that went to it.

        Two branches, and the difference is what was wrong. Non-collision: the
        DIGITS were wrong, so `customers.phone` is corrected and every live
        booking of that customer rotates — `customers` is the phone identity and
        every future SMS reads it at send time, while `manage_token_hash` is
        per-row. Collision: the IDENTITY was wrong, so the booking re-points at
        the customer who already holds that number, `customers.phone` is never
        touched, both rows survive, and only THIS booking rotates.
        """
        # Normalized first, so a malformed number is a 400 before the budget is
        # even consulted — the same function the claim uses, so the stored value
        # stays E.164 like every other phone in the product.
        normalized = normalize_israeli_mobile(phone)
        budget = self._sms_budget_key(tenant_id)
        if self._sms_limiter.is_blocked(budget):
            raise OwnerResendThrottledError

        now = self._now()
        async with tenant_session(self._session_factory, tenant_id) as session:
            booking = await self._guard_live(session, tenant_id, booking_id, now=now)
            old_customer_id = booking.customer_id
            old_customer = await self._customers.by_id(session, tenant_id, old_customer_id)
            old_phone = old_customer.phone if old_customer is not None else None

            target = await self._customers.by_phone(session, tenant_id, phone=normalized)
            repointed = target is not None and target.id != old_customer_id
            if target is not None and repointed:
                # 0009's index, pre-checked: two sisters in one capacity-2 slot
                # and a correction of the first onto the second's number would
                # put two live rows on (tenant, customer B, that instant). With
                # no error registry the flush escapes as a bare 500, outside the
                # house error shape. A boutique where a party books together
                # makes this ordinary, not exotic.
                collision = await self._bookings.active_at(
                    session, tenant_id, customer_id=target.id, starts_at=booking.starts_at
                )
                if collision is not None:
                    raise CustomerAlreadyBookedError
                try:
                    moved = await self._bookings.set_customer_id(
                        session,
                        tenant_id,
                        booking_id,
                        customer_id=target.id,
                        allowed_from=(BookingStatus.CONFIRMED.value,),
                        not_before=now,
                    )
                except IntegrityError as exc:
                    # The pre-check is the answer; this is the backstop, mapped
                    # to the same error the way `create_booking` treats its own
                    # lost race.
                    raise CustomerAlreadyBookedError from exc
                if moved is None:
                    raise BookingTransitionInvalidError("re-point lost to a concurrent write")
                rotate = [booking]
                new_customer_id = target.id
            else:
                try:
                    written = await self._customers.set_phone(
                        session, tenant_id, old_customer_id, phone=normalized
                    )
                except IntegrityError as exc:
                    # `by_phone` above is a pre-check, and this method takes no
                    # advisory lock — unlike `reschedule` and the public
                    # `create_booking`, both of which write the same
                    # `idx_customers_tenant_phone_unique`. A create claiming
                    # that number, or a second owner tab correcting onto it,
                    # commits in the window and this flush loses. Unmapped it is
                    # a bare 500, the very thing the re-point branch backstops
                    # against nine lines up. Not CUSTOMER_ALREADY_BOOKED: nobody
                    # is double-booked, the number just acquired an owner, and a
                    # retry takes the re-point branch.
                    raise BookingTransitionInvalidError(
                        "phone correction lost to a concurrent write"
                    ) from exc
                if written is None:
                    raise BookingNotFoundError
                # Every live booking of that customer, because the phone write
                # moved all of them onto the new number at once.
                rotate = await self._bookings.list_live_for_customer(
                    session, tenant_id, customer_id=old_customer_id, after=now
                )
                new_customer_id = old_customer_id

            tokens = await self._rotate_links(session, tenant_id, rotate, now=now)
            await self._record(
                session,
                tenant_id,
                staff=staff,
                action=AuditAction.BOOKING_PHONE_CORRECTED,
                booking_id=booking_id,
                details={
                    # Last4 only. `audit_log` is retained on the AUDIT clock, not
                    # the booking clock, and a full number in JSONB is a second
                    # uncontrolled copy of the one PII field this feature edits.
                    # The customer ids are what let an Amendment-13 complaint be
                    # answered at all: `set_phone` overwrites in place and
                    # `customers` has no history table, so without them the
                    # number the link was pointed AWAY from survives nowhere.
                    "old_phone_last4": _last4(old_phone),
                    "new_phone_last4": _last4(normalized),
                    "attested": True,
                    "old_customer_id": str(old_customer_id),
                    "new_customer_id": str(new_customer_id),
                    "repointed": repointed,
                    "rotated_booking_ids": [str(row.id) for row in rotate],
                },
            )
            # Only the EDITED booking's token leaves. Rotating a sibling's token
            # silently is the safety half and must be unconditional; texting the
            # bride N confirmations for N bookings is spend and noise (Risk 9).
            result = OwnerMutation(booking=booking, manage_token=tokens[booking_id])

        self._sms_limiter.record_failure(budget)
        return result

    async def resend_link(
        self, tenant_id: uuid.UUID, booking_id: uuid.UUID, *, staff: StaffContext
    ) -> OwnerMutation:
        """D8's rotation with no phone edit.

        Resend is not a re-send — it invalidates the old link, and the Hebrew
        says so. A plain resend is impossible in any case for a booking whose
        reminder has already fired: `bookings` stores only the sha256 and
        `cancel_pending` clears the raw token off the terminal row, so nothing
        on the platform can reproduce a sent link. Rotation is the only
        behaviour available in every case, which makes it the only honest one.

        No compare-and-swap (D9, the one rejected review finding): two rotations
        seconds apart produce one live link and one dead one, which IS the
        specified behaviour, and the row lock orders the writes so the surviving
        hash is always a real one. The mitigation is the client disabling the
        button while its request is in flight.
        """
        budget = self._sms_budget_key(tenant_id)
        if self._sms_limiter.is_blocked(budget):
            raise OwnerResendThrottledError

        now = self._now()
        async with tenant_session(self._session_factory, tenant_id) as session:
            booking = await self._guard_live(session, tenant_id, booking_id, now=now)
            tokens = await self._rotate_links(session, tenant_id, [booking], now=now)
            await self._record(
                session,
                tenant_id,
                staff=staff,
                action=AuditAction.BOOKING_LINK_RESENT,
                booking_id=booking_id,
                details={"customer_id": str(booking.customer_id)},
            )
            result = OwnerMutation(booking=booking, manage_token=tokens[booking_id])

        self._sms_limiter.record_failure(budget)
        return result

    async def _guard_live(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        booking_id: uuid.UUID,
        *,
        now: datetime.datetime,
    ) -> Booking:
        """Confirmed AND future, or neither operation runs (D8 mechanic 4).

        Evaluated here in Python for the honest answer, and carried again as the
        predicate on every rotation UPDATE below so it cannot go stale
        mid-operation — minting a fresh live control token on a booking that was
        cancelled seconds ago, and texting a confirmation for an appointment
        that no longer exists, is verbatim the outcome the guard prevents.
        """
        booking = await self._bookings.by_id(session, tenant_id, booking_id)
        if booking is None:
            raise BookingNotFoundError
        if booking.status != BookingStatus.CONFIRMED.value:
            raise BookingTransitionInvalidError(f"link rotation on a {booking.status} booking")
        if booking.starts_at <= now:
            raise BookingTransitionInvalidError("link rotation after starts_at")
        return booking

    async def _rotate_links(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        bookings: list[Booking],
        *,
        now: datetime.datetime,
    ) -> dict[uuid.UUID, str]:
        """Mint, rotate the hash under the guard predicate, and re-point the
        pending reminder — for each booking, inside the caller's transaction.

        The reminder re-point is the `reissue_manage_token` idiom verbatim (ORM
        attribute assignment on the loaded row): without it the reminder would
        send a link this rotation just invalidated.

        A `None` back from the rotation is a HARD failure that rolls the whole
        transaction back, never a discarded result. There must be no committed
        state in which the phone is corrected and the old hash survives — the
        stranger's link would still resolve through `by_manage_token_hash` and
        still cancel the bride's appointment at a route that has no phone check.
        """
        tokens: dict[uuid.UUID, str] = {}
        for booking in bookings:
            token = mint_manage_token()
            rotated = await self._bookings.set_manage_token_hash(
                session,
                tenant_id,
                booking.id,
                token_hash=manage_token_hash(token),
                allowed_from=(BookingStatus.CONFIRMED.value,),
                not_before=now,
            )
            if rotated is None:
                raise BookingTransitionInvalidError(
                    f"rotation lost to a concurrent write on booking {booking.id}"
                )
            pending = await self._scheduled.pending_for_booking(
                session,
                tenant_id,
                booking_id=booking.id,
                kind=ScheduledMessageKind.REMINDER.value,
            )
            if pending is not None:
                pending.manage_token = token
            tokens[booking.id] = token
        return tokens

    async def _record(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        staff: StaffContext,
        action: AuditAction,
        booking_id: uuid.UUID,
        details: dict[str, object],
    ) -> None:
        """`entity` is the booking id as a string — the auth precedent puts a
        human-meaningful target there — and `actor_id` is the staff member who
        tapped, which is the whole reason this trail exists (D2)."""
        await self._audit.record(
            session,
            tenant_id=tenant_id,
            action=action.value,
            actor_id=staff.id,
            entity=str(booking_id),
            details=details,
        )
