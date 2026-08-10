"""The cascade's own rules, against real Postgres — everything the race file
does not cover because it is not a race.

Two halves, matching D2's two steps:

* **Expiry runs at ALL hours** (D2.1), and D7's rule decides where the entry
  lands: `expired` only if its offer SMS actually reached `sent`, otherwise back
  to `waiting`. The offer clock does not get to run on a text that never left —
  and since `run()` is expire-then-issue in ONE transaction, `waiting` is where
  the expiry puts her, not somewhere she sits: the same tick re-offers her on a
  fresh token and a fresh full window. What D7 protects is the WINDOW.
* **The offer write is gated by quiet hours, never the window** (D3). Inside
  `[21:00, 08:00)` nothing is issued; the deadline of an offer issued at 20:59
  falls inside the block and is not extended.

⚠ db-marked: first run is CI (no local Docker).

**Every `offered` state here is produced by the cascade itself**, never by a
hand-written UPDATE — the same discipline as the race file. A fixture that
writes `status='offered'` directly can pass while the offer write is broken.
"""

import asyncio
import datetime
import uuid
from collections.abc import Callable, Coroutine
from typing import Any

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.booking.validation import jerusalem_day_index
from app.db.repositories.appointment_types import AppointmentTypesRepository
from app.db.repositories.availability import AvailabilityRulesRepository
from app.db.repositories.scheduled_messages import ScheduledMessagesRepository
from app.db.repositories.waitlist_entries import WaitlistEntriesRepository
from app.db.tenant import tenant_session
from app.models.appointment_type import AppointmentType
from app.models.availability import AvailabilityRule
from app.models.constants import (
    AppointmentAudience,
    ScheduledMessageKind,
    ScheduledMessageStatus,
    WaitlistEntryStatus,
)
from app.models.scheduled_message import ScheduledMessage
from app.models.waitlist_entry import WaitlistEntry
from app.storefront.validation import BOUTIQUE_TIMEZONE
from app.waitlist.cascade import (
    _MAX_OFFER_SEND_FAILURES,
    CascadeResult,
    WaitlistCascade,
)

pytestmark = pytest.mark.db

ENTRIES = WaitlistEntriesRepository()
SCHEDULED = ScheduledMessagesRepository()
KIND = ScheduledMessageKind.WAITLIST_OFFER.value

TARGET_DATE = datetime.date(2026, 8, 23)
WINDOW_SECONDS = 2 * 3600
MIN_LEAD_SECONDS = 2 * 3600

# 12:00 Jerusalem. Outside the quiet block, so the offer half is live.
NOW = datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.UTC)
# 22:00 Jerusalem, INSIDE `[21:00, 08:00)`.
QUIET_NOW = datetime.datetime(2026, 8, 1, 19, 0, tzinfo=datetime.UTC)


def _at(hour: int, minute: int = 0, *, date: datetime.date = TARGET_DATE) -> datetime.datetime:
    return datetime.datetime.combine(
        date, datetime.time(hour, minute), tzinfo=BOUTIQUE_TIMEZONE
    ).astimezone(datetime.UTC)


