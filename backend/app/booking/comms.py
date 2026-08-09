"""The booking lifecycle's SMS side: what gets sent, when it gets scheduled, and
what happens when the provider is absent or refuses.

Every send goes through `NotificationService.send_sms`, which stays the single
writer of `message_log` — nothing here touches that table. Templates live in
`comms_templates.py` as pure functions; this module owns the orchestration, the
schedule and the failure semantics.

**The failure semantics are split because F11 split them**, and the split is not
cosmetic. `SmsSendError` means a configured provider refused: the `failed`
`message_log` row already exists, so the error is swallowed and the evidence is
the record. `SmsNotConfiguredError` is raised *before* any insert
(`notifications/service.py:104-105`, a deliberate F11 ruling) and leaves no row
at all — so this module checks `is_configured` up front and skips with one app-log
warning instead. Until the real provider adapter lands, confirmations are
evidence-free by that F11 design, and the booking stands as a 201 either way.
"""

import dataclasses
import datetime
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.booking.comms_templates import (
    PAYMENT_RECEIVED_NO_SLOT_BODY,
    confirmation_sms_body,
    manage_link,
    mask_manage_link,
    offer_link,
    owner_cancel_sms_body,
    owner_reschedule_sms_body,
    reminder_sms_body,
    waitlist_offer_sms_body,
)
from app.booking.tokens import manage_token_hash, mint_manage_token
from app.db.repositories.bookings import BookingsRepository
from app.db.repositories.customers import CustomersRepository
from app.db.repositories.scheduled_messages import ScheduledMessagesRepository
from app.db.repositories.waitlist_entries import WaitlistEntriesRepository
from app.db.tenant import tenant_session
from app.models.booking import Booking
from app.models.constants import (
    BookingStatus,
    MessageKind,
    ScheduledMessageKind,
    ScheduledMessageStatus,
    WaitlistEntryStatus,
)
from app.models.scheduled_message import ScheduledMessage
from app.notifications.base import (
    SmsNotConfiguredError,
    SmsRecipientErasedError,
    SmsSendError,
)
from app.notifications.service import NotificationService, WallClock
from app.storefront.validation import profile_text

logger = logging.getLogger("app")

# The 24h mark (PRD §6 via architecture.md).
REMINDER_LEAD_SECONDS = 86_400
# Under two hours the confirmation SMS is seconds old, and a second message is
# noise rather than service (D3).
REMINDER_SUPPRESS_UNDER_SECONDS = 7_200

# How many due rows one tenant yields per tick. Bounded so a backlog after a
# deploy drains over several ticks instead of holding one transaction — and one
# row's lock — for minutes.
DRAIN_BATCH_SIZE = 50


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def reminder_send_after(
    *, starts_at: datetime.datetime, now: datetime.datetime
) -> datetime.datetime | None:
    """When the reminder for `starts_at` should go out, or None for no reminder.

    D3's three bands: >=24h out -> `starts_at - 24h`; 2-24h -> now (immediate,
    because she still gets the confirm-attendance ask); <2h -> nothing.

    Arithmetic on UTC instants, deliberately: "24 hours before" is 86 400 real
    seconds, and across an Israeli DST boundary that is 23 or 25 local wall-clock
    hours. The body renders from `starts_at`, so a reminder that lands early or
    late still states the true local time.
    """
    lead = (starts_at - now).total_seconds()
    if lead < REMINDER_SUPPRESS_UNDER_SECONDS:
        return None
    if lead >= REMINDER_LEAD_SECONDS:
        return starts_at - datetime.timedelta(seconds=REMINDER_LEAD_SECONDS)
    return now


