---
tags: [backend, notifications, sms, python, testing, adapter]
sources: [backend/app/notifications/fake.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/notifications/fake.py
blob: 15b97450fdcf62980c9017619fb8a28220003cba
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/notifications/fake.py

**Role.** The in-memory `SmsSender` adapter used by dev, the db test suite, and staging until a real provider lands — it appends every send to a public `outbox` list and returns a synthetic `fake-N` message id.

**Module.** [[backend/app/notifications/_index]] · **Layer.** platform

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `SentSms` | frozen dataclass | `phone` + `body` — one captured send |
| `FakeSmsSender` | class | `outbox: list[SentSms]`, `is_configured` → always `True`, `async send(...)` |

## Behavior

`send` appends a `SentSms` to `outbox` and mints `f"fake-{n}"` from an `itertools.count(1)` instance counter, so ids are per-sender-instance and monotonic — tests assert on send *order* through the outbox, not through timestamps. `is_configured` is hardcoded `True`, which is exactly what makes this adapter a valid stand-in for a working provider: [[backend/app/notifications/service.py]] gates on `is_configured` before writing anything, so a fake that reported `False` would exercise the unconfigured path instead of the happy one.

**The body is deliberately not logged.** The INFO line records the message id and the body's *character count* only. Staging runs this adapter on a publicly reachable host whose log stream is widely readable, so an INFO line carrying the live OTP code plus the customer's number would hand verification to anyone with log access — defeating the masking that [[backend/app/notifications/validation.py#mask_otp_body]] applies two layers up before the body reaches `message_log`. The `outbox` is the sanctioned way to read bodies, and it only exists in-process.

Nothing resets `outbox`, so a long-lived process grows it without bound. That is acceptable only because this adapter is never the production sender; in tests each app/service construction gets a fresh instance.

## Depends On

- [[backend/app/notifications/base.py]] — `SendResult` (structurally satisfies `SmsSender` without importing it)

## Depended On By

- [[backend/app/main.py]] — `_build_sms_sender` returns this when `sms_provider == "fake"`
- [[backend/app/worker.py]] — `build_sender` mirrors the same choice for the reminder poller
- [[backend/tests/test_booking_comms_db.py]], [[backend/tests/test_booking_owner_db.py]], [[backend/tests/test_notifications_service.py]] — assert against `outbox`

## Concepts

- [[Ports And Adapters]]
- [[Test Doubles]]

## Tests

- [[backend/tests/test_notifications_adapters.py]] — `test_fake_captures_sends_in_order`, `test_fake_is_configured`

## Notes

`sms_provider="fake"` is a **boot failure** in production — [[backend/app/core/config.py]]'s `_forbid_sms_test_paths_in_production` validator refuses to start, because a sender that "sends" nothing silently voids the phone verification the whole booking flow rests on.
