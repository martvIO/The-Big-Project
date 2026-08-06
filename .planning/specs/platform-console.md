# Spec: Feature 25 — Web platform console, replaces v1 CLI (Epic E5)

**Created**: 2026-08-06 · **Status**: **Gate 1: standing approval — interview-2026-07-30.md §Standing approvals** (Q1: F25 touches neither payments, refunds, privacy-law text nor billing — it self-approves; the named exceptions are F17/F18/F19/F20/F29/F48). **Operator auth is the platform's highest-privilege surface: the build's dual review (Q49) treats D2–D4 adversarially — brute force, session theft, host confusion, audit bypass — not as a form.**
**Depends on**: F6 (the CLI + `ProvisioningService`), F5 (staff auth patterns), F4 (reserved slugs / tenant resolver) · **Feeds**: F26 (invite-code signup builds ON this console's service layer)
**Pre-decided**: #20 (the CLI's audited command layer becomes the console's service layer; same four operations; no console-only powers; CLI retired at parity)

---

## Problem

Tenant lifecycle runs over SSH: `python -m app.cli provision|suspend|list|reset-password`. That was the whole v1 provisioning surface by design (F6), and it cannot onboard 50+ tenants — every operation needs a shell on the host and a person who knows the flags. F25 puts the same audited operations behind a web console. F26's invite-code redemption then reuses the exact service layer this feature exposes.

## Goal

An operator signs in at `admin.modryn.co.il` with email + password, sees the tenant table, provisions a boutique (slug, name, owner email, initial owner password), suspends one, and resets an owner password — each action writing the same `platform_audit_log` row the CLI writes today, under the same INSERT-only grant, running as the same `boutique_app` role. The four lifecycle subcommands are then deleted from the CLI. Hebrew-first RTL, `ar` keys untranslated, no exclamation marks, axe zero-violation.

## Conflicts between the brief and shipped reality (recorded, codebase-consistent reading taken)

1. **#20: "the CLI is deleted at parity"** — the CLI has since grown commands that are NOT in #20's parity set: `backfill-booking-links` (F16's one-time deploy step, not yet run in production — production is F62-parked) and `retention` (F20's `--armed` rehearsal design, deliberately shell-ergonomic; R12's closed reading says "access-restricted" *means* SSH on the host). Deleting `app/cli.py` wholesale would orphan both. Reading taken: **parity = the four lifecycle operations; those four subcommands are deleted; the CLI file survives as the maintenance surface** (backfill, retention, and the new `create-operator` bootstrap). No fork of the audit layer — everything still calls `ProvisioningService` / the audited repositories.
2. **F21 R18: "operator password reset via audited CLI only — no HTTP reset route exists"** was verified as a control. F25 supersedes it **by design**: the reset moves to an authenticated, rate-limited, audited HTTP route on the console host. The obligation R18 protected (audited, operator-identified, no tenant-facing route) carries over intact; the F21 citation rows referencing "no HTTP reset route" are updated at build.
3. **`test_audit_coverage.py` comment: "`platform_audit_log` … has no HTTP route at all, so it is out of this walk"** — false after F25. The console's mutating routes reach `self._audit.record(...)` through `ProvisioningService`, which the walker's delegation-following already detects; the module comment is updated and the new routes enter its accounting.
4. **Standing rule "no GET handler writes a row" (`dashboard/service.py:373`) vs `TENANTS_LISTED`** — F21 D6 made `list_tenants` the one audited read (a full cross-tenant enumeration). The console's `GET /platform/tenants` calls that same method, so a GET now writes a row over HTTP. Recorded exception, same shape as F21's: the standing rule governs tenant staff reading their own boutique; this is the platform enumeration row R12 demanded, carried from shell to HTTP verbatim.
5. **e5-growth F25 brief says size M; LOOP-STATE queued it, this run sized it L** — the third workspace app + the operator auth surface are why. No scope change, just honesty.

## What already exists to build on (verified against code)

- **The audited command layer IS already a service layer.** `app/platform/service.py::ProvisioningService(session_factory)` — `provision` / `suspend` / `list_tenants` / `reset_owner_password` (+ `backfill_booking_links`, `run_retention`), returning result dataclasses (`CommandResult`, `TenantSummary`), never raising for business failures (failure audits must commit — the F5 lesson). `app/cli.py` is already a thin argparse dispatcher over a `ProvisioningLike` protocol. **Pre-decided #20's refactor is therefore almost nothing: a new HTTP router in front of the same class.**
- **Audit**: `platform_audit_log` (0004) is INSERT-only for `app_user` (`REVOKE ALL` then `GRANT INSERT` — 0002's default privileges would otherwise leave full CRUD). `PlatformAuditLogRepository.record` already generates `id` and `created_at` client-side so the INSERT emits **no RETURNING** (which would need SELECT). `action` is unconstrained TEXT — new `PlatformAuditAction` members need **no migration**. Column is `target_tenant_id`, never `tenant_id` (dodges the forced-RLS metadata scan).
- **Role reality**: `cli.py` calls `ensure_safe_database_role()` — outside dev it refuses superuser/BYPASSRLS/table-owner roles, i.e. the CLI already runs lifecycle ops as `boutique_app`, and `test_provisioning.py` runs RLS-real as that role. 0002 grants CRUD on ALL tables to `app_user` (incl. `tenants`, `staff_users`); provisioning inserts inside `tenant_session(tenant_id)`. **The console's API needs no new DB role, no SECURITY DEFINER, no privilege change** — the web process already holds exactly the privileges the operations use. (docs/real-world-qa.md §2.1 running `app.cli` with the owner URL is a local-dev convenience under `APP_ENV=dev`, not a privilege requirement; it gets updated per conflict 1.)
- **Staff auth to mirror** (`app/auth/`): argon2 (`hash_password`/`verify_password` + `verify_password_dummy` timing equalizer), `generate_session_token`/`hash_token` (sha256-stored), `sessions` table pattern, host-only HttpOnly SameSite=Lax cookie, failures-only `FixedWindowRateLimiter` per-instance (per-(scope,email) key + inert per-IP arm behind `trust_forwarded_for`), `get_current_staff` dependency, login/failed audits committed inside the transaction.
- **Routing**: `TenantResolutionMiddleware` runs on every request except exact `EXEMPT_PATHS`; reserved slugs (`admin` ∈ `RESERVED_SLUGS`, enforced at request AND provision time) and the apex both get the one `TENANT_NOT_FOUND` 404 body. `csrf.py` protects `PROTECTED_PREFIX = "/manage"` only. `security_headers.py` is host-agnostic (CSP/HSTS ride free).
- **SPA serving** (`main.py`, pinned by `test_spa_serving.py`): built apps copied to `app/static/{manage,storefront}`; manage builds with `base: "/manage/"`, exact-path index at `/manage`, assets mount, storefront catch-all that **declines** reserved segments (`_RESERVED_SEGMENTS = {manage, storefront}`); missing bundles = API-only boot.
- **Workspace**: pnpm apps `storefront` + `manage`, packages `ui` + `api-client`, `e2e` member; Makefile/`ci` use `pnpm -r` (a third app rides free for lint/type/build); `e2e/playwright.config.ts` boots one `vite preview` webServer per app (4173/4174).
- **No operator identity exists anywhere web-facing** — grepped `platform_operator|operator_session`: nothing. `--operator` is a free-text CLI flag defaulting to `$USER`.
- **Migrations**: 0001–0025 merged; **F22 holds 0026 in a live worktree; F24 (queued next) takes the head after that** — F25 numbers its migration **head+1 at build time** and renumbers at rebase (parallel-alembic-numbering rule).

## Scope

**IN**
- `platform_operators` + `platform_sessions` tables; `create-operator` CLI bootstrap command.
- Operator login/logout/me on the console host; session cookie; rate limiting; login audits.
- Console host routing: `admin.{base_domain}` branch in the tenancy middleware, both directions fenced.
- HTTP endpoints for provision / suspend / list / reset owner password, calling `ProvisioningService` unchanged.
- Third workspace app `apps/platform` (login → tenant table → provision form → row actions), served at `/platform`.
- Deletion of the four lifecycle subcommands from `app/cli.py` at parity (same feature, last task); docs/seed_demo pointers updated.

**OUT**
- Invite-code signup — **F26**, which builds ON this console's service layer (its redemption path calls the same `ProvisioningService.provision`).
- Billing/metering — F48. Toggle matrix — F27.
- Any tenant-staff-facing surface; `/manage` and the storefront are untouched.
- Un-suspend/restore — F6 said "add when needed"; #20 says no console-only powers. First real suspension-reversal request owns it (service method + CLI-parity question dies with the CLI, so it lands console-first then).
- Operator self-service (password change, multi-operator management UI) — creation/deactivation stay CLI-side; one operator is the v1 posture.
- TOTP/2FA — recorded risk, see D6.
- Retention/backfill screens — they stay CLI (conflict 1).

## Design

### D1 — Hosting: the console lives at `admin.{base_domain}`, fenced both ways in the tenancy middleware

- New setting `platform_host_label: str = "admin"`. `"admin"` is already in `RESERVED_SLUGS` (request-time and provision-time), so the console host can never collide with a tenant; a boot-time assert pins `platform_host_label in RESERVED_SLUGS`.
- `TenantResolutionMiddleware` gains one branch: when `extract_slug(host)` equals the label → **no tenant resolution**; only paths matching `/platform` or `/platform/*` (plus the existing exact `EXEMPT_PATHS`) proceed with `request.state.platform_host = True`; **everything else on the console host returns the house `TENANT_NOT_FOUND` 404** — the storefront shell, `/manage`, and every tenant API are unreachable there. Conversely, on tenant hosts `/platform*` returns the same 404: the console does not exist on tenant hosts. One place, one body, no oracle in either direction.
- Why a subdomain, not the apex: the apex deliberately 404s (F4's anti-enumeration posture) and re-opening it re-litigates that; a reserved label is covered by the **existing wildcard DNS + wildcard cert** (`*.modryn.co.il`) — zero new external work, which matters because production DNS is still F62-parked. Why `admin` and not a new label: it is already reserved, already un-provisionable, and self-describing.
- The path prefix `/platform` joins `_RESERVED_SEGMENTS` so the storefront catch-all declines it.

### D2 — Operator identity: `platform_operators`, seeded by CLI, no self-signup

- Platform-scoped table (like `platform_audit_log`: **no `tenant_id` column** → outside the forced-RLS scan by construction, no RLS): standard `id/created_at/updated_at/deleted_at` block + `email TEXT NOT NULL`, `password_hash TEXT NOT NULL`, `display_name TEXT NOT NULL`. Partial unique index on `lower(email) WHERE deleted_at IS NULL`. Soft delete = deactivation (bites on next request — session resolution re-reads the row, mirroring `RoleGate`'s property).
- **Created only by `python -m app.cli create-operator --email …`** — password via stdin/getpass (never argv, F6's rule), `--operator required=True` (the retention precedent: bootstrap of the highest-privilege credential is not a `$USER`-default act), argon2 hash, audit `OPERATOR_CREATED`. Duplicate active email → failure result, non-zero exit. **No HTTP route creates or edits operators** — the console's own compromise cannot mint operators.
- Deactivation: `deactivate-operator` CLI subcommand (soft delete + revoke sessions + audit `OPERATOR_DEACTIVATED`). Refuses to deactivate the last active operator.

### D3 — Sessions: `platform_sessions` + `boutique_platform_session` cookie

- Table: standard block + `operator_id UUID NOT NULL`, `token_hash TEXT NOT NULL`, `expires_at TIMESTAMPTZ NOT NULL`; partial indexes on `(token_hash)` and `(operator_id)` `WHERE deleted_at IS NULL`. No `tenant_id`, no RLS. Never widen `sessions` (its `tenant_id`/`staff_user_id` are NOT NULL and staff/operator auth must not share a lookup path — the F24 `customer_sessions` precedent).
- Cookie `boutique_platform_session`: its **own name** (defence in depth — host-only scoping to `admin.{base}` already isolates it from every tenant host, but a distinct name means a leaked/misconfigured Domain attribute still cannot be resolved by staff or customer lookups), HttpOnly, Secure (prod), SameSite=Lax, path=/.
- TTL: new setting `platform_session_ttl_seconds`, **default 4h** — deliberately tighter than staff 12h: highest privilege, lowest login frequency, and re-login costs one password entry (no SMS bill, unlike the customer portal's 30d rationale). Fixed expiry, no sliding renewal.
- Dependency `get_current_operator(request)`: requires `request.state.platform_host` (belt — the middleware fence is the braces), cookie → `hash_token` → live row (`deleted_at IS NULL`, `expires_at > now()`) → re-read operator row (deactivation bites immediately) → `OperatorContext(id, email, display_name)`; failure raises the existing `NotAuthenticatedError` (house 401 body).
- CSRF: `csrf.py` `PROTECTED_PREFIX` becomes a tuple `("/manage", "/platform")` — every mutating `/platform` request gets the Origin-vs-Host check.

### D4 — Login: the staff pattern, keyed for one global scope, everything audited

`POST /platform/auth/login {email, password}`, mirroring `auth/router.py::login` exactly, with these substitutions:
- **Limiter**: a NEW `FixedWindowRateLimiter` instance on app state (`platform_login_rate_limiter` — its own instance, never a key on an existing budget: the per-instance rule `main.py` states five times). Keys: `e:{email}` (always) + `ip:{ip}` when `trust_forwarded_for` yields one (inherits R16's inert arm and its CGNAT caveat unchanged). Settings `platform_login_max_attempts: int = 5`, `platform_login_window_seconds: int = 900`. Failures-only recording; success resets the email key.
- **Timing**: unknown email does `verify_password_dummy` work — no operator-enumeration timing leak (the login response is a generic 401 either way).
- **Audit**: success writes `OPERATOR_LOGIN`, failure `OPERATOR_LOGIN_FAILED` (details: the attempted email) — into `platform_audit_log`, committed with the transaction (compute-then-raise outside it, the F5 lesson). New enum members only; TEXT action, no migration. This is stricter than staff (whose audits live in the per-tenant `audit_log`); the platform's front door logs to the platform's book.
- `POST /platform/auth/logout` (revoke by token hash, clear cookie) · `GET /platform/auth/me` → `{email, display_name}` (the SPA's bootstrap; 401 renders the login panel).

### D5 — The command layer becomes the service layer: a router, not a rewrite

New `app/platform/router.py` (`APIRouter(prefix="/platform")`), every handler `Depends(get_current_operator)`, delegating to the **unchanged** `ProvisioningService` with `operator=ctx.email` — the free-text `operator` column now carries an authenticated identity instead of `$USER`:

| CLI command (F6) | Endpoint | Console screen/action | Audit action (unchanged) |
|---|---|---|---|
| `provision` | `POST /platform/tenants/provision` `{slug, name, owner_email, owner_password}` | "בוטיק חדש" form | `TENANT_PROVISIONED` / `TENANT_PROVISION_FAILED` |
| `suspend` | `POST /platform/tenants/suspend` `{slug}` | row action + confirm dialog | `TENANT_SUSPENDED` |
| `list` | `GET /platform/tenants` | the tenant table (slug, name, status, created_at) | `TENANTS_LISTED` (conflict 4) |
| `reset-password` | `POST /platform/tenants/reset-owner-password` `{slug, owner_email, new_password}` | row action + dialog | `OWNER_PASSWORD_RESET` |
| `backfill-booking-links` | — stays CLI (one-time deploy step) | — | `BOOKING_LINKS_BACKFILLED` |
| `retention` | — stays CLI (conflict 1, R12 posture, `--armed` ergonomics) | — | `RETENTION_RUN` |

- Business failures surface as the service returns them: `CommandResult(ok=False, message=…)` maps to the house error body with code = the message (`invalid_or_reserved_slug`, `slug_taken`, `empty_password`, `tenant_not_found`, `owner_not_found`) at 409/404/400 as appropriate — **the failure audit rows keep committing** exactly as on the CLI, because the service, not the router, owns them.
- Initial owner password is typed by the operator and POSTed over TLS — the same trust shape as the CLI's stdin (the operator hands it to the boutique owner out of band, as `staff` management already does: "יש למסור את הסיסמה לעובדת בעצמך"). No invite emails — that machinery is F26's.
- **Parity, then deletion (same feature)**: once the db-marked suite proves the four endpoints write the same audits under `boutique_app`, the four subcommands + their `ProvisioningLike` protocol entries are deleted from `app/cli.py`; `test_cli.py` shrinks to the surviving commands; `docs/real-world-qa.md` §2/§3 and `scripts/seed_demo.py`'s printed instructions re-point provisioning at the console (dev: `create-operator` then the UI, or direct `ProvisioningService` in scripts).

### D6 — TOTP/2FA: out of scope, recorded as a risk with named compensating controls

No TOTP in F25: it is a new dependency + enrolment/recovery-code surface, and the threat it answers (phished/stuffed password) is materially blunted here because **the credential is CLI-seeded (never chosen on a web form), unique to this system, argon2-hashed, un-enumerable (timing-equalized generic 401), rate-limited, and the account list is not reachable over HTTP**. Compensating controls: 4h sessions, one operator, every success/failure audited, host fenced. **Recorded risk**: a stolen operator password is full platform control until noticed; revisit alongside F62's production stand-up (which owns the WAF/IP-allowlist clause R32 — an IP allowlist on `admin.{base}` at the edge is the cheaper, stronger sibling of TOTP and belongs to the infra layer).

### D7 — Data model (one migration, head+1 at build time)

Raw-SQL migration in the house style, numbered **head+1 when the branch cuts** (F22 holds 0026 live; F24 may hold the next by then — renumber at rebase, never squat a taken number):

```sql
CREATE TABLE platform_operators (
  -- standard block: id uuid_generate_v4() PK, created_at, updated_at (trigger), deleted_at
  email         TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  display_name  TEXT NOT NULL
);
CREATE UNIQUE INDEX idx_platform_operators_email_unique
  ON platform_operators (lower(email)) WHERE deleted_at IS NULL;

CREATE TABLE platform_sessions (
  -- standard block
  operator_id UUID NOT NULL,          -- no FK, house rule; validated in app
  token_hash  TEXT NOT NULL,
  expires_at  TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_platform_sessions_token    ON platform_sessions (token_hash)  WHERE deleted_at IS NULL;
CREATE INDEX idx_platform_sessions_operator ON platform_sessions (operator_id) WHERE deleted_at IS NULL;
```

- **No `tenant_id` on either table** — platform-scoped, outside the forced-RLS scan, no RLS, no `enable_tenant_rls`. 0002's default privileges give `app_user` CRUD (correct: login SELECTs, CLI INSERTs, logout/deactivation UPDATEs — all as the app role).
- `platform_audit_log` is **untouched**: INSERT-only grant honoured because every writer goes through `PlatformAuditLogRepository.record` (client-generated `id`/`created_at`, flush emits no RETURNING).

### D8 — Frontend: a third workspace app, `apps/platform`

**Decision: a separate app, not a route-space in `apps/manage`.** Rationale: manage is tenant-staff-facing — served per-tenant host, bootstrapped off `/manage/auth/me`, its bundle ships to every boutique's staff; folding the operator surface in would ship operator screens+strings to tenants, entangle two cookie/auth bootstraps in one shell, and put the platform's highest-privilege UI behind a tenant host. The workspace cost is small and enumerable: `package.json`, `vite.config.ts` (`base: "/platform/"`, dev proxy `/platform` → :8000, `--host 127.0.0.1`), `vitest.config.ts`, `tsconfig.json`, `.oxlintrc` wiring — all copied from manage; `pnpm -r` picks it up in lint/type/build/CI with zero Makefile or workflow edits.

- **Shape**: copy the manage app's no-client-router pattern — `App.tsx` bootstraps `GET /platform/auth/me`; 401 → login panel; 200 → one screen: tenant table + "בוטיק חדש" form + per-row actions (suspend with confirm dialog — destructive red on the final confirm only, the manage precedent; reset owner password dialog). Server refusals map to their own Hebrew sentences by error code (`slug_taken`, `invalid_or_reserved_slug`, `owner_not_found`, …) — codes are the contract, never a generic sentence.
- **i18n**: `he.ts` + `ar.ts` (untranslated, Q3/#47), **zero exclamation marks** (#5). Reuse `packages/ui` tokens/components as they fit; this is an internal tool but carries the same axe zero-violation bar (IS 5568 posture is program-wide — pre-decided #38's reading).
- **Serving**: `_register_spas` gains the platform triple mirroring manage exactly — `/platform/assets` mount, public-files mount, exact-path index at `/platform`; deploy job copies `apps/platform/dist` → `app/static/platform`. Missing bundle = API-only boot, unchanged.
- **e2e**: third `webServer` entry (`pnpm --filter platform preview --port 4175`, url `/platform/`), new `fixtures/platform.ts` interception harness (manage.ts style — fulfils `/platform/auth/me` etc.; it proves the console, not the contract) + `platform.spec.ts`.

## Audit contract (the obligation, stated once)

Every mutating console action writes exactly the `platform_audit_log` row its CLI ancestor wrote, plus the new auth actions — always with the authenticated operator's email in `operator`, always through `PlatformAuditLogRepository.record` (INSERT-only-safe: client-side `id`/`created_at`, no RETURNING), failure audits committing on their own transactions. New `PlatformAuditAction` members: `OPERATOR_CREATED`, `OPERATOR_DEACTIVATED`, `OPERATOR_LOGIN`, `OPERATOR_LOGIN_FAILED` — TEXT action column, **no migration**. `details` never carries passwords or hashes.

## Test plan

- **Fast lane (unit)**: middleware fence matrix (console host × {`/platform`, `/manage`, `/`, `/storefront/*`, `/health`} and tenant host × `/platform*` → exact expected bodies); `get_current_operator` (no cookie / bad token / expired / deactivated / not-platform-host); login limiter keys and reset; CLI `create-operator`/`deactivate-operator` dispatch with a fake service, password via stdin; parser no longer knows the four deleted subcommands.
- **db-marked (RLS/role reality)**: the whole console lifecycle **as `boutique_app`** — create-operator → HTTP login → provision → the owner then logs in via `AuthService` (F6's end-to-end, now through HTTP) → suspend → reset-password → each writes its platform_audit_log row (asserted via an owner-role connection, since the app role cannot SELECT it — the existing `test_provisioning.py` technique); failed login writes `OPERATOR_LOGIN_FAILED` and 401 stays generic; limiter 429 after budget; session expiry honoured; deactivated operator's live session refused; duplicate active operator email refused; reserved-slug and duplicate-slug provisioning refusals return their codes AND commit failure audits; last-operator deactivation refused.
- **Walkers (registration is the task)**: `test_cross_tenant_walker` — `/platform/*` routes carry no tenant-owned ids; register them so `walked ∪ exempt == route table` keeps holding both ways; `test_staff_role_gating` — assert a staff `boutique_session` cookie is worthless on `/platform/*` (401, by cookie name and host fence); `test_audit_coverage` — mutating `/platform` routes resolve to `_audit.record` through delegation, comment updated (conflict 3); `test_spa_serving` — `/platform` shell + assets on the static tree, catch-all declines `/platform`; `test_middleware`/`test_slugs` — the label branch; security headers ride free but one console response is asserted anyway.
- **e2e (Playwright + axe, `Frontend/e2e/platform.spec.ts`, interception fixtures)**: login journey (bad password → Hebrew error, no exclamation; good → table); provision form happy path + `slug_taken` + reserved-slug mapped sentences; suspend confirm dialog (red on final confirm only) flips the row status; reset-password dialog; logout returns to login; **axe zero-violation** on login, table, provision form, both dialogs; RTL rendering.

## Traps (for the plan)

- Migration number is **head+1 at build time** (F22 → 0026 live, F24 next in queue) — renumber at rebase (`.memory/parallel-alembic-numbering`).
- `git add` pathspecs lowercase (`backend/…`, `frontend/…`); reads capitalized.
- Never key the console login onto an existing limiter instance; never add `/platform` paths to `EXEMPT_PATHS` (the fence lives in the label branch, exemption would open the routes on every host).
- The audit repository's no-RETURNING property is load-bearing — any new audit write goes through `record`, never `session.add(PlatformAuditLog(...))` with server defaults.
- Vite dev server: bind `--host 127.0.0.1` (IPv6-only trap, `.memory/vite-dev-binds-ipv6-only`).
- Deleting the four subcommands: sweep `docs/real-world-qa.md`, `scripts/seed_demo.py`'s printed help, and `.brain` references — a doc that still says `app.cli provision` sends the next QA run to a dead command.
- e2e third webServer: CI builds all apps first (`pnpm -r build`) — already true via Makefile `e2e` target.

## Decisions log

| # | Decision | Basis |
|---|---|---|
| D1 | Console at `admin.{base}`; middleware label branch fences both directions with the house 404 | wildcard DNS/cert already covers it; apex 404 posture untouched; `admin` already un-provisionable |
| D2 | `platform_operators`, CLI-seeded, no HTTP creation, no self-signup | the console's compromise must not mint operators; F26 keeps signup invite-only anyway (Q10) |
| D3 | Own table + own cookie name, 4h fixed TTL | staff/customer precedent: auth populations never share a lookup path; highest privilege → tightest TTL |
| D4 | Staff-login mirror: dummy-verify timing, failures-only new limiter, success+failure platform audits | shipped, reviewed pattern; platform front door logs to the platform book |
| D5 | `ProvisioningService` unchanged; new router passes `operator=ctx.email`; four CLI subcommands deleted at parity, CLI survives for maintenance | pre-decided #20 + conflict 1 |
| D6 | No TOTP now; risk recorded; edge IP-allowlist named as F62's stronger sibling | credential is unphishable-by-form, un-enumerable, rate-limited; scope honesty |
| D7 | Two platform-scoped tables, no `tenant_id`, no RLS; audit table untouched | the F6 `target_tenant_id` lesson; INSERT-only grant honoured by construction |
| D8 | Third workspace app `apps/platform`, manage-shaped, base `/platform/` | operator UI must not ship in a tenant-served bundle; `pnpm -r` makes the cost one directory |

## Open questions (non-blocking)

- Un-suspend: first suspension that needs reversing owns it (console + service method); recorded here so it is not re-litigated as "missing parity".
- Whether F62's production stand-up puts an edge IP allowlist in front of `admin.{base}` (R32's WAF clause) — infra-layer, decided there; D6's risk note points at it.
- Operator password rotation (self-service change) — CLI `reset` via `create-operator`-style subcommand is the stopgap; a console form is a small follow-up if a second operator ever exists.
