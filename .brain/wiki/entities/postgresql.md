---
tags: [backend, db, infra]
sources: []
created: 2026-07-23
updated: 2026-07-23
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: entity
applicability: n/a
---

# PostgreSQL

**Purpose.** The database. Chosen specifically for **row-level security**, which is the mechanism enforcing tenant isolation in this product — see [[Row Level Security]].

Features this codebase depends on: RLS policies with `FORCE`, `set_config`/`current_setting` for per-connection tenant context, `uuid-ossp` for UUID generation (enabled in [[backend/migrations/versions/0001_baseline_uuid_ossp.py]]), and `TIMESTAMPTZ` for all timestamps.
