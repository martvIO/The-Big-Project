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
import inspect
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any, cast

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.atelier import schemas as atelier_schemas
from app.auth.dependencies import NotAuthorizedError
from app.auth.service import StaffContext
from app.db.repositories.audit_log import AuditLogRepository
from app.db.repositories.bookings import BookingsRepository
from app.db.repositories.customers import CustomersRepository
from app.db.repositories.dress_variants import DressVariantsRepository
from app.db.repositories.dresses import DressesRepository
from app.db.repositories.fitting_assignment_dresses import FittingAssignmentDressesRepository
from app.db.repositories.fitting_room_assignments import (
    ROOM_ACTIVE_INDEX,
    STAFF_ACTIVE_INDEX,
    FittingRoomAssignmentsRepository,
)
from app.db.repositories.fitting_rooms import FittingRoomsRepository, RoomRow
from app.db.repositories.queue_tickets import WAITLIST_LIMIT, QueueTicketsRepository
from app.db.repositories.roster_assignments import RosterAssignmentsRepository
from app.db.repositories.rosters import RostersRepository
from app.db.repositories.staff_notifications import StaffNotificationsRepository
from app.db.repositories.staff_users import StaffUsersRepository
from app.errors import DomainNotFoundError
from app.floor import service as app_service
from app.floor.service import (
    CLIENT_PICKER_LIMIT,
    DRESS_PICKER_LIMIT,
    FloorRead,
    FloorService,
    card_status,
)
from app.floor.validation import (
    FloorValidationError,
    QueueEmptyError,
    QueueTicketChangedError,
    QueueTicketNotWaitingError,
    RoomOccupiedError,
    StaffOccupiedError,
)
from app.models.booking import Booking
from app.models.constants import (
    AuditAction,
    BookingStatus,
    OnShiftSource,
    QueueTicketStatus,
    StaffCardStatus,
    StaffRole,
)
from app.models.customer import Customer
from app.models.dress import Dress
from app.models.fitting_room import FittingRoom
from app.models.fitting_room_assignment import FittingRoomAssignment
from app.models.staff_user import StaffUser
from app.privacy import retention as retention_module
from app.queue.validation import QueueTicketNotFoundError
from app.shifts.validation import jerusalem_moment

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


def _install_no_roster(monkeypatch: pytest.MonkeyPatch) -> None:
    """⚠ F40's DEFAULT IS RULE 3, and that is the whole of C1's promise: with no
    published `rosters` row every live staffer counts as on shift, so the board
    this suite describes is byte-identical to the pre-cutover one.

    `on_shift_staff_ids` is deliberately NOT stubbed — it is not reached at all
    when rule 2 cannot fire, and a test that had to stub it would be hiding that
    saving."""

    async def _no_roster(
        _self: object, _session: object, _tenant_id: uuid.UUID, _week_start: datetime.date
    ) -> None:
        return None

    monkeypatch.setattr(RostersRepository, "by_week", _no_roster)


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

    # ⚠ NOT recorded in `order`: F57's shipped sequence assertions are about the
    # WRITE ordering, and F40's roster read is a read added after them.
    _install_no_roster(monkeypatch)
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

    result = (await _service().start_break(TENANT_ID, target.id, actor=_actor(role))).row

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

    result = (await _service().start_break(TENANT_ID, me.id, actor=_actor(role, me.id))).row

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

    result = (await _service().start_break(TENANT_ID, target.id, actor=actor)).row

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

    result = (await _service().start_break(TENANT_ID, target.id, actor=_actor(StaffRole.OWNER))).row

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

    result = (await _service().end_break(TENANT_ID, before.id, actor=actor)).row

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

    result = (await _service().end_break(TENANT_ID, target.id, actor=_actor(StaffRole.OWNER))).row

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


def _dress(name: str) -> Dress:
    row = Dress(tenant_id=TENANT_ID, name=name, sort_order=0)
    row.id = uuid.uuid4()
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
        # F58. `None` is an empty queue, which is a 409 and not an empty 200.
        self.next_ticket: Any = _Ticket()
        self.named_ticket: Any = _Ticket()
        self.call_result: Any = _Called()
        self.skip_result: Any = _Skipped()
        self.removed = True
        self.closed = True
        self.ticket_status: tuple[str, int] | None = None
        # The panel read. Recorded in `waitlist_days` rather than in `order` or
        # `calls`, because every verb ends with it and the shipped sequence
        # assertions are about the WRITES.
        self.waiting: list[Any] = []
        self.in_service_phones: set[str] = set()
        self.waitlist_days: list[Any] = []
        self.dress_added = True
        self.dress_removed = True
        # F35's bell rows, kept out of `calls` and `order` on purpose.
        self.notifications: list[dict[str, Any]] = []


def _install_rooms(monkeypatch: pytest.MonkeyPatch, rig: _Rig) -> _Rig:
    async def _notify(
        _s: Any,
        _sess: Any,
        _t: Any,
        *,
        staff_user_id: uuid.UUID,
        actor_staff_user_id: uuid.UUID,
        kind: str,
        entity_id: uuid.UUID,
    ) -> None:
        # F35's producers fire inside three of the verbs this rig drives. Faked
        # here for the same reason every other repository is: the fake session
        # cannot serve a real INSERT. Recorded in its OWN list, never in `calls`
        # — the shipped `calls[-1] == {"call": "claim", ...}` assertions are
        # about the WRITES this file is actually about.
        rig.notifications.append(
            {
                "staff_user_id": staff_user_id,
                "actor_staff_user_id": actor_staff_user_id,
                "kind": kind,
                "entity_id": entity_id,
            }
        )
        return None

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
    monkeypatch.setattr(StaffNotificationsRepository, "insert", _notify)
    monkeypatch.setattr(FittingAssignmentDressesRepository, "add", _add)
    monkeypatch.setattr(FittingAssignmentDressesRepository, "remove", _remove)
    monkeypatch.setattr(FittingAssignmentDressesRepository, "by_assignment_ids", _by_assignment_ids)
    monkeypatch.setattr(BookingsRepository, "by_id", _booking_by_id)
    monkeypatch.setattr(DressesRepository, "by_id", _dress_by_id)
    monkeypatch.setattr(StaffUsersRepository, "by_id", _staff_by_id)

    async def _waiting_for_panel(_s: Any, _sess: Any, _t: Any, day: Any, *, limit: int) -> Any:
        rig.waitlist_days.append(day)
        assert limit == WAITLIST_LIMIT
        return rig.waiting

    async def _in_service_phones(_s: Any, _sess: Any, _t: Any, _day: Any) -> set[str]:
        return rig.in_service_phones

    monkeypatch.setattr(AuditLogRepository, "record", _audit_record)
    monkeypatch.setattr(QueueTicketsRepository, "waiting_for_panel", _waiting_for_panel)
    monkeypatch.setattr(QueueTicketsRepository, "in_service_phones", _in_service_phones)
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

    started = await _service().start_break(TENANT_ID, target.id, actor=_actor(StaffRole.OWNER))
    ended = await _service().end_break(TENANT_ID, target.id, actor=_actor(StaffRole.OWNER))
    row, occupancy = started.row, started.occupancy
    ended_row, ended_occupancy = ended.row, ended.occupancy

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
    _install_no_roster(monkeypatch)

    read = await _service().floor(TENANT_ID)

    assert list(read.occupancy_by_staff_id) == [holder]
    assert len(read.room_rows) == 2
    assert read.server_now == NOW


# --- F36: the two one-shot pickers (D16) -------------------------------------


async def test_the_dress_picker_pairs_each_gown_with_its_sizes_and_tolerates_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The sizes map is SPARSE and the pairing must survive that: a gown with no
    live variants is ordinary and binds with a null size, so a `[...]` lookup
    here would 500 the picker on the first sample dress a boutique adds."""
    sized, unsized = _dress("שמלה 47"), _dress("שמלה 12")

    async def _list_for_picker(_s: Any, _sess: Any, _t: Any, *, limit: int) -> list[Dress]:
        return [sized, unsized]

    async def _sizes(_s: Any, _sess: Any, _t: Any, ids: Any) -> dict[uuid.UUID, list[str]]:
        assert list(ids) == [sized.id, unsized.id]
        return {sized.id: ["38", "40"]}

    monkeypatch.setattr(DressesRepository, "list_for_picker", _list_for_picker)
    monkeypatch.setattr(DressVariantsRepository, "size_labels_by_dress", _sizes)

    read = await _service().dresses(TENANT_ID)

    assert read.sizes_by_dress_id == {sized.id: ["38", "40"]}
    assert [row.id for row in read.dresses] == [sized.id, unsized.id]
    assert read.truncated is False


async def test_a_full_dress_page_is_reported_as_truncated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ The flag is `len(rows) == LIMIT`, and the bound the repository was ASKED
    for is the one it is compared against. A hidden gown with no notice is the
    one failure a picker may not have — the UI renders a line pointing at
    «שמלות» instead."""
    rows = [_dress(f"שמלה {index}") for index in range(DRESS_PICKER_LIMIT)]

    async def _list_for_picker(_s: Any, _sess: Any, _t: Any, *, limit: int) -> list[Dress]:
        assert limit == DRESS_PICKER_LIMIT
        return rows

    async def _sizes(_s: Any, _sess: Any, _t: Any, ids: Any) -> dict[uuid.UUID, list[str]]:
        return {}

    monkeypatch.setattr(DressesRepository, "list_for_picker", _list_for_picker)
    monkeypatch.setattr(DressVariantsRepository, "size_labels_by_dress", _sizes)

    assert (await _service().dresses(TENANT_ID)).truncated is True


