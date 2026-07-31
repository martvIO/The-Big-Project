---
tags: [backend, booking, python, availability, timezone, repository]
sources: [backend/app/booking/slots_io.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/booking/slots_io.py
blob: 97c8ebb9aec0ed266e5cbdb63fa2138ef7d3f146
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/booking/slots_io.py

**Role.** The I/O-shaped sibling of the pure grid: reads one boutique day's availability rules, exceptions and booked counts, hands them to `materialize_slots`, and answers the single question both write paths need — *is this exact instant offered right now?*

**Module.** [[backend/app/booking/_index]] · **Layer.** api

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `offered_slot` | async fn | The requested instant as the grid currently offers it (a `Slot` carrying capacity and booked counts), or `None` |

## Behavior

This module exists because of a boundary, not a feature. [[backend/app/booking/slots.py]] is pure by construction — no session, no repositories, no clock — and that purity is what makes it trustworthy as the single arbiter of bookability, so a coroutine taking an `AsyncSession` and three repositories cannot live inside it. F15 promoted this function out of [[backend/app/booking/service.py]] when a second caller appeared; there is exactly one implementation for the reason the grid module states, that three would be three chances to disagree.

`offered_slot` normalizes the requested instant to UTC, then derives the **boutique-calendar date** it falls on — that is the only date whose rules and exceptions can produce it, so a one-day window is sufficient and not a shortcut. It reads active rules for the tenant, exceptions bounded to that single date, and booked counts over the day's UTC half-open span (boutique midnight to the next boutique midnight, computed through the zone rather than by adding 24 hours, so a DST day of 23 or 25 hours does not lose or duplicate an edge slot). It materializes that one day and returns the slot whose `starts_at` equals the wanted instant, or `None`.

The `None` answer is not a formality: without it a caller books 03:00 on a closed Saturday by posting an arbitrary timestamp. Because it is fed the **real** booked counts and full slots are dropped by the grid, one `None` covers past instants, off-grid times, closed and exception days, the DST rules *and* capacity exhaustion — which is why both callers can map it to a single indistinguishable 409 that leaks nothing about the boutique's grid.

Every read runs on the caller's session, so it inherits whatever tenant context and advisory lock the caller already holds — which is exactly what the claim protocol relies on when it re-materializes the grid inside `pg_advisory_xact_lock`.

## Depends On

- [[backend/app/booking/slots.py]] — `Slot`, `materialize_slots`
- [[backend/app/db/repositories/availability.py]] — `AvailabilityRulesRepository`, `AvailabilityExceptionsRepository`
- [[backend/app/db/repositories/bookings.py]] — `count_by_start`
- [[backend/app/storefront/validation.py]] — `BOUTIQUE_TIMEZONE`

## Depended On By

- [[backend/app/booking/service.py]] — step 5 of the claim, inside the advisory lock
- [[backend/app/booking/owner.py]] — step 4 of the reschedule protocol, inside the same lock

## Concepts

- [[Row Level Security]]
- [[Tenant Context]]

## Tests

- [[backend/tests/test_booking_service.py]] — the claim's grid check, including the concurrency proof
- [[backend/tests/test_booking_owner_db.py]] — reschedule targets over real rules and exceptions
- [[backend/tests/test_slot_engine.py]] — the pure grid this wraps

## Notes

Repositories are passed in rather than constructed here, so the two callers reuse the instances they already hold. The repositories carry an explicit `tenant_id` predicate as defence-in-depth on top of FORCE RLS.

Design context: [[.planning/specs/booking-core.md]] and [[.planning/specs/owner-booking-management.md]].
