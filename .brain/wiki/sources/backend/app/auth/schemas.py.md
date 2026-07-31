---
tags: [backend, auth, python, pydantic, schemas, validation, staff, passwords]
sources: [backend/app/auth/schemas.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/auth/schemas.py
blob: b660d9f25454b3f396866061d68e9cf25b743901
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/auth/schemas.py

**Role.** The wire contract for login and for owner staff administration, plus the three password/name bounds the frontend is held to by a parity test — and `StaffMember`, whose safety comes from what it does *not* model.

**Module.** [[backend/app/auth/_index]] · **Layer.** api

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `MAX_PASSWORD_LENGTH` | const | `4096` — argon2 cost scales with input, so this is the CPU-DoS cap |
| `MIN_STAFF_PASSWORD_LENGTH` | const | `10` — above NIST SP 800-63B's floor of 8, with no composition rules |
| `MAX_DISPLAY_NAME_LENGTH` | const | `200` — matches `MAX_APPOINTMENT_TYPE_NAME_LENGTH` in [[backend/app/boutique/validation.py]] |
| `DisplayName` | annotated type | `strip_whitespace` **then** `min_length=1`, `max_length=200` |
| `LoginRequest` | model | `email` (`EmailStr`, ≤320), `password` (≥1) — no minimum, so an old short password can still sign in |
| `StaffResponse` | model | The `/manage/auth/login` and `/me` body: `id`, `email`, `display_name`, `role` |
| `StaffMember` | model | A staff row on the wire — `password_hash` and `deleted_at` absent by construction |
| `CreateStaffRequest` | model | `ForbidExtraModel`; `role` typed as the `StaffRole` enum |
| `UpdateStaffRequest` | model | All fields optional; `email` deliberately absent |

## Behavior

The ordering inside `DisplayName` is the whole point: `strip_whitespace=True` runs *before* the bounds, so `"   "` is rejected. A bare `min_length=1` would admit it, and a whitespace-only name renders as an empty element in the Hebrew console — a staffer identifiable only by her email address. Stripping also collapses `" Dana"` and `"Dana"` into one value, which is what stops `StaffService.update`'s no-op comparison from being fooled by a trailing space into writing a pointless row and audit entry.

`role` is typed as `StaffRole` rather than `str`, so an unknown value is refused at the boundary as a validation error — normalized app-wide to a **400** by the `RequestValidationError` handler in [[backend/app/main.py]] (this backend emits no default 422s) — and can never reach migration 0011's `CHECK` constraint. Both mutation requests extend `ForbidExtraModel` from [[backend/app/schemas.py]], so an unknown key is a 400 rather than a silently dropped field.

`UpdateStaffRequest` omits `email` on purpose: the uniqueness index on `staff_users` is *partial* on `deleted_at IS NULL`, so deactivate-and-recreate is the supported remedy for a wrong address, and a login identity must not move under a live session. `current_password` carries a `max_length` but **no** `min_length` — deliberately, so a wrong value surfaces as a domain 400 in the console's own Hebrew rather than as a schema error complaining about its length.

`StaffMember` is the response model for the staff list and every staff mutation. `password_hash` and `deleted_at` are not fields, which means no serializer has to remember to exclude them and every row the list returns is live by definition — a safety property held by the type rather than by a filter someone maintains.

`LoginRequest.password` has `min_length=1`, not `MIN_STAFF_PASSWORD_LENGTH`: raising the login minimum would lock out any account seeded before the rule and turn a length check into an account-existence signal.

## Depends On

- [[backend/app/schemas.py]] — `ForbidExtraModel`
- [[backend/app/models/constants.py]] — `StaffRole`
- [[Pydantic]] — `BaseModel`, `EmailStr`, `Field`, `StringConstraints` (entity)

## Depended On By

- [[backend/app/auth/router.py]] — `LoginRequest`, `StaffResponse`
- [[backend/app/auth/staff_router.py]] — `CreateStaffRequest`, `UpdateStaffRequest`, `StaffMember`

## Concepts

- [[Input Validation At The Boundary]]
- [[Role Based Access Control]]

## Tests

- [[backend/tests/test_frontend_constant_parity.py]] — asserts `MIN_STAFF_PASSWORD_LENGTH`, `MAX_PASSWORD_LENGTH` and `MAX_DISPLAY_NAME_LENGTH` match the frontend's copies, so the console cannot drift from the server's rules
- [[backend/tests/test_staff_api.py]] — the rejection cases: blank/whitespace name, unknown role, short password, unknown key, and that `password_hash` never appears in a response
- [[backend/tests/test_auth_api.py]] — `LoginRequest` malformed-body handling

## Notes

`staff_users.display_name` is unbounded `TEXT` with no `CHECK` in the schema; the 200-character ceiling exists only here, so a writer that bypasses this model (the provisioning CLI, a migration) is not bound by it.

Rejected explicitly with the 10-character minimum: composition rules (800-63B advises against them, and they push an owner toward `Boutique1!`), rotation, and a breach-list check — the last would put a network dependency on the login path of a five-account tenant.

Design context: [[.planning/specs/staff-management.md]].
