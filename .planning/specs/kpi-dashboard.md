# Spec: F52 — KPI dashboard, the console's landing section (SMC-3)

**Created**: 2026-07-31 · **Status**: **Gate 1 self-approved 2026-07-31 under Interview Q1** (standing approval — Q1's stop-list is F17, F18, F19, F20, F29, F48 and F52 is not on it; this is a read-only surface that touches no money and no legal text). **The design gate self-approves too, under Interview Q2**: Q2 names exactly two novel patterns — F34's shift board and F42's capacity matrix — and F52 is neither. Its screen is `SectionHeading` + `Card` + `Skeleton`, all shipped, plus one hand-built bar row that stays inline markup in the section and is **not** promoted into `packages/ui` (D10). (`Badge` and `EmptyState` are deliberately **absent** — the layout table forbids an `EmptyState` in the only state that could carry one, and no tile places a `Badge`. Listing components the screen never mounts would pad the argument rather than make it.) Designer and `design-critic` must still both accept. · **Epic**: SMC (`.planning/epics/shift-manager-console.md`), phase SMC-3 · **Effort**: **M** (one GET, no migration, two new repository reads, one new coroutine in `slots_io.py`, one new backend package, one console section that becomes the landing screen — F51's M was four endpoints)
**Depends on**: #31 (`require_role`, the `RoleGate`, the default-deny route walker) and #51 (the role-filtered `NAV` table this feature inserts a row into, and the seventh section it counts) · **Feeds**: F53 and F34 (both land console sections beside this one; F34 also inherits the "no poll here" ruling in D11)

---

## Problem

The manage console has seven sections and every one of them answers a question about **one row**: this dress, this appointment type, this booking, this staffer. `BookingsSection` is the closest thing to an overview and it shows exactly one Jerusalem day, chosen from a `DateField`, with no aggregate anywhere (`BookingsSection.tsx:19, 88-104`). An owner who wants to know whether the boutique is busier than last month has to click through ninety days.

The data to answer that has been sitting in `bookings` since F13 and nothing reads it in aggregate. `BookingsRepository` has fourteen methods and exactly one of them groups: `count_by_start`, which feeds the slot grid and deliberately excludes cancellations (`db/repositories/bookings.py:436-459`). There is no method anywhere that answers "how many bookings last week", "what share were no-shows", or "how many of these brides had been here before".

The second half is the landing screen. `App.tsx:49` starts every session on `"profile"` — the boutique's name, address and hours. That is the screen an owner configures once and never opens again, and it is the first thing she and every shift manager see on every login. A console whose landing screen is a settings form is a console that makes its user navigate before it tells her anything.

The third is that the epic locked this feature's shape and its exclusions: **ops + customer KPIs, no revenue (payments are unbuilt until E4), forward-only utilization** (`epics/shift-manager-console.md:31`). Those exclusions are not editorial. `bookings` carries no price, no deposit-paid flag and no payment reference (`models/booking.py:24-53`), so "no revenue" is a schema fact. And historical capacity genuinely does not exist: `replace_weekly_rules` soft-deletes the whole active set and re-inserts, `AvailabilityRulesRepository.list_active` is the only reader and pins `deleted_at IS NULL`, so nothing in the product can say what the grid looked like in May.

## Goal

`apps/manage` gains an eighth section, **visible to both roles**, and it becomes the section the console lands on. It answers six questions and refuses to answer a seventh:

- how many appointments stood, week by week, for the last twelve complete Israeli weeks
- what share of bookings were cancelled, and who cancelled them
- what share of the appointments whose outcome the owner actually recorded were no-shows
- which appointment types filled those weeks
- how many of the brides in that window were new to the boutique, and how many had been before
- how full the next seven days are **right now**

and it does not pretend to know how full last May was.

Every number is defined once, in one place, as a pure function over a narrow projection of `bookings` — so every definition is pinned by a fast test that needs no Docker (D3). **F52 ships no migration.**

## What already exists to build on (verified against code)

- **The window arithmetic is a shipped idiom, and it is date-space arithmetic.** `OwnerBookingService.list_day` converts a Jerusalem calendar day to a half-open UTC range with `datetime.combine(date, time.min, tzinfo=BOUTIQUE_TIMEZONE).astimezone(UTC)` for the floor and the same on `date + timedelta(days=1)` for the exclusive ceiling, and its docstring states the reason: *"across a DST boundary the day is 23 or 25 hours long — arithmetic that added a fixed 24h would drop or duplicate the edge booking"* (`booking/owner.py:150-178`). `StorefrontService.list_slots` does the same three lines (`storefront/service.py:198-206`), as does `slots_io.offered_slot` (`slots_io.py:50-55`). F52 does it once more, for week edges.
- **`BOUTIQUE_TIMEZONE = ZoneInfo("Asia/Jerusalem")` is declared exactly once** (`storefront/validation.py:40`) and every module imports it; `booking/validation.py:4-6` records the rule — *"two zone constants is one zone constant too many"*. `Clock = Callable[[], datetime.datetime]` (`:42`) and `today_jerusalem(clock)` (`:86-94`) are the injectable calendar anchor.
- **The Israeli week is already encoded, once, and pinned on both sides.** `jerusalem_day_index(date) -> (date.weekday() + 1) % 7`, documented as *"0=Sunday … 6=Saturday — the Israeli week, and the encoding `availability_rules.day_of_week` uses"* (`booking/validation.py:104-112`). `packages/ui/src/lib/hours.ts` mirrors it and `tests/test_frontend_constant_parity.py` pins the pair.
- **The slot engine is the ONE place capacity is decided, and it says so.** `materialize_slots(*, rules, exceptions, booked, window_start, window_end, now)` — six keyword-only parameters, no defaults, window **inclusive on both ends** (`slots.py:107-122, 134`). Its module docstring: *"three implementations of this question would be three chances to disagree"* (`slots.py:1-15`), restated at `booking/owner.py:126-129`.
- **`booked` is caller-supplied precisely so it can be empty.** `slots.py:119-121`: *"in F12 the caller has nothing to pass: the `bookings` table lands with F13"*, and `StorefrontService.list_slots` records that F12 shipped exactly this call with `booked={}` (`storefront/service.py:191-194`). That mode is shipped and sanctioned, not a hack — see D4.
- **`availability_rules.capacity` carries `CHECK (capacity > 0)`** (`0005_boutique_settings.py:65`) and `DEFAULT_SLOT_CAPACITY = 1` (`booking/validation.py:28`). That is what makes `booked={}` a complete grid rather than a filtered one.
- **`count_by_start` is reusable as-is for the forward numerator** — per-instant occupied-seat counts in `[from, until)`, `status <> 'cancelled'`, `deleted_at IS NULL`, one GROUP BY range scan on `idx_bookings_tenant_starts` (`db/repositories/bookings.py:436-459`). It is **not** reusable for any historical rate (D2).
- **`list_day` is the in-repo precedent for an all-status read**, and its docstring already argues the distinction F52 needs: *"This deliberately does NOT inherit `count_by_start`'s `status <> 'cancelled'` predicate: that method mirrors the occupancy indexes"* (`db/repositories/bookings.py:369-376`).
- **The status set is CHECK-pinned and only one value frees a seat.** `status IN ('confirmed','cancelled','no_show','completed')` with `server_default 'confirmed'` (`0008_bookings.py:66-67, 84-87`), mirrored by `BookingStatus` (`models/constants.py:47-54`). Both partial unique indexes and every occupancy query use `status <> 'cancelled'` — a `no_show` still occupied its seat.
- **`cancelled_at` / `cancelled_by` have exactly one writer.** `BookingsRepository.cancel` writes both, guarded on `status = 'confirmed'` so a repeat cancel preserves the first cancellation's evidence (`db/repositories/bookings.py:302-318`); `set_status` explicitly never touches them (`:248-252`). `cancelled_by` is CHECK-pinned to `('customer','owner')` (`0010_booking_comms.py:41-45`).
- **`attendance_confirmed_at` is not an attendance record.** `set_status`'s own docstring: *"that is F16's column and it means the bride said she is coming, not that the owner recorded an outcome"* (`db/repositories/bookings.py:249-252`). F52 never reads it (D2).
- **`appointment_type_name` on `bookings` is a deliberate snapshot** — *"a renamed type or an archived dress must not rewrite history the customer agreed to"* (`models/booking.py:19-22`) — while `AppointmentTypesRepository.update_fields` renames in place and `soft_delete` archives, with the unique index partial on `deleted_at IS NULL` so an archived type frees its name for reuse (`db/repositories/appointment_types.py:60-97`, `0005_boutique_settings.py:52-54`). Both keys are lossy alone; D5 uses both.
- **Two indexes carry every read F52 makes.** `idx_bookings_tenant_starts ON bookings (tenant_id, starts_at) WHERE deleted_at IS NULL` (`0008_bookings.py:95-97`) and `idx_bookings_tenant_customer ON bookings (tenant_id, customer_id) WHERE deleted_at IS NULL` (`:101-104`). There is **no** index on `created_at`, `status` or `appointment_type_id` — which is why D2 buckets on `starts_at`.
- **The aggregate idiom, one shipped example.** `DressVariantsRepository.aggregate_by_dress`: module-level frozen dataclass, empty-input short-circuit, `select(key, func.count(), func.coalesce(func.sum(…), 0))`, explicit `tenant_id` + `deleted_at` predicates, dict comprehension (`db/repositories/dress_variants.py:12-62`). D6's second read copies it verbatim.
- **The `/manage` router template, five shipped copies.** `APIRouter(prefix="/manage", dependencies=[Depends(_no_store), Depends(require_role(...))])`, a local three-line `_no_store` rather than a cross-package import, a docstring recording the include-order shadowing hazard and naming its own `ROUTES` table as the guard, and an explicit note that *"the `.claude/rules` RPC / `@QueryValue` guidance is Kotlin boilerplate for another codebase"* (`auth/staff_router.py:1-64`, `booking/owner_router.py:1-27`). `create_app` includes the five in a fixed order, and the **shadowing comment appears on three of them** — catalog, owner-booking and staff (`main.py:678-691`). The first three includes (health, auth, boutique — `:675-677`) carry none, because each is the first on its prefix. F52 is the sixth `/manage` router, so it copies the three-router convention, not a five-router one.
- **`CsrfOriginMiddleware` fences `MUTATING_METHODS` only** (`csrf.py:48`) — so a GET under `/manage` cannot produce `CSRF_ORIGIN_MISMATCH`, which changes F52's error-completeness test (Tests).
- **Reads are never audited.** `AuditLogRepository.record` is called from four modules and every call site is a mutation; no GET handler in the product writes an audit row — not the booking day list, not the booking detail that renders a bride's phone and free-text notes, not the owner-only staff list. F52 writes none (D9).
- **The frontend shell takes a section in five edits.** `SectionKey` is a plain union (`App.tsx:15`), `NAV` is a `readonly NavItem[]` of `{key, labelKey, roles}` filtered by `staff.role` (`:29-43, 80`), the landing section is `useState<SectionKey>("profile")` (`:49`), and sections render as a flat list of `{activeKey === "x" && <XSection/>}` (`:111-117`). No router.
- **The wire format is the backend's snake_case verbatim.** `apps/manage/src/api.ts:1-5` states it — no case-conversion layer, `credentials: "include"`, errors surfaced as `ApiError` from the `{error:{code,message}}` envelope. Endpoints are one-line methods on a flat object (`:390-401`).
- **`BookingsSection` is the shipped read-only-section template**, down to the failure register: nullable state, `let cancelled = false`, `loading = rows === null && loadError === null`, one `role="status"` announced region, a muted `role="alert"` outage line, `<Skeleton variant="text" lines={4} />`, and a comment recording that the catch deliberately does **not** `setRows([])` because an empty list under the alert would stack the empty state on the outage (`BookingsSection.tsx:27-51, 106-141`).

