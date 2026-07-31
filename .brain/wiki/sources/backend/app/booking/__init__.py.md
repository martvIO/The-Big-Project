---
tags: [backend, booking, python, package]
sources: [backend/app/booking/__init__.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/booking/__init__.py
blob: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/booking/__init__.py

**Role.** Empty file marking `app.booking` as a package — the E3 booking engine, the most intricate module in the backend.

**Module.** [[backend/app/booking/_index]] · **Layer.** api

## Behavior

Zero bytes, no re-exports. Every consumer imports the concrete module it needs ([[backend/app/main.py]] imports five of them; [[backend/app/storefront/service.py]] imports only [[backend/app/booking/slots.py]]), so nothing here mediates. The one thing worth knowing about the package boundary is that it is deliberately importable *downward*: [[backend/app/storefront/service.py]] depends on `app.booking.slots`, never the reverse for the pure grid — and [[backend/app/auth/staff_router.py]] records a decision to duplicate three lines rather than import from `app.booking.owner_router`, because `app.auth` importing `app.booking` would point the dependency arrow backwards.

## Concepts

- [[Tenant Isolation]]
