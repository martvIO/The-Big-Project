# Infra Runbook — AWS + Railway Staging (Feature 2, Tasks 2 & 4)

Manual/CLI steps executed to unblock F10 (storefront browse, gated on the
media bucket per `.planning/external-applications.md`). Every command below
is reproducible from a clean account; Terraform-ization is explicitly E4 #21,
not this pass. Secrets are named here, never valued — real values live in
`Backend/.env` (local, gitignored) and Railway service variables only.

## AWS

**Account**: `849279003056` (root). Session is browser-based (`aws login`,
not IAM keys) — re-run that command yourself when it expires; it's a human
MFA step, not something to script.

### Region

`il-central-1` was already opt-in-enabled on this account — no action
needed. If starting from a fresh account: `aws account enable-region
--region-name il-central-1 --region us-east-1` (Account API is
global/us-east-1-only), then poll `aws account get-region-opt-status
--region-name il-central-1 --region us-east-1` until `ENABLED`.

### S3 buckets

`boutique-staging-media` and `boutique-production-media`, both in
`il-central-1`:

```bash
aws s3api create-bucket --bucket <name> --region il-central-1 \
  --create-bucket-configuration LocationConstraint=il-central-1
aws s3api put-public-access-block --bucket <name> \
  --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api put-bucket-versioning --bucket <name> --versioning-configuration Status=Enabled
aws s3api put-bucket-ownership-controls --bucket <name> \
  --ownership-controls Rules='[{ObjectOwnership=BucketOwnerEnforced}]'
aws s3api put-bucket-cors --bucket <name> --cors-configuration file://cors.json
```

CORS (`AllowedMethods: POST,GET,HEAD` — POST not PUT, since the app uses
presigned POST policies, not PUT):

```json
{
  "CORSRules": [{
    "AllowedMethods": ["POST", "GET", "HEAD"],
    "AllowedOrigins": ["https://*.staging.boutique-platform.invalid"],
    "AllowedHeaders": ["*"],
    "MaxAgeSeconds": 300
  }]
}
```

