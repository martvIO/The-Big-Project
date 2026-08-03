# Spec: F36 — Fitting-room registry + staff↔client↔room↔dress assignment (Epic E7, floor program iteration 3)

**Created**: 2026-08-03 · **Gate 1: standing approval — `interview-2026-07-30.md` §Standing approvals** (Q1's enumerated exceptions are F17, F18, F19, F20, F29, F48; F36 is none of them — no payments, no refunds, no privacy-law text, no billing) · **Design gate: self-approved (ruling 2026-07-31)** — Interview Q2 named exactly two novel interaction patterns for this run, F34's shift board and F42's capacity matrix; E7's screens assemble from F34's board shell and F57's shipped `FloorPanel`, so no prototype and no `design-critic` pass gate this build. **The gate goes away; the design work does not** — the deck and copy deck are build tasks (D17, D18), not review preconditions. · **Effort**: **L** — one migration with three `CREATE TABLE`s and three partial unique indexes, **ten** new routes on a router that already exists, one repository, one payload extension, one new console panel with three dialogs, and the concurrency design that is the whole reason this feature is not an M.
**Spec review**: 41 findings from 3 independent lenses · **40 applied**, **1 rejected** (recorded in *Rejected findings*, below Testing).
**Depends on**: **F57** (`backend/app/floor/` — router, service, schemas; `StaffCardStatus`; `frontend/apps/manage/src/components/FloorPanel.tsx`; `src/lib/usePoll.ts`; `src/lib/roles.ts`; the widened `StaffRole`) · **F34** (`BoardSection.tsx`, D4's six poll mechanisms, the `{401,403}` terminal rule, D11's live-region rule, D14's SC 2.2.2 control) · **F31** (`require_role`, `RoleGate`'s **intersection** composition, `test_staff_role_gating.py`'s default-deny walker) · **F13** (`bookings`, `customers`, and the seat-claim this feature deliberately does **not** copy) · **F8** (`dresses`, `dress_variants` — the dress snapshot's source) · **Feeds**: **F37** (`sos_alerts.fitting_room_assignment_id` points at this feature's row — see Risks 1 and 2 for exactly what F37 gets and what it must not assume), **F58** (take-next and push-assign INSERT into `fitting_room_assignments` inside their own transaction, and add the one column F36 deliberately does not ship — D2), **F41/F42** (E9's alteration tickets attach to the staff↔client record this feature creates).

**What F36 does *not* do.** It does **not** add a second poll loop, a second endpoint family, a second pause control or a second `usePoll` instance. Rooms and occupancy **extend F57's `/manage/floor` payload** (LOOP-STATE's F36 note, in as many words), and the rooms panel is a **child** of the shipped `FloorPanel` rather than a sibling of it (D15). It does not rebuild the staff cards, the break toggle, the freshness line or the announced region — it adds one status value to a derivation F57 wrote to be widened (D12).

---

## Problem

Two staffers walk two brides to the same curtain. That is the entire feature, and it is the one thing on this floor that a screen can settle **absolutely** rather than approximately — occupancy is a concurrency problem wearing a furniture costume.

Today the product can settle none of it:

- **There is no room.** No table in the schema names a physical space in the boutique. `backend/migrations/versions/` runs `0001` through `0016` and the tenant-scoped tables are `boutique_settings`, `availability_*`, `appointment_types`, `dresses`, `dress_variants`, `dress_media`, `terms_versions`, `customers`, `bookings`, `scheduled_messages`, `message_log`, `otp_codes`, `staff_users`, `sessions`, `audit_log`, `payments`, `tenant_gateway_credentials`. A boutique with three fitting rooms has no way to say so.
- **There is no occupancy, and F57 says so on the code.** `StaffCardStatus` is `available | break` and its comment states the reason in writing: *"'occupied' is coming and is deliberately NOT here. F36 gives it a writer — an open `fitting_room_assignments` row — and widens this in the SAME PR"* (`backend/app/models/constants.py:26-38`). `card_status()` carries the same sentence (`backend/app/floor/service.py:44-52`), and `api.ts:387-390` mirrors it on the client (the union itself is `:390`; its comment is `:387-389`). Three files are already written against this feature's arrival.
- **There is no record that a client and a staffer are together in a place.** E9's alteration tickets attach to it, F37's SOS needs it to say *where*, and F58's dispatch needs somewhere to put a customer it just took off the queue. The E7 brief is explicit that F36 → F37 is **forced, not chosen** (pre-decided #37): without the assignment row an SOS says "help" without saying "here".

**What is dangerous here is not the tables.** It is two things. First, the claim: a boutique that can double-book a fitting room has a worse product than one with no rooms panel at all, because the screen would be *authoritative and wrong* in front of a bride. Second — and this is the half a reviewer should spend time on — **F36 puts a customer's name onto a payload three shipped code comments assert carries none** (`floor/router.py:11-14`, `floor/service.py:69-75`, `floor/schemas.py:13-16`) — and it does so on the widest role gate in the product. D9 is where that is answered rather than waved past, and **all three comments are rewritten in this PR** rather than left standing as a false safety claim written by the feature that widened the gate.

## Goal

A boutique types its rooms in once — «חדר 1 / חדר 2 / הבמה» — and never again. A staffer walking a client to a room taps that room's tile and it is **hers**; a second tap on the same room, from anywhere, at the same instant, is refused with the name of the person who has it. She binds the gowns that went in with her. She hands the client to a colleague without the room changing hands twice. She releases, and the room is free on the next tick — ~5 seconds, the same beat everything else on this screen already runs at.

F36 ships **one migration** (three tables, three partial unique indexes, three `enable_tenant_rls` calls), **ten routes on the existing `/manage/floor` router**, **one repository**, **four `AuditAction` members**, **two new error codes**, **one payload extension**, **one status value**, and **no new poll loop, no new router, no new rate limiter, no advisory lock, and no second copy of anything F57 extracted.**

## What already exists to build on (verified against code)

- **The floor module is shipped and is shaped for this.** `backend/app/floor/router.py` mounts `prefix="/manage"` with `dependencies=[Depends(_no_store), Depends(require_role(*StaffRole))]` (`:73-79`), and its docstring already argues every decision F36's routes would otherwise re-argue: seventh `/manage` router, all five roles at router level, tenant from `get_current_tenant(request)` and never `StaffContext.tenant_id`, a fifth local `_no_store` copy, no rate limiter, **real HTTP verbs and a path parameter for the target** (`:44-46` — and it says out loud that `.claude/rules`' RPC/`@QueryValue` guidance is another codebase's Kotlin boilerplate).
- **`RoleGate` composes by INTERSECTION and a per-route gate can only narrow.** `auth/dependencies.py:44-45`; `_gate_role_sets` yields **every** gate in the dependency tree. F57's walker assertion `test_the_floor_roles_reach_exactly_the_floor_routes` classifies on `frozenset.intersection(*role_sets)` **precisely so that F36's tightened routes do not red-fail it** — its comment names F36 by name, and F57's shipped note carries the same warning forward (`LOOP-STATE.md`, F57 `shipped:` — *"F36 and F58 both extend this router and `any(...)` would red-fail a correctly tightened route"*). **F36 is the first customer of that decision** (D10).
- **`StaffCardStatus` was built to be widened by this PR** (`models/constants.py:26-38`), and **two** test modules pin its wire literals by **set equality** so the widening cannot be forgotten on one side — `test_floor_api.py:360` and `test_floor_service.py:370`, both named `test_the_card_status_wire_literals_are_exactly_available_and_break`. `api.ts:390` mirrors the union with the same comment. **Four** files change together and each of them says so.
- **The identity-map trap is documented four times and F57 shipped the fix twice.** `StaffUsersRepository._refreshed` (`db/repositories/staff_users.py:195-223`) is the canonical shape: a guarded `UPDATE … .returning(id)` for *"did I write"*, then a `select(...).execution_options(populate_existing=True)` re-read for what to render, applied **unconditionally** rather than per call site. Its docstring records that dropping the flag *"makes the LOSER of a start-racing-an-end render the WINNER's value"*. F36's release copies it verbatim.
- **Capture-before-write is documented on live code.** `FloorService.end_break` (`floor/service.py:108-116`) captures `previous_break_started_at` into a local **before** the writer runs, with a ⚠ comment saying that `evaluate` synchronization stamps the SET value onto the same identity-mapped instance, so reading it afterwards records `null`. F57's shipped note records that moving that capture after the write **reddens one db test and leaves all 17 fast tests green** — monkeypatched repositories never stamp anything. D8's handover has exactly this shape.
- **The two contrast cases for the concurrency design are both in the tree and both write down their own reasoning.** `booking/service.py:386-389` takes `pg_advisory_xact_lock(hashtext(:tenant_id))` and `:448-457` explains why — the claim must pick the lowest free `seat_index` (`seats = await self._bookings.active_seats_at(...)` then `next((index for index in range(1, slot.capacity + 1) if index not in seats), None)`), which is a **count** of taken seats, i.e. a read-then-write; `:404-411` states that *"a failed flush aborts the Postgres transaction"* and declines to recover, crediting **0009's** partial unique index as the backstop, and `:491-493` catches the `IntegrityError` with *"the index is the backstop"* (the index literal itself is `idx_bookings_slot_seat_unique`, created at `0008_bookings.py:88-92`). ⚠ **These four addresses moved ~130 lines on 2026-08-03 when F19's deposit flow merged into this file.** A reviewer who finds a third set of numbers should re-grep rather than assume drift. `auth/staff.py:9-34` takes a **namespaced** lock and states the other half in writing: *"No unique index can express it: an index expresses at most one of something, and this invariant is at least one."* D3 is the third case and it is neither.
- **`enable_tenant_rls(table)` is one call per table** (`db/rls.py`) and forgetting it fails **a different file's** test — `test_every_tenant_id_table_has_forced_rls` scans `pg_class` for any `tenant_id` table without `relforcerowsecurity` (`tests/test_tenant_isolation.py:203`). Forgetting the `GRANT` fails nothing until the app role touches the table. `0008_bookings.py:107-110` is the trailing loop that does both.
- **The dress snapshot has a written precedent with a written reason.** `0008_bookings.py:52-57`: *"Snapshot columns … are copied at booking time: the owner may rename a type or archive a dress, and a booking must render as what the customer agreed to. `dress_id` is kept alongside so the image resolves at read time."* F36's bindings are that paragraph applied to a room.
- **Dress names and size labels are already PUBLIC.** `app/storefront/service.py:75-100` answers `StorefrontDressListView` / `StorefrontSizeView(size_label, available)` to an **anonymous** visitor on the boutique's own storefront. That is the whole justification for D16's picker: it discloses to a signed-in seamstress strictly less than the boutique already publishes to strangers.
- **`@boutique/ui` already ships the three controls this feature needs, and `Select` already made D16's argument once.** `packages/ui/src/components/Select.tsx` carries the comment *"Native `<select>` — no custom dropdown in v1 (a11y cost not worth it)"*, requires a `label: string`, wires `useId()` → `htmlFor`, `aria-invalid` and `aria-describedby`, and applies `focusRing`; `Input` and `Modal` are exported alongside it (`packages/ui/src/index.ts:9,17,30`). **"A native `<select>`" is not the instruction — `Select` is**, because a bare element loses the label association and the focus ring on a surface where IS 5568 is legally binding, and axe sees the missing label but not the missing ring.
- **"She is physically here" is already a column.** F34 shipped `bookings.checked_in_at` (`models/booking.py:45`), which is the fact D9's whole privacy argument depends on and which D6 step 3 must actually filter on.
- **`usePoll` is extracted, tested and carries F34's unmount fix.** `frontend/apps/manage/src/lib/usePoll.ts` exports `POLL_INTERVAL_MS`, `MAX_BACKOFF_MS`, `IDLE_STOP_MS`, `IDLE_STOP_MINUTES`, `terminalOf`, and a `Poll` with `mode`, `terminal`, `generation()`, `isCurrent()`, `bump()`, `succeeded()`, `failed()`, `reschedule()`, `clearTick()`, `fail()`, `refresh()`, `pause()`, `resume()`. **F36 changes not one line of it** (D15).
- **`FloorPanel.tsx` already owns the mutation discipline F36's room actions need.** `toggle()` (`:280-341`) increments `mutationsRef`, calls `poll.clearTick()` + `poll.bump()`, patches from the **server's** response rather than optimistically, classifies a 403 as terminal via `poll.fail(error)`, treats a 404 as an in-card alert, and re-arms in its `.finally()` *"rather than the success path: a refused toggle must not park the loop either"*. `tick()` (`:155-164`) returns `"suppressed"` while a mutation is in flight and `"held"` on a pointer hold. Every room action rides the same dance (D15).
- **The Vite dev proxy names second path segments by explicit alternation, and a backend test asserts SET EQUALITY against the live route table.** `frontend/apps/manage/vite.config.ts`'s `MANAGE_API` and `tests/test_spa_serving.py:372-400`. `floor` is already in the list. **Every F36 route is under `/manage/floor/…`, so the segment set does not change and `vite.config.ts` needs no edit** — see D10, and see Conflict 7 for the one stale word in that file.
- **`ApiError` carries `{status, code}` and nothing else** (`api.ts:9-19`); `extractError` (`:26-38`) reads `{error: {code, message}}`. D14 extends both by six lines, and states why nothing smaller works.
- **The error envelope already has a dynamic body precedent.** `DomainValidationError`'s handler builds `{"error": {"code": "VALIDATION_ERROR", "message": str(exc)}}` at raise time (`main.py:790-794`) — the 409s in D14 are the same technique with the payload in a `details` object instead of interpolated into English prose.
- **`created_at` is a house standard column, `NOT NULL DEFAULT now()`, on every table** (`models/base.py`, `StandardColumns`). D2 spends it.

## Design

### D1 — `fitting_rooms` is a label, an order and two different kinds of "not in use"

```sql
CREATE TABLE fitting_rooms (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ,
    label TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT true
);

-- The panel's ENTIRE read is "this tenant's live rooms in display order", so
-- one index serves it and the ORDER BY rides it — BOTH keys, which is why
-- `created_at` is in here and not only `sort_order`. D11 orders by
-- (sort_order, created_at); an index carrying only the leading key would leave
-- the planner sorting inside each equal-`sort_order` group, and since
-- `sort_order` defaults to 0 and the registry lets it be omitted, a boutique
-- that never reorders has EVERY room in one group — i.e. the index would supply
-- none of the ordering in the common case. The tiebreak is the whole point: a
-- 5-second repaint that re-sorts rows is a repaint a finger cannot travel
-- across.
CREATE INDEX idx_fitting_rooms_tenant_order
    ON fitting_rooms (tenant_id, sort_order, created_at) WHERE deleted_at IS NULL;
```

`TEXT` not `VARCHAR`, `uuid_generate_v4()`, soft delete, `TIMESTAMPTZ`, `_updated_at_trigger("fitting_rooms")`, `GRANT SELECT, INSERT, UPDATE, DELETE … TO app_user`, `enable_tenant_rls("fitting_rooms")` — the `0008_bookings.py:107-110` trailing loop, unabridged.

