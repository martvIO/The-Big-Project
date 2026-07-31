"""Lemon Squeezy behind the PaymentGateway port — TEST MODE ONLY.

A DEVELOPMENT ENGINE, never a production path. LS is merchant-of-record, so it
would make MODRYN the seller of the bride's transaction; the deposit is legally
the boutique's and the boutique owes the Israeli receipt. Three guards keep it
where it belongs: `APP_ENV=production` + `PAYMENT_PROVIDER=lemonsqueezy` is a
boot failure (config.py), migration 0013 widens 0012's CHECK to exactly
`('fake','lemonsqueezy')`, and every checkout here both SENDS `test_mode: true`
and REFUSES a response that does not come back in test mode.

Credentials arrive per-tenant through `GatewayCredentials`, NOT from `Settings`
— the one structural difference from twilio.py, and the reason this adapter
holds no state but a transport. Everything else is that file: an injectable
`transport` as the only test seam, explicit timeouts, and the discipline that
nothing provider-supplied but an HTTP STATUS CODE ever leaves this module.
`scrub_provider_error` writes `f"{type(exc).__name__}: {exc}"` onto
`tenant_gateway_credentials.validation_error` and `payments.error`, columns that
live forever right beside the ciphertext whose whole job is hiding these values,
and LS's own 401 body quotes the key it refused. The scrub one layer up is a
second net, not the first: it can only replace a value verbatim, so a provider
that truncated or re-encoded it would slip through.

The design constraint this bridges: LS's checkout API is a product-catalog
checkout requiring a `variant_id`, while F17's port is amount-driven because a
deposit is an arbitrary sum. `checkout_data.custom_price` overrides the
variant's price, so one placeholder variant serves every amount and its id is
simply another declared credential field (D5) — which is why F18 needs no
frontend change.

`provider_session_id` IS THE REFERENCE ON BOTH HALVES, deliberately, and this
is the single most important thing to know before touching either one:

  create_session  -> `reference`   (NOT the LS checkout id)
  verify_webhook  -> `reference`   (read back out of `meta.custom_data`)

The port defines one identifier space — `PaymentSession.provider_session_id` is
what `open_deposit` stores on `payments.provider_session_id`, and
`WebhookEvent.provider_session_id` is what `settle_from_webhook` looks that row
up by (`by_provider_session_id`). Whatever this adapter puts in the first, it
must be able to produce in the second.

The LS checkout id cannot satisfy that. An LS ORDER carries no checkout id, so
it is unrecoverable from a webhook, and `checkout_data.custom` — the only
payload LS echoes back — is fixed at create time, before the checkout id
exists. The reference is therefore the ONLY key present on both sides.

Returning the checkout id instead is a money bug, not a cosmetic mismatch: the
stored value and the lookup value come from different spaces and can never
match, so a verified, genuinely-paid webhook finds no row. The charge succeeds,
the payment stays `pending`, the sweeper frees the seat, and the bride has paid
and lost her appointment. `test_the_two_halves_agree_on_provider_session_id`
and the end-to-end composition test pin this; do not change one half alone.

The checkout id is not discarded — `create_session` still requires it to be
present and logs it at INFO, because an operator needs it to find the checkout
in the LS dashboard.
"""

import datetime
import hashlib
import hmac
import json
import logging
from collections.abc import Mapping
from typing import Any

import httpx

from app.payments.base import (
    GatewayCredentials,
    GatewayCredentialsRejectedError,
    GatewayUnavailableError,
    GatewayWebhookInvalidError,
    PaymentSession,
    WebhookEvent,
)

logger = logging.getLogger("app")

LEMONSQUEEZY_PROVIDER = "lemonsqueezy"
# D5: the console form renders from whatever the adapter declares, so this set
# IS the API contract. `variant_id` is here because of the catalog-checkout
# constraint above; the placeholder variant is created by hand in the LS
# dashboard and its id typed in like any other credential.
LEMONSQUEEZY_CREDENTIAL_FIELDS = frozenset({"api_key", "store_id", "variant_id", "webhook_secret"})

API_BASE_URL = "https://api.lemonsqueezy.com"
_STORE_URL = API_BASE_URL + "/v1/stores/{store_id}"
_CHECKOUTS_URL = API_BASE_URL + "/v1/checkouts"
JSON_API_MEDIA_TYPE = "application/vnd.api+json"

