---
tags: [backend, db, python, booking, boutique, repositories, soft-delete]
sources: [backend/app/db/repositories/appointment_types.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/db/repositories/appointment_types.py
blob: 4977ec2f30675c84a8ed14ae7c525c55e397e462
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/db/repositories/appointment_types.py

**Role.** CRUD over `appointment_types` — the boutique's bookable service menu (name, duration, audience, deposit, display order) — read by both the owner console and the public storefront, and soft-deleted rather than removed so historical bookings keep pointing at a row that still exists.

**Module.** [[backend/app/db/repositories/_index]] · **Layer.** db

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `AppointmentTypesRepository` | class | Stateless; `AsyncSession` passed per call |
| `list_active` | method | Live types ordered by `sort_order` then `created_at` |
| `by_id` | method | One live type, or `None` |
| `insert` | method | Adds a row, flushes, refreshes; returns the persisted model |
| `update_fields` | method | Full-field overwrite of one live type; `None` if it does not exist |
| `soft_delete` | method | Stamps `deleted_at = now()`; `bool` for "did anything change" |

## Behavior

Every statement carries `tenant_id == tenant_id` **and** `deleted_at IS NULL`. The tenant predicate is redundant with FORCE RLS by design (the class docstring says so) — it is defense-in-depth, so a bug that loses the tenant context still cannot widen a query into a cross-tenant read. The `created_at` tiebreak on `list_active` is what stops two types sharing a `sort_order` from swapping places between page loads.

`update_fields` is a read-then-mutate: it reuses `by_id` and returns `None` when nothing live matches, so a caller distinguishes "not found" from "updated" without a second query. The `refresh` after `flush` is not decoration — `updated_at` is maintained by a database trigger, so without the refresh the returned instance would carry a stale timestamp. `insert` does the same for the server-side defaults (`id`, `created_at`).

`soft_delete` is the one guarded by predicate rather than read-then-write: it is a single `UPDATE … RETURNING id`, so a second delete of the same type matches zero rows and returns `False` instead of overwriting the original `deleted_at` with a newer timestamp. Because the row survives, `idx_appointment_types_tenant_name_unique` (a partial index over live rows only, migration [[backend/migrations/versions/0005_boutique_settings.py]]) frees the name for reuse the moment a type is deleted, while a booking's denormalized `appointment_type_name` snapshot keeps the old label.

## Depends On

- [[backend/app/models/appointment_type.py]] — the ORM model
- [[SQLAlchemy]] — `select`, `update`, `func.now`, `AsyncSession`

## Depended On By

- [[backend/app/boutique/service.py]] — the owner console's settings CRUD
- [[backend/app/storefront/service.py]] — the public bookable-services list
- [[backend/app/booking/service.py]] — resolves the requested type and its `duration_minutes` before claiming a slot

## Concepts

- [[Row Level Security]]
- [[Tenant Isolation]]
- [[Soft Delete]]

## Tests

- [[backend/tests/test_boutique_service.py]] — CRUD round-trip and ordering
- [[backend/tests/test_booking_service.py]] — types as the booking flow's input
- [[backend/tests/test_booking_comms_db.py]] · [[backend/tests/test_booking_owner_db.py]] — fixture setup for booking rows
- [[backend/tests/test_storefront_isolation.py]] — types never cross the tenant boundary

## Notes

`audience` and `deposit_*` are stored but the payment path is not built; `deposit_amount_agorot` is an integer in agorot (1/100 ILS), never a float.
