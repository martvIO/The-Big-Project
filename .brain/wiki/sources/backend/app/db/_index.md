---
tags: [backend, python]
sources: [backend/app/db]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/db
blob: 272a81ade1b54882710e2fe577e443e3545822e0
commit: 13d107b8b16f1f2676f1cdb1c994f95822fe2ba0
kind: directory
applicability: active
---

# backend/app/db/

**Purpose.** Engine, session factory, the tenant-binding wrapper that sets the RLS context, and the repository layer beneath.

**Parent.** [[backend/app/_index]]

## Files

- [[backend/app/db/__init__.py]] — Empty file marking `app.db` as a package — the engine and session factory ([[backend/app/db/session.py]]), the tenant-bound context managers ([[backend/app/db/tenant.py]]), the RLS DDL vocabulary ([[backend/app/db/rls.py]]), and…
- [[backend/app/db/rls.py]] — Single source of truth for the name of the Postgres session setting that carries the tenant context, and for the exact DDL that puts a tenant-scoped table under forced row-level security.
- [[backend/app/db/session.py]] — Owns the process-wide async engine and session factory, and enforces the fail-fast guard that refuses to run against a database role capable of bypassing row-level security.
- [[backend/app/db/tenant.py]] — The two — and only two — ways to reach a tenant-scoped table: async context managers that open a transaction, bind `app.tenant_id` into it with `set_config(..., is_local := true)`, and yield either an ORM `AsyncSession` (for repositories)…

## Subdirectories

- [[backend/app/db/repositories/_index]] — Every SQL statement in the product. One class per table, each tenant-scoped by RLS with an explicit `tenant_id` predicate as redundant defence-in-depth.
