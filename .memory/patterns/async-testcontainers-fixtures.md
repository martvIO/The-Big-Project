# Pattern: Sync fixtures + asyncio.run() for Testcontainers/Alembic setup

For pytest-asyncio suites backed by a session-scoped Postgres container: keep ALL
setup fixtures (`postgres_url`, `migrated_db`, role provisioning, probe tables)
plain synchronous Python, using `asyncio.run()` for one-off async setup calls.
Do async work only inside `async def test_*` bodies, each creating and disposing
its own engine.

**Why:** session-scoped *async* fixtures bind engines/connections to one event
loop while pytest-asyncio (auto mode) gives each test its own loop — the classic
"Future attached to a different loop" failure. Sync fixtures that return plain
URLs sidestep it entirely.

**Origin (2026-07-21, Feature 3):** `backend/tests/conftest.py` — noted by the
Gate 3.5 reviewer as the correct answer to a problem Features 4–9 will hit again.