---

## Design

### No migration, and no new `AuditAction` (D1)

Every column F52 reads exists: `starts_at`, `status`, `cancelled_by`, `customer_id`, `appointment_type_id`, `appointment_type_name`, `deleted_at` on `bookings`; `day_of_week`, `open_time`, `close_time`, `capacity` on `availability_rules`; `date`, `open_time`, `close_time` on `availability_exceptions`. Every read rides an index that already exists (`idx_bookings_tenant_starts`, `idx_bookings_tenant_customer`). No table is added, so `test_every_tenant_id_table_has_forced_rls` staying green is the assertion that F52 did not sneak one in.

Declined, each considered:

- **A `booking_metrics_daily` rollup table.** A pilot boutique's twelve-week window is hundreds of rows (Risk 3 names the threshold). A rollup buys nothing measurable and costs a table, a migration, a writer, a backfill and a staleness question the dashboard would then have to answer in its own copy.
- **An `availability_snapshots` table so historical utilization becomes possible.** This is the recorded upgrade path and it stays recorded, not built (D4, Risk 8). It needs a scheduled job, and a job that has not run yet renders as zero capacity — a boutique onboarded last week would read 100% utilized for every week before the job started.
- **An index on `bookings(tenant_id, status)`.** RLS plus the `starts_at` range already narrow the scan to one tenant's window; adding a status index to serve a screen nobody has opened yet is the un-lazy thing. Risk 3 names the threshold.
- **A `DASHBOARD_VIEWED` audit action.** `audit_log.action` is plain TEXT with no CHECK, so it would need no migration either — which is exactly the bad reason to add one. It would be the first read-audit in the product and it would put a write on the most-hit read in the console, on every page load (D9).

### The window is twelve complete Sunday-start weeks, and the endpoint takes no parameters (D2)

**Fixed, not client-selectable.** `HISTORY_WEEKS = 12` — one quarter, twelve bars, the smallest thing that shows a season. The window is computed entirely from `today_jerusalem(self._clock)`:

```
today              = today_jerusalem(clock)                                   # Jerusalem calendar date
current_week_start = today - timedelta(days=jerusalem_day_index(today))       # this Sunday
first_week_start   = current_week_start - timedelta(days=7 * HISTORY_WEEKS)
from_instant  = combine(first_week_start,   time.min, tzinfo=BOUTIQUE_TIMEZONE).astimezone(UTC)
until_instant = combine(current_week_start, time.min, tzinfo=BOUTIQUE_TIMEZONE).astimezone(UTC)
```

Three properties, each load-bearing:

1. **Every week edge is computed in DATE space and converted once.** Israel's autumn transition is always a **Sunday** — the first day of the Israeli week — so the bucket containing it is 169 UTC hours and the March bucket is 167. `midnight_utc(2026-10-25) + 7 days` is `2026-10-31T21:00Z`; the real boundary is `22:00Z`. Advancing on instants misfiles an hour of Saturday-night bookings twice a year; advancing on `date` and converting each edge is exact, always. This is `list_day`'s lesson (`booking/owner.py:151-156`) applied one unit up.
2. **The current, in-progress week is excluded.** A partial final bar next to twelve full ones reads as a collapse in bookings, and every rate computed over a window that includes future appointments is skewed by construction — a future booking cannot yet be a no-show. The forward panel is what covers "right now". Declined: including the partial week (the final bar always reads as a crash), and marking it visually (a marked partial bar is still read as a trend by every human who glances at it). **The cost is a hole**: this exclusion ends the history at last Saturday while D4's forward window starts today, so 0–6 days — worst on a Saturday — are on no panel. That is Risk 13, accepted with its magnitude rather than papered over, and it is why no copy string may imply the two panels are a continuous span.
3. **No caller-supplied date reaches any arithmetic, so no overflow guard is needed.** `OwnerBookingService.list_day` opens with `if not datetime.date.min < date < datetime.date.max: raise DomainValidationError` because its router declares a bare `datetime.date` and `?date=9999-12-31` overflows in `date + 1 day` (`booking/owner.py:163-172`); `slot_window` clamps both bounds for the same reason (`storefront/service.py:288-299`). `today` comes from a real clock and can never approach either end of the `date` range, so F52's arithmetic is total with no guard. **That is the reason the endpoint takes no parameters** — not laziness alone.

**Bucketing a booking** is two lines and never touches a UTC instant:

```
d      = fact.starts_at.astimezone(BOUTIQUE_TIMEZONE).date()
bucket = d - timedelta(days=jerusalem_day_index(d))
```

The twelve buckets are pre-generated as `first_week_start + timedelta(days=7 * i)` and **zero-filled**, so a week with no bookings is a `0` bar and not a missing one.

Declined: `date_trunc('week', starts_at AT TIME ZONE 'Asia/Jerusalem')`. Postgres `date_trunc('week', …)` is ISO — it truncates to **Monday** — so every Sunday would be filed under the previous week, and the hardcoded zone string forks `BOUTIQUE_TIMEZONE`. The codebase contains **zero** SQL date functions: no `date_trunc`, no `AT TIME ZONE`, in app code or in any of the eleven migrations. Every timezone conversion in this product is a Python `.astimezone()` and F52 does not introduce the first exception.

Also declined: **bucketing on `created_at`.** It reads like "when the booking happened" and there is no index on it, so the aggregate would drop off `idx_bookings_tenant_starts` into a full tenant scan. The two answers also differ in meaning — `created_at` is demand (when brides booked) and `starts_at` is throughput (when appointments happen) — and only `starts_at` is comparable to the forward utilization panel sitting beside it on the same screen. Demand-over-time is a different metric that needs its own index, and F52 has no migration in scope.

And declined: **reusing `count_by_start` as the general historical read.** Its predicate is `status != 'cancelled'` because it mirrors the occupancy indexes (`db/repositories/bookings.py:452-455`). A cancellation rate computed under it has zero cancellations in the numerator by construction — the metric is structurally always 0%. Widening `count_by_start` is worse still: the slot engine depends on it, and the one thing that predicate must not do is change.

### Every metric definition is a pure function over one narrow projection (D3)

**One statement answers five of the six metrics**, and it is not a `GROUP BY`:

```sql
SELECT starts_at, created_at, status, cancelled_by, customer_id, appointment_type_id, appointment_type_name
FROM bookings
WHERE tenant_id = :t AND starts_at >= :from AND starts_at < :until AND deleted_at IS NULL
```

One range scan on `idx_bookings_tenant_starts`, half-open on the right, **every status**. Python then folds it six ways.

`created_at` (from `StandardColumns`, `models/base.py:21`) is in the projection for exactly one fold: `appointment_type_name` is snapshotted **at booking creation** (`models/booking.py:19-22`), so the newest snapshot of a renamed type belongs to the booking with the greatest `created_at`, not the greatest `starts_at` (D6). In a bridal boutique those two orders disagree routinely — a fitting booked in May for July carries an older snapshot than one booked in June for next week.

This is a deliberate departure from `aggregate_by_dress`'s SQL-side fold, and the reason is the whole point of this feature. `aggregate_by_dress` exists to avoid an N+1 across dress rows; here there is no N+1 either way — it is one bounded scan whether Postgres or Python does the counting. What differs is testability. **The six definitions are where this feature can be silently wrong**, and a `GROUP BY` can only be exercised against a live Postgres, i.e. in a `db`-marked module that first runs on CI. A pure fold over a list of frozen dataclasses is pinned by `tests/test_dashboard_math.py`, which runs in the fast no-Docker suite, with hand-written fixtures covering both 2026 DST weeks, a mid-window rename, a reused archived name, an empty tenant and every zero denominator.

**A narrow projection, not `select(Booking)`.** The ORM row would drag `notes` (free customer text), `manage_token_hash` (a credential hash) and `dress_name` into a process that only counts. Seven scalar columns is smaller *and* is the disclosure-minimizing choice; the docstring says so. None of the seven is customer-identifying text — `customer_id` is a key that never reaches the wire (D8), and `created_at` is a booking timestamp.

**Bound.** Worst case at pilot scale is 5 seats × 18 starts/day × 7 days × 12 weeks ≈ 7,560 rows of seven narrow columns, and that assumes every seat of every slot booked for a quarter straight. Realistic is 300–800. Risk 3 names the threshold at which this must become SQL-side `GROUP BY`s — and the per-request cost of that fold, on the console's most-hit read, is part of what that risk covers.

The **customer history** read cannot be folded into this scan, because it needs rows *outside* the window (D7). It stays a real aggregate, in the `aggregate_by_dress` shape.

**Soft delete.** `deleted_at IS NULL` is on every predicate — it is the house rule and it rides both partial indexes — even though no repository or service anywhere writes `bookings.deleted_at` today. Nothing in the UI or the copy may depend on deleted bookings existing.

**RLS.** Every read opens with `async with tenant_session(self._session_factory, tenant_id) as session:` and keeps the redundant explicit `Booking.tenant_id == tenant_id` predicate. This matters more here than on a row read: with no tenant context set, the policy's `current_setting('app.tenant_id', true)::uuid` is NULL, the comparison is NULL, and every row is filtered out — a `by_id` then 404s *visibly*, but an aggregate returns a perfectly plausible **all-zeros dashboard** with nothing in the response and nothing in the logs to say so. The isolation test must therefore assert both halves (Tests).

### Forward utilization: the grid comes from `materialize_slots(booked={})`, and slots.py is not edited (D4)

The forward window is `[today, today + 6]` — `FORWARD_WINDOW_DAYS = 7`, and the engine's window is **inclusive on both ends** (`slots.py:116-117, 134`), so `today + 7` would materialize eight days of capacity into a metric labelled seven and inflate the denominator by ~14% with nothing to reveal the error.

```python
window_end = today + timedelta(days=FORWARD_WINDOW_DAYS - 1)          # inclusive  -> today + 6
first = combine(today, time.min, tzinfo=BOUTIQUE_TIMEZONE).astimezone(UTC)
last  = combine(today + timedelta(days=FORWARD_WINDOW_DAYS),          # exclusive  -> today + 7
                time.min, tzinfo=BOUTIQUE_TIMEZONE).astimezone(UTC)

grid = materialize_slots(rules=…, exceptions=…, booked={},
                         window_start=today, window_end=window_end, now=now)
booked_by_instant = await bookings.count_by_start(session, tenant_id,
                                                  from_instant=first, until_instant=last)
capacity = sum(slot.capacity for slot in grid)
taken    = sum(min(booked_by_instant.get(slot.starts_at, 0), slot.capacity) for slot in grid)
utilization = taken / capacity if capacity else None
```

**The two bounds differ by one day and that is deliberate, not a typo.** `materialize_slots`'s `window_end` is a **date** and inclusive on both ends (`slots.py:116-117, 134`), so it is `today + 6`; `count_by_start` is **half-open on the right** over instants (`db/repositories/bookings.py:436-447`), so its ceiling is boutique-midnight of `today + 7`. This is exactly the three-line idiom `StorefrontService.list_slots` ships, comment and all — *"the right edge is half-open — start of the day AFTER `window_end`"* (`storefront/service.py:198-206`), mirrored in `slots_io.offered_slot` (`:50-55`). Writing `last = midnight(today + 6)` instead reads correct against the sentence "the window is `[today, today + 6]`" and is the mirror image of the `today + 7` denominator error: day 7's capacity stays in the denominator while day 7's bookings vanish from the numerator, understating `forward.utilization` by up to a seventh, permanently and silently. The `db` test pins it by putting its booked slot on `today + 6` specifically (Tests).

