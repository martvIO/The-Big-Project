"""F36's three repositories and the payload read, against real Postgres as the
non-owner app role (`boutique_app`).

**Six of these cases cannot exist without a real server.** A monkeypatched
repository never raises `IntegrityError`, never takes a row lock, never blocks an
`ON CONFLICT` against an uncommitted delete and never lets `xmax` mean anything —
and those are precisely the mechanisms F36 exists to install. The two partial
unique indexes are not enforced by a single line of application code.

⚠ **Every row this module COMMITS holds `owner`, never a floor role**, and that
is a hard rule rather than a preference — `test_floor_db.py`'s rule, verbatim,
for the same reason. `migrated_db` and `app_role_url` are `scope="session"` so
one cluster is shared by every db-marked module, and pytest collects files
alphabetically: `test_fitting_rooms_repositories.py` sorts BEFORE
`test_migrations.py`, where `test_adding_the_role_check_validates_existing_rows`
re-adds 0011's TWO-value CHECK over whatever rows exist. A committed `reception`
row reddens a test that has nothing to do with fitting rooms and whose failure
names 0011's constraint. Nothing here asserts anything about a role, so the seed
role costs nothing.

Every test mints its own tenant id: the cluster is session-scoped and nothing
here truncates.
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.db.repositories.bookings import BookingsRepository
from app.db.repositories.dress_variants import DressVariantsRepository
from app.db.repositories.dresses import DressesRepository
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
from app.models.booking import Booking
from app.models.constants import BookingStatus, StaffRole
from app.models.customer import Customer
from app.models.dress import Dress
from app.models.dress_variant import DressVariant

pytestmark = pytest.mark.db

# Frozen module constants rather than a real clock: every assertion below is an
# equality on a stored value, and now() would make them all approximate.
NOW = datetime(2026, 8, 3, 9, 12, tzinfo=UTC)
LATER = datetime(2026, 8, 3, 10, 30, tzinfo=UTC)
# 09:00 Asia/Jerusalem on 2026-08-03 is 06:00Z (IDT, UTC+3). The client picker's
# window is a Jerusalem calendar day, so the bounds are spelled in UTC here
# exactly as the caller will compute them.
DAY_START = datetime(2026, 8, 2, 21, 0, tzinfo=UTC)
DAY_END = datetime(2026, 8, 3, 21, 0, tzinfo=UTC)
MORNING = datetime(2026, 8, 3, 6, 0, tzinfo=UTC)

ROOMS = FittingRoomsRepository()
ASSIGNMENTS = FittingRoomAssignmentsRepository()
BINDINGS = FittingAssignmentDressesRepository()


def _factory(app_role_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    return (
        engine := create_async_engine(app_role_url, poolclass=NullPool),
        async_sessionmaker(engine, expire_on_commit=False),
    )


async def _seed_staff(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    *,
    display_name: str = "Staff",
) -> uuid.UUID:
    """`owner` always — see the module docstring. Nothing here reads the role."""
    async with tenant_session(factory, tenant_id) as session:
        staff = await StaffUsersRepository().insert(
            session,
            tenant_id=tenant_id,
            email=f"fitting-{uuid.uuid4().hex[:10]}@bella.example",
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
    is_active: bool = True,
) -> uuid.UUID:
    async with tenant_session(factory, tenant_id) as session:
        room = await ROOMS.insert(
            session, tenant_id, label=label, sort_order=sort_order, is_active=is_active
        )
        return room.id


async def _seed_booking(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    *,
    customer_name: str = "מיכל",
    starts_at: datetime = MORNING,
    checked_in: bool = True,
    status: str = BookingStatus.CONFIRMED.value,
    seat_index: int = 1,
) -> tuple[uuid.UUID, uuid.UUID]:
    """(booking_id, customer_id). Written through the ORM rather than through
    BookingsRepository.insert, which wants a whole slot-claim context this module
    has no use for."""
    async with tenant_session(factory, tenant_id) as session:
        customer = Customer(
            tenant_id=tenant_id, phone=f"+9725{uuid.uuid4().int % 10**8:08d}", name=customer_name
        )
        session.add(customer)
        await session.flush()
        booking = Booking(
            tenant_id=tenant_id,
            customer_id=customer.id,
            appointment_type_id=uuid.uuid4(),
            starts_at=starts_at,
            seat_index=seat_index,
            status=status,
            terms_version_accepted=1,
            terms_accepted_at=NOW,
            appointment_type_name="מדידה",
            checked_in_at=NOW if checked_in else None,
        )
        session.add(booking)
        await session.flush()
        return booking.id, customer.id


# --- FittingRoomsRepository: the registry ---


async def test_insert_then_by_id_round_trips(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        room_id = await _seed_room(factory, tenant_id, label="הבמה", sort_order=3, is_active=False)
        async with tenant_session(factory, tenant_id) as session:
            row = await ROOMS.by_id(session, tenant_id, room_id)
        assert row is not None
        assert (row.label, row.sort_order, row.is_active) == ("הבמה", 3, False)
    finally:
        await engine.dispose()


async def test_by_id_is_one_indistinguishable_miss_for_absent_deleted_and_foreign(
    app_role_url: str,
) -> None:
    """An unknown id, a soft-deleted room and another tenant's room are ONE
    answer. The third leg is the one worth writing down: RLS already hides the
    foreign row, and the explicit `tenant_id` predicate is redundant
    defence-in-depth on top of it — see the repository docstring for what that
    redundancy can and cannot be proved by."""
    engine, factory = _factory(app_role_url)
    tenant_id, other_tenant = uuid.uuid4(), uuid.uuid4()
    try:
        deleted_id = await _seed_room(factory, tenant_id)
        async with tenant_session(factory, tenant_id) as session:
            assert await ROOMS.soft_delete(session, tenant_id, deleted_id) is True
        foreign_id = await _seed_room(factory, other_tenant)

        async with tenant_session(factory, tenant_id) as session:
            assert await ROOMS.by_id(session, tenant_id, uuid.uuid4()) is None
            assert await ROOMS.by_id(session, tenant_id, deleted_id) is None
            assert await ROOMS.by_id(session, tenant_id, foreign_id) is None
    finally:
        await engine.dispose()


async def test_list_live_ships_inactive_rooms_too_in_display_order(app_role_url: str) -> None:
    """Inactive rooms DO ship — the panel greys them, because a room a staffer
    cannot find is worse than one she can see is out of service. Only
    `deleted_at` removes a row from this read.

    The order is (sort_order, created_at) and the tiebreak is the point: both
    rooms below carry the default sort_order, which is the common case for a
    boutique that never reorders, so without `created_at` the tiles could swap
    places on a 5-second repaint."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        first = await _seed_room(factory, tenant_id, label="first")
        second = await _seed_room(factory, tenant_id, label="second")
        front = await _seed_room(factory, tenant_id, label="front", sort_order=-1)
        inactive = await _seed_room(factory, tenant_id, label="broken mirror", is_active=False)
        gone = await _seed_room(factory, tenant_id, label="gone")
        async with tenant_session(factory, tenant_id) as session:
            await ROOMS.soft_delete(session, tenant_id, gone)

        async with tenant_session(factory, tenant_id) as session:
            rows = await ROOMS.list_live(session, tenant_id)
        assert [row.id for row in rows] == [front, first, second, inactive]
    finally:
        await engine.dispose()


