# Spec: Feature 21 — Hardening, audits & pilot UAT (Epic E4)

**Created**: 2026-08-05 · **Status**: **Gate 1: standing approval — `interview-2026-07-30.md` §Standing approvals.** Q1's stop-list is enumerated (F17, F18, F19, F20, F29, F48) and F21 is not on it. F21 writes no consumer-facing money copy and no privacy-law text: it *audits* the money and legal surfaces F17–F20 already shipped and, where a row is red, closes it with a middleware or a test. The one place it touches legal text is `.planning/security-checklist-v1.md` itself, which is an internal audit artifact, not a public document. · **Epic**: E4 (`.planning/epics/e4-deposits-and-hardening.md`, Feature 21) · **Effort**: **L**
**Depends on**: F16, F15, F20 — all merged. Also reads, but does not modify, F55 (the SPAs are served by FastAPI, which is what makes the CSP row cheap) and F61 (the a11y walkthrough batch, which already closed six of the defects this feature would otherwise inherit).
**Feeds**: the pilot. **And one new parked queue entry, `F62`**, which carries every row that needs a live host — see *The split* and *Out of scope*.

**Migration position rule.** Resolve any alembic revision id from `alembic heads` on `main` immediately before the rebase that precedes the push — never from a number written in a planning document. `heads` reads `0025` today (`0025_walk_in_bookings.py`). **F21 ships NO migration**, and D9 argues why the one column that looked like it might be needed is not F21's to add. If that conclusion ever changes, the rule above is the one that applies.

---

## Problem

`.planning/security-checklist-v1.md` is the v1 ship gate. It has **32 rows**. Three are checked. Twenty-nine are not, and nobody has established which of those twenty-nine are *unmet* versus merely *unaudited* — which is a different and much smaller problem than the file's appearance suggests.

