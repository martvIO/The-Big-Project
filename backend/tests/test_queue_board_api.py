"""Fast API tests for the public wall board: a stub QueueService and a hardcoded
TenantContext, no database (the F11 posture template, via test_checkin_api.py).

The service suite proves the metering, the derivation and the field set; this one
proves the HTTP contract — anonymous, tenant-from-Host, cookie-blind, no-store,
POST-only — and the exact error table, which is two rows.

**This is the most exposed surface in the product and the posture is the whole
defence.** The body is a list of women's first names and their places in a queue,
answered to anyone who can reach the host, with no credential of any kind. There
is nothing here to authenticate, so every control is structural: the tenant comes
from the Host and from nowhere a caller can name, the response is `no-store` so it
never lands in a shared cache or a bfcache entry, and one spent per-tenant budget
is the only brake.

**POST, and NOT for F33's reason.** F33's two routes are POSTs because the ticket
id is a capability and a path or query segment leaks into every access log, proxy
trace and Referer on the way. F59's request carries nothing at all — no id, no
body, no secret — so that argument does not transfer. The reason here is
mechanical and lives in a different file: `ROUTES` in test_storefront_api.py is
DERIVED over every GET under /storefront and five guards parametrize over it, one
of which asserts 429 against a limiter configured to block everything. A GET on
this sibling router does not carry the read router's throttle, answers 200, and
reddens it. The two escapes are worse than a POST: share the catalog's 6000/60s
budget (the failure main.py names verbatim) or weaken a guard protecting six
shipped public reads.
"""

import uuid

import httpx
import pytest
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.auth.dependencies import get_auth_service
from app.auth.service import StaffContext
from app.main import TOO_MANY_ATTEMPTS_BODY, create_app
from app.queue.schemas import QueueBoardEntry, QueueBoardView
from app.queue.validation import CheckinThrottledError
from app.tenancy.middleware import TenantContext

TENANT = TenantContext(id=uuid.uuid4(), slug="bella", name="בלה כלות", settings={})
STAFF_ID = uuid.uuid4()
TOKEN = "session-token-abc"

BOARD_PATH = "/storefront/queue"

# The whole of QueueBoardView, spelled out rather than derived from the model —
# the same reason TICKET_KEYS is spelled out in test_checkin_api.py. A refactor
# that adds an envelope, a server timestamp or a ticket id must fail this
# literal, and a set derived from the model would move with it.
BOARD_KEYS = {"entries", "waiting_total"}
ENTRY_KEYS = {"position", "first_name", "called"}

# Two codes, and there is no third. No VALIDATION_ERROR because there is no
# request body to reject, and no NOT_FOUND because an empty queue is a 200 with
# an empty list — a screen that errored when nobody was waiting would render its
# error arm for most of the shop day.
SPEC_ERROR_CODES = {"TENANT_NOT_FOUND", "TOO_MANY_ATTEMPTS"}


class StubQueueService:
    """The router is a thin delegate, so the stub is a programmable outcome and a
    call log — nothing else. The body is deterministic, which is what lets the
    cookie-blindness comparison assert the FULL json() with no field excluded."""

    def __init__(self) -> None:
        self.board_error: Exception | None = None
        self.board_calls: list[uuid.UUID] = []

    async def board(self, tenant_id: uuid.UUID) -> QueueBoardView:
        if self.board_error is not None:
            raise self.board_error
        self.board_calls.append(tenant_id)
        return QueueBoardView(
            entries=[
                QueueBoardEntry(position=1, first_name="נועה", called=True),
                QueueBoardEntry(position=2, first_name="שירה", called=False),
            ],
            waiting_total=7,
        )


class FakeAuthService:
    """Only here so the owner cookie in the cookie-blindness test is a genuinely
    resolvable session rather than a random string."""

    def __init__(self) -> None:
        self.staff = StaffContext(
            id=STAFF_ID,
            tenant_id=TENANT.id,
            email="owner@bella.example",
            display_name="Owner",
            role="owner",
        )

    async def login(
        self, tenant_id: uuid.UUID, email: str, password: str
    ) -> tuple[StaffContext, str]:
        return self.staff, TOKEN

    async def resolve_session(self, tenant_id: uuid.UUID, token: str) -> StaffContext | None:
        return self.staff if token == TOKEN else None

    async def logout(self, tenant_id: uuid.UUID, token: str) -> None:
        return None


def _client(
    stub: StubQueueService | None = None, *, host: str = "bella.localtest.me"
) -> tuple[TestClient, StubQueueService]:
    async def _resolver(slug: str) -> TenantContext | None:
        return TENANT if slug == "bella" else None

    app = create_app(resolver=_resolver)
    service = stub if stub is not None else StubQueueService()
    app.state.queue_service = service
    auth = FakeAuthService()
    app.state.auth_service = auth
    app.dependency_overrides[get_auth_service] = lambda: auth
    return TestClient(app, base_url=f"http://{host}"), service


def _post(client: TestClient) -> httpx.Response:
    """No body, no query string, no header. The whole request is a method and a
    path — which is why there is no VALIDATION_ERROR row in the error table."""
    return client.post(BOARD_PATH)


