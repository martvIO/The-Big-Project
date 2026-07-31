---
tags: [frontend, typescript]
sources: [frontend/apps]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps
blob: cecae8c6fc050adcc45e891660678c1e7578ffd4
commit: 13d107b8b16f1f2676f1cdb1c994f95822fe2ba0
kind: directory
applicability: active
---

# frontend/apps/

**Purpose.** The two shipped applications — the public storefront and the authenticated owner console.

**Parent.** [[frontend/_index]]

## Subdirectories

- [[frontend/apps/manage/_index]] — The owner and shift-manager console. Cookie-authenticated against `/manage`, Hebrew-only, and deliberately router-less.
- [[frontend/apps/storefront/_index]] — The public per-tenant boutique site: catalogue, dress pages, the booking flow, and the tokenized manage-booking page.
