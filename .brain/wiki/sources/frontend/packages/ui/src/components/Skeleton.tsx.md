---
tags: [frontend, ui, component, loading, accessibility, motion]
sources: [frontend/packages/ui/src/components/Skeleton.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/components/Skeleton.tsx
blob: dadd899ba3a7e8f080c3e8f319542f6c80bcc771
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/components/Skeleton.tsx

**Role.** The single loading placeholder for both apps — three shapes (`text` / `image` / `block`) sharing one shimmer bar, every one of them `aria-hidden`. It is the most-used component in the repo: nearly every route and console section renders it while its fetch is in flight.

**Module.** [[frontend/packages/ui/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `Skeleton` | fn | placeholder block; three early-return branches on `variant` |
| `SkeletonVariant` | type | `"text" \| "image" \| "block"` |
| `SkeletonProps` | interface | `{variant?, lines?, className?}` — `variant` defaults to `"block"`, `lines` to `3` |

## Behavior

All three branches share the module-local `bar` class (`animate-skeleton rounded-sm bg-border`). `text` renders `lines` sibling `<span>`s of `h-4` inside a gap-2 column and shortens the **last** line to `w-2/3` so the block reads as a paragraph rather than a table; `image` is a single `aspect-[3/4]` full-width div matching the dress-card photo ratio; `block` fills its parent (`h-full w-full`) and therefore only works inside a container that already has a height.

**Every branch sets `aria-hidden="true"`.** A skeleton is decoration for a state the user is already in — announcing a dozen empty bars is pure noise, and the loading state proper is communicated by the copy or region that replaces them. Consequently a screen-reader user gets *nothing* from a screen that is only skeletons; that is the accepted trade, not an oversight.

The pulse is the `--animate-skeleton` token (`skeleton-pulse 1.5s ease-in-out infinite`) declared in `frontend/packages/ui/src/theme.css`, and the global `prefers-reduced-motion` block in the same stylesheet freezes it — the component itself contains no media query, so a copy-pasted `animate-pulse` elsewhere would *not* inherit that protection.

`className` is applied per-bar, not to the wrapper. In the `text` branch it lands on **every** line span (inside the same `cn()` as `w-2/3`), so a caller passing a width utility overrides… nothing reliably: `cn()` is a plain join with no class-merge, and same-specificity Tailwind rules resolve by stylesheet order. Size a skeleton by the container it sits in, not by a class you pass it.

## Depends On

- [[frontend/packages/ui/src/lib/styles.ts]] — `cn`
- [[Tailwind CSS]] — `animate-skeleton` maps to the `--animate-skeleton` theme token (entity)

## Depended On By

- [[frontend/packages/ui/src/index.ts]] — re-exports `Skeleton` + `SkeletonProps` + `SkeletonVariant`
- [[frontend/apps/storefront/src/routes/CatalogPage.tsx]] · [[frontend/apps/storefront/src/routes/DressPage.tsx]] · [[frontend/apps/storefront/src/routes/AboutPage.tsx]] · [[frontend/apps/storefront/src/routes/BookPage.tsx]] · [[frontend/apps/storefront/src/routes/ManageBookingPage.tsx]]
- [[frontend/apps/manage/src/components/BookingsSection.tsx]] · [[frontend/apps/manage/src/components/BookingDetail.tsx]] · [[frontend/apps/manage/src/components/CatalogSection.tsx]] · [[frontend/apps/manage/src/components/DressEditor.tsx]] · [[frontend/apps/manage/src/components/HoursSection.tsx]] · [[frontend/apps/manage/src/components/ProfileSection.tsx]] · [[frontend/apps/manage/src/components/StaffSection.tsx]] · [[frontend/apps/manage/src/components/TermsSection.tsx]] · [[frontend/apps/manage/src/components/TypesSection.tsx]] · [[frontend/apps/manage/src/components/RescheduleDialog.tsx]]

## Concepts

- [[Accessibility Compliance]]

## Tests

- [[frontend/packages/ui/src/__tests__/display-primitives.test.tsx]] — asserts the wrapper is `aria-hidden`, that `lines={4}` yields exactly four children, and that the `image` variant carries `animate-skeleton`

## Notes

The `text` branch's `key={i}` is an array index, which is correct here precisely because the list has no identity and never reorders.
