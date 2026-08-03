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
from app.db.repositories.sos_alerts import SosAlertRow, SosAlertsRepository
from app.db.repositories.staff_users import StaffUsersRepository
from app.errors import DomainNotFoundError
from app.floor.service import (
    ESCALATION_AFTER,
    STALLED_AFTER,
    FloorService,
    _escalated,
    _for_me,
    _stalled,
)
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
        # `.value`, not the member, because `StaffContext.role` is a `str` and
        # `ELEVATED_ROLES` is a frozenset of STRING values.
        #
        # ⚠ **The inherited reason for this line was wrong and F37 corrected it
        # rather than copying it.** It claimed a fake built from the enum member
        # "would compare unequal and every elevated row would pass vacuously".
        # `StaffRole` is a `StrEnum`, so a member and its value compare AND hash
        # equal and the membership test is byte-identical: mutation run, all 72
        # cases stayed GREEN. The rule survives as consistency with the wire
        # type; the vacuity argument does not.
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


def _view(alert: SosAlert, **names: str | None) -> SosAlertRow:
    """The joined row every verb answers with. The four names default to None:
    what they resolve to is the repository's business and is proven against a
    real database, never here."""
    return SosAlertRow(
        alert=alert,
        raised_by_name=names.get("raised_by_name"),
        target_name=names.get("target_name"),
        accepted_by_name=names.get("accepted_by_name"),
        room_label=names.get("room_label"),
    )


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
        # Every row the writers minted, so the view read each verb answers with
        # can hand the same one back instead of inventing a second.
        self.rows: list[SosAlert] = []
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
        row = _alert(
            raised_by=raised_by,
            target_staff_user_id=target_staff_user_id,
            fitting_room_assignment_id=fitting_room_assignment_id,
            note=note,
        )
        recorder.rows.append(row)
        return row

    async def _view_of(
        _self: object, _session: object, _tenant_id: uuid.UUID, alert_id: uuid.UUID
    ) -> SosAlertRow | None:
        recorder.order.append("view_of")
        return _view(next(row for row in recorder.rows if row.id == alert_id))

    monkeypatch.setattr(SosAlertsRepository, "assignment_of", _assignment_of)
    monkeypatch.setattr(SosAlertsRepository, "insert", _insert)
    monkeypatch.setattr(SosAlertsRepository, "view_of", _view_of)
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
    assert result.sos.alert.raised_by == actor.id
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
        assert result.sos.alert.status == SosStatus.OPEN, name
        assert result.sos.alert.target_staff_user_id == expected_target, name
        assert result.sos.alert.fitting_room_assignment_id == expected_assignment, name
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
    assert result.sos.alert.target_staff_user_id == target.id
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
            "entity": str(result.sos.alert.id),
            "details": {
                "alert": str(result.sos.alert.id),
                "requested_target": str(target.id),
                "target": None,
                "rerouted": True,
                "assignment": None,
            },
        }
    ]
    # The audit row is written INSIDE the transaction, after the insert and
    # before the commit — never after the answer has been handed back. The view
    # read that renders that answer is the last statement, and it too is inside.
    assert recorder.order[-3:] == ["insert", "audit", "view_of"]


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
        "alert": str(result.sos.alert.id),
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

    async def _view_of(
        _self: object, _session: object, _tenant_id: uuid.UUID, _alert_id: uuid.UUID
    ) -> SosAlertRow | None:
        recorder.order.append("view_of")
        answered = row if after is _UNSET else after
        return _view(answered) if answered is not None else None

    monkeypatch.setattr(SosAlertsRepository, "by_id", _by_id)
    monkeypatch.setattr(SosAlertsRepository, "accept", _accept)
    monkeypatch.setattr(SosAlertsRepository, "view_of", _view_of)
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
    assert result.alert.status == SosStatus.ACCEPTED
    assert result.alert.accepted_by == actor.id
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
    answered = await _service().accept_sos(TENANT_ID, row.id, actor=actor)
    assert answered.alert.accepted_by == actor.id


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
    assert result.alert is row
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