**`is_active` and `deleted_at` are two different facts and the feature needs both.** `deleted_at IS NOT NULL` means *the boutique reconfigured and this room is gone from the registry*. `is_active = false` means *the mirror is broken, do not send anyone in there today*. The first removes the row from every read; the second leaves it on the panel, greyed, with **no claim control**, so a staffer looking for a free room can see that room 2 exists and is out of service rather than wondering whether she forgot it. Collapsing them would mean the only way to say "out of service" is to delete the room and re-type it tomorrow, and that would silently orphan history (D2's assignments point at room ids).

**Deactivating an OCCUPIED room is allowed; deleting one is refused.** Deactivation is exactly the "the mirror just broke" case, and evicting a half-dressed bride to satisfy a flag would be the product being clever at her expense — `is_active` stops the **next** claim, not the current fitting. Deletion is refused with **409 `ROOM_OCCUPIED`** naming the occupant (D14), because a soft-deleted room with a live assignment is a row no read surfaces and an occupancy nothing can release.

⚠ **"By construction" is a per-room ROW LOCK, not a hope — and this is the one hidden read-then-write in the feature.** An earlier draft of this spec claimed that the delete's refusal "lets D11's read start from `fitting_rooms`: every active assignment has a live room, by construction." It does not, on its own. The delete is *read occupancy → write `deleted_at`*, which is a **cross-row invariant** — precisely the shape D3 says no unique index can express. Under READ COMMITTED, T1 (delete) sees zero active assignments while T2 (claim) is uncommitted; both commit; the result is a soft-deleted room holding a live assignment. Every consequence is permanent and invisible: the tile is gone from the payload (D11's read filters `deleted_at IS NULL`), so there is **no UI path to release it**; `idx_fitting_room_assignments_staff_active` still holds that staffer's key, so she can never claim another room; and the two occupancy derivations disagree forever — D11's payload derives it from the rooms join (she reads `available`), D12's break routes derive it from the staff index (she reads `occupied`). Recovery needs `psql`.

Writing the guard as `UPDATE fitting_rooms SET deleted_at = … WHERE … AND NOT EXISTS (SELECT 1 FROM fitting_room_assignments …)` does **not** fix it: that is F51's unsafe `count(*)`-against-a-snapshot verbatim, and EvalPlanQual does not re-read other tables.

**The fix is one row lock on the ROOM, and it is not the advisory lock D3 refuses.** Both the delete and the claim take `SELECT … FROM fitting_rooms WHERE id = :id AND tenant_id = :t AND deleted_at IS NULL FOR UPDATE` on the room row before they proceed; the delete then issues its occupancy guard as a **separate statement** (a new statement snapshot taken after the lock is held sees the committed claim) and only then stamps `deleted_at`. Cost: one row lock per room. Nothing that was concurrent becomes serial — two claims on the same room already resolve to exactly one winner, and claims on *different* rooms take different locks. The claim's INSERT is still the unlocked, index-decided statement D3 argues for; what the lock serializes is the delete against the claim, never a claim against a claim. **AC17 + a `db` forced-interleave test; mutation = remove the `FOR UPDATE`.**

**No unique index on `label`, and this is a decision rather than an omission.** `dresses`' own model states the rule for a tenant-scoped name: *"Names are not unique — a boutique legitimately carries one designer model in two colours, and a dress is only ever addressed by id"* (`models/dress.py:10-17`). A room is addressed by id everywhere in this feature; two alcoves a boutique genuinely both calls «הבמה» is not an error the platform should invent a 409 and a Hebrew sentence for; and the registry is a 2–6 row list the owner is looking at while she types. F33's Ruling 3 is the cautionary case in the other direction — a partial unique index whose key frees only on a state change nobody performs — and it does not apply here (soft delete frees this key and the same screen offers it), but the cost/benefit still lands on "no index". **Upgrade path if a pilot boutique asks: a partial unique on `(tenant_id, lower(label)) WHERE deleted_at IS NULL`, the `dress_variants` shape (`models/dress_variant.py:12-17`), plus one error code.**

**No index on `is_active`.** Nothing filters on it — the read returns every live room and the panel greys the inactive ones — so a partial index would serve no reader and cost every write (F57's D2, same sentence, same reason).

**Validation:** `label` stripped, `1 <= len <= MAX_ROOM_LABEL_LENGTH` (**40**), and `sort_order` in the **house form, symmetric**: `sort_order: int = Field(default=0, ge=-MAX_SORT_ORDER, le=MAX_SORT_ORDER)`, importing `MAX_SORT_ORDER = 1_000_000` from `app/catalog/validation.py:48` exactly as `catalog/schemas.py:46,63,72` and `boutique/schemas.py:73,85` already do. **Not `0 <=`** — negatives are the house convention and are how you move a row to the front without renumbering the rest, which is the reorder control the registry dialog ships; and "reuse the shipped constant" while silently halving its range is the confusing half, because a builder copying the shipped `Field(...)` line gets the symmetric bound and the spec's floor would exist only in prose. `MAX_ROOM_LABEL_LENGTH` lives in a new `app/floor/validation.py`, is mirrored in `apps/manage/src/validation.ts`, and gains a **new `MIRRORS` param** (`id="manage-floor"`) in `tests/test_frontend_constant_parity.py` — the house pattern for exactly this, three lines.

### D2 — `fitting_room_assignments`: `released_at` IS the occupancy model, `created_at` IS the claim time, and `queue_ticket_id` is not this feature's to ship

```sql
CREATE TABLE fitting_room_assignments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ,
    fitting_room_id UUID NOT NULL,
    staff_user_id UUID NOT NULL,
    booking_id UUID,
    released_at TIMESTAMPTZ
);
```

No FK constraints anywhere — house rule, and the reason it is safe here is the same reason it is safe on `bookings.customer_id`: every join predicate is spelled out in the repository and every read is tenant-scoped by RLS **and** by an explicit `tenant_id` predicate.

**`released_at IS NULL AND deleted_at IS NULL` is what "active" means, and it is the whole model.** Not a `status` column, not a boolean, not a row that gets deleted. The nullable timestamp is simultaneously the fact ("she is out") and the when, which is what makes the historical row worth keeping at all — and D3's two indexes are predicated on exactly that pair of nulls, so the model and the guarantee are the same sentence.

**No `assigned_at` column — `created_at` is the claim time. This is a deliberate departure from the E7 brief's column list.** The brief names `assigned_at`, and every table in this schema already carries `created_at TIMESTAMPTZ NOT NULL DEFAULT now()` from `StandardColumns` (`models/base.py`). The row is created at exactly the instant of the claim, so `assigned_at` would be a second copy of one fact — the shape F57's D2 declined for `break_ended_at` in as many words (*"two columns to express one boolean"*). **The wire field is still `assigned_at`**, sourced from `created_at`, with a one-line comment in `schemas.py` saying so; the card's «כבר 42 דק'» is the *client's* time in the room and a handover deliberately does not restart it (D8), which is exactly what `created_at` measures and what a separate `assigned_at` would tempt someone to reset. *Upgrade path: if a later feature genuinely needs the clock restarted on handover, that is the day `assigned_at` earns a column and a writer.*

⚠ **`created_at` is DB-generated and therefore NOT freezable, and the two timestamps on this row come from two different clocks.** `StandardColumns.created_at` is `server_default=text("now()")` (`models/base.py:21-22`), i.e. transaction-start time on the **database** host, while D7 stamps `released_at` from the service's injectable **Python** clock. So `released_at < created_at` is representable, and **no `db` test can freeze `created_at`** the way D7's frozen-clock equality assumes. D7's equality assertion is therefore on `released_at` only; `created_at` is asserted as a range or as an ordering, never as an equality. *Declined stamping `created_at` from the service clock on the INSERT to make both freezable: it would be the one table in the schema whose `created_at` does not come from `now()`, for a test convenience, and the ordering assertion costs nothing.*

**`deleted_at` on this table has no v1 writer, and that is not an omission.** No route soft-deletes an assignment — release is `released_at`, and a mis-tapped claim is corrected by releasing it. `deleted_at` is in both of D3's index predicates for the same reason it is on every table in this schema, so a reviewer looking for the missing route should stop looking. *(This is also why the mutation "make the index predicate `WHERE deleted_at IS NULL` only" is the pinned one in the Testing table: the `released_at` conjunct is the one with a writer.)*

**`released_at` is NOT `deleted_at`, and conflating them would be the cheapest-looking wrong answer.** `deleted_at` means *this record is wrong and should not have existed*; a completed fitting is neither. They also mean different things to the indexes: a released assignment must free the room (predicate leaves), a soft-deleted one must free it too (a mis-tapped claim, corrected), and both predicates are in D3's `WHERE` for that reason.

**`booking_id` ships. `queue_ticket_id` does NOT, and that is this spec's largest scope call.** The E7 brief says the assignment carries *"a nullable link to F34's dispatch record"*. **F34 shipped no dispatch record** — it shipped `bookings.checked_in_at`, two endpoints and `BoardSection.tsx` (Conflict 1). The walk-in's dispatch record is F33's `queue_tickets`, which is **unmerged and in flight in another session's worktree**, and the dispatch **action** is F58's. F36's deps are `[F8, F13, F31, F34, F57]` and do not include F33, so:

- F36 ships `booking_id UUID NULL`, whose writer is the claim and whose reader is D9's label resolution.
- **F58 adds `queue_ticket_id UUID NULL` in its own migration, with its writer, in the same PR** — the `ScheduledMessageKind` rule applied to a column instead of an enum value (`constants.py:89-92`: *"pre-adding speculative kinds is exactly the un-lazy thing"*). F58's LOOP-STATE note says *"No new table"*, which is true and is not the same as "no migration"; Risk 3 hands it over so it is not a surprise.
- **An assignment with no client link at all is legal and renders as an anonymous visit.** Both link columns are nullable, so a staffer prepping a room, or claiming for a walk-in before F58 exists, produces a row with no label. That is the *same* render path a retention-deleted ticket takes (D9), which is why the anonymous-visit branch is exercised from day one rather than being dead code that first runs the day F20's sweep deletes something.

### D3 — TWO partial unique indexes, and **INDEX, NOT LOCK** — with both contrast cases named

```sql
-- Pre-decided #31. ONE active assignment per room: this is the structural
-- guarantee the whole feature exists to give, and the predicate is what makes a
-- RELEASED room immediately re-claimable in the same tick.
CREATE UNIQUE INDEX idx_fitting_room_assignments_room_active
    ON fitting_room_assignments (tenant_id, fitting_room_id)
    WHERE released_at IS NULL AND deleted_at IS NULL;

-- Added by the 2026-07-31 ruling. ONE active room per worker. This is what makes
-- the staff card's `occupied` a FACT rather than a guess: the derivation reads
-- AT MOST ONE row per staffer by construction, so it never has to pick.
CREATE UNIQUE INDEX idx_fitting_room_assignments_staff_active
    ON fitting_room_assignments (tenant_id, staff_user_id)
    WHERE released_at IS NULL AND deleted_at IS NULL;
```

Plus one non-unique index for the history read that is **not** in this feature but is one line here and impossible to add cheaply later without a lock on a growing table:

```sql
CREATE INDEX idx_fitting_room_assignments_tenant_created
    ON fitting_room_assignments (tenant_id, created_at) WHERE deleted_at IS NULL;
```

*(Declined the temptation to skip it "until something reads it": the two unique indexes are partial on `released_at IS NULL`, so they are useless for any query over history — including F37's "which assignment was this alert raised in" and F41's ticket attachment — and this table is the one in the feature that grows monotonically. One index, stated cost, named readers.)*

#### The claim is ONE INSERT. There is no advisory lock, and the spec must say why rather than copying one.

```python
# app/floor/service.py — the whole of the claim's concurrency design.
# ⚠ The `try` is OUTSIDE the `async with`, and the INSERT is a CORE
# `session.execute(insert(...))`, not `session.add`. Both halves are
# load-bearing: with `session.add` the flush happens in
# AsyncSessionTransaction.__aexit__, so the IntegrityError surfaces when the
# savepoint block EXITS and a `try` placed inside it never catches anything.
try:
    async with session.begin_nested():             # SAVEPOINT, see below
        row = await self._assignments.claim(session, tenant_id, room_id, staff_id, booking_id)
except IntegrityError as exc:
    # asyncpg's UniqueViolationError is WRAPPED by SQLAlchemy, so the
    # discriminator is `exc.orig`, defensively: a None reads as unrecognised
    # and takes the re-raise branch.
    constraint = getattr(exc.orig, "constraint_name", None)
    ...
```

**Why F13's `pg_advisory_xact_lock` is NOT the precedent to copy.** `booking/service.py:448-457` claims *"the lowest free seat"*: it reads `active_seats_at`, computes `next((index for index in range(1, slot.capacity + 1) if index not in seats), None)`, and inserts. **That is a read-then-write, and only a lock makes it atomic** — two claimants each read `{1}` and each compute `2`, and the unique index then turns one of them into an `IntegrityError` the service has to explain (`:491-493` calls the index *"the backstop"*, and `:404-411` credits **0009's** partial unique index while declining to recover from the aborted flush at all). The lock is primary there because the *value being inserted is derived from a count of existing rows*.

**A fitting room has no seat to number.** The claim inserts `(tenant_id, fitting_room_id, staff_user_id)` — three values every one of which the caller already holds. Nothing is counted, nothing is derived, **the CLAIM has no read whose result the insert depends on**. The statement either violates a unique index or it does not, and Postgres decides that under the index's own concurrency guarantees with no help from us. *(The **delete** is the exception and it is stated as one: it carries a genuine cross-row invariant and is guarded by a per-room `FOR UPDATE`, D1. "No lock anywhere" would have been the false version of this claim.)* **A lock here would buy nothing and cost two things**: every claim in the boutique would serialize behind every other (and, if the key were the bare `hashtext(:tenant_id)`, behind every public booking create — the exact hazard `auth/staff.py:57-61` namespaces its own key to avoid), and the loser would experience a *wait* followed by a refusal instead of an immediate refusal. **An immediate 409 naming the occupant is more useful to a staffer standing in a corridor than a serialized wait that ends in the same answer.**

**Why F51's advisory lock is NOT the precedent either, and this is the sharper of the two.** `auth/staff.py:9-34` writes it out: the last-owner invariant is **"at least one"**, and *"No unique index can express it: an index expresses at most one of something."* It then shows that the obvious single guarded statement is unsafe under READ COMMITTED, because two transactions each evaluate the count against a snapshot missing the other's uncommitted write. **F36's invariant is "at most one", which is exactly and only what a unique index says**, and — unlike a `count(*)` subquery — a unique index is evaluated by the index itself, not against a transaction snapshot. The second inserter blocks on the first's uncommitted key and then gets a violation when it commits. That is the mechanism; there is nothing left for a lock to do.

**The SAVEPOINT, and why it is not a lock in disguise.** A failed flush aborts the enclosing Postgres transaction — `booking/service.py:279-286` states this and declines to recover from it for that reason. But F36 *must* recover: the ruling requires the 409 to **name the current occupant**, and the occupant can only be read after the conflict is known. `session.begin_nested()` issues a `SAVEPOINT`; the `IntegrityError` rolls back to it and leaves the outer transaction alive, so the occupant read happens in the same session, the same tenant context and the same round trip budget. It serializes nothing and blocks nobody. *(First use of `begin_nested()` in this codebase — declined the alternative of opening a second `tenant_session` to read the occupant, which costs another pool checkout, another `set_config`, another BEGIN/COMMIT and a second place for the tenant id to be wrong.)*

**IDEMPOTENCE IS RESOLVED FIRST, AND IT IS KEYED ON THE REQUEST — NEVER ON THE CONSTRAINT NAME.** When staffer S re-claims the room she already holds, the INSERT violates **both** partial unique indexes at once, and Postgres reports only the first index that fails, in `RelationGetIndexList` order — i.e. index OID, i.e. **creation order**. Deriving the idempotence branch from the constraint name would make it an artefact of the order the migration happens to create the two indexes, and it would flip silently after any `REINDEX CONCURRENTLY`, `pg_repack`, or a later migration that recreates one of them. If the staff index reported first, a staffer tapping the room she is standing in would read «היא כבר בחדר 2.» — the screen refusing her with the name of the room she is in.

So: on **any** `UniqueViolationError` from the claim, after the savepoint rollback the service does **one** read keyed on the request —

```sql
SELECT … FROM fitting_room_assignments
 WHERE tenant_id = :t AND fitting_room_id = :room AND staff_user_id = :target
   AND released_at IS NULL AND deleted_at IS NULL
```

A **hit** means "you already have this room" → **200** with that card, no audit row, deterministic whichever index fired. Only on a **miss** does the constraint name pick between the two 409s.

**Which index was violated is what picks the ERROR, and the constraint name is that discriminator and nothing else.** SQLAlchemy **wraps** asyncpg's `UniqueViolationError`, so the read is `getattr(exc.orig, "constraint_name", None)` — spelled defensively, because a `None` must take the re-raise branch. The service matches it against the two index names, declared once as module constants in the repository and imported by the service so a rename cannot drift. An unrecognised constraint name **re-raises** — a 500 on a violation nobody predicted is correct, and silently mapping it to `ROOM_OCCUPIED` would tell a staffer a lie about furniture.

| Violated | Raised | 409 body's `details` | What the staffer reads |
|---|---|---|---|
| `idx_fitting_room_assignments_room_active` | `RoomOccupiedError` | `{"staff_display_name": "דנה"}` | «דנה כבר בחדר הזה.» |
| `idx_fitting_room_assignments_staff_active` | `StaffOccupiedError` | `{"room_label": "חדר 2"}` | «היא כבר בחדר 2.» |
| either, but the occupant read comes back **empty** | the same two errors, **no `details`** | *(absent)* | «החדר נתפס זה עתה. נסי שוב.» / «היא כבר בחדר אחר.» |
| anything else | re-raised → 500 | — | the outage register |

**The occupant read can legitimately come back empty, and a 409 that names nobody is worse than one that says so.** The loser blocks on the winner's uncommitted index key and gets the violation when the winner commits; between that commit and the occupant read the winner can **release** — a fitting can end in the seconds a claim is queued. There is then no occupant to name. `details={"staff_display_name": None}` would break D14's TS type and «{{name}} כבר בחדר הזה.» would render with an empty interpolation on a legally binding surface. So `details` is **optional on both codes** (D14 types it `Record<string, string> | undefined`, never `| null`), and the panel selects `rooms.error.roomOccupiedUnknown` / `rooms.error.staffOccupiedUnknown` when it is absent. **`db` test: `test_a_claim_whose_occupant_released_first_does_not_name_nobody`.**
*Declined a single automatic retry of the INSERT in a fresh savepoint.* It would turn that rare refusal into the success she actually wanted, and it is four lines — but it puts a second write path on the hottest concurrency line in the feature for a case the next 5-second tick corrects anyway, and the copy already tells her to try again. **Recorded as the upgrade path if the pilot ever sees it twice.**

### D4 — `fitting_assignment_dresses` is a child table, not a JSONB array, and the concurrent double-add resolves to success

```sql
CREATE TABLE fitting_assignment_dresses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ,
    fitting_room_assignment_id UUID NOT NULL,
    dress_id UUID NOT NULL,
    dress_name TEXT NOT NULL,
    dress_size TEXT,
    -- Stamped on the soft delete, NULL while the binding is live. One column,
    -- because D13 declines FITTING_DRESS_REMOVED on the grounds that "the row
    -- IS the record" — and a row with no actor answers WHAT left the room and
    -- WHEN, but not WHO took it out, which for a boutique tracking gowns is the
    -- question the trail exists for.
    removed_by UUID
);

-- The read: every live binding for the assignments the payload is rendering.
CREATE INDEX idx_fitting_assignment_dresses_assignment
    ON fitting_assignment_dresses (tenant_id, fitting_room_assignment_id)
    WHERE deleted_at IS NULL;

-- THE THIRD partial unique index. One live binding per (assignment, dress), and
-- the predicate is what lets a removed dress be carried back IN.
CREATE UNIQUE INDEX idx_fitting_assignment_dresses_unique
    ON fitting_assignment_dresses (tenant_id, fitting_room_assignment_id, dress_id)
    WHERE deleted_at IS NULL;
```

**A child table and not a JSONB array on the assignment, for the brief's stated reason and it survives inspection:** two staffers add and remove dresses concurrently, and a JSONB array is a read-modify-write — the loser's write silently drops the winner's dress, with no error anywhere and no index able to say so. The child table makes each add and each remove a single-row statement that cannot lose anything it did not touch.

**`dress_name` / `dress_size` are snapshots, `0008_bookings.py:52-57`'s reasoning unchanged:** the owner may rename or archive a dress mid-fitting, and a card must render what actually went into the room. `dress_id` is kept alongside so the image and the live variant list resolve at read time rather than being copied. `dress_size` is nullable — a sample gown carried in before a size is chosen is an ordinary event, and `bookings.dress_size` is nullable for the same reason.

**Removing a dress is a soft delete, and that soft delete plus `removed_by` IS the audit record** (D13 declines a `FITTING_DRESS_REMOVED` action on exactly this basis): the row survives with `deleted_at` and the actor stamped, so "what was in the room, when did it leave and who took it out" is answerable from the table itself. Without `removed_by` the first two thirds would be answerable and the third would not, and D13's sentence would be claiming something the row cannot say.

**A concurrent double-add is a SUCCESS, not a 409.** Two staffers tapping «שמלה 47» at the same instant both want the dress in the room, and the dress is in the room; telling the second one she lost a race would be telling her she was wrong when she was right — F57's shipped `FloorPanel` already makes this argument for the break toggle (*"F-ok and F-noop announce the SAME sentence, deliberately"*).

⚠ **`ON CONFLICT DO NOTHING` reintroduces the exact lost update this section argues against, so the statement is `DO UPDATE`.** With `DO NOTHING`: T1 soft-deletes binding B (uncommitted); T2 adds the same dress, conflicts against the still-live B, does nothing, answers 200 «נוספה»; T1 commits. The dress is **out** of the room and the staffer who put it in was told it went in — no error, no index that can say so, and add-vs-remove is a pair no other test in the feature covers (AC7 covers add-vs-add and remove-then-re-add *sequentially*). So:

```
INSERT … ON CONFLICT (tenant_id, fitting_room_assignment_id, dress_id)
  WHERE deleted_at IS NULL
  DO UPDATE SET updated_at = :at
  RETURNING id, (xmax = 0) AS inserted
```

`DO UPDATE` **blocks** on T1's uncommitted delete; when T1 commits, `ON CONFLICT`'s re-check finds the row no longer in the partial index and the add re-inserts cleanly. **The resolution rule, stated once: an add and a remove of the same dress serialize on the binding row, and the later commit wins.** `(xmax = 0)` gives the `(wrote, row)` shape F57's writers already use, and `updated_at` is the only column touched on the no-op branch so nothing observable changes. **No `IntegrityError`, therefore no aborted transaction, therefore no savepoint on this path** — the reason the claim needs one (D3) is that it must *report* the conflict, and this one must not. **`db` test `test_an_add_racing_a_remove_does_not_silently_lose_the_add`, mutation: revert `DO UPDATE` to `DO NOTHING`.**

**The two dress routes are deliberately ALL FIVE and carry no ownership check beyond the router gate — a decision, not an omission.** A colleague fetching a second gown for a fitting already in progress is the normal case on a shop floor, and binding or unbinding a dress is not a destructive act on the *holder's* room: release and handover take the room away from her, which is why those two carry the two axes and these two do not. It is recorded here, repeated in D10's `Why` column, stated in D14 as "these two never 403", and — because a permissiveness that arrives by default is invisible — **asserted** in `test_floor_service.py`'s matrix as a positive: *a seamstress may bind a dress to a colleague's assignment*. `removed_by` is what keeps that permissiveness accountable.

### D5 — One migration, revision id resolved at build time, and what it must prove it did not do

**The revision id is NOT in this document, and this sentence is not the source either — LOOP-STATE's MIGRATION CHAIN block is.** At the time of writing `main`'s head is `0016_deposit_flow.py` (F19, merged 2026-08-03, `revision = "0016"` / `down_revision = "0015"`) and **two** other features are in flight and racing for numbers — **F33 and F53**, each in its own worktree, neither controlling the landing order. ⚠ **Do not read that head as current either.** It moved twice on the day this spec was written (F57's 0015, then F19's 0016), which is exactly why LOOP-STATE replaced every fixed assignment with a rule. **Read the head from `alembic heads`, and read the in-flight set from LOOP-STATE's `current:` block. This paragraph is a dated observation; the rule below is the instruction:**

> **BUILD** at `alembic heads` + 1 with `down_revision` = whatever head is on the branch, so the branch is self-coherent and its `db`-marked tests actually run.
> **RENUMBER** at the rebase that precedes the push, re-resolving from `alembic heads` on `main` **immediately** before it.
> **Make the migration the LAST commit on the branch**, so the renumber is one `git commit --amend` touching one file that nothing else references.
> **Do not OPEN the PR while a lower-numbered migration is still unmerged.**

F33's own D15 records that this was **tested, not theorised**: writing a migration whose `down_revision` names a revision living only on another branch makes alembic unable to build the revision map at all — `alembic upgrade head` fails and every `db`-marked test fails with it, so the branch is untestable for its whole life. A *wrong* `down_revision` therefore fails loudly rather than drifting, which is the third of the three properties that make this safe without coordination.

Everything asserted below is keyed to **"after this feature's migration"**, never to a number.

```python
"""fitting rooms: the registry, the assignment and its dress bindings

Revision ID: <alembic heads + 1 at build time>
Revises:     <whatever head is then — NOT hardcoded>
"""
```

The upgrade is three `CREATE TABLE`s in the order rooms → assignments → bindings, the six indexes above, three `_updated_at_trigger(...)` calls, and the trailing loop:

```python
for table in ("fitting_rooms", "fitting_room_assignments", "fitting_assignment_dresses"):
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO app_user")
    for statement in enable_tenant_rls(table):
        op.execute(statement)
```

`downgrade()` is `DROP TABLE IF EXISTS` in reverse order and nothing else — no explicit index, trigger or policy drops (`0008_bookings.py:113-115`). **F36 touches no existing table, so it has nothing to un-touch**, and unlike F57's migration its downgrade cannot fail on live data.

**What the migration must prove it did not do**, as `db`-marked tests rather than as promises:

- **The three partial UNIQUE index definitions pinned byte-identical** (`…_room_active`, `…_staff_active`, `…_dresses_unique` — the three that carry the structural guarantee; the three non-unique ones are performance and are not pinned), read from `pg_indexes.indexdef` after this feature's migration. ⚠ **CAPTURE the literals by running them on a real 16.x server — do not transcribe them from this file.** F34's shipped note and F33's D2 both record the same trap: Postgres deparses, re-parenthesises, schema-qualifies and re-orders predicates, so a literal that merely *looks* right pins nothing and reddens CI. These three are the highest-value tests in the feature, because what they guard against is a *future* edit — the day anybody "simplifies" a predicate, they collide with a pinned literal and a review instead of colliding with nothing.
- **`fitting_room_assignments` carries EXACTLY two unique indexes besides the primary key**, asserted by count: `SELECT count(*) FROM pg_index WHERE indrelid = 'fitting_room_assignments'::regclass AND indisunique AND NOT indisprimary` is **2**. A third one added later — a well-meaning `(tenant_id, booking_id)` say — would silently make a bride's second fitting of the day impossible.
- **`fitting_assignment_dresses` carries exactly one**, same query, same reason.
- **`test_every_tenant_id_table_has_forced_rls` stays green with no edit** — three new `tenant_id` tables, and the test that scans `pg_class` is what catches a missing `enable_tenant_rls` call, in a different file, a long way from here.
- The round trip in both directions, last in the file, inside `try/finally: command.upgrade(cfg, "head")` — these tests mutate the session-scoped schema and leaving it down fails unrelated modules with `UndefinedTable`.

**The three ORM models are the second half of this migration and are not optional.** No model↔migration parity test exists anywhere in `backend/tests/`, so without `models/fitting_room.py`, `models/fitting_room_assignment.py` and `models/fitting_assignment_dress.py` — each `class X(StandardColumns, Base)`, each declaring every column explicitly — every backend line in D6 through D11 is an `AttributeError`. Migration + models are one atomic change (F57's D3, F34's D2, `0008_bookings.py` / `models/booking.py`).

### D6 — The claim: one INSERT, one savepoint, and the 409 names a person

```
POST /manage/floor/rooms/{room_id}/claim
body: { "staff_user_id": uuid | null, "booking_id": uuid | null }
-> Room
```

Ordered exactly:

1. **Authorize on the two axes, before any read.** `staff_user_id` defaults to the caller. If it names somebody else and the caller is not elevated → `NotAuthorizedError`. This is `FloorService._authorize` (`floor/service.py:137-151`) reused **verbatim, by call**, not re-derived: *"the request names only WHOM to toggle, never WHO is asking"* is the same sentence for whom to seat. It runs before any read, so the 403 is not an existence oracle.
   ⚠ **F36 is the first feature in the product to take a target staff id in a BODY, which is the shape `_authorize`'s own docstring names as the hazard** (*"A body-supplied `staff_user_id` doubling as the caller's identity is the one shape that turns 'any staffer on herself' into 'any staffer on anyone'"*). Discharged explicitly here rather than deferred: the body's `staff_user_id` is read **only** as the target and is passed straight into `_authorize(staff_id, actor)`; the actor is the `StaffContext` resolved from the session cookie by `get_current_staff` and **no code path on this route may read the body field as an identity**. F57's break routes take the target in the *path* and `start_break`'s own docstring calls that out deliberately (`floor/router.py:92-94` — *"`staff` is the ACTING identity and comes from the session cookie; `staff_id` is the TARGET and comes from the path"*); this is the first body. **Asserted, not asserted-in-prose:** a claim whose body names a colleague, from a non-elevated caller, must 403 **and never reach the room repository** — the existence-oracle assertion `test_floor_service.py` already uses for the break routes. See Risk 2, which now owns F57's Risk 5 instead of deferring it.
2. **Read the room `FOR UPDATE`** — `WHERE id = :id AND tenant_id = :t AND deleted_at IS NULL AND is_active` — which is the claim's half of D1's per-room lock against a concurrent delete. Missing, deleted, inactive or another tenant's → `DomainNotFoundError` → **404**, one body, indistinguishable. Inactive is a 404 rather than a fifth error code because the panel renders no claim control on an inactive room: reaching this branch means the client was one tick stale, and «החדר כבר לא זמין. הרשימה תתוקן בעדכון הבא.» is the exact `floor.error.notFound` shape F57 already ships for a colleague who vanished.
3. **Read the booking** if `booking_id` is given → 404 if absent, same body. The predicate is `deleted_at IS NULL`, `status <> 'cancelled'`, **`checked_in_at IS NOT NULL`**, and the booking's `starts_at` falling on **today's calendar day in Asia/Jerusalem**. The claim stores the id and **nothing else about the customer** (D9).
   **The check-in predicate is what makes D9's table true rather than aspirational.** D9's load-bearing cell is *"only customers physically in a fitting room right now"*, and `deleted_at IS NULL AND status <> 'cancelled'` alone admits **next month's** booking — its customer's name would then surface on the five-role payload for as long as the assignment stayed open. F34 already shipped `bookings.checked_in_at` (`models/booking.py:45`), which is exactly the "she is in the building" fact, and a claim that ignored it would state the privacy argument more narrowly than the code behaves. This is also the **one** place a timezone legitimately enters this feature — via the shipped Jerusalem day computation, not a new one. **`db` test `test_a_booking_that_has_not_checked_in_cannot_be_bound_to_a_room`.**
   **`pending_payment` is admitted, deliberately.** F19's fifth `BookingStatus` member means "the seat is claimed, the money is not in yet", and `constants.py:84-93` records that *every* owner and customer verb 409s on an unpaid hold. This one does not, and that is the right call: the predicate is `status <> 'cancelled'` because the bride is **physically standing in the boutique having been checked in**, and refusing to name her on a room tile over a deposit is the product being clever at the expense of the person in front of it. Stated because F19's rule elsewhere is the opposite and a reviewer will look for it.
4. **`try: async with session.begin_nested():` INSERT** (Core `session.execute(insert(...))` — D3's snippet). `IntegrityError` → **resolve idempotence first** by the request-keyed read → on a miss, discriminate on `exc.orig.constraint_name` → read the occupant in the surviving outer transaction → `RoomOccupiedError` / `StaffOccupiedError`, with `details` omitted when that read finds nobody (D3, D14).
5. **Audit** `FITTING_ROOM_CLAIMED` in the same transaction, before commit.
6. **Answer the full `Room`**, rendered from the database rather than from the request — F57's D7 contract (*"the panel patches its card from the server's own row and cannot disagree with itself"*), and the reason the panel is not optimistic.

**A claim is NOT idempotent by predicate the way a break is**, and the difference is worth stating because the shipped neighbour is. `break/start` re-tapped is a no-op with a meaningful "the target state already holds". A room re-claimed by the *same* staffer is already the state she wants — but the INSERT violates **both** indexes at once and Postgres reports only one of them, in index-creation order. So idempotence is resolved by a read keyed on `(tenant_id, room_id, target_staff_id)` — **not** by the constraint name — and a hit answers **200 with the existing card and writes no audit row**: the `(wrote, row)` middle branch, in a shape that has to be explicit here because the index cannot express it. Two staffers double-tapping one control get one assignment and one audit row. **`db` test `test_re_claiming_your_own_room_is_a_200_whichever_index_reports`, with the named mutation: create the two indexes in the reverse order in a scratch schema and re-run.**

### D7 — Release is a conditional UPDATE, and rowcount 0 is not an error

```
POST /manage/floor/assignments/{assignment_id}/release  -> Room
```

```sql
UPDATE fitting_room_assignments SET released_at = :at
 WHERE tenant_id = :t AND id = :id AND released_at IS NULL AND deleted_at IS NULL
 RETURNING id
```

then **one** `select(...).execution_options(populate_existing=True)` re-read for what to render — `StaffUsersRepository._refreshed` (`db/repositories/staff_users.py:195-223`) applied to this table, unconditionally, for the reason that docstring gives: *"whether a caller happened to load the row first is exactly the reasoning that has bitten this repo three times."*

**Rowcount 0 with a live row back means somebody already released it, and that is NOT an error.** She wanted the room free; the room is free. **200**, the card rendered from the database's answer, **no audit row** (F34's D8 rule — `{released → released}` noise in the only trail this area has would be worse than silence). Rowcount 0 with **no** row back means the assignment does not exist for this tenant → 404.

`released_at` is stamped from the service's **injectable clock**, not from SQL `now()` — `FloorService.__init__` already takes one (`floor/service.py:56-65`) precisely so the db suite can freeze it and assert an equality rather than a range. The ruling's literal `SET released_at = now()` is satisfied in behaviour; the parameterised form is what makes it testable, and it is the shipped shape one file over.

**Authorization on release is the same two axes as the claim — but it CANNOT run first, and the refusal is a 404 rather than a 403.** The claim's target is a staff id in the body, so `_authorize` is the method's first statement. Release's target is an **assignment id**, and whose assignment it is can only be learned by reading the row. So the order is explicit and different:

> read the assignment (tenant-scoped, `released_at IS NULL AND deleted_at IS NULL`) → **absent → 404** → `staff_user_id != actor.id` **and** the actor is not elevated → **`DomainNotFoundError` → 404**, byte-identical to the missing case.

**Not `NotAuthorizedError`.** A 403 on a real assignment id and a 404 on a fake one would discriminate existence — an oracle, narrow but real, and it would break AC10's "indistinguishable from missing" rule the moment it were applied to an in-tenant id. Answering 404 costs no new code path and keeps the two responses identical. **The Testing section's "and the room repository is never called" assertion therefore applies to the CLAIM and to HANDOVER, never to release** — release is asserted instead as *a non-elevated caller acting on a colleague's assignment gets 404, byte-identical to a nonexistent id*.

Declined "anyone may release any room": a seamstress freeing a colleague's room while a bride is still in it is the one destructive act on this surface, and the elevated path already covers the legitimate case (a shift manager clearing up after someone who went home).

**One exception, and it is D11's ghost case.** When the holder has been soft-deleted from `staff_users` since the claim (F51's staff removal, which has no interaction rule with an open assignment), `staff_user_id` matches nobody, so under the two axes **only an elevated caller can release it**. That is the right answer and it is stated so a reviewer does not read it as a gap — see D11 for how the tile renders.