async def test_update_writes_only_what_it_is_given(app_role_url: str) -> None:
    """`None` means NOT SUPPLIED, never "clear it" — `CustomersRepository`'s
    rule. The registry dialog's three controls are independent, so a
    sort-order-only patch must leave the label alone. Supplying nothing is a
    legal no-op that still answers the live row."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        room_id = await _seed_room(factory, tenant_id, label="חדר 1", sort_order=0)
        async with tenant_session(factory, tenant_id) as session:
            row = await ROOMS.update(session, tenant_id, room_id, sort_order=5)
        assert row is not None
        assert (row.label, row.sort_order, row.is_active) == ("חדר 1", 5, True)

        async with tenant_session(factory, tenant_id) as session:
            row = await ROOMS.update(session, tenant_id, room_id)
        assert row is not None
        assert (row.label, row.sort_order) == ("חדר 1", 5)

        async with tenant_session(factory, tenant_id) as session:
            row = await ROOMS.update(session, tenant_id, room_id, label="הבמה", is_active=False)
        assert row is not None
        assert (row.label, row.sort_order, row.is_active) == ("הבמה", 5, False)

        async with tenant_session(factory, tenant_id) as session:
            assert await ROOMS.update(session, tenant_id, uuid.uuid4(), label="x") is None
    finally:
        await engine.dispose()


async def test_soft_delete_answers_false_the_second_time(app_role_url: str) -> None:
    """`deleted_at IS NULL` in the predicate is what makes a second call answer
    False rather than re-stamp the timestamp — `StaffUsersRepository.soft_delete`
    verbatim."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        room_id = await _seed_room(factory, tenant_id)
        async with tenant_session(factory, tenant_id) as session:
            assert await ROOMS.soft_delete(session, tenant_id, room_id) is True
        async with tenant_session(factory, tenant_id) as session:
            assert await ROOMS.soft_delete(session, tenant_id, room_id) is False
    finally:
        await engine.dispose()


