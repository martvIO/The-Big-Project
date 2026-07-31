---
tags: [backend, python]
sources: [backend/app/notifications]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/notifications
blob: 9daffe4ae23398eca6a2ef5e18419cdd3a4d5ebc
commit: 13d107b8b16f1f2676f1cdb1c994f95822fe2ba0
kind: directory
applicability: active
---

# backend/app/notifications/

**Purpose.** The SMS port and the OTP primitive: a provider-agnostic sender, its fake and unconfigured adapters, and the single writer of the `message_log` evidence trail.

**Parent.** [[backend/app/_index]]

## Files

- [[backend/app/notifications/__init__.py]] — Empty package marker for the SMS/OTP module — it re-exports nothing, so every importer names the submodule directly (`from app.notifications.service import OtpService`).
- [[backend/app/notifications/base.py]] — Defines the SMS port — the `SmsSender` protocol, its `SendResult`, and the two-way failure vocabulary (`SmsNotConfiguredError` vs `SmsSendError`) that every adapter and every caller in the codebase agrees on.
- [[backend/app/notifications/fake.py]] — The in-memory `SmsSender` adapter used by dev, the db test suite, and staging until a real provider lands — it appends every send to a public `outbox` list and returns a synthetic `fake-N` message id.
- [[backend/app/notifications/router.py]] — The public OTP surface: two anonymous, tenant-scoped POSTs (`/storefront/otp/send` → 204, `/storefront/otp/verify` → a `verification_token`), both forced `cache-control: no-store`, both resolving the tenant from the Host header and…
- [[backend/app/notifications/schemas.py]] — The three Pydantic models on the public OTP wire — send request, verify request, verify response — plus the two length ceilings that stop an oversized body from ever reaching the service layer.
- [[backend/app/notifications/service.py]] — Two services stacked on the SMS port: `NotificationService.send_sms` is the **single writer of `message_log`** for the entire application (insert `queued` → call the adapter → mark `sent`/`failed`), and `OtpService` owns the code lifecycle…
- [[backend/app/notifications/unconfigured.py]] — The null `SmsSender` for a deployment with no SMS provider: `is_configured` is `False` and `send` raises `SmsNotConfiguredError`, turning "no provider" into a defined 503 rather than an import-time failure or a silent no-op.
- [[backend/app/notifications/validation.py]] — The one place OTP *product policy* lives — code length, TTL, verify-attempt cap, verification-token TTL — plus the pure helpers that normalize an Israeli mobile to E.164, mint a code, render the Hebrew SMS body, and mask the code out of it…