**`AllowedOrigins` is a placeholder** (`*.boutique-platform.invalid`, the
RFC 2606 reserved-invalid TLD) — Task 3 (wildcard DNS/TLS) hasn't happened
yet because no staging domain has been purchased
(`.planning/external-applications.md` item #2 is still `not-started`).
Update both buckets' CORS the moment that domain exists:
`aws s3api put-bucket-cors --bucket boutique-staging-media --cors-configuration file://cors.json`
with the real origin.

### IAM

Scoped user `boutique-media-staging`, policy `boutique-media-staging-access`
(`s3:PutObject`/`GetObject`/`DeleteObject` on both buckets' `/*` object ARNs
— see `arn:aws:iam::849279003056:policy/boutique-media-staging-access`).
Access key lives in `Backend/.env` locally and in the `api`/`worker` Railway
services — nowhere else. Rotate via `aws iam create-access-key` +
`aws iam delete-access-key` (old key) if it ever leaks.

> **OPEN REMEDIATION — staging credential reaches the production bucket.**
> Granting this policy `boutique-production-media/*` as well as the staging
> bucket breaks environment isolation: staging is the less-hardened,
> actively-deployed environment, so any compromise of the staging `api`/`worker`
> process gets `PutObject`/`DeleteObject` on real production tenant media —
> overwrite-defacement, or delete-markers causing an outage. Versioning makes
> the deletes recoverable; the overwrite path is not mitigated.
> **Fix**: narrow `boutique-media-staging-access` to the
> `boutique-staging-media/*` ARN only, and give production its own user and
> policy when it is provisioned. Raised by the F2 Task 2/4 security review.

### Billing

AWS Budgets (not the legacy CloudWatch billing-alarm checkbox — that needs a
console-only account preference toggle; Budgets doesn't). Budget
`boutique-platform-monthly`, $50/mo, alerts at 80% actual / 100% forecasted
to the account owner's email (SNS email subscription — one manual
confirmation click, already done).

```bash
aws budgets create-budget --account-id 849279003056 \
  --budget file://budget.json --notifications-with-subscribers file://budget-notifications.json
```

### Known bug found and fixed here

`Backend/app/storage/s3.py`'s `S3MediaStorage._s3()` built its boto3 client
with `region_name` but no `endpoint_url`. `generate_presigned_post()` builds
its form `url` from the client's endpoint, not its region — with no
explicit endpoint, botocore falls back to the legacy global
`bucket.s3.amazonaws.com` host. AWS opt-in regions (il-central-1 included)
reject that host outright (`IllegalLocationConstraintException`). MinIO
tests never caught this because `MEDIA_ENDPOINT_URL` is always explicit
there. **Fix**: default `endpoint_url` to
`https://s3.{region}.amazonaws.com` when `MEDIA_ENDPOINT_URL` is unset.
Verified against real S3: full presign → upload → confirm → signed-GET
round trip, byte-identical.

## Railway

Project `boutique-platform` (`2752f987-2a07-4670-8c9d-697f6f409621`), linked
from `Backend/` (that's the deploy source root for both app services).

### Services

| Service | ID | Role |
|---|---|---|
| `api` | `6e91d557-4d19-423e-a238-775d934e7442` | uvicorn, public domain, `/health` healthcheck |
| `worker` | `d097e21d-74cb-4f3d-a3f1-e6c604ad2239` | `app/worker.py`, no public domain |
| `Postgres` | `79c0feaf-c60c-42cf-8348-9f0687f3379e` | managed Postgres **18** (Railway's current default template — spec said 16; nothing in the migrations is version-specific, no action taken) |

Environment: `fd2c55b0-e098-4fd2-b9da-10efc802c154` (Railway's default
environment, named `production` by Railway itself — unrelated to our app's
`APP_ENV`, which is set to `staging` on both services).

Created via:

```bash
cd Backend
railway init --name boutique-platform
railway add --database postgres
railway add --service api
railway add --service worker
```

**Public TCP proxy on Postgres was auto-created by the template — deleted
it** (spec requires private networking only):
`railway tcp-proxy delete <id> --service Postgres --yes`.

### Per-service build/deploy config

Set via the GraphQL API (`railway api`) — no CLI flag exposes these
directly, and per-service `railway.toml` can't vary the start command
across two services sharing one root directory:

```graphql
mutation($serviceId: String!, $environmentId: String, $input: ServiceInstanceUpdateInput!) {
  serviceInstanceUpdate(serviceId: $serviceId, environmentId: $environmentId, input: $input)
}
```

- `api`: `startCommand: "uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT"`,
  `healthcheckPath: "/health"`, `healthcheckTimeout: 60`, `restartPolicyType: ON_FAILURE`,
  `preDeployCommand: ["DATABASE_URL=$MIGRATIONS_DATABASE_URL uv run alembic upgrade head"]`
- `worker`: `startCommand: "uv run python -m app.worker"`, `restartPolicyType: ON_FAILURE`

**`preDeployCommand` is the mechanism, not a separate CI release step.** The
spec's phrasing ("release phase `DATABASE_URL=$MIGRATIONS_DATABASE_URL uv
run alembic upgrade head`") reads like a Heroku-style external release
phase, but Postgres is private-network-only — a GitHub Actions runner can't
reach it directly. Railway's `preDeployCommand` runs inside the container's
network before the main `startCommand`, which is where this has to live.
Verified: redeploying `api` shows the Alembic log lines before the
`Starting Container` → `Uvicorn running` transition.

**`railway redeploy` reuses the previous build manifest — it will NOT pick
up a service-instance config change.** Use `railway up` for that (confirmed
by trial: a `redeploy` after setting `preDeployCommand` showed `None` in the
deployment's manifest snapshot; a fresh `railway up` picked it up).

### Database role bootstrap

Migrations (already run, see below) create only the NOLOGIN group role
`app_user`. The LOGIN role is a deploy-time bootstrap, not a migration
(mirrors `Backend/tests/conftest.py` and
`Backend/migrations/versions/0002_tenants_app_role.py`):

```sql
CREATE ROLE boutique_app LOGIN PASSWORD '<generated, Railway env only>';
GRANT app_user TO boutique_app;
```

Run once against the owner URL. Since the public TCP proxy is off, connect
via `railway connect postgres --tunnel-only --port <port>` (SSH tunnel —
needs an SSH key registered first: `railway ssh keys add`) and point local
`psql`/`alembic` at `127.0.0.1:<port>`.

Migrations were run the same way, once, against the owner URL:
`DATABASE_URL=postgresql+asyncpg://postgres:<owner-pw>@127.0.0.1:<port>/railway uv run alembic upgrade head`.
Going forward, `preDeployCommand` handles this on every deploy.

### Env vars (both `api` and `worker`)

> **OPEN REMEDIATION — the owner-role URL is provisioned on `worker`, which
> never uses it.** Only `api` has a `preDeployCommand`, so `worker` holds a
> standing owner-role Postgres credential with no consumer. Table ownership
> carries implicit privileges that no `REVOKE` binds — an owner connection can
> `ALTER TABLE … NO FORCE ROW LEVEL SECURITY` and defeat tenant isolation
> outright, and `verify_database_role()` only guards the app's own SQLAlchemy
> engine, not a raw connection opened against a variable sitting in the
> environment. The realistic trigger is mundane: a future worker feature
> copy-pasting the wrong variable name when both are present.
> **Fix**: delete `MIGRATIONS_DATABASE_URL` from the `worker` service; keep it
> on `api` only. Raised by the F2 Task 2/4 security review.

`APP_ENV=staging`, `DATABASE_URL` (boutique_app role, `postgresql+asyncpg://`),
`MIGRATIONS_DATABASE_URL` (owner role, consumed only by `preDeployCommand` on
`api` — see the remediation note above; it should not be set on `worker`),
`BASE_DOMAIN=staging.boutique-platform.invalid` (placeholder — swap for the
real staging domain once Task 3 lands; nothing routes through it yet since
no wildcard DNS exists), `TRUST_FORWARDED_FOR=true`,
`MEDIA_BUCKET=boutique-staging-media`, `MEDIA_REGION=il-central-1`,
`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` (the scoped IAM user from
above). Names recorded in `Backend/.env.example` (values never committed).

**Gotcha hit while setting these**: a naive `grep AWS_ACCESS_KEY_ID .env`
also matched the explanatory comment line above it (which names the var in
prose) and concatenated both into one corrupted multi-line value pushed to
Railway. Fixed by anchoring the grep to line start (`^AWS_ACCESS_KEY_ID=`)
and re-setting both services. Verified after the fix: both keys are
single-line, correct length (20 / 40 chars).

### Public domain

`api` has a Railway-generated domain (`railway domain --service api`) for
`/health` checks and CI smoke-testing. `worker` has none (not HTTP-facing).
This is **not** the wildcard staging domain from Task 3 — it's a
`*.up.railway.app` domain, useful only for `/health`, not for per-tenant
subdomain routing (that needs the real domain + wildcard TLS).

### CI

`.github/workflows/ci.yml` → `deploy-staging` job: `needs: [backend,
frontend]`, only on `push` to `main` (never `pull_request`), own
non-cancelling concurrency group `staging-deploy`. Installs the Railway CLI at
a pinned version (bump by hand — Dependabot does not watch `npm install -g` in
a run step), runs `railway up --service api --ci` then `--service worker --ci` using the
`RAILWAY_TOKEN` secret (project-scoped — created in the Railway dashboard
under Settings → Tokens, since `projectTokenCreate` over the GraphQL API
returned "Not Authorized" for a personal login session; dashboard creation
was the only path that worked), then curls the api service's `/health` and
asserts on the body, not just the status — an app that booted with
`MEDIA_BUCKET` unset still answers 200, just with `"media":"unconfigured"`.
The health URL comes from the `STAGING_HEALTH_URL` repo variable when set,
falling back to the generated Railway domain; point the variable at the real
staging domain once Task 3 lands rather than editing the workflow.

### Operator CLI against staging (plan Task 2 step 5)

The operator CLI is `Backend/app/cli.py`, and it must run inside a service
container — it needs `DATABASE_URL` and the Postgres private network, neither
of which exists on a laptop. Shell into the `api` service and invoke it as a
module:

⚠ **The four tenant-lifecycle subcommands no longer exist.** F25 moved
`provision` / `suspend` / `list` / `reset-password` to the platform console at
`https://admin.<BASE_DOMAIN>/platform`, and deleted them here rather than leaving
a second door. They now answer `invalid choice` if a stale runbook still calls
them. Sign in there with an operator account, which is seeded from this shell:

```
railway ssh --service api
python -m app.cli create-operator --email <you>@<domain> --display-name "<Name>" --operator <you>
# password read from stdin/getpass — never argv
python -m app.cli deactivate-operator --email <them>@<domain> --operator <you>
```

The maintenance commands that stay here:

```
python -m app.cli backfill-booking-links --operator <name>
python -m app.cli retention --operator <name>            # rehearsal, counts only
python -m app.cli retention --operator <name> --armed    # actually deletes
```

`--operator` is REQUIRED on `retention` and on both operator commands, and it
must be a real person: inside a container `$USER` is whatever the image runs as,
and `platform_audit_log` is where this ends up. `create-operator` prompts for the
password on stdin rather than taking it as an argument, so it stays out of shell
history.

This is the path Task 5's two-tenant staging verification will use.

### If the worker deploy fails after api succeeded

The two `railway up` steps are sequential and not atomic — Railway has no
multi-service transaction. If `api` deploys and `worker` fails, the job stops
before the smoke check and the services sit on different commits. Recovery is
manual and safe to repeat: check what each service is actually running with
`railway status`, then re-run `railway up --service worker` from `Backend/`.
No rollback of `api` is needed — the two services share a database but not a
release, and `worker` currently registers no jobs.

## Verified end-to-end

- `aws sts get-caller-identity`, bucket CORS/versioning/public-access-block
  on both buckets, `aws budgets describe-budget` — all green.
- Local backend against real AWS: presign → upload (204) → confirm →
  signed-GET, byte-identical round trip. Test object deleted afterward.
- Railway `api` service: fresh `railway up` → build → `preDeployCommand`
  (Alembic, no-op since already at head) → healthcheck → `/health` returns
  `{"status":"ok","media":"configured"}` on the live public domain.
- DB role guard: `boutique_app` boots fine (non-superuser, non-owner,
  `platform_audit_log` SELECT denied); pointing the same guard check at the
  owner URL correctly raises `RuntimeError` — tested locally over the same
  SSH tunnel, without touching the live service.
- `worker` service: deployed, running, logs show a clean start
  (`worker started — no jobs registered yet`), not crash-looping.

## Hardening backlog (raised by the F2 Task 2/4 security review)

Two HIGH items are recorded inline above where the config they describe lives:
narrowing the staging IAM policy off the production bucket (§IAM), and dropping
`MIGRATIONS_DATABASE_URL` from `worker` (§Env vars). Both need console/CLI
access and are the operator's to apply. The rest:

- **Actions are tag-pinned, not SHA-pinned.** `deploy-staging` reuses
  `actions/checkout@v4` in the same job that later exposes `RAILWAY_TOKEN`, so
  a tag re-point executes with the token in scope for subsequent steps.
  Deferred deliberately: four Dependabot PRs (#6–#9) are open against exactly
  these actions, and SHA-pinning now would conflict with all of them. Do it in
  one pass after they land.
- **A failed deploy does not block the next one.** GitHub releases a
  concurrency group on job completion regardless of outcome, so if `api`
  succeeds and `worker` fails — or Alembic fails mid-`preDeployCommand` — the
  next merge deploys straight on top of the partial state, with no alert.
  Acceptable at staging volume; must be closed before this becomes the
  production pattern under E4 #21.
- **`RAILWAY_TOKEN` blast radius.** Project-scoped rather than account-scoped,
  so damage is bounded to `boutique-platform` — but that project holds the
  owner DB URL and the AWS media keys and accepts arbitrary code pushes to
  `api`/`worker`. Treat a leak as a full staging compromise: rotate the token,
  the `boutique_app` password, and the IAM key together.
- **Topology disclosure.** The AWS account ID, Railway resource UUIDs, and the
  generated `*.up.railway.app` hostname are committed in plaintext here and in
  `.planning/external-applications.md`. None grants access on its own, but all
  of it is reconnaissance material — redact before any decision to make this
  repo public.

## Explicitly not done here

- **Task 3 (wildcard DNS/TLS)** — blocked on a staging-domain purchase
  decision (`.planning/external-applications.md` item #2, still
  `not-started`). Nothing here depends on it having landed; several values
  above (`BASE_DOMAIN`, bucket CORS `AllowedOrigins`) are placeholders that
  need updating once it does.
- **Full B6 staging verification** (tenant reachable at
  `{slug}.<staging-domain>` over TLS, per-tenant subdomain routing,
  suspension-takes-effect-next-request) — depends on Task 3.
- **Production compute** — explicitly owned by E4 #21, not this feature.
- Terraform-izing any of the above — also E4 #21.
