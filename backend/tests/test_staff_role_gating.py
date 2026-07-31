"""F31 fast tests: the default-deny role walker, the admitted-set policy test,
the RoleGate unit matrix, and an HTTP matrix proving the wiring — shift_manager
admitted on every /manage route except the OWNER_ONLY set. Fake services +
hardcoded TenantContext resolver, no database (test_boutique_api.py style).

Coverage split: the structural tests derive from the LIVE route table, so every
/manage route — present and future — is policy-checked without a fake; the HTTP
matrix reuses the hand-maintained ROUTES tables of test_boutique_api and
test_catalog_api, so it covers exactly what those modules cover."""

import time
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from test_boutique_api import (
    ROUTES,
    TENANT,
    TERMS_BODY,
    TOKEN,
    FakeAuthService,
    FakeBoutiqueService,
)
from test_catalog_api import ROUTES as CATALOG_ROUTES
from test_catalog_api import FakeCatalogService
from test_payments_api import ROUTES as GATEWAY_ROUTES

from app.auth.dependencies import (
    NotAuthorizedError,
    get_auth_service,
    require_role,
)
from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.service import StaffContext
from app.catalog.router import get_media_storage
from app.csrf import CSRF_ORIGIN_MISMATCH_BODY
from app.main import NOT_AUTHORIZED_BODY, create_app
from app.models.constants import StaffRole
from app.storage.memory import InMemoryMediaStorage
from app.tenancy.middleware import TenantContext

TERMS_PUBLISH = ("POST", "/manage/terms")

# Spelled as ROUTE-TABLE TEMPLATES, not concrete URLs: the walkers below read
# route.path, so a literal /manage/staff/<uuid> would never match and
# test_route_table_matches_the_permission_matrix would red-fail with "routes lock
# shift_manager out but are not in OWNER_ONLY".
STAFF_LIST = ("GET", "/manage/staff")
STAFF_CREATE = ("POST", "/manage/staff")
STAFF_PATCH = ("PATCH", "/manage/staff/{staff_id}")
STAFF_DELETE = ("DELETE", "/manage/staff/{staff_id}")

# F17's four. The first router in the repo that is owner-only IN FULL (D13): a
# shift manager has no relationship to the boutique's merchant account, and the
# READ itself discloses whether the business can take money — which is why even
# GET is here.
GATEWAY_GET = ("GET", "/manage/gateway")
GATEWAY_SET = ("PUT", "/manage/gateway/credentials")
GATEWAY_VALIDATE = ("POST", "/manage/gateway/validate")
GATEWAY_DISCONNECT = ("DELETE", "/manage/gateway/credentials")

# The routes a shift_manager must NOT reach — the spec's permission matrix,
# pinned. F51's staff router added its four rows and F17's gateway router adds
# these four; adding an owner-only tightening anywhere else fails
# test_route_table_matches_the_permission_matrix, so narrowing the shift
# manager's surface stays a deliberate, reviewed act.
OWNER_ONLY = {
    TERMS_PUBLISH,
    STAFF_LIST,
    STAFF_CREATE,
    STAFF_PATCH,
    STAFF_DELETE,
    GATEWAY_GET,
    GATEWAY_SET,
    GATEWAY_VALIDATE,
    GATEWAY_DISCONNECT,
}

# The probe for "a role the enum does not know", shared verbatim by
# test_catalog_api and test_migrations. Deliberately NOT 'reception' (or
# seamstress/sales): 0011's comment names those three as the next roles to join
# StaffRole, and the day one of them does, a test using it as the unknown-role
# probe would silently start asserting the opposite of its own name.
UNKNOWN_ROLE = "no-such-role"
# The tripwire that keeps the sentence above true.
assert UNKNOWN_ROLE not in {role.value for role in StaffRole}, (
    "UNKNOWN_ROLE became a real StaffRole — every unknown-role test now asserts "
    "the opposite of its name; pick a new sentinel"
)

