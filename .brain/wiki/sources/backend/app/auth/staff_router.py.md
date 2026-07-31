---
tags: [backend, auth, python, fastapi, routing, staff, rbac, owner-only]
sources: [backend/app/auth/staff_router.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/auth/staff_router.py
blob: 799366b4b3908d5f7f32164e8632cebcd86fd5ba
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/auth/staff_router.py

**Role.** The four owner-only staff routes on `/manage` — list, create, patch, deactivate — gated at **router** level so a route added here later cannot forget the gate, and carrying `no-store` on every response.

**Module.** [[backend/app/auth/_index]] · **Layer.** api

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `router` | `APIRouter` | `prefix="/manage"`, `dependencies=[Depends(_no_store), Depends(require_role(StaffRole.OWNER))]` |
| `GET /manage/staff` | route | `list[StaffMember]` — a bare array, no envelope, no pagination |
| `POST /manage/staff` | route | Create → `StaffMember` |
| `PATCH /manage/staff/{staff_id}` | route | Name / role / password → `StaffMember` |
| `DELETE /manage/staff/{staff_id}` | route | Soft-delete → `OkResponse` |
| `get_staff_service` | fn | Pulls `StaffService` off `request.app.state` — the seam tests override |
| `_no_store` | fn | Sets `cache-control: no-store` |
| `_member` | fn | `StaffUser` row → `StaffMember` |

## Behavior

Owner-only is declared **once**, on the router, not four times on the routes. That is not only tidiness: [[backend/tests/test_staff_role_gating.py]]'s walker reads `allowed_roles` off whatever `RoleGate` a route carries, and the four `(method, path)` templates here must also appear in that module's `OWNER_ONLY` set — spelled as *route-table templates* (`PATCH /manage/staff/{staff_id}`), never as concrete URLs, because the walker compares against `route.path` and a literal UUID would never match. Adding an owner-only tightening anywhere in the app without updating that set is a red build.

Every handler still takes `staff: Staff` even though the gate already refused unauthorized callers. It is not a second guard — the acting id is what `StaffService`'s self-guards compare against and what every audit row records. FastAPI's per-request dependency cache resolves `get_current_staff` once for both the gate and the handler, so this costs no extra `resolve_session`.

`update_staff` does one thing the other three do not: it reads `SESSION_COOKIE` off the request and passes `hash_token(token)` down as `acting_token_hash`. A password write revokes the target's other sessions, and this is the one cookie that must survive it — otherwise an owner changing her own password would be signed out of the tab she just used. The `staff` dependency has already proved the cookie is present and valid, so the `if token else None` is defensive rather than a real branch. `role` is unwrapped from the enum to its `.value` before the service call, since `StaffService` is written against role strings.

This is the **fifth** router mounted on `/manage`, included after the owner booking router in [[backend/app/main.py]]. Five surfaces on one prefix means a duplicated `(method, path)` would silently win or lose on include order with no error; the `ROUTES` table in [[backend/tests/test_staff_api.py]] is what keeps that honest.

Path parameters and real HTTP verbs (`PATCH`, `DELETE`) are the shipped `/manage` convention here, matching [[backend/app/boutique/router.py]], [[backend/app/catalog/router.py]] and [[backend/app/booking/owner_router.py]]. The RPC-style / query-parameter guidance under `.claude/rules/` is Kotlin toolkit boilerplate for a different codebase and does not apply.

## Depends On

- [[backend/app/auth/staff.py]] — `StaffService`
- [[backend/app/auth/dependencies.py]] — `get_current_staff`, `require_role`
- [[backend/app/auth/schemas.py]] — `CreateStaffRequest`, `UpdateStaffRequest`, `StaffMember`
- [[backend/app/auth/service.py]] — `StaffContext`
- [[backend/app/auth/cookies.py]] — `SESSION_COOKIE`
- [[backend/app/auth/tokens.py]] — `hash_token`
- [[backend/app/models/constants.py]] — `StaffRole`
- [[backend/app/models/staff_user.py]] — the row `_member` converts
- [[backend/app/schemas.py]] — `OkResponse`
- [[backend/app/tenancy/middleware.py]] — `get_current_tenant`
- [[FastAPI]] (entity)

## Depended On By

- [[backend/app/main.py]] — includes it as the fifth `/manage` router

## Concepts

- [[Role Based Access Control]]
- [[Tenant Resolution]]

## Tests

- [[backend/tests/test_staff_api.py]] — the `ROUTES` table, the happy paths, the error codes (409s for duplicate email / last owner / self-manage, 404 for an unknown id) and the `no-store` header
- [[backend/tests/test_staff_role_gating.py]] — asserts these four templates are exactly the router's owner-only surface and that a `shift_manager` gets 403 on each
- [[backend/tests/test_staff_role_gating_integration.py]] — the same against a real database

## Notes

`_no_store` is a third local three-line copy rather than an import from [[backend/app/booking/owner_router.py]] — importing would point the dependency arrow backwards (`app.auth` depending on `app.booking`) to save three lines, and hoisting it to a new shared module would touch two shipped files for cosmetics. Recorded in the module docstring so the duplication reads as a decision.

Design context: [[.planning/specs/staff-management.md]], [[.planning/specs/staff-roles-gating.md]].
