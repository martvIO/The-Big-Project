"""TwilioSmsSender against a faked transport. Fast: no network, no db, no cost.

The credential helper sets or explicitly deletes all four vars on every path, so
a developer shell that exports the real Twilio pair cannot change an outcome.
"""

import base64
import contextlib
import urllib.parse
import uuid
from collections.abc import AsyncIterator
from typing import Any, cast

import httpx
import pytest

from app.core.config import Settings
from app.main import _build_sms_sender
from app.notifications.base import SendResult, SmsNotConfiguredError, SmsSender, SmsSendError
from app.notifications.fake import FakeSmsSender
from app.notifications.service import NotificationService
from app.notifications.twilio import (
    CONNECT_TIMEOUT_SECONDS,
    READ_TIMEOUT_SECONDS,
    TwilioSmsSender,
)
from app.notifications.unconfigured import UnconfiguredSmsSender
from app.notifications.validation import mask_otp_body, otp_sms_body
from app.worker import build_sender

ACCOUNT_SID = "AC00000000000000000000000000000001"
API_KEY_SID = "SK00000000000000000000000000000002"
API_KEY_SECRET = "s3cret-api-key-value"
FROM_NUMBER = "+972500000000"
TO_NUMBER = "+972501234567"

CREDENTIALS: dict[str, str] = {
    "TWILIO_ACCOUNT_SID": ACCOUNT_SID,
    "TWILIO_API_KEY_SID": API_KEY_SID,
    "TWILIO_API_KEY_SECRET": API_KEY_SECRET,
    "TWILIO_FROM_NUMBER": FROM_NUMBER,
}


def _set_credentials(monkeypatch: pytest.MonkeyPatch, **overrides: str | None) -> None:
    merged: dict[str, str | None] = {**CREDENTIALS, **overrides}
    for name, value in merged.items():
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)


def _mock(status: int, payload: dict[str, Any]) -> tuple[httpx.MockTransport, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status, json=payload)

    return httpx.MockTransport(handle), seen


# A realistic Twilio 400: the payload quotes the parameters that were submitted.
# This is not a strawman — Twilio's error messages routinely echo the offending
# value, which is the whole reason NotificationService._scrub exists.
def _echoing_error_payload(*, body: str) -> dict[str, Any]:
    return {
        "code": 21610,
        "message": (
            "The message From/To pair violates a blacklist rule. "
            f"Request was To={TO_NUMBER} From={FROM_NUMBER} Body={body!r}"
        ),
        "more_info": "https://www.twilio.com/docs/errors/21610",
        "status": 400,
    }


# --- is_configured ---


