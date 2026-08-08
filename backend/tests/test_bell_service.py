"""F35's four producers, as one guard table.

**The whole feature's write side is four `if`s**, and this file is what proves
each one. A notification is written when SOMEBODY ELSE makes you responsible for
a person — so a self-dispatch, a self-handover and a role-routed page each write
NOTHING, and the third of those is the sharpest call in the spec.

⚠ **This module reuses `test_floor_service.py`'s rig rather than rebuilding it.**
`_install_tickets` already fakes every repository the three dispatch verbs touch
and `_install_raise` does the same for the page; a second transcription of that
scaffold would be ~200 lines whose only job is to drift from the first. The
producers live at four call sites inside those verbs, so testing them means
driving those verbs, which is what that rig is for.

**What this file does NOT prove and must not be read as proving: that the
notification commits with its event.** A monkeypatched `insert` never reaches a
transaction. `test_bell_producers_db.py` owns the rollback.
"""

import uuid
from typing import Any

import pytest
from test_floor_service import (
    ASSIGNMENT_ID,
    ROOM_ID,
    TENANT_ID,
    _assignment,
    _install_tickets,
    _Rig,
)
from test_floor_service import _actor as _floor_actor
from test_floor_service import _service as _floor_service
from test_sos_service import TENANT_ID as SOS_TENANT_ID
from test_sos_service import _actor as _sos_actor
from test_sos_service import _install_raise, _staff_user
from test_sos_service import _service as _sos_service

from app.db.repositories.staff_notifications import StaffNotificationsRepository
from app.models.constants import StaffNotificationKind, StaffRole


