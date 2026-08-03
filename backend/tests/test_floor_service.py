"""F57's break toggle, driven with fakes and no database.

**This is where D6 is actually proven.** The authorization rule has two axes —
who is asking (session) and whom she is toggling (request) — and every branch of
it is a pure Python decision, so it belongs in the fast suite where it runs on
every push rather than in a `db`-marked module that first executes on CI.

The fake session factory is the `test_booking_owner_service.py` scaffold: enough
surface for `tenant_session`'s `set_config` and nothing else, so a statement
escaping to a real session raises here instead of passing silently.

What is NOT proven here and must not be claimed: that the repository's guarded
UPDATE and its `populate_existing` re-read behave under a real identity map.
`test_floor_db.py` owns that, and its mutation check is what makes it honest.
"""

import dataclasses
import datetime
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.auth.dependencies import NotAuthorizedError
from app.auth.service import StaffContext
from app.db.repositories.audit_log import AuditLogRepository
from app.db.repositories.bookings import BookingsRepository
from app.db.repositories.dresses import DressesRepository
from app.db.repositories.fitting_assignment_dresses import FittingAssignmentDressesRepository
from app.db.repositories.fitting_room_assignments import (
    ROOM_ACTIVE_INDEX,
    STAFF_ACTIVE_INDEX,
    FittingRoomAssignmentsRepository,
)
from app.db.repositories.fitting_rooms import FittingRoomsRepository, RoomRow
from app.db.repositories.staff_users import StaffUsersRepository
from app.errors import DomainNotFoundError
from app.floor.service import FloorService, card_status
from app.floor.validation import FloorValidationError, RoomOccupiedError, StaffOccupiedError
from app.models.booking import Booking
from app.models.constants import AuditAction, BookingStatus, StaffCardStatus, StaffRole
from app.models.dress import Dress
from app.models.fitting_room import FittingRoom
from app.models.fitting_room_assignment import FittingRoomAssignment
from app.models.staff_user import StaffUser

TENANT_ID = uuid.uuid4()
NOW = datetime.datetime(2026, 8, 2, 11, 20, tzinfo=datetime.UTC)
BREAK_BEGAN = datetime.datetime(2026, 8, 2, 9, 5, tzinfo=datetime.UTC)

ELEVATED = [StaffRole.OWNER, StaffRole.SHIFT_MANAGER]
FLOOR = [StaffRole.RECEPTION, StaffRole.SALES_ASSISTANT, StaffRole.SEAMSTRESS]


def _actor(role: StaffRole, staff_id: uuid.UUID | None = None) -> StaffContext:
    return StaffContext(
        id=staff_id or uuid.uuid4(),
        tenant_id=TENANT_ID,
        email="staff@example.com",
        display_name="נועה לוי",
        role=role.value,
    )


def _staff_user(**overrides: object) -> StaffUser:
    row = StaffUser(
        tenant_id=TENANT_ID,
        email="staff@example.com",
        password_hash="not-a-real-hash",
        display_name="נועה לוי",
        role=StaffRole.RECEPTION.value,
    )
    row.id = uuid.uuid4()
    row.break_started_at = None
    for key, value in overrides.items():
        setattr(row, key, value)
    return row


class _FakeTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *exc: object) -> bool:
        return False


class _FakeSession:
    def begin(self) -> _FakeTransaction:
        return _FakeTransaction()

    def begin_nested(self) -> _FakeTransaction:
        """The claim's SAVEPOINT. It does nothing here — a monkeypatched
        repository raises before any real flush — which is exactly why deleting
        `begin_nested()` from the service stays GREEN in this module and has to
        be pinned by a forced interleave instead."""
        return _FakeTransaction()

    async def execute(self, *args: object, **kwargs: object) -> None:
        return None


@asynccontextmanager
async def _fake_session_factory() -> AsyncIterator[_FakeSession]:
    yield _FakeSession()


def _service() -> FloorService:
    return FloorService(cast(async_sessionmaker, _fake_session_factory), clock=lambda: NOW)


class _Writes:
    """`order` is the whole point of this recorder. The 403-is-not-an-existence-
    oracle assertion is not "an error was raised" — it is "the target was never
    read", and only a sequence can say that."""

    def __init__(self) -> None:
        self.order: list[str] = []
        self.audit: list[dict[str, Any]] = []
        self.calls: list[dict[str, Any]] = []


