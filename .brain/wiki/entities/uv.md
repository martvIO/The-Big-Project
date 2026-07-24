---
tags: [backend, python, tooling]
sources: []
created: 2026-07-23
updated: 2026-07-23
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: entity
applicability: n/a
---

# uv

**Purpose.** The Python package and environment manager for the backend. Replaces pip/virtualenv/poetry.

Declared dependencies are in [[backend/pyproject.toml]]; the resolved lockfile is [[backend/uv.lock]] (generated — never hand-edit). `make bootstrap` runs `uv sync`. The pinned interpreter version is in [[backend/.python-version]].
