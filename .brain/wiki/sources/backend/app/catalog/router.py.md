---
tags: [backend, catalog, router, fastapi, python, api, rbac, security-headers]
sources: [backend/app/catalog/router.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/catalog/router.py
blob: e9bbb8e42429e16805bcc123fe1fde51c78ec065
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/catalog/router.py

**Role.** The eleven `/manage` catalog endpoints — a thin translator between HTTP and `CatalogService`'s frozen views — gated router-wide on `OWNER | SHIFT_MANAGER` and stamped router-wide with `Cache-Control: no-store`.

**Module.** [[backend/app/catalog/_index]] · **Layer.** api

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `router` | `APIRouter` | `prefix="/manage"`, router-level `Depends(_no_store)` + `Depends(require_role(OWNER, SHIFT_MANAGER))` |
| `get_catalog_service` / `get_media_storage` | dependency | Pull the singletons off `request.app.state`; the test suites override `get_media_storage` |
| `list_dresses` | `GET /manage/dresses` | `offset` / `limit` / `search` / `archived` query params |
| `create_dress` | `POST /manage/dresses` | → `DressResponse` |
| `get_dress` | `GET /manage/dresses/{dress_id}` | → `DressDetailResponse`, resolves archived rows |
| `update_dress` | `PATCH /manage/dresses/{dress_id}` | Full-replace body despite the verb |
| `archive_dress` | `DELETE /manage/dresses/{dress_id}` | → `OkResponse` |
| `restore_dress` | `POST /manage/dresses/{dress_id}/restore` | → `DressDetailResponse` |
| `replace_variants` | `PUT /manage/dresses/{dress_id}/variants` | Whole matrix |
| `presign_media` | `POST /manage/dresses/{dress_id}/media/presign` | → `PresignResponse` |
| `confirm_media` | `POST /manage/dresses/{dress_id}/media/{media_id}/confirm` | |
| `delete_media` | `DELETE /manage/dresses/{dress_id}/media/{media_id}` | |
| `reorder_media` | `PUT /manage/dresses/{dress_id}/media/order` | The one media route that works with no bucket |
| `_no_store` / `NO_STORE` | fn / const | Sets `cache-control: no-store` on every response |
| `_require_media_storage` | fn | Raises `MediaNotConfiguredError` (503) before any DB work |
| `_dress_fields` / `_dress_response` / `_dress_detail_response` / `_media_response` | fn | Hand-built projections from `DressView` / `MediaView` |

## Behavior

Each handler resolves the tenant with `get_current_tenant(request)` — host-derived, never a body or query field — and the dress from the URL path, so nothing a client sends can influence a storage key. Domain errors are not caught here at all: the service's six typed exceptions propagate to the explicit handlers registered in [[backend/app/main.py]], which is why adding a new typed error without a matching handler would surface as a 500 rather than the intended 4xx.

`_no_store` is attached to the **router**, not per route, and that is the point: nine of the eleven endpoints answer with a `DressResponse` or `DressDetailResponse` whose `cover.url` and `media[].url` are signed GETs valid for `SIGNED_GET_TTL_SECONDS`, and a tenth returns the POST policy itself. Setting the header centrally makes the invariant structural — a route added later cannot forget it — and the one route with nothing to protect (`archive_dress` → `OkResponse`) pays nothing for carrying it.

Role gating is uniform across the file: unlike [[backend/app/boutique/router.py]], no catalog route tightens to owner-only, so a shift manager can edit dresses, stock and photos. `get_current_staff` is additionally declared per handler as `Staff`, which is what makes `staff` available (and the session verified) inside the handler body even though the router-level `require_role` already ran.

`_require_media_storage` duplicates a check the service also performs. That is deliberate rather than redundant: the router is where the 503 belongs, refusing a media write before any database work so an unconfigured bucket cannot leave a pending row nobody could upload against — and the service keeps its own copy because the isolation suites call it directly, bypassing HTTP.

The response builders exist because only `VariantResponse` is a pure ORM projection. `DressResponse` and friends carry derived fields (`out_of_stock`, `media_count`, `cover`, `archived`), so `_dress_fields` assembles them from the view by hand. Note `archived` ships as a boolean derived from `row.deleted_at is not None` — the timestamp itself never leaves the server.

`list_dresses` spells its `offset` / `limit` bounds out longhand rather than reusing the shortcut from the boutique routes, because that shortcut only works where the default equals the maximum, and here the default (24) is far below the cap (100). The service clamps both again.

## Depends On

- [[backend/app/catalog/service.py]] — `CatalogService`, `DressView`, `MediaView`
- [[backend/app/catalog/schemas.py]] — every request and response model
- [[backend/app/catalog/validation.py]] — list limits, `MAX_SEARCH_LENGTH`, `VariantInput`
- [[backend/app/auth/dependencies.py]] — `get_current_staff`, `require_role`
- [[backend/app/auth/service.py]] — `StaffContext`
- [[backend/app/models/constants.py]] — `StaffRole`
- [[backend/app/tenancy/middleware.py]] — `get_current_tenant`
- [[backend/app/storage/base.py]] — `MediaStorage`, `MediaNotConfiguredError`
- [[backend/app/schemas.py]] — `OkResponse`
- [[FastAPI]]

## Depended On By

- [[backend/app/main.py]] — mounts this router after the boutique router, both at `prefix="/manage"`
- [[backend/tests/test_catalog_api.py]] · [[backend/tests/test_catalog_isolation.py]] · [[backend/tests/test_staff_role_gating.py]] — all override `get_media_storage`

## Concepts

- [[Role Based Access Control]]
- [[Tenant Resolution]]
- [[Media Upload Pipeline]]

## Tests

- [[backend/tests/test_catalog_api.py]] — endpoint behaviour and status codes
- [[backend/tests/test_staff_role_gating.py]] · [[backend/tests/test_staff_role_gating_integration.py]] — that every route here admits both roles
- [[backend/tests/test_catalog_isolation.py]] — cross-tenant 404s over HTTP

## Notes

The verbs are conventional REST (`PATCH`, `PUT`, `DELETE`) — the RPC-only routing convention in `.claude/rules/` is Spartan toolkit boilerplate for a stack this repo does not use and does not apply here.

`PATCH /manage/dresses/{dress_id}` takes a **full-replace** body: `UpdateDressRequest` requires every field. The verb is the misleading part, not the semantics.

Design context: [[.planning/specs/catalog-management.md]], [[.planning/specs/staff-roles-gating.md]].
