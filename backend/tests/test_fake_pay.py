"""F19 Task 14 (D21): the dev-only /fake-pay harness.

`FakeGateway` never posts a webhook to anything, so without this page a staging
deposit redirects to a 404, waits on the awaiting-payment screen forever, and is
cancelled by the sweeper one tick later — the inverse of the flow it is meant to
demonstrate. Three things are asserted and nothing else:

1. **The route does not exist unless the fake gateway is the configured
   provider.** That is the whole production guard: `Settings`'s
   `_forbid_fake_payment_paths_in_production` already boot-fails
   `payment_provider="fake"` under `APP_ENV=production`, so "the provider is
   fake" IS "this is not production" and no second notion of production is
   invented here.
2. **The button's payload verifies.** The signature the page embeds is checked
   against `FakeGateway.verify_webhook` through the real webhook route — if the
   body and the signature disagreed by one byte the route would answer 400.
3. **The secret never reaches the page.** A harness that renders the boutique's
   webhook secret into HTML would be worse than no harness.

Fast by construction: the page's two DB-shaped facts (the payment's amount and
the tenant's credentials) come from a stub, the same shape
test_payments_webhook_api.py uses for `DepositBookingService`.
"""

import html
import re
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.payments.base import GatewayCredentials
from app.payments.fake import FAKE_PROVIDER, FakeGateway
from app.payments.fake_pay import FakePayFacts, register_fake_pay
from app.payments.validation import FAKE_PAY_PATH
from app.payments.webhook_router import SIGNATURE_HEADER
from app.tenancy.middleware import TenantContext

TENANT = TenantContext(id=uuid.uuid4(), slug="bella", name="בלה כלות", settings={})
SESSION_ID = "fake-1"
AMOUNT = 30000
SECRET = "whsec-not-a-real-secret"
WEBHOOK_PATH = "/storefront/payments/webhook"


def _settings(**overrides: Any) -> Settings:
    return Settings(app_env="dev", gateway_secret_box="fake", **overrides)


def _paths(node: Any) -> Iterator[str]:
    """test_storefront_api.py's walker, for its reason: FastAPI wraps an included
    router in a `_IncludedRouter` rather than flattening it, so reading
    `app.routes` alone would find nothing and the guard below would pass
    vacuously in BOTH directions."""
    for route in getattr(node, "routes", []):
        inner = getattr(route, "original_router", None)
        if inner is not None:
            yield from _paths(inner)
            continue
        path = getattr(route, "path", None)
        if path is not None:
            yield path


# --- the guard --------------------------------------------------------------


@pytest.mark.parametrize("provider", [None, "lemonsqueezy"])
def test_the_route_does_not_exist_unless_the_provider_is_fake(provider: str | None) -> None:
    """Absent, not 404-ing: a real gateway deployment must not carry a page that
    mints its own settlements, and `payment_provider != "fake"` is the only
    condition consulted — production is unreachable here because Settings
    already refuses to boot as fake."""
    app = FastAPI()
    register_fake_pay(app, _settings(payment_provider=provider))
    assert FAKE_PAY_PATH not in set(_paths(app))


def test_the_route_exists_when_the_provider_is_fake() -> None:
    app = FastAPI()
    register_fake_pay(app, _settings(payment_provider=FAKE_PROVIDER))
    assert FAKE_PAY_PATH in set(_paths(app))


def test_production_cannot_reach_the_route_because_it_cannot_boot() -> None:
    """The reused guard, stated as a test so the two cannot drift: there is no
    `app_env` check in fake_pay.py because a production app carrying
    `payment_provider="fake"` does not exist."""
    with pytest.raises(ValueError, match="PAYMENT_PROVIDER"):
        Settings(
            app_env="production",
            database_url="postgresql+asyncpg://u:p@h/db",
            base_domain="example.com",
            # The Literal the Settings field declares, not FAKE_PROVIDER — the
            # two are the same string and mypy only accepts the literal here.
            payment_provider="fake",
            gateway_secret_box="fake",
        )


# --- what the page produces -------------------------------------------------


