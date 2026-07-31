---
tags: [backend, db, concurrency, postgres, booking]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: active
---

# Advisory Lock

**What it is.** `SELECT pg_advisory_xact_lock(hashtext(<key>))` executed as the first statement
inside a `tenant_session`, to serialize a read-then-write sequence that no constraint can
express. The lock releases with the transaction — there is no unlock call anywhere in the tree.

## Why it exists here

Postgres runs READ COMMITTED. Two concurrent transactions each read a count or a set, each
decides, and neither sees the other's uncommitted write. Every place in this repo that computes
a value *from a query* and then writes it needs serialization, and the [[Partial Unique Index]]
alone is not enough: an index makes a lost race an `IntegrityError`, but the point of the lock is
that the race does not happen, so honest callers never see a spurious 409.

**The index is the backstop. The lock is the control.** Both statements appear verbatim in
[[backend/app/db/repositories/bookings.py#insert]] and in 0008/0009's migration comments.

## The four key spaces

| Key | Taken by | Serializes |
|---|---|---|
| `hashtext(tenant_id)` (bare) | [[backend/app/booking/service.py]], [[backend/app/booking/owner.py]], [[backend/app/boutique/service.py#replace_weekly_rules]] | seat claims and the weekly-rules replace for one tenant |
| `hashtext('staff:' \|\| tenant_id)` | [[backend/app/auth/staff.py]] | staff role/deactivation edits |
| `hashtext('dress-media:' \|\| dress_id)` | [[backend/app/catalog/service.py]] | presign, confirm, delete, reorder of one dress's photos |
| `hashtext('dress-variants:' \|\| dress_id)` | [[backend/app/catalog/service.py]] | the size-matrix replace for one dress |

The prefixes are SQL literals and the id is always a bound parameter — never interpolated. The
namespacing is deliberate: reusing the bare tenant key for staff edits would serialize every
staff edit against every public booking create for that boutique.

## Ordering is the correctness argument

In [[backend/app/booking/owner.py#reschedule]] and in [[backend/app/auth/staff.py#update]] the
lock is taken **before any read**, and every value used afterwards comes from the post-lock read.
A read taken above the lock is a stale read, and the guard is then evaluated against a count
another transaction already invalidated. [[backend/tests/test_booking_owner_service.py]] pins
that ordering with a statement trace (`test_the_advisory_lock_is_taken_before_the_booking_is_read`).

[[backend/app/auth/staff.py]] carries the sharpest statement of why: the "at least one live owner"
invariant cannot be an index (an index expresses *at most one*), and a single `UPDATE … WHERE
(SELECT count(*) …) > 1` lets two concurrent demotions both see 2, both pass, and leave the tenant
with zero owners and no error anywhere.

## Writers that deliberately take no lock

- `StaffService.create` — an insert can only *raise* the live-owner count, and a raise never
  invalidates a decision another transaction made under the lock. Recorded as a ruling, not an omission.
- `correct_phone`'s phone-write branch in [[backend/app/booking/owner.py]] — its `by_phone` is a
  pre-check only, so the `IntegrityError` from `idx_customers_tenant_phone_unique` is mapped
  explicitly rather than left to become a bare 500.
- [[backend/app/db/repositories/customers.py#upsert]] — safe without its own lock precisely
  *because* every caller already holds the per-tenant one.

## Gotchas

- **No network I/O under a lock.** [[backend/app/catalog/service.py]] splits presign and confirm
  into explicit steps so no boto3 call (60 s connect + 60 s read defaults) can pin a pool
  connection and a per-dress lock across an S3 stall.
- One lock per tenant serializes *all* claims for that boutique — marked `ponytail:` in
  [[backend/app/booking/service.py]] with per-slot keys as the upgrade path if throughput ever cares.

## Related

- [[Partial Unique Index]] · [[Tenant Context]] · [[Repository Pattern]]
- Proven under real concurrency in [[backend/tests/test_booking_service.py]],
  [[backend/tests/test_booking_owner_db.py]], [[backend/tests/test_staff_management_db.py]],
  [[backend/tests/test_boutique_service.py]] and [[backend/tests/test_catalog_integration.py]].