# The ONLY /manage routes allowed to carry no RoleGate — and NOT for the same
# reason, which an earlier version of this comment got wrong:
#   POST /manage/auth/login  — anonymous by definition.
#   POST /manage/auth/logout — ANONYMOUS TOO, not "any authenticated staff". It
#       carries no auth dependency at all (app/auth/router.py): with no cookie
#       the revoke is skipped and the caller still gets 200 {"ok": true}. That is
#       deliberate — gating the one action a staffer takes when her session is
#       already broken would 401 it. Pinned by the two logout tests below.
#   GET  /manage/auth/me     — genuinely any-authenticated-staff: get_current_staff
#       with no RoleGate, so it 401s without a session and never 403s with one.
# Everything else must refuse or admit each role deliberately. Pinned so pruning
# a route here is a visible act.
UNGATED_ALLOWLIST = {
    ("POST", "/manage/auth/login"),
    ("POST", "/manage/auth/logout"),
    ("GET", "/manage/auth/me"),
}


async def _null_resolver(slug: str) -> TenantContext | None:
    """No host resolves. Enough to build the app and read its route table."""
    return None


def _leaf_routes(node: Any) -> Iterator[Any]:
    """FastAPI wraps an included router in `_IncludedRouter` rather than
    flattening it — recurse through `original_router` like test_storefront_api,
    or the walker sees only the docs routes and passes vacuously."""
    for route in getattr(node, "routes", []):
        inner = getattr(route, "original_router", None)
        if inner is not None:
            yield from _leaf_routes(inner)
            continue
        yield route


def _gate_role_sets(dependant: Any) -> Iterator[frozenset[str]]:
    """Every RoleGate in the dependency tree, however deep — router-level gates
    and per-route tightenings both surface here via `allowed_roles`."""
    for dep in getattr(dependant, "dependencies", []):
        roles = getattr(dep.call, "allowed_roles", None)
        if roles is not None:
            yield roles
        yield from _gate_role_sets(dep)


# --- default-deny: structural proof over the live route table ---


def test_every_manage_route_is_role_gated() -> None:
    app = create_app(resolver=_null_resolver)
    seen: set[tuple[str, str]] = set()
    ungated: list[tuple[str, str]] = []
    for route in _leaf_routes(app):
        path = getattr(route, "path", None)
        dependant = getattr(route, "dependant", None)
        if path is None or dependant is None or not path.startswith("/manage"):
            continue
        gated = bool(list(_gate_role_sets(dependant)))
        for method in getattr(route, "methods", None) or ():
            seen.add((method, path))
            if (method, path) in UNGATED_ALLOWLIST:
                continue
            if not gated:
                ungated.append((method, path))
    # An empty walk would make this guard vacuous — the storefront suite's
    # derivation lesson applies here too.
    assert seen - UNGATED_ALLOWLIST, "no gated /manage route was discovered — walker is broken"
    assert seen >= UNGATED_ALLOWLIST, "allowlist names a route that no longer exists — prune it"
    assert not ungated, f"role-ungated /manage routes: {sorted(ungated)}"


def test_gates_admit_only_known_roles() -> None:
    # Guards against drift: if RoleGate ever stops normalizing through
    # StaffRole (e.g. frozenset(allowed) instead of .value), a gate built from
    # a stale or removed member would silently lock that role out — this pins
    # every admitted string to the live enum.
    known = {role.value for role in StaffRole}
    app = create_app(resolver=_null_resolver)
    checked = 0
    for route in _leaf_routes(app):
        dependant = getattr(route, "dependant", None)
        if dependant is None:
            continue
        for roles in _gate_role_sets(dependant):
            assert roles, "an empty RoleGate admits nobody"
            assert roles <= known, f"gate admits unknown roles: {roles - known}"
            checked += 1
    assert checked, "no RoleGate was discovered — walker is broken"


