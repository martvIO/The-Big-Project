---
tags: [backend, db, postgres, concurrency, schema]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: active
---

# Partial Unique Index

**What it is.** `CREATE UNIQUE INDEX … WHERE <predicate>` — this repo's concurrency primitive and
the reason [[Soft Delete]] does not leak into uniqueness. Almost every uniqueness rule in the
schema is partial, and the predicate is always some form of "the row is still live".

## The two that carry the booking feature

Both live on `bookings`, both share the identical predicate
`WHERE deleted_at IS NULL AND status <> 'cancelled'`:

- `idx_bookings_slot_seat_unique` on `(tenant_id, starts_at, seat_index)` —
  [[backend/migrations/versions/0008_bookings.py]]. THE oversell guard, structural at *any*
  capacity, which a plain unique on `(tenant_id, starts_at)` would not be.
- `idx_bookings_tenant_customer_starts_unique` on `(tenant_id, customer_id, starts_at)` —
  [[backend/migrations/versions/0009_booking_idempotency.py]]. The backstop for the lost-201
  retry, and independently a statement that one person cannot be at two appointments at once.

**`status <> 'cancelled'`, not `= 'confirmed'`.** A no-show or a completed booking still *occupied*
its seat; only a cancellation releases it. That single choice is what makes cancelling a booking
structurally free its seat and lets the same customer rebook the same instant — no compensating
UPDATE anywhere. It is also why E4's future `pending_payment` status widens the `CHECK` and leaves
both indexes alone: a held seat is an occupied seat.

## What nothing in the database enforces

**Nothing ties `seat_index` to its slot's capacity.** 0008's `CHECK` is `1..1000`, flat. Seat 3
carried into a capacity-1 slot satisfies both the CHECK and the unique index and is a silent
oversell. Capacity is computed in Python — `offered_slot` plus the lowest-free-seat scan in
[[backend/app/booking/service.py]] and [[backend/app/booking/owner.py#reschedule]] — and nowhere
else. Any new writer of `bookings` must pick the lowest free seat at the *target* instant, never
carry the old one.

## The rest of the schema

`idx_tenants_slug_unique` ([[backend/migrations/versions/0002_tenants_app_role.py]]) makes a
soft-deleted slug reclaimable. `idx_staff_users_tenant_email_unique`
([[backend/migrations/versions/0003_auth.py]]), `idx_appointment_types_tenant_name_unique` and
`idx_availability_exceptions_tenant_date_unique`
([[backend/migrations/versions/0005_boutique_settings.py]]),
`idx_dress_variants_dress_size_unique` on `lower(size_label)`
([[backend/migrations/versions/0006_catalog.py]]) and
`idx_customers_tenant_phone_unique` ([[backend/migrations/versions/0008_bookings.py]]) all follow
the same shape.

Two are deliberately **plain**, and both say so in a comment: `idx_terms_versions_tenant_version_unique`
(nothing is ever deleted from that table — see [[Append Only Terms Versions]]) and
`idx_dress_media_storage_key_unique` (a regression guard on `build_media_key` in
[[backend/app/catalog/keys.py]], nothing more).

## Gotchas

- **Never pre-check instead of catching.** [[backend/app/db/repositories/bookings.py#insert]]
  refuses to pre-check the seat index: the index is the truth and a pre-check is a TOCTOU. Services
  catch `IntegrityError` and map it — `SLOT_UNAVAILABLE`, `CUSTOMER_ALREADY_BOOKED`,
  `DuplicateEmailError`, `DuplicateSizeError`. An unmapped one is a bare 500.
- The case-insensitive variant index means the booking service must match sizes case-insensitively
  too; [[backend/app/booking/service.py]] does, and snapshots the *boutique's* spelling.
- A flush that violates one of these aborts the whole Postgres transaction. Recovering in place
  would need a `SAVEPOINT`, which is exactly why the idempotency path in
  [[backend/app/booking/service.py]] reads under the [[Advisory Lock]] rather than catching.

## Related

- [[Advisory Lock]] · [[Soft Delete]] · [[Database Migrations]] · [[Row Level Security]]
