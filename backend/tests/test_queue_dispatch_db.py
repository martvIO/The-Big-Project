"""F58's forced interleaves, against real Postgres as the non-owner app role.

`test_floor_service.py` proves take-next's BRANCHES with fakes. This module
proves the four mechanisms the branches sit on, none of which a fake can produce:
a row lock and its EvalPlanQual re-check, `SKIP LOCKED`'s refusal to wait, a real
`IntegrityError` out of a partial unique index, and — the one this feature is
actually about — a Postgres transaction that ROLLS BACK on a propagating
exception and COMMITS on a return.

⚠ **THE HARNESS'S FOUR HARD RULES.** Three are `test_floor_rooms_db.py`'s,
verbatim; the fourth is F58's own.

1. **Every row this module COMMITS holds `owner` or `shift_manager`, never a
   floor role.** `migrated_db` is session-scoped, pytest collects alphabetically,
   and `test_migrations.py::test_adding_the_role_check_validates_existing_rows`
   re-adds 0011's two-value CHECK over whatever rows exist. A committed
   `reception` row reddens a test that has nothing to do with dispatch. Nothing
   here asserts anything about a role.
2. **Every test mints its own tenant id; nothing truncates.**
3. **`asyncio.gather` is never used for a deterministic branch.** The default
   shape is F36's shipped one: open a read-only snapshot `tenant_session` and
   assert the contested resource reads FREE — which is what makes the gap
   *observable* rather than assumed — commit the winner in a NESTED
   `tenant_session`, then call the service. No tasks, no `Event`, no hang.
   `asyncio.Event` + `HOLD_SECONDS` is reserved for a statement that must
   genuinely BLOCK on uncommitted work, which here is THREE tests and no others:
   the `SKIP LOCKED` timing one, the headline lost-room one, and A15's concurrent
   first skip.
4. **⚠ F58's OWN: every waiting ticket in an ordering test is inserted in its own
   `tenant_session`.** `0018_queue_tickets.py` gives `created_at` a
   `DEFAULT now()`, and Postgres's `now()` is TRANSACTION-START, so tickets
   batched into one transaction share a sort key to the microsecond: the list
   collapses onto the `, id` tiebreak (random UUID order, so "arrival order"
   asserts nothing) and `position()` answers 1 for all of them. Batching the
   seeds for speed produces a red whose most tempting fix is to weaken the
   assertion, which makes it vacuous.
"""

import asyncio
import time
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.auth.service import StaffContext
from app.db.repositories.fitting_room_assignments import FittingRoomAssignmentsRepository
from app.db.repositories.fitting_rooms import FittingRoomsRepository
from app.db.repositories.queue_tickets import QueueTicketsRepository
from app.db.repositories.staff_users import StaffUsersRepository
from app.db.tenant import tenant_session
from app.floor.schemas import Waitlist
from app.floor.service import FloorService
from app.floor.validation import (
    QueueEmptyError,
    QueueTicketChangedError,
    QueueTicketNotWaitingError,
    RoomOccupiedError,
    StaffOccupiedError,
)
from app.models.audit_log import AuditLog
from app.models.booking import Booking
from app.models.constants import (
    AuditAction,
    BookingStatus,
    QueueTicketStatus,
    StaffRole,
    VisitType,
)
from app.models.customer import Customer
from app.models.fitting_room_assignment import FittingRoomAssignment
from app.models.queue_ticket import QueueTicket
from app.queue.validation import QueueTicketNotFoundError

pytestmark = pytest.mark.db

# 09:12Z on 2026-08-03 is 12:12 Asia/Jerusalem — the same calendar day, which is
# what makes `_today()`'s Jerusalem binding assertable against a frozen clock.
NOW = datetime(2026, 8, 3, 9, 12, tzinfo=UTC)
TODAY = date(2026, 8, 3)

# How long the blocking test holds its transaction open. Long enough that the
# blocked statement is demonstrably issued first, short enough to cost little.
HOLD_SECONDS = 0.6
ISSUE_SECONDS = 0.05

ROOMS = FittingRoomsRepository()
ASSIGNMENTS = FittingRoomAssignmentsRepository()
TICKETS = QueueTicketsRepository()


