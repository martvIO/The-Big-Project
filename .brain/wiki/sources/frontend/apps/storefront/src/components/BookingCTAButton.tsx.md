---
tags: [frontend, storefront, react, navigation, cta]
sources: [frontend/apps/storefront/src/components/BookingCTAButton.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/components/BookingCTAButton.tsx
blob: 9b2fd87a8a04d039b9c303e2e1466bf2a3768c98
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/storefront/src/components/BookingCTAButton.tsx

**Role.** The one entry into `/book/*` — a `ButtonLink` anchor carrying `booking.cta`, wrapped in the fixed-bar `BookingCTA` by default and rendered bare when `inline`. It takes **no boutique data at all**, which is the whole design decision: a control that only navigates has nothing to degrade, so it renders unchanged on a page whose boutique fetch failed.

**Module.** [[frontend/apps/storefront/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `BookingCTAButton` | component | `{dressId?, inline?}` — the CTA, bar or inline |
| `BookingCTAButtonProps` | interface | |

## Behavior

`href` is `/book/slot` unbound and `/book/slot/${encodeURIComponent(dressId)}` bound — a path **segment**, never a query string, because the navigation store snapshots `pathname` only and would never observe a query. The encoding matches `api.getDress`'s, and `decodeId` in [[frontend/apps/storefront/src/router.tsx]] is its matching decoder. The href must stay absolute: the root click delegation pushes the anchor's raw `getAttribute("href")` rather than the resolved `.href`, so a relative value would be pushed verbatim.

It is an **anchor, not a button**, and the file says why: delegation turns a same-origin `<a>` into a client navigation while letting modifier-, middle- and target-clicks fall through, so open-in-new-tab and "copy link address" keep working on a page brides reach from an Instagram deep link. `onClick` + `navigate()` destroys both.

`inline` is not cosmetic — it selects whether `BookingCTA` is in the tree at all. `/about` is the one storefront screen that must carry no fixed bar at any width (qa §7), and `BookingCTA` cannot be argued out of its bar with a `className`: its base is `fixed inset-x-0 bottom-0` with only `md:static`, and `cn` is a naive joiner with no tailwind-merge, so at equal specificity the winner is decided by stylesheet order rather than by the caller. Which routes carry a bar is duplicated in [[frontend/apps/storefront/src/components/StorefrontLayout.tsx]]'s `hasBookingBar` — the layout reserves the footprint and lifts the A11y trigger; this component only renders the control. Change one without the other and the statutory הצהרת נגישות link ends up under the bar.

## Depends On

- [[frontend/packages/ui/src/components/BookingCTA.tsx]] — the responsive bar wrapper
- [[frontend/packages/ui/src/components/Button.tsx]] — `ButtonLink`
- [[i18next]] — `useTranslation`, `booking.cta`

## Depended On By

- [[frontend/apps/storefront/src/routes/CatalogPage.tsx]] — unbound, in the header row
- [[frontend/apps/storefront/src/routes/DressPage.tsx]] — bound to `dressId`, in the facts column
- [[frontend/apps/storefront/src/routes/AboutPage.tsx]] — `inline`, the only such caller

## Concepts

- [[Design Tokens]]
- [[Accessibility Compliance]]

## Tests

- [[frontend/apps/storefront/src/__tests__/AboutPage.test.tsx]] — the inline/no-bar branch
- [[frontend/apps/storefront/src/__tests__/CatalogPage.test.tsx]] · [[frontend/apps/storefront/src/__tests__/DressPage.test.tsx]]
- [[frontend/e2e/storefront.spec.ts]]

## Notes

The `w-full` passed for `inline` is the one className this component sends into `ButtonLink`; see [[.planning/design/qa-checklist.md]] §7 for the bar rules it encodes.
