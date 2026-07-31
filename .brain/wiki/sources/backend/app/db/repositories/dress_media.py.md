---
tags: [backend, db, python, catalog, media, s3, repositories, soft-delete]
sources: [backend/app/db/repositories/dress_media.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/db/repositories/dress_media.py
blob: c8ef5eb1f19a864351c2079844d6b8579b4a1949
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/db/repositories/dress_media.py

**Role.** The `dress_media` table's whole lifecycle — mint a `pending` row that owns its storage key, promote it to `ready` on confirm, sweep pendings that were abandoned mid-upload, and serve the gallery and the list page's cover photo — with every statement keyed on all three of `(tenant_id, dress_id, media_id)`.

**Module.** [[backend/app/db/repositories/_index]] · **Layer.** db

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `MediaCover` | frozen dataclass | One dress's cover row plus its ready-photo count |
| `_stale_before` | fn | `now() - interval` computed **by the database**, via `make_interval` |
| `DressMediaRepository` | class | Stateless; `AsyncSession` passed per call |
| `by_id` | method | One live row addressed through its dress |
| `list_ready` | method | The gallery read path — `ready` only |
| `covers_by_dress` | method | `DISTINCT ON` cover + windowed count, one statement per page |
| `count_active` | method | Ready rows plus pendings young enough to still be in flight |
| `max_ready_sort_order` | method | `-1` on an empty gallery so the caller's `+ 1` is slot 0 |
| `insert_pending` | method | The only statement that ever writes `storage_key` |
| `sweep_stale_pendings` | method | Soft-deletes abandoned pendings and returns their `(id, key)` pairs |
| `promote_to_ready` | method | Confirm; idempotent via a `status = 'pending'` predicate |
| `set_sort_order` | method | Reorders a ready row |
| `soft_delete` | method | Accepts either status |
| `soft_delete_all` | method | First step of the dress archive cascade |
| `restore_archived_with` | method | Un-deletes only rows stamped by one archive instant |

## Behavior

**Addressing is three-part on purpose.** Every method carries `tenant_id`, `dress_id` **and** the media id in its WHERE, alongside `deleted_at IS NULL`. The class docstring states the invariant: a media id that exists but belongs to a *different dress of the same tenant* must be a miss, never a silent re-parent. RLS alone would not catch that, since both dresses belong to the bound tenant — this is the one place in the package where the extra predicate is a real control rather than only defense-in-depth. [[backend/tests/test_catalog_isolation.py]] pins it with `test_media_addressed_through_the_wrong_dress_of_the_same_tenant_is_a_miss`.

**The pending/ready split is a two-phase upload.** `insert_pending` takes both `media_id` and `storage_key` as required arguments because the key embeds the row's own id: the service mints the UUID client-side, builds the key, and this is the single statement that ever writes it — never patched afterwards, never mutated (`idx_dress_media_storage_key_unique`, migration [[backend/migrations/versions/0006_catalog.py]]). `list_ready` filters to `ready` because a pending row is an *unverified object* and must never reach a signed URL. `promote_to_ready`'s `status = 'pending'` predicate is confirm's idempotency guard — a retried confirm updates zero rows instead of double-bumping `sort_order` — and the caller holds the per-dress media advisory lock.

**Time is the database's, not the application's.** `_stale_before` builds `now() - make_interval(...)` in SQL because `created_at` is stamped with `transaction_timestamp()`; comparing it against a Python clock would make the sweep depend on two clocks agreeing. Note `make_interval`'s positional order is `(years, months, weeks, days, hours, mins, secs)`, which is why the call is six zeros and then the seconds. `count_active` counts ready rows **or** pendings newer than the cutoff, so an abandoned pending stops occupying a gallery slot instead of locking it for the whole TTL; `sweep_stale_pendings` uses the same expression with the opposite comparison and hands back the `(id, storage_key)` pairs — it is the only holder of those keys, and returning them is what bounds the S3 orphan window instead of leaving objects forever.

`sweep_stale_pendings` is also the only statement here whose `RETURNING` is more than the primary key, so it sets `synchronize_session=False`: ORM session synchronization would want that `RETURNING` for itself, and since nothing re-reads these rows in this session, opting out avoids the contention.

**`covers_by_dress` is one statement for a whole page.** `DISTINCT ON (dress_id)` with `ORDER BY dress_id, sort_order, id` picks the first ready photo as the cover, while `count() OVER (PARTITION BY dress_id)` runs *before* `DISTINCT` is applied, so `media_count` still sees every ready row of the dress rather than the single surviving one. Empty input returns `{}` without a round trip.

**Archive/restore is asymmetric, deliberately.** `soft_delete_all` stamps only currently-live rows, so a photo the owner deleted last week keeps its older `deleted_at`; `restore_archived_with` matches `deleted_at == archived_at` so an archive/restore cycle restores exactly what the archive took. `soft_delete` accepts a row in **either** status — deleting a pending row frees a gallery slot immediately and is the client's abort path after a failed upload.

## Depends On

- [[backend/app/models/dress_media.py]] — the ORM model
- [[backend/app/models/constants.py]] — `DressMediaStatus`
- [[SQLAlchemy]] — `select`, `update`, `or_`, `func.count/max/coalesce/now/make_interval`, window functions, `AsyncSession`

## Depended On By

- [[backend/app/catalog/service.py]] — presign, confirm, reorder, delete, the sweep, and the archive cascade
- [[backend/app/storefront/service.py]] — the public gallery and list covers

## Concepts

- [[Row Level Security]]
- [[Tenant Isolation]]
- [[Soft Delete]]

## Tests

- [[backend/tests/test_catalog_integration.py]] — the pending→ready lifecycle, sweep, reorder, archive/restore
- [[backend/tests/test_catalog_isolation.py]] — `test_media_addressed_through_the_wrong_dress_of_the_same_tenant_is_a_miss`, `test_a_key_minted_for_one_tenant_never_carries_another_tenants_ids`
- [[backend/tests/test_storefront_isolation.py]]
- [[backend/tests/test_media_upload_s3.py]] — the object side of the same lifecycle

## Notes

`ttl_seconds` is passed in rather than read from settings here — the byte caps and TTLs are product policy and live once in [[backend/app/catalog/validation.py]] (`PENDING_MEDIA_TTL_SECONDS`, `MAX_MEDIA_PER_DRESS`, `MAX_UPLOAD_BYTES`), injected into `DressCatalogService` so tests can shorten the TTL without touching env.

`MediaCover.row` is the full `DressMedia` ORM instance, not a projection, so callers can presign directly from it.