# --- the read-time predicates (D6, D7) ---------------------------------------
#
# ⚠ **Pure branches over a row and a clock, and that is the argument for
# computing escalation in Python at all**: the whole of the thirty-second ruling
# and the whole `for_me` matrix are proven here with no Postgres, no worker, no
# sleeping and no write.


def _seconds_old(seconds: float) -> SosAlert:
    return _alert(created_at=NOW - datetime.timedelta(seconds=seconds))


def test_an_alert_open_for_31_seconds_is_escalated_and_one_open_for_29_is_not() -> None:
    assert _escalated(_seconds_old(31), server_now=NOW) is True
    assert _escalated(_seconds_old(29), server_now=NOW) is False


def test_the_escalation_threshold_is_inclusive_at_exactly_thirty_seconds() -> None:
    """⚠ **THE `>=` boundary, and no other test in the feature lands on it.**
    Thirty seconds is the ruling; `>` would make the rule «after thirty seconds»
    and nothing else would notice."""
    assert datetime.timedelta(seconds=30) == ESCALATION_AFTER
    assert _escalated(_alert(created_at=NOW - ESCALATION_AFTER), server_now=NOW) is True


def test_an_accepted_alert_never_escalates() -> None:
    """The hole `_stalled` exists to close: from here on nothing about this row
    escalates, forever.

    ⚠ **This test does NOT pin the `status != OPEN` conjunct and the plan said it
    would.** Mutation run: dropping that conjunct leaves this case GREEN, because
    an accepted row also carries `acknowledged_at` and the second conjunct
    catches it. What pins the status guard is
    `test_a_closed_alert_never_escalates`, whose rows are closed with NO
    acknowledgement. Recorded here rather than left as a table implying
    otherwise."""
    old = _alert(
        created_at=NOW - datetime.timedelta(minutes=5),
        status=SosStatus.ACCEPTED,
        accepted_by=uuid.uuid4(),
        acknowledged_at=NOW,
    )
    assert _escalated(old, server_now=NOW) is False


@pytest.mark.parametrize("status", [SosStatus.RESOLVED, SosStatus.CANCELLED])
def test_a_closed_alert_never_escalates(status: SosStatus) -> None:
    """⚠ **THE mutation target for `row.status != SosStatus.OPEN`, and the only
    one.** These rows carry no `acknowledged_at`, so the conjunct that shadows it
    on an accepted row is not there to cover for it.

    The OTHER conjunct, `acknowledged_at is not None`, is genuinely unmutatable —
    D6 concedes it is already implied — and deleting it leaves all 72 cases
    green. Mutation run; saying so is better than a table implying three pinned
    clauses where there are two."""
    assert (
        _escalated(
            _alert(created_at=NOW - datetime.timedelta(hours=1), status=status), server_now=NOW
        )
        is False
    )


def test_an_alert_created_after_server_now_is_not_escalated() -> None:
    """⚠ **An ASSERTION, deliberately not a mutation target, and the negative is
    the whole reason there is no `max(timedelta(0), …)` clamp here.**

    `lib/elapsed.ts` clamps because it returns a RENDERED NUMBER and a negative
    delta ships «כבר -1 דק'» to a screen. This returns a BOOLEAN against a
    one-sided positive threshold, so `timedelta(seconds=-5) >= timedelta(30)` is
    already False — byte-identical to the clamped result. Spec review ran the
    "drop the clamp" mutation and it came back GREEN, which is exactly the false
    confidence a mutation regime exists to catch."""
    assert _escalated(_seconds_old(-5), server_now=NOW) is False


def _accepted(minutes: float) -> SosAlert:
    return _alert(
        status=SosStatus.ACCEPTED,
        accepted_by=uuid.uuid4(),
        acknowledged_at=NOW - datetime.timedelta(minutes=minutes),
    )


