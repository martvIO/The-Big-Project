# Plan: Subdomain Routing & Tenant Resolution

**Branch**: `feature/subdomain-routing` (stacked on `feature/tenant-core-rls`) · **Spec**: `../specs/subdomain-routing.md` (full design + security notes live there) · **Epic**: E1 Feature 4

Tasks as executed (TDD; unit red→green local, db-marked tests CI-gated):

1. Slug/host parsing — `app/tenancy/slugs.py` (RESERVED_SLUGS shared with Feature 6, DNS-label validation, fail-closed `extract_slug` incl. ASCII-only guard) + `tests/test_slugs.py` host matrix.
2. Config — `base_domain` setting + non-dev boot guard (mirrors the DATABASE_URL guard).
3. Middleware — `app/tenancy/middleware.py` (TenantContext, TenantResolver protocol, exempt paths incl. `/docs/oauth2-redirect`, byte-identical generic 404 for every failure incl. the `TenantNotResolvedError` backstop) + `resolver.py` + `create_app(resolver=...)` wiring + fake-resolver unit tests + import-safety regression test.
4. DB integration tests — real resolver on Testcontainers Postgres: end-to-end resolve, suspended/deleted/never indistinguishable, reserved-with-row 404.
5. Docs — README dev-domain note, `.env.example`, epic status.

**Commits**: feature commit + review-round fix commit(s). Review: dual agents (quality + adversarial security), both ACCEPT required.
