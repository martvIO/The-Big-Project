---
tags: [backend, models, python, booking, notifications, worker, sqlalchemy]
sources: [backend/app/models/scheduled_message.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/models/scheduled_message.py
blob: fad995b4ff029f07377ecbf197dfd6ba4326770b
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/models/scheduled_message.py

**Role.** One future SMS waiting to be sent — the queue the background worker claims from when `send_after` passes, and the only place the raw manage-link token survives between the confirmation text and the reminder.

**Module.** [[backend/app/models/_index]] · **Layer.** models

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `ScheduledMessage` | class | ORM mapping for `scheduled_messages`; `StandardColumns` + `Base` |
| `tenant_id` | col | `UUID NOT NULL` — RLS discriminator |
| `booking_id` | col | `UUID NOT NULL` — no FK; the booking is re-read at claim time anyway |
| `kind` | col | `TEXT NOT NULL`, DB `CHECK (kind IN ('reminder'))` — mirrors `ScheduledMessageKind` |
| `send_after` | col | `TIMESTAMPTZ NOT NULL` — earliest send time, not an exact firing time |
| `status` | col | `TEXT NOT NULL DEFAULT 'pending'`, `CHECK` in `pending`/`sent`/`cancelled`/`failed` |
| `manage_token` | col | `TEXT NULL` — the **raw** link token while pending; cleared on every terminal status |

## Behavior

This table is the **schedule**, never the evidence — [[backend/app/models/message_log.py]] keeps the evidence and [[backend/app/notifications/service.py]] stays its single writer. A row's whole life is `pending` → `sent | failed | cancelled`, and `cancelled` covers two different non-failures: the booking was cancelled, and the claim-time re-check found the appointment already started. Neither is a delivery failure, so neither is `failed`.

Two partial indexes in [[backend/migrations/versions/0010_booking_comms.py]] carry the concurrency invariants. `idx_scheduled_messages_pending_unique` on `(tenant_id, booking_id, kind) WHERE deleted_at IS NULL AND status = 'pending'` is **the** idempotency key: a double-schedule converges on one row instead of sending twice, and the repository lets `flush()` raise `IntegrityError` rather than pre-checking, because a pre-check would be a TOCTOU. Terminal rows are excluded from that index deliberately — a reschedule must be able to leave a `sent` reminder in place and add a fresh pending one for the new time. The second index, `(tenant_id, send_after) WHERE deleted_at IS NULL AND status = 'pending'`, makes the poller's claim one range scan per tenant per tick. `mark()` is additionally guarded on `status = 'pending'`, so a row can only leave pending once — belt to the claim's braces.

`manage_token` storing a raw credential looks wrong until you know why it must: [[backend/app/models/booking.py]] stores only the sha256, the reminder has to carry the **same** link as the confirmation (a fresh token would kill the link in a text the customer is still reading), and the worker sends hours or days later in a different process. Clearing it at every terminal status bounds the window. Because the claim matches `send_after <= now()` rather than an exact time, a missed poll window self-heals on the next tick — which is what lets `worker_poll_interval_seconds` be deploy-tunable.

RLS gets **no exception here**, and that is a recorded decision: the poller stays inside the tenancy posture by enumerating tenants (`tenants` being deliberately RLS-free) and claiming one `tenant_session` at a time, rather than becoming the first cross-tenant reader in the codebase.

## Depends On

- [[backend/app/models/base.py]] — `Base`, `StandardColumns`
- [[SQLAlchemy]] — declarative mapping

## Depended On By

- [[backend/app/db/repositories/scheduled_messages.py]] — `insert`, `pending_for_booking`, `cancel_pending`, `claim_due`, `mark`
- [[backend/app/booking/comms.py]] — schedules the reminder when a booking is confirmed
- [[backend/app/booking/service.py]] — booking creation schedules through the comms layer
- [[backend/app/booking/owner.py]] — owner reschedule / cancel re-points or cancels the pending row
- [[backend/app/booking/manage.py]] — customer cancel cancels the pending row
- [[backend/app/booking/backfill.py]] — the one-time F16 backfill
- [[backend/app/worker.py]] — the poller that claims and sends

## Concepts

- [[Row Level Security]]
- [[Tenant Isolation]]
- [[Tenant Context]]

## Tests

- [[backend/tests/test_booking_comms_db.py]] — scheduling, idempotency index, cancel-pending
- [[backend/tests/test_worker.py]] — claim, send, terminal transition
- [[backend/tests/test_booking_isolation.py]] — cross-tenant reads return nothing
- [[backend/tests/test_booking_owner_db.py]], [[backend/tests/test_booking_owner_service.py]] — reschedule and cancel effects on the pending row
- [[backend/tests/test_booking_reminder_bands.py]] — how `send_after` is chosen

## Notes

`kind` is pinned to a single value on purpose. E4's hold-expiry sweep and E5's offer cascade widen the `CHECK` when they arrive; pre-adding speculative kinds is explicitly rejected in [[backend/app/models/constants.py]].

The `manage_token` column was a spec amendment, recorded in [[.planning/specs/booking-comms.md]]. Design context also: [[.planning/plans/booking-comms.md]], [[.planning/specs/owner-booking-management.md]].
