---
tags: [backend, tenancy, python, package]
sources: [backend/app/tenancy/__init__.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/tenancy/__init__.py
blob: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# backend/app/tenancy/__init__.py

**Role.** Empty package marker for `app.tenancy` — subdomain→tenant resolution, the request-scoped `TenantContext`, and the slug rules shared with provisioning.

**Module.** [[backend/app/tenancy/_index]] · **Layer.** tenancy

## Public Surface

Nothing. The file is zero bytes; it re-exports nothing.

## Behavior

Consumers import the concrete module: [[backend/app/tenancy/middleware.py]] for `TenantContext` / `get_current_tenant`, [[backend/app/tenancy/resolver.py]] for the DB-backed resolver, [[backend/app/tenancy/slugs.py]] for `is_valid_slug` and `RESERVED_SLUGS`. Keeping this empty matters for one real case: [[backend/app/platform/service.py]] imports only `app.tenancy.slugs`, a module with no SQLAlchemy or FastAPI dependency, and a re-exporting `__init__` would pull the middleware in behind it.

## Depends On

Nothing.

## Depended On By

Implicitly every importer of `app.tenancy.*`.

## Concepts

- [[Tenant Resolution]]

## Tests

None — nothing to test.
