# Plan: Staging Env + External Lead-Time Applications

**Spec**: `../specs/staging-and-external-apps.md` (rev 2) · **Epic**: E1 Feature 2

Infra feature — not TDD-shaped, and **not one long-lived branch**: Tasks 0–1 ship now as one small PR; each gated task ships as its own small PR the moment its account lands (avoids weeks of rebase churn while E2 lands on `main` in parallel).

### Task 0 — External tracker + user handoff (no blockers) — PR now
`.planning/external-applications.md` (four v1 items + deferred Meta/WhatsApp row, statuses, blocked-features). Hand the user the filing checklist: AWS account (+ il-central-1 opt-in), production domain (or stopgap staging domain), Grow/Meshulam merchant application, SMS sender-ID registration. Re-flag every future cycle until all approved.

### Task 1 — SMS provider comparison (no blockers) — same PR as Task 0
Research doc comparing Twilio vs Inforu vs 019 (₪/SMS at pilot volume, alphanumeric sender-ID registration process + lead time, delivery reports, API/webhook quality). Recommendation into the tracker; filing instructions to the user. Decision consumed by E3 #11.

### Task 2 — Deploy pipeline (needs Railway account) — own PR
Railway project: API service, worker service, Postgres 16 (private networking; public TCP proxy stays **disabled**).
1. First migration run + **role bootstrap** (one-time, owner URL, via `railway ssh`/one-off): `CREATE ROLE boutique_app LOGIN PASSWORD '<generated>'; GRANT app_user TO boutique_app;` — password only in Railway env.
2. Env for both services: `APP_ENV=staging`, `DATABASE_URL` (boutique_app, `postgresql+asyncpg://`), `MIGRATIONS_DATABASE_URL` (owner), `BASE_DOMAIN`, `TRUST_FORWARDED_FOR=true`. Names → `backend/.env.example`.
3. `deploy-staging` job in `ci.yml`: `needs: [backend, frontend]`, `on: push` to `main` only, own concurrency group `staging-deploy` with `cancel-in-progress: false`; release phase `DATABASE_URL=$MIGRATIONS_DATABASE_URL uv run alembic upgrade head`; then `railway up` with the project-scoped `RAILWAY_TOKEN`.
4. Smoke: `/health` 200; app fails to boot when `DATABASE_URL` is swapped to the owner URL (guard armed — needs F7's `verify_database_role` extension for the non-superuser-owner case).
5. CLI ops runbook: `railway ssh` → `python -m app.cli …`.

### Task 3 — Wildcard DNS + TLS (needs staging domain) — own PR (docs/config)
**Before purchase**: verify Railway wildcard-domain support; if falling back to Cloudflare, only a dedicated apex staging zone qualifies (one-level wildcard) and the Cloudflare→Railway host-routing path is verified end-to-end first. Then `*.<staging-domain>` CNAME, custom domain attach, cert issuance verified, `BASE_DOMAIN` set. Record the TLS decision (and its `TRUST_FORWARDED_FOR` implication — must be `false` under a two-proxy chain until XFF handling is adapted) in the tracker.

### Task 4 — S3 + production skeleton (needs AWS account) — own PR (docs/config)
il-central-1 opt-in; `boutique-staging-media` + `boutique-production-media` (block-public-access, versioning, CORS `AllowedOrigins: https://*.<staging-domain>` / `PUT,GET,HEAD` / small MaxAge); scoped IAM user; **keys → Railway env only** (no AWS keys in GH). Billing budget + alarm. Every console step → `docs/infra-runbook.md` (Terraform-ization is E4 #21).

### Task 5 — Staging verification (needs Tasks 2–3)
Provision two tenants via CLI on staging; verify TLS, routing, unknown-slug 404, suspension-next-request; guard checks (`current_user` = boutique_app; `platform_audit_log` SELECT denied; owner-URL boot refused); login rate-limit smoke. Tick E1 success criterion 1 with a dated note; epic table F2 → done.

**Review**: single mandatory reviewer + adversarial security pass per PR, focused on secrets handling, role separation (`MIGRATIONS_DATABASE_URL` vs `DATABASE_URL`), and the deploy-job trigger/permissions surface.
