---
tags: [backend, python]
sources: [backend/app/boutique]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/boutique
blob: 168e85d989d5e2457a818927c04d8decd578f424
commit: 13d107b8b16f1f2676f1cdb1c994f95822fe2ba0
kind: directory
applicability: active
---

# backend/app/boutique/

**Purpose.** Owner settings: profile, opening hours, appointment types, and the append-only terms versions a booking pins itself to.

**Parent.** [[backend/app/_index]]

## Files

- [[backend/app/boutique/__init__.py]] — Empty package marker for the owner-settings module (profile, toggles, appointment types, opening hours, cancellation-policy terms) — it re-exports nothing.
- [[backend/app/boutique/router.py]] — The eleven `/manage` owner-settings endpoints — profile/toggles, appointment types, opening hours and terms — gated router-wide on `OWNER | SHIFT_MANAGER`, with terms *publishing* tightened to owner-only on its own route.
- [[backend/app/boutique/schemas.py]] — The wire contract for the `/manage` owner-settings API — extra-forbidding request models whose `Field` bounds mirror the migration CHECKs, response models for appointment types, availability and terms versions, and a compatibility…
- [[backend/app/boutique/service.py]] — Owner-settings business logic — the `tenants.settings` JSONB merge, appointment-type CRUD, the whole-week opening-hours replace and exception dates, and the append-only cancellation-policy terms versions with their optimistic version race…
- [[backend/app/boutique/validation.py]] — Pure, I/O-free write-time gates for owner settings — the storefront-profile fields (phone, address, description, `maps_url`, essence, Instagram handle), the boolean toggles, appointment types, weekly opening windows, exception dates and…