class StubFakePay:
    def __init__(self) -> None:
        self.calls: list[tuple[uuid.UUID, str]] = []

    async def facts(self, tenant_id: uuid.UUID, *, session_id: str) -> FakePayFacts:
        self.calls.append((tenant_id, session_id))
        return FakePayFacts(amount_agorot=AMOUNT, webhook_secret=SECRET)


class SettleThroughTheRealGateway:
    """The webhook route's collaborator, reduced to the one thing under test:
    the genuine HMAC comparison in `FakeGateway.verify_webhook`."""

    def __init__(self) -> None:
        self.gateway = FakeGateway()
        self.credentials = GatewayCredentials(
            provider=FAKE_PROVIDER, fields={"webhook_secret": SECRET}
        )

    async def settle(self, tenant: Any, *, body: bytes, signature: str) -> None:
        self.gateway.verify_webhook(self.credentials, body=body, signature=signature)


def _client() -> tuple[TestClient, StubFakePay]:
    async def _resolver(slug: str) -> TenantContext | None:
        return TENANT if slug == "bella" else None

    app = create_app(resolver=_resolver)
    # create_app only registers the page when the deployment is fake, and the
    # test env is not — register it here rather than mutate the environment.
    register_fake_pay(app, _settings(payment_provider=FAKE_PROVIDER))
    stub = StubFakePay()
    app.state.fake_pay_service = stub
    app.state.deposit_booking_service = SettleThroughTheRealGateway()
    return TestClient(app, base_url="http://bella.localtest.me"), stub


def _payloads(page: str) -> dict[str, tuple[bytes, str]]:
    """The two buttons' data attributes, unescaped the way a browser would."""
    return {
        outcome: (html.unescape(body).encode(), signature)
        for outcome, body, signature in re.findall(
            r'data-outcome="([^"]+)" data-body="([^"]*)" data-signature="([^"]*)"', page
        )
    }


def test_the_page_offers_pay_and_decline_for_the_session_in_the_query() -> None:
    client, stub = _client()
    response = client.get(f"/fake-pay?session={SESSION_ID}")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert stub.calls == [(TENANT.id, SESSION_ID)]
    assert set(_payloads(response.text)) == {"pay", "decline"}


@pytest.mark.parametrize("outcome", ["pay", "decline"])
def test_the_webhook_route_accepts_the_payload_the_page_built(outcome: str) -> None:
    """The assertion the harness exists for. A 400 here means the page signed
    bytes other than the ones it embedded, which on staging would look exactly
    like a broken gateway."""
    client, _ = _client()
    body, signature = _payloads(client.get(f"/fake-pay?session={SESSION_ID}").text)[outcome]
    accepted = client.post(WEBHOOK_PATH, content=body, headers={SIGNATURE_HEADER: signature})
    assert accepted.status_code == 200


def test_a_tampered_payload_is_rejected() -> None:
    """The negative half — otherwise the test above would pass against a route
    that verified nothing."""
    client, _ = _client()
    body, signature = _payloads(client.get(f"/fake-pay?session={SESSION_ID}").text)["pay"]
    rejected = client.post(WEBHOOK_PATH, content=body + b" ", headers={SIGNATURE_HEADER: signature})
    assert rejected.status_code == 400


def test_the_page_carries_the_amount_but_never_the_secret() -> None:
    client, _ = _client()
    html = client.get(f"/fake-pay?session={SESSION_ID}").text
    assert str(AMOUNT) in html
    assert SECRET not in html


def test_the_paid_flag_is_what_separates_the_two_buttons() -> None:
    client, _ = _client()
    payloads = _payloads(client.get(f"/fake-pay?session={SESSION_ID}").text)
    assert b'"paid": true' in payloads["pay"][0]
    assert b'"paid": false' in payloads["decline"][0]
    # Distinct transaction ids: `settle_from_webhook` short-circuits on a
    # transaction it has already seen, so a shared id would make "decline then
    # pay" a silent no-op — the demo's most likely click order.
    assert payloads["pay"][0] != payloads["decline"][0]
