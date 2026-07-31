"""LemonSqueezyGateway against a faked transport. Fast: no network, no db, no cost.

The live API is NEVER reached from here, and that is a safety property rather
than a speed one: POST /v1/checkouts against the supplied store could mint a
LIVE checkout, and whether Test Mode is toggled on that store is unconfirmed
(spec Risk 2). Every response in this file is fabricated.

The test_notifications_twilio.py shape — `httpx.MockTransport` injected through
the adapter's one test seam — plus the test_payments_adapters.py discipline of
asserting rejections BY TYPE: an assertion that any exception escaped is exactly
what lets D25's 400-vs-503 misclassification ship green.
"""

import datetime
import hashlib
import hmac
import json
import logging
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.main import _build_payment_gateway
from app.payments.base import (
    GatewayCredentials,
    GatewayCredentialsRejectedError,
    GatewayUnavailableError,
    GatewayWebhookInvalidError,
    PaymentGateway,
    PaymentSession,
    WebhookEvent,
)
from app.payments.fake import FakeGateway
from app.payments.lemonsqueezy import (
    CONNECT_TIMEOUT_SECONDS,
    JSON_API_MEDIA_TYPE,
    LEMONSQUEEZY_CREDENTIAL_FIELDS,
    LEMONSQUEEZY_PROVIDER,
    READ_TIMEOUT_SECONDS,
    STORE_CURRENCY,
    LemonSqueezyGateway,
)
from app.payments.unconfigured import UnconfiguredGateway

API_KEY = "lsq_test_00000000000000000000000000000001"
STORE_ID = "287880"
VARIANT_ID = "994310"
WEBHOOK_SECRET = "webhook-signing-secret-value"
# Every credential value, as one tuple. The containment assertions sweep this —
# a new field added to the adapter without being added here would not be swept.
SECRETS = (API_KEY, WEBHOOK_SECRET, STORE_ID, VARIANT_ID)

GOOD = {
    "api_key": API_KEY,
    "store_id": STORE_ID,
    "variant_id": VARIANT_ID,
    "webhook_secret": WEBHOOK_SECRET,
}

REFERENCE = "5f1c9d2e-0000-4000-8000-000000000001"
CHECKOUT_ID = "8f1a1c66-0000-4000-8000-0000000000aa"
CHECKOUT_URL = "https://automationscript.lemonsqueezy.com/checkout/custom/8f1a1c66"
ORDER_ID = "3216549"
AMOUNT_AGOROT = 15000
RETURN_URL = "https://bella.ourbrand.co.il/booking/thanks"


def _credentials(**overrides: str) -> GatewayCredentials:
    return GatewayCredentials(provider=LEMONSQUEEZY_PROVIDER, fields={**GOOD, **overrides})


def _mock(status: int, payload: Any) -> tuple[httpx.MockTransport, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status, json=payload)

    return httpx.MockTransport(handle), seen


def _failing(exc: Exception) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        raise exc

    return httpx.MockTransport(handle)


def _gateway(transport: httpx.BaseTransport | httpx.AsyncBaseTransport) -> LemonSqueezyGateway:
    # MockTransport satisfies both base classes; the annotation is only to keep
    # the helper callable from every test without a cast at each site.
    assert isinstance(transport, httpx.AsyncBaseTransport)
    return LemonSqueezyGateway(transport=transport)


# The store record as the live API actually answered it on 2026-07-31 (spec
# "Ground truth"), trimmed to the fields this adapter reads plus enough
# neighbours that a shape change is visible.
def _store_payload(*, currency: str = STORE_CURRENCY) -> dict[str, Any]:
    return {
        "jsonapi": {"version": "1.0"},
        "links": {"self": f"https://api.lemonsqueezy.com/v1/stores/{STORE_ID}"},
        "data": {
            "type": "stores",
            "id": STORE_ID,
            "attributes": {
                "name": "دعوة Dawa",
                "slug": "automationscript",
                "country": "IL",
                "currency": currency,
                "plan": "free",
            },
        },
    }


def _checkout_payload(*, test_mode: Any = True, **attribute_overrides: Any) -> dict[str, Any]:
    attributes: dict[str, Any] = {
        "url": CHECKOUT_URL,
        "test_mode": test_mode,
        "expires_at": "2026-07-31T12:00:00.000000Z",
        **attribute_overrides,
    }
    return {
        "jsonapi": {"version": "1.0"},
        "data": {"type": "checkouts", "id": CHECKOUT_ID, "attributes": attributes},
    }


