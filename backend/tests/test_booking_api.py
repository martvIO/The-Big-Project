"""Fast API tests for the public booking POST: a stub BookingService + a
hardcoded TenantContext, no database (test_notifications_api.py style). The
db-marked service suite proves the claim; this file proves the HTTP contract —
route posture (anonymous, tenant-required, cookie-blind, no-store, POST-only)
and the exact error table from the F13 spec."""

import dataclasses
import datetime
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_auth_service
from app.auth.service import StaffContext
from app.booking.service import (
    BookingNotFoundError,
    BookingThrottledError,
    PhoneNotVerifiedError,
    SlotUnavailableError,
    TermsStaleError,
)
from app.booking.validation import BookingValidationError
from app.main import create_app
from app.models.constants import BookingStatus
from app.security_headers import SECURITY_HEADERS
from app.tenancy.middleware import TenantContext

TENANT = TenantContext(id=uuid.uuid4(), slug="bella", name="בלה כלות", settings={})
STAFF_ID = uuid.uuid4()
TOKEN = "session-token-abc"

PATH = "/storefront/bookings"
BOOKING_ID = uuid.uuid4()
TYPE_ID = uuid.uuid4()
STARTS_AT = datetime.datetime(2099, 8, 2, 7, 0, tzinfo=datetime.UTC)


def _body(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "phone": "050-123-4567",
        "verification_token": "tok-123",
        "name": "נועה לוי",
        "appointment_type_id": str(TYPE_ID),
        "starts_at": "2099-08-02T07:00:00Z",
        "terms_version": 1,
    }
    payload.update(overrides)
    return payload


@dataclasses.dataclass(frozen=True)
class _Row:
    """Only what the router reads off the returned booking."""

    id: uuid.UUID
    starts_at: datetime.datetime
    status: str
    appointment_type_name: str
    dress_name: str | None
    dress_size: str | None


class StubBookingService:
    """The router is a thin delegate, so the stub is programmable outcomes and
    a call log — nothing else."""

    def __init__(self) -> None:
        self.error: Exception | None = None
        self.calls: list[dict[str, Any]] = []

    async def create_booking(self, tenant_id: uuid.UUID, **kwargs: Any) -> _Row:
        if self.error is not None:
            raise self.error
        self.calls.append({"tenant_id": tenant_id, **kwargs})
        return _Row(
            id=BOOKING_ID,
            starts_at=kwargs["starts_at"],
            status=BookingStatus.CONFIRMED.value,
            appointment_type_name="מדידת שמלה",
            dress_name=None,
            dress_size=None,
        )


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
    stub: StubBookingService | None = None, *, host: str = "bella.localtest.me"
) -> tuple[TestClient, StubBookingService]:
    async def _resolver(slug: str) -> TenantContext | None:
        return TENANT if slug == "bella" else None

    app = create_app(resolver=_resolver)
    service = stub if stub is not None else StubBookingService()
    app.state.booking_service = service
    auth = FakeAuthService()
    app.state.auth_service = auth
    app.dependency_overrides[get_auth_service] = lambda: auth
    return TestClient(app, base_url=f"http://{host}"), service


# --- the public contract: anonymous, tenant-required, cookie-blind, POST-only ---


def test_create_accepts_anonymous_and_returns_201() -> None:
    client, stub = _client()
    with client:
        assert client.cookies == {}
        resp = client.post(PATH, json=_body(notes="מגיעה עם אמא"))
    assert resp.status_code == 201
    assert resp.json() == {
        "id": str(BOOKING_ID),
        "starts_at": "2099-08-02T07:00:00Z",
        "status": BookingStatus.CONFIRMED.value,
        "appointment_type_name": "מדידת שמלה",
        "dress_name": None,
        "dress_size": None,
    }
    assert "set-cookie" not in resp.headers
    assert resp.headers["cache-control"] == "no-store"
    assert {header: resp.headers.get(header) for header in SECURITY_HEADERS} == SECURITY_HEADERS

    [call] = stub.calls
    assert call["tenant_id"] == TENANT.id
    assert call["raw_phone"] == "050-123-4567"
    assert call["verification_token"] == "tok-123"
    assert call["appointment_type_id"] == TYPE_ID
    assert call["starts_at"] == STARTS_AT  # parsed to an aware instant
    assert call["terms_version"] == 1
    assert (call["dress_id"], call["dress_size"]) == (None, None)
    assert call["notes"] == "מגיעה עם אמא"


def test_unknown_host_is_tenant_not_found() -> None:
    client, stub = _client(host="nosuch.localtest.me")
    with client:
        resp = client.post(PATH, json=_body())
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "TENANT_NOT_FOUND"
    assert stub.calls == []


def test_get_is_method_not_allowed() -> None:
    """The read router is contractually GET-only and this one is POST-only —
    the pairing that keeps both contracts mechanically true."""
    client, _ = _client()
    with client:
        resp = client.get(PATH)
    assert resp.status_code == 405


def test_owner_cookie_changes_nothing() -> None:
    """Cookie-blind: a request carrying a VALID owner session answers exactly
    like an anonymous one — no personalization, no CSRF surface, no session
    reissue."""
    anon_client, _ = _client()
    with anon_client:
        anonymous = anon_client.post(PATH, json=_body())

    cookie_client, _ = _client()
    with cookie_client:
        cookie_client.cookies.set("boutique_session", TOKEN, domain="bella.localtest.me")
        with_cookie = cookie_client.post(PATH, json=_body())

    assert with_cookie.status_code == anonymous.status_code == 201
    assert with_cookie.json() == anonymous.json()
    assert "set-cookie" not in with_cookie.headers


# --- the exact error table from the spec ---


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (PhoneNotVerifiedError(), 403, "PHONE_NOT_VERIFIED"),
        (SlotUnavailableError(), 409, "SLOT_UNAVAILABLE"),
        (TermsStaleError(), 409, "TERMS_STALE"),
        (BookingNotFoundError(), 404, "NOT_FOUND"),
        (BookingThrottledError(), 429, "TOO_MANY_ATTEMPTS"),
        (BookingValidationError("name is too long"), 400, "VALIDATION_ERROR"),
    ],
)
def test_domain_errors_map_to_the_spec_table(error: Exception, status: int, code: str) -> None:
    stub = StubBookingService()
    stub.error = error
    client, _ = _client(stub)
    with client:
        resp = client.post(PATH, json=_body())
    assert resp.status_code == status, resp.text
    assert resp.json()["error"]["code"] == code


# --- schema boundary ---


@pytest.mark.parametrize(
    "broken",
    [
        {"phone": ""},
        {"verification_token": ""},
        {"name": ""},
        {"appointment_type_id": "not-a-uuid"},
        {"starts_at": "2099-08-02T07:00:00"},  # naive: no offset, no instant
        {"starts_at": "yesterday-ish"},
        {"terms_version": 0},
    ],
)
def test_malformed_bodies_are_schema_400s(broken: dict[str, Any]) -> None:
    client, stub = _client()
    with client:
        resp = client.post(PATH, json=_body(**broken))
    assert resp.status_code == 400, resp.text
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert stub.calls == []


def test_missing_body_is_a_schema_400() -> None:
    client, stub = _client()
    with client:
        resp = client.post(PATH)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert stub.calls == []
