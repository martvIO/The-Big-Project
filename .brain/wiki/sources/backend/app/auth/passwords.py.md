---
tags: [backend, auth, python, passwords, argon2, security, timing]
sources: [backend/app/auth/passwords.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/auth/passwords.py
blob: a6f584eac1c05432cdec77a045fd20e5bd0e3fe6
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/auth/passwords.py

**Role.** The one argon2 hasher for staff passwords, plus `verify_password_dummy` — a verify against a precomputed throwaway hash whose only job is to make the unknown-email login path burn the same CPU as a real one, so response time cannot enumerate accounts.

**Module.** [[backend/app/auth/_index]] · **Layer.** auth

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `hash_password` | fn | argon2 hash with `argon2-cffi`'s default parameters |
| `verify_password` | fn | `True` / `False` — `VerifyMismatchError` becomes `False`, every other argon2 exception propagates |
| `verify_password_dummy` | fn | Verifies against `_DUMMY_HASH` and always returns `False` — the timing equalizer |
| `_hasher` | module const | Single process-wide `PasswordHasher` |
| `_DUMMY_HASH` | module const | Hash of a fixed nonsense string, computed once at import |

## Behavior

`verify_password` catches only `VerifyMismatchError` and lets anything else escape. That is the interesting asymmetry: a *wrong password* is a normal business outcome and becomes `False`, while a **malformed or unparseable stored hash** (`InvalidHashError`, `HashingError`) is data corruption and is allowed to become a 500 rather than being laundered into "wrong password" — a corrupted row that silently reads as a failed login would be invisible forever. `verify_password_dummy` is the reason the unknown-email branch in [[backend/app/auth/service.py#login]] does not return early: without it, "no such account" would answer in microseconds while "wrong password" spent argon2's full cost, and the difference is measurable over the network, turning the login endpoint into an account-existence oracle for a tenant. `_DUMMY_HASH` is computed at import so the equalizing verify costs exactly one verify and no extra hash. Neither `hash_password` nor `verify_password` is async and both are CPU-bound by design — callers that can hoist them out of a database session do (see `create` and `update` in [[backend/app/auth/staff.py]], which hash *before* opening `tenant_session` so a pooled connection is not held across the work). Cost parameters are argon2-cffi's defaults, not pinned here; upper-bounding the *input* is done in the schema instead (`MAX_PASSWORD_LENGTH` in [[backend/app/auth/schemas.py]]), because argon2 cost scales with input size and an unbounded password field is a CPU DoS.

## Depends On

- [[Argon2]] — `PasswordHasher`, `VerifyMismatchError` (entity)

## Depended On By

- [[backend/app/auth/service.py]] — `verify_password` on the real path, `verify_password_dummy` on the unknown-email path
- [[backend/app/auth/staff.py]] — `hash_password` on create/update, `verify_password` for the self `current_password` check
- [[backend/app/platform/service.py]] — `hash_password` when the provisioning CLI seeds a tenant's first owner

## Concepts

- [[Account Enumeration Resistance]]
- [[Session Authentication]]

## Tests

- [[backend/tests/test_passwords.py]] — hash/verify round-trip, mismatch, and that `verify_password_dummy` returns `False`
- [[backend/tests/test_auth_integration.py]] — seeds a real hash and logs in against it
- [[backend/tests/test_staff_management_db.py]] · [[backend/tests/test_staff_service.py]] — assert a password write actually changed the stored hash

## Notes

The timing equalizer only holds as far as the argon2 work: the unknown-email branch also writes a `LOGIN_FAILED` audit row with the email as `entity`, and the known-email branch writes one with an `actor_id` as well — a difference in *database* work, not CPU. Both paths commit before raising, and both answer the same 401 body, so this is noted as a residual rather than a defect.

Design context: [[.planning/specs/owner-auth.md]].