def test_route_table_matches_the_permission_matrix() -> None:
    """The spec's matrix, asserted over the LIVE route table: every /manage
    route admits shift_manager unless OWNER_ONLY pins it, and every OWNER_ONLY
    route carries a gate that excludes shift_manager. Catches the mutation the
    walker cannot — a gate that is present and well-formed but admits the wrong
    set (e.g. an accidental owner-only catalog router)."""
    app = create_app(resolver=_null_resolver)
    wrongly_narrowed: list[tuple[str, str]] = []
    unenforced_owner_only: list[tuple[str, str]] = []
    for route in _leaf_routes(app):
        path = getattr(route, "path", None)
        dependant = getattr(route, "dependant", None)
        if path is None or dependant is None or not path.startswith("/manage"):
            continue
        role_sets = list(_gate_role_sets(dependant))
        if not role_sets:
            continue  # ungated routes are the walker test's job
        for method in getattr(route, "methods", None) or ():
            if (method, path) in OWNER_ONLY:
                if not any(StaffRole.SHIFT_MANAGER.value not in roles for roles in role_sets):
                    unenforced_owner_only.append((method, path))
            elif not all(StaffRole.SHIFT_MANAGER.value in roles for roles in role_sets):
                wrongly_narrowed.append((method, path))
    assert not wrongly_narrowed, (
        f"routes lock shift_manager out but are not in OWNER_ONLY: {sorted(wrongly_narrowed)}"
    )
    assert not unenforced_owner_only, (
        f"OWNER_ONLY routes with no gate excluding shift_manager: {sorted(unenforced_owner_only)}"
    )


def test_terms_publishing_is_owner_only_in_the_route_table() -> None:
    app = create_app(resolver=_null_resolver)
    for route in _leaf_routes(app):
        if getattr(route, "path", None) != "/manage/terms":
            continue
        if "POST" not in (getattr(route, "methods", None) or ()):
            continue
        role_sets = list(_gate_role_sets(route.dependant))
        assert frozenset({StaffRole.OWNER.value}) in role_sets, (
            "POST /manage/terms lost its owner-only tightening"
        )
        return
    pytest.fail("POST /manage/terms not found in the route table")


# --- RoleGate unit matrix ---


def _staff(role: str) -> StaffContext:
    return StaffContext(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        email="staff@bella.example",
        display_name="Staff",
        role=role,
    )


async def test_gate_admits_listed_roles() -> None:
    gate = require_role(StaffRole.OWNER, StaffRole.SHIFT_MANAGER)
    for role in ("owner", "shift_manager"):
        staff = _staff(role)
        assert await gate(staff) is staff


async def test_owner_only_gate_refuses_shift_manager() -> None:
    with pytest.raises(NotAuthorizedError):
        await require_role(StaffRole.OWNER)(_staff("shift_manager"))


async def test_unknown_role_fails_closed_on_every_gate_shape() -> None:
    # A role the enum does not know (a future migration slipped in early, a
    # hand-edited row) must be refused, not admitted by accident.
    gates = (
        require_role(StaffRole.OWNER),
        require_role(StaffRole.OWNER, StaffRole.SHIFT_MANAGER),
    )
    for gate in gates:
        with pytest.raises(NotAuthorizedError):
            await gate(_staff(UNKNOWN_ROLE))


# --- HTTP matrix: the wiring, end to end over the boutique ROUTES table ---


class CountingAuthService(FakeAuthService):
    def __init__(self, role: str) -> None:
        super().__init__()
        self.staff = StaffContext(
            id=self.staff.id,
            tenant_id=self.staff.tenant_id,
            email=self.staff.email,
            display_name=self.staff.display_name,
            role=role,
        )
        self.resolve_calls = 0
        self.logout_calls = 0

    async def resolve_session(self, tenant_id: uuid.UUID, token: str) -> StaffContext | None:
        self.resolve_calls += 1
        return await super().resolve_session(tenant_id, token)

    async def logout(self, tenant_id: uuid.UUID, token: str) -> None:
        self.logout_calls += 1
        return await super().logout(tenant_id, token)


