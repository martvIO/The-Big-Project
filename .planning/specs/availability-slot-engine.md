# Spec: Feature 12 — Availability & Slot Engine (Epic E3)

**Created**: 2026-07-28 · **Status**: draft — awaiting Gate 1 · **Epic**: E3 Feature 12 · **Effort**: M
**Depends on**: E2 #7 (`availability_rules`, `availability_exceptions`, `appointment_types`), E2 #10 (the public storefront router and its contract) — branches off `main` · **Feeds**: E3 #13 (the booking claim reads the same grid), E3 #14 (the slot picker renders it), E3 #15 (owner reschedule picks a new slot from it)

## Problem

F7 gave the owner a weekly grid and per-date exceptions; F10 renders them as opening hours on `/about`. Nothing turns them into **things a customer can book**. A "10:00–19:00, Sunday to Thursday" rule is prose until something materializes it into discrete start times, subtracts what is already taken, drops what is in the past, and answers the two questions the booking UI actually asks: *which times can I pick, and is this one still free?*

That computation has to exist exactly once. F13 needs it to validate a claim server-side, F14 needs it to paint a picker, F15 needs it to offer a reschedule target. Three implementations of "is 14:30 next Tuesday bookable" is three chances to disagree, and the one that disagrees in F13's favour is a double-booked bride.

## Goal

`GET /storefront/slots?from=2026-08-02&to=2026-08-08` returns every bookable start time in that window for the boutique the hostname resolves to — already excluding closed days, per-date exceptions, past times, and fully-taken slots, so every time it returns is one a customer can take. The engine behind it is a pure function with no I/O, so its hard parts — the Israeli week, Israel's DST transitions, an exception that closes a day the weekly grid says is open — are covered by unit tests that need no database and no clock.

## The slot model (decided 2026-07-28 with the pilot boutique)

**A slot is a start time. It has no duration and no end.** The appointment type a customer chooses is recorded on the booking, and its `duration_minutes` is information the boutique acts on — but it does **not** shape the grid, and no booking blocks a later start time. This resolves the epic's open capacity question and simplifies F13's claim to a point, not an interval:

- The grid is `SLOT_INTERVAL_MINUTES` (30) apart, from a day's `open_time` up to but excluding its `close_time`.
- **Capacity > 1 is supported.** `availability_rules.capacity` is how many bookings may share one start time (parallel fittings / fitting rooms). It already exists, defaults to 1, and is finally load-bearing here.
- A slot is bookable when `booked_count < capacity`. F13 enforces that with a per-tenant advisory lock plus a `seat_index` unique index, which is structural at any capacity — no interval overlap logic anywhere in the epic.

The alternative — durations, end times and overlap arithmetic — was rejected as a solution to a problem the pilot does not have.

## Design

### No migration

F12 adds no table, no column, no index. Every read is served by `idx_availability_rules_tenant_active` (built by 0005 with the comment "E3's slot engine reads the active weekly set on every computation") and the exceptions' partial unique index. `test_every_tenant_id_table_has_forced_rls` therefore gains nothing, and its continued green is the assertion that F12 did not sneak a table in.

### The engine — `app/booking/slots.py`, pure

```python
@dataclasses.dataclass(frozen=True)
class Slot:
    starts_at: datetime.datetime   # timezone-aware, UTC
    capacity: int
    booked: int
    @property
    def remaining(self) -> int: ...

def materialize_slots(
    *,
    rules: Sequence[AvailabilityRule],
    exceptions: Sequence[AvailabilityException],
    booked: Mapping[datetime.datetime, int],   # keyed by UTC start instant
    window_start: datetime.date,               # inclusive, boutique calendar
    window_end: datetime.date,                 # inclusive, boutique calendar
    now: datetime.datetime,
) -> list[Slot]
```

Zero I/O, zero ORM writes, no `Settings`. It takes rows and returns values, which is what makes the hard cases testable without a database.

**Rules of materialization, in order:**