def _factory(app_role_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    return (
        engine := create_async_engine(app_role_url, poolclass=NullPool),
        async_sessionmaker(engine, expire_on_commit=False),
    )


def _actor(tenant_id: uuid.UUID, staff_id: uuid.UUID) -> StaffContext:
    """Always OWNER — hard rule 1. Nothing here asserts anything about a role."""
    return StaffContext(
        id=staff_id,
        tenant_id=tenant_id,
        email="owner@bella.example",
        display_name="Owner",
        role=StaffRole.OWNER.value,
    )


def _service(factory: async_sessionmaker[AsyncSession]) -> FloorService:
    return FloorService(factory, clock=lambda: NOW)


async def _seed_staff(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, *, display_name: str = "Staff"
) -> uuid.UUID:
    async with tenant_session(factory, tenant_id) as session:
        staff = await StaffUsersRepository().insert(
            session,
            tenant_id=tenant_id,
            email=f"dispatch-{uuid.uuid4().hex[:10]}@bella.example",
            password_hash="not-a-real-hash",
            display_name=display_name,
            role=StaffRole.OWNER.value,
        )
        return staff.id


async def _seed_room(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    *,
    label: str = "חדר 1",
    sort_order: int = 0,
) -> uuid.UUID:
    async with tenant_session(factory, tenant_id) as session:
        room = await ROOMS.insert(session, tenant_id, label=label, sort_order=sort_order)
        return room.id


async def _seed_ticket(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    *,
    name: str,
    queue_day: date = TODAY,
) -> uuid.UUID:
    """⚠ ONE ticket per `tenant_session` — hard rule 4. Batching these shares one
    transaction-start `now()` across every row and destroys the sort key."""
    async with tenant_session(factory, tenant_id) as session:
        ticket = await TICKETS.insert(
            session,
            tenant_id=tenant_id,
            queue_day=queue_day,
            name=name,
            phone=f"+9725{uuid.uuid4().int % 10**8:08d}",
            visit_type=VisitType.BRIDE.value,
        )
        return ticket.id


async def _ticket(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, ticket_id: uuid.UUID
) -> QueueTicket:
    async with tenant_session(factory, tenant_id) as session:
        row = await TICKETS.by_id(session, tenant_id, ticket_id)
        assert row is not None
        return row


async def _position(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, ticket_id: uuid.UUID
) -> int | None:
    async with tenant_session(factory, tenant_id) as session:
        row = await TICKETS.by_id(session, tenant_id, ticket_id)
        assert row is not None
        return await TICKETS.position(session, tenant_id, row)


async def _dispatch_audit(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID
) -> list[AuditLog]:
    async with tenant_session(factory, tenant_id) as session:
        stmt = select(AuditLog).where(
            AuditLog.tenant_id == tenant_id,
            AuditLog.action == AuditAction.QUEUE_TICKET_DISPATCHED.value,
        )
        return list((await session.execute(stmt)).scalars().all())


async def _audit_rows(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, action: AuditAction
) -> list[AuditLog]:
    async with tenant_session(factory, tenant_id) as session:
        stmt = (
            select(AuditLog)
            .where(AuditLog.tenant_id == tenant_id, AuditLog.action == action.value)
            .order_by(AuditLog.created_at, AuditLog.id)
        )
        return list((await session.execute(stmt)).scalars().all())


async def _assignments_of(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID
) -> list[FittingRoomAssignment]:
    async with tenant_session(factory, tenant_id) as session:
        stmt = select(FittingRoomAssignment).where(
            FittingRoomAssignment.tenant_id == tenant_id,
            FittingRoomAssignment.released_at.is_(None),
            FittingRoomAssignment.deleted_at.is_(None),
        )
        return list((await session.execute(stmt)).scalars().all())


# --- the happy path, and the ordering it depends on ---------------------------


async def test_take_next_dispatches_the_earliest_waiting_customer(app_role_url: str) -> None:
    """The head of the queue by `COALESCE(requeued_at, created_at)`, moved to
    `in_service` and bound to the assignment in ONE transaction.

    The requeued third seed is what makes the ordering assertion about the
    COALESCE rather than about `created_at`: she arrived LAST and is stamped
    `requeued_at` EARLIEST, so a reader that sorted on `created_at` alone would
    leave her third and this test would still pass — which is why she is stamped
    earlier than everyone, so sorting on `created_at` puts the wrong woman in the
    room.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        room_id = await _seed_room(factory, tenant_id)
        staff_id = await _seed_staff(factory, tenant_id)
        first = await _seed_ticket(factory, tenant_id, name="נועה")
        second = await _seed_ticket(factory, tenant_id, name="מיכל")
        requeued = await _seed_ticket(factory, tenant_id, name="דנה")
        async with tenant_session(factory, tenant_id) as session:
            row = await TICKETS.by_id(session, tenant_id, requeued)
            assert row is not None
            row.requeued_at = NOW - timedelta(hours=1)

        read = await _service(factory).take_next(
            tenant_id, room_id, staff_user_id=None, actor=_actor(tenant_id, staff_id)
        )

        assert read.room.row.room_id == room_id
        # The queue the dispatch left behind rides the same answer: the two women
        # still waiting, and never the one now in the room.
        assert [entry.name for entry in read.waitlist.entries] == ["נועה", "מיכל"]
        assert (await _ticket(factory, tenant_id, requeued)).status == (
            QueueTicketStatus.IN_SERVICE.value
        )
        assert (await _ticket(factory, tenant_id, first)).status == QueueTicketStatus.WAITING.value
        assert (await _ticket(factory, tenant_id, second)).status == QueueTicketStatus.WAITING.value

        rows = await _assignments_of(factory, tenant_id)
        assert [(row.queue_ticket_id, row.booking_id) for row in rows] == [(requeued, None)]

        audit = await _dispatch_audit(factory, tenant_id)
        assert [row.details["mode"] for row in audit] == ["take_next"]
        assert "דנה" not in str([row.details for row in audit])
    finally:
        await engine.dispose()


async def test_yesterdays_unclosed_ticket_is_not_claimable_today(app_role_url: str) -> None:
    """`queue_day` is bound to TODAY on this path, so a ticket nobody closed
    overnight — the normal state of things until F20's sweep — is invisible to
    take-next rather than being served first thing in the morning."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        room_id = await _seed_room(factory, tenant_id)
        staff_id = await _seed_staff(factory, tenant_id)
        ghost = await _seed_ticket(
            factory, tenant_id, name="אתמול", queue_day=TODAY - timedelta(days=1)
        )

        with pytest.raises(QueueEmptyError):
            await _service(factory).take_next(
                tenant_id, room_id, staff_user_id=None, actor=_actor(tenant_id, staff_id)
            )

        assert (await _ticket(factory, tenant_id, ghost)).status == QueueTicketStatus.WAITING.value
        assert await _assignments_of(factory, tenant_id) == []
        assert await _dispatch_audit(factory, tenant_id) == []
    finally:
        await engine.dispose()


async def test_two_take_nexts_get_two_different_customers(app_role_url: str) -> None:
    """⚠ THE ROW LOCK PLUS THE `status` QUAL, not `SKIP LOCKED`.

    Two rooms, two staffers, one queue: each take-next must come away with a
    different woman. Serialised here rather than raced, because the mechanism is
    not timing — the subquery's `FOR UPDATE` holds the row for the whole
    transaction and the outer/inner `status = 'waiting'` is what makes the same
    woman unreachable twice.

    ⚠ MUTATION PERFORMED: drop `QueueTicket.status == WAITING` from
    `_live_waiting`'s use in the SUBQUERY (i.e. re-spell the predicates inline
    without it) → the second take-next re-selects the first woman and both
    assignments carry one ticket id.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        first_room = await _seed_room(factory, tenant_id, label="חדר 1", sort_order=0)
        second_room = await _seed_room(factory, tenant_id, label="חדר 2", sort_order=1)
        one = await _seed_staff(factory, tenant_id, display_name="נועה")
        two = await _seed_staff(factory, tenant_id, display_name="דנה")
        head = await _seed_ticket(factory, tenant_id, name="ראשונה")
        next_up = await _seed_ticket(factory, tenant_id, name="שנייה")
        service = _service(factory)

        await service.take_next(
            tenant_id, first_room, staff_user_id=one, actor=_actor(tenant_id, one)
        )
        await service.take_next(
            tenant_id, second_room, staff_user_id=two, actor=_actor(tenant_id, two)
        )

        rows = await _assignments_of(factory, tenant_id)
        assert sorted(str(row.queue_ticket_id) for row in rows) == sorted([str(head), str(next_up)])
    finally:
        await engine.dispose()


async def test_a_take_next_does_not_wait_behind_a_locked_ticket(app_role_url: str) -> None:
    """⚠ `SKIP LOCKED`'s ONLY WITNESS, and the assertion that carries it is the
    ELAPSED TIME rather than the exception.

    Exactly one waiting ticket. A locks its row and holds the transaction open;
    B's take-next must answer `QUEUE_EMPTY` PROMPTLY. Without `skip_locked=True`
    B blocks for the whole hold and then *still* answers `QUEUE_EMPTY` — the
    exception assertion alone is blind to the mechanism, which is exactly why the
    timing bound cannot be dropped.

    The lock is taken by CALL and SKIP too, so this is not a take-next-vs-
    take-next concern: an ordinary «call Noa forward» on one tablet would
    otherwise stall a dispatch on another.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        room_id = await _seed_room(factory, tenant_id)
        staff_id = await _seed_staff(factory, tenant_id)
        await _seed_ticket(factory, tenant_id, name="היחידה")
        locked = asyncio.Event()

        async def _hold() -> None:
            async with tenant_session(factory, tenant_id) as session:
                await session.execute(
                    select(QueueTicket.id)
                    .where(QueueTicket.tenant_id == tenant_id)
                    .with_for_update()
                )
                locked.set()
                await asyncio.sleep(HOLD_SECONDS)

        holder = asyncio.create_task(_hold())
        await locked.wait()
        await asyncio.sleep(ISSUE_SECONDS)
        started = time.monotonic()
        with pytest.raises(QueueEmptyError):
            await _service(factory).take_next(
                tenant_id, room_id, staff_user_id=None, actor=_actor(tenant_id, staff_id)
            )
        elapsed = time.monotonic() - started
        await holder

        assert elapsed < HOLD_SECONDS / 2, (
            f"take-next waited {elapsed:.3f}s behind a locked ticket — `skip_locked=True` is gone "
            "from claim_next's subquery, and the QUEUE_EMPTY it still answers hides it"
        )
        assert await _assignments_of(factory, tenant_id) == []
    finally:
        await engine.dispose()


# --- THE HEADLINE: a lost race must not strand a customer ---------------------


async def test_a_take_next_that_loses_the_room_leaves_the_ticket_waiting(
    app_role_url: str,
) -> None:
    """⚠⚠ **THE FEATURE'S HEADLINE TEST — F33's deployment gate is discharged on
    this one.**

    ⚠ **THE WINNER MUST STILL BE UNCOMMITTED WHEN STEP 2b READS**, and that is
    why this is one of only two tests in the feature allowed an `Event` and a
    hold. Every shape in which the winner commits FIRST is refused by step 2b
    before the INSERT is ever attempted — F36's shipped snapshot-then-nested-
    commit idiom included, because F36's claim has no 2b and take-next does. Run
    that way, this test exercises no `IntegrityError` at all and its headline
    mutation comes back green: verified, which is how this shape was arrived at.

    So: the winner holds an UNCOMMITTED assignment on the room. The loser's 2b
    reads the room FREE — truthfully, at READ COMMITTED — claims the head of the
    queue, and its INSERT then BLOCKS on the winner's uncommitted index key. The
    winner commits; the loser gets the unique violation. This is the
    genuinely-uncommitted-winner window 2b cannot see and does not claim to, and
    the partial unique index plus this rollback are its only correctness
    mechanism.

    **The winner and the loser's target are THE SAME STAFFER** — the stale-tile
    double-tap, an everyday event on a panel rendering a payload up to one tick
    old. That makes the conflict violate BOTH partial unique indexes at once,
    which is exactly the shape F36's `_resolve_claim_conflict` resolves with a
    RETURN, and exactly the shape that must not be resolved that way here.

    Four assertions, each naming a different way this can go wrong:
      1. she is refused at all, and the 409 names the occupant;
      2. **the ticket is still `waiting`** — not `in_service` with no room;
      3. she is still at position 1, because `requeued_at` was never touched;
      4. no audit row claims a dispatch that did not happen.

    ⚠ **MUTATIONS RUN, AND THE SPEC'S FIRST-DRAFT ONE IS VACUOUS.**

      * `begin_nested()` around the INSERT with the `try` moved inside — i.e.
        copy `FloorService.claim` verbatim — **GREEN, all eight cases.**
        `db/tenant.py:25` is `session.begin()`, so a propagating exception rolls
        the transaction back with or without a savepoint. Recorded here rather
        than hidden: a mutation predicted to bite that does not.
      * **the one that strands: `begin_nested()` PLUS F36's idempotence RETURN
        (`active_for` hit → `return await self._room_read(...)`) inside the
        `async with`, with step 2b deleted** — the faithful copy of the shipped
        resolver, which is what a builder told "one helper shared by take-next
        and push-assign" actually writes. The savepoint keeps the transaction
        usable, `active_for` finds the winner's now-committed row, the RETURN
        commits, and take-next answers **200 about a dispatch that claimed
        nobody**: assertions 1, 2, 3 and 4 all red, with the ticket left
        `in_service` and no assignment carrying it. Recovery needs psql.
      * the idempotence RETURN **without** the savepoint — the aborted
        transaction makes `active_for` itself raise, so the failure is a 500
        rather than a stranding. Red too, and for the lesser reason.
      * moving the ticket claim into its own `tenant_session` that commits before
        the INSERT → assertions 2 and 3 red.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        room_id = await _seed_room(factory, tenant_id)
        staff_id = await _seed_staff(factory, tenant_id, display_name="דנה")
        ticket_id = await _seed_ticket(factory, tenant_id, name="נועה בר")
        claimed = asyncio.Event()

        async def _uncommitted_winner() -> None:
            async with tenant_session(factory, tenant_id) as winner:
                await ASSIGNMENTS.claim(
                    winner, tenant_id, room_id=room_id, staff_id=staff_id, booking_id=None
                )
                claimed.set()
                # Still UNCOMMITTED for this long. Exiting the block is the
                # commit (`db/tenant.py:25`), which is what releases the loser's
                # blocked INSERT into its unique violation.
                await asyncio.sleep(HOLD_SECONDS)

        winner_task = asyncio.create_task(_uncommitted_winner())
        await claimed.wait()
        await asyncio.sleep(ISSUE_SECONDS)

        with pytest.raises(RoomOccupiedError) as refused:
            await _service(factory).take_next(
                tenant_id, room_id, staff_user_id=staff_id, actor=_actor(tenant_id, staff_id)
            )
        await winner_task

        assert refused.value.details == {"staff_display_name": "דנה"}
        ticket = await _ticket(factory, tenant_id, ticket_id)
        assert ticket.status == QueueTicketStatus.WAITING.value
        assert ticket.requeued_at is None
        assert await _position(factory, tenant_id, ticket_id) == 1
        assert await _dispatch_audit(factory, tenant_id) == []
        # …and the winner's row is the only one, carrying no ticket.
        rows = await _assignments_of(factory, tenant_id)
        assert [row.queue_ticket_id for row in rows] == [None]
    finally:
        await engine.dispose()


async def test_a_take_next_into_a_room_the_caller_already_holds_is_refused(
    app_role_url: str,
) -> None:
    """⚠ A8b — the assertion that structurally forbids the idempotence branch
    from ever being added back, and step 2b's witness at the same time.

    The target staffer already holds this room, COMMITTED, so `RoomsPanel`
    rendering a one-tick-stale free tile is all it takes. F36's claim answers
    this case with a 200 and is right to — nothing changed. Take-next must NOT:
    a 200 here reports a dispatch while the head of the queue is either consumed
    or, with the idempotence branch present, stranded.

    ⚠ MUTATIONS RUN. Deleting step 2b ALONE leaves this GREEN: the committed
    occupant makes the INSERT fail immediately, `_occupied_error` names her, and
    the ticket rolls back either way — so what 2b buys is that no customer's
    ticket is claimed and discarded at all, and its only witness is the fast
    suite's `test_take_next_into_an_occupied_room_refuses_before_touching_the_queue`,
    which asserts `claim_next` is never called. Delete 2b AND give the INSERT
    F36's savepoint + idempotence RETURN and this reds with a **200**, the head
    of the queue left `in_service` with no assignment carrying it.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        room_id = await _seed_room(factory, tenant_id)
        staff_id = await _seed_staff(factory, tenant_id, display_name="דנה")
        ticket_id = await _seed_ticket(factory, tenant_id, name="נועה בר")
        async with tenant_session(factory, tenant_id) as session:
            await ASSIGNMENTS.claim(
                session, tenant_id, room_id=room_id, staff_id=staff_id, booking_id=None
            )

        with pytest.raises(RoomOccupiedError) as refused:
            await _service(factory).take_next(
                tenant_id, room_id, staff_user_id=staff_id, actor=_actor(tenant_id, staff_id)
            )

        assert refused.value.details == {"staff_display_name": "דנה"}
        ticket = await _ticket(factory, tenant_id, ticket_id)
        assert ticket.status == QueueTicketStatus.WAITING.value
        assert ticket.requeued_at is None
        assert await _position(factory, tenant_id, ticket_id) == 1
        assert await _dispatch_audit(factory, tenant_id) == []
    finally:
        await engine.dispose()


async def test_a_take_next_refused_by_the_STAFF_index_also_leaves_the_ticket_waiting(
    app_role_url: str,
) -> None:
    """The other index, and it reaches `_occupied_error`'s SECOND branch — the
    room is free, so `occupant_of_room` answers None and `room_of_staff` names
    the room she is actually in. Step 2b cannot refuse this one: the contested
    room is empty and the conflict is about the STAFFER.

    ⚠ This is the case that proves `_occupied_error` needs its own
    `tenant_session`. MUTATION PERFORMED: reuse the aborted session instead →
    `PendingRollbackError`, i.e. a 500 in place of the 409 the staffer needs.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        held = await _seed_room(factory, tenant_id, label="חדר 1", sort_order=0)
        free = await _seed_room(factory, tenant_id, label="חדר 2", sort_order=1)
        staff_id = await _seed_staff(factory, tenant_id, display_name="דנה")
        ticket_id = await _seed_ticket(factory, tenant_id, name="נועה בר")
        async with tenant_session(factory, tenant_id) as session:
            await ASSIGNMENTS.claim(
                session, tenant_id, room_id=held, staff_id=staff_id, booking_id=None
            )

        with pytest.raises(StaffOccupiedError) as refused:
            await _service(factory).take_next(
                tenant_id, free, staff_user_id=staff_id, actor=_actor(tenant_id, staff_id)
            )

        assert refused.value.details == {"room_label": "חדר 1"}
        assert (await _ticket(factory, tenant_id, ticket_id)).status == (
            QueueTicketStatus.WAITING.value
        )
        assert await _position(factory, tenant_id, ticket_id) == 1
        assert await _dispatch_audit(factory, tenant_id) == []
    finally:
        await engine.dispose()


async def test_tenant_b_take_next_cannot_reach_tenant_a_s_queue(app_role_url: str) -> None:
    """Take-next's day-and-tenant scoping, probed as the APP ROLE.

    ⚠ **VACUITY MUTATION RUN, AND IT CAME BACK GREEN**, so this test is recorded
    for what it actually measures rather than for what the fixture suggests:
    swapping `app_role_url` for `migrated_db` — whose container superuser
    bypasses RLS entirely — leaves it passing. What it therefore proves is
    `claim_next`'s EXPLICIT `tenant_id` predicate (the "redundant
    defence-in-depth" the repository docstrings claim, which is not redundant at
    all if RLS is ever mis-bound), not RLS. RLS on these two tables is F33's
    `test_queue_isolation.py` and F36's `test_fitting_rooms_isolation.py`, and
    the full five-verb cross-tenant probe is Task 8's row.
    """
    engine, factory = _factory(app_role_url)
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    try:
        ticket_id = await _seed_ticket(factory, tenant_a, name="של א")
        room_b = await _seed_room(factory, tenant_b)
        staff_b = await _seed_staff(factory, tenant_b)

        with pytest.raises(QueueEmptyError):
            await _service(factory).take_next(
                tenant_b, room_b, staff_user_id=None, actor=_actor(tenant_b, staff_b)
            )

        assert (await _ticket(factory, tenant_a, ticket_id)).status == (
            QueueTicketStatus.WAITING.value
        )
        assert await _assignments_of(factory, tenant_b) == []
    finally:
        await engine.dispose()


# --- push-assign: the conditional UPDATE is the serialisation point (D4) ------


async def test_two_distinct_staffers_push_assigning_one_ticket_to_two_rooms_make_one_assignment(
    app_role_url: str,
) -> None:
    """A10, and ⚠ **BOTH "distinct"s in the name are load-bearing.**

    Same room and F36's room index blocks the second; same staffer and the staff
    index does — either way the mutation below goes green and the shipped indexes
    pass this test for the wrong reason. TWO rooms and TWO staffers leave
    `AND status = 'waiting'` in the conditional UPDATE as the ONLY thing standing
    between one woman and two fitting rooms.

    ⚠ MUTATION: drop that conjunct from `claim_by_id` → both succeed and two
    assignments carry one ticket.

    The winner is committed before the loser is called — the shipped
    snapshot-then-nested-commit shape — because the mechanism here is the
    conditional UPDATE's own predicate and not a blocked INSERT.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        first_room = await _seed_room(factory, tenant_id, label="חדר 1", sort_order=0)
        second_room = await _seed_room(factory, tenant_id, label="חדר 2", sort_order=1)
        first_staff = await _seed_staff(factory, tenant_id, display_name="דנה")
        second_staff = await _seed_staff(factory, tenant_id, display_name="רות")
        ticket_id = await _seed_ticket(factory, tenant_id, name="נועה בר")

        await _service(factory).assign(
            tenant_id,
            first_room,
            queue_ticket_id=ticket_id,
            staff_user_id=first_staff,
            actor=_actor(tenant_id, first_staff),
        )
        with pytest.raises(QueueTicketNotWaitingError) as refused:
            await _service(factory).assign(
                tenant_id,
                second_room,
                queue_ticket_id=ticket_id,
                staff_user_id=second_staff,
                actor=_actor(tenant_id, second_staff),
            )

        assert refused.value.details == {"status": QueueTicketStatus.IN_SERVICE.value}
        rows = await _assignments_of(factory, tenant_id)
        assert [row.queue_ticket_id for row in rows] == [ticket_id]
        assert [row.details["mode"] for row in await _dispatch_audit(factory, tenant_id)] == [
            "assign"
        ]
    finally:
        await engine.dispose()