# --- webhook fixtures ---


def _webhook_body(
    *,
    event_name: str = "order_created",
    status: str = "paid",
    refunded: bool = False,
    total: Any = AMOUNT_AGOROT,
    custom: Any = None,
) -> bytes:
    return json.dumps(
        {
            "meta": {
                "event_name": event_name,
                "custom_data": {"reference": REFERENCE} if custom is None else custom,
                "test_mode": True,
            },
            "data": {
                "type": "orders",
                "id": ORDER_ID,
                "attributes": {
                    "store_id": int(STORE_ID),
                    "identifier": "9c8b7a66-0000-4000-8000-000000000000",
                    "order_number": 12,
                    "currency": STORE_CURRENCY,
                    "subtotal": total,
                    "total": total,
                    "status": status,
                    "refunded": refunded,
                },
            },
        },
        sort_keys=True,
    ).encode()


def _sign(body: bytes, *, secret: str = WEBHOOK_SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


# --- metadata ---


def test_declares_the_provider_and_its_own_credential_shape() -> None:
    gateway = LemonSqueezyGateway()
    assert gateway.provider == LEMONSQUEEZY_PROVIDER == "lemonsqueezy"
    assert gateway.is_configured is True
    # D5's payoff: the console form renders from whatever the adapter declares,
    # so this set is the API contract and pinning it literally is the point.
    assert gateway.credential_fields == frozenset(
        {"api_key", "store_id", "variant_id", "webhook_secret"}
    )
    assert gateway.credential_fields == LEMONSQUEEZY_CREDENTIAL_FIELDS
    assert set(GOOD) == gateway.credential_fields


def test_adapter_satisfies_the_protocol() -> None:
    gateway: PaymentGateway = LemonSqueezyGateway()
    assert gateway.provider == LEMONSQUEEZY_PROVIDER


# --- validate_credentials ---


async def test_validate_accepts_an_ils_store_and_sends_the_json_api_headers() -> None:
    transport, seen = _mock(200, _store_payload())

    # Returns None and RAISES on refusal, so "it did not raise" IS the assertion.
    await _gateway(transport).validate_credentials(_credentials())

    assert len(seen) == 1
    request = seen[0]
    assert request.method == "GET"
    assert str(request.url) == f"https://api.lemonsqueezy.com/v1/stores/{STORE_ID}"
    assert request.headers["authorization"] == f"Bearer {API_KEY}"
    assert request.headers["accept"] == JSON_API_MEDIA_TYPE == "application/vnd.api+json"


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
async def test_validate_rejects_the_credentials_on_a_client_error(status: int) -> None:
    """ "Your key is wrong" and "LS is down" must not look the same to a boutique
    owner: this one is 400 and flips the credential row to `invalid`, the one
    below is 503 and touches neither status nor last_validated_at."""
    transport, _ = _mock(status, {"errors": [{"status": str(status), "title": "Unauthenticated."}]})

    with pytest.raises(GatewayCredentialsRejectedError):
        await _gateway(transport).validate_credentials(_credentials())


@pytest.mark.parametrize("status", [500, 502, 503, 504])
async def test_validate_reports_a_server_error_as_unavailable(status: int) -> None:
    transport, _ = _mock(status, {"errors": [{"title": "Server Error"}]})

    with pytest.raises(GatewayUnavailableError):
        await _gateway(transport).validate_credentials(_credentials())


async def test_validate_reports_a_rate_limit_as_unavailable_not_as_a_refusal() -> None:
    """429 is the one 4xx that is transient. Marking the credential row `invalid`
    because the free plan throttled us would take deposits offline for a boutique
    whose key is perfectly good, and only an operator could put them back."""
    transport, _ = _mock(429, {"errors": [{"title": "Too Many Requests"}]})

    with pytest.raises(GatewayUnavailableError):
        await _gateway(transport).validate_credentials(_credentials())


@pytest.mark.parametrize(
    "error",
    [
        httpx.ConnectTimeout("timed out"),
        httpx.ReadTimeout("timed out"),
        httpx.ConnectError("no route to host"),
    ],
)
async def test_validate_reports_a_transport_failure_as_unavailable(error: Exception) -> None:
    with pytest.raises(GatewayUnavailableError):
        await _gateway(_failing(error)).validate_credentials(_credentials())


@pytest.mark.parametrize("currency", ["USD", "EUR", "GBP", "ils"])
async def test_validate_rejects_a_store_that_is_not_in_shekels(currency: str) -> None:
    """THE currency test. `amount_agorot` maps 1:1 onto LS minor units only
    because the store is ILS; against a USD store 15000 agorot would be charged
    as $150.00 and every deposit in the system would be silently ~13x wrong,
    with nothing anywhere to notice. Case-sensitive on purpose — LS answers an
    uppercase ISO code, and a lowercase one means the field is not what we think."""
    transport, _ = _mock(200, _store_payload(currency=currency))

    with pytest.raises(GatewayCredentialsRejectedError):
        await _gateway(transport).validate_credentials(_credentials())


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"data": {"type": "stores", "id": STORE_ID}},
        {"data": {"type": "stores", "id": STORE_ID, "attributes": {}}},
        {"data": "not-an-object"},
        [],
    ],
)
async def test_validate_treats_an_unreadable_store_as_unavailable(payload: Any) -> None:
    """A 200 we cannot parse is OUR problem — a shape change, a proxy — not
    evidence that the merchant's account is bad. The _decrypt carve-out
    verbatim: flipping `invalid` here would send an owner whose credentials are
    fine to Lemon Squeezy's support desk over our bug."""
    transport, _ = _mock(200, payload)

    with pytest.raises(GatewayUnavailableError):
        await _gateway(transport).validate_credentials(_credentials())


