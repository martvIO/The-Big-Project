# Epic: E9 — Alterations Workshop & Capacity

**Created**: 2026-07-30
**Status**: planning — container only, same rule E5 records: no E9 feature gets a spec until its turn arrives, feature by feature, through the standing `/spartan:spec` → `/spartan:plan` → `/spartan:build` pipeline. E9 is the deepest feature block in the program: it sits behind E5, E7 and E8 (roadmap program order) and names **nine upstream F-numbers, five of which do not exist yet** (F31, F32, F34, F40 are unwritten; F24 is unwritten). Defining it now records the interview decisions that already bind it — above all Q13, which fixes the unit of workload and therefore the shape of the whole epic.
**Numbering**: global scheme **F41–F44**. The roadmap's four E9 bullets map one-to-one onto them — no split, no merge, no renumber.
**Owner**: team
**PRD**: §11.1 (job intake + lifecycle), §11.2 (capacity, bride-date priority, manual reallocation), §11.4 (workshop board + throughput analytics)

> **AMENDED 2026-07-31 — the floor-management program.** `LOOP-STATE.md`'s `rulings_2026_07_31` and its `queue:` notes GOVERN this file wherever the two disagree. **F41 and F42 are pulled forward** out of E9's dependency position and build now. Three amendments: the five states are relabelled **intake → in_progress → qc → ready → delivered** (E9 had no QC state; **pre-decided #39's mechanism is untouched** — five nullable `TIMESTAMPTZ` columns, no status enum, no event table); the date key is **`due_date`**, subsuming `wedding_date`, because an evening gown has no wedding; and **F42 ships a simplified capacity model** — `weekly_capacity_hours` per seamstress, load = sum of effort over undelivered tickets, bar red when over — with its **F40 roster dependency dropped**, since F40 is an E8 feature nowhere near being built. The F40 projection stays the recorded upgrade path, which this epic's own degradation clause already anticipated. **F42's design gate is self-approved** for this run. Q13's five effort bands and pre-decided #40's advisory-only rule are unchanged.

---

## Why

Alterations are where the boutique's promise is actually kept or broken. The dress is chosen, the deposit is taken, the bride goes home happy — and then the garment has to fit, by a date that cannot move. Every other epic ships a surface the owner can work around by hand; a garment that is not ready on Thursday for a Sunday wedding has no workaround at all.

**Q13 is the defining decision and it is why this epic has a capacity model instead of a job list with a colour on it.** Workload is measured in **hours, tapped from preset bands** (30 min / 1h / 2h / half-day / full-day) and each seamstress carries an hourly capacity. Only a time unit can be subtracted from a wedding date. That single choice converts "this will not be ready in time" from a seamstress's hunch into a computable claim, and everything else in E9 is scaffolding around that arithmetic: **F41** produces the estimates and the timestamps, **F42** does the subtraction and shows the human where to intervene, **F43** puts the bride's fittings on the same slot engine the storefront already uses rather than a second scheduler, **F44** makes the state visible on the shop floor and reports whether the estimates were ever true.

Enforcement stays **advisory** (pre-decided #40): the system flags conflicts and ranks the queue by wedding date, and every reassign / split / expedite remains a human click. Reallocating a garment is a staffing call the platform cannot make — it has no view of skill, sick days, or who is already halfway through a bodice. The system's job is to make the deadline arithmetic visible, not to make the decision.

Two identity facts are settled and shape the dependency graph (pre-decided #41): seamstresses are **E6 `staff_users` with the seamstress role** (F31 — today `StaffRole` in `app/models/constants.py` declares only `owner`, reserved for E6), and daily availability comes from the **E8 published roster** (F40), not from a workshop-local calendar. So E9 depends on both E6 and E8, and cannot compute a credible "will it be ready" without them.

---

## Success Criteria

- [ ] A job is taken in against a named bride and (where relevant) a dress snapshot, carries a **wedding date** and an **effort estimate in minutes chosen from the five Q13 bands**, and moves through all five states — received → measured → in_work → ready → collected — where each state is a **nullable timestamp column on the job row** (pre-decided #39): no status enum, no event table, no second history
- [ ] Each seamstress has an hourly capacity; assigned load is summed in minutes and projected across **her rostered days from the F40 published roster**; when the projection crosses a job's wedding date the system raises an **overload conflict** and ranks the queue by wedding date ascending — and the alert never moves a job by itself (pre-decided #40)
- [ ] **Reassign / split load / expedite** are all human actions taken from the capacity matrix, each writes an `audit_log` row, and an expedite is stored explicitly (who, when) so a queue that no longer matches wedding-date order still explains itself
- [ ] A job carries **two or more fittings**, each a real booking claimed through the **F12 slot engine** and linked by `alteration_job_id` (pre-decided #39); the bride sees them in the **F24 client portal** with a per-booking `.ics` (pre-decided #17), and confirmation + reminder ride **F16** unchanged
- [ ] A live workshop board shows every job by state on the **F32 realtime substrate**, and owner throughput is **jobs completed per seamstress per week + median time-in-state**, computed as SQL over the timestamped job rows — no new tables, no BI tool (pre-decided #41)
- [ ] Every screen is Hebrew-first RTL against the existing `packages/ui` tokens, ships `ar` resource keys untranslated (Q3), and passes the axe / IS 5568 (WCAG 2.0 AA) gate — including the matrix, where conflicts must be legible without colour and the grid must be keyboard-navigable (pre-decided #38)

---

## Features

| # | Feature | Status | Spec | Plan | Depends On |
|---|---------|--------|------|------|------------|
| 41 | Ticket intake + 5-state timestamped lifecycle + effort estimate | todo | — | — | F8, F13, F31, F34, F57 |
| 42 | Seamstress capacity hours + load bars + balanced assignment | todo | — | — | F41, F57 · *F40 dep dropped, design gate self-approved 2026-07-31* |
| 43 | Multi-fitting scheduling on the E3 slot engine | todo | — | — | F12, F13, F16, F24, F41 |
| 44 | Live workshop board + owner throughput analytics | todo | — | — | F32, F41, F42 |

**Order is F41 → F42 → F43 → F44.** Pre-decided #37 titles the E9 row but spells out only E6/E7/E8, on the stated basis that intra-epic order is *forced by dependency, not preference* — and for E9 dependency yields exactly the roadmap's bullet order: nothing can be estimated before the job row exists, nothing can be reallocated before capacity exists, the board renders what the first three produce. **F43 is the one feature that can jump the queue**: it depends on F41 but not on F42, so if F42 stalls at its user-facing design gate (Q2) or on a missing F40 roster, F43 proceeds and the epic does not park. That is deliberate — pre-decided #2 caps the run at three consecutive parks, and F42 is the single most likely park in this epic.

---

## Feature Briefs

### Feature 41: Job intake + 5-state timestamped lifecycle + effort estimate (M)

**In**: a tenant-scoped `alteration_jobs` table — `tenant_id`, RLS forced, TEXT not VARCHAR, `deleted_at` soft delete, partial index on active rows, and **new probes in F3's permanent cross-tenant isolation suite** (a new tenant table without them is a hole in the crown jewels). The row binds a customer (F13's `(tenant, phone)` record), an optional dress snapshot (`dress_id` plus `dress_name` / `dress_size` copied at intake, the same snapshot discipline `bookings` already uses so a renamed or archived dress cannot rewrite history), a **`wedding_date`** — the priority key the whole epic subtracts from — an optional `assigned_staff_user_id` (an F31 `staff_users` row with the seamstress role, per pre-decided #41), free-text notes, and the **five nullable timestamps** `received_at / measured_at / in_work_at / ready_at / collected_at` (pre-decided #39). Advancing a state stamps its column; the write path is idempotent and a correction is an explicit re-stamp, audited via the existing `audit_log`.

**Effort**: stored as `effort_minutes INTEGER`, resolved at intake from the five Q13 bands. The band → minutes mapping lives in **one tenant-settings block with platform defaults** (30 / 60 / 120 / 240 / 480) rather than hardcoded, because "half-day" is not 240 minutes in a boutique whose shifts are six hours — and the **minutes are what persist**, never the band label, so a boutique that later re-tunes its bands does not silently re-value work already estimated.

**Intake surfaces**: `/manage` for the owner, and from the E7/E6 in-store context — the staff↔client assignment record F34's dispatch produces (pre-decided #28 names E9 as one of its two consumers) is what lets a seamstress open a job on the bride she is standing with instead of retyping her.

**Out**: capacity, alerts and reallocation (F42); fitting appointments (F43); the board and analytics (F44); a status enum or an event table (both explicitly rejected by #39); alterations **pricing, invoicing or ILS amounts of any kind** — nothing in the roadmap or PRD asks the workshop to charge, and adding money here would drag the epic into E4's spec-gate exception (Q1); photo attachments on a job; automatic effort estimation.

**Noted, not depended on**: where **F28**'s date-bound rental reservation exists for the dress, the job's wedding date should be read from it rather than typed twice — same date, two sources is a divergence waiting to happen. Sale and made-to-order jobs have no reservation, so this is a soft link resolved at spec time, not a dependency.

### Feature 42: Seamstress capacity model, deadline-aware overload alerts, manual reallocation matrix (L)

This is the epic's core and **the one feature the interview names as a novel interaction pattern**: per **Q2, F42 does not self-approve at its design gate — it comes to the user as a clickable prototype first.** Token and contrast compliance is mechanically checkable, so a form carries no design risk; a dense capacity matrix carries all of it.

**In**: an hourly capacity per seamstress (a per-staff field with a tenant default, so a 6-hour and an 8-hour seamstress are both representable). Assigned load = SUM(`effort_minutes`) over her jobs not yet `ready_at`, projected across **her available days from the F40 published roster** — pre-decided #41 makes the roster the single source of "is she working that day", and F42 must not grow a second availability model. The overload computation is the Q13 arithmetic made concrete: walk back from each job's `wedding_date` minus a tenant-setting readiness buffer, sum her remaining capacity on rostered days before that point, and flag the job when the work does not fit. Queue ranked by wedding date ascending — the bride's date is the hard priority key.

**The matrix** is seamstresses × days, load against capacity, conflicts flagged, and exactly three human actions taken from it (pre-decided #40, wording lifted from ROADMAP E9 #2): **reassign** a job to another seamstress; **split load** — divide one job into child jobs each with its own estimate and assignee, which needs a parent/child link on `alteration_jobs`; **expedite** — lift a job above its wedding-date rank, stored as an explicit `expedited_at` + actor so a queue that no longer matches date order still explains why. Every one of the three writes an `audit_log` row.

**Out**: any automatic reassignment or load levelling; skill/competency matrices; sick days, holidays and vacation (F40's roster owns those, and duplicating them here is how the two models start disagreeing); automatic effort estimation; payroll, cost or piece-rate; per-garment task breakdown; a realtime substrate — the matrix is a computed read and refresh-on-open is enough, the live surface is F44.

**Degradation, decided here so the spec does not have to stall**: if no published roster covers a date, capacity falls back to the tenant's **opening-hours week** — the same source pre-decided #33 already seeds shift templates from. That keeps F42 buildable and honest if E8 lands late, and it is one query, not a second model.

### Feature 43: Multi-fitting scheduling on the E3 slot engine (M)

**In**: alteration fittings are **ordinary bookings** through the F12 slot engine, per pre-decided #39 — no second scheduler, and none of `slots.py`'s hard-won concurrency properties re-implemented. `bookings` gains a nullable **`alteration_job_id`**, which is the whole multi-fitting mechanism: two, three or five fittings on one job are simply that many booking rows carrying the same job id, and the **fitting's ordinal (first / second / final) is computed on read by ordering the job's fittings by `starts_at`, never stored** — the same call pre-decided #30 made for queue position, for the same reason: a stored ordinal has to be renumbered on every insert, which is a race for no benefit.

The bride sees her fittings in the **F24** portal's "My Bookings" and takes the per-booking **`.ics`** (pre-decided #17 — per-booking download only, no two-way sync). Comms need no new machinery: a fitting is a booking, so **F16**'s confirmation and 24h reminder already fire; if the copy must name the job, `MessageKind`'s CHECK widens by migration exactly as pre-decided #16 has offers do.

**One question F43's spec must settle, with the recommended shape recorded now**: a fitting type must not appear on the public storefront, because a fitting is booked by the boutique for a known bride, not claimed by an anonymous visitor. The recommendation is **one boolean on `appointment_types`** (staff-booked only) that the storefront's public type list excludes — one column, one type model, versus the alternatives of a parallel scheduler or a shadow tenant. Not settled here; flagged so the spec does not rediscover it.

Scheduling a fitting after the wedding-date deadline **warns and does not block** — advisory per #40; the boutique occasionally has a reason and the platform does not get to be certain it is wrong.

**Out**: a separate fittings table; a second scheduler; two-way calendar sync (dropped by recorded stakeholder decision); auto-proposing fitting dates — the human picks; waitlist / offer cascade on fitting slots (F22/F23 exist for storefront demand, not workshop scheduling); deposits on fittings.

### Feature 44: Live workshop board + owner throughput analytics (M)

**In**: a live board of jobs in five columns matching the five states, scoped by role — a seamstress sees her own work, the owner and shift manager see the room — on **each staff member's own phone**, signed in as herself (pre-decided #27). State advances from the board reuse F41's write path; a second one would be a second chance to disagree. Ordering follows F42's wedding-date rank so the board and the matrix never tell different stories.

**Transport**: pre-decided #23 starts the E6 staff board at ~5-second refresh with no vendor and says explicitly that **E9's workshop board assumes Pusher exists by then** — so F44 is the first feature that may actually require the vendor. It does not introduce a second transport either way: the correctness model is fixed (versioned events as hints, server as truth, full refetch on reconnect or version gap, tenant-prefixed channels authorised server-side — pre-decided #25), so if Pusher is still absent when F44 is spec'd it inherits F32's refresh interval and the API shape is identical.

**Analytics** are exactly what pre-decided #41 fixes: **jobs completed per seamstress per week** and **median time-in-state**, both single SQL queries over the timestamped job rows. No metrics table, no rollup job, no BI tool. Median time-in-state is also the epic's only feedback loop on estimate quality — it is what will eventually show whether the Q13 bands match reality.

**Out**: any new metrics or rollup table; CSV/PDF export; cross-tenant or platform-level analytics; enforced WIP limits; per-seamstress scoring with pay or performance consequences; forecasting or projected-completion modelling beyond F42's deadline check.

---

## Risks

- **Consistently bad effort estimates make the alerts lie — accepted at Q13, and it is the epic's central risk.** A capacity model is only as true as its inputs, and a boutique that taps "1h" for everything gets a system confidently telling it the queue is fine. Mitigations are structural rather than clever: the bands are coarse on purpose (five values, not a minute field), enforcement is advisory so a wrong alert misinforms rather than reassigns (#40), and F44's median time-in-state is the measurement that eventually exposes drift. It only helps once data exists, so **the pilot's first weeks of alerts are unverified by construction**. Owner: the boutique owner — estimate quality is hers, and the pilot conversation should say so out loud rather than let her discover it.
- **F42's design gate is a user gate, not a self-approval (Q2), so F42 is this epic's most likely park.** Owner: the user. The sequencing above is the mitigation — F43 depends on F41 only and proceeds while the prototype waits, so a design-gate stall costs one feature, not the epic.
- **Externally dependent: the realtime vendor.** Pre-decided #23 defers the Pusher decision but records that E9's board assumes it. Standing up Pusher means an account, a bill and a channel-auth layer. Owner: the user (account + billing); the platform side is F32's. If it is not in place at F44's spec, the recorded fallback is F32's refresh interval — no new transport, no re-architecture.
- **Legally sensitive: a bride's measurements and wedding date are personal data under PPL Amendment 13, and body measurements are the most intimate data this platform will ever hold.** `alteration_jobs` must be in scope for **F20**'s retention and PII-scrub jobs from its first migration, and its retention period must be pinned at F41's spec — pre-decided #10 sets bookings at 7 years and flags every number for counsel confirmation at the F21 audit; the alterations row should be decided the same way and not silently inherit a default. Owner: the user's lawyer confirms the number, the platform only enforces the clock.
- **Ex-seamstress de-identification must not break the analytics.** Pre-decided #34/#35 retain operational history permanently but blank personal fields 7 years after last day. F41's `assigned_staff_user_id` and F44's per-seamstress queries must therefore key on the **id**, which survives the scrub, never on a name that will not — otherwise the throughput report quietly loses rows the day an offboarding scrub runs.
- **Accessibility is a legal requirement and the matrix is the hard case** (pre-decided #38, IS 5568 / WCAG 2.0 AA). A dense grid whose only conflict signal is a red cell fails colour-not-sole-indicator, and a grid that cannot be traversed by keyboard fails outright. Both are gate conditions on F42's prototype, not polish afterwards. Owner: the F42 design gate.
- **Longest dependency chain in the program.** F31, F32, F34, F40 and F24 do not exist at the time of writing, and F42 in particular is uncomputable without F40's roster. The named degradation (opening-hours-week fallback) covers a late roster; nothing covers a missing F31, so **F41 cannot start before E6's staff records land** — that is the epic's real gate, and it should be checked before E9 is picked up rather than discovered mid-spec.

---

## Notes

- Hebrew copy is out of scope for this file — briefs describe behaviour. Strings land in each feature's copy deck at its design gate, Hebrew-first with `ar` keys added untranslated (Q3, pre-decided #47: `ar` bundles on the existing i18next setup, RTL layout reused wholesale, no direction-switching logic).
- `alteration_jobs` follows the repo's DB conventions, not the Kotlin/Exposed boilerplate in `.claude/rules/`: no FK constraints (app-level integrity), TEXT not VARCHAR, TIMESTAMPTZ/UTC, `uuid_generate_v4()` PKs, soft delete via `deleted_at`, partial indexes for active rows, snake_case on the wire.
- The five-state model is a row, not a workflow engine. If a future need really wants per-transition actors or reasons, that is a decision to revisit with evidence — pre-decided #39 rejected the event table on the grounds that the timestamps already answer both metrics the epic promises.
- Downstream: nothing depends on E9. It is the last functional epic before E10's cross-cutting polish, which means a mistake here is recoverable in a follow-up PR — the opposite of the money-and-legal features Q1 holds back for the user.