def test_an_alert_accepted_three_minutes_ago_is_stalled_and_one_accepted_a_minute_ago_is_not() -> (
    None
):
    assert _stalled(_accepted(3), server_now=NOW) is True
    assert _stalled(_accepted(1), server_now=NOW) is False


def test_the_stall_threshold_is_inclusive_at_exactly_two_minutes() -> None:
    assert datetime.timedelta(minutes=2) == STALLED_AFTER
    assert _stalled(_accepted(2), server_now=NOW) is True


@pytest.mark.parametrize("status", [SosStatus.OPEN, SosStatus.RESOLVED, SosStatus.CANCELLED])
def test_only_an_accepted_alert_can_stall(status: SosStatus) -> None:
    """An OPEN one escalates instead; a closed one is nobody's job. `_stalled` is
    about the SECOND silence and there is exactly one state that can fall into
    it."""
    row = _alert(status=status, acknowledged_at=NOW - datetime.timedelta(hours=1))
    assert _stalled(row, server_now=NOW) is False


def test_an_accepted_alert_with_no_acknowledgement_is_not_stalled() -> None:
    """Unrepresentable — one UPDATE writes both — and spelled anyway so the
    predicate reads as the rule rather than as a consequence."""
    assert _stalled(_alert(status=SosStatus.ACCEPTED), server_now=NOW) is False


# --- the `for_me` matrix (AC6) ------------------------------------------------

RAISER = uuid.uuid4()
NAMED = uuid.uuid4()
STRANGER = uuid.uuid4()


def _matrix_alert(*, target: uuid.UUID | None, status: SosStatus) -> SosAlert:
    return _alert(
        raised_by=RAISER,
        target_staff_user_id=target,
        status=status,
        accepted_by=STRANGER if status == SosStatus.ACCEPTED else None,
        acknowledged_at=NOW if status == SosStatus.ACCEPTED else None,
    )


