"""Fast API tests for `/w/{token}`'s three POSTs: stub services, hardcoded
TenantContext, no database — F22's file one surface over.

The service suite proves the transaction and the races; this one proves the HTTP
contract — anonymous, tenant-from-Host, cookie-blind, no-store, token-in-body —
and the exact error table. **D6's promise asserted as a literal: F23 adds ZERO
new error codes**, so a claim that loses a race is indistinguishable on the wire
from any other bride losing one.

It is also where `.memory/limiter-max-is-per-instance` is pinned at the WIRING
for the seventh time: `create_app` must hand the offer surface its OWN limiter
instance, never a key on the join's or the booking lookup's budget.
"""

import datetime
import uuid

import pytest
from fastapi.testclient import TestClient

from app.booking.service import (
    BookingClaim,
    DepositOutcome,
    SlotUnavailableError,
    TermsStaleError,
)
from app.main import create_app
from app.models.booking import Booking
from app.models.constants import BookingStatus, WaitlistEntryStatus
from app.tenancy.middleware import TenantContext
from app.waitlist.offer_service import (
    OfferNotClaimableError,
    OfferNotFoundError,
    WaitlistOfferService,
)
from app.waitlist.schemas import WaitlistOfferResponse
from app.waitlist.validation import WaitlistThrottledError

TENANT = TenantContext(id=uuid.uuid4(), slug="bella", name="בלה כלות", settings={})

LOOKUP_PATH = "/storefront/waitlist/offer"
CLAIM_PATH = "/storefront/waitlist/claim"
DECLINE_PATH = "/storefront/waitlist/decline"

TOKEN = "offer-token-abc"
SLOT = datetime.datetime(2026, 8, 23, 6, 0, tzinfo=datetime.UTC)
DEADLINE = datetime.datetime(2026, 8, 20, 9, 0, tzinfo=datetime.UTC)
BOOKING_ID = uuid.UUID("3fa85f64-5717-4562-b3fc-2c963f66afa6")

# The whole error surface these three routes can answer, and every row is a
# SHIPPED body. Asserted set-equal below against what this module exercises.
SPEC_ERROR_CODES = {
    "TENANT_NOT_FOUND",
    "VALIDATION_ERROR",
    "NOT_FOUND",
    "SLOT_UNAVAILABLE",
    "TERMS_STALE",
    "TOO_MANY_ATTEMPTS",
}


def _view(status: str = WaitlistEntryStatus.OFFERED.value) -> WaitlistOfferResponse:
    return WaitlistOfferResponse(
        status=status,
        starts_at=SLOT,
        expires_at=DEADLINE,
        appointment_type_name="מדידה ראשונה",
    )


def _booking(status: str = BookingStatus.CONFIRMED.value) -> Booking:
    return Booking(
        id=BOOKING_ID,
        tenant_id=TENANT.id,
        customer_id=uuid.uuid4(),
        appointment_type_id=uuid.uuid4(),
        starts_at=SLOT,
        seat_index=1,
        status=status,
        appointment_type_name="מדידה ראשונה",
        dress_name=None,
        dress_size=None,
    )


class StubOfferService:
    def __init__(self) -> None:
        self.error: Exception | None = None
        self.claims: list[tuple[uuid.UUID, str, str, int]] = []
        self.lookups: list[tuple[uuid.UUID, str]] = []
        self.declines: list[tuple[uuid.UUID, str]] = []

    async def lookup(self, tenant_id: uuid.UUID, *, token: str) -> WaitlistOfferResponse:
        if self.error is not None:
            raise self.error
        self.lookups.append((tenant_id, token))
        return _view()

    async def claim(
        self,
        tenant_id: uuid.UUID,
        *,
        token: str,
        name: str,
        terms_version: int,
        settings: object = None,
    ) -> BookingClaim:
        if self.error is not None:
            raise self.error
        self.claims.append((tenant_id, token, name, terms_version))
        return BookingClaim(
            booking=_booking(), created=True, manage_token="manage-token-1", deposit_due=False
        )

    async def decline(self, tenant_id: uuid.UUID, *, token: str) -> WaitlistOfferResponse:
        if self.error is not None:
            raise self.error
        self.declines.append((tenant_id, token))
        return _view(WaitlistEntryStatus.CANCELLED.value)


class StubBookingService:
    """Only `open_deposit`, which the claim route calls post-commit. The shipped
    one is unreachable here by construction — no gateway, no database."""

    def __init__(self, outcome: DepositOutcome | None = None) -> None:
        self.outcome = outcome
        self.calls: list[uuid.UUID] = []

    async def open_deposit(
        self, tenant_id: uuid.UUID, claim: BookingClaim, *, return_url: str
    ) -> DepositOutcome:
        self.calls.append(tenant_id)
        return self.outcome or DepositOutcome(
            status=claim.booking.status, deposit_due=claim.deposit_due
        )


class StubComms:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_confirmation(
        self, tenant: object, *, booking: Booking, manage_token: str
    ) -> bool:
        self.sent.append(manage_token)
        return True


