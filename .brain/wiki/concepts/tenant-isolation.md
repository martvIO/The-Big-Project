---
tags: [backend, db, tenancy, security, testing]
sources: []
created: 2026-07-23
updated: 2026-07-23
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: n/a
---

# Tenant Isolation

**Purpose.** The guarantee that one boutique can never observe or modify another's data.

Enforced by [[Row Level Security]] at the database layer rather than by application query filters. Proven by [[backend/tests/test_tenant_isolation.py]], which includes a metadata scan asserting no `tenant_id` table escapes forced RLS.

This is the product's core security property. Any change under `backend/app/db/` should be read against it.
