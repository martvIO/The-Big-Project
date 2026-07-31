---
tags: [backend, auth, python, fastapi, routing, login, rate-limiting, security]
sources: [backend/app/auth/router.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/auth/router.py
blob: e1fcc5dc68be75bca68659dbaf0e7603475d8e8c
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/auth/router.py

**Role.** The three `/manage/auth` routes — login (rate-limited per `(tenant,email)`, and per-IP only when a real client IP can be trusted), logout, and `me` — plus `RateLimitedError`, the 429 the login budget raises.

**Module.** [[backend/app/auth/_index]] · **Layer.** api

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `router` | `APIRouter` | `prefix="/manage/auth"` |
| `RateLimitedError` | exception | Login budget exhausted → [[backend/app/main.py]] answers 429 with the shared too-many-attempts body |
| `POST /manage/auth/login` | route | Verifies credentials, sets the session cookie, returns `StaffResponse` |
| `POST /manage/auth/logout` | route | Revokes if a cookie is present, always clears the cookie, always 200 |
| `GET /manage/auth/me` | route | The current `StaffResponse`; the only gated route here |
| `_client_ip` | fn | Real client IP or `None` — never the proxy's |
| `_staff_response` | fn | `StaffContext` → `StaffResponse` |

## Behavior

`login` builds its limiter keys before touching the service: `t:{tenant_id}:e:{email}` is the **always-on** brute-force control, and `ip:{ip}` is appended only when `_client_ip` returns something. That function returns `None` unless `Settings.trust_forwarded_for` is set, and the reasoning is the load-bearing part — behind a load balancer `request.client.host` is the *proxy*, so a per-IP bucket would be one global bucket and a small burst could 429 every boutique on the platform. Skipping the key entirely is safer than keying on a wrong value. With exactly one trusted proxy hop, the **last** `X-Forwarded-For` entry is taken, because that is the address the proxy itself observed; earlier entries are client-supplied and forgeable.

The order of operations is the other thing to read before editing: `is_blocked` is checked on *all* keys first (any one blocked → `RateLimitedError`, no credential work done), the service call runs, and only `InvalidCredentialsError` charges the keys. Successes never charge anyone, and success calls `limiter.reset(keys[0])` — the `(tenant,email)` key only; a shared-IP key is deliberately left standing so one user's success cannot clear another's accumulated failures. The email is lowercased here, matching what [[backend/app/auth/staff.py]] and the provisioning path write, since `by_email` matches exactly.

`logout` carries **no** authentication dependency at all, and that is deliberate rather than an oversight: with no cookie the revoke is skipped and the caller still gets `200 {"ok": true}`. Gating the one action a staffer takes when her session is already broken would 401 it. [[backend/tests/test_staff_role_gating.py]]'s default-deny walker names login and logout as the only two `/manage` routes allowed to carry no `RoleGate`, and pins this logout behaviour with its own tests. `me` is the gated one, via `get_current_staff`.

`RateLimitedError` is its own class rather than a shared throttle base because the login form's budget and the anonymous read surfaces' budgets have unrelated keys and operational meanings; reparenting all the throttle errors onto one base is named as F21 work. There is no error registry in [[backend/app/main.py]] — this class needs, and has, its own explicit handler.

## Depends On

- [[backend/app/auth/service.py]] — `AuthService.login` / `logout`, `InvalidCredentialsError`, `StaffContext`
- [[backend/app/auth/dependencies.py]] — `get_auth_service`, `get_current_staff`
- [[backend/app/auth/cookies.py]] — `set_session_cookie`, `clear_session_cookie`
- [[backend/app/auth/schemas.py]] — `LoginRequest`, `StaffResponse`
- [[backend/app/auth/rate_limit.py]] — `FixedWindowRateLimiter` (the instance lives on `app.state.login_rate_limiter`)
- [[backend/app/core/config.py]] — `secure_cookies`, `session_ttl_seconds`, `trust_forwarded_for`
- [[backend/app/tenancy/middleware.py]] — `get_current_tenant`
- [[FastAPI]] (entity)

## Depended On By

- [[backend/app/main.py]] — includes the router (first of the `/manage` mounts) and registers the `RateLimitedError` 429 handler

## Concepts

- [[Owner Authentication]]
- [[Rate Limiting]]
- [[Enumeration Resistance]]

## Tests

- [[backend/tests/test_auth_api.py]] — the whole surface: cookie attributes, the 401 body, the budget (including that success resets it), and the `me` route
- [[backend/tests/test_staff_role_gating.py]] — pins login and logout as the only ungated `/manage` routes, and that a cookie-less logout still answers 200
- [[backend/tests/test_auth_integration.py]] — the same flow against a real database

## Notes

`logout` reads the cookie as the literal `"boutique_session"` instead of importing `SESSION_COOKIE` from [[backend/app/auth/cookies.py]] — the one place in the backend where the cookie name is not the constant.

Design context: [[.planning/specs/owner-auth.md]].
