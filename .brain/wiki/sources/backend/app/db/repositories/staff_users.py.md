---
tags: [backend, db, repository, auth, staff, roles, python, sqlalchemy]
sources: [backend/app/db/repositories/staff_users.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/db/repositories/staff_users.py
blob: 35ff17c69e92e48bccee8fe55776f7f7073490f3
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/db/repositories/staff_users.py

**Role.** The `staff_users` table: the by-email read login runs, the by-id read session resolution runs on every request, the console's ordered roster, the live-owner count the last-owner invariant rests on, plus insert, partial update, and soft delete.

**Module.** [[backend/app/db/repositories/_index]] · **Layer.** db

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `StaffUsersRepository` | class | The repository; explicit `AsyncSession` + `tenant_id` on every method |
| `by_email` | method | Login's credential lookup, live rows only |
| `by_id` | method | Session resolution's re-read — the seam that makes deactivation take effect immediately |
| `list_live` | method | The roster, `created_at ASC` so the founding owner is first and rows do not shuffle |
| `count_live_owners` | method | The last-owner invariant's read — correct **only** under the caller's advisory lock |
| `insert` | method | New staffer; `role` defaults to `StaffRole.OWNER.value` |
| `update` | method | Patch of `display_name` / `role` / `password_hash`; all-omitted is a legal no-op |
| `soft_delete` | method | Guarded `deleted_at` stamp; `True` iff a live row was hit |

## Behavior

Every read filters `deleted_at IS NULL`, which is what makes a deactivated staffer's still-valid cookie fail on her next request without any session sweep — `by_id` is that seam. `count_live_owners` is the interesting one: it counts live `owner` rows, and it is only sound inside the advisory lock [[backend/app/auth/staff.py]] takes, because a count read outside the lock is a count a concurrent demotion or delete has already invalidated. No index supports it deliberately — RLS narrows the scan to one tenant's single-digit staff roster. `update` returns the row unchanged when every optional argument is omitted, because the service's no-op PATCH path calls straight through and an empty `.values()` would be a SQLAlchemy error rather than a 200; it never assigns `updated_at`, leaving that to the DB trigger and letting `refresh` pull the trigger's value back. `soft_delete` answers a bool rather than the row (the DELETE route returns an ok-response and the service already holds the row from its post-lock read), and its `deleted_at IS NULL` predicate makes a second call answer `False` instead of re-stamping. `insert`'s Python-level `role` default exists so the shipped tenant-provisioning path did not have to be edited to restate what the column's server default already says; the one consequence is that the INSERT now emits `role='owner'` explicitly.

## Depends On

- [[backend/app/models/staff_user.py]] — the `StaffUser` ORM entity
- [[backend/app/models/constants.py]] — `StaffRole`
- [[SQLAlchemy]] — `select` / `update` / `func`, `AsyncSession`

## Depended On By

- [[backend/app/auth/service.py]] — login and session resolution
- [[backend/app/auth/staff.py]] — staff management (roster, create, patch, delete) and the last-owner guard
- [[backend/app/platform/service.py]] — provisions the founding owner when a tenant is created

## Concepts

- [[Row Level Security]]
- [[Tenant Isolation]]
- [[Least Privilege Database Role]]

## Tests

- [[backend/tests/test_staff_management_db.py]]
- [[backend/tests/test_staff_role_gating_integration.py]]
- [[backend/tests/test_auth_integration.py]]
- [[backend/tests/test_provisioning.py]]
- [[backend/tests/test_boutique_integration.py]]
- [[backend/tests/test_migrations.py]]

## Notes

This class's docstring is the canonical statement of the house defence-in-depth rule — the other tenant-scoped repositories in this directory cite it by name rather than repeating it. Password hashing happens in [[backend/app/auth/passwords.py]]; this file only stores the hash it is handed.
