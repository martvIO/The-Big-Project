---
tags: [backend, booking, python, owner-console, state-machine, concurrency, audit, pii, rate-limiting]
sources: [backend/app/booking/owner.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/booking/owner.py
blob: 2af075f74654afbaefd597b4d003dc7a316138b8
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/booking/owner.py

**Role.** The owner console's booking service: the Jerusalem-day list and detail, the four-verb status graph split at `starts_at`, the in-place reschedule protocol, and the owner-attested phone correction that rotates live manage links inside the same transaction — every mutation writing an `audit_log` row before commit.

**Module.** [[backend/app/booking/_index]] · **Layer.** api

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `OwnerBookingService.list_day` | async method | One Jerusalem calendar day, every status, paged |
| `OwnerBookingService.detail` | async method | One booking, or an indistinguishable 404 |
| `OwnerBookingService.customers_for` | async method | The name/phone lookup the list and detail need, keyed for the caller |
| `OwnerBookingService.list_slots` | async method | Full `Slot` objects — capacity and remaining survive for the owner |
| `confirm` · `no_show` · `complete` | async method | The three non-cancel transitions, through `_transition` |
| `cancel` | async method | Owner cancel; also kills the pending reminder |
| `reschedule` | async method | Eight ordered steps in one transaction |
| `correct_phone` | async method | Owner-attested phone fix, with link rotation |
| `resend_link` | async method | Rotation with no phone edit |
| `OwnerMutation` | frozen dataclass | `booking`, `changed`, `manage_token` |
| `BookingTransitionInvalidError` | class | One code for every illegal state or clock → 409 |
| `CustomerAlreadyBookedError` | class | This customer already holds a live booking at the target instant → 409 |
| `OwnerResendThrottledError` | class | The per-tenant owner-SMS budget is spent → the shared 429 |
| `MAX_LIST_OFFSET` | const | 1 000 000 |

## Behavior

**The transition graph is split at `starts_at`, and that split is its whole shape.** Marking no-show or completed is something you do to a *past* appointment — both are attendance records; cancelling is something you do to a *future* one, because it frees a seat and texts the customer. `confirm` is the undo of a mis-tap and carries no clock bound at all, and it writes `status` only: `attendance_confirmed_at` means the **bride** said she is coming, so an owner correcting her own record of the outcome does not get to speak for her.

All four verbs run the same five ordered steps in one `tenant_session`: load (missing → 404); compare (already at the target → 200, `changed=False`, **no** audit row); raise (an illegal pair or an illegal clock → 409, nothing written); a **predicate-guarded** write carrying the same conditions as the Python checks; and the audit row, in the same transaction before commit. Step 4 is not redundant with step 3 — the predicate is what makes the write safe under a concurrent writer, while the Python check above it is what makes the *answer* honest, because a guarded UPDATE returns zero rows for an illegal transition **and** for a legal repeat, so the statement result alone cannot separate the 409 from the 200. When the guarded write returns nothing anyway, the service raises rather than committing evidence for a move that did not happen.

Two ORM traps are guarded explicitly and both would corrupt the audit trail rather than the data. The repositories' UPDATEs are ORM-enabled DML whose default `evaluate` synchronization **stamps the SET values onto the in-memory instance**, and the trailing `by_id` hands the same object back — so `from_status`, `old_starts_at` and `old_seat_index` are all captured *before* the write. Reading them afterwards would record `{from: no_show, to: no_show}` or `old == new`, emptying the exact trail the feature exists for. `cancel` is subtler still: `None` from its writer is the only usable signal, because a bride cancelling on her manage link in the same window leaves `status = 'cancelled'` — the target — and `evaluate` has already stamped `cancelled_by = 'owner'` onto the instance regardless of what the database matched, so even the evidence columns lie. The one case still indistinguishable is a concurrent *owner* cancel, whose audit row would merely duplicate a truthful one. `cancel` also cancels the pending reminder, mirroring the customer path — without it the customer gets a cancellation SMS and then, hours later, a reminder for the appointment that was cancelled. It is deliberately **not** metered, because `cancelled` is terminal and the ceiling is therefore one SMS per booking by construction. And `no_show`/`completed → cancelled` is forbidden for a reason of its own: refund-versus-forfeit evaluation reads `cancelled_at`, and writing it on a booking the bride actually attended would make that evaluation lie.

**Reschedule is an in-place UPDATE of `(starts_at, seat_index)` on the same row**, never a cancel-and-reinsert — which would write `cancelled_at` on a booking nobody cancelled, break the manage link, orphan the `scheduled_messages` row, re-snapshot the terms evidence and break the deposit carry-over. Eight steps, and the order is the argument. A total range guard on `new_starts_at` runs before any arithmetic (an `OverflowError` from `.astimezone()` on a year-9999 instant would be an unhandled 500). The SMS budget is consulted **before** the transaction opens, so a 429 writes nothing and sends nothing; reschedule is metered precisely because it is *unbounded* — a booking can be walked A↔B↔A between two legitimately offered slots forever, each hop a real SMS plus a reminder rewrite plus a token rotation. Inside, the advisory lock is taken **before any read of the booking**: skipping it would not oversell (the index backstops that), but reading outside it races a public create and, worse, two submissions of the same dialog would both see the *original* `starts_at`, the second would miss the no-op short-circuit, and the collision check would then find the booking itself. The no-op check is load-bearing for the same reason — `active_at` and `active_seats_at` have no booking-id exclusion. Then `offered_slot` buys past instants, off-grid times, closed and exception days, the DST rules and capacity in one call; the per-customer collision (0009) is a genuinely different failure from a full slot; and the **lowest free seat at the target** is recomputed, never carried, because nothing in the database ties a seat to its slot's capacity — 0008's `CHECK` is only 1..1000, so seat 3 carried into a capacity-1 target satisfies both the CHECK and the unique index and is a silent oversell. Capacity is enforced in Python and nowhere else. No extra write releases the source seat: both partial unique indexes are re-evaluated over the row's new values at statement time. Finally the reminder rewrite runs in **this** transaction, because post-commit a crash leaves the old `send_after` on a pending row and `drain_due` can claim the stale row and clear its token in the window.

**The phone correction is owner-attested — no OTP — because requiring one would require the bride to be reachable at the number that demonstrably does not work.** That narrows an invariant written down three times, so the mechanics are the argument for shipping it. Two branches, split by what was wrong. Non-collision means the *digits* were wrong: `customers.phone` is corrected and **every** live booking of that customer rotates, because `customers` is the phone identity every future SMS reads at send time while `manage_token_hash` is per-row. Collision means the *identity* was wrong: the booking re-points at the customer who already holds that number, `customers.phone` is never touched, both rows survive, and only this booking rotates. The 0009 collision is pre-checked because two sisters in one capacity-2 slot make it ordinary rather than exotic, and an unmapped flush would escape as a bare 500 — there is no error registry, so every typed error needs its own handler. The non-collision branch takes **no advisory lock** and its `IntegrityError` is mapped to a *different* error than the re-point branch's, deliberately: nobody is double-booked, the number just acquired an owner, and a retry takes the re-point branch. `_rotate_links` treats a `None` from any rotation as a hard failure that rolls the whole transaction back — there must be no committed state in which the phone is corrected and the old hash survives, because the stranger's link would still resolve and still cancel the bride's appointment at a route with no phone check. Only the **edited** booking's token leaves on the result: rotating a sibling's token silently is the safety half and must be unconditional, but texting the bride N confirmations for N bookings is spend and noise.

`resend_link` is rotation, not a re-send, and the Hebrew says so — a plain resend is impossible in any case once a reminder has fired, because `bookings` stores only the sha256 and cancelling a pending row clears the raw token, so nothing on the platform can reproduce a sent link. Rotation is the only behaviour available in every case, which makes it the only honest one. There is deliberately no compare-and-swap: two rotations seconds apart produce one live link and one dead one, which *is* the specified behaviour, and the row lock orders the writes so the surviving hash is always real.

`_guard_live` (confirmed **and** future) is evaluated in Python for the honest answer and carried again as the predicate on every rotation UPDATE so it cannot go stale mid-operation — minting a live control token on a booking cancelled seconds ago, and texting a confirmation for an appointment that no longer exists, is verbatim what it prevents.

`list_day` converts the calendar date through the boutique zone rather than by adding 24 hours, since a DST day is 23 or 25 hours long, and it guards `date.min`/`date.max` because the router declares a bare `datetime.date`: `?date=9999-12-31` overflows on `date + 1 day`, and boutique midnight on `0001-01-01` underflows in `.astimezone()`. `offset` is clamped in the service as well as at the router because it binds as `OFFSET $n::BIGINT` and an unbounded Python int from a non-router caller would die in asyncpg's encoder as a 500 rather than a 400. `customers_for` reads `customers` live rather than snapshotting, because the phone correction rewrites it in place and a snapshot would render the number the owner just fixed. `list_slots` delegates to `StorefrontService.list_slots` — injected rather than re-implemented, because a second materializer is the one thing the pure grid exists to forbid — and keeps `capacity`/`remaining`, which only the anonymous projection strips.

The SMS budget lives on its **own** `FixedWindowRateLimiter` instance, never a second key on another one, because `max_attempts` lives on the limiter and a shared instance would hand this budget somebody else's ceiling. It is spent immediately after commit, before returning to the router, rather than at the send site — reaching back into it would put limiter plumbing in three handlers to move one line, and `_deliver` swallows provider failures anyway, so there is no post-send value to branch on.

## Depends On

- [[backend/app/db/tenant.py]] — `tenant_session`
- [[backend/app/booking/slots_io.py]] — `offered_slot` for the reschedule target
- [[backend/app/booking/slots.py]] — the `Slot` type
- [[backend/app/booking/comms.py]] — `BookingCommsService`, and `upsert_reminder` run on the reschedule's own transaction
- [[backend/app/booking/service.py]] — `BOOKABLE_HORIZON`, `BookingNotFoundError`, `SlotUnavailableError`, reused rather than restated
- [[backend/app/booking/tokens.py]] — mint and hash on every rotation
- [[backend/app/booking/validation.py]] — `BOOKING_LIST_MAX_LIMIT`
- [[backend/app/storefront/service.py]] — `StorefrontService.list_slots`
- [[backend/app/auth/service.py]] — `StaffContext`, the audit actor
- [[backend/app/auth/rate_limit.py]] — `FixedWindowRateLimiter`
- [[backend/app/notifications/validation.py]] — `normalize_israeli_mobile`
- [[backend/app/db/repositories/bookings.py]] · [[backend/app/db/repositories/customers.py]] · [[backend/app/db/repositories/scheduled_messages.py]] · [[backend/app/db/repositories/audit_log.py]] · [[backend/app/db/repositories/availability.py]]
- [[backend/app/models/booking.py]] · [[backend/app/models/customer.py]] · [[backend/app/models/constants.py]] · [[backend/app/errors.py]] · [[backend/app/storefront/validation.py]]

## Depended On By

- [[backend/app/booking/owner_router.py]] — all ten routes, and `MAX_LIST_OFFSET` as the `Query` bound
- [[backend/app/main.py]] — constructs the service after the comms and storefront services (it holds both), wires the owner-SMS limiter, and binds handlers to `BookingTransitionInvalidError`, `CustomerAlreadyBookedError` and `OwnerResendThrottledError`

## Concepts

- [[Row Level Security]]
- [[Tenant Context]]
- [[Rate Limiting]]
- [[Tenant Isolation]]

## Tests

- [[backend/tests/test_booking_owner_service.py]] — the graph, the guards and the no-op semantics
- [[backend/tests/test_booking_owner_db.py]] — reschedule, phone correction and rotation against real rows and real indexes
- [[backend/tests/test_booking_owner_api.py]] — the HTTP surface and every error's status
- [[backend/tests/test_booking_comms_db.py]] — the reminder rewrite inside the reschedule transaction

## Notes

The `audit_log` payload for a phone correction stores **last-4 only** — `audit_log` is retained on the audit clock rather than the booking clock, and a full number in JSONB is a second uncontrolled copy of the one PII field this feature edits. The customer ids beside it are what make a data-subject complaint answerable at all: `set_phone` overwrites in place and `customers` has no history table, so without them the number the link was pointed *away from* survives nowhere. Reschedule details are ISO **strings** rather than `datetime` objects, because `details` is JSONB and a `datetime` there is a `TypeError` at flush — on the very audit row the feature exists for.

`OwnerResendThrottledError` is its own class rather than a reuse, matching the other three throttles; reparenting them onto one base is deferred.

Design context: [[.planning/specs/owner-booking-management.md]].
