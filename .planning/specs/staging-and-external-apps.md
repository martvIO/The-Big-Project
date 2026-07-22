# Spec: Feature 2 — Staging Env + External Lead-Time Applications (Epic E1)

**Created**: 2026-07-22 · **Status**: approved-for-build (pipeline continuation) · **Epic**: E1 Feature 2 (last open E1 feature) · **Effort**: S (build) + multi-week external lead times
**Depends on**: Feature 1 (CI) · **Blocks**: E1 success criterion 1 (staging DNS/TLS), E2 #8 (S3 bucket), E3 #11 (SMS), E4 #17–18 (Grow)

## Problem

E1 criteria 2–3 are green in CI, but criterion 1 — "a tenant provisioned via the CLI is reachable at its subdomain" — cannot be demonstrated: there is no deployed environment, no wildcard DNS/TLS, no S3, and none of the four external applications (AWS account, production domain, Grow merchant account, SMS sender-ID registration) have been filed. The applications have multi-week lead times and gate E3 (SMS) and E4 (payments); every week they slip, the pilot slips.

## Goal

Merges to `main` auto-deploy to a staging environment where `python -m app.cli provision` makes `{slug}.<staging-domain>` serve the app over TLS; a staging S3 media bucket exists for Feature 8 to consume; and all four external applications are filed and tracked in a standing tracker (`.planning/external-applications.md`) until approved.

## Design

Two workstreams: **(A) user-owned external applications** — started immediately, tracked and re-flagged every feature cycle until approved; **(B) infra build** — each task executes the moment its account/credential lands.

**A. External-applications tracker** — `.planning/external-applications.md`: the four items (AWS account + il-central-1 opt-in · production domain · Grow/Meshulam merchant account · SMS sender-ID/route registration incl. provider decision), each with status, owner, blocked-features list, and lead-time notes. This file is the single place the standing risk lives; every subsequent feature cycle re-checks it.

**B1. Staging platform = Railway** (architecture: "staging on Railway/similar"): API service (uvicorn), worker service (`app/worker.py`), managed Postgres 16. Deploy-on-merge via GitHub Actions (`railway` CLI + `RAILWAY_TOKEN` repo secret), release phase runs `alembic upgrade head`. **Two connection strings**: migrations run under the database-owner URL; the app runs as the non-owner `boutique_app` role (`DATABASE_URL`) so RLS is real on staging — `ensure_safe_database_role` must pass, fail-fast if misconfigured.

**B2. Wildcard DNS + TLS**: staging domain = subdomain of the production domain if it lands in time, else a dedicated staging domain the user purchases now (need not be `.co.il`). `*.<staging-domain>` CNAME → Railway; wildcard TLS via Railway custom domains. `extract_slug` base-domain config pointed at the staging domain.

**B3. S3 (AWS, il-central-1)**: staging media bucket (`boutique-staging-media`), block-public-access + versioning, CORS for presigned browser upload, IAM user scoped to the bucket, creds in Railway env only. Feature 2 provisions the bucket and records env-var names in `.env.example`; upload code arrives with Feature 8.

**B4. Production skeleton (il-central-1)**: opt-in region enabled, production media bucket (same conventions), IAM baseline, billing budget + alarm. Route 53 hosted zone when the production domain exists. No production compute. IaC stays a documented runbook for the pilot; Terraform formalization is E4 hardening scope.

**B5. SMS provider decision**: cost/capability comparison for Israeli SMS (Twilio vs local providers Inforu / 019 et al): price per SMS, alphanumeric sender-ID support + registration process, delivery reports, API quality. Output = decision section in the tracker + concrete filing instructions handed to the user.

**B6. Staging verification (closes E1 criterion 1)**: provision two tenants via the CLI on staging; verify TLS, subdomain routing, unknown-slug 404, and suspension-effective-next-request; tick the criterion in the E1 epic with a dated note.

## Out of scope

Production compute/deploy (E4 hardening) · Redis (E5) · CDN in front of S3 (when needed) · Terraform modules (E4) · per-tenant Grow credential storage (E4 #17) · any SMS-sending code (E3 #11) · self-serve anything (E5).

## Edge cases

1. `.co.il` registration can require Israeli-entity eligibility — user confirms registrar requirements early; a non-`.co.il` staging domain is fine for staging.
2. RLS on managed Postgres: isolation only holds if the app connects as non-owner `boutique_app`. Bootstrap creates the role via migrations (owner URL); the app URL must use `boutique_app` — `ensure_safe_database_role` guards against regression.
3. Wildcard custom domains on Railway: verify support on the current plan **before** buying the domain; fallback = front staging with Cloudflare (free wildcard TLS) pointing at Railway — decision recorded in the tracker.
4. il-central-1 is a newer opt-in region: confirm S3 availability/pricing there; if a needed service is missing, record the fallback-region decision in the tracker (data-residency is a preference lock, not yet a signed legal constraint).
5. Secrets hygiene: no cloud credentials in the repo, ever; Railway env + GH secrets only; `.env.example` documents names, not values.

## Testing

Infra feature — verification is the B6 staging smoke check (manual, recorded in the epic). CI is unchanged; any new settings entries are covered by the existing local `test_config.py` pattern (no Docker locally).

## Dependencies

User-provided: Railway account, AWS account, staging domain, and the four external applications. New secrets: `RAILWAY_TOKEN` (GitHub), AWS access keys (Railway env). No new Python deps (boto3 arrives with Feature 8).
