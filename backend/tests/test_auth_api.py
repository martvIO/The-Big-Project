import time
import uuid

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_auth_service
from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.service import InvalidCredentialsError, StaffContext
from app.core.config import Settings
from app.main import create_app
from app.tenancy.middleware import TenantContext

TENANT = TenantContext(id=uuid.uuid4(), slug="bella", name="Bella Bridal", settings={})


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


def test_the_session_cookie_is_secure_outside_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    """F21 B5 / row R15. `test_login_sets_host_only_httponly_cookie` above checks
    `HttpOnly`, `SameSite=Lax` and the absence of `Domain=` and stops there. The
    fourth flag was never asserted, and it is the one that decides whether the
    session survives a hostile network: without `Secure` a downgrade to http on
    any subdomain of the boutique replays the cookie in cleartext.

    Driven end to end rather than off `Settings.secure_cookies` alone — the
    property row 15 audits is what the browser receives, and a config flag nobody
    passes to `set_cookie` reads exactly the same in a unit test.

    Mutation-checked: making `secure_cookies` return True unconditionally
    (`config.py:243-245`) reds the dev leg; returning False unconditionally reds
    the staging and production legs.
    """
    for env, expected in (("dev", False), ("staging", True), ("production", True)):
        extra: dict[str, str] = (
            {}
            if env == "dev"
            else {"database_url": "postgresql+asyncpg://u:p@h/db", "base_domain": "example.com"}
        )
        settings = Settings(app_env=env, **extra)  # type: ignore[arg-type]
        monkeypatch.setattr("app.auth.router.get_settings", lambda s=settings: s)

        fake = FakeAuthService()
        with _app(fake) as client:
            resp = client.post(
                "/manage/auth/login", json={"email": "owner@bella.example", "password": "correct"}
            )
        assert resp.status_code == 200, env
        set_cookie = resp.headers["set-cookie"].lower()
        assert "boutique_session=" in set_cookie
        assert ("secure" in set_cookie) is expected, f"{env}: secure flag should be {expected}"
