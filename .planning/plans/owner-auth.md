# Plan: Owner Auth

**Branch**: `feature/owner-auth` (stacked on `feature/subdomain-routing`) · **Spec**: `../specs/owner-auth.md` · **Epic**: E1 Feature 5

AGENT_TEAMS off → sequential TDD. No Docker locally: pure-logic tests (passwords, rate limiter, 401/429 envelope with overridden deps) run local red→green; DB-marked tests (migration/RLS scan, login lifecycle, cross-tenant replay, audit) are CI-gated.

### Task 1 — Auth primitives (pure, local)
`app/auth/passwords.py` (argon2id hash/verify + constant-time dummy verify), `app/auth/rate_limit.py` (fixed-window, injectable clock, per (tenant,email)+IP), config additions (`login_max_attempts`, `login_window_seconds`, `session_ttl_seconds`, `secure_cookies` derived from app_env). Tests first: `tests/test_passwords.py`, `tests/test_rate_limit.py`.

### Task 2 — Data layer (migration + models + repos)
Migration `0003_auth`: staff_users, sessions, audit_log — each via `enable_tenant_rls`; partial unique index on (tenant_id, email); token_hash index; updated_at triggers. Models in `app/models/`; repos `app/db/repositories/{staff_users,sessions,audit_log}.py`. DB tests: `tests/test_auth_repositories.py` + rely on Feature 3's metadata-scan test to enforce RLS.

### Task 3 — Service + tenant session helper
Add `tenant_session()` (async_sessionmaker variant of `tenant_connection`) to `app/db/tenant.py`. `app/auth/service.py`: login/logout/current-staff, token mint+hash, audit writes — all tenant-scoped. Nested Input/Output where useful.

### Task 4 — Router + dependencies + wiring
`app/auth/router.py` (`/manage/auth` login/logout/me), `app/auth/dependencies.py` (`get_current_staff` → StaffContext), cookie set/clear helpers, exception handlers for generic 401/429 envelope; mount router in `create_app`. Unit tests with dependency overrides (`tests/test_auth_api.py`) + DB integration (`tests/test_auth_integration.py`: lifecycle, cross-tenant replay, expiry, 429, audit, cookie flags).

### Task 5 — Docs
README auth note, `.env.example` additions, epic status.

**Commits**: (1) primitives, (2) data layer, (3) service+helper, (4) router+api+integration tests, (5) docs. Review-round commits as needed. Dual reviewer agents (quality + adversarial security) → both ACCEPT.
