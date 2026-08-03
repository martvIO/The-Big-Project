"""Fast API tests for the public check-in surface: a stub QueueService and a
hardcoded TenantContext, no database (the F11 posture template).

This is the file a mutating public route proves itself in. The service suite
proves the metering; this one proves the HTTP contract — anonymous,
tenant-from-Host, cookie-blind, no-store, POST-only — and the exact error table.

**And it is where Ruling 3's security property becomes an assertion.** The create
answers ONE shape, 201, every time. Two submissions of the same number on the
same day are indistinguishable at every layer a client can observe: same status
line, same key set, same types. A stranger who submits a woman's mobile receives
a ticket of his own and learns nothing whatsoever about her.
"""

import datetime
import uuid
from collections.abc import Sequence
from itertools import cycle

import httpx
import pytest
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.auth.dependencies import get_auth_service
from app.auth.service import StaffContext
from app.errors import DomainValidationError
from app.main import TOO_MANY_ATTEMPTS_BODY, create_app
from app.models.constants import QueueTicketStatus, VisitType
from app.queue.schemas import TicketView
from app.queue.validation import CheckinThrottledError, QueueTicketNotFoundError
from app.security_headers import SECURITY_HEADERS
from app.tenancy.middleware import TenantContext

TENANT = TenantContext(id=uuid.uuid4(), slug="bella", name="בלה כלות", settings={})
STAFF_ID = uuid.uuid4()
TOKEN = "session-token-abc"

TICKET_ID = uuid.UUID("33333333-3333-4333-8333-333333333333")
SECOND_TICKET_ID = uuid.UUID("44444444-4444-4444-8444-444444444444")
CALLED_AT = datetime.datetime(2026, 7, 18, 20, 30, tzinfo=datetime.UTC)

CHECKIN_PATH = "/storefront/checkin"
POSITION_PATH = "/storefront/checkin/position"
PATHS = [CHECKIN_PATH, POSITION_PATH]

# The whole of TicketView, spelled out rather than derived from the model: a
# refactor that reintroduces an envelope or an `existing: true` flag must fail
# this literal, and a set derived from the model would move with it.
TICKET_KEYS = {"id", "status", "position", "called_at"}

# The storefront's existing four, and F33 adds none. Asserted set-equal below
# against what this module actually exercises, so a row added to the spec's
# error table without a test here fails immediately rather than shipping as a
# 500 — main.py registers no catch-all handler.
SPEC_ERROR_CODES = {"TENANT_NOT_FOUND", "NOT_FOUND", "VALIDATION_ERROR", "TOO_MANY_ATTEMPTS"}


def _body() -> dict[str, object]:
    return {
        "name": "נועה",
        "phone": "050-123-4567",
        "visit_type": VisitType.BRIDE.value,
        "marketing_opt_in": False,
    }


class StubQueueService:
    """The router is a thin delegate, so the stub is programmable outcomes and a
    call log — nothing else.

    `ids` cycles: the default single-element cycle makes every create byte
    identical (which is what the cookie-blindness comparison needs), and a
    two-element cycle is what the same-phone-twice test uses to prove the two
    ids differ while nothing else does.
    """

    def __init__(self, ids: Sequence[uuid.UUID] = (TICKET_ID,)) -> None:
        self._ids = cycle(ids)
        self.check_in_error: Exception | None = None
        self.position_error: Exception | None = None
        self.check_in_calls: list[tuple[uuid.UUID, str, str, str, bool]] = []
        self.position_calls: list[tuple[uuid.UUID, uuid.UUID]] = []

    async def check_in(
        self,
        tenant_id: uuid.UUID,
        *,
        name: str,
        raw_phone: str,
        visit_type: str,
        marketing_opt_in: bool,
    ) -> TicketView:
        if self.check_in_error is not None:
            raise self.check_in_error
        self.check_in_calls.append((tenant_id, name, raw_phone, visit_type, marketing_opt_in))
        return TicketView(
            id=next(self._ids),
            status=QueueTicketStatus.WAITING.value,
            position=3,
            called_at=None,
        )

    async def position(self, tenant_id: uuid.UUID, ticket_id: uuid.UUID) -> TicketView:
        if self.position_error is not None:
            raise self.position_error
        self.position_calls.append((tenant_id, ticket_id))
        return TicketView(
            id=ticket_id,
            status=QueueTicketStatus.WAITING.value,
            position=2,
            called_at=CALLED_AT,
        )