**`forward.booked` on the wire is `taken` — the clamped grid sum — never `sum(booked_by_instant.values())`.** The local is named `booked_by_instant` for exactly that reason: the two differ precisely on the tenant the next paragraph defends against, and shipping the dict sum would put two integers on one card that visibly disagree with the percentage beside them. `forward.booked <= forward.capacity` and `forward.utilization == forward.booked / forward.capacity` are both pure-tested invariants.

**Why `booked={}` and not the engine's normal output.** `materialize_slots` **drops** every slot where `taken >= capacity`, with the reason in the code: *"a public response that enumerated them would disclose the boutique's booking density"* (`slots.py:149-152`). Summing `capacity` over `StorefrontService.list_slots` or `OwnerBookingService.list_slots` therefore omits precisely the fully-booked slots — the ones that make utilization high. The resulting number is biased downward, can never reach 100%, and the error **grows as the boutique gets busier**, i.e. it is worst exactly when the number matters. Passing `booked={}` makes `taken` 0 at every instant, and `CHECK (capacity > 0)` (`0005_boutique_settings.py:65`) guarantees `0 < capacity` holds everywhere, so nothing is dropped for fullness. The grid comes back complete with zero change to the engine.

**Why iterate the grid and not the dict.** `count_by_start` can contain instants that are no longer on the grid at all — a booking made under a weekly rule the owner has since deleted, or on a date a later exception closed. Those rows exist and are counted but have no capacity behind them, so summing the dict produces `booked > capacity` and a utilization above 100%. Iterating the grid and clamping with `min(booked, capacity)` is the same defensive posture `Slot.remaining` takes with `max(capacity - booked, 0)` for the identical anomaly (`slots.py:36-41`).

**Where it lives: one new coroutine in `slots_io.py`.** That module's docstring already claims the job — *"where the reads that FEED `materialize_slots` live"* — and currently says it holds *"exactly one caller-facing question"* (`slots_io.py:1-12`); F52 adds a second and edits that sentence. `forward_capacity(session, *, tenant_id, window_start, window_end, now, rules, exceptions, bookings) -> ForwardCapacity(capacity: int, booked: int)` does the three reads `StorefrontService.list_slots` does (`storefront/service.py:207-218`) and calls the engine once. `ForwardCapacity.booked` is `taken`, the clamped grid sum.

**This panel deliberately republishes the aggregate the anonymous surface is fenced against, and that is a posture, not an oversight.** `materialize_slots` drops full slots because *"a public response that enumerated them would disclose the boutique's booking density"* (`slots.py:149-152`); `capacity` is in the storefront's `FORBIDDEN_KEYS` and there is a dedicated test asserting `remaining` must not ship either (`tests/test_storefront_api.py:215, 1463-1480`). F52 ships `forward.capacity` and `forward.booked` — seven-day sums of exactly those two quantities. It is allowed because the route is behind `require_role(OWNER, SHIFT_MANAGER)` on a host-resolved tenant reading its own rows, and because `GET /manage/slots` already ships **per-slot** `capacity` and `remaining` to those same two roles (`booking/owner_router.py:306-330`) — strictly more disclosure than two integers. What must not happen is `forward_capacity` growing a slot-list return: that is the shape the fence exists to stop, and it is the same footgun class the `include_full` flag was declined for below. **That sentence goes in the coroutine's docstring**, where the next caller will actually read it.

Declined, each considered:

- **`include_full: bool = False` on `materialize_slots`.** It works and the diff is small, but it is one rung too low: `booked={}` produces the identical grid with zero change to the engine. Worse, the flag's only purpose is to switch off a disclosure control on the function whose other caller serves anonymous traffic — a permanent footgun where a future `include_full=True` on the storefront path leaks booking density, and no test would catch it because the flag is legitimate here.
- **Re-walking the grid inside `DashboardService`.** *"A second materializer is the one thing slots.py exists to forbid"* (`booking/owner.py:126-129`).
- **`slot_window()` to bound the forward window.** Its whole job is clamping a *caller-supplied* value F52 does not accept, so here it is a no-op that returns `(today, today+6)` — and calling it would imply the endpoint takes a window it does not. It is also actively wrong for anything historical: its floor is clamped to `today` unconditionally, so a past request returns an **inverted** pair with no exception and materializes to nothing (`storefront/service.py:296-312`). Named so nobody reaches for it later.
- **Utilization as booked minutes over open minutes, using `appointment_types.duration_minutes`.** *"A slot is a START TIME. It has no duration and no end … it does not shape the grid and no booking blocks a later start"* (`slots.py:9-14`). A minutes-based ratio would be arithmetic over geometry the booking engine explicitly refuses to reason about, and it would disagree with what the engine actually enforces. **Capacity here means seat-slots: one start time × its capacity.**
- **Deriving capacity ourselves from the rules.** There are two reconciliation rules in the engine, in opposite directions, twelve lines apart: an exception day inherits the **min** of the weekday's rule capacities (`slots.py:69-78`) while an instant covered by two overlapping rule windows takes the **max** (`:141`). Reimplementing "the capacity rule" from either half produces numbers that disagree with the booking engine on real multi-window days. Read `Slot.capacity` off the engine's output; never compute it.
- **Reconstructing historical capacity from soft-deleted `availability_rules`.** The rows survive with `created_at`/`deleted_at` so a validity-interval join looks feasible. It needs a reader nobody has (`list_active` pins `deleted_at IS NULL`), a temporal join, and a second grid walk over historical rule sets — the second materializer. And a boutique that never edited its hours has one row set whose `created_at` is its first save, so every earlier week reconstructs to zero capacity and divides by zero. Risk 8, and the snapshot job stays the recorded upgrade path.

### Rates: exact numerators, exact denominators, and a defined answer at zero (D5)

All four counts are over the window, all four statuses, `deleted_at IS NULL`, bucketed by `starts_at`.

| Metric | Numerator | Denominator | At zero denominator |
|---|---|---|---|
| `weeks[].bookings` | bookings in the bucket with `status <> 'cancelled'` | — (a count, not a rate) | `0`, zero-filled |
| `cancellation_rate` | `status = 'cancelled'` | **all four statuses** | `null` |
| `no_show_rate` | `status = 'no_show'` | `no_show + completed` — **appointments whose outcome was actually recorded** | `null` |

**`weeks[].bookings` counts appointments that were NOT cancelled — the seat-slots the boutique held.** Not "appointments that stood": the invariant `sum(weeks[].bookings) == confirmed + no_show + completed` (asserted by a pure test) puts `no_show` rows in the bar, and a no-show is by definition an appointment that did not stand; `confirmed` rows are unrecorded outcomes that may include further no-shows. Non-cancelled seat-slots is the right answer to "how busy were we", and it is what the bar must be **labelled** as — a Hebrew label promising attendance, on a chart that includes no-shows, on the same screen as a no-show rate, is a contradiction a pilot owner finds in her first week. The copy deck carries this wording verbatim (Copy). Cancellations are the tile beside it; putting them in the bar too would double-count the same event on one screen.

**The no-show denominator is the sharp one.** Every booking in the window is in the past, so a row still reading `confirmed` is an appointment whose outcome the owner never recorded — `no_show` and `completed` are the only two verbs that record one, and both are `past_only` (`booking/owner.py:324-325`). Counting unmarked appointments as attended silently rewards owners who never use the console; excluding them is honest but leaves a rate that can be computed over three appointments out of forty. So **`status_totals.confirmed` ships alongside as the unclassified count**, and the copy states the denominator in words. No new concept, one integer already in hand.

Declined: **deriving no-shows from `attendance_confirmed_at IS NULL`.** That column is set by the bride tapping "confirm" on her F16 reminder SMS link — it means she said she is coming, not that she came. Most bookings never have it set because most people do not tap SMS links, and a booking can carry a confirmation *and* still be a no-show. `set_status`'s docstring names the distinction explicitly (`db/repositories/bookings.py:249-252`). A rate built on it would overstate no-shows by an order of magnitude.

