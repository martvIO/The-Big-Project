# Plan: Tenant Core + RLS Isolation Harness

**Branch**: `feature/tenant-core-rls` (stacked on `feature/repo-scaffolds-and-ci`) · **Spec**: `../specs/tenant-core-rls.md` · **Epic**: E1

Local machine has no Docker ⇒ db-marked tests are authored test-first but turn green in CI (PR checks); unit tests + ruff + mypy verified locally. TDD order preserved: tests written before implementation.

### Task 1 — Config env guard (pure unit, local red→green)
`app_env` setting; non-dev + missing DATABASE_URL ⇒ startup failure. Tests: `tests/test_config.py`.

### Task 2 — Models + migration 0002
`app/models/base.py` (Base, StandardColumns mixin), `app/models/tenant.py`; migration `0002_tenants_app_role`: update_updated_at(), tenants + trigger + partial unique slug index, `app_user` NOLOGIN role + grants + default privileges.

### Task 3 — RLS helper + tenant context
`app/db/rls.py` (DDL emitter used by migrations and the probe-table test), `app/db/tenant.py` (parameterized transaction-local `set_config` helper taking `UUID`).

### Task 4 — Test-role fixtures + isolation suite (test-first)
conftest: `boutique_app` LOGIN role in `app_user`; app-role engine fixture. `tests/test_tenant_isolation.py` per spec must-have #8.

### Task 5 — TenantsRepository + tests
`app/db/repositories/tenants.py` + `tests/test_tenants_repository.py` (insert, by_slug active-only, suspend, soft-delete, slug reuse).

### Task 6 — Wire-up & docs
Epic status update; README note on the app role in tests; ship stacked PR, watch CI (db suite is the release gate for this feature).

**Commits**: (1) config guard, (2) models + migration + rls/tenant helpers, (3) fixtures + isolation suite + repository + tests, (4) docs/planning. Review round commits as needed.
