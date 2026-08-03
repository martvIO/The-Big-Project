# Plan: Feature 33 — QR self-check-in + queue tickets + live position (Epic E6, floor-management program)

**Status**: Gate 2 self-approved 2026-08-03 under Interview Q1. **This file supersedes the plan that was here before** — that one was written against a superseded spec and against a tree in which F57 had not merged. The corrections **C1–C23** below are amended into the spec in Task 0; the spec text is the binding statement of each resolution, this file the reasoning.

**Spec**: `.planning/specs/qr-walkin-queue.md` (887 lines, D1–D15, four user rulings, three review rounds) · **Branch**: `feature/qr-walkin-queue` · **Worktree**: `.worktrees/qr-walkin-queue` · **Created**: 2026-08-03

TDD throughout. Every task states its **failing test first**, then the code that makes it pass, then the exact files, then how to verify, then the commit message.

**`db`-marked tests RUN LOCALLY on this feature, and that is what lets it ship green on its first CI run.** Postgres 16.14 is live via Homebrew (socket `/tmp`, superuser `mrwen`, no Docker). The runner is `scratchpad/run-db-tests.sh`: it recreates a clean `f33_test`, applies the local conftest escape hatch if it has been reverted, and runs `pytest -m db` with the S3 module ignored. **Baseline captured on this tree at 2026-08-03: `369 passed, 1277 deselected, 24.6s`** (378 db-marked tests collected; the 9 `test_media_upload_s3.py` cases need MinIO and are excluded — F33 touches no S3). Do **not** hardcode 369 into anything; re-read it at build time.

> ⚠ **THE conftest HARNESS PATCH IS LOCAL-ONLY AND MUST BE REVERTED BEFORE EVERY COMMIT.**
> Patch: `scratchpad/local-pg-harness.patch` (8 added lines in `backend/tests/conftest.py`). It is currently **applied** in the worktree. Every committing task below carries `git diff --stat` + an explicit `git checkout -- backend/tests/conftest.py` in its Done-when checklist. A commit carrying those 8 lines ships a `LOCAL_TEST_PG_URL` escape hatch into the test harness on main.

**Path hygiene.** The repo path contains a space and a `+`. **Quote every shell path.** And git tracks `backend/` / `frontend/` **lowercase** while the on-disk directories are `Backend/` / `Frontend/`: `git add Backend/…` silently skips modified tracked files. Lowercase every pathspec and verify every commit with `git show --stat`.

**`make lint` runs `frontend/scripts/qa-greps.sh`, which greps WHOLE FILES INCLUDING COMMENTS.** Verified at `qa-greps.sh:23` (bare `grep -rnE`) over `apps/storefront/src` (`:17`). English prose can fail the build with no code defect. Three live hazards for this feature's comment-heavy style: the literal `localStorage` (`:33`), the physical-direction pattern `[^a-zA-Z-](ml-|mr-|pl-|pr-|left-|right-|text-left|text-right|border-l-|border-r-)` (`:40`) which matches ordinary English like «left-hand», and a bare 6-digit hex (`:42`). **Every task that writes storefront source or comments repeats this warning in its checklist.**

---

## What moved since the spec was written — **F57 MERGED**, and it invalidates five spec facts

