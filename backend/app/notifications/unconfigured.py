from app.notifications.base import SendResult, SmsNotConfiguredError


class UnconfiguredSmsSender:
    """The no-provider deployment. send() raising (rather than returning a
    failed SendResult) is deliberate: the caller's message_log row must record
    'failed' with a reason, and the HTTP layer must answer 503 — same shape as
    UnconfiguredMediaStorage."""

    @property
    def is_configured(self) -> bool:
        return False

    async def send(self, *, phone: str, body: str) -> SendResult:
        raise SmsNotConfiguredError
