"""F53 fast API tests: route wiring, the 401, both roles, the generic 403, the
host-derived tenant, the whole error table and the disclosure walk — a
duck-typed FakeCustomersService on app.state.customers_service plus a hardcoded
TenantContext resolver, no database (test_dashboard_api.py style).

**This module is the shadowing guard for the EIGHTH /manage router.** Eight
routers now mount `prefix="/manage"`, and a duplicated (method, path) would
silently win or lose on include order with nothing else going red. The ROUTES
table below and `test_every_route_is_wired_and_reaches_the_service` are what
keep that honest; the ordinal also lives in `main.py`'s include comment and the
two must agree.

**This is also where F53 diverges from F52's template.** The dashboard module
asserts that a mismatched Origin is ALLOWED, correctly — its route is a GET and
CsrfOriginMiddleware fences MUTATING_METHODS only. F53 ships a PATCH, so the
inverse assertion is the right one here and copying F52's would assert the
opposite of this feature's posture.
"""

import datetime
import time
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_auth_service
from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.service import StaffContext
from app.customers.schemas import (
    CustomerBookingRow,
    CustomerDetail,
    CustomerListResponse,
    CustomerRow,
    SmsLogRow,
)
from app.customers.service import CustomerNotFoundError
from app.customers.validation import CUSTOMER_LIST_MAX_LIMIT, MAX_LIST_OFFSET
from app.main import NOT_AUTHORIZED_BODY, create_app
from app.models.constants import BookingStatus, MessageKind, MessageStatus, StaffRole
from app.tenancy.middleware import TenantContext

TENANT = TenantContext(id=uuid.uuid4(), slug="bella", name="Bella Bridal", settings={})
STAFF_ID = uuid.uuid4()
TOKEN = "session-token-abc"
CUSTOMER_ID = uuid.uuid4()
LIST_PATH = "/manage/customers"
DETAIL_PATH = f"/manage/customers/{CUSTOMER_ID}"
STARTS_AT = datetime.datetime(2026, 6, 1, 9, 0, tzinfo=datetime.UTC)

# Three rows. EIGHT routers now mount prefix="/manage", so a duplicated
# (method, path) would silently win or lose on include order: this table is the
# wiring guard, and a 404 in the walk below is what catches a shadow.
ROUTES: list[tuple[str, str, dict[str, Any] | None]] = [
    ("GET", LIST_PATH, None),
    ("GET", DETAIL_PATH, None),
    ("PATCH", DETAIL_PATH, {"notes": "x"}),
]

# The spec's error table (D9), and every code is re-derived from a live response
# in test_every_spec_error_code_is_asserted rather than trusted from here.
#
# CSRF_ORIGIN_MISMATCH IS in the set, unlike F52's: csrf.py fences
# MUTATING_METHODS and the PATCH is one.
SPEC_ERROR_CODES = {
    "NOT_AUTHENTICATED",
    "NOT_AUTHORIZED",
    "VALIDATION_ERROR",
    "NOT_FOUND",
    "CSRF_ORIGIN_MISMATCH",
}

# NOT test_dashboard_api.DASHBOARD_FORBIDDEN_KEYS. That set contains `phone`,
# `notes`, `customer_name` and `customer_id`, and F53 legitimately ships the
# first two on a screen whose entire purpose is one named person — borrowing it
# would red-fail against this spec's own contract.
#
# `phone` is deliberately ABSENT here, on both response halves. D6 argues it: a
# day list is a schedule, a customer directory is an index of PEOPLE, and the
# phone is the disambiguator for the shared-name case. A key the feature
# deliberately ships cannot also be a disclosure tripwire.
#
# The first two are the ones this module exists for. `provider_message_id` and
# `error` are the columns D4 refuses to publish, and `error` is fenced by a
# shipped comment on the column itself.
CUSTOMER_FORBIDDEN_KEYS = frozenset(
    {
        "provider_message_id",
        "error",
        "manage_token_hash",
        "password_hash",
        "tenant_id",
        "booking_id",
        "deleted_at",
        "dress_name",
        "dress_size",
        "seat_index",
        "email",
    }
)

