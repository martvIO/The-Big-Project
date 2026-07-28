"""The SMS port. Nothing here imports from app/db/ or any feature module — the
caller passes fully rendered bodies and normalized phones, so templates and
normalization stay in the notifications service and there is no cycle. Mirrors
app/storage/base.py, including the degradation contract: not-configured and
provider-refused are operationally distinct (503 SMS_NOT_CONFIGURED vs 503
SMS_UNAVAILABLE) but neither is ever a 500.
"""

import dataclasses
from typing import Protocol


class SmsNotConfiguredError(Exception):
    """No provider configured. A supported deployment state, not a bug: OTP send
    answers 503 and bookings are structurally gated on the sender-ID
    registration existing."""


class SmsSendError(Exception):
    """The provider could not be reached or refused the send. Carries no
    provider-supplied text: the original is logged server-side and recorded on
    the message_log row, and never reaches the caller."""


@dataclasses.dataclass(frozen=True)
class SendResult:
    provider_message_id: str | None


class SmsSender(Protocol):
    @property
    def is_configured(self) -> bool: ...

    async def send(self, *, phone: str, body: str) -> SendResult: ...
