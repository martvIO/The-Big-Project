# Plan: Feature 58 — Waitlist panel + dispatch: take-next, push-assign, finish, skip, call, remove (Epic E6, floor-management program iteration 5)

**Status**: Gate 2 self-approved 2026-08-03 under Interview Q1 (F58 is none of Q1's enumerated exceptions — no payments, no refunds, no privacy-law text, no billing). **Design gate self-approved** by the 2026-07-31 ruling; the deck and the copy deck are on disk, mechanically verified, and **the design critic's verdict is REVISE** — its nine required changes are folded in below as **DC-1 … DC-9** and each has an owning task. *The gate goes away; the design work does not.*

**⚠ THIS IS THE CRITICAL PATH OF THE RUN.** `LOOP-STATE.md`'s `deployment_gates` names F58 as `cleared_by` for **both** F33 (merged, PR #36) and F59 (merged, PR #38). Two already-merged features are inert until this lands. **Task 14 clears both entries**, and that is not paperwork — it is the deliverable the run report is written against.

**Spec**: `.planning/specs/floor-dispatch.md` (1 109 lines, D1–D19, 32 review findings / 32 applied, 3 narrowed) · **Design deck**: `.planning/design/screens/floor-dispatch/design.md` (593 lines, §0–§13, thirteen findings F-1…F-13) · **Copy deck**: `.planning/design/screens/floor-dispatch/copy.md` (242 lines, §0–§11, **40 keys**) · **Branch**: `feature/floor-dispatch` · **Worktree**: `.worktrees/floor-dispatch` · **Created**: 2026-08-03

TDD throughout. Every task states its **failing test first**, then the code that makes it pass, then the exact files, then how to verify, then the commit message.

---

## ⚠ Three process facts, carried from the F36 plan and re-verified on this tree

**1. `db`-marked tests run locally, and the escape hatch is SHIPPED CODE.** `backend/tests/conftest.py:88/:100/:109` — `TEST_POSTGRES_SUPERUSER_URL` replaces the Testcontainers cluster with one you started yourself. **There is no patch to apply and no revert obligation.** Postgres **16.14** is live via Homebrew (superuser `mrwen`, no Docker). The runner, written once into the scratchpad and never committed:

```bash
# scratchpad/run-db-tests.sh
set -euo pipefail
dropdb   --if-exists -h 127.0.0.1 -U mrwen f58_test
createdb              -h 127.0.0.1 -U mrwen f58_test
export TEST_POSTGRES_SUPERUSER_URL='postgresql+asyncpg://mrwen@127.0.0.1:5432/f58_test'
cd "/Users/mrwen/Documents/Github/Ryan + rawad + mrwen/.worktrees/floor-dispatch/Backend"
uv run pytest -m db -q --ignore=tests/test_media_upload_s3.py
```

**Capture the baseline on the branch's base commit BEFORE Task 1** and record the number in the run report. **Do not hardcode a count from any earlier plan** — F36 and F59 both added `db` cases since the last one was written (F59's `shipped:` block records 550 at its merge, which is already the wrong number to assert against). The 9 `test_media_upload_s3.py` cases need MinIO and are excluded; F58 touches no S3.

**This is what made F34, F53, F57, F36 and F59 green on their first CI run.** Six of this feature's mutation-checks **cannot be performed at all without a real Postgres**: a monkeypatched repository never takes a row lock, never runs an EvalPlanQual re-check, never raises `IntegrityError` and never blocks on an uncommitted tuple — and those four are the whole of what D3, D3a, D4 and D6 install.

**2. Path hygiene, unchanged and still load-bearing.** The repo path contains a **space** and a **`+`** — quote every shell path. Git tracks `backend/` / `frontend/` **lowercase** while the on-disk directories are `Backend/` / `Frontend/`: `git add Backend/…` **silently skips modified tracked files**. Lowercase every pathspec and verify every commit with `git show --stat`.

**3. `make lint` runs `frontend/scripts/qa-greps.sh`, and it reaches `apps/manage/src` in exactly one place.** Its ten `check` calls read `apps/storefront/src` only (`qa-greps.sh:17`), but the trailing **date-reads review block** (`:60-70`) greps `apps/storefront/src apps/manage/src packages/ui/src` for `getDay()` / `getDate()` / `toLocaleDateString` / `toLocaleTimeString` and for a single-line `Intl.DateTimeFormat(...)` without `timeZone`. **F58 renders a wait time and is exactly the feature that reaches for a formatter** — it must not: `elapsedMinutes` is arithmetic on two ISO instants and involves no timezone at all. Capture the baseline before Task 9 and diff it after every frontend task.

---

## What moved since the spec was written — **fourteen corrections**, C1–C14