async def upsert_reminder(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    booking_id: uuid.UUID,
    starts_at: datetime.datetime,
    now: datetime.datetime,
    bookings: BookingsRepository,
    scheduled: ScheduledMessagesRepository,
    token: str | None = None,
) -> datetime.datetime | None:
    """An UPSERT, never a re-target — and that distinction is the whole point.

    Cancel any pending row, then create a fresh one from the NEW `starts_at`
    under the D3 bands including the <2h suppression, regardless of whether
    the prior row was `sent`, `cancelled`, or never existed. A day-of
    reschedule is the common case and its old reminder has already fired, so
    "update the pending row" would be a silent no-op that ships green-tested.

    Takes a session rather than opening one, so a caller already inside a
    transaction can make the reminder rewrite part of it — F15's reschedule
    needs exactly that, because post-commit a crash loses or mis-schedules the
    reminder with nothing sweeping for the gap, and `drain_due` can claim the
    stale pending row and clear its token in the window. `reschedule_reminder`
    below is the one-line wrapper that opens its own `tenant_session`.

    `token`, when given, is a raw manage token the CALLER has already committed
    the hash of in this same transaction — F19's deferred confirm (D13). It wins
    over the carried one, and it must: `set_manage_token_hash` overwrites
    unconditionally, so a row inheriting the old token would carry a link that
    the caller's own write has just invalidated. Defaulted, so F15's
    `reschedule_reminder` caller is unchanged.

    Returns the new `send_after`, or None when the new time is inside the
    suppression window.
    """
    send_after = reminder_send_after(starts_at=starts_at, now=now)
    pending = await scheduled.pending_for_booking(
        session, tenant_id, booking_id=booking_id, kind=ScheduledMessageKind.REMINDER.value
    )
    # Read the token BEFORE cancelling — cancel_pending clears it.
    carried = pending.manage_token if pending is not None else None
    await scheduled.cancel_pending(
        session, tenant_id, booking_id=booking_id, kind=ScheduledMessageKind.REMINDER.value
    )
    if send_after is None:
        return None
    row_token = token if token is not None else carried
    if row_token is None:
        # Nothing pending to inherit the link from, and the hash is
        # one-way, so the new row needs a new token. Only reached when
        # the prior reminder already sent.
        row_token = mint_manage_token()
        await bookings.set_manage_token_hash(
            session, tenant_id, booking_id, token_hash=manage_token_hash(row_token)
        )
    await scheduled.insert(
        session,
        tenant_id=tenant_id,
        booking_id=booking_id,
        kind=ScheduledMessageKind.REMINDER.value,
        send_after=send_after,
        manage_token=row_token,
    )
    return send_after


@dataclasses.dataclass(frozen=True)
class CommsTenant:
    """The tenant identity a body needs: the display name, the slug the link is
    built on, and the published phone the owner-cancel body points at.

    A narrow value object rather than either ORM row, because the two callers
    hold different ones — the router has a `TenantContext` from the host
    middleware, the worker has a `Tenant` from the RLS-free tenants table.
    """

    id: uuid.UUID
    slug: str
    name: str
    phone: str | None = None

    @classmethod
    def from_settings(
        cls, *, tenant_id: uuid.UUID, slug: str, name: str, settings: dict[str, object]
    ) -> "CommsTenant":
        profile = settings.get("profile")
        return cls(
            id=tenant_id,
            slug=slug,
            name=name,
            # Same ""-to-null collapse as the public boutique projection: an owner
            # who cleared the field left "" or " " behind, and both mean "not set".
            phone=profile_text(profile if isinstance(profile, dict) else {}, "phone"),
        )


@dataclasses.dataclass(frozen=True)
class DrainResult:
    """One tenant, one tick. `deferred` counts rows left pending because no
    provider is configured — the pre-provider backlog, which flushes itself on
    the first tick after the adapter lands."""

    sent: int = 0
    failed: int = 0
    cancelled: int = 0
    deferred: int = 0


