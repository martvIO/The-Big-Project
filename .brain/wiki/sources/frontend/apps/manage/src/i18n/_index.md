---
tags: [frontend, typescript, i18n, hebrew]
sources: [frontend/apps/manage/src/i18n]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/src/i18n
blob: 11ddac1b00530a76f3cfffb5567372ffb055f1e7
commit: 13d107b8b16f1f2676f1cdb1c994f95822fe2ba0
kind: directory
applicability: active
---

# frontend/apps/manage/src/i18n/

**Purpose.** Hebrew strings, and the Arabic bundle that ships untranslated with the Hebrew standing in as placeholders.

**Parent.** [[frontend/apps/manage/src/_index]]

## Files

- [[frontend/apps/manage/src/i18n/ar.ts]] — The Arabic resource bundle — **shipped, registered, and entirely untranslated**.
- [[frontend/apps/manage/src/i18n/he.ts]] — The console's Hebrew string catalog and the only locale an owner can reach in v1 — every visible word in the owner console that is not data. It is structurally two catalogs in one object: **nested namespaces** (`document`, `console`…
- [[frontend/apps/manage/src/i18n/index.ts]] — The console's i18next initialisation: registers the `he` and `ar` bundles, pins the language to Hebrew, and exports the configured instance. Imported for its side effect by [[frontend/apps/manage/src/main.tsx]] and by every test file that…