# --- create_session ---


async def test_create_session_posts_the_json_api_envelope_and_returns_id_and_url() -> None:
    transport, seen = _mock(201, _checkout_payload())

    session = await _gateway(transport).create_session(
        _credentials(),
        amount_agorot=AMOUNT_AGOROT,
        reference=REFERENCE,
        return_url=RETURN_URL,
        expires_in=900,
    )

    assert session == PaymentSession(provider_session_id=CHECKOUT_ID, redirect_url=CHECKOUT_URL)
    assert len(seen) == 1
    request = seen[0]
    assert request.method == "POST"
    assert str(request.url) == "https://api.lemonsqueezy.com/v1/checkouts"
    assert request.headers["authorization"] == f"Bearer {API_KEY}"
    assert request.headers["accept"] == JSON_API_MEDIA_TYPE
    # JSON:API demands its own media type on the REQUEST too — httpx's json=
    # encoder would otherwise set application/json and LS answers 415.
    assert request.headers["content-type"] == JSON_API_MEDIA_TYPE

    body = json.loads(request.content)
    data = body["data"]
    assert data["type"] == "checkouts"
    attributes = data["attributes"]
    # THE guard, on the request side: an outgoing checkout is always test mode.
    assert attributes["test_mode"] is True
    # custom_price is the mechanism that bridges LS's catalog checkout to F17's
    # amount-driven port. Identity, not a conversion — the store is ILS.
    assert attributes["checkout_data"]["custom_price"] == AMOUNT_AGOROT
    # The opaque reference F19 passes (the booking id) has to survive the round
    # trip; `checkout_data.custom` is the only field LS echoes back on the webhook.
    assert attributes["checkout_data"]["custom"] == {"reference": REFERENCE}
    assert attributes["product_options"]["redirect_url"] == RETURN_URL
    assert "checkout_options" in attributes
    assert data["relationships"] == {
        "store": {"data": {"type": "stores", "id": STORE_ID}},
        "variant": {"data": {"type": "variants", "id": VARIANT_ID}},
    }


async def test_create_session_turns_expires_in_into_an_expires_at() -> None:
    """The port passes `expires_in` and LS speaks `expires_at`. Dropping the
    parameter silently would leave F19's hold clock enforced only on our side,
    so a bride could pay a checkout after the sweeper freed her seat."""
    transport, seen = _mock(201, _checkout_payload())
    before = datetime.datetime.now(datetime.UTC)

    await _gateway(transport).create_session(
        _credentials(),
        amount_agorot=AMOUNT_AGOROT,
        reference=REFERENCE,
        return_url=RETURN_URL,
        expires_in=900,
    )

    after = datetime.datetime.now(datetime.UTC)
    sent = json.loads(seen[0].content)["data"]["attributes"]["expires_at"]
    expires_at = datetime.datetime.fromisoformat(sent)
    assert expires_at.tzinfo is not None
    assert before + datetime.timedelta(seconds=900) <= expires_at
    assert expires_at <= after + datetime.timedelta(seconds=900)


