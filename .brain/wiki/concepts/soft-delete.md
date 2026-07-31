---
tags: [backend, db, schema, postgres]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: active
---

# Soft Delete

**What it is.** Every table in this schema carries `deleted_at TIMESTAMPTZ` and nothing is ever
hard-deleted. `DELETE` is a `values(deleted_at=func.now())`; "restore" is
`values(deleted_at=None)`.

The column is declared once, in `StandardColumns` in [[backend/app/models/base.py]], and once more
as the `_STANDARD` SQL fragment repeated at the top of each migration from
[[backend/migrations/versions/0003_auth.py]] onward.

## Why it is load-bearing, not hygiene

Because every uniqueness rule in the schema is a [[Partial Unique Index]] predicated on
`deleted_at IS NULL`, soft-deleting a row *frees its name*. That is not a side effect — it is the
mechanism:

- a soft-deleted tenant's slug becomes reclaimable (`idx_tenants_slug_unique`);
- an archived dress's size labels stop colliding with a new dress's;
- a deactivated staff member's email can be reused by a new hire.

The booking indexes extend the same idea one step further with `AND status <> 'cancelled'`, so a
cancellation frees a seat structurally. See [[Partial Unique Index]].

## Reads must opt in, and the misses are indistinguishable

Every repository read filters `deleted_at.is_(None)`, so an unknown id, an archived row and
another tenant's row collapse into one indistinguishable miss —
[[backend/app/db/repositories/dresses.py#by_id]] says so explicitly, and
[[backend/app/auth/staff.py]]'s `StaffNotFoundError` states the same rule for staff.

Reaching an archived row requires a *separate, named* method:
`DressesRepository.by_id_any_state` exists solely for the detail and restore routes, and
`DressesRepository._scope` treats archived as an **exclusive** branch, never a combined view, so
each branch is served by exactly one partial index.

## Where it means "archived"

In the catalog, soft delete is the user-facing *archive* action — the manage UI calls it that
([[frontend/apps/manage/src/api.ts]] `archiveDress` / `restoreDress`), and `restore` in
[[backend/app/db/repositories/dresses.py]] is guarded on `deleted_at.is_not(None)` so restoring a
live dress is a no-op rather than a silent write.

## Gotchas

- **`terms_versions` and `platform_audit_log` can never be soft-deleted at all** — `app_user` holds
  no `UPDATE`/`DELETE` grant on either. [[backend/app/db/repositories/terms.py]] keeps the
  `deleted_at IS NULL` predicate anyway, purely for house-style uniformity, and says so.
- **Never assign `updated_at`.** It is maintained by the shared `update_updated_at()` trigger
  created in [[backend/migrations/versions/0002_tenants_app_role.py]]; assigning it in Python is
  called out as forbidden in [[backend/app/models/base.py]],
  [[backend/app/db/repositories/tenants.py]] and [[backend/app/platform/service.py]].
- Soft delete does **not** delete S3 objects. Deleting a `dress_media` row commits, then the object
  delete runs best-effort outside the transaction — see [[Media Upload Pipeline]].
- Adding a table means adding `deleted_at` *and* re-checking every unique index you write, or the
  archive action will start failing on a name the user thinks they released.

## Related

- [[Partial Unique Index]] · [[Repository Pattern]] · [[Database Migrations]] · [[Row Level Security]]
