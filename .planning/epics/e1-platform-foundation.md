# Epic: E1 — Platform Foundation

**Created**: 2026-07-21 (rev 2 — post verification pass)
**Status**: in progress — features 1, 3–6 shipped (PRs #1–#5 merged to main 2026-07-22); only #2 (staging + external applications) remains
**Owner**: team
**PRD**: §1 (multi-tenancy, wildcard routing), §2 (admin access)

---

## Why

Everything in this product sits on three guarantees: a request on `{slug}.ourbrand.co.il` is bound to exactly one tenant, no query can ever read another boutique's rows, and only authenticated staff reach management surfaces. This epic builds those guarantees plus the minimal operator tooling to provision tenants — no customer-facing UI yet, by design. Verification pass trimmed it to pilot-minimum: provisioning is an audited CLI (web console arrives with self-serve signup in E5), slug resolution is a direct DB lookup (no Redis yet), and accounts are owner-only (role column reserved for E6).

---

## Success Criteria

- [ ] A tenant provisioned via the CLI is reachable at its subdomain (staging wildcard DNS + TLS); unknown slugs 404; suspension takes effect on next request
- [x] CI cross-tenant isolation suite passes: every repository/endpoint probed as tenant A against tenant B's data returns nothing; unset tenant context returns zero rows (RLS forced, non-owner role)
- [x] Owner can log in at `{slug}…/manage`; sessions are subdomain-scoped and inert across boutiques; a locked-out owner is recoverable via the operator CLI password reset

---

## Features

| # | Feature | Status | Spec | Plan | Depends On |
|---|---------|--------|------|------|------------|
| 1 | Repo scaffolds & CI | done | [spec](../specs/repo-scaffolds-and-ci.md) | [plan](../plans/repo-scaffolds-and-ci.md) | — |
| 2 | Staging env + external lead-time applications | planned | [spec](../specs/staging-and-external-apps.md) | [plan](../plans/staging-and-external-apps.md) | #1 |
| 3 | Tenant core + RLS isolation harness | done | [spec](../specs/tenant-core-rls.md) | [plan](../plans/tenant-core-rls.md) | #1 |
| 4 | Subdomain routing & tenant resolution | done | [spec](../specs/subdomain-routing.md) | [plan](../plans/subdomain-routing.md) | #3 |
| 5 | Owner auth | done | [spec](../specs/owner-auth.md) | [plan](../plans/owner-auth.md) | #3, #4 |
| 6 | Tenant provisioning CLI | done | [spec](../specs/tenant-provisioning-cli.md) | [plan](../plans/tenant-provisioning-cli.md) | #5 |

---

## Feature Briefs

### Feature 1: Repo scaffolds & CI (M)
Replace the empty scaffolds with real projects: FastAPI app (SQLAlchemy 2 + Alembic, settings, router-per-domain layout, worker entrypoint) and pnpm monorepo (`apps/storefront`, `apps/manage`, `packages/ui`, `packages/api-client` — **no `apps/console` in v1**). CI runs lint, pytest (Testcontainers-Postgres), and frontend build on every PR.

### Feature 2: Staging env + external lead-time applications (S)
Staging environment (Postgres, S3 bucket, secrets), wildcard DNS + ACM/TLS for the staging domain, production skeleton in il-central-1. **Files both external applications that gate later features: the Grow merchant account AND Israeli SMS sender-ID/route registration** (provider chosen here by cost comparison: Twilio vs. Inforu/019). Both are tracked as standing risks until approved.

### Feature 3: Tenant core + RLS isolation harness (M)
`tenants` table (slug, status, settings JSONB), house DB conventions (UUID PKs, TEXT, TIMESTAMPTZ, soft delete, no FK constraints). Every request transaction runs `SET LOCAL app.tenant_id`; app connects as a non-owner role with `FORCE ROW LEVEL SECURITY` policies on all tenant tables; repository base injects the tenant filter. Delivers the **permanent CI cross-tenant isolation suite** — blocking from this feature onward.
**Security-review advisories from Feature 1 (must be honored here):** (a) migrations must create a non-superuser, non-owner `app` role and dev/tests must connect through it — superusers bypass RLS unconditionally, so isolation tests running as the Testcontainers superuser would be vacuous; (b) make `DATABASE_URL` required (no localhost default) outside a dev environment flag so misconfigured deployments fail fast instead of silently targeting localhost as superuser.

### Feature 4: Subdomain routing & tenant resolution (S)
Middleware extracts the leftmost host label → resolves `tenants.slug` via **direct indexed DB lookup** (Redis cache deferred to E5 #6 — premature at pilot traffic; middleware interface designed so the cache slots in later) → binds tenant to request context; tenant is never accepted from client input. Reserved-slug list (www, api, admin, app…). Unknown host → 404/marketing page. Local dev via `{slug}.localtest.me`.

### Feature 5: Owner auth (M)
**Owner-only accounts in v1** (role column defaults to `owner`; real role model lands with its first consumer in E6). Email+password login at `{slug}…/manage`, rate-limited, `HttpOnly/Secure/SameSite` cookies scoped to the exact subdomain (never the parent domain). Password reset in v1 is **operator-performed via the Feature 6 CLI** (no email infrastructure in v1). Audit log starts here (Data Security Regs requirement).

### Feature 6: Tenant provisioning CLI (S)
Audited management command (SSH/CI-run): provision tenant (creates slug + first owner login), suspend, list, reset owner password. Every invocation writes to the audit log. **Replaces the web platform console for v1** — the console + self-serve signup arrive in E5 #4; the "50+ tenants" goal doesn't need a web UI to onboard pilot-cohort boutiques.

---

## Risks

- RLS + connection pooling misuse (context bleeding between pooled connections) — mitigated by `SET LOCAL` inside the transaction and the isolation suite.
- Wildcard TLS/DNS and both external applications (Grow, SMS sender registration) are lead-time-bound — all filed in Feature 2, not when first needed.

## Notes

- No storefront pixels in this epic — the "flashy UI" starts at E2 Feature 9's design gate, after the foundation holds.
