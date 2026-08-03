# Plan: Feature 36 — Fitting-room registry + staff↔client↔room↔dress assignment (Epic E7, floor-management program iteration 3)

**Status**: Gate 2 self-approved 2026-08-03 under Interview Q1 (F36 is none of Q1's enumerated exceptions — no payments, no refunds, no privacy-law text, no billing). **Design gate self-approved** by the 2026-07-31 ruling; the deck and the copy deck are on disk, mechanically verified, and **the design critic's verdict is REVISE** — its fourteen required changes are folded in below as **DC-1 … DC-14** and each has an owning task. *The gate goes away; the design work does not.*

**Spec**: `.planning/specs/fitting-rooms.md` (1 058 lines, D1–D18, 25 ACs, 41 review findings / 40 applied) · **Design deck**: `.planning/design/screens/fitting-rooms/design.md` (723 lines, §0–§12, ten findings F-1…F-10) · **Copy deck**: `.planning/design/screens/fitting-rooms/copy.md` (284 lines, 69 keys) · **Branch**: `feature/fitting-rooms` · **Worktree**: `.worktrees/fitting-rooms` · **Created**: 2026-08-03

TDD throughout. Every task states its **failing test first**, then the code that makes it pass, then the exact files, then how to verify, then the commit message.

---

## ⚠ Three process facts that changed since the last plan in this program

**1. `db`-marked tests run locally, and the escape hatch is now SHIPPED CODE — there is no patch to apply and no revert obligation.** F19 landed a permanent, documented override in `backend/tests/conftest.py:82-122`: `TEST_POSTGRES_SUPERUSER_URL` replaces the Testcontainers cluster with one you started yourself, and its docstring states in writing why the constraint it works around is *"permanent, not incidental"*. **The F33 plan's «REVERT `conftest.py` BEFORE EVERY COMMIT» ritual is gone.** Verified: `git status --short backend/tests/conftest.py` is empty and the override is on `main` in `3a70600`.

Postgres **16.14** is live via Homebrew (probed: both `127.0.0.1:5432` and the `/tmp` socket accept asyncpg connections; superuser `mrwen`; no Docker). The runner, which the builder writes once into the scratchpad and never commits:

```bash
# scratchpad/run-db-tests.sh
set -euo pipefail
dropdb   --if-exists -h 127.0.0.1 -U mrwen f36_test
createdb              -h 127.0.0.1 -U mrwen f36_test
export TEST_POSTGRES_SUPERUSER_URL='postgresql+asyncpg://mrwen@127.0.0.1:5432/f36_test'
cd "/Users/mrwen/Documents/Github/Ryan + rawad + mrwen/.worktrees/fitting-rooms/Backend"
uv run pytest -m db -q --ignore=tests/test_media_upload_s3.py
```

**Capture the baseline on the branch's base commit BEFORE Task 1** and record the number in the run report. Do not hardcode a count from any earlier plan — F19, F33 and F53 all added `db` cases since the last one was written. The 9 `test_media_upload_s3.py` cases need MinIO and are excluded; F36 touches no S3.

**This is what made F34, F57 and F53 green on their first CI run, and F36's races are harder than any of theirs.** Six of the twelve mutation-checks in this plan **cannot be performed at all without a real Postgres** — a monkeypatched repository never stamps anything, never raises `IntegrityError`, and never takes a row lock.

**2. Path hygiene, unchanged and still load-bearing.** The repo path contains a **space** and a **`+`** — quote every shell path. And git tracks `backend/` / `frontend/` **lowercase** while the on-disk directories are `Backend/` / `Frontend/`: `git add Backend/…` **silently skips modified tracked files**. Lowercase every pathspec and verify every commit with `git show --stat`. (Proof it still bites: `git log -- Backend/tests/conftest.py` returns nothing while `git log -- backend/tests/conftest.py` returns three commits.)

**3. `make lint` runs `frontend/scripts/qa-greps.sh`, and it reaches `apps/manage/src` in exactly one place.** Verified at `qa-greps.sh:17` — `SRC="apps/storefront/src"`, so the **ten `check` calls do not read this feature's code at all**. But the trailing **date-reads review block** (`:62-67`) greps `apps/storefront/src apps/manage/src packages/ui/src` for `getDay()` / `getDate()` / `toLocaleDateString` / `toLocaleTimeString` and for a single-line `Intl.DateTimeFormat(...)` without `timeZone`. **F36 computes elapsed minutes and is the feature most likely to reach for a formatter** (spec D17: *"'elapsed time' invites a date library, and it must not"*). Capture the baseline before the first frontend task and diff it after.

---

## What moved since the spec was written — **thirteen corrections**, C1–C13

The spec was written on 2026-08-03. **F53 (customers CRM, PR #35) merged the same day, after it**, and F19 (PR #34) merged the same morning. Every citation below was re-opened and re-read on this tree at `18127e7`. The spec is binding and D1–D18 are **not** re-litigated; these are the places where the document disagrees with the code.

| The spec says | Actually, now | # |
|---|---|---|
| `main`'s head is `0016_deposit_flow.py` (D5, D5's log entry) | `alembic heads` → **`0017 (head)`**. `0017_customer_crm_fields.py` is F53's. **Third move in two days** — which is D5's own point | **C1** |
| `SectionKey` stays **eleven** members; `NAV` stays **eleven** rows; `Nav.test.tsx`'s counts stay **owner ten / shift-manager eight** / floor-roles one (D15, AC15, Frontend changes) | `SectionKey` is **twelve** (`App.tsx:20-33`), `NAV` is **twelve** rows, and `Nav.test.tsx` asserts **owner eleven** (`:103`), **shift manager nine** (`:110`, `:114`, `:204`), `NAV_LABELS` **11** (`:156`) | **C2** |
| `vite.config.ts`'s comment says «eleven» while the alternation lists twelve; the one-word fix is a free drive-by (Conflict 7) | **Already fixed by F53.** The comment says **«The thirteen names»** and **«a fourteenth segment»**, and the alternation lists **thirteen** (`customers` added). **F36 touches that file not at all** | **C3** |
| `DomainValidationError`'s handler is `main.py:790-794`; `DomainNotFoundError`'s is `:796-798` (D14, "What already exists") | `:795-799` and `:801-804`. `NOT_FOUND_BODY` is `:157` | **C4** |
| Every shipped customer read filters `deleted_at` at `db/repositories/customers.py:20,30,45,68` (D11) | F53 rewrote that file. The filters are at **`:35, :58, :68, :83, :106, :175`**. D11's join argument is unaffected | **C5** |
| `auth/staff.py:57-61` namespaces its advisory-lock key (D3) | `_STAFF_LOCK = text("SELECT pg_advisory_xact_lock(hashtext('staff:' || :tenant_id))")` is **`:64`**. The docstring D3 quotes (*"No unique index can express it…"*) is **`:9-14`** and is intact | **C6** |
| `he.ts:553-565` is F34's `board.*` block (D17) | F53 inserted `customers.*`. The `board.*` block opens at **`:507`**. The `floor.*` block still opens at **`:608`** and `floor.statusAvailable` / `floor.statusBreak` are still **`:636-637`** — both spec citations survive | **C7** |
| `db`-marked tests are the standard F34 and F57 set (Testing) — with no statement about the harness | The harness is **committed**: `conftest.py:88` / `:100` / `:109`, `TEST_POSTGRES_SUPERUSER_URL`. No patch, no revert | **C8** |
| — *(the spec does not mention it)* | F19 shipped a **fast, no-DB single-head guard** at `test_migrations.py:44-52`: `len(ScriptDirectory…get_heads()) == 1`, failing in `make test` rather than as a CI mystery. **This is the guard that catches a bad renumber before the PR opens** | **C9** |
| `start_break`'s docstring (*"`staff` is the ACTING identity…"*) is `floor/router.py:92-94` (D6) | **`:94-96`** | **C10** |
| `FloorService._authorize` is `floor/service.py:137-151`; `floor()`'s docstring is `:69-75` (D6, D9) | `_authorize` is **`:138-151`** (`@staticmethod` at 138); `floor()`'s docstring is **`:68-75`** | **C11** |
| *(implicit)* `qa-greps.sh` is a storefront concern | Its ten `check` calls read `apps/storefront/src` only (`:17`), but the **date-reads review block** (`:62-67`) reads `apps/manage/src` too. **F36 can move that output and only that** | **C12** |
| D5's ORM-model paragraph: *"no model↔migration parity test exists anywhere in `backend/tests/`"* | Still true, and now **doubly** load-bearing: C9's single-head guard proves the *chain* is coherent and proves nothing about the *mapping*. Migration + models stay one atomic commit | **C13** |

### Citations re-captured — ✅ verified on this tree, do not re-check

- ✅ `backend/app/floor/router.py` — module docstring's *"ZERO customer data"* claim `:11-17` (the sentence itself `:12-14`), *"SEVENTH router"* `:3`, `test_dashboard_api.py:49-51` note `:8-9`, real-verbs paragraph `:44-46`, no-rate-limiter paragraph `:39-42`, `router = APIRouter(prefix="/manage", dependencies=[…require_role(*StaffRole)])` **`:73-79`**, `start_break`'s two-identities docstring **`:94-96`** (C10), the three shipped routes `:85`, `:90`, `:102`.
- ✅ `backend/app/floor/service.py` — `card_status(row)` **`:44-52`** with its *"'occupied' is coming"* docstring; `FloorService.__init__`'s injectable clock **`:56-65`**; `floor()`'s *"no customer data, so no gate has to be widened over one"* docstring **`:68-75`** (C11); `end_break`'s ⚠ capture-before-write comment **`:108-116`** (`before` at `:115`, `previous` at `:116`); `_authorize` **`:138-151`** (C11) with its *"A body-supplied `staff_user_id` doubling as the caller's identity"* hazard at `:143-145`; `ELEVATED_ROLES` `:41`.
- ✅ `backend/app/floor/schemas.py` — *"A card is a name, a role and a status, and deliberately nothing else"* **`:13-16`**; `StaffCard` `:29-38`; `from_row` **`:40-48`** with `card_status(row)` at **`:46`**; `FloorResponse.from_rows` **`:54-56`**.
- ✅ `backend/app/models/constants.py:26-38` — `class StaffCardStatus(StrEnum)` at `:26`, the *"'occupied' is coming and is deliberately NOT here… widens this in the SAME PR"* comment `:27-36`, `AVAILABLE` `:37`, `BREAK` `:38`.
- ✅ `backend/app/models/base.py` — `StandardColumns` `:13`, `id` server_default `uuid_generate_v4()` `:17-19`, **`created_at` `server_default=text("now()")` `:20-22`** (D2's not-freezable argument), `updated_at` `:23`, `deleted_at` `:24`.
- ✅ `backend/app/models/booking.py:45` — `checked_in_at: Mapped[datetime | None]`. Exactly as the spec cites.
- ✅ `backend/app/booking/service.py` — `pg_advisory_xact_lock(hashtext(:tenant_id))` **`:387`**, the *"a failed flush aborts…"* comment **`:404`**, `active_seats_at` **`:451`**, the `except IntegrityError` **`:491`**. The spec's ⚠ that these moved ~130 lines on F19's merge is **correct and already applied**; a reviewer finding a fourth set should re-grep.
- ✅ `backend/app/auth/staff.py` — the at-least-one docstring **`:9-14`**, `_STAFF_LOCK` **`:64`** (C6).
- ✅ `backend/app/db/repositories/staff_users.py` — `_refreshed` **`:195-223`** (`populate_existing=True` at **`:221`**), `soft_delete` **`:225`**.
- ✅ `backend/migrations/versions/0008_bookings.py` — the snapshot-columns comment **`:52-57`**, `idx_bookings_slot_seat_unique` **`:88-92`** (**one** unique index; `idx_bookings_tenant_starts` at `:95-98` is non-unique), the trailing `GRANT` + `enable_tenant_rls` loop **`:107-110`**, `downgrade` **`:113-115`**.
- ✅ `backend/app/db/rls.py:4` `def enable_tenant_rls(table_name) -> list[str]`; `backend/tests/test_tenant_isolation.py:203` `test_every_tenant_id_table_has_forced_rls`.
- ✅ `backend/app/main.py` — `NOT_FOUND_BODY` **`:157`**, `DomainValidationError` handler **`:795-799`**, `DomainNotFoundError` handler **`:801-804`** (C4).
- ✅ `backend/app/catalog/validation.py:48` `MAX_SORT_ORDER = 1_000_000`; the house symmetric `Field(default=0, ge=-MAX_SORT_ORDER, le=MAX_SORT_ORDER)` at `catalog/schemas.py:46`, `:63`, `:72` and `boutique/schemas.py:73`, `:85`.
- ✅ Gate citations: `catalog/router.py:61`, `boutique/router.py:33`, `booking/owner_router.py:83` — all `require_role(StaffRole.OWNER, StaffRole.SHIFT_MANAGER)`.
- ✅ `backend/app/storefront/service.py` — `StorefrontDressListView` `:78`, `StorefrontSizeView` `:86` with `size_label` `:90`, answered anonymously at `:166`/`:182`. D16's disclosure argument holds.
- ✅ `backend/tests/test_floor_api.py` — `FLOOR_ROUTES` **`:51-55`** (three rows) with its *"SEVEN routers now mount prefix=/manage"* comment `:48-50`, `SPEC_ERROR_CODES` **`:63-68`** (four codes) with its ⚠ NO NEW MEMBER comment `:60-62`, the `FLOOR_ROUTES` walks `:207`/`:218`/`:235`/`:245`/`:256`, `test_a_toggle_answers_one_card_and_not_the_whole_floor` `:342` with **`assert set(body) == {...}` at `:346`** *(the spec says `:344`; it is `:346` — the file gained two lines)*, `test_no_card_carries_an_email_or_any_credential` **`:349-358`**, `test_the_card_status_wire_literals_are_exactly_available_and_break` **`:360`**, `assert observed == SPEC_ERROR_CODES` `:418`.
- ✅ `backend/tests/test_floor_service.py:370` — the twin wire-literal set equality.
- ✅ `backend/tests/test_staff_role_gating.py` — `OWNER_ONLY` `:70`, the *"FLOOR_OPEN below is the exhaustive list of what they may reach"* comment **`:84`**, `FLOOR_ROLES` `:85-91`, the **route-template** comment `:93-96`, `FLOOR_READ`/`FLOOR_BREAK_START`/`FLOOR_BREAK_END` `:97-99`, `FLOOR_OPEN` **`:102`**, `test_the_floor_roles_reach_exactly_the_floor_routes` **`:240`** with its *"IT MUST NEVER BE RELAXED TO A SUBSET CHECK"* at `:248`, the intersection classifier `:282-284`, the equality `:292`, the `missing` guard `:301-302`.
- ✅ `backend/tests/test_migrations.py` — **the single-head guard `:44-52`** (C9), the captured-definition idiom and its *"pg_get_constraintdef normalises `IN (...)` into `= ANY (ARRAY[...])`"* comments, and the two most recent round-trip tests both **last in the file** in `try/finally: command.upgrade(cfg, "head")` with *"the revision … is resolved from `alembic heads` at build time, so a literal here would rot"* at `:641` and `:740`.
- ✅ `backend/tests/test_floor_db.py` — the ⚠ **seed-role rule** `:12-32`, and the forced-interleave shape **`:296-325`**: the loser opens its session and **reads** (a plain SELECT, no row locks) → the winner's inner `async with` opens, writes and **exits, which is the commit** → only then does the loser write. Exactly what the spec's Rejected-findings section defends.
- ✅ `backend/tests/test_spa_serving.py:372-401` — `test_the_manage_dev_proxy_names_every_manage_api_segment`, deriving `expected` from the live route table (`:392-396`) and asserting **`set(match.group(1).split("|")) == expected`** at **`:401`**. The scrape regex is `r'"\^/manage/\(([a-z|-]+)\)"'` at `:399`.
- ✅ `backend/tests/test_frontend_constant_parity.py` — `MIRRORS` `:54`, existing ids `"manage"` `:71`, `"manage-staff"` `:81`, `"manage-customers"` `:99`; parametrized at `:129` and `:138`. **`id="manage-floor"` is free.**
- ✅ `frontend/apps/manage/src/lib/usePoll.ts` — `POLL_INTERVAL_MS` `:15`, `MAX_BACKOFF_MS` `:19`, `IDLE_STOP_MS` `:23`, `IDLE_STOP_MINUTES` `:24`, `terminalOf` **`:100-108`** returning `"access"` for any 403 (`:107`).
- ✅ `frontend/apps/manage/src/components/FloorPanel.tsx` (617 lines) — `focusHeadingRef` declared `:74`, **set inside `load` at `:107`, one line before `setCards` at `:109`** (*"the only moment both lists exist"*); `reclaimFocusRef` `:78` and its ⚠ *"the alert we are about to remove may be HOLDING FOCUS"* block **`:114-127`**; `cardErrorRef` `:81`; `mutationsRef` `:82`; `holdRef` **`:83-88`**; `tick()` **`:155-164`** (`"suppressed"` / `"held"`); the ⚠ cue-only-when-changed comment **`:194-201`**; the `[cardError]` focus effect ending `:255`; the departing-tile effect **`:257-268`** (`document.activeElement === document.body` guard at `:265`); `pause`/`resume` `:270-278`; `toggle` **`:280-341`** — `mutationsRef += 1` `:285`, `clearTick`+`bump` `:289-290`, *"NOT optimistic"* `:296-299`, the F-ok/F-noop comment `:305-307`, `poll.fail(error)` `:319`, the 404 branch `:325-330`, **THE RE-ARM** `:334-340`; `heading` (`h2`, `tabIndex={-1}`) **`:343-347`**; the terminal branch **`:349-367`**; the pause control's *"FIRST STOP INSIDE THE PANEL"* comment **`:434-440`**; the outage `role="alert"` with `staff.loadFailed` **`:488-491`**; per-card `onBreak` **`:523`**; *"Which control EXISTS is the rendered form of D6's two axes"* **`:525-529`**; `mayToggle` **`:530`**; `min-w-0 grow` `:539`; the room-label-shaped `break-words` `:546`; *"The WORD carries the state; the colour never does"* **`:554`**; the `Badge` **`:556-557`**; the role line `:560-562`; the since-line **`:563-575`** with `onBreak && card.break_started_at !== null` at **`:566`**; the per-card `role="alert"` + `tabIndex={-1}` + `cardAlertRef` **`:576-584`**; `controlRefs` **`:589-591`**; `variant={onBreak ? "ghost" : "secondary"}` **`:592`**.
- ✅ `frontend/apps/manage/src/api.ts` — `ApiError` **`:9-19`** (`status` `:10`, `code` `:11`, **no `details`**), `extractError` **`:26-37`**, `apiFetch` `:39`, the floor wire-types banner `:385`, the `StaffCardStatus` comment **`:387-389`** and the union **`:390`**, `StaffCard` `:392-398`.
- ✅ `frontend/apps/manage/src/lib/roles.ts` — `ROLE_LABEL_KEY` `:21-27`, **`roleLabelKey(role: string): string | null` `:36-37`** (DC-12), `ROLE_OPTIONS` `:46`.
- ✅ `frontend/apps/manage/src/components/StaffSection.tsx:80-92` — the `deactivateTrigger` / `isConnected` / heading-fallback focus effect. D18's move-3 precedent.
- ✅ `frontend/apps/manage/src/lib/booking.tsx:75` `export function isolateLtr(text, value)`; `lib/jerusalem.ts:35` `export function jerusalemTime(instant)`, every formatter zoned at `:10`/`:16`.
- ✅ `frontend/packages/ui/src/components/` — `Button.tsx:36` `sm: "min-h-9 …"`, **`:37` `md: "min-h-11 …"`**, `focusRing` applied **`:63`**; `Select.tsx:6` **`label: string`**, `:13` signature, `:19-21` the `<label htmlFor>`, `:31` `focusRing`; `Input.tsx:14` **`label: ReactNode`** with the F17 widening comment `:6-13`, `:45` `focusRing`; `Modal.tsx:10` **`title: string`**, `:23` `useId`, `:44` `aria-labelledby`, **`:50-52`** the `<h2>`.
- ✅ `frontend/apps/manage/src/__tests__/i18n.test.ts` — `entries()` `:18`, the per-feature constants **`:24-47`**, the fold comment **`:33-37`**, the *"the namespace names the payload, not the feature"* rule **`:40-42`**, **`const HE = [...]` `:48`**, `HE_F57.length > 28` **`:317`** and its now-stale *"29 `floor.*` keys plus `nav.floor`"* comment **`:315-316`**, the F57-scoped digit guard **`:377-380`**, the `"!"` filter **`:396-398`**, the `/נשלח|תישלח|בדרך/` filter **`:400-402`**, the `ar`-empty scan **`:411-415`**, the `ar`-**presence** scan **`:417-420`**, and the two blocks both named *"resolves the eleventh nav item"* at **`:257`** and **`:320`**.
- ✅ `frontend/apps/manage/src/App.tsx:20-33` — `SectionKey`, **twelve members**, `floor` labelled *"the ELEVENTH member"* (F57's comment, stale since F53 inserted `customers` at `:23`); `NAV` rows at `:68-74`, `:89`, `:97`, `:103`, `:104`, `:108`.
- ✅ `frontend/apps/manage/src/__tests__/Nav.test.tsx` — `NAV_LABELS` `:66`, the `.slice(0, 9)` comment `:85`, **owner eleven `:103`**, **shift manager nine `:110`/`:114`**, the coupled-edits comment `:148-154`, `toHaveLength(11)` **`:156`**, the second `.slice(0, 9)` **`:204`**.
- ✅ `frontend/apps/manage/vite.config.ts:13-19` — *"The thirteen names"*, *"a fourteenth segment"*, and the thirteen-name alternation including `customers` and `floor` (C3).
- ✅ `Makefile` — `test` `:18`, `test-db` `:21`, `test-all` `:24`, `lint` `:27`, `qa-greps` `:33`, `fe-build` `:44`, `fe-test` `:47`, `e2e` `:51`.

---

## The design critic's fourteen required changes — DC-1 … DC-14

**The verdict is REVISE, not REJECT**, and the reasons matter: token compliance is clean, every contrast figure matches `tokens.md:25-34`, there are no AI-generic patterns, and **F-2 and F-3 are verified-real findings that justify the deck on their own**. What follows is the remediation list, severity descending, each with an owning task. **DC-2, DC-5, DC-6, DC-13 and DC-14 are document-only and land in Task 0. The other nine are build work.**

| # | What | Owner task |
|---|---|---|
| **DC-1** | **§10.1 is missing a sixth focus move: a poll tick unmounting the FOCUSED tile alert.** §3.3's diagram promises it; none of the five numbered moves owns it. Move 1 is keyed on `[tileError]` and does nothing when it goes null; move 2 fires on a mutation settling, not a tick; move 3 is about a tile leaving. **Without a sixth move the panel drops focus to `<body>` ~5 s after every refused claim, with no user action — F57's shipped MAJOR verbatim.** Mirror the shipped mechanism: `FloorPanel.tsx:107` sets its flag inside `load` **before** the new cards are applied (*"the only moment both lists exist"*, `:257-262`), and `:265` guards on `document.activeElement === document.body`. The shipped analogue for the alert specifically is `:114-127` → `reclaimFocusRef`. | **0** (deck) + **10** (build + named test + mutation) |
| **DC-2** | **`copy.md` cites the wrong lines for all four mechanical guards, and each is the evidence for a «0» in §11.** `:328-330` → **`:396-398`**; `:332-334` → **`:400-402`**; `:305-311` → **`:374-381`**; `:337-346` → **`:411-415`**. Re-verified by me on this tree. (`:24-48`, `:33-34`, `:40-42`, `:257`, `:320` are correct.) | **0** |
| **DC-3** | **There is no digit guard over `rooms.*`, and §0 rule 4 / §11 imply there is.** The shipped assertion at `:379-380` is `HE_F57.filter(…)` — F57-scoped. And the shipped `ar` guard at `:417-420` checks **presence** only (`!(key in ar.translation)`), never equality. So §11's «0» rows for rules 4 and 10 are hand-counts wearing citations. **Fix in the test, not the prose**: add an `HE_F36`-scoped digit mirror and the `ar[key] === he[key]` assertion spec D17/AC13 already require. | **0** (deck) + **8** (`i18n.test.ts`) |
| **DC-4** | **§5.1 contracts the registry dialog's state under the tick and leaves the inline client `Select` — up to five, live on the panel, no dialog holding anything — with no equivalent contract.** State that each free tile's selected `client_id` is local state **keyed by room id**, that it survives every repaint (tiles are keyed by `room.id`, so React preserves the subtree), and that a tick may not reset it. Same defect class as §5.1's, and *more* likely here. | **0** (deck) + **10** (named test, AC25's twin) |
| **DC-5** | **§10.2's «`role="alert"` appears exactly twice» is a miscount, and the count is the argument.** `FloorPanel` already ships three: `:357` (terminal 401/403), `:490` (`staff.loadFailed`, outage register), `:576-584` (the per-card alert). F36's tile alert is the **fourth**, and §3.2's unmapped-outage fallback renders `staff.loadFailed` inside a tile as a **fifth** site. Recount and re-argue the bound. | **0** |
| **DC-6** | **§10.1 move 3's premise «the only way a tile leaves is a registry delete» is wrong, and the wrong reading puts the fix in the wrong file.** A tile also leaves via a **tick** — another elevated user deleting a room from her own device — which arrives through the rooms `load`, not through this user's delete handler. Point at `FloorPanel.tsx:257-262`, which exists for precisely that distinction. | **0** (deck) + **10** (the move covers both origins) |
| **DC-7** | **Two 295px layout gaps in §9's element table.** The room label and holder name get `break-words`; the **client row**, the `rooms.holderGone` sentence and the **dress row** do not. The dress row is the worse one: `flex items-center justify-between gap-3` with a `<span>` carrying no `min-w-0`, so a long dress name cannot shrink and pushes «הסרה» out of a 295px tile. Add `break-words` to the client row, the holder-gone sentence and the dress name; add `min-w-0` to the dress row's span — the tile's own text block already gets `min-w-0 grow` for exactly this reason (`FloorPanel.tsx:539`). | **0** (deck) + **10** |
| **DC-8** | **`rooms.error.notFound` and `rooms.error.assignmentGone` promise «הרשימה תתוקן בעדכון הבא», and while the panel is PAUSED there is no next update.** Verified: `FloorPanel.tsx:270-273`'s `pause()` stops only the loop; `mode` is read only for the freshness stamp; the card control carries no `disabled` on paused. So a claim is fully available while paused and a 404 then renders a sentence the screen will not keep. §0 rule 4 was written against *durations*; this is the same failure in the **event** form. **Resolution: condition the «בעדכון הבא» clause on `mode === "running"`** and ship a paused variant pointing at «חידוש». | **0** (deck + copy) + **10** |
| **DC-9** | **No state anywhere for a dense registry.** Nothing in §7 or §8 covers fifteen or twenty rooms. `Modal.tsx:46` declares `w-[min(28rem,…)]` with **no `max-h` and no `overflow-y` of its own** — it relies entirely on the UA's `dialog:modal { max-height; overflow: auto }`, worth stating rather than assuming. And §5.4 puts the `role="status"` cue at the **top** of that scrolled list, so saving row 18 confirms off-screen. Add the state; move the cue to sit with the save it confirms, or record why the top is right. | **0** (deck) + **11** |
| **DC-10** | **The one-room boutique's reverse path is asserted but not designed.** §7 lists *"closed with its trigger gone (§1.2)"*, but §1.2's ⚠ describes only empty→populated. Delete your only room → the panel returns to `EmptyState` and the heading-row trigger is replaced by the CTA. §1.2's fallback target is the rooms `h3` — **and nothing in either deck says the `h3` renders in R-empty.** State that the `h3` renders in **every** state including R-empty, because it is the focus-rescue target. | **0** (deck) + **10**, **11** |
| **DC-11** | **The staff card's occupancy line drops `rooms.clientLabel` and the deck does not say why.** The tile renders «לקוחה  מיכל»; the card renders `<bdi>{room}</bdi> · <bdi>{client}</bdi> · …` — a bare name one line under another bare name, separated by a character most screen readers do not voice. `floor.pausedAt` is a weaker precedent than claimed (one string, one separator, not three unlabelled values). **Reuse `rooms.clientLabel` in the middle fragment**, or record the divergence with its reason the way every other divergence here is recorded. | **0** (deck §6.2 + copy §10) + **9** |
| **DC-12** | **`roleLabelKey` returns `string \| null` (`lib/roles.ts:36-37`), so §9's `<bdi>{t(roleLabelKey(role))}</bdi>` neither type-checks nor has a null branch.** Say what the tile renders for an unrecognised role string. **Resolution: no role line at all**, the same as the holder-gone case — and it matches `FloorPanel.tsx:561`'s shipped shape (`labelKey === null ? card.role : t(labelKey)`) closely enough to be defensible either way; **the tile takes the omit branch because a raw slug under a Hebrew name on a tile is noise, where on a staff card it is the only thing distinguishing two cards.** | **0** (deck) + **10** |
| **DC-13** | **Record the `Select.label: string` constraint as a finding with an owner and a trigger, the way F-4 records the min-height one.** `copy.md` §8 says isolation there is *"IMPOSSIBLE, not merely omitted"* — true today, and one line from possible: `Input.label` is typed **`ReactNode`** (`Input.tsx:14`) and its comment (`:6-13`) says F17 widened it for exactly this. F36 is right to decline the shared-code edit; without the finding the next feature re-argues it from zero. **New finding F-11.** | **0** |
| **DC-14** | **Line-number defects.** `design.md` §0: `Button.tsx:36` is `sm: min-h-9`, not `md`'s `min-h-11` — that is **`:37`**; `focusRing` is applied at **`:63`**, not `:62`; `isolateLtr` is `booking.tsx:75`, not `:74`. `copy.md` §5.1: `Modal`'s `<h2>` is **`:50-52`**, not `:51-53`. Separately: after `floor.statusOccupied` lands, `i18n.test.ts:315-316`'s comment («29 `floor.*` keys plus `nav.floor`») goes stale while `:317`'s `> 28` floor stays green. **F36 owns that one comment and updates it to 30, and nothing else in that file** — §0.1's *"do not helpfully renumber anything in that file"* covers the two stale *"eleventh nav item"* names at `:257`/`:320`, which are F53's and stay. | **0** |

---

## Scope fence — read this before every task

**F36 ships the room, the claim, the release, the handover, the dress bindings and the panel that renders them.** It ships no queue verb and no alert of any kind.

| Not in F36 | Whose |
|---|---|
| SOS, the targeted page, the full-screen overlay, the 30-second escalation, `sos_alerts`, `sos_alert_targets` | **F37** |
| `queue_ticket_id` on `fitting_room_assignments`, take-next, push-assign, finish, skip, call, the waitlist panel, the `/manage/**` Playwright interception harness | **F58** |
| `queue_tickets` and the walk-in ticket itself | **F33** (in flight) |
| The public wall board at `/queue` | **F59** |
| Booking a room in advance; a `capacity` column; auto-assignment or "next free room" | **out, D3 / Out of scope — a `capacity` column turns the index into a count, which is F13's lock, which is what the ruling forbids** |
| Occupancy timers, SLA alerts, anything firing on elapsed time; wait-time or utilisation analytics | **out — pre-decided #28, spec Out of scope** |
| Per-dress verdicts, ratings, photos, fitting notes | **E9 / F41** |
| A history read of past assignments | **out — the index ships, no reader does** |
| A unique index on `fitting_rooms.label`; a room `notes` field; per-room permissions | **out, D1** |
| Retention of assignment rows; the processing-activities entry | **F20** (spec Risk 5 hands it over) |
| Any change to `lib/usePoll.ts`, `App.tsx`, `vite.config.ts`, `qa-greps.sh`, `packages/ui/**` | **out — D15, C3, DC-13** |
| Widening `catalog/router.py` or `booking/owner_router.py` to admit a floor role | **out — F57's Risk 1 exists to prevent it; D16 answers both lists on the floor router instead** |
| A second poll loop, a second pause control, a second `usePoll` instance, a `version` field | **out — LOOP-STATE's F36 note, D11, D15. F32 is subsumed and must never be built** |

If a task's diff grows a second `usePoll(...)`, a nav row, a `packages/ui` edit or a `queue_` identifier, it has left F36.

---

# Part 0 — the plan

## Task 0 — This plan, thirteen spec amendments, and the design critic's fourteen
`.planning/plans/fitting-rooms.md` (this file), `.planning/specs/fitting-rooms.md`, `.planning/design/screens/fitting-rooms/design.md`, `.planning/design/screens/fitting-rooms/copy.md`

No test, no code. Amend the three documents so each is the binding statement of every resolution above.

**Spec (`fitting-rooms.md`) — C1–C13:**
- **Header + D5 + D5's log entry** — replace the dated head observation with **`0017`**, note it moved a **third** time, and keep the rule verbatim (C1). Add C9's single-head guard as the mechanical backstop: `test_migrations.py:44-52`, fast and no-DB.
- **D15, AC15, Frontend changes** — «eleven / owner ten / shift-manager eight» → **twelve / owner eleven / shift-manager nine**, citing `App.tsx:20-33`, `Nav.test.tsx:103`, `:110`, `:114`, `:156`, `:204`. **The rule is unchanged and is the point**: `App.tsx` and `Nav.test.tsx` are untouched, and the assertion is a `git diff` that is empty (C2).
- **Conflict 7 + D10 + AC16** — the `vite.config.ts` drive-by is **already done by F53**; the comment says thirteen and lists thirteen. F36 edits that file not at all and `test_spa_serving.py` stays green with no change (C3).
- **D14 + "What already exists"** — `main.py:790-794` → **`:795-799`**, `:796-798` → **`:801-804`**, plus `NOT_FOUND_BODY` `:157` (C4).
- **D11's join table** — `customers.py:20,30,45,68` → **`:35,58,68,83,106,175`** (C5).
- **D3** — `auth/staff.py:57-61` → **`:64`**; the quoted docstring is `:9-14` (C6).
- **D17** — `he.ts:553-565` → the `board.*` block opens at **`:507`**; `floor.*` at `:608` and `:636-637` are correct (C7).
- **Testing** — the `db` section gains C8: the harness is **committed** (`conftest.py:88`/`:100`/`:109`), there is no patch and no revert, and the runner recreates a throwaway `f36_test` database on the local 16.14 cluster. Delete any implication that `db` tests debut on CI.
- **D6, D9** — `_authorize` `:137-151` → **`:138-151`**; `floor()`'s docstring `:69-75` → **`:68-75`**; `start_break`'s docstring `router.py:92-94` → **`:94-96`** (C10, C11).
- **Testing → `test_floor_api.py`** — `test_a_toggle_answers_one_card…`'s key-set assertion is at **`:346`**, not `:344` (the test function is `:342`).
- **D17 + Risk 12** — the key count is **~68**, not "~40" (deck F-6), and D17's table is **not** canonical; `copy.md` is.

**Design deck (`design.md`) — DC-1, DC-4, DC-5, DC-6, DC-7, DC-8, DC-9, DC-10, DC-11, DC-12, DC-13, DC-14:**
- **§10.1** — a **sixth** focus move (DC-1), with destination and mutation; move 3's premise widened to name both origins and pointed at `FloorPanel.tsx:257-262` (DC-6); move 2's `roleLabelKey` null branch resolved (DC-12 belongs in §9, but the tile's render rule is stated once).
- **§10.2** — recount `role="alert"`: **four sites, five with §3.2's outage fallback**, and re-argue the bound (DC-5).
- **§5.1** — the inline client `Select`'s state contract (DC-4).
- **§9** — `break-words` on the client row, the holder-gone sentence and the dress name; `min-w-0` on the dress row's span (DC-7). The `roleLabelKey` null branch: **no role line** (DC-12).
- **§7 + §5.4** — the dense-registry state; `Modal.tsx:46` has no `max-h` of its own and relies on the UA's `dialog:modal` rule; the cue moves to sit with the save (DC-9). The one-room reverse path, and **the rooms `h3` renders in every state including R-empty** (DC-10).
- **§6.2** — the occupancy line reuses `rooms.clientLabel` (DC-11).
- **§0** — `Button.tsx:37` (`md`), `focusRing` `:63`, `isolateLtr` `booking.tsx:75` (DC-14).
- **§12** — a new finding **F-11**: `Select.label: string` versus `Input.label: ReactNode`; owner team; trigger the next feature that needs a bidi-isolated `Select` label (DC-13).

**Copy deck (`copy.md`) — DC-2, DC-3, DC-8, DC-11, DC-14:**
- **§0 rules 1, 2, 4 and §11** — the four guard citations corrected to `:396-398`, `:400-402`, `:374-381`, `:411-415` (DC-2).
- **§0.1 + §11** — add the two test edits the deck's own «0» rows depend on: an `HE_F36`-scoped digit mirror of `:379-380`, and `ar[key] === he[key]`. State plainly that the shipped `ar` guard is a **presence** check and cannot see a wrong value (DC-3).
- **§0.1** — F36 owns exactly one comment renumber in that file: `:315-316`'s floor-key count, **29 → 30**, because `floor.statusOccupied` lands in `HE_F57` by prefix. The two *"eleventh nav item"* names at `:257`/`:320` are F53's and stay (DC-14).
- **§6** — `rooms.error.notFound` / `rooms.error.assignmentGone` gain a paused variant; the «בעדכון הבא» clause is conditioned on `mode === "running"` (DC-8).
- **§10** — the staff card's occupancy line carries `rooms.clientLabel` (DC-11).
- **§5.1** — `Modal`'s `<h2>` is `:50-52` (DC-14).

- **Done when**: `grep -n "SectionKey stays eleven\|owner ten / shift-manager eight\|head is .0016\|790-794\|796-798" .planning/specs/fitting-rooms.md` returns nothing; `grep -n ":328-330\|:332-334\|:305-311\|:337-346\|Button.tsx:36\|booking.tsx:74\|:51-53" .planning/design/screens/fitting-rooms/*.md` returns nothing; `design.md` §10.1 has **six** rows; `copy.md` §0.1 names **three** test edits.
- **Commit**: `docs(planning): F36 implementation plan, thirteen spec amendments and the design critic's fourteen`

---

# Part I — the backend

## Task 1 — The migration **and** the three ORM models, as one atomic change (D1, D2, D3, D4, D5 / C1, C9, C13)
`backend/migrations/versions/00NN_fitting_rooms.py` (**✚**), `backend/app/models/fitting_room.py` (**✚**), `backend/app/models/fitting_room_assignment.py` (**✚**), `backend/app/models/fitting_assignment_dress.py` (**✚**), `backend/tests/test_migrations.py`

**Migration + models ship in one commit and this is not a preference.** No model↔migration parity test exists anywhere in `backend/tests/` (C13), and C9's new single-head guard proves the *chain* and not the *mapping*. Without the three model modules, every backend line Tasks 2–6 specify is an `AttributeError` at import.

### The revision number is a RULE, not a number

```
cd "/Users/mrwen/Documents/Github/Ryan + rawad + mrwen/.worktrees/fitting-rooms/Backend" \
  && uv run python -m alembic heads
```

As of 2026-08-03 it prints **`0017 (head)`**, so the file is `0018_fitting_rooms.py`, `revision = "0018"`, `down_revision = "0017"`. **Do not read that number off this document.** Two features are still in flight (F33 in `.worktrees/qr-walkin-queue`, F53 merged but the ordering rule is general) and the head moved three times in two days.

1. **BUILD at `alembic heads` + 1**, `down_revision` = whatever head is then — so the branch is self-coherent and its `db`-marked tests actually run. F33's D15 records that this was *tested, not theorised*: a `down_revision` naming a revision that lives only on another branch makes alembic unable to build the revision map at all, so `alembic upgrade head` fails and **every** `db` test fails with it, for the branch's whole life. A wrong number therefore fails **loudly** rather than drifting.
2. **Make the migration the LAST commit on the branch.** Task 1 is early, so the commit is *reordered onto the tip* at rebase — or amended in place, since nothing else in the tree references the revision literal.
3. **RE-RESOLVE from `alembic heads` on `origin/main` immediately before the rebase that precedes the push.** Three edits: the filename, the `revision` literal, the `down_revision` literal.
4. **Do not OPEN the PR while a lower-numbered migration is still unmerged.** CI tests the merge result, and two files claiming one revision id is an alembic multiple-heads error that git cannot see because the filenames differ.
5. **Confirm `alembic heads` prints exactly ONE head on the rebased branch**, and confirm `make test` is green — C9's `test_migrations.py:44-52` is the fast, no-DB guard that catches a bad renumber before CI does.

### The failing tests first (`db`-marked, appended to `test_migrations.py`, **run locally**)

Follow the file's own convention: **the round-trip test goes last in the file**, owns no fixtures, and wraps the downgrade in `try/finally: command.upgrade(cfg, "head")` — these tests mutate the session-scoped schema and leaving it down fails unrelated modules with `UndefinedTable`. Every assertion is keyed to **"after this feature's migration"** (i.e. at `head`), never to a number (`:641`, `:740` say so).

1. `test_the_fitting_rooms_migration_creates_the_three_tables` — all three exist; `fitting_rooms.label` is `text` NOT NULL, `sort_order` `integer` NOT NULL default 0, `is_active` `boolean` NOT NULL default true; `fitting_room_assignments.released_at` is a **nullable** `timestamp with time zone`; `fitting_assignment_dresses.dress_size` and `removed_by` are nullable. Read from `information_schema.columns`.
2. **`test_the_three_partial_unique_index_definitions_are_pinned`** — the highest-value test in the feature, because what it guards is a **future** edit. Pin `idx_fitting_room_assignments_room_active`, `idx_fitting_room_assignments_staff_active` and `idx_fitting_assignment_dresses_unique` **byte-identical from `pg_indexes.indexdef`**. The three non-unique indexes are performance and are **not** pinned.
   ⚠ **CAPTURE the literals by running them on the live 16.14 server. DO NOT TRANSCRIBE THEM FROM THE SPEC.** Postgres deparses, re-parenthesises, schema-qualifies and re-orders predicates: `WHERE released_at IS NULL AND deleted_at IS NULL` comes back as `WHERE ((released_at IS NULL) AND (deleted_at IS NULL))`, the table is `public.fitting_room_assignments`, and `USING btree` is inserted. F34's shipped note and F33's D2 both record that a literal which merely *looks* right pins nothing and reddens CI.
3. **`test_fitting_room_assignments_carries_exactly_two_non_primary_unique_indexes`** — `SELECT count(*) FROM pg_index WHERE indrelid = 'fitting_room_assignments'::regclass AND indisunique AND NOT indisprimary` is **2**. This is the half that catches an **addition** rather than an edit: a well-meaning `(tenant_id, booking_id)` added later would make a bride's second fitting of the day impossible, with no other test failing anywhere (spec Risk 7).
4. **`test_fitting_assignment_dresses_carries_exactly_one`** — same query, **1**. And `fitting_rooms` carries **0**, which is D1's no-unique-label decision asserted rather than assumed.
5. **`test_every_tenant_id_table_has_forced_rls` stays green with NO EDIT** — three new `tenant_id` tables. That test lives in `tests/test_tenant_isolation.py:203` and scans `pg_class` for `relforcerowsecurity`; forgetting one `enable_tenant_rls` call fails **a different file** a long way from here.
6. **A CHECK-free table is a decision, so assert it**: `fitting_rooms` and `fitting_room_assignments` carry **no** CHECK constraints. There is no status column anywhere in this feature (D2: *"`released_at IS NULL AND deleted_at IS NULL` is what active means, and it is the whole model"*), and a later reader reaching for one meets an assertion.
7. **`test_migration_00NN_round_trips`** — upgrade applies, assert the end state; `downgrade` one revision, assert the **reverse** (all three tables gone); `upgrade` to head, re-assert. Probing both directions is `0013`'s rule: a silently no-op downgrade stays green while shipping an unrollbackable migration. **Last in the file, in `try/finally`.**

### The code

`00NN_fitting_rooms.py`, the `0008_bookings.py` idiom verbatim: raw `op.execute` DDL, the module-level `_STANDARD` block, a local `_updated_at_trigger` helper, three `CREATE TABLE`s in the order **rooms → assignments → bindings**, the six indexes (three partial unique + `idx_fitting_rooms_tenant_order` + `idx_fitting_room_assignments_tenant_created` + `idx_fitting_assignment_dresses_assignment`), three `_updated_at_trigger(...)` calls, and **one trailing loop** doing the GRANT and the RLS together (`0008:107-110`):

```python
for table in ("fitting_rooms", "fitting_room_assignments", "fitting_assignment_dresses"):
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO app_user")
    for statement in enable_tenant_rls(table):
        op.execute(statement)
```

> Forgetting `enable_tenant_rls` fails **a different file's** test (`test_tenant_isolation.py:203`). Forgetting the GRANT fails **nothing** until the app role touches the table — i.e. in Task 7, as `permission denied`.

**Comments that must be in the DDL, because the reader is a future feature:**
- `idx_fitting_rooms_tenant_order` carries **both** sort keys `(tenant_id, sort_order, created_at)`: `sort_order` defaults to 0 and the registry lets it be omitted, so a boutique that never reorders has **every** room in one equal-`sort_order` group and a two-column index would supply none of the ordering. *A 5-second repaint that re-sorts rows is a repaint a finger cannot travel across.*
- The two assignment unique indexes carry pre-decided #31 and the 2026-07-31 ruling, and the predicate `WHERE released_at IS NULL AND deleted_at IS NULL` carries the sentence that makes a **released** room immediately re-claimable in the same tick.
- `idx_fitting_room_assignments_tenant_created` states its cost and names its readers (F37's "which assignment was this alert raised in", F41's ticket attachment): the two unique indexes are partial on `released_at IS NULL` and are useless over history, and this is the one table in the feature that grows monotonically.
- `fitting_assignment_dresses.removed_by` carries D13's argument in one sentence: the row **is** the audit record, and without an actor it answers *what* and *when* and cannot answer *who*.
- `deleted_at` on `fitting_room_assignments` has **no v1 writer** and is in both index predicates for the same reason it is on every table — say so, so a reviewer looking for the missing route stops looking.

`downgrade()` is `DROP TABLE IF EXISTS` in reverse order and nothing else — no explicit index, trigger or policy drops (`0008:113-115`). **F36 touches no existing table, so it has nothing to un-touch**, and unlike F57's migration its downgrade cannot fail on live data.

The three model modules each declare **every** column explicitly as `mapped_column`, the `models/booking.py` shape, `class X(StandardColumns, Base)`. `created_at` is **not** re-declared — it comes from `StandardColumns` with `server_default=text("now()")` (`base.py:20-22`), which is exactly why D2 says it is **not freezable** and why D7's frozen-clock equality is on `released_at` only.

### Mutation-checks (mandatory — RUN them, do not reason about them)

| Mechanism | Remove it | Expect |
|---|---|---|
| `enable_tenant_rls(...)` for any one of the three | delete that table from the loop | `test_every_tenant_id_table_has_forced_rls` **RED**, naming the table |
| `WHERE released_at IS NULL` on either assignment index | make the predicate `WHERE deleted_at IS NULL` only | test 2 **RED** on a byte-identical comparison — *and this is the pinned mutation the spec names, because `released_at` is the conjunct with a writer* |
| the `(tenant_id, staff_user_id)` index | drop it | test 3 **RED** (count 2 → 1). **It is the only test in Task 1 that fails**, which is exactly Task 6's point |
| `downgrade` | make it `pass` | test 7 **RED** on the reverse assertion |

- **Done when**: `bash "<scratchpad>/run-db-tests.sh"` green (baseline + the new cases); `make lint` clean; `make test` green with the new cases collected-and-deselected **and C9's single-head guard green**. `git show --stat` confirms the lowercase pathspecs landed.
- **Commit**: `feat(floor): the fitting-room registry, the assignment and its dress bindings — migration, models and pinned definitions`

## Task 2 — The three repositories and the payload read (D1, D2, D3, D4, D7, D8, D11)
`backend/app/db/repositories/fitting_rooms.py` (**✚**), `backend/app/db/repositories/fitting_room_assignments.py` (**✚**), `backend/app/db/repositories/fitting_assignment_dresses.py` (**✚**), `backend/tests/test_fitting_rooms_repositories.py` (**✚**)

Every method takes `tenant_id` explicitly and puts it in the `WHERE` beside `deleted_at IS NULL` — the `CustomersRepository` defence-in-depth rule, on top of RLS.

### The failing tests first (`db`-marked, **run locally**)

**`FittingRoomsRepository`** — `insert`; `by_id` (present / absent / soft-deleted / **another tenant's → `None`**); `list_live(tenant_id)` returning **every live room, active and inactive**, ordered `(sort_order, created_at)`; `update(label?, sort_order?, is_active?)`; `soft_delete`; and **`by_id_for_update`** — the per-room `SELECT … FOR UPDATE` D1's cross-row invariant needs. Its docstring states the invariant in writing and names AC17.

**`FittingRoomAssignmentsRepository`** — the four writers, each returning the `(wrote, row)` shape F57's writers already use:
- **`claim(session, tenant_id, room_id, staff_id, booking_id)`** — a **Core `session.execute(insert(...))`**, never `session.add`. ⚠ Both halves are load-bearing: with `session.add` the flush happens in `AsyncSessionTransaction.__aexit__`, so the `IntegrityError` surfaces when the savepoint block **exits** and a `try` placed inside it never catches anything. The repository raises; **the service owns the savepoint** (Task 4).
- **`active_for(tenant_id, room_id, staff_id)`** — the request-keyed idempotence read (D3/D6). **Never keyed on the constraint name.**
- **`occupant_of_room` / `room_of_staff`** — the two occupant reads the 409 `details` come from, each returning `None` when the winner released in the gap.
- **`release(tenant_id, assignment_id, at)`** — the conditional `UPDATE … SET released_at = :at WHERE … AND released_at IS NULL AND deleted_at IS NULL RETURNING id`, then **one `select(...).execution_options(populate_existing=True)` re-read, unconditionally**. `StaffUsersRepository._refreshed` (`:195-223`, flag at `:221`) applied to this table, for the reason its docstring gives: *"whether a caller happened to load the row first is exactly the reasoning that has bitten this repo three times."*
- **`handover(tenant_id, assignment_id, new_staff_id)`** — the guarded `UPDATE … SET staff_user_id = :new WHERE … AND released_at IS NULL AND deleted_at IS NULL RETURNING id`. **One statement, which is why the dress bindings survive for free.**
- **`has_active_for_room(tenant_id, room_id)`** — the delete's occupancy guard, issued as a **separate statement after** the `FOR UPDATE` is held, so a new statement snapshot sees the committed claim.

**`FittingAssignmentDressesRepository`** — `add` as

```sql
INSERT … ON CONFLICT (tenant_id, fitting_room_assignment_id, dress_id)
  WHERE deleted_at IS NULL
  DO UPDATE SET updated_at = :at
  RETURNING id, (xmax = 0) AS inserted
```

⚠ **`DO UPDATE`, not `DO NOTHING`, and the difference is a silent lost update.** With `DO NOTHING`: T1 soft-deletes binding B (uncommitted); T2 adds the same dress, conflicts against the still-live B, does nothing, answers 200 «נוספה»; T1 commits — **the dress is out of the room and the staffer who put it in was told it went in**, with no error and no index able to say so. `DO UPDATE` **blocks** on T1's uncommitted delete; when T1 commits, `ON CONFLICT`'s re-check finds the row no longer in the partial index and the add re-inserts cleanly. `(xmax = 0)` gives the `(wrote, row)` shape and `updated_at` is the only column touched on the no-op branch. **No `IntegrityError`, therefore no aborted transaction, therefore no savepoint on this path** — the claim needs one because it must *report* the conflict; this one must not.
Plus `remove(tenant_id, assignment_id, binding_id, actor_id, at)` — a soft delete stamping `deleted_at` **and `removed_by`** — and `by_assignment_ids(tenant_id, ids)`, skipped entirely when nothing is occupied.

**The payload read, and it is TWO statements added to the tick's existing session** — no new `tenant_session`, no new pool checkout, no second `tenants.by_slug`:

1. `fitting_rooms` **LEFT JOIN** active assignments **LEFT JOIN** `staff_users` **LEFT JOIN** `bookings` **LEFT JOIN** `customers`, driving from rooms so an unoccupied room still produces a row. **There are no FK constraints in this schema, so every predicate is written out in the code:**

   | Join | Predicate | Test that fails without it |
   |---|---|---|
   | `fitting_rooms` (driving) | `tenant_id = :t AND deleted_at IS NULL` | inactive rooms **do** ship — the panel greys them |
   | → `fitting_room_assignments` | `tenant_id = :t AND fitting_room_id = rooms.id AND released_at IS NULL AND deleted_at IS NULL` | D3's index predicate exactly, so the planner uses it |
   | → `staff_users` | `tenant_id = :t AND id = assignment.staff_user_id` — **no `deleted_at` filter** | `test_a_soft_deleted_holder_still_names_the_tile` |
   | → `bookings` | `tenant_id = :t AND id = assignment.booking_id AND deleted_at IS NULL AND status <> 'cancelled'` | `test_a_deleted_booking_renders_an_anonymous_visit` |
   | → `customers` | `tenant_id = :t AND id = bookings.customer_id AND **deleted_at IS NULL**` | `test_a_deleted_customer_renders_an_anonymous_visit` — ⚠ **an Amendment 13 erasure is about the PERSON, not her appointment**, and without this conjunct her name keeps rendering on a payload five roles can open after the platform told her it was erased |

   All five joins are **LEFT**, so an assignment whose source row has been swept still renders a room with `client_label: null`.
2. `fitting_assignment_dresses WHERE tenant_id = :t AND fitting_room_assignment_id IN (…) AND deleted_at IS NULL`.

The read returns a frozen `FloorRead(staff_rows, occupancy_by_staff_id, room_rows, bindings_by_assignment_id)` so `FloorResponse.from_rows` stays a **pure renderer** and the schema module never grows a query (D11).

**The clients and dresses reads** (D16) live here too: today's non-cancelled bookings with **`checked_in_at IS NOT NULL`** whose `starts_at` falls on today's calendar day **in Asia/Jerusalem** via the shipped day computation — `ORDER BY starts_at`, `LIMIT 200`, answering `booking_id`, `client_label`, `starts_at` and nothing else; and live dresses `ORDER BY sort_order, name`, `LIMIT 500`, answering `id`, `name`, `sizes`.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| `populate_existing=True` on the release re-read | drop the flag | **stays GREEN here** — every test in this module opens a fresh session, so the identity map is empty and the flag is a no-op. **Record that in the docstring** and pin it in Task 6's forced interleave instead. F57's shipped note records exactly this discovery |
| `customers.deleted_at IS NULL` on the payload join | drop it | `test_a_deleted_customer_renders_an_anonymous_visit` **RED**; `test_a_deleted_booking_renders_an_anonymous_visit` stays **green**, because it sweeps the appointment rather than the person |
| the `staff_users` join's *absence* of a `deleted_at` filter | add one | `test_a_soft_deleted_holder_still_names_the_tile` **RED** |
| `deleted_at IS NULL` in every `by_id` | drop it | the soft-deleted cases **RED** |
| the explicit `tenant_id` predicate | drop it (RLS still on) | stays **green** — RLS carries it. **Record that in the docstring** rather than pretending the unit test proves the defence-in-depth; it is proven in Task 7 |

- **Done when**: local db suite green; `make lint` clean; the two "stays green" mutations performed, recorded in docstrings and restored. `git show --stat`.
- **Commit**: `feat(floor): the room, assignment and dress-binding repositories and the two-statement payload read`

## Task 3 — Validation, schemas, the two error codes and their handlers, four audit actions (D1, D13, D14)
`backend/app/floor/validation.py` (**✚**), `backend/app/floor/schemas.py`, `backend/app/models/constants.py`, `backend/app/main.py`, `backend/tests/test_floor_validation.py` (**✚**), `backend/tests/test_frontend_constant_parity.py`, `frontend/apps/manage/src/validation.ts`

### The failing tests first (**fast**, no Postgres)

**`test_floor_validation.py`** — `label` stripped; empty → `DomainValidationError`; `MAX_ROOM_LABEL_LENGTH` (**40**) boundary and 41; `sort_order` at `-MAX_SORT_ORDER`, `+MAX_SORT_ORDER` and one past each.
⚠ **`sort_order` uses the house SYMMETRIC bound**, `Field(default=0, ge=-MAX_SORT_ORDER, le=MAX_SORT_ORDER)`, importing `MAX_SORT_ORDER = 1_000_000` from `app/catalog/validation.py:48` exactly as `catalog/schemas.py:46,63,72` and `boutique/schemas.py:73,85` already do. **Not `0 <=`**: negatives are how a row moves to the front without renumbering the rest — which is the reorder control the registry ships — and "reuse the shipped constant while silently halving its range" is the confusing half, because a builder copying the shipped `Field(...)` line gets the symmetric bound and a `0 <=` floor would exist only in prose.

**`test_frontend_constant_parity.py`** — one new `MIRRORS` param, `id="manage-floor"`, mirroring `MAX_ROOM_LABEL_LENGTH` into `apps/manage/src/validation.ts`. Three lines; existing ids are `"manage"` `:71`, `"manage-staff"` `:81`, `"manage-customers"` `:99`.

**The two 409 bodies, in `tests/test_floor_api.py` (extended in Task 5, written here)** — `ROOM_OCCUPIED` and `STAFF_OCCUPIED`, each asserted **including its `details`**, **plus both `details`-less variants**, plus a companion assertion that **no other body in `main.py` grew a `details` key**. The set of dynamic bodies is a thing a reviewer should be able to enumerate.

### The code

- `app/floor/validation.py` — `MAX_ROOM_LABEL_LENGTH = 40`, the label normaliser, and the two new domain errors `RoomOccupiedError` / `StaffOccupiedError`, each carrying an optional `details: dict[str, str] | None`.
- `app/floor/schemas.py` — `Room` (`id`, `label`, `sort_order`, `is_active`, `assignment: RoomAssignment | None`), `RoomAssignment`, `DressBinding`, `Occupancy`, `FloorDress` / `FloorDressList`, `FloorClient` / `FloorClientList`, and the extended `FloorResponse` (`staff`, `rooms`, **`server_now`**). Bodies use `ForbidExtraModel` where a body exists — the house form. **There is no separate `RoomCard` type**: every mutation answers the same `Room` the payload's `rooms[]` elements carry, so the panel patches one tile in place from the server's own row and cannot disagree with itself.
  ⚠ The wire field is **`assigned_at`**, sourced from `created_at`, with a one-line comment saying so (D2). A handover deliberately does not restart it.
- `app/models/constants.py` — `StaffCardStatus.OCCUPIED = "occupied"`, **rewriting** the *"'occupied' is coming and is deliberately NOT here"* comment (`:27-36`) into a statement that F36 gave it a writer. Plus the four `AuditAction` members — `FITTING_ROOM_CLAIMED`, `FITTING_ROOM_RELEASED`, `FITTING_ROOM_HANDED_OVER`, `FITTING_ROOM_DELETED`. **No migration**: `audit_log.action` is plain `TEXT` with no CHECK (`0003_auth.py:71-79`), and this is the seventh block to rely on it.
- `app/main.py` — two `@app.exception_handler`s returning **409** with a body built at raise time, the `DomainValidationError` technique (`:795-799`):

```jsonc
{ "error": { "code": "ROOM_OCCUPIED",  "message": "This fitting room is already claimed.",
             "details": { "staff_display_name": "דנה" } } }
{ "error": { "code": "STAFF_OCCUPIED", "message": "That staff member is already in a fitting room.",
             "details": { "room_label": "חדר 2" } } }
```

⚠ **`details` is OPTIONAL on both codes and is omitted entirely when the occupant read finds nobody** — never `{"staff_display_name": null}`. The loser blocks on the winner's uncommitted index key and gets the violation when the winner commits; between that commit and the occupant read the winner can **release**. There is then no occupant to name, and «{{name}} כבר בחדר הזה.» rendering with an empty interpolation on a legally binding surface is worse than a sentence that admits it does not know.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| the symmetric `ge=-MAX_SORT_ORDER` | change to `ge=0` | the negative-`sort_order` case **RED** |
| the `MIRRORS` param | delete the row, then change one side of the constant | the parity test must go **RED**; confirm it does |
| optional `details` | make it a required key | Task 6's `test_a_claim_whose_occupant_released_first_does_not_name_nobody` **RED** (recorded here, run there) |
| either 409 handler | drop the registration | the 409 body test **RED** (bare 500) |

- **Done when**: `make lint` + `make test` green. **First milestone**: the whole wire contract and both new codes exist with no Postgres. `git show --stat`.
- **Commit**: `feat(floor): the room wire shapes, the two occupancy 409s and the four audit actions`

## Task 4 — `FloorService`: the claim, the release, the handover, the dresses, the registry, and `card_status`'s second argument (D1, D3, D4, D6, D7, D8, D11, D12)
`backend/app/floor/service.py`, `backend/app/floor/schemas.py`, `backend/tests/test_floor_service.py`

**This is the task the whole feature is about.** Read D3 and D6 before writing a line.

### The failing tests first (**fast**, fakes — this is where the two axes are actually proven)

- **claim** — elevated on anyone → allowed; each floor role **on herself** → allowed; each floor role **on another** → `NotAuthorizedError` **and the room repository is never called**. That last clause is the assertion that proves the check runs **before** the read, i.e. that the 403 is not an existence oracle — and it is **AC23**, F57's Risk 5 discharged on the PR that creates the shape rather than deferred to F37.
  ⚠ **F36 is the first feature in the product to take a target staff id in a BODY**, which is the shape `_authorize`'s own docstring names as *the* hazard (`service.py:143-145`). F57's break routes take the target in the **path** and `start_break`'s docstring calls that out (`router.py:94-96`). The body's `staff_user_id` is read **only** as the target and is passed straight into `_authorize(staff_id, actor)`; **no code path on this route may read the body field as an identity.** `_authorize` is reused **by call, verbatim** — one implementation, now four call sites.
- **release** — the repository-never-called assertion **does not apply**, because the target is an assignment id and whose it is can only be learned by reading the row. Asserted instead as: **a non-elevated caller acting on a colleague's assignment gets 404, byte-identical to a nonexistent id.** Not a 403: a 403 on a real id and a 404 on a fake one would discriminate existence.
- **handover** — the role check is now the **route gate** (D8), so the service test is that a non-elevated caller is refused **before any read, on `actor.role` alone, even on her own assignment**. This is D8's asymmetry and the one case a reader will doubt.
- **the two dress routes** — asserted as a **positive**: a seamstress **may** bind and unbind a dress on a colleague's live assignment. D4's recorded permissiveness, asserted rather than defaulted, so it cannot arrive by omission. `removed_by` is what keeps it accountable.
- the `(wrote, row)` mapping onto 200 / 200-unchanged / 404; **an audit row on a write and NONE on a no-op** (a second release, a re-claim resolving to the caller's own assignment, a duplicate dress add); **`occupied` beating `break` in `card_status`**; and the idempotence branch resolved by the **request-keyed read** and never by the constraint name.
- `test_the_card_status_wire_literals_are_exactly_available_and_break` at **`:370`** — renamed and widened to `{"available","break","occupied"}`, still a **set equality**.

### The code — the claim, ordered exactly

```python
# The whole of the claim's concurrency design.
# ⚠ The `try` is OUTSIDE the `async with`, and the INSERT is a CORE
# session.execute(insert(...)), not session.add.
try:
    async with session.begin_nested():             # SAVEPOINT
        row = await self._assignments.claim(session, tenant_id, room_id, staff_id, booking_id)
except IntegrityError as exc:
    # SQLAlchemy WRAPS asyncpg's UniqueViolationError, so the discriminator is
    # exc.orig — spelled defensively: a None reads as unrecognised and re-raises.
    constraint = getattr(exc.orig, "constraint_name", None)
```

1. **Authorize on the two axes, before any read.** `staff_user_id` defaults to the caller.
2. **Read the room `FOR UPDATE`** — `WHERE id = :id AND tenant_id = :t AND deleted_at IS NULL AND is_active`. Missing / deleted / **inactive** / another tenant's → `DomainNotFoundError` → **404**, one body, indistinguishable. Inactive is a 404 rather than a fifth error code because the panel renders no claim control on an inactive room: reaching this branch means the client was a tick stale.
3. **Read the booking** if given — 404 if absent. Predicate: `deleted_at IS NULL`, `status <> 'cancelled'`, **`checked_in_at IS NOT NULL`**, and `starts_at` on **today's calendar day in Asia/Jerusalem** via the shipped day computation.
   **The check-in predicate is what makes D9's table true rather than aspirational**: `deleted_at IS NULL AND status <> 'cancelled'` alone admits **next month's** booking, whose customer's name would then surface on the five-role payload for as long as the assignment stayed open. **`pending_payment` is admitted, deliberately** — the bride is physically standing in the boutique having been checked in, and refusing to name her on a tile over a deposit is the product being clever at the expense of the person in front of it. Stated because F19's rule elsewhere is the opposite.
4. **`try: async with session.begin_nested():` INSERT.** On `IntegrityError`:
   **IDEMPOTENCE IS RESOLVED FIRST, AND IT IS KEYED ON THE REQUEST — NEVER ON THE CONSTRAINT NAME.** When staffer S re-claims the room she already holds, the INSERT violates **both** partial unique indexes at once and Postgres reports only the first that fails, in `RelationGetIndexList` order — i.e. index OID, i.e. **creation order**. Deriving the idempotence branch from the name would make it an artefact of migration ordering and would flip silently after any `REINDEX CONCURRENTLY` or `pg_repack`. If the staff index reported first, a staffer tapping the room she is standing in would read «היא כבר בחדר 2.» — the screen refusing her with the name of the room she is in. So: **one read keyed on `(tenant_id, room_id, target_staff_id)`.** A **hit** → **200** with that card, **no audit row**. Only on a **miss** does the constraint name pick between the two 409s. An **unrecognised** name **re-raises** — a 500 on a violation nobody predicted is correct, and silently mapping it to `ROOM_OCCUPIED` would tell a staffer a lie about furniture.
5. **Audit** `FITTING_ROOM_CLAIMED` in the same transaction, before commit.
6. **Answer the full `Room`, rendered from the database** — F57's D7 contract, and the reason the panel is not optimistic.

**The SAVEPOINT is not a lock in disguise.** A failed flush aborts the enclosing Postgres transaction (`booking/service.py:404`) and F13 declines to recover for that reason. F36 **must** recover: the ruling requires the 409 to **name the occupant**, and the occupant can only be read after the conflict is known. `begin_nested()` issues a `SAVEPOINT`; the `IntegrityError` rolls back to it and leaves the outer transaction alive. It serializes nothing and blocks nobody. *(First use of `begin_nested()` in this codebase — declined opening a second `tenant_session` to read the occupant: another pool checkout, another `set_config`, another BEGIN/COMMIT and a second place for the tenant id to be wrong.)*

**Handover** — the guarded UPDATE, with **`from` captured into a local BEFORE the writer runs**, `end_break`'s ⚠ comment verbatim (`service.py:108-116`): the UPDATE is ORM-enabled DML whose `evaluate` synchronization stamps the new value onto the same identity-mapped instance out of one identity map, so reading it afterwards records the **new** staffer as the **old** one and empties the row of its whole informational content. The audit row is `{"from": …, "to": …}`, F51's `STAFF_ROLE_CHANGED` shape.

**The registry delete** — `by_id_for_update` → `has_active_for_room` as a **separate statement** → stamp `deleted_at` → audit `FITTING_ROOM_DELETED` **carrying the label**, because the row it names is soft-deleted and its label may be re-typed onto a new room tomorrow. Occupied → **409 `ROOM_OCCUPIED`** naming the occupant. **Deactivating an occupied room is allowed** — that is the "the mirror just broke" case, and evicting a half-dressed bride to satisfy a flag would be the product being clever at her expense.

**`card_status` gains a second argument**, and **both break writers must pass the truth**:

```python
def card_status(row: StaffUser, *, occupied: bool) -> StaffCardStatus:
    if occupied:
        return StaffCardStatus.OCCUPIED
    if row.break_started_at is not None:
        return StaffCardStatus.BREAK
    return StaffCardStatus.AVAILABLE
```

`POST …/break/start` answers a full card, and if that staffer is in a room the card must say `occupied`. So both break writers gain **one indexed lookup** against `idx_fitting_room_assignments_staff_active` before building their response. Stated because *"pass False, it's just the break route"* is the shortcut that would ship a card contradicting the panel it lands in five seconds later. **Counted rather than assumed**: `card_status` has **one** app call site (`schemas.py:46`, plus two in `test_floor_service.py:366-367`); `StaffCard.from_row` has **three** (`schemas.py:56`, `router.py:97`, `router.py:106`).

⚠ **`occupied` beats `break`.** She is in a fitting room with a client; the break is a stale toggle nobody cleared, and telling a shift manager that a person standing in room 2 is «בהפסקה» is the screen lying about something she can see. `break_started_at` stays on the wire regardless.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| `_authorize` running **before** the room read | move it after | the never-called assertion **RED** (AC23) |
| the request-keyed idempotence read | branch on the constraint name instead | **stays GREEN in this module** — fakes raise nothing. Pinned in Task 6's reverse-index-order test. **Record that here** |
| `begin_nested()` | delete the savepoint | **stays GREEN here** — a fake repository raises no `IntegrityError` at all. Pinned in Task 6 |
| the `from` capture before the write | move it after | **stays GREEN across all fast tests** — monkeypatched repositories never stamp anything. F57's shipped note records this precise result. Pinned in Task 6 |
| the unrecognised-constraint re-raise | map it to `ROOM_OCCUPIED` | the unknown-violation test **RED** |
| `occupied` beating `break` | flip the order in `card_status` | the precedence test **RED** |
| the break writers' occupancy lookup | pass `occupied=False` | the break-route-answers-occupied test **RED** |

**Four of those seven stay green here and that is the finding, not a failure.** Write them down in the module docstring and pin each in Task 6 — that is exactly how F57 discovered its two vacuous tests.

- **Done when**: `make lint` + `make test` green. **Second milestone**: every branch of the authorization matrix and the whole `(wrote, row)` contract are exercised with no Postgres. `git show --stat`.
- **Commit**: `feat(floor): the claim, the release, the handover, the dress bindings and the occupancy status`

## Task 5 — Ten routes on the existing floor router, and the three shipped comments this PR must rewrite (D9, D10, D16)
`backend/app/floor/router.py`, `backend/app/floor/service.py`, `backend/app/floor/schemas.py`, `backend/tests/test_floor_api.py`, `backend/tests/test_staff_role_gating.py`

### The failing tests first (**fast**)

**`test_floor_api.py`** — `FLOOR_ROUTES` grows from **three rows (`:51-55`) to thirteen**, and **D10's table is the only source for that count**: a figure sized from prose reds a table-driven test on the first run, and this one powers the 401 walk (`:207`), the wiring walk (`:218`, `:235`), the `no-store` parametrization (`:245`, `:256`) and the shadowing guard. `FakeFloorService` grows the ten new methods. **`SPEC_ERROR_CODES` (`:63-68`) becomes SEVEN** and stays set-equal — the two 409s plus `VALIDATION_ERROR`, which the registry's label validation makes observable on this router for the first time. Its ⚠ *"NO NEW MEMBER"* comment (`:60-62`) is rewritten rather than deleted.

⚠ **`test_a_toggle_answers_one_card_and_not_the_whole_floor`'s key set at `:346` grows to SIX with `occupancy`, and stays a SET EQUALITY.** It is the assertion that catches a seventh field arriving unreviewed on a five-role payload, which on this particular payload is the whole of D9's argument mechanised. Named here because a builder working the enumerated edit list would otherwise hit an unexplained red on a file this spec claims to have fully enumerated.

The extended payload asserted as a literal for one occupied and one free room, **including `server_now`**. `test_no_card_carries_an_email_or_any_credential` (`:349-358`) is **unaffected** — `email`, `password_hash`, `tenant_id` and `deleted_at` stay off the card, which is what that test actually pins.

**`test_staff_role_gating.py`** — `FLOOR_OPEN` (`:102`) grows from three to **nine**, gaining the **six** new all-five paths (claim, release, dresses POST, dresses DELETE, `GET /dresses`, `GET /clients`) as **route TEMPLATES** — not concrete urls; the walkers read `route.path` and mixing spellings is a CI round trip (`:93-96`). The **four tightened paths** — three registry verbs plus **handover** — are **deliberately absent**, which is the assertion that the tightening is real and what keeps the table's shipped comment (*"the exhaustive list of what they may reach"*, `:84`) true.

⚠ **The intersection classifier at `:282-284` must not be touched.** F57's Risk 1 predicts this exact red and forbids the `any(...)` relaxation that "fixes" it: `any(...)` would report a correctly tightened route as admitting the floor roles and red-fail it. **F36 is the first customer of the decision F57's walker was written for** — its comment names F36 by name.

### The code

| Method | Path | Effective roles | Why |
|---|---|---|---|
| `POST` | `/manage/floor/rooms` | owner, shift_manager | **tightened** |
| `PATCH` | `/manage/floor/rooms/{room_id}` | owner, shift_manager | **tightened** |
| `DELETE` | `/manage/floor/rooms/{room_id}` | owner, shift_manager | **tightened** |
| `POST` | `/manage/floor/rooms/{room_id}/claim` | all five | self, or elevated on anyone (service) |
| `POST` | `/manage/floor/assignments/{assignment_id}/release` | all five | self, or elevated (service; 404 on refusal) |
| `POST` | `/manage/floor/assignments/{assignment_id}/handover` | owner, shift_manager | **tightened — a pure role predicate, so it belongs in the gate** |
| `POST` | `/manage/floor/assignments/{assignment_id}/dresses` | all five | **no ownership check** — D4 |
| `DELETE` | `/manage/floor/assignments/{assignment_id}/dresses/{binding_id}` | all five | same |
| `GET` | `/manage/floor/dresses` | all five | D16's one-shot list |
| `GET` | `/manage/floor/clients` | all five | D16 — **the only thing that can supply `booking_id`** |

Tightening is `dependencies=[Depends(require_role(StaffRole.OWNER, StaffRole.SHIFT_MANAGER))]` **per route**, composing to that intersection with the router's five (`auth/dependencies.py:44-45`).

**Handover is tightened at the ROUTE, not in the service, and the reasoning is two-part.** First, `FLOOR_OPEN`'s shipped comment is *"the exhaustive list of what they may reach"* — adding `handover` to it would make a structural test assert that a seamstress may reach a route she always gets a 403 on, i.e. the test would stop describing the product. Second, **a 403 is TERMINAL for the whole floor panel**: `usePoll.terminalOf` returns `"access"` for any 403 (`:100-108`) and `FloorPanel.tsx:349-367` clears every card — so a rendered control reaching an unreachable route **blanks a seamstress's only screen**. Handover's predicate depends on nothing about the target, which is precisely what `RoleGate` is; D6's and D7's are target-dependent and genuinely cannot live in a gate.

**All three shipped "ZERO customer data" comments are rewritten in this PR** — `router.py:11-17`, `service.py:68-75`, `schemas.py:13-16` — to the sentence D9 lands on: *"the floor payload carries the minimum customer datum required by the person standing on the floor — at most one name per occupied room, for the duration of the fitting, never the day's customer book."* On a surface this spec itself calls legally sensitive, **leaving the widest role gate in the product justified by a sentence that is no longer true is worse than never having written it.** `schemas.py`'s *"a card is … deliberately nothing else"* is falsified directly by `occupancy.client_label` landing inside `StaffCard`. `router.py` additionally carries D9's distinction table in prose: *the day book* versus *the ≤3 people physically in fitting rooms right now*.

⚠ **`floor/router.py`'s docstring says `test_dashboard_api.py:49-51` "says SIX; it is a historical note in another feature's module".** F36 adds no router, so the count stays **seven** and both notes stay as they are. **Do not "helpfully" renumber a third file.**

**No rate limiter** (no `/manage` router carries one — `router.py:39-42`). The **eight** new mutating verbs are CSRF-fenced by `CsrfOriginMiddleware` because they are mutating methods (`csrf.py:15,48`); the **two** new GETs are not, and their protection is the session cookie and the role gate alone.

**Every path's second segment is `floor`, so `vite.config.ts` needs NO EDIT** — and that is not free to get wrong. `test_spa_serving.py:372-401` asserts **set equality** between the live route table's second segments and the `^/manage/(…)` alternation, and a mismatch breaks **only a developer's machine** while production, CI and the whole suite stay green, serving the SPA shell where the API should be. It has bitten this repo twice (F52, then F57's plan, which claimed no edit was needed and was wrong). **Mounting the registry at `/manage/rooms` would have cost the edit; `/manage/floor/rooms` costs nothing and reads better anyway.** AC16 is the assertion: `git diff main -- frontend/apps/manage/vite.config.ts` is **empty**.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| the tightened `require_role` on any one of the four | drop it | `test_the_floor_roles_reach_exactly_the_floor_routes` **RED** as `unexpected=[that path]` |
| `FLOOR_OPEN`'s omission of the four | add `handover` to it | the same test **RED** as `missing` — confirm the table is a real assertion in both directions |
| `FLOOR_ROUTES` sized from prose | write twelve rows instead of thirteen | the wiring walk **RED** on a 404 |
| the `occupancy` key on `StaffCard` | drop it | the `:346` set equality **RED** |
| mounting the registry at `/manage/rooms` | change the prefix | `test_the_manage_dev_proxy_names_every_manage_api_segment` **RED**. ⚠ **Run this one deliberately, then revert it** — it is the only way to prove AC16 is a live assertion rather than a coincidence |

- **Done when**: `make lint` + `make test` green; `git diff main -- frontend/apps/manage/vite.config.ts` empty; the proxy mutation performed and reverted. **Third milestone**: all thirteen routes, both new codes and the whole extended payload are exercised end to end with no Postgres. `git show --stat`.
- **Commit**: `feat(floor): the ten room routes, their tightened gates, and the three comments this PR falsifies`

## Task 6 — The forced interleaves (**`db`-marked, run locally**) (D1, D3, D4, D6, D7, D8, D9)
`backend/tests/test_floor_rooms_db.py` (**✚**)

**This is the task the epic's success criteria are written against, and F36's races are harder than F34's or F57's.**

⚠ **The `test_floor_db.py` seed rule applies verbatim: every row this module COMMITS holds `owner` or `shift_manager`, never a floor role.** `migrated_db` is session-scoped, pytest collects alphabetically, and a committed `reception` row reddens three tests in `test_migrations.py` that have nothing to do with rooms (`test_floor_db.py:12-32`). Nothing here asserts anything about the actor's role — the gate is Tasks 4 and 5's job.

### The interleave shape, spelled out rather than copied by shape

`asyncio.gather` is **deliberately not used** for any deterministic branch, for the reason `test_floor_db.py` states verbatim: gather does not **order** two transactions, so the loser most often runs after the winner commits and the branch the test exists to prove goes green without the mechanism ever being exercised. The mechanism is that `tenant_session` is `async with session_factory() as session, session.begin()`, so **exiting the context manager IS the commit** (`db/tenant.py:25`), and two nested `tenant_session`s on one `NullPool` factory take two separate connections.

**The ORDER is what makes it safe for an INSERT race** (`test_floor_db.py:296-325`): the **loser** opens its session and **READS** (a plain SELECT, which takes no row locks) → the **winner's inner `async with` opens, writes and EXITS, which is the commit** → only then does the loser issue its write. So the loser's statement always runs against a **committed** key and fails immediately; nothing blocks and nothing hangs. *That is exactly what "landing in the gap" means* — the loser decided the room was free, then the world changed under it.

**What must NOT be attempted:** a shape in which the loser's INSERT is issued while the winner's transaction is still open. A duplicate-key INSERT does not return — it **blocks** on the winner's uncommitted index entry until that transaction ends — and with the winner's `async with` nested inside the loser's coroutine the winner can never reach its commit, so **the test hangs to the CI timeout**. A builder who hits that will reach for `asyncio.gather`, which is forbidden and which yields exactly the vacuous test this section exists to prevent. **No blocking is needed to prove the guarantee: the index refuses the second claim whether the first is committed or not; the committed-first ordering is the one that is also testable.**

### The tests, and the mutation each one MUST survive

| Test | Mutation that MUST turn it red | Why nothing else catches it |
|---|---|---|
| `test_a_second_claim_landing_in_the_gap_is_refused_and_names_the_occupant` | **change the room index predicate to `WHERE deleted_at IS NULL`** (drop `released_at IS NULL`) | the double-claim still fails — but `test_a_released_room_is_immediately_reclaimable` goes red, which is **the pair** that pins the predicate rather than the index |
| ″ | **remove `session.begin_nested()`** | the `IntegrityError` aborts the outer transaction, the occupant read raises `PendingRollbackError`, and the 409 becomes a **500**. **No fast test can see this** — a fake repository raises nothing |
| `test_a_worker_cannot_hold_two_rooms` | **drop `idx_fitting_room_assignments_staff_active`** | the **ONLY** test that fails. The room index is satisfied (two different rooms), so every other assertion in the feature passes with the second index gone — **including the staff card's `occupied`, which would then have to *choose* between two rows** |
| `test_a_released_room_is_immediately_reclaimable` · `test_a_second_release_writes_nothing` | see the predicate pair above | AC5 |
| `test_a_release_landing_in_the_gap_renders_the_database_value` | **remove `populate_existing=True` from the re-read** | every test that opens a **fresh** session per operation has an empty identity map, so the flag is a no-op there. F57's shipped note: with only the non-interleaved tests present, removing it changed **nothing** |
| `test_a_handover_preserves_the_bindings_and_records_the_previous_holder` | **move the `from` capture AFTER the writer** | F57's shipped note records this precise mutation leaving **all** fast tests green, because monkeypatched repositories never stamp anything. Only a real session's identity map poisons the local |
| `test_a_concurrent_double_add_yields_one_binding` | **remove `index_where` from the `ON CONFLICT` inference** | the statement then fails to match the partial index and raises instead of doing nothing; separately, `test_a_removed_dress_can_be_re_added` goes red if the index is made total |
| `test_an_add_racing_a_remove_does_not_silently_lose_the_add` | **revert `DO UPDATE SET updated_at` to `DO NOTHING`** | the **ONLY** test that fails. Every add-vs-add and every sequential remove-then-re-add stays green with `DO NOTHING`, which is precisely why the lost update it reintroduces is invisible without this pair |
| `test_a_room_cannot_be_deleted_out_from_under_a_claim` | **remove the `FOR UPDATE` from the delete's room read** (and from the claim's) | no other test takes two statements against one room from two transactions. Without the lock the delete's occupancy check reads a snapshot the claim is not yet in, both commit, and the result is **a soft-deleted room holding a live assignment — a state with no UI path to release it**, whose staffer can never claim another room, and no failing assertion anywhere |
| `test_re_claiming_your_own_room_is_a_200_whichever_index_reports` | **create the two partial unique indexes in the REVERSE order in a scratch schema and re-run** | Postgres reports whichever index has the lower OID, i.e. creation order. A branch derived from the constraint name passes in one order and **refuses the staffer her own room** in the other, and nothing else in the suite would ever run the second order |
| `test_a_claim_whose_occupant_released_first_does_not_name_nobody` | **restore `details` to a required key** | with `details` required this path either raises building the body or ships `{"staff_display_name": null}` and the panel renders an empty interpolation. Every other 409 test has an occupant to read |
| `test_a_booking_that_has_not_checked_in_cannot_be_bound_to_a_room` | **drop `checked_in_at IS NOT NULL` from the claim's booking predicate** | every other booking in the suite is checked in, so the predicate is invisible without a fixture that is not — and its absence is what would let next month's bride's name onto the five-role payload |
| `test_a_deleted_customer_renders_an_anonymous_visit` | **drop `customers.deleted_at IS NULL` from the payload join** | `test_a_deleted_booking_renders_an_anonymous_visit` stays **green**, because it sweeps the appointment rather than the person. Only this one catches the Amendment 13 erasure shape |
| `test_a_soft_deleted_holder_still_names_the_tile` | **add a `deleted_at` filter to the `staff_users` join** | D11's ghost holder: `list_live` drops her from `staff` (no card, so no `occupancy`) while the rooms join still yields an occupied tile. This is why `staff_display_name` is `string \| null` and why only an elevated caller can clear such a tile |
| `test_the_assignment_stores_no_personal_column` | add a `client_name TEXT` column to the migration | AC8's structural half — the column list of all three tables is pinned |

⚠ **EVERY ONE OF THESE MUTATIONS MUST BE RUN, NOT REASONED ABOUT.** F34 and F57 each found a real vacuous test this way, and F57's was a focus test jsdom could never have failed. **A test whose named mechanism can be removed with the suite still green is VACUOUS and must be rewritten**, not shipped with a note.

- **Done when**: `bash "<scratchpad>/run-db-tests.sh"` green; **every mutation in the table performed and restored**, with the result of each recorded in the run report. `make lint` clean. `git show --stat`.
- **Commit**: `test(floor): the forced-interleave race suite for the claim, the release, the handover and the dress bindings`

## Task 7 — The RLS isolation suite (**`db`-marked, run locally**) (AC10, AC11)
`backend/tests/test_fitting_rooms_isolation.py` (**✚**)

**Non-negotiable, and it is the crown-jewel suite `architecture.md` calls permanent.** Connected **only as the app role** over a `NullPool` engine via the **`app_role_url`** fixture — **never `migrated_db`**, because the container superuser bypasses RLS and GRANTs unconditionally and every assertion would pass vacuously.

### The failing tests first

- tenant A writes a room, an assignment and a binding; **tenant B's every reader returns `None` / empty / 0**, three times over
- a foreign-tenant room id, assignment id and binding id each read as **missing (`None`, the 404 path), never a 403** that would confirm existence
- tenant B can neither **claim** A's room, nor **release** A's assignment, nor **hand over** A's assignment, nor **bind or unbind a dress** on it — every attempt is a **404 indistinguishable from missing** (AC10)
- tenant B's payload read never joins A's rows; tenant A re-reads and nothing of hers moved
- **the GRANTs are exercised** — the app role can `INSERT`, `SELECT` and `UPDATE` on all three tables. Omitting a GRANT fails **nothing** until exactly here, as `permission denied`

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| `enable_tenant_rls(...)` in the migration | delete one call, re-run | **every** probe on that table **RED** — if any stays green the suite is connected as the superuser and is worthless |
| the `app_role_url` fixture | swap to `migrated_db` | the probes go **GREEN vacuously** — run this once, deliberately, confirm it, then restore. **That is the proof the suite measures RLS and not nothing** |
| one of the three GRANTs | drop it | that table's write probe **RED** as `permission denied` |

- **Done when**: local db suite green; both vacuity mutation-checks performed and restored. `make lint` clean. `git show --stat`.
- **Commit**: `test(floor): forced RLS isolation for the rooms, the assignments and the dress bindings`

---

# Part II — the frontend

> **Capture the qa-greps baseline BEFORE the first frontend edit** (C12) and diff it after every frontend task:
> ```
> make qa-greps > "<scratchpad>/qa-greps-baseline.txt" 2>&1
> ```
> The ten `check` calls read `apps/storefront/src` only, but the trailing **date-reads review block** (`qa-greps.sh:62-67`) reads `apps/manage/src`. **F36 computes elapsed minutes and is the feature most likely to reach for a formatter** — spec D17: *"'elapsed time' invites a date library, and it must not."* Elapsed minutes are arithmetic on two ISO instants and involve no timezone at all.

## Task 8 — The wire types, `ApiError.details`, the ten methods, and the i18n namespace with its three test edits (D14, D17 / DC-3, DC-8, DC-11, DC-14)
`frontend/apps/manage/src/api.ts`, `…/validation.ts`, `…/i18n/he.ts`, `…/i18n/ar.ts`, `…/__tests__/api.test.ts`, `…/__tests__/i18n.test.ts`

### The failing tests first

**`api.test.ts`** — each of the ten methods hits its path with the body verbatim (**no case conversion — this app speaks the backend's snake_case**); a 409 with `details` produces an `ApiError` **carrying** them; a 409 **without** `details` produces one whose `details` is `undefined`, never `null`.

**`i18n.test.ts` — THREE edits, and the second and third are DC-3's whole point:**

1. **`HE_F36` must be FOLDED INTO `HE`, not merely declared.** The file says so about itself at `:33-37`: *"Folded in, not just declared: without this the resolve check, BOTH register guards and the `ar` parity guard silently skip every F52 key."* Without the fold, **all 68 hand-transcribed strings ship unchecked** for an exclamation mark (`:396-398`), for the `/נשלח|תישלח|בדרך/` send-ban (`:400-402`) and for a missing `ar` key (`:417-420`). **This is the one line a builder working from the spec's enumerated edit list will not write** (deck F-5).

   ```ts
   const HE_F36 = entries(he.translation, (key) => key.startsWith("rooms."));
   const HE = [...HE_F15, ...HE_F51, ...HE_F52, ...HE_F17, ...HE_F34, ...HE_F57, ...HE_F53, ...HE_F36];
   ```

   **No `nav.` term in the selector, and that is an assertion rather than an omission** — F36 adds no nav row. Every other feature's constant starts `key === "nav.x" || …`; this one does not.

2. **An `HE_F36`-scoped digit guard** (DC-3). The shipped one at `:377-380` is `HE_F57.filter(…)` — F57-scoped — so **there is no digit guard over `rooms.*` at all**, and `copy.md` §11's «0» row for rule 4 is a hand-count wearing a citation. Mirror it: no literal digit in any `rooms.*` value, no exemption needed (every number on this panel is an interpolation).

3. **`ar[key] === he[key]` for every `rooms.*` key** (DC-3, AC13). The shipped `ar` guard at `:417-420` checks **presence** only (`!(key in ar.translation)`) and the `:411-415` one checks for `""`. Neither can see a **wrong value**, and *"non-empty"* passes on an English string, a `TODO`, or a **different** Hebrew wording — a live hazard when 68 keys are transcribed by hand into two files with no he/ar parity guard anywhere in the repo (deck F-6, spec Risk 12). One line, exactly the stated rule, scoped to this namespace so Risk 12 stays as it is.

**One comment renumber and no others** (DC-14): `:315-316`'s *"29 `floor.*` keys plus `nav.floor`"* → **30**, because `floor.statusOccupied` rides in `HE_F57` by prefix (`:40-42`: *"the namespace names the payload, not the feature that added the key"*) and inherits F57's digit guard and its `> 28` floor for free. ⚠ **Do not "helpfully" renumber anything else in that file** — the two `it(` blocks at `:257` and `:320` both claim *"resolves the eleventh nav item"* since F53 landed. It is a shipped inconsistency, it is not F36's, and touching it puts an unrelated edit on this diff.

### The code

- `api.ts` — `StaffCardStatus` gains `"occupied"` (the union at `:390`, its comment at `:387-389` rewritten); `StaffCard` gains `occupancy: Occupancy | null`; `FloorResponse` gains `rooms: Room[]` **and `server_now: string`**; new `Room`, `RoomAssignment`, `DressBinding`, `Occupancy`, `FloorDress`, `FloorDressList`, `FloorClient`, `FloorClientList` — **there is no `RoomCard`**; **`ApiError` gains `readonly details?: Record<string, string>`** (`:9-19`) and **`extractError` reads it when present** (`:26-37`). Six lines. ⚠ **Typed `| undefined`, never `| null`**, so the `{"staff_display_name": null}` shape cannot be constructed at all. Ten new methods on the exported `api` object.
- `validation.ts` — `MAX_ROOM_LABEL_LENGTH`, mirrored from `app/floor/validation.py` (Task 3's `MIRRORS` param).
- `i18n/he.ts` and `i18n/ar.ts` — the `rooms.*` namespace plus `floor.statusOccupied`, **flat dotted keys appended as a per-feature block**, the shipped `floor.*` shape (`:608`). **Transcribed from `copy.md`, which is the single source for both columns** — never from spec D17's table, which the deck supersedes and which is missing fourteen keys the components require. `ar` values are **the approved Hebrew standing in untranslated and are never empty strings**: i18next's `returnEmptyString` default renders `""` rather than falling back. `lng` and `fallbackLng` stay `"he"`; no switcher.
  - **DC-8**: `rooms.error.notFound` and `rooms.error.assignmentGone` ship in **two forms** — the running form promising «בעדכון הבא» and a paused form pointing at «חידוש».
  - **DC-11**: the staff card's occupancy line carries `rooms.clientLabel` on its middle fragment.
  - **Reuse before invention** (spec D17, deck §9's 17 rows): `floor.refresh`, `floor.pause*`, `floor.resume*`, `floor.paused*`, `floor.idleStopped`, `floor.staleAt`, `floor.staleBody`, `floor.updatedAt`, `floor.sessionEnded`, `floor.accessEnded`, `floor.reload` and `staff.loadFailed` are **all shipped and all reused unchanged**. The rooms panel is inside `FloorPanel`'s poll, so it inherits every one of its states and **must not spell any of them a second way**.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| the `HE_F36` fold | declare the constant without adding it to `HE` | the resolve check, both register guards and the `ar` guard **silently pass** on a deliberately broken key (add a `!` to one value and confirm it goes **green** without the fold and **red** with it). ⚠ **Run this one — it is the whole of DC-3** |
| the `rooms.*` digit guard | delete it, then put a literal `5` in a value | the guard must go **RED**; confirm it does |
| `ar[key] === he[key]` | delete it, then change one `ar` value to a different Hebrew wording | the presence guard stays **green** and the equality guard goes **RED** |
| `details?: Record<string,string>` | type it `| null` | the `details`-less 409 test **RED** on `undefined !== null` |

- **Done when**: `make fe-test` + `make fe-build` green; `pnpm -r lint && pnpm -r typecheck` clean; `make qa-greps` byte-identical to the baseline; every mutation performed and restored. `git show --stat`.
- **Commit**: `feat(manage): the room wire types, ApiError.details, and the rooms copy deck with its three i18n guards`

## Task 9 — `FloorPanel`: the `mutate` extraction, the three-way badge, the occupancy line, and **the defect F36 creates** (D12, D15 / DC-11, deck F-2)
`frontend/apps/manage/src/components/FloorPanel.tsx`, `…/__tests__/FloorPanel.test.tsx`

### ⚠ Deck F-2 — the defect F36 CREATES, and the spec names one third of it

`FloorPanel` derives `onBreak` from `card.status` at **three** sites. Spec D12 names the `Badge` (`:556-557`) and fixes it. The other two are named nowhere in the spec and I have verified both:

| Site | Shipped code | What `status: "occupied"` does to it |
|---|---|---|
| `:523` | `const onBreak = card.status === "break"` | the derivation itself |
| `:556-557` | `<Badge variant={onBreak ? "warning" : "success"}>{t(onBreak ? "floor.statusBreak" : "floor.statusAvailable")}</Badge>` | falls to the **else** branch and prints **«פנויה»** about a woman standing in room 2 — the lie D12 exists to prevent, one word over |
| `:566` | `{onBreak && card.break_started_at !== null && (` | **the since-line disappears** for a staffer who is on a break *and* in a room |
| `:281`, `:592` | `const onBreak = card.status === "break"` inside `toggle()`; `variant={onBreak ? "ghost" : "secondary"}` | ⚠ **the control calls `api.startStaffBreak` instead of `endStaffBreak`.** **A staffer who forgot to end a break and then claimed a room can never end it from this screen** — the button reads «להפסקה» until she releases the room |

**The fix is one line at each of `:281` and `:566`: derive from `card.break_started_at !== null`, not from `status`.** It needs no new string, it is behaviour-identical on every payload F57 can produce (so D15's zero-edit rule survives), and it requires **a NEW test block with a named mutation, because nothing else in the suite goes red without it.**

### The failing tests first

**Existing blocks pass UNEDITED. That is D15's acceptance rule and it is the instrument that tells a faithful refactor from a subtly different one.** New `it(` blocks are added freely; **an edit to an existing expectation means the extraction is wrong** and a reviewer seeing one should stop and read D15.

New blocks:
- **an occupied staff card reads «תפוסה», her room and her client, and NOT «פנויה»** (AC22) — the one a reviewer should look for
- her role renders as **muted words in a bare `<bdi>`, never a second `Badge`** (deck P-2)
- **`occupied` beats `break`** on the wire and on the render
- **deck F-2, three named mutations**: with `status: "occupied"` and `break_started_at` non-null, (a) the since-line **renders**, (b) the control reads «חזרה» and calls `endStaffBreak`, (c) the badge reads «תפוסה». Mutation for each: revert that site to `card.status === "break"`
- the occupancy line carries `rooms.clientLabel` (DC-11) and `rooms.anonymous` when `client_label` is null
- **`mutate`'s shared re-arm**: a room action that **fails** leaves the loop polling (the `.finally()` re-arm — F34's D4.4, *"the test that would still pass if it were dropped, and so would every other test here, which is exactly why it is named"*)

### The code

**`mutate(fn)` is extracted from the shipped `toggle()` (`:280-341`) and is this feature's ONE refactor of F57's code.** The five-part dance every room action needs identically: increment `mutationsRef`, `poll.clearTick()`, `poll.bump()`, run, classify a terminal error through `poll.fail`, then in the **`.finally()`** decrement and `poll.reschedule()` when the count reaches zero. Copying it into `RoomsPanel` would be six chances to drop the re-arm — the mistake whose F34 form was *"the loop survived unmount"* and whose F57 form the shipped comment names (`:334-336`).

`<RoomsPanel rooms={floor?.rooms ?? null} serverNow={…} fetchedAt={…} selfId={selfId} role={role} mutate={mutate} onCue={setCue} />` renders **above** the staff list — a staffer opens this screen to find a free room; the staff cards are the reference, the rooms are the action. The freshness line and the pause control stay exactly where F57 put them, **first stop inside the panel, before any content** (`:434-440`).

`holdRef`'s comment (`:83-88`) gains the rooms case: **a room being claimed grows its tile by a holder line, a role line, a client line, an elapsed line, a dress list and two more controls — far more than the ~20px the mechanism was built for — directly above the tile a finger is travelling toward.**

**`lib/usePoll.ts` gets a ZERO-LINE DIFF.** Not one line. Four features are queued to import it and a change here would be four features' problem.

- **Done when**: `make fe-test` + `make fe-build` green; **`git diff main -- frontend/apps/manage/src/lib/usePoll.ts` is EMPTY**; every shipped `FloorPanel.test.tsx` expectation passes unedited; the three F-2 mutations performed and restored; `make qa-greps` byte-identical. `git show --stat`.
- **Commit**: `feat(manage): the shared mutate dance, the third card status, and the onBreak derivation F36 breaks`

## Task 10 — `RoomsPanel` (D15, D16, D18 / DC-1, DC-4, DC-6, DC-7, DC-8, DC-10, DC-12)
`frontend/apps/manage/src/components/RoomsPanel.tsx` (**✚**), `…/__tests__/RoomsPanel.test.tsx` (**✚**)

### The failing tests first

**Render** — tiles show label, occupancy **word**, staffer name, **her role as muted words in a bare `<bdi>`** (and **no role line at all when `roleLabelKey` returns `null`** — DC-12), client label, elapsed minutes and the dress list; an anonymous assignment renders `rooms.anonymous`; a **holder-gone** tile renders `rooms.holderGone`; an inactive tile is greyed (a **token swap, never `opacity-*`**), carries the **word** «מחוץ לשירות» and offers **no** claim control; the empty state carries the CTA for an elevated role and **no CTA** for a seamstress.

**AC21 — which control EXISTS is the rendered form of the two axes.** For `role="seamstress"` the handover control, the release control on a colleague's tile, the empty-state CTA **and the populated-state «ניהול חדרים» trigger are ALL ABSENT**; all four are present for `owner`. **No disabled buttons, no lock glyphs — absence**, per `FloorPanel.tsx:525-529`. This is what keeps P-6's 403-is-terminal rule **unreachable by design rather than by luck**: a 403 stops the loop permanently and clears every card, so a seamstress who tapped a control the server will refuse would get a blank screen and a reload button — for the three floor roles, the whole product going dark.

**Mutations** — a claim patches the tile **from the response** and is disabled while in flight; a double-tap fires **one** request; a 409 `ROOM_OCCUPIED` renders the occupant's name from `details`; a `details`-less 409 renders `rooms.error.roomOccupiedUnknown`; a 409 `STAFF_OCCUPIED` renders the room label; a 404 renders `rooms.error.notFound` and is **not** terminal; a 403 **is** terminal; **after a FAILED action the loop keeps polling**.

**DC-8** — a 404 arriving while `mode !== "running"` renders the **paused** variant, not «בעדכון הבא». Mutation: drop the branch and assert the running sentence appears on a paused panel.

**DC-4 — the inline client `Select`'s state contract.** Each free tile's selected `client_id` is **local state keyed by room id**; tiles are keyed by `room.id`, so React preserves the subtree and a repaint mutates text nodes inside a stable element. **A poll tick landing with a client selected on tile 3 leaves that selection alone.** Named test, mutation: key the state by index instead of by id and drive a tick that reorders the list.

**The announced region** — it **does not change on a poll tick** and **does** change on an action, driven over **several consecutive ticks with the cue already populated** (`FloorPanel.tsx:194-201`): assigning a byte-identical string to a text node still produces a real `childList` mutation inside `role="status"`, and a single-tick assertion passes against the broken version whenever the cue starts empty. **The cues name the ROOM and never the client** — the region is persistent, so a bride's name in it would sit on a five-role screen for an arbitrary length of time.

**The focus moves — SIX, not five, each with a named non-vacuous mutation:**

| # | Move | Destination | Mutation |
|---|---|---|---|
| 1 | a failed room action | the tile's alert, keyed on the error state, **not raised in the handler** (the alert node does not exist when `setError` runs) | delete the `[tileError]` effect |
| 2 | a successful room action | the tile's **current** primary control via a `Map` keyed by room id, **guarded on `document.activeElement === document.body`** | delete the restore effect |
| 3 | a tile that leaves the list while holding focus — **by a registry delete OR by a TICK** (DC-6: another elevated user deleting a room from her own device, which arrives through the rooms `load`, not through this user's handler — `FloorPanel.tsx:257-262`) | the rooms `h3` | delete the departing-tile check |
| 4 | closing the dress or handover dialog | the tile's trigger, falling back to the `h3`. ⚠ **the 404 collision: move 1 wins over the native `<dialog>` return**, which fires second | make the native return win |
| 5 | a poll tick that removes the open dialog's assignment | close the dialog, focus the tile's control or the `h3` — **never `<body>`** | remove the open-dialog reconciliation |
| **6** | **DC-1 — a poll tick that clears the FOCUSED tile alert** | the tile's control, falling back to the `h3`. Set the flag inside the rooms `load` **before** the new tiles are applied (the only moment both lists exist) and guard on `document.activeElement === document.body`. The shipped analogue is `FloorPanel.tsx:114-127` → `reclaimFocusRef` | delete the reclaim branch and assert focus is on `<body>` five seconds after a refused claim |

⚠ **jsdom is the trap and F57's own success-path focus test was VACUOUS because of it**: jsdom does not blur a disabled element, so `document.activeElement` never became `<body>`, the guard never passed, and the entire restore effect could be deleted with the suite green. **A test for move 2 must explicitly blur the tapped control before the promise resolves.** `@boutique/ui`'s `Button` is `disabled={disabled || loading}` and **every room action is that shape.**

**An axe pass, explicitly not sufficient** — axe cannot see a focus move that never happened (three shipped instances in this repo), and axe has **no rule for SC 2.2.2**.

### The code

Tiles (label, occupancy word, holder name, role, client label, elapsed minutes, dress list), the claim control **plus its inline client `Select`**, the release and handover controls **rendered only when the caller may use them**, the per-tile alert, the empty state, the greyed inactive tile, the holder-gone tile.

**DC-10 — the rooms `h3` renders in EVERY state including R-empty**, because it is move 3's and move 6's focus-rescue target. Deleting your only room returns the panel to `EmptyState` and replaces the heading-row trigger with the CTA; the `h3` survives both transitions.

**DC-7 — the 295px rules.** `break-words` on the **client row**, the **`rooms.holderGone` sentence** and the **dress name**; **`min-w-0` on the dress row's `<span>`**, because `flex items-center justify-between gap-3` with no `min-w-0` cannot shrink and pushes «הסרה» out of a 295px tile. The tile's own text block already gets `min-w-0 grow` for exactly this reason (`FloorPanel.tsx:539`).

**Elapsed minutes** — `minutes_elapsed` is **not** on the wire, and it is **not** `Date.now() − assigned_at` either. F57 is not the precedent: `FloorPanel.tsx:563-575` formats an **absolute** instant through `jerusalemTime` and never subtracts. The envelope carries `server_now`; the client computes

```ts
minutes = Math.floor(((serverNow + (Date.now() - fetchedAt)) - assignedAt) / 60000)
```

— `fetchedAt` being the `Date.now()` captured when the tick resolved, so only the **elapsed** device clock is trusted (drift-free over five seconds) and never the absolute one. **No interval of its own, no date library, no new formatter** (C12).

**Bidi**: `<bdi dir="ltr">` around every numeric run; **bare `<bdi>`** around every Hebrew free-text run — forcing LTR on a Hebrew name reverses its words. **No truncation and no ellipsis on a client label, a room label, a dress name or a display name, ever**: a panel that abbreviates makes two people look like one. 44×44 on every target (`Button` `size="md"` → `min-h-11`, `Button.tsx:37`), and each `Select` call site passes `className="min-h-11"` (deck F-4: `Select.tsx:28` renders ~43.6px and declares no `min-h-*`, so `cn()`'s plain join has no fight to lose).

- **Done when**: `make fe-test` + `make fe-build` green; axe **zero**; **all six focus mutations performed and restored**; `make qa-greps` byte-identical. `git show --stat`.
- **Commit**: `feat(manage): the rooms panel, its tiles, the claim and the six focus moves`

## Task 11 — `RoomsRegistryDialog` (D15, D18 / DC-9, DC-10)
`frontend/apps/manage/src/components/RoomsRegistryDialog.tsx` (**✚**), `…/__tests__/RoomsRegistryDialog.test.tsx` (**✚**)

### The failing tests first

- add / rename / **reorder via a labelled `<input type="number">` bound to `sort_order`, reachable and operable by keyboard** / activate-deactivate / delete-with-confirm
- label and `sort_order` validation, field-local 400s
- **the 409 on deleting an occupied room, naming the occupant** — the one place a registry action meets the concurrency design — **and its `details`-less variant**, which is reachable here by a path the claim's is not: D11's **ghost holder** (a soft-deleted staffer, `staff_display_name` null)
- **focus returns to the «ניהול חדרים» trigger on close, and to the `h3` when the trigger is gone** (DC-10: the dialog deleted the last room and the empty state re-rendered). `StaffSection.tsx:80-92`'s `isConnected` fallback is the shipped shape
- **AC25 — a poll tick arriving with a dirty input leaves the input's value alone**
- **DC-9 — the dense registry**: twenty rows scroll inside the dialog and every row stays reachable; the `role="status"` cue sits with the save it confirms rather than at the top of the scrolled list
- an axe pass

### The code

The owner/shift-manager `Modal`: add, rename, reorder, activate/deactivate, delete-with-confirm as a **nested `Modal`** (deck P-7 — `manage-restyle.md`'s shipped destructive pattern; native `<dialog>` gives the trap, Esc and the focus return for free; and the inline two-step's focus test is already on LOOP-STATE's `known_flaky` list, where it has parked a green PR once).

**The data contract, because this dialog lives inside a component that repaints every five seconds.** There is no registry list endpoint, so the dialog renders from the polled `rooms` prop — and `holdRef` does not help, because it consumes **one** tick on `pointerdown` and typing fires no pointer events (`FloorPanel.tsx:155-164`). A tick landing while the owner is halfway through «חדר 4» would re-render the rows from server data, and this feature's "NOT optimistic, patch from the server's row" discipline makes that a **reset** rather than a merge. So:

> `RoomsRegistryDialog` **seeds its editable rows from `rooms` ONCE at open** and does not re-read from the poll while open. It re-seeds on close, and on any successful write from **that write's own response**.

**Do NOT reach for `poll.pause()`.** The pause control's accessible name would then announce a state the user did not choose — F57's D12, the reason there is one named control per region and not a hidden second pauser.

**Reorder is a labelled `<input type="number">`, never drag-and-drop.** Stated because "reorder" left as a bare verb invites drag, whose most common implementation is a WCAG 2.1.1 keyboard failure **that axe cannot see** — the same ladder rung and the same legal reasoning D16 uses to refuse the ARIA combobox. Validated `-MAX_SORT_ORDER … MAX_SORT_ORDER` against the mirrored constant.

**DC-9's `Modal` note, stated rather than assumed**: `Modal.tsx:46` declares `w-[min(28rem,…)]` with **no `max-h` and no `overflow-y` of its own**, relying entirely on the UA's `dialog:modal { max-height; overflow: auto }`. That is the only thing standing between a twenty-row registry and unreachable content, and it is worth a comment.

**F-8, stated so it does not read as a violation**: the registry's `role="status"` is a **second** live region on the screen, defensible only because it lives inside the top layer (a live region outside an open modal dialog is not reliably announced) and because **it is not auto-updating** — nothing writes to it but her own saves. F57's D12 rule (one named control per *auto-updating* region) is intact.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| the seed-once contract | re-read from `rooms` on every render | AC25's dirty-input test **RED** |
| the `isConnected` focus fallback | always focus the trigger | the delete-the-last-room case **RED** (focus on `<body>`) |
| the number input | swap to a drag handle | the keyboard-reachability assertion **RED** — **and axe stays green, which is the point** |

- **Done when**: `make fe-test` + `make fe-build` green; axe **zero**; every mutation performed and restored; `make qa-greps` byte-identical. `git show --stat`.
- **Commit**: `feat(manage): the rooms registry dialog, its seed-once contract and its keyboard reorder`

## Task 12 — `RoomDressDialog` and `RoomHandoverDialog` (D16, D18)
`frontend/apps/manage/src/components/RoomDressDialog.tsx` (**✚**), `…/components/RoomHandoverDialog.tsx` (**✚**), `…/__tests__/RoomDressDialog.test.tsx` (**✚**), `…/__tests__/RoomHandoverDialog.test.tsx` (**✚**)

### The failing tests first

**`RoomDressDialog`** — the `Input` filter, the dress `Select`, the size `Select`, add; the **truncation line at 500** pointing at «שמלות»; a filter matching nothing; an empty catalog; a null size binding rendering the name alone. **The two focus contracts (moves 4 and 5), each mutation-checked**: close → the tile's «הוספת שמלה» control, falling back to the `h3`; **a 404 add → the dialog closes and focus lands IN THE TILE'S ALERT, not on the returned-to trigger**; a poll tick removing the assignment → dialog closes, focus to the control or the `h3`, **never `<body>`**.

⚠ **Move 4's trigger sits on a tile that has just repainted from the mutation response**, so `StaffSection`'s `isConnected` question is live and is what this test pins. **The native `<dialog>` return fires second and would otherwise win** — that is why the collision is resolved explicitly.

⚠ **Move 5 is F57's own shipped MAJOR reproduced one level deeper.** The poll is only *suppressed* while a mutation is in flight (`FloorPanel.tsx:155-164`); it keeps ticking with a dialog merely **open**, so a colleague releasing the assignment unmounts the tile and the dialog under the user's hands with focus inside. **axe sees none of it.**

**`RoomHandoverDialog`** — the colleague list is built from the `staff` array **the poll already carries** (no new endpoint): filter to `id !== assignment.staff_user_id` and **exclude cards whose `status === "occupied"`**, so the 409 `STAFF_OCCUPIED` is usually **prevented** rather than explained; the empty case renders `rooms.handoverNobody`; confirm; **the residual 409 naming her current room** (the race the exclusion cannot close); the 404 when the assignment was released underneath; **focus return, the same two contracts**. The trigger does not exist for the three floor roles, so this dialog is elevated-only by construction.

Both dialogs: an axe pass, explicitly not sufficient.

### The code

`Input` + two `Select`s + a `Button`, all from `@boutique/ui`, inside the shipped `Modal`. **Filtering is client-side** — no `?q=`, no debounce, no server-side search, no second request. **One `getFloorDresses()` per open**, never on the poll. `getFloorClients()` is fetched **on `RoomsPanel` mount and after each successful claim** — two triggers, both existing code paths, no timer and no cache. *Named ceiling: a bride who checks in after the panel mounted appears only after somebody claims a room, or on the next page load. Upgrade path if the pilot complains — refetch on the release path too, one more `.finally()`.*

**The controls are the shipped ones, named — not "a native `<select>`".** `Select` already carries this decision in its own comment (*"Native `<select>` — no custom dropdown in v1 (a11y cost not worth it)"*), requires a `label: string` (`:6`), wires `useId()` → `htmlFor` (`:19-21`), and applies `focusRing` (`:31`). Written as "a native `<select>`", a builder reasonably renders a bare element and loses the label association and the focus ring — **and axe catches the missing label but not the missing ring.** Every `Select` needs a `label`, so `rooms.dressPick` / `rooms.sizePick` / `rooms.clientPick` / `rooms.handoverPick` are **labels, not placeholders**. **Declined an ARIA combobox** — the single most commonly mis-implemented widget in the spec, on a legally binding surface. **Declined a new dependency** — the platform already ships the control.

⚠ **DC-13 / F-11, recorded and not fixed here**: `Select.label` is typed `string`, so an interpolated label cannot be bidi-isolated at all — while `Input.label` is typed `ReactNode` (`Input.tsx:14`), widened by F17 for exactly this. **F36 declines the shared-code edit** (D15's discipline this run is not to reach into `packages/ui` for a convenience) and instead puts the value **last, after an em-dash**, which is the position a Latin room label cannot visibly reorder from.

- **Done when**: `make fe-test` + `make fe-build` green; axe **zero** on both dialogs; the four focus mutations performed and restored; `make qa-greps` byte-identical. `git show --stat`.
- **Commit**: `feat(manage): the dress and handover dialogs, their pickers and their four focus contracts`

## Task 13 — Gates, the rebase and renumber, and the run report
No files.

Run the full verification below, perform the rebase and renumber, report what ran and what passed, and carry forward:

- **C1 / D5 — the migration number.** State the number the branch was **built** at, the number it **shipped** at, and the `alembic heads` output on `origin/main` that decided the second. Confirm `alembic heads` prints **one** head on the rebased branch and that C9's fast single-head guard is green in `make test`.
- **Every mutation-check, by name, with its result.** Twelve in Task 6, seven in Task 4 (four of which stay green and are pinned in Task 6), six focus mutations in Task 10, four i18n mutations in Task 8. **Say plainly which ones were RUN and which were reasoned about — the answer must be "all run".** F34 and F57 each found a real vacuous test this way.
- **Spec Risk 2 — F57's Risk 5 is discharged on THIS PR, not deferred to F37.** F57 predicted F37 would be the first feature to take a target staff id in a body; F36 is. AC23 is the assertion. Note that `_authorize` now has **four** call sites and that F58's push-assign and F37's targeting will be tempted to write a fifth.
- **Spec Risk 3 — F58 needs a migration F36 deliberately does not ship.** LOOP-STATE's F58 note says *"No new table"*, which is true and is not the same thing: F58 must `ALTER TABLE fitting_room_assignments ADD COLUMN queue_ticket_id UUID` in its own migration, with its writer, in the same PR. **F58 must not be planned against the "no migration" reading.**
- **Spec Risk 1 — the three properties F37 will assume**: the assignment id is **stable across a handover**; "which room is this staffer in right now" is **one indexed lookup** returning at most one row by construction; and an assignment **released** while an alert is open resolves its room label by joining `fitting_rooms` on `fitting_room_id` **with no `deleted_at` filter** — a room label is not personal data, so D9's no-snapshot rule does not reach it.
- **Spec Risk 5 — F20 gets a fitting-room entry with TWO disclosures**, not one: (a) purpose = floor operations, personal data = the client's name for the duration of an active assignment, retention = none of its own; (b) **`GET /manage/floor/clients` — the names and appointment times of customers checked in today, disclosed to all five roles, fetched on demand and never stored.** (b) is the wider of the two.
- **Spec Risk 4 — hand F29 the number, do not let it rediscover one.** **~30** round trips per 5 s per device on the board screen: board ~17 (unchanged) + floor ~11 → ~13. Up from F57's ~28. The cheapest lever is still the uncached per-request `tenants.by_slug`.
- **D16's parked ceiling, re-nagged**: `/manage/bookings` is owner + shift_manager, so in v1 **only those two roles can check anyone in** — a boutique whose reception role does the arrivals sees an empty client list and every claim is anonymous. **That is F34's gate, not F36's**, and the remedy is F34 widening its check-in route.
- **Deck F-1, F-4, F-6, F-7, F-8, F-9, F-10 and the new F-11** — each carries an owner and a trigger; carry them verbatim.
- **The parked question**: *should a room out of service still show a client who was in it when it was deactivated?* It does; the alternative is evicting a bride to satisfy a flag; the pilot settles the rendering.

No push, no PR from this task — the orchestrator owns review and shipping. **The shipping checklist below is the precondition list it runs.**

---

## Shipping checklist — run in this order, top to bottom

1. **`git show --stat` on every commit** confirms the lowercase pathspecs landed. `git add Backend/…` silently skips modified tracked files.
2. **`git diff main -- backend/tests/conftest.py` is EMPTY.** The harness is shipped code now (C8) — if this diff is non-empty, something was patched that should not have been.
3. **No lower-numbered migration is unmerged.** Check LOOP-STATE's `current:` block and `gh pr list`. F33 is the live one to watch.
4. `git fetch origin && cd "…/Backend" && uv run python -m alembic heads` **on a checkout of `origin/main`**. Note the number.
5. **Renumber the migration to head + 1** — three edits: the filename, the `revision` literal, the `down_revision` literal. Amend the migration commit (it is the branch tip by Task 1's instruction).
6. Rebase onto `origin/main`. Re-run `alembic heads` **on the rebased branch** and confirm a **single** head. Run `make test` and confirm C9's `test_migrations.py:44-52` is green.
7. **`bash "<scratchpad>/run-db-tests.sh"` green on the rebased branch.**
8. Full local gate (below), all six targets green.
9. **`git diff main --stat` names none of**: `frontend/apps/manage/src/lib/usePoll.ts`, `frontend/apps/manage/src/App.tsx`, `frontend/apps/manage/src/__tests__/Nav.test.tsx`, `frontend/apps/manage/vite.config.ts`, `frontend/scripts/qa-greps.sh`, `frontend/packages/ui/**`, `backend/tests/conftest.py`. **That list is AC15 + AC16 + C3 mechanised.**
10. **`git diff main -- frontend/apps/manage/src/__tests__/FloorPanel.test.tsx` shows ADDED blocks only** — no edit to an existing expectation. That is D15's acceptance rule and the instrument Risk 9 relies on.
11. `make qa-greps` output **byte-identical to the pre-Task-8 baseline** (C12).
12. Open the PR. The three gating jobs are `Backend (lint, types, tests)`, `Frontend (lint, types, build)`, `Frontend E2E (Playwright + axe)`.

---

## Verification — the full local gate sequence

```
make lint      # Backend: ruff check . && ruff format --check . && mypy app tests
               #   + Frontend: pnpm -r lint && pnpm -r typecheck
               #   + bash frontend/scripts/qa-greps.sh
make test      # Backend: pytest -m "not db" -q        (includes C9's single-head guard)
bash "<scratchpad>/run-db-tests.sh"
               # recreates f36_test on the local 16.14 cluster, exports
               # TEST_POSTGRES_SUPERUSER_URL, runs pytest -m db
               # ⚠ NO conftest patch and NO revert — the hatch is shipped (C8)
make fe-test   # Frontend: pnpm -r --if-present test
make fe-build  # Frontend: pnpm -r build
make e2e       # Frontend: pnpm -r build && playwright install --with-deps chromium && pnpm e2e
```

**Green looks like:**

- **`make lint`** — ruff clean, `ruff format --check` clean, **mypy zero errors over `app` and `tests`**, `pnpm -r lint` and `pnpm -r typecheck` clean across all four workspace packages, and `qa-greps.sh` **exit 0** printing **exactly the pre-Task-8 baseline**. Any new `FAIL` or `review` line from F36 is prose or a formatter, not necessarily a code defect — read it before changing code.
- **`make test`** — all fast tests pass. `test_floor_api.py` green with `FLOOR_ROUTES` at **thirteen**, `SPEC_ERROR_CODES` at **seven** and the `:346` key set at **six**; `test_floor_service.py` green with the widened wire-literal set and the whole authorization matrix; `test_floor_validation.py` and `test_frontend_constant_parity.py` green; **`test_staff_role_gating.py` green with `FLOOR_OPEN` at nine and the intersection classifier UNTOUCHED**; `test_spa_serving.py` green **unedited**; `test_migrations.py`'s single-head guard green; the `db`-marked modules **collected and deselected**.
  ⚠ **Two `test_config.py` failures are always false locally** — `Backend/.env` leaks `MEDIA_BUCKET`. CI is green. Do not chase them.
- **the local db suite** — the captured baseline **plus** F36's new cases in `test_migrations.py`, `test_fitting_rooms_repositories.py`, `test_floor_rooms_db.py` and `test_fitting_rooms_isolation.py`, all green. The 9 `test_media_upload_s3.py` cases need MinIO and are excluded — **expected; F36 touches no S3.**
- **`make fe-test`** — `api.test.ts`, `i18n.test.ts`, `FloorPanel.test.tsx` (**shipped blocks unedited**), `RoomsPanel.test.tsx`, `RoomsRegistryDialog.test.tsx`, `RoomDressDialog.test.tsx`, `RoomHandoverDialog.test.tsx` all green; **axe at zero violations on the panel and all three dialogs**; every mutation-check performed and restored.
- **`make fe-build`** — both apps build; no unused-import or unused-variable TS error (`TS6133` is the one this feature's refactor invites).
- **`make e2e`** — unchanged. **F36 adds no e2e**, and the reason is F34's and F57's verbatim: the console's entire e2e surface is two login-screen tests because `vite preview` runs with no backend. **F58 owns the `/manage/**` interception harness.**
- **CI additionally** — the same db suite against Testcontainers, where the pinned `indexdef` literals are **re-read off the CI server** rather than off the local one. ⚠ **A first CI red on a test bug here is budgeted**; check `continue-on-error` on the job before believing it.

---

## What a local run cannot prove

The local harness closes almost all of the gap. What is left:

| Task | The local run proves | CI-only |
|---|---|---|
| 1 | the three tables, the six indexes, the round trip, the captured literals, the RLS/GRANT loop — **all of it, against real Postgres 16.14** | that the deparsed `indexdef` literals are identical on the CI server's Postgres build. They should be — same 16.x deparser — and the assertion **re-reads** rather than transcribes, so a difference is a red test and not a silent pass |
| 6 | every forced interleave and every one of the twelve mutations, including the four that no fast test can see | the same, on the container superuser / app-role split CI builds |
| 7 | the isolation suite in full, including the vacuity mutation-check | the same |
| 10–12 | jsdom focus behaviour, which **is not a browser** — a disabled element is not blurred, which is why every focus test explicitly blurs first | **nothing.** A real browser's focus behaviour on `disabled` is proven by neither the local run nor CI. It is proven by **F58's interception harness**, which does not exist. This is deck F-9 and spec Risk 10, and it is the honest gap |
| — | — | `test_media_upload_s3.py` (MinIO; F36 touches no S3) |

**Task 5 is the milestone**: all thirteen routes, both new codes, the whole extended payload and the four tightened gates are exercised end to end with no Postgres.

---

## Task-by-task file manifest

| Task | New (**✚**) | Modified |
|---|---|---|
| 0 | — | `.planning/plans/fitting-rooms.md`, `.planning/specs/fitting-rooms.md`, `.planning/design/screens/fitting-rooms/design.md`, `.planning/design/screens/fitting-rooms/copy.md` |
| 1 | `backend/migrations/versions/00NN_fitting_rooms.py`, `backend/app/models/fitting_room.py`, `backend/app/models/fitting_room_assignment.py`, `backend/app/models/fitting_assignment_dress.py` | `backend/tests/test_migrations.py` |
| 2 | `backend/app/db/repositories/fitting_rooms.py`, `…/fitting_room_assignments.py`, `…/fitting_assignment_dresses.py`, `backend/tests/test_fitting_rooms_repositories.py` | — |
| 3 | `backend/app/floor/validation.py`, `backend/tests/test_floor_validation.py` | `backend/app/floor/schemas.py`, `backend/app/models/constants.py`, `backend/app/main.py`, `backend/tests/test_frontend_constant_parity.py`, `frontend/apps/manage/src/validation.ts` |
| 4 | — | `backend/app/floor/service.py`, `backend/app/floor/schemas.py`, `backend/tests/test_floor_service.py` |
| 5 | — | `backend/app/floor/router.py`, `backend/app/floor/service.py`, `backend/app/floor/schemas.py`, `backend/tests/test_floor_api.py`, `backend/tests/test_staff_role_gating.py` |
| 6 | `backend/tests/test_floor_rooms_db.py` | — |
| 7 | `backend/tests/test_fitting_rooms_isolation.py` | — |
| 8 | — | `frontend/apps/manage/src/api.ts`, `…/validation.ts`, `…/i18n/he.ts`, `…/i18n/ar.ts`, `…/__tests__/api.test.ts`, `…/__tests__/i18n.test.ts` |
| 9 | — | `frontend/apps/manage/src/components/FloorPanel.tsx`, `…/__tests__/FloorPanel.test.tsx` |
| 10 | `frontend/apps/manage/src/components/RoomsPanel.tsx`, `…/__tests__/RoomsPanel.test.tsx` | — |
| 11 | `frontend/apps/manage/src/components/RoomsRegistryDialog.tsx`, `…/__tests__/RoomsRegistryDialog.test.tsx` | — |
| 12 | `frontend/apps/manage/src/components/RoomDressDialog.tsx`, `…/components/RoomHandoverDialog.tsx`, `…/__tests__/RoomDressDialog.test.tsx`, `…/__tests__/RoomHandoverDialog.test.tsx` | — |
| 13 | — | — |

**Never modified, and that is an assertion, not an accident:** `frontend/apps/manage/src/lib/usePoll.ts` (AC15 — zero-line diff) · `frontend/apps/manage/src/lib/roles.ts` (`roleLabelKey` already answers) · `frontend/apps/manage/src/App.tsx` (AC15, C2) · `frontend/apps/manage/src/__tests__/Nav.test.tsx` (AC15, C2) · `frontend/apps/manage/vite.config.ts` (AC16, C3) · `backend/tests/test_spa_serving.py` (AC16) · `backend/tests/test_tenant_isolation.py` (AC11) · `backend/tests/conftest.py` (C8) · `frontend/scripts/qa-greps.sh` · `frontend/packages/ui/**` (DC-13 / F-11) · `backend/app/booking/**`, `backend/app/auth/**`, `backend/app/catalog/**` (D16 — the floor router answers its own lists rather than widening theirs).

---

## Testing plan → spec criteria

| Spec criterion | Where |
|---|---|
| **AC1** — registry CRUD for owner and shift manager; 403 for the three floor roles, proven structurally | `test_floor_api.py` (fast) + `test_staff_role_gating.py::test_the_floor_roles_reach_exactly_the_floor_routes` (fast, **classifier untouched**) |
| **AC2** — a claim answers a `Room`, writes one audit row, and the room is occupied on the very next `/manage/floor` | `test_floor_rooms_db.py` (db, **local**) + `test_floor_api.py` (fast) |
| **AC3** — **a second claim is structurally impossible** and the loser is told **who holds the room** | `test_a_second_claim_landing_in_the_gap_is_refused_and_names_the_occupant` (db) — the forced interleave, three named mutations |
| **AC4** — **one worker holds at most one room** | `test_a_worker_cannot_hold_two_rooms` (db) — *the only test that fails when the second index is dropped* |
| **AC5** — release frees the room in the same tick; a second release is a 200 that writes nothing | `test_a_released_room_is_immediately_reclaimable`, `test_a_second_release_writes_nothing` (db) |
| **AC6** — handover preserves room, `created_at` and every binding; the audit row carries the **outgoing** staffer | `test_a_handover_preserves_the_bindings_and_records_the_previous_holder` (db) — the mutation leaves **all** fast tests green |
| **AC7** — a concurrent double-add is one binding and two 200s; a removed dress can be carried back in | `test_a_concurrent_double_add_yields_one_binding`, `test_a_removed_dress_can_be_re_added` (db) |
| **AC8** — **no personal field on any of the three tables**; a swept booking **and** a swept customer both render anonymous | `test_the_assignment_stores_no_personal_column`, `test_a_deleted_booking_renders_an_anonymous_visit`, `test_a_deleted_customer_renders_an_anonymous_visit` (db) |
| **AC9** — rooms and occupancy on the **same** request; `occupied` beats `break` | `test_floor_api.py` (fast) + `test_floor_service.py` (fast) |
| **AC10** — tenant B reaches nothing of A's; every attempt is a 404 indistinguishable from missing | `test_fitting_rooms_isolation.py` (db, **app role only**) |
| **AC11** — three `enable_tenant_rls` calls; `test_every_tenant_id_table_has_forced_rls` green **with no edit** | `test_tenant_isolation.py:203` (db, **unedited**) |
| **AC12** — the three index definitions pinned byte-identical; the unique-index counts 2 / 1 / 0 | `test_migrations.py` (db) — **the tests that will still be earning their keep when F58 wants a third index** |
| **AC13** — Hebrew-first RTL on `packages/ui` tokens; **`ar[key] === he[key]` for every `rooms.*` key**; axe zero | `i18n.test.ts` (**three edits — DC-3**), `RoomsPanel.test.tsx` |
| **AC14** — a failed action → the tile's alert; a successful one → the tile's control; a deleted room → the heading. Each **non-vacuous by a named mutation** | `RoomsPanel.test.tsx` — **six moves, not three** (DC-1, DC-6) |
| **AC15** — `FloorPanel.test.tsx`'s shipped expectations unedited; `usePoll.ts` zero-line diff; `Nav.test.tsx` unchanged **(owner eleven / shift-manager nine — C2)** | `git diff`, shipping checklist steps 9 and 10 |
| **AC16** — `vite.config.ts` unchanged; `test_spa_serving.py` green with no edit **(and F53 already fixed F57's stale comment — C3)** | `test_spa_serving.py` (fast, **unedited**) + the deliberate prefix mutation in Task 5 |
| **AC17** — **a room cannot be deleted out from under a claim**; the per-room `FOR UPDATE` is the mechanism | `test_a_room_cannot_be_deleted_out_from_under_a_claim` (db) — *no other test takes two statements against one room from two transactions* |
| **AC18** — a re-claim is a 200 **whichever index reports**; a 409 whose occupant released first names **nobody** | `test_re_claiming_your_own_room_is_a_200_whichever_index_reports` (db, **reverse-index-order mutation**), `test_a_claim_whose_occupant_released_first_does_not_name_nobody` (db) |
| **AC19** — **an add racing a remove does not silently lose the add** | `test_an_add_racing_a_remove_does_not_silently_lose_the_add` (db) — *the only test `DO NOTHING` reddens* |
| **AC20** — a booking that has not checked in today cannot be bound; `/manage/floor/clients` answers three fields | `test_a_booking_that_has_not_checked_in_cannot_be_bound_to_a_room` (db) + `test_floor_api.py` (fast) |
| **AC21** — a seamstress sees **none** of the four elevated controls; an owner sees all four | `RoomsPanel.test.tsx` — *the assertion that keeps P-6's 403-is-terminal rule unreachable* |
| **AC22** — an occupied card reads «תפוסה», her room and her client, never «פנויה»; her role is muted words | `FloorPanel.test.tsx` (**NEW blocks**) + `RoomsPanel.test.tsx` |
| **AC23** — a claim naming a colleague from a non-elevated caller **403s AND never reaches the room repository** | `test_floor_service.py` (fast) — **F57's Risk 5 discharged on the PR that creates the shape** |
| **AC24** — both dialogs return focus deliberately, including on a 404 and on a poll-tick unmount — never `<body>` | `RoomDressDialog.test.tsx`, `RoomHandoverDialog.test.tsx` — each mutation-checked |
| **AC25** — a poll tick with a dirty registry input does not destroy the typed value | `RoomsRegistryDialog.test.tsx` — **and DC-4's twin for the inline client `Select`**, in `RoomsPanel.test.tsx` |

---

## What could go wrong in review

Every item here is a **recorded ruling or a verified finding**. A reviewer who raises one should find the reasoning rather than file a finding.

1. **"The claim has no lock, and F13's claim has one."** **D3, and the spec argues it at length.** F13's claim picks *the lowest free `seat_index`*, which is a **count of taken seats** — a read-then-write only a lock makes atomic (`booking/service.py:451`, and `:491` calls the index *"the backstop"*). **A fitting room has no seat to number**: the claim inserts three values the caller already holds, nothing is derived, and the statement either violates a unique index or does not. A lock would serialize every claim in the boutique and turn an immediate, informative refusal into a wait ending in the same answer.
2. **"F51 takes an advisory lock for a one-row invariant, so this should too."** **The sharper case, and it is the other way round.** `auth/staff.py:9-14` writes it out: the last-owner invariant is *"at least one"* and *"No unique index can express it: an index expresses at most one of something."* F36's invariant **is** "at most one", which is exactly and only what a unique index says — and unlike a `count(*)` subquery it is evaluated **by the index**, not against a transaction snapshot.
3. **"There IS a lock — the delete takes `FOR UPDATE`."** **D1, and it is stated as the exception rather than smuggled.** The delete is *read occupancy → write `deleted_at`*, a genuine **cross-row** invariant that no index can express. Under READ COMMITTED the unguarded form leaves a **soft-deleted room holding a live assignment**: no UI path to release it, the holder can never claim another room, and the two occupancy derivations disagree forever. It is a **row** lock on one room; two claims on the same room already resolve to one winner and claims on different rooms take different locks. AC17 and its mutation.
4. **"The 409 branch keys on a constraint name, which is fragile."** **It keys on the REQUEST first.** A re-claim by the same staffer violates **both** indexes at once and Postgres reports whichever has the lower OID, i.e. **creation order** — so an idempotence branch derived from the name would flip silently after a `REINDEX CONCURRENTLY`. The constraint name discriminates **only** between the two 409s, on a miss, and an **unrecognised** name **re-raises**. `test_re_claiming_your_own_room_is_a_200_whichever_index_reports` runs the reverse index order deliberately.
5. **"`begin_nested()` is new in this codebase."** **D3, deliberately.** A failed flush aborts the enclosing Postgres transaction, and the ruling requires the 409 to **name the occupant** — which can only be read after the conflict is known. The declined alternative (a second `tenant_session`) costs another pool checkout, another `set_config`, another BEGIN/COMMIT and a second place for the tenant id to be wrong.
6. **"The floor payload now carries a customer's name, and three shipped comments say it carries none."** **Conflict 2, and the answer has two halves.** D11's *conclusion* survives: D9's table distinguishes *the day book* from *the ≤3 people physically in fitting rooms right now*, and the board's `customer_name` still does not go behind a five-role gate. **D11's three code-comment premises are REWRITTEN in this PR** (Task 5), because each states the absolute form as a fact about the code and one of them is the stated justification for the widest role gate in the product.
7. **"F36 ships a `GET /manage/floor/clients` the spec's own D9 argues against."** **D16, and without it the feature is inert.** The three floor roles cannot reach `/manage/bookings` at all and `RoleGate` narrows only, so nothing in the console could **supply** a `booking_id`: every claim would be anonymous, E7 criterion 2 would be unmet and the privacy widening would buy nothing. It is scoped to customers **checked in today** — the people in the building, not the day book — answers three fields, and is fetched **twice at most and never on the tick**.
8. **"The dress list discloses the catalog to a seamstress."** **D16.** `storefront/service.py:78/86/90` already answers dress names and size labels **to an anonymous visitor** on the boutique's own storefront. This route discloses strictly less than the boutique already publishes to strangers: no price, no description, no media, no stock.
9. **"Handover is gated at the route while claim and release are checked in the service."** **D8, and it is the one asymmetry on the surface.** Handover's predicate depends on **nothing about the target** — a pure role predicate, which is precisely what `RoleGate` is. The other two are target-dependent (self **or** elevated) and genuinely cannot live in a gate. And a **403 is terminal for the whole panel**, so a rendered control must never reach a route its caller may not use.
10. **"`FLOOR_OPEN` grew and the walker went red."** **D10, and F57's Risk 1 predicted this exact red and forbids the fix that "works".** `test_the_floor_roles_reach_exactly_the_floor_routes` classifies on `frozenset.intersection(*role_sets)` **precisely so that F36's tightened routes do not red-fail it**; `any(...)` would report a correctly tightened route as admitting the floor roles. **Fix the route, never relax the quantifier.**
11. **"AC15 says `SectionKey` stays eleven and it is twelve."** **C2.** F53 merged after the spec was written and added `customers`. **The rule is unchanged and is the point**: `App.tsx` and `Nav.test.tsx` are untouched and the assertion is an empty `git diff`. The numbers are restated in Task 0.
12. **"Conflict 7 says `vite.config.ts` needs a one-word fix."** **C3 — F53 already made it.** The comment says «thirteen» and the alternation lists thirteen. F36 touches that file not at all, and AC16 is the assertion.
13. **"The plan changes `FloorPanel.tsx:281` and `:566`, which the spec does not mention."** **Deck F-2, verified.** `onBreak` is derived from `card.status` at three sites and D12 names one. At `:281` the consequence is that **a staffer who forgot to end a break and then claimed a room can never end it from this screen**. One line each, behaviour-identical on every payload F57 can produce, and a new test block with a named mutation — because nothing else in the suite goes red without it.
14. **"There are six focus moves, and the deck specified five."** **DC-1.** §3.3's diagram promises the sixth and none of the five owns it: without it the panel drops focus to `<body>` ~5 s after **every refused claim**, with no user action — F57's shipped MAJOR verbatim, and **the fourth time this repo would ship that bug class.** axe walked past the first three.
15. **"`i18n.test.ts` grew two assertions the spec did not ask for."** **DC-3.** The shipped digit guard is `HE_F57`-scoped and the shipped `ar` guard checks **presence** only, so `copy.md` §11's «0» rows for rules 4 and 10 were hand-counts wearing citations. Two lines, exactly the stated rules, scoped to this namespace so Risk 12 stays as it is. **And `HE_F36` must be FOLDED into `HE`, not merely declared** — the file says so about itself at `:33-37`.
16. **"axe passes, so the a11y work is done."** **D18, and it is a legal bar here (IS 5568 / WCAG 2.0 AA).** axe **cannot see a focus move that never happened** — three shipped instances in this repo — and axe has **no rule for SC 2.2.2**. F57's own success-path focus test was **VACUOUS** because jsdom does not blur a disabled element. Every focus test here blurs explicitly and carries a named mutation that was **run**.
17. **"`ON CONFLICT DO UPDATE` looks like a typo for `DO NOTHING`."** **D4, and `DO NOTHING` reintroduces a silent lost update.** T1 soft-deletes a binding (uncommitted); T2 adds the same dress, conflicts against the still-live row, does nothing, answers «נוספה»; T1 commits — **the dress is out and the staffer was told it went in.** `test_an_add_racing_a_remove_does_not_silently_lose_the_add` is the only test that reddens.
18. **"`queue_ticket_id` is missing, so a walk-in cannot be seated."** **D2 and Risk 3, deliberately.** F33's table is unmerged, F36's deps do not include F33, and a column with no table, no writer and no reader is exactly what the `ScheduledMessageKind` rule refuses. **F58 adds it, with its writer, in its own migration** — and LOOP-STATE's *"No new table"* is true and is not the same thing.
19. **"An assignment with no client renders nothing useful."** **D9, and it is the DEFAULT path, not a rare one** — every claim without a `booking_id` and every walk-in until F58. That is the *same* render path a retention-deleted ticket takes, which is why the anonymous-visit branch is exercised from day one rather than being dead code that first runs the day F20's sweep deletes something.

---

## Out of scope (unchanged from the spec)

Booking a room in advance · a `capacity` column — **two rows in the registry**, and a count is F13's lock, which the ruling forbids · auto-assignment, room optimisation, "next free room" · occupancy timers, SLA alerts, anything firing on elapsed time · per-dress verdicts, ratings, photos, fitting notes — **E9 / F41** · the walk-in queue, the dispatch action, take-next, push-assign, skip, finish — **F33 / F58** · `queue_ticket_id` — **F58** · SOS, the full-screen overlay, the 30-second escalation — **F37** · wait-time or room-utilisation analytics — pre-decided #28 · a history read of past assignments · a `fitting_rooms` label uniqueness rule, a room `notes` field, a room photo, per-room permissions · retention of assignment rows and the processing-activities record — **F20** · the public wall board — **F59** · a second poll loop, a second pause control, a `version` field — **F32 is subsumed and must never be built** · a `packages/ui` `Select.label` widening — **recorded as F-11, declined here** · any `/manage/**` e2e — **F58 owns the interception harness**.
