# Plan: Feature 37 — SOS: targeted page, full-screen alert, ack/resolve, 30s escalation (Epic E7, floor-management program iteration 4)

**Status**: Gate 2 self-approved 2026-08-03 under Interview Q1 (F37 is none of Q1's enumerated exceptions — no payments, no refunds, no privacy-law text, no billing). **Design gate self-approved** by the 2026-07-31 ruling; the deck and the copy deck are on disk, mechanically verified, and **the design critic's verdict is REVISE** — its ten required changes are folded in below as **DC-1 … DC-10** and each has an owning task, as does the non-blocking cite drift. *The gate goes away; the design work does not.* ⚠ **One clause of the gate does NOT go away: the manual screen-reader pass on this PR** (e7 Risks), and spec **D15** is a gate condition in its own right.

**Spec**: `.planning/specs/sos-paging.md` (1 122 lines, D1–D18, 31 ACs, 33 review findings / 33 applied, four BLOCKERs) · **Design deck**: `.planning/design/screens/sos-paging/design.md` (608 lines, §0–§11, nine findings F-1…F-9) · **Copy deck**: `.planning/design/screens/sos-paging/copy.md` (215 lines, 48 keys → **49** after DC-4) · **Branch**: `feature/sos-paging` · **Worktree**: `.worktrees/sos-paging` · **Created**: 2026-08-03

TDD throughout. Every task states its **failing test first**, then the code that makes it pass, then the exact files, then how to verify, then the commit message.

⚠ **A build is running in `.worktrees/alteration-tickets` (F41, PR #39 OPEN) and a second in `.worktrees/floor-dispatch` (F58). Do not touch either.**

---

## ⚠ Four process facts, and the first one is not what the spec says

**1. `db`-marked tests run locally and the escape hatch is SHIPPED CODE.** `backend/tests/conftest.py:88` / `:100` / `:109` document `TEST_POSTGRES_SUPERUSER_URL`, which replaces the Testcontainers cluster with one you started yourself. There is **no patch to apply and no revert obligation** — `git diff main -- backend/tests/conftest.py` must be empty at every commit. Postgres **16.14** is live via Homebrew (superuser `mrwen`, no Docker). The runner, written once into the scratchpad and never committed:

```bash
# scratchpad/run-db-tests.sh
set -euo pipefail
dropdb   --if-exists -h 127.0.0.1 -U mrwen f37_test
createdb              -h 127.0.0.1 -U mrwen f37_test
export TEST_POSTGRES_SUPERUSER_URL='postgresql+asyncpg://mrwen@127.0.0.1:5432/f37_test'
cd "/Users/mrwen/Documents/Github/Ryan + rawad + mrwen/.worktrees/sos-paging/Backend"
uv run pytest -m db -q --ignore=tests/test_media_upload_s3.py
```

**Capture the baseline on the branch's base commit BEFORE Task 1** and record the number in the run report. Do not hardcode a count from any earlier plan — F36, F33 and F59 all added `db` cases since the last one was written. The 9 `test_media_upload_s3.py` cases need MinIO and are excluded; F37 touches no S3.

**This is what made F34, F57, F36 and F59 green on their first CI run.** Six of F37's mutation-checks **cannot be performed at all without a real Postgres** — a monkeypatched repository never stamps anything, never takes a row-level write lock, and never returns rowcount 0 on a guarded UPDATE.

**2. Path hygiene, unchanged and still load-bearing.** The repo path contains a **space** and a **`+`** — quote every shell path. Git tracks `backend/` / `frontend/` **lowercase** while the on-disk directories are `Backend/` / `Frontend/`: `git add Backend/…` **silently skips modified tracked files**. Lowercase every pathspec and verify every commit with `git show --stat`.

**3. `make lint` runs `frontend/scripts/qa-greps.sh`, and it reaches `apps/manage/src` in exactly one place.** Verified at `qa-greps.sh:17` — `SRC="apps/storefront/src"`, so the ten `check` calls **do not read this feature's code at all**. The trailing **date-reads review block** (`:62-67`) greps `apps/storefront/src apps/manage/src packages/ui/src` for `getDay()` / `getDate()` / `toLocaleDateString` / `toLocaleTimeString` and for a single-line `Intl.DateTimeFormat(...)` without `timeZone`. **F37 renders «מאז 11:20» and an elapsed line and is therefore in exactly the class of feature that reaches for a formatter.** It must not: `jerusalemTime` (`lib/jerusalem.ts:35`) already sets `timeZone` and `elapsedLine` (`lib/elapsed.ts`) is arithmetic on two ISO instants. **Capture the baseline before the first frontend task and diff it after every one.**

**4. Two other features hold a migration right now and BOTH claim `0020`.** See C1. This is the sharpest thing that moved since the spec was written and it invalidates one of D8's explicit claims.

---

## What moved since the spec was written — **thirteen corrections**, C1–C13

The spec was written on 2026-08-03. Every citation below was re-opened and re-read on this tree at `3c90c4d`. **The spec is binding and D1–D18 are not re-litigated**; these are the places where the document disagrees with the code.

| The spec says | Actually, now | # |
|---|---|---|
| D8: head is `0019` and *"exactly ONE other feature is in flight with a migration of its own: F41. ⚠ **F58 (floor-dispatch) is NOT a contender** — LOOP-STATE has it at `status: queued` and its own note reads 'No new table'"* | `alembic heads` → **`0019 (head)`** ✓, but **F58 IS a contender**. `.worktrees/floor-dispatch` exists on `feature/floor-dispatch` and holds an **untracked `backend/migrations/versions/0020_floor_dispatch.py`** (`revision = "0020"`, `down_revision = "0019"`) adding `queue_ticket_id` to `fitting_room_assignments` — exactly what F36's plan Task 13 Risk 3 said F58 would have to do. **F41's PR #39 is OPEN** with its own `0020_alteration_tickets.py`. **TWO files claim `0020` today.** The spec's carve-out sentence must go; the rule it protects («do not open the PR while a lower-numbered migration is unmerged») now binds on **two** features, not zero | **C1** |
| Frontend changes → `Nav.test.tsx`: *"the counts staying **owner ten / shift-manager eight** / floor-roles one"* | **owner TWELVE** (`Nav.test.tsx:127`, `:131`), **shift manager TEN** (`:134`, `:138`, `:228` — `NAV_LABELS.slice(0, 10)`), floor roles **one** (`:146`), `NAV_LABELS` **twelve** (`:180`). `SectionKey` is **thirteen** (`App.tsx:20-35`) and `NAV` is **thirteen rows** (`:71-124`) — both of which the spec states correctly elsewhere. **The rule is unchanged and is the point**: the file is untouched and the assertion is an empty `git diff` | **C2** |
| Frontend changes `:872`: `intervalMs?: number` | D12 (`:565`, `:1116`) and AC20b require **`number \| (() => number)`**, and the function form is the entire fix for the silent five-second hole. **The table is wrong and a builder working from it loses AC20b.** This is the critic's DC-9 / new deck finding F-10 | **C3** |
| D17 / deck §11 F-6 / copy §0.1: *"`i18n.test.ts` now folds NINE constants, so the spec's `:61-71` line reference is two lines stale"* | **The spec is RIGHT and both decks are WRONG.** `const HE = [` is line **61** and `];` is line **71** (`HE_F36` at `:60`). The drift claim is false in all three places and copy.md then instructs *"check the line numbers, not the count"* on that false premise. The **mechanism** claim (fold, not merely declare) is correct and its `:33` citation — *"Folded in, not just declared…"* — is correct. Critic's **DC-3** | **C4** |
| *(implicit — D17 asks for a "`sos.*`-scoped assertion that no value matches `/נשלח\|תישלח\|בדרך/`")* | ⚠ **There are TWO ban regexes in that file and copying the wrong one reds the suite.** The global guard at **`:560`** is `/נשלח\|תישלח\|בדרך/` — three terms. The `HE_F33`-scoped block at **`:547`** is `/נשלח\|תישלח\|בדרך\|SMS\|הודעה/` — **five**, and «הודעה» is in `sos.error.noteTooLong` («ההודעה ארוכה מדי.»). **The `sos.*`-scoped assertion must use the THREE-term regex.** A builder mirroring F33's block wholesale reds on a string the copy deck approved | **C5** |
| D15 / deck §8: the red field is where the cards sit | **DC-1's target is `bg-danger` on the FIELD, cards on `bg-surface-raised`** — the deck already corrects this (§2.1) and the arithmetic reproduces. See DC-10 for the two figures that do not | **C6** |
| Deck §0: `Button.tsx:36` is `md`'s `min-h-11`, `:37` is `lg`, `focusRing` at `:62` | `sm` **`:36`**, `md` **`:37`**, `lg` **`:38`**, `disabled={disabled \|\| loading}` **`:57`** ✓, `focusRing` **`:63`**. Critic's non-blocking drift | **C7** |
| Deck §2.4 / §9.5 / copy §0 rule 8: *"the WORD carries the state; the colour never does — `FloorPanel.tsx:554`"* | That sentence is at **`:40`** and **`:668`**. **`:554` is the «רענון» comment** (*"«רענון» in the STALE case only…"*). Cited twice, wrong twice | **C8** |
| Deck §8: `FloorPanel.tsx:521` for `<ul className="divide-y divide-border">` | **`:630`**, with the `<li>` at **`:648`**. The *shape* claim is right; `sm:items-center` vs the deck's `sm:items-start` is F36's own divergence and §7 already flags it | **C9** |
| D14: `main.py:907-909` (`DomainNotFoundError`), `:901-905` (`DomainValidationError`), `_occupied_body` `:350-365`, its `if details:` `:361-364`, imports `:82`, handlers `:1174`/`:1178` | All ✓ except `if details:`, which is **`:363-365`**. `ROOM_OCCUPIED_BODY` is `:339`, `STAFF_OCCUPIED_BODY` `:342`, `NOT_FOUND_BODY` `:164`. **The load-bearing claim — `main.py` registers per CONCRETE class and there is no `_OccupiedError` base handler — is VERIFIED true** | **C10** |
| Testing → `db`: *"`FloorService.__init__` already takes `clock=` (`floor/service.py:165,177`)"* | ✓ **verified**: `clock: Callable[[], datetime.datetime] \| None = None` at **`:165`**, `self._clock = clock or (lambda: …now(UTC))` at **`:177`**, and four shipped readers (`:222`, `:229`, `:429`, `:562`, `:727`). The spec's replacement of the vacuous "cannot freeze the database clock" justification is correct and Task 4 relies on it | **C11** |
| *(the spec does not mention it)* | The fast single-head guard is **`test_migrations.py::test_exactly_one_migration_head` at `:57`** (`get_heads()` at `:76`), and `_parent_of` is at **`:31`**. F36's plan called the guard `:44-52`; it moved. **This is the guard that catches a bad renumber in `make test` rather than as a CI mystery**, and F41's own migration header records it doing exactly that | **C12** |
| Frontend changes → `RoomsPanel.tsx` gains *"one new **optional** prop `onRaise`"* | ✓ and it really is the **only** new prop: `paused` (`:8` of the props interface), `mutate` (`:10`), `onCue` (`:18`), `serverNow`, `selfId`, `role` are all already shipped props. `poll_once` really does run **two** jobs (`worker.py:66`, `:90` `comms.drain_due`, `:108` `sweeper.sweep`) — AC25(a) is a live assertion | **C13** |

### Citations re-captured — ✅ verified on this tree at `3c90c4d`, do not re-check

- ✅ `backend/app/floor/router.py` (340 lines) — the `.claude/rules` paragraph **`:85-87`**; `_no_store` `:117`; `get_floor_service` `:121`; `router = APIRouter(` **`:126`**; the **thirteen** shipped routes `:138`, `:143`, `:156`, `:183`, `:197`, `:217`, `:230`, `:253`, `:263`, `:290`, `:309`, `:330`, `:336`; `ELEVATED = Depends(require_role(OWNER, SHIFT_MANAGER))` **`:173`** with its intersection comment `:169`; `_room(read: RoomRead)` `:176`; `create_room` **`:183`** with **no `status_code=`** (AC1's «200, pinned» claim is correct); handover's *"the role check for this route is the `ELEVATED` gate above and NOWHERE"* docstring `:271`.
- ✅ `backend/app/floor/service.py` (810 lines) — `ELEVATED_ROLES` **`:69`** (`frozenset({OWNER.value, SHIFT_MANAGER.value})` — **string values, not enum members**, which the `for_me` matrix must match); `card_status(row, *, occupied)` **`:80`**; `clock` param **`:165`** / `self._clock` **`:177`** (C11); `end_break`'s capture-before-write `before` **`:268`** / `previous` **`:269`**; `handover`'s `before` **`:481`**; `_authorize` **`:794`** with its role test at `:805`; `today_jerusalem(self._clock)` `:727`.
- ✅ `backend/app/floor/validation.py` (79 lines) — `FloorValidationError` `:14`, `MAX_ROOM_LABEL_LENGTH = 40` `:23`, **`class _OccupiedError(Exception)` `:43`** with the `__mro__` docstring, `RoomOccupiedError` `:64`, `StaffOccupiedError` `:70`.
- ✅ `backend/app/floor/schemas.py` (343 lines) — `CreateRoomRequest` `:296` whose docstring says **`label` carries NO `Field` bound** (DC-4's premise, verified in the code's own words); `UpdateRoomRequest` `:306`.
- ✅ `backend/app/db/repositories/sessions.py` — **four** methods and no more: `insert` `:11`, `active_by_token_hash` `:31`, `revoke_for_staff_user` `:44`, `revoke_by_token_hash` `:70`. **`has_live_session` does not exist.**
- ✅ `backend/app/db/repositories/fitting_room_assignments.py` — `STAFF_ACTIVE_INDEX` `:18`; **`violated_index(error)` `:21-43`**, returning `getattr(getattr(error.orig, "__cause__", None), "constraint_name", None)`, with the docstring recording that the obvious form *"is `None` for every violation there has ever been"*; `by_id` `:119` (**no `status` filter**, `:132`); `_refreshed` **`:276`** with `populate_existing=True` at **`:308`**.
- ✅ `backend/app/main.py` — `ROOM_OCCUPIED_BODY` `:339`, `STAFF_OCCUPIED_BODY` `:342`, `_occupied_body` **`:350`** with `if details:` **`:363-365`**, `DomainValidationError` handler **`:901`**, `DomainNotFoundError` **`:907`**, `NOT_FOUND_BODY` `:164`, the two floor imports **`:82`**, the two 409 handlers **`:1174`** and **`:1178`**. **No base-class handler anywhere.**
- ✅ `backend/app/models/constants.py` — `StaffRole` `:9`, `StaffCardStatus` `:26`, `AuditAction` `:181`, F36's four members `:325`, `:326`, `:330`, `:335` with the *"FOUR values and not six"* comment `:309`.
- ✅ `backend/app/worker.py` — `poll_once` **`:66`**, **two** jobs (`:90`, `:108`), the interval log `:149`/`:153`, `asyncio.sleep(settings.worker_poll_interval_seconds)` `:157`.
- ✅ `backend/tests/test_floor_api.py` — `FLOOR_OPEN_ROUTES` + `FLOOR_TIGHTENED_ROUTES` (four rows, `:108-111`) composed into `FLOOR_ROUTES` **`:113`** (**thirteen**); `SPEC_ERROR_CODES` **`:127`** (**seven**) with its *"⚠ SEVEN after F36"* comment `:121`; the walks at `:486`, `:514-516`, `:527`, `:593`, `:605`, `:633`, `:803`, the mutating filter `:1120`, `assert observed == SPEC_ERROR_CODES` `:1175`.
- ✅ `backend/tests/test_staff_role_gating.py` — the *"FLOOR_OPEN below is the exhaustive list"* comment **`:84`**, `FLOOR_ROLES` `:85`, the **route-template** comment `:93-96`, `FLOOR_READ` `:98`, F36's six `:107-115`, the ⚠ *"the FOUR tightened routes are DELIBERATELY ABSENT"* block `:117-122`, **`FLOOR_OPEN` `:123` with NINE members**, the *"IT MUST NEVER BE RELAXED TO A SUBSET CHECK"* warning `:279`, `frozenset.intersection(*role_sets)` **`:310`**, the equality `:323`, the `missing` guard `:332-333`.
- ✅ `backend/tests/test_migrations.py` — `_parent_of` **`:31`**, `test_exactly_one_migration_head` **`:57`** / `get_heads()` `:76`, the `_parent_of` round-trips at `:1462` (customer crm) and **`:1708` (fitting rooms)**, both last-in-file inside `try/finally`.
- ✅ `backend/tests/test_floor_db.py` — the ⚠ **seed-role rule** `:10-32` (*"Every row this module COMMITS holds `owner` or `shift_manager`, never a floor role"*, and the reason: session-scoped `migrated_db`, alphabetical collection, `test_migrations.py` reddens); the *"not `asyncio.gather`"* block **`:251-263`**; **`test_a_second_start_landing_in_the_gap_renders_the_winners_timestamp` `:266`** — the UPDATE-race shape F37 copies; `test_an_end_landing_in_the_gap_after_a_concurrent_end_writes_nothing` `:330`.
- ✅ `backend/tests/test_frontend_constant_parity.py` — `MIRRORS` `:55`, `("MAX_ROOM_LABEL_LENGTH",)` **`:109`** with `id="manage-floor"` **`:110`**, parametrized `:140` and `:149`.
- ✅ `backend/tests/test_spa_serving.py:381` `test_the_manage_dev_proxy_names_every_manage_api_segment`.
- ✅ `frontend/apps/manage/src/lib/usePoll.ts` (324 lines) — `POLL_INTERVAL_MS` `:15`, `MAX_BACKOFF_MS` `:19`, `IDLE_STOP_MS` `:23`, `IDLE_STOP_MINUTES` `:24`, `terminalOf` **`:100`**, **`idleRef` (the TIMEOUT HANDLE) `:118`**, `backoffRef` **`:119`**, `clearIdle` **`:140`**, the `document.hidden` early return `:156`, **`armIdle` `:165` opening with `clearIdle()` at `:166`** and `setTimeout(…, IDLE_STOP_MS)` `:170-176`, the second `document.hidden` guard `:187`, `schedule(backoffRef.current)` `:193`, the StrictMode note `:206-208`, `armIdle()` on mount `:261`, `succeeded()` resetting `backoffRef.current = POLL_INTERVAL_MS` **`:285`**, `fail` doubling `:288`, `reschedule` **`:290`**, `terminalOf` use `:293`, `resume()` resetting `:317` and re-arming `:319`.
- ✅ `frontend/apps/manage/src/App.tsx` (222 lines) — `SectionKey` **`:20-35`, thirteen members** (`floor` labelled *"the TWELFTH"*, `checkinQr` *"the THIRTEENTH"*); `NAV` **`:67`, thirteen rows** (`:71-124`); `setStaff` declared `:129`; `bootstrapped` `:130`; the `!bootstrapped` early return **`:146`**; `LoginForm` return **`:155`**; `handleLogout` `:158` with **`setStaff(null)` `:164`**; the only other clear **`:142`** (`api.me().catch()`); `ToastProvider` **`:187`**; `onNavigate={(key) => setSection(key as SectionKey)}` **`:196`**; `<FloorPanel …/>` at **`:212`** (board) and **`:215`** (floor) — **2 of 13 sections**.
- ✅ `frontend/apps/manage/src/components/FloorPanel.tsx` (759 lines) — `elapsedLine` import `:8`, `jerusalemTime` `:9`, **the "WORD carries the state" sentence `:40` and `:668`** (C8); `cardError` **`:99`**, `headingRef` **`:101`**, `cardAlertRef` **`:103`**, `cardErrorRef` `:114`, `holdRef` **`:127`**; the reclaim block `:168-169`; **`poll.succeeded()` `:174`** and **`poll.reschedule()` `:192`** — the two calls D11's five-second-hole argument turns on; the ⚠ cue-only-when-changed comment `:238`; the **unconditional** `cardAlertRef.current?.focus()` **`:270-271`** (MOVE D's warning, verified); the `[cardError]` effect ending `:292`; `headingRef.current?.focus()` `:291`, `:308`; **`mutate` `:363`** with `poll.reschedule()` in the `.finally()` `:381`; **`<h2 ref={headingRef} tabIndex={-1}> `:436`** (MOVE G's fallback); the terminal `role="alert"` `:449`; `jerusalemTime(updatedAt)` `:474`; the **one** `role="status"` cue `:510-516`; the outage `role="alert"` `:582`; **`<ul className="divide-y divide-border">` `:630`** (C9) with `<li` `:648`; *"Which control EXISTS is the rendered form of D6's two axes"* **`:639`**; `elapsedLine(t, serverNow, card.occupancy.assigned_at)` `:699`; `jerusalemTime(card.break_started_at)` `:712-714`; the per-card alert `:718-725`.
- ✅ `frontend/apps/manage/src/components/RoomsPanel.tsx` (955 lines) — the props interface (`selfId` `:5`, `role` `:6`, **`paused` `:8`**, `mutate` `:10`, `onCue` `:18`, `serverNow` `:24`); **`openDialog` state `:144`**; **`dialogTriggerRef` `:160`**; the open-dialog reconciliation `:291-306`; **the MOVE-4 effect `:308-330`, keyed on `[openDialog]` (`:330`), reading `dialogTriggerRef.current` (`:317`) and branching on `trigger.isConnected` (`:325`)**; the declaration-order comment `:433`; **`openFrom` `:558` setting `dialogTriggerRef.current = event.currentTarget` `:560`**; **a bare `<Select` at `:790`, OUTSIDE any dialog** (the Esc-capture guard's premise, verified); the tile action row **`<div className="flex flex-wrap justify-end gap-3">` `:838`**; the three shipped `Modal`s `:605`, `:932`, `:941`.
- ✅ `frontend/apps/manage/src/lib/elapsed.ts` — `elapsedMinutes(serverNow, assignedAt)` clamped at zero, **`elapsedLine(t, serverNow, assignedAt)`** hardcoding `rooms.elapsed` / `rooms.elapsedJustNow`.
- ✅ `frontend/apps/manage/src/__tests__/i18n.test.ts` — `HE_F15` `:24`, `HE_F51` `:28`, `HE_F52` `:29`, **the "Folded in, not just declared" comment `:33`**, `HE_F17` `:38`, `HE_F34` `:39`, `HE_F57` `:43`, `HE_F53` `:44`, `HE_F33` `:51`, **`HE_F36` `:60`**, **`const HE = [` `:61` … `];` `:71` — NINE constants** (C4); the F36 no-`nav.` assertion `:441`; **the `HE_F33`-scoped five-term ban `:547`** (C5); **the global three-term ban `:560`**.
- ✅ `frontend/apps/manage/src/__tests__/Nav.test.tsx` — `NAV_LABELS` `:83`, owner **twelve** `:127`/`:131`, shift manager **ten** `:134`/`:138`/`:228`, floor roles **one** `:146`, the coupled-edits comment `:174-179`, **`toHaveLength(12)` `:180`** (C2).
- ✅ `frontend/apps/manage/src/i18n/he.ts` — **`floor.refresh` = «רענון» `:618`**, **`floor.reload` = «רענון הדף» `:663`** (copy deck correction (b) confirmed), `rooms.elapsed` `:813`, `rooms.elapsedJustNow` `:817`, `rooms.cancel` `:864`, `rooms.handoverOnBreak` `:908`.
- ✅ `frontend/packages/ui/src/components/` — `Button.tsx` `sm:` `:36`, `md:` `:37`, `lg:` `:38`, `disabled={disabled \|\| loading}` `:57`, `focusRing` `:63` (C7); `Toast.tsx:40` `"pointer-events-none fixed top-4 start-0 end-0 z-50 …"` with `bg-danger text-surface-raised` `:47`; `ConsoleShell.tsx:43` `<SkipLink href="#console-main">` and **`:84` `<main id="console-main" tabIndex={-1} className="mx-auto flex max-w-[720px] …">`**; `BookingCTA.tsx:16` **`"fixed inset-x-0 bottom-0 z-40 …"`** (DC-2's shipped spelling).
- ✅ `frontend/packages/ui/src/theme.css` — `--color-surface` `#F6F0E6` `:23`, `--color-surface-raised` `#FFFFFF` `:24`, `--color-ink` `#2B2118` `:25`, `--color-danger` `#A03232` `:33`, `--color-focus` `#7F612B` `:35`, `@media (prefers-reduced-motion: reduce)` `:155`.
- ✅ `sr-only` is a shipped, used utility in this app — `LoginForm.tsx:41`, `DashboardSection.tsx:288`, `:393`. **DC-4's resolution needs no new CSS.**
- ✅ `Makefile` — `test` `:18`, `test-db` `:21`, `test-all` `:24`, `lint` `:27`, `qa-greps` `:33`, `fe-build` `:44`, `fe-test` `:47`, `e2e` `:51`.
- ✅ `frontend/scripts/qa-greps.sh` — `SRC="apps/storefront/src"` `:17`; the date-reads block reading `apps/manage/src` `:62-67`.

---

## The design critic's ten required changes — DC-1 … DC-10

**The verdict is REVISE, not REJECT.** The critic reproduced §2.1's contrast correction independently, confirmed no AI-generic patterns, confirmed token compliance (every colour, size, radius, shadow and spacing step resolves; `max-w-[720px]` is `ConsoleShell.tsx:84`'s own; no `gold-strong`; no new token) and confirmed the 375 arithmetic (375−32=343, 343−48=295, 16+24=40). What follows is the remediation list, severity descending, each with an owning task. **DC-3, DC-5, DC-6, DC-8, DC-9, DC-10 and the cite drift are document-only and land in Task 0. DC-1, DC-2, DC-4 and DC-7 are build work.**

| # | What | Owner task |
|---|---|---|
| **DC-1** | **MOVE A and MOVE C land focus on the accept button, which is the accidental-accept path §2.3 counts five guards against and never tallies.** MOVE A fires *iff* `activeElement === document.body` — precisely the state in which the next Space is a page-scroll — so it converts that keypress into an irreversible accept sitting on top of F-2's two-minute hole. MOVE C is worse: it parks focus on a **different** emergency's accept control at the moment the user was mid-keyboard-interaction with the one that left. **RESOLUTION: both destinations become the card container, `<article ref tabIndex={-1} aria-labelledby={whoId}>`.** Accept stays **first in DOM inside the card**, so reach costs one Tab; the `role="alert"` region is a child and the announcement is untouched; §2.3's five guards become six. ⚠ **`aria-labelledby` points at the WHO paragraph's `useId()` — no new string, no drift** — chosen over a bare `<article tabIndex={-1}>` because focusing an unnamed article makes some ATs re-read the whole subtree the alert just announced. ⚠ **THE Esc ROUTE-IN IS NOT CHANGED**: AC17 requires one Esc to land on «אני מגיעה», and it is a *deliberate* keypress, not an involuntary arrival — that distinction is the whole of DC-1 and a builder "unifying" the two destinations reverts it. §2.3's sentence *"the default outcome of a keypress inside the overlay is accepting the emergency"* is **rewritten**: DOM order still puts accept first, and the default outcome of a keypress on the card container is **nothing** | **0** (deck) + **14** (build + named test + mutation) |
| **DC-2** | **`inset-inline-0` is not a Tailwind utility.** §8's bottom-container row. Verified in the built bundle: `.inset-x-0{inset-inline:0}` exists, `.start-0`/`.end-0` exist, **`inset-inline-0` is 0 occurrences**. As written the class is dropped, the fixed container loses its inline inset, and *"one container, so they can never collide"* silently stops being true. **Use `inset-x-0`** — `BookingCTA.tsx:16`'s shipped spelling (`Toast.tsx:40`'s `start-0 end-0` is the equivalent and either is defensible; one spelling, picked, is the deliverable) | **0** (deck) + **14** |
| **DC-3** | **The `i18n.test.ts` "`:61-71` is two lines stale" claim is FALSE and it appears three times** — `design.md:10`, §11 F-6, `copy.md` §0.1 — and copy.md then instructs *"check the line numbers, not the count"* on that false premise. `const HE = [` is line **61**, `];` is line **71**. **Delete the drift claim from all three places and delete the derived instruction.** Keep the mechanism claim (fold, not merely declare) and the `:33` citation — both correct (C4) | **0** |
| **DC-4** | **The WHERE line is unlabelled and the room label is unconstrained free text.** `CreateRoomRequest.label: str` carries **no `Field` bound** — its own docstring says so (`floor/schemas.py:296-301`) — and `0019` puts no CHECK on content, so a boutique that types «2» or «A» is fully supported. The card's second line is then «2» at 23px with no prefix, and the atomic utterance is «דנה כהן קוראת לעזרה 2 צריך סיכות». §9.1's example («חדר 2») is the one case that hides it, and P-5's *"unambiguous by position"* is a sighted-user argument that does not survive `aria-atomic`. **RESOLUTION: a visually-hidden prefix INSIDE the region** — `<span className="sr-only">{t("sos.roomA11yPrefix")}</span>` before the bare `<bdi>`. ⚠ **NOT an `aria-label` on the `<p>`**: ARIA prohibits naming on `role=paragraph`/generic, so the deck's own em-dash-value-last shape is unavailable here and would have shipped a name nothing reads. **One new key, 48 → 49**, and §9.1's *"there is no visually-hidden copy to keep in sync"* is amended: it is a one-word **label**, not a copy of a value | **0** (deck + copy) + **12**, **14** |
| **DC-5** | **F-9 omits the one number the ruling asked to be added to honestly.** F57's Risk 2 handed F29 *"~28 round trips per 5 s per device on that screen"*; F-9 gives ~11 / ~27 / three-times-per-beat and never states the new board total, and *"Eleven sections … now issue ~11 round trips per 5s"* parses as 11 sections × 1 request. **RESOLUTION: state it with units, per device, per screen, the way F57 did** (table below), **and compute the no-idle-stop consequence instead of gesturing at it: 12 h × 720 ticks/h × ~11 ≈ 95 000 round trips per device per night — the first unbounded number in the product.** ⚠ **The critic's own ~39 / ~55 is one feature stale** and the plan says so rather than picking silently: it uses F57's pre-F36 floor tick of ~11, while F36's plan Task 13 records the floor tick at **~13** after F36 added a statement to the payload read. **The spec's ~41 / ~57 is the right pair and the addends are shown** | **0** (deck) + **18** |
| **DC-6** | **`sos.acceptedBy` = «{{name}} מגיעה.» is the one string that promises what the product cannot vouch for**, and F-2 admits it in as many words. Rule 2 exists to stop exactly this class of claim; the copy row argues only the button-word symmetry. **RESOLUTION: the string is KEPT and the row confronts the question.** The symmetry is a real property — she pressed «אני מגיעה» and the raiser reads the same verb, one word across two screens with no translation — and the alternative «{{name}} אישרה את הקריאה.» is system-register («approved the call») on the one screen that must read like a person. **So the row states in writing that the claim is deliberately stronger than the fact**, that the product knows an intention and not a walk, and that the mechanism bounding it is D6's `_stalled` at two minutes — **cross-referencing F-2 by name.** That is the critic's second permitted branch, taken deliberately | **0** (copy) |
| **DC-7** | **`SosCentre`'s per-row error has no home, and `FloorPanel` has exactly one of everything it would need.** Verified: `cardError` `:99`, `cardAlertRef` `:103`, an **unconditional** `cardAlertRef.current?.focus()` on every non-null transition `:270-271`, rendered under `cardError?.id === card.id` `:718`. §6 names the centre's 409/404 row states; §8 gives an in-card-alert row for the *overlay* and one for the dialog, and **nothing for a centre row.** Shared, an SOS 409 steals focus into a **staff card's** alert node through the exact guard-less effect MOVE D warns against copying — and `cardError.id` is a *staff card* id, so `cardError?.id === card.id` would collide semantically. **RESOLUTION: `SosCentre` owns its own pair** — its own `rowError: {id, text} \| null`, its own `rowAlertRef`, and its own focus rule **guarded on `document.activeElement` being inside that row** (MOVE D's shape, not `FloorPanel`'s unguarded one). Named **MOVE H**, with its own mutation. **`FloorPanel`'s pair is not touched, which is also what keeps its shipped test expectations unedited** | **0** (deck §6/§8/§9.2) + **15** |
| **DC-8** | **§2.2 and §8 disagree on the field element** — §2.2's diagram carries `role="presentation"`, §8's row does not. **RESOLUTION: drop it.** It is a no-op on a `div`, and on an `overflow-y-auto` container it invites a 2.1.1 argument nobody needs | **0** (deck) |
| **DC-9** | **Add the `intervalMs` contradiction as F-10.** Spec `:872`'s Frontend-changes table says `intervalMs?: number`; the spec's own code block at `:565` and D12 at `:1116` say `number \| (() => number)`, and the function form is the whole fix for the silent five-second hole (`:502-504`) — the hole that opens exactly when the raiser is waiting to see who is coming. `grep intervalMs design.md` returns two hits, neither of them this. **It is the highest-consequence spec defect the design work surfaced and §11 does not carry it.** New deck finding **F-10**, and the spec table row is amended (C3) | **0** (deck + spec) + **11** |
| **DC-10** | **Two of §2.1's four "measured, not eyeballed" numbers do not reproduce, and one contradicts the shipped ledger.** Recomputed from the shipped hexes (`theme.css:23-35`), sRGB relative luminance, WCAG 2.x: **`#7F612B` on `#A03232` = 1.22:1** (deck says 1.30) · **`#2B2118` on `#A03232` = 2.25:1** (deck says 2.22) · **`#FFFFFF` on `#A03232` = 7.01:1** ✓ (matches `tokens.md:33`'s ≈7.0) · **`#A03232` on `#FFFFFF` = 7.01:1 — the SAME PAIR**, so §8's *"danger text on white ≈7.4"* and §2.4's *"≈7.4:1 ✓"* are both wrong and align to **≈7.0**. `#A03232` on paper `#F6F0E6` = 6.18 ✓ unchanged. **No verdict flips** — 1.22 and 2.25 both still fail AA and 7.01 still passes — **but §2.1's entire authority is that it is arithmetic, and it is the table the next coloured-field feature will cite** | **0** |

**Non-blocking cite drift, fixed in place with no argument changes** (C7, C8, C9): `Button.tsx` `md` `:37`, `lg` `:38`, `focusRing` `:63` (`disabled` `:57` is right) · `FloorPanel.tsx:554` → **`:40` and `:668`** for *"The WORD carries the state; the colour never does"* (`:554` is the «רענון» comment) · `FloorPanel.tsx:521` → **`:630`** for the `<ul className="divide-y divide-border">`, `<li>` at `:648`; `sm:items-center` vs the deck's `sm:items-start` is F36's divergence and §7 already flags it correctly.

**Verified sound by the critic and NOT to be re-litigated**: the D15 contrast correction and its F15 F-6 call-site argument; §1's invisible normal state; MOVE D's premise (`FloorPanel.tsx:270-271` really is unguarded); MOVE G's premise (`RoomsPanel`'s effect `:308-330` really is keyed on its own `openDialog` `:144`); §9.4's `<select>` guard (`RoomsPanel.tsx:790`); `Modal` rendering its `<dialog>` unconditionally, so `dialog[open]` is sound; `Toast` `z-50` over `z-40`; thirteen `SectionKey`; `ToastProvider` `:187`; `setStaff(null)` only at `:142`/`:164`; `FloorPanel` at `:212`/`:215`; `ConsoleShell.tsx:43`/`:84`; `theme.css:155-163`; `usePoll`'s `document.hidden` pause and `terminalOf` `{401,403}`; `elapsedLine(t, serverNow, assignedAt)`; `ELEVATED_ROLES` at `service.py:69`; `violated_index()`'s `__cause__` form; `worker.py`'s interval-driven sleep. All four copy corrections check out (`floor.refresh` «רענון» `:618`, `floor.reload` «רענון הדף» `:663`, `rooms.cancel` `:864`, `rooms.handoverOnBreak` `:908`, `rooms.elapsed` `:813`). The register scan holds: zero `!`, zero `/נשלח|תישלח|בדרך/` including the near-misses «שליחת» and «נרשמה», zero literal digits.

