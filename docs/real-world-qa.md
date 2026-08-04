# Real-World QA Runbook — the assembled product, a real browser, a real database

This drives the **whole product** — both SPAs served by the real FastAPI app, on
one origin, against a real Postgres — through the four journeys the boutique
actually performs.

**Why it exists.** The two halves of this product have only ever been tested
apart. `frontend/e2e/fixtures/manage.ts` intercepts every `/manage` API call and
never authenticates (it fulfils `GET /manage/auth/me` with a 200 body; that *is*
"signed in" there) — its own header states the limit: *it proves the console, not
the contract*. The backend suite never opens a browser. A renamed payload key
passes both suites and breaks production.

**When to run it.** Loop step 9, the epic-boundary QA pass — **every** epic
boundary, not once. Budget ~45 minutes for the full sweep once the environment
exists; the environment survives between passes, so later passes are ~20 minutes.

**What it is not.** Not the dev-server layout (`make fe-dev` on :5174 storefront,
:5173/manage/ console, each proxying to :8000). That is a *different*
configuration — different origins, Vite's proxy in the path — and nothing below
exercises it.

---

## 0. Conventions

The repo path contains spaces and a `+`. **Quote every path, always.** Unquoted
paths fail in ways that read as missing files. Set this once per shell:

```bash
REPO="/Users/mrwen/Documents/Github/Ryan + rawad + mrwen"
# ...or your worktree:
# REPO="/Users/mrwen/Documents/Github/Ryan + rawad + mrwen/.worktrees/qa-foundation"

DB=boutique          # the standing QA database
# ...or a throwaway you can drop without touching anything else:
# DB=modryn_demo
```

Every command below is `cd "$REPO/backend"` or `cd "$REPO/frontend"`. Paths are
written lowercase (`backend/`, `frontend/`) — that is what git tracks, and macOS
is case-insensitive so it resolves either way. **In git pathspecs use lowercase
or `git add` silently skips modified tracked files.**

`$DB` is threaded through §2.1, §2.2, §3.A step 10, §4 and §5 so the whole
runbook can be pointed at a scratch database in one place. This document was
last verified end-to-end against `DB=modryn_demo`; every command below is one
that was actually run.

---

## 1. Prerequisites (one-time)

| Need | Check | Fix |
|---|---|---|
| Postgres 16, local, **no Docker** | `pg_isready` → `accepting connections` | `brew services start postgresql@16` |
| `psql` / `createdb` / `dropdb` | `which psql createdb dropdb` | Homebrew postgres on PATH |
| a **`postgres` login role** | `psql -d postgres -tAc "select 1 from pg_roles where rolname='postgres' and rolcanlogin"` → `1` | `createuser -s postgres` |
| `uv` | `uv --version` | https://docs.astral.sh/uv |
| Node 24 + pnpm 10 | `node -v && pnpm -v` | `corepack enable` |
| Chromium (only for the Playwright-MCP-driven variant) | — | `pnpm exec playwright install chromium` |

Install deps once:

```bash
cd "$REPO/backend"  && uv sync
cd "$REPO/frontend" && pnpm install
```

> If you have a `VIRTUAL_ENV` exported from another checkout, `uv` prints
> `does not match the project environment path .venv and will be ignored`. That
> is a warning, not a failure — `uv run` uses the project's own `.venv`.

---

## 2. Boot sequence

**Run the sub-sections in this order** — three of the dependencies are not
obvious and each one costs a restart or a wrong-database migration if you get it
backwards:

| Order | Step | Depends on |
|---|---|---|
| 1 | §2.2 `.env` | — (alembic reads `DATABASE_URL` from it; without it §2.1 silently migrates `boutique`) |
| 2 | §2.1 database + migrations | §2.2 |
| 3 | §2.3 build + copy the SPAs | — (but must precede §2.4: the route table is built at import) |
| 4 | §2.5 provision the tenant | §2.1. Does **not** need the server. |
| 5 | §2.4 run uvicorn | §2.2, §2.3 |
| 6 | §2.6 seed | §2.4 + §2.5 — `seed_demo.py` drives the live HTTP API |
| 7 | §2.7 smoke | all of it |

### 2.1 Database

Write `.env` **first** (§2.2) — alembic reads `DATABASE_URL` out of it, and with
no `.env` it silently falls back to the `boutique` default no matter what `$DB`
says.

```bash
createdb "$DB" 2>/dev/null || true
cd "$REPO/backend" && uv run alembic upgrade head
uv run alembic heads            # 0023 (head)
uv run alembic current          # must print the same revision
```

Verified head is **`0023`**, and a fresh `createdb` + `upgrade head` lands there.
A pre-existing local `boutique` database is very likely *stale* — mine was
sitting at `0011`. `alembic current` disagreeing with `alembic heads` is the
single most common cause of "the app is broken": you get 500s on whichever
surface the missing migration added.

Alembic reads `DATABASE_URL` (via `Settings.effective_database_url`); with no
`.env` it falls back to
`postgresql+asyncpg://postgres:postgres@localhost:5432/boutique`. **Run
migrations as the owner role (`postgres`)** — the app role deliberately has no
DDL and `REVOKE ALL ON alembic_version FROM app_user`. Homebrew's initdb creates
a superuser named after *you*, not `postgres`; if the role is missing every
command in this runbook dies with `FATAL: role "postgres" does not exist`. See
the prerequisites table.

⚠ `uv` prints `VIRTUAL_ENV=…/Backend/.venv does not match the project
environment path .venv and will be ignored` on every single invocation if you
have another checkout's venv exported. Harmless — it is on stderr and `uv run`
uses the project's own `.venv` — but it will be the first line of almost every
output below.

### 2.2 `.env`

Write `"$REPO/backend/.env"` (this is the exact heredoc that was run — `$DB`
interpolates, nothing else does because every other value is a literal):

```bash
cat > "$REPO/backend/.env" <<EOF
APP_ENV=dev
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/$DB
BASE_DOMAIN=localtest.me
SMS_PROVIDER=fake
OTP_DEV_CODE=424242
PAYMENT_PROVIDER=fake
GATEWAY_SECRET_BOX=fake
DEPOSIT_HOLD_SECONDS=120
# MEDIA_BUCKET left unset: dress photo UPLOAD answers 503, everything else works.
EOF
```

`.env` is gitignored (`.gitignore:193`) and, critically, it is **per checkout** —
a worktree does not inherit the main checkout's. Confirm you wrote the one the
process will actually read: `Settings` resolves `env_file=".env"` relative to the
**current working directory**, so it is `$REPO/backend/.env` that counts, not
`~/…/Ryan + rawad + mrwen/backend/.env`.

Every field in `Settings` has a default or is Optional and both boot-failing
validators are gated on `app_env != "dev"`, so **nothing here is required to
boot** — it is required to *walk the journeys*:

- `SMS_PROVIDER=fake` — unset ⇒ `UnconfiguredSmsSender`, `POST
  /storefront/otp/send` answers `503 SMS_NOT_CONFIGURED`, and the booking flow
  structurally dead-ends at step 4.
- `OTP_DEV_CODE=424242` — **effectively mandatory.** `FakeSmsSender` writes to an
  in-memory list the browser cannot read, and the real code is 6 random digits
  with a 300 s TTL. Without a dev code there is no way to type a valid code.
- `PAYMENT_PROVIDER=fake` + `GATEWAY_SECRET_BOX=fake` — the secret box is
  *required whenever a provider is set* (validator:
  `GATEWAY_SECRET_BOX is required when PAYMENT_PROVIDER is set`). `fake` also
  registers `GET /fake-pay` — the hosted page with **Pay** and **Decline**
  buttons that POST a correctly-HMAC'd webhook. Without it the deposit redirect
  falls through to the storefront catch-all and the sweeper cancels the hold one
  tick later. ⚠ **`/fake-pay` does *not* 404 when the provider is unset.**
  `/fake-pay` is neither in `EXEMPT_PATHS` nor under a reserved first segment,
  so `_SpaFallbackRoute` claims it and answers the storefront **HTML shell with
  200**. Verified both ways — the discriminator is the bare path with no query:

  ```bash
  curl -sS -o /dev/null -w '%{http_code} %{content_type}\n' http://demo.localtest.me:8000/fake-pay
  # 400 application/json   → route IS registered (VALIDATION_ERROR: query.session required)
  # 200 text/html          → route is NOT registered; PAYMENT_PROVIDER is not `fake`
  ```

  A 404 from `/fake-pay?session=…` means the route is registered and there is no
  payment row for that session id — the opposite conclusion.
- `DEPOSIT_HOLD_SECONDS=120` — so you can watch `הזמן שמור לך פג` without waiting
  the default 900 s.

