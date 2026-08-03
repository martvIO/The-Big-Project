"""F37's verbs, driven with fakes and no database.

**This is where «a page is never silently dropped» is actually proven.** The
raise's three failure modes are a closed list, and the list is a table a test can
walk — every other row in the boutique's state answers 200 with an alert.

The fake session factory is `test_floor_service.py`'s scaffold: enough surface
for `tenant_session`'s `set_config` and nothing else, so a statement escaping to
a real session raises here instead of passing silently.

What is NOT proven here and must not be claimed: that the guarded UPDATE and its
`populate_existing` re-read behave under a real identity map, and that the
resolve's captured local survives ORM-enabled DML. `test_sos_repositories.py` and
`test_sos_db.py` own those, because a monkeypatched repository never stamps
anything.
"""

import datetime
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.auth.service import StaffContext
from app.db.repositories.audit_log import AuditLogRepository
from app.db.repositories.sessions import SessionsRepository
from app.db.repositories.sos_alerts import SosAlertsRepository
from app.db.repositories.staff_users import StaffUsersRepository
from app.errors import DomainNotFoundError
from app.floor.service import FloorService
from app.floor.validation import (
    MAX_SOS_NOTE_LENGTH,
    SosAlreadyAcceptedError,
    SosClosedError,
    SosValidationError,
)
from app.models.constants import AuditAction, SosStatus, StaffRole
from app.models.fitting_room_assignment import FittingRoomAssignment
from app.models.sos_alert import SosAlert
from app.models.staff_user import StaffUser

TENANT_ID = uuid.uuid4()
NOW = datetime.datetime(2026, 8, 3, 11, 20, tzinfo=datetime.UTC)

ELEVATED = [StaffRole.OWNER, StaffRole.SHIFT_MANAGER]
FLOOR = [StaffRole.RECEPTION, StaffRole.SALES_ASSISTANT, StaffRole.SEAMSTRESS]


def _actor(role: StaffRole, staff_id: uuid.UUID | None = None) -> StaffContext:
    return StaffContext(
        id=staff_id or uuid.uuid4(),
        tenant_id=TENANT_ID,
        email="staff@example.com",
        display_name="נועה לוי",
        # ⚠ `.value`, not the member. `ELEVATED_ROLES` is a frozenset of STRING
        # values, so a fake built from the enum member would compare unequal and
        # every elevated row would pass vacuously against a wrong implementation.
        role=role.value,
    )


def _staff_user(display_name: str = "דנה כהן") -> StaffUser:
    row = StaffUser(
        tenant_id=TENANT_ID,
        email="staff@example.com",
        password_hash="not-a-real-hash",
        display_name=display_name,
        role=StaffRole.SEAMSTRESS.value,
    )
    row.id = uuid.uuid4()
    return row


def _alert(**overrides: Any) -> SosAlert:
    row = SosAlert(
        tenant_id=TENANT_ID,
        raised_by=uuid.uuid4(),
        target_staff_user_id=None,
        fitting_room_assignment_id=None,
        note=None,
        status=SosStatus.OPEN,
    )
    row.id = uuid.uuid4()
    row.accepted_by = None
    row.acknowledged_at = None
    row.created_at = NOW
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


class _Recorder:
    """`order` is the whole point. «The refusal is not an existence oracle» is
    not "an error was raised" — it is "the writer was never reached", and only a
    sequence can say that."""

    def __init__(self) -> None:
        self.order: list[str] = []
        self.audit: list[dict[str, Any]] = []
        self.inserted: list[dict[str, Any]] = []
        self.accepted: list[dict[str, Any]] = []


