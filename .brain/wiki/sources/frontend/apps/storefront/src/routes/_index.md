---
tags: [frontend, typescript]
sources: [frontend/apps/storefront/src/routes]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/routes
blob: 4c960e9be203ed569b723349c99731ea825c22a2
commit: 13d107b8b16f1f2676f1cdb1c994f95822fe2ba0
kind: directory
applicability: active
---

# frontend/apps/storefront/src/routes/

**Purpose.** One component per route, wired by the hand-rolled router.

**Parent.** [[frontend/apps/storefront/src/_index]]

## Files

- [[frontend/apps/storefront/src/routes/AboutPage.tsx]] — `/about` — the trust surface (Flow S3: "אמיתי? שווה ביקור? מתי פתוח?").
- [[frontend/apps/storefront/src/routes/AccessibilityPage.tsx]] — `/accessibility` — הצהרת נגישות, the statutory accessibility statement. IS 5568 §35 makes this page *and a named, reachable contact inside it* a legal obligation for a public Israeli site, so it is written to be read by a screen reader and…
- [[frontend/apps/storefront/src/routes/BookPage.tsx]] — The entire `/book/*` flow in one component: shell, stepper, and all five steps (`slot` → `details` → `terms` → `verify` → `confirm`), plus every degrade and every routed recovery from a failed submit. It is one file on purpose — the flow's…
- [[frontend/apps/storefront/src/routes/CatalogPage.tsx]] — `/` — the boutique's collection. Identity header from the layout's shared fetch, the dress grid from this route's own paged read, and five mutually exclusive body states (identity-failed, list-failed, loading, empty, grid).
- [[frontend/apps/storefront/src/routes/DressPage.tsx]] — `/dress/{id}` — one dress: gallery (or monogram) beside a facts column of name, price, clamped description, size badges, share and the bound booking CTA. Four states: loading, `notFound`, `failed`, loaded.
- [[frontend/apps/storefront/src/routes/ManageBookingPage.tsx]] — `/b/{token}` (F16) — the page behind the tokenized manage link that rides the confirmation and reminder SMS. It is the confirmation screen's **sibling, not a flow**: she arrived from a text message, possibly weeks later, so there is no…
