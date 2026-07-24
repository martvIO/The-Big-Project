---
tags: [backend, db, tenancy, security, core]
sources: [backend/app/db/rls.py, backend/app/db/tenant.py, backend/app/db/session.py, backend/migrations/versions/0003_auth.py, backend/tests/test_tenant_isolation.py]
created: 2026-07-23
updated: 2026-07-23
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: n/a
---

# Row Level Security

**Purpose.** The mechanism that makes this product multi-tenant. Isolation is enforced by
[[PostgreSQL]] itself, not by application query filters, so a forgotten `WHERE tenant_id = …`
cannot leak another boutique's data.

This is the single most important design decision in the codebase. Read this before touching
anything under `backend/app/db/`.

## How it works

1. **Every tenant-scoped table carries a `tenant_id` column** and an RLS policy named
   `tenant_isolation`, applied as both `USING` (reads, updates, deletes) and `WITH CHECK`
   (inserts, and the post-image of updates). The `WITH CHECK` half is what prevents a row from
   being re-parented to another tenant.

2. **The policy predicate reads a connection-local setting:**
   `tenant_id = current_setting('app.tenant_id', true)::uuid`.
   The setting name is defined once, in [[backend/app/db/rls.py#TENANT_ID_SETTING]].

3. **`FORCE ROW LEVEL SECURITY`, not just `ENABLE`.** Plain `ENABLE` exempts the table owner.
   `FORCE` removes that exemption, which is why the application also connects as a
   non-owner role — see [[Least Privilege Database Role]].

4. **The tenant context is bound per connection** by [[backend/app/db/tenant.py]] via
   `set_config`, and the DDL that establishes a table's policy comes from
   [[backend/app/db/rls.py#enable_tenant_rls]].

## Fail-closed, not fail-open

The `missing_ok := true` second argument to `current_setting` is the hinge. With no tenant
context bound, `current_setting` returns `NULL` rather than raising; the predicate evaluates to
`NULL`; and the connection sees **zero rows**.

That is the correct failure direction: a bug that forgets to bind the tenant produces an empty
result set, not a full-table read. See [[Fail Closed Defaults]].

## Where it is established

- [[backend/app/db/rls.py]] — the setting name and the policy DDL, in one place
- [[backend/app/db/tenant.py]] — binds the tenant onto a connection
- [[backend/app/db/session.py]] — session construction and role verification
- [[backend/migrations/versions/0003_auth.py]] — applies the policy to `staff_users`,
  `sessions`, and `audit_log`

## How it is proven

[[backend/tests/test_tenant_isolation.py]] is the permanent isolation suite. Beyond the obvious
cases it includes a **metadata scan** asserting that *every* table with a `tenant_id` column has
forced RLS — so a new table cannot silently escape the policy.

That scan is also why [[backend/app/models/platform_audit_log.py]] names its column
`target_tenant_id`: a platform-wide table with a literal `tenant_id` column would be required by
the scan to carry a policy it must not have.

## Gotchas

- A DB write followed by a `raise` inside the same tenant session is rolled back together.
  Commit failure-path audit rows **before** raising — see
  [[.memory/patterns/commit-before-raise-in-tenant-session.md]].
- Creating an RLS-free parent and an RLS-forced child atomically needs client-side UUIDs —
  see [[.memory/patterns/atomic-parent-child-across-rls.md]].
- Append-only tables that revoke `SELECT` break `INSERT … RETURNING`, because the ORM's
  RETURNING clause needs read permission. Generate the PK and timestamps client-side — see
  [[.memory/patterns/insert-only-table-no-returning.md]].

## Related

- [[Tenant Context]] · [[Tenant Isolation]] · [[Tenant Resolution]] · [[Fail Closed Defaults]]
- [[.planning/specs/tenant-core-rls.md]] — the originating spec
