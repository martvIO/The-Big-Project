---
tags: [backend, python, testing, infra]
sources: []
created: 2026-07-23
updated: 2026-07-23
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: entity
applicability: n/a
---

# Testcontainers

**Purpose.** Spins up a real [[PostgreSQL]] instance in [[Docker]] for the `-m db` test suite, so row-level security is tested against the real engine rather than a mock.

Wired up in [[backend/tests/conftest.py]]. There is a known event-loop gotcha with async fixtures documented in [[.memory/patterns/async-testcontainers-fixtures.md]] — sync fixtures with `asyncio.run()` for setup, async work only inside test bodies.
