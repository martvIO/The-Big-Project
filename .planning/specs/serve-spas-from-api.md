# Spec: Feature 55 — FastAPI serves the built SPAs (same-origin hosting)

**Created**: 2026-07-31 · **Status**: Gate 1 self-approved (no money/legal surface; Interview Q1 does not list it) · **Epic**: cross-cutting (deploy) · **Effort**: **M**
**Depends on**: nothing in code. Unblocked in the world by `modryn.co.il` being registered and the Railway wildcard `*.modryn.co.il` being created (2026-07-31). · **Feeds**: every future frontend feature — this is the first time any of them becomes reachable by a user.

---

## Problem

The frontends have never been hosted anywhere.

CI builds them and throws them away: `.github/workflows/ci.yml` runs `pnpm -r build` in the `frontend` job, the artifacts die with the runner, and `deploy-staging` uploads only `Backend/` (`working-directory: backend`, `railway up --service api --ci`). `Frontend/` is a sibling directory, outside the upload context. So the console and the storefront exist on developer machines and nowhere else.

`.planning/specs/storefront-browse.md:380` recorded this in F14 and left it open:

> **No frontend deploy pipeline exists at all.** … whatever eventually serves the SPA `index.html` must emit `X-Frame-Options: DENY` and `X-Content-Type-Options: nosniff`

and `:135` names the consequence: "the framable document is `index.html`, served by Vite in dev and by an **as-yet-nonexistent static host** in production — neither sees this middleware."

Everything else is now ready. The domain is bought, the wildcard domain exists on the `api` service, `BASE_DOMAIN=modryn.co.il` is live on both services, and the tenant middleware has resolved hosts to tenants since F4. The only missing piece is that nothing serves HTML.

## Goal

`https://{slug}.modryn.co.il/` renders the boutique's storefront and `https://{slug}.modryn.co.il/manage` renders the owner console, both served by the same FastAPI process that serves their APIs, on the same origin, behind the same security headers. A deploy carries frontend and backend as one artifact, so the two can never drift apart. `/health` keeps answering by IP for Railway's healthcheck, the docs stay dark outside dev, and every existing API route keeps its exact status code — including the 405s and 404s that three separate tests pin.

## Locked decision: same origin, split by PATH

This is already the architecture of record, and F55 implements it rather than deciding it.

`.planning/architecture.md:11`:
> Routing | Wildcard *.modryn.co.il, host→tenant middleware …, **storefront on subdomain, staff app at /manage**, cookies scoped to exact subdomain

`README.md:55`:
> The two apps share the origin `{slug}.localtest.me` in production (**storefront at `/`, console at `/manage`**) but are separate Vite servers in dev, so they need separate ports

`README.md:63`: "Both apps are same-origin in production and proxied in dev; **CORS must never be added for either**."

**Correction to this feature's own queue note.** `.planning/LOOP-STATE.md`'s F55 entry says the SPA fallback is decided "per host (manage vs storefront is decided by which app the host maps to)". That is a drafting slip: there is no second host. Every tenant host serves both apps and the split is by path prefix. `admin.{slug}.…` is impossible by construction anyway — `admin` is a reserved slug (`Backend/app/tenancy/slugs.py:8`) and `extract_slug` rejects nested labels (`slugs.py:43`).

The user's same-origin ruling (2026-07-31, recorded in the F55 queue note) rests on a fact in the code: `Backend/app/auth/cookies.py` mints the session cookie with **no `Domain` attribute**, so the browser itself refuses to send boutique A's session to boutique B's subdomain. A separate frontend origin would force `Domain=.modryn.co.il` to make credentialed cross-origin calls work, handing every tenant's cookie to every tenant's hostname, and would force dynamic wildcard CORS into a codebase that documents "no CORS, ever". Same-origin keeps that isolation browser-enforced.

## What already exists to build on (verified against code)