async def test_by_id_for_update_answers_the_row_it_locks(app_role_url: str) -> None:
    """The lock's presence cannot be observed from one session, so what is
    asserted here is the shape: same predicate as `by_id`, same answers, and a
    row that came back through `SELECT ... FOR UPDATE`. The interleave that
    proves the lock actually serialises a delete against a claim is Task 6's
    (AC17) and needs two concurrent sessions."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        room_id = await _seed_room(factory, tenant_id, label="חדר 2")
        async with tenant_session(factory, tenant_id) as session:
            row = await ROOMS.by_id_for_update(session, tenant_id, room_id)
            assert row is not None
            assert row.label == "חדר 2"
            assert await ROOMS.by_id_for_update(session, tenant_id, uuid.uuid4()) is None
    finally:
        await engine.dispose()


# --- FittingRoomAssignmentsRepository: claim, release, handover ---


async def test_a_claim_is_visible_to_both_occupancy_reads(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        room_id = await _seed_room(factory, tenant_id)
        staff_id = await _seed_staff(factory, tenant_id)
        booking_id, _ = await _seed_booking(factory, tenant_id)
        async with tenant_session(factory, tenant_id) as session:
            row = await ASSIGNMENTS.claim(
                session, tenant_id, room_id=room_id, staff_id=staff_id, booking_id=booking_id
            )
            assignment_id = row.id
        assert row.released_at is None

        async with tenant_session(factory, tenant_id) as session:
            occupant = await ASSIGNMENTS.occupant_of_room(session, tenant_id, room_id)
            room_of = await ASSIGNMENTS.room_of_staff(session, tenant_id, staff_id)
            assert await ASSIGNMENTS.has_active_for_room(session, tenant_id, room_id) is True
        assert occupant is not None and occupant.id == assignment_id
        assert room_of is not None and room_of.fitting_room_id == room_id
    finally:
        await engine.dispose()


async def test_a_second_claim_on_one_room_violates_the_room_index(app_role_url: str) -> None:
    """The structural guarantee the whole feature exists to give, and there is
    no application code enforcing it — the INSERT either violates the index or
    it does not. This case is IMPOSSIBLE to write against a fake repository."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        room_id = await _seed_room(factory, tenant_id)
        first = await _seed_staff(factory, tenant_id)
        second = await _seed_staff(factory, tenant_id)
        async with tenant_session(factory, tenant_id) as session:
            await ASSIGNMENTS.claim(
                session, tenant_id, room_id=room_id, staff_id=first, booking_id=None
            )
        with pytest.raises(IntegrityError) as caught:
            async with tenant_session(factory, tenant_id) as session:
                await ASSIGNMENTS.claim(
                    session, tenant_id, room_id=room_id, staff_id=second, booking_id=None
                )
        # The service discriminates on exactly this, and only after resolving
        # idempotence — see the repository's module constants. Read through
        # `violated_index`, NOT off `exc.orig`: the spec's spelling is wrong and
        # returns None for every violation, which would make this a 500.
        assert violated_index(caught.value) == ROOM_ACTIVE_INDEX
    finally:
        await engine.dispose()


async def test_a_second_claim_by_one_staffer_violates_the_staff_index(app_role_url: str) -> None:
    """One active room per worker — the 2026-07-31 ruling's index. This is what
    makes the staff card's `occupied` a fact rather than a guess."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        first_room = await _seed_room(factory, tenant_id, label="A")
        second_room = await _seed_room(factory, tenant_id, label="B")
        staff_id = await _seed_staff(factory, tenant_id)
        async with tenant_session(factory, tenant_id) as session:
            await ASSIGNMENTS.claim(
                session, tenant_id, room_id=first_room, staff_id=staff_id, booking_id=None
            )
        with pytest.raises(IntegrityError) as caught:
            async with tenant_session(factory, tenant_id) as session:
                await ASSIGNMENTS.claim(
                    session, tenant_id, room_id=second_room, staff_id=staff_id, booking_id=None
                )
        assert violated_index(caught.value) == STAFF_ACTIVE_INDEX
    finally:
        await engine.dispose()


async def test_active_for_answers_the_idempotent_reclaim(app_role_url: str) -> None:
    """The request-keyed read that resolves idempotence BEFORE the constraint
    name is ever consulted. A re-claim of the room she already holds violates
    BOTH indexes at once and Postgres reports whichever has the lower OID, so a
    branch keyed on the constraint name would be an artefact of migration
    ordering. This read is keyed on (room, staff) and is deterministic."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        room_id = await _seed_room(factory, tenant_id)
        staff_id = await _seed_staff(factory, tenant_id)
        other_room = await _seed_room(factory, tenant_id, label="other")
        other_staff = await _seed_staff(factory, tenant_id)
        async with tenant_session(factory, tenant_id) as session:
            claimed = await ASSIGNMENTS.claim(
                session, tenant_id, room_id=room_id, staff_id=staff_id, booking_id=None
            )
        async with tenant_session(factory, tenant_id) as session:
            hit = await ASSIGNMENTS.active_for(session, tenant_id, room_id, staff_id)
            wrong_room = await ASSIGNMENTS.active_for(session, tenant_id, other_room, staff_id)
            wrong_staff = await ASSIGNMENTS.active_for(session, tenant_id, room_id, other_staff)
        assert hit is not None and hit.id == claimed.id
        assert wrong_room is None
        assert wrong_staff is None
    finally:
        await engine.dispose()