---

## Scope fence — read this before every task

**F37 ships one table, five routes, one app-level poll, four components and an overlay that appears unbidden.** It ships no push, no bell, no sound, no worker job and no customer's name.

| Not in F37 | Whose |
|---|---|
| Browser push, service workers, APNs, FCM, SMS, a phone call, a `message_log` row, a `MessageKind` value | **out — #32 and the 2026-07-31 ruling, in-app only** |
| F35's durable staff bell | **F35 — DROPPED from this feature's deps by the ruling** |
| Sound, vibration, flashing, any motion at all | **out — WCAG 1.4.2, a quiet room, a vestibular trigger** |
| A durable `escalated_at`; a `SOS_ESCALATED` audit member; any worker job | **out — D6's recorded upgrade path. `app/worker.py` gets a ZERO-LINE DIFF (AC25b) and `poll_once` keeps running exactly two jobs (AC25a)** |
| A second escalation tier for an OPEN alert (30 s → manager → 60 s → everyone) | **out — one tier, one number, one ruling. `_stalled` is NOT that: same audience, same mechanism, applied to the ACCEPTED state** |
| Widening the stall's audience beyond `ELEVATED_ROLES` | **out — that IS a second tier** |
| Auto-resolve, auto-expire, auto-cancel, an un-accept verb | **out — nothing on a clock closes an alert; only a person does** |
| A `sos_alert_targets` table; any unique index on `sos_alerts`; any advisory lock; a `begin_nested()` savepoint | **out — D1, D2. There is no index to violate, therefore no `IntegrityError`, therefore no savepoint. Copying F36's claim one file over is cargo** |
| A history index on `sos_alerts`; `resolved_at` / `resolved_by` / `cancelled_at` | **out — D1, D2. F36's history index had NAMED readers; this one would have none** |
| A chat thread, a reply, an ETA, severity levels, priorities, per-role SLAs, response-time analytics, a history read | **out — pre-decided #28, D1, D2** |
| Paging a role other than shift manager; an on-shift roster column | **out — the ruling; F40's** |
| Cross-tenant or cross-branch paging; retention of alert rows | **out — F20 owns retention (Risk 5)** |
| A new nav row, a fourteenth section, an `App.tsx` `SectionKey` change | **out — D11. `SectionKey` and `NAV` stay THIRTEEN and `Nav.test.tsx` gets a zero-line diff (C2)** |
| A second pause control, a second freshness row, a third SC 2.2.2 mechanism on the board | **out — D16, F36's D15 (*"three would start to be a defect"*)** |
| A `packages/ui` component, variant, colour, token, formatter or motion rule; a new date library | **out — deck P-9. `packages/ui/**` gets a zero-line diff** |
| Any customer datum on the SOS payload | **out — D10, the feature's largest privacy decision, and the app-level poll is exactly why** |
| A `vite.config.ts` edit; a `qa-greps.sh` edit; a `conftest.py` edit | **out — every route's second segment is `floor` (D9); no new formatter (D17); the harness is shipped code** |
| Any `/manage/**` e2e | **F58 owns the interception harness** |
| `queue_ticket_id`, take-next, push-assign, finish, skip, call | **F58 — and it is BUILDING with its own migration right now (C1)** |

If a task's diff grows a nav row, a `packages/ui` edit, a `worker.py` line, a unique index, a `begin_nested()`, a `client_label`, or a fifth `usePoll` instance, it has left F37.

---

# Part 0 — the plan

## Task 0 — This plan, thirteen spec amendments, and the design critic's ten
`.planning/plans/sos-paging.md` (this file), `.planning/specs/sos-paging.md`, `.planning/design/screens/sos-paging/design.md`, `.planning/design/screens/sos-paging/copy.md`

No test, no code. Amend the three documents so each is the binding statement of every resolution above.

**Spec (`sos-paging.md`) — C1–C13, DC-9:**
- **D8 + the header + Risk 12** — delete the *"⚠ F58 is NOT a contender"* carve-out and replace it with C1's finding: **two** features hold a `0020` today (F41's PR #39 open, F58's worktree untracked), so the *"do not OPEN the PR while a lower-numbered migration is unmerged"* clause binds on both. Keep the RULE verbatim; delete the number-of-contenders claim, which is what rotted.
- **Frontend changes → `Nav.test.tsx`** — «owner ten / shift-manager eight» → **owner twelve / shift-manager ten**, citing `Nav.test.tsx:127`, `:134`, `:138`, `:180`, `:228`. The rule is unchanged and is the point (C2).
- **Frontend changes `:872`** — `intervalMs?: number` → **`intervalMs?: number | (() => number)`**, matching `:565` and D12 (C3, DC-9).
- **D17 + Testing → `i18n.test.ts`** — state that the `sos.*`-scoped ban assertion uses the **THREE-term** `/נשלח|תישלח|בדרך/` (`:560`), **not** the `HE_F33`-scoped five-term `/נשלח|תישלח|בדרך|SMS|הודעה/` (`:547`), because «הודעה» is in the approved `sos.error.noteTooLong` (C5).
- **D14** — `_occupied_body`'s `if details:` is `:363-365` (C10). Everything else in D14 verified.
- **Testing → `db`** — the single-head guard is `test_migrations.py::test_exactly_one_migration_head` at **`:57`**, `_parent_of` at **`:31`**, F36's own round-trip at `:1708` (C12).
- **D15 / Frontend changes → `SosOverlay.tsx`** — MOVE A and MOVE C land on the **card container**, not the accept control; the Esc route-in still lands on «אני מגיעה» (DC-1). Add DC-4's `sos.roomA11yPrefix` to D17's table with its reason.
- **Backend changes** — no change; `has_live_session`'s absence, the two imports and the two handler blocks are all verified true.

**Design deck (`design.md`) — DC-1, DC-2, DC-3, DC-4, DC-5, DC-8, DC-9, DC-10 + cite drift:**
- **§9.2 rows A and C, §2.3, §6 (S-one, S-many, S-gone)** — the destination is `<article ref tabIndex={-1} aria-labelledby={whoId}>`; accept stays first in DOM; **§2.3 gains a SIXTH guard** and its *"the default outcome of a keypress inside the overlay is accepting the emergency"* sentence is rewritten (DC-1). §9.4's Esc row is explicitly **exempted**, with the deliberate-versus-involuntary distinction stated.
- **§8 bottom-container row** — `inset-inline-0` → **`inset-x-0`** (DC-2).
- **§10 header, §11 F-6** — delete the "two lines stale" claim (DC-3).
- **§2.2, §8 WHERE row, §9.1** — the `sr-only` prefix inside the region; §9.1's *"no visually-hidden copy"* amended to *"one visually-hidden LABEL and no copy of any value"* (DC-4).
- **§11 F-9** — the full table with units (below), plus the ~95 000/night figure, plus the recorded reason the critic's ~39/~55 differs (DC-5).
- **§2.2 diagram** — drop `role="presentation"` (DC-8).
- **§11** — new finding **F-10**, the `intervalMs` contradiction (DC-9).
- **§2.1, §8** — focus-on-danger **1.22**, ink-on-danger **2.25**, white-on-danger **7.01**, and **danger-on-white 7.01, not 7.4** in both §2.4 and §8 (DC-10).
- **§6, §8, §9.2** — **MOVE H**: `SosCentre` owns its own `rowError` / `rowAlertRef` / in-row guard (DC-7).
- **§0, §2.4, §8** — the cite drift: `Button.tsx:37`/`:38`/`:63`; `FloorPanel.tsx:40`+`:668` not `:554`; `FloorPanel.tsx:630`+`:648` not `:521`.

**Copy deck (`copy.md`) — DC-3, DC-4, DC-6:**
- **§0.1** — delete the "two lines stale" sentence **and** the derived instruction *"check the line numbers, not the count"*; the fold and its `:33` citation stay (DC-3).
- **§0 rule 2, §9 rule 2, §10 step 3** — the `sos.*`-scoped assertion uses the **three-term** regex, and say why the five-term one is wrong here (C5).
- **§1** — a new row, **`sos.roomA11yPrefix`** = «מיקום», the `sr-only` label before the bare `<bdi>`; the WHERE row's *"NOT A KEY"* line is amended to *"the VALUE is not a key; the label is"*. **48 → 49**, and §9's scan and §10 step 1 re-count (DC-4).
- **§4, `sos.acceptedBy`** — the row gains the honesty paragraph: the claim is **deliberately stronger than the fact**, the product knows an intention and not a walk, and D6's `_stalled` at two minutes is the mechanism that bounds it. Cross-reference **`design.md` §11 F-2** by name (DC-6).

- **Done when** (each of these greps HITS today and must MISS after this task — verified on this tree, counts in brackets):
  - `grep -n "NOT a contender\|owner ten / shift-manager eight\|intervalMs?: number\`" .planning/specs/sos-paging.md` → nothing *(today: 1 + 1 + 1)*
  - `grep -rn "inset-inline-0\|two lines stale\|role=\"presentation\"\|7\.4\|1\.30:1\|2\.22:1\|Button.tsx:36\|FloorPanel.tsx:554\|FloorPanel.tsx:521" .planning/design/screens/sos-paging/` → nothing *(today: 2 + 2 files + 1 + 3 + 6 + n + 1 + 2 + 1)*
  - `design.md` §9.2 has **eight** rows (A–H, MOVE H added by DC-7); `copy.md` says **49** everywhere it said 48; `design.md` §11 has **ten** findings (F-10 added by DC-9).
- **Commit**: `docs(planning): F37 implementation plan, thirteen spec amendments and the design critic's ten`

---

# Part I — the backend

## Task 1 — The migration **and** the `SosAlert` ORM model, as one atomic change (D1, D2, D8 / C1, C12)
`backend/migrations/versions/00NN_sos_alerts.py` (**✚**), `backend/app/models/sos_alert.py` (**✚**), `backend/app/models/constants.py`, `backend/tests/test_migrations.py`

**Migration + model ship in one commit and this is not a preference.** No model↔migration parity test exists anywhere in `backend/tests/`, and C12's single-head guard proves the *chain* and not the *mapping*. Without `models/sos_alert.py`, every backend line in Tasks 2–9 is an `AttributeError` at import.

### The revision number is a RULE, not a number

```
cd "/Users/mrwen/Documents/Github/Ryan + rawad + mrwen/.worktrees/sos-paging/Backend" \
  && uv run python -m alembic heads
```

As of 2026-08-03 it prints **`0019 (head)`**, so the file is `0020_sos_alerts.py`, `revision = "0020"`, `down_revision = "0019"`. **Do not read that number off this document.** ⚠ **TWO other features hold a `0020` right now** (C1): F41's PR #39 is OPEN with `0020_alteration_tickets.py`, and `.worktrees/floor-dispatch` holds an untracked `0020_floor_dispatch.py`. The head **will** move, probably twice.

1. **BUILD at `alembic heads` + 1**, `down_revision` = whatever head is then — so the branch is self-coherent and its `db`-marked tests actually run. A `down_revision` naming a revision that lives only on another branch makes alembic unable to build the revision map at all, so `alembic upgrade head` fails and **every** `db` test fails with it. A wrong number therefore fails **loudly**.
   ⚠ **The quieter failure is the one F41's own migration header records having lived**: two files claiming the same `revision` STRING with different filenames do **not** error — alembic emits `UserWarning: Revision 0020 is present more than once`, **dedupes to ONE script and drops the other**, which on a fresh database means one of the two tables is simply never created. Git sees a textually clean merge. **`test_exactly_one_migration_head` is what catches it — but only AFTER the rebase**, because from an unrebased worktree there is only ever one `0020` to see. So: **rebase first, then read that test.**
2. **Make the migration the LAST commit on the branch.** Task 1 is early, so the commit is *reordered onto the tip* at rebase — or amended in place, since nothing else in the tree references the revision literal.
3. **RE-RESOLVE from `alembic heads` on `origin/main` immediately before the rebase that precedes the push.** Three edits: the filename, the `revision` literal, the `down_revision` literal.
4. **Do not OPEN the PR while a lower-numbered migration is still unmerged.** Watch PR #39 and `feature/floor-dispatch`.
5. **Confirm `alembic heads` prints exactly ONE head on the rebased branch**, and confirm `make test` is green — C12's `test_migrations.py:57` is the fast, no-DB guard.

### The failing tests first (`db`-marked, appended to `test_migrations.py`, **run locally**)

Follow the file's own convention: **the round-trip test goes last in the file**, owns no fixtures, and wraps the downgrade in `try/finally: command.upgrade(cfg, "head")`. Every assertion is keyed to **"after this feature's migration"**, never to a number.

1. `test_the_sos_alerts_migration_creates_the_table` — the column list read from `information_schema.columns`, pinned as a **set equality** so a fourteenth column cannot arrive unreviewed: `id, tenant_id, created_at, updated_at, deleted_at, raised_by, target_staff_user_id, fitting_room_assignment_id, note, status, accepted_by, acknowledged_at`. `raised_by` NOT NULL; `target_staff_user_id`, `fitting_room_assignment_id`, `note`, `accepted_by`, `acknowledged_at` **nullable**; `status` `text` NOT NULL DEFAULT `'open'`; every timestamp `timestamp with time zone`.
2. **`test_the_sos_status_check_is_pinned`** — the highest-value test in the migration, because what it guards is a **future** edit: the day anybody adds a fifth status they collide with a pinned literal and a review instead of colliding with nothing. Read `pg_get_constraintdef` for `sos_alerts_status_check`.
   ⚠ **CAPTURE the literal by running it on the live 16.14 server. DO NOT TRANSCRIBE IT FROM THE SPEC.** Postgres deparses `IN (…)` into `= ANY (ARRAY[…])`, re-parenthesises, and schema-qualifies. F34's shipped note and F33's D2 both record that a literal which merely *looks* right pins nothing and reddens CI.