### D8 — Handover is a guarded UPDATE of `staff_user_id`, not a release-and-reinsert

```
POST /manage/floor/assignments/{assignment_id}/handover
body: { "staff_user_id": uuid }
-> Room
```

```sql
UPDATE fitting_room_assignments SET staff_user_id = :new
 WHERE tenant_id = :t AND id = :id AND released_at IS NULL AND deleted_at IS NULL
 RETURNING id
```

**One statement, and it is why the dress bindings survive for free.** The obvious alternative — release the old assignment, insert a new one — would have to **copy every child row** to the new assignment id, which is a loop, a second failure mode, and a window in which the room is momentarily free and a third staffer can take it. The brief's requirement is *"handing the client to a colleague preserves the room and its dress bindings"*, and mutating one column preserves them by not touching them.

Three consequences, each deliberate:

1. **`created_at` does not move**, so the card's elapsed time stays the **client's** time in the room. That is the number a shift manager actually reads («כבר 70 דק'» is about the bride, not about who is currently with her), and it is D2's argument for not having an `assigned_at` at all.
2. **The `(tenant_id, staff_user_id)` index guards the receiving staffer.** Handing a room to a colleague who already holds another one is an `IntegrityError` → **409 `STAFF_OCCUPIED`** naming her current room. Same savepoint, same discriminator as D6. This is the second index earning its keep on a path that is not the claim.
3. **The assignment id is STABLE across a handover** — which is what makes F37's `sos_alerts.fitting_room_assignment_id` still correct after the room changes hands (Risk 1).

**The audit row carries the value the write destroys.** `FITTING_ROOM_HANDED_OVER` with `details={"from": "<uuid>", "to": "<uuid>"}` — F51's `STAFF_ROLE_CHANGED` shape (`auth/staff.py:251`). ⚠ **`from` is captured into a local BEFORE the writer runs**, `FloorService.end_break`'s ⚠ comment verbatim (`floor/service.py:108-116`): the UPDATE is ORM-enabled DML whose `evaluate` synchronization stamps the new value onto the same identity-mapped instance out of one identity map, so reading it afterwards records the **new** staffer as the **old** one and empties the row of its whole informational content. F57's shipped note records that this exact mutation **reddens one db test and leaves all 17 fast tests green**, because monkeypatched repositories never stamp anything — so the mutation check for this line has to be a `db`-marked test and cannot be anything else (Testing).

Rowcount 0 → **404** (already released; the panel's next tick corrects it).

**Authorization: elevated only, ENFORCED AT THE ROUTE, not in the service** — `dependencies=[Depends(require_role(StaffRole.OWNER, StaffRole.SHIFT_MANAGER))]`, exactly as the three registry routes are tightened, with the service carrying a comment pointing at the gate rather than a second check. This is the one asymmetry on the surface and it is also the one new route where the gate can express the rule: handover's predicate depends on **nothing about the target**, so it is a pure role predicate, which is precisely what `RoleGate` is. D6's and D7's checks are target-dependent (self **or** elevated) and therefore genuinely cannot live in a gate; handover's is not.

Putting it in the service instead would cost two things the earlier draft did not weigh. First, `FLOOR_OPEN`'s shipped comment is *"the exhaustive list of what they may reach"* (`test_staff_role_gating.py:84`) and F57's Risk 1 says it *"must never gain a route without the reviewer asking why"* — adding `handover` to it would make a structural test assert that a seamstress may reach a route she always gets a 403 on, i.e. the test would stop describing the product. Second, it is the shape that produces Blocker-class UI behaviour: a 403 is **terminal** for the whole floor panel (`usePoll.terminalOf` → `"access"` for any 403; `FloorPanel.tsx:349-367` clears every card), so an unreachable route reachable by a rendered control blanks a seamstress's only screen. With the gate, `FLOOR_OPEN` gains **six** new all-five paths and the **four** tightened ones (three registry + handover) are deliberately absent — which is the assertion that the tightening is real.

Declined "the current holder may hand off": it reads as the same act but it is not — a handover *takes* the room from one worker and *gives* it to another who has not consented and may already be busy, and "any staffer may act on herself" does not extend to acting on a colleague's availability. A staffer who wants out releases; a shift manager reassigns.

### D9 — Client PII is NEVER snapshotted; the label is resolved at read time; and what F57's "zero customer data" claim becomes

**The assignment stores `booking_id` and no personal field of any kind.** Not a name, not a phone, not an initial. The card's client label is resolved on every read from the live `bookings` → `customers` rows, and when they are gone the label is `null`.

**This is what keeps data minimisation honest rather than decorative.** Pre-decided #26 auto-deletes a walk-in ticket days after the visit and F20's retention job sweeps a booking on its own clock. A snapshotted name on the assignment would **survive both** — the platform would delete a customer record and quietly keep a copy of who she was, in a table nobody thought of, on a screen five roles can open. Resolving at read time means the historical assignment renders as an **anonymous visit** the instant the source row goes, which is exactly the *"operational history retained, de-identified"* shape pre-decided #34 requires and the epic's Amendment 13 risk names.

**The anonymous-visit render is not a rare path.** It is the *default* for any claim made without a `booking_id` — a staffer prepping a room, or every walk-in until F58 ships `queue_ticket_id` (D2). It is on screen from day one and it is tested from day one.

**But it must not be the ONLY path, and an earlier draft made it one.** `booking_id` is on the claim body, D9 is the longest section in this document, `rooms.anonymous` ships and Risk 5 hands F20 a new processing-activities entry — and nothing in the console could **supply** a booking id. The three floor roles cannot reach `/manage/bookings` at all (`booking/owner_router.py:79-85` gates that router at owner + shift_manager, and `RoleGate` narrows only), and `/manage/floor` carries no bookings. Every claim a seamstress, reception or sales assistant could make would have been anonymous, `client_label` would have been `null` on the surface that matters, E7 success criterion 2 (*"the board shows … the client label"*) would have been unmet, and the privacy widening would have bought nothing. **D16 therefore ships a second one-shot list route, `GET /manage/floor/clients`** — the identical wall, the identical solution, and the same disclosure argument the dress list makes. It is not optional and it is not F58's: F58 adds walk-ins, not booked brides.

**The name is still resolved at read time.** The clients route hands the panel a `booking_id`; the claim stores that id and nothing else; every rendered label comes back out of the live `bookings` → `customers` rows on the next read (D11). Nothing about the picker weakens the no-snapshot rule.

#### The F57 D11 tension, stated and answered — and the three code comments this PR must rewrite

**Two different claims, in two different places, and only one of them survives.** They are usually quoted as one and they are not:

- **D11's claim, which SURVIVES untouched.** `floor-staff-roles.md:495` refuses to merge the board's poll into the floor's, because *the board's* payload carries `customer_name` (`OwnerBookingRow`) and merging *"would put customer names behind a gate that admits a seamstress"*. That is about the **day book**, and F36 does not put the day book anywhere. Two loops stay two loops.
- **The absolute claim, which F36 FALSIFIES.** *"The floor payload carries ZERO customer data"* is not D11's ground — it is stated as a **fact about the code**, in `floor-staff-roles.md:20` (Problem) and, in capitals, in three shipped comments.

Those three comments are the problem, because each is load-bearing for something a later reviewer will audit:

| File | Shipped text | Why it matters |
|---|---|---|
| `floor/router.py:11-14` | *"The floor payload carries ZERO customer data — a name, a role and a status for each member of staff — which is exactly what makes it safe to widen and is why D11 refuses to merge it into the board's poll instead."* | This is **the stated justification for the only router in the product admitting five roles** |
| `floor/service.py:69-75` | *"there is nothing on a card a colleague may not see — a name, a role and a status. That is also what keeps this payload out of D11's merge argument: no customer data, so no gate has to be widened over one."* | The read that builds the payload |
| `floor/schemas.py:13-16` | *"A card is a name, a role and a status, and deliberately nothing else"* | D11 puts `occupancy.client_label` **inside** `StaffCard`, so the card itself now carries a customer's name |

**All three are rewritten in this PR**, to the sentence D9 already lands on: *"the floor payload carries the minimum customer datum required by the person standing on the floor — at most one name per occupied room, for the duration of the fitting, never the day's customer book."* Plus, in `router.py`, the distinction the table below draws. On a surface this spec itself calls legally sensitive (Risk 5, Amendment 13), leaving the widest role gate in the product justified by a sentence that is no longer true is **worse than never having written it**. `test_no_card_carries_an_email_or_any_credential` (`test_floor_api.py:348-357`) is unaffected — `email`, `password_hash`, `tenant_id` and `deleted_at` stay off the card, which is what that test actually pins.

And the distinction that keeps D11's *conclusion* right:

| | `GET /manage/bookings?date=` | `GET /manage/floor` after F36 | `GET /manage/floor/clients` (D16) |
|---|---|---|---|
| Whose names | **every** customer booked today | only customers **physically in a fitting room right now** | only customers **checked in today and still in the building** |
| How many | the boutique's day book, 0–50 rows | ≤ one per room, typically 0–3 | the arrivals so far, typically 0–10 |
| What else about her | appointment type, dress, size, notes, status, arrival, the manage-token surface | **the name, and nothing else** | the name and her appointment time, and nothing else |
| For how long | the whole day, to anyone who opens the section | the duration of the fitting | one fetch, when the panel mounts and after each claim — never on the poll |
| Why a seamstress needs it | she does not | she has been called to room 3 and must know who is in it | she is walking a bride to room 2 and must be able to say which bride |

So D11's rule is unchanged and is restated more precisely: **the floor payload carries the minimum customer datum required by the person standing on the floor, never the customer book.** The two loops stay two loops.

**Declined: first-name-only truncation.** F59's public wall board is specified as position + first name only, and that is right *there* — it is an unauthenticated screen in a room full of strangers. The console is authenticated, staff-only, and the person whose name is on it is standing in the room. Splitting `customers.name` on whitespace to synthesise a first name would be a new, untested string transform on a legally sensitive surface that mangles Hebrew compound names, in exchange for a disclosure reduction of roughly zero. **Declined: no label at all** — a room card that cannot say who is in it does not solve the problem the feature exists for.

**Recorded as a widening and handed on:** Risk 5 gives F20's processing-activities record a fitting-room entry — purpose = floor operations, personal data = the client's name for the duration of an active assignment, retention = none of its own (the label is not stored). Same hand-off shape as F57's Risk 10 for `break_started_at`.

### D10 — All ten new routes hang off F57's floor router, and the tightened four are the intersection classifier's first customers

Every route is on `backend/app/floor/router.py`, whose router-level gate is `require_role(*StaffRole)` (`:73-79`). `RoleGate` composes by **intersection**, so a per-route gate can only **narrow** — which is exactly what the registry needs:

| Method | Path | `allowed_roles` (effective) | Why |
|---|---|---|---|
| `GET` | `/manage/floor` | all five | **unchanged** — F57's, extended in place (D11) |
| `POST` | `/manage/floor/staff/{staff_id}/break/start` | all five | unchanged |
| `POST` | `/manage/floor/staff/{staff_id}/break/end` | all five | unchanged |
| **`POST`** | **`/manage/floor/rooms`** | **owner, shift_manager** | **NEW, tightened** |
| **`PATCH`** | **`/manage/floor/rooms/{room_id}`** | **owner, shift_manager** | **NEW, tightened** |
| **`DELETE`** | **`/manage/floor/rooms/{room_id}`** | **owner, shift_manager** | **NEW, tightened** |
| **`POST`** | **`/manage/floor/rooms/{room_id}/claim`** | **all five** | **NEW** |
| **`POST`** | **`/manage/floor/assignments/{assignment_id}/release`** | **all five** | **NEW** |
| **`POST`** | **`/manage/floor/assignments/{assignment_id}/handover`** | **owner, shift_manager** | **NEW, tightened** — a pure role predicate, so it belongs in the gate (D8) |
| **`POST`** | **`/manage/floor/assignments/{assignment_id}/dresses`** | **all five** | **NEW** — deliberately unauthorized beyond the gate (D4); a colleague fetching a second gown is the normal case and does not take the room away from the holder |
| **`DELETE`** | **`/manage/floor/assignments/{assignment_id}/dresses/{binding_id}`** | **all five** | **NEW** — same decision, same reason; `removed_by` is what keeps it accountable |
| **`GET`** | **`/manage/floor/dresses`** | **all five** | **NEW** — the dress picker's one-shot list (D16) |
| **`GET`** | **`/manage/floor/clients`** | **all five** | **NEW** — the client picker's one-shot list; the only thing that can supply `booking_id` (D9, D16) |

**Ten new routes; thirteen on the router after F36.** Eight of the ten are mutating (`csrf.py:15` — `MUTATING_METHODS = {POST, PUT, PATCH, DELETE}`), two are GETs; the router carries **ten** mutating routes and **three** GETs in total. Those figures drive `FLOOR_ROUTES` (three rows → **thirteen**), which is exported to `test_staff_role_gating.py` and powers the 401 walk, the wiring walk and the `no-store` parametrization — so a count sized from prose rather than from this table is a first-run CI red on the one table a reviewer would otherwise trust.

**The tightened gate is `dependencies=[Depends(require_role(StaffRole.OWNER, StaffRole.SHIFT_MANAGER))]` per route**, composing to that intersection with the router's five, on **four** routes: the three registry verbs and `handover`. **These are the first tightened routes on the floor router, and F57's walker was written for them**: `test_the_floor_roles_reach_exactly_the_floor_routes` classifies on `frozenset.intersection(*role_sets)` with a comment naming F36, and F57's Risk 1 says in writing that a reviewer facing a red here *"must fix the route, never relax the quantifier"*. **`any(...)` would report these four as admitting the floor roles and red-fail a correct route.** The test's `FLOOR_OPEN` table gains the **nine** all-five paths (three F57 + six F36 — claim, release, dresses POST, dresses DELETE, `GET /dresses`, `GET /clients`) as **route templates**, and the four tightened paths are **not** in it — which is the assertion that the tightening is real, and which keeps `FLOOR_OPEN`'s shipped comment (*"the exhaustive list of what they may reach"*, `test_staff_role_gating.py:84`) true.

**Owner **and** shift_manager on the registry, not owner-only.** F51's staff CRUD is owner-only because it creates people who can spend the boutique's money; a room label is not that. A shift manager already reaches settings, hours, appointment types, the catalog and every booking (`boutique/router.py:33`, `catalog/router.py:61`, `booking/owner_router.py:82`), so a room name is strictly less sensitive than what she can already edit — and "room 2's mirror is broken, take it out of service" is an act that has to be possible at 10am without telephoning the owner. Declined owner-only (breaks the deactivate case, which is the one operationally urgent registry act); declined all five (a seamstress renaming the boutique's rooms is not a capability anything asks for, and the registry is configuration).

**Every path's second segment is `floor`, so `vite.config.ts` needs no edit and `test_spa_serving.py` stays green with no change.** That is not an accident and it is not free to get wrong: `test_the_manage_dev_proxy_names_every_manage_api_segment` (`tests/test_spa_serving.py:372-400`) asserts **set equality** between the live route table's second segments and the `^/manage/(…)` alternation, and a mismatch breaks **only a developer's machine** — production, CI and the whole suite stay green while the SPA shell is served where the API should be. It has bitten this repo twice (F52, then F57's plan, which claimed no edit was needed and was wrong). Mounting the registry at `/manage/rooms` would have cost the edit; mounting it at `/manage/floor/rooms` costs nothing and reads better anyway.

**No rate limiter** (no `/manage` router carries one — `floor/router.py:39-42`). The **eight** new mutating verbs are CSRF-fenced by `CsrfOriginMiddleware` because they are mutating methods (`csrf.py:15,48`); the **two** new GETs are not, and their protection is the session cookie and the role gate alone.

### D11 — The payload EXTENDS `/manage/floor`; here is the added shape and what the extra tick costs

**No second poll. No second endpoint on the tick. No `version` field of any kind** — F32 is subsumed and must never be built (`shift-board-checkin.md:8`), so the poll *is* the full refetch and the E7 brief's *"versioned board state with full refetch on version gap"* has no referent in this codebase (Conflict 3).

```jsonc
// GET /manage/floor  — the F57 envelope, extended. `staff` is unchanged except
// for `status`'s third value and the new `occupancy`.
{
  "staff": [
    {
      "id": "0f5f…", "display_name": "דנה", "role": "seamstress",
      "status": "occupied",                    // "available" | "break" | "occupied"  (D12)
      "break_started_at": null,
      // NEW. Non-null EXACTLY when status == "occupied", and null on both other
      // statuses. Denormalised from `rooms` on purpose — see below.
      "occupancy": {
        "assignment_id": "3b7c…",
        "fitting_room_id": "aa10…",
        "room_label": "חדר 2",
        "client_label": "מיכל",                // null = an anonymous visit (D9)
        "assigned_at": "2026-08-03T09:12:00Z"  // the row's created_at (D2)
      }
    }
  ],
  // NEW. EVERY LIVE ROOM — active and inactive — in (sort_order, created_at)
  // order. Inactive rooms ship so the panel can grey them; a room a staffer
  // cannot find is worse than one she can see is out of service (D1).
  "rooms": [
    {
      "id": "aa10…", "label": "חדר 2", "sort_order": 1, "is_active": true,
      // null = free. Non-null = the ONE active assignment the partial unique
      // index guarantees; the read never has to choose between two.
      "assignment": {
        "id": "3b7c…",
        "staff_user_id": "0f5f…",
        // NULLABLE, and D11 says why: a staffer soft-deleted while holding a
        // room leaves this row live with no card on the floor.
        "staff_display_name": "דנה", "staff_role": "seamstress",
        "client_label": "מיכל",
        "booking_id": "77aa…",
        "assigned_at": "2026-08-03T09:12:00Z",
        "dresses": [
          { "id": "d001…", "dress_id": "9f2b…", "dress_name": "ורוניק", "dress_size": "38" }
        ]
      }
    },
    { "id": "aa11…", "label": "הבמה", "sort_order": 2, "is_active": false, "assignment": null }
  ],
  // NEW, one field on the envelope. The server's own instant at serialisation.
  // It is what the elapsed minutes are computed against — see below.
  "server_now": "2026-08-03T09:54:00Z"
}
```

**`occupancy` duplicates three fields that also appear under `rooms`, and that is deliberate.** The alternative is a client-side join — `new Map(rooms.map(r => [r.id, r]))` — which is one line of code and one *architectural* cost: the staff-card renderer would need `rooms` passed into it, coupling the two panels that D15 keeps independent. Denormalising on the server keeps both components pure renderers of their own slice, puts the join in the one place that already holds every row, and costs at most three short strings per occupied room on a payload that is already a list of people.

**`minutes_elapsed` is NOT on the wire, and it is NOT `Date.now() − assigned_at` either.** A server-computed minute count is stale the instant it is serialised; a device-clock-computed one is wrong by however far a boutique tablet's clock has drifted, and «כבר 400 דק'» for a fitting that started twenty minutes ago is the number a shift manager acts on. ⚠ **F57 is not the precedent an earlier draft claimed:** `FloorPanel.tsx:563-575` renders «מאז 11:20» by formatting an **absolute instant** through `jerusalemTime(card.break_started_at)`, which is immune to the device clock — it never subtracts anything. So the envelope gains **one field**, `server_now`, and the client computes

```ts
minutes = Math.floor(((serverNow + (Date.now() - fetchedAt)) - assignedAt) / 60000)
```

— `fetchedAt` being the `Date.now()` captured when the tick resolved, so only the *elapsed* device clock is trusted (drift-free over five seconds) and never the absolute one. One field, no library, and it is still arithmetic on two ISO instants with no timezone in it (D17).

**The read is TWO statements, added to the tick's existing session.** No new `tenant_session`, no new pool checkout, no second `tenants.by_slug`:

1. `fitting_rooms` **LEFT JOIN** active assignments **LEFT JOIN** `staff_users` **LEFT JOIN** `bookings` **LEFT JOIN** `customers` — one outer-join chain starting from rooms, so an unoccupied room still produces a row. There are no FK constraints in this schema (house rule), so **every join predicate is written out here rather than left to a reader to assume**:

   | Join | Predicate | Why exactly this |
   |---|---|---|
   | `fitting_rooms` (driving) | `tenant_id = :t AND deleted_at IS NULL` | inactive rooms **do** ship — the panel greys them |
   | → `fitting_room_assignments` | `tenant_id = :t AND fitting_room_id = rooms.id AND released_at IS NULL AND deleted_at IS NULL` | the exact predicate of D3's index, so the planner uses it |
   | → `staff_users` | `tenant_id = :t AND id = assignment.staff_user_id` — **no `deleted_at` filter** | the holder may have been soft-deleted since the claim; the row survives and the name is not a snapshot, so this is how the tile still says who is in there |
   | → `bookings` | `tenant_id = :t AND id = assignment.booking_id AND deleted_at IS NULL AND status <> 'cancelled'` | a swept booking renders an anonymous visit |
   | → `customers` | `tenant_id = :t AND id = bookings.customer_id AND **deleted_at IS NULL**` | ⚠ **an Amendment 13 erasure is about the PERSON, not her appointment.** F20 soft-deleting `customers` while the booking row survives is the likeliest shape, and without this conjunct her name keeps rendering on a payload five roles can open after the platform told her it was erased — the precise failure D9 exists to prevent, one predicate away. Every shipped customer read already filters it (`db/repositories/customers.py:20,30,45,68`) |

   All five joins are **LEFT**, so an assignment whose source row has been swept still renders a room with `client_label: null`.
2. `fitting_assignment_dresses WHERE tenant_id = :t AND fitting_room_assignment_id IN (…) AND deleted_at IS NULL` — skipped entirely when no room is occupied.

**What the two statements hand back, and what `from_rows` becomes.** `FloorService.floor()` today returns `list[StaffUser]` and `FloorResponse.from_rows(cls, rows: list[StaffUser])` renders it. After F36 it returns one small frozen dataclass — `FloorRead(staff_rows, occupancy_by_staff_id, room_rows, bindings_by_assignment_id)` — and `from_rows` takes that instead. Stated because it is the signature the whole payload is built through and D11's *"two statements"* has to land somewhere; keeping `from_rows` a **pure renderer** of a pre-joined structure is what stops the schema module from growing a second query.

**The ghost holder.** `StaffUsersRepository.soft_delete` (`db/repositories/staff_users.py:225-240`) is F51's shipped staff removal and it has **no interaction rule with an open assignment** — F36 does not add one, because freeing rooms out from under people is a cross-feature edit to F51's service that this feature should not own. The consequence is stated instead of discovered: `list_live` drops her from `staff` (no card, so no `occupancy`), while the rooms join still yields an occupied tile. Hence `staff_display_name` is typed **`string | null`**, hence the `staff_users` join carries no `deleted_at` filter (so the name usually still resolves), hence the states table carries a **"holder no longer on staff"** row, and hence D7 records that only an elevated caller can clear such a tile. One `db` test pins it.

**The cost delta, derived by F34's D3 method and NOT measured** (citations `tenancy/middleware.py:74`, `db/tenant.py:25-29`, `db/session.py:59`):

| Per floor tick, per device | F57 shipped | After F36 |
|---|---|---|
| Sessions opened | 3 | **3** |
| `set_config` + BEGIN/COMMIT | 2 each | **2 each** |
| `SELECT 1` on pool checkout | 3 | **3** |
| Business SQL | 4 | **6** |
| **Total** | ~6 statements / ~11 round trips / 3 checkouts | **~8 statements / ~13 round trips / 3 checkouts** |

So a board screen on one phone goes from ~28 round trips per 5 s (F57's number, two loops) to **~30**, and the arithmetic is shown because Risk 4's whole point is that F29 must be handed a figure that reconciles: **board ~17 (unchanged by F36) + floor ~11 → ~13 = ~30**, where F57's ~28 and its own floor table (`floor-staff-roles.md:507`, `:499-505`) are where the ~17 and the ~11 come from. Risk 4 hands F29 the updated figure rather than letting it rediscover one, and repeats F57's point that the single cheapest lever is still the uncached per-request `tenants.by_slug` (`tenancy/resolver.py:8-9`).

### D12 — `StaffCardStatus` gains `occupied`, in the PR that gives it a writer

```python
class StaffCardStatus(StrEnum):
    AVAILABLE = "available"
    BREAK = "break"
    OCCUPIED = "occupied"   # F36: an open fitting_room_assignments row
```

This is the widening `constants.py:26-38` was written to receive, and F36 is the PR that gives it a writer — the `ScheduledMessageKind` rule satisfied rather than waived. **FOUR files change together and each already says so**: the enum, **two** set-equality assertions on the wire literals (`test_floor_api.py:360` **and** `test_floor_service.py:370`, both named `test_the_card_status_wire_literals_are_exactly_available_and_break` — an earlier draft named only the first, so "three files" was really four), and `api.ts:390`'s mirrored union. A builder who edits one and not the others gets a red test or a type error, which is precisely what F57 built.

⚠ **A fifth shipped assertion goes red on the schema change and is not on any of those lists.** `test_a_toggle_answers_one_card_and_not_the_whole_floor` (`test_floor_api.py:344`) reads

```python
assert set(body) == {"id", "display_name", "role", "status", "break_started_at"}
```

and D11 gives `StaffCard` a sixth key, `occupancy`. **It grows to six and stays a SET EQUALITY** — it is the assertion that catches a seventh field arriving unreviewed on a five-role payload, which on this particular payload is the whole of D9's argument mechanised. Named here because a builder working the enumerated `test_floor_api.py` edit list would otherwise hit an unexplained red on a file this spec claims to have fully enumerated.

**Precedence when a staffer is both on a break and in a room.** `occupied` **wins**. She is in a fitting room with a client; the break is a stale toggle nobody cleared, and telling a shift manager looking for help that a person standing in room 2 is «בהפסקה» is the screen lying about something she can see. `break_started_at` stays on the wire regardless, so the card can still say «(שכחה לסיים הפסקה מ־11:20)» if the deck wants it. **Declined a fourth combined status**: two orthogonal facts in one enum is the shape that forces the impossible-tuple conversation later (F34's D1, F57's D2, both verbatim).

`card_status()` therefore stops being a total function of one nullable column and gains a second argument:

```python
def card_status(row: StaffUser, *, occupied: bool) -> StaffCardStatus:
    if occupied:
        return StaffCardStatus.OCCUPIED
    if row.break_started_at is not None:
        return StaffCardStatus.BREAK
    return StaffCardStatus.AVAILABLE
```

`StaffCard.from_row` (`floor/schemas.py:41-48`) gains the same parameter, and the two break routes pass `occupied=False`… **no.** They must pass the truth: `POST …/break/start` answers a full card, and if that staffer is in a room the card must say `occupied`. So both break writers gain one indexed lookup against `idx_fitting_room_assignments_staff_active` before they build their response — one row, one index, on a path that already opens a session. Stated because "pass False, it's just the break route" is the shortcut that would ship a card contradicting the panel it lands in five seconds later.

**Where the widening actually reaches, counted rather than assumed:** `card_status` has **one** app call site (`floor/schemas.py:46`, plus two in `test_floor_service.py:366-367`); `StaffCard.from_row` has **three** (`floor/schemas.py:56`, `floor/router.py:97`, `floor/router.py:106`). Four sites in all — the two `router.py` ones are the break writers above, and `schemas.py:56` is `FloorResponse.from_rows`, which is the one that renders the whole payload and whose signature D11 replaces.

#### What the staff card RENDERS, because the shipped badge is a binary and would say «פנויה» about her

The shipped card is `const onBreak = card.status === "break"` (`FloorPanel.tsx:523`) feeding `<Badge variant={onBreak ? "warning" : "success"}>{t(onBreak ? "floor.statusBreak" : "floor.statusAvailable")}</Badge>` (`:556-557`). With `status: "occupied"` that ternary falls to the **else** branch and renders **«פנויה»** — the card saying a staffer standing in a fitting room is available, which is exactly the lie this section exists to prevent, one word over. The since-line is guarded the same way (`:566`) and would also vanish. So:

- the badge becomes a **three-way on `card.status`**, with a new `floor.statusOccupied` = **«תפוסה»** (feminine, matching «פנויה» / «בהפסקה»), the variant chosen so the **word** carries it (D18) and never the colour;
- an **occupancy line** renders whenever `occupancy !== null`: «בחדר {{room}} עם {{client}} · כבר {{minutes}} דק'», with `rooms.anonymous` substituted for `{{client}}` when `client_label` is null, room label and client name in bare `<bdi>`, the minute count in `<bdi dir="ltr">`, computed against `server_now` (D11);
- both keys go in D17's table **and** in `copy.md`, and a **new** `FloorPanel.test.tsx` block asserts an occupied staffer's card shows the word, the room and the client and does **not** show «פנויה». (AC15's zero-edit rule is untouched: no shipped block asserts an occupied card, because none could exist.)

Without this, D11's whole reason for denormalising `room_label`, `client_label` and `assigned_at` onto the staff card buys nothing — three wire fields with no reader — and the E7 brief's *"per-staffer cards … client label, minutes elapsed"* goes unbuilt.

### D13 — Four `AuditAction` members, no migration, and the handover carries the value it destroys

`audit_log.action` is plain `TEXT` with no CHECK (`0003_auth.py:71-79`) — the **seventh** block to rely on that fact (F15's seven, F34's two, F51's five, F57's two, F17's, and **F19's**, whose `DEPOSIT_HOLD_OPENED` / `DEPOSIT_HOLD_EXPIRED` / `DEPOSIT_LATE_*` block merged on 2026-08-03 at `models/constants.py:228-245` and says the same thing in its own comment).

| Member | Value | Written by | `details` |
|---|---|---|---|
| `FITTING_ROOM_CLAIMED` | `fitting_room_claimed` | a claim that inserted | `{"room": "<uuid>", "assignment": "<uuid>", "staff": "<uuid>", "booking": "<uuid>\|null"}` |
| `FITTING_ROOM_RELEASED` | `fitting_room_released` | a release that wrote | `{"room": "<uuid>", "assignment": "<uuid>", "staff": "<uuid>"}` |
| `FITTING_ROOM_HANDED_OVER` | `fitting_room_handed_over` | a handover that wrote | `{"assignment": "<uuid>", "from": "<uuid>", "to": "<uuid>"}` |
| `FITTING_ROOM_DELETED` | `fitting_room_deleted` | a registry soft delete | `{"room": "<uuid>", "label": "<the label being removed>"}` |

`actor_id = actor.id`, `entity = str(<room or assignment id>)`, written in the same transaction before commit (F15's D2 shape). **A no-op writes no row** (F34's D8): a second release, a claim that resolved to the caller's own existing assignment, and a duplicate dress add all changed nothing.

**Declined `FITTING_ROOM_CREATED` / `FITTING_ROOM_UPDATED`.** Both are non-destructive, both are visible on the screen that performed them, and `created_at` / `updated_at` already time them. The trail is still write-only in v1 (F15's Risk 7, F34's Risk 7, F57's Risk 8 — F53's activity log is the first read surface), so every action added now is a line with no reader; the four above earn it because they are the only record of a destructive or an occupancy-changing act. **Declined `FITTING_DRESS_ADDED` / `_REMOVED`**: the binding row *is* the record — it is soft-deleted, so it survives with `deleted_at` **and `removed_by`** stamped and answers "what was in the room, when did it leave and **who took it out**" from the table itself, at a volume (a dozen per fitting) that would swamp the four rows above. ⚠ **The `removed_by` column is what makes that sentence true.** Without it the row answers *what* and *when* and cannot answer *who* — and since D4 deliberately admits all five roles to both dress routes with no ownership check, "a colleague emptied someone else's room" would otherwise be recorded nowhere at all. One nullable UUID in a migration this feature already writes, stamped by a route that already holds `actor.id`, is a smaller diff than an action stream nothing reads until F53.

`FITTING_ROOM_DELETED` carries the **label** and not just the id, for `previous_break_started_at`'s reason (F57's D8): the row it names is soft-deleted and its label may be re-typed onto a new room tomorrow, so an id alone records that something was removed and cannot say what.

### D14 — Two new error codes, one `details` key, and everything else reuses a shipped 404

| Condition | Status | Code | New? |
|---|---|---|---|
| No session / expired | 401 | `NOT_AUTHENTICATED` | no — app-wide |
| A role outside all five | 403 | `NOT_AUTHORIZED` | no — F31's generic body |
| Non-elevated caller acting on a colleague; non-elevated handover | 403 | `NOT_AUTHORIZED` | no — same generic body, raised in the service (F57's D6, reused by call) |
| Unknown / deleted / **inactive** room · unknown or released assignment · unknown binding · another tenant's anything | 404 | `NOT_FOUND` | no — `DomainNotFoundError`, `main.py:796-798` |
| Room label empty, too long, `sort_order` out of range | 400 | `VALIDATION_ERROR` | no — `DomainValidationError`, `main.py:790-794` |
| **Room already claimed** (also: deleting an occupied room) | **409** | **`ROOM_OCCUPIED`** | **YES** |
| **Target staffer already holds another room** (claim or handover) | **409** | **`STAFF_OCCUPIED`** | **YES** |
| Non-elevated caller acting on a colleague's **assignment** (release) | **404** | `NOT_FOUND` | no — deliberately not a 403, D7 |
| Adding or removing a **dress** on any live assignment, by any of the five | — | — | **never 403** — D4's recorded decision, asserted in the service matrix |
| Re-claim by the same staffer · second release · duplicate dress add | **200** | — | not errors, by D6/D7/D4 |
| Mutating request from a foreign origin | 403 | `CSRF_ORIGIN_MISMATCH` | no — `csrf.py:15-16,48` |
| Backend down / 5xx | — | — | no — backoff, not terminal |

`test_floor_api.py`'s `SPEC_ERROR_CODES` grows from four to **seven** and stays asserted by set equality.

**The two 409s carry a `details` object, and that is a real extension of the error envelope.** The shipped shape is `{"error": {"code", "message"}}` with every body a module constant. The ruling requires the 409 to **name the current occupant**, and:

- the `message` is English prose the console never renders for a *mapped* code (`StaffSection.tsx:18-23` is the shipped pattern — mapped codes get Hebrew from i18n, unmapped ones fall through to `errorMessage`), so interpolating the name into it puts the datum where the UI cannot reach it;
- a second `GET` to discover the occupant races the release it is trying to describe, and would be a request issued *because* something went wrong;
- waiting for the next 5-second tick to answer "who has it" is precisely the 5 seconds of a bride standing in a corridor that this feature exists to delete.

```jsonc
{ "error": { "code": "ROOM_OCCUPIED",
             "message": "This fitting room is already claimed.",
             "details": { "staff_display_name": "דנה" } } }

{ "error": { "code": "STAFF_OCCUPIED",
             "message": "That staff member is already in a fitting room.",
             "details": { "room_label": "חדר 2" } } }
```

Built at raise time by their handlers, the `DomainValidationError` technique (`main.py:790-794`). `ApiError` gains `readonly details?: Record<string, string>` and `extractError` reads it when present (six lines, `api.ts:9-38`). **`details` appears on these two codes and nowhere else**, and a fast test asserts that every *other* body in `main.py` is unchanged — the set of dynamic bodies is a thing a reviewer should be able to enumerate.

⚠ **`details` is OPTIONAL on both codes, and typed `Record<string, string> | undefined` rather than `| null`** — deliberately, so the `{"staff_display_name": null}` shape cannot be constructed at all. D3 records the case: the occupant can release between the violation and the occupant read, leaving nobody to name, and «{{name}} כבר בחדר הזה.» rendering with an empty interpolation on a legally binding surface is worse than a sentence that admits it does not know. The panel selects on the presence of `details`:

```jsonc
{ "error": { "code": "ROOM_OCCUPIED",  "message": "This fitting room is already claimed." } }
// → rooms.error.roomOccupiedUnknown  «החדר נתפס זה עתה. נסי שוב.»

{ "error": { "code": "STAFF_OCCUPIED", "message": "That staff member is already in a fitting room." } }
// → rooms.error.staffOccupiedUnknown «היא כבר בחדר אחר.»
```

**Declined: one code with a discriminating `details`.** Two causes, two Hebrew sentences, two remedies (take another room vs. release her other room first). One code would push the branch into the frontend as a `details`-key sniff, which is a worse place for it than an error code.

### D15 — `RoomsPanel` is a CHILD of the shipped `FloorPanel`: one poll, one pause control, one announced region

`App.tsx` is **not touched**. `SectionKey` stays eleven members, `NAV` stays eleven rows, `Nav.test.tsx`'s counts stay owner ten / shift-manager eight / floor-roles one. The whole feature lands inside the `board` and `floor` branches that already render `<FloorPanel/>` (`App.tsx:175-181`).

```tsx
// FloorPanel.tsx, inside the existing <section>
<RoomsPanel
  rooms={floor?.rooms ?? null}
  selfId={selfId}
  role={role}
  mutate={mutate}          // the extracted dance — see below
  onCue={setCue}
/>
{/* …the shipped staff list, unchanged… */}
```

**Why a child and not a sibling.** LOOP-STATE's ruling is *"do not add a second poll loop"*, and F57's D11 forbids lifting floor state above `FloorPanel`. A sibling would need the rooms from somewhere: either a second `usePoll` (forbidden) or state in `App` (forbidden). A child receives them as props from the component that already owns the tick. **This also fixes an a11y problem before it exists**: one updating region gets **one** SC 2.2.2 pause control and **one** `role="status"` cue region. The board screen still carries two pause controls (board + floor) and F36 does **not** add a third — F57's D12 said two is the answer rather than a defect *provided their accessible names distinguish the regions*, and three would start to be a defect.

**`mutate(fn)` is extracted from the shipped `toggle()` and is this feature's one refactor of F57's code.** `FloorPanel.toggle` (`:280-341`) performs a five-part dance every room action needs identically: increment `mutationsRef`, `poll.clearTick()`, `poll.bump()`, run, classify a terminal error through `poll.fail`, then in the `.finally()` decrement and `poll.reschedule()` when the count reaches zero. Copying it into `RoomsPanel` would be six chances to drop the re-arm — the mistake whose F34 form was *"the loop survived unmount"* and whose F57 form the shipped comment names (*"a refused toggle must not park the loop either, or the panel silently stops converging the first time anybody acts"*).

> **Acceptance rule, the D10 precedent applied one level down: `FloorPanel.test.tsx`'s shipped break-toggle, focus, cue, pause, idle and terminal assertions must pass with ZERO edits after the extraction.** They are the only thing that can tell a faithful refactor from a subtly different one. New `it(` blocks are added freely; **an edit to an existing expectation means the extraction is wrong.**

#### ⚠ WHICH CONTROL EXISTS is the rendered form of the two axes — carried across from F57 rather than left implied

**A 403 is TERMINAL for the whole floor screen, and for the three floor roles that is the entire product going dark.** `usePoll.terminalOf` returns `"access"` for **any** 403 (`lib/usePoll.ts:100-108`), `poll.fail(error)` stops the loop permanently, and `FloorPanel.tsx:349-367` then returns the terminal `<section>` with `floor.accessEnded` and **clears every card**. So a seamstress who taps a control the server will refuse does not get an in-tile alert — she gets a blank screen and a reload button, and the poll never restarts until she reloads.

F57 avoided this by **never rendering a control the caller may not use**: `const mayToggle = isSelf || ELEVATED.has(role)` (`FloorPanel.tsx:530`), with the shipped comment at `:525-529` — *"Which control EXISTS is the rendered form of D6's two axes… no disabled button, no lock glyph, no «אין לך הרשאה» line, no tooltip. The absence is cosmetics; the control is the server's check."* An earlier draft of this spec cited F57's D6 for the **service** check and never carried the **render** rule across. It is carried across now, explicitly, for four controls:

| Control | Rendered only when |
|---|---|
| handover («העברה לעמיתה») | `ELEVATED.has(role)` |
| release («שחרור») | `assignment.staff_user_id === selfId \|\| ELEVATED.has(role)` |
| registry trigger — **both** the empty-state CTA «הוספת חדר» *and* the populated-state «ניהול חדרים» | `ELEVATED.has(role)` |
| the claim's `staff_user_id` field | never sent as anything but `selfId` unless `ELEVATED.has(role)` |

**No disabled buttons, no lock glyphs — absence**, per F57's comment. An AC and a `RoomsPanel.test.tsx` block assert each of the four is **absent** for `role="seamstress"` and present for `owner`, so the 403-is-terminal rule stays unreachable **by design rather than by luck**. (Note the earlier draft named only the empty-state CTA as elevated-only and left the populated-state «ניהול חדרים» trigger unqualified — which is the one a boutique with rooms actually sees.)

**Layout: rooms above the staff list.** A staffer opens this screen to find a free room; the staff cards are the reference, the rooms are the action. The freshness line and the pause control stay where F57 put them — first stop inside the panel, before any content, because *"a 2.2.2 mechanism placed after the content it governs is reachable only by walking the list that is repainting under the walk"* (`FloorPanel.tsx:434-440`).

**The pointer hold matters more now, not less.** `holdRef` exists because a break starting on card 2 grows it ~20px and slides every control below it (`FloorPanel.tsx:83-88`). A room being claimed grows its tile by a staffer line, a client line and a dress list — considerably more than 20px — directly above the tile a finger is travelling toward. The mechanism is unchanged and the comment gains the rooms case.

**The registry dialog's data contract, because it lives inside a component that repaints every five seconds.** There is no registry list endpoint, so `RoomsRegistryDialog` renders from the polled `rooms` prop — and `holdRef` does not help, because it consumes **one** tick on `pointerdown` and typing fires no pointer events (`FloorPanel.tsx:155-164`). A tick landing while the owner is halfway through «חדר 4», or with a delete-confirm open, would re-render the rows from server data, and this spec's own "NOT optimistic, patch from the server's row" discipline makes that a **reset** rather than a merge. So, stated as a contract:

> `RoomsRegistryDialog` **seeds its editable rows from `rooms` ONCE at open** and does not re-read from the poll while open. It re-seeds on close, and on any successful write from **that write's own response**.

**Do NOT reach for `poll.pause()`.** The pause control's accessible name would then announce a state the user did not choose — F57's D12, the reason there is one named control per region and not a hidden second pauser. Two states join the dialog's list: *a room changed underneath the open dialog* (the seeded row is kept; the next open shows the truth) and *the row being confirmed for deletion has vanished* (→ 404, close the confirm, re-seed). `RoomsRegistryDialog.test.tsx` drives a tick with a **dirty input** and asserts the input keeps its value.

**No `usePoll` change.** Not one line of `lib/usePoll.ts`. Stated because four features are queued to import it and a change here would be four features' problem.

### D16 — TWO one-shot list routes, both `@boutique/ui` `Select`s, because `RoleGate` narrows only

```
GET /manage/floor/dresses  ->  { "dresses": [ {"id", "name", "sizes": ["38","40"]} ], "truncated": bool }
GET /manage/floor/clients  ->  { "clients": [ {"booking_id", "client_label", "starts_at"} ], "truncated": bool }
```

**One wall, twice.** `catalog/router.py:61` gates the catalog at owner + shift_manager and `booking/owner_router.py:79-85` gates the bookings router at the same two, and `RoleGate` **narrows only** — there is **no per-route way** to admit a seamstress to either (F57's D4). Widening either router is exactly what F57's Risk 1 exists to prevent. So the floor router answers both lists itself, minimally.

**`GET /manage/floor/dresses`** — fetched **once, when the dress dialog opens**; never on the poll. Live dresses only, `ORDER BY sort_order, name`, `LIMIT 500`. **What it discloses is strictly less than the boutique's own storefront publishes to anonymous strangers**: `app/storefront/service.py:75-100` already answers dress names and size labels with availability to an unauthenticated visitor. No price, no description, no media, no `reserved` flag, no stock quantity.

**`GET /manage/floor/clients`** — the route without which `booking_id` has no producer anywhere in the console (D9). Today's non-cancelled bookings for this tenant that are **`checked_in_at IS NOT NULL`** and whose `starts_at` falls on today's calendar day in Asia/Jerusalem — i.e. **the people physically in the building**, which is the same minimisation argument D9 already makes for the payload, not the day book. It answers `booking_id`, `client_label` and `starts_at` and **nothing else**: no phone, no notes, no dress, no size, no status, no manage token, no `customer_id`. `ORDER BY starts_at`, `LIMIT 200`, same `truncated` flag.
**Fetched twice at most, and never on the tick:** once when `RoomsPanel` mounts, and again after any successful claim. Two triggers, both existing code paths, no timer and no cache. *Named ceiling: a bride who checks in after the panel mounted appears only after somebody claims a room, or on the next page load.* That is acceptable for a 5–10 row list on a screen that gets reloaded every shift; **upgrade path if the pilot complains — refetch it on the release path too, which is one more `.finally()`.** *(Declined folding it onto the poll: that would put every checked-in customer's name on the 5-second five-role payload, which is precisely the day book D9 refuses.)*
⚠ **Parked, not blocking:** `/manage/bookings` is owner + shift_manager, so in v1 **only** those two roles can check anyone in — which means a boutique whose reception role does the arrivals will see an empty client list and every claim will be anonymous. That is F34's gate, not F36's, and the remedy is F34 widening its check-in route, not F36 widening this list.

**`truncated` renders one line pointing at the «שמלות» section (dresses) or at the board (clients)** — F34's `limit=50` precedent for the same class of honesty (*"a hidden bride is the one failure a board may not have"*).

**The controls are the shipped ones, named — not "a native `<select>`".** `Select` from `@boutique/ui` (`packages/ui/src/components/Select.tsx`, exported at `packages/ui/src/index.ts:17`) already carries this decision and its own comment already makes this argument: *"Native `<select>` — no custom dropdown in v1 (a11y cost not worth it)."* It also requires a `label: string`, wires `useId()` → `htmlFor`, `aria-invalid` and `aria-describedby`, and applies `focusRing`. Written as "a native `<select>`", a builder reasonably renders a bare element and loses the label association, the error wiring and the focus ring — on a surface where IS 5568 / WCAG 2.0 AA is legally binding, and where **axe catches the missing label but not the missing focus ring**, which is the same blind spot D18 spends a section on. So:

- **dress dialog**: `Input` for the filter box + `Select` (dresses, filtered) + `Select` (that dress's sizes) + «הוספה» `Button`, inside the shipped `Modal`. Filtering is client-side — no `?q=`, no debounce, no server-side search, no second request.
- **claim, on the free tile itself**: one `Select` of today's clients, defaulting to «ללא לקוחה», beside the «תפיסת החדר» `Button`. **No dialog** — no focus trap to write, no return contract to test, no fourth component; one tap if she does not care which bride, two if she does.

Every `Select` needs a `label`, so `rooms.dressPick` / `rooms.sizePick` / `rooms.clientPick` are in the copy deck as **labels**, not placeholders. **Declined an ARIA combobox**: the combobox pattern is the single most commonly mis-implemented widget in the spec and this is a legal surface. **Declined a new dependency**: the ladder's third rung — the platform already ships the control, and this decision has already been reviewed once.

`dress_size` is optional in the request; a gown carried in before a size is chosen binds with a null size and the card renders the name alone. `booking_id` is optional on the claim; the default is the anonymous visit (D9).

### D17 — i18n: a new `rooms.*` namespace, Hebrew only, `ar` untranslated

New keys in `apps/manage/src/i18n/he.ts` **and** `ar.ts`, with the approved Hebrew standing in untranslated in `ar.ts` — Interview Q3, pre-decided #47, the 2026-07-31 languages ruling, and `ar.ts`'s own mechanics (**never** empty strings; `lng` and `fallbackLng` stay `"he"`; no switcher; the tri-lingual top bar stays deferred). Flat dotted keys, the shipped `floor.*` shape (`he.ts:608-655`, opening at `"floor.heading": "צוות בקומה"`; `he.ts:553-565` is F34's `board.*` block, not this one).

| Key | Hebrew |
|---|---|
| `rooms.heading` | «חדרי מדידה» |
| `rooms.empty` | «עדיין לא הוגדרו חדרי מדידה» |
| `rooms.emptyCta` | «הוספת חדר» |
| `rooms.free` | «פנוי» |
| `rooms.inactive` | «מחוץ לשירות» |
| `rooms.claim` | «תפיסת החדר» |
| `rooms.claimAria` | «תפיסת החדר — {{room}}» |
| `rooms.release` | «שחרור» |
| `rooms.releaseAria` | «שחרור — {{room}}» |
| `rooms.handover` | «העברה לעמיתה» |
| `rooms.elapsed` | «כבר {{minutes}} דק'» |
| `rooms.anonymous` | «ללא לקוחה מקושרת» |
| `rooms.dresses` | «שמלות בחדר» |
| `rooms.addDress` | «הוספת שמלה» |
| `rooms.removeDressAria` | «הסרה — {{dress}}» |
| `rooms.error.ROOM_OCCUPIED` | «{{name}} כבר בחדר הזה.» |
| `rooms.error.STAFF_OCCUPIED` | «היא כבר בחדר {{room}}.» |
| `rooms.error.roomOccupiedUnknown` | «החדר נתפס זה עתה. נסי שוב.» — the 409 with no `details` (D3, D14) |
| `rooms.error.staffOccupiedUnknown` | «היא כבר בחדר אחר.» — same |
| `rooms.error.notFound` | «החדר כבר לא זמין. הרשימה תתוקן בעדכון הבא.» |
| `rooms.holderGone` | «אשת הצוות שתפסה את החדר כבר לא ברשימה.» — D11's ghost holder |
| `rooms.occupancyLine` | «בחדר {{room}} עם {{client}} · כבר {{minutes}} דק'» — on the **staff** card (D12) |
| `floor.statusOccupied` | «תפוסה» — the staff card's third badge word (D12); the `floor.*` namespace, because it sits beside `floor.statusAvailable` / `floor.statusBreak` (`he.ts:636-637`) |

plus `rooms.manage` / `rooms.manageTitle` / `rooms.label` / `rooms.order` / `rooms.active` / `rooms.add` / `rooms.save` / `rooms.delete` / `rooms.deleteConfirm` / `rooms.cancel` / `rooms.claimedCue` / `rooms.releasedCue` / `rooms.handedOverCue` / `rooms.dressAddedCue` / `rooms.dressRemovedCue` / `rooms.dressFilter` / `rooms.dressPick` / `rooms.sizePick` / `rooms.dressTruncated` / `rooms.labelTooLong` / `rooms.labelRequired`, the client picker's `rooms.clientPick` / `rooms.clientNone` («ללא לקוחה») / `rooms.clientsTruncated`, and the handover dialog's `rooms.handoverTitle` / `rooms.handoverPick` / `rooms.handoverConfirm` / `rooms.handoverNobody` (D8, `RoomHandoverDialog`). **The canonical key list is the copy deck (`.planning/design/screens/fitting-rooms/copy.md`), not this table** — the F57 precedent, where `copy.md` outranked D13's prose and three corrections landed there first.

⚠ **`rooms.dressPick` / `rooms.sizePick` / `rooms.clientPick` / `rooms.handoverPick` are `Select` LABELS, not placeholders** — `@boutique/ui`'s `Select` requires `label: string` (D16), so each is a required prop and must carry an approved Hebrew string rather than being invented at build time.

**Reuse before invention.** `floor.refresh`, `floor.pause*`, `floor.resume*`, `floor.paused*`, `floor.idleStopped`, `floor.staleAt`, `floor.staleBody`, `floor.updatedAt`, `floor.sessionEnded`, `floor.accessEnded`, `floor.reload` and `staff.loadFailed` are **all shipped and all reused unchanged** — the rooms panel is inside `FloorPanel`'s poll, so it inherits every one of its states and must not spell any of them a second way (F57's F-10 argument, which is the one place reusing a key from a *more* restricted namespace was right).

**No new formatter.** `lib/jerusalem.ts`'s `jerusalemTime` already renders with `timeZone: JERusalem` (`jerusalem.ts:35`), so `scripts/qa-greps.sh`'s unzoned-formatter grep gains nothing to find. Elapsed minutes are arithmetic on two ISO instants and involve no timezone at all — **stated because "elapsed time" invites a date library, and it must not.** No `he`/`ar` parity guard is invented (F15's Risk 5, inherited by F34, F57, and again here).

### D18 — a11y: what axe cannot see on this surface, and the three focus moves that need named tests

IS 5568 / WCAG 2.0 AA is **legally binding** here (pre-decided #38), not a nicety. axe must return **zero** violations — and axe is **not** the coverage, because:

- **axe cannot see a focus move that never happened.** This repo has shipped that exact bug class **three times** — F56 on the storefront, F34 on the board, F57 on this very panel (a successful poll unmounted the focused in-card alert and dropped focus to `<body>` five seconds later with no user action) — and axe walked past all three. `@boutique/ui`'s `Button` is `disabled={disabled || loading}`, so the browser blurs the tapped control the instant a request starts. **Every room action is that shape.** Three named, non-vacuous tests:
  1. **A failed claim moves focus to the tile's alert** — keyed on the error state, not raised in the handler, because the alert node does not exist when `setError` runs. **The failure path is the one that gets forgotten** (F34's success path compensated and its catch path did not).
  2. **A successful claim returns focus to the tile's now-«שחרור» control** — the control does not unmount, it renames, exactly like the break toggle; guarded on `document.activeElement === document.body` so it cannot steal focus from wherever she moved it.
  3. **A room that leaves the list while holding focus hands focus to the panel heading** — the registry dialog deleting the room whose tile has focus. F51's shipped pattern (`StaffSection.tsx:80-92`), no new string.
  4. **Closing the dress dialog returns focus to the tile's «הוספת שמלה» control**, falling back to the panel heading when that control is gone. The native `<dialog>` returns focus to its trigger for free (`packages/ui/src/components/Modal.tsx:35-49`) — but the trigger sits on a tile that has just **repainted from the mutation response**, so F51's `isConnected` fallback question is live and is what this test pins. **The 404 collision is resolved explicitly: when an add fails because the assignment was released, the dialog closes and focus goes into the TILE'S ALERT — move 1 wins over the native return.** Stated because the native return fires second and would otherwise win, and because "the dialog closes and the tile's alert takes over" (the states table) says which alert appears and not where focus lands, whose default outcome is `<body>`.
  5. **A poll tick that removes the open dialog's assignment closes the dialog and moves focus to the tile's control, or to the heading — never `<body>`.** The poll is only *suppressed* while a mutation is in flight (`FloorPanel.tsx:155-164`); it keeps ticking with a dialog merely **open**, so a colleague releasing the assignment unmounts the tile and the dialog under the user's hands with focus inside. That is F57's own shipped MAJOR (*"a successful poll unmounted the focused in-card alert and dropped focus to `<body>` five seconds later with no user action"*) reproduced one level deeper, and axe sees none of it. The same rule governs `RoomHandoverDialog`.
  ⚠ **Each of these must be mutation-checked.** F57's shipped note records that its own success-path focus test was **VACUOUS** — jsdom does not blur a disabled element, so the entire restore effect could be deleted with the suite green. A test that passes with its mechanism removed is not a test.
- **axe has no rule for SC 2.2.2.** F36 adds no new control (D15) — it inherits `FloorPanel`'s — but the shipped pause and idle assertions now govern a second updating region and **must not be cut as redundant with the axe row**.
- **The poll never writes into the announced region** (F34's D11, verbatim, non-negotiable). `role="status"` carries user-initiated outcomes only: the claim cue, the release cue, the handover cue, the dress cues, the pause, the idle stop, the terminal alert. A room being claimed by a colleague repaints its tile **silently**. ⚠ The cue is written **only when its value actually changes** — assigning a byte-identical string to a text node still produces a `childList` mutation inside `role="status"` (F34's F-7, and `FloorPanel.tsx:194-201` carries the warning); the test must drive **several consecutive ticks with the cue already populated**, because a single-tick assertion passes against the broken version whenever the cue starts empty.
- **Occupancy is never colour alone.** «פנוי» / «תפוס» / «מחוץ לשירות» are words, and so is the staff card's «תפוסה» (D12). A tile's `Badge` may accompany the word and may never replace it — F51's shipped rule (*"The WORD carries the role; the colour never does"*, `StaffSection.tsx:312`) and, closer to hand because it is about a **state** word rather than a role word, `FloorPanel.tsx:554` (*"The WORD carries the state; the colour never does"*).
- **One `Badge` per tile**, and it is the occupancy — the deck's P-2 for the staff card, applied here so a tile's single pill means one thing. The **staffer's role** on an occupied tile is therefore muted words in a bare `<bdi>` under her name, `FloorPanel.tsx:560-562`'s shape, and **never a second `Badge`**.
- **Reorder is a labelled `<input type="number">` bound to `sort_order`, never drag-and-drop.** Stated because "reorder" left as a bare verb invites drag, whose most common implementation is a WCAG 2.1.1 keyboard failure that **axe cannot see** — the same ladder rung and the same legal reasoning D16 uses to refuse the combobox. Validated `-MAX_SORT_ORDER … MAX_SORT_ORDER` against the mirrored constant (D1), 44×44, focus ring, and a keyboard-reachability assertion in `RoomsRegistryDialog.test.tsx`.
- `<bdi dir="ltr">` around every numeric run (elapsed minutes, times, sizes), **bare `<bdi>`** around Hebrew free text (display names, room labels, dress names) — forcing LTR on a Hebrew name reverses its words. **No truncation and no ellipsis on a client label or a room label, ever**: a panel that abbreviates makes two people look like one.
- 44×44 minimum on every control, visible focus ring, the panel heading an `h2` under the shell's single `h1`, no shimmer / pulse / flash on refresh (`prefers-reduced-motion`).
- **The registry `Modal` needs a focus trap and Esc-to-close** — the shipped `@boutique/ui` `Modal` provides both; the test that matters is the **return**: on close, focus goes back to the «ניהול חדרים» trigger, and when that trigger is gone (the dialog deleted the last room and the empty state re-rendered) to the heading. F51's `deactivateTrigger` / `isConnected` fallback is the shipped shape.

---

## API surface

| Method | Path | Body | Answers | Admits |
|---|---|---|---|---|
| `GET` | `/manage/floor` | — | `FloorResponse` (**extended** — D11) | all five |
| `POST` | `/manage/floor/rooms` | `{label, sort_order?}` | `Room` | owner, shift_manager |
| `PATCH` | `/manage/floor/rooms/{room_id}` | `{label?, sort_order?, is_active?}` | `Room` | owner, shift_manager |
| `DELETE` | `/manage/floor/rooms/{room_id}` | — | `OkResponse` | owner, shift_manager |
| `POST` | `/manage/floor/rooms/{room_id}/claim` | `{staff_user_id?, booking_id?}` | `Room` | all five (self, or elevated on anyone) |
| `POST` | `/manage/floor/assignments/{assignment_id}/release` | — | `Room` | all five (self, or elevated) |
| `POST` | `/manage/floor/assignments/{assignment_id}/handover` | `{staff_user_id}` | `Room` | **owner, shift_manager** (**tightened at the route** — D8) |
| `POST` | `/manage/floor/assignments/{assignment_id}/dresses` | `{dress_id, size_label?}` | `Room` | all five, **no ownership check** (D4) |
| `DELETE` | `/manage/floor/assignments/{assignment_id}/dresses/{binding_id}` | — | `Room` | all five, **no ownership check** (D4) |
| `GET` | `/manage/floor/dresses` | — | `FloorDressList` | all five |
| `GET` | `/manage/floor/clients` | — | `FloorClientList` | all five |

**Ten new routes, thirteen on the router.** All thirteen carry `cache-control: no-store` from the router-level `_no_store`; the **eight** new mutating verbs are CSRF-fenced by method (`csrf.py:15,48`), the **two** new GETs are not. Bodies use `ForbidExtraModel` where a body exists (the house form); the two `DELETE`s and `release` take none.

**Every mutation answers the full `Room`** — ONE shape, the same one `/manage/floor`'s `rooms[]` elements carry (`id`, `label`, `sort_order`, `is_active`, `assignment: RoomAssignment | null`) — so the panel patches one tile in place from the server's own row and cannot disagree with itself (F57's D7 contract, and the reason nothing here is optimistic). *There is no separate `RoomCard` type.* An earlier draft named the mutations' answer `RoomCard` and the registry's answer `Room`, which implied two shapes for one row; the registry's answer is simply a `Room` whose `assignment` is usually `null`, and collapsing them removes an interface, a naming question and a mismatch between the `api.ts` type list and the API table.

---

## Frontend changes

| File | Change |
|---|---|
| `apps/manage/src/api.ts` | `StaffCardStatus` gains `"occupied"`; `StaffCard` gains `occupancy: Occupancy \| null`; `FloorResponse` gains `rooms: Room[]` **and `server_now: string`** (D11); new `Room`, `RoomAssignment`, `DressBinding`, `Occupancy`, `FloorDress`, `FloorDressList`, `FloorClient`, `FloorClientList` interfaces — **there is no `RoomCard`; mutations and the payload answer the same `Room`**; **`ApiError` gains `readonly details?: Record<string,string>` and `extractError` reads it** (D14); **ten** new methods on the exported `api` object, one per new route |
| `…/components/FloorPanel.tsx` | **`mutate(fn)` extracted from `toggle()`** and passed down; renders `<RoomsPanel/>` above the staff list; `holdRef`'s comment gains the rooms case. **The staff card's `Badge` becomes a three-way on `card.status`** with `floor.statusOccupied`, and gains an **occupancy line** when `occupancy !== null` (D12). **Its shipped tests pass UNEDITED — that is D15's acceptance rule**; the badge and occupancy assertions are NEW blocks, because no shipped block asserts an occupied card |
| `…/components/RoomsPanel.tsx` | **new** — tiles (label, occupancy word, staffer name, **her role as muted words in a bare `<bdi>`, never a second `Badge`** — E7 criterion 2 names it and D11 puts `staff_role` on the wire for it, client label, elapsed minutes, dress list), the claim control **plus its inline client `Select`**, the release and handover controls **rendered only when the caller may use them** (D15), the per-tile alert and its focus moves, the empty state (CTA for elevated, none otherwise), the greyed inactive tile, the **holder-gone** tile |
| `…/components/RoomsRegistryDialog.tsx` | **new** — the owner/shift-manager `Modal`: add, rename, **reorder via a labelled `<input type="number">` bound to `sort_order` — never drag-and-drop** (D18), activate/deactivate, delete-with-confirm. Seeds its rows from `rooms` **once at open** and never re-reads from the poll while open (D15). F51's `StaffSection` shape, including its focus-return fallback |
| `…/components/RoomDressDialog.tsx` | **new** — `Input` filter + dress `Select` + size `Select` + «הוספה» `Button`, all from `@boutique/ui` (D16). One `getFloorDresses()` per open, client-side filter. Carries D18's focus moves 4 and 5 |
| `…/components/RoomHandoverDialog.tsx` | **new** — the shipped `Modal`, one `Select` of colleagues built from the `staff` array **the poll already carries** (no new endpoint: filter to `id !== assignment.staff_user_id`, and exclude cards whose `status === "occupied"` so the 409 `STAFF_OCCUPIED` is usually **prevented** rather than explained), confirm + cancel. Elevated callers only, so the trigger does not exist for the other three (D15) |
| `…/lib/usePoll.ts` | **no change** — not one line (D15) |
| `…/lib/roles.ts` | **no change** — `roleLabelKey()` already answers the staffer's role on a tile |
| `apps/manage/src/App.tsx` | **no change** — `SectionKey` stays eleven, `NAV` stays eleven (D15) |
| `apps/manage/src/validation.ts` | `MAX_ROOM_LABEL_LENGTH`, mirrored from `app/floor/validation.py` (D1) |
| `…/i18n/he.ts`, `…/i18n/ar.ts` | the `rooms.*` namespace — **both files**, Hebrew untranslated in `ar`. Transcribed from `copy.md`, which is the single source for both columns (D17) |
| `…/__tests__/RoomsPanel.test.tsx` | **new** |
| `…/__tests__/RoomsRegistryDialog.test.tsx` | **new** |
| `…/__tests__/RoomDressDialog.test.tsx` | **new** |
| `…/__tests__/RoomHandoverDialog.test.tsx` | **new** |
| `…/__tests__/FloorPanel.test.tsx` | **existing blocks unchanged** (D15's acceptance rule); new blocks for the composition |
| `…/__tests__/i18n.test.ts` | an `F36 rooms keys resolve` block, the shape F15/F51/F52/F17/F57 each have |
| `…/__tests__/Nav.test.tsx` | **no change** — and that is an assertion, not an omission: the counts staying owner ten / shift-manager eight / floor-roles one is what proves no twelfth section was added |
| `vite.config.ts` | **no change** — every path's second segment is `floor` (D10) |
| `scripts/qa-greps.sh` | **no change** (D17) |
| `test_frontend_constant_parity.py` | **one new `MIRRORS` param**, `id="manage-floor"` (D1) |

### Every state each surface can be in

**The rooms panel** (all inherited from `FloorPanel`'s poll unless marked NEW):

| State | Render |
|---|---|
| Initial load | `FloorPanel`'s existing `Skeleton` inside a `Card`; no pause control yet (nothing is auto-updating) |
| **Empty — no rooms configured yet** (NEW) | `EmptyState` with `rooms.empty`; **CTA «הוספת חדר» for owner/shift_manager only**, no CTA and no body for the other three — a seamstress cannot fix it and telling her to would be a dead end |
| Loaded, some free | tiles in `sort_order`; free tiles carry «פנוי» + the claim control |
| **All rooms occupied** (NEW) | every tile shows its holder, its client and its elapsed minutes; **no panel-level "full" banner** — the tiles already say it, and a banner would be a second thing to keep true. The panel does *not* offer a queue, a wait or a suggestion (out of scope) |
| **A room out of service** (NEW) | greyed tile, «מחוץ לשירות» as a **word**, no claim control |
| **Holder no longer on staff** (NEW) | the tile stays occupied and renders `rooms.holderGone` in place of the name when `staff_display_name` is null (D11); **a release control only for elevated callers**, since the two axes cannot match a person who is gone (D7) |
| **The client list** (NEW) | loading (the `Select` disabled with its label present) · loaded · **empty → the `Select` still renders with «ללא לקוחה» alone, and the claim proceeds anonymously** · truncated at 200 · load failed → the `Select` is absent and the claim is anonymous-only, never a blocked claim |
| **A room released underneath you** (NEW) | the claim 409s or 404s → per-tile alert, focus moves into it, «הרשימה תתוקן בעדכון הבא» — and the next tick keeps that promise, clearing the alert and returning focus to the tile's control (F57's shipped `reclaimFocusRef` path, extended to tiles) |
| **A room claimed underneath you** (NEW) | 409 `ROOM_OCCUPIED`, per-tile alert **naming the occupant** |
| **Your target is already in another room** (NEW) | 409 `STAFF_OCCUPIED`, per-tile alert naming her room |
| Failed poll with tiles on screen | tiles kept, freshness line marked stale, «רענון» — F57's shipped behaviour, unchanged |
| First-fetch failure | `staff.loadFailed` in the outage register — shipped, reused |
| Session or permission ended (401/403) | the shipped terminal panel; tiles cleared. For the three floor roles this is the whole product going dark |
| Paused / idle-stopped | the shipped freshness row and body line |
| Claim/release/handover in flight | the tile's control `loading`, the tile not repainted (the poll is `"suppressed"`) |

**The registry dialog:** empty (no rooms), populated, row in flight, label invalid (field-local 400), `sort_order` out of range (field-local 400), delete blocked by an occupancy (**409 `ROOM_OCCUPIED` naming the occupant** — the one place a registry action meets the concurrency design), delete confirmed, load failed, closed-and-focus-returned, **a room changed underneath the open dialog** (the seeded row is kept; the next open shows the truth — D15), **the row being confirmed for deletion has vanished** (→ 404, close the confirm, re-seed).

**The dress dialog:** loading, loaded, **truncated at 500** (one line pointing at «שמלות»), filter matches nothing, no dresses in the catalog at all, dress chosen / size chosen, add in flight, add failed (404 assignment released → **the dialog closes, the tile's alert takes over, and focus goes INTO that alert** — D18 move 4 resolves the collision with the native `<dialog>` return), **the assignment removed by a poll tick with the dialog open** (dialog closes, focus to the tile's control or the heading, never `<body>` — D18 move 5).

**The handover dialog:** open with a colleague list · **empty — no other staffer is free** (`rooms.handoverNobody`; occupied colleagues are excluded so the 409 is usually prevented rather than explained) · chosen · confirm in flight · **409 `STAFF_OCCUPIED` naming her current room** (the residual race the exclusion cannot close) · **404 — the assignment was released underneath the open dialog** (dialog closes, focus to the tile's alert) · cancelled-and-focus-returned. Trap and Esc come free from the native `<dialog>` (`packages/ui/src/components/Modal.tsx:35-49`); **the RETURN is what needs the test.**

---

## Acceptance criteria

Each maps to a named test; `db` marks the ones needing real Postgres.

- [ ] **AC1** — An owner adds, renames, reorders, deactivates and deletes a room; a shift manager can do all five; **reception / sales_assistant / seamstress get 403 on every one of them**, and the walker proves it structurally. → `test_floor_api.py`, `test_staff_role_gating.py::test_the_floor_roles_reach_exactly_the_floor_routes`
- [ ] **AC2** — A claim on a free room answers a `Room` naming the staffer, writes one `FITTING_ROOM_CLAIMED` row, and the room is occupied on the very next `/manage/floor`. → `test_floor_rooms_db.py`, `test_floor_api.py`
- [ ] **AC3** — **A second claim on an occupied room is structurally impossible**, proven by a forced-interleave pair to the F13/F51/F57 standard, and the loser is told **who currently holds the room**. → `db` `test_a_second_claim_landing_in_the_gap_is_refused_and_names_the_occupant`
- [ ] **AC4** — **One worker holds at most one room**: claiming a second room for a staffer who already holds one is refused and names her current room, under the same forced interleave. → `db` `test_a_worker_cannot_hold_two_rooms`
- [ ] **AC5** — Releasing frees the room **for the next claim in the same tick**; a second release is a 200 that writes nothing. → `db` `test_a_released_room_is_immediately_reclaimable`, `test_a_second_release_writes_nothing`
- [ ] **AC6** — Handing over preserves the room, the `created_at` and **every dress binding**, and the audit row carries the **outgoing** staffer. → `db` `test_a_handover_preserves_the_bindings_and_records_the_previous_holder`
- [ ] **AC7** — Two staffers adding the same dress concurrently produce **one** binding and two 200s; a removed dress can be carried back in. → `db` `test_a_concurrent_double_add_yields_one_binding`, `test_a_removed_dress_can_be_re_added`
- [ ] **AC8** — **No personal field is stored on any of the three tables**, asserted structurally: the column list of all three is pinned; an assignment whose **booking** is soft-deleted renders `client_label: null`; **and an assignment whose CUSTOMER is soft-deleted does too** (the Amendment 13 erasure shape, one join predicate away from rendering an erased person's name on a five-role payload — D11). → `db` `test_the_assignment_stores_no_personal_column`, `test_a_deleted_booking_renders_an_anonymous_visit`, `test_a_deleted_customer_renders_an_anonymous_visit`
- [ ] **AC9** — The `/manage/floor` payload carries rooms and occupancy on the **same** request; a staffer in a room reads `status: "occupied"` and `occupancy` non-null; `occupied` beats `break`. → `test_floor_api.py`
- [ ] **AC10** — Tenant B can neither read nor claim nor release nor bind a dress to **anything** of tenant A's; every attempt is a 404 indistinguishable from missing. → `db` `test_fitting_rooms_isolation.py`
- [ ] **AC11** — Three new `tenant_id` tables, three `enable_tenant_rls` calls, and `test_every_tenant_id_table_has_forced_rls` green with **no edit**. → `db` `test_tenant_isolation.py`
- [ ] **AC12** — The three index definitions are pinned byte-identical after this feature's migration, and the assignment table carries exactly two non-primary unique indexes. → `db` `test_migrations.py`
- [ ] **AC13** — The panel is Hebrew-first RTL on `packages/ui` tokens, ships every `ar` key **byte-identical to its approved Hebrew value** (`ar[key] === he[key]` for every `rooms.*` key — the stated rule, asserted; "non-empty" would pass on an English string or a `TODO`), and **axe returns zero violations**. → `i18n.test.ts`, `RoomsPanel.test.tsx`
- [ ] **AC14** — A failed room action **moves focus into the tile's alert**; a successful one returns focus to the tile's control; a deleted room holding focus hands it to the heading. Each proven **non-vacuous by a named mutation**. → `RoomsPanel.test.tsx`
- [ ] **AC15** — `FloorPanel.test.tsx`'s shipped expectations pass **unedited**, `lib/usePoll.ts` has a **zero-line diff**, and `Nav.test.tsx`'s three counts are unchanged. → the D15 acceptance rule, checked by `git diff`
- [ ] **AC16** — `vite.config.ts` is unchanged and `test_spa_serving.py::test_the_manage_dev_proxy_names_every_manage_api_segment` is green with no edit. → `test_spa_serving.py`
- [ ] **AC17** — **A room cannot be deleted out from under a claim.** A delete whose occupancy check runs while a claim is uncommitted still refuses, proven by a forced interleave; the per-room `FOR UPDATE` is the mechanism and removing it is the mutation. → `db` `test_a_room_cannot_be_deleted_out_from_under_a_claim`
- [ ] **AC18** — **A staffer re-claiming the room she already holds gets a 200 with her own card**, whichever of the two simultaneously-violated indexes Postgres happens to report; and a 409 whose occupant released first names **nobody** rather than an empty string. → `db` `test_re_claiming_your_own_room_is_a_200_whichever_index_reports`, `test_a_claim_whose_occupant_released_first_does_not_name_nobody`
- [ ] **AC19** — **An add racing a remove of the same dress does not silently lose the add**; the later commit wins and the staffer is never told a gown went in that is out. → `db` `test_an_add_racing_a_remove_does_not_silently_lose_the_add`
- [ ] **AC20** — **A booking that has not checked in today cannot be bound to a room**, which is what makes D9's "only customers physically in a fitting room right now" a fact; and `GET /manage/floor/clients` answers only `booking_id`, `client_label`, `starts_at`. → `db` `test_a_booking_that_has_not_checked_in_cannot_be_bound_to_a_room`, `test_floor_api.py`
- [ ] **AC21** — **A `seamstress` sees no handover control, no release control on a colleague's tile, and no registry trigger in either the empty or the populated state**; an `owner` sees all three. The 403-is-terminal rule is therefore unreachable by design. → `RoomsPanel.test.tsx`
- [ ] **AC22** — **An occupied staffer's card reads «תפוסה», her room and her client, and never «פנויה»**; her role renders as muted words and not as a second `Badge`. → `FloorPanel.test.tsx` (NEW blocks), `RoomsPanel.test.tsx`
- [ ] **AC23** — **A claim whose body names a colleague, from a non-elevated caller, 403s AND never reaches the room repository** — F57's Risk 5, discharged on the PR that creates the shape rather than deferred to F37. → `test_floor_service.py`
- [ ] **AC24** — **The dress dialog and the handover dialog each return focus deliberately**: to the tile's control on close, to the tile's alert on a 404, and to the tile's control or the heading when a poll tick removes the assignment underneath them — never to `<body>`. Each mutation-checked. → `RoomDressDialog.test.tsx`, `RoomHandoverDialog.test.tsx`
- [ ] **AC25** — **A poll tick landing while the registry dialog has a dirty input does not destroy the typed value.** → `RoomsRegistryDialog.test.tsx`

---

## Testing

### Fast suite (no marker, no Docker)

- **`tests/test_floor_api.py` (extended)** — `FLOOR_ROUTES` grows from three rows (`:51-55`) to **thirteen** — three shipped plus D10's ten, and **D10's table is the only source for that count**, because a figure sized from prose reds a table-driven test on the first run — giving the 401 walk, the wiring walk and the `no-store` parametrization for free. `FakeFloorService` grows the new methods. `SPEC_ERROR_CODES` becomes **seven** and stays set-equal (the two 409s plus `VALIDATION_ERROR`, which the registry's label validation makes observable on this router for the first time). `StaffCardStatus`'s wire literals asserted set-equal to `{"available","break","occupied"}` at **`:360`** — **the test that fails if the enum and the wire drift apart** — and its twin at `test_floor_service.py:370` moves with it. ⚠ **`test_a_toggle_answers_one_card_and_not_the_whole_floor`'s key set (`:344`) grows to six with `occupancy`, and stays a SET EQUALITY** — it is the assertion that catches a seventh field arriving unreviewed on a five-role payload, and it is not optional (D12). The extended payload asserted as a literal for one occupied and one free room, **including `server_now`**. The two 409 bodies asserted **including their `details`**, **plus both `details`-less variants**, and a companion assertion that no other body in `main.py` grew one.
- **`tests/test_floor_service.py` (extended)** — the authorization matrix as pure branches against fakes, **which is where the two axes are actually proven**:
  - **claim** — elevated on anyone → allowed; each floor role on **herself** → allowed; each floor role on **another** → `NotAuthorizedError` **and the room repository is never called** (the assertion that proves the check runs before the read, i.e. that the 403 is not an existence oracle, and F57's Risk 5 discharged — AC23);
  - **release** — the repository-never-called assertion **does not apply**, because the target is an assignment id and whose it is can only be learned by reading it (D7). Asserted instead as: a non-elevated caller acting on a colleague's assignment gets **404, byte-identical to a nonexistent id**;
  - **handover** — the role check is now the **route gate** (D8), so the service test is that a non-elevated caller is refused **before** any read, on `actor.role` alone, even on her own assignment (D8's asymmetry, the one case a reader will doubt);
  - **the two dress routes** — asserted as a **positive**: a seamstress **may** bind and unbind a dress on a colleague's live assignment (D4's recorded permissiveness, asserted rather than defaulted, so it cannot arrive by omission);
  - the `(wrote, row)` mapping onto 200 / 200-unchanged / 404; an audit row on a write and **none** on a no-op; `occupied` beating `break` in `card_status`; the idempotence branch resolved by the **request-keyed read** and not by the constraint name.
- **`tests/test_floor_validation.py` (new)** — label stripping, empty, over-length, `sort_order` bounds.
- **`tests/test_staff_role_gating.py` (extended)** — `FLOOR_OPEN` grows from three to **nine**, gaining the **six** new all-five paths (claim, release, dresses POST, dresses DELETE, `GET /dresses`, `GET /clients`) as **route templates** (not concrete urls — the walkers read `route.path`, and mixing the two spellings is a CI round trip, `test_staff_role_gating.py:47-50`); the **four** tightened paths — three registry verbs plus **handover** — are **deliberately absent**, which is the assertion that the tightening is real and what keeps the table's shipped comment (*"the exhaustive list of what they may reach"*, `:84`) true. `FLOOR_ROUTES` joins the two shipped HTTP walks so the tightened gates are proven to **raise** and not merely to carry an `allowed_roles` attribute. ⚠ **The intersection classifier must not be touched** — F57's Risk 1 predicts this exact red and forbids the `any(...)` relaxation that "fixes" it.
- **`tests/test_frontend_constant_parity.py` (extended)** — one new `MIRRORS` param.

### `db`-marked (real Postgres)

**Standard to meet: F34's and F57's.** Both stood up a throwaway Postgres 16 cluster outside the repo, ran every migration and executed the whole `db` set **before pushing** — which is why both were green on CI's first run despite their headline tests debuting there. F36's races are harder than either. **Capture every pinned literal by running it; do not transcribe.**

- **`tests/test_migrations.py` (extended)** — the three tables exist with their exact column lists; the three index definitions pinned byte-identical from `pg_indexes.indexdef` **after this feature's migration**; the unique-index **counts** (2 on assignments, 1 on bindings, 0 on rooms); the round trip in both directions, last in the file, inside `try/finally: command.upgrade(cfg, "head")`.
- **`tests/test_floor_rooms_db.py` (new)** — the writers and the races. ⚠ **The `test_floor_db.py` seed rule applies verbatim: every row this module COMMITS holds `owner` or `shift_manager`, never a floor role**, because `migrated_db` is session-scoped, pytest collects alphabetically, and a committed `reception` row reddens three tests in `test_migrations.py` that have nothing to do with rooms (`test_floor_db.py:12-32`). Nothing here asserts anything about the actor's role — the gate is the two fast modules' job.
- **`tests/test_fitting_rooms_isolation.py` (new)** — the house rule for a new tenant table, three times over: tenant B reads zero rooms, zero assignments and zero bindings of tenant A's; every write against a foreign id is a 404 indistinguishable from missing; the app role's `GRANT`s are exercised (a missing one surfaces here as `permission denied` and nowhere else).

#### The forced interleaves, and the mutation each one must survive

`asyncio.gather` is **deliberately not used** for any deterministic branch, for the reason `test_floor_db.py:251-263` states verbatim: gather does not **order** two transactions, so the loser most often runs after the winner commits, and the zero-row branch the test exists to prove goes green without the mechanism ever being exercised. The mechanism is that `tenant_session` is `async with session_factory() as session, session.begin()`, so **exiting the context manager IS the commit** (`db/tenant.py:25`), and two nested `tenant_session`s on one `NullPool` factory take two separate connections.

⚠ **The ORDER inside the nested shape is what makes it safe for an INSERT race, and it must be spelled out rather than copied by shape.** The shipped pattern (`test_floor_db.py:295-325`) is: the **loser** opens its session and **READS** (a plain SELECT, which takes no row locks) → the **winner's** inner `async with` opens, writes and **exits, which is the commit** → only then does the loser issue its write. So the loser's statement always runs against a **committed** key and fails immediately; nothing ever blocks and nothing can hang. *That is exactly what "landing in the gap" means* — the loser decided the room was free, then the world changed under it.
**What must NOT be attempted:** a shape in which the loser's INSERT is issued while the winner's transaction is still open. A duplicate-key INSERT does not return — it **blocks** on the winner's uncommitted index entry until that transaction ends — and with the winner's `async with` nested inside the loser's coroutine the winner can never reach its commit, so the test hangs to the CI timeout. A builder who hits that will reach for `asyncio.gather`, which this section forbids and which yields exactly the vacuous test it exists to prevent. **Read: no blocking is needed to prove the guarantee. The index refuses the second claim whether the first is committed or not; the committed-first ordering is the one that is also testable.**

| Test | Mutation that MUST turn it red | Why nothing else catches it |
|---|---|---|
| `test_a_second_claim_landing_in_the_gap_is_refused_and_names_the_occupant` | **drop `idx_fitting_room_assignments_room_active`** | every other test claims one room once; without the interleave the loser's INSERT lands after the winner's commit and… still violates. **So the sharper mutation is the one below.** |
| ″ | **change the index predicate to `WHERE deleted_at IS NULL`** (drop `released_at IS NULL`) | the double-claim still fails — but `test_a_released_room_is_immediately_reclaimable` goes red, which is the pair that pins the predicate rather than the index |
| ″ | **remove `session.begin_nested()`** | the `IntegrityError` aborts the outer transaction, the occupant read raises `PendingRollbackError`, and the 409 becomes a 500. **No fast test can see this** — a fake repository raises nothing |
| `test_a_worker_cannot_hold_two_rooms` | **drop `idx_fitting_room_assignments_staff_active`** | the ONLY test that fails. The room index is satisfied (two different rooms), so every other assertion in the feature passes with the second index gone — including the staff card's `occupied`, which would then have to *choose* between two rows |
| `test_a_handover_preserves_the_bindings_and_records_the_previous_holder` | **move the `from` capture AFTER the writer** | F57's shipped note records this precise mutation leaving **all** fast tests green, because monkeypatched repositories never stamp anything. Only a real session's identity map poisons the local |
| `test_a_release_landing_in_the_gap_renders_the_database_value` | **remove `populate_existing=True` from the re-read** | every test that opens a **fresh** session per operation has an empty identity map, so the flag is a no-op there. F57's shipped note: with only the non-interleaved tests present, removing it changed **nothing** |
| `test_a_concurrent_double_add_yields_one_binding` | **remove `index_where` from the `ON CONFLICT` inference** | the statement then fails to match the partial index and raises instead of doing nothing; and separately, `test_a_removed_dress_can_be_re_added` goes red if the index is made total |
| `test_an_add_racing_a_remove_does_not_silently_lose_the_add` | **revert `DO UPDATE SET updated_at` to `DO NOTHING`** | the ONLY test that fails. Every add-vs-add and every sequential remove-then-re-add stays green with `DO NOTHING`, which is precisely why the lost update it reintroduces is invisible without this pair (D4) |
| `test_a_room_cannot_be_deleted_out_from_under_a_claim` | **remove the `FOR UPDATE` from the delete's room read** (and from the claim's) | no other test in the feature takes two statements against one room from two transactions. Without the lock the delete's occupancy check reads a snapshot the claim is not yet in, both commit, and the result is a soft-deleted room holding a live assignment — a state with **no UI path to release it** and no failing assertion anywhere (D1) |
| `test_re_claiming_your_own_room_is_a_200_whichever_index_reports` | **create the two partial unique indexes in the REVERSE order** in a scratch schema and re-run | Postgres reports whichever index has the lower OID, i.e. creation order. A branch derived from the constraint name passes in one order and refuses the staffer her own room in the other, and nothing else in the suite would ever run the second order (D3, D6) |
| `test_a_claim_whose_occupant_released_first_does_not_name_nobody` | **restore `details` to a required key** | with `details` required, this path either raises building the body or ships `{"staff_display_name": null}` and the panel renders an empty interpolation. Every other 409 test has an occupant to read, so nothing else exercises the empty branch (D3, D14) |
| `test_a_booking_that_has_not_checked_in_cannot_be_bound_to_a_room` | **drop `checked_in_at IS NOT NULL` from the claim's booking predicate** | every other booking in the suite is checked in, so the predicate is invisible without a fixture that is not — and its absence is what would let next month's bride's name onto the five-role payload (D9) |
| `test_a_deleted_customer_renders_an_anonymous_visit` | **drop `customers.deleted_at IS NULL` from the payload join** | `test_a_deleted_booking_renders_an_anonymous_visit` stays **green**, because it sweeps the booking rather than the person. Only this one catches the Amendment 13 erasure shape (D11) |

**Every one of these mutations must be RUN, not reasoned about.** F34 and F57 each found a real vacuous test this way — F57's was a focus test that jsdom could never have failed — and both prior features in this program record it as the step that changed the work.

### Frontend (vitest)

- **`RoomsPanel.test.tsx` (new)** — tiles render label, occupancy **word**, staffer name, **her role** (muted words, bare `<bdi>`, not a second `Badge` — E7 criterion 2 names it and `staff_role` is on the wire for it), client label and elapsed minutes; an anonymous assignment renders `rooms.anonymous`; a **holder-gone** tile renders `rooms.holderGone`; **for `role="seamstress"` the handover control, the release control on a colleague's tile, the empty-state CTA and the populated-state «ניהול חדרים» trigger are ALL ABSENT, and all four are present for `owner`** (AC21 — the assertion that keeps the 403-is-terminal rule unreachable); an inactive tile is greyed, carries the **word** and offers **no** claim control; the empty state carries the CTA for an elevated role and **no CTA** for a seamstress; a claim patches the tile **from the response** and is disabled while in flight, and a double-tap fires **one** request; a 409 `ROOM_OCCUPIED` renders the occupant's name from `details`; a 409 `STAFF_OCCUPIED` renders the room label; a 404 renders `rooms.error.notFound` and is **not** terminal; a 403 **is** terminal; **after a FAILED action the loop keeps polling** (the `.finally()` re-arm — F34's D4.4, the test that would still pass if it were dropped, and so would every other test here, which is exactly why it is named); **the announced region does not change on a poll tick** and does change on an action — driven over **several consecutive ticks with the cue already populated** (D18); **the three focus moves**, each with its mutation; an **axe pass, explicitly not sufficient**.
- **`RoomsRegistryDialog.test.tsx` (new)** — add / rename / **reorder via the labelled number input, reachable and operable by keyboard** / toggle / delete; the label and `sort_order` validation; the 409 on deleting an occupied room; **focus returns to the trigger, and to the heading when the trigger is gone**; **a poll tick arriving with a dirty input leaves the input's value alone** (AC25 — the seed-once contract, D15).
- **`RoomDressDialog.test.tsx` (new)** — filter, dress `Select`, size `Select`, add; truncation line; empty catalog; **the two focus contracts (D18 moves 4 and 5), each mutation-checked**: close → the tile's «הוספת שמלה» control, falling back to the heading; a 404 add → the dialog closes and focus lands **in the tile's alert**, not on the returned-to trigger; a poll tick removing the assignment → dialog closes, focus to the control or the heading, **never `<body>`**.
- **`RoomHandoverDialog.test.tsx` (new)** — the colleague list excludes the current holder and excludes `status === "occupied"` cards; the empty case renders `rooms.handoverNobody`; confirm; the residual 409 naming her room; the 404 when the assignment was released underneath; **focus return**, same two contracts as the dress dialog.
- **`FloorPanel.test.tsx`** — **existing blocks unedited (D15's acceptance rule)**; new blocks for the composition, for `mutate`'s shared re-arm, and — the one a reviewer should look for — **an occupied staff card rendering «תפוסה», its room and its client, and NOT «פנויה»** (AC22, D12).
- **`i18n.test.ts`** — the whole `rooms.*` deck resolves in `he` and in `ar`; and, **for every key starting `rooms.`, `ar[key] === he[key]`**. ⚠ Not merely "non-empty": the stated rule is *the approved Hebrew standing in untranslated*, and a non-empty assertion passes on an English string, a `TODO`, or a **different** Hebrew wording — which is a live hazard when ~40 keys are transcribed into two files by hand and Risk 12 records that no he/ar parity guard exists to catch it downstream. One line, exactly the stated rule, scoped to this namespace so Risk 12 stays as it is.

### E2E

**None, and the reason is F34's and F57's verbatim:** the console's entire e2e surface is two login-screen tests because `vite preview` runs with no backend (`e2e/a11y.spec.ts:10-13`). **F58 owns the `/manage/**` Playwright interception harness** and the floor-program review budgets it there as real work (F34's Risk 8, F57's Risk 9). Recorded rather than silently skipped — and note that F36 makes that gap wider, because the rooms panel is the first floor surface whose *interesting* states (409 naming an occupant, a room released underneath you) are only reachable with a stubbed backend.

### Rejected findings

One of the 41 spec-review findings is **not** applied, and a rejection has to be written down rather than left silent.

- **REJECTED (MAJOR): *"The named interleave mechanism deadlocks for an INSERT race — it works for F57's UPDATE only because that UPDATE never blocks."*** The finding asserts that in the nested shape *"the winner's `async with` is inside the loser's coroutine, so the winner can never reach its commit and the test hangs until the CI timeout"*, and prescribes an `asyncio.create_task` + `pg_locks` polling harness instead.
  **That is not what the shipped shape does.** In `test_floor_db.py:295-325` the loser's only statement before the winner's block is a plain `SELECT` — which takes no row locks — and the winner's inner `async with` **opens, writes and exits (commits) before the loser issues its write at all**. The loser's duplicate-key INSERT therefore runs against a **committed** index entry and fails immediately. Nothing blocks, nothing hangs, and the "landing in the gap" scenario the tests exist to prove is precisely *loser reads free → winner commits → loser writes*.
  The prescribed harness would additionally introduce a `pg_stat_activity` / `pg_locks` poll, a bounded sleep and a "the task is blocked, not merely unscheduled" assertion — three new failure modes and a flaky-on-CI shape — to prove a property the index guarantees either way.
  **Applied in the narrower form the finding is right about:** the *order* inside the nested shape is load-bearing and was previously implied rather than stated, so the Testing section now spells out the committed-first sequence **and** names the both-uncommitted shape as the thing not to attempt — because a builder who invents it *would* hang, and would then reach for the `asyncio.gather` this section forbids.

---

## Out of scope

- **Booking a room in advance.** Rooms are claimed live, never scheduled. No calendar, no reservation, no "hold room 2 for the 14:00".
- **Capacity per room.** A space that genuinely holds two brides is **two rows in the registry**. A `capacity` column would destroy the structural guarantee this feature exists to give — D3's index would have to become a count, which is a read-then-write, which is F13's lock, which is the thing the ruling forbids. This is the single most expensive-looking cheap alternative on the page.
- **Auto-assignment, room optimisation, "next free room".** A human picks the room.
- **Occupancy timers, SLA alerts, anything that fires on elapsed time.** The number is displayed; nothing watches it. No worker tick, no sweep, no maximum fitting length (F57's D7 for breaks, same reasoning, same absence).
- **Per-dress verdicts, ratings, photos, fitting notes.** E9 owns alteration intake.
- **The walk-in queue, the dispatch action, take-next, push-assign, skip, finish.** F33's and F58's. F36 ships the row they write into and the `queue_ticket_id` column they add (D2).
- **SOS, the full-screen alert, the 30-second escalation.** F37's, on this feature's assignment row.
- **Wait-time or room-utilisation analytics.** Pre-decided #28 keeps reporting out of E6 and it holds here.
- **A history read of past assignments.** The rows accumulate and `idx_fitting_room_assignments_tenant_created` exists for the day something reads them; nothing does in v1.
- **A `fitting_rooms` label uniqueness rule** (D1), a room `notes` field, a room photo, per-room permissions.
- **Retention of assignment rows.** F20's job owns every retention clock; F36 stores no personal field, so what remains after a source row is swept is already de-identified (D9). Risk 5 hands F20 the entry.

---

## Codebase conflicts recorded

1. **The E7 brief says the assignment carries "a nullable link to F34's dispatch record". F34 shipped no dispatch record.** F34 (PR #32) shipped `bookings.checked_in_at`, two endpoints on `booking/owner_router.py` and `BoardSection.tsx` — nothing that dispatches anyone anywhere. The walk-in's dispatch record is **F33's `queue_tickets`** (unmerged, in flight) and the dispatch **action** is **F58's**. Codebase-consistent reading, taken: F36 ships `booking_id` only; **F58 adds `queue_ticket_id` with its writer** (D2, Risk 3).
2. **Three shipped code comments state the floor payload "carries ZERO customer data" and one of them is the stated justification for the widest role gate in the product. F36 puts a client name on it.** Answered rather than waved past — but the answer has two halves and only one of them is prose. **D11's *conclusion* survives unchanged**: D9's table distinguishes *the customer book* from *the ≤3 people physically in fitting rooms right now*, and `floor-staff-roles.md:495`'s actual ground (the board's `customer_name` must not go behind a five-role gate) is untouched. **D11's three code-comment *premises* are REWRITTEN IN THIS PR** — `floor/router.py:11-14`, `floor/service.py:69-75`, `floor/schemas.py:13-16` — because each states the absolute form as a fact about the code, and `schemas.py`'s *"a card is … deliberately nothing else"* is falsified directly by `occupancy.client_label` landing inside `StaffCard`. Risk 5 hands F20 the processing-record entry.
3. **The E7 brief says the card is "Live via F32's ~5-second refresh — versioned board state with full refetch on version gap".** **F32 is subsumed and must never be built** (`shift-board-checkin.md:8`, LOOP-STATE, SMC ruling 3); there is no version field anywhere in the product and computing one costs the same as answering in full. Codebase-consistent reading: the poll **is** the full refetch (D11).
4. **The E7 brief's column list names `assigned_at`. F36 does not add it.** `created_at TIMESTAMPTZ NOT NULL DEFAULT now()` is on every table from `StandardColumns` and is set at exactly the claim instant; a second column is F57's D2 `break_ended_at` argument verbatim. The **wire field is still `assigned_at`** (D2).
5. **The E7 brief says "Owner manages the list in `apps/manage`". F36 admits shift_manager to the registry too.** Reasoned in D10: a shift manager already edits settings, hours, appointment types, the catalog and every booking, and "room 2's mirror is broken" is an act that has to be possible without telephoning the owner. Flagged because a reader will find the brief's word.
6. **`card_status(row: StaffUser)` is a total function of one nullable column, and F36 breaks that signature.** Its own docstring anticipates the change (`floor/service.py:44-52`). Counted rather than assumed: **`card_status` has ONE app call site** (`floor/schemas.py:46`, plus two in `test_floor_service.py:366-367`) and **`StaffCard.from_row` has THREE** (`floor/schemas.py:56`, `floor/router.py:97`, `floor/router.py:106`). The widening reaches all four — the two `router.py` sites are the break writers that will be tempted to pass `occupied=False` and ship a card that contradicts the panel it lands in, and `schemas.py:56` is `FloorResponse.from_rows`, the one that renders the **whole payload** and whose signature D11 replaces with a pre-joined `FloorRead`. *(An earlier draft said "both break routes call `card_status`"; they call `from_row`. The design consequence was right; the call graph was not.)* (D12).
7. **`frontend/apps/manage/vite.config.ts`'s comment says "The eleven names are exactly the second path segments". The alternation lists twelve** (`appointment-types|auth|availability|bookings|dashboard|dresses|floor|gateway|settings|slots|staff|terms`) — F57 added `floor` and did not update the count word. F36 changes nothing else in that file; the one-word fix is a free drive-by and is recorded here so it is not read as drift by whoever next reconciles that test.
8. **`backend/app/floor/router.py`'s docstring says `test_dashboard_api.py:49-51` "says SIX; it is a historical note in another feature's module".** F36 adds no router, so the count stays seven and both notes stay as they are. Recorded so a builder does not "helpfully" renumber a third file.
9. **`.claude/rules/` describes a Kotlin/Micronaut/Exposed codebase and does not apply.** `floor/router.py:44-46` already says so about the RPC/`@QueryValue` guidance specifically. F36 uses real HTTP verbs and path parameters, the shipped `/manage` convention.

---

## Risks & open items

1. **F37 attaches its alert to this feature's assignment row, and there are three properties it will assume.** Named here so F37's spec does not have to rediscover them, and so a later change to F36 knows what it would break:
   (a) **The assignment id is stable across a handover** — D8 mutates `staff_user_id` on the same row rather than release-and-reinsert, so an alert raised before a handover still points at the right room and the right client. Changing D8 to release-and-reinsert would silently orphan every open alert.
   (b) **"Which room is this staffer in right now" is ONE indexed lookup** against `idx_fitting_room_assignments_staff_active` — the `(tenant_id, staff_user_id)` partial unique index — and it returns at most one row **by construction**, so F37's raise path never has to choose. That is the second index's payoff outside this feature.
   (c) **An assignment RELEASED while an alert is open must still resolve its room label — and the label is NOT on the assignment row.** An earlier draft told F37 to *"read the label off the assignment row regardless of `released_at`"*; `fitting_room_assignments` carries `fitting_room_id` and **no label**, and D1's delete refusal protects only rooms with a **live** assignment, so the moment the assignment is released the owner may soft-delete the room — and D11's read starts from `fitting_rooms WHERE deleted_at IS NULL`. **The rule F37 gets, decided here:** join `fitting_rooms` on `fitting_room_id` with **no `deleted_at` filter**, and render the label of a since-deleted room. That is deliberate and safe — **a room label is not personal data**, so D9's no-snapshot rule does not reach it, and D13 already makes the mirror-image argument for `FITTING_ROOM_DELETED` carrying the label (*"its label may be re-typed onto a new room tomorrow, so an id alone records that something was removed and cannot say what"*). *Declined snapshotting `room_label` onto the assignment (`0008_bookings.py:52-57` a third time): it is a column and a writer on every claim to serve one downstream reader that a filter-less join already serves.* The **client** label on an alert stays resolved at read time (D9's rule does apply to that). *Owner: team. Trigger: F37's spec, which is the very next E7 feature.*
2. **F36 is the feature F57's Risk 5 named, and the review happens on THIS PR.** F57's Risk 5 (`floor-staff-roles.md:716`) says the self/elevated split is an id comparison whose safety depends on nothing downstream reading a target id as an actor id, and sets *"Trigger: F37's spec, which is the first one to take a target staff id in a body."* **That prediction is wrong and F36 is what makes it wrong**: D6's claim body is `{staff_user_id, booking_id}` and F57's break routes take the target in the **path**, which `start_break`'s own docstring calls out (`floor/router.py:92-94`). `FloorService._authorize`'s docstring names this exact shape as *the* hazard (`floor/service.py:138-145`). Deferring the review to F37 would mean the review F57 scheduled never happens on the PR that **creates** the condition. Discharged in D6 step 1 and asserted as AC23. F36 reuses `_authorize` **by call rather than by copy**, keeping it to one implementation — but F36 now calls it from four places instead of two, and F58's push-assign and F37's targeting will be tempted to write a fifth. *Owner: team. **Trigger: this PR's code review**, not F37's spec.*
3. **F58 needs a migration F36 deliberately does not ship, and LOOP-STATE's F58 note says "No new table".** True and not the same thing: F58 must `ALTER TABLE fitting_room_assignments ADD COLUMN queue_ticket_id UUID` in its own migration, with its writer, in the same PR (D2). Without it, F58's take-next has nowhere to record which queue ticket it seated and every walk-in renders as an anonymous visit. *Owner: team. Trigger: F58's spec, which must not be planned against the "no migration" reading.*
4. **The board screen's per-tick cost grows again, and it is derived rather than measured.** **~30** round trips per 5 s per device on the board screen — board ~17 (unchanged) + floor ~11 → ~13 (D11's table, F34's D3 method) — up from F57's ~28 and F34's ~17. *(The figure was stated as ~32 in an earlier draft, which did not reconcile with D11's own table; handing F29 a number that does not add up is the thing this risk exists to prevent.)* Nothing throttles it server-side — F34's D3 declines a read limiter and that reasoning holds (there is no attacker, only loyal clients) — so the client backoff and the idle stop are the only ceilings, and `tenants.by_slug` is still uncached **per request** and now paid twice per beat. **F29 must be handed this number, not left to discover it.** *Owner: team. Trigger: F29's k6 pass.*
5. **A client's name is now on a payload five roles can open, and no privacy notice covers a fitting-room assignment.** It is a smaller delta than F34's arrival record — one name, only while she is physically in the room, never stored — but it is a **new processing purpose** and it widens what `/manage/floor` discloses. **F20 (`spec_gate: user`, owner of the collection notice and the processing-activities record) must carry a fitting-room entry with TWO disclosures, not one: (a) purpose = floor operations; personal data = the client's name for the duration of an active assignment; retention = none of its own, the label is resolved from the source row and vanishes with it. (b) `GET /manage/floor/clients` — the names and appointment times of customers checked in today, disclosed to all five roles, fetched on demand and never stored.** (b) is the wider of the two and did not exist in an earlier draft, which specified `booking_id` on the claim body with nothing in the console able to produce one. No build work here beyond the route D16 ships. F57's Risk 10 and F34's Risk 9, same hand-off, third subject. *Owner: team, discharged by F20.*
6. **`is_active` and `deleted_at` are two flavours of "not in use" and a boutique will confuse them.** The registry offers both and the panel renders them differently, but the words «מחוץ לשירות» and «מחיקה» are one dialog apart, and a deletion is the one that orphans nothing only because D1 refuses it while occupied. Mitigation is a confirm step on delete and none on deactivate. *Owner: user. Trigger: the first pilot morning; the cheap remedy if it bites is naming the room in the confirm sentence.*
7. **The claim is one INSERT with no lock, and the whole guarantee rests on two index definitions surviving future edits.** The pinned `indexdef` literals and the unique-index **counts** (D5) are what make a future "simplification" of a predicate collide with a review instead of colliding with nothing — and the counts are the half that catches an **addition** rather than an edit. A third unique index added later on `(tenant_id, booking_id)`, say, would make a bride's second fitting of the day impossible with no test failing anywhere else. *Owner: team. Trigger: F58, which INSERTs into this table inside its own transaction and will be reading these indexes.*
8. **The `details` key is an extension of an error envelope every other body in the product treats as a two-field constant.** It is confined to two codes and asserted as such, but the shape is now precedented and the next feature that wants to return data with an error will find it. That is fine if it stays deliberate and bad if it becomes the default — an error is not a response. *Owner: team. Trigger: the next new 409 in the codebase.*
9. **`FloorPanel` grows a child, a shared `mutate` and a second dialog family, on the component that F57's review found five defects in.** D15's zero-edit rule on its shipped test expectations is the mechanical mitigation, and it is the same instrument D10 used to make the `usePoll` extraction reviewable. *Owner: team. Trigger: the code-review pass; a reviewer seeing an edit to an existing `FloorPanel.test.tsx` expectation should stop and read D15.*
10. **No E2E covers any of this, and the states that matter most are the ones only a stubbed backend can produce.** A 409 naming an occupant, a room released underneath a travelling finger, two polls and a mutation racing on boutique wifi — all unit-tested with fake timers against a mocked `api`, none exercised against a real backend. F34's Risk 8 and F57's Risk 9, widened. *Owner: team. Trigger: F58, which builds the `/manage/**` interception harness.*
11. **The audit rows are still write-only.** Four more actions nothing renders, and `FITTING_ROOM_DELETED`'s label is the only surviving copy of a removed room's name with no way to read it without `psql` (F15's Risk 7, F34's Risk 7, F57's Risk 8). *Owner: user. Trigger: F53's activity log, which is the first read surface.*
12. **`ar.ts` still has no parity guard.** F36 adds ~40 keys to both files by hand. F15's Risk 5, inherited by F34, by F57, and again here. *Owner: team. Trigger: F45, the feature that makes Arabic selectable.*

**Parked question (named, not blocking):** *should a room out of service still show a client who was in it when it was deactivated?* Today it does — deactivation does not release (D1), so a greyed tile can carry a live assignment. Nothing in the brief, the epic or the rulings answers whether that reads as reassuring ("she's still in there") or as broken ("why is an out-of-service room occupied"). It ships as-is because the alternative — evicting a bride to satisfy a flag — is clearly worse, and the pilot is what settles the rendering.

---

## Decisions Log

- **D1 — `fitting_rooms` is `label` / `sort_order` / `is_active` plus the standard columns, with one partial index `(tenant_id, sort_order, created_at) WHERE deleted_at IS NULL` — BOTH sort keys, because D11 orders by `(sort_order, created_at)` and `sort_order` defaults to 0, so a two-column index would supply none of the ordering for a boutique that never reorders.** `is_active` and `deleted_at` are different facts — out of service versus gone — and collapsing them would make "the mirror is broken" require deleting and re-typing the room, orphaning the assignments that point at its id. Deactivating an occupied room is **allowed** (evicting a half-dressed bride to satisfy a flag is the product being clever at her expense); **deleting** one is refused with 409 `ROOM_OCCUPIED` — and that refusal is enforced by a **per-room `SELECT … FOR UPDATE`** taken by both the delete and the claim, not by "construction": read-occupancy-then-write-`deleted_at` is a cross-row invariant, and under READ COMMITTED the unguarded form leaves a soft-deleted room holding a live assignment that **no screen can release**. It is the one lock in the feature, it is a row lock rather than an advisory one, and it is what actually lets D11's read start from `fitting_rooms`. **No unique index on `label`** — `models/dress.py:10-17`'s rule for a tenant-scoped name, a 2–6 row list the owner is looking at, and a 409 nobody asked for; upgrade path recorded. No index on `is_active` (nothing filters on it). `MAX_ROOM_LABEL_LENGTH = 40`, mirrored, one new `MIRRORS` param; `sort_order` uses the **house symmetric** bound `ge=-MAX_SORT_ORDER, le=MAX_SORT_ORDER` (`catalog/schemas.py:46`), because negatives are how a row moves to the front without renumbering the rest.
- **D2 — `fitting_room_assignments`: `released_at IS NULL AND deleted_at IS NULL` IS the occupancy model; `created_at` IS the claim time; `booking_id` ships and `queue_ticket_id` does not.** No `assigned_at` column — every table already carries `created_at NOT NULL DEFAULT now()` and the row is created at the claim instant, so a second column is F57's D2 `break_ended_at` argument verbatim; the wire keeps the name `assigned_at` and a handover deliberately does not restart it, because the number a shift manager reads is the **client's** time in the room. `released_at` is not `deleted_at`: a completed fitting is not a record that should not have existed. **`queue_ticket_id` is F58's**, because F33's table is unmerged, F36's deps do not include F33, and a column with no table, no writer and no reader is the `ScheduledMessageKind` rule's exact target. An assignment with **no** client link is legal and renders as an anonymous visit — the same path a retention-deleted source takes, exercised from day one rather than being dead code — but it must not be the ONLY path, which is why D16 ships `GET /manage/floor/clients` (D9). `created_at` is **DB-generated** (`server_default=text("now()")`), so it is not freezable and D7's frozen-clock equality applies to `released_at` only; `deleted_at` on this table has **no v1 writer** and is in the index predicates for the same reason it is on every table.
- **D3 — TWO partial unique indexes, both `WHERE released_at IS NULL AND deleted_at IS NULL`: `(tenant_id, fitting_room_id)` and `(tenant_id, staff_user_id)`. INDEX, NOT LOCK.** **F13 is not the precedent**: its claim picks the lowest free `seat_index`, which is a **count**, i.e. a read-then-write only a lock makes atomic (`booking/service.py:317-327`, and `:350-353` calls the index "the backstop"). A fitting room has no seat to number — the claim inserts three values the caller already holds, nothing is derived, and the statement either violates a unique index or does not. **F51 is not the precedent either, and it is the sharper case**: its lock exists because "at least one live owner" is an invariant *"no unique index can express"* (`auth/staff.py:9-34`) and because a `count(*)` guard is unsafe under READ COMMITTED. F36's invariant is **"at most one"**, which is exactly what an index says, evaluated by the index rather than against a snapshot. A lock would serialize every claim in the boutique and turn an immediate, informative refusal into a wait ending in the same answer. The **savepoint** (`session.begin_nested()`) is not a lock in disguise: it exists solely so the `IntegrityError` does not abort the transaction the occupant must be read in, which is what the ruling's "409 that names the occupant" requires. Constraint-name discrimination picks between the two 409s; an unrecognised name **re-raises**.
- **D4 — `fitting_assignment_dresses` is a child table with a THIRD partial unique index, and a concurrent double-add is a 200.** Not a JSONB array, because two staffers adding and removing dresses is a read-modify-write whose loser silently drops the winner's dress with no error and no index able to say so. `dress_name` / `dress_size` snapshots per `0008_bookings.py:52-57`; `dress_id` alongside so the live variant list resolves at read time. Removal is a **soft delete, and that soft delete is the audit record** (which is why D13 ships no dress action). The double-add uses `INSERT … ON CONFLICT DO NOTHING` inferred on the partial index — no `IntegrityError`, therefore no aborted transaction, therefore no savepoint on this path — and answers the outcome she wanted, F57's F-ok/F-noop argument.
- **D5 — One migration, three tables, six indexes, three `enable_tenant_rls` calls; revision id resolved from `alembic heads` at build time and NEVER from this document.** (At the time of writing `main`'s head is **0016** (F19) and **two** features are in flight — F33 and F53 — but read that from `alembic heads` and LOOP-STATE's `current:` block, not from here: it moved twice on the day this was written.) Build at head+1 so the branch is self-coherent and its `db` tests run; make the migration the **last commit** so the renumber is one amend; re-resolve immediately before the rebase that precedes the push; **do not open the PR while a lower-numbered migration is unmerged**. F33's D15 records that a `down_revision` naming a revision on another branch makes alembic unable to build the revision map at all and fails every `db` test — so a wrong number fails loudly rather than drifting. What the migration must prove it did not do: three index definitions pinned **byte-identical from CAPTURED literals**, the unique-index counts (2 / 1 / 0), and `test_every_tenant_id_table_has_forced_rls` green with no edit. The three ORM models are the second half and are not optional — no model↔migration parity test exists anywhere.
- **D6 — The claim is authorize → read room → read booking → savepointed INSERT → audit → full card, in that order.** `FloorService._authorize` reused **by call** so the actor is read from the session and never from the path or the body; it runs before any read, so the 403 is not an existence oracle. An inactive room is a **404**, not a fifth error code, because the panel renders no claim control on one and reaching the branch means the client was a tick stale. A re-claim by the **same** staffer answers 200 with the existing card and writes no audit row — an explicit branch, because the index cannot distinguish "I already have it" from "she does".
- **D7 — Release is a conditional `UPDATE … WHERE released_at IS NULL` plus one `populate_existing=True` re-read, and rowcount 0 is NOT an error.** She wanted the room free; the room is free — 200, the card rendered from the **database's** answer, no audit row (F34's D8). Rowcount 0 with no row is a 404. `released_at` comes from `FloorService`'s injectable clock, the shipped shape one file over, so a db test asserts an equality rather than a range. Authorization is the same two axes as the claim — declined "anyone may release any room", because freeing a colleague's room with a bride still in it is the one destructive act on this surface.
- **D8 — Handover is a guarded `UPDATE … SET staff_user_id`, not release-and-reinsert.** One statement preserves the dress bindings by not touching them; release-and-reinsert would have to copy every child row and would open a window in which the room is momentarily free. `created_at` does not move, so the elapsed number stays the **client's** time in the room. The `(tenant_id, staff_user_id)` index guards the receiving staffer — a colleague who already holds a room is a 409 `STAFF_OCCUPIED` naming it. The assignment id is **stable**, which is what keeps F37's alerts correct. The audit row carries `{"from","to"}` with **`from` captured into a local BEFORE the write** (`floor/service.py:108-116`'s ⚠ comment verbatim) — the mutation that breaks it leaves every fast test green and must be a `db` test. **Elevated only**: a handover takes a room from one worker and gives it to another who has not consented, so "any staffer may act on herself" does not reach it.
- **D9 — The assignment stores NO personal field; the client label is resolved at read time; and F57's D11 survives.** A snapshot would outlive both F20's retention sweep and pre-decided #26's ticket auto-delete, so the platform would delete a customer record and quietly keep a copy of who she was on a screen five roles can open. The anonymous-visit render is the **default** for any claim without a booking, not a rare path. **F57's D11 "zero customer data" claim becomes a narrower and truer rule**: the floor payload carries the minimum datum required by the person standing on the floor — at most one name per room, for the duration of the fitting, and nothing else about her — never the day's customer book, which is what D11 actually refused to merge. Declined first-name truncation (a whitespace split on Hebrew compound names is a new untested transform on a legal surface for a disclosure reduction of roughly zero; F59's rule is for an unauthenticated wall screen); declined no label at all.
- **D10 — TEN new routes hang off F57's floor router (thirteen in total); FOUR are TIGHTENED per-route to owner + shift_manager — the three registry verbs and HANDOVER.** `RoleGate` composes by intersection, so narrowing is the only per-route move available — and **F36 is the first customer of the intersection classifier F57's Risk 1 exists to protect**: `any(...)` would report a correctly tightened route as admitting the floor roles and red-fail it. `FLOOR_OPEN` grows three → **nine**, gaining the six all-five paths as templates and **deliberately omitting the four tightened ones**, which is the assertion that the tightening is real and what keeps its shipped comment (*"the exhaustive list of what they may reach"*) true. **Handover is tightened at the ROUTE and not in the service** because its predicate depends on nothing about the target — a pure role predicate is what `RoleGate` is — and because a 403 is terminal for the whole panel, so a route a rendered control can reach must be a route its caller may use. `FLOOR_ROUTES` goes three → **thirteen**; eight of the ten new verbs are mutating and CSRF-fenced, two are GETs. Owner + shift_manager rather than owner-only, because a shift manager already edits every booking and the catalog, and "take room 2 out of service" cannot require a phone call. **Every second path segment is `floor`, so `vite.config.ts` needs no edit** — `test_spa_serving.py`'s set equality has broken a developer's machine twice while production, CI and the suite stayed green, and mounting at `/manage/rooms` would have cost that edit for nothing.
- **D11 — Rooms and occupancy EXTEND `/manage/floor`. One poll, one payload, no version field.** The envelope F57 shipped for exactly this gains `rooms`; the staff card gains `occupancy`, denormalised on purpose so `RoomsPanel` and the staff list stay independent renderers rather than one needing the other's data (D15's coupling rule). Inactive rooms ship so the panel can grey them. `minutes_elapsed` is **not** on the wire — but nor is it `Date.now() - assigned_at`: F57 formats an **absolute** instant through `jerusalemTime` and never subtracts, so the envelope gains one `server_now` field and the client anchors on it, trusting only the *elapsed* device clock. Every join predicate is written out, and two of them are load-bearing: `customers.deleted_at IS NULL` (an Amendment 13 erasure is about the person, not her appointment) and **no** `deleted_at` filter on `staff_users` (a holder soft-deleted mid-fitting leaves a live assignment with no card, so `staff_display_name` is `string | null` and only an elevated caller can clear the tile). `FloorService.floor()` stops returning `list[StaffUser]` and returns a frozen `FloorRead`, so `FloorResponse.from_rows` stays a pure renderer. The read is **two statements added to the tick's existing session** — one outer-join chain starting from rooms, one `IN (…)` for the bindings, skipped entirely when nothing is occupied — for **+2 statements, +2 round trips, 0 new sessions, 0 new pool checkouts**, taking the board screen to **~30** round trips per 5 s (board ~17 + floor ~13). F32 stays subsumed; the poll **is** the full refetch.
- **D12 — `StaffCardStatus` gains `occupied` in the PR that gives it a writer, and `occupied` beats `break`.** The widening **four** files were written to receive — the enum, **two** set-equality assertions (`test_floor_api.py:360`, `test_floor_service.py:370`) and the mirrored TS union at `api.ts:390` — plus a fifth that nobody listed: `test_a_toggle_answers_one_card_and_not_the_whole_floor`'s key set (`test_floor_api.py:344`) grows to six with `occupancy` and stays a set equality. **The staff card's RENDER changes too**: the shipped `Badge` is a binary on `onBreak`, so `status: "occupied"` would fall through and print «פנויה» about a woman standing in room 2 — it becomes a three-way with `floor.statusOccupied` «תפוסה», plus an occupancy line, or D11's three denormalised fields have no reader at all. `occupied` wins over `break` because she is standing in room 2 with a client and a screen that says «בהפסקה» is lying about something a shift manager can see; `break_started_at` stays on the wire so a forgotten toggle is still legible. Declined a fourth combined status (orthogonal facts in one enum — F34's D1, F57's D2). `card_status` gains an `occupied` parameter, and **both break writers must pass the truth** rather than `False`, or they answer a card that contradicts the panel five seconds later.
- **D13 — Four `AuditAction` members, no migration.** `audit_log.action` is plain TEXT with no CHECK — the **seventh** block to rely on it (F19's deposit block merged the same day). Claimed / released / handed-over / room-deleted. A no-op writes no row (F34's D8). Declined created and updated (non-destructive, visible on the screen that performed them, already timed by `created_at`/`updated_at`, and every action added now is a line with no reader until F53). Declined dress added and removed (the binding row **is** the record — soft-deleted, so it survives with `deleted_at` **and `removed_by`** — at a volume that would swamp the four that matter). **`removed_by UUID NULL` is what makes that sentence true**: without an actor the row answers what and when and not who, and D4 deliberately admits all five roles to both dress routes with no ownership check. `FITTING_ROOM_DELETED` carries the **label**, `previous_break_started_at`'s reason: the id alone records that something was removed and cannot say what.
- **D14 — Two new error codes, `ROOM_OCCUPIED` and `STAFF_OCCUPIED`, both 409, both carrying a `details` object; everything else reuses a shipped 404 or 400.** `SPEC_ERROR_CODES` goes four → seven, still set-equal. The `details` key is a real extension of an envelope every other body treats as a two-field constant, and it is justified narrowly: the ruling requires the 409 to **name** the occupant, the English `message` is never rendered for a mapped code, a second GET races the release it describes, and waiting for the next tick is the five seconds this feature exists to delete. Built at raise time, the `DomainValidationError` technique. `ApiError` and `extractError` grow six lines, and `details` is typed **`Record<string, string> | undefined`** rather than `| null`, because the occupant can release between the violation and the occupant read — leaving nobody to name — and an empty interpolation on a legal surface is worse than a sentence that says so (two extra Hebrew keys, no extra code). Declined one code with a discriminating `details` (two causes, two sentences, two remedies — that is what a code is for). Inactive rooms, released assignments and missing bindings are all **404**, deliberately, so the feature adds two codes and not five.
- **D15 — `RoomsPanel` is a CHILD of the shipped `FloorPanel`, not a sibling: one poll, one pause control, one announced region, and `App.tsx` is untouched.** A sibling would need a second `usePoll` (forbidden by the ruling) or state in `App` (forbidden by F57's D11). `mutate(fn)` is extracted from the shipped `toggle()` because copying its five-part dance would be six chances to drop the `.finally()` re-arm — the mistake whose F34 form was "the loop survived unmount". **`lib/usePoll.ts` gets a zero-line diff and `FloorPanel.test.tsx`'s shipped expectations pass UNEDITED — that is the acceptance rule, the D10 precedent one level down.** Rooms render above the staff list; the pause control stays first inside the panel, before the content it governs. The pointer hold matters more, not less: a claimed tile grows by far more than the ~20px `holdRef` was built for.
- **D16 — TWO one-shot list routes, `GET /manage/floor/dresses` and `GET /manage/floor/clients`, both rendered with `@boutique/ui`'s `Select`, neither on the poll.** The floor router needs its own dress list because `catalog/router.py:61` admits two roles and `RoleGate` narrows only — widening the catalog is what F57's Risk 1 exists to prevent. What it discloses is **strictly less than the boutique's own storefront publishes to anonymous strangers** (`storefront/service.py:75-100` already answers names and size labels): no price, no description, no media, no stock. Client-side filtering, so no `?q=`, no debounce, no second request. The **clients** route is the one without which `booking_id` has no producer anywhere in the console — the three floor roles cannot reach `/manage/bookings` at all — so without it every v1 claim is anonymous, E7 criterion 2 is unmet and D9's privacy widening buys nothing; it is scoped to customers **checked in today** (the people in the building, not the day book), answers three fields, and is fetched on mount and after each claim. The controls are named **`Select` / `Input` / `Modal` from `@boutique/ui`**, not "a native `<select>`": `Select` already carries this exact decision in its own shipped comment, and a bare element loses the `label` association and the `focusRing` that axe cannot see is missing. Declined an ARIA combobox on a legally binding a11y surface; declined a new dependency — the platform ships the control.
- **D17 — A new `rooms.*` namespace in `he.ts` AND `ar.ts` with the Hebrew standing in untranslated; every state string F57 already ships is REUSED unchanged.** Hebrew only, no switcher, the 2026-07-31 languages ruling; `ar` values are never empty (i18next's `returnEmptyString` renders `""` rather than falling back). The rooms panel lives inside `FloorPanel`'s poll, so it inherits every freshness, pause, idle, stale and terminal state and must not spell any of them a second way — F57's F-10 argument. The **copy deck is canonical**, not this document's table. The `i18n.test.ts` assertion for this namespace is **`ar[key] === he[key]`**, not "non-empty" — non-empty passes on an English string, a `TODO` or a different Hebrew wording, and ~40 keys are transcribed by hand into two files. No new formatter: elapsed minutes are arithmetic on two ISO instants and must not attract a date library.
- **D18 — a11y is a legal requirement (IS 5568 / WCAG 2.0 AA) and axe is not the coverage.** axe **cannot see a focus move that never happened** — this repo has shipped that bug class three times (F56, F34, F57) and axe walked past all three, because `@boutique/ui`'s `Button` is `disabled={disabled || loading}` and every room action is that shape. Three named focus tests (failed action → the tile's alert; successful action → the tile's control; a deleted room holding focus → the heading), **each mutation-checked**, because F57's own success-path focus test was **vacuous** — jsdom does not blur a disabled element, so the whole restore effect could be deleted with the suite green. axe has **no SC 2.2.2 rule**, so `FloorPanel`'s shipped pause and idle assertions now govern a second region and may not be cut as redundant. The poll never writes into `role="status"`, and the cue is written only when its value actually changes (F34's F-7 — the test must drive several consecutive ticks with the cue already populated). Occupancy is a **word**, never colour alone; one `Badge` per tile; `<bdi dir="ltr">` on numbers, bare `<bdi>` on Hebrew; **no truncation of a client label or a room label, ever**. **Five** focus tests, not three: the dress and handover dialogs each need a return contract *and* a rule for the poll tick that unmounts them under the user's hands, and the 404 collision is resolved explicitly (the tile's alert wins over the native `<dialog>` return). **Reorder is a labelled `<input type="number">`, never drag-and-drop** — the same ladder rung and the same legal reasoning D16 uses to refuse the combobox, and a WCAG 2.1.1 keyboard failure axe cannot see. **Which control EXISTS is the rendered form of the two axes** (`FloorPanel.tsx:525-530`): handover, release-on-a-colleague and both registry triggers are absent for a non-elevated caller, because a 403 is terminal for the whole panel and would blank a seamstress's only screen.
