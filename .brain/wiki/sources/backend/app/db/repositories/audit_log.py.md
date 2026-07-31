---
tags: [backend, db, python, audit, tenancy, repositories]
sources: [backend/app/db/repositories/audit_log.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/db/repositories/audit_log.py
blob: 7dfe1263238bb4d8eaa1826c72bd20c5dd5c7f28
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/db/repositories/audit_log.py

**Role.** Append-only writer for the per-tenant `audit_log` table — one `record()` that stamps an action, an optional actor and entity, and a JSON details blob into the caller's open transaction — plus a read helper used only by tests.

**Module.** [[backend/app/db/repositories/_index]] · **Layer.** db

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `AuditLogRepository` | class | Stateless; instantiated at the call site, session passed per call |
| `AuditLogRepository.record` | method | Adds one [[backend/app/models/audit_log.py]] row and flushes; returns `None` |
| `AuditLogRepository.list_actions` | method | Every `action` string visible to the current session, oldest first |

## Behavior

`record` is the odd one out in this package: it takes `tenant_id` as an explicit keyword and writes it onto the row, but it never puts a `tenant_id` predicate in a WHERE clause because it only ever inserts. The row lands under the same FORCE RLS `WITH CHECK` policy every tenant-scoped table carries, so an insert naming a tenant other than the bound one is refused by Postgres rather than by Python. `details` defaults to `{}` rather than `NULL` so that consumers can index into the JSON without a null branch. There is no `commit` — `flush()` only pushes the INSERT into the caller's transaction, which is what makes an audit row atomic with the thing it records: [[backend/app/auth/service.py]] writes the login row in the same transaction as the session insert, and [[backend/app/booking/owner.py]] rolls the audit row back with the booking change it describes when a guarded UPDATE matches zero rows.

`list_actions` carries **no** `tenant_id` predicate at all — deliberately, because it exists to prove that RLS alone confines the read. A test binds one tenant's context and asserts it sees only that tenant's actions; adding a redundant predicate here would make the assertion vacuous. Do not reuse it as a product read path.

This is not the platform-wide operator log. That is [[backend/app/platform/repository.py]]'s `PlatformAuditLogRepository` over [[backend/app/models/platform_audit_log.py]], which is INSERT-only at the grant level and names its column `target_tenant_id` precisely so it is not swept up by the tenant-RLS metadata scan.

## Depends On

- [[backend/app/models/audit_log.py]] — the ORM model
- [[SQLAlchemy]] — `AsyncSession`, `select`

## Depended On By

- [[backend/app/auth/service.py]] — `LOGIN`, `LOGIN_FAILED`, `LOGOUT`
- [[backend/app/auth/staff.py]] — `STAFF_CREATED`, `STAFF_UPDATED`, `STAFF_ROLE_CHANGED`, `STAFF_PASSWORD_RESET`, `STAFF_DEACTIVATED`
- [[backend/app/booking/owner.py]] — every owner-side booking mutation (`BOOKING_CONFIRMED`, `BOOKING_NO_SHOW`, `BOOKING_COMPLETED`, `BOOKING_CANCELLED`, `BOOKING_RESCHEDULED`, `BOOKING_PHONE_CORRECTED`, `BOOKING_LINK_RESENT`)

## Concepts

- [[Row Level Security]]
- [[Tenant Isolation]]

## Tests

- [[backend/tests/test_auth_integration.py]] — asserts the exact `list_actions` sequence after auth flows
- [[backend/tests/test_staff_management_db.py]] — asserts an empty log after a rejected staff mutation, i.e. that the audit row rolled back with it
- [[backend/tests/test_booking_owner_service.py]] — audit rows written (and not written) by owner actions

## Notes

`record` returning `None` is why callers cannot assert on the row they just wrote without a re-read; the tests use `list_actions` for that.
