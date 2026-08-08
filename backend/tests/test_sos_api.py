"""F37's five routes and the wire they answer — fast, no Postgres.

`test_floor_api.py` owns the eighteen-row table, the role gate, the CSRF fence
and the `no-store` header for all eighteen routes at once. This module owns what
is specific to the SOS surface: **the alert's key set, pinned by SET EQUALITY**,
the raise's three failure modes walked as a table, and the two 409 bodies.

⚠ **The key-set assertion is the one that catches a customer field arriving
unreviewed on a payload that polls eleven sections.** F36 put a bride's name on
`/manage/floor` — a payload fetched only while the console is on the board or the
floor, by a component that unmounts on navigation. This one is fetched on EVERY
section, every few seconds, for the whole shift, so a `client_label` here would
mean the console holds a customer's name in memory and on the wire while nobody
is looking at a floor at all.

The service is the duck-typed `FakeFloorService`: this module proves the ROUTER
hands it the host-resolved tenant, the path's alert id and the session's actor,
and renders exactly what it answers. Whether the RULES are right is
`test_sos_service.py`'s and `test_sos_db.py`'s.
"""

import uuid
from typing import Any

import pytest
from test_floor_api import (
    ALERT_ID,
    RAISED_AT,
    SERVER_NOW,
    SOS_ACCEPT_PATH,
    SOS_CANCEL_PATH,
    SOS_PATH,
    SOS_RESOLVE_PATH,
    STAFF_ID,
    TARGET_ID,
    FakeFloorService,
    _client,
    sos_read,
)

from app.errors import DomainNotFoundError, DomainValidationError
from app.floor.validation import (
    MAX_SOS_NOTE_LENGTH,
    SosAlreadyAcceptedError,
    SosClosedError,
    SosValidationError,
)
from app.models.constants import SosStatus, StaffRole

ASSIGNMENT_ID = uuid.uuid4()

# ⚠ FIFTEEN keys and it stays a SET EQUALITY. A sixteenth arriving unreviewed is
# what this assertion exists to catch, and on this particular payload that is the
# whole of the no-customer-datum argument mechanised.
ALERT_KEYS = {
    "id",
    "status",
    "raised_by",
    "raised_by_name",
    "target_staff_user_id",
    "target_name",
    "room_label",
    "note",
    "accepted_by",
    "accepted_by_name",
    "acknowledged_at",
    "created_at",
    "escalated",
    "stalled",
    "for_me",
}

MUTATIONS = [SOS_ACCEPT_PATH, SOS_RESOLVE_PATH, SOS_CANCEL_PATH]


def _iso(value: Any) -> str:
    return str(value.isoformat()).replace("+00:00", "Z")


# --- the payload --------------------------------------------------------------


def test_the_sos_payload_is_an_envelope_of_alerts_and_one_server_now() -> None:
    """`server_now` is the SAME field F36 put on `/manage/floor`, for the same
    reason and with one more: it is the instant BOTH derived booleans and the
    console's elapsed line are computed against, so an escalated badge can never
    render beside «כבר 0 דק'»."""
    fake = FakeFloorService()
    fake.sos_alerts = [sos_read()]
    with _client(fake) as client:
        body = client.get(SOS_PATH).json()

    # THREE keys since F35: the bell's count rides this payload because it is the
    # console's only app-wide tick. It is a plain integer and carries nothing
    # about WHICH notifications — the panel's own GET answers that.
    assert set(body) == {"alerts", "server_now", "unread_notifications"}
    assert body["server_now"] == _iso(SERVER_NOW)
    assert body["unread_notifications"] == 0
    assert body["alerts"] == [
        {
            "id": str(ALERT_ID),
            "status": "open",
            "raised_by": str(STAFF_ID),
            "raised_by_name": "דנה כהן",
            "target_staff_user_id": str(TARGET_ID),
            "target_name": "נועה לוי",
            "room_label": "חדר 1",
            "note": "צריך סיכות",
            "accepted_by": None,
            "accepted_by_name": None,
            "acknowledged_at": None,
            "created_at": _iso(RAISED_AT),
            "escalated": False,
            "stalled": False,
            "for_me": True,
        }
    ]


def test_the_sos_payload_carries_no_customer_datum() -> None:
    """⚠ **THE assertion, and it is a NEGATIVE over the whole response body** —
    which is exactly why it is the only thing that can fail when a field is
    added. Every other test in this feature asserts on fields that would still be
    present.

    The alert names a room and two colleagues. It does not name the bride behind
    the curtain, and it never will: the responder needs to know who is calling
    and which curtain, and an SOS already names the person in the room."""
    fake = FakeFloorService()
    fake.sos_alerts = [sos_read(), sos_read(status=SosStatus.ACCEPTED, accepted_by=TARGET_ID)]
    with _client(fake) as client:
        body = client.get(SOS_PATH).json()

    for alert in body["alerts"]:
        assert set(alert) == ALERT_KEYS, sorted(alert)
    assert "client" not in str(body)
    assert "customer" not in str(body)
    assert "booking" not in str(body)


