---
tags: [backend, booking, python, backfill, migration, batch-processing, idempotent]
sources: [backend/app/booking/backfill.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/booking/backfill.py
blob: 930510a20baa79ce4d2c927985ceaf7ee0b41c9c
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/booking/backfill.py

**Role.** The one-time, re-runnable deploy step that gives every already-live `confirmed` future booking a manage token and a banded reminder — the gap F16 inherited because F14 shipped bookings before the manage link existed.

**Module.** [[backend/app/booking/_index]] · **Layer.** cli

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `ManageLinkBackfill.run` | async method | Every active tenant, in turn; returns a `BackfillResult` |
| `BackfillResult` | frozen dataclass | `tenants`, `tokens_minted`, `reminders_scheduled` |
| `CHUNK_SIZE` · `MAX_CHUNKS` | const | 500 · 50 — one page per transaction, and a hard loop ceiling |

## Behavior

Enumerates active tenants from the RLS-free tenants table and runs each one inside its own `tenant_session`, so the backfill stays inside the same per-tenant RLS posture as the request path rather than taking an exemption. For each chunk it reads `confirmed`, future-dated bookings whose `manage_token_hash IS NULL`, mints a token, writes its hash, and — when `reminder_send_after` yields a time — inserts a `scheduled_messages` reminder row carrying the raw token.

**Idempotent by predicate rather than by a ledger.** The feed *is* `manage_token_hash IS NULL`, which the first pass fills, so a second run finds nothing and a partial failure is safe to re-run. That same property is why the paging carries **no offset**: each pass consumes its own rows by filling the column it selects on, so an offset would skip exactly the rows the previous pass shifted forward. The loop exits early when a chunk comes back short, and the `MAX_CHUNKS` ceiling means a runaway cannot loop forever — it logs a warning telling the operator to re-run instead, which is safe precisely because the predicate is self-consuming.

**No retroactive confirmation SMS.** A "your appointment is confirmed" text days after the fact reads as spam, and the reminder carries the same link anyway. A booking that falls inside the under-2 h suppression band still gets its **token** — the link is the half that matters — and simply gets no reminder, exactly as a fresh booking at that notice would not.

## Depends On

- [[backend/app/booking/comms.py]] — `reminder_send_after`, so the backfill uses the same three bands as a live claim
- [[backend/app/booking/tokens.py]] — `mint_manage_token`, `manage_token_hash`
- [[backend/app/db/tenant.py]] — `tenant_session`
- [[backend/app/db/repositories/tenants.py]] — `list_active`
- [[backend/app/db/repositories/bookings.py]] — `list_confirmed_without_manage_token`, `set_manage_token_hash`
- [[backend/app/db/repositories/scheduled_messages.py]] — the reminder insert
- [[backend/app/models/constants.py]] · [[backend/app/storefront/validation.py]]

## Depended On By

- [[backend/app/platform/service.py]] — the platform-operator action that runs it and records a `BOOKING_LINKS_BACKFILLED` platform audit entry with the three counts

## Concepts

- [[Row Level Security]]
- [[Tenant Context]]

## Tests

- [[backend/tests/test_booking_comms_db.py]] — `BackfillResult` and `ManageLinkBackfill` against real pre-F16 rows, including the re-run-finds-nothing property

## Notes

Chunk sizing follows the house batch-processing rule (a named page size plus a hard chunk ceiling). 500 × 50 is two orders of magnitude past the pilot's entire book, so `MAX_CHUNKS` is a runaway guard and not an expected path.

Design context: [[.planning/specs/booking-comms.md]].
