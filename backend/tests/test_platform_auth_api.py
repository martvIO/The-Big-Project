"""F25 D3/D4 — the operator session, treated adversarially (spec Q49).

Brute force, session theft, host confusion and audit bypass are the test plan
here, not an appendix. This module is the fast half: every assertion runs against
a real `create_app()` with a fake auth service in place of the database one, so
the dependency chain, the limiter, the CSRF prefix and the cookie attributes are
all exercised without Docker. The db-marked half (`test_platform_auth_db.py`)
proves the same surface against real Postgres as the real app role.
"""

import uuid
from collections.abc import Iterator
from http.cookies import SimpleCookie

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response

from app.auth.cookies import SESSION_COOKIE, platform_session_cookie_name
from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.service import InvalidCredentialsError
from app.core.config import Settings
from app.main import create_app
from app.platform.auth import OperatorContext
from app.tenancy.middleware import TenantContext

CONSOLE = "http://admin.localtest.me"
TENANT = "http://bella.localtest.me"

OPERATOR = OperatorContext(
    id=uuid.uuid4(), email="dana@modryn.example", display_name="Dana Operator"
)
GOOD_TOKEN = "a-live-session-token"

# The suite runs with `app_env="dev"`, so `secure_cookies` is False and the name
# has no `__Host-` prefix. The prefixed form is asserted in its own test, driven
# off a non-dev Settings — the prefix is browser-enforced and the browser also
# refuses it without Secure, which dev does not set.
PLATFORM_SESSION_COOKIE = platform_session_cookie_name(secure=False)


class FakeOperatorAuth:
    """Stands in for `OperatorAuthService`. `resolve_session` returns None for
    every token but one — which covers "missing", "garbage", "expired", "revoked"
    and "belongs to a deactivated operator" identically, because the real service
    returns None for all five and the dependency must not distinguish them."""

    def __init__(self) -> None:
        self.logged_out: list[str] = []
        self.attempts: list[tuple[str, str]] = []
        self.password = "op-console-pw"

    async def login(self, email: str, password: str) -> tuple[OperatorContext, str]:
        self.attempts.append((email, password))
        if email != OPERATOR.email or password != self.password:
            raise InvalidCredentialsError
        return OPERATOR, GOOD_TOKEN

    async def resolve_session(self, token: str) -> OperatorContext | None:
        return OPERATOR if token == GOOD_TOKEN else None

    async def logout(self, token: str) -> None:
        self.logged_out.append(token)


async def _resolver(slug: str) -> TenantContext | None:
    if slug == "bella":
        return TenantContext(id=uuid.uuid4(), slug="bella", name="Bella Bridal", settings={})
    return None


def _build_app() -> FastAPI:
    application = create_app(resolver=_resolver)
    application.state.platform_auth_service = FakeOperatorAuth()
    return application


@pytest.fixture
def app() -> Iterator[FastAPI]:
    yield _build_app()


def _fake(app: FastAPI) -> FakeOperatorAuth:
    service: FakeOperatorAuth = app.state.platform_auth_service
    return service


def _console(app: FastAPI) -> TestClient:
    return TestClient(app, base_url=CONSOLE)


# --- the dependency matrix ---------------------------------------------------


def test_me_needs_a_live_cookie_and_says_nothing_about_why_it_refused(app: FastAPI) -> None:
    """One body for missing, malformed, expired, revoked and deactivated — the
    401 must not be an oracle for "that token existed once"."""
    bodies = []
    with _console(app) as client:
        assert client.get("/platform/auth/me").status_code == 401
        bodies.append(client.get("/platform/auth/me").json())
        client.cookies.set(PLATFORM_SESSION_COOKIE, "not-a-real-token", domain="admin.localtest.me")
        resp = client.get("/platform/auth/me")
        assert resp.status_code == 401
        bodies.append(resp.json())
    assert bodies[0] == bodies[1]
    assert bodies[0]["error"]["code"] == "NOT_AUTHENTICATED"


