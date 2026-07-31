from app.payments.base import (
    GatewayCredentials,
    GatewayNotConfiguredError,
    PaymentSession,
    WebhookEvent,
)


class UnconfiguredGateway:
    """The no-adapter deployment — a supported state, not a bug.

    D22: the METADATA properties answer, only the I/O methods raise. `provider`
    is None, `credential_fields` is empty, `is_configured` is False. That is what
    makes `GET /manage/gateway` -> 200 `configured: false` structural rather than
    a remembered `if` in a route, and it is the one place this port departs from
    UnconfiguredMediaStorage — which has no metadata properties, so it settles
    nothing either way. A console that cannot read its own status cannot explain
    to the owner why deposits are unavailable.
    """

    @property
    def provider(self) -> str | None:
        return None

    @property
    def is_configured(self) -> bool:
        return False

    @property
    def credential_fields(self) -> frozenset[str]:
        return frozenset()

    async def validate_credentials(self, credentials: GatewayCredentials) -> None:
        raise GatewayNotConfiguredError

    async def create_session(
        self,
        credentials: GatewayCredentials,
        *,
        amount_agorot: int,
        reference: str,
        return_url: str,
        expires_in: int,
    ) -> PaymentSession:
        raise GatewayNotConfiguredError

    def verify_webhook(
        self, credentials: GatewayCredentials, *, body: bytes, signature: str
    ) -> WebhookEvent:
        raise GatewayNotConfiguredError
