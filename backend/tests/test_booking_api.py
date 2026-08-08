"""Fast API tests for the public booking POST: a stub BookingService + a
hardcoded TenantContext, no database (test_notifications_api.py style). The
db-marked service suite proves the claim; this file proves the HTTP contract —
route posture (anonymous, tenant-required, cookie-blind, no-store, POST-only)
and the exact error table from the F13 spec.

F16 adds one behaviour to this router that the wire cannot see: the confirmation
SMS fires post-commit, exactly once, and ONLY when the claim actually created a
booking. The 0009 replay path carries no raw token, so `test_a_replayed_create_*`
below is what keeps "a replay must not resend" from silently regressing into a
second text for the same appointment.
"""

import dataclasses
import datetime
import uuid
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_auth_service
from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.service import StaffContext
from app.booking.service import (
    BookingClaim,
    BookingNotFoundError,
    BookingService,
    BookingThrottledError,
    DepositOutcome,
    PhoneNotVerifiedError,
    DressUnavailableError,
    SlotUnavailableError,
    TermsStaleError,
)
from app.booking.validation import BookingValidationError
from app.main import create_app
from app.models.booking import Booking
from app.models.constants import BookingStatus
from app.payments.service import DepositHold, PaymentService
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


MANAGE_TOKEN = "manage-token-abc"
DEPOSIT_AGOROT = 15_000
SESSION_ID = "fake-7"
REDIRECT_URL = f"/fake-pay?session={SESSION_ID}"


class StubBookingService:
    """The router is a thin delegate, so the stub is programmable outcomes and
    a call log — nothing else.

    `created` is programmable because the router branches on it: True is a fresh
    claim (confirmation SMS), False is the 0009 replay (no token, no SMS).
    `status` and `outcome` are programmable for the same reason on F19's deposit
    path: the claim's intent and the deposit step's OUTCOME are different facts,
    and MD4 is precisely the case where they disagree."""

    def __init__(
        self,
        *,
        created: bool = True,
        status: str = BookingStatus.CONFIRMED.value,
        deposit_due: bool = False,
        outcome: DepositOutcome | None = None,
    ) -> None:
        self.error: Exception | None = None
        self.created = created
        self.status = status
        self.deposit_due = deposit_due
        self.outcome = outcome
        self.calls: list[dict[str, Any]] = []
        self.deposit_calls: list[dict[str, Any]] = []

    async def create_booking(self, tenant_id: uuid.UUID, **kwargs: Any) -> BookingClaim:
        if self.error is not None:
            raise self.error
        self.calls.append({"tenant_id": tenant_id, **kwargs})
        row = _Row(
            id=BOOKING_ID,
            starts_at=kwargs["starts_at"],
            status=self.status,
            appointment_type_name="מדידת שמלה",
            dress_name=None,
            dress_size=None,
        )
        return BookingClaim(
            booking=cast(Booking, row),
            created=self.created,
            manage_token=MANAGE_TOKEN if self.created else None,
            deposit_due=self.deposit_due,
            deposit_amount_agorot=DEPOSIT_AGOROT if self.deposit_due else 0,
        )

    async def open_deposit(
        self, tenant_id: uuid.UUID, claim: BookingClaim, *, return_url: str
    ) -> DepositOutcome:
        self.deposit_calls.append({"tenant_id": tenant_id, "return_url": return_url})
        if self.outcome is not None:
            return self.outcome
        return DepositOutcome(status=claim.booking.status, deposit_due=False)


class StubCommsService:
    """Records the confirmation sends the router fires post-commit. Never raises:
    the real service swallows both provider exceptions after their evidence rows
    exist, because a committed booking must stay a 201 (D4)."""

    def __init__(self) -> None:
        self.confirmations: list[tuple[uuid.UUID, str]] = []

    async def send_confirmation(self, tenant: Any, *, booking: Any, manage_token: str) -> bool:
        self.confirmations.append((booking.id, manage_token))
        return True


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
    client, service, _ = _client_with_comms(stub, host=host)
    return client, service


def _client_with_comms(
    stub: StubBookingService | None = None, *, host: str = "bella.localtest.me"
) -> tuple[TestClient, StubBookingService, StubCommsService]:
    async def _resolver(slug: str) -> TenantContext | None:
        return TENANT if slug == "bella" else None

    app = create_app(resolver=_resolver)
    service = stub if stub is not None else StubBookingService()
    comms = StubCommsService()
    app.state.booking_service = service
    app.state.booking_comms_service = comms
    auth = FakeAuthService()
    app.state.auth_service = auth
    app.dependency_overrides[get_auth_service] = lambda: auth
    return TestClient(app, base_url=f"http://{host}"), service, comms


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
        "deposit_due": False,
        "redirect_url": None,
        "payment_session_id": None,
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
        # F28. A SEPARATE code from SLOT_UNAVAILABLE and that is the decision:
        # the remedy is another DATE for this dress, not another time, and every
        # time on the blocked day is equally refused.
        (DressUnavailableError(), 409, "DRESS_UNAVAILABLE"),
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


