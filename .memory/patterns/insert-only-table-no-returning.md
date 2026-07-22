# Pattern: INSERT-only tables need client-side PK *and* timestamps

For an append-only table the app writes but must never read (platform/operator
audit logs), grant the app role `INSERT` only — but two things bite:

1. **`ALTER DEFAULT PRIVILEGES` leaks CRUD.** An early migration's
   `ALTER DEFAULT PRIVILEGES … GRANT SELECT,INSERT,UPDATE,DELETE … TO app_user`
   silently grants full CRUD on *every* later table created by that migration
   role. A plain `GRANT INSERT` does NOT make it INSERT-only — you must
   `REVOKE ALL … FROM app_user` first, then `GRANT INSERT`.

2. **`INSERT … RETURNING` needs SELECT.** SQLAlchemy emits `INSERT … RETURNING`
   to populate server-generated columns (the PK, and `created_at`/etc. under the
   2.0 default `eager_defaults="auto"`). RETURNING reads columns → needs SELECT →
   fails under an INSERT-only role with `permission denied`. Fix: generate EVERY
   otherwise-server-generated value client-side — `id=uuid4()` AND
   `created_at=datetime.now(UTC)` — so the INSERT has nothing to return.

**Origin (2026-07-22, Feature 6):** `platform_audit_log`. Both bites only surface
against a real non-owner Postgres role in CI (a local superuser/dev run bypasses
grants entirely), which is why the isolation test suite runs as `boutique_app`.
