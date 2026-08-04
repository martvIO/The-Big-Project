# Spec: F42 — Seamstress capacity hours + load bars + balanced assignment (Epic E9, floor-management program)

**Spec review**: 38 findings from 3 lenses · **36 applied**, **2 rejected** (both recorded in §Rejected findings, at the end of this document).

**Created**: 2026-08-04 · **Status**: **Gate 1: standing approval** — `interview-2026-07-30.md` §Standing approvals (Q1: only *F17, F18, F19, F20, F29, F48* stop for the user; F42 is not among them — no payments, no refunds, no privacy-law text, no billing). **Design gate: self-approved (ruling 2026-07-31)** — `LOOP-STATE.md` `rulings_2026_07_31` names F34's shift board and **F42's capacity matrix** as this run's two novel interaction patterns and self-approves both: *"build through their Q2 novel-pattern gates without pausing."* ⚠ And the simplified model this feature actually ships **has no matrix** (D8) — the surface is a list of the shape F41 already ships five of. · **Effort**: **M** — one migration of two DDL statements, one new atelier route, one extension to a shipped settings route, one new repository aggregate, four fields on a shipped wire object, one new console component and one edited one.

**Depends on**: **F41** (`alteration_tickets`, `effort_minutes`, `assigned_staff_user_id`, `delivered_at`, `AtelierBoardResponse`, `SeamstressRef`, `AtelierSection.tsx`, `lib/stages.ts`, the `atelier.*` i18n namespace, `ATELIER_OPEN`/`ATELIER_DELETE` in the walker) · **F57** (`StaffRole.SEAMSTRESS`, `StaffUsersRepository._refreshed`) · **F51** (`staff_users` CRUD, which is the writer that makes `assignable` a live question).
**Feeds**: **F40** (published roster — the recorded upgrade path for the denominator, D2/Risk 1) · **F43** (multi-fitting scheduling) · **F44** (workshop board + throughput analytics, which reads the five stamps directly and needs nothing from here).

**Scope fence — what F42 does *not* do.**

- **It does not project capacity from a roster.** F40's published-roster projection — hourly capacity walked back from the due date — is the **recorded upgrade path and NOT this build**. The 2026-07-31 ATELIER ruling drops F40 from this feature's deps for this run, E9's own degradation clause blesses a roster-free fallback, and F40 is an E8 feature that is nowhere near being built. What ships is a flat `weekly_capacity_hours` per seamstress. D2 states exactly what F40 replaces and what survives it.
- **Overload only ever FLAGS. It never blocks, refuses, warns-with-a-confirm, or reorders anything the user did not ask to be reordered.** Pre-decided #40 stands: every reallocation is a human action. There is **no 409, no confirm dialog, no disabled option and no advisory field on any write path**. The signal is a red bar carrying a word, and a cue.
- **No split and no expedite.** The other two actions of the E9 brief's success criterion 3. F41's Out-of-scope already names what they would cost (`parent_ticket_id`, `expedited_at` + `expedited_by`, two `AuditAction` members) and neither is in LOOP-STATE's scoping of this feature.
- **No per-day, per-week or per-shift breakdown of load.** One number per seamstress: the sum of undelivered minutes she holds *right now*. Bucketing it by due-date week is F40's shape and is refused here for D2's reason.
- **No change to any F41 write predicate, to `stage_of`, to the five stamps, or to the ticket wire object.** F41's Risk 9 promised this feature is an addition. D3 and D7 are what make that literally true.

---

## Problem

F41 shipped the two numbers this feature subtracts and performs no subtraction. Its own Problem section says so: *"only a time unit can be subtracted from a date. F41 is the feature that produces those minutes and those dates. It performs no subtraction — that is F42's."*

Today the workroom board can tell a shift manager **what** is due and **who** holds it, and nothing at all about **whether that is possible**.

- **`effort_minutes` has no denominator.** `alteration_tickets.effort_minutes` is `INTEGER NOT NULL` on every row (`0020_alteration_tickets.py:85`) and `staff_users` carries `id, tenant_id, email, password_hash, display_name, role, break_started_at` and nothing else (`app/models/staff_user.py`). There is no column anywhere in the product that says how much work a person can take.
- **The assign control is alphabetical.** `AlterationTicketsRepository.assignees` orders by `display_name, id` (`db/repositories/alteration_tickets.py:428`) and `TicketCard`'s assign `Select` renders that order filtered by `assignable` (`AtelierSection.tsx:1518-1524`). A shift manager choosing a seamstress is choosing from a list sorted by the first letter of her name.
- **The band mapping has a reader and no writer.** `effort_bands()` resolves `tenants.settings["atelier"]["effort_bands"]` per band with platform defaults (`app/atelier/stages.py:107-136`) and `TenantsRepository.merge_settings` takes `profile=` and `toggles=` alone (`db/repositories/tenants.py:69-95`) — so no shipped writer can reach the key at all. F41's Risk 4 owns that gap and hands it here by name. It matters *now* and did not matter then, because the E9 brief's reason for tunability is capacity arithmetic — *"'half-day' is not 240 minutes in a boutique whose shifts are six hours"* — and this is the feature that performs it.

**And the failure this prevents is the one the epic exists for.** A dress that is not ready on Thursday for a Sunday wedding has no fallback. The board already shows «באיחור» *after* the date has passed. A load bar is the only surface in the program that can say **before** the date passes that one person is holding thirty hours of work and has ten.

**What is not dangerous here.** This feature adds no customer data to any payload. It adds a staffer's weekly hours — a scheduling fact her colleagues already know from the rota on the wall — to a board three roles already read. The part that gets argued is D3's fourth statement on a five-second poll and D5's write into a JSONB blob two other features already write to.

## Goal

A nullable `staff_users.weekly_capacity_hours`, a tenant-level default in `tenants.settings["atelier"]`, and **load computed on read** as two grouped sums over live undelivered tickets: her whole backlog (`assigned_minutes`, LOOP-STATE's ruling verbatim) and the slice of it due inside a rolling week (`due_soon_minutes`). The atelier board's envelope gains four fields on each `SeamstressRef` and two of its own. A new seamstress panel above the columns renders one row per seamstress: her name, both numbers in words, and a bar that turns red — **with a word beside it** — when the work due this week exceeds a week of her capacity. ⚠ The bar's numerator is the horizoned figure and not the backlog, because the denominator is a RATE and a ratio of a stock to a rate reads red in a healthy shop (D3, §Conflicts 13). The assign `Select` sorts by remaining capacity and its options say why. One new atelier route writes a seamstress's hours; the shipped `PUT /manage/settings` gains an `atelier` block that writes the band mapping and the tenant default.

F42 ships **one migration** (one column, one index), **one new route**, **two new `AuditAction` members**, **zero new error codes**, **zero new `/manage` segments**, **one new frontend component** and **one new `lib/` module**.

## What already exists to build on (verified against code)

- **`main`'s head is `0021_floor_dispatch.py`** (F58, merged as PR #40; `revision = "0021"`, `down_revision = "0020"`). ⚠ That number is stale the moment another feature merges — **F37 is in flight in `.worktrees/sos-paging` carrying a migration of its own.** D1 states a rule and no number, and `0020`'s own header records what happens when the rule is skipped: *"it emits `UserWarning: Revision 0019 is present more than once`, dedupes to ONE script and drops the other, which on a fresh database means one of the two tables is simply never created."*
- **`alteration_tickets` has exactly the columns F42 needs and no index for the query it will run.** `0020`'s own comment: *"Declined: an index on assigned_staff_user_id. F42's load query (SUM(effort_minutes) … GROUP BY assigned_staff_user_id) is its only reader, and F42 has a migration of its own — the feature that measures the query buys the index."* F41's Risk 9.6 names the exact index and says it *"belongs in F42's migration"*.
- **`delivered_at IS NULL` is the whole of "not yet delivered", and it is one column.** F41's Risk 9.1 spells the query out. The five stamps are the state machine (`models/alteration_ticket.py:14-33`) and `stage` is derived in Python by `stage_of` (`app/atelier/stages.py:31-52`) — there is **no status column and no SQL expression for `stage`**, which is why D3's predicate names a column and never a stage.
- **`AlterationTicketsRepository.assignees` is a UNION and its second leg is already scoped to live undelivered tickets** (`alteration_tickets.py:383-430`): every live `seamstress` **plus** every distinct assignee on a live undelivered ticket, *"whatever that person's role or deleted_at now is"*. It is *"the ONE read in the feature that deliberately returns soft-deleted rows"*. F42 changes **not one line of it** — D3's aggregate is a separate statement and D7 reads `assignable` off the row exactly as `SeamstressRef.from_row` already does (`atelier/schemas.py:179-185`).
- **`SeamstressRef` was built to be extended, in writing.** `atelier/schemas.py:165-177`: *"F42 adds `weekly_capacity_hours` and `assigned_minutes` to exactly these objects."* `AtelierBoardResponse` is an envelope for the same reason (`:9-12`, `api.ts:938-944`).
- **`AtelierBoardResponse.build` joins names by id and re-sorts nothing** (`schemas.py:213-227`), and the ordering it preserves is the repository's `due_date, created_at, id`. D7 adds a second dict lookup to the same fold and re-sorts nothing either, for the same stated reason.
- **The bands are resolved in the ROUTER, from `TenantContext.settings`, at zero statements** (`atelier/router.py:103-110`, `stages.py:110-116`). The tenancy middleware binds that mapping per request from the same `tenants` row (`tenancy/middleware.py:46`), and `tenants.by_slug` is uncached per request (*"Caching is deliberately deferred to E5"*). D2 reads the capacity default the same way and adds no statement. **It also means a saved setting is live on the very next tick**, with no cache to bust.
- **`TenantsRepository.merge_settings` is ONE atomic `settings = settings || :patch::jsonb`, never a Python read-modify-write** (`db/repositories/tenants.py:69-95`), and its docstring states the guarantee this feature depends on: *"so a concurrent writer of a sibling top-level key (E4 #17/#20 will add them) can never be clobbered. Only the provided keys enter the patch."* ⚠ It also opens **its own session** — the class is constructed with a `session_factory` and every method does `async with self._session_factory()` — so nothing can join its transaction (D5, D12).
- **`PUT /manage/settings` admits owner AND shift_manager.** The boutique router's gate is `require_role(StaffRole.OWNER, StaffRole.SHIFT_MANAGER)` (`boutique/router.py:31-35`) with exactly one per-route owner-only tightening (`POST /manage/terms`, `:215`). That is precisely F42's editing set, which is why D5 rides this route rather than building one.
- **`app/auth/staff_router.py` is OWNER-ONLY at router level** (`:61-64`) and its four `(method, path)` rows are in `test_staff_role_gating.OWNER_ONLY`. That is why D6 does **not** hang capacity off `PATCH /manage/staff/{staff_id}`: a shift manager cannot reach that router at all, and the shipped `update` runs under `_STAFF_LOCK` (`auth/staff.py:64`, `:178`) for the last-owner invariant, which capacity does not have.
- **`StaffUsersRepository._refreshed` is shipped and carries its own argument** (`db/repositories/staff_users.py:195-212`): `populate_existing=True` *"is not a spare keyword to drop"*, applied *"unconditionally rather than per call site: whether a caller happened to load the row first is exactly the reasoning that has bitten this repo three times"*. D6 reuses it and writes no second one.
- **The atelier router's per-route tightening pattern is shipped, and so is its test.** `delete` carries `Depends(require_role(OWNER, SHIFT_MANAGER))` on top of the router's three (`atelier/router.py:162-167`), and `test_staff_role_gating.py:158-189` splits `ATELIER_DELETE` out of the seamstress's `NON_ELEVATED_REACH` row with the reason stated: the walker classifies on `frozenset.intersection(*role_sets)` (`:388`), so a row naming a tightened route *"would RED A CORRECT BUILD on the one test F57's Risk 1 declares untouchable"*. D16 is the second instance of that exact pattern.
- **The anti-vacuity half of the walker is `declared = FLOOR_OPEN | ATELIER_OPEN`** (`:421`) and its comment says exactly why a tightened route must still be named in `ATELIER_OPEN`: it is invisible to all three per-role equalities, so *"narrow `declared` back to FLOOR_OPEN, delete the /delete route from the router, and this test stays GREEN."*
- **`MANAGE_API` names FIFTEEN second-path-segments including `atelier`** (`apps/manage/vite.config.ts:18-19`) and `test_spa_serving.py::test_the_manage_dev_proxy_names_every_manage_api_segment` (`:381`) derives the set from the live route table and asserts set equality. D6's route lives under the existing `atelier` segment, so **that file needs no edit** — stated as a decision because the failure mode of getting it wrong is the one F57's note calls *"the nastiest of the three"*.
- **`HE_F41` selects by PREFIX** — `key === "nav.atelier" || key.startsWith("atelier.")` (`i18n.test.ts:70-73`) — and is spread into `HE` (`:85`). So every `atelier.*` key F42 adds is **automatically** covered by the `ar` parity guard, both register guards and the empty-`ar` guard. D15 is the one place in this document where the shipped guard does F42's work for it, and it is stated so nobody declares a redundant `HE_F42` fold and double-counts the union.
- **`AtelierSection.tsx`'s focus machinery is one unconditional capture with a commit stamp** (`:165-184`, `:234+`), and F41's post-mortem records both directions of the bug it fixes: a restore that clears its intent before the awaited repaint strands focus on `<body>`, and the naive fix — keeping the intent while focus is still inside the card — **creates a focus STEAL in the other direction**. D14 does not touch that machinery and states why its own destination needs neither.
- **`Modal` returns focus to its trigger by itself** — native `<dialog>`, and the shipped comment says so in those words: *"Native `<dialog>`: free focus trap, top-layer stacking, Esc handling, and focus return to the trigger"* (`packages/ui/src/components/Modal.tsx:15-18`). F41 relies on it and writes no focus code for the intake dialog (its §Every state says so in as many words). D14 depends on the same, plus one guard for the one case `<dialog>` cannot serve.
- **`AuditAction` is plain `TEXT` with no CHECK** (`0003_auth.py:71-79`) and its atelier block has **seven** members today (`models/constants.py:444-450`), not the six F41's D11 declared. D12 adds two to seven.
- **The console's numbers, stated so nobody re-derives them.** `SectionKey` is **fourteen** members and `NAV` is **thirteen** rows (`App.tsx:22-39`, `:81-150`); `Nav.test.tsx` asserts `NAV_LABELS` has **13** entries and slices `(0, 11)` for both console roles; the atelier router docstring says it is the **TENTH** `/manage` router. **F42 changes none of these** — it adds no nav row and no section (D8).

---

## Design

### D1 — One migration: one nullable column, one CHECK, one partial index. No RLS work at all

```sql
ALTER TABLE staff_users ADD COLUMN weekly_capacity_hours INTEGER;

ALTER TABLE staff_users ADD CONSTRAINT staff_users_weekly_capacity_hours_check
    CHECK (weekly_capacity_hours >= 0 AND weekly_capacity_hours <= 168);

CREATE INDEX idx_alteration_tickets_tenant_assignee
    ON alteration_tickets (tenant_id, assigned_staff_user_id)
    WHERE deleted_at IS NULL AND delivered_at IS NULL;
```

| Statement | Why it is exactly this |
|---|---|
| `weekly_capacity_hours INTEGER` **nullable, no default** | NULL is a **real and meaningful state**: "no capacity recorded for this person" (D2). A `DEFAULT 40` would write a number nobody chose onto every existing row and make the empty state unreachable and undetectable. Nullable-with-no-default is also the one `ALTER TABLE … ADD COLUMN` form Postgres does as **metadata only** — no table rewrite, an `ACCESS EXCLUSIVE` lock held for microseconds on a single-digit-row table. |
| `CHECK (>= 0 AND <= 168)` | **0 is legal and is not a typo**: a shift manager setting 0 is saying "she is not available this week", which is a thing the product should be able to say and which D9 renders honestly. 168 is hours-in-a-week — a **typo fence** in `effort_minutes CHECK (… <= 1440)`'s spirit (`0020:85`), not a policy about labour law. A named table constraint rather than an inline column check so `pg_get_constraintdef` has a name to pin. |
| the partial index | **F41 reserved this decision for here, by name** (`0020:111-115`, F41 Risk 9.6). It is not decoration: D3's aggregate is deliberately **uncapped** (unlike the board read's `BOARD_TICKET_LIMIT`), so on a boutique that abandons the board it scans an unbounded set every five seconds. The partial predicate bounds the scan to exactly the rows the aggregate sums. |

