---
tags: [backend, db, python, tenancy, security]
sources: [backend/app/db/rls.py]
created: 2026-07-23
updated: 2026-07-23
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/db/rls.py
blob: 2b10123ba1224dc55fc29f6701eaa096bf5068da
commit: d9d860b47f2c78acb9ce7304f18c1e18cc370851
kind: code
applicability: active
---

# backend/app/db/rls.py

**Role.** Single source of truth for the name of the Postgres session setting that carries the tenant context, and for the exact DDL that puts a tenant-scoped table under forced row-level security.

**Module.** [[backend/app/db/_index]] · **Layer.** db

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `TENANT_ID_SETTING` | const | `"app.tenant_id"` — the `set_config` / `current_setting` key every tenant-bound connection writes and every RLS policy reads |
| `enable_tenant_rls` | fn | Returns the three DDL statements (`ENABLE`, `FORCE`, `CREATE POLICY tenant_isolation`) that isolate one table by `tenant_id` |

## Behavior

`enable_tenant_rls(table_name)` returns a list of SQL strings rather than executing anything — the caller (a migration, or the isolation suite's probe fixture) runs them. The policy predicate is `tenant_id = current_setting('app.tenant_id', true)::uuid`, applied as both `USING` (reads, updates, deletes) and `WITH CHECK` (inserts and the post-image of updates), so a row can neither be read nor written outside the bound tenant, and a row cannot be re-parented to another tenant. The `missing_ok := true` second argument is the fail-closed hinge: with no tenant context set, `current_setting` yields `NULL`, the predicate is `NULL` rather than an error, and the connection sees **zero rows** instead of erroring or seeing everything. `FORCE ROW LEVEL SECURITY` is emitted alongside `ENABLE` because plain `ENABLE` exempts the table owner — that exemption is why the application connects as a non-owner role (see [[backend/app/db/session.py#verify_database_role]]). `table_name` is interpolated into the DDL, which is safe only because every caller passes a developer-authored literal; it must never receive user input.

## Depends On

Nothing — pure string construction, no imports.

## Depended On By

- [[backend/app/db/tenant.py]] — imports `TENANT_ID_SETTING` to bind the context via `set_config`
- [[backend/migrations/versions/0003_auth.py]] — applies `enable_tenant_rls` to `staff_users`, `sessions`, and `audit_log`
- [[backend/tests/test_tenant_isolation.py]] — secures the `rls_probe` table with the same helper the real migrations use

## Concepts

- [[Row Level Security]]
- [[Tenant Context]]
- [[Fail Closed Defaults]]

## Tests

- [[backend/tests/test_tenant_isolation.py]] — the whole permanent isolation suite is built on this helper: `test_force_rls_is_enabled_on_probe`, `test_no_context_means_zero_rows`, `test_write_for_other_tenant_is_rejected`, `test_reparenting_own_row_to_other_tenant_is_rejected`, `test_garbage_context_fails_loudly_not_open`, and `test_every_tenant_id_table_has_forced_rls` (a metadata scan asserting no table with a `tenant_id` column escapes forced RLS)

## Notes

The metadata-scan test is why [[backend/app/models/platform_audit_log.py]] names its column `target_tenant_id` and not `tenant_id` — a platform-wide table with a `tenant_id` column would be required to carry a policy it must not have.

Design context: [[.planning/specs/tenant-core-rls.md]] and [[.planning/plans/tenant-core-rls.md]].