async def test_a_push_assign_of_a_ticket_that_is_gone_is_a_404_and_writes_nothing(
    app_role_url: str,
) -> None:
    """A9's second half. A foreign-tenant id and an absent one are the SAME
    answer — RLS plus the explicit predicate make them indistinguishable, and a
    403 would confirm that a guessed ticket exists."""
    engine, factory = _factory(app_role_url)
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    try:
        room_id = await _seed_room(factory, tenant_b)
        staff_id = await _seed_staff(factory, tenant_b)
        theirs = await _seed_ticket(factory, tenant_a, name="של א")

        for probe in (theirs, uuid.uuid4()):
            with pytest.raises(QueueTicketNotFoundError):
                await _service(factory).assign(
                    tenant_b,
                    room_id,
                    queue_ticket_id=probe,
                    staff_user_id=None,
                    actor=_actor(tenant_b, staff_id),
                )

        assert (await _ticket(factory, tenant_a, theirs)).status == QueueTicketStatus.WAITING.value
        assert await _assignments_of(factory, tenant_b) == []
    finally:
        await engine.dispose()


# --- skip: the conjunct that stops two single taps removing a customer (D6) ---


async def test_a_concurrent_second_first_skip_is_refused_rather_than_removing_her(
    app_role_url: str,
) -> None:
    """⚠⚠ **A15 — THE THIRD BLOCKER THE SPEC REVIEW FOUND, AND THE ONLY TEST THAT
    CAN SEE IT.**

    Two managers on two tablets see the same no-show at `skip_count == 0` and
    both tap «דלגי». Neither client rendered the confirm, because the confirm is
    gated on `skip_count >= 1` and both read 0 from the same tick.

    A takes the row lock and writes `skip_count = 1`, `status = 'waiting'`.
    B blocks. On A's commit, READ COMMITTED's EvalPlanQual re-evaluates B's
    predicate against the NEW tuple — and `status = 'waiting'` STILL HOLDS. With
    `AND skip_count = :seen_skip_count` B matches nothing and is refused. Without
    it B proceeds, its SET expressions read the new row (1 → 2), the `CASE` fires
    `'removed'`, and **she is out of the queue irreversibly, by two ordinary
    single taps, with the confirm bypassed on both devices.**

    ⚠ **This is one of only three tests in the feature allowed an `Event` and a
    hold** (hard rule 3), because B's statement must genuinely BLOCK on
    uncommitted work — every shape where A commits first is a different race.

    ⚠ MUTATION RUN: drop `AND skip_count = :seen_skip_count` from
    `QueueTicketsRepository.skip` → no exception is raised at all, `status` is
    `removed`, `skip_count` is 2, and TWO audit rows say so.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        staff_id = await _seed_staff(factory, tenant_id)
        ticket_id = await _seed_ticket(factory, tenant_id, name="נועה בר")
        skipped = asyncio.Event()

        async def _uncommitted_first_skip() -> None:
            async with tenant_session(factory, tenant_id) as session:
                await TICKETS.skip(session, tenant_id, ticket_id, now=NOW, seen_skip_count=0)
                skipped.set()
                await asyncio.sleep(HOLD_SECONDS)

        winner = asyncio.create_task(_uncommitted_first_skip())
        await skipped.wait()
        await asyncio.sleep(ISSUE_SECONDS)

        with pytest.raises(QueueTicketChangedError) as refused:
            await _service(factory).skip(
                tenant_id, ticket_id, seen_skip_count=0, actor=_actor(tenant_id, staff_id)
            )
        await winner

        assert refused.value.details == {"skip_count": "1"}
        ticket = await _ticket(factory, tenant_id, ticket_id)
        assert ticket.status == QueueTicketStatus.WAITING.value
        assert ticket.skip_count == 1
        assert await _position(factory, tenant_id, ticket_id) == 1
        assert await _audit_rows(factory, tenant_id, AuditAction.QUEUE_TICKET_SKIPPED) == []
    finally:
        await engine.dispose()


async def test_two_deliberate_skips_leave_her_removed_with_the_count_at_two(
    app_role_url: str,
) -> None:
    """A15b, and it is SERIAL rather than interleaved — which is a finding.

    The plan asks for a forced interleave whose mutation is "replace the atomic
    `skip_count + 1` with a Python read-modify-write and the lost update lands".
    **`AND skip_count = :seen_skip_count` makes that window unreachable**: two
    concurrent skips necessarily send the same seen count, so one of them is
    refused before either can lose an update. The atomic increment is now
    redundancy BEHIND the conjunct rather than the primary guard, and the shape
    that can still assert it is the deliberate pair — each press sending the
    count its own tick rendered.

    The second press is the destructive one, which is why the client gates a
    confirm on `skip_count >= 1` and why the audit row carries the resulting
    status: a removal-by-second-skip is legible in the trail without a fifth
    action value.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        staff_id = await _seed_staff(factory, tenant_id)
        ticket_id = await _seed_ticket(factory, tenant_id, name="נועה בר")

        await _service(factory).skip(
            tenant_id, ticket_id, seen_skip_count=0, actor=_actor(tenant_id, staff_id)
        )
        await _service(factory).skip(
            tenant_id, ticket_id, seen_skip_count=1, actor=_actor(tenant_id, staff_id)
        )

        ticket = await _ticket(factory, tenant_id, ticket_id)
        assert ticket.skip_count == 2
        assert ticket.status == QueueTicketStatus.REMOVED.value
        rows = await _audit_rows(factory, tenant_id, AuditAction.QUEUE_TICKET_SKIPPED)
        assert [(row.details["skip_count"], row.details["status"]) for row in rows] == [
            (1, QueueTicketStatus.WAITING.value),
            (2, QueueTicketStatus.REMOVED.value),
        ]
    finally:
        await engine.dispose()


