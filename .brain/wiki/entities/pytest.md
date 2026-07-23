---
tags: [backend, python, testing]
sources: []
created: 2026-07-23
updated: 2026-07-23
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: entity
applicability: n/a
---

# pytest

**Purpose.** The test runner for the backend suite in `backend/tests/`.

The suite is split by marker: `-m "not db"` for fast unit tests (`make test`) and `-m db` for tests needing a live database (`make test-db`). See [[DB Test Marker]]. Shared fixtures are in [[backend/tests/conftest.py]].
