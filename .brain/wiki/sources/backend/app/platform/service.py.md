---
tags: [backend, platform, provisioning, audit, python, tenancy, cli]
sources: [backend/app/platform/service.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/platform/service.py
blob: ddacf92e5ee0857041de558d2aa79b6e0a628d7b
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# backend/app/platform/service.py

**Role.** The audited operator command layer for the tenant lifecycle: provision a tenant with its first owner atomically, suspend one, reset an owner's password, list tenants, and run F16's one-shot manage-link backfill — every state change (and every provisioning *failure*) writing a `platform_audit_log` row.

**Module.** [[backend/app/platform/_index]] · **Layer.** platform

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `ProvisioningService` | class | Constructed from a session factory; builds its own repositories |
| `provision` | method | Validate slug → reject blank password → check slug free → one transaction creating `Tenant` + owner `StaffUser` + audit row |
| `suspend` | method | Flips `status` to `suspended`; the slug stops resolving immediately |
| `reset_owner_password` | method | Re-hashes the password for a matching `OWNER` row within the tenant's RLS context |
| `list_tenants` | method | Non-deleted tenants ordered by `created_at`, as `TenantSummary` |
| `backfill_booking_links` | method | Runs `ManageLinkBackfill` across all tenants, then audits the totals |
| `CommandResult` | frozen dataclass | `ok`, `message`, optional `tenant_id` — the CLI's exit-code source |
| `TenantSummary` | frozen dataclass | `slug`, `name`, `status`, `created_at` |
| `_fail_provision` | method | Writes a `tenant_provision_failed` audit row and returns `ok=False` |

## Behavior

The governing rule is stated in the class docstring and shapes every method: **business failures are returned, never raised.** Raising would abort the enclosing transaction and roll back the very audit row that reports the failure — the Feature 5 lesson. So `_fail_provision` opens its *own* short transaction, commits the failure audit, and hands back a `CommandResult`; a rejected slug, a blank password and a taken slug are all recorded, not silently dropped.

`provision` validates in a deliberate order: `is_valid_slug` (from [[backend/app/tenancy/slugs.py]], the same predicate the request path uses, so a slug the middleware would refuse can never be created), then a blank-password check — `echo -n | … provision` would otherwise mint a loginable owner whose password is a hashed empty string — then a `by_slug` pre-check. The real creation runs inside a single `tenant_session`, so tenant row, owner `StaffUser` and audit row commit together or not at all; the `tenant_id` is minted client-side first because the session context must be bound before the rows exist. `IntegrityError` is caught as a backstop rather than as the primary check: the `by_slug` lookup only sees *active* tenants, so a slug belonging to a suspended tenant passes the pre-check and is stopped by the partial unique index — the same catch also closes the concurrent-provision race.

`suspend` and `_fail_provision` and `backfill_booking_links` use a plain `session_factory()` transaction because they touch only platform-scoped tables. `reset_owner_password` uses `tenant_session` because `staff_users` is under FORCE RLS — without the bound context the `UPDATE` would match zero rows regardless of its predicate. Its `WHERE` still names `tenant_id`, `role == OWNER` and `deleted_at IS NULL` explicitly: redundant against RLS by design, defense in depth. `updated_at` is never assigned; a database trigger owns it. The `RETURNING StaffUser.id` is what distinguishes "no such owner" from a successful reset, and returning `owner_not_found` before the audit means a no-op leaves no misleading success row.

`backfill_booking_links` is F16's one-time deploy step. It lives on this audited layer rather than in a standalone script for two reasons: F25's platform console will reuse this layer as its service layer, and a one-shot operator action that touches every tenant's bookings should leave an audit row. It is safe to re-run because the backfill's feed is `manage_token_hash IS NULL`, which the first run fills.

## Depends On

- [[backend/app/tenancy/slugs.py]] — `is_valid_slug`
- [[backend/app/db/repositories/tenants.py]] — `by_slug`
- [[backend/app/db/repositories/staff_users.py]] — owner insert
- [[backend/app/platform/repository.py]] — the audit writer
- [[backend/app/db/tenant.py]] — `tenant_session` for the RLS-bound writes
- [[backend/app/auth/passwords.py]] — `hash_password`
- [[backend/app/booking/backfill.py]] — `ManageLinkBackfill`
- [[backend/app/models/tenant.py]] · [[backend/app/models/staff_user.py]] · [[backend/app/models/constants.py]]

## Depended On By

- [[backend/app/cli.py]] — the only production caller; `ProvisioningService` is imported lazily inside `main()`, and the CLI's own Protocol mirrors this class's signatures
- [[backend/tests/test_provisioning.py]]
- [[backend/tests/test_cli.py]] — imports `CommandResult` and `TenantSummary` to build a stub service

## Concepts

- [[Platform Audit Log]]
- [[Tenant Provisioning]]
- [[Row Level Security]]
- [[Tenant Context]]

## Tests

- [[backend/tests/test_provisioning.py]] — `test_provision_creates_a_loginable_owner`, `test_provision_rejects_reserved_and_invalid_slugs`, `test_provision_rejects_duplicate_slug`, `test_provision_rejects_blank_password`, `test_provision_after_suspend_hits_integrity_backstop`, `test_provision_rolls_back_the_tenant_on_partial_failure`, `test_suspend_flips_status_and_list_reflects_it`, `test_reset_password_changes_credentials`, `test_reset_password_rejects_blank_password`, `test_each_state_change_writes_platform_audit`, `test_app_user_cannot_read_platform_audit`
- [[backend/tests/test_cli.py]] — argument parsing and exit codes against a stub

## Notes

There is no HTTP surface for any of this — provisioning runs over SSH/CI as `python -m app.cli provision …`. `owner_email` is lowercased on both write and lookup; `display_name` is seeded to the email, so the owner's first job is renaming herself.
