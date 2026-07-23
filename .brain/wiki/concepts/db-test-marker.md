---
tags: [backend, testing]
sources: []
created: 2026-07-23
updated: 2026-07-23
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: n/a
---

# DB Test Marker

**Purpose.** The backend suite is split by [[pytest]] marker so the fast tests stay fast.

- `make test` runs `-m "not db"` — no database, no [[Docker]]
- `make test-db` runs `-m db` — needs a live [[PostgreSQL]] via [[Testcontainers]]
- `make test-all` runs everything

Anything exercising [[Row Level Security]] necessarily carries the `db` marker, because RLS cannot be tested without the real engine. Markers and fixtures are set up in [[backend/tests/conftest.py]].
