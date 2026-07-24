---
tags: [backend, config, design]
sources: []
created: 2026-07-23
updated: 2026-07-23
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: n/a
---

# Fail Fast Configuration

**Purpose.** Invalid or missing configuration aborts startup rather than surfacing as a confusing runtime error later.

Implemented with [[Pydantic Settings]] in [[backend/app/core/config.py]]: every setting is typed and validated when the settings object is constructed. Documented variables are listed in [[backend/.env.example]].

Covered by [[backend/tests/test_config.py]].
