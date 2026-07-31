"""TwilioSmsSender against a faked transport. Fast: no network, no db, no cost.

Credentials are passed to `Settings` as EXPLICIT init kwargs on every path, and
init kwargs outrank both `.env` and the process environment in pydantic-settings,
so a developer shell that exports the real Twilio pair cannot change an outcome.
The three tests that deliberately exercise those two sources say so in their names.
"""

import base64
import contextlib
import logging
import os
import urllib.parse
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
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

# Field names, as Settings sees them.
CREDENTIALS: dict[str, str | None] = {
    "twilio_account_sid": ACCOUNT_SID,
    "twilio_api_key_sid": API_KEY_SID,
    "twilio_api_key_secret": API_KEY_SECRET,
    "twilio_from_number": FROM_NUMBER,
}
# The same four as an operator writes them, in `.env` or in a Railway variable.
ENV_CREDENTIALS: dict[str, str] = {
    name.upper(): value for name, value in CREDENTIALS.items() if value
}
SECRETS = (ACCOUNT_SID, API_KEY_SID, API_KEY_SECRET)


def _settings(**overrides: Any) -> Settings:
    return Settings(**{**CREDENTIALS, **overrides})


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
def test_is_configured_false_when_any_single_var_is_missing(missing: str) -> None:
    assert TwilioSmsSender(_settings(**{missing: None})).is_configured is False


def test_is_configured_true_when_all_four_are_present() -> None:
    assert TwilioSmsSender(_settings()).is_configured is True


def test_blank_credential_counts_as_missing() -> None:
    # An operator who sets TWILIO_FROM_NUMBER= in Railway gets 503, not a
    # runtime 400 on every send.
    assert TwilioSmsSender(_settings(twilio_from_number="")).is_configured is False


@pytest.mark.parametrize("blank", [" ", "  ", "\n", "\t "])
def test_whitespace_only_credential_counts_as_missing(blank: str) -> None:
    # `.strip()` and not merely falsiness. A space is truthy, so without it
    # is_configured would be True and every send would POST From=" " — a hard
    # 400 per message, where a missing credential degrades to a clean 503.
    assert TwilioSmsSender(_settings(twilio_from_number=blank)).is_configured is False
    assert TwilioSmsSender(_settings(twilio_api_key_secret=blank)).is_configured is False


async def test_unconfigured_send_raises_not_configured() -> None:
    with pytest.raises(SmsNotConfiguredError):
        await TwilioSmsSender(_settings(twilio_account_sid=None)).send(phone=TO_NUMBER, body="x")


def test_adapter_satisfies_the_protocol() -> None:
    sender: SmsSender = TwilioSmsSender(_settings())
    assert sender.is_configured is True


# --- the successful call ---


async def test_successful_send_posts_the_form_and_returns_the_sid() -> None:
    transport, seen = _mock(201, {"sid": "SM0123456789abcdef", "status": "queued"})

    result = await TwilioSmsSender(_settings(), transport=transport).send(
        phone=TO_NUMBER, body="שלום"
    )

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


# --- what the failure writes to the log ---


