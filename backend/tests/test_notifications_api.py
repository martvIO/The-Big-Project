"""Fast API tests for the public OTP surface: a stub OtpService + a hardcoded
TenantContext, no database (test_storefront_api.py style). The db-marked service
suite proves the lifecycle; this file proves the HTTP contract — route posture
(anonymous, tenant-required, cookie-blind, no-store, POST-only) and the exact
error table from the F11 spec."""

import datetime
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_auth_service
from app.auth.service import StaffContext
from app.errors import DomainValidationError
from app.main import create_app
from app.notifications.base import SmsNotConfiguredError, SmsSendError
from app.notifications.service import (
    OtpExpiredError,
    OtpInvalidError,
    OtpThrottledError,
    VerifyResult,
)
from app.security_headers import SECURITY_HEADERS
from app.tenancy.middleware import TenantContext

TENANT = TenantContext(id=uuid.uuid4(), slug="bella", name="בלה כלות", settings={})
STAFF_ID = uuid.uuid4()
TOKEN = "session-token-abc"


class _TrustingSettings:
    """Only `trust_forwarded_for` is read by the send route. A real `Settings`
    would work too; this makes the single field under test unmissable."""

    trust_forwarded_for = True


async def _null_resolver(slug: str) -> TenantContext | None:
    """No host resolves — enough to build the real app and read its wiring."""
    return None


SEND_PATH = "/storefront/otp/send"
VERIFY_PATH = "/storefront/otp/verify"
PATHS = [SEND_PATH, VERIFY_PATH]

PHONE = "050-123-4567"
EXPIRES_AT = datetime.datetime(2026, 7, 28, 12, 10, tzinfo=datetime.UTC)


class StubOtpService:
    """The router is a thin delegate, so the stub is programmable outcomes and
    a call log — nothing else."""

    def __init__(self) -> None:
        self.send_error: Exception | None = None
        self.verify_error: Exception | None = None
        self.send_calls: list[tuple[uuid.UUID, str]] = []
        self.verify_calls: list[tuple[uuid.UUID, str, str]] = []
        self.send_ips: list[str | None] = []

    async def send(self, tenant_id: uuid.UUID, raw_phone: str, *, ip: str | None = None) -> None:
        if self.send_error is not None:
            raise self.send_error
        self.send_calls.append((tenant_id, raw_phone))
        self.send_ips.append(ip)

    async def verify(self, tenant_id: uuid.UUID, raw_phone: str, code: str) -> VerifyResult:
        if self.verify_error is not None:
            raise self.verify_error
        self.verify_calls.append((tenant_id, raw_phone, code))
        return VerifyResult(verification_token="tok-123", expires_at=EXPIRES_AT)


class FakeAuthService:
    """Only here so the owner cookie in test_owner_cookie_changes_nothing is a
    genuinely resolvable session rather than a random string."""

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
        return self.staff, TOKEN

    async def resolve_session(self, tenant_id: uuid.UUID, token: str) -> StaffContext | None:
        return self.staff if token == TOKEN else None

    async def logout(self, tenant_id: uuid.UUID, token: str) -> None:
        return None


def _client(
    stub: StubOtpService | None = None, *, host: str = "bella.localtest.me"
) -> tuple[TestClient, StubOtpService]:
    async def _resolver(slug: str) -> TenantContext | None:
        return TENANT if slug == "bella" else None

    app = create_app(resolver=_resolver)
    service = stub if stub is not None else StubOtpService()
    app.state.otp_service = service
    auth = FakeAuthService()
    app.state.auth_service = auth
    app.dependency_overrides[get_auth_service] = lambda: auth
    return TestClient(app, base_url=f"http://{host}"), service


def _post(client: TestClient, path: str) -> httpx.Response:
    if path == SEND_PATH:
        return client.post(path, json={"phone": PHONE})
    return client.post(path, json={"phone": PHONE, "code": "123456"})


# --- the public contract: anonymous, tenant-required, cookie-blind, POST-only ---


