---
tags: [backend, python, db, orm]
sources: []
created: 2026-07-23
updated: 2026-07-23
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: entity
applicability: n/a
---

# SQLAlchemy

**Purpose.** The ORM and Core layer for all database access. Version 2.x, async style.

Declarative models live in `backend/app/models/`, with the shared base in [[backend/app/models/base.py]]. Session construction and the tenant-binding wrapper are in [[backend/app/db/session.py]] and [[backend/app/db/tenant.py]].

Note: this is **not** Exposed ORM. The `.claude/rules/database/` files describe Kotlin/Exposed patterns that do not apply here — see [[Documented Stack Vs Actual Stack]].
