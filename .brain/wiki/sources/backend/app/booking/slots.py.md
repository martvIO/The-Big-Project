---
tags: [backend, booking, python, availability, timezone, dst, pure-function]
sources: [backend/app/booking/slots.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/booking/slots.py
blob: a1fef9b42aeaf8791599ea454cb147615f2e4a3f
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/booking/slots.py

**Role.** The ONE place "is this time bookable" is decided: turns weekly availability rules plus date exceptions into the exact set of bookable UTC start instants in a date window, dropping past, nonexistent-under-DST and already-full slots.

**Module.** [[backend/app/booking/_index]] · **Layer.** api

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `Slot` | frozen dataclass | `starts_at` (aware UTC), `capacity`, `booked`, plus a `remaining` property clamped at 0 |
| `materialize_slots` | fn | Rules + exceptions + booked counts + window + `now` → sorted `list[Slot]` |
| `_Window` | frozen dataclass | Internal: one open/close/capacity band for one date |
| `_windows_for` | fn | Internal: resolves the weekly grid against a date exception |
| `_to_utc` | fn | Internal: boutique wall time → UTC instant, or `None` when that wall time is not a single real instant |

## Behavior

Pure by construction — no session, no ORM write, no `Settings`, no `datetime.now()`. That purity is exactly why it is trustworthy as the single arbiter, and it is why the I/O that feeds it was promoted into [[backend/app/booking/slots_io.py]] rather than added here. Three callers ask the same question through it: the claim validating a slot, the storefront painting a picker, and the owner console offering reschedule targets — three implementations would be three chances to disagree, and the one that disagrees in the claim's favour is a double-booked bride.

**A slot is a START TIME**, with no duration and no end. The appointment type's `duration_minutes` is information the boutique acts on but does not shape the grid, and no booking blocks a later start; `availability_rules.capacity` is how many bookings may share one start. That single decision is what removes interval-overlap arithmetic from the entire feature.

Exceptions beat the weekly grid **in both directions**: a row with both times NULL closes a day the grid opens, and a row with both times set replaces the grid's windows for that date. An exception inherits *capacity* from the weekday's own rules because an exception changes hours, not staffing — and when the day carries several windows with different capacities the **least** generous wins, since an exception is characteristically a constrained day and erring high means overselling a short-staffed boutique. With no rule at all to inherit from, `DEFAULT_SLOT_CAPACITY` applies. One window per exception date is an inherited v1 limitation.

DST is handled explicitly rather than left to `astimezone`'s defaults, and both cases are decided rather than accidental. A **nonexistent** local time (spring forward, 02:00→03:00) is dropped — detected by round-tripping the instant back to the boutique zone and comparing, since zoneinfo silently maps a nonexistent local time onto a real instant that renders differently. An **ambiguous** local time (fall back, 01:00 twice) yields only the first occurrence, because the grid generates each wall time once and `combine` leaves `fold=0`: two slots rendering identically at different instants is a worse failure than one lost hour a year. Israel transitions at 02:00 and a boutique's hours rarely reach it, but an exception with unusual hours can — "rarely" is not a correctness argument.

Two accumulation details are load-bearing. Results are keyed by **instant** in a dict, so overlapping windows on one day cannot yield the same start twice (a duplicated start would double-count against `booked`), and when they do overlap the higher capacity wins. And full slots are **dropped, never marked** — a public response enumerating them would disclose the boutique's booking density. `close_time` is exclusive, and only instants strictly after `now` survive.

## Depends On

- [[backend/app/booking/validation.py]] — `SLOT_INTERVAL_MINUTES`, `DEFAULT_SLOT_CAPACITY`, `jerusalem_day_index`
- [[backend/app/models/availability.py]] — `AvailabilityRule`, `AvailabilityException` (read-only, for their columns)
- [[backend/app/storefront/validation.py]] — `BOUTIQUE_TIMEZONE`, the single boutique wall clock

## Depended On By

- [[backend/app/booking/slots_io.py]] — the I/O wrapper that reads the rows and calls `materialize_slots`
- [[backend/app/storefront/service.py]] — `list_slots`, the picker's data
- [[backend/app/storefront/router.py]] — the `Slot` type in its projection
- [[backend/app/booking/owner.py]] — the `Slot` type returned by the owner slot grid
- [[backend/app/booking/owner_router.py]] — projects `Slot` into `OwnerSlotRow`

## Concepts

- [[Tenant Isolation]]

## Tests

- [[backend/tests/test_slot_engine.py]] — the whole grid: exceptions in both directions, capacity inheritance, the DST nonexistent and ambiguous cases, overlapping windows, the drop-full rule
- [[backend/tests/test_storefront_api.py]] — the picker's wire projection over real slots

## Notes

The `remaining` clamp at 0 is a second-bug guard, not a path: an overbooked slot is a data anomaly and reporting a negative vacancy would compound it — such a slot never reaches a caller anyway because `materialize_slots` drops it.

Design context: [[.planning/specs/booking-core.md]].
