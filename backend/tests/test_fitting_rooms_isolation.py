"""F36's three tables in the permanent cross-tenant isolation suite (AC10, AC11).

⚠ **Connected ONLY as the non-owner `boutique_app` role, over a `NullPool`
engine, via the `app_role_url` fixture — NEVER `migrated_db`.** The container
superuser bypasses RLS and every GRANT unconditionally.

⚠ **THE SWAP WAS RE-RUN WHEN F58 ADDED ITS ROW, AND THE PARAGRAPH THAT USED TO
STAND HERE — «all seven cases go RED» — WAS WRONG.** Measured, eight cases, the
whole module pointed at `migrated_db`: **four red, four green.** The claim was
never checked case by case, and the correction matters because the green four
are the shape it warned against.

RED, i.e. answered by the POLICY:
  * `..._no_reader_crosses_a_tenant...` — passes the FOREIGN tenant id as the
    repository argument, so with RLS bypassed the repositories' own
    `tenant_id ==` predicate matches and the foreign row comes back;
  * `..._foreign_ticket_pointer...` (F58) — reads with NO tenant predicate at
    all;
  * `..._cannot_reach_a_row_without_a_tenant_context` and
    `..._is_not_the_owner_of_these_tables` — both are about the connected role
    itself.

GREEN, i.e. answered by the repositories' redundant `tenant_id ==` predicate and
NOT by RLS — which is worth having and is not worth mislabelling:
  * `..._payload_read_never_joins_another_tenants_rows` and both writer probes
    pass their OWN tenant id with a foreign ROW id, so Python filters first;
  * `..._may_insert_select_and_update_all_three_tables` is a privilege
    assertion in a single tenant, and a superuser holding those privileges too
    is the correct result rather than a vacuous one.

**If a case is added here, decide which list it belongs in and say so.** A probe
that passes its own tenant id proves defence in depth; only a foreign tenant id
or a missing predicate reaches the policy.

**What makes fitting rooms worth a suite of their own rather than one more row in
`test_tenant_isolation.py`'s scan.** The assignment is the only table in the
product that names a member of staff, a room and a customer's booking in one row,
and the payload read joins SIX tables — `fitting_rooms`, `fitting_room_assignments`,
`staff_users`, `bookings`, `customers` and, since F58, `queue_tickets`. A join is
exactly where a missing policy hides: the driving table is filtered, the joined
one is not, and one boutique's bride's name arrives on another boutique's floor
with every row-count assertion still passing. So the payload read is probed here
directly, not only the writers.

**F58's row, and it is a new KIND of exposure rather than a sixth of the same.**
`fitting_room_assignments.queue_ticket_id` is a pointer with NO foreign key
behind it (house rule), so nothing in the schema stops an assignment in one
boutique carrying a ticket id belonging to another — a mis-typed id, a restored
backup, a future bulk import, a hostile request that guessed. The other five
joins reach rows the same tenant inserted; this one can be aimed anywhere. Every
seed below therefore carries a walk-in ticket, so the foreign-tenant-id probes
traverse the new join, and one case aims the pointer across a tenant boundary on
purpose and reads it back with NO tenant predicate at all — the only probe in
this module answered by the policy and nothing else.

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
from datetime import UTC, date, datetime

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
from app.db.repositories.queue_tickets import QueueTicketsRepository
from app.db.repositories.staff_users import StaffUsersRepository
from app.db.tenant import tenant_session
from app.errors import DomainNotFoundError
from app.floor.service import FloorService
from app.models.constants import StaffRole, VisitType

pytestmark = pytest.mark.db

LATER = datetime(2026, 8, 3, 10, 30, tzinfo=UTC)
DAY = date(2026, 8, 3)

ROOMS = FittingRoomsRepository()
ASSIGNMENTS = FittingRoomAssignmentsRepository()
BINDINGS = FittingAssignmentDressesRepository()
TICKETS = QueueTicketsRepository()


def _client_name(tenant_id: uuid.UUID) -> str:
    """DISTINCT PER TENANT, and that is what makes the join probes able to fail.

    With one literal name in both boutiques a leak would hand back a string the
    assertion was expecting anyway. `test_queue_isolation.py` learned this the
    same way and says so.
    """
    return f"לקוחה {tenant_id.hex[:8]}"


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
    """A staffer, a room, the walk-in she is serving, her assignment and one
    dress binding, in one tenant. Returns (staff, room, assignment, binding).

    ⚠ **The TICKET is F58's**, and it is seeded for every tenant rather than only
    where a case names it: it is what makes the payload probes traverse the sixth
    join instead of leaving `client_label` null and the new join untested by the
    cases that already exist. Its name is `_client_name(tenant_id)` — distinct
    per boutique on purpose.

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
        ticket = await TICKETS.insert(
            session,
            tenant_id=tenant_id,
            queue_day=DAY,
            name=_client_name(tenant_id),
            phone=f"+9725{uuid.uuid4().int % 10**8:08d}",
            visit_type=VisitType.BRIDE.value,
        )
        assignment = await ASSIGNMENTS.claim(
            session,
            tenant_id,
            room_id=room.id,
            staff_id=staff.id,
            booking_id=None,
            queue_ticket_id=ticket.id,
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
        # F58's sixth join: her tile names HER walk-in and not the other
        # boutique's, which is only an assertion because `_client_name` differs
        # per tenant.
        assert [row.client_label for row in rows] == [_client_name(here)]
    finally:
        await engine.dispose()


async def test_a_foreign_ticket_pointer_on_a_local_assignment_resolves_to_nothing(
    app_role_url: str,
) -> None:
    """⚠⚠ **F58's ROW, AND THE ONLY PROBE IN THIS MODULE ANSWERED BY THE POLICY
    ALONE.**

    Tenant B's assignment is made to carry tenant A's `queue_ticket_id`. There is
    no foreign key to prevent it and F58 deliberately added none, so this is not
    a contrived state — it is the state a mis-typed id, a restored backup or a
    bulk import produces, and the pointer is the one join in the chain that can
    be aimed outside the tenant that owns the row holding it.

    **Two assertions, and the difference is the whole point of the case.**

    The repository read carries `QueueTicket.tenant_id == tenant_id` like every
    other join in `_occupancy_rows`, so `client_label is None` there proves only
    that Python filtered — it is green with the policy switched off entirely.
    That is defence in depth and it is asserted as such.

    The RAW join below carries NO tenant predicate on either side. `a` is B's own
    row and is visible; `q` is A's and is not, so the inner join yields nothing —
    and the ONLY thing making that true is `queue_tickets`' policy. ⚠ VACUITY
    MUTATION RUN AND RESTORED: pointing this case at `migrated_db` reds it,
    because the container superuser bypasses RLS, sees A's ticket, and A's
    customer's name arrives on B's floor. That is the module's rule (docstring)
    achieved here by dropping the predicate rather than by passing the foreign
    tenant id, because a pointer aimed across a boundary has no foreign tenant id
    to pass — the caller supplies its own.
    """
    engine, factory = _factory(app_role_url)
    here, elsewhere = uuid.uuid4(), uuid.uuid4()
    try:
        await _seed_tenant(factory, elsewhere)
        my_staff, my_room, _, _ = await _seed_tenant(factory, here)
        async with tenant_session(factory, elsewhere) as session:
            theirs = (await session.execute(text("SELECT id FROM queue_tickets"))).scalar_one()

        # B frees her room and re-claims it, this time pointing at A's ticket.
        async with tenant_session(factory, here) as session:
            mine = (
                await session.execute(text("SELECT id FROM fitting_room_assignments"))
            ).scalar_one()
            await ASSIGNMENTS.release(session, here, mine, at=LATER)
            await ASSIGNMENTS.claim(
                session,
                here,
                room_id=my_room,
                staff_id=my_staff,
                booking_id=None,
                queue_ticket_id=theirs,
            )

        async with tenant_session(factory, here) as session:
            rows = await ROOMS.list_with_occupancy(session, here)
            leaked = (
                (
                    await session.execute(
                        text(
                            "SELECT q.name FROM fitting_room_assignments a "
                            "JOIN queue_tickets q ON q.id = a.queue_ticket_id "
                            "WHERE q.deleted_at IS NULL AND a.released_at IS NULL"
                        )
                    )
                )
                .scalars()
                .all()
            )

        assert [row.client_label for row in rows] == [None]
        assert list(leaked) == []
        assert _client_name(elsewhere) not in str(rows)
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
