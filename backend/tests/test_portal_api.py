"""Fast API tests for F24's portal surface: a stub PortalService + a hardcoded
TenantContext, no database (test_booking_manage_api.py style).

The db-marked suite proves the behaviour; this file proves the HTTP contract —
the auth matrix (every cookie-authed route 401s without a cookie and with a
garbage one), the cookie's own attributes, `no-store`, and the fact that the
STAFF cookie is not a portal credential and vice versa.

That last pair is the reason this file exists at all. Both apps live on one
tenant host, so both cookies ride every request to it. If `get_current_customer`
read `boutique_session`, an owner signing in would silently acquire a customer
session on her own boutique; if `get_current_staff` read the customer cookie, a
bride would hold a console session. Two names, two dependencies, and two tests.
"""

import dataclasses
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.auth.cookies import CUSTOMER_SESSION_COOKIE, SESSION_COOKIE
from app.auth.dependencies import get_auth_service
from app.auth.service import StaffContext
from app.main import create_app
from app.portal.schemas import PortalSessionResponse
from app.portal.service import CustomerContext, PortalNoBookingsError, PortalThrottledError
from app.security_headers import SECURITY_HEADERS
from app.tenancy.middleware import TenantContext

TENANT = TenantContext(id=uuid.uuid4(), slug="bella", name="בלה כלות", settings={})
STAFF_ID = uuid.uuid4()
CUSTOMER_ID = uuid.uuid4()
STAFF_SESSION_TOKEN = "staff-session-token"
PORTAL_TOKEN = "portal-session-token"
VERIFICATION_TOKEN = "vt-" + "a" * 40
PHONE = "0501234567"

SESSION = "/storefront/portal/session"
ME = "/storefront/portal/me"
LOGOUT = "/storefront/portal/logout"
# Every route that reads the customer cookie. Grows with each phase; the auth
# matrix below is parametrised over it so a route added without a cookie gate is
# a red rather than a gap.
COOKIE_ROUTES: tuple[tuple[str, str, dict[str, Any] | None], ...] = (
    ("GET", ME, None),
    ("POST", LOGOUT, None),
)

CUSTOMER = CustomerContext(id=CUSTOMER_ID, tenant_id=TENANT.id, name="רותם", phone="+972501234567")


@dataclasses.dataclass
class StubPortalService:
    """The router is a thin delegate, so the stub is programmable outcomes and a
    call log — nothing else."""

    error: Exception | None = None
    calls: list[tuple[str, Any]] = dataclasses.field(default_factory=list)

    async def create_session(
        self, tenant_id: uuid.UUID, *, raw_phone: str, verification_token: str
    ) -> tuple[PortalSessionResponse, str]:
        if self.error is not None:
            raise self.error
        self.calls.append(("create_session", (tenant_id, raw_phone, verification_token)))
        return PortalSessionResponse(customer_name=CUSTOMER.name), PORTAL_TOKEN

    async def resolve_session(self, tenant_id: uuid.UUID, token: str) -> CustomerContext | None:
        return CUSTOMER if token == PORTAL_TOKEN and tenant_id == TENANT.id else None

    async def logout(self, tenant_id: uuid.UUID, token: str) -> None:
        self.calls.append(("logout", (tenant_id, token)))


class FakeAuthService:
    """Only here so the owner cookie in the cross-cookie tests is a genuinely
    resolvable staff session rather than a random string."""

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
        return self.staff, STAFF_SESSION_TOKEN

    async def resolve_session(self, tenant_id: uuid.UUID, token: str) -> StaffContext | None:
        return self.staff if token == STAFF_SESSION_TOKEN else None

    async def logout(self, tenant_id: uuid.UUID, token: str) -> None:
        return None


def _client(
    stub: StubPortalService | None = None, *, host: str = "bella.localtest.me"
) -> tuple[TestClient, StubPortalService]:
    async def _resolver(slug: str) -> TenantContext | None:
        return TENANT if slug == "bella" else None

    app = create_app(resolver=_resolver)
    service = stub if stub is not None else StubPortalService()
    app.state.portal_service = service
    auth = FakeAuthService()
    app.state.auth_service = auth
    app.dependency_overrides[get_auth_service] = lambda: auth
    return TestClient(app, base_url=f"http://{host}"), service


