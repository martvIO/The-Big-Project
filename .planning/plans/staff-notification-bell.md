# Plan: Feature 35 — Staff in-app notification bell (Epic E6)

**Spec**: `.planning/specs/staff-notification-bell.md` (Gate 1 standing-approved; C1–C3 resolved)
**Design**: `.planning/design/screens/staff-notification-bell/design.md` (§0–§10, gate accepted 2026-08-06; P1–P4, F-B1–F-B4 binding)
**Plan written**: 2026-08-06. **Observed alembic head at plan time: `0026_waitlist_entries` (F22, PR #49).** F24/F25/F28 plans are queued ahead of this build, so **this plan's migration number WILL shift.** Build it at **head+1 as observed in the F35 worktree at build time**, re-resolve at rebase per §5.
**Depends on**: F31 (roles), F34 (console), F58 (dispatch), F37 (SOS) — all merged on `main`.
**Worktree**: `.worktrees/staff-notification-bell`, branched from `origin/main`.

---

## 0. How to read this plan

Every task is one TDD cycle: the named failing test first, then the code that makes it pass. Backend schema → producers → reads/routes → `packages/ui` slot → manage wiring → e2e; the UI needs settled wire shapes. The spec's §Data model / §Producers / §API / §Delivery / §UI contract and the design's §1–§7 + §10 are **binding and not restated here** — this plan maps them to files, tests and commits. Every path and line number below was verified against the tree on 2026-08-06.

## 1. Verified facts the tasks lean on

| Claim | Verified at |
|---|---|
| Head migration is `0026_waitlist_entries`; template for a new tenant table | `Backend/migrations/versions/0022_sos_alerts.py` (`_STANDARD`, `_updated_at_trigger`, `enable_tenant_rls`) |
| `FloorService.__init__` builds its own repositories, no DI | `Backend/app/floor/service.py:325-348` |
| `take_next` audit site, recipient `target_staff_id`, entity `assignment.id` | `Backend/app/floor/service.py:719` (in the `tenant_session` at `:699`) |
| `assign` audit site, same names | `Backend/app/floor/service.py:861` (session at `:829`) |
| `handover` audit site, recipient `new_staff_id`, entity `assignment_id` | `Backend/app/floor/service.py:1134` (session at `:1109`) |
| `raise_sos` audit site, recipient `target_id` (already reroute-resolved), entity `alert.id` | `Backend/app/floor/service.py:1568` (session at `:1507`) |
| Router is `prefix="/manage"`, class gate `Depends(require_role(*StaffRole))`; paths are `/floor/...` | `Backend/app/floor/router.py:158-170` |
| `FloorService.sos` — one `tenant_session`, returns `SosListRead(alerts, server_now)` | `Backend/app/floor/service.py:1447-1466`, dataclass at `:246` |
| `SosResponse` + `from_read` — where `unread_notifications` lands | `Backend/app/floor/schemas.py:575-589` |
| `ForbidExtraModel` for request bodies | `app.schemas`, used e.g. `Backend/app/atelier/schemas.py:34` |
| `app/notifications/` is TAKEN (SMS/OTP) — new module is `app/floor/notifications.py`, tests `test_bell_*.py` | `Backend/app/notifications/`, `Backend/tests/test_notifications_*.py` |
| `ConsoleShell` header wrapper `div` with the ⚠ comment; `guide` slot is the contract to copy | `Frontend/packages/ui/src/components/ConsoleShell.tsx:20-23, 52-70` |
| `Modal` already takes `describedById` (design §4 state E) | `Frontend/packages/ui/src/components/Modal.tsx:20, 53` |
| `packages/ui` has its **own** vitest (`pnpm test` in that package); ConsoleShell's suite | `Frontend/packages/ui/vitest.config.ts`, `src/__tests__/console-composites.test.tsx` |
| `SosContextValue` (the interface to extend) and `useSos` | `Frontend/apps/manage/src/lib/sos-context.ts:96-124` |
| `SosProvider` wraps `ConsoleShell`; `reachable` is already computed in `App.tsx` (F-B1's one-line fix) | `Frontend/apps/manage/src/App.tsx:202, 240, 245, 258` |
| The poll's read is `load()` → `api.getSos()`; `channelDown` derivation | `Frontend/apps/manage/src/lib/sos.tsx:136-166, 224` |
| Jerusalem helpers exist — **no new date code**: `jerusalemTime`, `jerusalemDate`, `jerusalemIsoDate`, `todayJerusalem` | `Frontend/apps/manage/src/lib/jerusalem.ts:30,35,43,74` |
| `floor` is **already** in the vite proxy alternation and in the e2e fixture's families — **zero edits, asserted** | `Frontend/apps/manage/vite.config.ts:20`, `Frontend/e2e/fixtures/manage.ts:76` |
| e2e stub style `replies: { "/manage/floor/sos": [...] }`, per-feature spec files | `Frontend/e2e/sos.spec.ts:180,500`; `Frontend/e2e/waitlist.spec.ts` |
| manage `he.ts`/`ar.ts` carry **no** `bell.*` block — free to take | grep, `Frontend/apps/manage/src/i18n/` |
| `UNAUDITED_BY_DECISION` exemption dict + its reason format | `Backend/tests/test_audit_coverage.py:160` |

## 2. Migration `NNNN_staff_notifications.py` (NNNN = head+1 at build time)

Raw SQL, `0022_sos_alerts.py`'s template verbatim: `_STANDARD` columns + the five domain columns and the CHECK exactly as the spec's §Data model DDL spells them, the one partial index `idx_staff_notifications_unread`, `_updated_at_trigger("staff_notifications")`, the house `GRANT`, and `*enable_tenant_rls("staff_notifications")` — **omitting the last fails `test_tenant_isolation.py::test_every_tenant_id_table_has_forced_rls`**. Rationale comment at the index (0018's demand). Downgrade drops the table and nothing else. **No second index** (spec's stated upgrade path is not built).

## 3. Ordered task list

### Phase A — schema, model, repository (commit 1)

| # | Task | Test first | Files (C=create, M=modify) |
|---|---|---|---|
| A1 | Migration per §2. | `test_migrations.py::test_migration_NNNN_creates_staff_notifications` (**db**) — table + the partial index pinned via `pg_indexes.indexdef` and the CHECK via `pg_get_constraintdef`, both **CAPTURED from the live cluster, never transcribed** (PG rewrites `IN (…)` → `= ANY (ARRAY[…])` and reorders index predicates — `test_migrations.py:571,849,1500` say so); `::test_migration_NNNN_round_trips`; `test_exactly_one_migration_head` and `test_every_tenant_id_table_has_forced_rls` stay green **unedited** | C `Backend/migrations/versions/NNNN_staff_notifications.py`, M `Backend/tests/test_migrations.py` |
| A2 | `StaffNotification` model + `StaffNotificationsRepository`: `insert(session, tenant_id, *, staff_user_id, actor_staff_user_id, kind, entity_id)`, `unread_count(session, tenant_id, staff_user_id)` (predicate **identical** to the partial index), `recent(session, tenant_id, staff_user_id, limit=20)` (LEFT JOIN `staff_users.name`, **no `deleted_at` filter on the join** — F37's shipped rule), `mark_read(session, tenant_id, staff_user_id, ids)` → new unread count. Every statement carries **both** `tenant_id` and `staff_user_id`. `kind` values on `app/models/constants.py`. | `test_bell_repository_db.py` (**db**, new) — insert round-trip; `recent` order + cap 20 + actor name resolved for a soft-deleted colleague and NULL when the row is gone; `mark_read` is idempotent (second mark keeps the first `read_at`); `mark_read` with another staffer's id changes nothing; unread count matches the index predicate. `test_bell_isolation.py` (**db**, new, `test_sos_isolation.py`'s shape) — tenant A never sees B's rows through any of the three reads, with and without the session variable | C `Backend/app/models/staff_notification.py`, C `Backend/app/db/repositories/staff_notifications.py`, M `Backend/app/models/constants.py`, C two test files |

### Phase B — the four producers (commit 2)

| # | Task | Test first | Files |
|---|---|---|---|
| B1 | `FloorService` gains `self._notifications = StaffNotificationsRepository()` (`:348`, beside `_session_rows`). One `await self._notifications.insert(...)` beside each of the four `_audit.record` calls, **inside the same `async with tenant_session`** — `:719`, `:861`, `:1134`, `:1568` — with the spec §Producers guards verbatim: `!= actor.id` on the first three, `target_id is not None` on the fourth. **No new `tenant_session` anywhere.** A no-op writes no row. | `test_bell_service.py` (fast, new) — the four guards as one table: self-dispatch (`take_next` and `assign`, where `target_staff_id = staff_user_id or actor.id`) writes nothing; dispatch-to-another writes exactly one row, right `kind` + `entity_id`; handover-to-self nothing; **role-routed SOS (`target_id is None`) writes nothing**; named SOS writes one; a reroute-to-NULL writes nothing | M `Backend/app/floor/service.py`, C `Backend/tests/test_bell_service.py` |
| B2 | No code — the transactional proof. | `test_bell_producers_db.py` (**db**, new) — force `take_next`'s `IntegrityError` path and assert **zero** notification rows alongside zero audit rows (commits with the event or not at all); the CHECK refuses a fourth `kind` | C `Backend/tests/test_bell_producers_db.py` |

### Phase C — reads, routes, count piggyback, registrations (commit 3)

| # | Task | Test first | Files |
|---|---|---|---|
| C1 | `app/floor/notifications.py` — the two read/write service methods over A2's repo (each its own `tenant_session`), plus schemas: `NotificationView {id, kind, actor_name: str\|None, created_at, read_at}` (**`entity_id` is NOT on the wire**), `NotificationListResponse {items}`, `MarkReadRequest(ForbidExtraModel) {ids: list[UUID]}` max 20, `MarkReadResponse {unread}`. Routes on the **existing** floor router: `@router.get("/floor/notifications")`, `@router.post("/floor/notifications/read")` — the class-level `require_role(*StaffRole)` is the whole gate, no per-route dependency. | `test_bell_validation.py` (fast, new) — `ids` cap 20 → 422, extra key → 422, `ids: []` is a 200 no-op. `test_bell_api.py` (fast, new) — both routes reachable by all five roles; 401 without a session; the list never returns another staffer's rows; `POST …/read` with someone else's id changes nothing and returns **her own** count | C `Backend/app/floor/notifications.py`, M `Backend/app/floor/schemas.py`, M `Backend/app/floor/router.py`, C two test files |
| C2 | **The count rides the SOS tick** (spec §Delivery): `SosListRead` gains `unread_notifications: int`, filled by one `unread_count(...)` **inside `FloorService.sos`'s existing `tenant_session`** (`:1457-1462`) — no second session, no second round trip. `SosResponse` + `from_read` carry it through. | `test_sos_api.py` / `test_sos_service.py` — the payload carries the field; it is that caller's own count and not the tenant's; **one session only** (assert the read still makes a single `tenant_session` entry) | M `Backend/app/floor/service.py`, M `Backend/app/floor/schemas.py`, M the two sos test files |
| C3 | Registrations, each a deliberate entry: `UNAUDITED_BY_DECISION[("POST", "/manage/floor/notifications/read")]` with the spec's reason ("a person marking her own notification read is not an administrative act"); the cross-tenant walker picks the two routes up under the existing staff cookie — **populate, don't exempt**. **`MANAGE_API` and `API_FAMILIES` stay byte-unchanged** (`floor` is already the segment) — assert it rather than edit it. | `test_audit_coverage.py` reds on the new mutating route until the entry lands — that red IS the failing test. `test_cross_tenant_walker.py::test_the_walk_and_the_exemptions_are_the_whole_route_table` reds until the routes walk. `test_spa_serving.py` and `test_staff_role_gating.py` stay green **unedited** — that is the contract | M `Backend/tests/test_audit_coverage.py`, M `Backend/tests/test_cross_tenant_walker.py` |

### Phase D — the `ConsoleShell` slot (commit 4, `packages/ui`)

| # | Task | Test first | Files |
|---|---|---|---|
| D1 | `ConsoleShellProps` gains `bell?: ReactNode`, rendered as the **first child of the existing chrome wrapper `div`, before `{guide}`** (design §1). The shell knows nothing about the control — `guide`'s contract verbatim, comment copied in shape. Nothing else in the file moves. | `console-composites.test.tsx` — new: `bell` renders inside the chrome wrapper and **before** `guide` in DOM order; **F-B4: every existing `ConsoleShell` assertion passes with a zero-line diff and omitting `bell` writes no node at all**. Run with `pnpm --filter @boutique/ui test` (this package has its own vitest) | M `Frontend/packages/ui/src/components/ConsoleShell.tsx`, M `Frontend/packages/ui/src/__tests__/console-composites.test.tsx` |

### Phase E — manage wiring (commits 5–6)

| # | Task | Test first | Files |
|---|---|---|---|
| E1 | `api.ts`: `SosResponse` gains `unread_notifications: number`; `listNotifications(): Promise<NotificationListResponse>`, `markNotificationsRead(ids): Promise<MarkReadResponse>` + the two types. `sos-context.ts`: `SosContextValue` gains `unreadNotifications: number` and `markRead(ids: string[]): Promise<unknown>`. `sos.tsx`: `load()` stores `result.unread_notifications` beside `setServerNow` (**one ref/state write, no new timer, no new `usePoll`**); `markRead` goes through the existing `mutate()` helper and sets the count from the response; on a terminal/`channelDown` tick the count **keeps its last value and is never zeroed** (design §4 state K). | `sos.test.tsx` — the count arrives off the tick payload; a failed tick keeps the last count; `markRead` sets the count from the POST response and rolls back on rejection; **still exactly one `usePoll` in the provider**. `api.test.ts` — the two new methods and their paths | M `Frontend/apps/manage/src/api.ts`, M `…/lib/sos-context.ts`, M `…/lib/sos.tsx`, M `…/__tests__/sos.test.tsx`, M `…/__tests__/api.test.ts` |
| E2 | `NotificationBell.tsx` per design §1–§6: bare `<button type="button" className={cn("min-h-11 min-w-11 px-2 text-sm text-ink-muted hover:text-ink", focusRing)}` with the **visible word** «התראות» (P1 — no icon, **no `Button`, no `size="sm"`**, F-W1); `<bdi dir="ltr">` badge in `Badge variant="neutral"`, `aria-hidden`, capped «9+», **absent entirely at zero**; exact count in `aria-label` only — **no `role="status"`, no `aria-live`, no `aria-expanded`, no `aria-haspopup`**. Panel is `Modal`: `<ul>`/`<li>` rows, `border-t` hairlines, `max-h-[60vh] overflow-y-auto`, states D/U/L/P/E/C/F1/F2 from §4 (**E uses `describedById`, F1 and F2 use `role="alert"` on first render**), cap note only at 20, «סמני הכל כנקרא» hidden when nothing on the page is unread and sending **the rendered page's ids only**. Rows: `jerusalemTime`/`jerusalemDate` via `todayJerusalem()` — absolute, never relative; unread marked by weight **and** the «חדש» badge; unknown `kind` skipped silently; `sos_targeted` rows are plain `<li>` (P2). Click order §3: `markRead([id])` → `onOpenFloor()` → `close()` → `#console-main` focus. Bare `<bdi>` on the actor name, logical properties only. | `NotificationBell.test.tsx` (new) — count in the accessible name (uncapped) while the badge shows «9+»; zero unread renders no badge node; unread badge + weight both present; unknown kind renders nothing; `sos_targeted` renders no button; mark-read optimistically zeroes and **rolls back with `bell.markFailed` on rejection**; F1 `role="alert"` on the first failed render; E resolves `aria-describedby` to the `bell.empty` line; cap note only at 20 items. ⚠ **Assert content, not focus** — jsdom stubs `showModal()` (`.memory/jsdom-has-no-dialog`); focus is the e2e leg's job | C `Frontend/apps/manage/src/components/NotificationBell.tsx`, C `Frontend/apps/manage/src/__tests__/NotificationBell.test.tsx` |
| E3 | `App.tsx`: `bell={<NotificationBell onOpenFloor={() => setSection(reachable.some(i => i.key === "floor") ? "floor" : "board")} />}` — **F-B1, one line, and the bell stays dumb**; `reachable` already exists at `:202`. | `App.test.tsx` — the bell renders inside `SosProvider` on every section; an **owner** (no `floor` nav row) lands on `board`, a **reception** on `floor` | M `Frontend/apps/manage/src/App.tsx`, M `…/__tests__/App.test.tsx` |
| E4 | The fifteen `bell.*` keys from design §7 into `he.ts`; `ar.ts` mirrors with the **Hebrew values** (pre-decided #47). Zero exclamation marks. `bell.retry` = «ניסיון נוסף» reused verbatim, no drift. | `i18n.test.ts` — a new `F35 bell keys resolve` describe in the shipped shape: every key present in both files, ar-presence guard, **no `!` in any value**, no digits in the static rows | M `Frontend/apps/manage/src/i18n/he.ts`, M `…/ar.ts`, M `…/__tests__/i18n.test.ts` |

### Phase F — e2e + axe (commit 7)

| # | Task | Test first | Files |
|---|---|---|---|
| F1 | `notifications.spec.ts` using `fixtures/manage.ts` — the `floor` family is **already** intercepted, so this **adds replies and does not fork the harness**: extend the `/manage/floor/sos` reply with `unread_notifications`, add `/manage/floor/notifications` and `POST /manage/floor/notifications/read`. Journey (sign in as `reception`): bell shows 2 → open panel → focus lands on a control, Esc returns it to the bell → tap a `dispatch_assigned` row → count drops to 1, the floor section renders, focus is on `#console-main` → «סמני הכל כנקרא» → 0 and no badge. Plus: `sos_targeted` row is not clickable; the list-failure retry; **F-B2 — no horizontal scroll at 375px with a long `display_name`, in both the badged and unbadged states**. **axe zero violations** on: header with badge, header without, open panel populated, open panel empty, open panel in the F1 failure state — each at 375 and 1440, RTL. | this IS the test | C `Frontend/e2e/notifications.spec.ts` |

## 4. Build environment — RECORD, these are facts not suggestions

- **No Docker locally.** Tests marked `db` (or `s3`) run **on CI only**. Do not chase local db-test failures.
- **The local fast lane (`make test`, `-m 'not db'`) points at a CLOSED Postgres port by design (F21).** A test dialing a real DB without the `db` marker fails locally — correct behavior, not a bug. Every db-touching test here (A1, A2, B2) **must** carry the `db` marker.
- **The worktree has no `Backend/.env`** — config-default tests behave differently than the main checkout (`.memory/local-env-breaks-config-tests`; there the failure is REAL if it appears).
- **Local gates, all must pass before push**: `make lint` · backend non-db tests (`make test`) · `make fe-test` · `make fe-build` · `make e2e`. `packages/ui` has its own vitest — confirm `make fe-test` runs it, and run `pnpm --filter @boutique/ui test` directly after D1 either way.
- The db-marked tests' **first run is CI** (`.memory/boutique-ci-first-run-surprises`) — write them carefully against §3 rather than iterating.
- Four gating CI jobs: Backend · Frontend · Frontend E2E (Playwright + axe) · Dependency audits. Only "Code wiki drift" is warn-only.

## 5. Build discipline

**Commit boundaries** (conventional, scoped):
1. `feat(bell): staff_notifications migration, model, repository` — A1–A2.
2. `feat(bell): notification rows at the four dispatch and SOS producers` — B1–B2.
3. `feat(bell): list and mark-read routes, unread count on the SOS payload` — C1–C3.
4. `feat(ui): ConsoleShell bell slot` — D1.
5. `feat(bell): count on the SOS context, notification bell component` — E1–E2.
6. `feat(bell): App wiring with role-aware floor target, he and ar copy` — E3–E4.
7. `test(e2e): notification bell journeys with axe` — F1.

**Migration renumber protocol**: built at observed-head+1 in the worktree (`alembic heads`, **not** file order). **F24/F25/F28 are queued ahead — assume this number shifts.** Immediately before the pre-push rebase, re-run `alembic heads` against rebased `main`; if a sibling took the number, renumber filename + `revision` + `down_revision` in one `fix(bell):` commit. A reserved-but-wrong number breaks alembic outright and reds every db test (`.memory/parallel-alembic-numbering`).

**Pathspec**: git tracks `backend/`/`frontend/` **lowercase**. `git add Backend/…` silently skips modified tracked files — lowercase every pathspec, verify with `git show --stat` (`.memory/git-add-uppercase-pathspec-trap`).

**Frontend build check**: `pnpm -r build` before staging any `.ts`/`.tsx`.

**After any merge-conflict resolution**: parse every touched test file's collection count — a broken file reads as one `Tests no tests` line, not N failures (`.memory/silently-unexecuted-test-files`). `he.ts`/`ar.ts` and `test_migrations.py` are the likely conflict sites.

## 6. Risks this plan adds to the spec's list

- **R-A — C2 puts a statement on the emergency channel's read.** If `unread_count` is anything but an index-only scan on the partial index, the SOS tick pays for it on 18 sections. The tripwire is A2's db test pinning the predicate against `pg_indexes.indexdef`; if it ever needs a second index, that is a new migration and a new review, not a widened one.
- **R-B — D1 edits a gate-passed shared component.** F-B4's zero-line-diff assertion is the tripwire and is not a nice-to-have: if `ConsoleShell`'s existing suite needs a single edit, the slot was built wrong.
- **R-C — the four producer inserts sit inside the product's hottest transactions.** B2 proves the rollback but not the latency. Keep each site to one `await` and one statement; if any site needs a read to resolve the recipient, stop — the recipient is already a local at all four (§1).
- **R-D — E2 is one component carrying eight states and the whole a11y contract.** Build the states in §4's order (D/U before L/P/E/C before F1/F2); a bell that renders before it fails correctly will pass vitest and fail axe.
- **R-E — three features touch manage `he.ts`/`ar.ts` in parallel.** Expect an i18n conflict at rebase; re-run `i18n.test.ts`'s collection count after resolving.