def test_a_live_cookie_reaches_me(app: FastAPI) -> None:
    with _console(app) as client:
        client.cookies.set(PLATFORM_SESSION_COOKIE, GOOD_TOKEN, domain="admin.localtest.me")
        resp = client.get("/platform/auth/me")
    assert resp.status_code == 200
    # ⚠ base_domain IS PART OF THIS RESPONSE. The console composes every address
    # it shows from it; before F26 it rebuilt them from a hardcoded
    # "modryn.co.il", which is wrong in dev and in any domain migration. Asserted
    # by exact dict equality so a field cannot be dropped without reddening here.
    assert resp.json() == {
        "email": OPERATOR.email,
        "display_name": OPERATOR.display_name,
        "base_domain": "localtest.me",
    }


def test_a_valid_operator_cookie_is_worthless_on_a_tenant_host(app: FastAPI) -> None:
    """SESSION THEFT, direction one. The cookie is host-only so a browser would
    never send it here — but a stolen token replayed by hand is not a browser, and
    the answer must not depend on the client's manners.

    It is refused TWICE over and both are asserted by this one call: the tenancy
    fence 404s /platform* on a tenant host, and `get_current_operator` would
    refuse anyway because `request.state.platform_host` is unset. The 404 is what
    arrives; the belt is proved by the test below."""
    with TestClient(app, base_url=TENANT) as client:
        client.cookies.set(PLATFORM_SESSION_COOKIE, GOOD_TOKEN, domain="bella.localtest.me")
        resp = client.get("/platform/auth/me")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "TENANT_NOT_FOUND"


def test_the_dependency_refuses_a_request_that_was_not_marked_platform_host(
    app: FastAPI,
) -> None:
    """The BELT, alone and without the braces. Mount the operator dependency on a
    path the fence does not guard and it must still refuse — so a future route
    registered outside /platform, or a middleware ordering mistake, cannot hand an
    operator context to a tenant host."""
    from typing import Annotated

    from fastapi import Depends

    from app.platform.auth import get_current_operator

    @app.get("/unfenced-probe")
    async def probe(operator: Annotated[OperatorContext, Depends(get_current_operator)]) -> str:
        return operator.email

    with TestClient(app, base_url=TENANT) as client:
        client.cookies.set(PLATFORM_SESSION_COOKIE, GOOD_TOKEN, domain="bella.localtest.me")
        resp = client.get("/unfenced-probe")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "NOT_AUTHENTICATED"


def test_a_staff_session_cookie_buys_nothing_on_the_console(app: FastAPI) -> None:
    """The two populations never share a lookup path (spec D3). A staff cookie is
    a different NAME on a different TABLE, so it is not even read here — which is
    exactly the defence in depth the distinct name exists for."""
    with _console(app) as client:
        client.cookies.set(SESSION_COOKIE, GOOD_TOKEN, domain="admin.localtest.me")
        resp = client.get("/platform/auth/me")
    assert resp.status_code == 401


# --- login: cookie, limiter, generic refusal ---------------------------------


def _login(client: TestClient, password: str = "op-console-pw") -> Response:
    return client.post("/platform/auth/login", json={"email": OPERATOR.email, "password": password})


def test_login_sets_a_host_only_httponly_lax_cookie_under_its_own_name(app: FastAPI) -> None:
    """Every attribute is asserted, and each one is load-bearing:

    * its OWN name — a leaked or misconfigured Domain still cannot be resolved by
      the staff or customer lookups (spec D3);
    * NO Domain attribute — host-only, so the browser never offers it to a
      boutique's subdomain;
    * HttpOnly — no script reads it;
    * SameSite=Lax — cross-site posts carry no session;
    * Max-Age is the 4h TTL and not the staff 12h.
    """
    with _console(app) as client:
        resp = _login(client)
    assert resp.status_code == 200
    # ⚠ base_domain IS PART OF THIS RESPONSE. The console composes every address
    # it shows from it; before F26 it rebuilt them from a hardcoded
    # "modryn.co.il", which is wrong in dev and in any domain migration. Asserted
    # by exact dict equality so a field cannot be dropped without reddening here.
    assert resp.json() == {
        "email": OPERATOR.email,
        "display_name": OPERATOR.display_name,
        "base_domain": "localtest.me",
    }

    jar = SimpleCookie()
    jar.load(resp.headers["set-cookie"])
    morsel = jar[PLATFORM_SESSION_COOKIE]
    assert morsel.value == GOOD_TOKEN
    assert morsel["httponly"]
    assert morsel["samesite"].lower() == "lax"
    assert morsel["path"] == "/"
    assert morsel["domain"] == ""
    assert morsel["max-age"] == str(60 * 60 * 4)