async def test_the_client_picker_asks_for_todays_jerusalem_day_and_names_the_arrivals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ The WINDOW is the assertion, not the rows. `NOW` is 11:20 UTC on
    2026-08-02, which is 14:20 in Jerusalem (IDT, UTC+3) — so today's calendar
    day there begins at 21:00 UTC on the 1st and ends at 21:00 UTC on the 2nd. A
    UTC-day window would drop or keep an arrival for three hours either side of
    midnight in Israel, every day.

    It is the SAME window the claim's check-in predicate uses, out of one helper:
    a booking this picker offers and the claim then refuses would be a control
    that does nothing.
    """
    booking = _booking(checked_in_at=NOW)
    asked: dict[str, Any] = {}

    async def _checked_in(
        _s: Any,
        _sess: Any,
        _t: Any,
        *,
        from_instant: datetime.datetime,
        until_instant: datetime.datetime,
        limit: int,
    ) -> list[Booking]:
        asked.update({"from_instant": from_instant, "until_instant": until_instant, "limit": limit})
        return [booking]

    async def _by_ids(_s: Any, _sess: Any, _t: Any, ids: Any) -> list[Customer]:
        assert list(ids) == [booking.customer_id]
        row = Customer(tenant_id=TENANT_ID, phone="+972501234567", name="מיכל")
        row.id = booking.customer_id
        return [row]

    monkeypatch.setattr(BookingsRepository, "list_checked_in_between", _checked_in)
    monkeypatch.setattr(CustomersRepository, "by_ids", _by_ids)

    read = await _service().clients(TENANT_ID)

    assert asked["from_instant"] == datetime.datetime(2026, 8, 1, 21, 0, tzinfo=datetime.UTC)
    assert asked["until_instant"] == datetime.datetime(2026, 8, 2, 21, 0, tzinfo=datetime.UTC)
    assert asked["limit"] == CLIENT_PICKER_LIMIT
    assert read.names_by_customer_id == {booking.customer_id: "מיכל"}
    assert read.truncated is False


async def test_the_client_picker_window_is_the_one_the_claim_admits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both sides of one helper, asserted against each other rather than against
    two transcriptions of the same arithmetic. A booking at either edge of the
    window the picker asks for must be claimable, and one outside it must not."""
    asked: dict[str, Any] = {}

    async def _checked_in(
        _s: Any,
        _sess: Any,
        _t: Any,
        *,
        from_instant: datetime.datetime,
        until_instant: datetime.datetime,
        limit: int,
    ) -> list[Booking]:
        asked.update({"from_instant": from_instant, "until_instant": until_instant})
        return []

    async def _by_ids(_s: Any, _sess: Any, _t: Any, ids: Any) -> list[Customer]:
        return []

    monkeypatch.setattr(BookingsRepository, "list_checked_in_between", _checked_in)
    monkeypatch.setattr(CustomersRepository, "by_ids", _by_ids)
    service = _service()
    await service.clients(TENANT_ID)

    first = asked["from_instant"]
    last = asked["until_instant"] - datetime.timedelta(microseconds=1)
    assert service._is_claimable(_booking(starts_at=first, checked_in_at=NOW)) is True
    assert service._is_claimable(_booking(starts_at=last, checked_in_at=NOW)) is True
    assert (
        service._is_claimable(_booking(starts_at=asked["until_instant"], checked_in_at=NOW))
        is False
    )


# =============================================================================
# F58 — TAKE-NEXT. The branches; the mechanisms are test_queue_dispatch_db.py's.
#
# ⚠ WHAT THIS MODULE CAN AND CANNOT SEE — mutations RUN, not reasoned about,
# and the plan's predictions corrected where they were wrong.
#
#   * `_authorize` moved below the room read → RED here (3 cases). `_Rig.order`
#     records the SEQUENCE rather than the outcome, which is the only way to
#     state that the 403 precedes the read.
#   * the unrecognised-constraint re-raise dropped → RED here (2 cases).
#   * step 2b deleted → **RED here (1 case)**, and the plan predicted GREEN. It
#     was wrong: `_Rig.occupant` stages a committed occupant, so the fast suite
#     does see the branch. What it CANNOT see is the branch's whole point — a
#     real customer's ticket claimed and thrown away, and a third take-next
#     SKIP-LOCKing past her. That needs a real server.
#   * F36's idempotence RETURN added around the INSERT → **RED here (1 case)**,
#     and the plan predicted GREEN across every fast test. Also wrong, and for a
#     reason worth keeping: the assertion is STRUCTURAL — `active_for` is never
#     called on any take-next path — rather than behavioural. What it cannot see
#     is the DEFECT: the commit that strands a woman `in_service` with no room.
#     `test_queue_dispatch_db.py` owns that one and it is the feature's headline.
#   * reusing the aborted session in `_occupied_error` instead of opening a
#     second one stays GREEN here — the fake session never aborts, so there is
#     no `PendingRollbackError` to raise. Pinned in the db module.
# =============================================================================

TICKET_ID = uuid.uuid4()


@dataclasses.dataclass(frozen=True)
class _Ticket:
    """`claim_next`'s four RETURNING columns. A projection, never the entity —
    `phone` and `marketing_opt_in_at` do not enter the process on this path."""

    id: uuid.UUID = TICKET_ID
    name: str = "נועה בר"
    visit_type: str = "bride"
    called_at: datetime.datetime | None = None


@dataclasses.dataclass(frozen=True)
class _Called:
    """`call`'s two RETURNING columns."""

    id: uuid.UUID = TICKET_ID
    called_at: datetime.datetime = NOW


@dataclasses.dataclass(frozen=True)
class _Skipped:
    """`skip`'s three. `status` is the CASE's answer, so the fake can stage both
    the requeue and the removal."""

    id: uuid.UUID = TICKET_ID
    skip_count: int = 1
    status: str = QueueTicketStatus.WAITING.value


@dataclasses.dataclass(frozen=True)
class _Waiting:
    """One row of `waiting_for_panel`'s seven-column projection. `phone` is on it
    because D9's grouping needs one, and the assertion that matters most in this
    module is that it never comes out the other side."""

    id: uuid.UUID = TICKET_ID
    name: str = "נועה בר"
    visit_type: str = "bride"
    created_at: datetime.datetime = CLAIMED_AT
    called_at: datetime.datetime | None = None
    skip_count: int = 0
    phone: str = "+972501234567"


def _install_tickets(monkeypatch: pytest.MonkeyPatch, rig: _Rig) -> _Rig:
    async def _claim_next(_s: Any, _sess: Any, _t: Any, *, day: Any) -> Any:
        rig.order.append("claim_next")
        rig.calls.append({"call": "claim_next", "day": day})
        return rig.next_ticket

    async def _claim_by_id(_s: Any, _sess: Any, _t: Any, ticket_id: uuid.UUID) -> Any:
        rig.order.append("claim_by_id")
        rig.calls.append({"call": "claim_by_id", "ticket_id": ticket_id})
        return rig.named_ticket

    async def _call(_s: Any, _sess: Any, _t: Any, ticket_id: uuid.UUID, *, now: Any) -> Any:
        rig.order.append("call")
        rig.calls.append({"call": "call", "ticket_id": ticket_id, "now": now})
        return rig.call_result

    async def _skip(
        _s: Any,
        _sess: Any,
        _t: Any,
        ticket_id: uuid.UUID,
        *,
        now: Any,
        seen_skip_count: int,
    ) -> Any:
        rig.order.append("skip")
        rig.calls.append(
            {
                "call": "skip",
                "ticket_id": ticket_id,
                "now": now,
                "seen_skip_count": seen_skip_count,
            }
        )
        return rig.skip_result

    async def _remove(_s: Any, _sess: Any, _t: Any, ticket_id: uuid.UUID) -> bool:
        rig.order.append("remove")
        rig.calls.append({"call": "remove", "ticket_id": ticket_id})
        return rig.removed

    async def _close(_s: Any, _sess: Any, _t: Any, ticket_id: uuid.UUID) -> bool:
        rig.order.append("close")
        rig.calls.append({"call": "close", "ticket_id": ticket_id})
        return rig.closed

    async def _status_of(_s: Any, _sess: Any, _t: Any, _ticket_id: uuid.UUID) -> Any:
        rig.order.append("status_of")
        return rig.ticket_status

    monkeypatch.setattr(QueueTicketsRepository, "claim_next", _claim_next)
    monkeypatch.setattr(QueueTicketsRepository, "claim_by_id", _claim_by_id)
    monkeypatch.setattr(QueueTicketsRepository, "call", _call)
    monkeypatch.setattr(QueueTicketsRepository, "skip", _skip)
    monkeypatch.setattr(QueueTicketsRepository, "remove", _remove)
    monkeypatch.setattr(QueueTicketsRepository, "close", _close)
    monkeypatch.setattr(QueueTicketsRepository, "status_of", _status_of)
    return _install_rooms(monkeypatch, rig)


# --- take-next's authorization matrix (D3 step 1) -----------------------------


