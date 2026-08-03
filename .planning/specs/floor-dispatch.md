# Spec: F58 — Waitlist panel + dispatch (take-next, push-assign, finish, skip, call) (Epic E6, floor program iteration 5)

**Spec review (2026-08-03, round 1)**: 32 findings from 3 lenses (the brief said 33; the list carried 32 entries, 6 of them the same defect seen by two lenses) — **32 applied, 0 rejected**, 3 applied in a narrower form than proposed and recorded as such in «Rejected findings». Three BLOCKERs and one MAJOR changed a *design* rather than a *sentence*: the take-next rollback proof (D3a), the shared 409 helper (D3a/D12), the skip statement (D6) and the announced cues (D16). Everything the review touched was re-verified against the shipped tree first — and that pass found four facts the spec asserted that had gone stale since it was written, all corrected here.

**Created**: 2026-08-03 · **Gate 1: standing approval — `interview-2026-07-30.md` §Standing approvals** (Q1's enumerated exceptions are F17, F18, F19, F20, F29, F48; F58 is none of them — no payments, no refunds, no privacy-law text, no billing. The one privacy-law string this program owes anyone, F33's collection notice, is already parked in `in_run_gates` and F58 neither writes nor reads it) · **Design gate: self-approved (ruling 2026-07-31)** — Interview Q2 names exactly two novel patterns for this run, F34's shift board and F42's capacity matrix. The waitlist is a list of people with three controls per row, assembled from `@boutique/ui`'s shipped `Card`, `Badge`, `Button` and `Modal` and mounted inside F57's shipped `FloorPanel`. No prototype and no `design-critic` pass gate this build; the design work is still build tasks (D17, D18). · **Effort**: **L** — one `ALTER TABLE` adding one column, five new routes on a router that already exists, one shipped route extended, two repositories extended, one payload extension, one new console panel, one shipped storefront component corrected, and the transaction design that is the reason this is not an M.

