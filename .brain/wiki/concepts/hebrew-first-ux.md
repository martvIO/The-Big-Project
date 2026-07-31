---
tags: [frontend, i18n, hebrew, product, design]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: active
---

# Hebrew First UX

**What it is.** Hebrew is not a localization of an English product — it is the only locale a
visitor can reach in v1. `lng: "he"`, `fallbackLng: "he"`, no language switcher
([[frontend/apps/storefront/src/i18n/index.ts]]).

## Arabic ships untranslated, on purpose

[[frontend/apps/storefront/src/i18n/ar.ts]] is registered but not selectable, and **every value in
it is the approved Hebrew standing in as a placeholder**. Both halves are deliberate:

- from F16 onward every feature adds its `ar` keys alongside its Hebrew, so the eventual launch is
  a translation job rather than a retrofit across ~28 features;
- an *empty* string would be worse than a Hebrew one — i18next's `returnEmptyString` default
  renders `""` rather than falling back, so a premature switch would blank the page.

The expensive half of Arabic is already paid for: Hebrew makes RTL the default and Arabic is also
RTL, so there is no direction-switching logic and no second stylesheet
([[RTL And Bidi Isolation]]).

## Copy rules that are not style preferences

- **`escapeValue: false`.** React already escapes; double-escaping corrupts Hebrew punctuation.
- **Whole i18n keys only, never composed at render time.** A key assembled from a fragment is
  invisible to the static `i18n-keys` guard, and i18next answers a miss with the bare key — so a
  renamed entry would print ASCII into a Hebrew page
  ([[frontend/apps/storefront/src/routes/AccessibilityPage.tsx]] spells this out).
- **The backend speaks English and the frontend never repeats it.** Every server message —
  `"No active boutique at this address."`, `"Too many attempts. Try again later."` — is English, so
  failure copy is selected by error **code** and rendered from the Hebrew bundle. Painting the
  server's sentence onto the page is the failure mode, and it is invisible to axe.

## Typography and locale

Display font Frank Ruhl Libre, body Assistant, both self-hosted via `@fontsource` **per weight** —
a bare import ships 400 alone and faux-bolds Hebrew ([[frontend/packages/ui/src/theme.css]]).
Israeli week (Sun–Thu, short Friday). Money is integer agorot, rendered number-then-`₪`. Dates run
on the boutique's calendar, not the device's — [[Jerusalem Time]].

## The storefront is the boutique's, not the platform's

[[frontend/apps/storefront/index.html]] carries a Hebrew `<title>` and only the platform *favicon*.
A `MODRYN` in that title is a regression, pinned by [[frontend/e2e/a11y.spec.ts]]: the storefront
is the boutique's own shop front, and the platform brands the console, not the shop.

## Related

- [[RTL And Bidi Isolation]] · [[Accessibility Compliance]] · [[Design Tokens]]
- [[frontend/apps/storefront/src/i18n/he.ts]] · [[frontend/apps/manage/src/i18n/index.ts]]
- [[.planning/design-config.md]] · [[.planning/specs/modryn-branding.md]]
