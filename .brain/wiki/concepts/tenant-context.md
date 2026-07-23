---
tags: [backend, db, tenancy, core]
sources: []
created: 2026-07-23
updated: 2026-07-23
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: n/a
---

# Tenant Context

**Purpose.** The per-connection binding that tells [[PostgreSQL]] which boutique the current request belongs to.

Carried in the connection-local setting `app.tenant_id`, whose name is defined once in [[backend/app/db/rls.py#TENANT_ID_SETTING]] and bound via `set_config` in [[backend/app/db/tenant.py]]. Every [[Row Level Security]] policy reads it.

Unbound context means **zero rows**, never all rows — see [[Fail Closed Defaults]].