def test_send_accepts_anonymous_and_returns_204() -> None:
    client, stub = _client()
    with client:
        assert client.cookies == {}
        resp = client.post(SEND_PATH, json={"phone": PHONE})
    assert resp.status_code == 204
    assert resp.content == b""
    assert "set-cookie" not in resp.headers
    assert stub.send_calls == [(TENANT.id, PHONE)]


def test_verify_returns_the_token_once() -> None:
    client, stub = _client()
    with client:
        resp = client.post(VERIFY_PATH, json={"phone": PHONE, "code": "123456"})
    assert resp.status_code == 200
    assert resp.json() == {
        "verification_token": "tok-123",
        "expires_at": "2026-07-28T12:10:00Z",
    }
    assert stub.verify_calls == [(TENANT.id, PHONE, "123456")]


@pytest.mark.parametrize("path", PATHS)
def test_otp_paths_are_not_exempt_from_tenant_resolution(path: str) -> None:
    """Public is not host-agnostic: an unresolvable host 404s before a handler."""
    client, _ = _client(host="nosuch.localtest.me")
    with client:
        resp = _post(client, path)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "TENANT_NOT_FOUND"


@pytest.mark.parametrize("path", PATHS)
def test_otp_responses_are_never_cached(path: str) -> None:
    """The verify response carries a bearer verification_token; no-store is set
    on the router so send cannot drift from verify."""
    client, _ = _client()
    with client:
        resp = _post(client, path)
    assert resp.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("path", PATHS)
def test_get_stays_405(path: str) -> None:
    client, _ = _client()
    with client:
        resp = client.get(path)
    assert resp.status_code == 405


def test_owner_cookie_changes_nothing() -> None:
    """A public endpoint that behaves differently for a logged-in owner is a
    public endpoint with a hidden second contract — bytes identical, not merely
    the status code."""
    client, _ = _client()
    with client:
        anonymous = {path: _post(client, path) for path in PATHS}
        client.cookies.set("boutique_session", TOKEN, domain="bella.localtest.me")
        authenticated = {path: _post(client, path) for path in PATHS}
    for path in PATHS:
        assert anonymous[path].status_code == authenticated[path].status_code, path
        assert anonymous[path].content == authenticated[path].content, path
        assert "set-cookie" not in authenticated[path].headers, path


def test_security_headers_are_on_an_otp_response() -> None:
    client, _ = _client()
    with client:
        resp = client.post(SEND_PATH, json={"phone": PHONE})
    assert {header: resp.headers.get(header) for header in SECURITY_HEADERS} == SECURITY_HEADERS


# --- the spec's error table, verbatim ---


def test_malformed_body_is_a_house_shape_400() -> None:
    client, _ = _client()
    with client:
        resp = client.post(SEND_PATH, json={})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_invalid_phone_maps_to_validation_error() -> None:
    client, stub = _client()
    stub.send_error = DomainValidationError("Enter a valid Israeli mobile number.")
    with client:
        resp = client.post(SEND_PATH, json={"phone": "not-a-phone"})
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["message"] == "Enter a valid Israeli mobile number."


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (OtpInvalidError(), 400, "OTP_INVALID"),
        (OtpExpiredError(), 400, "OTP_EXPIRED"),
        (OtpThrottledError(), 429, "TOO_MANY_ATTEMPTS"),
    ],
)
def test_verify_error_mapping(error: Exception, status: int, code: str) -> None:
    client, stub = _client()
    stub.verify_error = error
    with client:
        resp = client.post(VERIFY_PATH, json={"phone": PHONE, "code": "000000"})
    assert resp.status_code == status
    assert resp.json()["error"]["code"] == code


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (OtpThrottledError(), 429, "TOO_MANY_ATTEMPTS"),
        (SmsNotConfiguredError(), 503, "SMS_NOT_CONFIGURED"),
        (SmsSendError(), 503, "SMS_UNAVAILABLE"),
    ],
)
def test_send_error_mapping(error: Exception, status: int, code: str) -> None:
    client, stub = _client()
    stub.send_error = error
    with client:
        resp = client.post(SEND_PATH, json={"phone": PHONE})
    assert resp.status_code == status
    assert resp.json()["error"]["code"] == code
    # Fixed bodies: no provider name or provider-supplied text ever leaks.
    assert "twilio" not in resp.text.lower()


