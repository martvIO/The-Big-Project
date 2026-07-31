---
tags: [frontend, storefront, react, routing, accessibility, wcag]
sources: [frontend/apps/storefront/src/router.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/router.tsx
blob: eb9a57752199c20b2bfd61b05e48f3b4a96473d0
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/storefront/src/router.tsx

**Role.** The entire routing layer of the public site, hand-rolled: a pure `matchRoute` path→`RouteMatch` function, a `useSyncExternalStore` binding over `history`, a `navigate()` with an explicit push/replace contract, a `<Link>`, **one delegated document-level click listener**, and the per-route `<title>` + focus + scroll effect that satisfies WCAG 2.4.2. **The workspace carries no router dependency** — this file is the reason.

**Module.** [[frontend/apps/storefront/src/_index]] · **Layer.** app shell

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `RouteName` | type | `"catalog" \| "dress" \| "about" \| "accessibility" \| "book" \| "manage"` |
| `BOOK_STEPS` | const | the closed five-step tuple; `BookStep` is its element type |
| `BookStep` | type | one of `BOOK_STEPS` |
| `RouteMatch` | type | discriminated union; carries `dressId`, `step`, `token` where relevant |
| `MAIN_ID` | const | the id of `StorefrontLayout`'s `<main tabindex="-1">`; also the `SkipLink` target |
| `matchRoute` | fn | pure `pathname → RouteMatch`; no side effects, directly unit-tested |
| `usePathname` | hook | `useSyncExternalStore` over `popstate` + a custom navigation event |
| `navigate` | fn | `(to, { replace? })` — pushes or replaces, then dispatches the event |
| `shouldIntercept` | fn | predicate: should this click become a client navigation? |
| `Link` / `LinkProps` | component | a real `<a href>` that upgrades a plain left click |
| `Router` | component | mounts the delegation listener, runs the navigation effect, switches on the match |

## Behavior

**Match order is a security-shaped decision, not a formality.** `/b/{token}` is tested **before** the catalog fallthrough, because an unknown or rotated token must reach [[frontend/apps/storefront/src/routes/ManageBookingPage.tsx]] and render its own invalid-link state rather than being silently swallowed into the collection. For the same reason the token is *not* validated here — the route is opaque-by-design. The `/b/` prefix is deliberately short: the URL rides inside a UCS-2 Hebrew SMS where every character is segment budget. `decodeId` catches a `URIError` from a stray `%` so a hand-typed URL 404s as a dress id instead of throwing out of render and blanking the page. Everything unmatched falls through to the catalog: the design ships no 404 page, and a stale Instagram-bio link should land on the dresses.

**The book route's two-segment pattern is only unambiguous because `BOOK_STEPS` is closed.** `/book/{step}` and `/book/{step}/{dressId}` share one regex; `isBookStep` is what guarantees no dress id can ever be read as a step. Bare `/book` opens on `"slot"`; an unknown step is not a step and falls through to the catalog with everything else.

**`navigate`'s `replace` flag has a documented single use: guard redirects.** A step that bounces the visitor off itself because it has nothing to work with must *replace*, or the back button is trapped — from `/book/confirm`, Back lands on `/book/verify`, the guard pushes `/book/confirm` again, and the catalog becomes unreachable by Back forever. A mid-flow recovery that takes her somewhere she can act stays a push. Because `pushState` fires no event of its own, `navigate` dispatches a custom `storefront:navigation` event; `subscribe` listens for that plus `popstate` (the browser's own back/forward).

**`shouldIntercept`'s exclusion list is the contract, not an optimisation.** Written loosely as "same-origin left click without modifiers" it would swallow `SkipLink` — a plain `<a href="#content">` — so `preventDefault()` would fire, the browser would never perform the fragment navigation, focus would never move, and the WCAG item the e2e suite asserts would silently fail. Hence the explicit bail-outs: modifier and non-primary clicks (storefront links get opened in new tabs constantly), `target` other than `""`/`_self`, `download`, `rel="external"`, any non-`http(s)` protocol (`tel:`, `mailto:`, `whatsapp:` belong to the browser), cross-origin, and hash-on-the-current-path. `Link` and the delegated listener share this one predicate so they can never drift.

**The document-level click delegation exists to route a component the app cannot modify.** `DressCard` in [[frontend/packages/ui/src/components/DressCard.tsx]] renders a raw `<a href>` and takes no `onNavigate` prop; delegation is what turns the whole grid into client navigation without reopening a gate-passed `packages/ui` component or giving it a routing dependency.

**The navigation effect is the WCAG 2.4.2 (Level A) implementation.** It sets `document.title` from `DOC_TITLE_KEYS` through `t()`, then — only on a real path change — scrolls to the top and moves focus to `#content`. `handledPath` is a ref keyed on the *path* rather than a boolean, so React 19 StrictMode's double-invoked effect cannot read as a navigation and steal focus. First paint is skipped on purpose: the browser owns focus there and the skip link is the first stop. Without the scroll reset a visitor who taps a card in grid row 5 lands on the dress page still scrolled to row 5.

**`DOC_TITLE_KEYS` is one title per `RouteName`, and the two coarse entries are deliberate.** All five booking steps share `document.book` because [[frontend/apps/storefront/src/routes/BookPage.tsx]] must not write its own title — React flushes a child's passive effects before its parent's, so this effect would run last and clobber a per-step title. All six manage states share `document.manageTitle` because the visitor arrived from a text message and an outcome ("cancelled") does not belong in the tab strip.

A side effect worth keeping: with no `back()` in the surface, the QA-checklist ban on history-based back navigation is structural rather than a grep.

## Depends On

- [[frontend/apps/storefront/src/routes/CatalogPage.tsx]], [[frontend/apps/storefront/src/routes/DressPage.tsx]], [[frontend/apps/storefront/src/routes/AboutPage.tsx]], [[frontend/apps/storefront/src/routes/AccessibilityPage.tsx]], [[frontend/apps/storefront/src/routes/BookPage.tsx]], [[frontend/apps/storefront/src/routes/ManageBookingPage.tsx]] — the six route targets
- [[React]] — `useEffect`, `useRef`, `useSyncExternalStore`
- [[i18next]] — `useTranslation`, for the document titles

## Depended On By

- [[frontend/apps/storefront/src/App.tsx]] — mounts `Router` inside the layout
- [[frontend/apps/storefront/src/components/StorefrontLayout.tsx]] — `Link`, `MAIN_ID`, `matchRoute`, `usePathname`
- [[frontend/apps/storefront/src/routes/DressPage.tsx]], [[frontend/apps/storefront/src/routes/BookPage.tsx]]
- [[frontend/apps/storefront/src/__tests__/router.test.tsx]], [[frontend/apps/storefront/src/__tests__/BookPage.test.tsx]]

## Concepts

- [[Accessibility Compliance]]

## Tests

- [[frontend/apps/storefront/src/__tests__/router.test.tsx]] — `matchRoute` cases and the interception predicate
- [[frontend/apps/storefront/src/__tests__/BookPage.test.tsx]] — the guard-redirect `replace` behaviour through the flow

## Notes

The file opens with `// oxlint-disable react/only-export-components` — the route table, `navigate()` and the two components are one unit, and splitting them to buy fast refresh on a one-screen file was judged not worth it. Ceilings the author names in the header comment: no scroll restoration, no code splitting, no route-level data loaders (pages fetch their own).
