"""Twilio behind the SmsSender port — one form-encoded POST, no vendor SDK.

Credentials are read from the process environment and are deliberately NOT
Settings fields, the precedent boto3 set for AWS (config.py:43-44): they never
enter the config object, never appear in a repr and never reach a log line.
Any one of the four missing means is_configured is False, which routes to the
same 503 SMS_NOT_CONFIGURED as no provider at all — a half-configured
deployment degrades instead of erroring on every send.

The raised message is CONSTRUCTED, never the response body. Twilio's 4xx
payloads routinely quote the parameters that were submitted, body included, and
NotificationService writes the adapter's exception text onto message_log.error
— a forever-table whose masking (mask_otp_body) an echoed OTP would defeat.
`_scrub` one layer up is a second net, not the first one: it can only replace
the body verbatim, so a provider that re-encoded or truncated it would slip
through. Nothing provider-supplied but an INTEGER error code leaves this file.
"""

import logging
import os

import httpx

from app.notifications.base import SendResult, SmsNotConfiguredError, SmsSendError

logger = logging.getLogger("app")

_MESSAGES_URL = "https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"

# Explicit, and deliberately not httpx's 5s-everywhere default: a hung provider
# would otherwise hold a request thread for the default while a bride waits on
# an OTP. Connect is short (TCP+TLS to a global API), read is longer (Twilio
# queues the message before answering).
CONNECT_TIMEOUT_SECONDS = 3.0
READ_TIMEOUT_SECONDS = 10.0

_ENV_VARS = (
    "TWILIO_ACCOUNT_SID",
    "TWILIO_API_KEY_SID",
    "TWILIO_API_KEY_SECRET",
    "TWILIO_FROM_NUMBER",
)


class TwilioSmsSender:
    """Real sends. `transport` is a test seam only — production leaves it None."""

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        # Read once at construction: _build_sms_sender runs at boot, and a
        # credential appearing mid-process is not a state worth supporting.
        account_sid, api_key_sid, api_key_secret, from_number = (
            os.environ.get(name, "").strip() for name in _ENV_VARS
        )
        self._account_sid = account_sid
        self._api_key_sid = api_key_sid
        self._api_key_secret = api_key_secret
        self._from_number = from_number
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
            # The full payload goes to the server log — that stream is not the
            # forever-table, and an operator debugging a 21610 needs it. It does
            # NOT go into the exception.
            logger.warning(
                "twilio refused a send: status=%s code=%s",
                response.status_code,
                _error_code(response),
            )
            raise SmsSendError(f"twilio {response.status_code}: {_error_code(response)}")
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
