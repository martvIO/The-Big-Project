"""The payment gateway port.

Nothing here imports from app/db/ or any feature module — the app/storage/base.py
and app/notifications/base.py rule. That is exactly why `DepositHold` and
`Settlement` live in service.py rather than here: both carry a `Payment` model,
and the port is not allowed to know one exists.

Same degradation contract as the other two ports, with one more axis. Media and
SMS have two states (configured / unavailable); payments have four, and they are
operationally distinct: the PLATFORM may have no adapter, THIS TENANT may have
no valid credentials, the provider may refuse the credentials it was given, or
the provider may be unreachable. Each has a different remedy and a different
person who can apply it. None of them is ever a 500.
"""

import dataclasses
from collections.abc import Mapping
from typing import Protocol


class GatewayNotConfiguredError(Exception):
    """No adapter at all — a supported deployment, exactly like a missing media
    bucket. Every gateway route answers 503 and deposits are simply unavailable."""


class GatewayNotConnectedError(Exception):
    """An adapter exists; THIS tenant has no valid credentials behind it. The
    boutique's own remedy, not the operator's — which is why it is a distinct
    error from the one above."""


class GatewayCredentialsRejectedError(Exception):
    """The provider said no to these credentials. Carries no provider text: the
    original is scrubbed onto the row and never reaches the owner."""


class GatewayUnavailableError(Exception):
    """Unreachable or refused for a transient reason. Carries no provider text,
    the MediaStorageUnavailableError containment."""


class GatewayWebhookInvalidError(Exception):
    """The signature did not verify — an AUTHENTICATION failure, never an
    outage (D25). Folding this into GatewayUnavailableError would report a
    forgery as a provider blip: it invites a retry of the forgery, it is
    indistinguishable from a real outage in logs and alerting, and it makes the
    checklist's "webhook signature verification" row unprovable from outside."""


class PaymentAlreadyHeldError(Exception):
    """A live hold exists that open_deposit could not converge on (D23) — the
    mapped domain error for the partial unique index, exactly as
    SlotUnavailableError maps the slot-seat one. Never an unhandled 500."""


@dataclasses.dataclass(frozen=True, repr=False)
class GatewayCredentials:
    """`fields` is opaque to everything except the adapter (D5): we do not know
    what a real provider's credential set contains, so any fixed shape here
    would be a guess a migration has to correct.

    __repr__ is overridden to print field NAMES only. The S3MediaStorage rule,
    made STRUCTURAL because here the secret is IN the object: a stray log line,
    an f-string in an exception, or a traceback frame would otherwise render a
    merchant secret. repr=False so the generated one cannot win.
    """

    provider: str
    fields: Mapping[str, str]

    def __repr__(self) -> str:
        names = ", ".join(sorted(self.fields))
        return f"GatewayCredentials(provider={self.provider!r}, fields=[{names}])"


@dataclasses.dataclass(frozen=True)
class PaymentSession:
    provider_session_id: str
    redirect_url: str


@dataclasses.dataclass(frozen=True)
class WebhookEvent:
    provider_session_id: str
    provider_transaction_id: str
    amount_agorot: int
    paid: bool


class PaymentGateway(Protocol):
    """`verify_webhook` is a plain `def` while the other two are `async`, for the
    reason MediaStorage's docstring already gives about presigned_post:
    signature verification is local HMAC with zero I/O, and making it async
    would be a lie.

    `provider` is `str | None`, not `str`, because D22 requires
    UnconfiguredGateway to ANSWER its metadata rather than raise — that is what
    makes `GET /manage/gateway` -> 200 `configured: false` structural instead of
    a branch F18 and F19 would each have to remember.

    `validate_credentials` returns None and RAISES rather than returning a bool:
    the caller must not be able to ignore the answer.

    `reference` is a caller-supplied opaque string (F19 passes the booking id),
    so the port carries no knowledge of the booking domain. There is no
    `refund()` (D12) — no consumer, no method.
    """

    @property
    def provider(self) -> str | None: ...

    @property
    def is_configured(self) -> bool: ...

    @property
    def credential_fields(self) -> frozenset[str]: ...

    async def validate_credentials(self, credentials: GatewayCredentials) -> None: ...

    async def create_session(
        self,
        credentials: GatewayCredentials,
        *,
        amount_agorot: int,
        reference: str,
        return_url: str,
        expires_in: int,
    ) -> PaymentSession: ...

    def verify_webhook(
        self, credentials: GatewayCredentials, *, body: bytes, signature: str
    ) -> WebhookEvent: ...
