---
tags: [backend, models, db, boutique, booking, python]
sources: [backend/app/models/appointment_type.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/models/appointment_type.py
blob: 26be408c7bab3fbc4393e8573991280afc01f41b
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/models/appointment_type.py

**Role.** The `appointment_types` table: the per-tenant menu of bookable services (name, duration, audience, optional deposit, display order) that the storefront lists and every booking snapshots.

**Module.** [[backend/app/models/_index]] · **Layer.** models

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `AppointmentType` | class | `StandardColumns, Base` → `appointment_types` |
| `tenant_id` | column | Owning tenant; the RLS policy predicate and the leading key of every index |
| `name` | column | Hebrew display name; unique per tenant **among live rows only** |
| `duration_minutes` | column | Informational for the boutique, not slot geometry (DB `CHECK > 0`) |
| `audience` | column | `all` \| `brides_only` ([[backend/app/models/constants.py#AppointmentAudience]]), default `'all'` |
| `deposit_required` / `deposit_amount_agorot` | columns | E4 deposit policy; money in **agorot as INTEGER**, never float. Amount nullable, `CHECK` NULL-or-positive |
| `sort_order` | column | Owner-controlled display order, default `0` |

## Behavior

Soft delete means *archive*, and the DDL is what makes that true rather than a convention: `idx_appointment_types_tenant_name_unique` is a **partial** unique index over `(tenant_id, name) WHERE deleted_at IS NULL`, so archiving a type releases its name for reuse while the archived row stays readable forever. That matters because bookings reference a type by id *and* keep an `appointment_type_name` snapshot ([[backend/app/models/booking.py]]) — archiving or renaming a type therefore cannot rewrite history the customer agreed to, and no cascade or restore-blocking logic is needed. `duration_minutes` is deliberately **not** slot geometry: the slot engine reasons about start times only, so a duration change never invalidates an existing booking (see [[backend/app/booking/slots.py]]). The `audience` value is one of two gates that hide a type from a non-bride storefront visitor; the other is a tenant-wide `brides_only` toggle. The two numeric `CHECK`s (`duration_minutes > 0`, `deposit_amount_agorot IS NULL OR > 0`) live in [[backend/migrations/versions/0005_boutique_settings.py]] rather than only in the service, because these bounds feed E4's refund arithmetic and financial evidence must hold against any write path that skips the router.

There is no `Mapped` relationship to `Booking` or to any other model anywhere in this package — the house convention is no foreign keys and no ORM relationships; joins are written explicitly in repositories.

## Depends On

- [[backend/app/models/base.py]] — `Base`, `StandardColumns`
- [[backend/app/models/constants.py]] — `AppointmentAudience`, interpolated into the `audience` server default
- [[SQLAlchemy]]

## Depended On By

- [[backend/app/db/repositories/appointment_types.py]] — the only repository over this table
- [[backend/app/boutique/service.py]] — owner CRUD and archive
- [[backend/app/storefront/router.py]], [[backend/app/storefront/service.py]] — public listing, audience filtering

## Concepts

- [[Row Level Security]] — the table is under FORCE RLS keyed on `tenant_id`
- [[Tenant Isolation]]

## Tests

- [[backend/tests/test_boutique_models.py]] — `test_appointment_type_shape`, `test_all_new_tables_carry_standard_columns`
- [[backend/tests/test_boutique_api.py]], [[backend/tests/test_boutique_service.py]], [[backend/tests/test_boutique_integration.py]]
- [[backend/tests/test_storefront_api.py]] — audience gating on the public read path
- [[backend/tests/test_booking_service.py]] — the type a booking snapshots

## Notes

DDL, indexes and grants: [[backend/migrations/versions/0005_boutique_settings.py]]. Design context: [[.planning/specs/owner-settings.md]].
