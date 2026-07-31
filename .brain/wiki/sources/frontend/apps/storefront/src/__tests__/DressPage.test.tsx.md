---
tags: [frontend, storefront, test, vitest, dress-detail, gallery, presigned-urls, headings, document-title]
sources: [frontend/apps/storefront/src/__tests__/DressPage.test.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/__tests__/DressPage.test.tsx
blob: ec3780625c94d7b436d7af97bae474797444f597
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/storefront/src/__tests__/DressPage.test.tsx

**Role.** The dress-detail suite: the always-present way back, the gallery's position-based image names, the facts column (price, sizes in words, the reserved-but-still-bookable CTA), the description clamp's ARIA wiring, the archived-dress branch, the sole-`<h1>` invariant in four states, and the document title as a WCAG 2.4.2 obligation.

**Module.** [[frontend/apps/storefront/src/__tests__/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `BOUTIQUE` | const | a profile whose name starts with a **different letter** than the dress's, so the monogram test can tell which name rendered |
| `dress()` / `photo(url)` | helpers | `StorefrontDetail` and a `StorefrontMedia` whose `url` may be `null` |
| `imageOf(n, total)` | helper | the `gallery.imageOf` string the main photo's alt must equal |
| `renderDress(dressId)` / `renderLoaded(detail)` | helpers | mount inside the layout; the latter awaits the `<h1>` **and then flushes effects** |
| `stubMetrics(scrollHeight, clientHeight)` | helper | defines both on `HTMLElement.prototype` so the clamp can measure overflow |

## Behavior

`renderLoaded` ends with a bare `await act(async () => {})`, and the comment says exactly why: `findBy*` resolves on the first commit, *before* the passive effects that commit scheduled have run, and `DescriptionClamp` decides whether to show its toggle inside one of them — without the flush the clamp assertions race the measurement. `ApiError`, `isNotFound` and `errorMessageOr` are left real, because the archived-dress branch and the "never render the server's English message" rule are what half the file asserts.

**The gallery's accessible names are positions, never the dress name.** Three photos all called «ורד» give a screen-reader user three identical strings with no way to tell them apart, so the main image is `gallery.imageOf` and the thumbnails are `alt=""` decoration — which is why `getAllByRole("img")` is expected to have length 1. Numbering happens *after* dropping media whose signed URL was never issued: `[photo(null), photo(url)]` renders "1 of 1", because an unusable photo consuming a position makes the spoken count stop matching what she can page through. The stale-URL path refetches exactly once and then stops, so a genuinely deleted object cannot start a loop. With no media at all the page draws the **boutique's** initial (asserted by `data-testid`, since the monogram is `aria-hidden` decoration next to an `<h1>` that already says the name) and contains zero `<img>` elements.

Small, load-bearing assertions in the facts column: a Latin-only dress name carries `dir="ltr"` so RTL cannot mangle it; an unavailable size states its unavailability **in words** inside its own `<li>` rather than by dimming alone; and the reserved dress keeps a working CTA whose `href` is `/book/slot/d1` — checked as an attribute with the comment that jest-dom's `toBeEnabled()` applies only to form elements and asserts *nothing* on an `<a>`, and that the dress id must be a path **segment** because the navigation store snapshots pathname only and cannot see a query string.

The clamp block asserts the toggle's `aria-controls` resolves to a real element containing the description (a dangling id is invisible in the page and useless to assistive tech), that `aria-expanded` flips and the id is stable across the flip, and — with the same stub set to no overflow — that a fitting description gets no toggle, which is what makes it a test of the measurement rather than of jsdom's zeros.

Both 404 and 400 land on the same "this dress is unavailable" copy with a way back and **no retry**: retrying either just repeats it. A 500 does get a retry, and the test drives it through to a successful reload. Every failure branch also asserts the server's English string is absent.

Two further blocks are invariants rather than features. **One `<h1>` inside `<main>` in every state** — pending, archived, 5xx, loaded — falling back to the boutique's name when there is no dress to name, hand-asserted because `page-has-heading-one` is best-practice and axe passes a heading-less page. And the **document title**, which must become the dress name (so two dresses are not one entry in browser history) yet must stay the router's static placeholder when there is no dress to name.

## Depends On

- [[frontend/apps/storefront/src/routes/DressPage.tsx]] — the subject
- [[frontend/apps/storefront/src/components/StorefrontLayout.tsx]] — imported directly; supplies the boutique context
- [[frontend/apps/storefront/src/api.ts]] — `ApiError`/`isNotFound`/`errorMessageOr` real; `api` and `getBoutiqueOnce` mocked
- rendered through the subject, not imported here: [[frontend/apps/storefront/src/components/DescriptionClamp.tsx]] · [[frontend/packages/ui/src/components/Gallery.tsx]] · [[frontend/packages/ui/src/components/Price.tsx]]
- [[frontend/apps/storefront/src/i18n/index.ts]]
- [[Testing Library]] · [[Vitest]]

## Depended On By

Nothing imports a test file.

## Concepts

- [[Media Storage]] · [[Hebrew RTL Bidi]] · [[IS 5568 Accessibility]]

## Notes

`afterEach` deletes the `scrollHeight`/`clientHeight` definitions off `HTMLElement.prototype` — they are defined on the *shared* prototype (unlike [[frontend/apps/storefront/src/__tests__/DescriptionClamp.test.tsx]], which scopes them to paragraphs), so leaking them would make every element in later files look overflowing.
