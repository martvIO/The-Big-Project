---
tags: [backend, security, python, middleware, csrf, manage]
sources: [backend/app/csrf.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/csrf.py
blob: 98bcd3e5069ca22937c019bf7e60d47105be3c83
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# backend/app/csrf.py

**Role.** Middleware that rejects a mutating `/manage` request whose `Origin` header names a different hostname than its `Host` header, with a 403 `CSRF_ORIGIN_MISMATCH` — the defense `SameSite=Lax` cannot provide once sibling tenant subdomains are same-*site*.

**Module.** [[backend/app/_index]] · **Layer.** platform

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `CsrfOriginMiddleware` | class | `BaseHTTPMiddleware` — the fence |
| `MUTATING_METHODS` | const | `POST` · `PUT` · `PATCH` · `DELETE` |
| `PROTECTED_PREFIX` | const | `"/manage"` |
| `CSRF_ORIGIN_MISMATCH_BODY` | const | House-shape error body, imported by tests |
| `_origin_matches_host` / `_hostname` | fn | Hostname-only comparison helpers |

## Behavior

`dispatch` short-circuits unless the method is mutating **and** the path starts with `/manage`; reads pass through untouched, which is why `test_the_staff_list_read_with_a_mismatched_origin_is_allowed` and its catalog/booking siblings exist. A request with **no** `Origin` header passes deliberately: an absent `Origin` is not a browser cross-origin submission (curl, server-to-server, the test client), and rejecting it would break every non-browser caller for no gain. Comparison is **hostname only** — port and scheme are ignored — because the dev proxy serves the app on `:5173` while the API sees the same hostname, and the attack actually being blocked (one boutique's public storefront subdomain forging a write against a sibling's console) is a hostname property. A malformed `Origin`, or the literal `"null"` that sandboxed iframes and some redirect chains send, parses to `None` and is rejected; so is a request whose `Host` header is missing. The 403 is returned from the middleware's own `dispatch` without reaching a handler, so it is not covered by any `@app.exception_handler` — [[backend/app/security_headers.py]] still stamps it because that middleware is registered later and therefore sits outside this one.

Registration order in `create_app` is load-bearing: this is added **after** `TenantResolutionMiddleware`, so it runs **before** it, and a forged cross-origin write is refused without ever touching the database.

## Depends On

- [[Starlette]] — `BaseHTTPMiddleware`, `JSONResponse`
- [[FastAPI]] — `Request`

## Depended On By

- [[backend/app/main.py]] — `app.add_middleware(CsrfOriginMiddleware)`

## Concepts

- [[Tenant Resolution]]

## Tests

- [[backend/tests/test_boutique_api.py]] — `test_mutating_request_with_mismatched_origin_is_403`, `test_matching_origin_is_allowed_even_with_different_port`, `test_auth_login_is_csrf_protected_too`
- [[backend/tests/test_catalog_api.py]] — `test_mutating_catalog_request_with_mismatched_origin_is_403`, `test_catalog_read_with_mismatched_origin_is_allowed`
- [[backend/tests/test_staff_api.py]] — `test_a_mutating_staff_request_with_a_mismatched_origin_is_403`, `test_patch_and_delete_are_both_inside_the_csrf_fence`
- [[backend/tests/test_booking_owner_api.py]] — `test_a_mutating_owner_booking_request_from_a_foreign_origin_is_403`
- [[backend/tests/test_staff_role_gating.py]] — `test_a_forged_origin_beats_the_role_gate_on_the_same_route` (the fence fires before role checks)

## Notes

The fence is keyed on the `/manage` prefix, so any new cookie-authenticated surface mounted elsewhere would be outside it. `test_patch_and_delete_are_both_inside_the_csrf_fence` guards the method set, not the prefix — a new prefix is the gap a reviewer has to catch.

Design context: [[.planning/specs/storefront-browse.md]] (the F10 sibling-subdomain argument).