async def test_a_skip_clears_the_call_and_moves_her_behind_the_woman_who_was_second(
    app_role_url: str,
) -> None:
    """A13. The requeue is one column and the clock re-ranks the list — F33
    shipped `COALESCE(requeued_at, created_at)` before anything wrote the column
    precisely so this could not change a published read's semantics.

    ⚠ `called_at = NULL` is the half a reader is most likely to think
    decorative. She was called and did not come; leaving the stamp would
    highlight her on F59's public wall board at the BACK of the queue and leave
    her own page reading «אפשר לגשת לדלפק» indefinitely.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        staff_id = await _seed_staff(factory, tenant_id)
        first = await _seed_ticket(factory, tenant_id, name="נועה")
        second = await _seed_ticket(factory, tenant_id, name="מיכל")
        # ⚠ Both arrivals are pushed BEFORE the frozen service clock. The seeds
        # take `created_at` from the DATABASE host's `now()`, which is the real
        # wall clock, so a requeue stamped with this suite's frozen `NOW` would
        # otherwise land EARLIER than the arrival it is meant to follow and the
        # skip would move her to the FRONT.
        async with tenant_session(factory, tenant_id) as session:
            for ticket_id, arrived in (
                (first, NOW - timedelta(hours=2)),
                (second, NOW - timedelta(hours=1)),
            ):
                row = await TICKETS.by_id(session, tenant_id, ticket_id)
                assert row is not None
                row.created_at = arrived

        await _service(factory).call(tenant_id, first, actor=_actor(tenant_id, staff_id))
        waitlist = await _service(factory).skip(
            tenant_id, first, seen_skip_count=0, actor=_actor(tenant_id, staff_id)
        )

        assert [entry.name for entry in waitlist.entries] == ["מיכל", "נועה"]
        assert [entry.called for entry in waitlist.entries] == [False, False]
        assert [entry.skip_count for entry in waitlist.entries] == [0, 1]
        assert await _position(factory, tenant_id, first) == 2
        assert await _position(factory, tenant_id, second) == 1
    finally:
        await engine.dispose()


async def test_a_call_leaves_her_waiting_and_a_second_call_keeps_the_first_stamp(
    app_role_url: str,
) -> None:
    """A16 + A17, end to end through the service.

    ⚠ **`status` IS NOT TOUCHED**, and F59 recorded this as the one contract it
    could not enforce for itself: its board's predicate is `status = 'waiting'`,
    so flipping the status at call time drops the called row off the wall board
    the instant it is called — the opposite of the feature.

    The re-call is a 200 with NO audit row: she wanted her called and she is
    called.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        staff_id = await _seed_staff(factory, tenant_id)
        ticket_id = await _seed_ticket(factory, tenant_id, name="נועה בר")

        await _service(factory).call(tenant_id, ticket_id, actor=_actor(tenant_id, staff_id))
        first_stamp = (await _ticket(factory, tenant_id, ticket_id)).called_at
        waitlist = await _service(factory).call(
            tenant_id, ticket_id, actor=_actor(tenant_id, staff_id)
        )

        ticket = await _ticket(factory, tenant_id, ticket_id)
        assert ticket.status == QueueTicketStatus.WAITING.value
        assert ticket.called_at == first_stamp == NOW
        assert [entry.called for entry in waitlist.entries] == [True]
        assert await _position(factory, tenant_id, ticket_id) == 1
        assert len(await _audit_rows(factory, tenant_id, AuditAction.QUEUE_TICKET_CALLED)) == 1
    finally:
        await engine.dispose()


