---
tags: [backend, db, repository, tenancy, platform, jsonb, python, sqlalchemy]
sources: [backend/app/db/repositories/tenants.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/db/repositories/tenants.py
blob: 2b5f7ff6e4ef9c170567fd5fc7e88bbe8e0bf688
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/db/repositories/tenants.py

**Role.** The one **platform-scoped** repository: creates tenants, resolves a slug to an active tenant on every request, suspends and soft-deletes, atomically merges JSONB settings patches, and enumerates active tenants for the background poller.

**Module.** [[backend/app/db/repositories/_index]] · **Layer.** db

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `TenantsRepository` | class | Holds its own `async_sessionmaker` — unlike every sibling, callers pass no session |
| `insert` | method | Creates a `Tenant` from `(slug, name)` in its own committed transaction |
| `by_id` | method | Live tenant by id, any status |
| `by_slug` | method | Live **and active** tenant by slug — the host-resolution read |
| `suspend` | method | Sets `status = suspended`; `True` iff a live row was hit |
| `soft_delete` | method | Stamps `deleted_at`; `True` iff a live row was hit |
| `merge_settings` | method | One atomic `settings = settings \|\| :patch::jsonb`; returns the merged document |
| `list_active` | method | Every live active tenant, `created_at ASC` |

## Behavior

`tenants` has no `tenant_id` column and therefore no RLS policy — deliberately, because it is the table that *defines* the tenants everything else is scoped to, and it is what the background poller enumerates to stay inside the tenancy posture. That inversion drives the unusual shape: the repository owns a session factory and opens its own transaction per method, since its callers (host resolution middleware, provisioning, the worker) run before or outside a tenant-bound session. It **requires** a factory built with `expire_on_commit=False`, as `get_session_factory()` provides, because it returns ORM entities after commit — with expiry on, every returned entity would raise `DetachedInstanceError` on first attribute access. `by_slug` excludes both soft-deleted and non-`ACTIVE` tenants, so suspension and deletion are the same unresolvable-host 404. `merge_settings` is the one method with real subtlety: it builds a patch containing only the provided top-level keys and applies it as a single SQL `||` JSONB merge rather than a Python read-modify-write, so a concurrent writer of a *sibling* top-level key cannot be clobbered; it returns `None` when the tenant is missing or soft-deleted. `updated_at` is never assigned here — the DB trigger owns it.

## Depends On

- [[backend/app/models/tenant.py]] — the `Tenant` ORM entity
- [[backend/app/models/constants.py]] — `TenantStatus`
- [[SQLAlchemy]] — `select` / `update` / `cast`, the PostgreSQL `JSONB` type, `async_sessionmaker`
- [[PostgreSQL]] — the `||` JSONB concatenation operator

## Depended On By

- [[backend/app/tenancy/resolver.py]] — slug → tenant on the request path
- [[backend/app/platform/service.py]] — tenant provisioning, suspend, delete
- [[backend/app/boutique/service.py]] — reads and merges the boutique's `settings` document
- [[backend/app/worker.py]] — enumerates active tenants each poll tick
- [[backend/app/booking/backfill.py]] — walks tenants to backfill scheduled messages

## Concepts

- [[Tenant Resolution]]
- [[Tenant Context]]
- [[Row Level Security]]

## Tests

- [[backend/tests/test_tenants_repository.py]]
- [[backend/tests/test_tenancy_integration.py]]
- [[backend/tests/test_boutique_service.py]]
- [[backend/tests/test_boutique_integration.py]]
- [[backend/tests/test_storefront_isolation.py]]
- [[backend/tests/test_staff_management_db.py]]

## Notes

This is the file to read before assuming "every repository takes a session" — it is the documented exception, and the reason is architectural rather than stylistic. `merge_settings` only ever writes the `profile` and `toggles` top-level keys; the atomic-merge shape exists so that future sibling keys can be added without revisiting concurrency.