def _client(
    fake: FakeBoutiqueService,
    role: str,
    *,
    authed: bool = True,
    catalog: FakeCatalogService | None = None,
) -> tuple[TestClient, CountingAuthService]:
    async def _resolver(slug: str) -> TenantContext | None:
        return TENANT if slug == "bella" else None

    app = create_app(resolver=_resolver)
    auth = CountingAuthService(role)
    app.state.auth_service = auth
    app.state.login_rate_limiter = FixedWindowRateLimiter(
        max_attempts=3, window_seconds=900, clock=time.monotonic
    )
    app.state.boutique_service = fake
    app.dependency_overrides[get_auth_service] = lambda: auth
    if catalog is not None:
        # Wired ONLY when a test needs the catalog surface to answer 2xx. Left
        # unset otherwise on purpose: test_unknown_role_is_403_on_every_gated_route
        # depends on the real (ambient-env) service never being reached, so a
        # decoy gate that carries allowed_roles without raising blows that test up
        # instead of quietly passing.
        app.state.catalog_service = catalog
        app.dependency_overrides[get_media_storage] = lambda: InMemoryMediaStorage()
    client = TestClient(app, base_url="http://bella.localtest.me")
    if authed:
        client.cookies.set("boutique_session", TOKEN, domain="bella.localtest.me")
    return client, auth


def test_shift_manager_is_admitted_everywhere_except_terms_publishing() -> None:
    # ALL THREE route tables, so this is symmetric with the unknown-role walk
    # below: the spec's matrix grants the shift manager the catalog surface, and
    # without the catalog half an accidental owner-only catalog router would only
    # be caught structurally.
    #
    # GATEWAY_ROUTES is here for the opposite reason — all four are in
    # OWNER_ONLY, so this walk is what gives them a real end-to-end 403. Adding
    # the OWNER_ONLY rows alone would silence the structural test while leaving
    # the HTTP wiring unproven, which is exactly the gap this import closes. No
    # gateway fake is wired, deliberately: the gate raises during dependency
    # solving, so reaching the real (unconfigured) service would blow this up
    # rather than quietly pass.
    fake = FakeBoutiqueService()
    client, _ = _client(fake, "shift_manager", catalog=FakeCatalogService())
    with client:
        for method, path, body in [*ROUTES, *CATALOG_ROUTES, *GATEWAY_ROUTES]:
            resp = client.request(method, path, json=body)
            if (method, path) in OWNER_ONLY:
                assert resp.status_code == 403, (method, path, resp.text)
                # The whole body, so every route answers the SAME refusal. Note
                # what this cannot do: both sides are the imported constant, so
                # renaming the code or leaking role names into the message would
                # move them together and pass. The literals are pinned once, in
                # test_the_not_authorized_contract_is_pinned_by_literal.
                assert resp.json() == NOT_AUTHORIZED_BODY
            else:
                assert resp.status_code < 400, (method, path, resp.text)


def test_owner_still_publishes_terms() -> None:
    fake = FakeBoutiqueService()
    client, _ = _client(fake, "owner")
    with client:
        resp = client.post("/manage/terms", json=TERMS_BODY)
        assert resp.status_code == 200, resp.text


def test_unknown_role_is_403_on_every_gated_route() -> None:
    # Catalog routes ride along with only the boutique fake in place: the gate
    # raises during dependency solving, BEFORE any service dependency resolves,
    # so a 403 here proves the catalog gate's __call__ actually enforces — a
    # decoy gate that carries allowed_roles but never raises would fall through
    # to the real (unconfigured) CatalogService and blow the test up.
    fake = FakeBoutiqueService()
    client, _ = _client(fake, UNKNOWN_ROLE)
    with client:
        for method, path, body in [*ROUTES, *CATALOG_ROUTES, *GATEWAY_ROUTES]:
            resp = client.request(method, path, json=body)
            assert resp.status_code == 403, (method, path, resp.text)
            assert resp.json() == NOT_AUTHORIZED_BODY