def _client(
    stub: StubOfferService | None = None,
    *,
    host: str = "bella.localtest.me",
    bookings: StubBookingService | None = None,
    comms: StubComms | None = None,
) -> tuple[TestClient, StubOfferService, StubComms]:
    async def _resolver(slug: str) -> TenantContext | None:
        return TENANT if slug == "bella" else None

    app = create_app(resolver=_resolver)
    service = stub if stub is not None else StubOfferService()
    app.state.waitlist_offer_service = service
    app.state.booking_service = bookings or StubBookingService()
    sender = comms or StubComms()
    app.state.booking_comms_service = sender
    return TestClient(app, base_url=f"http://{host}"), service, sender


def _claim_body() -> dict[str, object]:
    return {"token": TOKEN, "name": "רותם לוי", "terms_version": 1}


def test_the_lookup_is_anonymous_and_answers_the_whole_view() -> None:
    client, stub, _ = _client()
    with client:
        assert client.cookies == {}
        resp = client.post(LOOKUP_PATH, json={"token": TOKEN})
    assert resp.status_code == 200
    # The WHOLE body. No phone echo, no entry id, no boutique name — the layout
    # already has the last from the host, and she typed neither of the others.
    assert resp.json() == {
        "status": WaitlistEntryStatus.OFFERED.value,
        "starts_at": SLOT.isoformat().replace("+00:00", "Z"),
        "expires_at": DEADLINE.isoformat().replace("+00:00", "Z"),
        "appointment_type_name": "מדידה ראשונה",
    }
    assert "set-cookie" not in resp.headers
    assert stub.lookups == [(TENANT.id, TOKEN)]


def test_the_token_never_reaches_the_url() -> None:
    """D7's rule, asserted rather than asserted-about: all three verbs are POSTs
    with the token in the BODY, so no access log, proxy or referrer header on the
    path ever holds a live claim credential."""
    client, _, _ = _client()
    with client:
        for path in (LOOKUP_PATH, CLAIM_PATH, DECLINE_PATH):
            assert client.get(path).status_code == 405
            assert f"{path}?token=" not in str(client.base_url)


def test_the_tenant_comes_from_the_host_and_never_from_the_body() -> None:
    client, stub, _ = _client()
    with client:
        client.post(CLAIM_PATH, json=_claim_body())
    assert stub.claims == [(TENANT.id, TOKEN, "רותם לוי", 1)]


def test_an_unresolved_host_is_a_404_before_the_service_is_reached() -> None:
    client, stub, _ = _client(host="nosuch.localtest.me")
    with client:
        resp = client.post(LOOKUP_PATH, json={"token": TOKEN})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "TENANT_NOT_FOUND"
    assert stub.lookups == []


def test_none_of_the_three_responses_is_ever_cached() -> None:
    client, _, _ = _client()
    with client:
        assert (
            client.post(LOOKUP_PATH, json={"token": TOKEN}).headers["cache-control"] == "no-store"
        )
        assert client.post(CLAIM_PATH, json=_claim_body()).headers["cache-control"] == "no-store"
        assert (
            client.post(DECLINE_PATH, json={"token": TOKEN}).headers["cache-control"] == "no-store"
        )


def test_the_claim_answers_201_with_the_booking_body() -> None:
    comms = StubComms()
    client, _, sender = _client(comms=comms)
    with client:
        resp = client.post(CLAIM_PATH, json=_claim_body())
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] == str(BOOKING_ID)
    assert body["status"] == BookingStatus.CONFIRMED.value
    assert body["deposit_due"] is False
    assert body["redirect_url"] is None
    # Nothing owed, so the confirmation goes out — the shipped condition, one
    # surface over.
    assert sender.sent == ["manage-token-1"]


def test_a_deposit_claim_hands_off_and_sends_no_confirmation() -> None:
    """§2.2: the deposit variant is F19's shipped hand-off, not a second
    checkout. Confirming an appointment before an agora is taken is a promise
    the boutique has not been paid for."""
    bookings = StubBookingService(
        DepositOutcome(
            status=BookingStatus.PENDING_PAYMENT.value,
            deposit_due=True,
            redirect_url="https://pay.example/session/1",
            payment_session_id="sess-1",
        )
    )
    client, _, sender = _client(bookings=bookings)
    with client:
        resp = client.post(CLAIM_PATH, json=_claim_body())
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == BookingStatus.PENDING_PAYMENT.value
    assert body["deposit_due"] is True
    assert body["redirect_url"] == "https://pay.example/session/1"
    assert sender.sent == []


def test_an_unknown_token_is_a_plain_404() -> None:
    stub = StubOfferService()
    stub.error = OfferNotFoundError()
    client, _, _ = _client(stub)
    with client:
        resp = client.post(LOOKUP_PATH, json={"token": "nope"})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_losing_the_seat_race_is_the_same_409_a_direct_booker_gets() -> None:
    stub = StubOfferService()
    stub.error = SlotUnavailableError()
    client, _, _ = _client(stub)
    with client:
        resp = client.post(CLAIM_PATH, json=_claim_body())
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "SLOT_UNAVAILABLE"


