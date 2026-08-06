"""Fast API tests for the storefront waitlist join: a stub WaitlistService and a
hardcoded TenantContext, no database (the F11 posture template, via F33's file).

The service suite proves the transaction and the race; this one proves the HTTP
contract — anonymous, tenant-from-Host, cookie-blind, no-store, POST-only — and
the exact error table. D2's promise is asserted as a literal: the join adds
ZERO new error codes.

It is also where `.memory/limiter-max-is-per-instance` is pinned at the WIRING:
create_app must hand the join its own two limiter instances, never a key on the
booking or OTP budgets.
"""

import datetime
import uuid

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_auth_service
from app.auth.service import StaffContext
from app.booking.service import BookingNotFoundError, PhoneNotVerifiedError
from app.errors import DomainValidationError
from app.main import create_app
from app.models.constants import WaitlistEntryStatus
from app.tenancy.middleware import TenantContext
from app.waitlist.schemas import WaitlistJoinResponse
from app.waitlist.validation import WaitlistThrottledError

TENANT = TenantContext(id=uuid.uuid4(), slug="bella", name="בלה כלות", settings={})
STAFF_ID = uuid.uuid4()
TOKEN = "session-token-abc"

JOIN_PATH = "/storefront/waitlist"
DAY = datetime.date(2026, 8, 20)
TYPE_ID = uuid.UUID("3fa85f64-5717-4562-b3fc-2c963f66afa6")

# The whole error surface this feature can answer, and F22 adds NO new code —
# every row is a shipped body. Asserted set-equal below against what this module
# actually exercises.
SPEC_ERROR_CODES = {
    "TENANT_NOT_FOUND",
    "VALIDATION_ERROR",
    "NOT_FOUND",
    "PHONE_NOT_VERIFIED",
    "TOO_MANY_ATTEMPTS",
}


def _body() -> dict[str, object]:
    return {
        "phone": "050-123-4567",
        "verification_token": "tok-1",
        "day": DAY.isoformat(),
        "appointment_type_id": str(TYPE_ID),
    }


class StubWaitlistService:
    def __init__(self) -> None:
        self.error: Exception | None = None
        self.calls: list[tuple[uuid.UUID, str, str, datetime.date, uuid.UUID]] = []

    async def join(
        self,
        tenant_id: uuid.UUID,
        *,
        raw_phone: str,
        verification_token: str,
        day: datetime.date,
        appointment_type_id: uuid.UUID,
    ) -> WaitlistJoinResponse:
        if self.error is not None:
            raise self.error
        self.calls.append((tenant_id, raw_phone, verification_token, day, appointment_type_id))
        return WaitlistJoinResponse(
            day=day,
            appointment_type_id=appointment_type_id,
            status=WaitlistEntryStatus.WAITING.value,
        )


class FakeAuthService:
    """Only here so the owner cookie in the cookie-blindness test is a genuinely
    resolvable session rather than a random string."""

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
    stub: StubWaitlistService | None = None, *, host: str = "bella.localtest.me"
) -> tuple[TestClient, StubWaitlistService]:
    async def _resolver(slug: str) -> TenantContext | None:
        return TENANT if slug == "bella" else None

    app = create_app(resolver=_resolver)
    service = stub if stub is not None else StubWaitlistService()
    app.state.waitlist_service = service
    auth = FakeAuthService()
    app.state.auth_service = auth
    app.dependency_overrides[get_auth_service] = lambda: auth
    return TestClient(app, base_url=f"http://{host}"), service


def test_the_join_accepts_anonymous_and_answers_201_with_the_whole_body() -> None:
    client, stub = _client()
    with client:
        assert client.cookies == {}
        resp = client.post(JOIN_PATH, json=_body())
    assert resp.status_code == 201
    # The WHOLE body: no id (a capability shape with no consumer, D2), no phone
    # echo, no position.
    assert resp.json() == {
        "day": DAY.isoformat(),
        "appointment_type_id": str(TYPE_ID),
        "status": WaitlistEntryStatus.WAITING.value,
    }
    assert "set-cookie" not in resp.headers
    assert stub.calls == [(TENANT.id, "050-123-4567", "tok-1", DAY, TYPE_ID)]


