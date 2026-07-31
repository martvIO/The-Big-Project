---
tags: [backend, notifications, sms, python, protocol, ports]
sources: [backend/app/notifications/base.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/notifications/base.py
blob: 048c0faf5ffb382b1b4b4faf5d83588446a75bdc
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/notifications/base.py

**Role.** Defines the SMS port — the `SmsSender` protocol, its `SendResult`, and the two-way failure vocabulary (`SmsNotConfiguredError` vs `SmsSendError`) that every adapter and every caller in the codebase agrees on.

**Module.** [[backend/app/notifications/_index]] · **Layer.** platform

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `SmsSender` | Protocol | `is_configured` property + `async send(*, phone, body) -> SendResult` — the whole contract an adapter must satisfy |
| `SendResult` | frozen dataclass | `provider_message_id: str \| None` — the only thing a successful send returns |
| `SmsNotConfiguredError` | exception | No provider configured. A *supported* deployment state, not a bug |
| `SmsSendError` | exception | The provider was unreachable or refused. Carries no provider-supplied text |

## Behavior

The module imports nothing from `app/db/` or any feature module, and that isolation is load-bearing: callers hand `send` a fully rendered body and an already-normalized E.164 phone, so templating stays in [[backend/app/booking/comms_templates.py]] and normalization stays in [[backend/app/notifications/validation.py]], and there is no import cycle back through the service. `SmsSender` is a structural `Protocol`, not an ABC — adapters do not subclass it, they just match the shape, and [[backend/tests/test_notifications_adapters.py]]'s `test_adapters_satisfy_the_protocol` is what keeps that honest.

The two exception types are **operationally distinct on purpose** and this distinction is an F11 ruling later features lean on. "Not configured" is known at boot and permanent; "send failed" is transient and provider-specific. [[backend/app/main.py]] maps them to two different 503s (`SMS_NOT_CONFIGURED` and `SMS_UNAVAILABLE`), and neither is ever allowed to become a 500 — an unconfigured deployment is a deployment choice, not a crash. `SmsSendError` deliberately carries no message: the provider's text is logged server-side and scrubbed onto the `message_log` row by [[backend/app/notifications/service.py#_scrub]], and never reaches the HTTP client. The evidence asymmetry matters downstream: a configured-but-failed send leaves a `failed` `message_log` row, while `SmsNotConfiguredError` is raised *before* any insert, so the unconfigured state is evidence-free by construction.

The module mirrors [[backend/app/storage/base.py]] deliberately, including the degradation contract — the media port and the SMS port answer absence the same way so an operator only has to learn the pattern once.

## Depends On

- `dataclasses`, `typing.Protocol` (stdlib only)

## Depended On By

- [[backend/app/notifications/fake.py]] — implements the protocol
- [[backend/app/notifications/unconfigured.py]] — implements it by raising
- [[backend/app/notifications/service.py]] — holds an `SmsSender`, re-raises both errors
- [[backend/app/main.py]] — `_build_sms_sender` returns `SmsSender`; registers the two exception handlers
- [[backend/app/booking/comms.py]] — catches both errors when draining scheduled messages

## Concepts

- [[Ports And Adapters]]
- [[Graceful Degradation]]

## Tests

- [[backend/tests/test_notifications_adapters.py]] — `test_adapters_satisfy_the_protocol`, `test_unconfigured_raises_and_reports`
- [[backend/tests/test_notifications_api.py]] — `test_send_error_mapping` asserts each error's HTTP status/code

## Notes

There is no error registry in [[backend/app/main.py]] — both of these needed an explicit `@app.exception_handler`. A third error type added here without a handler would surface as a 500.
