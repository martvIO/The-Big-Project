---
tags: [backend, models, db, python, sqlalchemy, soft-delete, core]
sources: [backend/app/models/base.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/models/base.py
blob: e6bb51c918ec74bfb86f30ea18fc6b0db4c71f7e
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/models/base.py

**Role.** The declarative root every mapped class inherits (`Base`) plus the four house-standard columns every table repeats (`StandardColumns`: server-generated UUID PK, `created_at`, trigger-maintained `updated_at`, soft-delete `deleted_at`).

**Module.** [[backend/app/models/_index]] · **Layer.** models

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `Base` | class | `DeclarativeBase` subclass; its `metadata` is the in-process table registry, populated as each model module is imported |
| `StandardColumns` | mixin | Plain (non-mapped) mixin contributing `id`, `created_at`, `updated_at`, `deleted_at` to any class that also inherits `Base` |

## Behavior

`id` and `created_at` carry `server_default` (`uuid_generate_v4()`, `now()`) rather than Python defaults, so a row written by a migration, a psql session or any non-ORM path gets the same values as one written through SQLAlchemy — the DDL in each migration repeats the identical defaults, which is why the `_STANDARD` block is duplicated verbatim across [[backend/migrations/versions/0003_auth.py]], [[backend/migrations/versions/0005_boutique_settings.py]], [[backend/migrations/versions/0006_catalog.py]] and [[backend/migrations/versions/0008_bookings.py]]. `updated_at` is nullable and **never assigned in application code**: each migration installs a `trg_<table>_updated_at BEFORE UPDATE` trigger calling the shared `update_updated_at()` function, so the column is authoritative even for a raw `UPDATE`, and a fresh row legitimately has it `NULL`. `deleted_at` is the only deletion mechanism — no row is ever hard-deleted — and every repository query therefore repeats `deleted_at IS NULL`; the partial unique indexes that carry the real invariants use the same predicate, which is what makes soft delete behave as *archive* (an archived appointment type frees its name; a cancelled booking frees its seat).

The mixin declares no `tenant_id`. Each tenant-scoped model declares its own, and that is deliberate: [[backend/app/models/platform_audit_log.py]] inherits `Base` **without** `StandardColumns` because it is platform-wide, and the isolation suite's metadata scan treats "has a `tenant_id` column" as the trigger for requiring forced RLS. `Base.metadata` is never a DDL source — `backend/migrations/env.py` sets `target_metadata = None`, so Alembic autogenerate is off and the migrations are hand-written raw SQL. Its only consumers are SQLAlchemy's own query construction and the two shape-assertion test modules.

## Depends On

- [[SQLAlchemy]] — `DeclarativeBase`, `Mapped`, `mapped_column`, the PostgreSQL `UUID` type
- [[PostgreSQL]] — `uuid_generate_v4()` (the `uuid-ossp` extension installed by [[backend/migrations/versions/0001_baseline_uuid_ossp.py]]) and the `update_updated_at()` trigger function defined once in [[backend/migrations/versions/0002_tenants_app_role.py]]

## Depended On By

Every model module: [[backend/app/models/appointment_type.py]], [[backend/app/models/audit_log.py]], [[backend/app/models/availability.py]], [[backend/app/models/booking.py]], [[backend/app/models/customer.py]], [[backend/app/models/dress.py]], [[backend/app/models/dress_media.py]], [[backend/app/models/dress_variant.py]], [[backend/app/models/message_log.py]], [[backend/app/models/otp_code.py]], [[backend/app/models/scheduled_message.py]], [[backend/app/models/session.py]], [[backend/app/models/staff_user.py]], [[backend/app/models/tenant.py]], [[backend/app/models/terms_version.py]] — all via `StandardColumns, Base`; [[backend/app/models/platform_audit_log.py]] via `Base` alone.

## Concepts

- [[Row Level Security]]
- [[Tenant Isolation]]

## Tests

- [[backend/tests/test_boutique_models.py]] — `test_all_new_tables_carry_standard_columns` asserts the four names plus `tenant_id` are present on every F7 table
- [[backend/tests/test_catalog_models.py]] — `test_all_catalog_tables_carry_standard_columns`, same assertion for the catalog tables

## Notes

`updated_at` exists on immutable tables too ([[backend/app/models/terms_version.py]]) purely for uniformity; those tables install no trigger, so it stays `NULL` forever. Column conventions are stated in [[.planning/architecture.md]].