def test_an_escalated_and_a_stalled_alert_render_their_derived_booleans() -> None:
    """Both are DERIVED at read time and neither is a column: there is no instant
    at which either happens and no writer to hang one on. The console renders
    what the server computed, so the audience rule exists once."""
    fake = FakeFloorService()
    fake.sos_alerts = [
        sos_read(escalated=True),
        sos_read(
            status=SosStatus.ACCEPTED,
            accepted_by=TARGET_ID,
            acknowledged_at=RAISED_AT,
            stalled=True,
        ),
    ]
    with _client(fake) as client:
        alerts = client.get(SOS_PATH).json()["alerts"]

    assert [(one["escalated"], one["stalled"]) for one in alerts] == [(True, False), (False, True)]
    assert alerts[1]["accepted_by"] == str(TARGET_ID)
    assert alerts[1]["accepted_by_name"] == "נועה לוי"
    assert alerts[1]["acknowledged_at"] == _iso(RAISED_AT)


def test_an_empty_boutique_answers_an_empty_list_and_not_a_204() -> None:
    """The console's poll must be able to tell «no alerts» from «no answer» — a
    channel that goes quiet on the good path cannot be distinguished from one
    that has died."""
    fake = FakeFloorService()
    with _client(fake) as client:
        resp = client.get(SOS_PATH)
    assert resp.status_code == 200
    assert resp.json()["alerts"] == []


def test_the_read_passes_the_session_actor_and_the_host_tenant() -> None:
    """The audience clause is computed from the SESSION's actor, never from
    anything the request names: an id in a query string would let any staffer
    poll as anybody."""
    fake = FakeFloorService()
    with _client(fake, role=StaffRole.SEAMSTRESS.value) as client:
        assert client.get(SOS_PATH).status_code == 200
    assert fake.calls[0]["method"] == "sos"
    assert fake.calls[0]["actor_id"] == STAFF_ID


# --- the raise ----------------------------------------------------------------


def test_an_empty_raise_body_pages_the_shift_manager_role_from_no_room() -> None:
    """All three fields optional, and all three defaults are the ORDINARY case:
    she taps once, from wherever she is, and the shift manager is who answers."""
    fake = FakeFloorService()
    with _client(fake) as client:
        resp = client.post(SOS_PATH, json={})
    assert resp.status_code == 200
    assert fake.calls[0] == {
        "method": "raise_sos",
        "tenant_id": fake.calls[0]["tenant_id"],
        "target_staff_user_id": None,
        "fitting_room_assignment_id": None,
        "note": None,
        "actor_id": STAFF_ID,
    }


def test_the_raise_answers_the_alert_and_whether_it_was_rerouted() -> None:
    """⚠ **`rerouted` is a fact about THIS REQUEST, not about the row**, which is
    why it cannot be inferred later: nobody reading the alert afterwards can know
    whether a null target means «she asked for the shift manager» or «she asked
    for Dana and Dana was logged out». It is what lets the raiser be TOLD, on
    screen, in the moment it matters."""
    fake = FakeFloorService()
    fake.rerouted = True
    with _client(fake) as client:
        body = client.post(SOS_PATH, json={"target_staff_user_id": str(TARGET_ID)}).json()
    assert set(body) == {"alert", "rerouted"}
    assert body["rerouted"] is True
    assert set(body["alert"]) == ALERT_KEYS


def test_the_raise_body_forbids_unknown_keys_including_raised_by() -> None:
    """⚠ **`ForbidExtraModel` is load-bearing on this one body above every other
    in the product.** `raised_by` is exactly the shape `_authorize`'s docstring
    names as THE hazard — a body-supplied staff id doubling as the caller's
    identity — and here it would let anyone page AS anyone."""
    fake = FakeFloorService()
    with _client(fake) as client:
        for body in ({"raised_by": str(TARGET_ID)}, {"bogus": 1}):
            resp = client.post(SOS_PATH, json=body)
            assert resp.status_code == 400, body
            assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert fake.calls == []


@pytest.mark.parametrize("role", [role.value for role in StaffRole])
def test_every_role_may_raise_a_page(role: str) -> None:
    """Five roles, and the SOS is the one verb on this router that could never be
    narrowed: the person alone with a half-dressed bride is whoever she is."""
    fake = FakeFloorService()
    with _client(fake, role=role) as client:
        assert client.post(SOS_PATH, json={}).status_code == 200


