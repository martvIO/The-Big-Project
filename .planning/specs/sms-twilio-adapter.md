# Spec: Feature 54 — Twilio SMS adapter (real sends)

**Created**: 2026-07-31 · **Status**: Gate 1 self-approved (not a money/legal surface; the provider decision was already made in F11) · **Epic**: E3 carve-out · **Effort**: **S**
**Depends on**: F11 (the `SmsSender` port, `NotificationService`, `message_log`) · **Feeds**: every real SMS the platform sends — OTP verification, booking confirmations, reminders, owner cancel/reschedule notices.

---

## Problem

F11 shipped the port and deliberately did not ship the provider. `.planning/specs/sms-foundation.md:148-163` names Twilio for the pilot and says plainly: *"The Twilio adapter itself is out of scope for F11 — it lands as its own small commit once the account and registered sender exist."*

The account now exists. The user supplied Twilio credentials on 2026-07-31 and they are wired into `Backend/.env`. So every SMS the product promises — the OTP that gates booking, F16's confirmation and 24h reminder, F15's owner cancel/reschedule notices — currently reaches `UnconfiguredSmsSender` and answers `503 SMS_NOT_CONFIGURED`. This feature is the one commit between "the platform can send SMS" and "the platform cannot".

## Goal

`SMS_PROVIDER=twilio` makes `_build_sms_sender` return a `TwilioSmsSender` that posts to Twilio's REST API and returns the provider's message SID. Everything upstream is untouched: `NotificationService` already inserts `queued`, calls `send()` outside any transaction, and marks `sent`/`failed`, and the error contract already scrubs provider text. A failure answers `503 SMS_UNAVAILABLE` with no Twilio wording on the wire, and the provider's own error lands on `message_log.error` for the operator.

## The port this must satisfy (verbatim, `Backend/app/notifications/base.py:29-34`)

```python
class SmsSender(Protocol):
    @property
    def is_configured(self) -> bool: ...

    async def send(self, *, phone: str, body: str) -> SendResult: ...
```

Two members. `SendResult(provider_message_id: str | None)`. Raise `SmsNotConfiguredError` for "no provider", anything else for a failed send — `NotificationService.send_sms` (`service.py:122-130`) catches bare `Exception`, scrubs it onto the row, and re-raises `SmsSendError`.

## Design

### Credentials — process env, not `Settings`

The house precedent is `_build_media_storage`/boto3 (`config.py:43-44`, `.env.example:15-18`): provider credentials an SDK reads from the environment stay out of the config object. This adapter reads its own four values from `os.environ` and reports `is_configured=False` when any is missing, which routes to the same 503 as no provider at all.

| Env var | Why |
|---|---|
| `TWILIO_ACCOUNT_SID` | the REST path is `/2010-04-01/Accounts/{AccountSid}/Messages.json` — **an API key pair alone names no account** |
| `TWILIO_API_KEY_SID` | HTTP basic username (`SK…`) |
| `TWILIO_API_KEY_SECRET` | HTTP basic password |
| `TWILIO_FROM_NUMBER` | E.164 sender. **A `PN…` resource SID is NOT valid as `From`** — Twilio wants the number itself (or an `MG…` Messaging Service SID, which a later commit may add) |

**Two of these are not yet supplied.** `external-applications.md` row 4b records that the user sent `TWILIO_API_KEY_SID`, `TWILIO_API_KEY_SECRET` and a `PN…` SID, but not the Account SID or the E.164 number. That gates a *live send*, not this build: the adapter is built and fully tested against a faked HTTP transport, and `is_configured` returns `False` until all four are present, so a half-configured deployment degrades to 503 instead of erroring at runtime.

### Transport — httpx, and it must be promoted to a runtime dependency

`Backend/pyproject.toml:37` has `httpx>=0.28` inside `[dependency-groups] dev`. It is currently a test-only dependency (FastAPI's TestClient). This adapter is the first runtime consumer, so httpx moves into `[project] dependencies`. **`uv.lock` must be regenerated in the same commit** or the CI `uv sync --locked` step fails.

No `twilio` SDK. The call is one form-encoded POST; the SDK would add a large sync-first dependency for one request, and `RETROFIT`-style thin clients are the house pattern. Timeouts must be explicit (connect + read), because a hung provider call would otherwise hold a request thread while a bride waits on an OTP.

### The call

`POST https://api.twilio.com/2010-04-01/Accounts/{ACCOUNT_SID}/Messages.json`, HTTP basic auth with the API key pair, form body `To` / `From` / `Body`. Success (201) returns JSON with `sid` → `SendResult(provider_message_id=sid)`. Any non-2xx raises, carrying Twilio's `code`/`message` for the log only.

### The hazard this feature must actively defend

`Backend/app/notifications/service.py:50-53` says why `_scrub` exists:

> several SMS SDKs echo the failing request — including the message body — in their exception

Twilio is exactly that shape: its error payloads routinely quote the submitted parameters, and its 400s embed a `more_info` URL plus the offending value. An OTP body echoed into `message_log.error` would defeat the masking `message_log` does one layer up — the code would sit in plaintext in a column the operator console can read. So:

- The adapter raises with a **constructed** message (`f"twilio {status}: {code}"`), never the raw response body.
- A test feeds a realistic Twilio error payload that contains the OTP body verbatim and asserts the recorded `message_log.error` does **not** contain it. This is the test that earns the feature.

### Wiring

`config.py:57` — `sms_provider: Literal["fake"] | None` widens to `Literal["fake", "twilio"] | None`.
`main.py:280-288` — one `elif settings.sms_provider == "twilio":` branch returning `TwilioSmsSender()`, with an INFO line that names the provider and the sender number but never a credential, matching the existing two branches.
The production boot guard (`config.py:172`) already forbids `fake` in production and needs no change — `twilio` is the value that makes production legal.

## Non-goals

- **No Messaging Service (`MG…`) support**, no alphanumeric sender. The `MODRYN` sender ID still needs registration (`external-applications.md` row 4, ~1 week) and until then sends come from the long-code number. Adding `MG` support later is a one-line branch on which env var is present.
- **No delivery-status webhook.** `message_log.status` stays `sent` at handoff; whether the handset received it is a separate feature.
- **No retry.** `NotificationService` records `failed` and the caller sees 503; the scheduled-message poller already retries its own kind.

## Tests

Fast, no network, no db:
- `is_configured` is False when any of the four env vars is missing, True when all are present.
- A successful send posts to the right URL with the right auth and form fields, and returns the `sid` from the response.
- A Twilio error response raises, and the raised message contains **neither** the message body nor the credentials.
- **The scrub test**: a realistic Twilio 400 payload echoing the OTP body → the exception, and by extension `message_log.error`, contains no part of that body.
- Unconfigured adapter raises `SmsNotConfiguredError`, which `NotificationService` maps to 503 `SMS_NOT_CONFIGURED`.
- Timeouts are set on the client (asserted structurally, so a future edit that drops them is caught).
- `test_frontend_constant_parity.py` and the existing notifications suites stay green.

## Risks

1. **Live sends cost money and reach real handsets.** Dev and test default to `fake`; `twilio` is opt-in per environment. Staging stays `fake` until the user asks otherwise.
2. **Two credentials still missing** — the feature ships dark. Recorded as a park-note on the queue entry, not a blocker on the build.
3. **Long-code sender in Israel** may see carrier filtering that the registered alphanumeric sender would not. Row 4 of the tracker owns that.
