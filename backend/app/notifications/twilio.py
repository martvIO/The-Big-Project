"""Twilio behind the SmsSender port — one form-encoded POST, no vendor SDK.

Credentials arrive as SecretStr Settings fields, NOT via os.environ: unlike
boto3, which reads the process environment itself, nothing but this file reads
these four names, so reading only os.environ would silently ignore every
deployment that supplies them through `.env` — the path .env.example documents.
SecretStr is what preserves the property the boto3 precedent was protecting:
they never appear in a repr, a log line or a traceback frame. Any one of the
four missing means is_configured is False, which routes to the same 503
SMS_NOT_CONFIGURED as no provider at all — a half-configured deployment
degrades instead of erroring on every send.

The raised message is CONSTRUCTED, never the response body. Twilio's 4xx
payloads routinely quote the parameters that were submitted, body included, and
NotificationService writes the adapter's exception text onto message_log.error
— a forever-table whose masking (mask_otp_body) an echoed OTP would defeat.
`_scrub` one layer up is a second net, not the first one: it can only replace
the body verbatim, so a provider that re-encoded or truncated it would slip
through. Nothing provider-supplied but an INTEGER error code leaves this file.
"""

import logging

import httpx
from pydantic import SecretStr

from app.core.config import Settings
from app.notifications.base import SendResult, SmsNotConfiguredError, SmsSendError

logger = logging.getLogger("app")

_MESSAGES_URL = "https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"

# Explicit, and deliberately not httpx's 5s-everywhere default: a hung provider
# would otherwise hold a request thread for the default while a bride waits on
# an OTP. Connect is short (TCP+TLS to a global API), read is longer (Twilio
# queues the message before answering).
CONNECT_TIMEOUT_SECONDS = 3.0
READ_TIMEOUT_SECONDS = 10.0


def _credential(value: SecretStr | None) -> str:
    """Unwrapped and trimmed. A value pasted into a Railway variable box or an
    `.env` line arrives with a trailing newline or a stray space more often than
    not, and `From=" "` would 400 on every single send instead of degrading to
    the 503 that a missing credential gets."""
    return value.get_secret_value().strip() if value is not None else ""


class TwilioSmsSender:
    """Real sends. `transport` is a test seam only — production leaves it None."""

    def __init__(
        self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        # Read once at construction: _build_sms_sender runs at boot, and a
        # credential appearing mid-process is not a state worth supporting.
        self._account_sid = _credential(settings.twilio_account_sid)
        self._api_key_sid = _credential(settings.twilio_api_key_sid)
        self._api_key_secret = _credential(settings.twilio_api_key_secret)
        self._from_number = _credential(settings.twilio_from_number)
        self._transport = transport

    @property
    def from_number(self) -> str:
        """The E.164 sender. Not a credential — main.py logs it so a wrong-sender
        deployment is observable."""
        return self._from_number

    @property
    def is_configured(self) -> bool:
        return all((self._account_sid, self._api_key_sid, self._api_key_secret, self._from_number))

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

    async def send(self, *, phone: str, body: str) -> SendResult:
        if not self.is_configured:
            raise SmsNotConfiguredError
        async with self._client() as client:
            response = await client.post(
                _MESSAGES_URL.format(account_sid=self._account_sid),
                auth=(self._api_key_sid, self._api_key_secret),
                data={"To": phone, "From": self._from_number, "Body": body},
            )
        if not response.is_success:
            # Status and code, and DELIBERATELY nothing else — the payload is
            # withheld from this line just as firmly as from the exception. Do
            # not "restore" `response.text` here: Twilio's 4xx quotes the
            # parameters it was handed, body included, so logging it would
            # relocate the echoed OTP into the process log stream rather than
            # prevent it, and fake.py refuses to log a body for exactly that
            # reason (that stream is widely readable). An operator who needs the
            # message text has it in Twilio's own console, against this code.
            # test_error_log_line_carries_only_status_and_code pins this.
            code = _error_code(response)
            logger.warning("twilio refused a send: status=%s code=%s", response.status_code, code)
            raise SmsSendError(f"twilio {response.status_code}: {code}")
        return SendResult(provider_message_id=_message_sid(response))


def _error_code(response: httpx.Response) -> str:
    """Twilio's numeric error code, or a placeholder. Only an int is ever
    stringified: a payload that put the message body in `code` must not become a
    second echo channel."""
    try:
        payload = response.json()
    except ValueError:
        return "unparsed"
    code = payload.get("code") if isinstance(payload, dict) else None
    return str(code) if isinstance(code, int) else "unknown"


def _message_sid(response: httpx.Response) -> str | None:
    """`sid` off a 2xx. None rather than raising if it is absent — the message
    IS accepted at that point, and failing here would mark a real send failed."""
    try:
        payload = response.json()
    except ValueError:
        return None
    sid = payload.get("sid") if isinstance(payload, dict) else None
    return sid if isinstance(sid, str) else None
