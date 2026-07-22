# Spec: Feature 6 — Tenant Provisioning CLI (Epic E1)

**Created**: 2026-07-21 · **Status**: approved-for-build (pipeline continuation) · **Epic**: E1 Feature 6 (last E1 feature) · **Effort**: S–M
**Depends on**: Features 3, 4, 5 — stacked on `feature/owner-auth`

## Problem

There is no way to onboard a boutique. A tenant + its first owner login must be created by a trusted operator (over SSH/CI), with every state change recorded in a durable audit trail. v1 has no self-serve signup and no web platform console (both E5) — an audited CLI is the whole provisioning surface.

## Goal

An operator runs `python -m app.cli provision --slug bella --name "Bella Bridal" --owner-email owner@bella.example` (password read from stdin, never a CLI arg) and gets an active tenant reachable at `bella.{base}` whose owner can immediately log in. `suspend`, `list`, and `reset-password` round out the lifecycle. Every state-changing invocation writes a **platform-level** audit row.

## Design

**Migration 0004** — `platform_audit_log` (append-only, **platform-scoped**):
- `id`, `operator TEXT`, `action TEXT`, `target_tenant_id UUID NULL`, `details JSONB DEFAULT '{}'`, `created_at TIMESTAMPTZ`.
- **Deliberately named `target_tenant_id`, NOT `tenant_id`** — a `tenant_id` column would trip Feature 3's `test_every_tenant_id_table_has_forced_rls` metadata scan (any `tenant_id`-bearing table must have FORCE RLS). This table is platform-wide operator history, so it must NOT be tenant-scoped. No RLS, no soft delete, no `updated_at` trigger (append-only). `GRANT`ed to `app_user`.

**`app/platform/`** module:
- `PlatformAuditLogRepository.record(...)`.
- `ProvisioningService(session_factory)` — methods return result dataclasses (never raise for business failures, so no write-then-raise rollback of failure audits — the Feature 5 lesson):
  - `provision(slug, name, owner_email, owner_password, operator)`: reuse `is_valid_slug` (Feature 4, rejects reserved+malformed) → pre-check `by_slug` → **atomic** create (client-generated tenant UUID → `tenant_session(id)` → insert `Tenant(id=…)` + owner `StaffUser` (argon2 via Feature 5 `hash_password`) + `platform_audit_log` in ONE transaction); `IntegrityError` on the partial unique slug index is the race-safe backstop → `slug_taken`. Failure paths write their own committed failure audit.
  - `suspend(slug, operator)`: flip `tenants.status` → suspended (platform table) + audit; already-suspended/unknown → result, not crash.
  - `list_tenants()`: all tenants (slug, name, status, created_at) ordered by created_at. Read-only, not audited.
  - `reset_owner_password(slug, owner_email, new_password, operator)`: update the owner's `password_hash` under tenant context + audit; unknown tenant/owner → failure result.
- `app/cli.py` — argparse (stdlib, no new dep) subcommands; password read from **stdin/getpass**, never an argv (process-list/shell-history leak). `--operator` defaults to `$USER`. Exit non-zero on failure; human-readable output.

## Out of scope

Web platform console + self-serve signup (E5) · multi-owner/roles (E6) · password reset for suspended tenants (v1 = active only) · un-suspend/restore (add when needed) · tenant hard-delete/offboarding + PII export (E10/PPL).

## Edge cases

1. Reserved slug (`admin`, `www`, …) or malformed → `provision` fails cleanly (failure audit written), non-zero exit.
2. Duplicate active slug → `slug_taken` (pre-check); duplicate under a concurrent/suspended row → `IntegrityError` backstop → `slug_taken`.
3. Password never appears in argv — supplied via stdin only.
4. Provisioning atomicity: tenant + owner + audit commit together, or none (transaction) — no orphan tenant without an owner.
5. `reset-password` / `suspend` on unknown slug → failure result, non-zero exit, no partial writes.
6. `platform_audit_log` must NOT be caught by the forced-RLS metadata scan (uses `target_tenant_id`).

## Testing

- Unit (local): `test_cli.py` — argparse dispatch maps subcommands/args to service calls with a fake service; password read from stdin; failure → non-zero exit. No DB.
- DB (CI): `test_provisioning.py` — provision creates a tenant whose owner then logs in via `AuthService` (end-to-end); reserved/invalid + duplicate slug rejected; suspend flips status; list returns provisioned tenants; reset-password makes the old password fail and the new one work; a `platform_audit_log` row per state change; RLS-real (runs as the non-owner `boutique_app` role).

## Dependencies

No new packages (argparse is stdlib). Reuses `is_valid_slug`, `hash_password`, `tenant_session`, `TenantsRepository`, `StaffUsersRepository`.
