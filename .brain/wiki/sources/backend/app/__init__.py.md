---
tags: [backend, python, package]
sources: [backend/app/__init__.py]
created: 2026-07-23
updated: 2026-07-23
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/__init__.py
blob: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
commit: d9d860b47f2c78acb9ce7304f18c1e18cc370851
kind: code
applicability: active
---

# backend/app/__init__.py

**Role.** Empty file whose only job is to make `app` an importable package, so every module is addressed as `app.<subpackage>.<module>` (`app.main:app` for [[Uvicorn]], `python -m app.cli`, `python -m app.worker`).

**Module.** [[backend/app/_index]] · **Layer.** platform

## Behavior

Zero bytes. It deliberately re-exports nothing: package-level imports here would run at `import app.main` time and could pull the database engine or settings into scope before a test has configured the environment — the invariant that [[backend/tests/test_app_import.py]] guards.

## Depended On By

- [[backend/app/main.py]]
- [[backend/app/cli.py]]
- [[backend/app/worker.py]]

## Tests

- [[backend/tests/test_app_import.py]] — asserts `import app.main` succeeds with no `DATABASE_URL` and no reachable database
