---
tags: [backend, boutique, schemas, pydantic, python, api, settings]
sources: [backend/app/boutique/schemas.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/boutique/schemas.py
blob: e33ecc18ae74aae77d8365525bf48e130f152997
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/boutique/schemas.py

**Role.** The wire contract for the `/manage` owner-settings API — extra-forbidding request models whose `Field` bounds mirror the migration CHECKs, response models for appointment types, availability and terms versions, and a compatibility re-export of `ForbidExtraModel` / `OkResponse`.

**Module.** [[backend/app/boutique/_index]] · **Layer.** api

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `ProfileUpdate` | request | Six all-optional storefront profile fields; only *sent* keys enter the JSONB patch |
| `TogglesUpdate` | request | `deposits_enabled`, `brides_only` — both optional |
| `UpdateSettingsRequest` | request | `{profile?, toggles?}` |
| `SettingsResponse` | response | `profile` / `toggles` as raw `dict[str, Any]` — the JSONB is echoed, not re-typed |
| `CreateAppointmentTypeRequest` | request | Defaults `audience=ALL`, `deposit_required=False`, `sort_order=0` |
| `UpdateAppointmentTypeRequest` | request | Full replace — every field required, no defaults |
| `AppointmentTypeResponse` | response | `from_attributes=True` ORM projection |
| `WeeklyRuleRequest` / `ReplaceWeeklyRulesRequest` | request | One window; list capped at `MAX_WEEKLY_RULES` |
| `AvailabilityRuleResponse` / `AvailabilityExceptionResponse` / `AvailabilityResponse` | response | ORM projections plus the `{rules, exceptions}` envelope |
| `CreateAvailabilityExceptionRequest` | request | `date` plus optional `open_time`/`close_time`/`note` |
| `CreateTermsRequest` | request | Text, `refundable_until_hours_before`, `forfeit_percent` (default 100) |
| `TermsVersionResponse` / `TermsHistoryResponse` | response | One immutable version; the paginated history with `current` alongside |
| `ForbidExtraModel` / `OkResponse` | re-export | Now defined in [[backend/app/schemas.py]]; re-exported here so no import site changed |

## Behavior

Requests extend `ForbidExtraModel`, so an unknown key is a 422 rather than a silently dropped field — which matters more here than anywhere else in the codebase, because `ProfileUpdate` and `TogglesUpdate` are dumped into a JSONB column that has no schema of its own to catch a stray key. The deeper rules (same-day overlaps, the deposit interplay, the byte-precise terms cap, URL and phone formats) all live in [[backend/app/boutique/validation.py]] and surface as house-shape 400s; the `Field` bounds here are only the cheap first gate.

Two request models are full-replace and say so: `UpdateAppointmentTypeRequest` requires every field with no defaults, so an omitted key can never silently clear a stored value. `ProfileUpdate` is the opposite by design — all six fields default to `None`, and the router calls `model_dump(exclude_unset=True)` so that only keys the client *actually sent* enter the merge patch. Both behaviours are correct for their respective storage: the appointment type is a row, the profile is a merged JSONB subtree.

`CreateTermsRequest.terms_text` carries a *character* cap of `MAX_TERMS_TEXT_BYTES`, which is not a typo but a coarse first filter: it blocks multi-megabyte bodies at the schema layer, while the byte-precise 50 KB check (Hebrew being two bytes per character in UTF-8) stays in `validate_terms`. A Hebrew body can therefore pass the schema and still be rejected by the domain gate — the intended ordering.

`CreateAppointmentTypeRequest.audience` and `UpdateAppointmentTypeRequest.audience` are typed as plain `str`, not as the enum; membership is checked in `validate_appointment_type` against `AppointmentAudience`'s values, so a bad audience is a domain 400 rather than a Pydantic 422. `SettingsResponse` echoes untyped dicts for the same family of reasons — the JSONB subtree's shape is enforced on write, not on read.

The `from … import X as X` form on the two re-exports at the top is the idiom ruff accepts as a deliberate re-export. They were moved to `app/schemas.py` so that [[backend/app/catalog/schemas.py]] would not have to import a boutique schema; nothing about the wire shape changed.

## Depends On

- [[backend/app/boutique/validation.py]] — every `Field` bound
- [[backend/app/schemas.py]] — `ForbidExtraModel`, `OkResponse`
- [[backend/app/models/constants.py]] — `AppointmentAudience` (as the default value only)
- [[Pydantic]]

## Depended On By

- [[backend/app/boutique/router.py]] — request bodies and every declared response type
- [[backend/tests/test_storefront_api.py]] — imports `TermsVersionResponse` to compare against the public terms shape

## Concepts

- [[Full Replace Update Semantics]]
- [[Append Only Terms Versions]]

## Tests

- [[backend/tests/test_boutique_api.py]] — request rejection and response shape over the ASGI app
- [[backend/tests/test_storefront_api.py]] — the terms shape as the public surface sees it

## Notes

`TermsVersionResponse` exposes `created_by` (a staff user id) on the manage surface. The public terms payload is `StorefrontTerms` in [[backend/app/storefront/schemas.py]], which is deliberately **not** a subclass of this model — inheriting would have leaked `created_by` to anonymous readers the moment either side gained a field.
