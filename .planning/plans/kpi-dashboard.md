# Plan: Feature 52 — KPI dashboard, the console's landing section (Epic SMC, phase SMC-3)

**Status**: Gate 2 self-approved 2026-07-31 under Interview Q1 (F52 is not on Q1's stop-list — F17/F18/F19/F20/F29/F48; read-only surface, no money, no legal text). The four contradictions below (C1–C4) are amended into the spec as of Task 0; **the spec text is the binding statement of each resolution, this file the reasoning.**

**Spec**: `.planning/specs/kpi-dashboard.md` (Gate 1 self-approved 2026-07-31, D1–D11) · **Design**: `.planning/design/screens/manage-dashboard/manage-dashboard.md` + `copy.md` — **both exist and are accepted**; unlike F51 this plan has no Task 1 authoring step, it has two open items the deck handed the builder (C1, C2) · **Branch**: `feature/kpi-dashboard` (worktree `.worktrees/kpi-dashboard`) · **Created**: 2026-07-31

TDD throughout: in every task below the failing test is written first, then the code that makes it pass. Local gate per task: `make lint` + `make test` for backend tasks; `make lint` + `make fe-test` + `make fe-build` for frontend ones. **`db`-marked tests are written here and executed only on CI** — there is no Docker locally. §"What a local run cannot prove" lists what that costs.

F52 ships **no migration** (D1). `test_every_tenant_id_table_has_forced_rls` staying green is the assertion that none snuck in.

---

## Rulings this plan is built on

| Ruling | Effect on the build |
|---|---|
| **SMC epic, SMC-3 row** | `GET /manage/dashboard`, Jerusalem window, **both roles**. Ops + customer KPIs. **No revenue** (payments are E4; `bookings` carries no price column). **Forward-only** utilization — the `availability_snapshots` job stays the recorded upgrade path, not built. |
| **Interview Q1** | Gate 2 self-approves. F52 is not on the stop-list. Risks 5, 12 and 13 are **re-nagged in the run report**; they do not stop the build. |
| **Interview Q2 / design gate** | Self-approves: the screen is `SectionHeading` + `Card` + `Skeleton` — three shipped `packages/ui` exports (verified at `packages/ui/src/index.ts:15, 24, 28`) — plus one hand-built bar that stays inline markup in the section. **No new `packages/ui` component and no promotion.** Designer and `design-critic` both accepted the deck already; this plan transcribes it. |
| **Interview Q3 / pre-decided #47** | `apps/manage/src/i18n/ar.ts` gains F52's 43 keys, values = the approved Hebrew, **never `""`**. `lng` stays `"he"`, no switcher. |
| **pre-decided #5** | Zero exclamation marks in Hebrew copy — mechanically enforced in `__tests__/i18n.test.ts` over `HE`, which the `HE_F52` fold is what extends to F52's keys. |
| **pre-decided #38** | IS 5568 / WCAG 2.0 AA is a **legal** requirement. The a11y items in Task 7 are not optional polish. |
| **D11 / F51's Risk 3** | **Do not add a poll, an interval, or a `me()` refresh.** F51 named F52 as the natural home because it expected the console's first repeating fetch to land here. It does not. Risk 3 stays open and moves to F34. |
| **D1** | **Do not add a table, an index, a migration or an `AuditAction`.** Every column and both indexes exist. |

---

## Rulings this plan makes, that the spec left to the builder

**The pure half lives in `app/dashboard/service.py`, not in a fourth module.** D3's argument is that the six definitions must be pinned by a fast test — that is a property of the *functions*, not of the file. Module-level frozen dataclasses, three constants, `history_window()` and the six folds sit above `DashboardService` in the same file; `test_dashboard_math.py` imports them by name. Declined: a `metrics.py` (a fourth file to make a docstring's claim look structural), and putting them on the class (a method needing `self` for nothing is what makes a pure test awkward).

**`BookingFact` and `CustomerHistory` are declared in `app/db/repositories/bookings.py`**, module-level and frozen, beside the coroutines that return them — `DressVariantsRepository.VariantAggregate`'s shape (`db/repositories/dress_variants.py:12-19`), which D3 already cites as the aggregate idiom. `app/dashboard/service.py` imports them; the repository imports nothing from `app.dashboard`. The dependency arrow only ever points at `app.db`.

**The forward clamp is a pure function in `app/booking/slots_io.py`**, not in the dashboard package. `forward_capacity` is I/O and lives there by D4; putting its clamp in `app/dashboard/` would make `app.booking` import `app.dashboard`, which is backwards. `grid_totals(grid, booked_by_instant) -> ForwardCapacity` sits beside it, module-level and pure, and `test_dashboard_math.py` imports it for the clamp cases the spec's Testing section lists.

---

## Four contradictions between the spec, the deck and the shipped tree — recorded, resolved, amended in Task 0

The spec is binding and D1–D11 are not re-litigated. These are four places where the documents disagree with each other or with the **shipped code**, and a plan cannot proceed without picking one side. Two of them are the deck's own "Open items handed to the builder" (`manage-dashboard.md:196-199`). Every resolution is the smaller of the two edits and none touches a D-decision's substance.

### C1 — the spec's precision-floor fixture does not exercise the floor, and the string it asserts is not the string that ships

The spec's frontend test list asks for "**a rate of `0.004` rendering `<0.1%` and not `0%`**" (Testing, `DashboardSection.test.tsx` bullet). Two things are wrong with that sentence and the deck flagged both.

1. **`0.004` is 0.4%.** Under the deck's `formatRate` (`manage-dashboard.md:101-111`) — `(r * 100).toFixed(1)` — `0.004` renders `0.4%`, which is exactly the normal path. The fixture that actually reaches the `s === "0.0" && r > 0` branch is **`0.0004`** (`0.04%` → `"0.0"`).
2. **The string is not `<0.1%`.** `copy.md` §3 ships `dashboard.rateUnderFloor` = «פחות מ־0.1%» and records why: a bare `<` inside an RTL paragraph mirrors and reads as a bracket, and this string sits unisolated in Hebrew running text. `<0.1%` is the spec's shorthand for the fact, not a literal.

**Resolution:** the fixture is `0.0004` and the assertion is on `t("dashboard.rateUnderFloor")`, not on an ASCII literal. `0.004` gets its **own** case asserting `0.4%`, because a floor test whose input does not reach the floor is worse than no test — it passes under a broken `formatRate` too. Amend the spec's Testing bullet and D5/D8's `<0.1%` shorthand to name the key.

### C2 — the appointment-type fold has no stated predicate, and the deck already shipped a column header that decides it

`manage-dashboard.md:199`. D5 defines `weeks[].bookings` as **non-cancelled**; D6 defines the customer cohort as **non-cancelled**; D6's type fold says only "fold the projection by `appointment_type_id`, sum the counts". The deck's types table reuses `dashboard.bookingsColumn` — «תורים שלא בוטלו», "appointments not cancelled" — as its count header (`copy.md` §5, §8), so the header is already a claim about the predicate.

Three predicates on one screen would be a defect the owner finds in her first week: a type count higher than the sum of the bars above it, under a header that says otherwise.

**Resolution:** **the type fold uses `status != 'cancelled'`, the same predicate as `weeks[].bookings` and the customer cohort.** One predicate for every count this screen labels «תורים שלא בוטלו». Amend D6 to state it, and add the invariant to the pure test: `sum(appointment_types[].bookings) <= sum(weeks[].bookings)` (`<=`, not `==`, because `TOP_APPOINTMENT_TYPES = 5` truncates — Risk 14). Declined: giving the types table its own column key (a second Hebrew word for one number, and it would need the deck reopened for a distinction the owner does not have).

### C3 — the frontend file table is missing the two files the deck's date rule requires

The spec's Frontend changes → Files table names seven files. The deck's rendering rules (`manage-dashboard.md:99`) require an eighth and a ninth:

> `generated_on`, `from_date` and `to_date` are **plain Jerusalem calendar dates on the wire**, not instants. They are formatted by splitting the ISO string — a two-line `plainDate(iso)` added to `lib/jerusalem.ts` beside the existing helpers, with a comment saying so.

Verified against `Frontend/apps/manage/src/lib/jerusalem.ts`: every shipped helper takes an **instant** string and runs it through `new Date()` plus a `timeZone: JERusalem` formatter. Passing `"2026-05-03"` through `jerusalemDate` parses it as UTC midnight and re-zones a date that was never in a zone — it happens to return the right day only because Jerusalem is ahead of UTC, which is the exact class of bug that file exists to prevent.