⚠ `Settings.model_config` is `extra="ignore"`: **a typo'd variable is silently
discarded.** Do not trust the file — trust the startup INFO lines (§2.7) and
`/health`.

⚠ **Do not set `APP_ENV=staging` or `production` for a browser walkthrough.**
`secure_cookies` is `True` whenever `app_env != "dev"`, so `boutique_session` is
set `Secure` and the browser drops it over plain `http://` — login "succeeds" and
the console bounces straight back to the login form.

### 2.3 Build the SPAs and copy them into the backend upload

```bash
cd "$REPO/frontend" && pnpm -r build

cd "$REPO"
rm -rf backend/app/static
mkdir -p backend/app/static
cp -R frontend/apps/manage/dist     backend/app/static/manage
cp -R frontend/apps/storefront/dist backend/app/static/storefront

# same assertion CI makes before `railway up`
test -s backend/app/static/manage/index.html
test -s backend/app/static/storefront/index.html
find backend/app/static -type f | wc -l      # expect ~85; under 20 = truncated copy
```

Those four lines are verbatim `.github/workflows/ci.yml` (the "Copy the SPAs into
the backend upload" step). `apps/manage` builds with `base: "/manage/"`; there
are **no `VITE_*` variables** — both SPAs use relative paths and are same-origin
with the API.

**Without the copy every browser step below is unwalkable while `/health` still
answers 200.** Absence is a supported state by design, not a boot failure — so
you must check rather than assume.

`app/main.py` does have a `logger.info("SPA bundles not found under %s — serving
the API only", …)` for exactly this, **but you will never see it** (§2.7: uvicorn
does not configure the root logger). Check the observable instead:

```bash
curl -sS http://demo.localtest.me:8000/
# <!doctype html> …                → bundles are on disk
# {"detail":"Not Found"}           → they are NOT; `_register_spas` returned
#                                    early and `/` has no route at all
# {"error":{"code":"TENANT_NOT_FOUND", …}}  → different problem: no active
#                                    boutique at that host (§2.5)
```

⚠ **Both failure modes are HTTP 404 on `/`.** The status code alone cannot tell
"the SPA copy did not happen" from "the tenant is not active" — read the *body*.
`{"detail":"Not Found"}` is Starlette's own (no route); the `error.code` envelope
is the app's.

#### Why `backend/app/static/` is untracked *and* must never be gitignored

Read `app/main.py` around `STATIC_ROOT` / `_register_spas`. The directory is:

- **Untracked** — it is a build artifact; committing ~85 hashed bundles per merge
  is noise, and it only needs to exist inside a CI runner.
- **Deliberately absent from `.gitignore`** — `railway up` *respects
  `.gitignore`*, and it drops an ignored path from the upload **with no error at
  all**. A gitignored static tree means a green CI run and a production origin
  that serves nothing but JSON. CI proves this rather than trusting the comment:
  it runs `git ls-files --others --ignored --exclude-standard --directory
  backend/app/static` over the *whole* tree and fails if anything comes back.
- Named `static/` and not `dist/` or `staticfiles/` — `.gitignore` already
  ignores both of those names anywhere in the tree.

To hide your local copy from `git status` without teaching git to hide it from
Railway, use the **local, uncommitted** exclude file:

```bash
echo 'backend/app/static/' >> "$(cd "$REPO" && git rev-parse --git-common-dir)/info/exclude"
```

`.git/info/exclude` is per-clone and never leaves your machine, so the upload is
unaffected. (In a worktree, `--git-common-dir` is what points at the shared
`.git`; `--git-dir` would give you the worktree's private directory.)

### 2.4 Run

```bash
cd "$REPO/backend" && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

⚠ **Order matters: build and copy the SPAs (§2.3) BEFORE this, or restart after.**
`_register_spas` runs once, at app import, and adds one exact route per file plus
two `StaticFiles` mounts. `--reload` watches `*.py`, so dropping the bundles in
afterwards changes nothing until you restart — the app keeps serving the API only
and `/` keeps 404ing. Same for editing `.env`.

To leave it running in the background while you drive curl:

```bash
cd "$REPO/backend" && nohup uv run uvicorn app.main:app \
  --host 127.0.0.1 --port 8000 > /tmp/uvicorn.log 2>&1 &
# stop it with: pkill -f "uvicorn app.main:app"
```

Second terminal, **optional but required for two assertions** (the deposit-hold
sweeper and the reminder poller):

```bash
cd "$REPO/backend" && uv run python -m app.worker
```

> The worker drains `scheduled_messages` every `WORKER_POLL_INTERVAL_SECONDS`
> (60). It is also the only thing that expires deposit holds. **Leave it off**
> while you are fishing the manage-link token out of the database (§3.A step 10)
> — a drained reminder row clears the raw token.

#### The IPv6 trap — read this before you file "the app is broken"

`*.localtest.me` publishes **both** records:

```
$ dig +short demo.localtest.me A       →  127.0.0.1
$ dig +short demo.localtest.me AAAA    →  ::1
```

A server bound to only one family refuses the other outright. Verified on this
machine with uvicorn bound to `127.0.0.1` (`lsof -nP -iTCP:8000 -sTCP:LISTEN`
shows one `IPv4 … 127.0.0.1:8000 (LISTEN)` row and nothing else):

```
$ curl http://[::1]:8000/health        →  curl: (7) Failed to connect to ::1 port 8000
$ curl http://127.0.0.1:8000/health    →  200
```

The browser's Happy Eyeballs falls back, so Chrome works either way — but a
`curl` script, or Vite's dev server (which in this repo binds `::1` only and
refuses every IPv4 attempt), will read as a dead app rather than a wrong bind.
**Bind explicitly.**

⚠ **`curl -4` / `curl -6` do NOT discriminate here — do not use them for this.**
On macOS, `curl -6 http://demo.localtest.me:8000/health` answers **200** against
an IPv4-only listener, because the system resolver hands libcurl the v4-mapped
form and the connection lands on the IPv4 socket:

```
$ curl -6 -v http://demo.localtest.me:8000/health
*   Trying [::ffff:127.0.0.1]:8000...
* Connected to demo.localtest.me (::ffff:127.0.0.1) port 8000
```

**Use the literal address forms instead** — `http://[::1]:8000/health` vs
`http://127.0.0.1:8000/health`. Those are the two that actually differ.

### 2.5 Provision a tenant

There is **no provisioning endpoint** — only the operator CLI. This does not need
the server to be running:

```bash
cd "$REPO/backend"
uv run python -m app.cli provision \
  --slug demo --name "בוטיק מודרין" --owner-email owner@demo.example
# password is read from getpass/stdin — never argv, never shell history
# → OK: provisioned (6be11d72-…)
```

`_read_password()` uses `getpass` **only when stdin is a tty**; otherwise it
reads one line. So in a script, pipe it — and note that an empty line is
rejected up front (`empty_password`), not turned into an unusable owner:

```bash
printf 'modryn-demo-owner-2026\n' | uv run python -m app.cli provision \
  --slug demo --name "בוטיק מודרין" --owner-email owner@demo.example
```

`uv run python -m app.cli list` prints `slug  status  name  created_at`:

```
demo	active	בוטיק מודרין	2026-08-04T06:05:27.429355+00:00
```

### 2.6 Seed browsable data

`scripts/seed_demo.py` drives the **real HTTP API**, so uvicorn (§2.4) must
already be up and the tenant must already exist:

```bash
cd "$REPO/backend"
uv run python scripts/seed_demo.py --help    # read the epilog; it restates both prerequisites
SEED_OWNER_PASSWORD='…' uv run python scripts/seed_demo.py
```

| Flag / var | Default | Notes |
|---|---|---|
| `--base-url` | `http://demo.localtest.me:8000` | **This is what selects the tenant** — the leftmost DNS label of its host, nothing else. |
| `--owner-email` | `owner@demo.example` | Must match the owner `provision` created. |
| `SEED_OWNER_PASSWORD` | — | Read from env, else prompted / stdin. Never argv. |
| `SEED_STAFF_PASSWORD` | `modryn-demo-2026` | The password every seeded staff member gets — you need it for journey C step 21. |

It seeds settings, appointment types, availability, staff, seamstress capacity,
dresses, fitting rooms, atelier tickets and a published terms version, then
verifies the storefront reads back. A clean first run ends:

```
SEEDED
  - settings: profile, toggles (deposits off), atelier bands + 30h default
  - appointment types: 4 created, 0 already present
  - availability: 6 weekly windows (Sun–Fri, Sat closed), 1 closure on …
  - staff: 5 created, 0 already present (all five roles)
  - seamstress capacity: רבקה לוי at 22h/week, אסתר פרידמן left on the boutique default
  - dresses: 5 created, 0 already present; size matrices replaced on all of them
  - fitting rooms: 3 created, 0 already present
  - atelier tickets: 3 created, 0 already present (each one also upserts its customer row)
  - terms: version 1 published (48h refundable window)
  - storefront: 4 appointment types, 230 bookable slots in the next 14 days
  - storefront: 5 public dresses, terms version 1
  - storefront <h1>: בוטיק מודרין
```

**Re-running is safe** — verified: a second run reports `0 created, N already
present` on every collection, `6 weekly windows replaced, exceptions left as-is`,
and `terms: version 1 already published, left alone`. Full-replace writes are
restated and every create either GETs-then-skips or treats its own 409 as success.

The `SIGN IN` block it prints is derived from `--base-url`, so under this
runbook's configuration it names `…:8000/manage` and `…:8000/` — the same origin
you are testing, not the Vite dev servers.

⚠ It does **not** seed bookings or customers. Journey A creates the first
booking; journey E's dashboard and CRM preconditions (bookings across several
weeks, two statuses, a repeat customer) still have to be built by walking journey
A a few times or by hand.

### 2.7 Smoke the boot

In this order — each line isolates one layer:

```bash
curl -sS http://demo.localtest.me:8000/health
# {"status":"ok","version":"0.1.0","media":"unconfigured"}   ← app is up

curl -sS -o /dev/null -w '%{http_code} %{content_type}\n' http://demo.localtest.me:8000/
# 200 text/html; charset=utf-8  → storefront shell is being served
# 404                           → EITHER the tenant is not active OR the §2.3
#                                 copy did not happen — read the body (§2.3)

curl -sS http://localhost:8000/
# {"error":{"code":"TENANT_NOT_FOUND","message":"No active boutique at this address."}}

curl -sS -o /dev/null -w '%{http_code} %{content_type}\n' http://demo.localtest.me:8000/manage
# 200 text/html; charset=utf-8  → console shell.  404 → same two causes as above.

curl -sS -o /dev/null -w '%{http_code}\n' http://demo.localtest.me:8000/manage/nope
# 404 → CORRECT. /manage is an EXACT route with no subtree, and `manage` is a
#       reserved first segment so the SPA catch-all declines it too.
```

⚠ **Do not use `/manage/settings` for that last check.** It answers **401**, not
404 — it is a real API route (`app/boutique/router.py`), and unauthenticated is
401. Same for `/manage/bookings`. `/manage/` with a trailing slash answers a
**307** to `/manage`. Only a path the API does *not* own, like `/manage/nope`,
demonstrates the missing subtree.

**Never use plain `localhost:8000`.** `extract_slug()` (`app/tenancy/slugs.py`)
takes the leftmost DNS label of `<label>.<BASE_DOMAIN>` from the `Host` header
and is the *only* source of tenant identity. A bare `localhost` has no label and
fails closed to the same generic 404 as an unknown slug, a suspended tenant, a
reserved subdomain (`admin api app assets cdn docs mail staging static status
support www`), an IP literal or a missing Host header.

Then browse:

- storefront → **http://demo.localtest.me:8000/**
- console → **http://demo.localtest.me:8000/manage**

Same origin. **That is the configuration under test.**

Then confirm the adapters are what you think. ⚠ **Not from the uvicorn log.**
`app/main.py` does emit `SMS sender: FAKE …`, `payment gateway: FAKE …`,
`secret box: FAKE …`, `media storage NOT configured …` and `SPA bundles not
found under … — serving the API only` — but they are `logger.info` on the `app.*`
logger, and **uvicorn configures only the `uvicorn*` loggers, never the root
one.** Root stays at WARNING with no handler, so every one of those lines is
dropped. Verified: they do not appear with `uv run uvicorn …`, and they do not
appear with `--log-level info` either. Do not conclude from their absence that
`extra="ignore"` ate a variable.

Ask the running app instead — each of these is one adapter, and each was run:

```bash
curl -sS http://demo.localtest.me:8000/health
# "media":"unconfigured"  → MEDIA_BUCKET unset (expected).  "configured" → S3 is on.

curl -sS -o /dev/null -w '%{http_code}\n' -H 'Content-Type: application/json' \
  -d '{"phone":"0501234567"}' http://demo.localtest.me:8000/storefront/otp/send
# 204 → SMS_PROVIDER is set.  503 SMS_NOT_CONFIGURED → unset or typo'd.

curl -sS -o /dev/null -w '%{http_code} %{content_type}\n' http://demo.localtest.me:8000/fake-pay
# 400 application/json → PAYMENT_PROVIDER=fake (route registered)
# 200 text/html        → not fake; the SPA catch-all answered

curl -sS -o /dev/null -w '%{http_code} %{content_type}\n' http://demo.localtest.me:8000/
# 200 text/html → the SPA copy happened.  200 application/json → it did not.
```

---

## 3. The journeys

Each table row is one step. **Proves** is why the step is in the runbook;
**failure means** is what to write in the bug report if it does not happen.

Aria labels and copy are Hebrew — the product ships Hebrew-only. Assert on the
**accessible name** and the `data-testid`, never on colour.

---

### A. Bride — catalog → book → terms → OTP → deposit → confirmation → manage link → cancel

**Preconditions** (owner-console setup, or `seed_demo.py`):

1. **שעות פעילות** — at least one open weekly day covering the date you book.
   Missing ⇒ `/book/slot` renders `booking.noSlots` and the dashboard forward tile
   renders `dashboard.forwardNoHours`.
2. **סוגי תורים** — at least one active appointment type. Missing ⇒ `/book` shows
   `booking.noTypes` and only a ContactPanel.
3. **מדיניות ביטולים** — a **published** terms version. Missing ⇒ `/book/terms`
   shows `booking.noTermsByPhone`, the flow is a dead end, and
   `data-testid="terms-setup-blocker"` is present.
4. **שמלות** — at least one dress with at least one size variant. Missing ⇒
   `catalog.empty`.
5. Deposit leg only: gateway credentials entered in the owner-only **סליקה
   ותשלומים** (the fake gateway wants `merchant_id`, `api_key`,
   `webhook_secret` — any values), and an appointment type with
   `deposit_required = true`.

| # | Do | Proves | A failure means |
|---|---|---|---|
| 1 | Browse `http://demo.localtest.me:8000/`. Title becomes `הקולקציה`. | Same-origin static serving + tenant resolution from the Host header. | §2.3 copy missing, or the tenant is not active. |
| 2 | Click a dress card → `/dress/{id}`, title `פרטי השמלה`. | The delegated document-level click listener upgrades a raw `<a href>` (packages/ui `DressCard`) to a client navigation, sets `document.title`, scrolls to top, focuses `#content`. | A full page reload = the listener is not attached. A 404 = the catch-all lost to something. |
| 3 | Click `קביעת תור למדידה` → `/book/slot/{dressId}`. Title `קביעת תור` for all six steps. | The CTA carries the dress id through the flow. | Losing the dress id here surfaces as a missing size chip at step 5. |
| 4 | Step **מועד**: press `המשך` with nothing selected. | R7 — the button is **never disabled**; it announces `צריך לבחור סוג פגישה כדי להמשיך` / `צריך לבחור מועד כדי להמשיך` instead of advancing. | A disabled button is the defect: a screen-reader user gets no reason. |
| 5 | Pick type / `תאריך` / `שעה`, `המשך`. Step **פרטים**: `שם מלא`, `טלפון נייד` = `0501234567`, pick a size chip (unavailable chips are still selectable, labelled `אפשר להזמין במיוחד`). `המשך`. | Slot materialization is real, and `booking.phoneHint` teaches exactly what `validatePhone` accepts. | Hint and validator disagreeing is a real reported-bug class. |
| 6 | Step **מדיניות ביטולים**: read the refund window and forfeit percent — each number inside its own `<bdi dir="ltr">`. Tick `קראתי את מדיניות הביטולים ואני מסכימה לה.`, `המשך`. Unticked ⇒ `כדי להמשיך צריך לאשר את מדיניות הביטולים.` | RTL/LTR number embedding on a legally binding surface. | A bare number in RTL flow renders `20%` as `%20` — wrong, and legally so. |
| 7 | Step **אימות טלפון**: `שליחת קוד אימות` (one label for first send *and* resend). Type `424242` into `קוד האימות`. | `POST /storefront/otp/send` always answers **204** and reveals nothing; the page shows `booking.otpSent` conditionally. `OTP_DEV_CODE` is accepted at verify via `hmac.compare_digest` beside the real code. | A 503 here = `SMS_PROVIDER` unset or typo'd. A non-204 = the endpoint became an enumeration oracle. |
| 8 | `אישור וקביעת התור` (in-flight label `קובעות את התור`). | `POST /storefront/bookings` end-to-end: **the payload-key contract between `apps/storefront` and FastAPI.** | A 400 `VALIDATION_ERROR` here is exactly the drift no CI job catches. |
| 9a | **No deposit** → `/book/confirm`. `h1` = `התור נקבע ב{boutique}`, the `מתי`/`מה`/`מידה` facts card, and `פרטי התור נשמרו אצלנו, וכדאי בכל זאת לצלם את המסך. אנחנו נחכה לך.` | `afterBooking()` routing; the boutique name interpolates. | An empty interpolation = the tenant name never reached the client. |
| 9b | **Deposit** → `/book/pay` (routed when `deposit_due && payment_session_id !== null`). One static `h1` `תשלום מקדמה` over all five states. State A auto-redirects via `handOff.leave()`; fallback link `מעבר לתשלום` under `אם הדף לא נפתח מעצמו, אפשר לעבור אליו מכאן.` | The hand-off is not a dead end without JS-driven navigation. | No fallback link = a blocked popup strands the bride mid-checkout. |
| 9c | On the hosted page at **`/fake-pay?session=…`** press **Pay**. Return; the page polls showing `מאשרים את התשלום`, then `navigate(..., {replace:true})` to `/book/confirm`. | The webhook is HMAC-verified for real (`sign_fake_webhook` → `POST /storefront/payments/webhook`), settles the payment and confirms the booking. Also assert the other four states: `התשלום לא הושלם` (**Decline** — its transaction id differs per outcome on purpose, so "decline then pay" is not a silent no-op), `הזמן שמור לך פג` (worker running + `DEPOSIT_HOLD_SECONDS=120`), and the bounded-poll timeout `עדיין לא קיבלנו אישור על התשלום. אין צורך לשלם שוב…` | A 400 on the webhook = amount mismatch. A stuck poll = the confirm-side write never happened. **A 404 on `/fake-pay?session=…` means the route IS registered and no payment row matches that session id** — not a config problem. `register_fake_pay` having been skipped shows up as a **200 HTML storefront shell** instead (the SPA catch-all claims the path); see §2.2. |
| 10 | Book a slot **≥24 h out**, then read the raw manage token: `psql -d "$DB" -tAc "select manage_token from scheduled_messages where status='pending' order by created_at desc limit 1"` | This is the **only** place the raw token is readable. `bookings.manage_token_hash` is sha256-only and `message_log.body` is masked by `mask_manage_link`. | Empty result ⇒ either the appointment is <2 h out (`REMINDER_SUPPRESS_UNDER_SECONDS`, no reminder scheduled, no raw token anywhere) or the worker already drained the row and cleared it. |
| 11 | Browse `/b/{token}`, title `התור שלך`. Press `אישור הגעה` → the button is **replaced** by `ההגעה אושרה. נתראה.` and the status region announces it. | The tokenized customer page; a capability URL that the router deliberately does **not** validate. | A dress grid instead = the `/b/` match fell through to the catalog. |
| 12 | Press `ביטול התור` — the **reveal**, not the cancellation. Panel: `לבטל את התור?`, policy line `לפי המדיניות שאישרת, אפשר לבטל עד {n} שעות לפני המועד.`, consequence line (`לא נגבה תשלום…` when `deposit_taken` false, `המקדמה מטופלת בהתאם למדיניות הביטולים של הבוטיק.` when true). Confirm with `אישור הביטול` (the page's only `danger` control) or back out with `השארת התור`. | One tap never cancels an appointment. | A single-tap cancel is a P0. |
| 13 | After cancel: `התור בוטל.` + `קביעת תור חדש`. Rebook the same slot. | Both partial unique indexes exclude `status='cancelled'`, so the seat is genuinely free again. | A `SLOT_UNAVAILABLE` on rebook = the index predicate is wrong. |
| 14 | `/b/{garbage}` → `הקישור הזה כבר לא תקף.` + `לכל שאלה על התור, אפשר להתקשר לבוטיק.` Unpaid deposit hold → `התור שמור עבורך וממתין לתשלום המקדמה.` with **both** action buttons *absent* (not disabled). Past appointment → `המועד הזה כבר עבר.` | One body for unknown/rotated/malformed tokens (no oracle); `BOOKING_AWAITING_PAYMENT` has its own code so a mid-checkout bride is never told she was cancelled. | Distinguishable 404s = a token-shape oracle. |
| 15 | **⚠ Reschedule is OWNER-side.** `/b/{token}` has only confirm-attendance and cancel. Go to console → **תורים** → open the booking → `שינוי מועד` → RescheduleDialog → `עדכון המועד` → cue `המועד עודכן.` A cancelled booking offers `קביעת מועד חדש ושחזור התור` instead. | The customer's existing link points at the new time (`upsert_reminder` re-points the pending row's token in the same transaction). | A dead link after reschedule = the token was rotated when it should not have been. |

---

### B. Walk-in — QR → `/checkin` → ticket → live position → public `/queue` board

**Preconditions.** Tenant reachable. The check-in form is **withheld entirely**
while `GET /storefront/boutique` is loading or failed, because `checkin.notice`
and `checkin.optIn` both interpolate `{{boutique}}` and may never render
nameless — so the boutique row must exist and the storefront read budget
(`STOREFRONT_READ_MAX_PER_WINDOW`, 6000/60 s per tenant) must not be spent. No
staff, rooms or dresses needed for the customer half.

| # | Do | Proves | A failure means |
|---|---|---|---|
| 1 | Console → **קוד סריקה** (roles ALL — the payload is a public URL). Read `כתובת הרישום:` and the QR image (alt `קוד QR שמוביל לטופס הרישום לתור`). `הדפסה` → poster `לרישום לתור אפשר לסרוק את הקוד`. | `CheckinQrService` builds the URL from `BASE_DOMAIN`, not the request Host. | A `localhost` URL on the poster = the service read the wrong source. |
| 2 | Open that URL → `/checkin`. `h1` and title `רישום לתור`. Expand `מה קורה אחרי הרישום?`. | The public-facing guide hint (F60) states **only queue facts**. `checkin.notice` is **always visible, never behind the disclosure** — it is the notice at the moment of collection. | A collapsed notice is a privacy defect, not a layout preference. |
| 3 | Fill `שם מלא`, `טלפון נייד`, pick `סוג הביקור` (`מדידת כלה` / `שמלת ערב`). Unpicked ⇒ `צריך לבחור סוג ביקור כדי להמשיך`. Optionally tick the marketing opt-in. `הצטרפות לתור` (in-flight `רושמות אותך לתור`). | `POST /storefront/checkin` → 201. | 400 here = payload-key drift on the second anonymous write path. |
| 4 | Lands on `/q/{ticket_id}`, title `מקומך בתור`. **Assert the title never carries the ticket id.** | The id is the capability; the tab strip is read over a shoulder in a shop. | An id in the title leaks a capability. |
| 5 | Assert `data-testid="queue-position"` and `"queue-number"`, the status word `ממתינה`, and the freshness line — three textually **distinct** states: `עודכן {time}` / `העדכון האחרון היה {time}` / `העדכון מושהה. עודכן {time}`, each followed by the time in its own `<bdi dir="ltr">`. | Freshness is conveyed in words. | A class-only difference between the three is the colour-alone defect this assertion exists to catch. |
| 6 | Press the pause control — **one** button whose accessible *name* flips between `השהיית העדכון` and `חידוש העדכון` (no `aria-pressed`, no `aria-label` variant). The `role="status"` region announces `העדכון האוטומטי הושהה` / `העדכון האוטומטי חודש`. | SC 2.2.2 Level A. The live region matters because a screen reader does not reliably re-announce an already-focused control that renamed itself under the press. Poll budget: 30/60 s per ticket. | Silent rename = the pause is invisible to the user who most needs it. |
| 7 | Reopen `/checkin` in the same tab. The courtesy pointer `הרישום האחרון שנעשה מהמכשיר הזה` links back to `/q/{id}`. | Labelled as what it **is**, never "your place in the queue" — on a shared door tablet the slot holds someone else's ticket. | Possessive wording on a shared device is a privacy defect. |
| 8 | Browse `/queue` (**exact match** — no id, no token, no query). `h1` `ממתינות בתור`, title `לוח התור`. Assert `data-testid="queue-board"`, one `"queue-board-row"` per waiting ticket showing **only the first whitespace-delimited token of the entered name**, and **no phone number anywhere**. | The public wall board is minimum-disclosure by construction. | A surname or a phone on a wall screen is a P0. |
| 9 | Empty board: `אין כרגע ממתינות` + `אפשר להצטרף לתור בסריקת הקוד שבבוטיק.` + `data-testid="queue-board-empty"` — **and the freshness line must still render.** | Without freshness, an empty board is indistinguishable from a crashed one. | Missing freshness on empty = the failure mode is invisible. |
| 10 | With more waiting than rows on screen: `data-testid="queue-board-overflow"` reads `ועוד {count} בתור`, **computed as the difference**, never echoed from the payload. | The count cannot disagree with the rows shown. | An echoed count drifts the moment the payload is truncated server-side. |
| 11 | After a staffer presses `קראי` (journey C), the board row shows the **word** `גשי לדלפק` beside the name. On the holder's own `/q/{id}` the wording differs: `אפשר לגשת לדלפק`. | The highlight is never background-colour alone; the two surfaces address different readers. | Colour-only highlight fails at three metres and for colour-blind staff. |
| 12 | `/q/{garbage}` → `הקישור הזה כבר לא תקף.` + `אפשר להירשם לתור מחדש…` + `רישום לתור חדש` back to `/checkin`. **Must not fall through to the dress grid.** | `QUEUE_PATH` is matched **before** the catalog fallthrough. Misses charge `CHECKIN_POSITION_MAX_MISSES_PER_WINDOW` (120/60 s); hits keep answering 200. | A dress grid leaves a woman in the doorway with no way to learn her place is gone. |
| 13 | Board poll budget is **per tenant**: `QUEUE_BOARD_MAX_PER_WINDOW` 600/60 s (sized for ~50 concurrent pollers — wall screens *plus every phone in the room*). | Each budget is its own `FixedWindowRateLimiter` instance: `max_attempts` lives on the limiter, so two keys on one instance share one ceiling and trip each other. | A 429 on the wall board at normal load = a budget was collapsed onto a shared instance. |

---

### C. Floor — login → board → check-in → staff cards + break → fitting rooms → waitlist dispatch → SOS → ack → 30 s escalation

**Preconditions.** In **צוות** (owner-only) create one each of `shift_manager`,
`reception`, `sales_assistant`, `seamstress` — the password is shown once and
must be handed over in person (`יש למסור את הסיסמה לעובדת בעצמך…`). At least one
**confirmed booking for today** (Asia/Jerusalem), else `אין תורים היום`. At least
one fitting room via **ניהול חדרים** → `הוספת חדר`, else `עדיין לא הוגדרו חדרי
מדידה`. At least one waiting queue ticket (run journey B first), else `אין
ממתינות בתור` and `קחי את הבאה` answers `rooms.error.QUEUE_EMPTY`.
**Two browser contexts are required for the SOS leg — the overlay never rises on
the raiser's own device, by design.**

| # | Do | Proves | A failure means |
|---|---|---|---|
| 1 | `/manage` → LoginForm, `h1` `MODRYN — כניסה לניהול הבוטיק`. Fill `אימייל` + `סיסמה`, press `כניסה`. | `boutique_session` is HttpOnly, SameSite=Lax and **host-only** (no Domain attribute) — one tenant's cookie can never travel to another slug. Failures are rate-limited (5 / 900 s) and every attempt, including failures, is committed to the per-tenant audit log. | A `Domain=` attribute is a cross-tenant session leak. A `Secure` flag over http means `APP_ENV` is not `dev` (§2.2). |
| 2 | Owner lands on **סקירה**. Click **לוח היום** → `BoardSection` above `FloorPanel`, board **first**. | Row 0 (`dashboard`) is what makes the initial `useState` and the `reachable[0]` fallback agree. | Landing anywhere else = the nav filter and the initial state disagree. |
| 3 | Assert `data-testid="board-day"` (`היום · {date}`), `"board-summary"` (`הגיעו {ratio}`), `"board-now"` (the `«עכשיו {time}»` divider, scrolled into view **once**), `"board-freshness"`/`"board-updated"` (`עודכן {time}` vs `אין עדכון מאז {time}` + `ייתכן שהמידע אינו עדכני.`). | Jerusalem-day computation against a real clock and real rows. | The `עכשיו` divider off-screen ⇒ the growing floor panel below pushed the one-shot `scrollIntoView` target out of view. |
| 4 | `הגיעה` on an arrival row (aria `הגיעה — {name}, {time}`) → row flips to `נרשמה הגעה · {time}`, cue `נרשמה הגעה עבור {name}.` Then `ביטול הרישום` (aria `ביטול הרישום — {name}, {time}`) → cue `הרישום בוטל עבור {name}.` | `POST /manage/bookings/{id}/check-in` and `…/undo-check-in`; the aria label disambiguates identical buttons in a list. | Bare `הגיעה` labels make the row unusable by screen reader. |
| 5 | `השהיה` (aria `השהיה — עדכון הלוח`) → `העדכון מושהה. הלוח לא יתעדכן עד לחידוש.`, freshness becomes `מושהה · עודכן {time}`. `חידוש` → `העדכון חודש.` Also assert the idle stop `העדכון הופסק אחרי {minutes} דקות ללא פעילות.` | The board screen carries **two independent** pause controls (board's and the floor panel's) with distinguishable accessible names — `board.pauseAria` vs `floor.pauseAria`. | Two identically-named pause buttons on one screen is an ambiguity defect. |
| 6 | Staff cards: assert the three status **words** `פנויה` / `בהפסקה` / `תפוסה`. `להפסקה` (aria `להפסקה — {name}`) → `בהפסקה` with `מאז {time}`, cue `נרשמה הפסקה עבור {name}.` Then `חזרה` → `ההפסקה הסתיימה עבור {name}.` | `POST /manage/floor/staff/{id}/break/start` and stop; status is never colour alone. | Colour-only status fails on a shop-floor tablet in sunlight. |
| 7 | Fitting rooms (**חדרי מדידה**): on a `פנוי` tile press `תפיסת החדר` (aria `תפיסת החדר — {room}`) → tile flips to `תפוס` with `לקוחה`, `כבר {n} דק'` (or `זה עתה`) and the holder. `הוספת שמלה` → pick `שמלה` + `מידה` → cue `השמלה נוספה לחדר: {dress}.`; `הסרה` removes it. | `POST /manage/floor/rooms/{id}/claim`; the elapsed-minutes formatter has a real clock under it. | A `NaN דק'` = the timestamp never round-tripped as UTC. |
| 8 | `העברה לעמיתה` (**elevated only** — owner/shift_manager): pick under `העברה אל`, press `העברה` → cue `החדר הועבר אל {name}.` With nobody free: `אין עכשיו עמיתה פנויה לקבל את החדר.` Then `שחרור` → `POST /manage/floor/assignments/{id}/release`, cue `החדר שוחרר: {room}.` | Role gating on a *sub-control*, not just a nav row. | A visible transfer control for a reception role = the server is the only guard left. |
| 9 | Waitlist **take-next**: on a free, active tile with `waiting > 0` press `קחי את הבאה` (aria `קחי את הבאה בתור — {room}`) → cue `הלקוחה שובצה: {room}.` Empty queue → `אין ממתינות בתור.` | `POST …/take-next`; the pull direction of dispatch. | A 409 on a genuinely free room = the occupancy read raced the claim. |
| 10 | Waitlist **push-assign**: from **ממתינות בתור** press `שבצי לחדר` on a row (aria `שבצי לחדר — {name}`) → dialog `שיבוץ לחדר — {name}` → `שיבוץ`. No room free → the row shows `אין חדר פנוי כרגע.` | `POST …/assign`; the push direction. **This is a real `<dialog>` in a real browser** — tab-trap, Esc-to-close and focus return are only measurable here. | jsdom stubs `showModal()` as `this.open = true`, so every vitest focus/trap/Esc assertion measures the stub and **cannot fail**. |
| 11 | Waitlist **call**: `קראי` (aria `קראי — {name}`) → row shows `נקראה`, cue `הקריאה נרשמה.` Go back to `/queue` (journey B step 11) and confirm `גשי לדלפק` appeared. | Cross-surface: a console write changes an anonymous public board. | The clearest single proof that the two halves are actually one system. |
| 12 | Waitlist **skip** (elevated): `דלגי` (aria `דלגי — {name}`) → `הועברה לסוף התור.`, row badged `דילגו עליה פעם אחת`. A **second** skip opens the confirm `דילוג נוסף יסיר את {name} מהתור. להמשיך?` — confirm with `אישור ההסרה` or back out with `השארה בתור`. | A second tap must never silently escalate to removal. | Silent removal on the second tap is a P0. |
| 13 | Waitlist **finish**: release the room she sits in (`שחרור`) — that is what closes her visit; her `/q/{id}` then reads `הביקור הזה הסתיים.` Removing her outright is `הסרה` (elevated, confirm `להסיר את {name} מהתור?`) → cue `הוסרה מהתור.` | The two exits are distinct and the customer-facing wording follows. | A finished visit still showing a position number is a stale-read bug. |
| 14 | **SOS raise — walk both trigger sites.** (a) `SosCentre`'s `קריאה לעזרה`: encodes **no** permission, all five roles, always present. (b) The room-tile raise: rendered **only** on the tile the signed-in staffer occupies (`assignment.staff_user_id === selfId`), prefills that room, aria `קריאה לעזרה — {room}`. | Neither opens with a page — both open `SosRaiseDialog`, so a mis-tap costs one Esc. | A trigger that pages immediately makes staff afraid to touch it. |
| 15 | In the dialog (`קריאה לעזרה`): pick `למי לקרוא` (default `מנהלת המשמרת`), optionally `מה צריך` (marked `לא חובה`), `שליחת הקריאה` → cue `הקריאה נרשמה.` Calling yourself → `אי אפשר לקרוא לעצמך.` Target not connected → `לא מחוברת עכשיו. הקריאה עברה למנהלת המשמרת.` with an `הבנתי` acknowledgement. | Fallback routing is surfaced, not silent. | A silent fallback means nobody knows who is coming. |
| 16 | In the **second** context (the target's, or the shift manager's): the alert appears in `SosCentre`, status `פתוחה`, line `{name} קוראת לעזרה`, location `מיקום …` or `לא בחדר מדידה`, `מאז {time}`. **The raiser's own device must not get the overlay.** | Two real sessions, two real cookies, one shared server state. | The raiser seeing her own overlay is the design being inverted. |
| 17 | **Ack**: `אני מגיעה` (aria `אני מגיעה — הקריאה מ{name}`) → cue `הקריאה התקבלה.`; the raiser's screen reads `{name} מגיעה.` A second acker gets `כבר מגיעה.` / `מישהי אחרת כבר מגיעה.` | `SOS_ALREADY_ACCEPTED` carries `details` naming the acceptor — a 409 that says "somebody" is unanswerable. | An anonymous 409 forces a second GET that races the resolve it is describing. |
| 18 | **30 s escalation**: raise a fresh alert and **do not ack**. Press `הסתרה` first (cue `ההתראה הוסתרה.`, collapsed counter `קריאות עזרה · {count}`), then wait ~35 s (the board polls every 5 s). Assert: the badge **word** `ללא מענה` appears, and `SosOverlay` **rises full-screen** on the fallback shift manager's device. | `_escalated()` is computed per response against **one shared `server_now`** — no worker, no column. The overlay's remount key is `${alert.id}:${alert.escalated}:${alert.stalled}`, so dismissing at t<30 s must **not** suppress the t=30 s rise. | A dismissal that permanently silences an escalation is a safety defect. This is a wall-clock assertion — it is only real here. |
| 19 | **Stall**: ack an alert and leave it. After `STALLED_AFTER` the badge `אין תזוזה מאז שאושרה` appears and the overlay re-rises. Close with `נפתר` (aria `נפתר — הקריאה מ{name}`) → cue `הקריאה נסגרה.` The raiser can withdraw with `ביטול הקריאה`, but only before an ack (`{name} כבר מגיעה. אפשר לסמן «נפתר» במקום.`). | The second silence uses the same mechanism as the first. | A stall that never re-rises means an accepted-and-forgotten alert. |
| 20 | **Session end**: expire or delete the session server-side (`delete from sessions where …`), then let any poll tick. The 401 is classified at **one** site inside `SosProvider` → `onSessionEnded` → `setStaff(null)` → the whole console drops to `LoginForm`. Board and floor also carry `תוקף החיבור פג. צריך להתחבר מחדש.` with `רענון הדף`. | There is **no fetch interceptor** — without this one site, the console would keep rendering a working-looking shell over a dead emergency channel. | A console that still paints after the session dies is the worst possible failure on this surface. |
| 21 | **Role gating** — the server is the control, the nav is cosmetics. Sign in as **reception**: exactly **one** row, `הצוות בקומה`, and she lands on it. As **seamstress**: exactly **two**, `הצוות בקומה` then `תפירה`, in that order. As **shift_manager**: **eight** rows, no `צוות` and no `סליקה ותשלומים`. Then confirm the server **403s** a shift manager on `/manage/staff/*` independently of the hidden row. | `NAV` is filtered by `item.roles.includes(staff.role)` and `activeKey = reachable.some(…) ? section : reachable[0]`. The counts are also asserted by `Nav.test.tsx` — here you additionally prove the *server* agrees. | A hidden row that the API still serves is the whole reason this step exists. |

---

### D. Atelier — intake → kanban → seamstress load bars

**Preconditions.** Signed in as owner, shift_manager or seamstress
(`ATELIER_ROLES` — reception and sales_assistant are refused by the router, which
spells the three literals so a sixth role fails closed). At least one **active**
seamstress, else `אין תופרות רשומות.` (owner variant adds `… אפשר להוסיף במסך
הצוות.`). Set weekly hours per seamstress or a boutique default, else a row reads
`לא הוגדרה קיבולת` and gets **no bar**.

| # | Do | Proves | A failure means |
|---|---|---|---|
| 1 | Nav row **תפירה**. `h1` `לוח התפירה`. Empty state: `אין עדיין כרטיסי תפירה` + `כל כרטיס עובר חמישה שלבים: התקבל, בעבודה, בקרה, מוכן, נמסר…` | The section mounts **alone**, never beneath the board — so a workroom phone runs one poll loop, not two. | Two poll loops on a phone in a back room is a battery and rate-budget bug. |
| 2 | `כרטיס חדש` → fill `שם הלקוחה` (required — `צריך שם לקוחה.`), `טלפון` (`מספר הטלפון אינו תקין.`), `תאריך יעד` (required; a past date is allowed with `התאריך שנבחר כבר עבר. אפשר להמשיך.`), `הערכת זמן` — the five bands `חצי שעה`/`שעה`/`שעתיים`/`חצי יום`/`יום מלא` rendered `{band} · {minutes} דק׳`. Optionally `שם השמלה`, `מידה`, `הערות`. `פתיחת כרטיס` → cue `{name} — נפתח כרטיס.` | `POST /manage/atelier/tickets`; a past due date warns but does not block. | A hard block on a past date makes back-dated intake impossible. |
| 3 | Assert the five columns and counts: `התקבל`, `בעבודה`, `בקרה`, `מוכן`, `נמסר`, header shape `{stage} · {total}`, empty column `אין כרטיסים בשלב זה`. On narrow screens use the stage rail (aria-label `מעבר לשלב`). | Kanban is navigable without horizontal drag. | No rail on narrow = unusable on the phone this screen targets. |
| 4 | `לשלב הבא` (aria `לשלב הבא — {name}`) → `POST …/stage/advance` → cue `{name} — שלב חדש: {stage}.` Walk intake → in-progress → `בקרה` → `מוכן` → `נמסר`. Jump with `העברה לשלב` → target → `העברה` (`POST …/stage/skip`). Step back with `ביטול שלב` → cue `{name} — חזרה לשלב: {stage}.` | All three stage transitions, and `TICKET_STAGE_CONFLICT` if two staffers race. | A generic `CONFLICT` here forces the console to branch on a message string. |
| 5 | `תופרת` → `שיוך` (aria `שיוך — {name}`) → cue `שויך ל{seamstress}.` Option rows carry live capacity: `{name} · נותרו {hours} שעות` or `{name} · {hours} שעות משויכות`. Seamstress self-serve: `לקחת` (aria `לקחת — {name}`); release → `השיוך בוטל.` Unassigned cards badged `לא משויך`; a card on a deactivated staffer reads `תופרת שאינה פעילה`. | Capacity is computed live at the point of decision, not on a separate screen. | `TICKET_ALREADY_ASSIGNED` must name the taker — the next tick should show her. |
| 6 | `עריכה` (form `עריכת כרטיס`, submit `שמירה`); `מחיקה` → cue `{name} — הכרטיס נמחק.` Overdue cards badged `באיחור` beside `יעד {date}`. | Overdue is a word beside the date. | Colour-only overdue is invisible at a glance across a workroom. |
| 7 | Roster `תופרות · {total}`: each row `{hours} שעות עד {date} מתוך {capacity}` — or `{hours} שעות` with no capacity — plus total `סה״כ {hours} שעות בתור`. Over the ceiling shows the **word** `עומס יתר`. A row on the boutique default is marked `ברירת מחדל של הבוטיק`. Unassigned work gets its own **bar-less** row `לא משויך · {hours} שעות`. | One `overloaded()` predicate drives the word, the bar **and** the assign cue — they cannot disagree. | A bar without the word = colour-alone overload. A bar on `לא משויך` = a denominator that does not exist. |
| 8 | `שעות` (aria `שעות — {name}`) → dialog `שעות שבועיות` → `שעות בשבוע` (help line names the boutique default) → `שמירה` → cue `{name} — עודכנו השעות.` Clear with `חזרה לברירת המחדל` → cue `{name} — חזרה לברירת המחדל.` Invalid: `צריך מספר שעות שלם ולא שלילי.` | Another real `<dialog>` — see journey C step 10. | Same jsdom blind spot. |
| 9 | Poll chrome mirrors the board's: `רענון` / `השהיה` (aria `השהיה — לוח התפירה`) / `חידוש`; freshness `עודכן {time}` vs `אין עדכון מאז {time}`; pause line `העדכון מושהה. לוח התפירה לא יתעדכן עד לחידוש.`; idle stop `עדכון לוח התפירה הופסק אחרי {minutes} דקות ללא פעילות.` Assert `data-testid="atelier-cue"` carries every mutation announcement, and truncation reads `מוצגים הכרטיסים הדחופים ביותר…` | One poll idiom across three surfaces, each with its own distinguishable aria label. | Divergent poll chrome means staff learn three interfaces. |

---

### E. Cross-cutting — guide, KPI dashboard, customers CRM, staff CRUD

**Preconditions.** Owner signed in. For the dashboard to be anything but zeros:
bookings across several weeks in at least two statuses, some past-and-marked
(completed / no-show), at least two distinct customers with one repeat, and open
weekly hours in the next 7 days. For the customers list to be non-empty a
customer must have **verified her phone and booked** — the empty state says so:
`לקוחה נוספת לרשימה אחרי שהיא מאמתת את מספר הטלפון שלה וקובעת תור.`

| # | Do | Proves | A failure means |
|---|---|---|---|
| 1 | On **any** section press `מדריך`. Title `מדריך — {section}`, progress `שלב {step} מתוך {total} במדריך`, navigate `הבא`/`הקודם`, finish `סיום`, abandon `סגירה` or Esc. | `ConsoleShell` gets `<GuideOverlay section={activeKey}/>`, and `activeKey` is already role-filtered — a receptionist can only ever be offered floor's three steps. | A guide for a section she cannot reach teaches a screen that does not exist for her. |
| 2 | Assert step counts per section (`GUIDE_STEPS` in `lib/guide.ts`, in NAV order): dashboard 2, profile 3, hours 3, types 3, terms 2, catalog 3, bookings 3, customers 2, board 3, floor 3, atelier 3, checkinQr 2, staff 2, gateway 2. | Every section has ≥1 step — a zero-step section is unrepresentable (`satisfies Record<SectionKey, readonly [string, ...string[]]>` is the whole mechanism). | A "מדריך" button that opens nothing is the button lying. |
| 3 | **Dashboard**: `נכון לתאריך:`, `סך התורים שלא בוטלו בתקופה: {count}`, and the tiles — `תפוסה בשבעת הימים הקרובים` (`אחוז התפוסה`, `סך המקומות בטווח`, `מקומות שנתפסו`; with no open hours: `אין שעות פעילות פתוחות בטווח הזה, ולכן אין כאן מה לחשב.`), `תורים לפי שבוע` (caption `תורים שלא בוטלו, לפי שבוע`; columns `תחילת שבוע` / `תורים שלא בוטלו`), `ביטולים ואי־הגעה` (`שיעור הביטולים`, split `ביטולים ביוזמת הלקוחה` / `ביטולים ביוזמת הבוטיק`, `שיעור אי־ההגעה`, `תורים שעברו ולא סומנו`), `לקוחות בתקופה` (`סך הלקוחות` / `לקוחות חדשות` / `לקוחות חוזרות` / `שיעור החזרה`), `סוגי התורים המבוקשים`. | Every KPI is computed from real rows over a real Jerusalem week boundary. | An off-by-one week boundary only shows up against real data. |
| 4 | Assert the two honest-degradation strings rather than fabricated numbers: `אין עדיין מספיק נתונים לחישוב.` and `פחות מ־0.1%`. Assert the first-run note and the outage line `לא הצלחנו לטעון את הנתונים כרגע.` | This section's one fetch is what an out-of-enum role hits, so its outage copy must cover any `ApiError`. | `NaN%` or `0%` where the honest string belongs is a trust defect on a business metric. |
| 5 | **Customers**: search `חיפוש לפי שם או טלפון` (placeholder `שם או מספר טלפון`). Assert `data-testid="customers-count"` (`לקוחות ברשימה: {count}`), truncation `מוצגות {count} מתוך {total} לקוחות.`, no-results `אין תוצאות לחיפוש הזה` + `אפשר לנסות שם חלקי או ספרות מתוך מספר הטלפון.` | Search runs server-side against real rows. | A count that disagrees with the rows = a truncation the UI does not know about. |
| 6 | Open a card. Edit `הערות` (placeholder `מה כדאי לזכור לפעם הבאה`, help `ההערות נשמרות בכרטיס ונראות לצוות הבוטיק בלבד.`). Add a tag: type into `תגית חדשה`, `הוספה` (`data-testid="customer-tags"`); remove with `הסרה` (aria `הסרה של התגית {tag}`). Assert all four rejections: `תגית יכולה להכיל עד {n} תווים.`, `התגית הזו כבר קיימת בכרטיס.`, `התגית מכילה תווים שאי אפשר לשמור.`, and at the ceiling `אי אפשר להוסיף עוד תגיות. אפשר להסיר תגית קיימת ולנסות שוב.` | Client and server validation agree on all four. | A rejection surfacing as a generic error means the server's reason never reached the user. |
| 7 | `שמירה` → `השינויים נשמרו`; on failure `data-testid="customer-save-error"` carries `לא ניתן לשמור את השינויים כרגע.` **Then re-read the row in the list** and confirm `data-testid="customer-row-tags"` reflects the change. | Form-state sync after save — the API's response, not the local optimistic value, is what the list shows. | A stale list row after a successful save is the classic "did it save?" bug. |
| 8 | Same card: `היסטוריית תורים` and the **read-only** `יומן הודעות` (`יומן לקריאה בלבד. אי אפשר לערוך או למחוק רשומה.`) with kinds `קוד אימות`/`אישור תור`/`תזכורת`/`ביטול מטעם הבוטיק`/`שינוי מועד מטעם הבוטיק` and statuses `בהמתנה`/`הועברה לספק`/`נכשלה`. | With `SMS_PROVIDER=fake` **nothing leaves, so `בהמתנה` is the expected steady state — that is a supported deployment, not a bug.** | Do not file "SMS not sending" from this screen under the fake adapter. |
| 9 | **Staff CRUD** (owner only): create — `שם לתצוגה`, `אימייל`, `תפקיד` (owner / shift_manager / reception / sales_assistant / seamstress → `בעלת הבוטיק` / `אחראית משמרת` / `קבלה` / `יועצת מכירות` / `תופרת`), `סיסמה`, notice `יש למסור את הסיסמה לעובדת בעצמך. המערכת אינה מעבירה אותה לאיש.` → `הוספה לצוות`. Edit with `עריכה` → `שמירה`; changing **your own** password also requires `הסיסמה הנוכחית שלך` (`אפשר להשאיר ריק כדי לא לשנות את הסיסמה.`); your own row is marked `זו את`. Deactivate → `להשבית את הגישה?` → `השבתה`. | The full owner-only lifecycle against real password hashing. | — |
| 10 | Assert the four server refusals surface as **copy, not a generic error**: `כתובת האימייל הזו כבר משויכת לאשת צוות פעילה.` (DUPLICATE_EMAIL), `לבוטיק חייבת להיות בעלת בוטיק אחת לפחות.` (LAST_OWNER_REQUIRED), `אי אפשר לשנות את התפקיד של עצמך או להשבית את עצמך.` (STAFF_SELF_MANAGE), `הפעולה הזו זמינה לבעלת הבוטיק בלבד.` (NOT_AUTHORIZED — reach it by driving the API directly as a shift_manager). | Error **codes** are the contract; the console maps each to its own sentence. | A generic "something went wrong" on LAST_OWNER_REQUIRED leaves the owner unable to guess what to do. |
| 11 | **Logout handoff**: press `יציאה`. `handleLogout` clears `staff` but **not** `section`. Sign in as a shift manager and assert she does **not** land on `צוות`. | `activeKey` is derived at render from the filtered list, never stored. | Landing on a panel her role cannot reach is a role-leak through stale state. |

---

## 4. Teardown / reset

Between epics, reset to a known-empty database rather than debugging accumulated
state:

```bash
# 1. stop uvicorn and the worker — an open connection blocks DROP DATABASE
pkill -f "uvicorn app.main:app"
cd "$REPO/backend"
dropdb "$DB"
createdb "$DB"
uv run alembic upgrade head
printf '…\n' | uv run python -m app.cli provision \
  --slug demo --name "בוטיק מודרין" --owner-email owner@demo.example

# 2. start uvicorn again (§2.4), THEN seed — seed_demo drives the live API
SEED_OWNER_PASSWORD='…' uv run python scripts/seed_demo.py
```

If `dropdb` reports *database is being accessed by other users*, something still
holds a connection:

```bash
psql -d postgres -c "select pid, application_name from pg_stat_activity where datname='$DB'"
psql -d postgres -c "select pg_terminate_backend(pid) from pg_stat_activity where datname='$DB'"
```

**A throwaway database is dropped the same way** — that is the whole reason `$DB`
exists. `dropdb modryn_demo` after `pkill -f "uvicorn app.main:app"` leaves every
other local database untouched.

Rebuild the SPAs only when frontend source changed:

```bash
cd "$REPO/frontend" && pnpm -r build
cd "$REPO" && rm -rf backend/app/static && mkdir -p backend/app/static \
  && cp -R frontend/apps/manage/dist backend/app/static/manage \
  && cp -R frontend/apps/storefront/dist backend/app/static/storefront
```

Leave `.env` in place — it is gitignored and is the expensive part of the setup.

---

## 5. What this catches that CI does not

**Payload-key drift between backend and frontend.** The Playwright manage suite
stubs every `/manage` API call; its own header names this as Risk 6: *"A backend
change that renames a payload key passes every test in this file while breaking
production."* The storefront suite fixes its fixtures locally for the same
reason. Journey A step 8 (`POST /storefront/bookings`), journey B step 3 (`POST
/storefront/checkin`) and every console mutation in C and D are the **only**
places the two vocabularies are ever compared.

**Real `<dialog>` focus behaviour.** `setup.ts` stubs `showModal()` as
`this.open = true`. Every vitest assertion about focus trapping, Esc-to-close or
focus return therefore measures the stub and **cannot fail**. Journey C step 10
(`שיבוץ לחדר`), C step 12 (the second-skip confirm) and D step 8 (`שעות שבועיות`)
are real `<dialog>` elements in a real browser.

**Wall-clock behaviour.** The SOS 30 s escalation (`_escalated()` computed per
response against one shared `server_now`, no worker, no column), the 5 s poll
cadence, the idle-stop timer, and the deposit sweeper's expiry are all real-time
properties. A frozen clock in a unit test proves the predicate; only journey C
step 18 proves the *loop* around it — including that a dismissal at t<30 s does
not suppress the t=30 s rise, which is the remount-key behaviour.

**Real same-origin static serving.** `_register_spas` runs **last**, after every
`include_router`. `_SpaFallbackRoute.matches` *declines* (`Match.NONE`) rather
than 404s for `EXEMPT_PATHS` and the reserved first segments `{manage,
storefront}` — because Starlette returns on the first full match, and a catch-all
that fully matched `GET /storefront/otp/send` would win outright and destroy the
POST route's 405. `/manage` is an exact route with **no** subtree. All of that is
route-table behaviour that only exists once the bundles are actually on disk —
and the backend suite deliberately hides them (`spa_static_absent` is an autouse
fixture that points `STATIC_ROOT` at an empty tmp dir, because five tests went red
on a machine that had run `pnpm -r build`). **CI never exercises the assembled
route table.**

**Real Lemon Squeezy test-mode HTTP** — *only if you swap
`PAYMENT_PROVIDER=lemonsqueezy`* and enter real test-mode credentials in the
owner console. With the default `fake` you get a real HMAC round-trip through
`/fake-pay` and the real webhook route, which proves the settlement path but not
the provider's wire format. Note there are deliberately **no `LEMONSQUEEZY_*`
environment variables**: credentials are per tenant, typed into `סליקה
ותשלומים`, encrypted through the SecretBox, stored as ciphertext on
`tenant_gateway_credentials`. Setting them in the environment configures nothing.
Create the placeholder LS variant by hand in the LS dashboard; its price is never
used — every checkout overrides with `custom_price`.

**Real RLS under a real tenant — but only if you opt in.** ⚠ **Be honest about
this one.** `ensure_safe_database_role()` is a no-op when `app_env == "dev"`, and
the default dev URL connects as `postgres`. **Postgres RLS, even FORCEd, does not
apply to superusers — so the default local walkthrough does not exercise RLS at
all.** To make it real, mirror what `tests/conftest.py` does:

```bash
psql -d "$DB" -c "DO \$\$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'boutique_app') THEN
    CREATE ROLE boutique_app LOGIN PASSWORD 'local-only-pw';
  END IF;
END \$\$"
psql -d "$DB" -c "GRANT app_user TO boutique_app"
```

then point **only the app** at it (migrations and `app.cli provision` keep the
owner URL):

```dotenv
DATABASE_URL=postgresql+asyncpg://boutique_app:local-only-pw@localhost:5432/${DB}
```

(spell the database name out — `.env` is not shell, `$DB` does not interpolate
there; regenerate it with the §2.2 heredoc if you want it substituted.)

Provision a **second** tenant, sign into both consoles in two browser profiles,
and confirm neither sees the other's rows. Under this role the app's own
guarantees bind: `terms_versions` is INSERT+SELECT only, `platform_audit_log` is
INSERT-only, payment tables have no DELETE, and `alembic_version` is unreadable.
Under `postgres` every one of those is silently void.

---

## 6. Known not covered here

- **SMS never leaves the process.** `SMS_PROVIDER=fake` writes to an in-memory
  list and deliberately does **not** log the body (staging's log stream is widely
  readable and an INFO line carrying a live OTP would defeat `mask_otp_body`).
  Twilio is not exercised: it needs `TWILIO_ACCOUNT_SID`, `TWILIO_API_KEY_SID`,
  `TWILIO_API_KEY_SECRET` and `TWILIO_FROM_NUMBER` (the **E.164 number**, not the
  `PN…` resource SID) — all four, or the adapter reports `is_configured False`
  and every send 503s with a boot WARNING as the only symptom. Do not set them
  locally: real SMS costs real money to real handsets. Consequence: OTP delivery,
  message segmentation, the short `/b/{token}` SMS budget and Twilio error
  mapping are **untested by this runbook**.
- **S3 / media is optional and off.** With `MEDIA_BUCKET` unset the catalog is
  fully usable and only the upload endpoints answer `503 MEDIA_NOT_CONFIGURED`
  (`/health` reports `"media":"unconfigured"`). Presign, the POST-policy, the
  content-type sniff and the pending-media TTL are **not** exercised. ⚠ A stale
  `backend/.env` leaking `MEDIA_BUCKET` is a known cause of two false
  `test_config.py` failures locally — CI is green.
- **No real money ever moves.** `fake` records and never charges; `lemonsqueezy`
  hard-codes test mode and is a **boot failure** in production (it is
  merchant-of-record, and the deposit is legally the boutique's). Refunds,
  chargebacks, settlement timing and the real Israeli PSP are out of scope
  entirely — that decision is unmade.
- **Rate limits are not stress-tested.** Every budget is sized so it cannot fire
  on organic traffic, but a **scripted** walkthrough can trip one. Know the
  numbers before you file a 429: login 5/900 s; storefront reads 6000/60 s per
  tenant; OTP send 5/h per phone and 100/h per tenant; OTP verify 10/300 s per
  phone; booking create 10/h per phone and 300/h per tenant; booking lookup
  60/300 s per tenant; check-in create 200/h per tenant; position poll 30/60 s
  per ticket; position **misses** 120/60 s per tenant; queue board 600/60 s per
  tenant; atelier / gateway / terms creation 10/h per tenant each.
- **The dev-server layout is a different configuration** and is not covered:
  `make fe-dev` (storefront :5174) and `pnpm --filter manage dev`
  (:5173/manage/), each proxying to :8000 with `changeOrigin: false`. Vite's
  proxy middleware runs before the static and transform middlewares, which is why
  `apps/manage/vite.config.ts` spells out fifteen API segments instead of
  proxying a bare `/manage` prefix.
- **`TRUST_FORWARDED_FOR` stays false.** Per-IP login keying needs exactly one
  trusted proxy appending `X-Forwarded-For`; there is none locally, so per-IP
  keying is unexercised. The per-(tenant, email) key — the real brute-force
  control — is always on and *is* exercised by journey C step 1.
- **`/docs`, `/redoc`, `/openapi.json` are open in dev only** (`docs_url` is
  `None` whenever `app_env != "dev"`). Useful for reading the live route table
  while you QA; do not treat their presence here as production behaviour.
