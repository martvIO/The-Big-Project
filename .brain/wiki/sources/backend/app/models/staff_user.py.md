---
tags: [backend, models, python, auth, staff, rbac, sqlalchemy]
sources: [backend/app/models/staff_user.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/models/staff_user.py
blob: f3af5acb3a001ff360245099d1fe52303e45e189
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/models/staff_user.py

**Role.** The boutique-side login identity — one row per staffer with an argon2 password hash, a display name and a role — and the table whose `role` column every `require_role` gate in the API reads.

**Module.** [[backend/app/models/_index]] · **Layer.** models

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `StaffUser` | class | ORM mapping for `staff_users`; `StandardColumns` + `Base` |
| `StaffUser.tenant_id` | col | `UUID NOT NULL` — the RLS discriminator |
| `StaffUser.email` | col | `TEXT NOT NULL`; unique per tenant via a *partial* index `(tenant_id, email) WHERE deleted_at IS NULL` |
| `StaffUser.password_hash` | col | `TEXT NOT NULL` — argon2 digest produced by [[backend/app/auth/passwords.py]], never a plaintext or reversible value |
| `StaffUser.display_name` | col | `TEXT NOT NULL` |
| `StaffUser.role` | col | `TEXT NOT NULL DEFAULT 'owner'`, default interpolated from `StaffRole.OWNER`; DB `CHECK` pins the set to `owner`/`shift_manager` |

## Behavior

Column declarations only — the invariants live in the DDL and in [[backend/app/db/repositories/staff_users.py]]. The email index is partial on `deleted_at IS NULL`, so deactivating a staffer frees their address for re-use within the same boutique rather than permanently reserving it; a plain unique constraint would have made "remove and re-add the same person" fail. `role` is plain `TEXT` in the model and `TEXT` with a `CHECK` in the database, added later by [[backend/migrations/versions/0011_staff_roles.py]] once a second role actually existed — `ADD CONSTRAINT` validates the pre-existing rows, all of which carry the `'owner'` default, so it cannot fail on live data.

The value in the `server_default` is an f-string over `StaffRole.OWNER`, which keeps the enum in [[backend/app/models/constants.py]] and the ORM default from drifting; the literal `'owner'` in the 0003 DDL and the literal set in the 0011 `CHECK` are separate copies that must be edited by hand. The table is under FORCE RLS by `tenant_id`, and the repository still writes an explicit `tenant_id` predicate on every statement as redundant defense-in-depth — that belt-and-braces matters most here because this is the row a login resolves to. Two reads on this table carry invariants that are not visible from the model: `count_live_owners` backs the "a boutique may never lose its last owner" rule, and `list_live` orders by `created_at ASC` so the founding owner stays first and the console's rows do not shuffle between page loads.

## Depends On

- [[backend/app/models/base.py]] — `Base`, `StandardColumns`
- [[backend/app/models/constants.py]] — `StaffRole`, interpolated into the `role` server default
- [[SQLAlchemy]] — declarative mapping

## Depended On By

- [[backend/app/db/repositories/staff_users.py]] — the only repository over this table
- [[backend/app/auth/service.py]] — login resolves an email to a `StaffUser` and verifies the hash
- [[backend/app/auth/staff.py]] — the staff-management service (create, update, role change, deactivate)
- [[backend/app/auth/staff_router.py]] — maps rows to the `StaffMember` response
- [[backend/app/platform/service.py]] — provisioning seeds the founding owner

## Concepts

- [[Row Level Security]]
- [[Tenant Isolation]]

## Tests

- [[backend/tests/test_staff_management_db.py]] — repository behavior against a migrated database
- [[backend/tests/test_staff_service.py]] — service-level rules including the last-owner invariant
- [[backend/tests/test_staff_role_gating.py]] and [[backend/tests/test_staff_role_gating_integration.py]] — what each role may call
- [[backend/tests/test_migrations.py]] — proves 0011's `CHECK` validates existing rows on a populated table
- [[backend/tests/test_auth_integration.py]], [[backend/tests/test_provisioning.py]], [[backend/tests/test_staff_api.py]]

## Notes

The role set is deliberately two values. `constants.py` records the reasoning: reception / seamstress / sales are not pre-added because a role with no consumer is speculative surface, and the DB `CHECK` would have to be widened anyway when one arrives.

Design context: [[.planning/specs/owner-auth.md]], [[.planning/specs/staff-management.md]], [[.planning/specs/staff-roles-gating.md]].
