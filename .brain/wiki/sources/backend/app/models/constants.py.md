---
tags: [backend, models, constants, enums, python, booking, audit, sms, staff]
sources: [backend/app/models/constants.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/models/constants.py
blob: 940eaacebf4ef87caa7f1da45046c1218f5e2ed9
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/models/constants.py

**Role.** The single `StrEnum` registry for every status / role / kind string the backend writes to a TEXT column — and, for the eight sets that a DB `CHECK` also pins, the Python mirror of a constraint that only a migration can widen.

**Module.** [[backend/app/models/_index]] · **Layer.** models

## Public Surface

| Symbol | Kind | Members | DB `CHECK`? |
|---|---|---|---|
| `TenantStatus` | StrEnum | `active`, `suspended` | no — plain TEXT, default `'active'` ([[backend/migrations/versions/0002_tenants_app_role.py]]) |
| `StaffRole` | StrEnum | `owner`, `shift_manager` | **yes** — [[backend/migrations/versions/0011_staff_roles.py]] |
| `AppointmentAudience` | StrEnum | `all`, `brides_only` | no CHECK; column default `'all'` |
| `DressMediaStatus` | StrEnum | `pending`, `ready` | **yes** — [[backend/migrations/versions/0006_catalog.py]] |
| `MessageKind` | StrEnum | `otp`, `confirmation`, `reminder`, `owner_cancel`, `owner_reschedule` | **yes** — [[backend/migrations/versions/0007_sms_foundation.py]] |
| `MessageStatus` | StrEnum | `queued`, `sent`, `failed` | **yes** — 0007 |
| `BookingStatus` | StrEnum | `confirmed`, `cancelled`, `no_show`, `completed` | **yes** — [[backend/migrations/versions/0008_bookings.py]] |
| `BookingCancelledBy` | StrEnum | `customer`, `owner` | **yes** — [[backend/migrations/versions/0010_booking_comms.py]] |
| `ScheduledMessageKind` | StrEnum | `reminder` | **yes** — 0010 |
| `ScheduledMessageStatus` | StrEnum | `pending`, `sent`, `cancelled`, `failed` | **yes** — 0010 |
| `AuditAction` | StrEnum | 3 auth + 7 `BOOKING_*` + 5 `STAFF_*` | **no** — `audit_log.action` is plain TEXT |
| `PlatformAuditAction` | StrEnum | 4 provisioning/suspension + `booking_links_backfilled` | **no** — plain TEXT |

## Behavior

`StrEnum` means each member *is* its string, so a member can be handed straight to a `TEXT` column, compared to a value read back from the DB, and interpolated into a `server_default` (which [[backend/app/models/appointment_type.py]] and [[backend/app/models/dress_media.py]] both do) with no `.value` anywhere. The interesting distinction in this file is which sets are **pinned by a DB `CHECK`** and which are not, because that determines whether adding a member is a one-line edit or a migration:

- **Pinned sets need a migration to widen.** Adding a `BookingStatus` value without touching 0008 produces a `CheckViolationError` at the first insert, not a Python error — which is the point. Two of these pins are load-bearing beyond validation: `BookingStatus.CANCELLED` is the *only* value that frees a seat, because `idx_bookings_slot_seat_unique` and `idx_bookings_tenant_customer_starts_unique` both use the predicate `status <> 'cancelled'`, so a `no_show` or `completed` booking still occupies its instant; and `DressMediaStatus.READY` is the gallery read path's admission gate, so a third status would be a way to serve an object whose magic bytes were never verified.
- **Unpinned sets are extensible without a migration.** `audit_log.action` and `platform_audit_log.action` are plain TEXT with no `CHECK` ([[backend/migrations/versions/0003_auth.py]], [[backend/migrations/versions/0004_platform_audit.py]]), which is why the seven `BOOKING_*` values and the five `STAFF_*` values were added in feature branches with no DDL.

The file's second consistent argument is **one value per action, not one value carrying a discriminator in `details`**: `BOOKING_CANCELLED` / `BOOKING_NO_SHOW` / `BOOKING_COMPLETED` are separate rather than a single `booking_status_changed`, and `STAFF_ROLE_CHANGED` / `STAFF_PASSWORD_RESET` stay out of `STAFF_UPDATED`, because a filtered audit read then stays one `WHERE action = …` instead of a JSONB predicate — and "who was made an owner" and "whose password did someone else change" are precisely the two questions a security review asks of that table. The third is a stated refusal to pre-add speculative members: `ScheduledMessageKind` carries exactly one value and `StaffRole` exactly two, each waiting for its first real consumer rather than reserving names in advance.

`ScheduledMessageStatus.CANCELLED` deserves its own note: it covers both "the booking was cancelled" and "the claim-time re-check found the appointment already started". Neither is a delivery failure, so neither is `FAILED` — a distinction the worker's retry accounting depends on.

## Depends On

- Python `enum.StrEnum` only. No imports from this codebase, which is what lets [[backend/app/models/base.py]]-derived models and the migrations both reference it without a cycle.

## Depended On By

The most widely imported module in `backend/app/`. Notably:

- Auth / staff — [[backend/app/auth/service.py]], [[backend/app/auth/staff.py]], [[backend/app/auth/dependencies.py]], [[backend/app/auth/schemas.py]], [[backend/app/auth/staff_router.py]], [[backend/app/db/repositories/staff_users.py]]
- Booking — [[backend/app/booking/service.py]], [[backend/app/booking/manage.py]], [[backend/app/booking/owner.py]], [[backend/app/booking/owner_router.py]], [[backend/app/booking/comms.py]], [[backend/app/booking/backfill.py]], [[backend/app/db/repositories/bookings.py]], [[backend/app/db/repositories/scheduled_messages.py]]
- Catalog / boutique / storefront — [[backend/app/catalog/service.py]], [[backend/app/catalog/router.py]], [[backend/app/boutique/service.py]], [[backend/app/boutique/router.py]], [[backend/app/boutique/schemas.py]], [[backend/app/boutique/validation.py]]
- Notifications & platform — [[backend/app/notifications/service.py]], [[backend/app/platform/service.py]], [[backend/app/db/repositories/tenants.py]], [[backend/app/db/repositories/dress_media.py]]
- Models that use a member as a `server_default` — [[backend/app/models/appointment_type.py]], [[backend/app/models/dress_media.py]], [[backend/app/models/staff_user.py]], [[backend/app/models/tenant.py]]

## Concepts

- [[Database Migrations]] — widening a pinned set is a migration, not an edit

## Tests

- [[backend/tests/test_boutique_models.py]] — `test_appointment_audience_values` asserts the exact `AppointmentAudience` member set
- [[backend/tests/test_catalog_models.py]] — `test_dress_media_status_values`, same for `DressMediaStatus`
- [[backend/tests/test_migrations.py]] — `test_adding_the_role_check_validates_existing_rows`, the 0011 `StaffRole` pin against pre-existing rows
- [[backend/tests/test_booking_repositories.py]], [[backend/tests/test_booking_owner_db.py]], [[backend/tests/test_notifications_repositories.py]] — exercise the pinned sets against real Postgres

## Notes

The inline comments in this file are the authoritative record of *why* each set is or is not pinned, and several name the future epic that widens them (E4 adds `pending_payment` to `BookingStatus`; E4/E5 widen `ScheduledMessageKind`). Roadmap context: [[.planning/epics/e4-deposits-and-hardening.md]].