async def test_release_stamps_the_callers_clock_and_frees_the_room_at_once(
    app_role_url: str,
) -> None:
    """`released_at` comes from the service's injectable clock, so this is an
    EQUALITY and not a range — `created_at` is DB-generated and could not be
    asserted this way, which is D2's reason for having no `assigned_at` column.

    The re-claim in the same breath is the predicate's whole point: the two
    unique indexes are partial on `released_at IS NULL`, so a released room is
    immediately re-claimable and the panel's next tick shows it free."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        room_id = await _seed_room(factory, tenant_id)
        staff_id = await _seed_staff(factory, tenant_id)
        other_staff = await _seed_staff(factory, tenant_id)
        async with tenant_session(factory, tenant_id) as session:
            claimed = await ASSIGNMENTS.claim(
                session, tenant_id, room_id=room_id, staff_id=staff_id, booking_id=None
            )
        async with tenant_session(factory, tenant_id) as session:
            wrote, row = await ASSIGNMENTS.release(session, tenant_id, claimed.id, at=LATER)
        assert wrote is True
        assert row is not None and row.released_at == LATER

        async with tenant_session(factory, tenant_id) as session:
            assert await ASSIGNMENTS.has_active_for_room(session, tenant_id, room_id) is False
            assert await ASSIGNMENTS.occupant_of_room(session, tenant_id, room_id) is None
            assert await ASSIGNMENTS.room_of_staff(session, tenant_id, staff_id) is None
            again = await ASSIGNMENTS.claim(
                session, tenant_id, room_id=room_id, staff_id=other_staff, booking_id=None
            )
        assert again.id != claimed.id
    finally:
        await engine.dispose()


async def test_a_second_release_keeps_the_first_timestamp_and_reports_no_write(
    app_role_url: str,
) -> None:
    """Rowcount 0 with a live row back is NOT an error: she wanted the room
    free, the room is free. Both halves of the tuple are asserted because they
    fail independently — the `wrote` flag comes off the `.returning()` scalar and
    the row comes off the unconditional re-read."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        room_id = await _seed_room(factory, tenant_id)
        staff_id = await _seed_staff(factory, tenant_id)
        async with tenant_session(factory, tenant_id) as session:
            claimed = await ASSIGNMENTS.claim(
                session, tenant_id, room_id=room_id, staff_id=staff_id, booking_id=None
            )
        async with tenant_session(factory, tenant_id) as session:
            await ASSIGNMENTS.release(session, tenant_id, claimed.id, at=NOW)
        async with tenant_session(factory, tenant_id) as session:
            wrote, row = await ASSIGNMENTS.release(session, tenant_id, claimed.id, at=LATER)
        assert wrote is False
        assert row is not None and row.released_at == NOW
    finally:
        await engine.dispose()


async def test_release_of_an_unknown_assignment_answers_no_row_at_all(app_role_url: str) -> None:
    """`(False, None)` means gone — another tenant's, soft-deleted, or never
    existed — and it is what the service turns into a 404. It is a different
    answer from `(False, row)` above, which is a 200."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        async with tenant_session(factory, tenant_id) as session:
            wrote, row = await ASSIGNMENTS.release(session, tenant_id, uuid.uuid4(), at=NOW)
        assert (wrote, row) == (False, None)
    finally:
        await engine.dispose()


async def test_handover_moves_the_holder_and_leaves_the_clock_alone(app_role_url: str) -> None:
    """ONE statement, which is why the dress bindings survive for free — the
    alternative (release the old assignment, insert a new one) would have to copy
    every child row, and would open a window in which the room is momentarily
    free and a third staffer can take it.

    `created_at` and the assignment ID are both asserted unchanged: the elapsed
    time on the card is the CLIENT's time in the room, and F37's alert pointer
    has to stay valid across a change of hands."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        room_id = await _seed_room(factory, tenant_id)
        holder = await _seed_staff(factory, tenant_id, display_name="דנה")
        colleague = await _seed_staff(factory, tenant_id, display_name="נועה")
        async with tenant_session(factory, tenant_id) as session:
            claimed = await ASSIGNMENTS.claim(
                session, tenant_id, room_id=room_id, staff_id=holder, booking_id=None
            )
            claimed_at = claimed.created_at
        async with tenant_session(factory, tenant_id) as session:
            wrote, row = await ASSIGNMENTS.handover(
                session, tenant_id, claimed.id, new_staff_id=colleague
            )
        assert wrote is True
        assert row is not None
        assert row.id == claimed.id
        assert row.staff_user_id == colleague
        assert row.created_at == claimed_at

        async with tenant_session(factory, tenant_id) as session:
            assert await ASSIGNMENTS.room_of_staff(session, tenant_id, holder) is None
            moved = await ASSIGNMENTS.room_of_staff(session, tenant_id, colleague)
        assert moved is not None and moved.id == claimed.id
    finally:
        await engine.dispose()