# `amount_agorot` maps 1:1 onto LS minor units ONLY because the store is ILS —
# verified against the live account, not assumed. Against a USD store every
# deposit would be charged ~13x wrong with nothing to notice, so the currency is
# asserted at connect time rather than trusted.
STORE_CURRENCY = "ILS"

# Explicit, and deliberately not httpx's 5s-everywhere default. This ceiling
# matters more here than in twilio.py: `open_deposit` calls `create_session`
# INSIDE the per-tenant advisory lock (D23 orders it that way so a session is
# never minted before the row that could refuse it), so a hung provider holds
# that lock for exactly this long.
CONNECT_TIMEOUT_SECONDS = 3.0
READ_TIMEOUT_SECONDS = 10.0

# 429 is the one 4xx that is transient — the free plan may throttle (spec Risk
# 3) — so it maps to Unavailable rather than to a refusal that would flip a good
# credential row to `invalid` and take deposits offline until an operator noticed.
_RATE_LIMITED = 429
_SERVER_ERROR_FLOOR = 500

_API_KEY_FIELD = "api_key"
_STORE_ID_FIELD = "store_id"
_VARIANT_ID_FIELD = "variant_id"
_WEBHOOK_SECRET_FIELD = "webhook_secret"

# The key inside `checkout_data.custom`, which is the only payload LS echoes
# back on the webhook (as `meta.custom_data`). One name, spelled once, because
# create_session and verify_webhook disagreeing about it is a silent money bug.
REFERENCE_KEY = "reference"

# --- THE paid mapping ---------------------------------------------------------
#
# F17's review found a DECLINE being recorded as paid, and `settle_from_webhook`
# now branches on `event.paid` to choose between settling the row and
# `_record_decline`. So this is the money decision of the whole adapter, and it
# is an ALLOWLIST rather than a denylist of failure names:
#
#   order_created + status "paid" + not refunded  -> paid=True
#   order_created + status pending/failed          -> paid=False
#   order_created + refunded (LS re-sends the      -> paid=False
#     order object with the same shape)
#   order_refunded, order_cancelled, every
#     subscription_* event, and any event name
#     Lemon Squeezy has not shipped yet            -> paid=False
#
# The asymmetry is deliberate. A wrong False costs a real payment landing as
# `failed` — visible, recoverable, and an owner chases it. A wrong True confirms
# an appointment against money that never arrived — invisible until the bride
# turns up. A denylist gets the second one wrong the first time LS adds an event
# name, which is precisely the failure this adapter was told to not repeat.
#
# Verification succeeding proves the message is AUTHENTIC. It says nothing about
# whether money moved; that is what `status` is for.
PAID_EVENT_NAME = "order_created"
PAID_ORDER_STATUS = "paid"


