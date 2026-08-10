# Spec: Feature 26 — Invite-code boutique signup + gateway onboarding (Epic E5)

**Created**: 2026-08-09 · **Status**: **Gate 1: standing approval — interview-2026-07-30.md §Standing approvals** (Q1's enumerated exceptions are F17, F18, F19, F20, F29, F48; F26 is none of them. It *touches* the deposit story only by linking to a screen F17 already shipped — it adds no payment code, no money movement, no billing, no privacy-law text. See D7, which is what keeps that true.)
**Depends on**: **F25** (`ProvisioningService`, `platform_operators`/`platform_sessions`, the `admin.{base}` host fence, `apps/platform`) · F4 (`RESERVED_SLUGS`, tenant resolver) · F5 (argon2, `hash_token`) · **F17 only as a destination**, not as a code dependency (D7)
**Interview**: **Q10 — INVITE CODES ONLY** (against recommendation) · Q3/#47 (`ar` keys ship untranslated) · #20 (one audited command layer, no console-only powers)

---

## Problem

Since F25 an operator provisions a boutique by typing the owner's **initial password into her own console** and handing it over out of band («יש למסור את הסיסמה לעובדת בעצמך»). That is the whole gap: the operator holds, transmits and can recover a credential that should never have left the owner's keyboard. Q10 rules out the public funnel that would have fixed it another way, so what remains is small and precise — the operator authorises a specific boutique, the owner activates it herself, and nobody in the middle ever sees her password.

## Goal

An operator clicks «הזמנה חדשה», types slug + boutique name + owner email, and gets **one link, shown once**. The owner opens it, sees which boutique and which email she is claiming (both read-only), chooses a password, submits — and in **one transaction** the invite is consumed, the tenant is created and her owner account exists, through the same `ProvisioningService` path the console uses, writing the same `TENANT_PROVISIONED` row. She lands on a success screen that links to `https://{slug}.modryn.co.il/manage`, logs in, and connects her payment gateway on F17's existing owner-only screen. A second click on the same link fails. Hebrew-first RTL, `ar` untranslated, no exclamation marks, axe zero-violation.

## CONFLICTS — the E5 brief vs Q10 (built to Q10)

`e5-growth.md` §Feature 26 describes **a different feature** and is stale in a load-bearing way. Recorded rather than silently followed:

| The brief says | Q10 / LOOP-STATE F26 says | Built to |
|---|---|---|
| "Owner-facing **public** signup" | "No open self-serve registration" | Q10 — redemption is reachable only with a code the operator issued |
| "**claim a subdomain**" (the redeemer picks the slug) | "no public subdomain claiming" | Q10 — **the operator pre-assigns the slug at invite time** (D2). Slug validation stays where F25 put it; the redeemer never types one |
| "abuse surface (slug squatting, junk tenants, rate limits) is **first-class spec scope**" | "removes almost the entire abuse surface — no captcha, no rate-limit-the-world, no slug reclamation in F26's scope" | Q10 — OUT. What survives is the *ordinary* failures-only limiter every unauthenticated route in this repo already carries (D5), not an abuse programme |
| "**does not launch publicly until #29 is green**" | "it is no longer gated by F29" | LOOP-STATE — there is no public launch to gate. F29 is not a dep and F26 does not wait on it |
| Effort **M**, "gateway-connect onboarding step wrapping E4 #17's credential management + validation ping" | — | **S/M, and the gateway step is a link** (D7). F17 shipped the whole surface owner-only on the tenant host; wrapping it here would fork it |

Second conflict, with shipped code: `test_staff_role_gating.py::test_every_platform_route_but_the_two_public_ones_requires_an_operator` names **two** public `/platform` routes. F26 makes it four. Extending that allowlist is a **task in the plan and a review item**, never an incidental edit — it is the test whose whole job is to make a new anonymous route on the platform's host a deliberate act.

**Third conflict — this spec vs the code it produced (built to the code; amended here rather than left stale).** Gate 1 approved a preview at `GET /platform/join/invite?code=…` reached from a link carrying `?code=` in the query string. Review round 1 changed both, and the change is right: **the code is a live 14-day boutique-creation credential**, and a query string puts it in every access log, proxy trace, `Referer` header and support bundle on the path. The repo already argues exactly this for two lesser secrets (`queue/router.py:16-20` for the walk-in ticket, `booking/schemas.py:74-83` for the manage token), so F26 following them is consistency, not novelty. What shipped, and what the sections below now describe:

| Gate-1 contract | Shipped | Why |
|---|---|---|
| `GET /platform/join/invite?code=…` | **`POST /platform/join/invite`**, code in the JSON body | The credential never reaches a request line. Still a pure read — writes no audit row, and `test_audit_coverage.py`'s `UNAUDITED_BY_DECISION` carries that note **because** the mutation walk classifies by method |
| `join_url` = `…/platform/join?code=…` | **`…/platform/join#code=…`** | A fragment is never sent to any server, so no origin on the path — ours or the edge's — can log it |
| `JoinPanel` bootstraps off `location.search` | **`location.hash`** | Follows the link above |

Everything else about the preview is unchanged: same one `invalid_invite` for four states, same shared limiter budget, same anonymous router.

## What already exists to build on (verified against merged code)

- **`ProvisioningService.provision`** (`app/platform/service.py:94`) already does the exact work redemption needs — `is_valid_slug` → `_password_problem` (the `MIN_STAFF_PASSWORD_LENGTH` floor) → `by_slug` → one `tenant_session` transaction inserting `Tenant` + owner `StaffUser` + the `TENANT_PROVISIONED` audit row, with an `IntegrityError` backstop mapping to `slug_taken`. Business failures are **returned**, never raised, so failure audits commit (the F5 lesson).
- **`PlatformAuditLogRepository.record`** — client-side `id`/`created_at` so the INSERT emits no `RETURNING`, which is what makes the INSERT-only grant satisfiable. `action` is plain TEXT with no CHECK (0004): **new `PlatformAuditAction` members need no migration.**
- **The host fence** (`app/tenancy/middleware.py`): on `admin.{base}` only `/platform*` proceeds and `request.state.platform_host = True`; on every tenant host `/platform*` gets the one `TENANT_NOT_FOUND` body. `PLATFORM_PREFIX` matching is segment-exact.
- **`csrf.py`** protects `/platform` already; **`get_current_operator`** is a per-route dependency (`platform/router.py:35`), not middleware — so a sibling router under the same prefix can be anonymous without touching the fenced one.
- **`app/auth/tokens.py`**: `generate_session_token()` = `secrets.token_urlsafe(32)`, `hash_token()` = sha256. The repo's existing "high-entropy secret, store only the hash" pair, used by staff sessions, manage links and `platform_sessions`.
- **`FixedWindowRateLimiter`** with the F25 posture: **its own instance per budget**, failures-only, plus `platform_login_global_max_attempts` — a global arm that exists specifically because failed attempts write rows into a table the app can neither read nor prune.
- **`apps/platform`**: no client router, one screen off `useState`, `GET /platform/auth/me` bootstrap, `ApiError.code` is the contract, `he.ts`/`ar.ts`, `validation.ts` mirrors `RESERVED_SLUGS`. `_serve_file(app, "/platform", …)` is an **exact path** — a second exact path is one line (`main.py:630`).
- **F17's gateway surface** is shipped and complete: `GET/PUT/DELETE /manage/gateway*` under `require_role(OWNER)`, a `gateway` entry in the manage nav's `SectionKey`, and `PolicyBlockerBanner` for deposits-on-with-no-gateway. `connect()` deliberately pings the provider **outside and before** its transaction.
- **Migrations**: main's head is **0031**; two builders hold later numbers in live worktrees. F26 numbers **head+1 when its branch cuts** and **renumbers at the pre-push rebase** (`.memory/parallel-alembic-numbering` — a duplicate `revision` breaks `alembic upgrade` outright; a duplicate `down_revision` only branches history, which the fast lane catches).

## Scope

**IN**
- `platform_invites` table (one migration) + repository.
- Operator surface on the console: create invite, list invites, revoke invite — new endpoints under `/platform/invites`, all `Depends(get_current_operator)`.
- **Two anonymous routes** on the console host: preview an invite by code, redeem it.
- `ProvisioningService.redeem_invite` — claim + provision + owner creation in **one transaction**, sharing `provision`'s body (D4).
- Redemption UI inside the existing `apps/platform` bundle, served at `/platform/join`.
- Five new `PlatformAuditAction` members (no migration).
- Walker registrations: cross-tenant, role-gating (the four-public-routes edit), audit coverage, SPA serving.

**OUT — per Q10**
- Any public signup funnel or open registration.
- Slug claiming *by the redeemer*; slug reclamation of any kind.
- Captcha, IP reputation, abuse scoring, rate-limiting beyond the ordinary failures-only limiter D5 specifies.

**OUT — because they are other features**
- Billing / metered invoicing — **F48**. WhatsApp — **F46**. Refund automation, k6, Redis caching — **F29** (not a dep, see Conflicts).
- Gateway credential entry — **F17, already shipped**; F26 links to it (D7).
- Sending the invite email/WhatsApp for the operator. The link is displayed once and copied; no outbound channel, no template, no deliverability surface. (`NotificationService` is SMS to Israeli mobiles — wrong instrument, and the operator already has the boutique's contact details.)
- Operator self-service, TOTP, un-suspend — F25's OUT list, unchanged.

## Design

### D1 — Where the redeemer lands: `admin.{base}/platform/join#code=…`, in the shipped bundle

There is no public app to host this. The three candidates and why one wins:

- **Apex** — deliberately 404s (F4's anti-enumeration posture, re-affirmed by F25 D1). Re-opening it re-litigates a settled decision and needs a new DNS record. **No.**
- **Tenant host `{slug}.modryn.co.il`** — the tenant does not exist until redemption succeeds; the resolver 404s it. Provisioning a "pending" tenant first would fork the audited path in two and burn the slug on an unredeemed invite. **No.**
- **A new reserved label `join.{base}`** — the wildcard cert `*.modryn.co.il` and wildcard DNS cover it for free, but the platform bundle is built with `base: "/platform/"`, so its assets resolve under `/platform/*`; serving it on an invite host means either leaking `/platform*` through that host's fence or standing up a **fourth workspace app** for one form. **No** — the cost is a whole app and a fourth e2e webServer.
- **Chosen: the console host, anonymous routes under the existing `/platform` prefix.** Zero DNS, zero cert, zero new SPA, zero new fence. The link is `https://admin.modryn.co.il/platform/join#code=…` — a **fragment**, never a query string, so the credential reaches no server's log (see CONFLICTS, third item).

**The honest cost, recorded:** F25 D6 named an edge IP-allowlist on `admin.{base}` as the cheaper, stronger sibling of TOTP, and F62 owns that decision. A blanket allowlist would now break signup. **F62's allowlist must be path-scoped** — `/platform/join*` open, `/platform/*` restricted — which every edge/WAF does natively. This constraint is carried to F62's open questions, not left to be discovered.

Mechanics: `_serve_file(app, "/platform/join", platform / "index.html")` — one line beside the existing `/platform` line, same exact-path rule. `App.tsx` branches before its `me()` bootstrap: `location.pathname === "/platform/join"` → render `JoinPanel`, never call `/platform/auth/me`. The operator console is untouched on `/platform`.

### D2 — The invite carries the slug; the redeemer contributes only her password

Q10 removes subdomain claiming, which settles this: **the operator pre-assigns `slug`, `name` and `owner_email` at invite time.** Consequences, all of them good:

- A leaked link can only create *the boutique the operator authorised, under the address he authorised*. A redeemer-chosen slug or email would make the link a bearer token for "become the owner of a boutique of my choosing".
- The redeemer's form has **one input**. Slug validation, `RESERVED_SLUGS` and `validation.ts`'s mirror all stay exactly where F25 put them — on the operator's form.
- The join screen renders slug, boutique name and owner email **read-only**, so a mistyped invite is visible before it is spent, and the fix is revoke-and-reissue.

### D3 — Data model (one migration, head+1 at build time, renumber at rebase)

Platform-scoped like `platform_operators`: **no `tenant_id` column**, therefore outside `test_every_tenant_id_table_has_forced_rls`'s metadata scan, no RLS, no policy over rows no tenant owns. The created tenant is recorded as `redeemed_tenant_id` — 0004's `target_tenant_id` lesson, applied a third time.

```sql
CREATE TABLE platform_invites (
  -- standard block MINUS tenant_id: id uuid_generate_v4() PK, created_at, updated_at (trigger), deleted_at
  code_hash          TEXT NOT NULL,          -- sha256 of a token_urlsafe(32); THE RAW CODE IS NEVER STORED
  slug               TEXT NOT NULL,
  name               TEXT NOT NULL,
  owner_email        TEXT NOT NULL,
  created_by         TEXT NOT NULL,          -- the authenticated operator's email
  expires_at         TIMESTAMPTZ NOT NULL,
  redeemed_at        TIMESTAMPTZ,            -- NULL = unredeemed; the single-use predicate
  redeemed_tenant_id UUID                    -- no FK, house rule
);
CREATE UNIQUE INDEX idx_platform_invites_code_hash ON platform_invites (code_hash);
CREATE INDEX idx_platform_invites_open ON platform_invites (expires_at)
  WHERE redeemed_at IS NULL AND deleted_at IS NULL;
```

Explicit `GRANT SELECT, INSERT, UPDATE ON platform_invites TO app_user` written out (0028's posture — 0002's `ALTER DEFAULT PRIVILEGES` only covers tables created by the role that ran it). No DELETE: revoke is a soft delete.

**`redeemed_by` is deliberately absent.** It could only ever equal `owner_email`, because that is the only identity a redemption can produce (D2). The request IP is not stored either — it is not needed for any decision, and Amendment 13's minimisation duty makes "collect it because we could" wrong. The `INVITE_REDEEMED` audit row is the record.

**Code handling**: `generate_session_token()` at creation → the raw value is returned **once** in the create response and **never again**; only `hash_token(code)` is stored. Lookup is by hash. A leaked database yields no usable invite. Expiry default **14 days** via a new setting `invite_ttl_seconds: int = 14 * 24 * 3600`.

### D4 — Redemption is one transaction, and it is `provision`'s transaction

`ProvisioningService.provision`'s body — `tenant_session` → `Tenant` → `StaffUser` → `TENANT_PROVISIONED` — is extracted verbatim into a private `_create_tenant(session, *, tenant_id, slug, name, owner_email, owner_password, operator)`. `provision` keeps its signature and behaviour exactly; `redeem_invite` opens the same kind of transaction and calls the same helper. **One provisioning path, one audit shape, no parallel writer** (#20).

```
redeem_invite(code, owner_password):
  hash = hash_token(code)
  row = SELECT by code_hash                     # read-only, outside the txn: shape the refusal
  refuse if none / expired / redeemed / soft-deleted  -> "invalid_invite"   (ONE code for all four)
  refuse if _password_problem(owner_password)         -> "empty_password" | "password_too_short"
  async with tenant_session(factory, tenant_id=uuid4()):
      claimed = UPDATE platform_invites
                   SET redeemed_at = now(), redeemed_tenant_id = :tid
                 WHERE code_hash = :hash
                   AND redeemed_at IS NULL AND deleted_at IS NULL
                   AND expires_at > now()
             RETURNING id                       # rowcount 0 -> raise -> whole txn rolls back
      _create_tenant(session, ..., operator=row.created_by)
      audit INVITE_REDEEMED
```

**Single-use under concurrency, two independent guards.** (a) The claim is an **atomic conditional UPDATE guarded on `redeemed_at IS NULL`**, taken as the *first* statement in the transaction: a second concurrent redeemer blocks on that row lock, and when the winner commits it re-evaluates the predicate, matches zero rows and rolls back — no tenant, no owner, no audit row of its own beyond the failure. (b) Even if (a) were bypassed, both racers insert the same slug and the partial unique index behind `provision`'s `IntegrityError` handler refuses the loser. This is the `create_booking` / `gateway connect` structural-idempotency shape the repo already uses, minus the advisory lock — a single-row conditional update needs no second serializer.

`tenant_id` is generated **before** the transaction so the claim can name it; a rollback simply discards it. Writing `platform_invites` inside a `tenant_session` is safe: the table carries no RLS policy, so the session's tenant context does not touch it.

**Failures return, never raise** — `CommandResult(ok=False, message=…)`, so every `INVITE_REDEEM_FAILED` row commits (F5).

### D5 — Ordinary limiter, one instance, and the reason it exists is the audit table

Q10 removes abuse scope; it does not remove the fact that **an anonymous route that writes INSERT-only audit rows can be made to fill a table the app cannot prune.** So: one **new** `FixedWindowRateLimiter` instance (never a key on an existing budget — the per-instance rule `main.py` states five times), failures-only, keys `code:{code_hash}` and `ip:{ip}` when `trust_forwarded_for` yields one, plus a global arm mirroring `platform_login_global_max_attempts`. Settings `invite_redeem_max_attempts: int = 5`, `invite_redeem_window_seconds: int = 900`, `invite_redeem_global_max_attempts: int = 60`. That is the same shape F25's login already ships and no more.

**One refusal code for four states.** Unknown / expired / already-redeemed / revoked all answer `invalid_invite` at 404. A distinct "already redeemed" would tell an unauthenticated caller that a code was real — the same anti-enumeration reading as `TENANT_NOT_FOUND`.

### D6 — API surface, and which host serves it

All under the existing `/platform` prefix on `admin.{base}` — fenced off every tenant host by the shipped middleware, CSRF-protected by the shipped prefix tuple.

| Method + path | Auth | Body / query | Returns |
|---|---|---|---|
| `POST /platform/invites` | operator | `{slug, name, owner_email}` | `{code, join_url, expires_at}` — **the only time `code` exists in a response** |
| `GET /platform/invites` | operator | — | open + redeemed invites (no code, no hash) |
| `POST /platform/invites/revoke` | operator | `{id}` | `{ok}` |
| `POST /platform/join/invite` | **anonymous** | `{code}` | `{slug, name, owner_email}` or 404 `invalid_invite` — **a POST because it is a read of a CAPABILITY**; see CONFLICTS, third item |
| `POST /platform/join/redeem` | **anonymous** | `{code, owner_password}` | `{slug, manage_url}` |

Two routers: the operator one extends the fenced `app/platform/router.py` pattern (`Depends(get_current_operator)` on the router); the anonymous one is **its own `APIRouter`** with no auth dependency, so no route can acquire or lose an operator context by editing a shared list. Refusal codes join `_REFUSAL_STATUS`: `invalid_invite` → 404, `invalid_or_reserved_slug`/`empty_password`/`password_too_short` → 400, `slug_taken` → 409.

`POST /platform/join/invite` is a **read that discloses a boutique name to an unauthenticated caller holding a 256-bit secret**. It is the whole point of showing the owner what she is claiming before she claims it. It is rate-limited on the same budget as redeem and writes no audit row (a read of one's own invite is not a platform event; `TENANTS_LISTED`'s cross-tenant-enumeration argument does not apply).

### D7 — Gateway onboarding is a link, not a step

The brief wants "a new tenant able to take deposits from day one". Against what F17 actually shipped, folding gateway connection into redemption is wrong three ways:

1. **F17's `connect()` pings the provider outside and before its transaction, on purpose** — "a provider hang must never hold a DB transaction open". Redemption is one transaction that must stay short; putting a third-party HTTP call inside it makes a boutique's existence depend on a merchant API's latency.
2. **The credential is per-tenant merchant material the owner holds**, entered on a route that requires a tenant host and `require_role(OWNER)`. At redemption there is no tenant host and no session.
3. **F17 already ships the entire flow**: a `gateway` section in the manage nav, connect/validate/disconnect, status in every state, and `PolicyBlockerBanner` when `deposits_enabled` is on with nothing behind it.

So: the redemption success screen states the boutique is live and links to `https://{slug}.modryn.co.il/manage`. A new tenant's `settings` is `{}`, so `deposits_enabled` is off and the banner is silent until she turns deposits on — at which point F17's shipped banner is exactly the nudge the brief was asking for. **F26 adds no payment code.** That is also what keeps Gate 1 self-approving (Q1).

### D8 — Frontend

`apps/platform`, no new app, no new build config.

- **`JoinPanel`** (`components/JoinPanel.tsx`): reads `code` from `location.hash` (`#code=…`), calls `POST /platform/join/invite`, renders boutique name + `{slug}.modryn.co.il` + owner email **read-only**, one password field (`minLength` mirroring `MIN_STAFF_PASSWORD_LENGTH`), submit → success screen with the manage link. No code in the URL, or a 404 → a manual code entry field, then the same panel. Server refusals map by `ApiError.code` to their own Hebrew sentences; anything unlisted falls through to `errorMessage()`.
- **`InvitesSection`** in `Console.tsx`: «הזמנות» — create form (slug + name + owner email, reusing the shipped `slugProblem()` mirror), a table of open/redeemed invites, revoke with a confirm dialog (destructive red on the **final** confirm only — the manage precedent). The created link is shown once in a copyable field with «הקישור מוצג פעם אחת בלבד» and disappears on dismiss.
- **i18n**: `he.ts` + `ar.ts` (untranslated, Q3/#47), **zero exclamation marks** (#5). New keys under `platform.invites.*` and `platform.join.*`: `title`, `slug`, `name`, `ownerEmail`, `create`, `linkOnce`, `copy`, `copied`, `revoke`, `revokeConfirm`, `expiresAt`, `redeemed`, `open`, `join.heading`, `join.claiming`, `join.password`, `join.submit`, `join.success`, `join.toManage`, `join.codePrompt`, and one sentence per refusal code (`invalid_invite`, `slug_taken`, `invalid_or_reserved_slug`, `password_too_short`, `empty_password`, `rate_limited`).
- **Touch targets**: every control on the join screen is `size="md"` — F-W1, `sm` is 36px and fails the 44px floor. The join screen is the one screen in this app a non-operator uses, likely on a phone.

## Audit contract

Every operator action and every redemption writes to `platform_audit_log` through `PlatformAuditLogRepository.record` (client-side `id`/`created_at`, no `RETURNING`). New `PlatformAuditAction` members — **TEXT column, no CHECK, no migration**: `INVITE_CREATED`, `INVITE_CREATE_FAILED`, `INVITE_REVOKED`, `INVITE_REDEEMED`, `INVITE_REDEEM_FAILED`.

- `operator` = the authenticated operator's email for create/revoke; for both redemption rows it is **the invite's `created_by`** — the accountable identity, since the redeemer authenticates as nobody. `INVITE_REDEEMED.details` carries `{slug, owner_email}`.
- Redemption **also** writes the unchanged `TENANT_PROVISIONED` row from `_create_tenant`, which is the mechanical proof that it used the same path (D4). `target_tenant_id` is set on it and on `INVITE_REDEEMED`.
- `details` never carries the raw code, the code hash, or a password.
- `INVITE_REDEEM_FAILED` records the reason and the code **hash prefix only** — never the raw code, which would put a live credential in an append-only table.

## Test plan

**Fast lane (unit)** — no DB: refusal mapping for all four invalid states → one `invalid_invite` code; the redeem limiter's keys, global arm and failures-only recording; `JoinPanel`'s branch (`/platform/join` never calls `me()`); `App.tsx` still bootstraps normally on `/platform`; the anonymous router carries no `get_current_operator` dependency (introspected, not asserted by comment).

**db-marked, as `boutique_app`** (the `test_provisioning.py` technique — audit rows asserted over an owner-role connection, since the app role has no SELECT on the book):
- create invite → redeem → the tenant exists, the owner logs in through `AuthService`, and `TENANT_PROVISIONED` + `INVITE_REDEEMED` are both present.
- **Concurrent double-redemption race** — two `redeem_invite` coroutines on the same code via `asyncio.gather` against a real Postgres: **exactly one** succeeds, exactly one tenant row exists for that slug, and the loser leaves no `Tenant`, no `StaffUser` and no `TENANT_PROVISIONED`. (The F19 hold-expiry and F13 double-book tests are the pattern.)
- Redeeming twice sequentially → `invalid_invite`; expired → `invalid_invite`; revoked → `invalid_invite`.
- Slug taken between issue and redemption → `slug_taken`, **and the invite stays unredeemed** (the transaction rolled the claim back) so a reissued slug can still use it.
- Short/blank password refused with its own code, invite unspent, `INVITE_REDEEM_FAILED` committed.
- Limiter: 429 after budget on repeated bad codes.

**Walkers (registration is the task, not a side effect)**:
- `test_cross_tenant_walker` — the five new `/platform` routes join `NOT_TENANT_SCOPED` so `walked ∪ exempt == route table` keeps holding.
- `test_staff_role_gating::test_every_platform_route_but_the_two_public_ones_requires_an_operator` — **renamed and extended to four**, with the two new anonymous routes named and justified in the allowlist comment (the Conflicts section's second item).
- `test_audit_coverage` — the four mutating routes resolve to `_audit.record` through delegation; `POST /platform/join/invite` joins `UNAUDITED_BY_DECISION` with its reason (it is a read wearing a POST, and the walk classifies by method).
- `test_spa_serving` — `/platform/join` serves the console index; the storefront catch-all still declines it; missing bundle still degrades.
- `test_middleware` — `/platform/join*` is refused on a tenant host and on the apex with the one `TENANT_NOT_FOUND` body.
- `test_frontend_constant_parity` — unchanged and must stay green (no new mirrored constant; the password floor is expressed as `minLength`, not re-derived).

**e2e (Playwright + axe, `Frontend/e2e/`, interception fixtures)**: extend `platform.spec.ts` with the invites section (create → link shown once → revoke confirm dialog, red on final confirm only) and add `join.spec.ts` — invalid code → Hebrew sentence, valid code → read-only facts → weak password refused → good password → success screen with the manage link. **axe zero-violation on the join panel, the success screen, the invites table and the revoke dialog**; RTL rendering asserted; no exclamation marks in any new string (the shipped i18n lint pattern).

## Traps (for the plan)

- Migration number is **head+1 when the branch cuts** (main is at 0031, two builders hold later numbers) and is **renumbered at the pre-push rebase**. Never squat a number visible in a sibling worktree.
- `git add` pathspecs **lowercase** (`backend/…`, `frontend/…`); file reads capitalized. Verify with `git show --stat`.
- Commit per task — a dying builder's uncommitted work is reverted (LOOP-STATE, 2026-08-08).
- Never add `/platform/join` to `EXEMPT_PATHS` — exemption skips resolution on *every* host and would open the join route on every boutique's subdomain. The fence is the label branch.
- The audit repository's no-`RETURNING` property is load-bearing: every new write goes through `record`, never `session.add(PlatformAuditLog(...))`.
- `_create_tenant` extraction must be **behaviour-identical** — `provision`'s existing tests are the regression check and must pass unedited.
- Vite dev: bind `--host 127.0.0.1` (IPv6-only trap).
- The raw code exists in exactly one response and one log-free code path. It must not reach a logger, an audit `details`, or an error message.

## Decisions log

| # | Decision | Basis |
|---|---|---|
| D1 | Redemption on the console host at `/platform/join`, in the shipped bundle | apex 404s by design, tenant host does not exist yet, a new label costs a fourth SPA; **F62's IP allowlist must be path-scoped** |
| D2 | Operator pre-assigns slug + name + owner email; redeemer supplies only a password | Q10 removes subdomain claiming; a leaked link must not be a bearer token for an arbitrary boutique |
| D3 | `platform_invites`, no `tenant_id`, sha256 code hash, single-use + expiry, soft-delete revoke | 0004/0028's platform-scoped precedent; the raw code is never stored |
| D4 | `redeem_invite` shares `provision`'s extracted body; claim is the first statement in that transaction | #20 — one audited command layer; atomicity and single-use fall out of one transaction |
| D5 | One new limiter instance, failures-only + global arm; one `invalid_invite` code for four states | the per-instance rule; the INSERT-only audit table is the resource being protected; anti-enumeration |
| D6 | Two routers under `/platform` — fenced operator routes, a separate anonymous one | auth cannot be acquired or lost by editing a shared dependency list |
| D7 | Gateway connection stays F17's owner-only `/manage/gateway`; F26 links to it | F17's ping is deliberately outside its transaction; no tenant host or session exists at redemption; the shipped banner is the nudge |
| D8 | Redemption UI inside `apps/platform`; `md` touch targets throughout the join screen | one exact-path line vs a fourth workspace app; F-W1's 44px floor |

## Open questions (non-blocking)

- **Reissue ergonomics**: revoke-then-create is two clicks and is the whole story for a mistyped invite. A one-click "reissue" is a follow-up if the operator ever asks.
- **Invite expiry default (14 days)** is a settings value; the pilot's actual turnaround is the only evidence that would change it.
- **F62 inherits a constraint from D1**: any edge IP allowlist on `admin.{base}` must exempt `/platform/join*`. Recorded here and to be carried into F62's spec.