class BookingCommsService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        notifications: NotificationService,
        base_domain: str,
        clock: WallClock = _utc_now,
    ) -> None:
        self._session_factory = session_factory
        self._notifications = notifications
        self._base_domain = base_domain
        self._clock = clock
        self._bookings = BookingsRepository()
        self._customers = CustomersRepository()
        self._scheduled = ScheduledMessagesRepository()
        self._entries = WaitlistEntriesRepository()

    def link_for(self, tenant: CommsTenant, token: str) -> str:
        return manage_link(slug=tenant.slug, base_domain=self._base_domain, token=token)

    # --- the sends ---------------------------------------------------------

    async def send_confirmation(
        self, tenant: CommsTenant, *, booking: Booking, manage_token: str
    ) -> bool:
        """Post-commit, and only for a booking that was actually created — the
        0009 replay path carries no raw token, so "the replay must not resend" is
        structural rather than a remembered `if`.

        Returns whether an SMS was handed to the provider. The caller ignores it:
        a 201 is a 201 whether or not the text went out, and propagating a send
        failure would turn a committed booking into a 503.
        """
        if not self._notifications.is_configured:
            # Not a swallow: this one warning is the ONLY observable trace of a
            # skipped lifecycle send before a provider exists (spec Risk 3), and
            # F11 raises before any insert so there is no message_log row.
            logger.warning("SMS not configured — no confirmation for booking %s", booking.id)
            return False
        phone = await self._customer_phone(tenant.id, booking.customer_id)
        if phone is None:
            return False
        body = confirmation_sms_body(
            boutique_name=tenant.name,
            starts_at=booking.starts_at,
            manage_url=self.link_for(tenant, manage_token),
        )
        return await self._deliver(
            tenant.id,
            phone=phone,
            body=body,
            kind=MessageKind.CONFIRMATION,
            booking=booking,
            token=manage_token,
        )

    async def notify_owner_cancel(self, tenant: CommsTenant, *, booking: Booking) -> bool:
        """F15's seam — built and unit-tested here, called when the owner console
        ships. Carries no money words: the refund/forfeit clause is added when
        E4 #19 exists to compute one (spec Risk 6)."""
        if not self._notifications.is_configured:
            logger.warning("SMS not configured — no owner-cancel notice for booking %s", booking.id)
            return False
        phone = await self._customer_phone(tenant.id, booking.customer_id)
        if phone is None:
            return False
        body = owner_cancel_sms_body(
            boutique_name=tenant.name,
            starts_at=booking.starts_at,
            boutique_phone=tenant.phone,
        )
        return await self._deliver(
            tenant.id, phone=phone, body=body, kind=MessageKind.OWNER_CANCEL, booking=booking
        )

    async def notify_payment_received_no_slot(
        self, tenant: CommsTenant, *, booking: Booking
    ) -> bool:
        """F19 MD2's seam: her deposit settled after the hold had already been
        swept and her seat given away, and the rebind could not put her back.

        `notify_owner_cancel`'s shape minus the token, because the body carries
        no manage link — so `_deliver` gets `token=None`, `log_body` stays None,
        and there is nothing in the stored evidence to mask. It exists because
        `_deliver` is private and no shipped public method carries this kind;
        this is the ONLY path in the whole flow where a customer's money moved
        and nothing else would tell her.
        """
        if not self._notifications.is_configured:
            logger.warning("SMS not configured — no no-slot notice for booking %s", booking.id)
            return False
        phone = await self._customer_phone(tenant.id, booking.customer_id)
        if phone is None:
            return False
        return await self._deliver(
            tenant.id,
            phone=phone,
            body=PAYMENT_RECEIVED_NO_SLOT_BODY,
            kind=MessageKind.PAYMENT_RECEIVED_NO_SLOT,
            booking=booking,
        )

    async def notify_owner_reschedule(self, tenant: CommsTenant, *, booking: Booking) -> bool:
        """F15's other seam. `booking` already carries the NEW `starts_at`, and
        `manage_token_hash` is whatever `reschedule_reminder` left on the row —
        so this reads the live token off the pending reminder rather than being
        handed one.

        The spec sketched this as `notify_owner_reschedule(booking, old_starts_at)`.
        The approved Hebrew states only the new time, so there is no old value to
        render and the parameter is gone rather than carried unused.
        """
        if not self._notifications.is_configured:
            logger.warning("SMS not configured — no reschedule notice for booking %s", booking.id)
            return False
        phone = await self._customer_phone(tenant.id, booking.customer_id)
        if phone is None:
            return False
        token = await self._live_token(tenant.id, booking.id)
        if token is None:
            # No pending reminder means no recoverable link (bookings holds only
            # the sha256), so rotate: the customer's newest message must carry a
            # link that works, and the message that carried the old one now
            # states a time that is no longer true.
            token = await self._rotate(tenant.id, booking.id)
            if token is None:
                return False
        body = owner_reschedule_sms_body(
            boutique_name=tenant.name,
            starts_at=booking.starts_at,
            manage_url=self.link_for(tenant, token),
        )
        return await self._deliver(
            tenant.id,
            phone=phone,
            body=body,
            kind=MessageKind.OWNER_RESCHEDULE,
            booking=booking,
            token=token,
        )

    async def reissue_manage_token(
        self, tenant: CommsTenant, *, booking_id: uuid.UUID
    ) -> str | None:
        """Rotate the hash and resend the confirmation.

        Rotation is the point, not a side effect: the old link went to a number
        that turned out to be wrong, so it has to stop working. Any pending
        reminder is re-pointed at the new token in the same transaction, or it
        would send a link this call just invalidated.

        Kept as a tested seam with no caller: D8 requires the mint-rotate-repoint
        half to run inside F15's own transaction, and this bundles it with the
        send across a `tenant_session` of its own — so it belongs to the surface
        that can afford a second one. F15 calls the public `send_confirmation`
        post-commit with the token it already minted, which is the same message.
        """
        async with tenant_session(self._session_factory, tenant.id) as session:
            booking = await self._bookings.by_id(session, tenant.id, booking_id)
            if booking is None:
                return None
            token = mint_manage_token()
            await self._bookings.set_manage_token_hash(
                session, tenant.id, booking_id, token_hash=manage_token_hash(token)
            )
            pending = await self._scheduled.pending_for_booking(
                session, tenant.id, booking_id=booking_id, kind=ScheduledMessageKind.REMINDER.value
            )
            if pending is not None:
                pending.manage_token = token
        await self.send_confirmation(tenant, booking=booking, manage_token=token)
        return token

    # --- the schedule ------------------------------------------------------

    async def reschedule_reminder(
        self, tenant: CommsTenant, *, booking_id: uuid.UUID, starts_at: datetime.datetime
    ) -> datetime.datetime | None:
        """The seam: `upsert_reminder` in a `tenant_session` of its own.

        The body lives at module level so F15's reschedule can run it on the
        transaction it already holds. `self._clock()` is read HERE, at the call,
        not inside `upsert_reminder` — the injected frozen clocks still govern.
        """
        async with tenant_session(self._session_factory, tenant.id) as session:
            return await upsert_reminder(
                session,
                tenant_id=tenant.id,
                booking_id=booking_id,
                starts_at=starts_at,
                now=self._clock(),
                bookings=self._bookings,
                scheduled=self._scheduled,
            )

    # --- the poller --------------------------------------------------------

    async def drain_due(self, tenant: CommsTenant, *, limit: int = DRAIN_BATCH_SIZE) -> DrainResult:
        """Claim and send this tenant's due reminders. One `tenant_session`, so
        the poller stays inside the RLS posture (D6).

        Ordering inside the loop is load-bearing:

        1. **Re-read the booking.** Cancelled, missing or already started -> flip
           the row to 'cancelled' and send nothing. This is the defence against
           races the schedule-time bands cannot see, and it is also what stops a
           pre-provider backlog from growing without bound.
        2. **Unconfigured provider -> leave the row PENDING and stop.** F11 raises
           before any insert, so there is no evidence row to lean on and marking
           it `failed` would be a lie. Leaving it pending is what makes the
           backlog flush itself on the first tick after the adapter lands.
        3. `SmsSendError` -> 'failed'. The `message_log` row already carries the
           reason, so this table does not repeat it.
        """
        now = self._clock()
        sent = failed = cancelled = deferred = 0
        async with tenant_session(self._session_factory, tenant.id) as session:
            rows = await self._scheduled.claim_due(session, tenant.id, now=now, limit=limit)
            for index, row in enumerate(rows):
                if row.kind == ScheduledMessageKind.WAITLIST_OFFER.value:
                    outcome = await self._drain_offer(session, tenant, row, now=now)
                    if outcome is None:
                        # Unconfigured provider. Same rule as the reminder half:
                        # leave every remaining row PENDING and stop, so the
                        # backlog flushes itself on the first tick after the
                        # adapter lands. D7 then returns the entry to `waiting`
                        # at its deadline — the clock does not run on an unsent
                        # text.
                        deferred = len(rows) - index
                        logger.warning(
                            "SMS not configured — %d due message(s) left pending for tenant %s",
                            deferred,
                            tenant.id,
                        )
                        break
                    sent += outcome == ScheduledMessageStatus.SENT.value
                    failed += outcome == ScheduledMessageStatus.FAILED.value
                    cancelled += outcome == ScheduledMessageStatus.CANCELLED.value
                    continue
                # `booking_id` is nullable from 0032 — a `waitlist_offer` row's
                # subject is an ENTRY. None here therefore falls into the
                # cancel branch below, which is also the right answer for the
                # impossible case of a reminder row with no booking.
                booking = (
                    await self._bookings.by_id(session, tenant.id, row.booking_id)
                    if row.booking_id is not None
                    else None
                )
                if (
                    booking is None
                    or booking.status != BookingStatus.CONFIRMED.value
                    or booking.starts_at <= now
                ):
                    await self._scheduled.mark(
                        session, tenant.id, row.id, status=ScheduledMessageStatus.CANCELLED.value
                    )
                    cancelled += 1
                    continue
                if not self._notifications.is_configured:
                    deferred = len(rows) - index
                    logger.warning(
                        "SMS not configured — %d due reminder(s) left pending for tenant %s",
                        deferred,
                        tenant.id,
                    )
                    break
                phone = await self._customer_phone(tenant.id, booking.customer_id, session=session)
                if row.manage_token is None or phone is None:
                    # No recoverable link, or an unreachable customer. 'failed'
                    # rather than a retry loop: neither condition heals on its
                    # own, and F15's resend is the remedy surface.
                    logger.warning(
                        "reminder %s has no token or no reachable phone — marking failed", row.id
                    )
                    await self._scheduled.mark(
                        session, tenant.id, row.id, status=ScheduledMessageStatus.FAILED.value
                    )
                    failed += 1
                    continue
                body = reminder_sms_body(
                    boutique_name=tenant.name,
                    starts_at=booking.starts_at,
                    manage_url=self.link_for(tenant, row.manage_token),
                )
                delivered = await self._deliver(
                    tenant.id,
                    phone=phone,
                    body=body,
                    kind=MessageKind.REMINDER,
                    booking=booking,
                    token=row.manage_token,
                )
                await self._scheduled.mark(
                    session,
                    tenant.id,
                    row.id,
                    status=(
                        ScheduledMessageStatus.SENT.value
                        if delivered
                        else ScheduledMessageStatus.FAILED.value
                    ),
                )
                sent += delivered
                failed += not delivered
        return DrainResult(sent=sent, failed=failed, cancelled=cancelled, deferred=deferred)

    async def _drain_offer(
        self,
        session: AsyncSession,
        tenant: CommsTenant,
        row: ScheduledMessage,
        *,
        now: datetime.datetime,
    ) -> str | None:
        """F23 D7's branch. Returns the status this row was marked with, or None
        for "no provider — leave it pending and stop the batch".

        **It re-reads the ENTRY where the reminder path re-reads the BOOKING**,
        and asks the same question in the same order: is the subject still in the
        state that justified queuing this text? Not `offered` — claimed,
        declined, expired, or cancelled by the owner — or a deadline that has
        already passed means the text is about a dead offer, so it is cancelled
        and nothing is sent. That re-read is the defence against every race the
        schedule could not see, exactly as it is for the reminder.

        A passed deadline is checked HERE as well as by the cascade because the
        two run in the same tick and the ordering between them is not guaranteed:
        texting a link that the very next statement will invalidate is worse than
        one wasted read.
        """
        entry = (
            await self._entries.by_id(session, tenant.id, row.waitlist_entry_id)
            if row.waitlist_entry_id is not None
            else None
        )
        if (
            entry is None
            or entry.status != WaitlistEntryStatus.OFFERED.value
            or entry.offer_expires_at is None
            or entry.offer_expires_at <= now
            or entry.offer_starts_at is None
        ):
            await self._scheduled.mark(
                session, tenant.id, row.id, status=ScheduledMessageStatus.CANCELLED.value
            )
            return ScheduledMessageStatus.CANCELLED.value
        if not self._notifications.is_configured:
            return None
        if row.manage_token is None:
            # No recoverable link. `failed` rather than a retry loop: the token
            # is unrecoverable by construction (only its sha256 survives), so
            # this never heals on its own and the cascade re-offers her instead.
            logger.warning("waitlist offer %s has no token — marking failed", row.id)
            await self._scheduled.mark(
                session, tenant.id, row.id, status=ScheduledMessageStatus.FAILED.value
            )
            return ScheduledMessageStatus.FAILED.value
        body = waitlist_offer_sms_body(
            boutique_name=tenant.name,
            slot_starts_at=entry.offer_starts_at,
            deadline=entry.offer_expires_at,
            sent_at=now,
            offer_url=offer_link(
                slug=tenant.slug, base_domain=self._base_domain, token=row.manage_token
            ),
        )
        delivered = await self._deliver_offer(
            tenant.id, phone=entry.phone, body=body, token=row.manage_token
        )
        status = (
            ScheduledMessageStatus.SENT.value if delivered else ScheduledMessageStatus.FAILED.value
        )
        await self._scheduled.mark(session, tenant.id, row.id, status=status)
        return status

    # --- internals ---------------------------------------------------------

    async def _deliver_offer(
        self, tenant_id: uuid.UUID, *, phone: str, body: str, token: str
    ) -> bool:
        """`_deliver`'s twin for a message with NO booking.

        Not a parameter on `_deliver`: that one takes a `Booking` and stamps
        `booking_id` on the evidence row, and threading a `Booking | None`
        through it would make the reminder path's non-null guarantee a runtime
        question. `message_log.booking_id` is nullable, so an offer's row is
        simply booking-less — the phone and the masked body are the evidence,
        which is all D7 asks for.

        The token is masked for the reminder's reason exactly: `waitlist_entries`
        stores only the sha256, so the raw value may not sit in the forever-table
        beside its own hash.
        """
        try:
            await self._notifications.send_sms(
                tenant_id,
                phone=phone,
                body=body,
                kind=MessageKind.WAITLIST_OFFER.value,
                log_body=mask_manage_link(body, token),
            )
        except SmsSendError:
            logger.warning("waitlist offer send failed for tenant %s", tenant_id)
            return False
        except SmsNotConfiguredError:
            logger.warning("waitlist offer skipped for tenant %s — no provider", tenant_id)
            return False
        except SmsRecipientErasedError:
            logger.warning("waitlist offer skipped for tenant %s — recipient erased", tenant_id)
            return False
        return True

    async def _deliver(
        self,
        tenant_id: uuid.UUID,
        *,
        phone: str,
        body: str,
        kind: MessageKind,
        booking: Booking,
        token: str | None = None,
    ) -> bool:
        try:
            await self._notifications.send_sms(
                tenant_id,
                phone=phone,
                body=body,
                kind=kind.value,
                booking_id=booking.id,
                # The evidence row must not store the raw token beside its own
                # hash on `bookings` — that would defeat hashed storage entirely.
                log_body=None if token is None else mask_manage_link(body, token),
            )
        except SmsSendError:
            # The provider refused. The `failed` message_log row already exists,
            # so the evidence is the record and this must not become a 5xx for a
            # committed booking (D4).
            logger.warning("%s send failed for booking %s", kind.value, booking.id)
            return False
        except SmsNotConfiguredError:
            # Raced the is_configured check, or the sender changed underneath.
            # No message_log row exists by F11's design.
            logger.warning("%s skipped for booking %s — no provider", kind.value, booking.id)
            return False
        except SmsRecipientErasedError:
            # She was erased or scrubbed between this booking's read and the
            # send. Same shape as the two above and for the same reason — a
            # committed booking must not become a 5xx — but it is NOT the same
            # fact, so it is not the same log line. No message_log row exists,
            # by F20's design: there is nothing to evidence.
            logger.warning("%s skipped for booking %s — recipient erased", kind.value, booking.id)
            return False
        return True

    async def _customer_phone(
        self,
        tenant_id: uuid.UUID,
        customer_id: uuid.UUID,
        *,
        session: AsyncSession | None = None,
    ) -> str | None:
        """Every booking's phone is already normalized E.164 (F11 normalizes at
        OTP send), so this is a read and never a re-normalization."""
        if session is not None:
            customer = await self._customers.by_id(session, tenant_id, customer_id)
        else:
            async with tenant_session(self._session_factory, tenant_id) as own:
                customer = await self._customers.by_id(own, tenant_id, customer_id)
        if customer is None:
            logger.warning("booking customer %s is missing — no SMS sent", customer_id)
            return None
        return customer.phone

    async def _live_token(self, tenant_id: uuid.UUID, booking_id: uuid.UUID) -> str | None:
        async with tenant_session(self._session_factory, tenant_id) as session:
            pending = await self._scheduled.pending_for_booking(
                session, tenant_id, booking_id=booking_id, kind=ScheduledMessageKind.REMINDER.value
            )
            return None if pending is None else pending.manage_token

    async def _rotate(self, tenant_id: uuid.UUID, booking_id: uuid.UUID) -> str | None:
        token = mint_manage_token()
        async with tenant_session(self._session_factory, tenant_id) as session:
            updated = await self._bookings.set_manage_token_hash(
                session, tenant_id, booking_id, token_hash=manage_token_hash(token)
            )
        return None if updated is None else token
