# Plan: Feature 42 — Seamstress capacity hours + load bars + balanced assignment (Epic E9, floor-management program)

**Status**: Gate 2 self-approved 2026-08-04 under Interview Q1 (F42 is not one of the six features that stop for the user) and the 2026-07-31 ATELIER ruling. **Design gate self-approved** by the same ruling.

**Spec**: `.planning/specs/seamstress-capacity.md` (1097 lines, D1–D16, 36 applied findings, 2 recorded rejections) · **Design deck**: `.planning/design/screens/seamstress-capacity/design.md` (736 lines, §0–§12, 8 resolved decisions, 11 findings) · **Copy deck**: `.planning/design/screens/seamstress-capacity/copy.md` (215 lines, 40 keys invented + 7 reused) · **Branch**: `feature/seamstress-capacity` · **Worktree**: `.worktrees/seamstress-capacity` · **Created**: 2026-08-04

TDD throughout. Every task states its **failing test first**, then the code that makes it pass, then the exact files, then how to verify, then the commit message, then the decisions it implements.

**F42 is the last feature of the floor-management program except F60.**

---

## The local Postgres escape hatch — shipped, nothing to patch, nothing to revert

`TEST_POSTGRES_SUPERUSER_URL` is committed on `main` (F19, `3a70600`) and read at `backend/tests/conftest.py:109` **before** any Docker lookup. Verified again on this tree; `git status --short` on that file is clean.

```
createdb -h /tmp -U mrwen f42_test
export TEST_POSTGRES_SUPERUSER_URL="postgresql+asyncpg://mrwen@127.0.0.1:5432/f42_test"
cd "/Users/mrwen/Documents/Github/Ryan + rawad + mrwen/.worktrees/seamstress-capacity/Backend" \
  && uv run pytest -m db -q --ignore=tests/test_media_upload_s3.py
```

Verified live: `pg_isready -h /tmp` → `/tmp:5432 - accepting connections`; `f33_test`, `f36_test`, `f37_test`, `f41_test` already exist from prior runs — **use a new `f42_test` and drop-and-recreate it before every full run**. `migrated_db` runs `command.upgrade(cfg, "head")` against exactly this URL and then `CREATE ROLE boutique_app`; `app_role_url` derives the non-superuser from it, which is the only reason the isolation suite is not vacuous.

⚠ `tests/test_media_upload_s3.py` needs MinIO and stays red locally. F42 touches no S3.
⚠ Two `test_config.py` failures are always false locally — `Backend/.env` leaks `MEDIA_BUCKET`. CI is green (`.memory/local-env-breaks-config-tests.md`).

**Capture the db baseline count before Task 1 and re-read it. Do not hardcode a number anywhere.**

---

## Path hygiene

The repo path is `"/Users/mrwen/Documents/Github/Ryan + rawad + mrwen"` — **a space and a `+`**. Quote every shell path.

⚠ **git tracks `backend/` and `frontend/` LOWERCASE while the on-disk directories are `Backend/` and `Frontend/`.** `git add Backend/app/atelier/stages.py` silently skips modified tracked files and exits 0. Lowercase every pathspec; verify every commit with `git show --stat` (`.memory/git-add-uppercase-pathspec-trap.md`).

⚠ **`.worktrees/sos-paging` (F37) is live in this checkout at `e7bae4b`. Do not touch it.** Expect files to change under you between calls; re-check state before every mutation (`.memory/parallel-sessions-share-worktree.md`).

**`make lint` runs `frontend/scripts/qa-greps.sh`.** Verified at `:17`: `SRC="apps/storefront/src"`, so the four hard `check` patterns do not see `apps/manage`. **One block does**: the unzoned-date review at `:61-71` greps `apps/storefront/src apps/manage/src packages/ui/src` for `getDay()|getDate()|toLocaleDateString|toLocaleTimeString` and for single-line `Intl.DateTimeFormat(...)` without `timeZone`. It prints `review` and does **not** set `status`, so it cannot fail the build — but it is output that must not grow. **F42 adds no formatter** (D15). **Task 10 captures the baseline before any frontend file is written; Task 16 diffs it.**

---

## What moved since the spec was written — I re-verified every citation myself

The spec was written against `main` at `aafa76f` and is current: `git status --short` shows only untracked `.planning/` and `Backend/app/static/`. **Every code citation below was re-read on this tree at `aafa76f`, not assumed.**

### ✅ Verified — do not re-check

| Claim | Verified |
|---|---|
| `alembic heads` on `main` | **`0021 (head)`**. `0021_floor_dispatch.py`: `revision = "0021"`, `down_revision = "0020"`. **F42 builds at `0022`** — see the RULE, and do not read that number off this document |
| `staff_users` has no capacity column | `app/models/staff_user.py` — `tenant_id, email, password_hash, display_name, role, break_started_at`, and the `break_started_at` comment states the no-parity-test rule verbatim |
| `_require_seamstress` is at **`service.py:502-520`** and raises `AtelierValidationError("staff_user_id must be a live seamstress")` at **`:517`** for `row is None` **or** wrong role | verified verbatim, including the docstring naming F42's `SUM(effort_minutes) GROUP BY assigned_staff_user_id` |
| `StaffUsersRepository.by_id` filters `tenant_id` **and** `deleted_at IS NULL` | `staff_users.py:27-35`. So D6's four refusals really are one indistinguishable 400 |
| `StaffUsersRepository._refreshed` and its `populate_existing=True` docstring | `:195-212`, *"not a spare keyword to drop"*, *"has bitten this repo three times"* |
| `merge_settings` is ONE atomic `settings = settings \|\| :patch::jsonb` and opens its **own** session | `tenants.py:69-95`; `async with self._session_factory() as session, session.begin()` at `:86`. The sibling-key docstring is verbatim as cited |
| `PUT /manage/settings` admits owner **and** shift_manager, binds an unused `staff: Staff`, and answers `SettingsResponse(profile, toggles)` — **no `atelier` key** | `boutique/router.py:31-35` (router gate), `:56-66` (the route). `update_settings(tenant_id, *, profile, toggles)` at `boutique/service.py:119-133`; `_settings_result` at `:85-89` |
| `ForbidExtraModel` is `extra="forbid"` and **nothing else** | `app/schemas.py:13-18` — no `strict=True` anywhere. **D5's `StrictInt` argument is real** |
| `atelier/router.py` gate is the three roles; `delete` carries the ONE per-route tightening | `:91-98`; `delete` at `:162-167` with `Depends(require_role(OWNER, SHIFT_MANAGER))` |
| `effort_bands` resolves off `TenantContext.settings` at zero statements; `MAX_BAND_MINUTES = 1440` | `stages.py:90`, `:107-136`; the router's `_bands` at `:103-104` |
| `AtelierService.board` is three business statements and already holds `today` | `service.py:129-148`; `today = today_jerusalem(self._clock)` at **`:134`** |
| `assignees()` is a UNION whose second leg is scoped to live undelivered tickets, ordered `display_name, id` | `alteration_tickets.py:383-430` |
| `BOARD_TICKET_LIMIT = 500` and `DELIVERED_WINDOW_DAYS = 7` are server-only | `alteration_tickets.py:19`, `:28`, with the unbounded-`intake` comment at `:21-24` |
| `0020` declines the assignee index **and names F42 as its buyer** | `0020_alteration_tickets.py:111-115`, verbatim |
| `due_date DATE NOT NULL`, `effort_minutes INTEGER NOT NULL CHECK (> 0 AND <= 1440)` | `0020:84-85` |
| `SeamstressRef` is `:165-185` and its docstring names F42 by field | `atelier/schemas.py`; `from_row` at `:180-185`; `AtelierBoardResponse` at `:193`; `build` at `:203-242` with the join-by-id docstring at `:213-227` |
| `AuditAction`'s atelier block is **seven** members | `models/constants.py:444-450`. **F42 adds two to seven** |
| `audit_log.actor_id` is nullable | `models/audit_log.py:16` |
| `DomainValidationError` → 400 `VALIDATION_ERROR` with **`str(exc)`**; `RequestValidationError` → 400 | `main.py:949-953` and `:936-941` |
| The walker classifies on `frozenset.intersection(*role_sets)` at **`:388`**; `ATELIER_DELETE` at `:158`; `ATELIER_OPEN` at `:159-167`; the seamstress row is `FLOOR_OPEN \| (ATELIER_OPEN - {ATELIER_DELETE})` at **`:189`** | `tests/test_staff_role_gating.py`. **There is no `ATELIER_ELEVATED` today — D16 creates it** |
| `MANAGE_API` names **fifteen** segments including `atelier` and `checkin-qr` | `apps/manage/vite.config.ts:18-19`, comment at `:13-17`. **No edit needed** |
| `HE_F41`'s selector is `:70-73`; it is spread into `HE` at **`:85`** | `i18n.test.ts` |
| `AtelierSection` takes `role` and passes it to `TicketCard` | `:99-100`, `:126`, `:1064` |
| `runMutation` → `poll.bump()`, `poll.fail(error)` at **`:479`**, `.finally()` re-arm via `poll.reschedule()` | `:470-490`. `poll.reschedule` re-arms at `backoffRef.current` (`usePoll.ts:290`) — **so the next tick after a save is up to 5 s away.** C7 turns on this |
| `dialogOpen` at `:212`; the terminal focus effect at `:338`; the terminal render at `:782-790` («אין הרשאה» / «פג תוקף») | `AtelierSection.tsx` |
| `cardErrorText`'s `default:` branch and its C5 comment | `:493-497` |
| F41's column structure — `<section aria-labelledby>` `:1027`, counted `<h3 tabIndex={-1}>` `:1028-1034`, `<ul tabIndex={0} aria-label>` `:1050-1053` with `md:max-h-[32rem] md:overflow-y-auto` | verbatim |
| The assign `Select` at `:1509-1525` renders `{row.display_name}` alone, filtered by `assignable` | `:1518-1524` |
| The shipped `Bar` — `aria-hidden`, no `role="progressbar"`, clamp + `Number.isFinite`, `bg-gold-strong` on `bg-border`, `inlineSize` NEVER `width` | `DashboardSection.tsx:21-44` |
| **`bg-accent` does not exist.** `theme.css`'s `@theme` declares fourteen colours and no `accent`; `grep -rn bg-accent apps packages` returns **zero hits** | `packages/ui/src/theme.css:21-35` |
| `Modal` returns focus to its trigger by itself (native `<dialog>`) | `Modal.tsx:15-18` |
| `Button` `md` is `min-h-11`, `sm` is `min-h-9` | `Button.tsx:36-37` |
| `Input` wires `aria-describedby` + `role="alert"` on its error | `Input.tsx:40`, `:50` |
| `isolateLtr` is `text.indexOf(value)` and returns JSX | `lib/booking.tsx:75-87`; `isolateBidi` at `:101-113` |
| `lib/jerusalem.ts` ships **six** formatters and **zero** date arithmetic; `plainDate`'s comment forbids `new Date(iso)` | whole file, 76 lines |
| `TEST_POSTGRES_SUPERUSER_URL` and `test_exactly_one_migration_head` | `conftest.py:109`; `test_migrations.py:58`, `get_heads()` at `:77` |
| Makefile targets | `:18` `test`, `:21` `test-db`, `:27` `lint`, `:33` `qa-greps`, `:44` `fe-build`, `:47` `fe-test`, `:51` `e2e` |
| F44 is the live owner for the reassigned finding | `LOOP-STATE.md:1684-1689` — `F44`, *"Live workshop board + owner throughput analytics"*, `deps: [F34, F41, F42]` |

### ✗ Drifted or wrong — corrected here

