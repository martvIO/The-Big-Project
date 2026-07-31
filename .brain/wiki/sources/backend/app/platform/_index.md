---
tags: [backend, python]
sources: [backend/app/platform]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/platform
blob: 34a6c2835aef6d11b8f7b6ed132f4b2d66247063
commit: 13d107b8b16f1f2676f1cdb1c994f95822fe2ba0
kind: directory
applicability: active
---

# backend/app/platform/

**Purpose.** The operator-side surface — tenant provisioning and the INSERT-only platform audit log. CLI-only; it has no HTTP routes at all.

**Parent.** [[backend/app/_index]]

## Files

- [[backend/app/platform/__init__.py]] — Empty package marker for `app.platform` — the operator-side surface: tenant provisioning and the INSERT-only platform audit log.
- [[backend/app/platform/repository.py]] — Writes one row to the INSERT-only `platform_audit_log` on a caller-supplied session, generating `id` and `created_at` client-side so the INSERT emits no `RETURNING` — which the app role has no `SELECT` privilege to satisfy.
- [[backend/app/platform/service.py]] — The audited operator command layer for the tenant lifecycle: provision a tenant with its first owner atomically, suspend one, reset an owner's password, list tenants, and run F16's one-shot manage-link backfill — every state change (and…
