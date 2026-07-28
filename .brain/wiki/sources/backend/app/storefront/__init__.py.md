---
tags: [backend, storefront, python, package, public-api]
sources: [backend/app/storefront/__init__.py]
created: 2026-07-27
updated: 2026-07-27
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/storefront/__init__.py
blob: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
commit: c9b045a8b70028db0de520384cdecf68f9b34c74
kind: code
applicability: active
---

# backend/app/storefront/__init__.py

**Role.** Empty file marking `app.storefront` as a package — the platform's only anonymous HTTP surface. It owns no business logic: the storefront reads the same `CatalogService` and `BoutiqueSettingsService` the owner console uses and re-projects them through public-only wire models.

**Module.** [[backend/app/storefront/_index]] · **Layer.** api

## Behavior

Zero bytes, no re-exports. The package exists so the public projection has a home separate from `app/catalog/` and `app/boutique/` — a reviewer asking "what can an anonymous visitor see?" reads exactly these two files.

## Concepts

- [[Tenant Resolution]]
