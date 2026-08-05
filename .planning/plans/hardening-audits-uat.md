# Plan: Feature 21 — Hardening, audits & pilot UAT (Epic E4)

**Spec**: `.planning/specs/hardening-audits-uat.md` (356 lines, D1–D11, B1–B9, Gate 1 standing approval)
**Plan written**: 2026-08-05, against `main` @ `7484c0a` (head migration `0025_walk_in_bookings`)
**Branch**: `feature/hardening-audits-uat` off `main`. No worktree — `.worktrees/` does not exist on this tree; build in the main checkout.
**Migration**: **NONE.** D9 and D11 argue why, and the one candidate column (the orphan clock) is `F62`'s. `alembic heads` reads `0025` and must still read `0025` at the pre-push rebase. If any task in this plan appears to need a migration, that task has left F21.

TDD throughout. Every task names its **failing test first**, then the change that makes it pass, then the exact files, then the verification command, then the commit it lands in.

---

## 0. How to read this plan

The spec is authoritative and D1–D11 are **not** re-litigated. What follows in §1 is six places where the spec's *file-and-line claims* disagree with the tree as it stands today. In every case the codebase-consistent reading is taken, per the interview's own rule, and the amendment is stated rather than absorbed — a plan that silently corrects its spec teaches the next reader to trust neither.

Two of the six change the shape of a deliverable:

- **C1** — `/queue` **already has two bespoke axe journeys**. Half of B6's first clause is already shipped.
- **C2** — the Playwright harness serves `vite preview`, **not FastAPI**, so B2's stated acceptance criterion cannot be met by adding a spec file. The resolution is in Task 5/6 and it is better than the spec's sketch, not a retreat from it.

---

## 1. Where the spec and the code disagree — C1…C6

### C1 — `/queue` is **not** unscanned. It has two bespoke axe journeys, both gating.

Spec D7 item 1: *"`/queue` — the public wall board — has zero axe coverage… no `AXE_ROUTES` row and no bespoke journey."* The first clause is right; the second is false, and the second is the one that matters.

`Frontend/e2e/storefront.spec.ts` ships two:

- `:2870` — inside *"storefront wall board"* journey 1: a populated five-row board, the freshness line, the 2.2.2 pause exercised **before** the scan (with a comment saying the pause is what makes the scan deterministic against a 5 s repaint), then `expect(await axeViolations(page)).toEqual([])`.
- `:2877` — `test("storefront wall board: the empty board is a designed state with its own axe pass")`, `installApi(page, "populated", BOUTIQUE, { queue: [ok(boardBody(0))] })`, `gotoSettled(page, "/queue")`, then the same hard assertion.

Both go through the file's shared `axeViolations` (`:571`), which is `withTags(["wcag2a","wcag2aa"])` with no `.disableRules()` and no `.exclude()`.

**Reading**: the board's **populated** and **empty** states are closed. What `public-queue-board.md`'s A29 ("zero axe violations on **every materially different state**") still lacks must be **derived from the board's own state list at build time**, not assumed to be "all of it". Task 10 opens `QueueBoardPage.tsx` and enumerates its render branches, and closes whatever is not one of those two — most likely the **truncated/partial** state and the **outage** state, both of which render different chrome. If the enumeration finds nothing left, A29 is ticked with the two shipped journeys as its evidence and B6's `/queue` clause costs zero lines. **That is a legitimate outcome and must be recorded as one**, not padded with a third scan that scans the same DOM.

### C2 — **The e2e harness never touches the middleware.** B2's acceptance criterion needs a different instrument.

`Frontend/e2e/playwright.config.ts:14-29` declares two `webServer` entries, both `vite preview` (`--filter storefront preview --port 4173`, `--filter manage preview --port 4174`). `Makefile:51-52` confirms it: `pnpm -r build && … && pnpm e2e`. **FastAPI is not in the request path in e2e.** The CSP `SecurityHeadersMiddleware` emits is therefore invisible to every Playwright test that exists, and a spec file added naively would assert the *absence* of a header and pass vacuously — the exact `known_vacuous` failure mode this repo has been bitten by four times.

The three ways out, and why one wins:

| Option | Cost | Verdict |
|---|---|---|
| A third `webServer` running uvicorn against `backend/app/static/` | Needs a database, a migrated schema, a seeded tenant and a resolvable `Host` — `TenantResolutionMiddleware` 404s an unknown host, so even serving the shell needs a tenant row. A whole new harness for one header. | **Rejected.** |
| `preview.headers` in both `vite.config.ts` files | The policy becomes a *copy* living in two frontend configs, drifting from the backend's the moment `media_endpoint_url` changes — and it proves nothing about the middleware. `vite.config.ts` is also the file two prior features fenced off. | **Rejected.** |
| **Playwright route interception injecting a policy read from a committed fixture, with a backend test pinning the fixture to what the middleware actually emits** | One fixture file, one backend parity test, one spec file. The browser applies a real policy to the real bundle, and drift between the two halves is a **red backend test**, not a silent divergence. | **Taken.** |

The parity direction has precedent in this repo: `test_frontend_constant_parity.py` mirrors backend constants into frontend files and asserts the mirror, and `test_frontend_imports_are_tracked.py` reads the frontend tree from a backend test. This is that pattern with the payload being a header string.

**Reading**: spec §Testing's B2 bullet — *"a Playwright test loading the real built bundle with the real policy applied"* — is met in substance and by a different mechanism. Tasks 5 and 6 spell it out. The spec's sentence is amended in Task 0 so nobody "fixes" the plan back toward the impossible reading.

### C3 — The console has **fifteen** sections, not sixteen, and **four** of them are already scanned.

`Frontend/apps/manage/src/lib/guide.ts:14-33` — `SectionKey` is fifteen members: `dashboard profile hours types terms catalog bookings customers board staff gateway floor checkinQr atelier privacy`. `GUIDE_STEPS` at `:53-69` is the fifteen-key `satisfies Record<SectionKey, …>` that makes a sixteenth a type error.

Scanned today:

| Section | Where |
|---|---|
| `floor` | `manage.spec.ts:601` — populated floor, a reveal and an alert open |
| `board` | `manage.spec.ts:643` — with the remove confirm open |
| `atelier` | `atelier-capacity.spec.ts:291`, `:370`, `:491` — three states |
| `dashboard` | **incidentally**, `guide.spec.ts:625` — `gotoConsole(page)` lands on the first `NAV` row (`App.tsx:68`, *"the console lands here"*), and `manage.spec.ts:419` records that a `dialog:modal` leaves the rest **inert but visible to axe**, so the guide scan does see the dashboard behind it |

So **eleven** are genuinely unscanned, and the spec's *list* — `dashboard, profile, hours, types, terms, catalog, bookings, customers, staff, gateway, privacy` — is **exactly right** while its count ("nine of sixteen") is wrong twice over.

**Reading**: build to the list, eleven surfaces. Keep `dashboard` on the list despite the incidental coverage: a scan taken with a modal open is a scan of a different DOM, and D7's whole complaint is that silence reads as coverage. Its own scan is one `AXE_SECTIONS` row.

### C4 — `catalog` has **nine** mutating routes, not eleven.

`Backend/app/catalog/router.py` declares eleven routes; **two are reads** (`@router.get("/dresses")` `:139`, `@router.get("/dresses/{dress_id}")` `:180`). The nine the spec enumerates by name — create `:163`, update `:188`, delete `:210`, restore `:219`, variants `:230`, media presign `:253`, media confirm `:276`, media delete `:290`, media reorder `:304` — are the mutating set, and nine is the number of audit rows B4 adds. Confirmed independently: `grep -n audit catalog/service.py` returns **nothing**, so the "zero `AuditLogRepository` usage" half is exactly true.

**Reading**: B4 is nine `_audit.record(...)` calls and nine `AuditAction` members. "Eleven endpoints" in the spec's D2/B4 reads **nine mutating endpoints of eleven routes**.

### C5 — `_client_ip` already exists, and it returns `None` on every deployment we currently have.

`Backend/app/auth/router.py:29-39`:

```python
def _client_ip(request: Request, trust_forwarded_for: bool) -> str | None:
    if not trust_forwarded_for:
        return None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else None
```

`trust_forwarded_for` ships **`False`** (`core/config.py:37`), and `config.py:108` names this feature as its resolver in writing: *"Per tenant, not per IP, for the same reason every other budget here is: trust_forwarded_for is unresolved until F21."*

So a per-IP key added to the OTP send path is **inert by default**: `ip is None`, the key is never appended, nothing is metered. Shipping it and ticking R16 would be a green row on a mechanism that does not run — the precise failure D2 exists to prevent.

**Reading, and this is a decision the plan makes**: F21 ships the code (Task 9) and does **not** flip the flag. `TRUST_FORWARDED_FOR=true` is only correct on a deployment that terminates exactly one trusted proxy, which is a host fact. **R16 is therefore AMBER, not green**, with three clauses and two owners:

- per-phone, per-tenant, OTP TTL 300 s, single-use — **green, F13/F16**
- per-IP on OTP send — **code green at F21, inert until `TRUST_FORWARDED_FOR=true`; enablement owned by `F62`**
- distributed limiter (Redis) — **`F62`**

