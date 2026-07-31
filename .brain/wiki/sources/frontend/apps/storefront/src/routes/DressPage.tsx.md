---
tags: [frontend, storefront, route, react, gallery, media, accessibility]
sources: [frontend/apps/storefront/src/routes/DressPage.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/routes/DressPage.tsx
blob: 511446a6cc3d10dd88c5448b70031d361028053b
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/storefront/src/routes/DressPage.tsx

**Role.** `/dress/{id}` — one dress: gallery (or monogram) beside a facts column of name, price, clamped description, size badges, share and the bound booking CTA. Four states: loading, `notFound`, `failed`, loaded.

**Module.** [[frontend/apps/storefront/src/routes/_index]] · **Layer.** api

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `DressPage` | component | `{dressId}` — the decoded path segment from `matchRoute` |
| `DressPageProps` | interface | |

## Behavior

`loadError` is a two-value discriminant, not a boolean: `"notFound"` is the archived / unknown / foreign-tenant 404, which the wire makes indistinguishable **on purpose**, and `"failed"` is everything else. The distinction drives the recovery — the failed state offers a retry button, the not-found state offers only the back link, because retrying a 404 just repeats it and an archived dress is gone for good.

`document.title` is set to the dress name in an effect (WCAG 2.4.2, Level A): without it two dresses are indistinguishable in a tab strip, in history and in a bookmark. This is the one route that overrides the router's title, and it is safe because the router sets `document.dress` as a placeholder and re-runs on **every** navigation, so this can only upgrade the current route's title and can never be inherited by the next.

Two refs guard the same failure class in opposite directions. `retried` caps presigned-URL recovery at one refetch — a stale URL is fixed by refetching, an object that is genuinely gone re-fails on the fresh URL, and without the ceiling that pair loops the endpoint forever. A second effect resets `retried` on `dressId` change, because the component **never unmounts between two `/dress/:id` routes**, so a different dress would otherwise inherit a spent budget.

Gallery images are **filtered then numbered**: a null URL (no bucket, or a signing failure) must not consume a position, or the spoken "תמונה 2 מתוך 5" stops matching what the visitor can page through. Each `alt` is the **position**, not the dress name — eight identical strings give a screen-reader user no way to tell the photos apart, while the thumbnails already announce position correctly. (The *card's* alt stays the dress name; that is F9's contract and §6/§8 bind it.) With no usable image at all, [[frontend/apps/storefront/src/components/Monogram.tsx]] renders the boutique's initial instead, falling back to the dress name if the boutique block failed too.

`latinOnlyName` wraps a Latin-script-only name in `<span dir="ltr">`; a name containing any Hebrew is left bare, because forcing LTR on Hebrew is itself a bidi defect. Size badges pair the visual `variant` with an `sr-only` availability word — availability signalled by colour alone fails WCAG 1.4.1.

The `identity` `<h1>` (boutique name, `catalog.essenceFallback` when unknown) is rendered by the loading and both error states so the page always has exactly one heading for the skip link; on the loaded state the dress name becomes the `<h1>` instead.

## Depends On

- [[frontend/apps/storefront/src/api.ts]] — `api.getDress`, `isNotFound`, `errorMessageOr`, `StorefrontDetail`
- [[frontend/apps/storefront/src/components/StorefrontLayout.tsx]] — `useBoutique`
- [[frontend/apps/storefront/src/components/DescriptionClamp.tsx]] · [[frontend/apps/storefront/src/components/Monogram.tsx]] · [[frontend/apps/storefront/src/components/ShareButton.tsx]] · [[frontend/apps/storefront/src/components/BookingCTAButton.tsx]]
- [[frontend/apps/storefront/src/router.tsx]] — `Link`
- [[frontend/packages/ui/src/components/Gallery.tsx]] · [[frontend/packages/ui/src/components/Badge.tsx]] · [[frontend/packages/ui/src/components/Price.tsx]] · [[frontend/packages/ui/src/components/Skeleton.tsx]] · [[frontend/packages/ui/src/components/Button.tsx]]
- [[React]] · [[i18next]]

## Depended On By

- [[frontend/apps/storefront/src/router.tsx]] — the `/dress/{id}` route

## Concepts

- [[Media Storage]]
- [[Accessibility Compliance]]
- [[RTL And Bidi Isolation]]

## Tests

- [[frontend/apps/storefront/src/__tests__/DressPage.test.tsx]]
- [[frontend/apps/storefront/src/__tests__/accessibility.test.tsx]] · [[frontend/e2e/storefront.spec.ts]]

## Notes

The back arrow is `→`, not `←`: in RTL the way back points inline-start-to-end, i.e. rightwards. Same glyph choice in [[frontend/apps/storefront/src/routes/BookPage.tsx]]. The facts column only becomes sticky at the widest step — below that the gallery is short enough that sticky would fight the scroll.