# who, role, target, status, escalated, stalled, expected
_FOR_ME: list[tuple[str, uuid.UUID, StaffRole, uuid.UUID | None, SosStatus, bool, bool, bool]] = [
    # OPEN, role-targeted (target is None = the shift-manager ROLE).
    ("raiser", RAISER, StaffRole.SEAMSTRESS, None, SosStatus.OPEN, False, False, False),
    ("floor role", STRANGER, StaffRole.SEAMSTRESS, None, SosStatus.OPEN, False, False, False),
    ("shift manager", STRANGER, StaffRole.SHIFT_MANAGER, None, SosStatus.OPEN, False, False, True),
    ("owner", STRANGER, StaffRole.OWNER, None, SosStatus.OPEN, False, False, True),
    # …and escalation changes nothing for the role-targeted case: she was the
    # audience from t=0, because she is the fallback.
    ("shift manager", STRANGER, StaffRole.SHIFT_MANAGER, None, SosStatus.OPEN, True, False, True),
    ("raiser", RAISER, StaffRole.OWNER, None, SosStatus.OPEN, True, False, False),
    # OPEN, name-targeted at NAMED, not yet escalated.
    ("named target", NAMED, StaffRole.SEAMSTRESS, NAMED, SosStatus.OPEN, False, False, True),
    ("floor role", STRANGER, StaffRole.SEAMSTRESS, NAMED, SosStatus.OPEN, False, False, False),
    (
        "shift manager",
        STRANGER,
        StaffRole.SHIFT_MANAGER,
        NAMED,
        SosStatus.OPEN,
        False,
        False,
        False,
    ),
    ("owner", STRANGER, StaffRole.OWNER, NAMED, SosStatus.OPEN, False, False, False),
    ("raiser", RAISER, StaffRole.SEAMSTRESS, NAMED, SosStatus.OPEN, False, False, False),
    # …and escalated: the two elevated roles now rise, and NOBODY else does.
    ("named target", NAMED, StaffRole.SEAMSTRESS, NAMED, SosStatus.OPEN, True, False, True),
    ("shift manager", STRANGER, StaffRole.SHIFT_MANAGER, NAMED, SosStatus.OPEN, True, False, True),
    ("owner", STRANGER, StaffRole.OWNER, NAMED, SosStatus.OPEN, True, False, True),
    ("floor role", STRANGER, StaffRole.SEAMSTRESS, NAMED, SosStatus.OPEN, True, False, False),
    ("raiser", RAISER, StaffRole.OWNER, NAMED, SosStatus.OPEN, True, False, False),
    # ACCEPTED and fresh: somebody's job, so it rises for NOBODY.
    ("named target", NAMED, StaffRole.SEAMSTRESS, NAMED, SosStatus.ACCEPTED, False, False, False),
    (
        "shift manager",
        STRANGER,
        StaffRole.SHIFT_MANAGER,
        None,
        SosStatus.ACCEPTED,
        False,
        False,
        False,
    ),
    ("owner", STRANGER, StaffRole.OWNER, None, SosStatus.ACCEPTED, False, False, False),
    ("raiser", RAISER, StaffRole.OWNER, None, SosStatus.ACCEPTED, False, False, False),
    # ACCEPTED and STALLED: nobody has moved for two minutes, so it is nobody's
    # job again and the elevated fallback gets it back. THE row that makes the
    # accept path non-silent.
    (
        "shift manager",
        STRANGER,
        StaffRole.SHIFT_MANAGER,
        None,
        SosStatus.ACCEPTED,
        False,
        True,
        True,
    ),
    ("owner", STRANGER, StaffRole.OWNER, NAMED, SosStatus.ACCEPTED, False, True, True),
    ("named target", NAMED, StaffRole.SEAMSTRESS, NAMED, SosStatus.ACCEPTED, False, True, False),
    ("floor role", STRANGER, StaffRole.SEAMSTRESS, None, SosStatus.ACCEPTED, False, True, False),
    # ⚠ …and NOT the raiser, even then. A full-screen red interruption on her own
    # device, caused by her own tap, is the product shouting at the person who
    # asked for quiet.
    ("raiser", RAISER, StaffRole.OWNER, None, SosStatus.ACCEPTED, False, True, False),
    # Closed: there is nothing to do.
    ("owner", STRANGER, StaffRole.OWNER, None, SosStatus.RESOLVED, True, True, False),
    (
        "shift manager",
        STRANGER,
        StaffRole.SHIFT_MANAGER,
        None,
        SosStatus.CANCELLED,
        True,
        True,
        False,
    ),
    ("named target", NAMED, StaffRole.SEAMSTRESS, NAMED, SosStatus.RESOLVED, True, True, False),
]


@pytest.mark.parametrize(
    ("who", "actor_id", "role", "target", "status", "escalated", "stalled", "expected"),
    _FOR_ME,
    ids=[
        f"{who}-{status.value}-{'named' if target else 'role'}"
        f"-{'esc' if escalated else 'fresh'}-{'stalled' if stalled else 'moving'}"
        for who, _, _, target, status, escalated, stalled, _ in _FOR_ME
    ],
)
def test_the_for_me_matrix(
    who: str,
    actor_id: uuid.UUID,
    role: StaffRole,
    target: uuid.UUID | None,
    status: SosStatus,
    escalated: bool,
    stalled: bool,
    expected: bool,
) -> None:
    """⚠ **Whether the full-screen overlay RISES, which is a narrower question
    than who may SEE it.** A shift manager can see every alert in her tenant from
    the instant it is raised; if every one of them also rose on her device she
    would learn within a day to dismiss them unread.

    The actors are built with `role.value` because `StaffContext.role` is a
    `str`; see `_actor` for why that is consistency and NOT the vacuity guard the
    inherited comment claimed.
    """
    row = _matrix_alert(target=target, status=status)
    actual = _for_me(row, actor=_actor(role, actor_id), escalated=escalated, stalled=stalled)
    assert actual is expected, who


