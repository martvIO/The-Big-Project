---
tags: [backend, models, python, platform, audit, security, sqlalchemy]
sources: [backend/app/models/platform_audit_log.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/models/platform_audit_log.py
blob: 902936cf3553032019e4883777c54562acedd749
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/models/platform_audit_log.py

**Role.** The operator trail for platform-wide acts — provisioning, suspension, owner password reset, the F16 link backfill — written by the app but **not readable** by it: the only INSERT-only table in the schema, and the only model that opts out of `StandardColumns`.

**Module.** [[backend/app/models/_index]] · **Layer.** platform

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `PlatformAuditLog` | class | ORM mapping for `platform_audit_log`; extends `Base` **only** — no `StandardColumns` |
| `id` | col | `UUID` PK, `uuid_generate_v4()` server default, but always supplied client-side (see Behavior) |
| `operator` | col | `TEXT NOT NULL` — who acted, a free-form operator identity, not a `staff_users` id |
| `action` | col | `TEXT NOT NULL`, no `CHECK` — values come from `PlatformAuditAction` in [[backend/app/models/constants.py]] |
| `target_tenant_id` | col | `UUID NULL` — **deliberately not named `tenant_id`** |
| `details` | col | `JSONB NOT NULL DEFAULT '{}'::jsonb` |
| `created_at` | col | `TIMESTAMPTZ NOT NULL DEFAULT now()`, also always supplied client-side |

## Behavior

Three deviations from every other model in this package, each with a reason that will bite anyone who "fixes" it. **First, the column is `target_tenant_id`.** [[backend/tests/test_tenant_isolation.py]]'s metadata scan asserts that every table with a `tenant_id` column is under forced RLS; this table must be readable *across* tenants by a platform operator, so it is named out of that scan rather than exempted from it. **Second, it has no `updated_at` or `deleted_at`** and no `update_updated_at` trigger — rows are append-only evidence, so `StandardColumns` would have contributed three columns that could only ever be wrong.

**Third, and the one that produces a confusing runtime error if forgotten:** [[backend/migrations/versions/0004_platform_audit.py]] does `REVOKE ALL … FROM app_user` before `GRANT INSERT`, because 0002's `ALTER DEFAULT PRIVILEGES` had already auto-granted full CRUD on every table that migration role creates — a bare `GRANT INSERT` would have left `SELECT` in place. With `SELECT` revoked, any `INSERT … RETURNING` fails with *permission denied*, and SQLAlchemy emits `RETURNING` precisely to fetch back server-generated defaults. That is why [[backend/app/platform/repository.py]] sets both `id` (`uuid4()`) and `created_at` (`datetime.now(UTC)`) client-side: with no server-generated column left to fetch, the INSERT returns nothing and succeeds. The server defaults stay in the DDL as a safety net for an out-of-band writer, not for this path.

`action` is plain `TEXT` with **no** `CHECK`, unlike `message_log.kind` or `staff_users.role`. That is what lets `PlatformAuditAction` grow — F16's `booking_links_backfilled` was added to the enum with no migration at all.

## Depends On

- [[backend/app/models/base.py]] — `Base` only
- [[SQLAlchemy]] — declarative mapping, `JSONB`

## Depended On By

- [[backend/app/platform/repository.py]] — `PlatformAuditLogRepository.record`, the sole writer
- [[backend/app/platform/service.py]] — provisioning, suspension and owner password reset call `record`
- [[backend/app/models/constants.py]] — `PlatformAuditAction` supplies the `action` values (no import; a value contract, not a code dependency)

## Concepts

- [[Least Privilege Database Role]]
- [[Row Level Security]] — the documented non-participant

## Tests

- [[backend/tests/test_provisioning.py]] — the only test file that touches this table; covers the recorded operator actions on a migrated database

## Notes

**Do not confuse this table with the tenant-scoped `audit_log`** ([[backend/app/models/audit_log.py]]). They answer different questions and have opposite permission postures: `audit_log` is per-tenant, under FORCE RLS, holds full CRUD grants and is read back by the boutique's own console; `platform_audit_log` is cross-tenant, has no RLS, and the application role can write to it but never read it. Their action vocabularies are also separate enums (`AuditAction` vs `PlatformAuditAction`).

The INSERT-without-RETURNING pattern is written up in [[.memory/patterns/insert-only-table-no-returning.md]].

Design context: [[.planning/specs/tenant-provisioning-cli.md]].