def test_the_not_authorized_contract_is_pinned_by_literal() -> None:
    """The one test that reads the LITERALS. Every other 403 assertion on this
    branch compares resp.json() against NOT_AUTHORIZED_BODY imported from
    app.main, so both sides move together: renaming the wire code, or leaking
    role names into the message, passes all of them. This is what actually holds
    the contract — and what makes F15's rebase fail loudly if its role-naming
    variant of the same-named constant wins the merge.

    The role-name scan iterates StaffRole rather than listing today's two, so a
    role added later is covered without touching this test. The reason the body
    must stay generic is that naming the required role tells a prober which
    roles exist."""
    fake = FakeBoutiqueService()
    client, _ = _client(fake, StaffRole.SHIFT_MANAGER.value)
    with client:
        resp = client.post("/manage/terms", json=TERMS_BODY)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "NOT_AUTHORIZED"
    assert resp.json()["error"]["message"] == "This action is not available for your account."
    for role in StaffRole:
        assert role.value not in resp.text, f"the 403 body names the role {role.value}"


def test_auth_me_stays_reachable_for_shift_manager() -> None:
    fake = FakeBoutiqueService()
    client, _ = _client(fake, "shift_manager")
    with client:
        resp = client.get("/manage/auth/me")
        assert resp.status_code == 200
        assert resp.json()["role"] == "shift_manager"


def test_gate_does_not_resolve_the_session_twice() -> None:
    # The router gate and the route's own Staff dependency both depend on
    # get_current_staff; FastAPI's per-request dependency cache must collapse
    # them to ONE resolve_session call — the spec's recorded risk.
    fake = FakeBoutiqueService()
    client, auth = _client(fake, "shift_manager")
    with client:
        resp = client.get("/manage/settings")
        assert resp.status_code == 200
    assert auth.resolve_calls == 1


def test_two_gates_on_one_route_still_resolve_the_session_once() -> None:
    """POST /manage/terms carries BOTH the router gate and its own owner-only
    tightening. The test above uses a ONE-gate route, so it cannot see a cache
    miss between two separate RoleGate instances — this one can. Must run as
    owner: a 403 would short-circuit before the second gate ever resolves."""
    fake = FakeBoutiqueService()
    client, auth = _client(fake, "owner")
    with client:
        assert client.post("/manage/terms", json=TERMS_BODY).status_code == 200
    assert auth.resolve_calls == 1


# --- the ungated allowlist, pinned ---


def test_logout_is_reachable_with_no_session_at_all() -> None:
    """Logout carries no auth dependency: an anonymous POST gets 200, nothing is
    resolved, no revoke is attempted, and the cookie is cleared anyway. This is
    the behaviour UNGATED_ALLOWLIST's comment describes."""
    fake = FakeBoutiqueService()
    client, auth = _client(fake, "owner", authed=False)
    with client:
        resp = client.post("/manage/auth/logout")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert auth.resolve_calls == 0
    assert auth.logout_calls == 0
    assert "boutique_session=" in resp.headers["set-cookie"]


def test_logout_revokes_the_session_for_any_role() -> None:
    """The inverse of every gated route: logout admits owner, shift_manager AND a
    role the enum does not know. A RoleGate added here would 403 exactly the
    caller who most needs to get rid of her cookie.

    logout_calls is the load-bearing assertion, not the 200: the route answers
    200 whether or not it revoked anything, so status alone would still pass if
    the revoke were skipped — which is a live risk, because the route reads the
    cookie by hardcoded literal while everything else reads SESSION_COOKIE. A
    rename of that constant leaves a stolen token valid until TTL with the user
    told she logged out."""
    for role in (StaffRole.OWNER.value, StaffRole.SHIFT_MANAGER.value, UNKNOWN_ROLE):
        fake = FakeBoutiqueService()
        client, auth = _client(fake, role)
        with client:
            assert client.post("/manage/auth/logout").status_code == 200, role
        assert auth.logout_calls == 1, role


