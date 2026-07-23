---
tags: [backend, db, migrations]
sources: []
created: 2026-07-23
updated: 2026-07-23
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: n/a
---

# Database Migrations

**Purpose.** Every schema change is a versioned, ordered [[Alembic]] revision. The chain is linear — each revision's `down_revision` points at its predecessor.

Current chain:
1. [[backend/migrations/versions/0001_baseline_uuid_ossp.py]] — baseline, enables `uuid-ossp`
2. [[backend/migrations/versions/0002_tenants_app_role.py]] — tenants table and the application role
3. [[backend/migrations/versions/0003_auth.py]] — auth tables, and the [[Row Level Security]] policies on them
4. [[backend/migrations/versions/0004_platform_audit.py]] — platform-wide audit log

Environment script: [[backend/migrations/env.py]]. Verified by [[backend/tests/test_migrations.py]].
