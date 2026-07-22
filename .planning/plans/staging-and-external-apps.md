# Plan: Staging Env + External Lead-Time Applications

**Branch**: `feature/staging-and-external-apps` off `main` · **Spec**: `../specs/staging-and-external-apps.md` · **Epic**: E1 Feature 2

Infra feature — not TDD-shaped. Code footprint is small (deploy workflow + config entries + docs); most tasks are gated on user-provided accounts and execute the moment each lands. Tasks 0–1 have **no blockers** and run immediately.

### Task 0 — External tracker + user handoff (no blockers)
Write `.planning/external-applications.md` (four items, statuses, blocked-features). Hand the user the filing checklist: AWS account (+ il-central-1 opt-in), production domain, Grow/Meshulam merchant application, SMS sender-ID registration. Re-flag in every future cycle until all approved.

### Task 1 — SMS provider comparison (no blockers)
Research doc comparing Twilio vs Inforu vs 019 (₪/SMS at pilot volume, alphanumeric sender-ID registration process + lead time, delivery reports, API/webhook quality). Recommendation into the tracker; filing instructions to the user. Decision consumed by E3 #11.

### Task 2 — Deploy pipeline (needs Railway account)
Railway project: API service, worker service, Postgres 16. GH Actions `deploy-staging` job on push to `main` (after CI passes): `railway up`, release command `alembic upgrade head` under the owner URL; app `DATABASE_URL` uses `boutique_app`. Smoke: `/health` 200 post-deploy. CLI ops documented via `railway run python -m app.cli …`.

### Task 3 — Wildcard DNS + TLS (needs staging domain)
Verify Railway wildcard-domain support first (fallback: Cloudflare front, record decision). `*.<staging-domain>` CNAME, custom domain attach, cert issuance verified. Point base-domain config at the staging domain.

### Task 4 — S3 + production skeleton (needs AWS account)
il-central-1 opt-in; `boutique-staging-media` + `boutique-production-media` buckets (block-public-access, versioning, CORS for presigned upload); scoped IAM user for staging; creds → Railway env; env-var names → `.env.example`. Billing budget + alarm. Runbook doc (`docs/infra-runbook.md`) capturing every console step for later Terraform-ization (E4).

### Task 5 — Staging verification (needs Tasks 2–3)
Provision two tenants via CLI on staging; verify TLS, routing, unknown-slug 404, suspension-next-request. Tick E1 success criterion 1 with a dated note; epic table F2 → done.

**Commits**: (1) tracker + SMS comparison docs, (2) deploy workflow + config, (3) runbook + `.env.example`. Review: single mandatory reviewer + adversarial security pass focused on secrets handling and the owner-vs-`boutique_app` connection-string separation.
