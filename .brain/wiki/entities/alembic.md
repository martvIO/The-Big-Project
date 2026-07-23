---
tags: [backend, python, db, migrations]
sources: []
created: 2026-07-23
updated: 2026-07-23
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: entity
applicability: n/a
---

# Alembic

**Purpose.** Schema migration tool for [[SQLAlchemy]]. Every schema change is a versioned revision.

Configuration is [[backend/alembic.ini]]; the environment script is [[backend/migrations/env.py]] and the revision template is [[backend/migrations/script.py.mako]]. Revisions live in `backend/migrations/versions/` and form a linear chain — see [[Database Migrations]].

Migrations are exercised in CI by [[backend/tests/test_migrations.py]].