def test_nothing_about_the_boutique_can_refuse_a_page() -> None:
    """⚠ **THE table, over HTTP, and it IS «a page is never silently dropped».**

    Not a missing room, not an assignment that no longer resolves, not a
    colleague who went home, not one who does not exist, not a second page by the
    same raiser. Every row answers **200 with an alert** — pinned as
    `== 200` and not «200 or 201», because no route on this router declares
    `status_code=` and an ambiguous expected status on a table walk is a
    first-run CI red on the one assertion that encodes the rule.

    The three failure modes are exhaustively 401 (no session), 403 (a role
    outside the five, unreachable for a signed-in staffer since the router admits
    all five) and 400 (note too long, or self-target). The service decides which
    of these bodies REROUTES; this walk's claim is only that none of them is
    refused."""
    rows: list[tuple[str, dict[str, Any]]] = [
        ("no room and the shift-manager role", {}),
        ("a note and nothing else", {"note": "צריך סיכות"}),
        (
            "an assignment that no longer resolves",
            {"fitting_room_assignment_id": str(uuid.uuid4())},
        ),
        ("an unknown target staff id", {"target_staff_user_id": str(uuid.uuid4())}),
        (
            "a named target and a room together",
            {
                "target_staff_user_id": str(TARGET_ID),
                "fitting_room_assignment_id": str(ASSIGNMENT_ID),
                "note": "א" * MAX_SOS_NOTE_LENGTH,
            },
        ),
    ]
    for name, body in rows:
        fake = FakeFloorService()
        with _client(fake, role=StaffRole.SEAMSTRESS.value) as client:
            resp = client.post(SOS_PATH, json=body)
        assert resp.status_code == 200, f"{name} → {resp.status_code} {resp.text}"
        assert set(resp.json()["alert"]) == ALERT_KEYS, name

    # …and a second page by the same raiser is admitted, because there is no
    # unique index to violate: «I need a seamstress AND I need the manager» is
    # two alerts and not a 409.
    fake = FakeFloorService()
    with _client(fake, role=StaffRole.SEAMSTRESS.value) as client:
        assert client.post(SOS_PATH, json={}).status_code == 200
        assert client.post(SOS_PATH, json={}).status_code == 200


@pytest.mark.parametrize(
    "error", [SosValidationError("note is too long"), DomainValidationError("cannot page yourself")]
)
def test_a_refused_raise_is_a_400_carrying_the_domain_message(error: Exception) -> None:
    """Both of the raise's own refusals ride the SHIPPED `DomainValidationError`
    handler — no new code, no new handler, and `SosValidationError` is a subclass
    precisely so that stays true."""
    with _client(FakeFloorService(raises=error)) as client:
        resp = client.post(SOS_PATH, json={})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


# --- the three mutations ------------------------------------------------------


@pytest.mark.parametrize("path", MUTATIONS)
def test_every_mutation_answers_the_same_alert_shape(path: str) -> None:
    """ONE shape for four routes plus the poll, so the console patches one card
    in place from the server's own row and cannot disagree with itself. A route
    that grew its own answer shows up here as a key-set difference."""
    fake = FakeFloorService()
    fake.sos_read = sos_read(status=SosStatus.ACCEPTED, accepted_by=TARGET_ID)
    with _client(fake) as client:
        body = client.post(path).json()
    assert set(body) == ALERT_KEYS
    assert body["status"] == "accepted"
    assert body["accepted_by_name"] == "נועה לוי"


@pytest.mark.parametrize("path", MUTATIONS)
def test_every_mutation_takes_the_alert_from_the_path_and_the_actor_from_the_session(
    path: str,
) -> None:
    """⚠ The two axes come from DIFFERENT places. If a handler ever passed the
    path id as the actor, every permission check in the feature would compare a
    value with itself and always pass."""
    fake = FakeFloorService()
    with _client(fake, role=StaffRole.SEAMSTRESS.value) as client:
        assert client.post(path).status_code == 200
    assert fake.calls[0]["alert_id"] == ALERT_ID
    assert fake.calls[0]["actor_id"] == STAFF_ID
    assert ALERT_ID != STAFF_ID


@pytest.mark.parametrize("path", MUTATIONS)
def test_no_mutation_takes_a_body(path: str) -> None:
    """The target is the alert id and there is nothing to say about it —
    `release_assignment`'s shipped reasoning. A body that arrived would be
    ignored rather than validated, so none is accepted."""
    fake = FakeFloorService()
    with _client(fake) as client:
        assert client.post(path, json={"note": "בבקשה"}).status_code == 200
    assert set(fake.calls[0]) == {"method", "tenant_id", "alert_id", "actor_id"}


