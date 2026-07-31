---
tags: [backend, db, python, repositories, package-marker]
sources: [backend/app/db/repositories/__init__.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/db/repositories/__init__.py
blob: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/db/repositories/__init__.py

**Role.** Empty package marker for `app.db.repositories`. It re-exports nothing on purpose — every caller imports the concrete class from its own module (`from app.db.repositories.bookings import BookingsRepository`), so adding a repository never touches this file and no import of one repository drags in the ORM models of all the others.

**Module.** [[backend/app/db/repositories/_index]] · **Layer.** db

## Public Surface

Nothing. Zero bytes.

## Behavior

Its emptiness is the contract: a re-export barrel here would make `import app.db.repositories.audit_log` transitively import every model in [[backend/app/models/__init__.py]], which matters because Alembic autogenerate and the RLS metadata scan both depend on which models are registered on the declarative base at a given moment.

## Depends On

Nothing.

## Depended On By

- Every module under `backend/app/db/repositories/` — as its package.

## Concepts

- [[Repository Pattern]]

## Tests

None directly; covered incidentally by [[backend/tests/test_app_import.py]].
