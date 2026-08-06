# Plan: Feature 22 — Waitlist join + entries model (Epic E5)

**Spec**: `.planning/specs/waitlist-join.md` (2026-08-06, Gate 1 standing-approved, D1–D7)
**Design**: `.planning/design/screens/waitlist-join/design.md` (Design Gate accepted 2026-08-06 — P1/P2/P3 taken, F-W1/W2/W3 owed)
**Plan written**: 2026-08-06. **Observed alembic head: `0025` (`0025_walk_in_bookings.py`) — the migration is `0026_waitlist_entries.py`**, `revision = "0026"`, `down_revision = "0025"`. Re-resolve `alembic heads` on the rebased branch immediately before push (§5).
**Depends on**: F11 (OTP endpoints), F12 (slot window), F13 (booking create shape), F14 (BookPage slot step), F20 (privacy surfaces) — all merged.
**Worktree**: `.worktrees/waitlist-join`, branched from `origin/main`.

---

## 0. How to read this plan

Every task is one TDD cycle: the named failing test first, then the code that makes it pass. Backend before frontend (the UI needs settled shapes). The spec's D1–D7 are binding and not restated — this plan maps them to files, tests, and commits. Every path below was verified against the tree on 2026-08-06.

## 1. Verified facts the tasks lean on

| Claim | Verified at |
|---|---|
| Head migration is 0025; template for a new tenant table is `0018_queue_tickets.py` | `Backend/migrations/versions/` |
| `enable_tenant_rls(table_name)` helper | `Backend/app/db/rls.py:4` |
| `consume_verification` | `Backend/app/notifications/service.py:377` |
| `normalize_israeli_mobile` | `Backend/app/notifications/validation.py:31` |
| `today_jerusalem` lives in `app/storefront/validation.py` (queue imports it from there) | `Backend/app/queue/service.py:50` |
| OTP limiter instances built in `create_app()` — the pattern for the two new join limiters | `Backend/app/main.py:801-826` |
| Module to mirror: `app/queue/` (`router.py`, `manage_router.py`, `schemas.py`, `service.py`, `validation.py`) | `Backend/app/queue/` |
| Walker id-kind map + QUEUE_TICKET population precedent | `Backend/tests/test_cross_tenant_walker.py:161-186` |
| `MANAGE_API` alternation, 16 segments ending `…|slots|staff|terms` | `Frontend/apps/manage/vite.config.ts:18-19` |
| e2e mirror set `API_FAMILIES` + F58's `waitlistEntry()`/`waitlist()` fixtures (names taken) | `Frontend/e2e/fixtures/manage.ts:60, 256-299` |
| Storefront `he.ts` has NO `waitlist.*` block — free to take | grep, `Frontend/apps/storefront/src/i18n/he.ts` |
| `TypePicker` exists; `WaitlistJoin.tsx` does not | `Frontend/apps/storefront/src/components/booking/` |
| Manage `WaitlistPanel.tsx` (F58) exists — the collision is real; `WaitlistSection.tsx` is free | `Frontend/apps/manage/src/components/` |
| Privacy surfaces: `export_subject`/`erase_subject` in `privacy/service.py`, registry in `privacy/retention.py` | `Backend/app/privacy/` |
| Per-feature e2e spec files are the pattern (`walk-in.spec.ts`) | `Frontend/e2e/` |

## 2. Migration `0026_waitlist_entries.py`

Raw SQL, `0018`'s template verbatim: `_STANDARD` columns, the DDL in spec D1 (table + named status CHECK + `idx_waitlist_entries_active_unique` partial unique + `idx_waitlist_entries_tenant_day`), `_updated_at_trigger`, `GRANT SELECT, INSERT, UPDATE, DELETE … TO app_user`, `enable_tenant_rls("waitlist_entries")`. The two index rationales from D1 go in as comments **at the index** (0018's demand). Downgrade: `DROP TABLE IF EXISTS waitlist_entries` — touches nothing else.

