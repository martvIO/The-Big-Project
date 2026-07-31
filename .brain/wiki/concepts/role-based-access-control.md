---
tags: [backend, auth, security, staff, testing]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: active
---

# Role Based Access Control

**What it is.** Every route under `/manage` carries a `RoleGate`, and the set of roles is
deliberately tiny: `owner` and `shift_manager`, and nothing else
([[backend/app/models/constants.py#StaffRole]], pinned by migration
[[backend/migrations/versions/0011_staff_roles.py]]).

## The gate

`RoleGate` / `require_role` live in [[backend/app/auth/dependencies.py]]. It is applied
**router-level as the default posture** and **per-route to tighten** — both gates run, and
FastAPI's per-request dependency cache collapses them to a single `resolve_session` call. A role
the enum does not know is refused, not admitted by accident.

The owner-only set is small on purpose: `POST /manage/terms` plus the four staff-administration
routes in [[backend/app/auth/staff_router.py]]. Everything else on `/manage` admits the shift
manager.

## Default-deny is proved, not asserted

[[backend/tests/test_staff_role_gating.py]] walks the **live route table** built by `create_app`
and introspects `RoleGate.allowed_roles` through the dependency tree. Three structural tests
matter more than the HTTP matrix beside them:

- every `/manage` route must carry a gate — a future router mounted there without one is a red
  build, not a convention;
- every gate must admit only strings that are live `StaffRole` values;
- the permission matrix itself is asserted over that table: a route locks the shift manager out
  **only** if it is named in `OWNER_ONLY`, and every `OWNER_ONLY` route must actually carry a gate
  that excludes her.

The inverse is guarded too: no route outside `/manage` may carry a gate, because a copy-pasted
`RoleGate` on `/storefront` would refuse the open internet.

## The traps

- **`OWNER_ONLY` entries are route-table *templates*, not URLs.** The walker reads `route.path`,
  so `/manage/staff/{staff_id}` matches and a concrete `/manage/staff/<uuid>` never would — it
  would red-fail with the opposite message.
- **The 403 body never names a role.** One generic `NOT_AUTHORIZED` for every unadmitted role, so
  a probe cannot learn which roles exist. Almost every 403 assertion compares against the imported
  constant, so both sides would move together on a rename; exactly one test reads the literals and
  scans the body for every `StaffRole` value. See [[Enumeration Resistance]].
- **Three `/manage` routes are ungated by design** — login, logout and `auth/me`. Logout carries
  *no* auth dependency at all: gating the one action a staffer takes when her session is already
  broken would 401 it.
- **A forged `Origin` wins.** [[CSRF Origin Check]] runs before routing, so its 403 can never
  surface as `NOT_AUTHORIZED`.

## Related

- [[Owner Authentication]] — role changes bite on the next request because nothing is cached
- [[backend/tests/test_staff_role_gating_integration.py]] · [[backend/app/auth/staff.py]]
- [[.planning/specs/staff-roles-gating.md]] · [[.planning/epics/shift-manager-console.md]]
