# Spec: Feature 2 — Staging Env + External Lead-Time Applications (Epic E1)

**Created**: 2026-07-22 · **Revised**: 2026-07-22 (rev 2 — post six-critic verification pass) · **Status**: approved-for-build (pipeline continuation) · **Epic**: E1 Feature 2 (last open E1 feature) · **Effort**: S (build) + multi-week external lead times
**Depends on**: Feature 1 (CI) · **Blocks**: E1 success criterion 1 (staging DNS/TLS), E2 #8 (S3 bucket), E3 #11 (SMS), E4 #17–18 (Grow)

## Problem

E1 criteria 2–3 are green in CI, but criterion 1 — "a tenant provisioned via the CLI is reachable at its subdomain" — cannot be demonstrated: there is no deployed environment, no wildcard DNS/TLS, no S3, and none of the four external applications (AWS account, production domain, Grow merchant account, SMS sender-ID registration) have been filed. The applications have multi-week lead times and gate E3 (SMS) and E4 (payments); every week they slip, the pilot slips.

## Goal

Merges to `main` auto-deploy to a staging environment where `python -m app.cli provision` makes `{slug}.<staging-domain>` serve the app over TLS; a staging S3 media bucket exists for Feature 8 to consume; and all external applications are filed and tracked in a standing tracker (`.planning/external-applications.md`) until approved.

## Design

Two workstreams: **(A) user-owned external applications** — started immediately, tracked and re-flagged every feature cycle until approved; **(B) infra build** — Tasks 0–1 are unblocked now; each remaining task executes the moment its account/credential lands, delivered as separate small PRs (no long-lived branch waiting on lead times).

