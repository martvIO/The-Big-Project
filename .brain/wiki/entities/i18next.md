---
tags: [frontend, i18n, hebrew, arabic, copy]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: entity
applicability: n/a
---

# i18next

**Purpose.** All user-facing copy in both apps. i18next 26.3.6 with `react-i18next` 17.0.11, initialised identically in [[frontend/apps/storefront/src/i18n/index.ts]] and [[frontend/apps/manage/src/i18n/index.ts]]: `lng: "he"`, `fallbackLng: "he"`, `interpolation.escapeValue: false` (React already escapes; double-escaping corrupts Hebrew punctuation).

**Two bundles, one reachable.** `he` is live. `ar` — [[frontend/apps/storefront/src/i18n/ar.ts]], [[frontend/apps/manage/src/i18n/ar.ts]] — is registered but **not selectable**: no language switcher ships, and every feature adds its Arabic keys untranslated so the eventual launch is a translation job rather than a retrofit. **Every `ar` value is the approved Hebrew standing in as a placeholder, never `""`** — i18next's `returnEmptyString` defaults to `true`, so an empty value renders `""` instead of falling back and would blank the page. [[frontend/apps/manage/src/__tests__/i18n.test.ts]] and [[frontend/apps/storefront/src/__tests__/i18n-keys.test.ts]] assert exactly that, plus key-for-key parity with `he`.

**`packages/ui` has no i18next dependency, by design.** Check [[frontend/packages/ui/package.json]]: every string is a prop — `Price` takes `hiddenLabel`, `SkipLink` takes children — so the component package stays locale-agnostic and the apps own the copy deck.

Newer keys are **dotted string literals** (`"booking.error.SLOT_UNAVAILABLE"`) sitting beside older nested namespaces in the same bundle; they resolve through i18next's `ignoreJSONStructure` flat fallback. An unresolved key renders as the key itself, which is why the suites above assert resolution rather than mere presence.
