---
tags: [backend, db, security, tenancy, compliance]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: active
---

# Audit Trail

**What it is.** The `audit_log` table — one row per staff action inside a boutique, tenant-scoped
and under FORCE [[Row Level Security]] like every other tenant table. Not to be confused with
[[Platform Audit Log]], which is a different table with the opposite permission posture.

## Shape

Created in [[backend/migrations/versions/0003_auth.py]] with the standard columns plus `actor_id`,
`action TEXT`, `entity TEXT` and `details JSONB`. Model:
[[backend/app/models/audit_log.py]]. Writer: [[backend/app/db/repositories/audit_log.py]] —
`record()` plus `list_actions()`, and nothing else.

`app_user` holds full `SELECT, INSERT, UPDATE, DELETE` here. The boutique owns and can read her
own trail; that is the whole point of putting it under RLS rather than making it append-only.

## `action` is plain TEXT with no CHECK

Deliberately. The vocabulary lives in Python as `AuditAction` in
[[backend/app/models/constants.py]] — `login`, `login_failed`, `logout`, the seven `booking_*`
values added by the owner console and the five `staff_*` values added by staff management — and
each block's comment records that adding a value needs **no migration**.

Values are fine-grained on purpose: `staff_role_changed` and `staff_password_reset` stay separate
from `staff_updated` because "who was made an owner" and "whose password did someone else change"
are the two questions a security audit actually asks, and each stays one `WHERE action = …`
instead of a JSONB predicate.

## Writers

[[backend/app/auth/service.py]] (login / failed login / logout), [[backend/app/auth/staff.py]]
(every staff mutation, written under the staff [[Advisory Lock]] in the same transaction as the
change), and [[backend/app/booking/owner.py]] (every status transition, reschedule, phone
correction and link resend).

## The two traps

**Commit before you raise.** An audit row written and then followed by a `raise` inside the same
`tenant_session` is rolled back *with* the exception that was supposed to report it. This is the
Feature 5 lesson, and it is why [[backend/app/platform/service.py]] returns `CommandResult(ok=False)`
for business failures instead of raising. See
[[.memory/patterns/commit-before-raise-in-tenant-session.md]].

**`details` is a second copy of whatever you put in it.** `audit_log` is retained on the audit
clock, not the booking clock, so [[backend/app/booking/owner.py]] writes only
`old_phone_last4` / `new_phone_last4` plus the customer ids on a phone correction — never the full
number, never the name. The customer ids are what make the row answerable at all, since `set_phone`
overwrites in place and `customers` has no history table.

## Related

- [[Platform Audit Log]] · [[Row Level Security]] · [[Advisory Lock]] · [[Soft Delete]]
