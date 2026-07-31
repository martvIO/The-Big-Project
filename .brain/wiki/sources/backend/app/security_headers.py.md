---
tags: [backend, security, python, middleware, headers, storefront]
sources: [backend/app/security_headers.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/security_headers.py
blob: 64ecf149b53c0a2c3dd7c3830f0863af366da068
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# backend/app/security_headers.py

**Role.** Outermost middleware; stamps `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff` and `Referrer-Policy: strict-origin-when-cross-origin` onto every response the app emits — including the ones returned from inside another middleware, which no inner middleware could reach.

**Module.** [[backend/app/_index]] · **Layer.** platform

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `SecurityHeadersMiddleware` | class | `BaseHTTPMiddleware`; registered **last** in `create_app` |
| `SECURITY_HEADERS` | const | The three header/value pairs, imported by tests |

## Behavior

`dispatch` awaits the downstream response and applies each header with `setdefault`, **not** assignment — a route with a documented reason to differ keeps its own value instead of being silently overwritten. Registration order is the load-bearing part: Starlette runs the most-recently-added middleware first, so being added last in `create_app` puts this **outside** [[backend/app/csrf.py]] and [[backend/app/tenancy/middleware.py]]. That matters for one specific response — the `404 TENANT_NOT_FOUND` that `TenantResolutionMiddleware` returns from its own `dispatch` without ever reaching a handler. On a public storefront that is the single most-served response to anyone probing the wildcard domain, and an inner middleware would miss it entirely; `test_security_headers_are_on_the_tenant_not_found_404` is the guard. The same reasoning covers the 403 that `CsrfOriginMiddleware` returns from its dispatch.

Two absences are decisions, not gaps, and the module's docstring records both.

**`X-Frame-Options: DENY` here is API defense-in-depth, not the clickjacking fix for the manage console.** The framable document is `index.html`, served by Vite in dev and by a static host in production — neither passes through this middleware. That requirement belongs to the frontend-deploy pipeline. Embedding a tenant storefront in a third-party site is unsupported in v1; a per-tenant `frame-ancestors` allowlist is a later concern if a boutique ever asks.

**HSTS and CSP are deliberately absent.** HSTS needs the real domain and a TLS-termination decision that is still blocked, and a `max-age` stamped against a `.invalid` staging host is meaningless. A CSP for a Vite bundle needs a nonce-or-hash story authored against a deployed artifact, and there is no frontend deploy pipeline to author it against. Owner: F21. Trigger: the domain is purchased.

## Depends On

- [[Starlette]] — `BaseHTTPMiddleware`
- [[FastAPI]] — `Request`

## Depended On By

- [[backend/app/main.py]] — `app.add_middleware(SecurityHeadersMiddleware)`, the last registration

## Concepts

- [[Tenant Resolution]]

## Tests

- [[backend/tests/test_storefront_api.py]] — `test_security_headers_are_on_a_storefront_response`, `test_security_headers_are_on_a_manage_response`, and `test_security_headers_are_on_the_tenant_not_found_404` (the one that pins the ordering)
- [[backend/tests/test_booking_manage_api.py]] — `test_every_manage_route_carries_the_security_headers`, parameterized over every path
- [[backend/tests/test_notifications_api.py]] — `test_security_headers_are_on_an_otp_response`
- [[backend/tests/test_booking_api.py]] — imports `SECURITY_HEADERS` for the public booking surface

## Notes

Every test asserts against the imported `SECURITY_HEADERS` dict rather than literal strings, so adding a header here automatically widens the assertions — but only for the routes each test already covers. A new *surface* still needs its own row.

Design context: [[.planning/specs/storefront-browse.md]] (Risks 2 — the frontend-deploy owner of the real clickjacking fix) and [[.planning/specs/staging-and-external-apps.md]] (the domain/TLS blocker behind HSTS).
