---
tags: [backend, tenancy, python, database, sqlalchemy]
sources: [backend/app/tenancy/resolver.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/tenancy/resolver.py
blob: e938465e5e9f4c0154a20f6ade1d08ad847d07f6
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# backend/app/tenancy/resolver.py

**Role.** The production `TenantResolver`: one indexed `tenants.slug` lookup per request, translating an active tenant row into the immutable `TenantContext` the middleware binds.

**Module.** [[backend/app/tenancy/_index]] · **Layer.** tenancy

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `RepositoryTenantResolver` | class | Callable `async (slug) -> TenantContext | None`, satisfying the `TenantResolver` Protocol |

## Behavior

The whole file is a thin adapter, and that is the point: the resolver Protocol exists so tests can inject a recording stub, and the real implementation must add nothing worth mocking. `__call__` delegates to `TenantsRepository.by_slug`, which filters on `deleted_at IS NULL` **and** `status = 'active'` — so suspension and soft-deletion both make a slug unresolvable through the same `None` return, and [[backend/app/tenancy/middleware.py]] cannot tell them apart from an unknown slug. Copying only `id`, `slug`, `name` and `settings` into a frozen `TenantContext` rather than passing the ORM entity through keeps a detached, mutable SQLAlchemy object out of `request.state` and out of every handler.

Caching is deliberately absent — a per-request lookup on the unique index `idx_tenants_slug_unique` is cheap, and a cache would need invalidation on suspend and on settings writes. Deferred to E5; premature at pilot traffic. The `tenants` table is platform-scoped (no `tenant_id` column, no RLS), which is what lets this query run before any tenant context is bound — a chicken-and-egg the rest of the codebase never faces.

## Depends On

- [[backend/app/db/repositories/tenants.py]] — `TenantsRepository.by_slug`
- [[backend/app/tenancy/middleware.py]] — `TenantContext`
- [[SQLAlchemy]] — `async_sessionmaker`

## Depended On By

- [[backend/app/main.py]] — `create_app` builds one when no resolver is injected
- [[backend/tests/test_tenancy_integration.py]]
- [[backend/tests/test_staff_management_db.py]]
- [[backend/tests/test_staff_role_gating_integration.py]]

## Concepts

- [[Tenant Resolution]]
- [[Tenant Context]]

## Tests

- [[backend/tests/test_tenancy_integration.py]] — `test_active_tenant_resolves_end_to_end`, `test_suspended_and_deleted_tenants_are_404`, `test_reserved_slug_is_404_even_with_a_row`

## Notes

`TenantsRepository` requires a session factory built with `expire_on_commit=False` (which `get_session_factory()` in [[backend/app/db/session.py]] provides) — it returns ORM entities after their transaction commits, which would otherwise raise `DetachedInstanceError`.