# Kept in step with test_staff_role_gating.UNKNOWN_ROLE, which owns the tripwire
# asserting it never becomes a real StaffRole. Duplicated because that module
# imports the API modules, so the dependency cannot run the other way.
UNKNOWN_ROLE = "no-such-role"


def _all_keys(node: Any) -> Iterator[str]:
    """Every key at every depth — test_dashboard_api.py:107-115, reused."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from _all_keys(value)
    elif isinstance(node, list):
        for item in node:
            yield from _all_keys(item)


def _detail() -> CustomerDetail:
    """A FULLY POPULATED detail — both panels non-empty and a real
    `messages_total`. The disclosure walk is only worth running against this: a
    key that never appears cannot leak."""
    return CustomerDetail(
        id=CUSTOMER_ID,
        name="מיכל לוי",
        phone="+972501234567",
        notes="מגיעה עם אמא",
        tags=["VIP", "כלה"],
        bookings=[
            CustomerBookingRow(
                id=uuid.uuid4(),
                starts_at=STARTS_AT,
                status=BookingStatus.CANCELLED.value,
                appointment_type_name="מדידה ראשונה",
            )
        ],
        messages=[
            SmsLogRow(
                id=uuid.uuid4(),
                created_at=STARTS_AT,
                kind=MessageKind.CONFIRMATION.value,
                status=MessageStatus.SENT.value,
                body="הפגישה שלך אושרה",
            )
        ],
        messages_total=97,
        # F20 DR-13: the three consent fields the CRM card renders a badge from.
        # A CONSENTED-AND-WITHDRAWN subject, deliberately — it is the only state
        # where both timestamps are non-null, so a console that collapsed them
        # into one boolean would render it wrong, and a payload seeded with the
        # simpler state would not notice.
        marketing_consent_at=STARTS_AT,
        marketing_consent_withdrawn_at=STARTS_AT + datetime.timedelta(days=30),
        erased_at=None,
    )


def _list() -> CustomerListResponse:
    return CustomerListResponse(
        items=[
            CustomerRow(id=CUSTOMER_ID, name="מיכל לוי", phone="+972501234567", tags=["VIP", "כלה"])
        ],
        total=1,
        offset=0,
        limit=50,
    )


class FakeAuthService:
    def __init__(self, role: str = StaffRole.OWNER.value) -> None:
        # The session's tenant_id DELIBERATELY disagrees with the host-resolved
        # TENANT.id, so a handler reaching for StaffContext.tenant_id is
        # distinguishable from a correct one.
        self.staff = StaffContext(
            id=STAFF_ID,
            tenant_id=uuid.uuid4(),
            email="owner@bella.example",
            display_name="Owner",
            role=role,
        )

    async def login(
        self, tenant_id: uuid.UUID, email: str, password: str
    ) -> tuple[StaffContext, str]:
        return self.staff, TOKEN

    async def resolve_session(self, tenant_id: uuid.UUID, token: str) -> StaffContext | None:
        return self.staff if token == TOKEN else None

    async def logout(self, tenant_id: uuid.UUID, token: str) -> None:
        return None


class FakeCustomersService:
    """Duck-typed CustomersService: records what every route was called with and
    answers one fully populated payload."""

    def __init__(self, *, missing: bool = False) -> None:
        self.calls: list[dict[str, Any]] = []
        self.missing = missing

    async def list_customers(
        self, tenant_id: uuid.UUID, *, q: str | None, offset: int, limit: int
    ) -> CustomerListResponse:
        self.calls.append({"tenant_id": tenant_id, "q": q, "offset": offset, "limit": limit})
        return _list()

    async def detail(self, tenant_id: uuid.UUID, customer_id: uuid.UUID) -> CustomerDetail:
        self.calls.append({"tenant_id": tenant_id, "customer_id": customer_id})
        if self.missing:
            raise CustomerNotFoundError
        return _detail()

    async def update(
        self,
        tenant_id: uuid.UUID,
        customer_id: uuid.UUID,
        *,
        notes: str | None,
        tags: list[str] | None,
        actor: StaffContext,
    ) -> CustomerDetail:
        self.calls.append(
            {
                "tenant_id": tenant_id,
                "customer_id": customer_id,
                "notes": notes,
                "tags": tags,
                "actor_id": actor.id,
            }
        )
        if self.missing:
            raise CustomerNotFoundError
        return _detail()


def _client(
    fake: FakeCustomersService, *, authed: bool = True, role: str = StaffRole.OWNER.value
) -> TestClient:
    async def _resolver(slug: str) -> TenantContext | None:
        return TENANT if slug == "bella" else None

    app = create_app(resolver=_resolver)
    auth = FakeAuthService(role)
    app.state.auth_service = auth
    app.state.login_rate_limiter = FixedWindowRateLimiter(
        max_attempts=3, window_seconds=900, clock=time.monotonic
    )
    # app.state, not dependency_overrides: get_customers_service reads app.state
    # directly, the way every other console dependency does.
    app.state.customers_service = fake
    app.dependency_overrides[get_auth_service] = lambda: auth
    client = TestClient(app, base_url="http://bella.localtest.me")
    if authed:
        client.cookies.set("boutique_session", TOKEN, domain="bella.localtest.me")
    return client


# --- wiring, authentication and the role gate ---


def test_every_route_requires_authentication() -> None:
    fake = FakeCustomersService()
    with _client(fake, authed=False) as client:
        for method, path, body in ROUTES:
            resp = client.request(method, path, json=body)
            assert resp.status_code == 401, f"{method} {path} → {resp.status_code}"
            assert resp.json()["error"]["code"] == "NOT_AUTHENTICATED"
    assert fake.calls == []  # the guard fires before any service call


def test_every_route_is_wired_and_reaches_the_service() -> None:
    """EIGHT routers now mount prefix="/manage": a path collision would silently
    shadow, and a 404 here is what catches it. The ordinal in `main.py`'s
    include comment and the one in this docstring must agree."""
    for method, path, body in ROUTES:
        fake = FakeCustomersService()
        with _client(fake) as client:
            resp = client.request(method, path, json=body)
        assert resp.status_code == 200, f"{method} {path} → {resp.status_code} {resp.text}"
        assert fake.calls, f"{method} {path} never reached the service"


@pytest.mark.parametrize("role", [StaffRole.OWNER.value, StaffRole.SHIFT_MANAGER.value])
def test_both_roles_reach_every_route(role: str) -> None:
    """The SMC epic's locked table admits both, and there is no per-role
    projection: a shift manager sees the same card the owner does and can edit
    the same notes. This router must NOT be added to
    test_staff_role_gating.OWNER_ONLY — a both-roles route there reports as
    `unenforced_owner_only`."""
    for method, path, body in ROUTES:
        fake = FakeCustomersService()
        with _client(fake, role=role) as client:
            resp = client.request(method, path, json=body)
        assert resp.status_code == 200, f"{role} {method} {path} → {resp.text}"


def test_an_unknown_role_is_refused_with_the_exact_generic_body() -> None:
    """Fails closed: a role the enum does not know is not admitted by accident.
    The comparison is against the imported constant, so it pins uniformity with
    every other /manage refusal rather than a literal of its own."""
    for method, path, body in ROUTES:
        fake = FakeCustomersService()
        with _client(fake, role=UNKNOWN_ROLE) as client:
            resp = client.request(method, path, json=body)
        assert resp.status_code == 403, f"{method} {path} → {resp.status_code}"
        assert resp.json() == NOT_AUTHORIZED_BODY
        assert fake.calls == []  # the gate raises during dependency solving


@pytest.mark.parametrize(("method", "path", "body"), ROUTES, ids=[f"{m}-{p}" for m, p, _ in ROUTES])
def test_no_customer_response_is_cached(
    method: str, path: str, body: dict[str, Any] | None
) -> None:
    """Router-level `_no_store`, so a route added here later cannot forget it.
    A cached copy of a bride's card in a shared boutique browser would show one
    customer's notes to whoever opens the console next."""
    fake = FakeCustomersService()
    with _client(fake) as client:
        resp = client.request(method, path, json=body)
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "no-store"


