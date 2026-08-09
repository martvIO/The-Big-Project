"""The offer cascade — D2's fourth worker job, and it is a POLLER.

**Why there is no "slot freed" hook.** The epic brief assumed a trigger at the
freeing transition. There is no such seam: SIX paths free capacity and
`BookingsRepository.cancel` covers three of them. `DepositSweeper._cancel_orphans`
is a bulk UPDATE, `BookingsRepository.reschedule` frees the source instant in
place with no cancel at all, and an owner WIDENING an availability rule or
deleting an exception frees capacity with **no booking write whatsoever**. A hook
would therefore be six call sites, two of them bulk statements, and would still
miss the availability case entirely. Keying off `waiting` entries instead is one
call site that catches all six, at the cost of up to one poll interval of lag
against a two-hour window (spec Risk 1, accepted).

**Ordered, and the order is the design (D2).**

1. **Expire — at ALL hours.** An offer must be able to die at night, or a slot
   nobody claimed stays locked behind a dead offer until 08:00 and is not even
   directly bookable. D7 decides where the entry lands: `expired` only if its
   offer SMS actually reached `sent`, otherwise back to `waiting`, because the
   clock does not get to run on a text that never left.
2. **Quiet gate.** Inside `[21:00, 08:00)` Jerusalem, return. **Quiet hours gate
   the cascade, never the window** — an offer issued at 20:59 keeps its full
   window to 22:59, and extending it across the block would hold a live slot
   hostage for one bride for ~13 hours.
3. **Offer**, one pair at a time, FIFO, sequential — never a broadcast (#13).

Its own try block in `poll_once`, no new process, no beat, no daemon (#16).
"""

import dataclasses
import datetime
import logging
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.booking.slots_io import day_slots
from app.booking.tokens import manage_token_hash, mint_manage_token
from app.db.repositories.availability import (
    AvailabilityExceptionsRepository,
    AvailabilityRulesRepository,
)
from app.db.repositories.bookings import BookingsRepository
from app.db.repositories.scheduled_messages import ScheduledMessagesRepository
from app.db.repositories.waitlist_entries import WaitlistEntriesRepository
from app.db.tenant import tenant_session
from app.models.constants import (
    ScheduledMessageKind,
    ScheduledMessageStatus,
    WaitlistEntryStatus,
)
from app.storefront.validation import Clock, today_jerusalem
from app.waitlist.schedule import in_quiet_hours, offer_expiry

logger = logging.getLogger("app")

OFFER_KIND = ScheduledMessageKind.WAITLIST_OFFER.value


@dataclasses.dataclass(frozen=True)
class CascadeResult:
    """One tenant, one tick. `returned` counts D7's return-to-`waiting`: an offer
    whose SMS never reached `sent` does not get to consume its window."""

    expired: int = 0
    returned: int = 0
    offered: int = 0

    def __add__(self, other: "CascadeResult") -> "CascadeResult":
        return CascadeResult(
            expired=self.expired + other.expired,
            returned=self.returned + other.returned,
            offered=self.offered + other.offered,
        )