class LemonSqueezyGateway:
    """Real HTTP. `transport` is a test seam only — production leaves it None."""

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    @property
    def provider(self) -> str | None:
        return LEMONSQUEEZY_PROVIDER

    @property
    def is_configured(self) -> bool:
        # The ADAPTER is configured; whether a given tenant has usable
        # credentials is GatewayCredentialService's question, and it answers it
        # with GatewayNotConnectedError. Same split FakeGateway makes.
        return True

    @property
    def credential_fields(self) -> frozenset[str]:
        return LEMONSQUEEZY_CREDENTIAL_FIELDS

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=CONNECT_TIMEOUT_SECONDS,
                read=READ_TIMEOUT_SECONDS,
                write=CONNECT_TIMEOUT_SECONDS,
                pool=CONNECT_TIMEOUT_SECONDS,
            ),
            transport=self._transport,
        )

    async def _request(
        self, method: str, url: str, *, api_key: str, json_body: Any = None
    ) -> httpx.Response:
        headers = {"Accept": JSON_API_MEDIA_TYPE, "Authorization": f"Bearer {api_key}"}
        if json_body is not None:
            # httpx's json= encoder would set application/json, which JSON:API
            # answers 415 to. Explicit headers win over the encoder's defaults
            # (Request._prepare uses setdefault), so this is the one that lands.
            headers["Content-Type"] = JSON_API_MEDIA_TYPE
        try:
            async with self._client() as client:
                return await client.request(method, url, headers=headers, json=json_body)
        except httpx.HTTPError as exc:
            # Timeouts, DNS, TLS, connection resets. `exc` is never rendered:
            # httpx puts the full URL in its message and the URL carries the
            # store id.
            raise GatewayUnavailableError("lemonsqueezy is unreachable") from exc

    async def validate_credentials(self, credentials: GatewayCredentials) -> None:
        response = await self._request(
            "GET",
            _STORE_URL.format(store_id=_field(credentials, _STORE_ID_FIELD)),
            api_key=_field(credentials, _API_KEY_FIELD),
        )
        _raise_for_status(response)

        currency = _string_attribute(_resource_attributes(response), "currency")
        if currency is None:
            # A 200 we cannot parse is OUR problem — a shape change, a proxy —
            # not evidence the merchant's account is bad. The `_decrypt`
            # carve-out verbatim: `invalid` renders "your account was refused"
            # to an owner whose account is fine and sends her to LS's support
            # desk over our bug. Unavailable leaves status untouched.
            raise GatewayUnavailableError("lemonsqueezy store response is unreadable")
        if currency != STORE_CURRENCY:
            raise GatewayCredentialsRejectedError("lemonsqueezy store currency is not ILS")

    async def create_session(
        self,
        credentials: GatewayCredentials,
        *,
        amount_agorot: int,
        reference: str,
        return_url: str,
        expires_in: int,
    ) -> PaymentSession:
        expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=expires_in)
        payload = {
            "data": {
                "type": "checkouts",
                "attributes": {
                    # Guard 3, outbound half.
                    "test_mode": True,
                    # The port speaks `expires_in`; LS speaks `expires_at`.
                    # Dropping it would leave F19's hold clock enforced only on
                    # our side, so a bride could pay a checkout after the
                    # sweeper had already freed her seat.
                    "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
                    # TOP-LEVEL, a sibling of checkout_data — NOT nested inside
                    # it. This is what bridges a catalog checkout to an
                    # amount-driven port, and it is identity rather than a
                    # conversion because the store is ILS.
                    #
                    # It shipped nested once and that was a money bug: LS drops
                    # attributes it does not recognise, so the checkout would be
                    # minted at the placeholder VARIANT'S OWN price. The bride is
                    # charged the wrong sum, and F17's D14 amount assertion then
                    # refuses to settle — so she pays wrongly AND loses the seat.
                    # Both official SDKs put it here: the JS SDK's attributes are
                    # {customPrice, expiresAt, preview, testMode, productOptions,
                    # checkoutOptions, checkoutData} and its CheckoutData type has
                    # no price field at all; the Go SDK's CheckoutAttributes has
                    # CustomPrice beside CheckoutData, whose struct is only
                    # Email/Name/BillingAddress/TaxNumber/DiscountCode/Custom.
                    "custom_price": amount_agorot,
                    "checkout_data": {
                        # The ONLY field LS echoes back on the webhook, and
                        # therefore the only key both halves of this adapter can
                        # share (see the module docstring).
                        "custom": {REFERENCE_KEY: reference},
                    },
                    # A hosted page we redirect to, not an overlay we embed:
                    # F19 hands the bride a URL, it has no page to embed into.
                    "checkout_options": {"embed": False},
                    "product_options": {"redirect_url": return_url},
                },
                "relationships": {
                    "store": {
                        "data": {"type": "stores", "id": _field(credentials, _STORE_ID_FIELD)}
                    },
                    "variant": {
                        "data": {"type": "variants", "id": _field(credentials, _VARIANT_ID_FIELD)}
                    },
                },
            }
        }
        response = await self._request(
            "POST", _CHECKOUTS_URL, api_key=_field(credentials, _API_KEY_FIELD), json_body=payload
        )
        _raise_for_status(response)

        # Guard 3, inbound half, and it runs BEFORE anything is read out of the
        # response. `is True`, never truthiness: `1` and `"true"` are exactly
        # the sloppy encodings a `==` would let a LIVE checkout through on. A
        # body we cannot parse at all lands here too — "could not confirm it is
        # a test checkout" and "it is a live checkout" cost the same if we are
        # wrong, so they get the same answer.
        #
        # Rejected (400) rather than Unavailable (503) deliberately: 503 renders
        # "temporarily unavailable", which invites a retry, and every retry
        # mints another live checkout at the provider.
        attributes = _resource_attributes(response)
        if attributes is None or attributes.get("test_mode") is not True:
            raise GatewayCredentialsRejectedError(
                "lemonsqueezy did not return a test-mode checkout"
            )

        # READ-BACK GUARD, and the general form of the test_mode one: require the
        # provider to ECHO the money we asked it to charge. We can never call the
        # live API from a test, so asserting the request shape only proves we
        # sent what we MEANT to — never that LS understood it. LS silently drops
        # attributes it does not recognise, which makes a misplaced field
        # invisible until a bride is charged the wrong amount. Comparing the echo
        # turns that entire class of bug into a loud failure on the FIRST real
        # call, before any money moves.
        #
        # Rejected (400), not Unavailable (503), for the test_mode reason
        # exactly: the wrongly-priced checkout ALREADY EXISTS at the provider and
        # is payable, so 503's "temporarily unavailable" would invite a retry
        # that mints another one. Nor is it transient — it is our bug or an API
        # change, and it persists until code changes, so the one error class that
        # means "refuse, do not retry" is the correct one.
        #
        # A missing or null price fails here too: "we could not confirm the
        # price" and "the price is wrong" cost the same if we are wrong.
        if attributes.get("custom_price") != amount_agorot:
            raise GatewayCredentialsRejectedError(
                "lemonsqueezy did not echo the requested checkout price"
            )

        # The same lens on IDENTITY, the other thing we send that has to survive
        # the round trip: if `custom` were ever dropped the webhook would carry
        # no reference, settle_from_webhook could never find the row, and we
        # would learn only after the charge. Checked only when the echo is
        # PRESENT — whether a create response populates checkout_data could not
        # be verified against the live API, so absence must not fail a
        # legitimate checkout, while a present-but-wrong value is unambiguous.
        checkout_data = attributes.get("checkout_data")
        echoed_custom = checkout_data.get("custom") if isinstance(checkout_data, Mapping) else None
        if isinstance(echoed_custom, Mapping) and echoed_custom.get(REFERENCE_KEY) != reference:
            raise GatewayCredentialsRejectedError(
                "lemonsqueezy did not echo the checkout reference"
            )

        # The checkout id is still REQUIRED to be present and well-formed even
        # though it is not what identifies the session to us: a 201 without one
        # is a reply we do not understand, and accepting it would mean trusting
        # the `url` beside it. It is logged (not a secret, and an operator needs
        # it to find the checkout in the LS dashboard) and then dropped.
        checkout_id = _string_member(_resource(response), "id")
        redirect_url = _string_attribute(attributes, "url")
        if checkout_id is None or redirect_url is None:
            # Past the guard, an unreadable field is a parse problem again.
            raise GatewayUnavailableError("lemonsqueezy checkout response is unreadable")

        # No credential value, and no redirect URL either — that URL is a bearer
        # capability to pay. FakeGateway's refusal to log a body, for its stated
        # reason: staging runs on a publicly reachable host whose log stream is
        # widely readable.
        logger.info(
            "%s test-mode checkout %s minted for %d agorot",
            LEMONSQUEEZY_PROVIDER,
            checkout_id,
            amount_agorot,
        )
        # THE reference, not the checkout id — see the module docstring. This is
        # the value F17 stores on `payments.provider_session_id`, and it is the
        # only one a webhook can produce.
        return PaymentSession(provider_session_id=reference, redirect_url=redirect_url)

    def verify_webhook(
        self, credentials: GatewayCredentials, *, body: bytes, signature: str
    ) -> WebhookEvent:
        """`X-Signature` carries an HMAC-SHA256 hex digest of the RAW request
        body. Raw bytes, never re-serialised JSON — which is why the port passes
        `bytes` and why F19's route must hand over what it read off the wire.

        Every failure below is `GatewayWebhookInvalidError` -> 400, never 503
        (D25): an HMAC mismatch is an authentication failure, and reporting a
        forgery as a provider blip invites a retry of the forgery.
        """
        secret = credentials.fields.get(_WEBHOOK_SECRET_FIELD, "")
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        if not secret or not _matches(expected, signature):
            raise GatewayWebhookInvalidError
        return _parse(body)


