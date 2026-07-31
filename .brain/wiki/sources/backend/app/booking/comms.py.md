---
tags: [backend, booking, python, sms, scheduling, worker, poller, transactions]
sources: [backend/app/booking/comms.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/booking/comms.py
blob: 141d8f651f366bf9a73bf0c6bbd93ee479d31793
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/booking/comms.py

**Role.** The booking lifecycle's SMS orchestration: when a reminder is scheduled (three bands), how a due batch is claimed and drained by the worker, how the four bodies are delivered through the single `message_log` writer, and what happens when the provider is absent or refuses.

**Module.** [[backend/app/booking/_index]] · **Layer.** worker

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `reminder_send_after` | fn | Pure: `starts_at` + `now` → the reminder's `send_after`, or `None` for no reminder |
| `upsert_reminder` | async fn | Module-level, takes a session: cancel any pending row, then create a fresh one from the new `starts_at` |
| `BookingCommsService.send_confirmation` | async method | Post-commit confirmation for a booking that was actually created |
| `BookingCommsService.notify_owner_cancel` | async method | Owner-cancel notice |
| `BookingCommsService.notify_owner_reschedule` | async method | Reschedule notice; reads the live token off the pending reminder, rotating if there is none |
| `BookingCommsService.reissue_manage_token` | async method | Rotate + re-point + resend across its own transaction — a tested seam with no caller |
| `BookingCommsService.reschedule_reminder` | async method | `upsert_reminder` wrapped in its own `tenant_session` |
| `BookingCommsService.drain_due` | async method | Claim and send one tenant's due reminders for one tick |
| `BookingCommsService.link_for` | method | The manage URL for a token |
| `CommsTenant` | frozen dataclass | `id`, `slug`, `name`, `phone`; `from_settings` classmethod |
| `DrainResult` | frozen dataclass | `sent` / `failed` / `cancelled` / `deferred` for one tenant, one tick |
| `REMINDER_LEAD_SECONDS` · `REMINDER_SUPPRESS_UNDER_SECONDS` · `DRAIN_BATCH_SIZE` | const | 86 400 · 7 200 · 50 |

## Behavior

Every send goes through `NotificationService.send_sms`, which stays the single writer of `message_log` — nothing here touches that table. Templates stay pure in [[backend/app/booking/comms_templates.py]]; this module owns the orchestration, the schedule and the failure semantics.

**The two failure modes are handled differently, and the split is not cosmetic.** `SmsSendError` means a configured provider refused: the `failed` `message_log` row already exists, so the error is swallowed and the evidence *is* the record. `SmsNotConfiguredError` is raised *before* any insert, so it leaves no row at all — which is why every send path checks `is_configured` up front and skips with one app-log warning instead. That warning is the only observable trace of a skipped lifecycle send before a provider exists. Either way the booking stands: a 201 is a 201 whether or not the text went out, and propagating a send failure would turn a committed booking into a 503.

`reminder_send_after` encodes three bands: ≥24 h out → `starts_at − 24 h`; 2–24 h → now, immediately, because she still gets the confirm-attendance ask; under 2 h → `None`, because the confirmation is seconds old and a second message is noise. The arithmetic is on **UTC instants** deliberately — "24 hours before" is 86 400 real seconds, and across an Israeli DST boundary that is 23 or 25 local wall-clock hours. Since every body renders from `starts_at`, a reminder that lands early or late still states the true local time.

`upsert_reminder` is an **upsert, never a re-target**, and that distinction is the whole point: it cancels any pending row and then creates a fresh one from the new `starts_at` under the bands *including* the under-2 h suppression, regardless of whether the prior row was sent, cancelled or never existed. A day-of reschedule is the common case and its old reminder has already fired, so "update the pending row" would be a silent no-op that ships green-tested. It reads the pending row's raw token **before** cancelling (cancel clears it) and carries it forward; only when there is nothing to inherit from does it mint a new token and rotate the booking's hash, because sha256 is one-way. It takes a session rather than opening one so a caller already inside a transaction can make the reminder rewrite part of it — the owner reschedule needs exactly that, since post-commit a crash loses or mis-schedules the reminder with nothing sweeping for it, and `drain_due` could claim the stale pending row and clear its token in the window.

`drain_due` runs one `tenant_session` per tenant per tick, keeping the poller inside the RLS posture rather than taking an exemption. The ordering inside its loop is load-bearing. First it **re-reads the booking**: cancelled, missing or already started flips the scheduled row to `cancelled` and sends nothing — the defence against races the schedule-time bands cannot see, and also what stops a pre-provider backlog from growing without bound. Second, an unconfigured provider leaves the remaining rows **pending** and breaks out, counting them as `deferred`: marking them `failed` would be a lie with no evidence row behind it, and leaving them pending is what makes the backlog flush itself on the first tick after an adapter lands. Third, a row with no token or an unreachable customer is marked `failed` rather than retried, because neither condition heals on its own and the owner console's resend is the remedy surface. The batch is bounded so a post-deploy backlog drains over several ticks instead of holding one transaction — and one row's lock — for minutes.

`notify_owner_reschedule` reads the **live** token off the pending reminder rather than being handed one, so the SMS carries the same link the future reminder will send; if there is no pending reminder there is no recoverable link, so it rotates. `reissue_manage_token` bundles mint + rotate + re-point + send across a `tenant_session` of its own and is deliberately **uncalled**: the owner console needs the mint-rotate-repoint half inside *its* transaction, so it does that itself and calls the public `send_confirmation` post-commit with the token it already minted.

`_deliver` passes `log_body` as the **masked** body whenever a token is involved, so the raw token never lands in `message_log` beside its own hash on `bookings`.

## Depends On

- [[backend/app/booking/comms_templates.py]] — the four bodies, `manage_link`, `mask_manage_link`
- [[backend/app/booking/tokens.py]] — mint and hash on the rotation paths
- [[backend/app/notifications/service.py]] — `NotificationService`, `WallClock`
- [[backend/app/notifications/base.py]] — `SmsSendError`, `SmsNotConfiguredError`
- [[backend/app/db/tenant.py]] — `tenant_session`
- [[backend/app/db/repositories/bookings.py]] · [[backend/app/db/repositories/customers.py]] · [[backend/app/db/repositories/scheduled_messages.py]]
- [[backend/app/models/booking.py]] · [[backend/app/models/constants.py]]
- [[backend/app/storefront/validation.py]] — `profile_text`

## Depended On By

- [[backend/app/booking/service.py]] — `reminder_send_after` for the claim's in-transaction reminder row
- [[backend/app/booking/router.py]] — post-commit `send_confirmation`
- [[backend/app/booking/owner.py]] — `upsert_reminder` inside the reschedule transaction; holds the service for the owner seams
- [[backend/app/booking/owner_router.py]] — post-commit `notify_owner_cancel`, `notify_owner_reschedule`, `send_confirmation`
- [[backend/app/booking/backfill.py]] — `reminder_send_after`
- [[backend/app/worker.py]] — `drain_due` per tenant per tick; `CommsTenant`, `DrainResult`
- [[backend/app/main.py]] — constructs the service

## Concepts

- [[Row Level Security]]
- [[Tenant Context]]
- [[Tenant Isolation]]

## Tests

- [[backend/tests/test_booking_reminder_bands.py]] — the three bands and the upsert semantics
- [[backend/tests/test_booking_comms_db.py]] — sends, rotation, masking and `drain_due` against real rows
- [[backend/tests/test_worker.py]] — the poller loop driving `drain_due`
- [[backend/tests/test_booking_isolation.py]] — `scheduled_messages` is the first table read by a background process, and the claim test is what makes per-tenant claiming structural

## Notes

`CommsTenant` is a narrow value object rather than either ORM row because the two callers hold different ones — the router has a host-resolved `TenantContext`, the worker has a `Tenant` from the RLS-free tenants table. Its `phone` collapses `""` and whitespace to `None`, the same rule the public boutique projection uses.

`notify_owner_reschedule` intentionally dropped the spec's `old_starts_at` parameter: the approved Hebrew states only the new time, so there was no old value to render and carrying it unused would be dead weight.

Design context: [[.planning/specs/booking-comms.md]] and [[.planning/specs/owner-booking-management.md]].