# --- F16: the confirmation SMS is post-commit, once, and never on a replay ---


def test_a_fresh_claim_fires_exactly_one_confirmation_with_the_raw_token() -> None:
    client, _, comms = _client_with_comms()
    with client:
        resp = client.post(PATH, json=_body())
    assert resp.status_code == 201
    assert comms.confirmations == [(BOOKING_ID, MANAGE_TOKEN)]


def test_a_replayed_create_sends_no_second_confirmation() -> None:
    """0009's idempotency path returns the EXISTING booking, and the spent
    verification token means a bride on a flaky network really does resubmit. A
    second "your appointment is confirmed" for one appointment is the regression
    this pins — and the router cannot cause it by accident, because a replay
    carries no raw token to put in a link."""
    client, _, comms = _client_with_comms(StubBookingService(created=False))
    with client:
        resp = client.post(PATH, json=_body())
    assert resp.status_code == 201
    assert comms.confirmations == []


def test_a_rejected_claim_sends_nothing() -> None:
    stub = StubBookingService()
    stub.error = SlotUnavailableError()
    client, _, comms = _client_with_comms(stub)
    with client:
        resp = client.post(PATH, json=_body())
    assert resp.status_code == 409
    assert comms.confirmations == []


# --- F19 D11: the deposit moves the SMS and adds three fields to the wire ---


def _deposit_stub(**overrides: Any) -> StubBookingService:
    """A claim that owes a deposit: committed `pending_payment`, hold opened."""
    kwargs: dict[str, Any] = {
        "status": BookingStatus.PENDING_PAYMENT.value,
        "deposit_due": True,
        "outcome": DepositOutcome(
            status=BookingStatus.PENDING_PAYMENT.value,
            deposit_due=True,
            redirect_url=REDIRECT_URL,
            payment_session_id=SESSION_ID,
        ),
    }
    kwargs.update(overrides)
    return StubBookingService(**kwargs)


def test_a_deposit_booking_answers_pending_payment_with_the_checkout_link() -> None:
    client, stub, comms = _client_with_comms(_deposit_stub())
    with client:
        resp = client.post(PATH, json=_body())
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == BookingStatus.PENDING_PAYMENT.value
    assert body["deposit_due"] is True
    assert body["redirect_url"] == REDIRECT_URL
    assert body["payment_session_id"] == SESSION_ID
    # The whole point of D11's ordering: no "your appointment is confirmed"
    # before a single agora is taken.
    assert comms.confirmations == []
    # Post-commit, and pointed back at the storefront she is standing on.
    [call] = stub.deposit_calls
    assert call["tenant_id"] == TENANT.id
    assert call["return_url"] == "http://bella.localtest.me/"


def test_the_create_hands_the_tenants_settings_to_the_predicate() -> None:
    """D19's master toggle lives in `tenants.settings`, and an ABSENT toggle
    reads as off — so a router that forgot this argument would silently book
    every deposit-required appointment for free."""
    client, stub, _ = _client_with_comms()
    with client:
        client.post(PATH, json=_body())
    [call] = stub.calls
    assert call["settings"] is TENANT.settings


def test_a_booking_with_no_deposit_carries_neither_link_nor_flag() -> None:
    client, stub, comms = _client_with_comms()
    with client:
        resp = client.post(PATH, json=_body())
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == BookingStatus.CONFIRMED.value
    assert (body["deposit_due"], body["redirect_url"], body["payment_session_id"]) == (
        False,
        None,
        None,
    )
    assert comms.confirmations == [(BOOKING_ID, MANAGE_TOKEN)]
    # Called on this path too — it is the service that decides there is nothing
    # to open, so the router cannot forget the branch that owes money.
    assert len(stub.deposit_calls) == 1


def test_the_replay_branch_hands_back_the_same_link() -> None:
    """D11b. The lost-201 retry lands on 0009's replay path, and the hold it
    converges onto is the FIRST one — same session, same hosted page. A second
    link here would be a second payable page for one appointment."""
    client, _, comms = _client_with_comms(_deposit_stub(created=False))
    with client:
        first = client.post(PATH, json=_body())
        second = client.post(PATH, json=_body())
    assert first.status_code == second.status_code == 201
    assert first.json()["redirect_url"] == second.json()["redirect_url"] == REDIRECT_URL
    assert first.json()["payment_session_id"] == second.json()["payment_session_id"] == SESSION_ID
    assert comms.confirmations == []


def test_md4_a_compensated_booking_is_confirmed_and_texted() -> None:
    """MD4 / D11a at the wire: the claim owed a deposit, the gateway was
    unreachable, the compensating transaction booked her anyway — so she gets
    the ordinary confirmation SMS and no checkout link, and the response shows
    `confirmed` even though the row this handler holds still reads
    `pending_payment`."""
    stub = _deposit_stub(
        outcome=DepositOutcome(status=BookingStatus.CONFIRMED.value, deposit_due=False)
    )
    client, _, comms = _client_with_comms(stub)
    with client:
        resp = client.post(PATH, json=_body())
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == BookingStatus.CONFIRMED.value
    assert (body["deposit_due"], body["redirect_url"], body["payment_session_id"]) == (
        False,
        None,
        None,
    )
    assert comms.confirmations == [(BOOKING_ID, MANAGE_TOKEN)]


