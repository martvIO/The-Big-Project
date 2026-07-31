---
tags: [frontend, storefront, test, vitest, catalog, pagination, presigned-urls, jerusalem, design-tokens]
sources: [frontend/apps/storefront/src/__tests__/CatalogPage.test.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/__tests__/CatalogPage.test.tsx
blob: 2fc2cd07b512b2a3333d318a4f8447e97ed314b6
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/storefront/src/__tests__/CatalogPage.test.tsx

**Role.** The landing page's suite: the four-way composition of two independent fetches (identity and collection) across loading/failure, load-more paging, the card states (priced, hidden price, reserved, photo-less), the one-shot refetch on a stale presigned URL, the go-live empty state, and the header's Jerusalem-zoned hours line.

**Module.** [[frontend/apps/storefront/src/__tests__/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `PAGE_SIZE` | const | 24 — the server-pinned page, against ~60 dresses in the pilot |
| `boutique()` / `dress()` / `listing()` | helpers | wire fixtures; `listing` builds the `{items, total, offset, limit}` envelope |
| `catalogue(size)` | helper | zero-padded names so «שמלה 25» is never a prefix of another card |
| `pending<T>()` | helper | a promise that never settles, holding a state open |
| `renderCatalog(now?)` | helper | route inside [[frontend/apps/storefront/src/components/StorefrontLayout.tsx]] |
| `FRIDAY_IN_JERUSALEM` / `SATURDAY_IN_JERUSALEM` | const | `2026-12-25T10:00:00Z` and `…T22:30:00Z` |

## Behavior

The module is spread rather than replaced: `ApiError`, the error-message mappers and `isNotFound` keep their real implementations, because the copy under test is chosen by **code mapping** and a stubbed mapper would assert nothing about it. Only `api.listDresses`, `api.getDress`, `api.getBoutique` and `getBoutiqueOnce` are spies.

Because identity and collection resolve independently, the loading matrix is a composition, and each cell is asserted for the *right* placeholder. A pending boutique must render **no `<h1>` at all** and not the fallback name — the fallback belongs to a *failed* boutique, not a pending one, and an `<h1>` here would claim an identity the tenant has not sent. A pending collection under a resolved header paints exactly six card skeletons. A failed collection keeps the boutique's real name, its today-line and the booking CTA, and renders in `text-ink-muted` rather than danger, since a backend that is down is not the boutique's fault. A failed *identity* keeps the `<h1>` carrying the fallback (the skip-link target; losing it drops a screen-reader user into an untitled region, which axe will not catch), and the retry is wired to both fetches — a retry bound only to the dress list would leave a failed identity failed forever.

The CTA assertion in that block is annotated as a deliberate strengthening: it checks `link` **with its `href`**, because the assertion it replaced (`queryByRole("button", …).toBeNull()`) became trivially true the moment the CTA turned into an anchor and would have gone on passing while the property it existed to prove went unverified.

Load-more asserts `listDresses` is called with the **count already held** (`24`), not a page counter, that page two appends rather than replaces, that the button disappears once `total` is reached, and — separately — that a failed page two keeps all 24 existing cards on screen, because losing the grid because page two timed out is the worse outcome. That test carries an explicit 15 s timeout with a comment justifying it: three pages and 50 cards make it the heaviest test in the suite, and it has twice exceeded the 5 s default on a loaded CI runner while every wait inside it is still a `findBy`/`waitFor` that resolves as soon as the DOM does.

The stale-URL test fires an `error` event on the `<img>`, requires exactly one refetch, then fires a second `error` on the fresh image and requires the count to stay at two — an object that is genuinely gone would otherwise re-sign, re-fail and loop. The photo-less card must contain **zero `<img>` elements** (a broken-image icon in a bridal grid is worse than the monogram) and a hidden-price card must contain no digit anywhere, so "the owner hid it" and "no price was ever set" are indistinguishable.

**Two colour assertions inject a real stylesheet built from `themeTokens`.** jsdom loads no CSS, so every class computes to the UA default and a naive colour check would pass whichever class the element carried; the tests paint `--color-ink`, `--color-ink-muted` and `--color-danger` onto probe spans, assert the two probes differ (guarding the guard against an inert stylesheet), and only then compare the element's computed colour.

The hours-line block is where the device clock is separated from the boutique's. `SATURDAY_IN_JERUSALEM` is still Friday in New York, so reading the device would render the named-reopening-day branch instead of "opens tomorrow" — the two tests are each other's control. A third requires the line to be **absent entirely** when the tenant has published no weekly rules: that is not "closed today", and a header reading "hours unknown" is worse than no line.

## Depends On

- [[frontend/apps/storefront/src/routes/CatalogPage.tsx]] — the subject
- [[frontend/apps/storefront/src/components/StorefrontLayout.tsx]] — the single boutique fetch and the CTA slot
- [[frontend/apps/storefront/src/api.ts]] — `ApiError` and the mappers real; four functions mocked
- [[frontend/packages/ui/src/tokens.ts]] — `themeTokens`, the source of the injected colours
- [[frontend/apps/storefront/src/i18n/index.ts]]
- [[Testing Library]] · [[Vitest]]

## Depended On By

Nothing imports a test file.

## Concepts

- [[Jerusalem Time]] · [[Media Storage]] · [[IS 5568 Accessibility]]

## Notes

The empty-state test filters `contact.call` links by `closest("dialog") === null`: the booking modal holds a second, closed `ContactPanel`, so an unfiltered query matches two. `beforeEach`/`afterEach` both reset the URL to `/` because the layout branches on pathname.
