---
tags: [backend, api, python, package]
sources: [backend/app/api/__init__.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/api/__init__.py
blob: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# backend/app/api/__init__.py

**Role.** Empty file marking `app.api` as a package. It holds only `routes/`, and `routes/` holds only the infrastructure probe — every product surface lives in its own domain package (`app/auth/`, `app/catalog/`, `app/booking/`, `app/storefront/`) with its router beside its service.

**Module.** [[backend/app/api/_index]] · **Layer.** api

## Behavior

Zero bytes, no re-exports. Reading this package as "where the API lives" is the one mistake worth avoiding: [[backend/app/main.py]] includes seven routers and only one of them ([[backend/app/api/routes/health.py]]) comes from here.

## Depended On By

- [[backend/app/main.py]] — `from app.api.routes.health import router as health_router`

## Notes

The package survives from the scaffold in [[.planning/specs/repo-scaffolds-and-ci.md]], before the per-domain layout settled. Nothing new should be added here.
