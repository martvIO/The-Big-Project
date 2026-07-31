---
tags: [backend, api, python, package]
sources: [backend/app/api/routes/__init__.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/api/routes/__init__.py
blob: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# backend/app/api/routes/__init__.py

**Role.** Empty file marking `app.api.routes` as a package; its only member is the unauthenticated `/health` probe.

**Module.** [[backend/app/api/routes/_index]] · **Layer.** api

## Behavior

Zero bytes, no re-exports. Deliberately does not aggregate routers: [[backend/app/main.py]] imports each router by its own module path and controls include order explicitly, because five routers share the `/manage` prefix and a duplicated `(method, path)` would silently shadow.

## Depended On By

- [[backend/app/api/routes/health.py]]
