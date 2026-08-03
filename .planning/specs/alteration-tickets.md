# Spec: F41 — Atelier alteration tickets + kanban (Epic E9, floor-management program)

**Spec review**: 32 findings from 3 independent lenses · **32 applied** · **0 rejected outright**; three citation sub-claims inside one finding are rejected and recorded in **§Rejected findings** at the foot of this document. Re-verified against `main` at `18127e7` (F53 merged, head `0017`).

**Created**: 2026-08-03 · **Status**: **Gate 1: standing approval — `interview-2026-07-30.md` §Standing approvals** (Q1: only *F17, F18, F19, F20, F29, F48* stop for the user; F41 is not among them — no payments, no refunds, no privacy-law text, no billing). **Design gate: self-approved (ruling 2026-07-31)** — Interview Q2 named exactly two novel interaction patterns for this run, F34's shift board and F42's capacity matrix (`LOOP-STATE.md` `rulings_2026_07_31`), and both of those were themselves self-approved the same day. A five-column board of cards assembled from `@boutique/ui`'s shipped `Card` / `Badge` / `Button` / `Select` on F34's console shell is neither. · **Effort**: **L** — one new tenant table with RLS, a **ninth** `/manage` module with seven routes, six audit actions, four concurrency mechanisms, a new console section with its own poll loop, and the **restructuring of `test_the_floor_roles_reach_exactly_the_floor_routes`** (D10), which is the one edit in this feature that touches a test F57's Risk 1 declares untouchable.

**Depends on**: **F13** (`customers`, `CustomersRepository.upsert` / `.by_ids`, `normalize_israeli_mobile`) · **F8** (`dresses`, and `0008_bookings.py`'s snapshot discipline) · **F31** (`require_role`, `RoleGate.allowed_roles`, `test_staff_role_gating.py`'s default-deny walker) · **F34** (D4's six poll mechanisms, the `{401,403}` terminal rule, D11's live-region rule, D14's SC 2.2.2 control) · **F57** (`StaffRole.SEAMSTRESS`, `app/floor/`'s module shape, `lib/usePoll.ts`, `lib/roles.ts`, `FloorPanel.tsx` as the reference consumer).
**Feeds**: **F42** (seamstress capacity — reads five named things from this feature, enumerated in D8/D9/D12 and in Risks) · **F43** (multi-fitting scheduling — adds `bookings.alteration_ticket_id`) · **F44** (workshop board + throughput analytics — reads the five timestamp columns directly) · **F20/F21** (retention — `alteration_tickets` is an e9 record class, D1 and Risk 8).

**What F41 does *not* do.** It does not compute capacity, does not warn about overload, does not rank a queue, and does not schedule a fitting. It produces the ticket row, the five timestamps, the effort estimate and the assignment — the four things F42, F43 and F44 each read. It ships **no pricing, no ILS amount, no invoice, no photo attachment** (deliberately, per the E9 brief's Out and Interview Q1's money fence).

---

## Problem

The boutique's promise is kept or broken in the workroom, and today the product cannot describe the workroom at all.

- **There is no row for a garment being altered.** `bookings` is an appointment at an instant with a seat index (`0008_bookings.py:60-79`); a hem that takes three weeks is not an appointment. `queue_tickets` (F33, in flight) is a walk-in's place in a line, scoped to one `queue_day`. Neither can hold a due date, an effort estimate or an assignee.
- **There is no way to say who is working on what.** F57 shipped `staff_users.role = 'seamstress'` and a floor card that says whether she is on a break (`app/floor/service.py:44-52`) — and that is the *entire* extent of what the product knows about a seamstress. The role has, until now, had exactly one consumer.
- **There is no record of when a garment reached a stage.** F44's two promised metrics (jobs completed per seamstress per week, median time-in-state — pre-decided #41) are single SQL queries *over columns that do not exist*.

**And the deadline is the part that cannot be worked around.** Every other surface in this program degrades into a phone call. A dress that is not ready on Thursday for a Sunday wedding has no fallback at all, which is why the E9 brief calls this the deepest block in the program and why Q13 measures workload in minutes rather than in a colour on a card: **only a time unit can be subtracted from a date.** F41 is the feature that produces those minutes and those dates. It performs no subtraction — that is F42's — and that split is the whole reason this feature is buildable in one PR.

**What is *not* dangerous here, stated because it changes the shape of the security argument.** The ticket payload carries a customer's **name** and no phone, no address and no measurements column. It is read by three roles, two of whom already read the full booking list. The part of this document that gets argued is D10: admitting `seamstress` — a role F57's walker pins *out of everywhere except three floor routes* — to **six more routes on a ninth `/manage` module**, without that admission becoming "and then everything".

## Goal

