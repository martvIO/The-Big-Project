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
   genuinely BLOCK on uncommitted work, which here is the `SKIP LOCKED` timing
   test and nothing else.
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
from app.floor.service import FloorService
from app.floor.validation import QueueEmptyError, RoomOccupiedError, StaffOccupiedError
from app.models.audit_log import AuditLog
from app.models.constants import AuditAction, QueueTicketStatus, StaffRole, VisitType
from app.models.fitting_room_assignment import FittingRoomAssignment
from app.models.queue_ticket import QueueTicket

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
