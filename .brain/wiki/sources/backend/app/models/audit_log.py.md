---
tags: [backend, models, db, audit, security, python]
sources: [backend/app/models/audit_log.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/models/audit_log.py
blob: f3a6e0ef4c195558cf0afe521edc7d0cef324809
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/models/audit_log.py

**Role.** The `audit_log` table: the per-tenant record of who did what inside one boutique — logins, staff-management changes and every owner action on a booking — with a JSONB `details` bag for the action-specific payload.

**Module.** [[backend/app/models/_index]] · **Layer.** models

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `AuditLog` | class | `StandardColumns, Base` → `audit_log` |
| `tenant_id` | column | Owning tenant; RLS predicate and leading key of `idx_audit_log_tenant_created` |
| `actor_id` | column | Nullable `UUID` — the acting `staff_users.id`, or NULL when there is no authenticated actor |
| `action` | column | Plain TEXT, **no `CHECK`**; values come from [[backend/app/models/constants.py#AuditAction]] |
| `entity` | column | Nullable free-text subject tag (which booking, which staff member) |
| `details` | column | `JSONB NOT NULL DEFAULT '{}'::jsonb` — never NULL, so readers never branch on it |

## Behavior

This is a tenant-scoped table under FORCE RLS, which is what distinguishes it from [[backend/app/models/platform_audit_log.py]]: rows here are visible to the boutique they belong to, and the tenant-context binding on the connection is what scopes a read. Unlike the platform log, `app_user` keeps full CRUD on it ([[backend/migrations/versions/0003_auth.py]] grants `SELECT, INSERT, UPDATE, DELETE`), so append-only here is convention rather than a permission — the only writer in practice is `AuditLogRepository.record` in [[backend/app/db/repositories/audit_log.py]], which `session.add(...)` + `flush()`es and never updates. `actor_id` is nullable for a real reason: a failed login (`AuditAction.LOGIN_FAILED`) has no authenticated actor, and forcing a sentinel there would make "who tried" indistinguishable from "the system did it".

`action` is deliberately unconstrained TEXT. That is why the seven `BOOKING_*` values and five `STAFF_*` values could be added to `AuditAction` in feature branches with no migration, and it is also why nothing in the database stops a typo from becoming a permanent row — the enum is the only guard, so writers must pass a member, never a literal. The one index, `idx_audit_log_tenant_created` on `(tenant_id, created_at)`, is what makes a chronological per-tenant read cheap and is why `AuditAction` splits each state change into its own value: a filtered read stays one `WHERE action = …` instead of a JSONB predicate over `details`.

## Depends On

- [[backend/app/models/base.py]] — `Base`, `StandardColumns`
- [[SQLAlchemy]] — the PostgreSQL `JSONB` type
- [[PostgreSQL]]

## Depended On By

- [[backend/app/db/repositories/audit_log.py]] — `record()` (the only writer) and `list_actions()`
- [[backend/app/auth/service.py]] — login / login-failed / logout
- [[backend/app/auth/staff.py]] — the `STAFF_*` actions
- [[backend/app/booking/owner.py]] — the `BOOKING_*` actions

## Concepts

- [[Row Level Security]]
- [[Tenant Isolation]]

## Tests

- [[backend/tests/test_staff_management_db.py]] — asserts the staff actions land with the right actor and details
- [[backend/tests/test_booking_owner_db.py]] — the owner-console booking actions
- [[backend/tests/test_booking_owner_service.py]], [[backend/tests/test_staff_service.py]] — which action value each path writes

## Notes

`list_actions()` selects `action` ordered by `created_at` with no tenant predicate of its own — it relies entirely on RLS for scoping, unlike the house pattern of repeating `tenant_id ==` as defense in depth. Worth knowing before reusing it. DDL: [[backend/migrations/versions/0003_auth.py]].