No `R16a/b/c` split is needed: the checklist already carries AMBER rows with named per-clause owners (F20's R40 and R42), and reusing that convention is one fewer moving part than a D1 suffix split. R7 takes the same shape for the same reason.

### C6 — **Seven** test files import `SECURITY_HEADERS`, not eight.

`test_booking_api.py`, `test_booking_manage_api.py`, `test_checkin_api.py`, `test_notifications_api.py`, `test_payments_webhook_api.py`, `test_spa_serving.py`, `test_storefront_api.py`. The eighth hit in a naive grep is `app/security_headers.py` itself.

**Reading**: cosmetic, but D3's mechanical argument is load-bearing and its arithmetic should be right. **Seven** files compare the dict with `==`, which is why CSP and HSTS must be emitted *beside* `SECURITY_HEADERS` and never joined to it. The constraint is unchanged.

### Citations re-verified — ✅ do not re-check

- ✅ `Backend/app/security_headers.py` — module docstring `:1-25`, the two stale claims at `:11-17` and `:19-24`, `SECURITY_HEADERS` `:31-37` (three headers), `SecurityHeadersMiddleware.dispatch` `:41-47` with the `setdefault` comment `:43-44`. Middleware registration `main.py:701`, **last**, after `CsrfOriginMiddleware` `:697`.
- ✅ `.github/workflows/ci.yml` — five jobs. `audit` `:218`, `name: Dependency audits (warn-only)` `:219`, the `# warn-only until the E4 ship gate flips this to blocking` comment `:220-221` naming the checklist by path, `continue-on-error: true` **`:223`**, `pip-audit` step `:227-231` (`uv export --locked --no-emit-project` then `uvx pip-audit -r`), `pnpm audit` step `:235-237`. `deploy-staging.needs: [backend, frontend]` **`:124`**. The `brain` job is already `continue-on-error: true` `:111` and stays that way.
- ✅ `Makefile` — `test` `:18-19` (`pytest -m "not db" -q`), `test-db` `:21-22`, `test-all` `:24-25`, `lint` `:27-30`, `qa-greps` `:33-34`, `fe-build` `:44-45`, `fe-test` `:47-48`, `e2e` `:51-52`, `brain-check` `:65-66`.
- ✅ `Backend/tests/conftest.py:84-112` — the `postgres_url` fixture and the `TEST_POSTGRES_SUPERUSER_URL` override, with its docstring stating the constraint is *"permanent, not incidental"* and requiring a **superuser** URL against a **throwaway** cluster.
- ✅ `Backend/tests/test_staff_role_gating.py` (992 lines) — `_leaf_routes` `:270-278` recursing through `original_router`, `_gate_role_sets` `:281-287` reading `allowed_roles` off the dependency tree, `test_every_manage_route_is_role_gated` `:292` with **both** anti-vacuity legs (`assert seen - UNGATED_ALLOWLIST`, `assert seen >= UNGATED_ALLOWLIST`) at `:307-308`, `UNGATED_ALLOWLIST` `:262-266` with a per-entry reason. `OWNER_ONLY` `:79-92`. This is the pattern Tasks 3 and 7 copy.
- ✅ `Backend/app/db/repositories/audit_log.py` — `AuditLogRepository.record(session, *, tenant_id, action, actor_id=None, entity=None, details=None)` `:10-30`, `session.add` + `await session.flush()`. The call idiom is `boutique/service.py:188-195`.
- ✅ `Backend/app/platform/service.py:202-209` — `list_tenants` opens a **bare** `self._session_factory()` (no `tenant_session`), selects every non-deleted tenant, and writes nothing. `reset_owner_password` `:212-241` is the in-file precedent for a `platform_audit_log` row: `self._audit.record(session, operator=…, action=PlatformAuditAction.…, target_tenant_id=…, details={…})` at `:234-240`.
- ✅ `Backend/app/auth/cookies.py` — `set_session_cookie(..., *, secure: bool, max_age: int)` with `httponly=True`, `samesite="lax"`, `path="/"` and **no `domain=`**, the host-only comment `:7-9`. `Settings.secure_cookies` is `self.app_env != "dev"` (`core/config.py:243-245`).
- ✅ `Backend/app/db/session.py` — `verify_database_role` `:12-42` (refuses `rolsuper`, `rolbypassrls` **and** table ownership), `ensure_safe_database_role` `:45-50` gated on `get_settings().app_env != "dev"`.
- ✅ `Backend/app/notifications/router.py:50` `POST /storefront/otp/send` — takes `request: Request` already, so no signature widening is needed to reach the client IP. `OtpService.send` `:232-274` builds `phone_key` `:239` and `tenant_key` `:240` and spends both at `:247-248`. Limiters are constructed at `main.py:795-812` (`phone_limiter` `:798`, `tenant_limiter` `:803`, `verify_limiter` `:808`).
- ✅ `Backend/app/storage/s3.py:78` — `endpoint_url = self._endpoint_url or f"https://s3.{self._region}.amazonaws.com"`, and `:73-76` records that an explicit `endpoint_url` forces **path-style** addressing. So the media origin is the endpoint host itself and never `bucket.s3.….amazonaws.com` — which is what makes the CSP source a one-line derivation.
- ✅ `Frontend/e2e/storefront.spec.ts` — `installApi` `:462`, `axeViolations` `:571`, `gotoSettled` `:580`, `AXE_ROUTES` **`:745-763`** (nine rows).
- ✅ `Frontend/e2e/manage.spec.ts` — `installManageApi` imported from `./fixtures/manage` `:9`, the ⚠ *"the harness stubs the API, so these prove the CONSOLE and not the CONTRACT"* banner `:31-33`, `axeViolations` `:135-136`.
- ✅ Six workspace manifests, which is the "six `package.json` files" D4 cost 2 predicts: `frontend/package.json`, `frontend/apps/manage`, `frontend/apps/storefront`, `frontend/e2e`, `frontend/packages/api-client`, `frontend/packages/ui`.

---

## 2. Three process facts, and one correction to the spec's Testing preamble

**1. `db`-marked tests RUN LOCALLY. Only `s3`-marked tests debut on CI.** The spec's §Testing says *"db-marked tests debut on CI unless run locally against real Postgres first"*, which is right but understates how shipped the path is. `Backend/tests/conftest.py:84-112` is **committed code**: `TEST_POSTGRES_SUPERUSER_URL` replaces Testcontainers with a cluster you started yourself, and its docstring says why in writing. Homebrew Postgres 16 is live (`.memory/ci-first-run-surprises` records the db suite at ~33 s locally on PG16; `.memory/boutique-build-workflow` records that there is no Docker here). There is **no patch to apply and no revert obligation** — `git diff main -- backend/tests/conftest.py` must stay empty.

The runner, written once into the scratchpad and never committed:

```bash
# scratchpad/run-db-tests.sh
set -euo pipefail
dropdb   --if-exists -h 127.0.0.1 -U mrwen f21_test
createdb              -h 127.0.0.1 -U mrwen f21_test
export TEST_POSTGRES_SUPERUSER_URL='postgresql+asyncpg://mrwen@127.0.0.1:5432/f21_test'
cd "/Users/mrwen/Documents/Github/Ryan + rawad + mrwen/Backend"
uv run pytest -m "db and not s3" -q
```

**Capture the baseline on `main` BEFORE Task 1** and record the number. Do not hardcode a count from an earlier plan. The `test_media_upload_s3.py` cases need MinIO and are excluded — **those are the only tests in this feature that genuinely debut on CI**, and F21 adds none of them.

Tasks 3, 7 and parts of 8 are `db`-marked. Every one runs locally before it is pushed.

**2. Path hygiene, still load-bearing.** The repo path contains a **space** and a **`+`** — quote every shell path. Git tracks `backend/` / `frontend/` **lowercase** while the on-disk directories are `Backend/` / `Frontend/`: `git add Backend/…` **silently skips modified tracked files** (`.memory/git-add-uppercase-pathspec-trap`). Lowercase every pathspec; verify every commit with `git show --stat`.

**3. `.brain/` will go stale and that is expected.** This feature edits `security_headers.py`, `catalog/service.py`, `platform/service.py`, `notifications/service.py` and `ci.yml`, several of which have brain pages. The `brain` CI job is `continue-on-error: true` (`ci.yml:111`). **Do not stop mid-task to write pages** — the SessionEnd hook surfaces the drift and `/brain-sync` reconciles it after merge. That is the project rule, restated here so a builder does not treat a stale-page warning as a gate.

**⚠ Two `test_config.py` failures are always false locally** — `Backend/.env` leaks `MEDIA_BUCKET` (`.memory/local-env-breaks-config-tests`). CI is green. Do not chase them. This matters more than usual in F21, because Task 5 adds `Settings`-derived behaviour and the instinct will be to blame the new code.

---

## 3. The sequencing decision the spec asked for: **the lockfile refresh goes FIRST**

The prompt for this plan asked for an explicit call with a justification, so here it is on the record.

**Decision: Task 1, alone, before any other line of F21 is written.** The full gate must be green on the refresh commit before Task 2 begins.

**Why not last.** The "last" argument is that a broken refresh then blocks nothing else. It is a real argument and it loses on one fact: **B2's browser test and B6's eleven new axe scans are Playwright code, and B6's console scans run against a Rolldown-built bundle.** Building twelve new browser tests against Playwright 1.62.0 / Rolldown 1.1.5 and *then* bumping both means the refresh's gate run is the first time the new tests ever meet the new toolchain — the entanglement is not avoided, only deferred to the worst moment, when the PR is otherwise assembled and the pressure to "just relax that assertion" is highest. Refreshing first means the bump is measured against a **known-good baseline of 2515 vitest tests and 155 e2e tests** that nobody in this feature has touched, which is the only configuration in which a red is unambiguously the bump's.

The same argument applies to `oxlint 1.74.0 → 1.77.0`: an oxlint minor can add rules, and new rules should be met by code that is being written, not by code that was just finished.

**Why the fallback makes "first" cheap.** The refresh is one commit touching two file classes (`pnpm-lock.yaml` + six manifests) and nothing else. If it cannot be made green within a bounded effort, `git revert` it and land the gate anyway with four dated per-advisory waivers — see Risk 1 for the exact escape. The gate flipping to blocking is what R34 actually requires; closing the nine findings is how F21 prefers to reach it, not the requirement itself. So the downside of "first" is one revert; the downside of "last" is re-debugging twelve browser tests through a version change.

**Why Task 2 (the gate flip) cannot come before Task 1.** Setting `continue-on-error: false` while `pnpm audit` still reports nine findings reds the PR on its first push and on every push after, which would make every subsequent task's CI run unreadable.

---

## 4. Dependency graph and ordering

```
T0 (plan + spec amendments)
 └─> T1  chore(deps): lockfile refresh          ── the blast radius, isolated
       └─> T2  feat(ci): gate the audits + e2e in the deploy gate
       └─> T6  test(security): CSP in a real browser        (needs T5)
       └─> T10 test(a11y): eleven console sections + the board's gap
       └─> T11 fix(a11y): FloorPanel / GuideOverlay live regions

T0 ─> T3  test(security): the cross-tenant walker      ── backend-only, independent of T1
T0 ─> T4  feat(security): HSTS                          ── backend-only, independent of T1
      └─> T5  feat(security): CSP                       ── independent of T4, ordered after it
            └─> T6
T0 ─> T7  feat(audit): catalog + list_tenants + walker  ── backend-only, independent of T1
T0 ─> T8  test(security): five pins                     ── backend-only, independent of T1
T0 ─> T9  feat(security): per-IP OTP key                ── backend-only, independent of T1

T10, T11 ─> T12 docs: .planning/a11y-audit-v1.md
ALL ─────> T13 docs: the checklist rewrite              ── STRICTLY LAST of the build tasks
T13 ─────> T14 docs: reconcile the F62 entry
```

**Strictly sequential**: T1 → T2. T5 → T6. T10/T11 → T12. Everything → T13.

**Genuinely parallel** (backend-only, no shared file, no shared test module): **T3, T4+T5, T7, T8, T9**. If this is split across sessions, that is the split. `main.py` is touched by T5 (middleware kwarg) and T9 (a new limiter instance) — those two are the only file collision in the backend half, and they collide in different functions.

**T13 is last and that is a correctness rule, not a preference.** The checklist records a verdict per row. A verdict written before the code it describes is exactly the failure mode the spec's Problem statement opens with — *"a row marked green on the strength of a planning note"*. T13 reads the tree, not this plan.

---

## 5. The ordered task list

### Task 0 — This plan and six spec corrections
`.planning/plans/hardening-audits-uat.md` (**✚**, this file), `.planning/specs/hardening-audits-uat.md`

No test, no code. Amend the spec so it is the binding statement of §1's readings:

- **D7 item 1** — `/queue` has two shipped bespoke axe journeys (`storefront.spec.ts:2870`, `:2877`). A29's residual is whatever the board's *other* render branches are, to be enumerated at build time (C1).
- **§Testing, B2 bullet** — the Playwright harness serves `vite preview` and never reaches the middleware; the acceptance instrument is route-injection of a policy read from a fixture that a backend test pins (C2). Name Tasks 5/6.
- **D7 item 2** — `SectionKey` is fifteen; four sections are already scanned; the unscanned **list of eleven is correct and the count of nine is not** (C3).
- **D2 / D6 / B4** — `catalog` has nine mutating routes of eleven (C4).
- **D2's R16 row and the PARKED table** — R16 is **AMBER** at F21: per-IP is code-green and inert until `TRUST_FORWARDED_FOR=true`, whose enablement joins the distributed limiter on `F62` (C5). R7 takes the same AMBER shape it already implies.
- **D3** — **seven** test files compare `SECURITY_HEADERS` with `==`, not eight (C6). The constraint is unchanged.

- **Done when**: `grep -n "zero axe coverage\|nine of sixteen\|all 11 endpoints\|Eight test files" .planning/specs/hardening-audits-uat.md` returns nothing.
- **Commit**: `docs(planning): F21 implementation plan and six corrections against the code`

---

### Task 1 — The lockfile refresh, alone (B1, part 1) · R34
`frontend/pnpm-lock.yaml`, `frontend/package.json`, `frontend/apps/manage/package.json`, `frontend/apps/storefront/package.json`, `frontend/e2e/package.json`, `frontend/packages/api-client/package.json`, `frontend/packages/ui/package.json`

**The failing check first.** This task's red is a command, not a pytest node — and it is a real red:

```
cd "…/Frontend" && pnpm audit ; echo "exit=$?"
```

must report **9 findings (4 high, 5 moderate)** and a non-zero exit today. Record the exact GHSA ids before touching anything; Task 2's waiver scaffold and Risk 1's fallback both need them.

**The change.**

```
cd "…/Frontend" && pnpm update -r --depth Infinity --lockfile-only
```

D4 measured this on 2026-08-05 and it lifts `undici` 7.28.0→≥7.29.0, `brace-expansion` 2.1.2→≥2.1.4, `js-yaml` 4.2.0→≥4.3.0 and `postcss` 8.5.21→≥8.5.23, all **inside the ranges the manifests already declare** — so **no `pnpm.overrides` and no range widening**. It also moves ~16 other packages (React 19.2.7→19.2.8, Vite 8.1.5→8.2.0, Rolldown 1.1.5→1.2.3, oxlint 1.74.0→1.77.0, Playwright 1.62.0→1.62.1) and **rewrites declared floors in all six manifests** (`react ^19.2.7→^19.2.8`, `vite ^8.1.1→^8.2.0`, `oxlint ^1.71.0→^1.77.0`, `typescript ^5.7.0→^5.9.3`, `@vitejs/plugin-react ^6.0.3→^6.0.5`, `@types/react ^19.2.17→^19.2.18`). That six-manifest diff is **expected and reviewable** — do not reach for `--no-save`, which would leave the manifests describing a floor the lockfile no longer sits on.

Then `pnpm install --frozen-lockfile` and run the whole gate. **Any breakage is fixed in this commit**, so the commit stays the single attributable unit.

- **Verify**:
  ```
  cd "…/Frontend" && pnpm audit                  # exit 0, "No known vulnerabilities found"
  make lint ; make fe-test ; make fe-build ; make e2e
  make test ; bash "<scratchpad>/run-db-tests.sh"
  ```
  The backend targets are in the list because a Vite/Rolldown output change alters `dist/`, and `test_spa_serving.py` asserts against the built shells.
  **Green looks like**: vitest **2515** (ui 108, storefront 1097, manage 1310) and e2e **155 with axe at zero violations** — the F61 merge numbers, which are this task's baseline. A count that *drops* is as much a failure as a red: `.memory/silently-unexecuted-test-files` records that a broken test file reads as one `Tests no tests` line, not N failures.
- **Commit**: `chore(deps): refresh the pnpm lockfile onto patched transitive devDependencies`

---

### Task 2 — Gate the audits, add the waiver scaffold, put `e2e` in the deploy gate (B1, parts 2–4) · R34, R47
`.github/workflows/ci.yml`, `frontend/package.json`

**The failing test first.** A CI change has no pytest node, so the red is constructed and it must be **run, not reasoned about**:

1. On a scratch branch off this one, add a deliberately fake waiver with a **past** expiry to `frontend/package.json`'s `pnpm.auditConfig`, push, and confirm the `Dependency audits` job **reds**. This is the assertion that the waiver machinery is not decorative — spec §Testing's B1 bullet requires exactly this and it is the only part of B1 that can be got wrong silently.
2. Discard the scratch branch.

**The change**, four edits:

| # | Edit | Line |
|---|---|---|
| 1 | Delete `continue-on-error: true` from the `audit` job | `ci.yml:223` |
| 2 | `name: Dependency audits (warn-only)` → `name: Dependency audits`, and replace the `# warn-only until the E4 ship gate flips this to blocking` comment with one recording that F21 flipped it, that the gate is the **full** `pnpm audit` and not `--prod`, and **why** (D4: `--prod` is blind to the toolchain that assembles `dist/`) | `ci.yml:219-221` |
| 3 | `deploy-staging.needs: [backend, frontend]` → `[backend, frontend, e2e]`, with a comment naming the reason: a legal accessibility requirement that does not block a deploy is not a gate (D7, spec Risk 4 accepts the longer merge path) | `ci.yml:124` |
| 4 | The waiver scaffold: `pnpm.auditConfig.ignoreGhsas: []` in `frontend/package.json` with a **comment block above it stating the four required fields** — GHSA/PYSEC id, one sentence of why it does not reach this product, the date, and an **expiry date** — and the rule that an expired waiver reds the build and a waiver with no rationale is the thing R34 exists to prevent. The backend half is `pip-audit --ignore-vuln <id>` appended to `ci.yml:231` when needed; scaffold the comment there too, with an empty flag list. | — |

**Do not add `--ignore-registry-errors`.** `pnpm audit` needs the registry and an outage will red this job. That is correct behaviour — retry. The flag would turn every outage into a silent pass, which is the same defect as `continue-on-error` wearing a different name.

- **Verify**: push and read the `Dependency audits` job — it must be **green and required**. `deploy-staging` must show `e2e` among its needs. The fake-waiver red from step 1 must have been observed and recorded in the PR body.
- **Commit**: `feat(ci): gate the dependency audits, add the waiver scaffold, and put e2e in the deploy gate`

---

### Task 3 — The cross-tenant route walker (B3) · R9
`Backend/tests/test_cross_tenant_walker.py` (**✚**)

**Run this task early.** It is the highest-variance deliverable in the feature: its success condition includes *finding a real isolation hole*, which is a BLOCKER-class discovery (Risk 3) and must land with runway, not against an assembled PR.

**The failing tests first** (`db`-marked, run locally):

1. **`test_every_tenant_scoped_route_refuses_another_tenants_ids`** — enumerate the live FastAPI route table with `_leaf_routes` (copied from `test_staff_role_gating.py:270-278`, including the `original_router` recursion — without it the walker sees only the docs routes and passes vacuously). For every tenant-scoped route not in `UNWALKABLE`, drive it as an authenticated principal of **tenant A** with every id in the path, query and body belonging to **tenant B**. Assert the status is **404** — never 200, never a 403 that leaks existence, never 500. A 500 is a failure and not an excuse: it means the route reached code that assumed the row existed.
2. **`test_the_walk_and_the_exemptions_are_the_whole_route_table`** — `walked | UNWALKABLE == {every tenant-scoped route}`, both directions. A new route is a **test failure**, not a silent gap. Carries `test_every_manage_route_is_role_gated`'s two anti-vacuity legs verbatim (`assert walked`, `assert route_table >= UNWALKABLE` — an exemption naming a route that no longer exists must be pruned, not left).
3. **`test_no_module_is_wholly_exempt`** — and **this is the test that makes Risk 3 mechanical rather than aspirational.** A per-module floor: `{"auth", "staff", "boutique", "customers", "dashboard", "privacy", "platform", "storage", "booking", "payments", "floor", "queue", "catalog", "atelier"}` each contribute **at least one walked route**. Spelled as a dict of module → minimum, not derived, so growing `UNWALKABLE` cannot silently empty a module. If `privacy` or `staff` ends up wholly exempt, **row 9 is not closed** — spec Risk 3's acceptance bar, asserted.

`UNWALKABLE` is an explicit dict of route → **reason string**, not a set. The reasons that are already known: multipart media upload (the body is a real file), webhook signature verification (the caller is the gateway, not a tenant principal), and token-authenticated storefront paths (`/b/{token}` proves possession, not tenancy — its isolation is `test_manage_token.py`'s and must be named as such).

**The mutation-check, mandatory — RUN it, do not reason about it.** The walker's own vacuity is the risk here.

| Mutation | Expect |
|---|---|
| Change one route's not-found branch from 404 to **403** | test 1 **RED**, naming that route. This is the leak the row's text is actually about. |
| Delete one entry from the walk (neither walked nor exempted) | test 2 **RED** |
| Move one `privacy` route into `UNWALKABLE` with a plausible reason | test 3 **RED** on the `privacy` floor — *the mutation that proves `UNWALKABLE` cannot quietly become the interesting half* |
| Drop the explicit `tenant_id ==` predicate from one repository read | **stays GREEN** — RLS carries it. **Record that in the module docstring** rather than pretending the walker proves defence-in-depth; the ten `test_*_isolation.py` files prove the repository half, which is why D5 keeps them. |

**⚠ If the walker finds a genuine hole, STOP.** Do not relax the assertion, do not move the route to `UNWALKABLE`. See Risk 3.

- **Verify**: `bash "<scratchpad>/run-db-tests.sh"` — baseline plus the three new cases, all green, all four mutations performed and restored. `make test` collects and deselects the module.
- **Commit**: `test(security): a live-route-table cross-tenant walker with a per-module coverage floor`

---

### Task 4 — Scheme-gated HSTS (B2, half 1) · R33
`Backend/app/security_headers.py`, `Backend/tests/test_security_headers.py` (**✚**)

**The failing tests first** (fast, no Postgres):

- `test_hsts_is_emitted_over_https` — a request with `x-forwarded-proto: https` carries `Strict-Transport-Security: max-age=31536000; includeSubDomains`. **Reds today with `KeyError`/`None`.**
- `test_hsts_is_absent_over_http` — the default test client (scheme `http`, no XFP header) carries **no** `Strict-Transport-Security` at all.
- `test_hsts_carries_no_preload` — the emitted value does not contain `preload`. Preload submission is effectively irreversible and belongs to a domain that resolves (D3).
- `test_the_security_headers_dict_is_unchanged` — `SECURITY_HEADERS` is still exactly the three constant headers. **This is the test that protects the seven files doing `== SECURITY_HEADERS`** (C6), and it is cheap insurance against a later author "tidying" the new headers into the dict.

**The change.** In `dispatch`, after the `setdefault` loop:

```python
if _effective_scheme(request) == "https":
    response.headers.setdefault("Strict-Transport-Security", HSTS_VALUE)
```

where `_effective_scheme` reads the **last** `x-forwarded-proto` entry and falls back to `request.url.scheme`.

**Why `x-forwarded-proto` is read unguarded while `x-forwarded-for` is not, and this asymmetry must be in the code comment.** `config.py:30-36` refuses to trust XFF without `trust_forwarded_for` because a spoofed XFF poisons a rate-limit bucket — a real attack. A spoofed XFP over plain HTTP makes the app emit an HSTS header that **the browser ignores**, because HSTS over http is ignored by specification. There is nothing to spend and nothing to poison. So HSTS needs no config flag and no trusted-proxy declaration, which is D3's *"one condition, not a config flag"* made mechanical.

The docstring's `**HSTS and CSP are deliberately absent**` paragraph (`:19-24`) is rewritten in Task 5, once both halves are in.

- **Verify**: `make test` — the four new cases green, the seven `SECURITY_HEADERS` importers green **unedited**.
- **Commit**: `feat(security): scheme-gated HSTS, emitted beside SECURITY_HEADERS and never inside it`

---

### Task 5 — The settings-derived CSP (B2, half 2) · R28, R33
`Backend/app/security_headers.py`, `Backend/app/main.py`, `Backend/tests/test_security_headers.py`, `Frontend/e2e/fixtures/csp.txt` (**✚**)

**The failing tests first** (fast, no Postgres):

- `test_the_csp_is_emitted_on_every_surface` — `Content-Security-Policy` present on both SPA shells, on a JSON API response, and on the `TENANT_NOT_FOUND` 404 that `TenantResolutionMiddleware` returns without reaching a handler. **Reds today with `None`** on all four.
- `test_the_csp_names_the_media_origin_when_a_bucket_is_configured` — with `media_bucket` set and `media_endpoint_url` unset, `img-src` and `connect-src` both contain `https://s3.il-central-1.amazonaws.com` and no other host.
- `test_the_csp_omits_the_media_origin_when_no_bucket_is_configured` — with `media_bucket` unset, `img-src` and `connect-src` are exactly `'self'`. **A deployment with no bucket gets a strictly tighter policy, never a broken one** (D3), and this is the test that says so.
- `test_the_media_origin_is_normalised_to_scheme_host_port` — a `media_endpoint_url` of `http://localhost:9000/` yields the source `http://localhost:9000` with no trailing slash and no path. Parametrised over a trailing slash, a path suffix and a non-default port.
- `test_the_csp_pins_the_directive_set` — the emitted policy parses to exactly the ten directives D3 enumerates, `style-src` carries **no `'unsafe-inline'`**, `frame-ancestors` is `'none'`, `base-uri` is `'none'`, `object-src` is `'none'`, `form-action` is `'self'`.
- `test_the_e2e_fixture_matches_the_emitted_policy` — **this is C2's parity assertion and the whole reason the browser test can be trusted.** Read `frontend/e2e/fixtures/csp.txt`, build the policy from a `Settings` carrying the fixture's own declared bucket/region, and compare **byte-for-byte**. Drift is a red backend test. Precedent: `test_frontend_constant_parity.py`.
- `test_the_security_headers_dict_is_unchanged` — extended: still three headers, and `Content-Security-Policy` is not among them (settings-derived, so it cannot be).

**The change.**

1. `media_csp_origin(settings) -> str | None` — `None` when `media_bucket` is falsy, else `urlsplit(settings.media_endpoint_url or f"https://s3.{settings.media_region}.amazonaws.com")` reduced to scheme + netloc. **Path-style addressing** (`s3.py:73-76`) is why the bucket never appears in the host and why this is one line.
2. `build_csp(settings) -> str` — D3's ten directives, with the media origin appended to `img-src` and `connect-src` when present.
3. `SecurityHeadersMiddleware.__init__(self, app, *, csp: str)`; `main.py:701` becomes `app.add_middleware(SecurityHeadersMiddleware, csp=build_csp(get_settings()))`. Built **at `create_app()` time from `Settings`**, never a module constant — D3's requirement, and what makes the no-bucket case tighter rather than broken.
4. `frontend/e2e/fixtures/csp.txt` — the policy string for the fixture's declared settings, one line, with a header comment naming `test_the_e2e_fixture_matches_the_emitted_policy` as the thing that keeps it honest.
5. **Rewrite the docstring's two stale paragraphs.** `:11-17` — F55 (PR #26) made FastAPI serve both SPAs (`ci.yml:156-161`, `main.py:466/:542/:559/:570`, `test_spa_serving.py:182-186`), so the shells **do** pass through this middleware and `frame-ancestors 'none'` is now the real clickjacking control with `X-Frame-Options: DENY` as the defence-in-depth it was always described as. `:19-24` — both of the CSP paragraph's clauses are false: the pipeline exists (`ci.yml:121-198`) and the artifacts need neither nonce nor hash because there is nothing inline to cover.

- **Verify**: `make test` — the seven new cases green, the seven `SECURITY_HEADERS` importers green **unedited**.
- **Commit**: `feat(security): a settings-derived CSP, and the docstring's two stale claims rewritten`

---

### Task 6 — The CSP against the real bundle, in a real browser (B2, acceptance) · R28
`Frontend/e2e/csp.spec.ts` (**✚**)

**This is B2's acceptance criterion, not the header assertions in Task 5.** `assetsInlineLimit` defaults to 4096, so the day someone imports a small SVG it becomes a `data:` URI in the emitted CSS and `img-src` needs `data:` — a header-string test cannot see that, and a browser can.

**The failing test first.** Written before it can pass, and **capable of reding today**: if the current bundle already contains an inlined `data:` asset, this test reds on its first run — which is the tripwire firing, exactly as designed, and the correct response is to widen the policy by one source with a comment naming the asset, not to weaken the test.

```
test("csp: the storefront bundle raises zero violations under the real policy")
test("csp: the manage shell raises zero violations under the real policy")
```

Each test:

1. Reads the policy from `./fixtures/csp.txt` (the string Task 5's backend test pins).
2. `page.addInitScript` — installs a `securitypolicyviolation` listener on `document` **before any page script runs**, pushing `${e.effectiveDirective} ${e.blockedURI}` into a window array. This is the same instrument discipline as F61's `MutationObserver` finding: the listener must exist before the action, or it observes nothing.
3. `page.route("**/*", …)` — `route.fetch()` then `route.fulfill({ response, headers: { ...response.headers(), "content-security-policy": policy } })`. The `vite preview` server is untouched; the browser receives a real policy on a real document.
4. Navigates, waits for settle.
5. **The anti-vacuity leg, and it is not optional**: assert the app's own root heading is visible. A CSP that blocks the module script leaves a blank page, and a blank page also has zero *further* violations — without this assertion the test passes hardest exactly when the policy is most broken.
6. Asserts the collected violation array is `[]`.

Also collect `page.on("console")` errors and include them in the failure message; a CSP refusal logs to the console with the directive name, which is the fastest read on what to widen.

- **Verify**: `make e2e` — 155 + 2 tests green, axe still at zero violations.
- **Commit**: `test(security): the CSP applied to the real built bundles in Chromium`

---

### Task 7 — Catalog's nine audit rows, `list_tenants`, and the coverage walker (B4) · R38, R12
`Backend/app/catalog/service.py`, `Backend/app/models/constants.py`, `Backend/app/platform/service.py`, `Backend/tests/test_audit_coverage.py` (**✚**), `Backend/tests/test_catalog_audit_db.py` (**✚**), `Backend/tests/test_provisioning.py`

**The failing tests first.** The walker is the red that drives the code, which is why it is written first even though it lands in the same commit.

`test_audit_coverage.py` (fast — it reads the route table and the source, not the database):

- **`test_every_mutating_manage_route_writes_an_audit_row_or_is_exempt`** — walk the live route table with `_leaf_routes`; for every `/manage` route whose method is not `GET`, assert it either reaches an `AuditLogRepository.record` call or appears in `UNAUDITED_BY_DECISION` with a **one-line reason**. **Reds today naming catalog's nine** (C4).
- **`test_the_exemption_list_is_exactly_the_recorded_decisions`** — `UNAUDITED_BY_DECISION`'s keys are exactly `boutique`'s `profile`/`toggles`/appointment-types/availability/terms-creation and `queue`'s check-in, and each reason quotes the shipped comment that recorded it (`boutique/service.py:143`, `queue/manage_router.py:29`). D6's rule: F21 does not reverse two recorded decisions inside a hardening feature; it converts an invisible gap into a reviewed list, and the next unaudited route becomes a test failure.
- Anti-vacuity legs, both: `assert mutating_routes` and `assert mutating_routes >= set(UNAUDITED_BY_DECISION)`.

`test_catalog_audit_db.py` (`db`-marked, run locally) — **one test per mutation, nine of them**, each asserting **exactly one** row with the right `action`, `actor_id` and `entity`; plus:

- **`test_a_no_op_mutation_writes_no_row`** — matching the standing design rule. Spec §Testing requires it and it is the assertion that stops nine audit calls from becoming nine audit calls *and* nine spurious rows on every idempotent retry.

`test_provisioning.py` — extended: `test_listing_tenants_writes_a_platform_audit_row` with the `--operator` name present in the row.

**The change.**

1. Nine `AuditAction` members. **No migration** — `audit_log.action` is plain `TEXT` with no CHECK (`0003_auth.py:71-79`), and D11 records this as the reason F21 ships none.
2. Nine `self._audit.record(session, tenant_id=…, action=…, actor_id=actor.id, entity=…, details=…)` calls in `catalog/service.py`, in the `boutique/service.py:188-195` idiom, **inside the existing `tenant_session`** so the audit row rides the same transaction as the mutation.
3. `platform/service.py::list_tenants` — a `platform_audit_log` row via `PlatformAuditAction`, taking the `operator` that `cli.py:68-69` already parses and currently discards. It is a **full cross-tenant read** and it is the only privileged operation in the CLI that leaves no trail. ⚠ `list_tenants` currently opens a bare `self._session_factory()` (`:203`), not `tenant_session` — the audit write is platform-scoped and belongs in that same bare session, matching `_fail_provision`'s shape (`:245`).

**The details payload carries no personal data.** `_last4`-style discipline (`booking/owner.py:93-96`) applies: a media key, a dress id, a size label. Not a customer name, ever.

- **Verify**: `make test` (the coverage walker) + `bash "<scratchpad>/run-db-tests.sh"` (the ten db cases). Mutation-check: delete **one** of the nine `record` calls and confirm both the walker and that mutation's db test red.
- **Commit**: `feat(audit): catalog's nine mutations and list_tenants, and a walker that fences the rest`

---

### Task 8 — Five pins on properties already true (B5) · R15, R7, R24, R21, D10
`Backend/tests/test_auth_api.py`, `Backend/tests/test_role_guard.py`, `Backend/tests/test_payments_api.py`, `Backend/tests/test_booking_manage_api.py`, `Backend/tests/test_booking_owner_api.py`

Five tests, **each of which must be shown to red on the mutation it guards** before the commit is made. A pin that cannot red is decoration.

| # | Test | File | Assertion | Mutation that must red it |
|---|---|---|---|---|
| 1 | `test_the_session_cookie_is_secure_outside_dev` | `test_auth_api.py` | login with `app_env="staging"` sets `Secure` on `boutique_session`; with `app_env="dev"` it does not. `test_auth_api.py:54` already checks `httponly`, `samesite` and the absence of `domain=` and **stops there** — this is the fourth flag. | make `secure_cookies` return `True` unconditionally (`config.py:243-245`) |
| 2 | `test_the_boot_guard_is_exempt_for_dev_and_for_nothing_else` | `test_role_guard.py` | `ensure_safe_database_role()` calls `verify_database_role` for **every** `app_env` value that is not exactly `"dev"` — parametrised over `staging`, `production` and a bogus `"Dev"`, so a case-folding or `in ("dev","test")` edit reds. R7's deployment half needs a deployment; **this is the half that can be proved here** (D2's parked table says so in as many words). | change the guard to `app_env not in ("dev", "staging")` |
| 3 | `test_no_request_schema_carries_a_card_field` | `test_payments_api.py` | walk every Pydantic request model reachable from the live route table; assert no field name matches `/card|pan|cvv|cvc|expiry|exp_month|exp_year/i`. **Derived from the route table, not a hand list** — R24's audited property is "no PAN on our origin" and it is true *by construction* today; a derivation keeps it true after the next schema. Anti-vacuity: `assert models` and assert the walk saw a known model. | add `card_number: str` to any request DTO |
| 4 | `test_the_manage_token_stays_readable_after_starts_at_and_the_actions_do_not` | `test_booking_manage_api.py` | past `starts_at`: `lookup` still answers **200** with the booking; `confirm_attendance` and `cancel` both refuse. D8's amended R21 text, pinned — the page stays readable **by decision** (`booking/manage.py:9`) and only the actions expire (`:158`, `:195`). | remove the clock check from `cancel` |
| 5 | `test_phone_correction_needs_no_otp_and_admits_both_roles` | `test_booking_owner_api.py` | `POST /manage/bookings/{id}/phone` succeeds for `owner` **and** `shift_manager` with no OTP and no step-up. D10 changes no behaviour; this is the test that makes the next change to it **deliberate**. Its docstring must cite the 2026-07-30 ruling verbatim and must **not** cite `owner-booking-management.md:560`, whose "bounded by the owner-role guard" justification went stale when F31 landed `shift_manager` (D10). | narrow the route to `require_role(StaffRole.OWNER)` |

Tests 1, 4 and 5 touch modules that are `db`-marked; run them locally.

- **Verify**: `make test` + `bash "<scratchpad>/run-db-tests.sh"`. All five mutations performed, observed red, restored.
- **Commit**: `test(security): five pins on properties that were true and unasserted`

---

### Task 9 — A per-IP key on the OTP send budget (B5, the one code change) · R16
`Backend/app/notifications/service.py`, `Backend/app/notifications/router.py`, `Backend/app/auth/router.py` (extract only), `Backend/app/main.py`, `Backend/app/core/config.py`, `Backend/tests/test_notifications_api.py`

**The failing tests first** (fast):

- `test_the_otp_send_budget_meters_the_client_ip_when_one_is_trusted` — with `trust_forwarded_for=True` and an `x-forwarded-for` header, the N+1th send from the same IP with **N different phones** is refused. **Reds today**: there is no per-IP key on the OTP path at all.
- `test_the_otp_send_budget_skips_the_ip_key_when_no_proxy_is_trusted` — with the shipped default (`trust_forwarded_for=False`), the same sequence is **not** refused by the IP budget. This is C5 asserted: the key is inert by default and the row is amber for that reason, not green.
- `test_the_ip_budget_is_its_own_limiter_instance` — exhausting the IP budget does not consume the phone budget, and vice versa.

**⚠ The house rule this task exists to obey**: `max_attempts` lives on the **limiter**, not on the key (`.memory/limiter-max-is-per-instance`, and `booking/service.py:233-236` says it in the code: *"A SEPARATE instance, not a second key on create_limiter"*). So the per-IP budget is a **new `FixedWindowRateLimiter` instance** at `main.py`, beside `phone_limiter` (`:798`) and `tenant_limiter` (`:803`) — never a third key on either.

**The change.**

1. Move `_client_ip` from `auth/router.py:29-39` into a shared module (`app/auth/client_ip.py`) and import it in both routers. **Root cause, not a copy**: two call sites diverging on how the real client IP is derived is exactly the bug class the helper's own comment warns about. `auth/router.py`'s behaviour is unchanged and its existing tests must stay green **unedited** — that is the assertion the extraction is safe.
2. `notifications/router.py:50` — `ip = _client_ip(request, get_settings().trust_forwarded_for)` and pass it into `service.send(tenant.id, body.phone, ip=ip)`. The router already takes `request`.
3. `OtpService.__init__` gains `ip_limiter: FixedWindowRateLimiter`; `send` gains `ip: str | None = None` and, **when `ip is not None`**, checks and spends `f"otp:ip:{ip}"` alongside the existing keys.
   ⚠ **A tripped IP budget must answer like the tripped PHONE budget, not the tenant one** — a silent `return` with the same 204, never a 429. `service.py:225-231` argues why at length: a 429 on this surface is an oracle for "is this number mid-booking at this boutique", and an IP-keyed 429 is the same oracle keyed differently. Getting this wrong is the one way this task can ship a *regression* while making a checklist row look better.
4. Two `Settings` keys with the existing naming: `otp_send_max_per_ip_window` / `otp_send_ip_window_seconds`, sized against `otp_send_max_per_phone_window = 5` — an IP legitimately sends for a household's few phones, not fifty.

- **Verify**: `make test` — the three new cases green, `test_auth_api.py`'s per-IP login cases green **unedited** (the extraction's safety assertion).
- **Commit**: `feat(security): a per-IP budget on the OTP send path, on its own limiter instance`

---

### Task 10 — axe on the eleven unscanned console sections and the board's residual states (B6) · R47
`Frontend/e2e/manage.spec.ts`, `Frontend/e2e/storefront.spec.ts`, `Frontend/e2e/fixtures/manage.ts`

**The failing tests first.** Eleven new `expect(await axeViolations(page)).toEqual([])` assertions, declared as an `AXE_SECTIONS` table in `AXE_ROUTES`' idiom (`storefront.spec.ts:745-763`) so a twelfth section is one row:

```
dashboard · profile · hours · types · terms · catalog · bookings · customers · staff · gateway · privacy
```

Each row is `[label, sectionKey, fixtureState]`, driven through the existing `installManageApi` fixture and an owner session. **`staff` and `privacy` are the two that matter most** (D7): `staff` is where F61's nameless-button defect lived, and `privacy` is the §13 subject-export/erase surface.

⚠ **`installManageApi` stubs the API and its header says so** (`manage.spec.ts:31-33`, *"these prove the CONSOLE and not the CONTRACT"*). These eleven scans inherit that limit exactly. **Do not dilute that banner** to make the new coverage sound broader — the audit artifact (Task 12) records the limitation instead.

**`/queue`'s residual (C1).** Open `QueueBoardPage.tsx`, enumerate its render branches, and diff them against the two shipped journeys (populated + empty). Add a scan **only** for a branch that renders materially different chrome — the truncated/partial-list state and the outage state are the candidates. If the enumeration finds nothing left, **record that** in the A29 line of Task 12's artifact and add no test. A third scan of the same DOM is coverage theatre.

- **Verify**: `make e2e`. Every new scan green. **⚠ If a scan reds, that is a real defect found on a real surface** — fix the component, never `.disableRules()` and never `.exclude()`. The suite has zero of either today (spec, D2 R47) and F21 must not be the feature that introduces the first one.
- **Commit**: `test(a11y): axe on the eleven unscanned console sections`

---

### Task 11 — The live-region sweep F61 named (B6) · R47
`Frontend/apps/manage/src/components/FloorPanel.tsx`, `Frontend/apps/manage/src/components/GuideOverlay.tsx`, and their `__tests__`

F61's own named next sweep, still open: `FloorPanel.tsx:267-275` and `GuideOverlay.tsx:47-51` carry the live-region belief that caused F61's defect #2 — **React skips the DOM text write when a live region re-renders to the same string, so a cue that repeats verbatim is silent.** (`RoomsRegistryDialog.tsx:157-163` was closed *deliberately* since; verified in code, and F61's note is now out of date on that third file. Do not re-fix it.)

**The failing test first**, one per file, and **the instrument is not negotiable**: a `MutationObserver` installed on the live region **before** the action, asserting the region's text node actually changed. That is the only instrument that caught defect #2; `toHaveTextContent` passes on the silent case because the string is right — it just never got written.

**The change**, per file, in this order:

1. Determine whether the region is actually silent on a repeat cue. **If it is**: fix with the nonce+key shape `AtelierSection` already uses.
2. **Whether or not it is**, correct the comment. A comment asserting a belief that F61 disproved is worse than no comment, and correcting it is the deliverable even in the no-fix case.

⚠ **jsdom has no `<dialog>`** (`.memory/jsdom-has-no-dialog`): `setup.ts` stubs `showModal()`. `GuideOverlay` lives in one. **A live-region assertion is about text mutation, not focus, and is valid in vitest** — but any assertion that pre-places focus on the target is vacuous, and that memory records that only 4 of ~30 such assertions were actually vacuous. Do not over-claim; audit before deleting.

- **Verify**: `make fe-test` — the new blocks green, the shipped blocks **unedited**. Mutation: revert the nonce, confirm the `MutationObserver` assertion reds.
- **Commit**: `fix(a11y): the live regions in FloorPanel and GuideOverlay, and the comment that was wrong either way`

---

### Task 12 — `.planning/a11y-audit-v1.md`, the manual pass (B7) · R48, R49
`.planning/a11y-audit-v1.md` (**✚**)

**A written artifact, not a test**, and the only deliverable in F21 that a machine cannot check. It needs no host: `vite preview` serves both built apps locally (`make e2e`'s first half, or `pnpm --filter storefront preview`).

It must contain, per surface: **the surface, the instrument (VoiceOver on macOS, Chromium, macOS 25.5), the date, and the result** — and **record failures as failures**. An audit artifact whose every row passes is the thing this feature exists to distrust.

Surfaces, at minimum: the storefront catalog, a dress detail, the booking flow's four steps, `/b/{token}`, `/checkin`, `/queue`, `/accessibility`, `/privacy`, and the console's login screen plus the three densest sections (`bookings`, `staff`, `privacy`).

Three things it must record beyond the walk:

1. **The WCAG-2.0-only scope decision** (D7 item 5) — `withTags(["wcag2a","wcag2aa"])` is what IS 5568 tracks, so 1.4.10 reflow, 1.4.11 non-text contrast and 2.5.8 target size are **unscanned by choice**. Recorded, because silence in an audit document reads as coverage.
2. **The e2e harness's limits** — `installManageApi` stubs the API, so every console scan proves markup and never the contract (Task 10).
3. **`ar.ts` has no `statement.*` or `a11y.*` section** in the storefront bundle. Arabic is not live for the pilot (pre-decided #47), so this is **recorded, not fixed** — it is F45's.

**Not in this file**: the counsel confirmation of the retention numbers (spec Risk 7). It stays in `user_actions` beside the SMS-body and privacy-default reviews.

R49 is ticked here rather than built: `packages/ui/src/__tests__/tokens.test.ts:33-42, :67-72, :152-164` already computes WCAG 2.0 relative luminance from the token hexes and asserts the published ratios at **rest and on hover**. The artifact cites it; it writes no new contrast code.

- **Done when**: every listed surface has a row with all four fields; the three recorded decisions are present; no row says "passed" without naming what was exercised.
- **Commit**: `docs(planning): the v1 manual keyboard and screen-reader audit`

---

### Task 13 — `.planning/security-checklist-v1.md` becomes an audited document (B8) · all rows
`.planning/security-checklist-v1.md`

**Strictly last of the build tasks.** Every verdict is read off the tree as it now stands, not off this plan.

**D1 first, before any other edit.** Every one of the 32 rows gains an explicit **`R<n>` label whose number is exactly the number it has today** — no renumbering, no reordering. The labels freeze what was accidental: today's numbers are **line numbers from the pre-F20 revision** (row = line for lines ≤ 37, row = line − 7 for lines ≥ 45) and they are cited by number from three other places — `.planning/ppl-compliance-record.md`'s appendix, the checklist's own F20 blockquote, and `Backend/app/security_headers.py:19-24` ("checklist row 33"). Any edit without the labels renumbers everything below it and breaks all three at once, silently.

⚠ `security_headers.py:19-24` is **rewritten by Task 5**, and its "checklist row 33" citation must survive the rewrite as `R33`. Check it here.

Row set, thirty-two:
`R7 R8 R9 R10 R11 R12` · `R15 R16 R17 R18` · `R21` · `R24 R25 R26 R27 R28` · `R31 R32 R33 R34 R35` · `R38 R39 R40 R41 R42 R43 R44` · `R47 R48 R49 R50`

Then, per row: **a verdict, and either the file-and-test that proves it or a named blocker and a named owner.** Nothing else is permitted — a row with a verdict and no evidence is the failure mode the whole feature exists to catch.

| Verdict | Rows |
|---|---|
| **GREEN, already true, evidence is a shipped test** | R8, R10, R11, R17, R18, R35, R39, R41, R43, R49, **R50** |
| **GREEN, closed by F21** | R9 (T3), R12's audit clause (T7), R15 (T8), R24 (T8, text amended), R28 (T5/T6), R33 (T4/T5), R34 (T2), R38 (T7), R47 (T10/T11), R48 (T12) |
| **AMBER, one clause green and one owned by `F62`** | **R7** (code green; the live role is a deployment fact — `walkthrough_coverage_gaps` G1 records the 2026-08-04 run connecting as `postgres` with `rolsuper = t`), **R12** (access restriction is SSH/console access to a host), **R16** (per-IP is code-green and inert until `TRUST_FORWARDED_FOR=true`; distributed limiter is Redis — C5), **R40** (split, below), **R42** (D9) |
| **UNCHECKED, blocker named, owner `F62`** | R26, R27, R31, R32, R44 |
| **Text amended to the shipped reading, then pinned** | R21, R24, R25 (D8) |

**The three amendments, verbatim targets** (D8):

- **R21** — "expire at appointment time" → **"actions (confirm / cancel) expire at appointment time; the page stays readable, by decision (`booking/manage.py:9`)"**, and the ≥128-bit clause corrected **upward**: `auth/tokens.py:4` is `TOKEN_BYTES = 32`, so the tokens are **256-bit**. Pinned by Task 8 #4.
- **R24** — "Grow's hosted page" → **"the configured gateway's hosted page"**. Grow was demoted 2026-07-31; the shipped engine is Lemon Squeezy test mode; production is boot-blocked for both `fake` and `lemonsqueezy` (`core/config.py:303-304, :311-314`). The audited property — no PAN proxied, logged or stored on our origin — is provider-independent and true by construction. Pinned by Task 8 #3.
- **R25** — "replay protection" → **"replay-safe by idempotency"**. Signature verification is real HMAC-SHA256 with `compare_digest` (`payments/lemonsqueezy.py:373-374`) and a redelivery is a proven no-op (`payments/service.py:611-617`, `test_deposit_confirm_db.py::test_a_redelivery_confirms_once_and_texts_once`). What does **not** exist is a timestamp/nonce freshness window, so a captured valid body replays indefinitely — **as a no-op, every time**. Residual: nil for money, non-nil for log noise. Recorded, not papered over.

**R40's split** — the edit F20 explicitly assigned this feature, executed under D1's suffix rule so nothing renumbers:

- **`R40a`** — capture with timestamp + terms-version + source, marketing opt-in separate, unbundled, structurally default-off, and the opt-out writer — **GREEN, F20**.
- **`R40b`** — honored in every marketing send — **OPEN, no subject until a marketing send exists. *Owner: F46.*** F21 does **not** close it.

**R38's amendment** — "data access by operators" reads as the shipped rule (D6): reads **of a data subject** are audited (`privacy/service.py:269, :391, :568, :657`); general console GETs are not, by the standing rule at `dashboard/service.py:373` (*"No GET handler in this product writes one"*).

**The PARKED table becomes the durable source of truth for `F62`.** Every parked row carries its `R<n>` id, its blocker (**the three DNS records at DomainTheNet — `external-applications.md` #2**), its owner (`F62`), and the evidence F21 gathered. This matters beyond tidiness: it is what makes Task 14's PR-body artifact recoverable if the PR body is ever lost.

- **Done when**: all 32 rows carry an `R<n>`; every row has a verdict **and** either evidence or blocker+owner; `grep -c "^- \[" .planning/security-checklist-v1.md` still counts 32 checkboxes plus R40's two clauses; `grep -n "Grow\|expire at appointment time\|replay protection" .planning/security-checklist-v1.md` returns nothing.
- **Commit**: `docs(planning): security-checklist-v1 becomes an audited document — R-ids, verdicts, evidence`

---

### Task 14 — The `F62` queue entry, as a build artifact (B9)
`.planning/plans/hardening-audits-uat.md` (this file, Appendix A) — **and NOT `.planning/LOOP-STATE.md`**

⚠ **This task must not edit `LOOP-STATE.md`.** That file lives on `main`, is written by the loop's own bookkeeping commits, and is edited every iteration. A feature-branch edit to it is a guaranteed merge conflict against the loop's own commits, and resolving that conflict by hand is how a queue entry silently loses a field.

**What F21 produces instead**: the entry's **text**, as a build artifact, in three places with decreasing durability and increasing convenience:

1. **Appendix A of this plan** (below) — committed on the feature branch, greppable, conflict-free.
2. **The PR body**, as a fenced YAML block, which is where the loop's merge bookkeeping reads it from.
3. `scratchpad/f62-queue-entry.yaml`, uncommitted, for paste convenience.

And **the durable fallback is Task 13**: the checklist's PARKED table already carries every parked row with its id, blocker, owner and evidence, in a committed file. If the PR body is lost, `F62` is reconstructible from `.planning/security-checklist-v1.md` alone. That redundancy is free and deliberate.

**The loop applies the entry to `LOOP-STATE.md` on the main side at merge bookkeeping time.** Say so in the PR body, in one line, so the reviewer knows the absence of a LOOP-STATE diff is intentional.

- **Done when**: Appendix A reflects what actually shipped (re-read it after Task 13, not before), and the same text is in the PR body.
- **Commit**: `docs(planning): reconcile the F62 queue entry with what F21 actually shipped` — or `--amend` onto Task 13's commit if nothing changed.

---

## 6. Gate checklist — run in this order, top to bottom, before the PR opens

Commands are from the `Makefile` verbatim. Nothing here is invented.

```
# 0 — baseline, captured on `main` BEFORE Task 1
bash "<scratchpad>/run-db-tests.sh"     # record the count

# 1 — the branch is clean and the pathspecs landed
git show --stat                          # on every commit; `git add Backend/…` silently skips
git diff main -- backend/tests/conftest.py   # MUST BE EMPTY — the db hatch is shipped code
git diff main --stat | grep -c "^ .planning/LOOP-STATE.md"   # MUST BE 0

# 2 — no migration
cd "…/Backend" && uv run python -m alembic heads    # MUST print exactly `0025 (head)`

# 3 — the full local gate
make lint          # ruff check + ruff format --check + mypy app tests scripts
                   #   + pnpm -r lint + pnpm -r typecheck
                   #   + bash frontend/scripts/qa-greps.sh
make test          # backend: pytest -m "not db" -q
bash "<scratchpad>/run-db-tests.sh"      # backend: pytest -m "db and not s3" -q, local PG16
make fe-test       # frontend: pnpm -r --if-present test
make fe-build      # frontend: pnpm -r build
make e2e           # frontend: pnpm -r build && playwright install --with-deps chromium && pnpm e2e

# 4 — the two commands the now-GATING CI job runs. Run them locally or the PR
#     reds on a job that was warn-only when the branch started.
cd "…/Backend" && uv export --locked --no-emit-project -o /tmp/requirements-audit.txt \
  && uvx pip-audit -r /tmp/requirements-audit.txt          # MUST exit 0
cd "…/Frontend" && pnpm audit                              # MUST exit 0

# 5 — qa-greps output byte-identical to the pre-Task-10 baseline
make qa-greps
```

**Green looks like:**

- **`make lint`** — ruff clean, `ruff format --check` clean, **mypy zero errors over `app tests scripts`**, `pnpm -r lint` and `pnpm -r typecheck` clean across all six workspace packages under **oxlint 1.77**, `qa-greps.sh` exit 0 printing exactly the baseline.
- **`make test`** — all fast tests pass, `db`-marked modules collected and deselected. **⚠ two `test_config.py` failures are always false locally** (`Backend/.env` leaks `MEDIA_BUCKET`). Do not chase them.
- **the local db suite** — the captured baseline plus `test_cross_tenant_walker.py`, `test_catalog_audit_db.py` and Task 8's three db-marked pins. `test_media_upload_s3.py`'s cases are excluded (MinIO) — **expected; F21 touches no S3 and those are the only genuine CI debuts in this feature.**
- **`make fe-test`** — **2515** vitest tests (ui 108, storefront 1097, manage 1310) plus Task 11's new blocks, with the shipped blocks unedited. A count that *drops* is a failure.
- **`make fe-build`** — both apps build under Rolldown 1.2.3; no `TS6133` (the unused-import error this feature's test-only edits invite).
- **`make e2e`** — **155** tests plus Task 6's two and Task 10's eleven, **axe at zero violations everywhere**, and **zero `.disableRules()` / `.exclude()` / allow-listed violations anywhere in the suite** — the property D2 R47 cites as its evidence, which F21 must not be the feature to break.
- **CI additionally** — `Dependency audits` is **green and required**, and `deploy-staging` lists `e2e` among its needs. The `brain` job stays `continue-on-error: true` and **will warn about stale pages** for `security_headers.py`, `catalog/service.py`, `platform/service.py` and `notifications/service.py`. That is expected; reconcile with `/brain-sync` after merge, not mid-task.

---

## 7. Risks and responses

| # | Risk | Likelihood | Response |
|---|---|---|---|
| **1** | **The lockfile refresh reds the build.** React, Vite, Rolldown, oxlint and Playwright all move; six manifests change with them. An oxlint minor can add rules; a Rolldown minor can change build output; a Playwright patch can move e2e timing. | **Highest in the feature** | Task 1 is **first and alone** (§3), against a known-good 2515+155 baseline, so a red is unambiguously the bump's. **Concrete fallback if it cannot be made green**: `git revert` the single refresh commit, then land Task 2's gate anyway with **four dated per-advisory waivers** — one `pnpm.auditConfig.ignoreGhsas` entry each for the `undici`, `brace-expansion`, `js-yaml` and `postcss` GHSAs recorded at Task 1's red, each carrying the id, the sentence *"transitive devDependency; not present in the shipped `dist/` runtime"*, the date, and a **90-day expiry**. R34's requirement is that the job gates, not that the tree is finding-free — and this exercises the waiver machinery for real rather than only against the injected fake. Record the fallback in `known_product_bugs` with trigger: the next lockfile touch. |
| **2** | **The CSP breaks the built SPA in a way a header test cannot see.** `assetsInlineLimit` defaults to 4096, so one small imported SVG becomes a `data:` URI in the CSS and `img-src` needs `data:`. Named as a live tripwire, not a hypothetical. | Medium | Task 6's browser test **is** the acceptance criterion, not Task 5's header assertions — and its anti-vacuity leg (assert the root heading rendered) is what stops a fully-blocked blank page from passing. If it reds, widen the policy by **one source with a comment naming the asset**. If it cannot be made green: **rolling back is two clean `git revert`s** (Tasks 5 and 6), Task 4's HSTS survives untouched, and R28 moves to `F62` with the browser evidence attached. A CSP that breaks the app is worse than no CSP. |
| **3** | **The R9 walker finds a genuine cross-tenant isolation hole.** Eight modules have never been probed over HTTP — `auth, staff, boutique, customers, dashboard, privacy, platform, storage` — and `booking` is 0/17 endpoints, `payments` 0/6. | Medium, and **finding one is a success** | **A genuine hole is BLOCKER-class and stops the feature.** It is not a test to relax, not an `UNWALKABLE` entry, and not a follow-up ticket. On discovery: (a) stop; (b) write the minimal failing test that reproduces it outside the walker; (c) surface it to the user as a blocker with the module, the route and the leak shape, because a live cross-tenant read on a multi-tenant pilot is not a build decision; (d) the fix is its own commit with its own test, ahead of every remaining F21 task. The diff expands and that is correct — F21's charter is that a row it *could* prove but did not prove is a lie in an audit document, and a hole it *found* and did not fix is worse. |
| **4** | **`UNWALKABLE` quietly becomes the interesting half.** The genuinely undrivable routes (multipart, webhook signatures, token-authenticated storefront paths) are a real category, and the slope from there to "this one is awkward" is short. | Medium | Task 3's **per-module coverage floor** (`test_no_module_is_wholly_exempt`) is Risk 3's mitigation mechanised: every one of the fourteen modules must contribute ≥1 walked route, and the mutation-check moves a `privacy` route into `UNWALKABLE` to prove the floor reds. Every entry carries a reason string. **If `privacy` or `staff` ends up wholly exempt, R9 is not closed** — spec Risk 3's own acceptance bar. |
| **5** | **A new advisory lands mid-PR and reds the now-gating audit job.** Green today is not green tomorrow. | Low, but certain eventually | The waiver mechanism, used properly: one entry per advisory with id, rationale, date and **expiry**. Never revert to warn-only, never silence wholesale. An expired waiver reds the build **by design**, and Task 2 proves that with the injected fake. |
| **6** | **A registry outage reds the gating audit job.** | Low | **Retry.** Do not add `--ignore-registry-errors`, which turns every outage into a silent pass — the same defect as `continue-on-error` under another name. Stated at D4's operational note and repeated here because it will be tempting at 2am. |
| **7** | **A checklist verdict is written ahead of the code it describes** — the exact failure the Problem statement opens with. | Medium if the ordering slips | Task 13 is **strictly last** and reads the tree, not this plan (§4). Its done-when is mechanical: no row may carry a verdict without either evidence or blocker+owner. |
| **8** | **A `LOOP-STATE.md` edit on the feature branch conflicts with the loop's own commits.** | High if attempted | Task 14 forbids it and says why. The entry text lives in Appendix A + the PR body; the **durable** fallback is Task 13's PARKED table, from which `F62` is fully reconstructible. |
| **9** | **Adding `e2e` to `deploy-staging.needs` lengthens the merge path**, and a flaky Playwright run now blocks a deploy. | Medium | **Accepted** (spec Risk 4): a legal accessibility requirement that does not block a deploy is not a gate. If flake appears, fix the flake — the suite already pauses the 5 s board poll before scanning for exactly this reason (`storefront.spec.ts:2860-2862`) and that is the pattern to copy, not a retry count. |
| **10** | **The audit is a snapshot.** Eleven rows are green because of code that merged in the last three weeks. | Certain | Mitigated by the *shape* of every deliverable: a walker, not a list; a test, not a paragraph. Tasks 3 and 7 both fail on a **new** route, which is the only property that survives the twelfth merge. |
| **11** | **`F62` rots into a wish list.** | Medium | Its blocker is one concrete user action already tracked in `external-applications.md` #2 and re-nagged every iteration, and each row carries the `R<n>` id and the evidence F21 gathered — so whoever picks it up starts from an audited baseline, not from a paragraph. |

---

## 8. Task → file manifest

| Task | New (**✚**) | Modified |
|---|---|---|
| 0 | `.planning/plans/hardening-audits-uat.md` | `.planning/specs/hardening-audits-uat.md` |
| 1 | — | `frontend/pnpm-lock.yaml` + the six `package.json` |
| 2 | — | `.github/workflows/ci.yml`, `frontend/package.json` |
| 3 | `backend/tests/test_cross_tenant_walker.py` | — |
| 4 | `backend/tests/test_security_headers.py` | `backend/app/security_headers.py` |
| 5 | `frontend/e2e/fixtures/csp.txt` | `backend/app/security_headers.py`, `backend/app/main.py`, `backend/tests/test_security_headers.py` |
| 6 | `frontend/e2e/csp.spec.ts` | — |
| 7 | `backend/tests/test_audit_coverage.py`, `backend/tests/test_catalog_audit_db.py` | `backend/app/catalog/service.py`, `backend/app/models/constants.py`, `backend/app/platform/service.py`, `backend/tests/test_provisioning.py` |
| 8 | — | `backend/tests/test_auth_api.py`, `test_role_guard.py`, `test_payments_api.py`, `test_booking_manage_api.py`, `test_booking_owner_api.py` |
| 9 | `backend/app/auth/client_ip.py` | `backend/app/notifications/service.py`, `backend/app/notifications/router.py`, `backend/app/auth/router.py`, `backend/app/main.py`, `backend/app/core/config.py`, `backend/tests/test_notifications_api.py` |
| 10 | — | `frontend/e2e/manage.spec.ts`, `frontend/e2e/storefront.spec.ts`, `frontend/e2e/fixtures/manage.ts` |
| 11 | — | `frontend/apps/manage/src/components/FloorPanel.tsx`, `GuideOverlay.tsx` + their `__tests__` |
| 12 | `.planning/a11y-audit-v1.md` | — |
| 13 | — | `.planning/security-checklist-v1.md` |
| 14 | — | `.planning/plans/hardening-audits-uat.md` |

**Never modified, and that is an assertion, not an accident**: `.planning/LOOP-STATE.md` (Task 14) · `backend/tests/conftest.py` (the db hatch is shipped code) · `backend/migrations/**` (D11, zero migrations) · `frontend/scripts/qa-greps.sh` · `frontend/apps/*/vite.config.ts` (C2 rejected the `preview.headers` route) · `backend/app/booking/owner.py` (D10 changes no behaviour) · `backend/app/boutique/service.py` and `backend/app/queue/manage_router.py` (D6 fences them, does not reverse them) · `backend/app/core/config.py:232` `retention_enabled` (D9 — it stays `False`, and its owner moves to `F62`).

---

## Appendix A — the `F62` queue entry, verbatim

**For the loop to apply to `LOOP-STATE.md` on the main side at merge bookkeeping time. NOT a feature-branch edit** (Task 14).

**Reconciled against what F21 actually shipped**, after Task 13 read the tree. Five
things changed from the draft this appendix carried before the build: `R38` gained
a parked clause the walker *found*; `R7` gained the defence-in-depth finding;
`R48` is here at all, which the plan did not anticipate; the `R9` note records
what the walker proved and what it did not; and the blocker line now distinguishes
the rows gated by DNS from the two that are not.

```yaml
  - id: F62
    slug: production-standup-and-hosted-rows
    epic: E4
    title: "The security-checklist rows that need a deployed host, and the pilot UAT"
    status: parked
    deps: [F21]
    migration: "one — the orphan clock; see R42's precondition below"
    blocker: "the 3 DNS records at DomainTheNet — external-applications.md #2"
    note: >-
      CREATED BY F21. Every row here was AUDITED at F21 against the code and found
      to need a deployed host, a cloud-console action, or a human — nothing here is
      unassessed. Row ids are the frozen R<n> ids from
      .planning/security-checklist-v1.md, which is the evidence document and the
      DURABLE SOURCE OF TRUTH for this entry: if this text is lost, F62 is fully
      reconstructible from that file's PARKED table alone.

      ⚠ NOT EVERYTHING HERE IS GATED BY THE DNS RECORDS. R48's screen-reader walk
      and R38's two scope items need no host and could be done today; they are
      here because they are parked, not because they are blocked on DNS.

      ROWS THIS ENTRY OWNS:
      R7  (deployment clause) — prove the LIVE database role is boutique_app, not
          postgres. walkthrough_coverage_gaps G1: on 2026-08-04 the app connected as
          postgres with rolsuper = t, so everything the runbook lists as binding
          under the app role was SILENTLY VOID for the whole run. The boot guard
          exists (db/session.py:12-42) and is exempt when app_env == "dev"
          (:45-50); F21 pinned that the exemption is dev-only and nothing wider
          (test_role_guard.py, parametrised over staging/production/Dev/DEV).
          ⚠ F21 FINDING, and it raises this row's stakes: the ten
          test_*_isolation.py files do NOT prove defence-in-depth. Under a mutation
          dropping the explicit `tenant_id ==` predicate from a repository method
          they stay GREEN, because they run under RLS too — NOTHING in the suite
          fails if those predicates are removed. What actually guards that layer is
          this boot guard, which makes proving the live role the real control and
          not a formality.
      R9  (nothing owed — recorded so it is not re-litigated) CLOSED at F21.
          test_cross_tenant_walker.py: 105 tenant-scoped routes, 56 driven with
          tenant B's ids, 6 UNWALKABLE with reasons, 43 carrying no tenant-owned id.
          NO CROSS-TENANT HOLE WAS FOUND. Four assertions: 404, no 5xx, no body
          echoes tenant B's ids at any status, and walked ∪ exempt == the route
          table both ways. auth, dashboard, notifications and payments are asserted
          to walk EXACTLY ZERO routes because none carries a tenant-owned id.
      R12 (access-restriction clause) — "access-restricted" means SSH/console access
          to the host. The audit clause CLOSED at F21 (list_tenants writes a
          platform_audit_log row, with the --operator name it used to discard).
      R16 (per-IP enablement + distributed limiter) — F21 SHIPPED the per-IP key on
          OTP send, on its OWN limiter instance, but it is INERT: _client_ip returns
          None unless TRUST_FORWARDED_FOR=true, which is only correct on a
          deployment that terminates exactly one trusted proxy. Set it at stand-up.
          Both arms are pinned (test_notifications_api.py), including the arm that
          asserts the budget does NOT meter with the shipped default — which is why
          the row is amber rather than green. Separately, auth/rate_limit.py:5-6
          names Redis: per-process buckets mean N instances -> N × the budget.
      R26 — per-tenant gateway credentials KMS-encrypted. Only FakeSecretBox ships
          ("THIS IS NOT ENCRYPTION", payments/secretbox.py:61-62). Production is
          boot-blocked (config.py:315-316) and 0012's provider IN ('fake') CHECK
          means production can hold no credential row, so nothing can ship wrong
          meanwhile. F17 Gate 1 Q2 accepted this unchecked.
      R27 — receipt (קבלה) issuance. Zero receipt code exists; refund() has no
          method and no consumer (payments/base.py:106). Waits on the production
          Israeli PSP (external-applications.md #3).
      R31 — secrets in AWS Secrets Manager. core/config.py:11 reads .env; zero hits
          for secretsmanager|vault|ssm in app/.
      R32 (WAF clause) — AWS/Cloudflare console action against a live origin. The
          rate-limiting clause is discharged: ~20 separate limiter instances at
          main.py:731-961.
      R38 (two scope items, NEITHER blocked on DNS) —
          (a) PUT /manage/privacy writes NO AUDIT ROW, and F21's audit-coverage
              walker FOUND this rather than confirming it: no decision to that
              effect existed anywhere in the tree. Same class as boutique's
              profile/toggles (the tenant editing its own text), so it is recorded
              in UNAUDITED_BY_DECISION with that reasoning rather than closed —
              D6 scopes F21's new rows to catalog + list_tenants and a hardening
              feature does not widen its own charter. Decide it deliberately here.
          (b) audit_log has NO READ SURFACE — zero routers touch AuditLogRepository,
              so detecting the accepted F15 phone-correction risk is a manual DB
              query nobody is prompted to run. Its own spec.
          The catalog half CLOSED at F21: nine mutating routes, nine audit rows,
          nine AuditAction members, and a walker that makes the next unaudited
          route a test failure (twelve reviewed exemptions, each with a reason).
      R42 — retention jobs RUNNING. retention_enabled stays False until row 44's
          restore drill. ⚠ PRECONDITION, from F21's audit and
          ppl-compliance-record.md:58 — BEFORE RETENTION_ENABLED is ever set: the
          30-day orphan grace runs from created_at, because nothing on the row
          records when a customer BECAME orphaned. It therefore protects a row
          created in the last 30 days and nothing else, and a phone correction that
          orphans a customer who first booked six months ago satisfies the conjunct
          IMMEDIATELY. F15's correction re-points the OTHER row and never touches
          this one (booking/owner.py:1136-1161), so updated_at will not serve as a
          proxy either. A real orphan clock is a NEW COLUMN and it belongs to
          whoever flips the flag — that is this entry, and it is this entry's one
          migration.
      R44 — backups automated, restore drilled, RPO/RTO written. Gates R42.
      R48 (screen-reader clause) — ⚠ NOT ANTICIPATED BY F21'S PLAN, which expected
          this row to close green. It did not. F21 RAN the keyboard half for real
          (18 surfaces, 261 tab stops, real Chromium against the real built
          bundles; zero defects; skip link, dialog focus trap, Escape and focus
          RESTORATION all verified) and marked the screen-reader half NOT RUN,
          because no screen reader was operated and an audit document that claims
          coverage it does not have is worse than one that says "not run".
          NEEDS A HUMAN WITH VOICEOVER, NOT A HOST — do it whenever.
          .planning/a11y-audit-v1.md §4 lists the ten surfaces (booking flow first,
          console privacy first of the three console sections) and the two
          questions only a listener can answer: does /queue's 5-second poll
          interrupt speech, and do the booking step transitions announce.
      Production stand-up: compute, prod wildcard DNS/TLS, prod Postgres.
      Terraform-izing docs/infra-runbook.md.
      Pilot onboarding with real Hebrew content + UAT sign-off.

      ONE RESIDUAL F21 RECORDED THAT IS NOT A CHECKLIST ROW (D10):
      the owner-SMS throttle key is booking:owner_sms:{tenant_id} — PER TENANT,
      not per actor, so one staffer can spend the whole boutique's budget.
      Filed in known_product_bugs; listed here because the fix and R38(b)'s audit
      read surface land in the same place.
```

**Where this text lives, in decreasing durability**: this appendix (committed on
the feature branch, greppable, conflict-free) · the PR body as a fenced YAML block,
which is where the loop's merge bookkeeping reads it from · and
`scratchpad/f62-queue-entry.yaml`, uncommitted, for paste convenience. **The
durable fallback is `.planning/security-checklist-v1.md`'s PARKED table**, from
which every row above is reconstructible.

**`.planning/LOOP-STATE.md` is deliberately untouched on this branch** — the loop
owns that file on `main` and a feature-branch edit is a guaranteed conflict with
the loop's own bookkeeping commits. Say so in one line in the PR body so the
reviewer knows the absent diff is intentional.

---

## 9. What this plan does NOT change from the spec

D1 (the `R<n>` freeze and the suffix rule) · D2's mechanical IN-SCOPE / PARKED split · D3's CSP directive set, its `frame-ancestors 'none'` argument, its no-`preload` HSTS rule and its "never inside `SECURITY_HEADERS`" constraint · D4's decision to gate the **full** audit rather than `--prod`, and the waiver shape · D5's one-walker-not-95-tests principle · D6's audit-catalog-and-fence-the-rest · D7's ten surfaces, its WCAG-2.0-only scope decision and the `e2e`-in-the-deploy-gate line · D8's three amendments and the R40 split · D9 (`retention_enabled` stays `False`, R42's owner moves to `F62`, the orphan-clock column goes with it) · D10 (re-derived, no behaviour change, one pinning test, two recorded residuals) · D11 (zero migrations) · every Out-of-scope item.

**Amended by drift, each argued in §1**: D7 item 1 (`/queue` is already scanned twice — C1) · §Testing's B2 bullet (the harness serves `vite preview`, so the instrument changes — C2) · D7 item 2's count (fifteen sections, four scanned, eleven to close — C3) · D2/D6/B4's endpoint count (nine mutating of eleven — C4) · D2's R16 verdict (AMBER, not green; per-IP enablement joins the distributed limiter on `F62` — C5) · D3's arithmetic (seven files, not eight — C6).
