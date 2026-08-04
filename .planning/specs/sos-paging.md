# Spec: F37 — SOS: targeted page, full-screen alert, ack/resolve, 30s escalation (Epic E7, floor program)

**Created**: 2026-08-03 · **Gate 1: standing approval — `interview-2026-07-30.md` §Standing approvals** (Q1's enumerated exceptions are F17, F18, F19, F20, F29, F48; F37 is none of them — no payments, no refunds, no privacy-law text, no billing) · **Design gate: self-approved (ruling 2026-07-31)** — Interview Q2 named exactly two novel interaction patterns for this run, F34's shift board and F42's capacity matrix; E7's screens assemble from F34's board shell and F57's shipped `FloorPanel`. **The gate goes away; the design work does not** — the deck and copy deck are build tasks (D17, D18), not review preconditions, and D15's focus-and-announcement contract is a **gate condition** in its own right (e7 Risks). · **Effort**: **L** — one migration with one `CREATE TABLE`, five routes on a router that already exists, **one new repository plus one method on a shipped one**, **two new `main.py` exception handlers** (it registers per concrete class, never per base), one new poll that runs on **eleven console sections that today poll nothing**, four new components, and an overlay that appears unbidden on a legally binding a11y surface.
**Depends on**: **F36** (`fitting_room_assignments` — the row an alert points at; `RoomsPanel`; the `_room_read`/`RoomRead` shape; `violated_index`; `elapsedLine`) · **F57** (`backend/app/floor/` router/service/schemas/validation; `FloorPanel.tsx`; `lib/usePoll.ts`; `lib/roles.ts`; `ELEVATED_ROLES`; `FloorService._authorize`) · **F34** (D4's six poll mechanisms, the `{401,403}` terminal rule, D11's live-region rule, D14's SC 2.2.2 control) · **F31/F51** (`require_role`, `RoleGate`'s **intersection** composition, the default-deny walker, the last-owner advisory lock this spec leans on in D3) · **F15** (`sessions`, `SessionsRepository` — "signed in somewhere" is a row in that table).
**Feeds**: nothing queued. F35's durable staff bell is the recorded upgrade path and is **dropped from this feature's deps** (ruling 2026-07-31).
**Spec review**: 33 findings from 3 lenses, 33 applied, 0 rejected (two applied in modified form and recorded as such in *Rejected findings*). **Four BLOCKERs, and three of them were one shape — a channel that goes quiet without saying so**: an accepted alert whose responder vanishes (D6's new `_stalled`), a terminal poll that renders `null` on eleven sections (D15's status strip + `onSessionEnded`), and a dismissal that is permanent on the eleven sections with no SOS centre (D15's re-open affordance). The fourth was the mirror image: an alert announced perfectly to a keyboard user who then could not reach the ack control (D15's Esc route-in).

**What F37 does *not* do.** No browser push, no APNs, no FCM, no service worker, no SMS, no `message_log` row, no `MessageKind` value — **in-app only, #32 stands and the 2026-07-31 ruling restates it.** No F35 bell. No chat thread on an alert. No severity levels, no per-role SLAs, no response-time analytics. No cross-tenant or cross-branch paging. No `sos_alert_targets` table (D1). No worker job (D6). No sound: a boutique fitting room is a quiet room and an autoplaying alarm is both a WCAG 1.4.2 problem and a bride's afternoon.

---

## Problem

A staffer is alone in a closed fitting room with a bride half-dressed in a ₪12,000 gown. She needs a seamstress with pins, or a second pair of hands on a corset back. **Today she opens the curtain and shouts.** This is the one thing on this floor with no manual workaround — every other coordination problem E6 and E7 solve has a slower, uglier, but real fallback, and this one has none.

What the product can do today, verified:

- **It knows who she is.** `staff_users` carries five roles since F57 (`models/constants.py:8-24`) and `sessions` records where each of them is signed in (`models/session.py`, `SessionsRepository.active_by_token_hash`).
- **It knows where she is.** F36 shipped `fitting_room_assignments`, and `idx_fitting_room_assignments_staff_active` — the `(tenant_id, staff_user_id)` partial unique index — makes "which room is this staffer in right now" **one indexed lookup returning at most one row by construction** (F36 Risk 1(b), which was written for this feature).
- **It has a live surface.** `FloorPanel` polls `/manage/floor` every five seconds behind `usePoll`, with a pause control, an idle stop, backoff, a `{401,403}` terminal rule and a `role="status"` cue region.
- **It has no way for her to ask for anything.** `grep -rn "sos" backend/app frontend/apps` finds nothing. There is no alert table, no alert route, no alert surface, and no mechanism in the console that renders over a section other than the one you are on.

**What is dangerous here is not the table.** It is three things, and each is answered below rather than waved past.

1. **A page that is lost is worse than no product.** If a raise can fail, or an alert can expire, or an accept can be lost to a race, the staffer learns not to trust it and goes back to shouting — and the one time she trusts it is the one time it matters. So the raise has **exactly three failure modes** (D3) and first-accept-owns is **structural** (D4).
2. **A full-screen red overlay that appears without warning on a device somebody is typing into is itself a defect.** This repo has shipped a focus bug **four times** — F56 on the storefront, F34 on the board, F57 on this very panel, F36's stale-closure patch — and axe walked past every one, because **axe cannot see a focus move that never happened, and it cannot see one that should not have happened either.** D15 is the whole answer and it is a gate condition (e7 Risks, pre-decided #38: IS 5568 / WCAG 2.0 AA is legally binding here).
3. **This is the first poll in the product that runs everywhere.** F34's and F57's loops live inside a section component and die when you navigate away. This one must survive every section, so it goes app-level (the ruling) — and that means eleven console screens that today issue zero requests will issue one every five seconds forever, plus a customer-data question that D10 answers by **carrying no customer data at all**.

## Goal

A staffer taps «קריאה לעזרה» on the room card she is standing in, picks a colleague or the shift manager, optionally types four words, and taps. Somewhere on the floor a phone goes **full-screen red** with her name, her room and her four words, and announces itself to a screen reader whether or not anybody is looking. The first person to tap «אני מגיעה» **owns it**; the second is told, by name, who does. If nobody has acknowledged it after **thirty seconds**, it rises on the shift manager's screen too — and that thirty seconds is computed when the row is read, not written by anything. If the colleague she named is not signed in anywhere, the page **is still created**, goes to the shift manager, and her own screen says so before she puts the phone down.

F37 ships **one migration** (one table, one index, one `enable_tenant_rls`), **five routes on the existing `/manage/floor` router**, **one NEW repository plus one method on a shipped one** (`SessionsRepository.has_live_session` does not exist — verified against `db/repositories/sessions.py`, which carries `insert` / `active_by_token_hash` / `revoke_for_staff_user` / `revoke_by_token_hash` and nothing else), **four `AuditAction` members**, **two new error codes** (each needing **its own `@app.exception_handler` block and its own import** — `main.py` registers by concrete class, never by base, verified at `:82` and `:1174-1180`), **one new `StrEnum`**, **one app-level poll**, **four new components**, **two new optional fields on `usePoll`** — and **no worker job, no unique index, no advisory lock, no new router, no new rate limiter, no second copy of anything F36 or F57 extracted, and no customer's name anywhere.**

## What already exists to build on (verified against code)

- **The floor router is shaped for this and says so.** `backend/app/floor/router.py` mounts `prefix="/manage"` with `dependencies=[Depends(_no_store), Depends(require_role(*StaffRole))]` (`:126-132`), carries thirteen routes after F36, and its docstring already argues every decision F37's routes would otherwise re-argue: seventh `/manage` router, all five roles at router level, tenant from `get_current_tenant(request)` and never `StaffContext.tenant_id`, a fifth local `_no_store` copy, no rate limiter, **real HTTP verbs and a path parameter for the target**, and — in as many words — that `.claude/rules`' RPC/`@QueryValue` guidance is another codebase's Kotlin boilerplate (`:85-87`).
- **`ELEVATED` is already spelled once on the router** (`floor/router.py:173`) and `ELEVATED_ROLES = frozenset({OWNER, SHIFT_MANAGER})` once in the service (`floor/service.py:69`), *spelled from the enum so a sixth role is not elevated by default*. F37 reuses both by import and adds neither.
- **`FloorService._authorize` is the two-axis check, by call and never by copy** (`floor/service.py:793-806`), and its docstring names this feature's exact hazard: *"A body-supplied `staff_user_id` doubling as the caller's identity is the one shape that turns 'any staffer on herself' into 'any staffer on anyone'."* F36 discharged that on the claim body; D3 states why the raise body is a **narrower** case and needs no `_authorize` call at all.
- **The 409-that-names-somebody has a shipped mechanism, end to end.** `_occupied_body` (`main.py:350-365`) copies a frozen module constant and adds `details` at raise time, *omitting the key entirely when there is nobody to name*; `_OccupiedError` (`floor/validation.py:43-62`) carries an optional `details` and is deliberately **not** a `DomainValidationError` subclass because *"Starlette resolves a handler by walking `type(exc).__mro__`"*; `ApiError` carries `readonly details?: Record<string, string>` typed `| undefined` and never `| null` (`api.ts:9-31`). D14 reuses all three.
- **⚠ Telling Postgres constraints apart has one working form and one that looks right.** `fitting_room_assignments.violated_index()` (`db/repositories/fitting_room_assignments.py:21-43`) records that `getattr(exc.orig, "constraint_name", None)` is **`None` for every violation there has ever been** — SQLAlchemy's asyncpg dialect rebuilds the error as a formatted string and raises it `from` the original — and that the working expression is `getattr(getattr(error.orig, "__cause__", None), "constraint_name", None)`. **F37 needs no constraint discrimination at all (D2), so it imports nothing from there; this is recorded so that nobody adds an index later and reaches for the obvious expression.**
- **The identity-map trap is documented five times and fixed twice in shipped code.** `StaffUsersRepository._refreshed` (`db/repositories/staff_users.py:195-223`) and `FittingRoomAssignmentsRepository._refreshed` (`:276-310`) are the canonical shape: a guarded `UPDATE … .returning(id)` for *"did I write"*, then `select(...).execution_options(populate_existing=True)` for what to render, applied **unconditionally**. D4 and D5 copy it verbatim.
- **Capture-before-write is documented on live code, twice.** `FloorService.end_break` (`floor/service.py:261-270`) and `FloorService.handover` (`:476-482`) both capture into a local before the writer runs, with ⚠ comments explaining that ORM-enabled DML's `evaluate` synchronization stamps the SET value onto the same identity-mapped instance. **F57's shipped note records that moving that capture after the write reddens exactly one `db` test and leaves all seventeen fast tests green**, because monkeypatched repositories never stamp anything. D13's `SOS_RESOLVED` has precisely this shape and is the fourth instance.
- **The forced-interleave harness is shipped, with its ordering rule written out.** `test_floor_db.py:251-263` states that `asyncio.gather` *"does not ORDER two transactions"*; the mechanism is that `tenant_session` is `async with session_factory() as session, session.begin()` so **exiting the context manager IS the commit** (`db/tenant.py:25`), and two nested `tenant_session`s on one `NullPool` factory take two separate connections. `test_a_second_start_landing_in_the_gap_renders_the_winners_timestamp` (`:266-325`) is the shape D4's accept race copies **exactly**, because the accept is an UPDATE and not an INSERT — the loser reads, the winner commits, the loser's guarded UPDATE matches zero rows, nothing ever blocks.
- **`usePoll` is extracted, tested, and carries F34's unmount fix and F57's StrictMode fix** (`lib/usePoll.ts`). It exports `POLL_INTERVAL_MS`, `MAX_BACKOFF_MS`, `IDLE_STOP_MS`, `IDLE_STOP_MINUTES`, `terminalOf`, and a `Poll`. **F36 changed not one line of it.** F37 changes **eight**, and D12 states the acceptance rule that makes that reviewable.
- **`FloorPanel.mutate(fn)` is already extracted** (`FloorPanel.tsx:363-386`, its ⚠ block at `:341-362`) — increment `mutationsRef`, `poll.clearTick()`, `poll.bump()`, run, classify a terminal error through `poll.fail`, decrement and `poll.reschedule()` **in the `.finally()`, not the success path**, *"or the panel silently stops converging the first time anybody acts"*. The SOS poll needs the same dance and D11 says why it gets its **own** copy inside the SOS provider rather than importing FloorPanel's.
- **`sessions` answers "is she signed in anywhere".** `Session` carries `tenant_id`, `staff_user_id`, `token_hash`, `expires_at` and the standard `deleted_at`; `SessionsRepository.active_by_token_hash` already filters `deleted_at IS NULL AND expires_at > now` (`db/repositories/sessions.py:30-42`). `settings.session_ttl_seconds` is **12 hours** (`core/config.py:24`), i.e. one shift. That is the whole of D3's reachability read.
- **`app/worker.py` ticks at `settings.worker_poll_interval_seconds`, default 60** (`core/config.py:124`, `worker.py:155-157`). D6 rejects it on that number.
- **`elapsedLine` / `elapsedMinutes` are shipped in `lib/elapsed.ts`**, anchored on the envelope's `server_now` — *"only the delta of a boutique tablet's clock is trusted and never its absolute value"* — clamped at zero because `created_at` is the **database** clock and `server_now` is the service's **Python** one. D6 inherits both the anchor and the clamp.
- **`jerusalemTime` renders an absolute instant with `timeZone` set** (`lib/jerusalem.ts:35`) and `FloorPanel` uses it for «מאז 11:20» (`:705-716`) — *it never subtracts*. D15's overlay uses exactly that and nothing else.
- **`@boutique/ui` ships `Button`, `Card`, `Badge`, `Select`, `Input`, `Modal`, `EmptyState`, `ToastProvider`** (`packages/ui/src/index.ts`), and `ConsoleShell` renders `<main id="console-main" tabIndex={-1}>` with a skip link pointing at it (`ConsoleShell.tsx:43,84`). D15 uses that `tabIndex={-1}` main as the one focus destination it needs outside its own subtree.
- **The `i18n.test.ts` global guard bans `/נשלח|תישלח|בדרך/` across every Hebrew value** (`:558-561`). ⚠ **«בדרך» is the natural Hebrew for "on my way" and is therefore banned from the single most important button in this feature.** D17 resolves it.
- **The Vite dev proxy names second path segments by explicit alternation and a backend test asserts SET EQUALITY against the live route table** (`vite.config.ts:18-19`, `test_spa_serving.py:381-408`). `floor` is already in the list; **every F37 route is under `/manage/floor/…`, so the segment set does not change** (D9).

## Design

### D1 — `sos_alerts` is one table, and `sos_alert_targets` is NOT built

```sql
CREATE TABLE sos_alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ,
    -- WHO IS CALLING. Never body-supplied: it is the StaffContext resolved from
    -- the session cookie (D3).
    raised_by UUID NOT NULL,
    -- WHOM SHE CALLED. NULL = the shift-manager ROLE, which is the audience
    -- {owner, shift_manager} — a set F51's last-owner invariant guarantees is
    -- never empty (D3). Also NULL when a named colleague turned out to be
    -- unreachable and the raise rerouted (D3), which is why the audit row
    -- carries the requested target and this column cannot.
    target_staff_user_id UUID,
    -- WHERE. F36's assignment row. NULL is ordinary: a staffer not in a room,
    -- or a pointer that no longer resolves (D3 — a page never fails over one).
    fitting_room_assignment_id UUID,
    -- FOUR WORDS. Optional, stripped, <= MAX_SOS_NOTE_LENGTH (120). NULL and ""
    -- are one input.
    note TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    -- WHO OWNS IT. Written by the same atomic UPDATE that sets status, so the
    -- pair can never disagree (D4).
    accepted_by UUID,
    acknowledged_at TIMESTAMPTZ,
    CONSTRAINT sos_alerts_status_check
        CHECK (status IN ('open', 'accepted', 'resolved', 'cancelled'))
);
```

`TEXT` not `VARCHAR`, `uuid_generate_v4()`, soft delete, `TIMESTAMPTZ`, `_updated_at_trigger("sos_alerts")`, `GRANT SELECT, INSERT, UPDATE, DELETE … TO app_user`, `enable_tenant_rls("sos_alerts")` — the `0008_bookings.py:107-110` trailing loop, unabridged, as `0019_fitting_rooms.py` already spells it for three tables.

**`accepted_by` is not in LOOP-STATE's column list and is not optional.** The ruling requires the losing accept to be *"a 409 NAMING THE OWNER"* and requires the raiser to see who is coming; neither is answerable from `status` and `acknowledged_at` alone. It is written by the same statement as `status` (D4), so «accepted with nobody» is unrepresentable in practice and asserted as such.

**`acknowledged_at`, not `accepted_at`.** LOOP-STATE governs; the e7 brief's `accepted_at` is the same column under the earlier name (Conflict 4).

**No `resolved_at`, no `resolved_by`, no `cancelled_at`, and that is a decision.** `status` says which terminal state, `updated_at` is stamped by the shipped trigger, and **the audit row is the record of who and when** — D13's four members carry the actor and the transition, which is the same argument F36's D13 makes for declining `FITTING_DRESS_REMOVED` (*"the binding ROW is the record"*) run the other way. Nothing in v1 or in the queue reads alert history. *Upgrade path if a pilot wants a response-time report: three columns and a writer, on a table whose only reader today is a poll over the live set.*

**`sos_alert_targets` is NOT built, and the epic's justification for it no longer applies.** The e7 brief wanted one row per paged staffer because targeting was a **role fanout**: it argued that deriving the audience at read time from (role, on-shift) would lose an alert for a staffer who went off shift mid-page, and would leave no evidence that nobody was on shift. The 2026-07-31 ruling replaced the fanout with **one target — a specific colleague or the shift-manager role** — so the audience is `target_staff_user_id`, a single nullable column, and there is nothing to snapshot. Building the table anyway would be one table, one repository, one insert per raise and one join per tick, to record a set with at most one member. (Conflict 1.)

**`note` is not personal data about a customer and must not become so.** It is free text a staffer types about her own situation («צריך סיכות»), it is disclosed to the alert's audience only, and it is never rendered on a public surface. D10 keeps every *customer* datum off this payload entirely, which is what makes the app-level poll defensible; a staffer who types a bride's name into the note has disclosed it to three colleagues for the length of one fitting, which is strictly less than F36's payload already does. Recorded, and handed to F20 as a processing-record line (Risk 5) rather than validated against — a length cap on an emergency field is the product being clever at the expense of the person in front of it, and 120 characters is already the cap.

### D2 — There is **NO unique index on `sos_alerts`**, and the reason is the one that makes this feature's guarantee structural anyway

F36's whole concurrency design is a partial unique index, and the tempting move here is to copy it: *one open alert per raiser*. **It does not work, and the reason is worth writing down because the failure is silent.**

The index would have to be

```sql
CREATE UNIQUE INDEX … ON sos_alerts (tenant_id, raised_by, target_staff_user_id)
    WHERE status = 'open' AND deleted_at IS NULL;   -- ⚠ WRONG
```

and **Postgres treats NULLs as distinct in a unique index** (no `NULLS NOT DISTINCT` in this schema, and adding it would be this codebase's first). `target_staff_user_id IS NULL` is *the shift-manager route* — the single most common target and the destination of every reroute (D3) — so the index would refuse the duplicate in the rare case (two pages to the same named colleague) and permit it in the common one. An index that guards everything except the case it was written for is worse than none: it is a guarantee a reviewer will believe.

The alternatives are both worse. `COALESCE(target_staff_user_id, '00000000-0000-0000-0000-000000000000')` is a functional index encoding a sentinel uuid that means "role" — a lie in the schema for a constraint nobody asked for. Dropping `target_staff_user_id` from the key would forbid the legitimate double page («I need a seamstress **and** I need the manager»), which is a real thing a staffer alone with a bride does.

**So: the raise is an unguarded INSERT and duplicates are possible.** What prevents them is the same thing that prevents F36's double-tap: `mutate`'s busy discipline disables the control while the request is in flight, and a duplicate alert is **noise, not corruption** — two cards on an overlay, either of which resolves the emergency. That is a categorically smaller harm than F36's double-claim, which put two brides behind one curtain.

**F37's structural guarantee is not an index. It is the conditional UPDATE** — `… WHERE status = 'open'` — which is exactly what "first-accept-owns, expressed structurally" means in the ruling, and it needs no index at all because it constrains a **transition**, not a **set**. This is the third case in this codebase's running argument and it belongs beside the other two:

| Feature | Invariant | Mechanism | Why not the others |
|---|---|---|---|
| F13 booking seat | "the lowest free seat" | **advisory lock** + unique index | the inserted value is derived from a **count**, i.e. a read-then-write |
| F51 last owner | "at least one" | **advisory lock** | *"No unique index can express it: an index expresses at most one of something"* (`auth/staff.py:9-34`) |
| F36 room claim | "at most one" | **partial unique index**, no lock | exactly what an index says, evaluated by the index rather than against a snapshot |
| **F37 accept** | **"exactly one transition out of `open`"** | **conditional UPDATE, no lock, no index** | it constrains a **state change**, not a population — Postgres's row-level write lock on `UPDATE … WHERE status='open'` serialises the two contenders and the loser's predicate then matches zero rows |

**One index, non-unique and partial:**

```sql
-- The poll's ENTIRE read: this tenant's non-terminal alerts, oldest first.
-- Predicate matched EXACTLY by the query so the planner uses it (F36's D11
-- rule). ⚠ Postgres deparses `IN (...)` to `= ANY (ARRAY[...])` and reorders
-- predicates — CAPTURE this literal from a live 16.x server for the pinning
-- test, do not transcribe it from this file (F34's shipped note, F33's D2).
CREATE INDEX idx_sos_alerts_live
    ON sos_alerts (tenant_id, created_at)
    WHERE status IN ('open', 'accepted') AND deleted_at IS NULL;

-- The raise's reachability question is answered against `sessions`, not here.
-- This one is for the four verbs' by-id read, which RLS already narrows to one
-- tenant — but the table grows monotonically and every verb reads by id, so the
-- PRIMARY KEY serves it and no second index is added.
```

**Only one index, and the history index F36 shipped is deliberately NOT copied.** F36 added `idx_fitting_room_assignments_tenant_created` with **named readers** (F37 and F41). `sos_alerts` has none: nothing in v1, nothing in the queue and nothing in E8–E10 reads a resolved alert. *Upgrade path, one line, stated cost: the day something reports on response times it adds `(tenant_id, created_at) WHERE deleted_at IS NULL` and takes the `ACCESS EXCLUSIVE` lock on a table that will still be small.*

### D3 — Verb 1 of 4: **RAISE**, and it has exactly three failure modes

```
POST /manage/floor/sos
body: { "target_staff_user_id": uuid | null, "fitting_room_assignment_id": uuid | null, "note": string | null }
-> { "alert": SosAlert, "rerouted": bool }
```

Ordered exactly:

1. **Validate.** `note` stripped, `""` → `None`, `len <= MAX_SOS_NOTE_LENGTH` (**120**) → else `SosValidationError` → 400. `target_staff_user_id == actor.id` → 400 «אי אפשר לקרוא לעצמך.» — a self-page has no audience and would sit open forever escalating to the shift manager for nothing.
2. **`raised_by = actor.id`, full stop.** ⚠ There is **no `_authorize` call on this route and its absence is the design, not an omission.** `_authorize`'s docstring names the hazard as *a body-supplied `staff_user_id` doubling as the caller's identity*; the raise body carries a **target**, never an actor, and the actor is the `StaffContext` from the session cookie. Nobody may raise a page **as** somebody else — not even an owner — because an SOS is a first-person statement («I need help»), and an owner who needs help raises her own. **Asserted, not asserted-in-prose:** a fast test posts a body containing `raised_by` and asserts `ForbidExtraModel` answers **400** rather than honouring it (the shipped house form, `floor/schemas.py`).
3. **Resolve the room pointer, permissively — and it must be HER OWN assignment.** If `fitting_room_assignment_id` is given, read it with `tenant_id`, **`staff_user_id = actor.id`**, `deleted_at IS NULL`, and **no `released_at` filter** (see D10). If it does not resolve, **store `NULL` and carry on**. A stale room pointer must never refuse a page; RLS makes a foreign tenant's id simply not resolve, so there is no leak and no oracle.

   ⚠ **The `staff_user_id` conjunct is not tidiness.** Without it any of the five roles could raise with any assignment id in her own tenant, and F36's floor payload hands every one of them out — `RoomAssignment.id` is on every occupied tile. The page would then render «דנה קוראת לעזרה — חדר 2» while Dana is standing in room 4. **«No room» is a defined, safe state this spec designed for (`sos.noRoom`); «wrong room» is not, and in an emergency it is strictly worse than no room** — the responder walks to a closed curtain with a stranger's bride behind it. D3 argues at length that the *actor* can never be body-supplied; the *location* gets the same treatment. The fallthrough stays permissive, so the three failure modes stay three, and the unfiltered read's weak in-tenant existence oracle goes with it. **AC1 walks this case («an assignment belonging to another staffer stores NULL and the alert is still created») and `test_sos_service.py` asserts it.**
4. **Resolve the target, permissively — and this is THE NO-ON-SHIFT-TARGET CASE.** If `target_staff_user_id` is given:
   - it must resolve to a live `staff_users` row for this tenant, **and**
   - that staffer must hold at least one **live session** — `SessionsRepository.has_live_session(tenant_id, staff_user_id, now)`, i.e. `deleted_at IS NULL AND expires_at > :now`. ⚠ **This method does not exist and is new work**: the shipped repository carries `insert`, `active_by_token_hash`, `revoke_for_staff_user` and `revoke_by_token_hash`, nothing more (verified). It is the codebase-consistent reading of the ruling's *"the targeted device is simply wherever that staffer is signed in"*, and it is one indexed-by-nothing read over a table with a handful of rows per tenant.

   ⚠ **WHAT THIS READ ACTUALLY PROVES, stated honestly because the copy could be read as claiming more.** A live `sessions` row proves **a session, not a screen**. `settings.session_ttl_seconds` is **12 hours** (`core/config.py:24`) and nothing revokes on going home — `revoke_for_staff_user` fires on a password change and on deactivation only. A staffer who signs in at 08:00 and leaves at 16:00 without logging out holds a live row until 20:00. And `usePoll` stops entirely on `document.hidden` (Risk 1), so a phone asleep in an apron is a live session behind a dark screen. **So the read is a cheap UPPER BOUND on reachability: `rerouted: false` claims only "she has not signed out and her session has not expired", and `rerouted: true` is the case it genuinely closes.** The copy «{{name}} לא מחוברת עכשיו» is worded for the negative case for exactly that reason and stays as written. **The thirty-second escalation is the real safety net, not this read** — that sentence belongs beside the read, not two sections away, and it is the honest answer to "what covers a live session on a sleeping device". Residual recorded in Risk 3, which already carries the structurally identical logged-out-elevated case.

   If **either** check fails, the alert is created with `target_staff_user_id = NULL` — **routed to the shift manager, in the data and not merely in the UI** — and the response carries `rerouted: true`. The raiser is then told **by an explicit acknowledgement rather than a transient cue** (D16): the raise dialog stays open and shows «{{name}} לא מחוברת עכשיו. הקריאה עברה למנהלת המשמרת.» with one «הבנתי» that closes it. **The raise does not fail.**
5. **INSERT.** One statement, no lock, no savepoint (D2 — there is no index to violate, therefore no `IntegrityError` to recover from, therefore no `begin_nested()`; stated because F36's claim has all three one file over and copying them here would be cargo).
6. **Audit** `SOS_RAISED` in the same transaction, before commit, carrying the **requested** target (D13).
7. **Answer** the rendered alert plus `rerouted`.

**THE THREE FAILURE MODES, exhaustively: 401 (no session), 403 (a role outside the five — impossible for a signed-in staffer, since the router admits all five), 400 (note too long, or self-target).** ⚠ **Nothing about the state of the boutique can refuse a page.** Not a missing room, not a deleted room, not a released assignment, not a colleague who went home, not a colleague who does not exist, not an empty shift, not another alert already open. That sentence *is* «a page is never silently dropped», expressed as a list a test can walk, and **AC1 walks it**.

**Why the shift-manager audience can never be empty, with the citation.** A `NULL` target routes to `ELEVATED_ROLES = {owner, shift_manager}` (`floor/service.py:69`). `auth/staff.py:9-34` holds the **last-owner invariant — "at least one live owner"** — under an advisory lock, precisely because *"No unique index can express it."* So every tenant always has at least one live owner, and the role route always has an audience. **This is the property that makes the epic's "with no on-shift staffer in the requested role" unreachable for the role target and real only for a named one** — which is exactly why step 4 is where the requirement is discharged. (Conflict 2.)

**Declined: an on-shift column.** The e7 brief says on-shift *"comes from whatever F31 exposes as the current-shift read"*. **F31 exposes no such thing and neither does F57**: `staff_users` carries `email, password_hash, display_name, role, break_started_at` and nothing else, and `StaffUsersRepository.list_live` returns every non-deleted staffer (`:37-45`). F34's `checked_in_at` is on **bookings**, not staff. Adding an on-shift flag here would be F37 building F40's roster on the way past, and a live session is a **better** signal than a checkbox: nobody has to remember to tick it and it is derived from an action she actually took. ⚠ **But it is not a signal that "cannot go stale", and claiming that would be wrong** — a 12-hour TTL outlives a shift, so a session goes stale by simply not being used (above). It is **strictly better than a checkbox and no worse**, which is the whole claim, and the residual — signed in, gone home — is closed by the thirty-second escalation and by nothing else. (Conflict 2, Risk 3.)

### D4 — Verb 2 of 4: **ACCEPT/ACK**, an atomic conditional UPDATE, and the 409 names the owner

```
POST /manage/floor/sos/{alert_id}/accept  ->  SosAlert
```

```sql
UPDATE sos_alerts
   SET status = 'accepted', accepted_by = :actor, acknowledged_at = :at
 WHERE tenant_id = :t AND id = :id AND status = 'open' AND deleted_at IS NULL
 RETURNING id
```

then **one** `select(...).execution_options(populate_existing=True)` re-read for what to render — `FittingRoomAssignmentsRepository._refreshed` applied to this table, **unconditionally**, for the reason that docstring gives: *"whether a caller happened to load the row first is exactly the reasoning that has bitten this repo three times."*

`acknowledged_at` comes from `FloorService`'s **injectable clock**, not SQL `now()`, so the `db` suite can freeze it and assert an equality rather than a range — the shipped shape one method over (`FittingRoomAssignmentsRepository.release`'s `at` parameter).

**`status` and `accepted_by` are set by ONE statement**, so «accepted by nobody» and «open but owned» are both unrepresentable. Stated because the obvious two-step (stamp the owner, then flip the status) reintroduces the whole race this verb exists to close.

Ordered exactly, and the **order is the first-accept-owns guarantee**:

1. **Read the alert** (`tenant_id`, `id`, `deleted_at IS NULL` — **no `status` filter**, for `by_id`'s reason in `fitting_room_assignments.py:122-131`: filtering here would make a losing accept read as *absent* and answer 404 instead of naming the owner).
2. **Absent, or not visible to this caller under D7's audience rule → `DomainNotFoundError` → 404.** Not a 403: whose alert it is can only be learned by reading it, so a 403 on a real id and a 404 on a fake one would discriminate existence — F36's D7 argument, same shape, same conclusion.
3. **Not permitted to accept → 404, byte-identical.** Permitted = `row.raised_by != actor.id` **AND** (`actor.id == target_staff_user_id` **or** `actor.role in ELEVATED_ROLES`). The shift manager is the universal fallback and may accept anything, *regardless of her own role* (the e7 brief's phrase, preserved) — **except the page she raised herself.** ⚠ **The `raised_by` term is a CONJUNCT of the whole predicate and not a clause of the target check**, because an elevated raiser passes the target check on the elevated branch: an owner alone in a fitting room, raising to the shift-manager ROLE (the dialog's first and DEFAULT option), could accept her own page in one tap — and `_escalated` short-circuits on `status != OPEN`, so the alert stops rising on **every device in the boutique** for the two minutes `_stalled` takes, while `_for_me`'s accepted branch returns `stalled and elevated`, which is False for the raiser at every t. If she is the only elevated staffer signed in it never rises again at all. She has `resolve` and `cancel`. **The guard sits ABOVE the idempotence branch so a raiser gets the same indistinguishable 404 as any other refused caller, and `SosCentre.tsx` mirrors it** (`mayAccept` carries `alert.raised_by !== selfId`) so the control does not exist either. **Test: `test_the_raiser_may_not_accept_her_own_page` PARAMETRIZED over `[SEAMSTRESS, OWNER, SHIFT_MANAGER]`** — the un-parametrized version pinned only the seamstress and the two elevated rows were unguarded and untested.
4. **⚠ IDEMPOTENCE FIRST, keyed on the request.** `status == 'accepted' AND accepted_by == actor.id` → **200 with the existing alert, no audit row, no write.** She tapped twice, or two of her devices did. F36's D6 branch, same reasoning, and it must be resolved before the 409 or a double-tap tells her *she* has it, by name, as an error.
5. **The conditional UPDATE.** Rowcount 1 → audit `SOS_ACCEPTED` → 200 with the re-read row.
6. **Rowcount 0 → discriminate on the CURRENT status, which is the only discriminator this feature has** (there is no constraint name because there is no index — D2):

| Current status | Answer | Code | `details` | What she reads |
|---|---|---|---|---|
| `accepted`, by somebody else | **409** | `SOS_ALREADY_ACCEPTED` | `{"staff_display_name": "דנה"}` | «דנה כבר מגיעה.» |
| `accepted`, by somebody else whose staff row is gone | **409** | `SOS_ALREADY_ACCEPTED` | *(absent)* | «מישהי אחרת כבר מגיעה.» |
| `resolved` or `cancelled` | **409** | `SOS_CLOSED` | *(never)* | «הקריאה כבר נסגרה.» |
| `open` | unreachable — the UPDATE would have matched | re-raise → 500 | — | the outage register |

**The `details`-less branch is real and is not defensive padding.** `accepted_by` names a `staff_users` row that F51's staff removal can soft-delete at any time, and the acceptor can be removed between her accept and this read. `details` is therefore **optional on `SOS_ALREADY_ACCEPTED`, typed `Record<string, string> | undefined` and never `| null`** — F36's D14 rule and `_occupied_body`'s shipped `if details:` (`main.py:363-365`), because «{{name}} כבר מגיעה.» rendering with an empty interpolation on a legally binding surface is worse than a sentence that admits it does not know. **`db` test: `test_an_accept_whose_winner_was_removed_does_not_name_nobody`.**

**Two codes and not one with a discriminating `details`** — F36's D14 argument, verbatim and for the same reason: two causes, two Hebrew sentences, two remedies (go somewhere else / there is nothing to do), and a `details`-key sniff in the console is a worse place for that branch than an error code.

**⚠ The unreachable branch is genuinely unreachable and must still have an `else`.** F41's spec review found the same shape and recorded why: *"a zero-row UPDATE TAKES NO LOCK and the repo runs READ COMMITTED"*, so a concurrent write can move the row between the UPDATE and the re-read. Here the re-read can therefore find `open` — the winner accepted and the raiser resolved and… no: nothing moves a row **back** to `open`, so `open` after a zero-row UPDATE means the row was deleted and re-created, which `uuid_generate_v4()` makes impossible. It is still spelled as `else: raise` rather than as a comment claiming impossibility, because F41's finding was exactly that an "impossible" branch with no `else` returns `None` and 500s with no message.

### D5 — Verbs 3 and 4: **RESOLVE** and **CANCEL**, and rowcount 0 is not an error

```
POST /manage/floor/sos/{alert_id}/resolve  ->  SosAlert
POST /manage/floor/sos/{alert_id}/cancel   ->  SosAlert
```

```sql
-- resolve: from EITHER live state. The emergency is over.
UPDATE sos_alerts SET status = 'resolved'
 WHERE tenant_id = :t AND id = :id AND status IN ('open','accepted') AND deleted_at IS NULL
 RETURNING id

-- cancel: from `open` ONLY.
UPDATE sos_alerts SET status = 'cancelled'
 WHERE tenant_id = :t AND id = :id AND status = 'open' AND deleted_at IS NULL
 RETURNING id
```

**Who.** Resolve: the raiser, the acceptor, **or** elevated. Cancel: the raiser **or** elevated. Both refuse with **404, byte-identical to a missing id** (D4 step 2's reasoning). Declined "anyone may resolve any alert": closing somebody else's open emergency is the one destructive act on this surface, and the elevated path already covers the legitimate case (a shift manager clearing up after a page that resolved itself).

**⚠ Both verbs run D4's SIX-STEP ORDER, and each gets its own discriminator table.** Prose was not enough here: an earlier draft stated *"rowcount 0 with a live row back is a 200"* and, one paragraph later, *"cancelling an ACCEPTED alert is a 409"* — **and cancel-of-accepted IS rowcount 0 with a live row back**, so the two rules disagreed on the same input with no stated precedence. A builder reading top-down writes the 200 and leaves the 409 unreachable. **The table is the rule; the prose below it is the reason.**

Ordered exactly, both verbs: **read (no `status` filter) → visibility 404 → permission 404 → conditional UPDATE → rowcount 0 discriminator.** ⚠ **The permission check PRECEDES the discriminator**, and that ordering is load-bearing: a 409 carrying `{"staff_display_name": "דנה"}` handed to a caller who may not act would leak a staff name that the 404-not-403 rule exists to withhold.

**RESOLVE**, on the re-read status after a zero-row UPDATE:

| Current status | Answer | Audit |
|---|---|---|
| `resolved` | **200** with the row | none |
| `cancelled` | **200** with the row | none |
| no row | **404** | none |
| `open` / `accepted` | unreachable — the UPDATE would have matched → `else: raise` | — |

**CANCEL**, same:

| Current status | Answer | `details` | Audit |
|---|---|---|---|
| `accepted` | **409 `SOS_ALREADY_ACCEPTED`** | `{"staff_display_name": …}`, **optional** (D4's rule) | none |
| `cancelled` | **200** with the row | — | none |
| `resolved` | **200** with the row | — | none |
| no row | **404** | — | none |
| `open` | unreachable → `else: raise` | — | — |

**Rowcount 0 with a live row back is otherwise a 200 and writes no audit row.** She wanted it closed; it is closed. F36's D7 rule (*"She wanted the room free; the room is free"*) and F34's D8 no-op rule, applied to a state machine instead of a timestamp. Rowcount 0 with **no** row back is a 404. **A second cancel of an already-cancelled alert is a 200 and has its own AC** (AC9).

**⚠ Cancelling an ACCEPTED alert is a 409 `SOS_ALREADY_ACCEPTED` naming the acceptor, and that asymmetry with resolve is the point.** A colleague is already walking to that curtain. Silently cancelling would send her to an empty room and teach her that accepting means nothing — the exact erosion this feature exists to prevent. The raiser's remedy is one word over: **resolve**, which is what actually happened («she sorted it, the responder can stand down»), and the copy says so. The 409 reuses D4's code, its optional `details` and its Hebrew, so this costs no new error and no new sentence.

**The resolve's audit row carries the state it destroys.** `SOS_RESOLVED` with `details={"from_status": "open"|"accepted"}`, ⚠ **captured into a local BEFORE the writer runs** — `FloorService.end_break`'s and `handover`'s ⚠ comments verbatim (`floor/service.py:261-270`, `:476-482`): the UPDATE is ORM-enabled DML whose `evaluate` synchronization stamps `'resolved'` onto the same identity-mapped instance out of one identity map, so reading it afterwards records `resolved → resolved` and empties the row of its whole informational content. F57's shipped note records that this exact mutation **reddens one `db` test and leaves all fast tests green**, because monkeypatched repositories never stamp anything — **so the mutation check for this line has to be a `db`-marked test and cannot be anything else** (Testing).

**«did anybody answer?» is answerable from the pair `SOS_RAISED` / `SOS_ACCEPTED`** without a `resolved_at` column, which is D1's argument for not shipping one.

### D6 — **THE READ-TIME ESCALATION PREDICATE**, written out, and the worker explicitly rejected

```python
# app/floor/service.py — the whole of the escalation design.
ESCALATION_AFTER = datetime.timedelta(seconds=30)
STALLED_AFTER = datetime.timedelta(minutes=2)

def _escalated(row: SosAlert, *, server_now: datetime.datetime) -> bool:
    """OPEN, unacknowledged, and older than thirty seconds.

    `status == 'open'` already implies `acknowledged_at IS NULL` (D4 sets both in
    one statement), and the second conjunct is spelled anyway so the predicate
    reads as the rule rather than as a consequence of another decision.

    ⚠ TWO CLOCKS. `created_at` is `server_default=text("now()")`, i.e. the
    DATABASE host's transaction-start time (F36's D2 records this and its
    consequence), while `server_now` is the SERVICE's Python clock — the same
    instant that goes on the wire as `server_now` and that `elapsedLine` anchors
    on. The skew is NTP-bounded and irrelevant against a 30-second threshold
    read every 2 seconds.

    ⚠ AND THERE IS DELIBERATELY NO `max(timedelta(0), ...)` CLAMP HERE, unlike
    `lib/elapsed.ts:23-25`, which is where the clamp is genuinely load-bearing.
    `elapsedMinutes` returns a RENDERED NUMBER, so a negative delta ships
    «כבר -1 דק'» to a screen. This returns a BOOLEAN against a one-sided
    positive threshold: `created_at > server_now` makes the delta negative, and
    `timedelta(seconds=-5) >= timedelta(seconds=30)` is already False — BYTE
    IDENTICAL to the clamped result. A clamp here pins nothing, and a spec
    review found the "drop the clamp" mutation coming back GREEN, which is
    exactly the false confidence the mutation regime exists to catch. The
    negative-delta case stays as an ASSERTION (AC5); it is not a mutation
    target.
    """
    if row.status != SosStatus.OPEN or row.acknowledged_at is not None:
        return False
    return server_now - row.created_at >= ESCALATION_AFTER


def _stalled(row: SosAlert, *, server_now: datetime.datetime) -> bool:
    """ACCEPTED two minutes ago and still not resolved — the SECOND silence.

    Same zero-write mechanism, same shared `server_now` anchor, one more
    constant and one more branch. See below for why it exists at all.
    """
    if row.status != SosStatus.ACCEPTED or row.acknowledged_at is None:
        return False
    return server_now - row.acknowledged_at >= STALLED_AFTER
```

**⚠ `_stalled` CLOSES THE HOLE THAT `_escalated` OPENS, and without it the accept path re-opens the one guarantee this feature exists to make.** `_escalated` short-circuits on `status != OPEN` and `_for_me` returns False for any non-open row (*"an accepted alert is somebody's job now"*). So **the instant anybody taps «אני מגיעה» the alert stops escalating and stops rising on every device in the boutique, forever.** If the acceptor's phone dies, her session drops, she is pulled into another fitting, or she taps accept and forgets — nothing ever re-surfaces it. There is no auto-resolve (Out of scope, correctly), no un-accept verb and no second threshold. **And it is worse than silence, because the raiser's screen reads «דנה מגיעה»: she stops looking for help on the strength of a signal the product cannot back.** E7's rule is *"a page is never silently dropped"*, and D3 discharges it on the **create** path only.

Two minutes is the threshold because a responder walking the length of a boutique and resolving on arrival takes well under it, and because a raiser told «דנה מגיעה» will wait roughly that long before deciding nobody is coming. It is a ruling-free number and it moves with pilot evidence exactly as `ESCALATION_AFTER` does (Risk 2), for the same reason: **read-time derivation means changing it changes every alert immediately, with no migration and no backfill.**

*Declined, and recorded: the alternative to a second boolean is not silence — it is the state table gaining the row, the SOS centre offering the raiser a visible re-raise, and a Risk with an owner and a trigger naming the ceiling. **The derived boolean is cheaper than the Risk**, introduces no new mechanism, and is the same argument D6 makes for `escalated` one paragraph up.*

Derived per row on every read, from **the same `server_now` the envelope carries**, and that shared anchor is the decisive argument for Python over SQL. The alternative — `(status = 'open' AND created_at <= now() - interval '30 seconds') AS escalated` — is *more* correct about clocks (one clock on both sides) and *less* correct about the screen: the elapsed line is computed against `server_now` (F36's `elapsedLine`), so a SQL-side predicate against `now()` could render «כבר 0 דק'» beside an escalated badge. **One instant decides both, or the overlay disagrees with itself.**

**THE WORKER IS REJECTED, and the justification is recorded because the alternative looks tempting.**

- `app/worker.py` ticks at `settings.worker_poll_interval_seconds`, **default 60** (`core/config.py:124`, and the log line at `worker.py:155-157` prints it). A worker-stamped `escalated_at` would therefore arrive **up to a full minute late — twice the requirement** — for a mechanism whose entire specification is a thirty-second number.
- It would introduce a **write that races a concurrent ack**: the worker's `UPDATE … SET escalated_at` and a responder's `UPDATE … WHERE status='open'` touch the same row from two processes, and every ordering has to be reasoned about for a value nothing durable needs.
- It would add a third job to `poll_once`, whose shipped comment already flags `O(tenants)` queries per tick as *"noise at pilot volume"* — and this one would be `O(tenants)` **even when no boutique in the country has an open alert.**
- The read-time predicate adds **zero latency beyond the poll**, cannot race anything because it writes nothing, and is the **house compute-on-read pattern**: pre-decided #30's queue positions, F43's fitting ordinals, `card_status()` (`floor/service.py:80-94`, *"Derived on read, never stored"*), and F36's occupancy itself.

**The recorded upgrade path, if history ever needs it:** a durable `escalated_at TIMESTAMPTZ`, stamped by the **accept path and the poll are still not its writer** — it would be stamped by whichever read first observes the threshold, which is a write on a read path and is exactly why it is not this build.

**What escalation actually changes.** ⚠ Not the audience: **a shift manager can see every alert in her tenant from the instant it is raised** (D7), because "never silently dropped" requires it and because she is the fallback. Escalation changes **whether the overlay rises on her device** — otherwise a shift manager would get a full-screen red interruption for every seamstress-to-seamstress page in the boutique, and would learn within a day to dismiss them unread. That is the derivation D7 folds into one server-computed boolean.

### D7 — The audience rule and `for_me`: one predicate, computed on the server, twice

**Visibility** (the SQL `WHERE`, in addition to `tenant_id`, `deleted_at IS NULL` and `status IN ('open','accepted')`):

```python
# Built conditionally in Python: an elevated caller gets NO extra predicate at
# all, which is both faster and clearer than binding a boolean into SQL.
if actor.role not in ELEVATED_ROLES:
    stmt = stmt.where(
        or_(
            SosAlert.raised_by == actor.id,           # her own page, so she sees the accept
            SosAlert.target_staff_user_id == actor.id,  # she was named
            SosAlert.accepted_by == actor.id,           # she owns it
        )
    )
```

**Rising** (`for_me`, derived per row alongside `escalated`):

```python
def _for_me(row: SosAlert, *, actor: StaffContext, escalated: bool, stalled: bool) -> bool:
    if row.raised_by == actor.id:
        return False                       # ⚠ never your own page — see below
    if row.status == SosStatus.ACCEPTED:
        # An accepted alert is somebody's job — UNLESS nobody has moved on it
        # for two minutes, at which point it is nobody's job again and the
        # shift manager is the fallback. D6's second silence.
        return stalled and actor.role in ELEVATED_ROLES
    if row.status != SosStatus.OPEN:
        return False                       # resolved / cancelled: nothing to do
    if row.target_staff_user_id == actor.id:
        return True                        # she named you
    if actor.role in ELEVATED_ROLES:
        return row.target_staff_user_id is None or escalated
    return False
```

**⚠ The raiser never gets the overlay for her own page**, and this is the sharpest of the small decisions. She is holding a bride's corset with one hand and her phone in the other; a full-screen red interruption on her own device, caused by her own tap, would be the product shouting at the person who asked for quiet. She sees the alert in the SOS-centre panel, and the thing she actually needs — **who is coming** — arrives as the accept, on the same 2-second tick.

**Both booleans are computed on the SERVER and ride the wire**, and that is the load-bearing choice. Put `for_me` in the console and the audience rule exists twice, in two languages, and the day the escalation window changes, one of them changes. On the server it is **pure branches over a `StaffContext` and a row**, unit-testable as a matrix against fakes with no database at all — which is exactly the shape `test_floor_service.py` already uses for F36's two axes, and where AC5's table lives.

### D8 — One migration, revision id resolved at build time, and what it must prove it did not do

**The revision id is NOT in this document.** At the time of writing `main`'s head is `0019_fitting_rooms.py` (`revision = "0019"` / `down_revision = "0018"`), and **more than one other feature is in flight with a migration of its own**. ⚠ **TWO features hold a `0020` at build time, not one** — F41 (PR #39, since merged, moving the head to `0020`) and F58 (`floor-dispatch`, building in its own worktree with a migration of its own). The earlier carve-out that excluded F58 was written off a stale LOOP-STATE `status: queued` and rotted; the clause it was written for — *"do not OPEN the PR while a lower-numbered migration is still unmerged"* — **binds on both**. ⚠ **Do not read that head as current.** It moved three times on one day during the F33/F19/F53 window, which is why LOOP-STATE replaced every fixed assignment with a rule. **Read the head from `alembic heads`, and read the in-flight set from LOOP-STATE's `current:` block:**

> **BUILD** at `alembic heads` + 1 with `down_revision` = whatever head is on the branch, so the branch is self-coherent and its `db`-marked tests actually run.
> **RENUMBER** at the rebase that precedes the push, re-resolving from `alembic heads` on `main` **immediately** before it.
> **Make the migration the LAST commit on the branch**, so the renumber is one `git commit --amend` touching one file that nothing else references.
> **Do not OPEN the PR while a lower-numbered migration is still unmerged.**

F36 records this working exactly as written (*"built at 0018, renumbered to 0019 when F33's 0018 landed first"*), and F33's D15 records that it was **tested, not theorised**: a `down_revision` naming a revision that lives only on another branch makes alembic unable to build the revision map at all, so `alembic upgrade head` fails and every `db`-marked test fails with it — a wrong number therefore fails **loudly** rather than drifting. F19's fast, no-DB single-head guard is what catches a double head in `make test` instead of as a CI mystery.

Everything asserted below is keyed to **"after this feature's migration"**, never to a number.

The upgrade is one `CREATE TABLE`, one index, one `_updated_at_trigger("sos_alerts")`, and the trailing loop:

```python
op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON sos_alerts TO app_user")
for statement in enable_tenant_rls("sos_alerts"):
    op.execute(statement)
```

`downgrade()` is `DROP TABLE IF EXISTS sos_alerts` and nothing else (`0008_bookings.py:113-115`, `0019_fitting_rooms.py`). **F37 touches no existing table**, so it has nothing to un-touch.

**⚠ The round-trip test must use F36's `_parent_of(marker)` helper and never `command.downgrade(cfg, "-1")`.** F36's shipped note records that `test_migration_0017_round_trips` broke *by being landed on* — `-1` made it downgrade the fitting-room tables and then assert about customers — and that the fix resolves the target **by identity**. F37 is the first migration to land on top of that helper and must prove it costs nothing (AC12).

**What the migration must prove it did not do**, as `db`-marked tests rather than as promises:

- **The `status` CHECK pinned byte-identical**, read from `pg_constraint`/`information_schema` after this feature's migration. ⚠ **CAPTURE the literal by running it on a real 16.x server.** Postgres deparses `IN (…)` to `= ANY (ARRAY[…])`, re-parenthesises and schema-qualifies — F34's shipped note and F33's D2 both record that a literal that merely *looks* right pins nothing and reddens CI. This is the highest-value test in the migration, because what it guards against is a *future* edit: the day anybody adds a fifth status they collide with a pinned literal and a review instead of colliding with nothing.
- **`idx_sos_alerts_live`'s definition pinned byte-identical** from `pg_indexes.indexdef`, same capture rule.
- **`sos_alerts` carries EXACTLY ZERO unique indexes besides the primary key** — `SELECT count(*) FROM pg_index WHERE indrelid = 'sos_alerts'::regclass AND indisunique AND NOT indisprimary` is **0**. This is D2's decision expressed as an assertion: a well-meaning `(tenant_id, raised_by) WHERE status='open'` added later would forbid the legitimate double page and would be defeated by NULL-distinctness in the common case, and nothing else in the suite would fail.
- **`test_every_tenant_id_table_has_forced_rls` stays green with no edit** — one new `tenant_id` table, and the test that scans `pg_class` for `relforcerowsecurity` (`tests/test_tenant_isolation.py:203`) is what catches a missing `enable_tenant_rls` call, in a different file, a long way from here.
- The round trip in both directions, last in the file, inside `try/finally: command.upgrade(cfg, "head")`.

**The ORM model is the second half of this migration and is not optional.** No model↔migration parity test exists anywhere in `backend/tests/`, so without `models/sos_alert.py` — `class SosAlert(StandardColumns, Base)`, every column declared explicitly — every backend line in D3 through D10 is an `AttributeError`. Migration + model are one atomic change (F36's D5, F57's D3, F34's D2).

### D9 — Five routes on F57's floor router, and **NOTHING is tightened** — which is itself a decision

| Method | Path | `allowed_roles` (effective) | Why |
|---|---|---|---|
| `GET` | `/manage/floor/sos` | all five | the app-level poll; rows filtered by D7's audience predicate |
| `POST` | `/manage/floor/sos` | all five | raise — first person, always for herself (D3) |
| `POST` | `/manage/floor/sos/{alert_id}/accept` | all five | permitted = target **or** elevated, refused as 404 (D4) |
| `POST` | `/manage/floor/sos/{alert_id}/resolve` | all five | permitted = raiser, acceptor **or** elevated, refused as 404 (D5) |
| `POST` | `/manage/floor/sos/{alert_id}/cancel` | all five | permitted = raiser **or** elevated, refused as 404 (D5) |

**Five new routes; eighteen on the router after F37.** Four of the five are mutating (`csrf.py:15` — `MUTATING_METHODS`), one is a GET; the router carries **fourteen** mutating routes and **four** GETs in total. Those figures drive `FLOOR_ROUTES` (thirteen rows → **eighteen**), which is exported to `test_staff_role_gating.py` and powers the 401 walk, the wiring walk and the `no-store` parametrization — **so a count sized from prose rather than from this table is a first-run CI red on the one table a reviewer would otherwise trust.**

**F36 tightened four routes; F37 tightens none, and the criterion is F36's D8 verbatim.** A per-route `RoleGate` can express only a **pure role predicate** — one that depends on nothing about the target. Every rule in this feature depends on the row: the raise is first-person (no target rule at all), and accept/resolve/cancel each read `target_staff_user_id`, `raised_by` or `accepted_by` before they can decide. There is no gate that can say *"the person this alert names"*. So `FLOOR_OPEN` grows from **nine to fourteen**, all five paths added as **route templates** (never concrete urls — the walkers read `route.path`, and mixing the two spellings is a CI round trip, `test_staff_role_gating.py:93-96`), and the **four tightened paths stay deliberately absent**, which is what keeps the table's shipped comment (*"the exhaustive list of what they may reach"*, `:84`) true.

⚠ **The intersection classifier must not be touched.** `test_the_floor_roles_reach_exactly_the_floor_routes` classifies on `frozenset.intersection(*role_sets)` and F57's Risk 1 says in writing that a reviewer facing a red here *"must fix the route, never relax the quantifier"*. F37 adds only untightened routes, so it should not go red at all — and if it does, the cause is a gate somebody added by accident.

**Every path's second segment is `floor`, so `vite.config.ts` needs no edit and `test_spa_serving.py` stays green with no change.** That is not an accident and it is not free to get wrong: `test_the_manage_dev_proxy_names_every_manage_api_segment` (`:381-408`) asserts **set equality** between the live route table's second segments and the `^/manage/(…)` alternation, and a mismatch breaks **only a developer's machine** — production, CI and the whole suite stay green while the SPA shell is served where the API should be. It has bitten this repo twice (F52, then F57's plan). **Mounting at `/manage/sos` would have cost the edit; `/manage/floor/sos` costs nothing.** ⚠ Note the two are independent facts: the **URL** says `floor` because the router does; the **console placement** is app-level (D11) and would be identical either way.

**No rate limiter** (no `/manage` router carries one — `floor/router.py:72-76`). The four new mutating verbs are CSRF-fenced by `CsrfOriginMiddleware` **by method rather than by path list** (`csrf.py:15,48`), so they are fenced by construction; the one new GET is not, and its protection is the session cookie and the role gate alone.

### D10 — The alerts payload: one statement, five LEFT JOINs, and **NO customer's name**

```jsonc
// GET /manage/floor/sos
{
  "alerts": [
    {
      "id": "8b21…",
      "status": "open",                        // open | accepted | resolved | cancelled
      "raised_by": "0f5f…",
      "raised_by_name": "דנה",                 // null only if her staff row is gone
      "target_staff_user_id": null,            // null = the shift-manager ROLE
      "target_name": null,                     // null when the target is the role
      "room_label": "חדר 2",                    // null = no room on this page
      "note": "צריך סיכות",                     // null = she typed nothing
      "accepted_by": null,
      "accepted_by_name": null,
      "acknowledged_at": null,
      "created_at": "2026-08-03T09:12:00Z",
      "escalated": false,                      // DERIVED: open, unacked, > 30s (D6)
      "stalled": false,                        // DERIVED: accepted, unresolved, > 2min (D6)
      "for_me": true                           // DERIVED: this is calling YOU now (D7)
    }
  ],
  // The server's own instant at serialisation — the SAME field F36 put on
  // /manage/floor, for the same reason, and the anchor BOTH `escalated` and the
  // console's elapsed line are computed against.
  "server_now": "2026-08-03T09:12:44Z"
}
```

**⚠ THERE IS NO `client_label` ON THIS PAYLOAD, AND ITS ABSENCE IS THE FEATURE'S LARGEST PRIVACY DECISION.**

F36 put a customer's name on `/manage/floor` and had to rewrite three shipped comments to do it honestly (its Conflict 2). That payload is fetched **only while the console is on the board or the floor section**, by a component that unmounts on navigation. **This one is fetched on every section, every few seconds, for the whole shift** — the settings screen, the catalog, the gateway page. Putting a bride's name on it would mean the console holds a customer's name in memory and on the wire while nobody is looking at a floor at all.

And it buys nothing. The responder needs to know **who is calling** and **which curtain**. She does not need the bride's name to walk to room 2; F36's justification for the label was *"she has been called to room 3 and must know who is in it"*, and an SOS **already names the person who is in it** — the colleague who raised it. So:

> **The SOS payload carries staff names and a room label. It carries no customer datum of any kind, and the app-level poll is exactly why.**

That sentence goes in `app/floor/schemas.py` beside the new models, in the same register as the three comments F36 rewrote, so the next feature to extend this payload meets the reason rather than the absence.

**The read is ONE statement with five LEFT JOINs**, and every predicate is written out because this schema has no FK constraints:

| Join | Predicate | Why exactly this |
|---|---|---|
| `sos_alerts` (driving) | `tenant_id = :t AND deleted_at IS NULL AND status IN ('open','accepted')` + D7's audience clause | matches `idx_sos_alerts_live`'s predicate exactly, so the planner uses it |
| → `staff_users` (raiser) | `tenant_id = :t AND id = raised_by` — **no `deleted_at` filter** | F36's ghost-holder rule: a staffer removed mid-page still has a name, and an alert that cannot say who called is worse than one naming a departed colleague |
| → `staff_users` (target) | `tenant_id = :t AND id = target_staff_user_id` — no `deleted_at` filter | same |
| → `staff_users` (acceptor) | `tenant_id = :t AND id = accepted_by` — no `deleted_at` filter | same; and it is what makes D4's `details`-less branch rare rather than routine |
| → `fitting_room_assignments` | `tenant_id = :t AND id = fitting_room_assignment_id AND deleted_at IS NULL` — **no `released_at` filter** | the fitting can end while the page is open, and the alert must still say where |
| → `fitting_rooms` | `tenant_id = :t AND id = assignment.fitting_room_id` — **NO `deleted_at` filter** | ⚠ **F36's Risk 1(c), decided there and handed here verbatim.** Once the assignment is released the owner may soft-delete the room, and D11's rooms read starts from `deleted_at IS NULL`. Rendering a since-deleted room's label is deliberate and safe: **a room label is not personal data**, so D9's no-snapshot rule does not reach it, and F36's `FITTING_ROOM_DELETED` makes the mirror-image argument (*"an id alone records that something was removed and cannot say what"*) |

All five are **LEFT**, so an alert whose every pointer has been swept still renders — with `raised_by_name: null`, `room_label: null`, and a card that says so.

**Every mutation answers the same `SosAlert`** the poll's `alerts[]` elements carry, so the console patches one card in place from the server's own row and cannot disagree with itself (F57's D7 contract, F36's D6 step 6). **The one exception is the raise**, which answers `{alert, rerouted}` — and the asymmetry is justified rather than convenient: **`rerouted` is a fact about *this request*, not about the row.** Nobody reading the alert later can know whether `target_staff_user_id IS NULL` means "she asked for the shift manager" or "she asked for Dana and Dana was logged out", which is precisely why it cannot live on the row's shape and why the audit row carries the requested target instead (D13). *Declined: letting the console infer it by comparing what it sent with what came back — the inference is correct today and is exactly the kind of implicit contract that survives one refactor.*

### D11 — The app-level poll: where it lives, its two tick rates, three loops on one screen, and the honest cost

**It lives in `apps/manage/src/lib/sos.tsx` as `SosProvider` + `useSos()`, mounted inside `App`'s signed-in return.** ⚠ **A provider rather than state in `App`, and the forcing constraint is mechanical, not architectural:** `App` early-returns for `!bootstrapped` and for `staff === null` (`App.tsx:146-156`), so a hook called after those returns is a rules-of-hooks violation — and `frontend/.oxlintrc.json` enables `react/rules-of-hooks: error` precisely so that is a lint failure rather than a runtime one. A provider is a component boundary, so it may be mounted **conditionally** where a hook may not. `ToastProvider` from `@boutique/ui` is the shipped precedent for exactly this shape and is already wrapped around the same tree (`App.tsx:187`).

Two consumers, which is the whole reason a provider exists at all rather than one component owning everything: **`SosOverlay`** (rendered by `App`, before `ConsoleShell`) and **`SosCentre`** (a child of `FloorPanel`, D16). One poll, one alert list, one freshness claim.

**Tick rate: 5 000 ms with no alert, 2 000 ms with any alert on the payload.** Not `for_me` — **any** alert in `{open, accepted}`, because the raiser is watching for the accept and the acceptor is watching for the resolve, and one condition that covers all three roles cannot be got wrong. The ~2-second tick while an alert is open is **pre-authorised** in the e7 Risks (*"the SOS feed is one row, so it may poll faster than the board's 5 seconds"*) and restated in the ruling.

**⚠ THE GAP FOR THE IMMINENT RE-ARM IS DERIVED FROM THE RESPONSE, NEVER FROM REACT STATE, AND GETTING THIS WRONG COSTS A SILENT FIVE-SECOND HOLE AT THE WORST MOMENT.** The shipped tick shape this provider copies calls `poll.succeeded()` inside the fetch's `try` (`FloorPanel.tsx:174`) and `poll.reschedule()` in the `.finally()` (`:192`) — **both in the same microtask chain as the response**, i.e. before React commits the `setAlerts` that would flip a state-derived `intervalMs` from 5 000 to 2 000, and long before the passive effect that would mirror it into a ref. So a state-derived gap makes **the tick that first observes an alert re-arm at 5 000 ms**, and the 2-second cadence starts only on the tick after — precisely when the raiser is waiting to see who is coming. Worse, the obvious test (*"changing `intervalMs` between ticks takes effect on the next re-arm"*) re-renders the hook with a new prop and *then* ticks, so it goes **green over the broken behaviour** — the same shape as F57's vacuous focus test.

**So `intervalMs` is passed as a FUNCTION** (D12): `intervalMs: () => (hasLiveAlertRef.current ? 2_000 : 5_000)`, read by `usePoll` **at arm time** inside `schedule()` / `succeeded()`. The provider sets `hasLiveAlertRef.current` in the **same `.then()` that calls `setAlerts`, before `poll.succeeded()`** — one ref write on the line above a call that already exists. **Named test, and it must drive ONE REAL TICK** whose response carries the first alert and assert the next timer fires at 2 000 ms; **mutation: revert to a state-derived gap, and it must go red** (the prop-rerender-then-tick shape does not, which is the point).

**⚠ THE IDLE STOP IS DISABLED ON THIS LOOP, AND THAT IS THE MOST DANGEROUS THING IN THIS DOCUMENT IF IT IS GOT WRONG.** `usePoll`'s `IDLE_STOP_MS` is ten minutes of no `pointerdown`/`keydown`/`focusin`/`scroll`. For F34's wall board that is exactly right. For an emergency receiver it is lethal: a phone in a staffer's apron pocket, untouched for eleven minutes, would **silently stop receiving pages** — and silence is the worst property an emergency channel can have. So `SosProvider` passes `idleStopMs: null` (D12), and the justification is written where the flag is set:

- **SC 2.2.2 does not apply in the idle state, because there is no content.** The criterion governs *auto-updating information presented in parallel with other content*; with no alert this component renders `null`. There is nothing to pause, stop or hide.
- **In the alert state the overlay's content does not auto-update.** One card per alert, static text, an **absolute** time («מאז 11:20») and **no countdown and no live elapsed counter** — D15 forbids both, which is what keeps this true rather than merely claimed.
- **The "hide" mechanism SC 2.2.2 asks for exists and is the dismiss control** (D15), plus Esc.
- The `document.hidden` pause inside `usePoll` still applies and is **kept deliberately** — see Risk 1, which is where the in-app-only ceiling gets written down instead of discovered.

**Why not fold SOS onto `/manage/floor`, four reasons and each is sufficient:**

1. **The overlay must render over any section** (the ruling). `FloorPanel` is mounted on 2 of the console's 13 sections.
2. **It would put a customer's name on an app-level loop.** The floor payload carries `client_label` (F36's D9); folding SOS onto it means the settings screen fetches a bride's name every five seconds. That inverts the argument F36 spent its longest section making.
3. **It would require lifting floor state above `FloorPanel`**, which F57's D11 forbids in writing and F36's D15 re-states.
4. **The two need different tick rates and different idle behaviour.** One loop cannot be both 5s-fixed-and-idle-stopping and 5s/2s-and-never-stopping.

**Three loops on the board screen, and the coexistence rules are explicit:**

| Screen | Loops | Pause controls |
|---|---|---|
| `board` (owner, shift_manager) | `BoardSection` 5s · `FloorPanel` 5s · **SOS 5s/2s** | two (board, floor) — **the SOS loop adds none** |
| `floor` (the three floor roles) | `FloorPanel` 5s · **SOS 5s/2s** | one (floor) |
| the other eleven sections | **SOS 5s/2s** — where the shipped product polls **zero** | none |

**⚠ `FloorPanel`'s pause control must not lie.** It is named «השהיה — עדכון הצוות» and it governs the region it sits in — which after D16 contains the SOS-centre panel, fed by a loop that pause does not stop. So **`SosCentre` receives `paused` and freezes its rendered list from a snapshot ref while paused**, exactly as `RoomsPanel` already receives `paused` for its copy decisions. Three lines, and it makes the control's claim true. **The overlay keeps rising while the board is paused, and that is the safety property**: pausing a *view* must never disable the *channel*. Named test + mutation (Testing).

**⚠ ONE EXEMPTION FROM THE FREEZE: an alert THIS DEVICE just raised.** Both raise entry points live on the floor section (D16), the overlay never rises for the raiser's own page (D7), and a frozen list will not add it — so a staffer who paused the board and then raised would see her own new alert **nowhere**, with a transient `sos.raisedCue` as her only feedback. The freeze exists so the pause control does not lie about **the poll**; a row this device created one tap ago is not the poll moving underneath her. One line — the raise's response alert is merged into the frozen snapshot — plus a `SosCentre.test.tsx` block.

**The per-device cost, derived by F34's D3 method and NOT measured** (citations `tenancy/middleware.py:74`, `db/tenant.py:25-29`, `db/session.py:59`):

| Per SOS tick, per device | Count | Where |
|---|---|---|
| Sessions opened | **3** | `tenants.by_slug` (its own session) → `resolve_session` → the alerts read |
| `set_config` + BEGIN/COMMIT | **2** each | the two tenant-scoped sessions |
| `SELECT 1` on pool checkout | **3** | `pool_pre_ping=True` |
| Business SQL | **4** | session ×2, alerts ×1, `tenants.by_slug` ×1 |
| **Total** | **~6 statements, ~11 round trips, 3 pool checkouts** | identical to F57's floor tick, because the alerts read is ONE statement |

So, adding to F36's number honestly rather than restating it:

| Screen | Before F37 | After F37, idle | After F37, alert open (2s) |
|---|---|---|---|
| `board` | ~30 / 5 s | board 17 + floor 13 + **SOS 11** = **~41** | 17 + 13 + **~27** = **~57** |
| `floor` | ~13 / 5 s | floor 13 + **SOS 11** = **~24** | 13 + **~27** = **~40** |
| the other eleven | **0** | **~11** | **~27** |

**F29 must be handed three things, not left to discover them** (Risk 4): the ~41/~57 board figure; the fact that **eleven sections that polled nothing now poll**; and that `tenants.by_slug` — the uncached-per-request lever `tenancy/resolver.py:8-9` already assigns to F29 — is now paid **three times per beat** on the board screen instead of twice. Nothing throttles it server-side; F34's D3 declines a read limiter (*"there is no attacker, only loyal clients"*) and that reasoning still holds, so the client backoff is the only ceiling — **and this loop has no idle stop**, which is the one place the ceiling is genuinely lower than before.

### D12 — `usePoll` gains **two optional fields**, and the acceptance rule is F36's

```ts
export interface PollOptions {
  run: (generation: number) => TickOutcome;
  onIdleStop?: () => void;
  /** Base gap between ticks. A NUMBER or a FUNCTION; the function form is read
   *  AT ARM TIME inside schedule()/succeeded(), which is the only shape that
   *  can switch the gap on the tick that observes the change rather than the
   *  one after (D11 — a state-derived gap costs a five-second hole, and the
   *  obvious test passes over it). The SOS loop runs at 5s idle and 2s while an
   *  alert is open. Defaults to POLL_INTERVAL_MS, which is what keeps every
   *  shipped caller byte-identical. */
  intervalMs?: number | (() => number);
  /** `null` DISABLES the idle stop. Exactly one caller passes it and its
   *  justification is at the call site: an emergency receiver that stops
   *  receiving after ten idle minutes is not degraded, it is dead — and dead
   *  silently. Defaults to IDLE_STOP_MS. */
  idleStopMs?: number | null;
}
```

The change is **eight lines**: one `intervalRef` and one **`idleGapRef`** mirrored in the existing `useEffect(() => { runRef.current = run; … })` block (no new effect), `backoffRef` initialised from the resolved `intervalMs`, `succeeded()` and `resume()` resetting to the **resolved** `intervalRef.current` (call it if it is a function) instead of the constant, and `armIdle()` returning early when the gap is `null`. `MAX_BACKOFF_MS` is unchanged — a 2-second base still backs off to sixty.

⚠ **`idleGapRef`, NOT `idleRef` — `idleRef` already exists** (`usePoll.ts:118`) and holds the idle **timeout handle** (`useRef<ReturnType<typeof setTimeout> | null>`), read and written by `clearIdle()` (`:140-145`) and `armIdle()` (`:165-177`). A second declaration is an immediate redeclaration error; the near-miss — reusing the name for the gap — silently breaks `clearIdle`.

⚠ **The `null` early return goes AFTER the existing `clearIdle()` call at `usePoll.ts:166`, never before.** `armIdle()` opens with `clearIdle()`; return above it and a timer armed under a numeric gap survives a switch to `null`, so the loop still idle-stops after the caller disabled the stop. **Named test: arm under a numeric `idleStopMs`, rerender with `null`, advance past `IDLE_STOP_MS`, assert the loop is still running.**

> **Acceptance rule, F36's D15 applied one level down: `BoardSection.test.tsx` and `FloorPanel.test.tsx` must pass with ZERO EDITS after this change, and `usePoll`'s own shipped assertions likewise.** They are the only thing that can tell a faithful extension from a subtly different one. New `it(` blocks are added freely; **an edit to an existing expectation means the change is wrong.** `git diff main -- frontend/apps/manage/src/lib/usePoll.ts` should be readable in one screen.

*Declined: a fifth hand-rolled loop for SOS.* It would forfeit F34's unmount fix, F57's StrictMode idempotence fix, the visibility pause, the backoff and the `{401,403}` terminal rule — the five things this hook exists to stop four builders re-deriving. F34's shipped note is explicit that *"Any later feature copying D4's mechanisms (F57, F37, F41, F59 all will) must copy this line with them"*; importing the hook is how F37 copies it.

*Declined: a constant 2-second tick.* 2.5× the requests on every console screen forever, to save two lines.

### D13 — Four `AuditAction` members, no migration, and the resolve carries the value it destroys

`audit_log.action` is plain `TEXT` with no CHECK (`0003_auth.py:71-79`) — the **eighth** block to rely on that fact (F15's seven, F34's two, F51's five, F57's two, F17's, F19's, F53's one, F36's four).

| Member | Value | Written by | `details` |
|---|---|---|---|
| `SOS_RAISED` | `sos_raised` | every raise | `{"alert": uuid, "requested_target": uuid\|null, "target": uuid\|null, "rerouted": bool, "assignment": uuid\|null}` |
| `SOS_ACCEPTED` | `sos_accepted` | an accept that wrote | `{"alert": uuid, "raised_by": uuid}` |
| `SOS_RESOLVED` | `sos_resolved` | a resolve that wrote | `{"alert": uuid, "from_status": "open"\|"accepted"}` |
| `SOS_CANCELLED` | `sos_cancelled` | a cancel that wrote | `{"alert": uuid}` |

`actor_id = actor.id`, `entity = str(alert_id)`, written in the same transaction before commit (F15's D2 shape). **A no-op writes no row** (F34's D8): a re-accept by the current owner, a second resolve, a resolve of an already-cancelled alert.

**`SOS_RAISED` carries `requested_target` AND `target`, and the pair is the whole point.** D3's reroute writes `NULL` into the column, destroying the only record of whom she actually tried to page — the `previous_break_started_at` argument (F57's D8) and the handover `from` argument (F36's D8), third instance. Without the pair the trail records that a page went to the shift manager and cannot say that Dana was meant to get it, which is the single most useful thing a pilot review could ask this table.

**`SOS_RESOLVED` carries `from_status`, ⚠ captured into a local BEFORE the writer runs** (D5). This is the fourth appearance of the identity-map trap in this repo and the only one where the destroyed value is a state rather than a timestamp.

**Declined `SOS_ESCALATED`.** There is no escalation event — escalation is a predicate over a row and a clock (D6), so there is no instant at which anything happens and no writer to hang an action on. Recording one from a read path would be a write on a read path, which is exactly what D6 rejects.

### D14 — Two new error codes, and the third and fourth `details` bodies in the product

| Condition | Status | Code | New? |
|---|---|---|---|
| No session / expired | 401 | `NOT_AUTHENTICATED` | no — app-wide |
| A role outside all five | 403 | `NOT_AUTHORIZED` | no — F31's generic body |
| Unknown / another tenant's alert · not visible to this caller · not permitted to accept, resolve or cancel | 404 | `NOT_FOUND` | no — `DomainNotFoundError`, `main.py:907-909` |
| Note too long · self-target | 400 | `VALIDATION_ERROR` | no — `DomainValidationError`, `main.py:901-905` |
| Body carries an unknown key (e.g. `raised_by`) | 400 | `VALIDATION_ERROR` | no — `ForbidExtraModel` |
| **Somebody else already accepted** (accept, and cancel-after-accept) | **409** | **`SOS_ALREADY_ACCEPTED`** | **YES** |
| **Already resolved or cancelled** (accept) | **409** | **`SOS_CLOSED`** | **YES** |
| Re-accept by the current owner · second resolve · resolve of a cancelled alert | **200** | — | not errors, by D4/D5 |
| Mutating request from a foreign origin | 403 | `CSRF_ORIGIN_MISMATCH` | no — `csrf.py:15-16,48` |
| Backend down / 5xx | — | — | no — backoff, not terminal |

`test_floor_api.py`'s `SPEC_ERROR_CODES` grows from **seven to nine** and stays asserted by set equality.

**Both errors subclass the shipped `_OccupiedError` pattern, and the shipped body helper is RENAMED rather than copied.** `_occupied_body` (`main.py:350-365`) already does exactly the right thing — copies a frozen module constant, adds `details` only when truthy, never mutates the shared dict (*"stamping `details` onto it would leak one boutique's staffer name into the next tenant's 409"*). It is private, it has two call sites, and F37 gives it two more with nothing to do with occupancy. **It becomes `_body_with_details`**: a one-line rename plus four call sites, no behaviour change, and it stops the product carrying two copies of six lines that must stay identical.

Likewise `floor/validation.py`'s `_OccupiedError` base is renamed **`_DetailedConflictError`** and keeps its whole docstring, including the load-bearing sentence that it is deliberately **not** a `DomainValidationError` subclass *"because Starlette resolves a handler by walking `type(exc).__mro__`"* — parenting a 409 onto the domain-400 base makes the shipped handler answer 400 and leaves the 409 handlers unreachable. `RoomOccupiedError` and `StaffOccupiedError` are unchanged subclasses; `SosAlreadyAcceptedError` and `SosClosedError` join them.

```jsonc
{ "error": { "code": "SOS_ALREADY_ACCEPTED",
             "message": "This SOS has already been accepted.",
             "details": { "staff_display_name": "דנה" } } }

// …and with nobody to name (D4): the key is ABSENT, never null.
{ "error": { "code": "SOS_ALREADY_ACCEPTED",
             "message": "This SOS has already been accepted." } }

{ "error": { "code": "SOS_CLOSED", "message": "This SOS is already closed." } }
```

**⚠ This fires F36's Risk 8, which named this PR as its trigger:** *"The `details` key is an extension of an error envelope every other body in the product treats as a two-field constant… That is fine if it stays deliberate and bad if it becomes the default — an error is not a response."* It stays deliberate here on the same three grounds F36 gave, restated for this feature: the **ruling requires** the losing accept to name the owner; the English `message` is never rendered for a mapped code (`StaffSection.tsx:18-23`, the shipped pattern); and a second `GET` to discover the owner would race the resolve it is trying to describe. The fast test asserting *every other body in `main.py` is unchanged* is widened by exactly two entries, and `SOS_CLOSED` deliberately **never** carries `details` — three of four codes with the key would be the drift Risk 8 warns about.

`ApiError` and `extractError` need **no change**: F36 already shipped `readonly details?: Record<string, string>` and the extraction (`api.ts:9-62`).

### D15 — **THE FOCUS AND ANNOUNCEMENT CONTRACT** for an overlay that appears unbidden — *the gate condition*

IS 5568 / WCAG 2.0 AA is **legally binding** here (pre-decided #38) and the e7 Risks make the screen-reader announcement a **gate condition, not a nicety**. axe must return **zero** violations **and axe is not the coverage**: it cannot see a focus move that never happened (this repo has shipped that four times — F56, F34, F57, and F36's stale-closure MAJOR), and it equally cannot see a focus move that **should not have happened**. This section is the whole answer and every clause below is a named test.

#### The shape: `role="alert"`, one per card, and no modality

The overlay is a `position: fixed; inset: 0` region rendered by `SosOverlay` as **the first element in `App`'s signed-in tree, before `<ConsoleShell>`**, so its controls precede every other focusable element in DOM order.

- **It is NOT a `<dialog>` and NOT `showModal()`.** A modal dialog moves focus into itself by definition, and `@boutique/ui`'s `Modal` is a native `<dialog>` that F36's three dialogs already use — stacking a second modal over an open one is undefined-ish across engines and would fight F36's shipped Esc handling.
- **It is NOT `inert` on the rest of the console.** `inert` moves focus **out** of the inert subtree, which is a focus steal by another name and would destroy a receptionist's half-typed phone number.
- **It is therefore visually blocking and interactively non-blocking**, and that asymmetry is the resolution of the two requirements that pull against each other. A pointer user's next tap lands on the overlay and she dismisses it in one tap with no state lost. A keyboard user's caret never moves and her form is intact. **Nobody loses work; nobody misses the alert.**
- **⚠ AND THE HAZARD THAT ASYMMETRY CREATES, named rather than left implicit: she is now typing into a field she cannot see.** `inset: 0` covers the viewport, so the receptionist whose half-typed phone number D15 exists to protect has a live caret, no visible input, no visible validation and no visible label. **The trade is taken deliberately** — the ruling says *full-screen red*, a band would be missable on a 375px phone held inside a curtain, and losing her keystrokes is worse than obscuring them for the few seconds it takes to dismiss or accept. **Recorded in writing rather than discovered**, and Risk 6 hands F58 «typing behind the overlay» as a **fourth** named case beside the three it already lists, because whether a real browser keeps the caret usable under a fixed overlay is exactly what jsdom cannot answer.
- **The red is `bg-danger` + `text-surface-raised`** — the pair the shipped error toast already uses (`packages/ui/src/components/Toast.tsx:46-48`), so the overlay inherits the product's one AA-checked red-on-light rather than inventing a red at build time. ⚠ **axe will not cover this**: its contrast rule computes against an element's own background and cannot see text in `main` obscured by a fixed sibling, so the token is named here instead of left to the mechanical pass.
- **Each alert card carries its own `role="alert"`** — implicit `aria-live="assertive"` + `aria-atomic="true"` — rather than one `role="alert"` wrapping the list. ⚠ With one wrapper, a second page arriving would re-announce **all** the cards (`aria-atomic`), so the seamstress hears about the emergency she already answered. With one per card, mounting announces exactly the new one. Keyed by `alert.id`, so a card that stays mounted across ticks is **never re-announced** — React skips an identical text update, so no `childList` mutation occurs inside the region (F34's F-7 hazard, avoided by construction rather than by a guard).
- **What is announced, in one atomic sentence:** who is calling, the room, and her note. «דנה קוראת לעזרה — חדר 2 — צריך סיכות».
- **⚠ THE `role="alert"` ELEMENT'S TEXT IS WRITE-ONCE, AND THE ESCALATION CLAUSE LIVES IN A SIBLING OUTSIDE IT.** `role="alert"` carries implicit `aria-live="assertive"` **and** implicit `aria-atomic="true"`, so **any** childList change inside the region re-announces the **entire** region, assertively, interrupting whatever the screen reader was saying. D15 built the per-card region specifically to stop `aria-atomic` re-announcing content the user already heard — and then putting «ללא מענה» inside that same region thirty seconds later would re-announce «דנה קוראת לעזרה — חדר 2 — צריך סיכות — ללא מענה», once per escalating card, for a fact that changes nothing about what she has to do. **So the announced sentence renders inside the `role="alert"` element and the escalation and stalled clauses render in a SIBLING node** — still visible words on the card (the colour rule below is untouched), just outside the live region. **AC16 is strengthened to: the `role="alert"` element's text content is byte-identical from mount to unmount, INCLUDING across the escalation transition. Mutation: move the clause inside the region, and it must go red.**

#### The focus rule, and the guard is the repo's own

> **MOVE A — arrival.** When the first rising alert appears, focus moves to that card's «אני מגיעה» control **if and only if `document.activeElement === document.body`.** Otherwise focus does not move at all.

That guard is not invented for this feature: it is the exact condition the shipped restore effects already use — `FloorPanel.tsx:258` (*"Guarded on document.body so it can never steal focus from wherever she moved it"*, `:250-257`) and `:307`, `RoomsPanel.tsx:262-272` (MOVE 6) and `:277-286` (MOVE 2). **F37 applies it to an arrival instead of a restore**, and the consequences are worth stating both ways:

- **⚠ Focus moves only when NOTHING HOLDS IT, which is a freshly loaded or reloaded tab — NOT "the common case on a shop floor".** An earlier draft claimed the latter and it is not true of a console anybody has touched: clicking a nav row or a `Button` leaves focus on that element, which is precisely why the four shipped restore effects exist and why `FloorPanel.tsx:246-250` has to explain that focus returns *only because* «@boutique/ui's Button is `disabled={disabled || loading}`, so the browser blurred it». **A board tablet loaded at 09:00 and untouched since IS on `<body>`, and there the emergency is one keypress from being accepted. A tablet in use is not, and there MOVE A does not fire at all** — `role="alert"` alone carries the announcement, and the Esc route below carries the reach. Both branches are real; only one of them is common, and which one depends on whether anybody has touched the screen.
- **The dangerous case is somebody typing**, and there focus does not move, the caret does not jump, no keystroke is lost — and the alert is **still announced**, because `role="alert"` interrupts a screen reader **without** taking focus. That is the whole reason the `alert` role exists and is why it, and not `alertdialog`, is correct here.
- **It also disposes of the return problem.** Since focus is only ever *taken from nowhere*, it only ever has to be *given back to nowhere*.

> **MOVE D — a mutation FAILED and its in-card alert appeared.** Focus moves to that alert **if and only if `document.activeElement` is inside that same card.** Otherwise it does not move at all.

⚠ **MOVE D is not optional padding: the state table uses it three times** (accept 409 `SOS_ALREADY_ACCEPTED`, accept 409 `SOS_CLOSED`, accept 404 — each *"focus into it"*), and an earlier draft defined only A, B and C, which left a fourth focus move with no rule, no guard, no AC and no mutation. The shipped analogue a builder will copy is `FloorPanel.tsx:265-292` (`cardAlertRef.current?.focus()`), which fires **unconditionally with no `document.body` guard** — correct *there*, because the panel's `Button` is `disabled={disabled||loading}` so the browser already blurred the control. **Copied into the overlay it becomes an unguarded focus move on an error path, in the one component whose whole premise is that it never moves focus uninvited**, and D15's own warning applies verbatim: *axe cannot see a focus move that should not have happened*. The in-card guard says: she tapped this card's accept control, `Button`'s disabled state blurred it, so focus is hers to reclaim — **but a 409 landing while she is typing behind the overlay must not pull her out.** **Mutation: remove the in-card guard, then assert focus does not leave a text input behind the overlay when a 409 lands** (AC15).

> **MOVE B — the overlay leaves while holding focus.** When the last rising alert is accepted or dismissed and the overlay unmounts, if `document.activeElement` was inside it, focus goes to `document.getElementById("console-main")` — the `<main id="console-main" tabIndex={-1}>` `ConsoleShell` already renders and the skip link already targets (`ConsoleShell.tsx:43,84`). **Never `<body>`.** F51's `isConnected` fallback shape, one shipped element, no new string, no new attribute.

> **MOVE C — a card leaves while holding focus, with other cards still up.** Two alerts, she accepts the first, the second is still rising: focus goes to the **next remaining card's** ack control. Same question F36's `departingTileHoldsFocus` asks, one card at a time; falls through to MOVE B when no card remains.

**Control order inside a card is «אני מגיעה» then «הסתרה», and that order is the design.** First in DOM is first reached by Tab — so once she is *in* the overlay, the default outcome of a keypress is *accepting the emergency*, not hiding it.

#### ⚠ THE KEYBOARD ROUTE IN, which MOVE A alone does not provide

**An alert announced perfectly to a user who cannot reach the ack control is not an accessible alert.** MOVE A deliberately does not move focus when something holds it, and Esc bound to the container fires only when focus is already inside — so for **the exact user this design protects**, someone mid-form in `main`, «אני מגיעה» sits behind a Shift+Tab run past every preceding focusable in her section plus the whole `ConsoleShell` chrome (SkipLink → logout → up to ten NAV rows → `<main id="console-main">`, `App.tsx:67-125`, `ConsoleShell.tsx:43,84`). Forward Tab is worse. *"First in DOM is first reached by Tab"* is true only in the `<body>` case — i.e. only in the case where focus moved anyway.

> **Esc from OUTSIDE the overlay MOVES FOCUS INTO the first rising card's «אני מגיעה». Esc from INSIDE keeps its meaning: dismiss.**

One document-level **capture** `keydown`, live only while at least one alert is rising, with **two guards**, and each guard preserves a shipped behaviour rather than being defensive padding:

- **`document.querySelector("dialog[open]") === null`** — this is what keeps F36's three shipped `<dialog>`s (and `SosRaiseDialog`) owning their own Esc (`Modal.tsx:38-44`'s `onCancel`). The container-only argument survives intact: with a dialog open, nothing is hijacked.
- **the event target is not a `<select>`** — `RoomsPanel`'s free-tile action row renders a bare `Select` **outside** any dialog, and Esc closing an open native dropdown is browser behaviour a capture listener would preempt. Two characters of condition; jsdom would never have caught it.

**AC: with focus in a text input, one Esc lands on the accept control and the input's value is unchanged; a second Esc dismisses; with a `Modal` open, Esc closes the Modal and the overlay is untouched. Mutation: delete the handler — the first assertion must go red.**

**Dismissal is per-device, in-memory, and changes nothing on the server.** The alert stays `open`, keeps appearing in the SOS-centre panel, keeps escalating, and comes back on reload — because if it is still open it is still an emergency. Nothing is sent and no column exists.

⚠ **BUT «dismissing hides a rendering, not a record» is only half true, and the missing half is a silent drop.** The claim that a dismissed alert *"keeps appearing in the SOS-centre panel"* is true of the **row** and false of the **delivery**: `SosCentre` is a child of `FloorPanel` (D16) and `FloorPanel` is mounted on **2 of 13 sections** (`App.tsx:207-215`, verified). **On the other eleven the dismiss set is the only state and there is no second surface.** Two consequences, both closed here:

1. **A dismissed card must be able to re-rise when the alert's delivery state changes.** The set is keyed on **`${alert.id}:${alert.escalated}:${alert.stalled}`**, not on the bare id. A role-targeted page is `for_me` for an elevated caller from t=0, so a shift manager can dismiss at t=2s — and with a bare id the card would still be hidden when `escalated` flips at t=30s and would **never re-rise**, defeating the safety net for the exact audience escalation targets. In a boutique with one shift manager on the floor that is the whole audience gone on one tap, before the net can fire. With the composite key, escalation (and D6's stall) re-rises the card **exactly once** each and a second dismiss silences it again. **AC + `SosOverlay.test.tsx`: dismiss at t<30s, tick with `escalated: true`, assert the card is back — mutation: revert the key to the bare id.**
2. **While the dismiss set holds any still-live alert, `SosOverlay` must NOT render `null`.** It renders one persistent 44×44 affordance carrying the live dismissed count — «קריאות עזרה · 2» — that re-opens the overlay. **This is the whole reason it works on the eleven sections that have no SOS centre**, and it is ~10 lines against a shift manager on `bookings` who dismissed one line to finish another and has removed her only view of a live emergency until she navigates to the floor or reloads. **Note the role-target route is the raise dialog's FIRST AND DEFAULT option (D16), so this is the common path, not an edge.** **AC: an alert dismissed on a non-floor section remains reachable without a reload. Mutation: delete the affordance — red.**

With both, **«never silently dropped» is preserved by construction** rather than by assertion, and the dismiss control is still the SC 2.2.2 "hide" mechanism for the one region that has content.

**⚠ Accept, resolve and dismiss issued FROM THE OVERLAY confirm through the shipped app-level toast, not through `FloorPanel`'s region.** Accept success removes the card and MOVE B parks focus on `<main id="console-main" tabIndex={-1}>` — an unlabelled container. On any section other than `board`/`floor` there is no `SosCentre` and therefore **no `role="status"` region at all**, so a shift manager who accepts an emergency from the catalog screen would get: the red overlay vanishes, focus jumps to the top of an unnamed main, and **nothing is announced or shown**. `ToastProvider` is already wrapped around the signed-in tree (`App.tsx:187`, verified) and renders `role="status"` for success and `role="alert"` for error (`Toast.tsx:38-50`) — an app-level polite region the product already ships. `SosOverlay` calls the shipped `useToast()`; **`SosCentre` keeps writing its own cues into `FloorPanel`'s region for actions taken there, unchanged.** Recorded so nobody consolidates them: **the app-level region is the toast, the panel region is `FloorPanel`'s, and they are different surfaces on different screens.** The "adds no second polite region" rule below is scoped to the floor board and does not reach the toast. **AC: an accept issued from a non-floor section produces a `role="status"` carrying `sos.acceptedCue`; mutation — delete the call, red.**

#### The rest of the a11y contract

- **Escalation is a WORD, never a colour and never a border.** «ללא מענה» renders as text on the card, in a **sibling node outside the `role="alert"` region** (above). ⚠ **The word is «ללא מענה» and NOT «ללא מענה כבר 30 שניות»**, because `escalated` is a boolean with no upper bound: a page ignored for four minutes would render a flat "30 seconds" to the shift manager deciding whether to walk or run, and in `SosCentre` it would sit beside `elapsedLine`'s «זה עתה» at t=31s and beside a climbing minute count from t=61s — the one surface where duration drives triage carrying the one string guaranteed to be wrong. **The card already carries «מאז 11:20» for the when and `SosCentre` already carries `elapsedLine` for the how-long.** This also removes the literal 30 from the client entirely, which strengthens D17's argument for not mirroring `ESCALATION_AFTER` through `test_frontend_constant_parity.py`. F51's shipped rule (*"The WORD carries the role; the colour never does"*, `StaffSection.tsx:312`) and `FloorPanel.tsx:554` (*"The WORD carries the state; the colour never does"*). The overlay's red background is not information — it is emphasis over information that is already words.
- **No countdown, no live elapsed counter, anywhere in the overlay.** The raise time renders as an **absolute** instant through `jerusalemTime` — «מאז 11:20», `FloorPanel.tsx:705-716`'s shape, which never subtracts and is immune to a boutique tablet's clock drift. A ticking counter would be auto-updating content inside a `role="alert"`, would re-announce on some screen readers, and would drag SC 2.2.2 back onto a region whose whole D11 argument is that it has nothing to pause.
- **`<bdi dir="ltr">` around every numeric run** (times, the escalation seconds), **bare `<bdi>`** around Hebrew free text (staff names, room labels, the note) — forcing LTR on a Hebrew name reverses its words. **No truncation and no ellipsis on a name, a room label or a note, ever.**
- **44×44 minimum on both overlay controls, visible focus ring, `prefers-reduced-motion` respected** — the overlay appears, it does not animate in; no pulse, no flash, no shimmer. An animated emergency is a vestibular trigger and a distraction from reading it.
- **`aria-hidden` is set on nothing.** The console behind the overlay is still there for a screen reader, deliberately — she may be mid-task and the alert is an interruption, not a replacement.
- **The SOS-centre panel writes into `FloorPanel`'s existing `role="status"` cue and adds no second polite region** (D16). The overlay's `role="alert"` is assertive and event-driven; the panel's `role="status"` is polite and user-initiated. **Two regions of different politeness for different purposes is correct ARIA**, and it is the only place in this console where both exist — stated so nobody "consolidates" them.
- **The poll never writes into either region.** F34's D11, verbatim and non-negotiable. A card mounting is not the poll writing into a region — it is new content arriving, which is exactly what `role="alert"` is for.

⚠ **Every one of MOVE A, B, C and D must be mutation-checked**, and so must the Esc route-in and the dismiss key. F57's shipped note records that its own success-path focus test was **VACUOUS** — jsdom does not blur a disabled element, so the entire restore effect could be deleted with the suite green. **A test that passes with its mechanism removed is not a test**, and the named mutations are in the Testing table.

### D16 — The SOS-centre panel, and the two raise entry points

**`SosCentre` is a CHILD of `FloorPanel`**, rendered **above** `RoomsPanel` — an active emergency outranks a room list — and it is a child for three reasons, each of which also rules out the alternatives:

1. It needs the **staff list** for the raise dialog's target `Select`, and `FloorPanel` already holds it. A sibling would need a second source for a list the floor payload already carries.
2. It needs **`paused`**, so `FloorPanel`'s pause control does not lie (D11).
3. It uses `FloorPanel`'s **one** `role="status"` cue and its **one** SC 2.2.2 control, so the board gains no third pause button — F36's D15 argument (*"two is the answer rather than a defect… three would start to be a defect"*).

It takes its **alerts from `useSos()`**, not from a prop, which is the one place this feature deliberately reaches past `FloorPanel` — the alerts belong to the app-level poll and there is exactly one of them.

**Rendered always, including with no alerts**, because it carries the second raise entry point. Empty state: one line + the «קריאה לעזרה» button. Populated: one row per alert (raiser, room, note, elapsed via F36's shipped `elapsedLine`, and the status word) with the controls the caller may actually use.

**Which control EXISTS is the rendered form of the permission rules** — F57's shipped comment (`FloorPanel.tsx:639-644`), carried across again because a 403 is **terminal for the whole floor screen** (`usePoll.terminalOf` → `"access"`, `FloorPanel.tsx:441-458` clears every card) and for the three floor roles that is the entire product going dark:

| Control | Rendered only when |
|---|---|
| «אני מגיעה» (accept) | `alert.status === "open" && (alert.target_staff_user_id === selfId \|\| ELEVATED.has(role))` |
| «נפתר» (resolve) | `alert.raised_by === selfId \|\| alert.accepted_by === selfId \|\| ELEVATED.has(role)` |
| «ביטול» (cancel) | `alert.status === "open" && (alert.raised_by === selfId \|\| ELEVATED.has(role))` |

**No disabled buttons, no lock glyphs — absence.** An AC and a `SosCentre.test.tsx` block assert each is absent for a seamstress on somebody else's alert and present for an owner.

**Two raise entry points, one dialog.**

- **On a room card** (the ruling: *"the RAISE control is reachable from a room card"*): `RoomsPanel`'s occupied tile gains «קריאה לעזרה», rendered **only when `assignment.staff_user_id === selfId`** — the tile of the room she is standing in, which is what prefills `fitting_room_assignment_id`. Not on a colleague's tile: raising on somebody else's behalf is not a thing (D3).
- **In the SOS centre**: always available, to any of the five, with no assignment — for a staffer who is not in a room at all.

Both open **`SosRaiseDialog`**, whose open-state `FloorPanel` owns (it is the common parent of both triggers) and which is the shipped `@boutique/ui` `Modal`. Inside: a `Select` of the target — **«מנהלת המשמרת» first and default** (value `""` → `null`), then every other live staffer by name, with F36's shipped hint shape for a colleague on a break («{{name}} — בהפסקה», `rooms.handoverOnBreak`'s pattern) — an `Input` for the note, and «שליחת הקריאה». Herself is excluded from the list (D3 refuses a self-target with a 400; excluding it prevents the 400 rather than explaining it, which is F36's `RoomHandoverDialog` argument).

**The controls are the shipped ones, named — not "a native `<select>`".** `Select` from `@boutique/ui` requires a `label: string`, wires `useId()` → `htmlFor`, `aria-invalid`, `aria-describedby` and `focusRing`, and its own comment already carries the decision (*"Native `<select>` — no custom dropdown in v1 (a11y cost not worth it)"*). Written as "a native `<select>`" a builder loses the label association and the focus ring on a legally binding surface, **and axe sees the missing label but not the missing ring** — F36's D16, same sentence, same reason.

**⚠ ON A REROUTED RAISE THE DIALOG DOES NOT CLOSE.** The ruling requires that when a named colleague is unreachable the raiser is told **on screen before she puts the phone down** — and delivering that once, as a transient polite cue written into `FloorPanel`'s single `role="status"` `<p>` (`FloorPanel.tsx:510-520`, whose text the next cue overwrites) **at the exact moment a `<dialog>` closes and focus moves**, is the classic case assistive tech drops or defers. It is also unrecoverable: `rerouted` is deliberately a fact about the **request** and not about the row (D10), so no `SosCentre` row can ever show it. Miss the cue and she believes Dana was paged, Dana was never paged, and **nothing on any screen will ever say otherwise.** So: on `rerouted === true` the shipped `Modal` **stays open**, its body is replaced with «{{name}} לא מחוברת עכשיו. הקריאה עברה למנהלת המשמרת.» and one «הבנתי» that closes it — **an explicit acknowledgement rather than an announcement, which is the correct interaction weight for the one message the ruling mandates.** On `rerouted === false` it closes normally. **AC + mutation: close unconditionally and it must go red.**

**⚠ THE RAISE DIALOG'S FAILURE STATE, which an earlier draft did not have at all.** The enumerated states covered open, loaded, empty, typed, over-length, sending, rerouted, self-target, released-assignment, overlay-rises and cancelled — and **no state for «the request did not complete»**: a 5xx, a dropped connection, a boutique wifi blackspot in a fitting room, which is the single most likely real-world failure of a phone held inside a curtain. (D14's *"Backend down / 5xx → backoff, not terminal"* row is about the **poll**, not a mutation.) With no key the builder falls through to `errorMessage()`'s `FALLBACK_ERROR_MESSAGE` — «אירעה שגיאה בלתי צפויה. נסי שוב.» (`api.ts:7`, verified) — **on the one screen in the product where «try again» is the wrong instruction and «open the curtain and shout» is the right one.** So: **`sos.error.raiseFailed`** = «הקריאה לא נרשמה. נסי שוב — או קראי בקול.» (⚠ worded «נרשמה» because «נשלחה» trips the `/נשלח|תישלח|בדרך/` ban). **The dialog stays open with the note preserved, so a retry costs one tap** — and a retry may create a duplicate, which D2 already rules noise rather than corruption. **AC + a `SosRaiseDialog.test.tsx` block for a rejected send.**

**Dialog focus return**: F36's contract in **shape**, ⚠ **but NOT by reusing `RoomsPanel`'s effect — that mechanism cannot reach a dialog `FloorPanel` owns.** `RoomsPanel.tsx:307-330` (MOVE 4) is `useEffect(…, [openDialog])` reading `dialogTriggerRef` (`:160`), which `openFrom` (`:558-562`) sets from `event.currentTarget`, and it is keyed on **`RoomsPanel`'s own `openDialog` state** (`:144`) — all verified against shipped code. With the open-state in `FloorPanel`, `RoomsPanel`'s `openDialog` never changes, **the effect never runs, the native `<dialog>`'s own return has no target, and focus drops to `<body>` for something the user did** — the exact bug this repo has shipped four times, on the surface D15 declares a gate condition and on which IS 5568 / WCAG 2.0 AA is legally binding. So, three lines instead of a citation:

- the tile's prop is **`onRaise?: (assignmentId: string, trigger: HTMLButtonElement) => void`** and the tile's handler passes `event.currentTarget`;
- **`FloorPanel` stores it in its own `sosTriggerRef`** and runs the MOVE-4 shape in an effect keyed on **`FloorPanel`'s own** dialog state: `document.activeElement === document.body` guard → `trigger.isConnected ? trigger.focus() : headingRef.current?.focus()`;
- **the fallback is `FloorPanel`'s `<h2 ref={headingRef} tabIndex={-1}>` (`FloorPanel.tsx:435-439`, verified), not `RoomsPanel`'s `<h3>`** — the heading actually in scope; **never `<body>`**;
- **`SosRaiseDialog.test.tsx` covers the tile-released-underneath case. Mutation: delete the `isConnected` branch and focus goes nowhere.**

⚠ **And the collision that is new here: the SOS overlay may rise while the raise dialog is open.** MOVE A's `document.activeElement === document.body` guard resolves it with no extra code — focus is inside the dialog, so the overlay does not take it — but it must be **asserted**, because "the guard happens to cover it" is exactly the kind of accidental correctness that a later refactor deletes.

### D17 — i18n: a new `sos.*` namespace, Hebrew only, `ar` untranslated — and **«בדרך» is banned**

New keys in `apps/manage/src/i18n/he.ts` **and** `ar.ts`, with the approved Hebrew standing in untranslated in `ar.ts` — Interview Q3, pre-decided #47, the 2026-07-31 languages ruling, and `ar.ts`'s own mechanics (**never** empty strings; `lng` and `fallbackLng` stay `"he"`; no switcher). Flat dotted keys, the shipped `rooms.*` / `floor.*` shape.

⚠ **`i18n.test.ts:558-561` bans `/נשלח|תישלח|בדרך/` across every Hebrew value in the bundle, and «בדרך» is the natural Hebrew for "on my way" — i.e. for the single most important button in this feature.** The guard is right and stays: it exists so no string in this console ever promises a message the product did not send, and «בדרך» reads as *en route* in exactly the sense the guard forbids elsewhere. **Resolved by wording, not by an exception:**

| Key | Hebrew |
|---|---|
| `sos.accept` | «אני מגיעה» — ⚠ **NOT «אני בדרך»**, which trips the global ban |
| `sos.acceptAria` | «אני מגיעה — קריאה מ{{name}}» |
| `sos.acceptedBy` | «{{name}} מגיעה.» — the raiser's answer, and the same word |
| `sos.acceptedByUnknown` | «מישהי כבר מגיעה.» |
| `sos.raise` | «קריאה לעזרה» |
| `sos.raiseAria` | «קריאה לעזרה — {{room}}» |
| `sos.title` | «קריאה לעזרה» |
| `sos.calling` | «{{name}} קוראת לעזרה» |
| `sos.room` | ⚠ **no interpolated sentence** — the boutique's own label already contains «חדר», so «בחדר {{room}}» renders «בחדר חדר 2». The bare label in a `<bdi>` beside a labelled prefix, `FloorPanel.tsx:675-696`'s shipped three-fragment rule |
| `sos.roomA11yPrefix` | «מיקום» — ⚠ **DC-4, and it is a LABEL and not a value.** The room label is rendered bare (above), and ARIA prohibits naming `role=paragraph`, so the em-dash-value-last shape used elsewhere is unavailable and an `aria-label` on the `<p>` would ship a name nothing reads. A `<span className="sr-only">` INSIDE the `role="alert"` region, before the `<bdi>`, so the atomic utterance parses when the label is bare («2») |
| `sos.noRoom` | «לא בחדר מדידה» |
| `sos.escalated` | «ללא מענה» — ⚠ **NOT «ללא מענה כבר 30 שניות»**: `escalated` is an unbounded boolean, so a four-minute-old page would state a flat "30 seconds", and in `SosCentre` it would sit beside `elapsedLine`'s «זה עתה» at t=31s (D15). The card carries «מאז 11:20» for the when and `elapsedLine` for the how-long |
| `sos.stalled` | «אין תזוזה מאז שאושרה» — D6's second silence, same rule: a word, no number |
| `sos.since` | «מאז {{time}}» |
| `sos.dismiss` | «הסתרה» |
| `sos.dismissAria` | «הסתרת ההתראה — קריאה מ{{name}}» |
| `sos.resolve` | «נפתר» |
| `sos.cancel` | «ביטול הקריאה» |
| `sos.targetPick` | «למי לקרוא» — a `Select` **label**, not a placeholder |
| `sos.targetManager` | «מנהלת המשמרת» |
| `sos.targetOnBreak` | «{{name}} — בהפסקה» |
| `sos.notePick` | «מה צריך» — an `Input` **label** |
| `sos.send` | «שליחת הקריאה» |
| `sos.raisedCue` | «הקריאה נרשמה.» — ⚠ not «הקריאה נשלחה», which trips the ban |
| `sos.rerouted` | «{{name}} לא מחוברת עכשיו. הקריאה עברה למנהלת המשמרת.» — ⚠ **the raise dialog's BODY on a rerouted raise, not a transient cue** (D16) |
| `sos.reroutedAck` | «הבנתי» — the one control that closes a rerouted dialog |
| `sos.error.raiseFailed` | «הקריאה לא נרשמה. נסי שוב — או קראי בקול.» — ⚠ «נרשמה», never «נשלחה» (the ban). **The only string in this console that names the manual fallback out loud**, because on this one screen «נסי שוב» alone is the wrong instruction (D16) |
| `sos.channelDown` | «ערוץ הקריאות אינו פעיל.» — the persistent strip on a terminal-`access` or badly-backed-off poll (D15). ⚠ It is the ONLY app-level surface, so it is the only thing that can say this on the eleven sections with no panel |
| `sos.channelReload` | «רענון» — reuse `floor.reload`'s word, its own key because the strip renders where `floor.*` does not |
| `sos.dismissedCount` | «קריאות עזרה · {{count}}» — the persistent re-open affordance while the dismiss set holds a live alert (D15) |
| `sos.centreHeading` | «קריאות עזרה» |
| `sos.centreEmpty` | «אין עכשיו קריאות פתוחות.» |
| `sos.statusOpen` / `sos.statusAccepted` | «פתוחה» / «מטופלת» |
| `sos.error.SOS_ALREADY_ACCEPTED` | «{{name}} כבר מגיעה.» |
| `sos.error.alreadyAcceptedUnknown` | «מישהי אחרת כבר מגיעה.» |
| `sos.error.SOS_CLOSED` | «הקריאה כבר נסגרה.» |
| `sos.error.cancelAfterAccept` | «{{name}} כבר מגיעה. אפשר לסמן «נפתר» במקום.» |
| `sos.error.notFound` | «הקריאה כבר לא פתוחה. הרשימה תתוקן בעדכון הבא.» |
| `sos.error.noteTooLong` | «ההודעה ארוכה מדי.» |
| `sos.error.selfTarget` | «אי אפשר לקרוא לעצמך.» |

plus `sos.acceptedCue` / `sos.resolvedCue` / `sos.cancelledCue` / `sos.dismissedCue` / `sos.centreRaise` / `sos.noteOptional`. **The canonical key list is the copy deck (`.planning/design/screens/sos-paging/copy.md`), not this table** — the F57 and F36 precedent, where `copy.md` outranked the spec's prose and corrections landed there first. ⚠ The four cue keys are rendered **twice, by two different surfaces**: `SosCentre` writes them into `FloorPanel`'s `role="status"` region, `SosOverlay` passes them to the shipped app-level `useToast()` (D15). One string, two regions, and that is deliberate.

⚠ **`HE_F37` MUST BE FOLDED INTO `HE`, and it is one line that the shipped file already warns about in writing.** `i18n.test.ts:24-71` builds `HE` as a **hand-folded spread** of per-feature constants (`HE_F15 … HE_F36`), and its own comment records the failure mode verbatim: *"Folded in, not just declared: without this the resolve check, BOTH register guards and the `ar` parity guard silently skip every F52 key."* (Verified.) **So the header's and this section's claim that «בדרך» *"is banned by `i18n.test.ts:558-561`"* is TRUE ONLY AFTER THE FOLD** — a `sos.*` namespace that is declared and not folded is skipped by the «בדרך» ban and by the no-exclamation-mark register guard alike, and the whole ack-button wording decision rests on that ban. Add, exactly as `HE_F36` does for `rooms.` at `:60`:

```ts
const HE_F37 = entries(he.translation, (key) => key.startsWith("sos."));
```

spread into `HE` at `:61-71`, with its own row-count floor. **The `sos.*`-scoped ban assertion is then belt-and-braces, as claimed — not the only guard.**

**Reuse before invention.** `floor.refresh`, `floor.pause*`, `floor.resume*`, `floor.paused*`, `floor.idleStopped`, `floor.staleAt`, `floor.staleBody`, `floor.updatedAt`, `floor.sessionEnded`, `floor.accessEnded`, `floor.reload`, `staff.loadFailed` are **all shipped and reused unchanged** by `SosCentre` — it is inside `FloorPanel`'s poll and must not spell any of its states a second way (F57's F-10 argument). **`rooms.elapsed` / `rooms.elapsedJustNow` are reused too**, because `lib/elapsed.ts` hardcodes them and the alternative is a second elapsed implementation, which D17's own no-date-library rule forbids. *Recorded as a deliberate cross-namespace reuse, exactly as F36 reused `floor.*` inside `rooms`.*

**No new formatter.** `jerusalemTime` already renders with `timeZone` set (`jerusalem.ts:35`), so `scripts/qa-greps.sh`'s unzoned-formatter grep gains nothing to find. `ESCALATION_AFTER` and `STALLED_AFTER` live on the server and are deliberately **not** mirrored through `test_frontend_constant_parity.py`, because the client never computes them — it renders booleans the server derived (D7). ⚠ **And after the copy fix the client carries no number at all**: «ללא מענה» and «אין תזוזה מאז שאושרה» name the thresholds as states rather than as durations, which is what makes «mirroring a number nothing computes is parity theatre» a complete argument rather than one with a literal 30 sitting in the bundle contradicting it. `MAX_SOS_NOTE_LENGTH` **is** mirrored, in the existing `id="manage-floor"` `MIRRORS` param beside `MAX_ROOM_LABEL_LENGTH` (`test_frontend_constant_parity.py:110`) — one name added to one tuple.

### D18 — a11y beyond the overlay, and what axe still cannot see

Everything in D15 plus:

- **axe has no rule for SC 2.2.2.** F37 adds no pause control (D11's argument) but it does add a second updating region **inside** `FloorPanel`'s — so `FloorPanel`'s shipped pause and idle assertions now govern one more thing and **must not be cut as redundant**, and the freeze-while-paused behaviour (D11) needs its own named test, because a pause control whose region keeps moving is a 2.2.2 failure that passes axe.
- **axe cannot see a focus move that should not have happened.** The three MOVE tests plus the *does-not-move* test are the only coverage, and each carries its named mutation.
- **One `Badge` per SOS-centre row**, and it is the status word. The raiser's role is muted words in a bare `<bdi>` and never a second pill — F36's D18 rule, same surface.
- **The raise control on a room tile is a fourth control in that tile's action row.** ⚠ The row already carries «שחרור», «העברה לעמיתה» and «הוספת שמלה» at 375px; a fourth must wrap rather than shrink, and 44×44 is not negotiable on any of them. This is the one place F37 touches a shipped layout and the deck owns the result.
- **`FloorPanel`'s pointer-hold (`holdRef`) gains one more reason and no code.** Its comment already records that F36 made it carry far more than the ~20px it was built for; an SOS-centre row appearing **above** the rooms panel moves every tile below it, directly under a travelling finger. The mechanism is unchanged; the comment gains the case.

---

## API surface

| Method | Path | Body | Answers | Admits |
|---|---|---|---|---|
| `GET` | `/manage/floor/sos` | — | `SosResponse` (`{alerts, server_now}`) | all five, rows filtered by D7 |
| `POST` | `/manage/floor/sos` | `{target_staff_user_id?, fitting_room_assignment_id?, note?}` | `RaisedAlert` (`{alert, rerouted}`) | all five, first-person only |
| `POST` | `/manage/floor/sos/{alert_id}/accept` | — | `SosAlert` | all five (target, or elevated) |
| `POST` | `/manage/floor/sos/{alert_id}/resolve` | — | `SosAlert` | all five (raiser, acceptor, or elevated) |
| `POST` | `/manage/floor/sos/{alert_id}/cancel` | — | `SosAlert` | all five (raiser, or elevated) |

**Five new routes, eighteen on the router.** All eighteen carry `cache-control: no-store` from the router-level `_no_store`; the four new mutating verbs are CSRF-fenced by method, the one new GET is not. The raise body uses `ForbidExtraModel` (the house form); the three action routes take **no body** — the target is the alert id and there is nothing to say about it (`release_assignment`'s shipped docstring, same reasoning).

---

## Backend changes

⚠ **This table exists because three of its rows are load-bearing enough that their absence produces a 500 rather than a compile error**, and an earlier draft had a nine-row frontend table and no backend equivalent.

| File | Change |
|---|---|
| `app/models/sos_alert.py` | **new** — `class SosAlert(StandardColumns, Base)`, every column declared explicitly. The second half of the migration and not optional (D8): no model↔migration parity test exists anywhere in `backend/tests/`, so without it every backend line in D3–D10 is an `AttributeError` |
| `app/models/constants.py` | **new `SosStatus` StrEnum** (open/accepted/resolved/cancelled) + **four `AuditAction` members** (D13) |
| `app/db/repositories/sos_alerts.py` | **new** — the five reads/writes |
| `app/db/repositories/sessions.py` | **+`has_live_session(tenant_id, staff_user_id, now)`.** ⚠ **It does not exist** — the shipped file carries `insert` / `active_by_token_hash` / `revoke_for_staff_user` / `revoke_by_token_hash` (verified), so this is new work on a **second** repository |
| `app/floor/router.py` | five routes (D9). ⚠ **No `status_code=`** — see below |
| `app/floor/service.py` | the four verbs, `ESCALATION_AFTER`, `STALLED_AFTER`, `_escalated`, `_stalled`, `_for_me`, the audience clause |
| `app/floor/schemas.py` | the request/response models + D10's no-customer-datum comment |
| `app/floor/validation.py` | `MAX_SOS_NOTE_LENGTH`, `SosValidationError`, `_OccupiedError` → **`_DetailedConflictError`**, `SosAlreadyAcceptedError`, `SosClosedError` |
| `app/main.py` | ⚠ **two new imports AND two new `@app.exception_handler` blocks**, plus `_occupied_body` → `_body_with_details` and its four call sites |
| `backend/migrations/versions/00NN_sos_alerts.py` | **new**, number resolved at build time (D8) |

⚠ **`main.py` REGISTERS HANDLERS PER CONCRETE EXCEPTION CLASS, NEVER PER BASE.** Verified: `RoomOccupiedError` and `StaffOccupiedError` are imported at `:82` and handled individually at `:1174` and `:1178`; there is **no** `_OccupiedError` / `_DetailedConflictError` base handler. So `SosAlreadyAcceptedError` and `SosClosedError` need **two imports and two handler blocks of their own** — without them the 409s answer **500**, which is exactly the failure `violated_index`'s docstring records for F36. `SPEC_ERROR_CODES`' set equality catches it on the first run, so this is **cost, not risk** — but it is cost that has to be in the plan.

## Frontend changes

| File | Change |
|---|---|
| `apps/manage/src/api.ts` | new `SosStatus`, `SosAlert`, `SosResponse`, `RaisedAlert`, `RaiseSosRequest` interfaces; **five** new methods on the exported `api` object, one per route, all under `/manage/floor/sos…`. **`ApiError` and `extractError` are unchanged** — F36 already shipped `details` |
| `…/lib/sos.tsx` | **new** — `SosProvider` (owns the one `usePoll`, the tick-rate switch, the four actions, the `{401,403}` terminal rule and its own copy of the five-part `mutate` dance) + `useSos()`. `.tsx` because it renders a provider; `lib/booking.tsx` is the shipped precedent for JSX in `lib/` |
| `…/lib/usePoll.ts` | **eight lines** — `intervalMs?: number \| (() => number)` and `idleStopMs?: number \| null`, both read through refs (D12). ⚠ **The function form is the signature, not a convenience** — see D12 and design deck §11 F-10.** **Gated by the zero-edit rule on `BoardSection.test.tsx` and `FloorPanel.test.tsx`** |
| `…/components/SosOverlay.tsx` | **new** — the full-screen region (`bg-danger` / `text-surface-raised`), one `role="alert"` per rising card with the escalation/stalled clause in a **sibling outside it**, MOVE A/B/C/**D**, Esc on the container **plus the document-capture Esc route-in**, the dismiss set keyed `${id}:${escalated}:${stalled}`, the **persistent re-open affordance** while any dismissed alert is live, the **persistent `sos.channelDown` strip** on a terminal-`access` or backed-off poll, `useToast()` for its own action outcomes, the two controls in accept-then-hide order |
| `…/components/SosCentre.tsx` | **new** — a child of `FloorPanel`: the list with accept / resolve / cancel rendered by permission, the empty state, the «קריאה לעזרה» trigger, the paused freeze, cues into `FloorPanel`'s `onCue` |
| `…/components/SosRaiseDialog.tsx` | **new** — the shipped `Modal` + target `Select` + note `Input` + «שליחת הקריאה», F36's focus-return contract reused whole |
| `…/components/FloorPanel.tsx` | renders `<SosCentre/>` **above** `<RoomsPanel/>`; owns `SosRaiseDialog`'s open-state (it is the common parent of both triggers) and passes `onRaise` down to `RoomsPanel`; `holdRef`'s comment gains the SOS case. **Its shipped test expectations pass UNEDITED** |
| `…/components/RoomsPanel.tsx` | one «קריאה לעזרה» control on an occupied tile, **only when `assignment.staff_user_id === selfId`**; one new **optional** prop **`onRaise?: (assignmentId: string, trigger: HTMLButtonElement) => void`** — ⚠ **the trigger element is passed UP**, because `RoomsPanel`'s own MOVE-4 effect is keyed on state `FloorPanel` now owns and can never fire for this dialog (D16). The optionality is what keeps the shipped test file's render helper edit-free |
| `apps/manage/src/App.tsx` | **four lines**: wrap the signed-in return in `<SosProvider selfId={staff.id} role={staff.role}>`, render `<SosOverlay onSessionEnded={() => setStaff(null)}/>` before `<ConsoleShell>`. ⚠ **`setStaff` already exists** (`:129`) and is the ONLY thing that drops the console to `LoginForm`; nothing else re-authenticates (D15). ⚠ **`SectionKey` stays thirteen and `NAV` stays thirteen rows** — no new section, no new nav row |
| `apps/manage/src/validation.ts` | `MAX_SOS_NOTE_LENGTH`, mirrored from `app/floor/validation.py` (D17) |
| `…/i18n/he.ts`, `…/i18n/ar.ts` | the `sos.*` namespace — **both files**, Hebrew untranslated in `ar`. Transcribed from `copy.md`, the single source for both columns |
| `…/__tests__/SosOverlay.test.tsx` | **new** |
| `…/__tests__/SosCentre.test.tsx` | **new** |
| `…/__tests__/SosRaiseDialog.test.tsx` | **new** |
| `…/__tests__/usePoll.test.ts` (or the shipped location) | new blocks for `intervalMs` and `idleStopMs: null`; **existing blocks unedited** |
| `…/__tests__/FloorPanel.test.tsx`, `RoomsPanel.test.tsx` | **existing expectations unchanged**; new blocks for the composition and the raise trigger |
| `…/__tests__/i18n.test.ts` | ⚠ **`const HE_F37 = entries(he.translation, (key) => key.startsWith("sos."))`, SPREAD INTO `HE` at `:61-71`** — without the fold the resolve check, both register guards and the `ar` parity guard silently skip every `sos.` key, which the file's own comment at `:32-36` records verbatim (D17). Then an `F37 sos keys resolve` block with its own row-count floor, `ar[key] === he[key]` for every `sos.*` key, and the explicit `sos.*`-scoped «בדרך» assertion **in addition to** the global guard the fold restores |
| `…/__tests__/Nav.test.tsx` | **no change** — and that is an assertion, not an omission: the counts staying owner twelve / shift-manager ten / floor-roles one (`Nav.test.tsx:127`, `:134`, `:138`, `:180`, `:228`) is what proves no fourteenth section was added |
| `vite.config.ts` | **no change** — every path's second segment is `floor` (D9) |
| `scripts/qa-greps.sh` | **no change** (D17) |
| `test_frontend_constant_parity.py` | **one name** added to the existing `id="manage-floor"` param |

### Every state each surface can be in

**The overlay** — note that its *normal* state is the one that renders nothing:

| State | Render |
|---|---|
| **No alerts** (the normal state, ~100% of the time) | `null`. No DOM, no region, no landmark, no focus consequence |
| **Alerts exist but none is `for_me`** | `null`. A shift manager watching a seamstress-to-seamstress page sees it in the SOS centre and is not interrupted |
| **One rising alert** | one card: «דנה קוראת לעזרה», the room, the note, «מאז 11:20», accept + hide. Announced once. MOVE A if `activeElement` is `<body>` |
| **Several rising at once** | one card each, **oldest first** — the longest-waiting emergency is the one to answer. No carousel, no "1 of 3", the list scrolls. Each announces itself on mount and only itself |
| **Escalated** | the same card plus «ללא מענה» as **words in a sibling node OUTSIDE the `role="alert"` element** (D15). ⚠ **The alert region's text never changes after mount** — an earlier draft's row claimed both "it does not re-announce" and "the card announces the change", which are opposite claims a builder cannot implement; `role="alert"` is `aria-atomic`, so a text mutation inside it re-announces the whole card assertively. **A card dismissed before it escalated RE-RISES here exactly once**, because the dismiss key carries `escalated` |
| **Stalled** (accepted, unresolved > 2 min) | ⚠ **the card RE-RISES for elevated callers** with «אין תזוזה מאז שאושרה» in the same sibling node (D6). The one thing between «דנה מגיעה» and an emergency nobody is answering. Same re-rise-once rule as escalation |
| **Accepted by somebody else while up** | the card leaves on the next tick (`status !== 'open'`). MOVE C or MOVE B. **No error, no message** — she did not lose a race, somebody answered |
| **Accepted by this caller** | the card leaves; `SosCentre` shows it as «מטופלת» |
| **Accept 409 `SOS_ALREADY_ACCEPTED`** | in-card alert naming the owner, focus into it (D15). The card stays until the next tick removes it |
| **Accept 409 `SOS_CLOSED`** | in-card alert «הקריאה כבר נסגרה.», same |
| **Accept 404** | in-card alert, not terminal |
| **Dismissed** | the card leaves this device only; the alert is untouched. MOVE B/C. ⚠ **While the dismiss set holds any still-live alert the overlay does NOT render `null`** — one persistent 44×44 «קריאות עזרה · {{count}}» affordance re-opens it. Without it, a dismissal on any of the eleven sections with no `SosCentre` is total and permanent (D15) |
| **401 on the poll or an action** | ⚠ the overlay renders **nothing**, the loop stops, **and `onSessionEnded` fires exactly once → `App` calls the `setStaff(null)` it already has → `LoginForm`.** An earlier draft claimed *"`App` will show the login form on her next navigation"* and that is **FALSE against shipped code**: `staff` is cleared in exactly two places, the initial `api.me().catch()` (`App.tsx:142`) and `handleLogout` (`:164`); `onNavigate` is `setSection` (`:196`) and there is no fetch interceptor. Without the callback the console keeps rendering normally on eleven sections that poll nothing else, and **the emergency channel is dead and says so nowhere** |
| **403 on the poll (terminal `access`)** | ⚠ **NOT a logout** — a persistent, non-dismissible strip: «ערוץ הקריאות אינו פעיל.» + «רענון». It is the only app-level surface, so it is the only thing that can say this on the eleven sections with no panel of their own |
| **Backend down** | the loop backs off; **above one tick of backoff the same `sos.channelDown` strip renders.** «Nothing renders» is not an acceptable state for an emergency receiver that has stopped receiving. **Risk 1 still owns the ceiling**: an outage is an outage, and the product has no second channel |

**The SOS-centre panel:**

| State | Render |
|---|---|
| Initial load | `FloorPanel`'s existing `Skeleton` shape |
| **No alerts** | «אין עכשיו קריאות פתוחות.» + the «קריאה לעזרה» trigger. The panel never disappears — it is an entry point |
| **One open** | raiser, room, note, elapsed, «פתוחה», and the controls she may use |
| **Several open** | oldest first, same order as the overlay so the two screens agree |
| **Accepted by somebody else** | «מטופלת» + «{{name}} מגיעה.»; the accept control is gone, resolve remains for the raiser/acceptor/elevated |
| **Escalated** | «ללא מענה» as words beside «פתוחה» |
| **Accepted and STALLED (> 2 min)** | «אין תזוזה מאז שאושרה» as words beside «מטופלת». The row is unchanged otherwise; resolve is still the way out |
| **Raised by me, unanswered** | my own card, no accept control (D7), cancel + resolve |
| **Rerouted at raise** | ⚠ **rendered in the raise DIALOG, which stays open with «הבנתי»** (D16) — not as a cue. `rerouted` is a fact about the request, not the row, so `SosCentre` can never show it, which is exactly why a missed transient cue would be unrecoverable |
| **Raised by me while the board is PAUSED** | ⚠ **my new alert appears anyway** — the freeze is exempt for a row this device just created (D11). Otherwise the overlay never rises for her own page and the frozen list never adds it, leaving a transient cue as her only feedback |
| **The raiser went offline** | nothing changes. The alert is a row, not a connection; it stays open, keeps escalating, and resolves when somebody says so |
| **The ACCEPTOR went offline / forgot** | ⚠ **`stalled` flips at two minutes and the card re-rises for every elevated caller** (D6). Without it the accept path re-opens the silent drop the create path closed: her phone dies, and the raiser's screen still reads «דנה מגיעה» |
| **The room was released** | the room label still renders (D10's filter-less join). «דנה קוראת לעזרה — חדר 2» is still where to go |
| **The room was deleted after release** | still renders, same join, same reason (F36 Risk 1(c)) |
| **The raiser was removed from staff** | `raised_by_name: null` → «אשת צוות שאינה ברשימה» + the room. The page is still answerable |
| **Paused** | the list **freezes** from a snapshot; the freshness line says «מושהה». The overlay keeps rising (D11) |
| Failed poll with rows on screen | rows kept, freshness marked stale, «רענון» — `FloorPanel`'s shipped behaviour |
| 401/403 | `FloorPanel`'s shipped terminal panel; everything cleared |

**The raise dialog:** open · target list loaded · **no colleagues at all** (only «מנהלת המשמרת», which is always a valid target — D3) · note typed · over-length (field-local 400, prevented client-side) · sending · **rerouted — the dialog STAYS OPEN with «הבנתי»** (D16) · 400 self-target (prevented by excluding herself from the list) · **the tile's assignment was released while the dialog was open** (the raise still succeeds with `fitting_room_assignment_id` resolving to `NULL` — a page never fails over a stale room, D3) · **an assignment id belonging to another staffer** (resolves to `NULL`; the alert is still created — D3 step 3) · ⚠ **THE SEND FAILED** — 5xx, dropped connection, a wifi blackspot inside a curtain, which is the most likely real failure of a phone in a fitting room: **the dialog stays open with the note preserved and renders `sos.error.raiseFailed`, the one string in the console that names «or shout» out loud**; a retry costs one tap and may duplicate, which D2 rules noise · **an SOS overlay rises while this dialog is open** (focus does not move — D15, asserted) · **Esc while this dialog is open closes the DIALOG, never the overlay** (D15's `dialog[open]` guard) · cancelled-and-focus-returned **via `FloorPanel`'s own `sosTriggerRef`, not `RoomsPanel`'s effect** (D16).

---

## Acceptance criteria

Each maps to a named test; `db` marks the ones needing real Postgres.

- [ ] **AC1** — **A raise has exactly three failure modes: 401, 403 (role outside the five), 400 (note too long, self-target).** Walked exhaustively: no room, deleted room, released assignment, foreign-tenant assignment id, **an assignment belonging to ANOTHER staffer (stores `NULL`, alert still created — D3 step 3)**, unknown staff id, logged-out target, a colleague who was deleted, an alert already open by the same raiser — **every one of them answers `200` with an alert**. ⚠ **`200`, pinned as `assert resp.status_code == 200` on every row**, not "201/200": no route on this router declares `status_code=` (verified — `create_room` at `floor/router.py:183` is the shipped create precedent and answers 200), and an ambiguous expected status on a table-driven walk is a first-run CI red on the one assertion that encodes «a page is never silently dropped». → `test_sos_api.py::test_nothing_about_the_boutique_can_refuse_a_page`, `db` `test_sos_db.py`
- [ ] **AC2** — **A named target who holds no live session is rerouted**: the alert is created with `target_staff_user_id IS NULL`, `rerouted: true` comes back, and **the raise dialog STAYS OPEN with «הבנתי»** rather than closing behind a transient cue. Mutation: close unconditionally → red. → `db` `test_a_logged_out_target_is_rerouted_to_the_shift_manager`, `SosRaiseDialog.test.tsx`
- [ ] **AC3** — **FIRST-ACCEPT-OWNS.** Two accepts landing in the gap produce one owner and one `SOS_ACCEPTED` audit row; the loser gets **409 naming the winner**. Proven by a forced interleave to the F13/F51/F57 standard. → `db` `test_a_second_accept_landing_in_the_gap_is_refused_and_names_the_owner`
- [ ] **AC4** — **Re-accepting your own accepted alert is a 200 with no audit row**; a second resolve is a 200 with no audit row; a resolve of a cancelled alert is a 200 with no audit row. → `db` `test_sos_db.py`
- [ ] **AC5** — **The escalation predicate is exact**: an alert 29 s old is not escalated, 31 s old is, exactly 30.000 s **is** (the `>=` boundary), an **accepted** alert never is, and `created_at > server_now` reads not-escalated. **And `_stalled` is exact**: accepted 1 min ago is not stalled, 3 min ago is, an **open** alert never is. → `test_sos_service.py` (pure branches, no DB)
- [ ] **AC6** — **`for_me` is exact**, as a matrix: the raiser never (including when her own page stalls), the named target always while open, an elevated caller only on a role-targeted or escalated alert — **and on a STALLED accepted one**, which is the row that makes the accept path non-silent. Everybody else never. → `test_sos_service.py`
- [ ] **AC7** — **The audience filter is exact**: a seamstress sees only alerts she raised, was named in, or owns; an owner and a shift manager see every alert in the tenant. → `db` `test_sos_db.py`
- [ ] **AC8** — **NO CUSTOMER DATUM IS ON THE SOS PAYLOAD.** The `SosAlert` key set is pinned by **set equality**, and a `db` test with a checked-in booking bound to the raiser's assignment asserts the response body contains her name **nowhere**. → `test_sos_api.py::test_the_sos_payload_carries_no_customer_datum`, `db` `test_sos_db.py`
- [ ] **AC9** — **Cancelling an accepted alert is a 409 naming the acceptor**, resolving it is a 200, **and a second cancel of an already-cancelled alert is a 200 with no audit row** (D5's cancel table, the row prose left implicit). → `db` `test_sos_db.py`
- [ ] **AC10** — Tenant B can neither read nor raise nor accept nor resolve nor cancel **anything** of tenant A's; every attempt is a 404 indistinguishable from missing. → `db` `test_sos_isolation.py`
- [ ] **AC11** — One new `tenant_id` table, one `enable_tenant_rls` call, and `test_every_tenant_id_table_has_forced_rls` green with **no edit**. → `db` `test_tenant_isolation.py`
- [ ] **AC12** — The `status` CHECK and `idx_sos_alerts_live` are pinned **byte-identical from CAPTURED literals** after this feature's migration; `sos_alerts` carries **zero** non-primary unique indexes; the round trip passes in both directions **using F36's `_parent_of` helper**. → `db` `test_migrations.py`
- [ ] **AC13** — **`FLOOR_ROUTES` is eighteen and `FLOOR_OPEN` is fourteen**; the four F36-tightened paths stay absent; the walker's intersection classifier is untouched. → `test_floor_api.py`, `test_staff_role_gating.py`
- [ ] **AC14** — **THE OVERLAY DOES NOT STEAL FOCUS, in all three branches.** (a) focus in a text input → an arriving alert leaves `document.activeElement` and the input's value untouched **and is still announced** (`role="alert"` present with the sentence); (b) focus on `<body>` → it moves to **the card CONTAINER** (`<article ref tabIndex={-1} aria-labelledby>`) and **never to the accept control** (DC-1: MOVE A fires exactly when the next Space is a page scroll, and there is no un-accept verb, so landing on the ack would convert an involuntary keypress into an irreversible accept on top of the two-minute stall hole; accept stays first in DOM, so reach costs one Tab); (c) ⚠ **focus on a `ConsoleShell` nav button — the ordinary state of a console in use** → `document.activeElement` is **unchanged** and the `role="alert"` sentence is still present. **All three mutation-checked** (delete the `=== document.body` guard). → `SosOverlay.test.tsx`
- [ ] **AC15** — **MOVE B, MOVE C, MOVE D and MOVE I.** B: the overlay leaving while holding focus lands on `#console-main`. C: a card leaving with siblings remaining lands on the **next remaining card's CONTAINER** (DC-1, as AC14(b)). **D: an in-card 409/404 alert takes focus ONLY when `document.activeElement` was inside that same card** — mutation: remove the in-card guard, then assert focus does **not** leave a text input behind the overlay when a 409 lands. **I: `SosCentre`'s SUCCESS path** — an accept/resolve/cancel that removes the tapped control restores focus to the row's remaining control, or to the panel's own `<h3 ref tabIndex={-1}>` when the row went with it. **Never `<body>`.** ⚠ **B and C must be asserted on a SUCCESSFUL ACCEPT and not only on «הסתרה»**: the dismiss control is synchronous and never `disabled`, so focus genuinely stays on it in both engines and a suite that only drives it passes over the path Chromium takes. ⚠ **Both DIRECTIONS for B/C/I** — the restore fires, AND a response landing after she has moved on does not steal focus back (F41's first fix cured the drop and shipped the steal). ⚠ **`HTMLElement.blur()` BAILS on a disabled element in jsdom**, so `control.blur()` after the click is a no-op and cannot produce `<body>`; use a scratch node outside React's tree, or a Chromium journey. Each mutation-checked. → `SosOverlay.test.tsx`, `SosCentre.test.tsx`, `e2e/sos.spec.ts`
- [ ] **AC16** — ⚠ **The `role="alert"` element's text content is BYTE-IDENTICAL from mount to unmount, INCLUDING across the escalation and stall transitions** (the clause renders in a sibling outside the region), and a second alert arriving mounts a second region and does not touch the first. **Mutation: move the escalation clause inside the alert region → red.** → `SosOverlay.test.tsx`
- [ ] **AC17** — **Esc, all four cases.** Esc from **inside** the overlay dismisses; Esc from **outside**, with an alert rising, **moves focus INTO the first card's «אני מגיעה» and leaves the source input's value unchanged**; a second Esc then dismisses; with a `@boutique/ui` `Modal` open, Esc closes the **Modal** and the overlay is untouched. **Mutation: delete the capture handler — the second case must go red.** → `SosOverlay.test.tsx`, `SosRaiseDialog.test.tsx`
- [ ] **AC18** — **Pausing the floor board freezes the SOS-centre list and does NOT stop the overlay** — **and an alert THIS device raises while paused appears anyway** (D11's one exemption). → `SosCentre.test.tsx` + `SosOverlay.test.tsx`
- [ ] **AC19** — **The SOS loop never idle-stops**, while `FloorPanel`'s and `BoardSection`'s still do — **including after `idleStopMs` changes from a number to `null` with a timer already armed** (D12's ordering rule). → `usePoll` tests + `SosOverlay.test.tsx`
- [ ] **AC20** — **`usePoll` shipped callers are byte-identical in behaviour.** Two halves, deliberately split because a `git diff` is a reviewer's habit and not a gate: **(a) mechanical, a real test** — `usePoll` called with no `intervalMs` and no `idleStopMs` arms at `POLL_INTERVAL_MS` and idle-stops at `IDLE_STOP_MS`, pinned in `usePoll`'s own file; **(b) review instruction** — `BoardSection.test.tsx` and `FloorPanel.test.tsx` expectations pass **unedited**, `Nav.test.tsx`'s three counts unchanged, `SectionKey` and `NAV` stay thirteen (D12's acceptance rule; **an edit to a shipped expectation means the change is wrong**). → `usePoll` tests + review
- [ ] **AC20b** — ⚠ **THE TICK RATE SWITCHES ON THE TICK THAT OBSERVES THE ALERT, not the one after.** Driving **one real tick** whose response carries the first alert, the next timer fires at **2 000 ms**. **Mutation: derive the gap from React state instead of the response ref → red** (the prop-rerender-then-tick test shape passes over the bug, which is why this AC names the tick). → `usePoll` tests + `SosOverlay.test.tsx`
- [ ] **AC21** — **A seamstress sees no accept control on an alert that names somebody else, no resolve on a stranger's alert and no cancel on one she did not raise**; an owner sees all three. The 403-is-terminal rule stays unreachable by design. → `SosCentre.test.tsx`
- [ ] **AC22** — **The raise control appears on the tile she holds and on no other tile**, and in the SOS centre for everyone. → `RoomsPanel.test.tsx`, `SosCentre.test.tsx`
- [ ] **AC23** — The console is Hebrew-first RTL on `packages/ui` tokens, ships every `ar` key **byte-identical to its approved Hebrew value** (`ar[key] === he[key]` for every `sos.*` key), **no `sos.*` value matches `/נשלח|תישלח|בדרך/`**, and **axe returns zero violations**. → `i18n.test.ts`, `SosOverlay.test.tsx`
- [ ] **AC24** — `vite.config.ts` is unchanged and `test_spa_serving.py::test_the_manage_dev_proxy_names_every_manage_api_segment` is green with no edit. → `test_spa_serving.py`
- [ ] **AC25** — **No worker job exists.** Split for the same reason as AC20: **(a) a real test** — `poll_once` still runs **exactly two** jobs, asserted in `test_worker*.py`; **(b) review instruction** — `app/worker.py` has a zero-line diff.
- [ ] **AC26** — ⚠ **THE ACCEPT PATH DOES NOT SILENTLY DROP A PAGE.** An alert accepted and left unresolved for two minutes reads `stalled: true`, `for_me` becomes true again for every elevated caller, and the card re-rises carrying «אין תזוזה מאז שאושרה». **Mutation: delete `_stalled` (or its `_for_me` branch) — an accepted alert then never re-surfaces on any device in the boutique, forever.** → `test_sos_service.py` matrix row + one `db` row seeding `acknowledged_at`
- [ ] **AC27** — ⚠ **THE RECEIVING END NEVER DIES SILENTLY.** A 401 on a tick fires `onSessionEnded` **exactly once** and the loop stops (and `App`'s `setStaff(null)` drops the console to `LoginForm`); a **403** leaves `staff` untouched and renders the persistent `sos.channelDown` strip; a loop backed off beyond one tick renders the same strip. **Mutation: delete the callback / the strip — the console keeps rendering a working-looking shell over a dead channel.** → `SosOverlay.test.tsx`
- [ ] **AC28** — ⚠ **A DISMISSAL IS NEVER PERMANENT.** (a) dismiss at t<30 s, tick with `escalated: true`, the card is **back** (mutation: revert the dismiss key to the bare id → red); (b) an alert dismissed on a **non-floor section** stays reachable without a reload, via the persistent «קריאות עזרה · {{count}}» affordance (mutation: delete the affordance → red). → `SosOverlay.test.tsx`
- [ ] **AC29** — **An accept, resolve or dismiss issued from the overlay on a NON-FLOOR section produces a `role="status"` carrying the matching cue**, through the shipped app-level `ToastProvider`. **Mutation: delete the `useToast()` call → red.** ⚠ **AND THE CUE IS FIRED FROM AN EFFECT GATED ON `terminal === null`, not from the handler**, exactly as `SosCentre` already does: the provider's `mutate` returns `null` on a SUCCESS **and** on a TERMINAL 401/403, so a cue fired on `failure === null` announces «הקריאה התקבלה.» to a responder the server just refused, with the channel-down strip rendering beside it and the alert still open and unowned. **Mutation: delete the terminal check → red.** → `SosOverlay.test.tsx`
- [ ] **AC30** — **A raise whose request fails keeps the dialog open with the note preserved and renders `sos.error.raiseFailed`**, never `FALLBACK_ERROR_MESSAGE`. → `SosRaiseDialog.test.tsx`
- [ ] **AC32** — **THE REROUTED SENTENCE IS ANNOUNCED, NOT MERELY RENDERED.** The `<p>` that replaces the dialog body on a reroute carries `role="status"` **and** an `id` referenced by the «הבנתי» button's `aria-describedby`, so it is read both as a live region and with the control MOVE E focuses. ⚠ **Without both, the one message the ruling mandates was announced to NOBODY**: `Modal` sets only `aria-labelledby` (no `aria-describedby`), so the swapped body was not the dialog's accessible description, and MOVE E then moved focus to a button whose entire label is «הבנתי» — a blind raiser heard «הבנתי, לחצן» and nothing about Dana, and `rerouted` is a fact about the REQUEST (D10) so no `SosCentre` row can ever tell her afterwards. **Mutation: remove either attribute → red.** → `SosRaiseDialog.test.tsx`
- [ ] **AC33** — **The overlay's bottom container is `pointer-events-none` with `pointer-events-auto` on the affordance and on the channel-down strip** (`Toast.tsx:40`'s shipped shape). Without it, a dismissed-but-live alert leaves an INVISIBLE full-width band ≈76px tall at `z-40` across the bottom of all thirteen sections, and a tap on a console control inside it does nothing with nothing on screen to explain why — measured in Chromium, where `elementFromPoint` returned the band. **Mutation: delete `pointer-events-none` → the Chromium journey reds.** → `SosOverlay.test.tsx`, `e2e/sos.spec.ts`
- [ ] **AC31** — **The raise dialog's focus return runs from `FloorPanel`'s own trigger ref**, lands on the trigger when it is connected and on `FloorPanel`'s `<h2>` when it is not, **never `<body>`**. **Mutation: delete the `isConnected` branch → focus goes nowhere.** → `SosRaiseDialog.test.tsx`

---

## Testing

### Fast suite (no marker, no Docker)

- **`tests/test_floor_api.py` (extended)** — `FLOOR_ROUTES` grows from thirteen rows to **eighteen**, split into `FLOOR_OPEN_ROUTES` (nine → **fourteen**) and `FLOOR_TIGHTENED_ROUTES` (unchanged at four), **and D9's table is the only source for those counts** — a figure sized from prose reds a table-driven test on the first run. `FakeFloorService` grows the five methods. `SPEC_ERROR_CODES` becomes **nine** and stays set-equal. The payload asserted as a literal for one open, one accepted and one escalated alert **including `server_now`**, `escalated` and `for_me`. Both 409 bodies asserted **including `details`**, **plus the `details`-less variant**, plus a companion assertion that no *other* body in `main.py` grew one.
- **`tests/test_sos_api.py` (new)** — the `SosAlert` key set pinned by **set equality** (AC8 — the assertion that catches a customer field arriving unreviewed on a payload that polls eleven sections); the raise's three failure modes walked exhaustively (AC1); `ForbidExtraModel` refusing a body that carries `raised_by`.
- **`tests/test_sos_service.py` (new)** — the pure branches, against fakes, which is where D6's and D7's derivations are actually proven:
  - **`_escalated`** — 29 s / 31 s / accepted / acknowledged / negative-delta clamp (AC5);
  - **`_for_me`** — the full matrix over {raiser, named target, other floor role, shift manager, owner} × {role-targeted, name-targeted} × {escalated, not} (AC6);
  - **accept** — the target and elevated allowed; everybody else **404 and the repository is never called past the read** (the assertion that proves the refusal is not an existence oracle);
  - **resolve / cancel** — raiser / acceptor / elevated allowed; the cancel-after-accept 409;
  - the `(wrote, row)` mapping onto 200 / 200-unchanged / 404 / 409; an audit row on a write and **none** on a no-op; `from_status` captured **before** the write.
- **`tests/test_floor_validation.py` (extended)** — note stripping, `""` → `None`, over-length, self-target.
- **`tests/test_staff_role_gating.py` (extended)** — `FLOOR_OPEN` grows from nine to **fourteen** as **route templates** (never concrete urls — `:92-96`); the four tightened paths stay **deliberately absent**; the intersection classifier is **not touched** (F57's Risk 1).
- **`tests/test_frontend_constant_parity.py` (extended)** — one name in the existing `id="manage-floor"` param.

### `db`-marked (real Postgres)

**Standard to meet: F34's, F57's and F36's.** All three stood up a throwaway Postgres 16 cluster outside the repo, ran every migration and executed the whole `db` set **before pushing** — which is why all three were green on CI's first run despite their headline tests debuting there. **Capture every pinned literal by running it; do not transcribe.**

- **`tests/test_migrations.py` (extended)** — the table exists with its exact column list; the CHECK and the index pinned byte-identical from **captured** literals; the non-primary unique-index count is **0**; the round trip in both directions via **`_parent_of`** (`:31`), last in the file, inside `try/finally: command.upgrade(cfg, "head")`. **The single-head guard is `test_exactly_one_migration_head` (`:57`) and is NOT `db`-marked**, so it catches a double head in `make test`; F36's own round trip is at `:1708` and F37's must land after it.
- **`tests/test_sos_db.py` (new)** — the four verbs and the races. ⚠ **`test_floor_db.py`'s seed rule applies verbatim: every row this module COMMITS holds `owner` or `shift_manager`, never a floor role** (`test_floor_db.py:12-32`) — `migrated_db` is session-scoped, pytest collects alphabetically, and a committed `reception` row reddens three tests in `test_migrations.py` that have nothing to do with SOS. ⚠ **And the escalation and stall tests FREEZE BOTH OPERANDS, because both are injectable and an earlier draft's justification for leaving one live was wrong.** The predicate never reads the database clock at evaluation time: it compares a seeded `created_at` against `server_now`, and **`server_now` is `self._clock()` — `FloorService.__init__` already takes `clock: Callable[[], datetime] | None = None` (`floor/service.py:165,177`, verified, with four shipped call sites using it.)** Construct the service under test as `FloorService(..., clock=lambda: FIXED)` and seed `created_at = FIXED - timedelta(seconds=29)` / `FIXED - timedelta(seconds=31)` (and `acknowledged_at = FIXED - timedelta(minutes=1)` / `FIXED - timedelta(minutes=3)` for the stall). **Both operands then come from the same frozen instant and the margin is exact rather than one second.** Left as written — seed `created_at`, let the wall clock supply `server_now` — the not-escalated assertion flips to escalated as soon as ~1 s elapses between the seed and the read, i.e. a Postgres round trip plus session setup on a loaded CI box, **and a test that goes green or red on machine speed will be re-run until it passes, which is how a mutation regime rots.** What a `db` test genuinely cannot freeze is `server_default=text("now()")` — which is precisely why `created_at` is **seeded** (the default applies only when the column is omitted); the service clock is a constructor argument.
- **`tests/test_sos_isolation.py` (new)** — the house rule for a new tenant table: tenant B reads zero alerts of tenant A's; every write against a foreign id is a 404 indistinguishable from missing; the app role's `GRANT`s are exercised (a missing one surfaces here as `permission denied` and nowhere else).

#### The forced interleaves, and the mutation each one must survive

`asyncio.gather` is **deliberately not used** for any deterministic branch, for the reason `test_floor_db.py:251-263` states verbatim. The mechanism is that `tenant_session` is `async with session_factory() as session, session.begin()`, so **exiting the context manager IS the commit** (`db/tenant.py:25`), and two nested `tenant_session`s on one `NullPool` factory take two separate connections.

⚠ **F37's races are UPDATE races, so they copy `test_a_second_start_landing_in_the_gap_renders_the_winners_timestamp` (`test_floor_db.py:266-325`) and NOT F36's INSERT shape.** The loser opens its session and **reads** (a plain SELECT, no row locks) → the winner's inner `async with` opens, writes and **exits, which is the commit** → only then does the loser issue its guarded UPDATE, which matches zero rows immediately. **Nothing ever blocks and nothing can hang** — F36's Rejected Finding worried about the INSERT variant and does not apply here at all, because a guarded UPDATE against a committed row returns rather than waiting.

| Test | Mutation that MUST turn it red | Why nothing else catches it |
|---|---|---|
| `test_a_second_accept_landing_in_the_gap_is_refused_and_names_the_owner` | **drop `AND status = 'open'` from the accept's UPDATE predicate** | every other accept test accepts once. Without the conjunct the loser overwrites the winner: `accepted_by` flips to the second responder, the first is never told, and **two people walk to one curtain while a third emergency goes unanswered.** The ONLY test that fails |
| ″ | **remove `populate_existing=True` from the accept's re-read** | every test that opens a **fresh** session per operation has an empty identity map, so the flag is a no-op there — F57's shipped note records exactly this. The loser would render **its own** `accepted_by` and the 409 would name the wrong person |
| ″ | **resolve idempotence AFTER the 409 instead of before** | a re-accept by the current owner then answers `409 «דנה כבר מגיעה»` **to דנה**. Every single-accept test stays green (F36's D6, same trap, same ordering rule) |
| `test_a_resolve_records_the_state_it_destroys` | **move the `from_status` capture AFTER the writer** | F57's shipped note records this precise mutation leaving **all** fast tests green, because monkeypatched repositories never stamp anything. Only a real session's identity map poisons the local, and the audit row silently becomes `resolved → resolved` |
| `test_a_cancel_racing_an_accept_never_strands_the_responder` | **widen cancel's predicate to `status IN ('open','accepted')`** | the cancel then succeeds against an accepted alert, the 409 never fires, and a colleague walks to a curtain for an emergency that was cancelled behind her. Every sequential cancel test stays green |
| `test_a_resolve_landing_after_a_resolve_writes_nothing` | **treat rowcount 0 as a 404** | she wanted it closed and it is closed; the second resolver would get an error for being right. No other test issues two resolves |
| `test_an_alert_open_for_31_seconds_is_escalated_and_one_open_for_29_is_not` | **change `>=` to `>` and assert the exactly-30.000 s boundary** | the boundary is the whole of the 30-second ruling and no other test lands on it. ⚠ **This ROW REPLACED a vacuous one.** The earlier draft named *"drop the `max(timedelta(0), …)` clamp and seed `created_at` after `server_now`"*, reasoning that *"on the reverse comparison it escalates instantly"* — **there is no reverse comparison**: the predicate is `delta >= ESCALATION_AFTER`, and `timedelta(seconds=-5) >= timedelta(seconds=30)` is `False`, byte-identical to the clamped `timedelta(0) >= timedelta(seconds=30)`. The mutation came back **GREEN**, which is exactly the false confidence the regime exists to catch, so **the clamp is deleted from `_escalated`** (D6) and the negative-delta case stays an **assertion**, not a mutation target |
| ″ | **drop the `row.status != SosStatus.OPEN` conjunct** | reds only the accepted-never-escalates case, which is the conjunct that actually carries weight. ⚠ **Two of the predicate's three clauses are genuinely unmutatable** — D6 concedes the same about `acknowledged_at is not None` (`status == 'open'` already implies it) — so only this guard and the threshold are pinned, and saying so is better than a table implying three |
| `test_an_accepted_alert_unresolved_for_two_minutes_re_rises_for_the_shift_manager` | **delete `_stalled`, or its branch in `_for_me`** | every other test accepts and then resolves. Without it an accepted alert stops escalating and stops rising **on every device in the boutique, forever** — and the raiser's screen still reads «דנה מגיעה», so she stops looking for help on a signal the product cannot back. **The ONLY test that fails** |
| ″ | **stamp `escalated` from a worker instead** | not a mutation of this code — recorded as the reason D6 has no worker to mutate. The equivalent check is AC25's zero-line `worker.py` diff |
| `test_an_accept_whose_winner_was_removed_does_not_name_nobody` | **make `details` a required key** | the path then either raises building the body or ships `{"staff_display_name": null}` and the console renders an empty interpolation. Every other 409 test has an owner to read |
| `test_a_logged_out_target_is_rerouted_to_the_shift_manager` | **drop the `expires_at > :now` conjunct from the reachability read** | an expired session then reads as live, the page is stored against a staffer whose cookie is dead, and it reaches **nobody** until the 30-second escalation — the exact silent drop this feature forbids. Every test whose target has a fresh session stays green |
| `test_the_sos_payload_carries_no_customer_datum` | **add `client_label` to the alert join** | the assertion is a **negative over the whole response body**, so it is the only thing that can fail; every other test asserts on fields that would still be present |
| `test_a_released_assignment_still_resolves_its_room_label` | **add `released_at IS NULL` to the assignment join, or `deleted_at IS NULL` to the rooms join** | the alert then loses its room mid-emergency. F36's Risk 1(c) predicted both, and no other test releases a room while an alert is open |

**Every one of these mutations must be RUN, not reasoned about.** F34, F57 and F36 each found a real vacuous test this way — F57's was a focus test jsdom could never have failed, and F36 ran nine mutations of which **two came back green and were recorded in the code as not-actually-pinned rather than left as false confidence.** F37 does the same: any mutation that comes back green is written into the source beside the mechanism it failed to pin.

### Frontend (vitest)

- **`SosOverlay.test.tsx` (new)** — renders nothing with no alerts and nothing when no alert is `for_me`; one card per rising alert, oldest first; the announced sentence present in a `role="alert"`; **the four focus tests, each with its named mutation** — (1) focus in an `<input>` → an arriving alert leaves `document.activeElement` and the input's value alone **and the alert is still announced** (mutation: delete the `=== document.body` guard); (2) focus on `<body>` → moves to the accept control (mutation: delete the effect — and ⚠ **check it is not vacuous**, since jsdom's focus behaviour is what made F57's equivalent test worthless); (3) the overlay leaving while holding focus → `#console-main`, never `<body>`; (4) a card leaving with siblings → the next card's control. **The `role="alert"` element's text is byte-identical from mount to unmount, across three consecutive ticks AND across the escalation and stall transitions** (AC16, mutation: move the clause inside the region); a second alert arriving mounts a second `role="alert"` and does not touch the first. **Esc inside dismisses; Esc OUTSIDE moves focus into the first accept control and leaves the source input's value alone** (AC17, mutation: delete the capture handler); with a `Modal` open, Esc closes the Modal. **The dismiss set is keyed on `${id}:${escalated}:${stalled}`** — dismiss, tick with `escalated: true`, the card is back (AC28a, mutation: bare id) — and **while it holds a live alert the overlay renders the «קריאות עזרה · {{count}}» affordance and not `null`** (AC28b). **A 401 fires `onSessionEnded` exactly once and stops the loop; a 403 renders the `sos.channelDown` strip and does NOT clear `staff`; a backed-off loop renders the same strip** (AC27). **An accept from a non-floor section calls the shipped `useToast()`** (AC29). **An axe pass, explicitly not sufficient.**
- **`SosCentre.test.tsx` (new)** — empty state with the trigger; rows with raiser, room, note, elapsed and the **status word**; `sos.escalated` as **words**; **for `role="seamstress"` the accept control on somebody else's alert, the resolve on a stranger's and the cancel on one she did not raise are ALL ABSENT, and all three are present for `owner`** (AC21); accept patches the row **from the response** and is disabled while in flight, and a double-tap fires **one** request; a 409 `SOS_ALREADY_ACCEPTED` renders the owner's name from `details` and the `details`-less variant renders the unknown sentence; a 404 is **not** terminal and a 403 **is**; **a tick landing while paused does not change the rendered list** (AC18) and the overlay still rises; cues go into `FloorPanel`'s region and **the poll never writes there**.
- **`SosRaiseDialog.test.tsx` (new)** — «מנהלת המשמרת» is first and default; herself is excluded; a colleague on a break is annotated and **not** excluded; the note's `maxLength`; **a rerouted raise KEEPS THE DIALOG OPEN with «הבנתי»** (AC2, mutation: close unconditionally); **a rejected send keeps it open with the note preserved and renders `sos.error.raiseFailed`** (AC30); **the focus return through `FloorPanel`'s own trigger ref** — trigger → `FloorPanel`'s `<h2>` fallback, never `<body>` (AC31, mutation: delete the `isConnected` branch); **an overlay rising while the dialog is open does not move focus** (AC14's sibling case, mutation-checked).
- **`usePoll` tests** — new blocks: `intervalMs` governs the gap as a **number and as a function**, and `succeeded()` resets to **the resolved value** and not to `POLL_INTERVAL_MS`; ⚠ **ONE REAL TICK whose response carries the first alert re-arms at 2 000 ms** (AC20b — mutation: derive the gap from React state; note the weaker rerender-then-tick shape passes over the bug and must not be the only block); `idleStopMs: null` never stops, **including when it changes from a number to `null` with a timer already armed** (D12's `clearIdle()` ordering); **the default path is pinned mechanically** — no `intervalMs`, no `idleStopMs` → gap is `POLL_INTERVAL_MS` and the idle stop trips at `IDLE_STOP_MS` (AC20a) — and every shipped block passes unedited.
- **`FloorPanel.test.tsx` / `RoomsPanel.test.tsx`** — **existing expectations unedited (AC20)**; new blocks for `<SosCentre/>`'s placement above the rooms and for the tile's raise control appearing on her own tile only.
- **`i18n.test.ts`** — ⚠ **FIRST, `HE_F37` is declared AND FOLDED into `HE` at `:61-71`** (D17): without the fold the resolve check, both register guards and the `ar` parity guard skip every `sos.` key, which the file's own comment at `:32-36` records verbatim, and the «בדרך» ban this spec cites as already binding **would not cover the namespace at all.** Then: the whole `sos.*` deck resolves in `he` and in `ar`; **for every key starting `sos.`, `ar[key] === he[key]`** (not merely "non-empty" — that passes on an English string, a `TODO`, or a *different* Hebrew wording, and ~40 keys are transcribed by hand into two files); **and an explicit `sos.*`-scoped assertion that no value matches the THREE-term `/נשלח|תישלח|בדרך/`** (`i18n.test.ts:560`) — ⚠ **NOT the `HE_F33`-scoped five-term `/נשלח|תישלח|בדרך|SMS|הודעה/` at `:547`, because «הודעה» appears in the approved `sos.error.noteTooLong`** — stated where the block is read — **belt-and-braces over the global guard the fold restores, not a substitute for it** (D17).

### E2E

**None, and the reason is F34's, F57's and F36's verbatim:** the console's entire e2e surface is two login-screen tests because `vite preview` runs with no backend (`e2e/a11y.spec.ts:10-13`). **F58 owns the `/manage/**` Playwright interception harness** and the floor-program review budgets it there as real work. Recorded rather than silently skipped — and ⚠ **F37 widens that gap more than any feature before it**, because an overlay that appears unbidden over a real browser's real focus is precisely the thing jsdom models worst. **Risk 6 hands F58 a named list of three overlay behaviours to cover the day the harness exists.**

---

## Out of scope

- **Browser push, service workers, APNs, FCM, SMS, a phone call.** #32 and the 2026-07-31 ruling: **in-app only.** No `message_log` row, no `MessageKind` value, so that enum and its CHECK are untouched.
- **F35's durable staff bell.** Dropped from this feature's deps by the ruling and still queued as the later durable surface.
- **Sound, vibration, flashing.** A quiet room, a WCAG 1.4.2 problem and a bride's afternoon.
- **A durable `escalated_at`.** D6's recorded upgrade path.
- **A second escalation tier for an OPEN alert** (30 s → manager → 60 s → everyone). One tier, one number, one ruling. ⚠ **`_stalled` is not that**: it is the same audience (elevated) and the same mechanism (a read-time boolean), applied to the **accepted** state, where the ruling's tier does not reach at all — and without it the accept path re-opens the silent drop the create path closes (D6). Widening the stall's audience beyond elevated **is** a second tier and stays out.
- **Auto-resolve, auto-expire, auto-cancel.** Nothing on a clock closes an alert; only a person does. That is the other half of «never silently dropped» — and it is exactly why `_stalled` re-raises attention rather than changing `status`.
- **An un-accept verb.** The remedy for an accept nobody followed through on is that it re-rises (`_stalled`) and somebody else accepts or resolves it. A verb that moves a row backwards to `open` would give D4's `else: raise` a reachable input and would make «who owns this» answerable two ways.
- **A chat thread, a reply, an ETA.** The responder is walking to the room, not typing.
- **Severity levels, priorities, per-role SLAs, response-time analytics, a history read.** Pre-decided #28 keeps reporting out of E6 and it holds here; D1 declines the columns and D2 declines the index.
- **Paging a role other than shift manager.** The ruling replaced the role fanout with a person or the shift manager, and «I need a seamstress» is now «I need Dana» or «I need the manager».
- **An on-shift roster.** F40's, and D3 explains why a live session is the better signal anyway.
- **Cross-tenant or cross-branch paging.**
- **Retention of alert rows.** F20's job owns every retention clock; F37 stores no customer datum, so what remains is already de-identified. Risk 5 hands F20 the entry.

---

## Codebase conflicts recorded

1. **The E7 brief specifies `sos_alert_targets` — one row per paged staffer — and F37 does not build it.** The brief's justification is explicitly about **role fanout** (*"a staffer who goes off-shift mid-page would lose an alert"*, *"nobody was on shift for this role would leave no evidence"*). The 2026-07-31 ruling replaced the fanout with a single target, so the audience is one nullable column and there is nothing to snapshot. Codebase-consistent reading, taken: one table, `target_staff_user_id UUID NULL`, and the audit row carries the *requested* target so the reroute leaves evidence (D1, D13).
2. **The E7 brief pages "every on-shift staffer with that role" and says on-shift "comes from whatever F31 exposes as the current-shift read". F31 exposes nothing of the kind, and neither does F57.** `staff_users` carries `email, password_hash, display_name, role, break_started_at` and the standard columns — verified against `models/staff_user.py` — and `StaffUsersRepository.list_live` returns **every** non-deleted staffer. F34's `checked_in_at` is on `bookings`, i.e. customers. Codebase-consistent reading, taken: **"reachable" is a live row in `sessions`** (`deleted_at IS NULL AND expires_at > now`), which is what the device-identity ruling actually describes and is a **strictly better signal than a checkbox and no worse** — nobody has to remember to tick it, and it is derived from an action she actually took (D3). ⚠ **CORRECTED: it is NOT a signal that "cannot go stale", and the consequence an earlier draft drew from that does not follow.** `settings.session_ttl_seconds` is **12 hours** (`core/config.py:24`, verified), `Session` carries only `expires_at`, and `revoke_for_staff_user` fires on a password change and on deactivation — **nothing revokes on going home.** A staffer who signs in at 08:00 and leaves at 16:00 without logging out holds a live row until 20:00, so `has_live_session` returns True, no reroute fires, and the raiser is affirmatively told nothing. *Consequence recorded honestly: the reachability read is a cheap **upper bound**, the design survives on that basis, and the residual — signed in, gone home — is closed by the thirty-second escalation and by nothing else. **Risk 3 carries it**, beside the structurally identical logged-out-elevated case.*
3. **The E7 brief says an unaccepted page "stays open, keeps appearing in every targeted bell and on the shift manager's board" and that "nothing expires and nothing re-routes".** The bell is dropped (ruling) and the 30-second escalation **is** a re-route of attention (ruling). What survives literally: nothing expires, and the shift manager sees it. Codebase-consistent reading: the alert is **visible** to the elevated audience from second zero and **rises** on their screens at thirty (D6, D7).
4. **The e7 brief names `accepted_at`; LOOP-STATE names `acknowledged_at`.** LOOP-STATE governs. Same column, later name. Flagged because a reader will find the brief's word.
5. **The E7 brief says "Delivery is the bell and only the bell (pre-decided #32)".** #32's actual content is *in-app only, no push/SMS*, which is untouched; the bell was the *mechanism*, and the ruling replaced it with the overlay. Recorded so nobody reads the parenthesis as forbidding the overlay.
6. **The E7 brief says the SOS control "lives in each staffer's own signed-in app on her own phone (pre-decided #27), reachable from the fitting-room card she is standing in".** True and shipped-compatible — but F36's room tiles render for **every** room, not just hers, so "the card she is standing in" needs a predicate the brief does not give. Taken: `assignment.staff_user_id === selfId` (D16), plus a second entry point in the SOS centre for a staffer who is not in a room at all — which the brief does not contemplate and which is the ordinary case for a seamstress at her table.
7. **The E7 brief says the alert rides "F32's ~5-second refresh".** **F32 is subsumed and must never be built** (`shift-board-checkin.md:8`, LOOP-STATE, SMC ruling 3). The ruling replaced it with an app-level poll at 5 s/2 s. Codebase-consistent reading: `usePoll`, a third instance, extended by two optional fields (D11, D12).
8. **`.claude/rules/` describes a Kotlin/Micronaut/Exposed codebase and does not apply.** `floor/router.py:85-87` already says so about the RPC/`@QueryValue` guidance specifically. F37 uses real HTTP verbs and path parameters, the shipped `/manage` convention.
9. **`main.py`'s `_occupied_body` and `floor/validation.py`'s `_OccupiedError` are named for occupancy and F37 gives them two non-occupancy subclasses.** Both are private, both have two call sites, and copying six lines that must stay identical is worse than a rename. Taken: `_body_with_details` and `_DetailedConflictError`, docstrings preserved verbatim including the `__mro__` sentence (D14).

---

## Risks & open items

1. **⚠ IN-APP ONLY MEANS THE APP MUST BE OPEN AND IN THE FOREGROUND, AND THAT IS THE FEATURE'S REAL CEILING.** `usePoll` stops on `document.hidden` — deliberately, and its own comment gives the reason (*"browsers already throttle background timers to >=1/minute, so an unpaused loop would silently become a slow one and the screen would look live while being a minute stale"*). So an SOS does **not** reach a phone whose screen is off, whose browser is backgrounded, or whose console tab is not the active one. F37 removes the idle stop (D11) so an *open, untouched* screen keeps receiving — that is the half this feature can fix. ⚠ **And this is why D3's reachability read proves a session and not a screen**: `has_live_session` returns True for a phone asleep in an apron, so `rerouted: false` carries far less information than the copy might imply, and **the thirty-second escalation — not the reroute — is what actually covers a live session on a dark screen.** Stated here and in D3 rather than left for the pilot to infer. The other half needs push or a native shell, both forbidden by #32. **The pilot must be told this in words before the first shift**, because the failure mode is silence and the staffer will not discover it until it matters. *Owner: user, at pilot briefing; team, for the F35/push upgrade path.* **Trigger: the first pilot morning.**
2. **The 30-second number is a ruling, not evidence.** It was reinstated by user ruling over pre-decided #29's "no escalation timer", and nothing in the product has ever measured how long a real page goes unanswered. Thirty seconds is short enough to feel instant to the raiser and long enough that a responder walking down a corridor is not overtaken by an escalation she was already answering. `ESCALATION_AFTER` is one module constant and the read-time derivation means **changing it changes every alert's behaviour immediately, with no migration and no backfill** — which is the strongest practical argument D6 has for computing it on read. *Owner: user, on pilot evidence. Trigger: the first week.*
3. **An alert is a row, not a channel — and a `sessions` row is an upper bound on reachability, not a screen. One risk, two subjects.** *(a)* D3's reachability read does not close the case where **every elevated staffer is logged out** — F51 guarantees an owner **exists**, not that she is signed in. *(b)* ⚠ **And it does not close the named-target case either, only narrows it**: `session_ttl_seconds` is **12 hours**, longer than a shift, and nothing revokes on going home (verified), so a staffer who signed in at 08:00 and left at 16:00 reads as reachable until 20:00 — `rerouted` stays false and the raiser is affirmatively told nothing. In both, the alert is created, escalates at thirty seconds, and waits for somebody to open a console. *One named ceiling, one recorded upgrade path for both: **a last-seen heartbeat**, which this feature's own app-level tick already provides for free — the poll is a signed-in staffer touching the server every 2–5 seconds, so `sessions.last_seen_at` plus a freshness window would turn the upper bound into a real presence signal. Extending the read to the role audience is the other four lines.* **Neither is built here, and the thirty-second escalation is what stands in for both.** *Owner: team. Trigger: pilot evidence — an alert sitting open past a shift, or a reroute that should have fired and did not.*
4. **F29 inherits a poll on eleven sections that had none.** ~41 round trips per 5 s per device on the board screen idle, ~57 with an alert open, ~11 on every other section where the shipped product does zero, and `tenants.by_slug` — the uncached-per-request lever `tenancy/resolver.py:8-9` already assigns to F29 — now paid **three times per beat** on the board screen. **And this is the first loop in the product with no idle stop**, so a console left open overnight polls until the session expires (12 h, `session_ttl_seconds`). Nothing throttles it server-side and F34's D3's reasoning against a read limiter still holds. **F29 must be handed these three numbers, not left to discover them.** *Owner: team. Trigger: F29's k6 pass.*
5. **`note` is free text a staffer types, and nothing stops her typing a customer's name into it.** F37 deliberately carries no customer datum of its own (D10), which is what makes the app-level poll defensible — but a note is a text box and text boxes receive whatever a person under pressure types. The disclosure is bounded (the alert's audience, for the life of the alert, never stored beyond the row) and validating it would be worse than the disease. **F20's processing-activities record gains one line**: purpose = floor emergency coordination; personal data = staff names, a room label, and free text that may incidentally contain a customer's name; retention = the alert row, with no clock of its own. Same hand-off shape as F57's Risk 10 and F36's Risk 5, fourth subject. *Owner: team, discharged by F20.*
6. **The overlay's most important behaviours are the ones jsdom models worst, and there is no E2E.** Whether a real browser actually leaves the caret in an input when a fixed overlay mounts above it, whether a real screen reader announces a `role="alert"` that mounts inside a React commit, and whether Tab from a form field genuinely reaches the overlay's controls — none of the three is provable in vitest. jsdom already made one F57 focus test **vacuous**. **F58 owns the `/manage/**` interception harness and inherits a named list of FOUR**: the typing-preservation case, the announcement, the tab order (including D15's Esc route-in, which is a real-browser key-handling question jsdom answers by fiat), and — the fourth, added because D15 names the hazard it created rather than only the one it solved — **whether a caret in an input obscured by a `position: fixed; inset: 0` overlay is genuinely still usable**, which is the trade D15 takes in writing. *Owner: team. Trigger: F58.* **And a manual screen-reader pass is a gate condition on THIS PR** (e7 Risks: *"Add an explicit manual screen-reader check to the design gate for F37 rather than trusting the mechanical pass"*), not a deferral.
7. **`usePoll` now has three callers and two optional fields, and it is the fourth feature to import it.** D12's zero-edit acceptance rule on `BoardSection.test.tsx` and `FloorPanel.test.tsx` is the mechanical mitigation and it is the same instrument F36 used for the `mutate` extraction. **A reviewer seeing an edit to a shipped expectation in either file should stop and read D12.** *Owner: team. Trigger: this PR's code review.*
8. **`details` is now on three error codes and the shape is precedented past the point of accident.** F36's Risk 8 named this PR as its trigger and its sentence stands: *"That is fine if it stays deliberate and bad if it becomes the default — an error is not a response."* Three of the four codes that could carry it do; `SOS_CLOSED` deliberately does not, which is the assertion that the choice is still being made. *Owner: team. Trigger: the next new 409 in the codebase.*
9. **A staffer can raise duplicate alerts and nothing structural stops her** (D2). The busy discipline stops the double-tap; a deliberate second page is legitimate; two cards for one emergency is noise. **But nothing measures it**, and if the pilot shows it happening the fix is not an index (D2 explains why the obvious one is defeated by NULL-distinctness) but a client-side "you already have an open page" line. *Owner: team. Trigger: pilot evidence.*
10. **The audit rows are still write-only.** Four more actions nothing renders, and `SOS_RAISED`'s `requested_target` is the only surviving record of a reroute with no way to read it without `psql` (F15's Risk 7, F34's Risk 7, F57's Risk 8, F36's Risk 11). *Owner: user. Trigger: F53's activity log, which is the first read surface.*
11. **`ar.ts` still has no parity guard.** F37 adds ~40 keys to both files by hand; the `ar[key] === he[key]` assertion is scoped to `sos.*` and does not widen the general gap. F15's Risk 5, inherited a fifth time. *Owner: team. Trigger: F45.*
12. **Three loops on one screen is the ceiling of this architecture, and F58 will want a fourth.** The waitlist is the next thing that wants to be live on the board. **F58 must extend `/manage/floor` (F36's rule) and must not add a loop** — and if a fifth caller of `usePoll` ever appears, that is the moment to ask whether the console wants one multiplexed poll rather than N. Recorded now, while the answer is still cheap. *Owner: team. Trigger: F58's spec.*

### Rejected findings

**None.** All 33 review findings were applied. Two were applied in **modified form**, and the modification is recorded here rather than silently absorbed:

1. **«The common case on a shop floor is `<body>`» → the finding proposed replacing it with "a freshly loaded or reloaded tab".** Applied, but **worded to keep both branches** rather than to invert the claim. The finding is right that a console anybody has touched holds focus on the last-clicked element — verified against the four shipped restore effects, which exist for exactly that reason — and the original sentence was over-stated. But a board tablet loaded at 09:00 and untouched since **is** on `<body>`, and that is a real shop-floor state this feature serves. D15 now says: **focus moves only when nothing holds it; both branches are real, and which one is common depends on whether anybody has touched the screen.** The finding's substantive half — the third AC14 case, focus on a nav button, with the same delete-the-guard mutation — is applied unchanged, and it is the part that has teeth.

2. **«A keyboard user cannot see the field she is typing into» → the finding offered a full-width band or a written trade.** The **written trade** is taken, not the band. The ruling says *full-screen red*, and a band is missable on a 375px phone held inside a curtain — which is the whole scenario. D15 now names the hazard it created beside the one it solved, and Risk 6 hands F58 «typing behind the overlay» as its fourth named case. The finding's other half — **naming `bg-danger` / `text-surface-raised` rather than inventing a red at build time, and recording that axe's contrast rule cannot see obscured text** — is applied unchanged.

**Parked question (named, not blocking):** *should the overlay rise for an alert raised before this device signed in?* Today it does — the poll returns every live alert and `for_me` knows nothing about when the session started, so a shift manager signing in at 14:00 gets a full-screen overlay for a page raised at 13:58 and never answered. That is almost certainly right (an unanswered emergency is an unanswered emergency), and the alternative — suppressing anything older than the session — would silently hide exactly the alert that most needs answering. It ships as-is; the pilot settles whether it feels like a system that works or a system that shouts on login.

---

## Decisions Log

- **D1 — `sos_alerts` is ONE table: `raised_by`, `target_staff_user_id` NULL (= the shift-manager role), `fitting_room_assignment_id` NULL, `note`, `status` CHECK over four values, `accepted_by`, `acknowledged_at`, plus the standard columns.** `accepted_by` is not in LOOP-STATE's list and is not optional — the 409 must name the owner and the raiser must see who is coming, neither of which `status` and `acknowledged_at` can answer; it is written by the **same statement** as `status`, so "accepted by nobody" is unrepresentable. No `resolved_at` / `resolved_by` / `cancelled_at`: `status` says which terminal state, the trigger stamps `updated_at`, and the audit row is the record of who and when — F36's D13 argument run the other way. **`sos_alert_targets` is NOT built**: the epic justified it by role fanout, and the 2026-07-31 ruling replaced fanout with one target, so there is nothing to snapshot (Conflict 1).
- **D2 — There is NO unique index on `sos_alerts`, and the one it would want is defeated by NULL-distinctness in the exact case that matters.** `(tenant_id, raised_by, target_staff_user_id) WHERE status='open'` would guard the rare duplicate (two pages to one named colleague) and permit the common one (two pages to the shift manager, where the key is NULL and Postgres treats NULLs as distinct) — a guarantee a reviewer would believe and that is not there. `COALESCE` to a sentinel uuid is a lie in the schema; dropping the target from the key forbids the legitimate double page. **F37's structural guarantee is the conditional UPDATE, which constrains a TRANSITION rather than a POPULATION and therefore needs no index at all** — the third case in this codebase's running argument, beside F13's lock (a count, i.e. read-then-write), F51's lock ("at least one", which no index can express) and F36's index ("at most one", which is exactly what an index says). One non-unique partial index for the poll; **F36's history index is deliberately not copied, because it had named readers and this one would have none.**
- **D3 — The raise has EXACTLY THREE FAILURE MODES: 401, 403, 400.** Nothing about the state of the boutique can refuse a page — not a missing room, a released assignment, a deleted colleague, an empty shift or an alert already open. That sentence is «never silently dropped» expressed as a list AC1 walks. `raised_by` is the session cookie's `StaffContext` and never the body, so `_authorize` is not called at all (the body carries a **target**, not an actor) and `ForbidExtraModel` refuses a body that tries. **The room pointer is resolved with `staff_user_id = actor.id`** — permissively still (unresolved → `NULL`, the page is created), but **her own assignment or none**, because F36's floor payload hands every tile's `RoomAssignment.id` to all five roles and «wrong room» is strictly worse than the safe, designed «no room»: the responder walks to a stranger's curtain. **THE NO-ON-SHIFT-TARGET CASE:** a named target must resolve to a live staffer **and** hold a live `sessions` row (`deleted_at IS NULL AND expires_at > now`, via a **new** `SessionsRepository.has_live_session` — the shipped repo has no such method) — the codebase-consistent reading of *"the targeted device is simply wherever that staffer is signed in"*; if either fails the alert is created with `target_staff_user_id = NULL`, **routed to the shift manager in the data**, and the raise dialog stays open to say so (D16). ⚠ **CORRECTED, and this is Risk 3(a) stated where it is implemented: the role audience `{owner, shift_manager}` CAN be empty.** F51's last-owner advisory lock (`auth/staff.py:9-34`) holds "at least one live **owner**" — a `staff_users` ROW with `deleted_at IS NULL`, read by `count_live_owners` — while reachability is `has_live_session`, a `sessions` row that has not expired. Two meanings of "live": the invariant proves an owner **exists**, never that she is **signed in**. **The role route is therefore NOT probed and can reach zero devices**, and escalation does not stand in for it either — for a NULL target `_for_me` is already True for every elevated caller from t=0, so the thirty-second net adds no audience. A known, accepted ceiling with a named upgrade path (Risk 3(a)); the word "never" must not come back into the source comment. **No on-shift column** — F31 and F57 expose none (Conflict 2), and a live session is a better signal than a checkbox ⚠ **but NOT one that "cannot go stale": the TTL is 12 hours and nothing revokes on going home, so it is an UPPER BOUND on reachability and the thirty-second escalation is what closes the residual** (Risk 3).
- **D4 — Accept is an atomic conditional `UPDATE … WHERE status='open'` setting `status`, `accepted_by` and `acknowledged_at` in ONE statement, plus one `populate_existing=True` re-read.** Rowcount 1 → 200 + audit. **Idempotence is resolved FIRST, keyed on the request** (`accepted_by == actor.id` → 200, no audit, no write) — F36's D6 ordering rule, because otherwise a double-tap tells her by name that *she* has it, as an error. Rowcount 0 → discriminate on the **current status**, which is this feature's only discriminator since there is no index and therefore no constraint name: `accepted` → 409 `SOS_ALREADY_ACCEPTED` with optional `details`; `resolved`/`cancelled` → 409 `SOS_CLOSED`; `open` → an explicit `else: raise` rather than a comment claiming impossibility (F41's finding). Refusals are **404, byte-identical to missing**, never 403 — whose alert it is can only be learned by reading it, so a 403 would be an existence oracle (F36's D7).
- **D5 — Resolve moves from `open` OR `accepted`; cancel moves from `open` ONLY, and the asymmetry is the point. Each verb gets D4's six-step order and its OWN four-row discriminator table**, because prose was not enough: *"rowcount 0 with a live row back is a 200"* and *"cancelling an accepted alert is a 409"* describe the **same input** with no stated precedence, and a builder reading top-down writes the 200 and leaves the 409 unreachable. **The permission check precedes the discriminator**, so a 409 body naming an acceptor never reaches a caller the 404-not-403 rule exists to withhold names from. Cancelling an accepted alert would send a colleague who is already walking to an empty room, so it is a 409 naming her and the remedy is one word over — **resolve**. Rowcount 0 with a live row is a **200 with no audit row** (F36's D7, F34's D8): she wanted it closed and it is closed. Rowcount 0 with no row is a 404. Resolve: raiser, acceptor or elevated. Cancel: raiser or elevated. `SOS_RESOLVED` carries `from_status` **captured into a local BEFORE the write** — the identity-map trap's fourth appearance in this repo, and the only one where the destroyed value is a state.
- **D6 — ESCALATION IS DERIVED AT READ TIME from the SAME `server_now` the envelope carries, and the worker is REJECTED on three grounds. ⚠ TWO booleans, not one: `escalated` (open, unacked, > 30 s) AND `_stalled` (accepted, unresolved, > 2 min).** Without the second, the instant anybody taps «אני מגיעה» the alert stops escalating and stops rising **on every device in the boutique, forever** — and the raiser's screen reads «דנה מגיעה», so she stops looking for help on a signal the product cannot back. Same zero-write mechanism, same shared anchor, one constant and one branch: **the derived boolean is cheaper than the Risk that would otherwise have to carry it.** ⚠ **NO `max(timedelta(0), …)` clamp**, unlike `lib/elapsed.ts` where a negative delta is *renderable*: here the comparison is one-sided against a positive threshold, so a negative delta is already False and the clamp pins **nothing** — its named mutation came back **GREEN** in review and the clamp is deleted rather than left as false confidence. `app/worker.py` ticks at 60 s (`config.py:124`), so a worker-stamped escalation would arrive **up to a full minute late — twice the requirement**; it would introduce a write that **races a concurrent ack**; and it would run `O(tenants)` queries per tick even when no boutique has an open alert. The read-time predicate adds zero latency beyond the poll, cannot race, and is the house compute-on-read pattern (#30's queue positions, F43's ordinals, `card_status()`). Python rather than SQL, and the decisive argument is the **shared anchor**: the elapsed line is computed against `server_now`, so a SQL predicate against `now()` could render an escalated badge beside «כבר 0 דק'». A durable `escalated_at` is the recorded upgrade path. **Escalation changes no audience — a shift manager sees every alert from second zero; it changes whether the OVERLAY rises**, without which she would be interrupted by every page in the boutique and would learn to dismiss them unread.
- **D7 — One audience predicate, computed on the server, twice.** Visibility is a SQL clause (the raiser, the named target, the owner of the alert, or any elevated caller — for whom no clause is added at all); rising is `for_me`, a derived boolean. **The raiser never gets the overlay for her own page** — she is holding a bride's corset and the product must not shout at the person who asked for quiet; she gets the accept on the same tick. Both booleans ride the wire **because the alternative is the audience rule existing twice, in two languages** — and on the server they are pure branches over a `StaffContext` and a row, unit-testable with no database, the shape `test_floor_service.py` already uses.
- **D8 — One migration, one table, one index, one `enable_tenant_rls`; revision id resolved from `alembic heads` at build time and NEVER from this document.** (At the time of writing head is **0019** and **F41 and F58 are in flight** — read that from `alembic heads` and LOOP-STATE, not from here.) Build at head+1 so the branch is self-coherent and its `db` tests run; make the migration the **last commit** so the renumber is one amend; re-resolve immediately before the rebase that precedes the push; **do not open the PR while a lower-numbered migration is unmerged**. What it must prove it did not do: the CHECK and the index pinned **byte-identical from CAPTURED literals** (Postgres deparses `IN (…)` to `= ANY (ARRAY[…])`), the non-primary unique-index count of **0**, `test_every_tenant_id_table_has_forced_rls` green with no edit, and the round trip via **F36's `_parent_of` helper** rather than `downgrade(cfg, "-1")`. The ORM model is the second half and is not optional.
- **D9 — FIVE new routes on F57's floor router (eighteen in total), and NOTHING is tightened — which is a decision, not a default.** `RoleGate` can express only a **pure role predicate** (F36's D8 criterion); every rule here reads the row, so none can live in a gate. `FLOOR_OPEN` grows nine → **fourteen** as route templates; the four F36-tightened paths stay absent, which is what keeps its shipped comment true. `FLOOR_ROUTES` goes thirteen → **eighteen**. **Every second path segment is `floor`, so `vite.config.ts` needs no edit** — `test_spa_serving.py`'s set equality has broken a developer's machine twice while production, CI and the suite stayed green, and `/manage/sos` would have cost that edit for nothing. No rate limiter; the four mutating verbs are CSRF-fenced by method.
- **D10 — The payload is one statement with five LEFT JOINs, and it carries NO CUSTOMER DATUM AT ALL.** That is the feature's largest privacy decision and the app-level poll is exactly why: F36's floor payload carries a client label but is fetched only on two sections by a component that unmounts; this one is fetched on **every** section for the whole shift. And it buys nothing — the responder needs who is calling and which curtain, and an SOS **already names the person in the room**. The three `staff_users` joins carry **no `deleted_at` filter** (the ghost-holder rule: an alert that cannot say who called is worse than one naming a departed colleague); the assignment join carries no `released_at` filter and the rooms join **no `deleted_at` filter** — F36's Risk 1(c), decided there and obeyed here, because **a room label is not personal data**. Every mutation answers the same `SosAlert`; the raise alone answers `{alert, rerouted}`, because `rerouted` is a fact about the **request** and not about the row, which is precisely why it cannot live on the row's shape.
- **D11 — The poll is a PROVIDER in `lib/sos.tsx`, mounted inside App's signed-in return, at 5 s idle and 2 s while any alert is live, WITH THE IDLE STOP DISABLED.** A provider rather than state in `App` because `App` early-returns twice before it could call a hook and `react/rules-of-hooks` is an error in this workspace — `ToastProvider` is the shipped precedent. **The idle stop is disabled because a phone in an apron pocket would otherwise stop receiving pages after ten minutes, silently** — and SC 2.2.2 does not bind, because in the idle state the component renders **nothing** (no content to pause), in the alert state nothing auto-updates (no countdown, no live counter — D15 forbids both), and the dismiss control is the "hide" mechanism. Not folded onto `/manage/floor` for four independently sufficient reasons: the overlay must render over any section; folding would put a customer's name on an app-level loop; it would require lifting floor state above `FloorPanel` (F57's D11); and the two need different tick rates and different idle behaviour. **Three loops on the board screen, and `FloorPanel`'s pause control is kept honest by freezing `SosCentre`'s list while paused — the overlay keeps rising, because pausing a VIEW must never disable the CHANNEL.** Cost handed to F29: **~41 idle / ~57 with an alert** on the board screen, **~11 on eleven sections that polled zero**, `tenants.by_slug` paid three times per beat.
- **D12 — `usePoll` gains TWO optional fields, `intervalMs: number | (() => number)` and `idleStopMs: number | null`, in eight lines read through refs.** ⚠ **The function form is not a convenience**: the shipped tick shape calls `succeeded()` and `reschedule()` in the same microtask chain as the response, so a state-derived gap re-arms the alert-observing tick at 5 000 ms and costs a silent five-second hole exactly when the raiser is waiting — **and the obvious prop-rerender-then-tick test passes over it**, the shape F57's vacuous focus test had. ⚠ **The gap ref is `idleGapRef`, NOT `idleRef`** — `idleRef` already exists at `usePoll.ts:118` holding the timeout handle — and the `null` early return goes **after** the existing `clearIdle()` at `:166`, or a timer armed under a numeric gap survives the switch to `null`. The acceptance rule is F36's D15 one level down: **`BoardSection.test.tsx` and `FloorPanel.test.tsx` pass with ZERO EDITS**, which is the only thing that can tell a faithful extension from a subtly different one. Declined a fifth hand-rolled loop (it would forfeit F34's unmount fix, F57's StrictMode fix, the visibility pause, the backoff and the `{401,403}` rule — the five things the hook exists to stop four builders re-deriving); declined a constant 2 s tick (2.5× the requests on every screen forever, to save two lines).
- **D13 — Four `AuditAction` members, no migration** — the eighth block to rely on `audit_log.action` being plain TEXT with no CHECK. `SOS_RAISED` carries **both** `requested_target` and `target`, because D3's reroute destroys the only record of whom she actually tried to page (`previous_break_started_at`'s reason, third instance) and that pair is the most useful thing a pilot review could ask this table. `SOS_RESOLVED` carries `from_status`, **captured before the write**. A no-op writes no row. **Declined `SOS_ESCALATED`**: there is no escalation event — it is a predicate over a row and a clock, so there is no instant and no writer, and recording one from a read path is exactly the write-on-read D6 rejects.
- **D14 — Two new error codes, `SOS_ALREADY_ACCEPTED` (409, optional `details`) and `SOS_CLOSED` (409, never `details`); `SPEC_ERROR_CODES` goes seven → nine.** The optional `details` is F36's rule for F36's reason — the acceptor's staff row can be removed between her accept and the read, and «{{name}} כבר מגיעה.» with an empty interpolation on a legally binding surface is worse than a sentence that admits it does not know; typed `Record<string,string> | undefined`, never `| null`. **The shipped `_occupied_body` is RENAMED `_body_with_details` and `_OccupiedError` becomes `_DetailedConflictError`** — both private, both two call sites, and shipping a second copy of six lines that must stay identical is worse than a rename; the `__mro__` docstring is preserved verbatim, because parenting a 409 onto the domain-400 base makes the shipped handler answer 400 and leaves the 409 handlers unreachable. **This fires F36's Risk 8, which named this PR as its trigger**, and it stays deliberate on the same three grounds. `ApiError` and `extractError` need no change.
- **D15 — THE FOCUS AND ANNOUNCEMENT CONTRACT, and it is a gate condition.** The overlay is `role="alert"` **per card** — not one wrapper, or a second page would re-announce the first through `aria-atomic` — and is **not** a `<dialog>`, **not** `showModal()`, and **not** `inert` on the rest of the console: each of those moves focus by definition, and this repo has shipped a focus bug four times. It is therefore **visually blocking and interactively non-blocking**, which is the resolution of "impossible to miss" against "must not steal focus": a pointer user dismisses in one tap with no state lost, a keyboard user's caret never moves and her form is intact, **and the alert is announced either way, because `role="alert"` interrupts a screen reader without taking focus — which is the entire reason that role exists.** MOVE A (arrival) is guarded on **`document.activeElement === document.body`**, the exact condition four shipped effects already use, so focus is only ever taken from nowhere and therefore only ever has to be given back to nowhere — ⚠ **which means it fires on a freshly loaded or untouched tab and NOT on a console in use, where a clicked nav row or button holds focus**; ⚠ **and its DESTINATION is the card CONTAINER, never «אני מגיעה»** (DC-1 — an involuntary arrival must not put an irreversible accept under the next Space; the Esc route-in below is explicitly EXEMPT, because a deliberate keypress is a different act and lands on the control); MOVE B lands on `ConsoleShell`'s `<main id="console-main" tabIndex={-1}>`, never `<body>` — **and it must fire on the SUCCESSFUL-ACCEPT path, where `Button`'s `disabled={disabled||loading}` has already blurred the tapped control to `<body>`, which is the only reason the departing-card intent needs an `actedRef` fallback at all**; MOVE C lands on the next remaining card's container; **MOVE D** (a failed action's in-card alert) fires **only when focus was already inside that card**, because copying `FloorPanel`'s unguarded `cardAlertRef.focus()` into this component would be an uninvited focus move on an error path. Controls are **accept then hide**. **Esc bound to the container dismisses** and never to `window` — ⚠ **plus one document-level CAPTURE `keydown` that is the KEYBOARD ROUTE IN**: Esc from *outside* moves focus into the first card's «אני מגיעה», guarded by `dialog[open] === null` (which is what preserves F36's three shipped `<dialog>`s and `SosRaiseDialog`) and by the target not being a `<select>` (RoomsPanel ships one outside any dialog). **Without it an alert announced perfectly to a keyboard user sits behind a Shift+Tab run past her whole section plus the console chrome — an emergency channel that announces and cannot be acted on.** The `role="alert"` element's text is **write-once**: the escalation and stall clauses render in a **sibling outside it**, because `role="alert"` is `aria-atomic` and a text mutation re-announces the whole card assertively. Escalation is a **word** — **«ללא מענה», not «ללא מענה כבר 30 שניות»**, since a boolean has no upper bound and a four-minute page must not state thirty seconds — never a colour; **no countdown and no live counter**, only an absolute `jerusalemTime` instant, which is what keeps D11's SC 2.2.2 argument true. Dismissal is **per-device and in-memory** — but ⚠ **keyed `${id}:${escalated}:${stalled}` so a safety net can re-rise it once, and paired with a persistent re-open affordance whenever the set holds a live alert**, because `SosCentre` exists on 2 of 13 sections and on the other eleven a bare-id dismissal is **total and permanent** — the silent drop this feature exists to prevent. **A terminal poll is never silent either**: a 401 fires `onSessionEnded` → `App`'s own `setStaff(null)`, a 403 or a backed-off loop renders a persistent `sos.channelDown` strip. Overlay action outcomes go through the **shipped app-level `ToastProvider`** (`App.tsx:187`), which is a different surface from `FloorPanel`'s region and not a consolidation candidate. The red is **`bg-danger` / `text-surface-raised`**, the toast's AA-checked pair. **Every MOVE, the Esc route-in, the dismiss key and the strip are mutation-checked**, because F57's own focus test was vacuous and jsdom is why.
- **D16 — `SosCentre` is a CHILD of `FloorPanel`, above `RoomsPanel`, taking its alerts from `useSos()` and everything else from its parent.** A child for three reasons that each rule out the alternatives: it needs the staff list (already there), it needs `paused` (D11's honesty fix), and it must use the **one** `role="status"` region and the **one** SC 2.2.2 control — a third pause button would start to be a defect (F36's D15). **Which control exists is the rendered form of the permission rules** (F57's shipped comment), because a 403 is terminal for the whole floor screen and for three roles that is the entire product going dark. **Two raise entry points, one dialog**: the tile she holds (`assignment.staff_user_id === selfId`, which prefills the room) and the SOS centre (no room, for a staffer at her table — a case the brief does not contemplate). The dialog is the shipped `Modal` with `@boutique/ui`'s `Select` and `Input` — **named, not "a native `<select>`"**, because a bare element loses the label association and the focus ring that axe cannot see is missing. ⚠ **On a REROUTED raise the dialog does NOT close**: it shows «{{name}} לא מחוברת עכשיו…» with one «הבנתי», because the one message the ruling mandates cannot be a transient polite cue delivered at the exact moment a `<dialog>` closes and focus moves — and `rerouted` is a fact about the request, so **no `SosCentre` row can ever say it again.** ⚠ **A FAILED send also keeps the dialog open**, with the note preserved and `sos.error.raiseFailed` — «הקריאה לא נרשמה. נסי שוב — או קראי בקול.» — the one string in the console that names the manual fallback, because `FALLBACK_ERROR_MESSAGE`'s «נסי שוב» is the wrong instruction on this screen. ⚠ **The focus return is `FloorPanel`'s own trigger ref and its own `<h2>` fallback, NOT a reuse of `RoomsPanel.tsx:307-330`** — that effect is keyed on `RoomsPanel`'s `openDialog`, which never changes for a dialog `FloorPanel` owns, so citing it would have shipped focus dropping to `<body>` a fifth time on the surface D15 declares a gate condition; the tile passes its `event.currentTarget` **up** through `onRaise`. **The overlay rising while the dialog is open is resolved by MOVE A's guard with no extra code — and is asserted, because accidental correctness is what a later refactor deletes.**
- **D17 — A new `sos.*` namespace in `he.ts` AND `ar.ts` with the Hebrew standing in untranslated; every state string `FloorPanel` already ships is REUSED unchanged.** ⚠ **`i18n.test.ts` bans `/נשלח|תישלח|בדרך/` across every Hebrew value, and «בדרך» is the natural wording for the single most important button in this feature.** The guard is right and stays; the wording changes: the ack is **«אני מגיעה»**, the raiser's answer is «{{name}} מגיעה.», the raise cue is «הקריאה נרשמה.» and not «נשלחה». ⚠ **And the citation is only TRUE after `HE_F37` is FOLDED INTO `HE`**: `i18n.test.ts` builds `HE` as a hand-folded spread of per-feature constants and its own comment records that a declared-but-unfolded namespace is silently skipped by the resolve check, **both** register guards and the `ar` parity guard. One line, `entries(he.translation, (key) => key.startsWith("sos."))`, spread at `:61-71`. The `sos.*`-scoped assertion is then belt-and-braces over the restored global guard, stating the ban where the block is read rather than leaving it to explain a wording choice nobody would otherwise understand. `rooms.elapsed` / `rooms.elapsedJustNow` are reused across namespaces deliberately, because `lib/elapsed.ts` hardcodes them and a second elapsed implementation is what D17's own no-date-library rule forbids. `MAX_SOS_NOTE_LENGTH` is mirrored through the existing `manage-floor` parity param; **the 30-second window is NOT mirrored**, because the client never computes it — it renders a boolean the server derived, and mirroring a number nothing computes is parity theatre.
- **D18 — a11y is a legal requirement (IS 5568 / WCAG 2.0 AA) and axe is not the coverage — in both directions.** axe cannot see a focus move that never happened (four shipped instances in this repo) and it equally cannot see one that **should not have happened**, which is the new failure this feature could introduce; the four named focus tests are the only coverage and each carries its mutation. axe has **no SC 2.2.2 rule**, so `FloorPanel`'s shipped pause and idle assertions now govern one more region and the freeze-while-paused behaviour needs its own test. One `Badge` per SOS row; `<bdi dir="ltr">` on numbers and bare `<bdi>` on Hebrew; **no truncation of a name, a room label or a note, ever**; 44×44 on both overlay controls and on the tile's fourth control, which must **wrap rather than shrink** at 375px; `prefers-reduced-motion` respected by an overlay that appears rather than animates; `aria-hidden` set on nothing, deliberately. **A manual screen-reader pass is a gate condition on this PR** (e7 Risks), not a deferral to F58.
