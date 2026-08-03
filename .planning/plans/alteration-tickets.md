# Plan: Feature 41 — Atelier alteration tickets + kanban (Epic E9, floor-management program)

**Status**: Gate 2 self-approved 2026-08-03 under Interview Q1 (F41 is not one of the six features that stop for the user) and the 2026-07-31 ATELIER ruling.

**Spec**: `.planning/specs/alteration-tickets.md` (1161 lines, D1–D19, 32 applied findings, 3 recorded rejections) · **Design deck**: `.planning/design/screens/alteration-tickets/design.md` (564 lines, P-1…P-8, F-1…F-12) · **Copy deck**: `.planning/design/screens/alteration-tickets/copy.md` (258 lines) · **Branch**: `feature/alteration-tickets` · **Worktree**: `.worktrees/alteration-tickets` · **Created**: 2026-08-03

TDD throughout. Every task states its **failing test first**, then the code that makes it pass, then the exact files, then how to verify, then the commit message, then the decisions it implements.

---

## ⚠ THE SINGLE HIGHEST-LEVERAGE CORRECTION IN THIS PLAN: the local Postgres escape hatch is SHIPPED, and there is nothing to patch and nothing to revert

The prompt, and the F33 plan that preceded this one, both describe a **temporary `LOCAL_TEST_PG_URL` escape hatch in `backend/tests/conftest.py` that must never be committed**, with a revert obligation on every commit. **That is stale.** Verified on `main`:

- `git log -S "TEST_POSTGRES_SUPERUSER_URL" -- backend/tests/conftest.py` → **`3a70600` (F19, "the deposit-flow migration, its enums, and a single-head guard")**. It is committed, it is on `main`, and `git status --short` on `backend/tests/conftest.py` is clean.
- `backend/tests/conftest.py:83-124` — `postgres_url` reads `os.environ.get("TEST_POSTGRES_SUPERUSER_URL")` and yields it **before** it ever looks for a Docker daemon. The docstring is 25 lines long and states the reason in the repo's own words: *"development on this project happens without a Docker daemon, so `pytest -m db` — which is where every RLS policy, every partial unique index and every concurrency race is actually proved — can otherwise only run on CI. That turns a routine test bug into a red CI run and a fix commit, on a feature whose whole point is a race."*

So: **no patch, no `git checkout --` in any Done-when checklist, no revert obligation, no risk of shipping a harness into `main`.** One exported environment variable.

**The setup, once, at the top of the build** (Postgres 16.14 is live via Homebrew on the `/tmp` socket, superuser `mrwen`, verified `pg_isready` → `/tmp:5432 - accepting connections`):

```
createdb -h /tmp -U mrwen f41_test
export TEST_POSTGRES_SUPERUSER_URL="postgresql+asyncpg://mrwen@127.0.0.1:5432/f41_test"
cd "/Users/mrwen/Documents/Github/Ryan + rawad + mrwen/.worktrees/alteration-tickets/Backend" \
  && uv run pytest -m db -q --ignore=tests/test_media_upload_s3.py
```

⚠ **It must point at a THROWAWAY database.** `migrated_db` (`conftest.py:125-152`) runs `command.upgrade(cfg, "head")` against exactly this URL and then `CREATE ROLE boutique_app`. `app_role_url` (`:156-161`) derives the non-superuser from it, which is the only reason the isolation suite is not vacuous. **Drop and recreate `f41_test` before each full run** — the session-scoped fixtures commit rows and the migration chain is applied in place.

⚠ **`tests/test_media_upload_s3.py` needs MinIO and stays red locally.** F41 touches no S3. Ignore that module; do not chase it.

⚠ **Two `test_config.py` failures are always false locally** — `Backend/.env` leaks `MEDIA_BUCKET`. CI is green. Do not chase them either (`.memory/local-env-breaks-config-tests.md`).

**Capture the baseline count before Task 1 and re-read it; do not hardcode a number into anything.**

---

## Path hygiene, and one trap that has already cost this repo a commit

The repo path is `"/Users/mrwen/Documents/Github/Ryan + rawad + mrwen"` — it contains **a space and a `+`**. **Quote every shell path.**

⚠ **git tracks `backend/` and `frontend/` LOWERCASE while the on-disk directories are `Backend/` and `Frontend/`.** `git add Backend/app/atelier/service.py` **silently skips modified tracked files** and exits 0. Lowercase every pathspec, and verify every commit with `git show --stat` (`.memory/git-add-uppercase-pathspec-trap.md`).

⚠ **Three sessions are live in this checkout.** `git worktree list` → `.worktrees/fitting-rooms` (F36) and `.worktrees/qr-walkin-queue` (F33), plus this one. **Do not touch either worktree.** Expect files to change under you between calls; re-check state before every mutation (`.memory/parallel-sessions-share-worktree.md`).

**`make lint` runs `frontend/scripts/qa-greps.sh`.** Read at `Frontend/scripts/qa-greps.sh:17`: `SRC="apps/storefront/src"`, so the four `check` patterns (`localStorage`, physical directions, raw hex, nav) **do not see `apps/manage`** and F41 cannot trip them. **One block does**: the unzoned-date review at `:61-66` greps `apps/storefront/src apps/manage/src packages/ui/src` for `getDay()|getDate()|toLocaleDateString|toLocaleTimeString` and for single-line `Intl.DateTimeFormat(...)` without `timeZone`. It prints `review` and **does not set `status`**, so it cannot fail the build — but it is output that must not grow. F41 adds **no formatter** (D18: `plainDate`, `jerusalemTime`, `todayJerusalem` all ship in `lib/jerusalem.ts`). **Task 9 captures the baseline before any frontend file is written and Task 14 diffs it.**

---

## What moved since the spec was written — I re-verified every citation myself

The spec says it was re-derived against `main` at `18127e7`. **`main` is now at `6de393d`, and `git diff --stat 18127e7..HEAD -- Backend frontend Frontend` is EMPTY** — the three intervening commits are `.planning/` only (F36's spec/plan/decks, F33's rewritten plan, LOOP-STATE). **So every code citation in the spec and the two decks is still against the live tree.** That is the good news and it is why this section is short. What follows is what I checked by hand, not what I assumed.

### ✅ Verified on this tree — do not re-check