def test_a_wrong_password_and_an_unknown_address_answer_the_same_401(app: FastAPI) -> None:
    """ACCOUNT ENUMERATION, closed at the body as well as at the clock. The
    service does dummy argon2 work on the unknown-address path; this asserts the
    half a test can see."""
    with _console(app) as client:
        wrong = _login(client, password="not-it")
        unknown = client.post(
            "/platform/auth/login", json={"email": "nobody@modryn.example", "password": "not-it"}
        )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert wrong.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert PLATFORM_SESSION_COOKIE not in wrong.cookies


def test_the_console_login_limiter_is_its_own_instance(app: FastAPI) -> None:
    """`.memory/limiter-max-is-per-instance`, and main.py states the rule five
    times: max_attempts lives on the LIMITER, so a key on the staff budget would
    give the console the staff ceiling and let a tenant's brute-force lock the
    platform out (or the reverse)."""
    assert app.state.platform_login_rate_limiter is not app.state.login_rate_limiter


def test_failures_only_are_counted_and_a_success_clears_the_email_key(app: FastAPI) -> None:
    """BRUTE FORCE. The budget must trip on repeated failures, answer the house
    429, and be cleared by a genuine success — otherwise a burst of wrong guesses
    locks the real operator out for the whole window, which is a denial of service
    aimed at the one account that can fix anything."""
    clock = {"now": 0.0}
    app.state.platform_login_rate_limiter = FixedWindowRateLimiter(
        max_attempts=3, window_seconds=900, clock=lambda: clock["now"]
    )
    with _console(app) as client:
        for _ in range(3):
            assert _login(client, password="wrong").status_code == 401
        blocked = _login(client)  # the RIGHT password, and it never gets tried
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "TOO_MANY_ATTEMPTS"
    # The correct credential was refused by the budget BEFORE the service saw it.
    assert _fake(app).attempts[-1][1] == "wrong"

    clock["now"] += 901
    with _console(app) as client:
        assert _login(client).status_code == 200
        # …and the successful login cleared the key, so the next failure starts
        # from zero rather than from a budget already spent.
        for _ in range(2):
            assert _login(client, password="wrong").status_code == 401
        assert _login(client).status_code == 200


def test_a_caller_rotating_email_addresses_is_stopped_by_the_global_arm(app: FastAPI) -> None:
    """⚠ THE ARM THAT DOES NOT DEPEND ON THE CALLER'S HONESTY.

    Both other keys are attacker-chosen: the per-email budget never trips for a
    script that sends a fresh address each time, and the per-IP arm is inert while
    `trust_forwarded_for` is False (every deployment we have). Unmetered, each of
    those attempts buys a full argon2id verify on the single-instance pilot and
    writes a permanent `platform_audit_log` row that the app role can neither read
    nor prune.

    Mutation-checked: deleting the `global_limiter.record_failure` call, or the
    `is_blocked` arm of the pre-check, reds this and nothing else.
    """
    clock = {"now": 0.0}
    app.state.platform_login_global_rate_limiter = FixedWindowRateLimiter(
        max_attempts=3, window_seconds=900, clock=lambda: clock["now"]
    )
    with _console(app) as client:
        for n in range(3):
            fresh = client.post(
                "/platform/auth/login",
                json={"email": f"{uuid.uuid4()}@x.example", "password": "x"},
            )
            assert fresh.status_code == 401, n
        # A FOURTH never-seen address — its own per-email budget is untouched.
        blocked = client.post(
            "/platform/auth/login",
            json={"email": f"{uuid.uuid4()}@x.example", "password": "x"},
        )
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "TOO_MANY_ATTEMPTS"
    # The service never saw it: no argon2 was spent and no audit row was written.
    assert len(_fake(app).attempts) == 3


def test_the_global_login_arm_is_its_own_instance(app: FastAPI) -> None:
    """`max_attempts` lives on the LIMITER, and the global ceiling has to be an
    order of magnitude wider than the per-email one — a shared instance would
    hand every single address the flood budget."""
    assert app.state.platform_login_global_rate_limiter is not app.state.platform_login_rate_limiter
    assert app.state.platform_login_global_rate_limiter is not app.state.login_rate_limiter