@pytest.mark.parametrize("test_mode", [False, None, "true", 1, 0])
async def test_create_session_refuses_a_checkout_that_is_not_in_test_mode(test_mode: Any) -> None:
    """THE guard, on the response side, and the reason it is not merely a
    request-side assertion: a mis-toggled store, an ignored attribute or a
    changed default would each hand back a LIVE checkout that charges a real
    bride real money on a development engine. `is True`, never truthiness —
    `1` and `"true"` are exactly the sloppy encodings that would slip a live
    checkout past a `==` comparison.

    Rejected rather than Unavailable deliberately: 503 renders "temporarily
    unavailable", which invites a retry, and every retry mints another live
    checkout at the provider. 400 is a refusal to proceed."""
    transport, _ = _mock(201, _checkout_payload(test_mode=test_mode))

    with pytest.raises(GatewayCredentialsRejectedError):
        await _gateway(transport).create_session(
            _credentials(),
            amount_agorot=AMOUNT_AGOROT,
            reference=REFERENCE,
            return_url=RETURN_URL,
            expires_in=900,
        )


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"data": {"type": "checkouts", "id": CHECKOUT_ID}},
        {"data": "not-an-object"},
        [],
    ],
)
async def test_create_session_refuses_a_checkout_whose_test_mode_cannot_be_confirmed(
    payload: Any,
) -> None:
    # Same direction as above and for the same money reason: "we could not
    # confirm it is a test checkout" and "it is a live checkout" get the same
    # answer, because the cost of being wrong is identical.
    transport, _ = _mock(201, payload)

    with pytest.raises(GatewayCredentialsRejectedError):
        await _gateway(transport).create_session(
            _credentials(),
            amount_agorot=AMOUNT_AGOROT,
            reference=REFERENCE,
            return_url=RETURN_URL,
            expires_in=900,
        )


@pytest.mark.parametrize("missing", ["url", "id"])
async def test_create_session_reports_a_confirmed_test_checkout_it_cannot_read_as_unavailable(
    missing: str,
) -> None:
    """Past the test-mode guard, an unreadable field is our parse problem again,
    so this half is 503 rather than 400 — and the split is what stops the
    test-mode refusal from being indistinguishable from a shape change."""
    payload = _checkout_payload()
    if missing == "url":
        del payload["data"]["attributes"]["url"]
    else:
        del payload["data"]["id"]
    transport, _ = _mock(201, payload)

    with pytest.raises(GatewayUnavailableError):
        await _gateway(transport).create_session(
            _credentials(),
            amount_agorot=AMOUNT_AGOROT,
            reference=REFERENCE,
            return_url=RETURN_URL,
            expires_in=900,
        )


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (401, GatewayCredentialsRejectedError),
        (404, GatewayCredentialsRejectedError),
        (422, GatewayCredentialsRejectedError),
        (429, GatewayUnavailableError),
        (500, GatewayUnavailableError),
        (503, GatewayUnavailableError),
    ],
)
async def test_create_session_maps_failures_exactly_as_validate_does(
    status: int, expected: type[Exception]
) -> None:
    # One mapping, one helper, both call sites — a 401 mid-flight means the same
    # thing whichever path found it.
    transport, _ = _mock(status, {"errors": [{"title": "nope"}]})

    with pytest.raises(expected):
        await _gateway(transport).create_session(
            _credentials(),
            amount_agorot=AMOUNT_AGOROT,
            reference=REFERENCE,
            return_url=RETURN_URL,
            expires_in=900,
        )


async def test_create_session_reports_a_transport_failure_as_unavailable() -> None:
    with pytest.raises(GatewayUnavailableError):
        await _gateway(_failing(httpx.ReadTimeout("timed out"))).create_session(
            _credentials(),
            amount_agorot=AMOUNT_AGOROT,
            reference=REFERENCE,
            return_url=RETURN_URL,
            expires_in=900,
        )


# --- verify_webhook: the signature ---


def test_verify_accepts_a_correctly_signed_body() -> None:
    body = _webhook_body()

    event = LemonSqueezyGateway().verify_webhook(_credentials(), body=body, signature=_sign(body))

    assert event == WebhookEvent(
        provider_session_id=REFERENCE,
        provider_transaction_id=ORDER_ID,
        amount_agorot=AMOUNT_AGOROT,
        paid=True,
    )


