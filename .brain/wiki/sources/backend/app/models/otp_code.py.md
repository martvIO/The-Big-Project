---
tags: [backend, models, python, notifications, otp, security, sqlalchemy]
sources: [backend/app/models/otp_code.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/models/otp_code.py
blob: 8b6315dc7ddbe4af62e878699f36f18d8f3015ad
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/models/otp_code.py

**Role.** The phone-verification row: one live SMS code per (tenant, phone) with its expiry and attempt counter, plus — on the *same* row — the short-lived verification token that a successful verify mints and the booking transaction later spends.

**Module.** [[backend/app/models/_index]] · **Layer.** models

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `OtpCode` | class | ORM mapping for `otp_codes`; `StandardColumns` + `Base` |
| `tenant_id` | col | `UUID NOT NULL` — RLS discriminator |
| `phone` | col | `TEXT NOT NULL` — the number the code was sent to |
| `code_hash` | col | `TEXT NOT NULL` — digest of the numeric code, never the code |
| `expires_at` | col | `TIMESTAMPTZ NOT NULL` |
| `attempts` | col | `INTEGER NOT NULL DEFAULT 0`, DB `CHECK (0 … 50)` |
| `consumed_at` | col | `TIMESTAMPTZ NULL` — set when the code is successfully verified |
| `verification_token_hash` | col | `TEXT NULL` — minted on successful verify |
| `verification_expires_at` | col | `TIMESTAMPTZ NULL` |
| `verification_consumed_at` | col | `TIMESTAMPTZ NULL` — set when the booking transaction spends the token |

## Behavior

This row has **two** lifecycles stacked on it, which is why nine columns sit on one table instead of two. First the code: sent, then either expired, or guessed wrong up to the service cap, or verified — at which point `consumed_at` is stamped. Verification then mints a bearer token whose hash, expiry and consumption occupy the three `verification_*` columns. All three shipped in [[backend/migrations/versions/0007_sms_foundation.py]] rather than with the booking feature specifically so that migration 0008 never had to touch this table.

The **one-live-code invariant** is maintained by the service, not by an index: a resend calls `soft_delete_active_for_phone` to retire its predecessor before inserting. The partial index `(tenant_id, phone) WHERE consumed_at IS NULL AND deleted_at IS NULL` keeps consumed and invalidated rows out of the scan the send and verify paths run on every request; `latest_active_by_phone` still orders by `created_at DESC` so the read stays correct even if a race ever left two live rows behind. `increment_attempts` is a SQL-level `attempts = attempts + 1` returning the new value — a read-modify-write here would race concurrent guesses into free tries, which is the whole security argument for the attempt cap.

The `CHECK (attempts <= 50)` is an absurdity ceiling at 10× the service cap of 5, in the house convention: it stops a broken write path, it does not encode the policy. Likewise the file's own docstring is explicit that `code_hash` is **hygiene, not a boundary** — a six-digit code is brute-forceable by hashing, so the real controls are the attempt cap, the expiry, and the separately-budgeted verify rate limit in [[backend/app/core/config.py]] (verify is throttled independently of send, because otherwise an attacker just requests a fresh code and keeps guessing).

## Depends On

- [[backend/app/models/base.py]] — `Base`, `StandardColumns`
- [[SQLAlchemy]] — declarative mapping

## Depended On By

- [[backend/app/db/repositories/otp_codes.py]] — the only repository over this table
- [[backend/app/notifications/service.py]] — `OtpService` send / verify; mints the verification token
- [[backend/app/booking/service.py]] — spends the verification token inside the booking transaction (via the notification service, not by importing this model)

## Concepts

- [[Row Level Security]]
- [[Tenant Isolation]]
- [[Fail Closed Defaults]]

## Tests

- [[backend/tests/test_notifications_repositories.py]] — insert, latest-active read, soft delete, atomic attempt increment
- [[backend/tests/test_notifications_service.py]] — send/verify rules, one-live-code invariant, attempt cap
- [[backend/tests/test_notifications_isolation.py]] — cross-tenant reads return nothing
- [[backend/tests/test_notifications_validation.py]] — code length, TTLs and the attempt cap live there, not in config
- [[backend/tests/test_booking_service.py]], [[backend/tests/test_booking_comms_db.py]], [[backend/tests/test_booking_owner_db.py]] — token consumption on the booking path

## Notes

The `verification_*` columns being nullable is what makes "verified" a distinct state from "code sent": a row with `consumed_at` set but `verification_consumed_at` still `NULL` is a phone that has proven itself and not yet booked. Nothing in the schema forces the token to be spent — expiry does that.

Design context: [[.planning/specs/sms-foundation.md]], [[.planning/specs/booking-core.md]].
