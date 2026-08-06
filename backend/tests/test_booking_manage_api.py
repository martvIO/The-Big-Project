"""Fast API tests for F16's three tokenized manage endpoints: a stub
ManageBookingService + a hardcoded TenantContext, no database
(test_booking_api.py style).

The db-marked suite proves the behaviour; this file proves the HTTP contract —
anonymous, tenant-required, cookie-blind, `no-store`, POST-only, token in the
BODY — and the exact error table from the F16 spec.

The token-in-the-body assertion is the one worth spelling out: a GET or a path
parameter would put a live credential into every access log, proxy trace and
Referer header on the request's path, which is why D7 puts it in a POST body even
for the read.
"""

import dataclasses
import datetime
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_auth_service
from app.auth.service import StaffContext
from app.booking.manage import (
    BookingAlreadyStartedError,
    BookingCancelledError,
    BookingLinkInvalidError,
    BookingLookupThrottledError,
)
from app.booking.schemas import (
    MAX_TOKEN_INPUT_LENGTH,
    ManageBookingFacts,
    ManageBookingResponse,
    ManageBoutique,
    ManagePolicy,
)
from app.main import create_app
from app.models.constants import BookingStatus
from app.security_headers import SECURITY_HEADERS
from app.tenancy.middleware import TenantContext

PROFILE: dict[str, Any] = {
    "phone": "052-1234567",
    "address": "רח׳ דיזנגוף 99, תל אביב",
    "maps_url": "https://maps.example/bella",
    # NOT part of the four-field manage subset. This row is what arms the
    # absence assertion below: a key a later feature adds to `profile` must not
    # reach this page by default.
    "instagram": "bella.bridal",
    "secret_note": "owner-only",
}
TENANT = TenantContext(
    id=uuid.uuid4(), slug="bella", name="בלה כלות", settings={"profile": dict(PROFILE)}
)
STAFF_ID = uuid.uuid4()
SESSION_TOKEN = "session-token-abc"
MANAGE_TOKEN = "mt-" + "a" * 40

LOOKUP = "/storefront/booking/lookup"
CONFIRM = "/storefront/booking/confirm-attendance"
CANCEL = "/storefront/booking/cancel"
ICS = "/storefront/booking/ics"
ALL_PATHS = (LOOKUP, CONFIRM, CANCEL)

STARTS_AT = datetime.datetime(2099, 8, 2, 7, 0, tzinfo=datetime.UTC)


def _response(
    *,
    status: str = BookingStatus.CONFIRMED.value,
    confirmed_at: datetime.datetime | None = None,
    deposit_taken: bool = False,
) -> ManageBookingResponse:
    return ManageBookingResponse(
        booking=ManageBookingFacts(
            starts_at=STARTS_AT,
            status=status,
            attendance_confirmed_at=confirmed_at,
            appointment_type_name="מדידה ראשונה",
            dress_name="שמלת אלמה",
            dress_size="36",
            deposit_taken=deposit_taken,
        ),
        policy=ManagePolicy(refundable_until_hours_before=48, forfeit_percent=50),
        boutique=ManageBoutique(
            name=TENANT.name,
            phone="052-1234567",
            address="רח׳ דיזנגוף 99, תל אביב",
            maps_url="https://maps.example/bella",
        ),
    )