# --- the public contract: anonymous, tenant-required, cookie-blind, POST-only ---


def test_the_board_is_anonymous_and_cookie_blind() -> None:
    """A1. Two separate clients compared on the FULL body, no field excluded.

    The wall screen has no session and never will, so the anonymous answer is the
    product; the owner-cookie half is what stops a future reviewer assuming the
    board is somehow richer for staff. test_owner_cookie_changes_nothing in
    test_storefront_api.py loops a GET-only ROUTES list and cannot cover a POST.
    """
    anon_client, stub = _client()
    with anon_client:
        assert anon_client.cookies == {}
        anonymous = _post(anon_client)

    assert anonymous.status_code == 200
    assert anonymous.json() == {
        "entries": [
            {"position": 1, "first_name": "נועה", "called": True},
            {"position": 2, "first_name": "שירה", "called": False},
        ],
        "waiting_total": 7,
    }
    assert set(anonymous.json()) == BOARD_KEYS
    assert {key for entry in anonymous.json()["entries"] for key in entry} == ENTRY_KEYS
    assert "set-cookie" not in anonymous.headers
    assert stub.board_calls == [TENANT.id]

    cookie_client, _ = _client()
    with cookie_client:
        cookie_client.cookies.set("boutique_session", TOKEN, domain="bella.localtest.me")
        with_cookie = _post(cookie_client)

    assert with_cookie.status_code == anonymous.status_code == 200
    assert with_cookie.json() == anonymous.json()
    assert "set-cookie" not in with_cookie.headers


def test_an_unknown_host_is_the_generic_404() -> None:
    """A2. Public is not host-agnostic. Never add a /storefront path to
    EXEMPT_PATHS — the capitalised warning in tenancy/middleware.py. A board that
    answered without a resolved tenant would be a board of somebody's names
    served under any host that reached the process."""
    client, stub = _client(host="nosuch.localtest.me")
    with client:
        resp = _post(client)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "TENANT_NOT_FOUND"
    assert stub.board_calls == []


def test_the_board_is_no_store() -> None:
    """A3. Inherited from the router's Depends(_no_store) with zero new code —
    which is the point of registering the third route on F33's router rather than
    on one of its own. The body names live people's places in a queue and the
    screen polls it every five seconds for months."""
    client, _ = _client()
    with client:
        resp = _post(client)
    assert resp.headers["cache-control"] == "no-store"


def test_get_stays_a_405() -> None:
    """A4. The read router is contractually GET-only and this sibling is
    POST-only. Converting this to a GET is the one change that reddens
    test_the_read_throttle_is_not_inert in test_storefront_api.py with a 200 —
    see this module's docstring."""
    client, _ = _client()
    with client:
        resp = client.get(BOARD_PATH)
    assert resp.status_code == 405


def test_the_tenant_reaches_the_service_from_the_host_and_never_from_a_request_field() -> None:
    """The request carries no tenant field because it carries no fields at all;
    the handler takes the tenant from get_current_tenant as its first statement.
    A tenant a caller could name would be every boutique's queue readable from
    one host."""
    client, stub = _client()
    with client:
        _post(client)
    assert stub.board_calls == [TENANT.id]


# --- the error table, and it is two rows ---


def test_a_spent_budget_is_the_shared_429_body() -> None:
    """A13. No new error class and no new handler: board() raises the same
    CheckinThrottledError the two check-in routes raise, and main.py's shipped
    handler answers the shared body byte for byte. No Retry-After — the window is
    a Settings field precisely so it can change without a deploy, and a body
    naming a duration would silently contradict the next .env edit."""
    client, stub = _client()
    stub.board_error = CheckinThrottledError()
    with client:
        resp = _post(client)
    assert resp.status_code == 429
    assert resp.content == JSONResponse(TOO_MANY_ATTEMPTS_BODY).body


def test_every_spec_error_code_is_asserted() -> None:
    """Mechanical completeness, the test_checkin_api.py shape: a row added to the
    spec's error table without a test here fails immediately rather than shipping
    as a 500 — main.py registers no catch-all handler."""
    observed = set()
    client, _ = _client(host="nosuch.localtest.me")
    with client:
        observed.add(_post(client).json()["error"]["code"])
    client, stub = _client()
    stub.board_error = CheckinThrottledError()
    with client:
        observed.add(_post(client).json()["error"]["code"])
    assert observed == SPEC_ERROR_CODES


@pytest.mark.parametrize("body", [None, {"tenant_id": "00000000-0000-4000-8000-000000000000"}])
def test_the_route_takes_no_body_and_a_supplied_one_changes_nothing(
    body: dict[str, str] | None,
) -> None:
    """There is no request model, so there is nothing to forbid extras on — and
    nothing a caller sends can reach the service. Asserted rather than assumed,
    because "the handler has no body parameter" is exactly the kind of claim a
    later signature change makes false silently."""
    client, stub = _client()
    with client:
        resp = client.post(BOARD_PATH, json=body)
    assert resp.status_code == 200
    assert stub.board_calls == [TENANT.id]
