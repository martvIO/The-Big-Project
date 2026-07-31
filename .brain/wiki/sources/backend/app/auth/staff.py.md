---
tags: [backend, auth, python, staff, rbac, concurrency, advisory-lock, audit, security]
sources: [backend/app/auth/staff.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/auth/staff.py
blob: dd4eca19ff9bef0ef40fe8bc33bbdb3db68e1157
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/auth/staff.py

**Role.** Owner-only staff administration — list, create, update (name / role / password) and deactivate — holding two invariants that must survive **concurrency**: a staffer may not demote or deactivate herself, and a tenant may never be left with zero live owners. The second is why role-changing and deactivation take a per-tenant advisory lock before their first read.

**Module.** [[backend/app/auth/_index]] · **Layer.** auth

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `StaffService` | class | Built from an async session factory; owns three repositories |
| `list_staff` | async fn | Live rows for the tenant — no lock, no pagination |
| `create` | async fn | Lowercases the email, hashes outside the session, inserts, audits `STAFF_CREATED` |
| `update` | async fn | Name / role / password under the lock; one audit row per thing that actually changed |
| `deactivate` | async fn | Soft-delete under the lock, audits `STAFF_DEACTIVATED` |
| `DuplicateEmailError` | exception | 409 — raised by the pre-check *and* by the `IntegrityError` backstop |
| `LastOwnerRequiredError` | exception | 409 — this write would leave the tenant ownerless |
| `StaffSelfManageError` | exception | 409 — the actor targeted her own role, or her own account for deactivation |
| `StaffNotFoundError` | exception | Subclasses `DomainNotFoundError`, so it needs no handler of its own |
| `_STAFF_LOCK` | module const | `pg_advisory_xact_lock(hashtext('staff:' || :tenant_id))` |

## Behavior

**Why a lock and not an index.** A unique index expresses *at most one* of something; "at least one live owner" is the opposite shape and no index can state it. A single guarded `UPDATE … WHERE (SELECT count(*) … ) > 1` does not work either, and that is the trap the module docstring writes down: under READ COMMITTED — Postgres's default and this repo's — two concurrent statements each evaluate the subquery against a snapshot lacking the other's uncommitted write, both see 2, both pass, both commit, and the tenant ends with **zero** owners with no error raised anywhere. So `update` (when a role moves) and `deactivate` run one protocol inside a single `tenant_session`: take `_STAFF_LOCK` **before any read**, then read the target, then evaluate the guards, then write, then audit. A read taken outside the lock is a stale read and the guard would be checked against a count another transaction has already invalidated. `create` takes no lock, and that absence is a ruling: an insert can only *raise* the live-owner count, and a raise never invalidates a decision another transaction already made under the lock.

The lock key is **namespaced** (`'staff:' || tenant_id`) rather than the bare `hashtext(tenant_id)` used by the booking claim in [[backend/app/booking/service.py]] and [[backend/app/booking/owner.py]] — sharing it would serialize every staff edit against every public booking create for that tenant. The prefix is a SQL literal and the tenant id is bound, never interpolated.

**`update`'s branch structure.** The role guard fires on the role *moving* (`role is not None and role != target.role`), not on the field being present, because the console's inline edit form posts `display_name` and `role` together — the stricter reading would 409 an owner for renaming herself. `current_password` is demanded only on the **self** path: an owner resetting someone else's password does not know it, which is the field's whole point. If nothing actually changed, the method returns the target having written nothing and audited nothing; `password` is never compared to detect "same password", since that would be a gratuitous argon2 verify. Audit rows are emitted one per real change — `STAFF_UPDATED` with a from/to name, `STAFF_ROLE_CHANGED` with a from/to role, `STAFF_PASSWORD_RESET` with a `self` flag. No password material, plaintext or hashed, ever enters `details`; emails do, because `audit_log` is per-tenant under forced RLS and the email is the identity the row is about.

**The one place a session sweep is required.** Deactivation needs none — `resolve_session` re-reads `staff_users` on every request and `by_id` filters `deleted_at IS NULL`, so the target's live cookie 401s on her very next call (see [[backend/app/auth/service.py#resolve_session]]). A *password* change gets no such seam for free, so `update` calls `revoke_for_staff_user` in the same transaction under the same lock, excluding `acting_token_hash` so the owner is not signed out of the tab she just used. On the reset-someone-else path she holds none of the target's sessions, so the exclusion is a harmless no-op there.

**Two error paths worth knowing.** `create` lowercases the address before anything else, because `login` lowercases before its lookup and `by_email` matches exactly — a row written as `Dana@Bella.example` would be an account that can never sign in, a total silent failure. The duplicate check is a pre-check *plus* an `IntegrityError` catch wrapping the whole `async with` block (the constraint may surface at flush or at commit, and catching inside would try to raise from an already-aborted transaction); the pre-check races, and a 500 on a duplicate email is not an answer. Argon2 hashing is hoisted **outside** the session in both `create` and `update`, so a deliberately expensive computation does not hold a pooled connection; the `verify_password` on the self path cannot move, because it needs the row's own hash.

`StaffNotFoundError` covers unknown, soft-deleted and other-tenant ids as one indistinguishable miss — forced RLS plus the repository's redundant `tenant_id` predicate are what make the foreign case identical to the missing one.

## Depends On

- [[backend/app/auth/passwords.py]] — `hash_password`, `verify_password`
- [[backend/app/auth/service.py]] — `StaffContext` (the acting principal)
- [[backend/app/db/tenant.py]] — `tenant_session`
- [[backend/app/db/repositories/staff_users.py]] — `by_email`, `by_id`, `insert`, `update`, `soft_delete`, `count_live_owners`, `list_live`
- [[backend/app/db/repositories/sessions.py]] — `revoke_for_staff_user`
- [[backend/app/db/repositories/audit_log.py]] — `record`
- [[backend/app/errors.py]] — `DomainNotFoundError`, `DomainValidationError`
- [[backend/app/models/constants.py]] — `AuditAction`, `StaffRole`
- [[backend/app/models/staff_user.py]] — the returned row type
- [[SQLAlchemy]] — `text`, `IntegrityError`, async session (entity)

## Depended On By

- [[backend/app/auth/staff_router.py]] — the only caller
- [[backend/app/main.py]] — constructs it onto `app.state.staff_service` and registers the 409 handlers for `DuplicateEmailError`, `LastOwnerRequiredError` and `StaffSelfManageError`

## Concepts

- [[Role Based Access Control]]
- [[Advisory Locks]]
- [[Audit Log]]
- [[Row Level Security]]

## Tests

- [[backend/tests/test_staff_service.py]] — the branch matrix against fakes: self-guards, the no-op path, `current_password` rules, which audit rows each change writes
- [[backend/tests/test_staff_management_db.py]] — the real-database suite, including racing two demotions/deactivations directly at the last-owner invariant and asserting a password reset revokes the target's other sessions but not the acting one
- [[backend/tests/test_staff_api.py]] — the HTTP surface and error codes

## Notes

The last-owner guard inside `deactivate` is unreachable over HTTP as long as the router stays owner-only (the acting owner is herself live, so a second owner target implies a count of at least 2). It is kept because the invariant belongs to the service, not to the gate, and the database suite races it directly.

Deliberately **not** methods on `AuthService`: that class verifies credentials and issues sessions, and folding administration into it would drag the login path's fake into every CRUD test. Two files in an existing package, rather than a new `app/staff/` package for one router.

Design context: [[.planning/specs/staff-management.md]].