@dataclasses.dataclass
class StubManageService:
    """The router is a thin delegate, so the stub is programmable outcomes and a
    call log — nothing else."""

    error: Exception | None = None
    deposit_taken: bool = False
    calls: list[tuple[str, uuid.UUID, str]] = dataclasses.field(default_factory=list)

    async def lookup(self, tenant: Any, *, token: str) -> ManageBookingResponse:
        return self._answer("lookup", tenant, token)

    async def confirm_attendance(self, tenant: Any, *, token: str) -> ManageBookingResponse:
        return self._answer("confirm", tenant, token, confirmed_at=STARTS_AT)

    async def cancel(self, tenant: Any, *, token: str) -> ManageBookingResponse:
        return self._answer("cancel", tenant, token, status=BookingStatus.CANCELLED.value)

    async def ics(self, tenant: Any, *, token: str, slug: str, base_domain: str) -> str:
        if self.error is not None:
            raise self.error
        self.calls.append(("ics", tenant.id, token))
        return "BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n"

    def _answer(
        self,
        name: str,
        tenant: Any,
        token: str,
        *,
        status: str = BookingStatus.CONFIRMED.value,
        confirmed_at: datetime.datetime | None = None,
    ) -> ManageBookingResponse:
        if self.error is not None:
            raise self.error
        self.calls.append((name, tenant.id, token))
        return _response(status=status, confirmed_at=confirmed_at, deposit_taken=self.deposit_taken)


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
        return self.staff, SESSION_TOKEN

    async def resolve_session(self, tenant_id: uuid.UUID, token: str) -> StaffContext | None:
        return self.staff if token == SESSION_TOKEN else None

    async def logout(self, tenant_id: uuid.UUID, token: str) -> None:
        return None


def _client(
    stub: StubManageService | None = None, *, host: str = "bella.localtest.me"
) -> tuple[TestClient, StubManageService]:
    async def _resolver(slug: str) -> TenantContext | None:
        return TENANT if slug == "bella" else None

    app = create_app(resolver=_resolver)
    service = stub if stub is not None else StubManageService()
    app.state.manage_booking_service = service
    auth = FakeAuthService()
    app.state.auth_service = auth
    app.dependency_overrides[get_auth_service] = lambda: auth
    return TestClient(app, base_url=f"http://{host}"), service


# --- the public contract ---------------------------------------------------


@pytest.mark.parametrize("path", ALL_PATHS)
def test_every_manage_route_accepts_anonymous_and_answers_the_same_shape(path: str) -> None:
    """One response type for all three, post-action, so the page re-renders every
    state from one payload instead of branching on which call it made."""
    client, stub = _client()
    with client:
        assert client.cookies == {}
        resp = client.post(path, json={"token": MANAGE_TOKEN})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body) == {"booking", "policy", "boutique"}
    assert body["policy"] == {"refundable_until_hours_before": 48, "forfeit_percent": 50}
    assert "set-cookie" not in resp.headers
    assert [call[2] for call in stub.calls] == [MANAGE_TOKEN]


@pytest.mark.parametrize("path", ALL_PATHS)
def test_every_manage_route_is_never_cached(path: str) -> None:
    """The page is opened from an SMS on a phone, where bfcache is the default and
    the payload names a real person's appointment."""
    client, _ = _client()
    with client:
        resp = client.post(path, json={"token": MANAGE_TOKEN})
    assert resp.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("path", ALL_PATHS)
def test_every_manage_route_carries_the_security_headers(path: str) -> None:
    client, _ = _client()
    with client:
        resp = client.post(path, json={"token": MANAGE_TOKEN})
    assert {header: resp.headers.get(header) for header in SECURITY_HEADERS} == SECURITY_HEADERS


@pytest.mark.parametrize("path", ALL_PATHS)
def test_get_is_method_not_allowed(path: str) -> None:
    """POST-only, and for the lookup that is a security choice rather than a REST
    preference: a GET would carry the token in the query string."""
    client, _ = _client()
    with client:
        assert client.get(path).status_code == 405


@pytest.mark.parametrize("path", ALL_PATHS)
def test_unknown_host_is_tenant_not_found(path: str) -> None:
    """Public is not host-agnostic: an unresolvable host 404s before a
    tenant-scoped handler runs, so a token cannot be probed against 'no tenant'."""
    client, stub = _client(host="nosuch.localtest.me")
    with client:
        resp = client.post(path, json={"token": MANAGE_TOKEN})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "TENANT_NOT_FOUND"
    assert stub.calls == []


