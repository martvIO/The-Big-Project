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

from app.auth.dependencies import (
    NotAuthorizedError,
    get_auth_service,
    require_role,
)
from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.service import StaffContext
from app.main import NOT_AUTHORIZED_BODY, create_app
from app.models.constants import StaffRole
from app.tenancy.middleware import TenantContext

TERMS_PUBLISH = ("POST", "/manage/terms")

# The routes a shift_manager must NOT reach — the spec's permission matrix,
# pinned. F51's staff router adds its rows here; adding an owner-only
# tightening anywhere else fails test_route_table_matches_the_permission_matrix,
# so narrowing the shift manager's surface stays a deliberate, reviewed act.
OWNER_ONLY = {TERMS_PUBLISH}

# The ONLY /manage routes allowed to carry no RoleGate: login is anonymous by
# definition; logout and me are any-authenticated-staff. Everything else must
# refuse or admit each role deliberately. Pinned so pruning a route here is a
# visible act.
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
        f"OWNER_ONLY routes with no gate excluding shift_manager: "
        f"{sorted(unenforced_owner_only)}"
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
            await gate(_staff("reception"))


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

    async def resolve_session(self, tenant_id: uuid.UUID, token: str) -> StaffContext | None:
        self.resolve_calls += 1
        return await super().resolve_session(tenant_id, token)


def _client(
    fake: FakeBoutiqueService, role: str, *, authed: bool = True
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
    client = TestClient(app, base_url="http://bella.localtest.me")
    if authed:
        client.cookies.set("boutique_session", TOKEN, domain="bella.localtest.me")
    return client, auth


def test_shift_manager_is_admitted_everywhere_except_terms_publishing() -> None:
    fake = FakeBoutiqueService()
    client, _ = _client(fake, "shift_manager")
    with client:
        for method, path, body in ROUTES:
            resp = client.request(method, path, json=body)
            if (method, path) in OWNER_ONLY:
                assert resp.status_code == 403, (method, path, resp.text)
                # The FULL body, not just the code: the generic message is a
                # stated invariant (no role names on the wire), and F15's rebase
                # carries a same-named constant with a role-naming message —
                # this assertion is what makes that merge resolution fail loudly.
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
    client, _ = _client(fake, "reception")
    with client:
        for method, path, body in [*ROUTES, *CATALOG_ROUTES]:
            resp = client.request(method, path, json=body)
            assert resp.status_code == 403, (method, path, resp.text)
            assert resp.json() == NOT_AUTHORIZED_BODY


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
