---
tags: [backend, models, db, booking, concurrency, snapshot, python, core]
sources: [backend/app/models/booking.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/models/booking.py
blob: 6e110a274bad9e138dccd4e2061c8e14dcccbc8e
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/models/booking.py

**Role.** The `bookings` table: one appointment at one start time, holding a numbered seat in that instant, carrying frozen snapshots of what the customer agreed to, the terms version she accepted, the hash of her tokenized manage link, and the cancellation evidence E4's refund math will read.

**Module.** [[backend/app/models/_index]] · **Layer.** models

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `Booking` | class | `StandardColumns, Base` → `bookings` |
| `tenant_id`, `customer_id`, `appointment_type_id` | columns | Owning tenant and the two referenced rows (ids only — no FK constraints anywhere) |
| `starts_at` | column | `TIMESTAMPTZ` — **the slot**. There is no end time |
| `seat_index` | column | 1-based position within the window's capacity; DB `CHECK 1..1000` |
| `status` | column | [[backend/app/models/constants.py#BookingStatus]], default `'confirmed'`, DB-pinned set |
| `attendance_confirmed_at` | column | Set by the reminder link's "confirm" action; rendered in the owner console |
| `terms_version_accepted` / `terms_accepted_at` | columns | Pointer into the append-only `terms_versions` table + the instant of acceptance; both NOT NULL |
| `appointment_type_name`, `dress_id`, `dress_name`, `dress_size` | columns | **Snapshots** plus the live `dress_id` for image resolution |
| `notes` | column | Free text from the customer |
| `manage_token_hash` | column | sha256 of the tokenized `/b/{token}` manage link; NULL only on pre-backfill rows |
| `cancelled_at` / `cancelled_by` | columns | Cancel evidence; `cancelled_by` is `customer` \| `owner`, DB-pinned |

## Behavior

**A booking has no end.** The slot model is a start time, and `duration_minutes` on the appointment type is information the boutique acts on rather than geometry the engine reasons about — which is why changing a type's duration never invalidates an existing booking. Overselling is made impossible structurally rather than by counting carefully: `idx_bookings_slot_seat_unique` is a partial unique index on `(tenant_id, starts_at, seat_index) WHERE deleted_at IS NULL AND status <> 'cancelled'`, and the service claims `seat_index = booked + 1` under a per-tenant advisory lock, so a lost race surfaces as an `IntegrityError` instead of a second bride in the same chair. The predicate is `status <> 'cancelled'` and *not* `= 'confirmed'` on purpose: a `no_show` or `completed` booking still occupied its seat, only a cancellation frees it — which is also what keeps the index correct when E4 adds `pending_payment` (a held seat is an occupied seat, so E4 widens the `CHECK` and leaves the index alone). [[backend/migrations/versions/0009_booking_idempotency.py]] adds a second partial unique index over `(tenant_id, customer_id, starts_at)` with the **identical** predicate: it converges the lost-201 retry onto the existing row, and independently states that one person cannot be at two appointments at one instant.

The `*_name` / `dress_*` columns are **snapshots, not denormalization for speed**: an owner may rename an appointment type or archive a dress, and the booking must still render as what the customer agreed to. `dress_id` is kept alongside the snapshot so the image resolves at read time — a storage key would duplicate the media lifecycle and a presigned URL would store something that expires. `terms_version_accepted` is the same idea taken further: an integer pointer into an append-only, `UPDATE`/`DELETE`-revoked table is permanent evidence at a fraction of the size of a text copy.

**The raw manage token never lands in this row.** Only its sha256 does; the raw token rides the SMS body and, while a reminder is pending, the `scheduled_messages` row — so a database read cannot mint a working link. `manage_token_hash` is nullable purely because rows predating that feature exist until the backfill in [[backend/app/booking/backfill.py]] reaches them, and it is indexed as `(tenant_id, manage_token_hash)`. `cancelled_at` + `cancelled_by` are evidence rather than state: `status` already says cancelled, and these say *when* and *by whom*, which is what E4 needs alongside `starts_at` and the accepted terms version to decide refund-due versus forfeit.

## Depends On

- [[backend/app/models/base.py]] — `Base`, `StandardColumns`
- [[SQLAlchemy]]

## Depended On By

- [[backend/app/db/repositories/bookings.py]] — the seat claim, occupancy counts, status transitions
- [[backend/app/booking/service.py]] — creation, the advisory lock, idempotent retry convergence
- [[backend/app/booking/manage.py]] — the customer-facing `/b/{token}` lookup, confirm and cancel
- [[backend/app/booking/owner.py]], [[backend/app/booking/owner_router.py]] — the owner console
- [[backend/app/booking/comms.py]] — confirmation, reminder and owner-action SMS bodies

## Concepts

- [[Row Level Security]]
- [[Tenant Isolation]]

## Tests

- [[backend/tests/test_booking_repositories.py]] — seat claim and both partial unique indexes against real Postgres
- [[backend/tests/test_booking_service.py]] — capacity, races, idempotent retry
- [[backend/tests/test_booking_api.py]], [[backend/tests/test_booking_manage_api.py]], [[backend/tests/test_booking_owner_api.py]]
- [[backend/tests/test_booking_owner_db.py]], [[backend/tests/test_booking_owner_service.py]], [[backend/tests/test_booking_isolation.py]]

## Notes

Money never appears on this row — deposits live on the appointment type until E4. DDL and the full argument for each index: [[backend/migrations/versions/0008_bookings.py]], [[backend/migrations/versions/0009_booking_idempotency.py]], [[backend/migrations/versions/0010_booking_comms.py]]. Design context: [[.planning/specs/booking-core.md]], [[.planning/specs/booking-comms.md]], [[.planning/specs/owner-booking-management.md]].