3. **`test_idx_sos_alerts_live_is_pinned`** — byte-identical from `pg_indexes.indexdef`, same capture rule. `WHERE status IN ('open','accepted') AND deleted_at IS NULL` comes back deparsed; the test **re-reads** rather than transcribes.
4. **`test_sos_alerts_carries_zero_non_primary_unique_indexes`** — `SELECT count(*) FROM pg_index WHERE indrelid = 'sos_alerts'::regclass AND indisunique AND NOT indisprimary` is **0**. **This is D2's decision expressed as an assertion.** A well-meaning `(tenant_id, raised_by) WHERE status='open'` added later would forbid the legitimate double page **and** would be defeated by NULL-distinctness in the common case (the shift-manager route, where the key is NULL) — and nothing else in the suite would fail.
5. **`test_every_tenant_id_table_has_forced_rls` stays green with NO EDIT** — one new `tenant_id` table. That test lives in `tests/test_tenant_isolation.py:203`; forgetting `enable_tenant_rls` fails **a different file**.
6. **`test_sos_alerts_migration_round_trips`** — upgrade applies, assert the end state; downgrade **via `_parent_of("sos alerts")`**, assert the table is gone; upgrade to head, re-assert. ⚠ **`_parent_of(marker)` (`:31`) and never `command.downgrade(cfg, "-1")`** — F36's shipped note records `test_migration_0017_round_trips` breaking *by being landed on* (`-1` downgraded the fitting-room tables and then asserted about customers). **F37 is the first migration to land on top of that helper and must prove it costs nothing (AC12).** Last in the file, in `try/finally`.

### The code

`00NN_sos_alerts.py`, the `0019_fitting_rooms.py` idiom: raw `op.execute` DDL, the module-level `_STANDARD` block, one `CREATE TABLE` exactly as D1 spells it, **one** index, `_updated_at_trigger("sos_alerts")`, and the trailing loop (`0008_bookings.py:107-110`):

```python
op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON sos_alerts TO app_user")
for statement in enable_tenant_rls("sos_alerts"):
    op.execute(statement)
```

> Forgetting `enable_tenant_rls` fails **a different file's** test. Forgetting the GRANT fails **nothing** until the app role touches the table — i.e. in Task 10, as `permission denied`.

**Comments that must be in the DDL, because the reader is a future feature:**
- `target_staff_user_id` carries **both** meanings of NULL in one sentence: *the shift-manager role*, **and** *a named colleague who turned out to be unreachable* — which is why the audit row carries the requested target and this column cannot (D3, D13).
- `idx_sos_alerts_live` states that its predicate is matched **exactly** by the poll's query so the planner uses it, and that **no history index ships** — F36's `idx_fitting_room_assignments_tenant_created` had **named readers**; this one would have none. One line for the upgrade path and its stated cost (`ACCESS EXCLUSIVE` on a table that will still be small).
- **`NO UNIQUE INDEX` is a decision and gets D2's argument in three lines**: the obvious `(tenant_id, raised_by, target_staff_user_id) WHERE status='open'` is defeated by NULL-distinctness in the *common* case and guards only the rare one — *an index that guards everything except the case it was written for is worse than none, because it is a guarantee a reviewer will believe.* The structural guarantee is the conditional UPDATE, which constrains a **transition** and not a **population**.
- `accepted_by` states that it is written by the **same statement** as `status`, so «accepted with nobody» is unrepresentable.
- `deleted_at` has **no v1 writer** and is in the index predicate for the same reason it is on every table — say so, so a reviewer looking for the missing route stops looking.

`downgrade()` is `DROP TABLE IF EXISTS sos_alerts` and nothing else (`0008:113-115`). **F37 touches no existing table, so it has nothing to un-touch.**

`models/sos_alert.py` declares **every** column explicitly as `mapped_column`, the `models/fitting_room_assignment.py` shape, `class SosAlert(StandardColumns, Base)`. `created_at` is **not** re-declared — it comes from `StandardColumns` with `server_default=text("now()")`, which is exactly why D6 says the two clocks differ and why Task 4's `db` test **seeds** `created_at` rather than relying on the default.

`models/constants.py` gains **`class SosStatus(StrEnum)`** (`OPEN`/`ACCEPTED`/`RESOLVED`/`CANCELLED`) beside `StaffCardStatus` (`:26`), and **four `AuditAction` members** — `SOS_RAISED`, `SOS_ACCEPTED`, `SOS_RESOLVED`, `SOS_CANCELLED` — after F36's four (`:325-335`). **No migration**: `audit_log.action` is plain `TEXT` with no CHECK (`0003_auth.py:71-79`), and this is the eighth block to rely on it. ⚠ **`SOS_ESCALATED` is DECLINED and the comment says why**: there is no escalation *event* — it is a predicate over a row and a clock, so there is no instant and no writer, and recording one from a read path is the write-on-read D6 rejects.

### Mutation-checks (mandatory — RUN them, do not reason about them)

| Mechanism | Remove it | Expect |
|---|---|---|
| `enable_tenant_rls("sos_alerts")` | delete the loop | `test_every_tenant_id_table_has_forced_rls` **RED**, naming the table, **in another file** |
| the `status` CHECK | drop the constraint | test 2 **RED** on a byte-identical comparison |
| `idx_sos_alerts_live`'s `WHERE` clause | make it a total index | test 3 **RED** |
| the zero-unique-index rule | add `(tenant_id, raised_by) WHERE status='open'` | test 4 **RED** (0 → 1). **It is the ONLY test that fails**, which is exactly its point |
| `downgrade` | make it `pass` | test 6 **RED** on the reverse assertion |
| `_parent_of` | swap to `command.downgrade(cfg, "-1")` | **stays GREEN today** and reds the day a later migration lands on it — **which is F36's shipped defect reproduced.** Run it, confirm the green, restore, and record the green in the docstring so nobody "simplifies" it back |

- **Done when**: `bash "<scratchpad>/run-db-tests.sh"` green (baseline + the new cases); `make lint` clean; `make test` green **with C12's single-head guard green**. `git show --stat` confirms the lowercase pathspecs landed.
- **Commit**: `feat(floor): the sos_alerts table, its pinned CHECK and index, and the SosAlert model`

## Task 2 — `SosAlertsRepository` and `SessionsRepository.has_live_session` (D1, D2, D3, D4, D5, D10)
`backend/app/db/repositories/sos_alerts.py` (**✚**), `backend/app/db/repositories/sessions.py`, `backend/tests/test_sos_repositories.py` (**✚**)

Every method takes `tenant_id` explicitly and puts it in the `WHERE` beside `deleted_at IS NULL` — the house defence-in-depth rule, on top of RLS.

### The failing tests first (`db`-marked, **run locally**)

**`SessionsRepository.has_live_session(session, tenant_id, staff_user_id, now)`** — ⚠ **it does not exist and this is new work on a SECOND repository** (verified: the shipped file carries `insert` `:11`, `active_by_token_hash` `:31`, `revoke_for_staff_user` `:44`, `revoke_by_token_hash` `:70`, and nothing else). `SELECT EXISTS(… WHERE tenant_id = :t AND staff_user_id = :s AND deleted_at IS NULL AND expires_at > :now)`. Cases: a fresh session → True; an **expired** session → False; a **revoked** (`deleted_at`) session → False; no session at all → False; **another tenant's** live session → False.
⚠ **Its docstring states what it PROVES, because the copy could be read as claiming more**: a live row proves **a session, not a screen**. `settings.session_ttl_seconds` is **12 hours** (`core/config.py:24`) and nothing revokes on going home — `revoke_for_staff_user` fires on a password change and on deactivation only. It is a cheap **upper bound** on reachability: `rerouted: false` claims only *"she has not signed out and her session has not expired"*, and `rerouted: true` is the case it genuinely closes. **The thirty-second escalation is the real safety net, not this read.**

**`SosAlertsRepository`** — the writers return the `(wrote, row)` shape F36's and F57's writers already use:
- **`insert(session, alert)`** — one plain `session.execute(insert(...))`. **No lock, no savepoint, no `ON CONFLICT`** (D2 — there is no index to violate, therefore no `IntegrityError` to recover from). ⚠ **Stated in the docstring because F36's claim has all three one file over and copying them here would be cargo**, and because `violated_index()` lives in the neighbouring module and is exactly the thing not to import.
- **`by_id(session, tenant_id, alert_id)`** — `tenant_id`, `id`, `deleted_at IS NULL`, **and NO `status` filter**, for `fitting_room_assignments.by_id`'s reason (`:119-132`): filtering on status here would make a losing accept read as *absent* and answer **404 instead of naming the owner**.
- **`accept(session, tenant_id, alert_id, actor_id, at)`** — the guarded `UPDATE … SET status='accepted', accepted_by=:actor, acknowledged_at=:at WHERE tenant_id=:t AND id=:id AND status='open' AND deleted_at IS NULL RETURNING id`, then **one `select(...).execution_options(populate_existing=True)` re-read, unconditionally** — `FittingRoomAssignmentsRepository._refreshed` (`:276-310`, the flag at `:308`) applied to this table, for the reason that docstring gives: *"whether a caller happened to load the row first is exactly the reasoning that has bitten this repo three times."*
- **`resolve(session, tenant_id, alert_id)`** — `… SET status='resolved' WHERE … AND status IN ('open','accepted') …`, same re-read.
- **`cancel(session, tenant_id, alert_id)`** — `… SET status='cancelled' WHERE … AND status='open' …`, same re-read.
- **`live_for(session, tenant_id, actor)`** — D10's ONE statement with **five LEFT JOINs**, driving from `sos_alerts`, ordered `created_at ASC` (oldest first — the overlay and the centre must agree). Every predicate is written out because this schema has no FK constraints:

  | Join | Predicate | Test that fails without it |
  |---|---|---|
  | `sos_alerts` (driving) | `tenant_id = :t AND deleted_at IS NULL AND status IN ('open','accepted')` + D7's audience clause | matches `idx_sos_alerts_live` exactly, so the planner uses it |
  | → `staff_users` (raiser) | `tenant_id = :t AND id = raised_by` — **no `deleted_at` filter** | `test_a_removed_raiser_still_names_the_page` |
  | → `staff_users` (target) | `tenant_id = :t AND id = target_staff_user_id` — no `deleted_at` filter | same rule |
  | → `staff_users` (acceptor) | `tenant_id = :t AND id = accepted_by` — no `deleted_at` filter | it is what makes D4's `details`-less branch rare rather than routine |
  | → `fitting_room_assignments` | `tenant_id = :t AND id = fitting_room_assignment_id AND deleted_at IS NULL` — **no `released_at` filter** | `test_a_released_assignment_still_resolves_its_room_label` |
  | → `fitting_rooms` | `tenant_id = :t AND id = assignment.fitting_room_id` — **NO `deleted_at` filter** | same test's second half. **F36's Risk 1(c), decided there and handed here verbatim**: a room label is not personal data, so D9's no-snapshot rule does not reach it |

  All five are **LEFT**, so an alert whose every pointer has been swept still renders, with `raised_by_name: null`, `room_label: null`, and a card that says so.

- **`assignment_of(session, tenant_id, assignment_id, staff_user_id)`** — D3 step 3's room-pointer read: `tenant_id`, `id`, **`staff_user_id = :actor`**, `deleted_at IS NULL`, **and no `released_at` filter**. ⚠ **The `staff_user_id` conjunct is not tidiness**: without it any of the five roles could raise with any assignment id in her own tenant, and F36's floor payload hands every one of them out (`RoomAssignment.id` is on every occupied tile). The page would then render «דנה קוראת לעזרה — חדר 2» while Dana is standing in room 4. **«No room» is a defined, safe state; «wrong room» is not, and in an emergency it is strictly worse** — the responder walks to a closed curtain with a stranger's bride behind it.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| `expires_at > :now` in `has_live_session` | drop the conjunct | the expired-session case **RED**. **This is AC2's mechanism and Task 5 pins it end to end** |
| `deleted_at IS NULL` in `has_live_session` | drop it | the revoked-session case **RED** |
| the `staff_user_id` conjunct in `assignment_of` | drop it | `test_another_staffers_assignment_does_not_resolve` **RED**. **Nothing else in the feature fails** — the alert is still created either way, which is exactly why the test exists |
| `populate_existing=True` on the three re-reads | drop the flag | **stays GREEN here** — every test in this module opens a fresh session, so the identity map is empty and the flag is a no-op. **Record that in the docstring** and pin it in Task 6's forced interleave. F57's shipped note records exactly this discovery |
| the explicit `tenant_id` predicate | drop it (RLS still on) | stays **green** — RLS carries it. **Record that in the docstring** rather than pretending the unit test proves the defence-in-depth; it is proven in Task 10 |
| the `staff_users` joins' *absence* of a `deleted_at` filter | add one | `test_a_removed_raiser_still_names_the_page` **RED** |
| the `fitting_rooms` join's *absence* of a `deleted_at` filter | add one | `test_a_released_assignment_still_resolves_its_room_label` **RED** |

- **Done when**: local db suite green; `make lint` clean; the two "stays green" mutations performed, recorded in docstrings and restored. `git show --stat`.
- **Commit**: `feat(floor): the sos_alerts repository, the five-join live read and the reachability probe`

## Task 3 — Validation, schemas, the two 409 codes, the two renames, the two handlers (D1, D10, D14)
`backend/app/floor/validation.py`, `backend/app/floor/schemas.py`, `backend/app/main.py`, `backend/tests/test_floor_validation.py`, `backend/tests/test_floor_api.py`, `backend/tests/test_frontend_constant_parity.py`, `frontend/apps/manage/src/validation.ts`

### The failing tests first (**fast**, no Postgres)

**`test_floor_validation.py` (extended)** — `note` stripped; `""` → `None`; whitespace-only → `None`; `MAX_SOS_NOTE_LENGTH` (**120**) boundary and 121 → `SosValidationError`; `target_staff_user_id == actor.id` → `SosValidationError`.

**`test_frontend_constant_parity.py`** — **one name** added to the existing `id="manage-floor"` param (`:109-110`): `("MAX_ROOM_LABEL_LENGTH", "MAX_SOS_NOTE_LENGTH")`. ⚠ **`ESCALATION_AFTER` and `STALLED_AFTER` are deliberately NOT mirrored** — the client never computes them, it renders booleans the server derived, and after the copy deck's rule 5 the client carries **no number at all**. Mirroring a number nothing computes is parity theatre.

**`test_floor_api.py` (extended, the bodies written here and walked in Task 9)** — `SOS_ALREADY_ACCEPTED` **with** `details`, `SOS_ALREADY_ACCEPTED` **without** (the key **absent**, never null), `SOS_CLOSED` (**never** `details`), **plus a companion assertion that no OTHER body in `main.py` grew a `details` key** — the set of dynamic bodies is a thing a reviewer should be able to enumerate.

### The code

- `app/floor/validation.py` — `MAX_SOS_NOTE_LENGTH = 120`, `normalize_sos_note`, `SosValidationError(DomainValidationError)`, and **the two renames**:
  - **`_OccupiedError` → `_DetailedConflictError`** (`:43`), keeping its whole docstring **including the load-bearing sentence** that it is deliberately **not** a `DomainValidationError` subclass *"because Starlette resolves a handler by walking `type(exc).__mro__`"* — parenting a 409 onto the domain-400 base makes the shipped handler answer 400 and leaves the 409 handlers unreachable. `RoomOccupiedError` (`:64`) and `StaffOccupiedError` (`:70`) are unchanged subclasses; **`SosAlreadyAcceptedError`** (optional `details`) and **`SosClosedError`** (never `details`) join them.
- `app/main.py` — **`_occupied_body` → `_body_with_details`** (`:350`), a one-line rename plus **four** call sites (`:1176`, `:1180`, and the two new ones), no behaviour change. It already does exactly the right thing: copies a frozen module constant (*"stamping `details` onto it would leak one boutique's staffer name into the next tenant's 409"*, `:354-357`) and adds `details` only when truthy (`:363-365`). Two new frozen bodies beside `ROOM_OCCUPIED_BODY` (`:339`) / `STAFF_OCCUPIED_BODY` (`:342`), **two new imports at `:82`, and TWO new `@app.exception_handler` blocks beside `:1174`/`:1178`.**
  ⚠ **`main.py` REGISTERS HANDLERS PER CONCRETE CLASS, NEVER PER BASE** — verified, there is no `_OccupiedError`/`_DetailedConflictError` base handler anywhere. Without both blocks the 409s answer **500**. `SPEC_ERROR_CODES`' set equality catches it on the first run, so this is **cost, not risk** — but it is cost that has to be in the plan.