The spec was written and reviewed on 2026-08-03. **F59 (PR #38) merged the same day**, and its own review pass already corrected four stale facts in place (spec Conflict 10). Every citation below was re-opened and re-read on `main` at `e251ba7`. **The spec is binding and D1–D19 are not re-litigated**; these are the places where the documents disagree with the code, plus three shipped comments this feature falsifies that neither the spec nor the deck lists.

| The spec or a deck says | Actually, now | # |
|---|---|---|
| `main`'s head is `0019_fitting_rooms` (Risk 7) | **Still true** — `migrations/versions/` ends at `0019_fitting_rooms.py` and F59 merged with no migration. **But F41 is building right now WITH one**, so the number will move. Task 1's rule, not its number, is what ships | **C1** |
| `test_spa_serving.py:377` asserts the dev-proxy set equality (D11, «What already exists») | The test is **`:381`** (`test_the_manage_dev_proxy_names_every_manage_api_segment`) and the set equality is **`:409`**. `expected` is derived at `:399-404` | **C2** |
| `QueueTicketsRepository`'s "no read keyed on `phone`" docstring is `:15-18` (D2, Conflict 5) | The class opens at **`:47`** and the docstring is **`:48-55`**; the sentence D2 corrects is **`:51-54`** | **C3** |
| `queue_ticket.py:23-26` carries the no-uniqueness paragraph (Problem) | **`:24-26`**. The per-column comments D2 and D7 quote are `:45-49` (`called_at`), `:50-54` (`requeued_at`), `:55-56` (`skip_count`) | **C4** |
| `floor/service.py:184-201` is the payload's privacy sentence; `occupancy_by_staff_id` is `:216-219` (D10) | The ⚠ block is **`:186-200`** and the binding clause *"at most one name per occupied room"* is **`:190-193`**. `occupancy_by_staff_id` is **`:217-219`** | **C5** |
| — *(neither document lists it)* | **`floor()`'s docstring says «TWO extra statements on the tick's EXISTING session» (`:202-205`).** D2 makes it **four**. A shipped comment this PR falsifies, on the same method D10 already rewrites — **fix it in the same edit** | **C6** |
| — *(neither document lists it)* | **`floor/router.py:1-2` opens «…the two one-shot pickers — thirteen routes on /manage».** D11 makes it **eighteen**. Same file as D10's rewrite, one word | **C7** |
| `models/fitting_room_assignment.py:26-30` is the "No personal field of any kind" sentence D1 corrects (Conflict 7) | Correct (**`:26-29`** plus the closing quote). **But there is a SECOND stale comment on that model**: `:39-42` reads *"any walk-in until F58 ships the queue link, produces a row with no client"* — true until this PR and false after it. `copy.md` §9 already anticipates the successor sentence. **Both are rewritten in Task 1** | **C8** |
| `RoomsPanel.describe()` is `:352-385` (D17, deck §3.4) | **`:352-388`**; the outage fall-through is **`:387`**. The deck's own §3.4 says `:352-388` and is right; the spec's D17 is the stale one | **C9** |
| `Button.tsx:62` applies `focusRing` (deck §11.5) | **`:63`**. `sizes[size]` is `:62`. **F36's plan corrected this exact figure once already (its DC-14) and the new deck reintroduced it** — the `sm`/`md` figures (`:36`/`:37`) and `disabled={disabled \|\| loading}` (`:57`) are correct | **C10** |
| `floor/validation.py:44-83` is `_OccupiedError` and its two subclasses (D12) | The class opens at **`:43`**; the two subclasses are `:65` and `:71`. The MRO trap the docstring writes out is `:44-52` and D12's citation of *that* is right | **C11** |
| `api.ts:447-448` mirrors the envelope sentence (D2) | **`:446-447`**. `ApiError` is `:9-30` with `details` at `:22` and the constructor at `:24-29` — D12's "no change needed" holds | **C12** |
| **DC-3's cheaper option — "take the two-line `he.ts`/`ar.ts` fix" for `rooms.error.STAFF_OCCUPIED`** | **NOT AVAILABLE.** Its literal is asserted in **three** shipped files: `RoomsPanel.test.tsx:604` and `:616`, `RoomHandoverDialog.test.tsx:238`, and `i18n.test.ts:501-513`. Editing the value reds four shipped assertions and breaks this feature's stated acceptance gate. **Task 9 takes the two-new-keys route instead** and records why | **C13** |
| `HE_F36`'s floor goes `>= 70` → `>= 71` (spec Frontend changes) / `>= 73` (deck F-6) | `he.ts` carries **71** `rooms.*` keys today against a floor of `>= 70` (`i18n.test.ts:424`). F58 adds **five** — the deck's three (§4) plus DC-3's two — so the floor is **`>= 76`**. Both documents are wrong and in different directions | **C14** |

### Citations re-captured — ✅ verified on this tree, do not re-check

- ✅ `backend/app/db/repositories/queue_tickets.py` (167 lines) — **four** methods: `insert` **`:57`** (its *"F58 owns every one of them"* docstring `:68-71`), `by_id` **`:85`** (a `select(QueueTicket)` **entity** read — D2's whole argument for `status_of`), `position` **`:95`**, `board` **`:123`**. Module-level `_live_waiting` **`:12-47`** (its *"F58 widening one status filter, say"* hazard `:22`, the four predicates `:42-47`, the day-binding paragraph `:26-34`) and `_sort_key` **`:39-45`**. Class docstring **`:48-55`** (C3).
- ✅ `backend/app/db/repositories/fitting_room_assignments.py` (310 lines) — **`violated_index()` `:21-43`**, the working form at **`:43`**: `getattr(getattr(error.orig, "__cause__", None), "constraint_name", None)`, with `:24` stating *"It is NOT `error.orig.constraint_name`"*. `claim` **`:51`**, `active_for` **`:100`**, `occupant_of_room` **`:151`**, `room_of_staff` **`:167`**, `has_active_for_room` **`:181`**, `release` **`:200`**, `handover` **`:235`**.
- ✅ `backend/app/floor/service.py` (810 lines) — module docstring's *"ordering is the security property … a 403 raised after a read is an existence oracle"* **`:19-24`**; `ELEVATED_ROLES` `:69`; `card_status` `:80`; `FloorService.__init__` **`:161-177`** (ten repositories, **no** `QueueTicketsRepository`, `_clock` at `:177`); `floor()` **`:179`** with the privacy block `:186-200` (C5) and the two-statements sentence `:202-205` (C6); the claim's savepoint **`:337-356`** (`try` at `:337`, `begin_nested()` at `:345`, `except IntegrityError` at `:353`); **`_resolve_claim_conflict` `:372-411`** — the idempotence **`return` at `:398-400`**, `violated_index` at `:401`, the two 409 branches `:402-410`, **`raise error` at `:411`**; `release` **`:413`** with its no-op-writes-no-audit comment **`:452-456`**; `handover` `:459`; `delete_room` `:624`; `_today_window` **`:719-733`** (`today_jerusalem(self._clock)` at `:727`); `_room_read` `:735`; `_occupant_details` `:747`; `_held_room_details` `:761`; `_is_claimable` `:772`; **`_authorize` `:793-806`** (`@staticmethod` at `:793`); `from app.storefront.validation import BOUTIQUE_TIMEZONE, today_jerusalem` at **`:64`**.
- ✅ `backend/app/floor/router.py` (340 lines) — the *"thirteen routes"* opener **`:1-2`** (C7), *"A SEVENTH router"* `:4`, the privacy block **`:17-26`**, the two-loops table `:29-42`, `_no_store` `:117`, `router = APIRouter(prefix="/manage", dependencies=[…])` **`:126-132`**, **`ELEVATED = Depends(require_role(OWNER, SHIFT_MANAGER))` `:173`** with its intersection comment `:168-172`, `_room()` `:176`, and the thirteen shipped routes at `:138`, `:143`, `:156`, `:183`, `:197`, `:217`, `:230`, `:253`, `:263`, `:290`, `:309`, `:330`, `:336`.
- ✅ `backend/app/floor/schemas.py` (343 lines) — the envelope sentence **`:7-11`** (*"F36 adds rooms and occupancy to it while F58 adds the waitlist"*), the falsified card sentence **`:13-19`**, `StaffCard` `:43`, `FloorResponse` `:72` / `from_rows` `:84`, `Room` `:145`, `Occupancy` `:198`, `FloorDressList` `:242`, `FloorClientList` `:271`, `CreateRoomRequest` `:296`.
- ✅ `backend/app/db/repositories/fitting_rooms.py` — `RoomRow.client_label` `:40`, `by_id_for_update` `:89`, `list_with_occupancy` `:197`, `room_with_occupancy` `:226`, `occupancy_for_staff` `:235`, **`_occupancy_rows` `:254`** with **FOUR** `outerjoin`s at **`:281`, `:290`, `:297`, `:306`** and `client_label=row[10]` at **`:334`** — *the projection is eleven columns and D10's fifth join shifts the index*.
- ✅ `backend/app/models/queue_ticket.py` — the no-uniqueness paragraph **`:24-26`** (C4), `queue_day` `:32-35`, `phone` `:36-40`, `status` `:41`, `called_at` **`:42-49`**, `requeued_at` **`:50-54`**, `skip_count` **`:55-56`**.
- ✅ `backend/app/models/fitting_room_assignment.py` — *"No personal field of any kind"* **`:26-29`**, the *"any walk-in until F58 ships the queue link"* comment **`:39-42`** (C8), `booking_id` `:43`, `released_at` `:48`.
- ✅ `backend/app/models/constants.py` — `QueueTicketStatus` and its *"every transition out of it is F58's"* comment `:96-108`; `AuditAction`'s F36 block; `audit_log.action` is plain TEXT with no CHECK (`0003`).
- ✅ `backend/app/queue/validation.py:56` — **`class QueueTicketNotFoundError(DomainNotFoundError)`**, `:59` recording that the base class's shipped 404 handler answers it, so **no new handler**.
- ✅ `backend/app/floor/validation.py` — `_OccupiedError` **`:43`** (C11) with the MRO trap `:44-52` and the optional-`details` ⚠ `:49-58`; `RoomOccupiedError` `:65`; `StaffOccupiedError` `:71`.
- ✅ `backend/app/main.py` — `ROOM_OCCUPIED_BODY` **`:339-341`**, `STAFF_OCCUPIED_BODY` **`:342-347`**, **`_occupied_body` `:350-365`** (copies rather than mutates `:362`; omits a falsy `details` `:363-364`).
- ✅ `backend/app/db/tenant.py:25` — `async with session_factory() as session, session.begin():`. **An exception propagating out of it ROLLS BACK.** D3a's whole proof, and the reason the first draft's mutation was vacuous.
- ✅ `backend/tests/test_migrations.py` — **`_parent_of` `:31-55`** (resolves the target by identity, so a renumber cannot rot it), **`test_exactly_one_migration_head` `:57`** with `get_heads()` at `:76` (F19's fast, no-DB guard), `test_the_queue_tickets_migration_pins_its_checks_and_its_one_index` **`:1007`**, `test_queue_tickets_carries_no_unique_index_but_the_primary_key` **`:1023`**, `_fitting_columns` **`:1521`**, `test_the_three_partial_unique_index_definitions_are_pinned` **`:1581`**, `test_fitting_room_assignments_carries_exactly_two_non_primary_unique_indexes` **`:1617`**, `test_the_fitting_room_tables_carry_no_check_constraints` **`:1648`**.
- ✅ `backend/tests/test_floor_api.py` — `FLOOR_OPEN_ROUTES` **`:94-104`** (**nine** rows), `FLOOR_TIGHTENED_ROUTES` **`:106-111`** (**four** rows), `FLOOR_ROUTES` **`:113-116`**, `SPEC_ERROR_CODES` **`:127-135`** (**seven** members) with its *"⚠ SEVEN after F36"* comment `:118-126`, the walks at `:486`, `:514-516`, `:527`, `:593`, `:605`, `:633`, `:803`, `:1120`, and `assert observed == SPEC_ERROR_CODES` **`:1175`**.
- ✅ `backend/tests/test_staff_role_gating.py` — the *"FLOOR_OPEN below is the exhaustive list of what they may reach"* comment **`:84`**, `FLOOR_ROLES` `:85`, the **route-template** rule `:93-96`, the nine constants `:99-116`, the ⚠ *"the FOUR tightened routes are DELIBERATELY ABSENT"* block **`:118-122`**, **`FLOOR_OPEN` `:123-133`** (nine entries), `test_the_floor_roles_reach_exactly_the_floor_routes` **`:271`** with *"MUST NEVER BE RELAXED TO A SUBSET CHECK"* **`:279`**, the intersection classifier **`:310-316`**, `assert admits_floor == FLOOR_OPEN` **`:323-327`**, **`assert not partial` `:329`**, the `missing` guard `:332-333`.
- ✅ `backend/tests/test_floor_rooms_db.py` — the harness docstring's four hard rules **`:1-45`** (seed roles `:9-19`, the interleave shape `:21-31`, the two task-using exceptions `:33-43`, own-tenant-id `:44`), and **`test_a_second_claim_landing_in_the_gap_is_refused_and_names_the_occupant` `:218`** — the snapshot-then-nested-commit shape F58 copies, with its *"THE SAVEPOINT'S ONLY WITNESS"* docstring `:221-234`.
- ✅ `backend/tests/test_frontend_imports_are_tracked.py:1-40` — F33's permanent guard: **every relative import in a git-TRACKED frontend module must resolve to a git-TRACKED file**, read through `git ls-files` rather than the disk. `frontend/e2e/fixtures/manage.ts` is a **new directory** and is not `.gitignore`d (checked).
- ✅ `frontend/apps/manage/src/components/FloorPanel.tsx` (759 lines) — `rooms` state `:77`, `fetchCount` `:83`, `serverNow` `:88`, `cue` `:94`, `focusHeadingRef` `:107`, `load` `:137` (`setRooms(result.rooms)` `:149`), `tick` `:197`, the **write-means-write** ⚠ **`:236-243`**, `applyRooms` **`:325-328`** with its *"the collision is MUTATION-vs-MUTATION"* comment `:315-324`, `pause`/`resume` `:330-337`, **`mutate` `:340-384`** (docstring `:340-362`, the `.finally()` re-arm `:379-383`), the cue `<p role="status">` **`:510-521`**, the *"ABOVE the staff list (spec D15)"* comment **`:605-608`** and `<RoomsPanel …/>` **`:609-620`**, the staff `Card` `:622`, the bare-`<bdi>` rule **`:655-660`**, `elapsedLine(t, serverNow, card.occupancy.assigned_at)` `:699`.
- ✅ `frontend/apps/manage/src/components/RoomsPanel.tsx` (955 lines) — the child contract **`:15-31`**, `RoomsPanelProps` **`:84-118`** (ten props; `onRooms`'s updater rule `:107-113`, `onCue` `:117`), `clientPick`'s keyed-by-id ⚠ **`:137-141`**, `busyIds` **`:142`**, **`controlRefs` `:159`**, `dialogTriggerRef` `:160`, `restoreFocusRef` `:161`, `reclaimFocusRef` `:162`, the two render-time captures **`:167-192`**, **MOVE 1 `:230-239`**, **MOVE 6 `:240-255`** (`controlRefs.current.get(reclaim)` `:248`), **MOVE 2 `:256-276`** (`controlRefs.current.get(pending)` `:270`), **MOVE 3 `:278-290`**, **MOVE 5 `:291-307`**, **MOVE 4 `:308-330`**, **`describe()` `:352-388`** (outage fall-through `:387`), **`act()` `:390-416`** (`restoreFocusRef` set `:397`, cleared on failure `:403`), `patch` `:418`, `claim` `:449` with **the cue rule `:464-468`** and `onCue` `:469`, `release` `:490`, the **W-load `return null` `:588-592`**, `<ul className="divide-y divide-border">` **`:638`**, `busy` **`:642`**, the ⚠ **one-`secondary`-per-tile comment `:834-837`**, the claim `Button` **`:839-851`** (`controlRefs.current.set` **`:842`**, `loading={busy}` `:847`), the release `Button` **`:902-914`** (`controlRefs.current.set` **`:905`**, `loading={busy}` `:910`).
- ✅ `frontend/apps/manage/src/lib/elapsed.ts` (37 lines) — **`elapsedMinutes` `:23-25`** (the clamp `:24`, the server-anchor rationale `:14-22`) and **`elapsedLine` `:31-37`**, which hard-codes `rooms.elapsedJustNow` `:34` and `rooms.elapsed` `:36`. D2's rule holds exactly: the waitlist calls `elapsedMinutes` and selects its own two keys.
- ✅ `frontend/apps/manage/src/api.ts` (1 097 lines) — `ApiError` **`:9-30`** (`details?: Record<string, string>` **`:22`**), `extractError` `:39-60`, the envelope comment **`:446-447`** (C12), `FloorResponse` `:448`.
- ✅ `frontend/apps/manage/src/__tests__/i18n.test.ts` (593 lines) — the fold rule `:33-37`, the *"the namespace names the payload, not the feature"* rule `:40-42`, **`HE_F36` `:60`**, **`HE` `:61-71`** (nine constants), the **four** 2.5.3 loops at **`:253`**, **`:311`**, **`:362`**, **`:456-468`** (its array `["claim","release","handover","addDress"]` at **`:461`**), **`HE_F36.length >= 70` `:424`**, the `HE_F36` digit guard **`:445-455`**, the shipped `STAFF_OCCUPIED` assertions **`:501-513`**, the `"!"` filter **`:556`**, the **`/נשלח|תישלח|בדרך/` filter `:560`**, the `ar`-empty scan `:566-575`, the `ar`-**presence** scan **`:575-578`**, and the **`HE_F36`-scoped `ar[key] === he[key]` guard `:580-592`**.
- ✅ `frontend/apps/manage/src/i18n/he.ts` (1 006 lines) — `nav.floor` «הצוות בקומה» **`:607`**, `floor.heading` «צוות בקומה» **`:608`**, `rooms.heading` `:787`, `rooms.elapsed` `:813`, `rooms.error.roomOccupiedUnknown` `:924`, **`rooms.error.STAFF_OCCUPIED` `:929`**, `rooms.error.staffOccupiedUnknown` `:930`. **71 `rooms.*` keys, 29 `floor.*` keys** (C14).
- ✅ `frontend/apps/manage/src/__tests__/Nav.test.tsx:162-165` — the nav label and the heading asserted **together**, which is deck F-1's whole argument.
- ✅ `frontend/apps/manage/src/App.tsx` — `SectionKey` `:21`, **`FLOOR_ONLY` `:49`**, the `floor` NAV row **`:106`**, `section` state `:136`, `activeKey` `:181`, the board's one-shot `scrollIntoView` note `:207-208`, `{activeKey === "floor" && <FloorPanel selfId={staff.id} role={staff.role} />}` **`:215`**.
- ✅ `frontend/apps/manage/vite.config.ts:13-20` — *"The fourteen names"*, *"a fifteenth segment"*, and the fourteen-name alternation **including `floor`**. **F58 touches this file not at all** (D11).
- ✅ `frontend/apps/storefront/src/routes/QueuePositionPage.tsx` — `CLOSED_STATUSES = new Set(["done","removed"])` **`:35`**, the loop stop `:139`, the called-transition cue `:144-148`, **`closed` `:266`**, **`called` `:267`**, `live` `:268`, and the **four render arms at `:319`, `:323`, `:329`, `:338`**.
- ✅ `frontend/apps/storefront/src/routes/ManageBookingPage.tsx` — the two-step: trigger `variant="secondary"` **`:401`**, the question `<p ref={revealRef} tabIndex={-1}>` **`:425`**, the confirm `variant="danger"` **`:459`**, the dismiss `variant="ghost"` **`:470`**. **The precedent's trigger is `secondary`, not `ghost`** (DC-9).
- ✅ `frontend/packages/ui/src/components/Button.tsx` — `sizes` `:35-39` (**`sm: "min-h-9 …"` `:36`, `md: "min-h-11 …"` `:37`**), **`disabled={disabled || loading}` `:57`**, `sizes[size]` `:62`, **`focusRing` `:63`** (C10). `Select.tsx` — **`label: string` `:6`**, `useId` `:14`, `<label htmlFor>` `:19-21`, the class string `:28`, **`focusRing` `:31`**.
- ✅ `frontend/e2e/` — **65** tests: `a11y.spec.ts` **10**, `storefront.spec.ts` **55** (counted with `grep -cE '^\s*test\('`). `const MANAGE = "http://localhost:4174/manage/"` at `a11y.spec.ts:8`. The interception idiom — a per-path reply queue, `take()`, and `page.route("**/storefront/**")` — is `storefront.spec.ts:409-450`. **There is no `frontend/e2e/fixtures/` directory**; D19 creates it.
- ✅ `Makefile` — `test` `:18`, `test-db` `:21`, `test-all` `:24`, `lint` `:27`, `qa-greps` `:33`, `fe-build` `:44`, `fe-test` `:47`, `e2e` `:51`.

---

## The design critic's nine required changes — DC-1 … DC-9

**The verdict is REVISE, not REJECT**, and the reasons matter: the lost-race design (§3.3) is the best thing in either file, token compliance is clean against `tokens.md` (ink-muted 5.61 · warning-text 5.20 · danger 6.18 · white-on-danger ≈7.0, all verified), there is not one AI-generic pattern, and **F-2 is a verified-real blocker catch that justifies the deck on its own**. What follows is the remediation list, each with an owning task. **DC-5, DC-6, DC-7 and DC-9 are document-first and land in Task 0; all nine have build consequences.**

| # | What | Resolution taken here | Owner task |
|---|---|---|---|
| **DC-1** | **The four `waitlist.*Aria` values ship with no mechanical 2.5.3 guard.** `i18n.test.ts` carries **four** separate label-in-name loops — `:253`, `:311`, `:362`, `:456-468` — one per feature that ever added an `*Aria`. F-6 correctly routes `rooms.takeNextAria` into the `:461` array; `callAria`, `assignAria`, `skipAria` and `removeAria` get nothing but §11's hand-count — on the criterion that is *legally binding*, while F-12 declares a twin for the lesser `ar`-parity one | **Declare an `HE_F58`-scoped 2.5.3 assertion** over `["call","assign","skip","remove"]`, `new RegExp("^" + t(\`waitlist.${name}\`))` against `t(\`waitlist.${name}Aria\`, { name: "נועה בר" })`. One `it()`, the `:456-468` shape | **0** (deck §0.1 + §11) + **9** |
| **DC-2** | **The free tile now has two controls, one `controlRefs` slot and one `busy` flag, and only the success path is designed.** `controlRefs` is `Map<roomId, node>` (`:159`), written by claim at `:842` and release at `:905`; MOVE 2 (`:270`) and MOVE 6 (`:248`) both read `.get(id)`. React runs ref callbacks in tree order, so with take-next rendered **first** the claim button's callback runs **last and silently wins the slot** — and on a `QUEUE_EMPTY`/`ROOM_OCCUPIED` refusal the tile stays free, so ~5s later MOVE 6 hands focus to «תפיסת החדר», a control she never touched | **Two rules, both named tests.** (a) **The slot belongs to the tile's FIRST control**: take-next writes it whenever it is rendered, and claim writes it only when `waitlistCount === 0` — one guarded ref callback, no new data structure, and it matches §3.1's declared order. (b) **`disabled` is shared, `loading` is not**: both controls take `disabled={busy}`; a new `pendingControl: Record<string, "takeNext" \| "claim">` (written by the two tile handlers, read only by the two `loading` props) decides which one spins. **Residual, accepted and stated**: a refused «תפיסת החדר» on a tile with a queue hands MOVE 6's focus one control over, to «קחי את הבאה» — both are tile-primary acts in the same action row, and it is strictly better than the last-writer-wins the shipped Map would otherwise give | **0** (deck §3.2, §11.1) + **11** |
| **DC-3** | **`rooms.error.STAFF_OCCUPIED` is third-person and F58's two dispatch verbs are first-person.** §4.1's reveal has **no staffer picker** and the shipped claim never sends `staff_user_id`, so on take-next and push-assign the target **is** the acting manager. She reads «היא כבר בחדר אחר: חדר 5.» — *she* is already in another room — about herself | ⚠ **The critic's cheaper option is not available (C13)**: the literal is asserted in `RoomsPanel.test.tsx:604`/`:616`, `RoomHandoverDialog.test.tsx:238` and `i18n.test.ts:501-513`, so editing the shipped value reds four shipped assertions and breaks this feature's acceptance gate. **Two NEW `rooms.*` keys instead** — `rooms.error.staffOccupiedSelf` «את כבר בחדר אחר: {{room}}.» and `rooms.error.staffOccupiedSelfUnknown` «את כבר בחדר אחר.» — rendered on the **dispatch** targets only; the shipped third-person pair keeps handover, where the target genuinely is a colleague. Not a duplicate value (§0 rule 9 is about values): two subjects, two sentences | **0** (copy §6, §9) + **9** + **11** + **10** |
| **DC-4** | **`RoomsPanel.tsx:834-837`'s shipped comment becomes false** — *"ONE `secondary` per tile and it is the act that ENDS the tile's current state"* — and §3.4 says the file needs no other edit. F36's own PR spent a load-bearing finding on three shipped comments stating a false fact as the rationale for a live decision | **A named build task**, not a drive-by: the comment is rewritten to the restated rule (*"at most one `secondary` per act-type, never more than two on one region; order carries the hierarchy"*) and names why two acts end a free tile's state | **11** |
| **DC-5** | **§0.1 under-enumerates the test edits it calls "the three this deck depends on"**, and §11 claims coverage §0.1 never asks anyone to write | **§0.1 names FIVE**: (1) `HE_F58` declared **and folded** into `HE`; (2) `HE_F36`'s floor `>= 70` → **`>= 76`** (C14) and `i18n.test.ts:461`'s array gains `"takeNext"`; (3) an `HE_F58`-scoped `ar[key] === he[key]`; (4) an `HE_F58`-scoped digit guard; (5) DC-1's `HE_F58`-scoped 2.5.3 loop. §11's counts become **`HE_F58 >= 37`** and **`HE_F36 >= 76`** | **0** + **9** |
| **DC-6** | **The duplicate line is one sentence for two opposite remedies**, and §7's stated remedy — *"the position numbers already say which arrived first"* — answers nothing when the twin is `in_service` and appears nowhere on the panel. `confirmRemoveDuplicate`'s «אפשר לומר לה שהמקום שלה נשמר» is then **false** | **The second branch the critic offers, because the first is unbuildable**: the wire carries `duplicate: bool` by spec D9's reasoned decision and the panel cannot tell the two cases apart. §7 gains a paragraph naming case (b) explicitly and stating that the sentence is already true of it (it says «פעילה» — *live*), while **deleting the false remedy claim**. And `confirmRemoveDuplicate`'s last clause is **corrected to be true in both cases**: «…כדאי לוודא איתה שהכניסה השנייה עדיין פעילה.» — no new key, one value | **0** (deck §7 + copy §5) + **10** |
| **DC-7** | **A successful push-assign has no stated focus destination and silently differs from take-next's** | **It is MOVE 3, the panel `h3`, and the reason is that the row is gone.** Take-next is tapped from a **tile** that survives and flips state, so §3.2 lands on the tile's new primary control; push-assign is tapped from a **row** that leaves the queue with its reveal inside it. Both land on the surface that survives the act. No seventh mechanism, one named assertion | **0** (deck §4) + **10** |
| **DC-8** | **The row alert and the duplicate line are byte-identical in style and adjacent** — both `text-sm font-semibold text-warning-text` — so on a called + duplicate + refused row three meanings carry one treatment | **The duplicate line moves to the MUTED register** (`text-sm text-ink-muted`), which is what §2 already does for `skippedOnce` and for the same reason (*"the confirm is the guard, and this is context"*). The differentiator is then a **rule** rather than a decoration: **on a row, `--color-warning-text` means "this is the answer to what you just pressed"**. One class swap, no new token, and the flag keeps its full sentence plus the confirm's second line | **0** (deck §10, §2.3) + **10** |
| **DC-9** | **P-5 cites a precedent that ships a different variant than the one it adopts.** `ManageBookingPage.tsx:401` is `variant="secondary"`; the deck goes one step below to `ghost`, leaving «הסרה» — the only irreversible control on the screen — visually identical to «קראי» and «דלגי» in a row that wraps at 375 | **Take the precedent: `waitlist.remove`'s trigger is `secondary`.** The deck's own restated rule (§3.1) permits *at most one `secondary` per act-type* and the row then carries two of different types — «שבצי לחדר» (dispatch) and «הסרה» (destructive). `ghost` stays on «קראי» and «דלגי», the two reversible ones, so at 375 the wrapped row distinguishes the irreversible control from the reversible ones by weight rather than by reading order. The reasoning against a permanently **red** trigger is kept verbatim | **0** (deck §5.3, §10, P-5) + **10** |

**Also recorded, not required:** §4.2 overclaims that `waitlist.noFreeRoom` is *"the only surface that explains"* the disappearance — at 375 it sits ~600px below the tiles whose «קחי את הבאה» just vanished. Task 0 narrows the sentence to the rows, which is what it is true of.

---

## Scope fence — read this before every task

**F58 ships one column, five routes, one extended route, one new panel, one control on a shipped panel, three shipped comments rewritten, one storefront precedence fix, and the reusable `/manage/**` e2e harness.** It ships no table, no second poll, no nav row and no analytics.

| Not in F58 | Whose |
|---|---|
| A new table; a unique index on `queue_ticket_id`; any CHECK; any index at all on the new column | **out — D1, and two shipped guards (`test_migrations.py:1617`, `:1648`) make a third index a reviewed act. This is that review, and the answer is no** |
| A sixth route for FINISH; a state-dependent release label | **out — D5, Conflict 2. `release` is extended** |
| SOS, the targeted page, the full-screen overlay, the 30-second escalation | **F37** |
| Wait-time estimates, queue analytics, an SLA colour, anything firing on elapsed minutes | **out — pre-decided #28, spec Out of scope** |
| Bride-priority ordering, any sort control, any filter | **out — `e6-instore-realtime.md:74`; `visit_type` renders and nothing sorts on it** |
| A merge verb, an auto-hide, a reorder of duplicates, a restore/undo for a removal | **out — D8, Decisions 5 and 8** |
| Closing yesterday's unclosed tickets | **F20's retention sweep — Risk 5** |
| Any change to `position()`, `/storefront/checkin`, the three check-in limiters, the QR sheet or the collection notice | **out — spec Out of scope; the notice is `in_run_gates`' F33 entry** |
| Any change to `lib/usePoll.ts`, `App.tsx`, `Nav.test.tsx`, `vite.config.ts`, `qa-greps.sh`, `packages/ui/**` | **out — D15, D11, deck F-1 and F-10. `usePoll.ts` gets a ZERO-LINE diff** |
| A second poll loop, a second pause control, a second `role="status"`, a second freshness stamp | **out — D15 and the LOOP-STATE note in as many words** |
| A `<dialog>` of any kind | **out — D4, Decision 21, deck P-4. Three inline reveals** |
| A customer's name in `role="status"` | **out — D16, Decision 20, deck §11.2. The cues name the ACT** |
| A link from a row to `/q/{id}` | **out — A29** |
| Renaming `floor.heading` / `nav.floor` | **out — deck F-1, declined with a re-set trigger** |
| A `packages/ui` `Select` min-height fix | **out — deck F-10, declined with a re-set trigger** |
| SMS of any kind | **out. F58 sends nothing — which is also why copy §7's send-verb catch matters** |

If a task's diff grows a second `usePoll(...)`, a nav row, a `packages/ui` edit, a `<dialog>`, a new table or a customer name inside `role="status"`, it has left F58.

---

# Part 0 — the plan

## Task 0 — This plan, fourteen spec/deck corrections, and the design critic's nine
`.planning/plans/floor-dispatch.md` (this file), `.planning/specs/floor-dispatch.md`, `.planning/design/screens/floor-dispatch/design.md`, `.planning/design/screens/floor-dispatch/copy.md`

No test, no code. Amend the three documents so each is the binding statement of every resolution above.

**Spec (`floor-dispatch.md`) — C2–C14:**
- **«What already exists», D11** — `test_spa_serving.py:377` → the test is **`:381`**, the set equality **`:409`** (C2).
- **D2, Conflict 5** — `QueueTicketsRepository`'s docstring is **`:48-55`**, the sentence corrected is **`:51-54`** (C3).
- **Problem, D7** — `queue_ticket.py:23-26` → **`:24-26`**; the per-column comments are `:42-49`, `:50-54`, `:55-56` (C4).
- **D10** — `floor/service.py:184-201` → **`:186-200`**, binding clause **`:190-193`**; `occupancy_by_staff_id` `:216-219` → **`:217-219`** (C5). **Add C6 and C7 to D10's list of comments this PR rewrites**: `floor/service.py:202-205` («TWO extra statements» → four) and `floor/router.py:1-2` («thirteen routes» → eighteen). D10 currently names three; it is **five**.
- **D1, Conflict 7** — add the **second** stale model comment, `fitting_room_assignment.py:39-42` (C8).
- **D17** — `RoomsPanel.describe()` `:352-385` → **`:352-388`**, fall-through `:387` (C9).
- **D12** — `floor/validation.py:44-83` → the class opens at **`:43`** (C11).
- **D2** — `api.ts:447-448` → **`:446-447`** (C12).
- **Frontend changes** — `HE_F36`'s floor `>= 70` → **`>= 76`**, not `>= 71` (C14, DC-3, DC-5).
- **Risk 7** — restate that `main`'s head is **`0019`** *and* that **F41 is building with a migration**, so the rule ships, not the number (C1).

**Design deck (`design.md`) — DC-2, DC-3, DC-4, DC-6, DC-7, DC-8, DC-9, C10:**
- **§3.1 / §3.2 / §11.1** — DC-2's two rules: the `controlRefs` slot belongs to the tile's **first** control; `disabled` is shared and `loading` is not; and the refusal path on a tile that stays free, with its accepted residual.
- **§3.3, §5.4, §10** — DC-3: the two dispatch verbs render the **self** form of `STAFF_OCCUPIED`, and handover keeps the shipped third-person one. Record C13 (three shipped assertions) as the reason the value is not edited.
- **§3.4** — DC-4: the `RoomsPanel.tsx:834-837` comment rewrite is a named build task, listed beside the `describe()` branch.
- **§7** — DC-6: name the `in_service` twin case explicitly, delete *"the position numbers already say which arrived first"* as a remedy for it, and state why one sentence is right (the wire carries a boolean by D9's decision; «פעילה» is true of both).
- **§4** — DC-7: push-assign's success focus is **MOVE 3, the panel `h3`**, with the one-line reason it differs from §3.2. Narrow §4.2's "only surface that explains" claim to the rows.
- **§2.3, §10** — DC-8: the duplicate line is **muted**, and the rule is stated: on a row, the notice register means *this is the answer to what you just pressed*.
- **§5.3, §10, P-5** — DC-9: the remove trigger is **`secondary`**; the confirm pair is unchanged; the argument against a **red** trigger is kept.
- **§11.5** — `Button.tsx:62` → **`:63`** (C10). *F36's plan corrected this once; do not reintroduce it a third time.*
- **§13** — a new finding **F-14** recording DC-3's two keys with the shipped-assertion evidence, an owner and a trigger.

**Copy deck (`copy.md`) — DC-1, DC-3, DC-5, DC-6, DC-8, DC-9:**
- **§0.1** — **FIVE** test edits, not three (DC-5), with `HE_F36 >= 76` and `HE_F58 >= 37`.
- **§3** — `waitlist.remove` is `Button secondary md` (DC-9).
- **§5** — `waitlist.confirmRemoveDuplicate`'s last clause corrected: «…כדאי לוודא איתה שהכניסה השנייה עדיין פעילה.» (DC-6). Same key, new value.
- **§6, §9** — the two DC-3 keys added to the `rooms.*` block with their rendering rule; §9's `STAFF_OCCUPIED` rows gain *"handover only"*.
- **§10** — the duplicate line's register (DC-8).
- **§11** — the mechanical pass gains a row for the `HE_F58` 2.5.3 guard (DC-1) and the counts move (DC-5). The key count becomes **37 `waitlist.*` + 5 `rooms.*` = 42**, not 40.

- **Done when**: `grep -n ":377\|184-201\|216-219\|:352-385\|Button.tsx:62\|>= 71\|>= 73\|47-448" .planning/specs/floor-dispatch.md .planning/design/screens/floor-dispatch/*.md` returns nothing; `copy.md` §0.1 names **five** test edits; `design.md` §13 has **fourteen** findings.
- **Commit**: `docs(planning): F58 implementation plan, fourteen spec corrections and the design critic's nine`

---

# Part I — the backend

## Task 1 — The `ALTER TABLE` **and** the ORM column, as one atomic change, plus the two model comments it falsifies (D1 / C1, C8)
`backend/migrations/versions/00NN_floor_dispatch.py` (**✚**), `backend/app/models/fitting_room_assignment.py`, `backend/tests/test_migrations.py`

**Migration + model ship in one commit and this is not a preference.** There is no model↔migration parity test anywhere in `backend/tests/`, and F19's single-head guard proves the *chain* and not the *mapping*. Without the mapped column every backend line in Tasks 2–7 is an `AttributeError`.

### The revision number is a RULE, not a number

```
cd "/Users/mrwen/Documents/Github/Ryan + rawad + mrwen/.worktrees/floor-dispatch/Backend" \
  && uv run python -m alembic heads
```

As of 2026-08-03 it prints **`0019 (head)`**, so the file is `0020_floor_dispatch.py`, `revision = "0020"`, `down_revision = "0019"`. **Do not read that number off this document.** **F41 is building right now with a migration of its own** and F59 merged without one; the head has moved three times in two days before.

1. **BUILD at `alembic heads` + 1**, `down_revision` = whatever head is then — so the branch is self-coherent and its `db`-marked tests actually run. A `down_revision` naming a revision that lives only on another branch makes alembic unable to build the revision map at all, so **every** `db` test fails for the branch's whole life. A wrong number fails **loudly** rather than drifting.
2. **Make the migration the LAST commit on the branch.** Task 1 is early, so the commit is *reordered onto the tip* at rebase — or amended in place, since nothing else in the tree references the revision literal.
3. **RE-RESOLVE from `alembic heads` on `origin/main` immediately before the rebase that precedes the push.** Three edits: the filename, the `revision` literal, the `down_revision` literal.
4. **Do not OPEN the PR while a lower-numbered migration is still unmerged.** CI tests the merge result, and two files claiming one revision id is an alembic multiple-heads error that git cannot see because the filenames differ.
5. **Confirm `alembic heads` prints exactly ONE head on the rebased branch**, and confirm `make test` is green — `test_migrations.py:57` (`test_exactly_one_migration_head`, `get_heads()` at `:76`) is the fast, no-DB guard that catches a bad renumber before CI does. **A32.**

### The failing tests first (`db`-marked except the head guard, appended to `test_migrations.py`, **run locally**)

Follow the file's own conventions: the round-trip goes **last in the file**, owns no fixtures, wraps the downgrade in `try/finally: command.upgrade(cfg, "head")`, and targets **`_parent_of("floor dispatch")`** (`:31-55`) rather than a literal — F36's shipped note records `"-1"` rotting for real when 0019 landed on 0017's test. **The migration's module docstring must therefore contain the marker string this helper greps for.**

1. `test_the_floor_dispatch_migration_adds_one_nullable_column` — `_fitting_columns(migrated_db)` (`:1521`) answers `("fitting_room_assignments","queue_ticket_id") == ("uuid","YES",None)`: nullable, **no default**.
2. **`test_fitting_room_assignments_carries_exactly_two_non_primary_unique_indexes` stays green with NO EDIT** (`:1617`). This is the shipped guard whose purpose is to make a third index a visible, reviewed act.
3. **`test_the_fitting_room_tables_carry_no_check_constraints` stays green with NO EDIT** (`:1648`). D1 adds none — not even `num_nonnulls(booking_id, queue_ticket_id) <= 1`, whose "invariant" is false about a bride who booked ahead *and* scanned the QR.
4. **`test_the_three_partial_unique_index_definitions_are_pinned` stays green with NO EDIT** (`:1581`) — an `ADD COLUMN` does not touch a partial index's deparsed definition, and asserting it is what catches a builder who "helpfully" widens a predicate while in the file.
5. **`test_queue_tickets_carries_no_unique_index_but_the_primary_key` (`:1023`) and `test_the_queue_tickets_migration_pins_its_checks_and_its_one_index` (`:1007`) stay green with NO EDIT** — F58 writes all four `status` values the shipped CHECK already admits and widens nothing.
6. `test_migration_00NN_round_trips` — upgrade applies and the column exists; `downgrade` one revision and the column is **gone**; `upgrade` to head and it is back. **Last in the file, in `try/finally`.** Probing both directions is `0013`'s rule: a silently no-op downgrade stays green while shipping an unrollbackable migration.

### The code

The migration is **one `op.execute`** and a comment block that is the actual deliverable — the `0014_booking_check_in.py` idiom, D1's text verbatim, covering: no `NOT NULL`, no FK/CASCADE, **no CHECK** (with the bride-who-did-both reason), **no unique index** (with the conditional-UPDATE-is-the-serialisation-point reason and the two shipped guards named), **no non-unique index** (nothing reads this column as a predicate), and **no GRANT and no `enable_tenant_rls`** (the table already has both; RLS is per-table, not per-column).

`downgrade()` carries the ⚠ **UNLIKE F36's, THIS DOWNGRADE CAN LOSE LIVE DATA** warning — it drops the only record of which walk-in each fitting served. F57's role-widening migration carries the same warning for the same reason.

`models/fitting_room_assignment.py` gains `queue_ticket_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)` **and rewrites both stale comments**:
- **`:26-29`** — *"No personal field of any kind. `booking_id` and nothing else"* → the stronger rule that survives: **neither pointer is a snapshot**; both resolve on every read from the live rows, so a retention sweep or an erasure renders an anonymous visit rather than quietly preserving a name in a table nobody thought of.
- **`:39-42`** (C8) — *"any walk-in until F58 ships the queue link, produces a row with no client"* → after this PR both-null is a **staffer prepping a room**, which is the case that comment always anticipated. `copy.md` §9's `rooms.anonymous` row says the same thing on the other side of the wire.

### Mutation-checks (mandatory — RUN them, do not reason about them)

| Mechanism | Remove it | Expect |
|---|---|---|
| the column's nullability | make it `NOT NULL` | test 1 **RED**, and the upgrade itself fails on any existing row — which is the point: every assignment F36 created has it null |
| `downgrade` | make it `pass` | test 6 **RED** on the reverse assertion |
| the absence of a unique index | add `(tenant_id, queue_ticket_id) WHERE released_at IS NULL AND deleted_at IS NULL` | test 2 **RED** (count 2 → 3). ⚠ **Run this one deliberately, then revert it** — it is the only way to prove D1's headline decision is guarded rather than merely written down |
| the docstring marker | rename it | test 6 **RED** in `_parent_of`, immediately and by name |

- **Done when**: `bash "<scratchpad>/run-db-tests.sh"` green (baseline + the new cases); `make lint` clean; `make test` green **including `test_exactly_one_migration_head`**. `git show --stat` confirms the lowercase pathspecs landed.
- **Commit**: `feat(floor): the assignment's pointer at the walk-in it serves — one column, its model and its four untouched guards`

## Task 2 — `QueueTicketsRepository`: five writers, the refusal projection, the waitlist read and the duplicate projection (D2, D3, D4, D6, D7, D8, D9 / C3)
`backend/app/db/repositories/queue_tickets.py`, `backend/tests/test_queue_repositories.py`

### The failing tests first (`db`-marked, **run locally**)

**⚠ THE HARNESS'S FOURTH HARD RULE IS F58'S OWN AND IT BELONGS IN THIS MODULE'S DOCSTRING: every waiting ticket in an ordering test is inserted in its OWN `tenant_session`.** `0018_queue_tickets.py:29` is `created_at TIMESTAMPTZ NOT NULL DEFAULT now()` and Postgres's `now()` is **transaction-start**, so tickets batched into one transaction share a sort key **to the microsecond**: the list collapses onto the `, id` tiebreak (random UUID order, so "arrival order" asserts nothing) and `position()` returns **1 for all of them**. A builder batching the seeds for speed gets a red whose most tempting fix is to weaken A3, which makes it vacuous.

Per method:

- **`claim_next(session, tenant_id, *, day)`** — D3's statement. Returns the four `RETURNING` columns or `None` on an empty queue. Tests: claims the earliest by `COALESCE(requeued_at, created_at)`; a requeued ticket sorts **behind** a later-arriving one; an empty queue answers `None` and writes nothing; yesterday's waiting ticket is **not** claimable today.
- **`claim_by_id(session, tenant_id, ticket_id)`** — D4's conditional UPDATE. Rowcount 0 on a non-`waiting`, soft-deleted, foreign-tenant or missing ticket.
- **`close(session, tenant_id, ticket_id)`** — D5's `status='done' WHERE status='in_service'`. Rowcount 0 on a `removed` ticket is **not** an error.
- **`skip(session, tenant_id, ticket_id, *, now, seen_skip_count, limit)`** — D6's single statement with **`AND skip_count = :seen_skip_count`**. Tests: first skip → `(1, 'waiting')`, `requeued_at` stamped, **`called_at` cleared**; second skip → `(2, 'removed')`; a stale `seen_skip_count` → rowcount 0.
- **`call(session, tenant_id, ticket_id, *, now)`** — D7's `called_at IS NULL` predicate. A second call is rowcount 0 and the **first** timestamp survives.
- **`remove(session, tenant_id, ticket_id)`** — D8.
- **`status_of(session, tenant_id, ticket_id) -> tuple[str, int] | None`** — **the refusal read, and it is a PROJECTION** (Decision 10). Its docstring states why it is not `by_id`: `by_id` (`:85`) is a `select(QueueTicket)` **entity** read that would pull `phone` and `marketing_opt_in_at` into the same session as an ORM-enabled UPDATE and put a `QueueTicket` in the identity map at exactly the moment `_refreshed`'s docstring says this repo has been bitten three times.
- **`waiting_for_panel(session, tenant_id, day, *, limit)`** — D2's column projection, **`.where(*_live_waiting(tenant_id, day)).order_by(_sort_key().asc(), QueueTicket.id.asc()).limit(WAITLIST_LIMIT)`**. ⚠ **The predicates and the sort key are `_live_waiting()` and `_sort_key()` CALLED, never re-spelled** — `_live_waiting`'s own docstring (`:22`) names *"F58 widening one status filter, say"* as the hazard it exists to prevent.
- **`in_service_phones(session, tenant_id, day)`** — D9's second statement. ⚠ **`_live_waiting` CANNOT be reused here**: its third predicate is `status == 'waiting'` and the whole point of this read is the rows that are not. A **phone-only** projection: no name, no id, nothing that could be rendered by accident.

⚠ **EVERY ORM-enabled UPDATE in this module carries `.execution_options(synchronize_session=False)`** — all six. SQLAlchemy 2.0's default is `'auto'` (`'evaluate'` then `'fetch'`); none of these WHERE clauses is Python-evaluable, D6's `skip_count + 1` and `CASE` least of all, and no caller reads an identity-mapped instance afterwards. `False` is the only spelling that is both correct and free.

⚠ **The class docstring is CORRECTED in this PR** (C3, Conflict 5). `:51-54` promises *"no read keyed on `phone` … That absence is the security property"* and D9's grouping is keyed on `phone`. The property that was actually load-bearing survives and is restated: **no read on an anonymous, unauthenticated surface is keyed on `phone`, and no response body anywhere carries it.** The oracle Ruling 3 closed was a public one; a signed-in staffer of this tenant grouping today's own arrivals is a different surface with a different threat model.

`WAITLIST_LIMIT = 100` is a module constant with D2's *"A BOUND, not a page size"* comment. `truncated = len(rows) == WAITLIST_LIMIT`.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| `_live_waiting()` **called** rather than copied | inline the four predicates and drop `queue_day` | the ordering-agreement test in Task 8 **RED**. ⚠ **Stays GREEN in this module** if every seed is today's — record that here and pin it there |
| `AND skip_count = :seen_skip_count` | drop the conjunct | **stays GREEN here** — a single-threaded test always sends what it read. Pinned in Task 8's forced interleave. **Record it** |
| `called_at IS NULL` on `call` | drop it | the second-call test **RED** on a moved timestamp |
| `called_at = NULL` in `skip` | drop it | the first-skip test **RED** — she keeps her «נקראה» at the back of the queue and F59's board highlights her there |
| the `CASE` reading the **pre-update** `skip_count` | change to `skip_count >= 2` | the second-skip test **RED** — she is never removed |
| `status = 'in_service'` in `close` | drop it | the removed-then-released test **RED** — a manager's removal is resurrected as `done` |
| `status_of`'s projection | call `by_id` instead | **stays GREEN** — the values are the same. **Record that in the docstring**: the reason is minimisation and the identity map, not the answer |

- **Done when**: local db suite green; `make lint` clean; the three "stays green" mutations performed, **recorded in docstrings** and restored. `git show --stat`.
- **Commit**: `feat(queue): the five ticket writers, the refusal projection and the waitlist read`

## Task 3 — The wire shapes, three error codes and their handlers, four `AuditAction` members (D2, D12, D13)
`backend/app/floor/schemas.py`, `backend/app/floor/validation.py`, `backend/app/models/constants.py`, `backend/app/main.py`, `backend/tests/test_floor_api.py`

### The failing tests first (**fast**, no Postgres)

- **The three 409 bodies asserted from a LIVE response**, each including its `details` where it has one, **plus the `details`-less variants**: `QUEUE_EMPTY` (no `details` ever), `QUEUE_TICKET_NOT_WAITING` (`{"status": …}` and its `details`-less twin), `QUEUE_TICKET_CHANGED` (`{"skip_count": …}` and its twin).
- **`SPEC_ERROR_CODES` (`:127-135`) goes from SEVEN to TEN and stays a set equality** re-derived at `:1175`. Its ⚠ *"SEVEN after F36"* comment (`:118-126`) is **rewritten, not deleted**.
- **`WaitlistEntry`'s key set asserted by SET EQUALITY** — the assertion that catches an eighth key arriving unreviewed on a five-role payload, which is how F36 pinned `StaffCard`.
- **A4's recursive scan**: no value in the whole payload matches `^\+972\d{9}$`, and no key is `phone`, `marketing_opt_in_at` or `queue_day`.

### The code

- `app/floor/schemas.py` — `WaitlistEntry` (`id`, `name`, `visit_type`, `position`, `arrived_at`, `called`, `skip_count`, `duplicate` — **eight fields, each carrying D2's comment verbatim**), `Waitlist` (`entries`, `truncated`), `DispatchResult` (`room`, `waitlist`), and `FloorResponse` gains **one** key: `waitlist: Waitlist`. `StaffCard`, `Room`, `RoomAssignment`, `Occupancy` and `server_now` are **untouched**. Request bodies `TakeNextRequest` / `AssignRequest` / `SkipRequest` are `ForbidExtraModel`.
  ⚠ `position` is **`index + 1` over this list's own order**, never a second count query — F59's D3 argument: two derivations of one number are two chances for the wall, her phone and this panel to disagree. ⚠ `arrived_at` is **`created_at`**, never the sort key (Decision 19). ⚠ `called` is a **boolean**, not the timestamp.
- `app/floor/validation.py` — `QueueEmptyError`, `QueueTicketNotWaitingError`, `QueueTicketChangedError`, all subclassing the `_OccupiedError` **pattern** (`:43`) and **explicitly NOT `DomainValidationError`**: Starlette resolves a handler by walking `type(exc).__mro__`, so parenting them onto the domain-400 base makes the shipped 400 handler answer first and leaves the 409 handlers unreachable. The trap is written out at `:44-52`; copy the reasoning, not just the base class.
- `app/main.py` — three module constants beside `ROOM_OCCUPIED_BODY` (`:339`), three three-line handlers, **`_occupied_body` (`:350-365`) reused unchanged** for the two that carry `details`. **`QueueTicketNotFoundError` needs no handler at all** — `queue/validation.py:59` records that the base class's 404 answers it, which is why the subclass is free (D4).
- `app/models/constants.py` — `QUEUE_TICKET_DISPATCHED` / `_CALLED` / `_SKIPPED` / `_REMOVED`, D13's comment block verbatim: **one** value for both dispatch verbs with the mode in `details`; **no second `FITTING_ROOM_CLAIMED` row**; **a NO-OP WRITES NO ROW**; **no name and no phone in any `details`**. `audit_log.action` is plain TEXT with no CHECK — the **eighth** block to rely on that.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| any one of the three handlers | drop the registration | that code's body test **RED** (bare 500) |
| the `_OccupiedError` parentage | reparent onto `DomainValidationError` | every one of the three answers **400** and all three body tests **RED** — run this once, deliberately, to prove the MRO trap is real |
| `SPEC_ERROR_CODES` sized from prose | write nine members | the `:1175` set equality **RED** |
| the `WaitlistEntry` key-set equality | add a ninth field | the set equality **RED**. Confirm it, then revert |

- **Done when**: `make lint` + `make test` green. **First milestone**: the whole wire contract and all three codes exist with no Postgres. `git show --stat`.
- **Commit**: `feat(floor): the waitlist wire shapes, three queue 409s and four audit actions`

## Task 4 — `FloorService.take_next`, and `_occupied_error` in full (D3, D3a, D12 / DC-3)
`backend/app/floor/service.py`, `backend/tests/test_floor_service.py`

**This is the task the whole feature is about.** Read D3 and D3a before writing a line. **The failure this prevents is a customer marked `in_service` with nowhere to be, recoverable only with `psql`.**

### Two additions the class does not have (verified at `:161-177`)

- `self._tickets = QueueTicketsRepository()` in `__init__` — the constructor builds ten repositories and none of them is this one.
- `def _today(self) -> date: return today_jerusalem(self._clock)`, written **beside `_today_window()` (`:719-733`) and called by it**, so the waitlist day, the take-next day and the client picker's window cannot drift apart — which is the argument `_today_window`'s own docstring already makes.

### The failing tests first (**fast**, fakes)

- **Authorization**: elevated on anyone → allowed; each floor role **on herself** → allowed; each floor role **on another** → `NotAuthorizedError` **and the room repository is never called**. That last clause is the only way to state that the 403 precedes the read (`service.py:19-24`), and `_authorize` now has **five** call sites.
- **A8c** — an **unrecognised** unique violation, injected as an `IntegrityError` whose `__cause__` carries an unknown `constraint_name`, **re-raises** (→ 500) rather than becoming a 409.
- **A8b's fast half** — `_occupied_error` has **no** `active_for` call. Assert it structurally: the fake assignment repository's `active_for` is never invoked on any take-next path.
- The two-answer shape of every refusal, and **no audit row on any of them**.

### The code — ordered exactly

```python
async def take_next(self, tenant_id, room_id, *, staff_user_id, actor) -> DispatchRead:
    target_staff_id = staff_user_id or actor.id
    self._authorize(target_staff_id, actor)          # 1. before any read
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

**⚠ THE GUARANTEE, AND IT IS NOT THE ONE THE SPEC'S FIRST DRAFT NAMED.** `db/tenant.py:25` is `async with session_factory() as session, session.begin():`, so an exception propagating out of that `async with` **ROLLS BACK**. A raised 409 rolls the ticket write back with or without a savepoint. The rule that actually holds:

> **Every refusal on this path RAISES out of `tenant_session`, and no code inside the `async with` may `return` after the ticket UPDATE has run.** A `return` from inside the block is the one construct that commits.

**There is NO savepoint and NO idempotence branch.** No savepoint because nothing after the conflict needs the transaction alive — the occupant read moves to a second, short, read-only `tenant_session`, paid only on a refusal, with the tenant id passed as an argument so there is no second place for it to be wrong. **No idempotence branch because the transaction that would have made a 200 true is gone**: every `IntegrityError` out of this transaction is a refusal, and answering 200 would report a dispatch that claimed nobody while consuming the head of the queue.

**`_occupied_error` in full, because "one helper shared by take-next and push-assign" is not a specification and the shipped analogue (`_resolve_claim_conflict`, `:372-411`) has two branches this one must NOT inherit:**

```python
async def _occupied_error(self, tenant_id, room_id, target_staff_id, error) -> Exception:
    """Returns the exception to raise. The caller does `raise ... from error`.

    ⚠ NO IDEMPOTENCE BRANCH. `active_for` is deliberately NOT consulted: on
    these two verbs the ticket write is live and a `return` would commit it
    (D3a). The shipped analogue's FIRST branch (`service.py:398-400`) is
    exactly that `return`, and copied here it strands a customer.

    ⚠ The ROOM is resolved FIRST and WITHOUT the constraint name — F36's rule
    applied to a case its own branch order cannot cover: a claim violating BOTH
    indexes reports whichever has the lower OID, i.e. migration creation order,
    which flips after any REINDEX CONCURRENTLY or pg_repack.

    ⚠ An UNRECOGNISED constraint RE-RAISES, unchanged from F36. This is why the
    helper RETURNS an exception rather than raising one — `return error` is how
    that branch is expressible at all.
    """
    async with tenant_session(self._sessions, tenant_id) as session:
        occupant = await self._assignments.occupant_of_room(session, tenant_id, room_id)
        if occupant is not None:
            return RoomOccupiedError(await self._occupant_details(session, tenant_id, occupant))
        held = await self._assignments.room_of_staff(session, tenant_id, target_staff_id)
        if held is not None:
            return StaffOccupiedError(await self._held_room_details(session, tenant_id, target_staff_id))
    if violated_index(error) is None:
        return error                       # unrecognised → 500, F36's rule
    return RoomOccupiedError(None)         # the winner released in the gap
```

⚠ **`violated_index()` is IMPORTED, not re-derived** (`fitting_room_assignments.py:21-43`). `getattr(exc.orig, "constraint_name", None)` is **always `None`** here — SQLAlchemy's asyncpg dialect rebuilds the error as a formatted string and raises it `from` the original — and F36's shipped note records that the obvious spelling made **every 409 a 500 with the happy path green**. The working form is `getattr(getattr(error.orig, "__cause__", None), "constraint_name", None)` and it already exists. **Do not write a second one.**

**Step 2b is a FAST PATH, not the guarantee.** `by_id_for_update` holds the room's row lock and `has_active_for_room`'s shipped docstring is the authority for why a read issued *after* that lock sees the committed claim. We call `occupant_of_room` rather than `has_active_for_room` because it is the same predicate returning the row the 409 needs anyway — one read, not two (spec Rejected finding 1). Without 2b, the feature's **most likely collision** claims a real customer's ticket and throws it away, and a third take-next SKIP-LOCKs past it — Risk 1's out-of-order service *manufactured by the design rather than forced by it*.

**DC-3's rendering half is a backend fact too**: the two dispatch verbs never take a target other than the caller in the shipped console, so the `STAFF_OCCUPIED` they raise is about the acting manager. The backend answer is unchanged (one code, one `details`); the *sentence* is the client's choice, and Task 9/11 render the self form.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| `_authorize` running **before** any read | move it after step 2 | the never-called assertion **RED** |
| the unrecognised-constraint re-raise | map it to `ROOM_OCCUPIED` | A8c **RED** |
| the absence of an idempotence branch | add `active_for` + `return self._room_read(...)` inside the `async with` | **stays GREEN across every fast test** — fakes raise no `IntegrityError`. **Record that here and pin it in Task 8's A8**, which is where it strands a customer |
| step 2b | delete the occupant read | **stays GREEN here** — no fake commits a competing assignment. Pinned in Task 8's A8b |
| the second `tenant_session` in `_occupied_error` | reuse the aborted one | **stays GREEN here**; in Task 8 it raises `PendingRollbackError` and the 409 becomes a 500 |

**Four of those five stay green here and that is the finding, not a failure.** Write them into the module docstring and pin each in Task 8 — that is exactly how F57, F36 and F59 each found a real vacuous test.

- **Done when**: `make lint` + `make test` green. **Second milestone**: the authorization matrix and the refusal helper's every branch are exercised with no Postgres. `git show --stat`.
- **Commit**: `feat(floor): take-next — one transaction, no savepoint, no idempotence branch`

## Task 5 — Push-assign, call, skip and remove (D4, D6, D7, D8)
`backend/app/floor/service.py`, `backend/tests/test_floor_service.py`

### The failing tests first (**fast**, fakes)

- **`assign`** — identical to `take_next` except step 3 names the ticket. Same `_authorize`, same step 2b, same `try`/`_occupied_error`, **same absence of a savepoint and of an idempotence branch**. Rowcount 0 → `status_of` → the **two-answer** table: `None` → `QueueTicketNotFoundError` (404); `status != 'waiting'` → `QueueTicketNotWaitingError` (409, `details={"status": …}`).
- **`call`** — ⚠ **THREE answers, not D4's two**, and this is where a builder implementing D4's table literally falls through with no branch at all. The extra `called_at IS NULL` conjunct adds the third, and on this verb rowcount 0 is the **normal, expected, non-error** case:

  | `status_of` result | Answer |
  |---|---|
  | `None` | 404 |
  | `status != 'waiting'` | 409 `QUEUE_TICKET_NOT_WAITING` |
  | `status == 'waiting'` (i.e. `called_at` was already set) | **200, the current waitlist, NO audit row** |

  **A17** asserts the third row explicitly. `status` is **not touched** — F59's board reads `status == 'waiting'`, and flipping it at call time drops the called row off the board the instant it is called, which is the opposite of the feature.
- **`skip`** — rowcount 0 → a **THREE-answer** read (`status_of` returns `(status, skip_count)` for exactly this): no row → 404; `status != 'waiting'` → 409 `QUEUE_TICKET_NOT_WAITING`; `status == 'waiting'` with a different `skip_count` → **409 `QUEUE_TICKET_CHANGED`**, `details={"skip_count": …}`.
- **`remove`** — D4's two-answer read (remove has no `skip_count` conjunct, so its rowcount 0 really does have only two causes).
- **Audit**: `QUEUE_TICKET_DISPATCHED` `{ticket, room, assignment, staff, mode}` on both dispatch verbs and **no second `FITTING_ROOM_CLAIMED`**; `QUEUE_TICKET_CALLED` `{ticket, called_at}`; `QUEUE_TICKET_SKIPPED` `{ticket, skip_count, status}` — so a removal-by-second-skip is legible without a fifth action value; `QUEUE_TICKET_REMOVED` `{ticket}`. **No name and no phone in any `details`.** **A no-op writes no row**, asserted three times.
- **Take-next and push-assign do NOT stamp `called_at`** (Decision 8): `QueuePositionPage.tsx` renders `called` ahead of the in-service arm, so stamping both would make «התור שלך התחיל» unreachable on every path in the product.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| `call`'s third branch | implement D4's two-answer table literally | A17 **RED** — a silent no-op reported as success, or a 500 |
| `skip`'s `QUEUE_TICKET_CHANGED` branch | fold it into `QUEUE_TICKET_NOT_WAITING` | the stale-count test **RED** on the code |
| the no-audit-on-no-op rule | write a row on the second call | the audit-count assertion **RED** |
| `assign`'s absence of a savepoint | copy `FloorService.claim`'s | **stays GREEN here.** Pinned in Task 8 |

- **Done when**: `make lint` + `make test` green. `git show --stat`.
- **Commit**: `feat(floor): push-assign, call, skip and remove — their guards and their three refusal tables`

## Task 6 — `release` extended, `_occupancy_rows`'s fifth join, and the five shipped comments this PR falsifies (D5, D10 / C5, C6, C7)
`backend/app/floor/service.py`, `backend/app/db/repositories/fitting_rooms.py`, `backend/app/floor/router.py`, `backend/app/floor/schemas.py`, `backend/tests/test_floor_service.py`

### The failing tests first (**fast**, and one shipped suite that must stay green)

- **`queue_ticket_id IS NULL` → byte-identical shipped behaviour.** Every assignment F36 ever created takes the untouched path, so **`test_floor_service.py`'s and `test_floor_rooms_db.py`'s release suites stay green with NO EDIT — and that is the acceptance gate, not a hope** (Risk 10).
- `wrote is False` → **no close**. A second release is a 200 that writes nothing; closing an already-closed ticket must not write either. Both no-ops, one condition.
- The audit row is the shipped `FITTING_ROOM_RELEASED` **with one key added to `details`** — `{"queue_ticket": str(id) | None}`. One act, one row.
- **A20** — a dispatched walk-in's name renders as the room tile's `client_label`; a **soft-deleted** ticket renders an anonymous visit.

### The code

**`release`** gains, inside its existing transaction, after the existing `wrote` branch:

```python
if wrote and row.queue_ticket_id is not None:
    await self._tickets.close(session, tenant_id, row.queue_ticket_id)
```

One transaction. `release()` already runs inside `tenant_session`; the ticket close is one more statement in it. **The worker frees and the entry closes together, or neither does** — the ruling's requirement, satisfied by an addition rather than a new boundary. `AND status = 'in_service'` in `close`'s predicate means a ticket a manager removed mid-fitting stays `removed`; rowcount 0 there raises nothing, because the room is free, which is what she asked for.

**HANDOVER and `delete_room` need no change at all** — handover mutates `staff_user_id` alone, so `queue_ticket_id`, `created_at`, the assignment id and the dress bindings all survive for free (`fitting_room_assignments.py:235-260`); `delete_room` already refuses an occupied room with `ROOM_OCCUPIED`.

**`_occupancy_rows` (`fitting_rooms.py:254`) gains a FIFTH `outerjoin`**, at the end of the chain after `customers`:

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

⚠ **The projection is eleven columns and `client_label=row[10]` is at `:334` — adding a column shifts the index.** Read the SELECT list before editing it.

- **`deleted_at IS NULL` and nothing else on this join**, and the asymmetry with the `bookings` join is deliberate: a cancelled appointment is not a fitting, but a ticket's terminal statuses are the *normal end* of a fitting the tile may still be rendering in the same transaction, so filtering on status would blank the label at exactly the wrong instant.
- **`COALESCE` and not a branch** — both pointers are nullable and independent; null/null is the anonymous visit F36 already ships.
- **`RoomRow` gains no field; `client_label` gains a source**, so all three callers (`list_with_occupancy`, `room_with_occupancy`, `occupancy_for_staff`) inherit it, and `Occupancy` on the staff card inherits it for free through `occupancy_by_staff_id` (`:217-219`).

**FIVE shipped comments are rewritten in this PR, not three.** D10 names three; C6 and C7 add two:

| File | Line | What it says now | What it becomes |
|---|---|---|---|
| `floor/router.py` | **`:17-26`** | *"at most one name per occupied room"* | D10's rewritten paragraph — **the people physically in the boutique right now**, one name per occupied fitting room **plus every walk-in currently waiting**, never the day's booking book; every name leaves the payload the moment she does; **and it DOES carry each waiting ticket's id, which is F33's position-page capability**, disclosed to a signed-in staffer of this tenant and to nobody else, and **the console must never render it as a link to `/q/{id}`** |
| `floor/router.py` | **`:1-2`** (C7) | *"thirteen routes on /manage"* | **eighteen** |
| `floor/service.py` | **`:186-200`** (C5) | the same false clause | the same rewritten paragraph |
| `floor/service.py` | **`:202-205`** (C6) | *"TWO extra statements on the tick's EXISTING session"* | **four** — `list_with_occupancy`, `by_assignment_ids`, the waitlist read and the in-service phone projection |
| `floor/schemas.py` | **`:13-19`** | the same false clause | the same rewritten paragraph |

⚠ **The last clause of D10's rewrite was written twice before it was true.** An earlier draft ended *"…or a stable customer identifier"* — false about the payload it was introducing, since `WaitlistEntry.id` is stable for the whole visit and is a bearer capability. **Shipping a newly-written false comment is worse than leaving an old one**: it is the sentence the reviewers of F20, F37 and F41 will rely on, at the exact moment the name count goes from ≤3 to ≤100 on a five-role router (Risk 4).

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| the `wrote` guard on the close | close unconditionally | the second-release test **RED** — the ticket is re-closed and an audit row appears |
| `QueueTicket.deleted_at.is_(None)` on the fifth join | drop it | A20's soft-deleted half **RED** — a swept ticket keeps naming the tile |
| the `COALESCE` order | swap to `coalesce(QueueTicket.name, Customer.name)` | the bride-who-did-both test **RED** — she resolves to the ticket name rather than the `customers` record with a verified phone behind it |
| the fifth join entirely | drop it | every dispatched walk-in renders `rooms.anonymous` — A20 **RED**, and it is the surface whose entire purpose is to say who is in the room |

- **Done when**: `make lint` + `make test` green; **`git diff main -- backend/tests/test_floor_service.py` shows ADDED blocks only** for the release suite. `git show --stat`.
- **Commit**: `feat(floor): the release closes its ticket, the tile resolves a walk-in, and five comments this PR falsifies`

## Task 7 — Five routes on the shipped floor router, their gates, and the two structural tables (D11)
`backend/app/floor/router.py`, `backend/tests/test_floor_api.py`, `backend/tests/test_staff_role_gating.py`

### The failing tests first (**fast**)

**`test_floor_api.py`** — `FLOOR_OPEN_ROUTES` goes **9 → 12**, `FLOOR_TIGHTENED_ROUTES` **4 → 6**, `FLOOR_ROUTES` **13 → 18**, and **D11's table is the only source for those counts**: a figure sized from prose reds a table-driven test on the first run, and this one powers the 401 walk (`:486`), the wiring guard (`:514-516`), the tenant walk (`:633`), the `no-store` parametrization (`:605`) and the CSRF fence (`:1120`). `FakeFloorService` grows the five new methods.

**`test_staff_role_gating.py`** — **`FLOOR_OPEN` (`:123-133`) gains exactly THREE entries** as route **TEMPLATES**, never concrete urls (`:93-96`): take-next, assign, call. **Skip and remove are DELIBERATELY ABSENT**, and that absence is the assertion that the tightening is real — the ⚠ block at `:118-122` is **extended, not replaced**.

⚠ **The intersection classifier at `:310-316` MUST NOT BE TOUCHED, and D11 explains why the obvious middle option is structurally forbidden.** `require_role(OWNER, SHIFT_MANAGER, RECEPTION)` lands in `admits_floor` (the intersection is non-empty) **and** in `partial` (it is not a superset of `FLOOR_ROLES`), so `assert not partial` (`:329`) red-fails on a route that is arguably correct. The docstring anticipates the response and forbids it: the test *"MUST NEVER BE RELAXED TO A SUBSET CHECK"*, and *"A reviewer facing that red on a test declared untouchable is most likely to 'fix' it by relaxing the assertion, which is precisely the outcome Risk 1 exists to prevent."* **So every route in this product is all-five or exactly-two. Skip and remove are `ELEVATED`, and the product cost — a reception staffer cannot skip a no-show or remove a duplicate; she calls a shift manager — is recorded rather than engineered around.**

### The code

| Method | Path | Gate | In `FLOOR_OPEN`? |
|---|---|---|---|
| `POST` | `/manage/floor/rooms/{room_id}/take-next` | router's five + service `_authorize` | **yes** |
| `POST` | `/manage/floor/rooms/{room_id}/assign` | same | **yes** |
| `POST` | `/manage/floor/queue/{ticket_id}/call` | router's five, no service check | **yes** |
| `POST` | `/manage/floor/queue/{ticket_id}/skip` | **`ELEVATED`** (`:173`, reused not redeclared) | **no — absence is the assertion** |
| `POST` | `/manage/floor/queue/{ticket_id}/remove` | **`ELEVATED`** | **no — absence is the assertion** |

**Every path's second segment is `floor`, so `apps/manage/vite.config.ts` needs NO EDIT** — and that is not free to get wrong. `test_spa_serving.py:381` asserts **set equality** (`:409`) between the live route table's second segments and the `^/manage/(…)` alternation, and a mismatch breaks **only a developer's machine** while production, CI and the whole suite stay green, serving the SPA shell where the API should be. **`/manage/queue/{id}/call` reads better and costs that edit.** **A23** is the assertion: `git diff main -- frontend/apps/manage/vite.config.ts` is **empty**.

**CSRF**: all five are POSTs, and `CsrfOriginMiddleware` gates on `request.method in MUTATING_METHODS` under `/manage` (`csrf.py:48`) — a method test, not a path list, so the five are fenced by construction. **No rate limiter** — no `/manage` router carries one.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| `ELEVATED` on skip or remove | drop it | `test_the_floor_roles_reach_exactly_the_floor_routes` **RED** as `unexpected=[that path]` |
| `FLOOR_OPEN`'s omission of the two | add `skip` to it | the same test **RED** as `missing` — confirm the table is a real assertion in both directions |
| `FLOOR_ROUTES` sized from prose | write seventeen rows | the wiring guard (`:514-516`) **RED** naming the count mismatch |
| mounting the queue verbs at `/manage/queue/…` | change the prefix | `test_the_manage_dev_proxy_names_every_manage_api_segment` **RED**. ⚠ **Run this one deliberately, then revert it** — it is the only way to prove A23 is a live assertion rather than a coincidence |

- **Done when**: `make lint` + `make test` green; `git diff main -- frontend/apps/manage/vite.config.ts` empty; the proxy mutation performed and reverted. **Third milestone**: all eighteen routes, all three new codes and the whole extended payload are exercised end to end with no Postgres. `git show --stat`.
- **Commit**: `feat(floor): the five dispatch routes, their two gates and the two structural tables`

## Task 8 — The forced interleaves and the cross-tenant probes (**`db`-marked, run locally**) (D3a, D4, D6, D7, D9, D10)
`backend/tests/test_queue_dispatch_db.py` (**✚**)

**This is the task the deployment gates are discharged on**, and F58's races are harder than F36's.

### The harness's hard rules, all four, in this module's docstring

1. **Every row this module COMMITS holds `owner` or `shift_manager`, never a floor role.** `migrated_db` is session-scoped, pytest collects alphabetically, and `test_migrations.py::test_adding_the_role_check_validates_existing_rows` re-adds 0011's two-value CHECK over whatever rows exist (`test_floor_rooms_db.py:9-19`).
2. **Every test mints its own tenant id; nothing truncates.**
3. **`asyncio.gather` is never used for a deterministic branch.** The default shape is F36's shipped one (`test_floor_rooms_db.py:218-274`): open a read-only snapshot `tenant_session` and assert the contested resource reads **FREE** — which is what makes the gap *observable* rather than assumed — commit the winner in a **nested** `tenant_session`, then call the service. No tasks, no `Event`, no hang. `asyncio.Event` + `HOLD_SECONDS` is reserved for the cases where a statement must genuinely **block** on uncommitted work: the SKIP-LOCKED timing test and the two concurrent-skip tests, **and nothing else in this feature**.
4. **⚠ F58's OWN: every waiting ticket in an ordering test is inserted in its OWN `tenant_session`.** `created_at` is `DEFAULT now()` and Postgres's `now()` is **transaction-start**, so batched seeds share a sort key to the microsecond, the list falls back to the `, id` tiebreak (random UUID order) and `position()` answers **1 for all of them**. A builder batching for speed gets a red on A3 whose most tempting fix is to weaken A3, which makes it vacuous.

### The tests, and the mutation each one MUST survive

| Test | Mechanism | **MUTATION that must turn it red** |
|---|---|---|
| `test_two_take_nexts_get_two_different_customers` (A6) | the subquery's **row lock + `status` qual** — **not** `SKIP LOCKED` | Drop `AND status = 'waiting'` from the **SUBQUERY** → the loser's EvalPlanQual re-check passes on the updated tuple and both end on one ticket |
| **`test_a_take_next_does_not_wait_behind_a_locked_ticket`** | `skip_locked=True` | Seed **exactly one** waiting ticket. A takes it and holds its transaction open (`Event` + `HOLD_SECONDS`); B's take-next must raise `QueueEmptyError` **promptly** — assert the exception **and** an elapsed bound well under `HOLD_SECONDS`. Remove `skip_locked=True` → B blocks for the full hold and *still* raises `QueueEmptyError`, so **only the timing assertion reds**, which is exactly why it cannot be dropped (Decision 22) |
| **`test_a_take_next_that_loses_the_room_leaves_the_ticket_waiting`** (A8) — **THE FEATURE'S HEADLINE TEST** | **Every refusal RAISES out of `tenant_session`; nothing `return`s after the ticket UPDATE** | **Give the `except` branch F36's idempotence RETURN** (`active_for` hit → `return await self._room_read(...)`) **inside the `async with`**, with the conflicting assignment held by the **SAME staffer as A's target** → 200, commit, ticket stranded `in_service` with no assignment: all four assertions red. ⚠ **The spec's first-draft mutation (savepoint + `try` inside) comes back GREEN** — `db/tenant.py:25` rolls back on a propagating exception with or without a savepoint — and is recorded in the code as *a mutation predicted to bite that does not* |
| ″ (A8, second mutation) | the audit call is inside the transaction | **Move the ticket claim and `_audit.record` into their own `tenant_session` that commits before the INSERT is attempted** → the ticket and the audit row survive the failure; assertions (2), (3) and (4) red. ⚠ The obvious mutation («move `_audit.record` outside the `async with`») is **unreachable** on the losing path — the exception is raised at the INSERT, so nothing after the block runs and zero rows are written either way |
| **`test_a_take_next_into_a_room_the_caller_already_holds_is_refused`** (A8b) | step 2b **and** the helper's missing idempotence branch, at once | Delete step 2b **and** add the idempotence branch → **200**, and the head of the queue is consumed. With both present: 409 `ROOM_OCCUPIED` naming her, `status == 'waiting'`, `position == 1`, `requeued_at` null, **zero audit rows** |
| `test_two_distinct_staffers_push_assigning_one_ticket_to_two_distinct_rooms_produce_one_assignment` (A10) | `AND status = 'waiting'` in the conditional UPDATE | Drop that conjunct → both succeed and two assignments carry one ticket. ⚠ **BOTH "distinct"s in the name are load-bearing**: same room and F36's room index blocks the second, same staffer and the staff index does — either way the mutation goes green and the shipped indexes pass the test for the wrong reason |
| **`test_a_concurrent_second_first_skip_is_refused_rather_than_removing_her`** (A15) | `AND skip_count = :seen_skip_count` | Drop the conjunct → B's EvalPlanQual re-check passes on A's updated row, B's `CASE` reads `skip_count = 1`, and **she is removed with neither client ever showing the confirm**: the status, count and audit assertions red |
| `test_two_deliberate_skips_leave_skip_count_at_two` (A15b) | `skip_count = skip_count + 1` in SQL | Replace with a Python read-modify-write → the lost update lands and the count is 1 |
| `test_the_second_skip_removes_her` (A14) | the `CASE` reading the pre-update value | `skip_count + 1 >= 2` → `skip_count >= 2` → she is never removed |
| `test_a_skip_clears_the_call` (A13) | `called_at = NULL` in the SET list | Drop it → she keeps «נקראה» at the **back** of the queue and F59's public board highlights her there indefinitely |
| `test_a_second_call_keeps_the_first_timestamp` (A17) | `called_at IS NULL` in the predicate | Drop it → the timestamp moves and an audit row is written |
| `test_a_call_leaves_the_status_waiting` (A16) | `status` absent from the SET list | Add `status='in_service'` → the row drops off F59's board the instant it is called, which is the opposite of the feature. **The one contract F59 recorded because it cannot enforce it** |
| `test_a_release_and_its_ticket_close_are_one_transaction` (A11) | both statements inside one `tenant_session` | Open a second `tenant_session` for the close → an injected failure between them leaves a free room and an `in_service` ticket |
| `test_the_waitlist_order_agrees_with_the_position_count` (A3) | `_live_waiting()` / `_sort_key()` **called**, not copied | Inline the four predicates and drop `queue_day` (or `deleted_at IS NULL`) → the two disagree. **Seeds are one-per-`tenant_session`.** ⚠ **Seed the noise the way F59 had to**: done / in_service / soft-deleted / yesterday rows, all **earlier** than every real row, so a one-sided widening shifts a position. F59's shipped note records that an all-waiting seed made this exact test blind |
| **`test_the_waitlist_and_position_disagree_on_a_deliberate_tie`** (A3b) | the documented residual | Two tickets seeded in **one** transaction: the list renders two distinct positions and `position()` answers one shared count. Pinned as a **fact**, not left in prose |
| `test_the_duplicate_flag_is_keyed_on_the_phone` (A19) | the grouping key | Group on `name` → the same-name-different-phone case reds |
| **`test_the_duplicate_flag_sees_an_in_service_twin`** (A19) | D2's fifth statement | Delete the in-service phone projection → the waiting ticket whose twin is already in a room renders **un-flagged**, which is the case D9 calls the most valuable thing on this panel to remove |
| `test_a_dispatched_walk_in_names_the_tile` / `test_a_soft_deleted_ticket_renders_an_anonymous_visit` (A20) | D10's fifth join and its `deleted_at` conjunct | Drop the join → every dispatched walk-in is anonymous. Drop the conjunct → a swept ticket keeps naming the tile |
| **`test_tenant_b_reaches_none_of_tenant_a_s_tickets`** | RLS + the explicit `tenant_id` predicates | Tenant B's take-next on A's day answers `QUEUE_EMPTY`; B's assign / call / skip / remove against A's ticket id each answer **404 indistinguishable from missing**; B's payload never joins A's rows |

⚠ **There is no separate `test_queue_dispatch_isolation.py`, and that is a decision rather than an omission.** F58 adds **no table**: `queue_tickets` is covered by F33's `test_queue_isolation.py` and `fitting_room_assignments` by F36's `test_fitting_rooms_isolation.py`, both connected as the app role. What is genuinely new is one join and five writers, and the last row above probes exactly those from tenant B. **Run those cases against the `app_role_url` fixture, never `migrated_db`** — the container superuser bypasses RLS and every assertion would pass vacuously. **Perform the vacuity mutation once** (swap the fixture to `migrated_db`, confirm the probes go green, restore) — that is the proof the block measures RLS and not nothing.

⚠ **EVERY ONE OF THESE MUTATIONS MUST BE RUN, NOT REASONED ABOUT.** F34, F57, F36 and F59 each found a real vacuous test this way, and F59's was the single test whose entire job was catching a divergence. **A test whose named mechanism can be removed with the suite still green is VACUOUS and must be rewritten**, not shipped with a note. Where a mutation was predicted to bite and does not, **say so in the code beside the mechanism** — that is F36's rule and this feature has two such rows already.

- **Done when**: `bash "<scratchpad>/run-db-tests.sh"` green; **every mutation in the table performed and restored**, each result recorded in the run report; the RLS vacuity mutation performed and restored. `make lint` clean. `git show --stat`.
- **Commit**: `test(queue): the forced-interleave suite for take-next, push-assign, skip, call and the duplicate flag`

---

# Part II — the frontend

> **Capture the qa-greps baseline BEFORE Task 9** and diff it after every frontend task:
> ```
> make qa-greps > "<scratchpad>/qa-greps-baseline.txt" 2>&1
> ```
> The ten `check` calls read `apps/storefront/src` only, but the trailing **date-reads review block** (`qa-greps.sh:60-70`) reads `apps/manage/src` and `apps/storefront/src`. **F58 renders a wait time and touches a storefront route** — it is the feature most likely to reach for a formatter, and it must not: `elapsedMinutes` is arithmetic on two ISO instants and involves no timezone at all.

## Task 9 — Wire types, five API methods, the `waitlist.*` deck and **its five i18n test edits** (D16 / DC-1, DC-3, DC-5)
`frontend/apps/manage/src/api.ts`, `…/i18n/he.ts`, `…/i18n/ar.ts`, `…/__tests__/api.test.ts`, `…/__tests__/i18n.test.ts`

### The failing tests first

**`api.test.ts`** — each of the five methods hits its path with the body verbatim (**no case conversion — this app speaks the backend's snake_case**); a 409 with `details` produces an `ApiError` **carrying** them; a 409 **without** produces one whose `details` is `undefined`, never `null`. `ApiError`, `extractError` and `errorMessage` are **unchanged** — F36 already typed `details` as `Record<string, string> | undefined` (`api.ts:22`).

**`i18n.test.ts` — FIVE edits (DC-5), and edits 3, 4 and 5 are the ones no enumerated list in either document asks for:**

1. **`HE_F58` must be FOLDED INTO `HE`, not merely declared.** The file says so about itself at `:33-37`: *"without this the resolve check, BOTH register guards and the `ar` parity guard silently skip every key."* On this feature the fold is load-bearing **twice**, because **deck F-2's send-ban catch only fires through it**.

   ```ts
   // No `nav.` term, and that is an assertion rather than an omission — the queue
   // is content of the floor, not a thirteenth console section, so F58 adds no
   // nav row. The three `rooms.*` keys are likewise absent: the namespace names
   // the surface, not the feature that added the key (:40-42).
   const HE_F58 = entries(he.translation, (key) => key.startsWith("waitlist."));
   const HE = [...HE_F15, ...HE_F51, ...HE_F52, ...HE_F17, ...HE_F34,
               ...HE_F57, ...HE_F53, ...HE_F33, ...HE_F36, ...HE_F58];
   ```
2. **`HE_F36`'s floor `>= 70` → `>= 76`** (`:424`, C14 — 71 today plus five), and **`:461`'s 2.5.3 array gains `"takeNext"`**, which puts the tile's new accessible name under a **shipped** guard instead of a parallel one.
3. **An `HE_F58`-scoped `ar[key] === he[key]` test.** The shipped one (`:580-592`) is scoped to `HE_F36` **by name**, so 37 hand-transcribed strings would ship with only a **presence** check (`:575-578`) — which passes on an English string, a `TODO`, or a different Hebrew wording, with no he/ar parity guard anywhere in this repo (F15's Risk 5).
4. **An `HE_F58`-scoped digit guard**, mirroring `:445-455`. Every number on this panel is an interpolation, so no exemption is needed.
5. **DC-1 — an `HE_F58`-scoped WCAG 2.5.3 assertion**, the `:456-468` shape:
   ```ts
   for (const name of ["call", "assign", "skip", "remove"]) {
     expect(i18n.t(`waitlist.${name}Aria`, { name: "נועה בר" })).toMatch(
       new RegExp(`^${i18n.t(`waitlist.${name}`)}`),
     );
   }
   ```
   `i18n.test.ts` carries **four** such loops already (`:253`, `:311`, `:362`, `:456`), one per feature that ever added an `*Aria`. Four prior features, no exceptions — and this is the criterion that is *legally binding*.

⚠ **Do not "helpfully" renumber anything else in that file.** Two `it(` blocks both claim *"resolves the eleventh nav item"*. It is a shipped inconsistency, it is not F58's, and touching it puts an unrelated edit on the diff of the PR that clears two deployment gates.

### The code

- `api.ts` — `WaitlistEntry`, `Waitlist`, `DispatchResult`, `TakeNextRequest`, `AssignRequest`, **`SkipRequest`** (`{ seen_skip_count: number }`); `FloorResponse` gains `waitlist: Waitlist`; a `queuePath(ticketId)` helper beside the shipped `roomPath`/`assignmentPath`; and `takeNext`, `assignFromQueue`, `callQueueTicket`, `skipQueueTicket`, `removeQueueTicket`.
- `i18n/he.ts` + `i18n/ar.ts` — the **37 `waitlist.*`** keys and **five `rooms.*`** keys, flat dotted, appended as a per-feature block, **transcribed from `copy.md`, which is canonical** — never from spec D16's table, which the deck supersedes with fourteen corrections. `ar` values are **the approved Hebrew standing in untranslated and never empty strings**: i18next's `returnEmptyString` default renders `""` rather than falling back.
  - **DC-3 — two of the five `rooms.*` keys are new here and their reason is C13**: `rooms.error.staffOccupiedSelf` «את כבר בחדר אחר: {{room}}.» and `rooms.error.staffOccupiedSelfUnknown` «את כבר בחדר אחר.», rendered on the **dispatch** targets only. The shipped third-person pair (`he.ts:929-930`) is **untouched** — its literal is asserted in `RoomsPanel.test.tsx:604`/`:616`, `RoomHandoverDialog.test.tsx:238` and `i18n.test.ts:501-513`, so editing it reds four shipped assertions and breaks this feature's acceptance gate.
  - **F-2, the deck's blocking correction**: `waitlist.calledCue` is «**הקריאה נרשמה.**» and **never** «נשלחה קריאה.» — «נשלחה» contains «נשלח» and `:560` filters every value in `HE` for `/נשלח|תישלח|בדרך/`. It is also **false**: `call` stamps a timestamp and **F58 sends nothing to anybody**.
  - **F-3, corrected as a class**: every `*Aria` is `<visible label> — {{value}}`. And **no string places a Hebrew preposition, article or agreeing verb immediately against `{{room}}`** — «לחדר {{room}}» renders «לחדר חדר 2» against the spec's own example labels.
  - **F-4, reuse before invention**: F36's two 409 sentences and both `*Unknown` twins are **reused unchanged**, not re-keyed. Four fewer keys, zero duplicates.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| the `HE_F58` fold | declare the constant without adding it to `HE` | put «נשלחה» into one value and confirm the send-ban goes **GREEN** without the fold and **RED** with it. ⚠ **Run this one — it is the whole of F-2 and F-12** |
| the `waitlist.*` digit guard | delete it, then put a literal `5` in a value | the guard must go **RED** |
| `ar[key] === he[key]` | delete it, then change one `ar` value to a different Hebrew wording | the presence guard stays **green** and the equality guard goes **RED** |
| **DC-1's 2.5.3 loop** | delete it, then restore D16's «הסרת {{name}} מהתור» | the loop must go **RED** on the word-form mismatch — and confirm nothing else does, which is why the guard is needed |
| `HE_F36`'s new floor | leave it at `>= 70` | delete three `rooms.*` keys and confirm the floor **does not** notice. Restore both |

- **Done when**: `make fe-test` + `make fe-build` green; `pnpm -r lint && pnpm -r typecheck` clean; `make qa-greps` byte-identical to the baseline; every mutation performed and restored. `git show --stat`.
- **Commit**: `feat(manage): the waitlist wire types, its five API methods and the copy deck with its five i18n guards`

## Task 10 — `WaitlistPanel` (D15, D17, D18 / DC-6, DC-7, DC-8, DC-9)
`frontend/apps/manage/src/components/WaitlistPanel.tsx` (**✚**), `…/__tests__/WaitlistPanel.test.tsx` (**✚**)

**A CHILD of `FloorPanel`, exactly as `RoomsPanel` is** (`RoomsPanel.tsx:15-31`): **no `usePoll` instance, no timer, no pause control, no `role="status"` of its own.** Props: `waitlist`, `rooms`, `serverNow`, `fetchCount`, `selfId`, `role`, `paused`, `mutate`, `onWaitlist`, `onRooms`, `onCue`. **`onWaitlist` is an UPDATER, never a finished list** (`applyRooms`'s shape and its review history): two rows can be in flight at once, and a handler rebuilding the list from the prop it closed over erases the other handler's patch.

### The failing tests first — all sixteen states, and the six focus moves each with its deletion mutation

**Render** — position in a `<bdi dir="ltr" className="… tabular-nums">`, name in a **bare `<bdi>`** at `font-semibold` (never `dir="ltr"` — forcing LTR on a Hebrew name reverses its words), the meta line `{visitKey} · {waitLine}`, **at most one `Badge`** («נקראה», `warning`), the duplicate sentence and the skip line. **No truncation and no ellipsis on a person's name, ever** — this is the panel where two abbreviated «נועה»s decide who gets removed.

⚠ **The wait line calls `elapsedMinutes(serverNow, entry.arrived_at)` and selects its own two keys — NEVER `elapsedLine`**, which hard-codes `rooms.elapsedJustNow` (`:34`) and `rooms.elapsed` (`:36`) and would render the ROOM's «כבר 42 דק'» about a woman who has not been in a room, leaving `waitlist.waiting` and `waitlist.waitingJustNow` **dead, green and unused** — `i18n.test.ts` counts entries and never checks that a key is reached. Three lines, no new mechanism, **no edit to a shipped `lib/` helper with two shipped callers**.

**Which control EXISTS is the rendered form of the authorization axes.** For the three floor roles «דלגי» and «הסרה» are **ABSENT** — no disabled button, no lock glyph, no «אין לך הרשאה» line, no tooltip (`RoomsPanel.tsx:26-31`). A **403 is TERMINAL for the whole floor screen**, and for those three roles that is the entire product going dark, so a rendered control reaching a route the server will refuse blanks a seamstress's only screen.

**DC-9 — «הסרה» is `Button variant="secondary" size="md"`**, taking the shipped storefront precedent (`ManageBookingPage.tsx:401`) rather than going one step below it. «קראי» and «דלגי» stay `ghost`; «שבצי לחדר» is the row's other `secondary`. At 375 the wrapped four-button row then distinguishes the one irreversible control by weight rather than by reading order. The argument against a permanently **red** trigger is unchanged.

**DC-8 — the duplicate line is MUTED** (`text-sm text-ink-muted`), like `skippedOnce` and for the same stated reason. **On a row, `--color-warning-text` means "this is the answer to what you just pressed"** — and the row alert is the only thing that carries it. Named test: on a called + duplicate + refused row, exactly one element carries the notice register.

**The three inline reveals — no `<dialog>` anywhere** (Decision 21, deck P-4): the assign room `Select`, the skip confirm and the remove confirm, all inside the row's own `<li>`, all covered by MOVES 3, 4 and 5 as they stand. **One reveal on the whole panel at a time.**

**DC-6 — the remove confirm's second line renders only when `entry.duplicate`**, and its corrected value is true in both duplicate cases: the twin may be another waiting row **or** an `in_service` ticket that appears nowhere on this panel.

**Mutations and refusals** — every verb patches from the **server's response**, never optimistically; a double-tap fires **one** request; the code→sentence map covers 404 + its paused twin, `QUEUE_TICKET_NOT_WAITING` (three keys: the `in_service` sentence, the closed sentence, and the `details`-less twin), `QUEUE_TICKET_CHANGED` + its paused twin, and — for push-assign — **F36's `ROOM_OCCUPIED` pair reused unchanged** plus **DC-3's `staffOccupiedSelf` pair**. **Nothing here is red**: 409 and 404 are both the notice register (`manage-restyle.md`'s three-register split), and the only `--color-danger` in this feature is the remove confirm's button.

**DC-7 — a successful push-assign lands focus on the panel `h3` (MOVE 3), because the row is gone.** Take-next lands on the tile's new primary control (§3.2) because the **tile** survives and flips state. Both land on the surface that survives the act. **State it, assert it, and do not let it fall out of MOVE 3 undocumented.**

**A29** — a DOM query over a populated fixture asserting **no element's `href` or `to` contains an entry's `id`**. Not a grep: a grep passes when the link is built by string concatenation.

**The six focus moves, each with a named non-vacuous mutation:**

| # | Move | Destination | Mutation |
|---|---|---|---|
| 1 | a refused verb (409, 404, outage) | the **row's** `role="alert" tabIndex={-1}` — keyed on the error state, **not raised in the handler** (the alert node does not exist when `setRowError` runs) | delete the `[rowError]` effect |
| 2 | a verb that succeeds and **leaves the row in place** — call, a first skip's increment | the row's current primary control, via a `Map` keyed by **entry id**, **guarded on `document.activeElement === document.body`** | delete the restore effect |
| 3 | a row that **leaves the list, OR leaves its place**, while holding focus | the panel `h3` | delete the departing-row check — **and run the deletion THREE times: a removal, a successful first skip (deck F-8: the row stays mounted and TRAVELS to position 40), and with a reveal open** |
| 4 | a reveal is dismissed — by her, **or because a tick removed what it was for** (deck F-9: the last free room vanishes under an open assign reveal) | back to its trigger; `isConnected` then the `h3` (`StaffSection.tsx:80-92`) | delete the `isConnected` fallback → focus lands on a detached node and silently does nothing |
| 5 | a reveal opens | onto the **question** (assign: onto the room `Select`) | delete the open-capture |
| 6 | a tick **clears a focused alert** | back to that row's control | delete the render-time capture — ~5s after the refusal, with **no user action**, «הרשימה תתוקן בעדכון הבא» is kept by the tick and focus must not fall to `<body>` with it |

⚠ **jsdom is the trap and it has already produced one shipped vacuous test.** `Button` is `disabled={disabled || loading}` (`Button.tsx:57`) and **every verb on this panel is that shape**, but **jsdom does not blur a disabled element**, so `activeElement` never became `<body>`, F57's guard never passed, and its whole restore effect could be deleted with the suite green. **A test for MOVE 2 must explicitly blur the tapped control before the promise resolves.** `known_flaky` also names a jsdom focus race in `ManageBookingPage.test.tsx` — the component these reveals copy — and the rule travels with it: **fix the wait, never raise the timeout.**

**Both render-time captures are copied from `RoomsPanel.tsx:167-192`**, and the reason is not style: by the time an effect runs the departing row is gone, `document.activeElement` has already dropped to `<body>`, and the question cannot be asked any more.

**The announced region** — `WaitlistPanel` writes into `FloorPanel`'s one cue via `onCue`, **only on a user-initiated outcome**, and **not one cue names a customer** (`RoomsPanel.tsx:464-468`: *"the region is PERSISTENT — nothing clears it on a timer"*). «נועה הוסרה מהתור.» would sit in a five-role screen's DOM after her row has left the payload and after she has left the shop, so the cue would become the only place her name survives. **The cues name the ACT**; only `dispatchedCue` interpolates, and it interpolates a **room label**. Test it over **several consecutive ticks with the cue already populated** — assigning a byte-identical string still produces a real `childList` mutation inside `role="status"` (`FloorPanel.tsx:236-243`), and a single-tick assertion passes against the broken version whenever the cue starts empty.

**44×44 on every target** — `size="md"` → `min-h-11`, asserted as a **class** because jsdom has no layout engine and a measurement would be vacuous (`BoardSection.test.tsx:507-512` writes the trap out). The assign `Select` carries `className="min-h-11"` at the call site (deck F-10: `Select` declares no `min-h-*`, so `cn()`'s plain join has no fight to lose).

**An axe pass, explicitly not sufficient** — axe cannot see a focus move that never happened (**four shipped instances in this repo**), and axe has **no rule for SC 2.2.2**.

- **Done when**: `make fe-test` + `make fe-build` green; axe **zero**; **all six focus mutations performed and restored, MOVE 3's three times**; `make qa-greps` byte-identical. `git show --stat`.
- **Commit**: `feat(manage): the waitlist panel, its four verbs, three inline reveals and six focus moves`

## Task 11 — `FloorPanel`'s plumbing and `RoomsPanel`'s take-next control (D15, D17 / DC-2, DC-3, DC-4)
`frontend/apps/manage/src/components/FloorPanel.tsx`, `…/components/RoomsPanel.tsx`, `…/__tests__/FloorPanel.test.tsx`, `…/__tests__/RoomsPanel.test.tsx`

**Two files, one task, and that is deliberate**: `RoomsPanel` gains two **required** props that only `FloorPanel` can pass, so splitting them reds `pnpm -r typecheck` on an intermediate commit. Every commit on this branch is expected to be green.

### The failing tests first

**Existing blocks in BOTH suites pass UNEDITED.** That is the acceptance rule and the instrument that tells a faithful addition from a subtly different one. New `it(` blocks are added freely; **an edit to an existing expectation means the change is wrong.**

**`FloorPanel.test.tsx`** — `waitlist` state beside `rooms`; `applyWaitlist` is an **updater** with `applyRooms`'s shape (`:325-328`); `setWaitlist(result.waitlist)` inside `load`; `<WaitlistPanel …/>` mounted **below** `<RoomsPanel/>` (`:609`) and **above** the staff `Card` (`:622`), receiving `mutate`, `onWaitlist`, `onRooms`, `onCue`, `serverNow`, `fetchCount`, `paused`, `selfId`, `role`. `mutate`, `load`, `tick`, the poll and all six shipped focus effects are **unchanged**. One new test: a floor tick **still repaints only the floor**.

**`RoomsPanel.test.tsx`** — ⚠ **take-next's control lives on the TILE, so its tests live here and not in `WaitlistPanel.test.tsx`**:
- the «קחי את הבאה» presence rule: **free + active tile only, and only while `waitlistCount > 0`**. An empty queue **removes the control** rather than refusing the tap, so `QUEUE_EMPTY` fires only on a stale tile.
- **A31b** — a 409 `QUEUE_EMPTY` renders «אין ממתינות בתור.» in the tile alert, in the **non-outage** register, with focus moved into it (MOVE 1).
- **DC-3** — a 409 `STAFF_OCCUPIED` on **take-next** renders the **self** sentence; the shipped third-person one still renders on **handover** (that assertion is `RoomHandoverDialog.test.tsx:238`, unedited).
- **DC-2 (a)** — with a non-empty queue, the tile's `controlRefs` slot is **«קחי את הבאה»**: after a refused take-next, the next tick clears the alert and MOVE 6 lands focus on the control she pressed, not on «תפיסת החדר». **Mutation: remove the `waitlistCount === 0` guard from the claim button's ref callback** → the claim button's callback runs last, wins the slot, and focus lands on the wrong control.
- **DC-2 (b)** — pressing «קחי את הבאה» spins **only** it; both controls are `disabled`. **Mutation: give both `loading={busy}`** → two spinners, and the assertion reds.

### The code

**`RoomsPanel` gains exactly this and nothing else:**
- two props — `waitlistCount: number` and `onDispatch: (result: DispatchResult) => void` — documented in `RoomsPanelProps` (`:84-118`) in the shipped style.
- one `Button` in the tile's action row, **first**, `variant="secondary" size="md" fullWidthMobile={false}`, `aria-label={t("rooms.takeNextAria", { room })}`, riding the shipped `act()` with a new `"queue"` target discriminator.
- **DC-2's two rules** — the guarded ref callback and `pendingControl`.
- **one new branch in `describe()`** for 409 `QUEUE_EMPTY` → `{ text: t("rooms.error.QUEUE_EMPTY"), value: null, outage: false }`, plus DC-3's `target === "queue"` self-form for `STAFF_OCCUPIED`. Without the first, `QUEUE_EMPTY` takes the fall-through at `:387` and renders «לא הצלחנו לטעון את רשימת הצוות כרגע.» in the muted **outage** register to a manager whose queue is simply empty — *the exact failure D3 buys the error code to avoid, delivered in the wrong colour on top.*
- **DC-4 — the shipped comment at `:834-837` is REWRITTEN**, not left standing: *"ONE `secondary` per tile and it is the act that ENDS the tile's current state"* becomes the restated rule — **at most one `secondary` per act-type, never `primary` anywhere on this screen, never more than two `secondary`s on one region; order carries the hierarchy** — and it names why a free tile with a queue has two acts that end its state, serving two different populations. F36's PR spent a load-bearing finding on three shipped comments that stated a false fact as the rationale for a live decision; this is the fourth.

**`FloorPanel`** gains `waitlist` state, `applyWaitlist`, one line in `load`, and the mount. **`holdRef`'s comment (`:83-88`) gains the waitlist case**: a remote skip moves a row from position 1 to position 12, so every row between them shifts up — directly under a finger travelling toward «הסרה» on the row below.

**`lib/usePoll.ts` gets a ZERO-LINE DIFF.** Not one line. Four features are queued to import it.

- **Done when**: `make fe-test` + `make fe-build` green; **`git diff main -- frontend/apps/manage/src/lib/usePoll.ts` is EMPTY**; every shipped `FloorPanel.test.tsx` and `RoomsPanel.test.tsx` expectation passes **unedited**; both DC-2 mutations performed and restored; `make qa-greps` byte-identical. `git show --stat`.
- **Commit**: `feat(manage): the waitlist plumbing, the tile's take-next control and the comment it falsifies`

## Task 12 — `QueuePositionPage`'s state precedence (D14)
`frontend/apps/storefront/src/routes/QueuePositionPage.tsx`, `…/__tests__/QueuePositionPage.test.tsx`

### The failing tests first

**A28, and a vitest case per arm, driven by a stubbed API client** — F33's D10 precedent: *"the `done` fixture is seeded by the stubbed API client, which is the only way it can be produced"*. **Nothing in the product can drive it, and no backend or e2e assertion may try.**

- `closed` → «הביקור הזה הסתיים.» and the loop stops. **This is F33's third deployment-gate consequence** and until this PR the arm is unreachable, because nothing writes `done` or `removed`.
- **`in_service` AND `called_at` set** → «התור שלך התחיל», **not** «אפשר לגשת לדלפק».
- `called` and still `waiting` → «אפשר לגשת לדלפק».
- `waiting` with a position → the number.

### The code

**Three lines, no string added and no string removed**: derive `const inService = ticket !== null && ticket.status === "in_service"` beside `closed` (`:266`) and `called` (`:267`), and order the render arms **`closed → inService → called → position`** (`:319`, `:323`, `:329`, `:338`).

F58 makes `called_at` and `status = 'in_service'` co-occur for the first time — a woman who was called and then taken — and in that state the shipped order renders «אפשר לגשת לדלפק», telling a woman standing in a fitting room to approach the counter, and making «התור שלך התחיל» (`he.ts:446`) unreachable on the only path in the product that produces it.

*Declined the alternative* — having take-next clear `called_at` — because it would erase the record that she was summoned, on the one column F59 reads, for a rendering problem that belongs to the renderer (Decision 15).

### Mutation-check (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| the precedence reorder | restore the shipped order | the `in_service`-after-`called` case **RED** and **nothing else** — confirm both halves |

- **Done when**: `make fe-test` + `make fe-build` green; the mutation performed and restored; `make qa-greps` byte-identical. `git show --stat`.
- **Commit**: `fix(storefront): the position page's four-arm precedence, now that in-service and called co-occur`

---

# Part III — the harness

## Task 13 — The reusable Playwright `/manage/**` interception harness (D19)
`frontend/e2e/fixtures/manage.ts` (**✚**), `frontend/e2e/manage.spec.ts` (**✚**)

**The console has FOUR e2e tests and every one of them is the LOGIN SCREEN.** `frontend/e2e/` holds 65 tests (`a11y.spec.ts` 10, `storefront.spec.ts` 55) and four of them reach `/manage` — the shared viewport-meta loop, two `manage:` login-screen tests (one already a zero-axe A/AA pass) and the print-sheet test, whose own comment names the gap: *"The login screen is the console screen this suite can reach unauthenticated."* **Nothing gets past `App.tsx`'s `api.me()` bootstrap without a stubbed identity. That is the gap: no authenticated console coverage of any kind, on twelve shipped sections.**

**⚠ WRITE THIS AS INFRASTRUCTURE, NOT AS THIS FEATURE'S SCAFFOLD.** F37's overlay, F41, F42 and every later console feature inherit it, so its shape matters more than F58's use of it. The `fixtures/` module is the deliverable; `manage.spec.ts` is its first consumer.

### `frontend/e2e/fixtures/manage.ts`

```ts
export const MANAGE = "http://localhost:4174/manage/";
export function staff(overrides?): Staff              // the identity /manage/auth/me answers
export function floorPayload(overrides?): FloorResponse
export async function installManageApi(page, options): Promise<Recorder>
```

**How it authenticates: it does not.** `App.tsx` bootstraps on `api.me()` and renders `<LoginForm/>` on a rejection, so **fulfilling `GET /manage/auth/me` with a 200 `Staff` body is the whole of "signed in"** — no cookie, no login POST, no session table.

**The default identity is `reception`, and that is deliberate rather than arbitrary.** `NAV`'s `floor` row is `FLOOR_ONLY` (`App.tsx:49`, `:106`), so a reception staffer's only reachable section **is** the floor, `activeKey` (`:181`) lands there with no navigation, and **no other panel ever mounts** — three stubbed GETs and not one stray request. A second identity, `shift_manager`, exercises the two `ELEVATED` controls and reaches the floor through the `board` section, which is why the harness also stubs `/manage/dashboard**` and `/manage/bookings**`.

**⚠ THE TRAP, AND THE HARNESS EXISTS PARTLY TO MAKE IT UN-STEPPABLE-ON: `page.route("**/manage/**")` ALSO MATCHES THE APP ITSELF.** `apps/manage` builds with `base: "/manage/"` (`vite.config.ts:23`), so `/manage/index.html`, `/manage/assets/*.js` and `/manage/favicon.svg` all live under that prefix, and **one broad glob serves a blank page with no error anywhere.** Register **narrow globs per API family** — `**/manage/auth/**`, `**/manage/floor`, `**/manage/floor/**`, `**/manage/dashboard**`, `**/manage/bookings**` — so an asset is never matched at all. The same reasoning `vite.config.ts:13-20` already carries for its fourteen-name alternation. **A31** asserts it: the app boots and the floor renders.

**What it stubs**, copying `storefront.spec.ts:409-450`'s idiom — a per-path **queue** of responses plus a **recorder**, so a test asserts *what the app sent* and not only what it rendered:

| Path | Default |
|---|---|
| `GET /manage/auth/me` | `staff()` |
| `GET /manage/floor` | `floorPayload()` — staff, rooms, **waitlist**, `server_now` |
| `GET /manage/floor/clients`, `GET /manage/floor/dresses` | empty lists, `truncated: false` |
| every POST/PATCH/DELETE under `/manage/floor/**` | the next queued response for that path |
| anything else matched | a house-shape 404 `{"error": {"code": "NOT_FOUND", …}}` |

**The last row is the design.** An unstubbed API call must fail **loudly** — as a rendered Hebrew error the test can see — rather than reaching `vite preview`'s proxy to a port with nothing on it, where the failure reads as a flake.

### The journeys — seven, plus one axe pass

1. reception signs in and the floor renders with a populated waitlist;
2. «קחי את הבאה» on a free tile dispatches the first entry — the tile fills, the row leaves, and the cue names **the room** (never the customer);
3. take-next answering 409 `ROOM_OCCUPIED` shows the Hebrew sentence in the **tile's** alert, **moves focus into it**, and leaves the row in place;
4. take-next answering 409 `QUEUE_EMPTY` shows «אין ממתינות בתור.» in the same alert, in the **non-outage** register;
5. a shift manager removes a duplicate through the two-step confirm;
6. a skip on `skip_count === 1` confirms first;
7. an unstubbed request surfaces as a rendered Hebrew error rather than a hang.

**A30 — zero axe A/AA violations on the floor screen with a populated waitlist: the console's first axe assertion BEHIND the login screen.**

⚠ **Journeys 2 and 3 are the ones a component test cannot stage**, and that is why the harness exists on this feature rather than a later one: **a real browser blurs a `disabled` control the instant a request starts, and jsdom does not.** That single difference made one of F57's shipped focus tests vacuous.

⚠ **Risk 6, stated in the module docstring so the harness is never trusted for what it cannot do:** it stubs the API, so **it proves the console and not the contract.** A backend change that renames a payload key passes every e2e test while breaking production; only `test_floor_api.py`'s set-equality assertions and the TypeScript types catch that. **It is a journey and a11y instrument.**

⚠ **`test_frontend_imports_are_tracked.py` is a live guard on this task**: `frontend/e2e/fixtures/` is a **new directory**, and a fixture module that exists on disk but not in the commit reds the backend job on a fresh clone. `git add frontend/e2e/fixtures/manage.ts` explicitly and confirm with `git show --stat`.

- **Done when**: `make e2e` green with **73 tests** (65 + 8); axe **zero** on the floor screen with content; `git ls-files frontend/e2e/fixtures/manage.ts` non-empty. `git show --stat`.
- **Commit**: `test(e2e): the reusable /manage interception harness and the floor's first authenticated journeys`

---

# Part IV — shipping

## Task 14 — Gates, the rebase and renumber, the two deployment gates, and the run report
No files, except **`.planning/LOOP-STATE.md`** (see below).

Run the full verification, perform the rebase and renumber, and carry forward:

- **⚠ CLEAR BOTH `deployment_gates` ENTRIES.** `LOOP-STATE.md:1587-1618` names F58 as `cleared_by` for **F33** and **F59**. **Discharging them is the point of this feature**, so the merge commit's `docs(planning)` update removes both entries and records, in one line each, what discharged them:
  - **F33** — (1) D2's waitlist is the first shipped surface that renders `queue_tickets`; (2) D8's remove verb plus D9's duplicate flag are the buyer Ruling 3 has been waiting for; (3) D5's release and D6's second skip write `done` and `removed`, so the position page's success terminal is reachable for the first time.
  - **F59** — D7's `call` stamps `called_at` and **leaves `status = 'waiting'`** (A16, and the one contract F59 recorded because it could not enforce it), and D3/D4/D6/D8 give the status column its four writers, so rows leave the board and **the five names stop freezing at 09:15**.
  - **⚠ F20's retention gate on F33 is NOT discharged and stays open** (`qr-walkin-queue.md` «Deployment ordering», row 2). F33 carried two preconditions; F58 clears one. **Do not delete that row.**
- **The migration number.** State the number the branch was **built** at, the number it **shipped** at, and the `alembic heads` output on `origin/main` that decided the second. Confirm `alembic heads` prints **one** head on the rebased branch and that `test_exactly_one_migration_head` is green in `make test` (**A32**).
- **Every mutation-check, by name, with its result.** Four in Task 1, seven in Task 2, four in Task 3, five in Task 4, four in Task 5, four in Task 6, four in Task 7, **eighteen in Task 8**, five in Task 9, **six focus moves (MOVE 3 three times) in Task 10**, two in Task 11, one in Task 12. **Say plainly which were RUN and which were reasoned about — the answer must be "all run".** Record the ones that came back **green** beside their mechanism in the code, as F36 did; this plan already predicts nine of them.
- **Risk 4, the one the reviewer owes the most time to.** The floor payload's name count went from **≤3 to ≤100**, it now also carries **≤100 position-page capabilities**, and the role gate did not move. D10's rewrite is honest about both. **F20 inherits it for the processing-activities entry and must record the capability disclosure as well as the names.**
- **Risk 1, narrowed but real.** D3's step 2b removes the common case; what remains is a winner that had not committed when 2b read, plus the wider case that the subquery SKIP-LOCKs past **any** row-locked ticket — including one a colleague is *calling* or *skipping*. One statement wide, visible on the panel (the skipped-past row is still at position 1), and strictly better than two staffers walking two brides to one curtain.
- **Risk 2** — a removed duplicate terminates a live device's position page. Mitigations now: the confirm names her, the duplicate line flags both rows, the survivor keeps her true arrival position, and **`confirmRemoveDuplicate` tells the manager the one consequence she can repair** (deck F-11, corrected by DC-6 to be true when the twin is already `in_service`).
- **Risk 5** — yesterday's unclosed tickets stay unclosed and unreachable; the panel is today-scoped. **F20's sweep owns it.**
- **Risk 6** — the harness stubs the API, so it proves the console and not the contract.
- **Deck findings F-1 … F-13 plus the new F-14** — each carries an owner and a trigger; carry them verbatim. **F-1 (renaming `floor.heading`) and F-10 (`Select`'s 43.6px) are DECLINED here with re-set triggers** — any PR already renaming a `nav.*` label or F37 for the first; any PR whose diff is already inside `packages/ui` for the second.
- **What F58 hands F37**: `_authorize` now has **five** call sites and F37's targeting will be tempted to write a sixth; the assignment id is stable across a handover; `queue_ticket_id` gives an alert a walk-in's identity for free.
- **The parked question, not reopened**: *should a booking and a queue ticket for the same woman be reconciled?* They are not. Both surfaces render her honestly and the manager reconciles by removing one; D10's `COALESCE` already resolves her to the `customers` name if she is dispatched on both.

No push, no PR from this task — the orchestrator owns review and shipping. **The checklist below is the precondition list it runs.**

---

## Shipping checklist — run in this order, top to bottom

1. **`git show --stat` on every commit** confirms the lowercase pathspecs landed. `git add Backend/…` silently skips modified tracked files.
2. **`git diff main -- backend/tests/conftest.py` is EMPTY.** The harness is shipped code — a non-empty diff means something was patched that should not have been.
3. **No lower-numbered migration is unmerged.** Check LOOP-STATE's `queue:` block and `gh pr list`. **F41 is the live one to watch** — it is building with a migration.
4. `git fetch origin && cd "…/Backend" && uv run python -m alembic heads` **on a checkout of `origin/main`**. Note the number.
5. **Renumber the migration to head + 1** — three edits: the filename, the `revision` literal, the `down_revision` literal. Amend the migration commit (it is the branch tip by Task 1's instruction).
6. Rebase onto `origin/main`. Re-run `alembic heads` **on the rebased branch** and confirm a **single** head. Run `make test` and confirm `test_exactly_one_migration_head` is green.
7. **`bash "<scratchpad>/run-db-tests.sh"` green on the rebased branch.**
8. Full local gate (below), all six targets green.
9. **`git diff main --stat` names none of**: `frontend/apps/manage/src/lib/usePoll.ts`, `…/src/App.tsx`, `…/src/__tests__/Nav.test.tsx`, `…/vite.config.ts`, `frontend/scripts/qa-greps.sh`, `frontend/packages/ui/**`, `backend/tests/conftest.py`, `backend/app/db/repositories/queue_tickets.py`'s `position()` body. **That list is A23 + D15 + deck F-1/F-10 mechanised.**
10. **`git diff main -- frontend/apps/manage/src/__tests__/FloorPanel.test.tsx` and `…/RoomsPanel.test.tsx` show ADDED blocks only** — no edit to an existing expectation. Same for `backend/tests/test_floor_service.py`'s release suite. That is Risk 10's acceptance condition, not a hope.
11. **`git ls-files frontend/e2e/fixtures/manage.ts` is non-empty** — `test_frontend_imports_are_tracked.py` reds on a fresh clone otherwise.
12. `make qa-greps` output **byte-identical to the pre-Task-9 baseline**.
13. Open the PR. The three gating jobs are `Backend (lint, types, tests)`, `Frontend (lint, types, build)`, `Frontend E2E (Playwright + axe)`.

---

## Verification — the full local gate sequence

```
make lint      # Backend: ruff check . && ruff format --check . && mypy app tests
               #   + Frontend: pnpm -r lint && pnpm -r typecheck
               #   + bash frontend/scripts/qa-greps.sh
make test      # Backend: pytest -m "not db" -q   (includes test_exactly_one_migration_head)
bash "<scratchpad>/run-db-tests.sh"
               # recreates f58_test on the local 16.14 cluster, exports
               # TEST_POSTGRES_SUPERUSER_URL, runs pytest -m db
               # ⚠ NO conftest patch and NO revert — the hatch is shipped
make fe-test   # Frontend: pnpm -r --if-present test
make fe-build  # Frontend: pnpm -r build
make e2e       # Frontend: pnpm -r build && playwright install --with-deps chromium && pnpm e2e
```

**Green looks like:**

- **`make lint`** — ruff clean, `ruff format --check` clean, **mypy zero errors over `app` and `tests`**, `pnpm -r lint` and `pnpm -r typecheck` clean across all four workspace packages, and `qa-greps.sh` **exit 0** printing **exactly the pre-Task-9 baseline**. A new `review` line from the date-reads block means a formatter arrived where arithmetic belongs — read it before changing code.
- **`make test`** — `test_floor_api.py` green with `FLOOR_ROUTES` at **eighteen**, `SPEC_ERROR_CODES` at **ten** and `WaitlistEntry`'s key set equal; `test_floor_service.py` green with the authorization matrix, all three refusal tables and the release suite's shipped blocks **unedited**; **`test_staff_role_gating.py` green with `FLOOR_OPEN` at twelve and the intersection classifier UNTOUCHED**; `test_spa_serving.py` green **unedited**; `test_frontend_imports_are_tracked.py` green; the single-head guard green; the `db`-marked modules **collected and deselected**.
  ⚠ **Two `test_config.py` failures are always false locally** — `Backend/.env` leaks `MEDIA_BUCKET`. CI is green. Do not chase them.
- **the local db suite** — the captured baseline **plus** F58's new cases in `test_migrations.py`, `test_queue_repositories.py`, `test_floor_db.py` and `test_queue_dispatch_db.py`, all green. The 9 `test_media_upload_s3.py` cases need MinIO and are excluded — **expected; F58 touches no S3.**
  ⚠ **`known_flaky` names `test_booking_owner_db.py::test_two_concurrent_reschedules_of_one_booking_never_self_collide`**, seen once locally during F59's build and never on CI. F58 touches nothing in booking reschedule. **If it reds, re-run it in isolation before believing it — and record the result either way.**
- **`make fe-test`** — `api.test.ts`, `i18n.test.ts`, `WaitlistPanel.test.tsx`, `FloorPanel.test.tsx` (**shipped blocks unedited**), `RoomsPanel.test.tsx` (**shipped blocks unedited**) and `QueuePositionPage.test.tsx` green; **axe zero on the waitlist panel**; every mutation performed and restored.
- **`make fe-build`** — both apps build; no unused-import or unused-variable TS error (`TS6133`).
- **`make e2e`** — **73 tests** (65 before), axe zero, including the console's first authenticated axe assertion.
- **CI additionally** — the same db suite against Testcontainers. ⚠ **A first CI red on a test bug here is budgeted**; check `continue-on-error` on the job before believing it.

---

## What a local run cannot prove

| Task | The local run proves | CI-only / not proven anywhere |
|---|---|---|
| 1 | the column shape, the four untouched guards, the round trip — **all of it, against real Postgres 16.14** | that the merge-result head is what the branch assumed. **A32 is the only gate line this feature can uniquely fail** |
| 2, 8 | every forced interleave, every EvalPlanQual re-check, the row locks, the `SKIP LOCKED` timing bound, and all eighteen mutations | the same, on CI's superuser / app-role split |
| 4, 5 | every branch of the refusal tables with no Postgres | — |
| 10, 11, 12 | jsdom focus behaviour, which **is not a browser** — a disabled element is not blurred, which is why every focus test blurs explicitly | a real browser's focus behaviour on `disabled`. **This is what Task 13 exists to prove**, and F58 is the first feature in the program where that gap closes rather than being recorded |
| 13 | the console's journeys and its first authenticated axe pass | **the contract.** The harness stubs the API, so a renamed payload key passes every e2e test while breaking production (Risk 6). Only `test_floor_api.py`'s set equalities and the TS types catch that |
| — | — | `test_media_upload_s3.py` (MinIO; F58 touches no S3) |

**Task 7 is the milestone**: all eighteen routes, all three new codes, both gates and the whole extended payload are exercised end to end with no Postgres.

---

## Task-by-task file manifest

| Task | New (**✚**) | Modified |
|---|---|---|
| 0 | — | `.planning/plans/floor-dispatch.md`, `.planning/specs/floor-dispatch.md`, `.planning/design/screens/floor-dispatch/design.md`, `.planning/design/screens/floor-dispatch/copy.md` |
| 1 | `backend/migrations/versions/00NN_floor_dispatch.py` | `backend/app/models/fitting_room_assignment.py`, `backend/tests/test_migrations.py` |
| 2 | — | `backend/app/db/repositories/queue_tickets.py`, `backend/tests/test_queue_repositories.py` |
| 3 | — | `backend/app/floor/schemas.py`, `backend/app/floor/validation.py`, `backend/app/models/constants.py`, `backend/app/main.py`, `backend/tests/test_floor_api.py` |
| 4 | — | `backend/app/floor/service.py`, `backend/tests/test_floor_service.py` |
| 5 | — | `backend/app/floor/service.py`, `backend/tests/test_floor_service.py` |
| 6 | — | `backend/app/floor/service.py`, `backend/app/db/repositories/fitting_rooms.py`, `backend/app/floor/router.py`, `backend/app/floor/schemas.py`, `backend/tests/test_floor_service.py` |
| 7 | — | `backend/app/floor/router.py`, `backend/tests/test_floor_api.py`, `backend/tests/test_staff_role_gating.py` |
| 8 | `backend/tests/test_queue_dispatch_db.py` | `backend/tests/test_floor_db.py` (the payload assertions) |
| 9 | — | `frontend/apps/manage/src/api.ts`, `…/i18n/he.ts`, `…/i18n/ar.ts`, `…/__tests__/api.test.ts`, `…/__tests__/i18n.test.ts` |
| 10 | `frontend/apps/manage/src/components/WaitlistPanel.tsx`, `…/__tests__/WaitlistPanel.test.tsx` | — |
| 11 | — | `frontend/apps/manage/src/components/FloorPanel.tsx`, `…/components/RoomsPanel.tsx`, `…/__tests__/FloorPanel.test.tsx`, `…/__tests__/RoomsPanel.test.tsx` |
| 12 | — | `frontend/apps/storefront/src/routes/QueuePositionPage.tsx`, `…/__tests__/QueuePositionPage.test.tsx` |
| 13 | `frontend/e2e/fixtures/manage.ts`, `frontend/e2e/manage.spec.ts` | — |
| 14 | — | `.planning/LOOP-STATE.md` (**both `deployment_gates` entries cleared**) |

**Never modified, and that is an assertion, not an accident:** `frontend/apps/manage/src/lib/usePoll.ts` (zero-line diff) · `…/src/lib/elapsed.ts` (D2 — `elapsedMinutes` is called, not extended) · `…/src/App.tsx` and `…/src/__tests__/Nav.test.tsx` (D15, deck F-1) · `…/vite.config.ts` (A23) · `backend/tests/test_spa_serving.py` (A23) · `backend/tests/conftest.py` · `frontend/scripts/qa-greps.sh` · `frontend/packages/ui/**` (deck F-10) · `backend/app/db/repositories/queue_tickets.py`'s `position()` **body** (the file is edited; that method is not) · `backend/app/queue/**` service and routers · `backend/tests/test_queue_isolation.py`, `test_queue_board_*.py` · `frontend/apps/storefront/src/routes/QueueBoardPage.tsx`.

---

## Testing plan → spec criteria

| Spec criterion | Where |
|---|---|
| **A1** — one nullable `queue_ticket_id`, no CHECK, no unique index, no FK | `test_migrations.py` (db) — the column shape **plus the three F36 counts/pins green with no edit** |
| **A2** — `waitlist.entries` in `COALESCE(requeued_at, created_at), id` order with `position == index + 1`, **one seed per `tenant_session`** | `test_floor_db.py` (db) |
| **A3** — the waitlist's predicate set is the **same function call** as `position()`'s | `test_queue_dispatch_db.py::test_the_waitlist_order_agrees_with_the_position_count` — **seeded with done / in_service / soft-deleted / yesterday noise**, F59's lesson |
| **A3b** — a deliberate tie renders two list positions and one shared `position()` | db |
| **A4** — no phone, no `marketing_opt_in_at`, no `queue_day` on the payload | `test_floor_api.py` (fast, recursive key/value scan) |
| **A5** — take-next claims the ticket `position()` calls 1 and inserts the assignment in one transaction | db |
| **A6** — two concurrent take-nexts get two **different** tickets | forced interleave, db |
| **A7** — an empty queue answers 409 `QUEUE_EMPTY` and writes nothing | db |
| **A8** — **a lost ROOM race leaves the ticket `waiting` at position 1, with no assignment and no audit row** | `test_a_take_next_that_loses_the_room_leaves_the_ticket_waiting` — **the feature's headline test, two named mutations, one of them a recorded false prediction** |
| **A8b** — take-next into a room the caller already holds is 409, never 200 | db — *the assertion that structurally forbids an idempotence branch* |
| **A8c** — an unrecognised unique violation **re-raises** (500) | fast (`test_floor_service.py`, injected `IntegrityError`) |
| **A9** — push-assign on a non-waiting ticket 409s; on a missing one, 404 | fast + db |
| **A10** — two concurrent push-assigns of one ticket produce **one** assignment | forced interleave, db — *both "distinct"s in the fixture are the test* |
| **A11** — release closes a linked ticket **in the same transaction**; `NULL` is byte-identical to F36 | db + **the shipped release suites green with no edit** |
| **A12** — a second release does not re-close and writes no audit row | db |
| **A13** — skip stamps `requeued_at`, increments, **clears `called_at`**, leaves her `waiting` | db |
| **A14** — the **second** skip writes `removed` | db |
| **A15** — **a concurrent second first-skip is REFUSED, not escalated** | forced interleave, db — *the review's third BLOCKER, mechanised* |
| **A15b** — two deliberate skips leave `skip_count == 2` | forced interleave, db |
| **A16** — call stamps `called_at` and **leaves `status = 'waiting'`** | db — **the F59 contract, and half of that deployment gate** |
| **A17** — a second call on an already-called `waiting` ticket is **200, first timestamp, no audit row** | db — D7's third branch, the one D4's table cannot supply |
| **A18** — remove writes `removed`; the row leaves and her page reaches its terminal | db + vitest |
| **A19** — `duplicate` true for two same-phone waiting, **true when the twin is `in_service`**, false for same-name-different-phone | db — *the in-service half is the one an earlier draft could not compute* |
| **A20** — a dispatched walk-in names the tile; a soft-deleted ticket renders anonymous | db |
| **A21** — skip and remove **403** for the three floor roles; take-next, assign and call **200** | `test_floor_api.py` + `test_staff_role_gating.py` |
| **A22** — the structural walker passes with `FLOOR_OPEN` **+3** and the classifier untouched | `test_staff_role_gating.py` |
| **A23** — the dev-proxy set equality holds with **no `vite.config.ts` edit** | `test_spa_serving.py` (unedited) + the deliberate prefix mutation in Task 7 |
| **A24** — each of the six focus moves lands where D18 says | `WaitlistPanel.test.tsx` — **one named test each, MOVE 3's mutation run three times** |
| **A25** — the empty state renders «אין ממתינות בתור» with no action | vitest |
| **A26** — a tick that drops the focused row moves focus to the panel heading | vitest (MOVE 3) |
| **A27** — skip's confirm only when `skip_count >= 1`; remove's always; both name her | vitest |
| **A28** — an `in_service` ticket that was called renders «התור שלך התחיל» | vitest (storefront), stubbed API client |
| **A29** — no element's `href`/`to` carries an entry's `id` | vitest — **a DOM query over a populated fixture, not a grep** |
| **A30** — zero axe A/AA on the floor screen with a populated waitlist | e2e — *the console's first behind the login screen* |
| **A31** — the harness intercepts no asset; the app boots and the floor renders | e2e |
| **A31b** — `QUEUE_EMPTY` renders in the **tile** alert, non-outage register, focus into it | `RoomsPanel.test.tsx` + e2e |
| **A32** — `alembic heads` returns exactly ONE head after the rebase | F19's shipped single-head guard, Task 14 step 6 |

---

## What could go wrong in review

Every item here is a **recorded ruling or a verified finding**. A reviewer who raises one should find the reasoning rather than file a finding.

1. **"LOOP-STATE says no new table, so why is there a migration?"** *"No new table"* is true and **is not the same promise as "no migration"**. F36's own DDL hands the column over in writing: *"F58 adds the column in its own migration alongside its writer."* One `ALTER TABLE`, one column, no index, no CHECK (Conflict 1, D1).
2. **"Take-next has no savepoint and `FloorService.claim` has one."** **D3a, and the difference is what the transaction has already written.** F36's claim needs the outer transaction alive to *read the occupant*, and nothing has been written yet. F58's take-next has already moved a customer to `in_service`, so it needs the opposite: **every refusal raises out of `tenant_session`, and nothing returns after the ticket UPDATE.** The occupant read moves to a second, short session, paid only on a refusal.
3. **"The spec's own first draft named a different mechanism here."** It did, and the correction is recorded: `db/tenant.py:25` **rolls back** on a propagating exception, so a *raised* 409 was never the hazard. **The hazard is a `return` from inside the block** — which is exactly what `_resolve_claim_conflict:398-400` does — and the mutation that proves it is the idempotence `return`, not the savepoint. **The savepoint mutation comes back green and is recorded as such.**
4. **"Why does skip send `seen_skip_count`? That looks like bookkeeping."** **D6, the review's third BLOCKER.** Without the conjunct, two managers each tapping «דלגי» **once** on a woman at `skip_count == 0` **remove her**: B's EvalPlanQual re-check passes on A's committed row, B's `CASE` reads 1, and **neither client ever showed the confirm** because both rendered 0. One conjunct, one field, one code — the confirm made enforceable rather than advisory.
5. **"`SKIP LOCKED` is what stops two managers getting the same woman."** **No — Decision 22.** LockRows sits *below* the Limit, so with plain `FOR UPDATE` the loser blocks, re-checks the updated tuple, discards it and locks the next row: it gets ticket 2 either way. **`SKIP LOCKED` buys non-blocking**, and its test asserts an elapsed bound, not a distinctness.
6. **"FINISH should be its own route; the ruling says so."** **D5, Conflict 2.** A second finish route would leave F36's shipped room-tile release able to free a room and strand its ticket `in_service` **forever** — the exact defect this feature exists to remove, re-introduced by the feature that removes it. `release` is extended and the shipped suites stay green with **no edit**.
7. **"A reception staffer should be able to remove a duplicate."** **D11, Conflict 8, and it is structural rather than a preference.** `test_the_floor_roles_reach_exactly_the_floor_routes` classifies on the intersection and asserts a floor route admits **all three** floor roles or none (`:313-315`, `:329`); a gate admitting reception but not seamstress red-fails it, and the docstring forbids relaxing the assertion. **Every route in this product is all-five or exactly-two.** The cost is recorded with its upgrade path.
8. **"The floor payload now carries a hundred names and three comments say it carries one per room."** **D10 and Conflict 6 — all five are rewritten in this PR** (three named by D10, two found here as C6 and C7). Leaving a false comment standing as the rationale for the widest role gate in the product is worse than never having written it, and this is the **third** time that sentence is being written.
9. **"The payload emits a bearer capability."** **It does, and D10's rewrite says so in as many words.** `WaitlistEntry.id` is F33's position-page capability; this payload is the second server path that emits one, to a signed-in staffer of this tenant and nobody else. **A29 asserts the console never renders it as a link.** An earlier draft of the rewrite denied it in the same sentence that introduced it — Risk 4.
10. **"`QueueTicketsRepository`'s docstring says no read is keyed on `phone`."** **Conflict 5 — corrected in this PR.** The property that was load-bearing survives: no *anonymous* surface keys on the phone, and **no response body anywhere carries it**. A signed-in staffer grouping today's own arrivals is a different surface with a different threat model.
11. **"Why a second statement just for the duplicate flag?"** **D9, corrected at review.** D2's waiting read filters `status == 'waiting'`, so a Python pass over it can only ever see waiting↔waiting pairs — **blind to the `in_service` twin, which D9 calls the most valuable thing on this panel to remove**, and blind in the direction where a manager with two «נועה»s removes by inference. A phone-only projection over the same index prefix.
12. **"The duplicate remedy should be a merge."** **D8, Decision 5.** A merge must choose which capability survives and whose arrival time wins. Keeping the later ticket costs her place; keeping the earlier one terminates the page her *current* tab is polling. The only column that could move a survivor forward is `requeued_at`, whose published meaning is skip-to-**back**.
13. **"The cues should name the customer — the manager just acted on her."** **Decision 20, and the deck's sharpest privacy line.** `FloorPanel`'s `role="status"` is **persistent** — nothing clears it, not a timer, not a tick, not unmount — so «נועה הוסרה מהתור.» would outlive her row, her visit and her presence in the shop, on a five-role screen. **The cues name the act.**
14. **"`waitlist.calledCue` should say a call was sent."** **It cannot, twice over.** «נשלחה» contains «נשלח» and `i18n.test.ts:560` filters every value in `HE` for it — and the fold D16 requires is what makes the guard reach these keys. It is also **false**: `call` stamps a timestamp and F58 sends nothing. Deck **F-2**.
15. **"Four of the `*Aria` values were corrected by hand and nothing guards them."** **DC-1 — that was true and is now fixed.** `i18n.test.ts` carries four 2.5.3 loops already, one per feature that added an `*Aria`; F58 declares the fifth. Four prior features, no exceptions, on the criterion that is legally binding.
16. **"`rooms.error.STAFF_OCCUPIED` should just be reworded."** **DC-3 and C13 — that option is not available.** Its literal is asserted in three shipped test files, so editing it reds four shipped assertions and breaks this feature's stated acceptance gate. **Two new keys, rendered on the dispatch targets only**, with the shipped third-person pair kept for handover, where the target genuinely is a colleague.
17. **"The assign affordance should be a dialog."** **Decision 21, deck P-4.** A `<dialog>` needs **three** focus mechanisms `RoomsPanel` has already had to ship — open-capture, a close-return resolved so the platform's own does not win, and a tick that drops the open dialog's row — **none of which axe can see.** A row-scoped reveal is covered by MOVES 3, 4 and 5 as they stand. **A11y coverage is a reason to pick the simpler element, not only a cost of picking the harder one.**
18. **"axe passes, so the a11y work is done."** **D18, and it is a legal bar here (IS 5568 / WCAG 2.0 AA).** axe cannot see a focus move that never happened — **four shipped instances in this repo** — and axe has **no rule for SC 2.2.2**. F57's own success-path focus test was **vacuous** because jsdom does not blur a disabled element. Every focus test here blurs explicitly and carries a named mutation that was **run**.
19. **"The e2e harness is the contract test we've been missing."** **It is not, and Risk 6 says so in its own module docstring.** It stubs the API, so a renamed payload key passes every journey while breaking production. It is a **journey and a11y** instrument, and saying so is what keeps it from being trusted for something it cannot do.
20. **"The waitlist should call `elapsedLine` — it already exists."** **It hard-codes `rooms.elapsed*` (`lib/elapsed.ts:31-37`)**, so it would render the ROOM's «כבר 42 דק'» about a woman who has not been in a room and leave two `waitlist.*` keys **dead, green and unused** — `i18n.test.ts` counts entries and never checks that a key is reached. `elapsedMinutes` plus a three-line branch, and **no edit to a shipped `lib/` helper with two shipped callers**.

---

## Out of scope (unchanged from the spec)

Wait-time estimates and any queue analytics — **pre-decided #28**; `created_at → called_at` becomes computable the day this merges and nothing computes it · bride-priority ordering — `e6-instore-realtime.md:74` · restoring a removed ticket — **D8**, recorded as the upgrade path · a true merge preserving both capabilities — **D8** · closing yesterday's unclosed tickets — **F20's retention sweep**, Risk 5 · SMS of any kind — F58 sends nothing, needs no `scheduled_messages` row and no sender ID · any change to `position()`, to `/storefront/checkin`, to F33's three limiters or to the QR sheet · reconciling a queue ticket with a booking for the same woman — **not in v1**; both surfaces render her honestly and the manager reconciles by removing one · a shared `usePoll` in `packages/ui` — **F33's D9** · a feature flag or a `queue_enabled` setting — **this merge IS the control** · renaming `floor.heading` — **deck F-1**, declined with a re-set trigger · a `packages/ui` `Select` min-height fix — **deck F-10**, declined with a re-set trigger · SOS and its overlay — **F37** · the public wall board — **F59**, shipped and gated on this one.
