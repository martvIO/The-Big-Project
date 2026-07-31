---
tags: [frontend, storefront, test, vitest, router, accessibility, focus-management]
sources: [frontend/apps/storefront/src/__tests__/router.test.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/__tests__/router.test.tsx
blob: 2fff3d06e38c40677b477751bd8cd1a015700b16
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/storefront/src/__tests__/router.test.tsx

**Role.** The contract test for the hand-rolled router: `matchRoute`'s full path table (including the closed booking-step set and the `/b/{token}` manage link), `Link` and the document-level click delegation deciding what to intercept, and the post-navigation trio of document title, focus into `#content`, and scroll reset.

**Module.** [[frontend/apps/storefront/src/__tests__/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `renderRoute(pathname, extra)` | helper | pushes the path, renders `<Router/>` inside a locally-built `<main id={MAIN_ID} tabIndex={-1}>`, optionally with extra anchors the router never rendered |
| `navigateAndFlush(to)` | helper | `act(() => navigate(to))` — `navigate` drives an external store, and the assertion reads `document.title` / `activeElement` after effects |
| `primeScroll(offset)` | helper | supplies the `scrollY` + `scrollTo` jsdom does not implement, so "returned to the top" can actually fail |
| `matchRoute` | suite | catalog/about/accessibility, `/dress/:id`, `/b/:token`, `/book/:step/:dressId`, fallbacks |
| `usePathname` | suite | re-renders on `popstate` and on a programmatic navigate |
| `Link` / `root click delegation` | suite | plain left click intercepted; modifier clicks, hash links, `tel:`, `target=_blank`, `rel=external` left alone |
| `Router document title, focus and scroll` | suite | per-route title, one title for the whole booking flow and one for manage, no focus theft on first paint |

## Behavior

Every route component is `vi.mock`ed to a bare string. That is the point: this file is about the router's own contract, and rendering the real pages would drag their fetches in and re-test them a second time.

`matchRoute`'s table encodes several decisions worth reading off it. There is **no 404 page** — anything unmatched falls through to the catalog, which is why `/nope`, `/dress`, `/dress/a/b` and `/book/d1` all resolve to `{name: "catalog"}`. Ids are percent-decoded but a malformed escape must **not throw**: a hand-typed `/dress/%` returns the literal `%` rather than blanking the page. Trailing slashes are ignored everywhere.

**The manage route is the one place the catalog fallthrough must *not* win.** `/b/anything-at-all` matches, unknown token and all, because the page owns the invalid-link state (spec D7/D8) — swallowing a rotated token into a dress grid leaves a bride with no explanation. The token charset test accepts `[A-Za-z0-9_-]` because that is what `token_urlsafe` emits, and a route choking on `-` or `_` would break roughly half of all generated links. `/b` bare and `/b/tok/extra` do fall back. The path is short on purpose (spec D7): the URL rides inside a UCS-2 Hebrew SMS where every character is segment budget.

The booking step set is **closed** (`BOOK_STEPS`), and the test spells out why that matters: with a closed set there is no `/book/{dressId}` shape for a dress id to be ambiguous with. A bare `/book` opens on `slot`.

The delegation suites cover anchors the router never rendered, because `DressCard` emits a raw `<a href>` and takes no `onNavigate` prop — the grid can only go client-side through the document-level listener. Interception is asserted through `fireEvent.click`'s return value (`false` means `preventDefault()` ran). Three non-interceptions are load-bearing: a **hash-only link is the skip link**, and calling `preventDefault()` there means the browser never performs the fragment navigation, focus never reaches `#content`, and the WCAG skip-link behaviour breaks silently with a green unit suite; `tel:` belongs to the OS dialer; `target="_blank"` and `rel="external"` belong to the browser.

The title suite pins one title for the **entire** booking flow and one for **all six** manage states, with `not.toBe("document.book")` guards catching an unresolved i18n key echoing itself back. The per-step reasoning is recorded in the file: React flushes a child's passive effects before its parent's, so a per-step title written inside `BookPage` would lose the race to the router's own effect anyway. A separate case pins that a dress name the detail page wrote into the title (WCAG 2.4.2) is **replaced** on the next hop rather than sticking, and another asserts the manage token never appears in `document.title`.

Focus is asserted in both directions: **not** stolen on first paint (the skip link is the first stop), and moved to `#content` on a client navigation together with the retitle and `scrollY === 0`. The scroll assertion only has teeth because `primeScroll` supplies what jsdom lacks — without it `scrollY` is `0` forever and the check could never fail.

## Depends On

- [[frontend/apps/storefront/src/router.tsx]] — the subject: `BOOK_STEPS`, `Link`, `MAIN_ID`, `Router`, `matchRoute`, `navigate`, `usePathname`
- [[frontend/apps/storefront/src/i18n/index.ts]] — the `document.*` titles
- [[Testing Library]] · [[Vitest]] · [[React]]

## Depended On By

Nothing imports a test file. It deliberately reproduces the `<main id="content" tabindex="-1">` that [[frontend/apps/storefront/src/components/StorefrontLayout.tsx]] really owns; the identity of that element with the skip link's target is asserted in [[frontend/apps/storefront/src/__tests__/StorefrontLayout.test.tsx]], so the two files together cover the full path.

## Concepts

- [[Accessibility Compliance]]

## Notes

Because the route components are mocked, this suite says nothing about what any page renders — the `/b/{token}` states live in [[frontend/apps/storefront/src/__tests__/ManageBookingPage.test.tsx]] and the booking steps in [[frontend/apps/storefront/src/__tests__/BookPage.test.tsx]]. `navigate()` is asserted to push with a `null` history state, so nothing in the app may start depending on `history.state` without updating this file.
