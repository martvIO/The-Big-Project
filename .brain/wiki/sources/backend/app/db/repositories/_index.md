---
tags: [backend, python]
sources: [backend/app/db/repositories]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/db/repositories
blob: ac01eca6ec4422dd31b0bfb0d48f7210d9253606
commit: 13d107b8b16f1f2676f1cdb1c994f95822fe2ba0
kind: directory
applicability: active
---

# backend/app/db/repositories/

**Purpose.** Every SQL statement in the product. One class per table, each tenant-scoped by RLS with an explicit `tenant_id` predicate as redundant defence-in-depth.

**Parent.** [[backend/app/db/_index]]

## Files

- [[backend/app/db/repositories/__init__.py]] — Empty package marker for `app.db.repositories`.
- [[backend/app/db/repositories/appointment_types.py]] — CRUD over `appointment_types` — the boutique's bookable service menu (name, duration, audience, deposit, display order) — read by both the owner console and the public storefront, and soft-deleted rather than removed so historical bookings…
- [[backend/app/db/repositories/audit_log.py]] — Append-only writer for the per-tenant `audit_log` table — one `record()` that stamps an action, an optional actor and entity, and a JSON details blob into the caller's open transaction — plus a read helper used only by tests.
- [[backend/app/db/repositories/availability.py]] — The two repositories the slot engine reads from: `AvailabilityRulesRepository` over the boutique's recurring weekly opening hours and seat capacity, and `AvailabilityExceptionsRepository` over the dated overrides (holiday closures and…
- [[backend/app/db/repositories/bookings.py]] — The single writer for the `bookings` table — slot/seat claim, status graph, cancel, reschedule, manage-token mint-and-rotate, and the owner/storefront read paths — written so that overselling a slot is refused by two partial unique indexes…
- [[backend/app/db/repositories/customers.py]] — Reads and writes `customers`, whose identity within a tenant is the **phone number** — an attach-or-insert `upsert` keyed on `(tenant, phone)` for the booking flow, a bulk `by_ids` for the owner day list, and a separate `set_phone` writer…
- [[backend/app/db/repositories/dress_media.py]] — The `dress_media` table's whole lifecycle — mint a `pending` row that owns its storage key, promote it to `ready` on confirm, sweep pendings that were abandoned mid-upload, and serve the gallery and the list page's cover photo — with every…
- [[backend/app/db/repositories/dress_variants.py]] — The size matrix of a dress — one row per `(dress, size_label)` with a quantity — read per dress for the detail page, pre-aggregated per dress for the list page, and replaced wholesale rather than patched.
- [[backend/app/db/repositories/dresses.py]] — Every read and write of the `dresses` table: the id lookup all `/manage/dresses/...` routes resolve first, the active/archived paged list with an ILIKE name search, insert, whole-record field update, and the soft-delete / restore pair that…
- [[backend/app/db/repositories/message_log.py]] — The per-tenant record of every SMS the platform attempted: insert a row before the provider call, stamp its outcome (`status`, `provider_message_id`, `error`) after, and read a phone's history in send order.
- [[backend/app/db/repositories/otp_codes.py]] — The whole phone-verification lifecycle in SQL: store a hashed OTP, find the one live code for a phone, retire superseded codes, count guesses atomically, and mint then single-use-consume the verification token a booking must present.
- [[backend/app/db/repositories/scheduled_messages.py]] — The reminder queue's data layer: enqueue a pending message whose uniqueness the DB enforces, cancel a booking's pending messages, claim due rows with `FOR UPDATE SKIP LOCKED` for the poller, and mark a claimed row terminal — clearing the…
- [[backend/app/db/repositories/sessions.py]] — Staff session rows: mint one for a login, resolve a live one from a cookie's token hash, revoke every session a staffer holds (optionally sparing the caller's own), and revoke a single session on logout.
- [[backend/app/db/repositories/staff_users.py]] — The `staff_users` table: the by-email read login runs, the by-id read session resolution runs on every request, the console's ordered roster, the live-owner count the last-owner invariant rests on, plus insert, partial update, and soft…
- [[backend/app/db/repositories/tenants.py]] — The one **platform-scoped** repository: creates tenants, resolves a slug to an active tenant on every request, suspends and soft-deletes, atomically merges JSONB settings patches, and enumerates active tenants for the background poller.
- [[backend/app/db/repositories/terms.py]] — The append-only `terms_versions` table: read the highest version number, append the next one, read the current version for display, read **one exact past version** for a booking that pinned it, and page the history.
