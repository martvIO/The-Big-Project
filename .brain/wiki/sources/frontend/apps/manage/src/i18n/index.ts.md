---
tags: [frontend, manage, i18n, i18next, hebrew, config]
sources: [frontend/apps/manage/src/i18n/index.ts]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/src/i18n/index.ts
blob: c4f09ed79d73fbc605c9dc647fba695b6ed69de1
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/manage/src/i18n/index.ts

**Role.** The console's i18next initialisation: registers the `he` and `ar` bundles, pins the language to Hebrew, and exports the configured instance. Imported for its side effect by [[frontend/apps/manage/src/main.tsx]] and by every test file that renders translated copy.

**Module.** [[frontend/apps/manage/src/i18n/_index]] · **Layer.** i18n

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| default export | `i18n` instance | the initialised i18next singleton; imported by [[frontend/apps/manage/src/__tests__/i18n.test.ts]] to resolve keys directly |

## Behavior

Four config choices, each doing work. `lng: "he"` is a **hard pin**, not a detection default — no `LanguageDetector` plugin is wired and no switcher component ships, so Hebrew is the only locale an owner can reach in v1. `ar` is registered anyway so the bundle is exercised by the build and the resource shape stays valid; nothing renders from it today. `fallbackLng: "he"` is what makes the partial Arabic bundle safe: any key [[frontend/apps/manage/src/i18n/ar.ts]] does not carry resolves to the Hebrew.

`interpolation.escapeValue: false` is correct here specifically because React already escapes anything it renders; leaving i18next's default on would double-escape apostrophes and quotes in the Hebrew copy.

The `void` before `i18n.use(...).init(...)` discards the returned promise on purpose — `init` is synchronous when the resources are inline objects rather than loaded over HTTP, so there is nothing to await, and the `void` is what keeps the lint rule for floating promises quiet without a suppression comment.

**The non-obvious resolution behaviour lives in the bundles, not here.** Both bundles hold a mix of nested namespaces (`console.title`) and flat dotted literal keys (`"booking.dateLabel"`). i18next handles that through `ignoreJSONStructure`, which defaults to true and falls back to a flat lookup when the nested path misses — turning that option off would leave every F15/F51 key rendering as its own key string in the console.

## Depends On

- [[frontend/apps/manage/src/i18n/he.ts]]
- [[frontend/apps/manage/src/i18n/ar.ts]]
- [[i18next]] — `i18n`, `initReactI18next`

## Depended On By

- [[frontend/apps/manage/src/main.tsx]]
- [[frontend/apps/manage/src/__tests__/i18n.test.ts]], [[frontend/apps/manage/src/__tests__/Nav.test.tsx]], and the other component suites — each imports `"../i18n"` so rendered copy is Hebrew rather than raw keys

## Tests

- [[frontend/apps/manage/src/__tests__/i18n.test.ts]] — proves every dotted literal key actually resolves through this instance
