---
tags: [frontend, storefront, route, react, trust, degradation]
sources: [frontend/apps/storefront/src/routes/AboutPage.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/routes/AboutPage.tsx
blob: 8d8085be545d0a4c96c117f23f443cdadf3a9435
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/storefront/src/routes/AboutPage.tsx

**Role.** `/about` — the trust surface (Flow S3: "אמיתי? שווה ביקור? מתי פתוח?"). Name, essence, linked address, story, hours, contact, and a booking CTA, as one editorial column that never goes multi-column at any width. It owns no fetch of its own: everything comes from `useBoutique()`.

**Module.** [[frontend/apps/storefront/src/routes/_index]] · **Layer.** api

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `AboutPage` | component | `{now?}` — three states: loading, boutique-failed, loaded |
| `AboutPageProps` | interface | injectable clock, same seam as `HoursCard` |

## Behavior

The address is the one thing this page renders that no shared primitive owns — `ContactPanel` has no address slot, and `BoutiqueHeader` (which owns the linked-address treatment) is the *catalog's* h1. `safeHref(boutique.maps_url)` runs the tenant-supplied URL through the scheme allowlist, so a stored `javascript:` value degrades to plain text instead of executing; React does not neutralise a `javascript:` href on its own. Note the deliberate bidi asymmetry: the address takes a **bare `<bdi>`**, not `dir="ltr"`, because it is tenant text that may be Hebrew or Latin, and forcing LTR on Hebrew is itself a defect.

The `identity` `<h1>` is hoisted out and rendered by **all three** states, with `catalog.essenceFallback` when the name is unknown. The `<h1>` is where the skip link lands, so a page whose only heading vanishes on an API error drops a screen-reader user into an untitled region — and axe cannot catch it, `page-has-heading-one` being best-practice rather than an A/AA rule, so it is asserted in tests instead. The catalog header and the accessibility statement use the same fallback.

The failed state renders `errorMessageOr(error, t, "about.error")` as `role="alert"` in muted ink plus a reload button, and **deliberately no contact card**: the phone, WhatsApp number and Instagram handle all come from the block that just failed, so there is nothing left to offer and the panel would print empty rows.

This is the **only** storefront screen with no fixed booking bar at any width (qa §7), which is why the CTA is `<BookingCTAButton inline />` — nothing moves at 768. `hasBookingBar()` in [[frontend/apps/storefront/src/components/StorefrontLayout.tsx]] must agree; claiming a bar here would lift the A11y trigger over content that reserved nothing for it (PRE-2).

## Depends On

- [[frontend/apps/storefront/src/components/StorefrontLayout.tsx]] — `useBoutique`
- [[frontend/apps/storefront/src/components/HoursCard.tsx]] · [[frontend/apps/storefront/src/components/ContactCard.tsx]] · [[frontend/apps/storefront/src/components/BookingCTAButton.tsx]]
- [[frontend/packages/ui/src/lib/url.ts]] — `safeHref`
- [[frontend/packages/ui/src/components/SectionHeading.tsx]] · [[frontend/packages/ui/src/components/Skeleton.tsx]] · [[frontend/packages/ui/src/components/Button.tsx]]
- [[frontend/apps/storefront/src/api.ts]] — `errorMessageOr`, `BoutiqueResponse`
- [[i18next]]

## Depended On By

- [[frontend/apps/storefront/src/router.tsx]] — the `/about` route

## Concepts

- [[Accessibility Compliance]]
- [[RTL And Bidi Isolation]]
- [[Jerusalem Time]]

## Tests

- [[frontend/apps/storefront/src/__tests__/AboutPage.test.tsx]]
- [[frontend/apps/storefront/src/__tests__/accessibility.test.tsx]] · [[frontend/e2e/storefront.spec.ts]]

## Notes

The retry here is `window.location.reload()`, not the context's `retry` — unlike the catalog, which needs `retryBoutique()` because it has a second surface to keep alive. See [[.planning/specs/storefront-browse.md]].
