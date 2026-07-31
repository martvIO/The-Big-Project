---
tags: [backend, models, db, booking, customer, otp, python]
sources: [backend/app/models/customer.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/models/customer.py
blob: f608b911a57a318e7ce4d53ec0887e2286501d85
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/models/customer.py

**Role.** The `customers` table: a phone-keyed person record inside one boutique, created only once OTP verification has proved possession of that number.

**Module.** [[backend/app/models/_index]] · **Layer.** models

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `Customer` | class | `StandardColumns, Base` → `customers` |
| `tenant_id` | column | Owning tenant; RLS predicate, and half of the natural key |
| `phone` | column | TEXT, NOT NULL — the identity. Unique per tenant among live rows |
| `name` | column | TEXT, NOT NULL — display name the bride gave at booking time |

## Behavior

Three columns and one index carry the whole model. `idx_customers_tenant_phone_unique` is partial — `(tenant_id, phone) WHERE deleted_at IS NULL` — so a soft-deleted record cannot block the same bride returning, and the tenant prefix means the **same phone under two tenants is two customers, deliberately**: a bride who visits two boutiques is not one cross-tenant identity, and making her one would be an RLS hole dressed up as deduplication. The row is only ever created after OTP verification succeeded, because the entire post-booking flow — confirmation SMS, reminder, the tokenized manage link in [[backend/app/models/booking.py]] — is delivered to this number; an unverified phone would strand a paying customer behind a link that can never arrive.

The phone is mutable, and the writer matters. `CustomersRepository.set_phone` is the owner's phone-correction path and is a plain `UPDATE` by id; `upsert` is *not* usable for it because upsert keys on phone, so calling it with the corrected number would mint a **second** customer and leave the booking pointing at the first. When the corrected number already belongs to another live customer of the tenant the partial unique index refuses and `set_phone` raises — the service never reaches that, because it pre-checks and re-points `bookings.customer_id` at the existing row instead, on the theory that the number identifies the person and that person already has a record. `by_ids` short-circuits on an empty sequence, since `IN ()` is a Postgres syntax error.

## Depends On

- [[backend/app/models/base.py]] — `Base`, `StandardColumns`
- [[SQLAlchemy]]

## Depended On By

- [[backend/app/db/repositories/customers.py]] — `by_phone`, `by_id`, `by_ids`, `set_phone`, upsert
- [[backend/app/booking/owner.py]], [[backend/app/booking/owner_router.py]] — the owner day list's name column and the phone correction

## Concepts

- [[Row Level Security]]
- [[Tenant Isolation]]

## Tests

- [[backend/tests/test_booking_repositories.py]] — upsert and lookup behavior against real Postgres
- [[backend/tests/test_booking_owner_db.py]], [[backend/tests/test_booking_owner_api.py]] — the phone-correction paths including the collision case
- [[backend/tests/test_booking_service.py]] — creation only after verification

## Notes

No email column, by design — SMS is the only channel in E3. DDL and the reasoning behind the per-tenant key: [[backend/migrations/versions/0008_bookings.py]]. Design context: [[.planning/specs/booking-core.md]].