The spec was written on 2026-08-03 while F57 was mid-flight on an unmerged branch. **F57 merged the same day (PR #33, `2ac292a`).** The worktree's base already contains it. Verified against the tree at `fed93fe`:

| The spec says | Actually, now | Correction |
|---|---|---|
| Build the migration at `0015` / `down_revision "0014"`; renumber to `0016` at rebase (D15, Risk 9) | `alembic heads` → **`0015 (head)`**. `0015_floor_roles.py` is F57's, on main. Building at `0015` is now a **duplicate revision id**. Probed: a stub `0016` / `down_revision "0015"` resolves — `alembic heads` prints `0016 (head)` | **C1** |
| F33's manage router is "**the EIGHTH** `/manage` router"; seven already mount it (D14) | F57 added `floor_router` at `main.py:1051`, whose own comment numbers it "**the SEVENTH** router carrying `prefix="/manage"` exactly"; `gateway_router` (`:1056`) is the eighth. Plus `auth_router` at `/manage/auth`. F33's is the **NINTH** | **C2** |
| `MANAGE_API` holds "**eleven** names"; F33 makes twelve (Frontend changes, D14) | It holds **twelve** — F57 added `floor` and did **not** update the comment, which still says eleven. F33 makes **thirteen** | **C3** |
| `SectionKey` is ten members; insert the QR row "after `board` and before `staff`"; the shift-manager slice `.slice(0, 8)` becomes `.slice(0, 9)` (D14) | `SectionKey` is **eleven** (`App.tsx:19-31`, F57's `floor` is "the ELEVENTH member"). `NAV` has **eleven** rows; F57's `floor` sits **between `board` and `staff`** with `roles: FLOOR_ONLY` and a comment saying "Immediately after the board". `NAV_LABELS` excludes `floor` and is asserted `toHaveLength(10)` at `Nav.test.tsx:136` | **C4** |
| D9/D11/D12 cite `BoardSection.tsx:11-27, 78-80, 104-124, 244-261, 248-261, 306-319, 321-333, 451-456, 556` | **All stale.** F57 extracted the loop into `frontend/apps/manage/src/lib/usePoll.ts` (324 lines) and rewrote `BoardSection.tsx` (608 lines). Every mechanism D9 tells F33 to copy now lives in `usePoll.ts` | **C5** |

**Two consequences that are good news:**

- **The rebase-conflict warning in D15 and in the pg-findings blast-radius note is DISCHARGED.** F33 branches from a base that already contains F57's `App.tsx`, `i18n/{he,ar}.ts` and `usePoll.ts`. There is no concurrent rewrite of those files to conflict with. The diff should still be **append-shaped** for the ordinary reason (two other sessions are live in this repo), but the specific F57 collision is gone.
- **The `usePoll` extraction already happened and F33 still must not import it.** D9's ruling is unchanged and its reasoning is now *stronger*, not weaker: `apps/manage/src/lib/usePoll.ts` is inside `apps/manage` and is unreachable from `apps/storefront` under pnpm's isolated `node_modules`. F33 **copies the mechanisms** and reads them off `usePoll.ts` rather than off `BoardSection.tsx`.

**Two other sessions are live in this repo right now** (`LOOP-STATE.md`'s `current:` block, verified 2026-08-03): **F19** in `.worktrees/deposit-booking-flow` and **F53** in `.worktrees/customers-crm`. Neither is this session's to touch. Both will land migrations. That is what C1's rule exists for.

### Citations re-captured — ✅ verified on this tree, do not re-check

- ✅ `Backend/app/main.py:1022-1070` — the whole `include_router` block, its per-router numbered shadowing comments, `_register_spas(app)` last (`:1070`). `_RESERVED_SEGMENTS = frozenset({"manage", "storefront"})` at `:323`, consulted at `:359`.
- ✅ `Backend/app/auth/rate_limit.py` — `_current_count` `:47-52` (a **read**: `self._buckets.get(key, (now, 0))` inserts nothing, so `is_blocked` creates no bucket), `is_blocked` `:54-56`, `record_failure` `:58-62` (**this is the only insert**), `_sweep` `:64-69` (drops only **expired** buckets; `_sweep_at` floats to `2×` survivors). The class docstring's bounded-key-space rule is `:14-16`; its "bounds memory for any future caller" claim is `:29-33`.
- ✅ `Backend/app/dashboard/router.py` — the whole file is the minimal `/manage` router shape D14 copies: module docstring, local three-line `_no_store`, one `get_*_service(request)` off `request.app.state`, `APIRouter(prefix="/manage", dependencies=[Depends(_no_store), Depends(require_role(...))])`, one `Annotated` alias, one handler taking `request` and calling `get_current_tenant(request)`. Its docstring already states the `OWNER_ONLY` trap verbatim.
- ✅ `Backend/app/booking/comms_templates.py:74-81` — `def manage_link(*, slug: str, base_domain: str, token: str) -> str:` at `:74`, `return f"https://{slug}.{base_domain}/b/{token}"` at `:81`. The spec's re-capture is correct.
- ✅ `Backend/app/booking/validation.py:40` — `MAX_CUSTOMER_NAME_LENGTH = 80`. **The spec says `:39`; it is `:40`.**
- ✅ `Backend/app/notifications/validation.py:31` — `def normalize_israeli_mobile(raw: str) -> str:`.
- ✅ `Backend/app/storefront/validation.py:40` `BOUTIQUE_TIMEZONE`, `:42` `Clock`, `:86-94` `today_jerusalem(clock)` and its injectable-clock docstring.
- ✅ `Backend/app/core/config.py:20` `base_domain: str = "localtest.me"`; `:152-164` the storefront read budget and its written-out arithmetic — the shape F33's six new fields copy. `main.py:547` and `:657` are the two shipped `base_domain=settings.base_domain` injection sites.
- ✅ `Backend/app/security_headers.py:32-37` — `"Referrer-Policy": "strict-origin-when-cross-origin"`. **This confirms C7.**
- ✅ `Backend/migrations/versions/0008_bookings.py` — `_STANDARD` `:16-23`, `_updated_at_trigger` `:25-30`, the `customers` partial unique index and its comment `:40-49`, the inline CHECKs in `CREATE TABLE bookings` `:60-70`, the trailing `GRANT` + `enable_tenant_rls` loop `:107-110`, `downgrade` `:113-115`. **`:88-92` is ONE unique index** (`idx_bookings_slot_seat_unique`); `idx_bookings_tenant_starts` at `:95-98` is **non-unique** — the spec's "two partial unique indexes" at D2/`:175` is wrong.
- ✅ `Backend/tests/test_storefront_api.py:237` `SPEC_ERROR_CODES`; `:565-599` the cross-router shadowing guard, whose explicit `/storefront` path-literal set is the one test F33 is meant to break, with `:569-571` stating why the literal stays a literal.
- ✅ `Backend/tests/test_spa_serving.py:67-80` `SHELL_PATHS` and its "every path a bride can be sent directly" comment; `:389` the `monkeypatch.setattr("app.main.get_settings", _settings)` shape; `:398` `assert match is not None`; **`:400`** the order-insensitive `set(match.group(1).split("|")) == expected` — **the spec says `:399`; it is `:400`**.
- ✅ `Backend/tests/test_staff_role_gating.py:70` `OWNER_ONLY`, `:85-102` `FLOOR_ROLES` / `FLOOR_OPEN`, `:209` `test_route_table_matches_the_permission_matrix`, `:240` `test_the_floor_roles_reach_exactly_the_floor_routes` (**exact set equality** — a `require_role(*StaffRole)` on F33's route would redden it).
- ✅ `Backend/tests/test_migrations.py:502-507` and `:621-626` — the two captured-definition blocks and their "pg_get_constraintdef normalises `IN (...)` into `= ANY (ARRAY[...])`" comments; `:588` and `:692` the two most recent round-trip tests, both **last in the file** with `try/finally: command.upgrade(cfg, "head")`.
- ✅ `Backend/tests/conftest.py:83` `postgres_url`, `:106` `migrated_db`, `:137` `app_role_url`.
- ✅ `frontend/apps/storefront/src/router.tsx:23` `RouteName` (six members), `:31-39` `RouteMatch` with the token-is-opaque comment, `:74-82` `decodeId`, `:84-113` `matchRoute` with the `/b/{token}`-before-catalog comment at `:92-96`, `:144-151` `navigate(to, { replace })` and its **"`replace` is for GUARD redirects only"** docstring at `:134-143`, `:258-273` the one effect that writes `document.title` (`:259`, unconditional) then **early-returns on first paint** (`:262-266`) before `scrollTo` + `focus()` (`:271-272`).
- ✅ `frontend/apps/storefront/src/api.ts:48-77` `errorMessageKey` and its real-Hebrew `default`; `:114-128` `apiFetch<T>(path, init: { method?, body? })` — **no `referrerPolicy`, no case conversion**; `:225-227` `BoutiqueResponse.name` "the display name, not the slug".
- ✅ `frontend/apps/storefront/src/components/StorefrontLayout.tsx:40-45` the `{ boutique: null, loading: true, error: null, retry }` context default, `:55` `useBoutique()`, `:128-130` `<main id={MAIN_ID} tabIndex={-1}>{children}</main>` **with no gate on `loading` or `error`**.
- ✅ `frontend/apps/storefront/src/routes/BookPage.tsx:1088` `autoComplete="name"`, `:1250` `autoComplete="tel"`.
- ✅ `frontend/apps/storefront/package.json` — **no `axe-core`**. `apps/manage/package.json` carries `axe-core ^4.12.1`.
- ✅ `frontend/apps/manage/src/lib/usePoll.ts` — `POLL_INTERVAL_MS` `:15`, `MAX_BACKOFF_MS` `:19`, `IDLE_STOP_MS` `:23`, `IDLE_STOP_MINUTES` `:24`; `tickRef` `:116`, `backoffRef` `:119`, `generationRef` `:123`, `runningRef` `:124`, `clearTick` `:133`, `schedule` `:151-161` (clears, then refuses on `!runningRef.current || document.hidden`), `tick` `:187-193`, the mount effect `:201-219`, **the unmount guard `:224-234` (`runningRef.current = false` at `:233` BEFORE `clearTick()` at `:234`)** with its "clearTick() alone cancels only the timer armed RIGHT NOW" comment at `:224`, `visibilitychange` `:240-257` (bumps the generation and fetches immediately at `:252-254`).
- ✅ `frontend/apps/manage/src/components/BoardSection.tsx` — `PAGE_LIMIT` `:22`, `usePoll(...)` `:66`, `freshKey` derivation **`:320`**, the pause `<Button … size="md">` **`:389`**, the `role="status"` region and its "update every five seconds passes every automated check" comment **`:416-420`**.
- ✅ `frontend/apps/manage/src/__tests__/BoardSection.test.tsx:510-512` — the `size="md" -> min-h-11 = 44px` comment and the two class assertions; `:593` the `MutationObserver`; **`:651-653`** the three separate `closest()` calls.
- ✅ `frontend/scripts/qa-greps.sh:17` `SRC`, `:23` the bare `grep -rnE`, `:33` the `localStorage` ban, `:40` physical directions, `:42` raw hex.
- ✅ `Makefile` — `lint`, `test`, `test-db`, `fe-test`, `fe-build`, `e2e`, `qa-greps`.

---

## Twenty-three corrections — recorded, resolved, amended into the spec in Task 0

The spec is binding and D1–D15 are **not** re-litigated. These are the places where the document disagrees with the tree, or where a verified finding survived the last review round. **Every resolution is the smaller edit.**

### C1 — the migration number: **build at `0016` / `down_revision "0015"`**, not 0015/0014

D15 and Risk 9 tell the builder to build at `0015` because "`0015` lives only on F57's unmerged branch". **F57 merged.** `alembic heads` on this worktree is `0015`. Building at `0015` is a duplicate revision id — the exact multiple-heads mystery D15 exists to prevent, in the other direction.

**Resolution — the rule from `LOOP-STATE.md`'s MIGRATION CHAIN block, which replaced the fixed grid on F57's merge:**

1. **BUILD at head + 1.** Today that is **`0016_queue_tickets.py`, `revision = "0016"`, `down_revision = "0015"`.** Verified by probe: a stub of that shape makes `alembic heads` print `0016 (head)`. **Do not read that number off this document either** — run `cd "…/Backend" && uv run python -m alembic heads` in Task 1 and take the next integer.
2. **Make the migration the LAST commit on the branch** (Task 1 is early, so the commit is *reordered* onto the tip at rebase — or simply amended in place, since nothing else references the revision literal). This is the one instruction that makes step 3 cost one amend.
3. **RE-RESOLVE from `alembic heads` on `main` immediately before the rebase that precedes push.** F19 is "nearly done" and is expected to land first, which would make main's head `0016` and F33's number `0017`. Three edits: the filename, the `revision` literal, the `down_revision` literal.
4. **Do not OPEN the PR while a lower-numbered migration is still unmerged.** The spec's precondition "the PR does not open until F57 has merged" is **already discharged**. The live precondition is now **F19's PR merging first**. Expected landing order, not a reservation: F19 → F33 → F53.

Declined: coordinating with the other two sessions. Three things make this safe without it, and `LOOP-STATE.md` names them: a wrong `down_revision` points at a revision that does not exist so alembic errors outright rather than drifting; F19 carries a fast no-DB **single-head guard** that fails in `make test`; and each branch builds against head+1 so it is self-coherent and its db tests run.

### C2 — F33's manage router is the **NINTH** `/manage` router

`main.py:1051`'s comment numbers `floor_router` "the SEVENTH router carrying `prefix="/manage"` exactly"; `gateway_router` at `:1056` is next. With `auth_router` at `prefix="/manage/auth"`, **eight already mount `/manage`**. D14's "the EIGHTH" was correct before F57 merged and is now off by one.

**Resolution:** the shadowing comment above `app.include_router(queue_manage_router)` says **"The NINTH"**, and names `tests/test_checkin_qr_api.py`'s `ROUTES` table as what keeps the nine-way prefix honest. The *public* sibling count is unaffected: F33's storefront router is still the **fourth** `/storefront` sibling (`main.py:1059`, `:1063`, `:1067`).

### C3 — `MANAGE_API` already holds twelve names and its comment already says eleven

`vite.config.ts:19` is `appointment-types|auth|availability|bookings|dashboard|dresses|floor|gateway|settings|slots|staff|terms` — **twelve**. The comment at `:13-17` says "The **eleven** names" and "a **twelfth** router added without touching this file fails there". F57 added `floor` and left the prose behind.

**Resolution:** F33 inserts `checkin-qr` **between `bookings` and `dashboard`** (alphabetical, for the reader — `test_spa_serving.py:400` compares sets) and fixes the counts in the same edit: «eleven» → **«thirteen»**, «a twelfth» → **«a fourteenth»**. Fixing F57's drift is one word and the alternative is leaving a comment that is wrong by two.

### C4 — the nav row goes **after `floor`, before `staff`**, and four assertions move

F57 inserted `{ key: "floor", labelKey: "nav.floor", roles: FLOOR_ONLY }` between `board` and `staff`, with a comment stating it sits "Immediately after the board". D14's "after `board` and before `staff`" now has two readings.

**Resolution:** insert `{ key: "checkinQr", labelKey: "nav.checkinQr", roles: ALL }` **after the `floor` row and before `staff`**. This keeps F57's adjacency comment true, keeps the two owner-only rows structurally last, and — because `NAV_LABELS` in `Nav.test.tsx` lists only the **owner-visible** rows and `floor` is `FLOOR_ONLY` — puts «קוד סריקה» at `NAV_LABELS` index **8**, exactly where D14 wanted it. Consequences, all in `Nav.test.tsx`:

- `NAV_LABELS` (`:57-75`) gains «קוד סריקה» after «לוח היום» and before «צוות».
- **`.slice(0, 8)` → `.slice(0, 9)` at BOTH sites: `:100` and `:184`.** The finding that raised this named `:95` and `:148`; F57 shifted them. Verified by grep: exactly two call sites.
- `expect(NAV_LABELS).toHaveLength(10)` at **`:136`** → `toHaveLength(11)`.
- The stale prose: the test name at `:96` ("shows a shift manager **eight** sections") → nine; the test name at `:131` ("the owner's **ten** and the shift manager's **eight**") → eleven and nine; the comment at `:71` ("below a `.slice(0, 8)`") → 9.
- `SectionKey` (`App.tsx:19-31`) gains `| "checkinQr"` as the **twelfth** member.

`useState<SectionKey>("dashboard")` (`App.tsx:103`) is **not touched** — `dashboard` is NAV row 0 and nothing inserted below it can displace the landing or the `reachable[0]?.key` fallback.

### C5 — D9's mechanisms live in `lib/usePoll.ts` now; every `BoardSection.tsx` line number in D9/D11/D12 is stale

**Resolution:** re-point, do not re-decide. D9's ruling (copy, do not import) is unchanged. The builder reads the six mechanisms off **`frontend/apps/manage/src/lib/usePoll.ts`** at the line numbers in the ✅ table above, and the wiring (`freshKey` derivation `:320`, the `size="md"` pause `:389`, the `role="status"` region `:416-420`) off the rewritten `BoardSection.tsx`. **The copied comments come with them** — Risk 5's mitigation is that the copies are greppable by their own prose, which only works if the prose is copied.

### C6 — **the per-ticket read limiter's key space is unbounded, and the fix is to charge on HITS ONLY** (finding: MAJOR)

D6's metering order (`spec:300`) is "check and record `position_ticket_limiter` → look the ticket up → on a miss only, check and record `position_miss_limiter`". The key `checkin:position:{tenant_id}:{ticket_id}` comes from the request **body**, and `record_failure` (`rate_limit.py:58-62`) inserts one dict entry per key while `_sweep` (`:64-69`) drops only **expired** buckets. So a fresh UUID per request is a fresh live-for-a-window bucket: 200 000 requests inside one 60s window leave 200 000 live buckets and ~34 MB of key strings, in the single uvicorn process that serves every tenant (`docs/infra-runbook.md:151`). The class docstring states the rule being broken at `:14-16` ("keys per TENANT … so that space is bounded by the tenant count, not by visitor count") and its claim at `:29-33` that the sweep bounds an unbounded caller is true only *across* windows. **F33 is the first caller to make that claim load-bearing, and it fails.**

**Resolution — one statement moves. The read's order becomes:**

1. validate the body (pydantic UUID)
2. `if ticket_limiter.is_blocked(ticket_key): raise CheckinThrottledError` — **consult only.** `is_blocked` goes through `_current_count`, which is a `.get(key, default)` and **inserts nothing**; consulting an unknown key is free and leaves no bucket.
3. look the ticket up
4. **miss** → `miss_limiter.record_failure(miss_key)`; then raise `CheckinThrottledError` if that budget is now spent, else `QueueTicketNotFoundError`
5. **hit** → `ticket_limiter.record_failure(ticket_key)`; return the `TicketView`

The per-ticket key space collapses to ids that resolved to a **live row**, which the create ceiling already bounds — `rate_limit.py:14-16`'s property restored. This **deletes** a line rather than adding one.

**Where this diverges from the finding's literal fix, and why.** The finding also proposed consulting the miss brake *before* the lookup, "so a spent brake 429s without a DB round-trip". Declined: a tenant-keyed brake consulted before the lookup 429s **hits** during a miss-flood, which is precisely the one-client-429s-everyone defect D6 built the miss brake to fix. The saving is one index lookup on a request that was going to 404; the cost is the whole property. Hits stay unaffected by a miss-flood.

**What this costs, stated:** D6 argued the per-ticket charge-on-miss "bounds a walk that hammers one guessed id". After the fix that walk is bounded by the tenant miss brake (120/60s) instead of by 30/60s. Both walk shapes still terminate, which is what the miss brake is for; the finding's argument on this point is accepted.

**The assertion that proves it** (Task 3, and it can fail): inject spy limiters into `QueueService` and assert that after N reads whose ids all miss, the per-ticket spy recorded **zero** keys. Mutation-check by restoring the record-before-lookup line — the count becomes N.

### C7 — **the ticket id rides `Referer` on every poll; D7's "1 log line instead of 360" is false on this deployment** (finding: MAJOR)

D7 claims the POST "keeps the id out of the `Referer` header on every subsequent request the page makes". Three verified facts kill it: `security_headers.py:36` sets `Referrer-Policy: strict-origin-when-cross-origin`, which strips the path only **cross-origin**; the SPA is served **same-origin** by user ruling; and `api.ts:114-128` passes no `referrerPolicy`, so the document policy governs and the document is `/q/{ticket_id}`. Result: `Referer: https://{slug}.…/q/{ticket_id}` on all 360 polls.

**Resolution:** one optional field on `apiFetch`'s `init`, `"no-referrer"` at the two queue call sites.

```ts
export async function apiFetch<T>(
  path: string,
  init: { method?: string; body?: unknown; referrerPolicy?: ReferrerPolicy } = {},
): Promise<T> {
  const { method = "GET", body, referrerPolicy } = init;
  const response = await fetch(path, { method, credentials: "omit", referrerPolicy, … });
```

`referrerPolicy: undefined` on every existing call site is exactly today's behaviour, so this is behaviour-neutral for F9/F13/F16. Asserted the way `BookPage.test.tsx` pins `autoComplete` — a **fetch-mock argument check**, not a browser test. F16's `/b/{token}` has the same pre-existing defect; F33 does not fix it, it just makes the option exist. D7's Referer sentence and its 1-vs-360 arithmetic are rewritten: the POST keeps the id out of the request **line**; `referrerPolicy` is what keeps it out of the header.

### C8 — **the shared-device analysis defends the weakest channel**: autofill and the back stack (finding: MAJOR)

D8 names the door tablet ("the mother checking in her daughter, then the next arrival") and then reasons only about the `sessionStorage` pointer. Two channels it does not reach: the house pattern for a name+phone form is `autoComplete="name"` / `autoComplete="tel"` (`BookPage.tsx:1088`, `:1250`, pinned as a requirement by `BookPage.test.tsx`), so a builder copying the sibling surface offers «נועה» and `0501234567` to the stranger behind her; and `navigate()` is `pushState` unless `replace` is passed (`router.tsx:144-151`), so every live ticket URL stays in the tab's back stack.

**Resolution — two attributes and one option:**

- `autoComplete="off"` on **both** the name and phone `Input`s, asserted the way `BookPage` asserts the opposite. The legal bar here is WCAG **2.0** AA (pre-decided #38), which has no SC 1.3.5 Identify Input Purpose, so this costs nothing conformance-wise. This **deliberately contradicts the sibling surface**, which is why it is a plan decision with a source comment rather than a silent omission.
- `navigate("/q/" + id, { replace: true })` on create success. `router.tsx:134-143` reserves `replace` for guard redirects, so this is a deliberate second use and the comment must say so: a submitted form must not be the Back target, and on a shared tablet the ticket URL must not be one press away.
- **State the residual honestly.** `replaceState` removes `/checkin` from the back stack; it does **not** remove `/q/{id}` from the browser's global history or the address bar. D8's reach table gains one row: **browser history and autofill are NOT defended; a kiosk deployment needs kiosk mode or a per-arrival tab reset.**

### C9 — **the create's tenant ceiling is also a boutique-wide kill switch** (finding: MAJOR)

With the per-phone budget deleted (D6) the create's only bound is `checkin:{tenant_id}` at 200/3600s, metered on the **attempt** (`spec:298`). `booking/service.py:190-191` states the consequence of exactly that ordering in writing — metering before the proof lets a caller "exhaust a boutique's hourly budget with garbage tokens and lock every real bride out — a denial of service costing the attacker nothing" — and `config.py:98-103` records that it already bit once, fixed by raising the ceiling **and** by the fact that each unit costs a real SIM. F33's unit costs one HTTP request. 200 requests close the boutique's self-service check-in for the hour.

**Resolution — do not chase it with a number.** Every tenant-keyed budget on an unauthenticated write is exhaustible; per-IP and distributed limiting are F21's, which D6 already says. Three edits, none of them mechanism:

- **The create's 429 Hebrew string sends her to the counter, not into a retry.** "Out of scope" already leans on that fallback ("The counter is three metres away"). One string, and it is the difference between a dead end and a working boutique.
- **Risk 1 gains the availability half** with **F21** as owner. Today it enumerates only junk tickets and in-process limiter weakness.
- **The «Deployment ordering» table gains a row** stating plainly that **F58 does not discharge this** — F58 ships a panel and remedies for junk *rows*, not a second way to join the queue.

Declined: a per-IP key (F21), and raising the ceiling (it moves the number, not the property).

### C10 — **the F58/F20 deployment gate has no mechanism; give it three lines** (finding: BLOCKER)

«Deployment ordering» says the gate is "the printed sign is not produced … and no pilot tenant is told the URL. There is no feature flag and F33 does not build one" (`spec:810`). That is obscurity of a guessable path on a public subdomain, and nothing in the build honours it: D1 registers the sibling router unconditionally, `/checkin` is not in `_RESERVED_SEGMENTS` (`main.py:323`) so the SPA catch-all serves the shell, and the spec itself adds `/checkin` to `SHELL_PATHS`. The exposure is imminent rather than theoretical — the domain is bought, the Railway wildcard is created, and the SPAs are same-origin. At merge, `/checkin` is a live unauthenticated PII-and-consent collector on every tenant subdomain, behind counsel-gated interim wording, into a table with no retention job, no staff surface and no remedy. That is the state Ruling 4 exists to prevent.

**Resolution — one `Settings` boolean, defaulting `False`:**

```python
# Ruling 4's gate, made checkable. F33's public check-in surface stays OFF until
# BOTH deployment preconditions clear: F58's waitlist panel (a staff surface, a
# remedy and a reachable terminal) and F20's retention sweep (the notice promises
# a retention window nothing enforces). Flipping this is one env var, no deploy.
checkin_enabled: bool = False
```

```python
    # Ruling 4. The manage QR route is NOT gated — it renders a public URL and a
    # picture of it, and reaching it is how an operator checks the sign before
    # the gate clears. The two anonymous routes are.
    if settings.checkin_enabled:
        app.include_router(queue_router)
```

The spec declined the wrong alternative: «Declined: a `queue_enabled` tenant setting» rightly refuses a migration plus a manage form, but an env flag is **neither**, and it is the same `Settings`-tunable-without-a-deploy discipline D6 already applies to six rate-limit numbers. «What "not enabled" means mechanically» is restated in terms of the flag, so the gate is checkable by grep instead of by trust.

**Test consequences, all in F33's own modules:**

- **One new fast test:** with the flag at its default, `POST /storefront/checkin` and `POST /storefront/checkin/position` answer **404** and neither path appears in the route table. Mutation-check: drop the `if` and it goes red.
- `test_checkin_api.py`'s `_client()` builds the app with the flag **on**, via `monkeypatch.setattr("app.main.get_settings", …)` — the shape `test_spa_serving.py:389` already ships.
- `test_storefront_api.py::test_no_route_is_registered_twice_across_routers` builds the app with the flag **on** before extending its explicit `/storefront` literal. That is the one existing test whose call site changes.
- `test_spa_serving.py` is unaffected — the SPA catch-all does not consult the flag, and that is correct: with the flag off, `/checkin` renders the form and its submit answers 404, which the page's error arm already covers. A second, frontend flag would be a second surface for no gain.
- `test_staff_role_gating.py` is unaffected — the manage router is unconditional.

### C11 — **the consent hedge needs a carrier in the schema** (finding: MAJOR)

D5 rules the tick "a submission record, not a consent record" that "must not become a marketing permission without possession proof at F20's send time". The only mechanical guard behind that is `test_migrations.py` asserting `customers` has no `marketing_opt_in_at` — **the exact assertion F20 deletes the day it adds the column**, which is what F33 tells it to do. And the column name is byte-identical to F20's, so the hand-off reads as a rename-free copy.

**Resolution — one migration statement, no new column, no rename:**

```sql
COMMENT ON COLUMN queue_tickets.marketing_opt_in_at IS
  'UNVERIFIED submission record, not a consent record: the check-in form takes no possession proof, so this evidences that someone typed a number, not that its owner agreed. Not promotable to a marketing permission without possession proof at send time (F33 D5). Consents stamped before counsel replaces checkin.notice/checkin.optIn are not promotable at all.';
```

The repo already puts load-bearing reasoning in migration comments (0014's absent-list). This one belongs in the **schema** because the reader is a different feature, and a `COMMENT ON COLUMN` survives every future `test_migrations.py` edit. **Asserted** by one line reading `col_description` back — non-vacuous, since deleting the statement reddens it. Plus one sentence in D5: consents collected before counsel's swap are not promotable, and F20 must key promotion on tickets created after the swap date. **That set is empty by construction under C10** — the flag is off until counsel clears.

Declined: renaming to `marketing_opt_in_claimed_at` (it lengthens F20's diff to shorten a sentence).

### C12 — **the `:day`-binding test is seeded so it CANNOT FAIL** (finding: MAJOR)

`spec:757` says: seed "a ticket left `waiting` on an earlier day plus three of today's, and assert it reports its own day's position rather than `1`". With exactly one earlier-day ticket, **its own-day position IS 1**, so both the correct binding (`:day` = the ticket's `queue_day`) and the buggy one (`:day` = `today_jerusalem(clock)`) return the same value. **Proven on the live 16.14 server**, seeded exactly as the spec specifies:

| ticket | `pos` with `:day = q.queue_day` | `pos` with `:day = today` |
|---|---|---|
| stale A (2026-08-02 09:00Z) | 1 | 1 |
| **stale B (2026-08-02 09:30Z)** | **2** | **1** |
| today 1 / 2 / 3 | 1 / 2 / 3 | 1 / 2 / 3 |

**Resolution:** seed **TWO** tickets left `waiting` on the earlier day plus three of today's, and assert the **LATER** stale ticket reports position **2** — its true place in the queue it joined — while a today-bound read would report 1. **State the negative control in the same test docstring**: with a single earlier-day ticket the two bindings agree and the test proves nothing. This is the only automated guard on the binding; D3 and its Decisions Log entry state the rule in prose only.

### C13 — the `SELECT`-free row's cross-reference is false (finding: MINOR ×2)

`spec:746` asserts "no request path in F33 consults the phone at all, which the source guard above already pins". The guard at `:743` reads only `Backend/app/queue/*.py` and only for `CustomersRepository` / `app.db.repositories.customers`. A phone lookup on `app/db/repositories/queue_tickets.py` — a different directory — passes it untouched.

**Resolution:** extend the guard rather than delete the sentence, because the extension can fail. Two clauses:

- the text guard reads `Backend/app/queue/*.py` **and `Backend/app/db/repositories/queue_tickets.py`**, asserting no occurrence of `CustomersRepository` or `app.db.repositories.customers`;
- `inspect.signature` over every public method of `QueueTicketsRepository` names **no `phone` parameter**, and `QueueService.__init__` names no customers repository.

Adding a `by_phone(...)` or a `phone=` kwarg reddens it. That is the failable form the false cross-reference was standing in for.

### C14 — the identical-phone isolation assertion is vacuous as written (finding: MINOR)

`spec:756`: "tenant B can write a ticket with the IDENTICAL phone and the identical `queue_day` as A's row, and both rows survive". Ruling 3 removed every unique constraint — confirmed on the live table, `count(*) FROM pg_index WHERE indisunique AND NOT indisprimary` is **0** — so nothing could ever refuse that write, with RLS on or off.

**Resolution:** fold the survival claim into the **visibility** half, which can fail: tenant B writes the identical phone on the identical day, **and A's reader still returns exactly one row (hers), and B's returns exactly one row (his), and neither id is visible to the other**. The phone stays deliberately identical — the point is that a phone is not a cross-tenant identity — but the failing half is RLS, not an index.

### C15 — **every `LOOP-STATE.md:NNN` citation in the spec is stale**, and one of them is load-bearing (finding: MAJOR)

Twelve of fourteen point at unrelated text and two point past end-of-file. The worst is `:241-243`, cited three times as the promise that "F58 needs no migration of its own" — the sole justification for shipping `skip_count`, a column with **neither reader nor writer in F33**. `grep -ni "needs no migration"` returns nothing in either copy of the file.

**Resolution:** this plan cites `LOOP-STATE.md` by **section and quote**, never by line, because that file is rewritten every loop iteration. And `skip_count`'s justification is restated honestly in the migration comment: F58's queue note describes it acting on `queue_tickets` (take-next, push-assign, finish, **skip**) and does not say it ships no migration; the column ships because **one `INTEGER NOT NULL DEFAULT 0` in the migration that creates the table is cheaper than a migration in the feature that was scoped not to have one**, and because D2 already closed the decision. The column stays; the false citation goes.

### C16 — `checkin_link()` has no specified home; it goes in `app/queue/service.py` (finding: MAJOR)

D14 says the function is `manage_link()`'s "exact sibling **beside it**", which reads as `app/booking/comms_templates.py` — a file no change list mentions, and one that would make `app/queue` import from `app.booking`. But D1's package tree names no module for it either. Both readings compile; they are different architectures.

**Resolution:** **module-level in `app/queue/service.py`, above the class, keyword-only**, with a comment naming `booking/comms_templates.py:74-81` as the sibling and stating why it does not live there: F33 sends nothing, so there is no comms-template module to put it in, and a new `app.queue → app.booking` package edge for a two-line f-string is the wrong trade. It stays pure, module-level and unit-testable with no app, which is every property D14 asked for. `tests/test_checkin_qr_link.py` imports `from app.queue.service import checkin_link`. Zero new files, zero new import edges.

### C17 — a sustained miss-flood defers the 404 terminal **indefinitely**, not "up to a window" (finding: MINOR)

D6 and the error table both say a client "backs off … until the minute-long window clears and the 404 arrives". `position_miss_limiter` is tenant-keyed at 120/60s, which one host holds spent indefinitely at trivial cost.

**Resolution:** wording only, no mechanism change. «for as long as the flood lasts», not «until the 60s window clears», in D6 and in the error table, plus one clause noting that an attacker-held terminal-deferral is a residual **F21** owns with the rest of the in-process limiter story. **Declined: a max poll lifetime** — D10's refusal is right for the reason it gives.

### C18 — five drifted code citations, re-captured

(a) `MAX_CUSTOMER_NAME_LENGTH` is `booking/validation.py:40`, not `:39`. (b) The order-insensitive set comparison is `test_spa_serving.py:400`, not `:399` (`:398` is `assert match is not None`). (c) **`BoardSection.tsx:513-519` is not the pause control** — post-F57 the `<Button … size="md">` is at `:389`, and the whole citation class is superseded by C5. (d) `0008_bookings.py:88-92` is **ONE** unique index; `idx_bookings_tenant_starts` at `:95-98` is non-unique — D2's and its log entry's "two partial unique indexes" is wrong. (e) The poll constants are five, not four, and they now live in `usePoll.ts:15,19,23,24` plus `BoardSection.tsx:22`.

### C19 — "all 353 db-marked tests" is wrong by twenty-five

`pytest --collect-only -q -m db` in this worktree returns **378 collected / 1277 deselected**. The local runner (which ignores the 9 MinIO-dependent S3 cases) reports **369 passed**. **Resolution:** the spec's two occurrences say "every db-marked test" with no number; the plan states the baseline as captured-today and tells the builder to re-read it.

### C20 — `test_checkin_api.py`'s stub is jointly over-constrained and the requirement is never stated

`spec:746` wants two creates on one client to return **different** ids; `spec:740` wants cookie-blindness by full `.json()` equality across two clients. Both hold only because `_client()` builds a fresh app and a fresh stub per call. **Resolution:** one sentence in the Testing section — *the fake mints a fresh id per call and is constructed per `_client()`, so cookie-blindness compares two first-calls and the duplicate test compares two calls on one client.*

### C21 — D8's focus justification over-reaches

`spec:419` says anything a page focuses on mount "is silently overwritten one tick later". Verified: `router.tsx:259` writes the title unconditionally (that half holds), but `:262-266` **early-returns when `previous === null`** — i.e. on a **first paint**, which is this feature's normal entry (a bride opening `/q/{id}` straight from a URL). A page-level focus-on-mount would survive there.

**Resolution:** keep the rule and keep the test — both are correct and non-vacuous when the page is rendered directly. Reword the justification: the router's override only masks the defect on **client navigations**, which is precisely why the **direct-load** case must be the one tested.

### C22 — storefront `ar.ts` is a deliberately partial bundle

`apps/storefront/src/i18n/ar.ts` is 2 608 bytes against `he.ts`'s 25 508; its `document:` block (`:25`) carries `manageTitle` and not `catalog`/`dress`/`about`/`accessibility`/`book`. It mirrors the F16 manage-booking surface and nothing else, and there is no storefront parity guard.

**Resolution:** one clause in the `ar.ts` row — adding F33's keys **extends a deliberately partial bundle**, and the builder is not being asked to backfill the rest of it. Never `""` (i18next's `returnEmptyString` default renders the empty string rather than falling back).

### C23 — the local db harness is a plan-level obligation, not a note

The spec's Testing section says db-marked tests are "CI only — no Docker locally, per the run's standing constraint". **That constraint no longer holds**: Postgres 16.14 is live and the harness exists. Every db-marked task in this plan **runs locally before it commits**, which is what let F34's successor ship green on its first CI run. The cost is the revert obligation at the top of this file.

---

## Scope fence — read this before every task

**F33 ships the ticket, the customer's own view of it, and the printable QR.** It ships no staff verb of any kind.

| Not in F33 | Whose |
|---|---|
| Take-next, push-assign, finish, skip, call; **every status transition**; `called_at`, `requeued_at`, `skip_count` writes | **F58** |
| The staff-facing waitlist panel; merging or removing a duplicate ticket | **F58** |
| The public wall board at `/queue` | **F59** |
| `customers.marketing_opt_in_at`; promoting a consenting ticket into `customers`; the retention sweep; the per-boutique notice override; possession proof before a first send | **F20** |
| Server-side dedup in any spelling — no unique index, no advisory lock, no pre-check, no `IntegrityError` path, no duplicate branch | **Ruling 3, declined outright** |
| Cross-device recovery; OTP on check-in; editing or cancelling her own ticket | **declined outright** |
| Wait-time estimates or analytics; bride-priority ordering; per-visit QR codes | pre-decided #28 / #30, `e6-instore-realtime.md` |
| Per-IP or distributed rate limiting; a `Retry-After` header; reparenting the throttle classes onto one base | **F21** |
| A shared `usePoll` in `packages/ui` | **D9** |
| SMS of any kind | — |

If a task's diff grows a status write, a staff surface, a `customers` touch or a second poll target, it has left F33.

---

# Part 0 — the plan

## Task 0 — This plan, and the twenty-three spec amendments
`.planning/plans/qr-walkin-queue.md` (this file), `.planning/specs/qr-walkin-queue.md`

No test, no code. Amend the spec so it is the binding statement of every resolution above:

- **Header** — add a line recording that F57 merged 2026-08-03 and that D15 and Risk 9's numbers are superseded by C1.
- **D15 + Risk 9** — replace the build-at-`0015` rule with C1's four steps. Keep the `KeyError: '0015'` evidence as recorded history (it is why the rule exists) and mark it as the *pre-merge* situation. Delete the F57 rebase-conflict paragraph's specific claim; keep "keep the diff append-shaped" for the two live sessions.
- **D14** — "the EIGHTH" → **"the NINTH"** (C2); the `MANAGE_API` counts → thirteen / a fourteenth (C3); the nav row → after `floor`, before `staff`, with the `Nav.test.tsx` consequences (C4); `checkin_link()`'s home → `app/queue/service.py` (C16).
- **D9 / D11 / D12** — re-point every `BoardSection.tsx` citation at `lib/usePoll.ts` and the rewritten file (C5, C18c/e).
- **D6** — the read's metering order becomes C6's five steps, with the key-space argument and the declined consult-before-lookup variant; the miss-flood wording becomes C17's; and the create's 429 copy requirement + Risk 1's availability half + the new «Deployment ordering» row are C9's.
- **D7** — replace the Referer sentence and the 1-vs-360 arithmetic with C7's truth.
- **D8** — the two `autoComplete="off"` attributes, `navigate(…, { replace: true })`, and the honest reach-table row (C8).
- **D5** — the `COMMENT ON COLUMN` carrier and the one sentence about pre-swap consents (C11).
- **«Deployment ordering»** — restate "what not enabled means mechanically" in terms of `settings.checkin_enabled`; replace «Declined: a `queue_enabled` tenant setting» with the flag's own justification and keep the tenant-setting refusal (C10).
- **Testing** — the `:day` seed becomes two earlier-day tickets with the negative control stated (C12); the source guard gains the second path and the signature assertion (C13); the identical-phone case folds into the RLS assertion (C14); the stub sentence (C20); the `ar.ts` clause (C22); "353" → no number (C19).
- **D2, D3, D4, conflicts 1/8, Risks 1/3b** — replace every `LOOP-STATE.md:NNN` with a quote plus a section name; restate `skip_count`'s justification (C15).
- **D8's focus paragraph** — reword per C21. **`:39` → `:40`, `:399` → `:400`, "two partial unique indexes" → one** (C18a/b/d).

- **Done when**: every C1–C23 is in the spec; `grep -n "LOOP-STATE.md:[0-9]" .planning/specs/qr-walkin-queue.md` returns nothing; `grep -n "the EIGHTH\|0015_queue_tickets\|down_revision = \"0014\"" .planning/specs/qr-walkin-queue.md` returns nothing.
- **Commit**: `docs(planning): F33 implementation plan and twenty-three spec amendments — Gate 2 self-approved`

---

# Part I — the backend

## Task 1 — The migration **and** the ORM model, as one atomic change (D2, D15/C1)
`Backend/migrations/versions/0016_queue_tickets.py` (**new**), `Backend/app/models/queue_ticket.py` (**new**), `Backend/tests/test_migrations.py`

**The two halves ship together and this is not a preference.** Nothing in this repo derives a mapping from a migration and no model↔migration parity test exists. Without `app/models/queue_ticket.py`, every backend line Tasks 2–5 specify is an `AttributeError` or an import failure.

**Resolve the revision id at build time. Do not read it off this document.**

```
cd "/Users/mrwen/Documents/Github/Ryan + rawad + mrwen/.worktrees/qr-walkin-queue/Backend" && uv run python -m alembic heads
```

As of 2026-08-03 it prints `0015 (head)`, so the file is `0016_queue_tickets.py`, `revision = "0016"`, `down_revision = "0015"`. If F19 or F53 has landed first, that is wrong and `alembic heads` is right. **Reorder this commit onto the branch tip at rebase, so C1 step 3 costs one amend.**

### The failing tests first (`db`-marked, appended to `test_migrations.py`, **run locally**)

Follow the file's own convention: **the round-trip test goes last in the file**, owns no fixtures, and wraps the downgrade in `try/finally: command.upgrade(cfg, "head")` — these tests mutate the live session-scoped schema and leaving it down fails unrelated modules with `UndefinedTable`.

1. `test_the_queue_tickets_migration_creates_the_table` — `queue_tickets` exists; `queue_day` is `date`, `NOT NULL`; `marketing_opt_in_at` is a **nullable** `timestamp with time zone`; read from `information_schema.columns`.
2. `test_customers_still_has_no_marketing_opt_in_column` — the Ruling 2 assertion. A later reader who "helpfully" re-adds the ADD COLUMN half reddens a test instead of quietly reopening the write path.
3. **`test_the_queue_tickets_definitions_are_pinned`** — the highest-value test in the feature, because what it guards is a *future* edit: when F58 or a later feature wants a fifth status it collides with a pinned literal and a deliberate review. **CAPTURE the literals from the server; never transcribe them.** Use the `test_migrations.py:502-507` / `:621-626` idiom — `pg_get_constraintdef(oid)` for the three CHECKs and `pg_indexes.indexdef` for the one index — asserted **after this feature's migration** (i.e. at `head`), never after a hardcoded revision id. Captured on a live 16.14 today, as the **expected shape** to cross-check against, not to paste:

   ```
   queue_tickets_visit_type_check  CHECK ((visit_type = ANY (ARRAY['bride'::text, 'evening'::text])))
   queue_tickets_status_check      CHECK ((status = ANY (ARRAY['waiting'::text, 'in_service'::text, 'done'::text, 'removed'::text])))
   queue_tickets_skip_count_check  CHECK ((skip_count >= 0))
   idx_queue_tickets_tenant_day_active  CREATE INDEX idx_queue_tickets_tenant_day_active ON public.queue_tickets USING btree (tenant_id, queue_day) WHERE (deleted_at IS NULL)
   ```
   `IN (…)` became `= ANY (ARRAY[…])`, every element gained `::text`, predicates gained parentheses, the table is schema-qualified.
4. **`test_queue_tickets_has_no_unique_index_but_the_primary_key`** — the Ruling 3 assertion. `SELECT count(*) FROM pg_index WHERE indrelid = 'queue_tickets'::regclass AND indisunique AND NOT indisprimary` is **0** (verified on the probe table). Re-adding the dedup index reddens a test rather than silently restoring the day-long denial and the presence oracle.
5. **`test_the_consent_column_carries_its_unverified_hedge`** (C11) — `col_description` on `queue_tickets.marketing_opt_in_at` is non-empty and contains `UNVERIFIED`. This is the only carrier of D5's hedge that survives F20 deleting test 2.
6. **A CHECK probed on four axes**, the `test_migrations.py:73-189` shape: superuser INSERT positive and negative on `status`; app-role UPDATE positive, negative, **and a read-back proving the refusal changed nothing**; and `ADD CONSTRAINT` against a populated table.
7. **`test_migration_0016_round_trips`** — upgrade applies, assert the end state; `downgrade` one revision, assert the **reverse** (the table is gone); `upgrade` to head, re-assert. Probing both directions is the `0013` docstring's rule: a silently no-op downgrade stays green while shipping an unrollbackable migration. **Last in the file, in `try/finally`.**

### The code

`0016_queue_tickets.py`, the `0008_bookings.py` idiom verbatim: raw `op.execute` DDL, the module-level `_STANDARD` block, a local `_updated_at_trigger` helper, the D2 `CREATE TABLE` with its inline CHECKs, **the one NON-unique partial index** with a comment stating what its predicate buys **and why there is no unique index on this table** (Ruling 3 — a later reader must meet that argument before adding one), the C11 `COMMENT ON COLUMN`, `_updated_at_trigger("queue_tickets")`, and **one trailing loop doing `GRANT SELECT, INSERT, UPDATE, DELETE ON queue_tickets TO app_user` and `enable_tenant_rls("queue_tickets")` together** (`0008:107-110`).

> Forgetting `enable_tenant_rls` fails a **different file's** test — `test_every_tenant_id_table_has_forced_rls` in `tests/test_tenant_isolation.py` scans `pg_class` for any `tenant_id` table without `relforcerowsecurity` — a confusing failure a long way from F33. Forgetting the GRANT fails nothing until the app role touches the table, i.e. in Task 6, as `permission denied`.

`downgrade()` is `DROP TABLE IF EXISTS queue_tickets` and nothing else — no explicit index, trigger or policy drops (`0008:113-115`). **F33 touches no existing table, so it has nothing to un-touch.** `models/customer.py` is **not** edited.

`app/models/queue_ticket.py` declares **every** column explicitly as `mapped_column`, the `models/booking.py` shape.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| `enable_tenant_rls("queue_tickets")` | delete the call | `test_every_tenant_id_table_has_forced_rls` **RED** |
| the `COMMENT ON COLUMN` | delete the statement | test 5 **RED** |
| the `status` CHECK | widen it to a fifth value | test 3 **RED** on a byte-identical comparison |
| `downgrade` | make it `pass` | test 7 **RED** on the reverse assertion |

- **Done when**: `bash "…/scratchpad/run-db-tests.sh"` green (baseline + the new cases); `make lint` clean; `make test` green with the new cases collected-and-deselected. Then **`git diff --stat` shows only F33 files, and `git checkout -- backend/tests/conftest.py`** before staging. `git show --stat` after committing confirms the lowercase pathspecs landed.
- **Commit**: `feat(queue): queue_tickets — the walk-in ticket table, its ORM model and its pinned definitions`

## Task 2 — `QueueTicketsRepository` and the position count (D3, C12, C13, C14)
`Backend/app/db/repositories/queue_tickets.py` (**new**), `Backend/tests/test_queue_repositories.py` (**new**)

### The failing tests first (`db`-marked, **run locally**)

`insert`; then **`by_id(session, tenant_id, ticket_id)` — the signature carries `tenant_id` explicitly and puts it in the `WHERE` beside `deleted_at IS NULL`**, matching `CustomersRepository.by_id` and the defence-in-depth rule its class docstring states. Cases: present / absent / soft-deleted / **present but owned by another tenant → `None`**.

**The position count**, D3's query:

```sql
SELECT count(*) FROM queue_tickets
 WHERE tenant_id = :tenant AND queue_day = :day
   AND status = 'waiting' AND deleted_at IS NULL
   AND COALESCE(requeued_at, created_at) < COALESCE(:my_requeued_at, :my_created_at)
```

- **`:day` is the TICKET's `queue_day`, never `today_jerusalem(clock)` — C12's seed, and the docstring carries the negative control.** Seed **two** tickets left `waiting` on the earlier day plus three of today's. Assert the **later** stale ticket reports **2**. Docstring, verbatim: *"With ONE earlier-day ticket the two bindings agree — its own-day position and its today-bound position are both 1 — so a single-ticket seed proves nothing. Two is the smallest seed under which the correct binding and the today-binding differ."*
- a ticket whose own status is not `waiting` → position `null`
- `requeued_at` set on the earliest ticket moves it to the back **and shifts every other position by one**
- `done` and `removed` tickets are not counted; another day's tickets are not counted; ties on the sort key do not crash
- **two tickets for one phone on one day both exist and report consecutive positions** (Ruling 3, asserted as a decision)

**`active_today` is NOT in this repository.** Ruling 3 deleted the pre-check and the method existed only for it.

**The Jerusalem day boundary, driven from the injectable clock**: two check-ins for one phone at `20:00Z` and `21:30Z` on 2026-07-18 (Jerusalem 23:00 on the 18th and **00:30 on the 19th**) land on two different `queue_day` values, so the second one's position is **1** — a new day's queue, not 2. Same pair across the 2026-03-27 spring-forward. **This test is only writable because `queue_day` is a stored column fed by an injectable clock** (D4) — it cannot be written against a database-clock expression at all.

### The code

`QueueTicketsRepository` with exactly: `insert`, `by_id`, `position_of` (or `waiting_ahead`). No `by_phone`, no `active_today`, **no method whose signature names `phone`** — C13's signature guard is what holds that.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| the `:day = ticket.queue_day` binding | bind to `today_jerusalem(clock)` | the C12 case **RED** (`2 != 1`) — and with a one-ticket seed it would stay green, which is the point |
| `COALESCE(requeued_at, created_at)` | order by `created_at` alone | the requeue case **RED** |
| `deleted_at IS NULL` in `by_id` | drop it | the soft-deleted case **RED** |
| the explicit `tenant_id` predicate in `by_id` | drop it (RLS still on) | the cross-tenant case stays **green** — so this one is proven in Task 6 instead. Note it in the docstring rather than pretending the unit test covers it |

- **Done when**: local db suite green; `make lint` clean. **Revert `backend/tests/conftest.py`; `git diff --stat`; `git show --stat`.**
- **Commit**: `feat(queue): the queue-ticket repository and the read-time position count`

## Task 3 — Validation, schemas, the three limiters, `QueueService` and `checkin_link()` (D5, D6/C6, D7, C16)
`Backend/app/queue/__init__.py`, `…/validation.py`, `…/schemas.py`, `…/service.py` (all **new**), `Backend/app/core/config.py`, `Backend/tests/test_checkin_service.py` (**new**), `Backend/tests/test_checkin_qr_link.py` (**new**)

### The failing tests first (**fast**, fakes, no Postgres — the `test_storefront_validation.py` scaffold, where a statement escaping to a real session raises rather than passing silently)

**Shape validation** — blank name / 80-char boundary / 81 chars / each control-character class / every phone form `normalize_israeli_mobile` accepts and rejects / unknown `visit_type`. All raise a `DomainValidationError` subclass; **none charges the create budget**.

**The opt-in branch** — OFF (and absent) leaves `marketing_opt_in_at` `NULL` on the inserted ticket; ON sets it to the **injected clock's** instant. One INSERT either way; `app/queue/service.py` contains **no `try` block** (Ruling 3).

**The create budget** — `checkin:{tenant_id}` blocks and raises `CheckinThrottledError`; it is **charged after shape validation** (a blank-name 400 does not burn the boutique's allowance) and **before** the transaction (F33 has no proof to fail, unlike booking-create).

**The read's two budgets, metered per C6.** This is the block that must be written first and read hardest:

- a **hit** charges `position_ticket_limiter` and **leaves `position_miss_limiter` untouched**
- a **miss** charges `position_miss_limiter` and **leaves `position_ticket_limiter` untouched** ← *the assertion that fails if someone restores the record-before-lookup rule and reopens the unbounded key space*
- **the key-space assertion**: N reads with N distinct random UUIDs that all miss leave the per-ticket spy with **zero** recorded keys
- a spent per-ticket budget raises `CheckinThrottledError` **without a repository call** (assert the fake repo saw zero lookups)
- a spent miss budget 429s further **misses** while **hits keep answering 200**

**The Ruling-2 source guard** (C13) — read `Backend/app/queue/*.py` **and `Backend/app/db/repositories/queue_tickets.py`** as text and assert no occurrence of `CustomersRepository` or `app.db.repositories.customers`; assert `inspect.signature(QueueService.__init__)` names no customers repository; assert no public method of `QueueTicketsRepository` names a `phone` parameter. The repo already reads source in a test and says why — `tests/test_frontend_constant_parity.py:22-23`, with `REPO_ROOT` at `:42`. **This one can fail**: re-add the `upsert` and the import appears.

**`checkin_link()`** — `tests/test_checkin_qr_link.py`, the `test_booking_comms_templates.py` shape: always `https`, dev `base_domain` included, no double slash, the slug is not escaped away.

### The code

- `app/core/config.py` — **seven** new fields, each with its arithmetic written out in the `:152-164` style: `checkin_create_max_per_window: int = 200` / `checkin_create_window_seconds: int = 3600`; `checkin_position_max_per_ticket_window: int = 30` / `checkin_position_ticket_window_seconds: int = 60`; `checkin_position_max_misses_per_window: int = 120` / `checkin_position_miss_window_seconds: int = 60`; **and C10's `checkin_enabled: bool = False`**.
- `app/queue/validation.py` — the ticket-specific bounds, reusing `MAX_CUSTOMER_NAME_LENGTH` (`booking/validation.py:40`) and `normalize_israeli_mobile` (`notifications/validation.py:31`) rather than restating them, plus `CheckinThrottledError` and `QueueTicketNotFoundError(DomainNotFoundError)`. **The 404 needs no new handler** — it inherits `main.py:757-758` by MRO.
- `app/queue/schemas.py` — `CheckinCreateRequest` (a `ForbidExtraModel`), `PositionRequest`, `TicketView` (`{id, status, position, called_at}` and **nothing else**), `CheckinQrResponse`.
- `app/queue/service.py` — module-level `checkin_link(*, slug, base_domain)` (C16) above `QueueService`; the class takes **three limiter kwargs**, the repository, an injectable `Clock` and `base_domain`. One `create`, one `position`, one `checkin_qr`.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| charge-on-hit-only (C6) | move `record_failure(ticket_key)` back before the lookup | the miss-leaves-it-untouched case **and** the key-space case **RED** |
| miss-brake charge | delete it | the walk case **RED** |
| the source guard's second path | drop `queue_tickets.py` from the file list, then add a `CustomersRepository` import there | the guard must go **RED**; confirm it does |
| record-after-validation ordering | charge before validating | the blank-name-does-not-burn case **RED** |

⚠ **No `errorMessageKey` case is added anywhere** — F33 adds **no error code**. `SPEC_ERROR_CODES` stays the existing four.

- **Done when**: `make lint` + `make test` green **locally**. This is the first milestone: the whole service contract is exercised with no Postgres. `git diff --stat`; conftest reverted; `git show --stat`.
- **Commit**: `feat(queue): the check-in service, its three budgets and the miss-only metering rule`

## Task 4 — The public sibling router, **the deployment flag**, and the wiring (D1, D7, C10)
`Backend/app/queue/router.py` (**new**), `Backend/app/main.py`, `Backend/tests/test_checkin_api.py` (**new**), `Backend/tests/test_storefront_api.py`, `Backend/tests/test_spa_serving.py`

### The failing tests first (**fast**)

**`tests/test_checkin_api.py`**, on the F11 posture template (`tests/test_notifications_api.py`) — a local `_client()` builds a real app with `create_app(resolver=…)`, **with `checkin_enabled` monkeypatched on** (the `test_spa_serving.py:389` shape), swaps **one** `app.state` attribute for a stub, and installs `FakeAuthService` both on `app.state` and via `dependency_overrides[get_auth_service]` so the owner cookie is genuinely resolvable.

> **C20, stated so the two assertions below do not read as contradictory:** the fake mints a **fresh id per call** and is constructed **per `_client()`**, so cookie-blindness compares two *first* calls across two clients (equal) and the duplicate test compares two calls on *one* client (different).

It must prove: both routes answer **anonymously** (201/200, and **no `set-cookie`**); an unresolvable Host answers the generic 404 `TENANT_NOT_FOUND` (i.e. the paths are **not** in `EXEMPT_PATHS` — never add a `/storefront` path there); `cache-control: no-store` on both; **GET stays a 405** on both; the tenant reaches the service as the **host-derived** id; each handler reaches its own service method with the right arguments; a service `DomainValidationError` leaves as 400 and `QueueTicketNotFoundError` as 404 `NOT_FOUND`; `CheckinThrottledError` leaves as 429 with the **byte-identical** shared body (`main.py:137-139`); `SPEC_ERROR_CODES` is set-equal to the four.

**Cookie-blindness, byte-level and per route** — a request carrying a **valid** owner session cookie gets a response byte-identical to the anonymous one, and no `set-cookie`. Position: `.content ==` on two identical reads. Create: **two separate clients, compared on the FULL `.json()`** (`test_booking_api.py:220-236`). This matters because `test_owner_cookie_changes_nothing` in `test_storefront_api.py` loops `ROUTES`, which is GET-only, and covers **neither** F33 route.

**The one-shape assertions, and they are the point of Ruling 3** — two creates with the **same** `(tenant, phone, day)` both answer **201** with a full `TicketView`; the two ids **differ**; the two responses are **structurally identical** (same status, same key set, same types). Assert the key set explicitly (`{"id", "status", "position", "called_at"}`) so a future refactor cannot reintroduce a `ticket` envelope or an `existing: true` flag without reddening.

**C10's flag test — new, and the only mechanism behind Ruling 4:**

```
test_the_check_in_surface_is_absent_until_the_deployment_flag_is_set
```
With `checkin_enabled` at its **default**, both public paths answer **404** and neither appears in the route table. Docstring names both preconditions (F58's panel, F20's sweep) and says the flag is the checkable form of «Deployment ordering».

**`tests/test_storefront_api.py::test_no_route_is_registered_twice_across_routers`** — the explicit `/storefront` path literal (`:574-599`) gains `"/storefront/checkin"` and `"/storefront/checkin/position"` with a comment naming F33 and `test_checkin_api.py`, **and the call site gains the flag-on app build**. This is the one test F33 is *meant* to break; the literal stays a literal on purpose (`:569-571`). The six `ROUTES`-parametrized guards need **no edit**, because F33 registers no new GET (D1).

**`tests/test_spa_serving.py`'s `SHELL_PATHS` (`:67-80`) gains `"/checkin"` and `"/q/tick3t"`** with a comment naming F33 — a **data** edit, not a test edit; `test_every_storefront_router_path_serves_the_shell` is parametrized over it and picks both up for free. Serving already works (`_RESERVED_SEGMENTS` at `main.py:323`), so this closes a **silent coverage hole**, not a red build — and `/checkin` is printed on a physical sign, which makes it the most deep-linked URL the product has.

### The code

`app/queue/router.py` — `APIRouter(prefix="/storefront", dependencies=[Depends(_no_store)])`, the `notifications/router.py:45` / `booking/router.py:67` posture byte-for-byte. **`_no_store` is a local three-line copy, not an import** — the shipped convention. **No ordinal in its comment**: the running count in those comments is already out of step and F33 must not add a wrong number to it. `get_current_tenant(request)` as the **first statement in each handler**, never a `Depends()`. Two POSTs, `status_code=201` on the create.

`app/main.py`, four edits:
1. `app.state.queue_service = QueueService(...)` beside the other service constructions — three `FixedWindowRateLimiter` instances built inline (`main.py:632-644` is the shipped shape, and its comment at `:637-639` states the one-budget-one-instance rule), plus `base_domain=settings.base_domain` (`:657` is the shipped shape) and the clock.
2. `@app.exception_handler(CheckinThrottledError)` returning `TOO_MANY_ATTEMPTS_BODY` verbatim — **the tenth handler returning that literal**, zero new codes.
3. **C10's gated include**, after `booking_router` (`:1067`) and before `_register_spas(app)` (`:1070`), with the sibling comment naming F33 as the **fourth** `/storefront` sibling.
4. `_register_spas(app)` stays **last**.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| the `if settings.checkin_enabled:` gate | make the include unconditional | the flag test **RED** |
| `get_current_tenant(request)` in a handler | take the tenant from the body instead | the host-derived test **RED** |
| `Depends(_no_store)` | drop it | the `no-store` cases **RED** |
| the `CheckinThrottledError` handler | drop the registration | the 429 body test **RED** (bare 500) |

- **Done when**: `make lint` + `make test` green **locally**. **This is the second milestone**: the full public surface, both verbs and the deployment gate are exercised end to end with no Postgres. `git diff --stat`; conftest reverted; `git show --stat`.
- **Commit**: `feat(queue): the public check-in routes behind the Ruling-4 deployment flag`

## Task 5 — `segno`, the printable QR route, and the dev proxy (D14, C2, C3)
`Backend/pyproject.toml`, `Backend/uv.lock`, `Backend/app/queue/manage_router.py` (**new**), `Backend/app/main.py`, `Backend/tests/test_checkin_qr_api.py` (**new**), `frontend/apps/manage/vite.config.ts`

### The failing tests first (**fast**)

**`tests/test_checkin_qr_api.py`** — its own `ROUTES` table (one row), the per-router convention `dashboard/router.py`'s docstring names: **nine** routers now mount `/manage` and a duplicated `(method, path)` silently wins or loses on include order with no error. Plus:

- **401** with no session
- **200 for a shift manager** — the both-roles decision, asserted rather than assumed
- `cache-control: no-store`
- the URL is composed from the **host-derived slug** and the **injected `base_domain`** — two different hosts, two different URLs
- the response is JSON and `qr_svg` **starts with `<svg` AND contains `xmlns="http://www.w3.org/2000/svg"`**

> **The second half is the assertion that catches the blank-poster failure.** Verified against segno 1.6.6: the default `save(buf, kind="svg")` emits an XML declaration and fails the first assertion; **`svg_inline()` passes the first assertion and emits no `xmlns`, rendering BLANK through a `data:` URI** — a green suite and an empty square on a printed poster. Only `save(buf, kind="svg", xmldecl=False)` is correct.

- `SPEC_ERROR_CODES == {NOT_AUTHENTICATED, NOT_AUTHORIZED}` — **`CSRF_ORIGIN_MISMATCH` is deliberately absent**: `CsrfOriginMiddleware` fences mutating methods only and this is a GET.

**`tests/test_spa_serving.py::test_the_manage_dev_proxy_names_every_manage_api_segment`** — **no edit to the test**; it goes red until `vite.config.ts` gains `checkin-qr`, which is the intended forcing function. **The segment must be lowercase letters and hyphens only**: the scrape is `r'"\^/manage/\(([a-z|-]+)\)"'`, so a digit or an underscore makes `re.search` return `None` and the failure reads as "no proxy key found".

**`tests/test_staff_role_gating.py` — no edit.** Its walker derives from the live route table, so the new route is default-deny-checked and matrix-checked for free. It must **not** join `OWNER_ONLY` or `test_route_table_matches_the_permission_matrix` reports `unenforced_owner_only`; and `require_role` must name **exactly** `StaffRole.OWNER, StaffRole.SHIFT_MANAGER` — naming all five would redden `test_the_floor_roles_reach_exactly_the_floor_routes` (`:240`), which is an **exact set equality** against `FLOOR_OPEN`.

### The code

`uv add segno` in `Backend/` — **commit `pyproject.toml` and `uv.lock` together.** CI runs `uv sync --locked` as its very first step, so a `pyproject` edit without a regenerated lockfile fails before lint or tests. `segno` ships `py.typed` (verified against 1.6.6), so **no `[[tool.mypy.overrides]]` block** and the boto3 precedent does not apply.

`app/queue/manage_router.py` — the `app/dashboard/router.py` shape verbatim, including a module docstring in that register. One route, no audit row, no body, no rate limiter, **no `AuditAction` member** (nothing here writes).

The exact call, in the service:
```python
buf = io.BytesIO()
segno.make(url).save(buf, kind="svg", xmldecl=False)
qr_svg = buf.getvalue().decode()
```

`main.py` — `app.include_router(queue_manage_router)` **after `gateway_router` (`:1056`) and before `storefront_router` (`:1059`)**, keeping every `/manage` router contiguous and ahead of the anonymous surfaces, carrying the numbered shadowing comment as **"The NINTH"** (C2).

`vite.config.ts` — `checkin-qr` inserted between `bookings` and `dashboard`; **and the comment at `:13-17` fixed in the same edit** (C3): «The **eleven** names» → **thirteen**, «a **twelfth** router» → **a fourteenth**.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| `xmldecl=False` | use the default `save(kind="svg")` | the starts-with-`<svg` assertion **RED** |
| the whole call → `svg_inline()` | swap it | the `xmlns` assertion **RED** — *this is the blank-poster case; if it does not go red the test is wrong* |
| `require_role(...)` | drop it from the router | `test_every_manage_route_is_role_gated` **RED** |
| the shift-manager admission | narrow to `OWNER` only | `test_route_table_matches_the_permission_matrix` **RED** as `wrongly_narrowed` |

- **Done when**: `make lint` + `make test` green **locally**, including the proxy-segment test. `git diff --stat` shows `Backend/pyproject.toml` **and** `Backend/uv.lock`; conftest reverted; `git show --stat`.
- **Commit**: `feat(queue): the printable check-in QR route, segno and the dev proxy segment`

## Task 6 — The RLS isolation suite (**`db`-marked, run locally**) (C14)
`Backend/tests/test_queue_isolation.py` (**new**)

**Non-negotiable, and it is the crown-jewel suite `architecture.md:48` calls permanent.** Connected **only as the app role** over a `NullPool` engine via the **`app_role_url`** fixture (`conftest.py:137`) — **never `migrated_db`**, because the container superuser bypasses RLS and GRANTs unconditionally and every assertion would pass vacuously.

### The failing tests first

- tenant A writes a ticket; **tenant B's every reader returns `None`/empty/0**
- a foreign-tenant ticket id reads as **missing (`None`, the 404 path), never a 403** that would confirm existence
- **C14's rewritten identical-phone case**: tenant B writes a ticket with the **identical phone and identical `queue_day`** as A's row; **A's reader returns exactly one row (hers), B's returns exactly one row (his), and neither id is visible to the other.** The phone is deliberately the same string in both tenants — the claim is that a phone is not a cross-tenant identity, and the **failing half is the visibility half**, because Ruling 3 left nothing that could refuse the write (`count(*) FROM pg_index WHERE indisunique AND NOT indisprimary` is 0, verified)
- tenant B's position count never counts A's tickets
- tenant A re-reads and nothing of hers moved
- **the Ruling-2 db half**: a full check-in with the opt-in **ON** and with it **OFF** leaves `SELECT count(*) FROM customers` **unchanged** — the behavioural companion to Task 3's source guard
- **the GRANT is exercised**: the app role can `INSERT`, `SELECT` and `UPDATE` on `queue_tickets` (omitting the GRANT fails nothing until exactly here, as `permission denied`)

**The consent column is on this same table**, so "B cannot read or set A's consent" is covered by the same assertions rather than needing a `customers` case of its own.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| `enable_tenant_rls("queue_tickets")` in the migration | delete the call, re-run | **every** isolation probe **RED** — if any stays green, the suite is connected as the superuser and is worthless |
| the `app_role_url` fixture | swap to `migrated_db` | the probes go **GREEN vacuously** — run this once, deliberately, confirm it, then restore. That is the proof the suite is measuring RLS and not nothing |
| the explicit `tenant_id` predicate in `by_id` | drop it | stays green (RLS carries it) — **record that in the docstring** rather than implying the test proves the defence-in-depth |

- **Done when**: `bash "…/scratchpad/run-db-tests.sh"` green; both mutation-checks performed and restored. `make lint` clean. **Revert `backend/tests/conftest.py`; `git diff --stat`; `git show --stat`.**
- **Commit**: `test(queue): forced RLS isolation for queue tickets and the no-customers-write proof`

---

# Part II — the frontend

## Task 7 — Storefront i18n, the API client, the courtesy pointer and the two routes (D8, C7, C22)
`frontend/apps/storefront/src/i18n/he.ts`, `…/i18n/ar.ts`, `…/api.ts`, `…/lib/checkinTicket.ts` (**new**), `…/router.tsx`, `…/__tests__/router.test.tsx`, `…/__tests__/api.test.ts`, `frontend/apps/storefront/package.json`, `frontend/pnpm-lock.yaml`

> ⚠ **`make lint` greps this app's source INCLUDING COMMENTS.** The literal `localStorage` fails at `qa-greps.sh:33`. `left-`/`right-`/`pr-`/`ml-` in English prose fail at `:40`. A bare 6-digit hex fails at `:42`. Run `make qa-greps` before staging.

### The failing tests first

**`__tests__/router.test.tsx`** — `/checkin` and `/q/abc` match their own routes; an **unknown ticket reaches the position page**, not the catalog (the `/b/{token}` precedent test); a stray `%` decodes to the raw segment rather than throwing; the two `DOC_TITLE_KEYS` resolve; **the ticket id never appears in `document.title`**. That last assertion is the *only* thing holding that rule — no shipped comment states it (`router.tsx:58-59` is about outcome copy, not tokens). **F33 establishes the rule; the test is the enforcement.** This file **does** mount the Router, which is why the title rule is asserted here and the page-level "does not touch the title" is asserted with a sentinel in Tasks 8 and 9.

**`__tests__/api.test.ts`** — `createCheckin()` and `getQueuePosition()` POST to the right paths with the body verbatim (**no case conversion, ever, on this client**) and **pass `referrerPolicy: "no-referrer"`** (C7). Asserted as a **fetch-mock argument check**, the `BookPage.test.tsx` `autoComplete` shape. Mutation-check: drop the option and it goes red.

**`checkinTicket.ts`** — read / write / clear round-trips under the constant key.

### The code

- `package.json` — **`axe-core` as a devDependency, `^4.12.1`**, matching `apps/manage/package.json`. Without it the promised storefront axe tests in Tasks 8 and 9 are **unbuildable**: axe-core is a devDependency of `apps/manage` only and under pnpm's isolated `node_modules` the import does not resolve. Regenerate `pnpm-lock.yaml` in the same commit — the same forcing-function discipline `uv.lock` gets for `segno`.
- `api.ts` — `CheckinCreateRequest`, `TicketView` (snake_case verbatim); `createCheckin()` and `getQueuePosition()` on the exported `api` object; **`apiFetch`'s `init` gains `referrerPolicy?: ReferrerPolicy`, forwarded to `fetch`** (C7). `referrerPolicy: undefined` on every existing call site is byte-identical to today, so F9/F13/F16 are untouched. **No `CheckinCreateResponse`** (Ruling 3 leaves one shape) and **no new `case` in `errorMessageKey`** (F33 adds no error code).
- `lib/checkinTicket.ts` — **~6 lines**, read/write/clear under the bare constant key `"checkin:ticket"`. Not a tenant slug: the storefront has **none** (`api.ts:225-227` — `name` is "the display name, not the slug"), and origin partitioning is what provides isolation since every boutique is its own subdomain. **Its comment must state the positive rule WITHOUT naming the banned API.** Wording to use verbatim: *"Session-scoped on purpose: one browser tab, one visit, gone when the tab closes. A store that outlived the tab would keep offering a stranger's ticket on a shared phone. The argument is in spec D8."*
- `router.tsx` — `RouteName` +2; `RouteMatch` +2 arms carrying the token-is-opaque comment; `DOC_TITLE_KEYS` +2 (**the one the compiler forces**); `QUEUE_PATH = /^\/q\/([^/]+)$/`; `/checkin` as an exact `===` match beside `/about`; the `/q/…` match **before the unconditional `return { name: "catalog" }`** with a comment stating the ordering is load-bearing for the identical reason `:92-96` gives; the id through `decodeId`; two `case`s in the render switch. **The `default: return <CatalogPage />` means a missing `case` compiles clean and renders the dress grid under the check-in title — the router test is the only thing that catches it.**
- `i18n/he.ts` — `document.checkin`, `document.queuePosition`, and a `checkin.*` block: `checkin.notice` **and `checkin.optIn`** (both **counsel-gated**, D13 — ship the interim Hebrew verbatim from the spec, both interpolating `{{boutique}}`), `checkin.phoneHint`, the **three** freshness keys `checkin.updatedAt` / `checkin.staleAt` / `checkin.pausedAt`, the pause/resume pair and its Aria variants, the boutique-unavailable arm's copy, the courtesy link (**"the last check-in made from this device"**, never «המקום שלך בתור»), and **C9's create-429 string, which sends her to the counter rather than inviting a retry** and names no duration.
- `i18n/ar.ts` — the **same keys**, Hebrew standing in untranslated (Q3 / pre-decided #47). **Never empty strings** — i18next's `returnEmptyString` default renders `""` rather than falling back. **C22: this extends a deliberately partial bundle** (2 608 bytes against `he.ts`'s 25 508; its `document:` block carries only `manageTitle`) and the builder is **not** being asked to backfill the rest of it. **No storefront parity guard exists** (Risk 7), so this is a review item.
- `validation.ts` — **no change.** `validateName`, `normalizePhone`, `validatePhone` are imported as they are, so `MIRRORS` in `backend/tests/test_frontend_constant_parity.py` gains **no row**.

⚠ **Risk 8, and it bites immediately:** once `checkin` exists as an `he.ts` section, **any quoted `"checkin.…"` literal anywhere in `apps/storefront/src` is scraped as an i18n key** by `i18n-keys.test.ts` and must resolve to a defined, non-empty Hebrew string. Do not name a `data-testid` `checkin.submit`.

- **Done when**: `make fe-test` + `make fe-build` + `make qa-greps` green; `pnpm -r lint && pnpm -r typecheck` clean. `git diff --stat` shows `frontend/pnpm-lock.yaml`; conftest reverted; `git show --stat`.
- **Commit**: `feat(storefront): the check-in routes, API client, courtesy pointer and copy`

## Task 8 — `CheckinPage` (D8, D13, C8)
`frontend/apps/storefront/src/routes/CheckinPage.tsx` (**new**), `…/__tests__/CheckinPage.test.tsx` (**new**)

> ⚠ qa-greps warning as Task 7.

### The failing tests first

- every validator fires **on the forward press only** — not on blur, not on input; **all messages appear at once**; focus lands on the first failure; **no request is issued** on a failed validation (`BookPage.tsx:566-592` is the house rule)
- the opt-in is **unchecked by default** and its value reaches the request; it is a **native checkbox with its role left alone** (`@boutique/ui`'s `Toggle` renders `role="switch"`, the wrong semantic for a consent)
- the collection notice **and the opt-in label** are rendered as visible text, are not behind a disclosure, and are not `aria-hidden`
- the phone field's `help` text is wired into its `aria-describedby` (`Input.tsx:20-24`)
- the submit carries `min-h-11` (`size="md"`; `sm` is `min-h-9` = **36px, under the floor**) — **a class assertion, never a measurement**, because jsdom has no layout engine (`vitest.config.ts:9`)
- a **double-tap fires one request** — the guard is a **re-entrant boolean, not `disabled`**, because React commits `disabled` asynchronously and a fast double-tap on iOS fires two clicks inside one frame (`BookPage.tsx:769-772`)
- a 429 renders its own copy, **names no duration**, does not auto-retry, and **C9: sends her to the counter**
- **a failed submit moves focus to the error** — a `useEffect` keyed on the error state, **not** a `.focus()` in the `catch`, because the alert node does not exist yet when `setError` runs
- a **successful create navigates to `/q/{id}`** — there is no other outcome to test — **and C8: with `{ replace: true }`**, asserted against a `replaceState` spy
- **C8: both `Input`s carry `autoComplete="off"`**, asserted the way `BookPage.test.tsx` asserts the opposite. A comment on the attribute states why this contradicts the sibling surface.
- an **axe pass** (needs Task 7's `axe-core`)

**The `useBoutique()` arms — this is the privacy assertion (D8/D13):**
- with `loading: true` the page renders **no form, no notice and no opt-in**
- with `boutique: null` after loading it renders the boutique-unavailable state (`role="alert"` + retry `Button`, the `AboutPage.tsx:106-127` shape) and, again, **no form**
- with a loaded fixture the rendered notice **and** the rendered opt-in label each **contain the fixture's boutique name** ← *this is the one that fails against a hole, against a literal `{{boutique}}`, and against a form rendered in either degraded arm. "Visible, not behind a disclosure, not `aria-hidden`" all pass against the broken sentence.*

**The courtesy-pointer pair (D8):**
- with **no** entry: the form renders, **no** courtesy link, and **zero requests on mount** — asserted as a call count of zero, because zero server round-trip is the whole of what this pointer is
- with an entry: the link to `/q/{id}` renders, **still zero requests**, and its accessible name is the **last-check-in-from-this-device** string, not a "your position" string
- a successful create **writes** the id, **overwriting** whatever was there — assert a second create replaces the first id, which is the whole of "a different phone clears it" (no phone number is ever stored)

**The sentinel pair** — set `document.title` to a sentinel, render the page **in isolation** (`<StorefrontLayout><CheckinPage /></StorefrontLayout>`, **never `<Router />`** — `ManageBookingPage.test.tsx:83-89`), assert it is **unchanged** after mount. The precedent for the sentinel is `router.test.tsx:70`. Same for `document.activeElement` — "not a node this page owns". **C21:** the router's override only masks a page-level focus move on *client navigations* (`router.tsx:262-266` early-returns on first paint), which is exactly why the **direct-load** rendering is the one tested.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| **the failure-path focus effect** | move it into the `catch` as `.focus()` | the focus test **RED** |
| the `loading`/`error` form withholding | render the form in both arms | the two privacy cases **RED** |
| the re-entrant boolean | swap to `disabled={busy}` | the double-tap test **RED** |
| `autoComplete="off"` | drop it | the C8 assertion **RED** |
| `{ replace: true }` | drop it | the `replaceState` assertion **RED** |
| the zero-request-on-mount rule | add a "helpful" `useEffect` fetch | the call-count-zero cases **RED** |

- **Done when**: `make fe-test` + `make fe-build` + `make qa-greps` green; axe at **zero** violations; every mutation-check performed and restored. Conftest reverted; `git show --stat`.
- **Commit**: `feat(storefront): the check-in form, its collection notice and its degraded arms`

## Task 9 — `QueuePositionPage` — the copied poll, the 2.2.2 pause and the terminals (D9/C5, D10, D11, D12)
`frontend/apps/storefront/src/routes/QueuePositionPage.tsx` (**new**), `…/__tests__/QueuePositionPage.test.tsx` (**new**)

> ⚠ qa-greps warning as Task 7. **This file carries the most copied prose in the feature**, which is exactly where an English comment trips `:40`.

**Read the mechanisms off `frontend/apps/manage/src/lib/usePoll.ts`** at the line numbers in the ✅ table (C5), **and copy the comments with the code** — Risk 5's whole mitigation is that the copies are greppable by their own prose. **Do not import it**: it is inside `apps/manage` and unreachable from `apps/storefront` under pnpm's isolated `node_modules`, and D9 declines promoting it into `packages/ui`.

**The six mechanisms to copy, minus the four with no subject here** (mutation-in-flight suppression and its re-arm; the pointer-hold skip; the stranded-row rescue; the scroll-once guard — this page never mutates and has no list):

1. **Schedule-after-settle, one arming site** (`usePoll.ts:151-161`). At most one request in flight per tab **by construction**. Not `setInterval` + `AbortController`.
2. **One monotonic `generationRef`** (`:123`), compared at three points — success, catch, **and the `.finally()` re-arm**. Missing the compare in `.finally()` lets a superseded load arm a second timer and the at-most-one property is gone.
3. **`tickRef` updated on every render with no dependency array** (`:116`, `:201`).
4. **`document.hidden` guarded twice** — in `schedule()` and in `tick()` (`:156`, `:187`) — and `visibilitychange` back to visible **bumps the generation and fetches immediately** (`:252-254`).
5. **Failure backoff, 5s doubling to a 60s cap, reset on the first success** (`:119`, and `MAX_BACKOFF_MS` at `:19`).
6. **The terminal branch** — D10, and **not** F34's `{401, 403}`: the storefront carries no session, so both of those are unreachable here.

**The two `0c7015a` fixes are not optional, and the reason is the same for both: axe cannot see either of them.**

**(a) The unmount guard** — `runningRef.current = false` **BEFORE** `clearTick()` (`usePoll.ts:233-234`). `clearTick()` alone cancels only the timer armed right now; the arming sites are `.finally()` callbacks that run *after* the cleanup, and nothing in `tick → load → finally → schedule` touches React state, so an orphaned loop **cannot be broken by unmounting**. On the board this leaked one permanent 5-second loop per navigation away. **Here it is worse**: the orphan is an *anonymous* loop against a public endpoint, from a customer's phone in a bag.

**(b) Failure-path focus restoration** — a `useEffect` keyed on the error state, **never** a `.focus()` in the `catch`. Applies to the pause/resume control, whose name changes under the user's focus.

**Declined, per D11: the idle stop.** F34/F57 ship one; porting it here would stop the updates at precisely the moment she is still waiting and has stopped touching her phone. What it buys there is covered here by `document.hidden`, D6's per-ticket budget and D10's closed-status terminal.

### The failing tests first — `vi.useFakeTimers()`, every advance wrapped in `act()`

- **exactly one request per tick and never two in flight** — advance timers while a fetch is unresolved and assert the call count did **not** grow
- **the unmount guard**: with a request in flight, unmount, resolve the pending promise, advance ten intervals, assert **no further calls**
- `document.hidden` pauses; `visibilitychange` back to visible fetches **immediately** rather than after the interval
- **the pause control stops the loop** — tap, advance several intervals, assert no calls — **and resume fetches before the interval elapses** and resets a backed-off gap; **one** button, its name flips, **no `aria-pressed`**; it is the **first** control in the section, before the auto-updating content; `toHaveClass("min-h-11")` and `toHaveClass("focus-visible:outline-focus")` (`BoardSection.test.tsx:510-512`), and **it has a text label** — `min-h-11` covers the height half only, the ×44 width half is the label; it keeps focus across the press
- **the three freshness states read differently as TEXT** — live / paused / stale render three distinct strings, `toHaveTextContent`, **never a class**, because a class-only assertion *is* the colour-alone defect it is supposed to catch. Derive in one line, the `BoardSection.tsx:320` shape: `const freshKey = stopped ? "checkin.pausedAt" : stale ? "checkin.staleAt" : "checkin.updatedAt";`
- **consecutive failures back the interval off and a success resets it** — walk the whole ladder and pin the cap in **both** directions (it did not double past the cap, **and** the next call still comes)
- **404 stops the loop** and renders the not-found state with a route back to `/checkin`; **a malformed id stops the loop**; **`status: "done"` stops the loop on a 200** — advance ten intervals and assert no further calls. This is D10's success-terminal, **the only place in the product where a 200 ends a loop**. **The `done` fixture is seeded by the stubbed API client**, which is the only way it can be produced: nothing in F33 writes a terminal status, so there is no product path to drive it and **no backend or e2e assertion may try** — that test would hang.
- **429 does NOT stop the loop** — it backs off and resumes
- **the announced region does not change on a poll tick.** The naive version passes against the broken code, because assigning an identical string still replaces the Text node. The real test populates the region first, observes it with a `MutationObserver` (`BoardSection.test.tsx:593`) across **three** ticks, and asserts **both** that the ticks happened and that `takeRecords()` is empty
- **the called transition IS announced, once** — one write on the `waiting → called` edge, and no further writes on subsequent ticks observing the same fact
- **the freshness line is present, not `aria-hidden`, and outside every announced region** — the assertion is `closest('[role="status"],[role="alert"],[aria-live]')` is `null`, the three-way check `BoardSection.test.tsx:651-653` already ships as three separate calls. **`closest('[aria-live]')` alone is VACUOUS**: every live region in this repo is a bare `role="status"` with no `aria-live` attribute, and `closest()` matches attributes, not implicit ARIA — so it returns `null` **even with the line nested inside the region**
- **…with a NEGATIVE CONTROL, and it is not optional.** A fixture renders the freshness line **inside** a `role="status"` region and asserts the selector **DOES** match. Without it the assertion is trusted on the strength of having passed, which is precisely how the vacuous version survived review.
- **the terminals clear the courtesy pointer** — after a 404, after a malformed id and after a `done` status, the entry is gone, so `/checkin` stops offering a link into a dead page
- the sentinel pair (`document.title` unchanged, focus not moved on mount), rendered in isolation
- an **axe pass** — **explicitly not sufficient: axe has no SC 2.2.2 rule**, so the pause assertions are the only automated coverage of a Level A criterion on this screen and **must not be dropped as redundant with the axe row**

### Mutation-checks (mandatory — these five are the named list)

| Mechanism | Remove it | Expect |
|---|---|---|
| **the poll unmount guard** | move `runningRef.current = false` **after** `clearTick()` | the unmount test **RED** |
| **the pause control** | delete the button | the pause/resume tests **RED** (axe stays green — that is the point) |
| **the failure-path focus restoration** | move it into the `catch` | the focus test **RED** |
| **the live-region negative control** | render the line inside `role="status"` in the main fixture | the outside-the-region test **RED**; and the control fixture must be **GREEN** — run both |
| **the success terminal** | drop the `{done, removed}` branch | the `status: "done"` test **RED** |

- **Done when**: `make fe-test` + `make fe-build` + `make qa-greps` green; axe at **zero** violations; every mutation-check performed and restored. Conftest reverted; `git show --stat`.
- **Commit**: `feat(storefront): the live position page, its 5s poll and the 2.2.2 pause control`

## Task 10 — The console's QR section and the twelfth nav item (D14, C2, C3, C4)
`frontend/apps/manage/src/App.tsx`, `…/api.ts`, `…/components/CheckinQrSection.tsx` (**new**), `…/i18n/he.ts`, `…/i18n/ar.ts`, `…/__tests__/CheckinQrSection.test.tsx` (**new**), `…/__tests__/Nav.test.tsx`, `…/__tests__/i18n.test.ts`

> **Keep this diff APPEND-SHAPED.** Two other sessions are live in this repo. F57's specific collision is discharged (it merged), but `App.tsx` and the manage i18n bundles remain the most contended files.

### The failing tests first

- **`CheckinQrSection.test.tsx`** — the URL renders as **selectable text** (a printed QR with no legible URL beside it strands anyone whose camera fails); the `<img>` carries a **non-empty `alt`**; a load failure renders a `role="alert"`; an axe pass.
- **`Nav.test.tsx`** — C4's edits, in one pass: `NAV_LABELS` gains «קוד סריקה» **after «לוח היום» and before «צוות»**; `.slice(0, 8)` → `.slice(0, 9)` at **both** `:100` and `:184`; `toHaveLength(10)` → `(11)` at `:136`; the test names at `:96` and `:131` and the comment at `:71` say nine / eleven.
- **`i18n.test.ts`** — a **new `HE_F33` constant with its own floor**, folded into `HE`. **Not merged into an existing constant**: the file's own comment says two constants rather than one widened filter is deliberate, because folding lets a feature's floor shrink and still pass. Plus the ar-parity assertion, which covers the manage side only.

### The code

- `App.tsx` — `SectionKey` gains `| "checkinQr"` as the **twelfth** member; `NAV` gains `{ key: "checkinQr", labelKey: "nav.checkinQr", roles: ALL }` **after the `floor` row and before `staff`** (C4 — this keeps F57's "Immediately after the board" comment true for `floor`, keeps the two owner-only rows last, and lands «קוד סריקה» at `NAV_LABELS` index 8); one render branch. **`useState<SectionKey>("dashboard")` is NOT touched.**
- `api.ts` — `CheckinQrResponse` + one `apiFetch` wrapper. No case conversion — this app speaks the backend's snake_case verbatim.
- `CheckinQrSection.tsx` — heading, the `<img src={"data:image/svg+xml;utf8," + encodeURIComponent(qr_svg)} alt={…} />`, the URL as selectable text, a print affordance, and the `StaffSection.tsx` skeleton / alert / `h2 tabIndex={-1}` shape. **A `data:` URI in an `<img>` renders the SVG in an image context — no scripts, no external references** — which is strictly safer than an inline `<svg>` or `dangerouslySetInnerHTML`.
- `i18n/he.ts`, `i18n/ar.ts` — `nav.checkinQr` + a `checkinQr.*` block, **flat dotted keys appended as a per-feature block**; **both files**, or the ar-parity guard reddens.

- **Done when**: `make fe-test` + `make fe-build` green; the console renders a twelfth nav item that swaps to the QR panel; `pnpm -r lint && pnpm -r typecheck` clean. Conftest reverted; `git show --stat`.
- **Commit**: `feat(manage): the printable check-in QR section and its nav row`

## Task 11 — The check-in journey e2e
`frontend/e2e/storefront.spec.ts`

**Three coordinated edits or `installApi` falls through to its dress-detail branch and answers a 404 that reads as a product bug**: the `BookingEndpoint` union, the `BOOKING_PATHS` pathname map, and the `bookingFixture()` default reply queue.

**Journey 1** — goto `/checkin`; wait for **real content** (never a skeleton — a skeleton makes the axe scan vacuous); fill by **Hebrew accessible name**; submit; land on `/q/…`; assert the position; **assert `ctaBar(page)` has count 0** (this route reserves no CTA gutter, because `hasBookingBar()` is catalog-and-dress only); run `axeViolations(page)` against `toEqual([])` on **each** materially different state (form, form-with-errors, live position, closed).

**Journey 2, short — Ruling 3** — submit the **same phone twice**; assert the second submit **also lands on a `/q/…` page with a position**, and that the two URLs carry **different ticket ids**. That is the end-to-end statement that the create has one outcome and therefore discloses nothing about the first ticket.

> ⚠ **The e2e run builds the apps and serves them via `vite preview` with no backend**, so both journeys run entirely against `installApi`'s interception. **No `/manage` e2e is promised** — the console's interception harness does not exist (F34's Risk 8) and F58 is scheduled to build it. **And no e2e may drive a `done` status** (D10) — there is no product path to it.

- **Done when**: `make e2e` green; the existing storefront and console specs stay green. Conftest reverted; `git show --stat`.
- **Commit**: `test(e2e): the walk-in check-in journey and Ruling 3's duplicate outcome`

## Task 12 — Gates, the run report, and shipping
No files.

Run the full verification below, report what ran and what passed, and carry forward:

- **Risk 2 — two counsel-gated privacy strings, re-nagged.** `in_run_gates` F33 stays **open**. `checkin.notice` and `checkin.optIn` are **interim**, in two named slots, in two files each, with **no component hardcoding any part of either**. *Owner: the user, via counsel.*
- **C10 — the deployment flag is the gate.** `checkin_enabled` ships **`False`**. Flipping it requires **both** F58's waitlist panel **and** F20's retention sweep. Say this in the run report in those words, and say that C11's hedge makes pre-swap consents non-promotable — a set that is **empty by construction** while the flag is off.
- **C9 — the create's tenant ceiling is also a boutique-wide kill switch**, 200 requests buy an hour of outage, and **F58 does not discharge it**. Owner F21.
- **C1 — the migration number.** State the number the branch was built at, the number it shipped at, and the `alembic heads` output that decided the second.
- **C6 / C7 / C8** — three plan-resolved corrections to shipped decisions (metering order, `referrerPolicy`, autofill + back stack). Each is one line to overturn.
- **Risk 7 — `ar.ts` on the storefront has no parity guard** and F33 invents none.
- **Risk 12 — the audit trail is silent about walk-ins.** F33 writes no `audit_log` row and adds no `AuditAction` member. When F58 adds staff actions, "who called her forward" and "who removed her" want rows, and `audit_log.action` is plain TEXT with no CHECK, so neither needs a migration.

No push, no PR from this task — the orchestrator owns review and shipping. **The shipping checklist below is the precondition list it runs.**

---

## Shipping checklist — run in this order, top to bottom

1. **`git diff --stat` and `git status --short` are clean of `backend/tests/conftest.py`.** `git log -p -- backend/tests/conftest.py` on the branch shows **no F33 commit**. If it does, the harness patch shipped — rewrite the history before anything else.
2. **`git show --stat` on every commit** confirms the lowercase pathspecs landed. `git add Backend/…` silently skips modified tracked files.
3. **F19's PR has merged.** (C1 step 4. The spec's "F57 must merge first" precondition is already discharged — F57 merged 2026-08-03.)
4. `git fetch origin && cd "…/Backend" && uv run python -m alembic heads` **on a checkout of `origin/main`**. Note the number.
5. **Renumber the migration to head + 1** — three edits: the filename, the `revision` literal, the `down_revision` literal. Amend the migration commit (it is the branch tip by Task 1's instruction).
6. Rebase onto `origin/main`. Re-run `alembic heads` **on the rebased branch** and confirm a **single** head.
7. **`bash "…/scratchpad/run-db-tests.sh"` green on the rebased branch**, then **revert `backend/tests/conftest.py` again** — the runner re-applies the patch.
8. Full local gate (below), all six targets green.
9. `grep -rn "localStorage" frontend/apps/storefront/src` returns **nothing**. `make qa-greps` output is **byte-identical to the pre-F33 baseline** — capture the baseline before Task 7 and diff it.
10. `grep -n "checkin_enabled" Backend/app/core/config.py Backend/app/main.py` returns the default `False` and the gated include. This is the grep that replaces trust in the poster.
11. Open the PR. The three gating jobs are `Backend (lint, types, tests)`, `Frontend (lint, types, build)`, `Frontend E2E (Playwright + axe)`.

---

## Verification — the full local gate sequence

```
make lint      # Backend: ruff check . && ruff format --check . && mypy app tests
               #   + Frontend: pnpm -r lint && pnpm -r typecheck
               #   + bash frontend/scripts/qa-greps.sh
make test      # Backend: pytest -m "not db" -q
bash "/private/tmp/claude-501/-Users-mrwen-Documents-Github-Ryan---rawad---mrwen/0dba6822-2444-475a-a2aa-18e3d89ceffc/scratchpad/run-db-tests.sh"
               # recreates f33_test, applies the LOCAL-ONLY conftest patch, runs pytest -m db
               # ⚠ REVERT backend/tests/conftest.py afterwards, every time
make fe-test   # Frontend: pnpm -r --if-present test
make fe-build  # Frontend: pnpm -r build
make e2e       # Frontend: pnpm -r build && playwright install --with-deps chromium && pnpm e2e
```

**Green looks like:**

- **`make lint`** — ruff clean, `ruff format --check` clean, **mypy zero errors over `app` and `tests`** (segno ships `py.typed`, so no override is needed and none is added), `pnpm -r lint` and `pnpm -r typecheck` clean across all four workspace packages, and `qa-greps.sh` **exit 0** printing **exactly the pre-F33 baseline** — capture it before Task 7 and diff. Any new `FAIL` line from F33 is prose, not a code defect, and the fix is the prose.
- **`make test`** — all fast tests pass. `test_checkin_api.py`, `test_checkin_service.py`, `test_checkin_qr_link.py` and `test_checkin_qr_api.py` green; `test_storefront_api.py` green with its **one deliberate literal edit**; `test_spa_serving.py` green with its **two `SHELL_PATHS` data rows** and the `checkin-qr` proxy segment; `test_staff_role_gating.py` and `test_frontend_constant_parity.py` pass **unedited**; the `db`-marked modules **collected and deselected**. ⚠ **Two `test_config.py` failures are always false locally** — `Backend/.env` leaks `MEDIA_BUCKET`. CI is green. Do not chase them.
- **the local db suite** — baseline (369 on this tree at 2026-08-03, 1277 deselected, ~25s) **plus** F33's new cases in `test_migrations.py`, `test_queue_repositories.py` and `test_queue_isolation.py`, all green. The 9 `test_media_upload_s3.py` errors need MinIO and stay red locally — **expected; F33 touches no S3.**
- **`make fe-test`** — `router.test.tsx`, `api.test.ts`, `CheckinPage.test.tsx`, `QueuePositionPage.test.tsx`, `CheckinQrSection.test.tsx`, `Nav.test.tsx`, `i18n.test.ts` all green; **axe at zero violations on all three new screens**; every mutation-check in Tasks 8–9 performed and restored.
- **`make fe-build`** — both apps build; no unused-import or unused-variable TS error.
- **`make e2e`** — the two new storefront journeys green, existing specs unchanged.
- **CI additionally** — the same db suite against Testcontainers, where the captured literals are re-read off the CI server rather than off the local one. ⚠ **A first CI red on a test bug here is budgeted** (`.memory/boutique-ci-first-run-surprises.md`); check `continue-on-error` on the job before believing it.

---

## What a local run cannot prove

The local harness closes almost all of F34's gap. What is left:

| Task | The local run proves | CI-only |
|---|---|---|
| 1 | the migration, the round trip, the captured literals, the RLS/GRANT loop — **all of it, against real Postgres 16.14** | that the captured literals are identical on the CI server's Postgres build. They should be — same 16.x deparser — and the assertion **re-reads** rather than transcribes, so a difference is a red test and not a silent pass |
| 6 | the isolation suite in full, including the vacuity mutation-check | the same, on the container superuser / app-role split CI builds |
| 11 | the e2e journeys against `vite preview` | the same, on CI's Chromium |
| — | — | `test_media_upload_s3.py` (MinIO; F33 touches no S3) |

**Task 4 is the milestone**: the full public surface, both verbs, the deployment gate and the wire shape are exercised end to end with no Postgres.

---

## Task-by-task file manifest

| Task | New | Modified |
|---|---|---|
| 0 | — | `.planning/plans/qr-walkin-queue.md`, `.planning/specs/qr-walkin-queue.md` |
| 1 | `backend/migrations/versions/0016_queue_tickets.py`, `backend/app/models/queue_ticket.py` | `backend/tests/test_migrations.py` |
| 2 | `backend/app/db/repositories/queue_tickets.py`, `backend/tests/test_queue_repositories.py` | — |
| 3 | `backend/app/queue/__init__.py`, `…/validation.py`, `…/schemas.py`, `…/service.py`, `backend/tests/test_checkin_service.py`, `backend/tests/test_checkin_qr_link.py` | `backend/app/core/config.py` |
| 4 | `backend/app/queue/router.py`, `backend/tests/test_checkin_api.py` | `backend/app/main.py`, `backend/tests/test_storefront_api.py`, `backend/tests/test_spa_serving.py` |
| 5 | `backend/app/queue/manage_router.py`, `backend/tests/test_checkin_qr_api.py` | `backend/pyproject.toml`, `backend/uv.lock`, `backend/app/main.py`, `frontend/apps/manage/vite.config.ts` |
| 6 | `backend/tests/test_queue_isolation.py` | — |
| 7 | `frontend/apps/storefront/src/lib/checkinTicket.ts` | `…/src/api.ts`, `…/src/router.tsx`, `…/src/i18n/he.ts`, `…/src/i18n/ar.ts`, `…/src/__tests__/router.test.tsx`, `…/src/__tests__/api.test.ts`, `frontend/apps/storefront/package.json`, `frontend/pnpm-lock.yaml` |
| 8 | `frontend/apps/storefront/src/routes/CheckinPage.tsx`, `…/src/__tests__/CheckinPage.test.tsx` | — |
| 9 | `frontend/apps/storefront/src/routes/QueuePositionPage.tsx`, `…/src/__tests__/QueuePositionPage.test.tsx` | — |
| 10 | `frontend/apps/manage/src/components/CheckinQrSection.tsx`, `…/src/__tests__/CheckinQrSection.test.tsx` | `…/src/App.tsx`, `…/src/api.ts`, `…/src/i18n/he.ts`, `…/src/i18n/ar.ts`, `…/src/__tests__/Nav.test.tsx`, `…/src/__tests__/i18n.test.ts` |
| 11 | — | `frontend/e2e/storefront.spec.ts` |
| 12 | — | — |

**Never modified, and that is an assertion:** `backend/tests/conftest.py` (local-only patch), `backend/tests/test_staff_role_gating.py`, `backend/tests/test_frontend_constant_parity.py`, `backend/app/models/customer.py`, `backend/app/db/repositories/customers.py`, `backend/app/storefront/router.py`, `frontend/scripts/qa-greps.sh`, `frontend/apps/storefront/src/validation.ts`, `frontend/apps/manage/src/lib/usePoll.ts`, `frontend/apps/manage/src/components/BoardSection.tsx`.

---

## Testing plan → spec criteria

| Spec criterion | Where |
|---|---|
| `queue_tickets` exists; `queue_day` DATE NOT NULL; `marketing_opt_in_at` nullable TIMESTAMPTZ | `test_migrations.py` (db, **local**) |
| The three CHECKs and the one partial index, **byte-identical from CAPTURED definitions** | `test_migrations.py` (db) — the test that will still be earning its keep when F58 wants a fifth status |
| **No unique index but the primary key** (Ruling 3) | `test_migrations.py` (db) |
| **`customers` has no `marketing_opt_in_at`** (Ruling 2) | `test_migrations.py` (db) — *deleted by F20; C11's `COMMENT ON COLUMN` is what survives it* |
| The consent hedge is carried in the schema (C11) | `test_migrations.py` (db) — `col_description` |
| Forced RLS on the new table | `test_every_tenant_id_table_has_forced_rls` (db, **unedited**) |
| Position = `count(*) + 1` over the **ticket's own `queue_day`**, `COALESCE(requeued_at, created_at)` ordered, `null` when not waiting | `test_queue_repositories.py` (db) — **C12's two-earlier-day seed, negative control in the docstring** |
| The Jerusalem day boundary and the spring-forward, driven from the injectable clock | `test_queue_repositories.py` (db) |
| Two tickets for one phone on one day both exist and report consecutive positions | `test_queue_repositories.py` (db) + `test_checkin_api.py` (fast) + e2e journey 2 |
| Shape validation; the opt-in branch; the create budget charged after validation | `test_checkin_service.py` (fast) |
| **The read's metering: hit charges the ticket key only, miss charges the miss key only, and N misses leave zero ticket keys** (C6) | `test_checkin_service.py` (fast) — *the assertion that closes the memory DoS* |
| **F33 never touches `customers`** | `test_checkin_service.py` source guard (fast, **C13's two paths + the signature check**) + `test_queue_isolation.py` count assertion (db) |
| Both routes anonymous, cookie-blind byte-for-byte, `no-store`, GET 405, host-derived tenant | `test_checkin_api.py` (fast) |
| One response shape, 201 always, key set `{id, status, position, called_at}` | `test_checkin_api.py` (fast) |
| **The surface is absent until `checkin_enabled`** (C10) | `test_checkin_api.py` (fast) — *the only mechanism behind Ruling 4* |
| The two paths are registered exactly once across routers | `test_storefront_api.py` explicit literal (fast, **one deliberate edit**) |
| Both new storefront paths serve the SPA shell | `test_spa_serving.py` `SHELL_PATHS` (fast, **data edit**) |
| The QR route: 401, **200 for a shift manager**, no-store, host-derived slug, `<svg` **and** `xmlns` | `test_checkin_qr_api.py` (fast) |
| The QR route is default-deny gated, does **not** join `OWNER_ONLY`, and the three floor roles do **not** reach it | `test_staff_role_gating.py` (fast, **unedited** — live route-table walker + exact `FLOOR_OPEN` equality) |
| `checkin_link()` as a pure function | `test_checkin_qr_link.py` (fast) |
| The dev proxy names every `/manage` segment | `test_spa_serving.py` (fast, **unedited** — `vite.config.ts` is what changes) |
| RLS: B sees nothing of A's; identical phone + identical day is **two rows, each visible only to its owner** (C14); a foreign id reads as missing | `test_queue_isolation.py` (db, **app role only**) |
| The two routes match, the id is opaque, a stray `%` does not throw, **the ticket id never reaches `document.title`** | `router.test.tsx` (vitest) |
| **`referrerPolicy: "no-referrer"` on both queue calls** (C7) | `api.test.ts` (vitest, fetch-mock argument check) |
| Forward-press-only validation; one request on a double-tap; failure-path focus; 429 copy naming no duration and pointing at the counter | `CheckinPage.test.tsx` (vitest) |
| **The notice and the opt-in label each carry the boutique's name, and the form is withheld in both degraded arms** | `CheckinPage.test.tsx` (vitest) — *the privacy assertion* |
| The courtesy pointer: zero requests on mount, the last-check-in label, overwrite on every create | `CheckinPage.test.tsx` (vitest) |
| `autoComplete="off"`; navigate with `replace` (C8) | `CheckinPage.test.tsx` (vitest) |
| Neither page sets `document.title` or moves focus on mount — **sentinel form, rendered in isolation** | `CheckinPage.test.tsx` + `QueuePositionPage.test.tsx` (vitest) |
| One request per tick, never two in flight; **the unmount guard**; hidden-tab pause; immediate fetch on return; backoff ladder capped in both directions | `QueuePositionPage.test.tsx` (vitest, fake timers) |
| **SC 2.2.2** — one button, name flips, no `aria-pressed`, first in the section, `min-h-11`, focus ring, text label, resume fetches early and resets the backoff | `QueuePositionPage.test.tsx` — **the only automated coverage; axe has no rule for it** |
| The three terminals (404, malformed id, **`done` on a 200**) stop the loop and clear the pointer; 429 does not | `QueuePositionPage.test.tsx` — **the `done` fixture is stubbed; no backend or e2e test may drive it** |
| The announced region never changes on a tick (`MutationObserver`, three ticks); the called transition is announced once | `QueuePositionPage.test.tsx` |
| The freshness line reads differently as **TEXT** in three states and sits outside every announced region — **with the negative control** | `QueuePositionPage.test.tsx` |
| Zero axe violations on all three new screens | the three `*.test.tsx` (needs `axe-core` in `apps/storefront/package.json`) |
| The twelfth nav item, both roles, `NAV_LABELS` index 8, `.slice(0, 9)` at both sites | `Nav.test.tsx` (vitest) |
| Manage he/ar parity for the new block | `i18n.test.ts` (vitest, `HE_F33` with its own floor) |
| The check-in journey and Ruling 3's duplicate outcome | `e2e/storefront.spec.ts` |

---

## What could go wrong in review

Every item here is a **recorded ruling**. A reviewer who raises one should find the reasoning rather than file a finding.

1. **"The spec says build the migration at 0015 and this built at 0016."** **C1.** F57 merged on 2026-08-03 and `alembic heads` is `0015`. Building at 0015 would be a duplicate revision id. The rule that replaced the fixed grid is in `LOOP-STATE.md`'s MIGRATION CHAIN block: resolve from `alembic heads` immediately before the rebase, and make the migration the branch tip so the renumber is one amend.
2. **"F33 ships a feature flag and the spec says «There is no feature flag and F33 does not build one»."** **C10, and it is the single most important change in this plan.** The spec's gate is that nobody prints the poster. `/checkin` is a guessable path on a public subdomain that the SPA catch-all already serves, so at merge it is a live unauthenticated PII-and-consent collector behind counsel-gated wording, into a table with no retention job and no remedy. The spec's own declined alternative — a `queue_enabled` **tenant setting** — is correctly refused (a migration plus a manage form). An env boolean is neither, and it is the same discipline D6 already applies to six numbers. Three lines and one test.
3. **"The read's metering order does not match D6."** **C6.** D6's order records the per-ticket key **before** the lookup, and that key comes from the request body — so 200 000 fresh UUIDs in one window leave 200 000 live buckets in the single API process. `rate_limit.py:14-16` states the bounded-key-space rule the shipped limiters all obey and F33 was the first to break. Charging on hits only restores it and **deletes** a line. The finding's stronger variant (consult the miss brake before the lookup) was **declined** because it would 429 legitimate hits during a miss-flood.
4. **"`apiFetch` grew a parameter."** **C7.** D7's "1 log line instead of 360" is false on this deployment: `Referrer-Policy: strict-origin-when-cross-origin` sends the full path **same-origin**, and the SPA is same-origin. The ticket id was going to ride `Referer` on all 360 polls. One optional field, `undefined` at every existing call site, behaviour-identical for F9/F13/F16.
5. **"`autoComplete="off"` contradicts `BookPage`."** **C8, deliberately.** D8 names the door tablet as the scenario and then defends only the `sessionStorage` pointer. Autofill hands the previous bride's name and mobile to the next arrival; `TicketView` is careful to carry neither, and the form field hands over both. WCAG **2.0** AA has no SC 1.3.5, so this costs nothing conformance-wise.
6. **"`navigate(…, { replace: true })` — the router docstring reserves `replace` for guard redirects."** **C8.** A submitted form must not be the Back target, and on a shared tablet a live ticket URL must not be one press away. **The residual is stated, not smoothed**: `replaceState` clears the back-stack entry, **not** the browser's global history or the address bar. A kiosk needs kiosk mode.
7. **"Two shipped test files were edited."** `test_storefront_api.py`'s explicit `/storefront` literal (deliberate — `:569-571` says "adding a public surface must fail one test on purpose") and `test_spa_serving.py`'s `SHELL_PATHS` (a **data** row, closing a silent coverage hole on the URL that is printed on a physical sign). `test_staff_role_gating.py` and `test_frontend_constant_parity.py` are **unedited** and that is the assertion.
8. **"`skip_count` has neither reader nor writer in F33."** True, and D2 closed it. **C15 corrects its justification**: the spec cited a `LOOP-STATE.md` line that does not say what it was cited for. The honest reason is that one `INTEGER NOT NULL DEFAULT 0` in the migration that creates the table is cheaper than a migration in the feature that was scoped not to have one.
9. **"Every `BoardSection.tsx` citation in D9/D11/D12 is wrong."** **C5.** F57 extracted the loop into `lib/usePoll.ts` and rewrote the file. The *content* the spec cites is all still there at the new locations in the ✅ table, unmount guard included (`usePoll.ts:233-234`).
10. **"The `:day` test looks over-specified with two stale tickets."** **C12, and it is the whole point.** With one, the correct binding and the buggy one **both return 1** — proven on a live 16.14 server. Two is the smallest seed under which the test can fail. Risk 4 forbids exactly this class, and the round-2 review found four of them in this spec.
11. **"The identical-phone isolation case cannot fail."** It could not, as written — Ruling 3 removed every unique constraint, so nothing could refuse the write. **C14** folds it into the visibility half, which can.
12. **"The create can be DoS'd by 200 requests."** True, named, and **F21's**. **C9.** The reply is the copy — the 429 sends her to the counter — plus an honest row saying F58 does **not** discharge it. Chasing it with a bigger number moves the number, not the property.
13. **"F33 collects consent and calls the column `marketing_opt_in_at`, the same name F20 will add on `customers`."** D5 and **C11**. The hedge now rides a `COMMENT ON COLUMN` where F20's author actually meets it, asserted by a test that outlives the `customers`-has-no-column assertion F20 deletes.
14. **"The `done` terminal is unreachable, so its test is fake."** D10 says so in the spec, in those words. The fixture is **stubbed at the API client**, which is the only way it can be produced — nothing in F33 writes a terminal status. **No backend or e2e assertion may drive it; that test would hang.** This is one of the three findings behind Ruling 4.
15. **"axe passes, so the a11y work is done."** **Risk 4.** axe has **no SC 2.2.2 rule**, and it cannot see a focus move that never happened — the class that shipped twice in this repo. The pause assertions and the two focus tests are the only automated coverage of a **legal** requirement here, and the live-region assertion ships a **negative control** because its first specification could not fail.

---

## Out of scope (unchanged from the spec)

Dispatch, take-next, push-assign, skip, finish, call — **F58** · the staff-facing waitlist panel and every remedy on a ticket, including merging a duplicate — **F58** · the public wall board at `/queue` — **F59** · `customers.marketing_opt_in_at`, the promotion, the retention sweep, the per-boutique notice override and the possession proof before a first send — **F20** · server-side dedup in any spelling — **Ruling 3, declined outright** · cross-device recovery and OTP on check-in — declined outright · editing or cancelling her own ticket from the position page · bride-priority ordering (`visit_type` records the fact and nothing sorts on it) · wait-time estimates and any owner reporting — pre-decided #28 · per-visit QR codes — pre-decided #30 · check-in for a customer who already holds a booking — **F34**'s `checked_in_at`, reconciled at **F58** · any staff action on a ticket from F34's board · a shared `usePoll` in `packages/ui` — **D9** · per-IP or distributed rate limiting, a `Retry-After` header, and reparenting the nine throttle classes onto one base — **F21** · a he/ar parity guard for the storefront — Risk 7, inherited · SMS of any kind.
