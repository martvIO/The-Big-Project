"""F36's races, against real Postgres as the non-owner app role (`boutique_app`).

**Every case here needs a real server and a second transaction.** A monkeypatched
repository never raises `IntegrityError`, never takes a row lock, never blocks an
`ON CONFLICT` against an uncommitted delete and never stamps an identity-mapped
instance — and those four are the whole of what F36 installs. `test_floor_service.py`
proves the branches; this module proves the mechanisms the branches sit on.

⚠ **Every row this module COMMITS holds `owner` or `shift_manager`, never a floor
role**, and that is a hard rule rather than a preference — `test_floor_db.py`'s
rule verbatim. `migrated_db` and `app_role_url` are `scope="session"` so one
cluster is shared by every db-marked module, and pytest collects files
alphabetically: this file sorts BEFORE `test_migrations.py`, where
`test_adding_the_role_check_validates_existing_rows` re-adds 0011's TWO-value
CHECK over whatever rows exist. A committed `reception` row reddens a test that
has nothing to do with fitting rooms and whose failure names 0011's constraint.
Nothing here asserts anything about a role — the gate is `test_floor_service.py`'s
and `test_staff_role_gating.py`'s job.

**The interleave, and why it is not a bare `asyncio.gather`.** `tenant_session` is
`async with session_factory() as session, session.begin()`, so EXITING the context
manager IS the commit (`db/tenant.py:25`), and two nested `tenant_session`s on one
NullPool factory take two separate connections. For an INSERT race the ORDER is
what makes it safe: the loser opens its session and READS (a plain SELECT, which
takes no row locks) → the winner's inner `async with` opens, writes and EXITS,
which is the commit → only then does the loser issue its write, against a
COMMITTED key, so it fails immediately and nothing hangs. `asyncio.gather` does not
ORDER two transactions, so the loser most often runs after the winner commits
anyway and the branch goes green without the mechanism ever being exercised.

**Two tests here DO use tasks, and they are the exception the rule points at.**
`test_an_add_racing_a_remove_does_not_silently_lose_the_add` and
`test_a_room_cannot_be_deleted_out_from_under_a_claim` are about a statement
BLOCKING on another transaction's uncommitted work — which cannot be written as
nested `async with` blocks, because the inner block can then never reach its
commit and the test hangs to the CI timeout. Their ordering is enforced by the
DATABASE (a row lock, and `ON CONFLICT`'s wait on a conflicting tuple's `xmax`),
not by the scheduler, and an `asyncio.Event` plus a short hold is what puts each
statement on the right side of it. Each of the two says in its own docstring
which mutation reds it — and, where the plan predicted a mutation that did not,
says that too.

Every test mints its own tenant id: the cluster is session-scoped and nothing here
truncates.
"""

import asyncio
import uuid
from datetime import UTC, date, datetime
from typing import Any

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.auth.service import StaffContext
from app.db.repositories.fitting_assignment_dresses import FittingAssignmentDressesRepository
from app.db.repositories.fitting_room_assignments import (
    ROOM_ACTIVE_INDEX,
    STAFF_ACTIVE_INDEX,
    FittingRoomAssignmentsRepository,
    violated_index,
)
from app.db.repositories.fitting_rooms import FittingRoomsRepository
from app.db.repositories.staff_users import StaffUsersRepository
from app.db.tenant import tenant_session
from app.errors import DomainNotFoundError
from app.floor.service import FloorService
from app.floor.validation import RoomOccupiedError, StaffOccupiedError
from app.models.audit_log import AuditLog
from app.models.booking import Booking
from app.models.constants import AuditAction, BookingStatus, StaffRole
from app.models.customer import Customer
from app.models.dress import Dress
from app.models.fitting_assignment_dress import FittingAssignmentDress
from app.models.fitting_room_assignment import FittingRoomAssignment

# F38 made `last_day` a REQUIRED argument on StaffUsersRepository.soft_delete —
# the retention policy's predicate needs `last_day IS NOT NULL`, so a row
# offboarded without one is a person the platform can never scrub, and a default
# would have made forgetting it silent. This module only ever soft-deletes a
# staffer to set up a fixture, so any past date does; naming it says so.
_LEFT_ON = date(2026, 1, 31)


pytestmark = pytest.mark.db

# Frozen module constants rather than a real clock: every assertion below is an
# equality on a stored value, and now() would make them all approximate.
NOW = datetime(2026, 8, 3, 9, 12, tzinfo=UTC)
LATER = datetime(2026, 8, 3, 10, 30, tzinfo=UTC)
# 06:00Z on 2026-08-03 is 09:00 Asia/Jerusalem, i.e. inside the calendar day NOW
# falls in — which is what `_is_claimable` requires of a bound booking.
MORNING = datetime(2026, 8, 3, 6, 0, tzinfo=UTC)

