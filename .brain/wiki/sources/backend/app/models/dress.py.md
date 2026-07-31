---
tags: [backend, models, db, catalog, storefront, python]
sources: [backend/app/models/dress.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/models/dress.py
blob: d0cabed8e5790e780184219a8d62e73020391dbc
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/models/dress.py

**Role.** The `dresses` table: one catalog item per row — name, optional price in agorot with its own visibility flag, a manual `reserved` marker and a display order — with soft delete doubling as the archive the owner can read back.

**Module.** [[backend/app/models/_index]] · **Layer.** models

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `Dress` | class | `StandardColumns, Base` → `dresses` |
| `tenant_id` | column | Owning tenant; RLS predicate and leading key of both list indexes |
| `name` | column | TEXT, NOT NULL — **not unique**, deliberately |
| `description` | column | Nullable free text |
| `price_agorot` | column | Nullable INTEGER — money in agorot, never float. NULL = no price recorded |
| `price_visible` | column | Default `true`; hides the price on the storefront without erasing it |
| `reserved` | column | Default `false`; the manual, date-less owner flag |
| `sort_order` | column | Default `0`; first key of the documented list order |

## Behavior

**No stock column, on purpose.** `out_of_stock` is derived from the dress's rows in [[backend/app/models/dress_variant.py]] on every read, so a badge can never disagree with the size matrix — the alternative (a cached boolean) has exactly one failure mode and it is the one customers notice. **Names are not unique**, and there is no index attempting it: a boutique legitimately carries one designer model in two colours, and a dress is only ever addressed by id. `price_agorot` and `price_visible` are separate because hiding a price is a display decision ("price on request") that must not destroy the number the owner recorded; the DB `CHECK` allows NULL or `1..1_000_000_000` agorot, an absurdity ceiling at 10× the service constant so tightening product policy in [[backend/app/catalog/validation.py]] never needs a migration.

Soft delete is the archive, and the archive is a first-class view rather than a tombstone: [[backend/migrations/versions/0006_catalog.py]] creates **two** indexes over the same four columns — `idx_dresses_tenant_active … WHERE deleted_at IS NULL` and `idx_dresses_tenant_archived … WHERE deleted_at IS NOT NULL` — so both the live catalog and the archive page are index scans. Both carry all four keys of the documented list order (`sort_order` ASC, `created_at` DESC, `id` ASC), which is what keeps paging stable while other rows are being inserted concurrently. `reserved` is the manual owner flag with no dates attached; E5's date-bound reservation supersedes it rather than extending it.

## Depends On

- [[backend/app/models/base.py]] — `Base`, `StandardColumns`
- [[SQLAlchemy]]

## Depended On By

- [[backend/app/db/repositories/dresses.py]] — list/archive queries and CRUD
- [[backend/app/catalog/service.py]] — owner-side catalog management
- [[backend/app/storefront/router.py]], [[backend/app/storefront/service.py]] — the public gallery

## Concepts

- [[Row Level Security]]
- [[Tenant Isolation]]

## Tests

- [[backend/tests/test_catalog_models.py]] — `test_dress_shape`, `test_all_catalog_tables_carry_standard_columns`
- [[backend/tests/test_catalog_api.py]] — CRUD, archive, list order
- [[backend/tests/test_storefront_api.py]], [[backend/tests/test_storefront_validation.py]] — the public read path and price visibility

## Notes

A booking snapshots `dress_name` and `dress_size` while keeping `dress_id` live ([[backend/app/models/booking.py]]), so archiving a dress never corrupts an existing appointment. DDL: [[backend/migrations/versions/0006_catalog.py]]. Design context: [[.planning/specs/catalog-management.md]].
