---
tags: [backend, models, python, notifications, sms, compliance, sqlalchemy]
sources: [backend/app/models/message_log.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/models/message_log.py
blob: 509e76500234a1e491bc88a37f1019f1018052bf
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/models/message_log.py

**Role.** One row per SMS **send attempt** — the Israeli Spam-Law evidence trail: who was texted, with what body, when, and whether the provider accepted it.

**Module.** [[backend/app/models/_index]] · **Layer.** models

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `MessageLog` | class | ORM mapping for `message_log` — a singular table name, like `audit_log` and `platform_audit_log` and unlike every other table here |
| `tenant_id` | col | `UUID NOT NULL` — RLS discriminator |
| `phone` | col | `TEXT NOT NULL` — the recipient number |
| `kind` | col | `TEXT NOT NULL`, DB `CHECK` pinned to `otp`/`confirmation`/`reminder`/`owner_cancel`/`owner_reschedule` (mirrors `MessageKind`) |
| `body` | col | `TEXT NOT NULL` — the message as sent, **except OTP bodies, which are stored masked** |
| `status` | col | `TEXT NOT NULL DEFAULT 'queued'`, `CHECK` in `queued`/`sent`/`failed` (mirrors `MessageStatus`) |
| `provider_message_id` | col | `TEXT NULL` — the gateway's handle, for reconciliation |
| `error` | col | `TEXT NULL` — provider failure detail for operators; never reaches a response body |
| `booking_id` | col | `UUID NULL` — no FK; populated for lifecycle sends |

## Behavior

Two rules about *who* may write this table are stated in the docstring and enforced by convention, not by the schema: [[backend/app/notifications/service.py]] is the single writer, and adapters ([[backend/app/notifications/fake.py]], [[backend/app/notifications/unconfigured.py]]) and feature code never touch it. The lifecycle is a row inserted `queued` before the adapter is called and then `UPDATE`d to `sent` or `failed` — which is exactly why [[backend/migrations/versions/0007_sms_foundation.py]] grants full CRUD here, unlike the append-only [[backend/app/models/terms_version.py]] one migration earlier: this is operational telemetry with a compliance duty, not immutable evidence, and the status transition is an update by construction.

The insert and the status update happen in **two separate tenant sessions**, deliberately: a hung provider must not hold a database transaction open, and a failed send must leave its evidence row behind rather than roll it away with the transaction.

The one storage rule with a security consequence: `body` for `kind = 'otp'` is written **masked**. [[backend/app/notifications/validation.py]]'s `mask_otp_body` replaces the code with a run of `●`, so a database read — or a leaked backup — cannot be replayed as a valid verification. The compliance duty is satisfied by proving *that* a message was sent to *that* number, which the masked body still does. `error` gets the same treatment on the failure path: the service truncates the provider's text and replaces any echo of the wire body with the masked one, so an SDK that quotes the failing request cannot persist the unmasked code beside the masked one.

Unlike [[backend/app/models/staff_user.py]] and [[backend/app/models/tenant.py]], this model imports nothing from [[backend/app/models/constants.py]] — the `'queued'` default is a raw `text()` literal and the `kind`/`status` vocabularies live only in the DB `CHECK` and in `MessageKind`/`MessageStatus`. That means three copies of each set (enum, DDL, ORM default) that a widening has to update by hand; the enum's own comments record which migration pins each. The read index is partial (`(tenant_id, created_at) WHERE deleted_at IS NULL`) — soft-deleted rows are kept out of the operator's scan, and the table is under FORCE RLS with the repository carrying a redundant explicit `tenant_id` predicate.

## Depends On

- [[backend/app/models/base.py]] — `Base`, `StandardColumns`
- [[SQLAlchemy]] — declarative mapping

## Depended On By

- [[backend/app/db/repositories/message_log.py]] — `insert`, `update_status`, `list_by_phone`
- [[backend/app/notifications/service.py]] — the sole writer, and the only place status transitions are made

## Concepts

- [[Row Level Security]]
- [[Tenant Isolation]]

## Tests

- [[backend/tests/test_notifications_repositories.py]] — insert / status transition / lookup against a migrated database
- [[backend/tests/test_notifications_service.py]] — masking, queue-then-mark ordering, failure recording
- [[backend/tests/test_notifications_isolation.py]] — cross-tenant reads return nothing
- [[backend/tests/test_booking_comms_templates.py]], [[backend/tests/test_booking_comms_db.py]] — the lifecycle kinds

## Notes

`booking_id` has no foreign key (house convention) and is `NULL` for OTP sends, which precede any booking. Do not confuse this table with [[backend/app/models/scheduled_message.py]]: this one is the **evidence** of what was sent, that one is the **schedule** of what is still to be sent, and they are written by different components.

Design context: [[.planning/specs/sms-foundation.md]], [[.planning/specs/ppl-compliance.md]], [[.planning/specs/booking-comms.md]].