# --- F19 D11b: BookingService.open_deposit, against a fake PaymentService ---
#
# No database: the success and converge paths never open a session. The
# compensating path does, and its assertions live in test_deposit_create_db.py.


@dataclasses.dataclass
class _FakeHoldPayment:
    provider_session_id: str


class _FakePaymentService:
    def __init__(self, *, created: bool, session_id: str, redirect_url: str | None) -> None:
        self.hold = DepositHold(
            payment=cast(Any, _FakeHoldPayment(provider_session_id=session_id)),
            redirect_url=redirect_url,
            created=created,
        )
        self.calls: list[dict[str, Any]] = []

    async def open_deposit(self, tenant_id: uuid.UUID, **kwargs: Any) -> DepositHold:
        self.calls.append({"tenant_id": tenant_id, **kwargs})
        return self.hold


def _service(payments: _FakePaymentService) -> BookingService:
    limiter = FixedWindowRateLimiter(max_attempts=1000, window_seconds=60, clock=lambda: 0.0)
    return BookingService(
        cast(Any, None),
        otp=cast(Any, None),
        create_limiter=limiter,
        phone_limiter=limiter,
        payments=cast(PaymentService, payments),
        deposit_hold_seconds=900,
    )


def _claim(*, status: str, deposit_due: bool = True) -> BookingClaim:
    row = _Row(
        id=BOOKING_ID,
        starts_at=STARTS_AT,
        status=status,
        appointment_type_name="מדידת שמלה",
        dress_name=None,
        dress_size=None,
    )
    return BookingClaim(
        booking=cast(Booking, row),
        created=False,
        manage_token=None,
        deposit_due=deposit_due,
        deposit_amount_agorot=DEPOSIT_AGOROT,
    )


async def test_open_deposit_returns_the_stored_link_on_the_converge_path() -> None:
    payments = _FakePaymentService(created=False, session_id=SESSION_ID, redirect_url=REDIRECT_URL)
    outcome = await _service(payments).open_deposit(
        TENANT.id,
        _claim(status=BookingStatus.PENDING_PAYMENT.value),
        return_url="http://bella.localtest.me/",
    )
    assert outcome == DepositOutcome(
        status=BookingStatus.PENDING_PAYMENT.value,
        deposit_due=True,
        redirect_url=REDIRECT_URL,
        payment_session_id=SESSION_ID,
    )
    [call] = payments.calls
    assert call["booking_id"] == BOOKING_ID
    assert call["amount_agorot"] == DEPOSIT_AGOROT
    assert call["hold_seconds"] == 900


async def test_open_deposit_does_nothing_when_no_deposit_is_due() -> None:
    payments = _FakePaymentService(created=True, session_id=SESSION_ID, redirect_url=REDIRECT_URL)
    outcome = await _service(payments).open_deposit(
        TENANT.id,
        _claim(status=BookingStatus.CONFIRMED.value, deposit_due=False),
        return_url="http://bella.localtest.me/",
    )
    assert outcome == DepositOutcome(status=BookingStatus.CONFIRMED.value, deposit_due=False)
    assert payments.calls == []


async def test_a_replay_of_an_already_paid_booking_opens_no_second_hold() -> None:
    """`active_at`'s predicate is `status != 'cancelled'`, so a replay can hand
    back a booking she has ALREADY paid for. `live_pending_for_booking` would
    find no pending row to converge onto and mint a second hosted page — a
    second charge for one appointment. The status guard is what stops it."""
    payments = _FakePaymentService(created=True, session_id="fake-2", redirect_url="/fake-pay?x")
    outcome = await _service(payments).open_deposit(
        TENANT.id,
        _claim(status=BookingStatus.CONFIRMED.value),
        return_url="http://bella.localtest.me/",
    )
    assert outcome == DepositOutcome(status=BookingStatus.CONFIRMED.value, deposit_due=False)
    assert payments.calls == []


async def test_the_marketing_consent_flag_defaults_off_and_rides_through_unchanged() -> None:
    """⚠ F20 D6. The DEFAULT is the compliance property, not a convenience: an
    omitted key must never be able to mean "she agreed", and a client that has
    not been updated yet must not consent anybody by silence.

    The unbundling is structural elsewhere (the checkbox sits on the `details`
    step, two navigations from the required terms checkbox on `terms`). What
    this asserts is the wire half — the flag is its own field, it is not derived
    from `terms_version`, and the router passes it through untouched.
    """
    client, stub = _client()
    with client:
        assert client.post(PATH, json=_body()).status_code == 201
        assert stub.calls[-1]["marketing_consent"] is False

        assert client.post(PATH, json=_body(marketing_consent=True)).status_code == 201
        assert stub.calls[-1]["marketing_consent"] is True
        # Accepting the terms is a DIFFERENT act on a different screen; nothing
        # about it may imply a marketing consent.
        assert stub.calls[-1]["terms_version"] == 1
