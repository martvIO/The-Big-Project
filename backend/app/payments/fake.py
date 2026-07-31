"""The in-memory gateway for dev, tests and staging until a real adapter lands.

Mirrors FakeSmsSender: it records instead of calling. The one place it does NOT
fake is the webhook signature — that is real HMAC-SHA256 with
`hmac.compare_digest`, deliberately, because F19's signature and tamper tests
must exercise a genuine comparison rather than a stub that returns True.
"""

import dataclasses
import hashlib
import hmac
import itertools
import json
import logging
from collections.abc import Mapping

from app.payments.base import (
    GatewayCredentials,
    GatewayCredentialsRejectedError,
    GatewayWebhookInvalidError,
    PaymentSession,
    WebhookEvent,
)
from app.payments.validation import FAKE_INVALID_MERCHANT_ID, FAKE_PAY_PATH

logger = logging.getLogger("app")

FAKE_PROVIDER = "fake"
# A plausible shape, explicitly NOT a claim about any real provider's (Risk 9).
# When F18 declares its adapter's real field set, the console form follows with
# no frontend edit — that is D5's payoff.
FAKE_CREDENTIAL_FIELDS = frozenset({"merchant_id", "api_key", "webhook_secret"})

_WEBHOOK_SECRET_FIELD = "webhook_secret"
_MERCHANT_ID_FIELD = "merchant_id"


@dataclasses.dataclass(frozen=True)
class FakeSession:
    """What create_session recorded. Carries no credential material — the
    assertions tests want are about the CALL, not about what authorised it."""

    provider_session_id: str
    amount_agorot: int
    reference: str
    return_url: str
    expires_in: int


def sign_fake_webhook(*, webhook_secret: str, body: bytes) -> str:
    """The one place the fake's signature scheme is spelled. Tests and F19's
    fixtures build signatures through this, so a change to the scheme cannot
    leave verify_webhook and its callers disagreeing."""
    return hmac.new(webhook_secret.encode(), body, hashlib.sha256).hexdigest()


def fake_webhook_body(
    *, provider_session_id: str, provider_transaction_id: str, amount_agorot: int, paid: bool
) -> bytes:
    """The fake's wire payload. Same reason as above: one definition, so a test
    cannot sign a body shaped differently from the one verify_webhook parses."""
    return json.dumps(
        {
            "provider_session_id": provider_session_id,
            "provider_transaction_id": provider_transaction_id,
            "amount_agorot": amount_agorot,
            "paid": paid,
        },
        sort_keys=True,
    ).encode()


class FakeGateway:
    def __init__(self) -> None:
        self.validations: list[GatewayCredentials] = []
        self.sessions: list[FakeSession] = []
        self._counter = itertools.count(1)

    @property
    def provider(self) -> str | None:
        return FAKE_PROVIDER

    @property
    def is_configured(self) -> bool:
        return True

    @property
    def credential_fields(self) -> frozenset[str]:
        return FAKE_CREDENTIAL_FIELDS

    async def validate_credentials(self, credentials: GatewayCredentials) -> None:
        self.validations.append(credentials)
        if credentials.fields.get(_MERCHANT_ID_FIELD) == FAKE_INVALID_MERCHANT_ID:
            raise GatewayCredentialsRejectedError

    async def create_session(
        self,
        credentials: GatewayCredentials,
        *,
        amount_agorot: int,
        reference: str,
        return_url: str,
        expires_in: int,
    ) -> PaymentSession:
        session_id = f"{FAKE_PROVIDER}-{next(self._counter)}"
        self.sessions.append(
            FakeSession(
                provider_session_id=session_id,
                amount_agorot=amount_agorot,
                reference=reference,
                return_url=return_url,
                expires_in=expires_in,
            )
        )
        # No credential value is logged, matching FakeSmsSender's refusal to log
        # the body: staging runs this adapter on a publicly reachable host whose
        # log stream is widely readable.
        logger.info("fake payment session %s minted for %d agorot", session_id, amount_agorot)
        return PaymentSession(
            provider_session_id=session_id,
            redirect_url=f"{FAKE_PAY_PATH}?session={session_id}",
        )

    def verify_webhook(
        self, credentials: GatewayCredentials, *, body: bytes, signature: str
    ) -> WebhookEvent:
        secret = credentials.fields.get(_WEBHOOK_SECRET_FIELD, "")
        expected = sign_fake_webhook(webhook_secret=secret, body=body)
        if not hmac.compare_digest(expected, signature):
            raise GatewayWebhookInvalidError
        return _parse(body)


def _parse(body: bytes) -> WebhookEvent:
    """A correctly signed blob that is not a webhook is still not a webhook —
    GatewayWebhookInvalidError, not a 500 and not GatewayUnavailableError."""
    try:
        payload = json.loads(body)
        if not isinstance(payload, Mapping):
            raise TypeError("webhook payload is not an object")
        return WebhookEvent(
            provider_session_id=str(payload["provider_session_id"]),
            provider_transaction_id=str(payload["provider_transaction_id"]),
            amount_agorot=int(payload["amount_agorot"]),
            paid=bool(payload["paid"]),
        )
    except (ValueError, TypeError, KeyError) as exc:
        raise GatewayWebhookInvalidError from exc
