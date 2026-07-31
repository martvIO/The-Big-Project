---
tags: [backend, python]
sources: [backend/app/storefront]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/storefront
blob: 4b7512e3eda6c04eed9b34e0078f7f3d50410d68
commit: 13d107b8b16f1f2676f1cdb1c994f95822fe2ba0
kind: directory
applicability: active
---

# backend/app/storefront/

**Purpose.** The public, anonymous read surface: the catalogue a bride browses and the slot grid she books from. Contractually GET-only and cookie-blind.

**Parent.** [[backend/app/_index]]

## Files

- [[backend/app/storefront/__init__.py]] — Empty file marking `app.storefront` as a package — the platform's only anonymous HTTP surface. It owns no business logic: the storefront reads the same `CatalogService` and `BoutiqueSettingsService` the owner console uses and re-projects…
- [[backend/app/storefront/router.py]] — The public storefront read API: **six** anonymous, tenant-scoped `GET`s plus the pure projection functions that map `StorefrontService`'s frozen views onto the public wire models. Three are F10's catalog/identity reads (`/dresses`…
- [[backend/app/storefront/schemas.py]] — The public wire models. Twelve response models, no request model — the only client-supplied values on this surface are `offset`, `limit` and the `/slots` date window, all bounded on the route. Renamed and flattened in the F10…
- [[backend/app/storefront/service.py]] — All read logic behind the anonymous storefront — dress list, dress detail, bookable slot grid, appointment types, current terms and the boutique/about payload — assembled from repositories directly rather than through `CatalogService`, so…
- [[backend/app/storefront/validation.py]] — The public storefront's named bounds, its two error types, the boutique's wall clock (`Asia/Jerusalem`) and `profile_text` — the single place the `""`-to-`null` collapse for published profile strings lives. Small, but it is imported by six…