**Resolution:** `Frontend/apps/manage/src/lib/jerusalem.ts` gains `plainDate(iso: string): string` — `const [y, m, d] = iso.split("-"); return \`${Number(d)}.${Number(m)}.${y}\`;` — with a comment stating it takes a **plain date, never an instant**, and `Frontend/apps/manage/src/__tests__/jerusalem.test.ts` gains its describe block. That suite runs under `TZ=America/New_York` (`apps/manage/package.json:11`), which is what gives the assertion bite: a device-clock `new Date("2026-05-03").toLocaleDateString()` prints **2.5.2026** there, so the test that pins `plainDate("2026-05-03") === "3.5.2026"` fails the moment someone routes a wire date through a `Date`. Both files are added to the spec's file table.

### C4 — `Nav.test.tsx` breaks in five places, not four, and two of them are test names

The spec's §"Adding a nav row is not an `App.tsx`-only change" names four. Verified line-by-line against `Frontend/apps/manage/src/__tests__/Nav.test.tsx` — all four are real, and there are two more edits in the same file that a builder who counts to four will leave red:

| # | Line | Today | Becomes |
|---|---|---|---|
| 1 | `:44-52` | `NAV_LABELS` — seven elements, compared with `toEqual` at `:71` | «סקירה» inserted at **index 0**; eight elements |
| 2 | `:78` | `expect(navItems()).toEqual(NAV_LABELS.slice(0, 6))` | `.slice(0, 7)` |
| 3 | `:127-133` | the handover test asserts `.slice(0, 6)` **and** «פרופיל והגדרות» carries `aria-current="page"` after re-login | `.slice(0, 7)`, and the `aria-current` expectation moves to **«סקירה»** — `reachable[0]` is now dashboard |
| 4 | `:10-29` | `vi.mock("../api")` hand-lists the `pending` methods | `getDashboard: pending,` added. Without it every one of the five nav tests red-fails with `TypeError: api.getDashboard is not a function`, naming the nav rather than the dashboard |
| **5** | `:67`, `:74` | test names «shows an owner all **seven** sections…» / «shows a shift manager **six** sections…» | eight / seven. A test whose name contradicts its assertion is a landmine for the next reader |

Two shipped assertions in that file are **unaffected and must not be touched** — they are the neutrality proof for the nav row: `:82-93` (an out-of-enum role still reaches an empty nav, because `roles: ALL` admits `owner`/`shift_manager` only) and `:115-116` (an owner clicking «צוות» still gets `aria-current` on it).

**Resolution:** all five edits land in the same commit as the `App.tsx` change (Task 8). Amend the spec's four-item list to five.

---

All four are amended into the spec in **Task 0**, in the same PR — the `booking-comms.md` / F15 and `staff-management.md` / F51 Task-0 precedent for a plan-phase spec amendment.

---

## Task 0 — This plan, and the four spec amendments
`.planning/plans/kpi-dashboard.md` (this file), `.planning/specs/kpi-dashboard.md`

- Amend the Testing section's `DashboardSection.test.tsx` bullet, and D5/D8's `<0.1%` shorthand, with C1's `0.0004` fixture and the `dashboard.rateUnderFloor` key.
- Amend **D6** with C2's ruling: the appointment-type fold uses `status != 'cancelled'`, and the `sum(types) <= sum(weeks)` invariant is pure-tested.
- Amend the Frontend changes → Files table with C3's two rows (`lib/jerusalem.ts`, `__tests__/jerusalem.test.ts`) and the `plainDate` rule.
- Amend §"Adding a nav row is not an `App.tsx`-only change" from four breaks to C4's five.
- **Done when**: all four are in the spec and this file is committed. No code, no tests.
- **Gate**: none (no code).
- Commit **1**: `docs(planning): F52 implementation plan — Gate 2 self-approved` — `.planning/plans/kpi-dashboard.md`, `.planning/specs/kpi-dashboard.md`.

---

# Part I — the backend

## Task 1 — Schemas, the two record types, the window arithmetic and the six pure folds (TDD, fast — **the module that carries this feature**)
`Backend/app/dashboard/__init__.py` (**new, empty**), `Backend/app/dashboard/schemas.py` (**new**), `Backend/app/dashboard/service.py` (**new — the pure half only**), `Backend/app/db/repositories/bookings.py` (**edit — two frozen dataclasses only**), `Backend/tests/test_dashboard_math.py` (**new, no marker**)

**Tests first.** `test_dashboard_math.py` is pure: hand-built `BookingFact` lists, a frozen `today`, no database, no `create_app`, no marker — it runs in `make test` locally. It is where every one of the six definitions is pinned, and D3 exists to make it possible.

### The failing tests, in the order they go red

**The window derivation, against a frozen clock.** For `today = date(2026, 7, 31)` — a Friday, `jerusalem_day_index == 5`:

- `from_date == date(2026, 5, 3)`
- `to_date == date(2026, 7, 25)`
- `to_date < generated_on`
- `to_date == from_date + timedelta(days=7 * HISTORY_WEEKS - 1)`
- `weeks[-1].week_start == generated_on - timedelta(days=jerusalem_day_index(generated_on) + 7)`

Repeated for a **Sunday** `today` (where `current_week_start == today`) and a **Saturday** `today` (the widest exclusion). Plus the exclusion itself: a fact whose `starts_at` falls inside the current in-progress week appears in **no** bucket and in **no** `status_totals` entry. **This is the test whose absence let a wrong example payload reach review** — every rate assertion below is invariant to a uniform window shift, which is exactly why this one is separate.