ORM: `Backend/app/models/waitlist_entry.py` (StandardColumns + `day: Mapped[date]`, `appointment_type_id`, `phone`, `status` with `server_default=text("'waiting'")`).

## 3. Ordered task list

### Phase A — schema, model, privacy ripples (ONE commit — a phone-bearing table absent from export/erase/retention is silently incomplete §13/§14 answers; spec D4)

| # | Task | Test first | Files (C=create, M=modify) |
|---|---|---|---|
| A1 | Migration 0026 per §2. | `test_migrations.py::test_migration_0026_creates_waitlist_entries` (**db**) — table + named CHECK + both indexes pinned via `pg_get_constraintdef`/`pg_indexes.indexdef`; `::test_migration_0026_round_trips`; `test_every_tenant_id_table_has_forced_rls` and `test_exactly_one_migration_head` stay green **unedited** (the RLS assertion) | C `Backend/migrations/versions/0026_waitlist_entries.py`, M `Backend/tests/test_migrations.py` |
| A2 | Model + repository: `insert`, `by_active_tuple(tenant_id, phone, day, type_id)` (the IntegrityError re-read), `list_active(day | None)` ordered `(day, created_at)`, `cancel(entry_id)` guarded UPDATE `WHERE status='waiting'`, `by_id`. | `test_waitlist_db.py` (**db**, new) — insert round-trip; active-unique raises on exact tuple; **per-tenant**: same (phone, day, type) under two tenants both insert; FIFO order; cancel guard returns 0 rows on a cancelled row | C `Backend/app/models/waitlist_entry.py`, C `Backend/app/db/repositories/waitlist_entries.py`, C `Backend/tests/test_waitlist_db.py` |
| A3 | Privacy ripples, all three: export block (mirror of the `queue_tickets` block, `privacy/service.py:217-231`) + `ExportedWaitlistEntry` schema; erase scrubs `phone` to `erased:{id}` (mirror `:497-518`); retention PURGE policy on `day < today_jerusalem - waitlist_retention_days` (setting, default 30, in `core/config.py`). | `test_privacy_subject_requests_db.py` (**db**) — export answers a subject's entries; erase scrubs and the row survives; `test_retention_db.py`'s predicate-falsification loop covers the new policy **by construction** (register it and the loop tests it — verify the loop picked it up, count of policies asserted) | M `Backend/app/privacy/service.py`, M `Backend/app/privacy/schemas.py`, M `Backend/app/privacy/retention.py`, M `Backend/app/core/config.py`, M both test files |

### Phase B — storefront join (commit 2)