- `app/floor/schemas.py` — `RaiseSosRequest(ForbidExtraModel)` (`target_staff_user_id`, `fitting_room_assignment_id`, `note`, all optional), `SosAlertView`, `SosResponse` (`alerts`, **`server_now`**), `RaisedAlert` (`alert`, `rerouted`). The three action routes take **no body** (`release_assignment`'s shipped docstring, same reasoning).
  ⚠ **D10's sentence goes here, in the register of the three comments F36 rewrote**: *"The SOS payload carries staff names and a room label. It carries no customer datum of any kind, and the app-level poll is exactly why."* So the next feature to extend this payload meets the **reason** rather than the absence.
  ⚠ **The raise's asymmetry is justified in a comment, not left convenient**: every mutation answers the same `SosAlertView`; the raise alone answers `{alert, rerouted}`, **because `rerouted` is a fact about *this request*, not about the row** — nobody reading the alert later can know whether `target_staff_user_id IS NULL` means "she asked for the shift manager" or "she asked for Dana and Dana was logged out". *Declined: letting the console infer it by comparing what it sent with what came back — correct today, and exactly the kind of implicit contract that survives one refactor.*
- `frontend/apps/manage/src/validation.ts` — `MAX_SOS_NOTE_LENGTH`, mirrored.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| either 409 handler registration | drop one block | that code's body test **RED** as a bare 500. ⚠ **Run BOTH** — the two are independent registrations and one missing is the exact shape `violated_index`'s docstring records for F36 |
| `_DetailedConflictError`'s non-`DomainValidationError` parentage | make it subclass `DomainValidationError` | **both** 409 tests **RED as 400s**, because Starlette walks `__mro__` and the shipped domain handler wins. Run it once, deliberately, and restore — it is the only proof the docstring's sentence is live |
| optional `details` | make it a required key | Task 6's `test_an_accept_whose_winner_was_removed_does_not_name_nobody` **RED** (recorded here, run there) |
| `SOS_CLOSED` never carrying `details` | add the key | the "no other body grew `details`" companion assertion **RED**. **Three of four codes with the key is the drift F36's Risk 8 warns about; four would be the default** |
| the `MIRRORS` name | delete it, then change one side of the constant | the parity test must go **RED**; confirm it does |

- **Done when**: `make lint` + `make test` green. **First milestone**: the whole wire contract, both new codes and both handlers exist with no Postgres. `git show --stat`.
- **Commit**: `feat(floor): the sos wire shapes, the two conflict codes and the two shipped helpers they rename`

## Task 4 — **The read-time predicates**: `_escalated`, `_stalled`, `_for_me` and the audience clause, with an INJECTED CLOCK (D6, D7 / C11)
`backend/app/floor/service.py`, `backend/tests/test_sos_service.py` (**✚**), `backend/tests/test_sos_db.py` (**✚**)

**This is the task the ruling is written against.** Read D6 and D7 before writing a line.

### The failing tests first — **fast, pure branches, no database at all**

That the whole escalation design is unit-testable with no Postgres **is the argument for computing it in Python**, and it is why this task is separate from the four verbs.

- **`_escalated`** (AC5) — 29 s → False; 31 s → True; **exactly 30.000 s → True** (the `>=` boundary, which is the whole of the ruling and which no other test lands on); `status='accepted'` → False; `acknowledged_at` set → False; **`created_at > server_now` (negative delta) → False**.
  ⚠ **There is NO `max(timedelta(0), …)` clamp and its absence is a decision, not an omission.** `lib/elapsed.ts` clamps because `elapsedMinutes` returns a **rendered number** and a negative delta ships «כבר -1 דק'» to a screen. This returns a **boolean against a one-sided positive threshold**: `timedelta(seconds=-5) >= timedelta(seconds=30)` is already `False`, **byte-identical to the clamped result**. The spec review ran the "drop the clamp" mutation and it came back **GREEN** — which is exactly the false confidence the mutation regime exists to catch. **The negative-delta case stays an ASSERTION and is not a mutation target**, and the docstring says so.
- **`_stalled`** (AC5, AC26) — accepted 1 min ago → False; 3 min ago → True; exactly `STALLED_AFTER` → True; an **open** alert → False; `acknowledged_at is None` → False.
- **`_for_me`** (AC6) — the **full matrix** over {raiser, named target, other floor role, shift manager, owner} × {role-targeted, name-targeted} × {escalated, not} × {open, accepted-fresh, accepted-stalled, resolved, cancelled}. The rows that carry weight:
  - the **raiser** is False on every row, **including when her own page escalates and including when it stalls**;
  - the **named target** is True while `open`, whatever `escalated` says;
  - an **elevated** caller is True on a role-targeted open alert from t=0, and on a name-targeted one **only once `escalated`**;
  - an **elevated** caller is True on an **accepted-and-stalled** row — **the row that makes the accept path non-silent**;
  - everybody else is False.
  ⚠ **`ELEVATED_ROLES` is `frozenset({OWNER.value, SHIFT_MANAGER.value})` — STRING values (`service.py:69`, verified).** `actor.role in ELEVATED_ROLES` compares a string; a test constructing a `StaffContext` with an enum member would pass vacuously against a wrong implementation. Build the fakes from `.value`.
- **the audience clause** — an elevated caller gets **no extra predicate at all** (faster and clearer than binding a boolean into SQL); a non-elevated caller gets `or_(raised_by == actor.id, target_staff_user_id == actor.id, accepted_by == actor.id)`.

### The `db` half — **and BOTH operands are frozen**

⚠ **`FloorService.__init__` already takes `clock: Callable[[], datetime] | None = None` (`service.py:165`, `:177`, verified — C11), with four shipped readers.** Construct the service under test as `FloorService(..., clock=lambda: FIXED)` and seed `created_at = FIXED - timedelta(seconds=29)` / `FIXED - timedelta(seconds=31)`, and `acknowledged_at = FIXED - timedelta(minutes=1)` / `FIXED - timedelta(minutes=3)`.

**Both operands then come from the same frozen instant and the margin is exact rather than one second.** Left the other way — seed `created_at`, let the wall clock supply `server_now` — the not-escalated assertion flips to escalated as soon as ~1 s elapses between the seed and the read, i.e. a Postgres round trip plus session setup on a loaded CI box, **and a test that goes green or red on machine speed will be re-run until it passes, which is how a mutation regime rots.**

What a `db` test genuinely cannot freeze is `server_default=text("now()")` — **which is precisely why `created_at` is SEEDED** (the default applies only when the column is omitted). The service clock is a constructor argument.

### The code

`ESCALATION_AFTER = datetime.timedelta(seconds=30)` and `STALLED_AFTER = datetime.timedelta(minutes=2)` as module constants in `service.py`, plus the three pure functions exactly as D6 and D7 spell them, plus the conditional audience clause built in Python.

**The ⚠ TWO CLOCKS comment goes on `_escalated`**: `created_at` is the **database** host's transaction-start time; `server_now` is the **service's** Python clock — the same instant that goes on the wire and that `elapsedLine` anchors on. The skew is NTP-bounded and irrelevant against a 30-second threshold read every 2 seconds.

**`_stalled`'s docstring carries the whole of why it exists**, because a reader will otherwise delete it as scope creep: `_escalated` short-circuits on `status != OPEN` and `_for_me` returns False for any non-open row, so **the instant anybody taps «אני מגיעה» the alert stops escalating and stops rising on every device in the boutique, forever.** There is no auto-resolve, no un-accept verb and no second threshold. **And it is worse than silence, because the raiser's screen reads «דנה מגיעה»: she stops looking for help on a signal the product cannot back.**

**The worker's rejection is recorded on the constants, in three lines**, because the alternative looks tempting: `app/worker.py` ticks at 60 s (`config.py:124`, `worker.py:157`), so a worker-stamped escalation would arrive **up to a full minute late — twice the requirement**; it would introduce a **write that races a concurrent ack**; and it would run `O(tenants)` queries per tick **even when no boutique in the country has an open alert**. The read-time predicate adds zero latency beyond the poll, cannot race anything because it writes nothing, and is the house compute-on-read pattern (#30's queue positions, F43's ordinals, `card_status()` `:80`).

**Python rather than SQL, and the decisive argument is the SHARED ANCHOR.** The alternative — `(status='open' AND created_at <= now() - interval '30 seconds') AS escalated` — is *more* correct about clocks and *less* correct about the screen: the elapsed line is computed against `server_now`, so a SQL-side predicate against `now()` could render an escalated badge beside «כבר 0 דק'». **One instant decides both, or the overlay disagrees with itself.**

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| `>=` on the escalation threshold | change to `>` | the **exactly-30.000 s** case **RED**. The boundary is the whole of the ruling and no other test lands on it |
| `row.status != SosStatus.OPEN` in `_escalated` | drop the conjunct | the accepted-never-escalates case **RED**. ⚠ **Two of the predicate's three clauses are genuinely unmutatable** — `acknowledged_at is not None` is already implied by `status == 'open'`, and D6 concedes it — **so only this guard and the threshold are pinned, and saying so is better than a table implying three** |
| the `max(timedelta(0), …)` clamp | *(there is none)* | **the mutation is DELETED from this plan.** It came back GREEN in spec review because `timedelta(seconds=-5) >= timedelta(seconds=30)` is already False. The negative-delta case is an **assertion** |
| **`_stalled`, or its branch in `_for_me`** | delete either | `test_an_accepted_alert_unresolved_for_two_minutes_re_rises_for_the_shift_manager` **RED — the ONLY test that fails.** Every other test accepts and then resolves. Without it an accepted alert stops rising **on every device in the boutique, forever**, and the raiser's screen still reads «דנה מגיעה» (AC26) |
| `_for_me`'s raiser-first branch | move it below the `ACCEPTED` branch | the **raiser's own stalled page** row **RED** — she would get a full-screen overlay for the emergency she reported |
| the audience clause | drop the `or_(...)` for non-elevated callers | Task 9's `test_a_seamstress_sees_only_her_own_pages` **RED** (recorded here, run there) |
| `ELEVATED_ROLES` compared against `.value` | build the fake's role from the enum member | the elevated rows **RED** — run it once to prove the fakes are not lying |

- **Done when**: `make lint` + `make test` green; the `db` escalation/stall rows green under the frozen clock; every mutation performed and restored. **Second milestone**: the 30-second boundary and the whole `for_me` matrix are proven **without sleeping and without a database**. `git show --stat`.
- **Commit**: `feat(floor): the read-time escalation and stall predicates, the for_me matrix and the audience clause`

## Task 5 — **VERB 1 of 4: RAISE**, and it has exactly three failure modes (D3, D13)
`backend/app/floor/service.py`, `backend/tests/test_sos_service.py`, `backend/tests/test_sos_api.py` (**✚**), `backend/tests/test_sos_db.py`

### The failing tests first

**Fast (`test_sos_api.py`, `test_sos_service.py`)** — **`test_nothing_about_the_boutique_can_refuse_a_page`**, a table walk over: no room · a deleted room · a released assignment · a foreign-tenant assignment id · **an assignment belonging to ANOTHER staffer** · an unknown target staff id · a logged-out target · a deleted target · **an alert already open by the same raiser**. **Every row answers `200` with an alert.**
⚠ **`200`, pinned as `assert resp.status_code == 200` on every row**, not "201/200": **no route on this router declares `status_code=`** — verified, `create_room` (`router.py:183`) is the shipped create precedent and answers 200 — and an ambiguous expected status on a table-driven walk is a first-run CI red on the one assertion that encodes «a page is never silently dropped».

Plus: `ForbidExtraModel` answers **400** to a body carrying `raised_by` (⚠ **asserted, not asserted-in-prose**); a note of 121 characters is **400**; `target_staff_user_id == actor.id` is **400**; and the three failure modes are **exhaustive** — 401 (no session), 403 (a role outside the five, impossible for a signed-in staffer since the router admits all five), 400.

**`db` (`test_sos_db.py`)** — `test_a_logged_out_target_is_rerouted_to_the_shift_manager`: the alert is created with `target_staff_user_id IS NULL`, the response carries `rerouted: true`, and the `SOS_RAISED` audit row carries **both** `requested_target` (the named colleague) and `target` (`null`). And `test_another_staffers_assignment_stores_null_and_the_alert_is_still_created` (AC1's sharpest row).

### The code — ordered exactly

1. **Validate.** `note` stripped, `""` → `None`, `len <= MAX_SOS_NOTE_LENGTH` else 400. `target_staff_user_id == actor.id` → 400 «אי אפשר לקרוא לעצמך.» — a self-page has no audience and would sit open forever escalating to the shift manager for nothing.
2. **`raised_by = actor.id`, full stop.** ⚠ **There is NO `_authorize` call on this route and its absence is the design, not an omission.** `_authorize`'s docstring (`service.py:794-805`) names the hazard as *a body-supplied `staff_user_id` doubling as the caller's identity*; the raise body carries a **target**, never an actor. **Nobody may raise a page AS somebody else — not even an owner** — because an SOS is a first-person statement, and an owner who needs help raises her own.
3. **Resolve the room pointer, permissively — and it must be HER OWN assignment.** `assignment_of(tenant_id, id, staff_user_id=actor.id)` (Task 2). **Unresolved → store `NULL` and carry on.** A stale room pointer must never refuse a page; RLS makes a foreign tenant's id simply not resolve, so there is no leak and no oracle.
4. **Resolve the target, permissively — THE NO-ON-SHIFT-TARGET CASE.** A named target must resolve to a live `staff_users` row **and** hold a live session (`has_live_session`, Task 2). If **either** check fails, the alert is created with `target_staff_user_id = NULL` — **routed to the shift manager in the data and not merely in the UI** — and the response carries `rerouted: true`.
   **Why the role audience can never be empty, with the citation**: a NULL target routes to `ELEVATED_ROLES = {owner, shift_manager}` (`service.py:69`), and `auth/staff.py:9-34` holds the **last-owner invariant — "at least one live owner"** — under an advisory lock, precisely because *"No unique index can express it."* **This is the property that makes the epic's "with no on-shift staffer in the requested role" unreachable for the role target and real only for a named one**, which is exactly why step 4 is where the requirement is discharged.
5. **INSERT.** One statement. **No lock, no savepoint** (D2).
6. **Audit `SOS_RAISED`** in the same transaction, before commit, carrying `{"alert", "requested_target", "target", "rerouted", "assignment"}`. ⚠ **The `requested_target`/`target` PAIR is the whole point**: the reroute writes `NULL` into the column, destroying the only record of whom she actually tried to page — the `previous_break_started_at` argument (F57's D8) and the handover `from` argument (F36's D8), **third instance**.
7. **Answer** `{alert, rerouted}`.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| the permissive room fallthrough | raise 404 when the assignment does not resolve | four rows of `test_nothing_about_the_boutique_can_refuse_a_page` **RED**. This is «never silently dropped» mechanised |
| **`expires_at > :now` in the reachability read** | drop the conjunct | `test_a_logged_out_target_is_rerouted_to_the_shift_manager` **RED**. An expired session then reads as live, the page is stored against a staffer whose cookie is dead, and it reaches **nobody** until the 30-second escalation — the exact silent drop this feature forbids. **Every test whose target has a fresh session stays green** |
| the `staff_user_id` conjunct on the room pointer | drop it | `test_another_staffers_assignment_stores_null_and_the_alert_is_still_created` **RED** — and the alert is still created either way, which is why nothing else fails |
| `requested_target` on the audit row | drop the key | the reroute audit test **RED**. Nothing on any screen would ever say Dana was meant to get it |
| `ForbidExtraModel` on the raise body | swap to a permissive model | the `raised_by`-in-body test **RED**. ⚠ **Run it** — this is the one shape `_authorize`'s docstring names as *the* hazard |
| the self-target 400 | drop the check | the self-target row **RED**, and the alert would sit open escalating to the shift manager for nothing |

- **Done when**: `make lint` + `make test` green; the two `db` rows green locally; every mutation performed and restored. `git show --stat`.
- **Commit**: `feat(floor): the raise, its three failure modes and the reroute that leaves evidence`

## Task 6 — **VERB 2 of 4: ACCEPT**, first-accept-owns as a forced interleave (D4)
`backend/app/floor/service.py`, `backend/tests/test_sos_service.py`, `backend/tests/test_sos_db.py`

**This is the task the ruling's «first-accept-owns, expressed structurally» is written against.**

### The failing tests first

**Fast** — the target and elevated callers allowed; **everybody else 404 and the repository is never called past the read** (the assertion that proves the refusal is not an existence oracle); the **raiser** may not accept her own page; the `(wrote, row)` mapping onto 200 / 200-unchanged / 409 / 404; an audit row on a write and **none** on a no-op.

**`db` — the forced interleave.** ⚠ **F37's races are UPDATE races, so they copy `test_a_second_start_landing_in_the_gap_renders_the_winners_timestamp` (`test_floor_db.py:266`) and NOT F36's INSERT shape.** `asyncio.gather` is **deliberately not used** for any deterministic branch, for the reason `test_floor_db.py:251-263` states verbatim: gather does not **order** two transactions, so the loser most often runs after the winner commits and the branch goes green without the mechanism ever being exercised. The mechanism is that `tenant_session` is `async with session_factory() as session, session.begin()`, so **exiting the context manager IS the commit** (`db/tenant.py:25`), and two nested `tenant_session`s on one `NullPool` factory take two separate connections.

**The ORDER**: the **loser** opens its session and **READS** (a plain SELECT, no row locks) → the **winner's inner `async with` opens, writes and EXITS, which is the commit** → only then does the loser issue its guarded UPDATE, **which matches zero rows immediately**. **Nothing ever blocks and nothing can hang** — F36's Rejected Finding worried about the INSERT variant and does not apply here at all, because a guarded UPDATE against a committed row **returns** rather than waiting.

⚠ **The seed rule applies verbatim: every row this module COMMITS holds `owner` or `shift_manager`, never a floor role** (`test_floor_db.py:10-32`). `migrated_db` is session-scoped, pytest collects alphabetically, and a committed `reception` row reddens three tests in `test_migrations.py` that have nothing to do with SOS. Nothing here asserts anything about the actor's role — the gate is Tasks 4 and 9's job.

### The code — ordered exactly, and the ORDER is the guarantee

1. **Read the alert** — `tenant_id`, `id`, `deleted_at IS NULL`, **no `status` filter** (Task 2's `by_id`).
2. **Absent, or not visible under D7's audience rule → 404.** Not a 403: whose alert it is can only be learned by reading it, so a 403 on a real id and a 404 on a fake one would discriminate existence.
3. **Not permitted → 404, byte-identical.** Permitted = `actor.id == target_staff_user_id` **or** `actor.role in ELEVATED_ROLES`. The **raiser** may not accept her own page — she has resolve and cancel.
4. **⚠ IDEMPOTENCE FIRST, keyed on the request.** `status == 'accepted' AND accepted_by == actor.id` → **200 with the existing alert, no audit row, no write.** She tapped twice, or two of her devices did. **It must be resolved BEFORE the 409 or a double-tap tells her, by name, that SHE has it, as an error.**
5. **The conditional UPDATE** (Task 2's `accept`). Rowcount 1 → audit `SOS_ACCEPTED` `{"alert", "raised_by"}` → 200 with the re-read row.
6. **Rowcount 0 → discriminate on the CURRENT status** — the only discriminator this feature has, because there is no index and therefore no constraint name (D2):

| Current status | Answer | Code | `details` |
|---|---|---|---|
| `accepted`, by somebody else | **409** | `SOS_ALREADY_ACCEPTED` | `{"staff_display_name": …}` |
| `accepted`, by somebody whose staff row is gone | **409** | `SOS_ALREADY_ACCEPTED` | *(key ABSENT)* |
| `resolved` or `cancelled` | **409** | `SOS_CLOSED` | *(never)* |
| `open` | **`else: raise`** | — | — |

⚠ **The unreachable branch is genuinely unreachable and must still have an `else: raise`.** F41's review found the same shape and recorded why: *"a zero-row UPDATE TAKES NO LOCK and the repo runs READ COMMITTED"*, so a concurrent write can move the row between the UPDATE and the re-read — but nothing moves a row **back** to `open`, and `uuid_generate_v4()` makes delete-and-recreate-with-the-same-id impossible. **It is spelled as `else: raise` rather than as a comment claiming impossibility, because F41's finding was exactly that an "impossible" branch with no `else` returns `None` and 500s with no message.**

⚠ **`acknowledged_at` comes from `FloorService`'s injectable clock, not SQL `now()`** (C11), so the `db` suite freezes it and asserts an equality rather than a range — the shipped shape one method over (`FittingRoomAssignmentsRepository.release`'s `at` parameter).

### Mutation-checks (mandatory)

| Test | Mutation that MUST turn it red | Why nothing else catches it |
|---|---|---|
| `test_a_second_accept_landing_in_the_gap_is_refused_and_names_the_owner` | **drop `AND status = 'open'` from the accept's UPDATE predicate** | every other accept test accepts once. Without the conjunct the loser **overwrites the winner**: `accepted_by` flips to the second responder, the first is never told, and **two people walk to one curtain while a third emergency goes unanswered.** The ONLY test that fails |
| ″ | **remove `populate_existing=True` from the accept's re-read** | every test that opens a **fresh** session per operation has an empty identity map, so the flag is a no-op there — F57's shipped note records exactly this. **The loser would render ITS OWN `accepted_by` and the 409 would name the wrong person** |
| ″ | **resolve idempotence AFTER the 409 instead of before** | a re-accept by the current owner then answers `409 «דנה כבר מגיעה»` **to דנה**. Every single-accept test stays green (F36's D6, same trap, same ordering rule) |
| `test_an_accept_whose_winner_was_removed_does_not_name_nobody` | **make `details` a required key** | the path then either raises building the body or ships `{"staff_display_name": null}` and the console renders an empty interpolation. Every other 409 test has an owner to read |
| `test_a_refused_accept_is_a_404_and_never_reaches_the_writer` | **move the permission check after the UPDATE** | the repository-never-called assertion **RED**, and a stranger's accept would silently succeed |
| `test_a_re_accept_by_the_owner_writes_no_audit_row` | **write the audit row unconditionally** | the no-op audit assertion **RED** |

**⚠ EVERY ONE OF THESE MUST BE RUN, NOT REASONED ABOUT.** F34, F57 and F36 each found a real vacuous test this way. **A test whose named mechanism can be removed with the suite still green is VACUOUS and must be rewritten**, not shipped with a note.

- **Done when**: local db suite green; every mutation performed and restored, each result recorded. `make lint` clean. `git show --stat`.
- **Commit**: `feat(floor): the accept, first-accept-owns as one conditional UPDATE, and the 409 that names the owner`

## Task 7 — **VERB 3 of 4: RESOLVE**, and rowcount 0 is not an error (D5, D13)
`backend/app/floor/service.py`, `backend/tests/test_sos_service.py`, `backend/tests/test_sos_db.py`

### The failing tests first

**Fast** — permitted = the raiser, the acceptor **or** elevated; everybody else **404, byte-identical to missing**; the four-row discriminator; an audit row on a write and **none** on a no-op.

**`db`** — `test_a_resolve_records_the_state_it_destroys` and `test_a_resolve_landing_after_a_resolve_writes_nothing`.

### The code — D4's SIX-STEP ORDER, and its own discriminator table

⚠ **Prose was not enough here and the spec says why**: an earlier draft stated *"rowcount 0 with a live row back is a 200"* and, one paragraph later, *"cancelling an ACCEPTED alert is a 409"* — **and cancel-of-accepted IS rowcount 0 with a live row back**, so the two rules disagreed on the same input with no stated precedence. **The table is the rule; the prose below it is the reason.**

Ordered: **read (no `status` filter) → visibility 404 → permission 404 → conditional UPDATE (`status IN ('open','accepted')`) → rowcount-0 discriminator.** ⚠ **The permission check PRECEDES the discriminator**, and that ordering is load-bearing: a 409 carrying `{"staff_display_name": "דנה"}` handed to a caller who may not act would leak a staff name the 404-not-403 rule exists to withhold.

| Current status | Answer | Audit |
|---|---|---|
| `resolved` | **200** with the row | none |
| `cancelled` | **200** with the row | none |
| no row | **404** | none |
| `open` / `accepted` | unreachable → **`else: raise`** | — |

**Rowcount 0 with a live row back is a 200 and writes no audit row.** She wanted it closed; it is closed. F36's D7 rule (*"She wanted the room free; the room is free"*) and F34's D8 no-op rule, applied to a state machine instead of a timestamp.

**`SOS_RESOLVED` carries `{"alert", "from_status": "open"|"accepted"}`, ⚠ CAPTURED INTO A LOCAL BEFORE THE WRITER RUNS** — `FloorService.end_break`'s (`:268-269`) and `handover`'s (`:481`) ⚠ comments verbatim: the UPDATE is ORM-enabled DML whose `evaluate` synchronization stamps `'resolved'` onto the same identity-mapped instance out of one identity map, so reading it afterwards records `resolved → resolved` and **empties the row of its whole informational content**. **This is the identity-map trap's fourth appearance in this repo and the only one where the destroyed value is a state rather than a timestamp.**

**«did anybody answer?» is answerable from the pair `SOS_RAISED` / `SOS_ACCEPTED`** without a `resolved_at` column, which is D1's argument for not shipping one.

*Declined "anyone may resolve any alert": closing somebody else's open emergency is the one destructive act on this surface, and the elevated path already covers the legitimate case (a shift manager clearing up after a page that resolved itself).*

### Mutation-checks (mandatory)

| Test | Mutation that MUST turn it red | Why nothing else catches it |
|---|---|---|
| `test_a_resolve_records_the_state_it_destroys` | **move the `from_status` capture AFTER the writer** | ⚠ **F57's shipped note records this precise mutation leaving ALL fast tests green**, because monkeypatched repositories never stamp anything. **Only a real session's identity map poisons the local**, and the audit row silently becomes `resolved → resolved`. **The mutation check for this line HAS to be a `db` test and cannot be anything else** |
| `test_a_resolve_landing_after_a_resolve_writes_nothing` | **treat rowcount 0 as a 404** | she wanted it closed and it is closed; the second resolver would get an error for being right. **No other test issues two resolves** |
| ″ | **write the audit row on the no-op branch** | the audit-count assertion **RED** |
| `test_a_stranger_cannot_resolve` | **drop the acceptor from the permitted set**, or widen it to anyone | one of the two **RED** — run both directions, because a permission set is wrong in two ways and a single-direction test pins one |
| the `else: raise` | replace with `return None` | the unreachable-branch test **RED** as a 500 with no message — F41's finding, reproduced deliberately once |

- **Done when**: local db suite green; every mutation performed and restored. `make lint` clean. `git show --stat`.
- **Commit**: `feat(floor): the resolve, its no-op 200 and the audit row that carries the state it destroys`

## Task 8 — **VERB 4 of 4: CANCEL**, and the asymmetry with resolve is the point (D5)
`backend/app/floor/service.py`, `backend/tests/test_sos_service.py`, `backend/tests/test_sos_db.py`

### The failing tests first

**Fast** — permitted = the raiser **or** elevated (⚠ **not the acceptor** — she has resolve); everybody else 404; the five-row discriminator.

**`db`** — `test_a_cancel_racing_an_accept_never_strands_the_responder`, the second forced interleave, same UPDATE shape as Task 6.

### The code — D4's six-step order, `status = 'open'` ONLY, and its own table

| Current status | Answer | `details` | Audit |
|---|---|---|---|
| `accepted` | **409 `SOS_ALREADY_ACCEPTED`** | `{"staff_display_name": …}`, **optional** (D4's rule) | none |
| `cancelled` | **200** with the row | — | none |
| `resolved` | **200** with the row | — | none |
| no row | **404** | — | none |
| `open` | unreachable → **`else: raise`** | — | — |

⚠ **Cancelling an ACCEPTED alert is a 409 naming the acceptor, and that asymmetry with resolve is the point.** A colleague is already walking to that curtain. **Silently cancelling would send her to an empty room and teach her that accepting means nothing — the exact erosion this feature exists to prevent.** The raiser's remedy is one word over: **resolve**, which is what actually happened («she sorted it, the responder can stand down»), and the copy says so («{{name}} כבר מגיעה. אפשר לסמן «נפתר» במקום.»). **The 409 reuses D4's code, its optional `details` and its Hebrew, so this costs no new error and no new sentence.**

**A second cancel of an already-cancelled alert is a 200 with no audit row and has its own AC** (AC9).

### Mutation-checks (mandatory)

| Test | Mutation that MUST turn it red | Why nothing else catches it |
|---|---|---|
| `test_a_cancel_racing_an_accept_never_strands_the_responder` | **widen cancel's predicate to `status IN ('open','accepted')`** | the cancel then succeeds against an accepted alert, **the 409 never fires, and a colleague walks to a curtain for an emergency that was cancelled behind her.** Every sequential cancel test stays green |
| `test_a_second_cancel_is_a_200_with_no_audit_row` | treat rowcount 0 as a 404 | **RED** (AC9) |
| `test_a_cancel_after_accept_names_the_acceptor` | **move the permission check AFTER the discriminator** | a caller who may not act receives `{"staff_display_name": "דנה"}` — assert the 404 path carries **no** name. ⚠ **This is the one ordering rule in D5 whose violation LEAKS rather than errors** |
| ″ | **make `details` required** | the `details`-less cancel-after-accept variant **RED** — the path `copy.md` added `sos.error.cancelAfterAcceptUnknown` for |

- **Done when**: local db suite green; every mutation performed and restored. `make lint` clean. `git show --stat`.
- **Commit**: `feat(floor): the cancel, its open-only predicate and the 409 that points at «נפתר»`

## Task 9 — Five routes on the existing floor router, and the two tables that are sized from D9 (D9, D10, D14)
`backend/app/floor/router.py`, `backend/app/floor/service.py`, `backend/tests/test_floor_api.py`, `backend/tests/test_sos_api.py`, `backend/tests/test_staff_role_gating.py`

### The failing tests first (**fast**)

**`test_floor_api.py`** — `FLOOR_OPEN_ROUTES` grows **nine → fourteen**, `FLOOR_TIGHTENED_ROUTES` stays **four**, so `FLOOR_ROUTES` (`:113`) is **eighteen** — and **D9's table is the only source for that count**: a figure sized from prose reds a table-driven test on the first run, and this one powers the 401 walk (`:486`), the count guard (`:514-516`), the wiring walks (`:527`, `:593`), the `no-store` parametrization (`:605`), the tenant walk (`:633`), the shadowing guard (`:803`) and the mutating filter (`:1120`). `FakeFloorService` grows the five methods. **`SPEC_ERROR_CODES` (`:127`) becomes NINE** and stays set-equal; its *"⚠ SEVEN after F36"* comment (`:121`) is **rewritten rather than deleted**.

**`test_sos_api.py`** — **the `SosAlertView` key set pinned by SET EQUALITY** (AC8): `{id, status, raised_by, raised_by_name, target_staff_user_id, target_name, room_label, note, accepted_by, accepted_by_name, acknowledged_at, created_at, escalated, stalled, for_me}`. **This is the assertion that catches a customer field arriving unreviewed on a payload that polls eleven sections.** Plus the envelope's `{alerts, server_now}`, and the payload asserted as a literal for one open, one accepted and one escalated alert **including `server_now`, `escalated`, `stalled` and `for_me`**.

**`test_staff_role_gating.py`** — `FLOOR_OPEN` (`:123`) grows **nine → fourteen**, the five new paths added as **route TEMPLATES** — not concrete urls; the walkers read `route.path` and mixing spellings is a CI round trip (`:93-96`). **The four tightened paths stay deliberately absent**, which is what keeps the table's shipped comment (*"the exhaustive list of what they may reach"*, `:84`) true.

⚠ **The intersection classifier at `:310` must not be touched.** F57's Risk 1 says in writing that a reviewer facing a red here *"must fix the route, never relax the quantifier"* (`:279`). **F37 adds only untightened routes, so it should not go red at all — and if it does, the cause is a gate somebody added by accident.**

### The code

| Method | Path | Effective roles | Why |
|---|---|---|---|
| `GET` | `/manage/floor/sos` | all five | the app-level poll; rows filtered by D7's audience predicate |
| `POST` | `/manage/floor/sos` | all five | raise — first person, always for herself (D3) |
| `POST` | `/manage/floor/sos/{alert_id}/accept` | all five | permitted = target **or** elevated, refused as 404 (D4) |
| `POST` | `/manage/floor/sos/{alert_id}/resolve` | all five | permitted = raiser, acceptor **or** elevated (D5) |
| `POST` | `/manage/floor/sos/{alert_id}/cancel` | all five | permitted = raiser **or** elevated (D5) |

**F36 tightened four routes; F37 tightens NONE, and the criterion is F36's D8 verbatim.** A per-route `RoleGate` can express only a **pure role predicate** — one that depends on nothing about the target. **Every rule in this feature reads the row**: the raise is first-person (no target rule at all), and accept/resolve/cancel each read `target_staff_user_id`, `raised_by` or `accepted_by` before they can decide. **There is no gate that can say "the person this alert names".**

**No `status_code=` on any route** (verified: no route on this router declares one; `create_room` `:183` is the shipped create precedent and answers 200). **No rate limiter** (no `/manage` router carries one). The four new mutating verbs are CSRF-fenced by `CsrfOriginMiddleware` **by method rather than by path list** (`csrf.py:15,48`), so they are fenced by construction; the one new GET is not, and its protection is the session cookie and the role gate alone.

**Every path's second segment is `floor`, so `vite.config.ts` needs NO EDIT** — and that is not free to get wrong. `test_spa_serving.py:381` asserts **set equality** between the live route table's second segments and the `^/manage/(…)` alternation, and a mismatch breaks **only a developer's machine** while production, CI and the whole suite stay green, serving the SPA shell where the API should be. **It has bitten this repo twice** (F52, then F57's plan). **Mounting at `/manage/sos` would have cost the edit; `/manage/floor/sos` costs nothing.** ⚠ Note the two facts are independent: the **URL** says `floor` because the router does; the **console placement** is app-level (D11) and would be identical either way.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| `FLOOR_ROUTES` sized from prose | write seventeen rows instead of eighteen | the count guard (`:514-516`) **RED** naming the mismatch |
| `FLOOR_OPEN`'s five new members | omit one | `test_the_floor_roles_reach_exactly_the_floor_routes` **RED** as `missing=[that path]` |
| a gate added by accident | hang `ELEVATED` on `/floor/sos/{alert_id}/accept` | the same test **RED** as `unexpected`. ⚠ **Fix the route, never relax the quantifier** |
| the `SosAlertView` key set | add `client_label` to the view | `test_the_sos_payload_carries_no_customer_datum` **RED**. ⚠ **The assertion is a NEGATIVE over the whole response body, so it is the only thing that can fail** — every other test asserts on fields that would still be present |
| the audience clause | drop it | `test_a_seamstress_sees_only_her_own_pages` **RED** (Task 4's mechanism, pinned here over HTTP) |
| mounting at `/manage/sos` | change the prefix | `test_the_manage_dev_proxy_names_every_manage_api_segment` **RED**. ⚠ **Run this one deliberately, then revert it** — it is the only way to prove AC24 is a live assertion rather than a coincidence |
| both 409 handlers | drop the registrations | `assert observed == SPEC_ERROR_CODES` (`:1175`) **RED** — the set equality is what catches Task 3's handler cost on the first run |

- **Done when**: `make lint` + `make test` green; `git diff main -- frontend/apps/manage/vite.config.ts` empty; the proxy mutation performed and reverted. **Third milestone**: all eighteen routes, both new codes and the whole payload are exercised end to end with **no Postgres**. `git show --stat`.
- **Commit**: `feat(floor): the five sos routes, the eighteen-row table and the audience the payload answers`

## Task 10 — The RLS isolation suite (**`db`-marked, run locally**) (AC10, AC11)
`backend/tests/test_sos_isolation.py` (**✚**)

**Non-negotiable, and it is the crown-jewel suite `architecture.md` calls permanent.** Connected **only as the app role** over a `NullPool` engine via the **`app_role_url`** fixture — **never `migrated_db`**, because the container superuser bypasses RLS and GRANTs unconditionally and every assertion would pass vacuously.

### The failing tests first

- tenant A raises an alert; **tenant B's `live_for` returns empty**, and `by_id` on A's alert id returns `None`
- tenant B can neither **accept**, **resolve** nor **cancel** A's alert — every attempt is a **404 indistinguishable from missing** (AC10), never a 403 that would confirm existence
- tenant B raising with **A's** `fitting_room_assignment_id` stores `NULL` and still creates the alert (D3's permissive fallthrough, proven across a tenant boundary)
- tenant B's `has_live_session` on **A's** staffer returns **False** even with a live row — the reachability read is tenant-scoped
- tenant A re-reads and nothing of hers moved
- **the GRANTs are exercised** — the app role can `INSERT`, `SELECT` and `UPDATE` on `sos_alerts`. Omitting the GRANT fails **nothing** until exactly here, as `permission denied`

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| `enable_tenant_rls("sos_alerts")` in the migration | delete the call, re-run | **every** probe **RED** — if any stays green the suite is connected as the superuser and is worthless |
| the `app_role_url` fixture | swap to `migrated_db` | the probes go **GREEN vacuously** — run this once, deliberately, confirm it, then restore. **That is the proof the suite measures RLS and not nothing** |
| the `GRANT` | drop it | the write probe **RED** as `permission denied` |

- **Done when**: local db suite green; both vacuity mutation-checks performed and restored. `make lint` clean. `git show --stat`.
- **Commit**: `test(floor): forced RLS isolation for the sos alerts and their four verbs`

---

# Part II — the frontend

> **Capture the qa-greps baseline BEFORE the first frontend edit** and diff it after every frontend task:
> ```
> make qa-greps > "<scratchpad>/qa-greps-baseline.txt" 2>&1
> ```
> The ten `check` calls read `apps/storefront/src` only (`qa-greps.sh:17`), but the trailing **date-reads review block** (`:62-67`) reads `apps/manage/src`. **F37 renders «מאז 11:20» and an elapsed line and is exactly the class of feature that reaches for a formatter.** It must not: `jerusalemTime` (`lib/jerusalem.ts:35`) already sets `timeZone`, and `elapsedLine` is arithmetic on two ISO instants with no timezone involved. **Byte-identical output after every task is the assertion.**

## Task 11 — `usePoll` gains **two optional fields**, in eight lines (D12 / C3, DC-9)
`frontend/apps/manage/src/lib/usePoll.ts`, `frontend/apps/manage/src/__tests__/usePoll.test.ts` (or the shipped location)

### The binding signature — and the spec's own table contradicts it

```ts
intervalMs?: number | (() => number);   // ⚠ NOT `number`. C3 / DC-9 / deck F-10.
idleStopMs?: number | null;
```

**The function form is not a convenience and AC20b is the whole reason.** The shipped tick shape calls `poll.succeeded()` inside the fetch's `try` (`FloorPanel.tsx:174`) and `poll.reschedule()` in the `.finally()` (`:192`) — **both in the same microtask chain as the response**, i.e. **before** React commits the `setAlerts` that would flip a state-derived gap from 5 000 to 2 000, and long before the passive effect that would mirror it into a ref. So a state-derived gap makes **the tick that first observes an alert re-arm at 5 000 ms**, and the 2-second cadence starts only on the tick after — **precisely when the raiser is waiting to see who is coming.**

⚠ **And the obvious test passes over the bug.** *"Changing `intervalMs` between ticks takes effect on the next re-arm"* re-renders the hook with a new prop and *then* ticks, so it goes **green over the broken behaviour** — the same shape as F57's vacuous focus test.

### The failing tests first — new blocks only, shipped blocks unedited

- `intervalMs` governs the gap **as a number** and **as a function**, and `succeeded()` resets to **the resolved value** and not to `POLL_INTERVAL_MS`.
- **AC20b — ONE REAL TICK.** Arm at 5 000; drive a single real tick whose `run` resolves with the first alert and whose handler sets the ref **before** `succeeded()`; assert the next timer fires at **2 000 ms**. ⚠ **This block must exist in addition to, and not instead of, the weaker rerender-then-tick block** — the weak one is kept precisely because it is the one that would have shipped the bug.
- `idleStopMs: null` never stops, **including when it changes from a number to `null` with a timer already armed**.
- **AC20a — the default path pinned mechanically**: no `intervalMs`, no `idleStopMs` → the gap is `POLL_INTERVAL_MS` and the idle stop trips at `IDLE_STOP_MS`.

### The code — exactly eight lines, and two of them are traps

1. `intervalRef` and **`idleGapRef`** mirrored in the **existing** `useEffect(() => { runRef.current = run; … })` block — **no new effect**.
   ⚠ **`idleGapRef`, NOT `idleRef` — `idleRef` already exists at `usePoll.ts:118`** and holds the idle **timeout handle** (`useRef<ReturnType<typeof setTimeout> | null>`), read and written by `clearIdle()` (`:140-145`) and `armIdle()` (`:165-177`). A second declaration is an immediate redeclaration error; **the near-miss — reusing the name for the gap — silently breaks `clearIdle`.**
2. `backoffRef` (`:119`) initialised from the **resolved** `intervalMs`.
3. `succeeded()` (`:285`) and `resume()` (`:317`) resetting to the **resolved** `intervalRef.current` (call it if it is a function) instead of the constant.
4. `armIdle()` returning early when the gap is `null`.
   ⚠ **The `null` early return goes AFTER the existing `clearIdle()` call at `:166`, never before.** `armIdle()` opens with `clearIdle()`; return above it and **a timer armed under a numeric gap survives a switch to `null`, so the loop still idle-stops after the caller disabled the stop.**

`MAX_BACKOFF_MS` is unchanged — a 2-second base still backs off to sixty.

> **Acceptance rule, F36's D15 applied one level down: `BoardSection.test.tsx` and `FloorPanel.test.tsx` must pass with ZERO EDITS after this change, and `usePoll`'s own shipped assertions likewise.** They are the only thing that can tell a faithful extension from a subtly different one. New `it(` blocks are added freely; **an edit to an existing expectation means the change is wrong.** `git diff main -- frontend/apps/manage/src/lib/usePoll.ts` should be readable in one screen.

*Declined a fifth hand-rolled loop for SOS.* It would forfeit F34's unmount fix, F57's StrictMode idempotence fix, the `document.hidden` pause, the backoff and the `{401,403}` terminal rule — the five things this hook exists to stop four builders re-deriving. *Declined a constant 2-second tick*: 2.5× the requests on every console screen forever, to save two lines.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| the **function** form of `intervalMs` | type it `number` and read it once at mount | **AC20b's one-real-tick block RED**; the weak rerender-then-tick block stays **green**, which is the whole point. ⚠ **Run both and record that one stayed green** |
| the `null` early return's **position** | move it above `clearIdle()` at `:166` | the arm-numeric-then-switch-to-null block **RED** |
| `succeeded()` resetting to the resolved value | leave it resetting to `POLL_INTERVAL_MS` | the function-form gap block **RED** after the first successful tick |
| `idleGapRef`'s name | rename it `idleRef` | a **compile error**, not a test failure — run it once to see the redeclaration and record why the near-miss is the dangerous one |

- **Done when**: `make fe-test` + `make fe-build` green; **`BoardSection.test.tsx` and `FloorPanel.test.tsx` diffs are EMPTY**; every mutation performed and restored; `make qa-greps` byte-identical. `git show --stat`.
- **Commit**: `feat(manage): usePoll's resolvable interval and its disableable idle stop`

## Task 12 — The wire types, the five API methods, and the `sos.*` namespace with its four i18n guards (D14, D17 / C4, C5, DC-4)
`frontend/apps/manage/src/api.ts`, `…/validation.ts`, `…/i18n/he.ts`, `…/i18n/ar.ts`, `…/__tests__/api.test.ts`, `…/__tests__/i18n.test.ts`

### The failing tests first

**`api.test.ts`** — each of the five methods hits its path with the body verbatim (**no case conversion — this app speaks the backend's snake_case**); a 409 with `details` produces an `ApiError` **carrying** them; a 409 **without** `details` produces one whose `details` is `undefined`, never `null`. **`ApiError` and `extractError` need NO change** — F36 already shipped `readonly details?: Record<string, string>` (`api.ts:9-31`).

**`i18n.test.ts` — FOUR edits, and the first is the one a builder working from an enumerated list will not write:**

1. **`HE_F37` must be FOLDED INTO `HE`, not merely declared.** The file says so about itself at **`:33`**: *"Folded in, not just declared: without this the resolve check, BOTH register guards and the `ar` parity guard silently skip every F52 key."* Without the fold, **all 49 hand-transcribed strings ship unchecked** for the exclamation mark, for the `/נשלח|תישלח|בדרך/` send-ban and for a missing `ar` key — **and the ban is the entire basis of the «אני מגיעה» wording decision.** Exactly as `HE_F36` does at `:60`:

   ```ts
   const HE_F37 = entries(he.translation, (key) => key.startsWith("sos."));
   const HE = [
     ...HE_F15, ...HE_F51, ...HE_F52, ...HE_F17, ...HE_F34,
     ...HE_F57, ...HE_F53, ...HE_F33, ...HE_F36, ...HE_F37,
   ];
   ```

   ⚠ **`const HE = [` is line 61 and `];` is line 71 — VERIFIED.** Both decks claim that reference is "two lines stale"; **it is not** (C4, DC-3). The array folds **nine** constants and F37 makes it **ten**.
   **No `nav.` term in the selector, and that is an assertion rather than an omission** — F37 adds no nav row. Every other feature's constant starts `key === "nav.x" || …`; this one does not, and it is the one-line proof that an alert is an interruption and not a destination.

2. **A row-count floor** — `HE_F37.length > 44`, for the reason the file's own comment gives: folded into an existing list, this feature's rows could shrink by this many and still pass.

3. **`ar[key] === he[key]` for every `sos.*` key** — **not "non-empty"**, which passes on an English string, a `TODO`, or a *different* Hebrew wording, and 49 keys are transcribed by hand into two files.

4. **A `sos.*`-scoped ban assertion** and **a `sos.*`-scoped digit guard.**
   ⚠ **THE BAN REGEX IS THE THREE-TERM ONE.** `/נשלח|תישלח|בדרך/` — the global guard at **`:560`**. **NOT** the `HE_F33`-scoped five-term `/נשלח|תישלח|בדרך|SMS|הודעה/` at **`:547`**: «הודעה» is in the approved `sos.error.noteTooLong` («ההודעה ארוכה מדי.»), so a builder mirroring F33's block wholesale **reds the suite on a string the copy deck approved** (C5). The digit guard is `/\d/` over every `sos.*` value — **0 hits**, because escalation and stall are named as **states** and every number is an interpolation, which is what makes D17's *"mirroring a number nothing computes is parity theatre"* a complete argument rather than one with a literal 30 sitting in the bundle contradicting it.

**Do not renumber or "tidy" anything else in that file.** Two `it(` blocks already both claim *"resolves the eleventh nav item"* since F53 landed. It is a shipped inconsistency, it is not F37's, and touching it puts an unrelated edit on this diff.

### The code

- `api.ts` — `SosStatus`, `SosAlert`, `SosResponse`, `RaisedAlert`, `RaiseSosRequest`; **five** new methods on the exported `api` object, all under `/manage/floor/sos…`.
- `validation.ts` — `MAX_SOS_NOTE_LENGTH`, mirrored from `app/floor/validation.py` (Task 3's `MIRRORS` name).
- `i18n/he.ts` and `i18n/ar.ts` — the `sos.*` namespace, **flat dotted keys appended as a per-feature block**, the shipped `rooms.*` / `floor.*` shape. **Transcribed from `copy.md`, which is the single source for both columns** — never from spec D17's table, which the deck supersedes and which is missing two keys, carries one that is not a key, and duplicates two. **`ar` values are the approved Hebrew standing in untranslated and are never empty strings**: i18next's `returnEmptyString` default renders `""` rather than falling back. `lng` and `fallbackLng` stay `"he"`; **no switcher.**
  - **DC-4** — one new key, **`sos.roomA11yPrefix`** = «מיקום», rendered in an `sr-only` span **inside** the `role="alert"` region before the bare `<bdi>`. **49 keys, not 48.**
  - **Reuse before invention** (copy §8): `rooms.cancel`, `rooms.handoverOnBreak` (⚠ replaces D17's proposed `sos.targetOnBreak`), `rooms.elapsed`, `rooms.elapsedJustNow`, and F57's whole `floor.*` state block — `floor.heading`, `floor.loading`, `floor.updatedAt`, `floor.staleAt`, `floor.staleBody`, `floor.refresh`, `floor.pause*`, `floor.resume*`, `floor.paused*`, `floor.idleStopped`, `floor.sessionEnded`, `floor.accessEnded`, `floor.reload`, `staff.loadFailed` — **all shipped and reused unchanged.** `SosCentre` is inside `FloorPanel`'s poll and **must not spell any of its states a second way.**
  - ⚠ **`sos.channelReload` is «רענון הדף», not «רענון».** D17 says *"reuse `floor.reload`'s word"* and `floor.reload` **is** «רענון הדף» (`he.ts:663`); «רענון» is `floor.refresh` (`:618`), a **different act** on a strip whose only remedy is a page reload. Its own key and not a reuse, because the strip renders on eleven sections where no `floor.*` string otherwise appears.
  - ⚠ **`sos.dismissAria` is «הסתרה — הקריאה מ{{name}}».** WCAG 2.5.3 label-in-name is **Level A** and therefore inside IS 5568's binding scope: an accessible name must contain the visible label, and D17's «הסתרת ההתראה — …» is a different word from the visible «הסתרה».
  - ⚠ **`sos.centreRaise` and `sos.targetOnBreak` are DELETED** — byte-identical to `sos.raise` and to the shipped `rooms.handoverOnBreak`. Two keys holding one string are two things to keep true and twice the hand transcription into `ar.ts`.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| **the `HE_F37` fold** | declare the constant without spreading it into `HE` | the resolve check, **both** register guards and the `ar` guard **silently pass** on a deliberately broken key. **Add a `!` to one value and confirm it goes GREEN without the fold and RED with it.** ⚠ **Run this one — it is the whole of deck F-6** |
| the `sos.*` digit guard | delete it, then put a literal `30` in `sos.escalated` | the guard must go **RED**; confirm it does |
| `ar[key] === he[key]` | delete it, then change one `ar` value to a different Hebrew wording | the shipped presence guard stays **green** and the equality guard goes **RED** |
| the **three-term** ban regex | swap in F33's five-term one | `sos.error.noteTooLong` **RED on «הודעה»** — run it once, deliberately, and record it, because the five-term regex is the one sitting three lines above the right answer in the same file (C5) |
| `details?: Record<string,string>` | type it `\| null` | the `details`-less 409 test **RED** on `undefined !== null` |

- **Done when**: `make fe-test` + `make fe-build` green; `pnpm -r lint && pnpm -r typecheck` clean; `make qa-greps` byte-identical to the baseline; every mutation performed and restored. `git show --stat`.
- **Commit**: `feat(manage): the sos wire types, its five api methods and the copy deck with its four i18n guards`

## Task 13 — **`lib/sos.tsx`: the app-level poll**, its two tick rates, and how it coexists with the two shipped loops (D11, D12)
`frontend/apps/manage/src/lib/sos.tsx` (**✚**), `frontend/apps/manage/src/__tests__/sos.test.tsx` (**✚**)

### How this relates to the shipped `usePoll` and to the floor board's 5s loop — decided, not left to a builder

- **It REUSES `usePoll`.** Third instance. Task 11 gave it two optional fields and nothing else. **Not a fifth hand-rolled loop** — that would forfeit F34's unmount fix, F57's StrictMode idempotence fix, the `document.hidden` pause, the backoff and the `{401,403}` terminal rule.
- **It is a SEPARATE loop from `FloorPanel`'s, and folding is refused on four independently sufficient grounds** (D11): the overlay must render over **any** section and `FloorPanel` is mounted on **2 of 13** (`App.tsx:212`, `:215`, verified); folding would put a **customer's name** on an app-level loop, inverting the argument F36 spent its longest section making; it would require **lifting floor state above `FloorPanel`**, which F57's D11 forbids in writing; and the two need **different tick rates and different idle behaviour** — one loop cannot be both 5s-fixed-and-idle-stopping and 5s/2s-and-never-stopping.
- **The two loops do not coordinate and must not.** They are independent `usePoll` instances with independent generations, backoffs and terminal states. The only place they touch is **`paused`** — see Task 15's freeze, which is a rendering contract inside `SosCentre` and not a poll-to-poll link. **The overlay keeps rising while the board is paused, and that is the safety property: pausing a VIEW must never disable the CHANNEL.**
- **Three loops on the board screen is this architecture's ceiling and F58 will want a fourth.** Recorded in Task 18's report. **If a fifth `usePoll` caller ever appears, that is the moment to ask whether the console wants one multiplexed poll rather than N.**

### The per-device cost, with units — DC-5

Per SOS tick, per device: **3 sessions opened** (`tenants.by_slug` in its own session → `resolve_session` → the alerts read), **2× `set_config` + BEGIN/COMMIT**, **3 `SELECT 1` pool pre-pings**, **4 business SQL** → **≈6 statements, ≈11 round trips, 3 pool checkouts** — identical to F57's floor tick, because the alerts read is **one** statement.

| Screen | Before F37, per 5 s per device | After F37, **idle** | After F37, **an alert open (2 s)** |
|---|---|---|---|
| `board` (owner, shift_manager) | ~30 (board 17 + floor 13) | 17 + 13 + **SOS 11** = **~41** | 17 + 13 + **~27** = **~57** |
| `floor` (the three floor roles) | ~13 | 13 + **11** = **~24** | 13 + **~27** = **~40** |
| **each of the other eleven sections** | **0** | **~11** | **~27** |

**And the no-idle-stop consequence, computed rather than gestured at**: a 5 s tick is 720 ticks/h, so a console left open for one 12-hour session issues **12 × 720 × ~11 ≈ 95 000 round trips per device per night**. **That is the first unbounded number in the product.**

⚠ **The critic's ~39 / ~55 is one feature stale and the divergence is recorded rather than picked silently**: it uses F57's pre-F36 floor tick of **~11**, while F36's plan Task 13 records the floor tick at **~13** after F36 added a statement to the payload read. **~41 / ~57 is the pair F29 gets.** `tenants.by_slug` — the uncached-per-request lever `tenancy/resolver.py:8-9` already assigns to F29 — is now paid **three times per beat** on the board screen instead of twice. Nothing throttles it server-side (F34's D3 declines a read limiter: *"there is no attacker, only loyal clients"*), so the client backoff is the only ceiling — **and this loop has no idle stop**, which is the one place the ceiling is genuinely lower than before.

### The failing tests first

- the provider owns **one** `usePoll`, and the tick rate is **5 000 with no alert, 2 000 with any alert in `{open, accepted}`** — **not `for_me`**, because the raiser is watching for the accept and the acceptor is watching for the resolve, and **one condition that covers all three roles cannot be got wrong**;
- **AC20b end to end**: one real tick whose response carries the first alert re-arms at 2 000;
- the four actions each run the five-part `mutate` dance and **re-arm in the `.finally()`**;
- a **401** stops the loop and fires `onSessionEnded` **exactly once**; a **403** sets a terminal `access` state and does **not** fire it; a backed-off loop exposes its state;
- `idleStopMs: null` — **the loop never idle-stops** (AC19).

### The code

**`SosProvider` + `useSos()`, mounted inside `App`'s signed-in return.** ⚠ **A provider rather than state in `App`, and the forcing constraint is mechanical, not architectural:** `App` early-returns for `!bootstrapped` (`:146`) and for `staff === null` (`:155`), so a hook called after those returns is a rules-of-hooks violation — and `frontend/.oxlintrc.json` enables `react/rules-of-hooks: error` precisely so that is a **lint failure** rather than a runtime one. **A provider is a component boundary, so it may be mounted conditionally where a hook may not.** `ToastProvider` (`App.tsx:187`) is the shipped precedent for exactly this shape and is already wrapped around the same tree.

**`.tsx` because it renders a provider**; `lib/booking.tsx` is the shipped precedent for JSX in `lib/`.

**⚠ THE GAP IS DERIVED FROM THE RESPONSE, NEVER FROM REACT STATE.** `intervalMs: () => (hasLiveAlertRef.current ? 2_000 : 5_000)`, read by `usePoll` **at arm time**. The provider sets `hasLiveAlertRef.current` in the **same `.then()` that calls `setAlerts`, on the line above `poll.succeeded()`** — one ref write beside a call that already exists.

**⚠ THE IDLE STOP IS DISABLED AND THIS IS THE MOST DANGEROUS THING IN THE FEATURE IF IT IS GOT WRONG.** `idleStopMs: null`, with the justification written where the flag is set: a phone in an apron pocket, untouched for eleven minutes, would otherwise **silently stop receiving pages**, and silence is the worst property an emergency channel can have. **SC 2.2.2 does not bind**: in the idle state the component renders **nothing** (no content to pause), in the alert state **nothing auto-updates** (no countdown, no live counter — D15 forbids both, which is what keeps this true rather than merely claimed), and the "hide" mechanism the criterion asks for **exists** (the dismiss control, plus Esc). **The `document.hidden` pause inside `usePoll` still applies and is kept deliberately** — Risk 1's ceiling, written down rather than discovered.

**Its own copy of the five-part `mutate` dance** (`FloorPanel.tsx:363-386`), not an import: increment, `poll.clearTick()`, `poll.bump()`, run, classify a terminal error through `poll.fail`, then **in the `.finally()`** decrement and `poll.reschedule()` — *"or the panel silently stops converging the first time anybody acts"* (`:341-362`).

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| the ref-derived gap | derive `intervalMs` from React state | the one-real-tick block **RED** (AC20b) |
| `idleStopMs: null` | pass the default | the never-idle-stops block **RED** after `IDLE_STOP_MS` (AC19) |
| the tick-rate condition | key it on `for_me` instead of `{open, accepted}` | the **raiser's** own-page block **RED** — she would wait 5 s to learn who is coming |
| `poll.reschedule()` in the `.finally()` | move it to the success path | the failed-action block **RED** — the loop stops converging the first time anybody acts |
| `onSessionEnded` firing **once** | drop the once-guard | the 401 block **RED** on a second call |

- **Done when**: `make fe-test` + `make fe-build` green; **`git diff main -- frontend/apps/manage/src/components/FloorPanel.tsx` still empty at this point**; every mutation performed and restored; `make qa-greps` byte-identical. `git show --stat`.
- **Commit**: `feat(manage): the app-level sos provider, its two tick rates and its disabled idle stop`

## Task 14 — **`SosOverlay`: the announcement and focus contract** — *the gate condition* (D15 / DC-1, DC-2, DC-4)
`frontend/apps/manage/src/components/SosOverlay.tsx` (**✚**), `frontend/apps/manage/src/__tests__/SosOverlay.test.tsx` (**✚**)

**IS 5568 / WCAG 2.0 AA is legally binding here (pre-decided #38) and the e7 Risks make the screen-reader announcement a gate condition, not a nicety.** axe must return **zero** violations **and axe is not the coverage — in both directions**: it cannot see a focus move that never happened (this repo has shipped that four times — F56, F34, F57, F36's stale closure) and it equally cannot see a focus move that **should not have happened**, which is the new failure class this feature could introduce. It has **no rule for SC 2.2.2**. It cannot see a focus ring that is the wrong colour against a parent's background (deck §2.1).

### ⚠ THE TWO TRAPS THAT MAKE A FOCUS TEST VACUOUS, and both have shipped

1. **jsdom does not blur a disabled element.** `Button.tsx:57` is `disabled={disabled || loading}`, so a **real browser** blurs the tapped control the instant a request starts — and **every action in this feature is that shape.** F57's shipped note records that its own success-path focus test was therefore **VACUOUS**: `document.activeElement` never became `<body>`, the guard never passed, and the whole restore effect could be deleted with the suite green. **Every test below must explicitly blur the tapped control before the promise resolves, or it asserts nothing.**
2. **The mid-typing focus-theft hazard needs its OWN test and it is a negative.** A test that asserts *"focus moved to X"* cannot fail when focus is stolen from somewhere it should not have been. **AC14 is three separate assertions and each has its own delete-the-guard mutation.**

### The failing tests first

**Render** — `null` with no alerts; `null` when alerts exist but none is `for_me` (⚠ **two different states, both rendering nothing** — the second is what stops a shift manager being interrupted by every page in the boutique and learning within a day to dismiss them unread); one card per rising alert, **oldest first**; the announced sentence present in a `role="alert"`; `sos.raiserGone` when `raised_by_name` is null; `sos.noRoom` when `room_label` is null; the note element **absent, not empty**, when the note is null.

**AC16 — the region's text is WRITE-ONCE.** Byte-identical from mount to unmount **across three consecutive ticks AND across the escalation and stall transitions**; a second alert arriving mounts a **second** `role="alert"` and does not touch the first. **Mutation: move the escalation clause inside the region → RED.**
⚠ `role="alert"` carries implicit `aria-live="assertive"` **and** implicit `aria-atomic="true"`, so **any** childList change inside re-announces the **entire** region, assertively, interrupting whatever the screen reader was saying. **One `role="alert"` per card and never one wrapping the list** — with a wrapper a second page would re-announce **every** card and the seamstress would hear again about the emergency she already answered.

**AC14 — THE OVERLAY DOES NOT STEAL FOCUS, in all three branches, each mutation-checked by deleting the `=== document.body` guard:**
- (a) focus in a **text input** → an arriving alert leaves `document.activeElement` **and the input's value** untouched **and the alert is still announced** (`role="alert"` present with the sentence);
- (b) focus on **`<body>`** → it moves to the **card container**;
- (c) ⚠ focus on a **`ConsoleShell` nav button — the ordinary state of a console in use** → `document.activeElement` is **unchanged** and the sentence is still present.

**AC15 — MOVES B, C and D**, each mutation-checked. **AC17 — Esc, all four cases.**

**AC27 — the channel never dies silently**: a 401 fires `onSessionEnded` **exactly once** and stops the loop; a **403 leaves `staff` untouched** and renders the persistent `sos.channelDown` strip; a loop backed off beyond one tick renders the same strip. **Mutation: delete the callback / the strip — the console keeps rendering a working-looking shell over a dead channel.**

**AC28 — a dismissal is never permanent**: (a) dismiss at t<30 s, tick with `escalated: true`, the card is **back** — **mutation: revert the dismiss key to the bare id**; (b) while the set holds a live alert the overlay renders the **«קריאות עזרה · {{count}}»** affordance and **not `null`** — **mutation: delete the affordance**.

**AC29** — an accept issued from a **non-floor** section calls the shipped `useToast()` and produces a `role="status"` carrying `sos.acceptedCue`. **Mutation: delete the call → RED.**

**An axe pass, explicitly not sufficient.**

### The focus moves — A, B, C, D, and DC-1 changes two destinations

| # | Move | Condition | Destination | Mutation that must turn it red |
|---|---|---|---|---|
| **A** | the first rising alert appears | **iff `document.activeElement === document.body`** | ⚠ **the CARD CONTAINER** — `<article ref tabIndex={-1} aria-labelledby={whoId}>` (**DC-1**), **not** the accept control | delete the `=== document.body` guard, then assert focus does not leave a text input |
| **B** | the overlay unmounts while holding focus | `activeElement` was inside it | `document.getElementById("console-main")` — the `<main tabIndex={-1}>` `ConsoleShell` already renders and the skip link already targets (`:43`, `:84`). **Never `<body>`** | delete the effect |
| **C** | a card leaves with siblings remaining | `activeElement` was inside that card | ⚠ **the NEXT REMAINING CARD'S CONTAINER** (**DC-1**), not its accept control; falls through to **B** when none remains | delete the departing-card check |
| **D** | a failed action's in-card alert appears | **iff `activeElement` is inside that same card** | that alert | remove the in-card guard, then assert focus does **not** leave a text input behind the overlay when a 409 lands |

⚠ **DC-1's reason, because it inverts a sentence the deck currently sells as a benefit.** MOVE A fires *iff* `activeElement === document.body` — **exactly the state in which the next Space is a page-scroll** — so landing on «אני מגיעה» converts that keypress into an **irreversible accept** sitting on top of the two-minute `STALLED_AFTER` hole (deck F-2). MOVE C is worse: it parks focus on a **different emergency's** accept control at the moment the user was mid-keyboard-interaction with the one that left. **Accept stays FIRST IN DOM inside the card, so reach costs one Tab, the announcement is untouched, and §2.3's five accidental-accept guards become six.**

⚠ **`aria-labelledby={whoId}` and not a bare `tabIndex={-1}`.** Focusing an unnamed `<article>` makes some ATs re-read the whole subtree the alert just announced; pointing at the WHO paragraph's `useId()` reuses the exact node, adds **no new string** and cannot drift. **Carry it into the manual screen-reader pass as a named item** — if the pass finds a double-read anyway, the recorded remedy is one line and not a redesign.

⚠ **THE Esc ROUTE-IN IS NOT CHANGED BY DC-1 AND A BUILDER "UNIFYING" THE DESTINATIONS REVERTS IT.** Esc-from-outside lands on **«אני מגיעה»** (AC17) because it is a **deliberate keypress**, not an involuntary arrival. MOVE A and MOVE C are involuntary. That distinction is the whole of DC-1.

⚠ **MOVE D copies `FloorPanel.tsx:270-271`'s SHAPE and NOT its guard.** That shipped effect fires `cardAlertRef.current?.focus()` **unconditionally** — correct *there*, because the panel's `Button` is `disabled={disabled||loading}` and the browser already blurred it. **Copied into the overlay it becomes an unguarded focus move on an error path, in the one component whose whole premise is that it never moves focus uninvited.**

### ⚠ THE KEYBOARD ROUTE IN, which MOVE A alone does not provide

**An alert announced perfectly to a user who cannot reach the ack control is not an accessible alert.** MOVE A deliberately does not move focus when something holds it, and Esc bound to the container fires only when focus is already inside — so for **the exact user this design protects**, someone mid-form in `main`, «אני מגיעה» sits behind a Shift+Tab run past every preceding focusable in her section **plus the whole `ConsoleShell` chrome** (SkipLink `:43` → logout → up to ten NAV rows → `<main id="console-main">` `:84`). Forward Tab is worse. *"First in DOM is first reached by Tab"* is true only in the `<body>` case — i.e. only where focus moved anyway.

> **Esc from OUTSIDE the overlay MOVES FOCUS INTO the first rising card's «אני מגיעה». Esc from INSIDE keeps its meaning: dismiss.**

One document-level **capture** `keydown`, live only while at least one alert is rising, with **two guards**, each preserving a shipped behaviour rather than being defensive padding:
- **`document.querySelector("dialog[open]") === null`** — what keeps F36's **three** shipped `<dialog>`s (`RoomsPanel.tsx:605`, `:932`, `:941`) and `SosRaiseDialog` owning their own Esc (`Modal`'s `onCancel`). `Modal` renders its `<dialog>` **unconditionally** and toggles `open` via `showModal()`/`close()`, so the selector matches only while one is genuinely open. **Verified.**
- **the event target is not a `<select>`** — ⚠ **`RoomsPanel.tsx:790` renders a bare `Select` on the free tile, OUTSIDE any dialog** (verified), and Esc closing an open native dropdown is browser behaviour a capture listener would pre-empt. **Two characters of condition; jsdom would never have caught it.**

**AC17's four cases, all in one block**: Esc from inside dismisses · Esc from outside moves focus into «אני מגיעה» **and leaves the source input's value unchanged** · a second Esc then dismisses · with a `Modal` open, Esc closes the **Modal** and the overlay is untouched. **Mutation: delete the capture handler — the second case must go RED.**

### The code

**The red is the FIELD; each card is paper** (deck §2.1, DC-10's recomputed figures): `<div className="fixed inset-0 z-40 overflow-y-auto overscroll-contain bg-danger p-4">` — **no handler, no `onClick`, no backdrop-dismiss** (a pocket press must not close an emergency), **no `role="presentation"`** (DC-8), **not a `<dialog>`, not `showModal()`, not `inert`** (each moves focus by definition). Cards are `<article className="rounded-md bg-surface-raised p-6 shadow-lg" tabIndex={-1} aria-labelledby={whoId}>` — `Modal`'s shipped skin.

⚠ **Why the field cannot be the card surface, in four measured numbers** (`theme.css:23-35`, recomputed at this gate — DC-10): on `--color-danger` `#A03232`, `--color-focus` `#7F612B` is **1.22:1** — and `focusRing` is drawn at `outline-offset-2`, i.e. **on whatever is behind the control**, so **the console's only focus indicator would be invisible on an emergency ack** (WCAG 2.4.7, legally binding, **and axe cannot report it** because its contrast rule computes an element against its own background); `--color-ink` is **2.25:1** (every shipped `Button secondary`/`ghost` label, every `Badge`); `Button danger`'s own fill is **1.00:1**; only `--color-surface-raised` passes, at **7.01:1**. **And the call-site patch is not available**: `className="focus-visible:outline-surface-raised"` is exactly F15's **F-6** — `cn()` is a plain join, both classes set `outline-color`, and which wins is decided by stylesheet order. **Full-screen red survives literally; the words move onto paper where the whole shipped vocabulary already works.**

**The card's content, in walking order** (deck §2.2): **WHO** «{{name}} קוראת לעזרה» `text-xl font-semibold text-ink`, name in a bare `<bdi>`, carrying `whoId` · **WHERE** — ⚠ **`<span className="sr-only">{t("sos.roomA11yPrefix")}</span>` then the bare `<bdi>{room_label}</bdi>`** (**DC-4**): `CreateRoomRequest.label` carries **no `Field` bound** (its own docstring says so, `schemas.py:296-301`) and `0019` puts no CHECK on content, so a boutique that types «2» is fully supported and the atomic utterance would otherwise be «דנה כהן קוראת לעזרה 2 צריך סיכות». ⚠ **NOT an `aria-label` on the `<p>`** — ARIA prohibits naming on `role=paragraph`/generic, so the deck's em-dash-value-last shape is unavailable here and would have shipped a name nothing reads · **WHAT** the note in a bare `<bdi>`, **the element absent when null** · then, **as SIBLINGS OUTSIDE the region**: «מאז {{time}}» through `jerusalemTime` (**which never subtracts**), and the escalation/stall clause in `text-base font-semibold text-danger`.

**Controls: «אני מגיעה» `Button primary lg fullWidthMobile` FIRST in DOM, then «הסתרה» `Button ghost md` on its own line `justify-end`.** *Declined `variant="danger"` for the ack*: red-on-red is invisible on the field and, on the card, red is this product's **destructive** register — the most affirmative act on the floor must not wear the colour of the most destructive one.

**The bottom container** — ⚠ **`<div className="fixed inset-x-0 bottom-0 z-40 flex flex-col items-end gap-2 p-4">` (DC-2).** `inset-inline-0` **is not a Tailwind utility**: verified in the built bundle, `.inset-x-0{inset-inline:0}` exists and `inset-inline-0` has **zero** occurrences, so as written the class is dropped, the container loses its inline inset and *"one container, so they can never collide"* silently stops being true. `inset-x-0` is `BookingCTA.tsx:16`'s shipped spelling. It holds the **channel strip** (`sos.channelDown` + `sos.channelReload`, F57's terminal-panel shape) and the **re-open affordance** (`sos.dismissedCount`, `Button danger md`, ≥44×44).

**The dismiss set is keyed `${alert.id}:${alert.escalated}:${alert.stalled}`** and not on the bare id. A role-targeted page is `for_me` for an elevated caller from t=0, so a shift manager can dismiss at t=2 s — and with a bare id the card would still be hidden when `escalated` flips at t=30 s and would **never re-rise**, **defeating the safety net for the exact audience escalation targets**. In a boutique with one shift manager on the floor that is the whole audience gone on one tap, before the net can fire.

**Escalation is a WORD, never a colour** — «ללא מענה», **not** «ללא מענה כבר 30 שניות»: `escalated` is an unbounded boolean, so a four-minute-old page would state a flat thirty seconds to the shift manager deciding whether to walk or run. **No countdown and no live elapsed counter anywhere in the overlay** — that is what keeps D11's SC 2.2.2 argument true rather than merely claimed. `aria-hidden` is set on **nothing**, deliberately. `prefers-reduced-motion` needs no new rule: **the overlay appears; it does not animate** (`theme.css:155`).

### Mutation-checks (mandatory — all seven RUN)

| Mechanism | Remove it | Expect |
|---|---|---|
| MOVE A's `=== document.body` guard | delete it | AC14(a) and AC14(c) **RED**. ⚠ **Blur explicitly first or the test is vacuous** |
| **MOVE A / MOVE C's card-container destination** | point them back at the accept control | a new block asserting `document.activeElement` is the `<article>` and **not** a `<button>` goes **RED**. ⚠ **This is DC-1 and nothing else in the suite sees it** |
| MOVE D's in-card guard | fire unconditionally | the 409-while-typing block **RED** |
| the Esc capture handler | delete it | AC17's Esc-from-outside case **RED** |
| the `dialog[open]` guard | drop it | the Modal-open case **RED** — F36's three shipped dialogs lose their Esc |
| the `<select>` guard | drop it | the free-tile-dropdown case **RED**. ⚠ jsdom cannot see the real browser behaviour; assert the handler **did not run**, which it can |
| the escalation clause's **sibling** position | move it inside `role="alert"` | AC16 **RED** |
| the composite dismiss key | revert to the bare id | AC28(a) **RED** |
| the re-open affordance | render `null` instead | AC28(b) **RED** |
| `onSessionEnded` / the strip | delete either | AC27 **RED** |
| the `useToast()` call | delete it | AC29 **RED** |
| `sos.roomA11yPrefix`'s `sr-only` span | delete it | a new block asserting the region's accessible text contains the prefix goes **RED** (DC-4) |

- **Done when**: `make fe-test` + `make fe-build` green; axe **zero**; **every focus mutation performed and restored, each explicitly blurring first**; `make qa-greps` byte-identical. `git show --stat`.
- **Commit**: `feat(manage): the full-screen alert overlay, its write-once regions and its five focus rules`

## Task 15 — `SosCentre` inside `FloorPanel`, and **MOVE H** (D11, D16, D18 / DC-7)
`frontend/apps/manage/src/components/SosCentre.tsx` (**✚**), `frontend/apps/manage/src/components/FloorPanel.tsx`, `frontend/apps/manage/src/__tests__/SosCentre.test.tsx` (**✚**), `frontend/apps/manage/src/__tests__/FloorPanel.test.tsx`

### The failing tests first

**⚠ `FloorPanel.test.tsx`'s shipped expectations pass UNEDITED. That is D12's acceptance rule and it is the instrument that tells a faithful composition from a subtly different one.** New `it(` blocks are added freely; **an edit to an existing expectation means the change is wrong** and a reviewer seeing one should stop and read D12. The new blocks assert only `<SosCentre/>`'s placement **above** `<RoomsPanel/>`.

**`SosCentre.test.tsx`** — the empty state (heading row + trigger + one muted line, **no `Card`, no `EmptyState`**); rows carrying raiser, room, note, `elapsedLine` and **the status word**; `sos.escalated` and `sos.stalled` as **words** beside the `Badge`, never a second pill and never a colour change on the first.

**AC21 — which control EXISTS is the rendered form of the permission rules.** For `role="seamstress"`: the **accept** control on an alert naming somebody else, the **resolve** on a stranger's alert and the **cancel** on one she did not raise are **ALL ABSENT**; all three are present for `owner`. **No disabled buttons, no lock glyphs — absence.** ⚠ **This is what keeps the 403-is-terminal rule unreachable by design rather than by luck**: `usePoll.terminalOf` returns `"access"` for any 403 (`:100`) and `FloorPanel.tsx:441-458` clears every card — so a rendered control reaching a route its caller may not use **blanks a seamstress's only screen**, and for the three floor roles that is the entire product going dark.

**Mutations** — an accept patches the row **from the response** and is disabled while in flight; a double-tap fires **one** request; a 409 `SOS_ALREADY_ACCEPTED` renders the owner's name **from `details`** and the `details`-less variant renders `sos.error.alreadyAcceptedUnknown`; a cancel-after-accept renders `sos.error.cancelAfterAccept` **and its `details`-less variant**; a 404 renders `sos.error.notFound` and is **not** terminal; a 403 **is**; an unmapped failure renders **`sos.error.actionFailed`** and never `FALLBACK_ERROR_MESSAGE`.

**AC18 — the paused freeze, and its one exemption.** A tick landing while `paused` does **not** change the rendered list; **the overlay still rises**; ⚠ **and an alert THIS device just raised appears anyway.**

**Cues go into `FloorPanel`'s existing `role="status"` region (`:510-516`) and the poll never writes there** (F34's D11, verbatim and non-negotiable). Driven over **several consecutive ticks with the cue already populated** — assigning a byte-identical string to a text node still produces a real `childList` mutation inside `role="status"`, and a single-tick assertion passes against the broken version whenever the cue starts empty (`FloorPanel.tsx:238`).

**An axe pass, explicitly not sufficient.**

### The code

**`SosCentre` is a CHILD of `FloorPanel`, rendered ABOVE `RoomsPanel`** — an active emergency outranks a room list — and it is a child for three reasons that each rule out the alternatives: it needs the **staff list** for the raise dialog's target `Select` and `FloorPanel` already holds it; it needs **`paused`**, so `FloorPanel`'s pause control does not lie; and it uses `FloorPanel`'s **one** `role="status"` cue and its **one** SC 2.2.2 control, so the board gains no third pause button (F36's D15: *"two is the answer… three would start to be a defect"*).

**It takes its alerts from `useSos()`, not from a prop** — the one place this feature deliberately reaches past `FloorPanel`, because the alerts belong to the app-level poll and there is exactly one of them.

**Rendered always, including with no alerts**, because it carries the second raise entry point. ⚠ **Empty is a heading row plus one muted line (~64px) and NOT an `EmptyState` (~140px)** — `EmptyState`'s `py-12` + `font-display text-xl` would make *there is no emergency* the visually loudest block on a screen a staffer reads fifty times a shift. **The condition `EmptyState` exists for is content that should be here and is not; no alerts is the desired state.** The `Card` appears only when there is something to put in it.

⚠ **THE PAUSED FREEZE, and it is three lines that make the pause control's claim true.** `FloorPanel`'s control is named «השהיה — עדכון הצוות» and governs the region it sits in — which after this feature contains a list fed by a loop pause does **not** stop. So `SosCentre` receives `paused` (already a shipped `RoomsPanel` prop, `:8`) and **freezes its rendered list from a snapshot ref while paused**. **The overlay keeps rising while the board is paused, and that is the safety property: pausing a VIEW must never disable the CHANNEL.**

⚠ **ONE EXEMPTION: an alert THIS DEVICE just raised.** Both raise triggers live on the floor section, the overlay never rises for the raiser's own page, and a frozen list will not add it — so a staffer who paused the board and then raised would see her own new alert **nowhere**, with a transient cue as her only feedback. **One line: the raise's response alert is merged into the frozen snapshot.** The freeze exists so the pause control does not lie about **the poll**; a row this device created one tap ago is not the poll moving underneath her.

**⚠ MOVE H — `SosCentre` OWNS ITS OWN error state, ref and focus rule (DC-7).** Verified: `FloorPanel` has exactly one of everything it would otherwise share — `cardError` `:99`, `cardAlertRef` `:103`, an **unconditional** `cardAlertRef.current?.focus()` on every non-null transition `:270-271`, rendered under `cardError?.id === card.id` `:718`. **Shared, an SOS 409 would steal focus into a STAFF CARD's alert node through the exact guard-less effect MOVE D warns against copying** — and `cardError.id` is a *staff card* id, so the render predicate would collide semantically too. So:

- `SosCentre` declares its own `rowError: {id, text} | null` and its own `rowAlertRef`;
- its focus effect is keyed on `[rowError]` (**not raised in the handler — the alert node does not exist when `setRowError` runs**) and is **guarded on `document.activeElement` being inside that row**, MOVE D's shape and not `FloorPanel`'s unguarded one;
- **`FloorPanel`'s pair is not touched**, which is also what keeps its shipped test expectations unedited.

**One `Badge` per row and it is the status word** — «פתוחה» `danger`, «מטופלת» `neutral`. **`elapsedLine(t, serverNow, created_at)` is F36's shipped helper, reused unchanged** — `rooms.elapsed` / `rooms.elapsedJustNow` **across namespaces, deliberately**, because `lib/elapsed.ts` hardcodes those keys and a second elapsed implementation is what D17's own no-date-library rule forbids. **No new formatter** (`jerusalemTime` already sets `timeZone`).

⚠ **`FloorPanel`'s `holdRef` gains one more reason and NO code** (`:127`). Its comment already records that F36 made it carry far more than the ~20px it was built for; **an SOS-centre row appearing ABOVE the rooms panel moves every tile below it, directly under a travelling finger.** The mechanism is unchanged; **the comment gains the case.**

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| the paused freeze | render live rows while paused | AC18's freeze block **RED** — and a pause control whose region keeps moving is an SC 2.2.2 failure **that passes axe** |
| the freeze's **raise exemption** | drop the merge | AC18's second half **RED** — her own alert appears nowhere |
| **MOVE H's in-row guard** | fire unconditionally | a block asserting focus stays in a text input when a 409 lands **RED** (DC-7) |
| **MOVE H's own ref** | reuse `FloorPanel`'s `cardAlertRef` | a block asserting the focused node is inside the alert's `<li>` and not a staff card **RED**. ⚠ **Run this one — it is the shape DC-7 exists to prevent** |
| any one permission predicate | render the control unconditionally | AC21 **RED** for `seamstress` |
| the cue's changed-only guard | write on every tick | the several-consecutive-ticks block **RED** (F34's D11) |
| `sos.error.actionFailed` | fall through to `FALLBACK_ERROR_MESSAGE` | the unmapped-failure block **RED** |

- **Done when**: `make fe-test` + `make fe-build` green; axe **zero**; **every shipped `FloorPanel.test.tsx` expectation passes unedited**; every mutation performed and restored; `make qa-greps` byte-identical. `git show --stat`.
- **Commit**: `feat(manage): the sos centre, its paused freeze and the per-row focus contract it owns`

## Task 16 — `SosRaiseDialog`, the tile's fourth control, and **MOVES E, F, G** (D16, D18 / deck F-7)
`frontend/apps/manage/src/components/SosRaiseDialog.tsx` (**✚**), `…/components/FloorPanel.tsx`, `…/components/RoomsPanel.tsx`, `…/__tests__/SosRaiseDialog.test.tsx` (**✚**), `…/__tests__/RoomsPanel.test.tsx`

### The failing tests first

**⚠ `RoomsPanel.test.tsx`'s shipped expectations pass UNEDITED**, and **the optionality of `onRaise` is what makes that possible** — the shipped render helper needs no edit. New blocks assert only that the raise control appears **on her own tile and on no other** (AC22).

**`SosRaiseDialog.test.tsx`** — «מנהלת המשמרת» is **first and default** (`value=""` → `null`); **herself is excluded** (the server refuses a self-target with a 400, and excluding it *prevents* the error rather than explaining it — F36's `RoomHandoverDialog` argument); a colleague on a break is **annotated and not excluded** (a seamstress on a five-minute break is exactly who you want for a corset back) via the shipped `rooms.handoverOnBreak`; the note's `maxLength`; **no colleagues at all** still offers «מנהלת המשמרת», which is always valid.

**AC2 — a rerouted raise KEEPS THE DIALOG OPEN with «הבנתי».** **Mutation: close unconditionally → RED.**
**AC30 — a rejected send keeps it open with the note preserved and renders `sos.error.raiseFailed`**, never `FALLBACK_ERROR_MESSAGE`.
**AC31 — the focus return runs from `FloorPanel`'s OWN trigger ref**, lands on the trigger when connected and on `FloorPanel`'s `<h2>` when not, **never `<body>`**. **Mutation: delete the `isConnected` branch → focus goes nowhere.**
**AC14's sibling case — an overlay rising while this dialog is open does not move focus.** ⚠ **Asserted, because "the guard happens to cover it" is exactly the kind of accidental correctness a later refactor deletes.**

**An axe pass, explicitly not sufficient.**

### ⚠ Three focus moves inside a native `<dialog>`, where "the browser handles it" is FALSE

| # | Move | Condition | Destination | Mutation |
|---|---|---|---|---|
| **E** | the send control is **replaced by «הבנתי»** (rerouted) | always — the focused element has just unmounted | «הבנתי» | delete it; focus falls to `<body>` **inside an open `<dialog>`** and the one message the ruling mandates becomes unreachable by keyboard |
| **F** | the failure alert appears | iff `activeElement` is the `<dialog>` or `<body>` — where the send button's blur left it | that alert | delete it |
| **G** | the dialog closes | `activeElement === document.body` | **`FloorPanel`'s own `sosTriggerRef`**: `trigger.isConnected ? trigger.focus() : headingRef.current?.focus()`. **Never `<body>`** | delete the `isConnected` branch |

**E and F are the FIFTH and SIXTH instances of the bug class this repo has shipped four times**, on the surface D15 declares a gate condition, and **the spec names neither** (deck F-7). `Button` is `disabled={disabled||loading}` (`:57`), and **a `<dialog>` whose focused child is removed drops focus to the dialog element or `<body>` depending on engine.**

⚠ **MOVE G is NOT a reuse of `RoomsPanel.tsx:307-330`, and citing it would ship the fifth focus bug.** Verified: that effect is `useEffect(…, [openDialog])` (`:330`) reading `dialogTriggerRef.current` (`:317`), which `openFrom` (`:558-560`) sets from `event.currentTarget`, **keyed on `RoomsPanel`'s own `openDialog` state (`:144`)**. With the open-state in `FloorPanel`, **`RoomsPanel`'s `openDialog` never changes, the effect never runs, the native `<dialog>`'s own return has no target, and focus drops to `<body>` for something the user did.** So, three lines instead of a citation:

- the tile's prop is **`onRaise?: (assignmentId: string, trigger: HTMLButtonElement) => void`** and the tile's handler passes `event.currentTarget` — ⚠ **the trigger element is passed UP**;
- **`FloorPanel` stores it in its own `sosTriggerRef`** and runs the MOVE-G shape in an effect keyed on **`FloorPanel`'s own** dialog state;
- **the fallback is `FloorPanel`'s `<h2 ref={headingRef} tabIndex={-1}>` (`:436`, verified), not `RoomsPanel`'s `<h3>`** — the heading actually in scope.

### The code

**Two raise entry points, one dialog, whose open-state `FloorPanel` owns** (it is the common parent of both triggers):
- **on a room tile** — `Button variant="danger" size="md"`, **FIRST in the shipped action row** (`RoomsPanel.tsx:838`, `flex flex-wrap justify-end gap-3`, which needs no change), rendered **only when `assignment.staff_user_id === selfId`**. Never on a colleague's tile: raising on somebody else's behalf is not a thing.
  ⚠ **Red here is the console's first NON-destructive `danger`, and the collision is worth one sentence rather than a new variant**: everywhere else red means *destructive*; here it means *this act has consequences you should mean*. `secondary` is unavailable — F36's rule is one `secondary` per tile and it is the act that ends the tile's current state («שחרור»); `ghost` would make the emergency control indistinguishable from «הוספת שמלה».
  ⚠ **The row wraps; it never shrinks, and `min-h-11` is not negotiable on any of the four.** 375 arithmetic: 295px of tile; «קריאה לעזרה» ≈120px + 12 gap + «הוספת שמלה» ≈112px = **244 ≤ 295** ✓, so line 1 holds two and «העברה לעמיתה» + «שחרור» take line 2.
  **A mis-tap costs one Esc**, because the trigger cannot page anybody — it opens a dialog with a default target and a separate send. **That is exactly why this control may be as large and prominent as an emergency deserves**, and why §2.3's machinery is not needed here.
- **in the SOS centre** — always available, to any of the five, with no assignment, for a staffer who is not in a room at all.

**Inside: the shipped `Modal` + `Select` + `Input` + «שליחת הקריאה».** **The controls are the shipped ones, named — not "a native `<select>`".** `Select` requires a `label: string`, wires `useId()` → `htmlFor`, `aria-invalid`, `aria-describedby` and `focusRing`, and carries the *"native `<select>` — no custom dropdown in v1"* decision in its own comment. **Written as a bare element a builder loses the label association and the focus ring, and axe sees the missing label but not the missing ring.** Both carry `className="min-h-11"` per F36's F-4, which is **not** an F15 F-6 violation because neither declares a `min-h-*` to lose. Footer is the house pattern: `ghost` dismiss (the shipped `rooms.cancel`) + `secondary` confirm.

⚠ **ON A REROUTED RAISE THE DIALOG DOES NOT CLOSE.** The ruling requires that when a named colleague is unreachable the raiser is told **on screen before she puts the phone down** — and delivering that once, as a transient polite cue written into `FloorPanel`'s single `role="status"` `<p>` **whose text the next cue overwrites**, at the exact moment a `<dialog>` closes and focus moves, is the classic case assistive tech drops or defers. **It is also unrecoverable**: `rerouted` is deliberately a fact about the **request** and not about the row, so **no `SosCentre` row can ever show it again.** Miss it and she believes Dana was paged, Dana was never paged, and **nothing on any screen will ever say otherwise.** So the `Modal` **stays open**, its body becomes «{{name}} לא מחוברת עכשיו. הקריאה עברה למנהלת המשמרת.» and one «הבנתי» closes it — **an explicit acknowledgement, which is the correct interaction weight for the one message the ruling mandates.**

⚠ **A FAILED SEND ALSO KEEPS THE DIALOG OPEN, with the note preserved.** A 5xx, a dropped connection, a wifi blackspot inside a curtain — **the single most likely real-world failure of a phone held behind a closed fitting-room curtain.** With no key the builder falls through to `errorMessage()`'s `FALLBACK_ERROR_MESSAGE` — «אירעה שגיאה בלתי צפויה. נסי שוב.» — **on the one screen in the product where «try again» alone is the wrong instruction and «open the curtain and shout» is the right one.** `sos.error.raiseFailed` = «הקריאה לא נרשמה. נסי שוב — או קראי בקול.» **A retry costs one tap and may duplicate, which D2 rules noise rather than corruption.**

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| the rerouted keep-open | close unconditionally | AC2 **RED** |
| **MOVE E** | delete it | a block asserting `document.activeElement` is «הבנתי» **RED** — focus in `<body>` inside an open `<dialog>` |
| **MOVE F** | delete it | the failed-send focus block **RED** |
| **MOVE G's `isConnected` branch** | always focus the trigger | the tile-released-underneath block **RED** (AC31) |
| **MOVE G's ref location** | key the effect on `RoomsPanel`'s `openDialog` | **every** MOVE-G block **RED** — run it once to prove the citation would have shipped the bug |
| the failed-send key | fall through to `FALLBACK_ERROR_MESSAGE` | AC30 **RED** |
| `onRaise`'s **optionality** | make it required | `RoomsPanel.test.tsx`'s shipped render helper breaks — **which is the diff D12's rule exists to catch.** Revert |
| the tile's `selfId` predicate | render on every occupied tile | AC22 **RED** |

- **Done when**: `make fe-test` + `make fe-build` green; axe **zero**; **`RoomsPanel.test.tsx` and `FloorPanel.test.tsx` shipped expectations unedited**; all three focus mutations performed and restored, each blurring explicitly; `make qa-greps` byte-identical. `git show --stat`.
- **Commit**: `feat(manage): the raise dialog, the tile's fourth control and its three dialog focus moves`

## Task 17 — `App.tsx`'s four lines, and **the manual screen-reader pass** (D11, D15 / e7 Risks)
`frontend/apps/manage/src/App.tsx`, `frontend/apps/manage/src/__tests__/App.test.tsx` (or the shipped location)

### The failing tests first

- the signed-in return is wrapped in `<SosProvider selfId={staff.id} role={staff.role}>` and `<SosOverlay onSessionEnded={…}/>` renders **before `<ConsoleShell>`**, so its controls precede every other focusable in DOM order;
- **AC27 end to end**: a 401 on a tick drops the console to `LoginForm`. ⚠ **`setStaff` already exists (`:129`) and `setStaff(null)` appears in exactly TWO places — `:142` (`api.me().catch()`) and `:164` (`handleLogout`) — verified. `onNavigate` is `setSection` (`:196`) and there is no fetch interceptor**, so the spec's earlier claim that *"`App` will show the login form on her next navigation"* was **false against shipped code**, and without the callback the console keeps rendering normally on eleven sections that poll nothing else while the emergency channel is dead and says so nowhere;
- ⚠ **`SectionKey` stays THIRTEEN and `NAV` stays THIRTEEN rows** — no new section, no new nav row. **`Nav.test.tsx` needs NO EDIT and that is an assertion, not an omission**: owner **twelve**, shift manager **ten**, floor roles **one**, `NAV_LABELS` **twelve** (C2). The assertion is an **empty `git diff`**.

### ⚠ The manual screen-reader pass — a gate condition on THIS PR, not a deferral

e7 Risks: *"Add an explicit manual screen-reader check to the design gate for F37 rather than trusting the mechanical pass."* **Run it here, on the assembled app, and record the result in the run report.** Named items, because a pass with no checklist is a claim:

1. **A card mounting announces exactly once**, as one atomic utterance: who, the room (**with DC-4's `sr-only` prefix**), the note.
2. **A second card arriving announces only itself** and does not re-announce the first.
3. **Escalation on an already-mounted card is SILENT**; a card that re-rises after a dismiss announces, because a re-rise is a fresh mount.
4. ⚠ **DC-1's `aria-labelledby={whoId}` on the focused `<article>` does NOT cause a double read** of the whole card. **If it does, the recorded one-line remedy is in Task 14** — it is not a redesign.
5. **Esc from a text input** moves focus to «אני מגיעה» and the input's value is intact.
6. **The overlay does not steal focus** from a nav button.

**What this pass cannot prove and F58 inherits** (Risk 6, four named cases): whether a real browser leaves a caret **usable** under a `position: fixed; inset: 0` sibling; whether a real screen reader announces a `role="alert"` that mounts inside a React commit; whether Tab and the capture-Esc route genuinely reach the overlay's controls from a form field; and **whether a caret in an obscured input is genuinely still usable**, which is the trade D15 takes in writing.

- **Done when**: `make fe-test` + `make fe-build` green; **`git diff main -- frontend/apps/manage/src/__tests__/Nav.test.tsx` EMPTY**; the manual pass run and its six items recorded. `git show --stat`.
- **Commit**: `feat(manage): mount the sos provider and its overlay above the console shell`

## Task 18 — Gates, the rebase and renumber, and the run report
No files.

Run the full verification below, perform the rebase and renumber, report what ran and what passed, and carry forward:

- **C1 / D8 — the migration number.** State the number the branch was **built** at, the number it **shipped** at, and the `alembic heads` output on `origin/main` that decided the second. ⚠ **TWO features held a `0020` when this branch started** — F41 (PR #39, open) and F58 (`.worktrees/floor-dispatch`, untracked) — so record which merged first and in what order. Confirm `alembic heads` prints **one** head on the rebased branch and that `test_exactly_one_migration_head` (`:57`) is green in `make test`. ⚠ **Rebase first, THEN read that test** — from an unrebased worktree there is only ever one `0020` to see, and two files claiming one revision string do **not** error: alembic warns, **dedupes to one script and drops the other**, which on a fresh database means one table is simply never created.
- **Every mutation-check, by name, with its result.** Six in Task 1, seven in Task 2, five in Task 3, seven in Task 4, six in Task 5, six in Task 6, five in Task 7, four in Task 8, seven in Task 9, three in Task 10, four in Task 11, five in Task 12, five in Task 13, twelve in Task 14, seven in Task 15, eight in Task 16. **Say plainly which were RUN and which were reasoned about — the answer must be "all run".** ⚠ **Three are expected to come back GREEN and must be recorded in the source beside the mechanism they failed to pin, not left as false confidence**: `populate_existing=True` in Task 2's fresh-session module, the explicit `tenant_id` predicate under live RLS, and `_parent_of` versus `downgrade(cfg, "-1")` (which reds only the day a later migration lands on it — F36's shipped defect). **F34, F57 and F36 each found a real vacuous test this way, and F36 ran nine mutations of which two came back green.**
- **The manual screen-reader pass (Task 17), item by item.** It is a **gate condition on this PR**.
- **DC-5 — hand F29 three numbers, not one, and do not let it rediscover them**: **~41 idle / ~57 with an alert open**, per 5 s per device, on the board screen (board 17 + floor 13 + SOS 11 / 27); **~11 idle / ~27 with an alert, on each of eleven sections where the shipped product does ZERO**; and `tenants.by_slug` now paid **three times per beat** on the board. **Plus the first unbounded number in the product: ~95 000 round trips per device per night** on a console left open through one 12-hour session, because this is the first loop with no idle stop. ⚠ **Record that the critic's ~39/~55 uses F57's pre-F36 floor tick of ~11 and is one feature stale**; ~41/~57 is the pair.
- **Spec Risk 1 — the pilot must be told, in words, before the first shift.** `usePoll` stops on `document.hidden`, so an SOS does **not** reach a phone whose screen is off, whose browser is backgrounded, or whose console tab is not active. F37 removes the idle stop so an *open, untouched* screen keeps receiving — **that is the half this feature can fix.** The other half needs push or a native shell, both forbidden by #32. **The failure mode is silence and the staffer will not discover it until it matters.**
- **Spec Risk 3 — the reachability read is an UPPER BOUND, twice over.** `session_ttl_seconds` is **12 hours**, longer than a shift, and nothing revokes on going home (`revoke_for_staff_user` fires on a password change and on deactivation only), so a staffer who signed in at 08:00 and left at 16:00 reads as reachable until 20:00 — `rerouted` stays false and the raiser is affirmatively told nothing. And it does not close the case where **every elevated staffer is logged out**: F51 guarantees an owner **exists**, not that she is signed in. **The thirty-second escalation stands in for both.** Recorded upgrade path, and this feature's own tick already provides it for free: **a `sessions.last_seen_at` heartbeat** — the poll is a signed-in staffer touching the server every 2–5 seconds — plus a freshness window turns the upper bound into a real presence signal. Four more lines extend it to the role audience. **Neither is built here.**
- **Spec Risk 5 — F20 gets one line**: purpose = floor emergency coordination; personal data = staff names, a room label, and **free text that may incidentally contain a customer's name**; retention = the alert row, with no clock of its own. **Nothing stops a staffer typing a bride's name into `note`, and validating it would be worse than the disease.** Fourth subject, same hand-off shape as F57's Risk 10 and F36's Risk 5.
- **Spec Risk 12 / deck F-9 — three loops on one screen is this architecture's ceiling and F58 will want a fourth.** The waitlist is the next thing that wants to be live on the board. **F58 must extend `/manage/floor` (F36's rule) and must not add a loop** — and **if a fifth `usePoll` caller ever appears, that is the moment to ask whether the console wants one multiplexed poll rather than N.** Recorded now, while the answer is still cheap.
- **Deck F-4 — `FloorPanel`'s `h2` now names one third of its own content, and the trigger has arrived ONE PR EARLY.** The panel is «צוות בקומה» and contains, in order, `SosCentre` («קריאות עזרה»), `RoomsPanel` («חדרי מדידה») and an unnamed staff list. F36's F-1 predicted three panels at F58; F37 delivers them now. **F37 does not rename `floor.heading`** — a copy change on a shipped panel is exactly the edit D12's zero-edit rule exists to catch. **Owner: team. Trigger: F58, now overdue rather than upcoming.**
- **Deck F-2 — an accidental accept is irreversible for up to `STALLED_AFTER`.** No un-accept verb (correctly out of scope, because it would give D4's `else: raise` a reachable input and make "who owns this" answerable two ways). **The honest statement is: an accidental accept costs up to two minutes of a raiser believing help is coming.** DC-1 turned §2.3's five structural guards into six by moving MOVE A and MOVE C off the accept control. `STALLED_AFTER` is one module constant if the pilot says two minutes is too long. **A named two-minute hole, not a claim of safety.**
- **Deck F-3 — «who is coming» renders on 2 of 13 sections.** `sos.acceptedBy` lives on a `SosCentre` row, the overlay never rises for the raiser, and no toast fires because the accept is another device's action. Bounded (both raise triggers are on the floor section, so she is there by construction) but recorded with a trigger. ⚠ **And DC-6: `sos.acceptedBy` = «{{name}} מגיעה.» is deliberately stronger than the fact** — the product knows an intention and not a walk — **which is F-2's residual wearing a sentence, and the copy row now says so.**
- **Risks 8, 9, 10, 11** carried verbatim: `details` on three codes (F36's Risk 8 named this PR as its trigger and `SOS_CLOSED`'s deliberate abstention is the assertion that the choice is still being made) · duplicate raises are possible and nothing measures them (D2 explains why the obvious index is defeated by NULL-distinctness) · the audit rows are still write-only, and `SOS_RAISED`'s `requested_target` is the only surviving record of a reroute with no way to read it without `psql` · `ar.ts` still has no general parity guard; F37's is scoped to `sos.*` and does not widen the gap.
- **The parked question**: *should the overlay rise for an alert raised before this device signed in?* It does — the poll returns every live alert and `for_me` knows nothing about when the session started. **That is almost certainly right** (an unanswered emergency is an unanswered emergency) and the alternative would silently hide exactly the alert that most needs answering. **The pilot settles whether it feels like a system that works or a system that shouts on login.**

No push, no PR from this task — the orchestrator owns review and shipping. **The shipping checklist below is the precondition list it runs.**

---

## Shipping checklist — run in this order, top to bottom

1. **`git show --stat` on every commit** confirms the lowercase pathspecs landed. `git add Backend/…` silently skips modified tracked files.
2. **`git diff main -- backend/tests/conftest.py` is EMPTY.** The harness is shipped code — a non-empty diff means something was patched that should not have been.
3. **No lower-numbered migration is unmerged.** ⚠ **Two contenders**: `gh pr list` (F41 is #39) and `git log feature/floor-dispatch` / `ls .worktrees/floor-dispatch/Backend/migrations/versions`. Check LOOP-STATE's `current:` block too.
4. `git fetch origin && cd "…/Backend" && uv run python -m alembic heads` **on a checkout of `origin/main`**. Note the number.
5. **Renumber the migration to head + 1** — three edits: the filename, the `revision` literal, the `down_revision` literal. Amend the migration commit (it is the branch tip by Task 1's instruction).
6. **Rebase onto `origin/main`.** Re-run `alembic heads` **on the rebased branch** and confirm a **single** head. Run `make test` and confirm `test_exactly_one_migration_head` (`:57`) is green. ⚠ **In this order — the duplicate-revision warning is invisible from an unrebased worktree.**
7. **`bash "<scratchpad>/run-db-tests.sh"` green on the rebased branch.**
8. Full local gate (below), all six targets green.
9. **`git diff main --stat` names none of**: `frontend/apps/manage/src/__tests__/Nav.test.tsx` · `frontend/apps/manage/vite.config.ts` · `frontend/scripts/qa-greps.sh` · `frontend/packages/ui/**` · `backend/tests/conftest.py` · `backend/app/worker.py` · `backend/app/booking/**` · `backend/app/auth/**` (beyond nothing — F37 touches none of it) · `backend/app/catalog/**`. **That list is AC20(b) + AC24 + AC25(b) mechanised.**
10. **`git diff main -- frontend/apps/manage/src/__tests__/FloorPanel.test.tsx …/BoardSection.test.tsx …/RoomsPanel.test.tsx` shows ADDED blocks only** — no edit to an existing expectation. That is D12's acceptance rule and the instrument Risk 7 relies on.
11. **`git diff main -- frontend/apps/manage/src/lib/usePoll.ts` is readable in ONE SCREEN** — D12's own stated bar for eight lines.
12. `make qa-greps` output **byte-identical to the pre-Task-11 baseline**.
13. **The manual screen-reader pass (Task 17) is recorded, item by item.** It is a gate condition, not a nicety.
14. Open the PR. The three gating jobs are `Backend (lint, types, tests)`, `Frontend (lint, types, build)`, `Frontend E2E (Playwright + axe)`.

---

## Verification — the full local gate sequence

```
make lint      # Backend: ruff check . && ruff format --check . && mypy app tests
               #   + Frontend: pnpm -r lint && pnpm -r typecheck
               #   + bash frontend/scripts/qa-greps.sh
make test      # Backend: pytest -m "not db" -q   (includes test_exactly_one_migration_head)
bash "<scratchpad>/run-db-tests.sh"
               # recreates f37_test on the local 16.14 cluster, exports
               # TEST_POSTGRES_SUPERUSER_URL, runs pytest -m db
               # ⚠ NO conftest patch and NO revert — the hatch is shipped
make fe-test   # Frontend: pnpm -r --if-present test
make fe-build  # Frontend: pnpm -r build
make e2e       # Frontend: pnpm -r build && playwright install --with-deps chromium && pnpm e2e
```

**Green looks like:**

- **`make lint`** — ruff clean, `ruff format --check` clean, **mypy zero errors over `app` and `tests`**, `pnpm -r lint` and `pnpm -r typecheck` clean across all four workspace packages (⚠ **`react/rules-of-hooks: error` is enabled in `frontend/.oxlintrc.json` and is precisely why `SosProvider` is a provider and not a hook in `App`** — a hook after `App`'s two early returns is a lint failure here, not a runtime surprise), and `qa-greps.sh` **exit 0** printing **exactly the pre-Task-11 baseline**.
- **`make test`** — all fast tests pass. `test_floor_api.py` green with `FLOOR_ROUTES` at **eighteen** and `SPEC_ERROR_CODES` at **nine**; `test_sos_api.py` green with the `SosAlertView` key set pinned by set equality and the three-failure-mode walk; `test_sos_service.py` green with the `_escalated` boundary, the `_stalled` boundary and the whole `for_me` matrix; `test_floor_validation.py` and `test_frontend_constant_parity.py` green; **`test_staff_role_gating.py` green with `FLOOR_OPEN` at fourteen and the intersection classifier UNTOUCHED**; `test_spa_serving.py` green **unedited**; `test_migrations.py`'s single-head guard green; the `db`-marked modules **collected and deselected**.
  ⚠ **Two `test_config.py` failures are always false locally** — `Backend/.env` leaks `MEDIA_BUCKET`. CI is green. **Do not chase them.**
- **the local db suite** — the captured baseline **plus** F37's new cases in `test_migrations.py`, `test_sos_repositories.py`, `test_sos_db.py` and `test_sos_isolation.py`, all green. The 9 `test_media_upload_s3.py` cases need MinIO and are excluded — **expected; F37 touches no S3.**
- **`make fe-test`** — `api.test.ts`, `i18n.test.ts`, the `usePoll` blocks (**shipped blocks unedited**), `sos.test.tsx`, `SosOverlay.test.tsx`, `SosCentre.test.tsx`, `SosRaiseDialog.test.tsx`, `FloorPanel.test.tsx` and `RoomsPanel.test.tsx` (**shipped expectations unedited**) all green; **axe at zero violations on the overlay, the centre and the dialog**; every mutation-check performed and restored.
- **`make fe-build`** — both apps build; no unused-import or unused-variable TS error (`TS6133` is the one this feature's refactor invites).
- **`make e2e`** — **unchanged. F37 adds no e2e**, and the reason is F34's, F57's and F36's verbatim: the console's entire e2e surface is two login-screen tests because `vite preview` runs with no backend (`e2e/a11y.spec.ts:10-13`). **F58 owns the `/manage/**` interception harness.**
- **CI additionally** — the same db suite against Testcontainers, where the pinned CHECK and `indexdef` literals are **re-read off the CI server** rather than off the local one. ⚠ **A first CI red on a test bug here is budgeted**; check `continue-on-error` on the job before believing it.

---

## What a local run cannot prove

The local harness closes almost all of the gap. What is left:

| Task | The local run proves | CI-only / not provable at all |
|---|---|---|
| 1 | the table, the CHECK, the index, the zero-unique-index count, the round trip via `_parent_of`, the RLS/GRANT loop — **all of it, against real Postgres 16.14** | that the deparsed literals are identical on the CI server's Postgres build. They should be — same 16.x deparser — and the assertion **re-reads** rather than transcribes, so a difference is a red test and not a silent pass |
| 4 | the 30-second and two-minute boundaries **exactly**, under a frozen clock on both operands, with **no sleeping** | nothing — this is the task the injected clock exists for |
| 6, 7, 8 | every forced interleave and every mutation, including the four no fast test can see (`status='open'`, `populate_existing`, the idempotence ordering, the `from_status` capture) | the same, on the container superuser / app-role split CI builds |
| 10 | the isolation suite in full, including the vacuity mutation-check | the same |
| 14, 15, 16 | **jsdom focus behaviour, which is not a browser** — a disabled element is not blurred, which is why every focus test blurs explicitly | ⚠ **NOTHING. A real browser's focus behaviour on `disabled` is proven by neither the local run nor CI.** It is proven by **F58's interception harness, which does not exist.** Deck F-8 and spec Risk 6 |
| 14, 17 | that a `role="alert"` element exists with the right text and never changes | ⚠ **whether a real screen reader announces a `role="alert"` that mounts inside a React commit; whether a caret under a `position: fixed; inset: 0` sibling is genuinely still usable; whether Tab and the capture-Esc route reach the controls from a form field.** **The manual pass (Task 17) is the interim evidence and is a gate condition; F58 inherits all four named cases** |
| — | — | `test_media_upload_s3.py` (MinIO; F37 touches no S3) |

**Task 9 is the milestone**: all eighteen routes, both new codes, the whole payload and the audience filter are exercised end to end with **no Postgres**.

---

## Task-by-task file manifest

| Task | New (**✚**) | Modified |
|---|---|---|
| 0 | — | `.planning/plans/sos-paging.md`, `.planning/specs/sos-paging.md`, `.planning/design/screens/sos-paging/design.md`, `.planning/design/screens/sos-paging/copy.md` |
| 1 | `backend/migrations/versions/00NN_sos_alerts.py`, `backend/app/models/sos_alert.py` | `backend/app/models/constants.py`, `backend/tests/test_migrations.py` |
| 2 | `backend/app/db/repositories/sos_alerts.py`, `backend/tests/test_sos_repositories.py` | `backend/app/db/repositories/sessions.py` |
| 3 | `backend/tests/test_sos_api.py` *(stub — the 409 bodies)* | `backend/app/floor/validation.py`, `backend/app/floor/schemas.py`, `backend/app/main.py`, `backend/tests/test_floor_validation.py`, `backend/tests/test_floor_api.py`, `backend/tests/test_frontend_constant_parity.py`, `frontend/apps/manage/src/validation.ts` |
| 4 | `backend/tests/test_sos_service.py`, `backend/tests/test_sos_db.py` | `backend/app/floor/service.py` |
| 5 | — | `backend/app/floor/service.py`, `backend/tests/test_sos_service.py`, `backend/tests/test_sos_api.py`, `backend/tests/test_sos_db.py` |
| 6 | — | `backend/app/floor/service.py`, `backend/tests/test_sos_service.py`, `backend/tests/test_sos_db.py` |
| 7 | — | `backend/app/floor/service.py`, `backend/tests/test_sos_service.py`, `backend/tests/test_sos_db.py` |
| 8 | — | `backend/app/floor/service.py`, `backend/tests/test_sos_service.py`, `backend/tests/test_sos_db.py` |
| 9 | — | `backend/app/floor/router.py`, `backend/app/floor/service.py`, `backend/tests/test_floor_api.py`, `backend/tests/test_sos_api.py`, `backend/tests/test_staff_role_gating.py` |
| 10 | `backend/tests/test_sos_isolation.py` | — |
| 11 | — | `frontend/apps/manage/src/lib/usePoll.ts`, `…/__tests__/usePoll.test.ts` |
| 12 | — | `frontend/apps/manage/src/api.ts`, `…/validation.ts`, `…/i18n/he.ts`, `…/i18n/ar.ts`, `…/__tests__/api.test.ts`, `…/__tests__/i18n.test.ts` |
| 13 | `frontend/apps/manage/src/lib/sos.tsx`, `…/__tests__/sos.test.tsx` | — |
| 14 | `frontend/apps/manage/src/components/SosOverlay.tsx`, `…/__tests__/SosOverlay.test.tsx` | — |
| 15 | `frontend/apps/manage/src/components/SosCentre.tsx`, `…/__tests__/SosCentre.test.tsx` | `…/components/FloorPanel.tsx`, `…/__tests__/FloorPanel.test.tsx` |
| 16 | `frontend/apps/manage/src/components/SosRaiseDialog.tsx`, `…/__tests__/SosRaiseDialog.test.tsx` | `…/components/FloorPanel.tsx`, `…/components/RoomsPanel.tsx`, `…/__tests__/RoomsPanel.test.tsx` |
| 17 | — | `frontend/apps/manage/src/App.tsx`, `…/__tests__/App.test.tsx` |
| 18 | — | — |

**Never modified, and that is an assertion, not an accident:** `frontend/apps/manage/src/__tests__/Nav.test.tsx` (AC20b, C2) · `frontend/apps/manage/vite.config.ts` (AC24, D9) · `backend/tests/test_spa_serving.py` (AC24) · `backend/tests/test_tenant_isolation.py` (AC11) · `backend/tests/conftest.py` · `backend/app/worker.py` (**AC25b — a ZERO-LINE diff, and `poll_once` keeps running exactly two jobs**) · `frontend/scripts/qa-greps.sh` (D17) · `frontend/packages/ui/**` (deck P-9 — no component, variant, colour, token, formatter or motion rule) · `frontend/apps/manage/src/lib/elapsed.ts`, `…/lib/jerusalem.ts`, `…/lib/roles.ts` (all three already answer) · `backend/app/db/repositories/fitting_room_assignments.py` (⚠ **`violated_index()` is READ and cited, never re-derived and never imported — F37 needs no constraint discrimination at all, because there is no unique index to violate**) · `backend/app/booking/**`, `backend/app/auth/**`, `backend/app/catalog/**`.

---

## Testing plan → spec criteria

| Spec criterion | Where |
|---|---|
| **AC1** — a raise has exactly three failure modes; nine boutique-state rows all answer **200** | `test_sos_api.py::test_nothing_about_the_boutique_can_refuse_a_page` (fast) + `test_sos_db.py` (db) — Task 5 |
| **AC2** — a named target with no live session is rerouted; the dialog **stays open** with «הבנתי» | `db test_a_logged_out_target_is_rerouted_to_the_shift_manager` (Task 5) + `SosRaiseDialog.test.tsx` (Task 16) |
| **AC3** — **FIRST-ACCEPT-OWNS**, forced interleave, one owner, one audit row, the loser 409'd **by name** | `db test_a_second_accept_landing_in_the_gap_is_refused_and_names_the_owner` — Task 6, three named mutations |
| **AC4** — re-accept / second resolve / resolve-of-cancelled are 200 with **no** audit row | `test_sos_db.py` — Tasks 6, 7 |
| **AC5** — `_escalated` and `_stalled` are **exact**, including the `>=` boundary and the negative delta | `test_sos_service.py` (**pure branches, no DB**) + the frozen-clock `db` rows — **Task 4** |
| **AC6** — `for_me` is exact as a matrix, **including the raiser on her own stalled page** | `test_sos_service.py` — Task 4 |
| **AC7** — the audience filter is exact | `db test_sos_db.py` (Task 4/9) + `test_sos_api.py` (Task 9) |
| **AC8** — **NO CUSTOMER DATUM**; the key set pinned by **set equality**; a negative over the whole body | `test_sos_api.py::test_the_sos_payload_carries_no_customer_datum` — **Task 9, and it is the only assertion that can fail** |
| **AC9** — cancel-of-accepted is a 409 naming the acceptor; resolve is a 200; a second cancel is a 200 | `test_sos_db.py` — Task 8 |
| **AC10** — tenant B reaches nothing of A's; every attempt is a 404 indistinguishable from missing | `test_sos_isolation.py` (db, **app role only**) — Task 10 |
| **AC11** — one `enable_tenant_rls`; `test_every_tenant_id_table_has_forced_rls` green **with no edit** | `test_tenant_isolation.py:203` (db, **unedited**) — Task 1 |
| **AC12** — the CHECK and the index pinned **byte-identical from CAPTURED literals**; **zero** non-primary unique indexes; the round trip via **`_parent_of`** | `test_migrations.py` (db) — Task 1 |
| **AC13** — `FLOOR_ROUTES` **eighteen**, `FLOOR_OPEN` **fourteen**, the four tightened paths absent, the classifier untouched | `test_floor_api.py`, `test_staff_role_gating.py` — Task 9 |
| **AC14** — **THE OVERLAY DOES NOT STEAL FOCUS**, three branches, three delete-the-guard mutations | `SosOverlay.test.tsx` — **Task 14**, each blurring explicitly |
| **AC15** — MOVES B, C and D, each mutation-checked, **never `<body>`**. ⚠ **DC-1 moves C's destination to the card container** | `SosOverlay.test.tsx` — Task 14 |
| **AC16** — the `role="alert"` text is **byte-identical from mount to unmount, across escalation and stall** | `SosOverlay.test.tsx` — Task 14, mutation: move the clause inside |
| **AC17** — Esc, all four cases; the capture handler and its two guards | `SosOverlay.test.tsx`, `SosRaiseDialog.test.tsx` — Tasks 14, 16 |
| **AC18** — pausing the board **freezes the centre and does NOT stop the overlay**; the raise exemption | `SosCentre.test.tsx` + `SosOverlay.test.tsx` — Task 15 |
| **AC19** — the SOS loop **never idle-stops**, including after `idleStopMs` flips to `null` with a timer armed | `usePoll` tests + `sos.test.tsx` — Tasks 11, 13 |
| **AC20a** — the default `usePoll` path pinned **mechanically** | `usePoll` tests — Task 11 |
| **AC20b** — ⚠ **the tick rate switches on the tick that OBSERVES the alert**, driven by one real tick | `usePoll` tests + `sos.test.tsx` — Tasks 11, 13. **Mutation: derive the gap from React state → red; the weak rerender-then-tick block stays green, which is why both exist** |
| **AC20(b) review** — shipped expectations unedited; `SectionKey` and `NAV` stay thirteen | `git diff`, shipping checklist steps 9–11 |
| **AC21** — a seamstress sees none of the three controls she may not use; an owner sees all three | `SosCentre.test.tsx` — Task 15 |
| **AC22** — the raise control appears on **her** tile and no other, and in the centre for everyone | `RoomsPanel.test.tsx`, `SosCentre.test.tsx` — Tasks 15, 16 |
| **AC23** — Hebrew-first RTL on `packages/ui` tokens; `ar[key] === he[key]` for every `sos.*` key; no `/נשלח\|תישלח\|בדרך/`; axe zero | `i18n.test.ts` (**four edits**), `SosOverlay.test.tsx` — Task 12 |
| **AC24** — `vite.config.ts` unchanged and `test_spa_serving.py` green with no edit | `test_spa_serving.py` (fast, **unedited**) + the deliberate prefix mutation in Task 9 |
| **AC25a/b** — `poll_once` still runs **exactly two** jobs; `worker.py` has a zero-line diff | `test_worker*.py` + `git diff` — Task 18 |
| **AC26** — ⚠ **the accept path does not silently drop a page**: `_stalled` re-rises for elevated callers | `test_sos_service.py` matrix row + one `db` row seeding `acknowledged_at` — **Task 4, and it is the ONLY test that fails when `_stalled` goes** |
| **AC27** — a 401 fires `onSessionEnded` **once**; a 403 and a backed-off loop render the strip | `SosOverlay.test.tsx`, `App.test.tsx` — Tasks 14, 17 |
| **AC28a/b** — a dismissal is never permanent: the composite key re-rises once, and the affordance | `SosOverlay.test.tsx` — Task 14, each mutation-checked |
| **AC29** — an accept from a **non-floor** section produces a `role="status"` through the shipped toast | `SosOverlay.test.tsx` — Task 14 |
| **AC30** — a failed raise keeps the dialog open with the note preserved and `sos.error.raiseFailed` | `SosRaiseDialog.test.tsx` — Task 16 |
| **AC31** — the dialog's focus return runs from **`FloorPanel`'s own** trigger ref, never `<body>` | `SosRaiseDialog.test.tsx` — Task 16 (MOVE G) |

---

## What could go wrong in review

Every item here is a **recorded ruling or a verified finding**. A reviewer who raises one should find the reasoning rather than file a finding.

1. **"There is no unique index, so nothing stops two accepts."** **D2, and the guarantee is structural anyway.** The conditional `UPDATE … WHERE status='open'` constrains a **transition**, not a **population** — Postgres's row-level write lock serialises the two contenders and the loser's predicate then matches zero rows. This is the third case in the codebase's running argument, beside F13's lock (a **count**, i.e. read-then-write), F51's lock (*"at least one"*, which **no index can express**) and F36's index (*"at most one"*, which is exactly what an index says).
2. **"F36's claim uses `begin_nested()` and a constraint-name discriminator; this should too."** **No: there is no index, therefore no `IntegrityError`, therefore nothing to recover from.** `violated_index()` is cited in the manifest precisely so nobody imports it. ⚠ **And if anybody ever DOES add an index here, the working expression is `getattr(getattr(error.orig, "__cause__", None), "constraint_name", None)`** — the obvious `error.orig.constraint_name` is **`None` for every violation there has ever been**, because SQLAlchemy's asyncpg dialect rebuilds the error as a formatted string and raises it `from` the original.
3. **"The obvious unique index would prevent duplicate pages."** **D2, and it is defeated in exactly the case that matters.** `(tenant_id, raised_by, target_staff_user_id) WHERE status='open'` — **Postgres treats NULLs as distinct**, and `target_staff_user_id IS NULL` is *the shift-manager route*, the single most common target and the destination of every reroute. **The index would refuse the rare duplicate and permit the common one: a guarantee a reviewer will believe and that is not there.** `COALESCE` to a sentinel uuid is a lie in the schema; dropping the target from the key forbids the legitimate double page.
4. **"Escalation should be a worker job."** **D6, three grounds, each sufficient.** `worker.py` ticks at **60 s** (`config.py:124`, `:157`), so a worker-stamped escalation arrives **up to a full minute late — twice the requirement**; it introduces a **write that races a concurrent ack**; and it runs `O(tenants)` queries per tick **even when no boutique in the country has an open alert**. The read-time predicate adds zero latency beyond the poll, cannot race, and is the house compute-on-read pattern. **AC25 is the assertion: `worker.py` gets a zero-line diff and `poll_once` still runs two jobs.**
5. **"`_stalled` is a second escalation tier and the ruling forbids one."** **It is not, and the distinction is stated in Out of scope.** The ruling's tier is 30 s → shift manager **on an OPEN alert**. `_stalled` is the **same** audience (elevated) and the **same** mechanism (a read-time boolean), applied to the **ACCEPTED** state, where the ruling's tier does not reach at all. **Without it the accept path re-opens the silent drop the create path closes** — the instant anybody taps «אני מגיעה» the alert stops rising on every device in the boutique, forever, **and the raiser's screen reads «דנה מגיעה» while nobody is walking.** Widening the stall's audience beyond elevated **would** be a second tier and stays out.
6. **"The clamp is missing from `_escalated` and `lib/elapsed.ts` has one."** **Deliberate, and its named mutation came back GREEN in spec review.** `elapsedMinutes` returns a **rendered number**, so a negative delta ships «כבר -1 דק'» to a screen. `_escalated` returns a **boolean against a one-sided positive threshold**: `timedelta(seconds=-5) >= timedelta(seconds=30)` is already `False`, **byte-identical to the clamped result**. **A clamp there pins nothing**, and the negative-delta case ships as an **assertion** rather than as false confidence.
7. **"`usePoll` grew and three shipped test files did not change."** **That IS the acceptance rule** (D12, F36's D15 one level down). They are the only thing that can tell a faithful extension from a subtly different one. **A reviewer seeing an edit to a shipped expectation should stop and read D12.**
8. **"`intervalMs` takes a function, which is over-engineering for a two-value switch."** **D11/D12, and the state-derived version costs a silent five-second hole at the worst moment.** `succeeded()` and `reschedule()` run in the **same microtask chain as the response**, before React commits the state that would flip the gap — so the tick that first observes an alert re-arms at **5 000 ms**, exactly when the raiser is waiting to see who is coming. ⚠ **And the obvious test passes over it**, which is why AC20b names *one real tick*.
9. **"The idle stop is disabled, which is an SC 2.2.2 violation."** **D11, three-part argument.** In the idle state the component renders **nothing** — the criterion governs *auto-updating information presented in parallel with other content* and there is no content to pause. In the alert state **nothing auto-updates**: static text, an **absolute** «מאז 11:20», **no countdown and no live counter** — which D15 forbids, and that is what keeps the argument true rather than merely claimed. The "hide" mechanism **exists**: «הסתרה», plus Esc. **And a phone in an apron pocket untouched for eleven minutes would otherwise silently stop receiving pages.**
10. **"The overlay puts a fixed layer over a form and that is a focus trap."** **D15, and it is the opposite.** It is **not** a `<dialog>`, **not** `showModal()`, **not** `inert` — each of those moves focus **by definition**. It is **visually blocking and interactively non-blocking**: a pointer user dismisses in one tap with no state lost, **a keyboard user's caret never moves and her form is intact**, and the alert is announced either way because `role="alert"` interrupts a screen reader **without** taking focus. ⚠ **The hazard that creates — she is typing into a field she cannot see — is named in writing (deck §9.3), bounded by four things, and handed to F58 as a real-browser case.** It is a trade taken, not one missed.
11. **"MOVE A lands on the card and the deck said the accept button."** **DC-1, and §2.3 was selling the hazard as a benefit.** MOVE A fires *iff* `activeElement === document.body` — **the state in which the next Space is a page-scroll** — so landing on «אני מגיעה» converts that keypress into an **irreversible accept** on top of a two-minute hole. MOVE C is worse: it parks focus on a **different emergency's** accept control. **Accept stays first in DOM, reach costs one Tab, and the Esc route-in still lands on the ack because that is a deliberate keypress.**
12. **"The overlay is red but the cards are white — the ruling said full-screen red."** **Deck §2.1, and the field IS full-screen red at every width.** On `#A03232` the shipped focus ring is **1.22:1** (recomputed at this gate — DC-10), `text-ink` is **2.25:1** and `Button danger` is **1.00:1** — so the product's whole component vocabulary either fails AA or vanishes, **on the one console surface where IS 5568 is legally binding and where axe cannot report it** (its contrast rule computes an element against its own background). **And the call-site patch is not available**: `cn()` is a plain join and two `outline-color` utilities resolve by stylesheet order (F15 F-6). **Full-screen red survives literally; the words move onto paper.**
13. **"`sos.acceptedBy` says «דנה מגיעה» and the product cannot know she is walking."** **DC-6, confronted rather than defended.** The claim is **deliberately stronger than the fact** and the copy row now says so, cross-referencing deck F-2. It is kept because the button-word symmetry is real — she pressed «אני מגיעה» and the raiser reads the same verb, one word across two screens — and because «{{name}} אישרה את הקריאה.» is system-register on the one screen that must read like a person. **`_stalled` at two minutes is the mechanism that bounds it, and it is the whole reason `_stalled` exists.**
14. **"There is an `sr-only` span inside the `role="alert"` region and §9.1 says there is no visually-hidden copy."** **DC-4, and it is a one-word LABEL, not a copy of any value.** `CreateRoomRequest.label` carries **no `Field` bound** (its own docstring, `schemas.py:296-301`) and `0019` puts no CHECK on content, so a boutique that types «2» is fully supported and the atomic utterance would otherwise be «דנה כהן קוראת לעזרה 2 צריך סיכות». **An `aria-label` on the `<p>` is not available** — ARIA prohibits naming on `role=paragraph`/generic — **so the deck's own em-dash-value-last shape would have shipped a name nothing reads.**
15. **"`SosCentre` duplicates `FloorPanel`'s error state."** **DC-7, deliberately.** Sharing would route an SOS 409 into a **staff card's** alert node through `FloorPanel.tsx:270-271`'s **unconditional** focus effect — the exact guard-less shape MOVE D warns against — and `cardError.id` is a staff card id, so the render predicate at `:718` would collide semantically. **MOVE H owns its own pair with an in-row guard, and `FloorPanel`'s pair is untouched, which is also what keeps its shipped expectations unedited.**
16. **"axe passes, so the a11y work is done."** **D18, and it is a legal bar here.** axe cannot see a focus move that **never happened** (four shipped instances) and cannot see one that **should not have happened** — the new failure class this feature could introduce. It has **no rule for SC 2.2.2**. It cannot see a focus ring that is the wrong colour against a **parent's** background. **F57's own success-path focus test was VACUOUS because jsdom does not blur a disabled element**, and every focus test here blurs explicitly and carries a named mutation that was **run**. **The manual screen-reader pass is a gate condition on this PR.**
17. **"`FLOOR_OPEN` grew by five and nothing was tightened — surely accept should be gated."** **D9, F36's D8 criterion verbatim.** A `RoleGate` can express only a **pure role predicate**. Every rule here **reads the row** — `target_staff_user_id`, `raised_by`, `accepted_by` — and **there is no gate that can say "the person this alert names"**. ⚠ **And a 403 is TERMINAL for the whole floor screen** (`terminalOf` → `"access"`, `FloorPanel.tsx:441-458` clears every card), so a rendered control reaching an unreachable route blanks a seamstress's only screen. **Which control EXISTS is the rendered form of the rule.**
18. **"Two files claimed revision `0020` and the merge was clean."** **C1, and it is why the rebase precedes the read.** Alembic keys revisions by the **string**, not the filename, so it does not error — it warns, **dedupes to one script and drops the other**, and on a fresh database one table is never created. **F41's own migration header records living exactly this.** `test_exactly_one_migration_head` (`:57`) catches it in half a second **after** the rebase.
19. **"The raise takes a `fitting_room_assignment_id` from the body — that is F57's named hazard."** **D3, and the hazard is about the ACTOR, not the location — but the location gets the same treatment anyway.** `raised_by` is the session cookie's `StaffContext` and never the body (`ForbidExtraModel` refuses a body that tries, **asserted**), so `_authorize` is not called at all. And the room pointer is read with **`staff_user_id = actor.id`**, because F36's floor payload hands every tile's `RoomAssignment.id` to all five roles: **«wrong room» is strictly worse than the safe, designed «no room»** — the responder walks to a stranger's curtain.
20. **"The reroute claims a colleague is unreachable on the strength of a `sessions` row."** **D3 and Risk 3, stated honestly rather than claimed.** A live row proves **a session, not a screen**: the TTL is **12 hours**, nothing revokes on going home, and `usePoll` stops on `document.hidden`. **So the read is a cheap UPPER BOUND** — `rerouted: false` claims only *"she has not signed out"*, and `rerouted: true` is the case it genuinely closes. **The thirty-second escalation is the real safety net, not this read**, and the copy is worded for the negative case for exactly that reason.

---

## Out of scope (unchanged from the spec)

Browser push, service workers, APNs, FCM, SMS, a phone call, a `message_log` row, a `MessageKind` value — **#32 and the ruling: in-app only** · **F35's durable staff bell** — dropped from this feature's deps by the ruling and still queued as the later durable surface · sound, vibration, flashing, any motion at all · **a durable `escalated_at`** — D6's recorded upgrade path · **any worker job** — AC25's zero-line `worker.py` diff · **a second escalation tier for an OPEN alert**; widening the stall's audience beyond elevated · auto-resolve, auto-expire, auto-cancel · **an un-accept verb** — it would give D4's `else: raise` a reachable input and make "who owns this" answerable two ways · a chat thread, a reply, an ETA · severity levels, priorities, per-role SLAs, response-time analytics, a history read — pre-decided #28, D1's columns, D2's index · **`sos_alert_targets`** — the epic justified it by role fanout and the ruling replaced fanout with one target · **any unique index on `sos_alerts`**, any advisory lock, any `begin_nested()` · a history index — F36's had **named readers**; this one would have none · paging a role other than shift manager · an on-shift roster column — F40's · cross-tenant or cross-branch paging · retention of alert rows — F20's, Risk 5 · a fourteenth nav section — `SectionKey` and `NAV` stay **thirteen** · a second pause control or a third SC 2.2.2 mechanism on the board · any `packages/ui` component, variant, colour, token, formatter or motion rule · any customer datum on the SOS payload · a `vite.config.ts` or `qa-greps.sh` edit · **any `/manage/**` e2e — F58 owns the interception harness** · `queue_ticket_id` and every dispatch verb — **F58, which is building with its own migration right now**.