@pytest.mark.parametrize("role", ELEVATED)
async def test_an_elevated_role_may_take_next_for_anybody(
    monkeypatch: pytest.MonkeyPatch, role: StaffRole
) -> None:
    rig = _install_tickets(monkeypatch, _Rig())
    target = uuid.uuid4()

    read = await _service().take_next(TENANT_ID, ROOM_ID, staff_user_id=target, actor=_actor(role))

    assert read.room.row.room_id == ROOM_ID
    assert rig.calls[-1] == {
        "call": "claim",
        "room_id": ROOM_ID,
        "staff_id": target,
        "booking_id": None,
        "queue_ticket_id": TICKET_ID,
    }


@pytest.mark.parametrize("role", FLOOR)
async def test_a_floor_role_may_take_next_for_herself(
    monkeypatch: pytest.MonkeyPatch, role: StaffRole
) -> None:
    rig = _install_tickets(monkeypatch, _Rig())
    actor = _actor(role)

    await _service().take_next(TENANT_ID, ROOM_ID, staff_user_id=None, actor=actor)

    assert rig.calls[-1]["staff_id"] == actor.id


@pytest.mark.parametrize("role", FLOOR)
async def test_a_floor_role_taking_next_for_a_colleague_is_refused_without_reading_anything(
    monkeypatch: pytest.MonkeyPatch, role: StaffRole
) -> None:
    """The empty `order` is the assertion, not the exception: a 403 raised after
    a read is an existence oracle for room ids, and `_authorize` is take-next's
    first statement for exactly that reason (`service.py:19-24`).

    ⚠ MUTATION PERFORMED: move `self._authorize(...)` below the room read →
    `rig.order` is `["room_for_update"]` and this reds. It is the only one of
    take-next's five mechanisms this module can see.
    """
    rig = _install_tickets(monkeypatch, _Rig())

    with pytest.raises(NotAuthorizedError):
        await _service().take_next(
            TENANT_ID, ROOM_ID, staff_user_id=uuid.uuid4(), actor=_actor(role)
        )

    assert rig.order == []
    assert rig.audit == []


# --- take-next's reads, in order ----------------------------------------------


@pytest.mark.parametrize("room", [None, _room(is_active=False)])
async def test_take_next_on_a_missing_or_INACTIVE_room_is_one_indistinguishable_404(
    monkeypatch: pytest.MonkeyPatch, room: FittingRoom | None
) -> None:
    """The room lock comes first, so the common refusal — a room that vanished
    or was deactivated — costs no ticket write at all."""
    rig = _Rig()
    rig.room = room
    _install_tickets(monkeypatch, rig)

    with pytest.raises(DomainNotFoundError):
        await _service().take_next(
            TENANT_ID, ROOM_ID, staff_user_id=None, actor=_actor(StaffRole.OWNER)
        )

    assert "claim_next" not in rig.order
    assert rig.audit == []


async def test_take_next_into_an_occupied_room_refuses_before_touching_the_queue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ STEP 2b, and what it buys is a CUSTOMER rather than a round-trip.

    Two managers tapping «קחי את הבאה» on the same free tile inside one 5s tick
    is the most likely collision in the feature. Without this read the loser
    claims a real customer's ticket and then throws it away on the INSERT — and
    for the window in which she held it, a third take-next SKIP-LOCKs past her
    and serves the woman behind her. With it, the serialised same-room case
    touches no ticket at all.

    ⚠ MUTATION PERFORMED: delete step 2b → this test RED and nothing else, so it
    is the only fast witness. The plan predicted GREEN here; it was wrong,
    because `_Rig.occupant` stages the committed occupant a fake normally would
    not. What stays invisible here is the CONSEQUENCE — the ticket claimed and
    discarded — which `test_queue_dispatch_db.py` pins.
    """
    rig = _Rig()
    rig.occupant = _assignment(uuid.uuid4())
    rig.occupant_staff = _staff_user(display_name="דנה")
    _install_tickets(monkeypatch, rig)

    with pytest.raises(RoomOccupiedError) as refused:
        await _service().take_next(
            TENANT_ID, ROOM_ID, staff_user_id=None, actor=_actor(StaffRole.OWNER)
        )

    assert refused.value.details == {"staff_display_name": "דנה"}
    assert "claim_next" not in rig.order
    assert "claim" not in rig.order
    assert rig.audit == []


async def test_an_empty_queue_is_a_409_that_claims_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Its own code rather than a 404 or an unchanged 200: a 404 would mean the
    ROOM is missing, which the panel renders as «החדר כבר לא זמין» about a room
    that is fine, and a 200 leaves the manager wondering whether the tap
    registered. The queue emptying between the render and the tap is an ordinary
    five-second race, so it is not an outage register either."""
    rig = _Rig()
    rig.next_ticket = None
    _install_tickets(monkeypatch, rig)

    with pytest.raises(QueueEmptyError):
        await _service().take_next(
            TENANT_ID, ROOM_ID, staff_user_id=None, actor=_actor(StaffRole.OWNER)
        )

    assert "claim" not in rig.order
    assert rig.audit == []


async def test_take_next_claims_the_queue_for_TODAY(monkeypatch: pytest.MonkeyPatch) -> None:
    """`_today()` is `today_jerusalem(self._clock)` and is the SAME derivation
    `_today_window()` uses, so the waitlist day, the take-next day and the client
    picker's window cannot drift apart. NOW is 11:20 UTC on 2026-08-02, i.e.
    14:20 in Jerusalem — the same calendar day, which is what makes this
    assertion about the timezone rather than about UTC."""
    rig = _install_tickets(monkeypatch, _Rig())

    await _service().take_next(
        TENANT_ID, ROOM_ID, staff_user_id=None, actor=_actor(StaffRole.OWNER)
    )

    assert rig.calls[1] == {"call": "claim_next", "day": datetime.date(2026, 8, 2)}


