---
tags: [backend, models, python, package]
sources: [backend/app/models/__init__.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/models/__init__.py
blob: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/models/__init__.py

**Role.** Empty file that makes `app.models` a package, so every table class is imported by its own module path (`from app.models.booking import Booking`) rather than from the package.

**Module.** [[backend/app/models/_index]] · **Layer.** models

## Behavior

Zero bytes, and re-exporting here would be actively wrong rather than merely unnecessary. Every mapped class registers itself on `Base.metadata` at *import* time (see [[backend/app/models/base.py]]), so a package-level `from .booking import Booking` block would make the population of that registry depend on whether anything had touched `app.models` yet — which is exactly the ordering hazard the shape tests in [[backend/tests/test_boutique_models.py]] and [[backend/tests/test_catalog_models.py]] rely on *not* existing: each imports precisely the models whose tables it then looks up. Alembic does not need a metadata aggregate either, because `backend/migrations/env.py` sets `target_metadata = None` and every migration is hand-written raw SQL.

## Depended On By

Nothing imports the package itself; ~60 call sites import its submodules directly (see the Depended On By list on each model page).

## Notes

If a future need for `Base.metadata` to be fully populated ever appears (a metadata-wide RLS scan run from application code, say), the import list belongs in that consumer or in a test fixture — not here, where it would run on every `import app.models.anything`.
