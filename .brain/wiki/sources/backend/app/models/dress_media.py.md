---
tags: [backend, models, db, catalog, media, s3, security, python]
sources: [backend/app/models/dress_media.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/models/dress_media.py
blob: 4bf52fbb1489e40411cee89b7e0646138d4fc0e1
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/models/dress_media.py

**Role.** The `dress_media` table: one uploaded photo per row, written `pending` at presign time with its storage key already computed, and flipped to `ready` only after the confirm step has verified the object's magic bytes.

**Module.** [[backend/app/models/_index]] · **Layer.** models

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `DressMedia` | class | `StandardColumns, Base` → `dress_media` |
| `tenant_id` / `dress_id` | columns | Owning tenant and parent dress (ids only — no FK constraints) |
| `storage_key` | column | Object key in the media bucket; **embeds this row's own `id`** |
| `content_type` | column | DB `CHECK IN ('image/jpeg','image/png','image/webp')` |
| `byte_size` | column | Client-declared size; DB `CHECK > 0 AND <= 20971520` (20 MiB) |
| `status` | column | [[backend/app/models/constants.py#DressMediaStatus]] — `pending` \| `ready`, DB-pinned, default `pending` |
| `sort_order` | column | Gallery order within the dress, default `0` |

## Behavior

The row's lifecycle is two statements and no patching. `storage_key` embeds the media row's own primary key, so the service mints the UUID client-side, computes the key, and writes both in the **single INSERT** at presign time — the key is never assigned afterwards and never mutated. (`uuid_generate_v4()` remains the column default for any non-service writer.) `status` starts `pending` and only the confirm path, having fetched the object and checked its magic bytes, promotes it to `ready`. Two of the three `CHECK`s here are **security boundaries rather than duplicated validation**: an `image/svg+xml` object served from our own bucket is stored XSS on the storefront, and a third status value the confirm path never writes would be a way to put an unverified object on the gallery read path. That is why [[backend/app/models/constants.py#DressMediaStatus]] cannot gain a member without a migration. `byte_size` and `content_type` are client *declarations* enforced twice — once by the POST policy S3 signs at presign, once by these `CHECK`s — and the byte ceiling is set at 2× the service constant rather than the 10× used elsewhere in [[backend/migrations/versions/0006_catalog.py]], precisely because the presigned policy also encodes that bound.

Three indexes back the three access patterns. `idx_dress_media_dress_ready` (`WHERE deleted_at IS NULL AND status = 'ready'`) is the gallery read; `idx_dress_media_pending` (`WHERE deleted_at IS NULL AND status = 'pending'`) is the stale-upload sweep, keyed tenant-first so one boutique's sweep never costs anything proportional to platform-wide upload traffic; and `idx_dress_media_storage_key_unique` on `(tenant_id, storage_key)` is a **plain** unique index acting as a regression guard on the key builder — since the key embeds the row's PK, a collision is only possible if `build_media_key` ever stops including `media_id`, and this turns that into an `IntegrityError` in CI rather than two rows pointing at one object.

## Depends On

- [[backend/app/models/base.py]] — `Base`, `StandardColumns`
- [[backend/app/models/constants.py]] — `DressMediaStatus`, interpolated into the `status` server default
- [[SQLAlchemy]]

## Depended On By

- [[backend/app/db/repositories/dress_media.py]] — presign insert, confirm promotion, gallery and pending queries
- [[backend/app/catalog/service.py]] — the presign / confirm flow and the byte + content-type policy
- [[backend/app/storefront/router.py]] — resolves `ready` media into the public gallery

## Concepts

- [[Row Level Security]]
- [[Tenant Isolation]]

## Tests

- [[backend/tests/test_catalog_models.py]] — `test_dress_media_shape`, `test_dress_media_status_values`
- [[backend/tests/test_media_upload_s3.py]] — presign → upload → confirm against a real object store
- [[backend/tests/test_storage_port.py]] — key construction and the storage seam
- [[backend/tests/test_catalog_api.py]], [[backend/tests/test_storefront_api.py]]

## Notes

Bucket, region and endpoint are deployment identity in [[backend/app/core/config.py]]; the byte cap and allowed content types are product policy in [[backend/app/catalog/validation.py]]. Neither set belongs in the other. DDL: [[backend/migrations/versions/0006_catalog.py]]. Design context: [[.planning/specs/catalog-management.md]].
