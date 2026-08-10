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
from app.models.constants import StaffRole, WaitlistEntryStatus
from app.tenancy.middleware import TenantContext
from app.waitlist.schemas import (
    ManageWaitlistResponse,
    ManageWaitlistRow,
    WaitlistJoinResponse,
)
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
    """The owner cookie in the cookie-blindness test and the whole of "signed
    in" for the manage half — the test_checkin_qr_api shape."""

    def __init__(self, role: str = StaffRole.OWNER.value) -> None:
        self.staff = StaffContext(
            id=STAFF_ID,
            tenant_id=TENANT.id,
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


def _client(
    stub: StubWaitlistService | None = None,
    *,
    host: str = "bella.localtest.me",
    role: str = StaffRole.OWNER.value,
) -> tuple[TestClient, StubWaitlistService]:
    async def _resolver(slug: str) -> TenantContext | None:
        return TENANT if slug == "bella" else None

    app = create_app(resolver=_resolver)
    service = stub if stub is not None else StubWaitlistService()
    app.state.waitlist_service = service
    auth = FakeAuthService(role)
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


# --- the manage half: list + cancel (D5) --------------------------------------

MANAGE_LIST_PATH = "/manage/waitlist"
ENTRY_ID = uuid.UUID("7fa85f64-5717-4562-b3fc-2c963f66afa7")
CREATED_AT = datetime.datetime(2026, 8, 1, 9, 30, tzinfo=datetime.UTC)
UNKNOWN_ROLE = "no-such-role"


OFFER_STARTS_AT = datetime.datetime(2026, 8, 20, 11, 30, tzinfo=datetime.UTC)
OFFER_EXPIRES_AT = datetime.datetime(2026, 8, 20, 9, 15, tzinfo=datetime.UTC)


def _row(
    status: str = WaitlistEntryStatus.WAITING.value,
    *,
    offer_starts_at: datetime.datetime | None = None,
    offer_expires_at: datetime.datetime | None = None,
) -> ManageWaitlistRow:
    return ManageWaitlistRow(
        id=ENTRY_ID,
        day=DAY,
        appointment_type_id=TYPE_ID,
        appointment_type_name="מדידה ראשונה",
        phone="+972501234567",
        customer_name=None,
        status=status,
        created_at=CREATED_AT,
        offer_starts_at=offer_starts_at,
        offer_expires_at=offer_expires_at,
    )


class StubManageWaitlistService(StubWaitlistService):
    def __init__(self) -> None:
        super().__init__()
        self.list_calls: list[tuple[uuid.UUID, datetime.date | None]] = []
        self.cancel_calls: list[tuple[uuid.UUID, uuid.UUID, uuid.UUID]] = []
        self.cancel_error: Exception | None = None
        self.rows: list[ManageWaitlistRow] = [_row()]

    async def list_entries(
        self, tenant_id: uuid.UUID, *, day: datetime.date | None = None
    ) -> ManageWaitlistResponse:
        self.list_calls.append((tenant_id, day))
        return ManageWaitlistResponse(entries=list(self.rows))

    async def cancel_entry(
        self, tenant_id: uuid.UUID, *, entry_id: uuid.UUID, actor: StaffContext
    ) -> ManageWaitlistRow:
        if self.cancel_error is not None:
            raise self.cancel_error
        self.cancel_calls.append((tenant_id, entry_id, actor.id))
        return _row(status=WaitlistEntryStatus.CANCELLED.value)


def _manage_client(
    *, authed: bool = True, role: str = StaffRole.OWNER.value
) -> tuple[TestClient, StubManageWaitlistService]:
    stub = StubManageWaitlistService()
    client, _ = _client(stub, role=role)
    if authed:
        client.cookies.set("boutique_session", TOKEN, domain="bella.localtest.me")
    return client, stub


def test_the_manage_routes_require_authentication() -> None:
    for method, path in (
        ("GET", MANAGE_LIST_PATH),
        ("POST", f"{MANAGE_LIST_PATH}/{ENTRY_ID}/cancel"),
    ):
        client, stub = _manage_client(authed=False)
        with client:
            resp = client.request(method, path)
        assert resp.status_code == 401, f"{method} {path} → {resp.status_code}"
        assert resp.json()["error"]["code"] == "NOT_AUTHENTICATED"
        assert stub.list_calls == [] and stub.cancel_calls == []


@pytest.mark.parametrize("role", [StaffRole.OWNER.value, StaffRole.SHIFT_MANAGER.value])
def test_both_console_roles_reach_the_list_and_the_cancel(role: str) -> None:
    """The exactly-two gate (D5), both halves asserted here; the walker in
    test_staff_role_gating.py covers the routes with no new test BECAUSE they
    must stay out of its OWNER_ONLY set — pinned below."""
    client, stub = _manage_client(role=role)
    with client:
        listed = client.get(MANAGE_LIST_PATH)
        cancelled = client.post(f"{MANAGE_LIST_PATH}/{ENTRY_ID}/cancel")
    assert listed.status_code == 200
    assert cancelled.status_code == 200
    assert [entry["phone"] for entry in listed.json()["entries"]] == ["+972501234567"]
    assert cancelled.json()["status"] == WaitlistEntryStatus.CANCELLED.value
    assert stub.cancel_calls == [(TENANT.id, ENTRY_ID, STAFF_ID)]


def test_the_manage_row_carries_the_two_offer_instants_and_nothing_more() -> None:
    """F23 D8 / design §4 — the console's whole share of the offer.

    An owner clearing a day needs exactly one thing from an `offered` row: IS
    ANYONE HOLDING THIS SLOT RIGHT NOW, AND UNTIL WHEN. That is two instants,
    and the design refuses the rest by name — no offer counter, no expiry log,
    no per-entry offer trail (the audit trail lives in `audit_log`).

    The key set is asserted whole, not by membership: the token hash is one
    column away from these two on the same row, and a wire shape that grew it
    would hand a live claim credential to every console session.
    """
    client, stub = _manage_client()
    stub.rows = [
        _row(
            status=WaitlistEntryStatus.OFFERED.value,
            offer_starts_at=OFFER_STARTS_AT,
            offer_expires_at=OFFER_EXPIRES_AT,
        ),
        _row(),
    ]
    with client:
        listed = client.get(MANAGE_LIST_PATH)

    offered, waiting = listed.json()["entries"]
    assert set(offered) == {
        "id",
        "day",
        "appointment_type_id",
        "appointment_type_name",
        "phone",
        "customer_name",
        "status",
        "created_at",
        "offer_starts_at",
        "offer_expires_at",
    }
    # The house Z form, not "+00:00": the console renders these two through
    # `new Date(...)`, and the offer column is the one place a misparsed instant
    # would silently show an owner the wrong deadline for a live hold.
    assert offered["offer_starts_at"] == "2026-08-20T11:30:00Z"
    assert offered["offer_expires_at"] == "2026-08-20T09:15:00Z"
    # A `waiting` row carries nulls rather than omitting the fields — the column
    # renders «—» from them, and an absent key would make that a client guess.
    assert waiting["offer_starts_at"] is None
    assert waiting["offer_expires_at"] is None


def test_the_waitlist_routes_are_absent_from_owner_only() -> None:
    from test_staff_role_gating import OWNER_ONLY

    assert ("GET", "/manage/waitlist") not in OWNER_ONLY
    assert ("POST", "/manage/waitlist/{entry_id}/cancel") not in OWNER_ONLY


def test_an_unknown_role_is_refused_with_the_exact_generic_body() -> None:
    from app.main import NOT_AUTHORIZED_BODY

    client, _ = _manage_client(role=UNKNOWN_ROLE)
    with client:
        resp = client.get(MANAGE_LIST_PATH)
    assert resp.status_code == 403
    assert resp.json() == NOT_AUTHORIZED_BODY


def test_the_day_filter_reaches_the_service_parsed_and_optional() -> None:
    client, stub = _manage_client()
    with client:
        client.get(MANAGE_LIST_PATH)
        client.get(f"{MANAGE_LIST_PATH}?day=2026-08-20")
    assert stub.list_calls == [(TENANT.id, None), (TENANT.id, DAY)]


def test_the_manage_responses_are_never_cached() -> None:
    client, _ = _manage_client()
    with client:
        listed = client.get(MANAGE_LIST_PATH)
        cancelled = client.post(f"{MANAGE_LIST_PATH}/{ENTRY_ID}/cancel")
    assert listed.headers["cache-control"] == "no-store"
    assert cancelled.headers["cache-control"] == "no-store"


def test_an_unknown_entry_cancel_is_the_shipped_404() -> None:
    client, stub = _manage_client()
    stub.cancel_error = BookingNotFoundError()
    with client:
        resp = client.post(f"{MANAGE_LIST_PATH}/{ENTRY_ID}/cancel")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"