**A. External-applications tracker** — `.planning/external-applications.md`: the four v1 items (AWS account + il-central-1 opt-in · production domain · Grow/Meshulam merchant account · SMS sender-ID/route registration incl. provider decision) plus a deferred-applications section (Meta Business/WhatsApp verification — ROADMAP E10 #2 requires it started during v1). Each row: status, owner, blocked features, lead-time notes. This file is the single place the standing risk lives.

**B1. Staging platform = Railway** (architecture: "staging on Railway/similar"): API service (uvicorn), worker service (`app/worker.py`), managed Postgres 16. Deploy-on-merge via GitHub Actions with a **project/environment-scoped** `RAILWAY_TOKEN` (never an account token), triggered only on `push` to `main` (never `pull_request`), as a job in `ci.yml` gated by `needs: [backend, frontend]` with its **own concurrency group** (`staging-deploy`, `cancel-in-progress: false`) so a second merge cannot cancel a mid-flight deploy/migration.

**Database roles — the part that is easy to get wrong** (verified against `0002_tenants_app_role.py` + `tests/conftest.py`):
- Migrations create only the **NOLOGIN group role `app_user`**. The LOGIN role is a **deployment bootstrap step, not a migration** (its password is a secret): once, under the owner URL, run `CREATE ROLE boutique_app LOGIN PASSWORD '<generated>'; GRANT app_user TO boutique_app;` (mirrors `conftest.py`). The password exists only inside Railway env, never in the repo.
- **Two env vars, both recorded in `.env.example`**: `MIGRATIONS_DATABASE_URL` (owner role — used ONLY by the release phase: `DATABASE_URL=$MIGRATIONS_DATABASE_URL uv run alembic upgrade head`, since `migrations/env.py` reads the same settings the app does) and `DATABASE_URL` (`boutique_app`) for the runtime services. The runtime env must never carry the owner URL under `DATABASE_URL`. Railway hands out `postgresql://` URLs — rewrite to `postgresql+asyncpg://`.
- **Required Railway env for BOTH services**: `APP_ENV=staging`, `DATABASE_URL` (boutique_app), `BASE_DOMAIN=<staging-domain>`, `TRUST_FORWARDED_FOR=true` (plain Railway = exactly one proxy). The dev default silently disables `verify_database_role`, Secure cookies, and the fail-fast config validators — forgetting `APP_ENV` recreates the exact silent misconfiguration this feature exists to prevent.
- The startup guard currently rejects only superuser/BYPASSRLS roles; the **owner-URL-as-app-URL hole is closed by F7's guard extension** (fail when `current_user` owns public tables). B6 verifies the guard is armed either way.
- Operator CLI on staging: **`railway ssh` into the API service** → `python -m app.cli …` inside the private network. The Postgres public TCP proxy **stays disabled** (`railway run` executes locally and would require exposing the DB).

**B2. Wildcard DNS + TLS**: staging domain = subdomain of the production domain if it lands in time, else a dedicated staging domain the user purchases now (need not be `.co.il`). `*.<staging-domain>` CNAME → Railway; wildcard TLS via Railway custom domains — **verify wildcard support on the current plan BEFORE purchasing the domain**. Fallback: Cloudflare in front — but free Universal SSL covers only a first-level wildcard, so the fallback is valid **only for a dedicated apex staging zone** (`*.staging.<prod-domain>` needs paid ACM); and Cloudflare→Railway host-routing must be verified end-to-end first. Any header-forwarding scheme (`X-Forwarded-Host`) is out of scope unless separately spec'd with its own spoofing analysis. `BASE_DOMAIN` points at the staging domain.

**B3. S3 (AWS, il-central-1)**: staging media bucket (`boutique-staging-media`), block-public-access + versioning, CORS pinned — `AllowedOrigins: https://*.<staging-domain>`, methods `PUT/GET/HEAD`, small `MaxAge` (same convention for production). IAM user scoped to the bucket; **AWS keys live in Railway env only — the only GitHub secret in this feature is `RAILWAY_TOKEN`**. Feature 2 provisions the bucket and records env-var names in `.env.example`; upload code arrives with Feature 8 (E2 epic updated: F8 consumes the F2-provisioned bucket and depends on F2 + AWS approval).

**B4. Production skeleton (il-central-1)**: opt-in region enabled, production media bucket (same conventions), IAM baseline, billing budget + alarm. Route 53 hosted zone when the production domain exists. No production compute here — **production stand-up (compute, DNS/TLS, prod Postgres, Secrets Manager) and Terraform-izing the runbook are explicitly owned by E4 #21** (E4 epic updated accordingly; previously unowned). Every console step lands in `docs/infra-runbook.md`.

**B5. SMS provider decision**: cost/capability comparison for Israeli SMS (Twilio vs local providers Inforu / 019 et al): price per SMS at pilot volume, alphanumeric sender-ID support + registration process and lead time, delivery reports, API/webhook quality. Output = decision section in the tracker + concrete filing instructions handed to the user. Consumed by E3 #11.

**B6. Staging verification (closes E1 criterion 1)**: provision two tenants via the CLI on staging; verify TLS, subdomain routing, unknown-slug 404, suspension-effective-next-request; **plus guard checks**: app refuses to boot when pointed at the owner/superuser URL, `SELECT current_user` = `boutique_app`, `SELECT * FROM platform_audit_log` under the app URL is denied, and a login rate-limit smoke check (per-IP limiting depends on `TRUST_FORWARDED_FOR` being correct for the proxy chain). Tick the criterion in the E1 epic with a dated note.

## Out of scope

Production compute/deploy + Terraform (E4 #21 — now explicitly) · Redis (E5) · CDN in front of S3 (when needed) · per-tenant Grow credential storage (E4 #17) · any SMS-sending code (E3 #11) · `X-Forwarded-Host` trust schemes · self-serve anything (E5).

## Edge cases

1. `.co.il` registration can require Israeli-entity eligibility — user confirms registrar requirements early; a non-`.co.il` staging domain is fine for staging.
2. RLS on managed Postgres: isolation and the REVOKE-based guarantees (append-only audit/terms tables) only hold if the app connects as non-owner `boutique_app`. The bootstrap is a documented deploy step (see B1); `verify_database_role` rejects superuser/BYPASSRLS today and table-owner connections once F7's extension lands; B6 proves the guard is armed on staging.
3. Wildcard TLS: Railway support verified before domain purchase; Cloudflare fallback only for a dedicated apex staging zone (one-level wildcard); host-routing verified before relying on it.
4. il-central-1 is a newer opt-in region: confirm S3 availability/pricing; if a needed service is missing, record the fallback-region decision in the tracker (data-residency is a preference lock, not yet a signed legal constraint).
5. Secrets hygiene: no cloud credentials in the repo, ever; Railway env + the single scoped `RAILWAY_TOKEN` GH secret; `.env.example` documents names, not values.
6. Concurrent merges to `main`: the deploy job's own non-cancelling concurrency group serializes deploys; CI proper keeps its existing cancel-in-progress behavior.

## Testing

Infra feature — verification is the B6 staging smoke + guard check list (manual, recorded in the epic). New settings entries covered by the existing local `test_config.py` pattern (no Docker locally). The deploy job addition is a CI change and is exercised by the first merge after Task 2.

## Dependencies

User-provided: Railway account, AWS account, staging domain, and the external applications. New secrets: `RAILWAY_TOKEN` (GitHub, project-scoped), AWS access keys + `MIGRATIONS_DATABASE_URL` + `boutique_app` password (Railway env only). No new Python deps (boto3 arrives with Feature 8). F7 delivers the `verify_database_role` table-ownership extension consumed by B6.
