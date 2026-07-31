---
tags: [backend, db, python, booking, availability, storefront, repositories, soft-delete]
sources: [backend/app/db/repositories/availability.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/db/repositories/availability.py
blob: 6178bf95b9bbcc0b24f8f7924b0fb4fcd4f7e2f5
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/db/repositories/availability.py

**Role.** The two repositories the slot engine reads from: `AvailabilityRulesRepository` over the boutique's recurring weekly opening hours and seat capacity, and `AvailabilityExceptionsRepository` over the dated overrides (holiday closures and one-off hours) that override them.

**Module.** [[backend/app/db/repositories/_index]] · **Layer.** db

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `AvailabilityRulesRepository` | class | The recurring weekly grid |
| `AvailabilityRulesRepository.list_active` | method | Live rules ordered by `day_of_week`, then `open_time` |
| `AvailabilityRulesRepository.insert` | method | One rule (day, open, close, capacity) |
| `AvailabilityRulesRepository.soft_delete_all` | method | Retires the entire live weekly set; returns how many rows it stamped |
| `AvailabilityExceptionsRepository` | class | Dated overrides |
| `AvailabilityExceptionsRepository.list_active` | method | Live exceptions, optionally bounded by `on_or_after` / `on_or_before`, ordered by date |
| `AvailabilityExceptionsRepository.insert` | method | One exception; `open_time`/`close_time` both `None` means a full closure |
| `AvailabilityExceptionsRepository.soft_delete` | method | Stamps one exception; `bool` |

## Behavior

`soft_delete_all` is the half of the weekly-schedule write that makes the replace atomic: the owner console does not patch individual rules, it retires the whole live set and re-inserts the new one inside a single transaction, **while holding the per-tenant advisory lock** (see the method docstring and [[backend/app/boutique/service.py]]). Without the lock two concurrent saves could interleave delete-then-insert and leave a boutique with a half-merged week; without the single transaction a crash between the two halves would leave it with no opening hours at all. It returns a count rather than a bool because the caller reports how many rules were replaced.

`AvailabilityExceptionsRepository.list_active` takes both date bounds as optional keyword arguments and applies them **in SQL**, not in the caller. The reason is stated in its docstring and worth respecting: the storefront asks for a bounded window, and a boutique with three years of recorded holidays would otherwise ship three years of rows to an anonymous request just to have Python discard them. Both bounds defaulting to `None` keeps the manage-side caller unchanged — the owner's console genuinely wants the full history, past dates included. The comparison is on `date`, so `on_or_before` is inclusive; contrast the booking repository's half-open instant windows.

Both classes filter on `tenant_id` and `deleted_at IS NULL` on every statement. The tenant predicate is redundant with FORCE RLS and kept as defense-in-depth. Soft delete is what lets `idx_availability_exceptions_tenant_date_unique` (partial over live rows, migration [[backend/migrations/versions/0005_boutique_settings.py]]) free a date for a new exception while the old row stays for audit. `AvailabilityRulesRepository` has no `by_id` and no update path at all — the replace-the-set model means individual rules are never addressed by id.

## Depends On

- [[backend/app/models/availability.py]] — `AvailabilityRule`, `AvailabilityException`
- [[SQLAlchemy]] — `select`, `update`, `func.now`, `AsyncSession`

## Depended On By

- [[backend/app/boutique/service.py]] — the owner console's schedule editor (the atomic replace)
- [[backend/app/booking/slots_io.py]] — loads rules + exceptions to feed the pure slot engine
- [[backend/app/booking/service.py]] — validates a requested slot against the grid
- [[backend/app/booking/owner.py]] — the owner-side reschedule offers slots from the same grid
- [[backend/app/storefront/service.py]] — the public availability calendar

## Concepts

- [[Row Level Security]]
- [[Tenant Isolation]]
- [[Soft Delete]]

## Tests

- [[backend/tests/test_booking_service.py]] — rules as slot-engine input
- [[backend/tests/test_storefront_isolation.py]] — `test_slots_and_types_never_cross_the_tenant_boundary`
- [[backend/tests/test_booking_comms_db.py]] · [[backend/tests/test_booking_owner_db.py]] — fixture schedules
- [[backend/tests/test_slot_engine.py]] — the pure engine these rows feed

## Notes

`capacity` on a rule is the seat count the slot/seat unique index in [[backend/migrations/versions/0008_bookings.py]] is checked against; the repository does not enforce it, the claim in [[backend/app/booking/service.py]] does.
