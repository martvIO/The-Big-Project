---
tags: [backend, tenancy, python, middleware, fastapi, security, multi-tenant]
sources: [backend/app/tenancy/middleware.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/tenancy/middleware.py
blob: 0089d0b283fc7d7e2a22517e6794b005febc19ad
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# backend/app/tenancy/middleware.py

**Role.** Turns the request hostname into a bound `TenantContext` on `request.state` before any handler runs, answers one indistinguishable 404 for every resolution failure, and exposes the `get_current_tenant` dependency every tenant-scoped route depends on.

**Module.** [[backend/app/tenancy/_index]] · **Layer.** tenancy

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `TenantResolutionMiddleware` | class | `BaseHTTPMiddleware` that resolves the slug and sets `request.state.tenant` |
| `TenantContext` | frozen dataclass | `id`, `slug`, `name`, `settings` — the request-scoped tenant identity |
| `TenantResolver` | Protocol | `async (slug) -> TenantContext | None`; lets tests inject a recording resolver |
| `get_current_tenant` | fn | FastAPI dependency; raises `TenantNotResolvedError` if nothing was bound |
| `TenantNotResolvedError` | exception | A tenant-scoped route ran on an exempt path — a misconfiguration, mapped to the same 404 |
| `EXEMPT_PATHS` | frozenset | `/health`, `/openapi.json`, `/docs`, `/docs/oauth2-redirect`, `/redoc` |
| `TENANT_NOT_FOUND_BODY` | const | The single response body for unknown, suspended, deleted, reserved and apex |

## Behavior

`dispatch` short-circuits on an exact `EXEMPT_PATHS` match, then calls `extract_slug` and `is_valid_slug` from [[backend/app/tenancy/slugs.py]]; either failing returns the generic 404 **without calling the resolver at all**, so a reserved or malformed host costs no database round trip. A resolver returning `None` produces the identical body. That sameness is the anti-enumeration invariant: unknown slug, suspended tenant, soft-deleted tenant, reserved slug and apex host must be indistinguishable, otherwise the 404 becomes an oracle for which boutiques exist. Tenant identity comes from the `Host` header and nothing else — client-controlled in the strict sense, but yielding no more than DNS already reveals, and never from a body field, a query parameter or a header the client can pick freely.

`EXEMPT_PATHS` carries the sharpest constraint in the file: **storefront paths must never be added to it.** The set skips tenant resolution entirely, and a storefront route reaching a handler with no `request.state.tenant` raises `TenantNotResolvedError`. Public is not the same as host-agnostic. The set is exact-match rather than prefix precisely so this cannot happen by accident, and `test_storefront_paths_are_not_exempt` asserts it anyway. The four docs paths remain listed but are only *reachable* in dev — [[backend/app/main.py]] passes `docs_url`/`redoc_url`/`openapi_url=None` outside dev so FastAPI never registers the routes. `/docs/oauth2-redirect` is auto-registered by FastAPI whenever docs are on, so it has to stay in sync with this set or Swagger's Authorize flow breaks silently.

`TenantContext.name` is required rather than defaulted on purpose: a `""` default would let a future resolver that forgets to wire it ship an empty `<h1>` to a public storefront instead of failing loudly at construction. `TenantNotResolvedError` needs an explicit handler in [[backend/app/main.py]] — there is no error registry — and that handler returns `TENANT_NOT_FOUND_BODY`, so even the misconfiguration path preserves the indistinguishability invariant. Middleware ordering matters and is set in `create_app`: this middleware is added first, so `CsrfOriginMiddleware` (added after) runs *before* it and rejects a cross-origin forgery without touching the database, while `SecurityHeadersMiddleware` is added last (outermost) so its headers land even on the 404 this middleware returns from its own `dispatch` without ever reaching a handler.

## Depends On

- [[backend/app/tenancy/slugs.py]] — `extract_slug`, `is_valid_slug`
- [[FastAPI]] — `Request`
- [[Starlette]] — `BaseHTTPMiddleware`, `JSONResponse`

## Depended On By

- [[backend/app/main.py]] — installs the middleware, registers the `TenantNotResolvedError` handler
- [[backend/app/tenancy/resolver.py]] — constructs `TenantContext`
- [[backend/app/auth/dependencies.py]] · [[backend/app/auth/router.py]] · [[backend/app/auth/staff_router.py]]
- [[backend/app/catalog/router.py]] · [[backend/app/storefront/router.py]] · [[backend/app/boutique/router.py]]
- [[backend/app/booking/router.py]] · [[backend/app/booking/owner_router.py]] · [[backend/app/notifications/router.py]]

## Concepts

- [[Tenant Resolution]]
- [[Tenant Context]]
- [[Tenant Isolation]]
- [[Fail Closed Defaults]]

## Tests

- [[backend/tests/test_middleware.py]] — `test_known_slug_resolves_and_binds_tenant`, `test_unknown_slug_is_404_with_generic_body`, `test_reserved_slug_never_reaches_resolver`, `test_apex_and_foreign_hosts_are_404_without_resolver_call`, `test_failure_kinds_are_indistinguishable`, `test_exempt_paths_ignore_host`, `test_backstop_returns_the_same_generic_body`, `test_host_header_with_port_and_case_resolves`
- [[backend/tests/test_tenancy_integration.py]] — end-to-end against a real database, including `test_suspended_and_deleted_tenants_are_404`
- [[backend/tests/test_storefront_api.py]] — imports `EXEMPT_PATHS` to assert no storefront path is in it

## Notes

Binding `request.state.tenant` is only the first half of isolation. The second half is that every tenant-scoped query runs inside a session with `app.tenant_id` set — see [[backend/app/db/tenant.py]] and [[backend/app/db/rls.py]]. This middleware decides *which* tenant; forced RLS is what makes that decision binding at the database.