def test_an_accepted_alert_unresolved_for_two_minutes_re_rises_for_the_shift_manager() -> None:
    """⚠ **THE test `_stalled` exists for, and deleting `_stalled` or its branch
    in `_for_me` is the only thing that reds it.**

    Every other test in this file accepts and then resolves. Without the second
    boolean an accepted alert stops escalating and stops rising on every device
    in the boutique, FOREVER — and it is worse than silence, because the raiser's
    screen reads «דנה מגיעה» and she stops looking for help on a signal the
    product cannot back. There is no auto-resolve, no un-accept verb and no
    second threshold."""
    row = _accepted(3)
    row.raised_by = RAISER
    stalled = _stalled(row, server_now=NOW)
    assert stalled is True
    manager = _actor(StaffRole.SHIFT_MANAGER)
    assert _for_me(row, actor=manager, escalated=False, stalled=stalled) is True
    # …and one minute in it is still hers, so the fallback does not fire early.
    fresh = _accepted(1)
    fresh.raised_by = RAISER
    assert (
        _for_me(fresh, actor=manager, escalated=False, stalled=_stalled(fresh, server_now=NOW))
        is False
    )


# --- the poll: the audience clause and one shared anchor ----------------------


def _install_live(monkeypatch: pytest.MonkeyPatch, rows: list[SosAlertRow]) -> list[Any]:
    asked: list[Any] = []

    async def _live_for(
        _self: object, _session: object, tenant_id: uuid.UUID, *, actor_id: uuid.UUID | None
    ) -> list[SosAlertRow]:
        asked.append(actor_id)
        return rows

    monkeypatch.setattr(SosAlertsRepository, "live_for", _live_for)
    return asked


@pytest.mark.parametrize("role", ELEVATED)
async def test_an_elevated_caller_asks_for_every_alert_in_the_tenant(
    monkeypatch: pytest.MonkeyPatch, role: StaffRole
) -> None:
    """⚠ `actor_id=None` is how «no audience narrowing» is spelled, and the role
    test lives HERE rather than in the repository — which is what keeps
    `ELEVATED_ROLES` the one place the product decides who is elevated."""
    asked = _install_live(monkeypatch, [])
    await _service().sos(TENANT_ID, actor=_actor(role))
    assert asked == [None]


@pytest.mark.parametrize("role", FLOOR)
async def test_a_floor_role_asks_only_for_her_own_pages(
    monkeypatch: pytest.MonkeyPatch, role: StaffRole
) -> None:
    asked = _install_live(monkeypatch, [])
    actor = _actor(role)
    await _service().sos(TENANT_ID, actor=actor)
    assert asked == [actor.id]


async def test_the_payload_derives_the_three_booleans_against_one_server_now(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ **ONE instant decides both the badge and the elapsed line, or the
    overlay disagrees with itself.** The SQL alternative — `created_at <= now() -
    interval '30 seconds'` — is more correct about clocks and less correct about
    the screen: the console computes «כבר 0 דק'» against `server_now`, so a
    predicate against the database's `now()` could render that beside an
    escalated badge."""
    old = _alert(created_at=NOW - datetime.timedelta(seconds=31), target_staff_user_id=None)
    stalled = _alert(
        status=SosStatus.ACCEPTED,
        accepted_by=uuid.uuid4(),
        acknowledged_at=NOW - datetime.timedelta(minutes=3),
    )
    _install_live(
        monkeypatch, [_view(old, raised_by_name="נועה", room_label="חדר 2"), _view(stalled)]
    )
    read = await _service().sos(TENANT_ID, actor=_actor(StaffRole.SHIFT_MANAGER))

    assert read.server_now == NOW
    assert [(one.escalated, one.stalled, one.for_me) for one in read.alerts] == [
        (True, False, True),
        (False, True, True),
    ]
    assert read.alerts[0].alert is old
    assert read.alerts[0].row.raised_by_name == "נועה"
    assert read.alerts[0].row.room_label == "חדר 2"