def test_verify_rejects_a_tampered_body() -> None:
    body = _webhook_body()
    signature = _sign(body)
    tampered = body.replace(str(AMOUNT_AGOROT).encode(), b"1")

    assert tampered != body
    # By TYPE. GatewayWebhookInvalidError is 400; folding a forgery into
    # GatewayUnavailableError's 503 would invite the sender to retry it (D25).
    with pytest.raises(GatewayWebhookInvalidError):
        LemonSqueezyGateway().verify_webhook(_credentials(), body=tampered, signature=signature)


def test_verify_rejects_a_truncated_signature() -> None:
    body = _webhook_body()

    with pytest.raises(GatewayWebhookInvalidError):
        LemonSqueezyGateway().verify_webhook(_credentials(), body=body, signature=_sign(body)[:-1])


def test_verify_rejects_a_signature_made_with_the_wrong_secret() -> None:
    body = _webhook_body()

    with pytest.raises(GatewayWebhookInvalidError):
        LemonSqueezyGateway().verify_webhook(
            _credentials(), body=body, signature=_sign(body, secret="not-the-secret")
        )


@pytest.mark.parametrize("signature", ["", "   ", "not-hex", "שלום", "0" * 64])
def test_verify_rejects_a_missing_or_malformed_signature(signature: str) -> None:
    """A missing X-Signature is a rejection, never a crash: `hmac.compare_digest`
    raises TypeError on a non-ASCII str, and an unhandled TypeError out of this
    method would surface as a 500 where D25 requires a 400."""
    body = _webhook_body()

    with pytest.raises(GatewayWebhookInvalidError):
        LemonSqueezyGateway().verify_webhook(_credentials(), body=body, signature=signature)


def test_verify_rejects_a_body_signed_with_a_missing_webhook_secret() -> None:
    # A credential set that somehow lost its secret must not verify everything
    # signed with the empty string.
    body = _webhook_body()
    credentials = GatewayCredentials(
        provider=LEMONSQUEEZY_PROVIDER,
        fields={k: v for k, v in GOOD.items() if k != "webhook_secret"},
    )

    with pytest.raises(GatewayWebhookInvalidError):
        LemonSqueezyGateway().verify_webhook(credentials, body=body, signature=_sign(body))


@pytest.mark.parametrize(
    "body",
    [
        b"not json",
        b"[]",
        b'{"meta": {}}',
        b'{"meta": {"event_name": "order_created"}, "data": {}}',
        json.dumps(
            {"meta": {"event_name": "order_created", "custom_data": {}}, "data": {}}
        ).encode(),
    ],
)
def test_verify_rejects_a_correctly_signed_body_that_is_not_a_webhook(body: bytes) -> None:
    # A correctly signed blob that is not a webhook is still not a webhook —
    # GatewayWebhookInvalidError, not a 500 and not GatewayUnavailableError.
    with pytest.raises(GatewayWebhookInvalidError):
        LemonSqueezyGateway().verify_webhook(_credentials(), body=body, signature=_sign(body))


def test_verify_rejects_a_webhook_with_no_reference() -> None:
    """Without the reference there is nothing to match a payment row on, so
    accepting it would produce a WebhookEvent that can only ever mismatch."""
    body = _webhook_body(custom={"something_else": "x"})

    with pytest.raises(GatewayWebhookInvalidError):
        LemonSqueezyGateway().verify_webhook(_credentials(), body=body, signature=_sign(body))


@pytest.mark.parametrize("total", [None, "not-a-number", {}, []])
def test_verify_rejects_a_webhook_whose_amount_is_not_a_number(total: Any) -> None:
    body = _webhook_body(total=total)

    with pytest.raises(GatewayWebhookInvalidError):
        LemonSqueezyGateway().verify_webhook(_credentials(), body=body, signature=_sign(body))


# --- verify_webhook: THE paid mapping ---
#
# F17's review found a decline being recorded as paid, and settle_from_webhook
# now reads event.paid to decide between `paid` and `failed`. So this table IS
# the money decision, and it is an ALLOWLIST: True requires order_created AND
# status == "paid" AND not refunded. Everything else — including an event name
# nobody has seen yet — is False, because the cost of a wrong False (a real
# payment lands as failed and an owner chases it) is recoverable and the cost of
# a wrong True (a seat confirmed against money that never arrived) is not.


