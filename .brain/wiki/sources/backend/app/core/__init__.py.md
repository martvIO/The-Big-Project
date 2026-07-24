---
tags: [backend, python, package, config]
sources: [backend/app/core/__init__.py]
created: 2026-07-23
updated: 2026-07-23
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/core/__init__.py
blob: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
commit: d9d860b47f2c78acb9ce7304f18c1e18cc370851
kind: code
applicability: active
---

# backend/app/core/__init__.py

**Role.** Empty file marking `app.core` as a package; the subpackage currently holds exactly one module, [[backend/app/core/config.py]].

**Module.** [[backend/app/core/_index]] · **Layer.** platform

## Behavior

Zero bytes, no re-exports. Callers import the concrete symbol path (`from app.core.config import get_settings`) rather than a package-level alias.

## Depended On By

- [[backend/app/core/config.py]]