async def test_error_log_line_carries_only_status_and_code(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Pins the WARNING verbatim, because the comment above it is the whole
    security argument of that file. An edit that "helpfully" adds `response.text`
    would relocate the echoed OTP into the process log stream — readable by
    anyone with log access — rather than prevent it. Equality, not containment:
    a substring assertion would pass with the payload appended."""
    code = "483920"
    body = otp_sms_body(code)
    transport, _ = _mock(400, _echoing_error_payload(body=body))

    with caplog.at_level(logging.DEBUG, logger="app"), pytest.raises(SmsSendError):
        await TwilioSmsSender(_settings(), transport=transport).send(phone=TO_NUMBER, body=body)

    emitted = [record.getMessage() for record in caplog.records if record.name == "app"]
    assert emitted == ["twilio refused a send: status=400 code=21610"]
    rendered = " ".join(emitted)
    assert code not in rendered
    assert body not in rendered
    for token in body.split():
        assert token not in rendered
    for secret in SECRETS:
        assert secret not in rendered


async def test_padded_credentials_are_trimmed_before_they_reach_the_wire() -> None:
    """The other half of `.strip()`: a value pasted into a Railway variable box
    or typed on an `.env` line keeps its trailing newline, and untrimmed it
    lands in the request path, the auth pair and the From field."""
    transport, seen = _mock(201, {"sid": "SM0123456789abcdef", "status": "queued"})
    padded = _settings(
        twilio_account_sid=f" {ACCOUNT_SID}\n",
        twilio_api_key_sid=f"{API_KEY_SID} ",
        twilio_api_key_secret=f"\t{API_KEY_SECRET}\n",
        twilio_from_number=f"{FROM_NUMBER}\n",
    )

    await TwilioSmsSender(padded, transport=transport).send(phone=TO_NUMBER, body="x")

    request = seen[0]
    assert str(request.url) == (
        f"https://api.twilio.com/2010-04-01/Accounts/{ACCOUNT_SID}/Messages.json"
    )
    _, _, encoded = request.headers["authorization"].partition(" ")
    assert base64.b64decode(encoded).decode() == f"{API_KEY_SID}:{API_KEY_SECRET}"
    assert dict(urllib.parse.parse_qsl(request.content.decode()))["From"] == FROM_NUMBER


# --- the failing call ---


async def test_error_response_raises_without_body_or_credentials() -> None:
    body = "שלום, ההזמנה שלך אושרה"
    transport, _ = _mock(400, _echoing_error_payload(body=body))

    with pytest.raises(SmsSendError) as caught:
        await TwilioSmsSender(_settings(), transport=transport).send(phone=TO_NUMBER, body=body)

    rendered = str(caught.value)
    # The operator still gets the two facts that identify the failure.
    assert "400" in rendered
    assert "21610" in rendered
    assert body not in rendered
    for secret in SECRETS:
        assert secret not in rendered
    assert "more_info" not in rendered
    assert "blacklist" not in rendered


async def test_non_json_error_body_still_raises_a_constructed_message() -> None:
    # A gateway 502 in front of Twilio answers HTML, not JSON. The adapter must
    # not carry that page — nor blow up parsing it.

    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="<html><body>upstream is very unwell</body></html>")

    with pytest.raises(SmsSendError) as caught:
        await TwilioSmsSender(_settings(), transport=httpx.MockTransport(handle)).send(
            phone=TO_NUMBER, body="שלום"
        )

    assert "502" in str(caught.value)
    assert "unwell" not in str(caught.value)


async def test_non_integer_error_code_is_never_echoed() -> None:
    # Twilio's `code` is always an integer. Anything else is refused rather than
    # stringified, so the field cannot become a second echo channel.
    body = "קוד האימות שלך: 424242"
    transport, _ = _mock(400, {"code": body, "message": "odd", "status": 400})

    with pytest.raises(SmsSendError) as caught:
        await TwilioSmsSender(_settings(), transport=transport).send(phone=TO_NUMBER, body=body)

    assert "424242" not in str(caught.value)


# --- THE test: an echoed OTP must not reach message_log.error ---


async def test_echoed_otp_never_survives_into_the_raised_exception() -> None:
    code = "483920"
    body = otp_sms_body(code)
    transport, _ = _mock(400, _echoing_error_payload(body=body))

    with pytest.raises(SmsSendError) as caught:
        await TwilioSmsSender(_settings(), transport=transport).send(phone=TO_NUMBER, body=body)

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
    code = "483920"
    body = otp_sms_body(code)
    transport, _ = _mock(400, _echoing_error_payload(body=body))
    recorder = _RecordingMessageLog()
    monkeypatch.setattr("app.notifications.service.tenant_session", _no_db_session)
    monkeypatch.setattr("app.notifications.service.MessageLogRepository", lambda: recorder)

    service = NotificationService(
        cast(Any, None), sender=TwilioSmsSender(_settings(), transport=transport)
    )
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


async def test_timeouts_are_explicit_on_the_client() -> None:
    """Structural, so an edit that drops `timeout=` is caught: both values are
    deliberately different from httpx's 5s default, which is what a bare client
    would report."""
    async with TwilioSmsSender(_settings())._client() as client:
        assert client.timeout.connect == CONNECT_TIMEOUT_SECONDS
        assert client.timeout.read == READ_TIMEOUT_SECONDS
    default = httpx.Timeout(5.0)
    assert default.connect != CONNECT_TIMEOUT_SECONDS
    assert default.read != READ_TIMEOUT_SECONDS


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


def test_build_sms_sender_dispatches_on_the_provider() -> None:
    assert isinstance(_build_sms_sender(_settings(sms_provider="twilio")), TwilioSmsSender)
    assert isinstance(_build_sms_sender(_settings(sms_provider="fake")), FakeSmsSender)
    assert isinstance(_build_sms_sender(_settings(sms_provider=None)), UnconfiguredSmsSender)


def test_worker_build_sender_dispatches_on_the_provider() -> None:
    # The worker drains F16's reminders through its OWN builder. Left behind, a
    # twilio deployment would send OTPs and silently leave every reminder pending.
    assert isinstance(build_sender(_settings(sms_provider="twilio")), TwilioSmsSender)
    assert isinstance(build_sender(_settings(sms_provider="fake")), FakeSmsSender)
    assert isinstance(build_sender(_settings(sms_provider=None)), UnconfiguredSmsSender)


def test_incomplete_credentials_degrade_to_503_rather_than_booting_dark() -> None:
    # Exactly today's state: the API key pair is supplied, the account SID is not.
    sender = _build_sms_sender(
        _settings(sms_provider="twilio", twilio_account_sid=None, twilio_from_number=None)
    )
    assert isinstance(sender, TwilioSmsSender)
    assert sender.is_configured is False


# --- where the credentials come from ---


def test_credentials_are_read_from_real_process_environment_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Railway's path. No `.env` exists there; the four names are real env vars."""
    for name, value in ENV_CREDENTIALS.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("SMS_PROVIDER", "twilio")

    sender = _build_sms_sender(Settings())

    assert isinstance(sender, TwilioSmsSender)
    assert sender.is_configured is True
    assert sender.from_number == FROM_NUMBER


def test_credentials_are_read_from_the_env_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The local path, and the defect this test exists for. `.env.example` tells
    an operator to put these four in `.env`, and pydantic-settings parses that
    file itself without ever writing os.environ — an adapter reading os.environ
    would report is_configured False here and answer 503 on every OTP with the
    credentials sitting right where the docs asked for them.

    Written through `model_config`'s own relative `env_file=".env"` rather than
    an `_env_file=` override, so what is under test is the mechanism the
    deployment actually uses."""
    for name in ENV_CREDENTIALS:
        monkeypatch.delenv(name, raising=False)
    (tmp_path / ".env").write_text(
        "SMS_PROVIDER=twilio\n"
        + "".join(f"{name}={value}\n" for name, value in ENV_CREDENTIALS.items())
    )
    monkeypatch.chdir(tmp_path)

    settings = Settings()
    sender = _build_sms_sender(settings)

    # The point of the test: nothing reached the process environment.
    assert all(os.environ.get(name) is None for name in ENV_CREDENTIALS)
    assert settings.sms_provider == "twilio"
    assert isinstance(sender, TwilioSmsSender)
    assert sender.is_configured is True
    assert sender.from_number == FROM_NUMBER


def test_credentials_never_render_through_settings() -> None:
    """SecretStr is what replaces the property the old process-env read bought:
    Settings is passed around, logged on config dumps and rendered into pydantic
    validation errors, and none of those may carry a key."""
    settings = _settings()
    rendered = " ".join(
        (
            repr(settings),
            str(settings),
            repr(settings.twilio_api_key_secret),
            str(settings.twilio_api_key_secret),
            repr(settings.model_dump()),
        )
    )
    for secret in SECRETS:
        assert secret not in rendered
    # The sender number is deliberately NOT a secret in this sense — main.py
    # logs it so a wrong-sender deployment is observable.
    assert TwilioSmsSender(settings).from_number == FROM_NUMBER
