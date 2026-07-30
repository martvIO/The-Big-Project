---
tags: [backend, worker, python, entrypoint, sms, booking]
sources: [backend/app/worker.py]
created: 2026-07-23
updated: 2026-07-30
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/worker.py
blob: 3ae3960ab432552e95cc078b7c9fb6c88211924b
commit: 99a8cef22bcd1b6c55105cb6e740d5a560f0596e
kind: code
applicability: active
---

# backend/app/worker.py

**Role.** The background-process entrypoint (`uv run python -m app.worker`, wired into the root `Makefile` and deployed as its own Railway service). **F16 turned it from a placeholder into a real job runner:** it drains due rows from `scheduled_messages`, tenant by tenant, on a settings-driven tick. The hold sweeper (F19) and the waitlist offer cascade (F23) are the next jobs slated to register here.

**Module.** [[backend/app/_index]] · **Layer.** worker

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `main` | async fn | Fail-fast role check, builds the comms service, then loops `poll_once` forever |
| `poll_once` | async fn | One tick across every active tenant; returns an aggregate `DrainResult` |
| `build_sender` | fn | Picks `FakeSmsSender` or `UnconfiguredSmsSender` from `Settings.sms_provider`, logging which |
| `logger` | const | `logging.getLogger("worker")` |

`POLL_INTERVAL_SECONDS` is **gone** — the tick is now `Settings.worker_poll_interval_seconds`, deploy-tunable without a code change.

## Behavior

`main` opens with the same `ensure_safe_database_role` fail-fast the web app and CLI perform, so a worker pointed at a superuser URL dies at boot rather than quietly bypassing RLS. It then builds a `BookingCommsService` over [[backend/app/db/session.py#get_session_factory]] and a `NotificationService`, and loops: `poll_once`, then `asyncio.sleep(settings.worker_poll_interval_seconds)`.

**Why a poller and not a cron firing at exactly 24 hours.** `.planning/architecture.md` pins the shape: a `scheduled_messages` table drained with `FOR UPDATE SKIP LOCKED`, never an exact-time trigger. Because the claim predicate is `send_after <= now()`, a window missed during a deploy self-heals on the next tick, and a reminder that fires late still states the true appointment time — the body renders from `starts_at`, not from when it was sent.

**Why tenants are enumerated rather than queried across.** `scheduled_messages` carries the standard FORCE RLS policy, so every read of it needs a bound tenant context. The `tenants` table is deliberately RLS-free, which makes enumerate-then-claim the only tenancy-preserving shape available (spec decision D6). Cross-tenant leakage is the recorded existential risk for this product, and the codebase's first background reader was not granted the first RLS exception.

`poll_once` wraps each tenant's `drain_due` in its own `try`/`except`, logging with `logger.exception` and `continue`ing. That containment is the point: one malformed row would otherwise silence every boutique's reminders until somebody noticed. A tenant whose drain raised is retried on the next tick, because the rolled-back claim leaves its rows `pending`. Totals are logged only when something actually happened, so an idle deployment stays quiet. It issues one query per active tenant per tick — noise at pilot volume, and flagged in-file as an F29 scale-pass concern.

`build_sender` mirrors `main`'s `_build_sms_sender`, including its observability line. **No provider is a supported state here** rather than an error: due rows are simply left `pending` until an adapter lands, so the backlog flushes itself on the first tick afterwards. `Settings.model_config` is `extra="ignore"`, so a typo'd `SMS_PROVDER` would otherwise degrade in total silence — hence logging the chosen sender either way.

Sends from this process are **unmetered**. The API's rate limiters are per-process and unreachable from here, and the volume is bounded by how many bookings sit inside the reminder horizon rather than by anything a caller controls.

## Depends On

- [[backend/app/booking/comms.py]] — `BookingCommsService`, `CommsTenant`, `DrainResult`
- [[backend/app/core/config.py]] — `worker_poll_interval_seconds`, `sms_provider`, `base_domain`
- [[backend/app/db/repositories/tenants.py]] — `list_active`, the enumeration feed
- [[backend/app/db/session.py]] — `get_session_factory`, `ensure_safe_database_role`
- [[backend/app/notifications/service.py]] — `NotificationService`
- [[backend/app/notifications/fake.py]] · [[backend/app/notifications/unconfigured.py]]

## Depended On By

Nothing imports this module — it is a process entrypoint.

## Concepts

- [[Row Level Security]]
- [[Tenant Context]]
- [[Fail Closed Defaults]]

## Tests

- [[backend/tests/test_worker.py]] — `build_sender` selection, `poll_once` aggregation, and per-tenant failure containment

## Notes

The 2026-07-23 version of this page described a job-less placeholder that slept forever and imported nothing from `app`, and predicted that the first real poller "should add the database role check and a graceful-shutdown path before this file gets a test." Half of that came true: F16 added the role check and the tests. **There is still no graceful-shutdown path** — `main` loops unconditionally and relies on the platform's SIGTERM, so a tick interrupted mid-send leaves its row `pending` and re-sends on restart. That is the deliberate at-least-once posture recorded in [[backend/app/db/repositories/scheduled_messages.py]], whose docstring names claim-commit-then-send with a `sending` status as the upgrade path if duplicate sends ever start to matter.