class FakeAuthService:
    """Only here so the owner cookie in the cookie-blindness tests is a genuinely
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


def _post(client: TestClient, path: str) -> httpx.Response:
    if path == CHECKIN_PATH:
        return client.post(path, json=_body())
    return client.post(path, json={"ticket_id": str(TICKET_ID)})


# --- the public contract: anonymous, tenant-required, cookie-blind, POST-only ---


def test_the_create_accepts_anonymous_and_answers_201_with_the_whole_ticket() -> None:
    client, stub = _client()
    with client:
        assert client.cookies == {}
        resp = client.post(CHECKIN_PATH, json=_body())
    assert resp.status_code == 201
    assert resp.json() == {
        "id": str(TICKET_ID),
        "status": QueueTicketStatus.WAITING.value,
        "position": 3,
        "called_at": None,
    }
    assert "set-cookie" not in resp.headers
    assert stub.check_in_calls == [
        (TENANT.id, "נועה", "050-123-4567", VisitType.BRIDE.value, False)
    ]


def test_the_position_read_accepts_anonymous_and_answers_200() -> None:
    client, stub = _client()
    with client:
        assert client.cookies == {}
        resp = client.post(POSITION_PATH, json={"ticket_id": str(TICKET_ID)})
    assert resp.status_code == 200
    assert resp.json() == {
        "id": str(TICKET_ID),
        "status": QueueTicketStatus.WAITING.value,
        "position": 2,
        "called_at": "2026-07-18T20:30:00Z",
    }
    assert "set-cookie" not in resp.headers
    assert stub.position_calls == [(TENANT.id, TICKET_ID)]


def test_the_tenant_reaches_the_service_from_the_host_and_never_from_the_body() -> None:
    """A tenant id a client could name would be a cross-tenant write on an
    anonymous surface. The request body carries no tenant field and the handler
    takes it from get_current_tenant as its first statement."""
    client, stub = _client()
    with client:
        client.post(CHECKIN_PATH, json=_body())
        client.post(POSITION_PATH, json={"ticket_id": str(TICKET_ID)})
    assert stub.check_in_calls[0][0] == TENANT.id
    assert stub.position_calls[0][0] == TENANT.id


@pytest.mark.parametrize("path", PATHS)
def test_the_checkin_paths_are_not_exempt_from_tenant_resolution(path: str) -> None:
    """Public is not host-agnostic. Never add a /storefront path to EXEMPT_PATHS
    — the capitalised warning in tenancy/middleware.py."""
    client, stub = _client(host="nosuch.localtest.me")
    with client:
        resp = _post(client, path)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "TENANT_NOT_FOUND"
    assert stub.check_in_calls == []
    assert stub.position_calls == []


@pytest.mark.parametrize("path", PATHS)
def test_checkin_responses_are_never_cached(path: str) -> None:
    """Both bodies name one person's place in a real queue, and the position
    page is reached on a phone where bfcache is the default."""
    client, _ = _client()
    with client:
        resp = _post(client, path)
    assert resp.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("path", PATHS)
def test_get_stays_405(path: str) -> None:
    """The read router is contractually GET-only and this sibling is POST-only —
    the pairing that keeps both contracts mechanically true. The position read
    is a POST deliberately: a GET would put the capability in the query string
    and from there into every access log on the path."""
    client, _ = _client()
    with client:
        resp = client.get(path)
    assert resp.status_code == 405


def test_the_position_read_is_byte_identical_with_an_owner_cookie() -> None:
    client, _ = _client()
    with client:
        anonymous = client.post(POSITION_PATH, json={"ticket_id": str(TICKET_ID)})
        client.cookies.set("boutique_session", TOKEN, domain="bella.localtest.me")
        with_cookie = client.post(POSITION_PATH, json={"ticket_id": str(TICKET_ID)})
    assert with_cookie.status_code == anonymous.status_code == 200
    assert with_cookie.content == anonymous.content
    assert "set-cookie" not in with_cookie.headers


def test_the_create_is_identical_with_an_owner_cookie() -> None:
    """Two separate clients compared on the FULL body, no field excluded: the
    stub returns a deterministic id, so anything less than full equality would
    be a weaker assertion than the precedent's.

    test_owner_cookie_changes_nothing in test_storefront_api.py loops a GET-only
    ROUTES list and covers neither of these two paths, which is why the
    assertion is repeated here rather than assumed.
    """
    anon_client, _ = _client()
    with anon_client:
        anonymous = anon_client.post(CHECKIN_PATH, json=_body())

    cookie_client, _ = _client()
    with cookie_client:
        cookie_client.cookies.set("boutique_session", TOKEN, domain="bella.localtest.me")
        with_cookie = cookie_client.post(CHECKIN_PATH, json=_body())

    assert with_cookie.status_code == anonymous.status_code == 201
    assert with_cookie.json() == anonymous.json()
    assert "set-cookie" not in with_cookie.headers


def test_security_headers_are_on_a_checkin_response() -> None:
    client, _ = _client()
    with client:
        resp = client.post(CHECKIN_PATH, json=_body())
    assert {header: resp.headers.get(header) for header in SECURITY_HEADERS} == SECURITY_HEADERS


# --- Ruling 3: one shape, and the create discloses nothing about anybody ---


def test_a_second_create_for_the_same_phone_is_indistinguishable_from_the_first() -> None:
    """The security property, asserted rather than described. Same status line,
    same key set, same types — nothing in the wire format tells a prober whether
    that number was already in this boutique's queue. A second ticket exists;
    F58 merges or removes it."""
    client, _ = _client(StubQueueService(ids=(TICKET_ID, SECOND_TICKET_ID)))
    with client:
        first = client.post(CHECKIN_PATH, json=_body())
        second = client.post(CHECKIN_PATH, json=_body())

    assert first.status_code == second.status_code == 201
    assert set(first.json()) == set(second.json()) == TICKET_KEYS
    assert first.json()["id"] != second.json()["id"]
    assert {type(value) for value in first.json().values()} == {
        type(value) for value in second.json().values()
    }


def test_the_create_response_carries_no_envelope_and_no_pii() -> None:
    """No `ticket` wrapper, no `outcome`, no `existing` flag — and no name, no
    phone, no visit_type, no queue_day, no tenant_id, no created_at and no
    consent stamp. She typed the name; echoing it back over an anonymous
    endpoint keyed by a guessable-in-principle id buys nothing."""
    client, _ = _client()
    with client:
        body = client.post(CHECKIN_PATH, json=_body()).json()
    assert set(body) == TICKET_KEYS
    assert "נועה" not in str(body)
    assert "050" not in str(body)


def test_the_create_and_the_position_read_answer_the_same_key_set() -> None:
    """One view, two routes. A field added to one and not the other is a second
    contract nobody wrote down."""
    client, _ = _client()
    with client:
        created = client.post(CHECKIN_PATH, json=_body()).json()
        read = client.post(POSITION_PATH, json={"ticket_id": str(TICKET_ID)}).json()
    assert set(created) == set(read) == TICKET_KEYS


# --- the exact error table from the spec ---


def test_an_unknown_key_in_the_create_body_is_a_house_shape_400() -> None:
    """ForbidExtraModel, the house convention on a public write."""
    client, stub = _client()
    with client:
        resp = client.post(CHECKIN_PATH, json={**_body(), "tenant_id": str(uuid.uuid4())})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert stub.check_in_calls == []


def test_a_malformed_ticket_id_is_a_house_shape_400() -> None:
    client, stub = _client()
    with client:
        resp = client.post(POSITION_PATH, json={"ticket_id": "not-a-uuid"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert stub.position_calls == []


def test_a_service_validation_error_leaves_as_a_400_carrying_its_message() -> None:
    client, stub = _client()
    stub.check_in_error = DomainValidationError("Enter a valid Israeli mobile number.")
    with client:
        resp = client.post(CHECKIN_PATH, json=_body())
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["message"] == "Enter a valid Israeli mobile number."


def test_an_unknown_ticket_is_the_shared_404_and_names_nothing() -> None:
    """QueueTicketNotFoundError inherits DomainNotFoundError, so it rides the
    shipped handler and F33 registers no 404 handler of its own. The body is the
    shared one: a foreign-tenant id must read exactly like an absent one."""
    client, stub = _client()
    stub.position_error = QueueTicketNotFoundError()
    with client:
        resp = client.post(POSITION_PATH, json={"ticket_id": str(uuid.uuid4())})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.parametrize("path", PATHS)
def test_a_spent_budget_is_the_shared_429_body_byte_for_byte(path: str) -> None:
    """The tenth handler returning TOO_MANY_ATTEMPTS_BODY verbatim. No new code,
    no Retry-After: every window here is a Settings field precisely so it can
    change without a deploy, and a body naming a duration would silently
    contradict the next .env edit."""
    client, stub = _client()
    stub.check_in_error = CheckinThrottledError()
    stub.position_error = CheckinThrottledError()
    with client:
        resp = _post(client, path)
    assert resp.status_code == 429
    assert resp.content == JSONResponse(TOO_MANY_ATTEMPTS_BODY).body


def test_every_spec_error_code_is_asserted() -> None:
    """Mechanical completeness: a row added to the spec's error table without a
    test here fails immediately rather than shipping as a 500 — main.py has 49
    explicit handler registrations and none for Exception."""
    observed = set()
    client, _ = _client(host="nosuch.localtest.me")
    with client:
        observed.add(client.post(CHECKIN_PATH, json=_body()).json()["error"]["code"])
    client, _ = _client()
    with client:
        observed.add(client.post(POSITION_PATH, json={"ticket_id": "nope"}).json()["error"]["code"])
    client, stub = _client()
    stub.position_error = QueueTicketNotFoundError()
    with client:
        observed.add(
            client.post(POSITION_PATH, json={"ticket_id": str(TICKET_ID)}).json()["error"]["code"]
        )
    client, stub = _client()
    stub.check_in_error = CheckinThrottledError()
    with client:
        observed.add(client.post(CHECKIN_PATH, json=_body()).json()["error"]["code"])
    assert observed == SPEC_ERROR_CODES
