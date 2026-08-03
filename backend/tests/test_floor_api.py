"""F57 fast API tests: route wiring, the 401, all five roles, the generic 403,
the host-derived tenant, the CSRF fence and the wire shape — a duck-typed
FakeFloorService on app.state.floor_service plus a hardcoded TenantContext
resolver, no database (test_dashboard_api.py style).

**This is the backend milestone.** It is the first point at which the route, the
role gate, the tenant trust path and the wire shape are exercised end to end with
no Postgres. `test_floor_db.py` runs below the router and swaps nothing, so the
two prove disjoint halves.

`FLOOR_ROUTES` is exported for `test_staff_role_gating.py` — the
`test_payments_api` / `test_catalog_api` precedent — so these three rows get a
real end-to-end 403 assertion rather than only the structural one.
"""

import datetime
import time
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_auth_service
from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.service import StaffContext
from app.errors import DomainNotFoundError
from app.main import NOT_AUTHORIZED_BODY, create_app
from app.models.constants import StaffCardStatus, StaffRole
from app.models.staff_user import StaffUser
from app.tenancy.middleware import TenantContext

TENANT = TenantContext(id=uuid.uuid4(), slug="bella", name="Bella Bridal", settings={})
STAFF_ID = uuid.uuid4()
TARGET_ID = uuid.uuid4()
TOKEN = "session-token-abc"

FLOOR_PATH = "/manage/floor"
START_PATH = f"/manage/floor/staff/{TARGET_ID}/break/start"
END_PATH = f"/manage/floor/staff/{TARGET_ID}/break/end"

BREAK_BEGAN = datetime.datetime(2026, 8, 2, 9, 5, tzinfo=datetime.UTC)

# CONCRETE urls, not templates (plan C4). The structural walker in
# test_staff_role_gating.py reads `route.path` and needs TEMPLATES, so it keeps
# its own FLOOR_OPEN table; these three issue real requests and need real ids.
#
# SEVEN routers now mount prefix="/manage", so a duplicated (method, path) would
# silently win or lose on include order: this table is the wiring guard, and a
# 404 in the walk below is what catches a shadow.
FLOOR_ROUTES: list[tuple[str, str, dict[str, Any] | None]] = [
    ("GET", FLOOR_PATH, None),
    ("POST", START_PATH, None),
    ("POST", END_PATH, None),
]

# The spec's error table, verbatim. NOT_FOUND is the only one a service method
# raises; the other three come from dependency solving or middleware.
#
# ⚠ NO NEW MEMBER. F57 adds no error code — NotAuthorizedError and
# DomainNotFoundError are both reused with their shipped handlers, which is why
# there is no new `except` and no new body in main.py.
SPEC_ERROR_CODES = {
    "NOT_AUTHENTICATED",
    "NOT_AUTHORIZED",
    "NOT_FOUND",
    "CSRF_ORIGIN_MISMATCH",
}

# Kept in step with test_staff_role_gating.UNKNOWN_ROLE, which owns the tripwire
# asserting it never becomes a real StaffRole.
UNKNOWN_ROLE = "no-such-role"

ALL_ROLES = [role.value for role in StaffRole]


def _staff_user(
    staff_id: uuid.UUID,
    *,
    display_name: str = "נועה לוי",
    role: str = StaffRole.RECEPTION.value,
    break_started_at: datetime.datetime | None = None,
) -> StaffUser:
    row = StaffUser(
        tenant_id=TENANT.id,
        email="staff@bella.example",
        password_hash="not-a-real-hash",
        display_name=display_name,
        role=role,
    )
    row.id = staff_id
    row.break_started_at = break_started_at
    return row


