---
tags: [backend, db, python, tenancy, security, rls]
sources: [backend/app/db/tenant.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/db/tenant.py
blob: 80c405abe82d127831ec034ebf2ff2e72caa5b7b
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# backend/app/db/tenant.py

**Role.** The two — and only two — ways to reach a tenant-scoped table: async context managers that open a transaction, bind `app.tenant_id` into it with `set_config(..., is_local := true)`, and yield either an ORM `AsyncSession` (for repositories) or a raw `AsyncConnection` (for DDL and migrations).

**Module.** [[backend/app/db/_index]] · **Layer.** db

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `tenant_session` | async ctx mgr | `async_sessionmaker` → an `AsyncSession` inside `session.begin()` with the tenant context bound. What every service uses. |
| `tenant_connection` | async ctx mgr | `AsyncEngine` → an `AsyncConnection` inside `engine.begin()` with the same binding. **Test-only today** — see Notes. |

## Behavior

Both wrap the work in a transaction *first*, then execute `SELECT set_config(:name, :value, true)` before yielding. The `true` third argument is the whole design: `is_local := true` makes the setting **transaction-scoped**, so it is discarded at COMMIT or ROLLBACK and a pooled connection handed to the next request can never carry the previous tenant's context — the single failure mode that would turn per-tenant RLS into a coin flip. The setting name is `TENANT_ID_SETTING` from [[backend/app/db/rls.py]], so the writer and the policy predicate can never drift apart. The value is **parameterized**, never interpolated, and typed as `UUID` at the Python boundary before `str()`, so a garbage tenant id cannot reach SQL as text; the policy's `::uuid` cast means a garbage value that somehow did arrive would raise rather than silently widen the view (`test_garbage_context_fails_loudly_not_open`).

Because the context is transaction-local, everything a caller does with the yielded handle must happen *inside* the `async with` — a repository call made after the block runs with no tenant context, and RLS then returns zero rows rather than erroring (fail-closed, by way of `current_setting(..., missing_ok := true)`). Exit is the context manager's own: an exception propagates, the transaction rolls back, and the binding disappears with it. Neither function catches anything.

Services layer an explicit `tenant_id` predicate on top of this in every repository query. That is redundant with the FORCE RLS policy on purpose — defense in depth, so a table that somehow escaped the policy still filters, and so a reader of a repository can see the scoping without inferring it.

## Depends On

- [[backend/app/db/rls.py]] — `TENANT_ID_SETTING`, the shared key
- [[SQLAlchemy]] — `async_sessionmaker`, `AsyncSession`, `AsyncEngine`, `AsyncConnection`, `text`

## Depended On By

- [[backend/app/storefront/service.py]]
- [[backend/app/catalog/service.py]]
- [[backend/app/boutique/service.py]]
- [[backend/app/booking/service.py]]
- [[backend/app/booking/manage.py]]
- [[backend/app/booking/owner.py]]
- [[backend/app/booking/comms.py]]
- [[backend/app/booking/backfill.py]]
- [[backend/app/notifications/service.py]]
- [[backend/app/auth/service.py]]
- [[backend/app/auth/staff.py]]
- [[backend/app/platform/service.py]]

## Concepts

- [[Row Level Security]]
- [[Tenant Context]]
- [[Fail Closed Defaults]]

## Tests

- [[backend/tests/test_tenant_isolation.py]] — `test_context_scopes_reads_to_own_tenant`, `test_no_context_means_zero_rows`, `test_garbage_context_fails_loudly_not_open`
- [[backend/tests/test_storefront_isolation.py]] · [[backend/tests/test_catalog_isolation.py]] · [[backend/tests/test_booking_isolation.py]] · [[backend/tests/test_notifications_isolation.py]] — each drives its service's repositories as tenant B against tenant A's rows
- [[backend/tests/test_migrations.py]] — drives migrated schemas through `tenant_session`
- [[backend/tests/test_catalog_integration.py]] — the only other `tenant_connection` caller

## Notes

**Docstring drift worth knowing about.** `tenant_connection`'s docstring says "The Feature 4 middleware is the only production caller." It has **no** production caller today: the only importers are [[backend/tests/test_tenant_isolation.py]] and [[backend/tests/test_catalog_integration.py]]. [[backend/app/tenancy/middleware.py]] and [[backend/app/tenancy/resolver.py]] do not import this module at all — the resolver reads the `tenants` table, which is not tenant-scoped. Every production path goes through `tenant_session`. The claim about *how* the binding works is still accurate; only the claim about who calls it is stale.

The platform-wide surface deliberately does **not** go through here: [[backend/app/models/platform_audit_log.py]] names its column `target_tenant_id` precisely so it is not a tenant-scoped table.

Design context: [[.planning/specs/tenant-core-rls.md]].