def _install_bell(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Records every insert. An EMPTY list is the assertion this file makes most
    often, and it is only meaningful because the fake is installed on the class:
    a producer that stopped calling the repository at all would look identical to
    one whose guard held, so every «wrote nothing» case is paired with a «wrote
    one» case on the same verb."""
    written: list[dict[str, Any]] = []

    async def _insert(
        _self: object,
        _session: object,
        _tenant_id: uuid.UUID,
        *,
        staff_user_id: uuid.UUID,
        actor_staff_user_id: uuid.UUID,
        kind: str,
        entity_id: uuid.UUID,
    ) -> None:
        written.append(
            {
                "staff_user_id": staff_user_id,
                "actor_staff_user_id": actor_staff_user_id,
                "kind": kind,
                "entity_id": entity_id,
            }
        )
        return None

    monkeypatch.setattr(StaffNotificationsRepository, "insert", _insert)
    return written


# --- take_next and assign: dispatch (F58) -------------------------------------


async def test_take_next_for_a_colleague_writes_one_dispatch_notification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The recipient is `target_staff_id` and the entity is the ASSIGNMENT, not
    the ticket. The audit row beside it keys on the ticket because the audit
    question is «which customer was dispatched»; the bell's is «which room are
    you now responsible for», and the ticket id is a customer datum this table
    must never hold."""
    rig = _install_tickets(monkeypatch, _Rig())
    written = _install_bell(monkeypatch)
    actor = _floor_actor(StaffRole.OWNER)
    target = uuid.uuid4()

    read = await _floor_service().take_next(TENANT_ID, ROOM_ID, staff_user_id=target, actor=actor)

    assert read.room.row.room_id == ROOM_ID
    assert len(written) == 1
    assert written[0]["staff_user_id"] == target
    assert written[0]["actor_staff_user_id"] == actor.id
    assert written[0]["kind"] == StaffNotificationKind.DISPATCH_ASSIGNED.value
    assert rig.calls, "the rig recorded the claim this notification rides on"


async def test_take_next_for_herself_writes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """`staff_user_id=None` means `target_staff_id = actor.id`, which is the
    ORDINARY case: a manager taking the next walk-in for herself. A row telling
    her what she just did is noise on the one surface whose whole value is that
    its count means something."""
    _install_tickets(monkeypatch, _Rig())
    written = _install_bell(monkeypatch)

    await _floor_service().take_next(
        TENANT_ID, ROOM_ID, staff_user_id=None, actor=_floor_actor(StaffRole.RECEPTION)
    )

    assert written == []


async def test_take_next_naming_herself_explicitly_also_writes_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The guard is `!= actor.id` and NOT `staff_user_id is not None`: a manager
    who picks her own name off the picker performed the same act as leaving it
    blank, and the two must not differ."""
    _install_tickets(monkeypatch, _Rig())
    written = _install_bell(monkeypatch)
    actor = _floor_actor(StaffRole.SHIFT_MANAGER)

    await _floor_service().take_next(TENANT_ID, ROOM_ID, staff_user_id=actor.id, actor=actor)

    assert written == []


async def test_assign_for_a_colleague_writes_one_dispatch_notification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Push-assign is take-next with a named ticket, and the recipient's sentence
    is identical — so it is the SAME `kind`. Splitting them would put the
    manager's choice of ticket on the recipient's screen, which is her business
    and not the recipient's."""
    _install_tickets(monkeypatch, _Rig())
    written = _install_bell(monkeypatch)
    actor = _floor_actor(StaffRole.OWNER)
    target = uuid.uuid4()

    await _floor_service().assign(
        TENANT_ID,
        ROOM_ID,
        queue_ticket_id=uuid.uuid4(),
        staff_user_id=target,
        actor=actor,
    )

    assert [row["kind"] for row in written] == [StaffNotificationKind.DISPATCH_ASSIGNED.value]
    assert written[0]["staff_user_id"] == target


async def test_assign_to_herself_writes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_tickets(monkeypatch, _Rig())
    written = _install_bell(monkeypatch)
    actor = _floor_actor(StaffRole.OWNER)

    await _floor_service().assign(
        TENANT_ID,
        ROOM_ID,
        queue_ticket_id=uuid.uuid4(),
        staff_user_id=actor.id,
        actor=actor,
    )

    assert written == []


# --- handover (F58) -----------------------------------------------------------


async def test_a_handover_to_a_colleague_writes_one_room_notification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`handover` is IN and it is not scope creep: it is `assign` with the
    customer already in the room. A bell that rang for one and not the other
    would be a bug nobody could state."""
    rig = _install_tickets(monkeypatch, _Rig())
    written = _install_bell(monkeypatch)
    actor = _floor_actor(StaffRole.OWNER)
    incoming = uuid.uuid4()
    rig.handover_result = (True, _assignment(uuid.uuid4()))

    await _floor_service().handover(TENANT_ID, ASSIGNMENT_ID, new_staff_id=incoming, actor=actor)

    assert len(written) == 1
    assert written[0]["staff_user_id"] == incoming
    assert written[0]["kind"] == StaffNotificationKind.ROOM_HANDED_OVER.value
    # The ASSIGNMENT is the entity, and it is the id the route was called with —
    # never the row the write answered, which is the same id one read later.
    assert written[0]["entity_id"] == ASSIGNMENT_ID


async def test_a_handover_to_herself_writes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rewriting the same value is a legitimate no-op at the repository (the
    docstring at `service.py`'s handover says so), and a no-op writes no row."""
    rig = _install_tickets(monkeypatch, _Rig())
    written = _install_bell(monkeypatch)
    actor = _floor_actor(StaffRole.OWNER)
    rig.handover_result = (True, _assignment(uuid.uuid4()))

    await _floor_service().handover(TENANT_ID, ASSIGNMENT_ID, new_staff_id=actor.id, actor=actor)

    assert written == []


# --- raise_sos (F37) ----------------------------------------------------------


async def test_a_named_reachable_sos_target_gets_one_notification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target_row = _staff_user()
    _install_raise(monkeypatch, target_row=target_row, target_live=True)
    written = _install_bell(monkeypatch)
    actor = _sos_actor(StaffRole.SEAMSTRESS)

    await _sos_service().raise_sos(
        SOS_TENANT_ID,
        target_staff_user_id=target_row.id,
        fitting_room_assignment_id=None,
        note=None,
        actor=actor,
    )

    assert len(written) == 1
    assert written[0]["staff_user_id"] == target_row.id
    assert written[0]["kind"] == StaffNotificationKind.SOS_TARGETED.value


async def test_a_ROLE_ROUTED_sos_writes_no_notification(monkeypatch: pytest.MonkeyPatch) -> None:
    """⚠ **The sharpest call in the feature, and the under-reporting is
    deliberate.**

    `target_staff_user_id=None` IS the shift-manager ROLE — an audience, not a
    row. Writing one notification per audience member would re-introduce the
    exact fan-out F37 declined when it did not build `sos_alert_targets`, inside
    the most latency-sensitive transaction in the product, to duplicate what
    `FloorService.sos` already computes at read time for every elevated caller
    from t=0. The durable record of a role page is the `SOS_RAISED` audit row.

    This is survivable only because the bell is NOT the emergency channel — the
    overlay is. If anything ever makes it one, this test is the defect.
    """
    _install_raise(monkeypatch)
    written = _install_bell(monkeypatch)

    await _sos_service().raise_sos(
        SOS_TENANT_ID,
        target_staff_user_id=None,
        fitting_room_assignment_id=None,
        note=None,
        actor=_sos_actor(StaffRole.SALES_ASSISTANT),
    )

    assert written == []


async def test_an_sos_rerouted_to_the_role_writes_no_notification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """She named Dana; Dana is logged out; the raise stores NULL and reroutes.
    The guard reads the RESOLVED `target_id`, so it correctly writes nothing —
    a notification for a colleague who is not signed in would be the one row on
    this table guaranteed never to be seen."""
    target_row = _staff_user()
    _install_raise(monkeypatch, target_row=target_row, target_live=False)
    written = _install_bell(monkeypatch)

    result = await _sos_service().raise_sos(
        SOS_TENANT_ID,
        target_staff_user_id=target_row.id,
        fitting_room_assignment_id=None,
        note=None,
        actor=_sos_actor(StaffRole.RECEPTION),
    )

    assert result.rerouted is True
    assert written == []
