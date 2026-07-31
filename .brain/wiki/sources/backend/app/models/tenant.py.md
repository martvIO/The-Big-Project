---
tags: [backend, models, python, tenancy, sqlalchemy, platform]
sources: [backend/app/models/tenant.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/models/tenant.py
blob: 4e7697206d590aab653f0c262f931ef2b7cfb5d6
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/models/tenant.py

**Role.** The tenant registry itself — slug, display name, lifecycle status and a JSONB settings blob — and the one tenant-facing table in the schema that deliberately carries **no** `tenant_id` column and **no** row-level security, because it is the table every tenant context is resolved *from*.

**Module.** [[backend/app/models/_index]] · **Layer.** models

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `Tenant` | class | ORM mapping for `tenants`; `StandardColumns` + `Base` |
| `Tenant.slug` | col | `TEXT NOT NULL` — the subdomain label; uniqueness is a *partial* unique index on `slug WHERE deleted_at IS NULL` |
| `Tenant.name` | col | `TEXT NOT NULL` — Hebrew display name of the boutique |
| `Tenant.status` | col | `TEXT NOT NULL DEFAULT 'active'`, default interpolated from `TenantStatus.ACTIVE` |
| `Tenant.settings` | col | `JSONB NOT NULL DEFAULT '{}'::jsonb` — the boutique's owner-editable settings document |

## Behavior

The class body is pure column declaration; every behavioral rule about this table lives either in the DDL of [[backend/migrations/versions/0002_tenants_app_role.py]] or in [[backend/app/db/repositories/tenants.py]]. Two of those rules are worth knowing before you open either. First, the slug uniqueness index is **partial** (`WHERE deleted_at IS NULL`), so soft-deleting a boutique releases its subdomain for re-provisioning instead of burning it forever — the reason a plain `UNIQUE` constraint was not used. Second, `settings` is never read-modify-written in Python: `TenantsRepository.merge_settings` issues a single `settings = settings || :patch::jsonb`, so two concurrent owner saves cannot clobber each other's keys.

`status` and `deleted_at` are two distinct ways to make a slug unresolvable and both are honored on the read path — `by_slug` filters active *and* not-soft-deleted, which is why a suspended boutique 404s rather than 403s at [[backend/app/tenancy/resolver.py]]. The `server_default` for `status` is an f-string over `TenantStatus.ACTIVE`, so the enum in [[backend/app/models/constants.py]] and the ORM default cannot drift; the DDL literal in 0002 is a third copy that must be changed by hand if the default ever moves. Unlike every other tenant-scoped table, 0002 creates no RLS policy here — a policy on `tenants` would make the registry invisible to the very lookup that establishes the tenant context, and it is also what lets [[backend/app/worker.py]] enumerate tenants before binding to each one in turn.

## Depends On

- [[backend/app/models/base.py]] — `Base`, `StandardColumns` (UUID PK, `created_at`/`updated_at`/`deleted_at`)
- [[backend/app/models/constants.py]] — `TenantStatus`, interpolated into the `status` server default
- [[SQLAlchemy]] — declarative mapping, `JSONB`, `Text`

## Depended On By

- [[backend/app/db/repositories/tenants.py]] — the only repository over this table
- [[backend/app/platform/service.py]] — provisioning and suspension return `Tenant` rows
- [[backend/app/tenancy/resolver.py]] — slug → tenant, indirectly through the repository
- [[backend/app/boutique/service.py]] — reads and merges `settings`
- [[backend/app/worker.py]] — enumerates active tenants per poll tick

## Concepts

- [[Tenant Resolution]]
- [[Tenant Context]]
- [[Row Level Security]] — this table is the documented exception

## Tests

- [[backend/tests/test_tenants_repository.py]] — insert, slug lookup, suspend, soft delete, settings merge
- [[backend/tests/test_tenancy_integration.py]] — resolver against a migrated database
- [[backend/tests/test_provisioning.py]] — tenant creation via the CLI path
- [[backend/tests/test_storefront_isolation.py]] and [[backend/tests/test_booking_comms_db.py]] — construct `Tenant` rows directly to build two-tenant fixtures

## Notes

The absence of an RLS policy here is load-bearing, not an oversight: [[backend/tests/test_tenant_isolation.py]]'s metadata scan only requires forced RLS on tables that *have* a `tenant_id` column, and this one does not. The same trick is used deliberately by [[backend/app/models/platform_audit_log.py]] (`target_tenant_id`).

Design context: [[.planning/specs/tenant-core-rls.md]], [[.planning/specs/tenant-provisioning-cli.md]], [[.planning/specs/owner-settings.md]].
