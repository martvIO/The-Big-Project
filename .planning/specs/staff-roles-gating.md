# Spec: F31 — staff roles & default-deny manage gating (SMC-1)

Epic: `.planning/epics/shift-manager-console.md`. Backend-only PR. Gate 1
self-approves (no money/legal surface).

## Problem

`staff_users.role` is free TEXT with a single enum member (`owner`) and **no route
checks it** — `Depends(get_current_staff)` is authentication only. The moment a
second role can exist, every `/manage` route silently grants it everything. E6's
brief names missing gating the epic's most likely security defect.

## Scope

1. **`StaffRole.SHIFT_MANAGER`** joins the enum (`Backend/app/models/constants.py`).
2. **Migration 0011**: `CHECK (role IN ('owner','shift_manager'))` on `staff_users`.
   Only two values — reception/seamstress/sales wait for their first consumer
   (pre-adding speculative kinds is the un-lazy thing, house precedent D9).
3. **`require_role(*allowed)`** dependency in `Backend/app/auth/dependencies.py` —
   a callable `RoleGate` carrying an introspectable `allowed_roles` frozenset,
   raising the relocated **`NotAuthorizedError`** (formerly planned in F15's
   `booking/owner.py`; lives here so both consumers share one class and one
   403 handler). Body: `NOT_AUTHORIZED`, 403, role-neutral message.
4. **Router-level gating**: boutique + catalog routers → `(OWNER, SHIFT_MANAGER)`;
   route-level tightening `POST /manage/terms` → `(OWNER,)` (composes additively —
   both gates run). Auth router: login anonymous; logout/me any-authenticated.
5. **Default-deny is a CI test, not a convention**: a fast route-walker asserts
   every `/manage` route outside a pinned allowlist (`login`, `logout`, `me`)
   carries a `RoleGate`. A future ungated `/manage` router is a red build.

## Permission matrix (locked)

| Surface | owner | shift_manager |
|---|---|---|
| settings, hours, types, catalog, terms GET | ✓ | ✓ |
| `POST /manage/terms` (publish) | ✓ | 403 |
| staff router (F51) | ✓ | 403 |
| F15 bookings routes (on rebase) | ✓ | ✓ |

## Non-goals

- No staff CRUD API/UI (F51). No login changes (`AuthService.login` is role-blind;
  email+password per Q11 override). No frontend change — a shift_manager cannot
  exist until F51 ships the creation UI; today's nav needs no filtering.
- No session invalidation work: `resolve_session` re-reads `staff_users` per
  request, so demotion/deactivation is instantly effective by construction.

## Tests

- `test_staff_role_gating.py` (fast): default-deny walker; RoleGate unit matrix
  (owner passes, shift_manager 403 on OWNER-only gate, unknown role refused
  everywhere); HTTP matrix over the boutique ROUTES table as shift_manager —
  everything 2xx except `POST /manage/terms` → 403 `NOT_AUTHORIZED`.
- db-marked: migration CHECK rejects a bogus role INSERT, admits `shift_manager`.

## Risks

- Widening F15's owner router to shift_manager on rebase hands them the
  phone-correction surface (F15's top risk) — accepted by the user's near-owner
  ruling; recorded here for the F21 audit.
- FastAPI dependency caching (`use_cache=True`) resolves `get_current_staff` once
  per request even with two gates — verified in tests via the fake auth service.