# --- F21 B5 / row R16: the per-IP send budget's wiring, and its inertness ---


def test_the_send_route_hands_the_service_no_ip_on_the_shipped_default() -> None:
    """⚠ THIS IS THE ASSERTION THAT KEEPS ROW R16 AMBER RATHER THAN GREEN.

    `trust_forwarded_for` ships `False` (`config.py:37`), so `client_ip` returns
    `None`, so the per-IP budget the service now carries is NEVER SPENT on any
    deployment we currently have. The code is correct and INERT. Ticking R16
    green on the strength of the code alone would be exactly the failure D2
    exists to prevent — a checklist row describing a mechanism that does not run.

    Arming it is a host fact, not a code change: `TRUST_FORWARDED_FOR=true` is
    only correct on a deployment that terminates exactly one trusted proxy which
    appends `X-Forwarded-For`, and getting it wrong turns the budget into a single
    global bucket keyed on the proxy. Enablement is the parked `F62` entry's,
    together with the distributed limiter.

    An `X-Forwarded-For` header IS sent here, so the test cannot pass merely
    because nothing offered an address.
    """
    client, stub = _client()
    with client:
        resp = client.post(
            SEND_PATH, json={"phone": PHONE}, headers={"x-forwarded-for": "203.0.113.9"}
        )
    assert resp.status_code == 204
    assert stub.send_ips == [None], (
        "the router derived a client IP with trust_forwarded_for=False — the "
        "budget is no longer inert, and row R16's amber reasoning is now wrong"
    )


def test_the_send_route_hands_the_service_the_forwarded_ip_when_a_proxy_is_trusted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The other half: the wiring is real, and flipping one setting arms it. The
    LAST XFF entry is taken — with exactly one trusted hop that is the address the
    proxy saw, and every earlier entry is client-supplied and forgeable."""
    monkeypatch.setattr("app.notifications.router.get_settings", lambda: _TrustingSettings())
    client, stub = _client()
    with client:
        resp = client.post(
            SEND_PATH,
            json={"phone": PHONE},
            headers={"x-forwarded-for": "198.51.100.7, 203.0.113.9"},
        )
    assert resp.status_code == 204
    assert stub.send_ips == ["203.0.113.9"]


def test_the_shipped_app_gives_every_otp_budget_its_own_limiter_instance() -> None:
    """⚠ WRITTEN BECAUSE A MUTATION CAME BACK GREEN. Reusing one
    `FixedWindowRateLimiter` for the IP budget and the phone budget in `main.py`
    left every test in this module and in `test_notifications_service.py` passing:
    the service tests inject their own limiters, so they never see the wiring, and
    nothing else looked at it.

    `max_attempts` lives on the LIMITER and not on the key
    (`.memory/limiter-max-is-per-instance`, and `booking/service.py:233-236` says
    it in the code: "A SEPARATE instance, not a second key on create_limiter").
    Two keys on one instance share one ceiling — a boutique's whole tenant budget
    spent by one number, or every customer in the country throttled against one
    another. This is the assertion that makes the wiring, not just the logic, a
    tested property.

    Pairwise identity over the four, so a fifth budget added later cannot quietly
    join an existing instance either.
    """
    app = create_app(resolver=_null_resolver)
    otp = app.state.otp_service
    limiters = {
        "phone": otp._phone_limiter,
        "tenant": otp._tenant_limiter,
        "verify": otp._verify_limiter,
        "ip": otp._ip_limiter,
    }
    for name, limiter in limiters.items():
        others = {other: obj for other, obj in limiters.items() if other != name}
        shared = [other for other, obj in others.items() if obj is limiter]
        assert not shared, f"the {name} budget shares its limiter instance with {shared}"
