"""F25 D5 — the console endpoints' HTTP contract, fast lane.

⚠ THE ERROR CODES ARE THE CONTRACT, and that is what this module exists for. The
console maps each one to its own Hebrew sentence (design deck §6) and falls
through to a generic message for anything unlisted — so a code that silently
changed status, or arrived spelled differently, would reach an operator as "an
unexpected error occurred" on a screen that had a precise sentence ready.

The db-marked sibling proves the same routes against real Postgres with the real
audit rows. This one pins the mapping where it can be seen without Docker.
"""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.cookies import platform_session_cookie_name
from app.main import create_app
from app.platform.auth import OperatorContext
from app.platform.service import CommandResult, TenantSummary

CONSOLE = "http://admin.localtest.me"
TOKEN = "a-live-session-token"

# The suite runs with `app_env="dev"`, so `secure_cookies` is False and the name
# has no `__Host-` prefix. The prefixed form is asserted in its own test, driven
# off a non-dev Settings — the prefix is browser-enforced and the browser also
# refuses it without Secure, which dev does not set.
PLATFORM_SESSION_COOKIE = platform_session_cookie_name(secure=False)
OPERATOR = OperatorContext(id=uuid.uuid4(), email="dana@modryn.example", display_name="Dana")


class FakeOperatorAuth:
    async def resolve_session(self, token: str) -> OperatorContext | None:
        return OPERATOR if token == TOKEN else None


class FakeProvisioning:
    """Records the kwargs each route passes through, so the `operator=` argument
    — the whole point of D5, an authenticated identity replacing the CLI's
    free-text `$USER` — is asserted rather than assumed."""

    def __init__(self, result: CommandResult | None = None) -> None:
        self.calls: list[tuple[str, dict]] = []
        self._result = result or CommandResult(ok=True, message="done")

    async def provision(self, **kwargs: object) -> CommandResult:
        self.calls.append(("provision", kwargs))
        return self._result

    async def suspend(self, **kwargs: object) -> CommandResult:
        self.calls.append(("suspend", kwargs))
        return self._result

    async def reset_owner_password(self, **kwargs: object) -> CommandResult:
        self.calls.append(("reset_owner_password", kwargs))
        return self._result

    async def list_tenants(self, **kwargs: object) -> list[TenantSummary]:
        self.calls.append(("list_tenants", kwargs))
        return [
            TenantSummary(
                slug="bella",
                name="Bella Bridal",
                status="active",
                created_at=datetime(2026, 8, 1, 9, 30, tzinfo=UTC),
            )
        ]


async def _resolver(slug: str) -> None:
    return None


@pytest.fixture
def app() -> Iterator[FastAPI]:
    application = create_app(resolver=_resolver)
    application.state.platform_auth_service = FakeOperatorAuth()
    application.state.provisioning_service = FakeProvisioning()
    yield application


def _client(app: FastAPI) -> TestClient:
    client = TestClient(app, base_url=CONSOLE)
    client.cookies.set(PLATFORM_SESSION_COOKIE, TOKEN, domain="admin.localtest.me")
    return client


PROVISION_BODY = {
    "slug": "bella",
    "name": "Bella Bridal",
    "owner_email": "owner@bella.example",
    "owner_password": "owner-first-password",
}

CONSOLE_ROUTES = (
    ("POST", "/platform/tenants/provision", PROVISION_BODY),
    ("POST", "/platform/tenants/suspend", {"slug": "bella"}),
    ("GET", "/platform/tenants", None),
    (
        "POST",
        "/platform/tenants/reset-owner-password",
        {"slug": "bella", "owner_email": "owner@bella.example", "new_password": "a-new-password"},
    ),
)


def test_every_console_route_refuses_an_unauthenticated_caller(app: FastAPI) -> None:
    """DEFAULT DENY, walked over the whole surface rather than route by route: a
    fifth endpoint added later without `Depends(get_current_operator)` fails
    here."""
    with TestClient(app, base_url=CONSOLE) as client:
        for method, path, body in CONSOLE_ROUTES:
            resp = client.request(method, path, json=body)
            assert resp.status_code == 401, (method, path)
            assert resp.json()["error"]["code"] == "NOT_AUTHENTICATED", (method, path)


