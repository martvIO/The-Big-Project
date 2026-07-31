---
tags: [backend, python]
sources: [backend/app/api]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/api
blob: 4709839e21bc78b6a7da4c2df08878371a21e2fa
commit: 13d107b8b16f1f2676f1cdb1c994f95822fe2ba0
kind: directory
applicability: active
---

# backend/app/api/

**Purpose.** A scaffold vestige. It holds only the `/health` probe — every other router lives in its own domain package, so a reader looking here for "the API" is in the wrong place.

**Parent.** [[backend/app/_index]]

## Files

- [[backend/app/api/__init__.py]] — Empty file marking `app.api` as a package. It holds only `routes/`, and `routes/` holds only the infrastructure probe — every product surface lives in its own domain package (`app/auth/`, `app/catalog/`, `app/booking/`, `app/storefront/`)…

## Subdirectories

- [[backend/app/api/routes/_index]] — The health probe, and nothing else.
