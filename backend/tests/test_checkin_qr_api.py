"""F33's `/manage` half: route wiring, the 401, both roles, the generic 403, the
host-derived slug and the two assertions that keep the printed poster from being
an empty square.

The `test_dashboard_api.py` shape — a hardcoded TenantContext resolver, a
FakeAuthService, no database — with one deliberate difference: the service on
`app.state` is the REAL `CheckinQrService`, not a fake.

That is the whole point of the trust-path test below.
A fake could only record the slug it was handed; the real service constructed
with a base_domain that DISAGREES with the request host is what makes an
origin-derived composition — the shape a frontend implementation would have had
to use — visibly wrong. `CheckinQrService` needs no session factory, no limiter
and no clock, so there is nothing to stub.
"""

import time
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_auth_service
from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.service import StaffContext
from app.main import NOT_AUTHORIZED_BODY, create_app
from app.models.constants import StaffRole
from app.queue.qr import CheckinQrService
from app.tenancy.middleware import TenantContext

TENANT = TenantContext(id=uuid.uuid4(), slug="bella", name="Bella Bridal", settings={})
OTHER_TENANT = TenantContext(id=uuid.uuid4(), slug="vered", name="Vered", settings={})
STAFF_ID = uuid.uuid4()
TOKEN = "session-token-abc"
PATH = "/manage/checkin-qr"

# DELIBERATELY not the host suffix the TestClient uses. A URL composed from
# window.location.origin — or from the request's own Host — would answer
# `bella.localtest.me`, and this is what tells the two apart.
BASE_DOMAIN = "modryn.co.il"

SVG_NAMESPACE = 'xmlns="http://www.w3.org/2000/svg"'

# One row — and EIGHT routers now mount prefix="/manage" (auth at
# /manage/auth, boutique, catalog, owner-booking, staff, dashboard, floor,
# gateway, and this one). A duplicated (method, path) silently wins or loses on
# include order with no error, so this table is the wiring guard and the 404 in
# the walk below is what catches a shadow.
ROUTES: list[tuple[str, str, dict[str, Any] | None]] = [("GET", PATH, None)]

# Two rows. The route takes no input, so there is nothing to 400 on, and it
# reads no row, so there is nothing to 404 on: the answer is a pure function of
# the tenant's own slug and always exists.
#
# CSRF_ORIGIN_MISMATCH is deliberately ABSENT: CsrfOriginMiddleware fences
# MUTATING_METHODS only (`csrf.py:48`) and this is a GET.
SPEC_ERROR_CODES = {"NOT_AUTHENTICATED", "NOT_AUTHORIZED"}

# Kept in step with test_staff_role_gating.UNKNOWN_ROLE, which owns the tripwire
# asserting it never becomes a real StaffRole.
UNKNOWN_ROLE = "no-such-role"


class FakeAuthService:
    def __init__(self, role: str = StaffRole.OWNER.value) -> None:
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


def _client(
    *, authed: bool = True, role: str = StaffRole.OWNER.value, host: str = "bella"
) -> TestClient:
    async def _resolver(slug: str) -> TenantContext | None:
        return {"bella": TENANT, "vered": OTHER_TENANT}.get(slug)

    app = create_app(resolver=_resolver)
    auth = FakeAuthService(role)
    app.state.auth_service = auth
    app.state.login_rate_limiter = FixedWindowRateLimiter(
        max_attempts=3, window_seconds=900, clock=time.monotonic
    )
    app.state.checkin_qr_service = CheckinQrService(base_domain=BASE_DOMAIN)
    app.dependency_overrides[get_auth_service] = lambda: auth
    client = TestClient(app, base_url=f"http://{host}.localtest.me")
    if authed:
        client.cookies.set("boutique_session", TOKEN, domain=f"{host}.localtest.me")
    return client


# --- wiring, authentication and the role gate ---


def test_every_route_requires_authentication() -> None:
    with _client(authed=False) as client:
        for method, path, body in ROUTES:
            resp = client.request(method, path, json=body)
            assert resp.status_code == 401, f"{method} {path} → {resp.status_code}"
            assert resp.json()["error"]["code"] == "NOT_AUTHENTICATED"