def test_each_route_delegates_with_the_authenticated_operators_email(app: FastAPI) -> None:
    """D5's substance. The service is UNCHANGED; what the router adds is that the
    free-text `operator` column now carries an identity somebody had to
    authenticate as, instead of whatever `$USER` happened to be on the box."""
    with _client(app) as client:
        for method, path, body in CONSOLE_ROUTES:
            assert client.request(method, path, json=body).status_code == 200, path
    calls = app.state.provisioning_service.calls
    assert [name for name, _ in calls] == [
        "provision",
        "suspend",
        "list_tenants",
        "reset_owner_password",
    ]
    for _, kwargs in calls:
        assert kwargs["operator"] == OPERATOR.email


def test_the_tenant_list_is_the_service_summary_verbatim(app: FastAPI) -> None:
    with _client(app) as client:
        resp = client.get("/platform/tenants")
    assert resp.status_code == 200
    assert resp.json() == {
        "tenants": [
            {
                "slug": "bella",
                "name": "Bella Bridal",
                "status": "active",
                "created_at": "2026-08-01T09:30:00Z",
            }
        ]
    }


@pytest.mark.parametrize(
    ("message", "status"),
    [
        ("invalid_or_reserved_slug", 400),
        ("empty_password", 400),
        ("slug_taken", 409),
        ("tenant_not_found", 404),
        ("owner_not_found", 404),
    ],
)
def test_a_service_refusal_becomes_its_own_code_at_its_own_status(
    app: FastAPI, message: str, status: int
) -> None:
    """Five codes, five sentences in the console. `slug_taken` is 409 rather than
    400 on purpose: the request is well-formed and another boutique — possibly a
    SUSPENDED one the operator cannot see — is what refuses it."""
    app.state.provisioning_service = FakeProvisioning(CommandResult(ok=False, message=message))
    with _client(app) as client:
        resp = client.post("/platform/tenants/provision", json=PROVISION_BODY)
    assert resp.status_code == status
    assert resp.json()["error"]["code"] == message


def test_an_unmapped_refusal_still_arrives_as_its_own_code(app: FastAPI) -> None:
    """A service message nobody mapped must not collapse into a 500 or into
    somebody else's code. It arrives as itself at 400, and the console's
    fall-through renders the generic sentence — degraded, never wrong."""
    app.state.provisioning_service = FakeProvisioning(
        CommandResult(ok=False, message="a_new_refusal_nobody_mapped")
    )
    with _client(app) as client:
        resp = client.post("/platform/tenants/suspend", json={"slug": "bella"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "a_new_refusal_nobody_mapped"


def test_the_console_routes_do_not_exist_on_a_tenant_host(app: FastAPI) -> None:
    """The fence again, over the console's real surface rather than over a probe
    route — and with a live operator cookie attached, which is the case that would
    matter."""
    with TestClient(app, base_url="http://bella.localtest.me") as client:
        client.cookies.set(PLATFORM_SESSION_COOKIE, TOKEN, domain="bella.localtest.me")
        for method, path, body in CONSOLE_ROUTES:
            resp = client.request(method, path, json=body)
            assert resp.status_code == 404, (method, path)
            assert resp.json()["error"]["code"] == "TENANT_NOT_FOUND", (method, path)


def test_a_console_response_carries_the_security_headers(app: FastAPI) -> None:
    """SecurityHeadersMiddleware is host-agnostic and outermost, so CSP/HSTS ride
    free on the console host too. Asserted once rather than assumed — the spec's
    test plan asks for exactly one such check."""
    with _client(app) as client:
        resp = client.get("/platform/tenants")
    assert resp.headers["content-security-policy"]
    assert resp.headers["x-content-type-options"] == "nosniff"
