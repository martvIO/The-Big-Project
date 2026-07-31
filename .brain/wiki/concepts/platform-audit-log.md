---
tags: [backend, db, security, platform, postgres]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: active
---

# Platform Audit Log

**What it is.** The `platform_audit_log` table — a cross-tenant record of what a *platform
operator* did, created in [[backend/migrations/versions/0004_platform_audit.py]]. It is the
mirror image of [[Audit Trail]]: same idea, opposite permission posture.

## Two things this table does that no other table does

**1. Its tenant column is named `target_tenant_id`.** Not cosmetic. The forced-RLS metadata scan in
[[backend/tests/test_tenant_isolation.py]] asserts that *every* table with a literal `tenant_id`
column carries a `tenant_isolation` policy. This table must not carry one — it is intentionally
platform-wide — so the column is renamed to stay out of the scan's way. The migration's first
comment says exactly this.

**2. `app_user` may INSERT and nothing else.**

```sql
REVOKE ALL ON platform_audit_log FROM app_user;
GRANT INSERT ON platform_audit_log TO app_user;
```

The `REVOKE` is mandatory and comes first: [[backend/migrations/versions/0002_tenants_app_role.py]]
issues an `ALTER DEFAULT PRIVILEGES … GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user`,
which auto-grants full CRUD on *every table created afterwards*. A bare `GRANT INSERT` would add
nothing and remove nothing. Operators who need to read the history connect with a separate,
more-privileged role.

## The consequence that bites: no RETURNING

With `SELECT` revoked, `INSERT … RETURNING` fails with `permission denied` — and SQLAlchemy emits
a RETURNING clause automatically to fetch back server-generated columns. So
[[backend/app/platform/repository.py]] sets **both** `id=uuid4()` and `created_at=datetime.now(UTC)`
client-side, leaving the INSERT with nothing to fetch. Deleting either assignment because "the
database has a default for that" is how this breaks. The pattern is written up in
[[.memory/patterns/insert-only-table-no-returning.md]].

Note the contrast with [[Append Only Terms Versions]], which does the same `REVOKE` dance but keeps
`SELECT` granted — so *its* `INSERT … RETURNING` works fine.

## What gets written

`PlatformAuditAction` in [[backend/app/models/constants.py]]: `tenant_provisioned`,
`tenant_provision_failed`, `tenant_suspended`, `owner_password_reset`,
`booking_links_backfilled`. `action` is plain TEXT with no CHECK, so new values need no migration.
The sole writer is [[backend/app/platform/service.py]], driven from the operator CLI
[[backend/app/cli.py]]. Failures are audited too — `_fail_provision` writes a row and *returns*
rather than raising, so the audit commits.

## Related

- [[Audit Trail]] · [[Tenant Provisioning]] · [[Least Privilege Database Role]] · [[Row Level Security]]
