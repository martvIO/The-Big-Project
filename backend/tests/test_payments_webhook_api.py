"""F19 Task 6: the webhook sibling router and the poll beside it.

Fast by construction — a stub DepositBookingService and a hardcoded
TenantContext, the test_booking_api.py shape. Three things live here and nowhere
else:

1. **D9's status contract.** 200 on every non-forgery outcome and 400 on the
   three that raise, because a provider reads a non-2xx as "retry" and a decline
   retried forever is the failure D25's 400-vs-503 argument is made of.
2. **The RAW body reaches the verifier.** `verify_webhook` HMACs the exact bytes
   the provider signed, so a route that parsed and re-serialised the JSON would
   reject every genuine webhook. The assertion is byte equality against a body
   whose key order and spacing no serialiser would reproduce.
3. **D4's branch table, as a pure function.** `deposit_reaction` maps a
   `Settlement` to what F19 does about it, and the table is driven from
   `settlement.payment.status` — never from `newly_settled`, which is False on
   five distinct outcomes including the two that must confirm and honour.

The route posture (anonymous, cookie-blind, no-store, tenant-from-Host) is the
OTP/booking posture and is asserted the same way. The confirm transaction and
the honour path are `db`-marked and live in test_deposit_confirm_db.py.
"""

import datetime
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_auth_service
from app.auth.service import StaffContext
from app.errors import DomainNotFoundError
from app.main import create_app
from app.models.constants import BookingStatus, PaymentStatus
from app.models.payment import Payment
from app.payments.base import GatewayWebhookInvalidError
from app.payments.service import Settlement
from app.payments.webhook_router import (
    SIGNATURE_HEADER,
    DepositReaction,
    PaymentStatusFacts,
    deposit_reaction,
)
from app.payments.webhook_router import (
    router as webhook_router,
)
from app.security_headers import SECURITY_HEADERS
from app.tenancy.middleware import TenantContext

TENANT = TenantContext(id=uuid.uuid4(), slug="bella", name="בלה כלות", settings={})
STAFF_ID = uuid.uuid4()
TOKEN = "session-token-abc"

WEBHOOK_PATH = "/storefront/payments/webhook"
STATUS_PATH = "/storefront/booking/payment-status"
SESSION_ID = "fake-1"
PAID_AT = datetime.datetime(2026, 8, 3, 9, 30, tzinfo=datetime.UTC)

# Deliberately NOT what json.dumps would emit: unsorted keys, ragged spacing, a
# trailing newline. Any route that round-tripped this through a model would hand
# the verifier different bytes and break every real signature.
RAW_BODY = b'{"provider_transaction_id":"txn-9",   "paid": true,"provider_session_id":"fake-1"}\n'
SIGNATURE = "0f" * 32


def _payment(status: str, *, paid_at: datetime.datetime | None = None) -> Payment:
    return Payment(
        id=uuid.uuid4(),
        tenant_id=TENANT.id,
        booking_id=uuid.uuid4(),
        provider="fake",
        amount_agorot=30000,
        status=status,
        provider_session_id=SESSION_ID,
        paid_at=paid_at,
    )


class StubDeposits:
    """The router is a thin delegate, so the stub is a call log plus a
    programmable raise."""

    def __init__(self) -> None:
        self.settlements: list[tuple[uuid.UUID, bytes, str]] = []
        self.status_calls: list[tuple[uuid.UUID, str]] = []
        self.error: Exception | None = None
        self.facts = PaymentStatusFacts(
            booking_status=BookingStatus.CONFIRMED.value,
            payment_status=PaymentStatus.PAID.value,
            paid_at=PAID_AT,
        )

    async def settle(self, tenant: Any, *, body: bytes, signature: str) -> None:
        if self.error is not None:
            raise self.error
        self.settlements.append((tenant.id, body, signature))

    async def payment_status(
        self, tenant_id: uuid.UUID, *, provider_session_id: str
    ) -> PaymentStatusFacts:
        if self.error is not None:
            raise self.error
        self.status_calls.append((tenant_id, provider_session_id))
        return self.facts


