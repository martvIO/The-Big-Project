---
tags: [frontend, manage, i18n, arabic, placeholder, rtl]
sources: [frontend/apps/manage/src/i18n/ar.ts]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/src/i18n/ar.ts
blob: d5c97bcea801f70cfae32349493bef4f4fa67a0b
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/manage/src/i18n/ar.ts

**Role.** The Arabic resource bundle — **shipped, registered, and entirely untranslated**. Every value is the approved Hebrew standing in as a placeholder. It carries only the F15 booking keys and the F51 staff keys; nothing renders from it today.

**Module.** [[frontend/apps/manage/src/i18n/_index]] · **Layer.** i18n

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `ar` | const (`as const`) | `{ translation: { … } }` — registered under `ar` by [[frontend/apps/manage/src/i18n/index.ts]] |

## Behavior

**The Hebrew values are the design, not laziness.** A translator opens one file and sees every key with its live source text beside it, replacing values in place. An empty string would be strictly worse: i18next's `returnEmptyString` defaults to true, so `""` renders as an empty node rather than falling back — a premature language switch would blank the console instead of showing Hebrew. `fallbackLng: "he"` covers every key this file does **not** carry, which is why a partial bundle is safe to ship.

Arabic is not live for the pilot: `lng` stays `"he"`, no switcher component exists, and no direction-switching logic or second stylesheet ships. The expensive half is already paid for — Hebrew makes RTL the document default and Arabic is also RTL — so what remains is strings, number/date formatting, and a switcher.

**Nothing keeps this file in sync with [[frontend/apps/manage/src/i18n/he.ts]].** There is no he/ar parity guard in this repo, and the F15/F51 test suites assert only over the Hebrew bundle. A key added to `he.ts` and not here simply falls back to Hebrew — which is what renders today regardless — so the drift is harmless now and becomes a translation backlog the day a switcher lands.

The file was started by F15 (the console's first Arabic bundle; the storefront has had its own since F16) and later console features append their keys. The `staff.deactivateBody` placeholder keeps its literal `<bdi>` markup, so the `<Trans>` render path stays valid when a real Arabic string replaces the value.

## Depends On

Nothing — a plain object literal.

## Depended On By

- [[frontend/apps/manage/src/i18n/index.ts]]
- [[frontend/apps/manage/src/__tests__/i18n.test.ts]]

## Concepts

- [[RTL And Bidi Isolation]]

## Tests

- [[frontend/apps/manage/src/__tests__/i18n.test.ts]] — imports the bundle; the assertions it shares with the Hebrew catalog (no exclamation marks, no delivery claims) hold trivially while the values *are* the Hebrew

## Notes

**Warning for a future reader:** because the values are Hebrew, any test that asserts "the Arabic bundle differs from the Hebrew" would fail today, and any grep for Arabic script in this repo finds nothing. The pre-F15 nested namespaces (`console`, `nav`, `login`, `profile`, `common`) are absent here entirely — only the flat dotted keys were ever added.