async def test_take_next_records_one_dispatch_row_naming_no_person(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ONE value for both dispatch verbs with the mode in `details`, and NO
    second FITTING_ROOM_CLAIMED — the claim row's whole content is a subset of
    this one's. No name and no phone in `details`: audit_log has no retention
    policy and platform operators read across tenants."""
    rig = _install_tickets(monkeypatch, _Rig())
    actor = _actor(StaffRole.SHIFT_MANAGER)

    await _service().take_next(TENANT_ID, ROOM_ID, staff_user_id=None, actor=actor)

    assert rig.audit == [
        {
            "action": AuditAction.QUEUE_TICKET_DISPATCHED.value,
            "actor_id": actor.id,
            "entity": str(TICKET_ID),
            "details": {
                "ticket": str(TICKET_ID),
                "room": str(ROOM_ID),
                "assignment": str(ASSIGNMENT_ID),
                "staff": str(actor.id),
                "mode": "take_next",
            },
        }
    ]
    assert "נועה בר" not in str(rig.audit)


# --- _occupied_error: every branch, and the two it must NOT have --------------


async def test_a_take_next_room_conflict_names_the_occupant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ THE ROOM IS RESOLVED FIRST AND WITHOUT THE CONSTRAINT NAME, which is
    F36's rule applied to a case its own branch order cannot cover: a claim
    violating BOTH indexes reports whichever has the lower OID — migration
    creation order, which flips after any REINDEX CONCURRENTLY or pg_repack.
    Both parametrisations answer the same thing."""
    for reported in (ROOM_ACTIVE_INDEX, STAFF_ACTIVE_INDEX):
        rig = _Rig()
        rig.claim_error = _integrity_error(reported)
        rig.occupant = _assignment(uuid.uuid4())
        rig.occupant_staff = _staff_user(display_name="דנה")
        _install_tickets(monkeypatch, rig)

        with pytest.raises(RoomOccupiedError) as refused:
            await _service().take_next(
                TENANT_ID, ROOM_ID, staff_user_id=None, actor=_actor(StaffRole.OWNER)
            )

        assert refused.value.details == {"staff_display_name": "דנה"}
        assert rig.audit == []


async def test_a_take_next_staff_conflict_names_the_room_she_is_already_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rig = _Rig()
    rig.claim_error = _integrity_error(STAFF_ACTIVE_INDEX)
    rig.staff_room = _assignment(uuid.uuid4())
    rig.occupied_room = _room(label="חדר 2")
    _install_tickets(monkeypatch, rig)

    with pytest.raises(StaffOccupiedError) as refused:
        await _service().take_next(
            TENANT_ID, ROOM_ID, staff_user_id=None, actor=_actor(StaffRole.OWNER)
        )

    assert refused.value.details == {"room_label": "חדר 2"}
    assert rig.audit == []


async def test_a_take_next_whose_winner_released_in_the_gap_does_not_name_nobody(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nobody to name and a recognised constraint: «החדר נתפס זה עתה. נסי שוב.»
    A 409 that admits it does not know beats one interpolating an empty name."""
    rig = _Rig()
    rig.claim_error = _integrity_error(ROOM_ACTIVE_INDEX)
    _install_tickets(monkeypatch, rig)

    with pytest.raises(RoomOccupiedError) as refused:
        await _service().take_next(
            TENANT_ID, ROOM_ID, staff_user_id=None, actor=_actor(StaffRole.OWNER)
        )

    assert refused.value.details is None


@pytest.mark.parametrize("reported", [None, "idx_something_nobody_predicted"])
async def test_an_unrecognised_violation_on_take_next_is_re_raised(
    monkeypatch: pytest.MonkeyPatch, reported: str | None
) -> None:
    """A8c. Unchanged from F36: a 500 on a violation nobody predicted is correct,
    and silently mapping it to ROOM_OCCUPIED would tell a staffer a lie about
    furniture. This is why `_occupied_error` RETURNS an exception rather than
    raising one — `return error` is how this branch is expressible at all.

    ⚠ MUTATION PERFORMED: `return RoomOccupiedError(None)` unconditionally at the
    end of the helper → both parametrisations red.
    """
    rig = _Rig()
    rig.claim_error = _integrity_error(reported)
    _install_tickets(monkeypatch, rig)

    with pytest.raises(IntegrityError):
        await _service().take_next(
            TENANT_ID, ROOM_ID, staff_user_id=None, actor=_actor(StaffRole.OWNER)
        )

    assert rig.audit == []


async def test_take_next_never_consults_the_idempotence_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ A8b's FAST HALF, and it is STRUCTURAL: `active_for` is never called on
    any take-next path.

    F36's `_resolve_claim_conflict` resolves idempotence with
    `active_for` → `return await self._room_read(...)`, which is correct there
    and catastrophic here. `db/tenant.py:25` is
    `async with session_factory() as session, session.begin():`, so a RETURN from
    inside that block COMMITS — a transaction in which the ticket has already
    gone to `in_service` and no assignment was created. The woman is then
    `in_service` with no room: gone from the waitlist, gone from the public
    board, on no tile, her own phone reading «התור שלך התחיל» for the rest of the
    day, recoverable only with psql.

    Asserting the absence STRUCTURALLY is what stops it being added back here,
    since the DEFECT it causes — the commit — needs a real Postgres to observe
    (`test_queue_dispatch_db.py`).

    ⚠ MUTATION PERFORMED: wrap the INSERT in `except IntegrityError:` →
    `active_for` → `return await self._room_read(...)` inside the `async with`
    → this test RED. The plan predicted GREEN across every fast test and was
    wrong; the structural assertion is what makes the difference.
    """
    expected: list[tuple[str | None, type[Exception]]] = [
        (ROOM_ACTIVE_INDEX, RoomOccupiedError),
        (STAFF_ACTIVE_INDEX, RoomOccupiedError),
        (None, IntegrityError),
    ]
    for reported, error in expected:
        rig = _Rig()
        rig.claim_error = _integrity_error(reported)
        # The idempotence read is armed with a HIT, so a branch that consulted it
        # would take it. It is never consulted.
        rig.idempotent = _assignment(uuid.uuid4())
        _install_tickets(monkeypatch, rig)

        with pytest.raises(error):
            await _service().take_next(
                TENANT_ID, ROOM_ID, staff_user_id=None, actor=_actor(StaffRole.OWNER)
            )

        assert "active_for" not in rig.order


# --- F58: the waitlist read and D9's duplicate flag ---------------------------


async def test_the_waitlist_asks_for_todays_jerusalem_day_and_renders_the_rows_in_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The day is `_today()` — the SAME derivation take-next and the client
    picker use, so a walk-in dispatched from the panel cannot be one the panel
    could not see. NOW is 11:20 UTC on 2026-08-02, i.e. 14:20 in Jerusalem."""
    rig = _Rig()
    rig.waiting = [_Waiting(name="נועה בר"), _Waiting(id=uuid.uuid4(), name="מיכל")]
    _install_tickets(monkeypatch, rig)

    async def _list_live(_s: Any, _sess: Any, _t: Any) -> list[StaffUser]:
        return []

    async def _list_with_occupancy(_s: Any, _sess: Any, _t: Any) -> list[RoomRow]:
        return []

    monkeypatch.setattr(StaffUsersRepository, "list_live", _list_live)
    monkeypatch.setattr(FittingRoomsRepository, "list_with_occupancy", _list_with_occupancy)
    _install_no_roster(monkeypatch)

    read = await _service().floor(TENANT_ID)

    assert rig.waitlist_days == [datetime.date(2026, 8, 2)]
    assert [entry.name for entry in read.waitlist.entries] == ["נועה בר", "מיכל"]
    assert read.waitlist.truncated is False


async def test_the_duplicate_flag_is_keyed_on_the_phone_and_sees_an_in_service_twin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D9's rule, and the SECOND statement is what makes it worth having.

    Three rows: two waiting with one phone between them, one waiting whose twin
    is already IN a room, and one alone. `name` collides legitimately in a bridal
    boutique — two women called נועה is an ordinary Tuesday — so the grouping is
    the normalised phone and nothing else.

    ⚠ MUTATION PERFORMED: drop `or row.phone in in_service` → the third row
    renders un-flagged, which is the case D9 calls the most valuable thing on
    this panel to remove. MUTATION PERFORMED: group on `name` → rows 1 and 4
    (both «נועה בר», different numbers) flag each other and row 2 stops flagging.
    """
    shared, served, lonely = "+972500000001", "+972500000002", "+972500000003"
    rig = _Rig()
    rig.waiting = [
        _Waiting(id=uuid.uuid4(), name="נועה בר", phone=shared),
        _Waiting(id=uuid.uuid4(), name="מיכל", phone=shared),
        _Waiting(id=uuid.uuid4(), name="דנה", phone=served),
        _Waiting(id=uuid.uuid4(), name="נועה בר", phone=lonely),
    ]
    rig.in_service_phones = {served}
    _install_tickets(monkeypatch, rig)

    entries = (await _service()._waitlist(cast(AsyncSession, _FakeSession()), TENANT_ID)).entries

    assert [entry.duplicate for entry in entries] == [True, True, True, False]
    # The number is the KEY and never the payload: `WaitlistEntryRead` has no
    # field to carry one, so the grouping cannot leak by accident downstream.
    assert not any(hasattr(entry, "phone") for entry in entries)


async def test_a_full_waitlist_page_is_reported_as_truncated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`len(rows) == WAITLIST_LIMIT` — F36's `DressPickerRead` derivation
    verbatim, and the bound the repository was ASKED for is the one it is
    compared against."""
    rig = _Rig()
    rig.waiting = [
        _Waiting(id=uuid.uuid4(), phone=f"+97250{index:07d}") for index in range(WAITLIST_LIMIT)
    ]
    _install_tickets(monkeypatch, rig)

    assert (
        await _service()._waitlist(cast(AsyncSession, _FakeSession()), TENANT_ID)
    ).truncated is True


# =============================================================================
# F58 — PUSH-ASSIGN, CALL, SKIP and REMOVE (D4, D6, D7, D8).
#
# ⚠ WHAT THIS MODULE CAN AND CANNOT SEE, mutations RUN:
#
#   * `call`'s THIRD branch removed (D4's two-answer table implemented
#     literally) → RED here, by name. It is a pure branch and needs no server.
#   * `skip`'s QUEUE_TICKET_CHANGED branch folded into QUEUE_TICKET_NOT_WAITING
#     → RED here. What stays invisible is the DAMAGE the conjunct prevents — a
#     woman removed by two ordinary single taps — which needs two transactions.
#   * the no-audit-on-a-no-op rule → RED here, on the call path.
#   * `assign` copying `claim`'s savepoint → GREEN here, exactly as it is for
#     take-next: a monkeypatched repository raises with no real flush to abort.
#     Pinned in test_queue_dispatch_db.py.
# =============================================================================

SECOND_TICKET_ID = uuid.uuid4()


# --- push-assign (D4) ---------------------------------------------------------


@pytest.mark.parametrize("role", ELEVATED)
async def test_an_elevated_role_may_push_assign_for_anybody(
    monkeypatch: pytest.MonkeyPatch, role: StaffRole
) -> None:
    rig = _install_tickets(monkeypatch, _Rig())
    target = uuid.uuid4()

    read = await _service().assign(
        TENANT_ID,
        ROOM_ID,
        queue_ticket_id=TICKET_ID,
        staff_user_id=target,
        actor=_actor(role),
    )

    assert read.room.row.room_id == ROOM_ID
    assert rig.calls[-1] == {
        "call": "claim",
        "room_id": ROOM_ID,
        "staff_id": target,
        "booking_id": None,
        "queue_ticket_id": TICKET_ID,
    }


@pytest.mark.parametrize("role", FLOOR)
async def test_a_floor_role_push_assigning_for_a_colleague_is_refused_without_reading_anything(
    monkeypatch: pytest.MonkeyPatch, role: StaffRole
) -> None:
    """The empty `order` is the assertion. `_authorize` now has FIVE call sites
    and every one of them is its method's first statement — a 403 raised after a
    read is an existence oracle for room ids AND, on this verb, for ticket ids.

    ⚠ MUTATION PERFORMED: move `self._authorize(...)` below the room read → this
    reds on `rig.order == ["room_for_update"]`.
    """
    rig = _install_tickets(monkeypatch, _Rig())

    with pytest.raises(NotAuthorizedError):
        await _service().assign(
            TENANT_ID,
            ROOM_ID,
            queue_ticket_id=TICKET_ID,
            staff_user_id=uuid.uuid4(),
            actor=_actor(role),
        )

    assert rig.order == []
    assert rig.audit == []


async def test_push_assign_into_an_occupied_room_refuses_before_touching_the_ticket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Step 2b, on the second verb that has it. Without it the loser of the most
    likely collision — two managers on one free tile inside one 5s tick — moves a
    NAMED customer to `in_service` and then throws the write away."""
    rig = _Rig()
    rig.occupant = _assignment(uuid.uuid4())
    rig.occupant_staff = _staff_user(display_name="דנה")
    _install_tickets(monkeypatch, rig)

    with pytest.raises(RoomOccupiedError) as refused:
        await _service().assign(
            TENANT_ID,
            ROOM_ID,
            queue_ticket_id=TICKET_ID,
            staff_user_id=None,
            actor=_actor(StaffRole.OWNER),
        )

    assert refused.value.details == {"staff_display_name": "דנה"}
    assert "claim_by_id" not in rig.order
    assert rig.audit == []


async def test_push_assign_names_the_ticket_and_never_drains_the_queue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ONE difference from take-next: step 3 names a ticket instead of taking
    the head. `claim_next` must not be reachable from this verb at all — a
    push-assign that quietly served the head would put the wrong woman in the
    room the manager was looking at."""
    rig = _Rig()
    rig.named_ticket = _Ticket(id=SECOND_TICKET_ID, name="מיכל")
    _install_tickets(monkeypatch, rig)

    await _service().assign(
        TENANT_ID,
        ROOM_ID,
        queue_ticket_id=SECOND_TICKET_ID,
        staff_user_id=None,
        actor=_actor(StaffRole.OWNER),
    )

    assert "claim_next" not in rig.order
    assert {"call": "claim_by_id", "ticket_id": SECOND_TICKET_ID} in rig.calls
    assert rig.calls[-1]["queue_ticket_id"] == SECOND_TICKET_ID


async def test_push_assign_records_one_dispatch_row_carrying_the_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ONE action value for both dispatch verbs, with the mode in `details` — the
    question this table gets asked is "who put whom in which room", and nobody
    will ever ask it "who used the take-next button but not the assign one". And
    NO second FITTING_ROOM_CLAIMED: the claim row's whole content is a subset of
    this one's."""
    rig = _install_tickets(monkeypatch, _Rig())
    actor = _actor(StaffRole.SHIFT_MANAGER)

    await _service().assign(
        TENANT_ID, ROOM_ID, queue_ticket_id=TICKET_ID, staff_user_id=None, actor=actor
    )

    assert rig.audit == [
        {
            "action": AuditAction.QUEUE_TICKET_DISPATCHED.value,
            "actor_id": actor.id,
            "entity": str(TICKET_ID),
            "details": {
                "ticket": str(TICKET_ID),
                "room": str(ROOM_ID),
                "assignment": str(ASSIGNMENT_ID),
                "staff": str(actor.id),
                "mode": "assign",
            },
        }
    ]
    assert "נועה בר" not in str(rig.audit)


async def test_push_assigning_a_ticket_that_is_gone_is_a_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`QueueTicketNotFoundError`, F33's shipped subclass, so the platform's own
    404 handler answers it and no new code or error code exists for this. A
    foreign-tenant id is deliberately the SAME answer as an absent one."""
    rig = _Rig()
    rig.named_ticket = None
    rig.ticket_status = None
    _install_tickets(monkeypatch, rig)

    with pytest.raises(QueueTicketNotFoundError):
        await _service().assign(
            TENANT_ID,
            ROOM_ID,
            queue_ticket_id=TICKET_ID,
            staff_user_id=None,
            actor=_actor(StaffRole.OWNER),
        )

    assert "claim" not in rig.order
    assert rig.audit == []


@pytest.mark.parametrize(
    "status",
    [
        QueueTicketStatus.IN_SERVICE.value,
        QueueTicketStatus.DONE.value,
        QueueTicketStatus.REMOVED.value,
    ],
)
async def test_push_assigning_a_ticket_that_is_no_longer_waiting_is_a_409_naming_the_state(
    monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    """The two-answer table's second row. `details` carries the state because
    that is what lets the console choose between «היא כבר בטיפול.» and «הכניסה
    הזו נסגרה.» — one code, two sentences, and the branch lives in the copy deck
    rather than in a second error code."""
    rig = _Rig()
    rig.named_ticket = None
    rig.ticket_status = (status, 0)
    _install_tickets(monkeypatch, rig)

    with pytest.raises(QueueTicketNotWaitingError) as refused:
        await _service().assign(
            TENANT_ID,
            ROOM_ID,
            queue_ticket_id=TICKET_ID,
            staff_user_id=None,
            actor=_actor(StaffRole.OWNER),
        )

    assert refused.value.details == {"status": status}
    assert "claim" not in rig.order
    assert rig.audit == []


# --- call (D7) ----------------------------------------------------------------


async def test_a_call_stamps_the_service_clock_and_records_one_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rig = _install_tickets(monkeypatch, _Rig())
    actor = _actor(StaffRole.SEAMSTRESS)

    waitlist = await _service().call(TENANT_ID, TICKET_ID, actor=actor)

    assert waitlist.entries == []
    assert {"call": "call", "ticket_id": TICKET_ID, "now": NOW} in rig.calls
    assert rig.audit == [
        {
            "action": AuditAction.QUEUE_TICKET_CALLED.value,
            "actor_id": actor.id,
            "entity": str(TICKET_ID),
            "details": {"ticket": str(TICKET_ID), "called_at": NOW.isoformat()},
        }
    ]


async def test_a_second_call_on_a_still_waiting_ticket_is_a_200_that_records_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ A17, AND THE BRANCH A BUILDER IMPLEMENTING D4'S TABLE LITERALLY DOES NOT
    WRITE. `call`'s rowcount 0 has THREE causes, not two: the extra `called_at IS
    NULL` conjunct adds one, and on this verb it is the NORMAL, EXPECTED,
    NON-ERROR case. She wanted her called and she is called.

    A `{called → called}` row would be noise in a trail this area has four rows
    in, so the no-op writes nothing.

    ⚠ MUTATION PERFORMED: implement D4's two-answer table literally here — i.e.
    fall through with no branch for `status == 'waiting'` — and this test reds
    with a 409 the manager cannot act on, or a 500.
    """
    rig = _Rig()
    rig.call_result = None
    rig.ticket_status = (QueueTicketStatus.WAITING.value, 0)
    _install_tickets(monkeypatch, rig)

    waitlist = await _service().call(TENANT_ID, TICKET_ID, actor=_actor(StaffRole.RECEPTION))

    assert waitlist.entries == []
    assert rig.audit == []


async def test_calling_a_ticket_that_left_the_queue_is_a_409(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rig = _Rig()
    rig.call_result = None
    rig.ticket_status = (QueueTicketStatus.REMOVED.value, 0)
    _install_tickets(monkeypatch, rig)

    with pytest.raises(QueueTicketNotWaitingError) as refused:
        await _service().call(TENANT_ID, TICKET_ID, actor=_actor(StaffRole.RECEPTION))

    assert refused.value.details == {"status": QueueTicketStatus.REMOVED.value}
    assert rig.audit == []


async def test_calling_a_ticket_that_is_gone_is_a_404(monkeypatch: pytest.MonkeyPatch) -> None:
    rig = _Rig()
    rig.call_result = None
    rig.ticket_status = None
    _install_tickets(monkeypatch, rig)

    with pytest.raises(QueueTicketNotFoundError):
        await _service().call(TENANT_ID, TICKET_ID, actor=_actor(StaffRole.RECEPTION))

    assert rig.audit == []


async def test_the_call_verb_takes_no_target_staffer_and_therefore_no_authorize(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A summons is not destructive and has no target STAFFER, so there is
    nothing for a self-or-elevated rule to compare and the router's five-role
    gate is the whole check. Reception, a sales assistant and a seamstress all
    legitimately call the next woman forward."""
    for role in (*ELEVATED, *FLOOR):
        rig = _install_tickets(monkeypatch, _Rig())
        await _service().call(TENANT_ID, TICKET_ID, actor=_actor(role))
        assert len(rig.audit) == 1


# --- skip (D6) ----------------------------------------------------------------


async def test_a_first_skip_requeues_her_and_records_the_resulting_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`skip_count` and the RESULTING status ride in `details`, so a
    removal-by-second-skip is legible in the trail without a fifth action
    value."""
    rig = _install_tickets(monkeypatch, _Rig())
    actor = _actor(StaffRole.OWNER)

    await _service().skip(TENANT_ID, TICKET_ID, seen_skip_count=0, actor=actor)

    assert {
        "call": "skip",
        "ticket_id": TICKET_ID,
        "now": NOW,
        "seen_skip_count": 0,
    } in rig.calls
    assert rig.audit == [
        {
            "action": AuditAction.QUEUE_TICKET_SKIPPED.value,
            "actor_id": actor.id,
            "entity": str(TICKET_ID),
            "details": {
                "ticket": str(TICKET_ID),
                "skip_count": 1,
                "status": QueueTicketStatus.WAITING.value,
            },
        }
    ]


async def test_a_second_skip_records_the_removal_it_actually_performed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The status in `details` is the one the SERVER wrote, read off the
    statement's own RETURNING rather than re-derived in Python — the `CASE` is
    the authority on whether that press removed her."""
    rig = _Rig()
    rig.skip_result = _Skipped(skip_count=2, status=QueueTicketStatus.REMOVED.value)
    _install_tickets(monkeypatch, rig)

    await _service().skip(TENANT_ID, TICKET_ID, seen_skip_count=1, actor=_actor(StaffRole.OWNER))

    assert rig.audit[0]["details"] == {
        "ticket": str(TICKET_ID),
        "skip_count": 2,
        "status": QueueTicketStatus.REMOVED.value,
    }


async def test_a_skip_whose_count_moved_under_the_caller_is_its_own_409(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ THE THIRD ANSWER, AND SHE IS NOT REMOVED.

    A colleague skipped her between this render and this tap. Folding this into
    `QUEUE_TICKET_NOT_WAITING` would tell the manager the entry is closed when it
    is live and still skippable, and the remedy is «רענני ונסי שוב» rather than
    «הכניסה הזו נסגרה». `details` carries the count the server actually holds, so
    the next tick raises her rendered count to 1 and the next press correctly
    opens the confirm instead of silently removing her.

    ⚠ MUTATION PERFORMED: fold the branch into `QueueTicketNotWaitingError` →
    this reds on the class.
    """
    rig = _Rig()
    rig.skip_result = None
    rig.ticket_status = (QueueTicketStatus.WAITING.value, 1)
    _install_tickets(monkeypatch, rig)

    with pytest.raises(QueueTicketChangedError) as refused:
        await _service().skip(
            TENANT_ID, TICKET_ID, seen_skip_count=0, actor=_actor(StaffRole.OWNER)
        )

    assert refused.value.details == {"skip_count": "1"}
    assert rig.audit == []


async def test_skipping_a_ticket_that_left_the_queue_is_a_409_and_a_missing_one_is_a_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for status, error in (
        (QueueTicketStatus.IN_SERVICE.value, QueueTicketNotWaitingError),
        (None, QueueTicketNotFoundError),
    ):
        rig = _Rig()
        rig.skip_result = None
        rig.ticket_status = (status, 0) if status is not None else None
        _install_tickets(monkeypatch, rig)

        with pytest.raises(error):
            await _service().skip(
                TENANT_ID, TICKET_ID, seen_skip_count=0, actor=_actor(StaffRole.OWNER)
            )

        assert rig.audit == []


# --- remove (D8) --------------------------------------------------------------


async def test_a_removal_records_one_row_naming_only_the_ticket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`details = {"ticket"}` and nothing else. audit_log has no retention policy
    and platform operators read across tenants, so a queue ticket's name is a
    third party's exactly as customer notes are — ids only."""
    rig = _install_tickets(monkeypatch, _Rig())
    actor = _actor(StaffRole.SHIFT_MANAGER)

    await _service().remove(TENANT_ID, TICKET_ID, actor=actor)

    assert rig.audit == [
        {
            "action": AuditAction.QUEUE_TICKET_REMOVED.value,
            "actor_id": actor.id,
            "entity": str(TICKET_ID),
            "details": {"ticket": str(TICKET_ID)},
        }
    ]


async def test_removing_a_ticket_that_already_left_is_a_409_and_a_missing_one_is_a_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Remove's rowcount 0 really does have only D4's TWO causes — it carries no
    `skip_count` conjunct and no `called_at` one."""
    for status, error in (
        (QueueTicketStatus.REMOVED.value, QueueTicketNotWaitingError),
        (None, QueueTicketNotFoundError),
    ):
        rig = _Rig()
        rig.removed = False
        rig.ticket_status = (status, 0) if status is not None else None
        _install_tickets(monkeypatch, rig)

        with pytest.raises(error):
            await _service().remove(TENANT_ID, TICKET_ID, actor=_actor(StaffRole.OWNER))

        assert rig.audit == []


# --- what all four answer -----------------------------------------------------


async def test_every_queue_verb_answers_the_current_waitlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One round trip, not two. A client that acted and then waited up to five
    seconds for the row to leave the list would render the same woman as both
    served and waiting."""
    for act in (
        lambda service: service.call(TENANT_ID, TICKET_ID, actor=_actor(StaffRole.OWNER)),
        lambda service: service.skip(
            TENANT_ID, TICKET_ID, seen_skip_count=0, actor=_actor(StaffRole.OWNER)
        ),
        lambda service: service.remove(TENANT_ID, TICKET_ID, actor=_actor(StaffRole.OWNER)),
    ):
        rig = _Rig()
        rig.waiting = [_Waiting(name="מיכל")]
        _install_tickets(monkeypatch, rig)

        waitlist = await act(_service())

        assert [entry.name for entry in waitlist.entries] == ["מיכל"]
        assert rig.waitlist_days == [datetime.date(2026, 8, 2)]


async def test_both_dispatch_verbs_answer_the_tile_and_the_queue_together(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for act in (
        lambda service: service.take_next(
            TENANT_ID, ROOM_ID, staff_user_id=None, actor=_actor(StaffRole.OWNER)
        ),
        lambda service: service.assign(
            TENANT_ID,
            ROOM_ID,
            queue_ticket_id=TICKET_ID,
            staff_user_id=None,
            actor=_actor(StaffRole.OWNER),
        ),
    ):
        rig = _Rig()
        rig.waiting = [_Waiting(name="מיכל")]
        _install_tickets(monkeypatch, rig)

        read = await act(_service())

        assert read.room.row.room_id == ROOM_ID
        assert [entry.name for entry in read.waitlist.entries] == ["מיכל"]


# --- F58: FINISH is the shipped release, EXTENDED (D5) ------------------------
#
# ⚠ THE ACCEPTANCE GATE FOR THIS TASK IS THE FOUR TESTS ABOVE STAYING GREEN WITH
# NO EDIT. Every assignment F36 ever created carries `queue_ticket_id IS NULL`
# and must take the byte-identical shipped path — including its audit row, whose
# `details` the shipped test asserts as an EXACT dict.
#
# ⚠ AND THAT IS WHY THE NEW KEY IS OMITTED RATHER THAN NULL. D5 property 5 says
# the row gains `{"queue_ticket": str(id) | None}`, which would have added a
# `None` key to every release in the product and reddened
# `test_a_release_that_wrote_records_one_audit_row_and_stamps_the_service_clock`
# — contradicting D5 property 2, which calls those suites the acceptance gate.
# The key is therefore present exactly when there is a ticket to name, which is
# `_occupied_body`'s shipped rule for the same situation one layer up.


async def test_a_release_of_a_dispatched_walk_in_closes_her_ticket_in_the_same_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FINISH. There is no sixth route, and that is a SAFETY property rather than
    an economy: a separate finish verb would leave releasing from the room tile —
    the control that is already there, already tested — freeing the room and
    leaving the ticket `in_service` forever, which is precisely the defect this
    feature exists to eliminate.

    One transaction: the worker frees and the entry closes together, or neither
    does.
    """
    rig = _Rig()
    actor = _actor(StaffRole.SEAMSTRESS)
    rig.assignment = _assignment(actor.id)
    rig.release_result = (True, _assignment(actor.id, released_at=NOW, queue_ticket_id=TICKET_ID))
    _install_tickets(monkeypatch, rig)

    await _service().release(TENANT_ID, ASSIGNMENT_ID, actor=actor)

    assert {"call": "close", "ticket_id": TICKET_ID} in rig.calls
    assert rig.order.index("close") < rig.order.index("audit")
    assert rig.audit == [
        {
            "action": AuditAction.FITTING_ROOM_RELEASED.value,
            "actor_id": actor.id,
            "entity": str(ASSIGNMENT_ID),
            "details": {
                "room": str(ROOM_ID),
                "assignment": str(ASSIGNMENT_ID),
                "staff": str(actor.id),
                "queue_ticket": str(TICKET_ID),
            },
        }
    ]


async def test_a_release_of_an_ordinary_assignment_closes_nothing_and_names_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`queue_ticket_id IS NULL` is the DEFAULT, not an edge case: a staffer
    prepping a room, a booked bride, an anonymous visit. Every one of those takes
    the path F36 shipped, unchanged and unmentioned."""
    rig = _Rig()
    actor = _actor(StaffRole.SEAMSTRESS)
    rig.assignment = _assignment(actor.id)
    rig.release_result = (True, _assignment(actor.id, released_at=NOW))
    _install_tickets(monkeypatch, rig)

    await _service().release(TENANT_ID, ASSIGNMENT_ID, actor=actor)

    assert "close" not in rig.order
    assert "queue_ticket" not in rig.audit[0]["details"]


async def test_a_second_release_of_a_dispatched_walk_in_re_closes_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ `wrote is False` → NO CLOSE, and the two no-ops are ONE condition.

    Somebody already released it: she wanted the room free and the room is free,
    which is a 200 with no audit row. Closing the ticket anyway would be a write
    on a path whose whole point is that it writes nothing — and on a ticket a
    manager may have REMOVED mid-fitting, `close`'s own `status = 'in_service'`
    conjunct is the second guard behind this one.

    ⚠ MUTATION PERFORMED: close unconditionally (drop the `wrote` guard) → this
    test reds on `close` appearing in the order.
    """
    rig = _Rig()
    actor = _actor(StaffRole.SEAMSTRESS)
    rig.assignment = _assignment(actor.id)
    rig.release_result = (False, _assignment(actor.id, released_at=NOW, queue_ticket_id=TICKET_ID))
    _install_tickets(monkeypatch, rig)

    await _service().release(TENANT_ID, ASSIGNMENT_ID, actor=actor)

    assert "close" not in rig.order
    assert rig.audit == []


async def test_a_release_whose_ticket_a_manager_already_removed_still_frees_the_room(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`close` answering False raises NOTHING. The room is free, which is what
    she asked for; the ticket stays `removed` because a release must not
    resurrect a manager's removal as `done`."""
    rig = _Rig()
    actor = _actor(StaffRole.SEAMSTRESS)
    rig.assignment = _assignment(actor.id)
    rig.release_result = (True, _assignment(actor.id, released_at=NOW, queue_ticket_id=TICKET_ID))
    rig.closed = False
    _install_tickets(monkeypatch, rig)

    read = await _service().release(TENANT_ID, ASSIGNMENT_ID, actor=actor)

    assert read.row.room_id == ROOM_ID
    assert len(rig.audit) == 1


# --- F40 C1: the cutover, and the six things it must NOT change ---------------


def _install_roster(
    monkeypatch: pytest.MonkeyPatch,
    *,
    published: bool,
    rostered: set[uuid.UUID] | None = None,
) -> list[str]:
    """The two reads `_on_shift` makes, and a record of WHICH it made.

    The list is the assertion `test_the_resolver_reads_nothing_it_does_not_need`
    rests on: with no published roster the id set is never asked for at all.
    """
    reads: list[str] = []

    async def _by_week(
        _self: object, _session: object, _tenant_id: uuid.UUID, _week_start: datetime.date
    ) -> Any:
        reads.append("by_week")
        if not published:
            return None
        return SimpleNamespace(id=uuid.uuid4(), published_at=NOW, week_start=_week_start)

    async def _ids(
        _self: object, _session: object, _tenant_id: uuid.UUID, _at: datetime.datetime
    ) -> set[uuid.UUID]:
        reads.append("on_shift_staff_ids")
        return set() if rostered is None else rostered

    monkeypatch.setattr(RostersRepository, "by_week", _by_week)
    monkeypatch.setattr(RosterAssignmentsRepository, "on_shift_staff_ids", _ids)
    return reads


async def _board(
    monkeypatch: pytest.MonkeyPatch, staff: list[StaffUser], *, occupied: uuid.UUID | None = None
) -> FloorRead:
    rig = _Rig()
    _install_rooms(monkeypatch, rig)

    async def _list_live(_s: Any, _sess: Any, _t: Any) -> list[StaffUser]:
        return staff

    async def _list_with_occupancy(_s: Any, _sess: Any, _t: Any) -> list[RoomRow]:
        return [] if occupied is None else [_occupied_room_row(occupied)]

    monkeypatch.setattr(StaffUsersRepository, "list_live", _list_live)
    monkeypatch.setattr(FittingRoomsRepository, "list_with_occupancy", _list_with_occupancy)
    return await _service().floor(TENANT_ID)


async def test_the_board_never_drops_a_card_under_any_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ D1's REGRESSION GUARD, ASSERTED PER RULE RATHER THAN ONCE. The board
    LABELS and never filters: `GET /manage/floor` is what a seamstress opens to
    find out who else is in the building, and a colleague who walked in anyway —
    covering a sick call, collecting something, working a day nobody rostered —
    must not vanish from it. The failure would be silent and would look like an
    empty boutique.
    """
    on, off = _staff_user(), _staff_user()
    staff = [on, off]

    for published, rostered in ((False, None), (True, set()), (True, {on.id})):
        _install_roster(monkeypatch, published=published, rostered=rostered)
        read = await _board(monkeypatch, staff)
        assert [row.id for row in read.staff_rows] == [on.id, off.id], (published, rostered)
        assert set(read.on_shift_by_staff_id) == {on.id, off.id}, (published, rostered)


async def test_the_three_rules_reach_the_board_from_the_three_input_shapes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The four inputs are gathered from the ROW and the two reads and nothing
    else — the resolver itself is proved exhaustively in
    `test_shifts_resolver.py`, so what this asserts is the WIRING."""
    rostered = _staff_user()
    unrostered = _staff_user()
    marked = _staff_user()
    marked.on_shift_on = jerusalem_moment(NOW)[0]
    marked.on_shift_override = False

    _install_roster(monkeypatch, published=True, rostered={rostered.id, marked.id})
    read = await _board(monkeypatch, [rostered, unrostered, marked])

    assert read.on_shift_by_staff_id[rostered.id] == (True, OnShiftSource.ROSTER)
    assert read.on_shift_by_staff_id[unrostered.id] == (False, OnShiftSource.ROSTER)
    # ⚠ THE SICK CALL: she is on the published roster and she is not coming in.
    assert read.on_shift_by_staff_id[marked.id] == (False, OnShiftSource.MANUAL_TODAY)


async def test_a_boutique_with_no_published_roster_sees_the_board_it_saw_before(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ C1'S PROMISE, LITERALLY. Rule 3 resolves to today's exact behaviour —
    every live staffer counts as on shift — so a boutique that never publishes
    sees no change at all beyond two new keys."""
    staff = [_staff_user(), _staff_user()]
    reads = _install_roster(monkeypatch, published=False)
    read = await _board(monkeypatch, staff)

    assert all(read.on_shift_by_staff_id[row.id] == (True, OnShiftSource.FALLBACK) for row in staff)
    # ⚠ ONE statement, not two: the id set is never asked for when rule 2 cannot
    # fire, so an unpublishing boutique pays nothing for the cutover on a read
    # that runs every five seconds per device.
    assert reads == ["by_week"]


async def test_an_occupied_staffer_can_be_off_shift_and_the_card_says_both(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ D9's whole point. `status` answers WHAT SHE IS DOING RIGHT NOW and
    `on_shift` answers WHETHER SHE IS SUPPOSED TO BE HERE TODAY — both are true
    at once, and that tuple is the single most useful thing this feature puts on
    the board. A fourth `StaffCardStatus` would make it unrepresentable."""
    her = _staff_user()
    _install_roster(monkeypatch, published=True, rostered=set())
    read = await _board(monkeypatch, [her], occupied=her.id)

    occupancy = read.occupancy_by_staff_id[her.id]
    assert card_status(her, occupied=occupancy is not None) is StaffCardStatus.OCCUPIED
    assert read.on_shift_by_staff_id[her.id] == (False, OnShiftSource.ROSTER)


async def test_the_break_writers_answer_the_resolved_pair_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Design F-1: the client cannot compute `on_shift_source` — that is the whole
    of D8 — so a break route answering without it would force the panel to guess,
    and a guess prints the wrong Hebrew rule label on a live floor screen."""
    target = _staff_user(break_started_at=NOW)
    _install(monkeypatch, wrote=True, row=target, before=target)
    _install_roster(monkeypatch, published=True, rostered={target.id})

    started = await _service().start_break(TENANT_ID, target.id, actor=_actor(StaffRole.OWNER))
    assert (started.on_shift, started.on_shift_source) == (True, OnShiftSource.ROSTER)

    ended = await _service().end_break(TENANT_ID, target.id, actor=_actor(StaffRole.OWNER))
    assert (ended.on_shift, ended.on_shift_source) == (True, OnShiftSource.ROSTER)


def test_the_card_status_enum_is_still_exactly_three(monkeypatch: pytest.MonkeyPatch) -> None:
    """⚠ NOT FOUR (D9). `on_shift` is two new keys on the card and never a fourth
    status — folding it in would also break the console's deliberate no-fallback
    `STATUS_BADGE` Record."""
    assert {member.value for member in StaffCardStatus} == {"occupied", "break", "available"}


def test_the_on_shift_columns_stay_out_of_the_retention_scrub() -> None:
    """⚠ D16: the two new `staff_users` columns are a DATE and a BOOLEAN — no
    name, no phone, nothing a subject request could name — so they stay out of
    `_scrub_staff_users`' UPDATE. Asserted on the source, because the scrub is the
    one place where «add the new column» is the reflex and doing it would destroy
    an override for no privacy gain at all."""
    source = inspect.getsource(retention_module._scrub_staff_users)
    assert "on_shift_on" not in source
    assert "on_shift_override" not in source


def test_the_sos_audience_and_the_reachability_probe_are_not_rewired() -> None:
    """⚠ C2/D15: F37's SOS is NOT rewired, and this asserts it on the source
    rather than on behaviour, because the failure would be an ADDITION.

    `sos_alerts` has no role column: a page is at one named staffer or at NULL,
    and NULL means the two-member elevated audience computed at read time. The
    one reachability probe reads `sessions.has_live_session` — «is she signed in
    right now» — which is a strictly better proxy for «is she in the building»
    than a roster published a week ago. Wiring the roster in would page people who
    are rostered but logged out and un-page people who walked in and signed in,
    CREATING the epic's own stated risk rather than mitigating it.
    """
    source = inspect.getsource(app_service)
    for verb in ("raise_sos", "_for_me"):
        block = source.split(f"def {verb}", 1)[1].split("\n    async def ", 1)[0]
        assert "on_shift" not in block, verb
        assert "_roster_assignments" not in block, verb


def test_the_atelier_assignable_predicate_is_not_rewired() -> None:
    """⚠ C3/D15: F42 shipped with its F40 dependency explicitly dropped, and
    `assignable` stays `deleted_at IS NULL AND role == seamstress`. The
    published-roster projection is the recorded UPGRADE PATH and not this
    build — one derived boolean, separately reviewable."""
    source = inspect.getsource(atelier_schemas)
    assert "assignable=" in source
    assert "on_shift" not in source


# --- F40 C2: the same-day override --------------------------------------------


def _install_override(monkeypatch: pytest.MonkeyPatch, row: StaffUser | None) -> list[Any]:
    """Records the `(on_shift_on, on_shift_override)` pair every write sends, so
    the pair invariant is observable without a database."""
    writes: list[Any] = []

    async def _set(
        _self: object,
        _session: object,
        _tenant_id: uuid.UUID,
        staff_id: uuid.UUID,
        *,
        on_shift_on: datetime.date | None,
        on_shift_override: bool | None,
    ) -> StaffUser | None:
        writes.append(
            {
                "staff_id": staff_id,
                "on_shift_on": on_shift_on,
                "on_shift_override": on_shift_override,
            }
        )
        return row

    monkeypatch.setattr(StaffUsersRepository, "set_on_shift_override", _set)
    return writes


@pytest.mark.parametrize("role", FLOOR)
async def test_a_floor_role_may_not_mark_anybody_on_shift_not_even_herself(
    monkeypatch: pytest.MonkeyPatch, role: StaffRole
) -> None:
    """⚠ D13, AND THE «not even herself» HALF IS THE POINT. A staffer marking
    herself present is an attendance punch and the epic's labour-law row puts
    attendance visibly out of scope — so this is `ELEVATED_ROLES` alone and NEVER
    the self-or-elevated guard the break toggle uses.

    It is also the assertion design F-26 depends on: the console must not render
    the mark button on a seamstress's own card, because her press would be a 403
    and `mutate`'s P-6 rule makes a 403 terminal for the whole floor panel — she
    would lose the board for the session by pressing a button that should never
    have existed.
    """
    me = _staff_user(role=role.value)
    writes = _install_override(monkeypatch, me)
    actor = _actor(role, me.id)

    with pytest.raises(NotAuthorizedError):
        await _service().set_on_shift(TENANT_ID, me.id, on_shift=False, actor=actor)
    with pytest.raises(NotAuthorizedError):
        await _service().set_on_shift(TENANT_ID, uuid.uuid4(), on_shift=True, actor=actor)
    with pytest.raises(NotAuthorizedError):
        await _service().clear_on_shift(TENANT_ID, me.id, actor=actor)

    # ⚠ REFUSED BEFORE ANY WRITE — a 403 raised after one is a change nobody
    # asked for, and after a READ it is an existence oracle.
    assert writes == []


@pytest.mark.parametrize("role", ELEVATED)
async def test_both_elevated_roles_may_mark_a_colleague(
    monkeypatch: pytest.MonkeyPatch, role: StaffRole
) -> None:
    """C4/D13: the override is ELEVATED and never owner-only. A shift manager is
    the person standing on the floor when somebody calls in sick."""
    target = _staff_user()
    writes = _install_override(monkeypatch, target)
    # ⚠ `_install` re-patches `RostersRepository.by_week` to «no roster»
    # (rule 3 is its default), so it MUST run before `_install_roster` or the
    # roster this test is about is silently replaced by no roster at all.
    _install(monkeypatch, wrote=True, row=target, before=target)
    _install_roster(monkeypatch, published=False)

    read = await _service().set_on_shift(TENANT_ID, target.id, on_shift=False, actor=_actor(role))
    assert read.row is target
    assert [write["staff_id"] for write in writes] == [target.id]


async def test_the_date_is_the_servers_jerusalem_today_and_never_the_bodys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ THE ROUTE ACCEPTS NO DATE AT ALL (D3). Accepting one would make rule 1
    pre-settable for TOMORROW — a roster edit wearing an override's clothes — and
    would let a client's clock decide what «today» means. NOW is 11:20 UTC on
    2026-08-02, i.e. 14:20 in Jerusalem."""
    target = _staff_user()
    writes = _install_override(monkeypatch, target)
    # ⚠ `_install` re-patches `RostersRepository.by_week` to «no roster»
    # (rule 3 is its default), so it MUST run before `_install_roster` or the
    # roster this test is about is silently replaced by no roster at all.
    _install(monkeypatch, wrote=True, row=target, before=target)
    _install_roster(monkeypatch, published=False)

    await _service().set_on_shift(
        TENANT_ID, target.id, on_shift=True, actor=_actor(StaffRole.OWNER)
    )
    assert writes[0]["on_shift_on"] == datetime.date(2026, 8, 2)
    assert writes[0]["on_shift_override"] is True


async def test_both_columns_move_together_on_set_and_on_clear(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ D4's PAIR INVARIANT. `staff_users_on_shift_pair_check` refuses one
    without the other, so a writer that set only the date would be a `psycopg`
    error rather than half an override — and half an override would make rule 1
    fire on a NULL answer."""
    target = _staff_user()
    writes = _install_override(monkeypatch, target)
    # ⚠ `_install` re-patches `RostersRepository.by_week` to «no roster»
    # (rule 3 is its default), so it MUST run before `_install_roster` or the
    # roster this test is about is silently replaced by no roster at all.
    _install(monkeypatch, wrote=True, row=target, before=target)
    _install_roster(monkeypatch, published=False)
    actor = _actor(StaffRole.OWNER)

    await _service().set_on_shift(TENANT_ID, target.id, on_shift=False, actor=actor)
    await _service().clear_on_shift(TENANT_ID, target.id, actor=actor)

    assert writes[0]["on_shift_on"] is not None
    assert writes[0]["on_shift_override"] is False
    assert writes[1]["on_shift_on"] is None
    assert writes[1]["on_shift_override"] is None


async def test_the_override_write_returns_the_patched_card_with_its_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ DESIGN F-1. The client CANNOT compute `on_shift_source` — that is the
    whole of D8 — so a route answering `204` would force a refetch or a guess,
    and a guess is the panel disagreeing with itself in Hebrew on a shared floor
    tablet."""
    target = _staff_user()
    target.on_shift_on = jerusalem_moment(NOW)[0]
    target.on_shift_override = False
    _install_override(monkeypatch, target)
    # ⚠ `_install` re-patches `RostersRepository.by_week` to «no roster»
    # (rule 3 is its default), so it MUST run before `_install_roster` or the
    # roster this test is about is silently replaced by no roster at all.
    _install(monkeypatch, wrote=True, row=target, before=target)
    _install_roster(monkeypatch, published=True, rostered={target.id})

    read = await _service().set_on_shift(
        TENANT_ID, target.id, on_shift=False, actor=_actor(StaffRole.OWNER)
    )
    assert (read.on_shift, read.on_shift_source) == (False, OnShiftSource.MANUAL_TODAY)


async def test_clearing_hands_the_answer_back_to_the_roster(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After a clear the source moves to `roster` or `fallback`, and only the
    server can say which — which is the second half of F-1's argument."""
    target = _staff_user()
    _install_override(monkeypatch, target)
    # ⚠ `_install` re-patches `RostersRepository.by_week` to «no roster»
    # (rule 3 is its default), so it MUST run before `_install_roster` or the
    # roster this test is about is silently replaced by no roster at all.
    _install(monkeypatch, wrote=True, row=target, before=target)
    _install_roster(monkeypatch, published=True, rostered={target.id})

    read = await _service().clear_on_shift(TENANT_ID, target.id, actor=_actor(StaffRole.OWNER))
    assert (read.on_shift, read.on_shift_source) == (True, OnShiftSource.ROSTER)


async def test_both_override_writes_audit_with_ids_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ THE AUDIT ROW IS THE ONLY DURABLE RECORD of who flipped it and when — D4
    puts no `set_at`/`set_by` on `staff_users` (F38's precedent verbatim). Ids and
    flags only, never a display name: `audit_log` has no retention class and
    platform operators read across tenants."""
    target = _staff_user(display_name="דנה כהן")
    _install_override(monkeypatch, target)
    writes = _install(monkeypatch, wrote=True, row=target, before=target)
    _install_roster(monkeypatch, published=False)
    actor = _actor(StaffRole.OWNER)

    await _service().set_on_shift(TENANT_ID, target.id, on_shift=False, actor=actor)
    await _service().clear_on_shift(TENANT_ID, target.id, actor=actor)

    assert [entry["action"] for entry in writes.audit] == [
        AuditAction.ON_SHIFT_OVERRIDE_SET.value,
        AuditAction.ON_SHIFT_OVERRIDE_CLEARED.value,
    ]
    assert writes.audit[0]["details"] == {
        "target": str(target.id),
        "on_shift_on": "2026-08-02",
        "on_shift": False,
    }
    assert "דנה כהן" not in str(writes.audit)


async def test_an_unknown_staffer_is_a_404_on_both_verbs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_override(monkeypatch, None)
    actor = _actor(StaffRole.OWNER)
    with pytest.raises(DomainNotFoundError):
        await _service().set_on_shift(TENANT_ID, uuid.uuid4(), on_shift=True, actor=actor)
    with pytest.raises(DomainNotFoundError):
        await _service().clear_on_shift(TENANT_ID, uuid.uuid4(), actor=actor)


async def test_a_second_set_overwrites_rather_than_appending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ D4's «no table» argument, observable: one override per person per day,
    only today's is ever read, so there is no sort order, no per-parent cap, no
    count and no sweep loop. A table would buy a repository and an RLS policy to
    express «at most one»."""
    target = _staff_user()
    writes = _install_override(monkeypatch, target)
    # ⚠ `_install` re-patches `RostersRepository.by_week` to «no roster»
    # (rule 3 is its default), so it MUST run before `_install_roster` or the
    # roster this test is about is silently replaced by no roster at all.
    _install(monkeypatch, wrote=True, row=target, before=target)
    _install_roster(monkeypatch, published=False)
    actor = _actor(StaffRole.OWNER)

    await _service().set_on_shift(TENANT_ID, target.id, on_shift=False, actor=actor)
    await _service().set_on_shift(TENANT_ID, target.id, on_shift=True, actor=actor)

    assert [write["on_shift_override"] for write in writes] == [False, True]