# --- the mint ---------------------------------------------------------------


def test_the_mint_is_anonymous_and_sets_the_customer_cookie() -> None:
    client, stub = _client()
    with client:
        assert client.cookies == {}
        resp = client.post(SESSION, json={"phone": PHONE, "verification_token": VERIFICATION_TOKEN})
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"customer_name": "רותם"}
    assert [name for name, _ in stub.calls] == ["create_session"]
    cookie = resp.headers["set-cookie"]
    assert cookie.startswith(f"{CUSTOMER_SESSION_COOKIE}=")
    # HttpOnly (no JS theft), SameSite=Lax (CSRF, with CsrfOriginMiddleware),
    # path=/ and NO Domain attribute — host-only, so a session minted on
    # boutique A is never sent to boutique B's subdomain.
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/" in cookie
    assert "Domain=" not in cookie
    # dev settings: Secure is off locally, on everywhere else.
    assert "Secure" not in cookie


def test_the_mint_cookie_carries_the_portal_ttl_not_the_staff_one() -> None:
    """30 days, deliberately longer than the staff 12h (spec D2): every
    re-login costs the tenant a real SMS, so a short TTL is a recurring bill."""
    from app.core.config import get_settings

    client, _ = _client()
    with client:
        resp = client.post(SESSION, json={"phone": PHONE, "verification_token": VERIFICATION_TOKEN})
    settings = get_settings()
    assert settings.portal_session_ttl_seconds == 30 * 24 * 3600
    assert settings.portal_session_ttl_seconds != settings.session_ttl_seconds
    assert f"Max-Age={settings.portal_session_ttl_seconds}" in resp.headers["set-cookie"]


def test_an_unknown_phone_is_the_portal_no_bookings_code() -> None:
    """Not an oracle: she just proved possession of the number, so «this phone
    has no bookings here» discloses only her own data (spec D1). Its own code
    rather than the house 404 because the login panel renders a state off it."""
    client, _ = _client(StubPortalService(error=PortalNoBookingsError()))
    with client:
        resp = client.post(SESSION, json={"phone": PHONE, "verification_token": VERIFICATION_TOKEN})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "PORTAL_NO_BOOKINGS"
    assert "set-cookie" not in resp.headers


def test_the_mint_brake_is_the_shared_too_many_attempts_body() -> None:
    client, _ = _client(StubPortalService(error=PortalThrottledError()))
    with client:
        resp = client.post(SESSION, json={"phone": PHONE, "verification_token": VERIFICATION_TOKEN})
    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "TOO_MANY_ATTEMPTS"


def test_the_mint_refuses_an_unknown_field() -> None:
    """ForbidExtra: a field the schema silently dropped is the shape that lets a
    caller believe it sent something."""
    client, _ = _client()
    with client:
        resp = client.post(
            SESSION,
            json={"phone": PHONE, "verification_token": VERIFICATION_TOKEN, "name": "רותם"},
        )
    assert resp.status_code == 400


# --- the auth matrix --------------------------------------------------------


@pytest.mark.parametrize(("method", "path", "body"), COOKIE_ROUTES)
def test_a_cookie_authed_route_is_401_without_a_cookie(
    method: str, path: str, body: dict[str, Any] | None
) -> None:
    client, _ = _client()
    with client:
        resp = client.request(method, path, json=body)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "NOT_AUTHENTICATED"


@pytest.mark.parametrize(("method", "path", "body"), COOKIE_ROUTES)
def test_a_cookie_authed_route_is_401_with_a_garbage_cookie(
    method: str, path: str, body: dict[str, Any] | None
) -> None:
    """One body whether the cookie is missing, expired, revoked or another
    tenant's — the `NotAuthenticatedError` contract the staff side already
    holds."""
    client, _ = _client()
    with client:
        client.cookies.set(CUSTOMER_SESSION_COOKIE, "not-a-real-token")
        resp = client.request(method, path, json=body)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "NOT_AUTHENTICATED"