**No `enable_tenant_rls` call, no `GRANT`, no trigger.** `staff_users` has forced RLS from `0003` and `alteration_tickets` from `0020`; adding a column to a table under a policy does not change the policy, and `GRANT`s are table-level and column-agnostic (`0003_auth.py:83-84`'s precedent, cited by `0020:122`). ⚠ Stated explicitly because `test_every_tenant_id_table_has_forced_rls` walks `pg_class` and would **not** catch a mistake here — there is no new table for it to find, so the absence of a red is not evidence.

**Declined: `weekly_capacity_minutes`.** Minutes are the unit of `effort_minutes` and using them here would make the two columns comparable with no multiplication. Declined because **the human types hours** — «12 שעות» is what a shift manager says and thinks, and storing 720 to render 12 puts a conversion between the input and the column for no gain. The multiplication lives in exactly one place (D9's `capacityMinutes`) and is unit-tested.

**Declined: a `staff_capacity` table.** A second tenant table costs a policy, a `GRANT`, an isolation suite, an `enable_tenant_rls` row and an F20 retention entry, and it buys history nobody asked for. One nullable column on the row the fact belongs to. If a boutique ever needs "her hours as of last March", the audit trail (D12) has it.

**⚠ The ORM model is the second half of this migration and is not optional.** `app/models/staff_user.py` gains `weekly_capacity_hours: Mapped[int | None]`, in the **same commit**, because **no model↔migration parity test exists anywhere in `Backend/tests/`** — the shipped `break_started_at` comment says exactly this (`staff_user.py:22-25`: *"without this every line of the break writers and the floor read is an AttributeError"*).

**The revision id is resolved at build time and NEVER from this document.**

1. **Build against `head + 1`** — read `alembic heads` on `main` at the moment the branch is cut. Building at head+1 makes the branch self-coherent so its `db` tests actually run; a `down_revision` naming a revision that does not exist is an outright alembic error.
2. **Make the migration the LAST commit on the branch**, so the renumber at rebase costs one amend to one file nothing else references.
3. **Re-read `alembic heads` IMMEDIATELY BEFORE the rebase that precedes the push** and renumber `revision`, `down_revision` and the filename.
4. **Verify `alembic heads` prints exactly ONE head.** `test_exactly_one_migration_head` is the fast, no-DB guard and `0020`'s header records that it is what caught the F36 collision — *"but only AFTER the rebase, because from an unrebased worktree there is only ever one 0019 to see. So: rebase first, then read that test."*
5. **Do not open the PR while a lower-numbered migration is still unmerged.** `main` is at `0021` today and **F37 is building with one**.

`downgrade()` drops the index, the constraint and the column. `test_migrations.py` runs this feature's migration **up and down**.

### D2 — The tenant default lives in `tenants.settings["atelier"]`, NULL means "not set", and the platform supplies NO number

```python
# app/atelier/stages.py, beside effort_bands()
MAX_WEEKLY_CAPACITY_HOURS = 168        # the DDL CHECK's ceiling, one magnitude one place

def default_capacity_hours(settings: dict[str, Any]) -> int | None:
    """The tenant's house default, or None. There is NO platform default."""
    atelier = settings.get("atelier")
    stored = atelier.get("default_weekly_capacity_hours") if isinstance(atelier, dict) else None
    if isinstance(stored, bool) or not isinstance(stored, int):
        return None
    return stored if 0 <= stored <= MAX_WEEKLY_CAPACITY_HOURS else None
```

**Resolution is two steps, the answer may be `None`, and it is REAL CODE rather than pseudocode because the obvious short form is wrong:**

```python
# app/atelier/stages.py, beside default_capacity_hours()
def resolve_capacity(
    row: StaffUser, tenant_default: int | None
) -> tuple[int | None, bool]:
    """Returns (resolved_hours, capacity_is_default).

    ⚠ `is not None`, NEVER truthiness. 0 is a DELIBERATE value — "she is not
    available this week" (D1) — and `or` would hand her the boutique's default,
    render her bar at a fraction of the truth in the non-overload colour, print
    «ברירת מחדל של הבוטיק» on a number she personally set, and sort her FIRST in
    the assign Select. The shipped `settings.get("atelier") or {}` idiom this
    spec cites approvingly elsewhere (D5 edit #3) is exactly the habit that
    produces the bug here, which is why this is code and not a sentence.
    """
    if row.weekly_capacity_hours is not None:
        return row.weekly_capacity_hours, False
    return tenant_default, tenant_default is not None
```

```
resolved = row.weekly_capacity_hours  if IS NOT NONE (0 counts, and is hers)
           else tenant default        if set
           else None                  -> NO BAR, and that is a designed state
```

**⚠ THE SAME RULE ON THE CLIENT, AND D9's TABLE IS WHAT INVITES THE BUG.** Every fold in `lib/capacity.ts` branches on `row.weekly_capacity_hours === null`, **never** on falsiness. `null` and `0` demand opposite renderings — `null` draws no bar, no colour and no word; `0` with any load draws a full red bar and «עומס יתר» — and `if (!row.weekly_capacity_hours) return null` collapses them, rendering the away-and-drowning seamstress as «לא הוגדרה קיבולת». Both directions are named acceptance lines with named mutations.

**⚠ THE PLATFORM SHIPS NO DEFAULT NUMBER, AND THIS IS THE DECISION A READER WILL CHALLENGE FIRST.** `effort_bands` has five platform defaults (`stages.py:79-85`) and capacity has none. The asymmetry is deliberate and it is two separate arguments:

1. **`effort_minutes` is `NOT NULL` in the DDL, so band resolution MUST answer a number** — `stages.py:123` says so: *"Every tenant always has exactly five bands. That is what lets the intake form render with no empty-state branch and what lets `effort_minutes NOT NULL` hold."* `weekly_capacity_hours` is nullable, so "unknown" is representable and does not have to be faked.
2. **A wrong band is bounded and a wrong capacity is not.** The five bands span 30–480 minutes; a boutique whose half-day is 300 rather than 240 is off by 25 % on one band. A capacity is a **denominator**: guessing 40 for a seamstress who works 12 renders every one of her bars at a third of the truth, in a colour that says everything is fine. E9 Risk 2 already concedes that bad estimates make the alerts lie; a fabricated denominator would make them lie *by construction*, on day one, on every tenant, with nobody having entered a number to be wrong.

**So a brand-new boutique sees: the panel, every seamstress in it, her real load in hours — and «לא הוגדרה קיבולת» with a control that fixes it in two taps.** The load is true data and always renders. The bar is the only thing withheld, and it is withheld because a bar without a denominator is a picture of a number that does not exist. §Every state pins the exact rendering.

**Why the default is a tenant setting and not a per-seamstress requirement.** A boutique's seamstresses mostly work the same week. Making the shift manager type the same 36 five times is the un-lazy thing, and it means the day the shop changes its hours she edits five rows instead of one. The default is also what makes the panel useful **immediately** after one save.

**The key path is `settings["atelier"]["default_weekly_capacity_hours"]`** — a sibling of `effort_bands` under the `atelier` key F41 established. Read off `TenantContext.settings` in the router, **zero statements**, exactly as `effort_bands` is (`atelier/router.py:103-110`). D5's writer is the only writer of the whole `atelier` block, which is what makes the shallow JSONB merge safe.

**What F40 changes when it lands, recorded now so this is an upgrade and not a rewrite.** F40's published roster gives the hours a seamstress is *actually scheduled* between now and a ticket's due date. When it arrives:

- `weekly_capacity_hours` becomes the **fallback** for a staffer with no published shifts, not the primary source. The column stays; the resolution function gains a step in front of it.
- The load bar's denominator becomes per-ticket-horizon rather than per-week, so one seamstress can be green for next month and red for Thursday. **That is a change to the DENOMINATOR only** — D3's two numerators are unchanged, and so is the column, the index, the route, the wire shape and the panel. F42's rolling-7-day `due_soon_minutes` is the crude, roster-free version of the same idea: F40 replaces one fixed horizon with each ticket's own.
- The tenant default survives as the roster's own fallback.
- **The one thing F40 must not inherit**: `capacity_is_default` (D7) becomes a three-valued question (roster / her column / tenant default) and should become an explicit source field then, not a second boolean.

*Owner: F40. Trigger: F40's spec, which is an E8 feature and is not queued.*

### D3 — THE LOAD COMPUTATION, exactly — TWO SUMS IN ONE STATEMENT, because a stock is not a rate

```sql
SELECT assigned_staff_user_id,
       SUM(effort_minutes) FILTER (WHERE due_date <= :horizon) AS due_soon_minutes,
       SUM(effort_minutes)                                      AS assigned_minutes
  FROM alteration_tickets
 WHERE tenant_id = :t
   AND deleted_at IS NULL
   AND delivered_at IS NULL
 GROUP BY assigned_staff_user_id
```

`AlterationTicketsRepository.load_by_assignee(session, tenant_id, *, horizon) -> dict[UUID | None, tuple[int, int]]`. One new method, **one statement**, run inside the board's existing `tenant_session`. `horizon = today_jerusalem + 7 days`, and **`board()` already computes `today` and passes it down** (`service.py:134`), so the clock call is free and no second date source enters the feature.

**⚠ WHY TWO SUMS, AND THIS IS THE DECISION A READER WILL CHALLENGE SECOND (§Conflicts 13).** `weekly_capacity_hours` is a **rate** — hours per week. A single unfiltered `SUM(effort_minutes)` over every undelivered ticket is a **stock** — the whole backlog, with no date predicate anywhere and, by `alteration_tickets.py:20-28`'s own words, no bound at all (*"a boutique that abandons the board accumulates `intake` rows without bound"*). Dividing the second by the first is not a utilisation of anything, and the error is chronic and one-directional: a 40 h/week seamstress holding six weeks of evenly-spread forward work renders at 600 %, clamped, red — **on day one, on every row, in any boutique with a book**. D9's own edge table concedes it in passing (*"400 % is not hypothetical — it is one seamstress and a wedding season"*) while treating it as an alarm rather than as an artifact of the units. A bar that is red in the steady state is a bar nobody reads, which is the failure this feature exists to avoid.

So: **the bar's numerator is `due_soon_minutes`** — the work due inside a rolling week, against a week of capacity, which is dimensionally a utilisation and is the question a shift manager actually asks on a Monday. **`assigned_minutes` keeps the ruling's literal meaning** — the sum of *all* undelivered effort — stays on the wire under that name, and is stated in words in the same row, so the total queue is never hidden.

**The week is a ROLLING 7 days from `today_jerusalem`, not a Sunday-anchored calendar week.** A calendar anchor would require pro-rating the denominator by day-of-week — on a Friday, two days of remaining capacity against two days of work — which is a per-horizon projection, which is F40's shape, which this run drops (D2). A rolling week needs no pro-rating: seven days of work against one week of capacity, every day.

**Overdue rows are INSIDE the horizon and that is arithmetic, not a special case.** `due_date < today ≤ horizon`, so a job ten days late is in `due_soon_minutes` in full — which is correct, because late work is the most urgent work there is.

**Which tickets count — the definition, against F41's five-timestamp model where there is no status column:**

| Clause | Why, and what a builder would get wrong |
|---|---|
| `delivered_at IS NULL` | **This is the entire definition of "not yet delivered", and it is ONE COLUMN.** F41's Risk 9.1 states it verbatim: *"one column, no derivation and no stage enum."* ⚠ It is **not** `stage != 'delivered'`: `stage` is derived in **Python** by `stage_of` as the rightmost stamped column (`stages.py:31-52`) and has no SQL expression. Re-deriving the rightmost-stamp rule in SQL to express the same predicate would be a second copy of the state machine, in a second language, that a concurrent write can desynchronise. |
| `deleted_at IS NULL` | A soft-deleted ticket is gone to every verb (`alteration_tickets.py`, every predicate). |
| `tenant_id = :t` | Redundant defence-in-depth beside RLS — the house pattern, stated at `alteration_tickets.py:32-33`. RLS is the fence; this is the belt. |
| **no** stamp predicate of any kind | A ticket at `intake` counts in full. A seamstress holding ten un-started jobs is **not** free, and a numerator that only counted started work would read her as idle on the exact morning she is drowning. ⚠ The e9 brief says *"not yet `ready_at`"* and LOOP-STATE's ruling says *"not yet delivered"*; the ruling governs and §Conflicts 14 records the consequence. |
| `FILTER (WHERE due_date <= :horizon)` on the FIRST sum only | The bar's numerator. `due_date` is `DATE NOT NULL` on every row (`0020:78`), so there is no NULL branch to reason about. The FILTER is inside the same aggregate — same statement, same scan, same index — so it costs nothing. **Mutation: delete the FILTER → a ticket due in 30 days reddens the bar → red.** |
| **no** horizon on the SECOND sum | `assigned_minutes` is the ruling's number verbatim and is deliberately the whole backlog. It is what the row states in words and what a manager reads when deciding whether to reassign at all. |
| **no** `assigned_staff_user_id IS NOT NULL` | The NULL group is kept deliberately: it is the **unassigned pile**, F41's Risk 9.2 — *"the unassigned pile is the first thing a capacity view must show"* — and dropping it here would mean a second statement to get it back. |
| **no** delivered-window predicate | `DELIVERED_WINDOW_DAYS = 7` bounds what the **board renders**, not what the load counts, because every delivered ticket is excluded from load outright. Stated because a reader who knows the board read will look for the window here and must not add it. |
| **no** `BOARD_TICKET_LIMIT` | The aggregate is **uncapped**, deliberately, and that is the whole argument against the free alternative below. |

**⚠ A ticket that was delivered and then UNDONE re-enters the load, immediately.** F41's D4 undo clears `delivered_at`, so the row rejoins the aggregate on the next tick with no other write. That is correct — the garment is back in the workroom — and it is stated because it is the one path by which a bar goes **up** with nobody assigning anything.

**Computed on read. Nothing is stored.** This is the house compute-on-read pattern with four shipped precedents — pre-decided #30's queue positions, F43's fitting ordinals, F37's read-time SOS escalation, and F41's own `overdue` (`schemas.py:120-123`: *"A stored boolean would need a worker to flip it at Jerusalem midnight, would be stale for up to a tick, and would race a concurrent delivery."*). Here the argument is stronger, not weaker: a stored `assigned_minutes` on `staff_users` would have to be maintained by **eight** writers — intake-with-an-assignee, `update` when the band changes, elevated `assign`, `claim`, `release`, advance-to-`delivered`, undo-of-`delivered`, and `soft_delete` — each of which is a place to forget it and each of which would need its own conditional predicate not to race the other seven. **The sum is one statement and it cannot be stale.**

**⚠ THE COST, DERIVED BY F34's D3 METHOD AND NOT MEASURED, AND IT IS A DEPARTURE FROM F41's STATED BUDGET.** F41's D12 fixes the board poll at **three business statements** and calls that *"the budget"*. F42 makes it **four**: tickets, `customers.by_ids`, `assignees`, and this aggregate. Per tick per device on the atelier screen: 3 sessions opened, 2 `set_config` + BEGIN/COMMIT, 3 `SELECT 1` pool pre-pings, **4 business statements** ≈ **7 statements, ≈12 round trips, 3 pool checkouts** — against F41's ≈6 / ≈11 / 3. The capacity default and the bands are **not** statements: both come off `TenantContext.settings`, which the middleware already bound. **F29 is handed this figure by name (Risk 3), as F41 handed it the previous one.**

**Declined: folding the aggregate into `assignees()` as a `LEFT JOIN`.** It would hold the budget at three statements and it is genuinely tempting — `assignees`' existing `assigned` subquery has the *identical* predicate, so `load.assigned_staff_user_id IS NOT NULL` would subsume it exactly. Refused on two counts: **(1)** a `LEFT JOIN` from `staff_users` can never carry the **NULL group**, because there is no staff row for "unassigned" — so the unassigned pile would need a second statement anyway and the saving evaporates; **(2)** it rewrites a shipped, heavily-commented query whose union semantics are the one thing standing between a re-roled seamstress and an invisible bucket (F41's D9/Risk 12), inside a PR whose subject is arithmetic. **Recorded as the optimisation to reach for if F29's k6 pass says the fourth statement matters**, at which point the NULL group moves to a `COALESCE` on a `FULL JOIN` or to the ticket fold.

**Declined: folding the load in PYTHON over the tickets the board already fetched.** It is **free** — zero statements — and it is **wrong in exactly the boutique that needs the feature**. The board read is capped at `BOARD_TICKET_LIMIT = 500` and windowed; a truncated payload would silently under-count every bar, and the boutique whose board truncates is by definition the overloaded one. A bar that understates load is worse than no bar: it is a green light computed from a partial view, and nothing on screen would say so. The aggregate is uncapped by construction, so **the bars stay exact on a truncated board** — which is also why `truncated: true` and a correct set of bars can coexist and must.

**Declined: a `HAVING` clause or any filtering of GROUPS.** Every group is wanted, including a seamstress with zero (she does not appear in the result at all, and D7 reads her as `(0, 0)` through `load.get(id, (0, 0))`). The `FILTER` above narrows one *sum*, never the group set — a seamstress whose every job is due next month is still in the result with `due_soon_minutes = 0` and a real `assigned_minutes`.

### D4 — What happens to tickets already stamped with a band when the mapping CHANGES: **nothing**

This is the question a reader asks first, so it gets its own section rather than a sentence in D5.

**A re-tune re-values nothing, retroactively or otherwise, and it cannot**, because **there is no band on the ticket to re-resolve.** `alteration_tickets` stores `effort_minutes` and has no `effort_band` column — deliberately, and the migration says so at `0020:50-53` and the model at `alteration_ticket.py:50-53`: *"MINUTES persist, never the band label. A boutique that re-tunes its bands must not silently re-value work already estimated."* That is the E9 brief's own sentence, and F41's D8 is built on it.

So saving a new mapping changes exactly three things, and no others:

1. **What a NEW ticket gets.** `create` resolves `bands[request.effort_band]` at intake (`service.py:171`).
2. **What the intake and edit dialogs OFFER.** The board payload carries the tenant's resolved bands (`AtelierBoardResponse.effort_bands`) and the dialog renders those five.
3. **What an OLD card RENDERS — and this has TWO cases, not one.** `bandLabel(minutes, bands, t)` is `bands.find((band) => band.minutes === minutes)`, **first match wins on the MINUTES VALUE with no notion of which band produced them** (`lib/stages.ts:72-81`).
   - **The minutes match no live band → the `«{{minutes}} דק׳»` fallback** (`lib/stages.ts`, whose own header says it *"is reachable the day after F42 ships and not before"*).
   - **⚠ The minutes match a DIFFERENT band → a silent RELABEL, no fallback, no visible act.** D5 makes this reachable on purpose: bands are *"NOT required to be distinct or increasing"*, so flattening «יום מלא» from 480 to 240 makes every garment ever estimated at «חצי יום» read «יום מלא» on the board.

**And that third one is the visible consequence, designed rather than discovered.** After a boutique re-tunes «חצי יום» from 240 to 300, the board shows old tickets reading «240 דק׳» beside new ones reading «חצי יום». That is not a bug and must not be "fixed": it is the product being honest that the two garments were estimated under two rulers.

**⚠ THE RELABEL IS ACCEPTED, AND SAYING SO IS THE POINT OF THIS BULLET.** The alternative is an `effort_band` column, which `alteration_ticket.py:50-53` and `0020:50-53` refuse by design and which F42 must not add. So the "two rulers" honesty above is a property of the **minutes**, which never move, and **not** of the band word, which is a live reverse lookup and can move under a re-tune. The load arithmetic is untouched either way — minutes are minutes. Pinned by an acceptance line rather than left to arrive as a bug report.

**⚠ AND THE LOAD BAR IS WHERE THE MIXTURE LANDS.** A seamstress's `assigned_minutes` after a re-tune is a sum of minutes valued under two mappings. **This is correct and is left alone** — minutes are minutes, they add, and the number is the true total of what was estimated. It is stated here because it is the kind of thing a later reader "notices" and tries to normalise.

**Declined: re-valuing live tickets on save.** It is a write across every undelivered ticket in the tenant, triggered by a settings save, with no per-ticket decision by anyone, moving every bar on the board the instant a form is submitted. It needs an audit shape nobody has designed (one row? one per ticket? what is the actor's intent?), and it would silently overwrite an estimate a seamstress made deliberately for *this* garment. It also fails the obvious test of intent: an owner correcting a typo in one band would re-value work she never looked at.

**Declined: offering it as an opt-in checkbox on the save dialog.** Same write, same problems, plus a destructive default nobody will read.

**The remedy that already exists, and it is the right one:** «עריכה» on a card re-picks a band and writes new minutes — one ticket, one human decision, one `ATELIER_TICKET_UPDATED` audit row carrying `{"changed": ["effort_minutes"]}` (`service.py:275-289`). The boutique most likely to re-tune does it in its first week, when the board holds five tickets.

### D5 — The band + capacity-default editor: `PUT /manage/settings` gains an `atelier` block, and the SHALLOW merge is the trap

F41's Risk 4 sized this as *"four edits"*. It is **seven, across four files**, and the count is corrected here rather than inherited (§Conflicts 7).

| # | File | Edit |
|---|---|---|
| 1 | `db/repositories/tenants.py` | `merge_settings` gains `atelier: dict[str, Any] \| None = None` and one `if atelier is not None: patch["atelier"] = atelier` |
| 2 | `boutique/service.py` | `SettingsResult` gains `atelier: dict[str, Any]` |
| 3 | `boutique/service.py` | `_settings_result` projects `dict(settings.get("atelier") or {})` — the shipped `settings.get(…) or {}` idiom |
| 4 | `boutique/schemas.py` | `AtelierSettingsUpdate(ForbidExtraModel)` and `UpdateSettingsRequest.atelier: AtelierSettingsUpdate \| None = None`; `SettingsResponse.atelier: dict[str, Any]` |
| 5 | `boutique/validation.py` | `validate_atelier_settings(atelier)` |
| 6 | `boutique/router.py` | both handlers pass `atelier` through, `update_settings` with the shipped `model_dump(exclude_unset=True)` idiom |
| 7 | `boutique/service.py` + `boutique/router.py` | ⚠ **`update_settings` gains `actor: StaffContext`** and the router passes the `staff: Staff` it already binds (`boutique/router.py:57-58`). The shipped signature is `update_settings(tenant_id, *, profile, toggles)` (`boutique/service.py:118-133`) and takes **no actor at all**, so D12's audit row has nobody to name unless this edit happens. `audit_log.actor_id` is nullable (`models/audit_log.py:16`) so an actor-less row would insert silently — and D12's whole justification is *"nobody can say who or when"* |

Plus `boutique/service.py::update_settings` gains `validate_atelier_settings` and D12's audit call.

**⚠ THE CLOBBER QUESTION, ANSWERED IN TWO HALVES BECAUSE THE ANSWER DIFFERS BY LEVEL.**

**Top level: safe, by the shipped mechanism, and no new code buys it.** `merge_settings` is one atomic `settings = settings || :patch::jsonb` in one `UPDATE … RETURNING settings`, *"never a Python read-modify-write"*, and its docstring names this exact guarantee. A profile save committing in the same millisecond as an atelier save cannot lose either: `profile` and `atelier` are different top-level keys and `||` merges them. **There is no read-modify-write anywhere on this path and none may be introduced** — that is the mechanism, and D14's mutation table names the mutation that must red it.

**⚠ Second level: `||` IS A SHALLOW MERGE, and this is what a builder gets wrong.** `settings || '{"atelier":{"effort_bands":{…}}}'` **replaces the entire `atelier` object**. Two writers that each send *part* of `atelier` do clobber each other — and F42 has **two** things to store under that key, which makes this concrete rather than hypothetical: a "save bands" button and a "save default hours" button would silently delete each other's work.

**The fix is not a deeper SQL expression. It is ONE WRITER THAT ALWAYS SENDS THE WHOLE `atelier` BLOCK**, and the request model makes that structural rather than a convention:

```python
from pydantic import StrictInt

class AtelierSettingsUpdate(ForbidExtraModel):
    """⚠ A FULL REPLACE OF THE WHOLE `atelier` BLOCK — every field REQUIRED, no
    default anywhere. `UpdateAppointmentTypeRequest`'s shipped rule, and here it
    is load-bearing for a second reason: `merge_settings` merges at the TOP level
    only, so a patch carrying a PARTIAL `atelier` object replaces the whole thing
    and deletes the key it did not name. One writer, one dialog, one save, both
    keys, always.

    ⚠ `StrictInt`, NOT `int`, AND THE ANTI-`bool` RULE IS VACUOUS WITHOUT IT.
    `ForbidExtraModel` sets `extra="forbid"` and NOTHING ELSE (`app/schemas.py:13-19`
    — there is no `strict=True` anywhere on it), so plain `dict[str, int]` COERCES
    before any validator runs: `{"half_day": true}` becomes `1`, `"300"` becomes
    `300`, `30.0` becomes `30`. `validate_atelier_settings` would then never see a
    bool or a string, its `isinstance(v, bool)` check would be unreachable code,
    and `{"half_day": true}` would be a 200 writing a ONE-MINUTE «חצי יום» — the
    exact trap `stages.py:93-104` exists to keep out of a hand-edited blob,
    reintroduced through the API this feature adds, silently understating every
    load bar downstream. `StrictInt` refuses `true`, `"30"` and `30.0` and accepts
    `30`, and the refusal surfaces as VALIDATION_ERROR through `main.py:936`.
    """
    effort_bands: dict[EffortBand, StrictInt]
    default_weekly_capacity_hours: StrictInt | None   # required; `null` CLEARS it
```

**⚠ THE SAME HOLE IS ON `SetCapacityRequest` AND IS CLOSED THE SAME WAY.** `weekly_capacity_hours: StrictInt | None = Field(ge=0, le=MAX_WEEKLY_CAPACITY_HOURS)` — with a plain `int`, `true` coerces to `1`, lands in range, and is accepted as a one-hour week.

**The type refusal runs FIRST and `validate_atelier_settings` owns only what pydantic cannot express**: the five-key set equality and the two ranges. Keying `effort_bands` on `EffortBand` rather than `str` also makes an unknown key pydantic's refusal rather than the validator's — the validator still owns the **missing**-key half, which pydantic cannot see.

`default_weekly_capacity_hours` is `int | None` **with no default** — `AssignTicketRequest.staff_user_id`'s shipped shape (`atelier/schemas.py:85-91`): *"`null` RELEASES, and it is a value rather than an omission … An optional field would make a malformed request that dropped the key indistinguishable from a deliberate release."*

**⚠ AND `jsonb_set` IS THE WRONG REACH, named so nobody takes it.** `jsonb_set(settings, '{atelier,effort_bands}', :v, true)` looks like the deep-merge answer and **silently returns `settings` unchanged when the `atelier` key is absent** — `create_missing` creates the **leaf**, not the intermediate object. That is precisely the brand-new-boutique case, i.e. every tenant on day one, and it fails with no error. If a third key under `atelier` ever forces a genuine deep merge, the correct expression is `settings || jsonb_build_object('atelier', coalesce(settings->'atelier','{}'::jsonb) || :patch)`.

**The ceiling, recorded**: the first feature to add a third key under `atelier` (F43, F44) must either join this block or deepen the merge as above. `test_a_partial_atelier_patch_is_refused_by_the_request_model` is where that conversation starts.

**⚠ THIRD LEVEL: TWO HUMANS. LAST WRITE WINS ON THE WHOLE `atelier` BLOCK, NO 409, NO VERSION CHECK — and neither half above is the case that actually bites.** The two paragraphs above are about *code paths*; this is about *actors*. Every save is a full replace of `settings["atelier"]` with an unconditional `UPDATE` — no version, no if-match, no re-read, no rowcount discrimination — and the shipped router gate admits **both** the owner and every shift manager (`boutique/router.py:31-35`). Two managers with the dialog open produce a **silent lost update**: the second save reverts the first's five bands *and* the tenant default, both see «ההגדרות נשמרו.», and nothing on either screen ever differs.

**That is the intended behaviour, in D6's voice**: a shift manager tuning the boutique's ruler is making a call that is hers, and a conflict dialog because a colleague opened the same form is the platform second-guessing it. **The recovery path is the audit trail** — `ATELIER_SETTINGS_UPDATED` carries the **full new value** and no diff (D12), so the reverted mapping is literally the previous row and the trail reconstructs what was lost. **That is what makes D12's no-`from` choice load-bearing rather than incidental.**

⚠ The blast radius is larger than D6's, which is why that section's "last write wins" does not transfer by analogy and is argued separately: capacity is one person's hours, the band mapping is **the ruler every future estimate in the boutique is cut with**, and D4's whole point is that a mis-set band cannot be corrected retroactively — every ticket created under a reverted mapping is stamped with the wrong minutes permanently and feeds every load bar. Pinned by a named test: two sequential whole-block saves, the second wins entirely, and **both** audit rows exist with their full values.

**⚠ A SAVE ON A BRAND-NEW BOUTIQUE FREEZES THE PLATFORM BANDS, AND THAT IS ACCEPTED.** The settings dialog prefills from the board envelope, whose `effort_bands` are the **resolved** bands — on a tenant with no `atelier` key those are `DEFAULT_EFFORT_BANDS` (`stages.py:79-85`, `:107-136`). Since every save sends the whole block, opening the dialog and pressing save with no edit writes the five platform numbers into `settings["atelier"]["effort_bands"]`, after which a future change to `DEFAULT_EFFORT_BANDS` never reaches that tenant. **Intended**: the five bands are the product's own numbers, freezing them on first save is a boutique adopting them, and the platform has no plan to move them under a live tenant. The asymmetry with the capacity dialog's explicit anti-conversion guard (empty when `capacity_is_default` is true) is deliberate and is D2's argument: a *capacity* default is a number about one person that nobody chose, while the bands are a mapping the product ships and stands behind. The alternative — a `bands_are_default` bit and a partial patch — reintroduces the shallow-merge hazard the whole section closes.

**`validate_atelier_settings`, and every rule has a reason:**

- **`effort_bands`' keys must be EXACTLY the five `EffortBand` values** — set equality. The `dict[EffortBand, …]` annotation makes an **unknown** key pydantic's 400; the validator owns the **missing** one, which pydantic cannot see. ⚠ The read side tolerates a partial mapping (`stages.py:118-121` falls back per band), and that tolerance is a **backstop against a hand-edited JSONB blob**, not a contract for the API. A writer that could post three bands would let the other two revert to platform defaults with no visible act and no way to tell from the payload.
- **`1 <= v <= MAX_BAND_MINUTES`** (1440, imported from `app/atelier/stages.py` — one magnitude, one place; the import direction is `boutique.validation → atelier.stages`, and `atelier.stages` imports only `app.models`, so there is no cycle). The `int`-ness and the anti-`bool` rule are **`StrictInt`'s**, above, not this function's.
- **Bands are NOT required to be distinct or increasing.** An owner may flatten her two longest bands onto one number, `bandLabel`'s "first match wins" already handles it (`lib/stages.ts` says so), and refusing it would be the platform having an opinion about her workshop. ⚠ D4 records the consequence — a flattened band silently **relabels** old cards — and accepts it.
- **`default_weekly_capacity_hours`: `None`, or `0..MAX_WEEKLY_CAPACITY_HOURS`.** **Imported from `app/atelier/stages.py`** — the same module and the same import edge as `MAX_BAND_MINUTES`, already argued acyclic one bullet above — so the column bound and the settings bound cannot drift. ⚠ **One home, and it is `stages.py`**: D2's code block declares it there beside `default_capacity_hours`, which is its only other reader. An `app/atelier/validation.py` copy would be a second home for the one magnitude this section argues must have exactly one, and it would buy a second import edge (`boutique.validation → atelier.validation`, which pulls in `app.booking.validation` and `app.catalog.validation`, `atelier/validation.py:13-20`) for nothing.

**Declined: a new `POST /manage/atelier/settings` route.** It would need its own gate (identical to the boutique router's), its own reader, and it would put two writers on one JSONB key — reintroducing the exact clobber the paragraph above closes. `PUT /manage/settings` already admits precisely owner and shift_manager, already owns the atomic merge, and already has a console client (`api.updateSettings`).

**Declined: putting the editor behind the owner-only staff router.** A shift manager balances the workroom and must be able to tune the ruler she balances with.

### D6 — Per-seamstress hours: one new atelier route, elevated-only, last-write-wins

```
POST /manage/atelier/seamstresses/{staff_user_id}/capacity
body:    {"weekly_capacity_hours": 24}   |   {"weekly_capacity_hours": null}
answers: SeamstressCapacityResponse   — CAPACITY FACTS ONLY, never a SeamstressRef
```

**⚠ IT DOES NOT ANSWER A `SeamstressRef`, AND THAT IS THE WHOLE REASON THIS PARAGRAPH EXISTS.** `SeamstressRef` requires `assigned_minutes` and `due_soon_minutes` (D7), and this write path has **no source for either**: D3's aggregate is a board-read method run inside the poll's `tenant_session`, and D11 rules out *"a fifth statement on a write path"*. The only value a builder can reach without the aggregate is `load.get(id, (0, 0))` = `(0, 0)` — so every successful capacity save would patch a **zero load** onto that seamstress, collapsing her bar and dropping her «עומס יתר» word for up to five seconds, on this feature's own primary surface, at the exact moment a manager is looking at it (§Every state's Success row repaints from the write's own response).

```python
class SeamstressCapacityResponse(BaseModel):
    """Capacity facts only. NO load, because this path has no aggregate and
    buying one would be a second business statement on a write to avoid a
    problem the console does not have: it is already holding both load numbers
    from the last tick, and it patches only the four keys below."""
    id: uuid.UUID
    display_name: str
    assignable: bool
    weekly_capacity_hours: int | None    # RESOLVED (D2), read back through _refreshed
    capacity_is_default: bool
```

**Declined: a single-assignee `SELECT SUM(effort_minutes) … WHERE assigned_staff_user_id = :id`** in the same `tenant_session`. It is one cheap statement on a rare elevated write and it would let the route answer a whole `SeamstressRef` — but it buys nothing the console needs (it already has the number, five seconds old at worst, and the next tick corrects it), and it puts a second business statement on a write path D11 argues has none.

```python
@router.post(
    "/atelier/seamstresses/{staff_user_id}/capacity",
    # The SECOND per-route tightening on this router, `delete`'s shape exactly.
    dependencies=[Depends(require_role(StaffRole.OWNER, StaffRole.SHIFT_MANAGER))],
)
```

**A seamstress may not set her own hours, and that is the same rule F41 already made twice.** **F41's D3**'s per-verb table lets her *record work* (advance, undo on her own or an unassigned ticket) and refuses her a *scheduling decision* (`update` on a ticket she does not hold, because *"a `due_date` on a ticket she does not hold is a decision about somebody else's queue"*). Her own weekly hours are a staffing decision about the whole workroom's arithmetic — it is the denominator every other bar is read against. **Refused in the ROUTE and not the service**, because unlike every other atelier rule this one depends on nothing but the role, which is the single criterion `delete` already meets (`atelier/router.py:26-30`). *If the pilot asks, it is one literal and one control — Risk 6.*

**The target must be a live seamstress** — `AtelierService._require_seamstress` verbatim (`service.py:502-520`), which is one `by_id` (already filtering `tenant_id` and `deleted_at IS NULL`, `staff_users.py:27-35`) plus a role equality, and answers `AtelierValidationError` → 400. Reason: capacity on a non-seamstress is a number no bar will ever render, for the identical argument **F41's D9** makes about assignment.

**⚠ SO ALL FOUR REFUSALS ARE ONE 400, AND THERE IS NO 404 ON THIS ROUTE.** The shipped helper raises `AtelierValidationError` — a `DomainValidationError`, i.e. **400 VALIDATION_ERROR** (`main.py:949-953`) — when the row is `None` **or** when the role is wrong. Because `by_id` already filters both `tenant_id` and `deleted_at IS NULL`, an **unknown id**, a **retired staffer**, **another tenant's id** and a **live receptionist** are one indistinguishable 400 with a byte-identical body. That is correct — RLS plus `by_id`'s tenant predicate make a foreign row identical to a missing one by design, which is the same posture `_require_ticket` takes — and it is stated here because the obvious reading ("missing → 404") is unreachable without abandoning "verbatim". D13's table and the acceptance line say **400 / 400 / 400 / 400**, not 400/404/404/404. The **only** path to a 404 on this route is a soft-delete landing between the check and the UPDATE, which is a race and is named as such below.

**Declined: loading the row in the capacity service and raising `DomainNotFoundError` for the `None` case.** It would make "missing" and "not a seamstress" two different statuses, which reads tidier and buys nothing: a probe learns the difference between "no such staffer" and "she exists but is not a seamstress", which is a small information leak for no product gain, and it forks a shipped helper this feature otherwise reuses whole. ⚠ **Consequence, inherited and stated**: a **re-roled or retired** assignee appears in the panel with live load and `assignable: false`, and this route **refuses to set her hours**. That is correct — the remedy for her is to reassign her tickets or restore her role, not to give a receptionist workroom hours — and D8 renders her row without the control rather than with one the server always refuses.

**Last write wins, no 409, unconditional predicate:**

```sql
UPDATE staff_users SET weekly_capacity_hours = :v
 WHERE tenant_id = :t AND id = :id AND deleted_at IS NULL
RETURNING id
```

**⚠ NO `updated_at = now()`.** The shipped house rule is in `StaffUsersRepository.update`'s own docstring in as many words: *"updated_at is never assigned — the DB trigger owns it, and `refresh` is what picks the trigger's value back up (the dresses/platform rule)"* (`staff_users.py:103-104`). `staff_users` carries `trg_staff_users_updated_at` from `0003_auth.py:48`, whose `update_updated_at()` is `BEFORE UPDATE … NEW.updated_at = now()` (`0002_tenants_app_role.py:19-25`), so an explicit SET is overwritten on the same row anyway. Neither shipped writer on this table (`start_break`, `end_break`) assigns it.

**F41's D9**'s elevated-assign argument, verbatim: *"a manager reassigning a garment is making a staffing decision with a person in front of her, and a conflict dialog because a colleague touched the same ticket four seconds ago is the platform second-guessing a call that is hers."* Zero rows means the live row vanished **between `_require_seamstress` and the UPDATE** → **404**. That is a race and the only 404 this route has; every ordinary refusal is the single 400 above.

**⚠ IT ANSWERS THROUGH `StaffUsersRepository._refreshed`, AND THAT IS NOT OPTIONAL.** The service loads the row first — it must, for `_require_seamstress` and for the audit row's `from` — so `update(StaffUser)` is ORM-enabled DML whose default `evaluate` synchronization stamps this caller's value onto the identity-mapped instance **whatever the database matched**, and the factory is `expire_on_commit=False`. Without the re-read the response renders **this caller's intent** rather than the database's answer, which is the same defect `_refreshed`'s shipped docstring says *"has bitten this repo three times"*. The method is shipped and takes no new code; **write no second one**. D14's mutation table names the mutation and the interleave that reds it.

**The `before` value is captured into a local BEFORE the write**, for `floor/service.py:108-116`'s reason and F41's undo's: the `evaluate` synchronization overwrites the very instance the audit row is about to read, so a capture-after-write records the new value as the old one. A named mutation.

**A no-op writes no audit row.** Setting the hours she already has answers 200 and writes nothing — F34's D8, F57's D8, F41's D11, and the shipped `StaffService.update`'s F15 D3 rule (`auth/staff.py:215-220`).

**Declined: `PATCH /manage/staff/{staff_id}` gaining the field.** Three reasons, any one sufficient: the staff router is **owner-only at router level** and its four rows are in `OWNER_ONLY`, so a shift manager could not reach it at all; `StaffService.update` runs under `_STAFF_LOCK` for the last-owner invariant and capacity would be serialised against every staff edit in the boutique for an invariant it does not have; and it would put a workroom fact behind account administration, where a seamstress's hours would sit beside her password reset.

**Declined: a bulk `POST …/capacity` taking a map of ids to hours.** One row per human decision, one audit row per change. A bulk write's partial failure has no honest answer.

### D7 — The envelope extension: four fields on `SeamstressRef`, two on the board

```jsonc
{
  "tickets": [ /* UNCHANGED — not one field added, removed or renamed */ ],
  "seamstresses": [
    {
      "id": "9c21…", "display_name": "נועה", "assignable": true,
      // RESOLVED (D2): her own column, else the tenant default, else null.
      // `null` is a real answer and means "no bar" — never zero, never a guess.
      "weekly_capacity_hours": 12,
      // The resolved number came from the TENANT DEFAULT, not from her row. The
      // panel says so and the editor offers "back to the boutique default".
      // False when `weekly_capacity_hours` is null — there is nothing to default.
      "capacity_is_default": false,
      // SUM(effort_minutes) over live UNDELIVERED tickets assigned to her (D3).
      // The RULING's number: her whole backlog, no date predicate. 0 when she
      // holds none — absent from the aggregate, read through .get().
      // ⚠ This is the number the row STATES IN WORDS. It is NOT the bar's.
      "assigned_minutes": 2760,
      // The same sum FILTERed to `due_date <= today + 7 days` (D3). THE BAR'S
      // NUMERATOR and the sort key's, because the denominator is a weekly RATE
      // and a ratio of a backlog to a rate is not a utilisation. Always <=
      // assigned_minutes. 0 when everything she holds is due later.
      "due_soon_minutes": 900
    }
  ],
  "effort_bands": [ /* UNCHANGED */ ],
  "truncated": false,
  // The NULL group of D3's aggregate: work nobody holds. Not a bar — nobody has
  // capacity for it — a number the panel states in words.
  "unassigned_minutes": 240,
  // Off TenantContext.settings, zero statements. On the envelope so the settings
  // dialog opens with no read of its own, and so the panel can say whose default
  // an inherited number is.
  "default_weekly_capacity_hours": 30
}
```

**Four fields and not F41's predicted two.** F41's Risk 9.4 predicted `weekly_capacity_hours` and `assigned_minutes`. `capacity_is_default` is the third because **the resolved number and her own column are different facts** and the console needs both: the panel must not present an inherited number as hers, and the editor must be able to distinguish "clear back to the default" from "set to the same number". Carrying the column separately (`weekly_capacity_hours_own`) was the alternative; a boolean is one field instead of two and the editor derives everything it needs from it plus the envelope's default. `due_soon_minutes` is the fourth, for D3's dimensional argument: the bar needs a numerator with the denominator's units, and the ruling's total needs to stay on the wire and on screen. §Conflicts 5 and 13.

**`AtelierBoardResponse.build` gains two parameters and re-sorts nothing.** `load: Mapping[UUID | None, tuple[int, int]]` (`(due_soon_minutes, assigned_minutes)`) and `default_capacity_hours: int | None`; `SeamstressRef.from_row` gains the same two, reads `load.get(row.id, (0, 0))`, and resolves capacity through D2's `resolve_capacity`. The fold stays a **total function of its arguments** with no I/O, which is what keeps `test_atelier_board.py` in the fast no-Docker suite — `schemas.py:13-17` says that is the reason the fold lives there.

**⚠ `SeamstressRef.from_row` keeps deriving `assignable` from the row** (`deleted_at is None and role == SEAMSTRESS`) and F42 does not touch it. A retired seamstress with live tickets therefore ships with `assignable: false`, a real `assigned_minutes`, and whatever capacity resolves — which is the anomalous bucket F41's Risk 9.2 hands here, now carrying a number.

**Declined: putting capacity on the ticket.** `AtelierTicket` gains nothing. A capacity fact on 500 card objects, repeated once per ticket per five seconds, to say something about ten people.

**Declined: a second endpoint for the panel.** F41's D12 rule, and it is why the envelope exists: *"F42/F43 extend this payload; nobody adds a third loop."*

### D8 — The panel: a LIST, not a matrix, and therefore keyboard-navigable by construction

**⚠ THE EPIC'S "CAPACITY MATRIX" IS F40's SHAPE AND IT IS NOT WHAT THIS FEATURE SHIPS.** Interview Q2 flagged the capacity matrix as one of two novel interaction patterns and the 2026-07-31 ruling self-approved its design gate. A matrix is two-dimensional — seamstress × day — and the second dimension is the **roster projection this run explicitly drops**. With a flat weekly number there is one value per person, which is a list. Recorded as a conflict (§Conflicts 1) rather than silently narrowed.

**And that discharges the e9 Risks' keyboard requirement structurally, which is the same move F41's D16 made for drag-and-drop.** A `role="grid"` with a roving `tabindex` is a custom keyboard model to build, document and test, and it buys nothing over a `<ul>` whose every row is text plus one ordinary `Button`. **There is no `role="grid"`, no roving tabindex and no arrow-key manager anywhere in this feature.**

**Structure**, F41's shipped column structure verbatim (`AtelierSection.tsx:1027-1053`):

```
<section aria-labelledby="atelier-h-capacity">
  <h3 id="atelier-h-capacity" tabIndex={-1}>{«תופרות · 3»}</h3>          {/* headingCount */}
  <ul tabIndex={0} aria-label={t("atelier.capacity.heading")}           {/* «תופרות», UNCOUNTED */}
      class="max-h-64 overflow-y-auto">
    <li data-seamstress-id="9c21…"> … one row … </li>
  </ul>
  <p>{«לא משויך · 4 שעות»}</p>   {/* SIBLING of the <ul>, never an <li> */}
</section>
```

- **The `<section>` and the `<ul>` are both NAMED, and they take DIFFERENT keys.** F41's D16 argument applies unchanged: an unnamed `<section>` is not exposed as a region and an unnamed `<ul>` is an anonymous list, so a user navigating by list would land on six consecutive unnamed lists with no way to tell the capacity panel from the `qc` column. ⚠ The `<h3>` takes the **counted** `atelier.capacity.headingCount` and the `<ul>` takes the **uncounted** `atelier.capacity.heading` — F41's shipped answer at `AtelierSection.tsx:1051` is exactly this split (`aria-label={t(STAGE_LABEL_KEY[stage])}` on the `<ul>`, the counted string on the `<h3>`) and the reason is that **an accessible name must not churn on every five-second tick.**
- **⚠ `{{total}}` IS `seamstresses.length` — PEOPLE, NOT ROWS — and that is why the unassigned total is a `<p>` OUTSIDE the `<ul>`.** With it inside, a screen-reader user would hear «תופרות, 4 פריטים» after a heading claiming 3, on every board with unassigned work. Moving it out is also what the spec already says about it in words: *"It is a total, not a person"*. The list's item count and the heading's number are then the same fact, and an acceptance line asserts they are equal.
- **`tabIndex={0}` on the `<ul>` unconditionally**, because it is a bounded overflow container and axe's `scrollable-region-focusable` fires on exactly that. F41 made the same call for the same reason and stated it (`:1039-1043`).
- **Bounded at EVERY width** (`max-h-64`), not only at ≥768 as the ticket columns are. Twenty rows above the board would push the stage rail and the first card off a 375 px screen; 16 rem is about four rows and a hint of the fifth, which is enough to read and short enough to scroll past.
- **Position: below the freshness row and above WHICHEVER OF the stage rail OR F41's `EmptyState` renders**, so the pause control stays the first stop inside the section (**F41's D17**'s SC 2.2.2 rule, non-negotiable) and the panel is the first *content* a shift manager meets. ⚠ **The `EmptyState` half is not a footnote**: `AtelierSection` has three branches under `boardData !== null`, and at `tickets.length === 0` it renders an `<EmptyState>` that **replaces both the rail and the columns** (`:960-971`, *"the columns AND the rail are replaced"*); only at `tickets.length > 0` does the rail exist (`:973+`). A brand-new boutique has zero tickets by definition, so **both** states D2 singles out as *"the first thing a brand-new boutique sees"* and *"the second thing a new boutique sees"* land in the branch where the rail does not exist. The panel renders there too — setting capacity before the first intake is the useful order — and §Every state pins it.
- **It renders in its own component**, `SeamstressPanel.tsx`, presentational plus its two dialogs' open state, with every write going out through a callback prop that `AtelierSection` implements with its shipped `runMutation` wrapper — `TicketCard`'s shape exactly (`onAdvance`, `onAssign`, … all callbacks into the section). Its own file rather than a third component inside a 1 639-line one, and because it is the one part of this feature F40 replaces wholesale.

**⚠ THE CALLBACK CONTRACT IS PART OF THE DESIGN, NOT AN IMPLEMENTATION DETAIL — D14's focus fallback is unbuildable without it.**

```ts
onSaveCapacity(staffUserId: string, hours: number | null): Promise<boolean>
onSaveAtelierSettings(patch: AtelierSettingsUpdate): Promise<boolean>
onDialogOpenChange(open: boolean): void
```

- Both save callbacks **resolve** — never reject. `AtelierSection` implements each with its shipped `runMutation`, returning `true` on `{ok: true}` and `false` on a handled error, so the panel can `await` the write, close its `Modal` only on `true`, and run D14's guard on the paint after. A rejecting promise would make the panel duplicate `runMutation`'s catch and would put a second `poll.fail` call site in the feature.
- **`onDialogOpenChange` exists for C7 and nothing else** — see below.

**⚠ C7's DEFERRED TERMINAL MUST COVER THE NEW DIALOGS, AND IT DOES NOT FOR FREE.** `AtelierSection` computes `const dialogOpen = form !== null || pendingDelete !== null` (`:212`) and **both** the terminal render (`:782`) and the terminal focus effect (`:338`) gate on it, for the stated reason: *"unmounting the section under an open dialog would silently discard typed work, and a 401 arriving mid-form is exactly the case: the session outlives a shift."* F42 adds two dialogs whose open state lives in `SeamstressPanel`, which `AtelierSection` cannot see — so without a signal, a 401 or 403 tick unmounts the settings dialog while it holds six edited band values. The panel therefore reports its open state up through `onDialogOpenChange`, and `AtelierSection` ORs it into `dialogOpen`. One boolean, one `useState`, and the mutation that reds it is named in Testing.

**⚠ BOTH WRITE CONTROLS ARE ROLE-GATED, AND OMITTING THIS DOES NOT MERELY SHOW A DEAD BUTTON — IT DESTROYS THE BOARD.** The atelier router admits `seamstress` to `GET /manage/atelier/tickets` (`router.py:96-98`), so a seamstress renders the board and therefore the panel. `SeamstressPanel` takes `role: string` and gates **both** the per-row «שעות» `Button` and the panel's «הגדרות» trigger on `ELEVATED.has(role)` — `AtelierSection`'s shipped set (`:57`) and exactly how `TicketCard` already gates assign and delete (`:1343`, `{elevated && (` at `:1503`, `:1607`). Without the gate: she taps, the server refuses (`POST …/capacity` carries the per-route `require_role`; `PUT /manage/settings` is owner+shift_manager at router level, `boutique/router.py:31-35`), the 403 reaches `runMutation`'s catch → `poll.fail(error)` (`:479`) → **403 is TERMINAL under `usePoll`'s {401,403} rule**, so `terminal !== null` fires and the whole atelier board is replaced by «אין הרשאה» (`:782-790`) for a seamstress who tapped a control the console offered her. D13 records the 403 as expected behaviour; this is the console consequence D13 does not see.

**No disclosure, no collapse, no `<details>`.** The panel *is* the feature; a collapsed feature is a feature nobody sees, and the bounded list already solves the only problem a collapse would. `<details>`/`<summary>` was the native-first candidate and is **declined**: it would be the first in this codebase, and it brings three unknowns (jsdom's toggle fidelity under vitest, `::marker` under RTL, `focusRing` on a `<summary>`) to save three lines on a console where every other disclosure is a `Button`. ⚠ It also has a trap worth naming: `<details open={x}>` is a **controlled** attribute in React, so an `open` derived from "is anyone overloaded" would re-assert itself on every five-second tick and reopen under the user's hand — the same class of defect as F41's post-mortem focus steal.

**No nav row, no `SectionKey` member, no `App.tsx` edit, no `Nav.test.tsx` change.** The panel is content of the atelier section. F58's rooms did the same and `i18n.test.ts:63-66` records the general rule: *"the queue is CONTENT of the floor, not a thirteenth console section."*

### D9 — The load bar: its accessible role is NONE, and the row's TEXT is the entire a11y payload

**⚠ A BARE COLOURED DIV IS A FAIL AND SO IS A `role="progressbar"` BOLTED ONTO ONE. Both are refused, and this is the decision, stated explicitly.**

**⚠ THE CONSOLE ALREADY SHIPS THIS EXACT WIDGET AND F42 REUSES ITS SHAPE VERBATIM.** `DashboardSection.tsx:20-43` has a `Bar` that already made every decision below: `aria-hidden` on the whole bar, an explicit refusal of `role="progressbar"` in almost these words, the 0–100 clamp, a `Number.isFinite` NaN guard, a `bg-border` track and a `bg-gold-strong` fill, and the comment *"inlineSize, NEVER width — a logical property, so in RTL the fill grows from the inline-start (right) edge."* Copy that shape into `SeamstressPanel`. **Do not import it across sections and do not promote it to `packages/ui`** — the dashboard spec's D10 explicitly declined promotion, it is ten lines, and a cross-section component import is worse than a copy. *Promotion is the recorded upgrade at a third caller.*

```jsx
<li data-seamstress-id={s.id}>
  <span><bdi>{s.display_name}</bdi></span>
  {/* DECORATION. It carries no role, no value and no name, and it is pruned
      from the accessibility tree — because the sentence beside it already says
      everything it shows, more precisely. */}
  <span aria-hidden="true" class="block h-2 rounded-sm bg-border">
    {/* inlineSize, NEVER width: a LOGICAL property, so in this RTL console the
        fill grows from the inline-start (right) edge. `width` fills from the
        left and is the shipped Bar's named mistake. */}
    <span class={`block h-2 rounded-sm ${over ? "bg-danger" : "bg-gold-strong"}`}
          style={{ inlineSize: `${pct}%` }} />
  </span>
  {/* THE PAYLOAD. Real text in the DOM, read by everyone. */}
  <p>{«6 שעות עד 11.8 מתוך 12»}{over && « · »}{over && <b>{«עומס יתר»}</b>}
     {« · סה״כ 46 שעות בתור»}</p>
</li>
```

**⚠ `bg-accent` DOES NOT EXIST IN THIS DESIGN SYSTEM AND WOULD RENDER NOTHING.** `theme.css`'s `@theme` block declares bg, surface, surface-raised, ink, ink-muted, gold, gold-strong, gold-text, border, border-input, success, danger, warning-text, focus — **and nothing else**; `grep -rn bg-accent frontend/` returns zero hits. Tailwind 4 emits no utility for an undeclared token, so an `accent` fill would leave this feature's headline widget **invisible in its normal state**. The pair is `bg-gold-strong` on `bg-border`, exactly as the shipped `Bar`.

**Contrast, stated rather than assumed**: `gold-strong #9E7B36` on `border #E4DACA` is **2.84:1**; `danger #A03232` on the same track is **5.07:1**. WCAG **1.4.11 does not bind** either pair, because the bar is `aria-hidden` decoration whose every value is text in the same row — the shipped `Bar`'s own *"remove every bar and the screen loses nothing"* argument. The sub-3:1 pair is therefore a **recorded decision**, not an unexamined one.

**What a screen reader announces**, arrowing into the list: «תופרות, 3 פריטים · נועה, 15 שעות עד 11.8 מתוך 12, עומס יתר, סה״כ 46 שעות בתור · דנה, 6 שעות עד 11.8 מתוך 12, סה״כ 12 שעות בתור · רותי, 4 שעות, לא הוגדרה קיבולת» — then, outside the list, «לא משויך · 4 שעות». Nothing else. No «progressbar», no «125 percent», no widget to enter or exit.

**Why not `role="progressbar"`.** It is ARIA's *"progress of a task that takes a long time"*. Nothing here is progressing toward completion; a capacity meter is a level, not a task. It would also announce a bare ratio, so the honest form needs `aria-valuetext` — and `aria-valuetext` would be **byte-identical to the visible sentence beside it**, which puts the same fact in the accessibility tree twice. Hiding the visible sentence to avoid the duplication then makes the visible and announced content diverge, which is the WCAG 2.5.3 failure `aria-label`-on-visible-text causes.

**Why not `role="meter"`.** Semantically it is the right role — ARIA 1.2's *"graphical display of a numeric value within a defined range"* — and it is **declined for support, not for meaning**: NVDA and JAWS announce it inconsistently and it would need the same `aria-valuetext` duplication to say anything useful. Recorded as the role to revisit if the repo's a11y bar ever moves to ARIA 1.2 with measured AT support.

**So: the bar is redundancy on top of text that is complete on its own, and it says so in the markup.** `aria-hidden="true"` is the assertion. This is the same shape **F41's D17** already mandates for overdue — *"Overdue is a `Badge` carrying «באיחור» plus the date, never a red border alone"* — applied to the one widget in this feature whose whole job is a colour.

**Overload is `due_soon_minutes > weekly_capacity_hours * 60`.** One comparison, in one place (`lib/capacity.ts::overloaded`), used by **three** things: the bar's colour, the row's word, and the assign cue. **The word and the colour are set by the same predicate**, which is what makes "never colour-only" a structural property rather than a rule someone has to remember.

⚠ **The panel heading's count is NOT a consumer** — `atelier.capacity.headingCount`'s `{{total}}` is `seamstresses.length`, a roster count (D8, D15), and it must be: §Every state's argument is *"the `<h3>`'s count is what tells a screen-reader user the list is long before she enters it"*, which only works if it counts rows. An overload total on the heading would need its own key, its own §Every state line and its own assertion; none is wanted and the claim is dropped rather than half-built.

**⚠ AND THE CUE MUST REACH THE SAME PREDICATE, WHICH NEEDS ONE MORE EXPORT.** D11's cue asks a *hypothetical* question — "would this assign push her over?" — which `overloaded(row)` cannot answer because it takes a row. Without a helper the builder hand-rolls both the `× 60` and the `>` inside `AtelierSection`'s assign handler, which is exactly where drift is most expensive: a `>=` on one side, or one of the two forgetting the null-capacity guard and computing `null * 60 = 0` in JS so **every** assign to an unconfigured seamstress announces «עומס יתר». That is a legal-accessibility regression that leaves the sighted surface correct and passes axe. So:

```ts
export function wouldOverload(row: SeamstressRef, extraMinutes: number): boolean {
  return overloaded({ ...row, due_soon_minutes: row.due_soon_minutes + extraMinutes });
}
```

**`capacityMinutes` is the ONLY site of `* 60` and `overloaded` the ONLY site of the comparison**, and the cue reaches both only through `wouldOverload`, which contains no arithmetic and no `60`. Pinned by one assertion — `wouldOverload(row, 0) === overloaded(row)` across the whole edge table below — which fails on any drift between the two sites, including the `null * 60` case.

**The arithmetic, and each ugly case pinned by a unit test:**

| Case | `pct` | Text |
|---|---|---|
| capacity `null` (**never** `0` — D2's `=== null`) | — **no bar rendered at all** | «{{hours}} שעות · לא הוגדרה קיבולת» |
| capacity 0, due-soon 0 | 0 | «0 שעות עד {{date}} מתוך 0» — not overloaded |
| capacity 0, due-soon > 0 | **100** | «6 שעות … מתוך 0 · עומס יתר» — the ratio is undefined, the fact is not |
| due-soon ≤ capacity | `due_soon / cap × 100` | «6 שעות עד {{date}} מתוך 12» |
| due-soon 4× capacity | **100, CLAMPED** | «46 שעות עד {{date}} מתוך 12 · עומס יתר» |

**⚠ The clamp is the line a naive `inlineSize: ${ratio*100}%` breaks the layout on**, and 400 % is not hypothetical — it is one seamstress and a wedding season. The bar cannot be four times its track; the **text** carries the true numbers and is never clamped, rounded away or abbreviated. A `Number.isFinite` guard sits with the clamp, the shipped `Bar`'s reason verbatim: `inlineSize: NaN%` is an **ignored declaration** that silently leaves the previous width in place on re-render.

**Hours are rendered from minutes with one decimal at most and never a bare float — and the load rounds UP, which is one character and a real defect closed.** `hoursFromMinutes(minutes) = Math.ceil(minutes / 6) / 10`. **`Math.round` would let the sentence contradict the word**: `overloaded` compares raw minutes, so at a 12 h capacity a load of 721 minutes renders «12 שעות … מתוך 12 · עומס יתר» — displayed numbers saying *equal* beside a word saying *over*, in the one string that is this feature's entire accessibility payload. With `ceil`: 721 → «12.1 … מתוך 12 · עומס יתר», 719 → «12 … מתוך 12» with no word (equal display, not-over word: consistent). **The word is computed from raw minutes and NEVER from the rendered figure; the rendered load rounds up so the sentence can never read equal beside «עומס יתר».** ⚠ It is easy to miss because with the five platform bands (all multiples of 30) every sum is a whole half-hour and it never fires — but D5 makes bands tunable to any int in 1..1440 and explicitly *"NOT required to be distinct or increasing"*, so a 37-minute band produces loads at arbitrary offsets. One helper, three tests (capacity−1, capacity, capacity+1 minutes).

**Every numeric run is `<bdi dir="ltr">` and every name is a bare `<bdi>`** — `isolateLtr` / `isolateBidi` (`lib/booking.tsx:75-113`), whose own comment says forcing LTR on «נועה לוי» reverses its words.

### D10 — The assignment surface sorts by remaining capacity, and the options say why

`lib/capacity.ts::sortByRemainingCapacity(rows: SeamstressRef[]): SeamstressRef[]` — a pure function of the wire, returning a new array.

```
remaining = weekly_capacity_hours * 60 - due_soon_minutes      (capacity resolved)

1. capacity resolved AND remaining > 0   — by `remaining` DESC        (real headroom)
2. NO capacity resolved                  — by `due_soon_minutes` ASC  (unknown)
3. capacity resolved AND remaining <= 0  — by `remaining` DESC        (least over first)
   tiebreak throughout: display_name ASC, then id ASC
```

**THREE groups, not two, and the middle one is the correction.** Two groups put every capacity-set row ahead of every capacity-less one — including a row at 400 %. On the state D2 says every boutique starts in (some configured, most not) the first option in the control, the one a hurried shift manager takes, would be the person the panel three inches above is drawing in **red**, ranked above a colleague with no capacity set and nothing in her hands. **"Unknown" and "certainly worse than everyone" are not the same rank**, and the feature's own title is *balanced* assignment.

**The rule in one line: known headroom beats unknown; unknown beats known overload.** Nothing is hidden and nothing is disabled, so #40 still holds exactly — the overloaded seamstress is **last**, labelled «עומס יתר», and one tap away.

**Sorted on the CLIENT, not in the SQL**, and the server's `ORDER BY display_name, id` is untouched. Three reasons: `remaining` is a pure function of two fields already on the wire, so a server sort would be a second ordering to keep in step with the fold; changing `assignees()`' `ORDER BY` would reorder the payload for every consumer including F44; and F41's own lesson is that an ordering with no unique tiebreak is plan-dependent — the tiebreak here is the server's own order, which already has one.

**Rows with no capacity sort BELOW real headroom**, because "unknown headroom" is not a rank and a person the boutique has not configured must not be recommended over one it has *with room*. Within that group, least-loaded-first is the same intent with the only number available. ⚠ **A capacity of `0` with any load is group 3** — `remaining` is negative — **not group 1**: D2's `is not None` resolution is what puts her there, and truthiness would put her first (see D2's trap).

**Applied at exactly two sites**, both from one call: the elevated assign `Select`'s options (which already filters `assignable`, `AtelierSection.tsx:1518-1524`) and the panel's rows. **Not** applied to `seamstresses` in the raw payload — the array the console holds stays the server's, and the sort is a render-time fold, so nothing downstream inherits an order it did not ask for.

**⚠ THE OPTION LABEL CARRIES THE NUMBER, OR THE SORT IS AN INVISIBLE RULE.** A reordered list with no explanation is a list that shuffles for no reason a user can see:

| Row | Option text | Keys |
|---|---|---|
| capacity set, headroom | «נועה · נותרו 6 שעות» | `optionRow` ∘ `optionRemaining` |
| capacity set, overloaded | «נועה · עומס יתר» | `optionRow` ∘ `over` |
| no capacity | «נועה · 6 שעות משויכות» | `optionRow` ∘ `optionAssigned` |

⚠ **EVERY PART IS A KEY, INCLUDING THE SEPARATOR.** F41 renders `{row.display_name}` alone in this `<option>` (`AtelierSection.tsx:1518-1524`) and declares no key of this shape, so all three strings would otherwise ship as **bare Hebrew literals in TSX** — outside the `ar` parity guard, outside `HE_F41`'s prefix fold, untranslated, with `he.ts:1210-1213`'s standing rule and acceptance line for `atelier.capacity.*` both blind to them. D15 declares `optionRow` = «{{name}} · {{detail}}», so even the « · » is composed from a key and the string contains no literal.

⚠ **The option text is a plain string and cannot contain `<bdi>`** — `isolateLtr` returns JSX and `<option>` takes none. Hebrew digits inside an RTL run resolve correctly by the bidi algorithm on their own, so the numeral goes **before** its Hebrew unit word («6 שעות») and never adjacent to Latin text or a bare parenthesis. Stated because reaching for `isolateLtr` here type-errors and reaching for `dir="ltr"` on the `<option>` reverses the name.

**Declined: sorting by raw `assigned_minutes`.** It ignores capacity, which is the whole feature: a 40-hour seamstress holding 20 is more available than a 10-hour one holding 15.

**Declined: hiding or disabling overloaded options.** That is a block, and #40 says overload never blocks. She is sorted last, labelled «עומס יתר», and remains one tap away.

**⚠ Accepted risk, with the mitigation that already ships**: the option ORDER now changes as work moves, which F41's alphabetical order never did — a control whose contents reorder under a poll. Three things bound it: the deterministic tiebreak means equal rows never shuffle; F41's shipped `holdRef` returns `"held"` while a pointer is down, so a travelling finger never sees a reorder; and `mutationsRef` suppresses ticks while a write is in flight. The remaining window is a keyboard user with the listbox open and no mutation running, and the reorder needs a *colleague's* write to land inside it. Risk 5.

### D11 — Overload FLAGS. The flag is a bar, a word, and one clause on a cue — and there is no server-side flag at all

Pre-decided #40, LOOP-STATE's F42 note and F41's Risk 9.5 all say the same thing. Concretely, in this build:

- **No write path gains a status, a refusal, a confirm step or a disabled control.** `assign`, `claim`, `release`, `create`-with-an-assignee: byte-identical behaviour to F41.
- **No advisory field on any mutation response.** F41's Risk 9.5 predicted *"F42 adds an advisory overload flag to its response"*; **it does not**, and the reason is better than the prediction: the console already holds `assigned_minutes`, the capacity and — from the assign response, which is the **full ticket** (`schemas.py:106-115`) — the ticket's own `effort_minutes`. It can compute the post-assign overload itself, at the instant of the tap, with **zero server work and no fifth statement on a write path**. §Conflicts 5.
- **⚠ AND THE CUE IS WHY THIS IS NOT A NICETY.** **F41's D17** forbids the poll from writing into the announced region, and it is non-negotiable. So a sighted user sees the bar turn red on the next tick and **a screen-reader user gets nothing at all** unless the cue says it — which would make overload a sighted-only signal on the one action that causes it. The assign cue therefore gains a conditional clause:

  `atelier.cue.assignedOverload` = «שויך ל{{seamstress}} — עומס יתר.» beside the shipped `atelier.cue.assigned` = «שויך ל{{seamstress}}.»

  Chosen at the moment of the write by **`wouldOverload(target, ticket.effort_minutes)`** (D9) — **no arithmetic and no `60` at this call site**, because a cue predicate that drifts from the bar's is an a11y regression that leaves the sighted surface correct and passes axe.

- **⚠ AND IT IS GATED ON AN ACTUAL MOVE, OR IT ANNOUNCES A FALSE OVERLOAD WITH NO RACE AT ALL.** The clause is computed **only when `ticket.assigned_staff_user_id !== targetId`**. `due_soon_minutes` is her **pre-write** load and already includes any ticket she currently holds; the shipped commit fires whenever a draft exists (`disabled={assignDraft === undefined}`, `AtelierSection.tsx:1529`) and the `Select`'s value defaults to `ticket.assigned_staff_user_id`, so **arrowing away and back and committing sends a no-op assign to the current holder**. The server answers 200 and writes no audit row (`service.py:432`) — and without the gate the console adds minutes it has already counted and announces «שויך ל… — עומס יתר» on the one channel this bullet argues is legally necessary. The next bullet concedes the estimate *"can be wrong by one ticket if a colleague assigned something in the same second"*; **this path is wrong by one ticket with no colleague and no race**, which is a different class of defect and is closed rather than conceded.

**⚠ This is the console computing a domain fact, which F41's rule normally forbids, and the boundary is stated.** It is legitimate here because it is **not a control**: nothing is refused, nothing is stored, and the next tick replaces the estimate with the server's own numbers. It can be wrong by one ticket if a colleague assigned something in the same second, and the correction arrives within five seconds in the same panel. A control computed this way would be a defect; a cue is a message about data the console is already rendering.

**Declined: a toast.** The console has a `ToastProvider` and this feature uses it for nothing. A toast is transient and this board is read by two people over one bench; the bar is the durable signal and the cue is the announced one.

### D12 — Two `AuditAction` members, no migration, and one of them is written in its own transaction

| Member | Value | Written when | `details` |
|---|---|---|---|
| `ATELIER_CAPACITY_SET` | `atelier_capacity_set` | D6's route actually changed the value | `{"from": 24 \| null, "to": 30 \| null}` — `entity = str(staff_user_id)` |
| `ATELIER_SETTINGS_UPDATED` | `atelier_settings_updated` | `PUT /manage/settings` carried an `atelier` block and the merge succeeded | `{"effort_bands": {…}, "default_weekly_capacity_hours": 30}` — `entity = str(tenant_id)` |

**Both rows carry `actor_id = actor.id`**, and for the settings row that is **not free**: `BoutiqueSettingsService.update_settings(tenant_id, *, profile, toggles)` takes **no actor at all** (`boutique/service.py:118-133`) while the router already binds an unused `staff: Staff` (`boutique/router.py:57-58`) — D5's seventh edit threads it. ⚠ `audit_log.actor_id` is **nullable** (`models/audit_log.py:16`), so an actor-less row would insert silently and green, while this row's entire justification is *"the denominator of every capacity number in the boutique changed and **nobody can say who or when**"*. Every shipped atelier write already passes one (`service.py:183`, `:207`, `:281`, …). Asserted, not assumed.

**No migration** — `audit_log.action` is plain `TEXT` with no CHECK (`0003_auth.py:71-79`); the eighth block to rely on it.

**`ATELIER_CAPACITY_SET` carries `from` and `to`**, captured before the write, and the no-op rule holds: setting the hours she already has writes nothing.

**`ATELIER_SETTINGS_UPDATED` carries the NEW VALUE and no `from`, deliberately.** Two reasons and the second is structural: the trail *is* the history, so the previous mapping is the previous row's `to`; and computing a diff needs a read of the current settings **before** the write, which is precisely the read-modify-write `merge_settings`' single atomic statement exists to avoid (`tenants.py:76-80`). The values are boutique configuration and carry no personal data, so F41's D11 names-only rule does not bind here — and the whole value of this row is answering *"what was «חצי יום» worth when this ticket was estimated"*, which needs the numbers.

**⚠ IT IS WRITTEN IN A SEPARATE TRANSACTION, AFTER THE MERGE SUCCEEDS, AND THAT IS A KNOWN AND BOUNDED COMPROMISE.** F15's rule is that an audit row is written in the same `tenant_session` as the write it describes, before commit. That is **structurally impossible** here: `TenantsRepository` is constructed with a `session_factory` and opens its own session inside every method (`tenants.py:20`, `:86`), so nothing can join `merge_settings`' transaction. The options were (a) no audit row, or (b) a row written after the merge returns non-`None`, in its own `tenant_session`. **(b), because the failure mode is one-directional**: a crash between the two loses a row and can never invent one, and *"the denominator of every capacity number in the boutique changed and nobody can say who or when"* is the worse state. **Ordering is the assertion** — a merge that answers `None` (missing or soft-deleted tenant) writes nothing, and that is a named test.

*Upgrade path: give `merge_settings` an optional `session` parameter the day a second caller needs atomicity. Not bought here — it is a shipped class with other callers and this PR's subject is arithmetic.*

**The shipped settings path stays unaudited for `profile` and `toggles`.** F42 audits the key it owns and does not widen a pre-existing gap it did not create. Risk 7.

### D13 — Zero new error codes, and the set-equality is what proves it

| Condition | Status | Code | Source |
|---|---|---|---|
| No session / expired | 401 | `NOT_AUTHENTICATED` | shipped |
| A role outside the router's three | 403 | `NOT_AUTHORIZED` | shipped, generic body |
| **A seamstress on the capacity route** | 403 | `NOT_AUTHORIZED` | the per-route gate — the **same** generic body, so a probe learns nothing |
| **Unknown / retired / another tenant's / a non-seamstress `staff_user_id`** — ONE indistinguishable refusal | **400** | `VALIDATION_ERROR` | `_require_seamstress` (`AtelierValidationError`). `by_id` already filters `tenant_id` **and** `deleted_at IS NULL`, so all four cases raise the **same** exception with a byte-identical body. There is **no 404 for a missing target on this route** — D6 |
| The live row is soft-deleted **between** the check and the UPDATE (a race) | 404 | `NOT_FOUND` | the guarded UPDATE returning zero rows → `DomainNotFoundError` |
| `weekly_capacity_hours` not a strict int (`true`, `"24"`, `24.0`) or outside `0..168` | 400 | `VALIDATION_ERROR` | `StrictInt` + `Field(ge=0, le=MAX_WEEKLY_CAPACITY_HOURS)` → `RequestValidationError` handler (`main.py:936`). ⚠ **`StrictInt` is what makes the `true` row real** — a plain `int` coerces `true` to `1`, which is in range and would be accepted as a one-hour week (D5) |
| `atelier` block with an unknown band key, a non-strict-int value, or a non-strict-int default | 400 | `VALIDATION_ERROR` | pydantic (`dict[EffortBand, StrictInt]`) → `main.py:936` |
| `atelier` block **missing** a band key, or a value/default out of range | 400 | `VALIDATION_ERROR` | `validate_atelier_settings` → `DomainValidationError` → `main.py:949-953` |
| Setting the hours she already has | **200** | — | not an error |
| Mutating request from a foreign origin | 403 | `CSRF_ORIGIN_MISMATCH` | `csrf.py:48` |

**`test_atelier_api.SPEC_ERROR_CODES` is asserted SET-EQUAL to the observed set (`:112-120`, `:788`) and F42 adds NOTHING to it.** That assertion is the proof, not this table. There is no overload error, no capacity conflict and no 409 anywhere in this feature — which is what "flags, never blocks" means at the wire.

### D14 — Focus: one destination, one guard, and BOTH directions pinned

**⚠ THIS REPO HAS SHIPPED A FOCUS-DROPS-TO-`<body>` DEFECT FIVE TIMES (F56, F34, F57, F57's own vacuous test, F41) AND AXE WALKED PAST EVERY ONE, because axe cannot see a focus move that never happened.** F41's post-mortem adds the second half: **the naive fix creates a focus STEAL in the other direction**, and an adversarial verifier caught it after the first fix shipped green.

**What F42 does NOT touch.** `AtelierSection`'s `restoreRef` / `captureFocus` / `boardCommit` machinery (`:165-184`, `:234+`, `:343+`) is keyed on `[data-ticket-id]` and stamped with the board-commit count. F42 adds **no** seamstress key to it, does not generalise its selector, and does not add a destination. Any edit to that block is a review stop.

**Because both of F42's writes are `Modal`s, and native `<dialog>` restores focus to its trigger by itself** (`packages/ui/src/components/Modal.tsx:15-18`, the thing F41's intake dialog relies on and writes no focus code for). **Both dialogs mount at PANEL level** — inside `SeamstressPanel`, siblings of the `<ul>`, never inside an `<li>`. F41's C6 rule (`AtelierSection.tsx:1097-1100`) forbids **the `<li>`** and nothing further: a repaint that removed the row would unmount a dialog mounted inside it and discard what she typed. Panel level satisfies C6 and is what §Frontend changes and §Every state both say; **any "section level" reading is wrong and is corrected here.**

**The ONE case `<dialog>` cannot serve, and its guard.** The capacity dialog's trigger is a `Button` inside a seamstress `<li>`. A seamstress leaves the union when she is retired **and** her last undelivered ticket is delivered (`alteration_tickets.py:400-403`). If that lands between opening the dialog and saving it, the trigger has unmounted and `<dialog>`'s auto-restore lands on `<body>`.

**⚠ THE OWNER AND THE TURN ARE BOTH SPECIFIED, BECAUSE "on the paint that follows" IS NOT A MECHANISM AND THIS IS THE BUG CLASS THAT HAS SHIPPED FIVE TIMES.** The line lives in **`SeamstressPanel`**, which owns both the trigger and the heading ref; `AtelierSection` owns `runMutation` and **touches no focus code for this feature at all**. F41's post-mortem measured the local/CI difference at exactly one event-loop turn, which is why the shipped fix needed a commit stamp — so the turn is named rather than implied:

```
SeamstressPanel's save handler:
  const ok = await onSaveCapacity(id, hours);   // D8's contract: resolves, never rejects
  if (!ok) return;                              // the dialog stays open, the alert renders
  closeDialog();
  setSaveCount((n) => n + 1);                   // monotonic

useEffect(() => {
  if (saveCount === 0) return;
  if (document.activeElement === document.body) headingRef.current?.focus();
}, [saveCount]);                                // runs AFTER React has committed the repaint
```

- **The destination is the panel's own `<h3 tabIndex={-1}>`** — F51's shipped stranded-focus pattern, the same one F41 uses for a deleted card's column heading. No ref map, no lookup, one node that is always mounted whenever the panel is.
- **The effect is keyed on the counter and NOT on the payload**, for the reason `AtelierSection.tsx:343+` already records about `boardCommit`: a state setter bails out of a reference-identical value, so keying on the data would silently skip the one repaint the guard is waiting for.
- **The guard is `activeElement === document.body` and nothing else.** That is the browser saying the repaint dropped focus, rather than the console guessing from the data. It is F41's shipped guard, and it is what makes the move free: if focus is on something real, this does nothing.
- **⚠ AND THAT IS EXACTLY WHY IT CANNOT STEAL.** F41's shipped fix stamps intents with a board-commit count because its restore fires on **poll repaints**, which arrive with no user action and can outlive the user's own focus move. This one fires **only on a successful save**, in the same turn, and only when focus is already nowhere. There is no window in which a stale intent survives to yank focus back — so no commit stamp is needed, and adding one would be machinery for a race this shape does not have. Stated because copying F41's mechanism wholesale is the obvious wrong move.

**Both directions are named, non-vacuous tests, and each states the mutation that reds it** (Testing). A test that only asserts "the save succeeded" passes with every focus line deleted; a test that only asserts the restore passes against a build that steals.

### D15 — i18n: `atelier.capacity.*` and `atelier.settings.*`, and the shipped fold already covers them

New keys in `apps/manage/src/i18n/he.ts` **and** `ar.ts`, Hebrew standing in untranslated in `ar.ts` (Interview Q3, pre-decided #47, the 2026-07-31 languages ruling).

| Key | Hebrew |
|---|---|
| `atelier.capacity.heading` | «תופרות» |
| `atelier.capacity.headingCount` | «תופרות · {{total}}» |
| `atelier.capacity.load` | «{{hours}} שעות עד {{date}} מתוך {{capacity}}» |
| `atelier.capacity.backlog` | «סה״כ {{hours}} שעות בתור» |
| `atelier.capacity.loadNoCapacity` | «{{hours}} שעות» |
| `atelier.capacity.notSet` | «לא הוגדרה קיבולת» |
| `atelier.capacity.fromDefault` | «ברירת מחדל של הבוטיק» |
| `atelier.capacity.over` | «עומס יתר» |
| `atelier.capacity.unassignedRow` | «לא משויך · {{hours}} שעות» |
| `atelier.capacity.optionRow` | «{{name}} · {{detail}}» — the separator is a key too (D10) |
| `atelier.capacity.optionRemaining` | «נותרו {{hours}} שעות» |
| `atelier.capacity.optionAssigned` | «{{hours}} שעות משויכות» |
| `atelier.capacity.empty` | «אין תופרות רשומות.» |
| `atelier.capacity.emptyOwner` | «אין תופרות רשומות. אפשר להוסיף במסך הצוות.» |
| `atelier.capacity.edit` / `atelier.capacity.editAria` | «שעות» / «שעות — {{name}}» |
| `atelier.capacity.dialogTitle` | «שעות שבועיות» |
| `atelier.capacity.hoursLabel` | «שעות בשבוע» |
| `atelier.capacity.useDefault` | «חזרה לברירת המחדל של הבוטיק» |
| `atelier.capacity.error.hours` | «צריך מספר שעות שלם ולא שלילי.» — ⚠ **no numeral** |
| `atelier.capacity.error.server` | «לא ניתן לשמור את השעות. אפשר לנסות שוב.» — the Hebrew default branch |
| `atelier.capacity.cue.saved` | «{{name}} — עודכנו השעות.» |
| `atelier.capacity.cue.cleared` | «{{name}} — חזרה לברירת המחדל.» |
| `atelier.cue.assignedOverload` | «שויך ל{{seamstress}} — עומס יתר.» |
| `atelier.settings.open` / `openAria` | «הגדרות» / «הגדרות — לוח התפירה» |
| `atelier.settings.title` | «הגדרות התפירה» |
| `atelier.settings.bandsLabel` | «הערכות זמן» |
| `atelier.settings.bandMinutes` | «{{band}} — דקות» |
| `atelier.settings.defaultCapacity` | «ברירת מחדל: שעות בשבוע» |
| `atelier.settings.defaultCapacityHelp` | «חלה על תופרת שלא הוגדרו לה שעות משלה.» |
| `atelier.settings.submit` | «שמירה» |
| `atelier.settings.error.minutes` | «צריך מספר דקות שלם וחיובי.» — ⚠ **no numeral** |
| `atelier.settings.error.default` | «צריך מספר שעות שלם ולא שלילי, או ריק.» — ⚠ **no numeral** |
| `atelier.settings.error.server` | «לא ניתן לשמור את ההגדרות. אפשר לנסות שוב.» — the Hebrew default branch |
| `atelier.settings.cue.saved` | «ההגדרות נשמרו.» |

**⚠ NOT ONE OF THESE STRINGS CONTAINS A SERVER BOUND, AND THAT IS THE SAME RULE §Frontend changes STATES WITH A ⚠.** «168» and «1440» are `MAX_WEEKLY_CAPACITY_HOURS` and `MAX_BAND_MINUTES` — **server** bounds — and a Hebrew sentence quoting one is a mirror exactly as much as a TypeScript constant is, with none of the protection: `test_frontend_constant_parity.py` scrapes only the two `validation.ts` files (`:44-46`), so raising the DB CHECK to 200 would leave three Hebrew sentences lying, silently and greenly. **The precedent is not ambiguous**: F41 declared `form.error.dueDateHorizon` and **cut it at review** for this exact rule, with the reason recorded at `i18n.test.ts:705-719` (*"730 is a SERVER bound and no client constant may mirror one"*) — the very comment §Conflicts 4 already cites. The copy states the **shape** requirement; the server's 400 states the range. Same for the `Input`: `min={0}` and `inputMode="numeric"` stay (shape), **`max={168}` is cut** (a bound).

**⚠ THE FOLD IS ALREADY DONE AND MUST NOT BE DONE TWICE.** `HE_F41` selects by **prefix** — `key === "nav.atelier" || key.startsWith("atelier.")` (`i18n.test.ts:70-73`) — and is spread into `HE` (`:85`). So every key above is already inside the `ar` parity guard, both register guards and the empty-`ar` guard. **Do NOT declare a second `HE_F42 = entries(he.translation, key.startsWith("atelier."))` and spread it**: it would double-count the union and make every `HE`-iterating guard run twice over F41's 94 keys, which is silent and green and wastes the next reader's afternoon. F42's own block derives instead:

```ts
const HE_F42 = HE_F41.filter(
  ([key]) => key.startsWith("atelier.capacity.") || key.startsWith("atelier.settings."),
);   // NOT spread into HE — HE_F41 already carries these rows
```

`i18n.test.ts:721`'s `expect(HE_F41.length).toBeGreaterThanOrEqual(94)` is a floor and stays true. ⚠ `he.ts:1196`'s section header reads *"F41, the atelier. 95 keys, 0 reused"* — that comment goes stale and is corrected in passing.

**Guards this deck must clear:** the `/נשלח|תישלח|בדרך/` send-claim guard (trivially — **nothing in F42 notifies anybody**, and «נודיע לתופרת» on an overload cue is exactly the sentence a well-meaning editor would add, and it would be a lie); the no-exclamation guard; the `ar` parity guard; and the no-empty-`ar` guard. **The label-in-name containment (WCAG 2.5.3) applies to the two new aria pairs** — `atelier.capacity.editAria` starts with «שעות» and `atelier.settings.openAria` with «הגדרות» — asserted, not trusted.

⚠ `he.ts:1210-1213`'s standing rule applies: **any quoted `"atelier.…"` literal anywhere in `apps/manage/src` is scraped as an i18n key and must resolve.** Do not name a `data-testid` or a `data-control` `atelier.capacity.save`.

**No new formatter.** Hours are a number and a word; no date, no time, no zone. `scripts/qa-greps.sh`'s unzoned-formatter grep gains nothing to find.

### D16 — The route table: one new row in `ATELIER_OPEN`, split out of the seamstress's reach exactly as `delete` is

```python
# test_staff_role_gating.py
ATELIER_DELETE = ("POST", "/manage/atelier/tickets/{ticket_id}/delete")
# ⚠ THE SECOND TIGHTENED ROUTE, and it is split out for ATELIER_DELETE's reason
# verbatim: the walker classifies on frozenset.intersection(*role_sets) (:388),
# and this route carries require_role(OWNER, SHIFT_MANAGER) on top of the
# router's three — so its effective set is {owner, shift_manager} and seamstress
# is NOT in it. A seamstress row naming it would be one element larger than
# reality and would RED A CORRECT BUILD on the test F57's Risk 1 declares
# untouchable, which is the exact situation that gets a test relaxed.
ATELIER_CAPACITY = ("POST", "/manage/atelier/seamstresses/{staff_user_id}/capacity")
ATELIER_ELEVATED = {ATELIER_DELETE, ATELIER_CAPACITY}
ATELIER_OPEN = { …the seven…, ATELIER_CAPACITY }

NON_ELEVATED_REACH = {
    RECEPTION:       frozenset(FLOOR_OPEN),
    SALES_ASSISTANT: frozenset(FLOOR_OPEN),
    SEAMSTRESS:      frozenset(FLOOR_OPEN | (ATELIER_OPEN - ATELIER_ELEVATED)),
}
```

- **The new row MUST be in `ATELIER_OPEN`** even though it is in nobody's reach, and the shipped comment at `:416-420` says exactly why: a tightened route is invisible to all three per-role equalities, so the anti-vacuity half (`declared = FLOOR_OPEN | ATELIER_OPEN`, `:421`) is the **only** thing that notices if the route is deleted. Leaving it out would let someone remove the route with the suite green.
- **`test_route_table_matches_the_permission_matrix` needs no edit**: `OWNER_ONLY` does not gain a row, because both gates on this route admit `shift_manager`, so the `all(...)` branch passes.
- **`test_gate_admits_listed_roles` needs no new case**: `require_role(OWNER, SHIFT_MANAGER)` is already asserted by F41's `delete`.
- **`test_gates_admit_only_known_roles` needs zero edits** — it derives `known` from the live enum and F42 adds no role.
- **`test_atelier_api.ATELIER_ROUTES` gains one concrete row**, which feeds the 401 walk, the wiring walk, the `cache-control: no-store` parametrization and (via `test_staff_role_gating`'s import at `:18`) two end-to-end HTTP walks.
- **`apps/manage/vite.config.ts` needs NO edit.** `MANAGE_API` matches the **second** path segment, and `atelier` is already the fifteenth of fifteen. `test_spa_serving.py::test_the_manage_dev_proxy_names_every_manage_api_segment` derives the segment set from the live route table and asserts set equality, so it stays green — **and it would go red instantly if this route had been put on a new second segment**. Stated as a decision because F57's note calls that omission *"the nastiest failure mode of the three: production, CI and the suite all stay green while only a developer's machine breaks."*

---

## API surface

| Method | Path | Body | Answers | Admits |
|---|---|---|---|---|
| `GET` | `/manage/atelier/tickets` | — | `AtelierBoardResponse` **+ 2 fields, `seamstresses[]` + 4** | owner, shift_manager, seamstress (unchanged) |
| `POST` | `/manage/atelier/seamstresses/{staff_user_id}/capacity` | `SetCapacityRequest` | **`SeamstressCapacityResponse`** — capacity facts only, **no load** (D6) | **owner, shift_manager only** — per-route tightening (D6/D16) |
| `PUT` | `/manage/settings` | `UpdateSettingsRequest` **+ `atelier`** | `SettingsResponse` **+ `atelier`** | owner, shift_manager (unchanged, shipped router gate) |
| `GET` | `/manage/settings` | — | `SettingsResponse` **+ `atelier`** | owner, shift_manager (unchanged) |

Every other atelier route is byte-identical to F41.

```jsonc
// POST /manage/atelier/seamstresses/{staff_user_id}/capacity  — a ForbidExtraModel
{ "weekly_capacity_hours": 24 }     // 0..168, or null to CLEAR back to the tenant default.
                                    // REQUIRED with no schema default: null is a VALUE.

// PUT /manage/settings — the `atelier` block is a FULL REPLACE of that key (D5)
{
  "atelier": {
    "effort_bands": {                       // EXACTLY the five keys; set equality
      "thirty_min": 30, "one_hour": 60, "two_hours": 120,
      "half_day": 300, "full_day": 540
    },
    "default_weekly_capacity_hours": 30      // or null
  }
}
// `profile` and `toggles` omitted -> untouched. That is merge_settings' atomic
// `settings || :patch::jsonb` and it is why the top level cannot be clobbered.
```

`POST` and the path parameter follow the shipped `/manage` convention (`atelier/router.py:53-55`: the `.claude/rules` RPC / `@QueryValue` guidance is Kotlin boilerplate for another codebase). The capacity route is CSRF-fenced by `CsrfOriginMiddleware`; `cache-control: no-store` comes from the router-level dependency.

---

## Frontend changes

| File | Change |
|---|---|
| `apps/manage/src/components/SeamstressPanel.tsx` | **new** — the named `<section>`/`<h3>`/`<ul>` panel, one row per seamstress, the unassigned total as a `<p>` **outside** the `<ul>` (D8), the load bars (`DashboardSection`'s shipped `Bar` shape, `inlineSize` + `bg-gold-strong`/`bg-danger` on `bg-border`), the capacity `Modal` and the atelier-settings `Modal`, both mounted at **panel** level. Takes `role` and gates both write controls on `ELEVATED.has(role)`. **Owns D14's `<body>` focus fallback** (the heading ref and the trigger are both here). Presentational plus dialog state; every write leaves through D8's callback contract, and dialog open/close is reported up through `onDialogOpenChange` for C7 |
| `apps/manage/src/lib/capacity.ts` | **new** — `capacityMinutes(hours)`, `remainingMinutes(row)`, `loadRatio(row)` (clamped, `Number.isFinite`-guarded, 0-capacity-safe), `overloaded(row)`, **`wouldOverload(row, extraMinutes)`**, `hoursFromMinutes(minutes)` (**`Math.ceil`**, D9), `sortByRemainingCapacity(rows)` (**three groups**, D10). ⚠ **Every fold branches on `weekly_capacity_hours === null`, never on falsiness** (D2). In `lib/` for `lib/stages.ts`'s reason: the panel, the assign `Select` and F40's replacement share it with no import cycle |
| `apps/manage/src/components/AtelierSection.tsx` | **edited** — renders `<SeamstressPanel>` between the freshness row and **whichever of the stage rail or the `EmptyState`** renders (D8); passes `role`; implements the two save callbacks with the shipped `runMutation` (`poll.bump()`, `mutationsRef`, the `.finally()` re-arm, `poll.fail(error)`) **returning a boolean, never rejecting**; ORs the panel's reported dialog state into `dialogOpen` (C7); the assign `Select`'s options sorted and relabelled (D10); the assign cue's overload clause through `wouldOverload`, gated on an actual move (D11). ⚠ **`restoreRef` / `captureFocus` / `boardCommit` are NOT touched, and NO focus code for this feature lives here** |
| `apps/manage/src/api.ts` | **edited** — `SeamstressRef` +4 fields; `AtelierBoardResponse` +2 fields; `SetCapacityRequest`; `SeamstressCapacityResponse`; `AtelierSettingsUpdate`; `Settings`/`UpdateSettingsRequest` gain `atelier`; `api.setSeamstressCapacity(staffUserId, hours)` |
| `apps/manage/src/i18n/he.ts`, `…/ar.ts` | `atelier.capacity.*`, `atelier.settings.*`, `atelier.cue.assignedOverload` — **both files**, Hebrew untranslated in `ar` (D15). The stale *"95 keys"* header comment corrected |
| `apps/manage/src/__tests__/SeamstressPanel.test.tsx` | **new** |
| `apps/manage/src/__tests__/capacity.test.ts` | **new** — the pure folds, including every ugly arithmetic edge |
| `apps/manage/src/__tests__/AtelierSection.test.tsx` | **extended** — the sorted/relabelled assign `Select`, the overload cue, D14's focus fallback and its steal-check |
| `apps/manage/src/__tests__/i18n.test.ts` | **extended** — an `F42 capacity keys resolve` block deriving `HE_F42` **from `HE_F41`** and spreading nothing (D15) |
| `apps/manage/src/__tests__/ProfileSection.test.tsx` | **no change** — `Settings` gains a field; nothing that file asserts is removed |
| `apps/manage/src/App.tsx`, `…/__tests__/Nav.test.tsx` | **no change** — no nav row, no `SectionKey` member. The counts (`NAV_LABELS` 13, `.slice(0, 11)`) stand |
| `apps/manage/vite.config.ts` | **no change** — D16; the new route is on the existing `atelier` segment |
| `apps/manage/src/lib/usePoll.ts`, `…/lib/stages.ts` | **no change** — imported, not modified. Any edit is a review stop; `usePoll` has four callers |
| `Backend/tests/test_frontend_constant_parity.py` | **no change** — ⚠ `MAX_WEEKLY_CAPACITY_HOURS` and `MAX_BAND_MINUTES` are **server** bounds and **must not be mirrored on the client**. The dialogs render the server's 400, exactly as F41 does for the 730-day due-date horizon (`AtelierSection.tsx:70-75` states the rule) |

**Per-component behaviour:**

- **The panel row** is name · bar · sentence · one `Button` «שעות» (**elevated only**). Nothing else. No sparkline, no per-stage split, no ticket list — the columns are three inches below it.
- **The unassigned total is a `<p>` AFTER `</ul>`, never an `<li>`, and carries no bar** — «לא משויך · 4 שעות». It is a total, not a person, nobody has capacity for it, and inside the list it would put the announced item count one above the heading's (D8). Rendered only when `unassigned_minutes > 0`: a zero line is noise on every board that is fully assigned.
- **The capacity `Modal`** carries one `Input type="number"` (`inputMode="numeric"`, `min={0}` — the platform feature, no stepper component; ⚠ **no `max`**, that is a server bound, D15), a «חזרה לברירת המחדל» ghost `Button` that submits `null`, cancel and save. Prefilled with `weekly_capacity_hours` when `capacity_is_default` is false, and **empty** when it is true — so saving without typing cannot silently convert an inherited number into an owned one.
- **The settings `Modal`** carries five number `Input`s (one per band, labelled with the band's Hebrew word) and one for the default. **Prefilled from the board envelope** — `effort_bands` and `default_weekly_capacity_hours` are already on the wire, so the dialog opens with **no read of its own**. Save sends the whole `atelier` block, always (D5), and on a brand-new boutique that freezes the platform bands — intended, D5.
- **Client-side validation is shape only; the server is truth.** A non-integer or a negative is refused before the request with a field-local Hebrew message. ⚠ **Anything the client did not anticipate renders the HEBREW default — `response.data.error.message` is NEVER shown.** Both dialogs route their server errors through a `cardErrorText`-shaped mapper whose `default:` branch is `atelier.capacity.error.server` / `atelier.settings.error.server`. F41 refused exactly this inside this tree and recorded why in the code: *"⚠ C5 — THE `default:` BRANCH IS STRUCTURAL, NOT COSMETIC. `main.py`'s error bodies are ENGLISH and this console is Hebrew-only"* (`AtelierSection.tsx:493-497`). Every domain 400 here is English — `DomainValidationError`'s handler returns `str(exc)` (`main.py:949-953`) and the message this route can actually produce is `_require_seamstress`'s literal `"staff_user_id must be a live seamstress"` (`service.py:517`).
- **Nothing mutates on `change`.** Every `Input` sets draft state and a footer `Button` commits — F41's D16 rule, and here it is the ordinary form shape anyway.
- **Every control is `size="md"`. `size="sm"` is barred on this surface**, as it is on the board: `Button` is `min-h-11` at `md` and `min-h-9` (36 px) at `sm`, and this console runs on workroom phones.

---

## Every state of every surface

**The panel:**

| State | What renders |
|---|---|
| **Initial load** | Nothing. The panel is inside the `boardData !== null` branch — a skeleton for a list of four names is more chrome than content, and F41's `<Skeleton>` card already says the section is loading |
| **Loaded, ZERO tickets (the `EmptyState` branch)** | ⚠ **The panel STILL RENDERS**, above F41's `<EmptyState>`, which in this branch has replaced both the columns and the rail (`AtelierSection.tsx:960-971`). Every seamstress at «0 שעות», no unassigned line. Setting capacity before the first intake is the useful order, so the panel is not suppressed here — and this is the branch a brand-new boutique is in, i.e. both of D2's two "first thing a new boutique sees" states (D8) |
| **Loaded, capacities set** | The `<h3>` «תופרות · 3», then one row per seamstress sorted by remaining capacity, then — **outside the `<ul>`** — the unassigned line if non-zero |
| **EMPTY — no seamstresses at all (a brand-new boutique)** | The `<section>`, the `<h3>` «תופרות · 0», and **one muted line inside the `<ul>`'s place**: an owner reads «אין תופרות רשומות. אפשר להוסיף במסך הצוות.» and a shift manager reads «אין תופרות רשומות.» ⚠ **Two keys, not one**: the staff screen is owner-only (`App.tsx:145`), and a line telling a shift manager to go somewhere the gate refuses is this console lying about its own permissions — `App.tsx:44-49` records that exact failure for `board` |
| **EMPTY — no seamstresses AND `unassigned_minutes > 0`** | **Both, in this order**: the muted empty line, then the unassigned `<p>`. A boutique that opens three tickets before adding any staff satisfies both rules at once — a plausible first hour of a pilot — and it is the state in which the unassigned total is the **only true thing on the panel**. A seamstress row cannot be the empty line's replacement here, because there are none |
| **A SEAMSTRESS is looking at it** | Every row, every bar, every sentence, the unassigned line — and **zero controls**: no «שעות» on any row and no «הגדרות» on the panel (D8). She is admitted to the board by the router (`atelier/router.py:96-98`) and refused by both write routes, and a control she can tap would take the whole section terminal |
| **EMPTY — seamstresses, none with capacity (the second thing a new boutique sees)** | Every row renders **with its real load in hours and NO bar**, each carrying «לא הוגדרה קיבולת». The «הגדרות» control (one boutique-wide default) and each row's «שעות» (one person) are both one tap away. ⚠ **No bar is drawn against an invented denominator** (D2) |
| **Capacity inherited from the tenant default** | The bar and the sentence render normally, plus a muted «ברירת מחדל של הבוטיק». The number is honest about whose it is |
| **Failed poll with the panel on screen** | Unchanged rows. The freshness row above already swapped `updatedAt` for `staleAt` and said so; blanking correct load numbers to report a network fault is worse than the fault |
| **Session or permission ended (401/403)** | The whole section is replaced by F41's terminal panel and the loop stops — **unless one of the FOUR dialogs is open, in which case the terminal DEFERS** (C7). `AtelierSection`'s `dialogOpen` must include the panel's two, or a 401 tick unmounts a settings dialog holding six edited band values (D8). The panel goes with the board once the dialog is dismissed |
| **Truncated board** | The panel is **unaffected and exact**. D3's aggregate is uncapped, so `truncated: true` and correct bars coexist — which is the whole argument against the free Python fold |

**The ugly edges, each designed rather than discovered:**

| Edge | Behaviour |
|---|---|
| **Capacity 0, load 0** | «0 שעות מתוך 0», bar empty, **not** overloaded. She is configured as unavailable and holds nothing; that is a consistent state, not an alarm |
| **Capacity 0, load > 0** | «6 שעות מתוך 0 · עומס יתר», bar full and red. The ratio is undefined; the fact is not |
| **Load with no capacity set** | «6 שעות · לא הוגדרה קיבולת». **No bar, no colour, no overload word** — there is nothing to exceed. This is the single most likely state in week one and it must not read as an error |
| **400 % load** | Bar **clamped at 100 %**, text unclamped: «46 שעות מתוך 12 · עומס יתר». The numbers are never abbreviated, rounded away or replaced by «>100%» |
| **20 seamstresses** | The `<ul>` is `max-h-64 overflow-y-auto` at **every** width with `tabIndex={0}`, so the panel never pushes the stage rail off a 375 px screen. The `<h3>`'s count is what tells a screen-reader user the list is long before she enters it |
| **A deleted or re-roled seamstress with live tickets** | Her row renders **with her load and her bar** — the work is real and somebody must move it — carrying the shipped «תופרת שאינה פעילה». **The «שעות» control is absent**: the server refuses her (`_require_seamstress`), and rendering a control that always 400s is a trap. She is **not** in the assign `Select` (F41's shipped `assignable` filter) |
| **A seamstress whose row leaves the payload mid-edit** | Retired **and** her last undelivered ticket delivered. The dialog is at panel level so it survives the repaint; on save the trigger is gone and D14's `<body>` guard puts focus on the panel `<h3>` |
| **`unassigned_minutes` is 0** | The unassigned row is not rendered at all |
| **A band re-tuned yesterday** | Bars are sums of minutes valued under two mappings. Correct, left alone, and stated in D4 so nobody normalises it |
| **A re-tune FLATTENS one band onto another's number** | An old 240-minute ticket under a mapping where `full_day = 240` renders «יום מלא», not the «{{minutes}} דק׳» fallback — `bandLabel` matches on the minutes value, first match wins (`lib/stages.ts:72-81`). **The label moves, the load number does not.** Accepted (D4), because the alternative is an `effort_band` column the model refuses by design |
| **Load 721 minutes against a 12 h capacity** | «12.1 שעות … מתוך 12 · עומס יתר». `hoursFromMinutes` rounds **up** so the sentence can never read «12 מתוך 12» beside «עומס יתר» — displayed-equal beside a word saying over, in the one string that is the whole a11y payload (D9) |
| **Every seamstress overloaded** | Every bar red, every row carrying the word. No aggregated «הבוטיק בעומס» banner — a second, louder signal saying what four rows already say is how a board stops being read |

**The two dialogs:**

| State | What renders |
|---|---|
| **Submitting** | The confirm `Button` carries `loading` (which also disables it); the fields stay enabled so a slow network does not eat a correction |
| **Per-field validation error** | The message rides the field's own `error` prop (`Input` wires `aria-describedby` + `role="alert"`) |
| **A server error mapping to no field** | One alert **inside the dialog**, above the footer, `role="alert"` and focused — carrying the **Hebrew default**, never `error.message`'s English (§Frontend) and never a toast behind a modal. The dialog stays **open**: the callback resolved `false` |
| **Success** | The `Modal` closes, native `<dialog>` returns focus to the trigger by itself (D14), the cue is announced, and the panel repaints from the write's response patched into the held payload — ⚠ **only `weekly_capacity_hours`, `capacity_is_default` and `assignable`**, which is all `SeamstressCapacityResponse` carries. `assigned_minutes` and `due_soon_minutes` are **left untouched** and keep their last-tick values, so a capacity save never collapses her bar or drops her «עומס יתר» word (D6). The next tick supplies the load |

---

## Acceptance criteria

Each line maps to a named test.

- [ ] `staff_users.weekly_capacity_hours` exists, is `INTEGER` **nullable**, and its CHECK definition is pinned **byte-identical** via `pg_get_constraintdef` (captured by running it, never transcribed) → `test_migrations.py` (db)
- [ ] `idx_alteration_tickets_tenant_assignee` exists with its partial predicate, pinned via `pg_indexes.indexdef` → `test_migrations.py` (db)
- [ ] This feature's migration runs **up and down**, and `alembic heads` prints exactly one head → `test_migrations.py` (db) + `test_exactly_one_migration_head` (fast)
- [ ] `weekly_capacity_hours` of `-1` and of `169` are both refused by the database → `test_migrations.py` (db)
- [ ] Load counts a ticket at `intake`, at `ready`, and one whose `delivered_at` was **undone**; excludes a delivered one, a soft-deleted one and another tenant's → `test_atelier_capacity_db.py` (db)
- [ ] **A ticket due in 30 days is in `assigned_minutes` and NOT in `due_soon_minutes`; a ticket 10 days overdue IS in both. Mutation: delete the `FILTER (WHERE due_date <= :horizon)` → the 30-day ticket reddens the bar → red** → `test_atelier_capacity_db.py` (db)
- [ ] The horizon is `today_jerusalem + 7` and comes from `board()`'s existing `today`; a ticket due exactly on day 7 is in, day 8 is out → `test_atelier_capacity_db.py` (db)
- [ ] Load groups `NULL` as its own bucket and it reaches the wire as `unassigned_minutes` → `test_atelier_capacity_db.py` (db) + `test_atelier_board.py` (fast)
- [ ] A seamstress holding no tickets reports `assigned_minutes: 0` and `due_soon_minutes: 0` and does not vanish from `seamstresses[]`; a seamstress whose every job is due next month reports `due_soon_minutes: 0` and a real `assigned_minutes` → `test_atelier_board.py` (fast)
- [ ] **A board that TRUNCATES still reports exact load** — the aggregate is uncapped. **Mutation: compute the load by folding the board's ticket list in Python → red** → `test_atelier_capacity_db.py` (db)
- [ ] `weekly_capacity_hours` resolves from her column, else the tenant default, else `null`; `capacity_is_default` is true only in the middle case → `test_atelier_capacity.py` (fast)
- [ ] **A stored `weekly_capacity_hours` of `0` with a tenant default of `40` resolves to `0` with `capacity_is_default: false`. Mutation: replace `resolve_capacity`'s `is not None` with `or` → red** → `test_atelier_capacity.py` (fast)
- [ ] A tenant with no `atelier` settings key resolves every seamstress to `weekly_capacity_hours: null` — **no platform default** → `test_atelier_capacity.py` (fast)
- [ ] A corrupt stored default (a string, a bool, `-1`, `200`) resolves to `null` and does not crash the poll → `test_atelier_capacity.py` (fast)
- [ ] The board poll issues exactly **four** business statements; the bands and the capacity default add none → `test_atelier_capacity_db.py` (db, statement count)
- [ ] `PUT /manage/settings` with an `atelier` block leaves `profile` and `toggles` intact, and a concurrent profile write is not lost. **Mutation: replace `merge_settings`' `settings || :patch` with a Python read-modify-write → red** → `test_boutique_settings_db.py` (db, **forced interleave**)
- [ ] An `atelier` block missing a band key, carrying an unknown key, a `bool`, a `"300"`, a `240.0`, a `0`, or a value over 1440 is a **400** and writes nothing → `test_boutique_settings_api.py` (fast)
- [ ] **`{"half_day": true}` is a 400, not a 200 writing a one-minute band. Mutation: relax `StrictInt` to `int` → pydantic coerces `true` to `1`, the case turns 200 → red** → `test_boutique_settings_api.py` (fast)
- [ ] **Two sequential whole-block `atelier` saves: the second wins entirely, the first's bands are gone, and BOTH audit rows exist with their full values** — the lost update is the designed behaviour and the trail is the recovery path (D5/D12) → `test_boutique_settings_db.py` (db)
- [ ] `default_weekly_capacity_hours: null` **clears** the stored default; omitting the field is a 400 (it is required) → `test_boutique_settings_api.py` (fast)
- [ ] Saving only the bands **cannot** clear the default. **Mutation: give `AtelierSettingsUpdate.default_weekly_capacity_hours` a `= None` default and drop it from the patch when unset → red** → `test_boutique_settings_api.py` (fast)
- [ ] A re-tuned band mapping changes **no** `alteration_tickets.effort_minutes` and **no** load number; a card whose minutes match no live band renders «{{minutes}} דק׳» → `test_atelier_capacity_db.py` (db) + `stages` test
- [ ] **A 240-minute ticket under a mapping where `full_day = 240` renders «יום מלא» — the relabel is chosen, not discovered — and the load number is unchanged** (D4) → `stages` test
- [ ] `POST …/capacity` sets, updates and clears; the response is the **refreshed** `SeamstressCapacityResponse` and carries **no** `assigned_minutes` and **no** `due_soon_minutes` → `test_atelier_capacity_db.py` (db)
- [ ] **A capacity save does not change the rendered load or the overload word** — the console patches only the response's keys onto the held row → `SeamstressPanel.test.tsx`
- [ ] Setting the hours she already has answers **200** and writes **no** audit row → `test_atelier_capacity_service.py` (fast)
- [ ] The capacity audit row carries `from` and `to`. **Mutation: capture `before` after the write → red** → `test_atelier_capacity_db.py` (db)
- [ ] Two interleaved capacity writes: the loser renders the **database's** value. **Mutation: drop `populate_existing=True` from `StaffUsersRepository._refreshed` → red** → `test_atelier_capacity_db.py` (db, **forced interleave**)
- [ ] `POST …/capacity` against a receptionist, a retired staffer, an unknown id and another tenant's id → **400 / 400 / 400 / 400, and all four bodies are byte-identical** — `_require_seamstress` cannot distinguish them and no 404 exists on this route outside the check-to-UPDATE race (D6/D13) → `test_atelier_capacity_service.py` (fast) + `test_atelier_isolation.py` (db)
- [ ] `SetCapacityRequest` refuses `true`, `"24"` and `24.0` — **`StrictInt`. Mutation: relax to `int` → `true` is accepted as a one-hour week → red** → `test_atelier_capacity_service.py` (fast)
- [ ] **A seamstress gets 403 on `POST …/capacity`, with the generic body** → `test_atelier_api.py` (fast)
- [ ] `reception` and `sales_assistant` reach exactly the three floor routes; `seamstress` reaches the floor routes plus the six non-elevated atelier routes and **neither** `delete` **nor** `capacity` — a set equality **per role** over `effective = intersection(gates)` → `test_staff_role_gating.py` (fast)
- [ ] `ATELIER_OPEN` names `capacity`, so deleting the route reds the anti-vacuity half → `test_staff_role_gating.py` (fast)
- [ ] The observed error-code set is still **set-equal** to `SPEC_ERROR_CODES`; **F42 adds none** → `test_atelier_api.py` (fast)
- [ ] The Vite dev proxy's segment set still equals the live route table's, **with no `vite.config.ts` edit** → `test_spa_serving.py` (fast, shipped guard)
- [ ] The settings audit row is written only after a successful merge, **names the actor**, and a merge answering `None` writes nothing → `test_boutique_settings_db.py` (db)
- [ ] `loadRatio` — 0 capacity with 0 load, 0 capacity with load, exactly at capacity, 4× capacity (**clamped at 100**), null capacity, and a `NaN` input (the `isFinite` guard) → `capacity.test.ts`
- [ ] **A row with capacity `0` and 360 due-soon minutes renders a full red bar and «עומס יתר»; a row with capacity `null` and 360 renders NO bar and «לא הוגדרה קיבולת». Mutation: replace the `=== null` check with `!row.weekly_capacity_hours` → red** → `capacity.test.ts` + `SeamstressPanel.test.tsx`
- [ ] **`wouldOverload(row, 0) === overloaded(row)` across the whole D9 edge table** (null capacity, 0/0, 0/load, exactly at capacity, 4×) — one assertion that reds on any drift between the bar's predicate and the cue's, including the `null * 60 = 0` case. **Mutation: re-inline the cue's comparison and drop the null guard → red** → `capacity.test.ts`
- [ ] **`hoursFromMinutes` at capacity−1, capacity and capacity+1 minutes for a 12 h capacity: the rendered string and `overloaded` never disagree** — «12 מתוך 12» never appears beside «עומס יתר». **Mutation: `Math.ceil` → `Math.round` → red** → `capacity.test.ts`
- [ ] `sortByRemainingCapacity` — real headroom first, then no-capacity rows by load ascending, then **overloaded rows last, least-over first**; `display_name` then `id` as tiebreaks; a capacity-`0`-with-load row is in group 3; and the input array is not mutated. **Mutation: collapse groups 1 and 3 into one → the overloaded-below-unconfigured assertion reds** → `capacity.test.ts`
- [ ] The assign `Select`'s options appear in remaining-capacity order and each carries its hours. **Mutation: drop the sort → red** → `AtelierSection.test.tsx`
- [ ] An assign that pushes the target over capacity announces `atelier.cue.assignedOverload`; one that does not announces `atelier.cue.assigned`. Asserted on `getByRole("status")`'s **textContent** → `AtelierSection.test.tsx`
- [ ] **Re-committing the ticket's CURRENT assignee announces `atelier.cue.assigned`, never the overload variant** — her minutes are already in her load and the clause is gated on an actual move (D11) → `AtelierSection.test.tsx`
- [ ] Nothing is blocked: an overloaded seamstress is still selectable, the assign still answers 200, and no confirm dialog appears → `AtelierSection.test.tsx`
- [ ] An overloaded row's text contains her name, both numbers **and «עומס יתר»**. **Mutation: delete the word and keep the red class → red** → `SeamstressPanel.test.tsx`
- [ ] The bar is `aria-hidden`, carries no `role`, no `aria-valuenow` and no accessible name, and its fill sets **`inline-size`** (not `width`) with a **declared** token class (`bg-gold-strong` / `bg-danger`, never `bg-accent` — which does not exist in `theme.css` and emits no utility) → `SeamstressPanel.test.tsx`
- [ ] A seamstress with no resolved capacity renders **no bar at all** and the «לא הוגדרה קיבולת» word → `SeamstressPanel.test.tsx`
- [ ] A `assignable: false` row renders its load and **no** «שעות» control → `SeamstressPanel.test.tsx`
- [ ] The panel `<section>` is a named region and its `<ul>` resolves as `getByRole("list", { name: t("atelier.capacity.heading") })` — the **uncounted** key, so the name does not churn on every tick — which also catches a row grid built with `role="grid"` → `SeamstressPanel.test.tsx`
- [ ] **The `<ul>`'s item count equals `seamstresses.length` and equals the `<h3>`'s `{{total}}`, on a board with `unassigned_minutes > 0`** — the unassigned total is a `<p>` outside the list → `SeamstressPanel.test.tsx`
- [ ] Zero seamstresses: an owner sees the staff-screen line and a shift manager does not; **zero seamstresses AND `unassigned_minutes > 0` renders the muted empty line AND the unassigned line, in that order** → `SeamstressPanel.test.tsx`
- [ ] **`role="seamstress"` renders no «שעות» on any row and no «הגדרות» — an ungated control is one the server is certain to refuse. Mutation: drop the role guard → `queryAllByRole("button")` is no longer empty → red.** *(Corrected in review round 1: the mutation was stated as "a 403 reaches `runMutation`, `poll.fail` classifies it terminal and the whole section is replaced by «אין הרשאה»", which is unreachable — both panel writes pass `terminalOnFailure = false`, so their 403 never reaches `poll.fail`. That opt-out is pinned separately by the line below; do not restore the flag to make the old wording true.)* → `SeamstressPanel.test.tsx`
- [ ] **A 403 from either panel write keeps the BOARD alive and renders the refusal inside the dialog** — a per-route refusal means "not this control", never "not this board". **Mutation: pass `terminalOnFailure = true` → the section is replaced by «אין הרשאה» → red** → `AtelierSection.test.tsx`
- [ ] **A 401 tick while the settings dialog is open does NOT unmount it** — C7's deferral covers all four dialogs. **Mutation: drop the panel's dialogs from `dialogOpen` → red** → `AtelierSection.test.tsx`
- [ ] **The panel renders in the zero-ticket `EmptyState` branch**, above the `EmptyState`, with every seamstress at «0 שעות» → `AtelierSection.test.tsx`
- [ ] **An unmapped 400 renders the Hebrew default in the dialog's alert, never `error.message`'s English body** (`_require_seamstress`'s `"staff_user_id must be a live seamstress"` is the concrete case) → `SeamstressPanel.test.tsx`
- [ ] Saving capacity when the row has left the payload moves focus to the panel `<h3>`. **Mutation: delete the fallback → focus is `<body>` → red** → `SeamstressPanel.test.tsx`
- [ ] Saving capacity when the user has moved focus elsewhere herself **does NOT move it** — the steal direction. **Mutation: drop the `activeElement === document.body` guard → red** → `SeamstressPanel.test.tsx`
- [ ] «שעות» and «הגדרות» do not call any API method until the dialog's save is activated → `SeamstressPanel.test.tsx`
- [ ] Every control renders at the 44 px floor (`toHaveClass("min-h-11")`); no `size="sm"` anywhere in the panel tree → `SeamstressPanel.test.tsx`
- [ ] **The concrete tab order**: `userEvent.tab()` from the `<h3>` reaches the `<ul>` (its `tabIndex={0}` overflow stop), then each row's «שעות» `Button` in render order, then «הגדרות». Enter on «שעות» opens the dialog; Tab reaches the number `Input`, «חזרה לברירת המחדל» and save; Esc dismisses **without writing**. *(This replaces "fully operable with no pointer", which named no assertion and would have been written as a tautology or skipped — and it is what pins D8's "keyboard-navigable by construction" claim.)* → `SeamstressPanel.test.tsx`
- [ ] axe: zero violations on the panel and on both open dialogs — **explicitly not sufficient**, since axe cannot see a focus move that never happened → `SeamstressPanel.test.tsx`
- [ ] Every `atelier.capacity.*` / `atelier.settings.*` key resolves in `he` and is non-empty in `ar`; both new aria names contain their visible labels; nothing matches `/נשלח|תישלח|בדרך/`; **no new key's Hebrew contains «168» or «1440»** (they are server bounds — F41's `dueDateHorizon` precedent, `i18n.test.ts:705-719`); `HE_F42` is **derived from `HE_F41` and not spread into `HE`** → `i18n.test.ts`
- [ ] **The three assign-option strings are composed from `optionRow` / `optionRemaining` / `optionAssigned` / `over` and contain no Hebrew literal in TSX** → `AtelierSection.test.tsx` + `i18n.test.ts`

---

## Testing

**Fast suite (no marker, no Docker):**

- `tests/test_atelier_capacity.py` (**new**, pure): `default_capacity_hours` over an absent key, a `dict`, a `str`, a `bool`, `-1`, `0`, `168`, `169`; the two-step resolution and `capacity_is_default` over the four combinations of (her column set / not) × (tenant default set / not).
- `tests/test_atelier_board.py` (**extended**, pure folds over frozen records): `SeamstressRef` with a load, without one (0 through `.get`), with `assignable: false` and a load; `unassigned_minutes`; `default_weekly_capacity_hours` on the envelope; the fold still re-sorts nothing.
- `tests/test_atelier_capacity_service.py` (**new**): the capacity route's authorization matrix against fakes — elevated on anyone; the target-not-a-seamstress 400; the unknown-id 404; the no-op writing no audit row; the `before`/`after` audit payload; **and the repository is never called on the pure-role refusal**, `test_floor_service.py`'s shipped assertion.
- `tests/test_atelier_api.py` (**extended**): `ATELIER_ROUTES` gains the capacity row (the 401 walk, the wiring walk, `no-store`); the seamstress 403 with the generic body; the error-code set still **set-equal** to `SPEC_ERROR_CODES`.
- `tests/test_boutique_settings_api.py` (**extended**): the `atelier` block's validation matrix, **each row with its expected status stated** — missing band key **400**, unknown band key **400**, `true` **400**, `"300"` **400**, `240.0` **400**, `0` **400**, `1441` **400**, a `default` of `-1` **400** / `169` **400** / `"30"` **400** / `true` **400**, and the required-`default` omission **400**. ⚠ The `true`, `"300"` and `240.0` rows are **`StrictInt`'s**, and every one of them is a **200** against plain `int` — which is the whole reason D5 types them strictly.
- `tests/test_staff_role_gating.py` (**extended**): `ATELIER_CAPACITY` and `ATELIER_ELEVATED`; the per-role set equality; the widened `declared`. ⚠ **The classifier stays `frozenset.intersection`, never `any(...)`** — the shipped docstring (`:364-374`) gives the whole argument and the capacity route is the second instance of exactly the shape that breaks under `any`.
- `tests/test_spa_serving.py` (**no edit — it is the guard**): it stays green precisely because the new route is on the existing `atelier` segment.

**`db`-marked (real Postgres; no Docker locally, per the run's standing constraint. F34's, F57's and F41's shipped notes are the standard: stand up a throwaway Postgres 16 cluster outside the repo, run every migration and execute these before pushing, and CAPTURE the deparsed constraint and index literals rather than transcribing them):**

- `tests/test_migrations.py` (**extended**): the column, nullable, `integer`; the CHECK pinned byte-identical via `pg_get_constraintdef`; the index via `pg_indexes.indexdef`; the two out-of-range inserts refused; up **and** down.
- `tests/test_atelier_capacity_db.py` (**new**): the load aggregate against real rows across all five stages, an undone delivery, a soft delete and a foreign tenant; the uncapped-vs-truncated case; the statement count on the poll; the capacity write's happy paths, its audit row, and the two forced interleaves below.
- `tests/test_boutique_settings_db.py` (**extended**): the `atelier` patch leaving `profile` and `toggles` intact under a forced interleave; the audit row's ordering against a `None` merge.
- `tests/test_atelier_isolation.py` (**extended**): tenant B's context cannot set tenant A's seamstress's capacity and cannot see her load; the 404 is indistinguishable from missing. *A new column on a tenant table under forced RLS still gets its isolation line — the E9 brief's crown-jewels rule.*

**⚠ `asyncio.gather` is deliberately NOT used for either interleave**, for F34's, F57's and F41's reason verbatim (`test_floor_db.py:251-263`): gather does not **order** two transactions, so the loser most often loads *after* the winner commits, the in-memory instance is already correct, and the branch the test exists to prove goes green **without the mechanism ever being exercised**. The mechanism is `tenant_session`'s own shape — exiting the context manager **is** the commit (`db/tenant.py:25`) — and two nested `tenant_session`s on one `NullPool` factory take two separate connections.

**⚠ `test_atelier_capacity_db.py` seeds `staff_users` rows and inherits F57's D1 trap through F41's note**: no **committed** `staff_users` row may hold a floor role, or `test_migrations.py::test_adding_the_role_check_validates_existing_rows` — which re-adds 0011's **two-value** CHECK on a populated table — goes red in a file that never mentions capacity. Seed seamstress rows inside a transaction the test rolls back.

**The concurrency mechanisms, and for each the EXACT mutation that must turn its test red** — and each mutation must additionally be verified to leave **every other test green**, because a mutation that reds three tests has pinned nothing specific:

| # | Test | Mechanism | **MUTATION → RED** |
|---|---|---|---|
| 1 | `test_the_loser_of_two_capacity_writes_renders_the_databases_hours` | `populate_existing=True` inside `StaffUsersRepository._refreshed`, reached from the capacity path | **Drop `populate_existing=True`.** ORM-enabled DML's `evaluate` synchronization has already stamped the SET value onto the identity-mapped instance the loser loaded (it must load it — `_require_seamstress` and the audit `from`), and `expire_on_commit=False` hands it straight back, so the loser's response carries **its own** hours. ⚠ It **must** be this shape: F57's note records that with only fresh-session tests present, removing this flag changed nothing |
| 2 | `test_an_atelier_patch_does_not_clobber_a_concurrent_profile_write` | `merge_settings`' single atomic `settings = settings \|\| :patch::jsonb` | **Replace it with a Python read-modify-write** (`by_id` → mutate the dict → `UPDATE … SET settings = :whole`). Under READ COMMITTED both writers read a snapshot without the other's commit and the last one wins the whole column; `assert merged["profile"] == …` reds |
| 3 | `test_the_capacity_audit_row_carries_the_value_it_replaced` | the capture of `before` into a **local, before** the write | **Move the capture after the write.** `evaluate` synchronization stamps the new value onto the very instance being read, so `details["from"]` becomes the new hours. F57's note records that this mutation leaves the fast suite green, because monkeypatched repositories never stamp anything |
| 4 | `test_a_truncated_board_still_reports_exact_load` | D3's separate, **uncapped** aggregate | **Fold the load in Python over `board()`'s ticket list.** Seed `BOARD_TICKET_LIMIT + 20` live tickets for one seamstress; the fold under-counts by the truncated tail and the assertion reds. This is the mutation that makes the fourth statement's cost justified rather than asserted |

**Plus one non-race mutation, for the mechanism a request model carries rather than a statement:**

| Test | Mechanism | **MUTATION → RED** |
|---|---|---|
| `test_saving_only_the_bands_cannot_clear_the_default` | `AtelierSettingsUpdate`'s **required** `default_weekly_capacity_hours` (D5) | **Give it `= None` and drop it from the patch when unset.** A bands-only save then replaces the whole `atelier` object without the default and silently clears it; the assertion on the re-read reds. This is the shallow-merge trap, pinned |
| `test_a_boolean_band_is_refused` | `StrictInt` on `AtelierSettingsUpdate.effort_bands` (D5) | **Relax `StrictInt` to `int`.** Pydantic coerces `true` to `1` before any validator runs, `validate_atelier_settings` never sees a bool, and `{"half_day": true}` becomes a 200 writing a **one-minute** band that silently understates every load bar downstream |
| `test_a_zero_capacity_is_hers_and_not_the_boutiques` | `resolve_capacity`'s `is not None` (D2) | **Replace it with `or`.** A seamstress marked 0 ("away this week") resolves to the tenant default, her bar renders at a fraction of the truth in the non-overload colour, `capacity_is_default` reports `true` on a number she set, and D10's sort puts her **first** in the assign `Select` labelled «נותרו 40 שעות» |
| `test_the_bar_counts_only_work_due_inside_the_week` | D3's `FILTER (WHERE due_date <= :horizon)` | **Delete the FILTER.** `due_soon_minutes` becomes the whole backlog, a ticket due in 30 days reddens the bar, and a healthy shop with a forward book reads red on every row |
| `test_the_cue_and_the_bar_share_one_predicate` | `wouldOverload` routing both call sites through `overloaded` (D9) | **Re-inline the cue's comparison** as `due_soon_minutes + effort_minutes > capacity * 60` and drop the null guard. `null * 60 = 0` in JS, so every assign to an unconfigured seamstress announces «עומס יתר» on the one channel a screen-reader user has — correct on screen, green under axe |
| `test_a_seamstress_sees_no_write_controls_on_the_panel` | `ELEVATED.has(role)` on both panel controls (D8) | **Drop the role guard.** A seamstress taps «שעות», the 403 reaches `runMutation`, `poll.fail` classifies it terminal under the {401,403} rule, and the **entire atelier board** is replaced by «אין הרשאה» |
| `test_a_terminal_defers_while_a_panel_dialog_is_open` | the panel's `onDialogOpenChange` folded into `AtelierSection`'s `dialogOpen` (C7) | **Drop the panel's dialogs from `dialogOpen`.** A 401 tick unmounts a settings dialog holding six edited band values |

**Frontend (vitest).** `capacity.test.ts` is pure and covers the arithmetic edges; `SeamstressPanel.test.tsx` and the `AtelierSection.test.tsx` extension cover the acceptance list. **Three assertions carry the legal load and may not be cut:**

1. **Both focus directions** (D14) — the `<body>` fallback lands on the `<h3>`, and a user who moved focus herself is **not** yanked back. Each written so that deleting its line reds it: assert `document.activeElement` **is** the expected node, never merely that the node exists. ⚠ jsdom does not blur a disabled element, so a test that leans on that is vacuous — F57's own vacuous focus test is the recorded instance.
2. **Overload is never colour-only** — the row's textContent, and the mutation that deletes the word while keeping the class.
3. **The bar has no widget semantics** — `aria-hidden`, no role, no `aria-valuenow`, no accessible name. axe will not catch a wrongly-roled `progressbar`; this assertion is the only thing that does.

**No E2E**, F34's, F57's and F41's reason verbatim: the console's entire e2e surface is two login-screen tests because `vite preview` runs with no backend. Recorded rather than silently skipped.

---

## Out of scope

- **The F40 roster projection** — hourly capacity walked back from the due date, per-day and per-horizon bars. The recorded upgrade path (D2), an E8 feature, not queued.
- **Split load and expedite** — the other two actions of the E9 brief's success criterion 3. Both add columns to `alteration_tickets` and two `AuditAction` members; F41's Out-of-scope sizes them.
- **Any block, refusal, confirm-on-overload or auto-balancing suggestion.** #40: every reallocation is a human action.
- **Load history, trend or throughput** — F44's, which reads the five stamps directly.
- **Per-day or per-week buckets of the current load.** One number, now.
- **Capacity for reception, sales assistants or the owner.** D6 refuses a non-seamstress target; Risk 6 carries the ceiling and the escape hatch.
- **A re-validation sweep that corrects `assigned_staff_user_id` when a role changes.** F41's Risk 12 handed this here; F42 **renders** the anomalous bucket (with a load number) rather than correcting it, and the correcting sweep on every staff write stays unbought.
- **Auditing `profile` and `toggles` on `PUT /manage/settings`.** A pre-existing gap this feature does not widen (D12, Risk 7).
- **A bulk re-value of `effort_minutes` after a band re-tune** — D4, declined with reasons.
- **A second poll loop, a capacity-only endpoint, or a nav row.** The envelope is the mechanism (F41 D12) and the panel is content.
- **Mirroring any server bound on the client.** `MAX_WEEKLY_CAPACITY_HOURS` and `MAX_BAND_MINUTES` stay server-only.
- **A language switcher.** Deferred by the 2026-07-31 languages ruling; `ar` keys ship untranslated.

---

## Codebase and program-state conflicts recorded

1. **LOOP-STATE and Interview Q2 call this surface "the capacity matrix"; the simplified model has no matrix.** Q2 flagged it as a novel interaction pattern and the 2026-07-31 ruling self-approved its design gate. A matrix's second dimension is time, and time is the roster projection the same ruling **drops**. What ships is a list of the shape F41 already ships five of, which is also what discharges the e9 Risks' keyboard requirement without a custom keyboard model (D8). **Codebase-and-ruling-consistent reading taken; the matrix is recorded as F40's shape.**
2. **F41's spec D10 and D12 call `app/atelier/` the NINTH `/manage` router and say `create_app()` mounts eight; the SHIPPED router docstring says TENTH** (`atelier/router.py:3`), because F33's `queue_manage_router` landed between the spec and the build. **Codebase-consistent reading taken: ten today, and F37 may make it eleven.** F42 adds no router, so no count moves — recorded because a builder reading F41's spec would write the wrong number into a comment.
3. **F41's spec D11 declares SIX `AuditAction` members; SEVEN shipped.** `ATELIER_CUSTOMER_RENAMED` (`constants.py:444`) was added at build as the mitigation for `upsert` rewriting `customers.name`, replacing the dialog notice the spec described. **F42 adds two to seven, not to six.**
4. **F41's spec §Every state promises an intake-dialog notice «לקוחה קיימת — השם יעודכן ל…»; it does not ship.** `atelier.form.existingCustomer` was **removed at review** and `i18n.test.ts:705-719` records why. Not F42's to fix, and named because a reader of the F41 spec will look for it and find an audit row instead.
5. **F41's Risk 9.4 predicts F42 adds TWO fields to `seamstresses[]`; F42 adds FOUR.** `capacity_is_default` is the third, because the resolved number and her own column are different facts and both the panel and the editor need to tell them apart (D7). `due_soon_minutes` is the fourth, for §Conflicts 13's dimensional argument: the bar needs a numerator in the denominator's units, and the ruling's total stays on the wire beside it.
6. **F41's Risk 9.5 predicts F42 adds "an advisory overload flag" to `AtelierService.assign`'s response; F42 adds NONE.** The console already holds every number needed and computes the cue itself at zero server cost (D11). The prediction's *intent* — flag, never refuse — is honoured exactly; its mechanism is not needed.
7. **F41's Risk 4 sizes the settings writer as "four edits"; it is six across four files** (D5's table). The two it does not count are `SettingsResponse` and the router's two pass-throughs — both required, because a settings endpoint that cannot read back what it just wrote is a trap.
8. **F41's D12 fixes the board poll at THREE business statements and calls that "the budget"; F42 makes it FOUR.** A deliberate, sized departure with the alternative (a `LEFT JOIN` fold) recorded and the reason it was refused stated (D3). F29 is handed the new figure by name.
9. **The E9 brief and LOOP-STATE both say "the load bar turns red when load exceeds capacity"; with the simplified model a seamstress may have NO capacity, and then there is no bar to turn red.** D2 makes that a designed state rather than an overload, and §Every state pins its rendering. Recorded because "no bar" is not what either source describes, and it is the state a brand-new boutique sits in.
10. **F41's Risk 5 hands F42 "a boutique whose owner sews cannot be assigned a ticket".** F42 **does not widen** `_require_seamstress` and does not treat the owner as an implicit capacity row — both were the recorded cheap remedies. The reason is the same one that makes the check worth having: a ticket assigned to a non-seamstress is work no bar will ever show, and widening the check would put exactly that hole into the feature whose job is to close it. The escape hatch stays a `seamstress` account, and the cost — she loses owner-only access to staff CRUD, terms and the gateway — is restated in Risk 6 rather than solved.
11. **Pre-decided #41 makes F40's published roster the source of seamstress availability.** The 2026-07-31 ruling drops it for this run and records the projection as the upgrade path. Named so nobody schedules F42 against #41's dependency graph, and D2 states exactly what F40 replaces.
12. **`main`'s head is `0021` as this spec is written and that number is already a liability.** F37 is building with a migration in `.worktrees/sos-paging`. D1 states a rule and no number, and `0020`'s header records the two occasions this repo has already lived the failure.
13. **⚠ LOOP-STATE's ATELIER ruling states the load as *"the sum of undelivered effort"* with no date predicate; F42 adds a 7-day horizon to the BAR's numerator and keeps the ruling's total on the wire.** The ruling's formula compares a **stock** (an unbounded backlog — `alteration_tickets.py:20-28` says so in as many words) to a **rate** (hours per week). The ratio is not a utilisation, and the error is chronic and one-directional: a 40 h/week seamstress with six weeks of evenly-spread forward work renders at 600 %, clamped, red, on day one, on every row, in any boutique with a book — and a bar that is red in the steady state is a bar nobody reads. So the bar's numerator is `due_soon_minutes` (`due_date <= today + 7`), the ruling's number ships unchanged as `assigned_minutes`, both are on screen in the same row, and the horizon costs **one FILTER clause in the same aggregate, zero statements and zero new date sources** (`board()` already has `today`). **This is not F40's projection** — no roster, no availability model, no per-ticket walk-back, one flat weekly number. *If the ruling is to be read word-for-word on the bar as well, the reversal is ONE LINE: point `loadRatio` at `assigned_minutes` in `lib/capacity.ts`. Recorded so that choice stays available rather than buried.* (D3, D7, D9.)
14. **The e9 brief defines the load numerator as *"over her jobs not yet `ready_at`"* (`e9-alterations.md:67`); LOOP-STATE's ruling says *"not yet delivered"* and governs, so D3 uses `delivered_at IS NULL`.** The consequence is worth stating because it is the largest product divergence in this list: **a garment finished, QC'd and hanging on the rack counts in full against the seamstress who made it until the bride collects it.** In wedding season that is days of phantom load per garment; a seamstress with ten finished-but-uncollected gowns reads red with an empty bench, and D10's sort then routes work away from the only person free to take it. Defensible because the work is still physically in the workroom and still hers to redo if QC bounces — and the remedy already ships: advance to `delivered` at collection, one tap on F41's shipped control. **If the pilot reports it, the fix is a one-clause change to D3's predicate**, which makes it an upgrade rather than a rewrite.
15. **E9's degradation clause names the tenant's OPENING-HOURS WEEK as the roster-free fallback; F42 declines it and ships a hand-set tenant default instead.** The clause (`e9-alterations.md:73`) is specific: *"if no published roster covers a date, capacity falls back to the tenant's opening-hours week … it is one query, not a second model"*, and this spec cites the clause three times as its authority for a roster-free build while silently dropping its named mechanism. **Declined for D2's reason**: a shop open 60 hours a week does not mean a seamstress works 60, and a denominator wrong by 3× in the reassuring direction is worse than no denominator — it would make every bar lie by construction on day one with nobody having entered a number to be wrong. `availability_rules` remains available to F40 if the pilot rejects the two-tap setup. **This is also the second-order reason D2's "no bar" state exists at all**, and recording it converts a silent omission into a decision.
16. **The e9 brief says F42 *"does not self-approve at its design gate — it comes to the user as a clickable prototype first"* (Interview Q2).** The 2026-07-31 ruling supersedes it — *"build through their Q2 novel-pattern gates without pausing"* — and D8 records the second-order reason the gate mattered less than Q2 assumed: the dense matrix that carried all the design risk is F40's shape and is not what ships.

---

## Risks and open items

1. **The denominator is a self-reported weekly number, and nothing verifies it.** A seamstress who works 20 hours but is recorded at 40 gets a green bar while she drowns. There is no clock-in, no roster and no measurement of actual throughput in this build — F44's median time-in-state is the first thing that could expose the drift, and F40 is the first thing that could replace the number. **This is the same accepted risk as E9's estimate-quality risk (F41's Risk 2), one level up**: bad estimates make the numerator lie and a bad capacity makes the denominator lie, and the product cannot tell either. *Owner: the boutique owner. The pilot conversation should say this out loud rather than let her discover it. Trigger: F44, then F40.*
2. **What F40 changes when it lands, and it is only the denominator.** D2 states it in full: the column becomes a fallback, the bar becomes horizon-scoped, `capacity_is_default` becomes a three-valued source. The numerator, the index, the route, the wire object and the panel's structure survive. *Owner: F40's spec. Trigger: F40 is an E8 feature and is not queued.*
3. **A fourth business statement on a five-second poll, derived and not measured.** ≈7 statements, ≈12 round trips, 3 pool checkouts per tick per device on the atelier screen (D3). It replaces rather than adds to F57's number since the console renders one section at a time, and `tenants.by_slug` is still uncached per request (*"Caching is deliberately deferred to E5"*) and is still the single cheapest lever. **F29 must be handed this number, not left to discover it.** *Owner: team. Trigger: F29's k6 pass. Recorded remedy: the `LEFT JOIN` fold in D3.*
4. **The `atelier` settings key now has two sub-keys, exactly ONE CODE PATH and NO CONCURRENCY CONTROL — and "one writer" must not be read as "one actor".** `||` merges at the top level only, so a second writer sending a partial `atelier` object would delete the key it did not name. D5 makes the request model enforce the whole-block rule and names the deep-merge expression for the day a third key arrives. **The first feature to add one (F43, F44) must join the block or deepen the merge.** ⚠ **And two shift managers with the dialog open silently lose each other's work** — full replace, unconditional UPDATE, no version, no if-match, both admitted by the shipped router gate. That is the designed behaviour (D5) and the recovery path is the audit trail, which is why D12's full-value, no-`from` payload is load-bearing rather than incidental. The blast radius is the ruler every future estimate in the boutique is cut with. *Owner: F43/F44. Trigger: any new `settings["atelier"]` key, or a pilot report of a reverted mapping.*
5. **The assign `Select`'s option order now changes as work moves.** F41's alphabetical order never did. Three things bound it — a deterministic tiebreak, the shipped pointer hold (`"held"`), and mutation suppression — leaving one window: a keyboard user with the listbox open while a colleague's write lands. Accepted rather than engineered around; the mitigation if a pilot reports it is freezing the order for a card that has a draft. *Owner: team. Trigger: pilot feedback.*
6. **A boutique whose owner sews still cannot be given hours or a ticket.** D6 refuses a non-seamstress target for the same reason F41's D9 refuses a non-seamstress assignee, and F42 declines both of F41's recorded remedies (§Conflicts 10). **This is a real ceiling for a two-person boutique and it is not hypothetical in a pilot**: she must hold a `seamstress` account and give up owner-only access to staff CRUD, terms and the gateway, or leave her own work unassigned and invisible to every bar. *Owner: user, then whoever builds multi-role staff. Trigger: the first tenant with fewer than three staff.*
7. **The band mapping's audit row is written in its own transaction, and `profile`/`toggles` remain unaudited.** A crash between the merge and the audit loses a row and can never invent one (D12), and the shipped gap for the other two keys is inherited rather than widened — which means `deposits_enabled` is still changed by nobody-knows-who. *Owner: team. Trigger: a second `merge_settings` caller needing atomicity, or F53's activity log.*
8. **The audit rows are still write-only.** Two more actions nothing renders, and `ATELIER_SETTINGS_UPDATED` is the only place the previous band mapping survives — the fact you need to explain an old ticket's estimate, readable only through `psql` (F15's Risk 7, inherited by F34, F51, F57, F41 and now this). *Owner: user. Trigger: pilot feedback, or F53's activity log.*
9. **A retired seamstress with live tickets is visible, has a load, has a bar and cannot be edited.** F41's Risk 12 handed this here and F42 makes it *more* legible rather than correct: her row now carries a number, so the work she is holding is quantified and the manager knows what reassigning costs. The correcting sweep on every staff write stays unbought, and the ceiling — her capacity is whatever resolved before she was retired — is stated. *Owner: team. Trigger: the first offboarding in a pilot with an open board.*
10. **`weekly_capacity_hours` is personal-adjacent data on `staff_users`.** It is a scheduling fact her colleagues already know from the rota, and it is **not** a new record class — `staff_users` is already in whatever retention F20 assigns it, and pre-decided #34/#35's offboarding scrub blanks personal fields on that row. **No new F20 entry is created and none is needed**, and this line exists so that conclusion is recorded rather than assumed. *Owner: F20/F21 confirm at the audit.*
11. **No E2E covers the poll loop, and the panel now rides it.** Three loops in the console, all unit-tested with fake timers against a mocked `api`, none exercised against a real backend. F34's Risk 8, widened again. *Owner: team. Trigger: the `/manage/**` interception harness.*
12. **The panel is the fifth surface on one screen and the atelier section is now ~2 000 lines across two files.** Nothing is broken by that today; it is recorded because F40 replaces the panel wholesale and the seam between `AtelierSection` (state, polling, writes) and `SeamstressPanel` (rendering, dialogs) is what makes that a replacement rather than a rewrite. *Owner: F40.*

---

## Decisions Log

- **D1 — One migration: `staff_users.weekly_capacity_hours INTEGER` nullable with no default, a named `CHECK (>= 0 AND <= 168)`, and the partial index F41 reserved for this feature by name.** Nullable-with-no-default because NULL is a real state (D2) and because it is the one `ADD COLUMN` form Postgres does as metadata only. 0 is legal — "she is not available this week" is a thing the product should be able to say. 168 is a typo fence in `effort_minutes CHECK (… <= 1440)`'s spirit. **No RLS work, no `GRANT`, no trigger** — both tables already carry theirs, and `test_every_tenant_id_table_has_forced_rls` would not catch a mistake here because there is no new table for it to find. Declined `weekly_capacity_minutes` (the human types hours) and a `staff_capacity` table (a second tenant table for one nullable fact). **The ORM model is the second half and is not optional — no model↔migration parity test exists anywhere in `Backend/tests/`.** The revision id is resolved from `alembic heads` immediately before the rebase, made the last commit, and verified to leave exactly one head; `main` is at `0021` and F37 is in flight.
- **D2 — The tenant default lives at `tenants.settings["atelier"]["default_weekly_capacity_hours"]`; resolution is `resolve_capacity`, REAL CODE branching on `is not None` and NEVER on truthiness; and THE PLATFORM SHIPS NO DEFAULT NUMBER.** `0` is a deliberate value ("away this week", D1) and an `or` would hand her the boutique default, print «ברירת מחדל של הבוטיק» on a number she set, and sort her FIRST in the assign `Select`. The same rule binds every client fold: `weekly_capacity_hours === null`, never falsiness, because `null` and `0` demand opposite renderings. Both directions are named mutations. The asymmetry with `effort_bands`' five platform defaults is deliberate and is two arguments: `effort_minutes` is `NOT NULL` so band resolution must always answer, while capacity is nullable and "unknown" is representable; and a wrong band is bounded within five coarse presets while a wrong capacity is a **denominator** that renders every bar at a fraction of the truth in a colour that says everything is fine. **A brand-new boutique therefore sees real load in hours, no bars, «לא הוגדרה קיבולת», and a two-tap fix** — the load is true data and always renders; only the bar is withheld, because a bar without a denominator is a picture of a number that does not exist. Read off `TenantContext.settings` at zero statements, so a saved setting is live on the very next tick with no cache to bust. **F40 replaces the denominator and nothing else**, and the one thing it must not inherit is `capacity_is_default`, which becomes a source field then.
- **D3 — Load is TWO SUMS in ONE statement: `SUM(effort_minutes) FILTER (WHERE due_date <= today+7) AS due_soon_minutes` and the unfiltered `SUM(effort_minutes) AS assigned_minutes`, over `tenant_id AND deleted_at IS NULL AND delivered_at IS NULL GROUP BY assigned_staff_user_id` — computed on read, in one new uncapped repository method, as a FOURTH business statement.** **The horizon exists because `weekly_capacity_hours` is a RATE and an unfiltered backlog is a STOCK**; dividing one by the other is not a utilisation and renders every row red on day one in any boutique with a forward book. `due_soon_minutes` is the bar's numerator and the sort key's; `assigned_minutes` is LOOP-STATE's ruling verbatim, stays on the wire and is stated in words in the same row. The week is a **rolling 7 days from `today_jerusalem`**, never Sunday-anchored (a calendar anchor would need the denominator pro-rated by day-of-week, which is F40's projection). Overdue rows are inside the horizon by arithmetic. §Conflicts 13 records the divergence from the ruling's literal formula and names the one-line reversal. *"Not yet delivered" is `delivered_at IS NULL` — ONE COLUMN*, never `stage != 'delivered'`: `stage` is derived in Python by `stage_of` and has no SQL expression, so re-deriving it in SQL would be a second copy of the state machine in a second language. No stamp predicate at all — a ticket at `intake` counts in full, because a seamstress holding ten un-started jobs is not free. The NULL group is kept as the unassigned pile. Compute-on-read is the house pattern and the argument is stronger here than for `overdue`: a stored total would need eight writers to maintain, each a place to forget it and each needing its own predicate not to race the other seven. **Declined the `LEFT JOIN` fold into `assignees()`** (it holds three statements but can never carry the NULL group, and it rewrites the one shipped query standing between a re-roled seamstress and an invisible bucket) — recorded as the optimisation if F29 says so. **Declined the free Python fold over the board's ticket list**: `BOARD_TICKET_LIMIT` would make it silently under-count in exactly the boutique that is overloaded, and a bar that understates load is worse than no bar. The uncapped aggregate is why a truncated board still has exact bars, and a mutation pins it.
- **D4 — A band re-tune changes NOTHING about tickets already stamped, and it cannot, because there is no band on the ticket to re-resolve.** `alteration_tickets` stores minutes and has no `effort_band` column, deliberately — the E9 brief's own sentence, in `0020`'s DDL comment and the model's. A save changes only what new tickets get, what the dialogs offer, and how an old card **renders** (`bandLabel`'s «{{minutes}} דק׳» fallback, which becomes reachable the day this ships). **The load bar after a re-tune is a sum of minutes valued under two mappings, and that is correct and left alone** — stated so nobody normalises it. Declined re-valuing live tickets on save (a write across the tenant with no per-ticket human decision, moving every bar on form submit, with an audit shape nobody has designed) and declined offering it as a checkbox (same write, destructive default, nobody reads it). The remedy that exists is «עריכה» on a card: one ticket, one decision, one audit row.
- **D5 — The editor rides the shipped `PUT /manage/settings` with a new `atelier` block, SEVEN edits across four files (the seventh threads an `actor` for D12's audit row), the request model enforces a WHOLE-BLOCK replace, and every numeric field is `StrictInt`.** ⚠ **`ForbidExtraModel` is `extra="forbid"` and NOTHING ELSE** (`app/schemas.py:13-19`), so plain `dict[str, int]` coerces `true` → `1` and `"300"` → `300` **before** any validator runs, which would make the anti-`bool` rule unreachable code and let `{"half_day": true}` be a 200 writing a one-minute band. `StrictInt` moves the type refusal into the model, where it runs first; `validate_atelier_settings` keeps only the five-key set equality and the ranges. ⚠ **`MAX_WEEKLY_CAPACITY_HOURS` has ONE home and it is `app/atelier/stages.py`** — the same module and the same already-argued acyclic import edge as `MAX_BAND_MINUTES`. ⚠ **Two shift managers editing the block lose each other's work silently, and that is the designed behaviour** (D6's voice, one code path and no concurrency control); the recovery path is the audit trail, which is what makes D12's full-value, no-`from` payload load-bearing. A save on a brand-new boutique freezes the five platform bands — intended. `merge_settings`' single atomic `settings || :patch::jsonb` is what makes the **top level** unclobberable and no new code buys it — but **`||` is a SHALLOW merge**, so a partial `atelier` patch replaces the whole key and deletes what it did not name. The fix is one writer that always sends both sub-keys, made structural by `AtelierSettingsUpdate` having no default on either field (`UpdateAppointmentTypeRequest`'s full-replace rule, and `AssignTicketRequest`'s "null is a value, not an omission" for the nullable one). **`jsonb_set('{atelier,effort_bands}', …, true)` is named as the wrong reach**: it silently returns the settings unchanged when the intermediate key is absent, which is every tenant on day one. Validation: exactly the five band keys as a set equality (the read side's per-band fallback is a backstop against a hand-edited blob, not an API contract), each an `int` (never `bool` — the `int`-subclass trap `stages.py` already records) in `1..1440`, the default `None` or `0..168`, and bands need not be distinct or increasing. Declined a new `POST /manage/atelier/settings` (two writers on one JSONB key, reintroducing the clobber) and the owner-only staff router (a shift manager must be able to tune the ruler she balances with).
- **D6 — Per-seamstress hours get their own atelier route, `POST /manage/atelier/seamstresses/{staff_user_id}/capacity`, tightened per-route to owner and shift_manager — `delete`'s shape exactly — answering a `SeamstressCapacityResponse` that carries CAPACITY FACTS ONLY.** ⚠ **It does not answer a `SeamstressRef`**: that model requires both load numbers, this write path has no aggregate, and the only reachable value is zero — which would collapse her bar and drop her «עומס יתר» word for five seconds at the exact moment a manager is looking at it. The console patches only the response's keys onto the held row. ⚠ **All four ordinary refusals are ONE 400**: `_require_seamstress` raises `AtelierValidationError` when the row is missing **or** not a seamstress, and `by_id` already filters `tenant_id` and `deleted_at IS NULL`, so an unknown id, a retired staffer, a foreign tenant's id and a live receptionist are byte-identical — **there is no 404 on this route** outside the check-to-UPDATE race. ⚠ **The UPDATE does NOT set `updated_at`** — the trigger owns it and the house rule is in `staff_users.py:103-104`. A seamstress may not set her own hours: F41 already drew this line twice, letting her record work and refusing her a scheduling decision, and her weekly hours are the denominator every other bar is read against. Refused in the ROUTE and not the service because, uniquely among the atelier's rules, this one depends on nothing but the role. The target must be a live seamstress (`_require_seamstress` verbatim), which means a re-roled assignee's hours cannot be set — correct, and rendered as an absent control rather than one the server always refuses. **Last write wins, no 409** — F41's D9's elevated-assign argument. **It answers through the shipped `StaffUsersRepository._refreshed` and that is not optional**: the service loads the row first, so ORM-enabled DML's `evaluate` synchronization would otherwise render this caller's intent; the `before` value is captured into a local before the write for the same reason; both are named mutations. Declined `PATCH /manage/staff/{staff_id}` (owner-only router, `_STAFF_LOCK` serialising for an invariant capacity does not have, and a workroom fact behind account administration) and a bulk map write (partial failure has no honest answer).
- **D7 — `SeamstressRef` gains `weekly_capacity_hours` (resolved), `capacity_is_default`, `assigned_minutes` and `due_soon_minutes`; the envelope gains `unassigned_minutes` and `default_weekly_capacity_hours`. `AtelierTicket` gains NOTHING.** Four fields and not F41's predicted two, because the resolved number and her own column are different facts the panel and the editor must tell apart. The fold stays a total function of its arguments with no I/O, which is what keeps `test_atelier_board.py` in the fast suite, and it re-sorts nothing. `assignable` keeps its shipped derivation, so a retired assignee ships with a real load and a false flag — the anomalous bucket F41 handed here, now carrying a number. Declined capacity on the ticket (a fact about ten people repeated on 500 objects every five seconds) and a second endpoint (F41's D12: *"nobody adds a third loop"*).
- **D8 — The surface is a LIST, not a matrix, and therefore keyboard-navigable by construction.** The epic's "capacity matrix" is two-dimensional and the second dimension is the roster projection this run drops; with a flat weekly number there is one value per person. **No `role="grid"`, no roving tabindex, no arrow-key manager** — the same structural move F41's D16 made for drag-and-drop. Structure is F41's shipped column structure verbatim: a NAMED `<section>` with a `tabIndex={-1}` `<h3>` and a NAMED `<ul>` carrying `tabIndex={0}` because it is a bounded overflow container and axe's `scrollable-region-focusable` fires on exactly that. Bounded at **every** width, unlike the ticket columns, because twenty rows above the board would push the rail off a phone. **No disclosure and no `<details>`**: the panel is the feature, a collapsed feature is one nobody sees, and `<details>` would be this codebase's first, bringing three unknowns to save three lines — plus React's controlled-`open` trap, which would reopen the panel under the user's hand on every tick. Its own component file, presentational with callback writes, because F40 replaces it wholesale. ⚠ **Both write controls are gated on `ELEVATED.has(role)`** — the router admits a seamstress to the board, both write routes refuse her, and `runMutation`'s `poll.fail` makes a 403 **terminal**, so an ungated control would replace her entire board with «אין הרשאה». ⚠ **The panel reports its dialog state up through `onDialogOpenChange`** so C7's deferred terminal keeps covering all four dialogs. ⚠ **The `<ul>` takes the UNCOUNTED `atelier.capacity.heading`** (a name must not churn every tick) and the **unassigned total is a `<p>` outside the list**, so the announced item count and the heading's number are the same fact. The panel renders in the zero-ticket `EmptyState` branch too, where the rail does not exist.
- **D9 — The bar carries NO role, NO value and NO name; it is `aria-hidden` decoration, and the row's TEXT is the entire accessibility payload. Its markup is `DashboardSection`'s shipped `Bar` verbatim — `inlineSize` NEVER `width` (a logical property, so in RTL the fill grows from the inline-start edge), `bg-gold-strong`/`bg-danger` on a `bg-border` track, clamp plus `Number.isFinite`.** ⚠ `bg-accent` **does not exist** in `theme.css`'s `@theme` block, emits no Tailwind 4 utility, and would leave this feature's headline widget invisible in its normal state. Contrast is named (2.84:1 and 5.07:1) and WCAG 1.4.11 is argued not to bind, because the bar is `aria-hidden` decoration whose every value is text in the same row. `role="progressbar"` is refused on meaning (nothing is progressing toward completion) and on duplication (its honest form needs an `aria-valuetext` byte-identical to the visible sentence, putting one fact in the tree twice — and hiding the sentence to fix that makes visible and announced content diverge, the WCAG 2.5.3 failure). `role="meter"` is semantically right and refused on **support**, not meaning — recorded as the role to revisit if the repo's a11y bar moves to ARIA 1.2 with measured AT support. **Overload is `due_soon_minutes > weekly_capacity_hours * 60` — one predicate in one place**, driving the colour AND the word together, which is what makes "never colour-only" structural rather than a rule to remember. It has **three** consumers, not four: the bar's colour, the row's word, and the assign cue — the panel heading counts the ROSTER, not overloads, and that claim is dropped rather than half-built. ⚠ **The cue reaches it only through `wouldOverload(row, extraMinutes)`**, so the `× 60` lives at one site and the comparison at one site; a hand-rolled cue predicate that drops the null guard computes `null * 60 = 0` and announces «עומס יתר» on every assign to an unconfigured seamstress — correct on screen, green under axe, and a legal-accessibility regression on the one channel a screen-reader user has. The bar **clamps at 100 %** (with `Number.isFinite`) and the text never does; 0 capacity with load is overload and 0 capacity with 0 load is not; a `null` capacity draws no bar at all. **`hoursFromMinutes` rounds UP (`Math.ceil`)** so the rendered load can never read equal beside «עומס יתר» — the word is computed from raw minutes and never from the rendered figure. Every edge is a unit test.
- **D10 — `sortByRemainingCapacity` sorts on the CLIENT into THREE groups: real headroom (`remaining > 0`) by remaining DESC, then no-capacity rows by `due_soon_minutes` ASC, then overloaded rows (`remaining <= 0`) by remaining DESC — known headroom beats unknown, unknown beats known overload — tiebroken by `display_name` then `id`.** Two groups would put a seamstress at 400 % **above** an unconfigured colleague holding nothing, making the first option in the control the person the panel is drawing in red, on a *balanced*-assignment surface. Nothing is hidden or disabled, so #40 holds: she is last, labelled «עומס יתר», one tap away. Client-side because `remaining` is a pure function of two wire fields, because changing `assignees()`' `ORDER BY` would reorder the payload for every consumer including F44, and because a second server ordering is a second thing to keep in step with the fold. Applied at exactly two render sites from one call; the held array keeps the server's order. **The option label carries the number, or the sort is an invisible rule** — «נועה · נותרו 6 שעות» / «· עומס יתר» / «· 6 שעות משויכות». ⚠ `<option>` takes no markup, so `isolateLtr` type-errors and `dir="ltr"` reverses the name: the numeral goes before its Hebrew unit word and never beside Latin text. Declined sorting by raw load (it ignores capacity, which is the feature) and declined hiding or disabling overloaded options (that is a block, and #40 says overload never blocks).
- **D11 — Overload flags with a bar, a word and one conditional clause on the assign cue, and there is NO server-side flag anywhere.** No write path gains a status, a refusal, a confirm or a disabled control, and no mutation response gains an advisory field — F41's Risk 9.5 predicted one and it is not needed, because the console already holds the capacity, the load and (from the full-ticket response) the ticket's own minutes. **The cue is why this is not a nicety**: F41's D17 forbids the poll from writing into the announced region, so without the clause a screen-reader user would get **nothing** on the one action that causes overload while a sighted user watches the bar turn red. The console computing a domain fact is legitimate here precisely because it is **not a control** — nothing is refused, nothing is stored, and the next tick replaces the estimate with the server's numbers. Declined a toast.
- **D12 — Two `AuditAction` members, no migration (`audit_log.action` is plain TEXT — the eighth block).** `ATELIER_CAPACITY_SET` carries `from`/`to` captured before the write, and a no-op writes nothing. `ATELIER_SETTINGS_UPDATED` carries the **new value and no `from`**, because the trail is the history and computing a diff needs exactly the read-modify-write `merge_settings`' single atomic statement exists to avoid — and because the row's whole value is answering what a band was worth when a ticket was estimated, which needs the numbers. ⚠ **It is written in its own transaction, after a successful merge**, because `TenantsRepository` opens its own session per method and nothing can join it; the compromise is one-directional (a crash loses a row, never invents one) and the ordering is a named test. Upgrade path: an optional `session` parameter the day a second caller needs atomicity.
- **D13 — Zero new error codes, and `SPEC_ERROR_CODES`' set-equality is the proof.** There is no overload error, no capacity conflict and no 409 in this feature, which is what "flags, never blocks" means at the wire. A seamstress on the capacity route gets the **same generic 403 body** an unadmitted role gets, so a probe learns nothing.
- **D14 — Both writes are PANEL-level `Modal`s (C6 forbids the `<li>` and nothing further), so native `<dialog>` restores focus by itself; the one case it cannot serve gets a one-line `activeElement === document.body` fallback onto the panel `<h3>` — OWNED BY `SeamstressPanel`, which holds both the trigger and the heading ref — run from a `useEffect` keyed on a monotonic save counter after an `await`ed callback resolves `true`. BOTH directions are pinned.** The owner and the turn are named rather than implied because *"the paint that follows"* is not a mechanism and F41's post-mortem measured the local/CI difference at exactly one event-loop turn. `AtelierSection` supplies the awaitable callback and touches **no** focus code for this feature. F41's `restoreRef`/`captureFocus`/`boardCommit` machinery is **not touched, generalised or extended** — any edit to it is a review stop. The fallback needs no commit stamp and adding one would be machinery for a race this shape does not have: F41's mechanism fires on **poll repaints**, which arrive with no user action and can outlive her own focus move, while this fires only on a successful save, in the same turn, and only when focus is already nowhere. The bug class has shipped five times and axe walked past all five, so the tests assert `document.activeElement` **is** the expected node, and a second test pins the **steal** direction — a user who moved focus herself is not yanked back.
- **D15 — New keys under `atelier.capacity.*` and `atelier.settings.*` in both locales, and the shipped fold already covers them.** `HE_F41` selects by **prefix** and is spread into `HE`, so every new key is already inside the `ar` parity guard, both register guards and the empty-`ar` guard. ⚠ **A second `HE_F42 = entries(…startsWith("atelier."))` spread into `HE` would double-count the union** — silently and greenly — so F42's block is **derived from `HE_F41` by filter and spread nowhere**. Two aria pairs carry the WCAG 2.5.3 label-in-name containment and it is asserted, not trusted. The `/נשלח|תישלח|בדרך/` guard is cleared by construction — **nothing in F42 notifies anybody**, and «נודיע לתופרת» on an overload cue would be a lie as well as a red. No new formatter; `he.ts`'s stale *"95 keys"* header is corrected in passing.
- **D16 — `ATELIER_CAPACITY` joins `ATELIER_OPEN` and is split out of the seamstress's `NON_ELEVATED_REACH` row via a new `ATELIER_ELEVATED` set, `ATELIER_DELETE`'s shape exactly.** The walker classifies on `frozenset.intersection(*role_sets)`, so a tightened route's effective set excludes the seamstress and a row naming it would **red a correct build on the test F57's Risk 1 declares untouchable** — the exact situation that gets a test relaxed. It must still be in `ATELIER_OPEN`, because a tightened route is invisible to all three per-role equalities and the anti-vacuity half is the only thing that would notice its deletion. The classifier stays `intersection`, never `any(...)`. `OWNER_ONLY`, `test_gate_admits_listed_roles` and `test_gates_admit_only_known_roles` need zero edits. **`vite.config.ts` needs no edit** because the route is on the existing `atelier` segment — stated as a decision, because a route on a new segment would break only a developer's machine while production, CI and the whole suite stayed green.

---

## Rejected findings

Two of the 38 review findings were not applied as written. Both are recorded here rather than silently dropped; in each case the finding's *defect* was real and is fixed, and only its *recommended remedy* is refused.

1. **"Put `MAX_WEEKLY_CAPACITY_HOURS` in `app/atelier/validation.py`."** — *(the MINOR "two homes one section apart" finding)*

   **The defect is applied**: D2 and D5 gave the constant two different home modules under a heading arguing one magnitude has one place, and D5 now names `app/atelier/stages.py` alone.

   **The recommended module is refused.** `atelier/validation.py`'s docstring does declare itself the home of the atelier's pure domain bounds, which is the finding's argument — but D5 already imports `MAX_BAND_MINUTES` from `atelier/stages.py` and has already argued that edge acyclic (`atelier.stages` imports only `app.models`, `stages.py:16-17`). Taking `validation.py` would buy a **second** import edge from `boutique.validation`, and that one is genuinely heavier: `atelier/validation.py:13-20` pulls in `app.booking.validation` and `app.catalog.validation`. One magnitude, one place, **and one import edge** — `stages.py`, beside `default_capacity_hours`, which is its only other reader.

   *(The finding's second half — that D5's no-cycle sentence was written for the wrong edge — dissolves under this resolution: with `stages.py` chosen, the sentence describes the edge actually taken.)*

2. **"Drop the settings dialog's envelope prefill and read `GET /manage/settings` on open."** — *(part of the MAJOR lost-update finding)*

   **The defect is applied**: D5 now states the two-manager lost update explicitly, names the audit trail as the recovery path, amends Risk 4 so "one writer" cannot be read as "one actor", and adds the two-sequential-saves test.

   **The extra read is refused.** The finding's argument is that the envelope is up to one poll tick old, so the dialog opens on data already 5 seconds behind. True — and it buys **five seconds** off a window whose real length is however long the dialog stays open, which is minutes. The stale-prefill risk and the concurrent-edit risk are the same risk, and a read on open shortens it by well under 1 %. Paying a route round trip for that is the kind of mitigation that looks like diligence and measures as noise. The envelope prefill stays, the window is stated honestly in D5 and Risk 4, and **the mechanism that actually recovers a lost mapping is the audit row**, which now carries the actor as well as the full value.

   *If a pilot reports a reverted band mapping, the remedy is a version field and a 409 — not a read on open.*