class FakeAuthService:
    def __init__(
        self, role: str = StaffRole.OWNER.value, staff_id: uuid.UUID | None = None
    ) -> None:
        # The session's tenant_id DELIBERATELY disagrees with the host-resolved
        # TENANT.id, so a handler reaching for StaffContext.tenant_id is
        # distinguishable from a correct one (test_dashboard_api.py's reason).
        self.staff = StaffContext(
            id=staff_id or STAFF_ID,
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


class FakeFloorService:
    """Duck-typed FloorService: records what it was called with and answers rows.

    It does NOT re-implement the authorization rule — that is
    test_floor_service.py's, against the real one. What this fake exists to prove
    is that the ROUTER hands the service the host-resolved tenant, the path's
    target id and the SESSION's actor, in that shape.
    """

    def __init__(self, *, missing: bool = False) -> None:
        self.floor_calls: list[uuid.UUID] = []
        self.toggle_calls: list[dict[str, Any]] = []
        self.missing = missing

    async def floor(self, tenant_id: uuid.UUID) -> list[StaffUser]:
        self.floor_calls.append(tenant_id)
        return [
            _staff_user(STAFF_ID, display_name="דנה כהן", role=StaffRole.OWNER.value),
            _staff_user(
                TARGET_ID,
                display_name="נועה לוי",
                role=StaffRole.SEAMSTRESS.value,
                break_started_at=BREAK_BEGAN,
            ),
        ]

    async def start_break(
        self, tenant_id: uuid.UUID, staff_id: uuid.UUID, *, actor: StaffContext
    ) -> StaffUser:
        return self._toggle("start", tenant_id, staff_id, actor, BREAK_BEGAN)

    async def end_break(
        self, tenant_id: uuid.UUID, staff_id: uuid.UUID, *, actor: StaffContext
    ) -> StaffUser:
        return self._toggle("end", tenant_id, staff_id, actor, None)

    def _toggle(
        self,
        verb: str,
        tenant_id: uuid.UUID,
        staff_id: uuid.UUID,
        actor: StaffContext,
        began: datetime.datetime | None,
    ) -> StaffUser:
        self.toggle_calls.append(
            {"verb": verb, "tenant_id": tenant_id, "staff_id": staff_id, "actor_id": actor.id}
        )
        if self.missing:
            raise DomainNotFoundError("staff_user")
        return _staff_user(staff_id, role=StaffRole.SEAMSTRESS.value, break_started_at=began)


def _client(
    fake: FakeFloorService,
    *,
    authed: bool = True,
    role: str = StaffRole.OWNER.value,
    staff_id: uuid.UUID | None = None,
) -> TestClient:
    async def _resolver(slug: str) -> TenantContext | None:
        return TENANT if slug == "bella" else None

    app = create_app(resolver=_resolver)
    auth = FakeAuthService(role, staff_id)
    app.state.auth_service = auth
    app.state.login_rate_limiter = FixedWindowRateLimiter(
        max_attempts=3, window_seconds=900, clock=time.monotonic
    )
    # app.state, not dependency_overrides: get_floor_service reads app.state
    # directly, the way every other console dependency does.
    app.state.floor_service = fake
    app.dependency_overrides[get_auth_service] = lambda: auth
    client = TestClient(app, base_url="http://bella.localtest.me")
    if authed:
        client.cookies.set("boutique_session", TOKEN, domain="bella.localtest.me")
    return client


# --- wiring, authentication and the role gate ---


def test_every_route_requires_authentication() -> None:
    fake = FakeFloorService()
    with _client(fake, authed=False) as client:
        for method, path, body in FLOOR_ROUTES:
            resp = client.request(method, path, json=body)
            assert resp.status_code == 401, f"{method} {path} → {resp.status_code}"
            assert resp.json()["error"]["code"] == "NOT_AUTHENTICATED"
    assert fake.floor_calls == []
    assert fake.toggle_calls == []


def test_every_route_is_wired_and_reaches_the_service() -> None:
    """SEVEN routers now mount prefix="/manage": a path collision would silently
    shadow, and a 404 here is what catches it."""
    for method, path, body in FLOOR_ROUTES:
        fake = FakeFloorService()
        with _client(fake) as client:
            resp = client.request(method, path, json=body)
        assert resp.status_code == 200, f"{method} {path} → {resp.status_code} {resp.text}"
        assert fake.floor_calls or fake.toggle_calls, f"{method} {path} never reached the service"


@pytest.mark.parametrize("role", ALL_ROLES)
def test_all_five_roles_reach_every_floor_route(role: str) -> None:
    """⚠ The ONLY router in the codebase admitting more than two roles, and the
    gate is spelled `require_role(*StaffRole)` so this test covers a sixth role
    the day one is added. The floor payload carries zero customer data, which is
    what makes that safe — plus
    test_the_floor_roles_reach_exactly_the_floor_routes, which pins these three
    roles OUT of every other /manage route.
    """
    for method, path, body in FLOOR_ROUTES:
        fake = FakeFloorService()
        with _client(fake, role=role) as client:
            resp = client.request(method, path, json=body)
        assert resp.status_code == 200, f"{role} {method} {path} → {resp.status_code}"


def test_an_unknown_role_is_refused_with_the_exact_generic_body() -> None:
    """Fails closed even though the gate names every role the product has: a role
    string the enum does not know is still not admitted."""
    for method, path, body in FLOOR_ROUTES:
        fake = FakeFloorService()
        with _client(fake, role=UNKNOWN_ROLE) as client:
            resp = client.request(method, path, json=body)
        assert resp.status_code == 403
        assert resp.json() == NOT_AUTHORIZED_BODY
        assert fake.floor_calls == []
        assert fake.toggle_calls == []


@pytest.mark.parametrize(
    ("method", "path", "body"), FLOOR_ROUTES, ids=[f"{m}-{p}" for m, p, _ in FLOOR_ROUTES]
)
def test_no_floor_response_is_cached(method: str, path: str, body: dict[str, Any] | None) -> None:
    """Router-level `_no_store`, so a route added here later cannot forget it. A
    cached floor in a shared browser would show one boutique's staff to the next
    person who opens it — and a stale card is worse than none on a screen whose
    whole purpose is being current."""
    fake = FakeFloorService()
    with _client(fake) as client:
        resp = client.request(method, path, json=body)
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "no-store"


# --- the trust path ---


def test_every_handler_passes_the_host_resolved_tenant() -> None:
    """`get_current_tenant(request)` is host-derived; StaffContext.tenant_id is
    session-derived. The fake makes them disagree, so a handler reaching for the
    session's id fails here."""
    fake = FakeFloorService()
    with _client(fake) as client:
        assert client.get(FLOOR_PATH).status_code == 200
        assert client.post(START_PATH).status_code == 200
        assert client.post(END_PATH).status_code == 200

    assert fake.floor_calls == [TENANT.id]
    assert [call["tenant_id"] for call in fake.toggle_calls] == [TENANT.id, TENANT.id]


def test_the_target_comes_from_the_path_and_the_actor_from_the_session() -> None:
    """⚠ The two axes must come from DIFFERENT places, and this is where that is
    observable over HTTP. If the handler ever passed the path id as the actor,
    `staff_id == actor.id` would be trivially true and every staffer could toggle
    anybody — the D6 check would still be present and would always pass."""
    fake = FakeFloorService()
    with _client(fake, role=StaffRole.SEAMSTRESS.value) as client:
        assert client.post(START_PATH).status_code == 200

    assert fake.toggle_calls == [
        {"verb": "start", "tenant_id": TENANT.id, "staff_id": TARGET_ID, "actor_id": STAFF_ID}
    ]
    assert TARGET_ID != STAFF_ID


def test_each_toggle_reaches_its_own_service_method() -> None:
    fake = FakeFloorService()
    with _client(fake) as client:
        client.post(START_PATH)
        client.post(END_PATH)
    assert [call["verb"] for call in fake.toggle_calls] == ["start", "end"]


# --- the wire shape ---


def test_the_floor_payload_is_an_envelope_with_one_card_per_live_staffer() -> None:
    """An ENVELOPE, not a bare array: F36 adds rooms and F58 the waitlist to this
    same payload, and a bare array makes the first of them a breaking change."""
    fake = FakeFloorService()
    with _client(fake) as client:
        body = client.get(FLOOR_PATH).json()

    assert body == {
        "staff": [
            {
                "id": str(STAFF_ID),
                "display_name": "דנה כהן",
                "role": "owner",
                "status": "available",
                "break_started_at": None,
            },
            {
                "id": str(TARGET_ID),
                "display_name": "נועה לוי",
                "role": "seamstress",
                "status": "break",
                "break_started_at": BREAK_BEGAN.isoformat().replace("+00:00", "Z"),
            },
        ]
    }


def test_a_toggle_answers_one_card_and_not_the_whole_floor() -> None:
    fake = FakeFloorService()
    with _client(fake) as client:
        body = client.post(START_PATH).json()
    assert set(body) == {"id", "display_name", "role", "status", "break_started_at"}
    assert body["status"] == "break"


def test_no_card_carries_an_email_or_any_credential() -> None:
    """A card is a name, a role and a status. `email` is the key a later reader
    reaches for as a stable identifier — `id` is the key, and the address of
    every member of staff is not something a seamstress needs to see who is on a
    break."""
    fake = FakeFloorService()
    with _client(fake) as client:
        body = client.get(FLOOR_PATH).json()
    keys = {key for card in body["staff"] for key in card}
    assert keys & {"email", "password_hash", "tenant_id", "deleted_at"} == set()


def test_the_card_status_wire_literals_are_exactly_available_and_break() -> None:
    """SET EQUALITY. Fails if `occupied` is pre-added before F36 gives it a
    writer — asserted here as well as in test_floor_service.py because this is
    the module that pins the WIRE."""
    assert {status.value for status in StaffCardStatus} == {"available", "break"}


# --- the error table ---


def test_a_missing_target_is_a_404() -> None:
    fake = FakeFloorService(missing=True)
    with _client(fake) as client:
        for path in (START_PATH, END_PATH):
            resp = client.post(path)
            assert resp.status_code == 404
            assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_a_toggle_with_a_mismatched_origin_is_refused() -> None:
    """Both POSTs ARE fenced — CsrfOriginMiddleware gates on
    `request.method in MUTATING_METHODS` (csrf.py:48)."""
    fake = FakeFloorService()
    with _client(fake) as client:
        for path in (START_PATH, END_PATH):
            resp = client.post(path, headers={"origin": "http://evil.localtest.me"})
            assert resp.status_code == 403
            assert resp.json()["error"]["code"] == "CSRF_ORIGIN_MISMATCH"
    assert fake.toggle_calls == []


def test_the_floor_read_with_a_mismatched_origin_is_allowed() -> None:
    """The GET is NOT fenced, and that asymmetry is asserted rather than assumed:
    CsrfOriginMiddleware fences MUTATING_METHODS only. The protection on the read
    is the session cookie and the role gate, alone."""
    fake = FakeFloorService()
    with _client(fake) as client:
        resp = client.get(FLOOR_PATH, headers={"origin": "http://evil.localtest.me"})
    assert resp.status_code == 200


def test_every_spec_error_code_is_asserted() -> None:
    """Mechanical completeness, re-derived from live responses rather than from a
    literal — and SET EQUALITY, so F57 adding an error code without a test here
    fails immediately."""
    observed = set()
    with _client(FakeFloorService(), authed=False) as client:
        observed.add(client.get(FLOOR_PATH).json()["error"]["code"])
    with _client(FakeFloorService(), role=UNKNOWN_ROLE) as client:
        observed.add(client.get(FLOOR_PATH).json()["error"]["code"])
    with _client(FakeFloorService(missing=True)) as client:
        observed.add(client.post(START_PATH).json()["error"]["code"])
    with _client(FakeFloorService()) as client:
        observed.add(
            client.post(START_PATH, headers={"origin": "http://evil.localtest.me"}).json()["error"][
                "code"
            ]
        )
    assert observed == SPEC_ERROR_CODES
