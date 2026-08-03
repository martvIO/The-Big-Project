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

import datetime
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.auth.dependencies import NotAuthorizedError
from app.auth.service import StaffContext
from app.db.repositories.audit_log import AuditLogRepository
from app.db.repositories.staff_users import StaffUsersRepository
from app.errors import DomainNotFoundError
from app.floor.service import FloorService, card_status
from app.models.constants import AuditAction, StaffCardStatus, StaffRole
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

    monkeypatch.setattr(StaffUsersRepository, "by_id", _by_id)
    monkeypatch.setattr(StaffUsersRepository, "start_break", _start)
    monkeypatch.setattr(StaffUsersRepository, "end_break", _end)
    monkeypatch.setattr(AuditLogRepository, "record", _record)
    return writes


# --- the authorization matrix (D6) ------------------------------------------


@pytest.mark.parametrize("role", ELEVATED)
async def test_an_elevated_role_may_toggle_anybody(
    monkeypatch: pytest.MonkeyPatch, role: StaffRole
) -> None:
    target = _staff_user(break_started_at=NOW)
    writes = _install(monkeypatch, wrote=True, row=target)

    result = await _service().start_break(TENANT_ID, target.id, actor=_actor(role))

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

    result = await _service().start_break(TENANT_ID, me.id, actor=_actor(role, me.id))

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

    result = await _service().start_break(TENANT_ID, target.id, actor=actor)

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

    result = await _service().start_break(TENANT_ID, target.id, actor=_actor(StaffRole.OWNER))

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

    result = await _service().end_break(TENANT_ID, before.id, actor=actor)

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

    result = await _service().end_break(TENANT_ID, target.id, actor=_actor(StaffRole.OWNER))

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
    assert card_status(_staff_user(break_started_at=NOW)) is StaffCardStatus.BREAK
    assert card_status(_staff_user(break_started_at=None)) is StaffCardStatus.AVAILABLE


def test_the_card_status_wire_literals_are_exactly_available_break_and_occupied() -> None:
    """⚠ SET EQUALITY, and it is still the test that refuses a value with no
    writer.

    F36 gives `occupied` one — an open `fitting_room_assignments` row — and
    widens this in the same PR, which is `ScheduledMessageKind`'s rule MET
    rather than waived. A fourth value added ahead of its producer fails here.
    """
    assert {status.value for status in StaffCardStatus} == {"available", "break", "occupied"}