That distinction is the whole feature. This audit found that **eleven unchecked rows are already true in shipped code** and have been for weeks; that **six are genuinely red and closable with no deployed host**; and that **nine cannot be closed at all until a production environment exists**, which waits on three DNS records the user has not yet added (`external-applications.md` #2). Two more are F20's amber rows with named owners, and one of those owners is this feature.

A checklist row this feature *could* prove but does not prove is a lie in an audit document. So is a row marked green on the strength of a planning note. Both failure modes are live here: the brief for this feature asserts the accessibility statement page "does not exist yet", and it has been shipped, routed, footer-linked, axe-scanned and unit-tested since F10.

**And the checklist itself is fragile in a way that will corrupt the audit.** Its rows are cited by number in three other documents — `.planning/ppl-compliance-record.md`'s appendix, F20's blockquote inside the checklist, and `Backend/app/security_headers.py:19-24` ("checklist row 33"). Those numbers are **line numbers from the revision that existed before F20 inserted its seven-line blockquote**: for lines ≤ 37 the row number is the line number, and for lines ≥ 45 it is the line number minus 7. F20's own instruction to this feature — "splitting rows 40 and 42 into their per-owner clauses is F21's edit" — would, executed naively, renumber every row below it and silently invalidate every existing citation. D1 fixes that before anything else.

---

## Goal

`.planning/security-checklist-v1.md` becomes an **audited document**: every one of its 32 rows carries a stable id, a verdict, and either the file-and-test that proves it or a named blocker and a named owner. F21 closes every row that can be closed without a deployed host, and hands the rest to one new parked queue entry whose blocker is the domain.

**F21 ships: one middleware change (two headers), one CI change (three lines), one route-walker isolation test, audit rows on the one module that had none, six small pins on properties that are already true, axe coverage for the ten unscanned surfaces, two written audit artifacts, a rewritten checklist, and a new parked queue entry. Zero migrations, zero new product surface, zero new Hebrew in front of a member of the public.**

---

## What already exists to build on (verified against code)

Everything in this section was opened and read. It is here because it changes the size of the feature.

- **RLS is real, forced, and mechanically swept.** `Backend/app/db/rls.py:16-19` emits `ENABLE`, `FORCE ROW LEVEL SECURITY` and a `tenant_isolation` policy keyed to `current_setting('app.tenant_id', true)::uuid` on every tenant table (`0003:85`, `0005:119,128`, `0006:135`, `0007:87`, `0008:109`, `0010:100`, `0012:152`, `0018:100`, `0019:201`, `0020:129`, `0022:138`). `test_tenant_isolation.py::test_every_tenant_id_table_has_forced_rls` fails on any table that grows a `tenant_id` column without `relforcerowsecurity`, so this cannot rot. The `missing_ok := true` at `rls.py:14` is what makes an unset context a NULL predicate rather than an open door.
- **The app refuses to boot on an RLS-bypassing role.** `Backend/app/db/session.py:12-42` rejects `rolsuper`, `rolbypassrls` *and* table ownership, and `ensure_safe_database_role()` (`:45-50`) is called from all three entrypoints — `main.py:586`, `worker.py:181`, `cli.py:184`. The test suite provisions a real non-owner `boutique_app` role for exactly this reason (`Backend/tests/conftest.py:26-30`: "the container superuser bypasses RLS unconditionally, which would make every isolation assertion vacuously pass").
- **Security headers already ship and are already tested on eight surfaces.** `Backend/app/security_headers.py` sets `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, registered LAST in `create_app()` (`main.py:701`) so it is outermost and covers the `TENANT_NOT_FOUND` 404 that `TenantResolutionMiddleware` returns without reaching a handler. Eight test files import `SECURITY_HEADERS` and compare the response headers to it with `==`.
- **The built SPAs contain nothing a CSP has to negotiate with.** Read from the actual `dist/` artifacts, not the sources: both `index.html` files carry exactly one external `<script type="module">` and one external `<link rel="stylesheet">`, **zero inline `<script>`, zero inline `<style>`, zero `data:`, zero `blob:`**. Vite emitted no modulepreload polyfill. Fonts are self-hosted `@fontsource` woff/woff2 under `/assets` (`theme.css:1-10`). The only `https://` strings in either bundle are user-initiated `target="_blank"` navigations (instagram, wa.me, waze) and XML namespace URIs. There is no analytics, no tag manager, no CDN, no runtime Google Fonts, no payment iframe.
- **The accessibility statement is shipped product.** `Frontend/apps/storefront/src/routes/AccessibilityPage.tsx` (182 lines), route `/accessibility` (`router.tsx:31, :52, :80, :132, :363`), footer link on every route via `A11yStatementLink` (`StorefrontLayout.tsx:154`), Hebrew copy at `he.ts:712+`, unit tests in `__tests__/accessibility.test.tsx` (316 lines), **and it is axe-scanned twice** — rows 4 and 9 of `AXE_ROUTES`. Its header comment cites **IS 5568 §35** by name, and it enforces the §35 rule that a `<dt>` is never rendered without a reachable value.
- **`/privacy` is the clone, not the precedent.** `PrivacyPage.tsx:9-11` says in its own header that it was written the way the accessibility statement is written. The direction in the brief is reversed.
- **The axe pass is gating and has no escape hatches.** Seven spec files, all `new AxeBuilder({page}).withTags(["wcag2a","wcag2aa"])`, **zero `.disableRules()`, zero `.exclude()`, zero allow-listed violations**, every assertion a hard `expect(violations).toEqual([])`. `AXE_ROUTES` lives at `Frontend/e2e/storefront.spec.ts:745-763` (not, as the brief assumes, an env var). Bespoke axe journeys additionally cover the whole booking flow, `/b/{token}`, `/checkin`, `/q/{id}`, and two A11yMenu states.
- **Contrast is already computed in CI, not eyeballed.** `Frontend/packages/ui/src/__tests__/tokens.test.ts:33-42` implements WCAG 2.0 relative luminance from the token hexes and asserts the corrected AA values, the published ratios (ink/bg 15.24, gold-strong/white 3.93), and the primary CTA at **rest and on hover** (`:157-164` — "the state a tap leaves latched on mobile"). `qa-greps.sh:42` bans raw hex in storefront source; `:40` bans physical direction utilities.
- **Upload validation is three layers deep and tested against real MinIO.** Server-side type+size before presign (`catalog/validation.py:149-157`), an S3 POST policy with an **exact** `content-length-range` and a pinned key (`storage/s3.py:125-134`), and a post-upload `head_object` + magic-byte check that deletes a polyglot (`catalog/service.py:596-622`). Plus a DB CHECK at 2× the app cap.
- **Tokens are 256-bit, not 128.** `auth/tokens.py:4` `TOKEN_BYTES = 32` → `secrets.token_urlsafe(32)`, stored as sha256 hex only, compared with `hmac.compare_digest` (`booking/tokens.py:36`).
- **The audit-log table needs no migration to grow actions.** `audit_log.action` is plain `TEXT` with no CHECK (`0003_auth.py:71-79`); `AuditAction` already carries members added on exactly that basis.
- **`pip-audit` is clean today.** Run against `uv export --locked` on 2026-08-05: *"No known vulnerabilities found."*

---

## Where the planning documents and the code disagree

Five conflicts. The codebase-consistent reading is taken in every case, per the interview's own rule.

| # | The document says | The code says | Taken as |
|---|---|---|---|
| 1 | The brief for this feature: the accessibility statement page "does not exist yet — verify". | `AccessibilityPage.tsx` is 182 lines of shipped product with a route, a footer link on every page, Hebrew copy, 316 lines of unit tests and **two** axe scans. It predates F20. | **Row 50 is already true.** F21 ticks it with evidence and builds no page. This is the single largest scope reduction in the feature. |
| 2 | `Backend/app/security_headers.py:11-14`: "The framable document is `index.html`, served by Vite in dev and by a static host in production — neither passes through this middleware." | F55 (PR #26) made FastAPI serve both SPAs. `ci.yml:156-161` copies both `dist/` trees into `backend/app/static/`; `main.py:466, :542, :559, :570` mounts and serves them; `test_spa_serving.py:182-186` already asserts `SECURITY_HEADERS` on the manage shell. | **Stale.** The shells *do* pass through the middleware and already carry `X-Frame-Options: DENY`. The docstring is rewritten in D3. |
| 3 | Same docstring, `:22-23`: "A CSP for a Vite bundle needs a nonce or hash story authored against a deployed artifact, and there is no frontend deploy pipeline to author it against yet." | Both clauses are false. The pipeline exists (`ci.yml:121-198`). The artifacts need **neither** nonce nor hash: there is nothing inline to cover. | **Stale.** CSP moves from "deferred project" to "four lines and a test". D3. |
| 4 | Checklist row 21: manage tokens "expire at appointment time". | `Backend/app/booking/manage.py:9`, as a documented decision: "The page stays READABLE after `starts_at`; only the ACTIONS expire." Only `confirm_attendance` (`:158`) and `cancel` (`:195`) check the clock. `lookup` (`:140-142`) has no time bound and there is no `expires_at` column. | **The row overstates the shipped design.** D8 amends the row text to the shipped reading and pins it, rather than changing a deliberate product decision inside a hardening feature. |
| 5 | Checklist row 24: "Card entry exclusively on **Grow's** hosted page". | Grow was demoted to one candidate on 2026-07-31; the shipped engine is Lemon Squeezy test mode, and production is boot-blocked for both `fake` and `lemonsqueezy` (`core/config.py:303-304, :311-314`). | **Row names a provider that is no longer the engine.** D8 rewrites the row provider-agnostically — the property being audited is "no PAN on our origin", which is provider-independent and currently **true by construction**. |

---

## Design

### D1 — Stable row ids, applied before anything else

Rows are cited by number in `.planning/ppl-compliance-record.md`'s appendix, in the checklist's own F20 blockquote, and in `Backend/app/security_headers.py:19-24`. Those numbers are **line numbers from the pre-F20 revision**: row = line for lines ≤ 37, row = line − 7 for lines ≥ 45. Any edit to the file — including the split F20 explicitly assigned to this feature — renumbers everything below it and breaks all three citation sites at once, silently.

**Every row gains an explicit `R<n>` label whose number is exactly the number it has today.** No renumbering, no renaming, no reordering; the labels freeze what was accidental. New rows created by a split take a suffix (`R40a` / `R40b`), never a new integer, so the sequence can never shift again.

The full row set, which is the vocabulary for the rest of this spec:

`R7 R8 R9 R10 R11 R12` (tenant isolation) · `R15 R16 R17 R18` (sessions & auth) · `R21` (tokens) · `R24 R25 R26 R27 R28` (payments) · `R31 R32 R33 R34 R35` (platform hardening) · `R38 R39 R40 R41 R42 R43 R44` (data protection) · `R47 R48 R49 R50` (accessibility). Thirty-two rows.

### D2 — The split, row by row

This is the feature's spine and the reason it does not park as a whole. The rule is mechanical: **a row is IN SCOPE if it can be proved on a CI runner and in this repository with no host and no cloud-console action.** Everything else is PARKED, with the blocker named.

**ALREADY TRUE — F21 ticks it, and the deliverable is the test that pins it, not new code (11 rows).**

| Row | Proof (file) | Proof (test) |
|---|---|---|
| **R7** RLS FORCEd, non-owner app role, `app.tenant_id` policies | `db/rls.py:16-19`; role at `0002_tenants_app_role.py:63`; boot guard `db/session.py:12-42` | `test_tenant_isolation.py::test_every_tenant_id_table_has_forced_rls`, `::test_app_role_is_not_superuser_or_table_owner`, `::test_force_rls_is_enabled_on_probe`; `test_role_guard.py` (3 tests). **Deployment half is R7's parked clause — see below.** |
| **R8** Unset context → zero rows | `db/rls.py:14` (`missing_ok := true`) | `test_tenant_isolation.py::test_no_context_means_zero_rows`, `::test_garbage_context_fails_loudly_not_open` |
| **R10** Tenant host-derived only | `tenancy/middleware.py:69, :74, :88-92`; no `tenant_id` in any request schema | `test_middleware.py::test_known_slug_resolves_and_binds_tenant`, `::test_failure_kinds_are_indistinguishable`; `test_catalog_isolation.py:459` |
| **R11** S3 keys tenant-prefixed, short-lived signed URLs | `catalog/keys.py:32`; TTL 300 s presign / 900 s GET (`catalog/validation.py:80-82`) | `test_media_upload_s3.py::test_rewriting_the_key_to_another_tenant_prefix_is_rejected`, `::test_posting_after_the_policy_expires_is_rejected`, `::test_signed_get_downloads_the_object_and_then_expires` |
| **R17** OTP before customer creation | `booking/service.py:316-322` (step 1, before anything is written) | `test_booking_service.py::test_unproven_phone_is_rejected_and_writes_nothing` |
| **R18** Operator password reset via audited CLI only | `cli.py:63-66, :169-172` → `platform/service.py:211-241`, audit at `:234`; **no HTTP reset route exists** | `test_cli.py::test_password_is_not_a_cli_argument`; `test_provisioning.py::test_reset_password_changes_credentials`, `::test_each_state_change_writes_platform_audit` |
| **R24** No PAN on our origin | zero card fields anywhere in `app/`; redirect-only (`payments/base.py:76-79`) | **gap — B5 adds the pin.** Row text also amended (D8). |
| **R35** Upload validation | three layers, `catalog/validation.py:149-157` + `storage/s3.py:125-134` + `catalog/service.py:596-622` | `test_media_upload_s3.py` — four rejection tests + `::test_confirm_deletes_an_honest_size_polyglot`, against real MinIO |
| **R47** axe-core on storefront + booking flow | `Frontend/e2e/storefront.spec.ts:745-763` + 6 bespoke journeys | the gating `Frontend E2E (Playwright + axe)` job. **Coverage gaps closed by B6.** |
| **R49** Contrast audit | `theme.css:21-94` tokens | `packages/ui/src/__tests__/tokens.test.ts:67-72, :152-164` — real WCAG 2.0 luminance math, rest **and** hover |
| **R50** Accessibility statement published | `AccessibilityPage.tsx`, route + footer link + Hebrew | `__tests__/accessibility.test.tsx`; `AXE_ROUTES` rows 4 and 9 |

**IN SCOPE, RED — F21 builds these (7 rows).**

| Row | What is actually missing | Build |
|---|---|---|
| **R9** CI cross-tenant isolation suite | 66 tests across 10 files, but only **~7 of 103 tenant-scoped endpoints** are ever probed over HTTP as tenant A against tenant B, and **eight modules have no isolation file at all** — auth, staff, boutique (12 endpoints), customers, dashboard, privacy (5 endpoints incl. subject-export/erase), platform, storage. booking is 0/17 endpoints, payments 0/6, floor 12/23. | B3 |
| **R12** Provisioning CLI audit-logged | `platform/service.py:202-209` — **`list_tenants` writes no audit row**, and it is a full cross-tenant read taking an `--operator` flag that goes nowhere (`cli.py:68-69`). Access restriction has no code meaning at all; `--operator` defaults to `$USER`. | B4 (audit row) + parked clause (access restriction is a host fact) |
| **R15** Cookie flags | `auth/cookies.py:10-18` is correct — `httponly`, `samesite="lax"`, **no `domain=` at all** so the cookie is host-only. But `secure` is `app_env != "dev"` (`config.py:243-245`) and **no test asserts it**. `test_auth_api.py:54` checks httponly, samesite and the absence of `domain=`, and stops there. | B5 |
| **R16** Rate limits per phone **and per IP** | Per-phone ✓ (5/3600 s send, 10/300 s verify), per-tenant ✓, OTP TTL 300 s ✓ single-use ✓. **Per-IP does not exist on the OTP path at all**, and on login it is conditional on `trust_forwarded_for`, which defaults `False` (`config.py:37`). | B5 (per-IP OTP key) + parked clause (distributed limiter) |
| **R28** CSP forbids third-party scripts on our origin | No CSP anywhere — no header, no `<meta http-equiv>`. | B2 |
| **R33** HSTS + CSP | XFO, nosniff and Referrer-Policy ship and are tested. HSTS and CSP are absent. | B2 |
| **R34** Dependency scanning green in CI | The `audit` job is `continue-on-error: true` (`ci.yml:223`). | B1 |
| **R38** Audit log on all owner mutations | **`app/catalog/` has zero `AuditLogRepository` usage** — all 11 endpoints (dress create/update/delete/restore, variants, media presign/confirm/delete/reorder) leave no trail. `boutique/service.py:143` says outright "`profile` and `toggles` stay UNAUDITED"; appointment types, availability rules/exceptions and terms creation write nothing. `app/queue/` writes nothing (`queue/manage_router.py:29` acknowledges it). | B4 |

R21 is red-adjacent and handled by D8 rather than by code.

**PARKED — new queue entry `F62`, blocker: the three DNS records at DomainTheNet (`external-applications.md` #2), and where noted a second cloud-console action (9 rows + the epic's unowned infra scope).**

| Row / item | Why it cannot be closed here |
|---|---|
| **R7 (deployment clause)** — the *live* database role is `boutique_app`, not `postgres` | `walkthrough_coverage_gaps` **G1**: on 2026-08-04 the app connected as `postgres` with `rolsuper = t`, so *"everything the runbook lists as binding under the app role was SILENTLY VOID for the whole run"*. The boot guard exists but is exempt when `app_env == "dev"` (`db/session.py:47`). Proving a deployment's role needs a deployment. **B5 adds what *can* be proved here: that the guard is not exempt for any non-`dev` env value.** |
| **R12 (access-restriction clause)** | "Access-restricted" means SSH/console access to the host. No host. |
| **R16 (distributed limiter clause)** | `auth/rate_limit.py:5-6`, verbatim: *"Sufficient for a single-instance pilot; distributed limiting (Redis) is the Feature 21 hardening gate."* Redis is an infrastructure resource. Per-process buckets mean N instances → N × the budget. |
| **R26** Per-tenant gateway credentials KMS-encrypted | The only adapter shipped is `FakeSecretBox`, base64 of JSON, whose own comment says *"THIS IS NOT ENCRYPTION"* (`payments/secretbox.py:61-62`). `gateway_secret_box` is `Literal["fake"] | None`. A KMS key is an AWS console/CLI action. Production is boot-blocked (`config.py:315-316`) and `0012`'s `provider IN ('fake')` CHECK means production can hold no credential row, so nothing can ship wrong in the meantime. **F17 Gate 1 Q2 already accepted this unchecked.** |
| **R27** Receipt (קבלה) issuance | Zero receipt code exists; `refund()` has no method and no consumer (`payments/base.py:106`). Both wait on the production Israeli PSP (`external-applications.md` #3). |
| **R31** Secrets in AWS Secrets Manager | `core/config.py:11` reads `.env`. Zero hits for `secretsmanager|vault|ssm` in `app/`. Migrating secrets requires a production environment to migrate them into. |
| **R32 (WAF clause)** | AWS/Cloudflare console action against a live origin. |
| **R42** Retention jobs *running* | D9. |
| **R44** Backups automated, restore drilled, RPO/RTO written | A drill needs something to restore. |
| Production stand-up: compute, prod wildcard DNS/TLS, prod Postgres | The epic folded this into Feature 21. It is the definition of a host item. |
| Terraform-izing the F2 infra runbook (`docs/infra-runbook.md`) | Terraform against no account state is an unverifiable plan. |
| Pilot onboarding with real Hebrew content + UAT sign-off | A pilot boutique cannot use a URL that does not resolve. |

### D3 — Two headers, and neither one needs the domain

The two absences the docstring blames on the domain are separable, and **both** can be closed today. The docstring's reasoning is rewritten along with the code.

**CSP.** The blocker the docstring names — "a nonce or hash story authored against a deployed artifact" — does not exist, because the deployed artifact has nothing inline. What the policy must accommodate is exactly one thing that is *not* self: the media bucket, which serves dress photos over presigned GET (`img-src`) and receives presigned POST uploads via `fetch(presign.url, {method:"POST"})` from `apps/manage/src/api.ts:315` (`connect-src`). The bucket host is derived from `media_bucket` + `media_region` + `media_endpoint_url`, all settings — so **the policy is built at `create_app()` time from `Settings`, not written as a constant**, and a deployment with no bucket gets a strictly tighter policy rather than a broken one.

```
default-src 'self';
script-src 'self';
style-src 'self';
img-src 'self' <media-origin>;
font-src 'self';
connect-src 'self' <media-origin>;
form-action 'self';
frame-ancestors 'none';
base-uri 'none';
object-src 'none'
```

`frame-ancestors 'none'` is what actually stops clickjacking on the shells; `X-Frame-Options: DENY` stays as the defense-in-depth it was always described as. `form-action 'self'` and `base-uri 'none'` are free and close the two injection shapes a `default-src` does not. **`style-src` gets no `'unsafe-inline'`** — the build emits an external stylesheet and Tailwind v4 compiles at build time; if that ever changes the CSP reds in e2e, which is the correct place for it to red.

⚠ **`assetsInlineLimit` defaults to 4096**, so the day someone imports a small SVG it becomes a `data:` URI in the CSS and `img-src` needs `data:`. That is a live tripwire, not a hypothetical, and it is why B2's acceptance criterion is a real browser loading the real bundle with the real policy — not a header-string assertion.

**HSTS.** The docstring says HSTS "needs the real domain and a TLS-termination decision". It needs neither. A browser applies an HSTS header **only to the host that sent it** (and, with `includeSubDomains`, that host's subtree) — it can never reach a sibling of a shared parent, so emitting it from `*.up.railway.app` is safe. And a browser ignores HSTS over plain HTTP anyway. So the rule is one condition, not a config flag:

> Emit `Strict-Transport-Security: max-age=31536000; includeSubDomains` when the effective request scheme is https (`request.url.scheme`, honouring `x-forwarded-proto` as Railway sets it). No `preload` — preload submission is effectively irreversible and is a decision for a domain that resolves.

**Mechanically, `SECURITY_HEADERS` must stay exactly what it is.** Eight test files do `assert {h: resp.headers.get(h) for h in SECURITY_HEADERS} == SECURITY_HEADERS`, which is only meaningful for headers that are unconditional and constant. CSP is settings-derived and HSTS is request-derived, so **neither joins that dict**; they are emitted alongside it by the same middleware and get their own tests. This is the smallest change that adds two headers without touching eight files.

### D4 — Dependency scanning: gate the FULL audit, and the reason is measured

The `audit` job is `continue-on-error: true` and the comment at `ci.yml:220-221` names this feature as the trigger to flip it. Flipping a chronically-red job to gating reds every build unless the findings are actually resolved. So the findings were run before choosing a shape.

**Measured on 2026-08-05, on this tree:**

| Command | Result |
|---|---|
| `pip-audit` against `uv export --locked` | **clean** — "No known vulnerabilities found" |
| `pnpm audit --prod` | **clean** — "No known vulnerabilities found" |
| `pnpm audit` (full tree) | **9 findings** — 4 high, 5 moderate |

All nine are transitive **devDependencies**, and each is exactly one patch release behind:

| Package | In lockfile | Patched | Reached via |
|---|---|---|---|
| `undici` (5 advisories) | 7.28.0 | ≥ 7.29.0 | `apps__manage > jsdom > undici` |
| `brace-expansion` (2) | 2.1.2 | ≥ 2.1.4 | `packages__api-client > openapi-typescript > @redocly/openapi-core > minimatch > brace-expansion` |
| `js-yaml` (1) | 4.2.0 | ≥ 4.3.0 | `… > @redocly/openapi-core > js-yaml` |
| `postcss` (1) | 8.5.21 | ≥ 8.5.23 | `apps__manage > vite > postcss` |

**The decision is to gate the FULL audit, not `--prod`.** `--prod` would be green today for free, and would be a permanent blind spot over exactly the packages that assemble the bundle: a compromised `vite`, `rolldown` or `postcss` ships to production inside `dist/` while never appearing in a production dependency tree. Auditing the toolchain that builds the artifact is the point, not an accident of the tool's defaults.

**That gate is achievable today, and this was measured rather than assumed.** `pnpm update -r --depth Infinity --lockfile-only` lifts all four to patched versions that sit **inside the ranges the manifests already declare** — so **no `pnpm.overrides` and no range *widening* are needed**. Both the lockfile and the manifests were restored to `HEAD` after the check.

**The refresh is not free, and the plan must budget for three separate costs.**

1. **It moves ~16 other locked packages**, including **React 19.2.7 → 19.2.8, Vite 8.1.5 → 8.2.0, Rolldown 1.1.5 → 1.2.3, oxlint 1.74.0 → 1.77.0, Playwright 1.62.0 → 1.62.1**, and re-resolves the vitest/vite peer graph. An oxlint minor can add rules; a rolldown minor can change build output; a Playwright patch can move e2e timing.
2. **It also rewrites the declared ranges in all six `package.json` files** — this is pnpm's default behaviour, not an accident of the flags, and it was observed: `react ^19.2.7 → ^19.2.8`, `vite ^8.1.1 → ^8.2.0`, `oxlint ^1.71.0 → ^1.77.0`, `typescript ^5.7.0 → ^5.9.3`, `@vitejs/plugin-react ^6.0.3 → ^6.0.5`, `@types/react ^19.2.17 → ^19.2.18`. Those are floor bumps, not widenings, and they are a reviewable diff — **but the plan must expect a six-manifest change, not a lockfile-only one.** If that is unwanted, the escape is `--no-save`, at the cost of leaving the manifests describing a floor the lockfile no longer sits on.
3. **The whole gate re-runs after the refresh, and any breakage is this feature's to fix.**

A narrower `pnpm update … undici postcss js-yaml brace-expansion` was also measured and is strictly worse: identical churn, and it leaves `js-yaml` at 4.2.0.

**Waiver mechanism, because green today is not green tomorrow.** The day an advisory lands with no patched version, the job must not be reverted to warn-only and must not be silenced wholesale. Each waived advisory gets its own entry — pnpm's `pnpm.auditConfig.ignoreGhsas` in `frontend/package.json`, `pip-audit --ignore-vuln` for the backend — carrying **the GHSA/PYSEC id, one sentence of why it does not reach this product, the date, and an expiry date**. An expired waiver reds the build. A waiver with no rationale is the thing this row exists to prevent.

One operational note the plan must not discover in CI: `pnpm audit` needs the registry. A registry outage reds a gating job. That is correct — retry, do not add `--ignore-registry-errors`, which would turn every outage into a silent pass.

### D5 — R9: one walker, not ninety-five tests

Row 9's text is "every repository method + API endpoint probed as tenant A against tenant B's data". Ninety-five hand-written endpoint tests would satisfy it on the day they are written and rot on the next merge. The repository already has the right pattern: `test_staff_role_gating.py`'s walker reads `allowed_roles` off the **live** route table, so a route added later is policy-checked with no new test.

**F21 writes one `test_cross_tenant_walker.py` on the same principle**: enumerate the live FastAPI route table, and for every tenant-scoped route, drive it as an authenticated principal of tenant A while every id in the path, query and body belongs to tenant B — asserting 404 (never 200, never 403-that-leaks-existence, never 500). Routes it cannot drive generically go in an explicit, commented `UNWALKABLE` set with a per-route reason, and a second test asserts the union of walked and exempted **is** the route table — so a new route is a test failure, not a silent gap.

The existing ten `test_*_isolation.py` files stay. They probe repository methods below HTTP, which the walker cannot reach, and row 9 names both halves.

### D6 — R38: close catalog, then fence the rest with a reviewed list

`app/catalog/` is the one owner-facing mutation module with **zero** audit rows, and it is the module whose writes are publicly visible. It gets `_audit(...)` on its eleven mutating paths plus new `AuditAction` members — **no migration**, because `audit_log.action` is unconstrained `TEXT`. `platform/service.py::list_tenants` gets a `platform_audit_log` row: it is a cross-tenant read that already takes an operator name and discards it.

`boutique`'s `profile`/`toggles`/appointment-types/availability/terms and `queue`'s check-in are judgement calls, and both modules record their omission deliberately (`boutique/service.py:143`, `queue/manage_router.py:29`). Rather than reverse two recorded decisions inside a hardening feature, **F21 adds a walker with an explicit exemption list**: every mutating `/manage` route either writes an audit row or appears in `UNAUDITED_BY_DECISION` with a one-line reason. That converts an invisible coverage gap into a reviewed decision, which is what an audit document actually needs, and it makes the next unaudited route a test failure.

"Data access by operators" is amended to the shipped reading (D8): reads **of a data subject** are audited (`privacy/service.py:269, :391, :568, :657`); general console GETs are not, by the standing rule at `dashboard/service.py:373` ("No GET handler in this product writes one").

### D7 — R47/R48/R49: what is left is ten surfaces and two written artifacts

F61 (PR #47) closed six a11y defects five days ago and its LOOP-STATE entry records the tests that red if each fix is reverted. **None of them are re-specced here.** What the audit found still open:

1. **`/queue` — the public wall board — has zero axe coverage.** It is in the overflow sweep and the 200%-text sweep but has no `AXE_ROUTES` row and no bespoke journey. `.planning/specs/public-queue-board.md:776` carries acceptance criterion **A29** ("zero axe violations on every materially different state") as an unchecked box that was never satisfied. It is public, unauthenticated and wall-mounted.
2. **Nine of sixteen console sections have no axe scan**: `dashboard, profile, hours, types, terms, catalog, bookings, customers, staff, gateway, privacy`. Two matter most — `staff`, which is where F61's nameless-button defect lived, and `privacy`, which is the §13 subject-export/erase surface.
3. **F61's own named next sweep is still open**: `FloorPanel.tsx:267-275` and `GuideOverlay.tsx:47-51` carry the live-region belief that caused defect #2. (`RoomsRegistryDialog.tsx:157-163` has since been closed *deliberately* rather than by accident — verified in code, and the F61 note is now out of date on that third file.)
4. **Row 48, the manual keyboard + screen-reader spot check, has never been run** and needs no host: `vite preview` serves both built apps locally. It produces a written artifact, `.planning/a11y-audit-v1.md`, listing surface, instrument (VoiceOver on macOS), and per-surface result.
5. **WCAG 2.1/2.2 tags are not enabled** — so 1.4.10 reflow, 1.4.11 non-text contrast and 2.5.8 target size are unscanned. **This stays as it is**: IS 5568 tracks WCAG 2.0 AA, which is what `withTags(["wcag2a","wcag2aa"])` scans. But it is recorded as a deliberate scope decision in the audit artifact rather than left silent, because silence in an audit document reads as coverage.
6. `ar.ts` has no `statement.*` or `a11y.*` section in the storefront bundle. Arabic is not live for the pilot (pre-decided #47), so this is **recorded, not fixed** — it is F45's.

**`e2e` is not in `deploy-staging`'s `needs`** (`ci.yml:124` reads `needs: [backend, frontend]`). An a11y regression therefore does not block a deploy to main. One-line fix, and it belongs in a feature whose subject is a legal accessibility requirement.

### D8 — Three rows whose text is wrong, and the rule for amending them

A hardening feature must not change deliberate product behaviour to make a checklist sentence true. Where the sentence and the shipped design disagree and **the shipped design is the reasoned one**, the sentence is amended and the design is pinned by a test. Where the sentence is right, the code changes. Three rows fall in the first bucket:

- **R21** — "expire at appointment time" → **"actions (confirm / cancel) expire at appointment time; the page stays readable, by decision (`booking/manage.py:9`)"**, plus the ≥128-bit clause corrected upward: the tokens are 256-bit. B5 pins that `lookup` after `starts_at` still answers and that both actions refuse.
- **R24** — "Grow's hosted page" → **"the configured gateway's hosted page"**. Grow was demoted 2026-07-31 and the shipped engine is Lemon Squeezy test mode. The audited property — no PAN proxied, logged or stored on our origin — is provider-independent and currently true by construction (zero card fields in any schema). B5 pins that.
- **R25** — "replay protection" → **"replay-safe by idempotency"**. Signature verification is real HMAC-SHA256 with `compare_digest` (`payments/lemonsqueezy.py:373-374`), and a redelivery is a proven no-op (`payments/service.py:611-617`; `test_deposit_confirm_db.py::test_a_redelivery_confirms_once_and_texts_once`). What does **not** exist is a timestamp/nonce freshness window, so a captured valid body can be replayed indefinitely — as a no-op, every time. The residual is nil for money and non-nil for log noise. Recorded as the shipped shape, not papered over.

**R40** is F20's amber row and **not F21's to close** — the send-time opt-out clause has no subject until a marketing send exists, *Owner: F46*. F21's edit, which F20 explicitly assigned it, is only to split the row so the discharged clauses read as discharged: `R40a` (capture, unbundling, structural default-off, the opt-out writer — **green, F20**) and `R40b` (honored in every marketing send — **open, F46**).

### D9 — `retention_enabled` stays `False`, and the row's owner changes

F20 handed this feature row **R42** with `retention_enabled: bool = False` (`core/config.py:232`) and the reason: an unattended irreversible mass-delete must not precede a drilled restore. **Verified against the code before asserting it**, because the honest answer had to be checked rather than assumed:

- The default is `False` (`config.py:232`), asserted by two tests (`test_config.py:217`, `test_worker.py:315`).
- The worker's scheduled path is genuinely gated on it (`worker.py:206, :215`), and `test_worker.py:273` names the disarmed path *"the DEPLOYED path"*.
- `run_retention` on the CLI is **deliberately not gated** (`cli.py:97`, `platform/service.py:156`), and its default mode is a rehearsal that counts and writes nothing; `--armed` is required. That is the single place the disarm can be defeated, on purpose.

**Row 44 — the drilled restore that gates row 42 — is in the parked half.** Therefore: `retention_enabled` stays `False`, **R42 stays unchecked**, and its owner moves from F21 to the parked entry `F62`. This is the honest reading the brief anticipated, and it is what the code says, not what the plan said.

**F21's positive deliverable on this row is a finding, not a flag flip.** `.planning/ppl-compliance-record.md:58` assigned one item to "F21's audit" with the trigger "BEFORE `RETENTION_ENABLED` is ever set": the 30-day orphan grace runs from `created_at`, because nothing on the row records when a customer *became* orphaned — so it protects a row created in the last 30 days and nothing else, and a phone correction that orphans a customer who first booked six months ago satisfies the conjunct immediately. **Re-derived and confirmed**: F15's phone correction re-points the *other* row and never touches this one (`booking/owner.py:1136-1161`), so `updated_at` will not serve as a proxy either. A real orphan clock is a new column — **and it belongs to whoever flips the flag, which is `F62`, so F21 adds no migration.** The finding is written into `F62`'s entry as a precondition, not left in a record nobody reads at flip time.

### D10 — The named audit row: F15 Risk 2, re-derived at production scale

The brief requires this finding be re-derived from the code rather than treated as closed. It was. **It is true as written, and the code is more specific than the sentence.**

**The endpoint.** Exactly one: `POST /manage/bookings/{booking_id}/phone` (`booking/owner_router.py:360-376` → `OwnerBookingService.correct_phone`, `booking/owner.py:1069-1193`). Body is one field, `phone: str`. Ruled out by grep, not assumption: `PATCH /manage/customers/{id}` takes only `notes` and `tags`; the walk-in create takes two UUIDs and no phone; `set_phone` has exactly one production caller.

**The gate — confirmed, both roles.** Router-level `require_role(StaffRole.OWNER, StaffRole.SHIFT_MANAGER)` (`owner_router.py:80-86`), no per-route tightening. Of the five `StaffRole` members exactly those two can call it. The route is not in `OWNER_ONLY` (`test_staff_role_gating.py:83-97`), and `test_booking_owner_api.py:405` walks both roles over it and asserts 200 — its docstring is the in-repo acknowledgment.

**What one call does.** New manage token minted, old token hard-revoked (only the sha256 was ever stored, so the old link is unrecoverable), the pending reminder re-pointed to the new token, and a **confirmation SMS carrying the new live control link sent to the NEW number**. On the non-collision branch `customers.set_phone` overwrites in place, which revokes the live link on **every** future confirmed booking of that customer while texting only one of them. **Nothing is ever sent to the old number** — `old_phone` is read at `owner.py:1101` and used for exactly one thing, `_last4()` in the audit details at `:1178`.

**No OTP, and that is documented as intentional in three places** (`owner_router.py:369-372`, `owner.py:1054-1058`, `owner-booking-management.md:560`): requiring one would require the bride to be reachable at the number that demonstrably does not work. The only ceremony is a client-side confirm modal echoing the typed number; server-side it is a single unconditioned POST.

**Does the acknowledgment still hold?** **Yes, and it was made with full knowledge.** `rulings_2026_07_30` records it verbatim: *"F15 phone-correction without OTP is ACKNOWLEDGED as shipped for owner AND shift_manager."* The role expansion is not news the acknowledgment failed to account for. What *had* gone stale is the reasoning in the spec that preceded it — `owner-booking-management.md:560` accepted Risk 2 as "bounded by the owner-role guard", and that bound was removed when F31 landed `shift_manager` before F15 merged. The 2026-07-30 ruling replaced the bound with an explicit acceptance. **The acknowledgment stands. The sentence that justified it does not, and the checklist must not cite it.**

**Residual risk, as it now stands.** Preconditions: a valid `shift_manager` session cookie. No password re-entry, no step-up, no per-action token. `GET /manage/bookings/{id}` returns the customer's full phone in cleartext, so the real number can be recorded before it is destroyed; the POST then delivers a live control link to the attacker's own handset, from which she can — anonymously, from any device — read the booking, confirm attendance, or cancel it attributed to the customer, freeing the seat to the public funnel. Volume is ~20/hour/tenant **per worker process**, shared with reschedules and resends, because the limiter is in-process.

- **Detectable and attributable**: one `audit_log` row per call with `actor_id`, booking id, both customer ids, `rotated_booking_ids`, timestamp, and last-4 of both numbers; `audit_log` is retention-exempt.
- **Unrecoverable**: the victim's original phone number on the non-collision branch (overwritten in place, no history table, audit carries last-4 only by deliberate policy, pinned by `test_booking_owner_service.py:1702`); every rotated manage link; any cancellation performed through the stolen link; and the fact that the victim was never told.
- **Two residuals worth naming that are not the accepted risk itself**: `audit_log` has **no read surface** — zero routers touch `AuditLogRepository`, so detection is a manual DB query nobody is prompted to run; and the throttle key is `booking:owner_sms:{tenant_id}`, per-tenant rather than per-actor, so one staffer can spend the whole boutique's budget.

**F21 changes no behaviour here.** The risk is accepted, the acceptance is current, and narrowing the gate to owner-only would reverse a ruling inside a hardening feature. What F21 ships is **one test** pinning that this path requires no OTP and admits both roles — so the day someone changes it, they change it deliberately — and the two residuals above recorded as named items on `F62` (an audit read surface) and in `known_product_bugs` (the per-tenant throttle key).

---

## Build list

| # | Deliverable | Rows |
|---|---|---|
| **B1** | CI: drop `continue-on-error` from `audit` (`ci.yml:223`), rename the job off "(warn-only)", refresh the lockfile with `pnpm update -r --depth Infinity`, add the waiver scaffold, and add `e2e` to `deploy-staging.needs` (`:124`) | R34, R47 |
| **B2** | `security_headers.py`: settings-derived CSP + scheme-gated HSTS emitted alongside (never inside) `SECURITY_HEADERS`; docstring rewritten against D3's two stale claims | R28, R33 |
| **B3** | `test_cross_tenant_walker.py` — live-route-table walker + `UNWALKABLE` completeness assertion | R9 |
| **B4** | Audit rows on `catalog`'s 11 mutations and on `platform.list_tenants`; audit-coverage walker with a reviewed `UNAUDITED_BY_DECISION` list | R38, R12 |
| **B5** | Six pins on properties already true or one line from true: cookie `secure` outside dev · a per-IP key on OTP send · the boot guard is not exempt for any non-`dev` env · no card field in any schema · manage-token action-expiry vs readable-lookup · no-OTP-and-both-roles on phone correction | R15, R16, R7, R24, R21, D10 |
| **B6** | axe: `/queue` (spec A29) + the 9 unscanned console sections; live-region sweep of `FloorPanel.tsx` and `GuideOverlay.tsx` | R47 |
| **B7** | `.planning/a11y-audit-v1.md` — manual keyboard + VoiceOver spot check, per surface, plus the recorded WCAG-2.0-only scope decision | R48, R49 |
| **B8** | `.planning/security-checklist-v1.md` rewritten: `R<n>` ids (D1), per-row verdict + evidence, R40 split, R21/R24/R25 amended | all |
| **B9** | New `F62` queue entry in `LOOP-STATE.md`: every parked row, blocker named as the three DNS records, the orphan-clock precondition, and the two D10 residuals | — |

---

## Frontend changes

**No new product surface.** The accessibility statement page — the one page this feature was expected to build — already ships (D2, conflict 1).

The frontend diff is tests and one comment sweep:

- `Frontend/e2e/storefront.spec.ts` — one `AXE_ROUTES` row for `/queue`, or a bespoke journey if the board needs seeded state to be materially different from empty.
- `Frontend/e2e/manage.spec.ts` — axe scans for the nine unscanned console sections, driven through the existing `installManageApi` fixture. ⚠ That fixture **stubs the API** and says so in its own header, so these prove the console's markup, never the contract; the header's warning must not be diluted.
- `FloorPanel.tsx` / `GuideOverlay.tsx` — audit the live regions against F61's corrected rule (React skips the DOM text write when a live region re-renders to the same string, so a cue that repeats verbatim is silent). Fix with the nonce+key shape `AtelierSection` already uses if either is actually silent; correct the comment either way.
- `frontend/package.json` / `pnpm-lock.yaml` — the B1 refresh, plus the `pnpm.auditConfig` waiver scaffold.

The lockfile refresh moves React and Vite minors, so `pnpm -r test` (2515 vitest tests) and `pnpm e2e` (155 tests) are both at risk and both must be green before the PR opens.

---

## Testing

Everything below runs on a CI runner with no deployed host.

- **B1** — `make lint`, full `pytest`, `pnpm -r test`, `pnpm -r build`, `pnpm e2e` all green **after** the lockfile refresh. `pip-audit` and `pnpm audit` both exit 0 with the job gating. A deliberately-injected fake waiver with a past expiry reds the job (proves the waiver machinery is not decorative).
- **B2** — per-header tests on a real response for both apps' shells, the JSON API, and the `TENANT_NOT_FOUND` 404; a settings-derived test proving the media origin appears in `img-src`/`connect-src` when a bucket is configured and **is absent when it is not**; an HSTS test proving presence over https and absence over http. **And the one that matters most: a Playwright test loading the real built bundle with the real policy applied and asserting zero CSP violations in the console** — a header-string assertion cannot see `assetsInlineLimit` turning an icon into a `data:` URI.
- **B3** — the walker itself, plus a mutation check: temporarily strip the `deleted_at`/tenant predicate from one repository read and confirm the walker reds. A walker that cannot red is the `known_vacuous` failure mode this repo has already been bitten by.
- **B4** — one test per newly-audited catalog mutation asserting exactly one row with the right actor and entity; the coverage walker; and a test that a *no-op* mutation writes no row, matching the standing design rule.
- **B5** — six focused tests, each of which must be shown to red on the mutation it guards.
- **B6** — axe green on all ten new surfaces; the live-region assertions use a `MutationObserver` installed **before** the action, which is the only instrument that caught F61's defect #2.
- **B7** — a written artifact, not a test. It must name the instrument and the date, and record failures as failures.

**Two standing hazards this feature must respect.** vitest runs in jsdom, where `showModal()` is stubbed — so no dialog-focus assertion added here is trustworthy at unit level; those belong in `frontend/e2e/dialog-focus.spec.ts`. And db-marked tests debut on CI unless run locally against real Postgres first; B3 and B4 are both db-marked, so run them against a local PG16 cluster as the app role before pushing.

---

## Out of scope

- **Everything in D2's PARKED table.** It becomes queue entry `F62`, `status: parked`, `blocker: "the 3 DNS records at DomainTheNet — external-applications.md #2"`, and it explicitly owns: R7's deployment clause, R12's access-restriction clause, R16's distributed limiter, R26 (KMS), R27 (receipts), R31 (Secrets Manager), R32's WAF clause, R42 (`retention_enabled` **and** the orphan-clock column that must precede it), R44 (backups + drilled restore + written RPO/RTO), production stand-up, prod wildcard DNS/TLS, prod Postgres, Terraform-izing `docs/infra-runbook.md`, and pilot onboarding + UAT sign-off with real Hebrew content.
- **Changing the F15 phone-correction behaviour.** D10. Accepted, current, and reversing it here would overturn a ruling inside a hardening feature.
- **An `audit_log` read surface.** Real product surface, its own spec. Recorded on `F62`.
- **k6 load testing.** Cut from v1 by the epic; it gates multi-tenant onboarding in E5 #29.
- **WCAG 2.1/2.2 axe tags.** D7 item 5 — recorded as a deliberate decision, not silently omitted.
- **`ar.ts`'s missing `statement.*` / `a11y.*` keys.** Arabic is not live for the pilot; F45's.
- **A manage-console accessibility statement and an `A11yMenu` in `ConsoleShell`.** Neither exists. IS 5568's public-site obligation is discharged by the storefront's; an employee-facing console obligation is a real question and a real page, and it is recorded as a finding rather than smuggled into a hardening feature.
- **Reversing `boutique`'s and `queue`'s recorded decisions not to audit.** D6 fences them with a reviewed list instead.
- **`/fake-pay`'s SPA-fallback tidiness item and the missing `favicon.ico`.** Still open in `known_product_bugs`, still LOW, still not this.

---

## Risks & open items

1. **The lockfile refresh reds the build.** Highest-probability failure in the feature. React, Vite, Rolldown, oxlint and Playwright all move, and six manifests change with them (D4 cost 2). Mitigation: refresh first, in its own commit, and get the full gate green before writing a line of B2–B7 — so a red is attributable to the bump and not entangled with a middleware change.
2. **The CSP breaks the built SPA in a way a header test cannot see.** `assetsInlineLimit` is the named tripwire. Mitigation: the browser-level CSP test in B2 is the acceptance criterion, not the header assertion. A CSP that breaks the app is worse than no CSP, and rolling back is one line if the browser test cannot be made green.
3. **The R9 walker cannot drive some routes generically** (multipart uploads, webhook signatures, token-authenticated storefront paths) and the `UNWALKABLE` set quietly becomes the interesting half. Mitigation: every entry carries a reason and the eight modules with *no* isolation file today are the acceptance bar — if `privacy` or `staff` ends up exempt, the row is not closed.
4. **`Frontend E2E` is not currently in `deploy-staging.needs`, and adding it lengthens the merge path.** Accepted: a legal accessibility requirement that does not block a deploy is not a gate.
5. **The audit is a snapshot.** Eleven rows are green because of code that merged in the last three weeks; nothing stops the twelfth merge from reopening one. Mitigation is the shape of every deliverable here — a walker, not a list; a test, not a paragraph.
6. **`F62` is a large parked entry and could rot into a wish list.** Mitigation: its blocker is one concrete user action already tracked in `external-applications.md` and re-nagged every iteration, and each of its rows carries the row id and the evidence F21 gathered, so whoever picks it up starts from an audited baseline rather than from this file.
7. **Counsel confirmation of the retention numbers** was flagged at pre-decided #10 "for counsel confirmation at the F21 audit". F21 cannot obtain it. It stays in `user_actions` alongside the SMS-body and privacy-default reviews, and `.planning/a11y-audit-v1.md` is not the place for it.

---

## Decisions Log

| # | Decision | Why |
|---|---|---|
| D1 | Freeze today's row numbers as explicit `R<n>` ids; splits take letter suffixes | Rows are pre-F20 line numbers cited from three other files; F20's assigned split would silently invalidate all of them |
| D2 | Split IN SCOPE / PARKED on one mechanical rule — provable on a CI runner with no host | The feature's whole reason for existing; a row this feature could prove but did not prove is a lie in an audit document |
| D3 | Ship CSP **and** HSTS now; neither needs the domain; both live outside the `SECURITY_HEADERS` dict | The built artifacts have nothing inline, so no nonce/hash is needed; HSTS applies only to the sending host and is ignored over http. Eight tests compare `SECURITY_HEADERS` with `==`, so conditional headers cannot join it |
| D4 | Gate the **full** `pnpm audit`, not `--prod`; close the 9 findings with a measured lockfile refresh; per-advisory waivers with rationale and expiry | `--prod` is free but blind to the toolchain that builds the shipped bundle. The refresh was run and verified, then reverted; it costs a React/Vite/Rolldown/oxlint bump |
| D5 | One live-route-table walker for R9, not 95 hand-written tests | The repo's own `test_staff_role_gating.py` pattern; a walker cannot rot when a route is added |
| D6 | Audit `catalog` + `list_tenants`; fence `boutique`/`queue` with a reviewed exemption list | Both modules recorded their omission deliberately; reversing that inside a hardening feature is out of character, and a reviewed list is what an audit needs |
| D7 | Close ten unscanned a11y surfaces; keep WCAG 2.0-only tags and say so; add `e2e` to the deploy gate | IS 5568 tracks WCAG 2.0 AA. Silence in an audit document reads as coverage |
| D8 | Amend R21, R24 and R25 to the shipped reading and pin it; split R40 without closing it | Where the checklist and a reasoned shipped design disagree, the sentence is wrong. R40's send-time clause is F46's and has no subject yet |
| D9 | `retention_enabled` stays `False`, R42 stays unchecked, and its owner moves from F21 to `F62`; the orphan-clock column goes with it | Verified against `config.py:232`, `worker.py:206`, `cli.py:97`: row 44 gates row 42 and row 44 needs a host. The flag flip and the column belong to the same hands |
| D10 | Re-derive F15 Risk 2, change no behaviour, ship one pinning test, record two residuals | The acknowledgment is current and was made knowing both roles. The *justification* in `owner-booking-management.md:560` is stale and must not be cited |
| D11 | Zero migrations | `audit_log.action` is unconstrained `TEXT`, so new `AuditAction` members need none; the only candidate column (the orphan clock) belongs to `F62` |