@pytest.mark.parametrize(("method", "path", "body"), COOKIE_ROUTES)
def test_a_staff_cookie_is_not_a_portal_credential(
    method: str, path: str, body: dict[str, Any] | None
) -> None:
    """The whole reason the cookie has its own name. An owner signed into the
    console must not be silently logged into the portal of her own boutique."""
    client, _ = _client()
    with client:
        client.cookies.set(SESSION_COOKIE, STAFF_SESSION_TOKEN)
        resp = client.request(method, path, json=body)
    assert resp.status_code == 401


def test_a_portal_cookie_is_not_a_staff_credential() -> None:
    """The mirror direction, asserted on a real /manage route: a live customer
    session must never resolve a console principal."""
    client, _ = _client()
    with client:
        client.cookies.set(CUSTOMER_SESSION_COOKIE, PORTAL_TOKEN)
        resp = client.get("/manage/auth/me")
    assert resp.status_code == 401


def test_me_answers_the_session_customers_name() -> None:
    client, _ = _client()
    with client:
        client.cookies.set(CUSTOMER_SESSION_COOKIE, PORTAL_TOKEN)
        resp = client.get(ME)
    assert resp.status_code == 200
    assert resp.json() == {"customer_name": "רותם"}


def test_logout_revokes_and_clears_the_cookie() -> None:
    client, stub = _client()
    with client:
        client.cookies.set(CUSTOMER_SESSION_COOKIE, PORTAL_TOKEN)
        resp = client.post(LOGOUT)
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert stub.calls == [("logout", (TENANT.id, PORTAL_TOKEN))]
    cleared = resp.headers["set-cookie"]
    assert cleared.startswith(f"{CUSTOMER_SESSION_COOKIE}=")
    assert "Max-Age=0" in cleared or "expires=Thu, 01 Jan 1970" in cleared.lower()


# --- the shared posture -----------------------------------------------------


@pytest.mark.parametrize(("method", "path"), [("POST", SESSION), ("GET", ME), ("POST", LOGOUT)])
def test_every_portal_route_is_never_cached(method: str, path: str) -> None:
    """Every body here names a real person's appointments, and the flow runs on
    a phone where bfcache is the default."""
    client, _ = _client()
    with client:
        client.cookies.set(CUSTOMER_SESSION_COOKIE, PORTAL_TOKEN)
        resp = client.request(
            method, path, json={"phone": PHONE, "verification_token": VERIFICATION_TOKEN}
        )
    assert resp.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(("method", "path"), [("POST", SESSION), ("GET", ME), ("POST", LOGOUT)])
def test_every_portal_route_carries_the_security_headers(method: str, path: str) -> None:
    client, _ = _client()
    with client:
        client.cookies.set(CUSTOMER_SESSION_COOKIE, PORTAL_TOKEN)
        resp = client.request(
            method, path, json={"phone": PHONE, "verification_token": VERIFICATION_TOKEN}
        )
    assert {header: resp.headers.get(header) for header in SECURITY_HEADERS} == SECURITY_HEADERS


@pytest.mark.parametrize(("method", "path"), [("POST", SESSION), ("GET", ME), ("POST", LOGOUT)])
def test_unknown_host_is_tenant_not_found(method: str, path: str) -> None:
    """Public is not host-agnostic: an unresolvable host 404s before any
    tenant-scoped handler runs, so a cookie cannot be probed against 'no
    tenant'."""
    client, _ = _client(host="nosuch.localtest.me")
    with client:
        client.cookies.set(CUSTOMER_SESSION_COOKIE, PORTAL_TOKEN)
        resp = client.request(
            method, path, json={"phone": PHONE, "verification_token": VERIFICATION_TOKEN}
        )
    assert resp.status_code == 404


def test_the_portal_lives_under_the_storefront_prefix() -> None:
    """Spec D7: no new top-level API family. A `/portal` prefix would need a
    vite proxy entry, an SPA-fallback exclusion and a CSRF review, for nothing —
    and `_RESERVED_SEGMENTS` would have to grow a third member."""
    from app.main import _RESERVED_SEGMENTS

    assert frozenset({"manage", "storefront"}) == _RESERVED_SEGMENTS
    for path in (SESSION, ME, LOGOUT):
        assert path.startswith("/storefront/portal/")
