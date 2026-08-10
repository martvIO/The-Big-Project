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

# The MODULE, not `from … import ISSUE_BATCH_SIZE`: a from-import binds a second
# name, and `_issue`'s saturation test would then read a different number from
# the LIMIT that produced the page the moment anything rebinds one of them.
from app.db.repositories import waitlist_entries as entries_repo
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

# How many refused offer texts an entry gets before D7's return-to-`waiting`
# stops applying to it.
#
# D7 reasoned about a provider-wide OUTAGE, which self-heals on the first tick
# after the adapter recovers. It does not cover a permanently unreachable
# RECIPIENT — a number that replied STOP — for whom the loop offer -> failed ->
# waiting never terminates, and who blocks her whole (day, type) queue for the
# full window on every cycle because `waiting_pairs` excludes a pair holding a
# live offer. Three is enough windows (six hours at the shipped two) for a real
# outage to recover, and it bounds the undeliverable case at three.
#
# She lands in `expired`, not `cancelled`: `expired` is the terminal the manage
# console already renders, it takes her out of the active-unique predicate so she
# can rejoin, and the queue behind her advances on the next tick.
_MAX_OFFER_SEND_FAILURES = 3


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
        # Where the last tick stopped walking this tenant's (day, type) pairs.
        # In-process on purpose: it is a fairness hint, not a fact — a restart
        # or a second worker simply starts its own walk at the top, which costs
        # a repeat, never a miss. Persisting it would buy nothing and add a
        # write to the hottest path in the poller.
        self._issue_cursor: dict[uuid.UUID, tuple[datetime.date, uuid.UUID]] = {}
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
        undeliverable: list[uuid.UUID] = []
        for entry in due:
            message = await self._scheduled.latest_for_entry(
                session, tenant_id, waitlist_entry_id=entry.id, kind=OFFER_KIND
            )
            if message is not None and message.status == ScheduledMessageStatus.SENT.value:
                sent.append(entry.id)
                continue
            # D7's rule, BOUNDED. Without the cap an entry the provider will
            # never accept cycles back to the head of its queue forever and
            # freezes every bride behind her out of that (day, type) for a full
            # window per cycle — see `_MAX_OFFER_SEND_FAILURES`.
            failures = await self._scheduled.count_failed_for_entry(
                session, tenant_id, waitlist_entry_id=entry.id, kind=OFFER_KIND
            )
            (undeliverable if failures >= _MAX_OFFER_SEND_FAILURES else unsent).append(entry.id)

        expired = await self._entries.close_offer(
            session, tenant_id, sent + undeliverable, status=WaitlistEntryStatus.EXPIRED.value
        )
        returned = await self._entries.close_offer(
            session, tenant_id, unsent, status=WaitlistEntryStatus.WAITING.value
        )
        moved = set(expired)
        for entry_id in undeliverable:
            # Only the rows that really moved, exactly as the `returned` loop
            # below only sees `close_offer`'s RETURNING. Louder than that one,
            # because this is a bride dropped off her queue rather than one put
            # back on it.
            if entry_id in moved:
                logger.warning(
                    "waitlist offers for entry %s failed %d times — "
                    "expiring it so the queue advances",
                    entry_id,
                    _MAX_OFFER_SEND_FAILURES,
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
        every boutique reaches this on every 60-second tick.

        **The walk RESUMES, but only when the cap actually bit.**
        `waiting_pairs` is capped so one tick cannot materialize a thousand
        day-grids inside a transaction a bride's claim is queued behind. A cap on
        its own starves, though: only a pair that PRODUCES an offer leaves the
        candidate set, so the first N FULL days — which is exactly why those
        brides are on a waitlist — get re-read on every tick and pair N+1 is
        never reached at all.

        So the cursor advances on a SATURATED read and is cleared on a short one.
        A short page means this read reached the end of the list, so there is no
        horizon to resume past. That distinction is the whole point rather than a
        tidy-up: an unconditional cursor would make every boutique pay for the
        big one's problem — a seat freed behind the cursor would wait for the walk
        to wrap instead of being offered on the very next tick, and almost every
        boutique has a handful of pairs and never reaches the cap at all.
        """
        cursor = self._issue_cursor.get(tenant_id)
        pairs = await self._entries.waiting_pairs(
            session, tenant_id, from_day=today_jerusalem(lambda: now), after=cursor
        )
        if len(pairs) < entries_repo.ISSUE_BATCH_SIZE:
            self._issue_cursor.pop(tenant_id, None)
        else:
            self._issue_cursor[tenant_id] = pairs[-1]
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
        # `day_slots` is type-AGNOSTIC — one grid per day for every appointment
        # type — while `waiting_pairs` keys on (day, TYPE). Two pairs on one day
        # therefore walk the same grid, and without this read they both pick the
        # same earliest free slot and text two brides about one seat. Live
        # `offered` rows are the record of what is already spoken for; the
        # cascade's own UPDATE lands in this transaction, so the same read covers
        # the second pair in THIS tick and every pair in a later one.
        held = await self._entries.offered_instants(session, tenant_id, day=day)
        # ⚠ The lead rule lives in ONE place — `offer_expiry` returning None —
        # and the walk is what makes that possible. Taking the earliest slot and
        # THEN testing the lead would drop a whole day when only its opening hour
        # is too close, silently losing every later slot on it.
        for slot in slots:
            # Counted against `remaining`, not skipped outright: a two-seat
            # instant can carry two live offers without either being a broadcast.
            if slot.remaining <= held.get(slot.starts_at, 0):
                continue
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
