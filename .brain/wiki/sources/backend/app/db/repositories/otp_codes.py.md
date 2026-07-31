---
tags: [backend, db, repository, notifications, otp, phone-verification, python, sqlalchemy]
sources: [backend/app/db/repositories/otp_codes.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/db/repositories/otp_codes.py
blob: 3ff097a958a5e13ead9aebd581418505396205b3
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/db/repositories/otp_codes.py

**Role.** The whole phone-verification lifecycle in SQL: store a hashed OTP, find the one live code for a phone, retire superseded codes, count guesses atomically, and mint then single-use-consume the verification token a booking must present.

**Module.** [[backend/app/db/repositories/_index]] · **Layer.** db

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `OtpCodesRepository` | class | The repository; explicit `AsyncSession` + `tenant_id` on every method |
| `insert` | method | New `OtpCode` for `(phone, code_hash, expires_at)` |
| `latest_active_by_phone` | method | The single unconsumed, un-soft-deleted code for a phone, newest first |
| `soft_delete_active_for_phone` | method | Retires every live code for a phone; returns how many |
| `increment_attempts` | method | `attempts = attempts + 1` in SQL, returning the **new** value |
| `mark_consumed` | method | Stamps `consumed_at` and mints `verification_token_hash` / `verification_expires_at` in one guarded write |
| `consume_verification` | method | Atomically burns the verification token for a phone; `True` iff this call won |

## Behavior

Every state change here is a guarded `UPDATE ... RETURNING`, never read-modify-write, because each one is exactly the kind of thing two concurrent requests race for. `increment_attempts` does the arithmetic in SQL so parallel guesses cannot each read the same count and hand the attacker free tries beyond the per-code cap. `mark_consumed` filters on `consumed_at IS NULL`, so a raced double-verify mints at most one verification token — the loser gets `None` — and it re-selects the row afterwards because the UPDATE returns only the id. `consume_verification` is the single-use claim: the row must match the phone, the token hash, an unconsumed `verification_consumed_at`, and an unexpired `verification_expires_at`, all in one statement; the **phone predicate is the security-relevant one**, binding a token to the number it verified so a stolen token cannot be spent booking for a different phone. `latest_active_by_phone` orders `created_at DESC LIMIT 1` even though the send path maintains a one-live-code invariant via `soft_delete_active_for_phone` — belt-and-braces so a race that ever left two codes still resolves to the newest. Policy (code length, TTLs, the attempt ceiling) lives in [[backend/app/notifications/validation.py]], not here; this file only enforces the concurrency invariants.

## Depends On

- [[backend/app/models/otp_code.py]] — the `OtpCode` ORM entity
- [[SQLAlchemy]] — `select` / `update` / `func`, `AsyncSession`

## Depended On By

- [[backend/app/notifications/service.py]] — the send/verify flow and the verification-token consumption the booking path calls into

## Concepts

- [[Row Level Security]]
- [[Tenant Isolation]]
- [[Fail Closed Defaults]]

## Tests

- [[backend/tests/test_notifications_repositories.py]]
- [[backend/tests/test_notifications_isolation.py]]
- [[backend/tests/test_notifications_service.py]]
- [[backend/tests/test_booking_service.py]]
- [[backend/tests/test_booking_comms_db.py]]
- [[backend/tests/test_booking_owner_db.py]]

## Notes

Only hashes are stored — never a raw OTP and never a raw verification token — so a DB read cannot be replayed as a verification. `increment_attempts` returning `0` is ambiguous by construction: it means "no live row matched", which callers must not mistake for "zero attempts so far".