def _install_raise(
    monkeypatch: pytest.MonkeyPatch,
    *,
    assignment: FittingRoomAssignment | None = None,
    target_row: StaffUser | None = None,
    target_live: bool = True,
) -> _Recorder:
    recorder = _Recorder()

    async def _assignment_of(
        _self: object,
        _session: object,
        _tenant_id: uuid.UUID,
        assignment_id: uuid.UUID,
        staff_user_id: uuid.UUID,
    ) -> FittingRoomAssignment | None:
        recorder.order.append("assignment_of")
        return assignment

    async def _staff_by_id(
        _self: object, _session: object, _tenant_id: uuid.UUID, staff_id: uuid.UUID
    ) -> StaffUser | None:
        recorder.order.append("staff_by_id")
        return target_row

    async def _has_live_session(
        _self: object,
        _session: object,
        _tenant_id: uuid.UUID,
        _staff_id: uuid.UUID,
        _now: datetime.datetime,
    ) -> bool:
        recorder.order.append("has_live_session")
        return target_live

    async def _insert(
        _self: object,
        _session: object,
        tenant_id: uuid.UUID,
        *,
        raised_by: uuid.UUID,
        target_staff_user_id: uuid.UUID | None,
        fitting_room_assignment_id: uuid.UUID | None,
        note: str | None,
    ) -> SosAlert:
        recorder.order.append("insert")
        recorder.inserted.append(
            {
                "tenant_id": tenant_id,
                "raised_by": raised_by,
                "target_staff_user_id": target_staff_user_id,
                "fitting_room_assignment_id": fitting_room_assignment_id,
                "note": note,
            }
        )
        return _alert(
            raised_by=raised_by,
            target_staff_user_id=target_staff_user_id,
            fitting_room_assignment_id=fitting_room_assignment_id,
            note=note,
        )

    monkeypatch.setattr(SosAlertsRepository, "assignment_of", _assignment_of)
    monkeypatch.setattr(SosAlertsRepository, "insert", _insert)
    monkeypatch.setattr(StaffUsersRepository, "by_id", _staff_by_id)
    monkeypatch.setattr(SessionsRepository, "has_live_session", _has_live_session)
    _install_audit(monkeypatch, recorder)
    return recorder


def _install_audit(monkeypatch: pytest.MonkeyPatch, recorder: _Recorder) -> None:
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
        recorder.order.append("audit")
        recorder.audit.append(
            {"action": action, "actor_id": actor_id, "entity": entity} | {"details": details}
        )

    monkeypatch.setattr(AuditLogRepository, "record", _record)


# --- VERB 1: raise -----------------------------------------------------------


@pytest.mark.parametrize("role", [*ELEVATED, *FLOOR])
async def test_every_role_may_raise_and_raises_only_for_herself(
    monkeypatch: pytest.MonkeyPatch, role: StaffRole
) -> None:
    """⚠ **There is NO `_authorize` call on this route and its absence is the
    design, not an omission.** `_authorize`'s docstring names the hazard as a
    body-supplied `staff_user_id` doubling as the caller's identity; the raise
    body carries a TARGET and never an actor. Nobody may raise a page AS somebody
    else — not even an owner — because an SOS is a first-person statement, and an
    owner who needs help raises her own."""
    recorder = _install_raise(monkeypatch)
    actor = _actor(role)
    result = await _service().raise_sos(
        TENANT_ID,
        target_staff_user_id=None,
        fitting_room_assignment_id=None,
        note=None,
        actor=actor,
    )
    assert result.alert.raised_by == actor.id
    assert result.rerouted is False
    assert recorder.inserted[0]["raised_by"] == actor.id