def test_every_route_is_wired_and_answers() -> None:
    """Eight routers now mount prefix="/manage": a path collision would silently
    shadow, and a 404 here is what catches it."""
    for method, path, body in ROUTES:
        with _client() as client:
            resp = client.request(method, path, json=body)
        assert resp.status_code == 200, f"{method} {path} → {resp.status_code} {resp.text}"


@pytest.mark.parametrize("role", [StaffRole.OWNER.value, StaffRole.SHIFT_MANAGER.value])
def test_both_roles_get_the_same_qr(role: str) -> None:
    """BOTH roles, asserted rather than assumed. The payload is a public URL and
    a picture of it — the same URL printed on a sign in the window that anyone
    in the shop can read — so locking a shift manager out of reprinting a torn
    poster is a support ticket for no security gain.

    The mechanical consequence is `test_staff_role_gating.py`: this route's
    (method, path) must NOT join its OWNER_ONLY set, or the walker reports it as
    `unenforced_owner_only`.
    """
    with _client(role=role) as client:
        resp = client.get(PATH)
    assert resp.status_code == 200
    assert resp.json()["checkin_url"] == f"https://bella.{BASE_DOMAIN}/checkin"


def test_an_unknown_role_is_refused_with_the_exact_generic_body() -> None:
    with _client(role=UNKNOWN_ROLE) as client:
        resp = client.get(PATH)
    assert resp.status_code == 403
    assert resp.json() == NOT_AUTHORIZED_BODY


@pytest.mark.parametrize(("method", "path", "body"), ROUTES, ids=[f"{m}-{p}" for m, p, _ in ROUTES])
def test_no_qr_response_is_cached(method: str, path: str, body: dict[str, Any] | None) -> None:
    """Router-level `_no_store`. The payload names the boutique's own subdomain,
    and this console runs on shared shop-floor tablets."""
    with _client() as client:
        resp = client.request(method, path, json=body)
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "no-store"


# --- the trust path ---


def test_the_url_takes_its_slug_from_the_host_and_its_domain_from_the_injection() -> None:
    """Two hosts, two URLs — and neither carries the request's own domain.

    `slug` appears nowhere in `apps/manage` and `GET /manage/settings` does not
    return it, so a client-side composition would have to guess from
    `window.location.origin`: correct today only because the console is
    same-origin with the storefront, and silently wrong the day it is not. This
    assertion is what would fail on that day.
    """
    with _client(host="bella") as client:
        bella = client.get(PATH).json()["checkin_url"]
    with _client(host="vered") as client:
        vered = client.get(PATH).json()["checkin_url"]

    assert bella == f"https://bella.{BASE_DOMAIN}/checkin"
    assert vered == f"https://vered.{BASE_DOMAIN}/checkin"
    assert "localtest.me" not in bella  # not the request's own host


# --- the payload ---


def test_the_response_is_json_and_the_svg_is_renderable_through_a_data_uri() -> None:
    """`starts with <svg` AND `contains xmlns` — and the second half is the one
    that matters. segno's `svg_inline()` satisfies the first and emits no
    namespace, which renders BLANK through a `data:` URI: a green suite and an
    empty square on a printed poster.
    """
    with _client() as client:
        resp = client.get(PATH)
    assert resp.headers["content-type"].startswith("application/json")
    body = resp.json()
    assert set(body) == {"checkin_url", "qr_svg"}
    assert body["qr_svg"].startswith("<svg")
    assert SVG_NAMESPACE in body["qr_svg"]


# --- the error table ---


def test_every_spec_error_code_is_asserted() -> None:
    """The two the route can produce, and no third. CSRF_ORIGIN_MISMATCH is
    absent on purpose — a GET is not fenced by CsrfOriginMiddleware."""
    assert {"NOT_AUTHENTICATED", "NOT_AUTHORIZED"} == SPEC_ERROR_CODES


def test_a_qr_read_with_a_mismatched_origin_is_allowed() -> None:
    """The leg the CSRF claim actually rests on, rather than an assertion
    against a code this route cannot produce."""
    with _client() as client:
        resp = client.get(PATH, headers={"origin": "https://evil.example"})
    assert resp.status_code == 200