async def test_a_removal_takes_her_off_the_panel_and_out_of_every_count(
    app_role_url: str,
) -> None:
    """A18's server half. `removed` is terminal, so she leaves the waitlist, the
    public board and `position()` in one write — and her own page reaches the
    closed terminal, which is the one consequence D8 states rather than argues
    away."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        staff_id = await _seed_staff(factory, tenant_id)
        first = await _seed_ticket(factory, tenant_id, name="נועה")
        second = await _seed_ticket(factory, tenant_id, name="מיכל")

        waitlist = await _service(factory).remove(
            tenant_id, first, actor=_actor(tenant_id, staff_id)
        )

        assert [entry.name for entry in waitlist.entries] == ["מיכל"]
        assert [entry.position for entry in Waitlist.from_read(waitlist).entries] == [1]
        assert (await _ticket(factory, tenant_id, first)).status == (
            QueueTicketStatus.REMOVED.value
        )
        assert await _position(factory, tenant_id, first) is None
        assert await _position(factory, tenant_id, second) == 1
    finally:
        await engine.dispose()


# --- the waitlist read, its order and D9's flag -------------------------------


async def test_the_waitlist_order_agrees_with_the_position_count(app_role_url: str) -> None:
    """⚠ A3, and the NOISE is what makes it an alarm rather than a decoration.

    The panel read and `position()` are the SAME `_live_waiting()` call and the
    SAME `_sort_key()`. Four rows neither may count are seeded alongside the
    three both must, every one of them EARLIER than the first real row — so a
    one-sided widening (a status filter dropped, `queue_day` forgotten,
    `deleted_at` forgotten) SHIFTS a position and this reds. F59's shipped note
    records that an all-waiting seed made its own version of this test blind.

    ⚠ **Every ticket in its own `tenant_session`** — hard rule 4. `now()` is
    transaction-start, so batched seeds tie to the microsecond and `position()`
    answers 1 for all of them.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        yesterday = await _seed_ticket(
            factory, tenant_id, name="אתמול", queue_day=TODAY - timedelta(days=1)
        )
        swept = await _seed_ticket(factory, tenant_id, name="נמחקה")
        served = await _seed_ticket(factory, tenant_id, name="בטיפול")
        finished = await _seed_ticket(factory, tenant_id, name="סיימה")
        async with tenant_session(factory, tenant_id) as session:
            for ticket_id, status, deleted in (
                (swept, QueueTicketStatus.WAITING.value, NOW),
                (served, QueueTicketStatus.IN_SERVICE.value, None),
                (finished, QueueTicketStatus.DONE.value, None),
            ):
                row = await TICKETS.by_id(session, tenant_id, ticket_id)
                assert row is not None
                row.status = status
                row.deleted_at = deleted
        assert yesterday
        first = await _seed_ticket(factory, tenant_id, name="אלף")
        second = await _seed_ticket(factory, tenant_id, name="בית")
        third = await _seed_ticket(factory, tenant_id, name="גימל")

        async with tenant_session(factory, tenant_id) as session:
            waitlist = await _service(factory)._waitlist(session, tenant_id)

        assert [entry.name for entry in waitlist.entries] == ["אלף", "בית", "גימל"]
        assert [entry.position for entry in Waitlist.from_read(waitlist).entries] == [1, 2, 3]
        for index, ticket_id in enumerate((first, second, third)):
            assert await _position(factory, tenant_id, ticket_id) == index + 1
    finally:
        await engine.dispose()


