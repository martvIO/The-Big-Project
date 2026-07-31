---
tags: [backend, db, python, catalog, dresses, repositories, soft-delete]
sources: [backend/app/db/repositories/dress_variants.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/db/repositories/dress_variants.py
blob: e842f082b12c8b1289e59cdcdc3084ca060e368a
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/db/repositories/dress_variants.py

**Role.** The size matrix of a dress — one row per `(dress, size_label)` with a quantity — read per dress for the detail page, pre-aggregated per dress for the list page, and replaced wholesale rather than patched.

**Module.** [[backend/app/db/repositories/_index]] · **Layer.** db

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `VariantAggregate` | frozen dataclass | `variant_count` + `total_quantity` for one dress |
| `DressVariantsRepository` | class | Stateless; `AsyncSession` passed per call |
| `list_active` | method | Live variants of one dress, ordered by `sort_order` then `id` |
| `aggregate_by_dress` | method | One `GROUP BY` for a whole page of dresses; empty input short-circuits |
| `insert` | method | One variant; the partial unique index surfaces on flush |
| `soft_delete_all` | method | Retires the dress's whole live matrix; returns the count |
| `restore_archived_with` | method | Un-deletes only the rows stamped by one archive instant |

## Behavior

`aggregate_by_dress` exists so the list page's `out_of_stock` badge is computed from one pre-aggregated group row per dress instead of a per-row query the page did not pay for — the dataclass docstring makes that the point of the type. `func.coalesce(sum, 0)` matters because a dress whose only variants are soft-deleted groups to no row at all, and a dress with variants summing to nothing must read as `0`, not `NULL`. Empty input returns `{}` before touching the database.

`insert` has no pre-check for a duplicate size: `idx_dress_variants_dress_size_unique` is on `lower(size_label)` over live rows (migration [[backend/migrations/versions/0006_catalog.py]]), so "M" and "m" collide, and the `IntegrityError` on flush is the report. The `id` tiebreak on `list_active`'s ordering keeps two variants sharing a `sort_order` in a stable order across page loads.

The two soft-delete methods form the archive/restore pair, and the asymmetry between them is the interesting part. `soft_delete_all` stamps only rows that are currently live (`deleted_at IS NULL`), which is what leaves a size the owner deleted last week on its *older* timestamp. `restore_archived_with` then matches on `deleted_at == archived_at` — the dress's own archive instant — so an archive/restore cycle restores exactly what the archive took and nothing else. Matching on `deleted_at IS NOT NULL` instead would resurrect deletions the owner made deliberately. `soft_delete_all` is also the first half of the atomic replace used when the owner edits the size matrix, and the second step of the dress archive cascade after [[backend/app/db/repositories/dress_media.py]].

Every statement carries `tenant_id` and (except `restore_archived_with`, which keys on the archive stamp) `deleted_at IS NULL`. The tenant predicate is redundant with FORCE RLS and kept as defense-in-depth.

## Depends On

- [[backend/app/models/dress_variant.py]] — the ORM model
- [[SQLAlchemy]] — `select`, `update`, `func.count`, `func.sum`, `func.coalesce`, `AsyncSession`

## Depended On By

- [[backend/app/catalog/service.py]] — owner-side CRUD, the archive cascade, and the list page's `VariantAggregate`
- [[backend/app/storefront/service.py]] — the public size list
- [[backend/app/booking/service.py]] — validates a requested `dress_size` against the live matrix

## Concepts

- [[Row Level Security]]
- [[Tenant Isolation]]
- [[Partial Unique Index]]
- [[Soft Delete]]

## Tests

- [[backend/tests/test_catalog_integration.py]] — CRUD, replace, archive/restore round-trips
- [[backend/tests/test_catalog_isolation.py]] — `test_repositories_return_nothing_for_another_tenants_ids`
- [[backend/tests/test_storefront_isolation.py]] · [[backend/tests/test_booking_service.py]]

## Notes

`quantity` is inventory, not a booking capacity — seat capacity lives on the availability rule, see [[backend/app/db/repositories/availability.py]].
