---
tags: [backend, boutique, service, python, settings, concurrency, rate-limiting, tenancy]
sources: [backend/app/boutique/service.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/boutique/service.py
blob: d90275d96527cacecd894c009ac3c4c8cbeec0bc
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/boutique/service.py

**Role.** Owner-settings business logic — the `tenants.settings` JSONB merge, appointment-type CRUD, the whole-week opening-hours replace and exception dates, and the append-only cancellation-policy terms versions with their optimistic version race and per-tenant creation throttle.

**Module.** [[backend/app/boutique/_index]] · **Layer.** db

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `BoutiqueSettingsService` | class | Constructed with a session factory and a terms `FixedWindowRateLimiter` |
| `get_settings` / `update_settings` | method | Read and merge the `tenants.settings` JSONB subtrees |
| `list_appointment_types` / `create_appointment_type` / `update_appointment_type` / `archive_appointment_type` | method | Appointment-type lifecycle |
| `get_availability` / `replace_weekly_rules` / `add_availability_exception` / `remove_availability_exception` | method | Opening hours |
| `create_terms_version` / `get_terms_history` | method | Append-only policy versions |
| `SettingsResult` / `AvailabilityResult` / `TermsHistoryResult` | frozen dataclass | The router's input types |
| `NotFoundError` | error | `DomainNotFoundError` subclass → shared 404 |
| `DuplicateNameError` / `DuplicateDateError` / `TermsVersionConflictError` | error | 409 each, distinct bodies |
| `TermsThrottledError` | error | 429 |
| `TERMS_HISTORY_DEFAULT_LIMIT` | const | 50 — also the page-size *maximum* |

## Behavior

Every tenant-scoped table is reached through `tenant_session`, which binds the RLS tenant context — without it FORCE RLS returns zero rows rather than erroring, so a forgotten context reads as "empty boutique", not as a crash. `tenants.settings` is the one exception: it lives on the platform-scoped `tenants` table and goes through `TenantsRepository`, which is constructed with the session factory and manages its own sessions.

`update_settings` validates each subtree only when the caller passed it, then delegates to `merge_settings`. The merge replaces whole top-level keys, which is why [[backend/app/boutique/router.py]] dumps the request with `exclude_unset=True` — sending the model's defaults would clear every profile field the client did not mention. `_settings_result` defensively copies with `dict(settings.get("profile") or {})`, so a tenant row whose `settings` has never been written still yields empty dicts rather than `None`.

The three `IntegrityError` catches are all narrowings of the same idea: validation has already covered every CHECK constraint, so an integrity failure at that point can only be the partial unique index — `(tenant_id, name)` for appointment types, `(tenant_id, date)` for exceptions — and each is re-raised as a typed 409. `raise … from None` is used throughout so the SQL detail does not ride along in the traceback.

`replace_weekly_rules` validates *first*, so a rejected replacement leaves the existing week untouched, then takes `pg_advisory_xact_lock(hashtext(:tenant_id))` inside the transaction before soft-deleting and re-inserting. Without that lock two concurrent replaces under READ COMMITTED would both pass validation and UNION their sets, leaving a week neither caller asked for. Note the key is the bare tenant id with **no prefix** — [[backend/app/catalog/service.py]] deliberately prefixes its own locks (`dress-media:` / `dress-variants:`) to stay clear of this lock space.

`create_terms_version` is the most intricate path. Validation runs first, then the throttle check, then `_insert_next_terms_version` computes `max_version + 1` and inserts optimistically. Losing the race raises `IntegrityError`, and because an aborted transaction cannot be reused the retry must open a **fresh** `tenant_session` and recompute the max — a second loss becomes `TermsVersionConflictError` and the caller retries the whole request. The final `record_failure` on success is not a bug: `FixedWindowRateLimiter` counts only what is explicitly recorded, so every *successful* creation must be charged by hand, because rows on this append-only table are permanent and spam here is permanent bloat. One budget is one limiter instance, and this one's `max_attempts` comes from `terms_creation_max_per_window` in [[backend/app/core/config.py]].

`get_terms_history` clamps `offset` at zero and `limit` into `[1, TERMS_HISTORY_DEFAULT_LIMIT]`, so the default and the maximum are the same number — history is unbounded by design and it is the page size, not the data, that is capped. It issues three statements in one read transaction (`current`, the page, the count) so the total cannot disagree with the page it describes.

## Depends On

- [[backend/app/db/tenant.py]] — `tenant_session`
- [[backend/app/db/repositories/tenants.py]] — the platform-scoped settings read/merge
- [[backend/app/db/repositories/appointment_types.py]] · [[backend/app/db/repositories/availability.py]] · [[backend/app/db/repositories/terms.py]]
- [[backend/app/boutique/validation.py]] — every validator and `WeeklyRuleInput`
- [[backend/app/auth/rate_limit.py]] — `FixedWindowRateLimiter`
- [[backend/app/errors.py]] — `DomainNotFoundError`
- [[backend/app/models/appointment_type.py]] · [[backend/app/models/availability.py]] · [[backend/app/models/terms_version.py]] · [[backend/app/models/constants.py]]
- [[SQLAlchemy]] — `text`, `IntegrityError`, async session types

## Depended On By

- [[backend/app/boutique/router.py]] — the whole surface, plus `TERMS_HISTORY_DEFAULT_LIMIT` as the query-param ceiling
- [[backend/app/main.py]] — constructs the service with its terms limiter and registers a handler for each of the four typed errors
- [[backend/tests/test_storefront_integration.py]] · [[backend/tests/test_storefront_isolation.py]] · [[backend/tests/test_staff_management_db.py]] · [[backend/tests/test_staff_role_gating_integration.py]] — seed settings, hours and terms through this service

## Concepts

- [[Row Level Security]]
- [[Tenant Isolation]]
- [[Advisory Lock]]
- [[Append Only Terms Versions]]

## Tests

- [[backend/tests/test_boutique_service.py]] — the unit-level suite over the typed errors
- [[backend/tests/test_boutique_integration.py]] — DB-backed, including the version race and the overlap rejection
- [[backend/tests/test_boutique_api.py]] — the HTTP surface

## Notes

`archive_appointment_type` and `remove_availability_exception` raise `NotFoundError` **after** the session closes, from the repository's boolean return, rather than reading the row first — one statement instead of two, and the soft-delete predicate already carries the tenant id as defense in depth on top of RLS.

There is no error registry in [[backend/app/main.py]]: `DuplicateNameError`, `DuplicateDateError`, `TermsVersionConflictError` and `TermsThrottledError` each need their own explicit `@app.exception_handler`, and all four currently have one.

Design context: [[.planning/specs/owner-settings.md]].