**Cancellations are attributed, not just counted.** `cancelled_by` is CHECK-pinned to `('customer','owner')` and `cancel` is its only writer, so `cancelled_by_customer` and `cancelled_by_owner` come free from a column already in the projection. Without them a boutique that closed for a week and cancelled twenty appointments itself reads a 20% cancellation rate as customer flakiness. The response ships **one** rate (the epic's scope) plus the two counts; `cancelled_by_customer + cancelled_by_owner <= status_totals.cancelled` is the stated invariant, because a row cancelled before 0010 added the columns would carry NULL and is counted in neither.

**Busiest appointment types: group by the ID, label from the snapshot.** `TOP_APPOINTMENT_TYPES = 5`, ranked on the **total** sort key `(-count, name, str(appointment_type_id))`.

Count-then-name is not enough, and it fails on precisely the case this design section exists to handle: a name freed by archiving and legally reused by a **second** `appointment_type_id` (the partial unique index is on `deleted_at IS NULL` exactly so that reuse is legal). When those two IDs have equal counts, count and name are both ties and the order falls through to `sorted`'s stability over the fold's insertion order — which is the projection's row order, and D3's statement carries no `ORDER BY`, so Postgres may return it differently across plans, vacuums or restarts. The `str(id)` third element makes the order total for one extra tuple element and no query change.

Both available keys are lossy alone, and the failures are mirror images:

- Joining `appointment_type_id` to `AppointmentTypesRepository.list_active` drops any type archived during the window (`list_active` pins `deleted_at IS NULL`), so its bookings render with a blank label or vanish.
- Grouping on the snapshot `appointment_type_name` splits one type renamed mid-window into two chart rows, **and** merges two different types into one when a name freed by archiving is reused — the partial unique index is on `deleted_at IS NULL` specifically so that reuse is legal (`0005_boutique_settings.py:52-54`).

**Amended (plan C2) — the fold's predicate is `status != 'cancelled'`, the same one `weeks[].bookings` and the customer cohort use.** D6 previously said only "sum the counts", leaving the predicate unstated while the deck already reused `dashboard.bookingsColumn` — «תורים שלא בוטלו», *appointments not cancelled* — as the types table's count header (`copy.md` §5, §8). Three predicates on one screen would be a defect the owner finds in her first week: a type count higher than the sum of the bars above it, under a header that says otherwise. One predicate for every count this screen labels «תורים שלא בוטלו». The invariant `sum(appointment_types[].bookings) <= sum(weeks[].bookings)` is pure-tested — **`<=`, not `==`**, because `TOP_APPOINTMENT_TYPES = 5` truncates (Risk 14). Declined: a second column key for the types table (a second Hebrew word for one number, and it would reopen the deck for a distinction the owner does not have).

So: fold the **non-cancelled** projection by `appointment_type_id`, sum the counts, and take the label from the sub-group with the greatest **`created_at`** — the most recently *written* snapshot, which is the one closest to the type's current name. **Not the greatest `starts_at`.** `appointment_type_name` is snapshotted when the booking is created (`models/booking.py:19-22`), so `starts_at` orders by *appointment date*, which in a boutique where brides book months ahead routinely disagrees: rename the type on 1 June; booking A created 1 May for 20 July carries the old name, booking B created 15 June for 20 May carries the new one; `max(starts_at)` picks A and renders the label every booking made since June has already stopped using. `max(created_at)` picks B. That is the one reason `created_at` is the seventh column of D3's projection.

No join to `appointment_types` at all. Archived types keep a name, renames do not split a bucket, reused names do not merge two. Five lines of Python, pinned by a pure test that exercises all three cases — with the rename fixture deliberately built so `created_at` and `starts_at` order the two bookings **differently**, otherwise the test passes under either rule and pins neither.

### New-vs-returning and repeat rate survive the phone-correction re-point (D6, D7)

**D6 — the definitions.** The cohort is the set of distinct `customer_id` on **non-cancelled** bookings in the window (a bride who booked and cancelled did not visit).

| Field | Definition | At zero |
|---|---|---|
| `customers.total` | `\|cohort\|` | `0` |
| `customers.new` | cohort members whose **first-ever** non-cancelled booking at this tenant falls inside the window | `0` |
| `customers.returning` | `total - new` | `0` |
| `customers.repeat_rate` | cohort members with **≥ 2** non-cancelled bookings ever / `total` | `null` |

"First-ever" and "ever" are both evaluated **as of `until_instant`**, so a fitting booked for next month cannot retroactively change last quarter's numbers.

`new` and `repeat_rate` are genuinely different questions and both ship: a bride who booked twice inside the window is **new** (her first-ever booking is in it) and **counts toward the repeat rate** (she has two). One is cohort composition, the other is retention.

**D7 — why both are derived from `bookings` and never from `customers`.** `OwnerBookingService.correct_phone` has two branches. Non-collision: `customers.phone` is updated in place. Collision — the corrected number already belongs to another live customer — **the booking is re-pointed** via `BookingsRepository.set_customer_id` to the existing customer row, `customers.phone` is untouched, and **both customer rows survive** because *"the original may be a real other person"* (`booking/owner.py:641-695`; `set_customer_id` at `db/repositories/bookings.py:167-202` has exactly that one caller).

After one phone correction a tenant therefore has customer rows with zero bookings, bookings attached to a customer row created long after them, and customers whose `created_at` post-dates their own earliest booking. Any metric reading `customers.created_at` — or counting rows in `customers` — is wrong, **and only at the tenants that actually used the F15 remedy**, so it looks right in dev and lies in production.

**What that write actually moves — precisely, because the spec previously overstated it.** `set_customer_id` is called with `allowed_from=(BookingStatus.CONFIRMED.value,)` and `not_before=now`, and the repository predicate is `status IN (allowed_from) AND starts_at > not_before` (`booking/owner.py:679-686`, `db/repositories/bookings.py:186-196`). So **exactly one booking moves** — the one being corrected, and only if it is confirmed and in the future. Every other booking of the old customer row stays where it is. The old row is therefore orphaned *only* when the corrected booking was its sole booking; in every other case both rows keep bookings and both appear in the cohort.

The booking-derived answers are still the right ones, and for a narrower reason than "the orphan never appears": every number here is a fold over **bookings**, so a customer row that never held a booking cannot enter any of them, and a row's `created_at` — which the phone remedy makes meaningless as a "first seen" date — is never read. Under the naive `customers`-derived definition the same tenant would have counted zero-booking rows as real people and would have dated a bride from a row created after her first visit.

What the booking-derived definitions do **not** cure is history that was already split across two rows: see Risk 12. That is a property of the F15 remedy, not of these metrics, and F52 records it rather than assuming it away.

**The implementation is one aggregate in the `aggregate_by_dress` shape** — this is the one read that cannot fold into D3's projection, because it needs rows outside the window:

```python
async def history_by_customer(session, tenant_id, customer_ids, *, until_instant
                              ) -> dict[UUID, CustomerHistory]:   # (first_starts_at, bookings)
```

Empty-input short-circuit, `select(Booking.customer_id, func.min(Booking.starts_at), func.count())`, `.where(tenant_id ==, customer_id.in_(…), status != 'cancelled', starts_at < until_instant, deleted_at.is_(None))`, `.group_by(Booking.customer_id)`. It rides `idx_bookings_tenant_customer`. The cohort ids come from D3's projection, so this is the request's **second of three** booking statements — the third is `count_by_start`, issued inside `forward_capacity` (D4).

### The API (D8)

New package `Backend/app/dashboard/` — `service.py` (`DashboardService`), `router.py`, `schemas.py`.

Not two files in `app/booking/`: the dashboard reads across `bookings` **and** the availability pair, so it belongs to neither domain, and `booking/schemas.py` is a shipped file that would gain ten response models for a surface that is not the booking API. **`app/notifications/` is the in-repo precedent** for the `service.py` / `router.py` / `schemas.py` trio in a package that owns no table. (`app/platform/` is *not* the precedent for this shape and is not cited: it ships `__init__.py`, `repository.py` and `service.py` — no router, no schemas.) F51's D6 declined a new package for one router for the opposite reason: `staff_users` is an auth table and `StaffService` sits beside `AuthService`.

`DashboardService(get_session_factory(), clock: Clock | None = None)` is constructed in `create_app()` onto `app.state.dashboard_service`, reached through `get_dashboard_service(request)` behind a `Service = Annotated[…]` alias — the `booking/owner_router.py:64-89` pattern, which is what lets the fast API test swap in a duck-typed `FakeDashboardService`. **Its own clock**, resolved with the house one-liner (`booking/owner.py:143-145`); it never borrows `StorefrontService._clock`, and `create_app` wires none (the parameter exists for tests).

Router: `APIRouter(prefix="/manage", dependencies=[Depends(_no_store), Depends(require_role(StaffRole.OWNER, StaffRole.SHIFT_MANAGER))])`, its own **fourth local three-line `_no_store`** for the reason `auth/staff_router.py:22-27` records, included in `create_app()` after `staff_router` with the shadowing comment the **catalog, owner-booking and staff** includes carry (`main.py:678-691` — the other three includes at `:675-677` carry none, because they are the first on their prefixes) — six routers now mount `/manage`.

**The handler resolves the tenant from the host, not from the session.** The whole handler is:

```python
@router.get("/dashboard")
async def get_dashboard(request: Request, service: Service) -> DashboardResponse:
    return await service.dashboard(get_current_tenant(request).id)
```

`get_current_tenant(request)` is what **every** shipped `/manage` handler without exception uses (`auth/staff_router.py:84, 92, 112, 134`; `booking/owner_router.py:173, 188, 205, 214, 225, 234, 252, 274, 288, 323`), and it is host-derived — `TenantResolutionMiddleware` binds it from the Host header and nothing else (`tenancy/middleware.py:57-76`). The other available source, `StaffContext.tenant_id` (`auth/service.py:19-24`), is session-derived. They are equal in practice because `get_current_staff` resolves the session against the host-derived id under RLS, so a foreign cookie does not resolve — but they are different trust paths and F52 is the first `/manage` route with **no** independent reason to inject `staff` at all (no audit row, no self-guard, D9), which makes it exactly the route where an implementer reaches for the session id because it is already in hand. No `Staff` parameter is declared; the `RoleGate` runs router-level and needs no binding here. `test_dashboard_api.py`'s `FakeDashboardService` records the `tenant_id` it was called with and asserts it equals the resolver's `TENANT.id` — that pins the source at the HTTP boundary, which the `db` isolation test (running below the router) cannot.

**No rate limiter**, and the reason is one leg, not two. No `/manage` router carries a limiter and F52 does not introduce the first one; the storefront limiters exist because that surface is anonymous. **CSRF fencing is explicitly NOT part of this route's posture** — `CsrfOriginMiddleware` gates on `request.method in MUTATING_METHODS` (`csrf.py:15, 48`) and this is a GET, which D9 relies on in the opposite direction. The protection here is the session cookie and the role gate, alone. The per-request cost that leaves unbounded is Risk 3's, not a new one.

| Method | Path | Params | Answers |
|---|---|---|---|
| `GET` | `/manage/dashboard` | **none** | `DashboardResponse` |

Real HTTP verbs and no `@Post("/list")`: the shipped `/manage` convention, ruled by F15's D7 and restated in two shipped router docstrings. One nested object, no pagination envelope, no request body, no `ForbidExtraModel` (nothing to forbid extras in).

```json
{
  "generated_on": "2026-07-31",
  "history": {
    "from_date": "2026-05-03",
    "to_date":   "2026-07-25",
    "weeks": [
      { "week_start": "2026-05-03", "bookings": 23 }
    ],
    "status_totals": {
      "confirmed": 12, "cancelled": 9, "no_show": 4, "completed": 88
    },
    "cancellation_rate": 0.079,
    "cancelled_by_customer": 7,
    "cancelled_by_owner": 2,
    "no_show_rate": 0.043,
    "appointment_types": [
      { "appointment_type_id": "…", "name": "מדידה", "bookings": 61 }
    ],
    "customers": {
      "total": 74, "new": 51, "returning": 23, "repeat_rate": 0.31
    }
  },
  "forward": {
    "from_date": "2026-07-31",
    "to_date":   "2026-08-06",
    "capacity": 84,
    "booked": 37,
    "utilization": 0.44
  }
}
```

- `generated_on` is `today` in Jerusalem — the frontend renders no "as of" it computed itself.
- `history.from_date` is the first bucket's Sunday; `history.to_date` is the **last covered Jerusalem date**, i.e. the Saturday before the current week. `weeks` is always `HISTORY_WEEKS` entries, ascending, zero-filled.
- **The example above is the worked output of D2's arithmetic for `generated_on = 2026-07-31`, and it is normative.** That date is a Friday, so `jerusalem_day_index = 5`, `current_week_start = 2026-07-26`, `first_week_start = 2026-07-26 − 84d = 2026-05-03`, and the last covered date is `2026-07-25`. Three shape invariants follow and all three are pure-tested (Tests): `to_date == from_date + 7*HISTORY_WEEKS − 1 day`, `to_date < generated_on`, and `weeks[-1].week_start == generated_on − (jerusalem_day_index(generated_on) + 7) days`. Any payload where `to_date >= generated_on`, or whose last bucket contains `today`, is the partial-week shape D2 refuses — copy this block into `schemas.py`, the TS interface and both fixtures only after re-checking it against those three lines.
- `cancellation_rate`, `no_show_rate`, `customers.repeat_rate` and `forward.utilization` are `float | None`. **`null` means "not computable", never "zero"** — and the console must render those two differently (D10).
- **Precision is a wire contract, not a rendering accident.** The backend emits the **unrounded** quotient (`9/113 == 0.07964601769911504`); the example above is rounded for readability only. The console renders one decimal place, and a rate whose numerator is non-zero but rounds to `0.0%` renders the copy-deck string **`dashboard.rateUnderFloor`** instead — otherwise a boutique with one cancellation in 250 bookings renders `0%`, colliding with the true-zero fact D10 makes load-bearing. **Amended (plan C1): `<0.1%` was this spec's shorthand for the fact, never a literal.** The shipped value is «פחות מ־0.1%» (`copy.md` §3) — a bare `<` inside an RTL paragraph mirrors and reads as a bracket, and this string sits unisolated in Hebrew running text. Every assertion is on the key, never on an ASCII literal.
- `forward.to_date` is inclusive, matching the engine's window.
- Nothing in the payload identifies a customer. `customer_id` is folded away in the service; only counts reach the wire. `appointment_types[].name` is an appointment **type** label, never a person's — which is why F52's own forbidden-key set cannot contain the bare key `name` (Tests).

### Errors (D9)

| Raised | Code | Status | Handler |
|---|---|---|---|
| no session cookie | `NOT_AUTHENTICATED` | 401 | existing |
| `shift_manager` — **not raised**, both roles are admitted | — | — | — |
| an out-of-enum role | `NOT_AUTHORIZED` | 403 | existing (F31, fails closed) |

**No new error code, no new body, no new handler, no `main.py` change.** The endpoint takes no input, so there is nothing to 400 on, and it reads rows that may legitimately not exist, so there is nothing to 404 on — an empty tenant is a valid all-zero dashboard, not a miss.

`CSRF_ORIGIN_MISMATCH` is **not** in F52's set: `CsrfOriginMiddleware` fences `MUTATING_METHODS` only (`csrf.py:48`) and this is a GET. That matters mechanically — `test_dashboard_api.py`'s `test_every_spec_error_code_is_asserted` hand-unions the codes raised in dependency-solving, and unioning the CSRF code the way `test_staff_api.py:458-466` does would red-fail against a set that cannot contain it.

**No audit row.** No GET handler in this product writes one — not the booking day list, not the booking detail that renders a bride's phone and free-text notes, not the owner-only staff list. A landing screen is the most-hit read in the console and an audit row would make every page load a write.

### The section is the console's landing screen (D10)

`NAV` gains a row **first**, with `roles: ALL`, and `useState<SectionKey>("profile")` becomes `useState<SectionKey>("dashboard")`. That is the whole of the landing change: `activeKey` already falls back to `reachable[0]?.key` (`App.tsx:94-96`), and with dashboard first and reachable by both roles, the fallback and the initial state now agree.

**No chart library, and no `packages/ui` promotion** — that is the Q2 self-approval hinge. `packages/ui` exports no chart, bar, meter, sparkline or gauge primitive, and the repo contains zero `role="progressbar"`, `role="meter"`, `<meter>` or `<progress>` elements. F52 adds none.

The weekly bar is a track `div` (`bg-border rounded-sm h-2`) containing a fill `div` sized `style={{ inlineSize: \`${pct}%\` }}` — **`inlineSize`, not `width`**, so it grows from the inline-start edge in RTL — and the whole bar is `aria-hidden="true"` decoration beside a real text label carrying the number in `<bdi dir="ltr">`. It is **not** `role="progressbar"`: that role announces a task's completion, not a ratio of a static quantity, and an AT would read the utilization bar as an in-flight operation. `SetupProgress` is the shipped precedent for `aria-hidden` marks beside a word.

Colour and length never carry meaning alone. **The section mounts no `Badge` at all** — this is the record of why one was considered and declined, not of one that renders. `Badge` has exactly five variants and deliberately **no gold** one — `gold-strong` is 3.80:1, below the 4.5:1 text floor, and a Badge is always `text-xs`; a gold marker is a `text-gold-text` span. Adding a variant would be a `packages/ui` promotion, which is precisely what the Q2 argument forbids.

`null` vs `0`: a rate that is `null` renders its own sentence («אין עדיין מספיק נתונים» register), never `0%`. A boutique with no cancellations shows `0%`; a boutique with no bookings at all shows the sentence. Those are different facts and the copy deck gives them different strings.

### One fetch, on mount, and no poll (D11)

`useEffect` with `let cancelled = false`, no interval, no refetch control — `BookingsSection.tsx:27-49` verbatim in shape. A dashboard of twelve complete past weeks changes at most once a week; the forward panel changes when someone books. Neither justifies the console's first repeating fetch.

**This declines F51's Risk 3 explicitly.** That risk records that `api.me()` runs once at mount, so an owner demoted mid-session keeps a stale nav item, and names F52 as *"the natural place to refresh `me()`"* because F52 was expected to introduce a poll. F52 does not, so Risk 3 stays open and moves to **F34**, whose 5-second board poll is a real repeating fetch with somewhere for a `me()` refresh to hang. Recorded here so the next reader does not conclude it was forgotten.

---

## Frontend changes

### Files

| File | Change |
|---|---|
| `Frontend/apps/manage/src/components/DashboardSection.tsx` | **new** — the whole section |
| `Frontend/apps/manage/src/App.tsx` | `SectionKey` gains `"dashboard"`; `NAV` gains a **first** row `{key:"dashboard", labelKey:"nav.dashboard", roles: ALL}`; `useState<SectionKey>("dashboard")`; the render line; the import |
| `Frontend/apps/manage/src/api.ts` | a `// --- dashboard wire types (mirror backend/app/dashboard/schemas.py) ---` banner before `// --- endpoints ---`, the interfaces, and `getDashboard(): Promise<DashboardResponse> { return apiFetch("/manage/dashboard"); }` |
| `Frontend/apps/manage/src/i18n/he.ts` | `nav.dashboard` + a flat `dashboard.*` block |
| `Frontend/apps/manage/src/i18n/ar.ts` | the same keys, the approved Hebrew standing in, **never** `""` |
| `Frontend/apps/manage/src/lib/jerusalem.ts` | **amended, plan C3** — `plainDate(iso: string): string`, two lines, beside the existing helpers |
| `Frontend/apps/manage/src/__tests__/Nav.test.tsx` | **required edits, see below** |
| `Frontend/apps/manage/src/__tests__/i18n.test.ts` | `HE_F52` constant folded into `HE` |
| `Frontend/apps/manage/src/__tests__/jerusalem.test.ts` | **amended, plan C3** — the `plainDate` describe block |
| `.planning/design/screens/manage-dashboard/manage-dashboard.md` + `copy.md` | **new** — Task 1, before any frontend code |

**Amended (plan C3) — `generated_on`, `from_date` and `to_date` are plain Jerusalem calendar dates on the wire, not instants, and need their own helper.** The deck's rendering rules (`manage-dashboard.md:99`) require it and the file table above previously named neither file. Every shipped helper in `lib/jerusalem.ts` takes an **instant** string and runs it through `new Date()` plus a `timeZone: Asia/Jerusalem` formatter; passing `"2026-05-03"` through `jerusalemDate` parses it as UTC midnight and re-zones a date that was never in a zone — it returns the right day only because Jerusalem is ahead of UTC, which is the exact class of bug that file exists to prevent. So `plainDate(iso)` splits the string and never constructs a `Date`:

```ts
const [y, m, d] = iso.split("-");
return `${Number(d)}.${Number(m)}.${y}`;
```

with a comment stating it takes a **plain date, never an instant**. The suite runs under `TZ=America/New_York` (`apps/manage/package.json:11`), which is what gives the assertion bite: a device-clock `new Date("2026-05-03").toLocaleDateString()` prints **2.5.2026** there, so a test pinning `plainDate("2026-05-03") === "3.5.2026"` fails the moment someone routes a wire date through a `Date`.

The deck folder is named after the **screen**, not the queue slug: the shipped decks are `manage-staff/`, `manage-catalog/`, `manage-booking/`, `owner-bookings/`, `shift-board/`. Likewise the i18n prefix follows the section (`dashboard.*`), not the feature id.

**No new `packages/ui` component and no promotion** (D10). The section mounts `SectionHeading`, `Card` and `Skeleton` — shipped, and all three exported from `packages/ui/src/index.ts`. It mounts **no** `EmptyState` (the layout table forbids it in the zero-data state) and **no** `Badge` (no tile places one); both are named here only so the Q2 self-approval argument enumerates what actually renders.

**`packages/api-client` is not touched** — it is a three-file stub and each app ships its own `src/api.ts`.

### Adding a nav row is not an `App.tsx`-only change

**Amended (plan C4): `Nav.test.tsx` breaks in FIVE places, not four, and two of them are test names.** Verified line-by-line against the shipped file — the four below are all real, and there is a fifth edit in the same file that a builder who counts to four will leave red. All five land in the same commit as the `App.tsx` change:

1. `NAV_LABELS` is a hardcoded seven-element array compared with `toEqual` — order-sensitive, exact equality. The dashboard label goes at index 0.
2. The shift-manager test asserts `NAV_LABELS.slice(0, 6)`; it becomes `slice(0, 7)`.
3. The handover test asserts the same slice **and** that «פרופיל והגדרות» carries `aria-current="page"` after re-login. Making dashboard the landing section breaks that assertion outright, because `reachable[0]` is now dashboard — the expectation moves to the dashboard label.
4. `vi.mock("../api")` replaces the whole `api` object with a hand-listed set of `pending` methods. A `DashboardSection` calling `api.getDashboard()` against that mock throws `TypeError: api.getDashboard is not a function` on mount and red-fails **all five** nav tests with an error that names the nav, not the dashboard. `getDashboard: pending,` goes in the factory.
5. **The two test NAMES** (`:67`, `:74`) — «shows an owner all **seven** sections…» and «shows a shift manager **six** sections…» — become eight and seven. A test whose name contradicts its assertion is a landmine for the next reader.

Two shipped assertions in that file are **unaffected and must not be touched** — they are the neutrality proof for the nav row: `:82-93` (an out-of-enum role still reaches an empty nav, because `roles: ALL` admits `owner`/`shift_manager` only) and `:115-116` (an owner clicking «צוות» still gets `aria-current` on it).

### Wire types

Mirrored field-for-field in **snake_case**. There is no case-conversion layer in this repo — `api.ts:1-5` states it — and a camelCase interface compiles fine and reads `undefined` at runtime on every field. Nullable rates are `number | null` in TypeScript, matching `float | None`.

### Layout and states

`BookingsSection.tsx` is the template, verbatim in shape.

| Screen | State | Treatment |
|---|---|---|
| Section | loading | `<Skeleton variant="text" lines={6} />` — **`variant="text"`, never the default `"block"`**, which renders `h-full w-full` and collapses to zero height inside a parent with no intrinsic height |
| Section | load failure | one `<p role="alert" className="text-sm text-ink-muted">` — the **outage** register, no retry control. The catch sets only `loadError` and deliberately leaves the data state `null`, so the empty state can never stack on the outage message |
| Section | loaded, zero data | the tiles render `0` / the not-computable sentence; **no `EmptyState`** — a boutique with no bookings yet still has a real dashboard, and an `EmptyState` would hide the forward panel that tells her the grid is open |
| Weeks | all zero | twelve zero bars plus the announced total in the `role="status"` region |
| Forward | `capacity == 0` | the not-computable sentence, naming closed hours rather than zero demand |
| Types | empty list | one muted line, not a `Card` full of nothing |

Card padding is **not** overridden: `cn()` is a plain `.filter(Boolean).join(" ")` with no conflict resolution, so a consumer `p-0` and `Card`'s baked-in `p-6` are same-specificity rules and the built stylesheet emits `.p-0` first — the override is silently inert.

Every KPI number is wrapped `<bdi dir="ltr">`; any interpolated Hebrew sentence carrying a count goes through the shipped `isolateLtr` from `lib/booking.tsx` (reused, not re-implemented). Dates are rendered through `lib/jerusalem.ts`, never an unzoned `toLocaleDateString`.

Physical-direction properties and raw hex colours are self-enforced here: `scripts/qa-greps.sh` scopes its `no physical direction props` and `no raw hex colours` checks to `apps/storefront/src` only, and its unzoned-date-read check prints an advisory line without setting a failing status. `make lint` will not catch either in this section.

### Copy (Hebrew-first, `dashboard.*`)

Authored in `copy.md` as Task 1, in the shipped two-file deck shape with a `| Key | What it must say | Approved Hebrew (he) | ar (untranslated) | Status |` table, under the recorded register rules:

- **Zero exclamation marks** (pre-decided #5) — mechanically enforced over `HE`.
- **No string may contain «נשלח», «תישלח» or «בדרך»** — the guard exists for SMS claims, but «בדרך» is a natural Hebrew word for a rising trend and would red-fail a test whose message is about sends. The deck records the rule so the copy is written around it rather than discovering it.
- **The no-show denominator is stated in words**, not implied by a percentage sign (D5).
- **The weekly bar is labelled as appointments the boutique HELD — seat-slots not cancelled — never as appointments that took place** (D5). The bar includes `no_show` rows by its own asserted invariant, and it sits on the same screen as a no-show rate; a label promising attendance contradicts the tile beside it.
- **A `dashboard.rateUnderFloor` string**, for a rate whose numerator is non-zero but rounds to `0.0%` at one decimal. Distinct from both `0%` (a true zero) and the not-computable sentence (a `null`) — three facts, three strings. **Amended (plan C1)**: the deck ships «פחות מ־0.1%», not an ASCII `<0.1%`, and the spec's earlier `<0.1%` was shorthand for the fact.
- **The forward number is labelled as remaining offerable capacity in the next seven days, from now** — not "next week", which would imply a fixed window (Risk 6).
- **One error string, `dashboard.loadFailed`.** No code→Hebrew map — and the reason is **not** that either code is unreachable. Both are reachable: `apiFetch` has no 401 interceptor (it just throws `ApiError(401, …)` to the section, and `App.tsx` clears `staff` only on the mount-time `me()` rejection or on logout), and `NOT_AUTHORIZED` is reachable *because of D10's landing change* — `RoleGate` fails closed on any role string the enum does not know (`auth/dependencies.py:40-62`), `reachable` is then empty, and `reachable[0]?.key ?? section` lands such a staffer on the initial section, which is now the dashboard rather than a 200-ing Profile panel. The reason there is no map is that the section renders `t("dashboard.loadFailed")` for **any** `ApiError` — `BookingsSection`'s shape — so no code needs a Hebrew string. That also keeps `errorMessage()`'s verbatim **English** server text off this screen. `DashboardSection.test.tsx`'s outage-alert case covers the 403 explicitly.
- **`null` rates get their own sentence**, distinct from `0%` (D10).

---

## Testing

Tests marked `db` run **only on CI** — there is no Docker locally, so `test_dashboard_db.py` is first exercised on the CI runner, which runs the unfiltered `uv run pytest -q`. `make test` is `-m "not db"` and passing it proves nothing about that module. **None of F52's tests are `s3`-marked.**

**`Backend/tests/test_dashboard_math.py`** (new, no marker, **the module that carries this feature**) — pure functions over hand-built `BookingFact` lists, no database, no app:

- **The window derivation itself, against a frozen clock — the test whose absence let a wrong example payload ship.** For `today = 2026-07-31` (a Friday, `jerusalem_day_index = 5`): `from_date == date(2026, 5, 3)`, `to_date == date(2026, 7, 25)`, `to_date < generated_on`, `to_date == from_date + timedelta(days=7 * HISTORY_WEEKS - 1)`, and `weeks[-1].week_start == generated_on - timedelta(days=jerusalem_day_index(generated_on) + 7)`. Repeated for a **Sunday** `today` (the boundary where `current_week_start == today`) and for a **Saturday** `today` (the widest exclusion). Plus the exclusion itself: a booking whose `starts_at` falls inside the current in-progress week appears in **no** bucket and in **no** `status_totals` entry. Every rate assertion below is invariant to a uniform window shift, which is exactly why this one has to be separate.
- **Sunday bucketing.** 2026-10-25 (a Sunday, and Israel's fall-back date) buckets to itself; 2026-03-27 (a Friday, and the spring-forward date) buckets to 2026-03-22; 2026-10-31 (Saturday) buckets to 2026-10-25. A booking at `21:30Z` on a date where the UTC and Jerusalem calendar days differ lands in the Jerusalem bucket.
- **DST week spans.** The bucket beginning 2026-10-25 covers 169 UTC hours and the one beginning 2026-03-22 covers 167; a booking one minute inside each edge is in the right bucket and one minute outside is not. This is the test that fails if anyone advances an edge with `+ timedelta(days=7)` on an instant.
- **Zero-fill and ordering.** Always `HISTORY_WEEKS` buckets, ascending, a bookingless week is `0`.
- **The consistency invariant** `sum(weeks[].bookings) == confirmed + no_show + completed`.
- **Every rate at zero.** Empty window → all three rates and `utilization` are `None`, `total == 0`. A window with only `confirmed` rows → `no_show_rate is None` while `cancellation_rate == 0.0`. A window with only cancellations → `cancellation_rate == 1.0` and `no_show_rate is None`.
- **Cancellation attribution**, including a row with `cancelled_by = None` counted in neither bucket.
- **Type folding**, all five cases (**amended, plan C2** — the fifth is the predicate): a cancelled booking of a type does **not** raise its count, and `sum(appointment_types[].bookings) <= sum(weeks[].bookings)`. Plus: a type renamed mid-window (one row, labelled from the greatest **`created_at`** — the fixture puts `created_at` and `starts_at` in **opposite** orders across the rename, so `max(starts_at)` labelling red-fails), a type archived during the window (still present, still named), a name freed and reused by a second `appointment_type_id` (two rows, not one), and **those two reused-name IDs at equal counts**, asserting the full ordered list is stable under a reversed input order — the `str(id)` tie-break.
- **New vs returning vs repeat**, three shapes: two bookings re-pointed to one `customer_id` produce one cohort member with two lifetime bookings; a customer row with no bookings never appears; and the **split shape** — customer A with two pre-window bookings and customer B with one in-window booking (what the collision branch actually leaves behind, since it moves one confirmed future booking and nothing else) asserting the currently-shipped answer, B scored `new` and excluded from `repeat_rate`. That last one pins Risk 12's behaviour rather than assuming it away.
- **Utilization clamping**: an instant with `booked > capacity` clamps to `capacity`; an instant present in `count_by_start` but absent from the grid contributes nothing; `capacity == 0` → `None`; and on every populated case `booked <= capacity` and `utilization == booked / capacity`, so shipping `sum(booked_by_instant.values())` as `forward.booked` red-fails (D4).

**`Backend/tests/test_dashboard_api.py`** (new, no marker) — the `test_staff_api.py` template with a duck-typed `FakeDashboardService` on `app.state.dashboard_service`, fake auth service, hardcoded tenant resolver, no database:

- The `ROUTES` table — one row, `("GET", "/manage/dashboard", None)` — driving `test_every_route_requires_authentication`, `test_every_route_is_wired_and_reaches_the_service` and the `cache-control: no-store` assertion. This table is also the sixth-router shadowing guard.
- `SPEC_ERROR_CODES = {"NOT_AUTHENTICATED", "NOT_AUTHORIZED"}` plus `test_every_spec_error_code_is_asserted`. **Its hand-union must not include `CSRF_ORIGIN_MISMATCH`** — the route is a GET and the middleware fences mutating methods only (D9).
- **Both roles get 200**; the shared `UNKNOWN_ROLE` sentinel gets the exact generic 403 body.
- **The handler passes the host-resolved tenant.** `FakeDashboardService` records the `tenant_id` it was called with; the test asserts it equals the resolver's `TENANT.id` (D8). This is the only place the trust path is observable — the `db` isolation test runs below the router.
- **A disclosure walk with F52's OWN forbidden set — not the storefront's.** `_all_keys` (the recursive every-key-at-every-depth helper, `test_storefront_api.py:643-651`) is reused; `FORBIDDEN_KEYS` is **not**. That frozenset (`test_storefront_api.py:203-232`) was built for F10's manage-only storefront leaks and contains **no** `customer_id`, **no** phone key and **no** `name` — so borrowing it proves nothing about this endpoint's PII claim — while it *does* contain `capacity`, which F52 legitimately ships at `forward.capacity`, so borrowing it also red-fails on the spec's own contract. F52 declares:

  ```python
  DASHBOARD_FORBIDDEN_KEYS = frozenset(
      {"customer_id", "phone", "customer_name", "notes",
       "manage_token_hash", "email", "dress_name", "seat_index"}
  )
  ```

  Note what is **not** in it and why, both recorded in a comment beside it: `capacity` is deliberately permitted here (D4 records the posture — this route is role-gated and `GET /manage/slots` already discloses strictly more to the same two roles), and the bare key `name` cannot be forbidden because `appointment_types[].name` is a type label, not a person's — the customer-name key, if one ever appeared, would be `customer_name`. The walk runs against a **fully populated** `FakeDashboardService` response (non-empty `weeks`, `appointment_types`, `customers`, `forward`), so it cannot pass vacuously on an all-`null` payload.

**`Backend/tests/test_staff_role_gating.py` is NOT edited.** Its default-deny walker reads the **live** route table, so a router-level `RoleGate` covers the new route with no test written — provided the gate is actually there, and a router without one is a red build. `OWNER_ONLY` stays exactly as F51 left it: adding a both-roles route to it makes `test_route_table_matches_the_permission_matrix` report it as `unenforced_owner_only`, red-failing with a message about a missing owner-only gate. Note also that the module's HTTP matrix tests iterate `[*ROUTES, *CATALOG_ROUTES]` imported from two other modules, so they do **not** pick up F52's route — the HTTP behaviour is proven in `test_dashboard_api.py`'s own walks.

**`Backend/tests/test_dashboard_db.py`** (new, module-level `pytestmark = pytest.mark.db`; NullPool engines in `try/finally`, the `app_role_url` fixture, never the superuser):

- The two real statements against real Postgres: the window projection returns exactly the rows in `[from, until)` and nothing outside, and `history_by_customer` returns the right `min(starts_at)` and count for a customer with bookings on both sides of the window edge.
- **Forward utilization end to end** against a real rule set, with one slot booked to capacity **on `today + 6` specifically**: the fully-booked instant is present in the denominator (this is the assertion that fails if anyone builds the grid from `list_slots` instead of `booked={}`), it is present in the **numerator** (this is the assertion that fails if `until_instant` is written as boutique-midnight of `today + 6` rather than `today + 7`, D4 — with the booked slot anywhere else in the window, both spellings pass), and utilization comes out at the hand-computed value.
- A booking at an instant the current rules no longer offer contributes nothing to `forward.booked`.
- **Tenant isolation.** Tenant B's dashboard does not see tenant A's bookings — asserted together with **tenant A's own numbers being non-zero in the same test**, because an all-zeros pass is exactly what a missing `tenant_session` produces and it would otherwise read as green (D3).

**Frontend (vitest, `apps/manage/src/__tests__/`)** — the `CatalogSection.test.tsx` pattern (`vi.mock("../api")` with `importActual` for `ApiError` / `errorMessage`, fixture builders, `vi.mocked`). Both suites run under `TZ=America/New_York`, which is what gives the date assertions bite:

- `DashboardSection.test.tsx` — loading skeleton, outage alert with no stacked empty state (**including a 403 `ApiError`**, which D10's landing change makes reachable for an out-of-enum role), a populated render, a zero-data render (`null` rates render the sentence, not `0%`), **the three rate facts as three strings** (see below), the bars' `aria-hidden` + text-label pairing, RTL bidi on every number, and an axe pass (`axe-core` is already a manage devDependency).

  **Amended (plan C1) — the precision-floor fixture.** This bullet previously asked for "a rate of `0.004` rendering `<0.1%`", and both halves were wrong. `0.004` is **0.4%**: under `formatRate` (`manage-dashboard.md:101-111`, `(r * 100).toFixed(1)`) it renders `0.4%`, the ordinary path — a floor test whose input never reaches the floor passes under a broken `formatRate` too. The fixture that reaches the `s === "0.0" && r > 0` branch is **`0.0004`** (0.04% → `"0.0"`), and the assertion is on `t("dashboard.rateUnderFloor")`, never on an ASCII literal. So: `0.0` → `0.0%`; **`0.0004` → `t("dashboard.rateUnderFloor")`**; **`0.004` → `0.4%`** in its own case; `null` → `t("dashboard.notEnoughData")`.
- `Nav.test.tsx` — the **five** edits above (amended, plan C4), plus: both roles see the dashboard item, and the console lands on it.
- `jerusalem.test.ts` — the `plainDate` describe block (amended, plan C3): `plainDate("2026-05-03") === "3.5.2026"`, `plainDate("2026-07-25") === "25.7.2026"`, and the comment recording that a device-clock read of the same string prints `2.5.2026` under this suite's `TZ=America/New_York`.
- `i18n.test.ts` — `const HE_F52 = entries(he.translation, (k) => k === "nav.dashboard" || k.startsWith("dashboard."))`, folded into `const HE = [...HE_F15, ...HE_F51, ...HE_F52]`, with its own describe block and a `toBeGreaterThan(N)` floor set just under the deck's stated row count. **A separate constant, not a widened filter**: the file's own comment records that folding groups together lets one feature's floor absorb another's rows. Without the fold, the resolve check, both register guards and the `ar` parity guard silently skip every F52 key.

**No new `MIRRORS` row** in `test_frontend_constant_parity.py`. `HISTORY_WEEKS`, `FORWARD_WINDOW_DAYS` and `TOP_APPOINTMENT_TYPES` are server-side shape decisions; the client renders whatever array arrives and mirrors no numeric bound.

**No E2E.** The shipped `a11y.spec.ts` only reaches `http://localhost:4174` unauthenticated — no backend runs during e2e, so `api.me()` fails and `App` renders `LoginForm`. Every authenticated console section is unreachable to axe there. The dashboard's accessibility proof is the vitest axe test plus the deck's a11y section; claiming e2e coverage for it would be false.

---

## Out of scope

- **Any revenue, deposit or payment metric.** `bookings` carries no price column; payments are E4.
- **Historical slot utilization** (D4, Risk 8). The snapshot job is the recorded upgrade path and is not built.
- **A client-selectable window, a date picker, or a comparison-to-previous-period arrow** (D2). The endpoint takes no parameters; every one of those adds a caller-supplied date to arithmetic that is currently total.
- **Per-staff metrics** ("who handled the most appointments"). `bookings` records no assignee — `seat_index` is a seat, not a person. F34's board is where a staffer first touches a booking.
- **Demand over time** (bucketing by `created_at`). A different metric that needs its own index (D2).
- **Export, CSV, print, or a share link.** Nothing has asked.
- **A poll, an auto-refresh, or a `me()` refresh** (D11). F51's Risk 3 moves to F34.
- **Reading `audit_log`** — same ruling as F15's D2 and F51's D8.
- **Any chart library, and any promotion of a bar/meter into `packages/ui`** (D10). That promotion is what the Q2 self-approval argument forbids.
- **Retrofitting the four hardcoded-Hebrew console sections to i18n** — inherited from F15's D16, unchanged.

---

## Risks & open items

1. **A zero-data tenant sees a real screen made of zeroes and three not-computable sentences.** Twelve `0` bars, `status_totals` all zero, `cancellation_rate`/`no_show_rate`/`repeat_rate` all `null`, and a forward panel that reads either a real utilization (if she has set hours) or a fourth sentence (if she has not). Bounded and deliberate: the alternative is an `EmptyState` that hides the forward panel — the one number a brand-new boutique can actually act on. *Owner: team. Trigger: first pilot onboarding.*
2. **Two Sunday-start weeks a year are 167 or 169 UTC hours, and the transition falls inside the bucket, not at its edge.** Israel's spring-forward is always a Friday and its fall-back always a Sunday — day-index 0, the first day of the Israeli week. Date-space arithmetic makes every bucket edge exact; the residual is that a 01:xx wall time on the fall-back Sunday is ambiguous and `_to_utc` keeps only its first occurrence (`slots.py:81-104`). Bounded to one hour, once a year, at an hour no boutique is open. *Owner: team. Trigger: none realistically; the DST tests are the guard.*
3. **The window projection is unbounded in row count within the window.** Worst case at pilot scale is ~7,560 narrow rows and realistic is 300–800, but a tenant with several boutiques' worth of history in one row set would pull all of it into Python on every dashboard open. **This is a per-request cost as much as a data-volume one**: F52 is the heaviest read in the product *and* the landing screen — fetched on every mount, every login, every handover — with `no-store` and no poll, so the only amplification available to a holder of one valid session is request repetition, and nothing throttles it (D8 declines a limiter for consistency with every other `/manage` router, and says so). The fix is mechanical when needed — the folds are already pure functions, so moving each to a SQL `GROUP BY` changes only the source of the numbers, not the definitions. *Owner: team. Trigger: any tenant crossing ~10,000 bookings in twelve weeks, which would be roughly 120 appointments a day.*
4. **`history_by_customer` scans each cohort member's entire booking history.** It rides `idx_bookings_tenant_customer` and a boutique's customer has single-digit bookings. Recorded for symmetry with Risk 3. *Owner: team. Trigger: the same threshold.*
5. **The no-show rate can be computed over a handful of appointments and still be rendered as a percentage.** An owner who marks three no-shows and no completions reads 100%. Bounded by shipping `status_totals.confirmed` — the unclassified count — beside it and by the copy stating the denominator in words (D5). It cannot be bounded further without either lying about unmarked appointments or refusing to show the metric at all. *Owner: **user** (to overturn, not to authorise). Trigger: the first pilot boutique that does not use the outcome verbs.*
6. **The forward utilization number moves through the day with no bookings changing.** `materialize_slots` drops every instant `<= now` (`slots.py:140`), so today's elapsed slots leave the denominator as the day progresses and the same booking set reads differently at 09:00 and 17:00. Accepted rather than starting the window at `today + 1`, which would hide today entirely while the booking section beside it starts today — two adjacent panels disagreeing about when "the week" starts is worse than one number that moves. Bounded by the copy, which calls it remaining offerable capacity **from now**. *Owner: team. Trigger: a pilot report that the number "jumps".*
7. **Utilization counts seat-slots, not time.** A 30-minute consultation and a two-hour fitting are one seat-slot each, because the engine's grid has no duration (`slots.py:9-14`). A boutique whose types differ wildly in length will read a utilization that does not match how busy the room felt. Any other answer would disagree with what the booking engine actually enforces. *Owner: team. Trigger: the E4/F42 capacity work, which is where duration first shapes anything.*
8. **There is no historical utilization and there cannot be one without a schema change.** `replace_weekly_rules` soft-deletes the whole active set on every save and no reader reads deleted rows, so the grid's past is unrecoverable — and a boutique that never edited its hours would reconstruct every earlier week as zero capacity even if one existed. The snapshot job stays the recorded upgrade path (D4). *Owner: team. Trigger: a boutique asking "were we busier in May".*
9. **New-vs-returning is booking-derived, so a customer row with no bookings is invisible.** That is correct — after F15's phone-correction collision branch such rows exist and are not people who visited — but a later CRM screen (F53) counting rows in `customers` would print a different "total customers" than this dashboard's cohort, on the same tenant, with both being right about different questions. Named so F53 defines its own number deliberately rather than discovering the discrepancy. *Owner: team. Trigger: F53.*
10. **F51's Risk 3 — the nav is filtered once, at bootstrap — is not closed here and now has no queued owner until F34.** F51 named F52 as the natural home because it expected a poll; F52 declines one (D11). A mid-session demotion still leaves a stale door drawn until reload, and every call behind it 403s correctly. *Owner: team. Trigger: F34's 5-second board poll, or a pilot report.*
11. **`cancelled_by_customer + cancelled_by_owner` can be less than `status_totals.cancelled`.** Any row cancelled before 0010 added the columns carries NULL and is counted in neither. There are no such rows in any live database today, but the response contract permits it and the console must not render the two counts as a partition that must sum. *Owner: team. Trigger: none; recorded as a contract property.*
12. **A phone correction can split one human's history across two `customer_id`s, and she then reads as `new`.** F15's collision branch re-points **one** confirmed, future booking (`allowed_from=('confirmed',)`, `starts_at > now` — `booking/owner.py:679-686`); every past booking of that human stays on the old customer row. If the old row was a mis-keyed duplicate rather than a real other person, her past visits sit under id A and her corrected visit under id B, so B's `min(starts_at)` falls inside the window with a lifetime count of 1 — she is scored **new** and excluded from `repeat_rate`, and `customers.total` counts her twice across windows. Magnitude is **one customer per collision-branch correction**, and the correction is itself the rare branch of a rare remedy. The alternative considered and declined: re-pointing that customer's whole history, which is a change to F15's write, not to F52's reads, and which would be wrong whenever the old row IS a real other person — the exact case `set_customer_id`'s docstring says it keeps both rows for. Pinned by a pure test asserting the shipped answer rather than assumed away. *Owner: team. Trigger: a pilot boutique using the phone remedy on a duplicate row.*
13. **Between zero and six days of the most recent data are on no panel of this screen.** History ends on the Saturday before the current week (D2) and the forward window starts today (D4), so `current_week_start … today − 1` — `jerusalem_day_index(today)` days: 0 on a Sunday, 5 on the Friday the example payload is generated on, 6 on a Saturday — appears in nothing. Each half is right on its own (a partial final bar reads as a collapse; a forward window starting tomorrow would disagree with the booking section beside it about when "the week" starts, Risk 6) and together they leave a hole in "what happened this week so far", which is a natural first question at a landing screen. **Accepted, not closed.** Closing it means a `history.current_week_so_far` scalar off a projection widened to `midnight(today + 1)` — cheap in SQL, but it puts partial-week rows inside the one scan every rate folds over, which is precisely the shape D2 excludes and the shape a wrong window already slipped past review once. The copy must therefore not imply a continuous span: the two panels are labelled with their own ranges and no sentence bridges them. *Owner: team. Trigger: a pilot asking what this week looks like — at which point the scalar ships with its own fold, not by widening the shared one.*
14. **Only the top five appointment types are returned.** A boutique with more sees the rest folded into nothing, not into an "other" bucket. Single-digit type counts make this theoretical; an "other" row is one line of Python when someone asks. *Owner: team. Trigger: a boutique with more than five active types.*

---

## Decisions Log

- **D1 — F52 ships no migration and adds no `AuditAction`.** Every column and both indexes exist; the reads ride `idx_bookings_tenant_starts` and `idx_bookings_tenant_customer`. Declined: a `booking_metrics_daily` rollup (a table, a writer, a backfill and a staleness question, for hundreds of rows), an `availability_snapshots` table (D4's upgrade path, not built), an index on `(tenant_id, status)` (Risk 3 names the threshold), and a `DASHBOARD_VIEWED` audit action — which would need no migration either, and that is exactly the bad reason to add one.
- **D2 — Twelve complete Sunday-start weeks, computed from `today_jerusalem`, with no query parameters.** Week edges are advanced in **date** space and converted once each, because Israel's fall-back is always a Sunday — the first day of the Israeli week — so one bucket a year is 169 UTC hours and one is 167. The current partial week is excluded: a partial final bar reads as a collapse, and rates over future appointments are skewed by construction. The worked example in the response block is normative and its three shape invariants (`to_date < generated_on` above all) are pure-tested against a frozen clock — the arithmetic being prose-only is how an off-by-one-week example survived to review. The exclusion's accepted cost is Risk 13's 0–6 uncovered days. Taking no caller date is what makes the arithmetic total with no `date.min/date.max` guard, unlike `list_day` and `slot_window`. Declined: `date_trunc('week', …)` (ISO — Monday-start — and the codebase has zero SQL date functions), bucketing on `created_at` (no index, and it answers a different question), and reusing `count_by_start` (its `status <> 'cancelled'` makes the cancellation rate structurally 0%).
- **D3 — One narrow projection, folded in Python, so every metric definition is pinned by a fast test.** `SELECT starts_at, created_at, status, cancelled_by, customer_id, appointment_type_id, appointment_type_name` over the window, all statuses, one range scan — then six pure folds. `created_at` earns its place as the seventh column by being the only correct label key for D6. The departure from `aggregate_by_dress`'s SQL-side aggregate is deliberate: there is no N+1 either way, and a `GROUP BY` can only be exercised in a `db`-marked module that debuts on CI, while the six definitions are exactly where this feature can be silently wrong. Narrow, not `select(Booking)`, so `notes` and `manage_token_hash` never enter a process that only counts. `deleted_at IS NULL` on every predicate; `tenant_session` plus the redundant `tenant_id` predicate on every read, because a missing tenant context turns an aggregate into a plausible all-zeros dashboard rather than a visible 404.
- **D4 — Forward utilization calls `materialize_slots` with `booked={}` over `[today, today+6]`, from a new coroutine in `slots_io.py`.** The engine drops full slots by design, so summing `list_slots` omits precisely the busiest ones and the error grows with the boutique; `CHECK (capacity > 0)` is what makes `booked={}` a complete grid. The numerator iterates the **grid** and clamps with `min(booked_by_instant, capacity)`, because `count_by_start` can hold instants the grid no longer offers — and `forward.booked` on the wire is that clamped sum, never the dict's sum. The two window bounds differ by one day on purpose: `window_end` is an inclusive **date** (`today + 6`) for the engine while `until_instant` is an exclusive **instant** (boutique-midnight of `today + 7`) for the half-open `count_by_start`, the `list_slots` idiom verbatim; writing `today + 6` in both understates utilization by a seventh, silently, and the `db` test puts its booked slot on the last forward day to catch it. This panel knowingly publishes the density aggregate the anonymous surface is fenced against — legitimate because the route is role-gated and `GET /manage/slots` already discloses more to the same two roles, and recorded in the coroutine's docstring together with the rule that it must never return a slot list. Declined: an `include_full` flag (a switch whose only purpose is disabling a disclosure control on a function serving anonymous traffic), a second materializer in `DashboardService`, `slot_window` (a no-op here, and inverted for anything historical), minutes-based utilization (the grid has no duration), deriving capacity ourselves (the engine reconciles it two different ways twelve lines apart), and reconstructing history from soft-deleted rules.
- **D5 — Cancellation rate over all four statuses; no-show rate over recorded outcomes only, with the unclassified count shipped beside it.** Every rate answers `null` at a zero denominator, never `0`, and the console renders the two differently — a third string, **`dashboard.rateUnderFloor`** (amended, plan C1: «פחות מ־0.1%», not an ASCII `<0.1%`), keeps a non-zero rate that rounds to zero from collapsing into the true-zero one; the wire carries the unrounded quotient and the console does all rounding. The pure-test fixture for that branch is **`0.0004`**, not `0.004` — `0.004` is 0.4% and never reaches the floor. `weeks[].bookings` counts non-cancelled appointments — the seat-slots the boutique **held**, not the ones that stood, since `sum(weeks[].bookings) == confirmed + no_show + completed` is asserted and a no-show is in that sum; the copy deck carries the held-not-attended wording so the Hebrew label cannot contradict the no-show tile beside it. Cancellations are attributed via `cancelled_by`, free from a column already in the projection, because a boutique that cancelled twenty appointments itself would otherwise read its own closure as customer flakiness. Declined: `attendance_confirmed_at IS NULL` as a no-show signal — it means the bride tapped an SMS link, not that she came, and `set_status`'s docstring names the distinction.
- **D6 — Busiest types count NON-CANCELLED bookings, group on `appointment_type_id` and label from the snapshot on the greatest `created_at`.** **Amended (plan C2)**: the fold's predicate is `status != 'cancelled'` — the same predicate `weeks[].bookings` and the customer cohort use — because the deck reuses the «תורים שלא בוטלו» header for this count, and `sum(appointment_types[].bookings) <= sum(weeks[].bookings)` is a pure-tested invariant (`<=`, since the top-five cut truncates). Both keys are lossy alone and the failures are mirror images: joining `list_active` drops types archived mid-window, while grouping on the snapshot name splits a renamed type in two and merges two types that reused one freed name. Grouping by ID and labelling from the snapshot is correct on both axes, needs no join to `appointment_types`, and is five lines of Python pinned by a pure test covering all four cases. **`created_at`, not `starts_at`**: the name is snapshotted when the booking is written, and in a boutique where brides book months ahead the newest snapshot and the latest appointment are routinely different rows — which is why `created_at` is D3's seventh column. Top five on the **total** key `(-count, name, str(appointment_type_id))`: count-and-name alone leaves two reused-name IDs at equal counts ordered by whatever row order Postgres happens to return from an `ORDER BY`-less statement, and that is the exact case this decision exists for.
- **D7 — New-vs-returning and repeat rate are derived from `bookings` alone, never from `customers`.** F15's phone-correction collision branch re-points `bookings.customer_id` at an existing customer and leaves both customer rows alive, so after one correction a tenant has customer rows with zero bookings and customers whose `created_at` post-dates their own first visit — a `customers`-derived answer looks right in dev and lies only at the tenants that used the remedy. The booking-derived answer never reads `customers.created_at` and cannot see a zero-booking row at all, which is the whole of the cure. It is **not** a cure for split history: the write moves exactly one confirmed, future booking, so past bookings stay on the old row — Risk 12, accepted with its magnitude and pinned by a test rather than assumed away. "First-ever" and "ever" are both evaluated as of `until_instant`. One aggregate, `history_by_customer`, in the `aggregate_by_dress` shape — the one read that cannot fold into D3 because it needs rows outside the window.
- **D8 — New package `app/dashboard/`, a sixth `/manage` router, both roles, no parameters, one nested response.** Not two files in `app/booking/`: the surface reads across bookings and both availability repositories, so it belongs to neither domain, and `booking/schemas.py` would gain ten models for an API that is not the booking API (**`app/notifications/` alone** is the precedent for the `service.py`/`router.py`/`schemas.py` trio — `app/platform/` ships neither a router nor schemas and is not cited; F51's D6 declined a package for the opposite reason). Router-level `require_role(OWNER, SHIFT_MANAGER)`, its own fourth local `_no_store`, included after `staff_router` with the shadowing comment the catalog, owner-booking and staff includes carry (`main.py:678-691` — three of the six, not five). The handler takes the tenant from `get_current_tenant(request)`, host-derived like every shipped `/manage` handler, and declares no `Staff` parameter, because this is the first `/manage` route with no audit row and no self-guard to need one; the API test pins the source by recording what the fake service was called with. Nullable rates are `float | None` on the wire, precision is a stated contract, and no customer identifier reaches it — proven by F52's own forbidden-key walk, not the storefront's, which names none of the three keys and forbids the `capacity` this response legitimately ships. No rate limiter, and the reason is the session plus the role gate: CSRF fencing does not cover a GET (D9).
- **D9 — Two error codes, both existing, no new handler, and no audit row.** The endpoint takes no input, so nothing can 400; an empty tenant is a valid zero dashboard, so nothing can 404. `CSRF_ORIGIN_MISMATCH` is impossible on a GET (`csrf.py:48`) and must not be unioned into the completeness test the way the shipped template does. No GET handler in this product writes an audit row, and a landing screen is the wrong place for the first one.
- **D10 — The dashboard is the landing section, and it ships no chart library and no `packages/ui` promotion.** `NAV` gains a first row with `roles: ALL` and the initial `section` becomes `"dashboard"`, so the existing `reachable[0]?.key` fallback and the initial state agree. **The other half of that blast radius**: an out-of-enum role reaches no `NAV` row, so `reachable[0]?.key ?? section` now lands it on the dashboard rather than on a 200-ing Profile panel, and its one fetch 403s — `NOT_AUTHORIZED` becomes reachable on this section, which is why the copy rationale rests on "one string covers any `ApiError`" and not on either code being impossible. Bars are a track div plus a fill sized with `inlineSize` (not `width`, so RTL grows from the inline start), `aria-hidden` beside a real text label — never `role="progressbar"`, which announces a task's completion rather than a ratio. No gold `Badge` variant is added; `gold-strong` is 3.80:1 and a Badge is always `text-xs` — and in fact no `Badge` and no `EmptyState` are mounted at all, so the Q2 component set is the three the screen actually renders (`SectionHeading`, `Card`, `Skeleton`) rather than five that pad it. That restraint is the Q2 self-approval argument.
- **D11 — One fetch on mount, no poll, and F51's Risk 3 explicitly moves to F34.** Twelve complete past weeks change once a week. F51 named F52 as the natural home for a `me()` refresh because it expected the console's first repeating fetch to land here; it does not, so the risk stays open and F34's 5-second board poll inherits it. Recorded so the next reader does not read it as forgotten.

---

## Review response (adversarial review, 2026-07-31 — 3 reviewers, 20 findings)

All 20 findings were verified against the code before being acted on. Twelve were distinct (findings 1/6/8 are one issue, 2/7 are one, 5/9 are one). **All 20 are fixed; none rejected. The one BLOCKER is closed.**

| # | Verdict | Where it landed |
|---|---|---|
| 1, 6, 8 (**BLOCKER**) | fixed | Example payload was one week late — it shipped the in-progress week and a `to_date` in the future, the exact shape D2 refuses. Corrected to `from_date 2026-05-03` / `to_date 2026-07-25` / `weeks[0] 2026-05-03`, marked normative, with three shape invariants and a frozen-clock derivation test (Sunday and Saturday boundaries) added to `test_dashboard_math.py`. |
| 2, 7 | fixed | `first`/`last` were undefined identifiers in D4. Written out as the `list_slots` idiom, with the inclusive-date/exclusive-instant asymmetry stated as deliberate, plus a `db` assertion that the booked slot sits on `today + 6`. |
| 3 | fixed | D7's "the orphan simply never appears" overstated `set_customer_id`, which moves exactly one confirmed future booking. Prose corrected, split-history consequence added as Risk 12 with its magnitude and the declined alternative, pinned by a new pure-test shape. |
| 4 | fixed (accepted, not closed) | The 0–6 day hole between the two windows is now Risk 13, named with its magnitude and its Saturday worst case, cross-referenced from D2. The `current_week_so_far` scalar is declined **with the reason**: it would put partial-week rows inside the single scan every rate folds over. |
| 5, 9 | fixed | The storefront `FORBIDDEN_KEYS` asserts none of the three keys the spec attributed to it and forbids the `capacity` this response ships. Replaced with `DASHBOARD_FORBIDDEN_KEYS`, run over a fully-populated fake so it cannot pass vacuously, with `capacity`'s permitted status and `appointment_types[].name`'s type-label status both recorded. |
| 10 | fixed | `NOT_AUTHORIZED` is reachable *because of* D10's landing change, and `apiFetch` has no 401 interceptor. Copy rationale rebuilt on "one string covers any `ApiError`", the blast radius recorded in D10, the 403 case added to `DashboardSection.test.tsx`. |
| 11 | fixed | Label key changed from `max(starts_at)` to `max(created_at)` — snapshots are written at booking creation — with `created_at` added as D3's seventh column and the test fixture required to order the two keys oppositely. |
| 12 | fixed | Sort key is now `(-count, name, str(appointment_type_id))`, total, with an equal-count reused-name ordering test. |
| 13 | fixed | Precision stated as a wire contract: unrounded quotient on the wire, one decimal in the console, `<0.1%` as a third copy string so a non-zero rate never collapses into the true-zero one. |
| 14 | fixed | `weeks[].bookings` re-glossed as non-cancelled seat-slots the boutique **held**, not appointments that stood, and the wording carried into the copy deck so the Hebrew label cannot contradict the no-show tile. |
| 15 | fixed | D4 now records that the forward panel deliberately republishes the density aggregate the anonymous surface fences, why that is allowed (`GET /manage/slots` discloses strictly more to the same two roles), and the rule that `forward_capacity` must never return a slot list — in the docstring, where the next caller reads it. |
| 16 | fixed | D8's "CSRF-fenced" leg removed; the posture is the session and the role gate, and D9's GET argument is cited rather than contradicted. |
| 17 | fixed | The handler is written out with `get_current_tenant(request)` and no `Staff` parameter, with the two trust paths named and the source pinned at the HTTP boundary by the fake service. |
| 18 | fixed | `Badge` and `EmptyState` dropped from the Q2 component set in all three places; the set is now the three components the screen mounts. |
| 19 | fixed | Local renamed `booked_by_instant`; `forward.booked` stated to be the clamped grid sum, with `booked <= capacity` and `utilization == booked / capacity` as pure-tested invariants. |
| 20 | fixed | Include-comment claim corrected to three routers (`main.py:678-691`); `app/platform/` dropped as a package-shape precedent, leaving `app/notifications/` alone. |

**Rejected review findings**: none. Every finding reproduced against the code on re-check.
