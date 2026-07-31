---
tags: [backend, notifications, sms, python, adapter, degradation]
sources: [backend/app/notifications/unconfigured.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/notifications/unconfigured.py
blob: ab3435130715f7786ff57e837847b91fc8763704
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/notifications/unconfigured.py

**Role.** The null `SmsSender` for a deployment with no SMS provider: `is_configured` is `False` and `send` raises `SmsNotConfiguredError`, turning "no provider" into a defined 503 rather than an import-time failure or a silent no-op.

**Module.** [[backend/app/notifications/_index]] · **Layer.** platform

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `UnconfiguredSmsSender` | class | `is_configured` → `False`; `send` → raises `SmsNotConfiguredError` |

## Behavior

`send` **raises** rather than returning a failed `SendResult`, and that choice is the contract: a raise is what lets [[backend/app/notifications/service.py#send_sms]] mark its `message_log` row `failed` with a reason and lets [[backend/app/main.py]]'s handler answer 503 `SMS_NOT_CONFIGURED`. A returned failure object would have to be inspected at every call site and would eventually be ignored at one of them.

In practice the raise from `send` is a backstop that rarely fires, because both callers check `is_configured` first and bail *before* any database write — [[backend/app/notifications/service.py#send_sms]] and `OtpService.send` each raise `SmsNotConfiguredError` up front, precisely so an unconfigured deployment does not soft-delete a live OTP code, spend a send budget, or accumulate two orphan rows per anonymous request on the way to the same 503 (F11 review finding 10). The net effect is the deliberate asymmetry the rest of the module relies on: a *configured* provider that fails leaves an evidence row; an *unconfigured* deployment leaves nothing at all.

Shape-mirrors `UnconfiguredMediaStorage` in [[backend/app/storage/unconfigured.py]], so absence of a bucket and absence of an SMS route degrade identically.

## Depends On

- [[backend/app/notifications/base.py]] — `SendResult`, `SmsNotConfiguredError`

## Depended On By

- [[backend/app/main.py]] — `_build_sms_sender` default when `sms_provider` is unset or unrecognised
- [[backend/app/worker.py]] — `build_sender` returns it; due reminders are then left pending rather than dropped
- [[backend/tests/test_booking_service.py]], [[backend/tests/test_booking_comms_db.py]], [[backend/tests/test_booking_owner_db.py]] — drive the degraded path

## Concepts

- [[Graceful Degradation]]
- [[Ports And Adapters]]

## Tests

- [[backend/tests/test_notifications_adapters.py]] — `test_unconfigured_raises_and_reports`
- [[backend/tests/test_notifications_service.py]] — `test_unconfigured_sender_writes_nothing`

## Notes

`sms_provider = None` is a **supported** deployment, not a misconfiguration — same stance [[backend/app/core/config.py]] takes on a missing `media_bucket`. Booking is structurally gated on the sender-ID registration existing, so an un-provisioned tenant simply cannot reach the send path.