async def test_the_waitlist_and_position_disagree_on_a_deliberate_tie(app_role_url: str) -> None:
    """⚠ A3b — the documented residual, pinned as a FACT rather than left in
    prose.

    Two tickets seeded in ONE transaction share `created_at` to the microsecond
    (`now()` is transaction-start). The list is totally ordered by the `, id`
    tiebreak and renders 1 and 2; `position()` counts `sort_key < mine` and has
    no second key, so it answers the SAME number for both. `position()` is
    deliberately NOT edited — changing a shipped read's semantics to buy a
    cosmetic agreement is not a trade worth making.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        async with tenant_session(factory, tenant_id) as session:
            tied = [
                (
                    await TICKETS.insert(
                        session,
                        tenant_id=tenant_id,
                        queue_day=TODAY,
                        name=name,
                        phone=f"+9725{uuid.uuid4().int % 10**8:08d}",
                        visit_type=VisitType.BRIDE.value,
                    )
                ).id
                for name in ("אלף", "בית")
            ]

        async with tenant_session(factory, tenant_id) as session:
            waitlist = Waitlist.from_read(await _service(factory)._waitlist(session, tenant_id))

        assert [entry.position for entry in waitlist.entries] == [1, 2]
        assert {await _position(factory, tenant_id, ticket_id) for ticket_id in tied} == {1}
    finally:
        await engine.dispose()


async def test_the_duplicate_flag_is_keyed_on_the_phone_and_sees_an_in_service_twin(
    app_role_url: str,
) -> None:
    """A19, all three cases, against real SQL.

    ⚠ The middle one is the whole reason D9's SECOND statement exists: she
    re-scanned the QR, was dispatched on the first ticket, and the second is
    still waiting. That ghost is the most valuable thing on this panel to remove,
    and a flag blind to it leaves a manager with two «נועה»s and neither flagged,
    removing one by inference — with no undo.

    ⚠ MUTATIONS RUN: delete `in_service_phones` → the middle row renders
    un-flagged; group on `name` → the two «נועה בר»s with different numbers flag
    each other and the real pair stops flagging.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        room_id = await _seed_room(factory, tenant_id)
        staff_id = await _seed_staff(factory, tenant_id)
        shared = f"+9725{uuid.uuid4().int % 10**8:08d}"
        rescanned = f"+9725{uuid.uuid4().int % 10**8:08d}"

        async with tenant_session(factory, tenant_id) as session:
            twin = await TICKETS.insert(
                session,
                tenant_id=tenant_id,
                queue_day=TODAY,
                name="שרה",
                phone=rescanned,
                visit_type=VisitType.BRIDE.value,
            )
        assert twin
        # She is taken on the FIRST of her two tickets, so the second is the one
        # left waiting with a live twin already in a room.
        await _service(factory).take_next(
            tenant_id, room_id, staff_user_id=None, actor=_actor(tenant_id, staff_id)
        )
        for name, phone in (
            ("נועה בר", shared),
            ("מיכל", shared),
            ("שרה", rescanned),
            ("נועה בר", f"+9725{uuid.uuid4().int % 10**8:08d}"),
        ):
            async with tenant_session(factory, tenant_id) as session:
                await TICKETS.insert(
                    session,
                    tenant_id=tenant_id,
                    queue_day=TODAY,
                    name=name,
                    phone=phone,
                    visit_type=VisitType.BRIDE.value,
                )

        async with tenant_session(factory, tenant_id) as session:
            waitlist = await _service(factory)._waitlist(session, tenant_id)

        assert [(entry.name, entry.duplicate) for entry in waitlist.entries] == [
            ("נועה בר", True),
            ("מיכל", True),
            ("שרה", True),
            ("נועה בר", False),
        ]
    finally:
        await engine.dispose()