class FakeAuthService:
    """Only so the owner cookie in the cookie-blindness test is a genuinely
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
    stub: StubDeposits | None = None, *, host: str = "bella.localtest.me"
) -> tuple[TestClient, StubDeposits]:
    async def _resolver(slug: str) -> TenantContext | None:
        return TENANT if slug == "bella" else None

    app = create_app(resolver=_resolver)
    # create_app owns the router table; this file must not depend on whether the
    # wiring commit has landed yet, and must not double-register once it has.
    if not any(getattr(route, "path", None) == WEBHOOK_PATH for route in app.routes):
        app.include_router(webhook_router)
    deposits = stub if stub is not None else StubDeposits()
    app.state.deposit_booking_service = deposits
    auth = FakeAuthService()
    app.state.auth_service = auth
    app.dependency_overrides[get_auth_service] = lambda: auth
    return TestClient(app, base_url=f"http://{host}"), deposits


def _post(client: TestClient) -> Any:
    return client.post(WEBHOOK_PATH, content=RAW_BODY, headers={SIGNATURE_HEADER: SIGNATURE})


# --- D4's branch table, with no I/O at all ----------------------------------


@pytest.mark.parametrize("newly_settled", [True, False])
@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (PaymentStatus.PAID.value, DepositReaction.CONFIRM),
        (PaymentStatus.EXPIRED.value, DepositReaction.HONOUR),
        (PaymentStatus.PENDING.value, DepositReaction.IGNORE),
        (PaymentStatus.FAILED.value, DepositReaction.IGNORE),
    ],
)
def test_the_outcome_is_read_off_the_row_status(
    status: str, expected: DepositReaction, newly_settled: bool
) -> None:
    """`newly_settled` is parametrized ACROSS the table on purpose: it is False
    on five distinct outcomes — a redelivery of a settled txn, a decline, a
    concurrent loser, a different txn on a paid row, and a late settlement — so
    gating on it would collapse rows that must not collapse. Flipping it must
    change nothing."""
    settlement = Settlement(payment=_payment(status), newly_settled=newly_settled)
    assert deposit_reaction(settlement) == expected


def test_a_paid_row_confirms_even_when_nothing_was_newly_settled() -> None:
    """Race row #11, and the reason this row exists at all. `settle_from_webhook`
    commits payments->paid inside its OWN transaction and returns, so the
    booking-confirm is necessarily a SECOND one. A process death in that window
    leaves the card charged and the booking stuck at `pending_payment` — seat
    held, no SMS, no reminder, no alert, and 0009's index blocking her from
    rebooking. The redelivery is the repair, and it is a no-op against a booking
    that is already confirmed."""
    stranded = Settlement(payment=_payment(PaymentStatus.PAID.value), newly_settled=False)
    assert deposit_reaction(stranded) == DepositReaction.CONFIRM


# --- D9's status contract ---------------------------------------------------


def test_every_non_forgery_outcome_is_200() -> None:
    """Paid, decline, redelivery, duplicate transaction, late settlement — every
    one of them returns from `settle` without raising, so the route's answer is
    the same 200 for all five. A provider reads anything else as "retry", and
    retrying a decline forever turns a transient outage into permanently
    unconfirmed bookings. Which outcome the service picked is `deposit_reaction`'s
    table above; that it does not change the STATUS is this test."""
    client, deposits = _client()
    with client:
        resp = _post(client)
    assert resp.status_code == 200
    assert resp.json() == {}
    assert len(deposits.settlements) == 1


def test_a_rejected_webhook_is_400() -> None:
    """One error, three conditions, and they are not the same event: a forged
    signature, an amount mismatch, and a signature-valid webhook matching no
    payment row. All three already raise from PaymentService and main.py already
    maps the error to 400 — this asserts the route does not swallow it."""
    stub = StubDeposits()
    stub.error = GatewayWebhookInvalidError()
    client, _ = _client(stub)
    with client:
        resp = _post(client)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "GATEWAY_WEBHOOK_INVALID"


def test_the_raw_body_bytes_reach_the_service() -> None:
    """The regression guard the spec names by hand: a route that re-serialised
    the JSON would hand `verify_webhook` different bytes from the ones the
    provider HMAC'd, and every genuine webhook would 400."""
    client, deposits = _client()
    with client:
        _post(client)
    [(tenant_id, body, signature)] = deposits.settlements
    assert body == RAW_BODY
    assert signature == SIGNATURE
    assert tenant_id == TENANT.id