@pytest.mark.parametrize("missing", sorted(CREDENTIALS))
async def test_is_configured_false_when_any_single_var_is_missing(
    monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    _set_credentials(monkeypatch, **{missing: None})
    assert TwilioSmsSender().is_configured is False


async def test_is_configured_true_when_all_four_are_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_credentials(monkeypatch)
    assert TwilioSmsSender().is_configured is True


async def test_blank_credential_counts_as_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    # An operator who sets TWILIO_FROM_NUMBER= in Railway gets 503, not a
    # runtime 400 on every send.
    _set_credentials(monkeypatch, TWILIO_FROM_NUMBER="")
    assert TwilioSmsSender().is_configured is False


async def test_unconfigured_send_raises_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_credentials(monkeypatch, TWILIO_ACCOUNT_SID=None)
    with pytest.raises(SmsNotConfiguredError):
        await TwilioSmsSender().send(phone=TO_NUMBER, body="x")


def test_adapter_satisfies_the_protocol(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_credentials(monkeypatch)
    sender: SmsSender = TwilioSmsSender()
    assert sender.is_configured is True


# --- the successful call ---


async def test_successful_send_posts_the_form_and_returns_the_sid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_credentials(monkeypatch)
    transport, seen = _mock(201, {"sid": "SM0123456789abcdef", "status": "queued"})

    result = await TwilioSmsSender(transport=transport).send(phone=TO_NUMBER, body="שלום")

    assert result == SendResult(provider_message_id="SM0123456789abcdef")
    assert len(seen) == 1
    request = seen[0]
    assert request.method == "POST"
    # The account SID is in the PATH — an API key pair alone names no account.
    assert str(request.url) == (
        f"https://api.twilio.com/2010-04-01/Accounts/{ACCOUNT_SID}/Messages.json"
    )
    scheme, _, encoded = request.headers["authorization"].partition(" ")
    assert scheme == "Basic"
    assert base64.b64decode(encoded).decode() == f"{API_KEY_SID}:{API_KEY_SECRET}"
    assert request.headers["content-type"] == "application/x-www-form-urlencoded"
    assert dict(urllib.parse.parse_qsl(request.content.decode())) == {
        "To": TO_NUMBER,
        "From": FROM_NUMBER,
        "Body": "שלום",
    }


# --- the failing call ---


async def test_error_response_raises_without_body_or_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_credentials(monkeypatch)
    body = "שלום, ההזמנה שלך אושרה"
    transport, _ = _mock(400, _echoing_error_payload(body=body))

    with pytest.raises(SmsSendError) as caught:
        await TwilioSmsSender(transport=transport).send(phone=TO_NUMBER, body=body)

    rendered = str(caught.value)
    # The operator still gets the two facts that identify the failure.
    assert "400" in rendered
    assert "21610" in rendered
    assert body not in rendered
    for secret in (ACCOUNT_SID, API_KEY_SID, API_KEY_SECRET):
        assert secret not in rendered
    assert "more_info" not in rendered
    assert "blacklist" not in rendered


async def test_non_json_error_body_still_raises_a_constructed_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A gateway 502 in front of Twilio answers HTML, not JSON. The adapter must
    # not carry that page — nor blow up parsing it.
    _set_credentials(monkeypatch)

    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="<html><body>upstream is very unwell</body></html>")

    with pytest.raises(SmsSendError) as caught:
        await TwilioSmsSender(transport=httpx.MockTransport(handle)).send(
            phone=TO_NUMBER, body="שלום"
        )

    assert "502" in str(caught.value)
    assert "unwell" not in str(caught.value)


async def test_non_integer_error_code_is_never_echoed(monkeypatch: pytest.MonkeyPatch) -> None:
    # Twilio's `code` is always an integer. Anything else is refused rather than
    # stringified, so the field cannot become a second echo channel.
    _set_credentials(monkeypatch)
    body = "קוד האימות שלך: 424242"
    transport, _ = _mock(400, {"code": body, "message": "odd", "status": 400})

    with pytest.raises(SmsSendError) as caught:
        await TwilioSmsSender(transport=transport).send(phone=TO_NUMBER, body=body)

    assert "424242" not in str(caught.value)


# --- THE test: an echoed OTP must not reach message_log.error ---


async def test_echoed_otp_never_survives_into_the_raised_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_credentials(monkeypatch)
    code = "483920"
    body = otp_sms_body(code)
    transport, _ = _mock(400, _echoing_error_payload(body=body))

    with pytest.raises(SmsSendError) as caught:
        await TwilioSmsSender(transport=transport).send(phone=TO_NUMBER, body=body)

    # `_scrub` renders "TypeName: message" — assert against exactly that shape.
    rendered = f"{type(caught.value).__name__}: {caught.value}"
    assert code not in rendered
    assert body not in rendered
    # No word of the body survives either. Every token here is >= 3 characters,
    # so this cannot pass by accident on shared punctuation.
    for token in body.split():
        assert len(token) >= 3
        assert token not in rendered


class _RecordingMessageLog:
    """Stands in for MessageLogRepository so send_sms runs its real control flow
    (including _scrub) without Postgres. Captures exactly what would be written
    to message_log.error."""

    def __init__(self) -> None:
        self.error: str | None = None
        self.row = cast(Any, type("Row", (), {"id": uuid.uuid4()})())

    async def insert(self, session: Any, **kwargs: Any) -> Any:
        return self.row

    async def update_status(
        self, session: Any, tenant_id: uuid.UUID, log_id: uuid.UUID, **kwargs: Any
    ) -> Any:
        self.error = kwargs.get("error")
        return None


@contextlib.asynccontextmanager
async def _no_db_session(factory: Any, tenant_id: uuid.UUID) -> AsyncIterator[None]:
    yield None


async def test_message_log_error_carries_no_otp_end_to_end(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One level up from the adapter: the value NotificationService would persist
    on message_log.error, for a provider that echoed the OTP body verbatim."""
    _set_credentials(monkeypatch)
    code = "483920"
    body = otp_sms_body(code)
    transport, _ = _mock(400, _echoing_error_payload(body=body))
    recorder = _RecordingMessageLog()
    monkeypatch.setattr("app.notifications.service.tenant_session", _no_db_session)
    monkeypatch.setattr("app.notifications.service.MessageLogRepository", lambda: recorder)

    service = NotificationService(cast(Any, None), sender=TwilioSmsSender(transport=transport))
    with pytest.raises(SmsSendError):
        await service.send_sms(
            uuid.uuid4(),
            phone=TO_NUMBER,
            body=body,
            kind="otp",
            log_body=mask_otp_body(body, code),
        )

    assert recorder.error is not None
    assert code not in recorder.error
    assert body not in recorder.error
    for token in body.split():
        assert token not in recorder.error


# --- timeouts ---


async def test_timeouts_are_explicit_on_the_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Structural, so an edit that drops `timeout=` is caught: both values are
    deliberately different from httpx's 5s default, which is what a bare client
    would report."""
    _set_credentials(monkeypatch)
    async with TwilioSmsSender()._client() as client:
        assert client.timeout.connect == CONNECT_TIMEOUT_SECONDS
        assert client.timeout.read == READ_TIMEOUT_SECONDS
    default = httpx.Timeout(5.0)
    assert CONNECT_TIMEOUT_SECONDS != default.connect
    assert READ_TIMEOUT_SECONDS != default.read


# --- wiring ---


def test_settings_accepts_the_twilio_provider() -> None:
    assert Settings(sms_provider="twilio").sms_provider == "twilio"


def test_twilio_is_a_legal_production_provider() -> None:
    settings = Settings(
        app_env="production",
        database_url="postgresql+asyncpg://app:secret@db.internal:5432/boutique",
        base_domain="ourbrand.co.il",
        sms_provider="twilio",
    )
    assert settings.sms_provider == "twilio"


def test_build_sms_sender_dispatches_on_the_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_credentials(monkeypatch)
    assert isinstance(_build_sms_sender(Settings(sms_provider="twilio")), TwilioSmsSender)
    assert isinstance(_build_sms_sender(Settings(sms_provider="fake")), FakeSmsSender)
    assert isinstance(_build_sms_sender(Settings(sms_provider=None)), UnconfiguredSmsSender)


def test_worker_build_sender_dispatches_on_the_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    # The worker drains F16's reminders through its OWN builder. Left behind, a
    # twilio deployment would send OTPs and silently leave every reminder pending.
    _set_credentials(monkeypatch)
    assert isinstance(build_sender(Settings(sms_provider="twilio")), TwilioSmsSender)
    assert isinstance(build_sender(Settings(sms_provider="fake")), FakeSmsSender)
    assert isinstance(build_sender(Settings(sms_provider=None)), UnconfiguredSmsSender)


def test_incomplete_credentials_degrade_to_503_rather_than_booting_dark(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Exactly today's state: the API key pair is supplied, the account SID is not.
    _set_credentials(monkeypatch, TWILIO_ACCOUNT_SID=None, TWILIO_FROM_NUMBER=None)
    sender = _build_sms_sender(Settings(sms_provider="twilio"))
    assert isinstance(sender, TwilioSmsSender)
    assert sender.is_configured is False
