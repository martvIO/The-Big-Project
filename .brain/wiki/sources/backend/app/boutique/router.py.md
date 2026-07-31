---
tags: [backend, boutique, router, fastapi, python, api, rbac, settings]
sources: [backend/app/boutique/router.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/boutique/router.py
blob: 86569125cf5528cd46aed4896b266b1b298eb577
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/boutique/router.py

**Role.** The eleven `/manage` owner-settings endpoints — profile/toggles, appointment types, opening hours and terms — gated router-wide on `OWNER | SHIFT_MANAGER`, with terms *publishing* tightened to owner-only on its own route.

**Module.** [[backend/app/boutique/_index]] · **Layer.** api

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `router` | `APIRouter` | `prefix="/manage"`, router-level `Depends(require_role(OWNER, SHIFT_MANAGER))` |
| `get_boutique_service` | dependency | Pulls the singleton off `request.app.state` |
| `get_settings` / `update_settings` | `GET` / `PUT /manage/settings` | The JSONB profile + toggles |
| `list_appointment_types` / `create_appointment_type` / `update_appointment_type` / `archive_appointment_type` | `GET` / `POST /manage/appointment-types`, `PATCH` / `DELETE /manage/appointment-types/{type_id}` | |
| `get_availability` | `GET /manage/availability` | `{rules, exceptions}` |
| `replace_weekly_rules` | `PUT /manage/availability/rules` | Whole week |
| `add_availability_exception` / `remove_availability_exception` | `POST` / `DELETE /manage/availability/exceptions[/{exception_id}]` | |
| `get_terms_history` | `GET /manage/terms` | Paginated, `limit` capped at `TERMS_HISTORY_DEFAULT_LIMIT` |
| `create_terms_version` | `POST /manage/terms` | **Owner-only** — the one per-route tightening |

## Behavior

Every handler resolves the tenant with `get_current_tenant(request)` — host-derived, never from the body — and passes `tenant.id` to the service. Nothing is caught here: the service's four typed errors propagate to the explicit handlers in [[backend/app/main.py]], and the shared `DomainValidationError` / `DomainNotFoundError` handlers cover the rest.

The role model is the interesting part of this file. The router-level `require_role(OWNER, SHIFT_MANAGER)` is the *default posture* for anything added here, and `POST /manage/terms` adds a second, narrower `require_role(OWNER)` in its own `dependencies`. Both gates run — the per-route dependency does not replace the router-level one, it stacks on top, so the tightening is additive and cannot accidentally widen access. The rationale is recorded in the code: publishing a new policy version binds every future booking, so the shift manager reads terms and never writes them. `create_terms_version` is also the only handler that uses `staff` for anything beyond authentication — it passes `staff.id` as `created_by`, which is what makes each immutable version attributable.

`update_settings` is where the JSONB merge semantics are enforced at the HTTP edge: it dumps `body.profile` and `body.toggles` with `model_dump(exclude_unset=True)` because the merge replaces whole top-level keys, so only fields the client actually sent may enter the patch. Sending the model's `None` defaults instead would clear every profile field the client did not mention. `body.profile is not None` and the `exclude_unset` dump are two different distinctions — omitting `profile` entirely leaves the subtree alone, while sending `{"profile": {}}` is a no-op merge.

`get_terms_history` reuses `TERMS_HISTORY_DEFAULT_LIMIT` as both the query default and the `Query(le=…)` ceiling, which is exactly the shortcut [[backend/app/catalog/router.py]] declines to reuse — it only works where the default equals the maximum, and here it does. The service clamps again anyway.

Responses that are pure ORM projections use `model_validate(row)` directly (`AppointmentTypeResponse`, `AvailabilityRuleResponse`, `AvailabilityExceptionResponse`, `TermsVersionResponse`); the two composite shapes (`SettingsResponse`, `AvailabilityResponse`) are assembled from the service's frozen result dataclasses.

## Depends On

- [[backend/app/boutique/service.py]] — `BoutiqueSettingsService`, `TERMS_HISTORY_DEFAULT_LIMIT`
- [[backend/app/boutique/schemas.py]] — every request and response model
- [[backend/app/boutique/validation.py]] — `WeeklyRuleInput`
- [[backend/app/auth/dependencies.py]] — `get_current_staff`, `require_role`
- [[backend/app/auth/service.py]] — `StaffContext`
- [[backend/app/models/constants.py]] — `StaffRole`
- [[backend/app/tenancy/middleware.py]] — `get_current_tenant`
- [[FastAPI]]

## Depended On By

- [[backend/app/main.py]] — mounts this router; [[backend/app/catalog/router.py]] is registered after it, both at `prefix="/manage"`

## Concepts

- [[Role Based Access Control]]
- [[Tenant Resolution]]
- [[Append Only Terms Versions]]

## Tests

- [[backend/tests/test_boutique_api.py]] — endpoint behaviour and status codes
- [[backend/tests/test_staff_role_gating.py]] · [[backend/tests/test_staff_role_gating_integration.py]] — that the shift manager is admitted everywhere here except `POST /manage/terms`
- [[backend/tests/test_boutique_integration.py]]

## Notes

Unlike its catalog sibling this router sets **no** `Cache-Control: no-store` — nothing it returns is bearer material. Adding an endpoint here that returns a signed URL or a token would need that header added deliberately.

The verbs are conventional REST (`PUT`, `PATCH`, `DELETE`); the RPC-only routing convention in `.claude/rules/` is Spartan toolkit boilerplate for a stack this repo does not use.

Design context: [[.planning/specs/owner-settings.md]], [[.planning/specs/staff-roles-gating.md]].