| Fact | Where | Why it matters |
|---|---|---|
| Nothing is registered at `/` or at exactly `/manage` | `Backend/app/main.py:675-702` — deepest are `/manage/settings`, `/manage/auth/me`, `/manage/staff`, `/manage/bookings`, `/manage/dresses`, `/manage/slots`, `/manage/terms`, `/manage/availability`, `/manage/appointment-types` | both paths are free for F55 |
| `SecurityHeadersMiddleware` is registered LAST = outermost | `Backend/app/main.py:319-322`; headers at `security_headers.py:31-37` | static responses get `X-Frame-Options: DENY` + `nosniff` for free — closes `storefront-browse.md:380` |
| No CSP exists yet | `security_headers.py:19-24` — "HSTS and CSP are deliberately absent… Owner: F21. Trigger: the domain is purchased." | nothing blocks the SPAs' assets. The trigger has now fired, so F21 inherits a CSP that must account for these mounts |
| `CsrfOriginMiddleware` ignores GET | `Backend/app/csrf.py:48` — guards only `MUTATING_METHODS` under `/manage` | serving the console shell by GET is untouched by CSRF |
| `EXEMPT_PATHS` is exact-match, 5 entries | `Backend/app/tenancy/middleware.py:28` | the fallback must not swallow them |
| Both apps default `base: "/"` and `outDir: dist`; `index.html` references **absolute** `/assets/…` | `Frontend/apps/*/vite.config.ts`; `dist/index.html` | manage needs `base: "/manage/"` or its asset URLs collide with the storefront's |
| The manage app has **no client-side router** | `App.tsx:49` `useState<SectionKey>`; `BookingsSection.tsx:55` "apps/manage has no router" | `/manage` needs one exact route, not a fallback subtree |
| The storefront hand-rolls a pushState router and treats unmatched paths as the catalog | `Frontend/apps/storefront/src/router.tsx:63-114` | needs a real SPA fallback: `/`, `/about`, `/accessibility`, `/dress/{id}`, `/b/{token}`, `/book[/step[/dressId]]` |
| Railway builds from `Backend/` via nixpacks; no Dockerfile/railway.toml exists | `docs/infra-runbook.md:110-154` | the SPAs must be copied INTO `Backend/` before `railway up` |

## Design

### 1. `Frontend/apps/manage/vite.config.ts` gains `base: "/manage/"`

One line. It makes manage emit `/manage/assets/…` and `/manage/favicon.svg`, so the two apps' static trees are disjoint and each can be mounted independently with no URL rewriting.

Consequence to fix in the same commit: `vite preview` for manage then serves at `:4174/manage/`, so `Frontend/e2e/a11y.spec.ts`'s `MANAGE` constant becomes `http://localhost:4174/manage/`. Without this the two manage e2e tests go red.

### 2. `Backend/app/main.py` — mounts and fallback, appended AFTER every `include_router`

Order is the whole design. Registered last means every API route wins first.

```
/health, /docs, …          EXEMPT_PATHS — untouched, must keep working by IP
/manage/auth/*, /manage/*  API routers (already registered above)
/storefront/*              API routers (already registered above)
--- F55 adds, in this order: ---
Mount /manage/assets       StaticFiles(manage_dist/assets)
Mount /assets              StaticFiles(storefront_dist/assets)
GET  /manage               -> manage index.html          (exact path only)
GET  /{path:path}          -> storefront index.html      (guarded fallback)
```

**The fallback is guarded, not merely last.** It returns 404 unless the path is safe to claim:

- path is in `EXEMPT_PATHS` → **404**. Without this, `GET /docs` in production returns the storefront shell with a 200, breaking `test_storefront_api.py:1379` and turning "docs are dark outside dev" into a lie.
- path starts with `manage/` or `storefront/` → **404**. Without this, `GET /storefront/otp/send` (a POST-only route) fully matches the catch-all and returns `200 text/html` instead of 405, breaking `test_notifications_api.py:154`. It is also worse in production than in test: `Frontend/apps/storefront/src/api.ts` would try to parse HTML as JSON — precisely the failure `storefront-browse.md:174` already names.