# --- FINISH: the release closes its ticket, in ONE transaction (D5) -----------


async def test_a_release_and_its_ticket_close_are_one_transaction(app_role_url: str) -> None:
    """⚠ A11, and the SECOND half is the one that matters.

    The first two assertions say the release closed the ticket. The rest inject a
    failure INSIDE the release — after the room is freed and the ticket is closed
    — and assert that BOTH writes are gone. That is what "one transaction" means
    operationally, and it is what a second `tenant_session` for the close would
    lose: the room would be free and the woman would be `in_service` forever,
    which is the exact defect this feature exists to eliminate.

    ⚠ MUTATION: give the close its own `tenant_session` → the second half reds
    with a free room and an `in_service` ticket.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        room_id = await _seed_room(factory, tenant_id)
        staff_id = await _seed_staff(factory, tenant_id)
        first = await _seed_ticket(factory, tenant_id, name="נועה")
        second = await _seed_ticket(factory, tenant_id, name="מיכל")

        dispatched = await _service(factory).take_next(
            tenant_id, room_id, staff_user_id=None, actor=_actor(tenant_id, staff_id)
        )
        assignment_id = dispatched.room.row.assignment_id
        assert assignment_id is not None
        await _service(factory).release(tenant_id, assignment_id, actor=_actor(tenant_id, staff_id))

        assert (await _ticket(factory, tenant_id, first)).status == QueueTicketStatus.DONE.value
        assert await _assignments_of(factory, tenant_id) == []

        # …and now the same act, interrupted between the two writes.
        second_dispatch = await _service(factory).take_next(
            tenant_id, room_id, staff_user_id=None, actor=_actor(tenant_id, staff_id)
        )
        second_assignment = second_dispatch.room.row.assignment_id
        assert second_assignment is not None
        service = _service(factory)

        async def _boom(*args: object, **kwargs: object) -> None:
            raise RuntimeError("the audit write failed")

        service._audit.record = _boom  # type: ignore[method-assign]
        with pytest.raises(RuntimeError):
            await service.release(tenant_id, second_assignment, actor=_actor(tenant_id, staff_id))

        assert (await _ticket(factory, tenant_id, second)).status == (
            QueueTicketStatus.IN_SERVICE.value
        )
        assert [row.id for row in await _assignments_of(factory, tenant_id)] == [second_assignment]
    finally:
        await engine.dispose()


async def test_a_second_release_re_closes_nothing_and_a_removed_ticket_is_never_resurrected(
    app_role_url: str,
) -> None:
    """A12 plus `close`'s own conjunct.

    A second release is a 200 that writes nothing — `wrote is False`, so neither
    the audit row nor the close happens. And a ticket a manager REMOVED while the
    fitting was running stays `removed`: freeing the room must not rewrite her
    removal as `done`, and rowcount 0 there raises nothing, because the room is
    free, which is what the staffer asked for.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        room_id = await _seed_room(factory, tenant_id)
        staff_id = await _seed_staff(factory, tenant_id)
        ticket_id = await _seed_ticket(factory, tenant_id, name="נועה")

        dispatched = await _service(factory).take_next(
            tenant_id, room_id, staff_user_id=None, actor=_actor(tenant_id, staff_id)
        )
        assignment_id = dispatched.room.row.assignment_id
        assert assignment_id is not None
        # A manager removes her mid-fitting: `remove`'s own predicate is
        # `status = 'waiting'`, so this is written directly.
        async with tenant_session(factory, tenant_id) as session:
            row = await TICKETS.by_id(session, tenant_id, ticket_id)
            assert row is not None
            row.status = QueueTicketStatus.REMOVED.value

        await _service(factory).release(tenant_id, assignment_id, actor=_actor(tenant_id, staff_id))
        await _service(factory).release(tenant_id, assignment_id, actor=_actor(tenant_id, staff_id))

        assert (await _ticket(factory, tenant_id, ticket_id)).status == (
            QueueTicketStatus.REMOVED.value
        )
        released = await _audit_rows(factory, tenant_id, AuditAction.FITTING_ROOM_RELEASED)
        assert [row.details.get("queue_ticket") for row in released] == [str(ticket_id)]
    finally:
        await engine.dispose()


