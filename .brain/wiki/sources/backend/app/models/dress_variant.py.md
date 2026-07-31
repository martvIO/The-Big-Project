---
tags: [backend, models, python, catalog, inventory, sqlalchemy]
sources: [backend/app/models/dress_variant.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/models/dress_variant.py
blob: 9ec58e50261af4d934275c4fcecb1bc93c9a989b
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/models/dress_variant.py

**Role.** One size bucket of one dress — the only place stock quantity is recorded, and therefore the sole input to the storefront's "out of stock" treatment.

**Module.** [[backend/app/models/_index]] · **Layer.** models

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `DressVariant` | class | ORM mapping for `dress_variants`; `StandardColumns` + `Base` |
| `tenant_id` | col | `UUID NOT NULL` — RLS discriminator |
| `dress_id` | col | `UUID NOT NULL` — the parent dress. No FK, by house convention |
| `size_label` | col | `TEXT NOT NULL` — free-form ("38", "US 6", Hebrew labels); normalized by the service |
| `quantity` | col | `INTEGER NOT NULL DEFAULT 0`, DB `CHECK (0 … 10000)` |
| `sort_order` | col | `INTEGER NOT NULL DEFAULT 0` — the owner's chosen display order |

## Behavior

The uniqueness rule is the whole point of this file's docstring. [[backend/migrations/versions/0006_catalog.py]] builds an **expression** index on `(tenant_id, dress_id, lower(size_label)) WHERE deleted_at IS NULL`. [[backend/app/catalog/service.py]] already strips and collapses whitespace, so `lower()` is the part the service cannot do without also mangling the label the owner typed: without it, "US 6" and "us 6" would persist as two stock buckets for one physical size and the storefront's availability answer would be wrong. Hebrew has no case, so on the common path `lower()` is a no-op and the guard only ever fires on Latin custom labels.

Because the unique index is partial on `deleted_at IS NULL`, a retired size label is re-usable, and archival is a two-step dance the repository owns rather than the model: `soft_delete_all` retires a dress's whole active size matrix with one timestamp, and `restore_archived_with` un-archives **only** the rows carrying that same stamp — matching on the dress's own `deleted_at` is what keeps a size the owner deleted last week deleted when the dress itself is restored. The `CHECK (quantity <= 10000)` is an absurdity ceiling in the house style: it stops a broken write path, it does not encode product policy (the real limits live in [[backend/app/catalog/validation.py]]).

Reads never go one-variant-at-a-time. `DressVariantsRepository.aggregate_by_dress` returns one pre-aggregated `VariantAggregate` row per dress so the catalog and storefront lists compute `out_of_stock` in a single extra statement rather than a per-row query.

## Depends On

- [[backend/app/models/base.py]] — `Base`, `StandardColumns`
- [[SQLAlchemy]] — declarative mapping

## Depended On By

- [[backend/app/db/repositories/dress_variants.py]] — the only repository over this table
- [[backend/app/catalog/service.py]] — the owner-side size matrix editor
- [[backend/app/storefront/service.py]] — computes `out_of_stock` from the aggregate
- [[backend/app/booking/service.py]] — reads variants when a booking names a dress

## Concepts

- [[Row Level Security]]
- [[Tenant Isolation]]

## Tests

- [[backend/tests/test_catalog_models.py]] — schema-shape assertions (standard columns, nullability), no database
- [[backend/tests/test_catalog_integration.py]] — the real DDL: unique index, `CHECK`, archive/restore round trip
- [[backend/tests/test_catalog_isolation.py]] — cross-tenant reads return nothing
- [[backend/tests/test_catalog_api.py]], [[backend/tests/test_storefront_integration.py]], [[backend/tests/test_storefront_isolation.py]], [[backend/tests/test_booking_service.py]]

## Notes

The sibling models [[backend/app/models/dress.py]] and [[backend/app/models/dress_media.py]] complete the catalog triple; media carries a status boundary (`pending` → `ready`) that this table does not.

Design context: [[.planning/specs/catalog-management.md]], [[.planning/plans/catalog-management.md]].