async def test_a_note_is_stripped_and_an_empty_one_is_stored_as_null(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = _install_raise(monkeypatch)
    service = _service()
    await service.raise_sos(
        TENANT_ID,
        target_staff_user_id=None,
        fitting_room_assignment_id=None,
        note="  צריך סיכות  ",
        actor=_actor(StaffRole.SEAMSTRESS),
    )
    await service.raise_sos(
        TENANT_ID,
        target_staff_user_id=None,
        fitting_room_assignment_id=None,
        note="   ",
        actor=_actor(StaffRole.SEAMSTRESS),
    )
    assert recorder.inserted[0]["note"] == "צריך סיכות"
    assert recorder.inserted[1]["note"] is None


async def test_a_note_past_the_bound_is_refused_before_anything_is_written(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = _install_raise(monkeypatch)
    with pytest.raises(SosValidationError):
        await _service().raise_sos(
            TENANT_ID,
            target_staff_user_id=None,
            fitting_room_assignment_id=None,
            note="א" * (MAX_SOS_NOTE_LENGTH + 1),
            actor=_actor(StaffRole.SEAMSTRESS),
        )
    assert recorder.order == []


async def test_paging_yourself_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """A self-page has no audience. It would sit open forever, escalating to the
    shift manager for nothing, and the raiser never gets the overlay for her own
    page — so nothing on any screen would ever surface it to her either."""
    recorder = _install_raise(monkeypatch)
    actor = _actor(StaffRole.SEAMSTRESS)
    with pytest.raises(SosValidationError):
        await _service().raise_sos(
            TENANT_ID,
            target_staff_user_id=actor.id,
            fitting_room_assignment_id=None,
            note=None,
            actor=actor,
        )
    assert recorder.order == []


async def test_nothing_about_the_boutique_can_refuse_a_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ **THE table walk, and it IS «a page is never silently dropped».**

    Not a missing room, not a room that no longer resolves, not an assignment
    belonging to another staffer, not an unknown target, not a logged-out target,
    not a deleted target. Every row creates the alert.

    The three failure modes are exhaustively 401 (no session), 403 (a role
    outside the five — unreachable for a signed-in staffer, since the router
    admits all five) and 400 (note too long, or self-target). This test is the
    other half of that sentence.
    """
    actor = _actor(StaffRole.SEAMSTRESS)
    unknown_target = uuid.uuid4()
    unknown_assignment = uuid.uuid4()

    rows: list[tuple[str, dict[str, Any], uuid.UUID | None, uuid.UUID | None, bool]] = [
        # name, install kwargs, expected stored target, expected stored assignment, rerouted
        ("no room and the shift-manager role", {}, None, None, False),
        (
            "an assignment that does not resolve",
            {"assignment": None},
            None,
            None,
            False,
        ),
        (
            "an unknown target staff id",
            {"target_row": None},
            None,
            None,
            True,
        ),
        (
            "a target who is logged out",
            {"target_row": _staff_user(), "target_live": False},
            None,
            None,
            True,
        ),
    ]
    for name, kwargs, expected_target, expected_assignment, rerouted in rows:
        recorder = _install_raise(monkeypatch, **kwargs)
        target = unknown_target if "target_row" in kwargs else None
        result = await _service().raise_sos(
            TENANT_ID,
            target_staff_user_id=target,
            fitting_room_assignment_id=unknown_assignment if "assignment" in kwargs else None,
            note=None,
            actor=actor,
        )
        assert result.alert.status == SosStatus.OPEN, name
        assert result.alert.target_staff_user_id == expected_target, name
        assert result.alert.fitting_room_assignment_id == expected_assignment, name
        assert result.rerouted is rerouted, name
        assert "insert" in recorder.order, name


async def test_a_reachable_named_target_is_stored_and_is_not_rerouted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = _staff_user()
    recorder = _install_raise(monkeypatch, target_row=target, target_live=True)
    result = await _service().raise_sos(
        TENANT_ID,
        target_staff_user_id=target.id,
        fitting_room_assignment_id=None,
        note=None,
        actor=_actor(StaffRole.SEAMSTRESS),
    )
    assert result.rerouted is False
    assert result.alert.target_staff_user_id == target.id
    assert recorder.order.index("staff_by_id") < recorder.order.index("has_live_session")


async def test_the_reroute_audit_row_records_who_was_meant_to_get_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ **The `requested_target` / `target` PAIR is the whole point.** The
    reroute writes NULL into the column, destroying the only record of whom she
    actually tried to page. Without the pair the trail records that a page went
    to the shift manager and cannot say Dana was meant to get it — which is the
    single most useful thing a pilot review could ask this table."""
    target = _staff_user()
    recorder = _install_raise(monkeypatch, target_row=target, target_live=False)
    actor = _actor(StaffRole.SEAMSTRESS)
    result = await _service().raise_sos(
        TENANT_ID,
        target_staff_user_id=target.id,
        fitting_room_assignment_id=None,
        note=None,
        actor=actor,
    )
    assert result.rerouted is True
    assert recorder.audit == [
        {
            "action": AuditAction.SOS_RAISED,
            "actor_id": actor.id,
            "entity": str(result.alert.id),
            "details": {
                "alert": str(result.alert.id),
                "requested_target": str(target.id),
                "target": None,
                "rerouted": True,
                "assignment": None,
            },
        }
    ]
    # The audit row is written INSIDE the transaction, after the insert and
    # before the commit — never after the answer has been handed back.
    assert recorder.order[-1] == "audit"


async def test_a_role_targeted_raise_records_no_requested_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`requested_target` is null when she asked for the ROLE, which is what
    makes the pair readable: a null requested target and a null target is the
    shift-manager route; a named requested target and a null target is a
    reroute."""
    recorder = _install_raise(monkeypatch)
    result = await _service().raise_sos(
        TENANT_ID,
        target_staff_user_id=None,
        fitting_room_assignment_id=None,
        note=None,
        actor=_actor(StaffRole.SEAMSTRESS),
    )
    assert result.rerouted is False
    assert recorder.audit[0]["details"] == {
        "alert": str(result.alert.id),
        "requested_target": None,
        "target": None,
        "rerouted": False,
        "assignment": None,
    }
    # No target was named, so neither read was issued at all.
    assert "staff_by_id" not in recorder.order
    assert "has_live_session" not in recorder.order


# --- VERB 2: accept ----------------------------------------------------------


# The writer's re-read is a THIRD value, independent of the row the service
# first read: `(False, None)` is gone and `(False, row)` is conflicted, and a
# helper that collapsed the two would make the 404 branch untestable.
_UNSET = cast(SosAlert, object())


def _install_accept(
    monkeypatch: pytest.MonkeyPatch,
    *,
    row: SosAlert | None,
    wrote: bool = True,
    after: SosAlert | None = _UNSET,
    acceptor: StaffUser | None = None,
) -> _Recorder:
    recorder = _Recorder()

    async def _by_id(
        _self: object, _session: object, _tenant_id: uuid.UUID, _alert_id: uuid.UUID
    ) -> SosAlert | None:
        recorder.order.append("by_id")
        return row

    async def _accept(
        _self: object,
        _session: object,
        _tenant_id: uuid.UUID,
        alert_id: uuid.UUID,
        *,
        actor_id: uuid.UUID,
        at: datetime.datetime,
    ) -> tuple[bool, SosAlert | None]:
        recorder.order.append("accept")
        recorder.accepted.append({"alert_id": alert_id, "actor_id": actor_id, "at": at})
        return wrote, (row if after is _UNSET else after)

    async def _staff_by_id(
        _self: object, _session: object, _tenant_id: uuid.UUID, staff_id: uuid.UUID
    ) -> StaffUser | None:
        recorder.order.append("staff_by_id")
        return acceptor

    monkeypatch.setattr(SosAlertsRepository, "by_id", _by_id)
    monkeypatch.setattr(SosAlertsRepository, "accept", _accept)
    monkeypatch.setattr(StaffUsersRepository, "by_id", _staff_by_id)
    _install_audit(monkeypatch, recorder)
    return recorder


async def test_the_named_target_may_accept(monkeypatch: pytest.MonkeyPatch) -> None:
    actor = _actor(StaffRole.SEAMSTRESS)
    row = _alert(target_staff_user_id=actor.id)
    accepted = _alert(
        id=row.id,
        target_staff_user_id=actor.id,
        status=SosStatus.ACCEPTED,
        accepted_by=actor.id,
        acknowledged_at=NOW,
    )
    recorder = _install_accept(monkeypatch, row=row, wrote=True, after=accepted)
    result = await _service().accept_sos(TENANT_ID, row.id, actor=actor)
    assert result.status == SosStatus.ACCEPTED
    assert result.accepted_by == actor.id
    assert recorder.accepted[0]["at"] == NOW
    assert recorder.audit[0]["action"] == AuditAction.SOS_ACCEPTED
    assert recorder.audit[0]["details"] == {"alert": str(row.id), "raised_by": str(row.raised_by)}


@pytest.mark.parametrize("role", ELEVATED)
async def test_an_elevated_caller_may_accept_anything(
    monkeypatch: pytest.MonkeyPatch, role: StaffRole
) -> None:
    """The shift manager is the universal fallback and may accept anything,
    regardless of her own role — the e7 brief's phrase, preserved."""
    actor = _actor(role)
    row = _alert(target_staff_user_id=uuid.uuid4())
    accepted = _alert(id=row.id, status=SosStatus.ACCEPTED, accepted_by=actor.id)
    _install_accept(monkeypatch, row=row, wrote=True, after=accepted)
    assert (await _service().accept_sos(TENANT_ID, row.id, actor=actor)).accepted_by == actor.id


async def test_a_refused_accept_is_a_404_and_never_reaches_the_writer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ **404 and not 403, byte-identical to a missing id.** Whose alert it is
    can only be learned by READING it, so a 403 on a real id and a 404 on a fake
    one would discriminate existence and let a seamstress enumerate the tenant's
    alerts.

    And the assertion that matters is `"accept" not in order`: "an error was
    raised" would still hold if the permission check ran AFTER the UPDATE, and a
    stranger's accept would have silently succeeded."""
    stranger = _actor(StaffRole.SEAMSTRESS)
    row = _alert(target_staff_user_id=uuid.uuid4())
    recorder = _install_accept(monkeypatch, row=row)
    with pytest.raises(DomainNotFoundError):
        await _service().accept_sos(TENANT_ID, row.id, actor=stranger)
    assert "accept" not in recorder.order
    assert recorder.audit == []


async def test_the_raiser_may_not_accept_her_own_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """She has resolve and cancel. Accepting her own page would put her name on
    the card the boutique reads as «somebody is going», which is the one claim
    this feature must never make falsely."""
    actor = _actor(StaffRole.SEAMSTRESS)
    row = _alert(raised_by=actor.id, target_staff_user_id=None)
    recorder = _install_accept(monkeypatch, row=row)
    with pytest.raises(DomainNotFoundError):
        await _service().accept_sos(TENANT_ID, row.id, actor=actor)
    assert "accept" not in recorder.order


async def test_an_unknown_alert_is_a_404(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = _install_accept(monkeypatch, row=None)
    with pytest.raises(DomainNotFoundError):
        await _service().accept_sos(TENANT_ID, uuid.uuid4(), actor=_actor(StaffRole.OWNER))
    assert "accept" not in recorder.order


async def test_a_re_accept_by_the_current_owner_is_a_200_with_no_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ **IDEMPOTENCE FIRST, keyed on the REQUEST, and the ORDER is the rule.**
    She tapped twice, or two of her devices did. Resolved after the 409 instead
    of before, a double-tap tells her — by name — that SHE has it, as an error.
    Every single-accept test stays green either way, which is why this one
    exists."""
    actor = _actor(StaffRole.SEAMSTRESS)
    row = _alert(
        target_staff_user_id=actor.id,
        status=SosStatus.ACCEPTED,
        accepted_by=actor.id,
        acknowledged_at=NOW,
    )
    recorder = _install_accept(monkeypatch, row=row)
    result = await _service().accept_sos(TENANT_ID, row.id, actor=actor)
    assert result is row
    assert "accept" not in recorder.order
    assert recorder.audit == []


async def test_a_losing_accept_is_a_409_that_names_the_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ruling's «a 409 NAMING THE OWNER», and it is why `accepted_by` is a
    column: neither `status` nor `acknowledged_at` can answer it."""
    winner = _staff_user("דנה כהן")
    row = _alert(status=SosStatus.ACCEPTED, accepted_by=winner.id, acknowledged_at=NOW)
    recorder = _install_accept(monkeypatch, row=row, wrote=False, after=row, acceptor=winner)
    with pytest.raises(SosAlreadyAcceptedError) as raised:
        await _service().accept_sos(TENANT_ID, row.id, actor=_actor(StaffRole.SHIFT_MANAGER))
    assert raised.value.details == {"staff_display_name": "דנה כהן"}
    assert recorder.audit == []


async def test_an_accept_whose_winner_was_removed_does_not_name_nobody(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ `accepted_by` names a `staff_users` row that staff removal can
    soft-delete at any time, and the acceptor can be removed between her accept
    and this read. `details` is therefore OPTIONAL and the key is ABSENT — never
    `{"staff_display_name": null}`, which would render «{{name}} כבר מגיעה.» with
    an empty interpolation on a legally binding surface."""
    row = _alert(status=SosStatus.ACCEPTED, accepted_by=uuid.uuid4(), acknowledged_at=NOW)
    _install_accept(monkeypatch, row=row, wrote=False, after=row, acceptor=None)
    with pytest.raises(SosAlreadyAcceptedError) as raised:
        await _service().accept_sos(TENANT_ID, row.id, actor=_actor(StaffRole.OWNER))
    assert raised.value.details is None


@pytest.mark.parametrize("status", [SosStatus.RESOLVED, SosStatus.CANCELLED])
async def test_accepting_a_closed_alert_is_its_own_409(
    monkeypatch: pytest.MonkeyPatch, status: SosStatus
) -> None:
    """Two codes and not one with a discriminating `details`: two causes, two
    Hebrew sentences, two remedies (go somewhere else / there is nothing to do).
    And SOS_CLOSED never carries `details` — there is nobody to name."""
    row = _alert(status=status)
    _install_accept(monkeypatch, row=row, wrote=False, after=row)
    with pytest.raises(SosClosedError) as raised:
        await _service().accept_sos(TENANT_ID, row.id, actor=_actor(StaffRole.OWNER))
    assert raised.value.details is None


async def test_a_zero_row_accept_that_reads_back_open_raises_rather_than_returning_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ **The unreachable branch is genuinely unreachable and must STILL have an
    `else: raise`.** A zero-row UPDATE takes no lock and the repo runs READ
    COMMITTED, so a concurrent write can move the row between the UPDATE and the
    re-read — but nothing moves a row BACK to `open`, and `uuid_generate_v4()`
    makes delete-and-recreate-with-the-same-id impossible.

    It is spelled as a raise rather than as a comment claiming impossibility
    because F41's review found exactly that: an "impossible" branch with no
    `else` returns `None` and 500s with no message."""
    row = _alert(status=SosStatus.OPEN)
    _install_accept(monkeypatch, row=row, wrote=False, after=row)
    with pytest.raises(RuntimeError):
        await _service().accept_sos(TENANT_ID, row.id, actor=_actor(StaffRole.OWNER))


async def test_a_zero_row_accept_whose_row_vanished_is_a_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`(False, None)` from the writer is gone, not conflicted."""
    row = _alert()
    _install_accept(monkeypatch, row=row, wrote=False, after=None)
    with pytest.raises(DomainNotFoundError):
        await _service().accept_sos(TENANT_ID, row.id, actor=_actor(StaffRole.OWNER))