def _field(credentials: GatewayCredentials, name: str) -> str:
    """Trimmed, the twilio `_credential` reason: a value pasted into the console
    keeps its trailing newline more often than not, and untrimmed it lands in
    the request path and the Bearer header."""
    return credentials.fields.get(name, "").strip()


def _raise_for_status(response: httpx.Response) -> None:
    """One mapping, both call sites — a 401 mid-checkout means what a 401 at
    connect time means. ONLY the integer status escapes: LS's error bodies quote
    the key and the store they refused."""
    if response.is_success:
        return
    status = response.status_code
    if status == _RATE_LIMITED or status >= _SERVER_ERROR_FLOOR:
        raise GatewayUnavailableError(f"lemonsqueezy {status}")
    raise GatewayCredentialsRejectedError(f"lemonsqueezy {status}")


def _resource(response: httpx.Response) -> Mapping[str, Any] | None:
    """The JSON:API `data` member, or None if this is not a JSON:API document.
    The envelope is `{meta, jsonapi, links, data}` — verified against the live
    account, not read from documentation the vendor 403s."""
    try:
        payload = response.json()
    except ValueError:
        return None
    if not isinstance(payload, Mapping):
        return None
    data = payload.get("data")
    return data if isinstance(data, Mapping) else None


def _resource_attributes(response: httpx.Response) -> Mapping[str, Any] | None:
    resource = _resource(response)
    if resource is None:
        return None
    attributes = resource.get("attributes")
    return attributes if isinstance(attributes, Mapping) else None