def test_a_missing_signature_header_still_reaches_the_verifier() -> None:
    """Empty, not a 422. Authenticity is the verifier's call and its answer is a
    400 with an audit row; a schema rejection here would leave no evidence."""
    client, deposits = _client()
    with client:
        resp = client.post(WEBHOOK_PATH, content=RAW_BODY)
    assert resp.status_code == 200
    assert deposits.settlements[0][2] == ""


# --- the route posture ------------------------------------------------------


def test_the_webhook_is_anonymous_and_no_store() -> None:
    client, _ = _client()
    with client:
        assert client.cookies == {}
        resp = _post(client)
    assert resp.status_code == 200
    assert "set-cookie" not in resp.headers
    assert resp.headers["cache-control"] == "no-store"
    assert {header: resp.headers.get(header) for header in SECURITY_HEADERS} == SECURITY_HEADERS


def test_an_owner_cookie_changes_nothing() -> None:
    """Cookie-blind, which is what makes "CSRF is structurally N/A" true rather
    than remembered: there is no ambient credential a cross-site request could
    ride."""
    anon, _ = _client()
    with anon:
        anonymous = _post(anon)

    carried, _ = _client()
    with carried:
        carried.cookies.set("boutique_session", TOKEN, domain="bella.localtest.me")
        with_cookie = _post(carried)

    assert with_cookie.status_code == anonymous.status_code == 200
    assert with_cookie.json() == anonymous.json()
    assert "set-cookie" not in with_cookie.headers


def test_an_unknown_host_is_tenant_not_found() -> None:
    client, deposits = _client(host="nosuch.localtest.me")
    with client:
        resp = _post(client)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "TENANT_NOT_FOUND"
    assert deposits.settlements == []


def test_the_webhook_is_post_only() -> None:
    client, _ = _client()
    with client:
        assert client.get(WEBHOOK_PATH).status_code == 405


def test_the_webhook_is_not_under_manage() -> None:
    """Not a formality: CsrfOriginMiddleware and the default-deny role walker
    both key on the /manage prefix, and a webhook under it would need an
    exemption in each."""
    assert not WEBHOOK_PATH.startswith("/manage")
    assert not STATUS_PATH.startswith("/manage")


# --- the poll ---------------------------------------------------------------


def test_the_poll_answers_the_three_facts_and_no_pii() -> None:
    client, deposits = _client()
    with client:
        resp = client.post(STATUS_PATH, json={"payment_session_id": SESSION_ID})
    assert resp.status_code == 200
    assert resp.json() == {
        "booking_status": BookingStatus.CONFIRMED.value,
        "payment_status": PaymentStatus.PAID.value,
        "paid_at": "2026-08-03T09:30:00Z",
    }
    assert deposits.status_calls == [(TENANT.id, SESSION_ID)]


def test_the_poll_is_keyed_on_the_session_id_not_the_manage_token() -> None:
    """D13. The manage token cannot work here three times over:
    `BookingCreateResponse` carries no token, the deposit path suppresses the
    confirmation SMS so she never receives the manage link, and
    `set_manage_token_hash` overwrites the hash unconditionally while
    `by_manage_token_hash` is the only lookup — so a token-keyed poll would
    start 404-ing at precisely the moment it should return paid."""
    client, deposits = _client()
    with client:
        resp = client.post(STATUS_PATH, json={"token": "manage-token-abc"})
    assert resp.status_code == 400
    assert deposits.status_calls == []


def test_an_unknown_session_id_is_404() -> None:
    stub = StubDeposits()
    stub.error = DomainNotFoundError("no such payment session")
    client, _ = _client(stub)
    with client:
        resp = client.post(STATUS_PATH, json={"payment_session_id": "nope"})
    assert resp.status_code == 404


def test_the_poll_is_cookie_blind_and_no_store() -> None:
    client, _ = _client()
    with client:
        client.cookies.set("boutique_session", TOKEN, domain="bella.localtest.me")
        resp = client.post(STATUS_PATH, json={"payment_session_id": SESSION_ID})
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "no-store"
    assert "set-cookie" not in resp.headers


def test_the_poll_is_post_only() -> None:
    """POST for a read, the /booking/lookup precedent: a GET would put the
    session id in the query string and from there into every access log."""
    client, _ = _client()
    with client:
        assert client.get(STATUS_PATH).status_code == 405