def test_a_dead_offer_answers_that_same_409_and_names_no_internal_state() -> None:
    """`OfferNotClaimableError` carries `claimed` / `expired` / `cancelled` for
    the log. The WIRE gets one code, because she is owed the outcome and not a
    report on which internal transition beat her — and a new code here would be
    an oracle over the waitlist's internals on an anonymous route."""
    stub = StubOfferService()
    stub.error = OfferNotClaimableError(WaitlistEntryStatus.CLAIMED.value)
    client, _, _ = _client(stub)
    with client:
        resp = client.post(CLAIM_PATH, json=_claim_body())
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "SLOT_UNAVAILABLE"
    assert WaitlistEntryStatus.CLAIMED.value not in resp.text


def test_stale_terms_are_the_shipped_409() -> None:
    stub = StubOfferService()
    stub.error = TermsStaleError()
    client, _, _ = _client(stub)
    with client:
        resp = client.post(CLAIM_PATH, json=_claim_body())
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "TERMS_STALE"


def test_the_anti_scrape_budget_is_the_shipped_429() -> None:
    stub = StubOfferService()
    stub.error = WaitlistThrottledError()
    client, _, _ = _client(stub)
    with client:
        resp = client.post(LOOKUP_PATH, json={"token": TOKEN})
    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "TOO_MANY_ATTEMPTS"


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"token": ""},
        {"token": TOKEN, "extra": "x"},
    ],
)
def test_a_malformed_lookup_body_is_the_shipped_validation_error(
    body: dict[str, object],
) -> None:
    """ForbidExtra is what keeps a field the schema deliberately omits from
    riding in as dead weight — and the answer is the SHIPPED 400, not FastAPI's
    raw 422, because both frontends read `response.data.error.message`."""
    client, stub, _ = _client()
    with client:
        resp = client.post(LOOKUP_PATH, json=body)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert stub.lookups == []


@pytest.mark.parametrize(
    "body",
    [
        {"token": TOKEN, "name": "רותם לוי"},
        {"token": TOKEN, "terms_version": 1},
        {"token": TOKEN, "name": "", "terms_version": 1},
        {"token": TOKEN, "name": "רותם לוי", "terms_version": 1, "phone": "050-1234567"},
    ],
)
def test_the_claim_takes_exactly_three_fields(body: dict[str, object]) -> None:
    """No phone (the entry carries the proven one), no verification token
    (possession of the offer token IS the proof), no dress, no consent, no
    notes. Each row above is one of those omissions being refused."""
    client, stub, _ = _client()
    with client:
        resp = client.post(CLAIM_PATH, json=body)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert stub.claims == []


def test_the_decline_answers_the_cancelled_view() -> None:
    client, stub, _ = _client()
    with client:
        resp = client.post(DECLINE_PATH, json={"token": TOKEN})
    assert resp.status_code == 200
    assert resp.json()["status"] == WaitlistEntryStatus.CANCELLED.value
    assert stub.declines == [(TENANT.id, TOKEN)]


def test_the_offer_surface_adds_no_error_code_of_its_own() -> None:
    """D6's promise, DRIVEN rather than declared: every failure these three
    routes can produce is answered with a body that shipped before F23. That is
    what lets the page reuse the whole `errors.*` map and add no new Hebrew, and
    it is why a set-equality assertion here is worth having — a new code would
    have to be added in two places to pass."""
    seen: set[str] = set()

    client, _, _ = _client(host="nosuch.localtest.me")
    with client:
        seen.add(client.post(LOOKUP_PATH, json={"token": TOKEN}).json()["error"]["code"])

    client, _, _ = _client()
    with client:
        seen.add(client.post(LOOKUP_PATH, json={}).json()["error"]["code"])

    for error in (
        OfferNotFoundError(),
        SlotUnavailableError(),
        TermsStaleError(),
        WaitlistThrottledError(),
        OfferNotClaimableError(WaitlistEntryStatus.EXPIRED.value),
    ):
        stub = StubOfferService()
        stub.error = error
        client, _, _ = _client(stub)
        with client:
            seen.add(client.post(CLAIM_PATH, json=_claim_body()).json()["error"]["code"])

    assert seen == SPEC_ERROR_CODES


def test_the_offer_surface_gets_its_own_limiter_instance() -> None:
    """`.memory/limiter-max-is-per-instance`, pinned at the WIRING. max_attempts
    lives on the LIMITER, not per key, so a key on the join's budget would let a
    waitlist rush close the offer surface — and the offer surface's own scrape
    budget could never trip first."""

    async def _resolver(slug: str) -> TenantContext | None:
        return TENANT if slug == "bella" else None

    app = create_app(resolver=_resolver)
    offers = app.state.waitlist_offer_service
    assert isinstance(offers, WaitlistOfferService)
    joins = app.state.waitlist_service
    assert offers._lookup_limiter is not joins._phone_limiter
    assert offers._lookup_limiter is not joins._tenant_limiter
    bookings = app.state.booking_service
    assert offers._lookup_limiter is not bookings._create_limiter
    assert offers._lookup_limiter is not bookings._phone_limiter