# How long a blocking test holds its lock open. Long enough that the blocked
# statement is demonstrably issued first, short enough that two of them cost less
# than a second of suite time.
HOLD_SECONDS = 0.4
ISSUE_SECONDS = 0.05

ROOMS = FittingRoomsRepository()
ASSIGNMENTS = FittingRoomAssignmentsRepository()
BINDINGS = FittingAssignmentDressesRepository()


def _factory(app_role_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    return (
        engine := create_async_engine(app_role_url, poolclass=NullPool),
        async_sessionmaker(engine, expire_on_commit=False),
    )


def _actor(tenant_id: uuid.UUID, staff_id: uuid.UUID) -> StaffContext:
    """Always OWNER: this module commits its rows, and nothing here reads the
    role — the elevated branch of the two-axis rule just keeps every call legal
    whoever the target is."""
    return StaffContext(
        id=staff_id,
        tenant_id=tenant_id,
        email="owner@bella.example",
        display_name="Owner",
        role=StaffRole.OWNER.value,
    )


async def _seed_staff(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    *,
    display_name: str = "Staff",
) -> uuid.UUID:
    async with tenant_session(factory, tenant_id) as session:
        staff = await StaffUsersRepository().insert(
            session,
            tenant_id=tenant_id,
            email=f"rooms-{uuid.uuid4().hex[:10]}@bella.example",
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


async def _seed_dress(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, *, name: str = "ורוניק"
) -> uuid.UUID:
    async with tenant_session(factory, tenant_id) as session:
        dress = Dress(tenant_id=tenant_id, name=name, sort_order=0)
        session.add(dress)
        await session.flush()
        return dress.id


async def _seed_booking(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    *,
    checked_in: bool = True,
    customer_name: str = "מיכל",
    seat_index: int = 1,
) -> uuid.UUID:
    """`seat_index` is a parameter because `idx_bookings_slot_seat_unique` keys
    on (tenant, starts_at, seat) — two bookings in one slot need two seats."""
    async with tenant_session(factory, tenant_id) as session:
        customer = Customer(
            tenant_id=tenant_id,
            phone=f"+9725{uuid.uuid4().int % 10**8:08d}",
            name=customer_name,
        )
        session.add(customer)
        await session.flush()
        booking = Booking(
            tenant_id=tenant_id,
            customer_id=customer.id,
            appointment_type_id=uuid.uuid4(),
            starts_at=MORNING,
            seat_index=seat_index,
            status=BookingStatus.CONFIRMED.value,
            terms_version_accepted=1,
            terms_accepted_at=NOW,
            appointment_type_name="מדידה",
            checked_in_at=NOW if checked_in else None,
        )
        session.add(booking)
        await session.flush()
        return booking.id


async def _audit_rows(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, action: AuditAction
) -> list[AuditLog]:
    async with tenant_session(factory, tenant_id) as session:
        stmt = select(AuditLog).where(
            AuditLog.tenant_id == tenant_id, AuditLog.action == action.value
        )
        return list((await session.execute(stmt)).scalars().all())


def _service(factory: async_sessionmaker[AsyncSession], *, at: datetime = NOW) -> FloorService:
    return FloorService(factory, clock=lambda: at)


# --- the claim: the room index, the savepoint, and the 409 that names her ------


async def test_a_second_claim_landing_in_the_gap_is_refused_and_names_the_occupant(
    app_role_url: str,
) -> None:
    """⚠ THE SAVEPOINT'S ONLY WITNESS, and the reason it is here rather than in
    the fast suite: a fake repository raises nothing, so `session.begin_nested()`
    can be deleted from the service with every fast test still green.

    Without it the `IntegrityError` aborts the enclosing Postgres transaction,
    the occupant read that follows raises `PendingRollbackError`, and the 409 the
    staffer in the corridor needs becomes a 500.

    The GAP is made observable rather than assumed: the loser's own session is
    opened and reads the room FREE before the winner's transaction runs, and is
    still open when she issues her claim. She decided the room was free and the
    world changed under her — which is exactly the request the index exists to
    refuse.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        room_id = await _seed_room(factory, tenant_id)
        winner = await _seed_staff(factory, tenant_id, display_name="דנה")
        loser = await _seed_staff(factory, tenant_id, display_name="נועה")

        async with tenant_session(factory, tenant_id) as snapshot:
            # A plain SELECT — no row locks, so nothing the winner does can block
            # on it and nothing here can hang.
            tiles = await ROOMS.list_with_occupancy(snapshot, tenant_id)
            assert [row.assignment_id for row in tiles] == [None]

            async with tenant_session(factory, tenant_id) as _winner_session:
                await ASSIGNMENTS.claim(
                    _winner_session,
                    tenant_id,
                    room_id=room_id,
                    staff_id=winner,
                    booking_id=None,
                )

            with pytest.raises(RoomOccupiedError) as refused:
                await _service(factory).claim(
                    tenant_id,
                    room_id,
                    staff_user_id=loser,
                    booking_id=None,
                    actor=_actor(tenant_id, loser),
                )

        assert refused.value.details == {"staff_display_name": "דנה"}

        # …and nothing of the loser's landed: still exactly one live assignment.
        async with tenant_session(factory, tenant_id) as session:
            rows = await ROOMS.list_with_occupancy(session, tenant_id)
        assert [row.staff_user_id for row in rows] == [winner]
    finally:
        await engine.dispose()


async def test_a_worker_cannot_hold_two_rooms(app_role_url: str) -> None:
    """⚠ THE STAFF INDEX'S ONLY WITNESS. Two DIFFERENT rooms, so the room index
    is satisfied and every other assertion in the feature passes with
    `idx_fitting_room_assignments_staff_active` dropped — including the staff
    card's `occupied`, which would then have to CHOOSE between two rows.

    The 409 names the room she is already in, because "you are already somewhere"
    is not actionable and "you are in חדר 1" is."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        first = await _seed_room(factory, tenant_id, label="חדר 1", sort_order=0)
        second = await _seed_room(factory, tenant_id, label="חדר 2", sort_order=1)
        staff_id = await _seed_staff(factory, tenant_id, display_name="נועה")
        service = _service(factory)
        actor = _actor(tenant_id, staff_id)

        await service.claim(tenant_id, first, staff_user_id=staff_id, booking_id=None, actor=actor)
        with pytest.raises(StaffOccupiedError) as refused:
            await service.claim(
                tenant_id, second, staff_user_id=staff_id, booking_id=None, actor=actor
            )
        assert refused.value.details == {"room_label": "חדר 1"}

        async with tenant_session(factory, tenant_id) as session:
            rows = await ROOMS.list_with_occupancy(session, tenant_id)
        assert [row.assignment_id is not None for row in rows] == [True, False]
    finally:
        await engine.dispose()


async def test_a_released_room_is_immediately_reclaimable(app_role_url: str) -> None:
    """⚠ THE OTHER HALF OF THE PREDICATE PAIR. `test_a_second_claim_…` still
    passes with the room index narrowed to `WHERE deleted_at IS NULL` — a double
    claim fails either way. THIS is the one that reds, because a released
    assignment would still hold the key and the next bride could never have the
    room. The pair is what pins the predicate rather than the index."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        room_id = await _seed_room(factory, tenant_id)
        first = await _seed_staff(factory, tenant_id, display_name="דנה")
        second = await _seed_staff(factory, tenant_id, display_name="נועה")
        service = _service(factory)

        held = await service.claim(
            tenant_id, room_id, staff_user_id=first, booking_id=None, actor=_actor(tenant_id, first)
        )
        assignment_id = held.row.assignment_id
        assert assignment_id is not None
        await service.release(tenant_id, assignment_id, actor=_actor(tenant_id, first))

        reclaimed = await service.claim(
            tenant_id,
            room_id,
            staff_user_id=second,
            booking_id=None,
            actor=_actor(tenant_id, second),
        )
        assert reclaimed.row.staff_user_id == second
        assert reclaimed.row.assignment_id != assignment_id
    finally:
        await engine.dispose()


async def test_a_second_release_writes_nothing(app_role_url: str) -> None:
    """Rowcount 0 with a LIVE row back is a 200-unchanged, not an error: she
    wanted the room free and the room is free. What must NOT happen is a second
    audit row — a {released → released} entry would be noise in the only trail
    this area has — or the timestamp moving to the second caller's clock."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        room_id = await _seed_room(factory, tenant_id)
        staff_id = await _seed_staff(factory, tenant_id)
        actor = _actor(tenant_id, staff_id)

        held = await _service(factory).claim(
            tenant_id, room_id, staff_user_id=staff_id, booking_id=None, actor=actor
        )
        assignment_id = held.row.assignment_id
        assert assignment_id is not None

        await _service(factory, at=NOW).release(tenant_id, assignment_id, actor=actor)
        again = await _service(factory, at=LATER).release(tenant_id, assignment_id, actor=actor)
        assert again.row.assignment_id is None  # the tile is free, and stays free

        async with tenant_session(factory, tenant_id) as session:
            stored = await ASSIGNMENTS.by_id(session, tenant_id, assignment_id)
        assert stored is not None
        assert stored.released_at == NOW
        assert len(await _audit_rows(factory, tenant_id, AuditAction.FITTING_ROOM_RELEASED)) == 1
    finally:
        await engine.dispose()


async def test_a_release_landing_in_the_gap_renders_the_database_value(
    app_role_url: str,
) -> None:
    """⚠ THE `populate_existing=True` WITNESS, and the ONLY one.

    Every other test in the feature opens a FRESH session per operation, so the
    identity map is empty when the UPDATE runs and the flag is a no-op there —
    verified by mutation, recorded in the repository's own docstring. The bug
    needs the row LOADED IN THE SAME SESSION that then writes, which is the shape
    `FloorService.release` has because it must authorize on `staff_user_id`
    before it writes.

    The poisoning: the loser loads the row while `released_at IS NULL`. The winner
    releases at NOW and commits. The loser's `UPDATE … WHERE released_at IS NULL`
    now matches ZERO rows — but it is ORM-enabled DML whose default `evaluate`
    synchronization re-evaluates that predicate IN PYTHON against the
    identity-mapped instance, which still reads None, so it stamps
    `released_at = LATER` onto an object the database never touched. With
    `expire_on_commit=False` a plain re-read hands that object straight back and
    the panel renders the LOSER's timestamp for a release she did not perform.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        room_id = await _seed_room(factory, tenant_id)
        staff_id = await _seed_staff(factory, tenant_id)
        held = await _service(factory).claim(
            tenant_id,
            room_id,
            staff_user_id=staff_id,
            booking_id=None,
            actor=_actor(tenant_id, staff_id),
        )
        assignment_id = held.row.assignment_id
        assert assignment_id is not None

        async with tenant_session(factory, tenant_id) as loser:
            loaded = await ASSIGNMENTS.by_id(loser, tenant_id, assignment_id)
            assert loaded is not None
            assert loaded.released_at is None  # the predicate WOULD match

            async with tenant_session(factory, tenant_id) as winner:
                won, _ = await ASSIGNMENTS.release(winner, tenant_id, assignment_id, at=NOW)
                assert won is True

            wrote, row = await ASSIGNMENTS.release(loser, tenant_id, assignment_id, at=LATER)

        assert wrote is False
        assert row is not None
        assert row.released_at == NOW
        assert row.released_at != LATER

        async with tenant_session(factory, tenant_id) as session:
            stored = await ASSIGNMENTS.by_id(session, tenant_id, assignment_id)
        assert stored is not None
        assert stored.released_at == NOW
    finally:
        await engine.dispose()


# --- the handover -------------------------------------------------------------


async def test_a_handover_preserves_the_bindings_and_records_the_previous_holder(
    app_role_url: str,
) -> None:
    """⚠ THE IDENTITY-MAP WITNESS for the audit row's `from`.

    `test_floor_service.py` catches the CODE MOTION — it asserts the read is
    ordered before the write — but not its EFFECT: monkeypatched repositories
    never stamp anything, so a service that read `before.staff_user_id` after the
    writer would still record the right value there. Here the UPDATE is real, and
    `evaluate` synchronization stamps the NEW staffer onto the very instance the
    capture came from, out of one identity map. A service that read it afterwards
    would record `from == to` on every handover and empty the row of its whole
    informational content, with nothing else in the suite going red.

    The bindings surviving is the other half: a handover is a guarded UPDATE of
    ONE column, so the gowns in the room need no copying — release-and-reinsert
    would need a loop, a second failure mode, and a window in which the room is
    momentarily free for a third staffer to take.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        room_id = await _seed_room(factory, tenant_id)
        dress_id = await _seed_dress(factory, tenant_id)
        holder = await _seed_staff(factory, tenant_id, display_name="דנה")
        receiver = await _seed_staff(factory, tenant_id, display_name="נועה")
        service = _service(factory)
        actor = _actor(tenant_id, holder)

        held = await service.claim(
            tenant_id, room_id, staff_user_id=holder, booking_id=None, actor=actor
        )
        assignment_id = held.row.assignment_id
        assert assignment_id is not None
        await service.add_dress(
            tenant_id, assignment_id, dress_id=dress_id, size_label="38", actor=actor
        )

        handed = await service.handover(
            tenant_id, assignment_id, new_staff_id=receiver, actor=actor
        )

        assert handed.row.staff_user_id == receiver
        assert handed.row.assignment_id == assignment_id  # the id is STABLE
        assert handed.row.assigned_at == held.row.assigned_at  # the CLIENT's clock
        assert [binding.dress_id for binding in handed.bindings] == [dress_id]

        rows = await _audit_rows(factory, tenant_id, AuditAction.FITTING_ROOM_HANDED_OVER)
        assert len(rows) == 1
        assert rows[0].details == {
            "assignment": str(assignment_id),
            "from": str(holder),
            "to": str(receiver),
        }
        assert rows[0].details["from"] != rows[0].details["to"]
    finally:
        await engine.dispose()


# --- the dress bindings -------------------------------------------------------


async def test_a_concurrent_double_add_yields_one_binding(app_role_url: str) -> None:
    """Two staffers tapping «ורוניק» at the same instant both wanted the dress in
    the room, and the dress is in the room: the second is a SUCCESS, not a 409.

    The loser reads first and finds nothing, the winner commits, and only then
    does the loser insert — against a committed key, so `ON CONFLICT` fires
    immediately and `(xmax = 0)` reports `inserted=False`. Removing `index_where`
    from the inference makes the statement fail to match the PARTIAL index and
    raise instead of doing nothing."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        room_id = await _seed_room(factory, tenant_id)
        dress_id = await _seed_dress(factory, tenant_id)
        staff_id = await _seed_staff(factory, tenant_id)
        held = await _service(factory).claim(
            tenant_id,
            room_id,
            staff_user_id=staff_id,
            booking_id=None,
            actor=_actor(tenant_id, staff_id),
        )
        assignment_id = held.row.assignment_id
        assert assignment_id is not None

        async with tenant_session(factory, tenant_id) as loser:
            existing = await BINDINGS.by_assignment_ids(loser, tenant_id, [assignment_id])
            assert existing == {}

            async with tenant_session(factory, tenant_id) as winner:
                inserted, first = await BINDINGS.add(
                    winner,
                    tenant_id,
                    assignment_id=assignment_id,
                    dress_id=dress_id,
                    dress_name="ורוניק",
                    dress_size="38",
                )
                assert inserted is True

            again, second = await BINDINGS.add(
                loser,
                tenant_id,
                assignment_id=assignment_id,
                dress_id=dress_id,
                dress_name="ורוניק",
                dress_size="40",
            )

        assert again is False
        assert second.id == first.id
        # The SNAPSHOTS are not rewritten by the second tap: what the room was
        # given must not be changed by somebody arriving after it.
        assert second.dress_size == "38"

        async with tenant_session(factory, tenant_id) as session:
            grouped = await BINDINGS.by_assignment_ids(session, tenant_id, [assignment_id])
        assert [row.id for row in grouped[assignment_id]] == [first.id]
    finally:
        await engine.dispose()


async def test_a_removed_dress_can_be_re_added(app_role_url: str) -> None:
    """The partial index is `WHERE deleted_at IS NULL`, so a gown carried out and
    carried back in gets a NEW row rather than a conflict — and the removed row
    survives as the audit record of what left the room and who took it out. Making
    the index TOTAL reds this and nothing else."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        room_id = await _seed_room(factory, tenant_id)
        dress_id = await _seed_dress(factory, tenant_id)
        staff_id = await _seed_staff(factory, tenant_id)
        actor = _actor(tenant_id, staff_id)
        held = await _service(factory).claim(
            tenant_id, room_id, staff_user_id=staff_id, booking_id=None, actor=actor
        )
        assignment_id = held.row.assignment_id
        assert assignment_id is not None

        added = await _service(factory).add_dress(
            tenant_id, assignment_id, dress_id=dress_id, size_label="38", actor=actor
        )
        first_binding = added.bindings[0].id
        await _service(factory, at=LATER).remove_dress(
            tenant_id, assignment_id, first_binding, actor=actor
        )
        back = await _service(factory).add_dress(
            tenant_id, assignment_id, dress_id=dress_id, size_label="40", actor=actor
        )

        assert [binding.id for binding in back.bindings] != [first_binding]
        assert [binding.dress_size for binding in back.bindings] == ["40"]

        async with tenant_session(factory, tenant_id) as session:
            removed = await BINDINGS.by_id_any_state(session, tenant_id, first_binding)
        assert removed is not None
        assert removed.deleted_at == LATER
        assert removed.removed_by == staff_id
    finally:
        await engine.dispose()


async def test_an_add_racing_a_remove_does_not_silently_lose_the_add(
    app_role_url: str,
) -> None:
    """The "later commit wins" rule, proved rather than asserted: an add ISSUED
    while a remove of the same dress is still uncommitted ends as a REAL
    re-insert, not as a swallowed no-op and not as an error.

    **This is the one shape that cannot be written as nested `async with`
    blocks** — T2's statement must be in flight while T1's transaction is still
    open, and T1 must then reach its commit — so it runs as two tasks whose
    ordering is enforced by the row lock rather than by the scheduler. That it
    does not deadlock, and that the blocked statement resumes correctly after the
    delete commits, is half of what is being pinned.

    ⚠ **What this test does NOT pin, stated because the plan claimed it did:
    `DO UPDATE` versus `DO NOTHING`. MUTATION RUN, and it stayed GREEN.** The
    plan's story — T2 conflicts against the still-live row, does nothing, and the
    staffer is told a dress went into a room it left — does not happen on
    Postgres 16: `ON CONFLICT ... DO NOTHING` also waits on the conflicting
    tuple's `xmax` and RE-CHECKS the index after the other transaction commits,
    so it re-inserts here exactly as `DO UPDATE` does.

    `DO UPDATE` IS pinned, by the two add-vs-add tests instead — with `DO NOTHING`
    a conflict against a COMMITTED live row returns no row at all, so `RETURNING`
    is empty and there is no `(xmax = 0)` discriminator to read.
    `test_a_concurrent_double_add_yields_one_binding` here and
    `test_a_second_add_of_one_dress_is_a_no_op_success` in
    `test_fitting_rooms_repositories.py` are the two that go red; the plan
    predicted both would stay green and both do not.

    What DOES red this test: removing `index_where` from the inference, and
    making the unique index TOTAL. Both mutations run.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        room_id = await _seed_room(factory, tenant_id)
        dress_id = await _seed_dress(factory, tenant_id)
        staff_id = await _seed_staff(factory, tenant_id)
        actor = _actor(tenant_id, staff_id)
        held = await _service(factory).claim(
            tenant_id, room_id, staff_user_id=staff_id, booking_id=None, actor=actor
        )
        assignment_id = held.row.assignment_id
        assert assignment_id is not None
        added = await _service(factory).add_dress(
            tenant_id, assignment_id, dress_id=dress_id, size_label="38", actor=actor
        )
        binding_id = added.bindings[0].id

        removed = asyncio.Event()

        async def remover() -> None:
            async with tenant_session(factory, tenant_id) as session:
                assert await BINDINGS.remove(
                    session,
                    tenant_id,
                    assignment_id=assignment_id,
                    binding_id=binding_id,
                    actor_id=staff_id,
                    at=LATER,
                )
                removed.set()
                # Held UNCOMMITTED, so the adder's statement is issued into the
                # window this test exists to describe. Exiting is the commit.
                await asyncio.sleep(HOLD_SECONDS)

        async def adder() -> tuple[bool, FittingAssignmentDress]:
            await removed.wait()
            await asyncio.sleep(ISSUE_SECONDS)
            async with tenant_session(factory, tenant_id) as session:
                return await BINDINGS.add(
                    session,
                    tenant_id,
                    assignment_id=assignment_id,
                    dress_id=dress_id,
                    dress_name="ורוניק",
                    dress_size="40",
                )

        _, (inserted, row) = await asyncio.gather(remover(), adder())

        # A REAL insert, not a swallowed conflict: the add was not lost.
        assert inserted is True
        assert row.id != binding_id
        assert row.dress_size == "40"

        async with tenant_session(factory, tenant_id) as session:
            grouped = await BINDINGS.by_assignment_ids(session, tenant_id, [assignment_id])
        assert [binding.id for binding in grouped[assignment_id]] == [row.id]
    finally:
        await engine.dispose()


# --- the room lock (AC17) -----------------------------------------------------


async def test_a_room_cannot_be_deleted_out_from_under_a_claim(app_role_url: str) -> None:
    """⚠ THE `FOR UPDATE` WITNESS. No other test takes two statements against one
    room from two transactions.

    Deleting a room is the one hidden read-then-write in the feature: read
    occupancy, then stamp `deleted_at`. That is a CROSS-ROW invariant, which is
    exactly the shape no unique index can express. Without the lock the delete's
    occupancy guard reads a snapshot the claim is not yet in, both commit, and the
    result is **a soft-deleted room holding a live assignment** — a row no read
    surfaces, so there is NO UI PATH TO RELEASE IT, the staffer's key stays in the
    staff index forever and she can never claim another room. Recovery needs psql,
    and no assertion anywhere else would have failed.

    Two tasks again, and for the same reason as the add/remove race: the delete's
    read must be ISSUED while the claim's transaction is still open, and the claim
    must then reach its commit.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        room_id = await _seed_room(factory, tenant_id)
        staff_id = await _seed_staff(factory, tenant_id)
        claimed = asyncio.Event()

        async def claimer() -> None:
            async with tenant_session(factory, tenant_id) as session:
                # The claim's half of the per-room lock, taken exactly as
                # FloorService.claim takes it.
                assert await ROOMS.by_id_for_update(session, tenant_id, room_id) is not None
                await ASSIGNMENTS.claim(
                    session, tenant_id, room_id=room_id, staff_id=staff_id, booking_id=None
                )
                claimed.set()
                await asyncio.sleep(HOLD_SECONDS)

        async def deleter() -> BaseException | None:
            await claimed.wait()
            await asyncio.sleep(ISSUE_SECONDS)
            try:
                await _service(factory).delete_room(
                    tenant_id, room_id, actor=_actor(tenant_id, staff_id)
                )
            except BaseException as error:  # noqa: BLE001 - the assertion is the type
                return error
            return None

        _, refused = await asyncio.gather(claimer(), deleter())

        assert isinstance(refused, RoomOccupiedError), refused
        async with tenant_session(factory, tenant_id) as session:
            room = await ROOMS.by_id(session, tenant_id, room_id)
            occupied = await ASSIGNMENTS.has_active_for_room(session, tenant_id, room_id)
        assert room is not None, "the room was soft-deleted out from under a live claim"
        assert occupied is True
        assert await _audit_rows(factory, tenant_id, AuditAction.FITTING_ROOM_DELETED) == []
    finally:
        await engine.dispose()


# --- idempotence, the anonymous 409, and the check-in predicate ---------------


async def test_re_claiming_your_own_room_is_a_200_whichever_index_reports(
    app_role_url: str,
) -> None:
    """Re-claiming the room she already holds violates BOTH partial unique
    indexes at once, and Postgres reports only the FIRST that fails, in index-OID
    order — i.e. migration creation order, which flips after any
    `REINDEX CONCURRENTLY` or `pg_repack`.

    So the idempotence branch is keyed on the REQUEST and resolved BEFORE the
    constraint name is looked at: 200 with that card and NO audit row, nothing
    changed. A branch derived from the name would pass in one creation order and
    refuse the staffer her own room in the other — «היא כבר בחדר 2», the screen
    refusing her with the name of the room she is standing in.

    Both halves are asserted: that the raw INSERT really does violate one of the
    two indexes on this cluster (so the 200 below is a resolved conflict and not
    an absent one), and that the service answers 200 anyway.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        room_id = await _seed_room(factory, tenant_id)
        staff_id = await _seed_staff(factory, tenant_id)
        actor = _actor(tenant_id, staff_id)
        held = await _service(factory).claim(
            tenant_id, room_id, staff_user_id=staff_id, booking_id=None, actor=actor
        )

        async with tenant_session(factory, tenant_id) as session:
            with pytest.raises(IntegrityError) as raw:
                async with session.begin_nested():
                    await ASSIGNMENTS.claim(
                        session, tenant_id, room_id=room_id, staff_id=staff_id, booking_id=None
                    )
        assert violated_index(raw.value) in {ROOM_ACTIVE_INDEX, STAFF_ACTIVE_INDEX}

        again = await _service(factory).claim(
            tenant_id, room_id, staff_user_id=staff_id, booking_id=None, actor=actor
        )
        assert again.row.assignment_id == held.row.assignment_id
        assert len(await _audit_rows(factory, tenant_id, AuditAction.FITTING_ROOM_CLAIMED)) == 1
    finally:
        await engine.dispose()


async def test_a_claim_whose_occupant_cannot_be_named_does_not_name_nobody(
    app_role_url: str,
) -> None:
    """⚠ `details` is ABSENT, never `{"staff_display_name": null}`.

    D11's ghost holder is the forceable shape of "there is nobody to name": the
    occupant's staff row is soft-deleted while she still holds the room, so
    `_occupant_details` finds the assignment and no staffer behind it. A null
    would break the console's `Record<string, string>` type and «{{name}} כבר
    בחדר הזה.» would render with an empty interpolation on a legally binding
    surface. A sentence that admits it does not know is better.

    Every other 409 test in this module has an occupant to read, which is why
    this one exists.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        room_id = await _seed_room(factory, tenant_id)
        ghost = await _seed_staff(factory, tenant_id, display_name="דנה")
        newcomer = await _seed_staff(factory, tenant_id, display_name="נועה")
        await _service(factory).claim(
            tenant_id, room_id, staff_user_id=ghost, booking_id=None, actor=_actor(tenant_id, ghost)
        )
        async with tenant_session(factory, tenant_id) as session:
            await StaffUsersRepository().soft_delete(session, tenant_id, ghost, last_day=_LEFT_ON)

        with pytest.raises(RoomOccupiedError) as refused:
            await _service(factory).claim(
                tenant_id,
                room_id,
                staff_user_id=newcomer,
                booking_id=None,
                actor=_actor(tenant_id, newcomer),
            )
        assert refused.value.details is None
    finally:
        await engine.dispose()


async def test_a_booking_that_has_not_checked_in_cannot_be_bound_to_a_room(
    app_role_url: str,
) -> None:
    """⚠ THE PREDICATE THAT MAKES THE PRIVACY ARGUMENT TRUE RATHER THAN
    ASPIRATIONAL, and the only fixture in the suite that is not checked in.

    `deleted_at IS NULL AND status <> 'cancelled'` alone admits NEXT MONTH's
    booking, whose customer's name would then surface on a five-role payload for
    as long as the assignment stayed open. Its absence is invisible without a
    booking that has not arrived — every other one in the suite has."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        room_id = await _seed_room(factory, tenant_id)
        staff_id = await _seed_staff(factory, tenant_id)
        actor = _actor(tenant_id, staff_id)
        not_arrived = await _seed_booking(factory, tenant_id, checked_in=False)
        arrived = await _seed_booking(
            factory, tenant_id, checked_in=True, customer_name="מיכל", seat_index=2
        )

        with pytest.raises(DomainNotFoundError):
            await _service(factory).claim(
                tenant_id, room_id, staff_user_id=staff_id, booking_id=not_arrived, actor=actor
            )
        # Nothing was written by the refusal, so the room is still claimable.
        bound = await _service(factory).claim(
            tenant_id, room_id, staff_user_id=staff_id, booking_id=arrived, actor=actor
        )
        assert bound.row.booking_id == arrived
        assert bound.row.client_label == "מיכל"
    finally:
        await engine.dispose()


# --- AC8's structural half ----------------------------------------------------

_PERSONAL = {"client_name", "customer_name", "client_phone", "phone", "name", "email", "notes"}

_EXPECTED_COLUMNS = {
    "fitting_rooms": {
        "id",
        "tenant_id",
        "label",
        "sort_order",
        "is_active",
        "created_at",
        "updated_at",
        "deleted_at",
    },
    "fitting_room_assignments": {
        "id",
        "tenant_id",
        "fitting_room_id",
        "staff_user_id",
        "booking_id",
        # F58's half of the same rule. A POINTER at a live queue_tickets row,
        # never a copy of anything on it — which is why adding it leaves this
        # test's whole argument intact rather than weakening it. A soft-deleted
        # or swept ticket renders an anonymous visit, exactly as a swept booking
        # already does.
        "queue_ticket_id",
        "released_at",
        "created_at",
        "updated_at",
        "deleted_at",
    },
    "fitting_assignment_dresses": {
        "id",
        "tenant_id",
        "fitting_room_assignment_id",
        "dress_id",
        "dress_name",
        "dress_size",
        "removed_by",
        "created_at",
        "updated_at",
        "deleted_at",
    },
}


async def test_the_assignment_stores_no_personal_column(app_role_url: str) -> None:
    """⚠ AC8's structural half, and a SET EQUALITY on all three tables rather
    than a blacklist — the column a later feature adds will not be called
    `client_name`.

    The assignment stores TWO POINTERS — `booking_id` and, since F58,
    `queue_ticket_id` — and no personal field of any kind, so the card's label is
    resolved on every read from the live rows. A snapshotted name would SURVIVE
    both the walk-in auto-delete and F20's retention sweep: the platform would
    delete a customer record and quietly keep a copy of who she was, in a table
    nobody thought of, on a screen five roles can open.

    ⚠ F58's column is the first ADDITION this set equality has ever refused, and
    that is the test working. Neither the F58 spec's D1 nor its plan named this
    guard — both named only the three in `test_migrations.py` — so the addition
    was reviewed here, on the failure, which is exactly the review the equality
    exists to force.

    `dress_name` and `dress_size` are snapshots and are deliberately IN the set —
    a gown is not a person, and the owner renaming one mid-fitting must not
    rewrite what actually went into the room.
    """
    engine, factory = _factory(app_role_url)
    try:
        async with factory() as session:
            rows = (
                await session.execute(
                    text(
                        "SELECT table_name, column_name FROM information_schema.columns "
                        "WHERE table_schema = 'public' AND table_name IN "
                        "('fitting_rooms', 'fitting_room_assignments', "
                        "'fitting_assignment_dresses')"
                    )
                )
            ).all()
        columns: dict[str, set[str]] = {}
        for table, column in rows:
            columns.setdefault(str(table), set()).add(str(column))

        assert columns == _EXPECTED_COLUMNS
        assert columns["fitting_room_assignments"] & _PERSONAL == set()
    finally:
        await engine.dispose()


# --- the ORM's own view of the same fact --------------------------------------


async def test_the_assignment_model_exposes_no_personal_attribute(
    app_role_url: str,
) -> None:
    """The same claim one layer up, because a mapped column is what a later
    reader would actually add. Cheap, and it fails on the same edit."""
    mapped: Any = FittingRoomAssignment.__table__.columns
    assert {column.name for column in mapped} == _EXPECTED_COLUMNS["fitting_room_assignments"]