| Cited as | Actually | Where |
|---|---|---|
| the deck's verification baseline `0c71702` | **`git ls-tree 0c71702 frontend/apps/manage/src/components/` contains NO `AtelierSection.tsx`** — that commit is F57's pr-open docs commit and predates F41 entirely. F41 merged at **`242a0ee`** (PR #39); `main` is **`aafa76f`** | `design.md` §0 — **C1** |
| the cue `<p role="status">` "ends at `:481`" | `:481` is inside `runMutation`'s `finally`. The cue **opens at `:925` and closes at `:932`** | `design.md` §1.1 — **C2** |
| F41's `EmptyState` branch at `:960-971` | **`:961-972`**, and the `tickets.length > 0` branch opens at **`:974`**. Two siblings the sketch omits: the Skeleton at **`:934-938`** and the outage block at **`:940-959`** | spec D8, §Every state; `design.md` §1.1 — **C2** |
| the panel `Card` is `surface-raised` | **`Card` is `rounded-md bg-surface p-6 shadow-sm`** (`Card.tsx:13`). Only `Modal` is `bg-surface-raised` (`Modal.tsx:46`) | `design.md` §1 — **C3** |
| the `Modal` footer at `:56` | **`:54`** — `{footer && <div className="mt-6 flex justify-end gap-3">{footer}</div>}`, hard-coded, no wrap, **no `className` seam** | `design.md` §3.1 — F-6 stands, the line number is corrected |
| the shipped `Bar` at `DashboardSection.tsx:20-43` | **`:21-44`** (`function Bar` opens at `:21`) | spec D9 |
| the assign commit `Button`'s `disabled` at `:1529` / the critic's `:1530` | **`:1531`**. `value={assignDraft ?? ticket.assigned_staff_user_id ?? ""}` is at **`:1514`** | spec D11; the critic |
| `i18n.test.ts` — exclamation guard `:397-399`, send guard `:401-402`, empty-`ar` `:406-415` | **`:885-887`**, **`:889-891`**, **`:894-906`**. The decks' cluster was read from a pre-F41 file. ⚠ **The stricter `/נשלח\|תישלח\|בדרך\|SMS\|הודעה/` at `:571` runs over `HE_F33` only**; F42's keys are not in `HE_F33`, so the binding guard is the global one at `:890` | both decks — **C5** |
| `i18n.test.ts:722` for the `HE_F41` floor (the critic) | **`:721`** — `expect(HE_F41.length).toBeGreaterThanOrEqual(94);`. **The spec and the copy deck were right and the critic is wrong.** Recorded so nobody "fixes" a correct citation | the critic's REQUIRED 5 |
| «`text-danger` is 6.18:1 **on paper**» / the critic's «it is 6.78 on `bg-surface`» | **Both labels are wrong and the critic's number is the wrong correction.** Recomputed: `#A03232` on `--color-bg #FDFBF7` = **6.78**; on `--color-surface #F6F0E6` = **6.18**. The word renders inside a `Card`, i.e. on `bg-surface`, so **6.18 is the correct figure and only its label is wrong.** Changing the figure to 6.78 would introduce the error the finding claims to fix | `design.md` §1.2, §9 — **C3** |
| «the bar's `bg-border` track is visible against its own card» | `#E4DACA` on `#F6F0E6` = **1.22:1**. An empty track is **not** visible without reading. §2.3's third decision must rest on the text | `design.md` §2.3 — **C3** |
| «every keyboard stop is ≥44 px, `Input` lands at ≈44» | `Input.tsx:42` is `px-3 py-2 text-base` + `border`; `--text-base--line-height: 1.6` → 25.6 + 16 + 2 = **43.6 px**. Nothing *fails* (WCAG 2.0 AA has no target-size criterion) but a check written `>= 44` reds against a shipped component | `design.md` §7, §8 — **C8** |
| `HE_F42`'s filter covers all 40 keys | It selects **39**. `atelier.cue.assignedOverload` starts with neither `atelier.capacity.` nor `atelier.settings.` — and it is the string `copy.md` §5 calls the only thing a screen-reader user ever hears about an overload she just caused | `copy.md` §0 line 33 and §10 — **C4** |
| `test_boutique_settings_api.py` / `test_boutique_settings_db.py` | **Neither module exists.** The shipped homes are `tests/test_boutique_api.py` (fast, fake service, a `ROUTES` table at `:56-69` already carrying `("PUT", "/manage/settings", {})`), `tests/test_boutique_validation.py` (fast, pure) and `tests/test_boutique_service.py` (**`pytestmark = pytest.mark.db`**, which already ships `test_merge_settings_preserves_concurrently_written_sibling_key` at `:146`) | spec §Testing — **C11** |
| «F37 is building with a migration of its own» | Sharper than that: **`.worktrees/sos-paging/Backend/migrations/versions/0021_sos_alerts.py` declares `revision = "0021"`, `down_revision = "0020"` — it is ALREADY COLLIDED with `main`'s `0021_floor_dispatch`.** F37 must renumber to `0022` at its rebase, which is the number F42 builds at | spec D1, §Conflicts 12 — **C12** |

---

## THE MIGRATION-NUMBER RULE — a rule, never a number

`main`'s head is **`0021`** as this plan is written, and **F37 is in flight in `.worktrees/sos-paging` carrying a migration that is already numbered `0021`** and must move. LOOP-STATE's MIGRATION CHAIN block records that the grid moved three times in one day and that *"not one of the four fixed numbers this file originally assigned survived contact."* So:

1. **BUILD at `head + 1`.** In Task 1, from the worktree:
   ```
   cd "/Users/mrwen/Documents/Github/Ryan + rawad + mrwen/.worktrees/seamstress-capacity/Backend" \
     && uv run python -m alembic heads
   ```
   Today that prints `0021 (head)`, so the file is `0022_seamstress_capacity.py`, `revision = "0022"`, `down_revision = "0021"`. **If it prints something else, `alembic heads` is right and this document is stale.** Building at head+1 is what makes the branch self-coherent so its `db`-marked tests run at all — a `down_revision` naming a revision that does not exist is an outright alembic error, not a drift.
2. **Make the migration the LAST commit on the branch.** Task 1 is early, so the commit is reordered onto the tip at rebase — or amended in place, because nothing else in the branch references the revision literal. This is the one instruction that makes step 3 cost one amend to one file.
3. **RE-RESOLVE from `alembic heads` on `origin/main` IMMEDIATELY BEFORE the rebase that precedes the push.** Three edits: the filename, the `revision` literal, the `down_revision` literal. **If F37 lands first, `main` will be at `0022` and F42 goes to `0023`.**
4. **Verify `alembic heads` prints exactly ONE head** on the rebased branch. Two files claiming one revision id is a multiple-heads error **git cannot see** (the filenames differ). `0020`'s own header records the shape: *"it emits `UserWarning: Revision 0019 is present more than once`, dedupes to ONE script and drops the other, which on a fresh database means one of the two tables is simply never created."* F19's fast no-DB guard (`test_migrations.py:58`) fails in `make test` if you forget — **but only AFTER the rebase**, because from an unrebased worktree there is only ever one number to see.
5. **Do not OPEN the PR while a lower-numbered migration is still unmerged.** CI tests the merge result.

**Every assertion in `test_migrations.py` keys to "after this feature's migration", never to a revision literal.**

---

## Thirteen corrections — the critic's REVISE and my own re-verification, amended into the sources in Task 0

The spec is binding and D1–D16 are **not** re-litigated. These are the places where the critic's verdict, the design deck's findings, or my own re-reading disagrees with the documents. **Every resolution is the smaller edit.**

### C1 — the decks' verification baseline is a commit that predates the code they verify

`design.md` §0 names *"`main` at `0c71702`"*. Verified: that commit's tree has **no `AtelierSection.tsx` at all**. **Resolution:** the baseline is **`aafa76f`** (current `main`); F41's tree entered at **`242a0ee`** (PR #39) and F58's at `595dfe5` (PR #40). §0 states which files were re-read at that baseline. This plan's ✅ table is that statement.

### C2 — §1.1's insertion point, re-cited, with all four siblings

The panel's placement is correct as designed; only the anchors are wrong. **Resolution — the sketch shows the real order:**

```jsx
{/* AtelierSection.tsx — the cue <p role="status"> is :925-932 */}

{boardData !== null && ( <SeamstressPanel … /> )}                    {/* NEW — one insertion point */}

{boardData === null && !loadFailed && ( <Card><Skeleton …/></Card> )}     {/* :934-938 */}
{loadFailed && boardData === null && ( <div>…outage…</div> )}             {/* :940-959 */}
{boardData !== null && boardData.tickets.length === 0 && ( <EmptyState …/> )}  {/* :961-972 */}
{boardData !== null && boardData.tickets.length > 0 && ( <>…truncated, CTA, rail, columns…</> )} {/* :974 */}
```

The panel's `boardData !== null` gate is mutually exclusive with both omitted blocks, so the behaviour the deck wants is unchanged — but §1.1 is sold as *"read against the shipped file"* and Task 14 will paste it.

### C3 — `Card` is `bg-surface`, §2.3's third decision moves to the text, and the contrast ledger is corrected in the direction the critic got backwards

Three edits, and the third is a **rejection**:

1. **`Card` is `bg-surface`** (`Card.tsx:13`). §1's ASCII annotation is corrected.
2. **The empty-track-vs-no-track distinction is dropped as a *visual* claim.** `#E4DACA` on `#F6F0E6` is **1.22:1** — an empty track is not visible without reading. The distinction rests where §2.4's own argument already puts it: **«0 שעות עד … מתוך 0» versus «לא הוגדרה קיבולת»**, which is text, which is announced, and which is already the acceptance line. **No colour is invented and no token is added.**
3. **⚠ The critic's «6.18 → 6.78» correction is REFUSED, with the arithmetic.** Recomputed from `theme.css`'s own hexes: `#A03232` on `--color-bg #FDFBF7` = **6.78**; on `--color-surface #F6F0E6` = **6.18**. The overload word is a `<strong>` inside a `<p>` inside a `Card`, i.e. on `bg-surface`. **6.18 is the right number; only the label "on paper" is wrong.** §9's row becomes *"`text-danger` on `bg-surface` — 6.18:1"*. Adopting 6.78 would put the page-background figure on a card-background row.

The bar's own pair is unchanged and re-verified: `#9E7B36` on `#E4DACA` = **2.84:1**, `#A03232` on `#E4DACA` = **5.07:1**, and 1.4.11 is argued not to bind because the bar is `aria-hidden` decoration.

### C4 — `HE_F42` drops the one key that carries the feature's legal a11y load

`copy.md` §0 (line 33) and §10 both filter on the two prefixes. `atelier.cue.assignedOverload` matches neither, so the block selects **39 of 40**. **Resolution — one term, by EXACT key:**

```ts
const HE_F42 = HE_F41.filter(
  ([key]) =>
    key.startsWith("atelier.capacity.") ||
    key.startsWith("atelier.settings.") ||
    key === "atelier.cue.assignedOverload",
);   // NOT spread into HE — HE_F41 already carries these rows
```

⚠ **Not `startsWith("atelier.cue.")`** — that swallows F41's six shipped cue keys (`created`, `advanced`, `undone`, `assigned`, `released`, `deleted`, verified `he.ts:1392-1416`) and turns F42's block into a partial re-count of F41's.

### C5 — the `i18n.test.ts` citation cluster, and one citation the critic broke

Every guard citation in both decks moves: exclamation **`:885-887`**, send **`:889-891`**, empty-`ar` **`:894-906`**, `HE_F41` selector `:70-73` (unchanged, correct), spread into `HE` `:85` (unchanged, correct). ⚠ **The `HE_F41` floor is `:721` and the decks already say `:721`** — the critic's `:722` is wrong and is **not** applied. §8's register row names the **global** guard at `:890` (`/נשלח|תישלח|בדרך/`); the stricter `:571` variant runs over `HE_F33` only and does not bind F42.

### C6 — `atelier.capacity.useDefault`'s approved value changed from D15 and the change is right

D15 `:699` is «חזרה לברירת המחדל **של הבוטיק**»; `copy.md` §3 ships «חזרה לברירת המחדל». The change follows F-6 — the control now **clears the field** rather than submitting, and «של הבוטיק» moved into `hoursHelp`, where the tenant's number actually lives. **Resolution:** the F-6 row in `copy.md`'s front table names the **value** change explicitly, not only the placement and behaviour change, so a reviewer diffing D15 against the deck finds an owner.

### C7 — the window between a settings save and the next tick: **the one-tick lag is ACCEPTED**

Verified: `PUT /manage/settings` returns `SettingsResponse` (which D5 edit #4 extends with `atelier`, so the server side is built either way), and `runMutation` re-arms through `poll.reschedule()` at the current backoff (`usePoll.ts:290`) — **up to five seconds.** So for up to one tick after an owner changes the default from 30 to 40, «ברירת מחדל של הבוטיק» rows still divide by 30 and F41's cards below still carry old band labels through `bandLabel`.

**Resolution — accept it, and give §6 the row it needs.** Reasons, in order:

1. `default_weekly_capacity_hours` and `effort_bands` are **envelope** fields the poll owns. Patching them from a different endpoint's response puts a second writer on data D7 makes the board authoritative for — the same shape D6 refuses for `assigned_minutes`, one level up.
2. The lag is bounded by one tick, self-corrects with no user action, and the dialog's own cue («ההגדרות נשמרו.») already tells her the write landed.
3. The alternative buys ≤5 s of freshness for a second patch discipline and a second §6.1.

**§6 gains one row: «Settings saved, before the next tick» → every rendered number is the previous mapping's; nothing is patched; the next tick replaces the whole envelope.** No code, no test beyond the row.

### C8 — the 44 px assertion is scoped to what actually carries it

`Input.tsx:42` lands at **43.6 px** by the deck's own type scale. **Resolution:** §7/§8 assert the floor on **`Button size="md"`** (`min-h-11`, verified `Button.tsx:37`) and on the tree-wide **absence of `size="sm"`**; the `Input`'s number is stated for what it is, with the reason it does not fail — **WCAG 2.0 AA, the legal bar here (pre-decided #38), has no target-size criterion at all** (2.5.5 is 2.1 AAA; 2.5.8 is 2.2 AA). A check written `>= 44` would red against a shipped `packages/ui` component that F42 may not edit.

### C9 — F-2's bound, and why it differs from its own siblings

**Resolution (F-2, adopted):** the `<ul>` is **`md:max-h-96 md:overflow-y-auto`**, unbounded at 375, `tabIndex={0}` unconditional. Two independent defects in D8's `max-h-64`-at-every-width: 16 rem = 256 px shows **2.3** common rows (24 `py-3` + 44 `min-h-11` + 16 bar + 25 sentence = 109 px/row, 151 px worst case), not "about four"; and bounding at 375 reintroduces F41 §6's refused scroll-trap on the primary device.

⚠ **And the divergence from F41's `md:max-h-[32rem]` (`:1053`) is named rather than left to be read as drift**: 24 rem is a Tailwind scale value where `[32rem]` is arbitrary, and 3.5 rows of a **3–6 person roster** (Risk 6) is a bound that never engages, while a 60-card column's does. One sentence in §7.

### C10 — `copy.md` §0 rule 7 forbids the separator it uses seven times

*"No emoji, no dots, no glyphs"* — while « · » is the separator in `headingCount`, `unassignedRow`, `optionRow` and the row sentence. **Resolution: one word — "no **status** dots".** The separator has shipped precedent (`atelier.stageCount` = «{{stage}} · {{total}}», `he.ts:1277`), which also makes F42's heading byte-consistent with F41's.

### C11 — the settings tests go in the modules that exist

`test_boutique_settings_api.py` and `test_boutique_settings_db.py` do not exist. **Resolution — the real homes, verified:**

| Spec name | Real module | Marker |
|---|---|---|
| `test_boutique_settings_api.py` | **`tests/test_boutique_api.py`** — fake service, `ROUTES` at `:56-69` already lists `("PUT", "/manage/settings", {})` | fast |
| pure validator cases | **`tests/test_boutique_validation.py`** | fast |
| `test_boutique_settings_db.py` | **`tests/test_boutique_service.py`** — `pytestmark = pytest.mark.db` at `:40`; already ships `test_merge_settings_preserves_concurrently_written_sibling_key` at `:146` | db |

⚠ **The shipped sibling-key test uses `asyncio.gather`, and F42's must not.** That test's mechanism is `||` itself over two single-statement UPDATEs, so ordering is irrelevant to it. F42's mutation is *"replace `||` with a Python read-modify-write"*, whose failure depends entirely on both readers seeing a pre-commit snapshot — with `gather` that is luck. **F42 writes a second, explicitly ordered test** (open A, open B, read in both, write A, commit A, write B, commit B) so the mutation is deterministic, and says so in a comment beside the shipped one.

### C12 — F37's migration is already collided, which sharpens the rule rather than changing it

`.worktrees/sos-paging/Backend/migrations/versions/0021_sos_alerts.py` is `revision = "0021"`, `down_revision = "0020"` — built before F58 merged. **F42 builds at `0022` and must expect `0022` to be taken by F37's renumber.** Step 3 of the RULE is not optional on this branch.

### C13 — the six design-deck findings that are build tasks, folded

| # | Finding | Resolution, and where it lands |
|---|---|---|
| **F-1** | `atelier.capacity.load`'s `{{date}}` has **no source**: `lib/jerusalem.ts` ships zero date arithmetic (verified, whole file) and a client computation would print the wrong date anyway — the SQL filtered on the **server's** `today_jerusalem + 7` | **`AtelierBoardResponse` gains `due_soon_through: datetime.date`.** `board()` already holds the horizon. **The envelope's additions are THREE, not two.** Task 4 |
| **F-2** | `max-h-64` at every width | **C9.** Task 12 |
| **F-4** | `loadNoCapacity`'s `{{hours}}` is `assigned_minutes`, **therefore D10's sort group 2 keys on `assigned_minutes` ASC, not `due_soon_minutes`** — or panel and `<Select>` are ordered by a number neither displays, which is D10's own argument against itself. The Hebrew already settles it (`optionAssigned` = «{{hours}} שעות **משויכות**»). The spec's acceptance line («by load ascending») survives unchanged | **One word in D10.** Tasks 11, 14 |
| **F-5** | D9's *"every numeric run is `<bdi dir="ltr">`"* is unbuildable and ships a live collision: `capacity.load` has **three** numeric interpolations and `isolateLtr` isolates one by `indexOf`, so on «12.1 … מתוך 12» isolating `"12"` matches **inside "12.1"** (verified `booking.tsx:76`). F41 bars a second helper | **No bidi helper anywhere in this feature.** UBA derivation in §10.4; only the **name** gets a bare `<bdi>` in its own element. Tasks 12, 15 |
| **F-6** | The capacity dialog's third footer button cannot exist: `Modal.tsx:54` is `mt-6 flex justify-end gap-3`, hard-coded, no wrap, **no `className` seam**, and three buttons overflow 295 px at 375. Editing `packages/ui` from a call site is barred | «חזרה לברירת המחדל» moves **into the body** and **clears the field**; empty ⇒ `null` in both directions. **Two consequential new keys** (`hoursHelp` / `hoursHelpNoDefault`) — the help line is a lie on a tenant with no default, i.e. every boutique on day one. Task 13 |
| **F-11** | The settings dialog never mentions D4's silent relabel | One key: `atelier.settings.bandsHelp` = «שינוי ההערכות משפיע רק על כרטיסים חדשים.» Task 13 |

**Recorded / closed, not built:** F-3 (`unassigned_minutes` is the **unfiltered** sum — no bar means no rate) · **F-7** (F41's F-2 named "F42's capacity matrix" as owner of the 720 px console-width decision; **F42 declines it — no matrix ships and the list fits. New owner: F44**, `LOOP-STATE.md:1684-1689`, `deps: [F34, F41, F42]`, verified) · F-8 (fired, answered "no change" — the panel is above the rail, not a sixth chip) · F-9 (the region name churn is inherited from F41's five columns; diverging on one region would be worse) · F-10 (the bar is byte-identical at 140 % and 400 % — designed, stated so nobody adds a stripe or a «×4» to an `aria-hidden` widget).

**Key arithmetic after C4, C6 and C13:** **40 invented, 7 reused.** D15's table is short by five and carries one changed value: **add** `capacity.submit` (D15 gives the capacity dialog no confirm key at all), `capacity.hoursHelp`, `capacity.hoursHelpNoDefault`, `settings.bandsHelp`; **change** `capacity.useDefault` to «חזרה לברירת המחדל». `copy.md` is the binding list.

---

## Scope fence — read this before every task

**F42 ships one nullable column, one tenant default, two grouped sums, four wire fields plus three envelope fields, one write route, one settings block, one panel and one pure-fold module.**

| Not in F42 | Whose |
|---|---|
| The roster projection — hourly capacity walked back from the due date, per-day or per-horizon bars, `availability_rules` as a denominator | **F40** (E8, not queued). D2 records exactly what it replaces |
| Any block, refusal, 409, confirm-on-overload, disabled option or auto-balancing suggestion | **#40 — declined outright.** Overload only flags |
| A server-side overload flag, or any advisory field on any mutation response | **D11 — not needed.** The console holds every number |
| Split load (`parent_ticket_id`) and expedite (`expedited_at`) | **later; F41's Out-of-scope sizes them** |
| Per-day / per-week / per-shift buckets of load | **F40's shape** |
| Load history, trend, throughput, median time-in-state | **F44** |
| Any change to `stage_of`, the five stamps, `assignees()`, `AtelierTicket`, or any F41 write predicate | **nothing — F41's Risk 9 promised an addition and D3/D7 make that literally true** |
| A re-value sweep of `effort_minutes` after a band re-tune | **D4 — declined with reasons** |
| A `staff_capacity` table, an `effort_band` column, a stored `assigned_minutes` | **D1, D3, D4 — each declined with its reason** |
| A second poll loop, a capacity-only read endpoint, a nav row, a `SectionKey` member | **F41 D12: the envelope is the mechanism, the panel is content** |
| A `role="grid"`, a roving tabindex, an arrow-key manager | **D8 — the list discharges the keyboard requirement structurally** |
| Auditing `profile` / `toggles` on `PUT /manage/settings` | **a pre-existing gap this feature does not widen** (Risk 7) |
| Lifting `ConsoleShell`'s 720 px cap | **F44** — F42 declines the ownership F41's F-2 assigned it |
| Mirroring `MAX_WEEKLY_CAPACITY_HOURS` or `MAX_BAND_MINUTES` on the client, in TS **or in a Hebrew sentence** | **server bounds — `i18n.test.ts:705-719`'s recorded precedent** |
| Any `packages/ui` edit — including a `className` seam on `Modal`'s footer | **barred; F-6 is the workaround** |
| Any notification, SMS or scheduled message | **none, and the `:890` guard is what keeps a copy edit from claiming otherwise** |
| A language switcher | **the 2026-07-31 languages ruling; `ar` ships untranslated** |
| Any E2E | **`vite preview` runs with no backend; F58 owns the `/manage/**` harness** |

If a task's diff grows a roster read, a second fetch on the atelier screen, a `packages/ui` edit, a write to `restoreRef`/`captureFocus`/`boardCommit`, or a client constant mirroring a server bound, **it has left F42**.

---

# Part 0

## Task 0 — This plan, and the thirteen corrections amended into the spec and both decks
`.planning/plans/seamstress-capacity.md` (this file), `.planning/specs/seamstress-capacity.md`, `.planning/design/screens/seamstress-capacity/design.md`, `…/copy.md`

No test, no code. Make the three source documents the binding statement of every resolution above.

**Spec:**
- **Header / §What already exists** — the baseline is `aafa76f`; F41's tree entered at `242a0ee`. **F37's `0021_sos_alerts.py` is already collided** (C12).
- **D3 / D7 / §API surface / §Every state** — `AtelierBoardResponse` gains **three** fields, not two: `due_soon_through: datetime.date` (F-1). Every «two on the board» becomes «three».
- **D8 / §Every state / §Frontend changes** — `max-h-64` at every width → **`md:max-h-96 md:overflow-y-auto`**, unbounded at 375, `tabIndex={0}` unconditional (C9/F-2); the `EmptyState` branch is `:961-972` and the rail branch opens at `:974` (C2).
- **D9** — the bar's markup shape is `DashboardSection.tsx:21-44`; the contrast row for `text-danger` reads **6.18:1 on `bg-surface`** (C3); **"every numeric run is `<bdi dir="ltr">`" is DELETED and replaced by "no bidi helper; the name takes a bare `<bdi>` in its own element"** (F-5).
- **D10** — sort **group 2 keys on `assigned_minutes` ASC** (F-4). One word.
- **D15** — the key table gains `capacity.submit`, `capacity.hoursHelp`, `capacity.hoursHelpNoDefault`, `settings.bandsHelp`; `capacity.useDefault` becomes «חזרה לברירת המחדל»; every `i18n.test.ts` line number is re-cited (C5); the `HE_F42` filter gains `|| key === "atelier.cue.assignedOverload"` (C4).
- **§Testing** — the three real module names (C11), and the note that F42's sibling-key test is **explicitly ordered, never `gather`**.
- **§Conflicts** — a new entry: **F42 declines F41's F-2 hand-off of the 720 px console-width decision; the owner is F44** (`LOOP-STATE.md:1684-1689`).

**`design.md`:** §0's baseline → `aafa76f` + the list of files re-read (C1); §1's `Card` annotation → `bg-surface` and §2.3's decision 3 rested on the text (C3); §1.1's sketch re-cited with all four siblings (C2); §1.2/§9's contrast rows corrected **to 6.18 on `bg-surface`** with the critic's 6.78 recorded as refused and why (C3); §7 gains the `md:max-h-96` vs F41's `md:max-h-[32rem]` divergence sentence (C9); §7/§8's 44 px claim scoped to `Button size="md"` with `Input`'s 43.6 stated (C8); §6 gains the settings-save one-tick-lag row (C7); every `i18n.test.ts` and `Modal.tsx` line number re-cited (C5); F-7's owner named as **F44 at `LOOP-STATE.md:1684`** (C13).

**`copy.md`:** §0 rule 7 → "no **status** dots" (C10); §0 line 33 and §10's `HE_F42` filter gain the exact-key term with the `startsWith("atelier.cue.")` trap named (C4); the F-6 row names the **value** change to `useDefault` (C6); the `HE_F41` floor stays `:721` (C5).

- **Done when**: `grep -n "0022\|down_revision" .planning/specs/seamstress-capacity.md` returns no build-against number; `grep -rn "0c71702\|max-h-64\|bg-accent\|test_boutique_settings" .planning/specs/seamstress-capacity.md .planning/design/screens/seamstress-capacity/` returns only recorded-correction prose; `grep -c 'atelier\.' .planning/design/screens/seamstress-capacity/copy.md` reflects 40 invented keys.
- **Commit**: `docs(planning): F42 implementation plan and thirteen corrections to the spec and decks — Gate 2 self-approved`
- **Implements**: C1–C13, `design.md` F-1/F-2/F-4/F-5/F-6/F-11.

---

# Part I — the backend

## Task 1 — The migration **and** the ORM model, as one atomic change (D1)
`backend/migrations/versions/00NN_seamstress_capacity.py` (**✚**), `backend/app/models/staff_user.py`, `backend/tests/test_migrations.py`

**The two halves ship together and this is not a preference.** No model↔migration parity test exists anywhere in `Backend/tests/` — `staff_user.py:22-25`'s own comment says so about `break_started_at` — so without the mapped column every backend line in Tasks 2–8 is an `AttributeError`.

**Resolve the revision id at build time.** `uv run python -m alembic heads` in the worktree's `Backend/`; today `0021 (head)` → `0022_seamstress_capacity.py`. **Reorder this commit onto the branch tip at rebase.**

### The failing tests first — `db`-marked, appended to `test_migrations.py`, run locally

The file's convention: **the round-trip test goes LAST**, owns no fixtures, and wraps the downgrade in `try/finally: command.upgrade(cfg, "head")` — these tests mutate the live session-scoped schema and leaving it down fails unrelated modules with `UndefinedTable`.

1. `test_the_capacity_column_exists_and_is_nullable` — `information_schema.columns`: `weekly_capacity_hours` is `integer`, `is_nullable = 'YES'`, **no column default**.
2. **`test_the_capacity_definitions_are_pinned`** — the highest-value test here, because what it guards is a *future* edit. **CAPTURE the literals by running `pg_get_constraintdef(oid)` and `pg_indexes.indexdef` against the server; never transcribe them from this document.** Postgres deparses predicates, adds `::text` casts and schema-qualifies. Two rows: `staff_users_weekly_capacity_hours_check`, and `idx_alteration_tickets_tenant_assignee`'s `indexdef` — **the row that fails loudly if someone drops the `delivered_at IS NULL` half of the partial predicate**. Asserted **after this feature's migration** (at `head`), never after a revision literal.
3. `test_the_capacity_check_refuses_out_of_range` — superuser INSERT/UPDATE: `0` accepted, `168` accepted, `-1` refused, `169` refused, **and a read-back proving each refusal changed nothing**.
4. `test_migration_00NN_round_trips` — upgrade applies and the end state asserts; `downgrade` one revision and the **reverse** asserts (no column, no constraint, no index); `upgrade` to head and re-assert. `0013`'s docstring rule: a silently no-op downgrade stays green while shipping an unrollbackable migration. **Last in the file, in `try/finally`.**

**`test_every_tenant_id_table_has_forced_rls` needs no edit — and its silence is not evidence.** F42 creates no table, so that walker has nothing new to find. Stated in the migration comment (D1).

### The code

```sql
ALTER TABLE staff_users ADD COLUMN weekly_capacity_hours INTEGER;

ALTER TABLE staff_users ADD CONSTRAINT staff_users_weekly_capacity_hours_check
    CHECK (weekly_capacity_hours >= 0 AND weekly_capacity_hours <= 168);

CREATE INDEX idx_alteration_tickets_tenant_assignee
    ON alteration_tickets (tenant_id, assigned_staff_user_id)
    WHERE deleted_at IS NULL AND delivered_at IS NULL;
```

Raw `op.execute` DDL, the `0020` idiom. **Nullable with no default** — a real state, and the one `ADD COLUMN` form Postgres does as metadata only. **A named table constraint**, so `pg_get_constraintdef` has a name to pin. **The index carries a comment quoting `0020:111-115`'s hand-off** and stating that D3's aggregate is deliberately uncapped, which is what the partial predicate bounds.

**No `enable_tenant_rls`, no `GRANT`, no trigger** — both tables carry theirs (`0003_auth.py:83-84`'s table-level precedent), and adding a column to a table under a policy does not change the policy. `downgrade()` drops the index, the constraint and the column, in that order.

`app/models/staff_user.py` gains `weekly_capacity_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)` with the `break_started_at` comment's reason restated for this column.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| the CHECK | widen to `<= 200` | test 2 **RED** on the byte-identical comparison; test 3 **RED** on the `169` case |
| the index's `AND delivered_at IS NULL` | drop that clause | test 2 **RED** on `indexdef` |
| the model field | delete it | **Task 3's tests fail to import** — noted here rather than assumed, because no parity test exists |
| `downgrade` | make it `pass` | test 4 **RED** on the reverse assertion |

- **Done when**: the local db suite is green (baseline + these cases); `make lint` clean; `make test` green with the db module collected-and-deselected; `git show --stat` confirms the **lowercase** pathspecs landed.
- **Commit**: `feat(atelier): staff_users.weekly_capacity_hours, its CHECK, and the assignee index F41 reserved`
- **Implements**: D1.

---

## Task 2 — The pure capacity core: one magnitude, one home, and `is not None` (D2)
`backend/app/atelier/stages.py`, `backend/tests/test_atelier_capacity.py` (**✚**)

**`MAX_WEEKLY_CAPACITY_HOURS` lives in `app/atelier/stages.py` and nowhere else** — beside `MAX_BAND_MINUTES`, on the import edge D5 already argued acyclic (`atelier.stages` imports only `app.models`). The rejected finding's `atelier/validation.py` would buy a second edge pulling in `app.booking.validation` and `app.catalog.validation` (`atelier/validation.py:13-20`, verified) for nothing.

### The failing tests first — fast, pure, no Postgres, no fakes

**`test_atelier_capacity.py`:**
- `default_capacity_hours` over: **no `atelier` key** (→ `None`), a non-dict `atelier`, a missing sub-key, a `str`, a **`bool`** (the `int`-subclass trap `_positive_int` already records), `-1`, `0` (→ `0`), `168`, `169` (→ `None`). ⚠ **`0` resolves to `0`, not `None`** — that is the whole of D1's "she is not available this week".
- `resolve_capacity` over the **four** combinations of (her column set / not) × (tenant default set / not), asserting both the hours **and** `capacity_is_default`.
- **`test_a_zero_capacity_is_hers_and_not_the_boutiques`** — stored `0`, tenant default `40` → `(0, False)`. **The named mutation.**

### The code

```python
MAX_WEEKLY_CAPACITY_HOURS = 168        # the DDL CHECK's ceiling, one magnitude one place

def default_capacity_hours(settings: dict[str, Any]) -> int | None:
    """The tenant's house default, or None. There is NO platform default."""
    atelier = settings.get("atelier")
    stored = atelier.get("default_weekly_capacity_hours") if isinstance(atelier, dict) else None
    if isinstance(stored, bool) or not isinstance(stored, int):
        return None
    return stored if 0 <= stored <= MAX_WEEKLY_CAPACITY_HOURS else None


def resolve_capacity(row: StaffUser, tenant_default: int | None) -> tuple[int | None, bool]:
    if row.weekly_capacity_hours is not None:
        return row.weekly_capacity_hours, False
    return tenant_default, tenant_default is not None
```

`resolve_capacity`'s docstring is D2's, verbatim, including why `or` is the bug: it would hand her the boutique's default, render her bar at a fraction of the truth in the non-overload colour, print «ברירת מחדל של הבוטיק» on a number she set, and sort her **first** in the assign `Select`.

⚠ **`default_capacity_hours` deliberately does NOT share `_positive_int`.** That helper's range is `1..1440` and rejects `0`; this one's is `0..168` and accepts it. One shared helper with two range parameters would be a parameterised abstraction over two call sites — and getting the `0` boundary wrong in it silently breaks the state this whole feature has a designed rendering for.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| `resolve_capacity`'s `is not None` | replace with `or` | `test_a_zero_capacity_is_hers_and_not_the_boutiques` **RED** |
| `default_capacity_hours`' `isinstance(stored, bool)` | drop it | the `True` case **RED** (resolves to a one-hour week) |
| the `0 <= stored <= MAX` clause | drop it | the `169` case **RED** — and note a stored 200 would then reach the wire and every bar would divide by it |

- **Done when**: `make lint` + `make test` green locally.
- **Commit**: `feat(atelier): the tenant capacity default and its two-step resolution`
- **Implements**: D2.

---

## Task 3 — The load aggregate: two sums, one statement, and no arithmetic anywhere on the server (D3)
`backend/app/db/repositories/alteration_tickets.py`, `backend/tests/test_atelier_capacity_db.py` (**✚**)

⚠ **THE UNIT BOUNDARY, STATED ONCE AND ENFORCED IN TWO PLACES.** The database stores **hours** (`weekly_capacity_hours`) and **minutes** (`effort_minutes`), and **the server never multiplies the two**: the aggregate returns minutes, `resolve_capacity` returns hours, both reach the wire in their own units under their own names, and **the single `× 60` in the entire feature is `capacityMinutes()` in `lib/capacity.ts` (Task 11)**. This task's assertion is the negative half: **no `60` and no `* 60` appears anywhere in `Backend/app/atelier/` or `Backend/app/db/repositories/alteration_tickets.py`** — a grep, asserted in review, because an hours/minutes mix-up on the server would produce a number that is wrong by 60× and dimensionally plausible on both sides.

### The failing tests first — `db`-marked, run locally

`tests/test_atelier_capacity_db.py`, seeding through `tenant_session` against real rows:

1. `test_load_counts_undelivered_work_at_every_stage` — a ticket at `intake`, one at `in_progress`, one at `qc`, one at `ready`, and one whose `delivered_at` was **undone**, all counted in full. A `delivered` one, a soft-deleted one and another tenant's excluded.
2. **`test_the_bar_counts_only_work_due_inside_the_week`** — a ticket due in 30 days is in `assigned_minutes` and **not** in `due_soon_minutes`; a ticket 10 days overdue is in **both**; a ticket due exactly on `today + 7` is **in**, `today + 8` is **out**. **Mutation: delete the `FILTER` → red.**
3. `test_load_groups_null_as_the_unassigned_pile` — the `NULL` key is present with its own two sums.
4. `test_a_seamstress_with_no_tickets_is_absent_from_the_result` — she does not appear at all; Task 4's fold is what reads her as `(0, 0)`.
5. **`test_a_truncated_board_still_reports_exact_load`** — seed `BOARD_TICKET_LIMIT + 20` live tickets for one seamstress; the aggregate is exact and `truncated` is `True`. **Mutation: fold the load in Python over `board()`'s ticket list → under-counts by the truncated tail → red.**
6. **`test_the_hours_and_the_minutes_never_meet_on_the_server`** — the aggregate's return values are pure minute sums: a seamstress with `weekly_capacity_hours = 12` holding one 30-minute ticket reports `30`, never `30/60`, never `720`. **The hours/minutes catcher.** Mutation: divide or multiply by 60 anywhere in the method → red.

⚠ **`test_atelier_capacity_db.py` seeds `staff_users` rows and inherits F57's D1 trap through F41's note**: no **committed** `staff_users` row may hold a floor role, or `test_migrations.py::test_adding_the_role_check_validates_existing_rows` — which re-adds `0011`'s two-value CHECK on a populated table — goes red in a file that never mentions capacity. **Seed seamstress rows inside a transaction the test rolls back.**

### The code

```python
async def load_by_assignee(
    self, session: AsyncSession, tenant_id: UUID, *, horizon: datetime.date
) -> dict[UUID | None, tuple[int, int]]:
    """(due_soon_minutes, assigned_minutes) per assignee, NULL included."""
```

One statement:

```sql
SELECT assigned_staff_user_id,
       SUM(effort_minutes) FILTER (WHERE due_date <= :horizon) AS due_soon_minutes,
       SUM(effort_minutes)                                      AS assigned_minutes
  FROM alteration_tickets
 WHERE tenant_id = :t AND deleted_at IS NULL AND delivered_at IS NULL
 GROUP BY assigned_staff_user_id
```

**Uncapped, deliberately** — the docstring says so and names the partial index Task 1 bought. `COALESCE(..., 0)` on the FILTERed sum, because a group whose every ticket is due later returns `NULL` for it. **`delivered_at IS NULL` is the whole definition of "not yet delivered"** and the docstring states, in F41 Risk 9.1's words, that it is **one column, never `stage != 'delivered'`** — `stage` is derived in Python by `stage_of` and has no SQL expression, so re-deriving it here would be a second copy of the state machine in a second language.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| `FILTER (WHERE due_date <= :horizon)` | delete it | test 2 **RED** — a 30-day ticket reddens the bar |
| `delivered_at IS NULL` | delete it | test 1 **RED** on the delivered row |
| the uncapped aggregate | replace with a Python fold over `board()`'s tickets | test 5 **RED** |
| the `COALESCE` on the filtered sum | drop it | the everything-due-later case **RED** with a `None` |

- **Done when**: local db suite green; `make lint` + `make test` green.
- **Commit**: `feat(atelier): the load aggregate — two grouped sums in one uncapped statement`
- **Implements**: D3.

---

## Task 4 — The envelope: four fields on `SeamstressRef`, THREE on the board (D7, F-1)
`backend/app/atelier/schemas.py`, `backend/app/atelier/service.py`, `backend/tests/test_atelier_board.py`

### The failing tests first — fast, pure folds over frozen records

`test_atelier_board.py` (extended):
- `SeamstressRef` with a load; **without one — `(0, 0)` through `load.get(row.id, (0, 0))`, and she does not vanish**; with `assignable: false` **and** a real load (the anomalous bucket F41's Risk 9.2 hands here).
- A seamstress whose every job is due next month: `due_soon_minutes: 0`, a real `assigned_minutes`.
- `weekly_capacity_hours` resolves through `resolve_capacity`: her column, else the tenant default, else `null`; `capacity_is_default` true only in the middle case.
- `unassigned_minutes` is the NULL group's **unfiltered** sum (F-3), and `default_weekly_capacity_hours` and **`due_soon_through`** are on the envelope.
- **The fold re-sorts nothing** — the input order survives.
- **`tickets` is byte-identical to F41's** — not one field added, removed or renamed. Assert the serialised ticket dict against a frozen expectation.

### The code

`SeamstressRef` gains `weekly_capacity_hours: int | None`, `capacity_is_default: bool`, `assigned_minutes: int`, `due_soon_minutes: int`; `from_row` gains `load: Mapping[...]` and `tenant_default: int | None` and **keeps deriving `assignable` from the row untouched**.

`AtelierBoardResponse` gains **three**: `unassigned_minutes: int`, `default_weekly_capacity_hours: int | None`, **`due_soon_through: datetime.date`** (F-1 — the client has no date arithmetic and must not invent one; `board()` already holds the horizon). `build` gains `load` and `default_capacity_hours` and `due_soon_through`, and **stays a total function of its arguments with no I/O**, which is what keeps this module's tests in the fast suite.

`AtelierService.board` computes `horizon = today + datetime.timedelta(days=7)` from the `today` it **already has** (`service.py:134`) — **no second clock call and no second date source** — calls `load_by_assignee` inside the existing `tenant_session`, reads `default_capacity_hours(...)` off the settings the router already passes, and passes all three down. Its docstring's *"THREE business statements, and that number is the budget"* becomes **FOUR**, with §Conflicts 8's sizing and **F29 named**.

The router passes the tenant default the same way it passes bands — off `TenantContext.settings`, **zero statements**.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| `load.get(row.id, (0, 0))`'s default | make it `load[row.id]` | the no-tickets seamstress case **RED** with a `KeyError` |
| `due_soon_through` on the envelope | delete it | Task 12's date-rendering test **RED** — and note the client cannot compute it |
| the unfiltered sum for `unassigned_minutes` | use the filtered one | the F-3 case **RED** |

- **Done when**: `make lint` + `make test` green; `test_atelier_board.py` still runs with no Postgres.
- **Commit**: `feat(atelier): the board envelope carries capacity, both load sums and its own horizon`
- **Implements**: D7, D2 (the wire half), F-1.

---

## Task 5 — The capacity route: one 400 for four refusals, `_refreshed`, and the audit row's `from` (D6, D12, D13)
`backend/app/atelier/schemas.py`, `backend/app/atelier/service.py`, `backend/app/atelier/router.py`, `backend/app/db/repositories/staff_users.py`, `backend/app/models/constants.py`, `backend/tests/test_atelier_capacity_service.py` (**✚**), `backend/tests/test_atelier_api.py`

### The failing tests first

**`test_atelier_capacity_service.py`** (fast, fakes):
- **`test_every_ordinary_refusal_is_one_indistinguishable_400`** — a receptionist target, a retired staffer, an unknown id and another tenant's id → **400 / 400 / 400 / 400 with byte-identical bodies**. `_require_seamstress` cannot distinguish them and `by_id` already filters both predicates. **There is no 404 on this route** outside the check-to-UPDATE race.
- **`test_a_strict_int_is_required`** — `true`, `"24"` and `24.0` are each a 400. **Mutation: relax `StrictInt` to `int` → `true` is accepted as a one-hour week → red.**
- `test_setting_the_hours_she_already_has_writes_no_audit_row` — 200, zero rows.
- `test_the_repository_is_never_called_on_the_pure_role_refusal` — `test_floor_service.py`'s shipped assertion shape.

**`test_atelier_api.py`** (fast, extended): `ATELIER_ROUTES` gains the concrete capacity row — which feeds the 401 walk, the wiring walk, the CSRF walk and the `cache-control: no-store` parametrization. **A seamstress gets 403 with the generic body.** `SPEC_ERROR_CODES` stays **set-equal** and **F42 adds nothing to it** — that assertion is D13's proof.

### The code

```python
class SetCapacityRequest(ForbidExtraModel):
    weekly_capacity_hours: StrictInt | None = Field(ge=0, le=MAX_WEEKLY_CAPACITY_HOURS)
    # REQUIRED with no schema default: null is a VALUE (it clears), never an omission.

class SeamstressCapacityResponse(BaseModel):
    id: uuid.UUID
    display_name: str
    assignable: bool
    weekly_capacity_hours: int | None    # RESOLVED (D2), read back through _refreshed
    capacity_is_default: bool
```

⚠ **It does NOT answer a `SeamstressRef`.** That model requires both load numbers, this path has no aggregate, and the only reachable value is `(0, 0)` — which would collapse her bar and drop her «עומס יתר» word for up to five seconds on this feature's own primary surface, at the moment a manager is looking at it.

`StaffUsersRepository.set_weekly_capacity_hours` — one guarded UPDATE, `RETURNING id`, answering through the **shipped** `_refreshed`. **Write no second `_refreshed`.** ⚠ **No `updated_at = now()`** — `staff_users.py:103-104`'s house rule; the trigger owns it.

The service loads the row first (it must, for `_require_seamstress` and for the audit `from`), **captures `before` into a local BEFORE the write**, and writes `ATELIER_CAPACITY_SET` with `{"from": …, "to": …}`, `entity = str(staff_user_id)`, `actor_id = actor.id`, **only when the value actually changed**. Zero rows from the UPDATE → `DomainNotFoundError` → the route's only 404, and it is a race.

The router carries the **second** per-route tightening, `delete`'s shape exactly (`router.py:162-167`):

```python
@router.post(
    "/atelier/seamstresses/{staff_user_id}/capacity",
    dependencies=[Depends(require_role(StaffRole.OWNER, StaffRole.SHIFT_MANAGER))],
)
```

`AuditAction` gains `ATELIER_CAPACITY_SET` — **the eighth member of a seven-member block, not the seventh of six** (§Conflicts 3). No migration: `audit_log.action` is plain `TEXT` with no CHECK.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| `StrictInt` | → `int` | the `true` case turns **200** → **RED** |
| `_require_seamstress` | drop the call | the receptionist case **RED** |
| the per-route `require_role` | drop it | `test_atelier_api`'s seamstress-403 **RED**, and Task 7's per-role set equality **RED** |
| the no-op guard | always write | `test_setting_the_hours_she_already_has…` **RED** |

- **Done when**: `make lint` + `make test` green; the whole HTTP surface exists with no Postgres. **This is the first milestone.**
- **Commit**: `feat(atelier): the per-seamstress capacity route, its single 400 and its audit row`
- **Implements**: D6, D12 (half), D13.

---

## Task 6 — The `atelier` settings block, and the shallow-merge trap (D5, D12)
`backend/app/db/repositories/tenants.py`, `backend/app/boutique/schemas.py`, `backend/app/boutique/service.py`, `backend/app/boutique/validation.py`, `backend/app/boutique/router.py`, `backend/app/models/constants.py`, `backend/tests/test_boutique_validation.py`, `backend/tests/test_boutique_api.py`

**Seven edits across four files** (D5's table), and the seventh — threading `actor: StaffContext` into `update_settings` — is the one a builder skips, because `audit_log.actor_id` is **nullable** (verified `models/audit_log.py:16`) so an actor-less row inserts silently and green while D12's whole justification is *"nobody can say who or when"*.

### The failing tests first

**`test_boutique_validation.py`** (fast, pure) — `validate_atelier_settings`: exactly the five `EffortBand` keys as a **set equality** (the **missing**-key half, which pydantic cannot see); `1 <= v <= MAX_BAND_MINUTES`; the default `None` or `0..MAX_WEEKLY_CAPACITY_HOURS`; **bands need not be distinct or increasing** — a flattened mapping is accepted, and D4 owns the consequence.

**`test_boutique_api.py`** (fast, fake service) — the validation matrix, **each row with its status stated**: missing band key **400**, unknown band key **400**, `true` **400**, `"300"` **400**, `240.0` **400**, `0` **400**, `1441` **400**, default `-1`/`169`/`"30"`/`true` **400**, and the **omitted** default **400** (it is required). ⚠ **The `true`, `"300"` and `240.0` rows are `StrictInt`'s, and every one is a 200 against plain `int`** — that is the whole reason D5 types them strictly. `ROUTES`' existing `("PUT", "/manage/settings", {})` row is untouched.

### The code

```python
class AtelierSettingsUpdate(ForbidExtraModel):
    effort_bands: dict[EffortBand, StrictInt]
    default_weekly_capacity_hours: StrictInt | None   # required; `null` CLEARS it
```

**A FULL REPLACE of the whole `atelier` block, every field REQUIRED, no default anywhere** — because `merge_settings` merges at the **top level only**, so a patch carrying a *partial* `atelier` object replaces the whole key and deletes what it did not name. **One writer, one dialog, one save, both keys, always**, and the request model makes that structural rather than a convention.

⚠ **`StrictInt`, not `int`, and the anti-`bool` rule is vacuous without it.** `ForbidExtraModel` is `extra="forbid"` and nothing else (verified `app/schemas.py:13-18`), so plain `dict[str, int]` coerces `{"half_day": true}` → `1` **before any validator runs** — `validate_atelier_settings`' `isinstance(v, bool)` check would be unreachable code and a one-minute «חצי יום» would be a 200, silently understating every load bar downstream.

⚠ **`jsonb_set` is the wrong reach and is named so nobody takes it**: `jsonb_set(settings, '{atelier,effort_bands}', :v, true)` **silently returns `settings` unchanged when the `atelier` key is absent** — `create_missing` creates the leaf, not the intermediate object. That is every tenant on day one, and it fails with no error. The comment records the correct deep-merge expression for the day a third key arrives.

`merge_settings` gains `atelier: dict[str, Any] | None = None` and one `if atelier is not None: patch["atelier"] = atelier`. **The single atomic `settings = settings || :patch::jsonb` is untouched and no read-modify-write may be introduced.** `SettingsResult` and `SettingsResponse` gain `atelier`; `_settings_result` projects `dict(settings.get("atelier") or {})`; the router passes it through with the shipped `model_dump(exclude_unset=True)` idiom and hands the `staff: Staff` it already binds (`boutique/router.py:57-58`) to the service.

`ATELIER_SETTINGS_UPDATED` carries the **new value and no `from`** — the trail is the history, and computing a diff needs precisely the read-modify-write the atomic statement exists to avoid. ⚠ **It is written in its own transaction, after the merge returns non-`None`**, because `TenantsRepository` opens its own session per method (verified `tenants.py:86`) and nothing can join it. The compromise is one-directional: a crash loses a row and can never invent one.

### Mutation-checks (mandatory) — Task 8 runs the db half

| Test | Mechanism | **MUTATION → RED** |
|---|---|---|
| `test_a_boolean_band_is_refused` | `StrictInt` on `effort_bands` | **relax to `int`** — pydantic coerces `true` to `1`, `validate_atelier_settings` never sees a bool, and the case turns 200 |
| `test_saving_only_the_bands_cannot_clear_the_default` | the **required** `default_weekly_capacity_hours` | **give it `= None` and drop it from the patch when unset** — a bands-only save replaces the whole `atelier` object without the default and silently clears it |
| `test_an_unknown_band_key_is_refused` | `dict[EffortBand, StrictInt]` | **key on `str`** — the unknown key becomes the validator's problem and its set-equality still catches it, so **assert the STATUS SOURCE too** (a `RequestValidationError`, not a `DomainValidationError`) or this mutation is invisible |
| `test_the_settings_audit_row_names_its_actor` | D5 edit #7 | **drop the `actor` parameter** — `actor_id` is nullable, so the row still inserts and only this assertion reds |

- **Done when**: `make lint` + `make test` green. **This is the second milestone** — the whole settings contract with no Postgres.
- **Commit**: `feat(boutique): the atelier settings block — a whole-key replace, strictly typed, audited`
- **Implements**: D5, D12 (half).

---

## Task 7 — The walker and the route tables (D16)
`backend/tests/test_staff_role_gating.py`, `backend/tests/test_atelier_api.py`

**No production code.** Verified shape today: `ATELIER_DELETE` at `:158`, `ATELIER_OPEN` at `:159-167` (seven rows), the seamstress row at `:189` as `frozenset(FLOOR_OPEN | (ATELIER_OPEN - {ATELIER_DELETE}))`, the classifier at `:388`.

```python
ATELIER_CAPACITY = ("POST", "/manage/atelier/seamstresses/{staff_user_id}/capacity")
ATELIER_ELEVATED = {ATELIER_DELETE, ATELIER_CAPACITY}     # NEW — replaces the inline set-literal
ATELIER_OPEN = { …the seven…, ATELIER_CAPACITY }
NON_ELEVATED_REACH[SEAMSTRESS] = frozenset(FLOOR_OPEN | (ATELIER_OPEN - ATELIER_ELEVATED))
```

- **The new row MUST be in `ATELIER_OPEN`** even though it is in nobody's reach. A tightened route is invisible to all three per-role equalities, so the anti-vacuity half (`declared = FLOOR_OPEN | ATELIER_OPEN`) is the **only** thing that would notice the route being deleted.
- **It MUST be split out of the seamstress's row.** The walker classifies on `frozenset.intersection(*role_sets)`, so this route's effective set is `{owner, shift_manager}`; a seamstress row naming it would be one element larger than reality and would **red a correct build on the one test F57's Risk 1 declares untouchable** — the exact situation that gets a test relaxed.
- **⚠ The classifier stays `frozenset.intersection`, never `any(...)`.** The shipped docstring gives the whole argument and this route is the second instance of exactly the shape that breaks under `any`.
- `OWNER_ONLY`, `test_gate_admits_listed_roles` and `test_gates_admit_only_known_roles` need **zero** edits — both gates admit `shift_manager`, `require_role(OWNER, SHIFT_MANAGER)` is already asserted by F41's `delete`, and `known` derives from the live enum.
- **`apps/manage/vite.config.ts` needs NO edit**, and this is stated as a decision rather than an omission. `MANAGE_API` matches the **second** path segment; `atelier` is already the fifteenth of fifteen (verified `:18-19`), and the new route sits under it. `test_spa_serving.py::test_the_manage_dev_proxy_names_every_manage_api_segment` derives the segment set from the live route table and asserts set equality — **so it stays green, and it would red instantly had the route been put on a new second segment.** That failure mode is the one F57's note calls *"the nastiest of the three: production, CI and the suite all stay green while only a developer's machine breaks."*

**Named tests:** the per-role set equality (`reception` and `sales_assistant` reach exactly the three floor routes; `seamstress` reaches those plus the six non-elevated atelier routes and **neither** `delete` **nor** `capacity`); and `ATELIER_OPEN` naming `capacity` so deleting the route reds the anti-vacuity half.

- **Done when**: `make test` green, including `test_spa_serving.py` **unedited**.
- **Commit**: `test(auth): the capacity route joins ATELIER_OPEN and is split out of the seamstress's reach`
- **Implements**: D16.

---

## Task 8 — The forced interleaves, the audit ordering, and the statement count (D3, D5, D6, D12)
`backend/tests/test_atelier_capacity_db.py`, `backend/tests/test_boutique_service.py`

**⚠ `asyncio.gather` is deliberately NOT used for either interleave**, for F34's, F57's and F41's reason verbatim (`test_floor_db.py:251-263`): gather does not **order** two transactions, so the loser most often loads *after* the winner commits, its in-memory instance is already correct, and the branch the test exists to prove goes green **without the mechanism ever being exercised**. The mechanism is `tenant_session`'s own shape — exiting the context manager **is** the commit (`db/tenant.py:25`) — and two nested sessions on one `NullPool` factory take two separate connections.

⚠ **This applies to the settings test too, and the shipped neighbour is the trap.** `test_boutique_service.py:146`'s `test_merge_settings_preserves_concurrently_written_sibling_key` uses `gather` legitimately — its mechanism is `||` over two single-statement UPDATEs. F42's is different: the mutation is *"replace `||` with a Python read-modify-write"*, whose failure depends on both readers seeing a pre-commit snapshot. **F42's test opens both sessions explicitly and orders them**, and carries a comment saying why it does not follow its neighbour.

| # | Test | Mechanism | **MUTATION → RED** |
|---|---|---|---|
| 1 | `test_the_loser_of_two_capacity_writes_renders_the_databases_hours` | `populate_existing=True` inside `StaffUsersRepository._refreshed` | **Drop `populate_existing=True`.** ORM-enabled DML's `evaluate` synchronization has already stamped the SET value onto the identity-mapped instance the loser loaded — it **must** load it, for `_require_seamstress` and the audit `from` — and `expire_on_commit=False` hands it straight back, so the loser's response carries **its own** hours. ⚠ It must be this shape: F57's note records that with only fresh-session tests present, removing the flag changed nothing |
| 2 | `test_an_atelier_patch_does_not_clobber_a_concurrent_profile_write` | `merge_settings`' single atomic `settings = settings \|\| :patch::jsonb` | **Replace with a Python read-modify-write** (`by_id` → mutate the dict → `UPDATE … SET settings = :whole`). Under READ COMMITTED both writers read a snapshot without the other's commit and the last one wins the whole column; `assert merged["profile"] == …` reds. **Explicitly ordered, not `gather`** |
| 3 | `test_the_capacity_audit_row_carries_the_value_it_replaced` | the capture of `before` into a **local, before** the write | **Move the capture after the write.** `evaluate` stamps the new value onto the very instance being read, so `details["from"]` becomes the new hours. F57's note records that this mutation leaves the **fast** suite green, because monkeypatched repositories never stamp anything |
| 4 | `test_two_sequential_atelier_saves_leave_the_second_and_both_audit_rows` | the designed last-write-wins (D5) | not a mutation — the **behaviour** is the assertion. The second save wins entirely, the first's bands are gone, and **both** audit rows exist with their full values. The lost update is designed and the trail is the recovery path, which is what makes D12's no-`from` choice load-bearing |
| 5 | `test_the_settings_audit_row_is_written_only_after_a_successful_merge` | D12's ordering | a merge answering `None` (missing or soft-deleted tenant) writes **no** audit row |
| 6 | `test_the_board_poll_issues_exactly_four_business_statements` | D3's budget | a statement-count assertion around one `board()` call. The bands and the capacity default add **none** — both come off `TenantContext.settings` |
| 7 | `test_a_capacity_write_answers_the_refreshed_row` | happy paths | set, update, and **clear to `null`**; the response carries **no** `assigned_minutes` and **no** `due_soon_minutes` |

- **Done when**: local db suite green; **every mutation performed, observed red, and restored** — and each verified to leave every *other* test green, because a mutation that reds three tests has pinned nothing specific.
- **Commit**: `test(atelier): the two capacity races, the settings interleave and the four-statement budget`
- **Implements**: D3, D5, D6, D12.

---

## Task 9 — The RLS isolation lines (**non-negotiable**)
`backend/tests/test_atelier_isolation.py`

A new column on a tenant table under forced RLS still gets its isolation line — the E9 brief's crown-jewels rule. **App role only**, never the superuser, and with the deliberate vacuity check the shipped suites carry.

- Tenant B's context **cannot set** tenant A's seamstress's capacity — and the refusal is **indistinguishable from a missing row** (a 400 through `_require_seamstress`, because `by_id` returns `None` under B's policy).
- Tenant B's board **cannot see** A's load: `load_by_assignee` under B's context returns nothing of A's.
- A context-free connection sees zero rows.

- **Done when**: local db suite green, and the vacuity check demonstrates the suite fails when the tenant context is set to A's.
- **Commit**: `test(atelier): tenant isolation for the capacity column and the load aggregate`
- **Implements**: the E9 brief's isolation rule.

---

# Part II — the frontend

## Task 10 — The qa-greps baseline, the 40 keys, and the i18n block (D15, C4, C5)
`frontend/apps/manage/src/i18n/he.ts`, `…/i18n/ar.ts`, `…/src/__tests__/i18n.test.ts`

**⚠ FIRST, BEFORE ANY FRONTEND FILE IS WRITTEN:**

```
cd "/Users/mrwen/Documents/Github/Ryan + rawad + mrwen" && make qa-greps > /tmp/f42-qa-greps.baseline 2>&1
```

The unzoned-date review block (`qa-greps.sh:61-71`) greps `apps/manage/src` and prints `review` without setting `status`, so it **cannot fail the build** — which is exactly why it must be diffed by hand. **F42 adds no formatter** (D15: hours are a number and a word; `due_soon_through` is rendered by the shipped `plainDate`, which takes no `Date` and no zone). Task 16 diffs this file.

### The failing tests first

`i18n.test.ts` gains one `describe("F42 capacity keys resolve")` block:

```ts
const HE_F42 = HE_F41.filter(
  ([key]) =>
    key.startsWith("atelier.capacity.") ||
    key.startsWith("atelier.settings.") ||
    key === "atelier.cue.assignedOverload",
);   // NOT spread into HE — HE_F41 already carries these rows
```

- `expect(HE_F42.length).toBeGreaterThanOrEqual(40)` — a floor, F41's shape.
- **`expect(HE_F42.map(([k]) => k)).toContain("atelier.cue.assignedOverload")`** — the assertion that would have caught C4. ⚠ **Not `startsWith("atelier.cue.")`**: that swallows F41's six shipped cue keys (`he.ts:1392-1416`).
- **`HE_F42` is NOT spread into `HE`.** A second `entries(he.translation, startsWith("atelier."))` spread into `HE` would double-count the union and make every `HE`-iterating guard run twice over F41's 95 keys — silently, greenly, and expensively for the next reader. Assert the union's length is unchanged.
- Both new aria pairs carry **WCAG 2.5.3 label-in-name containment**: `capacity.editAria` starts with «שעות», `settings.openAria` with «הגדרות». Asserted, not trusted.
- **No new key's Hebrew contains «168» or «1440»** — they are **server** bounds, and a Hebrew sentence quoting one is a mirror exactly as much as a TypeScript constant is, with none of the protection (`test_frontend_constant_parity.py` scrapes only the two `validation.ts` files). F41 declared `form.error.dueDateHorizon` and **cut it at review** for this rule; `i18n.test.ts:705-719` records why.
- The four shipped guards are cleared **by construction and by assertion**: `/נשלח|תישלח|בדרך/` at **`:890`** (nothing in F42 notifies anybody, and «נודיע לתופרת» on an overload cue would be a lie as well as a red), no-exclamation at **`:886`**, `ar` parity, and no-empty-`ar` at **`:894-906`**.

### The code

The 40 keys from `copy.md`, in **both** bundles, Hebrew standing in untranslated in `ar.ts`. `he.ts:1196`'s stale header — *"F41, the atelier. 95 keys, 0 reused"* — is corrected in passing to name both features and both counts.

⚠ `he.ts:1210-1213`'s standing rule: **any quoted `"atelier.…"` literal anywhere in `apps/manage/src` is scraped as an i18n key and must resolve.** Do not name a `data-testid` or a `data-control` `atelier.capacity.save`.

- **Done when**: `make fe-test` green; the baseline file exists and is committed to the scratchpad, not the repo.
- **Commit**: `feat(manage): the F42 capacity and settings copy, in both bundles`
- **Implements**: D15, C4, C5.

---

## Task 11 — `lib/capacity.ts`: the pure folds, and the ONE `× 60` in the whole feature (D2, D9, D10, F-4)
`frontend/apps/manage/src/lib/capacity.ts` (**✚**), `frontend/apps/manage/src/api.ts`, `frontend/apps/manage/src/__tests__/capacity.test.ts` (**✚**)

**⚠ THE UNIT CONVERSION LIVES HERE AND NOWHERE ELSE.** `capacityMinutes(hours)` is the only `* 60` in F42 — server-side or client-side (Task 3 asserts the server half). `overloaded` is the only site of the comparison. `wouldOverload` contains **no arithmetic and no `60`** and reaches both only through `overloaded`.

### The failing tests first — pure, no DOM

`capacity.test.ts`:

- **`test_capacity_minutes_is_the_only_conversion`** — `capacityMinutes(12) === 720`; `capacityMinutes(0) === 0`; `capacityMinutes(null) === null`. **The hours/minutes catcher: a build that divided instead of multiplying, or that forgot the conversion entirely, gives 0.2 or 12 and reds here.** Paired with an `overloaded` case that is only correct with the multiplication: **capacity 12 h, `due_soon_minutes` 700 → not overloaded; 721 → overloaded.** A missing `× 60` makes 700 > 12 and reddens a healthy row; a `/ 60` makes 721 > 0.2 do the same. Either mistake is dimensionally plausible on inspection and impossible to miss here.
- `loadRatio` — 0 capacity with 0 load (0), 0 capacity with load (**100**), exactly at capacity (100), 4× capacity (**100, CLAMPED**), `null` capacity (no ratio), and a `NaN` input (the `Number.isFinite` guard).
- **`test_null_and_zero_capacity_render_oppositely`** — capacity `0` with 360 due-soon minutes is a full red bar and «עומס יתר»; capacity `null` with 360 is **no bar** and «לא הוגדרה קיבולת». **Mutation: replace `=== null` with `!row.weekly_capacity_hours` → red.**
- **`test_would_overload_at_zero_equals_overloaded`** — `wouldOverload(row, 0) === overloaded(row)` across the **whole** D9 edge table (null capacity, 0/0, 0/load, exactly at capacity, 4×). One assertion that reds on any drift between the bar's predicate and the cue's, **including the `null * 60 = 0` case**. **Mutation: re-inline the cue's comparison and drop the null guard → red.**
- **`test_hours_from_minutes_never_contradicts_the_word`** — at capacity−1, capacity and capacity+1 minutes for a 12 h capacity, the rendered string and `overloaded` never disagree: «12 מתוך 12» never appears beside «עומס יתר». `hoursFromMinutes(minutes) = Math.ceil(minutes / 6) / 10`. **Mutation: `Math.ceil` → `Math.round` → red.** ⚠ Easy to miss because with the five platform bands (all multiples of 30) every sum is a whole half-hour and it never fires — but D5 makes bands tunable to any int in 1..1440 and explicitly not required to be distinct or increasing.
- `sortByRemainingCapacity` — **three groups**: real headroom (`remaining > 0`) by `remaining` DESC; **no-capacity rows by `assigned_minutes` ASC (F-4)**; overloaded rows (`remaining <= 0`) by `remaining` DESC, least-over first. `display_name` then `id` as tiebreaks throughout. **A capacity-`0`-with-load row is in group 3**, not group 1. **The input array is not mutated.** **Mutation: collapse groups 1 and 3 → the overloaded-below-unconfigured assertion reds.**

### The code

`lib/capacity.ts`: `capacityMinutes`, `remainingMinutes`, `loadRatio`, `overloaded`, `wouldOverload`, `hoursFromMinutes`, `sortByRemainingCapacity`. In `lib/` for `lib/stages.ts`'s reason: the panel, the assign `Select` and F40's replacement share it with no import cycle.

⚠ **Every fold branches on `row.weekly_capacity_hours === null`, never on falsiness.** `null` and `0` demand opposite renderings and `if (!row.weekly_capacity_hours) return null` collapses them, rendering the away-and-drowning seamstress as «לא הוגדרה קיבולת».

**F-4, in one line:** group 2 keys on `assigned_minutes` ASC, because that is the number `optionAssigned` («{{hours}} שעות **משויכות**») and `loadNoCapacity` actually display — ordering a group by a number neither surface shows is D10's own argument against itself. The spec's acceptance line («by load ascending») survives unchanged.

`api.ts`: `SeamstressRef` +4 fields; `AtelierBoardResponse` +3; `SetCapacityRequest`; `SeamstressCapacityResponse`; `AtelierSettingsUpdate`; `Settings`/`UpdateSettingsRequest` gain `atelier`; `api.setSeamstressCapacity(staffUserId, hours)`.

- **Done when**: `make fe-test` + `make fe-build` green; **no `60` literal anywhere in `apps/manage/src` outside `lib/capacity.ts`** (a grep, asserted).
- **Commit**: `feat(manage): the capacity folds, the single hours-to-minutes conversion and the three-group sort`
- **Implements**: D2 (client half), D9 (arithmetic), D10, F-4.

---

## Task 12 — `SeamstressPanel.tsx`: the panel, the rows, the bar, the four empty states (D8, D9, F-2, F-3, F-5)
`frontend/apps/manage/src/components/SeamstressPanel.tsx` (**✚**), `frontend/apps/manage/src/__tests__/SeamstressPanel.test.tsx` (**✚**)

### The failing tests first

- The `<section>` is a **named region** and its `<ul>` resolves as `getByRole("list", { name: t("atelier.capacity.heading") })` — **the UNCOUNTED key**, so the name does not churn on every five-second tick — which also catches a row grid built with `role="grid"`.
- **The `<ul>`'s item count equals `seamstresses.length` and equals the `<h3>`'s `{{total}}`, on a board with `unassigned_minutes > 0`** — the unassigned total is a `<p>` **outside** the list. With it inside, a screen-reader user would hear «תופרות, 4 פריטים» after a heading claiming 3.
- **`test_an_overloaded_row_carries_the_word`** — the row's textContent contains her name, both numbers **and «עומס יתר»**. **Mutation: delete the word and keep the red class → red.**
- **`test_the_bar_has_no_widget_semantics`** — `aria-hidden="true"`, **no `role`, no `aria-valuenow`, no accessible name**, and its fill sets **`inline-size`** (never `width`) with a **declared** token class (`bg-gold-strong` / `bg-danger`). ⚠ **Never `bg-accent`** — it is not in `theme.css`'s `@theme`, Tailwind 4 emits no utility for it, and this feature's headline widget would render **colourless in its normal state**. Assert the class list.
- A seamstress with no resolved capacity renders **no bar at all** and «לא הוגדרה קיבולת».
- An `assignable: false` row renders its load, the shipped «תופרת שאינה פעילה», and **no** «שעות» control — the server refuses her (`_require_seamstress`) and a control that always 400s is a trap.
- **All four empty states**: zero seamstresses (owner sees the staff-screen line, a shift manager does **not** — the staff screen is owner-only and a line telling her to go somewhere the gate refuses is the console lying about its own permissions); **zero seamstresses AND `unassigned_minutes > 0` renders the muted empty line AND the unassigned line, in that order**; seamstresses with no capacity anywhere; `unassigned_minutes === 0` renders no unassigned row at all.
- **`test_a_seamstress_sees_no_write_controls`** — `role="seamstress"` renders no «שעות» on any row and no «הגדרות». **Mutation: drop the `ELEVATED.has(role)` guard → she taps, the 403 reaches `runMutation`, `poll.fail` classifies it terminal under the {401,403} rule, and the entire atelier board is replaced by «אין הרשאה» → red** (asserted jointly with Task 14's section test).
- Every control renders at the 44 px floor — **`toHaveClass("min-h-11")` on `Button size="md"` only** (C8), plus a tree-wide assertion that no element carries `min-h-9`.

### The code

F41's shipped column structure verbatim (`AtelierSection.tsx:1027-1053`): a named `<section aria-labelledby>`, a **counted** `<h3 id tabIndex={-1}>` («תופרות · 3»), a **named, uncounted** `<ul tabIndex={0}>`, and the unassigned total as a `<p>` **sibling of the `</ul>`**.

- **`md:max-h-96 md:overflow-y-auto`, unbounded at 375** (C9/F-2). `tabIndex={0}` **unconditional** even though the overflow is `md:`-only — axe's `scrollable-region-focusable` fires on exactly this shape, and *"a resize observer deciding an ARIA-relevant attribute is a mechanism to keep true for a tab stop that costs nothing."*
- **The bar is `DashboardSection.tsx:21-44`'s shape, copied.** Do **not** import it across sections and do **not** promote it to `packages/ui` — the dashboard spec's D10 declined promotion, it is ten lines, and a cross-section component import is worse than a copy. *Promotion is the recorded upgrade at a third caller.*
- **The row is `name · bar · sentence · one Button`.** Nothing else. No sparkline, no per-stage split, no ticket list — the columns are three inches below.
- **The overload word is a `<strong className="font-semibold text-danger">` inside the one `<p>`, never a second `Badge`** — F41 fixes exactly one `Badge` per card and overdue owns it, and a `Badge` here would split the payload into two announced chunks. `text-danger` on `bg-surface` is **6.18:1** (C3), so the word passes AA as text on its own; `font-semibold` is the non-colour half.
- **⚠ NO BIDI HELPER ANYWHERE (F-5).** `isolateLtr` isolates by `indexOf` (verified `booking.tsx:76`), so on «12.1 … מתוך 12» isolating `"12"` matches **inside "12.1"** — a live collision, and `capacity.load` has three numeric interpolations. F41 bars a second helper. **Only the name gets a bare `<bdi>`, in its own element.** The sentence relies on the UBA, whose derivation is in §10.4.
- **The date comes from `due_soon_through` and is rendered by the shipped `plainDate`** — a wire `datetime.date`, split on `-`, never through a `Date` (F-1, and `plainDate`'s own comment is the rule).
- **`unassigned_minutes` is the unfiltered sum** (F-3) — no bar, because nobody has capacity for it, and «בתור» already means that on seamstress rows.
- **No disclosure, no collapse, no `<details>`.** `<details open={x}>` is a **controlled** attribute in React, so an `open` derived from "is anyone overloaded" would re-assert itself on every tick and reopen under the user's hand — the same class of defect as F41's post-mortem focus steal.

- **Done when**: `make fe-test` + `make fe-build` green; **`make qa-greps` output byte-identical to Task 10's baseline**.
- **Commit**: `feat(manage): the seamstress panel, its load bars and its four empty states`
- **Implements**: D8, D9, F-2, F-3, F-5.

---

## Task 13 — The two dialogs (D5, D6, F-6, F-11)
`frontend/apps/manage/src/components/SeamstressPanel.tsx`, `frontend/apps/manage/src/__tests__/SeamstressPanel.test.tsx`

**Both `Modal`s mount at PANEL level** — inside `SeamstressPanel`, siblings of the `<ul>`, **never inside an `<li>`**. F41's C6 rule forbids the `<li>` and nothing further: a repaint that removed the row would unmount a dialog mounted inside it and discard what she typed. Any "section level" reading is wrong.

### The failing tests first

- **«שעות» and «הגדרות» call no API method until the dialog's save is activated.**
- The capacity dialog is **prefilled with `weekly_capacity_hours` when `capacity_is_default` is false and EMPTY when it is true** — so saving without typing cannot silently convert an inherited number into an owned one.
- **F-6: «חזרה לברירת המחדל» is in the BODY, not the footer, and it CLEARS THE FIELD.** Empty ⇒ `null` in both directions. **Assert the footer has exactly two buttons** — `Modal.tsx:54` is `mt-6 flex justify-end gap-3`, hard-coded, no wrap, **no `className` seam**, and three buttons overflow 295 px at 375. Editing `packages/ui` from a call site is barred.
- **F-6's two consequential keys**: `hoursHelp` names the tenant's number; `hoursHelpNoDefault` renders when there is none — the help line would otherwise be a lie on every boutique on day one.
- **F-11: the settings dialog states D4's silent relabel** — `atelier.settings.bandsHelp` = «שינוי ההערכות משפיע רק על כרטיסים חדשים.»
- The settings dialog is **prefilled from the board envelope** — `effort_bands` and `default_weekly_capacity_hours` are already on the wire, so it opens with **no read of its own**. Save sends the **whole** `atelier` block, always.
- **Nothing mutates on `change`.** Every `Input` sets draft state and a footer `Button` commits.
- **`min={0}` and `inputMode="numeric"` stay; `max={168}` is CUT** — that is a server bound (D15), and the dialog renders the server's 400.
- **`test_an_unmapped_400_renders_the_hebrew_default`** — the alert carries `atelier.capacity.error.server`, never `response.data.error.message`'s English. The concrete case is `_require_seamstress`'s literal `"staff_user_id must be a live seamstress"` (verified `service.py:517`), and `main.py:949-953` returns `str(exc)`. **Mutation: replace the `default:` branch with `errorMessage(error)` → red.**
- Submitting: the confirm `Button` carries `loading` (which also disables it); **the fields stay enabled** so a slow network does not eat a correction.
- A server error mapping to no field renders **one alert inside the dialog**, above the footer, `role="alert"` and focused, and **the dialog stays open** — the callback resolved `false`.
- **`test_a_capacity_save_does_not_change_the_rendered_load`** — on success the console patches **only** `weekly_capacity_hours`, `capacity_is_default` and `assignable` onto the held row. `assigned_minutes` and `due_soon_minutes` keep their last-tick values, so a save never collapses her bar or drops her «עומס יתר» word.

### The code

Both dialogs use D8's callback contract, which **resolves and never rejects**:

```ts
onSaveCapacity(staffUserId: string, hours: number | null): Promise<boolean>
onSaveAtelierSettings(patch: AtelierSettingsUpdate): Promise<boolean>
onDialogOpenChange(open: boolean): void
```

A rejecting promise would make the panel duplicate `runMutation`'s catch and put a second `poll.fail` call site in the feature.

- **Done when**: `make fe-test` + `make fe-build` green.
- **Commit**: `feat(manage): the capacity and atelier-settings dialogs, both at panel level`
- **Implements**: D5 (client), D6 (client), F-6, F-11.

---

## Task 14 — `AtelierSection`: the insertion point, the callbacks, `dialogOpen`, the sorted `Select` and the overload cue (D8, D10, D11, C2, C7)
`frontend/apps/manage/src/components/AtelierSection.tsx`, `frontend/apps/manage/src/__tests__/AtelierSection.test.tsx`

⚠ **`restoreRef` / `captureFocus` / `boardCommit` (`:165-184`, `:234+`, `:343+`) are NOT touched, generalised or extended, and NO focus code for this feature lives in this file.** Any edit to that block is a review stop.

### The failing tests first

- **The panel renders in the zero-ticket `EmptyState` branch**, above the `EmptyState`, with every seamstress at «0 שעות» — that branch replaces both the columns and the rail (`:961-972`), and it is the branch a brand-new boutique is in, i.e. **both** of D2's "first thing a new boutique sees" states.
- **The pause control is still the first stop inside the section** — F41's D17 / SC 2.2.2, non-negotiable.
- **The assign `Select`'s options appear in remaining-capacity order and each carries its hours. Mutation: drop the sort → red.**
- **The three option strings are composed from `optionRow` / `optionRemaining` / `optionAssigned` / `over` and contain no Hebrew literal in TSX** — **including the « · » separator**, which is `optionRow`'s own interpolation. F41 renders `{row.display_name}` alone here and declares no key of this shape, so all three would otherwise ship as bare Hebrew literals outside the `ar` parity guard and outside `HE_F41`'s prefix fold. ⚠ `<option>` takes no markup, so `isolateLtr` type-errors and `dir="ltr"` reverses the name: the numeral goes **before** its Hebrew unit word and never beside Latin text.
- An assign that pushes the target over capacity announces `atelier.cue.assignedOverload`; one that does not announces `atelier.cue.assigned`. Asserted on `getByRole("status")`'s **textContent**.
- **`test_recommitting_the_current_assignee_never_announces_overload`** — the clause is gated on `ticket.assigned_staff_user_id !== targetId`. `due_soon_minutes` is her **pre-write** load and already includes anything she holds; the shipped commit fires whenever a draft exists (`disabled={assignDraft === undefined}`, verified `:1531`) and the `Select`'s value defaults to the current assignee (`:1514`), so **arrowing away and back and committing sends a no-op assign**. Without the gate the console adds minutes it has already counted and announces a false overload **with no colleague and no race**.
- **Nothing is blocked**: an overloaded seamstress is still selectable, the assign still answers 200, and no confirm dialog appears.
- **`test_a_terminal_defers_while_a_panel_dialog_is_open`** — a 401 tick while the settings dialog is open does **not** unmount it. **Mutation: drop the panel's dialogs from `dialogOpen` → a settings dialog holding six edited band values is discarded → red.**

### The code

**The insertion point, C2's corrected sketch** — one conditional, above all four shipped board branches, below the cue.

`AtelierSection` implements both save callbacks with the shipped `runMutation` (`poll.bump()`, `mutationsRef`, the `.finally()` re-arm, `poll.fail(error)`), **returning a boolean and never rejecting**; ORs the panel's reported dialog state into `dialogOpen` (`:212`), which both the terminal render (`:782`) and the terminal focus effect (`:338`) already gate on; passes `role`; sorts and relabels the assign options; and adds the cue's overload clause through **`wouldOverload(target, ticket.effort_minutes)`** — **no arithmetic and no `60` at this call site**.

**C7, recorded, not built:** after a successful settings save nothing is patched into the held envelope. Every rendered default and every `bandLabel` is the previous mapping's until the next tick (≤5 s, `usePoll.ts:290`). One row in §6, no code.

- **Done when**: `make fe-test` + `make fe-build` green; `FloorPanel.test.tsx`, `BoardSection.test.tsx` and `StaffSection.test.tsx` pass **unedited** — an assertion, not a hope.
- **Commit**: `feat(manage): the panel wired into the atelier board, the sorted assign picker and the overload cue`
- **Implements**: D8, D10, D11, C2, C7.

---

## Task 15 — The a11y contract and **both** focus directions (D9, D14)
`frontend/apps/manage/src/components/SeamstressPanel.tsx`, `frontend/apps/manage/src/__tests__/SeamstressPanel.test.tsx`, `…/__tests__/AtelierSection.test.tsx`

**⚠ THIS REPO HAS SHIPPED A FOCUS-DROPS-TO-`<body>` DEFECT FIVE TIMES (F56, F34, F57, F57's own vacuous test, F41) AND AXE WALKED PAST EVERY ONE**, because axe cannot see a focus move that never happened. F41's post-mortem adds the second half: **the naive fix creates a focus STEAL in the other direction**, and an adversarial verifier caught it after the first fix shipped green.

**⚠ EVERY TEST IN THIS TASK MUST BE RUN BOTH WAYS, SEVERAL TIMES EACH:**

```
# 1. in the full suite
cd "…/Frontend" && pnpm -r --if-present test
# 2. FIRST IN A WORKER, IN ISOLATION — repeat at least five times
cd "…/Frontend/apps/manage" && for i in 1 2 3 4 5; do pnpm vitest run src/__tests__/SeamstressPanel.test.tsx; done
```

**F41 shipped a full-suite-green focus test that CI failed**, and the difference was measured at **exactly one event-loop turn** (an A/B probe: zero extra turns strands focus, one extra turn restores it). Local full-suite green is **luck, not correctness**. If the two modes disagree, the test is wrong or the code is — investigate, do not average.

### The three assertions that carry the legal load and may not be cut

1. **Both focus directions.**
   - **`test_saving_when_her_row_has_left_the_payload_moves_focus_to_the_heading`** — a seamstress leaves the union when she is retired **and** her last undelivered ticket is delivered (`alteration_tickets.py:400-403`). If that lands between opening the dialog and saving, the trigger has unmounted and `<dialog>`'s auto-restore hits `<body>`. **Assert `document.activeElement` IS the panel `<h3>`**, never merely that the node exists. **Mutation: delete the fallback → focus is `<body>` → red.**
   - **`test_saving_when_she_moved_focus_herself_does_not_yank_it_back`** — the **steal** direction. **Mutation: drop the `activeElement === document.body` guard → red.**
   - ⚠ **jsdom does not blur a disabled element**, so a test that leans on that is vacuous — F57's own vacuous focus test is the recorded instance.

   The mechanism, owned by `SeamstressPanel` (which holds both the trigger and the heading ref) — `AtelierSection` touches no focus code for this feature:

   ```ts
   const ok = await onSaveCapacity(id, hours);   // resolves, never rejects
   if (!ok) return;                              // the dialog stays open, the alert renders
   closeDialog();
   setSaveCount((n) => n + 1);                   // monotonic

   useEffect(() => {
     if (saveCount === 0) return;
     if (document.activeElement === document.body) headingRef.current?.focus();
   }, [saveCount]);                              // runs AFTER React has committed the repaint
   ```

   - **Keyed on the counter and NOT on the payload** — a state setter bails out of a reference-identical value, so keying on the data would silently skip the one repaint the guard is waiting for (`AtelierSection.tsx:343+` records exactly this about `boardCommit`).
   - **⚠ No commit stamp, and adding one would be machinery for a race this shape does not have.** F41's shipped fix stamps intents with a board-commit count because its restore fires on **poll repaints**, which arrive with no user action and can outlive the user's own focus move. This fires **only on a successful save, in the same turn, and only when focus is already nowhere.** Stated because copying F41's mechanism wholesale is the obvious wrong move.

2. **Overload is never colour-only.** The row's textContent, and the mutation that deletes the word while keeping the class. **The word and the colour are set by the same predicate** (`overloaded`), which is what makes "never colour-only" a structural property rather than a rule someone has to remember: a red-without-word build cannot be written.

3. **The bar has no widget semantics** — `aria-hidden`, no `role`, no `aria-valuenow`, no accessible name. **axe will not catch a wrongly-roled `progressbar`; this assertion is the only thing that does.**
   - **Why not `role="progressbar"`**: it is ARIA's *"progress of a task that takes a long time"*, and nothing here progresses toward completion. Its honest form needs `aria-valuetext` byte-identical to the visible sentence, putting one fact in the tree twice — and hiding the sentence to fix that makes visible and announced content diverge (the WCAG 2.5.3 failure).
   - **Why not `role="meter"`**: semantically right, **declined for support** — NVDA and JAWS announce it inconsistently. Recorded as the role to revisit if this repo's a11y bar moves to ARIA 1.2 with measured AT support.

### The keyboard grid — a concrete DOM-order walk, not "fully operable"

**`test_the_concrete_tab_order`** (this is what pins D8's *"keyboard-navigable by construction"* claim, and it replaces a phrasing that would have been written as a tautology or skipped):

```
pause / resume            (STILL the first stop — SC 2.2.2)
→ the <ul> itself         (tabIndex={0}; the <h3> is tabIndex={-1}, a target, NOT a stop)
→ row 1 «שעות» → row 2 «שעות» → row 3 «שעות»   (render order = sort order)
   (the unassigned <p> is text — no stop)
→ «הגדרות»                (LAST stop in the panel)
→ «כרטיס חדש» → the rail → F41's columns, unchanged
```

`userEvent.tab()` walks it. **Enter on «שעות» opens the dialog and calls no API method.** Inside: the number `Input` → «חזרה לברירת המחדל» → «ביטול» → «שמירה». **Esc dismisses without writing**, and focus returns to the trigger by itself.

**A non-elevated viewer's pass is shorter and still complete**: the `<ul>` is her only stop, and she reads every row's text on the way past it. Nothing is hidden from her; only the two write controls are absent.

**`test_axe_reports_zero_violations`** on the panel and on both open dialogs — **explicitly not sufficient**, and the comment says so: axe has no rule for a focus move that never happened, no rule for a wrongly-roled `progressbar`'s *meaning*, and no target-size rule at the level this repo runs it.

- **Done when**: `make fe-test` green; **both run modes green, five times each**; every mutation performed, observed red, and restored.
- **Commit**: `test(manage): the panel's a11y contract, its keyboard walk and both focus directions`
- **Implements**: D9, D14.

---

## Task 16 — Rebase, renumber, the gates, and the run report
No files.

Run the shipping checklist and the full gate below, report what ran and what passed, and carry forward:

- **The migration number.** State the number the branch was **built** at, the number it **shipped** at, and the `alembic heads` output that decided the second. Built at `head + 1` from `0021`. **⚠ F37's `.worktrees/sos-paging` migration is already numbered `0021` and must renumber too — if it lands first, F42 goes to `0023`.**
- **Risk 1 — the denominator is self-reported and nothing verifies it.** A seamstress who works 20 hours but is recorded at 40 gets a green bar while she drowns. No clock-in, no roster, no throughput measurement. **This is E9's estimate-quality risk one level up**: bad estimates make the numerator lie and a bad capacity makes the denominator lie, and the product cannot tell either. *The pilot conversation should say this out loud rather than let her discover it. Trigger: F44, then F40.*
- **Risk 3 — a FOURTH business statement on a five-second poll, derived and not measured.** ≈7 statements, ≈12 round trips, 3 pool checkouts per tick per device on the atelier screen — against F41's ≈6 / ≈11 / 3. It **replaces rather than adds to** F57's number, because the console renders one section at a time. `tenants.by_slug` is still uncached per request (*"caching is deliberately deferred to E5"*) and is still the cheapest lever. **F29 must be handed this number, not left to discover it.** *Recorded remedy: D3's `LEFT JOIN` fold, with the reason it was refused.*
- **Risk 4 — `settings["atelier"]` now has two sub-keys, ONE code path and NO concurrency control, and "one writer" must not be read as "one actor".** Two shift managers with the dialog open **silently lose each other's work** — full replace, unconditional UPDATE, no version, no if-match, both admitted by the shipped router gate. That is designed; the recovery path is the audit trail, which is why D12's full-value, no-`from` payload is load-bearing. **The blast radius is the ruler every future estimate in the boutique is cut with**, and D4's whole point is that a mis-set band cannot be corrected retroactively. **The first feature to add a third key under `atelier` (F43, F44) must join the block or deepen the merge.**
- **Risk 6 — a boutique whose owner sews still cannot be given hours or a ticket.** She must hold a `seamstress` account and give up owner-only staff CRUD, terms and the gateway, or leave her own work unassigned and invisible to every bar. **A real ceiling for a two-person pilot.** *Trigger: the first tenant with fewer than three staff.*
- **§Conflicts 13 — the bar diverges from LOOP-STATE's literal formula, and the reversal is one line.** The ruling says *"the sum of undelivered effort"*; the bar's numerator is `due_soon_minutes`. The ruling's number ships unchanged as `assigned_minutes`, on the wire and on screen. **If the ruling is to be read word-for-word on the bar as well, point `loadRatio` at `assigned_minutes` in `lib/capacity.ts`.** Recorded so the choice stays available rather than buried.
- **§Conflicts 14 — the largest product divergence in the feature.** The e9 brief says *"not yet `ready_at`"*; the ruling says *"not yet delivered"* and governs. So **a garment finished, QC'd and hanging on the rack counts in full against the seamstress who made it until the bride collects it.** A seamstress with ten finished-but-uncollected gowns reads red with an empty bench, and D10's sort then routes work away from the only person free to take it. **If the pilot reports it, the fix is a one-clause change to D3's predicate.**
- **§Conflicts 15 — E9's degradation clause names the tenant's OPENING-HOURS WEEK as the roster-free fallback and F42 declines it.** A shop open 60 hours a week does not mean a seamstress works 60, and a denominator wrong by 3× in the reassuring direction is worse than no denominator. `availability_rules` remains available to F40.
- **F-7 reassigned: F42 declines F41's F-2 hand-off of the 720 px console-width decision.** No matrix ships and the list fits. **New owner: F44** (`LOOP-STATE.md:1684-1689`, `deps: [F34, F41, F42]`).
- **Risk 9 — a retired seamstress with live tickets is visible, has a load, has a bar and cannot be edited.** F42 makes it *more legible* rather than correct: her row now quantifies what reassigning costs. The correcting sweep stays unbought.
- **Risk 10 — `weekly_capacity_hours` is personal-adjacent data on `staff_users`**, which is already in whatever retention F20 assigns it, and #34/#35's offboarding scrub blanks personal fields on that row. **No new F20 entry is created and none is needed** — recorded so that conclusion is stated rather than assumed. *Owner: F20/F21 confirm at the audit.*
- **Risk 11 — no E2E covers the poll loop, and the panel now rides it.** Three loops in the console, all unit-tested with fake timers against a mocked `api`. F34's Risk 8, widened again. *Trigger: F58's `/manage/**` interception harness, now shipped — the first feature that can use it should.*
- **`design.md` F-9 — the `poll.*` rename is still declined**, for the reason that has not changed: it would edit components that must pass unedited. *Owner: team. Trigger: F59, as a standalone i18n PR touching no component logic.*
- **F60 is the only floor-management entry left queued**, and LOOP-STATE names it the one to leave if the run has to stop early.

No push, no PR from this task — the orchestrator owns review and shipping.

### Shipping checklist — run in this order, top to bottom

1. **`git status --short` is clean** and `git log -p -- backend/tests/conftest.py` shows **no F42 commit**. (There is nothing to revert — the escape hatch is shipped — but assert it anyway.)
2. **`git show --stat` on every commit** confirms the **lowercase** pathspecs landed.
3. **No lower-numbered migration is still unmerged.** F37 is in flight and its number is already collided.
4. `git fetch origin && cd "…/Backend" && uv run python -m alembic heads` **on a checkout of `origin/main`**. Note the number.
5. **Renumber to head + 1** — three edits: the filename, the `revision` literal, the `down_revision` literal. **Amend the migration commit** (it is the branch tip by Task 1's instruction).
6. **Rebase onto `origin/main`.** Re-run `alembic heads` **on the rebased branch** and confirm a **single** head. F19's fast guard does this in `make test` too — **but only after the rebase.**
7. **Re-run the full db suite on the rebased branch** — `dropdb -h /tmp -U mrwen f42_test && createdb -h /tmp -U mrwen f42_test`, then `pytest -m db`.
8. **Full local gate, all six targets green.**
9. **`make qa-greps` output byte-identical to the Task 10 baseline.** Diff it.
10. `grep -rn "bg-accent\|role=\"progressbar\"\|role=\"grid\"\|roving" frontend/apps/manage/src/components/SeamstressPanel.tsx` returns **nothing**.
11. `grep -rn "\* 60\|60 \*" frontend/apps/manage/src` returns **only `lib/capacity.ts`**; `grep -rn "60" Backend/app/atelier/` returns no arithmetic.
12. `git diff --stat origin/main -- frontend/packages/ui frontend/apps/manage/src/lib/usePoll.ts frontend/apps/manage/src/lib/stages.ts backend/tests/test_spa_serving.py frontend/apps/manage/vite.config.ts` is **empty**.
13. `git diff origin/main -- frontend/apps/manage/src/components/AtelierSection.tsx | grep -n "restoreRef\|captureFocus\|boardCommit"` returns **nothing**.
14. **Task 15's focus tests run first-in-worker in isolation, five times, green.**
15. Open the PR. The three gating jobs are `Backend (lint, types, tests)`, `Frontend (lint, types, build)`, `Frontend E2E (Playwright + axe)`.

- **Commit**: none (the renumber is an amend).

---

## Verification — the full local gate sequence

```
export TEST_POSTGRES_SUPERUSER_URL="postgresql+asyncpg://mrwen@127.0.0.1:5432/f42_test"

make lint      # Backend: ruff check . && ruff format --check . && mypy app tests
               #   + Frontend: pnpm -r lint && pnpm -r typecheck
               #   + bash Frontend/scripts/qa-greps.sh
make test      # Backend: pytest -m "not db" -q   (includes F19's single-head guard)
dropdb -h /tmp -U mrwen f42_test; createdb -h /tmp -U mrwen f42_test
cd Backend && uv run pytest -m db -q --ignore=tests/test_media_upload_s3.py
make fe-test   # Frontend: pnpm -r --if-present test
make fe-build  # Frontend: pnpm -r build
make e2e       # Frontend: pnpm -r build && playwright install chromium && pnpm e2e
```

**Green looks like:**

- **`make lint`** — ruff clean, `ruff format --check` clean, **mypy zero errors over `app` and `tests`**, `pnpm -r lint` and `pnpm -r typecheck` clean across all four workspace packages, and `qa-greps.sh` **exit 0 printing exactly the Task 10 baseline**.
- **`make test`** — `test_atelier_capacity.py`, `test_atelier_capacity_service.py`, `test_atelier_board.py`, `test_atelier_api.py`, `test_boutique_api.py`, `test_boutique_validation.py` green; **`test_staff_role_gating.py` green with `ATELIER_ELEVATED`**; **`test_spa_serving.py` green UNEDITED**; `test_frontend_constant_parity.py` passes **unedited** (no client constant mirrors a server bound); the db modules **collected and deselected**; the single-head guard green. ⚠ Two `test_config.py` failures are always false locally.
- **the db suite** — the captured baseline **plus** F42's cases in `test_migrations.py`, `test_atelier_capacity_db.py`, `test_boutique_service.py` and `test_atelier_isolation.py`. `test_media_upload_s3.py` is ignored.
- **`make fe-test`** — `capacity.test.ts`, `SeamstressPanel.test.tsx`, `AtelierSection.test.tsx`, `i18n.test.ts` green; **axe at zero violations on the panel, both dialogs and all four empty states**; **every mutation in Tasks 11–15 performed and restored**; `FloorPanel.test.tsx`, `BoardSection.test.tsx`, `StaffSection.test.tsx`, `Nav.test.tsx` and `ProfileSection.test.tsx` pass **unedited**.
- **`make fe-build`** — both apps build; no unused-import or unused-variable TS error.
- **`make e2e`** — existing specs unchanged. **F42 adds none.**
- **CI additionally** — the same db suite against Testcontainers, where the captured literals are re-read off the CI server rather than off the local one. ⚠ **A first CI red on a test bug is budgeted** (`.memory/boutique-ci-first-run-surprises.md`); check `continue-on-error` on the job before believing it.

---

## What a local run CANNOT prove

| Task | The local run proves | CI-only, or nothing proves it |
|---|---|---|
| 1 | the column, the CHECK, the partial index, the round trip — **all of it, against real Postgres 16** | that the deparsed literals are **byte-identical on the CI server's Postgres build**. They should be — same 16.x deparser — and the assertion **re-reads** rather than transcribes, so a difference is a red test and not a silent pass |
| 3, 8 | the two sums, the audit ordering, and every interleave against real transactions | that the interleave holds under CI's container timing. The harness does not depend on timing — it depends on `tenant_session`'s commit-on-exit — so this is low risk and is stated rather than assumed |
| 8 | the four-statement budget as a **count** | ⚠ **nothing here measures LATENCY.** F29's k6 pass is the only thing that can say whether the fourth statement matters; the number is derived by F34's D3 method, not observed |
| 9 | the isolation lines in full, **including the vacuity check** | the same on CI's container-superuser / app-role split |
| 12–15 | every state, every focus destination, the keyboard walk, axe — **in jsdom** | ⚠ **jsdom has no layout engine**, so every 44 px claim is a **class** assertion and never a measurement, and F-2's row-height arithmetic (109/151 px) is **derived and unmeasured** — the `md:max-h-96` bound is a judgement, not a fit test; ⚠ **jsdom does not blur a disabled element**, which is precisely how a vacuous focus test shipped once; ⚠ **the one-event-loop-turn difference that reddened F41 on CI is invisible to a full-suite local run** — which is why Task 15 mandates first-in-worker isolation, five times |
| 12, 15 | that the bar carries no role and the word is in the text | ⚠ **that a real screen reader announces the sentence the way §10.4's UBA derivation says it will.** F-5 removes the bidi helper on an argument about the algorithm; nothing automated verifies the rendered visual order of a three-number Hebrew sentence. **The 2.84:1 fill contrast is likewise a calculation, not an observation** |
| — | — | ⚠ **RTL rendering.** The design deck's diagrams are drawn LTR for legibility and the shipped console is RTL. A builder implementing the drawn order ships a **mirrored panel that passes axe, passes every named vitest assertion, and reads backwards to the only users who will ever see it.** `inlineSize` is the mechanism; no automated check catches getting it wrong, because `width` renders too |
| — | — | **the poll loop against a real backend.** Three loops, none e2e-covered. **F58 shipped the `/manage/**` interception harness** and this is the first feature that could use it — recorded as the trigger, not built here |

**Task 5 is the first milestone** (the whole capacity HTTP surface with no Postgres) and **Task 6 is the second** (the whole settings contract with no Postgres).

---

## Task-by-task file manifest

| Task | New (✚) | Modified |
|---|---|---|
| 0 | — | `.planning/plans/seamstress-capacity.md`, `.planning/specs/seamstress-capacity.md`, `.planning/design/screens/seamstress-capacity/design.md`, `…/copy.md` |
| 1 | `backend/migrations/versions/00NN_seamstress_capacity.py` | `backend/app/models/staff_user.py`, `backend/tests/test_migrations.py` |
| 2 | `backend/tests/test_atelier_capacity.py` | `backend/app/atelier/stages.py` |
| 3 | `backend/tests/test_atelier_capacity_db.py` | `backend/app/db/repositories/alteration_tickets.py` |
| 4 | — | `backend/app/atelier/schemas.py`, `…/service.py`, `…/router.py`, `backend/tests/test_atelier_board.py` |
| 5 | `backend/tests/test_atelier_capacity_service.py` | `backend/app/atelier/schemas.py`, `…/service.py`, `…/router.py`, `backend/app/db/repositories/staff_users.py`, `backend/app/models/constants.py`, `backend/tests/test_atelier_api.py` |
| 6 | — | `backend/app/db/repositories/tenants.py`, `backend/app/boutique/schemas.py`, `…/service.py`, `…/validation.py`, `…/router.py`, `backend/app/models/constants.py`, `backend/tests/test_boutique_validation.py`, `…/test_boutique_api.py` |
| 7 | — | `backend/tests/test_staff_role_gating.py`, `…/test_atelier_api.py` |
| 8 | — | `backend/tests/test_atelier_capacity_db.py`, `…/test_boutique_service.py` |
| 9 | — | `backend/tests/test_atelier_isolation.py` |
| 10 | — | `frontend/apps/manage/src/i18n/he.ts`, `…/i18n/ar.ts`, `…/src/__tests__/i18n.test.ts` |
| 11 | `frontend/apps/manage/src/lib/capacity.ts`, `…/src/__tests__/capacity.test.ts` | `…/src/api.ts` |
| 12 | `frontend/apps/manage/src/components/SeamstressPanel.tsx`, `…/src/__tests__/SeamstressPanel.test.tsx` | — |
| 13 | — | `…/src/components/SeamstressPanel.tsx`, `…/src/__tests__/SeamstressPanel.test.tsx` |
| 14 | — | `…/src/components/AtelierSection.tsx`, `…/src/__tests__/AtelierSection.test.tsx` |
| 15 | — | `…/src/components/SeamstressPanel.tsx`, `…/src/__tests__/SeamstressPanel.test.tsx`, `…/src/__tests__/AtelierSection.test.tsx` |
| 16 | — | — (the renumber is an amend) |

**NEVER MODIFIED, and that is an assertion the review should check:**
`backend/tests/conftest.py` · `backend/tests/test_frontend_constant_parity.py` · `backend/tests/test_spa_serving.py` (it is the guard, and **`vite.config.ts` does not change either** — D16) · `backend/tests/test_tenant_isolation.py` · `backend/app/atelier/validation.py` (the rejected finding's module — the constant lives in `stages.py`) · `backend/app/floor/**` · `backend/app/catalog/**` · `backend/app/db/repositories/customers.py` · **`frontend/apps/manage/vite.config.ts`** · **`frontend/apps/manage/src/lib/usePoll.ts`** (four callers — any edit is a review stop) · `…/src/lib/stages.ts` · `…/src/lib/jerusalem.ts` · `…/src/lib/booking.tsx` (F-5: no new bidi helper and no edit to the two shipped ones) · `…/src/App.tsx` · `…/src/components/FloorPanel.tsx` · `…/BoardSection.tsx` · `…/StaffSection.tsx` · `…/DashboardSection.tsx` (the `Bar` is **copied**, never imported or promoted) · **`frontend/packages/ui/**`** (zero new components, zero new variants, **no `className` seam on `Modal`'s footer** — F-6 is the workaround) · `frontend/scripts/qa-greps.sh` · `frontend/e2e/**` · **`AtelierSection.tsx`'s `restoreRef` / `captureFocus` / `boardCommit` block**.

---

## Testing plan → spec acceptance criteria

| Spec criterion | Where |
|---|---|
| The nullable `INTEGER` column, its CHECK pinned **byte-identical from CAPTURED definitions**, the partial index's `indexdef`, `-1` and `169` refused, up **and** down | `test_migrations.py` (db) |
| `alembic heads` prints exactly one head | `test_exactly_one_migration_head` (fast) — **only meaningful after the rebase** |
| Load counts every undelivered stage and an undone delivery; excludes delivered, soft-deleted and foreign | `test_atelier_capacity_db.py` (db) |
| **The 7-day FILTER, day 7 in / day 8 out, overdue in both** — mutation: delete the FILTER | `test_atelier_capacity_db.py` (db) |
| **A truncated board still reports exact load** — mutation: fold in Python | `test_atelier_capacity_db.py` (db) |
| **The server never multiplies hours by minutes** | `test_atelier_capacity_db.py` (db) + a grep in the checklist |
| The NULL group reaches the wire as `unassigned_minutes` (the **unfiltered** sum) | `test_atelier_capacity_db.py` (db) + `test_atelier_board.py` (fast) |
| A seamstress with no tickets is `(0, 0)` and does not vanish; one with only far-future work is `due_soon_minutes: 0` | `test_atelier_board.py` (fast) |
| Resolution from her column, else the default, else `null`; `capacity_is_default` true only in the middle case; a corrupt stored default resolves to `null` | `test_atelier_capacity.py` (fast) |
| **A stored `0` is hers with `capacity_is_default: false`** — mutation: `is not None` → `or` | `test_atelier_capacity.py` (fast) |
| A tenant with no `atelier` key resolves every seamstress to `null` — **no platform default** | `test_atelier_capacity.py` (fast) |
| **`due_soon_through` is on the envelope** (F-1) and the client renders it through `plainDate` | `test_atelier_board.py` (fast) + `SeamstressPanel.test.tsx` |
| The poll issues exactly **four** business statements | `test_atelier_capacity_db.py` (db, statement count) |
| **An `atelier` patch leaves `profile` and `toggles` intact** — mutation: `\|\|` → Python read-modify-write, **explicitly ordered, never `gather`** | `test_boutique_service.py` (db) |
| The `atelier` validation matrix, **each row with its status** | `test_boutique_api.py` + `test_boutique_validation.py` (fast) |
| **`{"half_day": true}` is a 400** — mutation: `StrictInt` → `int` | `test_boutique_api.py` (fast) |
| **Saving only the bands cannot clear the default** — mutation: `= None` + drop-when-unset | `test_boutique_api.py` (fast) |
| **Two sequential whole-block saves: the second wins and BOTH audit rows exist with full values** | `test_boutique_service.py` (db) |
| The settings audit row is written only after a successful merge and **names the actor** | `test_boutique_service.py` (db) |
| `POST …/capacity` sets, updates and clears; the response is the **refreshed** `SeamstressCapacityResponse` with **no** load numbers | `test_atelier_capacity_db.py` (db) |
| **400 / 400 / 400 / 400, byte-identical bodies**, and no 404 outside the race | `test_atelier_capacity_service.py` (fast) + `test_atelier_isolation.py` (db) |
| **The loser renders the database's hours** — mutation: drop `populate_existing=True` | `test_atelier_capacity_db.py` (db, forced interleave) |
| **The audit row carries `from`** — mutation: capture after the write | `test_atelier_capacity_db.py` (db) |
| The no-op writes no audit row; the repository is never called on the pure-role refusal | `test_atelier_capacity_service.py` (fast) |
| A seamstress gets 403 with the generic body; `SPEC_ERROR_CODES` still **set-equal**, F42 adding none | `test_atelier_api.py` (fast) |
| **Per-role set equality**; `ATELIER_OPEN` names `capacity` | `test_staff_role_gating.py` (fast) |
| The dev proxy's segment set still equals the route table's, **with no `vite.config.ts` edit** | `test_spa_serving.py` (fast, **unedited**) |
| Tenant B cannot set A's capacity nor see A's load | `test_atelier_isolation.py` (db) |
| **`capacityMinutes` is the only conversion; a `/60` or a missing `*60` reds** | `capacity.test.ts` |
| `loadRatio`'s six edges including the clamp and the `isFinite` guard | `capacity.test.ts` |
| **`null` vs `0` capacity render oppositely** — mutation: `=== null` → falsiness | `capacity.test.ts` + `SeamstressPanel.test.tsx` |
| **`wouldOverload(row, 0) === overloaded(row)` across the whole edge table** — mutation: re-inline the cue's comparison | `capacity.test.ts` |
| **`hoursFromMinutes` never lets the sentence read equal beside «עומס יתר»** — mutation: `ceil` → `round` | `capacity.test.ts` |
| The three sort groups, group 2 on **`assigned_minutes` ASC** (F-4), the tiebreaks, no input mutation — mutation: collapse groups 1 and 3 | `capacity.test.ts` |
| The assign options in remaining-capacity order, each carrying its hours, **composed from keys with no Hebrew literal in TSX** | `AtelierSection.test.tsx` + `i18n.test.ts` |
| The overload cue fires on a real move and **never on a re-commit of the current assignee** | `AtelierSection.test.tsx` |
| **Nothing is blocked** — the overloaded option is selectable, 200, no confirm | `AtelierSection.test.tsx` |
| **The panel renders in the zero-ticket `EmptyState` branch**; a 401 defers while a panel dialog is open | `AtelierSection.test.tsx` |
| **A capacity save does not change the rendered load or the overload word** | `SeamstressPanel.test.tsx` |
| **Overload carries the word** — mutation: delete it, keep the class | `SeamstressPanel.test.tsx` |
| **The bar has no role, no value, no name, sets `inline-size`, and uses a DECLARED token** | `SeamstressPanel.test.tsx` |
| The named region and the **uncounted** list name; the item count equals the heading's `{{total}}` | `SeamstressPanel.test.tsx` |
| All four empty states, in order, with the owner/shift-manager split | `SeamstressPanel.test.tsx` |
| **A seamstress sees no write controls** — mutation: drop the role guard | `SeamstressPanel.test.tsx` + `AtelierSection.test.tsx` |
| An unmapped 400 renders the Hebrew default, never the English body | `SeamstressPanel.test.tsx` |
| **Both focus directions**, each asserting `document.activeElement` **IS** the node, **run first-in-worker five times** | `SeamstressPanel.test.tsx` |
| **The concrete tab order**, Enter-opens-writes-nothing, Esc-dismisses-without-writing | `SeamstressPanel.test.tsx` |
| The 44 px floor on `Button size="md"`; no `size="sm"` in the tree | `SeamstressPanel.test.tsx` |
| axe zero on the panel and both dialogs — **explicitly not sufficient** | `SeamstressPanel.test.tsx` |
| Every new key resolves in `he`, non-empty in `ar`; both aria names contain their labels; no «168»/«1440»; **`HE_F42` derived, not spread, and carrying `atelier.cue.assignedOverload`** | `i18n.test.ts` |

---

## What could go wrong in review

Every item here is a **recorded ruling**. A reviewer who raises one should find the reasoning rather than file a finding.

1. **"The bar divides by a 7-day number but the ruling says the whole backlog."** **§Conflicts 13.** `weekly_capacity_hours` is a **rate** and an unfiltered backlog is a **stock**; a 40 h/week seamstress with six weeks of forward work renders at 600 %, clamped, red, **on day one, on every row, in any boutique with a book** — and a bar that is red in the steady state is a bar nobody reads. The ruling's number ships unchanged as `assigned_minutes`, on the wire and in the same sentence. **The reversal is one line and is named.**
2. **"A finished gown still counts against her."** **§Conflicts 14**, and it is the largest product divergence in the feature. The brief says *"not yet `ready_at`"*; LOOP-STATE's ruling says *"not yet delivered"* and governs. Defensible — the work is physically in the workroom and still hers to redo if QC bounces — and the remedy already ships (advance to `delivered` at collection). **If the pilot reports it, it is a one-clause change.**
3. **"There is no capacity matrix and the epic names one."** **§Conflicts 1 / D8.** A matrix's second dimension is time, and time is the roster projection the same ruling **drops**. What ships is a list of the shape F41 already ships five of — which is also what discharges the e9 Risks' keyboard requirement **without a custom keyboard model**.
4. **"The load bar has no `role` — surely a meter is a progressbar."** **D9.** `role="progressbar"` announces a task's completion, not a level; its honest form needs an `aria-valuetext` byte-identical to the visible sentence, which puts one fact in the tree twice, and hiding the sentence to fix that is the WCAG 2.5.3 divergence failure. `role="meter"` is semantically right and **declined for AT support**, recorded as the role to revisit. **The row's text is the entire payload and the bar says so in markup.**
5. **"`bg-accent` would be the obvious fill."** It **does not exist** — `theme.css`'s `@theme` declares fourteen colours and no `accent`, `grep -rn bg-accent` returns zero hits, and Tailwind 4 emits no utility for an undeclared token. **The feature's headline widget would render colourless in its normal state.**
6. **"Three buttons in the capacity dialog's footer would be simpler."** **F-6.** `Modal.tsx:54` is `mt-6 flex justify-end gap-3`, hard-coded, **no wrap and no `className` seam**, and three buttons overflow 295 px at 375. Editing `packages/ui` from a call site is barred. The control moved into the body and now **clears the field**, which is also the better interaction.
7. **"`isolateLtr` exists — why not use it?"** **F-5.** It isolates by `indexOf` (verified `booking.tsx:76`), and `capacity.load` has **three** numeric interpolations: on «12.1 … מתוך 12», isolating `"12"` matches **inside "12.1"**. F41 bars a second helper. **No bidi helper anywhere; the name gets a bare `<bdi>` in its own element.**
8. **"The panel is bounded at `md:` only, but the columns are bounded at `md:` too — with a different value."** **C9.** 24 rem is a scale value where F41's `[32rem]` is arbitrary, and 3.5 rows of a 3–6 person roster is a bound that never engages, while a 60-card column's does. Bounding at 375 would reintroduce F41 §6's refused scroll-trap on the primary device.
9. **"`text-danger` is 6.78:1, not 6.18."** **C3 — refused, with the arithmetic.** 6.78 is `#A03232` on `--color-bg #FDFBF7`; the word renders inside a `Card`, i.e. on `--color-surface #F6F0E6`, where it is **6.18**. Only the *label* "on paper" was wrong.
10. **"`HE_F42` should just be `startsWith("atelier.")`."** **C4/D15.** That double-counts the union when spread and swallows F41's six shipped cue keys when narrowed to `atelier.cue.`. The block **derives from `HE_F41`, spreads nowhere, and names `atelier.cue.assignedOverload` by exact key** — the string that is the only thing a screen-reader user ever hears about an overload she just caused.
11. **"The capacity route should 404 on an unknown id."** **D6/D13.** `_require_seamstress` raises `AtelierValidationError` for missing **and** non-seamstress, and `by_id` already filters `tenant_id` and `deleted_at IS NULL` — so all four cases are one indistinguishable **400** by design, the same posture `_require_ticket` takes. Splitting them leaks whether a staffer exists, for no product gain, and forks a helper this feature otherwise reuses whole.
12. **"The write route should answer a `SeamstressRef` so the panel repaints fully."** **D6.** It has no aggregate and the only reachable load is `(0, 0)` — which would **collapse her bar and drop her «עומס יתר» word for five seconds** at the exact moment a manager is looking at it. The console patches four keys and the next tick supplies the load.
13. **"`StrictInt` is defensive typing."** **D5, and it is load-bearing.** `ForbidExtraModel` is `extra="forbid"` and **nothing else** (verified `app/schemas.py:13-18`), so plain `dict[str, int]` coerces `{"half_day": true}` → `1` **before any validator runs** — `validate_atelier_settings`' `isinstance(v, bool)` becomes unreachable code and a one-minute band ships as a 200, silently understating every load bar downstream.
14. **"Two managers can silently lose each other's settings."** **D5/Risk 4 — designed, and the recovery path is the audit trail.** A conflict dialog because a colleague opened the same form is the platform second-guessing a call that is hers. **This is why D12's full-value, no-`from` payload is load-bearing rather than incidental.** *If a pilot reports a reverted mapping, the remedy is a version field and a 409 — not a read on open (rejected finding #2).*
15. **"`MAX_WEEKLY_CAPACITY_HOURS` belongs in `atelier/validation.py`."** **Rejected finding #1.** `atelier/validation.py:13-20` pulls in `app.booking.validation` and `app.catalog.validation`; `stages.py` imports only `app.models` and is the module D5 already imports `MAX_BAND_MINUTES` from. One magnitude, one place, **and one import edge**.
16. **"The Hebrew should tell her the maximum is 168."** **D15, and F41 set the precedent by cutting `form.error.dueDateHorizon` at review** (`i18n.test.ts:705-719`). A Hebrew sentence quoting a server bound is a mirror exactly as much as a TypeScript constant is, with none of the protection — `test_frontend_constant_parity.py` scrapes only the two `validation.ts` files, so raising the CHECK would leave three sentences lying, silently and greenly.
17. **"axe passes, so the a11y work is done."** axe **cannot see a focus move that never happened** (five instances in this repo), cannot judge whether a `progressbar` role is semantically wrong, and has no target-size rule at the level this repo runs it. **The three assertions in Task 15 are the sole automated coverage of a legal requirement (IS 5568 / WCAG 2.0 AA).**
18. **"The focus fallback should carry F41's commit stamp."** **D14 — no, and copying it wholesale is the obvious wrong move.** F41's restore fires on **poll repaints**, which arrive with no user action and can outlive her own focus move; this one fires **only on a successful save, in the same turn, and only when focus is already nowhere.** There is no window for a stale intent, so a stamp would be machinery for a race this shape does not have.
19. **"The migration is numbered `0022` and LOOP-STATE said something else."** LOOP-STATE's MIGRATION CHAIN block records that the grid moved three times in one day. **The plan states a rule** — build at head+1, migration last, renumber at rebase, verify one head — and no number is authoritative except `alembic heads` at the moment of the rebase. **F37's in-flight `0021_sos_alerts.py` is already collided**, which is the live proof.

---

## Out of scope (unchanged from the spec, the decks and the scope fence)

The F40 roster projection, per-day and per-horizon bars, and the opening-hours-week fallback E9's degradation clause names — **F40 / §Conflicts 15** · split load and expedite — **later** · any block, refusal, 409, confirm-on-overload or auto-balancing suggestion — **#40** · a server-side overload flag or any advisory mutation field — **D11** · per-day/per-week buckets — **F40's shape** · load history, trend, throughput — **F44** · a re-value sweep after a band re-tune — **D4** · a `staff_capacity` table, an `effort_band` column, a stored `assigned_minutes` — **D1/D3/D4** · a re-validation sweep correcting `assigned_staff_user_id` on a role change — **F42 renders the anomalous bucket; the sweep stays unbought** · capacity for reception, sales assistants or the owner — **D6/Risk 6** · auditing `profile`/`toggles` — **a pre-existing gap** · a second poll loop, a capacity-only endpoint, a nav row, a `SectionKey` member — **F41 D12** · a `role="grid"` or a roving tabindex — **D8** · lifting `ConsoleShell`'s 720 px cap — **F44 (F-7 reassigned)** · any `packages/ui` edit — **barred; F-6 is the workaround** · mirroring any server bound on the client, in TS or in Hebrew — **D15** · any notification or SMS — **none** · a language switcher — **the 2026-07-31 languages ruling** · any E2E — **`vite preview` runs with no backend; F58 owns the harness**.
