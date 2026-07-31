---
tags: [backend, platform, audit, python, sqlalchemy, database]
sources: [backend/app/platform/repository.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/platform/repository.py
blob: a814ac810b149b54760860e82f43a2a1fb77dbb8
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# backend/app/platform/repository.py

**Role.** Writes one row to the INSERT-only `platform_audit_log` on a caller-supplied session, generating `id` and `created_at` client-side so the INSERT emits no `RETURNING` — which the app role has no `SELECT` privilege to satisfy.

**Module.** [[backend/app/platform/_index]] · **Layer.** platform

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `PlatformAuditLogRepository` | class | Stateless; one method |
| `PlatformAuditLogRepository.record` | method | `session.add(PlatformAuditLog(...))` + `flush()`; takes `operator`, `action`, optional `target_tenant_id` and `details` |

## Behavior

The single non-obvious line in this file is why `id=uuid4()` and `created_at=datetime.now(UTC)` are set in Python when the table already defaults both server-side. Migration `0004` does `REVOKE ALL ON platform_audit_log FROM app_user` then `GRANT INSERT` — a REVOKE that is itself mandatory, because migration `0002`'s `ALTER DEFAULT PRIVILEGES` auto-grants full CRUD on every later table to `app_user`, so a bare `GRANT INSERT` would leave `SELECT` in place. With `SELECT` gone, any `INSERT … RETURNING` fails with `permission denied`, and SQLAlchemy emits exactly that whenever a mapped column carries a server default it needs to populate. Filling both columns client-side removes the server-generated columns, so the ORM issues a plain INSERT and the write succeeds under an INSERT-only grant.

`record` takes the session rather than opening one, which is what lets [[backend/app/platform/service.py]] commit an audit row *in the same transaction* as the state change it describes — provisioning is atomic across tenant, owner and audit. `flush()` (not `commit()`) keeps that ownership with the caller. `details` defaults to `{}` rather than `None` because the column is `NOT NULL`. The table is deliberately platform-scoped and carries no RLS: its column is `target_tenant_id`, not `tenant_id`, precisely so the forced-RLS metadata scan in [[backend/tests/test_tenant_isolation.py]] does not demand a policy on a table meant to be read across tenants by operators — who connect with a separate, more-privileged role than the application's.

## Depends On

- [[backend/app/models/platform_audit_log.py]] — the ORM model
- [[SQLAlchemy]] — `AsyncSession`

## Depended On By

- [[backend/app/platform/service.py]] — the only caller; every command records through it

## Concepts

- [[Platform Audit Log]]
- [[Least Privilege Database Role]]

## Tests

- [[backend/tests/test_provisioning.py]] — `test_each_state_change_writes_platform_audit` (read back through a privileged reader), `test_app_user_cannot_read_platform_audit` (the grant itself)

## Notes

`action` values come from `PlatformAuditAction` in [[backend/app/models/constants.py]]. The column is plain `TEXT` with no `CHECK`, so adding a new action needs no migration — which is how `booking_links_backfilled` was added for F16. Migration: [[backend/migrations/versions/0004_platform_audit.py]].
