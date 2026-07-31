---
tags: [backend, auth, python, cookies, session, security, tenancy]
sources: [backend/app/auth/cookies.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/auth/cookies.py
blob: 13264a6dd200778d54c857df7358e809896a7e21
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/auth/cookies.py

**Role.** Owns the name of the staff session cookie and the exact attribute set it is written and cleared with — deliberately *without* a `Domain` attribute, which is what keeps a session minted on one boutique's subdomain from being sent to another's.

**Module.** [[backend/app/auth/_index]] · **Layer.** auth

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `SESSION_COOKIE` | const | `"boutique_session"` — the single cookie name the whole backend reads |
| `set_session_cookie` | fn | Writes the session token with `HttpOnly`, `SameSite=Lax`, `Path=/`, caller-supplied `secure` and `max_age` |
| `clear_session_cookie` | fn | Deletes it with the *same* attribute set |

## Behavior

Both functions mutate a Starlette `Response` in place and return nothing; neither knows what a token means. The load-bearing detail is what is *absent*: no `Domain` attribute is set, so the browser stores a **host-only** cookie scoped to `bella.example.com` alone. Since tenants are separated by subdomain (see [[backend/app/tenancy/middleware.py]]), a `Domain=.example.com` cookie would be broadcast to every boutique on the platform, and cross-tenant session presentation would become a browser default rather than an attack. `HttpOnly` removes the cookie from `document.cookie` so an XSS in the console cannot exfiltrate it, and `SameSite=Lax` blocks the cross-site POST that would otherwise let a third-party page drive an authenticated `/manage` mutation. `secure` is a parameter rather than a constant because local development runs on plain HTTP; callers pass `Settings.secure_cookies` (`app_env != "dev"`) from [[backend/app/core/config.py]]. `clear_session_cookie` repeats `httponly`/`samesite`/`path` because a browser only removes a cookie when the delete matches the original attributes — a mismatched `Path` would leave the old cookie alive and logout would silently do nothing in the browser even though the row was revoked server-side.

## Depends On

- [[Starlette]] — `Response.set_cookie` / `delete_cookie` (entity)

## Depended On By

- [[backend/app/auth/router.py]] — sets on login, clears on logout
- [[backend/app/auth/dependencies.py]] — reads `SESSION_COOKIE` off the request in `get_current_staff`
- [[backend/app/auth/staff_router.py]] — reads `SESSION_COOKIE` so the acting session survives a self password change

## Concepts

- [[Owner Authentication]]
- [[Tenant Isolation]]

## Tests

- [[backend/tests/test_auth_api.py]] — asserts the attributes on the login `Set-Cookie` and that logout clears it
- [[backend/tests/test_staff_api.py]] — sends the cookie on every owner-only call
- [[backend/tests/test_staff_role_gating_integration.py]] — real login, real cookie, across roles

## Notes

The cookie name is duplicated as a string literal once, in `logout` in [[backend/app/auth/router.py]] (`request.cookies.get("boutique_session")`), which does not import the constant. Harmless today, but it is the one place a rename would not be caught by the compiler.

Design context: [[.planning/specs/owner-auth.md]].
