# Plan: Feature 25 — Web platform console (Epic E5)

**Spec**: `.planning/specs/platform-console.md` (2026-08-06, Gate 1 standing-approved, D1–D8 + conflicts 1–5 binding)
**Design**: `.planning/design/screens/platform-console/design.md` (§Screens 1–5, copy deck §1–§6, F-W1 ruling: every Button `md`)
**Plan written**: 2026-08-06. **Observed alembic head on main: `0025` (`0025_walk_in_bookings.py`). F22 holds `0026` live in `.worktrees/waitlist-join`; F24 (client-portal) is queued next and takes the head after that — TWO parallel numbers may land before this branch rebases.** The migration is numbered **head+1 as observed in the F25 worktree at build time** and re-resolved at rebase per §5.
**Depends on**: F6 (`ProvisioningService` + CLI), F5 (staff auth patterns), F4 (reserved slugs / resolver) — all merged. **Feeds**: F26.
**Worktree**: `.worktrees/platform-console`, branched from `origin/main`.

---

## 0. How to read this plan

Every task is one TDD cycle: the named failing test first, then the code that makes it pass. Order: parity pin on the service layer first (pre-decided #20 — the CLI stays green through everything until its own deletion task), then operator schema + CLI bootstrap, then the host fence, then operator auth (treated adversarially — the spec's Q49 note), then the console endpoints and the CLI parity deletion, then the third workspace app, then e2e. The spec's D1–D8 and the design doc are binding and not restated. Every path below was verified against the tree on 2026-08-06.

## 1. Verified facts the tasks lean on

| Claim | Verified at |
|---|---|
| `ProvisioningService(session_factory)` with `provision/suspend/list_tenants/reset_owner_password` (+`backfill_booking_links:113`, `run_retention:146`); `CommandResult:25`, `TenantSummary:32` | `Backend/app/platform/service.py:39,50,94,202,237` |
| `PlatformAuditLogRepository.record` (client-side id/created_at, no RETURNING) | `Backend/app/platform/repository.py:11` |
| `PlatformAuditAction` is a TEXT-valued enum in constants — new members need no migration | `Backend/app/models/constants.py:704-732` |
| `app/cli.py`: `ProvisioningLike:30`, subparsers `:53-89`, password via `getpass:171`, `ensure_safe_database_role():184` | `Backend/app/cli.py` |
| `RESERVED_SLUGS` (has `admin`) / `extract_slug` | `Backend/app/tenancy/slugs.py:5,29` |
| `EXEMPT_PATHS:28`, `TENANT_NOT_FOUND_BODY:32`, `TenantResolutionMiddleware:57` | `Backend/app/tenancy/middleware.py` |
| CSRF `PROTECTED_PREFIX = "/manage"`, checked via `path.startswith(...)` — a tuple drops in | `Backend/app/csrf.py:16,48` |
| `_RESERVED_SEGMENTS = {manage, storefront}`:469, `_register_spas`:526 (manage triple = assets mount, public files, exact-path index), staff `login_rate_limiter` instance:752 | `Backend/app/main.py` |
| `SESSION_COOKIE = "boutique_session"` (staff — operator cookie must be a new name) | `Backend/app/auth/cookies.py:3` |
| `get_current_staff` shape to mirror; `verify_password_dummy`; `generate_session_token`/`hash_token` | `Backend/app/auth/dependencies.py:28`, `passwords.py:25`, `tokens.py:7,11` |
| Settings: `base_domain:20`, staff `session_ttl_seconds:24`, `trust_forwarded_for:37` | `Backend/app/core/config.py` |
| `test_provisioning.py` runs RLS-real as the app role and asserts audit rows via an owner-role connection — the technique to reuse | `Backend/tests/test_provisioning.py:31-58` |
| `test_cli.py` drives the parser with a fake `ProvisioningLike` — the parity suites that must stay green unedited | `Backend/tests/test_cli.py:44-238` |
| pnpm workspace globs `apps/*` — a third app is a member with zero workspace-file edits; manage lint script `oxlint -c ../../.oxlintrc.json src` | `Frontend/pnpm-workspace.yaml`, `Frontend/apps/manage/package.json:9` |
| manage `base: "/manage/"` — the vite config to copy | `Frontend/apps/manage/vite.config.ts:28` |
| e2e webServers: storefront 4173 / manage 4174; `fixtures/` holds `manage.ts` only; Makefile `e2e` runs `pnpm -r build` first | `Frontend/e2e/playwright.config.ts:14-22`, `Makefile:61-62` |
| **CI copy step hardcodes the two dists + an index.html assert loop — spec D8's "zero workflow edits" is FALSE here; one edit required** | `.github/workflows/ci.yml:173-183` |
| No `platform_operator|operator_session` anywhere web-facing (spec grep re-confirmed) | spec §exists |

## 2. Migration `NNNN_platform_operators.py` (NNNN = head+1 at build time)

Raw SQL, house style: `platform_operators` (standard id/created_at/updated_at-trigger/deleted_at block + `email TEXT NOT NULL`, `password_hash TEXT NOT NULL`, `display_name TEXT NOT NULL`; partial unique index on `lower(email) WHERE deleted_at IS NULL`) and `platform_sessions` (standard block + `operator_id UUID NOT NULL` no-FK, `token_hash TEXT NOT NULL`, `expires_at TIMESTAMPTZ NOT NULL`; partial indexes on token_hash and operator_id `WHERE deleted_at IS NULL`) — spec D7 verbatim. **No `tenant_id` on either table** (outside the forced-RLS scan by construction), no `enable_tenant_rls`, 0002's default privileges give `app_user` the CRUD these tables need. `platform_audit_log` untouched. Downgrade drops both tables, nothing else.

## 3. Ordered task list

### Phase A — parity pin, schema, operator model (commit 1)

| # | Task | Test first | Files (C=create, M=modify) |
|---|---|---|---|
| A1 | **Pre-decided #20's refactor, honestly sized: the command layer already IS a service layer** (`ProvisioningService` takes a session factory, returns result dataclasses, owns its failure audits). This task is the parity pin, not a rewrite: read the class for any CLI coupling (there should be none — `ensure_safe_database_role` lives in `cli.py:184`, not the service); extract only if found. The router (D1) lands against the unchanged class. | `test_cli.py` and `test_provisioning.py` stay green **unedited** — that IS the contract; expected diff ≈ zero, and a zero diff is a pass, not a skipped task | M (only if coupling found) `Backend/app/platform/service.py` |
| A2 | Migration per §2. | `test_migrations.py::test_migration_NNNN_creates_platform_operator_tables` (**db**) — both tables + the three partial indexes pinned via `pg_indexes.indexdef`; `::test_migration_NNNN_round_trips`; `test_every_tenant_id_table_has_forced_rls` and `test_exactly_one_migration_head` stay green **unedited** | C `Backend/migrations/versions/NNNN_platform_operators.py`, M `Backend/tests/test_migrations.py` |
| A3 | `PlatformOperator` + `PlatformSession` models; repositories: operators `insert / by_active_email(lower) / by_id / soft_delete / count_active`; sessions `insert / live_by_token_hash (deleted_at IS NULL AND expires_at > now()) / revoke / revoke_all_for_operator`. New `PlatformAuditAction` members `OPERATOR_CREATED / OPERATOR_DEACTIVATED / OPERATOR_LOGIN / OPERATOR_LOGIN_FAILED` (constants only — no migration). | `test_platform_operators_db.py` (**db**, new) — round-trips; email lookup is case-insensitive and misses soft-deleted; session lookup misses expired and revoked; revoke-all hits only that operator | C `Backend/app/models/platform_operator.py`, C `Backend/app/models/platform_session.py`, C `Backend/app/db/repositories/platform_operators.py`, C `Backend/app/db/repositories/platform_sessions.py`, M `Backend/app/models/constants.py`, C `Backend/tests/test_platform_operators_db.py` |

### Phase B — CLI bootstrap (commit 2)

| # | Task | Test first | Files |
|---|---|---|---|
| B1 | Service methods on `ProvisioningService` (one service layer, no fork): `create_operator(email, display_name, operator)` — argon2 hash, duplicate-active-email → `CommandResult(ok=False)`, audit `OPERATOR_CREATED`; `deactivate_operator(email, operator)` — soft delete + `revoke_all_for_operator` + audit `OPERATOR_DEACTIVATED`, **refuses the last active operator** (failure audits commit, the F5 lesson throughout). CLI: `create-operator` / `deactivate-operator` subcommands — password via stdin/getpass (never argv, `cli.py:171` pattern), `--operator required=True` (the retention precedent at `test_cli.py:214`). | `test_cli.py` (fast) — new subcommands map through a fake service, password read from stdin, `--operator` required, failure = non-zero exit; `test_platform_operators_db.py` (**db**) — duplicate active email refused with its failure audit committed; last-operator deactivation refused; deactivation revokes live sessions | M `Backend/app/platform/service.py`, M `Backend/app/cli.py`, M `Backend/tests/test_cli.py`, M `Backend/tests/test_platform_operators_db.py` |

### Phase C — host fence, then operator auth (commits 3–4)

| # | Task | Test first | Files |
|---|---|---|---|
| C1 | Spec D1: setting `platform_host_label: str = "admin"` + boot assert `in RESERVED_SLUGS`; middleware label branch — console host: only `/platform`/`/platform/*` + exact `EXEMPT_PATHS` proceed with `request.state.platform_host = True`, everything else the house `TENANT_NOT_FOUND` 404; tenant hosts: `/platform*` → same 404. `"platform"` joins `_RESERVED_SEGMENTS` (`main.py:469`). **Never add `/platform` to `EXEMPT_PATHS`** (spec trap — exemption opens the routes on every host). | `test_middleware.py` (fast) — the fence matrix: console host × {`/platform`, `/platform/x`, `/manage`, `/`, `/storefront/x`, `/health`} and tenant host × `/platform*`, exact expected bodies both directions; `test_slugs.py` — label branch + boot assert | M `Backend/app/core/config.py`, M `Backend/app/tenancy/middleware.py`, M `Backend/app/main.py`, M `Backend/tests/test_middleware.py`, M `Backend/tests/test_slugs.py` |
| C2 | Spec D3+D4, **adversarial (Q49): brute force, session theft, host confusion are the test plan, not the appendix.** Cookie constant `PLATFORM_SESSION_COOKIE = "boutique_platform_session"` beside the staff one; settings `platform_session_ttl_seconds` (4h), `platform_login_max_attempts` (5), `platform_login_window_seconds` (900); `get_current_operator` (requires `request.state.platform_host` → cookie → `hash_token` → live session → **re-read operator row**, deactivation bites immediately → `OperatorContext`; failure = existing `NotAuthenticatedError`); `POST /platform/auth/login` mirroring `auth/router.py::login` — NEW `FixedWindowRateLimiter` instance `app.state.platform_login_rate_limiter` (**own instance, never a key on an existing budget** — the per-instance rule `main.py` repeats), keys `e:{email}` + inert `ip:{ip}` arm, failures-only, success resets the email key; `verify_password_dummy` on unknown email, generic 401 either way; audits `OPERATOR_LOGIN`/`OPERATOR_LOGIN_FAILED` committed with the transaction; `/logout` (revoke + clear), `/me`. CSRF: `PROTECTED_PREFIX` becomes `("/manage", "/platform")` — `startswith` takes a tuple, `csrf.py:48` unchanged otherwise. | `test_platform_auth_api.py` (fast, new) — dependency matrix: no cookie / garbage / expired / deactivated / **valid cookie on a non-platform host** → 401; limiter keying + success-reset with a fake clock; CSRF applies to mutating `/platform`; **cookie attrs asserted: HttpOnly, Secure(prod), SameSite=Lax, path=/, host-only (no Domain)**. `test_platform_auth_db.py` (**db**, new) — create-operator → HTTP login → me → logout lifecycle; failed login writes `OPERATOR_LOGIN_FAILED` (owner-role SELECT, `test_provisioning.py:31` technique) and the 401 stays generic; 429 after budget without touching any other limiter (`.memory/limiter-max-is-per-instance`); expiry honoured; **a deactivated operator's still-live session is refused**; staff `boutique_session` cookie is worthless on `/platform/*` | C `Backend/app/platform/auth.py` (deps+cookie), C `Backend/app/platform/auth_router.py`, M `Backend/app/auth/cookies.py`, M `Backend/app/core/config.py`, M `Backend/app/csrf.py`, M `Backend/app/main.py`, C `Backend/tests/test_platform_auth_api.py`, C `Backend/tests/test_platform_auth_db.py` |

### Phase D — console endpoints, walkers, parity deletion (commits 5–6)

| # | Task | Test first | Files |
|---|---|---|---|
| D1 | Spec D5: `app/platform/router.py` (`APIRouter(prefix="/platform")`, every handler `Depends(get_current_operator)`) — `POST /tenants/provision`, `POST /tenants/suspend`, `GET /tenants`, `POST /tenants/reset-owner-password`, delegating to the **unchanged** service with `operator=ctx.email`. `CommandResult(ok=False)` maps message→house error body code (`slug_taken` 409, `invalid_or_reserved_slug`/`empty_password` 400, `tenant_not_found`/`owner_not_found` 404); **the service, not the router, owns the failure audits — they keep committing**. All new audit writes go through `record`, never `session.add` (spec trap: the no-RETURNING property is load-bearing). | `test_platform_console_db.py` (**db**, new) — the whole lifecycle **as `boutique_app`**: create-operator → HTTP login → provision → **the new owner logs in via `AuthService`** (F6's end-to-end, now over HTTP) → suspend → reset-password → owner logs in with the new password; each action's `platform_audit_log` row asserted via owner-role connection with `operator` = the authenticated email; `GET /tenants` writes `TENANTS_LISTED` (conflict 4); reserved-slug + duplicate-slug refusals return their codes AND their failure audits commit | C `Backend/app/platform/router.py`, C `Backend/app/platform/schemas.py`, M `Backend/app/main.py`, C `Backend/tests/test_platform_console_db.py` |
| D2 | Walker registration — the registration IS the task (spec test plan): cross-tenant walker learns the `/platform/*` routes so `walked ∪ exempt == route table` holds both ways; audit-coverage walker follows the delegation to `_audit.record` and its **module comment claiming `platform_audit_log` has no HTTP route is updated** (conflict 3); staff-role-gating asserts the staff cookie fails on `/platform/*`; one console response asserts the security headers ride free. | `test_cross_tenant_walker.py` reds on the unregistered routes until this lands — that red is the failing test first; `test_audit_coverage.py`, `test_staff_role_gating.py` | M `Backend/tests/test_cross_tenant_walker.py`, M `Backend/tests/test_audit_coverage.py`, M `Backend/tests/test_staff_role_gating.py` |
| D3 | **Parity, then deletion (conflict 1)**: the four lifecycle subcommands + their `ProvisioningLike` entries leave `app/cli.py`; the CLI file survives (backfill, retention, create-operator, deactivate-operator). Sweep the pointers: `docs/real-world-qa.md` §2/§3, `scripts/seed_demo.py` printed instructions, F21 citation rows referencing "no HTTP reset route" (conflict 2), `.brain` references — a doc still saying `app.cli provision` sends the next QA run to a dead command (spec trap). | `test_cli.py` (fast) — parser no longer knows `provision/suspend/list/reset-password` (exit 2), surviving commands still green; grep-sweep asserted by review, not test | M `Backend/app/cli.py`, M `Backend/tests/test_cli.py`, M `Backend/docs/real-world-qa.md`, M `Backend/scripts/seed_demo.py`, M `Backend/tests/citations.py` (if the F21 rows live there) |

### Phase E — the third workspace app (commits 7–8)

| # | Task | Test first | Files |
|---|---|---|---|
| E1 | **Scaffolding, every file enumerated** (workspace glob `apps/*` makes it a member automatically; Makefile needs zero edits — `pnpm -r` covers lint/typecheck/build/e2e-build): `package.json` (name `platform`, manage's script block incl. `"lint": "oxlint -c ../../.oxlintrc.json src"`), `vite.config.ts` (**`base: "/platform/"`**, dev proxy `/platform` → :8000, **`--host 127.0.0.1`** — `.memory/vite-dev-binds-ipv6-only`), `vitest.config.ts`, `tsconfig.json`, `index.html` (`lang="he" dir="rtl"`), `src/main.tsx`, `src/index.css`, `src/vite-env.d.ts` — all copied from manage. Backend serving: `_register_spas` gains the platform triple mirroring manage (`/platform/assets` mount, public files, exact-path index at `/platform`; missing bundle = API-only boot unchanged). **CI: `.github/workflows/ci.yml:173-183` copy step gains `cp -R frontend/apps/platform/dist backend/app/static/platform` + the index.html assert — spec D8's "zero workflow edits" was wrong about this one step; recorded here.** | `test_spa_serving.py` — `/platform` shell + assets served when present, catch-all declines `/platform`, API-only boot without the bundle (all three pinned like manage) | C `Frontend/apps/platform/{package.json, vite.config.ts, vitest.config.ts, tsconfig.json, index.html}`, C `Frontend/apps/platform/src/{main.tsx, index.css, vite-env.d.ts}`, M `Backend/app/main.py`, M `Backend/tests/test_spa_serving.py`, M `.github/workflows/ci.yml` |
| E2 | Login + shell: `api.ts` (thin fetch client: `me/login/logout/listTenants/provision/suspend/resetOwnerPassword`, house error-body parsing keyed on `code`); `App.tsx` bootstraps `GET /platform/auth/me` — 401 → `LoginPanel` (LoginForm shape per design §Screen 1: generic failed sentence, tooMany, sessionExpired status line), 200 → console. i18n `src/i18n/{he.ts, ar.ts, index.ts}` seeded from the design copy deck §1 — `ar` mirrors `he` untranslated (#47), **zero exclamation marks (#5)**, the mechanical i18n guard test copied from manage. | `App.test.tsx` (new) — 401 renders login, 200 renders console, mid-session 401 flips back with the sessionExpired status; `LoginPanel.test.tsx` — submit → me refetch, 401/429 mapped sentences; `i18n.test.ts` — no `!`, ar key parity | C `Frontend/apps/platform/src/{App.tsx, api.ts}`, C `…/src/components/LoginPanel.tsx`, C `…/src/i18n/{he.ts, ar.ts, index.ts}`, C `…/src/__tests__/{App.test.tsx, LoginPanel.test.tsx, i18n.test.ts}` |
| E3 | Console screen per design §Screens 2–4: semantic `<table>` in `overflow-x-auto` (caption sr-only, `th scope="col"`, worded Badges, suspended rows lose the suspend action), client-side filter, **fetch once per mount + patch rows locally** (every list GET writes an audit row — no refetch loops); provision form (client slug validation mirroring `tenancy/slugs.py` regex + 12 reserved slugs, live URL help, `autoComplete="new-password"`, success `role="status"` with the URL, password leaves memory); suspend `Modal` (**danger on the modal confirm ONLY** — the design's declared table-density deviation; do not cite it as house pattern) and reset-password `Modal` (`new-password`, values intact on failure, done-line never repeats the password). Every Button `md` (F-W1). Error codes → deck §6 sentences; unlisted codes fall through. Full copy deck §2–§6 into `he.ts`/`ar.ts`. | `Console.test.tsx` (new) — filter is client-side (no second fetch); suspend confirm patches the row to suspended locally; provision success appends the row + clears the password field; error codes map to their own sentences; reset modal keeps values on `owner_not_found`; render asserts no `size="sm"` buttons | C `Frontend/apps/platform/src/components/{Console.tsx, TenantTable.tsx, ProvisionForm.tsx, SuspendDialog.tsx, ResetPasswordDialog.tsx}` (fold small ones into Console.tsx if they stay small — fewest files wins), M `…/src/i18n/{he.ts, ar.ts}`, C `…/src/__tests__/Console.test.tsx` |

### Phase F — e2e (commit 9)

| # | Task | Test first | Files |
|---|---|---|---|
| F1 | Third `webServer` entry (`pnpm --filter platform preview --port 4175 --strictPort`); `fixtures/platform.ts` interception harness in the `manage.ts` style (fulfils `/platform/auth/*` + `/platform/tenants*` — it proves the console, not the contract; the db-marked tests are the contract side). `platform.spec.ts` journeys: bad password → Hebrew error (no exclamation) → good → table; provision happy path + `slug_taken` + reserved-slug client message; suspend dialog (red on the final confirm only) flips the row; reset dialog; logout → login. **axe zero-violation** on: login (incl. error state), table (populated + empty + filter-no-match), provision form, both modals open. RTL rendering; focus-trap/restore assertions live here, not vitest (`.memory/jsdom-has-no-dialog`). | this IS the test | M `Frontend/e2e/playwright.config.ts`, C `Frontend/e2e/fixtures/platform.ts`, C `Frontend/e2e/platform.spec.ts` |

## 4. Build environment — RECORD, these are facts not suggestions

- **No Docker locally.** Tests marked `db` or `s3` run **on CI only**. Do not chase local db-test failures.
- **The local fast lane (`-m 'not db'`) points at a CLOSED Postgres port by design (F21).** A db-touching test without the `db` marker fails locally — correct behaviour, not a bug. Every new db-touching test carries the marker.
- **The worktree has no `Backend/.env`** — config-default tests behave differently than the main checkout (`.memory/local-env-breaks-config-tests`; in the worktree a config failure is REAL).
- **Local gates, all must pass before push**: `make lint` · backend non-db tests (`make test`) · `make fe-test` · `make fe-build` · `make e2e`.
- db-marked tests debut on CI — write them carefully against the spec's test plan (`.memory/boutique-ci-first-run-surprises`).

## 5. Build discipline

**Commit boundaries** (conventional, scoped):
1. `feat(platform): operator and session tables, models, repositories; CLI parity pinned` — A1–A3.
2. `feat(cli): create-operator and deactivate-operator bootstrap` — B1.
3. `feat(tenancy): admin host fence, both directions` — C1.
4. `feat(platform): operator login, sessions, cookie auth, rate limiting, CSRF` — C2.
5. `feat(platform): console endpoints over the unchanged ProvisioningService; walker registration` — D1–D2.
6. `refactor(cli): delete the four lifecycle subcommands at parity` — D3 (its own commit: the deletion must be revertable without touching the console).
7. `feat(platform-app): third workspace app scaffolding, SPA serving, CI copy step` — E1.
8. `feat(platform-app): login, tenant table, provision form, row actions, i18n` — E2–E3.
9. `test(e2e): platform console journeys with axe` — F1.

**Migration renumber protocol**: numbered observed-head+1 in the worktree at build time. **F22 holds `0026` live and F24 is queued next — assume up to two siblings land first and this plan's number shifts.** Immediately before the pre-push rebase, re-run `alembic heads` against rebased main; if a sibling took the number, renumber (filename + `revision` + `down_revision`) in one `fix(platform):` commit. A squatted number breaks alembic outright and reds every db test (`.memory/parallel-alembic-numbering`).

**Pathspec**: git tracks `backend/`/`frontend/` **lowercase**. `git add Backend/…` silently skips modified tracked files — lowercase every pathspec, verify with `git show --stat` (`.memory/git-add-uppercase-pathspec-trap`).

**Frontend build check**: `pnpm build` before staging any `.ts`/`.tsx`.

**After any merge-conflict resolution**: parse every touched test file's collection count — a broken file reads as one `Tests no tests` line (`.memory/silently-unexecuted-test-files`).

## 6. Risks this plan adds to the spec's list

- **R-A**: C2 is the platform's highest-privilege surface and its dual review is adversarial by decree (spec header). If any auth test is awkward to write fast-lane (limiter clocks, host state), write it db-marked rather than weakening it — the adversarial matrix (brute force, theft, host confusion, audit bypass) is the deliverable, not a coverage number.
- **R-B**: D3's deletion is ordered AFTER D1's db-marked lifecycle proves endpoint parity — but that proof first runs on CI. If the builder cannot see CI green before D3 locally, D3 still lands in the same PR; the merge gate (the only gate — main is unprotected) is where parity is enforced. Do not ship commit 6 without commit 5 in the same push.
- **R-C**: the fence (C1) and the SPA catch-all (E1) both claim `/platform` — land C1 first so `_RESERVED_SEGMENTS` and the middleware agree before any static serving exists; `test_spa_serving.py` runs bundle-less in the fast lane, so the fence matrix is the real tripwire.
- **R-D**: `csrf.py`'s prefix change (C2) touches `/manage` behaviour — the existing manage CSRF suite staying green unedited is the regression tripwire for the tuple change.
- **R-E**: ci.yml is shared ground with any parallel feature editing workflows — expect a rebase conflict in the copy step; after resolving, re-check all three `cp -R` lines and the assert loop survive.