1. **The Israeli week.** `availability_rules.day_of_week` is 0=Sunday…6=Saturday; Python's `date.weekday()` is 0=Monday. One conversion, `jerusalem_day_index(d) = (d.weekday() + 1) % 7`, lives here and is unit-tested against a hand-written table of real dates. `packages/ui/src/lib/hours.ts` already ships the same conversion for rendering — `test_frontend_constant_parity.py` gains a row so the two cannot drift.
2. **Exceptions beat the weekly grid, in both directions.** For a date with an exception row: both times NULL → the day is **closed**, no slots, even if a weekly rule says otherwise; both times set → those hours **replace** the weekly windows for that date. (One window per exception date is F7's documented v1 limitation, inherited unchanged.)
3. **Capacity for an exception day** comes from that weekday's weekly rule when one exists, else `DEFAULT_SLOT_CAPACITY` (1). Where the weekday carries several windows at different capacities, the **least** generous wins: an exception is characteristically a constrained day (a holiday opened for one bride), so erring high would oversell a short-staffed boutique — the exact failure this feature exists to prevent. Exceptions have no capacity column, and inventing one for a per-date override would be a schema change in service of a case the pilot has never asked for.
4. **Local wall clock → UTC instant.** Times are boutique-local by definition, so each start is built in `BOUTIQUE_TIMEZONE` and converted. Two DST cases are handled explicitly rather than left to `astimezone`'s defaults:
   - **Nonexistent** local time (spring forward, 02:00→03:00): the slot is **dropped**. It does not exist, so it cannot be booked.
   - **Ambiguous** local time (fall back, 01:00 twice): the **first** occurrence (`fold=0`) is kept and the second dropped, so a day never silently offers two slots that render identically and are different instants.
   Israel's transitions are at 02:00 and a boutique's hours rarely reach them — but an exception with unusual hours can, and "rarely" is not a correctness argument.
5. **The past is not bookable.** Slots with `starts_at <= now` are dropped. The cutoff is the passed-in `now`, never `datetime.now()`, so the boundary is testable.
6. **Taken slots are dropped, not marked.** A slot whose `booked >= capacity` never reaches the wire: a public response that enumerated full slots would disclose the boutique's booking density to anyone.

Output is sorted by `starts_at`.

### The API — two public GETs

Both join the existing `app/storefront/router.py` (GET-only, `_no_store` + `_throttle`, anonymous, tenant-from-Host), inheriting its whole contract. The route-table guards in `test_storefront_api.py` pick them up automatically.

**`GET /storefront/slots?from=&to=`** → `{"slots": [{"starts_at": "...Z"}, ...]}`

- `from`/`to` are boutique-calendar dates, inclusive; `from` defaults to today in Jerusalem, `to` to `from + SLOT_WINDOW_DEFAULT_DAYS` (14). The window is capped at `SLOT_WINDOW_MAX_DAYS` (60) — one anonymous request must not be able to ask for five years of grid.
- `to < from` → 400 `VALIDATION_ERROR`.
- **Both bounds are clamped against `today`, not against the caller's own value.** That is not cosmetic: `date + timedelta` raises `OverflowError` within 60 days of `date.max`, there is no handler for it, and `?from=9999-12-31` is among the first things anyone probes on a public endpoint — a free 500 outside the house error shape. `today` comes from a real clock and can never be near either end of the range. Clamping the floor costs nothing because the engine already drops everything at or before `now`; a wholly-past window comes back inverted and materializes to nothing, the same empty answer as before. (Same reasoning as `MAX_LIST_OFFSET`: an unbounded caller value reaching something that raises rather than validates.)
- **Neither `capacity` NOR `remaining` reaches the wire — a start time is the whole message.** F10's allowlist fences `capacity` off this surface because it "discloses how many parallel fittings the boutique runs". An earlier draft shipped `remaining` as the safe half of it; that was wrong. The engine drops full slots, so with no bookings `remaining` equals `capacity` **exactly, for every slot, on every response** — the fenced field republished under a key the wire-absence walk does not know to forbid. The picker does not need it either: every slot returned is by construction bookable. A scarcity cue ("last spot") is a real product idea, and the feature that adds it should add a deliberately COARSE signal on top of a real booking count.
- No `appointment_type_id` parameter. The grid is type-independent by the slot model above, so accepting one would imply a filter that does not exist.

**`GET /storefront/appointment-types`** → `[{"id", "name", "duration_minutes", "audience", "deposit_required", "deposit_amount_agorot"}]`

The booking UI has to show what can be booked, and no public endpoint exposes types today. Active types only, `sort_order` then `created_at`.

**Audience is disclosed, not enforced** — and this is a deliberate scope call. `audience = brides_only` marks a type for brides; an anonymous visitor cannot be classified as one, so there is no server-side filter to write that would not be theatre. The field ships so F14 can label the option ("לכלות בלבד"), and real enforcement waits for a client identity — E5's client login. Recorded here so a later reader does not mistake the omission for an oversight.

`deposit_required` / `deposit_amount_agorot` ship now because E4's deposit step reads them, and because a customer is entitled to see a deposit before choosing a time, not after.

### Service — `StorefrontService` gains two reads

`list_slots(tenant_id, *, from_date, to_date)` and `list_appointment_types(tenant_id)`. The first does one `tenant_session` with two repository reads (rules, exceptions **bounded on both sides in SQL**) then calls the pure engine. The upper bound is not decoration: the window bounds the response either way, but an unbounded upper predicate would still scan every future exception the boutique has ever recorded, on every anonymous request.

**`booked` is `{}` in F12 and is the seam.** No `bookings` table exists until F13, so the engine is fed an empty mapping and every slot shows full capacity. F13's change is one repository call replacing that literal — the engine, its tests, the response shape and the picker are all already correct at that point. This is the one place F12 knowingly ships an incomplete truth, and it is why the parameter exists at all rather than being read inside the engine.

### Named constants (`app/booking/validation.py`)

| Constant | Value | Why this number |
|---|---|---|
| `SLOT_INTERVAL_MINUTES` | 30 | the boutique's own scheduling granularity; 15 doubles the picker for no pilot benefit, 60 loses the half-hour starts owners actually use. Per-tenant tunability is a column and a settings row — deliberately deferred until a boutique asks |
| `DEFAULT_SLOT_CAPACITY` | 1 | matches the DB default; used only when an exception day has no weekly rule to inherit from |
| `SLOT_WINDOW_DEFAULT_DAYS` | 14 | two weeks is what a picker shows before "next" |
| `SLOT_WINDOW_MAX_DAYS` | 60 | one anonymous request must not materialize years of grid; 60 days at 30-minute steps over a 9-hour day is ~1000 slots, a bounded response |

Not env-tunable, per F8's rule that `Settings` carries deployment identity and never product policy.

## Frontend changes

None. F12 is backend-only; F14 builds the picker against the contract above. The one frontend touch is a row in `test_frontend_constant_parity.py` pinning the Israeli-week conversion against `packages/ui/src/lib/hours.ts`.

## Testing

Fast suite (no marker), and it is the bulk of the feature:
- `jerusalem_day_index` against a hand-written table of real dates spanning a year.
- Grid generation: open/close boundaries (close is exclusive), a window that starts mid-day, odd open times that do not land on the interval.
- Exceptions: closed-all-day beats an open weekly rule; special hours replace weekly hours; an exception on a day with no rule opens it; capacity inheritance and the `DEFAULT_SLOT_CAPACITY` fallback.
- Multi-window days (F7 allows several rules per weekday) produce the union with no duplicates.
- **DST**: a slot at a nonexistent local time is dropped; an ambiguous one appears exactly once; a normal day either side is unaffected. Uses real Israeli transition dates.
- Capacity: `booked < capacity` remains with correct `remaining`; `booked == capacity` disappears; `booked > capacity` (a data anomaly) disappears rather than reporting negative.
- `now` boundary: a slot exactly at `now` is out, one second later is in.

API tests: the two routes join the derived `ROUTES` table (auth-guard-reverse, tenant-required, no-store, cookie-blind, forbidden-key walk — `capacity` is already in `FORBIDDEN_KEYS`, so the wire-absence walk arms itself), window validation and clamping, and the empty-`booked` seam asserted explicitly so F13's change is a visible diff.

`db`-marked: a service-level read against real Postgres proving rules + exceptions load and the engine runs end-to-end; an isolation row proving tenant B's slots never reflect tenant A's rules.

## Out of scope

The `bookings` table and any real `booked` count (F13), the picker UI (F14), owner reschedule (F15), per-tenant slot interval, per-date capacity overrides, and audience enforcement (needs client identity — E5).

## Risks

1. **`booked` is empty until F13**, so `/storefront/slots` overstates availability if it reaches a customer before F13 merges. Mitigated by ordering: F13 is the next PR and nothing links to the endpoint until F14. Flagged in the response's own service docstring so it cannot be forgotten.
2. **The 30-minute interval is a guess about the pilot's rhythm.** It is one constant in one file with no schema behind it, so the cost of being wrong is a PR, not a migration.
3. **Exception days inherit weekly capacity**, which is still approximate for a boutique that opens a normally-closed day with fewer staff — the `min` rule above errs toward under-booking rather than overselling, but a real per-date capacity would need a column. No pilot signal either way; revisit if one appears.
