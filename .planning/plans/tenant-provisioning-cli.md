# Plan: Tenant Provisioning CLI

**Branch**: `feature/tenant-provisioning-cli` (stacked on `feature/owner-auth`) · **Spec**: `../specs/tenant-provisioning-cli.md` · **Epic**: E1 Feature 6

AGENT_TEAMS off → sequential TDD. No Docker locally: CLI arg-dispatch tests run local red→green; the provisioning service tests (multi-table atomic create, RLS-real) are CI-gated.

### Task 1 — Platform audit data layer
`migrations/versions/0004_platform_audit.py` (platform_audit_log, `target_tenant_id` NOT `tenant_id`, no RLS, GRANT app_user), `app/models/platform_audit_log.py` (lean append-only model, no StandardColumns), `PlatformAuditAction` enum in constants, `app/platform/repository.py` (record). No test-first here (schema) — covered by the service db tests.

### Task 2 — Provisioning service (db-tested)
`app/platform/service.py`: provision (atomic tenant+owner+audit via tenant_session with client-gen UUID; is_valid_slug reuse; by_slug pre-check + IntegrityError backstop), suspend, list_tenants, reset_owner_password — all returning result dataclasses, failure audits committed (no write-then-raise). `tests/test_provisioning.py` (db) written first conceptually, verified in CI.

### Task 3 — CLI (unit-tested)
`app/cli.py`: argparse subcommands (provision/suspend/list/reset-password), password from stdin/getpass, `--operator` default `$USER`, exit codes. `tests/test_cli.py` first (fake service, local red→green): arg mapping, stdin password, non-zero exit on failure.

### Task 4 — Docs
README provisioning section, epic status → building, `.env.example` unchanged (no new config).

**Commits**: (1) platform audit layer + provisioning service + service tests, (2) CLI + cli tests, (3) docs. Review-round commits as needed. Single mandatory reviewer (AGENT_TEAMS off) + a dedicated adversarial security reviewer (provisioning is privileged) → both ACCEPT.
