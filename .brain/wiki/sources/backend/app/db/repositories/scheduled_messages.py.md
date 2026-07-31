---
tags: [backend, db, repository, booking, scheduled-messages, worker, queue, python, sqlalchemy]
sources: [backend/app/db/repositories/scheduled_messages.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/db/repositories/scheduled_messages.py
blob: 91fccc0d1458cb1382b2d41c80c706ba2ad23d20
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/db/repositories/scheduled_messages.py

**Role.** The reminder queue's data layer: enqueue a pending message whose uniqueness the DB enforces, cancel a booking's pending messages, claim due rows with `FOR UPDATE SKIP LOCKED` for the poller, and mark a claimed row terminal — clearing the raw manage token on the way out.

**Module.** [[backend/app/db/repositories/_index]] · **Layer.** db

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `ScheduledMessagesRepository` | class | The repository; explicit `AsyncSession` + `tenant_id` on every method |
| `insert` | method | Enqueue a `pending` row; relies on the partial unique index to reject a duplicate |
| `pending_for_booking` | method | The at-most-one pending row for `(booking_id, kind)` |
| `cancel_pending` | method | Flip every pending row of a kind to `cancelled`, drop its token, return the count |
| `claim_due` | method | Lock and return up to `limit` due pending rows for one tenant |
| `mark` | method | Terminal transition guarded on `status = 'pending'`; returns the refreshed row or `None` |
| `_by_id` | method | Private live-row re-read used by `mark` |

## Behavior

The queue's idempotency key is not code, it is `idx_scheduled_messages_pending_unique` — a partial unique index on `(tenant_id, booking_id, kind) WHERE deleted_at IS NULL AND status = 'pending'`. `insert` deliberately does **not** pre-check for an existing pending row: a pre-check would be a TOCTOU, so the `flush()` is what surfaces the `IntegrityError` and a double-schedule converges on one row instead of sending twice. The index excludes terminal rows on purpose, which is what lets a reschedule leave a `sent` reminder in place and enqueue a fresh pending one for the new time. `claim_due` selects pending rows with `send_after <= now` ordered oldest-first `WITH FOR UPDATE SKIP LOCKED`, so a second worker replica skips locked rows rather than blocking on them or re-sending them; the lock is held for the caller's whole transaction, which by design spans the provider call — the accepted trade is at-least-once redelivery (a crash before `mark` leaves the row pending) rather than possible loss, with claim-commit-then-send behind a `sending` status as the documented upgrade path. Because the claim matches on `send_after <= now` rather than an exact time, a missed poll tick self-heals. Both terminal paths (`cancel_pending`, `mark`) set `manage_token = None`: the raw link token is retained only while a pending row still has to reproduce the link the confirmation SMS already sent. `mark`'s `status = 'pending'` guard is belt to the claim's braces — a row can leave pending exactly once. Both counted methods use `RETURNING id` instead of `rowcount`, since the async `Result` is not typed with one.

## Depends On

- [[backend/app/models/scheduled_message.py]] — the `ScheduledMessage` ORM entity
- [[backend/app/models/constants.py]] — `ScheduledMessageStatus`
- [[SQLAlchemy]] — `select` / `update`, `with_for_update`, `AsyncSession`

## Depended On By

- [[backend/app/booking/comms.py]] — enqueues confirmation/reminder messages and drains claimed rows
- [[backend/app/booking/service.py]] — schedules on booking creation
- [[backend/app/booking/manage.py]] — customer-side cancel/reschedule re-queues
- [[backend/app/booking/owner.py]] — owner-side resend, phone correction, reschedule, cancel
- [[backend/app/booking/backfill.py]] — backfills queue rows for bookings created before the queue existed

## Concepts

- [[Row Level Security]]
- [[Tenant Isolation]]
- [[Partial Unique Index]]

## Tests

- [[backend/tests/test_booking_comms_db.py]]
- [[backend/tests/test_booking_isolation.py]]
- [[backend/tests/test_booking_owner_db.py]]
- [[backend/tests/test_booking_owner_service.py]]
- [[backend/tests/test_worker.py]]

## Notes

`claim_due` is tenant-scoped, so the poller in [[backend/app/worker.py]] enumerates tenants from [[backend/app/db/repositories/tenants.py]] and claims per tenant — that is how a background job stays inside the RLS posture instead of needing a cross-tenant read. The second index, `idx_scheduled_messages_due`, is what makes that one range scan per tenant per tick. See [[backend/migrations/versions/0010_booking_comms.py]] for both index definitions.