@pytest.mark.parametrize(
    ("event_name", "status", "refunded", "expected"),
    [
        ("order_created", "paid", False, True),
        ("order_created", "pending", False, False),
        ("order_created", "failed", False, False),
        ("order_created", "refunded", True, False),
        # The one that would slip past a name-only allowlist: LS re-sends the
        # order object on a refund with the same `order_created`-shaped body.
        ("order_created", "paid", True, False),
        ("order_refunded", "refunded", True, False),
        ("order_refunded", "paid", False, False),
        ("subscription_payment_failed", "failed", False, False),
        ("subscription_payment_success", "paid", False, False),
        ("subscription_cancelled", "paid", False, False),
        ("order_cancelled", "paid", False, False),
        ("some_event_lemon_squeezy_has_not_shipped_yet", "paid", False, False),
    ],
)
def test_the_paid_mapping(event_name: str, status: str, refunded: bool, expected: bool) -> None:
    body = _webhook_body(event_name=event_name, status=status, refunded=refunded)

    event = LemonSqueezyGateway().verify_webhook(_credentials(), body=body, signature=_sign(body))

    assert event.paid is expected
    # The rest of the event is populated either way: a decline still has to find
    # its row, because _record_decline writes onto it.
    assert event.provider_session_id == REFERENCE
    assert event.provider_transaction_id == ORDER_ID
    assert event.amount_agorot == AMOUNT_AGOROT


def test_a_failed_order_is_not_paid_even_though_it_is_a_valid_webhook() -> None:
    """The regression this feature exists to not repeat, stated once on its own
    rather than only as a parametrize row: verification succeeding says the
    message is authentic, NOT that money arrived."""
    body = _webhook_body(status="failed")

    event = LemonSqueezyGateway().verify_webhook(_credentials(), body=body, signature=_sign(body))

    assert event.paid is False


# --- containment ---


async def test_no_credential_reaches_a_raised_exception(caplog: pytest.LogCaptureFixture) -> None:
    """The twilio.py discipline: nothing provider-supplied but a status code
    leaves this adapter, and no credential value leaves it at all.
    `scrub_provider_error` writes `f"{type(exc).__name__}: {exc}"` onto
    `tenant_gateway_credentials.validation_error` — a column that lives forever
    beside the ciphertext whose whole job is hiding these values."""
    # A realistic hostile 401: the payload quotes the key it refused.
    echoing = {
        "errors": [
            {
                "status": "401",
                "title": "Unauthenticated.",
                "detail": f"The api key {API_KEY} for store {STORE_ID} is not valid.",
            }
        ]
    }
    transport, _ = _mock(401, echoing)

    with (
        caplog.at_level(logging.DEBUG, logger="app"),
        pytest.raises(GatewayCredentialsRejectedError) as caught,
    ):
        await _gateway(transport).validate_credentials(_credentials())

    rendered = f"{type(caught.value).__name__}: {caught.value}"
    assert "401" in rendered
    for secret in SECRETS:
        assert secret not in rendered
    assert "Unauthenticated" not in rendered
    assert "api key" not in rendered
    for record in caplog.records:
        for secret in SECRETS:
            assert secret not in record.getMessage()


async def test_the_minted_session_log_line_names_no_credential(
    caplog: pytest.LogCaptureFixture,
) -> None:
    transport, _ = _mock(201, _checkout_payload())

    with caplog.at_level(logging.DEBUG, logger="app"):
        await _gateway(transport).create_session(
            _credentials(),
            amount_agorot=AMOUNT_AGOROT,
            reference=REFERENCE,
            return_url=RETURN_URL,
            expires_in=900,
        )

    emitted = " ".join(record.getMessage() for record in caplog.records if record.name == "app")
    assert LEMONSQUEEZY_PROVIDER in emitted
    assert CHECKOUT_ID in emitted
    for secret in SECRETS:
        assert secret not in emitted
    # The hosted-page URL is a bearer capability to pay — it is not logged either.
    assert CHECKOUT_URL not in emitted