def test_owner_cookie_changes_nothing() -> None:
    """Cookie-blind: a request carrying a VALID owner session answers exactly like
    an anonymous one. The storefront and the console share this origin, so a
    browser would attach the cookie if the client asked it to."""
    anon_client, _ = _client()
    with anon_client:
        anonymous = anon_client.post(LOOKUP, json={"token": MANAGE_TOKEN})

    cookie_client, _ = _client()
    with cookie_client:
        cookie_client.cookies.set("boutique_session", SESSION_TOKEN, domain="bella.localtest.me")
        with_cookie = cookie_client.post(LOOKUP, json={"token": MANAGE_TOKEN})

    assert with_cookie.status_code == anonymous.status_code == 200
    assert with_cookie.json() == anonymous.json()
    assert "set-cookie" not in with_cookie.headers


def test_the_token_travels_in_the_body_and_never_in_the_url() -> None:
    """Asserted on the route table, not on one call: a future route added with a
    `{token}` path parameter would put a live credential in every access log."""
    client, _ = _client()
    with client:
        paths = [
            getattr(route, "path", "")
            for route in client.app.routes  # type: ignore[attr-defined]
        ]
    assert not [path for path in paths if "token" in path]


# --- what reaches the wire ------------------------------------------------


def test_the_payload_carries_no_customer_pii_and_no_ids() -> None:
    """The link is possession-auth, so the response carries the appointment's
    facts and nothing that identifies the person holding it — no name, no phone,
    no booking id, no seat index, no notes (spec Risk 4)."""
    client, _ = _client()
    with client:
        body = client.post(LOOKUP, json={"token": MANAGE_TOKEN}).json()
    assert set(body["booking"]) == {
        "starts_at",
        "status",
        "attendance_confirmed_at",
        "appointment_type_name",
        "dress_name",
        "dress_size",
        "deposit_taken",
    }
    forbidden = {"id", "customer_id", "seat_index", "notes", "phone", "name", "manage_token_hash"}
    assert not forbidden & set(body["booking"])


def test_the_deposit_fact_is_a_bare_boolean_and_never_the_sum() -> None:
    """MD3's field (A3), and the reason it is a `bool` rather than an amount:
    the cancel screen branches on WHETHER a deposit exists, and the interim
    sentence names no number. A sum on this anonymous, possession-authed wire
    would be a money fact about a person the payload otherwise refuses to
    identify."""
    client, _ = _client(StubManageService(deposit_taken=True))
    with client:
        body = client.post(LOOKUP, json={"token": MANAGE_TOKEN}).json()
    assert body["booking"]["deposit_taken"] is True
    assert not {"amount_agorot", "deposit_amount_agorot", "refund_due_agorot"} & set(
        body["booking"]
    )


def test_a_booking_with_no_deposit_says_so_rather_than_omitting_the_field() -> None:
    """`cancelConsequenceFree` survives ONLY on this branch, so the field is
    always present: a missing key would make the false "cancelling is free"
    sentence the client's default again (MD3's hard constraint)."""
    client, _ = _client()
    with client:
        body = client.post(LOOKUP, json={"token": MANAGE_TOKEN}).json()
    assert body["booking"]["deposit_taken"] is False


def test_the_boutique_block_is_the_contact_subset_only() -> None:
    client, _ = _client()
    with client:
        body = client.post(LOOKUP, json={"token": MANAGE_TOKEN}).json()
    assert set(body["boutique"]) == {"name", "phone", "address", "maps_url"}
    # `instagram` and `secret_note` are in the fixture profile and must not leak.
    assert "instagram" not in body["boutique"]
    assert "secret_note" not in body["boutique"]


def test_the_response_never_echoes_the_token() -> None:
    client, _ = _client()
    with client:
        raw = client.post(LOOKUP, json={"token": MANAGE_TOKEN}).text
    assert MANAGE_TOKEN not in raw