**⚠ THIS FEATURE DISCHARGES TWO DEPLOYMENT GATES.** `LOOP-STATE.md` `deployment_gates` records that **F33 (merged, PR #36) and F59 (building) are both merged-but-not-launchable until F58 ships**, and names F58 as `cleared_by` for each. Concretely, the day this merges:

| Gate | Why it was raised | What discharges it here |
|---|---|---|
| **F33** — "merges and is fully tested, but is NOT enabled for a live pilot tenant" | (1) F33 writes queue tickets **no shipped surface renders**; (2) a duplicate ticket is a normal outcome of Ruling 3 and **nothing can merge or remove one**; (3) the position page's success terminal is **unreachable**, because nothing in the product writes `done` or `removed` | (1) **D2** — the waitlist joins `/manage/floor`; (2) **D8** — the remove verb plus **D9**'s duplicate flag; (3) **D5/D6** — `release` closes the ticket to `done`, the second skip writes `removed` |
| **F59** — "merges, but the TV does not go on a wall" | Inherits F33's gate and sharpens it into a privacy point: with no writer for `called_at` or `status`, nothing is highlighted, the board only grows, and the day's five earliest check-ins are on a public screen from ~09:15 to midnight | **D7** — `call` stamps `called_at` and **leaves `status = 'waiting'`**, which is the contract F59's D10/Risk 6 records that it cannot enforce for itself; **D3/D4/D6/D8** give the status column its four writers, so rows leave the board |

**F20's retention gate on F33 is NOT discharged by this feature and stays open** (`qr-walkin-queue.md` «Deployment ordering», row 2). F33 carries two preconditions; F58 clears one.

**Depends on**: **F33** (`queue_tickets`, `app/queue/`, `QueueTicketStatus`, `position()`'s published ordering, `TicketView`, `QueuePositionPage.tsx`) · **F36** (`fitting_room_assignments`, its two partial unique indexes, `violated_index()`, `FloorService.claim`/`release`, `RoomsPanel.tsx`, `FloorResponse`) · **F57** (`app/floor/`, `FloorPanel.tsx`, `usePoll.ts`, the widened `StaffRole`, `test_staff_role_gating.py`'s `FLOOR_OPEN`) · **F34** (D4's six poll mechanisms, the `{401,403}` terminal rule, D11's live-region rule, D14's SC 2.2.2 control) · **F31** (`require_role`, `RoleGate`'s **intersection** composition and the default-deny walker)
**Feeds**: **F59** (its wall board highlights `called_at` and its five rows finally turn over) · **F37** (SOS attaches to `fitting_room_assignments`, whose rows this feature also creates — the alert pointer is unchanged, D5) · **F20** (the retention sweep now has terminal statuses to sweep on, and one more consent-bearing surface to describe)

## What F58 does *not* do

It does **not** add a table. It does **not** add a second poll loop, a second pause control, a second announced region or a second `usePoll` instance — the waitlist **extends F57's `/manage/floor` payload** (`LOOP-STATE.md`, F58 `note:`, in as many words) and `WaitlistPanel` is a **child** of the shipped `FloorPanel`, exactly as `RoomsPanel` is (D15). It does **not** rebuild the staff cards, the room tiles, the freshness line, the dress bindings, the registry, the handover or the pickers. It does **not** touch `position()`, the public `/storefront/checkin` routes, the three check-in limiters, the QR sheet or the collection notice. It ships **no wait-time analytics** (pre-decided #28) and **no bride-priority ordering** (`e6-instore-realtime.md:74` — still an open product question; `visit_type` is rendered and nothing sorts on it).

---

## Problem

`queue_tickets` has 1 writer and 0 readers on the staff side. That sentence is the whole feature.

Verified against the shipped code rather than asserted:

- **`app/db/repositories/queue_tickets.py` has four methods and no writer but `insert`** — `insert`, `by_id`, `position`, and F59's `board` — and `insert`'s docstring says out loud what is missing: *"`status` and `skip_count` are left to their DB defaults — F33 writes no transition and F58 owns every one of them"*.
  ⚠ **STALE FACT CORRECTED AT REVIEW: `board` and the two module-level helpers `_live_waiting()` / `_sort_key()` landed with F59 (PR #38, merged) after this spec was drafted.** `_live_waiting`'s docstring is written *at this feature*: *"Both readers bind these four and they are ONE expression rather than two copies … Two copies that drift — **F58 widening one status filter, say** — put a different number on the wall from the one on her phone, and nothing about that failure looks like a bug until a customer says so."* D2 therefore **calls those two helpers rather than re-spelling their predicates**, and that is now a shipped instruction rather than this spec's taste.
- **`app/models/constants.py:96-108`** says it a second time on the enum: *"F33 writes only the WAITING default — every transition out of it is F58's, which is why nothing in the shipped product can currently reach a terminal."*
- **`app/models/queue_ticket.py:43-56`** says it a third time, per column: `called_at` is *"Stamped when a manager calls her forward … even though F58 writes it"*; `requeued_at` is *"F58's skip-to-back"*; `skip_count` is *"F58's second-skip rule. Neither reader nor writer in F33."*
- **`backend/migrations/versions/0019_fitting_rooms.py`** says it a fourth time, in the DDL: *"`queue_ticket_id` is deliberately ABSENT. The walk-in's dispatch record is F33's `queue_tickets` and the dispatch action is F58's; F58 adds the column in its own migration alongside its writer."*
- **`app/models/queue_ticket.py:23-26`** says it a fifth time, and this one is a liability rather than a plan: *"There is no uniqueness of any kind beyond the primary key: a second ticket for the same phone on the same day is a real, expected outcome, and F58 merges or removes it. That is what closes the presence oracle."*

Five files are written against this feature's arrival, and until it lands the consequences are not theoretical:

1. **A woman scans the QR and lands in a table nobody can open.** `GET /manage/floor` answers `{staff, rooms, server_now}` and nothing else. The console has thirteen floor routes and not one of them can see the queue.
2. **Ruling 3 traded server-side dedup for duplicates, and the buyer has not paid.** The trade was explicit and correct — the dedup index was a free, silent, unbounded presence oracle *and* a day-long denial with no remedy — but its stated price was *"a duplicate ticket is now a real, expected outcome, and F58 merges or removes it"*. Nothing does.
3. **Her phone can never say the visit ended.** `QueuePositionPage.tsx:35` stops the loop on `status ∈ {done, removed}`. Neither is reachable. Every open tab polls until it is closed.
4. **F59's board is a monotonic list of the day's earliest arrivals.** `deployment_gates` states the privacy consequence in the sharpest available terms: a woman who arrived at 09:00 and left at 10:00 is still on an unauthenticated public URL at 17:00, which is not «לצורך ניהול התור בלבד» — the exact purpose limitation the shipped notice promises her.

**What is dangerous here is not the panel.** It is that **take-next is the one action in this product where getting the concurrency wrong is visible to a customer**, and it has two failure modes rather than one. Two managers pressing it at the same instant must not get the same woman — that is the drain pattern, and it is well understood. The second is subtler and worse: take-next writes to **two tables**, and a design that lets the ticket's write survive the assignment's failure strands her `in_service` with no room, on a status that no verb in this feature can leave — invisible on the waitlist, invisible on the wall board, and her own phone reading «התור שלך התחיל» forever. **D3a is where that is proved impossible rather than promised.**

## Goal

A manager opens the floor screen and sees, under the room tiles, everyone waiting: a name, what she is here for, how long she has been standing there, in arrival order. She taps «קחי את הבאה» on a free room and **that room is hers and the first woman in the queue is in it** — atomically, so a colleague tapping the same instant gets the *second* woman or a clean «אין ממתינות בתור», never the same one twice, and never a customer marked in-service with nowhere to be. She can call someone forward without dispatching her, which is what turns the wall board's highlight on. She can send a no-show to the back of the queue; a second skip removes her. She finishes a fitting with the control she already uses, and the room frees and the visit closes together.

F58 ships **one migration (one `ALTER TABLE`, one column)**, **five new routes**, **one shipped route extended**, **four `AuditAction` members**, **three new error codes**, **one payload extension**, **one new console panel**, **one three-line correction to a shipped storefront component**, and — because the console has no coverage behind its login screen — **the reusable Playwright `/manage/**` interception harness** (D19).

## What already exists to build on (verified against code)

- **The floor router is shaped for exactly this.** `app/floor/router.py` mounts `prefix="/manage"` with `dependencies=[Depends(_no_store), Depends(require_role(*StaffRole))]` (`:126-132`) and its docstring already argues every decision F58's routes would otherwise re-argue: all five roles at router level, four routes narrowed per-route by an `ELEVATED` constant that *"composes by INTERSECTION … so it can only narrow"* (`:167-173`), tenant from `get_current_tenant(request)` and never `StaffContext.tenant_id`, a fifth local `_no_store` copy, no rate limiter, real HTTP verbs and a path parameter for the target.
- **`FloorResponse` was built as an envelope FOR THIS FEATURE, and says so.** `app/floor/schemas.py:7-11`: *"The read is an ENVELOPE, not a bare array … this one is the FLOOR's, and F36 adds rooms and occupancy to it **while F58 adds the waitlist**. An envelope makes those additive."* `api.ts:447-448` mirrors the sentence on the client. D2 is the promised addition.
- **`position()` publishes the ordering and F58 must not change it.** `db/repositories/queue_tickets.py:59-89`: 1-based among the WAITING tickets of the ticket's own `queue_day`, ordered by `COALESCE(requeued_at, created_at)`, counted as `count(sort_key < mine) + 1`, never stored. Its docstring records why the day comes from `ticket.queue_day` and never from a clock, and F59's D3 already established the rule this feature inherits: **any second reader of that order must use a byte-identical predicate set, not an equivalent-looking one.**
- **`FittingRoomAssignmentsRepository.claim` is a CORE `session.execute(insert(...))` and the docstring says why.** `db/repositories/fitting_room_assignments.py:77-86`: with `session.add` the flush happens inside `AsyncSessionTransaction.__aexit__`, so the `IntegrityError` surfaces when the block EXITS and a `try` placed inside it catches nothing. *"This repository raises. The SAVEPOINT is the service's."* D3 spends that last sentence.
- **`violated_index()` is already correct and must be reused verbatim.** `db/repositories/fitting_room_assignments.py:21-43` — `getattr(getattr(error.orig, "__cause__", None), "constraint_name", None)`, with the whole of why `exc.orig.constraint_name` is always `None` written on it. F36's shipped note records that the obvious spelling made **every 409 a 500** with the happy path green. F58 discriminates the same two indexes and imports the same function.
- **The two partial unique indexes and their count are pinned.** `0019_fitting_rooms.py` creates `idx_fitting_room_assignments_room_active` and `…_staff_active`, both `WHERE released_at IS NULL AND deleted_at IS NULL`; `test_migrations.py:1581` pins all three unique definitions byte-identical, and **`test_fitting_room_assignments_carries_exactly_two_non_primary_unique_indexes` (`:1617`) asserts the count is exactly 2**. D1 is bounded by that test rather than by taste.
- **`test_the_fitting_room_tables_carry_no_check_constraints` (`test_migrations.py:1648`)** asserts zero CHECKs on all three F36 tables. D1's `ALTER TABLE` must add none.
- **`queue_tickets` carries no unique index but the primary key, and a test says so.** `test_queue_tickets_carries_no_unique_index_but_the_primary_key` (`test_migrations.py:1023`). F58 adds none — D9's duplicate flag is derived on read for precisely this reason.
- **`update_updated_at()` is a trigger on both tables.** `0018_queue_tickets.py` and `0019_fitting_rooms.py` both call `_updated_at_trigger(...)`. **No UPDATE in this feature sets `updated_at`** — the shipped `release()` and `handover()` do not either.
- **`tenant_session` IS the transaction.** `db/tenant.py:16-30` is `async with session_factory() as session, session.begin()`, so exiting the block is the commit and an exception propagating out of it is the rollback. D3a's entire proof rests on that one line.
- **`FloorService._authorize` is the target-dependent rule, written once, and it runs before any session opens.** `floor/service.py:793-806`, with `:19-24` recording that the ordering is the security property: *"a 403 raised after a read is an existence oracle."* D3 and D4 call it as their first statement.
- **The claim's savepoint exists to RECOVER, and that is the difference D3a turns on.** `floor/service.py:337-356`: the `try` is outside `async with session.begin_nested()`, the `except` reads the occupant and raises a 409, and `:341-344` says the savepoint *"rolls back to the savepoint and leaves the outer transaction alive"*. F36 needs the outer transaction alive because nothing else in the claim has been written. **F58's take-next has already written to `queue_tickets` at that point**, so it needs the opposite.
- **The release is already a conditional UPDATE whose rowcount-0 is a 200.** `db/repositories/fitting_room_assignments.py:200-233` returns `(wrote, row)`; `released_at IS NULL` in the predicate makes a second release keep the FIRST timestamp; `floor/service.py:452-456` records that a no-op writes **no audit row**. D5, D6 and D7 copy this shape three times.
- **The four 409-discriminating pieces are shipped end to end.** `floor/validation.py:44-83` (`_OccupiedError` and its two subclasses, deliberately **not** `DomainValidationError` subclasses so Starlette's MRO walk does not answer 400), `main.py:339-346` (the two bodies), `main.py:350-362` (`_occupied_body`, which **copies** the module constant and **omits** a falsy `details` rather than writing null), `api.ts:11-30` (`ApiError.details`, typed `Record<string, string> | undefined`, never `| null`). D12 adds two codes to that machinery and no new machinery.
- **`AuditAction` needs no migration for a new member** — `audit_log.action` is plain TEXT with no CHECK (0003), restated at `constants.py` seven times. F36's block is the model for D13's, including its rule that **a no-op writes no row**.
- **`FloorPanel` owns the mutation discipline, extracted in F36 precisely so a third panel could reuse it.** `FloorPanel.tsx:340-384` — `mutate()` counts rather than latches, calls `poll.clearTick()` + `poll.bump()`, classifies a 401/403 as terminal via `poll.fail`, and **re-arms in its `.finally()` rather than on the success path**, with the comment saying six room actions would otherwise be six chances to drop the re-arm. `applyRooms` (`:325-328`) is an **updater**, never a value, because two mutations overlap by design — that was F36's sharper review MAJOR.
- **`RoomsPanel` is the child-panel template, and its six focus MOVES are numbered in the source.** `RoomsPanel.tsx:15-31` (no poll, no timer, no pause control, no announced region of its own), `:167-192` (the two render-time captures, because an effect runs after the departing node is already gone), `:194-330` (MOVE 1–6). D15 follows it row for row.
- **`elapsedMinutes(serverNow, assignedAt)` already exists and is what the waitlist calls — NOT `elapsedLine`.** `lib/elapsed.ts` exports both. `elapsedMinutes` carries the two things that were load-bearing: the clamp at zero (the DB clock and the Python clock are two clocks) and the anchor to the envelope's `server_now`, so it freezes exactly when the panel freezes. **`elapsedLine` hard-codes its keys** — it returns `t("rooms.elapsedJustNow")` and `isolateLtr(t("rooms.elapsed", {minutes}), …)`, verified at `lib/elapsed.ts:31-37` — so calling it from the waitlist would render the ROOM's copy («כבר 42 דק'», *already 42 min*, about a woman who has not been in a room) and leave D16's two waitlist keys dead, green, and unused, because `i18n.test.ts` counts entries and never checks that a key is reached. `WaitlistPanel` therefore calls `elapsedMinutes` and does its own two-branch key selection in three lines. **No new mechanism, no date library** (F36's D17 forbids one) and **no edit to a shipped `lib/` helper with two shipped callers** — adding a key-prefix parameter to `elapsedLine` buys nothing and puts `RoomsPanel.test.tsx` and `FloorPanel.test.tsx` at risk for a rename.
- **The dev proxy names second path segments and a backend test asserts SET EQUALITY.** `apps/manage/vite.config.ts`'s `MANAGE_API` (fourteen names, `floor` among them) and `tests/test_spa_serving.py:377`. **Every F58 route's second segment is `floor`, so `vite.config.ts` needs no edit** — see D11, and see conflict 4 for what mounting at `/manage/queue` would have cost.
- **`test_the_floor_roles_reach_exactly_the_floor_routes` classifies on the INTERSECTION and asserts a floor route admits ALL THREE floor roles or none.** `test_staff_role_gating.py:271-334`, and `:314-315` + `:329` are the two lines that make D11's conclusion structural rather than a preference. Its docstring names **F58 by name** as an expected extender and says the assertion *"MUST NEVER BE RELAXED TO A SUBSET CHECK"*.
- **The console has FOUR e2e tests and every one of them is the LOGIN SCREEN. There is no authenticated console coverage of any kind.** ⚠ Corrected at review: an earlier draft said "ZERO Playwright coverage", which is false and would have made A30's claim false with it. `frontend/e2e/` holds `a11y.spec.ts` (**10** tests) and `storefront.spec.ts` (**55** — counted, not the 48 an earlier draft asserted), so **65**, not 58. Four of the ten visit `MANAGE`: the shared viewport-meta loop (`a11y.spec.ts:64`), *"manage: login screen has zero axe A/AA violations + Hebrew title"* (`:128`), *"manage: login screen is MODRYN-branded and still has exactly one h1"* (`:139`) and *"manage: printing a screen with no print sheet does not blank the page"* (`:162`). The last one's own comment names the gap D19 closes: *"The login screen is the console screen this suite can reach unauthenticated."* Nothing gets past `App.tsx`'s `api.me()` bootstrap without a stubbed identity, which is exactly what the harness supplies. `storefront.spec.ts:414-450` is the interception idiom to copy — `page.route`, a per-path queue of `ok(...)` responses, and a recorder. D19 builds the `/manage` analogue.

---

## Design

### D1 — One `ALTER TABLE`. `queue_ticket_id` and nothing else, and what it must prove it did not add

"No new table" is F58's ruling and it is true. **It is not the same promise as "no migration"**, and F36 wrote the handover in its own DDL:

> `queue_ticket_id` is deliberately ABSENT. The walk-in's dispatch record is F33's `queue_tickets` and the dispatch action is F58's; F58 adds the column in its own migration alongside its writer, rather than this one pre-adding a speculative pointer nothing can fill.
> — `0019_fitting_rooms.py`, verbatim

```python
"""floor dispatch: the assignment's pointer at the walk-in it serves

Revision ID: <alembic heads + 1 at build time>
Revises:     <whatever head is then — NOT hardcoded>
"""

def upgrade() -> None:
    # The other half of `booking_id`, and the two are mutually exclusive in
    # practice without being constrained to be: a fitting serves either a bride
    # who booked (booking_id) or a walk-in off the queue (queue_ticket_id) or
    # nobody at all (a staffer prepping a room — both null, the ordinary case
    # and the one F36 already exercises).
    #
    # DELIBERATELY ABSENT, each with its reason and its verifying test — the
    # 0014_booking_check_in.py idiom, where the comment and not the DDL line is
    # the deliverable:
    #
    #   No NOT NULL: every assignment F36 created has this column null, and the
    #     anonymous claim stays a first-class path.
    #   No FK, no CASCADE: house rule; the join predicate is spelled out in
    #     FittingRoomsRepository._occupancy_rows and every read is RLS-scoped.
    #   No CHECK of any kind — not `num_nonnulls(booking_id, queue_ticket_id) <= 1`
    #     either. test_the_fitting_room_tables_carry_no_check_constraints
    #     (test_migrations.py:1648) asserts this table has zero, and the
    #     exclusivity it would express is not actually an invariant: a bride who
    #     booked ahead and ALSO scanned the QR is a real person, and refusing to
    #     record both facts about her would be the schema being clever at the
    #     expense of the room she is standing in.
    #   No UNIQUE INDEX — not `(tenant_id, queue_ticket_id) WHERE released_at IS
    #     NULL AND deleted_at IS NULL`, which reads like the missing third
    #     guarantee and is not one. Two dispatches of the same ticket are already
    #     impossible: both verbs claim the ticket with a conditional
    #     `UPDATE ... WHERE status = 'waiting'` FIRST, so the second transaction
    #     blocks on that row's lock, re-evaluates the predicate against the
    #     updated row and matches nothing (D4). Adding one would also RED
    #     test_fitting_room_assignments_carries_exactly_two_non_primary_unique_indexes
    #     (test_migrations.py:1617) — a shipped guard whose whole purpose is to
    #     make a third index a visible, reviewed act. This is that review, and
    #     the answer is no.
    #   No non-unique index either: nothing reads this column as a predicate.
    #     The payload joins queue_tickets on ITS primary key, and the finish
    #     path goes assignment -> ticket. An index here would serve no reader
    #     and cost every claim (D1's `is_active` reasoning, F36).
    #   No GRANT and no enable_tenant_rls: the table already has both, and RLS
    #     is per-table, not per-column.
    op.execute("ALTER TABLE fitting_room_assignments ADD COLUMN queue_ticket_id UUID")


def downgrade() -> None:
    # ⚠ UNLIKE F36's, THIS DOWNGRADE CAN LOSE LIVE DATA — it drops the only
    # record of which walk-in each fitting served. F57's role-widening migration
    # carries the same warning for the same reason. Stated here rather than
    # discovered on a staging rollback.
    op.execute("ALTER TABLE fitting_room_assignments DROP COLUMN IF EXISTS queue_ticket_id")
```

**The ORM model is the second half of this migration and is not optional.** `models/fitting_room_assignment.py` gains the mapped column in the same commit — there is no model↔migration parity test anywhere in `backend/tests/`, so without it every backend line in D2 through D8 is an `AttributeError` (F36's D5, F57's D3, F34's D2, all the same sentence). **The model's class docstring must also be corrected**: it currently reads *"**No personal field of any kind.** `booking_id` and nothing else"* (`:26-30`), and the second clause becomes false in this PR. The rule that survives — and it is the stronger one — is that **neither pointer is a snapshot**: the label is resolved on every read from the live rows, so a retention sweep or an erasure renders an anonymous visit rather than quietly preserving a name in a table nobody thought of. That property is exactly what D10 extends to the queue join.

**What the migration must prove it did not do**, as `db`-marked assertions rather than as promises:

- `queue_ticket_id` is `("uuid", "YES", None)` in `_fitting_columns` — nullable, no default.
- `test_fitting_room_assignments_carries_exactly_two_non_primary_unique_indexes` **stays green with no edit**.
- `test_the_fitting_room_tables_carry_no_check_constraints` **stays green with no edit**.
- `test_the_three_partial_unique_index_definitions_are_pinned` **stays green with no edit** — an `ALTER TABLE ADD COLUMN` does not touch a partial index's deparsed definition, and asserting that is what catches a builder who "helpfully" widens a predicate while in the file.
- `test_queue_tickets_carries_no_unique_index_but_the_primary_key` and `test_the_queue_tickets_migration_pins_its_checks_and_its_one_index` **stay green with no edit** — F58 writes all four `status` values the shipped CHECK already admits and widens nothing.
- The round trip, last in the file, targeting `_parent_of("floor dispatch")` and never `"-1"`. F36's shipped note records `"-1"` rotting for real when 0019 landed on 0017's test; `_parent_of` (`test_migrations.py:31-55`) resolves the target **by identity** and survives both a renumber and a stack. The migration's docstring must therefore contain the marker string this test greps for.

### D2 — The waitlist joins `/manage/floor`. One more statement on the tick's existing session, wait time computed on read

```python
class WaitlistEntry(BaseModel):
    # The ticket id, and it IS F33's capability — whoever holds it can POST
    # /storefront/checkin/position and read that ticket's status. On THIS surface
    # that is not a disclosure: the caller is a signed-in staffer of this tenant,
    # the payload is behind the session cookie and the role gate, and what the
    # capability buys is `{id, status, position, called_at}` — TicketView echoes
    # no name and no phone (`app/queue/schemas.py:47-72`). It is here because
    # every verb in this feature takes it as the target and there is no lesser id.
    # ⚠ TicketView's own docstring says the id is "issued exactly once, at
    # creation … and by NO OTHER SERVER PATH EVER". This payload is the second
    # path, deliberately and to a signed-in staffer only, and D10's rewritten
    # privacy comment names it rather than leaving that promise quietly broken.
    # ⚠ The console must never render it as a link to `/q/{id}` (A29).
    id: uuid.UUID
    name: str
    visit_type: str
    # 1-based, and DERIVED FROM THIS LIST'S OWN ORDER (index + 1) — never a
    # second count query. F59's D3 argument: two derivations of one number are
    # two chances for the wall, her phone and this panel to disagree.
    position: int
    # ⚠ `created_at`, NOT the sort key — renamed at review, and the rename IS the
    # fix. An earlier draft sent COALESCE(requeued_at, created_at) as
    # `waiting_since`, which D6 rewrites on every skip: one skip would reset the
    # rendered clock to zero and the panel would say «הגיעה זה עתה» — *she
    # arrived just now* — about a woman who has been standing there forty
    # minutes, on the number the Goal says this panel exists to show and that
    # D8's remove decision is partly a judgement about. Two facts, two columns:
    # `arrived_at` is when she walked in and never moves; the ordering key is
    # what a skip moves. Sent as an INSTANT so the CLIENT computes the minutes
    # against the envelope's server_now with the shipped elapsedMinutes() — a
    # server-computed count is stale the instant it is serialised and a
    # device-clock one is wrong by however far a boutique tablet has drifted.
    # This is `assigned_at`'s rule, unchanged.
    arrived_at: datetime.datetime
    # A BOOLEAN, not the timestamp — F59's D-payload rule applied one surface
    # over. The panel needs to know WHETHER, not WHEN; the instant would let
    # anyone with the screen time how long a named woman has been standing at a
    # counter, and nothing renders it.
    called: bool
    # So the second-skip rule is LEGIBLE rather than surprising. The next skip on
    # an entry with skip_count >= 1 removes her, and that is destructive with no
    # undo (D8) — a control that silently changes meaning on its second press is
    # the shape this number exists to prevent.
    skip_count: int
    # D9. "Another live ticket today carries the same phone." The phone itself
    # never reaches the wire.
    duplicate: bool


class Waitlist(BaseModel):
    entries: list[WaitlistEntry]
    # F36's FloorDressList rule verbatim: the UI renders one line saying the list
    # is partial and names NO count and NO limit, because both are the server's
    # to change without a copy edit.
    truncated: bool
```

`FloorResponse` gains one key: `waitlist: Waitlist`. `StaffCard`, `Room`, `RoomAssignment`, `Occupancy` and `server_now` are untouched.

**The read**, on the tick's EXISTING session — no second `tenant_session`, no second pool checkout, no second `tenants.by_slug`. ⚠ **The predicates and the sort key are `_live_waiting()` and `_sort_key()`, CALLED and never re-spelled** — F59 shipped both as module-level helpers in `queue_tickets.py` precisely so this feature could not drift from `position()` and the wall board (see «Problem»):

```python
WAITLIST_LIMIT = 100  # A BOUND, not a page size. F36's picker reasoning: "more
                      # than any boutique has", so `truncated` is the honesty for
                      # the one case it bites — a griefing flood inside F33's
                      # 200/hour tenant ceiling (F33 Risk 1).

waiting = (
    select(
        QueueTicket.id, QueueTicket.name, QueueTicket.visit_type,
        QueueTicket.created_at, QueueTicket.called_at,
        QueueTicket.skip_count, QueueTicket.phone,
    )
    .where(*_live_waiting(tenant_id, day))          # the four, shared not copied
    .order_by(_sort_key().asc(), QueueTicket.id.asc())
    .limit(WAITLIST_LIMIT)
)

# ⚠ THE SECOND STATEMENT, and it is D9's and only D9's. `_live_waiting` CANNOT
# be reused here — its third predicate is `status == 'waiting'`, and the whole
# point of this read is the rows that are not. A phone-only projection: no name,
# no id, nothing that could be rendered by accident.
in_service_phones = (
    select(QueueTicket.phone).where(
        QueueTicket.tenant_id == tenant_id,
        QueueTicket.queue_day == day,
        QueueTicket.status == QueueTicketStatus.IN_SERVICE.value,
        QueueTicket.deleted_at.is_(None),
    )
)
```

`truncated = len(rows) == WAITLIST_LIMIT` — F36's `DressPickerRead` derivation verbatim, stated here because an earlier draft left it to be guessed.

**A COLUMN PROJECTION, never `select(QueueTicket)`, and it is load-bearing twice.** First, minimisation: the entity pulls a normalised Israeli mobile and a `marketing_opt_in_at` consent timestamp for every waiting woman into the process **twelve times a minute forever**, for a view that renders six fields — F59's D3 made this argument for the public board and it is the same argument one surface over. Second, the identity map: **every statement in this feature — the two reads above, the five writes (D3–D8) and the refusal read (D4) — is a projection, so no `QueueTicket` INSTANCE is ever constructed on any path in this feature.** The class of bug F36 and F57 each shipped once — ORM-enabled DML stamping the SET value onto an identity-mapped instance a later line then reads — is therefore structurally unreachable rather than defended against, and `populate_existing=True` appears nowhere as a consequence rather than an oversight.

⚠ **THE REFUSAL READ IS WHERE THAT PROPERTY WAS ABOUT TO BE LOST, AND THE REVIEW CAUGHT IT.** D4's rowcount-0 branch says "the service issues one read of the row", and the only shipped method that answers it is `QueueTicketsRepository.by_id`, which is `select(QueueTicket)` — an entity, in the same session as an ORM-enabled UPDATE, with `phone` and `marketing_opt_in_at` in tow. That would have made the paragraph above false on four verbs and would have put a `QueueTicket` in the identity map at exactly the moment the docstring on `FittingRoomAssignmentsRepository._refreshed` says this repo has been bitten three times. **So D4's read is a new projection on `QueueTicketsRepository`, beside the write methods, and never `by_id`:**

```python
async def status_of(session, tenant_id, ticket_id) -> tuple[str, int] | None:
    """The refusal read, and it is a PROJECTION for the reason D2 gives.
    `(status, skip_count)` is everything the two-answer table and D6's
    optimistic branch need; `phone` never enters the process on a refusal."""
    stmt = select(QueueTicket.status, QueueTicket.skip_count).where(
        QueueTicket.tenant_id == tenant_id,
        QueueTicket.id == ticket_id,
        QueueTicket.deleted_at.is_(None),
    )
    return (await session.execute(stmt)).one_or_none()
```

⚠ **EVERY ORM-enabled UPDATE in this feature carries `.execution_options(synchronize_session=False)`** — D3's, D4's, D5's close, D6's, D7's and D8's, not take-next alone. SQLAlchemy 2.0's default is `'auto'`, which tries `'evaluate'` and falls back to `'fetch'`; none of these WHERE clauses is Python-evaluable, D6's `skip_count + 1` and `CASE` SET expressions least of all, and no caller reads an identity-mapped instance afterwards. `False` is the only spelling that is both correct and free, and stating it once here beats six chances to forget it.

⚠ **`phone` IS selected and NEVER serialised.** It exists in this statement for D9's grouping and for nothing else. `QueueTicketsRepository`'s class docstring currently promises *"There is no `active_today`, no dedup lookup and no read keyed on `phone` … That absence is the security property, not an omission"* (`:15-18`). **F58 makes the last clause false and the docstring is corrected in this PR** — F36's precedent for exactly this situation, where three shipped comments asserted a property the new feature removed. The rule that survives, and it is the one that was actually load-bearing: **no read on an anonymous, unauthenticated surface is keyed on `phone`, and no response body anywhere carries it.** The oracle Ruling 3 closed was a public one; a signed-in staffer of this tenant grouping today's own arrivals is a different surface with a different threat model, and saying so beats leaving a false comment standing as the rationale.

**`day` is TODAY, from `today_jerusalem(self._clock)`** — the helper `FloorService._today_window` already calls (`floor/service.py:719-733`), so the waitlist and the client picker cannot drift apart. Bound to today rather than to a ticket's own day, which is the opposite of `position()`'s binding and deliberately so: `position()` has a ticket in hand and binding it to today would tell a woman who walked out yesterday that she is next (`queue_tickets.py:66-70`); the panel has no ticket, and yesterday's ghosts must not sit above this morning's first arrival. **The consequence is stated rather than hidden: an unclosed ticket from an earlier day is invisible and therefore unremovable from this panel, and its own `/q/{id}` page still reports its own day's position.** F20's retention sweep owns it (Risk 5), and it is the same disagreement F59 already records.

**The ordering is byte-identical to `position()`'s predicate set** — it is literally the same function call now — plus a `, id` tiebreak on the ORDER BY. `position()` counts `sort_key < mine` and has no tiebreak, so two rows sharing a sort key both render the same number; this list has to be totally ordered or two ticks could transpose them. F59 recorded the same residual and shipped the same `, id` on `board`. **`position()` is NOT edited** — changing a shipped read's semantics to buy a cosmetic agreement is not a trade worth making.

⚠ **THE TIE IS NOT A ONE-IN-A-MICROSECOND EVENT, AND A `db` TEST WILL MANUFACTURE IT ON ITS FIRST RUN.** `0018_queue_tickets.py:29` declares `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`, and `FittingRoomAssignmentsRepository.release`'s own docstring records what that means here: *"`created_at` … is `server_default=text(\"now()\")`, i.e. the DATABASE host's transaction-start time"*. Postgres's `now()` is **transaction-start**, so **every ticket inserted inside one transaction carries the same `created_at` to the microsecond** — and `insert` refuses a caller-supplied one on purpose. A test that seeds three waiting tickets through one `tenant_session`, which is the obvious shape and the one `test_floor_rooms_db.py`'s harness invites, gets three identical sort keys: the list collapses onto the `, id` tiebreak (random UUID order, so "arrival order" is asserted about nothing) and `position()` returns **1 for all three**. **HARD RULE for the `db` suite, stated beside the harness's other hard rules: every waiting ticket in an ordering test is inserted in its OWN `tenant_session`.** A builder batching the seeds for speed produces the degenerate case silently, and the likeliest "fix" for the red is to weaken A3 to `>= 1`, which makes it vacuous.

**Cost, stated:** the payload goes from three statements per tick (`list_live`, `list_with_occupancy`, `by_assignment_ids` — verified in `FloorService.floor`) to **five**: the waitlist read and D9's phone-only in-service projection. Both are index-prefix range scans over one tenant-day on `idx_queue_tickets_tenant_day_active`, which is `(tenant_id, queue_day) WHERE deleted_at IS NULL` and is **not** status-narrowed, so the second costs the same scan and no schema change. Unlike F36's bindings read neither is skippable when empty — an empty queue is the common case and «אין ממתינות בתור» is the answer the panel exists to give.

### D3 — TAKE-NEXT is ONE transaction, and the absence of a savepoint is the guarantee

```python
async def take_next(self, tenant_id, room_id, *, staff_user_id, actor) -> DispatchRead:
    target_staff_id = staff_user_id or actor.id
    self._authorize(target_staff_id, actor)          # 1. before any read (floor/service.py:19-24)
    try:
        async with tenant_session(self._sessions, tenant_id) as session:
            room = await self._rooms.by_id_for_update(session, tenant_id, room_id)   # 2.
            if room is None or not room.is_active:
                raise DomainNotFoundError("fitting_room")
            occupant = await self._assignments.occupant_of_room(session, tenant_id, room_id)
            if occupant is not None:                                                 # 2b. FAST PATH
                raise RoomOccupiedError(
                    await self._occupant_details(session, tenant_id, occupant)
                )
            ticket = await self._tickets.claim_next(session, tenant_id, day=self._today())  # 3.
            if ticket is None:
                raise QueueEmptyError                                                # 4.
            assignment = await self._assignments.claim(                              # 5. RAISES
                session, tenant_id, room_id=room_id, staff_id=target_staff_id,
                booking_id=None, queue_ticket_id=ticket.id,
            )
            await self._audit.record(...)                                            # 6.
            return await self._dispatch_read(session, tenant_id, room_id)            # 7.
    except IntegrityError as error:
        # ⚠ THE TRANSACTION IS ALREADY GONE. See D3a.
        raise await self._occupied_error(tenant_id, room_id, target_staff_id, error) from error
```

**Two additions to `FloorService` that the snippet above assumes and the class does not have** — verified at `floor/service.py:161-177`, which constructs ten repositories and none of them is `QueueTicketsRepository`, and which has `_today_window()` but no `_today()`. Both are `AttributeError`s as written, which is the same class of omission D1 flags for the ORM column:

- `self._tickets = QueueTicketsRepository()` in `__init__`.
- `def _today(self) -> date: return today_jerusalem(self._clock)`, written beside `_today_window()` **and called by it**, so the waitlist day, the take-next day and the client picker's window cannot drift apart — which is the argument `_today_window`'s own docstring already makes.

**Step 2b, and it is a FAST PATH rather than the guarantee.** `by_id_for_update` holds the room's row lock, and `FittingRoomAssignmentsRepository.has_active_for_room`'s docstring is the shipped statement of why a read issued *after* that lock is meaningful: *"a new statement snapshot taken under the lock is what sees the committed claim."* `delete_room` already uses that shape. We call `occupant_of_room` rather than `has_active_for_room` because it is the same predicate returning the row the 409 needs anyway — one read, not two. Without it, the **most likely collision in the entire feature** (two managers tapping «קחי את הבאה» on the same free tile inside one 5s tick) claims a real customer's ticket and then throws it away: B blocks on the room lock, A commits, B acquires the lock, claims ticket **2**, fails the INSERT, rolls everything back — and for the window in which B held ticket 2, a third take-next SKIP-LOCKs past it and serves ticket 3. That is Risk 1's out-of-order service **manufactured by the design rather than forced by it**. With 2b, the serialised same-room case touches no ticket at all. The partial unique index and D3a's rollback remain the correctness mechanism for the genuinely-uncommitted-winner window, which 2b cannot see and does not claim to.

Step 3, and it is the shape the ruling fixes:

```sql
UPDATE queue_tickets SET status = 'in_service'
 WHERE tenant_id = :t AND status = 'waiting'      -- redundant BY CONSTRUCTION; see below
   AND id = (
        SELECT id FROM queue_tickets
         WHERE tenant_id = :t AND queue_day = :day
           AND status = 'waiting' AND deleted_at IS NULL
         ORDER BY COALESCE(requeued_at, created_at), id
         LIMIT 1
         FOR UPDATE SKIP LOCKED
      )
RETURNING id, name, visit_type, called_at
```

**The two outer conjuncts are free and they are there for the reader.** The subquery's `FOR UPDATE` holds the row for the whole transaction, so nothing can change between the two and neither conjunct can alter the outcome — they are redundant by construction. But every other predicate in this feature leads with `tenant_id`, both repositories' class docstrings call that *"redundant defence-in-depth (house pattern)"*, and **this is the one statement in the product that moves a named customer into a fitting room**. It is the statement a reader will study, and the one that silently loses its tenant scoping if RLS is ever mis-bound by a `tenant_session` refactor. Spelling them costs nothing and makes the statement readable in isolation.

In SQLAlchemy Core, the inner select is `.with_for_update(skip_locked=True).scalar_subquery()`; the outer statement carries `.execution_options(synchronize_session=False)` because its WHERE cannot be evaluated in Python, and it `RETURNING`s **four columns, not the entity** (D2's projection rule — `phone` and `marketing_opt_in_at` never enter the process on this path either).

**`FOR UPDATE` on the SUBQUERY is what makes two managers get two customers; `SKIP LOCKED` is what makes the loser NOT WAIT.** ⚠ **Corrected at review, because the earlier draft attributed the wrong property to `SKIP LOCKED` and built the feature's second concurrency test on that attribution.** The plan for the inner select is `Limit → LockRows → Sort → Scan`, with LockRows *below* the Limit. With plain `FOR UPDATE`, B blocks on the row lock; when A commits, LockRows runs EvalPlanQual against the updated tuple, the `status = 'waiting'` qual now fails, the row is discarded, and **LockRows pulls the next row from the sort and locks that one** — B gets ticket 2 exactly as it would have with `SKIP LOCKED`. Plain `FOR UPDATE` here is *slower*, not *wrong*. So: the row lock plus the `status` qual is what makes the same woman unreachable twice; `SKIP LOCKED` is what stops a take-next waiting behind an unrelated transaction that happens to hold a queue row. Both matter and they are different properties, and the test for each is different (see «The forced interleaves»). `updated_at` is not in the SET list — the shipped trigger owns it.

**Two consequences, both stated rather than discovered:**

1. **SKIP LOCKED passes over ANY row-locked ticket, not only a contested one, so it can serve out of order.** If A holds ticket 1 and then rolls back (D3a), B — which skipped past it — already took ticket 2, and ticket 1 is served next. **And the lock is taken by CALL (D7) and SKIP (D6) too**, so an ordinary «call Noa forward» on one tablet can cause a simultaneous take-next on another to serve position 2. Same window, same accepted trade, stated here because an earlier draft named only the take-next-vs-take-next case. It is strictly better than the alternative it buys: two managers walking two different brides to the same curtain with one ticket between them. The window is the length of one statement.
2. **The room is locked before the ticket is claimed** (`by_id_for_update`, step 2, F36's shipped AC17 lock). Ordering the two the other way would let a concurrent room delete slip between them and strand the ticket; taking the room lock first also means the common refusal — a room that vanished or was deactivated — costs no ticket write at all.

**`QueueEmptyError` is a 409, not a 404 and not an empty 200.** 404 would mean the *room* is missing, which the panel would render as «החדר כבר לא זמין» about a room that is fine. A 200 with an unchanged payload would leave the manager wondering whether the tap registered. Its own code, its own Hebrew sentence (D12), and — because the queue emptying between the render and the tap is an ordinary five-second race — **not an outage register**.

### D3a — A lost race rolls BOTH writes back. What she sees, and why the ticket cannot be stranded `in_service`

**This is the single most important behaviour in the feature.** It is the one a customer would notice, and the one where copying the shipped code would produce the defect.

**⚠ THE HAZARD, RESTATED AT REVIEW, BECAUSE THE FIRST DRAFT NAMED THE WRONG MECHANISM AND ITS HEADLINE MUTATION WAS THEREFORE VACUOUS.** The draft said: *"the service raises a 409 → the enclosing `tenant_session` **commits on the way out**"*. **That is false about the line it cites.** `db/tenant.py:25` is `async with session_factory() as session, session.begin():`, and an exception propagating out of that `async with` runs `AsyncSessionTransaction.__aexit__` **with an exception set, which ROLLS BACK**. A raised 409 rolls the ticket write back *with or without* a savepoint.

**So the guarantee is narrower and different, and it is this:**

> **Every refusal on this path RAISES out of `tenant_session`, and no code inside the `async with` may `return` after the ticket UPDATE has run.** A `return` from inside the block is the one construct that commits.

`FloorService.claim`'s savepoint (`floor/service.py:337-356`) does not exist to permit a commit; it exists to keep the transaction *usable* long enough for `_resolve_claim_conflict` to read the occupant, and the `RoomOccupiedError` that follows rolls the outer transaction back anyway. **The shape that actually strands a customer is `_resolve_claim_conflict`'s FIRST branch** (`floor/service.py:398-400`):

```python
existing = await self._assignments.active_for(session, tenant_id, room_id, target_staff_id)
if existing is not None:
    return await self._room_read(session, tenant_id, room_id)   # ⚠ RETURN. COMMITS.
```

Copied into take-next — and a builder told "one helper shared by take-next and push-assign" and pointed at the shipped resolver **will** copy it — that `return` commits a transaction in which the ticket has already gone to `in_service` and **no assignment was created**:

> the ticket UPDATE (step 3) has run → the INSERT failed → the helper RETURNS from inside the `async with` → `tenant_session` **commits** → **the woman is `in_service` with no room**, and the route answers **200** about a dispatch that did not happen.

The path is ordinary, not exotic: `RoomsPanel` renders «קחי את הבאה» from a payload up to one tick (~5s) stale, so tapping a tile the caller already occupies is the everyday double-tap. That state is unreachable by any verb in this feature: she is gone from the waitlist (`status != 'waiting'`), gone from F59's board, on no room tile, and her own phone reads «התור שלך התחיל» for the rest of the day. Recovery needs `psql`. It is F36's soft-deleted-room-holding-a-live-assignment defect, one table over, and with a customer in it.

**The design: there is NO savepoint on this path, and there is NO idempotence branch.** No savepoint because nothing after the conflict needs the transaction alive — the occupant read moves to a second session (below) — so the simpler shape is also the correct one, and the `try` wraps the **`async with` itself**, not a block inside it. **No idempotence branch because the transaction that would have made a 200 true is gone**: every `IntegrityError` out of this transaction is a refusal, and answering 200 would report a dispatch that claimed nobody while consuming the head of the queue. That absence is a safety property and is asserted as one (A8b), not an economy.

**Three properties fall out, and each is asserted:**

| Property | Why it holds |
|---|---|
| The ticket returns to `waiting` at its **original** position | The rollback discards the UPDATE; `requeued_at` was never touched, so `COALESCE(requeued_at, created_at)` is unchanged and `position()` answers exactly what it answered before the tap |
| No other transaction ever observed her as `in_service` | The UPDATE held the row's write lock for the whole transaction; READ COMMITTED readers see the pre-update row and a concurrent take-next SKIP-LOCKs past it |
| No audit row is written | Step 6 is inside the transaction, so the trail cannot claim a dispatch that did not happen — F36's *"a NO-OP WRITES NO ROW"* rule (`constants.py`, F36's block) |

**The cost, paid deliberately.** The 409 must name the occupant, and the occupant can only be read *after* the conflict — but the transaction is gone, so that read opens a **second, short, read-only `tenant_session`**. F36 declined a second session for its claim (*"another pool checkout, another `set_config`, another BEGIN/COMMIT and a second place for the tenant id to be wrong"*) and was right to, because it had a savepoint available. **Here the savepoint is not available and would not help**, so the second checkout is the price of correctness, and it is paid only on a refusal. The tenant id is passed as an argument, so there is no second place for it to be wrong.

**`_occupied_error()` in full, because "one helper shared by take-next and push-assign" is not a specification and the shipped analogue has two branches this one must NOT inherit:**

```python
async def _occupied_error(self, tenant_id, room_id, target_staff_id, error) -> Exception:
    """Returns the exception to raise. The caller does `raise ... from error`.

    ⚠ NO IDEMPOTENCE BRANCH. `active_for` is deliberately NOT consulted: on
    these two verbs the ticket write is live and a `return` would commit it
    (D3a). A dispatch that violated either index dispatched NOBODY and must
    refuse — the exact inverse of `claim`, where a re-claim is a true 200.

    ⚠ The ROOM is resolved FIRST and WITHOUT the constraint name, which is
    F36's rule (`_resolve_claim_conflict`'s docstring) applied to a case its
    own branch order cannot cover: a claim that violates BOTH indexes reports
    whichever has the lower OID — migration creation order, which flips after
    any REINDEX CONCURRENTLY or pg_repack. Reading the occupant first makes
    the answer deterministic. (Step 2b already refuses the committed-occupant
    case before the INSERT, so this branch runs only for a winner that had not
    yet committed when 2b read — but it must still be right.)

    ⚠ An UNRECOGNISED constraint RE-RAISES, unchanged from F36: "a 500 on a
    violation nobody predicted is correct, and silently mapping it to
    ROOM_OCCUPIED would tell a staffer a lie about furniture." This is why the
    helper RETURNS an exception rather than raising one — `return error` is
    how that branch is expressible at all.
    """
    async with tenant_session(self._sessions, tenant_id) as session:
        occupant = await self._assignments.occupant_of_room(session, tenant_id, room_id)
        if occupant is not None:
            return RoomOccupiedError(
                await self._occupant_details(session, tenant_id, occupant)
            )
        held = await self._assignments.room_of_staff(session, tenant_id, target_staff_id)
        if held is not None:
            return StaffOccupiedError(
                await self._held_room_details(session, tenant_id, target_staff_id)
            )
    if violated_index(error) is None:
        return error                       # unrecognised → 500, F36's rule
    return RoomOccupiedError(None)         # the winner released in the gap:
                                           # «החדר נתפס זה עתה. נסי שוב.»
```

**What the user sees.** «דנה כבר בחדר הזה.» or «היא כבר בחדר 2.» in the tile's alert, focus moved into it (MOVE 1), the queue **unchanged** on the same screen — her name is still at position 1, and the manager taps a different room. Nothing on the panel claims the dispatch happened. If the occupant released in the meantime and cannot be named, «החדר נתפס זה עתה. נסי שוב.» — F36's shipped `*Unknown` strings, reused unchanged.

**The proof, as tests — and BOTH the interleave and the mutation were respecified at review.**

*The interleave, as stated in the first draft, could not be staged.* "B claims the room and commits **while A is between its ticket claim and its INSERT**" needs a seam inside `take_next`, and there is none: `by_id_for_update` holds the room's row lock for A's whole transaction, and `FloorService`'s only injectable is `clock`. Written literally the test is unbuildable; written with `asyncio.gather` it is exactly the shape `test_floor_rooms_db.py:19-40` forbids. **The shipped precedent does something simpler and fully deterministic** — `test_a_second_claim_landing_in_the_gap_is_refused_and_names_the_occupant` (`test_floor_rooms_db.py:218-274`): open a read-only snapshot `tenant_session` and assert the room reads **free** (this is what makes the gap *observable* rather than assumed), commit the conflicting assignment through `ASSIGNMENTS.claim` in a **nested** `tenant_session`, then call the service. No tasks, no Event, no hang. F58 copies that shape exactly, and reserves `asyncio.Event` + `HOLD_SECONDS` for the cases where a statement must genuinely **block** on uncommitted work — which here is the SKIP LOCKED test and the concurrent-skip pair, and nothing else.

**A8, `test_a_take_next_that_loses_the_room_leaves_the_ticket_waiting`.** Four assertions: (1) `RoomOccupiedError` raised, (2) the ticket is `status == 'waiting'`, (3) `position(ticket) == 1`, (4) zero audit rows.

**MUTATION — the one that matters most in this feature, and NOT the one the first draft named.** The draft's mutation («wrap step 5 in `begin_nested()` and move the `try` inside, i.e. copy `FloorService.claim` verbatim») **comes back GREEN**: under it the savepoint rolls back the INSERT, the 409 is *raised*, the raise propagates out of `tenant_session`, and the ticket UPDATE rolls back too — all four assertions hold, and the feature's headline test would have been vacuous on the gate it exists to discharge. The mutation that actually strands is the `return`:

> **MUTATION: give the except branch F36's idempotence RETURN** — `existing = await self._assignments.active_for(session, tenant_id, room_id, target_staff_id); if existing is not None: return await self._room_read(session, tenant_id, room_id)` — **inside the `async with`**, and run it against the fixture where the conflicting assignment is held by **the same staffer as A's target** (the stale-tile double-tap). Take-next then answers **200**, `tenant_session` commits, and the ticket is stranded `in_service` with no assignment: assertions (1), (2), (3) and (4) all red.
>
> **SECOND MUTATION, cheaper and also biting:** move the ticket claim and `_audit.record` into their own `tenant_session` that commits **before** the INSERT is attempted → the ticket and the audit row survive the failure; (2), (3) and (4) red.

**A8b, `test_a_take_next_into_a_room_the_caller_already_holds_is_refused`** — the assertion that structurally forbids the idempotence branch from ever being added back: the target staffer already holds this room (committed), take-next answers **409 `ROOM_OCCUPIED` naming her**, never 200, and the head of the queue is untouched — `status == 'waiting'`, `position == 1`, `requeued_at` null, zero audit rows. This is also the case step 2b refuses before the INSERT, so it is a test of 2b and of the helper's missing branch at once.

### D4 — PUSH-ASSIGN: the same insert against a named ticket, guarded by a conditional UPDATE

Identical to D3 except step 3, which names the ticket instead of draining the queue:

```sql
UPDATE queue_tickets SET status = 'in_service'
 WHERE tenant_id = :t AND id = :ticket_id
   AND status = 'waiting' AND deleted_at IS NULL
RETURNING id, name, visit_type, called_at
```

**Push-assign takes step 2b too** — the room lock, then `occupant_of_room`, before the ticket is touched. Same reason, same fast path, same "not the guarantee" caveat.

**Rowcount 0 is the whole refusal design, and it is two answers, not one.** The conditional UPDATE cannot distinguish "gone" from "not waiting", so on rowcount 0 the service issues **one** read of the row — `status_of()`, the projection D2 specifies, never `by_id` — and the transaction is healthy, no error was raised, nothing is aborted:

| Read result | Raised | What she reads |
|---|---|---|
| `None` | `QueueTicketNotFoundError` → 404 `NOT_FOUND` | «הכניסה הזו כבר לא קיימת.» |
| `(status, _)`, `status != 'waiting'` | `QueueTicketNotWaitingError` → 409, `details={"status": …}` | «היא כבר בטיפול.» / «הכניסה הזו נסגרה.» |

**`QueueTicketNotFoundError`, not a bare `DomainNotFoundError("queue_ticket")`** — corrected at review. F33 already ships the subclass (`app/queue/validation.py:56`, *"An unknown, soft-deleted or foreign-tenant ticket id"*), and `main.py` records that it deliberately needs no handler because the base class's 404 answers it. The wire answer is identical, so nothing in `test_floor_api.py`'s `SPEC_ERROR_CODES` moves; what the subclass buys is a named, greppable condition, which is this feature's posture everywhere else. The resulting `app/floor/service.py` → `app/queue/validation.py` import is the accepted direction — the module already imports `app/storefront/validation.py` for `today_jerusalem`.

*Declined collapsing the two into one 404.* «כבר לא קיימת» and «כבר בטיפול» have different remedies — remove the row from your screen versus find her in a fitting room — and one extra read on a refusal path buys the difference. The `status` value in `details` is not a disclosure on an authenticated tenant-scoped surface, and it is what lets one code carry two sentences.

**No second unique index is needed to stop a double push-assign, and D1 explains why in the DDL comment.** Two concurrent push-assigns of one ticket to two rooms: both issue the UPDATE, the second blocks on the first's row lock, and when the first commits the second **re-evaluates its predicate against the updated row** (READ COMMITTED's EvalPlanQual on the locked tuple), finds `status = 'in_service'`, matches nothing, and takes the 409 branch. The ticket row **is** the serialisation point. `db` forced-interleave test; **mutation: drop `AND status = 'waiting'` from the predicate** → both succeed, two assignments carry one `queue_ticket_id`, the test reds.

⚠ **THE FIXTURE IS LOAD-BEARING AND IS PINNED IN THE TEST NAME: two DISTINCT staffers push-assign ONE ticket to two DISTINCT free rooms.** Both distinctions are the test, not decoration. Same room and F36's `idx_fitting_room_assignments_room_active` blocks the second insert; same target staffer and `…_staff_active` blocks it — either way the mutation comes back **green** and the shipped indexes pass the test for the wrong reason. This is a case the review caught by asking what the mutation would actually do, and it is recorded so a builder does not simplify the fixture.

**A push-assign losing the ROOM race rolls back exactly as D3a does** — same `try`, same helper, same absence of a savepoint, same absence of an idempotence branch, same four assertions.

**Which ticket, and from where.** The control lives on the waitlist row («שבצי לחדר»), and it needs a room. It offers the **free, active rooms from the `rooms` prop the panel already has** — no second fetch, no picker endpoint, the same argument `RoomsPanel` makes for building its handover list from `staff` (`RoomsPanel.tsx:88-92`). If no room is free the control is not rendered and the row carries one line saying so (D16, and the «no free room» state in «Every state»).

⚠ **IT IS AN INLINE REVEAL INSIDE THE ROW, NOT A `<dialog>`, and that is a decision made at review rather than left to the build.** An earlier draft listed "the assign dialog" in D15's file table and then never designed it — no element, no mount point, and none of D18's six focus moves covering it. A `<dialog>` here would need **three more** focus moves, all of which `RoomsPanel` has already had to ship: open → first focusable with the trigger in a ref; close → `dialogTriggerRef` with the `isConnected`-then-`h3` fallback, *resolved explicitly so the native `<dialog>`'s own focus return does not win* (`RoomsPanel.tsx:309-330`, MOVE 4); and a tick that drops the OPEN dialog's row → `setOpenDialog(null)` from an effect keyed on `[waitlist, openDialog]` (`RoomsPanel.tsx:292-307`, MOVE 5, whose comment reads *"a colleague releasing the room unmounts the tile and the dialog under the user's hands with focus inside — F57's own shipped MAJOR reproduced one level deeper, and axe sees none of it"*). F58 reproduces it one level deeper again: another manager takes Noa by take-next from her own device, the 5s tick drops her row, row and dialog unmount together, `activeElement` falls to `<body>`. **The inline reveal costs none of that**: it is a `Select` of the free active rooms plus «אישור»/«ביטול» rendered inside the row, structurally identical to the two confirm blocks, so **D18's MOVE 3 (departing row → `h3`), MOVE 4 (dismiss → trigger) and MOVE 5 (open → the question) already cover it** and the move count stays at six. Same information, same two taps, three fewer focus mechanisms to get right and to test.

### D5 — FINISH is F36's `release`, EXTENDED. There is no sixth route, and that is a safety property

`LOOP-STATE`'s F58 note describes FINISH («סיימתי עם הלקוחה») as its own verb. **The codebase-consistent reading is that it is the shipped release, extended**, and the argument is not economy — it is that a separate route would leave a **second, reachable path that strands tickets**.

`POST /manage/floor/assignments/{assignment_id}/release` is shipped, on the room tile, reachable by every role that may release, and it is what a staffer already taps when a fitting ends. If FINISH were a second route on the waitlist, then releasing from the room tile — the control that is already there, already documented, already tested — would free the room and leave the ticket `in_service` **forever**. That is precisely the defect this feature exists to eliminate, re-introduced by the feature that eliminates it.

So `FloorService.release` gains, inside its existing transaction, after the existing `wrote` branch:

```python
if wrote and row.queue_ticket_id is not None:
    closed = await self._tickets.close(session, tenant_id, row.queue_ticket_id, )
```

```sql
UPDATE queue_tickets SET status = 'done'
 WHERE tenant_id = :t AND id = :id AND status = 'in_service' AND deleted_at IS NULL
RETURNING id
```

**Five properties, each deliberate:**

1. **One transaction.** `release()` already runs inside `tenant_session`; the ticket close is one more statement in it. The worker frees and the entry closes together, or neither does — the ruling's requirement, satisfied by an addition rather than a new boundary.
2. **`queue_ticket_id IS NULL` → byte-identical shipped behaviour.** Every assignment F36 ever created takes the untouched path, so `test_floor_rooms_db.py` and `test_floor_service.py`'s release suites stay green with no edit, and that is the acceptance gate.
3. **`wrote is False` → no close.** A second release is a 200 that writes nothing (`floor/service.py:452-456`); closing an already-closed ticket must not write either. Both no-ops, one condition.
4. **`AND status = 'in_service'` in the predicate.** A ticket a manager removed while the fitting was running is `removed`, and a release must not resurrect it as `done`. Rowcount 0 here is **not** an error and raises nothing: the room is free, which is what she asked for.
5. **The audit row is the shipped `FITTING_ROOM_RELEASED`, with one key added to `details`** — `{"queue_ticket": str(id) | None}`. One act, one row. `audit_log` has no reader in the product yet (F53's activity log is the first, `constants.py`, F57's block), so the addition is additive and breaks nothing.

**HANDOVER needs no change at all**, and the reason is F36's design paying off: it mutates `staff_user_id` alone, so `queue_ticket_id`, `created_at`, the assignment id and the dress bindings all survive for free (`fitting_room_assignments.py:235-260`). A walk-in handed to a colleague keeps her ticket, her elapsed clock and F37's future alert pointer.

**`delete_room` needs no change either**: it already refuses an occupied room with `ROOM_OCCUPIED` naming the holder, and an assignment serving a walk-in is occupied like any other.

### D6 — SKIP: one atomic statement, and the second skip removes

```sql
UPDATE queue_tickets
   SET requeued_at = :now,
       called_at   = NULL,
       skip_count  = skip_count + 1,
       status      = CASE WHEN skip_count + 1 >= 2 THEN 'removed' ELSE 'waiting' END
 WHERE tenant_id = :t AND id = :id AND status = 'waiting' AND deleted_at IS NULL
   AND skip_count = :seen_skip_count            -- ⚠ added at review; see below
RETURNING id, skip_count, status
```

**⚠ `AND skip_count = :seen_skip_count` IS NOT BOOKKEEPING — WITHOUT IT TWO ORDINARY SINGLE TAPS REMOVE A CUSTOMER WITH THE CONFIRM BYPASSED.** This was the review's third BLOCKER and it is worth tracing, because the earlier draft analysed the race one step short and then asserted its outcome as the *pass condition* of A15. Two managers on two tablets see the same no-show at `skip_count == 0` and both tap «דלגי»:

- A takes the row lock, writes `skip_count = 1`, `status = 'waiting'` (0+1 ≥ 2 is false), commits.
- B was blocked on the lock. On A's commit, READ COMMITTED's EvalPlanQual re-evaluates B's predicate against the **new** tuple: `status = 'waiting'` still holds, so B proceeds — and B's SET expressions read the **new** row: `skip_count` 1 → 2, `CASE WHEN 1 + 1 >= 2` → **`'removed'`**.

She is **removed from the queue, irreversibly, with no undo (Risk 3), by two single taps, and neither client ever showed the confirm** — because D8 gates the confirm on `skip_count >= 1` and both clients rendered `skip_count == 0` from the same tick. The whole stated rationale for putting `skip_count` on the wire is that *"a control that silently changes meaning on its second press is the shape this number exists to prevent"*; this is the control silently changing meaning on its **first** press, on the one destructive act in the feature.

**The fix is one conjunct and one request field, and it reuses machinery D4 already designs.** `POST …/skip` takes `{seen_skip_count: int}` — the value the client rendered, which is already on the wire. B's rowcount is then 0 and B takes the refusal read (`status_of`, which returns `(status, skip_count)` for exactly this): the row is live and `waiting` but its count moved, so **409 `QUEUE_TICKET_CHANGED`** with `details={"skip_count": …}` and «מצב הכניסה השתנה. רענני ונסי שוב.» The manager's next tick shows `skip_count == 1` and her next press correctly opens the confirm. The atomic `skip_count + 1` **stays** — it is still what makes the increment lost-update-proof on the deliberate second skip.

**ONE statement, and every part of that is load-bearing.**

- **`skip_count = skip_count + 1` is the ATOMIC increment**, never a Python read-modify-write. Two managers skipping the same no-show would otherwise both read 0, both write 1, and she would never reach the removal the rule promises (`TRANSACTIONS.md`'s balance rule, and the only place in this codebase it applies to a counter).
- **The `CASE` reads the PRE-update `skip_count`**, because every SET expression in one UPDATE is evaluated against the old row. `skip_count + 1 >= SKIP_LIMIT` with `SKIP_LIMIT = 2` therefore means *"this is her second skip"*, which is the brief's rule exactly. `SKIP_LIMIT` is a named module constant — no magic number, and one place to change it if a pilot asks.
- **`requeued_at = :now` is the whole skip-to-back**, and it is a one-column write rather than a renumbering pass because `position()` orders on `COALESCE(requeued_at, created_at)` (F33's D3, which shipped that `COALESCE` before anything wrote the column *precisely so this feature could not change a published read's semantics by adding one*).
- **⚠ `called_at = NULL`, and this is a decision the rulings did not name (Decision 7).** She was called and did not come; that is *why* she is being skipped. Leaving the stamp would highlight her on F59's public wall board at the **back** of the queue, and her own page would read «אפשר לגשת לדלפק» indefinitely. Clearing it is the only spelling under which both surfaces stay true. It also makes the summons re-issuable: the manager can call her again when she comes round.
- **Two concurrent skips serialise on the row lock and the loser is REFUSED, not silently escalated.** The second re-evaluates the predicate against the updated row: if the first removed her, `status = 'waiting'` matches nothing (→ 409 `QUEUE_TICKET_NOT_WAITING`); if the first only incremented, `skip_count = :seen_skip_count` matches nothing (→ 409 `QUEUE_TICKET_CHANGED`). **A skip never escalates on a count the caller did not see.**

**Rowcount 0 → a THREE-answer read** (`status_of` returns `(status, skip_count)`): no row → 404; `status != 'waiting'` → 409 `QUEUE_TICKET_NOT_WAITING`; `status == 'waiting'` with a different `skip_count` → 409 `QUEUE_TICKET_CHANGED`. Audit: `QUEUE_TICKET_SKIPPED` with `details = {"ticket", "skip_count", "status"}`, so a removal-by-second-skip is legible in the trail without a second action value.

### D7 — CALL: stamps `called_at`, leaves `status = 'waiting'` — the contract F59 cannot enforce for itself

```sql
UPDATE queue_tickets SET called_at = :now
 WHERE tenant_id = :t AND id = :id
   AND status = 'waiting' AND deleted_at IS NULL AND called_at IS NULL
RETURNING id, called_at
```

**⚠ `status` IS NOT TOUCHED, and F59's spec records that its board breaks if it is.** `public-queue-board.md` D10/Risk 6, written while F58 was queued and quoted here so it cannot be missed:

> **The contract F58 must keep, recorded here because F59 cannot enforce it.** F58's `CALL` must stamp `called_at` and leave `status = 'waiting'`. If F58 flips the status to `in_service` at call time instead, **the called row drops off this board the instant it is called** — the opposite of the feature — because D3's predicate is `status == 'waiting'`, byte-identical to `position()`'s.

Being called and being taken are two facts. Call is a summons awaiting a response; take-next/push-assign is the staffer having her. Nothing else in this feature couples them.

**`called_at IS NULL` in the predicate makes a second call keep the FIRST timestamp** — `release()`'s shipped idempotence, one table over (`fitting_room_assignments.py:208-210`).

⚠ **CALL'S ROWCOUNT 0 HAS THREE CAUSES, NOT D4'S TWO, AND IT GETS ITS OWN TABLE RATHER THAN A REFERENCE.** The extra `called_at IS NULL` conjunct is what adds the third, and on this verb rowcount 0 is the **normal, expected, non-error** case — a re-call. An earlier draft said "the same two-answer read as D4", and a builder implementing D4's two-branch table literally on this path falls through with no branch at all for `status == 'waiting'`: a silent no-op reported as success, or a 500.

| `status_of` result | Answer |
|---|---|
| `None` | `QueueTicketNotFoundError` → 404 |
| `status != 'waiting'` | `QueueTicketNotWaitingError` → 409 |
| `status == 'waiting'` (i.e. `called_at` was already set) | **200**, the current waitlist, **no audit row** |

She wanted her called and she is called; a `{called → called}` row would be noise in a write-only trail, and F36's block states the rule. A17 asserts the third row explicitly.

**Take-next and push-assign do NOT stamp `called_at`, and the reason is a shipped Hebrew string.** `QueuePositionPage.tsx:317-341` renders `called` **ahead of** the in-service arm, so stamping both would make `checkin.statusInService` («התור שלך התחיל», `he.ts:446`) unreachable on every path in the product — a shipped string deleted by implication. See D14 for the one collision that remains and its three-line fix.

### D8 — REMOVE, and the duplicate-ticket remedy designed rather than named

```sql
UPDATE queue_tickets SET status = 'removed'
 WHERE tenant_id = :t AND id = :id AND status = 'waiting' AND deleted_at IS NULL
RETURNING id
```

**One verb covers both obligations**, and they are the same act: a no-show who is never coming back, and the second of Ruling 3's two tickets for one woman.

**Why not "merge".** A merge is a two-argument operation and it has to decide two things a remove does not: which capability survives, and whose arrival time wins. Both answers are bad. Keeping the **later** ticket costs her place in the queue. Keeping the **earlier** one — which is her true arrival and the right answer for the queue — means the ticket her *current* tab is polling goes `removed`, and F33's page renders «הביקור הזה הסתיים.» and **stops the loop** at a woman who is still in the queue. There is no third option: the only column that could move a survivor forward is `requeued_at`, whose entire published meaning is skip-to-**back**, and overloading it to mean "forward" would make `requeued_at < created_at` representable for the first time and falsify the model comment that defines it.

**So the remedy is: remove the duplicate, keep her real place, and be honest about the one consequence.** The device polling the removed ticket reaches the closed terminal. She is standing in the shop, three metres from the counter — which is the same disposition F33 took when it declined cross-device recovery outright. Stated as Risk 2 rather than argued away.

**Removing a person from a queue is destructive and has no undo, so it gets a confirm and a name.** Two-step, the shipped `ManageBookingPage` cancel-reveal shape: the row's «הסרה» reveals a confirm block naming **the entry** — «להסיר את נועה מהתור?» — with «אישור» / «ביטול», focus moved onto the question (D18, and the same test discipline that caught this class four times). *Declined a restore verb.* It is one more route, one more gate, one more audit value and one more control, to undo an act that already has a confirm in front of it and an audit row behind it; **recorded as the upgrade path**, with Risk 3 naming the mis-tap consequence and its trigger.

**Skip also gets a confirm, but only on the press that removes** — i.e. when the entry's rendered `skip_count >= 1`. The first skip is harmless and must stay one tap; a control that silently changes meaning on its second press is what `skip_count` is on the wire to prevent. **And the server enforces what the client renders**, which is D6's `seen_skip_count`: if the count moved under her, the press is refused rather than escalated, so the confirm cannot be bypassed by a stale tile.

Audit: `QUEUE_TICKET_REMOVED`, `details = {"ticket"}`. Rowcount 0 → D4's two-answer read (remove has no `skip_count` conjunct, so its rowcount 0 really does have only the two causes).

### D9 — The duplicate flag: what makes the remedy safe rather than a guess

Without it, a manager with forty rows on screen and two «נועה»s removes one of them by inference. Two women genuinely called Noa is not a rare event in a bridal boutique, and the entry she removes has no undo.

**The rule:** `duplicate = true` when another **live** ticket (`status IN ('waiting','in_service')`, `deleted_at IS NULL`) of the same `queue_day` carries the **same normalised phone**.

⚠ **AND D2 HAD NO READ THAT COULD COMPUTE THE HALF THAT MATTERS MOST — corrected at review, in D2 rather than here.** The first draft said the flag was *"derived in Python from the projection D2 already selects, in one pass over at most `WAITING_LIMIT` rows plus the day's in-service tickets"*, but D2's statement filters `status == 'waiting'` and returns **no `in_service` row at all**, no second statement was specified anywhere, and `WAITING_LIMIT` is not even the constant's name (`WAITLIST_LIMIT` is). As written, the flag would only ever have fired for waiting↔waiting pairs — silently blind to precisely the case the paragraph below calls *"the most valuable thing on this panel to remove"*, and blind in the direction where a manager with two «נועה»s and neither one flagged removes by inference. **D2 now specifies the second statement**: a phone-only projection over today's `in_service` rows, on the same session, over the same non-status-narrowed index, with no name and no id in it. `duplicate` is then `phone in (waiting phones seen more than once) | (in-service phones)`.

**One honest limit, stated rather than left to be inferred from a badge:** the waiting read is capped at `WAITLIST_LIMIT`, so a pair straddling the bound is not flagged — the twin at row 101 is invisible and row 40 renders clean. **`truncated: true` therefore means the duplicate flag is best-effort on that payload**, and the panel's truncation line is the only signal a manager gets. Accepted: the bound bites only inside a griefing flood (F33 Risk 1), and a flag that lies by omission on row 40 of a 40-row list would be the real problem.

**A boolean, not a group index.** A woman's twin can be `in_service` — she re-scanned, was dispatched on the first ticket, and the second is still waiting; that ghost is the most valuable thing on this panel to remove, and a group *number* would render a group of one visible row, which reads as a bug. The boolean says the true thing in both cases: *this entry duplicates another live entry today*. Two flagged rows with the same name are the pair, and the manager can ask.

**Grouping is by phone and by nothing else, which is exactly why D2 corrects the repository docstring.** `name` is free text she typed and collides legitimately; `phone` is normalised to E.164 at insert (`queue/service.py:89`, `normalize_israeli_mobile`), so exact string equality is the right key. **The phone never reaches the wire** — a fast test asserts no E.164-shaped string appears anywhere in the payload, and **three** `db` assertions cover the rule: the flag is true for two same-phone **waiting** tickets, **true for a waiting ticket whose same-phone twin is `in_service`** (the case an earlier draft could not compute and did not test), and false for two same-name-different-phone ones. **Mutations: key the grouping on `name` instead of `phone`** → the third reds; **delete the in-service statement** → the second reds.

**No index, no column, no migration.** `test_queue_tickets_carries_no_unique_index_but_the_primary_key` is the guard, and Ruling 3 is the reason it exists.

### D10 — `client_label` on the room tile now resolves through the queue too, and the payload's privacy sentence changes for the third time

`FittingRoomsRepository._occupancy_rows` (`fitting_rooms.py:254-336`) drives from `fitting_rooms` through **four** LEFT joins — `fitting_room_assignments` → `staff_users` → `bookings` → `customers`, counted at `:281`, `:290`, `:297`, `:306` — and produces `client_label` from `customers.name`. **F58 makes it five.** (Corrected at review: an earlier draft said five and asked for a sixth, on the section a reviewer is told to check hardest.) A walk-in has no booking and no customer row, so **without one more join every dispatched walk-in renders as an anonymous visit** — the tile would say a room is occupied and refuse to say by whom, on the surface whose entire purpose is to answer that.

**One more LEFT join, at the end of the chain:**

```python
.outerjoin(
    QueueTicket,
    and_(
        QueueTicket.tenant_id == tenant_id,
        QueueTicket.id == FittingRoomAssignment.queue_ticket_id,
        QueueTicket.deleted_at.is_(None),
    ),
)
```

and `client_label = func.coalesce(Customer.name, QueueTicket.name)`.

- **`deleted_at IS NULL` and nothing else on this join, and the asymmetry with the `bookings` join is deliberate.** The bookings join also excludes `status = 'cancelled'` because a cancelled appointment is not a fitting; a ticket's terminal statuses are the *normal end* of a fitting the tile may still be rendering during the same transaction, so filtering on status would blank the label at exactly the wrong instant. `deleted_at` is the retention/erasure signal, which is the one that must remove the name — the `customers` join's rule, applied unchanged.
- **`COALESCE` and not a branch**, because both pointers are nullable and independent: null/null is the anonymous visit F36 already ships, and a bride who booked *and* scanned resolves to her `customers` name, which is the record with a verified phone behind it.
- **Still resolved on EVERY read and never snapshotted** — `models/fitting_room_assignment.py`'s standing rule. A ticket F20's sweep deletes makes the tile render an anonymous visit rather than preserving a name in a table nobody thought of.
- **`RoomRow` gains no field — `client_label` gains a source**, so all three callers of `_occupancy_rows` (`list_with_occupancy`, `room_with_occupancy`, `occupancy_for_staff`) inherit it. That is the intended behaviour on every one of them, and it is asserted once (A20) rather than assumed three times.
- **`Occupancy` on the staff card inherits this for free**, since `occupancy_by_staff_id` is derived from the same `room_rows` (`floor/service.py:216-219`).

**⚠ THE PAYLOAD'S PRIVACY SENTENCE IS NOW FALSE FOR THE SECOND TIME, AND THIS PR REWRITES IT FOR THE THIRD.** Three shipped comments — `floor/router.py:17-26`, `floor/service.py:184-201`, `floor/schemas.py:13-19` — say, in the same words, and one of them is the stated justification for **the only router in the product admitting five roles**:

> the floor payload carries the minimum customer datum required by the person standing on the floor — **at most one name per occupied room**, for the duration of the fitting, never the day's customer book.

F58 puts **up to a hundred names** on it. F36's own note records why this cannot be left alone: *"Leaving them would leave a false comment standing as the rationale for the widest role gate in the codebase."* The rule as it actually is after this feature, and it is still a real limit rather than a retreat:

> **The floor payload carries the people who are physically in the boutique right now** — one name per occupied fitting room, plus the name of every walk-in currently waiting to be served — **and never the day's booking book.** Every name leaves the payload the moment she does: a released fitting, a served ticket, a skipped-out ticket, a removed ticket, or midnight Jerusalem. Nothing on it carries a phone, an email, an address or a consent flag. **It DOES carry each waiting ticket's id, and that id is F33's position-page capability** — this payload is the only server path other than the check-in response that emits one, so it is disclosed to a signed-in staffer of this tenant and to nobody else, and **the console must never render it as a link to `/q/{id}`.**

⚠ **The last clause was written twice before it was true.** An earlier draft of this very rewrite ended *"…a consent flag or a stable customer identifier"* — false about the payload it was introducing, since `WaitlistEntry.id` is stable for the whole visit and is a bearer capability, and D2's own comment on that field said so two hundred lines earlier. Shipping a newly-written false comment is worse than leaving an old one: it is the sentence the reviewers of F20, F37 and F41 will rely on, and it would have understated the disclosure at the exact moment the name count goes from ≤3 to ≤100 on a five-role router (Risk 4). The ⚠ from D2's field comment is folded in here rather than left in a schema docstring, because **this** comment is what the next reviewer reads.

The contrast that keeps D11's two-loops conclusion right is unchanged and still exact: `GET /manage/bookings?date=` is the **day book** — every customer booked today with her type, dress, size, notes, status and manage-token surface, for the whole day, to two roles. `GET /manage/floor` is **the room**.

### D11 — Role gating: three routes join `FLOOR_OPEN`, two are deliberately absent, and the middle option is structurally forbidden

| Route | Gate | In `FLOOR_OPEN`? | Why |
|---|---|---|---|
| `POST /manage/floor/rooms/{room_id}/take-next` | router's five + service `_authorize(target, actor)` | **yes** | Target-dependent (herself, or elevated on anyone) — the `claim` rule verbatim, and no `RoleGate` can express it |
| `POST /manage/floor/rooms/{room_id}/assign` | same | **yes** | same |
| `POST /manage/floor/queue/{ticket_id}/call` | router's five, no service check | **yes** | A summons is not destructive and has no target staffer. Reception, a sales assistant and a seamstress all legitimately call the next woman forward |
| `POST /manage/floor/queue/{ticket_id}/skip` | `ELEVATED` | **no — absence is the assertion** | Re-orders a stranger's place in a queue, and its second press removes her |
| `POST /manage/floor/queue/{ticket_id}/remove` | `ELEVATED` | **no — absence is the assertion** | Takes a real customer out of the queue, irreversibly |
| `POST …/assignments/{assignment_id}/release` (finish) | unchanged | already in | D5 changes no gate |

`ELEVATED` is F36's shipped constant (`floor/router.py:173`), reused, not redeclared.

**⚠ THE OBVIOUS MIDDLE OPTION — `require_role(OWNER, SHIFT_MANAGER, RECEPTION)` — IS STRUCTURALLY FORBIDDEN, and this is a finding rather than a preference.** `test_the_floor_roles_reach_exactly_the_floor_routes` computes `effective = frozenset.intersection(*role_sets)` and then:

```python
if effective & FLOOR_ROLES:                 # :313
    admits_floor.add((method, path))
    if not effective >= FLOOR_ROLES:        # :315
        partial.append(...)
...
assert not partial, "floor routes admitting only some floor roles"   # :329
```

A gate admitting reception but not seamstress lands in `admits_floor` (the intersection is non-empty) **and** in `partial` (it is not a superset), so assertion 2 red-fails — on a route that is arguably correct. The docstring anticipates the response and forbids it: the test *"MUST NEVER BE RELAXED TO A SUBSET CHECK"*, and *"A reviewer facing that red on a test declared untouchable is most likely to 'fix' it by relaxing the assertion, which is precisely the outcome Risk 1 exists to prevent."*

**So every route in this product is all-five or exactly-two. There is no middle, and F58 takes the codebase-consistent reading**: skip and remove are `ELEVATED`. The product consequence is real and recorded — **a reception staffer cannot skip a no-show or remove a duplicate; she calls a shift manager** — and it is the honest cost of a guard whose whole value is that it never bends. *Upgrade path if a pilot asks: the service-side target-dependent form the claim and the release use. It does not apply today because skip has no "target" that can be the caller, so there is nothing for a self-or-elevated rule to compare.*

**A 403 is TERMINAL for the whole floor screen** (`usePoll.terminalOf` returns `"access"` for any 403, and for the three floor roles that is the entire product going dark), so **the panel renders no control a caller may not use** — no disabled button, no lock glyph, no «אין לך הרשאה» line, no tooltip. `RoomsPanel.tsx:26-31` states the rule; `WaitlistPanel` inherits it.

**Every path's second segment is `floor`**, so `apps/manage/vite.config.ts` needs no edit and `test_spa_serving.py:377`'s set equality holds unchanged. `/manage/queue/{id}/call` would have read better and cost that edit — the failure mode F57's shipped note calls *"the nastiest of the three: production, CI and the suite all stay green while only a developer's machine breaks, serving the SPA shell where the API should be."*

**CSRF**: all five are POSTs, and `CsrfOriginMiddleware` gates on `request.method in MUTATING_METHODS` under `/manage` (`csrf.py:48`) — a method test, not a path list, so the five are fenced by construction.

### D12 — Three new error codes, and everything else reuses shipped machinery

| Condition | Class | Status | Code | `details` | Hebrew |
|---|---|---|---|---|---|
| The queue is empty at take-next | `QueueEmptyError` | 409 | `QUEUE_EMPTY` | — | «אין ממתינות בתור.» |
| The ticket is not `waiting` | `QueueTicketNotWaitingError` | 409 | `QUEUE_TICKET_NOT_WAITING` | `{"status": …}` | «היא כבר בטיפול.» / «הכניסה הזו נסגרה.» |
| **A skip whose `skip_count` moved under the caller** | **`QueueTicketChangedError`** | 409 | `QUEUE_TICKET_CHANGED` | `{"skip_count": …}` | «מצב הכניסה השתנה. רענני ונסי שוב.» |
| The ticket is gone / another tenant's | `QueueTicketNotFoundError` (**shipped, F33**) | 404 | `NOT_FOUND` | — | «הכניסה הזו כבר לא קיימת.» |
| The room is taken | `RoomOccupiedError` (**shipped**) | 409 | `ROOM_OCCUPIED` | `{"staff_display_name"}` opt. | «דנה כבר בחדר הזה.» / «החדר נתפס זה עתה. נסי שוב.» |
| The staffer holds another room | `StaffOccupiedError` (**shipped**) | 409 | `STAFF_OCCUPIED` | `{"room_label"}` opt. | «היא כבר בחדר 2.» / «היא כבר בחדר אחר.» |
| The room is gone / inactive | `DomainNotFoundError("fitting_room")` (**shipped**) | 404 | `NOT_FOUND` | — | «החדר כבר לא זמין.» |
| **A unique violation nobody predicted** | the original `IntegrityError`, **re-raised** | 500 | — | — | the outage register |

**⚠ THE LAST ROW IS A ROW, not an omission.** F36 wrote a whole docstring on why an unrecognised constraint must 500 rather than be mapped to `ROOM_OCCUPIED` (*"silently mapping it … would tell a staffer a lie about furniture"*), and the first draft's helper signature — `raise await self._occupied_error(...)`, a helper that *returns* an exception object — could not express "re-raise the original" at all. D3a's helper therefore returns `error` on that branch and the caller's `raise … from error` re-raises it. **There is deliberately NO idempotent-200 row in this table**, and D3a says why in the one place a builder will look.

The three new classes subclass `floor/validation.py`'s `_OccupiedError` pattern — **explicitly NOT `DomainValidationError`**, because Starlette resolves a handler by walking `type(exc).__mro__` and parenting them onto the domain-400 base would make the shipped 400 handler answer first and leave the 409 handlers unreachable (`floor/validation.py:44-52`, the trap written out). Three module constants beside `ROOM_OCCUPIED_BODY`, three three-line handlers, `_occupied_body` reused for the two that carry `details`. `QueueTicketNotFoundError` needs **no handler at all** — `main.py` records that the base class's 404 handler answers it, and that is why the subclass is free. `ApiError.details` and `extractError` need **no change** — F36 already typed them `Record<string, string> | undefined`.

### D13 — Four `AuditAction` members, no migration, and one shipped `details` key added

`audit_log.action` is plain TEXT with no CHECK (0003) — the **eighth** block to rely on that fact.

```python
# F58's floor dispatch (D13). No migration, same as every block above.
#
# ONE value for both dispatch verbs, with the mode in `details`, and that is
# CUSTOMER_UPDATED's split criterion rather than BOOKING_*'s: the question this
# table gets asked is "who put whom in which room", and nobody will ever ask it
# "who used the take-next button but not the assign one". The row already names
# the ticket, the room, the assignment and the staffer, so a second action value
# would carry no information the first does not.
#
# ⚠ A dispatch writes THIS row and NOT a second FITTING_ROOM_CLAIMED: the claim
# row's whole content is a subset of this one's, and two rows for one act is the
# noise D13 declined FITTING_ROOM_CREATED over.
#
# A NO-OP WRITES NO ROW — F36's rule, and it bites three times here: a second
# call, a lost take-next race (D3a: the transaction is gone, so the row is too),
# and a release whose ticket was already closed.
QUEUE_TICKET_DISPATCHED = "queue_ticket_dispatched"   # {ticket, room, assignment, staff, mode}
QUEUE_TICKET_CALLED = "queue_ticket_called"           # {ticket, called_at}
# skip_count and the resulting status ride in `details` so a removal-by-second-
# skip is legible without a fifth action value.
QUEUE_TICKET_SKIPPED = "queue_ticket_skipped"         # {ticket, skip_count, status}
QUEUE_TICKET_REMOVED = "queue_ticket_removed"         # {ticket}
```

**No name and no phone in any `details` object.** `audit_log` has no retention policy and platform operators read across tenants — `CUSTOMER_UPDATED`'s block states the rule in as many words, and a queue ticket's name is a third party's exactly as customer notes are. Ids only.

**`FITTING_ROOM_RELEASED` gains `"queue_ticket"` in its `details`** (D5). Additive; nothing reads `audit_log` in the product yet.

This closes F33's Risk 12 — *"'who called her forward' and 'who removed her' are the two questions that will want rows"* — by name.

### D14 — One three-line correction to a shipped storefront component, because F58 makes a collision reachable

`QueuePositionPage.tsx:317-341` renders, in order: `closed` → `called` → `position !== null` → `position === null`. F58 makes `called_at` and `status = 'in_service'` co-occur for the first time (a woman who was called and then taken), and in that state the page renders «אפשר לגשת לדלפק» — telling a woman standing in a fitting room to approach the counter, and making «התור שלך התחיל» unreachable on the only path that produces it.

**The fix is a precedence reorder, not new copy:** derive `inService = ticket.status === "in_service"` and order the arms `closed → inService → called → position`. Three lines, no string added, no string removed, both sentences reachable and correct.

*Declined the alternative* — having take-next clear `called_at` — because that would erase the record that she was summoned, on the one column F59 reads, for a rendering problem that belongs to the renderer.

**A vitest case per arm, driven by a stubbed API client**, exactly as F33 tests its own terminal (its D10: *"the `done` fixture is seeded by the stubbed API client, which is the only way it can be produced"*). **Mutation: restore the shipped order** → the `in_service`-after-`called` case reds and nothing else does.

### D15 — `WaitlistPanel` is a CHILD of `FloorPanel`: one poll, one pause control, one announced region

`RoomsPanel`'s contract, applied a second time — which is what makes the pattern reviewable rather than a one-off:

- **No `usePoll` instance, no timer, no pause control, no `role="status"` of its own.** It receives `waitlist`, `rooms`, `serverNow`, `fetchCount`, `selfId`, `role`, `paused`, `mutate`, `onWaitlist`, `onRooms`, `onCue` as props.
- **`FloorPanel` owns the state**, as it already owns `rooms`: the staff, the rooms and the waitlist arrive in **one response**, so two owners would be two freshness claims that can disagree by an interval with no way to tell which to believe (`FloorPanel.tsx:73-77`, verbatim reasoning).
- **`onWaitlist` is an UPDATER, never a finished list** — `applyRooms`'s shape and its review history. Two waitlist rows can be in flight at once (`busy` is per entry, `mutate` counts rather than latches), and a handler that rebuilt the list from the `waitlist` prop it closed over would erase the other handler's patch. This is F36's sharper MAJOR, pre-paid.
- **Every mutation patches from the SERVER's response, never optimistically** — which is what makes an idempotent second call render the *first* timestamp rather than this request's intent.
- **Placement: BELOW the rooms and ABOVE the staff cards.** The rooms are what she acts on, the queue is what she acts *from*, and the staff cards are reference. `RoomsPanel` sits above the staff list for the same reason (`FloorPanel.tsx:605-608`), and the ordering keeps `BoardSection`'s one-shot `scrollIntoView` target undisturbed (`App.tsx:206-208`).

**Response shapes, so a tile and a row can each patch in place:**

```ts
// take-next, assign: the room tile AND the queue both changed.
interface DispatchResult { room: Room; waitlist: Waitlist }
// call, skip, remove: only the queue changed.
type QueueResult = Waitlist
```

**`DispatchResult` carries no customer name and does not need one.** Take-next is tapped from a room tile, so the caller does not know which entry the server will take, and after the dispatch that entry is gone from `waitlist`. The only field that *could* carry her name is `room.assignment.client_label` — which D10 does make equal to the ticket's `name`, but which is null on the anonymous branch. **The cue renders from `result.room.label`, which is always present** (D16), and that is not a workaround: it is the same rule `rooms.claimedCue` already ships under.

The whole waitlist travels rather than one entry, because **skip reorders it** and remove/second-skip shorten it — a per-entry patch cannot express either. It is at most a hundred short rows on a refusal-rare path. `release` keeps answering `Room` **unchanged**: finishing a fitting does not touch the waiting list at all.

**No `server_now` on a mutation response.** Elapsed lines stay anchored to the last tick's instant (≤5s), which is exactly what the room tiles already do — a second freshness anchor is a second thing that can disagree.

### D16 — i18n: a new `waitlist.*` namespace, Hebrew only, `ar` untranslated

Its own flat-dotted namespace and its own constant in `__tests__/i18n.test.ts` (`HE_F58 = entries(he.translation, (key) => key.startsWith("waitlist."))`), folded into `HE`, with its own floor. **Its own, and not folded into `HE_F57`**, for the reason that file states three times: folding lets a feature's rows shrink by that many and still pass. **No `nav.` term in the selector** — the waitlist is content of the floor, not a thirteenth console section, so F58 adds no nav row (F36's `HE_F36` comment, verbatim situation).

**⚠ ONE KEY IS DELIBERATELY OUTSIDE THIS NAMESPACE: `rooms.error.QUEUE_EMPTY`.** Take-next's control lives on the ROOM TILE (D17), so its refusals are rendered by `RoomsPanel.describe()` alongside the four F36 sentences, and a `waitlist.`-keyed string in that alert would be the only foreigner in it. `HE_F36`'s floor (`i18n.test.ts:424`, currently `>= 70`) goes up by one; `HE_F58`'s floor counts the rest.

The deck (Hebrew only; `ar.ts` gets the same keys untranslated, per the 2026-07-31 languages ruling and F15's Risk 5):

| Key | Hebrew |
|---|---|
| `waitlist.heading` | «ממתינות בתור» |
| `waitlist.empty` | «אין ממתינות בתור» |
| `waitlist.visitBride` / `waitlist.visitEvening` | «שמלת כלה» / «שמלת ערב» |
| `waitlist.waiting` | «ממתינה {{minutes}} דק'» |
| `waitlist.waitingJustNow` | «הגיעה זה עתה» |
| `rooms.error.QUEUE_EMPTY` (**`rooms.`, not `waitlist.`** — see below) | «אין ממתינות בתור.» |
| `waitlist.called` | «נקראה» |
| `waitlist.duplicate` | «כניסה כפולה» |
| `waitlist.skippedOnce` | «דילגו עליה פעם אחת» |
| `waitlist.takeNext` / `waitlist.takeNextAria` | «קחי את הבאה» / «קחי את הבאה בתור לחדר {{room}}» |
| `waitlist.assign` / `waitlist.assignAria` | «שבצי לחדר» / «שבצי את {{name}} לחדר» |
| `waitlist.call` / `waitlist.callAria` | «קראי» / «קראי ל{{name}}» |
| `waitlist.skip` / `waitlist.skipAria` | «דלגי» / «דלגי על {{name}}» |
| `waitlist.remove` / `waitlist.removeAria` | «הסרה» / «הסרת {{name}} מהתור» |
| `waitlist.confirmSkip` | «דילוג נוסף יסיר את {{name}} מהתור. להמשיך?» |
| `waitlist.confirmRemove` | «להסיר את {{name}} מהתור?» |
| `waitlist.confirmYes` / `waitlist.confirmNo` | «אישור» / «ביטול» |
| `waitlist.noFreeRoom` | «אין חדר פנוי כרגע.» |
| `waitlist.truncated` | «הרשימה ארוכה מהמוצג.» |
| `waitlist.dispatchedCue` | «הלקוחה נכנסה לחדר {{room}}.» — **no name; see below** |
| `waitlist.calledCue` / `waitlist.skippedCue` / `waitlist.removedCue` | «נשלחה קריאה.» / «הועברה לסוף התור.» / «הוסרה מהתור.» — **no name** |
| `waitlist.error.QUEUE_TICKET_NOT_WAITING` | «היא כבר בטיפול.» |
| `waitlist.error.QUEUE_TICKET_CHANGED` | «מצב הכניסה השתנה. רענני ונסי שוב.» |
| `waitlist.error.notFound` / `waitlist.error.notFoundPaused` | «הכניסה הזו כבר לא קיימת. הרשימה תתוקן בעדכון הבא.» / «…העדכון מושהה.» |
| `waitlist.error.ROOM_OCCUPIED` / `…Unknown` / `waitlist.error.STAFF_OCCUPIED` / `…Unknown` | F36's four sentences, re-keyed for this panel's alert |

**Names and room labels render inside a bare `<bdi>`, never `dir="ltr"`** — forcing LTR on a Hebrew name reverses its words (`FloorPanel.tsx:655-659`). **No truncation and no ellipsis on a person's name, ever**: a panel that abbreviates makes two women look like one, and this is the panel where that decides who gets removed.

**⚠ NO CUSTOMER'S NAME GOES IN THE CUE — the four cues above were rewritten at review, and the first draft had the shipped rule backwards.** It cited `RoomsPanel.tsx:465-469` as saying *"a waiting woman's name never enters the cue on a refusal, only on an act the manager just performed"*. That is not what it says. Verbatim:

> The cue names the ROOM and never the client. The region is **PERSISTENT** — nothing clears it on a timer — so a bride's name in it would sit on a five-role screen for an arbitrary length of time, in a room she is standing in. The tile one line away carries her name for exactly as long as the fitting lasts.

**The rule is about persistence, not about refusals**, and `FloorPanel.tsx:501-521` confirms it: the cue is a plain `<p role="status">` overwritten only by the next cue and cleared by nothing — no timer, no tick, no unmount. Every shipped floor cue obeys it (`rooms.claimedCue`/`releasedCue` name the room, `handedOverCue` and `floor.breakStartedCue` name a **staffer**); no customer name has ever entered that region. F58's four cues would have been **strictly worse than the case F36 declined**: «נועה הוסרה מהתור.» sits in the DOM of a five-role screen after her row has left the payload *and after she has left the shop*, so the cue becomes the only place her name survives — which directly falsifies D10's rewritten promise that *"every name leaves the payload the moment she does"*, on the surface Risk 4 calls the most legally sensitive line in the spec. So the cues **name the act, not the person**, and the row (or the tile) one line away carries her name for exactly as long as she is on the floor. `{text, name}` bidi pairing is dropped for these four (`name: null`); the dispatch cue's `{{room}}` comes from `result.room.label`.

`waitlist.waiting` / `waitlist.waitingJustNow` are rendered by `WaitlistPanel` from **`elapsedMinutes(serverNow, entry.arrived_at)`** — not by `elapsedLine`, which hard-codes `rooms.elapsed*` and would ship the room's copy while leaving these two keys dead and green (see «What already exists»). Same clamp, same server anchor, «דק'» invariant and **no plural rule** — this must not become the console's first i18next plural.

### D17 — Design: what the panel is, in one paragraph, so the build has no room to invent

A `Card` under the room tiles, headed «ממתינות בתור» (`h3`, `tabIndex={-1}`, the focus-rescue target). Inside, a `<ul className="divide-y divide-border">` of rows, one per entry, in server order. Each row: the **position number** in a fixed-width run, then the **name** in a `<bdi>` at `font-semibold`, then a muted line carrying visit type «·» wait time, then at most two `Badge`s — «נקראה» (`warning`) and «כניסה כפולה» (`neutral`). Controls right-aligned on `sm:` and stacked at 375: «קראי» (`ghost`), «שבצי לחדר» (`secondary`), and for elevated «דלגי» (`ghost`) and «הסרה» (`ghost`). **`size="md"` on every one** — `min-h-11` is 44px and `sm` is `min-h-9` = 36px, under the floor, which is the trap `BoardSection.test.tsx:507-512` writes out.

**«שבצי לחדר» opens an INLINE REVEAL inside the row — not a `<dialog>`, and not an unspecified "assign dialog".** Structurally the third of the row's three reveals, identical to the two confirm blocks: a `Select` labelled with the free active rooms from the `rooms` prop, «אישור» / «ביטול», focus onto the `Select` on open and back to the trigger on dismiss. **This is why D18 still has six focus moves and not nine** — D4 spells out the three `RoomsPanel` had to ship for its `<dialog>`s and why F58 declines to inherit them.

The **«קחי את הבאה»** control is **not** on this panel: it lives on each free, active room tile in `RoomsPanel`, rendered only while `waitlist.entries.length > 0`, because take-next needs a room and putting it here would need a room picker for a one-tap action. ⚠ **Its refusals therefore render in the TILE's alert, through `RoomsPanel.describe()`** — which is why that shipped function gains a `QUEUE_EMPTY` branch (`{ text: t("rooms.error.QUEUE_EMPTY"), value: null, outage: false }`) and why the Frontend-changes table's `RoomsPanel.tsx` row is *not* "no other change". Verified at `RoomsPanel.tsx:352-385`: `describe()` maps `ROOM_OCCUPIED`, `STAFF_OCCUPIED`, three 404 targets and then falls through to `{ text: t("staff.loadFailed"), outage: true }`. Without the branch, the queue emptying between the render and the tap — *"an ordinary five-second race"*, D3's own words — renders «שגיאת טעינה» in the muted OUTAGE register to a manager whose queue is simply empty: the exact failure D3 buys the error code to avoid, delivered in the wrong colour on top. **`outage: false`** — an empty queue is not an outage.

`EmptyState title={t("waitlist.empty")}` with **no body and no action** — an empty queue is the ordinary state of a bridal boutique and needs no explanation. One `truncated` line, naming no number.

### D18 — a11y: what axe cannot see here, and the focus moves that each need a named test

IS 5568 / WCAG 2.0 AA is **legally binding** on this product (pre-decided #38). Axe must be zero, and zero axe is not the bar — **this repo has shipped a dropped-focus defect four times (F56, F34, F57, and F36's dialog case) and axe walked past every one, because axe cannot see a focus move that never happened.**

Six moves, each with a named non-vacuous test, following `RoomsPanel`'s numbering:

| Move | When | Where focus goes | Why axe cannot see it |
|---|---|---|---|
| 1 | An action is refused | into the row's `role="alert"` | The alert node does not exist when `setRowError` runs, so the move must be an effect keyed on the error state |
| 2 | An action succeeds | back to the row's current primary control | `@boutique/ui`'s `Button` is `disabled={disabled \|\| loading}`, so a real browser blurred it the instant the request started — **and jsdom does not blur a disabled element, which is what made F57's success-path focus test vacuous.** The test must assert against a control that is present and focusable, and the mutation below is what proves it |
| 3 | A row LEAVES the list while holding focus | the panel `h3` | A remove, a second skip, **or a poll tick** — another manager dispatching from her own device drops the row under this user's hands with no action by her |
| 4 | A reveal is dismissed — **either confirm block OR the assign reveal** | back to its trigger | The trigger is a row control that may itself have gone; `isConnected` then `h3` (F51's shipped shape) |
| 5 | A reveal opens — **either confirm block OR the assign reveal** | onto the question (or the room `Select`) | The two-step's whole a11y value; `ManageBookingPage`'s shipped shape, and the one this repo's `known_flaky` entry names — **fix the wait, never raise the timeout** |
| 6 | A tick CLEARS a focused alert | back to that row's control | ~5s after the refusal, with no user action; the promise «הרשימה תתוקן בעדכון הבא» is kept by the tick and the focus must not fall to `<body>` with it |

**MOVES 3, 4 and 5 are what let the assign affordance be an inline reveal rather than a `<dialog>` (D17).** MOVE 3 is the one that matters: another manager takes Noa by take-next from her own device, the 5s tick drops her row, and the row **with its open reveal inside it** unmounts under this user's hands with focus in it. In a `<dialog>` that is a separate mechanism and a separate effect (`RoomsPanel.tsx:292-307`, MOVE 5 there); in a row-scoped reveal it is the same node removal MOVE 3 already handles. **A11y coverage is a reason to pick the simpler element, not only a cost of picking the harder one** — and the deletion mutation for MOVE 3 must be run with a reveal open, or it tests half of what it claims.

**MUTATION for the whole class:** delete the effect body for each move in turn; each must red exactly one named test and nothing else. **A move whose test stays green when its mechanism is deleted is a vacuous test and must be respecified before the gate.**

Also: the two render-time captures (`RoomsPanel.tsx:167-192`) are copied, because by the time an effect runs the departing row is gone, `document.activeElement` has already dropped to `<body>`, and the question cannot be asked any more. **No `aria-live` on the list itself** — `role="log"` is the tempting wrong answer (it is for append-only chat and this list mutates in place), and a status region rewritten every five seconds announces the whole queue forever (F34's D12). The one announced region is `FloorPanel`'s existing cue, written **only** on a user-initiated outcome.

### D19 — The Playwright `/manage/**` interception harness. The console has no coverage behind its login screen

Recorded as a gap in **F34's spec Risk 8** and never closed. ⚠ **Premise corrected at review:** `frontend/e2e/` is **65** tests (`a11y.spec.ts` 10, `storefront.spec.ts` 55), and **four of them do reach `/manage`** — the shared viewport-meta loop plus three named `manage:` tests, one of which is already a zero-axe A/AA pass. What none of them can reach is anything *behind* the login screen, and the print-sheet test's own comment says so: *"The login screen is the console screen this suite can reach unauthenticated."* Nothing gets past `App.tsx`'s `api.me()` bootstrap without a stubbed identity. **That is the gap: no authenticated console coverage of any kind, on twelve shipped sections.** F58 builds the harness because it is the first console feature whose headline behaviour is a *sequence* — tap, refuse, recover — that a component test cannot stage against a real browser's focus and disabled-button semantics. **It is reusable infrastructure and it is scoped as such**: every later console feature (F37's overlay, F41, F42, F53) inherits it.

**`frontend/e2e/fixtures/manage.ts`**, exporting:

```ts
export const MANAGE = "http://localhost:4174/manage/";
export function staff(overrides?): Staff            // the identity /manage/auth/me answers
export function floorPayload(overrides?): FloorResponse
export async function installManageApi(page, options): Promise<Recorder>
```

**How it authenticates: it does not.** `App.tsx:138-142` bootstraps on `api.me()` and renders `<LoginForm/>` on a rejection. Fulfilling `GET /manage/auth/me` with a 200 `Staff` body is the whole of "signed in" — no cookie, no login POST, no session table. The default identity is **`reception`**, and that is deliberate rather than arbitrary: `NAV`'s `floor` row is `FLOOR_ONLY` (`App.tsx:101-106`), so a reception staffer's only reachable section **is** the floor, `activeKey` lands there with no navigation, and **no other panel ever mounts** — three stubbed GETs and not one stray request. A second identity, `shift_manager`, exercises the two `ELEVATED` controls and reaches the floor through the `board` section, which is why the harness also stubs `/manage/dashboard**` and `/manage/bookings**`.

**⚠ THE TRAP, and the harness exists partly to make it un-steppable-on: `page.route("**/manage/**")` ALSO MATCHES THE APP ITSELF.** `apps/manage` builds with `base: "/manage/"`, so `/manage/index.html`, `/manage/assets/*.js`, `/manage/favicon.svg` all live under that prefix, and one broad glob serves a blank page with no error anywhere. The harness registers **narrow globs per API family** — `**/manage/auth/**`, `**/manage/floor`, `**/manage/floor/**`, `**/manage/dashboard**`, `**/manage/bookings**` — so an asset is never matched at all. The same fourteen-name alternation `vite.config.ts` carries, and for the same reason.

**What it stubs**, `storefront.spec.ts:414-450`'s idiom (a per-path queue of responses plus a recorder, so a test asserts *what the app sent* and not only what it rendered):

| Path | Default |
|---|---|
| `GET /manage/auth/me` | `staff()` |
| `GET /manage/floor` | `floorPayload()` — staff, rooms, **waitlist**, `server_now` |
| `GET /manage/floor/clients`, `GET /manage/floor/dresses` | empty lists, `truncated: false` |
| every POST/PATCH/DELETE under `/manage/floor/**` | the next queued response for that path, defaulting to a house-shape 404 |
| anything else matched | a house-shape 404 `{"error": {"code": "NOT_FOUND", …}}` |

**The last row is the design.** An unstubbed API call must fail **loudly** — as a rendered Hebrew error the test can see — rather than reaching `vite preview`'s proxy to a port with nothing on it, where the failure reads as a flake.

Seven journeys ship with it (test plan below), plus **an axe pass on the floor screen with a populated waitlist** — the console's first axe assertion **behind the login screen, against real content** (the login screen itself has had one since F51).

---

## API surface

| Method | Path | Roles | Body | Answers |
|---|---|---|---|---|
| `GET` | `/manage/floor` | five | — | `FloorResponse` **+ `waitlist`** |
| `POST` | `/manage/floor/rooms/{room_id}/take-next` | five (+ `_authorize`) | `{staff_user_id?}` | `DispatchResult` · 404 · 409 `QUEUE_EMPTY` / `ROOM_OCCUPIED` / `STAFF_OCCUPIED` |
| `POST` | `/manage/floor/rooms/{room_id}/assign` | five (+ `_authorize`) | `{queue_ticket_id, staff_user_id?}` | `DispatchResult` · 404 · 409 `QUEUE_TICKET_NOT_WAITING` / `ROOM_OCCUPIED` / `STAFF_OCCUPIED` |
| `POST` | `/manage/floor/queue/{ticket_id}/call` | five | — | `Waitlist` · 404 · 409 `QUEUE_TICKET_NOT_WAITING` |
| `POST` | `/manage/floor/queue/{ticket_id}/skip` | owner + shift_manager | `{seen_skip_count}` | `Waitlist` · 404 · 409 `QUEUE_TICKET_NOT_WAITING` / `QUEUE_TICKET_CHANGED` |
| `POST` | `/manage/floor/queue/{ticket_id}/remove` | owner + shift_manager | — | `Waitlist` · 404 · 409 |
| `POST` | `/manage/floor/assignments/{assignment_id}/release` | **unchanged** | — | `Room` — **now also closes a linked ticket (D5)** |

Every request body is a `ForbidExtraModel`. Every 401 is the shipped session answer; every 403 is `NOT_AUTHORIZED_BODY`. `test_floor_api.py`'s `FLOOR_ROUTES` table goes from thirteen rows to **eighteen** — twelve admitting five roles, six composing `ELEVATED` — and `test_staff_role_gating.py`'s `FLOOR_OPEN` gains exactly three entries.

---

## Frontend changes

| File | Change |
|---|---|
| `apps/manage/src/api.ts` | **Types**: `WaitlistEntry`, `Waitlist`, `DispatchResult`, `AssignRequest`, `TakeNextRequest`, **`SkipRequest`**; `FloorResponse` gains `waitlist: Waitlist`. **Methods**: `takeNext(roomId, body)`, `assignFromQueue(roomId, body)`, `callQueueTicket(ticketId)`, **`skipQueueTicket(ticketId, { seenSkipCount })`** (D6), `removeQueueTicket(ticketId)`; a `queuePath(ticketId)` helper beside the shipped `roomPath`/`assignmentPath`. `ApiError`, `extractError`, `errorMessage` **unchanged** |
| `apps/manage/src/components/WaitlistPanel.tsx` | **NEW.** The child panel: rows, badges, four row controls, **three inline reveals** (two confirms + the assign room `Select`, D17 — no `<dialog>`), six focus moves, the `describe()` code→sentence map for the row's own verbs (`QUEUE_TICKET_NOT_WAITING`, `QUEUE_TICKET_CHANGED`, 404 + paused twin, `ROOM_OCCUPIED`/`STAFF_OCCUPIED` + both `*Unknown`). No `usePoll`, no timer, no pause control, no announced region |
| `apps/manage/src/components/FloorPanel.tsx` | `waitlist` state beside `rooms`; `applyWaitlist` (an **updater**, `applyRooms`'s shape); `setWaitlist(result.waitlist)` in `load`; `<WaitlistPanel … />` mounted **below** `<RoomsPanel/>` and above the staff `Card`, receiving `mutate`, `onWaitlist`, `onRooms`, `onCue`, `serverNow`, `fetchCount`, `paused`, `selfId`, `role`. `mutate`, `load`, `tick`, the poll and all six shipped focus effects **unchanged** |
| `apps/manage/src/components/RoomsPanel.tsx` | One control added to the free-active-room tile — «קחי את הבאה», rendered only when `waitlistCount > 0` — riding the shipped `act()`; `waitlistCount` and `onDispatch` as two new props; **and ONE new branch in `describe()` for 409 `QUEUE_EMPTY` → `t("rooms.error.QUEUE_EMPTY")`, `outage: false`** (D17 — corrected at review; an earlier draft said "no other change", which would have rendered «שגיאת טעינה» to a manager whose queue is empty). Nothing else |
| `apps/manage/src/i18n/he.ts` · `ar.ts` | The `waitlist.*` deck **plus one `rooms.error.QUEUE_EMPTY`** (D16); `ar` untranslated |
| `apps/manage/src/__tests__/i18n.test.ts` | `HE_F58` constant + its floor, folded into `HE`; **`HE_F36`'s floor goes from `>= 70` to `>= 71`** (`:424`) for the one `rooms.` key |
| `apps/storefront/src/routes/QueuePositionPage.tsx` | **D14** — the three-line state-precedence fix. No new string |
| `frontend/e2e/fixtures/manage.ts` · `frontend/e2e/manage.spec.ts` | **NEW.** D19 |

### Every state each surface can be in

| # | State | What renders |
|---|---|---|
| W-load | `waitlist === null` (first tick in flight) | Nothing — `FloorPanel`'s existing skeleton covers the whole panel, exactly as `RoomsPanel` returns `null` (`RoomsPanel.tsx:590-592`). No second skeleton and no second pause control over a fetch nothing has seen produce anything |
| **W-empty** | `entries.length === 0` — **the common case** | «אין ממתינות בתור», no body, no action. A bridal boutique's queue is empty most of the day and the panel must read as *quiet*, never as *broken* |
| W-list | 1–100 entries | Rows in server order |
| **W-40** | Forty waiting | The list scrolls with the page; no virtualisation, no pagination, no collapse. «קחי את הבאה» is one tap regardless of length, which is the control that matters at forty. Position numbers are what keep a scrolled list legible |
| W-truncated | `truncated: true` (>100 — a griefing flood inside F33's 200/hour ceiling) | One line, «הרשימה ארוכה מהמוצג.», naming no number and no limit |
| **W-noroom** | Entries exist, every room occupied or inactive | No «קחי את הבאה» on any tile (there is no free tile), the row's «שבצי לחדר» is not rendered, and one muted line says «אין חדר פנוי כרגע.» Never a disabled button — a control that refuses is a 403's cousin on a screen where 403 is terminal |
| **W-vanished** | She was dispatched, skipped or removed from another device between the render and the tap | 404 → «הכניסה הזו כבר לא קיימת. הרשימה תתוקן בעדכון הבא.» in the row's alert, focus into it (MOVE 1), cleared by the next tick (MOVE 6). While `paused`, the `…Paused` twin instead — a stopped panel has no next update to promise (F36's DC-8) |
| **W-duplicate** | Two rows, same name, both `duplicate: true` | Both carry the «כניסה כפולה» badge. Neither is auto-merged, auto-hidden or reordered. Removing one is two taps and names her in the confirm |
| W-called | `called: true` | «נקראה» badge; «קראי» stays (a re-call is a 200 no-op — she did not come the first time) |
| W-lastskip | `skip_count >= 1` | «דילגו עליה פעם אחת» line, and «דלגי» opens the confirm instead of acting |
| **W-stalecount** | A colleague skipped her between this render and this tap (D6) | 409 `QUEUE_TICKET_CHANGED` → «מצב הכניסה השתנה. רענני ונסי שוב.» in the row's alert, focus into it (MOVE 1), cleared by the next tick (MOVE 6) — which is also the tick that raises her `skip_count` to 1, so the next press correctly opens the confirm. **She is NOT removed**, which is the whole point of the conjunct |
| **W-emptyqueue** | Take-next tapped on a tile after the last entry left | 409 `QUEUE_EMPTY` → «אין ממתינות בתור.» in the **tile's** alert (`rooms.error.QUEUE_EMPTY`), non-outage register, focus into it. The waitlist below is already empty and says so |
| W-refused | Any 409 | The mapped Hebrew sentence in the row's alert. `ROOM_OCCUPIED` / `STAFF_OCCUPIED` reuse F36's four strings including both `*Unknown` variants |
| W-outage | 5xx or a dropped request | `staff.loadFailed`, the OUTAGE register (`--color-ink-muted`), **never `--color-danger`** — nothing that can go wrong here is her fault (F36's rule) |
| W-terminal | 401 / 403 from a tick **or a mutation** | `FloorPanel`'s existing terminal takes the whole screen. The panel adds no second terminal — `mutate()` already routes it |
| W-paused | `mode !== "running"` | Rows keep rendering, elapsed times **frozen** with the stamp (`elapsedMinutes` is anchored to `server_now`), every control still live: pausing is a repaint control, not a read-only mode |

---

## Acceptance criteria

| # | Criterion | Test |
|---|---|---|
| A1 | The migration adds `queue_ticket_id UUID NULL` and nothing else — no CHECK, no unique index, no FK | `test_migrations.py` (column shape + the three F36 counts/pins stay green with no edit) |
| A2 | `GET /manage/floor` carries `waitlist.entries` in `COALESCE(requeued_at, created_at), id` order, with `position == index + 1` — **each seed ticket inserted in its OWN `tenant_session`** (D2: `now()` is transaction-start, so batched seeds share a sort key and "arrival order" asserts nothing) | `test_floor_db.py` |
| A3 | The waitlist read's predicate set is the **same function call** as `position()`'s (`_live_waiting`) and the same `_sort_key()`, so for any two entries with **distinct** sort keys `position()` ranks them the way the list does, and every entry's `position()` is in `{index, index + 1}` | `test_queue_dispatch_db.py::test_the_waitlist_order_agrees_with_the_position_count` |
| **A3b** | A deliberate TIE (two tickets seeded in one transaction) renders two distinct list positions and one shared `position()` count — the documented disagreement, pinned as a fact rather than left in prose | `db` |
| A4 | No phone, no `marketing_opt_in_at` and no `queue_day` reaches the payload | `test_floor_api.py` (recursive key/value scan) |
| A5 | Take-next claims the ticket `position()` calls 1 and inserts the assignment in one transaction | `test_queue_dispatch_db.py` |
| A6 | **Two concurrent take-nexts get two DIFFERENT tickets** | forced interleave, `db` |
| A7 | **Take-next on an empty queue answers 409 `QUEUE_EMPTY` and writes nothing** | `db` |
| A8 | **⚠ A take-next that loses the ROOM race leaves the ticket `waiting` at position 1, with no assignment and no audit row** | F36's shipped snapshot-then-nested-commit shape, `db` — **the feature's headline test** |
| **A8b** | **A take-next into a room the CALLER already holds answers 409 `ROOM_OCCUPIED` naming her — never 200 — and the head of the queue is untouched** | `db` — the assertion that structurally forbids an idempotence branch |
| **A8c** | An unrecognised unique violation **re-raises** (500) rather than becoming a 409 | fast (`test_floor_service.py`, injected `IntegrityError`) |
| A9 | Push-assign on a non-waiting ticket answers 409; on a missing one, 404 | fast + `db` |
| A10 | Two concurrent push-assigns of one ticket produce exactly one assignment | forced interleave, `db` |
| A11 | Release closes a linked ticket to `done` **in the same transaction**; with `queue_ticket_id IS NULL` its behaviour is byte-identical to F36's | `db` + the shipped release suites green with no edit |
| A12 | A second release does not re-close and writes no audit row | `db` |
| A13 | Skip stamps `requeued_at`, increments `skip_count`, **clears `called_at`**, and leaves her `waiting` | `db` |
| A14 | The **second** skip writes `removed` | `db` |
| A15 | **A concurrent SECOND first-skip is REFUSED (409 `QUEUE_TICKET_CHANGED`), not escalated: `skip_count == 1`, `status == 'waiting'`, exactly one audit row** — she is not removed by two single taps with the confirm never shown | forced interleave, `db` |
| **A15b** | Two DELIBERATE skips (each sending the `seen_skip_count` it rendered) leave `skip_count == 2` — the atomic increment never loses one | forced interleave, `db` |
| A16 | Call stamps `called_at` and **leaves `status = 'waiting'`** | `db` — the F59 contract |
| A17 | A second call on an **already-called `waiting`** ticket answers **200**, keeps the first timestamp and writes **no audit row** — the third branch D7's table adds | `db` |
| A18 | Remove writes `removed`; the ticket leaves the waitlist and her page reaches its terminal | `db` + vitest |
| A19 | `duplicate` is true for two same-phone **waiting** tickets, **true when the same-phone twin is `in_service`**, and false for two same-name-different-phone ones | `db` |
| A20 | A dispatched walk-in's name renders as the room tile's `client_label`; a soft-deleted ticket renders an anonymous visit | `db` |
| A21 | Skip and remove **403** for reception / sales_assistant / seamstress; take-next, assign and call **200** | `test_floor_api.py` + `test_staff_role_gating.py` |
| A22 | `test_the_floor_roles_reach_exactly_the_floor_routes` passes with `FLOOR_OPEN` gaining exactly three rows | `test_staff_role_gating.py` |
| A23 | `test_the_manage_dev_proxy_names_every_manage_api_segment` passes with **no `vite.config.ts` edit** | `test_spa_serving.py` |
| A24 | Each of the six focus moves lands where D18 says | vitest, one named test each |
| A25 | The empty state renders «אין ממתינות בתור» with no action | vitest |
| A26 | A tick that drops the focused row moves focus to the panel heading | vitest |
| A27 | Skip's confirm appears only when `skip_count >= 1`; remove's always; both name her | vitest |
| A28 | An `in_service` ticket that was called renders «התור שלך התחיל», not «אפשר לגשת לדלפק» | vitest (storefront) |
| A29 | **The rendered waitlist contains no element whose `href` (or `to`) includes an entry's `id`** — a DOM query over a populated fixture, not a grep, because a grep passes when the link is built by string concatenation | vitest |
| A30 | Zero axe A/AA violations on the floor screen **with a populated waitlist** — the console's first axe assertion **behind the login screen** | e2e |
| A31 | The e2e harness intercepts no asset — the app boots and the floor renders | e2e |
| **A31b** | Take-next answering 409 `QUEUE_EMPTY` renders «אין ממתינות בתור.» **in the tile alert, in the non-outage register**, with focus moved into it | vitest (`RoomsPanel.test.tsx`) + e2e |
| A32 | **`alembic heads` returns exactly ONE head after the rebase that precedes the push** (Risk 7 — the only gate line this feature can uniquely fail). The rest of the CI list is every PR's and asserts nothing about F58 | F19's shipped single-head guard |

---

## Testing

### Fast suite (no marker, no Docker)

- **`test_floor_api.py`** — the eighteen-row `FLOOR_ROUTES` walk against a duck-typed `FakeFloorService`: 401 without a session, 200 for all five roles on the twelve open rows, 403 for the three floor roles on the six `ELEVATED` rows, the host-derived tenant, the CSRF fence on all five new POSTs, and the wire shape by **set equality over `WaitlistEntry`'s keys** — the assertion that catches an eighth key arriving unreviewed on a five-role payload, which is how F36 pinned `StaffCard`.
- **A4's recursive scan**: no value in the payload matches `^\+972\d{9}$` and no key is `phone`, `marketing_opt_in_at` or `queue_day`.
- **`test_floor_service.py`** — the authorization matrix, each case asserting **the repository was never called** (the only way to state that the 403 precedes the read); the two-answer refusal branches; the release's `queue_ticket_id IS NULL` short-circuit.
- **`test_staff_role_gating.py`** — `FLOOR_OPEN` + 3 rows, and the two tightened rows deliberately absent.
- **`test_spa_serving.py`**, **`test_migrations.py`**'s non-db assertions, **`test_frontend_imports_are_tracked.py`** (F33's permanent guard — any new frontend module must be `git add`ed).

### `db`-marked (real Postgres)

`test_queue_dispatch_db.py` — new, `test_floor_rooms_db.py`'s harness and its hard rules verbatim: **every committed staff row is `owner` or `shift_manager`, never a floor role** (the cluster is session-scoped, pytest collects alphabetically, and `test_migrations.py::test_adding_the_role_check_validates_existing_rows` re-adds 0011's two-value CHECK over whatever rows exist); every test mints its own tenant id; nothing truncates.

**⚠ ONE MORE HARD RULE, F58's own: every waiting ticket in an ordering test is inserted in its OWN `tenant_session`.** `created_at` is `DEFAULT now()` and Postgres's `now()` is **transaction-start**, so tickets batched into one transaction share a sort key to the microsecond — the list then falls back to the `, id` tiebreak (random UUID order) and `position()` answers **1 for all of them**. A builder batching the seeds for speed gets a red on A3 whose most tempting fix is to weaken A3, which makes it vacuous. Stated here, beside the other three, because it has exactly the same shape as them: an invisible property of the shared fixture that breaks an unrelated-looking assertion.

Plus the migration assertions in `test_migrations.py`, the payload assertions in `test_floor_db.py`, and the ordering-agreement test.

#### The forced interleaves, and the exact mutation each must survive

Never a bare `asyncio.gather` for a deterministic branch — it does not **order** two transactions, so the loser usually runs after the winner has already committed and the branch goes green with the mechanism never exercised. **The default shape is F36's shipped one** (`test_floor_rooms_db.py:218-274`): open a read-only snapshot `tenant_session` and assert the contested resource reads FREE — which is what makes the gap *observable* rather than assumed — commit the winner in a **nested** `tenant_session`, then call the service. No tasks, no Event, no hang, and it is what A8 uses. `asyncio.Event` + `HOLD_SECONDS`/`ISSUE_SECONDS` tasks **only** where a statement must genuinely **block** on another transaction's uncommitted work: the SKIP-LOCKED timing test and the two concurrent-skip tests, and nothing else in this feature.

⚠ **Three of this table's ten mutations were wrong in the first draft and are corrected below with the reason recorded rather than silently swapped.** Two would have come back green (the savepoint one and the audit-row one) and one was fixture-dependent. That is the point of running them.

| Test | Mechanism | **MUTATION that must turn it red** |
|---|---|---|
| `test_two_take_nexts_get_two_different_customers` | The subquery's **row lock + `status` qual** — NOT `SKIP LOCKED`, see the correction below | Drop `AND status = 'waiting'` from the SUBQUERY → the loser's EvalPlanQual re-check passes on the updated tuple and both end on one ticket |
| **`test_a_take_next_does_not_wait_behind_a_locked_ticket`** (new, replaces the vacuous `SKIP LOCKED` claim) | `skip_locked=True` | Seed **exactly one** waiting ticket. A takes it and holds its transaction open (`asyncio.Event` + `HOLD_SECONDS`); B's take-next must raise `QueueEmptyError` **promptly** — assert the exception AND an elapsed bound well under `HOLD_SECONDS`. Remove `skip_locked=True` → B blocks for the full hold and then still raises `QueueEmptyError`, so **only the timing assertion reds**, which is exactly why it cannot be dropped |
| **`test_a_take_next_that_loses_the_room_leaves_the_ticket_waiting`** (A8) | **Every refusal RAISES out of `tenant_session`; nothing `return`s after the ticket UPDATE** | **Give the `except` branch F36's idempotence RETURN** (`active_for` hit → `return await self._room_read(...)`) **inside the `async with`**, with the conflicting assignment held by the SAME staffer as A's target → 200, commit, ticket stranded `in_service` with no assignment: all four assertions red. ⚠ **The first draft's mutation (savepoint + `try` inside) comes back GREEN** — `db/tenant.py:25` rolls back on a propagating exception with or without a savepoint — and is recorded here as a mutation that was *predicted to bite and does not*, per F36's rule |
| `test_a_take_next_that_loses_the_room_writes_no_audit_row` (A8) | The audit call is inside the transaction | ⚠ The first draft's mutation («move `_audit.record` outside the `async with`») is **unreachable** on the losing path — the exception is raised at the INSERT, so nothing after the block runs and zero rows are written either way. Replaced: **move the ticket claim and `_audit.record` into their own `tenant_session` that commits before the INSERT is attempted** → an audit row survives the failure and the count assertion reds |
| `test_two_distinct_staffers_push_assigning_one_ticket_to_two_distinct_rooms_produce_one_assignment` | `AND status = 'waiting'` in the conditional UPDATE | Drop that conjunct → both succeed and two assignments carry one ticket. ⚠ **Both "distinct"s in the name are load-bearing**: same room and the room index blocks the second, same staffer and the staff index does — either way the mutation goes green and F36's shipped indexes pass the test for the wrong reason |
| **`test_a_concurrent_second_first_skip_is_refused_rather_than_removing_her`** (A15) | `AND skip_count = :seen_skip_count` | Drop that conjunct → B's EvalPlanQual re-check passes on A's updated row, the `CASE` reads `skip_count = 1`, and **she is removed with neither client ever showing the confirm**: the status, count and audit assertions red |
| `test_two_deliberate_skips_leave_skip_count_at_two` (A15b) | `skip_count = skip_count + 1` in SQL | Replace with a Python read-modify-write (`skip_count=row.skip_count + 1`) → the lost update lands and the count is 1 |
| `test_the_second_skip_removes_her` | The `CASE` reading the pre-update value | Change `skip_count + 1 >= 2` to `skip_count >= 2` → she is never removed |
| `test_a_second_call_keeps_the_first_timestamp` | `called_at IS NULL` in the predicate | Drop it → the timestamp moves and an audit row is written |
| `test_a_release_and_its_ticket_close_are_one_transaction` | Both statements inside one `tenant_session` | Open a second `tenant_session` for the close → an injected failure between them leaves a free room and an `in_service` ticket |
| `test_the_waitlist_order_agrees_with_the_position_count` (A3) | `_live_waiting()` / `_sort_key()` **called**, not copied | Inline the four predicates and drop `queue_day` (or `deleted_at IS NULL`) → the two disagree. Seeds are one-per-`tenant_session`; A3b pins the tie case separately |
| `test_the_duplicate_flag_is_keyed_on_the_phone` | Grouping key | Group on `name` → the same-name-different-phone case reds |
| **`test_the_duplicate_flag_sees_an_in_service_twin`** (A19) | D2's fifth statement | Delete the in-service phone projection → the waiting ticket whose twin is already in a room renders un-flagged, and the test reds |

**Every mutation above is RUN, and a green result is RECORDED IN THE CODE rather than left as false confidence** — F36 ran nine and two came back green, and said so beside the mechanism. A test whose named mechanism can be deleted with the suite still green is **vacuous** and must be respecified before the gate. Every feature in this program has found real vacuous tests this way.

### Frontend (vitest)

`WaitlistPanel.test.tsx` — all sixteen states, the six focus moves (each with its own deletion mutation, and **MOVE 3's run with a reveal open**), the three inline reveals, the code→sentence map including both `*Unknown` branches and `QUEUE_TICKET_CHANGED`, A29's no-anchor-carries-an-id DOM query over a populated fixture, the updater-not-value patch under two overlapping mutations, and the 44px class assertion on every control (`min-h-11`; jsdom has no layout engine, so a measurement would be vacuous — `BoardSection.test.tsx:507-512` writes the trap out).

**`RoomsPanel.test.tsx`** — ⚠ **not `WaitlistPanel.test.tsx`, because take-next's control lives on the tile**: the «קחי את הבאה» control's presence rule (`waitlistCount > 0`, free + active tile only), the new `QUEUE_EMPTY` branch rendering «אין ממתינות בתור.» in the **non-outage** register, and MOVE 1 moving focus into the tile alert. The rest of the file must stay green **with no edit**.

`FloorPanel.test.tsx` gains the waitlist plumbing and one test that a floor tick **still** repaints only the floor. `QueuePositionPage.test.tsx` gains D14's four-arm precedence, seeded through the stubbed API client (F33's D10 precedent — nothing in the product can drive it, and no backend or e2e assertion may try).

### E2E (the D19 harness)

Seven journeys plus one axe pass: (1) reception signs in and the floor renders with a populated waitlist; (2) «קחי את הבאה» on a free tile dispatches the first entry — the tile fills, the row leaves, and the cue names **the room** (never the customer, D16); (3) take-next answering 409 `ROOM_OCCUPIED` shows the Hebrew sentence in the **tile's** alert, **moves focus into it**, and leaves the row in place; (4) take-next answering 409 `QUEUE_EMPTY` shows «אין ממתינות בתור.» in the same alert, in the non-outage register; (5) a shift manager removes a duplicate through the two-step confirm; (6) a skip on `skip_count === 1` confirms first; (7) an unstubbed request surfaces as a rendered Hebrew error rather than a hang. **Zero axe A/AA on the floor screen with content** — the console's first behind the login screen.

---

## Out of scope

- **Wait-time estimates and any queue analytics** — pre-decided #28. `created_at → called_at` becomes computable the day this merges and nothing computes it. The first person to notice will propose a chart; the ruling stands until an epic reopens it.
- **Bride-priority ordering** — `e6-instore-realtime.md:74`. FIFO by arrival; `visit_type` is rendered and nothing sorts on it.
- **Restoring a removed ticket** — D8. Recorded as the upgrade path; the confirm is the guard.
- **A true merge that preserves both capabilities** — D8. It cannot be had without either moving a survivor's sort key backwards (which falsifies `requeued_at`'s published meaning) or terminating a live device's page at a woman still in the queue.
- **Closing yesterday's unclosed tickets** — **F20's retention sweep**. The panel is scoped to today's `queue_day` (D2), so a ghost from an earlier day is invisible and unremovable here. Risk 5.
- **SMS of any kind** — no «you're next» text. F58 sends nothing, needs no `scheduled_messages` row and no sender ID.
- **Any change to `position()`, to the public `/storefront/checkin` routes, to F33's three limiters or to the QR sheet.**
- **Reconciling a queue ticket with a booking for the same woman** — F33's out-of-scope list hands this to F58 as an *open* question and the answer is: not in v1. Both surfaces render her honestly (a room tile from her booking, a row from her ticket) and the manager reconciles them by removing one. A pilot day is what decides whether that is worth automating.
- **A shared `usePoll` in `packages/ui`** — F33's D9. Two apps behind two API clients is still not the second caller that makes an extraction reviewable.
- **A feature flag or a `queue_enabled` setting** — declined by F33 and unchanged: the loop's own ordering is the control, and this is the merge that clears the gate.

---

## Codebase and program-state conflicts recorded

1. **`LOOP-STATE` says F58 needs "no new table"; `qr-walkin-queue.md:20` says it needs "no migration of its own".** The first is true; the second is **false**, and F36's own DDL is the evidence — `0019_fitting_rooms.py` states that F58 adds `queue_ticket_id` "in its own migration alongside its writer", and F36's spec D2 calls that its largest scope call. **Codebase-consistent reading taken** (D1): one `ALTER TABLE`, one column. F59's spec already spotted the discrepancy and said so (`public-queue-board.md:163`: *"`LOOP-STATE.md:481-482` says the narrower 'No new table', which is not the same promise"*).
2. **`LOOP-STATE` describes FINISH as its own verb; the shipped `release` route makes a second verb a stranding hazard.** A separate finish route would leave F36's shipped room-tile release able to free a room and leave the ticket `in_service` forever — the exact defect this feature exists to remove. **Codebase-consistent reading taken** (D5): `release` is extended and the shipped tests stay green with no edit. ⚠ **The shipped release LABEL is unchanged** — an earlier draft of this line said "the label is state-dependent", which no design section, no i18n key and no frontend-changes row delivered. Declined deliberately: a state-dependent label is a second thing that can disagree with the tile it sits on, for a wording gain, and the brief's «סיימתי עם הלקוחה» is what the shipped control already means.
3. **The brief's mental model puts take-next on the waitlist; the concurrency design puts it on a room tile.** Take-next needs a room, and a server-chosen "first free room" would derive a value from a count of existing rows — F13's read-then-write shape, which needs a lock and which F36's D3 argues at length is not this feature's shape. A tile-mounted control inserts three values the caller already holds. **Narrowed deliberately** (D3), and the one-tap ergonomic is preserved.
4. **Mounting the queue verbs at `/manage/queue/…` would have cost a `vite.config.ts` edit.** `test_spa_serving.py:377` asserts set equality between the live route table's second path segments and the dev proxy's alternation, and F57's shipped note records that this exact collision breaks **only a developer's machine** while production, CI and the whole suite stay green. Every F58 path is `/manage/floor/…`. F36 made the identical call for `/manage/floor/rooms`.
5. **`QueueTicketsRepository`'s class docstring promises "no read keyed on `phone`" and calls the absence "the security property".** D9's duplicate grouping is keyed on `phone`. **The docstring is corrected in this PR**, F36's three-comments precedent verbatim; the property that was actually load-bearing — no *anonymous* surface keys on the phone, and no response body carries it — survives intact and is restated.
6. **Three shipped comments state that the floor payload carries "at most one name per occupied room".** F58 puts up to a hundred names on it. **All three are rewritten in this PR** (D10) rather than left standing as the rationale for the widest role gate in the codebase. This is the second time that sentence has been falsified and the third time it is being written.
7. **`models/fitting_room_assignment.py` states "No personal field of any kind. `booking_id` and nothing else".** D1 adds a second pointer; the sentence is corrected, and the stronger rule it was protecting — neither pointer is a snapshot, both resolve on read — is stated explicitly.
8. **A three-role gate is not expressible in this codebase**, so reception cannot skip or remove. Discovered against `test_staff_role_gating.py:313-329` rather than assumed. Recorded as a product limitation with an upgrade path (D11) rather than "fixed" by relaxing the assertion — which the test's own docstring names as the outcome its Risk 1 exists to prevent.
9. **F59 recorded the contract that `call` leaves `status = 'waiting'` because it cannot enforce it** (`public-queue-board.md` Risk 6). **F59 has since MERGED (PR #38)**, so the contract is now against shipped code rather than a parallel build. D7 keeps it, and A16 is the test that makes it a fact.
10. **⚠ FOUR FACTS THIS SPEC ASSERTED HAD GONE STALE BY REVIEW TIME, and all four are corrected in place rather than footnoted.** (a) `queue_tickets.py` has four methods, not three — F59 shipped `board` plus the module-level `_live_waiting()` / `_sort_key()`, whose docstring names *"F58 widening one status filter"* as the hazard it exists to prevent, so D2 now **calls** them. (b) `_occupancy_rows` has **four** LEFT joins, not five (`fitting_rooms.py:281/290/297/306`), and begins at `:254`. (c) `frontend/e2e/` is **65** tests and **four of them reach `/manage`**, one already an axe A/AA pass — the gap is authenticated coverage, not coverage. (d) `elapsedLine` hard-codes `rooms.*`, so the waitlist calls `elapsedMinutes` and renders its own two keys. None of these changed a decision; (a) and (d) changed the code a builder would have written.
11. **`RoomsPanel.describe()` has no `QUEUE_EMPTY` branch and take-next's control lives on its tile.** Discovered at review against `RoomsPanel.tsx:352-385`. The Frontend-changes row that said "no other change" is corrected, the string is keyed `rooms.error.QUEUE_EMPTY` beside the four F36 sentences it renders alongside, and `HE_F36`'s floor moves by one.
12. **`RoomsPanel.tsx:464-469` says the cue never names the client BECAUSE THE REGION IS PERSISTENT — not "except on an act the manager performed".** An earlier draft of D16 paraphrased it the second way and specified four cues interpolating a customer's name into `FloorPanel`'s persistent `role="status"`. Corrected: the cues name the act. Recorded as a conflict because the misreading, not the rule, is what a later feature would have copied.

---

## Risks and open items

1. **SKIP LOCKED can serve two customers out of order — NARROWED at review, and the common case is now designed out.** D3's step 2b (the room lock, then `occupant_of_room`) refuses the serialised same-room collision — two managers tapping one free tile inside a tick, which is the likeliest collision in the feature — **before any ticket is touched**, so nothing is claimed and nothing is skipped past. What remains is genuinely irreducible: a winner that has not yet committed when 2b reads, plus the wider case that the subquery skips **any** row-locked ticket, including one a colleague is calling (D7) or skipping (D6). The window is one statement, and the alternative is two staffers walking two brides to one curtain. Accepted, stated in D3, and visible on the panel — the skipped-past row is still at position 1 and is the obvious next tap. *Owner: team. Trigger: a pilot manager reporting an out-of-order call.*
2. **A removed duplicate terminates a live device's position page.** Whichever of a woman's two tickets is removed, if it is the one her current tab polls, `QueuePositionPage` renders «הביקור הזה הסתיים.» and stops — while she is still in the queue on the other ticket. There is no design that avoids this without either an oracle or an SMS, both of which F33 ruled out. The mitigations are that she is three metres from the counter, that the confirm names her, and that the survivor keeps her true arrival position. *Owner: team. Trigger: the first pilot day with a duplicate, which F33's Risk 11 predicts.*
3. **Remove has no undo and one mis-tap silently costs a real customer her place.** The guards are the two-step confirm, the entry's name in the question, the duplicate badge that stops the manager inferring from a shared first name, and an audit row naming who did it. Restore is one repository method behind the decision (D8). *Owner: team. Trigger: the first mis-tap, or a pilot asking for it.*
4. **The floor payload's name count went from ≤3 to ≤100, it now also carries ≤100 position-page CAPABILITIES, and the role gate did not move.** D10 rewrites the justification honestly — including the capability, which the first draft's rewrite denied in the same sentence that introduced it — and the limit that remains is real: physically present, right now, no contact route, gone when she is. But it is a **legally sensitive widening on the one router in the product admitting five roles**, and it deserves the reviewer's time more than any other line in this spec. F20 inherits it for the processing-activities entry, and must record the capability disclosure as well as the names. *Owner: F20. Trigger: F20's spec, which stops for the user anyway.*
5. **Yesterday's unclosed tickets remain unclosed and unreachable.** The panel is today-scoped, so a ghost from an earlier day cannot be removed from any surface, and her page still reports her own day's position. F33 accepted this and F59 records the same asymmetry; F20's sweep is the remedy. *Owner: F20.*
6. **The e2e harness stubs the API, so it proves the console and not the contract.** A backend change that renames a payload key passes every e2e test while breaking production; only `test_floor_api.py`'s set-equality assertions and the TypeScript types catch that. The harness is a **journey and a11y** instrument, and saying so is what keeps it from being trusted for something it cannot do. *Owner: team. Trigger: the first payload rename.*
7. **The migration number will move.** `main`'s head is `0019_fitting_rooms` **at review time** (verified: `migrations/versions/` ends at 0019, and F59 merged without one), and **F41 is building right now WITH a migration**. The rule, not the number: **build at `alembic heads` + 1** with `down_revision` = the head on the branch so the branch is self-coherent and its `db` tests actually run; **renumber at the rebase that precedes the push**, re-resolving from `alembic heads` on `main` **immediately** before it; **make the migration the LAST commit** so the renumber is one `git commit --amend` touching one file; **do not OPEN the PR while a lower-numbered migration is unmerged.** F33's own history records this failing for real: two files claiming `0016`, filenames different, merge textually clean, nothing in review looking wrong, and `test_exactly_one_migration_head` naming both heads in half a second. *Owner: the loop.*
8. **A green a11y test is not an a11y test.** Every focus move here needs its deletion mutation run, because jsdom does not blur a disabled element and that alone made one of F57's shipped focus tests vacuous. `known_flaky` also names a jsdom focus race in `ManageBookingPage.test.tsx` — **fix the wait, never raise the timeout**, and do not copy the flaky shape into the confirm-block tests. *Owner: team, at the dual review.*
9. **`ar.ts` has no parity guard on the storefront and a partial one on manage.** The `waitlist.*` keys go into both files by hand; a missing `ar` key ships green. F15's Risk 5, inherited. *Owner: team. Trigger: F45.*
10. **This PR touches a shipped storefront component (D14) and a shipped backend route (D5).** Both are additive and both are gated on shipped suites staying green with **no edit** — that is the acceptance condition, not a hope. Any red in `test_floor_rooms_db.py`, `test_floor_service.py` or `QueuePositionPage.test.tsx` is a design failure in this feature, not a test to update. *Owner: the builder.*

---

## Decisions Log

1. **The migration is one `ALTER TABLE ADD COLUMN` and no index of any kind.** "No new table" is kept; "no migration" was never promised by anything but a stale line, and F36's DDL hands the column over explicitly. No unique index, because two shipped guards (`test_fitting_room_assignments_carries_exactly_two_non_primary_unique_indexes`, `test_the_fitting_room_tables_carry_no_check_constraints`) exist to make a third a reviewed act, and the review's answer is that the conditional UPDATE on the ticket row is already the serialisation point.
2. **Take-next takes no savepoint AND no idempotence branch, and the SECOND of those is the guarantee.** ⚠ Restated at review. `tenant_session` rolls back on any exception propagating out of it (`db/tenant.py:25`), so a *raised* 409 was never the hazard; the hazard is a **`return` from inside the block**, which is what F36's `_resolve_claim_conflict` does on its idempotence hit and which would commit a ticket claimed for a dispatch that did not happen. The rule is therefore: **every refusal raises out of `tenant_session`, and nothing returns after the ticket UPDATE.** The savepoint is dropped because nothing needs the transaction alive afterwards — the 409's occupant read moves into a second short transaction, paid only on a refusal.
3. **Take-next's control lives on the room tile.** A server-chosen free room would be a read-then-write needing a lock; a tile-mounted control inserts three values the caller already holds.
4. **FINISH is the shipped `release`, extended.** A second verb would leave the shipped room-tile release able to strand a ticket in `in_service` forever — the defect this feature exists to remove, re-introduced by the feature that removes it.
5. **The duplicate remedy is REMOVE, not merge.** A merge must choose which capability survives and whose arrival time wins; both answers are worse than one honest removal plus a badge that stops the manager guessing.
6. **The duplicate flag is a boolean keyed on `phone`, derived on read.** A group index would render groups of one when a woman's twin is already in service. `phone` is the only key that does not collide; `name` collides legitimately, and this is the panel where a collision decides who gets removed. The phone never reaches the wire, and the repository docstring that promised no phone-keyed read is corrected rather than quietly falsified.
7. **Skip clears `called_at`.** Not named by any ruling. She was called and did not come, which is why she is being skipped; leaving the stamp would highlight her at the back of F59's public board and leave her own page reading «אפשר לגשת לדלפק» indefinitely.
8. **Take-next and push-assign do NOT stamp `called_at`.** Being summoned and being taken are two facts, and stamping both would make the shipped string «התור שלך התחיל» unreachable on every path in the product.
9. **Skip and remove are `ELEVATED`; take-next, assign and call are all five.** Forced by `test_staff_role_gating.py`'s intersection classifier, which structurally forbids a gate admitting reception but not seamstress and whose docstring forbids relaxing it. The product cost — reception cannot skip a no-show — is recorded rather than engineered around.
10. **Every statement in this feature is a column projection — including the REFUSAL read — so no `QueueTicket` instance is constructed anywhere.** ⚠ The absolute was about to be false: D4's "one read of the row" had exactly one shipped implementation, `by_id`, which returns an entity carrying `phone` and `marketing_opt_in_at` into the same session as an ORM-enabled UPDATE. A new `status_of()` projection returning `(status, skip_count)` is what the two-answer table (and D6's optimistic branch) actually needs. **And every ORM-enabled UPDATE carries `.execution_options(synchronize_session=False)`**, stated once for all six rather than on take-next alone.
11. **The mutation responses carry the whole waitlist, not one entry.** Skip reorders the list and remove shortens it; a per-entry patch cannot express either.
12. **No `waiting_total` on the wire — `truncated` alone.** F36's picker rule: the copy names no count and no limit, both are the server's to change without a copy edit, and a total would cost a second statement on the tick for a line that renders at a hundred entries and never otherwise.
13. **The queue verbs mount under `/manage/floor/queue/…`.** `/manage/queue` reads better and costs a `vite.config.ts` edit whose omission breaks only a developer's machine while everything green stays green.
14. **The e2e harness authenticates by stubbing `GET /manage/auth/me` and defaults to a `reception` identity.** No cookie, no login POST, and — because `NAV`'s floor row is `FLOOR_ONLY` — the floor is the landing section, so exactly three stubbed GETs render the whole screen and no other panel ever mounts. Narrow per-family globs, never `**/manage/**`, because the app's own shell and assets live under that prefix.
15. **`QueuePositionPage`'s state precedence is corrected here.** F58 makes `called_at` + `in_service` reachable for the first time, so F58 owns the three lines. Clearing `called_at` on dispatch was the alternative and was declined: it would erase a record F59 reads to solve a rendering problem that belongs to the renderer.
16. **One `QUEUE_TICKET_DISPATCHED` action with the mode in `details`, and no second `FITTING_ROOM_CLAIMED` row.** `CUSTOMER_UPDATED`'s split criterion: nobody will ever ask this table "who used the take-next button but not the assign one", and the claim row's whole content is a subset of the dispatch row's.

**Added at spec review (round 1):**

17. **Skip is OPTIMISTIC on the count the client rendered** (`AND skip_count = :seen_skip_count`, 409 `QUEUE_TICKET_CHANGED`). Without it, two managers each tapping «דלגי» **once** on a woman at `skip_count == 0` remove her — B's predicate re-check passes on A's committed row and B's `CASE` reads 1 — with the confirm never shown on either device, because both clients rendered 0. One conjunct, one request field, one code, and it is the confirm made enforceable rather than advisory.
18. **The dispatch verbs have NO idempotence branch and DO re-raise an unrecognised constraint.** `_occupied_error` is specified in full in D3a rather than described as "one helper", because the shipped analogue's first branch is a `return` that would strand a customer and its last branch is a re-raise the first draft's signature could not express.
19. **The wait clock is anchored to `created_at`, and the field is named `arrived_at`.** Anchoring it to the sort key made one skip reset the rendered wait to zero, so «הגיעה זה עתה» would render for a woman who arrived an hour earlier. The ordering key is deliberately **not** serialised — it would time how long ago a named woman was skipped, which is the argument D2 already makes for `called` being a boolean.
20. **No cue in this feature names a customer.** `FloorPanel`'s `role="status"` region is persistent and nothing clears it, which is the shipped reason `rooms.claimedCue` names the room. A removed woman's name would otherwise be the only trace of her left on a five-role screen after she has gone — falsifying D10's own promise on the surface Risk 4 calls the most sensitive in the spec.
21. **The assign affordance is an inline reveal, not a `<dialog>`.** A dialog needs three focus mechanisms `RoomsPanel` has already had to ship (open-capture, close-return beating the platform's own, and a tick that drops the open dialog's row), none of which axe can see. A row-scoped reveal is covered by MOVES 3, 4 and 5 as they stand.
22. **`SKIP LOCKED` is tested for NON-BLOCKING, not for non-duplication.** Plain `FOR UPDATE` also yields two different customers — LockRows sits below the Limit, so the loser's EvalPlanQual re-check discards the row and locks the next one. What `SKIP LOCKED` buys is that a take-next never waits behind a colleague's call or skip, and that is what its test asserts.
23. **Step 2b: read the room's occupant under the room lock, before the queue is touched.** A fast path, not the guarantee — but it removes the feature's most likely collision from the class of "claim a customer's ticket and throw it away", which is the only way Risk 1's out-of-order service was reachable on the common path.

---

## Rejected findings

**None of the 32 review findings was rejected.** Three were applied in a narrower form than proposed, recorded here because a narrowing is a decision:

1. **The post-lock occupancy guard** (proposed: `has_active_for_room` + a second `occupant_of_room` read for the 409's details). Applied as **`occupant_of_room` alone** — it is the same predicate under the same lock, returning the row the refusal needs anyway, so the two-read form buys nothing. `has_active_for_room`'s docstring is still the authority for *why* a post-lock statement sees the committed claim, and is cited as such.
2. **A29's guard** (proposed: a rendered-DOM assertion **plus** a source scan for `/q/` in `WaitlistPanel.tsx`). Applied as **the DOM assertion only**. A source grep over one file is a second mechanism guarding the same property, and the finding's own companion (A29's original spelling) is the argument against grep-shaped tests. If a later feature does add a link, the DOM query reds.
3. **The e2e counts** (finding stated `storefront.spec.ts` declares 51). Applied with the **counted** figure, **55** — `grep -cE "^\s*test\("` against the shipped file — so the spec's total is 65, not the 58 it claimed or the 61 the finding implied. The finding's substance (the premise "zero console coverage" is false) is applied in full.
