import time
import uuid

from fastapi.testclient import TestClient

from app.auth.dependencies import get_auth_service
from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.service import InvalidCredentialsError, StaffContext
from app.main import create_app
from app.tenancy.middleware import TenantContext

TENANT = TenantContext(id=uuid.uuid4(), slug="bella", settings={})


class FakeAuthService:
    def __init__(self) -> None:
        self.password = "correct"
        self.staff = StaffContext(
            id=uuid.uuid4(),
            tenant_id=TENANT.id,
            email="owner@bella.example",
            display_name="Owner",
            role="owner",
        )
        self.token = "session-token-abc"

    async def login(
        self, tenant_id: uuid.UUID, email: str, password: str
    ) -> tuple[StaffContext, str]:
        if password != self.password:
            raise InvalidCredentialsError
        return self.staff, self.token

    async def resolve_session(self, tenant_id: uuid.UUID, token: str) -> StaffContext | None:
        return self.staff if token == self.token else None

    async def logout(self, tenant_id: uuid.UUID, token: str) -> None:
        return None


def _app(fake: FakeAuthService) -> "TestClient":
    async def _resolver(slug: str) -> TenantContext | None:
        return TENANT if slug == "bella" else None

    app = create_app(resolver=_resolver)
    app.state.auth_service = fake
    app.state.login_rate_limiter = FixedWindowRateLimiter(
        max_attempts=3, window_seconds=900, clock=time.monotonic
    )
    app.dependency_overrides[get_auth_service] = lambda: fake
    return TestClient(app, base_url="http://bella.localtest.me")


def test_login_sets_host_only_httponly_cookie() -> None:
    fake = FakeAuthService()
    with _app(fake) as client:
        resp = client.post(
            "/manage/auth/login", json={"email": "owner@bella.example", "password": "correct"}
        )
    assert resp.status_code == 200
    assert resp.json()["email"] == "owner@bella.example"
    set_cookie = resp.headers["set-cookie"].lower()
    assert "boutique_session=" in set_cookie
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie
    assert "domain=" not in set_cookie  # host-only


def test_wrong_password_is_generic_401() -> None:
    fake = FakeAuthService()
    with _app(fake) as client:
        resp = client.post(
            "/manage/auth/login", json={"email": "owner@bella.example", "password": "nope"}
        )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert "set-cookie" not in resp.headers


def test_me_requires_session_cookie() -> None:
    fake = FakeAuthService()
    with _app(fake) as client:
        assert client.get("/manage/auth/me").status_code == 401
        client.cookies.set("boutique_session", fake.token, domain="bella.localtest.me")
        resp = client.get("/manage/auth/me")
    assert resp.status_code == 200
    assert resp.json()["role"] == "owner"


def test_rate_limit_returns_429_after_threshold() -> None:
    fake = FakeAuthService()
    with _app(fake) as client:
        codes = [
            client.post(
                "/manage/auth/login",
                json={"email": "owner@bella.example", "password": "nope"},
            ).status_code
            for _ in range(4)
        ]
    assert codes[:3] == [401, 401, 401]
    assert codes[3] == 429


def test_unknown_tenant_host_is_404_before_auth() -> None:
    fake = FakeAuthService()

    async def _no_tenant(slug: str) -> TenantContext | None:
        return None

    app = create_app(resolver=_no_tenant)
    app.state.auth_service = fake
    app.state.login_rate_limiter = FixedWindowRateLimiter(
        max_attempts=3, window_seconds=900, clock=time.monotonic
    )
    with TestClient(app, base_url="http://ghost.localtest.me") as client:
        resp = client.post("/manage/auth/login", json={"email": "x@y.z", "password": "p"})
    assert resp.status_code == 404
