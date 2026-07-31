---
tags: [backend, python]
sources: [backend/app/tenancy]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/tenancy
blob: 384474362099aaf0e267d161728e30a27ab02304
commit: 13d107b8b16f1f2676f1cdb1c994f95822fe2ba0
kind: directory
applicability: active
---

# backend/app/tenancy/

**Purpose.** Subdomain-to-tenant resolution and the middleware that runs it — the thing every RLS session context depends on.

**Parent.** [[backend/app/_index]]

## Files

- [[backend/app/tenancy/__init__.py]] — Empty package marker for `app.tenancy` — subdomain→tenant resolution, the request-scoped `TenantContext`, and the slug rules shared with provisioning.
- [[backend/app/tenancy/middleware.py]] — Turns the request hostname into a bound `TenantContext` on `request.state` before any handler runs, answers one indistinguishable 404 for every resolution failure, and exposes the `get_current_tenant` dependency every tenant-scoped route…
- [[backend/app/tenancy/resolver.py]] — The production `TenantResolver`: one indexed `tenants.slug` lookup per request, translating an active tenant row into the immutable `TenantContext` the middleware binds.
- [[backend/app/tenancy/slugs.py]] — Pulls the leftmost DNS label out of a `Host` header against the configured base domain, and decides whether that label is a legal, non-reserved boutique slug — the only place tenant identity is derived from anything the client sends.