**Sunday bucketing.** `2026-10-25` (a Sunday, and Israel's fall-back date) buckets to itself; `2026-03-27` (a Friday, the spring-forward date) buckets to `2026-03-22`; `2026-10-31` (a Saturday) buckets to `2026-10-25`. A fact at `21:30Z` on a date where the UTC and Jerusalem calendar days differ lands in the **Jerusalem** bucket.

**DST week spans.** The bucket beginning `2026-10-25` covers **169** UTC hours; the one beginning `2026-03-22` covers **167**. A fact one minute inside each edge is in the right bucket, one minute outside is not. **This is the test that fails if anyone advances an edge with `+ timedelta(days=7)` on an instant.**

**Zero-fill and ordering.** Always `HISTORY_WEEKS` buckets, ascending, a bookingless week is `0`.

**The consistency invariant** `sum(weeks[].bookings) == confirmed + no_show + completed`.

**Every rate at zero.** Empty window → all three rates `None`, `customers.total == 0`. Only-`confirmed` window → `no_show_rate is None` while `cancellation_rate == 0.0`. Only-cancellations window → `cancellation_rate == 1.0`, `no_show_rate is None`.

**Cancellation attribution**, including a row with `cancelled_by = None` counted in neither bucket, and `cancelled_by_customer + cancelled_by_owner <= status_totals.cancelled` (Risk 11 — a contract property, `<=` not `==`).

**Type folding**, all five cases:
- a type **renamed mid-window** → one row, labelled from the greatest **`created_at`**. The fixture puts `created_at` and `starts_at` in **opposite** orders across the rename, so `max(starts_at)` labelling red-fails. Without that the test passes under either rule and pins neither.
- a type **archived during the window** → still present, still named.
- a name **freed and reused** by a second `appointment_type_id` → two rows, not one.
- **those two reused-name IDs at equal counts** → the full ordered list is stable under a reversed input order. That is the `str(appointment_type_id)` tie-break in `(-count, name, str(appointment_type_id))`.
- **C2**: a cancelled booking of a type does **not** raise its count, and `sum(appointment_types[].bookings) <= sum(weeks[].bookings)`.

**New vs returning vs repeat**, three shapes:
- two facts re-pointed to one `customer_id` → one cohort member with two lifetime bookings;
- a customer row with no bookings never appears (it cannot — the fold is over facts, D7);
- **the split shape** — customer A with two pre-window bookings, customer B with one in-window booking, which is what F15's collision branch actually leaves behind (it moves **one** confirmed future booking and nothing else). Asserts the **currently shipped** answer: B is scored `new` and excluded from `repeat_rate`. **This pins Risk 12's behaviour rather than assuming it away.**

### The code that makes them pass

`Backend/app/db/repositories/bookings.py` gains **only two module-level frozen dataclasses** in this task — the coroutines returning them arrive in Task 3, deliberately, because there is no fast test that can exercise a statement:

```python
@dataclasses.dataclass(frozen=True)
class BookingFact:
    """One row of D3's narrow window projection — seven scalar columns, never
    select(Booking). `notes` (free customer text), `manage_token_hash` (a
    credential hash) and `dress_name` must not enter a process that only counts,
    and seven columns is smaller as well as disclosure-minimizing."""
    starts_at: datetime
    created_at: datetime
    status: str
    cancelled_by: str | None
    customer_id: UUID
    appointment_type_id: UUID | None
    appointment_type_name: str | None


@dataclasses.dataclass(frozen=True)
class CustomerHistory:
    first_starts_at: datetime
    bookings: int
```

`Backend/app/dashboard/schemas.py` — plain `BaseModel`s used as return-type annotations, never `response_model=` (the shipped house form). **No `ForbidExtraModel`**: the endpoint takes no body, so there are no extras to forbid.

`WeekBucket` · `StatusTotals` · `AppointmentTypeCount` · `CustomerMix` · `HistoryPanel` · `ForwardPanel` · `DashboardResponse`, field-for-field as the spec's normative payload block. Nullable rates are `float | None`. **Copy the spec's worked example into this file's docstring only after re-checking it against D2's three shape invariants** — that block is normative and an off-by-one-week example already survived one review.

`Backend/app/dashboard/service.py`, the pure half:

| Name | Shape |
|---|---|
| `HISTORY_WEEKS = 12` | one quarter, twelve bars, the smallest thing that shows a season |
| `FORWARD_WINDOW_DAYS = 7` | |
| `TOP_APPOINTMENT_TYPES = 5` | |
| `HistoryWindow` | frozen: `first_week_start`, `current_week_start`, `from_instant`, `until_instant` |
| `history_window(today: date) -> HistoryWindow` | D2's five lines, **every edge advanced in date space and converted once** |
| `week_buckets(window, facts) -> list[WeekBucket]` | pre-generated, zero-filled, `status != 'cancelled'` |
| `status_totals(facts) -> StatusTotals` | all four statuses |
| `cancellation(facts) -> tuple[float | None, int, int]` | rate over all four statuses, plus the two attributions |
| `no_show_rate(totals) -> float | None` | denominator is `no_show + completed` only |
| `top_types(facts) -> list[AppointmentTypeCount]` | group by id, label from `max(created_at)`, sort `(-count, name, str(id))`, non-cancelled (C2) |
| `customer_mix(facts, history, *, from_instant) -> CustomerMix` | cohort = distinct `customer_id` on non-cancelled facts |
| `build_history(window, facts, history) -> HistoryPanel` | one entry point, so the shape-invariant test has one call |

`history_window` needs **no `date.min`/`date.max` guard** — unlike `OwnerBookingService.list_day` (`booking/owner.py:163-172`) and `slot_window` (`storefront/service.py:288-299`), no caller-supplied date reaches any arithmetic here. `today` comes from a real clock. **That is the reason the endpoint takes no parameters**, and the comment says so, because it is what a later "just add a `?weeks=` param" would silently break.

- **Done when**: `make lint` clean (`ruff check` + `ruff format --check` + `mypy app tests`), `make test` green locally and on CI. `test_dashboard_math.py` is the whole proof — nothing in this task needs Postgres.
- **Gate**: `make lint && make test`.
- Commit **2**: `feat(dashboard): the Jerusalem window arithmetic and the six metric folds` — the four backend files above + `test_dashboard_math.py`.

## Task 2 — `forward_capacity` in `slots_io.py`, and the clamp (TDD, fast)
`Backend/app/booking/slots_io.py` (**edit**), `Backend/tests/test_dashboard_math.py` (**extend**)

**Tests first**, in a `--- forward utilization ---` section of the existing pure module — `grid_totals` takes a `Sequence[Slot]` and a `Mapping[datetime, int]`, so it needs no session:

- an instant with `booked > capacity` **clamps to `capacity`**;
- an instant present in `booked_by_instant` but **absent from the grid contributes nothing** (a booking made under a weekly rule the owner has since deleted, or on a date a later exception closed — the rows exist and are counted but have no capacity behind them);
- `capacity == 0` → `utilization is None`;
- on every populated case `booked <= capacity` **and** `utilization == booked / capacity`. **This is the pair that red-fails if anyone ships `sum(booked_by_instant.values())` as `forward.booked`** (D4, review finding 19).

### The code

`Backend/app/booking/slots_io.py` — the module docstring's sentence *"it holds exactly one caller-facing question: is this instant offered right now?"* becomes two questions, and the new one is named. Then:

```python
@dataclasses.dataclass(frozen=True)
class ForwardCapacity:
    capacity: int
    booked: int          # the CLAMPED GRID SUM, never sum(booked_by_instant.values())

    @property
    def utilization(self) -> float | None:
        return self.booked / self.capacity if self.capacity else None


def grid_totals(grid, booked_by_instant) -> ForwardCapacity:
    """Iterate the GRID, not the dict. count_by_start can hold instants the grid
    no longer offers, so summing the dict produces booked > capacity and a
    utilization above 100%. min(booked, capacity) is the same defensive posture
    Slot.remaining takes with max(capacity - booked, 0) for the identical
    anomaly (slots.py:36-41)."""


async def forward_capacity(
    session, *, tenant_id, window_start, window_end, now, rules, exceptions, bookings
) -> ForwardCapacity:
```

`forward_capacity` does the three reads `StorefrontService.list_slots` does (`storefront/service.py:207-218`), calls `materialize_slots(..., booked={}, window_start=window_start, window_end=window_end, now=now)` **once**, and hands the grid to `grid_totals`. Its parameter shape copies `offered_slot`'s verbatim (`slots_io.py:28-37`) — same three repositories, same keyword-only spelling.

**The ±1 lives inside this coroutine, in one place, with the comment on it.** `window_end` is an inclusive **date** for the engine (`slots.py:116-117, 134`); `count_by_start` is **half-open on the right** over instants, so its ceiling is boutique-midnight of `window_end + 1 day`:

```python
first = combine(window_start, time.min, tzinfo=BOUTIQUE_TIMEZONE).astimezone(UTC)
last  = combine(window_end + timedelta(days=1), time.min, tzinfo=BOUTIQUE_TIMEZONE).astimezone(UTC)
```

This is `StorefrontService.list_slots`'s three-line idiom verbatim, comment and all — *"the right edge is half-open — start of the day AFTER `window_end`"*. Writing `last = midnight(window_end)` reads correct against the sentence "the window is `[today, today + 6]`" and understates `forward.utilization` by up to a seventh, permanently and silently. Task 5's `db` test is what catches it.

**The docstring carries D4's disclosure posture**, where the next caller actually reads it: this panel deliberately republishes the density aggregate `materialize_slots` fences the anonymous surface against (`slots.py:149-152`), it is allowed because the route is behind `require_role(OWNER, SHIFT_MANAGER)` on a host-resolved tenant reading its own rows and `GET /manage/slots` already ships **per-slot** `capacity` and `remaining` to the same two roles (`booking/owner_router.py:306-330`), **and `forward_capacity` must never grow a slot-list return** — that is the shape the fence exists to stop.

**`app/booking/slots.py` is not edited.** Not one character.

- **Done when**: `make lint` + `make test` green. The end-to-end behaviour is Task 5's `db` suite — **CI only**.
- **Gate**: `make lint && make test`.
- Commit **3**: `feat(booking): forward_capacity — a complete grid from booked={}` — `Backend/app/booking/slots_io.py`, `Backend/tests/test_dashboard_math.py`.

## Task 3 — The two repository reads (TDD, **`db`-marked → CI only**)
`Backend/app/db/repositories/bookings.py` (**edit**), `Backend/tests/test_dashboard_db.py` (**new, `pytestmark = pytest.mark.db`**)

**Tests first**, in a `--- the two statements ---` section. Module-level `pytestmark = pytest.mark.db`; NullPool engines in `try/finally`; the **`app_role_url`** fixture, **never the superuser** (`conftest.py:26-29` states why: the container superuser bypasses RLS unconditionally, which would make every isolation assertion vacuously pass); `tenant_session` for every read; a fresh `uuid4()` tenant per test.

- `list_window_facts` returns exactly the rows in `[from_instant, until_instant)` and nothing outside — a booking one microsecond before the floor and one exactly on the ceiling are both absent.
- Every status comes back, cancellations included, and a soft-deleted row does not.
- `history_by_customer` returns the right `min(starts_at)` and count for a customer with bookings on **both sides** of the window edge — the whole reason this read cannot fold into the projection (D7).
- `history_by_customer([])` short-circuits to `{}` with no statement issued.
- `history_by_customer` excludes cancelled bookings and anything at or after `until_instant`.

### The code

```python
async def list_window_facts(
    self, session, tenant_id, *, from_instant, until_instant
) -> list[BookingFact]:
    """D3's narrow window projection: seven scalar columns, EVERY status, one
    range scan on idx_bookings_tenant_starts, half-open on the right.

    Deliberately not select(Booking): the ORM row drags notes (free customer
    text), manage_token_hash (a credential hash) and dress_name into a process
    that only counts.

    Deliberately not count_by_start: its `status <> 'cancelled'` predicate
    mirrors the occupancy indexes, so a cancellation rate computed under it is
    structurally always 0%. Widening count_by_start is worse — the slot engine
    depends on it, and the one thing that predicate must not do is change."""
```

`select(Booking.starts_at, Booking.created_at, Booking.status, Booking.cancelled_by, Booking.customer_id, Booking.appointment_type_id, Booking.appointment_type_name).where(tenant_id ==, starts_at >=, starts_at <, deleted_at.is_(None))`. **No `ORDER BY`** — nothing downstream depends on row order, which is precisely why D6's sort key carries `str(appointment_type_id)` as a total tie-break.

```python
async def history_by_customer(
    self, session, tenant_id, customer_ids, *, until_instant
) -> dict[UUID, CustomerHistory]:
```

`aggregate_by_dress`'s shape verbatim (`db/repositories/dress_variants.py:39-62`): empty-input short-circuit, `select(Booking.customer_id, func.min(Booking.starts_at), func.count())`, `.where(tenant_id ==, customer_id.in_(...), status != 'cancelled', starts_at < until_instant, deleted_at.is_(None))`, `.group_by(Booking.customer_id)`, dict comprehension. Rides `idx_bookings_tenant_customer`.

Both keep `deleted_at IS NULL` and the redundant explicit `tenant_id` predicate — the class docstring's stated defence-in-depth, and here it matters more than on a row read: with no tenant context set, `current_setting('app.tenant_id', true)::uuid` is NULL, every row is filtered out, and an aggregate returns a **plausible all-zeros dashboard** rather than a visible 404.

- **Done when**: `make lint` clean, `make test` green (these are `db`-marked, so locally they are **collected and deselected** — the summary line says so), `make test-db` green **on CI**.
- **Gate**: `make lint && make test` locally; `make test-db` on CI.
- Commit **4**: `feat(db): the dashboard window projection and per-customer history` — `Backend/app/db/repositories/bookings.py`, `Backend/tests/test_dashboard_db.py`.

## Task 4 — `DashboardService`, the sixth `/manage` router, `main.py` wiring and the fast API suite (TDD — **the milestone task**)
`Backend/app/dashboard/service.py` (**edit — the class**), `Backend/app/dashboard/router.py` (**new**), `Backend/app/main.py` (**edit — two lines plus a comment**), `Backend/tests/test_dashboard_api.py` (**new, no marker**)

**Tests first**, on the `test_staff_api.py` template: a duck-typed `FakeDashboardService` assigned to **`app.state.dashboard_service`** (not `app.dependency_overrides` — `get_dashboard_service(request)` reads `app.state` directly, the way every other `/manage` dependency does), a `FakeAuthService`, a hardcoded `TenantContext` resolver, no database.

### The failing tests

- **`ROUTES: list[tuple[str, str, dict | None]]` — one row, `("GET", "/manage/dashboard", None)`** — driving `test_every_route_requires_authentication` (401 `NOT_AUTHENTICATED`, and the fake records **zero** calls), `test_every_route_is_wired_and_reaches_the_service` (200 + the service was reached) and the `cache-control: no-store` assertion. **This table is the sixth-router shadowing guard.**
- **`SPEC_ERROR_CODES = {"NOT_AUTHENTICATED", "NOT_AUTHORIZED"}`** plus `test_every_spec_error_code_is_asserted`. ⚠ **The hand-union must NOT include `CSRF_ORIGIN_MISMATCH`.** `CsrfOriginMiddleware` fences `MUTATING_METHODS` only (`csrf.py:48`) and this is a GET, so unioning it the way `test_staff_api.py:458-466` does red-fails against a set that cannot contain it. The template computes `covered` from `ERROR_CASES` rows only, so both codes need a row.
- **Both roles get 200.** `owner` and `shift_manager`, same body.
- The shared `UNKNOWN_ROLE` sentinel gets the **exact generic 403 body** (`NOT_AUTHORIZED_BODY` imported from `app.main`), and the fake records zero calls — the gate raises during dependency solving.
- **The handler passes the host-resolved tenant.** `FakeDashboardService` records the `tenant_id` it was called with; the test asserts it equals the resolver's `TENANT.id`. **This is the only place the trust path is observable** — Task 5's `db` isolation test runs below the router.
- **A disclosure walk with F52's OWN forbidden set.** `_all_keys` (the recursive every-key-at-every-depth helper, `test_storefront_api.py:643-651`) is **reused**; the storefront's `FORBIDDEN_KEYS` is **not**:

  ```python
  # NOT test_storefront_api.FORBIDDEN_KEYS. That frozenset was built for F10's
  # manage-only storefront leaks: it contains no customer_id, no phone key and no
  # `name`, so borrowing it proves nothing about this endpoint's PII claim — and it
  # DOES contain `capacity`, which F52 legitimately ships at forward.capacity, so
  # borrowing it would red-fail against this spec's own contract.
  #
  # `capacity` is deliberately permitted (D4: role-gated route, and GET
  # /manage/slots already discloses strictly more to the same two roles).
  # The bare key `name` cannot be forbidden — appointment_types[].name is a TYPE
  # label, never a person's; the customer-name key, if one ever appeared, is
  # customer_name.
  DASHBOARD_FORBIDDEN_KEYS = frozenset(
      {"customer_id", "phone", "customer_name", "notes",
       "manage_token_hash", "email", "dress_name", "seat_index"}
  )
  ```

  The walk runs against a **fully populated** `FakeDashboardService` response — non-empty `weeks`, non-empty `appointment_types`, real `customers`, real `forward` — **so it cannot pass vacuously on an all-`null` payload.**

### The code

`DashboardService(session_factory, clock: Clock | None = None)` in `app/dashboard/service.py`, below the pure half. **Its own clock**, resolved with the house one-liner (`booking/owner.py:143-145`: `now = self._clock() if self._clock is not None else datetime.datetime.now(datetime.UTC)`); it never borrows `StorefrontService._clock`, and `create_app` wires none — the parameter exists for tests. It builds its own `BookingsRepository()`, `AvailabilityRulesRepository()` and `AvailabilityExceptionsRepository()`, the `AuthService.__init__` shape.

`async def dashboard(self, tenant_id) -> DashboardResponse` — one `async with tenant_session(self._session_factory, tenant_id) as session:` holding **three** reads and one engine call:

1. `today = today_jerusalem(self._clock)`; `window = history_window(today)`;
2. `facts = await self._bookings.list_window_facts(session, tenant_id, from_instant=window.from_instant, until_instant=window.until_instant)`;
3. `history = await self._bookings.history_by_customer(session, tenant_id, cohort_ids, until_instant=window.until_instant)` — the cohort ids come from the facts, so this is the request's **second and last** booking statement;
4. `forward = await forward_capacity(session, tenant_id=tenant_id, window_start=today, window_end=today + timedelta(days=FORWARD_WINDOW_DAYS - 1), now=self._now(), rules=..., exceptions=..., bookings=self._bookings)`.

`window_end` is `today + 6`, **not** `today + 7`: the engine's window is inclusive on both ends (`slots.py:116-117, 134`), so `today + 7` materializes eight days of capacity into a metric labelled seven and inflates the denominator by ~14% with nothing to reveal the error.

**No audit row.** No GET handler in this product writes one — not the booking day list, not the booking detail that renders a bride's phone and free-text notes, not the owner-only staff list. A landing screen is the most-hit read in the console and an audit row would make every page load a write. A comment says so.

`Backend/app/dashboard/router.py` — the sixth `/manage` router:

```python
router = APIRouter(
    prefix="/manage",
    dependencies=[Depends(_no_store), Depends(require_role(StaffRole.OWNER, StaffRole.SHIFT_MANAGER))],
)
Service = Annotated[DashboardService, Depends(get_dashboard_service)]

@router.get("/dashboard")
async def get_dashboard(request: Request, service: Service) -> DashboardResponse:
    return await service.dashboard(get_current_tenant(request).id)
```

- **`_no_store` is a fourth local three-line copy**, not an import. The alternative points the dependency arrow backwards to save three lines; `auth/staff_router.py:22-27` records the decision and this docstring restates it.
- **`get_current_tenant(request)`, host-derived** — what every shipped `/manage` handler without exception uses, bound by `TenantResolutionMiddleware` from the Host header and nothing else (`tenancy/middleware.py:57-76`). **No `Staff` parameter is declared.** F52 is the first `/manage` route with no audit row and no self-guard to need one, which makes it exactly the route where an implementer reaches for `StaffContext.tenant_id` because it is already in hand. The `RoleGate` runs router-level and needs no binding here.
- Module docstring carries the **shadowing warning** the catalog, owner-booking and staff includes carry (`main.py:678-691` — three of the six, not five; the first three at `:675-677` carry none because each is the first on its prefix) and names `test_dashboard_api.py`'s `ROUTES` table as its guard.
- **No rate limiter**, and the reason is one leg, not two: no `/manage` router carries one and F52 does not introduce the first. CSRF fencing is **not** part of this route's posture — `CsrfOriginMiddleware` gates on `request.method in MUTATING_METHODS` and this is a GET. The protection is the session cookie and the role gate, alone.

`Backend/app/main.py` — two lines plus one comment:
- `app.state.dashboard_service = DashboardService(get_session_factory())`, beside `app.state.staff_service` (`main.py:328`);
- `app.include_router(dashboard_router)` **after** `staff_router` (`main.py:691`) and before `storefront_router`, carrying the **sixth** instance of the shadowing comment, pointing at `test_dashboard_api.py`'s `ROUTES` table.

**No new error code, no new body, no new handler, no other `main.py` change.** The endpoint takes no input, so there is nothing to 400 on, and it reads rows that may legitimately not exist, so there is nothing to 404 on — an empty tenant is a valid all-zero dashboard, not a miss.

### `Backend/tests/test_staff_role_gating.py` is NOT edited

Verified against the shipped file. Its default-deny walker reads the **live** route table, so the router-level `RoleGate` covers `/manage/dashboard` with no test written — provided the gate is actually there, and a router without one is a red build (`test_every_manage_route_is_role_gated`). **`OWNER_ONLY` stays exactly as F51 left it** (`:59`): adding a both-roles route to it makes `test_route_table_matches_the_permission_matrix` report it as `unenforced_owner_only` and red-fail with a message about a missing owner-only gate. Note also that the module's HTTP matrix tests iterate `[*ROUTES, *CATALOG_ROUTES]` imported from two other modules (`:312`, `:343`), so they do **not** pick up F52's route — the HTTP behaviour is proven in `test_dashboard_api.py`'s own walks. `test_no_route_is_registered_twice_across_routers` (`test_storefront_api.py:564-573`) stays green **untouched**: F52 adds no `/storefront` path.

- **Done when**: `make lint` + `make test` green, locally and on CI. **This is the milestone task**: the route, the role gate, the tenant trust path and the disclosure contract are exercised end to end with no Postgres.
- **Gate**: `make lint && make test`.
- Commit **5**: `feat(dashboard): GET /manage/dashboard, the sixth /manage router and app wiring` — `Backend/app/dashboard/service.py`, `Backend/app/dashboard/router.py`, `Backend/app/main.py`, `Backend/tests/test_dashboard_api.py`.

## Task 5 — The rest of the `db`-marked suite (written here, executed on CI)
`Backend/tests/test_dashboard_db.py` (**extend**)

Extends the module Task 3 created, now against the real `DashboardService`.

- **Forward utilization end to end** against a real rule set, with one slot booked to capacity **on `today + 6` specifically**:
  - the fully-booked instant is present in the **denominator** — *this is the assertion that fails if anyone builds the grid from `list_slots` instead of `booked={}`*;
  - it is present in the **numerator** — *this is the assertion that fails if `until_instant` is written as boutique-midnight of `today + 6` rather than `today + 7`. With the booked slot anywhere else in the window, both spellings pass.*
  - utilization comes out at the hand-computed value.
- A booking at an instant the current rules **no longer offer** contributes nothing to `forward.booked`.
- **Tenant isolation.** Tenant B's dashboard does not see tenant A's bookings — asserted **together with tenant A's own numbers being non-zero in the same test**, because an all-zeros pass is exactly what a missing `tenant_session` produces and it would otherwise read as green (D3).
- The service's own assembly — three reads and one engine call inside one `tenant_session` — is exercised here and **nowhere else**, because `test_dashboard_api.py` swaps in a fake. Recorded in §"What a local run cannot prove".

Seeding uses `asyncio.run` where a `TestClient` is involved (`test_staff_role_gating_integration.py:15-18`'s loop rule). A frozen clock is injected via `DashboardService(session_factory, clock=...)` so the fixture dates are stable.

- **Done when**: `make test-db` green **on CI**. Locally these collect and skip; `make lint` (mypy over `tests`) is the only local signal.
- **Gate**: `make lint` locally; `make test-db` on CI.
- Commit **6**: `test(dashboard): db-marked forward utilization on day seven and tenant isolation` — `Backend/tests/test_dashboard_db.py`.

---

# Part II — the frontend

## Task 6 — Wire types, the API method, the plain-date helper and the Hebrew copy
`Frontend/apps/manage/src/api.ts` (**edit**), `Frontend/apps/manage/src/lib/jerusalem.ts` (**edit — C3**), `Frontend/apps/manage/src/i18n/he.ts` (**edit**), `Frontend/apps/manage/src/i18n/ar.ts` (**edit**), `Frontend/apps/manage/src/__tests__/jerusalem.test.ts` (**edit — C3**), `Frontend/apps/manage/src/__tests__/i18n.test.ts` (**edit**)

**Tests first** in `jerusalem.test.ts` and `i18n.test.ts`.

### `jerusalem.test.ts` — a new describe block for `plainDate` (C3)

- `plainDate("2026-05-03") === "3.5.2026"` and `plainDate("2026-07-25") === "25.7.2026"` — unpadded d.m.yyyy, the spelling `comms_templates.py` already texts the bride, so the owner reads one date format across the product.
- **The negative control, and it is the whole point of the helper**: the suite runs under `TZ=America/New_York` (`apps/manage/package.json:11`), where `new Date("2026-05-03")` is UTC midnight = **2 May, 20:00 local**. A comment states that a device-clock read of the same string prints `2.5.2026`, which is why `plainDate` splits the string and never constructs a `Date`.

### `i18n.test.ts` — the `HE_F52` fold

```ts
const HE_F52 = entries(he.translation, (k) => k === "nav.dashboard" || k.startsWith("dashboard."));
const HE = [...HE_F15, ...HE_F51, ...HE_F52];
```

**A separate constant, not a widened filter.** The file's own comment (`:12-16`) records why: folding groups together lets one feature's floor absorb another's rows. Its own describe block, `expect(HE_F52.length).toBeGreaterThan(40)` — just under the deck's **43** rows (counted: §1 3, §2 4, §3 2, §4 7, §5 6, §6 9, §7 7, §8 5). Plus `expect(i18n.t("nav.dashboard")).toBe("סקירה")` and a resolution check on `dashboard.rateUnderFloor` and `dashboard.notEnoughData`.

**Without the fold into `HE`, the resolve check, both register guards and the `ar` parity guard silently skip every F52 key.** That is the whole reason the constant is folded and not just declared.

Note the register guard at `:99`: `/נשלח|תישלח|בדרך/`. **«בדרך» is a natural Hebrew word for a rising trend** and would red-fail a test whose message is about SMS sends. `copy.md` §0 rule 2 records that the deck is written around it; if a transcribed string trips it, the string is wrong, not the test.

### The code

**`api.ts`** — a `// --- dashboard wire types (mirror backend/app/dashboard/schemas.py) ---` banner before `// --- endpoints ---`, the seven interfaces mirrored **field-for-field in snake_case**, and one line on the exported `api` object:

```ts
getDashboard(): Promise<DashboardResponse> { return apiFetch("/manage/dashboard"); }
```

There is **no case-conversion layer in this repo** — `api.ts:1-5` states it. A camelCase interface compiles fine and reads `undefined` at runtime on every field. Nullable rates are `number | null`, matching `float | None`. **`packages/api-client` is not touched** — it is an intentionally empty stub and each app ships its own `src/api.ts`.

**`lib/jerusalem.ts`** — `plainDate(iso)`, two lines, with a comment saying it takes a **plain Jerusalem calendar date, never an instant**, and that routing one through `new Date()` and a zoned formatter re-zones a date that was never in a zone. Placed beside the existing helpers, above `todayJerusalem`.

**`he.ts`** — `nav.dashboard` + the flat `dashboard.*` block: **every one of the deck's 43 rows, verbatim**, in the file's existing dotted-literal style.

**`ar.ts`** — the same 43 keys, values = the approved Hebrew standing in untranslated, **never `""`**. i18next's `returnEmptyString` default renders `""` rather than falling back, so an empty placeholder blanks the page instead of showing Hebrew. Appended to the existing file, whose header already says later console features append theirs.

⚠ **`dashboard.summary` uses `{{count}}`, which is i18next's plural trigger.** It resolves through the base key today because no `dashboard.summary_one` / `_other` exist — the same shape `booking.dayCount` already ships and `i18n.test.ts:51` already pins. **Do not add suffixed variants**; Hebrew's dual would then need a third and the announced sentence would fork.

**No `vite.config.ts` change** — `/manage` is already forwarded by the dev proxy. **No new `MIRRORS` row** in `test_frontend_constant_parity.py`: `HISTORY_WEEKS`, `FORWARD_WINDOW_DAYS` and `TOP_APPOINTMENT_TYPES` are server-side shape decisions and the client mirrors no numeric bound.

- **Done when**: `make lint` clean, `make fe-test` green, `make fe-build` clean.
- **Gate**: `make lint && make fe-test && make fe-build`.
- Commit **7**: `feat(manage): dashboard wire types, the plain-date helper and the Hebrew copy` — the six frontend files above.

## Task 7 — `DashboardSection` (TDD)
`Frontend/apps/manage/src/components/DashboardSection.tsx` (**new**), `Frontend/apps/manage/src/__tests__/DashboardSection.test.tsx` (**new**)

**Tests first**, the `CatalogSection.test.tsx` pattern: `vi.mock("../api")` with `importActual` for `ApiError` / `errorMessage`, fixture builders, `vi.mocked`. `axe-core` is **already** a devDependency of `apps/manage` (`package.json:33`) — no new dependency.

### The failing tests

- **loading** → `<Skeleton variant="text" lines={6} />` and `dashboard.loading` in the `role="status"` region.
- **outage** → one `role="alert"` carrying `dashboard.loadFailed`, the status region empty, and **no stacked zero-data content** — the catch sets only `loadError` and leaves the data state `null`. **Including a 403 `ApiError`**, which D10's landing change makes reachable: `RoleGate` fails closed on any role string the enum does not know, `reachable` is then empty, and `reachable[0]?.key ?? section` lands such a staffer on the initial section — now the dashboard rather than a 200-ing Profile panel.
- **populated render** — five Cards in the deck's order: **forward first**, then weeks, rates, customers, types.
- **zero-data render** — the same five Cards, all values `0` or `dashboard.notEnoughData`, plus `dashboard.firstRunNote`. **No `EmptyState` anywhere**, and nothing hidden.
- **The three rate facts, three strings** (C1): `0.0` → `0.0%`; `0.0004` → `t("dashboard.rateUnderFloor")`; `0.004` → `0.4%`; `null` → `t("dashboard.notEnoughData")`.
- **The bars are decoration**: every bar is `aria-hidden="true"` and every value it draws is present as text in the same row. The assertion the design is answerable to — *remove every bar and the screen loses nothing*.
- **No `role="progressbar"`, no `role="meter"`, no `<meter>`, no `<progress>`** anywhere in the rendered tree.
- **Bidi**: every number, percentage and date inside `<bdi dir="ltr">`; appointment-type names inside a **bare** `<bdi>` (`dir="ltr"` on a Hebrew name is itself a bidi defect); a range is **one** `<bdi dir="ltr">` around `{from}–{to}` together, not two.
- `max(weeks[].bookings) === 0` → every fill is `0%`, **not `NaN%`** — `count / max` with `max === 0` is `NaN`, and `inlineSize: NaN%` is an ignored declaration that silently leaves the previous width in a re-render.
- `capacity === 0` → `dashboard.forwardNoHours` and **no bar drawn**.
- `types.length === 0` → one muted `<p>` (`dashboard.typesEmpty`), not a table and not an `EmptyState`.
- **an axe pass at zero violations**: `expect((await run(container)).violations).toEqual([])`.

### The code

`BookingsSection.tsx:27-51` verbatim in shape: `useEffect`, `let cancelled = false`, one `api.getDashboard()`, **no interval, no refetch control** (D11). No props. The failure register is `BookingsSection`'s down to the comment recording that the catch deliberately does **not** set the data state to an empty value.

Structure exactly as `manage-dashboard.md:34-89`. `SectionHeading as="h2" ornament`; panel headings are plain `<h3 className="text-sm font-semibold text-ink">` — markup, not a component, the idiom `StaffSection.tsx:345` / `TypesSection.tsx:214` / `HoursSection.tsx:162` all use.

**The bar**, the one hand-built thing:

```tsx
<span aria-hidden="true" className="block h-2 rounded-sm bg-border">
  <span className="block h-2 rounded-sm bg-gold-strong" style={{ inlineSize: `${pct}%` }} />
</span>
```

**`inlineSize`, never `width`** — a logical property, so in RTL the fill grows from the inline-start (right) edge. `pct` is clamped `Math.min(Math.max(pct, 0), 100)` even though the server already clamps `booked <= capacity`: one expression, and it is what keeps a contract change from painting outside the track. **Two bar semantics, kept apart by what they sit beside**: the forward bar is absolute (max = `forward.capacity`) and sits beside a percentage; the weeks and types bars are relative (max = the largest value in the visible list) and sit beside a count. No axis, no gridline, no tick.

`formatRate` exactly as `manage-dashboard.md:101-111`, including the derived floor. **The wire carries the unrounded quotient and the console does all rounding** (D5).

Tables for the two ranked panels — `<caption class="sr-only">`, `<th scope="col">` on both columns, `<th scope="row">` per row. `<dl>` for the tiles, each `<dt>`/`<dd>` pair wrapped in a `<div>`; sub-lines live **inside the `<dd>`** as `<span className="block">` — a `<p>` between a `<dt>` and a `<dd>` is invalid and axe reports it.

`dashboard.summary` goes through the shipped `isolateLtr` from `lib/booking.tsx:32-44` (**reused, not re-implemented**); `total` is `sum(weeks[].bookings)` summed client-side — arithmetic over numbers already on the wire, not a second definition. Dates go through `plainDate`. **Card padding is not overridden**: `cn()` is a plain `.filter(Boolean).join(" ")` with no conflict resolution, so a consumer `p-0` and `Card`'s baked-in `p-6` are same-specificity rules and the built stylesheet emits `.p-0` first — the override is silently inert.

**Cancellation attribution renders as two independent labelled tiles**, no "X of Y" framing and no sum shown: a row cancelled before migration 0010 carries NULL and is in neither (Risk 11).

⚠ **`make lint` will not catch a physical-direction property or a raw hex colour in this file.** `Frontend/scripts/qa-greps.sh` scopes both checks to `apps/storefront/src` only, and its unzoned-date-read check prints an advisory line without setting a failing status. This deck, this plan and review are the only guard — which is precisely why it is written down.

- **Done when**: `make lint` clean, `make fe-test` green including the axe pass at **zero** violations, `make fe-build` clean.
- **Gate**: `make lint && make fe-test && make fe-build`.
- Commit **8**: `feat(manage): the KPI dashboard section` — `DashboardSection.tsx`, `DashboardSection.test.tsx`.

## Task 8 — The landing change, and `Nav.test.tsx`'s five edits (C4)
`Frontend/apps/manage/src/App.tsx` (**edit**), `Frontend/apps/manage/src/__tests__/Nav.test.tsx` (**edit**)

**Tests first** in `Nav.test.tsx` — all five edits from C4, plus two new assertions:

- **both roles see the dashboard item**, and it is **first**;
- **the console lands on it**: on first render, `«סקירה»` carries `aria-current="page"` for an owner and for a shift manager, with no click.

### The code — `App.tsx`, four edits and an import

| Line | Change |
|---|---|
| `:15` | `SectionKey` gains `"dashboard"` |
| `:35-43` | `NAV` gains a **first** row `{ key: "dashboard", labelKey: "nav.dashboard", roles: ALL }` |
| `:49` | `useState<SectionKey>("profile")` → `useState<SectionKey>("dashboard")` |
| `:111` | `{activeKey === "dashboard" && <DashboardSection />}` added above the profile line |
| `:6-13` | the `DashboardSection` import, alphabetical among the others |

**That is the whole of the landing change.** `activeKey` already falls back to `reachable[0]?.key ?? section` (`:94-96`), and with dashboard first and reachable by both roles the fallback and the initial state now agree. `ConsoleShell` is **not** touched — its `ConsoleNavItem` contract is unchanged.

**The other half of that blast radius, recorded here because it is what makes the 403 test in Task 7 necessary**: an out-of-enum role reaches no `NAV` row, so `reachable[0]?.key ?? section` now lands it on the **dashboard** rather than on a 200-ing Profile panel, and its one fetch 403s. `NOT_AUTHORIZED` is reachable on this section. The copy rationale rests on "one string covers any `ApiError`", **not** on either code being impossible.

- **Done when**: `make lint` clean, `make fe-test` green (all five nav tests, plus `DashboardSection.test.tsx` and `i18n.test.ts` still green), `make fe-build` clean.
- **Gate**: `make lint && make fe-test && make fe-build`.
- Commit **9**: `feat(manage): the dashboard is the console's landing section` — `App.tsx`, `Nav.test.tsx`.

## Task 9 — Gates and the run report
No files, no commit.

Run the verification block below in order, report what ran and what passed, and state **explicitly** that `test_dashboard_db.py` executes only on CI. **Re-nag Risks 5, 12 and 13 in the run report**:

- **Risk 5** — the no-show rate can be computed over a handful of appointments and still render as a percentage. Bounded by `status_totals.confirmed` shipping beside it and by `dashboard.noShowHelp` stating the denominator in words. *Owner: **user**, to overturn — not to authorise.*
- **Risk 12** — a phone correction can split one human's history across two `customer_id`s and she then reads as `new`. Pinned by a pure test asserting the shipped answer.
- **Risk 13** — between zero and six days of the most recent data are on **no panel** of this screen. Accepted, not closed; the copy must never imply the two panels are a continuous span.

Also carry forward: **F51's Risk 3 is not closed here** and now has no queued owner until F34 (D11). No push, no PR — the orchestrator owns review and shipping.

---

## Local gate commands, in order

Per task, as listed above. At the end of the build, in this order:

```
make lint      # ruff check . && ruff format --check . && mypy app tests
               #   + pnpm -r lint && pnpm -r typecheck
               #   + bash Frontend/scripts/qa-greps.sh
make test      # pytest -m "not db" -q
make fe-test   # pnpm -r --if-present test
make fe-build  # pnpm -r build
make e2e       # pnpm -r build && playwright install chromium && pnpm e2e
```

`make test-db` (`pytest -m db -q`) is **CI only** — there is no Docker locally. Every path in the Makefile is `$(CURDIR)`-quoted; the repo path contains a space and a `+`, so run these from the worktree root and never hand-build a `cd`.

**Green looks like:**

- `make lint` — ruff clean, `ruff format --check` clean, **mypy zero errors over `app` and `tests`**, `pnpm -r lint` and `pnpm -r typecheck` clean across all four workspace packages, and `qa-greps.sh` exit 0 printing **none** of F52's files. F52 adds no new date-formatting call on an instant, so the advisory date-read block's output is unchanged from F51's merge.
- `make test` — all fast tests pass; `test_dashboard_math.py`, `test_dashboard_api.py` green; `test_staff_role_gating.py` green **with no edit at all**; `test_storefront_api.py::test_no_route_is_registered_twice_across_routers` green untouched; `test_dashboard_db.py` **collected and deselected**, and the summary line says so.
- `make fe-test` — `DashboardSection.test.tsx` green including the axe pass at **zero** violations; `Nav.test.tsx` green with C4's five edits; `jerusalem.test.ts` green with the `plainDate` block; `i18n.test.ts` green with F15's `> 70` and F51's `> 25` floors **still reading their own key sets alone**.
- `make fe-build` — both apps build; no unused-import or unused-variable TS error.
- `make e2e` — the existing storefront and console specs stay green. **F52 adds no e2e spec**, so an unchanged e2e count is the expected result, not a gap: `e2e/a11y.spec.ts` only reaches `http://localhost:4174` unauthenticated, no backend runs during e2e, so `api.me()` fails and `App` renders `LoginForm`. Every authenticated console section is unreachable to axe there. The dashboard's accessibility proof is the vitest axe test plus the deck's a11y section; claiming e2e coverage for it would be false.
- **CI additionally**: `make test-db` green, including the window projection bounds, `history_by_customer` across the window edge, forward utilization with the booked slot on `today + 6`, the off-grid booking, and tenant isolation with tenant A's own numbers non-zero in the same test.

---

## Every EXISTING file this feature edits

A new file is a decision the reviewer sees. An edited one is not, so they are all enumerated:

| File | Edit | Task |
|---|---|---|
| `.planning/specs/kpi-dashboard.md` | the four C-amendments | 0 |
| `Backend/app/db/repositories/bookings.py` | `BookingFact` + `CustomerHistory` (T1); `list_window_facts` + `history_by_customer` (T3) | 1, 3 |
| `Backend/app/booking/slots_io.py` | docstring's "exactly one caller-facing question" → two; `ForwardCapacity`, `grid_totals`, `forward_capacity` | 2 |
| `Backend/app/main.py` | `app.state.dashboard_service = …` beside `:328`; `app.include_router(dashboard_router)` after `:691` with the sixth shadowing comment | 4 |
| `Frontend/apps/manage/src/api.ts` | the wire-type banner, seven interfaces, `getDashboard()` | 6 |
| `Frontend/apps/manage/src/lib/jerusalem.ts` | `plainDate(iso)` (**C3 — not in the spec's file table**) | 6 |
| `Frontend/apps/manage/src/i18n/he.ts` | `nav.dashboard` + the flat `dashboard.*` block, 43 rows | 6 |
| `Frontend/apps/manage/src/i18n/ar.ts` | the same 43 keys, approved Hebrew standing in, **never `""`** | 6 |
| `Frontend/apps/manage/src/__tests__/jerusalem.test.ts` | the `plainDate` describe block (**C3**) | 6 |
| `Frontend/apps/manage/src/__tests__/i18n.test.ts` | `HE_F52` constant, folded into `HE`, own describe block, `> 40` floor | 6 |
| `Frontend/apps/manage/src/App.tsx` | `SectionKey`, the first `NAV` row, the initial `useState`, the render line, the import | 8 |
| `Frontend/apps/manage/src/__tests__/Nav.test.tsx` | C4's **five** edits | 8 |

**Files that must NOT be edited**, each for a stated reason:

| File | Why not |
|---|---|
| `Backend/app/booking/slots.py` | *"Three implementations of this question would be three chances to disagree."* `booked={}` produces the identical grid with zero change to the engine. An `include_full` flag would be a switch whose only purpose is disabling a disclosure control on the function that also serves anonymous traffic. |
| `Backend/tests/test_staff_role_gating.py` | The walker reads the live route table; `OWNER_ONLY` gaining a both-roles route red-fails as `unenforced_owner_only`. |
| `Backend/tests/test_frontend_constant_parity.py` | No `MIRRORS` row — the three constants are server-side shape decisions and the client mirrors no bound. |
| `Frontend/packages/ui/**` | No new component and **no promotion**. That restraint *is* the Q2 self-approval argument. |
| `Frontend/packages/api-client/**` | An intentionally empty stub; each app ships its own `src/api.ts`. |
| `Frontend/apps/manage/vite.config.ts`, `vitest.config.ts`, `package.json` | `/manage` is already proxied; `TZ=America/New_York` is already pinned at `package.json:11`. |
| `Frontend/apps/manage/src/components/BookingsSection.tsx` and the other six sections | F15's D16 stands: no i18n retrofit of the hardcoded-Hebrew sections. |

---

## Traps — the load-bearing gotchas, verbatim from the spec

**These are the sentences a builder who skims will violate.** They are quoted, not paraphrased.

1. **The slot engine DROPS full slots, which is why `forward_capacity` passes `booked={}`.**
   > Full slots are **DROPPED**, never marked: a public response that enumerated them would disclose the boutique's booking density. (`slots.py:149-152`)

   > Summing `capacity` over `StorefrontService.list_slots` or `OwnerBookingService.list_slots` therefore omits precisely the fully-booked slots — the ones that make utilization high. The resulting number is biased downward, can never reach 100%, and **the error grows as the boutique gets busier**, i.e. it is worst exactly when the number matters. Passing `booked={}` makes `taken` 0 at every instant, and `CHECK (capacity > 0)` guarantees `0 < capacity` holds everywhere, so nothing is dropped for fullness.

2. **DST-safe Sunday bucketing — every week edge is computed in DATE space and converted once.**
   > Israel's autumn transition is always a **Sunday** — the first day of the Israeli week — so the bucket containing it is 169 UTC hours and the March bucket is 167. `midnight_utc(2026-10-25) + 7 days` is `2026-10-31T21:00Z`; the real boundary is `22:00Z`. **Advancing on instants misfiles an hour of Saturday-night bookings twice a year**; advancing on `date` and converting each edge is exact, always.

   And the bucketing itself never touches a UTC instant:
   ```
   d      = fact.starts_at.astimezone(BOUTIQUE_TIMEZONE).date()
   bucket = d - timedelta(days=jerusalem_day_index(d))
   ```

3. **The never-empty i18n placeholder rule.**
   > `apps/manage/src/i18n/ar.ts` gains F52's keys, values = the approved Hebrew standing in untranslated, **never `""`** — i18next's `returnEmptyString` default renders `""` rather than falling back.

4. **`TZ=America/New_York` in frontend tests.**
   > Both suites run under `TZ=America/New_York`, which is what gives the date assertions bite.

   Already pinned at `apps/manage/package.json:11`. It is a **deliberately wrong** zone: on a UTC runner an unzoned read agrees with Jerusalem for most of the day, so a device-clock bug would pass.

5. **The wire is the backend's snake_case verbatim.**
   > **The wire format is the backend's snake_case verbatim.** `apps/manage/src/api.ts:1-5` states it — no case-conversion layer.

   > Mirrored field-for-field in **snake_case**. There is no case-conversion layer in this repo — `api.ts:1-5` states it — and **a camelCase interface compiles fine and reads `undefined` at runtime on every field.**

   (The `.claude/rules` `keysToSnake` / `keysToCamel` guidance is Kotlin/Micronaut boilerplate for another codebase and does not apply here.)

6. **The two forward bounds differ by one day and that is deliberate, not a typo.**
   > `materialize_slots`'s `window_end` is a **date** and inclusive on both ends, so it is `today + 6`; `count_by_start` is **half-open on the right** over instants, so its ceiling is boutique-midnight of `today + 7`. Writing `last = midnight(today + 6)` instead reads correct against the sentence "the window is `[today, today + 6]`" and is the mirror image of the `today + 7` denominator error: **day 7's capacity stays in the denominator while day 7's bookings vanish from the numerator, understating `forward.utilization` by up to a seventh, permanently and silently.**

7. **`forward.booked` on the wire is the clamped grid sum.**
   > **`forward.booked` on the wire is `taken` — the clamped grid sum — never `sum(booked_by_instant.values())`.** The local is named `booked_by_instant` for exactly that reason.

8. **The type label comes from `max(created_at)`, not `max(starts_at)`.**
   > `appointment_type_name` is snapshotted when the booking is created, so `starts_at` orders by *appointment date*, which in a boutique where brides book months ahead routinely disagrees: rename the type on 1 June; booking A created 1 May for 20 July carries the old name, booking B created 15 June for 20 May carries the new one; `max(starts_at)` picks A and **renders the label every booking made since June has already stopped using.**

9. **`CSRF_ORIGIN_MISMATCH` must not be in `SPEC_ERROR_CODES`.**
   > `test_dashboard_api.py`'s `test_every_spec_error_code_is_asserted` hand-unions the codes raised in dependency-solving, and unioning the CSRF code the way `test_staff_api.py:458-466` does would **red-fail against a set that cannot contain it**.

10. **The disclosure walk uses F52's own forbidden set.**
    > That frozenset was built for F10's manage-only storefront leaks and contains **no** `customer_id`, **no** phone key and **no** `name` — so borrowing it proves nothing about this endpoint's PII claim — while it *does* contain `capacity`, which F52 legitimately ships at `forward.capacity`, so borrowing it also red-fails on the spec's own contract.

11. **`Skeleton variant="text"`, never the default.**
    > **`variant="text"`, never the default `"block"`**, which renders `h-full w-full` and collapses to zero height inside a parent with no intrinsic height.

12. **`inlineSize`, not `width`; `aria-hidden`, not `role="progressbar"`.**
    > **`inlineSize`, not `width`** — so it grows from the inline-start edge in RTL. It is **not** `role="progressbar"`: that role announces a task's completion, not a ratio of a static quantity, and an AT would read the utilization bar as an in-flight operation.

13. **`null` is not `0`.**
    > **`null` means "not computable", never "zero"** — and the console must render those two differently. A boutique with no cancellations shows `0%`; a boutique with no bookings at all shows the sentence. Those are different facts and the copy deck gives them different strings.

14. **`max === 0` is a `NaN` guard, not a nicety.**
    > `count / max` with `max === 0` is `NaN`, and `inlineSize: NaN%` is an **ignored declaration that silently leaves the previous width in a re-render**.

15. **The tenant comes from the host, not from the session.**
    > `get_current_tenant(request)` is what **every** shipped `/manage` handler without exception uses, and it is host-derived. The other available source, `StaffContext.tenant_id`, is session-derived… F52 is the first `/manage` route with **no** independent reason to inject `staff` at all, which makes it exactly the route where an implementer reaches for the session id because it is already in hand.

16. **A missing tenant context does not 404 here — it returns a plausible screen.**
    > With no tenant context set, the policy's `current_setting('app.tenant_id', true)::uuid` is NULL, the comparison is NULL, and every row is filtered out — a `by_id` then 404s *visibly*, but an aggregate returns a perfectly plausible **all-zeros dashboard** with nothing in the response and nothing in the logs to say so.

---

## What a local run cannot prove

No Docker locally, so `pytest -m db` collects and skips.

| Task | Proof that is CI-only | What the local run still gives |
|---|---|---|
| **3** (repository reads) | the window projection's half-open bounds, every-status inclusion, soft-delete exclusion, `history_by_customer` across the window edge | `ruff` + `mypy` over the two new signatures and the two dataclasses |
| **5** (the service, end to end) | forward utilization with the booked slot on `today + 6` — **both the denominator and the numerator assertions**; the off-grid booking; tenant isolation with tenant A non-zero in the same test; **`DashboardService.dashboard()`'s three-reads-one-session assembly, which is exercised nowhere else** because `test_dashboard_api.py` swaps in a fake | `mypy` over `tests` |

Everything in Tasks 1, 2, 4 and 6–8 verifies locally. **Task 4 is the milestone**: the first point at which the route, the role gate, the host-derived tenant path and the disclosure contract are exercised end to end with no Postgres.

---

## Testing plan → spec criteria

| Spec criterion | Where |
|---|---|
| The window derivation against a frozen clock; all three shape invariants; the Sunday and Saturday boundaries | `test_dashboard_math.py` (fast) |
| Sunday bucketing; the 169/167-hour DST weeks; zero-fill and ordering | `test_dashboard_math.py` (fast) |
| `sum(weeks[].bookings) == confirmed + no_show + completed` | `test_dashboard_math.py` (fast) |
| Every rate `None` at a zero denominator; the three zero-shapes | `test_dashboard_math.py` (fast) |
| Cancellation attribution, including the NULL row, and `by_customer + by_owner <= cancelled` | `test_dashboard_math.py` (fast) |
| Type folding: rename (`max(created_at)`), archive, reused name, equal-count tie-break, **non-cancelled predicate (C2)** | `test_dashboard_math.py` (fast) |
| New / returning / repeat, including **Risk 12's split shape** | `test_dashboard_math.py` (fast) |
| Utilization clamping, off-grid instants, `capacity == 0`, `booked <= capacity`, `utilization == booked / capacity` | `test_dashboard_math.py` (fast, `grid_totals`) |
| Route wired, authenticated, `no-store`, no `/manage` shadow across six routers | `test_dashboard_api.py` `ROUTES` (fast) |
| `SPEC_ERROR_CODES` set equality — **two** codes, no CSRF | `test_dashboard_api.py` (fast) |
| Both roles 200; `UNKNOWN_ROLE` gets the exact generic 403 body | `test_dashboard_api.py` (fast) |
| The handler passes the **host-resolved** tenant | `test_dashboard_api.py` (fast — the only place the trust path is observable) |
| No customer identifier on the wire, over a **fully populated** response | `test_dashboard_api.py` `DASHBOARD_FORBIDDEN_KEYS` (fast) |
| The route is structurally role-gated | `test_staff_role_gating.py` live-route walkers (fast, **unedited**) |
| The two statements against real Postgres | `test_dashboard_db.py` (`db`) |
| Forward utilization on `today + 6` — denominator **and** numerator | `test_dashboard_db.py` (`db`) |
| Tenant isolation, with tenant A non-zero in the same test | `test_dashboard_db.py` (`db`) |
| No migration snuck in | `test_every_tenant_id_table_has_forced_rls` (`db`, unchanged) |
| Section states, the three rate strings, bars aria-hidden, bidi, axe | `DashboardSection.test.tsx` |
| Both roles see the item; the console lands on it; C4's five edits | `Nav.test.tsx` |
| `plainDate` does not re-zone a plain date | `jerusalem.test.ts` (under `TZ=America/New_York`) |
| Zero exclamation marks, no send claim, no empty `ar` value, 43 keys resolve | `i18n.test.ts` (`HE_F52` folded into `HE`) |

**No E2E.** Recorded rather than quietly skipped — the reason is in the Verification block above.

---

## Out of scope (unchanged from the spec)

Any revenue, deposit or payment metric · **historical slot utilization** (the `availability_snapshots` job stays the recorded upgrade path and is not built) · a client-selectable window, a date picker, or a comparison-to-previous-period arrow · per-staff metrics · demand over time (bucketing by `created_at`) · export, CSV, print, or a share link · **a poll, an auto-refresh, or a `me()` refresh** (F51's Risk 3 moves to F34) · reading `audit_log` · **any chart library, and any promotion of a bar/meter into `packages/ui`** · retrofitting the four hardcoded-Hebrew console sections to i18n · an `other` bucket for appointment types beyond the top five (Risk 14) · a `history.current_week_so_far` scalar (Risk 13 — declined **with the reason**: it would put partial-week rows inside the single scan every rate folds over).
