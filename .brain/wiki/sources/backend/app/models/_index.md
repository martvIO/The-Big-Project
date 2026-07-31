---
tags: [backend, python]
sources: [backend/app/models]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/models
blob: ad9970225365cbc95c752d5561c93fa01bdfbfa7
commit: 13d107b8b16f1f2676f1cdb1c994f95822fe2ba0
kind: directory
applicability: active
---

# backend/app/models/

**Purpose.** The SQLAlchemy declarative models — one per table, each mirroring a raw-SQL migration, plus the shared base and the `StrEnum` registry whose values several DB `CHECK` constraints pin.

**Parent.** [[backend/app/_index]]

## Files

- [[backend/app/models/__init__.py]] — Empty file that makes `app.models` a package, so every table class is imported by its own module path (`from app.models.booking import Booking`) rather than from the package.
- [[backend/app/models/appointment_type.py]] — The `appointment_types` table: the per-tenant menu of bookable services (name, duration, audience, optional deposit, display order) that the storefront lists and every booking snapshots.
- [[backend/app/models/audit_log.py]] — The `audit_log` table: the per-tenant record of who did what inside one boutique — logins, staff-management changes and every owner action on a booking — with a JSONB `details` bag for the action-specific payload.
- [[backend/app/models/availability.py]] — The two tables the slot engine reads: `availability_rules` (the recurring weekly opening grid, with a per-window parallel-appointment `capacity`) and `availability_exceptions` (a per-date override that beats the grid in both directions).
- [[backend/app/models/base.py]] — The declarative root every mapped class inherits (`Base`) plus the four house-standard columns every table repeats (`StandardColumns`: server-generated UUID PK, `created_at`, trigger-maintained `updated_at`, soft-delete `deleted_at`).
- [[backend/app/models/booking.py]] — The `bookings` table: one appointment at one start time, holding a numbered seat in that instant, carrying frozen snapshots of what the customer agreed to, the terms version she accepted, the hash of her tokenized manage link, and the…
- [[backend/app/models/constants.py]] — The single `StrEnum` registry for every status / role / kind string the backend writes to a TEXT column — and, for the eight sets that a DB `CHECK` also pins, the Python mirror of a constraint that only a migration can widen.
- [[backend/app/models/customer.py]] — The `customers` table: a phone-keyed person record inside one boutique, created only once OTP verification has proved possession of that number.
- [[backend/app/models/dress.py]] — The `dresses` table: one catalog item per row — name, optional price in agorot with its own visibility flag, a manual `reserved` marker and a display order — with soft delete doubling as the archive the owner can read back.
- [[backend/app/models/dress_media.py]] — The `dress_media` table: one uploaded photo per row, written `pending` at presign time with its storage key already computed, and flipped to `ready` only after the confirm step has verified the object's magic bytes.
- [[backend/app/models/dress_variant.py]] — One size bucket of one dress — the only place stock quantity is recorded, and therefore the sole input to the storefront's "out of stock" treatment.
- [[backend/app/models/message_log.py]] — One row per SMS **send attempt** — the Israeli Spam-Law evidence trail: who was texted, with what body, when, and whether the provider accepted it.
- [[backend/app/models/otp_code.py]] — The phone-verification row: one live SMS code per (tenant, phone) with its expiry and attempt counter, plus — on the *same* row — the short-lived verification token that a successful verify mints and the booking transaction later spends.
- [[backend/app/models/platform_audit_log.py]] — The operator trail for platform-wide acts — provisioning, suspension, owner password reset, the F16 link backfill — written by the app but **not readable** by it: the only INSERT-only table in the schema, and the only model that opts out…
- [[backend/app/models/scheduled_message.py]] — One future SMS waiting to be sent — the queue the background worker claims from when `send_after` passes, and the only place the raw manage-link token survives between the confirmation text and the reminder.
- [[backend/app/models/session.py]] — The server-side half of a staff login cookie — one row per live session, storing only the **hash** of the session token plus its owner and hard expiry, so a database read cannot reconstruct a usable cookie.
- [[backend/app/models/staff_user.py]] — The boutique-side login identity — one row per staffer with an argon2 password hash, a display name and a role — and the table whose `role` column every `require_role` gate in the API reads.
- [[backend/app/models/tenant.py]] — The tenant registry itself — slug, display name, lifecycle status and a JSONB settings blob — and the one tenant-facing table in the schema that deliberately carries **no** `tenant_id` column and **no** row-level security, because it is…
- [[backend/app/models/terms_version.py]] — One immutable snapshot of a boutique's cancellation policy — the text plus the two numbers the refund math needs — versioned per tenant so the terms a customer accepted at booking time stay reconstructable after the boutique republishes.
