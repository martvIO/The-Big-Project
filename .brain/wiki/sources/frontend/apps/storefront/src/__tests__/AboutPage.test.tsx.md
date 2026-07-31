---
tags: [frontend, storefront, test, vitest, about, opening-hours, jerusalem, headings]
sources: [frontend/apps/storefront/src/__tests__/AboutPage.test.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/__tests__/AboutPage.test.tsx
blob: 898dff8080ab56863ed49dd3a364c45f3f69305d
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/storefront/src/__tests__/AboutPage.test.tsx

**Role.** The trust-surface suite: load/failure states, the sole-`<h1>` invariant in every one of them, the opening-hours week (grouping, the day the wire omits, the lunch break), the exceptions list, the address-without-a-map case, and the fact that `/about` ships one inline booking CTA and no fixed bar.

**Module.** [[frontend/apps/storefront/src/__tests__/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `getBoutiqueOnce` | `vi.hoisted` mock | the **only** thing faked — the layout's single boutique fetch |
| `boutique(patch)` | helper | a full profile, Sun–Thu 10:00–19:00 |
| `renderAbout(children)` | helper | wraps the route in [[frontend/apps/storefront/src/components/StorefrontLayout.tsx]] |
| `hoursRows()` | helper | `[rowheader, cell]` text pairs for every row `HoursTable` emitted |
| `THURSDAY` / `SUNDAY` | const | fixed instants, injected as the route's `now` prop |

## Behavior

The route is exercised *through the layout* rather than with a per-route fetch stub, because everything on `/about` comes from the one layout-level `getBoutiqueOnce()` — mocking a fetch the route no longer makes would test nothing. Only that function is replaced; `ApiError` and the error-message mapper stay real, so the Hebrew failure copy asserted is the copy production renders, and the same assertion pins that the server's English (`"Service Unavailable"`) never reaches the page.

**`now` is a prop, never `Date.now()`.** The suite runs under `TZ=America/New_York` on purpose, and both fixtures are chosen as Jerusalem calendar days (`2026-12-24T10:00:00Z` is a Thursday there). Exception dates are asserted as `25.12`, not `12.25` — the wire value is already a Jerusalem calendar date and must not be re-zoned.

The hours suite is the substantive part. One test gives Sun–Fri six *different* closing times so nothing can group, and requires seven rows keyed by the seven day labels in order, with Saturday — which has no rule on the wire at all — rendering the literal closed label rather than a blank cell or a dropped row. A second test proves the grouper keys on **adjacency**, not on the window set: with Tuesday missing, `א׳–ב׳` and `ד׳–ה׳` must be separate ranges and `א׳–ה׳` must not appear anywhere, because that string would advertise the boutique as open on a day it is shut. A third renders a lunch-break day as two `<bdi>` runs in the same row *and* as one comma-joined "today" line, which is what fails under a one-window-per-day model. The fourth separates "no rules published" from "closed today": a brand-new tenant has entered nothing, and announcing a closure it never declared turns a blank profile into a shut door.

A dedicated describe block asserts **exactly one `<h1>` inside `<main>` in all three states** — pending, failed, loaded — carrying the brand fallback until the boutique's own name arrives. The comment states why it is hand-written: axe passes a heading-less page, since `page-has-heading-one` is best-practice rather than A/AA, and the `<h1>` is where the skip link lands.

Two smaller traps are recorded in place. The address-without-`maps_url` test uses `closest("a")`, **not** `queryByRole("link")`, because an `<a>` with no `href` has no link role and the role query would pass on the very defect it guards. The CTA test asserts the raw `href` attribute is the absolute `/book/slot`, because the router's delegated click handler pushes `anchor.getAttribute("href")` rather than the resolved `.href`, so a relative value would be pushed verbatim; it also isolates the fixed booking bar as `.fixed.inset-x-0` so the (fixed, but not full-width) accessibility menu does not false-positive.

## Depends On

- [[frontend/apps/storefront/src/routes/AboutPage.tsx]] — the subject
- [[frontend/apps/storefront/src/components/StorefrontLayout.tsx]] — supplies the boutique context and the CTA slot
- [[frontend/apps/storefront/src/api.ts]] — `ApiError` real, `getBoutiqueOnce` mocked
- [[frontend/apps/storefront/src/i18n/index.ts]] — every asserted string is a production key
- [[frontend/packages/ui/src/components/HoursTable.tsx]] — the table whose rows `hoursRows()` reads
- [[Testing Library]] · [[Vitest]]

## Depended On By

Nothing imports a test file.

## Concepts

- [[Jerusalem Time]] · [[RTL And Bidi Isolation]] · [[Accessibility Compliance]]

## Notes

`beforeEach` rewrites the URL to `/about` — the layout reads the path to decide whether a fixed booking bar is claimed, and the default `/` would put the page in the catalog's shape. The grouping logic itself lives in [[frontend/apps/storefront/src/lib/hoursText.ts]] / [[frontend/packages/ui/src/lib/hours.ts]] and has its own unit suites; this file asserts the rendered week.