| # | Task | Test first | Files |
|---|---|---|---|
| B1 | Day-window validation: `today_jerusalem(clock) <= day <= today + SLOT_WINDOW_MAX_DAYS`; phone via `normalize_israeli_mobile`. Pure function in `validation.py`. | `test_waitlist_validation.py` (**non-db**, new) — frozen clock: today ok, horizon edge ok, past/beyond → error; schema shapes | C `Backend/app/waitlist/__init__.py`, C `Backend/app/waitlist/validation.py`, C `Backend/app/waitlist/schemas.py`, C `Backend/tests/test_waitlist_validation.py` |
| B2 | `WaitlistService.join` — one `tenant_session`, F13's order (spec D2 steps 1-5): validate → check both join budgets, **spend after proof** → `consume_verification` → `AppointmentTypesRepository.by_id` (None → `DomainNotFoundError`) → INSERT; `IntegrityError` → re-read via `by_active_tuple`, same 201 body. Zero new error codes. | `test_waitlist_service.py` (**db**, new) — happy join; **duplicate idempotent** (one row, token burned); concurrent-join race → one row, two identical 201 bodies (F13's double-book standard); unknown/archived type 404; day 400; unverified → `PHONE_NOT_VERIFIED`; join limiters trip **without touching the booking budget** (assert `BookingService`'s limiter unspent — `.memory/limiter-max-is-per-instance`) | C `Backend/app/waitlist/service.py`, C `Backend/tests/test_waitlist_service.py` |
| B3 | `POST /storefront/waitlist` (201) router with `_no_store`, mounted like `notifications/router.py`; two new `FixedWindowRateLimiter` instances in `create_app()` — `waitlist_join_max_per_phone_window`/`_per_tenant_window` (+ `_seconds`), F13's config-name pattern. **Own instances, never a key on the booking limiter.** | `test_waitlist_api.py` (fast, new) — TestClient: 201/400/404/PHONE_NOT_VERIFIED/429; no new members in any error-code set-equality assertion | C `Backend/app/waitlist/router.py`, M `Backend/app/main.py`, M `Backend/app/core/config.py`, C `Backend/tests/test_waitlist_api.py` |

### Phase C — manage endpoints + walkers (commit 3)

| # | Task | Test first | Files |
|---|---|---|---|
| C1 | `GET /manage/waitlist?day=` + `POST /manage/waitlist/{entry_id}/cancel`, router-level `require_role(OWNER, SHIFT_MANAGER)` + `_no_store` (`customers/router.py` shape). List: default all active `day >= today`, `(day, created_at)`; `customer_name` decoration via one `(tenant, phone)` customers lookup; `appointment_type_name` via types repo. Cancel: guarded UPDATE, idempotent double-tap returns row as-is, foreign/unknown id → 404. Audit: `AuditAction.WAITLIST_ENTRY_CANCELLED = "waitlist_entry_cancelled"` (TEXT, no migration), `details = {entry_id, day, appointment_type_id}` — **no phone**. | `test_waitlist_service.py` extended (**db**) — list FIFO; day filter; decoration null and non-null; cancel happy + idempotent + foreign-id 404; audit row `details` **key-set equality** (catches a later phone). `test_waitlist_api.py` — shift_manager 200, route absent from `OWNER_ONLY`; `test_staff_role_gating.py` **unedited** (walker covers both routes) | C `Backend/app/waitlist/manage_router.py`, M `Backend/app/waitlist/service.py`, M `Backend/app/waitlist/schemas.py`, M `Backend/app/models/constants.py` |
| C2 | Cross-tenant walker: **populate, don't exempt** — add `"entry_id": Kind.WAITLIST_ENTRY` to the id-kind map (`:161-172`) and a factory that runs the storefront join under `otp_dev_code` (the walker already patches settings; QUEUE_TICKET at `:184` is the precedent). Fallback if the anonymous-call plumbing fights back: exemption with a written reason — but try population first. | `test_cross_tenant_walker.py::test_the_walk_and_the_exemptions_are_the_whole_route_table` reds on the new routes until this lands — that red IS the failing test first | M `Backend/tests/test_cross_tenant_walker.py` |
| C3 | Registration: `MANAGE_API` alternation gains `waitlist` (alphabetical, after `terms`); e2e `API_FAMILIES` set gains `"waitlist"`. | `test_spa_serving.py` reds until the vite line matches — run it on CI awareness: it derives the set from the live route table, so it reds **at C1** and greens here | M `Frontend/apps/manage/vite.config.ts`, M `Frontend/e2e/fixtures/manage.ts` |

### Phase D — storefront UI (commit 4)

| # | Task | Test first | Files |
|---|---|---|---|
| D1 | `WaitlistJoin.tsx` per design §2-3: CTA renders under `SlotPicker` empty state only when `times.length === 0 && flow.typeId !== null`; inline reveal (no Modal, no route change); OTP block copied from the verify step (one code field, `dir="ltr"`, 60s cooldown, one send/resend label); privacy-notice line (`substituteBoutique(boutique.privacy_notice_text, name)` — the details step's call); on 201 confirmation line `role="status"` `tabindex="-1"` focused; errors via shipped `errorKey` map; **F-W3: date/type change collapses the reveal AND clears `codeSent`/token state**. | `WaitlistJoin.test.tsx` (new) — CTA absent when slots exist / no type picked; present on empty day; notice before send; cooldown disables resend; join posts **exactly four keys** (`Object.keys` equality); confirmation replaces form; collapse clears token state; error keys map | C `Frontend/apps/storefront/src/components/booking/WaitlistJoin.tsx`, M `Frontend/apps/storefront/src/routes/BookPage.tsx`, C `Frontend/apps/storefront/src/__tests__/WaitlistJoin.test.tsx`, M `Frontend/apps/storefront/src/api.ts` (join call + types) |
| D2 | i18n: new `waitlist.*` block in storefront `he.ts` — the design §8 seven keys (`cta, send, sendWait, sending, join, joining, confirmed`), P1 rules OTP-mechanics rows reused from `booking.*`; `ar.ts` mirrors with Hebrew values (pre-decided #47). No exclamation marks. | storefront i18n test extends its floor for the new prefix | M `Frontend/apps/storefront/src/i18n/he.ts`, M `…/ar.ts`, M storefront i18n test |

### Phase E — manage UI (commit 5)

| # | Task | Test first | Files |
|---|---|---|---|
| E1 | `WaitlistSection.tsx` per design §4: NAV row `{ key: "waitlist", labelKey: "nav.bookingWaitlist", roles: ["owner", "shift_manager"] }`; **`SectionKey` is guide-typed — the one-step guide entry ships in the same commit or the build breaks**; DateField filter default today; table (day, type, `customer_name ?? phone` via `isolateLtr`, status Badge, joined-at, cancel); cancel = in-place secondary→danger swap (P3), Escape/click-elsewhere reverts; refetch on success; **no `usePoll`**; **F-W1: verify `Button size="sm"` box ≥44px, else `min-h-[44px]`**. States: skeleton/loaded/empty/emptyFiltered/error per design. | `WaitlistSection.test.tsx` (new) — rows render FIFO as given; cancel swap + fires + refetches; Escape reverts; empty + filtered-empty states; error + retry | C `Frontend/apps/manage/src/components/WaitlistSection.tsx`, M `Frontend/apps/manage/src/App.tsx`, M `Frontend/apps/manage/src/lib/guide.ts`, C `Frontend/apps/manage/src/__tests__/WaitlistSection.test.tsx` |
| E2 | Types + API in `api.ts`: `BookingWaitlistRow`, `BookingWaitlistList`, `getBookingWaitlist(day?)`, `cancelBookingWaitlistEntry(id)` — the `bookingWaitlist` spelling is **load-bearing** (F58 owns `waitlist` in this app, F-W2). i18n: `nav.bookingWaitlist` + `bookingWaitlist.*` (design §9, ~18 keys) in `he.ts`, `ar.ts` mirror; **`HE_F22` block spread into `HE`** in `i18n.test.ts` with a `toBeGreaterThanOrEqual(18)` floor — an unspread block is silently green (the file's own warning). | `i18n.test.ts` — the spread + floor; ar-presence guard binds via the new prefixes | M `Frontend/apps/manage/src/api.ts`, M `Frontend/apps/manage/src/i18n/he.ts`, M `…/ar.ts`, M `Frontend/apps/manage/src/__tests__/i18n.test.ts` |

### Phase F — e2e (commit 6)

| # | Task | Test first | Files |
|---|---|---|---|
| F1 | Fixtures: `bookingWaitlistRow()` factory (NOT `waitlistEntry()` — taken by F58 at `:256`) + stub handlers for `GET /manage/waitlist` and `POST /manage/waitlist/{id}/cancel` in the manage harness (`API_FAMILIES` already gained `waitlist` at C3). | the specs below consume them | M `Frontend/e2e/fixtures/manage.ts` |
| F2 | `waitlist.spec.ts` (per-feature file, `walk-in.spec.ts` pattern). Storefront: stub empty day + OTP routes, walk CTA → phone → code → confirmation; **focus lands on phone input at open**; axe zero-violation on the open reveal and the confirmed state (IS 5568). Manage: open section, cancel an entry (two-click swap), row disappears; axe clean loaded + empty + confirm-swap open. | this IS the test | C `Frontend/e2e/waitlist.spec.ts` |

## 4. Build environment — RECORD, these are facts not suggestions

- **No Docker locally.** Tests marked `db` or `s3` run **on CI only**. Do not chase local db-test failures.
- **The local fast lane (`-m 'not db'`) points at a CLOSED Postgres port by design (F21).** Any test that dials a real DB without the `db` marker **fails locally — that is correct behavior**, not a bug to fix. New db-touching tests MUST carry the `db` marker.
- **The worktree has no `Backend/.env`.** Config-default tests behave differently than in the main checkout (`.memory/local-env-breaks-config-tests` — there the failure is REAL if it appears).
- **Local gates, all must pass before push**: `make lint` · backend non-db tests (`make test`) · `make fe-test` · `make fe-build` · `make e2e`.
- Write db-marked tests carefully against the spec's test plan; their first run is CI (`.memory/boutique-ci-first-run-surprises`).

## 5. Build discipline

**Commit boundaries** (conventional, scoped):
1. `feat(waitlist): entries table, model, repository, privacy ripples (0026)` — A1+A2+A3 one commit (D4's same-PR-same-commit discipline: migration and privacy surfaces are inseparable).
2. `feat(waitlist): storefront join endpoint with own rate limiters` — B1-B3.
3. `feat(waitlist): manage list and cancel, walker registration, proxy segment` — C1-C3.
4. `feat(waitlist): storefront join reveal on the slot step` — D1-D2.
5. `feat(waitlist): manage waitlist section` — E1-E2.
6. `test(e2e): waitlist join and manage specs with axe` — F1-F2.

**Migration renumber protocol**: built as `0026`. Immediately before the pre-push rebase, re-run `alembic heads` against rebased main; if a sibling took `0026`, renumber (filename + `revision` + `down_revision`) in one `fix(waitlist):` commit. A reserved-but-wrong number breaks alembic outright and reds every db test (`.memory/parallel-alembic-numbering`).

**Pathspec**: git tracks `backend/`/`frontend/` **lowercase**. `git add Backend/…` silently skips modified tracked files — lowercase every pathspec, verify with `git show --stat` (`.memory/git-add-uppercase-pathspec-trap`).

**Frontend build check**: `pnpm build` before staging any `.ts`/`.tsx`.

**Focus/dialog assertions belong to Playwright, not vitest** — jsdom has no `<dialog>` and setup.ts stubs it; only state assertions are valid in vitest (`.memory/jsdom-has-no-dialog`). The reveal is not a dialog, but the focus-movement assertions (§F2) still measure real browsers only.

**After any merge-conflict resolution**: parse every touched test file's collection count — a broken file reads as one `Tests no tests` line (`.memory/silently-unexecuted-test-files`).

## 6. Risks this plan adds to the spec's list

- **R-A**: C2's walker population depends on the storefront join being callable inside the walker's harness (anonymous route + `otp_dev_code`). If the harness's tenant plumbing resists, take the exemption-with-reason path the whole-table test forces — but the reason must say "F23 will populate it via offers", not "too hard".
- **R-B**: the retention loop covering the new policy "by construction" is only true if the policy is **registered** in `retention.py`'s list — an unregistered policy is silently green, the same failure shape as an unspread i18n block. A3's test asserts the registry count.
- **R-C**: `test_spa_serving.py` reds between C1 and C3 if run mid-phase — expected, sequenced inside one commit's TDD cycle, never pushed red.