# --- D10: the tile resolves a walk-in through the fifth join ------------------


async def test_a_dispatched_walk_in_names_the_tile_and_a_swept_ticket_does_not(
    app_role_url: str,
) -> None:
    """⚠ A20. Without the fifth join every dispatched walk-in renders as an
    anonymous visit — the tile would say a room is occupied and refuse to say by
    whom, on the surface whose entire purpose is to answer that.

    The second half is the join's `deleted_at IS NULL` conjunct: a ticket F20's
    retention sweep deletes makes the tile render an anonymous visit rather than
    quietly preserving a name in a table nobody thought of. That is the
    `customers` join's rule applied unchanged, and it is why the name is resolved
    on EVERY read instead of being snapshotted onto the assignment.

    The staff card inherits both for free — `occupancy_by_staff_id` is derived
    from the same rows — which is asserted here rather than assumed three times.

    ⚠ MUTATIONS RUN: drop the join → both halves anonymous; drop its
    `deleted_at` conjunct → the swept half reds.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        room_id = await _seed_room(factory, tenant_id)
        staff_id = await _seed_staff(factory, tenant_id)
        ticket_id = await _seed_ticket(factory, tenant_id, name="נועה בר")

        await _service(factory).take_next(
            tenant_id, room_id, staff_user_id=None, actor=_actor(tenant_id, staff_id)
        )
        read = await _service(factory).floor(tenant_id)
        assert [row.client_label for row in read.room_rows] == ["נועה בר"]
        assert read.occupancy_by_staff_id[staff_id].client_label == "נועה בר"

        async with tenant_session(factory, tenant_id) as session:
            row = await TICKETS.by_id(session, tenant_id, ticket_id)
            assert row is not None
            row.deleted_at = NOW

        swept = await _service(factory).floor(tenant_id)
        assert [row.client_label for row in swept.room_rows] == [None]
        assert swept.occupancy_by_staff_id[staff_id].client_label is None
    finally:
        await engine.dispose()


async def test_a_bride_who_booked_and_scanned_resolves_to_her_customer_record(
    app_role_url: str,
) -> None:
    """The COALESCE order, and it is not arbitrary: `customers.name` is the
    record with a verified phone behind it, while the ticket's name is what she
    typed at the QR sheet.

    ⚠ MUTATION RUN: swap to `coalesce(QueueTicket.name, Customer.name)` → the
    tile renders the typed name over the verified record.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        room_id = await _seed_room(factory, tenant_id)
        staff_id = await _seed_staff(factory, tenant_id)
        ticket_id = await _seed_ticket(factory, tenant_id, name="נועה מהסמארטפון")
        async with tenant_session(factory, tenant_id) as session:
            customer = Customer(
                tenant_id=tenant_id,
                phone=f"+9725{uuid.uuid4().int % 10**8:08d}",
                name="נועה בר",
            )
            session.add(customer)
            await session.flush()
            booking = Booking(
                tenant_id=tenant_id,
                customer_id=customer.id,
                appointment_type_id=uuid.uuid4(),
                appointment_type_name="מדידה",
                starts_at=NOW,
                seat_index=1,
                status=BookingStatus.CONFIRMED.value,
                terms_version_accepted=1,
                terms_accepted_at=NOW,
                checked_in_at=NOW,
            )
            session.add(booking)
            await session.flush()
            await ASSIGNMENTS.claim(
                session,
                tenant_id,
                room_id=room_id,
                staff_id=staff_id,
                booking_id=booking.id,
                queue_ticket_id=ticket_id,
            )

        read = await _service(factory).floor(tenant_id)

        assert [row.client_label for row in read.room_rows] == ["נועה בר"]
    finally:
        await engine.dispose()


# --- the cross-tenant probe, for the four verbs take-next's does not cover ----


async def test_tenant_b_reaches_none_of_tenant_a_s_tickets(app_role_url: str) -> None:
    """Every verb that takes a TICKET id, probed from the wrong boutique, as the
    app role. Each answers 404 — indistinguishable from missing — and tenant A's
    row is untouched by all four.

    ⚠ Same vacuity caveat as take-next's probe, and it was RE-RUN here: swapping
    `app_role_url` for `migrated_db` leaves this green, so what it measures is
    the repositories' EXPLICIT `tenant_id` predicates rather than RLS. RLS on
    `queue_tickets` is F33's `test_queue_isolation.py`.
    """
    engine, factory = _factory(app_role_url)
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    try:
        room_b = await _seed_room(factory, tenant_b)
        staff_b = await _seed_staff(factory, tenant_b)
        theirs = await _seed_ticket(factory, tenant_a, name="של א")
        actor = _actor(tenant_b, staff_b)
        service = _service(factory)

        for verb in (
            service.call(tenant_b, theirs, actor=actor),
            service.skip(tenant_b, theirs, seen_skip_count=0, actor=actor),
            service.remove(tenant_b, theirs, actor=actor),
            service.assign(
                tenant_b, room_b, queue_ticket_id=theirs, staff_user_id=None, actor=actor
            ),
        ):
            with pytest.raises(QueueTicketNotFoundError):
                await verb

        ticket = await _ticket(factory, tenant_a, theirs)
        assert ticket.status == QueueTicketStatus.WAITING.value
        assert ticket.called_at is None
        assert ticket.skip_count == 0
        assert await _assignments_of(factory, tenant_b) == []
        async with tenant_session(factory, tenant_b) as session:
            assert (await _service(factory)._waitlist(session, tenant_b)).entries == []
    finally:
        await engine.dispose()