# --- the trust path ---


@pytest.mark.parametrize(("method", "path", "body"), ROUTES, ids=[f"{m}-{p}" for m, p, _ in ROUTES])
def test_every_handler_passes_the_host_resolved_tenant(
    method: str, path: str, body: dict[str, Any] | None
) -> None:
    """`get_current_tenant(request)` is host-derived — TenantResolutionMiddleware
    binds it from the Host header and nothing else. The other source in hand,
    `StaffContext.tenant_id`, is session-derived, and the FakeAuthService above
    deliberately disagrees with it. This is the only place the difference is
    observable."""
    fake = FakeCustomersService()
    with _client(fake) as client:
        assert client.request(method, path, json=body).status_code == 200
    assert [call["tenant_id"] for call in fake.calls] == [TENANT.id]


def test_the_patch_carries_the_acting_staff_id_and_the_two_gets_do_not() -> None:
    """The PATCH declares `staff` because the acting id has exactly one reader —
    `actor_id` on its audit row. The two GETs declare none: a parameter with no
    reader would put the session-derived tenant_id in reach on two routes with
    no other reason to want it."""
    fake = FakeCustomersService()
    with _client(fake) as client:
        client.patch(DETAIL_PATH, json={"tags": ["VIP"]})
    assert fake.calls == [
        {
            "tenant_id": TENANT.id,
            "customer_id": CUSTOMER_ID,
            "notes": None,
            "tags": ["VIP"],
            "actor_id": STAFF_ID,
        }
    ]