def test_no_signature_or_raw_body_reaches_the_webhook_rejection(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A rejected webhook is attacker-controlled input. Echoing the body or the
    submitted signature into an exception puts an attacker's chosen bytes into
    an operator's log and, through `scrub_provider_error`, into `payments.error`."""
    body = _webhook_body()
    signature = _sign(body, secret="forged-secret-value")

    with (
        caplog.at_level(logging.DEBUG, logger="app"),
        pytest.raises(GatewayWebhookInvalidError) as caught,
    ):
        LemonSqueezyGateway().verify_webhook(_credentials(), body=body, signature=signature)

    rendered = " ".join(
        [
            f"{type(caught.value).__name__}: {caught.value}",
            *(record.getMessage() for record in caplog.records),
        ]
    )
    assert signature not in rendered
    assert body.decode() not in rendered
    assert ORDER_ID not in rendered
    for secret in SECRETS:
        assert secret not in rendered


def test_the_signature_comparison_is_constant_time() -> None:
    """Structural, because there is no behavioural test for a timing leak: a
    plain `==` on a hex digest passes every other test in this file while
    leaking the expected signature one byte at a time."""
    from pathlib import Path

    from app.payments import lemonsqueezy

    assert lemonsqueezy.__file__
    source = Path(lemonsqueezy.__file__).read_text()
    assert "hmac.compare_digest" in source


# --- timeouts ---


async def test_timeouts_are_explicit_on_the_client() -> None:
    # Structural, so an edit that drops `timeout=` is caught: both values are
    # deliberately different from httpx's 5s default, which is what a bare
    # client would report. A hung provider inside open_deposit holds the
    # per-tenant advisory lock, so this ceiling is the one that bounds it.
    async with LemonSqueezyGateway()._client() as client:
        assert client.timeout.connect == CONNECT_TIMEOUT_SECONDS
        assert client.timeout.read == READ_TIMEOUT_SECONDS
    default = httpx.Timeout(5.0)
    assert default.connect != CONNECT_TIMEOUT_SECONDS
    assert default.read != READ_TIMEOUT_SECONDS


# --- wiring ---


def test_settings_accepts_the_lemonsqueezy_provider() -> None:
    settings = Settings(app_env="dev", payment_provider="lemonsqueezy", gateway_secret_box="fake")
    assert settings.payment_provider == "lemonsqueezy"


def test_production_with_lemonsqueezy_fails_fast() -> None:
    """Guard 1 of the three that keep a development engine from becoming a
    payment processor. Lemon Squeezy is merchant-of-record, so it can never
    carry a boutique's deposit — the boutique owes the Israeli receipt and the
    money is legally hers.

    `match=` ISOLATES this guard, the reason test_production_with_the_fake_gateway_fails_fast
    gives: `gateway_secret_box` has to be passed too or the "required when
    PAYMENT_PROVIDER is set" guard fires instead, and a bare `pytest.raises`
    would then stay green with this guard deleted."""
    with pytest.raises(ValidationError, match="PAYMENT_PROVIDER"):
        Settings(
            app_env="production",
            database_url="postgresql+asyncpg://app:secret@db.internal:5432/boutique",
            base_domain="ourbrand.co.il",
            payment_provider="lemonsqueezy",
            gateway_secret_box="fake",
        )


def test_staging_may_use_lemonsqueezy() -> None:
    # The whole point of the adapter: a real network, a real signature scheme,
    # no real money, everywhere that is not production.
    settings = Settings(
        app_env="staging",
        database_url="postgresql+asyncpg://app:secret@db.internal:5432/boutique",
        base_domain="staging.ourbrand.co.il",
        payment_provider="lemonsqueezy",
        gateway_secret_box="fake",
    )
    assert settings.payment_provider == "lemonsqueezy"


def test_build_payment_gateway_dispatches_on_the_provider() -> None:
    def _settings(provider: str | None) -> Settings:
        return Settings(
            app_env="dev",
            payment_provider=provider,  # type: ignore[arg-type]
            gateway_secret_box="fake" if provider else None,
        )

    assert isinstance(_build_payment_gateway(_settings("lemonsqueezy")), LemonSqueezyGateway)
    assert isinstance(_build_payment_gateway(_settings("fake")), FakeGateway)
    assert isinstance(_build_payment_gateway(_settings(None)), UnconfiguredGateway)


def test_the_builder_names_the_provider_and_no_credential(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Settings.model_config is extra="ignore", so a typo'd PAYMENT_PROVDER
    # degrades silently — this INFO line is what makes the degradation
    # observable. It names the adapter; credentials are per-tenant and are not
    # in Settings at all, so there is nothing here it could leak.
    with caplog.at_level(logging.INFO, logger="app"):
        _build_payment_gateway(
            Settings(app_env="dev", payment_provider="lemonsqueezy", gateway_secret_box="fake")
        )

    emitted = " ".join(record.getMessage() for record in caplog.records if record.name == "app")
    assert LEMONSQUEEZY_PROVIDER in emitted