def test_me_echoes_an_out_of_enum_role_verbatim() -> None:
    """Recorded honestly, both halves: the serializer applies NO allowlist, so
    StaffContext.role reaches the browser exactly as staff_users.role held it.
    What makes that safe is the DATABASE, not this code path — since 0011 no such
    row can exist, and test_migrations.py's app-role UPDATE probe is what keeps
    that true. If a role filter is ever wanted on the wire, this is the test that
    must change."""
    fake = FakeBoutiqueService()
    client, _ = _client(fake, UNKNOWN_ROLE)
    with client:
        resp = client.get("/manage/auth/me")
    assert resp.status_code == 200
    assert resp.json()["role"] == UNKNOWN_ROLE


# --- precedence and the anonymous surface ---


def test_a_forged_origin_beats_the_role_gate_on_the_same_route() -> None:
    """Two different 403s can answer POST /manage/terms. CsrfOriginMiddleware is
    added after the tenant middleware, so it runs BEFORE routing and a forged
    Origin can never surface NOT_AUTHORIZED. resolve_calls is what makes this a
    precedence test rather than two status-code tests: the forged request never
    reached dependency solving at all."""
    fake = FakeBoutiqueService()
    client, auth = _client(fake, "shift_manager")
    with client:
        forged = client.post(
            "/manage/terms", json=TERMS_BODY, headers={"origin": "http://evil.localtest.me"}
        )
        honest = client.post("/manage/terms", json=TERMS_BODY)
    assert forged.status_code == 403
    assert forged.json() == CSRF_ORIGIN_MISMATCH_BODY
    assert honest.status_code == 403
    assert honest.json() == NOT_AUTHORIZED_BODY
    assert auth.resolve_calls == 1
    assert fake.calls == []


def test_no_route_outside_manage_carries_a_role_gate() -> None:
    """The inverse of test_every_manage_route_is_role_gated. /storefront* and
    /health are anonymous by contract; a RoleGate copy-pasted onto one of them
    would refuse the open internet — a dead public page rather than a security
    hole, and the kind of failure no gating test would otherwise notice."""
    app = create_app(resolver=_null_resolver)
    checked = 0
    for route in _leaf_routes(app):
        path = getattr(route, "path", None)
        dependant = getattr(route, "dependant", None)
        if path is None or dependant is None or path.startswith("/manage"):
            continue
        checked += 1
        assert not list(_gate_role_sets(dependant)), f"anonymous route is role-gated: {path}"
    assert checked, "no non-/manage route was discovered — walker is broken"


def test_head_and_options_on_a_gated_route_are_405_before_the_gate() -> None:
    """A framework CHARACTERIZATION test, not a gating test — it cannot fail for
    any gate-related reason, and it is here to record why no gate is needed on
    these two verbs.

    In the locked fastapi 0.139.2, APIRoute.__init__ never calls
    super().__init__(): it calls _populate_api_route_state, which sets
    route.methods = {m.upper() for m in methods} and never reaches Starlette's
    `if "GET" in self.methods: self.methods.add("HEAD")`. So a GET route carries
    methods == {"GET"} exactly, matching returns PARTIAL, and 405 is answered
    before any dependency — gate included — is solved. OPTIONS 405s for the
    simpler reason that no CORS middleware is installed to handle it.

    Backstop, stated precisely because it is only partial: if a FastAPI bump
    restored the HEAD augmentation, GET /manage/auth/me would gain HEAD, which is
    absent from UNGATED_ALLOWLIST, so test_every_manage_route_is_role_gated would
    go red. Nothing catches a new OPTIONS handler that way — a CORS middleware
    added later would flip this test's second assertion instead, which is the
    review such a change deserves."""
    fake = FakeBoutiqueService()
    client, auth = _client(fake, "shift_manager")
    with client:
        assert client.request("HEAD", "/manage/settings").status_code == 405
        assert client.request("OPTIONS", "/manage/settings").status_code == 405
    assert auth.resolve_calls == 0
