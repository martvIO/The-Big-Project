---
tags: [backend, tenancy, http, core]
sources: []
created: 2026-07-23
updated: 2026-07-23
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: n/a
---

# Tenant Resolution

**Purpose.** Turning an inbound HTTP request into a known tenant, before any database work happens.

This product resolves tenants by **subdomain** — each boutique gets its own. The middleware in [[backend/app/tenancy/middleware.py]] extracts the slug, [[backend/app/tenancy/resolver.py]] maps it to a tenant record, and [[backend/app/tenancy/slugs.py]] handles slug validation and reserved names.

The resolved tenant is then bound as [[Tenant Context]] for the request's database work.

Spec: [[.planning/specs/subdomain-routing.md]]. Slug parsing deliberately splits extraction from validation — see [[.memory/patterns/two-layer-fail-closed-parsing.md]].