class WaitlistCascade:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        window_seconds: int,
        min_lead_seconds: int,
        quiet_start_hour: int,
        quiet_end_hour: int,
        clock: Clock | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._window = datetime.timedelta(seconds=window_seconds)
        self._min_lead = datetime.timedelta(seconds=min_lead_seconds)
        self._quiet_start_hour = quiet_start_hour
        self._quiet_end_hour = quiet_end_hour
        # Injectable for the same reason `DepositSweeper`'s is: the deadline is
        # written by the offer step and read by the expiry step and by the
        # claim, and a test that cannot move all three together cannot pin the
        # race at all.
        self._clock = clock
        self._entries = WaitlistEntriesRepository()
        self._scheduled = ScheduledMessagesRepository()
        self._rules = AvailabilityRulesRepository()
        self._exceptions = AvailabilityExceptionsRepository()
        self._bookings = BookingsRepository()

    def _now(self) -> datetime.datetime:
        now = self._clock() if self._clock is not None else datetime.datetime.now(datetime.UTC)
        return now.astimezone(datetime.UTC)

    async def run(self, tenant_id: uuid.UUID) -> CascadeResult:
        """One tenant, one tick, ONE `tenant_session` — so the poller stays
        inside the RLS posture the worker's other three jobs keep (D6)."""
        now = self._now()
        async with tenant_session(self._session_factory, tenant_id) as session:
            result = await self._expire(session, tenant_id, now)
            if in_quiet_hours(
                now, start_hour=self._quiet_start_hour, end_hour=self._quiet_end_hour
            ):
                return result
            return result + await self._issue(session, tenant_id, now)

    async def _expire(
        self, session: AsyncSession, tenant_id: uuid.UUID, now: datetime.datetime
    ) -> CascadeResult:
        """Step 1. Read the due rows, split them by D7's question, then two
        guarded bulk UPDATEs — `_expire_holds`'s shape, answer off RETURNING.

        The read is a plain SELECT with no locking clause and `close_offer`
        re-asserts `status='offered'`, so a claim landing in between simply makes
        the transition match nothing. That is the whole expiry-vs-late-claim
        arbitration and it needs no lock (race 3).
        """
        due = await self._entries.due_offers(session, tenant_id, now=now)
        if not due:
            return CascadeResult()
        # ponytail: one message read per due entry, bounded by the repository's
        # 200-row page. At pilot volume the steady state is zero and the busy
        # state is single digits; batch it if F29's scale pass ever measures it.
        sent: list[uuid.UUID] = []
        unsent: list[uuid.UUID] = []
        for entry in due:
            message = await self._scheduled.latest_for_entry(
                session, tenant_id, waitlist_entry_id=entry.id, kind=OFFER_KIND
            )
            reached_sent = (
                message is not None and message.status == ScheduledMessageStatus.SENT.value
            )
            (sent if reached_sent else unsent).append(entry.id)

        expired = await self._entries.close_offer(
            session, tenant_id, sent, status=WaitlistEntryStatus.EXPIRED.value
        )
        returned = await self._entries.close_offer(
            session, tenant_id, unsent, status=WaitlistEntryStatus.WAITING.value
        )
        for entry_id in expired + returned:
            # An entry leaving `offered` must not leave a text about that offer
            # queued behind it. For the `expired` half this is usually a no-op
            # (the row is already `sent`); for the `returned` half it is the
            # whole point.
            await self._scheduled.cancel_pending_for_entry(
                session, tenant_id, waitlist_entry_id=entry_id, kind=OFFER_KIND
            )
        for entry_id in returned:
            # D7's residual, made visible: with a provider down this line repeats
            # once per window for ONE entry. It is the signal that the adapter is
            # broken, so it is logged per occurrence rather than aggregated away.
            logger.warning(
                "waitlist offer for entry %s was never sent — returning it to waiting", entry_id
            )
        return CascadeResult(expired=len(expired), returned=len(returned))

    async def _issue(
        self, session: AsyncSession, tenant_id: uuid.UUID, now: datetime.datetime
    ) -> CascadeResult:
        """Steps 3-6. Silence is the steady state: no slot, no waiting entry, or
        a lost guard all fall through without a log line or an error, because
        every boutique reaches this on every 60-second tick."""
        pairs = await self._entries.waiting_pairs(
            session, tenant_id, from_day=today_jerusalem(lambda: now)
        )
        offered = 0
        for day, appointment_type_id in pairs:
            if await self._offer_one(session, tenant_id, now, day, appointment_type_id):
                offered += 1
        return CascadeResult(offered=offered)

    async def _offer_one(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        now: datetime.datetime,
        day: datetime.date,
        appointment_type_id: uuid.UUID,
    ) -> bool:
        entry = await self._entries.oldest_waiting(
            session, tenant_id, day=day, appointment_type_id=appointment_type_id
        )
        if entry is None:
            # The pair was read a statement ago; a cancellation since then is
            # not an error, it is the next tick's business.
            return False
        # ponytail: one day-grid materialization per (day, type) pair holding a
        # waiting entry, per tick. Same work one storefront page load does, and
        # #12's basis is a 4-5 person queue. F29's scale pass revisits.
        slots = await day_slots(
            session,
            tenant_id=tenant_id,
            day=day,
            now=now,
            rules=self._rules,
            exceptions=self._exceptions,
            bookings=self._bookings,
        )
        # ⚠ The lead rule lives in ONE place — `offer_expiry` returning None —
        # and the walk is what makes that possible. Taking the earliest slot and
        # THEN testing the lead would drop a whole day when only its opening hour
        # is too close, silently losing every later slot on it.
        for slot in slots:
            expires_at = offer_expiry(
                now, slot.starts_at, window=self._window, min_lead=self._min_lead
            )
            if expires_at is not None:
                break
        else:
            return False

        token = mint_manage_token()
        moved = await self._entries.offer(
            session,
            tenant_id,
            entry.id,
            now=now,
            starts_at=slot.starts_at,
            expires_at=expires_at,
            token_hash=manage_token_hash(token),
        )
        if not moved:
            # Another worker offered this entry between the pair read and here.
            # A no-op, not an error — this guard IS the cascade-vs-cascade answer.
            return False
        try:
            # The savepoint is what keeps a converged INSERT from rolling back
            # the offer transition beside it: the pending-unique index means the
            # other worker has already queued this exact SMS, so the right answer
            # is to stop, not to unwind.
            async with session.begin_nested():
                await self._scheduled.insert(
                    session,
                    tenant_id=tenant_id,
                    waitlist_entry_id=entry.id,
                    kind=OFFER_KIND,
                    send_after=now,
                    # The RAW token, its existing semantics verbatim: kept only
                    # while pending, cleared on every terminal transition. The
                    # entry beside it holds the sha256 and nothing else.
                    manage_token=token,
                )
        except IntegrityError:
            return False
        return True