async def test_handover_to_an_occupied_colleague_violates_the_staff_index(
    app_role_url: str,
) -> None:
    """The second index earning its keep on a path that is not the claim. The
    service turns this into a 409 naming her current room."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        first_room = await _seed_room(factory, tenant_id, label="A")
        second_room = await _seed_room(factory, tenant_id, label="B")
        holder = await _seed_staff(factory, tenant_id)
        busy = await _seed_staff(factory, tenant_id)
        async with tenant_session(factory, tenant_id) as session:
            claimed = await ASSIGNMENTS.claim(
                session, tenant_id, room_id=first_room, staff_id=holder, booking_id=None
            )
            await ASSIGNMENTS.claim(
                session, tenant_id, room_id=second_room, staff_id=busy, booking_id=None
            )
        with pytest.raises(IntegrityError) as caught:
            async with tenant_session(factory, tenant_id) as session:
                await ASSIGNMENTS.handover(session, tenant_id, claimed.id, new_staff_id=busy)
        assert violated_index(caught.value) == STAFF_ACTIVE_INDEX
    finally:
        await engine.dispose()


async def test_handover_of_a_released_assignment_answers_no_write(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        room_id = await _seed_room(factory, tenant_id)
        holder = await _seed_staff(factory, tenant_id)
        colleague = await _seed_staff(factory, tenant_id)
        async with tenant_session(factory, tenant_id) as session:
            claimed = await ASSIGNMENTS.claim(
                session, tenant_id, room_id=room_id, staff_id=holder, booking_id=None
            )
            await ASSIGNMENTS.release(session, tenant_id, claimed.id, at=NOW)
        async with tenant_session(factory, tenant_id) as session:
            wrote, row = await ASSIGNMENTS.handover(
                session, tenant_id, claimed.id, new_staff_id=colleague
            )
        assert wrote is False
        assert row is None
    finally:
        await engine.dispose()


# --- FittingAssignmentDressesRepository: the bindings ---


async def _claimed(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID
) -> tuple[uuid.UUID, uuid.UUID]:
    """(assignment_id, staff_id) for a fresh room."""
    room_id = await _seed_room(factory, tenant_id)
    staff_id = await _seed_staff(factory, tenant_id)
    async with tenant_session(factory, tenant_id) as session:
        row = await ASSIGNMENTS.claim(
            session, tenant_id, room_id=room_id, staff_id=staff_id, booking_id=None
        )
        return row.id, staff_id


async def test_a_second_add_of_one_dress_is_a_no_op_success(app_role_url: str) -> None:
    """A concurrent double-add is a SUCCESS, not a 409: two staffers tapping the
    same gown both want it in the room, and it is in the room. `(xmax = 0)` is
    what distinguishes the insert from the no-op, and it is a fact only a real
    server can produce."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        assignment_id, _ = await _claimed(factory, tenant_id)
        dress_id = uuid.uuid4()
        async with tenant_session(factory, tenant_id) as session:
            wrote, first = await BINDINGS.add(
                session,
                tenant_id,
                assignment_id=assignment_id,
                dress_id=dress_id,
                dress_name="ורוניק",
                dress_size="38",
            )
        assert wrote is True
        async with tenant_session(factory, tenant_id) as session:
            wrote, again = await BINDINGS.add(
                session,
                tenant_id,
                assignment_id=assignment_id,
                dress_id=dress_id,
                dress_name="ורוניק",
                dress_size="40",
            )
        assert wrote is False
        assert again.id == first.id
        # The no-op branch touches updated_at and nothing else: the SNAPSHOT the
        # room was given must not be rewritten by a second tap.
        assert again.dress_size == "38"
    finally:
        await engine.dispose()


