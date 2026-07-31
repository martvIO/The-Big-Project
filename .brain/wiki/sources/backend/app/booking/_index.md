---
tags: [backend, python]
sources: [backend/app/booking]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/booking
blob: 6a1ac8fc512980a4a66132978602e6d3b102052a
commit: 13d107b8b16f1f2676f1cdb1c994f95822fe2ba0
kind: directory
applicability: active
---

# backend/app/booking/

**Purpose.** The booking engine and the most intricate code in the repo: the concurrency-safe seat claim, the availability question, the SMS lifecycle, the customer's tokenized manage page, and the owner console's booking surface.

**Parent.** [[backend/app/_index]]

## Files

- [[backend/app/booking/__init__.py]] — Empty file marking `app.booking` as a package — the E3 booking engine, the most intricate module in the backend.
- [[backend/app/booking/backfill.py]] — The one-time, re-runnable deploy step that gives every already-live `confirmed` future booking a manage token and a banded reminder — the gap F16 inherited because F14 shipped bookings before the manage link existed.
- [[backend/app/booking/comms.py]] — The booking lifecycle's SMS orchestration: when a reminder is scheduled (three bands), how a due batch is claimed and drained by the worker, how the four bodies are delivered through the single `message_log` writer, and what happens when…
- [[backend/app/booking/comms_templates.py]] — The four Hebrew lifecycle SMS bodies, the UCS-2 segment arithmetic that keeps them inside a three-segment cost ceiling, the boutique-zone date/weekday/time rendering they use, and the mask that keeps the raw manage token out of the…
- [[backend/app/booking/manage.py]] — The service behind the anonymous `/b/{token}` page: resolve a booking by manage-token possession alone, render its facts with the policy from the **accepted** terms version, and let the customer confirm attendance or cancel — both…
- [[backend/app/booking/owner.py]] — The owner console's booking service: the Jerusalem-day list and detail, the four-verb status graph split at `starts_at`, the in-place reschedule protocol, and the owner-attested phone correction that rotates live manage links inside the…
- [[backend/app/booking/owner_router.py]] — The owner console's ten booking routes on `/manage` — day list, detail, four status verbs, reschedule, phone correction, resend-link and the owner slot grid — behind a router-level role gate and `no-store`, with every SMS fired post-commit…
- [[backend/app/booking/router.py]] — The four anonymous, tenant-scoped POSTs on `/storefront`: create a booking, and the three token-authed manage actions (lookup, confirm-attendance, cancel) — plus the post-commit confirmation SMS.
- [[backend/app/booking/schemas.py]] — Every wire shape the booking feature exposes across three audiences — the anonymous create, the token-authed manage page, and the session-authed owner console — with the PII boundary between them expressed as separate models rather than as…
- [[backend/app/booking/service.py]] — The claim: turns a phone-verified anonymous request into exactly one `bookings` row at a slot the grid offers, under a per-tenant advisory lock with a partial unique index as the structural backstop — and returns the raw manage token that…
- [[backend/app/booking/slots.py]] — The ONE place "is this time bookable" is decided: turns weekly availability rules plus date exceptions into the exact set of bookable UTC start instants in a date window, dropping past, nonexistent-under-DST and already-full slots.
- [[backend/app/booking/slots_io.py]] — The I/O-shaped sibling of the pure grid: reads one boutique day's availability rules, exceptions and booked counts, hands them to `materialize_slots`, and answers the single question both write paths need — *is this exact instant offered…
- [[backend/app/booking/tokens.py]] — Mint, hash and constant-time-compare the manage-link credential — the secret in `/b/{token}` that lets an anonymous bride read, confirm attendance on and cancel her own booking, stored on `bookings.manage_token_hash` as sha256 only.
- [[backend/app/booking/validation.py]] — The booking module's product-policy constants (slot granularity, window ceilings, name/notes lengths, list paging bounds), the pure request-shape checker that answers a clean 400 without touching the database, and the single…
