---
tags: [backend, db, repository, notifications, sms, message-log, python, sqlalchemy]
sources: [backend/app/db/repositories/message_log.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/db/repositories/message_log.py
blob: d7ecb25d3f3915c8a3b99b756f1e7dc0be3d7c24
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/db/repositories/message_log.py

**Role.** The per-tenant record of every SMS the platform attempted: insert a row before the provider call, stamp its outcome (`status`, `provider_message_id`, `error`) after, and read a phone's history in send order.

**Module.** [[backend/app/db/repositories/_index]] · **Layer.** db

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `MessageLogRepository` | class | The repository; explicit `AsyncSession` + `tenant_id` on every method |
| `insert` | method | New `MessageLog` for `(phone, kind, body)`, optionally tied to a `booking_id` |
| `update_status` | method | Sets `status`, `provider_message_id` and `error` on one row; `None` when the row is missing |
| `list_by_phone` | method | Every live log line for a phone, oldest first |
| `_by_id` | method | Private live-row lookup used by `update_status` |

## Behavior

The log is written in two beats around the provider call — a row exists before the SMS is attempted, so a crash mid-send leaves evidence rather than silence — and `update_status` then overwrites the outcome triple. Note that `update_status` assigns `provider_message_id` and `error` **unconditionally** from its arguments, so calling it without them clears whatever was there; it is a full outcome overwrite, not a patch. There is no `booking_id` filter and no paging: `list_by_phone` is a per-phone history read ordered by `created_at`, which is the order a customer experienced the messages in. Both the reads and `_by_id` filter `deleted_at IS NULL`, and the explicit `tenant_id` predicate rides alongside the table's FORCE RLS as redundant defence-in-depth. Nothing here touches `updated_at` — the DB trigger owns it, and `refresh` after `flush` is what pulls the trigger's value back into the returned entity.

## Depends On

- [[backend/app/models/message_log.py]] — the `MessageLog` ORM entity
- [[SQLAlchemy]] — `select`, `AsyncSession`

## Depended On By

- [[backend/app/notifications/service.py]] — the only production caller: logs OTP and booking SMS around each send

## Concepts

- [[Row Level Security]]
- [[Tenant Isolation]]

## Tests

- [[backend/tests/test_notifications_repositories.py]]
- [[backend/tests/test_notifications_isolation.py]]
- [[backend/tests/test_notifications_service.py]]
- [[backend/tests/test_booking_comms_db.py]]

## Notes

`kind` and `status` are passed as plain strings here; their allowed values live in [[backend/app/models/constants.py]], and this layer does not validate them. `body` is stored verbatim, so anything sensitive that reaches an SMS template lands in this table too.
