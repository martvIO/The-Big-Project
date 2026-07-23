---
tags: [backend, worker, python, entrypoint]
sources: [backend/app/worker.py]
created: 2026-07-23
updated: 2026-07-23
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/worker.py
blob: a4fee87c307bd67ddade8d4d8939afdd2cdd7bdb
commit: d9d860b47f2c78acb9ce7304f18c1e18cc370851
kind: code
applicability: active
---

# backend/app/worker.py

**Role.** Placeholder background-process entrypoint (`python -m app.worker`, wired into the root `Makefile`) that exists only to prove the second process model deploys and stays alive; the scheduled-message, hold-sweeper, and offer-cascade pollers register here in later features.

**Module.** [[backend/app/_index]] · **Layer.** worker

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `main` | async fn | Logs a startup line, then sleeps forever in `POLL_INTERVAL_SECONDS` increments |
| `POLL_INTERVAL_SECONDS` | const | 60 — the idle tick of the placeholder loop |
| `logger` | const | `logging.getLogger("worker")` |

## Behavior

Under `__main__` it calls `logging.basicConfig(level=logging.INFO)` and hands `main()` to `asyncio.run`. `main` emits one INFO line and then loops on `asyncio.sleep`, carrying a `# noqa: ASYNC110` because a bare sleep loop is exactly what the lint rule flags and exactly what a job-less placeholder needs. It opens no database connection and imports nothing from the rest of `app`, so it cannot fail on a misconfigured `DATABASE_URL` — a property that will change the moment a real poller lands and needs [[backend/app/db/session.py#get_session_factory]] plus the same `ensure_safe_database_role` fail-fast the web and CLI entrypoints already perform.

## Notes

No tests exercise this module; there is nothing to assert beyond "it sleeps". The first real poller should add the database role check and a graceful-shutdown path before this file gets a test.