async def test_a_removed_dress_can_be_carried_back_in(app_role_url: str) -> None:
    """The partial predicate on the third unique index is what makes this
    possible: the removed row leaves the index, so the re-add is a clean INSERT
    rather than a violation."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        assignment_id, staff_id = await _claimed(factory, tenant_id)
        dress_id = uuid.uuid4()
        async with tenant_session(factory, tenant_id) as session:
            _, binding = await BINDINGS.add(
                session,
                tenant_id,
                assignment_id=assignment_id,
                dress_id=dress_id,
                dress_name="ורוניק",
                dress_size="38",
            )
        async with tenant_session(factory, tenant_id) as session:
            assert (
                await BINDINGS.remove(
                    session,
                    tenant_id,
                    assignment_id=assignment_id,
                    binding_id=binding.id,
                    actor_id=staff_id,
                    at=LATER,
                )
                is True
            )
        async with tenant_session(factory, tenant_id) as session:
            wrote, back = await BINDINGS.add(
                session,
                tenant_id,
                assignment_id=assignment_id,
                dress_id=dress_id,
                dress_name="ורוניק",
                dress_size="40",
            )
        assert wrote is True
        assert back.id != binding.id
        assert back.dress_size == "40"
    finally:
        await engine.dispose()


async def test_remove_stamps_both_deleted_at_and_removed_by(app_role_url: str) -> None:
    """The soft-deleted row IS the audit record, which is why no
    FITTING_DRESS_REMOVED action exists. Without `removed_by` it answers what
    left the room and when, and cannot answer who took it out — the question a
    boutique tracking gowns keeps the trail for.

    A second remove answers False rather than re-stamping, and a remove aimed at
    another assignment's binding answers False too."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        assignment_id, staff_id = await _claimed(factory, tenant_id)
        other_assignment, _ = await _claimed(factory, tenant_id)
        async with tenant_session(factory, tenant_id) as session:
            _, binding = await BINDINGS.add(
                session,
                tenant_id,
                assignment_id=assignment_id,
                dress_id=uuid.uuid4(),
                dress_name="ורוניק",
                dress_size=None,
            )
        async with tenant_session(factory, tenant_id) as session:
            assert (
                await BINDINGS.remove(
                    session,
                    tenant_id,
                    assignment_id=other_assignment,
                    binding_id=binding.id,
                    actor_id=staff_id,
                    at=LATER,
                )
                is False
            )
            assert (
                await BINDINGS.remove(
                    session,
                    tenant_id,
                    assignment_id=assignment_id,
                    binding_id=binding.id,
                    actor_id=staff_id,
                    at=LATER,
                )
                is True
            )
            assert (
                await BINDINGS.remove(
                    session,
                    tenant_id,
                    assignment_id=assignment_id,
                    binding_id=binding.id,
                    actor_id=staff_id,
                    at=LATER,
                )
                is False
            )
        async with tenant_session(factory, tenant_id) as session:
            stored = await BINDINGS.by_id_any_state(session, tenant_id, binding.id)
        assert stored is not None
        assert stored.deleted_at == LATER
        assert stored.removed_by == staff_id
    finally:
        await engine.dispose()


async def test_by_assignment_ids_skips_removed_bindings_and_short_circuits_on_empty(
    app_role_url: str,
) -> None:
    """The payload's SECOND statement, and the empty input is the branch that
    matters: an unoccupied boutique must not pay a round trip for `IN ()`."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        assignment_id, staff_id = await _claimed(factory, tenant_id)
        other_assignment, _ = await _claimed(factory, tenant_id)
        async with tenant_session(factory, tenant_id) as session:
            _, kept = await BINDINGS.add(
                session,
                tenant_id,
                assignment_id=assignment_id,
                dress_id=uuid.uuid4(),
                dress_name="ורוניק",
                dress_size="38",
            )
            _, dropped = await BINDINGS.add(
                session,
                tenant_id,
                assignment_id=assignment_id,
                dress_id=uuid.uuid4(),
                dress_name="אלין",
                dress_size=None,
            )
            await BINDINGS.remove(
                session,
                tenant_id,
                assignment_id=assignment_id,
                binding_id=dropped.id,
                actor_id=staff_id,
                at=LATER,
            )
        async with tenant_session(factory, tenant_id) as session:
            found = await BINDINGS.by_assignment_ids(
                session, tenant_id, [assignment_id, other_assignment]
            )
            assert await BINDINGS.by_assignment_ids(session, tenant_id, []) == {}
        assert list(found) == [assignment_id]
        assert [row.id for row in found[assignment_id]] == [kept.id]
    finally:
        await engine.dispose()


# --- the payload read: one outer-join chain from rooms ---


async def test_the_payload_carries_every_live_room_free_and_occupied(app_role_url: str) -> None:
    """Driving from `fitting_rooms` with five LEFT joins, so an unoccupied room
    still produces a row and an occupied one carries its holder and its client."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        occupied = await _seed_room(factory, tenant_id, label="חדר 1", sort_order=0)
        free = await _seed_room(factory, tenant_id, label="חדר 2", sort_order=1)
        staff_id = await _seed_staff(factory, tenant_id, display_name="דנה")
        booking_id, _ = await _seed_booking(factory, tenant_id, customer_name="מיכל")
        async with tenant_session(factory, tenant_id) as session:
            claimed = await ASSIGNMENTS.claim(
                session, tenant_id, room_id=occupied, staff_id=staff_id, booking_id=booking_id
            )

        async with tenant_session(factory, tenant_id) as session:
            rows = await ROOMS.list_with_occupancy(session, tenant_id)
        assert [row.room_id for row in rows] == [occupied, free]
        first, second = rows
        assert first.assignment_id == claimed.id
        assert first.staff_user_id == staff_id
        assert first.staff_display_name == "דנה"
        assert first.staff_role == StaffRole.OWNER.value
        assert first.booking_id == booking_id
        assert first.client_label == "מיכל"
        assert first.assigned_at == claimed.created_at
        assert second.assignment_id is None
        assert second.client_label is None
        assert second.assigned_at is None
    finally:
        await engine.dispose()


