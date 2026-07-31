---
tags: [backend, db, repository, catalog, dresses, python, sqlalchemy]
sources: [backend/app/db/repositories/dresses.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/db/repositories/dresses.py
blob: de8a391bc42af4286f2de5306168713a4aaa0cca
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/db/repositories/dresses.py

**Role.** Every read and write of the `dresses` table: the id lookup all `/manage/dresses/...` routes resolve first, the active/archived paged list with an ILIKE name search, insert, whole-record field update, and the soft-delete / restore pair that flips `deleted_at`.

**Module.** [[backend/app/db/repositories/_index]] · **Layer.** db

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `_escape_like` | fn | Escapes `\`, `%` and `_` in a search term so an owner searching `50%_lace` gets a literal match, not a wildcard scan |
| `DressesRepository` | class | The repository; every method takes an explicit `AsyncSession` and `tenant_id` |
| `DressesRepository._scope` | method | Builds the shared predicate list — tenant, the archived/active branch, and the optional escaped ILIKE |
| `by_id` | method | Live dress only; unknown id, archived dress and another tenant's dress are one indistinguishable miss |
| `by_id_any_state` | method | Same lookup without the `deleted_at IS NULL` filter — only detail and restore may use it |
| `list_page` | method | Offset/limit page ordered `sort_order, created_at DESC, id` |
| `count` | method | The total that pairs with `list_page` under the identical scope |
| `insert` | method | Adds a `Dress`, flushes, refreshes |
| `update_fields` | method | Read-then-assign whole-record update; `None` when the dress is missing |
| `soft_delete` / `restore` | method | Guarded `UPDATE ... RETURNING id`; return whether a row in the expected state was hit |

## Behavior

`_scope` treats archived as an **exclusive** branch rather than a filter you can widen — active and archived are served by two separate partial indexes (`idx_dresses_tenant_active` and `idx_dresses_tenant_archived`), and a combined view would fall off both. The list order carries all four keys of those indexes; `id` is the tiebreaker that keeps a page from repeating or skipping a row when `sort_order` and `created_at` tie under concurrent inserts. `soft_delete` and `restore` are single guarded UPDATEs rather than read-then-write, so a second call answers `False` instead of re-stamping `deleted_at` or clearing an already-live row — and the boolean is all the caller needs, since both routes answer an ok-response. `update_fields` and `insert` both `refresh` after `flush`, which is how the DB-trigger-maintained `updated_at` gets back into the returned entity; the repository never assigns it. Tenant scoping is doubled: `dresses` is under FORCE RLS, and the explicit `tenant_id` predicate is the house's redundant defence-in-depth on top of it.

## Depends On

- [[backend/app/models/dress.py]] — the `Dress` ORM entity
- [[SQLAlchemy]] — `select` / `update` / `func`, `AsyncSession`

## Depended On By

- [[backend/app/catalog/service.py]] — owner-side catalog CRUD (list, detail, create, update, archive, restore)
- [[backend/app/storefront/service.py]] — public catalog: `list_page` + `count` for the grid, `by_id` for the detail page
- [[backend/app/booking/service.py]] — resolves the optional dress a customer picked when creating a booking

## Concepts

- [[Row Level Security]]
- [[Tenant Isolation]]
- [[Soft Delete]]

## Tests

- [[backend/tests/test_catalog_isolation.py]]
- [[backend/tests/test_storefront_isolation.py]]
- [[backend/tests/test_storefront_integration.py]]
- [[backend/tests/test_storefront_validation.py]]
- [[backend/tests/test_booking_service.py]]
- [[backend/tests/test_catalog_integration.py]]

## Notes

There is deliberately **no** unique index on `(tenant_id, name)` — one designer model in two colours is legitimate, and a dress is only ever addressed by id (see [[backend/migrations/versions/0006_catalog.py]]). `by_id_any_state` is the one hole in the "archived is missing" rule; widening its use would leak archived stock into the storefront.
