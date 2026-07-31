---
tags: [backend, storage, media, python, degradation]
sources: [backend/app/storage/unconfigured.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/storage/unconfigured.py
blob: 79f320ed5f1e9f06b400c0cfd37e57f817495cde
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# backend/app/storage/unconfigured.py

**Role.** The null-object implementation of the media storage port for deployments with no `MEDIA_BUCKET` — every method raises `MediaNotConfiguredError` so the router answers one 503 and the rest of the catalog keeps working.

**Module.** [[backend/app/storage/_index]] · **Layer.** platform

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `UnconfiguredMediaStorage` | class | Satisfies `MediaStorage`; `is_configured` is `False` and all six operations raise |

## Behavior

Chosen over `None` for one reason: a `None` storage would grow a null check at every call site, and a call site can forget one. Here every path fails loudly with the same typed error, [[backend/app/main.py]] maps it to a single 503 `MEDIA_NOT_CONFIGURED` body, and no vendor text is involved because there is no vendor. The `is_configured` flag is not redundant with the raises — it is what lets read paths *avoid* the error entirely: [[backend/app/catalog/service.py]] and [[backend/app/storefront/service.py]] check it and serialise `url` as `null`, so dress and variant CRUD, reorder and every read keep working on a bucket-less deployment. **Running without a bucket is a supported deployment, not a misconfiguration** — which is why [[backend/app/core/config.py]] treats a *missing* `media_bucket` as fine while a *wrong* media config aborts boot. `MediaNotConfiguredError` is also what [[backend/app/storage/s3.py]] raises when credentials are absent or partial, so a bucket with unusable credentials degrades along exactly this path rather than through a different one.

## Depends On

- [[backend/app/storage/base.py]] — `MediaNotConfiguredError`, `ObjectHead`, `PresignedPost`

## Depended On By

- [[backend/app/main.py]] — `_build_media_storage` returns this when `settings.media_bucket` is unset
- [[backend/tests/test_storage_port.py]]
- [[backend/tests/test_storefront_api.py]]
- [[backend/tests/test_storefront_validation.py]]
- [[backend/tests/test_catalog_api.py]]

## Concepts

- [[Media Storage]]
- [[Fail Closed Defaults]]

## Tests

- [[backend/tests/test_storage_port.py]] — `test_unconfigured_storage_is_never_configured`, `test_unconfigured_storage_raises_on_every_method`, `test_create_app_selects_unconfigured_storage_without_a_bucket`, `test_unconfigured_storage_serialises_a_null_url_instead_of_raising`

## Notes

[[backend/app/api/routes/health.py]] reports `media: "unconfigured"` for this instance — state only, never bucket identity, because `/health` is unauthenticated and host-agnostic. That field is how a staging smoke test learns the app came up bucket-less before it tries a presign, which matters because `Settings.model_config` is `extra="ignore"` and a typo'd `MEDIA_BUKCET` is discarded silently.