def _string_member(resource: Mapping[str, Any] | None, name: str) -> str | None:
    if resource is None:
        return None
    value = resource.get(name)
    return value if isinstance(value, str) and value else None


def _string_attribute(attributes: Mapping[str, Any] | None, name: str) -> str | None:
    return _string_member(attributes, name)


def _matches(expected: str, signature: str) -> bool:
    """`compare_digest` raises TypeError on a non-ASCII str, and an unhandled
    TypeError out of verify_webhook would surface as a 500 where D25 requires a
    400. A missing header arrives here as "" and simply does not match."""
    try:
        return hmac.compare_digest(expected, signature)
    except TypeError:
        return False


def _parse(body: bytes) -> WebhookEvent:
    """A correctly signed blob that is not a webhook is still not a webhook."""
    try:
        payload = json.loads(body)
        if not isinstance(payload, Mapping):
            raise TypeError("webhook payload is not an object")
        meta = payload["meta"]
        data = payload["data"]
        if not isinstance(meta, Mapping) or not isinstance(data, Mapping):
            raise TypeError("webhook meta/data are not objects")
        attributes = data["attributes"]
        custom = meta["custom_data"]
        if not isinstance(attributes, Mapping) or not isinstance(custom, Mapping):
            raise TypeError("webhook attributes/custom_data are not objects")
        return WebhookEvent(
            # The reference we put into checkout_data.custom, which is exactly
            # what create_session returned — see the module docstring. An LS
            # order carries no checkout id, so this is the only key that can
            # appear on both halves.
            provider_session_id=str(custom[REFERENCE_KEY]),
            provider_transaction_id=str(data["id"]),
            # `total`, not `subtotal`: the money that actually MOVED. If a tax
            # or discount ever diverges the two, D14's amount assertion in
            # settle_from_webhook fires and persists its evidence — which is the
            # safe direction. `subtotal` would silently settle a short payment
            # as if it were the full deposit.
            amount_agorot=int(attributes["total"]),
            paid=_is_paid(str(meta["event_name"]), attributes),
        )
    except (ValueError, TypeError, KeyError) as exc:
        # `from exc` keeps the cause on the traceback for an operator without
        # putting attacker-chosen bytes into the message.
        raise GatewayWebhookInvalidError from exc


def _is_paid(event_name: str, attributes: Mapping[str, Any]) -> bool:
    """The allowlist argued for at PAID_EVENT_NAME. Three conditions, all
    required; anything unrecognised is False."""
    if event_name != PAID_EVENT_NAME:
        return False
    if attributes.get("refunded"):
        return False
    return attributes.get("status") == PAID_ORDER_STATUS