@pytest.mark.parametrize("path", MUTATIONS)
def test_a_refused_mutation_is_a_404_indistinguishable_from_a_missing_alert(path: str) -> None:
    """⚠ **404 and not 403.** Whose alert it is can only be learned by READING
    it, so a 403 on a real id and a 404 on a fake one would discriminate
    existence and let any staffer enumerate the tenant's alerts."""
    with _client(FakeFloorService(missing=True)) as client:
        resp = client.post(path)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_a_losing_accept_is_a_409_that_names_the_owner() -> None:
    """The ruling requires the 409 to NAME the responder who got there first, and
    `message` is English prose the console never renders for a mapped code — so
    the datum has to travel in `details` or it is unreachable by the UI."""
    fake = FakeFloorService(raises=SosAlreadyAcceptedError({"staff_display_name": "דנה"}))
    with _client(fake) as client:
        resp = client.post(SOS_ACCEPT_PATH)
    assert resp.status_code == 409
    assert resp.json() == {
        "error": {
            "code": "SOS_ALREADY_ACCEPTED",
            "message": "This SOS has already been accepted.",
            "details": {"staff_display_name": "דנה"},
        }
    }


def test_a_cancel_after_an_accept_is_the_same_409_naming_the_acceptor() -> None:
    """The 409 REUSES the accept's code, its optional `details` and its Hebrew,
    so the resolve/cancel asymmetry costs no new error and no new sentence."""
    fake = FakeFloorService(raises=SosAlreadyAcceptedError({"staff_display_name": "דנה"}))
    with _client(fake) as client:
        resp = client.post(SOS_CANCEL_PATH)
    assert resp.status_code == 409
    assert resp.json()["error"]["details"] == {"staff_display_name": "דנה"}


def test_a_conflict_with_nobody_to_name_omits_details_entirely() -> None:
    """⚠ The key is ABSENT, never `{"staff_display_name": null}`. `accepted_by`
    points at a `staff_users` row staff removal can soft-delete at any time, and
    a null would break the console's `Record<string, string>` and render
    «{{name}} כבר מגיעה.» with an empty interpolation on a legally binding
    surface."""
    with _client(FakeFloorService(raises=SosAlreadyAcceptedError())) as client:
        resp = client.post(SOS_ACCEPT_PATH)
    assert resp.status_code == 409
    assert "details" not in resp.json()["error"]


def test_accepting_a_closed_alert_is_its_own_409_and_never_carries_details() -> None:
    """Two codes and not one with a discriminating `details`: two causes, two
    Hebrew sentences, two remedies — go somewhere else, versus there is nothing
    to do. And there is nobody to name for a resolved alert."""
    with _client(FakeFloorService(raises=SosClosedError())) as client:
        resp = client.post(SOS_ACCEPT_PATH)
    assert resp.status_code == 409
    assert resp.json() == {
        "error": {"code": "SOS_CLOSED", "message": "This SOS is already closed."}
    }


def test_a_missing_alert_on_the_read_is_impossible_and_the_poll_never_404s() -> None:
    """The poll answers a list, so «nothing to show» is an empty list and never a
    404 — a terminal status on the app-level loop would take the whole channel
    down for a boutique with no emergencies."""
    fake = FakeFloorService(missing=True)
    with _client(fake) as client:
        resp = client.get(SOS_PATH)
    assert resp.status_code == 200
    assert resp.json()["alerts"] == []


def test_the_read_is_not_fenced_by_csrf_but_the_four_verbs_are() -> None:
    """`CsrfOriginMiddleware` gates on the METHOD, not on a path list, so the
    four new mutating verbs are fenced by construction. The GET's protection is
    the session cookie and the role gate, alone — which is asserted rather than
    assumed because "by construction" is the sentence that stops being true the
    day somebody adds a GET that writes."""
    foreign = {"origin": "http://evil.localtest.me"}
    fake = FakeFloorService()
    with _client(fake) as client:
        assert client.get(SOS_PATH, headers=foreign).status_code == 200
        for path in [SOS_PATH, *MUTATIONS]:
            resp = client.post(path, json={} if path == SOS_PATH else None, headers=foreign)
            assert resp.status_code == 403, path
            assert resp.json()["error"]["code"] == "CSRF_ORIGIN_MISMATCH"


def test_a_domain_not_found_from_the_read_would_still_be_a_404() -> None:
    """The shipped handler, unchanged: F37 adds no NOT_FOUND producer of its own
    on the read path and this pins that the mapping is the same one."""
    with _client(FakeFloorService(raises=DomainNotFoundError("sos_alert"))) as client:
        assert client.get(SOS_PATH).status_code == 404
