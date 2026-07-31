---
tags: [frontend, typescript, i18n, hebrew]
sources: [frontend/apps/storefront/src/i18n]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/i18n
blob: 6763e9db3e580823671a0c8cada65877f9a93440
commit: 13d107b8b16f1f2676f1cdb1c994f95822fe2ba0
kind: directory
applicability: active
---

# frontend/apps/storefront/src/i18n/

**Purpose.** Hebrew strings plus the untranslated Arabic bundle.

**Parent.** [[frontend/apps/storefront/src/_index]]

## Files

- [[frontend/apps/storefront/src/i18n/ar.ts]] — The Arabic resource bundle — **shipped, registered, and entirely untranslated.** Every value in it is the approved Hebrew standing in as a placeholder. Nothing renders from this file today, and nothing is meant to.
- [[frontend/apps/storefront/src/i18n/he.ts]] — Every visible string on the public site, in one `as const` object under twelve sections. This is the *only* place Hebrew may be written — no component, and no other module, may hardcode a visitor-facing string.
- [[frontend/apps/storefront/src/i18n/index.ts]] — The single `i18n.init()` call for the public site: registers `he` and `ar`, pins `lng: "he"`, and default-exports the initialised instance so non-component code can call `t()` without a hook.