# --- the exact error table ------------------------------------------------


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (BookingLinkInvalidError(), 404, "BOOKING_LINK_INVALID"),
        (BookingAlreadyStartedError(), 409, "BOOKING_ALREADY_STARTED"),
        (BookingCancelledError(), 409, "BOOKING_CANCELLED"),
        (BookingLookupThrottledError(), 429, "TOO_MANY_ATTEMPTS"),
    ],
)
def test_domain_errors_map_to_the_spec_table(error: Exception, status: int, code: str) -> None:
    stub = StubManageService(error=error)
    client, _ = _client(stub)
    with client:
        resp = client.post(LOOKUP, json={"token": MANAGE_TOKEN})
    assert resp.status_code == status
    assert resp.json()["error"]["code"] == code


def test_an_invalid_link_is_not_the_shared_not_found_code() -> None:
    """The page renders its own invalid-link state off BOOKING_LINK_INVALID.
    Reusing NOT_FOUND would make a rotated manage token indistinguishable from an
    archived dress on the same origin, and the two need different copy."""
    client, _ = _client(StubManageService(error=BookingLinkInvalidError()))
    with client:
        body = client.post(LOOKUP, json={"token": MANAGE_TOKEN}).json()
    assert body["error"]["code"] != "NOT_FOUND"


@pytest.mark.parametrize("path", ALL_PATHS)
@pytest.mark.parametrize(
    "broken",
    [
        {},
        {"token": ""},
        {"token": None},
        {"token": 7},
        {"token": "x" * (MAX_TOKEN_INPUT_LENGTH + 1)},
    ],
)
def test_malformed_bodies_are_schema_400s(path: str, broken: dict[str, Any]) -> None:
    """400 and the house error shape, never a default 422 — and never a 500 from
    a megabyte token reaching the hash function."""
    client, stub = _client()
    with client:
        resp = client.post(path, json=broken)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert stub.calls == []


# --- F24's tokenized calendar download --------------------------------------


def test_the_token_ics_is_a_calendar_attachment_and_never_cached() -> None:
    """One builder, two transports (F24 D5). POST because the manage token is
    the credential and tokens never ride URLs (D7) — the SPA turns the body into
    a blob download.

    `no-store` is asserted rather than assumed: the handler returns its OWN
    Response, and FastAPI discards the dependency-owned one that carries the
    router's header."""
    client, stub = _client()
    with client:
        assert client.cookies == {}
        resp = client.post(ICS, json={"token": MANAGE_TOKEN})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "text/calendar; charset=utf-8"
    assert resp.headers["content-disposition"] == 'attachment; filename="appointment.ics"'
    assert resp.headers["cache-control"] == "no-store"
    assert resp.text.startswith("BEGIN:VCALENDAR")
    assert [call[0] for call in stub.calls] == ["ics"]
    assert "set-cookie" not in resp.headers


def test_the_token_ics_rejects_a_get() -> None:
    """A GET would put the manage token in the query string and from there into
    every access log on the path."""
    client, _ = _client()
    with client:
        assert client.get(ICS).status_code == 405


def test_a_rotated_token_gets_the_invalid_link_body_not_a_file() -> None:
    client, _ = _client(StubManageService(error=BookingLinkInvalidError()))
    with client:
        resp = client.post(ICS, json={"token": MANAGE_TOKEN})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "BOOKING_LINK_INVALID"


def test_a_cancelled_booking_serves_no_file_on_the_token_transport_either() -> None:
    client, _ = _client(StubManageService(error=BookingCancelledError()))
    with client:
        resp = client.post(ICS, json={"token": MANAGE_TOKEN})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "BOOKING_CANCELLED"


def test_the_token_ics_carries_the_security_headers() -> None:
    client, _ = _client()
    with client:
        resp = client.post(ICS, json={"token": MANAGE_TOKEN})
    assert {header: resp.headers.get(header) for header in SECURITY_HEADERS} == SECURITY_HEADERS
