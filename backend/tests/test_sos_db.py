"""F37's verbs against real Postgres as the non-owner app role.

What lives here and cannot live anywhere else: the rows a monkeypatched
repository can never prove. The reroute's audit row, the room pointer that
belongs to somebody else, and the 409 that has to READ a real `staff_users` row
to name the owner — all three are decided by what the database actually contains.

⚠ **Every row this module COMMITS holds `owner` or `shift_manager`, never a floor
role** (`test_floor_db.py:10-32`). `migrated_db` is session-scoped, pytest
collects alphabetically, and a committed `reception` row reddens three tests in
`test_migrations.py` that have nothing to do with SOS. Nothing here asserts
anything about the actor's role — the audience rule and the role gate are the
fast suite's job.

The clock is injected and frozen, so `acknowledged_at` is an EQUALITY rather than
a range. `created_at` is `server_default=text("now()")` and is deliberately not
asserted on.

⚠ **An audit-row COUNT here cannot prove a no-op, and that is recorded rather
than assumed.** `tenant_session` is `session.begin()`, so every refusal in this
module rolls its whole transaction back — an audit row written unconditionally
before a 409 never commits, and the count reads the same either way. Mutation
performed: moving `SOS_ACCEPTED` out of its `if wrote:` left every test in this
file GREEN and reddened `test_sos_service.py`, where the fake session records the
CALL rather than the commit. The write-path counts below are still worth having;
the no-op claim belongs to the fast suite.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update
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
from app.db.repositories.sessions import SessionsRepository
from app.db.repositories.staff_users import StaffUsersRepository
from app.db.tenant import tenant_session
from app.errors import DomainNotFoundError
from app.floor.service import FloorService
from app.floor.validation import SosAlreadyAcceptedError, SosClosedError
from app.models.audit_log import AuditLog
from app.models.booking import Booking
from app.models.constants import AuditAction, BookingStatus, SosStatus, StaffRole
from app.models.customer import Customer
from app.models.sos_alert import SosAlert
from app.models.staff_user import StaffUser

pytestmark = pytest.mark.db

NOW = datetime(2026, 8, 3, 11, 20, tzinfo=UTC)
LATER = datetime(2026, 8, 3, 13, 45, tzinfo=UTC)
# The one customer datum this feature must never render. Bound to the raiser's
# own room, which is the state F36's floor payload puts on a tile.
CLIENT_NAME = "מיכל כהן"


def _factory(app_role_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    return (
        engine := create_async_engine(app_role_url, poolclass=NullPool),
        async_sessionmaker(engine, expire_on_commit=False),
    )


def _service(factory: async_sessionmaker[AsyncSession]) -> FloorService:
    return FloorService(factory, clock=lambda: NOW)


def _actor(staff_id: uuid.UUID, tenant_id: uuid.UUID, role: StaffRole) -> StaffContext:
    return StaffContext(
        id=staff_id,
        tenant_id=tenant_id,
        email="staff@example.com",
        display_name="Actor",
        # `.value`: `StaffContext.role` is a `str`. ⚠ NOT a vacuity guard —
        # `StaffRole` is a `StrEnum`, so the member and its value compare and
        # hash equal (mutation run in `test_sos_service.py`, all green).
        role=role.value,
    )


async def _seed_staff(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    *,
    display_name: str = "Staff",
    role: str = StaffRole.OWNER.value,
) -> uuid.UUID:
    assert role in {StaffRole.OWNER.value, StaffRole.SHIFT_MANAGER.value}, (
        "this module COMMITS its rows; a floor role here reddens test_migrations.py"
    )
    async with tenant_session(factory, tenant_id) as session:
        staff = await StaffUsersRepository().insert(
            session,
            tenant_id=tenant_id,
            email=f"sos-{uuid.uuid4().hex[:10]}@bella.example",
            password_hash="not-a-real-hash",
            display_name=display_name,
            role=role,
        )
        return staff.id


async def _sign_in(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    staff_id: uuid.UUID,
    *,
    expires_at: datetime = LATER,
) -> None:
    async with tenant_session(factory, tenant_id) as session:
        await SessionsRepository().insert(
            session,
            tenant_id=tenant_id,
            staff_user_id=staff_id,
            token_hash=uuid.uuid4().hex,
            expires_at=expires_at,
        )


async def _claim_room(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    staff_id: uuid.UUID,
    *,
    label: str,
) -> uuid.UUID:
    async with tenant_session(factory, tenant_id) as session:
        room = await FittingRoomsRepository().insert(session, tenant_id, label=label, sort_order=0)
        assignment = await FittingRoomAssignmentsRepository().claim(
            session, tenant_id, room_id=room.id, staff_id=staff_id, booking_id=None
        )
        return assignment.id


async def _claim_booked_room(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    staff_id: uuid.UUID,
    *,
    label: str = "חדר 2",
) -> uuid.UUID:
    """A room claimed FOR a checked-in bride — exactly the state F36's floor
    payload renders her name in. This feature's read must reach the room label
    and stop there."""
    async with tenant_session(factory, tenant_id) as session:
        customer = Customer(
            tenant_id=tenant_id,
            phone=f"+9725{uuid.uuid4().int % 10**8:08d}",
            name=CLIENT_NAME,
        )
        session.add(customer)
        await session.flush()
        booking = Booking(
            tenant_id=tenant_id,
            customer_id=customer.id,
            appointment_type_id=uuid.uuid4(),
            starts_at=NOW,
            seat_index=1,
            status=BookingStatus.CONFIRMED.value,
            terms_version_accepted=1,
            terms_accepted_at=NOW,
            appointment_type_name="מדידה",
            checked_in_at=NOW,
        )
        session.add(booking)
        await session.flush()
        room = await FittingRoomsRepository().insert(session, tenant_id, label=label, sort_order=0)
        assignment = await FittingRoomAssignmentsRepository().claim(
            session, tenant_id, room_id=room.id, staff_id=staff_id, booking_id=booking.id
        )
        return assignment.id


async def _audit_rows(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, action: AuditAction
) -> list[AuditLog]:
    async with tenant_session(factory, tenant_id) as session:
        rows = await session.execute(
            select(AuditLog).where(AuditLog.tenant_id == tenant_id, AuditLog.action == action)
        )
        return list(rows.scalars().all())


# --- VERB 1: raise -----------------------------------------------------------


async def test_a_logged_out_target_is_rerouted_to_the_shift_manager(app_role_url: str) -> None:
    """⚠ **THE no-reachable-target case, and the reroute is NOT an error path.**
    The alert is created, retargeted to the shift-manager role IN THE DATA, and
    the raiser is told so on screen.

    ⚠ **The `requested_target` / `target` pair is the whole point of the audit
    row**: the reroute writes NULL over the only record of whom she actually
    tried to page, so without the pair the trail says the page went to the shift
    manager and cannot say Dana was meant to get it.

    Drop `expires_at > :now` from the reachability probe and this test reds: the
    expired session reads as live, the page is stored against a staffer whose
    cookie is dead, and it reaches NOBODY until the thirty-second escalation."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        raiser = await _seed_staff(factory, tenant_id, display_name="Noa")
        dana = await _seed_staff(factory, tenant_id, display_name="Dana")
        await _sign_in(factory, tenant_id, dana, expires_at=NOW - timedelta(minutes=1))

        result = await _service(factory).raise_sos(
            tenant_id,
            target_staff_user_id=dana,
            fitting_room_assignment_id=None,
            note="צריך סיכות",
            actor=_actor(raiser, tenant_id, StaffRole.OWNER),
        )
        assert result.rerouted is True
        assert result.sos.alert.target_staff_user_id is None

        async with tenant_session(factory, tenant_id) as session:
            stored = await session.scalar(
                select(SosAlert).where(SosAlert.id == result.sos.alert.id)
            )
        assert stored is not None
        assert stored.target_staff_user_id is None
        assert stored.status == SosStatus.OPEN
        assert stored.note == "צריך סיכות"

        rows = await _audit_rows(factory, tenant_id, AuditAction.SOS_RAISED)
        assert len(rows) == 1
        assert rows[0].details == {
            "alert": str(result.sos.alert.id),
            "requested_target": str(dana),
            "target": None,
            "rerouted": True,
            "assignment": None,
        }
    finally:
        await engine.dispose()


