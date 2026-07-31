---
tags: [frontend, ui, barrel, public-api, export-surface, design-system]
sources: [frontend/packages/ui/src/index.ts]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/index.ts
blob: aab88d264857f5426a657818984bb05c478fd2e3
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/index.ts

**Role.** The entire public surface of `@boutique/ui` — the barrel that both apps import from, and the *only* module path either app is expected to name. It re-exports the tokens, the two lib helpers, twenty-odd components with their prop types, and the hours engine, grouped by who consumes them: shared primitives, storefront composites, one deliberately-shared composite, then manage-console composites.

**Module.** [[frontend/packages/ui/src/_index]] · **Layer.** frontend / shared library

## Public Surface

Grouped as the file itself groups them.

| Group | Exports |
|---|---|
| Tokens | `tokens`, `themeTokens`, types `Tokens` / `ThemeTokens` — from [[frontend/packages/ui/src/tokens.ts]] |
| Lib | `cn`, `focusRing` ([[frontend/packages/ui/src/lib/styles.ts]]); `safeHref` ([[frontend/packages/ui/src/lib/url.ts]]) |
| Form + control primitives | `Button`, `ButtonLink`, `Input`, `TextArea`, `Select`, `Toggle`, `Checkbox`, `TimeField`, `DateField` |
| Display primitives | `Badge`, `Card`, `Skeleton`, `EmptyState`, `SectionHeading`, `Price` |
| Overlay / feedback | `Modal`, `ToastProvider`, `useToast` |
| A11y | `SkipLink`, `VisuallyHidden`, `A11yMenu`, `A11yStatementLink` |
| Hours | `groupWeeklyRules`, `jerusalemDayIndex`, `nextOpen`, `todayHours`, `JERusalem` + all six types — from [[frontend/packages/ui/src/lib/hours.ts]] |
| Storefront composites | `HoursTable`, `BoutiqueHeader`, `DressCard`, `DressGrid`, `Gallery`, `BookingCTA`, `ContactPanel` |
| Shared composite | `SlotPicker` |
| Manage composites | `ConsoleShell`, `SetupProgress`, `PolicyBlockerBanner` |

Every component ships its props type alongside it (`ButtonProps`, `DressCardProps`, `SlotPickerLabels`, …). Two exceptions are worth knowing: `TimeField`/`DateField` export **no** props type, because they are `Omit<InputProps, "type">` wrappers over `Input`; and the toast surface exports `useToast` plus `ToastOptions`/`ToastVariant`/`ShowToast` but **not** `ToastContext`.

## Behavior

**The barrel is where the package's no-i18n rule becomes visible.** Look at what is exported and what is not: components come with `…Labels` types (`GalleryLabels`, `ContactPanelLabels`, `SlotPickerLabels`) because **every string arrives as a prop**. There is no `t()`, no locale, no i18next import anywhere in the package — the Hebrew lives in the apps ([[frontend/apps/storefront/src/i18n/he.ts]]). Adding an i18n dependency here would let a component render text it was never handed, and the label types would rot into decoration.

**`ToastContext` is held back deliberately.** [[frontend/packages/ui/src/components/toast-context.ts]] exports the raw `createContext` object, and this barrel does not forward it — consumers get `ToastProvider` and the `useToast()` hook (which is the one that can throw on a missing provider) and cannot reach around them. Same shape of decision as the `Omit<…, "type">` wrappers: the surface is narrower than the module.

**The `SlotPicker` grouping is a documented sharing decision, not tidiness.** Its comment records that the storefront's booking flow and the console's reschedule dialog render the *same* grid from the same materializer, so the `fieldset`/`legend`/radio contract lives in one place rather than being implemented twice and drifting on one side. That is why it sits between the two app-specific groups rather than inside either.

**This is the `.` entry point only — `theme.css` is a separate one.** The barrel exports no CSS; [[frontend/packages/ui/src/theme.css]] is reached through the manifest's `"./theme.css"` export and imported from each app's `index.css`. An app that imported only this file would get every component with none of the tokens they resolve against. Because [[frontend/packages/ui/package.json]] points `main`/`types`/`exports["."]` straight at this TypeScript file, there is no build step between an edit here and the apps — but there is also no tree-shaking safety net beyond the bundler's, so a side-effectful module added to this graph would run for every consumer.

## Depends On

Every module under `src/components/` and `src/lib/`, plus [[frontend/packages/ui/src/tokens.ts]]. Nothing external.

## Depended On By

- [[frontend/apps/storefront/package.json]] and [[frontend/apps/manage/package.json]] — the workspace dependency
- Storefront: [[frontend/apps/storefront/src/App.tsx]] · [[frontend/apps/storefront/src/components/StorefrontLayout.tsx]] · [[frontend/apps/storefront/src/components/ContactCard.tsx]] · [[frontend/apps/storefront/src/components/HoursCard.tsx]] · [[frontend/apps/storefront/src/components/ShareButton.tsx]] · [[frontend/apps/storefront/src/components/DescriptionClamp.tsx]] · [[frontend/apps/storefront/src/components/BookingCTAButton.tsx]] · [[frontend/apps/storefront/src/components/booking/SizeChips.tsx]] · [[frontend/apps/storefront/src/components/booking/TypePicker.tsx]] · [[frontend/apps/storefront/src/lib/contact.ts]] · [[frontend/apps/storefront/src/lib/hoursText.ts]] · all files under `frontend/apps/storefront/src/routes/`
- Manage: [[frontend/apps/manage/src/App.tsx]] · [[frontend/apps/manage/src/lib/jerusalem.ts]] · [[frontend/apps/manage/src/lib/booking.tsx]] · every file under `frontend/apps/manage/src/components/`
- [[frontend/e2e/storefront.spec.ts]]

## Concepts

- [[Design Tokens]]
- [[Jerusalem Time]]

## Tests

No test of its own. Its contents are covered by the per-component suites under `frontend/packages/ui/src/__tests__/`; the apps' suites (e.g. [[frontend/apps/storefront/src/__tests__/CatalogPage.test.tsx]]) exercise it as the import path.

## Notes

[[frontend/packages/api-client/package.json]] is a deliberately empty stub — the apps hand-write their own typed fetch clients ([[frontend/apps/storefront/src/api.ts]]). So this barrel, not a generated client, is the only cross-app code contract in the frontend.
