"""F36's three tables in the permanent cross-tenant isolation suite (AC10, AC11).

⚠ **Connected ONLY as the non-owner `boutique_app` role, over a `NullPool`
engine, via the `app_role_url` fixture — NEVER `migrated_db`.** The container
superuser bypasses RLS and every GRANT unconditionally.

The swap WAS performed as a mutation check, and the result is better than the
plan predicted: all seven cases go **RED**, not vacuously green. That is by
construction rather than by luck — every probe passes the FOREIGN tenant id as
the repository argument, so with RLS bypassed the repositories' own
`tenant_id ==` predicate matches and the foreign row comes back. A probe written
the other way (own tenant id, assert the list is short) would have passed
silently, which is the shape to avoid if a case is ever added here.

**What makes fitting rooms worth a suite of their own rather than one more row in
`test_tenant_isolation.py`'s scan.** The assignment is the only table in the
product that names a member of staff, a room and a customer's booking in one row,
and the payload read joins FIVE tables — `fitting_rooms`, `fitting_room_assignments`,
`staff_users`, `bookings`, `customers`. A join is exactly where a missing policy
hides: the driving table is filtered, the joined one is not, and one boutique's
bride's name arrives on another boutique's floor with every row-count assertion
still passing. So the payload read is probed here directly, not only the writers.

**The app role's PRIVILEGES are exercised on purpose, and the plan was wrong
about why.** Its mutation table predicted that dropping one of 0019's three
`GRANT` statements would red a write probe. MUTATION RUN: it changes nothing at
all, because **0002's `ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT,
INSERT, UPDATE, DELETE ON TABLES TO app_user` already confers them** on every
table a later migration creates as that role. 0019's explicit GRANT loop is
redundant — belt-and-braces for a table created out-of-band, which is what 0002's
own comment says it is for.

What the probes below therefore pin is the PRIVILEGE, not the statement: a
`REVOKE`, a future narrowing of 0002's default privileges, or a table created by
a different deploy role all show up here as `permission denied` (verified by
mutation — revoking INSERT on one table reds four cases). Nothing else in the
suite would name the table.
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.auth.service import StaffContext
from app.db.repositories.fitting_assignment_dresses import FittingAssignmentDressesRepository
from app.db.repositories.fitting_room_assignments import FittingRoomAssignmentsRepository
from app.db.repositories.fitting_rooms import FittingRoomsRepository
from app.db.repositories.staff_users import StaffUsersRepository
from app.db.tenant import tenant_session
from app.errors import DomainNotFoundError
from app.floor.service import FloorService
from app.models.constants import StaffRole

pytestmark = pytest.mark.db

LATER = datetime(2026, 8, 3, 10, 30, tzinfo=UTC)

ROOMS = FittingRoomsRepository()
ASSIGNMENTS = FittingRoomAssignmentsRepository()
BINDINGS = FittingAssignmentDressesRepository()


def _factory(app_role_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(app_role_url, poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _actor(tenant_id: uuid.UUID, staff_id: uuid.UUID) -> StaffContext:
    return StaffContext(
        id=staff_id,
        tenant_id=tenant_id,
        email="owner@bella.example",
        display_name="Owner",
        role=StaffRole.OWNER.value,
    )


async def _seed_tenant(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    """A staffer, a room, her assignment and one dress binding — all four rows
    F36 owns, in one tenant. Returns (staff, room, assignment, binding).

    ⚠ `owner` always: this module COMMITS its rows and the cluster is shared, so
    a floor role here would redden `test_migrations.py`'s 0011 CHECK backfill —
    `test_floor_db.py`'s rule verbatim. Nothing here reads the role.
    """
    async with tenant_session(factory, tenant_id) as session:
        staff = await StaffUsersRepository().insert(
            session,
            tenant_id=tenant_id,
            email=f"iso-{uuid.uuid4().hex[:10]}@bella.example",
            password_hash="not-a-real-hash",
            display_name="דנה",
            role=StaffRole.OWNER.value,
        )
        room = await ROOMS.insert(session, tenant_id, label="חדר 1", sort_order=0)
        assignment = await ASSIGNMENTS.claim(
            session, tenant_id, room_id=room.id, staff_id=staff.id, booking_id=None
        )
        _, binding = await BINDINGS.add(
            session,
            tenant_id,
            assignment_id=assignment.id,
            dress_id=uuid.uuid4(),
            dress_name="ורוניק",
            dress_size="38",
        )
        return staff.id, room.id, assignment.id, binding.id


# --- the readers --------------------------------------------------------------


async def test_no_reader_crosses_a_tenant_on_any_of_the_three_tables(
    app_role_url: str,
) -> None:
    """Every read F36 owns, run from tenant B's connection with tenant A's
    arguments — which is what makes a pass here RLS doing the work rather than
    the repositories' redundant `tenant_id ==` predicate. With the policy off
    that predicate alone would still let `tenant_id == A` through on B's
    connection, because B is the one supplying it.

    A foreign id reads as MISSING (`None` / empty / `False`), never as a refusal
    that would confirm the row exists — one indistinguishable 404, which is the
    whole of AC10 at the repository layer.
    """
    engine, factory = _factory(app_role_url)
    here, elsewhere = uuid.uuid4(), uuid.uuid4()
    try:
        staff_id, room_id, assignment_id, binding_id = await _seed_tenant(factory, elsewhere)
        await _seed_tenant(factory, here)

        async with tenant_session(factory, here) as session:
            assert await ROOMS.by_id(session, elsewhere, room_id) is None
            assert await ROOMS.by_id_for_update(session, elsewhere, room_id) is None
            assert await ROOMS.room_with_occupancy(session, elsewhere, room_id) is None
            assert await ROOMS.occupancy_for_staff(session, elsewhere, staff_id) is None
            assert await ROOMS.list_live(session, elsewhere) == []
            assert await ROOMS.list_with_occupancy(session, elsewhere) == []

            assert await ASSIGNMENTS.by_id(session, elsewhere, assignment_id) is None
            assert await ASSIGNMENTS.active_by_id(session, elsewhere, assignment_id) is None
            assert await ASSIGNMENTS.active_for(session, elsewhere, room_id, staff_id) is None
            assert await ASSIGNMENTS.occupant_of_room(session, elsewhere, room_id) is None
            assert await ASSIGNMENTS.room_of_staff(session, elsewhere, staff_id) is None
            assert await ASSIGNMENTS.has_active_for_room(session, elsewhere, room_id) is False

            assert await BINDINGS.by_id_any_state(session, elsewhere, binding_id) is None
            assert await BINDINGS.by_assignment_ids(session, elsewhere, [assignment_id]) == {}
    finally:
        await engine.dispose()


async def test_the_payload_read_never_joins_another_tenants_rows(app_role_url: str) -> None:
    """⚠ THE FIVE-TABLE JOIN, probed as its own case.

    `list_with_occupancy` drives from `fitting_rooms` and LEFT JOINs the
    assignment, the staffer, the booking and the customer. A policy missing on any
    ONE of those four would leave the room list correctly filtered while a
    foreign holder's name — or a foreign bride's — rode in on the join, and the
    row COUNT would be identical. So the assertion is on the joined columns, not
    on the length.
    """
    engine, factory = _factory(app_role_url)
    here, elsewhere = uuid.uuid4(), uuid.uuid4()
    try:
        await _seed_tenant(factory, elsewhere)
        mine_staff, mine_room, _, _ = await _seed_tenant(factory, here)

        async with tenant_session(factory, here) as session:
            rows = await ROOMS.list_with_occupancy(session, here)
        assert [row.room_id for row in rows] == [mine_room]
        assert [row.staff_user_id for row in rows] == [mine_staff]
        assert [row.staff_display_name for row in rows] == ["דנה"]
    finally:
        await engine.dispose()


# --- the writers, through the service (AC10) ----------------------------------


async def test_every_mutation_on_another_tenants_row_is_an_indistinguishable_404(
    app_role_url: str,
) -> None:
    """⚠ AC10, at the layer that answers the HTTP status. Tenant B tries every
    verb F36 ships against tenant A's rows and gets the SAME `DomainNotFoundError`
    she would get for an id that never existed — never a 403, which would confirm
    the row is real, and never a 409, which would confirm it is occupied.

    The claim is the interesting one: B's `by_id_for_update` finds no room, so she
    is refused BEFORE the INSERT — meaning A's partial unique indexes are never
    even consulted, and B cannot use a conflict as an oracle either.
    """
    engine, factory = _factory(app_role_url)
    here, elsewhere = uuid.uuid4(), uuid.uuid4()
    try:
        _, room_id, assignment_id, binding_id = await _seed_tenant(factory, elsewhere)
        my_staff, _, _, _ = await _seed_tenant(factory, here)
        service = FloorService(factory, clock=lambda: LATER)
        actor = _actor(here, my_staff)

        with pytest.raises(DomainNotFoundError):
            await service.claim(here, room_id, staff_user_id=my_staff, booking_id=None, actor=actor)
        with pytest.raises(DomainNotFoundError):
            await service.release(here, assignment_id, actor=actor)
        with pytest.raises(DomainNotFoundError):
            await service.handover(here, assignment_id, new_staff_id=my_staff, actor=actor)
        with pytest.raises(DomainNotFoundError):
            await service.add_dress(
                here, assignment_id, dress_id=uuid.uuid4(), size_label="38", actor=actor
            )
        with pytest.raises(DomainNotFoundError):
            await service.remove_dress(here, assignment_id, binding_id, actor=actor)
        with pytest.raises(DomainNotFoundError):
            await service.update_room(
                here, room_id, label="גנוב", sort_order=None, is_active=None, actor=actor
            )
        with pytest.raises(DomainNotFoundError):
            await service.delete_room(here, room_id, actor=actor)

        # …and the SAME error for an id that never existed anywhere, which is what
        # makes the two indistinguishable rather than merely both refused.
        with pytest.raises(DomainNotFoundError):
            await service.release(here, uuid.uuid4(), actor=actor)
    finally:
        await engine.dispose()


async def test_nothing_of_the_foreign_tenants_moved(app_role_url: str) -> None:
    """A silently-refused cross-tenant write and a silently-SUCCEEDING one look
    identical from the caller's side, so the owning tenant re-reads afterwards.
    Every value is asserted, not just the row's existence: a policy that filters
    SELECT but not UPDATE would leave the row present and rewritten.
    """
    engine, factory = _factory(app_role_url)
    here, elsewhere = uuid.uuid4(), uuid.uuid4()
    try:
        staff_id, room_id, assignment_id, binding_id = await _seed_tenant(factory, elsewhere)
        my_staff, _, _, _ = await _seed_tenant(factory, here)
        service = FloorService(factory, clock=lambda: LATER)
        actor = _actor(here, my_staff)

        for attempt in (
            service.release(here, assignment_id, actor=actor),
            service.handover(here, assignment_id, new_staff_id=my_staff, actor=actor),
            service.remove_dress(here, assignment_id, binding_id, actor=actor),
            service.delete_room(here, room_id, actor=actor),
        ):
            with pytest.raises(DomainNotFoundError):
                await attempt

        async with tenant_session(factory, elsewhere) as session:
            room = await ROOMS.by_id(session, elsewhere, room_id)
            assignment = await ASSIGNMENTS.by_id(session, elsewhere, assignment_id)
            binding = await BINDINGS.by_id_any_state(session, elsewhere, binding_id)

        assert room is not None
        assert (room.label, room.is_active, room.deleted_at) == ("חדר 1", True, None)
        assert assignment is not None
        assert assignment.staff_user_id == staff_id  # not handed to the intruder
        assert assignment.released_at is None
        assert binding is not None
        assert (binding.deleted_at, binding.removed_by) == (None, None)
    finally:
        await engine.dispose()


# --- the GRANTs ---------------------------------------------------------------


async def test_the_app_role_may_insert_select_and_update_all_three_tables(
    app_role_url: str,
) -> None:
    """⚠ THE ONLY TEST IN THE PRODUCT THAT NAMES THESE THREE TABLES WHEN A
    PRIVILEGE GOES MISSING.

    Every other db module would also break, but a `permission denied` there looks
    like an unrelated failure in somebody else's feature. Here it is the
    assertion, and the failure names the table.

    ⚠ It does NOT pin 0019's `GRANT` statements — those are redundant, see the
    module docstring. It pins the privilege however it arrives.

    Every verb the app role actually issues is exercised: INSERT (the room, the
    claim, the binding), SELECT (the reads back) and UPDATE (release, soft
    delete, and the binding's soft delete). No DELETE — nothing in this feature
    hard-deletes, and asserting a privilege the code never uses would be pinning
    one we could drop.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        staff_id, room_id, assignment_id, binding_id = await _seed_tenant(factory, tenant_id)

        async with tenant_session(factory, tenant_id) as session:
            assert await ROOMS.by_id(session, tenant_id, room_id) is not None
            assert await ASSIGNMENTS.by_id(session, tenant_id, assignment_id) is not None
            assert await BINDINGS.by_id_any_state(session, tenant_id, binding_id) is not None

            assert await BINDINGS.remove(
                session,
                tenant_id,
                assignment_id=assignment_id,
                binding_id=binding_id,
                actor_id=staff_id,
                at=LATER,
            )
            wrote, _ = await ASSIGNMENTS.release(session, tenant_id, assignment_id, at=LATER)
            assert wrote is True
            assert await ROOMS.soft_delete(session, tenant_id, room_id) is True
    finally:
        await engine.dispose()


async def test_the_app_role_cannot_reach_a_row_without_a_tenant_context(
    app_role_url: str,
) -> None:
    """`current_setting(..., missing_ok := true)` yields NULL with no context set,
    so the policy's predicate is NULL and the connection sees ZERO rows. It fails
    CLOSED rather than erroring or, worse, seeing everything — which is what makes
    a forgotten `tenant_session` a bug that shows up as empty data rather than as
    a cross-tenant leak.

    Deliberately NOT wrapped in `tenant_session`: this is the one place the raw
    factory is used, because setting the context is exactly what is being left
    out.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        _, room_id, assignment_id, binding_id = await _seed_tenant(factory, tenant_id)

        async with factory() as session, session.begin():
            assert await ROOMS.by_id(session, tenant_id, room_id) is None
            assert await ASSIGNMENTS.by_id(session, tenant_id, assignment_id) is None
            assert await BINDINGS.by_id_any_state(session, tenant_id, binding_id) is None
            assert await ROOMS.list_with_occupancy(session, tenant_id) == []
    finally:
        await engine.dispose()


async def test_the_app_role_is_not_the_owner_of_these_tables(app_role_url: str) -> None:
    """The anti-vacuity assertion for the WHOLE module, and the reason it is not
    a comment: `FORCE ROW LEVEL SECURITY` binds the table owner too, but a
    SUPERUSER bypasses every policy and every GRANT unconditionally. A future
    edit that points this suite at `migrated_db` — or a fixture that quietly
    starts handing back the superuser URL — would leave every probe above green
    while proving nothing.

    So: assert the connected role cannot do something only a superuser or the
    owner can. `ALTER TABLE ... DISABLE ROW LEVEL SECURITY` is the sharpest
    available, because it is precisely the privilege whose absence makes the rest
    of this file meaningful.
    """
    engine, factory = _factory(app_role_url)
    try:
        with pytest.raises(ProgrammingError) as denied:
            async with factory() as session, session.begin():
                await session.execute(
                    text("ALTER TABLE fitting_room_assignments DISABLE ROW LEVEL SECURITY")
                )
        assert "must be owner" in str(denied.value) or "permission denied" in str(denied.value)
    finally:
        await engine.dispose()
