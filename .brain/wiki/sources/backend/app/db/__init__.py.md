---
tags: [backend, db, python, package]
sources: [backend/app/db/__init__.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/db/__init__.py
blob: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# backend/app/db/__init__.py

**Role.** Empty file marking `app.db` as a package — the engine and session factory ([[backend/app/db/session.py]]), the tenant-bound context managers ([[backend/app/db/tenant.py]]), the RLS DDL vocabulary ([[backend/app/db/rls.py]]), and `repositories/`.

**Module.** [[backend/app/db/_index]] · **Layer.** db

## Behavior

Zero bytes, no re-exports. That matters more here than in most packages: `session.py` builds the async engine at import time of its module-level accessors, so a package-level re-export would make `import app.db.<anything>` reach for `DATABASE_URL`. Every caller imports the exact module it needs (`from app.db.tenant import tenant_session`).

## Depended On By

- [[backend/app/db/session.py]]
- [[backend/app/db/tenant.py]]
- [[backend/app/db/rls.py]]

## Concepts

- [[Row Level Security]]