A tenant-scoped `alteration_tickets` table with **five nullable `TIMESTAMPTZ` columns and no status enum** (pre-decided #39's mechanism, untouched), whose labels are the brief's **intake → in_progress → qc → ready → delivered** (the 2026-07-31 ATELIER ruling, which supersedes #39's five names). A ticket binds a customer, a dress snapshot, a `due_date`, an `effort_minutes` resolved from Q13's five preset bands, an optional assigned seamstress and free-text notes. Seven routes on a new `app/atelier/` module. A five-column kanban section in `apps/manage` on **its own poll endpoint and its own `usePoll` instance** (D13), fully keyboard-operable with **no drag-and-drop anywhere** (D16).

F41 ships **one migration** (one new table), **one new router**, **six `AuditAction` members**, **two new error codes**, **one new tenant table therefore one new isolation suite**, **four concurrency mechanisms each with a named mutation**, and **one restructured walker test**.

## What already exists to build on (verified against code)

- **`StaffRole.SEAMSTRESS` shipped four hours ago.** `constants.py:9-24` declares five members; `0011`'s `staff_users_role_check` was widened by F57's `0015_floor_roles.py`, and `test_the_floor_roles_migration_pins_the_widened_constraint_definition` holds the deparsed literal. F41 needs **no role work at all** — the role exists and F57's own `StaffRole` comment records that the bar for adding it (a real consumer) was met.
- **`RoleGate` fails closed and composes by INTERSECTION.** `auth/dependencies.py:40-62`; the docstring at `:44-45` is explicit and `_gate_role_sets` yields *every* gate in the dependency tree (`test_staff_role_gating.py:154-161`). A per-route gate can only narrow. That is why F41 gets its own module and cannot hang a route off `booking/owner_router.py` (D10) — the identical argument F57's D4 made, and the router docstring it produced (`app/floor/router.py:19-24`) states it in the shipped source.
- **`test_the_floor_roles_reach_exactly_the_floor_routes` is the test this feature must edit, and F57's Risk 1 forbids relaxing it.** Read the shipped body (`test_staff_role_gating.py:240-302`; `FLOOR_OPEN` is declared at `:102`): it walks every `/manage` route, computes `effective = frozenset.intersection(*role_sets)` (`:278`), and asserts (1) `admits_floor == FLOOR_OPEN`, (2) **no route admits only *some* floor roles** (`partial`), (3) `FLOOR_OPEN` names no dead route. **A router admitting `seamstress` but not `reception`/`sales_assistant` reds assertions 1 AND 2.** D10 is how F41 restructures it without weakening it — and D10's per-route `delete` tightening is why the intersection, not the union, is what the new table must be written against.
- **`app/floor/` is the shape for a small `/manage` domain module with a poll**, four days old and written to be copied: router-level gate so a later route cannot forget it (`floor/router.py:11-17`), tenant from `get_current_tenant(request)` and never `StaffContext.tenant_id` (`:31-33`), a fifth local three-line `_no_store` (`:35-37`), no rate limiter (`:39-42`), real HTTP verbs and a path parameter for the target (`:44-47`).
- **`FloorService` is the shape for the service layer**, including the two things F41 repeats verbatim: the authorization check is **each method's first statement and runs before the session is opened**, because a 403 raised after a read is an existence oracle (`floor/service.py:11-16`, and `test_floor_service.py` asserts the repository was never called); and the **capture-before-the-write** rule for any value the write destroys (`floor/service.py:108-116` — `end_break`'s `before`, with the comment naming the identity-map trap).
- **`StaffUsersRepository.start_break` / `end_break` / `_refreshed` are the conditional-write shape, with the reasoning inline** (`db/repositories/staff_users.py:121-223`): a guarded `UPDATE … RETURNING id` is the **only** honest "did I write?", and one `select(...).execution_options(populate_existing=True)` re-read is what makes the loser of a race render the *database's* answer rather than its own intent. `_refreshed`'s docstring (`:195-212`) says the flag *"is not a spare keyword to drop"* and — the sentence F41 must copy along with the code — *"It is applied **unconditionally rather than per call site**: whether a caller happened to load the row first is exactly the reasoning that has bitten this repo three times, and the flag costs one chained method."* F41 copies both, on **every** write path (D3).
- **`StaffUsersRepository.update` rewrites `role` unconditionally** (`:89-119`, the assignment at `:114`) and `soft_delete` retires a staffer. Both are F51's shipped staff CRUD and both run with no knowledge of the atelier — which is why D9's seamstress-only assignee check is a **write-time nudge and not an invariant**, and why D12's `seamstresses[]` is a union rather than a filter.
- **`0008_bookings.py` is the snapshot discipline, in the migration's own words** (`:52-57`): *"Snapshot columns (appointment_type_name, dress_name, dress_size) are copied at booking time: the owner may rename a type or archive a dress, and a booking must render as what the customer agreed to. dress_id is kept alongside so the image resolves at read time."* `bookings` carries `dress_id UUID`, `dress_name TEXT`, `dress_size TEXT`, all nullable (`models/booking.py:51-53`). F41 copies the exact three columns and the exact reasoning.
- **`bookings` does NOT snapshot the customer** — it carries `customer_id` and joins. `CustomersRepository.by_ids` exists precisely for the list case, with the reason stated: *"The owner day list's name column, in one statement rather than one per row"* (`db/repositories/customers.py:72-85`, the sentence at `:75-77`). D6 follows both.
- **`CustomersRepository.upsert` is safe only under a caller's lock**, and says so: *"Safe to call without its own lock because every caller already holds the per-tenant advisory lock for the slot claim; the partial unique index is the backstop either way"* (`db/repositories/customers.py:184-204`, the precondition at `:187-189`). **F41 is the first caller that holds no such lock** — D7.
- **F53's customer CRM is MERGED, not in flight** (PR #35, `d9f5d38`; migration `0017_customer_crm_fields.py`). `CustomersSection.tsx` and `CustomerDetail.tsx` ship, backed by `CustomersRepository.search` / `count_search` (`customers.py:115-143`) — but the whole customers router is gated `require_role(OWNER, SHIFT_MANAGER)` (`customers/router.py:76`), which is why F41 still identifies the bride by `(tenant, phone)` (D7). F53 also shipped the ruling this feature's `POST …/update` inherits: **no `updated_at` precondition, last write wins**, because it *"turns a rare recoverable overwrite into a frequent confusing 409 on a field where the loser can retype"* (`customers/service.py:6-13`).
- **The repo runs READ COMMITTED and says so in writing.** `get_engine()` sets no `isolation_level` (`db/session.py:56-60`) and `tenant_session` issues no `SET TRANSACTION ISOLATION LEVEL`, so *"every statement takes a FRESH snapshot"* (`customers/service.py:27-35`). Every conditional write in this feature — and every re-read after one — is designed against that, not against a stable read view. D3 and D4 depend on it in both directions.
- **`tenants.settings` is already on the request, and reading it again is free work.** `TenantContext` carries `settings: dict[str, Any]` (`tenancy/middleware.py:46`), bound once per request by `TenantResolutionMiddleware` from the same `tenants` row, and every `/manage` router already calls `get_current_tenant(request)`. The column is `JSONB NOT NULL DEFAULT '{}'` with two top-level keys today (`0002_tenants_app_role.py:36`, `models/tenant.py:21-23`), projected as `settings.get("profile") or {}` / `settings.get("toggles") or {}` (`boutique/service.py:85-89`). ⚠ **`TenantsRepository` cannot join a request's tenant session** — it is constructed with a `session_factory` and opens its own session inside every method (`db/repositories/tenants.py:20`, `:31-45`) — and **`merge_settings` takes only `profile=` and `toggles=` keywords** (`:69-95`), so no shipped writer can reach a third top-level key at all. D8 reads through `TenantContext.settings`; Risk 4 carries what F42 must add to write it.
- **`audit_log.action` is plain `TEXT` with no CHECK** (`0003_auth.py:71-79`) — `AuditAction` has now grown six times without a migration (F15's seven, F34's two, F51's five, F57's two, F17's eight, F19's six). F41 is the seventh such block.
- **`enable_tenant_rls(table)` is the three-statement DDL** every tenant table calls (`db/rls.py:4-19`), and `test_every_tenant_id_table_has_forced_rls` (`test_tenant_isolation.py:203-229`) walks `pg_class` for any `tenant_id` column without `relforcerowsecurity`. A new tenant table without the call is a red build, and by house rule it also gets its own `test_*_isolation.py` (there are five: booking, catalog, notifications, payments, storefront).
- **`today_jerusalem(clock=None) -> datetime.date` already exists** (`storefront/validation.py:86-94`), injectable *"so the date cutoff is unit-testable with no I/O and no dependence on the machine's TZ — the CI runner, a developer's laptop and Israel are three different calendar days for part of every day."* D5 uses it and adds nothing.
- **`usePoll` shipped with F34's two review fixes inside it, and its `run` is SYNCHRONOUS.** `Frontend/apps/manage/src/lib/usePoll.ts`: `run: (generation: number) => TickOutcome` — **not** the `Promise<TickOutcome>` F57's D10 predicted; the caller fires `void load()` and returns. `TickOutcome` is `void | "held" | "suppressed"`. The mount effect's **first** line is `runningRef.current = true` (the StrictMode-idempotence fix) and its cleanup's **first** line is `runningRef.current = false` before `clearTick()` (the unmount fix, F34's blocker). Both carry their comments. F41 imports the hook and re-derives neither.
- **`FloorPanel.tsx` is the reference consumer, 617 lines, and every hazard is commented.** The caller-owned pointer hold (`:82-88`, `:155-163`), `mutationsRef` → `"suppressed"`, the `.finally()` re-arm *in the finally and not the success path* (`:333-339`), the success-path focus restore guarded on `document.body` (`:205-218`), the **failure-path** focus move keyed on the error state rather than raised in the handler (`:220-236`), the departing-row focus rescue (`:252-266`), and the `role="status"` region the poll may never write into (`:418-429`). F41's section is the fourth consumer of this pattern and the second to carry a *destructive* mutation.
- **`test_spa_serving.py::test_the_manage_dev_proxy_names_every_manage_api_segment` derives the proxy alternation from the live route table and asserts SET EQUALITY** (`:372-403`). `MANAGE_API` in `apps/manage/vite.config.ts:18-19` currently names **thirteen** segments — `appointment-types|auth|availability|bookings|customers|dashboard|dresses|floor|gateway|settings|slots|staff|terms` — and the file's own comment at `:13-17` says *"a **fourteenth** segment added without touching this file fails there rather than silently 404ing in dev only."* `atelier` is that fourteenth. F57's shipped note records this test catching exactly this omission — *"the nastiest failure mode of the three: production, CI and the suite all stay green while only a developer's machine breaks."* D19.
- **⚠ `i18n.test.ts`'s guards all iterate `HE`, which is a HAND-ASSEMBLED UNION OF PER-FEATURE SELECTIONS** — `const HE = [...HE_F15, ...HE_F51, ...HE_F52, ...HE_F17, ...HE_F34, ...HE_F57, ...HE_F53]` (`:48`). The send-claim guard `/נשלח|תישלח|בדרך/` (`:401-402`), the no-exclamation guard (`:397-399`) and **the `ar` parity guard — which DOES exist**, `it("carries every key both features added to he.ts")` (`:417-420`) — every one of them walks `HE` and therefore silently skips any block that is declared and not spread. The file records that failure in its own words at `:33-35`: *"Folded in, not just declared: without this the resolve check, BOTH register guards and the `ar` parity guard silently skip every F52 key."* F53 asserts the fold itself (`:248-256`). **Only** the bundle-wide no-empty-`ar` test (`:406-415`) reads `ar.translation` directly and works without the fold. The label-in-name containment assertion F41 copies for its pause control is at `:337-345`.
- **`App.tsx` is a TWELVE-member `SectionKey` union plus a role-filtered `NAV` of twelve rows** (`:20-33`, `:64-109`) — F53 added `customers` between `bookings` and `board`; the in-file comment *"F57's floor — the ELEVENTH member"* (`:31`) is itself stale and will mislead. It states twice that the array is **cosmetics** and the server's `RoleGate` is the control. `reachable` is `:151`; `activeKey`'s `reachable[0]?.key ?? section` fallback (`:165-167`) lands a role that reaches one row on that row with no edit.

---

## Design

### D1 — `alteration_tickets`: every column, every CHECK, the one partial index, the RLS call

```sql
CREATE TABLE alteration_tickets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ,
    customer_id UUID NOT NULL,
    due_date DATE NOT NULL,
    effort_minutes INTEGER NOT NULL CHECK (effort_minutes > 0 AND effort_minutes <= 1440),
    assigned_staff_user_id UUID,
    dress_id UUID,
    dress_name TEXT,
    dress_size TEXT,
    notes TEXT,
    intake_at      TIMESTAMPTZ,
    in_progress_at TIMESTAMPTZ,
    qc_at          TIMESTAMPTZ,
    ready_at       TIMESTAMPTZ,
    delivered_at   TIMESTAMPTZ
)
```

Column by column, and the ones that exist for a later feature are named as such:

| Column | Why it exists | Written by |
|---|---|---|
| `customer_id UUID NOT NULL` | The bride. A pointer, **not** a snapshot — `bookings` carries `customer_id` and joins for the name, and `customers.name` is *updated* on every booking to the most recent thing she calls herself (`db/repositories/customers.py:191-192`), which is what you want on a live ticket. **No FK** (house rule, `architecture.md`); integrity is the service's. | F41's intake, via `upsert` (D7) |
| `due_date DATE NOT NULL` | **The priority key the whole epic subtracts from**, and the ATELIER ruling's replacement for E9's `wedding_date`, because an evening gown has no wedding. `DATE` and not `TIMESTAMPTZ`: it is a calendar day the bride names, not an instant — the one place `Asia/Jerusalem` is allowed to appear (D5). `NOT NULL` because F42's arithmetic is undefined without it and because "she needs it by" is the one fact every alteration has. | F41's intake and update |
| `effort_minutes INTEGER NOT NULL CHECK (…)` | Q13's unit. **Minutes persist, never the band label** — a boutique that re-tunes its bands must not silently re-value work already estimated (E9 brief). The upper bound is 1440 (one day) rather than an absurdity ceiling, because the largest band is `full_day` and a tenant-tuned mapping is still bounded by the day it names. | F41's intake and update, resolved server-side from a band key (D8) |
| `assigned_staff_user_id UUID` | The seamstress. **NULL is a real state** and the board must render it — an unassigned ticket is the thing a shift manager is looking for. Keyed on the **id**, never a name, because pre-decided #34/#35's offboarding scrub blanks personal fields and leaves the id, and F44's per-seamstress report must not quietly lose rows the day a scrub runs (E9 Risks). | F41's assign (D9) |
| `dress_id UUID` / `dress_name TEXT` / `dress_size TEXT` | **`0008_bookings.py:52-57`'s three columns and its exact reasoning** — the owner may rename or archive a dress mid-alteration and the ticket must keep rendering the garment it was opened for. All three nullable: an alteration is frequently on the bride's *own* gown, which has no catalog row (D6). | F41's intake and update |
| `notes TEXT` | Free text — «להרים 4 ס״מ, לצרף חגורה». Bounded by `MAX_TICKET_NOTES_LENGTH` (D6). ⚠ **This is the column most likely to hold body measurements**, which is the most intimate data this platform will ever carry; Risk 8 hands it to F20 by name. | F41's intake and update |
| `intake_at TIMESTAMPTZ` | Stage 1 of five. Stamped by the INSERT itself. | F41's intake |
| `in_progress_at` / `qc_at` / `ready_at` / `delivered_at` | Stages 2–5. **Five nullable timestamps, no status enum** — pre-decided #39's mechanism, which the ATELIER ruling explicitly leaves untouched while relabelling the stages. D2 is the whole argument. | F41's advance / undo |

**One index, partial, and it has one job — the board read's access path:**

```sql
CREATE INDEX idx_alteration_tickets_tenant_due
    ON alteration_tickets (tenant_id, due_date)
    WHERE deleted_at IS NULL
```

`(tenant_id, due_date)` is exactly the filter-then-sort the board read performs (D12): one tenant's live tickets, ordered by due date ascending, which is the bride-date rank pre-decided #40 fixes. The delivered-window predicate is applied over that handful.

**Declined: an index on `assigned_staff_user_id`.** F42's load query is `SUM(effort_minutes) … WHERE delivered_at IS NULL GROUP BY assigned_staff_user_id`, and **F42 has a migration of its own** (`staff_users.weekly_capacity_hours`, per its LOOP-STATE note), so it buys the index it measures — F33's rule verbatim. Shipping it now is an index with no reader.
**Declined: an index on `(tenant_id, customer_id)`.** A customer-detail panel that listed a bride's tickets would want it. F53 has now **merged** and did not add one — `0017_customer_crm_fields.py` adds `notes` and `tags` and nothing else — and F53's detail builder does not read this table, so the index still has no reader. The feature that measures the query buys the index.
**Declined: an index on any of the five timestamps.** F44's medians are one-off analytic scans over a boutique's few thousand rows.
**Declined: a `status TEXT` column beside the timestamps.** This is the decision the ruling calls non-negotiable and it is worth spelling out *why* rather than only citing it: the timestamps **are** the audit trail. `median time-in-state` (pre-decided #41) is `ready_at - in_progress_at`; a status enum answers neither metric this epic promises, and keeping both is two representations of one fact that a concurrent writer can desynchronise — F57's D2 argument against a `staff_users.status` column, in the same words.
**Declined: an `alteration_ticket_events` table.** Rejected by #39 on the stated grounds that the timestamps already answer both metrics, and it would cost a second tenant table: a policy, grants, an isolation suite, an `enable_tenant_rls` row and an F20 retention entry. `audit_log` already carries the actor for every transition (D11), which is the only thing the timestamps cannot say.
**Declined: any unique index.** Two tickets for one bride on one dress is legitimate (a gown and a going-away dress; a re-do). There is nothing here that is unique.
**Declined: `wedding_date` as a second column beside `due_date`.** The ruling says `due_date` **subsumes** it. Two date columns is a divergence waiting to happen, and the F28 rental-reservation prefill named in the ruling fills `due_date` when it arrives.

**RLS, grants and the trigger — the `0008` block verbatim:**

```python
op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON alteration_tickets TO app_user")
for statement in enable_tenant_rls("alteration_tickets"):
    op.execute(statement)
op.execute(_updated_at_trigger("alteration_tickets"))
```

No `REVOKE`-first dance: that is `terms_versions`' and `platform_audit_log`'s append-only shape (`0005:122-126`), and this table is ordinary CRUD. The `ALTER DEFAULT PRIVILEGES` in `0002` already auto-grants CRUD to `app_user` for tables created by the migration role — the explicit `GRANT` is stated anyway because `0002`'s own caveat says default privileges do not cover a table created out of band.

**The pinned literals are CAPTURED from the server, never transcribed from this document.** Postgres deparses `IN (…)` to `= ANY (ARRAY[…])`, adds `::text` casts, parenthesises predicates and schema-qualifies. F34's shipped note records that transcribing such a literal *"would have pinned nothing and reddened CI"*; F33's D2 shows the deparsed forms. `test_migrations.py` reads definitions back through `pg_get_constraintdef` and `pg_indexes.indexdef`, and F41's additions do the same — including `pg_indexes.indexdef` for the one index, which is the row that fails loudly if someone re-adds `UNIQUE`.

### D2 — The five nullable timestamps ARE the state machine, and the derivation is total

```python
class TicketStage(StrEnum):
    # NOT pinned by the DB and deliberately not: there is no stored value for a
    # CHECK to constrain. The state is DERIVED from five nullable TIMESTAMPTZ
    # columns (pre-decided #39's mechanism, relabelled by the 2026-07-31 ATELIER
    # ruling). StaffCardStatus is the shipped precedent for a derived, DB-unpinned
    # wire enum.
    #
    # DECLARATION ORDER IS THE TOTAL ORDER and D3's predicate builder reads it.
    # A member inserted in the middle changes the semantics of every advance.
    INTAKE = "intake"
    IN_PROGRESS = "in_progress"
    QC = "qc"
    READY = "ready"
    DELIVERED = "delivered"


STAGE_COLUMNS: dict[TicketStage, str] = {
    TicketStage.INTAKE: "intake_at",
    TicketStage.IN_PROGRESS: "in_progress_at",
    TicketStage.QC: "qc_at",
    TicketStage.READY: "ready_at",
    TicketStage.DELIVERED: "delivered_at",
}


def stage_of(row: AlterationTicket) -> TicketStage:
    """The RIGHTMOST stamped column, in declaration order.

    Total by construction: the fallback is INTAKE, so a row with no stamp at all
    — which the writer cannot produce, because the INSERT stamps intake_at — is
    read as intake rather than crashing a poll every five seconds. `StaffCard`'s
    `card_status` is the same shape one file over: a total function of nullable
    columns whose output set is pinned by a set-equality test.
    """
    current = TicketStage.INTAKE
    for stage in TicketStage:
        if getattr(row, STAGE_COLUMNS[stage]) is not None:
            current = stage
    return current
```

**All five columns are declared `TIMESTAMPTZ NULL`, including `intake_at`, and the ruling's word "nullable" is honoured literally.** Making `intake_at NOT NULL` would be more or less equivalent in practice and is **declined** for one reason: it would make the five columns four-plus-one in the DDL, and every later reader — F42's load query, F44's medians, a future correction path — would have to know which one is special.

**⚠ But the symmetry is a DDL symmetry only, and this document does not claim more than that.** `intake_at` is **structurally non-null and immutable**: D1 stamps it in the INSERT, D4 refuses to undo it, and no other verb writes it — so no live row the API can produce has `intake_at IS NULL`, and its value equals `created_at` to within the handler's own latency. Two consequences for the readers this feature feeds, stated here because otherwise they will be rediscovered wrongly:

- **`stage_of`'s `INTAKE` fallback is a defence against a hand-edited row, not a state the API produces.** It is total for the reason a poll must not crash, not because the writer can reach it.
- **F44 must not treat `intake_at IS NOT NULL` as evidence of anything.** Unlike the other four, where a non-NULL stamp means a stage was *separately recorded*, this one is set by construction on every row. Risk 8 already concedes the point without noticing: the one place this spec needs the intake instant for a clock, it reaches for `created_at`.

**⚠ THE RULE THIS DOCUMENT IS ASKED TO PIN: an earlier stamp that is NULL while a later one is set means *that stage was never separately recorded*, not that it did not happen.** A seamstress who takes a hem from `intake` straight to `ready` in one sitting leaves `in_progress_at` and `qc_at` NULL forever, and the ticket reads `ready`. That is the honest reading of a timestamp trail and it is the only one that survives contact with a workroom: the alternative — refusing any advance that skips a stage — would force staff to tap three buttons to record one afternoon's work, and a system that makes people lie to it gets lied to.

Three consequences, each stated so nothing downstream rediscovers them:

1. **`stage_of` reads the rightmost stamp and never the count.** Any implementation that walks forward looking for the first NULL is wrong on exactly this row.
2. **The skip is legible.** The audit row for a stage advance carries `{"from": "intake", "to": "ready"}` (D11), so a skip is a fact with an actor and a time, not an absence somebody has to infer.
3. **F44's median time-in-state must treat a NULL as "no observation", never as zero.** A ticket that skipped `qc` contributes nothing to the qc median rather than a zero-length one. Written here because F44 reads these columns directly and would otherwise divide by a denominator that includes rows it never observed. *Owner: F44.*

**Backwards is not a state the columns can express, and D3 is what enforces it.** There is no ordering constraint in the DDL — a `CHECK (in_progress_at IS NULL OR intake_at IS NOT NULL)` chain would forbid the legitimate skip above. The invariant that actually matters (a stamp is never written *behind* the current stage) is enforced by the write predicate, where it is one clause instead of ten.

### D3 — Advancing: one conditional UPDATE, four outcomes, and the race in full

```python
#   UPDATE alteration_tickets
#      SET <target>_at = :at
#    WHERE tenant_id = :t AND id = :id AND deleted_at IS NULL
#      AND <target>_at IS NULL
#      AND <every column AFTER target in TicketStage order> IS NULL
#   RETURNING id
#   -> the scalar is the ONLY honest "did I write?" (staff_users.py:157-169)
#   then ONE re-read:
#     select(AlterationTicket).where(tenant, id, deleted_at IS NULL)
#       .execution_options(populate_existing=True)
```

**The `later columns IS NULL` clause is the whole concurrency mechanism and it is doing two jobs at once.** It refuses a backwards stamp (a stale board tapping `qc` on a ticket already at `ready`) and it refuses the *loser* of a genuine race, in one predicate evaluated by the database rather than by a pre-read that another transaction can invalidate between the SELECT and the UPDATE.

`advance` returns `(outcome, row)`. **⚠ THE DISCRIMINATOR IS ONE EQUALITY AND ONE ELSE — NOT THREE ORDERED COMPARISONS.** The mapping must be total over *every* stage the re-read can show, because the UPDATE and the re-read are two statements and nothing holds a lock between them:

| Rows | Re-read | `stage_of(row)` vs target | Answer |
|---|---|---|---|
| 1 | the row | — | **200**, card rendered from it, **one audit row** with `from`/`to` |
| 0 | the row | `==` target | **200 unchanged**, no audit row — the first tapper's timestamp survives (F57's D7 idempotency, verbatim) |
| 0 | the row | **anything else** | **409 `TICKET_STAGE_CONFLICT`** — *"the ticket is not where you last saw it"* |
| 0 | `None` | — | **404 `NOT_FOUND`** — soft-deleted, another tenant's, or never existed |

**⚠ AN EARLIER STAGE ON THE RE-READ IS REACHABLE, AND AN EARLIER DRAFT OF THIS DOCUMENT CLAIMED IT WAS NOT.** The claim was that `stage_of(row) < target` with zero rows cannot happen, "because if the target column and every later column were NULL the predicate would have matched". That holds only if the UPDATE and the re-read are atomic, and they are not: a **zero-row UPDATE takes no row lock**, and this repo runs READ COMMITTED with no `isolation_level` on `get_engine()` (`customers/service.py:27-35`), so the re-read takes a **fresh snapshot**. Four ordinary steps reach it:

1. A ticket is at `qc`. Caller A taps advance → `qc` (a stale board, or a double-tap).
2. A's UPDATE evaluates `qc_at IS NULL` → false → **0 rows, no lock held**.
3. Caller B's **undo of `qc`** commits — D4 is a shipped verb of this same feature.
4. A's re-read with `populate_existing=True` sees B's commit: `qc_at` is NULL, so `stage_of(row)` is `in_progress` or `intake` — strictly **less** than A's target.

Written as `if stage == target: 200 / elif stage > target: 409` with no else, A's handler falls off the end and returns `None` — a **500 on the hottest mutation in the feature**. So: **0 rows + a live row + `stage == target` → 200; 0 rows + a live row + anything else → 409.** The 409 is honest in both directions — the ticket moved, and the next tick repaints it either way — and it is one branch instead of two. **The same shape is mandatory for D4's undo and D9's seamstress claim**, both of which have the identical hole and are stated as total; each says so in its own section.

**Why a three-valued outcome and not F57's `(bool, row)`.** F57's D7 chose a boolean because a break has no status guard, and said in as many words that *"if a later feature ever gives the break a status guard, that is the day the enum earns its keep"*. This is that day: zero rows here has **two opposite causes** (already there → 200; overtaken → 409), which is exactly F34's `CheckInOutcome` situation and exactly the reason a boolean cannot serve.

**Concurrency, stated because two people genuinely tap one card.** A shift manager taps `ready` while the seamstress taps `qc`, both from boards last painted five seconds ago:

- Whoever commits first wins. Say `ready` wins. The `qc` writer's predicate now fails on `ready_at IS NULL`, matches zero rows, re-reads, sees `ready`, and answers **409**.
- The 409 is the right answer and a 200 would be a lie. The `qc` tapper asked to record a stage the garment has already left; telling her it worked would put a `qc_at` later than `ready_at` on the row if the predicate were dropped, and would silently discard her intent if it were kept.
- Her console does not need to do anything clever: the next poll tick (≤5s, and the mutation's own `.finally()` re-arm makes it sooner) repaints the card in its real column, and the 409's copy says «הכרטיס כבר התקדם» — the event, not a duration (copy rule 5).

**⚠ THE SEAMSTRESS'S PER-TICKET RULE, AND WHY THE TWO HALVES OF IT DIFFER.** D9 governs who may set the *assignee*; this is the rule for the other three ticket verbs, and it lived only in a table column until this revision. A seamstress may:

| Verb | A seamstress may act on | Reason |
|---|---|---|
| `stage/advance`, `stage/undo` | **her own ticket, or an UNASSIGNED one** | Advancing an unassigned ticket is a seamstress **recording work she has just done**. Refusing it would force a claim-then-advance two-tap on the common case — a hem picked up off the rack — and a system that makes people take an extra step to be honest gets lied to (D2's rule, applied to authorization) |
| `update` | **her own ticket ONLY** | Editing a `due_date` or an estimate is a **scheduling decision**, not a record of work. On a ticket she does not hold it is a decision about somebody else's queue, which is a shift manager's call (#40) |
| `delete` | **never** — refused in the route table, not the service (D10) | |

Both refusals are the generic `NotAuthorizedError` body. The `update`-on-another's-ticket refusal is its own acceptance line and its own named test; it is the one that a reader of the API table alone would get wrong.

**No advisory lock.** F51's namespaced `pg_advisory_xact_lock(hashtext('staff:' || :tenant_id))` (`auth/staff.py:64`) exists because the last-owner invariant is *"at least one"*, which no single statement can express. This writes one column on one row and has a predicate that expresses its entire invariant. Taking a lock would serialise every stage advance in the boutique against every other.

**⚠ ONE `_refreshed`, AND EVERY WRITE PATH IN THIS FEATURE ANSWERS THROUGH IT — not just this one.**

```python
# AlterationTicketsRepository._refreshed(session, tenant_id, ticket_id)
#   select(AlterationTicket)
#     .where(tenant_id, id, deleted_at IS NULL)
#     .execution_options(populate_existing=True)
```

`update(AlterationTicket)` is ORM-enabled DML whose default `evaluate` synchronization stamps the SET value onto the identity-mapped instance **whatever the database matched**, and the factory is `expire_on_commit=False`. Every write in this feature has the shape that poisons, because every one of them **loads the row first**:

| Write path | Why it has already loaded the row |
|---|---|
| `stage/advance`, `stage/undo` | the previous stage for the audit row's `from`; the seamstress's authorization reads `assigned_staff_user_id` |
| `assign` (elevated) | D11 requires `{"from": "<uuid>|null", "to": …}` |
| `assign` (claim / release) | the same audit row, plus the authorization reads the current assignee |
| `update` | D11's `{"changed": [...]}` is a diff |
| `delete` | D11's `{"stage": "qc"}` is derived from the loaded row |

All six then answer **the full ticket** (D15: *"the console patches its card from the server's own row … so the console cannot disagree with itself"*), and without the flag they render **this caller's intent** rather than the database's answer — which is exactly the disagreement D15 promises is impossible. So the flag is applied **unconditionally, in one repository method**, in the shipped `_refreshed`'s own words: *"whether a caller happened to load the row first is exactly the reasoning that has bitten this repo three times, and the flag costs one chained method"* (`db/repositories/staff_users.py:195-212`). D9's elevated last-write-wins stays last-write-wins; the flag only changes **which row it renders**, never who won.

### D4 — One undo verb; it clears the rightmost stamp and the audit row carries what it destroyed

```
POST /manage/atelier/tickets/{ticket_id}/stage/undo   body: {"stage": "ready"}
```

**Why an undo exists at all**, when the epic's Out-of-scope says nothing about one: a mis-tapped `delivered` takes a wedding dress off the board with no way back, and F34 shipped `BOOKING_CHECK_IN_UNDONE` for exactly this class of finger-slip on a surface people tap fifty times a shift. The alternative correction — soft-delete and re-create — throws away the ticket's real history to fix a typo.

**The client names the stage it intends to clear**, taken from what its last poll showed. That is what makes a stale board harmless: if the ticket moved on between the paint and the tap, the predicate fails and the caller gets a 409 rather than clearing a stage that arrived after it last looked.

```
UPDATE alteration_tickets SET <stage>_at = NULL
 WHERE tenant_id AND id AND deleted_at IS NULL
   AND <stage>_at IS NOT NULL
   AND <every column AFTER stage> IS NULL
RETURNING id
```

**Same one-equality-and-one-else discriminator as D3, and for the same reason.** An earlier draft listed the zero-row branches as *"the column is already NULL → 200 no-op"* and *"a later stamp exists → 409"*, which are **not disjoint** — both are true whenever the named column is NULL *and* something later is stamped, and a builder implementing them in the order written returns 200 for a ticket that has moved on. That state needs no concurrency at all to reach, because D2 makes forward skips legal:

> A ticket is at `in_progress`. A undoes `in_progress` (→ `intake`), then advances **straight to `qc`**, skipping `in_progress` — legal and normal under D2. B's board was painted before all that and still shows `in_progress`; B taps «ביטול שלב», sending `{"stage": "in_progress"}`. The predicate `in_progress_at IS NOT NULL` fails → 0 rows. `in_progress_at` is NULL **and** `qc_at` is set. The honest answer is 409: the stage B asked to clear is not the stage the ticket is in.

So, after the re-read:

| Rows | Re-read | Condition | Answer |
|---|---|---|---|
| 1 | the row | — | **200** + one audit row carrying the destroyed stamp |
| 0 | the row | the named column is NULL **and every column after it is also NULL** | **200 no-op** — a genuine double-tap, nothing later exists |
| 0 | the row | **anything else** | **409 `TICKET_STAGE_CONFLICT`** |
| 0 | `None` | — | **404** |

The worked example above is a named fast test in `test_atelier_service.py`; it needs no database.

**`intake` cannot be undone.** Clearing `intake_at` would leave a ticket whose derived stage is `intake` anyway (D2's fallback) and whose trail says nothing happened — a lie with no upside. A 400 `VALIDATION_ERROR`; the remedy for a ticket that should not exist is the delete verb.

**The audit row carries the timestamp it destroys** — `{"stage": "ready", "previous_stamp": "2026-08-02T11:20:00Z"}`. This is F57's `previous_break_started_at` argument and F15's `old_customer_id` argument, and here it is load-bearing in a way it was not there: the five timestamps **are** the trail, so an un-stamp is the one write in this feature that destroys history, and the audit row is the only place it survives. **The value is captured into a local BEFORE the write** for the reason `floor/service.py:108-116` spells out at length — the ORM's `evaluate` synchronization stamps `NULL` onto the very instance the reader is about to read, so a capture-after-write records `null` and empties the row it exists to fill. That is a **named mutation target** (Testing).

**Declined: undoing more than one stage per call.** «Back to intake» from `delivered` is four audit rows or one lossy one. If the pilot asks, the console can call the verb repeatedly.

### D5 — `due_date` is a `DATE`; `overdue` is computed on read against `today_jerusalem`

```python
overdue = row.delivered_at is None and row.due_date < today_jerusalem(self._clock)
```

**A `DATE`, not a `TIMESTAMPTZ`.** TIMEZONE.md's rule is UTC everywhere with `Asia/Jerusalem` appearing "only where a calendar day is computed", and a due date is the canonical case: the bride says "the fourteenth", not an instant. Storing it as a timestamp would force every reader to pick a time of day and would make the same date render differently either side of midnight.

**`overdue` is computed on read and never stored.** This is the house compute-on-read pattern with three shipped precedents — pre-decided #30's queue positions, F43's fitting ordinals, and F37's read-time SOS escalation, whose LOOP-STATE note argues it best: *"the read-time predicate adds zero latency beyond the poll, cannot race, and is the house compute-on-read pattern."* A stored `is_overdue` boolean would need a worker to flip it at Jerusalem midnight, would be stale for up to a tick, and would race a concurrent delivery.

**`delivered_at IS NOT NULL` cancels overdue.** A garment delivered late is a fact about the past, not a thing to chase; the timestamps carry the lateness for F44's report.

**⚠ THE BOUNDS ARE ASYMMETRIC AND THE ASYMMETRY IS THE POINT.** D13's error table used to list an undefined *"`due_date` out of range"*, which a builder would most naturally have resolved as `due_date >= today` — and that would 400 the exact ticket the console renders a soft warning for. Pinned, in both directions:

- **NO LOWER BOUND WHATSOEVER.** A past `due_date` is accepted by the server on **create and on update**, 200, no warning field, no soft error. Pre-decided #40's advisory rule: *a dress that was due yesterday is exactly the ticket a boutique most needs to open.* The past-date warning is a **client affordance only** and there is no `min` attribute on the `<input type="date">`. **One fast test asserts a past `due_date` is a 200** — that is the assertion that stops someone resolving this the wrong way later.
- **An upper bound of `today_jerusalem(clock) + MAX_DUE_DATE_HORIZON_DAYS` (730), refused as a 400.** Not a policy about how far ahead a boutique may plan — two years is far beyond any of them — but a typo fence: `DATE` accepts year 9999, D5's `overdue` comparison and F42's forthcoming date arithmetic both consume this column unbounded, and one mistyped year poisons the board's sort and every capacity number derived from it. A named constant, like every other bound in this feature.

**The clock is injectable on the service** (`FloorService`'s and `DashboardService`'s shape — `main.py:577-582`: *"No clock wired: the parameter exists so the db suite can freeze the window, and production reads a real one"*), so the overdue boundary is unit-testable with no I/O and no dependence on the runner's TZ.

**Declined: a `due_at TIMESTAMPTZ` with a per-tenant cutoff time.** No boutique has asked what hour a dress is due, and it would put a second timezone conversion on the hottest read in the feature.

### D6 — The dress is a snapshot; the customer is a pointer

**The dress, `0008`'s three columns and its exact reasoning.** When `dress_id` is supplied at intake the service reads the dress through `DressesRepository` and copies `dresses.name` into `dress_name` — the server copies, the client does not send it, so the snapshot cannot disagree with the row it was taken from on the day it was taken. An unknown, archived or another tenant's `dress_id` is a **404** (RLS plus the explicit predicate make a foreign row indistinguishable from a missing one, by design).

When `dress_id` is **NULL** the client may send a free-text `dress_name`: an alteration is frequently on a gown the bride already owns, which has no catalog row at all. That is why all three columns are nullable and why `dress_name` has two sources. Stated explicitly because a reader will otherwise assume the client-supplied path is a mistake.

**`dress_size` is always client free text**, bounded, and is **not** validated against `dress_variants`. A seamstress records what she measured — «38, מותן מוקטן» — not a stock bucket, and `dress_variants` is documented as *"the only source of truth for stock"* (`models/dress_variant.py:11`), which is a different question.

**The customer is `customer_id` and nothing else — no snapshot, deliberately.** `bookings` does the same, and the reason is that `customers.name` only ever drifts *toward* the truth: `upsert` updates it because *"she typed it on this booking, so it is the most recent thing she calls herself"* (`db/repositories/customers.py:191-192`). A ticket that snapshotted her name at intake would keep calling her by a spelling she has since corrected. The board read resolves names through `CustomersRepository.by_ids` — one statement for the whole payload, which is what that method was written for.

**⚠ ACCEPTED, WITH ITS NOW-VISIBLE COST: intake RENAMES a returning customer.** `upsert` assigns `existing.name = name` unconditionally (`customers.py:191-199`), so a seamstress typing «מיכל» at intake for a phone stored as «מיכל לוי» silently rewrites that customer's name — and since F53 merged, that name is rendered on a screen of its own. The rule above was written from the booking path, where the bride supplies her own name; a staff member typing it at a counter is a weaker source. It is **still accepted** — one name that drifts is better than two that disagree, and the alternative is a second identity path for one person — but it is no longer invisible: the intake response echoes the resolved `customer_name`, and the Modal surfaces it beside the phone field the moment the phone parses (§Every state of every surface). No new endpoint, no new column.

**The wire carries `customer_name` and NOT `customer_phone`.** The board is read by a seamstress, and F57's narrowing rule applies: a card needs enough to know whose garment this is. There is no surface in F41 that calls a bride — that is F43's fitting booking, which rides F16's shipped comms. Recorded as a deliberate minimisation for Risk 8 and named as the first thing to add if the pilot asks.

**Validation bounds**, mirroring the shipped constants rather than inventing new magnitudes: `MAX_TICKET_NOTES_LENGTH = 500` (`MAX_BOOKING_NOTES_LENGTH`'s value and its reason, `booking/validation.py:45` — a paragraph, not a document, rendered as text and never HTML), `MAX_DRESS_LABEL_LENGTH = 200` (mirroring `MAX_DRESS_NAME_LENGTH`, `catalog/validation.py:28`), `MAX_DRESS_SIZE_LENGTH = 40`, `MAX_DUE_DATE_HORIZON_DAYS = 730` (D5). Customer name and phone at intake reuse `MAX_CUSTOMER_NAME_LENGTH = 80` (`booking/validation.py:40`) and the shipped `normalize_israeli_mobile`. **The C0-control-character rules are the booking path's two regexes, not the storefront's** — `_CONTROL_CHARS` and `_CONTROL_CHARS_EXCEPT_WS` at `booking/validation.py:69-70`, applied at `:88` (name, the whole C0 set barred) and `:93` (notes, newlines and tabs kept). The same split applies here: notes keep whitespace, every label does not.

### D7 — Intake resolves the customer through `CustomersRepository.upsert`, under a SAVEPOINT

Intake takes `customer_name` + `customer_phone`, **not** a `customer_id`. **F53's customer picker SHIPPED and is deliberately not used here** — `CustomersSection.tsx` and `CustomerDetail.tsx` are on `main`, and an earlier draft of this decision rested on their absence, which a reviewer can falsify in one `ls`. The reason that actually holds is a permission one: the whole customers router is gated `require_role(OWNER, SHIFT_MANAGER)` (`customers/router.py:76`), while D10 admits a **seamstress** to intake. A picker she could never load is not an identification path for the role that most needs one. Routing intake through it would also make a counter interaction two steps and would *still* need the upsert path for a first-time bride. So the bride at the counter is identified the way every writer in this product identifies her — by `(tenant, phone)`. A prefill from the picker for elevated callers is a later addition and costs nothing then.

**⚠ F41 is the first caller of `upsert` that holds no advisory lock, and the method's own docstring says that matters** (`db/repositories/customers.py:187-189`): *"Safe to call without its own lock because every caller already holds the per-tenant advisory lock for the slot claim; the partial unique index is the backstop either way."* `upsert` is read-then-insert; two intakes for one brand-new phone interleave into two INSERTs and the second hits `idx_customers_tenant_phone_unique`, raising an `IntegrityError` **inside an open transaction**, which in Postgres aborts the whole transaction — so the intake 500s and the ticket is lost.

The fix is five lines and is the standard one:

```python
# A SAVEPOINT, not a retry of the whole request: an IntegrityError aborts the
# enclosing transaction, so without begin_nested() the re-read below raises
# PendingRollbackError instead of running. The partial unique index is what makes
# this correct — the loser's INSERT is refused, the savepoint rolls back to the
# instant before it, and by_phone then finds the winner's committed row.
try:
    async with session.begin_nested():
        customer = await self._customers.upsert(session, tenant_id, phone=phone, name=name)
except IntegrityError:
    customer = await self._customers.by_phone(session, tenant_id, phone=phone)
    if customer is None:
        raise            # not the unique index — do not swallow an unrelated constraint
```

**Declined: taking a per-tenant advisory lock.** One line instead of five, but it serialises every atelier intake in the boutique against every other — and against F51's staff edits if it reused the `'staff:'` namespace — to protect a collision that exists only for a phone number the tenant has never seen before.
**Declined: changing `upsert` to `INSERT … ON CONFLICT DO NOTHING`.** It is shipped, it has three other callers on the booking path, and rewriting it inside this feature puts the booking flow's regression risk inside an atelier PR.
**Declined: swallowing the `IntegrityError` without the `is None` re-raise.** A different constraint failing would then present as a silent, wrong customer link.

**This is the lowest-value of the four concurrency mechanisms and it is ranked here on purpose.** If the plan has to cut scope, this is the one to cut — the ceiling is a 500 on a genuinely simultaneous first-ever intake for one bride, and the recorded remedy is the same five lines added later. The other three (D3's advance, D4's undo, D9's claim) are not cuttable: each protects a wrong *stored* value rather than a failed request.

⚠ **If it is cut, the MECHANISM AND ITS TEST ARE CUT TOGETHER.** Unlike the other three, this race cannot be reproduced by the session-ordering harness the rest of the feature uses — `upsert` is read-then-insert *inside one call*, so no ordering of two `tenant_session`s can make both miss before either inserts (Testing, race #4, states both failing orderings). The test therefore needs its own named seam, or it is green against a build with the savepoint deleted. **A green test that proves nothing is worse than no test**, so shipping the guard without that seam is not an option this document leaves open.

### D8 — `effort_minutes` persists; the five bands live in tenant settings; F41 ships no editor

```python
class EffortBand(StrEnum):
    # Q13's five, verbatim. NOT pinned by the DB: what persists is
    # alteration_tickets.effort_minutes, and a band is only ever an INPUT
    # affordance. StaffCardStatus is the precedent for a wire enum with no CHECK.
    THIRTY_MIN = "thirty_min"
    ONE_HOUR = "one_hour"
    TWO_HOURS = "two_hours"
    HALF_DAY = "half_day"
    FULL_DAY = "full_day"


DEFAULT_EFFORT_BANDS: dict[EffortBand, int] = {
    EffortBand.THIRTY_MIN: 30,
    EffortBand.ONE_HOUR: 60,
    EffortBand.TWO_HOURS: 120,
    EffortBand.HALF_DAY: 240,
    EffortBand.FULL_DAY: 480,
}
```

**The wire carries the BAND KEY; the server resolves it to minutes; the row stores minutes.** The client never sends a number. That is what makes "five preset bands, not a minute field" a structural property rather than a UI convention — there is no request shape in which 37 minutes reaches the row.

**The mapping lives at `tenants.settings["atelier"]["effort_bands"]`**, a **third top-level key** beside `profile` and `toggles`, read with the shipped `settings.get(…) or {}` idiom (`boutique/service.py:85-89`). No migration: the column is `JSONB NOT NULL DEFAULT '{}'` and has been since `0002`.

**⚠ THE READ COSTS NOTHING AND MUST NOT COST A STATEMENT.** `TenantContext.settings` is **already bound on the request** (`tenancy/middleware.py:46`) from the same `tenants` row, and every `/manage` router already calls `get_current_tenant(request)`. The bands are resolved **in the router, from `get_current_tenant(request).settings`**, and passed into the service as a plain `dict` — the way `_settings_result` consumes one. Reading the row again would be a fourth session, a fourth pool checkout and a fourth BEGIN/COMMIT on the **hottest read in the feature, every five seconds per device**, because `TenantsRepository` is constructed with a `session_factory` and opens its own session inside every method (`db/repositories/tenants.py:20`, `:31-45`) — it *cannot* join the atelier's `tenant_session`. D12's cost table is stated against the free path.

**⚠ NO SHIPPED WRITER CAN REACH THE KEY.** `merge_settings`' atomic `settings || :patch::jsonb` is the right *mechanism* — it exists precisely so *"a concurrent writer of a sibling top-level key can never be clobbered"* (`db/repositories/tenants.py:69-95`) — but it takes only `profile=` and `toggles=` keywords and builds `patch` from exactly those two, so an `atelier` key is unreachable through it today. That is a fact about F42's scope, not a gap in F41: F41 reads, and Risk 4 carries the four edits the writer costs.

**A brand-new boutique has no `atelier` key, and that is the normal case, not an error.** Resolution is per-band with a platform default, so a partial mapping is legal too:

```python
def effort_bands(settings: dict[str, Any]) -> dict[EffortBand, int]:
    stored = (settings.get("atelier") or {}).get("effort_bands") or {}
    return {
        band: _positive_int(stored.get(band.value), DEFAULT_EFFORT_BANDS[band])
        for band in EffortBand
    }
```

`_positive_int` falls back to the platform default for anything that is not a positive int within the CHECK's bound — a hand-edited JSONB blob must not be able to write a negative estimate or crash a poll. **Every tenant always has exactly five bands**, which is what lets the board render the intake form with no empty-state branch and what lets D1's `NOT NULL` hold.

**F41 ships no editor for the mapping, and F42 owns it.** The only stated reason the bands are tunable is the E9 brief's — *"'half-day' is not 240 minutes in a boutique whose shifts are six hours"* — and that sentence is about **capacity arithmetic**, which F41 does not perform. F41 records minutes; a re-tune changes nothing it computes. F42 subtracts minutes from `weekly_capacity_hours` and is therefore the feature that both needs the tuning and can test that it changed an answer. So: **F41 fixes the storage shape and the resolution rule; F42 adds a writer**, which is **four edits and not one**: a third `merge_settings` keyword, an `atelier` field on `SettingsResult` and in `_settings_result` (`boutique/service.py:85-89`, which today projects only `profile` and `toggles` back out), the `UpdateSettingsRequest` `ForbidExtraModel`'s `atelier` block, and its validator. That is a named, owned gap — Risk 4 — not an omission.

**The minutes are what persist, never the band label**, which is the E9 brief's own sentence and the reason `alteration_tickets` has no `effort_band` column: a boutique that re-tunes `half_day` from 240 to 300 must not silently re-value every ticket already estimated. The consequence is that a stored `effort_minutes` may match no current band, and the board renders it honestly (D16).

**The board payload carries the tenant's resolved bands** as a sibling of the tickets array (D12), so the console renders the five choices and the reverse lookup — minutes → the band's Hebrew word, falling back to «{{minutes}} דק׳» when nothing matches — with **zero server branches**. One field on an envelope that exists anyway.

### D9 — Assignment: two axes, an elevated last-write-wins and a seamstress conditional claim

```
POST /manage/atelier/tickets/{ticket_id}/assign   body: {"staff_user_id": "<uuid>" | null}
```

The rule, and it is F57's D6 shape with the target being a ticket rather than a person:

| Caller | May set the assignee to | Mechanism |
|---|---|---|
| `owner`, `shift_manager` | anyone, including `null` | **unconditional** `UPDATE … WHERE id AND deleted_at IS NULL` — last write wins |
| `seamstress` | **herself, on an unassigned ticket**; or `null`, **on a ticket assigned to herself** | **conditional** — the predicate is the race guard |

**Elevated assignment is deliberately last-write-wins and takes no 409.** A manager reassigning a garment is making a staffing decision with a person in front of her; a conflict dialog because a colleague touched the same ticket four seconds ago is the platform second-guessing a call pre-decided #40 says is hers. The audit row carries `from` and `to`, so a reassignment war is legible after the fact.

**The seamstress claim is where the race is, and it is real**: two seamstresses looking at the same unassigned ticket on two phones, both tapping «לקחת».

```
UPDATE alteration_tickets SET assigned_staff_user_id = :her
 WHERE tenant_id AND id AND deleted_at IS NULL AND assigned_staff_user_id IS NULL
RETURNING id
```

**Same one-equality-and-one-else discriminator as D3, and it is not optional here either.** Zero rows → re-read → **assigned to her**: **200 no-op** (a double-tap, or her own second device). **Anything else**: **409 `TICKET_ALREADY_ASSIGNED`**, and the console's copy names the colleague the next tick will show. Row gone: 404. The "anything else" explicitly includes **the re-read showing `NULL`** — a winner who claims and then releases between the loser's zero-row UPDATE and its re-read, which READ COMMITTED makes ordinary and which an `if her / elif someone-else` pair drops on the floor as a 500.

Release is the mirror — `WHERE assigned_staff_user_id = :her` — so a seamstress can drop her own claim and can never drop anybody else's. The check is **in the predicate and not only in a pre-read**, for the reason every conditional write in this repo states: a pre-read another transaction can invalidate is not a guard.

**The target must be a live `staff_users` row of this tenant holding `role = 'seamstress'`.** Anything else is a 400 `VALIDATION_ERROR`. The reason is F42-shaped and worth recording because it will read as gratuitous otherwise: F42's load bars are `SUM(effort_minutes) … GROUP BY assigned_staff_user_id` against `staff_users.weekly_capacity_hours`, a column F42 puts on seamstresses. A ticket assigned to a receptionist is work that exists and that **no load bar will ever show** — invisible, not merely unusual. The escape hatch for a boutique whose owner sews is one `<select>` in F51's shipped staff CRUD, and it is named in Risk 5.

**⚠ THE CHECK RUNS ONCE, AT ASSIGN TIME, AND IT IS A NUDGE — NOT AN INVARIANT.** Nothing re-validates it afterwards and two shipped writers break it the moment they run: `StaffUsersRepository.update` sets `row.role = role` unconditionally (`db/repositories/staff_users.py:114`) and `soft_delete` retires her. Either one leaves live, undelivered tickets pointing at a staff id that is no longer a seamstress — producing **exactly the invisible bucket the paragraph above says it prevents**, on the first role edit or offboarding. No invariant is expressible here without a re-validation this feature is not buying (a trigger, or a sweep on every role write), so the honest statement is: the check keeps the *common* mistake out of the column, and **`assigned_staff_user_id` is a point-in-time-validated pointer, never a live guarantee of role.** Two cheap consequences, both carried:

- **D12's `seamstresses[]` is a UNION, not a filter** — live seamstresses **plus** every distinct `assigned_staff_user_id` on a live undelivered ticket, each carrying `assignable: true|false`. One extra `IN` on a list the read already computes. It also makes the console's «תופרת שאינה פעילה» branch **data-driven instead of inferred from absence**.
- **Risk 9 hands F42 the obligation** to render a non-assignable/unknown-assignee bucket alongside the `NULL` one.

**The authorization check is the method's first statement and runs before any read of the ticket** (`floor/service.py:11-16`, and `test_floor_service.py` asserts the repository was never called). A seamstress probing `/tickets/<random-uuid>/assign` must not be able to distinguish "no such ticket" from "not yours" — but note the asymmetry this feature *cannot* avoid: her permission depends on the ticket's own `assigned_staff_user_id`, so the stage and assign verbs must read the row to authorize. **The generic `NotAuthorizedError` body** (`auth/dependencies.py:17-21`) is what keeps that from being an oracle: it is byte-identical to the 403 an unadmitted role gets, so the only thing a probe learns is that it is not permitted — which it already knew.

### D10 — `app/atelier/` is a new module, the gate is THREE roles, and F57's walker test must be restructured

New package `Backend/app/atelier/` with `router.py`, `schemas.py`, `service.py`, `validation.py` — the `app/floor/` shape, registered as the **ninth** `/manage` router in `create_app()` (`main.py:1070-1109` mounts eight today: `boutique`, `catalog`, `owner_booking`, `staff`, `dashboard`, `floor`, `gateway`, `customers` — F53's landed since F57) with the same include-order shadowing warning the other eight carry, and a `ROUTES` table in `tests/test_atelier_api.py` to keep it honest. **The count goes in the router docstring and in `test_atelier_api.py`'s wiring-walk comment**, both of which state it as the number it is.

```python
router = APIRouter(
    prefix="/manage",
    dependencies=[
        Depends(_no_store),
        Depends(require_role(StaffRole.OWNER, StaffRole.SHIFT_MANAGER, StaffRole.SEAMSTRESS)),
    ],
)
```

**Three roles spelled as literals, NOT `*StaffRole`.** F57's floor router is spelled from the enum because *"the set this router admits **is** 'every role the product has'"* (`floor/router.py:26-29`). The atelier's set is not: a receptionist and a sales assistant have no business in the workroom, and a sixth role added later must be refused here by default. Spelling the three is what makes that the safe direction to fail.

**Declined: admitting reception and sales_assistant.** The workroom board is not a floor surface. Reception's screen is F57's floor panel and F33's queue; nothing in the brief, the epic or the ruling puts a receptionist on a kanban. If the pilot asks, it is one literal in one gate and one `NAV` row — and Risk 1 is what makes adding it a visible act.

**⚠ THE EDIT THIS FEATURE MUST MAKE TO A TEST F57'S RISK 1 CALLS UNTOUCHABLE.** `test_the_floor_roles_reach_exactly_the_floor_routes` (`test_staff_role_gating.py:240-302`) currently asserts, over the whole `/manage` route table:

1. `admits_floor == FLOOR_OPEN` — the three floor roles reach exactly those three routes;
2. `not partial` — **no route admits only *some* of the three floor roles**;
3. `FLOOR_OPEN - seen == set()` — no dead entry.

An atelier router admitting `seamstress` and not the other two **reds assertions 1 and 2 simultaneously**, and it is *correct code failing a correct test*: the test's model is that the three floor roles move as a block, and F41 is the feature that ends that. F57's Risk 1 says the test *"must never be relaxed to a subset check"* — and a reviewer facing this red on a test declared untouchable is exactly the person most likely to relax it. So:

**The single `FLOOR_ROLES`/`FLOOR_OPEN` pair becomes a per-role table, and the assertion becomes a set equality per role.**

```python
FLOOR_OPEN = {FLOOR_READ, FLOOR_BREAK_START, FLOOR_BREAK_END}      # unchanged

# ⚠ DELETE IS SPLIT OUT, and this is not tidiness. The walker classifies on
# `effective = frozenset.intersection(*role_sets)` (:278), and delete carries a
# per-route require_role(OWNER, SHIFT_MANAGER) on top of the router gate — so its
# effective set is {owner, shift_manager} and seamstress is NOT in it. A
# NON_ELEVATED_REACH row that named delete would be one element larger than
# reality and would RED A CORRECT BUILD on the one test F57's Risk 1 declares
# untouchable, which is the exact situation that gets a test relaxed.
ATELIER_DELETE = ("POST", "/manage/atelier/tickets/{ticket_id}/delete")
ATELIER_OPEN = {
    ("GET",  "/manage/atelier/tickets"),
    ("POST", "/manage/atelier/tickets"),
    ("POST", "/manage/atelier/tickets/{ticket_id}/update"),
    ("POST", "/manage/atelier/tickets/{ticket_id}/assign"),
    ("POST", "/manage/atelier/tickets/{ticket_id}/stage/advance"),
    ("POST", "/manage/atelier/tickets/{ticket_id}/stage/undo"),
    ATELIER_DELETE,
}

# The EXHAUSTIVE reach of each non-elevated role. Set equality per role, so a
# route that admits one of them and should not still reds — and a route that
# admits seamstress ALONE no longer reds a correct build.
NON_ELEVATED_REACH: dict[str, frozenset[tuple[str, str]]] = {
    StaffRole.RECEPTION.value:       frozenset(FLOOR_OPEN),
    StaffRole.SALES_ASSISTANT.value: frozenset(FLOOR_OPEN),
    StaffRole.SEAMSTRESS.value:      frozenset(FLOOR_OPEN | (ATELIER_OPEN - {ATELIER_DELETE})),
}
```

The walker keeps **intersecting** the gates (never `any(...)` — F57's D5 gives the whole argument, and F41's own `POST /delete` is precisely the shape that would red-fail under `any`), and asserts, for each of the three roles, that the set of routes whose `effective` set contains it equals its table row. **Assertion 3's anti-vacuity half is kept and widened to the FULL `FLOOR_OPEN | ATELIER_OPEN`, delete included** — delete does exist, the owner reaches it, and the point of that half is that no row of either table names a path the route table has lost.

**What this preserves, stated because the point of the restructure is that it gives nothing up:** it is still an exact set equality, still derived from the live route table, still catches a floor or atelier route that quietly *lost* its gate (an ungated route's `effective` is empty, so it drops out and the equality fails), and still fails on the day some future router copy-pastes a wide gate. What it drops is only the assumption that the three roles are interchangeable — which F41 makes false, deliberately and visibly. **Assertion 2's `partial` check does not survive as written and its intent is absorbed into the per-role equality**: "admits only some of them" is now expressible only as a row that names a route the table does not, which is assertion 1.

**Per-route tightening inside the atelier router**, so the elevated-only verbs are elevated-only in the route table and not merely in the service:

| Route | Router gate | Per-route tightening |
|---|---|---|
| `POST /manage/atelier/tickets/{ticket_id}/delete` | owner, shift_manager, seamstress | `require_role(OWNER, SHIFT_MANAGER)` — a seamstress may not remove a garment from the board |

Every other route carries the router gate alone; the finer rules (a seamstress on her own ticket, the seamstress self-claim) depend on the **ticket's** state and no `RoleGate` can express them — they are D9's and D3's service checks, exactly as F57's D6 self-toggle is.

**No rate limiter** (no `/manage` router carries one and F41 does not introduce the first). CSRF fencing covers the six POSTs by default (`csrf.py:48` gates on `request.method in MUTATING_METHODS`) and not the GET, whose protection is the session cookie and the role gate alone. **Tenant from `get_current_tenant(request)`**, never `StaffContext.tenant_id` — the third module to be told this in writing.

### D11 — Six `AuditAction` members, no migration

| Member | Value | Written when | `details` |
|---|---|---|---|
| `ATELIER_TICKET_CREATED` | `atelier_ticket_created` | intake | `{"customer_id", "due_date", "effort_minutes", "assigned_staff_user_id"}` |
| `ATELIER_TICKET_UPDATED` | `atelier_ticket_updated` | a field actually changed | `{"changed": ["due_date", "effort_minutes"]}` — key names only |
| `ATELIER_TICKET_ASSIGNED` | `atelier_ticket_assigned` | the assignee actually changed | `{"from": "<uuid>|null", "to": "<uuid>|null"}` |
| `ATELIER_TICKET_STAGE_ADVANCED` | `atelier_ticket_stage_advanced` | a stamp was written | `{"from": "intake", "to": "ready"}` |
| `ATELIER_TICKET_STAGE_UNDONE` | `atelier_ticket_stage_undone` | a stamp was cleared | `{"stage": "ready", "previous_stamp": "…Z"}` |
| `ATELIER_TICKET_DELETED` | `atelier_ticket_deleted` | a soft delete wrote | `{"stage": "qc"}` — what was lost from the board |

`actor_id = actor.id`, `entity = str(ticket_id)`, written in the same `tenant_session` as the write it describes, **before commit** (F15's D2 shape; the commit-before-raise pattern is for failure-path writes with no actor and does not apply here).

**No migration** — `audit_log.action` is plain `TEXT` with no CHECK (`0003_auth.py:71-79`), the seventh block to rely on it.

**A no-op writes no audit row.** Re-tapping a stage the ticket is already at, re-claiming a ticket she already holds, an update that changes nothing — all answer 200 and write nothing. `{ready → ready}` noise in the only trail this area has would be worse than silence (F34's D8, F57's D8).

**One `STAGE_ADVANCED` value rather than five, and the split rule is followed rather than broken.** The house rule (`constants.py`, the `BOOKING_*` block) splits an action into its own value when *"a filtered read stays one WHERE instead of a JSONB predicate"* — and the questions this table gets asked here are "who moved this ticket, and when", both of which are one `WHERE action = 'atelier_ticket_stage_advanced'` plus the row's own `details`. The question the split would serve — "how many tickets reached delivered" — is answered by pre-decided #41 from the **timestamp columns**, not from `audit_log`, which is the whole point of #39's mechanism. Five values would buy a query nobody runs.

**`ATELIER_TICKET_UPDATED`'s `details` carries changed key NAMES and not values.** `notes` may contain a bride's measurements (Risk 8) and `audit_log` is a table with a different retention clock from the row it describes; copying intimate free text into it would put the same data in two places with two deletion dates. F15's `BOOKING_PHONE_CORRECTED` carries `old_customer_id` because an *identifier* is what a security audit asks for; a paragraph of measurements is not.

### D12 — The poll endpoint, its envelope, the delivered window and the hard ceiling

```
GET /manage/atelier/tickets  ->  AtelierBoardResponse
```

One request per tick, one envelope, **and F42/F43/F44 extend it rather than adding a second loop** — F57's D11 made this rule for `/manage/floor` and the floor-program review pre-sanctioned the cost of two loops on one screen, not three.

```jsonc
{
  // An ENVELOPE, never a bare array: F42 adds capacity to `seamstresses`,
  // F43 adds fitting counts to a ticket, F44 adds nothing at all because it
  // reads the timestamp columns directly. A bare array makes the first of
  // those a breaking shape change on a screen that polls every five seconds.
  "tickets": [
    {
      "id": "0f5f…",
      "customer_name": "מיכל לוי",          // resolved via customers.by_ids; no phone (D6)
      "due_date": "2026-08-20",              // a plain calendar date, never an instant
      "overdue": false,                      // computed on read (D5), never stored
      "effort_minutes": 120,
      "assigned_staff_user_id": "9c21…",     // null = unassigned, a real state
      "dress_id": "3a70…",                   // null when the gown is the bride's own
      "dress_name": "ולנטינה",
      "dress_size": "38",
      "notes": "להרים 4 ס\"מ",
      "stage": "in_progress",                // DERIVED (D2) — the rightmost stamp
      "intake_at": "2026-08-01T08:10:00Z",
      "in_progress_at": "2026-08-02T09:00:00Z",
      "qc_at": null,                         // a NULL here with a later stamp set means
      "ready_at": null,                      //   "never separately recorded" (D2)
      "delivered_at": null
    }
  ],
  // A UNION, not a filter (D9): every LIVE staff_users row with
  // role='seamstress', PLUS every distinct assigned_staff_user_id on a live
  // undelivered ticket — because F51's staff CRUD can rewrite a role or retire
  // a staffer at any time and nothing re-validates the column. `assignable`
  // is what the assign control filters on and what makes the console's
  // «תופרת שאינה פעילה» branch data-driven instead of inferred from absence.
  // F42 adds `weekly_capacity_hours` and `assigned_minutes` to exactly these
  // objects and sorts the assign picker by remaining capacity — that is what
  // "F42 is an addition, not a rewrite" means concretely.
  "seamstresses": [
    { "id": "9c21…", "display_name": "נועה", "assignable": true },
    { "id": "4e08…", "display_name": "דנה",  "assignable": false }
  ],
  // The tenant's resolved bands (D8), so the console renders the five choices and
  // the minutes -> word reverse lookup with no server branch.
  "effort_bands": [
    { "band": "thirty_min", "minutes": 30 }, { "band": "one_hour", "minutes": 60 },
    { "band": "two_hours", "minutes": 120 }, { "band": "half_day", "minutes": 240 },
    { "band": "full_day", "minutes": 480 }
  ],
  "truncated": false                          // the ceiling was hit (see below)
}
```

**The read is: every live ticket that is not yet delivered, PLUS every ticket delivered on or after `today_jerusalem − DELIVERED_WINDOW_DAYS` (7), ordered by `due_date` ASC, capped at `BOARD_TICKET_LIMIT` (500).**

- **Why a delivered window at all.** Without one, the `delivered` column is an ever-growing archive and a 5-second poll ships a boutique's entire alteration history on every tick, forever. With it, the column is a receipt of the last week — which is what it is actually for: "did it go out?".
- **Why seven days.** One boutique week. It is a named constant, not a magic number, and its ceiling is stated: a ticket delivered eight days ago is invisible to the board and reachable only through F44's report. That is the correct trade for a live surface.
- **Why a hard limit as well.** The window bounds the delivered column but not the undelivered one — a boutique that abandons the board accumulates `intake` rows without bound, and an unbounded 5-second payload is the failure mode the client cannot recover from. 500 is far above any real workroom; `truncated: true` is on the wire so the console can say so rather than silently lying about the board. Ordering by `due_date` ASC means a truncated payload drops the **least urgent** tickets, which is the only truncation that is defensible.
- **Ordering is `due_date` ASC, `created_at` ASC, then `id` ASC**, so cards do not shuffle between ticks. **The `id` column is not decoration**: `created_at` defaults to `now()`, which in Postgres is **transaction start time** and is therefore *identical for every row inserted in one transaction* — and `test_atelier_board.py` and `test_atelier_db.py` both seed several tickets per `tenant_session` to exercise the 500 cap and the delivered window. The shipped precedent states the failure exactly: `CustomersRepository.search` orders by `name, id` because *"with `ORDER BY name` alone Postgres may return them in either order across plans — so page 1 and page 2 can show the same row and hide the other"* (`db/repositories/customers.py:122-126`). `list_live`'s single-column order (`staff_users.py:37-45`) is **not** a precedent for a unique tiebreak; it gets away with it because its tests seed one row per session. One extra column makes the truncation boundary and the vitest card order deterministic instead of plan-dependent. The primary key is also pre-decided #40's bride-date rank, so F42's matrix and this board can never tell different stories.

**Per-tick cost, derived by F34's D3 method and NOT measured** (citations: `tenancy/middleware.py:74`, `db/tenant.py:25-29`, `db/session.py:59`): 3 sessions opened (`tenants.by_slug` → `resolve_session` → the board read), 2 `set_config` + BEGIN/COMMIT, 3 `SELECT 1` pool pre-pings, and **3 business statements** in the tenant session — tickets, `customers.by_ids`, the seamstress union. ≈ 6 statements, ≈ 11 round trips, 3 pool checkouts. **The bands are NOT a fourth statement**: they come off `TenantContext.settings`, which the middleware already bound (D8), and reading them through `TenantsRepository` would open a fourth session on a five-second poll. A shift manager with the board **and** the atelier open is not a shape the console permits (one section at a time), so this replaces rather than adds to F57's number. **F29 is handed this figure in Risk 3 rather than left to discover it.**

**Declined: merging this into `/manage/floor`.** That endpoint admits all five roles; this payload carries a customer's name. It is F57's D11 security argument in the other direction, and the answer is the same — two endpoints with two admitted sets is the honest shape.
**Declined: a `?stage=` filter or per-column pagination.** The board renders five columns from one payload; five requests per tick is the thing D12 exists to prevent.
**Declined: a separate ticket-detail endpoint.** The card carries every field; a detail request would be a second round trip for data already on the client.

### D13 — Two new error codes, two new handlers

F57 shipped zero new error codes and that was right for a break toggle. F41 has two genuinely new facts, and both are **races whose remedy the console must be able to name**:

| Error | Status | Code | Raised by |
|---|---|---|---|
| `TicketStageConflictError` | 409 | `TICKET_STAGE_CONFLICT` | D3's advance, D4's undo — the ticket has moved past the stage this caller named |
| `TicketAlreadyAssignedError` | 409 | `TICKET_ALREADY_ASSIGNED` | D9's seamstress claim — a colleague got there first |

Two handlers and two `*_BODY` constants in `main.py`, the shape of the twenty already there. **They are two and not one** because the console's copy and the user's next move differ: a stage conflict says the *garment* moved on and the remedy is to look again; an assignment conflict says a *person* took it, and the next tick will name her. Collapsing them into the shipped generic `CONFLICT` code (`TERMS_CONFLICT_BODY`, `main.py:168-170`) would make the console branch on a message string.

Everything else reuses shipped machinery with **no new code and no new handler**:

| Condition | Status | Code |
|---|---|---|
| No session / expired | 401 | `NOT_AUTHENTICATED` |
| A role outside the three | 403 | `NOT_AUTHORIZED` — F31's generic body, so a probe learns nothing |
| A seamstress acting on a ticket that is not hers | 403 | `NOT_AUTHORIZED` — the **same** generic body (D9) |
| Unknown / soft-deleted / another tenant's ticket, or an unknown `dress_id` | 404 | `NOT_FOUND` — `DomainNotFoundError`, handler at `main.py:801-805` |
| Bad band key, non-seamstress assignee, notes too long, **`due_date` more than `MAX_DUE_DATE_HORIZON_DAYS` in the future** (D5 — there is **no** lower bound; a past date is a 200), undoing `intake` | 400 | `VALIDATION_ERROR` — `DomainValidationError`, handler at `main.py:795-799` |
| Repeat advance / repeat claim / no-op update | **200** | — not errors (D3, D9) |
| Mutating request from a foreign origin | 403 | `CSRF_ORIGIN_MISMATCH` — `csrf.py:15-16,48` |

`test_atelier_api.py` asserts the observed code set is **set-equal** to a `SPEC_ERROR_CODES` literal, the `test_floor_api.py:63-68` shape, so a third new code cannot arrive unnoticed.

### D14 — One migration, and the revision id is resolved at build time — never from this document

**⚠ DO NOT HARDCODE A NUMBER.** `main`'s head is **`0017_customer_crm_fields.py`** as this spec is written (F19 merged as 0016 and F53 as 0017, both 2026-08-03), and features are still in flight racing for the next free number. Any number written here is stale before the build starts — F34's D2 made this rule after exactly that. **The best statement of the hazard is `0017`'s own header comment**, which records it in current terms: *"the filenames differ, so git merges two same-revision migrations with no conflict at all, and the only symptom is alembic reporting multiple heads at runtime, far from the change that caused it. F33 is carrying `0016_queue_tickets.py` against a main whose 0016 is already taken, and will hit exactly this."*

**The rule, in the order it must be executed:**

1. **Build against `head + 1`** — read `alembic heads` on `main` at the moment the branch is cut and revise whatever it prints. Building at head+1 makes the branch **self-coherent**, so its `db`-marked tests actually run; a migration whose `down_revision` names a revision that does not exist is an outright alembic error, not a drift.
2. **Make the migration the LAST commit on the branch**, so the renumber at rebase costs **one amend to one file that nothing else references**.
3. **Re-read `alembic heads` IMMEDIATELY BEFORE the rebase that precedes the push**, and renumber `revision` / `down_revision` / the filename to whatever head then is.
4. **Verify `alembic heads` prints exactly ONE head** after the rebase. Two files claiming one revision id is a multiple-heads error git cannot see (the filenames differ) and that reads as a mystery. F19 shipped a fast, no-DB single-head guard that fails in `make test` rather than as a CI surprise — it is permanent and it is what catches step 4 if a human forgets it.
5. **Do not open the PR while a lower-numbered migration is still unmerged.** CI tests the merge result.

Every assertion in this spec and in `test_migrations.py` keys to *"after this feature's migration"*, never to a revision number.

**Deliberately absent from the migration, each for a verified reason:** no column-level `GRANT` (table grants are column-agnostic, `0003_auth.py:83-84`'s precedent); no `REVOKE`-first (that is the append-only shape, `0005:122-126`); no FK and no `ON DELETE` (house rule); no `NOT NULL` on any of the five stamps (D2).

**The ORM model is the second half of this migration and is not optional.** `Backend/app/models/alteration_ticket.py` declares every column explicitly — `AlterationTicket(StandardColumns, Base)`, `tenant_id` and the rest — because **no model↔migration parity test exists anywhere in `Backend/tests/`**, so without it every backend line in D2, D3 and D9 is an `AttributeError`. Migration + model are one atomic change (`0008_bookings.py` / `models/booking.py`, F34's D2, F57's D3).

**`test_migrations.py` gains:** the table exists with the five stamps **nullable** and `TIMESTAMPTZ`; `effort_minutes`' CHECK definition pinned **byte-identical** via `pg_get_constraintdef` (**captured by running it**, not transcribed — `IN`/comparison deparsing); the one index pinned via `pg_indexes.indexdef`, which is the row that fails if someone re-adds `UNIQUE`; forced RLS on the table; and this feature's migration up **and down**.

### D15 — The console section, its own poll, and both of F34's shipped loop fixes

A new `AtelierSection.tsx` in `apps/manage`, owning **all** of its own state and its own `usePoll` instance. It is the **fourth** caller of the hook (`BoardSection`, `FloorPanel`, this, then F42's extension of this) and it re-derives nothing.

**Every one of F34's D4 mechanisms comes from the hook and is not re-implemented**: the single arming site (`schedule-after-settle`, so at most one request in flight per tab **by construction**), the `document.hidden` gate plus the `visibilitychange` **immediate** refetch, the 5s → 60s backoff with reset on first success, the `{401, 403}` terminal classification, the idle stop, and the monotonic generation behind `isCurrent`.

**Two shipped fixes come with it and the section must not defeat either.** Both live inside `usePoll` and both are one line:

- **The unmount fix** (`usePoll.ts`, the mount effect's cleanup: `runningRef.current = false` **before** `clearTick()`, with its comment). `clearTick()` alone cancels only the timer armed right now; the arming sites are a request's `.finally()`, which runs **after** cleanup when a request is in flight, and nothing in tick → run → finally → reschedule touches React state, so the loop would outlive the component. That leak shipped once and cost one permanent 5-second request loop **per nav-away**, for the rest of a twelve-hour session.
- **The StrictMode-idempotent mount effect** (`runningRef.current = true` as the effect's **first** line). Without it a setup → cleanup → setup cycle — which `<StrictMode>` performs on every mount in development — leaves the loop permanently dead while `mode` still reads `"running"`, so the UI shows a pause control for a loop that is not polling.

**What the section owns**, matching `FloorPanel.tsx` exactly:

- Its own `holdRef` pointer-hold → `run` returns `"held"`; the hook re-arms at the **current, possibly backed-off** gap and leaves the backoff alone. The hold matters more here than on the floor panel: a card that changes column is a **layout** change under a travelling finger, not a text swap.
- Its own `mutationsRef` → `run` returns `"suppressed"` while non-zero; the single re-arm is the mutation's own **`.finally()`**, not its success path, so a refused advance does not park the loop.
- `poll.bump()` before every mutation, so the one poll that could still be in the air is discarded.
- `poll.fail(error)` in every mutation's `catch`, which is what makes a 403 on an advance **terminal** on the same `{401,403}` rule the ticks use (F57's deck P-6) — the realistic cause is a mid-shift role change, and an in-card alert plus a loop still polling with a role the server just refused is the panel disagreeing with itself for five seconds and then doing the same thing anyway.
- **NOT optimistic.** Every mutation answers the **full ticket** and the card is patched from the server's row (`AtelierTicket`, not `{ok: true}`), so the console cannot disagree with itself — and on a 200 no-op that is what renders the **first** actor's timestamp rather than this request's intent.

**No atelier state above `AtelierSection`.** `App.tsx` composes `{activeKey === "atelier" && <AtelierSection selfId={staff.id} role={staff.role} />}` and nothing else; lifting rows into `App` would make every atelier tick repaint the whole console.

### D16 — NO DRAG AND DROP. The accessible primary path, and the focus move an advance forces

**A kanban is a drag-shaped idea and this one ships with no drag affordance at all.** That is a decision, not an omission, and the argument is short: every accessible drag-and-drop implementation is a keyboard-and-screen-reader alternative bolted onto a pointer gesture, which means building the button path anyway and then building the gesture on top. Pre-decided #38 makes IS 5568 / WCAG 2.0 AA a **legal** requirement for these screens, and the WCAG 2.1 successor's SC 2.5.7 (Dragging Movements) says the same thing from the other side: a drag must have a single-pointer alternative. So the alternative **is** the interface.

**Each card carries, in tab order. EVERY control is `size="md"`, and the two `<Select>`s carry `className="min-h-11"`:**

| Control | Shape | Behaviour |
|---|---|---|
| «לשלב הבא» | `Button variant="secondary"` | Advances to the **immediately next** stage. The 90 % case, one tap. Absent on a `delivered` card. |
| «העברה לשלב» + «העברה» | `Select` (native) **plus a sibling commit `Button`** | Options are **only** the stages strictly later than the current one; a backwards option is never rendered, so the 409 is a race guard rather than a routine refusal. **The `Select` sets a per-card `pendingStage` and issues NO request**; the `Button` issues it and is `disabled={pendingStage === null}`. |
| «ביטול שלב» | `Button variant="ghost"` | The undo (D4). Absent when the stage is `intake`. |
| assign | `Select` of assignable `seamstresses` + «לא משויך» **plus a sibling «שיוך» commit `Button`**, or a single «לקחת» / «לשחרר» button for a seamstress | D9's two axes rendered, same select-then-commit split. Which control **exists** is cosmetics; the server is the control (F57's rule). |
| «עריכה» | `Button variant="ghost"` | Reopens the intake `Modal` **in edit mode**, prefilled from the card (`POST …/update`, a full replace — API surface). The customer is not editable. Elevated on any ticket; a seamstress on **her own** ticket only (D3's per-verb table) — and which control renders is cosmetics, the service is the control. |
| «מחיקה» | `Button variant="danger"` behind a confirm `Modal` | `POST …/delete`. **Owner and shift manager only** (D10's per-route tightening), and the confirm is `StaffSection`'s shipped deactivate shape — there is no un-delete (Risk 6). |

**⚠ NO CONTROL ON THIS BOARD MUTATES ON `change`. This is the one interaction rule that a builder will get wrong by copying the obvious thing.** An earlier draft made the skip `Select` fire `advanceStage` from `onChange` with no confirm step. On Windows Chrome and Firefox a **closed** native `<select>` changes its value and fires `change` on *every arrow keypress* — so a keyboard user on an `in_progress` card arrowing down to «נמסר» would fire three separate advances (`qc`, `ready`, `delivered`), writing three timestamps and three `ATELIER_TICKET_STAGE_ADVANCED` audit rows, moving the card across three columns and firing the focus move three times, before committing to anything. Under D2 those stamps **are** the trail and under D4 each needs its own undo call to reverse. That is WCAG **3.2.2 On Input** (Level A, inside the legally binding AA bar of pre-decided #38), it falsifies this feature's own "fully operable with no pointer" criterion, and it would be the **first** `<Select>` in this console to mutate on change — every shipped one sets draft state only (`StaffSection.tsx:241-246`, `:375-380`). Selection and commit are separate controls, on both selects.

**Structure: five `<section aria-labelledby={headingId}>`, each with an `<h3 id={headingId}>` naming the stage and its count, each containing a `<ul aria-label={t(STAGE_LABEL_KEY[stage])}>`.** Not a table, not a grid, not `role="application"`. **The names are load-bearing, not decoration**: an unnamed `<section>` is not exposed as a region at all and an unnamed `<ul>` is an anonymous list, so a user navigating by list (NVDA `L`, VoiceOver rotor) — the exact navigation a five-column board invites — would land on five consecutive unnamed lists with no way to tell `qc` from `ready`, and the count in the `<h3>` would be reachable only by walking backwards out of the list. With the names, a screen reader reads «בעבודה, 4 כרטיסים, רשימה בת 4 פריטים» and arrows through it; the count in the heading is what replaces the visual scan a sighted user gets for free.

**⚠ THE FOCUS MOVE, AND HERE IT IS STRUCTURAL RATHER THAN ACCIDENTAL.** A successful advance **moves the card to a different column**. The tapped control therefore unmounts, and the browser drops `document.activeElement` to `<body>`. This is the bug class that has now shipped **three times** in this repo — F56 on the storefront, F34 on the board, F57 on the floor panel — and **axe walked past it every time, because axe cannot see a focus move that never happened.** On this surface it is not a side effect of `@boutique/ui`'s `Button` being `disabled={disabled || loading}`; it is what the feature *does*.

The rule, keyed on state rather than raised inside the handler (the alert node does not exist yet when `setError` runs — `FloorPanel.tsx:220-236` is the shape):

- **Success** → focus the **same ticket's** «לשלב הבא» control in its **new column**. The ref map is keyed by `data-ticket-id`, which survives the move, so this is a map lookup and not a search. If the destination card has no advance control (`delivered`), focus its **column heading** (`tabIndex={-1}`), which is F51's shipped stranded-focus pattern and needs no new string.
- **Failure** → focus the **in-card alert** (`role="alert"`, `tabIndex={-1}`), in the `text-danger` fix-this register.
- **A successful poll that unmounts the focused in-card alert** → hand focus back to that card's own control, the `reclaimFocusRef` mechanism `FloorPanel.tsx:118-131` documents. This one is easy to miss: the alert is cleared about five seconds later **with no user action at all**, and the departing-card rescue cannot cover it because the card is still in the list.
- **A successful DELETE** → the card leaves the board **entirely**, so there is no destination card and the ref map has nothing to look up. Focus its **column's `<h3 tabIndex={-1}>`** via `focusHeadingRef`, which is the shipped `departingCardHoldsFocus` rescue (`FloorPanel.tsx:39`, `:252-266`) pointed at a heading instead of a row. Without it, deleting the focused card drops `document.activeElement` to `<body>` on the single most destructive action in the feature.

**Each of the four gets a named, non-vacuous vitest test whose mutation is stated in Testing.** A test that only asserts "the advance succeeded" would pass with every focus line deleted.

### D17 — SC 2.2.2, the live region, and colour is never the signal

The section is a **third** auto-updating surface in the console, so it carries its own mechanism. Level A sits inside the AA bar pre-decided #38 makes legal, and **axe has no rule for SC 2.2.2** — the named vitest assertions are the *sole* automated coverage of a legal requirement and may not be cut as redundant with the axe row.

- **44×44 is the floor for EVERY control on this surface, not only the pause toggle.** `@boutique/ui`'s `Button` is `min-h-11` (44 px) at `size="md"` but **`min-h-9` (36 px) at `size="sm"`** (`Button.tsx:35-39`), and `Select` declares no min-height at all — `px-3 py-2 text-base` lands near 42 px (`Select.tsx:26-34`). A five-column board with six controls per card is exactly the layout in which someone reaches for `size="sm"` to make the cards fit, and this console is used on staff phones. **`size="sm"` is barred on this surface**, and the two `<Select>`s carry `min-h-11` explicitly (D16). Asserted as a rendering check, because axe has no target-size rule at the level this repo runs it.
- **Its own visible pause / resume toggle**, 44×44 minimum, in the tab order, **first inside the section and before any card** (a 2.2.2 mechanism placed after the content it governs is reachable only by walking the list that is repainting under the walk). One button whose accessible name changes; never `aria-pressed`. Resume fetches immediately and resets to the **base** interval, not a backed-off gap.
- **Its own idle stop** at the shared `IDLE_STOP_MS`, and its own copy naming **its own region** — `atelier.idleStopped` must not be byte-identical to `board.idleStopped` or `floor.idleStopped`, because all three write into a `role="status"` region and all three idle windows are reset by the same global interactions (`design.md` F-4's finding, generalised).
- **The accessible names of the pause controls must CONTAIN their visible labels** — WCAG 2.5.3 label-in-name. `floor.pauseAria` is «השהיה — עדכון הצוות» because «השהיית» is a different word form and a speech-input user saying «השהיה» would match nothing. `atelier.pauseAria` = «השהיה — לוח התפירה», same shape, and `i18n.test.ts` asserts the containment rather than trusting it.
- **The poll never writes into an aria-live region** (F34's D11, verbatim and non-negotiable). A `role="status"` update every five seconds announces the whole board forever. The announced region carries **only user-initiated outcomes**: the advance cue, the assign cue, the pause, the idle stop (whose trigger is her own inactivity), the terminal alert. Cards repaint silently.
- **⚠ THE CUE TEXT IS THE ENTIRE A11Y PAYLOAD OF D16'S NO-DRAG DECISION, AND IT IS DECLARED COPY — not "some string".** For a sighted user a stage advance is self-evident: the card is visibly in another column. For a screen-reader user **the cue IS the move**, and a cue that does not name the ticket and its destination announces nothing. F57 shipped exactly this shape (`he.ts:647-648`, `floor.breakStartedCue` = «נרשמה הפסקה עבור {{name}}.»), so D18 declares the five F41 cues and the acceptance criterion asserts the cue's **text**, not merely that it changed. The state shape is the shipped one — `{ text, name }` plus `isolateBidi(cueText, cue.name)` (`FloorPanel.tsx:61`, `:428`) — because the interpolated values are Hebrew names sitting next to a stage word.
- **The cue is written only when its value actually changes.** Assigning a non-empty string to a text node runs the DOM's string-replace-all and produces a real `childList` mutation inside `role="status"` **even when the two strings are byte-identical** (F34's F-7). `setCue` with an equal value is a React no-op, so the guard is the `setState` itself — and the test has to drive **several consecutive ticks with the cue already populated**, because a single-tick assertion passes against the broken version whenever the cue starts empty.
- **The freshness line is visible, readable and NOT `aria-hidden`** (F34's accepted F-1 — the only honesty signal must not be sighted-only).
- **Status and urgency carry WORDS.** The stage is the column heading, in words. **Overdue is a `Badge` carrying «באיחור» plus the date**, never a red border alone — a dense board whose only urgency signal is a colour fails colour-not-sole-indicator, and the E9 Risks name this as the epic's hard accessibility case. A `Badge variant="danger"` may accompany the word and may never replace it.
- **No shimmer, no pulse, no flash on refresh** — the same rule that serves `prefers-reduced-motion`.
- `<bdi dir="ltr">` around every numeric run (dates, minutes), **bare `<bdi>`** around Hebrew free text (customer names, dress names, notes) — forcing LTR on a Hebrew name reverses its words. One `h1` (the shell's), the section heading an `h2`, column headings `h3`. Visible focus ring on every control.

### D18 — i18n: the `atelier.*` namespace, stage words as a `Record`, and the shipped guards

A new `atelier.*` namespace plus `nav.atelier`, in `apps/manage/src/i18n/he.ts` **and** `ar.ts`, with the Hebrew standing in untranslated in `ar.ts` — Interview Q3, pre-decided #47, the 2026-07-31 Hebrew-only ruling, and `ar.ts`'s own mechanics (never empty strings; `lng` and `fallbackLng` stay `"he"`; no switcher).

| Key | Hebrew |
|---|---|
| `nav.atelier` | «תפירה» |
| `atelier.heading` | «לוח התפירה» |
| `atelier.stage.intake` | «התקבל» |
| `atelier.stage.inProgress` | «בעבודה» |
| `atelier.stage.qc` | «בקרה» |
| `atelier.stage.ready` | «מוכן» |
| `atelier.stage.delivered` | «נמסר» |
| `atelier.band.thirtyMin` … `atelier.band.fullDay` | «חצי שעה» / «שעה» / «שעתיים» / «חצי יום» / «יום מלא» |
| `atelier.overdue` | «באיחור» |
| `atelier.unassigned` | «לא משויך» |
| `atelier.assigneeInactive` | «תופרת שאינה פעילה» |
| `atelier.advance` / `atelier.advanceAria` | «לשלב הבא» / «לשלב הבא — {{name}}» |
| `atelier.undo` / `atelier.undoAria` | «ביטול שלב» / «ביטול שלב — {{name}}» |
| `atelier.skip` / `atelier.skipAria` | «העברה לשלב» / «העברה לשלב — {{name}}» |
| `atelier.skipCommit` | «העברה» — the commit `Button` beside the skip `Select` (D16) |
| `atelier.assignLabel` / `atelier.assignAria` | «שיוך» / «שיוך — {{name}}» — the `Select`'s **required** `label` prop and its per-card name |
| `atelier.assignCommit` | «שיוך» — the commit `Button` beside the assign `Select` |
| `atelier.claim` / `atelier.claimAria` | «לקחת» / «לקחת — {{name}}» |
| `atelier.release` / `atelier.releaseAria` | «לשחרר» / «לשחרר — {{name}}» |
| `atelier.newTicket` | «כרטיס חדש» — the board-level intake CTA |
| `atelier.edit` / `atelier.editAria` | «עריכה» / «עריכה — {{name}}» |
| `atelier.delete` / `atelier.deleteAria` | «מחיקה» / «מחיקה — {{name}}» |
| `atelier.deleteConfirmTitle` / `atelier.deleteConfirmBody` | «מחיקת כרטיס» / «הכרטיס של {{name}} יימחק מהלוח. לא ניתן לשחזר אותו.» |
| `atelier.cue.created` | «{{name}} — נפתח כרטיס.» |
| `atelier.cue.advanced` | «{{name}} — הועבר ל{{stage}}.» |
| `atelier.cue.undone` | «{{name}} — הוחזר ל{{stage}}.» |
| `atelier.cue.assigned` | «{{name}} — שויך ל{{seamstress}}.» |
| `atelier.cue.released` | «{{name}} — השיוך בוטל.» |
| `atelier.cue.deleted` | «{{name}} — הכרטיס נמחק.» |
| `atelier.error.stageConflict` | «הכרטיס כבר התקדם. הלוח יתעדכן בעדכון הבא.» |
| `atelier.error.alreadyAssigned` | «הכרטיס כבר משויך. הלוח יתעדכן בעדכון הבא.» |

**⚠ ALL FOUR PER-CARD CONTROLS GET A DISAMBIGUATING ACCESSIBLE NAME, not just the two `Button`s.** `@boutique/ui`'s `Select` derives its accessible name **solely** from its required `label` prop, which it renders as a visible `<label htmlFor>` (`Select.tsx:6`, `:14-32`) — there is no name-override path in the component's own API. Left at that, a board of 30 cards exposes 30 comboboxes all named «העברה לשלב» and up to 30 more all named «שיוך», and a screen-reader user pulling up the control list, or a speech-input user saying the label, cannot address a specific ticket (WCAG 4.1.2, 2.4.6). The component spreads `...rest` onto the `<select>`, so both carry `aria-label={t("atelier.skipAria", { name })}` / `aria-label={t("atelier.assignAria", { name })}`. **Each aria value CONTAINS its visible label** — the same label-in-name shape D17 pins for the pause control (WCAG 2.5.3), so a speech-input user saying «העברה לשלב» still matches — and `i18n.test.ts` asserts that containment for **all four** aria keys, not only the pause pair.

plus the polling surface's own state set, which is the set a third auto-updating surface needs and a reason not to re-derive it: `atelier.pause` / `pauseAria` / `resume` / `resumeAria` / `paused` / `pausedAt` / `idleStopped` / `resumed` / `loading` / `updatedAt` / `staleAt` / `staleBody` / `refresh` / `empty` / `emptyColumn` / `sessionEnded` / `accessEnded` / `reload` / `truncated`, plus the intake and edit form's labels and its validation messages.

**Reuse rather than re-declare where this surface says the same thing about the same thing.** `staff.roleSeamstress` (F57) is the role word; `ROLE_LABEL_KEY` in `lib/roles.ts` is `Record<StaffRole, string>` and needs no edit. Follow F57's `design.md` F-10 precedent for outage copy: **reuse a key whose NAMESPACE NAMES ITS SUBJECT, never one whose namespace names a screen.**

**The stage word becomes a `Record`, for the reason `lib/roles.ts` exists.**

```ts
export const STAGE_LABEL_KEY: Record<TicketStage, string> = {
  intake: "atelier.stage.intake",
  in_progress: "atelier.stage.inProgress",
  qc: "atelier.stage.qc",
  ready: "atelier.stage.ready",
  delivered: "atelier.stage.delivered",
};
```

`Record<TicketStage, string>` is the point: a sixth stage added to the union without a key is a **compile** error, not a wrong label. A vitest assertion resolves every value through i18n so a key in the map but not in `he.ts` is caught too — the two halves catch different bugs, and `lib/roles.ts`'s header says why.

**⚠ `HE_F41` MUST BE DECLARED *AND SPREAD INTO* `HE`, OR EVERY GUARD BELOW SILENTLY SKIPS THIS FEATURE.**

```ts
const HE_F41 = entries(
  he.translation,
  (key) => key === "nav.atelier" || key.startsWith("atelier."),
);
const HE = [...HE_F15, ...HE_F51, ...HE_F52, ...HE_F17, ...HE_F34, ...HE_F57, ...HE_F53, ...HE_F41];
```

`HE` is a hand-assembled union of per-feature selections (`i18n.test.ts:48`), and **four** shipped guards iterate it. Declaring the constant and forgetting the spread is a failure the file records in its own words at `:33-35` — *"without this the resolve check, BOTH register guards and the `ar` parity guard silently skip every F52 key"* — and F53 asserts the fold itself rather than trusting it (`:248-256`). F41 does the same: **`expect(HE.map(([key]) => key)).toContain("nav.atelier")`.**

**Four shipped guards this deck must clear, and none is optional:**

1. **The `ar` parity guard EXISTS.** `it("carries every key both features added to he.ts")` (`:417-420`) asserts every `HE` key is present in `ar.translation`. An earlier draft of this document claimed no parity guard existed, inheriting a stale F15 risk; it does, it has since F52, and it only sees F41's keys through the fold above.
2. **`:401-402` rejects any selected Hebrew value matching `/נשלח|תישלח|בדרך/`.** Trivially satisfied — F41 sends nothing, has no SMS template and touches no `comms_templates.py` body — and stated anyway, because «נודיע לתופרת» is exactly the sentence a well-meaning editor adds to an assign cue. It would also be a **lie**: nothing in this feature notifies anybody.
3. **`:397-399` rejects an exclamation mark** anywhere in the selected values.
4. **`:406-415` rejects any empty `ar` value** — the one guard that works without the fold, because it reads `ar.translation` directly. i18next's `returnEmptyString` renders `""` rather than falling back, so a placeholder blanks the page instead of showing Hebrew.

**F41's own block mirrors `HE_F57`'s**: a `length` floor, the no-retry-interval check over its values, the no-role-in-`accessEnded` check, the label-in-name containment for all four aria pairs, and the resolve check over every `STAGE_LABEL_KEY` value.

**No new formatter.** `lib/jerusalem.ts::plainDate(iso)` renders `due_date` (a wire **calendar date**, `"2026-08-20"`) as `d.m.yyyy` and its header states the rule this feature must not break: *"a wire date is a plain calendar date and must never meet a `Date`"* — `new Date("2026-08-20")` parses as UTC midnight and re-zoning it re-zones a date that was never in a zone. `todayJerusalem()` exists for the intake form's default. `jerusalemTime` renders the stamps. `scripts/qa-greps.sh`'s unzoned-formatter grep gains nothing to find.

**No NEW guard is invented.** The parity guard, the two register guards and the empty-`ar` guard are all shipped; F41's whole obligation is the fold above plus its own block.

### D19 — `vite.config.ts` gains `atelier`, or a developer's machine silently serves the SPA shell

`MANAGE_API` in `apps/manage/vite.config.ts:18-19` names the second path segments of every `/manage` router in an explicit alternation, because `base: "/manage/"` means a bare `/manage` proxy would forward the console's own shell and assets to the backend. It names **thirteen** today — `appointment-types|auth|availability|bookings|customers|dashboard|dresses|floor|gateway|settings|slots|staff|terms` — and its own comment at `:13-17` calls out *"a fourteenth segment added without touching this file"*. `atelier` is that fourteenth and must be added to the alternation.

**This is not housekeeping.** `Backend/tests/test_spa_serving.py::test_the_manage_dev_proxy_names_every_manage_api_segment` (`:372-403`) derives the segment set from the **live route table** and asserts **SET EQUALITY** against the regex. F57's shipped note records this exact test catching this exact omission and calls it *"the nastiest failure mode of the three: production, CI and the suite all stay green while only a developer's machine breaks, serving the SPA shell where the API should be."* It has now bitten this repo twice (F52 and F57).

The edit is one word. It is called out as its own decision so the plan carries it as a task rather than as an afterthought inside a frontend task.

---

## API surface

| Method | Path | Body | Answers | Admits |
|---|---|---|---|---|
| `GET` | `/manage/atelier/tickets` | — | `AtelierBoardResponse` | owner, shift_manager, seamstress |
| `POST` | `/manage/atelier/tickets` | `CreateTicketRequest` | `AtelierTicket` | all three (a seamstress opens a ticket on the bride she is standing with) |
| `POST` | `/manage/atelier/tickets/{ticket_id}/update` | `UpdateTicketRequest` | `AtelierTicket` | all three — a seamstress **only on a ticket assigned to her**; scheduling is not work-recording (**D3's per-verb table** carries the reason for the asymmetry with the two rows below) |
| `POST` | `/manage/atelier/tickets/{ticket_id}/assign` | `AssignTicketRequest` | `AtelierTicket` | all three — a seamstress only herself-on-unassigned, or release-her-own (D9) |
| `POST` | `/manage/atelier/tickets/{ticket_id}/stage/advance` | `StageRequest` | `AtelierTicket` | all three — a seamstress on her own **or an unassigned** ticket (D3) |
| `POST` | `/manage/atelier/tickets/{ticket_id}/stage/undo` | `StageRequest` | `AtelierTicket` | same |
| `POST` | `/manage/atelier/tickets/{ticket_id}/delete` | — | `OkResponse` | **owner, shift_manager only** — per-route tightening (D10) |

Real HTTP verbs and a path parameter for the target, the shipped `/manage` convention (`app/floor/router.py:44-47`: the `.claude/rules` RPC / `@QueryValue` guidance is Kotlin boilerplate for another codebase). All seven are `cache-control: no-store` by the router-level dependency; the six POSTs are CSRF-fenced by `CsrfOriginMiddleware`.

```jsonc
// POST /manage/atelier/tickets       — every request model is a ForbidExtraModel
{
  "customer_name": "מיכל לוי",          // required, <= 80, control chars barred
  "customer_phone": "0521234567",       // required, normalize_israeli_mobile
  "due_date": "2026-08-20",             // required, a plain calendar date
  "effort_band": "two_hours",           // required, one of the five keys — NEVER minutes
  "assigned_staff_user_id": null,       // optional; must be a live seamstress if given
  "dress_id": "3a70…",                  // optional; when given the server copies dress_name
  "dress_name": null,                   // optional free text, ONLY when dress_id is null
  "dress_size": "38",                   // optional free text, <= 40
  "notes": "להרים 4 ס\"מ"                // optional, <= 500
}

// POST …/update — FULL REPLACE of the editable fields. Every one is required so
// an omitted key can never silently clear a value (UpdateAppointmentTypeRequest's
// shipped rule). The customer is NOT editable: a ticket opened for the wrong
// bride is a delete, not an edit.
{ "due_date": "2026-08-22", "effort_band": "half_day",
  "dress_id": null, "dress_name": "שמלת ערב של הלקוחה", "dress_size": "M", "notes": "" }

// POST …/assign
{ "staff_user_id": "9c21…" }            // or null to release

// POST …/stage/advance  and  POST …/stage/undo
{ "stage": "qc" }                       // advance: the stage to ENTER.
                                        // undo:    the stage to CLEAR (D4) — the client
                                        //          names what its last poll showed, which
                                        //          is what makes a stale board harmless.
```

Every mutation answers the **full ticket**, so the console patches its card from the server's own row (F34's D4.4 contract).

---

## Frontend changes

| File | Change |
|---|---|
| `apps/manage/src/components/AtelierSection.tsx` | **new** — the five columns, the cards, the intake/edit `Modal` and the delete confirm `Modal`, the advance/skip/undo/assign/edit/delete controls (**every one commit-on-click, never on `change`** — D16), its own `usePoll`, the pause/resume + idle control, the freshness line, the announced region, the terminal panel, all **four** focus moves (D15–D17) |
| `apps/manage/src/lib/stages.ts` | **new** — `STAGE_ORDER: readonly TicketStage[]`, `STAGE_LABEL_KEY: Record<TicketStage, string>`, `laterStages(current)` for the skip `Select`, `bandLabel(minutes, bands)` for the minutes→word reverse lookup with a «{{minutes}} דק׳» fallback (D8, D18). In `lib/` so the section and F42's picker share it without an import cycle |
| `apps/manage/src/App.tsx` | `SectionKey` (`:20-33`) gains a **thirteenth** member `"atelier"` — F53's `customers` is already the twelfth, and the in-file comment *"F57's floor — the ELEVENTH member"* at `:31` is stale and should be corrected in passing; a new `ATELIER_ROLES = ["owner", "shift_manager", "seamstress"]`; a **thirteenth** `NAV` row (`:64-109`) after `floor`; an `"atelier"` render branch. `FLOOR_ONLY` is unchanged — a seamstress now reaches **two** rows (floor and atelier) and `reachable[0]?.key ?? section` (`:165-167`) still lands her on the floor with no edit |
| `apps/manage/src/api.ts` | `TicketStage`, `EffortBand`, `AtelierTicket`, `SeamstressRef`, `EffortBandRef`, `AtelierBoardResponse` interfaces; `getAtelierBoard`, `createTicket`, `updateTicket`, `assignTicket`, `advanceStage`, `undoStage`, `deleteTicket` on the exported `api` object |
| `apps/manage/src/i18n/he.ts`, `…/ar.ts` | `nav.atelier` + the `atelier.*` namespace — **both files**, Hebrew untranslated in `ar` (D18) |
| `apps/manage/vite.config.ts` | **`atelier` added to `MANAGE_API`'s alternation as the FOURTEENTH segment** — D19, and `test_spa_serving.py` asserts set equality against the live route table |
| `apps/manage/src/__tests__/AtelierSection.test.tsx` | **new** |
| `apps/manage/src/__tests__/Nav.test.tsx` | **extended, and the post-F41 numbers are stated so nobody re-derives today's.** F53 already moved these: the file reads *"all eleven sections"* (`:103`), `.slice(0, 9)` (`:114`, `:204`) and `toHaveLength(11)` (`:156`). After F41 they become **owner twelve**, **shift manager `.slice(0, 10)`**, `NAV_LABELS` **12** entries — the atelier label inserted after «לוח היום» and before «צוות» — and the test **name** at `:145` (*"keeps the owner's eleven and the shift manager's nine…"*) is renamed with them, because that file says in as many words that the numbers move together and carries them in words as well. Reception and sales_assistant **unchanged at one**; **a seamstress sees exactly two rows, «הצוות בקומה» first**, as its own assertion — the one that fails if the atelier row was given to `FLOOR_ONLY` by mistake |
| `apps/manage/src/__tests__/i18n.test.ts` | **extended** — `HE_F41` declared **and spread into `HE`** (D18), a `F41 atelier keys resolve` block in the shape F15/F51/F52/F17/F34/F57/F53 each have, including F53's own *"is FOLDED into `HE`, not merely declared"* assertion |
| `…/__tests__/FloorPanel.test.tsx`, `…/BoardSection.test.tsx`, `…/StaffSection.test.tsx` | **no change** — F41 touches none of those components |
| `Frontend/apps/manage/src/lib/usePoll.ts` | **no change** — the hook is imported, not modified. Any edit to it is a review stop: it has three shipped callers |
| `scripts/qa-greps.sh` | **no change** (D18 — no new formatter) |
| `Backend/tests/test_frontend_constant_parity.py` | **no change** — no client constant mirrors a server bound. ⚠ `DELIVERED_WINDOW_DAYS` and `BOARD_TICKET_LIMIT` are **server-only** and must not be re-declared on the client; the `truncated` flag is on the wire precisely so the console never has to know the number |

**Per-component behaviour and UI rules:**

- **Intake** is a `Modal` (F51's `StaffSection` shape) opened by «כרטיס חדש» above the columns. `due_date` is a native `DateField` (`<input type="date">` — the platform feature, no picker library) defaulting to **empty**, not to today: a due date is the one field a hurried user must not be able to accept by not looking at it. `effort_band` is a `Select` of the five, defaulting to **`one_hour`** (the middle-low band; a default of `full_day` inflates every estimate and a default of `thirty_min` deflates it). `dress_id` is a `Select` of the tenant's live dresses with a «לא מהקטלוג» option that reveals the free-text `dress_name`.
- **Validation is client-side for shape and server-side for truth.** An empty `customer_name`, an unparseable phone, a missing `due_date` or a `notes` over 500 characters is refused before the request; the server refuses the same things and the console renders `response.data.error.message` for anything it did not anticipate.
- **A `due_date` in the past is a WARNING, never a block** — pre-decided #40's advisory rule, and **the server agrees**: there is no lower bound and a past date is a 200 on create and on update (D5). No `min` attribute. A dress that was due yesterday is exactly the ticket a boutique most needs to open.
- **⚠ NO CONTROL MUTATES ON `change`.** The skip `Select` and the assign `Select` each set per-card draft state; a sibling commit `Button` issues the request (D16, and the WCAG 3.2.2 argument for why). This is the console's shipped convention, not a new one — every `<Select>` in `StaffSection.tsx` sets a draft and nothing else.
- **The assign control is a `Select` + commit `Button` for an elevated user and a single «לקחת»/«לשחרר» button for a seamstress.** Which control exists is cosmetics (F57's rule, asserted **as** cosmetics); the server's D9 check is the control.
- **Edit is «עריכה» on the card**, reopening the intake `Modal` in edit mode prefilled from that card and issuing `POST …/update` (a full replace). **Delete is «מחיקה»**, `variant="danger"`, behind a confirm `Modal` in `StaffSection`'s deactivate shape — elevated only, and there is no un-delete (Risk 6), so it asks before it writes and announces after.
- **A card whose `assigned_staff_user_id` carries `assignable: false`** renders «תופרת שאינה פעילה» — the assignee's role was changed or she was retired (D9), and surfacing it is the signal a manager needs to reassign. **The flag is on the wire**, so this is not an inference from absence.

---

## Every state of every surface

**The board:**

| State | What renders |
|---|---|
| **Initial load** | One `Card` with `<Skeleton variant="text" lines={3} />`. **No pause control** — nothing is auto-updating yet, and a control over a skeleton pauses a fetch the user has not seen produce anything (`FloorPanel.tsx:369-376`'s shipped rule) |
| **Loaded** | Five `<section>`s, each `<h3>` with a stage word and a count, each a `<ul>` of cards ordered by `due_date` ASC |
| **EMPTY — a brand-new boutique** | The five columns are **replaced** by one `<EmptyState title={atelier.empty} />` plus the «כרטיס חדש» CTA. Five empty columns is a wall of nothing that teaches the vocabulary at the cost of looking broken. The freshness row **still renders beneath it** — *a surface that has stopped updating must still be able to say so* |
| **Empty column, board not empty** | A muted «אין כרטיסים בשלב זה» inside the column. The four other columns are the context that makes an empty one legible |
| **First-fetch failure** | The outage register — reuse a subject-named shipped key rather than declaring `atelier.outage` (F57's F-10 precedent) — plus a «רענון» control, **not** while paused (`«רענון»` beside `«חידוש»` is two Hebrew words a hurried reader will not tell apart) |
| **Failed poll with cards on screen** | Keep the cards, swap `updatedAt` for `staleAt` in `text-warning-text font-semibold`, show `staleBody` and a «רענון». Stale-and-labelled beats empty: blanking correct data to report a network fault is worse than the fault |
| **Paused / idle-stopped** | `pausedAt` in the warning register; the body line says **which** — a manual pause and an idle stop are a control and a surprise, and they must not read alike |
| **Session or permission ended (401 / 403)** | Loop stopped, cards cleared (a dead session cannot vouch for them; on the 403 the board is exactly what she may no longer see), a reload affordance, and copy that **names no role** |
| **Truncated** | A line above the columns saying the board is showing the most urgent 500; the number is the server's and the console never states it |

**The ugly edges, each designed rather than discovered:**

| Edge | Behaviour |
|---|---|
| **60 tickets in one column** | The column body is its own `overflow-y: auto` container with a `max-height`, so the page never scrolls horizontally and the other four headings stay reachable. The count in the `<h3>` is what tells a screen-reader user the column is long before she enters it |
| **A ticket with no seamstress** | «לא משויך» as a muted word plus the assign control. Not an empty space, and not a red flag — unassigned is the normal state of a ticket ten seconds old |
| **An overdue ticket** | `Badge variant="danger"` carrying **«באיחור»** plus the date. Never a red border alone, never a colour alone (D17). An overdue **delivered** ticket carries nothing — it is history |
| **A 60-character dress name** | `break-words`, **no truncation and no ellipsis, ever** — a board that abbreviates two garments into the same string is worse than a tall card (`FloorPanel.tsx`'s shipped rule for display names) |
| **`effort_minutes` matching no current band** (post re-tune) | «{{minutes}} דק׳» via `bandLabel`'s fallback. Honest, and it is the visible consequence of D8's "minutes persist, never the label" |
| **A deactivated or re-roled assignee** | «תופרת שאינה פעילה» from the wire's `assignable: false` (D9/D12) — the signal to reassign |
| **A ticket at `ready` with `in_progress_at` and `qc_at` NULL** | Renders in the `ready` column with no annotation. D2's rule: a NULL earlier stamp means never separately recorded, and the board is not the place to explain a skip — `audit_log` is |

**The intake / edit `Modal`, where four of D13's six 400s and the `dress_id` 404 actually land.** It had two prose sentences and no state table; it gets one, because a dialog is a surface:

| State | What renders |
|---|---|
| **Submitting** | The confirm `Button` carries `loading` (which also disables it — `@boutique/ui`'s `disabled={disabled \|\| loading}`); the fields stay enabled so a slow network does not eat a correction |
| **Per-field validation error** | The message rides the field's own `error` prop (`Input` / `Select` both take one and wire `aria-describedby` + `role="alert"`): `customer_name`, `customer_phone`, `due_date`, `effort_band`, `dress_name`, `dress_size`, `notes` |
| **A server error that maps to no field** | An unknown band key, a `dress_id` 404, a 409 from a concurrent edit: one alert **inside the dialog**, above the footer, `role="alert"` and focused — never a toast behind a modal and never a message the dialog dismisses itself to show |
| **Success** | The `Modal` closes. Native `<dialog>` **returns focus to the trigger by itself** (`Modal.tsx:14-18`), so no focus code is written here — stated so the fourth `usePoll` consumer does not re-derive it — and `atelier.cue.created` is announced |
| **A returning customer whose stored name differs** | Once the phone parses, «לקוחה קיימת — השם יעודכן ל…» beside the phone field. `upsert` rewrites `customers.name` unconditionally (D6), F53 renders that name on a screen of its own, and a seamstress typing «מיכל» for «מיכל לוי» must not do that invisibly. No new endpoint: intake echoes the resolved `customer_name` |

**The delete confirm `Modal`** carries the same three rows (submitting / refused / succeeded), plus: on success the card leaves the board and focus goes to the column heading (D16's fourth focus move).

---

## Acceptance criteria

Each line maps to a named test.

- [ ] `alteration_tickets` exists with the five `TIMESTAMPTZ NULL` stamps, `enable_tenant_rls` forced, the one partial index, and the `updated_at` trigger → `test_migrations.py` (db)
- [ ] `test_every_tenant_id_table_has_forced_rls` still passes with the new table → `test_tenant_isolation.py` (db, unchanged)
- [ ] Tenant B can neither read, advance, assign nor delete tenant A's ticket, and every attempt is a 404 indistinguishable from missing → `test_atelier_isolation.py` (db, **new**)
- [ ] `stage_of` is a total function returning the rightmost stamp, `intake` when none is set → `test_atelier_stages.py` (fast)
- [ ] A ticket with `intake_at` and `ready_at` set and the two middle stamps NULL reads as `ready` → `test_atelier_stages.py` (fast)
- [ ] An advance to a strictly later stage stamps the column, answers 200 and writes one audit row carrying `from`/`to` → `test_atelier_service.py` (fast) + `test_atelier_db.py` (db)
- [ ] Re-advancing to the current stage answers **200 unchanged**, keeps the first timestamp and writes **no** audit row → `test_atelier_db.py` (db)
- [ ] Advancing to a stage the ticket has passed answers **409 `TICKET_STAGE_CONFLICT`**, and so does a zero-row advance whose re-read shows an **EARLIER** stage (the concurrent-undo interleave — no branch returns `None`) → `test_atelier_service.py` (fast) + `test_atelier_db.py` (db, **forced interleave**)
- [ ] Undoing a stage that is NULL **while a later stamp exists** answers **409**, not 200 — the skip-then-stale-undo sequence in D4, verbatim → `test_atelier_service.py` (fast)
- [ ] A `due_date` in the **past** is accepted on create and on update (**200**, no warning field); a `due_date` beyond `MAX_DUE_DATE_HORIZON_DAYS` is a 400 → `test_atelier_api.py` (fast)
- [ ] Two concurrent advances leave exactly one stamp and the loser renders the **database's** stage → `test_atelier_db.py` (db, **forced interleave**)
- [ ] Undo clears the rightmost stamp and the audit row carries the destroyed timestamp → `test_atelier_db.py` (db)
- [ ] Undoing `intake` is a 400 → `test_atelier_service.py` (fast)
- [ ] `effort_minutes` is resolved server-side from a band key; a tenant with no `atelier` settings gets the five platform defaults; a partial or corrupt mapping falls back per band → `test_atelier_bands.py` (fast)
- [ ] A band key outside the five is a 400 and never reaches the row → `test_atelier_api.py` (fast)
- [ ] `dress_name` is copied from `dresses` when `dress_id` is given; an unknown/archived/foreign `dress_id` is a 404 → `test_atelier_service.py` (fast) + `test_atelier_db.py` (db)
- [ ] Intake upserts the customer by `(tenant, phone)`; two concurrent intakes for one new phone create **one** customer and two tickets → `test_atelier_db.py` (db, **forced interleave**)
- [ ] `overdue` is true only when `due_date < today_jerusalem` **and** `delivered_at IS NULL`, against a frozen clock → `test_atelier_board.py` (fast)
- [ ] An elevated caller assigns anyone, last write wins, audited with `from`/`to` → `test_atelier_service.py` (fast)
- [ ] A seamstress claims an unassigned ticket; a second seamstress claiming the same one gets **409 `TICKET_ALREADY_ASSIGNED`** and the winner keeps it → `test_atelier_db.py` (db, **forced interleave**)
- [ ] A seamstress cannot assign anyone but herself, cannot release another's claim, and cannot delete — and the ticket repository is **never called** on the pure-role refusals → `test_atelier_service.py` (fast)
- [ ] A seamstress **advances an unassigned ticket** (200) but **cannot `update` one that is not hers** (403, generic body) — D3's per-verb asymmetry, both halves → `test_atelier_service.py` (fast)
- [ ] A non-seamstress assignee is a 400 → `test_atelier_service.py` (fast)
- [ ] `seamstresses[]` carries a **retired or re-roled** assignee with `assignable: false` alongside the live ones — the union, not the filter (D9/D12) → `test_atelier_board.py` (fast)
- [ ] All three admitted roles reach all seven routes except `delete`, which admits two → `test_atelier_api.py` (fast)
- [ ] **`reception` and `sales_assistant` reach exactly the three floor routes and no atelier route; `seamstress` reaches the three floor routes plus the SIX NON-`delete` atelier routes — asserted as a set equality PER ROLE over `effective = intersection(gates)`** → `test_staff_role_gating.py` (fast, **restructured**, D10)
- [ ] The observed error-code set is **set-equal** to `SPEC_ERROR_CODES` and adds exactly the two new members → `test_atelier_api.py` (fast)
- [ ] The board payload excludes tickets delivered more than 7 days ago, caps at 500 and flags `truncated` → `test_atelier_board.py` (fast) + `test_atelier_db.py` (db)
- [ ] Ordering is `due_date, created_at, id` — two tickets sharing a `due_date` **and a seed transaction** come back in the same order on every run → `test_atelier_db.py` (db)
- [ ] The Vite dev proxy's segment set equals the live `/manage` route table's → `test_spa_serving.py` (fast, **shipped guard**, D19)
- [ ] A successful advance moves focus to the same ticket's control **in its new column** → `AtelierSection.test.tsx`
- [ ] A **failed** advance moves focus to the in-card alert → `AtelierSection.test.tsx`
- [ ] A successful poll that clears the focused in-card alert hands focus back to that card's control → `AtelierSection.test.tsx`
- [ ] Deleting the **focused** card moves focus to its column's `<h3>` — the card is gone, so there is nothing to look up → `AtelierSection.test.tsx`
- [ ] **`{ArrowDown}{ArrowDown}` on the skip `Select` calls `api.advanceStage` ZERO times**; activating «העברה» calls it **exactly once** with the selected stage. Same pair for the assign `Select` and `api.assignTicket`. **Mutation: move the request back into the select's `onChange` → both red** → `AtelierSection.test.tsx`
- [ ] «עריכה» round-trips a `due_date` and an `effort_band` through `POST …/update` and the card renders the server's row → `AtelierSection.test.tsx`
- [ ] «מחיקה» **asks before it writes** — `api.deleteTicket` is not called until the confirm `Modal`'s confirm is activated → `AtelierSection.test.tsx`
- [ ] Each of the five columns resolves as `getByRole("list", { name: <stage word> })`, and each `<section>` is a named region — which also catches a column rendered as a `<div>` when someone reaches for CSS grid → `AtelierSection.test.tsx`
- [ ] One control of each kind renders at the 44 px floor (`toHaveClass("min-h-11")`); no `size="sm"` anywhere in the tree → `AtelierSection.test.tsx`
- [ ] The board is fully operable with no pointer: every advance, skip, undo, assign, edit and delete is reachable by keyboard, and no drag handler exists anywhere in the tree → `AtelierSection.test.tsx`
- [ ] The pause control stops the loop; resume fetches immediately at the base interval; the idle stop fires and names its own region → `AtelierSection.test.tsx`
- [ ] The announced region does **not** change across several consecutive ticks with the cue already populated, and **does** change on an advance and on a pause → `AtelierSection.test.tsx`
- [ ] After an advance to `qc`, `getByRole("status")`'s **textContent** contains the ticket's customer name **and «בקרה»** — the cue is the only signal a screen-reader user gets that the card moved, so its text is asserted, not merely its change → `AtelierSection.test.tsx`
- [ ] Overdue carries the word «באיחור», not colour alone → `AtelierSection.test.tsx`
- [ ] axe: zero violations, **explicitly not sufficient** — axe has no SC 2.2.2 rule and cannot see a focus move that never happened → `AtelierSection.test.tsx`
- [ ] **`HE_F41` is spread into `HE`** (`expect(HE.map(([key]) => key)).toContain("nav.atelier")`) — without it the `ar` parity guard and both register guards silently skip every key below → `i18n.test.ts`
- [ ] Every `atelier.*` key resolves in `he` and exists in `ar` with a non-empty value; every `STAGE_LABEL_KEY` value resolves; **all four aria names contain their visible labels** (pause, skip, assign, advance/undo); no value names a retry interval; `accessEnded` names no role; nothing matches `/נשלח|תישלח|בדרך/` → `i18n.test.ts`

---

## Testing

**Fast suite (no marker, no Docker):**

- `tests/test_atelier_api.py` (**new**, the `test_floor_api.py` shape): a `ROUTES` table for the seven routes, giving the 401 walk, the wiring walk (a **ninth** `/manage` router — a duplicated `(method, path)` would silently win or lose on include order) and the `cache-control: no-store` parametrization; a `FakeAtelierService`; each route reaching its own service method with the right arguments; the CSRF fence on a POST and its absence on the GET; the error-code set asserted **set-equal**; `TicketStage`'s and `EffortBand`'s wire literals asserted **set-equal**; the payload literal for a two-ticket board. `ATELIER_ROUTES` is **exported** for `test_staff_role_gating.py` (the `test_floor_api.FLOOR_ROUTES` precedent) so the seven rows get a real end-to-end 403 assertion and not only the structural one.
- `tests/test_atelier_service.py` (**new**): the authorization matrix as pure branches against fakes — owner/shift_manager on anything; a seamstress **advancing** her own ticket *and* an unassigned one; a seamstress **updating** an unassigned ticket → `NotAuthorizedError` (D3's asymmetry, the half a reader of the API table alone gets wrong); a seamstress on **another's** ticket → `NotAuthorizedError` **and the repository is never called** on the pure-role refusals; the four-outcome mapping of advance and of undo onto 200 / 200-unchanged / 409 / 404, **including the two branches an earlier draft called unreachable**: a zero-row advance whose re-read shows an *earlier* stage, and D4's skip-then-stale-undo sequence — both must be 409 and neither may fall through to `None`; an audit row on a write and **none** on a no-op; the undo's `details` carrying `previous_stamp`; the non-seamstress assignee 400; the `dress_id` 404; undoing `intake` as a 400; a past `due_date` accepted and an out-of-horizon one refused.
- `tests/test_atelier_stages.py` (**new**, pure): `stage_of` over all 32 combinations of the five nullable stamps — which is what makes D2's "rightmost, not first-NULL" rule a fact rather than a comment; the predicate builder emitting the right later-columns clause for each of the five targets.
- `tests/test_atelier_bands.py` (**new**, pure): resolution with no `atelier` key, with a partial mapping, with a negative value, with a string, with a value over the CHECK bound — each falling back **per band** rather than discarding the whole mapping.
- `tests/test_atelier_board.py` (**new**, pure folds over frozen records, the `test_dashboard_math.py` shape — *"a pure fold … is pinned in the fast no-Docker suite"*): `overdue` against a frozen clock either side of Jerusalem midnight; the delivered-window cutoff; the 500 cap and the `truncated` flag; the `due_date` ASC / `created_at` ASC ordering.
- `tests/test_staff_role_gating.py` (**extended, and this is the delicate one — D10**): `NON_ELEVATED_REACH` replaces the single `FLOOR_ROLES`/`FLOOR_OPEN` pair; the walker keeps **intersecting** the gates and asserts a set equality **per role**; the anti-vacuity half widens to `FLOOR_OPEN | ATELIER_OPEN`; `ATELIER_ROUTES` joins the two shipped HTTP walks so the gates are proven to *raise*.
  - ⚠ **`test_gate_admits_listed_roles` (`:333`) gains a NEW CASE, not three roles** (F57's note, verbatim reasoning): that test is a `RoleGate` unit test and widening an existing assertion would assert something false. A **second** case asserts that `require_role(OWNER, SHIFT_MANAGER, SEAMSTRESS)` admits exactly those three and refuses `reception`.
  - **`test_gates_admit_only_known_roles` (`:190`) needs ZERO edits** — it derives `known` from the live enum and F41 adds no role.
- `tests/test_spa_serving.py` (**no edit — it is the guard**): it will go red the moment the atelier router lands without D19's `vite.config.ts` edit. Recorded so a builder seeing that red reads D19 rather than "fixing" the test.

**`db`-marked (real Postgres; no Docker locally, per the run's standing constraint. F34's and F57's shipped notes are the standard to meet: stand up a throwaway Postgres 16 cluster outside the repo, run every migration and execute these before pushing, and CAPTURE the deparsed constraint and index literals rather than transcribing them):**

- `tests/test_migrations.py` (**extended**): the table and its five nullable `TIMESTAMPTZ` stamps after this feature's migration; `effort_minutes`' CHECK pinned byte-identical via `pg_get_constraintdef`; the index pinned via `pg_indexes.indexdef`; forced RLS; the migration up **and down**.
- `tests/test_atelier_isolation.py` (**new — NON-NEGOTIABLE**, the `test_catalog_isolation.py` shape): tenant B's session sees zero of tenant A's tickets; every write verb against tenant A's ticket id from tenant B's context is a 404 indistinguishable from missing; a connection with **no** tenant context sees zero rows (RLS fails closed via `current_setting(..., true)::uuid` being NULL). *A new tenant table without this suite is a hole in the crown jewels — the E9 brief's words.*
- `tests/test_atelier_db.py` (**new**): the single-writer happy paths for all five stages; the idempotent re-advance; the undo's cleared column and its audit row; the delete's soft-delete predicate; the board read's window, cap and ordering against real rows; **and the four forced-interleave races below.**

**⚠ `asyncio.gather` is deliberately NOT used for any of the four**, for F34's and F57's reason verbatim (`test_booking_owner_db.py:1313-1336`, `test_floor_db.py:251-263`): gather does not **order** two transactions, so the loser most often loads *after* the winner commits, the in-memory instance is already correct, and the zero-row branch the test exists to prove goes green **without the mechanism ever being exercised**. The mechanism is `tenant_session`'s own shape — exiting the context manager **is** the commit (`db/tenant.py:25`), and two nested `tenant_session`s on one `NullPool` factory take two separate connections; under READ COMMITTED the loser's UPDATE and its re-read both see the winner's commit.

**The four races, and for each the EXACT mutation that must turn its test red** (each mutation must also be verified to leave **every other test green** — a mutation that reds three tests has not pinned anything specific, and F57's note records two mechanisms that would have shipped unproven):

| # | Test | Mechanism | **MUTATION → RED** |
|---|---|---|---|
| 1 | `test_a_concurrent_advance_to_a_later_stage_refuses_the_earlier_one` | the `AND <every later column> IS NULL` clause in `advance_stage`'s predicate | **Delete the later-columns clause.** The loser then stamps `qc_at` on a ticket already at `ready`; `assert stored.qc_at is None` reds. Every single-writer test stays green — which is exactly why this one must exist |
| 2 | `test_the_loser_of_an_advance_race_renders_the_databases_stage` | `populate_existing=True` on `_refreshed` | **Drop `populate_existing=True`.** ORM-enabled DML's `evaluate` synchronization has already stamped the SET value onto the identity-mapped instance the loser loaded, and `expire_on_commit=False` hands it straight back — so `assert stage_of(row) == TicketStage.READY` reds with `QC`. ⚠ It **must** be this shape: the loser's session has to have LOADED the row before the write, which `advance` does anyway to build the audit row's `from`. F57's note records that with only fresh-session tests present, removing this flag changed **nothing** |
| 3 | `test_two_seamstresses_claiming_one_ticket_leave_one_owner` | `AND assigned_staff_user_id IS NULL` in the claim predicate | **Delete the `IS NULL` clause.** The loser overwrites the winner; `assert stored.assigned_staff_user_id == winner_id` reds, and the 409 becomes a 200 |
| 4 | `test_two_intakes_for_one_new_phone_create_one_customer` | the `session.begin_nested()` SAVEPOINT + `IntegrityError` → `by_phone` re-read (D7) | **Delete the savepoint** (keep the `try`). The loser's `IntegrityError` has aborted the enclosing transaction, so the re-read raises `PendingRollbackError` and the test reds. A second mutation — **delete the whole `try`** — reds it with the raw `IntegrityError`, which is the 500 this guard exists to prevent |

**⚠ RACE #4 NEEDS ITS OWN SEAM — THE SESSION-ORDERING HARNESS ABOVE CANNOT PRODUCE IT, AND A TEST WRITTEN THAT WAY IS VACUOUS.** Races #1–#3 work under it because each loser's mechanism is a **single UPDATE** whose predicate is evaluated after the winner committed. `CustomersRepository.upsert` is **read-then-insert inside one call** (`customers.py:184-204`): `by_phone` → miss → `session.add` → `flush`. For an `IntegrityError` to fire, **both** sessions must miss before **either** inserts, and session ordering gives only two arrangements, neither of which is a test:

- **Loser held open first** → the loser INSERTs (uncommitted, holding the index tuple) and the winner's `flush` **blocks** on `idx_customers_tenant_phone_unique`, waiting on a transaction that cannot commit until the outer `async with` exits. Single-threaded asyncio: a hang.
- **Winner first, committed, then loser** → the loser's `by_phone` **finds** the committed row and returns it. No INSERT, no `IntegrityError`, the savepoint is never entered — **and the test passes identically with `begin_nested()` deleted.** The stated mutation does not red it, and the acceptance line *"two concurrent intakes for one new phone create one customer and two tickets"* is satisfied by plain sequential execution.

**The seam, named:** in `test_atelier_db.py`, monkeypatch the loser service's `CustomersRepository.by_phone` so that on its **first** call it returns `None` **and, as a side effect, commits the winner's customer row from a separate `tenant_session`**. That forces miss → winner commits → loser INSERTs → `IntegrityError`, deterministically, with no `gather`. Both mutations then bite against it. **If that harness is judged too costly, D7 already ranks this mechanism as the cuttable one — then the mechanism and the test are cut TOGETHER**, never the harness alone.

**Plus two non-race mutations:**

| Test | Mechanism | **MUTATION → RED** |
|---|---|---|
| `test_the_undo_audit_row_carries_the_stamp_it_destroyed` | the capture of the previous stamp into a **local, before** the write | **Move the capture after the write.** `evaluate` synchronization stamps `NULL` onto the very instance being read, so `details["previous_stamp"]` becomes `null` and the assertion reds. `test_floor_db.py`'s `test_the_end_audit_row_carries_the_timestamp_the_break_actually_started` is the shipped precedent, and F57's note records that this mutation leaves **all 17 fast tests green** because monkeypatched repositories never stamp anything |
| `test_the_loser_of_an_elevated_reassign_renders_the_databases_assignee` (db, **forced interleave**) | `populate_existing=True` inside `_refreshed`, applied to the **assign** path and not only to advance (D3) | **Drop `populate_existing=True` from `_refreshed`.** Two managers reassign one ticket; the loser's response carries **its own** assignee instead of the winner's, and `assert response.assigned_staff_user_id == winner_target` reds. Race #2 pins it for advance only — this is the row that stops the flag being re-scoped to one call site, which is the mistake `_refreshed`'s own docstring says has bitten this repo three times |

⚠ **`test_atelier_db.py` and `test_atelier_isolation.py` commit rows into a session-scoped container** (`migrated_db` and `app_role_url` are `scope="session"`, `conftest.py:73,83`). F57's D1 trap — *no committed `staff_users` row may hold a floor role* — **still applies to any `staff_users` row these modules seed**: seed assignees as `seamstress` only inside a transaction the test rolls back, or accept that `test_migrations.py`'s `test_adding_the_role_check_validates_existing_rows` (which re-adds **0011's two-value** CHECK on a populated table) will go red in a file that never mentions the atelier. **The safe shape: seed the assignee rows and roll them back, and where a committed assignee is unavoidable, assert on `assigned_staff_user_id` alone — nothing in this module depends on the assignee's role**, because the role check is `test_atelier_service.py`'s.

**Frontend (vitest):** `__tests__/AtelierSection.test.tsx` (**new**) covers the acceptance list above. Three assertions carry the whole legal load and must not be cut:

1. **The four focus moves** (D16) — advance-success into the new column, advance-failure onto the in-card alert, poll-clears-a-focused-alert back onto the card's control, and **delete onto the column heading**, since that card is gone and there is nothing to look up. Each is written so that deleting its focus line reds it — assert `document.activeElement` is the expected node, never merely that the node exists. The bug class has shipped three times and axe walked past it three times.
   - **Plus the two that are not focus but are the same class of invisible**: `{ArrowDown}{ArrowDown}` on either `<Select>` calls no API method (WCAG 3.2.2 — mutation: move the request back into `onChange`), and «מחיקה» calls no API method until the confirm is activated.
2. **SC 2.2.2** — the pause stops the loop, resume fetches before the interval elapses and at the **base** gap, the idle stop fires. **axe has no rule for 2.2.2**, so these are the sole automated coverage of a legal requirement and may not be dropped as redundant with the axe row.
3. **The live region is not written by a poll** — driven across **several consecutive ticks with the cue already populated**, because a single-tick assertion passes against the broken version whenever the cue starts empty (F34's F-7).

**No E2E**, and the reason is F34's and F57's verbatim: the console's entire e2e surface is two login-screen tests because `vite preview` runs with no backend (`e2e/a11y.spec.ts:10-13`). **F58 owns the `/manage/**` interception harness** and the floor-program review budgets it there as real work. Recorded rather than silently skipped.

---

## Out of scope

- **Capacity, load bars, overload flags, balanced assignment** — F42's, which extends this payload and adds `staff_users.weekly_capacity_hours` in its own migration. F41 computes no arithmetic over `effort_minutes` at all.
- **Split load and expedite** — the two remaining actions of the E9 brief's success criterion 3 (*"Reassign / split load / expedite are all human actions taken from the capacity matrix, each writes an `audit_log` row, and an expedite is stored explicitly (who, when)"*). **Reassign** ships here (D9 + `ATELIER_TICKET_ASSIGNED`); the other two do not. Neither is in F42's simplified build either — LOOP-STATE scopes F42 to `weekly_capacity_hours` + load bars — and if they land, both add **columns to `alteration_tickets` in F42's own migration**: `parent_ticket_id UUID` for split (the epic's *"parent/child link"*) and `expedited_at TIMESTAMPTZ` + `expedited_by UUID` for expedite (the epic's *"stored as an explicit `expedited_at` + actor so a queue that no longer matches date order still explains why"*), plus two `AuditAction` members. Named here so Risk 9's "an addition, not a rewrite" is read against the right F42.
- **The effort-band settings editor** — F42's (D8, Risk 4). F41 fixes the storage shape and the resolution rule.
- **Fitting appointments, `bookings.alteration_ticket_id`, the staff-booked appointment type** — F43's.
- **The live workshop board on the shop floor, throughput analytics, median time-in-state** — F44's, which reads the five timestamp columns directly and needs nothing from this feature's API.
- **A status enum, an event table, per-transition reason codes** — rejected by pre-decided #39 and by the 2026-07-31 ATELIER ruling, which calls the five-timestamp mechanism non-negotiable (D1).
- **Pricing, invoicing, deposits or any ILS amount on a ticket** — deliberately, per the E9 brief. Nothing in the roadmap or the PRD asks the workroom to charge, and money would drag this feature into Q1's user gate.
- **Photo attachments** — deliberately, per the E9 brief and the ruling.
- **Measurements as structured columns** — none exist. `notes` is free text and Risk 8 hands it to F20.
- **The bride's view of her alteration** — F24's client portal, which does not exist.
- **Any notification.** Nothing in F41 sends an SMS, queues a scheduled message or touches `comms_templates.py`. `i18n.test.ts`'s `/נשלח|תישלח|בדרך/` guard is what keeps a copy edit from claiming otherwise.
- **Reception and sales_assistant access** (D10) — one gate literal and one `NAV` row if the pilot asks.
- **A multi-stage undo, a stage-correction audit trail beyond `audit_log`, or restoring a deleted ticket** — D4's ceiling, named.
- **The F28 rental-reservation prefill of `due_date`** — the ruling says "later"; F28 is not built and is not a dep.
- **Retention enforcement.** F41 *flags* the record class (Risk 8); F20 owns the clock.
- **A language switcher** — deferred by the 2026-07-31 languages ruling; `ar` keys keep shipping untranslated.

---

## Codebase and program-state conflicts recorded

1. **The prompt says `main`'s head is migration `0015`; an earlier draft of this document "corrected" it to `0016`; it is `0017`.** F19 merged as `0016_deposit_flow.py` and **F53 merged as `0017_customer_crm_fields.py`** (PR #35, `d9f5d38`) — both on 2026-08-03, both after the numbers in LOOP-STATE and in this spec's first draft were written. That is the whole lesson, and it is why D14 states a **rule and no number**: a correction written down is stale by the next merge. `0017`'s own header records the live hazard better than any planning file can — *"the filenames differ, so git merges two same-revision migrations with no conflict at all… F33 is carrying `0016_queue_tickets.py` against a main whose 0016 is already taken, and will hit exactly this."* **Codebase-consistent reading taken.**
2. **The E9 brief calls the table `alteration_jobs`; this feature ships `alteration_tickets`.** `LOOP-STATE.md`'s F41 entry is titled *"Atelier tickets + kanban"*, its note says *"Row: customer, dress snapshot…"* about a ticket, and the assigned slug is `alteration-tickets`. LOOP-STATE governs where it and the epic disagree. Flagged so a reader who finds `alteration_jobs` in `e9-alterations.md` finds the rename here. Every downstream reference — F42's load query, F43's `bookings` column, F44's analytics — must use `alteration_tickets`; **F43's `alteration_job_id` becomes `alteration_ticket_id`.**
3. **The E9 brief names `wedding_date`; the ruling names `due_date` and this feature ships only `due_date`.** The ruling's reason is recorded verbatim in D1 — an evening gown has no wedding. Named because #39's row in the interview still says "wedding date" and a reader will find it.
4. **The E9 brief's five state names are `received / measured / in_work / ready / collected`; this feature ships `intake / in_progress / qc / ready / delivered`.** The 2026-07-31 ATELIER ruling supersedes the labels and **explicitly preserves the mechanism**. E9 had no QC state at all; the brief adds one, so the epic's Success Criteria row listing five names is stale on the names and current on everything else.
5. **F57's spec D10 predicts `usePoll`'s contract as `run: (isCurrent: () => boolean) => Promise<TickOutcome>`; the SHIPPED hook is `run: (generation: number) => TickOutcome` — synchronous.** `FloorPanel.tsx:155-163` returns `"suppressed"` / `"held"` / falls through to `void load()`. F41 codes against the shipped signature. Named because a builder reading F57's spec rather than the source would write an `async run` and get a `Promise` where a `TickOutcome` is expected, with no type error at the call site.
6. **F57's Risk 1 declares `test_the_floor_roles_reach_exactly_the_floor_routes` untouchable and forbids relaxing it to a subset check. F41 must restructure it.** D10 is the restructure and it preserves every property Risk 1 named (exact set equality, derived from the live route table, catches a lost gate, fails on a copy-pasted wide gate) while dropping the one assumption F41 makes false — that the three floor roles move as a block. **Doing this is compliance with Risk 1, not a reversal of it**, and the per-role table is what makes every future divergence a deliberate, reviewed edit rather than a relaxation.
7. **`CustomersRepository.upsert`'s docstring asserts a precondition F41 does not meet.** It is safe without a lock *"because every caller already holds the per-tenant advisory lock for the slot claim"* (`db/repositories/customers.py:187-189`; the name-update sentence is `:191-192`, and `by_ids`' quoted docstring is `:75-77` — **all three moved when F53 rewrote the file above `upsert`**, and every anchor in this spec has been re-derived against `main` at `18127e7`). F41 is the first caller that does not hold the lock, and D7 supplies the missing guard. The docstring should gain a sentence naming the atelier's savepoint path so the next caller is not misled by a precondition that is now conditional.
8. **Pre-decided #41 makes the E8 published roster (F40) the source of seamstress availability. F41 uses no roster at all.** The 2026-07-31 ruling drops F40 from F42's deps for this run and records the roster projection as the upgrade path; F41 never needed it, since it neither projects nor subtracts. Named so nobody schedules F41 against #41's dependency graph.
9. **Pre-decided #28 names E9 as a consumer of F34's staff↔client dispatch record; no such record exists.** F34 shipped `bookings.checked_in_at` and no assignment table. So the "seamstress opens a ticket on the bride she is standing with" intake path is a **typed name and phone**, not a handoff — recorded rather than silently dropped, and F58's dispatch is where it could become a prefill.
10. **Pre-decided #24's role slug is `sales`; the shipped enum is `sales_assistant`** (the 2026-07-31 roles ruling). F41 only ever names `seamstress`, but D10's `NON_ELEVATED_REACH` table names all three and would be wrong against #24.
11. **F53 (customers CRM) is MERGED, not "in flight in another session", and it moved five counted facts this spec's first draft pinned.** `SectionKey` is **twelve** members and F41's is the thirteenth; `NAV` is twelve rows and F41's is the thirteenth; `Nav.test.tsx` is owner eleven / shift manager nine *before* F41 and becomes **twelve / ten** after it; `MANAGE_API` names **thirteen** segments and F41's is the fourteenth; `main`'s head is **`0017`**; and `app/main.py` mounts **eight** `/manage` routers, so F41's is the ninth. A customer picker now exists and D7's original justification — that none did — was false; the reason that survives is that the picker's router is owner/shift-manager-only while F41 admits a seamstress to intake. Every one of these is a number a builder codes to directly, which is why they are listed rather than silently fixed. **`App.tsx:31`'s own comment (*"F57's floor — the ELEVENTH member"*) is stale in the shipped source** and should be corrected while the thirteenth is added.
12. **`test_the_floor_roles_reach_exactly_the_floor_routes` classifies on the INTERSECTION of the gates, and D10's new table must be written against that.** A `NON_ELEVATED_REACH` row naming `POST …/delete` for `seamstress` would red a **correct** build, because the per-route tightening removes her from that route's `effective` set. Recorded as a conflict rather than only as a design note because the earlier draft of D10 made exactly that error, and the red it produces lands on the one test F57's Risk 1 declares untouchable — the worst possible place for a builder to be guessing.

---

## Risks and open items

1. **`seamstress` now reaches NINE routes instead of three — three floor plus six atelier, `delete` excluded by its per-route tightening — and the per-role walker table is the only thing between the tenth and everything.** F31's gate default-denies by construction, so the risk is not that a seamstress leaks today — it is that a future `/manage` router copy-pastes the atelier's three-literal gate onto a surface answering customer data, or that a reviewer facing D10's restructured test relaxes a row instead of asking why. `NON_ELEVATED_REACH` must never become a subset check and no row may gain a route without the reviewer asking why. *Owner: team. Trigger: F42, F43 and F44 all add `/manage` routes, and F42 will want to extend this very router.*
2. **Consistently bad effort estimates make F42's alerts lie, and F41 is where the estimates are created.** This is the E9 brief's central accepted risk (Q13). The structural mitigations are here: five coarse bands rather than a minute field, so a bad estimate is bad by at most a factor of two; minutes persist so a re-tune cannot silently re-value history; and F44's median time-in-state is the measurement that eventually exposes drift. **The pilot's first weeks are unverified by construction** — there is no history to measure against. *Owner: the boutique owner — estimate quality is hers, and the pilot conversation should say so out loud rather than let her discover it.*
3. **A third 5-second poll enters the console and the per-tick cost is derived rather than measured.** **≈11 round trips**, 6 statements and 3 pool checkouts per tick per device on the atelier screen (D12's table, F34's D3 method — the earlier ≈13 counted a fourth statement for the effort bands, which D8 removed by reading them off `TenantContext.settings`). It replaces rather than adds to F57's board-screen number, since the console renders one section at a time — but `tenants.by_slug` is still uncached **per request** (`tenancy/resolver.py:8-9`, *"Caching is deliberately deferred to E5"*) and is still the single cheapest lever. **F29 must be handed this number, not left to discover it.** *Owner: team. Trigger: F29's k6 pass.*
4. **The effort-band mapping has a reader and no writer.** A boutique whose shifts are six hours cannot re-tune `half_day` without `psql` until F42 ships the settings block. The platform defaults are correct for an eight-hour day, which is the common case; the visible symptom of a wrong mapping is F42's load bars, which is also the feature that fixes it. **The writer is four edits, not one**, and F42's spec must size it as such: a third keyword on `TenantsRepository.merge_settings` (which today builds its patch from `profile` and `toggles` alone, `tenants.py:69-95`), an `atelier` field on `SettingsResult` **and** in `_settings_result` (`boutique/service.py:85-89`, which projects only those two back out), the `UpdateSettingsRequest` `ForbidExtraModel`'s `atelier` block, and its validator. *Owner: F42. Trigger: F42's spec.*
5. **A boutique whose owner sews cannot be assigned a ticket.** D9 refuses a non-seamstress assignee so F42's load bars cannot be blind to real work. One person holds one role, so the owner must either give herself `seamstress` (and lose owner-only access to staff CRUD, terms and the gateway) or leave her own work unassigned. **This is a real ceiling for a two-person boutique and it is not hypothetical in a pilot.** The cheap remedy if it bites: F42 treats "the owner" as an implicit capacity row, or D9 widens to any live staff row and F42 shows an "unassignable" bucket. *Owner: F42. Trigger: pilot feedback, or the first tenant with fewer than three staff.*
6. **There is no un-delete and no multi-stage undo.** A ticket soft-deleted by mistake is recoverable only through `psql`; a ticket advanced three stages by three mis-taps needs three undo calls. Both are deliberate (D4) and both are the crude end of a spectrum whose sophisticated end is a workflow engine #39 rejected. *Owner: team. Trigger: pilot feedback.*
7. **The audit rows are still write-only.** Six more actions nothing renders, and `previous_stamp` is the only surviving copy of a destroyed stage timestamp with no way to read it without `psql` (F15's Risk 7, inherited by F34, F51, F57 and now this). It matters slightly more here than there: the five timestamps are the feature's entire history, so an undo is the one write in the product that removes history into a table nothing reads. *Owner: user. Trigger: pilot feedback, or F53's activity log.*
8. **⚠ LEGALLY SENSITIVE — `alteration_tickets` is an e9 record class and `notes` may hold body measurements.** A bride's due date is personal data under PPL Amendment 13, and body measurements are the most intimate data this platform will ever hold. **F20 and F21 must carry an `alteration_tickets` entry from this feature's first migration**, and the E9 brief is explicit that the number must be **pinned here and not silently inherited**:
   - **Retention: 7 years, measured from `delivered_at`, or from `created_at` for a ticket never delivered.** Same number and same basis as bookings (pre-decided #10), because a ticket is a record of a commercial engagement of the same kind and a shorter clock would leave a booking describing an alteration whose own record had been purged. **Flagged for counsel confirmation at the F21 audit, exactly as #10 flags every number.**
   - **Scope for the PII scrub**: `notes` (free text, may contain measurements) and the `customer_id` link, which is scrubbed with the customer it points at. `dress_name` / `dress_size` are catalog facts, not personal data.
   - **`assigned_staff_user_id` keys on the ID and never on a name**, so pre-decided #34/#35's offboarding scrub — which blanks a departed seamstress's personal fields 7 years after her last day but retains operational history — cannot make F44's per-seamstress report lose rows.
   - **`audit_log`'s `ATELIER_TICKET_UPDATED` carries changed key NAMES and not values** (D11), so measurements never enter a second table with a second clock.
   *Owner: the user's lawyer confirms the number; the platform only enforces the clock. Discharged by F20, whose spec stops for the user anyway (`spec_gate: user`).*
9. **What F42 reads from this feature, named exactly, so its SIMPLIFIED capacity model is an addition and not a rewrite.** F42 as LOOP-STATE scopes it — `weekly_capacity_hours` + load bars — ships without changing a line of F41's data model. **That claim does NOT extend to the epic's split and expedite actions**, which add columns to `alteration_tickets` in F42's own migration and are named in Out of scope; a reader planning F42 against this list alone would size it wrong.
   1. `SELECT assigned_staff_user_id, SUM(effort_minutes) FROM alteration_tickets WHERE tenant_id = :t AND deleted_at IS NULL AND delivered_at IS NULL GROUP BY assigned_staff_user_id` — **"not yet delivered" is `delivered_at IS NULL`**, one column, no derivation and no stage enum.
   2. `alteration_tickets.assigned_staff_user_id` as the grouping key, and **`NULL` as a real bucket** — the unassigned pile is the first thing a capacity view must show. ⚠ **F42 must render a SECOND anomalous bucket beside it: a non-assignable or unknown assignee.** D9's seamstress-only check runs once at assign time and F51's shipped staff CRUD rewrites `role` (`staff_users.py:114`) and retires staffers with no knowledge of this table, so the column is a point-in-time-validated pointer and never a live guarantee. D12's `seamstresses[]` already carries the `assignable` flag F42 needs to label it.
   3. `staff_users.weekly_capacity_hours` — **F42's own new column in F42's own migration.** F41 adds nothing to `staff_users`.
   4. **The `seamstresses[]` array in this feature's envelope** (D12), to which F42 adds `weekly_capacity_hours` and `assigned_minutes` members and by which it sorts the assign picker by remaining capacity. **F42 must not add a second poll loop** — it extends this payload, which is F57's D11 rule for the floor and the reason `AtelierBoardResponse` is an envelope rather than an array.
   5. **`AtelierService.assign`** — F42 adds an advisory overload **flag** to its response and **never a refusal** (pre-decided #40: every reallocation is a human action).
   6. The index F42 will want, `(tenant_id, assigned_staff_user_id) WHERE deleted_at IS NULL AND delivered_at IS NULL`, is **deliberately not shipped here** (D1) and belongs in F42's migration.
   *Owner: F42's spec. Trigger: it is the next feature and it deps on this one.*
10. **No E2E covers the poll loop, and there are now three of them in the console.** All three are unit-tested with fake timers against a mocked `api`; none is exercised against a real backend, and the interaction most likely to differ in reality — a slow tick on boutique wifi while a mutation is in flight — is exactly what fake timers model least faithfully. F34's Risk 8, widened twice. *Owner: team. Trigger: F58, which builds the `/manage/**` interception harness.*
11. **`ar.ts`'s parity guard is real, and the risk is the FOLD, not the guard.** F15's Risk 5 has been discharged since F52: `i18n.test.ts:417-420` asserts every `HE` key exists in `ar.translation`. But `HE` is a hand-assembled union (`:48`) and **a block that is declared and not spread is skipped by that guard and by both register guards, silently and greenly** — the failure the file records for F52 and that F53 now asserts against explicitly. F41 adds ~70 keys to both files by hand and its whole exposure is one missing `...HE_F41`. D18 pins the fold and the acceptance list asserts it. *Owner: this feature, not a later one.*
12. **A boutique that re-roles or offboards a seamstress leaves live tickets pointing at a non-seamstress.** D9's check is a write-time nudge and `staff_users` has two shipped writers that know nothing about it. F41 makes the state **visible** (`assignable: false` on the wire, «תופרת שאינה פעילה» on the card) rather than correct; correcting it would need a re-validation sweep on every role write, which is F42's call to make when it can measure what the bucket costs. *Owner: F42. Trigger: the first offboarding in a pilot with an open board.*

---

## Decisions Log

- **D1 — `alteration_tickets`: one new tenant table, five nullable stamps, one partial index on `(tenant_id, due_date) WHERE deleted_at IS NULL`, `enable_tenant_rls` + `GRANT` + the shared `update_updated_at` trigger.** Declined a `status` column (the timestamps ARE the trail and two representations of one fact desynchronise — F57's D2 argument); an event table (rejected by #39, and it would cost a second tenant table with a policy, an isolation suite and an F20 row); any unique index (two tickets for one bride is legitimate); indexes on `assigned_staff_user_id`, `customer_id` or any stamp (the feature that measures the query buys the index — F42 has a migration of its own, and F53's has already shipped without wanting one); a second `wedding_date` column (the ruling says `due_date` subsumes it). Constraint and index literals are **captured by running them**, never transcribed — Postgres deparses.
- **D2 — The state is the RIGHTMOST stamped column, `stage_of` is total with `intake` as the floor, and a NULL earlier stamp means "never separately recorded".** All five declared nullable including `intake_at`, so no reader has to know which one is special **in the DDL** — but `intake_at` is stated as structurally non-null and immutable (stamped by the INSERT, never cleared, equal to `created_at`), so F44 does not read its non-NULL as evidence the way it reads the other four. Forward skips are legal and legible through the audit row's `from`/`to`; backwards is unrepresentable because D3's predicate refuses it, not because a CHECK forbids it — a DDL ordering chain would forbid the legitimate skip too. **F44 must treat a NULL as "no observation", never as zero.**
- **D3 — One conditional `UPDATE … WHERE <target> IS NULL AND <every later column> IS NULL … RETURNING id`, plus one `populate_existing=True` re-read, mapping to four total outcomes (200 / 200-unchanged / 409 / 404).** The later-columns clause does two jobs in one predicate: it refuses a stale backwards stamp and it refuses the loser of a real race, in the database rather than in a pre-read another transaction can invalidate. Three-valued rather than F57's `(bool, row)` because zero rows here has two **opposite** causes — the condition F57's D7 named as the day an enum would earn its keep. No advisory lock (one column, one row, the predicate is the whole invariant). **The zero-row discriminator is ONE EQUALITY AND ONE ELSE**: an earlier stage on the re-read is reachable through a concurrent undo (READ COMMITTED, and a zero-row UPDATE takes no lock), so `elif stage > target` with no else returns `None` and 500s the hottest mutation in the feature. **`_refreshed` is one method applied UNCONDITIONALLY to every write path** — advance, undo, assign, update, delete — because all six load the row first for their audit row and all six answer the full ticket; the shipped `_refreshed` docstring says per-call-site reasoning is what has bitten this repo three times. **D3 also carries the seamstress's per-verb rule** (advance/undo on her own *or an unassigned* ticket, because that is recording work she just did; `update` on her own only, because a due date is a scheduling decision).
- **D4 — One undo verb that clears the RIGHTMOST stamp, names the stage it intends to clear, and writes the destroyed timestamp into `audit_log`.** The client naming the stage is what makes a stale board harmless. **Its zero-row discriminator is D3's**: 200 no-op **iff** the named column is NULL *and every column after it is NULL too*; otherwise 409. The two branches an earlier draft listed were not disjoint, and the overlap is reachable with no concurrency at all through D2's legal forward skip. `intake` cannot be undone (it would leave a lie with no upside; the remedy is delete). The previous value is **captured into a local before the write** — the ORM stamps `NULL` onto the instance being read, and a capture-after-write empties the row it exists to fill (`floor/service.py:108-116`, a named mutation target). Declined multi-stage undo.
- **D5 — `due_date` is a `DATE`; `overdue` is computed on read as `delivered_at IS NULL AND due_date < today_jerusalem(clock)`.** A calendar day the bride names, not an instant — the one place `Asia/Jerusalem` is permitted. Compute-on-read is the house pattern with three shipped precedents; a stored boolean needs a worker at Jerusalem midnight and races a concurrent delivery. The clock is injectable, `DashboardService`'s and `FloorService`'s shape. **The bounds are asymmetric and both are pinned: NO lower bound at all** — a past `due_date` is a 200 on create and on update, #40's advisory rule, and the past-date warning is a client affordance with no `min` attribute — **and an upper bound of `today + MAX_DUE_DATE_HORIZON_DAYS` (730)** as a typo fence, because `DATE` accepts year 9999 and F42's arithmetic consumes this column unbounded.
- **D6 — The dress is `0008`'s three snapshot columns and its exact reasoning; the customer is a pointer, not a snapshot.** `dress_name` is server-copied from `dresses` when `dress_id` is given and client free text when it is not (a gown the bride already owns has no catalog row); `dress_size` is never validated against `dress_variants`, which is the stock question, not the measurement one. No customer snapshot because `customers.name` only drifts toward the truth and `bookings` already made this call. **`customer_name` on the wire, no phone** — a deliberate minimisation for Risk 8.
- **D7 — Intake resolves the customer through `CustomersRepository.upsert` wrapped in a `session.begin_nested()` SAVEPOINT with an `IntegrityError` → `by_phone` re-read.** F41 is the first caller of `upsert` without the booking path's advisory lock, and the method's own docstring says that is the precondition. Declined an advisory lock (serialises every intake to protect a first-ever-phone collision); declined rewriting `upsert` to `ON CONFLICT` (three shipped callers on the booking path); declined swallowing the error without an `is None` re-raise. **Ranked as the cuttable one of the four races**, with its ceiling stated.
- **D8 — The wire carries a BAND KEY; the server resolves minutes from `tenants.settings["atelier"]["effort_bands"]` with per-band platform defaults; the row stores MINUTES.** The client never sends a number, which is what makes "five bands, not a minute field" structural. A brand-new boutique has no key and gets the five defaults; a partial or corrupt mapping falls back **per band** so a hand-edited blob cannot write a negative estimate. Minutes persist so a re-tune cannot silently re-value history — the E9 brief's own sentence, and the reason there is no `effort_band` column. **The read is `TenantContext.settings` off the request** (`tenancy/middleware.py:46`), resolved in the router and passed in as a dict — reading it through `TenantsRepository` would open a fourth session on a five-second poll, because that repository opens its own session per method and cannot join the request's. **F41 ships no editor and F42 owns it**, because the tuning only changes an answer F42 computes — and no shipped writer can even reach the key: `merge_settings` takes `profile=` and `toggles=` alone, so F42's writer is four edits (Risk 4).
- **D9 — Assignment has two axes: elevated is unconditional last-write-wins; a seamstress's self-claim is a conditional `WHERE assigned_staff_user_id IS NULL` and her release is `WHERE assigned_staff_user_id = :her`.** The elevated path takes no 409 because a manager reassigning is making a call #40 says is hers. The target must be a live **seamstress** — not gatekeeping for its own sake, but because F42's load bars group on this column and a ticket assigned to a receptionist is work no bar will ever show (Risk 5 carries the ceiling and the escape hatch). **That check is a write-time NUDGE and not an invariant**: F51's shipped `StaffUsersRepository.update` rewrites `role` unconditionally and `soft_delete` retires her, so `assigned_staff_user_id` is a point-in-time-validated pointer. D12's `seamstresses[]` is therefore a **union** carrying an `assignable` flag, and Risk 9 hands F42 the obligation to render the anomalous bucket. **The claim's zero-row discriminator is D3's one-equality-and-one-else**, because the re-read can show `NULL` after a winner claims and releases. The authorization check runs before any read on the pure-role refusals, so the 403 is not an existence oracle; where the rule depends on the ticket's own assignee the generic `NotAuthorizedError` body is what keeps it from disclosing.
- **D10 — `app/atelier/` is the NINTH `/manage` module, gated `require_role(OWNER, SHIFT_MANAGER, SEAMSTRESS)` at router level with `delete` tightened per-route, and `test_the_floor_roles_reach_exactly_the_floor_routes` is RESTRUCTURED into a per-role set equality.** ⚠ **`ATELIER_DELETE` is split out of the seamstress's row**: the walker classifies on `frozenset.intersection(*role_sets)`, so delete's effective set is `{owner, shift_manager}` and a row naming it would red a correct build on the one test Risk 1 declares untouchable. The anti-vacuity half keeps the **full** `FLOOR_OPEN | ATELIER_OPEN`. `RoleGate` composes by intersection, so a route on an existing router can only be narrowed — F57's D4 argument, now shipped in `floor/router.py`'s docstring. Three literals rather than `*StaffRole` because the atelier's set is not "every role the product has" and a sixth role must be refused here by default. The walker restructure preserves every property F57's Risk 1 named and drops only the assumption F41 makes false — that the three floor roles move as a block. Declined admitting reception and sales_assistant (the workroom is not a floor surface; one literal if the pilot asks).
- **D11 — Six `AuditAction` members, no migration (`audit_log.action` is plain TEXT, the seventh block to rely on it).** No-ops write no row. **One `STAGE_ADVANCED` value rather than five**, because the questions this table gets asked are "who moved it and when" — both one `WHERE` — while "how many reached delivered" is answered from the **timestamp columns** per #41, which is the whole point of #39's mechanism. `UPDATED` carries changed key **names** and not values, so a bride's measurements never enter a second table with a second retention clock.
- **D12 — One `GET /manage/atelier/tickets` returning an ENVELOPE: undelivered tickets plus the last 7 days of delivered, ordered `due_date, created_at, id`, capped at 500 with a `truncated` flag, alongside `seamstresses[]` (a **union** with an `assignable` flag) and the tenant's resolved `effort_bands[]`.** The `id` tiebreak is `customers.search`'s stated reason, not decoration: `created_at` defaults to transaction start time and the test fixtures seed several tickets per transaction, so without it the order Postgres returns is plan-dependent and the acceptance test is flaky by construction. Three business statements per tick, not four — the bands ride on `TenantContext.settings`. The delivered window stops a live poll shipping a boutique's whole history; the cap bounds the undelivered side, and ordering by due date means truncation drops the least urgent. Declined merging into `/manage/floor` (that gate admits five roles and this payload carries a customer's name — F57's D11 security argument, mirrored); declined a `?stage=` filter (five requests per tick); declined a detail endpoint (a second round trip for data already on the client). **F42/F43 extend this payload; nobody adds a third loop.**
- **D13 — Two new error codes, `TICKET_STAGE_CONFLICT` and `TICKET_ALREADY_ASSIGNED`, both 409, both with their own handler and body.** Two and not one because the console's copy and the user's next move differ — a garment moved on versus a person took it — and collapsing them into the shipped generic `CONFLICT` would make the client branch on a message string. Everything else reuses `NotAuthorizedError`, `DomainNotFoundError` and `DomainValidationError` with their shipped handlers; a `SPEC_ERROR_CODES` set equality stops a third arriving unnoticed.
- **D14 — One migration whose revision id is resolved from `alembic heads` IMMEDIATELY BEFORE the rebase that precedes the push, built at head+1 so the branch is self-coherent and its `db` tests run, made the LAST commit so the renumber costs one amend, and verified to leave exactly ONE head.** `main` is at **`0017`** today (F19 → 0016, F53 → 0017, both 2026-08-03) and features are still racing; any number in this document is stale before the build starts — this entry has already been corrected twice. The ORM model is the second half of the migration and is not optional — no model↔migration parity test exists anywhere in `Backend/tests/`.
- **D15 — `AtelierSection.tsx` owns all its own state and its own `usePoll` instance, imports the hook unmodified, and carries every one of F34's D4 mechanisms including both shipped loop fixes.** The unmount fix (`runningRef.current = false` before `clearTick()` in cleanup) and the StrictMode-idempotent mount effect (`runningRef.current = true` as the first line) both live inside the hook and this section must not defeat either. Caller-owned pointer hold → `"held"`; caller-owned `mutationsRef` → `"suppressed"`; the single re-arm in the mutation's `.finally()` and not its success path; `poll.fail(error)` making a mutation's 403 terminal; never optimistic — every mutation answers the full ticket.
- **D16 — NO DRAG AND DROP ANYWHERE. The accessible path IS the interface: an advance button, a native `<select>` of later stages plus a commit button for a forward skip, an undo button, an assign control, an edit button and a delete button behind a confirm, inside five NAMED `<section>`s of NAMED `<ul>`s.** Every accessible DnD is a keyboard alternative bolted onto a gesture, so the button path gets built either way; WCAG 2.5.7 requires the single-pointer alternative regardless. ⚠ **NOTHING MUTATES ON `change`** — a closed native `<select>` fires `change` on every arrow keypress, so an onChange-mutating skip control would write three timestamps and three audit rows while a keyboard user was still choosing (WCAG 3.2.2, and the first `<Select>` in this console to break the shipped draft-state convention). ⚠ **Every control is `size="md"`; `size="sm"` is barred** (36 px against a 44 px floor). **A successful advance MOVES the card to another column and a delete removes it entirely, so the focus drop is structural rather than accidental** — focus goes to the same ticket's control in its new column, to the column heading when the card is gone, to the in-card alert on failure, and back to the card's control when a successful poll clears a focused alert. Four named, non-vacuous tests, because this bug class has shipped three times and axe cannot see a focus move that never happened.
- **D17 — A third auto-updating surface, so its own SC 2.2.2 pause/resume and idle stop, its own region-naming copy, and D11's live-region rule inherited whole.** Level A inside a legally binding AA (pre-decided #38) and **axe has no rule for 2.2.2**, so the named vitest assertions are the sole automated coverage and may not be cut as redundant with the axe row. The pause control is the first stop inside the section, before any card. The poll never writes into the announced region, and the cue is written only when its value actually changes — which the test must drive across several consecutive ticks with the cue already populated. **The cue's TEXT is declared copy and asserted, not merely its change**: for a screen-reader user the cue *is* the card's move across a column, so `atelier.cue.advanced` names the ticket and its destination stage and the test reads `getByRole("status")`'s textContent. **Overdue carries the WORD «באיחור»**, never colour alone; the E9 Risks name colour-only urgency as this epic's hard accessibility case.
- **D18 — A new `atelier.*` namespace plus `nav.atelier` in both `he.ts` and `ar.ts` (Hebrew standing in untranslated), and the stage word becomes `Record<TicketStage, string>` in `lib/`.** The `Record` makes a missing member a compile error while an i18n test makes a missing key a red test — `lib/roles.ts` exists because a two-branch ternary silently labelled a seamstress «אחראית משמרת». Reuse a key whose **namespace names its subject**, never one whose namespace names a screen (F57's F-10). ⚠ **`HE_F41` is DECLARED AND SPREAD INTO `HE`** — the `ar` parity guard (`i18n.test.ts:417-420`, which does exist and has since F52) and both register guards iterate that hand-assembled union, so a declared-but-unspread block is skipped silently and greenly; the fold itself is asserted, F53's shape. Every per-card control carries a **disambiguating** accessible name containing its visible label, `<Select>`s included — the component names itself from its required `label` prop alone, so 30 cards would otherwise expose 30 identically-named comboboxes. Clears the shipped `/נשלח|תישלח|בדרך/` guard trivially and by construction — F41 sends nothing — and the no-empty-`ar` guard by rule. No new formatter: `plainDate` renders a wire calendar date and its header states the rule this feature must not break.
- **D19 — `atelier` is added to `MANAGE_API`'s alternation in `apps/manage/vite.config.ts` as the FOURTEENTH segment** (thirteen today, the file's own comment names the number). `test_spa_serving.py::test_the_manage_dev_proxy_names_every_manage_api_segment` derives the segment set from the live route table and asserts **set equality**; without the edit, production, CI and the whole suite stay green while only a developer's machine breaks, serving the SPA shell where the API should be. It has bitten this repo twice. One word, and its own decision so the plan carries it as a task.

---

## Rejected findings

Three claims from the review are **not** applied, all from the same citation-cluster finding. Each was checked against the shipped source at `18127e7` and the spec's original anchor is correct.

1. **"`csrf.py:48` → the `request.method in MUTATING_METHODS` gate is `:47`." REJECTED — it is `:48`.** `:46` is `class CsrfOriginMiddleware`, `:47` is `async def dispatch`, `:48` is the gate. The shipped `app/floor/router.py` docstring cites `:48` for the same sentence; changing this spec's anchor would put it out of step with the module F41 copies.
2. **"`0003_auth.py:83-84` → the GRANT/RLS loop is `:85-88`." REJECTED — `:83-84` is what D14 actually cites.** D14 cites this as the precedent for a **table-level GRANT with no column list**: `:83` is `for table in ("staff_users", "sessions", "audit_log"):` and `:84` is the `GRANT SELECT, INSERT, UPDATE, DELETE ON {table}`. The `enable_tenant_rls` loop is `:85-86` and is a different statement, cited separately in D1.
3. **"`auth/dependencies.py:44-45` → the intersection sentence is `:43-44`." REJECTED — it is `:44-45`.** `:43` is blank; `:44-45` is *"Applied router-level as the default posture and per-route to tighten (both gates run; FastAPI's per-request dependency cache resolves the session once)."* The shipped walker test and `floor/router.py` both cite `:44-45`.

Everything else in that finding — the `DomainValidationError` / `DomainNotFoundError` handler pair (`main.py:795-799` / `:801-805`), `_settings_result` (`:85-89`), `models/tenant.py:21-23`, `list_live` (`:37-45`), the walker's `:240-302`, `dress_variant.py:11`, `0008_bookings.py:52-57`, and `booking/owner.py:326-333` being `list_slots` rather than the capture-before-write trap — is applied. The last of those is worth its own note: **the shipped `app/floor/service.py:114` comment carries the same stale pointer**, so a builder following it lands on the wrong function. F41 does not propagate it and does not fix it in passing.