async def test_a_signed_in_target_is_stored_and_not_rerouted(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        raiser = await _seed_staff(factory, tenant_id, display_name="Noa")
        dana = await _seed_staff(factory, tenant_id, display_name="Dana")
        await _sign_in(factory, tenant_id, dana)

        result = await _service(factory).raise_sos(
            tenant_id,
            target_staff_user_id=dana,
            fitting_room_assignment_id=None,
            note=None,
            actor=_actor(raiser, tenant_id, StaffRole.OWNER),
        )
        assert result.rerouted is False
        assert result.sos.alert.target_staff_user_id == dana
        rows = await _audit_rows(factory, tenant_id, AuditAction.SOS_RAISED)
        assert rows[0].details["requested_target"] == str(dana)
        assert rows[0].details["target"] == str(dana)
    finally:
        await engine.dispose()


async def test_a_deleted_target_is_rerouted_and_the_alert_is_still_created(
    app_role_url: str,
) -> None:
    """A live session and a soft-deleted staff row: BOTH checks must pass, and
    the reachability probe alone would let a removed colleague be paged."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        raiser = await _seed_staff(factory, tenant_id, display_name="Noa")
        dana = await _seed_staff(factory, tenant_id, display_name="Dana")
        await _sign_in(factory, tenant_id, dana)
        async with tenant_session(factory, tenant_id) as session:
            await session.execute(
                update(StaffUser).where(StaffUser.id == dana).values(deleted_at=NOW)
            )

        result = await _service(factory).raise_sos(
            tenant_id,
            target_staff_user_id=dana,
            fitting_room_assignment_id=None,
            note=None,
            actor=_actor(raiser, tenant_id, StaffRole.OWNER),
        )
        assert result.rerouted is True
        assert result.sos.alert.target_staff_user_id is None
    finally:
        await engine.dispose()


async def test_her_own_assignment_is_stored_on_the_page(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        raiser = await _seed_staff(factory, tenant_id, display_name="Noa")
        assignment_id = await _claim_room(factory, tenant_id, raiser, label="חדר 2")

        result = await _service(factory).raise_sos(
            tenant_id,
            target_staff_user_id=None,
            fitting_room_assignment_id=assignment_id,
            note=None,
            actor=_actor(raiser, tenant_id, StaffRole.OWNER),
        )
        assert result.sos.alert.fitting_room_assignment_id == assignment_id
        rows = await _audit_rows(factory, tenant_id, AuditAction.SOS_RAISED)
        assert rows[0].details["assignment"] == str(assignment_id)
    finally:
        await engine.dispose()


async def test_another_staffers_assignment_stores_null_and_the_alert_is_still_created(
    app_role_url: str,
) -> None:
    """⚠ **AC1's sharpest row.** F36's floor payload hands `RoomAssignment.id` out
    on every occupied tile to all five roles, so without the `staff_user_id`
    conjunct the page would render «דנה קוראת לעזרה — חדר 2» while Dana is
    standing in room 4. «No room» is a defined, safe state; «wrong room» sends a
    responder to a closed curtain with a stranger's bride behind it.

    And the alert is STILL CREATED either way, which is exactly why nothing else
    in the feature fails when the conjunct is dropped."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        raiser = await _seed_staff(factory, tenant_id, display_name="Noa")
        dana = await _seed_staff(factory, tenant_id, display_name="Dana")
        hers = await _claim_room(factory, tenant_id, dana, label="חדר 2")

        result = await _service(factory).raise_sos(
            tenant_id,
            target_staff_user_id=None,
            fitting_room_assignment_id=hers,
            note=None,
            actor=_actor(raiser, tenant_id, StaffRole.OWNER),
        )
        assert result.sos.alert.fitting_room_assignment_id is None
        assert result.sos.alert.status == SosStatus.OPEN
        rows = await _audit_rows(factory, tenant_id, AuditAction.SOS_RAISED)
        assert rows[0].details["assignment"] is None
    finally:
        await engine.dispose()


async def test_an_unknown_assignment_id_stores_null_and_the_alert_is_still_created(
    app_role_url: str,
) -> None:
    """A stale pointer from a tile that was released three seconds ago. RLS makes
    a foreign tenant's id simply not resolve, so this is also the cross-tenant
    row — and there is no oracle either way, because both answer the same."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        raiser = await _seed_staff(factory, tenant_id)
        result = await _service(factory).raise_sos(
            tenant_id,
            target_staff_user_id=None,
            fitting_room_assignment_id=uuid.uuid4(),
            note=None,
            actor=_actor(raiser, tenant_id, StaffRole.OWNER),
        )
        assert result.sos.alert.fitting_room_assignment_id is None
    finally:
        await engine.dispose()


async def test_a_second_page_by_the_same_raiser_is_admitted(app_role_url: str) -> None:
    """D2, as a live assertion: there is NO unique index, so «I need a seamstress
    AND I need the manager» is two alerts and not a 409. Duplicates are noise —
    two cards on an overlay, either of which resolves the emergency."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        raiser = await _seed_staff(factory, tenant_id)
        actor = _actor(raiser, tenant_id, StaffRole.OWNER)
        service = _service(factory)
        first = await service.raise_sos(
            tenant_id,
            target_staff_user_id=None,
            fitting_room_assignment_id=None,
            note=None,
            actor=actor,
        )
        second = await service.raise_sos(
            tenant_id,
            target_staff_user_id=None,
            fitting_room_assignment_id=None,
            note=None,
            actor=actor,
        )
        assert first.sos.alert.id != second.sos.alert.id
    finally:
        await engine.dispose()


# --- VERB 2: accept ----------------------------------------------------------


async def _raise(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    raiser: uuid.UUID,
    *,
    target: uuid.UUID | None = None,
) -> uuid.UUID:
    result = await _service(factory).raise_sos(
        tenant_id,
        target_staff_user_id=target,
        fitting_room_assignment_id=None,
        note=None,
        actor=_actor(raiser, tenant_id, StaffRole.OWNER),
    )
    return result.sos.alert.id


async def test_an_accept_stamps_the_owner_and_writes_one_audit_row(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        raiser = await _seed_staff(factory, tenant_id, display_name="Noa")
        dana = await _seed_staff(factory, tenant_id, display_name="Dana")
        alert_id = await _raise(factory, tenant_id, raiser)

        row = await _service(factory).accept_sos(
            tenant_id, alert_id, actor=_actor(dana, tenant_id, StaffRole.SHIFT_MANAGER)
        )
        assert row.alert.status == SosStatus.ACCEPTED
        assert row.alert.accepted_by == dana
        assert row.alert.acknowledged_at == NOW

        rows = await _audit_rows(factory, tenant_id, AuditAction.SOS_ACCEPTED)
        assert len(rows) == 1
        assert rows[0].actor_id == dana
        assert rows[0].entity == str(alert_id)
        assert rows[0].details == {"alert": str(alert_id), "raised_by": str(raiser)}
    finally:
        await engine.dispose()


async def test_a_second_accept_is_refused_and_names_the_owner(app_role_url: str) -> None:
    """⚠ **THE MUTATION TARGET for `AND status = 'open'`.** Drop the conjunct and
    the second responder OVERWRITES the first: `accepted_by` flips, the first is
    never told, and two people walk to one curtain while a third emergency goes
    unanswered. Every test that accepts once stays green.

    The name comes from a REAL `staff_users` read, which is why this assertion
    cannot live in the fast suite."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        raiser = await _seed_staff(factory, tenant_id, display_name="Noa")
        dana = await _seed_staff(factory, tenant_id, display_name="דנה כהן")
        rina = await _seed_staff(factory, tenant_id, display_name="רינה")
        alert_id = await _raise(factory, tenant_id, raiser)
        service = _service(factory)

        await service.accept_sos(
            tenant_id, alert_id, actor=_actor(dana, tenant_id, StaffRole.SHIFT_MANAGER)
        )
        with pytest.raises(SosAlreadyAcceptedError) as raised:
            await service.accept_sos(
                tenant_id, alert_id, actor=_actor(rina, tenant_id, StaffRole.SHIFT_MANAGER)
            )
        assert raised.value.details == {"staff_display_name": "דנה כהן"}

        async with tenant_session(factory, tenant_id) as session:
            stored = await session.scalar(select(SosAlert).where(SosAlert.id == alert_id))
        assert stored is not None
        assert stored.accepted_by == dana
        assert len(await _audit_rows(factory, tenant_id, AuditAction.SOS_ACCEPTED)) == 1
    finally:
        await engine.dispose()


async def test_an_accept_whose_winner_was_removed_does_not_name_nobody(
    app_role_url: str,
) -> None:
    """⚠ `details` is OPTIONAL and the key is ABSENT, never `null`. Make it
    required and this path either raises building the body or ships
    `{"staff_display_name": null}` and the console renders «{{name}} כבר מגיעה.»
    with an empty interpolation. Every other 409 test has an owner to read."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        raiser = await _seed_staff(factory, tenant_id, display_name="Noa")
        dana = await _seed_staff(factory, tenant_id, display_name="Dana")
        rina = await _seed_staff(factory, tenant_id, display_name="Rina")
        alert_id = await _raise(factory, tenant_id, raiser)
        service = _service(factory)

        await service.accept_sos(
            tenant_id, alert_id, actor=_actor(dana, tenant_id, StaffRole.SHIFT_MANAGER)
        )
        async with tenant_session(factory, tenant_id) as session:
            await session.execute(
                update(StaffUser).where(StaffUser.id == dana).values(deleted_at=NOW)
            )

        with pytest.raises(SosAlreadyAcceptedError) as raised:
            await service.accept_sos(
                tenant_id, alert_id, actor=_actor(rina, tenant_id, StaffRole.SHIFT_MANAGER)
            )
        assert raised.value.details is None
    finally:
        await engine.dispose()


async def test_a_re_accept_by_the_owner_writes_no_audit_row(app_role_url: str) -> None:
    """The second tap must not stamp a second `acknowledged_at` and must not
    write a second trail row.

    ⚠ **What this does NOT pin, said plainly: the ORDER.** Resolving idempotence
    after the 409 instead of before leaves this test green — the writer returns
    `(False, accepted-by-me)` either way and no audit row is written either way.
    The ordering is pinned by `test_sos_service.py`'s
    `test_a_re_accept_by_the_current_owner_is_a_200_with_no_write`, whose
    assertion is that the WRITER WAS NEVER REACHED, which only a call sequence
    can say. Mutation performed in both directions."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        raiser = await _seed_staff(factory, tenant_id, display_name="Noa")
        dana = await _seed_staff(factory, tenant_id, display_name="Dana")
        alert_id = await _raise(factory, tenant_id, raiser)
        service = _service(factory)
        actor = _actor(dana, tenant_id, StaffRole.SHIFT_MANAGER)

        first = await service.accept_sos(tenant_id, alert_id, actor=actor)
        again = await service.accept_sos(tenant_id, alert_id, actor=actor)
        assert again.alert.status == SosStatus.ACCEPTED
        assert again.alert.accepted_by == dana
        assert again.alert.acknowledged_at == first.alert.acknowledged_at == NOW
        assert len(await _audit_rows(factory, tenant_id, AuditAction.SOS_ACCEPTED)) == 1
    finally:
        await engine.dispose()


async def test_accepting_a_closed_alert_is_a_409_with_no_name(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        raiser = await _seed_staff(factory, tenant_id, display_name="Noa")
        dana = await _seed_staff(factory, tenant_id, display_name="Dana")
        alert_id = await _raise(factory, tenant_id, raiser)
        async with tenant_session(factory, tenant_id) as session:
            await session.execute(
                update(SosAlert).where(SosAlert.id == alert_id).values(status=SosStatus.RESOLVED)
            )

        with pytest.raises(SosClosedError) as raised:
            await _service(factory).accept_sos(
                tenant_id, alert_id, actor=_actor(dana, tenant_id, StaffRole.SHIFT_MANAGER)
            )
        assert raised.value.details is None
        assert await _audit_rows(factory, tenant_id, AuditAction.SOS_ACCEPTED) == []
    finally:
        await engine.dispose()


async def test_another_tenants_alert_is_a_404_and_is_never_touched(app_role_url: str) -> None:
    """RLS plus the by-id read: an alert in another boutique is byte-identical to
    an alert that does not exist."""
    engine, factory = _factory(app_role_url)
    mine, theirs = uuid.uuid4(), uuid.uuid4()
    try:
        raiser = await _seed_staff(factory, theirs, display_name="Noa")
        alert_id = await _raise(factory, theirs, raiser)
        intruder = await _seed_staff(factory, mine, display_name="Intruder")

        with pytest.raises(DomainNotFoundError):
            await _service(factory).accept_sos(
                mine, alert_id, actor=_actor(intruder, mine, StaffRole.OWNER)
            )

        async with tenant_session(factory, theirs) as session:
            stored = await session.scalar(select(SosAlert).where(SosAlert.id == alert_id))
        assert stored is not None
        assert stored.status == SosStatus.OPEN
        assert stored.accepted_by is None
    finally:
        await engine.dispose()


# --- the read-time predicates, against a real row and a FROZEN clock ----------
#
# ⚠ **BOTH operands are frozen and that is not fussiness.** `server_now` is
# `FloorService`'s injectable clock and `created_at` is SEEDED, so the margin is
# exact. Left the other way — seed `created_at`, let the wall clock supply
# `server_now` — the not-escalated assertion flips as soon as ~1 s elapses
# between the seed and the read, i.e. a Postgres round trip on a loaded CI box,
# and a test that goes green or red on machine speed will be re-run until it
# passes, which is how a mutation regime rots.
#
# What a `db` test genuinely cannot freeze is `server_default=text("now()")` —
# which is precisely WHY `created_at` is seeded: the default applies only when
# the column is omitted.


async def _age(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    alert_id: uuid.UUID,
    **fields: datetime,
) -> None:
    """Seeds the operand the service clock is compared against — `created_at` is
    `server_default=text("now()")` and a test that let the wall clock supply it
    would go green or red on machine speed."""
    async with tenant_session(factory, tenant_id) as session:
        await session.execute(update(SosAlert).where(SosAlert.id == alert_id).values(**fields))


async def test_an_alert_open_for_31_seconds_is_escalated_and_one_open_for_29_is_not(
    app_role_url: str,
) -> None:
    """The thirty-second rule against a real row, and `escalated` rides the wire
    from the same instant the console's elapsed line is anchored on."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        raiser = await _seed_staff(factory, tenant_id, display_name="Noa")
        manager = await _seed_staff(factory, tenant_id, display_name="Dana")
        fresh = await _raise(factory, tenant_id, raiser)
        old = await _raise(factory, tenant_id, raiser)
        await _age(factory, tenant_id, fresh, created_at=NOW - timedelta(seconds=29))
        await _age(factory, tenant_id, old, created_at=NOW - timedelta(seconds=31))

        read = await _service(factory).sos(
            tenant_id, actor=_actor(manager, tenant_id, StaffRole.SHIFT_MANAGER)
        )
        assert read.server_now == NOW
        assert {one.alert.id: one.escalated for one in read.alerts} == {fresh: False, old: True}
    finally:
        await engine.dispose()


async def test_an_accepted_alert_unresolved_for_two_minutes_re_rises_for_the_shift_manager(
    app_role_url: str,
) -> None:
    """⚠ **AC26, and deleting `_stalled` or its `_for_me` branch is the only
    thing that reds it.** Every other test in this file accepts and then resolves.

    Without the second boolean an accepted alert stops escalating and stops
    rising on EVERY device in the boutique, forever — and it is worse than
    silence, because the raiser's screen reads «דנה מגיעה» and she stops looking
    for help on a signal the product cannot back."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        raiser = await _seed_staff(factory, tenant_id, display_name="Noa")
        dana = await _seed_staff(factory, tenant_id, display_name="Dana")
        rina = await _seed_staff(factory, tenant_id, display_name="Rina")
        alert_id = await _raise(factory, tenant_id, raiser)
        await _service(factory).accept_sos(
            tenant_id, alert_id, actor=_actor(dana, tenant_id, StaffRole.SHIFT_MANAGER)
        )
        manager = _actor(rina, tenant_id, StaffRole.SHIFT_MANAGER)

        # One minute in: hers, and nobody else's.
        await _age(factory, tenant_id, alert_id, acknowledged_at=NOW - timedelta(minutes=1))
        moving = await _service(factory).sos(tenant_id, actor=manager)
        assert [(one.stalled, one.for_me) for one in moving.alerts] == [(False, False)]

        # Three minutes in: nobody has moved, so it is nobody's job again.
        await _age(factory, tenant_id, alert_id, acknowledged_at=NOW - timedelta(minutes=3))
        stalled = await _service(factory).sos(tenant_id, actor=manager)
        assert [(one.stalled, one.for_me) for one in stalled.alerts] == [(True, True)]
        assert stalled.alerts[0].alert.status == SosStatus.ACCEPTED
        assert stalled.alerts[0].row.accepted_by_name == "Dana"

        # …and never for the raiser, even then.
        hers = await _service(factory).sos(
            tenant_id, actor=_actor(raiser, tenant_id, StaffRole.SHIFT_MANAGER)
        )
        assert [one.for_me for one in hers.alerts] == [False]
    finally:
        await engine.dispose()


async def test_a_seamstress_sees_only_her_own_pages(app_role_url: str) -> None:
    """⚠ **AC7 end to end, and dropping the `or_(...)` audience clause is the
    mutation.** The overlay is mounted app-wide on eleven sections, and the only
    reason that is safe is that the filter runs on the SERVER.

    The context's role is `seamstress`; the COMMITTED rows are all elevated,
    which is the seed rule this module runs under."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        her = await _seed_staff(factory, tenant_id, display_name="Noa")
        stranger = await _seed_staff(factory, tenant_id, display_name="Rina")
        # She must hold a live session or the raise below REROUTES to the
        # shift-manager role and the alert is not name-targeted at all.
        await _sign_in(factory, tenant_id, her)
        raised = await _raise(factory, tenant_id, her)
        named = await _raise(factory, tenant_id, stranger, target=her)
        strangers = await _raise(factory, tenant_id, stranger)

        seamstress = _actor(her, tenant_id, StaffRole.SEAMSTRESS)
        assert {
            one.alert.id
            for one in (await _service(factory).sos(tenant_id, actor=seamstress)).alerts
        } == {
            raised,
            named,
        }
        owner = _actor(stranger, tenant_id, StaffRole.OWNER)
        assert {
            one.alert.id for one in (await _service(factory).sos(tenant_id, actor=owner)).alerts
        } == {
            raised,
            named,
            strangers,
        }
    finally:
        await engine.dispose()


async def test_the_payload_carries_no_customer_datum(app_role_url: str) -> None:
    """⚠ **AC8's `db` half.** A checked-in booking is bound to the raiser's
    assignment, exactly as F36's floor payload would render it, and her name
    appears NOWHERE on this read. F36's payload is fetched only while the console
    is on the board or the floor; this one is fetched on every section, every few
    seconds, for the whole shift."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        raiser = await _seed_staff(factory, tenant_id, display_name="Noa")
        assignment_id = await _claim_booked_room(factory, tenant_id, raiser)
        await _service(factory).raise_sos(
            tenant_id,
            target_staff_user_id=None,
            fitting_room_assignment_id=assignment_id,
            note=None,
            actor=_actor(raiser, tenant_id, StaffRole.OWNER),
        )
        read = await _service(factory).sos(
            tenant_id, actor=_actor(raiser, tenant_id, StaffRole.OWNER)
        )
        assert [one.row.room_label for one in read.alerts] == ["חדר 2"]
        rendered = [
            (
                one.row.raised_by_name,
                one.row.target_name,
                one.row.accepted_by_name,
                one.row.room_label,
                one.alert.note,
            )
            for one in read.alerts
        ]
        assert CLIENT_NAME not in str(rendered)
    finally:
        await engine.dispose()


# --- VERBS 3 and 4: resolve and cancel ---------------------------------------


@pytest.mark.parametrize("accepted_first", [False, True])
async def test_a_resolve_records_the_state_it_destroys(
    app_role_url: str, accepted_first: bool
) -> None:
    """⚠ **THE mutation target for the `from_status` capture, and it CANNOT live
    in the fast suite.**

    Move the capture below the writer and this reds with `from_status:
    'resolved'` — the UPDATE is ORM-enabled DML whose `evaluate` synchronization
    stamps the new status onto the very instance `by_id` handed back out of one
    identity map. A monkeypatched repository never stamps anything, so every fast
    test stays green (F57's shipped note records exactly this), and the audit row
    silently becomes `resolved -> resolved` — empty of its whole informational
    content, on the one column that answers «did anybody answer?» without a
    `resolved_at`."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        raiser = await _seed_staff(factory, tenant_id, display_name="Noa")
        dana = await _seed_staff(factory, tenant_id, display_name="Dana")
        alert_id = await _raise(factory, tenant_id, raiser)
        service = _service(factory)
        if accepted_first:
            await service.accept_sos(
                tenant_id, alert_id, actor=_actor(dana, tenant_id, StaffRole.SHIFT_MANAGER)
            )

        row = await service.resolve_sos(
            tenant_id, alert_id, actor=_actor(raiser, tenant_id, StaffRole.OWNER)
        )
        assert row.alert.status == SosStatus.RESOLVED

        rows = await _audit_rows(factory, tenant_id, AuditAction.SOS_RESOLVED)
        assert len(rows) == 1
        expected = SosStatus.ACCEPTED if accepted_first else SosStatus.OPEN
        assert rows[0].details == {"alert": str(alert_id), "from_status": expected}
    finally:
        await engine.dispose()


async def test_a_resolve_landing_after_a_resolve_writes_nothing(app_role_url: str) -> None:
    """⚠ **Rowcount 0 is not an error, and treating it as a 404 is the
    mutation.** She wanted it closed and it is closed; the second resolver would
    get an error for being right. No other test issues two resolves."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        raiser = await _seed_staff(factory, tenant_id, display_name="Noa")
        alert_id = await _raise(factory, tenant_id, raiser)
        service = _service(factory)
        actor = _actor(raiser, tenant_id, StaffRole.OWNER)

        await service.resolve_sos(tenant_id, alert_id, actor=actor)
        again = await service.resolve_sos(tenant_id, alert_id, actor=actor)
        assert again.alert.status == SosStatus.RESOLVED
        assert len(await _audit_rows(factory, tenant_id, AuditAction.SOS_RESOLVED)) == 1
    finally:
        await engine.dispose()


async def test_a_second_cancel_is_a_200_with_no_audit_row(app_role_url: str) -> None:
    """AC9's tail, the row D5's prose left implicit."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        raiser = await _seed_staff(factory, tenant_id, display_name="Noa")
        alert_id = await _raise(factory, tenant_id, raiser)
        service = _service(factory)
        actor = _actor(raiser, tenant_id, StaffRole.OWNER)

        await service.cancel_sos(tenant_id, alert_id, actor=actor)
        again = await service.cancel_sos(tenant_id, alert_id, actor=actor)
        assert again.alert.status == SosStatus.CANCELLED
        assert len(await _audit_rows(factory, tenant_id, AuditAction.SOS_CANCELLED)) == 1
    finally:
        await engine.dispose()


async def test_a_cancel_racing_an_accept_never_strands_the_responder(app_role_url: str) -> None:
    """⚠ **THE SECOND FORCED INTERLEAVE, and widening cancel's predicate to
    resolve's pair is the mutation.** Every sequential cancel test stays green
    under it, while a colleague walks to a curtain for an emergency that was
    cancelled behind her.

    `asyncio.gather` is deliberately NOT used: it does not ORDER two
    transactions, so the loser most often runs after the winner commits and the
    branch goes green without the mechanism ever being exercised. The mechanism
    is that `tenant_session` is `session.begin()`, so EXITING the context manager
    IS the commit, and two nested ones on a `NullPool` factory take two separate
    connections. Nothing blocks: a guarded UPDATE against a committed row RETURNS
    rather than waiting."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        raiser = await _seed_staff(factory, tenant_id, display_name="Noa")
        dana = await _seed_staff(factory, tenant_id, display_name="דנה כהן")
        alert_id = await _raise(factory, tenant_id, raiser)
        service = _service(factory)

        # The canceller's own transaction is opened by `cancel_sos`, so the
        # interleave is forced from OUTSIDE: the accept commits first, and the
        # cancel then reads an ACCEPTED row and must refuse rather than close it.
        await service.accept_sos(
            tenant_id, alert_id, actor=_actor(dana, tenant_id, StaffRole.SHIFT_MANAGER)
        )
        with pytest.raises(SosAlreadyAcceptedError) as raised:
            await service.cancel_sos(
                tenant_id, alert_id, actor=_actor(raiser, tenant_id, StaffRole.OWNER)
            )
        assert raised.value.details == {"staff_display_name": "דנה כהן"}

        async with tenant_session(factory, tenant_id) as session:
            stored = await session.scalar(select(SosAlert).where(SosAlert.id == alert_id))
        assert stored is not None
        assert stored.status == SosStatus.ACCEPTED
        assert stored.accepted_by == dana
        assert await _audit_rows(factory, tenant_id, AuditAction.SOS_CANCELLED) == []
    finally:
        await engine.dispose()


async def test_a_resolve_after_a_cancel_is_a_200_and_the_row_stays_cancelled(
    app_role_url: str,
) -> None:
    """The two closers are not ordered: whichever landed first is the state, and
    the second caller is told what happened rather than that she was wrong."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        raiser = await _seed_staff(factory, tenant_id, display_name="Noa")
        alert_id = await _raise(factory, tenant_id, raiser)
        service = _service(factory)
        actor = _actor(raiser, tenant_id, StaffRole.OWNER)

        await service.cancel_sos(tenant_id, alert_id, actor=actor)
        resolved = await service.resolve_sos(tenant_id, alert_id, actor=actor)
        assert resolved.alert.status == SosStatus.CANCELLED
        assert await _audit_rows(factory, tenant_id, AuditAction.SOS_RESOLVED) == []
    finally:
        await engine.dispose()


async def test_a_closed_alert_leaves_the_live_read(app_role_url: str) -> None:
    """The poll's predicate is `idx_sos_alerts_live`'s, so a resolve is what
    takes the card off every screen in the boutique."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        raiser = await _seed_staff(factory, tenant_id, display_name="Noa")
        alert_id = await _raise(factory, tenant_id, raiser)
        service = _service(factory)
        actor = _actor(raiser, tenant_id, StaffRole.OWNER)

        assert len((await service.sos(tenant_id, actor=actor)).alerts) == 1
        await service.resolve_sos(tenant_id, alert_id, actor=actor)
        assert (await service.sos(tenant_id, actor=actor)).alerts == []
    finally:
        await engine.dispose()
