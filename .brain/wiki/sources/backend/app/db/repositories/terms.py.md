---
tags: [backend, db, repository, terms, boutique, booking, append-only, python, sqlalchemy]
sources: [backend/app/db/repositories/terms.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/db/repositories/terms.py
blob: 64c9ab6581f5ef55430ba9feb3b1e0c3a1e450d5
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/db/repositories/terms.py

**Role.** The append-only `terms_versions` table: read the highest version number, append the next one, read the current version for display, read **one exact past version** for a booking that pinned it, and page the history.

**Module.** [[backend/app/db/repositories/_index]] · **Layer.** db

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `TermsVersionsRepository` | class | The repository; explicit `AsyncSession` + `tenant_id` on every method |
| `max_version` | method | `COALESCE(MAX(version), 0)` — the number the next version is computed from |
| `insert` | method | Appends a version with its cancellation policy and `created_by` |
| `current` | method | The newest version, or `None` when the boutique has published none |
| `by_version` | method | One exact version — the read a booking's pinned `terms_version_accepted` resolves through |
| `list_versions` | method | Newest-first page of the history |
| `count` | method | Total versions, pairing with `list_versions` |

## Behavior

There is no update and no delete method here, and none could work: the migration `REVOKE ALL`s on `terms_versions` and re-grants only `SELECT, INSERT` to the application role, so append-only is a DB grant rather than a convention. That makes `deleted_at` structurally always `NULL`; the predicate stays only for house-style uniformity. Version numbering is `max_version() + 1` computed by the caller and enforced by the unique index on `(tenant_id, version)`, so a concurrent double-publish surfaces as an `IntegrityError` at `flush()` rather than two rows sharing a number. **`current()` must never be substituted for `by_version()`** on the customer-facing paths: a booking stores `terms_version_accepted`, and computing a cancellation consequence from the *current* version instead would let a boutique that republishes its policy silently rewrite the terms of appointments already agreed to — which is precisely the bug that column exists to prevent. `current()` is correct for the storefront's "here are the terms you are about to accept" and for the owner console's head-of-history display. Creation is throttled per tenant in [[backend/app/boutique/service.py]] because spam on an append-only table is permanent bloat.

## Depends On

- [[backend/app/models/terms_version.py]] — the `TermsVersion` ORM entity
- [[SQLAlchemy]] — `select` / `func`, `AsyncSession`

## Depended On By

- [[backend/app/boutique/service.py]] — publish (`max_version` + `insert`) and the owner-console history (`current`, `list_versions`, `count`)
- [[backend/app/storefront/service.py]] — `current()` for the terms a customer is shown before booking
- [[backend/app/booking/service.py]] — `current()` at booking time, whose number is pinned onto the booking
- [[backend/app/booking/manage.py]] — `by_version()` for the version the customer actually accepted

## Concepts

- [[Row Level Security]]
- [[Tenant Isolation]]
- [[Least Privilege Database Role]]

## Tests

- [[backend/tests/test_boutique_service.py]]
- [[backend/tests/test_booking_service.py]]
- [[backend/tests/test_booking_owner_db.py]]
- [[backend/tests/test_booking_comms_db.py]]

## Notes

The grant-level append-only stance is set in [[backend/migrations/versions/0005_boutique_settings.py]], which also creates `idx_terms_versions_tenant_version_unique`. `refundable_until_hours_before` and `forfeit_percent` travel with the text as one immutable bundle — the whole point is that a booking pins the policy *and* its numbers together.