# --- the error table (D9): 400 everywhere, never 422 ---


@pytest.mark.parametrize(
    "query",
    [
        {"limit": 0},
        {"limit": CUSTOMER_LIST_MAX_LIMIT + 1},
        {"offset": -1},
        {"offset": MAX_LIST_OFFSET + 1},
        {"q": "מ" * 200},
    ],
)
def test_a_bad_list_bound_is_a_house_shape_400_and_never_reaches_the_service(
    query: dict[str, Any],
) -> None:
    """400, not 422 — `main.py` normalizes RequestValidationError platform-wide
    with the comment "no default 422s anywhere". The offset bound is not
    cosmetic: an unbounded int binds into `OFFSET $n::BIGINT` and dies in
    asyncpg's int8_encode as a 500."""
    fake = FakeCustomersService()
    with _client(fake) as client:
        resp = client.get(LIST_PATH, params=query)
    assert resp.status_code == 400, resp.text
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert fake.calls == []


def test_an_unknown_body_key_is_a_400_and_never_reaches_the_service() -> None:
    """`UpdateCustomerRequest` is a `ForbidExtraModel`: an unknown key is a
    house-shape 400, not a silently ignored field."""
    fake = FakeCustomersService()
    with _client(fake) as client:
        resp = client.patch(DETAIL_PATH, json={"notes": "x", "name": "מישהי אחרת"})
    assert resp.status_code == 400, resp.text
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert fake.calls == []


def test_a_malformed_customer_id_is_a_400_not_a_500() -> None:
    fake = FakeCustomersService()
    with _client(fake) as client:
        resp = client.get("/manage/customers/not-a-uuid")
    assert resp.status_code == 400, resp.text
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert fake.calls == []


@pytest.mark.parametrize(
    ("method", "body"), [("GET", None), ("PATCH", {"notes": "x"})], ids=["GET", "PATCH"]
)
def test_an_unknown_customer_is_a_404_on_both_detail_routes(
    method: str, body: dict[str, Any] | None
) -> None:
    """`CustomerNotFoundError` subclasses `DomainNotFoundError`, so the handler
    bound to the app/errors.py base answers it through Starlette's MRO walk —
    F53 registers no handler of its own (D9)."""
    fake = FakeCustomersService(missing=True)
    with _client(fake) as client:
        resp = client.request(method, DETAIL_PATH, json=body)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_a_mutating_customer_request_with_a_mismatched_origin_is_403() -> None:
    """Where F53 diverges from F52's GET-only template: `csrf.py` fences
    MUTATING_METHODS and the PATCH is one. Do NOT copy
    `test_a_dashboard_read_with_a_mismatched_origin_is_allowed` — that module's
    route is a GET and its assertion is the opposite of this one."""
    fake = FakeCustomersService()
    with _client(fake) as client:
        resp = client.patch(
            DETAIL_PATH, json={"notes": "x"}, headers={"origin": "http://evil.localtest.me"}
        )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "CSRF_ORIGIN_MISMATCH"
    assert fake.calls == []


