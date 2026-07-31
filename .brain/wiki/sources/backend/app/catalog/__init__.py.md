---
tags: [backend, catalog, python, package-marker]
sources: [backend/app/catalog/__init__.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/catalog/__init__.py
blob: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/catalog/__init__.py

**Role.** Empty package marker for the owner's dress catalogue module — it re-exports nothing, so every consumer imports the concrete submodule by name.

**Module.** [[backend/app/catalog/_index]] · **Layer.** api

## Public Surface

Nothing. Zero bytes.

## Behavior

Its emptiness is the contract: [[backend/app/main.py]], [[backend/app/storefront/service.py]] and [[backend/app/booking/service.py]] all reach past it (`from app.catalog.service import …`, `from app.catalog.validation import normalize_size_label`), so there is no convenience surface here that could drift from the modules it would re-export.

## Depends On

Nothing.

## Depended On By

- Every `app.catalog.*` import in the tree, implicitly.

## Concepts

- [[Package Layout]]

## Tests

None of its own.