| Claim | Verified |
|---|---|
| `alembic heads` on `main` | **`0017 (head)`**. `migrations/versions/` ends `0015_floor_roles` · `0016_deposit_flow` · `0017_customer_crm_fields`. **F41 builds at `0018`** — see the RULE below, and do not read that number off this document |
| `main.py` mounts **eight** `/manage` routers; F41's is the **ninth** | `:1099` `floor_router`, comment *"The SEVENTH router carrying prefix=\"/manage\" exactly"*; `:1104` `gateway_router`; `:1109` `customers_router`, comment *"The EIGHTH, after the gateway one… now with eight surfaces on one prefix"* |
| `App.tsx` `SectionKey` is **twelve** members; `NAV` is **twelve** rows | `:20-33` and `:64-109`. NAV order is `… bookings(:83?), customers(:89), board(:97), floor(:103), staff(:104), gateway(:108)` |
| The stale in-file comment is at **`:32`**, not `:31` | `grep -n "ELEVENTH member"` → **`32`**. **The design deck says `:31` and is wrong by one** (the critic's catch; `:31` is `| "gateway"`). **C11** |
| `usePoll`'s `run` is **synchronous** | `usePoll.ts:54` `run: (generation: number) => TickOutcome;` · `:46` `TickOutcome = void \| "held" \| "suppressed"` · constants `:15` `POLL_INTERVAL_MS = 5_000`, `:19` `MAX_BACKOFF_MS = 60_000`, `:23` `IDLE_STOP_MS = 600_000`, `:24` `IDLE_STOP_MINUTES` |
| Both shipped loop fixes are inside the hook | mount effect's **first** line `runningRef.current = true` at **`:218`**; cleanup's **first** line `runningRef.current = false` at **`:233`** *before* `clearTick()` at **`:234`**, with its comment at `:224` |
| `ConsoleShell` caps content at 720 px in **three** places | **`packages/ui/src/components/ConsoleShell.tsx`** — `:46` header, `:56` nav, `:84` `#console-main` (`tabIndex={-1}`). ⚠ **It is in `packages/ui`, NOT in `apps/manage`** — the deck's bare filename could send a builder looking in the wrong package |
| `Button` sizes | `Button.tsx:36` `sm: "min-h-9 …"` (36 px), `:37` `md: "min-h-11 …"` (44 px) |
| `Select` declares **no** min-height and names itself from `label` alone | `Select.tsx:5-9` (`label: string` required), `:19-21` the visible `<label htmlFor>`, `:24` `{...rest}` spread onto the `<select>`, `:27` `px-3 py-2 text-base`. **`aria-label` reaches the `<select>` through `...rest` — confirmed** |
| `Badge` has `danger` and `muted` | `Badge.tsx:4` the variant union, `:18` `danger: "border border-danger text-danger"`, `:19` `muted: "border border-border text-ink-muted"` |
| The walker classifies on the **INTERSECTION** | `test_staff_role_gating.py:279` `effective = frozenset.intersection(*role_sets) if role_sets else frozenset()`. **The spec cites `:278`; it is `:279`.** `FLOOR_ROLES` `:85`, `FLOOR_OPEN` `:102`, the test `:240`, its "never relaxed to a subset check" docstring `:248`, the `partial` accumulation `:284-285`, the three assertions `:292` / `:298` / `:301-302`. `test_gates_admit_only_known_roles` `:190`, `test_route_table_matches_the_permission_matrix` `:209`, `test_gate_admits_listed_roles` `:333`. **C1** |
| `csrf.py:48` **is** the `MUTATING_METHODS` gate | verified — the spec's rejected finding #1 is correct, and `app/floor/router.py` cites the same line |
| `i18n.test.ts` guards | `:44-47` `HE_F53`, **`:48`** the hand-assembled `HE` union (7 blocks), `:397` no-exclamation, `:401-402` `/נשלח\|תישלח\|בדרך/`, `:407-414` no-empty-`ar` (reads `ar.translation` directly — the one guard that works without the fold), `:417` `it("carries every key both features added to he.ts")` |
| `Nav.test.tsx` today | `NAV_LABELS` declared `:66`, **eleven** entries ending «צוות», «סליקה ותשלומים»; owner test name *"all eleven sections"* `:103`; shift-manager test `:110` asserting `NAV_LABELS.slice(0, 9)` at `:114`; `toHaveLength(11)` at **`:156`**; the second `.slice(0, 9)` at **`:204`**; the comment *"below a `.slice(0, 9)`"* at `:85`; the numbers-move-together comment at `:151` |
| ⚠ **The three floor roles share ONE `it.each`** | **`:122` `it.each(["reception", "sales_assistant", "seamstress"])`**, asserting `toEqual(["הצוות בקומה"])` at **`:138`**. **This is a concrete edit nothing upstream names**: F41 must remove `"seamstress"` from that list and give it its own two-row assertion. **C2** |
| `MANAGE_API` names **thirteen** segments | `vite.config.ts:18-19` `appointment-types\|auth\|availability\|bookings\|customers\|dashboard\|dresses\|floor\|gateway\|settings\|slots\|staff\|terms`; its comment at `:13-17` says *"a fourteenth segment added without touching this file fails there"* |
| The proxy test asserts **set equality** against the live route table | `test_spa_serving.py:372-403` — the regex scrape is `r'"\^/manage/\(([a-z\|-]+)\)"'` and the comparison is `set(match.group(1).split("|")) == expected` |
| ⚠ **`catalog/router.py` is gated OWNER + SHIFT_MANAGER at router level** | **`:57` `router = APIRouter(`, `:61` `Depends(require_role(StaffRole.OWNER, StaffRole.SHIFT_MANAGER))`**, `@router.get("/dresses")` at `:139`. `catalog/validation.py:90-91` `DRESS_LIST_DEFAULT_LIMIT = 24` / `DRESS_LIST_MAX_LIMIT = 100`. `apps/manage/src/api.ts:676-685` `listDresses`. **The critic's BLOCKER 1 is real. C3 resolves it** |
| `customers/router.py:76` gates the whole CRM router | owner + shift_manager — which is D7's surviving reason for the phone-based intake |
| `CustomersRepository` anchors | `:52` `by_phone`, `:72` `by_ids`, `:115` `search`, `:184` `upsert`, and the lock precondition sentence at `:188` |
| `StaffUsersRepository._refreshed` | `:195` the method, `:199` *"`_refreshed` verbatim, for the same reason"*, `:201` *"`populate_existing=True` is the whole mechanism and it is not a spare…"*, `:221` the chained option. Callers `:168`, `:192` |
| `enable_tenant_rls` is three statements and fails closed | `db/rls.py:4-19` — `ENABLE` + `FORCE` + one `CREATE POLICY` on `current_setting('app.tenant_id', true)::uuid` |
| The two shipped handlers F41 reuses | `main.py:795-799` `DomainValidationError` → 400 `VALIDATION_ERROR` with **`str(exc)` as the message**; `:801-805` `DomainNotFoundError` → 404 `NOT_FOUND_BODY`. ⚠ **The 400's message is the exception's own English string** — C5 is why the console must never render it |
| `StaffRole` has five members, `seamstress` last | `models/constants.py:9-24`; `AuditAction` at `:150` |
| `TenantContext.settings` is bound per request | `tenancy/middleware.py:46`; `_settings_result` projects only `profile`/`toggles` at `boutique/service.py:85-89`; `merge_settings` takes only those two keywords at `tenants.py:69-75` |
| `today_jerusalem(clock=None)` and its injectable-clock docstring | `storefront/validation.py:86-94` |
| Validation constants F41 reuses | `booking/validation.py:40` `MAX_CUSTOMER_NAME_LENGTH = 80`, `:45` `MAX_BOOKING_NOTES_LENGTH = 500`, `:69-70` `_CONTROL_CHARS` / `_CONTROL_CHARS_EXCEPT_WS`; `catalog/validation.py:28` `MAX_DRESS_NAME_LENGTH = 200` |
| `FloorPanel.tsx` mechanisms (617 lines) | `:39` `departingCardHoldsFocus`, `:74` `focusHeadingRef`, `:78` `reclaimFocusRef`, `:82` `mutationsRef`, `:88` `holdRef`, `:107` the capture *"the only moment both lists exist"* (its comment at `:259`), `:127` the reclaim assignment, `:149`/`:156`/`:159-160` the `run` guards, `:179-182` the pointer hold, `:196` the byte-identical-write comment, `:239-240` the reclaim effect, `:261-264` the heading rescue, `:285`/`:332`/`:337` the `mutationsRef` bracket and the `.finally()` re-arm, `:418` the cue region comment |
| `StaffSection.tsx` conventions | the two `<Select>`s at `:241` and `:375` **both set draft state and issue no request**; the destructive confirm `<Modal>` at **`:411`**, a **sibling of the `</Card>` at `:409`** — i.e. section level, not inside a row. **C6 depends on this** |
| `test_floor_api.py` exports its route table | `FLOOR_ROUTES` at `:51`, `SPEC_ERROR_CODES` at `:63`, the set-equality assertion at `:418` — the precedent `ATELIER_ROUTES` copies |
| `test_floor_db.py` forced-interleave shape | nested `async with tenant_session(factory, tenant_id)` blocks, no `asyncio.gather` anywhere in the file |
| Five isolation suites exist | `test_booking_isolation.py`, `test_catalog_isolation.py`, `test_notifications_isolation.py`, `test_payments_isolation.py`, `test_storefront_isolation.py` (+ `test_tenant_isolation.py`, the RLS walker). **F41's is the sixth** |
| `Makefile` targets | `:18` `test` (`pytest -m "not db" -q`), `:21` `test-db`, `:27` `lint`, `:33` `qa-greps`, `:44` `fe-build`, `:47` `fe-test`, `:51` `e2e` |
| F19's single-head guard is permanent and no-DB | `test_migrations.py:37-48` — `ScriptDirectory.from_config(...).get_heads()`, in the **fast** suite. This is what catches a forgotten renumber in `make test` |

### ✗ Drifted or wrong — corrected here

| Cited as | Actually | Where |
|---|---|---|
| the walker's intersection at `test_staff_role_gating.py:278` | **`:279`** (`:278` is the `for` header) | spec §What already exists, D10 |
| `App.tsx:31` for the stale ELEVENTH comment | **`:32`** | `design.md` §0 |
| a **local-only, never-committed** `LOCAL_TEST_PG_URL` conftest patch with a revert obligation | **`TEST_POSTGRES_SUPERUSER_URL`, shipped on `main` by F19 (`3a70600`)**, 25 lines of docstring, zero patch, zero revert | the prompt, and `.planning/plans/qr-walkin-queue.md`'s header |
| «axe cannot see it» claimed for target size at the **legal** bar | true, and **the legal bar is WCAG 2.0 AA, which has NO target-size criterion at all** (2.5.5 is 2.1 AAA, 2.5.8 is 2.2 AA). 44×44 here is a house rule. **C8 turns on this** | `design.md` §9.4 |
| `main`'s head is `0015` (the prompt) / `0016` (an earlier spec draft) / `0017` (the spec) | **`0017` today, and the number is not the point** — see the RULE | everywhere |

---

## THE MIGRATION-NUMBER RULE — a rule, never a number

`main`'s head is **`0017`** as this plan is written and **two other features are in flight racing for the next free number** (F33 in `.worktrees/qr-walkin-queue`, F36 in `.worktrees/fitting-rooms`). LOOP-STATE's MIGRATION CHAIN block records that the grid moved **three times in one day** and that *"not one of the four fixed numbers this file originally assigned survived contact"*. So:

1. **BUILD at `head + 1`.** Run, in Task 1, from the worktree:
   ```
   cd "/Users/mrwen/Documents/Github/Ryan + rawad + mrwen/.worktrees/alteration-tickets/Backend" && uv run python -m alembic heads
   ```
   Today that prints `0017 (head)`, so the file is `0018_alteration_tickets.py`, `revision = "0018"`, `down_revision = "0017"`. **If it prints something else, `alembic heads` is right and this document is stale.** Building at head+1 is what makes the branch **self-coherent** so its `db`-marked tests actually run — a `down_revision` naming a revision that does not exist is an outright alembic error, not a drift.
2. **Make the migration the LAST commit on the branch.** Task 1 is early, so the commit is *reordered onto the tip* at rebase — or simply amended in place, because nothing else in the branch references the revision literal. This is the one instruction that makes step 3 cost **one amend to one file**.
3. **RE-RESOLVE from `alembic heads` on `origin/main` IMMEDIATELY BEFORE the rebase that precedes the push.** Three edits: the filename, the `revision` literal, the `down_revision` literal.
4. **Verify `alembic heads` prints exactly ONE head** on the rebased branch. Two files claiming one revision id is a multiple-heads error **git cannot see** (the filenames differ) and that reads as a mystery far from its cause — `0017`'s own header comment says so. F19's fast no-DB guard (`test_migrations.py:37-48`) fails in `make test` if you forget.
5. **Do not OPEN the PR while a lower-numbered migration is still unmerged.** CI tests the merge result.

Declined: coordinating with the other two sessions. Three things make this safe without it, and LOOP-STATE names them — a wrong `down_revision` errors outright rather than drifting; the single-head guard fails locally; and each branch builds at head+1 so it is self-coherent.

**Every assertion in `test_migrations.py` keys to "after this feature's migration", never to a revision literal.**

---

## Twelve corrections — the critic's REVISE, resolved, and amended into the spec and the decks in Task 0

The spec is binding and D1–D19 are **not** re-litigated. These are the places where the critic's verdict, or my own re-verification, disagrees with the documents. **Every resolution is the smaller edit.**

### C1 — the walker restructure, and the exact line the table must be written against

D10's `NON_ELEVATED_REACH` is correct as specified (`ATELIER_DELETE` split out of the seamstress row, anti-vacuity over the full union). Two mechanical corrections only: the intersection is at **`:279`**, and **assertion 2's `partial` list (`:284-285`, asserted `:298`) must be DELETED, not adapted** — its model is "the three floor roles move as a block", which F41 makes false, and its intent is absorbed by the per-role set equality. Deleting it while adding three set equalities is a strictly stronger test, and the docstring at `:248` must be rewritten to say so in the same edit, or the next reader meets a "never relax this" comment above a test that was just relaxed-looking.

### C2 — `Nav.test.tsx:122`'s shared `it.each` must be SPLIT, and nothing upstream says so

`it.each(["reception", "sales_assistant", "seamstress"])` asserts `toEqual(["הצוות בקומה"])` at `:138`. After F41 a seamstress sees **two** rows. **Resolution:** remove `"seamstress"` from the `it.each` list (leaving reception and sales_assistant at one row, unchanged) and add a separate `it("shows a seamstress the floor panel and the atelier, in that order")` asserting `toEqual(["הצוות בקומה", "תפירה"])`. **The order in that assertion is the whole test**: it is what fails if the `NAV` row was inserted before `floor` instead of after, which would also move `reachable[0]?.key` and land a seamstress on the atelier instead of the floor.

### C3 — BLOCKER: the intake dialog's dress `Select` has no data source and 403s for a seamstress. **The picker is CUT.**

The deck's §7.1 specifies "a `Select` of the tenant's live dresses". Verified: `AtelierBoardResponse` carries no dresses; the only source is `api.listDresses` → `GET /manage/dresses`, whose router is gated **`require_role(OWNER, SHIFT_MANAGER)`** (`catalog/router.py:57-61`) while F41's intake admits a **seamstress**; and it is paginated at `DRESS_LIST_DEFAULT_LIMIT = 24` (`catalog/validation.py:90`).

**Resolution — climb the ladder to rung 1: the picker does not need to exist in F41.** `dress_id`'s stated purpose is *"kept alongside so the image resolves at read time"* (`0008_bookings.py:52-57`, quoted by D1) — and **F41's card renders no image at all**: the deck's §2.1 anatomy is name row, dress line, due line, effort+assignee, notes, controls. So on this surface `dress_id` has **no reader**. Buying it costs a fetch, a role branch, a 403 that would be terminal through `poll.fail`, a silent 24-row ceiling, a loading state, a failure state and a test — for a column nothing on this screen displays.

**So the console ships the free-text `dress_name` `Input` alone, unconditionally, for all three roles, and sends `dress_id: null` on every request.** Consequences, all of them subtractions:

- `atelier.form.dress` and `atelier.form.dressNone` are **deleted** from the copy deck (two keys). `atelier.form.dressName` loses its "revealed only by «לא מהקטלוג»" condition and is always visible.
- No `api.listDresses` call, no `poll.fail` question, no ceiling, no dialog loading/failure branch, no role branch in the dialog.
- **The SERVER path is KEPT unchanged** — `dress_id` stays on `CreateTicketRequest`/`UpdateTicketRequest`, `AtelierService` keeps the `DressesRepository` name-copy and its 404, and both keep their tests. It is already specified and already tested, **F43 sends it**, and deleting it would remove a D13 error row and an acceptance criterion on the strength of a finding about a *client control*. Recorded in the spec as: *in F41 the server's `dress_id` path has no console caller; its callers are F43 and a later elevated prefill.*
- `alteration_tickets.dress_id` stays a column in the migration with **no writer reachable from this console**, and the migration comment says exactly that — F33's `skip_count` precedent, verbatim reasoning: one nullable column in the migration that creates the table is cheaper than a migration in the feature that was scoped not to have one.

### C4 — there is a SIXTH focus move, and the fix is to make rule #5 UNCONDITIONAL, which is less code than the deck's version

The deck's §3.3 rule #5 triggers on *"the focused card's incoming `stage` differs"*. The critic's case: a seamstress tabbed onto «לקחת» on an unassigned card; a colleague claims it; the next tick renders that card **with zero controls for her** (§2.3 — a seamstress sees no controls on a colleague's ticket). The stage did not change, so #5 does not fire; no alert, so #3 does not fire; the ticket is still in the payload, so #4 does not fire. Focus drops to `<body>` with no user action.

**Resolution — one mechanism replaces rules #1, #1b, #4, #5 and the sixth case, and it needs no predicate at all:**

- Every per-card control carries **`data-control="advance"|"skip"|"skipCommit"|"assign"|"assignCommit"|"claim"|"release"|"undo"|"edit"|"delete"|"alert"`**, and every `<li>` carries `data-ticket-id` (already required by the deck's §8).
- **Before applying an incoming payload** — the `FloorPanel.tsx:107` moment, *"the only moment both lists exist"* — if `document.activeElement.closest("[data-ticket-id]")` matches, record `{ ticketId, control, columnStage }` into a ref. **Unconditionally. No comparison against the incoming list.**
- **After paint**, in an effect: if and only if `document.activeElement === document.body` — i.e. the repaint dropped focus, rather than the user moving it — restore, in this order: **(1)** the same `data-control` on the same `data-ticket-id`; **(2)** any control on that ticket, if it still renders; **(3)** the `<h3 tabIndex={-1}>` of the ticket's **new** column, if the ticket is still on the board; **(4)** the `<h3>` of the column it was recorded in, if it is gone entirely.

The `document.body` guard is what makes it safe to run on every tick: if focus is still on something real, it does nothing. The `data-control` key is what answers the critic's item 3 — she returns to **the control she was actually on**, not always to «לשלב הבא». The four-step fallback is what answers item 3's first half (present in the new column but carrying no «לשלב הבא» — it landed on `delivered`, or her advance right went away with the assign).

**Mutation, named:** delete the capture line. Every one of the five focus tests in Task 13 that goes through this path must go red.

This **replaces** the deck's rule #5 and subsumes #1b and #4; the mutation-driven moves (#1 success, #2 failure) stay as they are, because those are keyed on a mutation's own response and not on a repaint.

### C5 — a reachable 400 renders `main.py`'s ENGLISH body in a Hebrew console. One key closes it, and every future hole with it.

D13's 400 row includes *"non-seamstress assignee"*, and it is reachable from this surface: the assign `Select` renders only `assignable: true` rows, but F51's shipped staff CRUD can re-role or retire a seamstress between the tick and the tap. The 400 handler (`main.py:795-799`) returns **`str(exc)`** — an English developer string. The copy deck declares three card errors and none for 400.

**Resolution — one key, and a `default:` branch rather than a per-code string.** On any card mutation the console maps `TICKET_STAGE_CONFLICT` → `atelier.error.stageConflict`, `TICKET_ALREADY_ASSIGNED` → `atelier.error.alreadyAssigned`, `NOT_FOUND` → `atelier.error.notFound`, and **everything else** → **`atelier.error.rejected`** «הפעולה נדחתה. הלוח יתעדכן בעדכון הבא.» That is structurally stronger than a `notAssignable` string: it guarantees **no English body can ever reach this console from any code F41 or a later feature adds**, and for the assign-400 case it is also the correct instruction — the next tick removes the person from the picker. A per-code string would leave the next new code uncovered.

**Named test:** a mutation rejected with an unmapped code renders `atelier.error.rejected` and never the response's `message`. **Mutation:** replace the `default:` with `errorMessage(error)` → red.

### C6 — where the two `Modal`s mount, and what a tick does to an open dialog

**Resolution:** both `Modal`s mount at **section level**, siblings of the column grid — `StaffSection.tsx:411` is the shipped instance (a sibling of the `</Card>` at `:409`, not inside a row). Their `open` state and their draft live in `AtelierSection`'s own state keyed by `ticketId`. Because they are not children of any `<li>`, **no repaint can unmount them**, and **ticks continue behind an open dialog** — which is correct: the board behind it must still be current when she closes it. If the ticket vanishes from the payload while the delete confirm is open, the confirm stays open and its confirm answers 404 into the dialog's own alert. `usePoll`'s "no tick while a mutation is in flight" is about `mutationsRef`, not about dialogs, and this states the difference rather than leaving it inferred.

### C7 — a terminal transition while a dialog is open would silently discard typed work

§5's A-401/A-403 replace the board and clear the cards. With the intake `Modal` open — bride's name typed, date chosen, note written — a 12-hour session expiring on a tick would unmount the dialog and throw all of it away, with no sentence and no focus destination.

**Resolution — the terminal is DEFERRED while a dialog is open.** One boolean in one conditional: the render is `terminal && !dialogOpen ? <TerminalPanel/> : <Board/>`. The loop has already stopped (that is `usePoll`'s doing and is not deferred). Her next submit answers 401/403 and lands in the dialog's own server-error alert carrying the terminal copy; dismissing the dialog then reveals the terminal panel, and focus goes to it (`role="alert" tabIndex={-1}` — the native `<dialog>`'s focus return would otherwise aim at a trigger that no longer exists). **Named test + mutation:** drop the `!dialogOpen` guard → the open-dialog-survives-a-401 test goes red.

### C8 — "44×44 on every target" is extended to the board and RECORDED AS A DEPARTURE in the dialog

D17 asserts 44×44 as the floor for **every** control on the surface; the deck applies `min-h-11` to two board `<Select>`s and leaves the dialog's `Input`s, `DateField`, `TextArea` and effort `Select` at the shipped ~42 px.

**Resolution — record the departure, with three reasons, rather than either extending it silently or leaving it silent:**

1. **The legal bar is WCAG 2.0 AA (pre-decided #38), which has NO target-size success criterion at all.** 2.5.5 is 2.1 AAA; 2.5.8 is 2.2 AA. So 44×44 here is a house rule, not a conformance item — which is exactly why it may be traded deliberately and may not be traded silently.
2. **`manage-restyle.md` bars overriding a `packages/ui` component's own utility from the call site** (`cn()` is a plain join and the consumer loses). Every shipped console dialog runs at the component's height.
3. **D17's floor is written about the BOARD's controls** — the ones under a thumb in a five-column scan on a staff phone. A dialog is a focused, one-thing-at-a-time surface reached deliberately.

So: **the board's two `<Select>`s carry `min-h-11`; every board `Button` is `size="md"`; `size="sm"` is barred anywhere in this tree; the dialog's fields keep the shipped component heights.** Asserted as a rendering check (`toHaveClass("min-h-11")` on the board's selects; a tree-wide assertion that no element carries `min-h-9`).

### C9 — `<Card className="space-y-1">` vs §2.1's `--space-3` control separation

**Resolution:** the control stack gets its own named container inside the `Card`: `<div className="mt-3 space-y-2">`. `mt-3` **is** `--space-3` (12 px), so §2.1's claim becomes true as written, and `space-y-2` between control rows keeps the stack from reading as one block. No divider, no second `Card`.

### C10 — the rail's history cost, priced

Five plain `<a href="#…">` push a history entry per activation, so Back walks column jumps before leaving the console.

**Resolution — accepted, with the reason stated.** `replaceState` would need an `onClick`, a `preventDefault`, a manual `focus()` and a manual scroll — which is precisely the JavaScript §1.1's whole argument is about not writing, and it would break middle-click and open-in-new-tab. And the cost is smaller than it looks: **section switching in this console is `useState`, not history** (`App.tsx:120`), so Back has never been a section-level affordance here — it leaves the console. What changes is that it now leaves after N column jumps. One line in the deck, recorded, not fixed.

### C11 — the two citation slips

(a) `design.md` §0 puts the stale `SectionKey` comment at `App.tsx:31`; it is at **`:32`**. (b) §8's contrast ledger lists "focus ring 5.57" beside figures all stated *on paper*; `tokens.md:34` measures 5.57 **on cream**. Both are one-word edits in Task 0.

### C12 — §4.1's delete row is wrong as written and would be built literally

*"A colleague deleted a ticket | its card leaves — **unless it holds focus** (§3.3 #5)"* — nothing retains a card because it holds focus, and under C4 nothing needs to. **Resolution:** reword to *"its card leaves; if it held focus, the capture-and-restore lands focus on that column's `<h3>`"*.

### Also folded in from the decks, because they are BLOCKER-class and the spec does not carry them

- **The five-column board does not fit the console** (`design.md` **F-2**): `ConsoleShell` caps content at 720 px in three places → 128 px per column, and a `Button size="md"` reading «לשלב הבא» is wider than the column containing it. The shipped answer is **one column at 375, two-up at ≥768 and 1440, plus the five-chip stage rail**. Lifting the cap is a console relayout owned by F42 and is **not** in F41.
- **`atelier.error.notFound`** — D13 lists the 404's status and code; D18 declares no string.
- **The four copy corrections to D18** (`cue.advanced` / `cue.undone` grammar, `cue.assigned`'s single name, `assignLabel` «תופרת» vs `assignCommit` «שיוך», the two missing `*Aria` keys) and **`atelier.loadFailed`**, all already resolved in `copy.md` and none of them in the spec.
- **The column heading interpolates `{{total}}`, never `{{count}}`** (i18next plural trigger, 10× per paint) and **carries no noun** (Hebrew dual would need four plural suffixes × two bundles).

**Key arithmetic after C3 and C5:** `copy.md`'s 96 keys become **95** — minus `atelier.form.dress`, minus `atelier.form.dressNone`, minus `atelier.form.error.dueDateHorizon` (deleted: it is a **server** 400 and no client constant may mirror a server bound — `test_frontend_constant_parity.py` exists to prevent exactly that class, and the deck's own §Frontend changes says *"no client constant mirrors a server bound"*), plus `atelier.error.rejected`, plus `atelier.form.error.server` (the dialog-level alert §7.3 specifies and no deck declares — it is where the horizon 400 and the `dress_id` 404 actually land).

---

## Scope fence — read this before every task

**F41 ships the ticket row, the five timestamps, the effort estimate, the assignment and the board that renders them.** It performs no arithmetic over `effort_minutes` at all.

| Not in F41 | Whose |
|---|---|
| Capacity, `weekly_capacity_hours`, load bars, overload flags, remaining-capacity sorting on the assign picker, the seamstress directory | **F42** |
| Split load (`parent_ticket_id`), expedite (`expedited_at` + actor), and their two `AuditAction` members | **F42's own migration** |
| The effort-band **settings editor** — the `merge_settings` third keyword, the `SettingsResult` field, the `UpdateSettingsRequest` block and its validator | **F42** (four edits, Risk 4) |
| Lifting `ConsoleShell`'s 720 px cap / a `contentWidth` prop | **F42** (`design.md` **F-2**) |
| An index on `assigned_staff_user_id`, `customer_id`, or any of the five stamps | **F42 / F53 / F44** — the feature that measures the query buys the index |
| Fitting appointments, `bookings.alteration_ticket_id`, the staff-booked appointment type | **F43** |
| The shop-floor board, throughput analytics, median time-in-state | **F44** |
| A `status` enum, an event table, per-transition reason codes | **#39 and the ATELIER ruling — declined outright** |
| A second `wedding_date` column | **the ATELIER ruling — `due_date` subsumes it** |
| The F28 rental-reservation prefill of `due_date` | **later; F28 is not built and is not a dep** |
| Pricing, invoicing, deposits, any ILS amount | **deliberately — the E9 brief and Interview Q1's money fence** |
| Photo attachments; measurements as structured columns | **deliberately — the E9 brief** |
| Retention enforcement, the PII scrub, the 7-year clock | **F20/F21.** F41 *flags* the record class (Risk 8) |
| Reception and sales_assistant access to the atelier | **one gate literal and one `NAV` row if the pilot asks** |
| A multi-stage undo; restoring a deleted ticket | **D4's ceiling, named (Risk 6)** |
| Any notification, SMS, scheduled message or `comms_templates.py` touch | **none, and `i18n.test.ts:401-402` is what keeps a copy edit from claiming otherwise** |
| A dress **picker** in the console; any `api.listDresses` call | **C3 — F43, or a later elevated prefill** |
| A shared `poll.*` i18n namespace | **F37 or F59, as a standalone i18n PR (`design.md` F-9)** |
| A `/manage/**` e2e interception harness | **F58** |
| A second poll loop, on this screen or any other | **D12/D15 — F42/F43/F44 extend this payload** |

If a task's diff grows an arithmetic over `effort_minutes`, a `staff_users` column, a second fetch on the atelier screen, or a `packages/ui` edit, it has left F41.

---

# Part 0

## Task 0 — This plan, and the twelve corrections amended into the spec and the two decks
`.planning/plans/alteration-tickets.md` (this file), `.planning/specs/alteration-tickets.md`, `.planning/design/screens/alteration-tickets/design.md`, `.planning/design/screens/alteration-tickets/copy.md`

No test, no code. Make the three source documents the binding statement of every resolution above.

**Spec:**
- **Header** — record that `main` at `6de393d` is code-identical to `18127e7`, so every citation still holds; and that D14's `0017` is today's head and not a number to build against.
- **D3 / D9 / D10** — the intersection is `test_staff_role_gating.py:279`; **assertion 2's `partial` block is DELETED and the `:248` docstring rewritten in the same edit** (C1).
- **D6 / §API surface / §Frontend changes / §Every state of every surface** — C3: the console ships the free-text `dress_name` alone and sends `dress_id: null`; the server path is unchanged and its callers are F43 and a later prefill; `dress_id` is a column with no console writer, and the migration comment says so.
- **D13** — add the client-side mapping rule and `atelier.error.rejected` as the `default:` (C5); note that the 400 handler returns `str(exc)` in English.
- **D16** — replace the four-destination focus table with C4's single unconditional capture-and-restore, its `data-control` key, its `document.body` guard and its four-step fallback; carry the named mutation.
- **D15 / §Every state of every surface** — C6 (both `Modal`s at section level; ticks continue behind a dialog) and C7 (the terminal defers while a dialog is open, and where focus goes when it is dismissed).
- **D17** — C8's recorded departure, with the WCAG 2.0-has-no-target-size-criterion reason stated in those words.
- **D18** — the key arithmetic: `form.dress`, `form.dressNone` and `form.error.dueDateHorizon` deleted; `error.rejected`, `error.notFound`, `form.error.server`, `loadFailed`, `railAria`, `stageCount`, `skipCommitAria`, `assignCommitAria` added; `assignLabel` = «תופרת»; `cue.advanced` / `cue.undone` / `cue.assigned` replaced by the copy deck's versions; `{{total}}` and no noun on the heading.
- **§Frontend changes** — add the `Nav.test.tsx:122` `it.each` split (C2) and the two-up ≥768 layout + stage rail (F-2).
- **§Testing** — replace the "no Docker locally, per the run's standing constraint" clause with the shipped `TEST_POSTGRES_SUPERUSER_URL` instruction; every `db`-marked task in this plan runs locally before it commits.

**`design.md`:** `App.tsx:31` → **`:32`**; "focus ring 5.57" → "5.57 **on cream**"; §3.3's five-row table → C4's one rule; §4.1's delete row reworded (C12); §7.1's dress `Select` row deleted and `dress_name` made unconditional (C3); §7.3 gains the dialog-level `form.error.server` row and the terminal-defer row (C7); §7.4 and §7.3 state the section-level mount (C6); §8's `<Card className="space-y-1">` row gains the `mt-3 space-y-2` control container (C9); §9.4's 44×44 bullet gains C8's departure; §1.1 gains C10's history line.

**`copy.md`:** the three deletions and three additions above; the header's «96 keys invented» → **95**; §9's register table re-run over the new set.

- **Done when**: `grep -n "0018\|down_revision" .planning/specs/alteration-tickets.md` returns no build-against number; `grep -rn "listDresses\|form.dressNone\|dueDateHorizon" .planning/specs .planning/design/screens/alteration-tickets` returns only the recorded-deletion prose; `grep -c "atelier\." .planning/design/screens/alteration-tickets/copy.md` reflects 95 keys.
- **Commit**: `docs(planning): F41 implementation plan and twelve corrections to the spec and decks — Gate 2 self-approved`
- **Implements**: C1–C12, `design.md` F-1/F-2/F-5/F-10/F-11/F-12.

---

# Part I — the backend

## Task 1 — The migration **and** the ORM model, as one atomic change (D1, D14)
`backend/migrations/versions/00NN_alteration_tickets.py` (**✚**), `backend/app/models/alteration_ticket.py` (**✚**), `backend/tests/test_migrations.py`

**The two halves ship together and this is not a preference.** No model↔migration parity test exists anywhere in `Backend/tests/`, so without `app/models/alteration_ticket.py` every backend line in Tasks 2–6 is an `AttributeError` or an import failure.

**Resolve the revision id at build time. Do not read it off this document.** Run `uv run python -m alembic heads` in the worktree's `Backend/` and take the next integer. Today: `0018_alteration_tickets.py`, `revision = "0018"`, `down_revision = "0017"`. **Reorder this commit onto the branch tip at rebase** so the renumber costs one amend.

### The failing tests first — `db`-marked, appended to `test_migrations.py`, run locally

Follow the file's own convention: **the round-trip test goes LAST in the file**, owns no fixtures, and wraps the downgrade in `try/finally: command.upgrade(cfg, "head")` — these tests mutate the live session-scoped schema and leaving it down fails unrelated modules with `UndefinedTable`.

1. `test_the_alteration_tickets_migration_creates_the_table` — the table exists; **all five stamps are `timestamp with time zone` and `is_nullable = 'YES'`, `intake_at` included**; `due_date` is `date NOT NULL`; `effort_minutes` is `integer NOT NULL`; `customer_id` is `uuid NOT NULL`; read from `information_schema.columns`.
2. **`test_the_alteration_tickets_definitions_are_pinned`** — the highest-value test in the feature, because what it guards is a *future* edit. **CAPTURE the literals by running `pg_get_constraintdef(oid)` and `pg_indexes.indexdef` against the server; never transcribe them from this document.** Postgres deparses `IN (…)` into `= ANY (ARRAY[…])`, adds `::text` casts, parenthesises predicates and schema-qualifies. F34's shipped note records that transcribing *"would have pinned nothing and reddened CI"*. Asserted **after this feature's migration** (at `head`), never after a revision literal. Two rows: the `effort_minutes` CHECK, and `idx_alteration_tickets_tenant_due`'s `indexdef` — **the row that fails loudly if someone re-adds `UNIQUE`**.
3. `test_alteration_tickets_has_no_unique_index_but_the_primary_key` — `SELECT count(*) FROM pg_index WHERE indrelid = 'alteration_tickets'::regclass AND indisunique AND NOT indisprimary` is **0** (D1: two tickets for one bride on one dress is legitimate).
4. **A CHECK probed on four axes**, the `test_migrations.py:73-189` shape: superuser INSERT positive and negative on `effort_minutes` (1440 ok, 1441 refused, 0 refused); app-role UPDATE positive, negative, **and a read-back proving the refusal changed nothing**; and `ADD CONSTRAINT` against a populated table.
5. `test_migration_00NN_round_trips` — upgrade applies and the end state asserts; `downgrade` one revision and the **reverse** asserts (the table is gone); `upgrade` to head and re-assert. Probing both directions is `0013`'s docstring rule: a silently no-op downgrade stays green while shipping an unrollbackable migration. **Last in the file, in `try/finally`.**

**`test_every_tenant_id_table_has_forced_rls` (`test_tenant_isolation.py:203-229`) needs NO edit** — it walks `pg_class` for any `tenant_id` column without `relforcerowsecurity` and picks the new table up for free. Forgetting `enable_tenant_rls` therefore fails a **different file's** test, a long way from F41.

### The code

`00NN_alteration_tickets.py`, the `0008_bookings.py` idiom verbatim: raw `op.execute` DDL, the module-level `_STANDARD` block, a local `_updated_at_trigger` helper, D1's `CREATE TABLE` with its inline CHECK, **the one NON-unique partial index** with a comment stating what its predicate buys and **why there is no unique index on this table**, then the trailing block:

```python
op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON alteration_tickets TO app_user")
for statement in enable_tenant_rls("alteration_tickets"):
    op.execute(statement)
op.execute(_updated_at_trigger("alteration_tickets"))
```

No `REVOKE`-first (that is `terms_versions`' append-only shape, `0005:122-126`); no column-level GRANT (`0003_auth.py:83-84`'s table-level precedent); no FK and no `ON DELETE` (house rule); **no `NOT NULL` on any of the five stamps** (D2).

⚠ **`dress_id` ships as a column with no writer reachable from this console (C3), and the migration comment says so in those words** — F33's `skip_count` precedent: one nullable column in the migration that creates the table is cheaper than a migration in the feature that was scoped not to have one, and F43 is the caller.

`downgrade()` is `DROP TABLE IF EXISTS alteration_tickets` and nothing else (`0008:113-115`). **F41 touches no existing table, so it has nothing to un-touch.**

`app/models/alteration_ticket.py` declares **every** column explicitly as `mapped_column` on `AlterationTicket(StandardColumns, Base)` (`app/models/base.py:13`), the `models/booking.py` shape.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| `enable_tenant_rls("alteration_tickets")` | delete the loop | `test_every_tenant_id_table_has_forced_rls` **RED** (in `test_tenant_isolation.py`, a different file) |
| the `effort_minutes` CHECK | widen it to allow 0 | test 2 **RED** on a byte-identical comparison, test 4 **RED** on the negative INSERT |
| the partial index's `WHERE deleted_at IS NULL` | drop the predicate | test 2 **RED** on `indexdef` |
| `downgrade` | make it `pass` | test 5 **RED** on the reverse assertion |
| the `GRANT` | delete it | nothing fails **until Task 8**, as `permission denied` — note it in the migration comment rather than assuming a test covers it |

- **Done when**: the local db suite is green (baseline + these cases); `make lint` clean; `make test` green with the db module collected-and-deselected; `git show --stat` confirms the **lowercase** pathspecs landed.
- **Commit**: `feat(atelier): alteration_tickets — the ticket table, its ORM model and its pinned definitions`
- **Implements**: D1, D2 (the nullable-stamp DDL), D14.

---

## Task 2 — The pure core: the two enums, `stage_of`, the predicate builder and the band resolver (D2, D8)
`backend/app/models/constants.py`, `backend/app/atelier/__init__.py` (**✚**), `backend/app/atelier/stages.py` (**✚**), `backend/app/atelier/validation.py` (**✚**), `backend/tests/test_atelier_stages.py` (**✚**), `backend/tests/test_atelier_bands.py` (**✚**)

**Where these live, decided here because the spec names four package files and this is a fifth.** `TicketStage` and `EffortBand` go in **`app/models/constants.py`**, beside `StaffRole` (`:9`), `StaffCardStatus` (`:26`) and `AuditAction` (`:150`) — `StaffCardStatus` is the shipped precedent for a **derived, DB-unpinned wire enum**, and `constants.py` is being edited in Task 4 for the six `AuditAction` members anyway. The pure functions (`STAGE_COLUMNS`, `stage_of`, `later_columns`, `DEFAULT_EFFORT_BANDS`, `effort_bands`) go in **`app/atelier/stages.py`**, because the **repository** needs the predicate builder and the **service** needs the discriminator, and putting them in either creates a backwards import edge.

### The failing tests first — fast, pure, no Postgres, no fakes

**`test_atelier_stages.py`:**
- **`stage_of` over all 32 combinations of the five nullable stamps** — this is what makes D2's *"rightmost, not first-NULL"* rule a fact rather than a comment. Include the two the rule exists for: `{intake_at, ready_at}` set with `in_progress_at` and `qc_at` NULL reads **`ready`**; all five NULL reads **`intake`** (the total-function floor).
- **The declaration order is the total order.** Assert `list(TicketStage) == [INTAKE, IN_PROGRESS, QC, READY, DELIVERED]` and that `STAGE_COLUMNS` has exactly five keys, one per member — so a member inserted in the middle is a red test rather than a silent semantic change.
- **`later_columns(target)` for each of the five targets** — `intake` → the four later columns; `delivered` → the empty tuple. This is D3's whole concurrency mechanism and it is unit-testable with no database.

**`test_atelier_bands.py`** — resolution with **no `atelier` key** (five platform defaults), a **partial** mapping (the named band tuned, the other four defaulted — **per band**, never discarding the whole mapping), a **negative** value, a **string**, a value **over the CHECK's 1440 bound**, and `0`. Each falls back to that band's platform default. **Every tenant always has exactly five bands** — which is what lets the intake form render with no empty branch and what lets D1's `NOT NULL` hold.

### The code

`app/models/constants.py` — `TicketStage(StrEnum)` and `EffortBand(StrEnum)` with D2's and D8's comments carried verbatim, including *"NOT pinned by the DB and deliberately not"* and *"DECLARATION ORDER IS THE TOTAL ORDER"*.

`app/atelier/stages.py` — `STAGE_COLUMNS`, `stage_of(row)` (D2's body, its docstring included), `later_columns(target)`, `DEFAULT_EFFORT_BANDS`, `effort_bands(settings)` and `_positive_int`.

`app/atelier/validation.py` — the bounds and the errors. **Reuse rather than restate:** `MAX_CUSTOMER_NAME_LENGTH` (`booking/validation.py:40`), `MAX_BOOKING_NOTES_LENGTH`'s value as `MAX_TICKET_NOTES_LENGTH = 500`, `MAX_DRESS_NAME_LENGTH` (`catalog/validation.py:28`) as `MAX_DRESS_LABEL_LENGTH = 200`, `normalize_israeli_mobile` (`notifications/validation.py:31`), and the **booking path's two control-character regexes** (`booking/validation.py:69-70`) — `_CONTROL_CHARS` for every label, `_CONTROL_CHARS_EXCEPT_WS` for `notes`. New: `MAX_DRESS_SIZE_LENGTH = 40`, `MAX_DUE_DATE_HORIZON_DAYS = 730`. Plus `TicketStageConflictError` and `TicketAlreadyAssignedError`.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| `stage_of`'s rightmost walk | rewrite it to return the **first** stage whose column is NULL | the `{intake, ready}` case **RED** — the one row the whole rule exists for |
| `stage_of`'s `INTAKE` floor | drop the initialiser and return `None` when nothing is stamped | the all-NULL case **RED** |
| `effort_bands`' per-band fallback | discard the whole stored mapping when any value is bad | the partial-mapping case **RED** |
| `_positive_int`'s upper bound | drop the `<= 1440` clause | the over-bound case **RED** — and note that without it a hand-edited JSONB blob writes a row the CHECK then refuses at INSERT |

- **Done when**: `make lint` + `make test` green locally.
- **Commit**: `feat(atelier): the five-stage derivation, its predicate builder and the tenant effort-band resolver`
- **Implements**: D2, D8.

---

## Task 3 — `AlterationTicketsRepository`: the conditional writes, one `_refreshed`, and the board read (D3, D4, D9, D12)
`backend/app/db/repositories/alteration_tickets.py` (**✚**), `backend/tests/test_atelier_db.py` (**✚**)

### The failing tests first — `db`-marked, run locally, single-writer only (the four races are Task 7)

- `insert`; `by_id(session, tenant_id, ticket_id)` — **the signature carries `tenant_id` explicitly and puts it in the `WHERE` beside `deleted_at IS NULL`**, matching `CustomersRepository.by_id`'s defence-in-depth. Cases: present / absent / soft-deleted / **present but owned by another tenant → `None`**.
- **`advance_stage`** — the guarded `UPDATE … SET <target>_at = :at WHERE tenant_id AND id AND deleted_at IS NULL AND <target>_at IS NULL AND <every later column> IS NULL RETURNING id`, for each of the five targets. Rows written; the stamp is the injected clock's instant; a second advance to the same stage writes **zero rows and keeps the first timestamp**.
- **`undo_stage`** — `SET <stage>_at = NULL WHERE … AND <stage>_at IS NOT NULL AND <every later column> IS NULL RETURNING id`. The cleared column; the double-tap writing zero rows.
- **`claim` / `release`** — `WHERE assigned_staff_user_id IS NULL` and `WHERE assigned_staff_user_id = :her`.
- **`assign` (elevated)** — unconditional, last write wins, `null` accepted.
- **`soft_delete`** — sets `deleted_at`, and `by_id` then misses.
- **`_refreshed`** — one `select(...).where(tenant, id, deleted_at IS NULL).execution_options(populate_existing=True)`, **applied unconditionally on every write path**, not per call site. Its mutation is Task 7's races #2 and the elevated-reassign row; **note in the docstring that no single-writer test can prove it**, which is exactly the finding F57's note records.
- **The board read** — every live ticket not yet delivered, **plus** every ticket delivered on or after `today_jerusalem − DELIVERED_WINDOW_DAYS` (7), ordered **`due_date` ASC, `created_at` ASC, `id` ASC**, capped at `BOARD_TICKET_LIMIT` (500) with `truncated` when the cap bit.
  - ⚠ **The `id` tiebreak is not decoration and its test is the reason it exists.** `created_at` defaults to `now()`, which in Postgres is **transaction start time** and is therefore identical for every row inserted in one transaction — and this module seeds several tickets per `tenant_session`. Seed **three tickets sharing one `due_date` in one transaction** and assert the same order across two consecutive reads. `CustomersRepository.search`'s comment (`customers.py:122-126`) states the failure exactly. `StaffUsersRepository.list_live`'s single-column order (`staff_users.py:37-45`) is **not** a precedent — it gets away with it because its tests seed one row per session.
- **The seamstress union (D9/D12)** — every live `staff_users` row with `role = 'seamstress'` **plus** every distinct `assigned_staff_user_id` on a live undelivered ticket, each carrying `assignable`.

⚠ **`test_atelier_db.py` commits into a session-scoped container** (`migrated_db` and `app_role_url` are `scope="session"`). **F57's D1 trap still applies**: no committed `staff_users` row may hold a floor role, or `test_migrations.py::test_adding_the_role_check_validates_existing_rows` — which re-adds `0011`'s **two-value** CHECK against a populated table — goes red **in a file that never mentions the atelier**. **The safe shape: seed assignee rows inside a transaction the test rolls back, and where a committed assignee is unavoidable, assert on `assigned_staff_user_id` alone** — nothing in this module depends on the assignee's role, because the role check is `test_atelier_service.py`'s.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| the `id` tiebreak in the ORDER BY | order by `due_date, created_at` alone | the same-transaction, same-`due_date` ordering test **RED or flaky** — if it stays green, the seed is one row per transaction and the test is wrong |
| `deleted_at IS NULL` in `by_id` | drop it | the soft-deleted case **RED** |
| the delivered-window predicate | drop it | the window test **RED** |
| the 500 cap / `truncated` | drop the limit | the cap test **RED** |
| the explicit `tenant_id` predicate in `by_id` | drop it (RLS still on) | the cross-tenant case stays **GREEN** — RLS carries it. **Record that in the docstring** rather than pretending the unit test proves the defence-in-depth; Task 8 is where it is proved |

- **Done when**: local db suite green; `make lint` clean; `git show --stat`.
- **Commit**: `feat(atelier): the ticket repository, its guarded writes and the board read`
- **Implements**: D3 (the predicate and `_refreshed`), D4, D9, D12.

---

## Task 4 — `AtelierService`, the schemas, the authorization matrix, and the six audit actions (D3, D4, D5, D6, D7, D9, D11)
`backend/app/atelier/schemas.py` (**✚**), `backend/app/atelier/service.py` (**✚**), `backend/app/models/constants.py`, `backend/tests/test_atelier_service.py` (**✚**), `backend/tests/test_atelier_board.py` (**✚**)

### The failing tests first — fast, against fakes, no Postgres

**`test_atelier_service.py` — the authorization matrix as pure branches:**
- owner / shift_manager on anything.
- **a seamstress advancing her OWN ticket *and* an UNASSIGNED one** → 200. A seamstress **updating** an unassigned ticket → `NotAuthorizedError`. **Both halves, and the second is the one a reader of the API table alone gets wrong** (D3's per-verb table: advancing is recording work she just did; a `due_date` is a scheduling decision).
- a seamstress on **another's** ticket → `NotAuthorizedError`, **and the repository is never called** on the pure-role refusals (`floor/service.py:11-16`'s shape; `test_floor_service.py` is the precedent). A 403 raised after a read is an existence oracle.
- a seamstress may not `delete` — refused by the **route**, not the service (D10), so this is asserted in Task 5.

**The four-outcome discriminators, and this is the block to write first and read hardest.** ⚠ **ONE EQUALITY AND ONE ELSE, on all three of advance, undo and claim:**
- advance, 1 row → **200** + one audit row with `from`/`to`.
- advance, 0 rows, re-read shows **`== target`** → **200 unchanged**, first timestamp kept, **no audit row**.
- advance, 0 rows, re-read shows **anything else** → **409 `TICKET_STAGE_CONFLICT`**. ⚠ **Including an EARLIER stage** — the concurrent-undo interleave D3 spells out (a zero-row UPDATE takes no lock; READ COMMITTED gives the re-read a fresh snapshot). **`elif stage > target` with no `else` returns `None` and 500s the hottest mutation in the feature.**
- advance, 0 rows, re-read `None` → **404**.
- undo: 200; **200 no-op iff the named column is NULL *and every column after it is also NULL*; 409 otherwise** — D4's skip-then-stale-undo sequence verbatim, as a named test needing no database.
- claim: 200; **200 no-op iff the re-read shows it assigned to her**; **409 `TICKET_ALREADY_ASSIGNED` otherwise, explicitly including a re-read showing `NULL`** (a winner who claims and releases in the gap).
- **Undoing `intake` is a 400.**
- Elevated assign is **unconditional last-write-wins and takes no 409** (D9).
- A **non-seamstress** assignee is a 400.
- An unknown / archived / foreign `dress_id` is a **404** (the server path C3 keeps).
- A **past** `due_date` is accepted on create **and** on update (**200**, no warning field); beyond `MAX_DUE_DATE_HORIZON_DAYS` is a 400. **The past-date 200 is the assertion that stops someone resolving D5's asymmetry the wrong way later.**
- **Audit rows**: one per real write, **none on any no-op**; the undo's `details` carrying `previous_stamp`; `ATELIER_TICKET_UPDATED` carrying changed key **names and not values** (Risk 8 — `notes` may hold measurements and `audit_log` has a different retention clock).
- **D7's SAVEPOINT** — `session.begin_nested()` around `upsert`, `IntegrityError` → `by_phone` re-read, **`raise` when that re-read is `None`** (a different constraint failing must not present as a silent wrong customer link). Its race test is Task 7 #4 and it needs its own seam.

**`test_atelier_board.py`** — pure folds over frozen records, the `test_dashboard_math.py` shape: `overdue` against a **frozen clock** either side of Jerusalem midnight and with `delivered_at` set (delivered cancels overdue); the delivered-window cutoff at exactly 7 days; the 500 cap and the `truncated` flag; the `due_date, created_at, id` ordering; and **`seamstresses[]` as a UNION carrying a retired or re-roled assignee with `assignable: false` alongside the live ones** — the assertion that fails if someone "simplifies" it to a filter.

### The code

`app/atelier/schemas.py` — `CreateTicketRequest`, `UpdateTicketRequest` (**a FULL REPLACE: every editable field required, so an omitted key can never silently clear a value** — `UpdateAppointmentTypeRequest`'s shipped rule; the customer is **not** editable), `AssignTicketRequest`, `StageRequest`, `AtelierTicket`, `SeamstressRef`, `EffortBandRef`, `AtelierBoardResponse`. **Every request model is a `ForbidExtraModel`.**

`app/models/constants.py` — the six `AuditAction` members (D11). **No migration**: `audit_log.action` is plain `TEXT` with no CHECK (`0003_auth.py:71-79`), and this is the seventh block to rely on it. **One `STAGE_ADVANCED` value rather than five** — D11's split-rule argument.

`app/atelier/service.py` — the authorization check as **each method's first statement, before any session is opened**; the injectable `Clock` (`main.py:577-582`'s shape); `today_jerusalem(self._clock)` for `overdue`; the six write paths all answering **the full ticket** through `_refreshed`.

⚠ **The effort bands are resolved in the ROUTER from `get_current_tenant(request).settings` and passed in as a plain dict** (D8). Reading them through `TenantsRepository` would open a **fourth session** on a five-second poll — that repository is constructed with a `session_factory` and opens its own session inside every method (`tenants.py:20`, `:31-45`), so it *cannot* join the atelier's `tenant_session`.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| the one-equality-and-one-else discriminator | write it as `if == target: 200 / elif > target: 409` with no else | the concurrent-undo case **RED** with `None`/500 — on advance **and** on undo **and** on claim; all three |
| the authorization-before-read ordering | move the role check after the `by_id` | the repository-never-called assertions **RED** |
| the no-audit-on-no-op rule | write a row unconditionally | the three no-op cases **RED** |
| the capture-before-the-write of `previous_stamp` | move the capture after the write | `details["previous_stamp"]` becomes `null` → **RED**. ⚠ **This mutation leaves every other fast test green**, because monkeypatched repositories never stamp anything — which is why the db-level version in Task 7 is not optional |
| D5's absent lower bound | add `due_date >= today` | the past-date-is-200 case **RED** |
| `UpdateTicketRequest`'s all-required fields | make one optional | the full-replace test **RED** (an omitted key clears a value) |

- **Done when**: `make lint` + `make test` green **locally**. **This is the first milestone**: the whole service contract, every authorization branch and every one of the four outcomes is exercised with no Postgres.
- **Commit**: `feat(atelier): the ticket service, its four-outcome discriminators and six audit actions`
- **Implements**: D3, D4, D5, D6, D7, D8 (consumption), D9, D11.

---

## Task 5 — The ninth `/manage` router, the two error codes, the wiring, **and the `vite.config.ts` segment** (D10, D13, D19)
`backend/app/atelier/router.py` (**✚**), `backend/app/main.py`, `backend/tests/test_atelier_api.py` (**✚**), `frontend/apps/manage/vite.config.ts`

### ⚠ Why the `vite.config.ts` edit is in THIS commit and not in a task of its own

D19 asks the plan to carry the edit as its own task. **It ships in this commit instead**, and the reason is mechanical: `test_spa_serving.py::test_the_manage_dev_proxy_names_every_manage_api_segment` (`:372-403`) derives the segment set from the **live route table** and asserts **SET EQUALITY** against the regex in `vite.config.ts`. The moment this task's router is registered, that test goes **red** — so deferring the one-word edit leaves `make test` red across every task between. One commit, one green suite.

The edit: `atelier` inserted into `MANAGE_API`'s alternation (`vite.config.ts:19`) as the **fourteenth** segment, **and the file's own comment at `:13-17` updated in the same edit** («The thirteen names» → fourteen, «a fourteenth segment» → a fifteenth). ⚠ **The segment must be lowercase letters and hyphens only** — the scrape is `r'"\^/manage/\(([a-z|-]+)\)"'`, so a digit or an underscore makes `re.search` return `None` and the failure reads as *"no proxy key found"* rather than as a drift.

**Why it matters, in F57's shipped words**: without it, *"production, CI and the whole suite stay green while only a developer's machine breaks, serving the SPA shell where the API should be."* **It has bitten this repo twice** (F52 and F57). `test_spa_serving.py` itself needs **no edit** — it is the guard.

### The failing tests first — fast

**`tests/test_atelier_api.py`**, on the `test_floor_api.py` shape:
- **`ATELIER_ROUTES`**, a table of the seven routes, **exported** for `test_staff_role_gating.py` (the `test_floor_api.FLOOR_ROUTES` precedent, `:51`), giving the 401 walk, the wiring walk and the `cache-control: no-store` parametrization for free.
- **The wiring walk names the count**: a **ninth** `/manage` router, where a duplicated `(method, path)` would silently win or lose on include order with no error.
- Each route reaching its own service method with the right arguments, against a `FakeAtelierService`.
- **The CSRF fence on a POST and its absence on the GET** (`csrf.py:48` gates on `request.method in MUTATING_METHODS`; the GET's protection is the session cookie and the role gate alone).
- **All three roles reach all seven routes except `delete`, which admits two.** The seamstress's 403 on `delete` is a real end-to-end assertion, not a structural one.
- **`SPEC_ERROR_CODES` asserted SET-EQUAL**, adding exactly `TICKET_STAGE_CONFLICT` and `TICKET_ALREADY_ASSIGNED` — so a third new code cannot arrive unnoticed (`test_floor_api.py:418`'s shape).
- `TicketStage`'s and `EffortBand`'s **wire literals** asserted set-equal.
- The payload literal for a two-ticket board.
- **A past `due_date` is a 200; beyond the horizon is a 400** (the API-level half of D5).
- **A band key outside the five is a 400 and never reaches the row.**

### The code

`app/atelier/router.py` — the `app/floor/router.py` shape verbatim, including a module docstring in that register:

```python
router = APIRouter(
    prefix="/manage",
    dependencies=[
        Depends(_no_store),
        Depends(require_role(StaffRole.OWNER, StaffRole.SHIFT_MANAGER, StaffRole.SEAMSTRESS)),
    ],
)
```

**Three roles spelled as LITERALS, not `*StaffRole`.** F57's floor router is spelled from the enum because *"the set this router admits **is** 'every role the product has'"* (`floor/router.py:26-29`); the atelier's set is not, and a sixth role must be refused here by default.

**Per-route tightening**: `POST …/delete` carries `Depends(require_role(StaffRole.OWNER, StaffRole.SHIFT_MANAGER))` on top of the router gate. `RoleGate` composes by **intersection** (`auth/dependencies.py:44-45`), so a per-route gate can only narrow — which is why F41 needs its own module and cannot hang a route off an existing router.

**`_no_store` is a local three-line copy, not an import** — the shipped convention, sixth instance (`auth/staff_router.py:22-27` records the decision). **Tenant from `get_current_tenant(request)`**, never `StaffContext.tenant_id` — the third module told this in writing. **No rate limiter** (no `/manage` router carries one and F41 does not introduce the first). **Real HTTP verbs and a path parameter for the target** — the `.claude/rules` RPC/`@QueryValue` guidance is Kotlin boilerplate for another codebase.

**The bands are resolved here**, from `get_current_tenant(request).settings`, and passed into the service as a dict (D8).

`app/main.py`, three edits:
1. `app.state.atelier_service = AtelierService(...)` beside the other service constructions, with the injectable clock (`:577-582`'s shape).
2. Two `@app.exception_handler`s returning `TICKET_STAGE_CONFLICT_BODY` and `TICKET_ALREADY_ASSIGNED_BODY`, the shape of the twenty already there. **Two and not one** because the console's copy and the user's next move differ (D13).
3. `app.include_router(atelier_router)` **after `customers_router` (`:1109`) and before `storefront_router` (`:1112`)**, keeping every `/manage` router contiguous and ahead of the anonymous surfaces, carrying the numbered shadowing comment as **"The NINTH"** and naming `test_atelier_api.py`'s `ATELIER_ROUTES` as what keeps it honest. **`_register_spas(app)` stays last.**

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| `atelier` in `MANAGE_API` | drop the word | `test_the_manage_dev_proxy_names_every_manage_api_segment` **RED** — run this once, deliberately, to see the guard bite |
| the per-route `require_role` on `delete` | drop it | the seamstress-403-on-delete case **RED**, and Task 6's walker **RED** |
| the router-level gate | drop it | `test_every_manage_route_is_role_gated` **RED** |
| either 409 handler | drop the registration | the corresponding body test **RED** (bare 500) |
| `get_current_tenant(request)` in a handler | take the tenant from `StaffContext` | the host-derived test **RED** |

- **Done when**: `make lint` + `make test` green **locally**, `test_spa_serving.py` included. **This is the second milestone**: the whole HTTP surface, all seven routes, both new codes and the dev proxy are exercised end to end with no Postgres. `git show --stat` shows **both** `backend/app/main.py` and `frontend/apps/manage/vite.config.ts`.
- **Commit**: `feat(atelier): the ninth /manage router, its two conflict codes and the dev proxy segment`
- **Implements**: D10 (the gate), D13, D19.

---

## Task 6 — The walker restructure: a per-role set equality, and the one test F57's Risk 1 calls untouchable (D10, C1)
`backend/tests/test_staff_role_gating.py`

**This is the delicate task and it is separated so it gets its own review.** `test_the_floor_roles_reach_exactly_the_floor_routes` (`:240-302`) currently asserts, over the whole `/manage` route table: (1) `admits_floor == FLOOR_OPEN`; (2) `not partial` — no route admits only *some* of the three floor roles; (3) `FLOOR_OPEN - seen == set()`.

**An atelier router admitting `seamstress` and not the other two reds assertions 1 and 2 simultaneously, and it is correct code failing a correct test.** F57's Risk 1 says the test *"must never be relaxed to a subset check"* — and a reviewer facing this red on a test declared untouchable is exactly the person most likely to relax it.

### The edit

```python
FLOOR_OPEN = {FLOOR_READ, FLOOR_BREAK_START, FLOOR_BREAK_END}      # unchanged

# ⚠ DELETE IS SPLIT OUT, and this is not tidiness. The walker classifies on
# `effective = frozenset.intersection(*role_sets)` (:279), and delete carries a
# per-route require_role(OWNER, SHIFT_MANAGER) on top of the router gate — so its
# effective set is {owner, shift_manager} and seamstress is NOT in it. A
# NON_ELEVATED_REACH row naming delete would be one element larger than reality
# and would RED A CORRECT BUILD on the one test F57's Risk 1 declares untouchable.
ATELIER_DELETE = ("POST", "/manage/atelier/tickets/{ticket_id}/delete")
ATELIER_OPEN = { …the seven rows, ATELIER_DELETE included… }

NON_ELEVATED_REACH: dict[str, frozenset[tuple[str, str]]] = {
    StaffRole.RECEPTION.value:       frozenset(FLOOR_OPEN),
    StaffRole.SALES_ASSISTANT.value: frozenset(FLOOR_OPEN),
    StaffRole.SEAMSTRESS.value:      frozenset(FLOOR_OPEN | (ATELIER_OPEN - {ATELIER_DELETE})),
}
```

The walker keeps **intersecting** the gates — never `any(...)`; F57's D5 gives the whole argument and F41's own `POST /delete` is precisely the shape that would red-fail under `any` — and asserts, **for each of the three roles**, that the set of routes whose `effective` set contains it equals its table row.

⚠ **Assertion 2's `partial` accumulation (`:284-285`) and its assertion (`:298`) are DELETED, not adapted** (C1). Its model is that the three floor roles move as a block, which F41 makes false; its intent — *"admits only some of them"* — is now expressible only as a row naming a route the table does not, which **is** assertion 1. **Rewrite the `:248` docstring in the same edit** so the next reader does not meet a "never relax this" comment above what looks like a relaxation, and state there what the restructure preserves: still an exact set equality, still derived from the live route table, still catches a route that quietly lost its gate (an ungated route's `effective` is empty, so it drops out and the equality fails), still fails the day some future router copy-pastes a wide gate.

**Assertion 3's anti-vacuity half is KEPT and WIDENED to the FULL `FLOOR_OPEN | ATELIER_OPEN`, delete included** — delete does exist, the owner reaches it, and the point of that half is that no row of either table names a path the route table has lost.

⚠ **`test_gate_admits_listed_roles` (`:333`) gains a NEW CASE, not three roles.** It is a `RoleGate` unit test; widening an existing assertion would assert something false. A **second** case asserts `require_role(OWNER, SHIFT_MANAGER, SEAMSTRESS)` admits exactly those three and refuses `reception`. (F57's shipped note, verbatim reasoning.)

⚠ **`test_gates_admit_only_known_roles` (`:190`) needs ZERO edits** — it derives `known` from the live enum and F41 adds no role.

**`ATELIER_ROUTES` joins the two shipped HTTP walks**, so the seven rows get a real end-to-end 403 assertion and not only the structural one.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| the `ATELIER_DELETE` split | put `ATELIER_DELETE` back into the seamstress row | the seamstress equality **RED** against a **correct** build — run this once, see the red, and understand why the split exists |
| the intersection | swap `frozenset.intersection` for `any(...)`/union | the seamstress equality **RED** (delete would appear in her effective set) |
| the router gate on the atelier | drop it | `admits_floor` gains seven routes → **all three** equalities **RED** |
| the per-role split | collapse the three rows back to one `FLOOR_OPEN` check | the seamstress row **RED** — the restructure is load-bearing, not cosmetic |
| the widened anti-vacuity half | narrow it back to `FLOOR_OPEN` | delete a route from the router and the test stays **GREEN** — the vacuity the widening exists to prevent |

- **Done when**: `make lint` + `make test` green locally; every mutation above performed, observed and restored; **and each mutation verified to leave every other test green** — a mutation that reds three tests has not pinned anything specific.
- **Commit**: `test(staff): the role walker becomes a per-role set equality as the atelier admits a seamstress alone`
- **Implements**: D10, spec Conflicts 6 and 12, C1.

---

## Task 7 — The four forced-interleave races and the two non-race mutations (D3, D4, D7, D9)
`backend/tests/test_atelier_db.py`

**`db`-marked, run locally.** ⚠ **`asyncio.gather` is deliberately NOT used for any of the four**, for F34's and F57's reason verbatim (`test_booking_owner_db.py:1313-1336`, `test_floor_db.py:251-263`): **gather does not ORDER two transactions**, so the loser most often loads *after* the winner commits, its in-memory instance is already correct, and the zero-row branch the test exists to prove goes green **without the mechanism ever being exercised**.

**The mechanism is `tenant_session`'s own shape**: exiting the context manager **is** the commit (`db/tenant.py:25`), and two nested `tenant_session`s on one `NullPool` factory take two separate connections. Under READ COMMITTED the loser's UPDATE and its re-read both see the winner's commit.

> ⚠ **STATE THIS PLAINLY AND OBEY IT: a mechanism whose test stays GREEN when the mechanism is removed is VACUOUS and must be rewritten.** Every row below names the exact mutation, and **each mutation must also be verified to leave every OTHER test green** — a mutation that reds three tests has pinned nothing specific. F57's shipped note records two mechanisms that would have shipped unproven.

| # | Test | Mechanism | **MUTATION → RED** |
|---|---|---|---|
| 1 | `test_a_concurrent_advance_to_a_later_stage_refuses_the_earlier_one` | the `AND <every later column> IS NULL` clause in `advance_stage`'s predicate | **Delete the later-columns clause.** The loser stamps `qc_at` on a ticket already at `ready`; `assert stored.qc_at is None` reds and the 409 becomes a 200. **Every single-writer test stays green — which is exactly why this one must exist** |
| 2 | `test_the_loser_of_an_advance_race_renders_the_databases_stage` | `populate_existing=True` inside `_refreshed` | **Drop `populate_existing=True`.** ORM-enabled DML's `evaluate` synchronization has already stamped the SET value onto the identity-mapped instance the loser loaded, and `expire_on_commit=False` hands it straight back — so `assert stage_of(row) == READY` reds with `QC`. ⚠ **It MUST be this shape: the loser's session has to have LOADED the row before the write**, which `advance` does anyway to build the audit row's `from`. F57's note records that with only fresh-session tests present, removing this flag changed **nothing** |
| 3 | `test_two_seamstresses_claiming_one_ticket_leave_one_owner` | `AND assigned_staff_user_id IS NULL` in the claim predicate | **Delete the `IS NULL` clause.** The loser overwrites the winner; `assert stored.assigned_staff_user_id == winner_id` reds and the 409 becomes a 200 |
| 4 | `test_two_intakes_for_one_new_phone_create_one_customer` | D7's `session.begin_nested()` SAVEPOINT + `IntegrityError` → `by_phone` re-read | **Delete the savepoint (keep the `try`).** The loser's `IntegrityError` has aborted the enclosing transaction, so the re-read raises `PendingRollbackError` → **RED**. **Second mutation — delete the whole `try`** → the raw `IntegrityError`, which is the 500 the guard exists to prevent |

**Plus a fifth forced-interleave and a sixth non-race, both of which pin `_refreshed` against being re-scoped to one call site:**

| Test | Mechanism | **MUTATION → RED** |
|---|---|---|
| `test_the_loser_of_an_elevated_reassign_renders_the_databases_assignee` (db, forced interleave) | `populate_existing=True` applied to the **assign** path and not only to advance | **Drop `populate_existing=True` from `_refreshed`.** Two managers reassign one ticket; the loser's response carries **its own** assignee instead of the winner's → red. Race #2 pins it for advance only; this is the row that stops the flag being re-scoped, which is the mistake `_refreshed`'s own docstring (`staff_users.py:195-212`) says has bitten this repo three times |
| `test_the_undo_audit_row_carries_the_stamp_it_destroyed` (db) | the capture of the previous stamp into a **local, BEFORE** the write | **Move the capture after the write.** `evaluate` synchronization stamps `NULL` onto the very instance being read, so `details["previous_stamp"]` becomes `null` and the assertion reds. `test_floor_db.py::test_the_end_audit_row_carries_the_timestamp_the_break_actually_started` is the shipped precedent, and **F57's note records that this mutation leaves all 17 fast tests green** — monkeypatched repositories never stamp anything |

### ⚠ RACE #4 NEEDS ITS OWN SEAM, and a test written without it is VACUOUS

Races #1–#3 and the reassign work under session ordering because each loser's mechanism is a **single UPDATE** whose predicate is evaluated after the winner committed. `CustomersRepository.upsert` is **read-then-insert inside one call** (`customers.py:184-204`): `by_phone` → miss → `session.add` → `flush`. For an `IntegrityError` to fire, **both** sessions must miss before **either** inserts — and session ordering gives only two arrangements, neither of which is a test:

- **Loser held open first** → the loser INSERTs (uncommitted, holding the index tuple) and the winner's `flush` **blocks** on `idx_customers_tenant_phone_unique`, waiting on a transaction that cannot commit until the outer `async with` exits. Single-threaded asyncio: **a hang**.
- **Winner first, committed, then loser** → the loser's `by_phone` **finds** the committed row. No INSERT, no `IntegrityError`, the savepoint never entered — **and the test passes identically with `begin_nested()` deleted.**

**The seam, named:** monkeypatch the loser service's `CustomersRepository.by_phone` so that on its **first** call it returns `None` **and, as a side effect, commits the winner's customer row from a separate `tenant_session`**. That forces miss → winner commits → loser INSERTs → `IntegrityError`, deterministically, with no `gather`. Both mutations then bite.

**If the seam is judged too costly, D7 already ranks this mechanism as the cuttable one of the four — and then THE MECHANISM AND THE TEST ARE CUT TOGETHER**, never the harness alone. Shipping the savepoint with a test that cannot fail is the one option this plan does not leave open.

- **Done when**: local db suite green; **all six mutations performed, each observed red, each verified to leave every other test green, each restored**; `make lint` clean.
- **Commit**: `test(atelier): the four forced-interleave races and the two identity-map mutations`
- **Implements**: D3, D4, D7, D9.

---

## Task 8 — The RLS isolation suite (**non-negotiable**)
`backend/tests/test_atelier_isolation.py` (**✚**)

**Non-negotiable, and the E9 brief's own words are the reason: *a new tenant table without these probes is a hole in the crown jewels.*** The sixth isolation suite, the `test_catalog_isolation.py` shape.

⚠ **Connected ONLY as the app role, via the `app_role_url` fixture (`conftest.py:156-161`) over a `NullPool` engine — NEVER `migrated_db`**, because the container superuser bypasses RLS and GRANTs unconditionally and **every assertion would pass vacuously.**

### The failing tests first

- Tenant A writes a ticket; **tenant B's every reader returns `None` / empty / 0** — the board read, `by_id`, the position of nothing.
- **Every write verb against tenant A's ticket id from tenant B's context is a 404 indistinguishable from missing** — advance, undo, assign, update, delete. Not a 403, which would confirm existence.
- **A connection with NO tenant context sees zero rows** — RLS fails closed via `current_setting('app.tenant_id', true)::uuid` being NULL (`db/rls.py:9-11`).
- Tenant B's board read never counts A's tickets; tenant A re-reads and **nothing of hers moved**.
- **The GRANT is exercised**: the app role can `INSERT`, `SELECT`, `UPDATE` and `DELETE` on `alteration_tickets`. Omitting the GRANT in Task 1 fails nothing until exactly here, as `permission denied`.
- **`notes` — the column Risk 8 hands to F20 — is covered by the same assertions**, so there is no separate probe for the most intimate field on the table; state that in the module docstring rather than leaving it inferred.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| `enable_tenant_rls("alteration_tickets")` in the migration | delete the loop, re-run | **EVERY** isolation probe **RED**. If any stays green, the suite is connected as the superuser and is worthless |
| the `app_role_url` fixture | swap it to `migrated_db` | the probes go **GREEN VACUOUSLY**. **Run this once, deliberately, confirm it, then restore.** That is the proof the suite measures RLS and not nothing |
| the explicit `tenant_id` predicate in `by_id` | drop it | stays **green** (RLS carries it) — **record that in the docstring** rather than implying this suite proves the defence-in-depth |

- **Done when**: local db suite green; **both mutation-checks performed and restored**; `make lint` clean.
- **Commit**: `test(atelier): forced RLS isolation for alteration tickets across all seven verbs`
- **Implements**: D1's RLS block, the E9 brief's non-negotiable, Risk 8.

---

# Part II — the frontend

## Task 9 — Capture the qa-greps baseline, then the i18n block and its four shipped guards (D18)
`frontend/apps/manage/src/i18n/he.ts`, `…/i18n/ar.ts`, `…/__tests__/i18n.test.ts`

### ⚠ FIRST, before any frontend file is written: capture the baseline

```
cd "…/.worktrees/alteration-tickets" && make qa-greps > "…/scratchpad/qa-greps-baseline.txt" 2>&1
```

`qa-greps.sh:17` scopes its four `check` patterns to `apps/storefront/src`, so F41 cannot trip them. **One block does reach `apps/manage/src`**: the unzoned-date review at `:61-66`. It prints `review` and does **not** set `status`, so it cannot fail the build — which is exactly why a growing list would go unnoticed. F41 adds **no formatter** (D18 — `plainDate`, `jerusalemTime`, `todayJerusalem` all ship in `lib/jerusalem.ts`), so the output must be **byte-identical** at Task 14. Capture it now; diff it then.

### The failing tests first

**`__tests__/i18n.test.ts`** — a `F41 atelier keys resolve` block in the shape F15/F51/F52/F17/F34/F57/F53 each have:

```ts
const HE_F41 = entries(
  he.translation,
  (key) => key === "nav.atelier" || key.startsWith("atelier."),
);
const HE = [...HE_F15, ...HE_F51, ...HE_F52, ...HE_F17, ...HE_F34, ...HE_F57, ...HE_F53, ...HE_F41];
```

⚠ **`HE_F41` MUST BE DECLARED *AND SPREAD INTO* `HE` (`:48`), OR FOUR SHIPPED GUARDS SILENTLY SKIP THIS FEATURE.** `HE` is a **hand-assembled union of per-feature selections**, and the resolve check, **both** register guards (`:397` no-exclamation, `:401-402` `/נשלח|תישלח|בדרך/`) and **the `ar` parity guard (`:417-420`, which DOES exist and has since F52)** all iterate it. A block declared and not spread is skipped **silently and greenly** — the file records that exact failure in its own words for F52, and F53 asserts the fold rather than trusting it. **F41 does the same: `expect(HE.map(([key]) => key)).toContain("nav.atelier")`.** Only the no-empty-`ar` guard (`:407-414`) works without the fold, because it reads `ar.translation` directly.

The block's own assertions, mirroring `HE_F57`'s: a **`length` floor**; the no-retry-interval check over its values; the no-role-in-`accessEnded` check; **the label-in-name containment for ALL SIX aria pairs** — pause, resume, advance, undo, skip, skipCommit, assign, assignCommit, claim, release, edit, delete — asserting each `*Aria` value **starts with** its visible label (WCAG 2.5.3; `floor.pauseAria` is «השהיה — עדכון הצוות» and not «השהיית…» for exactly this reason, and the containment assertion at `:337-345` is the shape to copy); and the **resolve check over every `STAGE_LABEL_KEY` value**.

### The code

`i18n/he.ts` and `i18n/ar.ts` — `nav.atelier` plus the `atelier.*` namespace, **95 keys** (copy deck's 96, minus `form.dress`, `form.dressNone` and `form.error.dueDateHorizon`, plus `error.rejected` and `form.error.server` — C3, C5). **Both files, flat dotted keys appended as one per-feature block, Hebrew standing in untranslated in `ar` and NEVER an empty string** (i18next's `returnEmptyString` default renders `""` rather than falling back, so a placeholder blanks the page).

**Copy is transcribed from `copy.md` verbatim**, including the four corrections to D18 the deck records: `cue.advanced` = «{{name}} — שלב חדש: {{stage}}.» and `cue.undone` = «{{name}} — חזרה לשלב: {{stage}}.» (the five stage words are past-tense verbs and an adjective, and «ל» does not prefix them — «הוחזר להתקבל» is the commonest undo there is); `cue.assigned` = «שויך ל{{seamstress}}.» (one interpolated user value, not two, which is what lets the shipped `isolateBidi(text, value)` and `{ text, name }` state shape work unmodified); and `assignLabel` = «תופרת» against `assignCommit` «שיוך» (two controls in one card must not carry one accessible name).

⚠ **`atelier.stageCount` interpolates `{{total}}`, NEVER `{{count}}`** — `count` is i18next's plural-resolution trigger, and this string renders **ten times per paint** (five headings, five rail chips). And it carries **no noun**: Hebrew has singular, dual and plural agreement, so «כרטיס / שני כרטיסים / כרטיסים» would need four plural suffixes per string in **two** bundles, while the `<ul>`'s own list role already announces the item count.

⚠ **`atelier.idleStopped` may not be byte-identical to `board.idleStopped` or `floor.idleStopped`.** All three write into a `role="status"` region and all three idle windows are reset by the same global listeners in `usePoll`. This console renders one section at a time so the collision is rarer here — the string still names its own region, **because the reason is a rule and not a coincidence**.

⚠ **Ten values are byte-identical to shipped `board.*` / `floor.*` strings and are DECLARED, not reused.** `design.md` **F-9** records that F57's own F-9 predicted *this* PR as the one where a shared `poll.*` namespace becomes worth the rename — **and it is still declined here**, for the reason that has not changed: lifting them would edit `BoardSection`'s and `FloorPanel`'s i18n, and **both components must pass unedited**, which is the only thing separating a faithful fourth `usePoll` consumer from a subtly different one. Named owner, not a deferred trigger: **team, at F37 or F59, as a standalone i18n PR touching no component logic.**

⚠ **Risk, and it bites immediately**: once `atelier` exists as an `he.ts` section, **any quoted `"atelier.…"` literal anywhere in `apps/manage/src` is scraped as an i18n key** and must resolve to a defined, non-empty Hebrew string. Do not name a `data-testid` `atelier.submit`.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| the `...HE_F41` spread | declare the constant and drop it from `HE` | **the fold assertion RED — and every other guard silently green.** Run this once and watch the parity guard pass over 95 missing `ar` keys. That is the whole reason the fold is asserted |
| one `ar` key | delete it | the parity guard **RED** (only with the fold in place) |
| `{{total}}` → `{{count}}` | swap it | no test reds — **which is why it is a rule in the copy deck and a review item, not a test.** Record it; do not invent a guard for it |

- **Done when**: `make fe-test` green; `pnpm -r lint && pnpm -r typecheck` clean; `make qa-greps` byte-identical to the baseline.
- **Commit**: `feat(manage): the atelier i18n namespace, its ar parity and the HE_F41 fold`
- **Implements**: D18.

---

## Task 10 — `lib/stages.ts`, the API client, the thirteenth section and the nav row (D18, C2)
`frontend/apps/manage/src/lib/stages.ts` (**✚**), `…/src/api.ts`, `…/src/App.tsx`, `…/src/__tests__/Nav.test.tsx`

### The failing tests first

**`Nav.test.tsx`, and every number moves together** — the file says so in its own comment at `:151`:
- `NAV_LABELS` (`:66`) gains **«תפירה» after «לוח היום» and before «צוות»** → **12** entries.
- `toHaveLength(11)` at **`:156`** → `(12)`.
- `.slice(0, 9)` → **`.slice(0, 10)`** at **BOTH** sites: **`:114`** and **`:204`**. Verified by grep: exactly two call sites.
- The test **names**: `:103` *"all eleven sections"* → twelve; `:110` *"nine sections"* → ten; `:145` *"keeps the owner's eleven and the shift manager's nine"* → twelve and ten. The comment at `:85` (*"below a `.slice(0, 9)`"*) → 10.
- ⚠ **C2 — SPLIT the shared `it.each` at `:122`.** Remove `"seamstress"` from `it.each(["reception", "sales_assistant", "seamstress"])`, leaving the other two asserting `["הצוות בקומה"]` at `:138` **unchanged**, and add:
  ```
  it("shows a seamstress the floor panel and the atelier, in that order")
    → expect(navItems()).toEqual(["הצוות בקומה", "תפירה"])
  ```
  **The ORDER in that assertion is the whole test.** It is what fails if the `NAV` row went in *before* `floor` instead of after — which would also move `reachable[0]?.key` and land a seamstress on the atelier instead of the floor.

**`lib/stages.ts`** — `STAGE_LABEL_KEY` resolves every value through i18n (a key in the map but absent from `he.ts` is caught **here**, while a missing member is caught by the **compiler** — `lib/roles.ts`'s header says why the two halves catch different bugs); `laterStages(current)` returns only strictly-later stages and the empty array at `delivered`; `bandLabel(minutes, bands)` returns the band's word on a match and **«{{minutes}} דק׳»** when nothing matches.

### The code

`lib/stages.ts` — `STAGE_ORDER: readonly TicketStage[]`, `STAGE_LABEL_KEY: Record<TicketStage, string>`, `laterStages`, `bandLabel`. **`Record<TicketStage, string>` is the point**: a sixth stage added to the union without a key is a **compile** error, not a wrong label. **In `lib/` so this section and F42's picker share it with no import cycle.**

`api.ts` — `TicketStage`, `EffortBand`, `AtelierTicket`, `SeamstressRef`, `EffortBandRef`, `AtelierBoardResponse`; and `getAtelierBoard`, `createTicket`, `updateTicket`, `assignTicket`, `advanceStage`, `undoStage`, `deleteTicket` on the exported `api` object. **No case conversion** — this app speaks the backend's snake_case verbatim. ⚠ **`createTicket` and `updateTicket` send `dress_id: null` always** (C3), with a comment naming F43 as the caller that will send an id.

`App.tsx` — `SectionKey` (`:20-33`) gains **`| "atelier"`** as the **thirteenth** member; **the stale in-file comment at `:32` (*"F57's floor — the ELEVENTH member"*) is corrected in passing** (F53's `customers` made `floor` the twelfth). A new `ATELIER_ROLES = ["owner", "shift_manager", "seamstress"] as const`. A **thirteenth** `NAV` row, `{ key: "atelier", labelKey: "nav.atelier", roles: ATELIER_ROLES }`, **between `floor` (`:103`) and `staff` (`:104`)**.

⚠ **That slot is the same position as "after «לוח היום», before «צוות»" and the two phrasings are NOT in conflict** — `floor` carries `roles: FLOOR_ONLY`, so **the owner never sees it**, and all three counted claims hold at once: the owner's filtered nav is 12 with «תפירה» between «לוח היום» and «צוות»; the shift manager's is `NAV_LABELS.slice(0, 10)`; and a seamstress sees «הצוות בקומה» then «תפירה», so `reachable[0]?.key ?? section` (`:165-167`) still lands her on the floor **with no edit to `useState<SectionKey>("dashboard")` (`:120`)**. Put it *before* `floor` and the last two break together.

One render branch: `{activeKey === "atelier" && <AtelierSection selfId={staff.id} role={staff.role} />}`. **No atelier state above `AtelierSection`** — lifting rows into `App` would make every atelier tick repaint the whole console.

> **Keep this diff APPEND-SHAPED.** Two other sessions are live in this checkout and `App.tsx` and the manage i18n bundles are the most contended files in the repo.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| the nav row's position | move it **before** `floor` | the seamstress order assertion **RED** — and note that the owner's 12-entry assertion stays green, which is why the order assertion is the one that matters |
| `ATELIER_ROLES` | swap it for `FLOOR_ONLY` | the owner's 12-entry assertion **RED** and the seamstress's still green — the pair is what pins it |
| `STAGE_LABEL_KEY`'s `Record` type | widen it to `Partial<Record<…>>` | `tsc` stops catching a missing member → `make fe-build` no longer protects it. **Record this; it is a type-level guarantee, not a test** |

- **Done when**: `make fe-test` + `make fe-build` green; `pnpm -r lint && pnpm -r typecheck` clean.
- **Commit**: `feat(manage): the atelier nav row, its stage helpers and the board API client`
- **Implements**: D18, spec §Frontend changes, C2.

---

## Task 11 — `AtelierSection`: the five named regions, the stage rail, the poll, SC 2.2.2 and the thirteen board states (D12, D15, D17)
`frontend/apps/manage/src/components/AtelierSection.tsx` (**✚**), `…/src/__tests__/AtelierSection.test.tsx` (**✚**)

### ⚠ REUSE `lib/usePoll.ts`. Do not write a third poll loop.

F41 is the **fourth** caller of the hook (`BoardSection`, `FloorPanel`, this, then F42's extension of this) and **re-derives nothing**. `Frontend/apps/manage/src/lib/usePoll.ts` is listed as **never modified** in the manifest, and **any edit to it is a review stop** — it has three shipped callers.

**Six mechanisms come from the hook**: the single arming site (schedule-after-settle, so at most one request in flight per tab **by construction**), the `document.hidden` gate plus the `visibilitychange` **immediate** refetch, the 5 s → 60 s backoff with reset on first success, the `{401, 403}` terminal classification, the idle stop, and the monotonic generation behind `isCurrent`.

**Two shipped fixes come with it and this section must not defeat either. Both are one line and both are INSIDE the hook:**
- **The unmount fix** — `runningRef.current = false` at **`usePoll.ts:233`, BEFORE `clearTick()` at `:234`**, with its comment at `:224`. `clearTick()` alone cancels only the timer armed **right now**; the arming sites are a request's `.finally()`, which runs **after** cleanup when a request is in flight, and nothing in tick → run → finally → reschedule touches React state — **so the loop would outlive the component. That leak shipped once and cost one permanent 5-second request loop PER NAV-AWAY, for the rest of a twelve-hour session.**
- **The StrictMode-idempotent mount effect** — `runningRef.current = true` as the effect's **first** line, `:218`. Without it a setup → cleanup → setup cycle, which `<StrictMode>` performs on every mount in development, leaves the loop permanently dead while `mode` still reads `"running"`: a pause control over a loop that is not polling.

⚠ **`run` is SYNCHRONOUS — `run: (generation: number) => TickOutcome` (`usePoll.ts:54`), NOT the `Promise<TickOutcome>` F57's spec D10 predicted.** The caller fires `void load()` and returns. `TickOutcome` is `void | "held" | "suppressed"`. **Coding against the prediction gives you a `Promise` where a `TickOutcome` is expected, with no type error at the call site** (spec Conflict 5).

**Four things are the CALLER's** (`FloorPanel.tsx` is the reference, and every one of its hazards is commented): its own `holdRef` pointer-hold → `"held"` (`:179-182`) — **it matters more here than on the floor panel, because a card changing column is a LAYOUT change under a travelling finger, not a text swap**; its own `mutationsRef` → `"suppressed"` (`:82`, `:285`, `:332`), with the single re-arm in the mutation's own **`.finally()`** (`:337`) and **never its success path**, so a refused advance does not park the loop; `poll.bump()` before every mutation; and `poll.fail(error)` in every mutation's `catch`, which is what makes a mutation's **403 terminal** on the same `{401,403}` rule the ticks use. **A 404 is NOT terminal** — a ticket vanishing is a fact about the ticket, not about her access.

**Never optimistic.** Every mutation answers the **full ticket** and the card is patched from the server's row, so the console cannot disagree with itself — and on a 200 no-op that renders the **first** actor's timestamp rather than this request's intent.

### The failing tests first — `vi.useFakeTimers()`, every advance wrapped in `act()`

**Structure (§9.1):**
- **Each of the five columns resolves as `getByRole("list", { name: <stage word> })`** and each `<section>` is a **named region**. This also catches a column rendered as a `<div>` when someone reaches for CSS grid. **An unnamed `<section>` is not exposed as a region at all** and an unnamed `<ul>` is an anonymous list — a user navigating by list (NVDA `L`, VoiceOver rotor), which is exactly what a five-region board invites, would land on five consecutive anonymous lists with no way to tell `qc` from `ready`.
- The column `<h3>` carries the stage word and its count, with **no noun** and **`{{total}}`**.
- `<ul tabIndex={0}>` **unconditionally at every width** — axe's `scrollable-region-focusable` fires on the bounded ≥768 body, and a resize observer deciding an ARIA-relevant attribute is a mechanism to keep true for a tab stop that costs nothing. It is also useful: §3.4's tab order depends on it.
- **Heading levels**: the shell owns the `h1`, the section heading is an `h2` (`FloorPanel.tsx:344`'s exact shape — `tabIndex={-1}`, which adds **no** tab stop), the five column headings are `h3`. No skipped levels; **the card has no heading**, or sixty headings would sit between two columns.

**The stage rail (§1.1):** five `<a href="#atelier-h-{stage}">` inside a **named** `<nav aria-label>` — a second navigation landmark on a page that already has one must be named. Activating a chip focuses that column's `<h3 tabIndex={-1})` — **fragment navigation to a `tabindex="-1"` target focuses it, which is exactly how `ConsoleShell`'s shipped `SkipLink` reaches `#console-main` (`ConsoleShell.tsx:84`)**, so this is zero JavaScript, no `scrollIntoView` and no focus code. A chip for an **empty** column still renders reading «· 0» and still links (a chip that vanishes is a control that moves under a finger). The chips carry `min-h-11` explicitly — `py-2 text-sm` lands near 40 px.

**Layout (§6, `design.md` F-2):** one column at 375; **two-up at ≥768 and 1440** (`md:grid-cols-2 md:gap-4 md:items-start`), each column body `md:max-h-[32rem] md:overflow-y-auto`. **There is no five-across view at any width and that is arithmetic, not taste**: `ConsoleShell` caps content at 720 px in three places (`:46`, `:56`, `:84`) → 688 − 4×12 gap = 640 ÷ 5 = **128 px per column**, minus `Card`'s `p-6` = **80 px of content**, and a `Button size="md"` reading «לשלב הבא» is wider than that. **Lifting the cap is a console relayout owned by F42 and is out of scope.**

**SC 2.2.2 — the sole automated coverage of a legal requirement (axe has NO rule for it), and it may not be cut as redundant with the axe row:**
- The pause control **stops the loop** — tap, advance several intervals, assert **no calls**.
- **Resume fetches before the interval elapses and at the BASE gap**, not a backed-off one.
- **One** button whose accessible **name** flips; **never `aria-pressed`**.
- It is the **FIRST stop inside the section, before any card** — a 2.2.2 mechanism placed after the content it governs is reachable only by walking the list that is repainting under the walk.
- `toHaveClass("min-h-11")` and the focus ring — **a class assertion, never a measurement**, because jsdom has no layout engine.
- **Focus stays on it across the press** — it renames, it does not unmount.
- The **idle stop** fires at `IDLE_STOP_MS` and its copy **names its own region**.

**The live region (§4.2, and this is F34's F-7 in full):**
- **The announced region does NOT change across several consecutive ticks with the cue already populated.** ⚠ **A single-tick assertion passes against the broken version whenever the cue starts empty.** Populate the region first, observe it with a `MutationObserver` across **three** ticks, and assert **both** that the ticks happened **and** that `takeRecords()` is empty. Assigning a non-empty string to a text node runs the DOM's string-replace-all and produces a real `childList` mutation **even when the two strings are byte-identical**.
- It **does** change on an advance and on a pause.
- **The freshness line is present, NOT `aria-hidden`, and OUTSIDE every announced region** — asserted as three separate `closest()` calls (`role="status"`, `role="alert"`, `[aria-live]`), **with a NEGATIVE CONTROL**: a fixture rendering the line **inside** a `role="status"` region and asserting the selector **DOES** match. ⚠ **`closest('[aria-live]')` alone is VACUOUS** — every live region in this repo is a bare `role="status"` with no `aria-live` attribute, and `closest()` matches attributes, not implicit ARIA, so it returns `null` **even nested inside the region**.

**The thirteen states**, every one from §5 and none optional: `A-load` (one `Card` with `Skeleton variant="text" lines={3}`, **no freshness row and therefore no pause control** — a control over a skeleton pauses a fetch the user has not seen produce anything; the cue carries `atelier.loading`); `A` loaded; **`A-empty`** (the five columns **and the rail** replaced by one `EmptyState` whose body **teaches the five stage words in one sentence**, plus the CTA as its `action`; **the freshness row still renders** — a surface that has stopped updating must still be able to say so); `A-emptycol`; `A-fail` (the **outage** register, `atelier.loadFailed`, plus «רענון» — **and the freshness row and its pause control DO render**, because the loop is alive and backing off and a viewer who wants it stopped must be able to stop it); `A-stale` (**the cards stay**; `staleAt` in `text-warning-text font-semibold`; **nothing states the interval and nothing may**, because the backoff falsifies any number the moment it doubles); `A-paused` (cards stay and are **not dimmed** — they were correct at «עודכן 14:07» and pausing did not make them wrong; **no «רענון» in this state**, because «רענון» beside «חידוש» is two Hebrew words a hurried reader will not tell apart); `A-idle` (mechanically identical, **one thing differs and it is why there are two states**: the body line names the cause and its own region); `A-401` / `A-403` (loop stopped, **cards cleared**, a reload affordance, **copy naming no role**); `A-trunc` (**the console never states the number** — `BOARD_TICKET_LIMIT` is server-only and `truncated` is on the wire precisely so it stays that way); `A-busy`; `A-ok` / `A-noop` (**identical, deliberately** — the outcome she wanted is the outcome that holds).

⚠ **C7 — the terminal DEFERS while a dialog is open.** Named test: with the intake `Modal` open and text typed, a tick answers 401 → **the dialog is still open, the draft is still there**, and the terminal panel is not rendered. Dismiss it → the terminal panel renders and takes focus. **Mutation: drop the `!dialogOpen` guard → red.**

### The code

`AtelierSection.tsx` — the section shell, the freshness row (`flex flex-wrap items-center justify-end gap-3 text-sm text-ink-muted`; `items-center`, never `items-baseline`, now that the line carries a 44 px control), the pause/resume `Button variant="ghost" size="md"`, the intake CTA `Button variant="primary" size="md"` with `fullWidthMobile={false}`, the cue `<p role="status" tabIndex={-1}>` **written only when its value changes** with `{{name}}` through **`isolateBidi`** (bare `<bdi>`, `FloorPanel.tsx:428`'s exact call) and **never `isolateLtr`**, the rail, the five sections, and the thirteen state branches.

**Bidi, per interpolation and not per string** (F57's F-11): `<bdi dir="ltr">` on **numeric** runs (`{{time}}`, `{{date}}`, `{{minutes}}`, `{{total}}`) via `isolateLtr`; **bare `<bdi>`** on Hebrew free text (`{{name}}`, `{{seamstress}}`, dress names, notes) via `isolateBidi` — **`dir="ltr"` on «מיכל לוי» reverses its words and looks deliberate**. `{{stage}}` and `{{band}}` are our own Hebrew vocabulary and need neither. **Every `*Aria` key interpolates plainly — an `aria-label` takes no markup at all.**

**No motion.** Nothing animates except the shipped `Button` spinner and the `Skeleton` pulse, both already frozen by `theme.css`'s global `prefers-reduced-motion` block. **No highlight, fade, tint or flash on a card that moved** — it would fire every five seconds on a shared board, and it draws the eye to *what changed* when the question this board answers is *what is late*. **This feature adds no motion rule because it adds no motion.**

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| the pause control | delete the button | the SC 2.2.2 tests **RED** — **and axe stays GREEN. That is the point** |
| the resume-at-base-interval reset | resume at the backed-off gap | the resume test **RED** |
| the cue's change guard | write the cue on every tick | the three-tick `MutationObserver` test **RED** |
| the live-region negative control | render the freshness line **inside** `role="status"` in the main fixture | the outside-the-region test **RED**, **and the control fixture must be GREEN — run both** |
| the terminal-defer guard (C7) | render the terminal unconditionally | the open-dialog-survives-401 test **RED** |
| `<ul tabIndex={0}>` | drop it | axe `scrollable-region-focusable` **RED** at ≥768 |
| the `aria-label` on a `<ul>` | drop it | the `getByRole("list", { name })` query **RED** |

- **Done when**: `make fe-test` + `make fe-build` green; **axe at zero violations**; `make qa-greps` byte-identical to the baseline; every mutation performed and restored.
- **Commit**: `feat(manage): the atelier board, its five named regions, stage rail and 2.2.2 pause control`
- **Implements**: D12, D15, D17, `design.md` §1/§4/§5/§6/§9, C7, C10.

---

## Task 12 — The card, its controls, and the two section-level `Modal`s (D16, D6, C3, C5, C6, C8, C9)
`frontend/apps/manage/src/components/AtelierSection.tsx`, `…/src/__tests__/AtelierSection.test.tsx`

### The failing tests first

**⚠ NOTHING ON THIS BOARD MUTATES ON `change`, and this is the one interaction rule a builder will get wrong by copying the obvious thing.**

- **`{ArrowDown}{ArrowDown}` on the skip `<Select>` calls `api.advanceStage` ZERO times**; activating «העברה» calls it **exactly once** with the selected stage. **The same pair for the assign `<Select>` and `api.assignTicket`.**
- ⚠ **The mutation is named and must red BOTH pairs: move the request back into the select's `onChange`.**
- **Why**: on Windows Chrome and Firefox a **closed** native `<select>` changes its value and fires `change` on **every arrow keypress**. A keyboard user on an `in_progress` card arrowing to «נמסר» would fire **three** advances — `qc`, `ready`, `delivered` — writing three timestamps, three `ATELIER_TICKET_STAGE_ADVANCED` audit rows, moving the card across three columns and firing the focus move three times, **before committing to anything**. Under D2 those stamps **are** the trail and under D4 each needs its own undo call to reverse. That is **WCAG 3.2.2 On Input (Level A)**, inside the AA bar pre-decided #38 makes legally binding, it falsifies this feature's own "fully operable with no pointer" criterion, and it would be **the first `<Select>` in this console to mutate on change** — every shipped one sets draft state and nothing else (`StaffSection.tsx:241`, `:375`).
- Each commit `Button` is `disabled` until its sibling draft is non-null.

**The control matrix, asserted AS COSMETICS** (F57's rule — the server's D3/D9/D10 checks are the control):
- «לשלב הבא» absent on a `delivered` card and on a seamstress's view of **another seamstress's** ticket.
- The skip pair renders **only when ≥2 later stages exist** — with exactly one it does what «לשלב הבא» already does, and a board that offers one act twice has to be read twice.
- «ביטול שלב» absent when the stage is `intake`.
- The assign **`Select` + «שיוך»** for elevated; a single **«לקחת» / «לשחרר»** for a seamstress.
- «עריכה» for elevated on any ticket; a seamstress on **her own** only.
- «מחיקה» **elevated only**, `variant="danger"`, behind a confirm `Modal`.
- ⚠ **A seamstress on a colleague's ticket sees the facts and NO CONTROLS AT ALL** — no disabled buttons, no lock glyph, no «אין לך הרשאה» line. A disabled control with no explanation is worse than an absent one; an explanation would teach the permission model on a screen she opens fifty times a shift to answer a question she did not ask; and it would be the client asserting a rule the server owns.

**«מחיקה» asks before it writes** — `api.deleteTicket` is **not called** until the confirm `Modal`'s confirm is activated. Its own test and its own acceptance line.

**Target size (C8):** one control of each kind on the **board** renders at the 44 px floor (`toHaveClass("min-h-11")` — the two `<Select>`s explicitly, because `Select.tsx` declares **no** min-height and `px-3 py-2 text-base` lands near 42); **no `size="sm"` anywhere in the tree** (a tree-wide assertion that nothing carries `min-h-9`). **The dialog's fields keep the shipped component heights, and that departure is recorded** — the legal bar is WCAG **2.0** AA, which has no target-size criterion at all, and `manage-restyle.md` bars overriding a `packages/ui` utility from the call site.

**The card's facts:**
- **Nothing is truncated, clipped, ellipsised or line-clamped.** A 60-character dress name wraps with `break-words` — *a board that abbreviates two garments into the same string is worse than a tall card*. A customer name is the same argument about a person. And **`notes` is the one that looks like it wants a clamp and is the one where a clamp does the most damage**: the note **is** the work order, and «עריכה» is refused to a seamstress on a ticket that is not hers, so a clamp would hide the instruction from precisely the person doing the work.
- **Overdue carries the WORD «באיחור»** in a `Badge variant="danger"` (`border-danger text-danger`), **plus** the due line escalating to `text-danger font-semibold` — **two text signals**, and the card itself gets **nothing**: no red border, no tint, no left rule, no icon. On a 60-card column a wall of red stops meaning anything. **An overdue DELIVERED ticket carries nothing** — it is history.
- **Exactly one `Badge` per card, and overdue owns it. The stage is NOT on the card** — it is the column heading, and repeating it is 295 px spent restating the region plus a second place to keep true.
- «לא משויך» as muted words; «תופרת שאינה פעילה» **from the wire's `assignable: false`**, not inferred from absence.
- `bandLabel`'s **«{{minutes}} דק׳» fallback** when a stored `effort_minutes` matches no current band — the visible consequence of D8's *minutes persist, never the label*.
- **C9**: the control stack lives in `<div className="mt-3 space-y-2">` inside `<Card className="space-y-1">`, so §2.1's `--space-3` separation is true as written. **`Card`'s `p-6` is not overridden**, and neither is `Badge`'s or `Button`'s.

**The intake / edit `Modal` (§7):**
- ⚠ **C3 — there is NO dress `Select`.** The free-text `dress_name` `Input` renders unconditionally for all three roles, and `dress_id` is `null` on every request. **State the reason in a source comment**: the only data source is `GET /manage/dresses`, gated owner + shift_manager (`catalog/router.py:57-61`) while intake admits a seamstress, paginated at 24 — and F41 renders no dress image, so `dress_id` has no reader on this surface.
- Create mode vs edit mode; **the customer is a static line in edit mode**, because *a ticket opened for the wrong bride is a delete, not an edit*.
- `due_date` is a native **`DateField`** (`<input type="date">`, the platform feature, no picker library) defaulting to **empty, never to today** — a due date is the one field a hurried user must not be able to accept by not looking at it. **No `min` attribute**: a past date is a **200** on the server and a **warning** here (#40's advisory rule — *a dress that was due yesterday is exactly the ticket a boutique most needs to open*, and a form that refuses it sends the seamstress to WhatsApp).
- `effort_band` `Select` defaults to **`one_hour`** — the middle-low band; `full_day` inflates every estimate in the boutique and `thirty_min` deflates it. **Its `<option>` labels carry the word AND the tenant-resolved minutes** («חצי יום · 240 דק׳»), because F41 ships no editor and F42 owns it — showing the number at the moment the estimate is made is what lets an owner discover on day one that the platform thinks her half-day is four hours. ⚠ **An `<option>` takes no markup**, so no isolation helper is available: the string is built so the numeric run is **bracketed by Hebrew on both sides**. A string *ending* in the number would put a neutral run at the paragraph edge and could reorder.
- `notes` is a `TextArea` with `showCount maxLength={500}` — **which is what makes "the board never truncates a note" honest**, by putting the length in front of whoever is writing it.
- **The returning-customer notice**: the moment the phone parses, «לקוחה קיימת — השם יעודכן ל…» beside the phone field, in `--color-warning-text`. `upsert` rewrites `customers.name` **unconditionally** (`customers.py:191-192`) and F53 now renders that name on a screen of its own, so a seamstress typing «מיכל» for «מיכל לוי» must not do that invisibly. **No new endpoint** — intake echoes the resolved `customer_name`.
- **Success**: the `Modal` closes and **native `<dialog>` returns focus to the trigger by itself**, so **no focus code is written here at all** — stated so the fourth `usePoll` consumer does not re-derive it. `atelier.cue.created` is announced, **naming the bride**, because focus went back to «כרטיס חדש» and **not** to the new card.
- **C5** — a server error mapping to no field renders **one alert inside the dialog, above the footer**, `role="alert"` and focused (`atelier.form.error.server`) — **never a Toast behind a modal and never a message the dialog dismisses itself to show**. This is where the horizon 400 and the `dress_id` 404 land.

**C6 — both `Modal`s mount at SECTION level**, siblings of the column grid (`StaffSection.tsx:411` is the shipped instance, a sibling of the `</Card>` at `:409`). Their open state and draft live in `AtelierSection`'s state keyed by `ticketId`. **Named test**: with a `Modal` open, drive three ticks that reorder and remove cards, and assert the dialog is **still mounted with its draft intact**.

**C5 — the error mapping.** `TICKET_STAGE_CONFLICT` → `stageConflict`; `TICKET_ALREADY_ASSIGNED` → `alreadyAssigned`; `NOT_FOUND` → `notFound` (**not terminal** — a ticket vanishing is a fact about the ticket); **everything else → `atelier.error.rejected`**. **Named test**: a mutation rejected with an unmapped code renders `atelier.error.rejected` and **never the response's `message`**. **Mutation: replace the `default:` with `errorMessage(error)` → red.** This is what structurally guarantees `main.py`'s English 400 body can never reach a Hebrew console.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| the select→draft→commit split | move the request into `onChange` | **BOTH** `{ArrowDown}{ArrowDown}` tests **RED**. If only one reds, the other select was missed |
| the delete confirm | call `api.deleteTicket` from the trigger | the asks-before-it-writes test **RED** |
| the `default: atelier.error.rejected` branch | fall through to `errorMessage(error)` | the unmapped-code test **RED** |
| the section-level `Modal` mount | move it inside the `<li>` | the dialog-survives-three-ticks test **RED** |
| the `assignable: false` branch | infer the inactive assignee from absence | the «תופרת שאינה פעילה» test **RED** |
| `break-words` on notes | add `line-clamp-3` | the no-truncation test **RED** |

- **Done when**: `make fe-test` + `make fe-build` green; **axe at zero violations**; `make qa-greps` byte-identical; every mutation performed and restored.
- **Commit**: `feat(manage): the ticket card, its commit-on-click controls and the two section-level dialogs`
- **Implements**: D6, D16, `design.md` §2/§3.1/§3.2/§7, C3, C5, C6, C8, C9.

---

## Task 13 — The focus moves: one unconditional capture, five destinations, five non-vacuous tests (D16, C4, C12)
`frontend/apps/manage/src/components/AtelierSection.tsx`, `…/src/__tests__/AtelierSection.test.tsx`

**This task is separated because these assertions carry the whole legal load and must not be diluted into a bigger commit.** ⚠ **A successful advance MOVES the card to a different column, so the tapped control unmounts and the browser drops `document.activeElement` to `<body>`. On this surface that is not a side effect — IT IS WHAT THE FEATURE DOES.** This bug class has shipped **three times** in this repo (F56 on the storefront, F34 on the board, F57 on the floor panel) and **axe walked past it every time, because axe cannot see a focus move that never happened.**

**Every rule is keyed on STATE, never raised inside the handler** — the destination node does not exist yet when `setState` runs (`FloorPanel.tsx:220-236` is the shipped shape).

### The mechanism (C4) — one capture replaces the deck's five-row table

- Every per-card control carries **`data-control="advance|skip|skipCommit|assign|assignCommit|claim|release|undo|edit|delete|alert"`**; every `<li>` carries **`data-ticket-id`**.
- **Before applying an incoming payload** — `FloorPanel.tsx:107`'s moment, *"decided BEFORE the new list is applied — the only moment both lists exist"* (`:259`) — if `document.activeElement.closest("[data-ticket-id]")` matches, record `{ ticketId, control, columnStage }`. **Unconditionally. No comparison against the incoming list.**
- **After paint**: if and only if **`document.activeElement === document.body`** — the repaint dropped focus rather than the user moving it — restore in order: (1) the same `data-control` on the same `data-ticket-id`; (2) any control on that ticket; (3) the **new** column's `<h3 tabIndex={-1}>`; (4) the **recorded** column's `<h3>`.

**Why unconditional beats the deck's stage comparison**: the critic's sixth case has no stage change at all — a seamstress tabbed onto «לקחת» on an unassigned card, a colleague claims it, and the next tick renders that card **with zero controls for her** (§2.3). The stage did not change, so a stage-keyed capture does not fire; no alert, so `reclaimFocusRef` does not fire; the ticket is still in the payload, so `departingCardHoldsFocus` does not fire. **The `document.body` guard makes the unconditional version free**: if focus is still on something real it does nothing, and it is strictly less code than any predicate.

### The five named, non-vacuous tests

⚠ **Each asserts `document.activeElement` IS the expected node — never merely that the node exists.** F57's shipped note records a success-path focus test that was **vacuous** because jsdom does not blur a disabled element, so the whole restore effect could have been deleted with the suite green.

| # | Trigger | Destination | Mutation → RED |
|---|---|---|---|
| 1 | **Advance / skip / undo succeeded** | the **same ticket's** control **in its new column**, via the id-keyed ref map (a lookup, not a search — and focusing it scrolls it into view natively, so the stacked layout needs no scroll code) | delete the success-path focus line |
| 2 | **Any mutation failed** (409 / 404 / 400) | the **in-card alert** (`role="alert" tabIndex={-1}`, `text-danger`) | **move it into the `catch` as a `.focus()`.** The failure path is the one that gets forgotten: F34's success path compensated and its catch path restored nothing, and that was a Level A defect found in review and not in CI |
| 3 | **A successful poll unmounts the focused in-card alert** | back to that card's own control (`reclaimFocusRef`, `FloorPanel.tsx:118-131`) | delete the reclaim. **Easy to miss because the alert is cleared about five seconds later with NO user action at all**, and the departing-card rescue cannot cover it — the card is still in the list |
| 4 | **A successful DELETE** | the departing card's **own** column `<h3 tabIndex={-1}>` | delete the heading rescue. The card is gone entirely, so the ref map has nothing to look up. Without it, deleting the focused card drops focus to `<body>` **on the single most destructive action in the feature** |
| 5 | **A POLL moved or de-controlled the focused card, because a COLLEAGUE acted** | the same control on the same ticket, else the new column's `<h3>`, else the old column's `<h3>` | **delete the capture line.** ⚠ **Two fixtures, both required**: (a) a colleague **advances** the focused card → it unmounts from one `<ul>` and mounts in another; (b) a colleague **claims** the unassigned card she is focused on → the card stays put and her «לקחת» disappears. **Test (b) is the case a stage-keyed capture would miss** and is the reason the capture is unconditional |

**Plus the axe pass** — over the loaded board, the empty board and the open dialog. ⚠ **Explicitly not sufficient**, and the acceptance line says so: axe has **no SC 2.2.2 rule** and **cannot see a focus move that never happened**. These five tests and Task 11's pause assertions are the sole automated coverage of a **legal** requirement, and neither set may be dropped as redundant with the axe row.

**And two assertions of the same class of invisible**, already written in Task 12 and re-run here as a set: the two `{ArrowDown}{ArrowDown}` pairs, and «מחיקה» calling nothing until the confirm.

**The keyboard sweep**: every advance, skip, undo, assign, edit and delete is reachable by keyboard, and **no drag handler exists anywhere in the tree** (`grep -c "onDragStart\|draggable\|onDrop" AtelierSection.tsx` is 0, asserted as a source read the way `test_frontend_constant_parity.py` reads source). **A kanban is a drag-shaped idea and this one ships with no drag affordance at all** — every accessible DnD is a keyboard alternative bolted onto a gesture, so the button path gets built either way, and WCAG 2.5.7 requires the single-pointer alternative regardless. **The alternative IS the interface.**

- **Done when**: `make fe-test` + `make fe-build` green; **axe at zero violations**; **all five focus mutations performed, each observed red, each restored**; `make qa-greps` byte-identical.
- **Commit**: `feat(manage): the five focus destinations a repaint or a mutation can strand`
- **Implements**: D16, `design.md` §3.3 / F-1, C4, C12.

---

## Task 14 — Rebase, renumber, the gates, and the run report
No files.

Run the shipping checklist and the full gate below, report what ran and what passed, and carry forward:

- **The migration number.** State the number the branch was **built** at, the number it **shipped** at, and the `alembic heads` output that decided the second. Today's build number is `head + 1` from `0017`.
- **Risk 8 — LEGALLY SENSITIVE, and it is the one item the run report must not compress.** `alteration_tickets` is an **e9 record class** and `notes` may hold body measurements — the most intimate data this platform will ever carry. **Retention: 7 years, measured from `delivered_at`, or from `created_at` for a ticket never delivered** — same number and same basis as bookings (pre-decided #10), because a shorter clock would leave a booking describing an alteration whose own record had been purged. **FLAGGED FOR COUNSEL CONFIRMATION at the F21 audit, exactly as #10 flags every number.** Scope for F20's PII scrub: `notes`, and the `customer_id` link scrubbed with the customer it points at; `dress_name`/`dress_size` are catalog facts, not personal data. `assigned_staff_user_id` keys on the **id** and never a name, so #34/#35's offboarding scrub cannot make F44's per-seamstress report lose rows. **Owner: the user's lawyer confirms the number; the platform only enforces the clock.**
- **Risk 4 — the effort-band mapping has a reader and no writer.** A boutique whose shifts are six hours cannot re-tune «חצי יום» without `psql` until F42 ships the settings block. **The writer is FOUR edits, not one**, and F42's spec must size it as such: a third keyword on `TenantsRepository.merge_settings` (which today builds its patch from `profile` and `toggles` alone, `tenants.py:69-75`), an `atelier` field on `SettingsResult` **and** in `_settings_result` (`boutique/service.py:85-89`), the `UpdateSettingsRequest` `ForbidExtraModel`'s `atelier` block, and its validator. **Mitigated in F41 by the picker showing the resolved minutes** (`atelier.bandOption`), so an owner discovers a wrong mapping on day one rather than in F42's load bars three weeks later.
- **Risk 5 — a boutique whose owner sews cannot be assigned a ticket.** D9 refuses a non-seamstress assignee so F42's load bars cannot be blind to real work. One person holds one role, so the owner must either take `seamstress` (losing owner-only staff CRUD, terms and gateway) or leave her own work unassigned. **A real ceiling for a two-person pilot.** Owner F42.
- **Risk 12 — the seamstress-only check is a write-time NUDGE, not an invariant.** `StaffUsersRepository.update` rewrites `role` unconditionally (`staff_users.py:114`) and `soft_delete` retires her, both with no knowledge of this table. F41 makes the state **visible** (`assignable: false`, «תופרת שאינה פעילה») rather than correct. Owner F42.
- **Risk 9 — what F42 reads, named exactly**, so its simplified model is an addition and not a rewrite: `SUM(effort_minutes) … WHERE delivered_at IS NULL GROUP BY assigned_staff_user_id`; `NULL` as a real bucket **plus a second anomalous bucket for a non-assignable assignee**; `staff_users.weekly_capacity_hours` in **F42's own migration**; the `seamstresses[]` array it extends with `weekly_capacity_hours` and `assigned_minutes`; `AtelierService.assign` gaining an advisory **flag** and never a refusal; and the `(tenant_id, assigned_staff_user_id) WHERE deleted_at IS NULL AND delivered_at IS NULL` index it buys. ⚠ **That claim does NOT extend to split and expedite**, which add columns in F42's migration.
- **Risk 3 — F29 is handed the per-tick figure rather than left to discover it**: **≈11 round trips, 6 statements, 3 pool checkouts** per tick per device on the atelier screen (D12's table, F34's D3 method). It **replaces rather than adds to** F57's board-screen number, because the console renders one section at a time. `tenancy/resolver.py:8-9` records that `tenants.by_slug` is uncached per request and *"caching is deliberately deferred to E5"* — still the single cheapest lever.
- **Risk 10 — no E2E covers the poll loop, and there are now THREE of them in the console.** All three are unit-tested with fake timers against a mocked `api`; none is exercised against a real backend, and the interaction most likely to differ in reality — a slow tick on boutique wifi while a mutation is in flight — is exactly what fake timers model least faithfully. **No E2E ships here**, and the reason is F34's and F57's verbatim: the console's entire e2e surface is two login-screen tests because `vite preview` runs with no backend (`e2e/a11y.spec.ts:10-13`). **F58 owns the `/manage/**` interception harness.** Recorded rather than silently skipped.
- **`design.md` F-9 — the `poll.*` rename is now DUE and is still declined.** Ten strings are byte-identical across `board.*`, `floor.*` and `atelier.*`. F57's F-9 named this PR as the trigger; the reason for declining has not changed (it would edit two components that must pass unedited). **Owner: team. Trigger: F37 or F59, as a standalone i18n PR touching no component logic.**
- **`design.md` F-4 — an accepted a11y residual.** A screen-reader user whose focused card is moved by a colleague hears the same control re-announced and never learns why: C4's capture moves focus correctly, but D11 forbids the poll writing into the live region, and the control's `aria-label` is byte-identical before and after. **Accepted, because the alternative is worse** — a bounded exception would be the first crack in a rule three surfaces now depend on. Cheap remedy if a pilot hits it: exactly that bounded exception, at most one announcement per remote move of one card, never per tick.
- **Risk 6 / Risk 7** — no un-delete, no multi-stage undo, and the audit rows are still write-only. `previous_stamp` is the **only surviving copy of a destroyed stage timestamp** with no way to read it without `psql`, which matters more here than in F15/F34/F51/F57 because the five timestamps are this feature's entire history.
- **Spec Conflict 7** — `CustomersRepository.upsert`'s docstring asserts a precondition F41 does not meet. **It should gain a sentence naming the atelier's savepoint path** so the next caller is not misled by a precondition that is now conditional. Not done in this PR (it would put a booking-path file in an atelier diff); recorded.

No push, no PR from this task — the orchestrator owns review and shipping.

### Shipping checklist — run in this order, top to bottom

1. **`git status --short` is clean** and `git log -p -- backend/tests/conftest.py` shows **no F41 commit**. (There is nothing to revert — the escape hatch is shipped — but assert it anyway.)
2. **`git show --stat` on every commit** confirms the **lowercase** pathspecs landed.
3. **No lower-numbered migration is still unmerged.** F33 and F36 are both in flight; whichever lands first moves the head.
4. `git fetch origin && cd "…/Backend" && uv run python -m alembic heads` **on a checkout of `origin/main`**. Note the number.
5. **Renumber the migration to head + 1** — three edits: the filename, the `revision` literal, the `down_revision` literal. **Amend the migration commit** (it is the branch tip by Task 1's instruction).
6. **Rebase onto `origin/main`.** Re-run `alembic heads` **on the rebased branch** and confirm a **single** head. F19's fast guard (`test_migrations.py:37-48`) does this in `make test` too.
7. **Re-run the full db suite on the rebased branch** — `dropdb f41_test && createdb f41_test`, then `pytest -m db`.
8. **Full local gate, all six targets green.**
9. **`make qa-greps` output is byte-identical to the Task 9 baseline.** Diff it.
10. `grep -rn "onDragStart\|draggable\|onDrop" frontend/apps/manage/src/components/AtelierSection.tsx` returns **nothing**.
11. `grep -n "atelier" frontend/apps/manage/vite.config.ts` returns the segment **and** the corrected comment counts.
12. Open the PR. The three gating jobs are `Backend (lint, types, tests)`, `Frontend (lint, types, build)`, `Frontend E2E (Playwright + axe)`.

- **Commit**: none (the renumber is an amend).

---

## Verification — the full local gate sequence

```
export TEST_POSTGRES_SUPERUSER_URL="postgresql+asyncpg://mrwen@127.0.0.1:5432/f41_test"

make lint      # Backend: ruff check . && ruff format --check . && mypy app tests
               #   + Frontend: pnpm -r lint && pnpm -r typecheck
               #   + bash Frontend/scripts/qa-greps.sh
make test      # Backend: pytest -m "not db" -q   (includes F19's single-head guard)
dropdb -h /tmp -U mrwen f41_test; createdb -h /tmp -U mrwen f41_test
cd Backend && uv run pytest -m db -q --ignore=tests/test_media_upload_s3.py
make fe-test   # Frontend: pnpm -r --if-present test
make fe-build  # Frontend: pnpm -r build
make e2e       # Frontend: pnpm -r build && playwright install chromium && pnpm e2e
```

**Green looks like:**

- **`make lint`** — ruff clean, `ruff format --check` clean, **mypy zero errors over `app` and `tests`**, `pnpm -r lint` and `pnpm -r typecheck` clean across all four workspace packages, and `qa-greps.sh` **exit 0** printing **exactly the Task 9 baseline**.
- **`make test`** — `test_atelier_api.py`, `test_atelier_service.py`, `test_atelier_stages.py`, `test_atelier_bands.py`, `test_atelier_board.py` green; **`test_staff_role_gating.py` green with its restructure**; **`test_spa_serving.py` green with the `vite.config.ts` edit**; `test_frontend_constant_parity.py` passes **unedited** (no client constant mirrors a server bound); the three `db`-marked modules **collected and deselected**; the single-head guard green. ⚠ **Two `test_config.py` failures are always false locally** — `Backend/.env` leaks `MEDIA_BUCKET`. Do not chase them.
- **the db suite** — the captured baseline **plus** F41's new cases in `test_migrations.py`, `test_atelier_db.py` and `test_atelier_isolation.py`, all green. `test_media_upload_s3.py` is ignored (MinIO; F41 touches no S3).
- **`make fe-test`** — `AtelierSection.test.tsx`, `Nav.test.tsx`, `i18n.test.ts` green; **axe at zero violations on the loaded board, the empty board and the open dialog**; **every mutation-check in Tasks 11–13 performed and restored**. `FloorPanel.test.tsx`, `BoardSection.test.tsx` and `StaffSection.test.tsx` pass **unedited** — that is an assertion, not a hope.
- **`make fe-build`** — both apps build; no unused-import or unused-variable TS error.
- **`make e2e`** — existing specs unchanged. **F41 adds none**, per Risk 10.
- **CI additionally** — the same db suite against Testcontainers, where the captured literals are re-read off the CI server rather than off the local one. ⚠ **A first CI red on a test bug is budgeted** (`.memory/boutique-ci-first-run-surprises.md`); check `continue-on-error` on the job before believing it.

---

## What a local run CANNOT prove

The shipped harness closes almost the whole gap. What is left is small and is named rather than hoped over:

| Task | The local run proves | CI-only, or nothing proves it |
|---|---|---|
| 1 | the migration, the round trip, the captured CHECK and index literals, the RLS/GRANT block — **all of it, against real Postgres 16.14** | that the deparsed literals are **byte-identical on the CI server's Postgres build**. They should be — same 16.x deparser — and the assertion **re-reads** rather than transcribes, so a difference is a red test and not a silent pass |
| 3, 7 | the writes, the ordering, and all six mutations against real transactions | that the interleave holds under CI's container timing. The harness does not depend on timing — it depends on `tenant_session`'s commit-on-exit — so this is low risk and is stated rather than assumed |
| 8 | the isolation suite in full, **including the deliberate vacuity check** | the same on CI's container-superuser / app-role split |
| 11–13 | every focus destination, every state, SC 2.2.2, the live region, axe — **in jsdom** | ⚠ **jsdom has no layout engine**, so every 44 px claim is a **class** assertion and never a measurement; ⚠ **jsdom does not blur a disabled element**, which is precisely how a vacuous focus test shipped once — hence "assert `document.activeElement` IS the node"; ⚠ **the `<select>` arrow-key behaviour the 3.2.2 rule exists for is a Windows Chrome/Firefox behaviour jsdom does not reproduce** — the test asserts the *architecture* (no request from `onChange`), which is the only thing a unit test can pin, and the browser behaviour is the *reason* |
| — | — | **the poll loop against a real backend.** Three loops now, none e2e-covered; a slow tick on boutique wifi while a mutation is in flight is exactly what fake timers model least faithfully. **F58** |
| — | — | **RTL rendering.** The design deck's diagrams are drawn LTR for legibility and the shipped section is RTL. A builder implementing the drawn order ships a **mirrored board that passes axe, passes every named vitest assertion, and reads backwards to the only users who will ever see it.** No automated check catches this; the rail is where it matters most, because a pipeline drawn in the wrong direction says the work flows the wrong way |

**Task 4 is the first milestone** (the whole service contract with no Postgres) and **Task 5 is the second** (the whole HTTP surface, both new codes and the dev proxy, with no Postgres).

---

## Task-by-task file manifest

| Task | New (✚) | Modified |
|---|---|---|
| 0 | — | `.planning/plans/alteration-tickets.md`, `.planning/specs/alteration-tickets.md`, `.planning/design/screens/alteration-tickets/design.md`, `…/copy.md` |
| 1 | `backend/migrations/versions/00NN_alteration_tickets.py`, `backend/app/models/alteration_ticket.py` | `backend/tests/test_migrations.py` |
| 2 | `backend/app/atelier/__init__.py`, `…/stages.py`, `…/validation.py`, `backend/tests/test_atelier_stages.py`, `backend/tests/test_atelier_bands.py` | `backend/app/models/constants.py` |
| 3 | `backend/app/db/repositories/alteration_tickets.py`, `backend/tests/test_atelier_db.py` | — |
| 4 | `backend/app/atelier/schemas.py`, `…/service.py`, `backend/tests/test_atelier_service.py`, `backend/tests/test_atelier_board.py` | `backend/app/models/constants.py` |
| 5 | `backend/app/atelier/router.py`, `backend/tests/test_atelier_api.py` | `backend/app/main.py`, **`frontend/apps/manage/vite.config.ts`** |
| 6 | — | `backend/tests/test_staff_role_gating.py` |
| 7 | — | `backend/tests/test_atelier_db.py` |
| 8 | `backend/tests/test_atelier_isolation.py` | — |
| 9 | — | `frontend/apps/manage/src/i18n/he.ts`, `…/i18n/ar.ts`, `…/src/__tests__/i18n.test.ts` |
| 10 | `frontend/apps/manage/src/lib/stages.ts` | `…/src/api.ts`, `…/src/App.tsx`, `…/src/__tests__/Nav.test.tsx` |
| 11 | `frontend/apps/manage/src/components/AtelierSection.tsx`, `…/src/__tests__/AtelierSection.test.tsx` | — |
| 12 | — | `…/src/components/AtelierSection.tsx`, `…/src/__tests__/AtelierSection.test.tsx` |
| 13 | — | `…/src/components/AtelierSection.tsx`, `…/src/__tests__/AtelierSection.test.tsx` |
| 14 | — | — (the renumber is an amend) |

**NEVER MODIFIED, and that is an assertion the review should check:**
`backend/tests/conftest.py` · `backend/tests/test_frontend_constant_parity.py` · `backend/tests/test_spa_serving.py` (it is the guard; `vite.config.ts` is what changes) · `backend/tests/test_tenant_isolation.py` (its RLS walker picks the new table up for free) · `backend/app/db/repositories/customers.py` · `backend/app/db/repositories/staff_users.py` · `backend/app/floor/**` · `backend/app/catalog/**` · **`frontend/apps/manage/src/lib/usePoll.ts`** (three shipped callers — any edit is a review stop) · `frontend/apps/manage/src/components/FloorPanel.tsx` · `…/BoardSection.tsx` · `…/StaffSection.tsx` · `frontend/packages/ui/**` (zero new components, zero new variants) · `frontend/scripts/qa-greps.sh` · `frontend/e2e/**`.

---

## Testing plan → spec acceptance criteria

| Spec criterion | Where |
|---|---|
| The table, five `TIMESTAMPTZ NULL` stamps, the partial index, the `updated_at` trigger, forced RLS | `test_migrations.py` (db) + `test_tenant_isolation.py` (db, **unedited**) |
| The `effort_minutes` CHECK and the index pinned **byte-identical from CAPTURED definitions**; no unique index | `test_migrations.py` (db) — the row that fails if someone re-adds `UNIQUE` |
| The migration up **and down** | `test_migrations.py` (db, **last in the file**, `try/finally`) |
| `stage_of` total, rightmost-stamp, `intake` floor — **all 32 combinations** | `test_atelier_stages.py` (fast, pure) |
| The predicate builder's later-columns clause for each of five targets | `test_atelier_stages.py` (fast) |
| Bands resolve per band against platform defaults; partial / negative / string / over-bound all fall back | `test_atelier_bands.py` (fast) |
| The four-outcome mapping of advance, undo and claim — **including the two branches an earlier draft called unreachable, and NO branch returning `None`** | `test_atelier_service.py` (fast) + `test_atelier_db.py` (db, forced interleave) |
| D4's skip-then-stale-undo sequence is a **409**, not a 200 | `test_atelier_service.py` (fast) |
| Undoing `intake` is a 400 | `test_atelier_service.py` (fast) |
| A **past** `due_date` is a 200 on create and update; beyond 730 days is a 400 | `test_atelier_service.py` + `test_atelier_api.py` (fast) |
| `overdue` iff `due_date < today_jerusalem` **and** `delivered_at IS NULL`, against a frozen clock | `test_atelier_board.py` (fast, pure) |
| The delivered window, the 500 cap, `truncated`, and `due_date, created_at, id` ordering | `test_atelier_board.py` (fast) + `test_atelier_db.py` (db, **three tickets, one `due_date`, one transaction**) |
| `seamstresses[]` is a **UNION** carrying a retired/re-roled assignee with `assignable: false` | `test_atelier_board.py` (fast) |
| The seamstress's per-verb asymmetry — advances an **unassigned** ticket (200) but cannot `update` one that is not hers (403, generic body) | `test_atelier_service.py` (fast) |
| The repository is **never called** on the pure-role refusals | `test_atelier_service.py` (fast) |
| A non-seamstress assignee is a 400; an unknown/archived/foreign `dress_id` is a 404 | `test_atelier_service.py` (fast) |
| One audit row per real write, **none on any no-op**; `UPDATED` carries key **names**; the undo carries `previous_stamp` | `test_atelier_service.py` (fast) + `test_atelier_db.py` (db, **capture-before-write mutation**) |
| All three roles reach all seven routes except `delete`, which admits two | `test_atelier_api.py` (fast, `ATELIER_ROUTES`) |
| **Per-role set equality over `effective = intersection(gates)`** — reception and sales_assistant reach exactly the three floor routes; seamstress reaches those plus the **six non-`delete`** atelier routes | `test_staff_role_gating.py` (fast, **restructured**) |
| `SPEC_ERROR_CODES` set-equal, adding exactly the two new members | `test_atelier_api.py` (fast) |
| CSRF fences the six POSTs and not the GET | `test_atelier_api.py` (fast) |
| The dev proxy's segment set equals the live `/manage` route table's | `test_spa_serving.py` (fast, **shipped guard, unedited** — `vite.config.ts` is what changes) |
| Tenant B can neither read, advance, assign, update nor delete A's ticket; every attempt is a **404 indistinguishable from missing**; a context-free connection sees zero rows | `test_atelier_isolation.py` (db, **app role only**, with the deliberate vacuity check) |
| Two concurrent advances leave one stamp and the loser renders the **database's** stage | `test_atelier_db.py` (db, forced interleave, **`populate_existing` mutation**) |
| Two seamstresses claiming one ticket leave one owner and one 409 | `test_atelier_db.py` (db, forced interleave) |
| Two concurrent intakes for one new phone create **one** customer and two tickets | `test_atelier_db.py` (db, **its own named seam** — session ordering alone cannot produce it) |
| An elevated reassign race renders the **database's** assignee | `test_atelier_db.py` (db — the row that stops `_refreshed` being re-scoped) |
| The thirteenth nav row; owner twelve; shift manager `.slice(0, 10)`; **a seamstress sees «הצוות בקומה» then «תפירה»** | `Nav.test.tsx` (vitest) |
| **`HE_F41` is spread into `HE`** (`toContain("nav.atelier")`) | `i18n.test.ts` — *without it the `ar` parity guard and both register guards silently skip every key* |
| Every `atelier.*` key resolves in `he` and is non-empty in `ar`; every `STAGE_LABEL_KEY` value resolves; **all aria names contain their visible labels**; no value names a retry interval; `accessEnded` names no role; nothing matches `/נשלח\|תישלח\|בדרך/` | `i18n.test.ts` (vitest) |
| Five columns as **named lists inside named regions** | `AtelierSection.test.tsx` |
| **SC 2.2.2** — pause stops the loop, resume fetches early at the base gap, the idle stop fires and names its own region | `AtelierSection.test.tsx` — **the sole automated coverage; axe has no rule for it** |
| The announced region does **not** change across several consecutive ticks with the cue populated; **does** change on an advance and a pause | `AtelierSection.test.tsx` (`MutationObserver`, three ticks) |
| After an advance to `qc`, `getByRole("status")`'s **textContent** contains the bride's name **and «בקרה»** — the cue's TEXT, not merely its change | `AtelierSection.test.tsx` |
| The freshness line is outside every announced region — **with the negative control** | `AtelierSection.test.tsx` |
| **`{ArrowDown}{ArrowDown}` calls the API ZERO times** on both selects; the commit buttons call it exactly once | `AtelierSection.test.tsx` — mutation: move the request into `onChange`, **both** red |
| «מחיקה» calls nothing until the confirm is activated | `AtelierSection.test.tsx` |
| **The five focus destinations**, each asserting `document.activeElement` **IS** the node | `AtelierSection.test.tsx` — *the bug class has shipped three times and axe walked past it three times* |
| Overdue carries the word «באיחור», not colour alone; one `Badge` per card | `AtelierSection.test.tsx` |
| One control of each kind at the 44 px floor; **no `size="sm"` anywhere**; **no drag handler anywhere** | `AtelierSection.test.tsx` |
| An unmapped error code renders `atelier.error.rejected` and never the server's English message | `AtelierSection.test.tsx` (C5) |
| A `Modal` survives three ticks that reorder and remove cards; a terminal defers while it is open | `AtelierSection.test.tsx` (C6, C7) |
| axe: zero violations — **explicitly not sufficient** | `AtelierSection.test.tsx` |

---

## What could go wrong in review

Every item here is a **recorded ruling**. A reviewer who raises one should find the reasoning rather than file a finding.

1. **"The plan says there is no conftest patch, but the prompt and the F33 plan both describe one."** Verified: `TEST_POSTGRES_SUPERUSER_URL` was **committed to `main` by F19 (`3a70600`)** with a 25-line docstring. `git status` on `backend/tests/conftest.py` is clean. There is nothing to patch and nothing to revert.
2. **"`test_the_floor_roles_reach_exactly_the_floor_routes` was edited, and F57's Risk 1 forbids it."** **D10, and doing this is COMPLIANCE with Risk 1, not a reversal.** Risk 1 forbids relaxing it **to a subset check**. The restructure keeps an exact set equality, keeps it derived from the live route table, keeps the lost-gate detection and keeps the wide-gate detection — and drops only the assumption F41 makes false, that the three floor roles move as a block. The per-role table makes every future divergence a deliberate, reviewed edit.
3. **"`assertion 2` (`partial`) was deleted."** **C1.** Its model *is* the assumption F41 falsifies, and its intent is absorbed: "admits only some of them" is now expressible only as a row naming a route the table does not, which is assertion 1. Deleting it while adding three set equalities is strictly stronger. The `:248` docstring was rewritten in the same edit so nobody meets a stale "never relax this" above it.
4. **"`ATELIER_DELETE` is split out of the seamstress's row — that looks like tidiness."** **It is the opposite.** The walker classifies on `frozenset.intersection(*role_sets)` (`:279`) and `delete` carries a per-route `require_role(OWNER, SHIFT_MANAGER)`, so its effective set is `{owner, shift_manager}`. A row naming it would **red a correct build** on the one test Risk 1 declares untouchable — the worst possible place for a builder to be guessing. Spec Conflict 12.
5. **"The intake dialog has no dress picker and the spec's D6 describes one."** **C3.** Its only data source is `GET /manage/dresses`, gated **owner + shift_manager** (`catalog/router.py:57-61`) while F41's intake admits a **seamstress** — so a seamstress tapping «כרטיס חדש» would hit a 403, and routed through `poll.fail` that 403 is **terminal** and blanks her whole board for opening a dialog. It is also silently capped at 24 rows. And F41's card **renders no image**, so `dress_id` has no reader on this surface at all. The server path is unchanged and its callers are F43 and a later elevated prefill.
6. **"There are FIVE focus destinations and D16 names four."** `design.md` **F-1** plus the critic's sixth case. **C4 replaces the whole table with one unconditional capture** guarded on `document.activeElement === document.body` — which is less code than any predicate, covers the colleague-advances case *and* the colleague-claims-and-her-controls-vanish case, and restores the control she was actually on via `data-control`.
7. **"The client maps every unmapped error code to one string."** **C5.** `main.py:795-799` returns `str(exc)` — an **English** developer string — and D13's 400 row (*non-seamstress assignee*) is reachable whenever F51 re-roles somebody between a tick and a tap. A `default:` branch structurally guarantees no English body ever reaches a Hebrew console, including from codes a *later* feature adds. A per-code string would leave the next one uncovered.
8. **"The board is two columns, not five."** **`design.md` F-2, and it is arithmetic.** `ConsoleShell` caps content at 720 px in **three** places (`:46`, `:56`, `:84`) → **128 px per column**, and a `Button size="md"` reading «לשלב הבא» is wider than that. Lifting the cap is a console relayout (the header and nav carry it too), its natural owner is **F42's capacity matrix**, and the stage rail is what delivers the pipeline overview five 128 px columns never could.
9. **"The dialog's fields are under 44 px and D17 says 44 is the floor for every control."** **C8, recorded not silent.** The legal bar is WCAG **2.0** AA, which has **no target-size criterion at all** (2.5.5 is 2.1 AAA, 2.5.8 is 2.2 AA); `manage-restyle.md` bars overriding a `packages/ui` utility from the call site; and every shipped console dialog runs at the component height. **The board's controls — the ones under a thumb — all carry the floor, and `size="sm"` is barred tree-wide.**
10. **"`atelier.stageCount` uses `{{total}}` and the obvious name is `{{count}}`."** **`design.md` F-12.** `count` is i18next's plural-resolution trigger and this string renders **ten times per paint**. It works today and is one library upgrade, one `pluralSeparator` change or one `returnObjects` edit away from not.
11. **"Ten strings duplicate `board.*` and `floor.*` — why not a shared `poll.*`?"** F57's **F-9** predicted this PR as the trigger and the rename is **still declined**, for the reason that has not changed: it would edit `BoardSection`'s and `FloorPanel`'s i18n, and both components must pass **unedited**, which is the only thing separating a faithful fourth `usePoll` consumer from a subtly different one. Owner and trigger are now named rather than deferred again.
12. **"`asyncio.gather` would be simpler than the nested-session harness."** It does not **order** two transactions, so the loser most often loads after the winner commits, its in-memory instance is already correct, and the zero-row branch goes green **without the mechanism ever being exercised**. That is the vacuity Task 7 exists to prevent, and it is why every race names its exact mutation.
13. **"Race #4's harness looks over-engineered."** It is the only shape that can produce the failure. `upsert` is read-then-insert **inside one call**, so session ordering gives only a hang or a test that passes with the savepoint deleted. **A green test that proves nothing is worse than no test** — so the seam ships, or the mechanism and the test are cut together.
14. **"axe passes, so the a11y work is done."** axe has **no SC 2.2.2 rule** and **cannot see a focus move that never happened** — the class this repo has shipped three times. The pause assertions and the five focus tests are the sole automated coverage of a **legal** requirement (IS 5568 / WCAG 2.0 AA), and neither set may be dropped as redundant with the axe row.
15. **"The migration is numbered `0018` and LOOP-STATE once said something else."** LOOP-STATE's own MIGRATION CHAIN block records that the grid moved **three times in one day** and that *"not one of the four fixed numbers this file originally assigned survived contact."* The plan states a **rule** — build at head+1, migration last, renumber at rebase, verify one head — and no number is authoritative except `alembic heads` at the moment of the rebase.

---

## Out of scope (unchanged from the spec, the decks and the scope fence)

Capacity, load bars, overload flags, balanced assignment, `weekly_capacity_hours` — **F42** · split load and expedite, and their two columns and two audit actions — **F42's own migration** · the effort-band settings editor (four edits, Risk 4) — **F42** · lifting `ConsoleShell`'s 720 px cap — **F42** · every index F41 declines to buy — **the feature that measures the query** · fitting appointments and `bookings.alteration_ticket_id` — **F43** · a dress picker and any `api.listDresses` call — **F43 or a later elevated prefill** · the shop-floor board, throughput analytics and median time-in-state — **F44** · a `status` enum, an event table, per-transition reason codes — **#39 and the ATELIER ruling, declined outright** · a second `wedding_date` column — **the ruling: `due_date` subsumes it** · the F28 rental prefill — **later; F28 is not built and is not a dep** · pricing, invoicing, deposits, any ILS amount — **deliberately, the E9 brief and Q1's money fence** · photo attachments and measurements as structured columns — **deliberately** · retention enforcement and the PII scrub — **F20/F21; F41 flags the record class** · reception and sales_assistant access — **one gate literal and one `NAV` row if the pilot asks** · a multi-stage undo and restoring a deleted ticket — **D4's ceiling** · any notification, SMS or scheduled message — **none, and `i18n.test.ts:401-402` keeps a copy edit from claiming otherwise** · a shared `poll.*` namespace — **F37 or F59** · a `/manage/**` e2e interception harness — **F58** · a language switcher — **the 2026-07-31 languages ruling; `ar` keeps shipping untranslated** · a second poll loop anywhere — **D12/D15**.
