---
tags: [backend, db, python, booking, customers, repositories, soft-delete]
sources: [backend/app/db/repositories/customers.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/db/repositories/customers.py
blob: 54844b69cd1dc55660509fc41eb13c6fd6524537
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/db/repositories/customers.py

**Role.** Reads and writes `customers`, whose identity within a tenant is the **phone number** — an attach-or-insert `upsert` keyed on `(tenant, phone)` for the booking flow, a bulk `by_ids` for the owner day list, and a separate `set_phone` writer for the owner's phone correction.

**Module.** [[backend/app/db/repositories/_index]] · **Layer.** db

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `CustomersRepository` | class | Stateless; `AsyncSession` passed per call |
| `by_phone` | method | The live customer holding this number, or `None` |
| `by_id` | method | One live customer |
| `by_ids` | method | Bulk fetch; empty input short-circuits without a round trip |
| `set_phone` | method | Rewrites the number on an existing row; `None` if no live row by that id |
| `upsert` | method | Attach-or-insert by `(tenant, phone)`, updating `name` on a return visit |

## Behavior

`upsert` reads by phone, updates `name` if a row exists, otherwise inserts. Updating the name rather than ignoring it is deliberate: she typed it on this booking, so it is the most recent thing she calls herself. It is safe without a lock of its own because every caller already holds the per-tenant advisory lock for the slot claim, and `idx_customers_tenant_phone_unique` (partial over live rows, migration [[backend/migrations/versions/0008_bookings.py]]) is the backstop either way. Because that index is partial on `deleted_at IS NULL`, a soft-deleted customer does not block a returning one from re-registering the same number — a behavior the tests pin explicitly.

`set_phone` is a separate writer and must not be replaced by `upsert`: `upsert` keys on phone, so calling it with a *corrected* number would create a second customer and leave the booking pointing at the first. It is one guarded `UPDATE … RETURNING id`; `None` means no live row by that id. If the corrected number already belongs to another live customer of the tenant, the unique index refuses and this raises — the service never reaches that, because it pre-checks and instead re-points `bookings.customer_id` at the existing row via [[backend/app/db/repositories/bookings.py#set_customer_id]]. The reasoning is that the number *identifies a person* and that person already has a record; both customer rows survive, since the original may be a real other person and soft-deleting on a guess is worse than leaving a row nobody looks at.

`by_ids` short-circuits on an empty sequence because `IN ()` is a syntax error in Postgres and SQLAlchemy's empty-IN rewrite would be a needless round trip. Note it returns `list(...scalars())` rather than `.scalars().all()` — equivalent here, but the only method in the file that spells it that way.

All statements carry `tenant_id` and `deleted_at IS NULL`. The tenant predicate is redundant with FORCE RLS and kept as defense-in-depth, which is what makes the same phone number under two tenants two independent customers.

## Depends On

- [[backend/app/models/customer.py]] — the ORM model
- [[SQLAlchemy]] — `select`, `update`, `AsyncSession`

## Depended On By

- [[backend/app/booking/service.py]] — `upsert` during the public create
- [[backend/app/booking/owner.py]] — `set_phone`, `by_id`, `by_ids` for the day list and the phone-correction remedy
- [[backend/app/booking/comms.py]] — the recipient number read at SMS send time

## Concepts

- [[Row Level Security]]
- [[Tenant Isolation]]
- [[Partial Unique Index]]
- [[Soft Delete]]

## Tests

- [[backend/tests/test_booking_repositories.py]] — `test_customer_upsert_attaches_and_updates_name`, `test_soft_deleted_customer_does_not_block_return`, `test_set_phone_rewrites_the_number_and_the_index_is_the_backstop`, `test_set_customer_id_onto_a_customer_who_holds_the_instant_raises`
- [[backend/tests/test_booking_isolation.py]] — `test_same_phone_under_two_tenants_is_two_customers`
- [[backend/tests/test_booking_owner_db.py]] · [[backend/tests/test_booking_owner_service.py]] · [[backend/tests/test_booking_service.py]]

## Notes

`customers.phone` is the identity every future SMS reads at send time, which is why a correction has to re-mint every still-live manage token — see [[backend/app/db/repositories/bookings.py#list_live_for_customer]].
