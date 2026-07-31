---
tags: [backend, auth, python, fastapi, authorization, roles, rbac, security]
sources: [backend/app/auth/dependencies.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/auth/dependencies.py
blob: 6aa4d0dd98136866f6d10a7bdd7cdb7e0124a0b2
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/auth/dependencies.py

**Role.** The authentication and authorization seam every `/manage` route hangs off: `get_current_staff` turns the session cookie into a `StaffContext` or raises, `RoleGate`/`require_role` admits only listed roles and fails closed on everything else, and the two exception types here are what [[backend/app/main.py]] maps to a single generic 401 and a single generic 403.

**Module.** [[backend/app/auth/_index]] · **Layer.** auth

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `NotAuthenticatedError` | exception | No valid session — one 401 body whether the cookie is missing, expired, revoked, or another tenant's |
| `NotAuthorizedError` | exception | Live session, unadmitted role — one 403 body for every role, so a probe learns nothing about the role set |
| `get_auth_service` | fn | Pulls `AuthService` off `request.app.state` |
| `get_current_staff` | async fn | Cookie → tenant-scoped `resolve_session` → `StaffContext`, else `NotAuthenticatedError` |
| `RoleGate` | class | Callable dependency holding `allowed_roles: frozenset[str]` |
| `require_role` | fn | `require_role(StaffRole.OWNER, ...)` → a `RoleGate` |

## Behavior

`get_current_staff` reads the tenant from the request first (via [[backend/app/tenancy/middleware.py#get_current_tenant]]), then the cookie, then calls `AuthService.resolve_session(tenant.id, token)`. Every failure funnels to the same bare `NotAuthenticatedError` — the cross-tenant case does not even need a check, because the lookup runs inside a tenant-bound session and forced RLS makes another boutique's session row simply not exist (see [[backend/app/db/rls.py]]). `RoleGate.__call__` depends on `get_current_staff`, so a gate implies authentication: an anonymous request 401s before any role is examined. The membership test is `staff.role not in self.allowed_roles` against a frozenset of enum *values*, which is what makes it **fail closed** — a role string the `StaffRole` enum does not know (a future DB value, a hand-edited row) matches nothing and is refused, rather than falling through a `match` with a permissive default.

Two structural properties matter more than the code. First, gates compose: a router-level `Depends(require_role(...))` sets the default posture and a per-route gate tightens it, and because both resolve the same `get_current_staff` dependency, FastAPI's per-request dependency cache collapses them to **one** `resolve_session` call — so layering gates costs no extra database round-trip. Second, `allowed_roles` is deliberately a public attribute because [[backend/tests/test_staff_role_gating.py]] walks the *live* route table and asserts every `/manage` route carries a `RoleGate`, with an explicit two-route allowlist (login and logout, both anonymous by design — logout carries no auth dependency at all, since gating the one action a staffer takes when her session is already broken would 401 it). A future router mounted under `/manage` without a gate is therefore a red build, not a convention someone remembered.

There is no session state to invalidate: `resolve_session` re-reads `staff_users` on every request, so a role change or a deactivation bites on the very next call. That is why [[backend/app/auth/staff.py#deactivate]] performs no session sweep and why a *password* change is the only mutation that needs an explicit revoke.

Both exception classes live here rather than in a domain module because every `/manage` router raises them, and [[backend/app/main.py]] holds no error registry — each one needs its own explicit `@app.exception_handler`, registered once for the whole app.

## Depends On

- [[backend/app/auth/cookies.py]] — `SESSION_COOKIE`
- [[backend/app/auth/service.py]] — `AuthService.resolve_session`, `StaffContext`
- [[backend/app/models/constants.py]] — `StaffRole`
- [[backend/app/tenancy/middleware.py]] — `get_current_tenant`
- [[FastAPI]] — `Depends`, `Request` (entity)

## Depended On By

- [[backend/app/main.py]] — registers the 401 and 403 handlers
- [[backend/app/auth/router.py]] — `get_auth_service`, `get_current_staff` for `/manage/auth/me`
- [[backend/app/auth/staff_router.py]] — router-level `require_role(StaffRole.OWNER)`
- [[backend/app/boutique/router.py]] · [[backend/app/catalog/router.py]] · [[backend/app/booking/owner_router.py]] — the other three `/manage` routers

## Concepts

- [[Role Based Access Control]]
- [[Fail Closed Defaults]]
- [[Session Authentication]]
- [[Tenant Isolation]]

## Tests

- [[backend/tests/test_staff_role_gating.py]] — the default-deny route walker, the `OWNER_ONLY` permission matrix pinned against the live route table, the `RoleGate` unit matrix (including an unknown-role sentinel asserted not to be a real `StaffRole`), and an HTTP matrix
- [[backend/tests/test_staff_role_gating_integration.py]] — the same gating against a real database and real logins
- [[backend/tests/test_auth_api.py]] — 401 shape for missing / expired / revoked cookies
- [[backend/tests/test_staff_api.py]] — 403 shape for a `shift_manager` on the owner-only routes

## Notes

`get_auth_service` is the seam every API suite overrides (`app.dependency_overrides[get_auth_service]`) to swap in a fake service — which is why it is a function dependency rather than a direct `request.app.state` read inside the handlers.

Design context: [[.planning/specs/staff-roles-gating.md]], [[.planning/specs/owner-auth.md]].
