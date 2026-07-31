---
tags: [frontend, storefront, i18n, arabic, untranslated, rtl]
sources: [frontend/apps/storefront/src/i18n/ar.ts]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/i18n/ar.ts
blob: 1813f1f3149c596d4abff9933af8b9e11522df41
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/storefront/src/i18n/ar.ts

**Role.** The Arabic resource bundle — **shipped, registered, and entirely untranslated.** Every value in it is the approved Hebrew standing in as a placeholder. Nothing renders from this file today, and nothing is meant to.

**Module.** [[frontend/apps/storefront/src/i18n/_index]] · **Layer.** app shell

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `ar` | const | `{ translation: { document, manage, booking } }`, `as const` — F16's keys only |

## Behavior

**This is a deliberate forward-cost decision, recorded in the file header** (Interview Q3 / pre-decided #47): every feature from F16 onward adds its `ar` keys alongside its Hebrew, so the eventual Arabic launch is a translation job on one file rather than a retrofit across ~28 features. Arabic is **not live** for the pilot — [[frontend/apps/storefront/src/i18n/index.ts]] pins `lng: "he"` and ships no switcher.

**The placeholder values are Hebrew, not empty strings, and that choice is load-bearing.** i18next's `returnEmptyString` default renders `""` rather than falling back, so a premature `lng: "ar"` with empty values would blank the page instead of degrading to Hebrew. Hebrew placeholders also mean a translator opens one file and sees every key beside its live source text, replacing values in place. `fallbackLng: "he"` covers every key this file does not yet carry — which is the large majority, since it starts at F16.

The expensive half of Arabic is already paid for: Hebrew makes RTL the document default, and Arabic is also RTL. What remains is strings, number/date formatting and a switcher — no direction-switching logic and no second stylesheet, by that same ruling.

## Depends On

Nothing — a pure data module with no imports.

## Depended On By

- [[frontend/apps/storefront/src/i18n/index.ts]] — registered as the `ar` resource

## Tests

**None, and this is the gap worth knowing about.** [[frontend/apps/storefront/src/__tests__/i18n-keys.test.ts]] resolves keys against `he.translation` only and never opens this file, so nothing checks that `ar`'s keys still exist in `he`, nothing flags a key `he` renamed and `ar` did not, and nothing detects a value here that was *supposed* to be translated. The drift is invisible until a switcher ships.

## Notes

Carries only three sections (`document.manageTitle`, the `manage` block, one `booking` key) because F16 was the first feature to add Arabic. Later features append theirs — so the size of this file is a rough record of how much of the product has been built since that ruling.
