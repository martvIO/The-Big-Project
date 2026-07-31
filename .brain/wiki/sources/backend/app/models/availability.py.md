---
tags: [backend, models, db, boutique, availability, slots, python]
sources: [backend/app/models/availability.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/models/availability.py
blob: 91e79e0456a134a32128c5ffc43be4b6ff9e76c4
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/models/availability.py

**Role.** The two tables the slot engine reads: `availability_rules` (the recurring weekly opening grid, with a per-window parallel-appointment `capacity`) and `availability_exceptions` (a per-date override that beats the grid in both directions).

**Module.** [[backend/app/models/_index]] · **Layer.** models

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `AvailabilityRule` | class | `availability_rules` — one weekly window |
| `AvailabilityRule.day_of_week` | column | **0 = Sunday … 6 = Saturday**, the Israeli week; DB `CHECK BETWEEN 0 AND 6` |
| `AvailabilityRule.open_time` / `close_time` | columns | `TIME`, both NOT NULL; DB `CHECK (close_time > open_time)` |
| `AvailabilityRule.capacity` | column | Parallel appointments in this window, default `1`, DB `CHECK > 0` |
| `AvailabilityException` | class | `availability_exceptions` — one dated override |
| `AvailabilityException.date` | column | `DATE`; unique per tenant among live rows |
| `AvailabilityException.open_time` / `close_time` | columns | **Both nullable** — the three-valued encoding below |
| `AvailabilityException.note` | column | Free-text reason shown to the owner |

## Behavior

An exception's two nullable times encode the override in a single row with no discriminator column: **both NULL = closed all day**, **both set = special hours for that date**, and **exactly one set is rejected** by `validate_exception_times` in [[backend/app/boutique/validation.py]] — there is no DB `CHECK` for that third case, so that function is the only guard and dropping it would let a half-configured date reach the slot engine. Because `idx_availability_exceptions_tenant_date_unique` is partial (`WHERE deleted_at IS NULL`), one date carries at most one live exception; a single window per exception date is a documented v1 limitation, not an oversight. Weekly rules have no such uniqueness — multiple windows per weekday are expected (morning and evening), and **non-overlap within a day is enforced by `validate_weekly_rules` in [[backend/app/boutique/validation.py]], not by the database** — touching windows (`close == next open`) are allowed, true overlap is not — which makes it the invariant most at risk from a write path that skips the router.

`capacity` on the rule is what makes a window hold more than one bride at a time, and it is the number the booking claim converts into `seat_index` (see [[backend/app/models/booking.py]] and the `idx_bookings_slot_seat_unique` partial unique index). The owner's save path (`replace_weekly_rules`) is an *atomic replace* of the whole weekly set under a per-tenant serialization lock rather than a per-row edit, which soft-deletes the previous generation; those tombstones accumulate on a table the slot engine scans on every computation, which is exactly why [[backend/migrations/versions/0005_boutique_settings.py]] adds `idx_availability_rules_tenant_active … WHERE deleted_at IS NULL`.

## Depends On

- [[backend/app/models/base.py]] — `Base`, `StandardColumns`
- [[SQLAlchemy]]

## Depended On By

- [[backend/app/db/repositories/availability.py]] — the repository for both tables
- [[backend/app/booking/slots.py]] — the slot engine; the primary consumer
- [[backend/app/boutique/service.py]] — owner CRUD, atomic weekly replace, overlap validation
- [[backend/app/storefront/service.py]] — public availability rendering

## Concepts

- [[Row Level Security]]
- [[Tenant Isolation]]

## Tests

- [[backend/tests/test_boutique_models.py]] — `test_availability_rule_shape`, `test_availability_exception_shape` (the latter asserts both times are nullable, i.e. the encoding above)
- [[backend/tests/test_slot_engine.py]] — grid + exception interaction, capacity
- [[backend/tests/test_boutique_api.py]], [[backend/tests/test_storefront_api.py]], [[backend/tests/test_storefront_validation.py]]

## Notes

`day_of_week` numbering is the one thing to check before writing any date arithmetic against this table: Python's `date.weekday()` is Monday-0 and `isoweekday()` is Monday-1, so neither matches directly. DDL: [[backend/migrations/versions/0005_boutique_settings.py]]. Design context: [[.planning/specs/availability-slot-engine.md]].