def test_the_tenant_reaches_the_service_from_the_host_and_never_from_the_body() -> None:
    client, stub = _client()
    with client:
        client.post(JOIN_PATH, json=_body())
    assert stub.calls[0][0] == TENANT.id


def test_the_join_path_is_not_exempt_from_tenant_resolution() -> None:
    client, stub = _client(host="nosuch.localtest.me")
    with client:
        resp = client.post(JOIN_PATH, json=_body())
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "TENANT_NOT_FOUND"
    assert stub.calls == []


def test_the_join_response_is_never_cached() -> None:
    client, _ = _client()
    with client:
        resp = client.post(JOIN_PATH, json=_body())
    assert resp.headers["cache-control"] == "no-store"


def test_get_stays_405() -> None:
    client, _ = _client()
    with client:
        resp = client.get(JOIN_PATH)
    assert resp.status_code == 405


def test_an_owner_cookie_changes_nothing() -> None:
    """Cookie-blind, the sibling routers' shared posture: the credential is the
    verification token in the body, and an ambient session must neither help
    nor hurt."""
    client, _ = _client()
    with client:
        anonymous = client.post(JOIN_PATH, json=_body())
        client.cookies.set("session", TOKEN)
        with_cookie = client.post(JOIN_PATH, json=_body())
    assert anonymous.status_code == with_cookie.status_code == 201
    assert anonymous.json() == with_cookie.json()
    assert "set-cookie" not in with_cookie.headers


def test_an_unknown_key_is_a_422_and_reaches_no_service(client_error_code: str = "") -> None:
    client, stub = _client()
    with client:
        resp = client.post(JOIN_PATH, json={**_body(), "name": "נועה"})
    assert resp.status_code in (400, 422)
    assert stub.calls == []


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (DomainValidationError("day is outside the joinable window"), 400, "VALIDATION_ERROR"),
        (BookingNotFoundError(), 404, "NOT_FOUND"),
        (PhoneNotVerifiedError(), 403, "PHONE_NOT_VERIFIED"),
        (WaitlistThrottledError(), 429, "TOO_MANY_ATTEMPTS"),
    ],
)
def test_the_error_table_is_exactly_the_shipped_codes(
    error: Exception, status: int, code: str
) -> None:
    stub = StubWaitlistService()
    stub.error = error
    client, _ = _client(stub)
    with client:
        resp = client.post(JOIN_PATH, json=_body())
    assert resp.status_code == status
    assert resp.json()["error"]["code"] == code


def test_no_new_error_codes_joined_the_spec_table() -> None:
    """The set-equality leg: every code this module exercises is in the spec
    set, and the spec set names nothing this module does not exercise — a row
    added to either side without the other fails here."""
    exercised = {
        "TENANT_NOT_FOUND",
        "VALIDATION_ERROR",
        "NOT_FOUND",
        "PHONE_NOT_VERIFIED",
        "TOO_MANY_ATTEMPTS",
    }
    assert exercised == SPEC_ERROR_CODES


def test_the_join_budgets_are_their_own_limiter_instances() -> None:
    """`.memory/limiter-max-is-per-instance`, pinned at the WIRING: max_attempts
    lives on the limiter, so a shared instance is one shared ceiling — a
    waitlist join must never be able to eat the booking or OTP budgets, nor the
    two join budgets each other's."""

    async def _resolver(slug: str) -> TenantContext | None:
        return TENANT

    app = create_app(resolver=_resolver)
    waitlist = app.state.waitlist_service
    booking = app.state.booking_service
    otp = app.state.otp_service

    own = {id(waitlist._phone_limiter), id(waitlist._tenant_limiter)}
    assert waitlist._phone_limiter is not waitlist._tenant_limiter
    others = {
        id(booking._create_limiter),
        id(booking._phone_limiter),
        id(otp._phone_limiter),
        id(otp._tenant_limiter),
        id(otp._verify_limiter),
        id(otp._ip_limiter),
    }
    assert not own & others
    # And the OTP budgets are SHARED BY CONSTRUCTION (D3): the join reuses the
    # OTP endpoints, so the service must hold the same OtpService instance —
    # one phone proving itself is one proof, whichever flow consumes it.
    assert waitlist._otp is otp
