---
tags: [frontend, storefront, i18n, i18next, hebrew, rtl]
sources: [frontend/apps/storefront/src/i18n/index.ts]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/i18n/index.ts
blob: 08f5cc2a7c41e0aa87e148dd36e6e0b810e0ae65
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/storefront/src/i18n/index.ts

**Role.** The single `i18n.init()` call for the public site: registers `he` and `ar`, pins `lng: "he"`, and default-exports the initialised instance so non-component code can call `t()` without a hook.

**Module.** [[frontend/apps/storefront/src/i18n/_index]] · **Layer.** app shell

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| default export | i18next instance | the initialised singleton; imported as a value by [[frontend/apps/storefront/src/validation.ts]] |

Side effect on import: `i18n.use(initReactI18next).init(...)` — which is why [[frontend/apps/storefront/src/main.tsx]] carries a bare `import "./i18n"` before rendering.

## Behavior

Three config choices, each with a reason. `lng: "he"` is fixed and there is **no language switcher** — Hebrew is the only locale a visitor can reach in v1. `ar` is registered anyway so the bundle is loadable the day a switcher ships; see [[frontend/apps/storefront/src/i18n/ar.ts]] for why it exists untranslated. `fallbackLng: "he"` covers every key the partial `ar` bundle does not carry, which is most of them.

`interpolation.escapeValue: false` because React already escapes; leaving i18next's default on would double-escape and corrupt Hebrew punctuation.

The default export matters as much as the side effect. Component code reaches strings through `useTranslation`, but [[frontend/apps/storefront/src/validation.ts]] runs inside event handlers and needs `i18n.t()` directly — that only works because this module both initialises and exports the same instance, and because `main.tsx` imports it before the first render.

## Depends On

- [[i18next]]
- [[frontend/apps/storefront/src/i18n/he.ts]] — the live bundle
- [[frontend/apps/storefront/src/i18n/ar.ts]] — registered, not selectable

## Depended On By

- [[frontend/apps/storefront/src/main.tsx]] — side-effect import at boot
- [[frontend/apps/storefront/src/validation.ts]] — value import, for `i18n.t()`
- every test under [[frontend/apps/storefront/src/__tests__/i18n-keys.test.ts]] and its siblings, which import `../i18n` to get a real bundle rather than mocking `t`

## Tests

- [[frontend/apps/storefront/src/__tests__/i18n-keys.test.ts]] — resolves every key the source uses through this instance, not only through `he.translation`

## Notes

`void i18n.use(...).init(...)` — the `void` discards the returned promise deliberately; nothing awaits initialisation because the resources are synchronous imports.