def test_every_spec_error_code_is_asserted() -> None:
    """Mechanical completeness, re-derived from live responses rather than read
    off a literal."""
    observed = set()
    with _client(FakeCustomersService(), authed=False) as client:
        observed.add(client.get(LIST_PATH).json()["error"]["code"])
    with _client(FakeCustomersService(), role=UNKNOWN_ROLE) as client:
        observed.add(client.get(LIST_PATH).json()["error"]["code"])
    with _client(FakeCustomersService()) as client:
        observed.add(client.get(LIST_PATH, params={"limit": 0}).json()["error"]["code"])
        observed.add(
            client.patch(
                DETAIL_PATH, json={"notes": "x"}, headers={"origin": "http://evil.localtest.me"}
            ).json()["error"]["code"]
        )
    with _client(FakeCustomersService(missing=True)) as client:
        observed.add(client.get(DETAIL_PATH).json()["error"]["code"])
    assert observed == SPEC_ERROR_CODES


# --- the disclosure contract ---


def test_the_sms_log_row_ships_exactly_five_fields() -> None:
    """An EQUALITY, never a subset, and **this assertion is not to be relaxed**.

    It is what fails when someone adds `provider_message_id` or `error` "for
    debugging", and — unlike a value-based sentinel — it also catches a rename
    that would quietly drop a field the console renders. The value half is
    unreachable from this module: FastAPI serializes against the annotation and
    `SmsLogRow` has no slot for either column, so the sentinel walk lives in
    `test_customers_service.py`, where a real MessageLog crosses the mapping.
    """
    assert set(SmsLogRow.model_fields) == {"id", "created_at", "kind", "status", "body"}


@pytest.mark.parametrize(("method", "path", "body"), ROUTES, ids=[f"{m}-{p}" for m, p, _ in ROUTES])
def test_no_fenced_key_reaches_the_wire_on_any_route(
    method: str, path: str, body: dict[str, Any] | None
) -> None:
    fake = FakeCustomersService()
    with _client(fake) as client:
        payload = client.request(method, path, json=body).json()
    keys = set(_all_keys(payload))

    assert keys & CUSTOMER_FORBIDDEN_KEYS == set()
    # The walk is not vacuous: every nested collection it has to descend into is
    # populated on the detail routes, so a leaked key would have somewhere to
    # appear.
    assert "phone" in keys, "the walk is pointless if the payload is empty"
    if path == DETAIL_PATH:
        assert payload["bookings"] and payload["messages"]
        assert payload["messages_total"] == 97
        # Deliberately present, and named here so a future reader does not "fix"
        # them: `notes` and `phone` are what this screen exists to show, to the
        # same two roles that already read both on the booking detail.
        assert {"notes", "tags", "messages_total"} <= keys
    else:
        assert payload["items"]


def test_the_detail_carries_the_three_consent_fields_and_the_list_does_not() -> None:
    """⚠ F20 DR-13, and the second half is as load-bearing as the first.

    The detail gains them because Gate 1 Q4 admits a shift manager to
    `marketing-withdraw` and NOT to the privacy panel — so this card is the only
    surface where a front-desk staffer can see what she is being asked to
    revoke, and without it Q4's ruling is reachable only by an owner who goes
    looking somewhere else first.

    The LIST gains nothing: no consent column, no filter, no sort. A customer
    directory that renders a marketing-consent state per row is a marketing
    audience list on the busiest screen in the console, and nothing in v1 sends
    marketing at all.
    """
    fake = FakeCustomersService()
    client = _client(fake)
    with client:
        detail = client.get(DETAIL_PATH).json()
        listed = client.get(LIST_PATH).json()

    assert detail["marketing_consent_at"] is not None
    assert detail["marketing_consent_withdrawn_at"] is not None
    assert detail["erased_at"] is None

    consent_keys = {"marketing_consent_at", "marketing_consent_withdrawn_at", "erased_at"}
    assert not consent_keys & set(_all_keys(listed)), "the customer LIST leaks the consent state"
    assert set(CustomerRow.model_fields) == {"id", "name", "phone", "tags"}
