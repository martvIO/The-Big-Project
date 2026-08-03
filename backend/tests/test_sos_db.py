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
from app.models.constants import AuditAction, SosStatus, StaffRole
from app.models.sos_alert import SosAlert
from app.models.staff_user import StaffUser

pytestmark = pytest.mark.db

NOW = datetime(2026, 8, 3, 11, 20, tzinfo=UTC)
LATER = datetime(2026, 8, 3, 13, 45, tzinfo=UTC)


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
        # `.value`: ELEVATED_ROLES is a frozenset of strings.
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
        assert result.alert.target_staff_user_id is None

        async with tenant_session(factory, tenant_id) as session:
            stored = await session.scalar(select(SosAlert).where(SosAlert.id == result.alert.id))
        assert stored is not None
        assert stored.target_staff_user_id is None
        assert stored.status == SosStatus.OPEN
        assert stored.note == "צריך סיכות"

        rows = await _audit_rows(factory, tenant_id, AuditAction.SOS_RAISED)
        assert len(rows) == 1
        assert rows[0].details == {
            "alert": str(result.alert.id),
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
        assert result.alert.target_staff_user_id == dana
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
        assert result.alert.target_staff_user_id is None
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
        assert result.alert.fitting_room_assignment_id == assignment_id
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
        assert result.alert.fitting_room_assignment_id is None
        assert result.alert.status == SosStatus.OPEN
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
        assert result.alert.fitting_room_assignment_id is None
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
        assert first.alert.id != second.alert.id
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
    return result.alert.id


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
        assert row.status == SosStatus.ACCEPTED
        assert row.accepted_by == dana
        assert row.acknowledged_at == NOW

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
        assert again.status == SosStatus.ACCEPTED
        assert again.accepted_by == dana
        assert again.acknowledged_at == first.acknowledged_at == NOW
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