**Never `Mount("/", StaticFiles(html=True))`.** A `Mount` matches *every* method, so `HEAD /manage/settings` would look for a file and answer 404 instead of 405, breaking `test_staff_role_gating.py:519`. A FastAPI `@app.get` catch-all carries `methods == {"GET"}` exactly and leaves HEAD/OPTIONS to Starlette's 405 path — which is why the fallback is a GET route and not a mount.

Static roots come from a module-level constant pointing at `Backend/app/static/{manage,storefront}`. **When the directory is absent** (every dev machine, every test run, any deploy where the copy step failed) the app must boot normally and the mounts must simply not be registered — a dev running `make dev` has never built the SPAs and must not get a boot crash. `/health` then still answers, which is what keeps a mis-built deploy diagnosable rather than dead.

### 3. `.github/workflows/ci.yml` — build the SPAs into the upload

`deploy-staging` already `needs: [backend, frontend]`. It gains, before the two `railway up` steps: pnpm setup, `pnpm -r build`, and a copy of each app's `dist/` into `Backend/app/static/`.

⚠️ **The trap that fails silently.** `railway up` respects `.gitignore`, and `.gitignore:183` ignores `dist/`. A copy target named `dist` anywhere inside `Backend/` would be excluded from the upload with **no error** — green CI, 404s in production. The target is `Backend/app/static/` for that reason, and `staticfiles/` is also unusable (`.gitignore:170`). The build must additionally *assert* the copied files exist before `railway up`, so this failure can never be silent again.

## Non-goals

- **No CSP.** `security_headers.py:19-24` assigns it to F21; F55 only notes that the trigger has fired and that a CSP must now cover these mounts.
- **No `/assets/*` tenant-resolution bypass.** Every asset request currently costs one tenant DB lookup (`architecture.md:11`, "direct DB lookup in v1"). That is real but not this feature's problem — E5 #29 caches slugs. Recorded as a risk.
- **No apex routing.** `modryn.co.il` with no subdomain stays a 404; there is no marketing page to serve.
- **No prerender/SEO.** F49 owns that.

## Tests

- **Fallback guards** (fast): `/docs`, `/redoc`, `/openapi.json` still 404 in production; `GET /storefront/otp/send` still 405; `HEAD`/`OPTIONS /manage/settings` still 405; an unknown path on a valid tenant host serves the storefront shell; every storefront router path (`/about`, `/dress/x`, `/b/tok`, `/book/slot`) serves it too.
- **Absent-static-dir**: `create_app()` boots with no `app/static/` and `/health` answers; the fallback then 404s rather than 500s.
- **Existing walkers must stay green** unchanged — `test_storefront_api.py`'s ROUTES derivation and duplicate-route guard, `test_staff_role_gating.py`'s default-deny walker.
- **Explicitly recorded, not fixed**: the role-gating walker skips `Mount`s (no `dependant`), so the console *shell* is served ungated. That is correct — the shell is public HTML and every API behind it is role-gated — but a future reader must not read the walker's green as coverage of it. Asserted as a documented expectation in the test file.
- Frontend: `make fe-build` + `make e2e` (the `base` change moves manage's preview root).

## Risks

1. **The silent-copy failure** (above). Mitigated by the assert in CI and by `/health` staying green so the deploy is diagnosable.
2. **Per-asset tenant lookups** — ~40 DB round-trips per cold page load. Acceptable at pilot scale; E5 #29 is the fix.
3. **The console shell is public.** Anyone can fetch the HTML at `{slug}.modryn.co.il/manage`; it renders a login form and every API call behind it is authenticated and role-gated. Stated so it is a decision, not an oversight.
4. **`base: "/manage/"` breaks the manage dev server's root** — dev now serves at `localhost:5173/manage/`. The Vite proxy is unaffected; README's dev section needs the one-line correction.
