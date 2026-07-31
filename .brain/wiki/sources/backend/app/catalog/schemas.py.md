---
tags: [backend, catalog, schemas, pydantic, python, api]
sources: [backend/app/catalog/schemas.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/catalog/schemas.py
blob: 71fead16d509754c5296babdcdcf482000eafc85
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/catalog/schemas.py

**Role.** The wire contract for the `/manage` catalog API — extra-forbidding request models whose `Field` bounds mirror [[backend/app/catalog/validation.py]], plus response models for dresses, variants, media and the presigned POST.

**Module.** [[backend/app/catalog/_index]] · **Layer.** api

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `CreateDressRequest` | request | Name, optional description/price, `price_visible`, `reserved`, `sort_order` — all nullable scalars default to `None` |
| `UpdateDressRequest` | request | Full replace: every field required, and the nullable scalars carry **no default** |
| `VariantRequest` / `ReplaceVariantsRequest` | request | One size row; the list is capped at `MAX_VARIANTS_PER_DRESS` |
| `PresignRequest` | request | Exactly `content_type` + `byte_size` — neither influences the storage key |
| `ReorderMediaRequest` | request | `media_ids` list capped at `MAX_MEDIA_PER_DRESS` |
| `VariantResponse` | response | The **only** model with `from_attributes=True`; carries raw `quantity` (manage-only) |
| `MediaResponse` | response | `url` / `url_expires_at` are nullable — a missing bucket serialises null, it does not fail the read |
| `PresignResponse` | response | `media_id`, `url`, POST-policy `fields`, `expires_in`, `max_bytes` |
| `DressResponse` | response | Row fields plus derived `out_of_stock`, `total_quantity`, `variant_count`, `media_count`, `cover`, `archived` |
| `DressDetailResponse` | response | `DressResponse` + `variants`, `media`, `media_uploads_enabled`, `media_slots_remaining` |
| `DressListResponse` | response | House envelope: `items` / `total` / `offset` / `limit` |
| `MAX_CONTENT_TYPE_LENGTH` | const | 64 — long enough for any accepted type, short enough that a megabyte of junk never reaches the validator |

## Behavior

Requests extend `ForbidExtraModel` (from [[backend/app/schemas.py]]), so an unknown key is a 422 rather than a silently ignored field; responses extend plain `BaseModel`. The `Field` bounds here are a *first* gate that keeps oversized bodies out of the domain layer — the authoritative rules (label normalisation, duplicate sizes, the accepted content-type set, the byte-precise checks) still run in `validation.py` and surface as house-shape 400s.

`ConfigDict(from_attributes=True)` is set on `VariantResponse` **only**, and that asymmetry is deliberate: it is the sole pure ORM projection. `DressResponse`, `DressDetailResponse` and `MediaResponse` all carry fields that are not columns — `out_of_stock`, `media_count`, `cover`, `archived`, `url` — so `model_validate(row)` would raise; [[backend/app/catalog/router.py]] builds them by hand from the service's frozen `DressView` / `MediaView`.

The most easily-reintroduced bug in the file is documented in `UpdateDressRequest`: its nullable scalars (`description`, `price_agorot`) are required *with no default*. Copying `CreateDressRequest`'s `default=None` across would restore exactly the silent-clear the full-replace rule exists to prevent — an omitted key would wipe a stored value instead of being rejected.

`MediaResponse.url` being nullable is the wire half of the service's degradation rule: with no bucket configured (or with signing failing on rotated credentials) reads keep working with the gallery unrendered, and only the media *write* endpoints answer 503. `PresignResponse.fields` is bearer material for the whole TTL — never logged, never in an error body, and returned under `Cache-Control: no-store` set at the router.

`DressDetailResponse.media_slots_remaining` is `MAX_MEDIA_PER_DRESS − (ready + non-expired pending)`; it exists only to enable or disable the client's file input, and `MEDIA_LIMIT_REACHED` remains the server-side authority, so a stale client converges after one refetch rather than corrupting anything.

## Depends On

- [[backend/app/catalog/validation.py]] — every `Field` bound is one of its constants
- [[backend/app/schemas.py]] — `ForbidExtraModel`
- [[Pydantic]] — `BaseModel`, `ConfigDict`, `Field`

## Depended On By

- [[backend/app/catalog/router.py]] — request bodies and every declared response type
- [[backend/tests/test_storefront_api.py]] — imports `DressResponse` to assert the storefront's shape is a deliberate subset

## Concepts

- [[Full Replace Update Semantics]]
- [[Media Upload Pipeline]]

## Tests

- [[backend/tests/test_catalog_api.py]] — request rejection and response shape over the ASGI app
- [[backend/tests/test_storefront_api.py]] — cross-checks which manage-only fields (raw `quantity`) must never leak to the public surface

## Notes

`VariantResponse.quantity` is manage-only by policy: raw stock counts are boutique-confidential, and the storefront's variant shape is `{size_label, available}` instead. That divergence is a spec decision, not an oversight — see [[backend/app/storefront/schemas.py]].
