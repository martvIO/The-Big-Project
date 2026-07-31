---
tags: [backend, platform, tenancy, operations, cli]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: active
---

# Tenant Provisioning

**What it is.** The operator-only lifecycle for a boutique: create the `tenants` row, its first
owner and the platform audit row — atomically — then suspend, list or reset an owner password.
There is **no self-service signup**; every tenant is created by hand over SSH/CI.

## The two halves

- [[backend/app/cli.py]] — an argparse front end run as `python -m app.cli provision --slug bella
  --name "Bella" --owner-email …`. Passwords come from `getpass`/stdin, **never argv**, which
  would leak into the process list and shell history. Operator-supplied text is stripped of control
  characters before printing, so a tab or an ANSI sequence cannot corrupt or spoof the terminal.
- [[backend/app/platform/service.py]] — `ProvisioningService`, which owns every state change and
  writes the [[Platform Audit Log]] row for it.

## Business failures are returned, never raised

`provision` answers with a frozen `CommandResult(ok=False, message=…)` for an invalid slug, an
empty password or a taken slug — and each of those goes through `_fail_provision`, which **writes
an audit row and returns**. Raising instead would roll the audit row back with the exception meant
to report it: the Feature 5 lesson, recorded in
[[.memory/patterns/commit-before-raise-in-tenant-session.md]] and restated in the class docstring.

## The atomic create needs a client-side UUID

```python
tenant_id = uuid4()
async with tenant_session(self._session_factory, tenant_id) as session:
    session.add(Tenant(id=tenant_id, slug=slug, name=name))
    ...staff.insert(...)  ...audit.record(...)
```

`tenants` has no `tenant_id` and no RLS; `staff_users` has forced RLS. To write both in one
transaction the tenant id must exist *before* the insert, so the session can be bound to it — see
[[.memory/patterns/atomic-parent-child-across-rls.md]]. Letting `uuid_generate_v4()` mint it would
mean two transactions and a window in which a tenant has no owner.

The pre-check `by_slug()` races, so `IntegrityError` from `idx_tenants_slug_unique` (a
[[Partial Unique Index]] on `WHERE deleted_at IS NULL`) is caught and mapped back to `slug_taken`.

## Slugs

A slug is the leftmost DNS label and therefore the tenant's identity — validated by `is_valid_slug`
in [[backend/app/tenancy/slugs.py]] against both a DNS-label regex and `RESERVED_SLUGS`. The same
module is used at request time by [[Tenant Resolution]], so reservation is enforced at creation and
at every request.

Suspension and soft-deletion both make a slug unresolvable —
[[backend/app/db/repositories/tenants.py#by_slug]] filters on active status, and the storefront
serves a 404.

## Also on this surface

`backfill_booking_links` — a one-time, re-runnable deploy step
([[backend/app/booking/backfill.py]]) that mints a manage token and schedules a reminder for every
already-confirmed future booking. It lives on the audited command layer rather than in a standalone
script so that an operator action touching every tenant's bookings leaves a trail; its feed is
`manage_token_hash IS NULL`, which the first run fills.

## Related

- [[Platform Audit Log]] · [[Tenant Resolution]] · [[Row Level Security]] · [[Least Privilege Database Role]]
- Tests: [[backend/tests/test_provisioning.py]] · [[backend/tests/test_cli.py]] · [[backend/tests/test_tenants_repository.py]]
