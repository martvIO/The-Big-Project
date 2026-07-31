---
tags: [frontend, storefront, route, react, catalog, pagination, degradation]
sources: [frontend/apps/storefront/src/routes/CatalogPage.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/routes/CatalogPage.tsx
blob: 24cd72b350c0e669f357374222320913d05e4b0e
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/storefront/src/routes/CatalogPage.tsx

**Role.** `/` — the boutique's collection. Identity header from the layout's shared fetch, the dress grid from this route's own paged read, and five mutually exclusive body states (identity-failed, list-failed, loading, empty, grid). Two independent failure domains is the design: a dress list that 503s or 429s must not take a boutique that answered down with it.

**Module.** [[frontend/apps/storefront/src/routes/_index]] · **Layer.** api

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `CatalogPage` | component | `{now?}` — injectable clock for the closed-today line |
| `CatalogPageProps` | interface | |

## Behavior

`api.listDresses()` runs in a mount effect keyed on an `attempt` counter, with a `cancelled` flag. **Load-more is a separate path** with its own `unmounted` ref guard, because it resolves outside the mount effect's cancellation scope. Paging advances by `dresses.length` — the number of items already held — rather than a page counter, so a concurrent insert cannot make the button skip a row; the server pins the page at 24, so without this button dress 25 of the pilot's ~60 is unreachable and E2's third success criterion fails. A failed "more" page **keeps the dresses already on screen** and shows the error inline beneath the grid: losing the whole grid because page two timed out is the worse outcome.

`retryAll` retries **both** surfaces. The boutique block is fetched once by [[frontend/apps/storefront/src/components/StorefrontLayout.tsx]], so a retry that only re-ran the dress list would leave a failed identity failed forever and the button would look live while doing nothing — this is the reason `BoutiqueState.retry` exists at all.

When the boutique failed, **one** alert speaks, not two: identity and list have almost certainly failed together (same outage), and announcing it twice makes a screen reader read two messages for one problem, so the identity failure is the headline and the list error is suppressed. Both error bodies are `text-ink-muted`, never danger — a backend that is down is not the boutique's fault. `BoutiqueHeader` still renders in the failed state with `catalog.essenceFallback`, because the degraded page must keep exactly one `<h1>` for the skip link to land on.

The empty state is hand-rolled rather than using `EmptyState`: the design's empty catalog is an identity moment whose headline is ink-**muted** (it reports a temporary absence, it is not the page's voice), while `EmptyState` pins its title to ink for the console's in-card empties. It carries `HoursCard` and `ContactCard` along so the boutique still feels complete on the day it goes live before a single photo is uploaded.

`handlePhotoError` reloads the list once — a stale presigned URL is fixed by refetching, but an object that is genuinely gone re-fails on the fresh URL, so `photoRetried` caps it at one refetch per page load or it would loop forever. `price_agorot === null` covers both "hidden" and "never set"; the storefront cannot tell them apart by design and renders both as the same-height agreed-price label so the grid never jumps.

## Depends On

- [[frontend/apps/storefront/src/api.ts]] — `api.listDresses`, `errorMessageOr`, `StorefrontDress`
- [[frontend/apps/storefront/src/components/StorefrontLayout.tsx]] — `useBoutique` (including `retry`)
- [[frontend/apps/storefront/src/components/HoursCard.tsx]] · [[frontend/apps/storefront/src/components/ContactCard.tsx]] · [[frontend/apps/storefront/src/components/BookingCTAButton.tsx]]
- [[frontend/apps/storefront/src/lib/hoursText.ts]] — `todayLine` for the header one-liner
- [[frontend/packages/ui/src/components/BoutiqueHeader.tsx]] · [[frontend/packages/ui/src/components/DressCard.tsx]] · [[frontend/packages/ui/src/components/DressGrid.tsx]] · [[frontend/packages/ui/src/components/Price.tsx]] · [[frontend/packages/ui/src/components/Skeleton.tsx]] · [[frontend/packages/ui/src/components/Button.tsx]]
- [[React]] · [[i18next]]

## Depended On By

- [[frontend/apps/storefront/src/router.tsx]] — the `/` route, and the fallthrough for every unmatched path (the design ships no 404 page)

## Concepts

- [[Accessibility Compliance]]
- [[Media Storage]]
- [[Jerusalem Time]]

## Tests

- [[frontend/apps/storefront/src/__tests__/CatalogPage.test.tsx]]
- [[frontend/e2e/storefront.spec.ts]] — asserts the single `<h1>` survives a failed identity fetch

## Notes

The fixed CTA bar's footprint is reserved by the layout's page shell, not here — a reservation inside `<main>` cannot clear the `<footer>` that sits outside it. See [[.planning/design/qa-checklist.md]] §7 and [[.planning/specs/storefront-browse.md]].
