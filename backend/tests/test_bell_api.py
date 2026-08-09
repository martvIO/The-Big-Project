"""F35's two routes and the wire they answer — fast, no Postgres.

`test_floor_api.py` owns the twenty-five-row table, the role gate, the CSRF fence
and the `no-store` header for all twenty-five routes at once. This module owns
what is specific to the bell: **the row's key set, pinned by SET EQUALITY**, and
the two places the SESSION's actor is the only scope there is.

⚠ **The key-set assertion is the one that catches a customer field arriving
unreviewed**, and here it also catches `entity_id`. That column is STORED — it is
what makes the row a record rather than a log line — and it is deliberately not
emitted, because nothing renders it and an id nothing reads is a capability
handed out for free.

The service is `test_floor_api.py`'s duck-typed `FakeFloorService`, which fills
both `app.state` slots. This module proves the ROUTER hands it the host-resolved
tenant and the session's actor and renders exactly what it answers; whether the
RULES are right is `test_bell_repository_db.py`'s and `test_bell_isolation.py`'s.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from test_floor_api import BELL_PATH, BELL_READ_PATH, FakeFloorService, _client

from app.db.repositories.staff_notifications import StaffNotificationRow
from app.models.constants import StaffNotificationKind, StaffRole
from app.models.staff_notification import StaffNotification

ALL_ROLES = [role.value for role in StaffRole]

CREATED_AT = datetime(2026, 8, 6, 11, 32, tzinfo=UTC)
READ_AT = datetime(2026, 8, 6, 11, 40, tzinfo=UTC)

# ⚠ FIVE keys and it stays a SET EQUALITY. `entity_id` is the sixth a reader
# would add without thinking, and its absence is the decision this pins.
ROW_KEYS = {"id", "kind", "actor_name", "created_at", "read_at"}


def _iso(value: Any) -> str:
    return str(value.isoformat()).replace("+00:00", "Z")


def _row(
    *,
    kind: str = StaffNotificationKind.DISPATCH_ASSIGNED.value,
    actor_name: str | None = "דנה כהן",
    read_at: datetime | None = None,
) -> StaffNotificationRow:
    notification = StaffNotification(
        tenant_id=uuid.uuid4(),
        staff_user_id=uuid.uuid4(),
        actor_staff_user_id=uuid.uuid4(),
        kind=kind,
        entity_id=uuid.uuid4(),
    )
    notification.id = uuid.uuid4()
    notification.created_at = CREATED_AT
    notification.read_at = read_at
    return StaffNotificationRow(notification=notification, actor_name=actor_name)


# --- the list -----------------------------------------------------------------


def test_the_list_is_an_envelope_of_items() -> None:
    """An envelope rather than a bare array, `FloorResponse`'s reason: the day
    this read grows a cursor or a total it stays additive."""
    fake = FakeFloorService()
    row = _row()
    fake.notification_rows = [row]
    with _client(fake) as client:
        body = client.get(BELL_PATH).json()

    assert set(body) == {"items"}
    assert body["items"] == [
        {
            "id": str(row.notification.id),
            "kind": StaffNotificationKind.DISPATCH_ASSIGNED.value,
            "actor_name": "דנה כהן",
            "created_at": _iso(CREATED_AT),
            "read_at": None,
        }
    ]


def test_a_row_carries_five_keys_and_never_the_entity_id() -> None:
    """⚠ **THE assertion, and it is a set equality over the row.** Every other
    test here asserts on fields that would still be present when a sixth arrives.

    `entity_id`, a customer's name, a phone, a ticket id — none of them may reach
    this shape, and the first of those is the one already sitting on the row in
    the database.
    """
    fake = FakeFloorService()
    fake.notification_rows = [_row(read_at=READ_AT)]
    with _client(fake) as client:
        body = client.get(BELL_PATH).json()

    assert set(body["items"][0]) == ROW_KEYS
    assert body["items"][0]["read_at"] == _iso(READ_AT)


def test_a_nameless_actor_is_null_rather_than_a_missing_key() -> None:
    """NULL when the actor's staff row is gone entirely. The copy has a nameless
    variant for exactly this, so the key must be present and null rather than
    absent."""
    fake = FakeFloorService()
    fake.notification_rows = [_row(actor_name=None, kind=StaffNotificationKind.SOS_TARGETED.value)]
    with _client(fake) as client:
        body = client.get(BELL_PATH).json()

    assert body["items"][0]["actor_name"] is None
    assert set(body["items"][0]) == ROW_KEYS


def test_an_empty_bell_is_an_empty_list_and_not_a_404() -> None:
    """Every staffer's bell on the day she starts. An empty list is the ordinary
    case and the panel has designed copy for it."""
    fake = FakeFloorService()
    with _client(fake) as client:
        resp = client.get(BELL_PATH)

    assert resp.status_code == 200
    assert resp.json() == {"items": []}


# --- the actor is the only scope ---------------------------------------------


def test_the_list_is_scoped_to_the_session_actor_and_nothing_the_request_names() -> None:
    """⚠ The route takes NO `staff_id` and must never take one. The service is
    handed the id off the session cookie, and a query parameter naming a
    colleague is simply ignored by the router rather than honoured."""
    fake = FakeFloorService()
    mine = uuid.uuid4()
    hers = uuid.uuid4()
    with _client(fake, staff_id=mine) as client:
        client.get(BELL_PATH, params={"staff_id": str(hers)})

    call = next(one for one in fake.calls if one["method"] == "notifications")
    assert call["actor_id"] == mine


def test_mark_read_is_scoped_to_the_session_actor_and_answers_her_own_count() -> None:
    """The ids come from the body; the PERSON never does. A colleague's id in the
    list matches nothing, and the count answered is still the caller's — which is
    the number her bell is about to render."""
    fake = FakeFloorService()
    fake.unread = 3
    mine = uuid.uuid4()
    ids = [uuid.uuid4(), uuid.uuid4()]
    with _client(fake, staff_id=mine) as client:
        body = client.post(BELL_READ_PATH, json={"ids": [str(one) for one in ids]}).json()

    assert body == {"unread": 3}
    call = next(one for one in fake.calls if one["method"] == "mark_read")
    assert call["actor_id"] == mine
    assert call["ids"] == ids


def test_mark_read_with_an_empty_list_is_a_200_that_still_answers_a_count() -> None:
    """«She tapped a row that was already read» and «nothing on the page was
    unread» both land here. Neither is a client error."""
    fake = FakeFloorService()
    fake.unread = 7
    with _client(fake) as client:
        resp = client.post(BELL_READ_PATH, json={"ids": []})

    assert resp.status_code == 200
    assert resp.json() == {"unread": 7}


def test_a_twenty_first_id_is_refused_at_the_route() -> None:
    """The cap is enforced server-side, not merely respected by the console: the
    page is at most 20 rows, so a longer body is a bug or a replay."""
    fake = FakeFloorService()
    with _client(fake) as client:
        resp = client.post(BELL_READ_PATH, json={"ids": [str(uuid.uuid4()) for _ in range(21)]})

    # 400 with the house VALIDATION_ERROR envelope, not FastAPI's raw 422 — the
    # app-level handler owns that shape for every request body in the product.
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert not [one for one in fake.calls if one["method"] == "mark_read"]


# --- the audience -------------------------------------------------------------


@pytest.mark.parametrize("role", ALL_ROLES)
def test_all_five_roles_reach_both_bell_routes(role: str) -> None:
    """The bell's audience IS the router's five, which is why neither route
    carries a per-route gate: any narrower one would be wrong, and every one of
    the five can be a dispatch, handover or SOS recipient."""
    fake = FakeFloorService()
    with _client(fake, role=role) as client:
        assert client.get(BELL_PATH).status_code == 200
        assert client.post(BELL_READ_PATH, json={"ids": []}).status_code == 200


def test_both_routes_require_a_session() -> None:
    fake = FakeFloorService()
    with _client(fake, authed=False) as client:
        for method, path, body in (
            ("GET", BELL_PATH, None),
            ("POST", BELL_READ_PATH, {"ids": []}),
        ):
            resp = client.request(method, path, json=body)
            assert resp.status_code == 401, f"{method} {path} → {resp.status_code}"
            assert resp.json()["error"]["code"] == "NOT_AUTHENTICATED"
    assert fake.calls == []
