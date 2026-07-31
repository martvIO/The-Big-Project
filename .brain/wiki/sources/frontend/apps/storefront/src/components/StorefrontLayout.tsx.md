---
tags: [frontend, storefront, react, layout, context, accessibility]
sources: [frontend/apps/storefront/src/components/StorefrontLayout.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/components/StorefrontLayout.tsx
blob: 2d8ed2133e7fbf0d15857c341b7ed6a76138d638
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/storefront/src/components/StorefrontLayout.tsx

**Role.** The app shell and the **single owner of the boutique fetch**: it calls `getBoutiqueOnce()` once for the whole app, publishes `{boutique, loading, error, retry}` through a context every route reads, and owns the chrome that no route can own — the skip link, the `<main tabindex="-1">` focus target, the footer with the statutory הצהרת נגישות link, the fixed `A11yMenu`, and the block-end space reservations that keep the two fixed elements off that footer.

**Module.** [[frontend/apps/storefront/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `StorefrontLayout` | component | `{children}` — mounts **above** the Router in `App.tsx`, so `/book/*` already renders inside the shell |
| `useBoutique` | hook | reads `BoutiqueState`; the only sanctioned access to the shared boutique block |
| `BoutiqueState` | interface | `{boutique, loading, error, retry}` |

## Behavior

One `useEffect`, keyed on an `attempt` counter, drives the fetch and records **both** outcomes into a single `fetched` object. The rejection is deliberately stored rather than dropped: a route can only degrade honestly if the failure is observable, and a swallowed rejection makes "failed" and "still loading" visually identical forever. `retry` clears the module-level cache via `resetBoutiqueCache()` and bumps `attempt` — it is load-bearing, because the fetch runs once on mount and without it a route rendering a retry button for a failed boutique would have nothing to change, leaving the button permanently inert. [[frontend/apps/storefront/src/routes/CatalogPage.tsx]] is the caller that needs it.

`hasBookingBar(route)` is the layout's other cross-cutting fact: **only `catalog` and `dress`** carry the fixed CTA bar. It feeds two things. The page shell gets `max-md:[padding-block-end:calc(var(--cta-bar-height)+env(safe-area-inset-bottom))]`, and the reservation must live on this div — which wraps `<main>` **and** `<footer>` — because `<footer>` is a *sibling* of `<main>`, so a reservation inside a page component cannot clear the הצהרת נגישות link (qa §7 / PRE-2). And `A11yMenu` receives `hasBookingBar` so its fixed trigger is lifted where there is a bar (PRE-1) and **not** lifted where there is none — claiming a bar on `/about` or `/accessibility` would float the trigger 92px over content that reserved nothing for it.

The footer carries its own `[padding-block-end:var(--space-a11y-footprint)]` for the A11y trigger's own footprint, written as `pt-6` plus a logical property rather than `py-6` plus an override, because `cn` has no tailwind-merge and both rules would ship. `footerLinkClass` combines `min-w-0` with `[overflow-wrap:anywhere]` for WCAG 1.4.10 reflow: an Instagram handle and a phone number are single unbreakable Latin tokens, and at 200% text-only zoom on 375px they push the whole document sideways without it — `anywhere` rather than `break-word` because only `anywhere` breaks a token with no break opportunity. Both are wrapped in `<bdi dir="ltr">`, correct here because both values genuinely are Latin/digit runs. The footer is links only; the storefront ships no nav component, and `/about` and `/accessibility` are reachable from here and nowhere else.

The `oxlint-disable react/only-export-components` at the top is intentional: the provider, its hook and the shell are one unit, and moving the hook elsewhere would mean exporting the context object itself — a wider surface.

## Depends On

- [[frontend/apps/storefront/src/api.ts]] — `getBoutiqueOnce`, `resetBoutiqueCache`, `BoutiqueResponse`
- [[frontend/apps/storefront/src/router.tsx]] — `Link`, `MAIN_ID`, `matchRoute`, `usePathname`, `RouteMatch`
- [[frontend/packages/ui/src/components/A11y.tsx]] — `SkipLink`, `A11yStatementLink`
- [[frontend/packages/ui/src/components/A11yMenu.tsx]]
- [[frontend/packages/ui/src/lib/styles.ts]] — `cn`, `focusRing`
- [[frontend/packages/ui/src/tokens.ts]] — `--cta-bar-height`, `--space-a11y-footprint`, `--space-a11y-clearance`
- [[React]] · [[i18next]]

## Depended On By

- [[frontend/apps/storefront/src/App.tsx]] — mounts it around the Router
- Every route, via `useBoutique`: [[frontend/apps/storefront/src/routes/CatalogPage.tsx]], [[frontend/apps/storefront/src/routes/DressPage.tsx]], [[frontend/apps/storefront/src/routes/AboutPage.tsx]], [[frontend/apps/storefront/src/routes/AccessibilityPage.tsx]], [[frontend/apps/storefront/src/routes/BookPage.tsx]], [[frontend/apps/storefront/src/routes/ManageBookingPage.tsx]]

## Concepts

- [[Accessibility Compliance]]
- [[IS 5568 Accessibility]]
- [[Design Tokens]]
- [[Hebrew RTL Bidi]]

## Tests

- [[frontend/apps/storefront/src/__tests__/StorefrontLayout.test.tsx]]
- [[frontend/apps/storefront/src/__tests__/accessibility.test.tsx]] · [[frontend/e2e/a11y.spec.ts]]

## Notes

`hasBookingBar` is duplicated knowledge with [[frontend/apps/storefront/src/components/BookingCTAButton.tsx]]'s `inline` prop — the layout decides the *reservation*, the button decides the *bar*. They must be changed together; `/about` passing `inline` while the layout claimed a bar (or the reverse) is exactly the PRE-1/PRE-2 pair.