def _install(
    monkeypatch: pytest.MonkeyPatch,
    *,
    wrote: bool,
    row: StaffUser | None,
    before: StaffUser | None = None,
) -> _Writes:
    writes = _Writes()

    async def _by_id(
        _self: object, _session: object, _tenant_id: uuid.UUID, staff_id: uuid.UUID
    ) -> StaffUser | None:
        writes.order.append("by_id")
        return before

    async def _start(
        _self: object,
        _session: object,
        tenant_id: uuid.UUID,
        staff_id: uuid.UUID,
        *,
        at: datetime.datetime,
    ) -> tuple[bool, StaffUser | None]:
        writes.order.append("start_break")
        writes.calls.append({"tenant_id": tenant_id, "staff_id": staff_id, "at": at})
        return wrote, row

    async def _end(
        _self: object, _session: object, tenant_id: uuid.UUID, staff_id: uuid.UUID
    ) -> tuple[bool, StaffUser | None]:
        writes.order.append("end_break")
        writes.calls.append({"tenant_id": tenant_id, "staff_id": staff_id})
        return wrote, row

    async def _record(
        _self: object,
        _session: object,
        *,
        tenant_id: uuid.UUID,
        action: str,
        actor_id: uuid.UUID | None = None,
        entity: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        writes.order.append("audit")
        writes.audit.append(
            {"action": action, "actor_id": actor_id, "entity": entity, "details": details}
        )

    async def _no_occupancy(
        _self: object, _session: object, _tenant_id: uuid.UUID, _staff_id: uuid.UUID
    ) -> None:
        """F36 gave both break writers one indexed occupancy lookup. It is NOT
        recorded in `order`: F57's shipped sequence assertions are about the
        write ordering, and this is a read added after it.
        `test_a_break_route_answers_occupied_when_she_is_in_a_room` asserts what
        it answers."""
        return None

    monkeypatch.setattr(StaffUsersRepository, "by_id", _by_id)
    monkeypatch.setattr(StaffUsersRepository, "start_break", _start)
    monkeypatch.setattr(StaffUsersRepository, "end_break", _end)
    monkeypatch.setattr(FittingRoomsRepository, "occupancy_for_staff", _no_occupancy)
    monkeypatch.setattr(AuditLogRepository, "record", _record)
    return writes


# --- the authorization matrix (D6) ------------------------------------------


@pytest.mark.parametrize("role", ELEVATED)
async def test_an_elevated_role_may_toggle_anybody(
    monkeypatch: pytest.MonkeyPatch, role: StaffRole
) -> None:
    target = _staff_user(break_started_at=NOW)
    writes = _install(monkeypatch, wrote=True, row=target)

    result, _ = await _service().start_break(TENANT_ID, target.id, actor=_actor(role))

    assert result is target
    assert writes.order == ["start_break", "audit"]


@pytest.mark.parametrize("role", FLOOR)
async def test_a_floor_role_may_toggle_herself(
    monkeypatch: pytest.MonkeyPatch, role: StaffRole
) -> None:
    """The `staff_id == actor.id` half. The id comes from the REQUEST and the
    actor from the SESSION — a body-supplied identity doubling as the caller's
    is the one shape that turns this into "any staffer on anyone"."""
    me = _staff_user(role=role.value, break_started_at=NOW)
    writes = _install(monkeypatch, wrote=True, row=me)

    result, _ = await _service().start_break(TENANT_ID, me.id, actor=_actor(role, me.id))

    assert result is me
    assert writes.order == ["start_break", "audit"]


@pytest.mark.parametrize("role", FLOOR)
async def test_a_floor_role_toggling_a_colleague_is_refused_without_reading_her(
    monkeypatch: pytest.MonkeyPatch, role: StaffRole
) -> None:
    """⚠ The second assertion is the feature, not the first.

    A 403 raised AFTER a read is an existence oracle: a non-elevated staffer
    could enumerate which staff ids exist in her tenant by timing or by which
    error came back. The check is the method's first statement and it runs
    before the session is even opened, so the repository is never reached — and
    an empty `order` is the only way to assert that.
    """
    stranger = _staff_user()
    writes = _install(monkeypatch, wrote=True, row=stranger)
    actor = _actor(role)
    assert actor.id != stranger.id

    with pytest.raises(NotAuthorizedError):
        await _service().start_break(TENANT_ID, stranger.id, actor=actor)
    with pytest.raises(NotAuthorizedError):
        await _service().end_break(TENANT_ID, stranger.id, actor=actor)

    assert writes.order == []
    assert writes.audit == []


async def test_the_check_compares_ids_and_never_names_or_emails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same display_name and same email, different id — still refused. The
    identity of a person is her id; the other two are mutable strings."""
    twin = _staff_user(role=StaffRole.SEAMSTRESS.value)
    writes = _install(monkeypatch, wrote=True, row=twin)
    actor = StaffContext(
        id=uuid.uuid4(),
        tenant_id=TENANT_ID,
        email=twin.email,
        display_name=twin.display_name,
        role=StaffRole.SEAMSTRESS.value,
    )

    with pytest.raises(NotAuthorizedError):
        await _service().start_break(TENANT_ID, twin.id, actor=actor)

    assert writes.order == []


# --- the (wrote, row) mapping ------------------------------------------------


async def test_a_write_answers_the_row_and_records_one_audit_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = _staff_user(break_started_at=NOW)
    writes = _install(monkeypatch, wrote=True, row=target)
    actor = _actor(StaffRole.OWNER)

    result, _ = await _service().start_break(TENANT_ID, target.id, actor=actor)

    assert result is target
    assert writes.calls[0]["at"] == NOW
    assert writes.audit == [
        {
            "action": AuditAction.STAFF_BREAK_STARTED.value,
            "actor_id": actor.id,
            "entity": str(target.id),
            "details": {"target": str(target.id), "break_started_at": NOW.isoformat()},
        }
    ]


async def test_a_no_op_answers_the_row_unchanged_and_records_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """200-unchanged, and the FIRST toggler's timestamp survives. An audit row
    here would assert that this staffer started a break she did not start."""
    target = _staff_user(break_started_at=BREAK_BEGAN)
    writes = _install(monkeypatch, wrote=False, row=target)

    result, _ = await _service().start_break(TENANT_ID, target.id, actor=_actor(StaffRole.OWNER))

    assert result is target
    assert result.break_started_at == BREAK_BEGAN
    assert writes.audit == []
    assert "audit" not in writes.order


async def test_a_missing_target_is_a_404_for_an_elevated_caller(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`(False, None)` — deactivated, another tenant's, or never existed, and
    the three are deliberately indistinguishable."""
    writes = _install(monkeypatch, wrote=False, row=None)

    with pytest.raises(DomainNotFoundError):
        await _service().start_break(TENANT_ID, uuid.uuid4(), actor=_actor(StaffRole.OWNER))
    with pytest.raises(DomainNotFoundError):
        await _service().end_break(TENANT_ID, uuid.uuid4(), actor=_actor(StaffRole.OWNER))

    assert writes.audit == []


# --- the end, and the value it destroys --------------------------------------


async def test_the_end_audit_row_carries_the_timestamp_captured_before_the_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ `previous_break_started_at` is load-bearing: ending a break DESTROYS the
    only copy of when it began, and there is no history table (D2). F34's
    `previous_checked_in_at` is the same shape.

    It must be read into a local BEFORE the write, and that is not style — the
    repository's UPDATE is ORM-enabled DML whose `evaluate` synchronization
    stamps `break_started_at = NULL` onto the very instance `by_id` just handed
    back, so reading it afterwards records `null` and empties the trail this row
    exists for (`booking/owner.py:326-333`, the identical trap on `from_status`).
    """
    before = _staff_user(break_started_at=BREAK_BEGAN)
    after = _staff_user(break_started_at=None)
    after.id = before.id
    writes = _install(monkeypatch, wrote=True, row=after, before=before)
    actor = _actor(StaffRole.SHIFT_MANAGER)

    result, _ = await _service().end_break(TENANT_ID, before.id, actor=actor)

    assert result is after
    assert writes.order == ["by_id", "end_break", "audit"]
    assert writes.audit == [
        {
            "action": AuditAction.STAFF_BREAK_ENDED.value,
            "actor_id": actor.id,
            "entity": str(before.id),
            "details": {
                "target": str(before.id),
                "previous_break_started_at": BREAK_BEGAN.isoformat(),
            },
        }
    ]


async def test_an_end_on_a_staffer_who_was_not_on_a_break_records_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = _staff_user(break_started_at=None)
    writes = _install(monkeypatch, wrote=False, row=target, before=target)

    result, _ = await _service().end_break(TENANT_ID, target.id, actor=_actor(StaffRole.OWNER))

    assert result is target
    assert writes.audit == []


async def test_a_self_toggle_still_writes_an_audit_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D8 considered and DECLINED the asymmetric rule. A break is a fact about
    the floor whoever recorded it, and a trail with holes in it where people
    acted on themselves is worse than no trail."""
    me = _staff_user(role=StaffRole.SEAMSTRESS.value, break_started_at=NOW)
    writes = _install(monkeypatch, wrote=True, row=me)
    actor = _actor(StaffRole.SEAMSTRESS, me.id)

    await _service().start_break(TENANT_ID, me.id, actor=actor)

    assert len(writes.audit) == 1
    assert writes.audit[0]["actor_id"] == actor.id
    assert writes.audit[0]["entity"] == str(me.id)


# --- status derivation -------------------------------------------------------


def test_status_is_break_iff_a_break_is_open() -> None:
    assert card_status(_staff_user(break_started_at=NOW), occupied=False) is StaffCardStatus.BREAK
    assert (
        card_status(_staff_user(break_started_at=None), occupied=False) is StaffCardStatus.AVAILABLE
    )


def test_the_card_status_wire_literals_are_exactly_available_break_and_occupied() -> None:
    """⚠ SET EQUALITY, and it is still the test that refuses a value with no
    writer.

    F36 gives `occupied` one — an open `fitting_room_assignments` row — and
    widens this in the same PR, which is `ScheduledMessageKind`'s rule MET
    rather than waived. A fourth value added ahead of its producer fails here.
    """
    assert {status.value for status in StaffCardStatus} == {"available", "break", "occupied"}


# =============================================================================
# F36 — the rooms. Every branch of the claim, the release, the handover, the two
# dress routes and the registry, on fakes and with no Postgres.
#
# All seven of this task's mutations were RUN. Six go RED here; the results
# where they differ from what the plan predicted are recorded because a test
# whose reach is guessed is a test nobody can trust:
#
#   - branching on the constraint name instead of the request-keyed read was
#     predicted GREEN and is RED, because
#     `test_re_claiming_your_own_room_is_a_200_whichever_index_reports` is
#     PARAMETRISED over both index names. A fake reports whichever name the test
#     hands it, so covering both is what makes the ordering visible with no
#     Postgres at all.
#   - capturing the handover's `from` AFTER the write was predicted GREEN and is
#     RED — but only on the explicit `order.index(...)` assertion, i.e. this
#     module catches the CODE MOTION and not its effect. A monkeypatched writer
#     stamps nothing onto an identity map, so the actual corruption (the new
#     staffer recorded as the old one) is still only visible in the db suite.
#
# ONE mutation stays GREEN here and that is the finding, not a failure:
# deleting `session.begin_nested()` changes nothing, because a fake repository
# raises its IntegrityError with no real flush to abort and no transaction to
# keep alive. It is pinned by a forced interleave. (`populate_existing=True` on
# the release re-read is the same class and belongs to the repository module,
# where it is already recorded.)
# =============================================================================

ROOM_ID = uuid.uuid4()
ASSIGNMENT_ID = uuid.uuid4()
BOOKING_ID = uuid.uuid4()
DRESS_ID = uuid.uuid4()
BINDING_ID = uuid.uuid4()
CLAIMED_AT = datetime.datetime(2026, 8, 2, 10, 0, tzinfo=datetime.UTC)
# NOW is 2026-08-02 11:20 UTC, i.e. 14:20 in Jerusalem, so this is today there.
TODAY_START = datetime.datetime(2026, 8, 2, 9, 30, tzinfo=datetime.UTC)


def _room(**overrides: object) -> FittingRoom:
    row = FittingRoom(tenant_id=TENANT_ID, label="חדר 2", sort_order=1, is_active=True)
    row.id = ROOM_ID
    for key, value in overrides.items():
        setattr(row, key, value)
    return row


def _room_row(**overrides: Any) -> RoomRow:
    return dataclasses.replace(
        RoomRow(
            room_id=ROOM_ID,
            label="חדר 2",
            sort_order=1,
            is_active=True,
            assignment_id=None,
            staff_user_id=None,
            staff_display_name=None,
            staff_role=None,
            booking_id=None,
            client_label=None,
            assigned_at=None,
        ),
        **overrides,
    )


def _occupied_room_row(staff_id: uuid.UUID) -> RoomRow:
    return _room_row(
        assignment_id=ASSIGNMENT_ID,
        staff_user_id=staff_id,
        staff_display_name="דנה כהן",
        staff_role=StaffRole.SEAMSTRESS.value,
        client_label="מיכל",
        assigned_at=CLAIMED_AT,
    )


def _assignment(staff_id: uuid.UUID, **overrides: object) -> FittingRoomAssignment:
    row = FittingRoomAssignment(
        tenant_id=TENANT_ID, fitting_room_id=ROOM_ID, staff_user_id=staff_id, booking_id=None
    )
    row.id = ASSIGNMENT_ID
    row.released_at = None
    for key, value in overrides.items():
        setattr(row, key, value)
    return row


def _booking(**overrides: object) -> Booking:
    row = Booking(
        tenant_id=TENANT_ID,
        customer_id=uuid.uuid4(),
        appointment_type_id=uuid.uuid4(),
        appointment_type_name="מדידה",
        starts_at=TODAY_START,
        seat_index=1,
        status=BookingStatus.CONFIRMED.value,
        terms_version_accepted=1,
        terms_accepted_at=TODAY_START,
    )
    row.id = BOOKING_ID
    row.checked_in_at = NOW
    for key, value in overrides.items():
        setattr(row, key, value)
    return row


class _UniqueViolation(Exception):
    """asyncpg's `UniqueViolationError` in the only respect the discriminator
    cares about. It reaches the service as `IntegrityError.orig.__cause__` —
    NOT as `orig` itself, which is SQLAlchemy's own re-wrapped string."""

    def __init__(self, constraint_name: str | None) -> None:
        super().__init__("duplicate key value violates unique constraint")
        self.constraint_name = constraint_name


def _integrity_error(constraint: str | None) -> IntegrityError:
    orig = Exception("duplicate key value violates unique constraint")
    orig.__cause__ = _UniqueViolation(constraint)
    return IntegrityError("INSERT INTO fitting_room_assignments ...", None, orig)


class _Rig:
    """One recorder for every room repository. `order` is what proves the two
    ordering rules the feature actually depends on: the 403 before the room
    read, and the occupancy guard after the row lock."""

    def __init__(self) -> None:
        self.order: list[str] = []
        self.audit: list[dict[str, Any]] = []
        self.calls: list[dict[str, Any]] = []
        self.room: FittingRoom | None = _room()
        self.room_row: RoomRow = _room_row()
        self.booking: Booking | None = None
        self.dress: Dress | None = None
        self.assignment: FittingRoomAssignment | None = None
        self.active_assignment: FittingRoomAssignment | None = None
        self.claim_error: IntegrityError | None = None
        self.idempotent: FittingRoomAssignment | None = None
        self.occupant: FittingRoomAssignment | None = None
        self.occupant_staff: StaffUser | None = None
        self.staff_room: FittingRoomAssignment | None = None
        self.occupied_room: FittingRoom | None = None
        self.release_result: tuple[bool, FittingRoomAssignment | None] = (True, None)
        self.handover_result: tuple[bool, FittingRoomAssignment | None] = (True, None)
        self.handover_error: IntegrityError | None = None
        self.has_active = False
        self.occupancy: RoomRow | None = None
        self.dress_added = True
        self.dress_removed = True


def _install_rooms(monkeypatch: pytest.MonkeyPatch, rig: _Rig) -> _Rig:
    def _record(name: str, **payload: Any) -> None:
        rig.order.append(name)
        if payload:
            rig.calls.append({"call": name, **payload})

    async def _by_id_for_update(_s: Any, _sess: Any, _t: Any, room_id: uuid.UUID) -> Any:
        _record("room_for_update", room_id=room_id)
        return rig.room

    async def _room_by_id(_s: Any, _sess: Any, _t: Any, room_id: uuid.UUID) -> Any:
        _record("room_by_id")
        return rig.occupied_room

    async def _room_with_occupancy(_s: Any, _sess: Any, _t: Any, _room_id: uuid.UUID) -> Any:
        _record("room_with_occupancy")
        return rig.room_row

    async def _occupancy_for_staff(_s: Any, _sess: Any, _t: Any, _staff_id: uuid.UUID) -> Any:
        _record("occupancy_for_staff")
        return rig.occupancy

    async def _insert(_s: Any, _sess: Any, _t: Any, **kwargs: Any) -> Any:
        _record("room_insert", **kwargs)
        return rig.room

    async def _update(_s: Any, _sess: Any, _t: Any, room_id: uuid.UUID, **kwargs: Any) -> Any:
        _record("room_update", **kwargs)
        return rig.room

    async def _soft_delete(_s: Any, _sess: Any, _t: Any, _room_id: uuid.UUID) -> bool:
        _record("room_soft_delete")
        return True

    async def _claim(_s: Any, _sess: Any, _t: Any, **kwargs: Any) -> Any:
        _record("claim", **kwargs)
        if rig.claim_error is not None:
            raise rig.claim_error
        return _assignment(kwargs["staff_id"])

    async def _active_for(_s: Any, _sess: Any, _t: Any, _room: Any, _staff: Any) -> Any:
        _record("active_for")
        return rig.idempotent

    async def _occupant_of_room(_s: Any, _sess: Any, _t: Any, _room: Any) -> Any:
        _record("occupant_of_room")
        return rig.occupant

    async def _room_of_staff(_s: Any, _sess: Any, _t: Any, _staff: Any) -> Any:
        _record("room_of_staff")
        return rig.staff_room

    async def _has_active(_s: Any, _sess: Any, _t: Any, _room: Any) -> bool:
        _record("has_active_for_room")
        return rig.has_active

    async def _assignment_by_id(_s: Any, _sess: Any, _t: Any, _id: uuid.UUID) -> Any:
        _record("assignment_by_id")
        return rig.assignment

    async def _assignment_active_by_id(_s: Any, _sess: Any, _t: Any, _id: uuid.UUID) -> Any:
        _record("assignment_active_by_id")
        return rig.active_assignment

    async def _release(_s: Any, _sess: Any, _t: Any, _id: uuid.UUID, *, at: Any) -> Any:
        _record("release", at=at)
        return rig.release_result

    async def _handover(_s: Any, _sess: Any, _t: Any, _id: uuid.UUID, *, new_staff_id: Any) -> Any:
        _record("handover", new_staff_id=new_staff_id)
        if rig.handover_error is not None:
            raise rig.handover_error
        return rig.handover_result

    async def _add(_s: Any, _sess: Any, _t: Any, **kwargs: Any) -> Any:
        _record("dress_add", **kwargs)
        return rig.dress_added, object()

    async def _remove(_s: Any, _sess: Any, _t: Any, **kwargs: Any) -> bool:
        _record("dress_remove", **kwargs)
        return rig.dress_removed

    async def _by_assignment_ids(_s: Any, _sess: Any, _t: Any, ids: Any) -> dict[Any, list[Any]]:
        return {}

    async def _booking_by_id(_s: Any, _sess: Any, _t: Any, _id: uuid.UUID) -> Any:
        _record("booking_by_id")
        return rig.booking

    async def _dress_by_id(_s: Any, _sess: Any, _t: Any, _id: uuid.UUID) -> Any:
        _record("dress_by_id")
        return rig.dress

    async def _staff_by_id(_s: Any, _sess: Any, _t: Any, _id: uuid.UUID) -> Any:
        _record("staff_by_id")
        return rig.occupant_staff

    async def _audit_record(
        _s: Any,
        _sess: Any,
        *,
        tenant_id: uuid.UUID,
        action: str,
        actor_id: uuid.UUID | None = None,
        entity: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        rig.order.append("audit")
        rig.audit.append(
            {"action": action, "actor_id": actor_id, "entity": entity, "details": details}
        )

    monkeypatch.setattr(FittingRoomsRepository, "by_id_for_update", _by_id_for_update)
    monkeypatch.setattr(FittingRoomsRepository, "by_id", _room_by_id)
    monkeypatch.setattr(FittingRoomsRepository, "room_with_occupancy", _room_with_occupancy)
    monkeypatch.setattr(FittingRoomsRepository, "occupancy_for_staff", _occupancy_for_staff)
    monkeypatch.setattr(FittingRoomsRepository, "insert", _insert)
    monkeypatch.setattr(FittingRoomsRepository, "update", _update)
    monkeypatch.setattr(FittingRoomsRepository, "soft_delete", _soft_delete)
    monkeypatch.setattr(FittingRoomAssignmentsRepository, "claim", _claim)
    monkeypatch.setattr(FittingRoomAssignmentsRepository, "active_for", _active_for)
    monkeypatch.setattr(FittingRoomAssignmentsRepository, "occupant_of_room", _occupant_of_room)
    monkeypatch.setattr(FittingRoomAssignmentsRepository, "room_of_staff", _room_of_staff)
    monkeypatch.setattr(FittingRoomAssignmentsRepository, "has_active_for_room", _has_active)
    monkeypatch.setattr(FittingRoomAssignmentsRepository, "by_id", _assignment_by_id)
    monkeypatch.setattr(FittingRoomAssignmentsRepository, "active_by_id", _assignment_active_by_id)
    monkeypatch.setattr(FittingRoomAssignmentsRepository, "release", _release)
    monkeypatch.setattr(FittingRoomAssignmentsRepository, "handover", _handover)
    monkeypatch.setattr(FittingAssignmentDressesRepository, "add", _add)
    monkeypatch.setattr(FittingAssignmentDressesRepository, "remove", _remove)
    monkeypatch.setattr(FittingAssignmentDressesRepository, "by_assignment_ids", _by_assignment_ids)
    monkeypatch.setattr(BookingsRepository, "by_id", _booking_by_id)
    monkeypatch.setattr(DressesRepository, "by_id", _dress_by_id)
    monkeypatch.setattr(StaffUsersRepository, "by_id", _staff_by_id)
    monkeypatch.setattr(AuditLogRepository, "record", _audit_record)
    return rig


# --- the claim's authorization matrix (D6 / AC23) -----------------------------


@pytest.mark.parametrize("role", ELEVATED)
async def test_an_elevated_role_may_claim_a_room_for_anybody(
    monkeypatch: pytest.MonkeyPatch, role: StaffRole
) -> None:
    rig = _install_rooms(monkeypatch, _Rig())
    target = uuid.uuid4()

    read = await _service().claim(
        TENANT_ID, ROOM_ID, staff_user_id=target, booking_id=None, actor=_actor(role)
    )

    assert read.row.room_id == ROOM_ID
    assert rig.calls[1] == {
        "call": "claim",
        "room_id": ROOM_ID,
        "staff_id": target,
        "booking_id": None,
    }


@pytest.mark.parametrize("role", FLOOR)
async def test_a_floor_role_may_claim_a_room_for_herself(
    monkeypatch: pytest.MonkeyPatch, role: StaffRole
) -> None:
    """`staff_user_id` omitted defaults to the caller — one tap, no picker."""
    rig = _install_rooms(monkeypatch, _Rig())
    actor = _actor(role)

    await _service().claim(TENANT_ID, ROOM_ID, staff_user_id=None, booking_id=None, actor=actor)

    assert rig.calls[1]["staff_id"] == actor.id


@pytest.mark.parametrize("role", FLOOR)
async def test_a_floor_role_claiming_for_a_colleague_is_refused_without_reading_the_room(
    monkeypatch: pytest.MonkeyPatch, role: StaffRole
) -> None:
    """⚠ AC23, and the empty `order` is the assertion — not the exception.

    F36 is the FIRST feature in the product to take a target staff id in a
    BODY, which is the exact shape `_authorize`'s docstring names as the hazard.
    The body field is read ONLY as the target; the actor comes from the session
    cookie. Running the check after the room read would make the 403 an
    existence oracle for room ids.
    """
    rig = _install_rooms(monkeypatch, _Rig())
    actor = _actor(role)
    colleague = uuid.uuid4()

    with pytest.raises(NotAuthorizedError):
        await _service().claim(
            TENANT_ID, ROOM_ID, staff_user_id=colleague, booking_id=None, actor=actor
        )

    assert rig.order == []
    assert rig.audit == []


# --- the claim's reads --------------------------------------------------------


@pytest.mark.parametrize("room", [None, _room(is_active=False)])
async def test_a_claim_on_a_missing_or_INACTIVE_room_is_one_indistinguishable_404(
    monkeypatch: pytest.MonkeyPatch, room: FittingRoom | None
) -> None:
    """Inactive is a 404 rather than a fifth error code: the panel renders no
    claim control on an inactive room, so reaching this branch means the client
    was one tick stale."""
    rig = _Rig()
    rig.room = room
    _install_rooms(monkeypatch, rig)

    with pytest.raises(DomainNotFoundError):
        await _service().claim(
            TENANT_ID, ROOM_ID, staff_user_id=None, booking_id=None, actor=_actor(StaffRole.OWNER)
        )


@pytest.mark.parametrize(
    "booking",
    [
        None,
        _booking(checked_in_at=None),
        _booking(status=BookingStatus.CANCELLED.value),
        _booking(starts_at=TODAY_START + datetime.timedelta(days=30)),
    ],
    ids=["missing", "not-checked-in", "cancelled", "not-today"],
)
async def test_a_booking_that_has_not_checked_in_cannot_be_bound_to_a_room(
    monkeypatch: pytest.MonkeyPatch, booking: Booking | None
) -> None:
    """⚠ The check-in predicate is what makes the no-snapshot privacy argument
    TRUE rather than aspirational. `deleted_at IS NULL AND status <> 'cancelled'`
    alone admits NEXT MONTH's booking, whose customer's name would then surface
    on a five-role payload for as long as the assignment stayed open."""
    rig = _Rig()
    rig.booking = booking
    _install_rooms(monkeypatch, rig)

    with pytest.raises(DomainNotFoundError):
        await _service().claim(
            TENANT_ID,
            ROOM_ID,
            staff_user_id=None,
            booking_id=BOOKING_ID,
            actor=_actor(StaffRole.OWNER),
        )


async def test_a_pending_payment_booking_is_admitted_deliberately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stated because the rule elsewhere is the opposite: every owner and
    customer verb 409s on an unpaid hold. Here the bride is physically standing
    in the boutique having been checked in, and refusing to name her on a room
    tile over a deposit is the product being clever at her expense."""
    rig = _Rig()
    rig.booking = _booking(status=BookingStatus.PENDING_PAYMENT.value)
    _install_rooms(monkeypatch, rig)

    await _service().claim(
        TENANT_ID, ROOM_ID, staff_user_id=None, booking_id=BOOKING_ID, actor=_actor(StaffRole.OWNER)
    )

    assert rig.audit[0]["details"]["booking"] == str(BOOKING_ID)


# --- the claim's conflicts ----------------------------------------------------


@pytest.mark.parametrize("reported", [ROOM_ACTIVE_INDEX, STAFF_ACTIVE_INDEX])
async def test_re_claiming_your_own_room_is_a_200_whichever_index_reports(
    monkeypatch: pytest.MonkeyPatch, reported: str
) -> None:
    """⚠ IDEMPOTENCE IS KEYED ON THE REQUEST, NEVER ON THE CONSTRAINT NAME.

    A re-claim violates BOTH partial unique indexes at once and Postgres reports
    only the first that fails, in index-OID order — i.e. migration creation
    order, which flips after any REINDEX CONCURRENTLY or pg_repack. If the staff
    index reported first, a staffer tapping the room she is standing in would
    read «היא כבר בחדר 2.»: the screen refusing her with the name of the room
    she is in. So the request-keyed read runs FIRST and both parametrisations
    answer 200.
    """
    rig = _Rig()
    rig.claim_error = _integrity_error(reported)
    rig.idempotent = _assignment(uuid.uuid4())
    rig.room_row = _occupied_room_row(uuid.uuid4())
    _install_rooms(monkeypatch, rig)

    read = await _service().claim(
        TENANT_ID, ROOM_ID, staff_user_id=None, booking_id=None, actor=_actor(StaffRole.SEAMSTRESS)
    )

    assert read.row.assignment_id == ASSIGNMENT_ID
    assert rig.audit == []
    assert "occupant_of_room" not in rig.order
    assert "room_of_staff" not in rig.order


async def test_a_room_conflict_names_the_occupant(monkeypatch: pytest.MonkeyPatch) -> None:
    rig = _Rig()
    rig.claim_error = _integrity_error(ROOM_ACTIVE_INDEX)
    rig.occupant = _assignment(uuid.uuid4())
    rig.occupant_staff = _staff_user(display_name="דנה")
    _install_rooms(monkeypatch, rig)

    with pytest.raises(RoomOccupiedError) as caught:
        await _service().claim(
            TENANT_ID, ROOM_ID, staff_user_id=None, booking_id=None, actor=_actor(StaffRole.OWNER)
        )

    assert caught.value.details == {"staff_display_name": "דנה"}
    assert rig.audit == []


async def test_a_staff_conflict_names_the_room_she_is_already_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rig = _Rig()
    rig.claim_error = _integrity_error(STAFF_ACTIVE_INDEX)
    rig.staff_room = _assignment(uuid.uuid4())
    rig.occupied_room = _room(label="חדר 2")
    _install_rooms(monkeypatch, rig)

    with pytest.raises(StaffOccupiedError) as caught:
        await _service().claim(
            TENANT_ID, ROOM_ID, staff_user_id=None, booking_id=None, actor=_actor(StaffRole.OWNER)
        )

    assert caught.value.details == {"room_label": "חדר 2"}


@pytest.mark.parametrize(
    ("reported", "error"),
    [(ROOM_ACTIVE_INDEX, RoomOccupiedError), (STAFF_ACTIVE_INDEX, StaffOccupiedError)],
)
async def test_a_claim_whose_occupant_released_first_does_not_name_nobody(
    monkeypatch: pytest.MonkeyPatch, reported: str, error: type[Exception]
) -> None:
    """The loser blocks on the winner's uncommitted index key and gets the
    violation when the winner commits — and a fitting can end in the seconds a
    claim is queued, so the occupant read legitimately comes back empty."""
    rig = _Rig()
    rig.claim_error = _integrity_error(reported)
    _install_rooms(monkeypatch, rig)

    with pytest.raises(error) as caught:
        await _service().claim(
            TENANT_ID, ROOM_ID, staff_user_id=None, booking_id=None, actor=_actor(StaffRole.OWNER)
        )

    assert caught.value.details is None  # type: ignore[attr-defined]


@pytest.mark.parametrize("reported", [None, "idx_something_nobody_predicted"])
async def test_an_unrecognised_constraint_violation_is_re_raised(
    monkeypatch: pytest.MonkeyPatch, reported: str | None
) -> None:
    """A 500 on a violation nobody predicted is correct. Silently mapping it to
    ROOM_OCCUPIED would tell a staffer a lie about furniture."""
    rig = _Rig()
    rig.claim_error = _integrity_error(reported)
    _install_rooms(monkeypatch, rig)

    with pytest.raises(IntegrityError):
        await _service().claim(
            TENANT_ID, ROOM_ID, staff_user_id=None, booking_id=None, actor=_actor(StaffRole.OWNER)
        )


async def test_a_claim_that_inserted_records_one_audit_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rig = _install_rooms(monkeypatch, _Rig())
    actor = _actor(StaffRole.SHIFT_MANAGER)
    target = uuid.uuid4()

    await _service().claim(TENANT_ID, ROOM_ID, staff_user_id=target, booking_id=None, actor=actor)

    assert rig.audit == [
        {
            "action": AuditAction.FITTING_ROOM_CLAIMED.value,
            "actor_id": actor.id,
            "entity": str(ROOM_ID),
            "details": {
                "room": str(ROOM_ID),
                "assignment": str(ASSIGNMENT_ID),
                "staff": str(target),
                "booking": None,
            },
        }
    ]


# --- the release (D7) ---------------------------------------------------------


@pytest.mark.parametrize("role", FLOOR)
async def test_a_non_elevated_caller_releasing_a_colleagues_assignment_gets_a_404(
    monkeypatch: pytest.MonkeyPatch, role: StaffRole
) -> None:
    """⚠ 404, NOT 403, and the "repository was never called" assertion does NOT
    apply here.

    The claim's target is a staff id in the body, so its check can be the first
    statement. Release's target is an ASSIGNMENT id, and whose it is can only be
    learned by reading the row — so the refusal must be byte-identical to the
    missing case, or a 403 on a real id and a 404 on a fake one would
    discriminate existence.
    """
    rig = _Rig()
    rig.assignment = _assignment(uuid.uuid4())
    _install_rooms(monkeypatch, rig)

    with pytest.raises(DomainNotFoundError):
        await _service().release(TENANT_ID, ASSIGNMENT_ID, actor=_actor(role))

    assert "release" not in rig.order
    assert rig.audit == []


async def test_a_release_that_wrote_records_one_audit_row_and_stamps_the_service_clock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rig = _Rig()
    actor = _actor(StaffRole.SEAMSTRESS)
    rig.assignment = _assignment(actor.id)
    rig.release_result = (True, _assignment(actor.id, released_at=NOW))
    _install_rooms(monkeypatch, rig)

    await _service().release(TENANT_ID, ASSIGNMENT_ID, actor=actor)

    assert {call["at"] for call in rig.calls if call["call"] == "release"} == {NOW}
    assert rig.audit == [
        {
            "action": AuditAction.FITTING_ROOM_RELEASED.value,
            "actor_id": actor.id,
            "entity": str(ASSIGNMENT_ID),
            "details": {
                "room": str(ROOM_ID),
                "assignment": str(ASSIGNMENT_ID),
                "staff": str(actor.id),
            },
        }
    ]


async def test_a_second_release_answers_the_room_and_records_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rowcount 0 with a live row back: she wanted the room free and the room is
    free. A `{released → released}` audit row would be noise in the only trail
    this area has."""
    rig = _Rig()
    actor = _actor(StaffRole.OWNER)
    rig.assignment = _assignment(actor.id, released_at=NOW)
    rig.release_result = (False, _assignment(actor.id, released_at=NOW))
    _install_rooms(monkeypatch, rig)

    read = await _service().release(TENANT_ID, ASSIGNMENT_ID, actor=actor)

    assert read.row.room_id == ROOM_ID
    assert rig.audit == []


async def test_a_release_of_an_unknown_assignment_is_a_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rig = _Rig()
    rig.assignment = None
    _install_rooms(monkeypatch, rig)

    with pytest.raises(DomainNotFoundError):
        await _service().release(TENANT_ID, ASSIGNMENT_ID, actor=_actor(StaffRole.OWNER))


# --- the handover (D8) --------------------------------------------------------


@pytest.mark.parametrize("role", FLOOR)
async def test_the_handover_carries_no_service_role_check_because_the_route_gate_owns_it(
    monkeypatch: pytest.MonkeyPatch, role: StaffRole
) -> None:
    """⚠ D8's asymmetry, asserted as the ABSENCE it is — a permissiveness that
    arrives by omission is invisible, and a reader WILL doubt this one.

    Handover's predicate depends on nothing about the target, so it is a pure
    role predicate, which is precisely what `RoleGate` is — and the route gate is
    where it lives, so `FLOOR_OPEN` keeps describing the product and a control a
    seamstress can see never produces the terminal 403 that blanks her only
    screen. `test_staff_role_gating.py` is what asserts the refusal.
    """
    rig = _Rig()
    actor = _actor(role)
    rig.assignment = _assignment(actor.id)
    rig.handover_result = (True, _assignment(uuid.uuid4()))
    _install_rooms(monkeypatch, rig)

    await _service().handover(TENANT_ID, ASSIGNMENT_ID, new_staff_id=uuid.uuid4(), actor=actor)

    assert "handover" in rig.order


async def test_the_handover_audit_row_carries_the_holder_captured_before_the_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ `from` is read into a local BEFORE the writer runs. The UPDATE is
    ORM-enabled DML whose `evaluate` synchronization stamps the new value onto
    the same identity-mapped instance, so reading it afterwards records the NEW
    staffer as the OLD one and empties the row of its whole informational
    content. This assertion CANNOT see that mutation — a monkeypatched writer
    stamps nothing — so the ordering is pinned in the db suite instead."""
    rig = _Rig()
    previous = uuid.uuid4()
    incoming = uuid.uuid4()
    actor = _actor(StaffRole.OWNER)
    rig.assignment = _assignment(previous)
    rig.handover_result = (True, _assignment(incoming))
    _install_rooms(monkeypatch, rig)

    await _service().handover(TENANT_ID, ASSIGNMENT_ID, new_staff_id=incoming, actor=actor)

    assert rig.order.index("assignment_by_id") < rig.order.index("handover")
    assert rig.audit == [
        {
            "action": AuditAction.FITTING_ROOM_HANDED_OVER.value,
            "actor_id": actor.id,
            "entity": str(ASSIGNMENT_ID),
            "details": {
                "assignment": str(ASSIGNMENT_ID),
                "from": str(previous),
                "to": str(incoming),
            },
        }
    ]


async def test_a_handover_to_a_staffer_who_already_holds_a_room_is_a_staff_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The second index earning its keep on a path that is not the claim."""
    rig = _Rig()
    rig.assignment = _assignment(uuid.uuid4())
    rig.handover_error = _integrity_error(STAFF_ACTIVE_INDEX)
    rig.staff_room = _assignment(uuid.uuid4())
    rig.occupied_room = _room(label="חדר 5")
    _install_rooms(monkeypatch, rig)

    with pytest.raises(StaffOccupiedError) as caught:
        await _service().handover(
            TENANT_ID, ASSIGNMENT_ID, new_staff_id=uuid.uuid4(), actor=_actor(StaffRole.OWNER)
        )

    assert caught.value.details == {"room_label": "חדר 5"}
    assert rig.audit == []


async def test_a_handover_on_an_already_released_assignment_is_a_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rig = _Rig()
    rig.assignment = _assignment(uuid.uuid4())
    rig.handover_result = (False, None)
    _install_rooms(monkeypatch, rig)

    with pytest.raises(DomainNotFoundError):
        await _service().handover(
            TENANT_ID, ASSIGNMENT_ID, new_staff_id=uuid.uuid4(), actor=_actor(StaffRole.OWNER)
        )

    assert rig.audit == []


# --- the two dress routes (D4) ------------------------------------------------


@pytest.mark.parametrize("role", FLOOR)
async def test_a_floor_role_may_bind_a_dress_to_a_colleagues_assignment(
    monkeypatch: pytest.MonkeyPatch, role: StaffRole
) -> None:
    """⚠ A POSITIVE assertion of a permissiveness, because one that arrives by
    default is invisible. A colleague fetching a second gown for a fitting
    already in progress is the normal case on a shop floor; binding a dress is
    not a destructive act on the HOLDER's room, which is why release and
    handover carry the two axes and these two do not. `removed_by` is what keeps
    it accountable."""
    rig = _Rig()
    rig.active_assignment = _assignment(uuid.uuid4())
    rig.dress = Dress(tenant_id=TENANT_ID, name="ורוניק", sort_order=0)
    _install_rooms(monkeypatch, rig)

    await _service().add_dress(
        TENANT_ID, ASSIGNMENT_ID, dress_id=DRESS_ID, size_label="38", actor=_actor(role)
    )

    assert {"dress_add"} <= set(rig.order)
    assert rig.audit == []


@pytest.mark.parametrize("role", FLOOR)
async def test_a_floor_role_may_unbind_a_dress_from_a_colleagues_assignment(
    monkeypatch: pytest.MonkeyPatch, role: StaffRole
) -> None:
    rig = _Rig()
    actor = _actor(role)
    rig.active_assignment = _assignment(uuid.uuid4())
    _install_rooms(monkeypatch, rig)

    await _service().remove_dress(TENANT_ID, ASSIGNMENT_ID, BINDING_ID, actor=actor)

    removes = [call for call in rig.calls if call["call"] == "dress_remove"]
    assert removes[0]["actor_id"] == actor.id
    assert removes[0]["at"] == NOW
    assert rig.audit == []


async def test_a_duplicate_dress_add_writes_nothing_new_and_still_answers_the_room(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two staffers tapping «שמלה 47» at the same instant both want the dress in
    the room, and the dress is in the room."""
    rig = _Rig()
    rig.active_assignment = _assignment(uuid.uuid4())
    rig.dress = Dress(tenant_id=TENANT_ID, name="ורוניק", sort_order=0)
    rig.dress_added = False
    _install_rooms(monkeypatch, rig)

    read = await _service().add_dress(
        TENANT_ID, ASSIGNMENT_ID, dress_id=DRESS_ID, size_label=None, actor=_actor(StaffRole.OWNER)
    )

    assert read.row.room_id == ROOM_ID
    assert rig.audit == []


@pytest.mark.parametrize("verb", ["add", "remove"])
async def test_a_dress_route_on_a_released_assignment_is_a_404(
    monkeypatch: pytest.MonkeyPatch, verb: str
) -> None:
    rig = _Rig()
    rig.active_assignment = None
    _install_rooms(monkeypatch, rig)
    service = _service()

    with pytest.raises(DomainNotFoundError):
        if verb == "add":
            await service.add_dress(
                TENANT_ID,
                ASSIGNMENT_ID,
                dress_id=DRESS_ID,
                size_label=None,
                actor=_actor(StaffRole.OWNER),
            )
        else:
            await service.remove_dress(
                TENANT_ID, ASSIGNMENT_ID, BINDING_ID, actor=_actor(StaffRole.OWNER)
            )


async def test_an_unknown_binding_is_a_404(monkeypatch: pytest.MonkeyPatch) -> None:
    rig = _Rig()
    rig.active_assignment = _assignment(uuid.uuid4())
    rig.dress_removed = False
    _install_rooms(monkeypatch, rig)

    with pytest.raises(DomainNotFoundError):
        await _service().remove_dress(
            TENANT_ID, ASSIGNMENT_ID, BINDING_ID, actor=_actor(StaffRole.OWNER)
        )


# --- the registry (D1 / D13) --------------------------------------------------


async def test_a_room_label_is_normalised_before_it_reaches_the_repository(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rig = _install_rooms(monkeypatch, _Rig())

    await _service().create_room(
        TENANT_ID, label="  חדר 4  ", sort_order=3, actor=_actor(StaffRole.OWNER)
    )

    inserts = [call for call in rig.calls if call["call"] == "room_insert"]
    assert inserts == [{"call": "room_insert", "label": "חדר 4", "sort_order": 3}]
    assert rig.audit == []


async def test_an_empty_room_label_never_opens_a_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The 400 is a pure decision, so it is taken before the pool checkout."""
    rig = _install_rooms(monkeypatch, _Rig())

    with pytest.raises(FloorValidationError):
        await _service().create_room(
            TENANT_ID, label="   ", sort_order=0, actor=_actor(StaffRole.OWNER)
        )

    assert rig.order == []


async def test_deleting_an_occupied_room_is_a_conflict_naming_the_occupant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A soft-deleted room holding a live assignment is a row no read surfaces:
    there would be NO UI path to release it, the staffer's key would stay in the
    staff index forever, and recovery would need psql."""
    rig = _Rig()
    rig.has_active = True
    rig.occupant = _assignment(uuid.uuid4())
    rig.occupant_staff = _staff_user(display_name="דנה")
    _install_rooms(monkeypatch, rig)

    with pytest.raises(RoomOccupiedError) as caught:
        await _service().delete_room(TENANT_ID, ROOM_ID, actor=_actor(StaffRole.OWNER))

    assert caught.value.details == {"staff_display_name": "דנה"}
    assert "room_soft_delete" not in rig.order


async def test_the_occupancy_guard_is_issued_only_after_the_room_row_lock_is_held(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ AC17's ordering. A new statement snapshot taken UNDER the lock is what
    sees a claim that committed in the gap; folded into the UPDATE as a
    `NOT EXISTS` it would be evaluated against the transaction's snapshot, which
    is the unsafe count-against-a-snapshot shape."""
    rig = _install_rooms(monkeypatch, _Rig())

    await _service().delete_room(TENANT_ID, ROOM_ID, actor=_actor(StaffRole.OWNER))

    assert rig.order.index("room_for_update") < rig.order.index("has_active_for_room")
    assert rig.order.index("has_active_for_room") < rig.order.index("room_soft_delete")


async def test_the_delete_audit_row_carries_the_label_it_is_about_to_hide(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The row it names is soft-deleted and its label may be re-typed onto a new
    room tomorrow, so an id alone records that something was removed and cannot
    say what."""
    rig = _Rig()
    rig.room = _room(label="הבמה")
    _install_rooms(monkeypatch, rig)
    actor = _actor(StaffRole.OWNER)

    await _service().delete_room(TENANT_ID, ROOM_ID, actor=actor)

    assert rig.audit == [
        {
            "action": AuditAction.FITTING_ROOM_DELETED.value,
            "actor_id": actor.id,
            "entity": str(ROOM_ID),
            "details": {"room": str(ROOM_ID), "label": "הבמה"},
        }
    ]


async def test_deactivating_an_occupied_room_is_allowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ "The mirror just broke" — `is_active` stops the NEXT claim, never the
    fitting in progress. Evicting a half-dressed bride to satisfy a flag would be
    the product being clever at her expense."""
    rig = _Rig()
    rig.has_active = True
    rig.room_row = _occupied_room_row(uuid.uuid4())
    _install_rooms(monkeypatch, rig)

    read = await _service().update_room(
        TENANT_ID,
        ROOM_ID,
        label=None,
        sort_order=None,
        is_active=False,
        actor=_actor(StaffRole.OWNER),
    )

    assert read.row.assignment_id == ASSIGNMENT_ID
    assert rig.audit == []


async def test_updating_an_unknown_room_is_a_404(monkeypatch: pytest.MonkeyPatch) -> None:
    rig = _Rig()
    rig.room = None
    _install_rooms(monkeypatch, rig)

    with pytest.raises(DomainNotFoundError):
        await _service().update_room(
            TENANT_ID,
            ROOM_ID,
            label="חדר 9",
            sort_order=None,
            is_active=None,
            actor=_actor(StaffRole.OWNER),
        )


# --- occupancy on the staff card (D12) ----------------------------------------


def test_occupied_beats_break() -> None:
    """⚠ She is standing in a fitting room with a client. The break is a stale
    toggle nobody cleared, and telling a shift manager that a person she can see
    in room 2 is «בהפסקה» is the screen lying about something visible."""
    on_break = _staff_user(break_started_at=NOW)
    assert card_status(on_break, occupied=True) is StaffCardStatus.OCCUPIED
    assert card_status(on_break, occupied=False) is StaffCardStatus.BREAK
    assert (
        card_status(_staff_user(break_started_at=None), occupied=True) is StaffCardStatus.OCCUPIED
    )
    assert (
        card_status(_staff_user(break_started_at=None), occupied=False) is StaffCardStatus.AVAILABLE
    )


async def test_a_break_route_answers_occupied_when_she_is_in_a_room(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ "Pass False, it's just the break route" is the shortcut that ships a
    card contradicting the panel it lands in five seconds later."""
    target = _staff_user(break_started_at=NOW)
    _install(monkeypatch, wrote=True, row=target, before=target)
    rig = _Rig()
    rig.occupancy = _occupied_room_row(target.id)
    _install_rooms(monkeypatch, rig)

    row, occupancy = await _service().start_break(
        TENANT_ID, target.id, actor=_actor(StaffRole.OWNER)
    )
    ended_row, ended_occupancy = await _service().end_break(
        TENANT_ID, target.id, actor=_actor(StaffRole.OWNER)
    )

    assert row is target
    assert occupancy is not None
    assert card_status(row, occupied=occupancy is not None) is StaffCardStatus.OCCUPIED
    assert ended_row is target
    assert ended_occupancy is not None


async def test_the_floor_read_keys_occupancy_by_staff_id_off_the_rooms_join(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No second query for the staff cards' occupancy: it is DERIVED from the
    room rows the payload already has, which is what keeps `from_rows` a pure
    renderer and both panels renderers of their own slice."""
    holder = uuid.uuid4()
    rig = _Rig()
    _install_rooms(monkeypatch, rig)

    async def _list_live(_s: Any, _sess: Any, _t: Any) -> list[StaffUser]:
        return []

    async def _list_with_occupancy(_s: Any, _sess: Any, _t: Any) -> list[RoomRow]:
        return [_room_row(), _occupied_room_row(holder)]

    monkeypatch.setattr(StaffUsersRepository, "list_live", _list_live)
    monkeypatch.setattr(FittingRoomsRepository, "list_with_occupancy", _list_with_occupancy)

    read = await _service().floor(TENANT_ID)

    assert list(read.occupancy_by_staff_id) == [holder]
    assert len(read.room_rows) == 2
    assert read.server_now == NOW