def _factory(url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(url, poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _run(coro: Callable[[], Coroutine[Any, Any, None]]) -> None:
    asyncio.run(coro())


def _cascade(factory: async_sessionmaker[AsyncSession], now: datetime.datetime) -> WaitlistCascade:
    return WaitlistCascade(
        factory,
        window_seconds=WINDOW_SECONDS,
        min_lead_seconds=MIN_LEAD_SECONDS,
        quiet_start_hour=21,
        quiet_end_hour=8,
        clock=lambda: now,
    )


async def _seed(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    *,
    capacity: int = 1,
    open_time: datetime.time = datetime.time(9, 0),
    close_time: datetime.time = datetime.time(13, 0),
    day: datetime.date = TARGET_DATE,
) -> uuid.UUID:
    """⚠ ONE call per tenant — it provisions the whole boutique. An extra day
    gets an extra RULE, never a second seed."""
    async with tenant_session(factory, tenant_id) as session:
        await AvailabilityRulesRepository().insert(
            session,
            tenant_id=tenant_id,
            day_of_week=jerusalem_day_index(day),
            open_time=open_time,
            close_time=close_time,
            capacity=capacity,
        )
        type_row = await AppointmentTypesRepository().insert(
            session,
            tenant_id=tenant_id,
            name="מדידה ראשונה",
            duration_minutes=60,
            audience=AppointmentAudience.ALL.value,
            deposit_required=False,
            deposit_amount_agorot=None,
            sort_order=0,
        )
        return type_row.id


async def _second_type(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID
) -> uuid.UUID:
    """A second appointment type on the SAME grid — `_seed` provisions one, and
    the day grid is type-agnostic, so this is what makes two (day, type) pairs
    compete for one instant."""
    async with tenant_session(factory, tenant_id) as session:
        row = await AppointmentTypesRepository().insert(
            session,
            tenant_id=tenant_id,
            name="מדידה שנייה",
            duration_minutes=60,
            audience=AppointmentAudience.ALL.value,
            deposit_required=False,
            deposit_amount_agorot=None,
            sort_order=1,
        )
        return row.id


async def _refused_offers(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    entry_id: uuid.UUID,
    *,
    count: int,
) -> None:
    """Prior offer texts the provider refused. `_offer_one` writes exactly one
    row per offer, so these ARE the attempt history `_MAX_OFFER_SEND_FAILURES`
    counts.

    Aged a real day back — `created_at` is a DB default off the WALL clock, not
    off the test clock — so `latest_for_entry` still picks the cascade's own
    message. `failed`, so the pending-unique index has no opinion about them.
    """
    stale = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=1)
    async with tenant_session(factory, tenant_id) as session:
        for _ in range(count):
            session.add(
                ScheduledMessage(
                    tenant_id=tenant_id,
                    waitlist_entry_id=entry_id,
                    kind=KIND,
                    send_after=stale,
                    status=ScheduledMessageStatus.FAILED.value,
                    created_at=stale,
                )
            )
        await session.flush()


async def _join(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    type_id: uuid.UUID,
    *,
    day: datetime.date = TARGET_DATE,
) -> uuid.UUID:
    async with tenant_session(factory, tenant_id) as session:
        row = await ENTRIES.insert(
            session,
            tenant_id=tenant_id,
            day=day,
            appointment_type_id=type_id,
            phone=f"+9725{uuid.uuid4().int % 10**8:08d}",
        )
        return row.id


async def _entry(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, entry_id: uuid.UUID
) -> WaitlistEntry:
    async with tenant_session(factory, tenant_id) as session:
        row = await ENTRIES.by_id(session, tenant_id, entry_id)
    assert row is not None
    return row


async def _message(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, entry_id: uuid.UUID
) -> ScheduledMessage:
    async with tenant_session(factory, tenant_id) as session:
        row = await SCHEDULED.latest_for_entry(
            session, tenant_id, waitlist_entry_id=entry_id, kind=KIND
        )
    assert row is not None
    return row


async def _message_by_id(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, message_id: uuid.UUID
) -> ScheduledMessage:
    """By id, because a re-offered entry has TWO rows and `latest_for_entry`
    answers the new one — the dead offer has to be named to be asserted on."""
    async with tenant_session(factory, tenant_id) as session:
        row = await session.get(ScheduledMessage, message_id)
    assert row is not None
    return row


async def _mark(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    message_id: uuid.UUID,
    *,
    status: str,
) -> None:
    """Through the shipped repository transition, so the terminal states this
    file reasons about are the ones `drain_due` really writes."""
    async with tenant_session(factory, tenant_id) as session:
        await SCHEDULED.mark(session, tenant_id, message_id, status=status)


async def _purge(factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID) -> None:
    async with tenant_session(factory, tenant_id) as session:
        await session.execute(
            delete(ScheduledMessage).where(ScheduledMessage.tenant_id == tenant_id)
        )
        await session.execute(delete(WaitlistEntry).where(WaitlistEntry.tenant_id == tenant_id))
        await session.execute(
            delete(AvailabilityRule).where(AvailabilityRule.tenant_id == tenant_id)
        )
        await session.execute(delete(AppointmentType).where(AppointmentType.tenant_id == tenant_id))


# --- the offer half ---------------------------------------------------------


def test_the_cascade_offers_the_fifo_oldest_waiting_entry(app_role_url: str) -> None:
    """#14, and the whole of the offer write in one pass: the older entry gets
    the offer, the entry carries only the sha256, and the queued message carries
    the raw token nothing else can reproduce."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()

    async def check() -> None:
        try:
            type_id = await _seed(factory, tenant_id)
            first = await _join(factory, tenant_id, type_id)
            second = await _join(factory, tenant_id, type_id)

            result = await _cascade(factory, NOW).run(tenant_id)
            assert result.offered == 1

            older = await _entry(factory, tenant_id, first)
            assert older.status == WaitlistEntryStatus.OFFERED.value
            assert older.offered_at is not None
            # The earliest instant the seeded day offers.
            assert older.offer_starts_at == _at(9, 0)
            assert older.offer_expires_at == NOW + datetime.timedelta(seconds=WINDOW_SECONDS)
            assert older.offer_token_hash is not None
            assert len(older.offer_token_hash) == 64, "sha256 hex, never the raw token"

            younger = await _entry(factory, tenant_id, second)
            assert younger.status == WaitlistEntryStatus.WAITING.value

            message = await _message(factory, tenant_id, first)
            assert message.status == ScheduledMessageStatus.PENDING.value
            assert message.booking_id is None
            assert message.send_after == NOW
            assert message.manage_token is not None
            assert message.manage_token != older.offer_token_hash
        finally:
            await _purge(factory, tenant_id)
            await engine.dispose()

    _run(check)


def test_a_pair_already_holding_an_offer_is_skipped(app_role_url: str) -> None:
    """The `NOT EXISTS` in `waiting_pairs` IS #13's "sequential, no broadcast"
    rule. A second tick with the first offer still live must issue nothing —
    otherwise every tick adds a bride to a slot that seats one."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()

    async def check() -> None:
        try:
            type_id = await _seed(factory, tenant_id, capacity=3)
            await _join(factory, tenant_id, type_id)
            second = await _join(factory, tenant_id, type_id)

            assert (await _cascade(factory, NOW).run(tenant_id)).offered == 1
            assert (await _cascade(factory, NOW).run(tenant_id)).offered == 0
            assert (
                await _entry(factory, tenant_id, second)
            ).status == WaitlistEntryStatus.WAITING.value
        finally:
            await _purge(factory, tenant_id)
            await engine.dispose()

    _run(check)


def test_a_day_whose_slots_are_all_inside_the_lead_is_silent(app_role_url: str) -> None:
    """#15. The boutique opens in ninety minutes and the lead is two hours, so
    there is nothing to offer — and the cascade says nothing at all: no log line
    per tick (this is the steady state near closing), no error, and the entry
    sits `waiting` until the retention purge takes it."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    # 12:00 Jerusalem on the target day itself; the grid runs 13:00-14:00 local,
    # every instant of it inside the 2h lead.
    now = _at(12, 0)

    async def check() -> None:
        try:
            type_id = await _seed(
                factory,
                tenant_id,
                open_time=datetime.time(13, 0),
                close_time=datetime.time(14, 0),
            )
            entry_id = await _join(factory, tenant_id, type_id)

            assert (await _cascade(factory, now).run(tenant_id)).offered == 0
            assert (
                await _entry(factory, tenant_id, entry_id)
            ).status == WaitlistEntryStatus.WAITING.value
        finally:
            await _purge(factory, tenant_id)
            await engine.dispose()

    _run(check)


def test_the_first_slot_past_the_lead_is_the_one_offered(app_role_url: str) -> None:
    """The lead rule lives in ONE place — `offer_expiry` returning None — and the
    cascade walks the day until a slot clears it. Taking the earliest slot and
    then testing the lead would drop the whole day when only its opening hour is
    too close, which is a silent loss of every later slot."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    # 09:30 local on the day itself. The lead clears at `slot - 2h > now`, i.e.
    # `slot > 11:30`, so 10:00 … 11:30 are all refused and 12:00 is the first
    # offerable start on a 30-minute grid.
    now = _at(9, 30)

    async def check() -> None:
        try:
            type_id = await _seed(
                factory,
                tenant_id,
                open_time=datetime.time(10, 0),
                close_time=datetime.time(13, 0),
            )
            entry_id = await _join(factory, tenant_id, type_id)

            assert (await _cascade(factory, now).run(tenant_id)).offered == 1
            entry = await _entry(factory, tenant_id, entry_id)
            assert entry.offer_starts_at == _at(12, 0)
            # #15's truncation, visible: `slot - min_lead` (10:00) beats
            # `now + window` (11:30), so the window is cut to half an hour and an
            # offer can never outlive the appointment it is for.
            assert entry.offer_expires_at == _at(10, 0)
        finally:
            await _purge(factory, tenant_id)
            await engine.dispose()

    _run(check)


def test_quiet_hours_issue_nothing(app_role_url: str) -> None:
    """D3's gate. 22:00 Jerusalem: no offer is issued, and the entry is untouched
    — the clock never starts on a text a bride is asleep for. The cascade resumes
    at 08:00 with a full window."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()

    async def check() -> None:
        try:
            type_id = await _seed(factory, tenant_id)
            entry_id = await _join(factory, tenant_id, type_id)

            assert (await _cascade(factory, QUIET_NOW).run(tenant_id)).offered == 0
            entry = await _entry(factory, tenant_id, entry_id)
            assert entry.status == WaitlistEntryStatus.WAITING.value
            assert entry.offer_token_hash is None
        finally:
            await _purge(factory, tenant_id)
            await engine.dispose()

    _run(check)


# --- the expiry half --------------------------------------------------------


def test_a_sent_offer_that_runs_out_expires(app_role_url: str) -> None:
    """D7's ordinary case: the SMS reached `sent`, she had her window, the offer
    dies and the slot goes back to the pool. `offer_starts_at` AND the token hash
    both survive: her SMS link must keep answering design row E («תוקף ההצעה הזו
    פג» + the rebook CTA) rather than «הקישור אינו תקין», and expiry is the most
    common way an offer ends."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    later = NOW + datetime.timedelta(seconds=WINDOW_SECONDS)

    async def check() -> None:
        try:
            type_id = await _seed(factory, tenant_id)
            entry_id = await _join(factory, tenant_id, type_id)
            assert (await _cascade(factory, NOW).run(tenant_id)).offered == 1
            message = await _message(factory, tenant_id, entry_id)
            await _mark(factory, tenant_id, message.id, status=ScheduledMessageStatus.SENT.value)

            result = await _cascade(factory, later).run(tenant_id)
            assert (result.expired, result.returned) == (1, 0)

            entry = await _entry(factory, tenant_id, entry_id)
            assert entry.status == WaitlistEntryStatus.EXPIRED.value
            assert entry.offer_expires_at is None
            assert entry.offer_starts_at == _at(9, 0)
            assert entry.offer_token_hash is not None, (
                "row E is a LOOKUP on an expired entry — clearing the hash 404s her link"
            )
        finally:
            await _purge(factory, tenant_id)
            await engine.dispose()

    _run(check)


def test_an_offer_whose_sms_never_left_does_not_consume_her_turn(app_role_url: str) -> None:
    """**D7, and the residual it accepts.** With no provider configured the row
    is left `pending` by `drain_due` (F16's rule, unchanged), so the bride was
    never told anything — expiring her would consume a window she never had. She
    goes back to `waiting`, the pending message is cancelled so a late adapter
    cannot send a text about a dead offer.

    **And step 3 of the SAME tick re-offers her**, which is what "the clock does
    not run on an unsent SMS" cashes out to: `waiting` is where the expiry puts
    her, not where she waits. `run()` is expire-then-issue in one transaction
    (D2), she is still FIFO-oldest, and her pair stops holding a live offer the
    moment the return commits — so she leaves this tick `offered` again on a
    fresh token with a fresh FULL window. Asserting she rests in `waiting` would
    be asserting a poll interval, and it is the WINDOW D7 protects.

    The loop this admits is one entry per window, not per tick, and it
    self-heals on the first tick after the adapter lands; expiring the whole
    queue unread is strictly worse."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    later = NOW + datetime.timedelta(seconds=WINDOW_SECONDS)

    async def check() -> None:
        try:
            type_id = await _seed(factory, tenant_id)
            entry_id = await _join(factory, tenant_id, type_id)
            assert (await _cascade(factory, NOW).run(tenant_id)).offered == 1
            first = await _message(factory, tenant_id, entry_id)

            result = await _cascade(factory, later).run(tenant_id)
            assert (result.expired, result.returned, result.offered) == (0, 1, 1), (
                "she did not expire, and the same tick put her back on offer"
            )

            # The dead offer is properly dead: its text is cancelled, so a late
            # adapter cannot send a link to a window that has closed.
            dead = await _message_by_id(factory, tenant_id, first.id)
            assert dead.status == ScheduledMessageStatus.CANCELLED.value
            assert dead.manage_token is None, "a cancelled row keeps no live token"

            entry = await _entry(factory, tenant_id, entry_id)
            assert entry.status == WaitlistEntryStatus.OFFERED.value
            assert entry.offer_starts_at == _at(9, 0)
            # A FULL window from this tick — the one that never left took none
            # of it with it.
            assert entry.offer_expires_at == later + datetime.timedelta(seconds=WINDOW_SECONDS)
            assert entry.offer_token_hash is not None

            reissued = await _message(factory, tenant_id, entry_id)
            assert reissued.id != first.id
            assert reissued.status == ScheduledMessageStatus.PENDING.value
            assert reissued.manage_token is not None
            assert reissued.manage_token != first.manage_token, (
                "a re-offer mints a new token — the dead one is not resent"
            )
        finally:
            await _purge(factory, tenant_id)
            await engine.dispose()

    _run(check)


def test_a_failed_offer_sms_is_answered_the_same_way_as_an_unsent_one(app_role_url: str) -> None:
    """The other failure shape `_deliver` produces — a configured provider that
    refused. Same answer as the unconfigured one, because the question D7 asks is
    "did it reach `sent`", not "which way did it fail": returned rather than
    expired, and re-offered on the same tick.

    One refusal, so `_MAX_OFFER_SEND_FAILURES` has no opinion yet — the test
    below is where the third one ends the loop."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    later = NOW + datetime.timedelta(seconds=WINDOW_SECONDS)

    async def check() -> None:
        try:
            type_id = await _seed(factory, tenant_id)
            entry_id = await _join(factory, tenant_id, type_id)
            assert (await _cascade(factory, NOW).run(tenant_id)).offered == 1
            message = await _message(factory, tenant_id, entry_id)
            await _mark(factory, tenant_id, message.id, status=ScheduledMessageStatus.FAILED.value)

            result = await _cascade(factory, later).run(tenant_id)
            assert (result.expired, result.returned, result.offered) == (0, 1, 1)
            entry = await _entry(factory, tenant_id, entry_id)
            assert entry.status == WaitlistEntryStatus.OFFERED.value
            assert entry.offer_expires_at == later + datetime.timedelta(seconds=WINDOW_SECONDS)
        finally:
            await _purge(factory, tenant_id)
            await engine.dispose()

    _run(check)


def test_an_entry_the_provider_keeps_refusing_stops_blocking_its_queue(
    app_role_url: str,
) -> None:
    """**D7's loop, bounded.** The two tests above cover the shape D7 reasoned
    about — a provider-wide outage, which self-heals on the first tick after the
    adapter lands. They do NOT cover a permanently unreachable RECIPIENT: a
    number that replied STOP fails every time, so offer -> failed -> waiting
    never terminates, and because `waiting_pairs` excludes a pair holding a live
    offer, every bride behind her in that (day, type) is frozen out for a full
    window on every cycle, forever, at one `logger.warning` per turn.

    After `_MAX_OFFER_SEND_FAILURES` refusals she lands in `expired` instead —
    off the active-unique predicate, free to rejoin — and the queue advances.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    later = NOW + datetime.timedelta(seconds=WINDOW_SECONDS)

    async def check() -> None:
        try:
            type_id = await _seed(factory, tenant_id)
            unreachable = await _join(factory, tenant_id, type_id)
            behind = await _join(factory, tenant_id, type_id)
            await _refused_offers(
                factory, tenant_id, unreachable, count=_MAX_OFFER_SEND_FAILURES - 1
            )

            assert (await _cascade(factory, NOW).run(tenant_id)).offered == 1
            assert (
                await _entry(factory, tenant_id, unreachable)
            ).status == WaitlistEntryStatus.OFFERED.value, "FIFO — she is still first in line"
            message = await _message(factory, tenant_id, unreachable)
            await _mark(factory, tenant_id, message.id, status=ScheduledMessageStatus.FAILED.value)

            result = await _cascade(factory, later).run(tenant_id)
            assert (result.expired, result.returned) == (1, 0), (
                "the third refusal ends the loop rather than restarting it"
            )
            assert (
                await _entry(factory, tenant_id, unreachable)
            ).status == WaitlistEntryStatus.EXPIRED.value

            # The point of the cap: the bride behind her gets the slot. This tick
            # or the next — the cap is what makes either possible.
            await _cascade(factory, later).run(tenant_id)
            assert (
                await _entry(factory, tenant_id, behind)
            ).status == WaitlistEntryStatus.OFFERED.value
        finally:
            await _purge(factory, tenant_id)
            await engine.dispose()

    _run(check)


def test_two_types_on_one_day_are_never_offered_the_same_instant(app_role_url: str) -> None:
    """**"No broadcast" (#13) is a claim about INSTANTS, not about pairs.**

    `waiting_pairs` de-duplicates on (day, appointment_type_id) and its NOT
    EXISTS only excludes a pair already holding an offer — but `day_slots` is
    type-AGNOSTIC, one grid per day for every type. Two pairs on one day
    therefore walk the same grid, and without the held-instant read both take the
    earliest free slot and text two brides about one seat. Whoever claims second
    gets «התור הזה נתפס בינתיים», and per D4/F-O2 her entry stays `offered` for
    the full window, so her queue does not advance either.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()

    async def check() -> None:
        try:
            first_type = await _seed(factory, tenant_id)
            second_type = await _second_type(factory, tenant_id)
            rotem = await _join(factory, tenant_id, first_type)
            noa = await _join(factory, tenant_id, second_type)

            assert (await _cascade(factory, NOW).run(tenant_id)).offered == 2
            assert {
                (await _entry(factory, tenant_id, rotem)).offer_starts_at,
                (await _entry(factory, tenant_id, noa)).offer_starts_at,
            } == {_at(9, 0), _at(9, 30)}, "one seat, one offer — the second pair walks on"
        finally:
            await _purge(factory, tenant_id)
            await engine.dispose()

    _run(check)


def test_a_two_seat_instant_carries_two_offers(app_role_url: str) -> None:
    """The other half of the same read: held instants are COUNTED against
    `Slot.remaining`, not skipped outright. Two seats at 09:00 are two seats, and
    blanket-skipping would silently halve a boutique's throughput."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()

    async def check() -> None:
        try:
            first_type = await _seed(factory, tenant_id, capacity=2)
            second_type = await _second_type(factory, tenant_id)
            rotem = await _join(factory, tenant_id, first_type)
            noa = await _join(factory, tenant_id, second_type)

            assert (await _cascade(factory, NOW).run(tenant_id)).offered == 2
            assert (await _entry(factory, tenant_id, rotem)).offer_starts_at == _at(9, 0)
            assert (await _entry(factory, tenant_id, noa)).offer_starts_at == _at(9, 0)
        finally:
            await _purge(factory, tenant_id)
            await engine.dispose()

    _run(check)


def test_expiry_runs_inside_quiet_hours(app_role_url: str) -> None:
    """**The asymmetry D2.1 exists for.** An offer must be able to die at night —
    otherwise a slot nobody claimed stays locked behind a dead offer until 08:00
    and is not even directly bookable. So the quiet gate returns AFTER the expiry
    step, never before it."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    # Issued at 12:00 local; the sweep runs at 22:00 local, deep inside the block.
    quiet_later = NOW + datetime.timedelta(hours=10)

    async def check() -> None:
        try:
            type_id = await _seed(factory, tenant_id)
            entry_id = await _join(factory, tenant_id, type_id)
            assert (await _cascade(factory, NOW).run(tenant_id)).offered == 1
            message = await _message(factory, tenant_id, entry_id)
            await _mark(factory, tenant_id, message.id, status=ScheduledMessageStatus.SENT.value)

            result = await _cascade(factory, quiet_later).run(tenant_id)
            assert result.expired == 1
            assert result.offered == 0, "expiry at all hours; issuing, never in the block"
            assert (
                await _entry(factory, tenant_id, entry_id)
            ).status == WaitlistEntryStatus.EXPIRED.value
        finally:
            await _purge(factory, tenant_id)
            await engine.dispose()

    _run(check)


def test_a_tenant_with_no_waiting_entries_is_a_no_op(app_role_url: str) -> None:
    """The steady state. Every boutique is cascaded on every 60-second tick and
    almost all of them have nothing to do — so the empty tick must cost one
    bounded SELECT and produce no rows, no log line and no error."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()

    async def check() -> None:
        try:
            await _seed(factory, tenant_id)
            assert await _cascade(factory, NOW).run(tenant_id) == CascadeResult()
        finally:
            await _purge(factory, tenant_id)
            await engine.dispose()

    _run(check)


def test_offers_never_reach_into_a_past_day(app_role_url: str) -> None:
    """`waiting_pairs(from_day=today_jerusalem)`. An entry for a day that has
    already gone is dead weight the retention purge owns; offering against it
    would materialize a grid for a date the engine refuses anyway."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    # NOW is 2026-08-01 local; the entry's day is weeks BEFORE it.
    past = datetime.date(2026, 7, 5)

    async def check() -> None:
        try:
            type_id = await _seed(factory, tenant_id)
            entry_id = await _join(factory, tenant_id, type_id, day=past)

            assert (await _cascade(factory, NOW).run(tenant_id)).offered == 0
            assert (
                await _entry(factory, tenant_id, entry_id)
            ).status == WaitlistEntryStatus.WAITING.value
        finally:
            await _purge(factory, tenant_id)
            await engine.dispose()

    _run(check)


def test_a_pair_past_the_batch_is_reached_on_a_later_tick(
    app_role_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**The cap must bound the WORK, never which brides exist.**

    `waiting_pairs` is `ORDER BY day, type LIMIT N`, and the cap's original
    defence was that a LIMIT rotates on its own because an offered pair drops out
    of the `NOT EXISTS`. That is only true of a pair that PRODUCES an offer. A
    pair whose day has no free slot past the lead produces nothing and stays a
    candidate forever — and a full day is the normal state of a waitlist, which
    is why those brides joined it. So a deterministic first-N walk re-reads the
    same full days on every tick and never reads pair N+1: a cancellation behind
    the horizon is missed indefinitely, and silently, because `_issue` logs
    nothing when it offers nothing.

    The batch size is patched down rather than seeding fifty-one appointment
    types: the starvation is a property of the walk, not of the number 50.

    ⚠ ONE cascade instance across both ticks — the worker builds it once in
    `main()` and reuses it, and the resume cursor lives there.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    # Sorts BEFORE the seeded day and has no rule for its weekday, so it is a
    # standing candidate that can never yield an offer — `test_a_closed_day_
    # offers_nothing`'s shape, used here as the blocker.
    closed = TARGET_DATE - datetime.timedelta(days=1)
    monkeypatch.setattr("app.db.repositories.waitlist_entries.ISSUE_BATCH_SIZE", 1)

    async def check() -> None:
        try:
            type_id = await _seed(factory, tenant_id)
            blocked = await _join(factory, tenant_id, type_id, day=closed)
            behind = await _join(factory, tenant_id, type_id, day=TARGET_DATE)

            cascade = _cascade(factory, NOW)
            # Tick one reads the closed day and offers nothing at all.
            assert (await cascade.run(tenant_id)).offered == 0
            assert (
                await _entry(factory, tenant_id, blocked)
            ).status == WaitlistEntryStatus.WAITING.value

            # Tick two must move PAST it. On a first-N walk it reads the same
            # closed day again and this entry waits out the whole cancellation.
            assert (await cascade.run(tenant_id)).offered == 1
            assert (
                await _entry(factory, tenant_id, behind)
            ).status == WaitlistEntryStatus.OFFERED.value

            # And the walk wraps: running off the end clears the cursor, so the
            # blocked pair is a candidate again rather than skipped forever.
            assert (await cascade.run(tenant_id)).offered == 0
            assert cascade._issue_cursor.get(tenant_id) is None
        finally:
            await _purge(factory, tenant_id)
            await engine.dispose()

    _run(check)


def test_a_closed_day_offers_nothing(app_role_url: str) -> None:
    """No rule for that weekday means no grid, so nothing to offer — the
    cascade's silence covers "the boutique is shut" as well as "the day is
    full", because both reach it as an empty slot list.

    Capacity exhaustion is deliberately NOT re-asserted here: `materialize_slots`
    DROPS a full slot rather than marking it, so "the earliest materialized slot"
    already means "free", and race 1 is where a contested seat is proved."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    # The rule is seeded for TARGET_DATE's weekday; the entry asks for the day
    # after, which has none.
    closed = TARGET_DATE + datetime.timedelta(days=1)

    async def check() -> None:
        try:
            type_id = await _seed(factory, tenant_id)
            entry_id = await _join(factory, tenant_id, type_id, day=closed)

            assert (await _cascade(factory, NOW).run(tenant_id)).offered == 0
            assert (
                await _entry(factory, tenant_id, entry_id)
            ).status == WaitlistEntryStatus.WAITING.value
        finally:
            await _purge(factory, tenant_id)
            await engine.dispose()

    _run(check)