def test_the_platform_cookie_is_host_prefixed_outside_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    """F25 D3's sibling-subdomain threat, answered by the BROWSER rather than by a
    convention.

    A distinct name stops the platform cookie being read by the staff lookup; it
    does not stop a script on any `*.modryn.co.il` host planting a cookie of that
    same name for the parent domain, after which admin. receives two and
    `request.cookies.get` picks one the server cannot distinguish. `__Host-` is
    refused by browsers unless Secure + path=/ + no Domain — the attributes this
    cookie already carries — so the plant becomes impossible.

    Dev keeps the bare name: the prefix REQUIRES Secure, and dev serves
    *.localtest.me over http, where a Secure cookie is never sent back.
    """
    for env, prefixed in (("dev", False), ("staging", True), ("production", True)):
        extra: dict[str, str] = (
            {}
            if env == "dev"
            else {"database_url": "postgresql+asyncpg://u:p@h/db", "base_domain": "example.com"}
        )
        settings = Settings(app_env=env, **extra)  # type: ignore[arg-type]
        monkeypatch.setattr("app.platform.auth_router.get_settings", lambda s=settings: s)

        app = _build_app()
        with _console(app) as client:
            resp = _login(client)
        assert resp.status_code == 200, env

        jar = SimpleCookie()
        jar.load(resp.headers["set-cookie"])
        expected = f"__Host-{PLATFORM_SESSION_COOKIE}" if prefixed else PLATFORM_SESSION_COOKIE
        assert expected in jar, env
        morsel = jar[expected]
        # The three attributes the prefix is contingent on. A browser drops a
        # `__Host-` cookie missing any of them, so asserting the name alone would
        # pass on a cookie no browser accepts.
        assert morsel["path"] == "/"
        assert morsel["domain"] == ""
        assert bool(morsel["secure"]) is prefixed


def test_logout_revokes_the_token_and_clears_the_cookie(app: FastAPI) -> None:
    with _console(app) as client:
        client.cookies.set(PLATFORM_SESSION_COOKIE, GOOD_TOKEN, domain="admin.localtest.me")
        resp = client.post("/platform/auth/logout")
    assert resp.status_code == 200
    assert _fake(app).logged_out == [GOOD_TOKEN]
    jar = SimpleCookie()
    jar.load(resp.headers["set-cookie"])
    assert jar[PLATFORM_SESSION_COOKIE].value == ""


def test_logout_without_a_cookie_still_clears_and_revokes_nothing(app: FastAPI) -> None:
    """No 401: signing out of a session you do not have is not an error, and
    answering one would make logout an oracle for "was that cookie live"."""
    with _console(app) as client:
        resp = client.post("/platform/auth/logout")
    assert resp.status_code == 200
    assert _fake(app).logged_out == []


# --- CSRF --------------------------------------------------------------------


def test_a_cross_origin_mutating_console_request_is_refused(app: FastAPI) -> None:
    """CSRF, and it is NOT redundant with SameSite=Lax: once tenant pages are
    public, a boutique's own subdomain is same-SITE with the console. The
    protected prefix became a tuple for exactly this."""
    with _console(app) as client:
        resp = client.post(
            "/platform/auth/login",
            json={"email": OPERATOR.email, "password": "op-console-pw"},
            headers={"origin": "http://bella.localtest.me"},
        )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "CSRF_ORIGIN_MISMATCH"


def test_a_same_origin_mutating_console_request_passes(app: FastAPI) -> None:
    with _console(app) as client:
        resp = client.post(
            "/platform/auth/login",
            json={"email": OPERATOR.email, "password": "op-console-pw"},
            headers={"origin": CONSOLE},
        )
    assert resp.status_code == 200


def test_the_manage_prefix_is_still_protected(app: FastAPI) -> None:
    """R-D's tripwire: `/platform` was ADDED to the CSRF prefix, not substituted
    for `/manage` or F24's `/storefront/portal`. The shipped manage and portal
    CSRF suites staying green unedited are the other half of this."""
    from app.csrf import PROTECTED_PREFIXES

    assert "/manage" in PROTECTED_PREFIXES
    assert "/storefront/portal" in PROTECTED_PREFIXES
    assert "/platform" in PROTECTED_PREFIXES