async def test_a_released_room_stops_being_occupied_on_the_payload(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        room_id = await _seed_room(factory, tenant_id)
        staff_id = await _seed_staff(factory, tenant_id)
        async with tenant_session(factory, tenant_id) as session:
            claimed = await ASSIGNMENTS.claim(
                session, tenant_id, room_id=room_id, staff_id=staff_id, booking_id=None
            )
            await ASSIGNMENTS.release(session, tenant_id, claimed.id, at=LATER)
        async with tenant_session(factory, tenant_id) as session:
            rows = await ROOMS.list_with_occupancy(session, tenant_id)
        assert [row.assignment_id for row in rows] == [None]
    finally:
        await engine.dispose()


async def test_a_soft_deleted_holder_still_names_the_tile(app_role_url: str) -> None:
    """THE GHOST HOLDER. F51's staff removal has no interaction rule with an open
    assignment and F36 does not add one — freeing rooms out from under people is
    a cross-feature edit this feature should not own. So the consequence is
    pinned instead of discovered: `list_live` drops her card, the rooms join
    still yields an occupied tile, and the `staff_users` join carries NO
    `deleted_at` filter so the tile can still say who is in there.

    Adding that filter is the mutation, and it reddens exactly this test."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        room_id = await _seed_room(factory, tenant_id)
        staff_id = await _seed_staff(factory, tenant_id, display_name="דנה")
        async with tenant_session(factory, tenant_id) as session:
            await ASSIGNMENTS.claim(
                session, tenant_id, room_id=room_id, staff_id=staff_id, booking_id=None
            )
            assert await StaffUsersRepository().soft_delete(session, tenant_id, staff_id) is True

        async with tenant_session(factory, tenant_id) as session:
            rows = await ROOMS.list_with_occupancy(session, tenant_id)
            cards = await StaffUsersRepository().list_live(session, tenant_id)
        assert [card.id for card in cards] == []
        assert len(rows) == 1
        assert rows[0].assignment_id is not None
        assert rows[0].staff_display_name == "דנה"
    finally:
        await engine.dispose()


async def test_a_deleted_booking_renders_an_anonymous_visit(app_role_url: str) -> None:
    """A swept appointment takes the label with it and leaves the tile. The
    booking join is the one carrying `status <> 'cancelled'` as well, so a
    cancelled booking answers the same way."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        room_id = await _seed_room(factory, tenant_id)
        staff_id = await _seed_staff(factory, tenant_id)
        booking_id, _ = await _seed_booking(factory, tenant_id, customer_name="מיכל")
        async with tenant_session(factory, tenant_id) as session:
            await ASSIGNMENTS.claim(
                session, tenant_id, room_id=room_id, staff_id=staff_id, booking_id=booking_id
            )
            booking = await BookingsRepository().by_id(session, tenant_id, booking_id)
            assert booking is not None
            booking.deleted_at = LATER

        async with tenant_session(factory, tenant_id) as session:
            rows = await ROOMS.list_with_occupancy(session, tenant_id)
        assert rows[0].assignment_id is not None
        assert rows[0].booking_id == booking_id
        assert rows[0].client_label is None
    finally:
        await engine.dispose()


async def test_a_deleted_customer_renders_an_anonymous_visit(app_role_url: str) -> None:
    """⚠ An Amendment 13 erasure is about the PERSON, not her appointment.

    F20 soft-deleting `customers` while the booking row survives is the likeliest
    shape, and without `customers.deleted_at IS NULL` on the last join her name
    keeps rendering on a payload five roles can open AFTER the platform told her
    it was erased. Dropping that one conjunct reddens this and leaves the
    deleted-BOOKING case above green, which is exactly the distinction."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        room_id = await _seed_room(factory, tenant_id)
        staff_id = await _seed_staff(factory, tenant_id)
        booking_id, customer_id = await _seed_booking(factory, tenant_id, customer_name="מיכל")
        async with tenant_session(factory, tenant_id) as session:
            await ASSIGNMENTS.claim(
                session, tenant_id, room_id=room_id, staff_id=staff_id, booking_id=booking_id
            )
            customer = await session.get(Customer, customer_id)
            assert customer is not None
            customer.deleted_at = LATER

        async with tenant_session(factory, tenant_id) as session:
            rows = await ROOMS.list_with_occupancy(session, tenant_id)
        assert rows[0].assignment_id is not None
        assert rows[0].booking_id == booking_id
        assert rows[0].client_label is None
    finally:
        await engine.dispose()


async def test_the_payload_never_crosses_a_tenant(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id, other_tenant = uuid.uuid4(), uuid.uuid4()
    try:
        mine = await _seed_room(factory, tenant_id, label="mine")
        await _seed_room(factory, other_tenant, label="theirs")
        async with tenant_session(factory, tenant_id) as session:
            rows = await ROOMS.list_with_occupancy(session, tenant_id)
        assert [row.room_id for row in rows] == [mine]
    finally:
        await engine.dispose()


# --- the two picker reads (D16) ---


async def test_the_client_picker_lists_only_todays_checked_in_bookings(app_role_url: str) -> None:
    """The people physically IN THE BUILDING, which is the same minimisation
    argument D9 makes for the payload — never the day book. `checked_in_at IS
    NOT NULL` is the whole filter that makes the difference, and a cancelled or
    swept booking is out on the same terms every occupancy query uses."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        # Distinct seat indexes: three of these share a start time, and
        # idx_bookings_slot_seat_unique is (tenant_id, starts_at, seat_index).
        here, _ = await _seed_booking(
            factory, tenant_id, starts_at=MORNING, checked_in=True, seat_index=1
        )
        await _seed_booking(factory, tenant_id, starts_at=MORNING, checked_in=False, seat_index=2)
        await _seed_booking(
            factory,
            tenant_id,
            starts_at=MORNING,
            checked_in=True,
            status=BookingStatus.CANCELLED.value,
            seat_index=3,
        )
        await _seed_booking(
            factory,
            tenant_id,
            starts_at=datetime(2026, 8, 4, 6, 0, tzinfo=UTC),
            checked_in=True,
        )
        async with tenant_session(factory, tenant_id) as session:
            rows = await BookingsRepository().list_checked_in_between(
                session, tenant_id, from_instant=DAY_START, until_instant=DAY_END, limit=200
            )
        assert [row.id for row in rows] == [here]
    finally:
        await engine.dispose()


async def test_the_dress_picker_lists_live_dresses_with_their_sizes(app_role_url: str) -> None:
    """`ORDER BY sort_order, name` and not `list_page`'s `created_at DESC` — a
    picker is read by a human scanning for a name, where the catalog page is read
    newest-first. Sizes come back for every dress in ONE grouped statement rather
    than one per row.

    What this discloses is strictly less than the boutique's own storefront
    already publishes to an anonymous visitor: no price, no description, no
    media, no stock quantity."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        async with tenant_session(factory, tenant_id) as session:
            veronique = Dress(tenant_id=tenant_id, name="ורוניק", sort_order=1)
            aline = Dress(tenant_id=tenant_id, name="אלין", sort_order=0)
            archived = Dress(tenant_id=tenant_id, name="גנוזה", sort_order=0, deleted_at=LATER)
            session.add_all([veronique, aline, archived])
            await session.flush()
            session.add_all(
                [
                    DressVariant(
                        tenant_id=tenant_id, dress_id=veronique.id, size_label="40", sort_order=1
                    ),
                    DressVariant(
                        tenant_id=tenant_id, dress_id=veronique.id, size_label="38", sort_order=0
                    ),
                    DressVariant(
                        tenant_id=tenant_id,
                        dress_id=veronique.id,
                        size_label="42",
                        sort_order=2,
                        deleted_at=LATER,
                    ),
                ]
            )
            live_ids = (aline.id, veronique.id)

        async with tenant_session(factory, tenant_id) as session:
            dresses = await DressesRepository().list_for_picker(session, tenant_id, limit=500)
            sizes = await DressVariantsRepository().size_labels_by_dress(
                session, tenant_id, [dress.id for dress in dresses]
            )
            assert (
                await DressVariantsRepository().size_labels_by_dress(session, tenant_id, []) == {}
            )
        assert tuple(dress.id for dress in dresses) == live_ids
        assert sizes == {live_ids[1]: ["38", "40"]}
    finally:
        await engine.dispose()
