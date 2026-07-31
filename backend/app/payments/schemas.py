import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.payments.service import GatewayStatus


class GatewayStatusResponse(BaseModel):
    """The WHOLE response, in every state.

    Nothing else, ever: no ciphertext, no key_ref, no validation_error, no field
    value. `validation_error` is operator telemetry on the row, held to the same
    containment as message_log.error.

    `configured` is platform-level and `connected` is tenant-level — two
    booleans because the two facts have different owners and different remedies.
    `credential_fields` is the adapter's own declared shape, sorted, which is
    what lets the console render the right form without hardcoding a provider's
    field names — and why F18 needs no frontend change.
    """

    provider: str | None
    configured: bool
    connected: bool
    status: str | None
    last_validated_at: datetime.datetime | None
    credential_fields: list[str]

    @classmethod
    def from_status(cls, status: GatewayStatus) -> "GatewayStatusResponse":
        return cls(
            provider=status.provider,
            configured=status.configured,
            connected=status.connected,
            status=status.status,
            last_validated_at=status.last_validated_at,
            credential_fields=status.credential_fields,
        )


class SetGatewayCredentialsRequest(BaseModel):
    """The complete set, always. There is no PATCH and there is no partial
    update, because a partial one would have to read back what it is not
    replacing — and there is no read path for a field value."""

    # extra="forbid" so a stray top-level key is the house 400 rather than a
    # silently ignored field; the per-KEY check against the adapter's declared
    # set is app/payments/validation.py's job, since only the adapter knows it.
    model_config = ConfigDict(extra="forbid")

    fields: dict[str, str] = Field(min_length=1)
