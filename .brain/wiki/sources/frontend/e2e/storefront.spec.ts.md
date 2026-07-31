---
tags: [frontend, e2e, playwright, axe, accessibility, wcag, rtl, hebrew, booking, storefront, fixtures]
sources: [frontend/e2e/storefront.spec.ts]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/e2e/storefront.spec.ts
blob: 956b5c050a77cf07cac662fd784dc4f8909d1f21
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/e2e/storefront.spec.ts

**Role.** The storefront's whole journey suite in one file: it fulfils every `/storefront/*` request from an in-file fixture, then drives the real built app through the catalog, the dress detail, `/about`, `/accessibility`, the five-step `/book/*` flow and the tokenized `/b/{token}` manage page — asserting axe A/AA cleanliness, **measured** layout geometry, keyboard order, document titles and the exact POST bodies that reach the wire. It is the only test in the repo that can see anything a browser has to compute: overlap between fixed elements, grid column counts, clipped text, real focus movement.

**Module.** [[frontend/e2e/_index]] · **Layer.** test

## Public Surface

Nothing is exported. The file's structure is a fixture block, a helper block, then roughly forty `test(...)` cases in six groups.

| Symbol | Kind | Purpose |
|---|---|---|
| `installApi` | helper | one `page.route("**/storefront/**")` that answers boutique, dresses, detail and the nine booking/manage endpoints; takes a `ListVariant` (`populated` \| `empty` \| `paged`), a boutique override and per-endpoint reply queues |
| `bookingFixture` / `take` | helper | each booking endpoint is a **queue** of replies consumed in order with the last entry repeating — one mechanism serves both mid-flow conflicts (terms v3→v4, booking 409→201) |
| `gotoSettled` | helper | per-route "the data landed" tell, so no axe scan runs against a skeleton |
| `walkBooking` | helper | the forward pass through all five booking steps with an `atStep` hook fired after each render; every booking test is this walk with a different hook |
| `axeViolations` | helper | axe `wcag2a`+`wcag2aa`, flattened to `rule — selectors` instead of ~10 KB of internals |
| `expectNotClipped` · `intersectionArea` · `bottomBarRect` · `inlineStartGap` · `horizontalOverflow` · `focusState` · `tabTo` | helpers | the measurement kit: clipping, rect overlap, bar-ness, direction-agnostic offsets, overflow, focus location, keyboard-only traversal |
| `photo` / `PHOTOS` | fixture | inline 3:4 SVG data URIs — they render, they decode, and they cannot 404 |

## Behavior

**Everything is fixture-driven, and the header explains why that is the opposite choice from [[frontend/e2e/a11y.spec.ts]].** Under `vite preview` there is no backend, so the app falls into its error state on every route; the grid, the gallery, the hours card and the CTA bar only exist once data lands, which is why the real screens are testable only from a fixture. The five dresses are chosen so one populated list exercises every card variant at once: a 3-photo priced dress, a price-hidden one (`price_agorot: null` — the number is absent server-side, not hidden in CSS), a `reserved` one, a photo-less one that must fall back to a monogram, and one with a name long enough to wrap an `h1` twice at 375. `ARCHIVED_ID` has no detail entry, so an unknown id, an archived dress and another tenant's dress are all one 404 on the wire — as designed.

**The measurement tests are the ones no component test can replace.** PRE-1 asserts zero intersection between the [[frontend/packages/ui/src/components/A11yMenu.tsx]] trigger and the [[frontend/packages/ui/src/components/BookingCTA.tsx]] bar at 375 — measured, because the original defect was a `--space-a11y-clearance` token that *looked* right while the rects still overlapped. `bottomBarRect` is the precondition, not a nicety: two boxes both in the wrong place trivially fail to intersect, so the bar must first be proven flush to the bottom edge and full-width. PRE-2 walks **every** `footer a`, not only the statutory הצהרת נגישות link, because the footer wraps at 375 and whichever link lands last is the one under the trigger — and it finishes with `link.click({ trial: true })`, which runs Playwright's hit-target check and fails on a covered link. `inlineStartGap` states offsets relative to the *inline-start* edge rather than "right", so the skip-link assertion survives the document ever flipping to LTR.

**The title/focus/scroll walk is entered by clicking, deliberately.** In a Vite SPA the served `<title>` is `index.html`'s forever unless something rewrites it per navigation, and a mount-time write covers for a router that never retitles again — while axe's `document-title` rule is satisfied by the stale one. So all four routes are reached by clicking, with a `window.__sameDocument` marker that survives `pushState` and dies on a reload proving no document swap happened, plus assertions that focus landed on `#content` and the viewport reset to 0.

**The `/book/*` flow is a state machine, not five URLs.** D8's guard bounces any step past `slot` with no picked time back to `slot`, so `details`, `terms` and `verify` are unreachable by `page.goto` and every scan has to arrive by walking — hence one `walkBooking` with a per-step hook, reused by the axe pass, the overflow sweep, the CTA-bar count and the Tab-order probe. The two mid-flow conflict tests are the richest: a `409 SLOT_UNAVAILABLE` returns her to a **freshly re-fetched** grid with the taken time gone (the fixture answers a *different* slot list the second time, so a UI that never re-fetched would fail), her chosen type and typed name survive, and `otpSends` is asserted to still be **1** — the failed claim rolled its own token burn back, so re-verifying would spend one of five hourly sends to re-prove what the server never un-proved. A `409 TERMS_STALE` re-renders v4's text and numbers, and the consent checkbox is unchecked *by construction* (`accepted` is `acceptedVersion === terms.version`) rather than by an effect someone remembered to write.

**Times are asserted in the boutique's calendar, never the device's.** The slot constants are `2099-01-04T08:00:00Z` and friends: Jerusalem is UTC+2 in January, so the grid must read `10:00`. The year 2099 keeps every assertion independent of today, of a TTL and of the machine's clock.

**F16's `/b/{token}` page is asserted on the wire shape as much as the screen**: all three calls (`lookup`, `confirm-attendance`, `cancel`) are POSTs whose body is exactly `{token}`, and each test additionally asserts the token never appears in the pathname — a GET would put a bride's manage token in a query string, in logs and in a Referer header. Cancel is a two-step reveal, and the reveal is asserted **not** to have called the cancel endpoint.

The suite also pins several negative contracts: `"אזל"`, `"out of stock"`, `"quantity"` and `"מלאי"` must never reach the storefront body (manage-only vocabulary); a hidden price renders "מחיר בתיאום" with no `₪` anywhere; the confirmation may not contain `"היחיד"`, `"SMS"` or `"מסרון"` — it may not promise a message the product may not send. And the `TEXT_RESIZE_BROKEN_AT_375` array is now **empty**: two WCAG 1.4.4 overflows (the Gallery thumbnail strip's 368px min-content, the footer's unbreakable `<bdi>` Instagram handle) used to live there as expected failures and are both fixed, so every route is held to the same bar.

## Depends On

- [[Playwright]] — `test`, `expect`, `Page`, `Locator`, `page.route` (entity)
- [[axe-core]] — `AxeBuilder` (entity)
- [[frontend/e2e/playwright.config.ts]] — the :4173 preview server and the `he-IL` locale
- [[frontend/apps/storefront/src/router.tsx]] — the routes, the focus-to-`#content` contract and the per-route title
- [[frontend/apps/storefront/src/routes/CatalogPage.tsx]] · [[frontend/apps/storefront/src/routes/DressPage.tsx]] · [[frontend/apps/storefront/src/routes/AboutPage.tsx]] · [[frontend/apps/storefront/src/routes/AccessibilityPage.tsx]] · [[frontend/apps/storefront/src/routes/BookPage.tsx]] · [[frontend/apps/storefront/src/routes/ManageBookingPage.tsx]]
- [[frontend/apps/storefront/src/components/StorefrontLayout.tsx]] — the skip link, `<main id="content" tabindex="-1">`, `hasBookingBar()`
- [[frontend/packages/ui/src/components/A11yMenu.tsx]] · [[frontend/packages/ui/src/components/BookingCTA.tsx]] · [[frontend/packages/ui/src/components/Gallery.tsx]] · [[frontend/packages/ui/src/components/DressGrid.tsx]] · [[frontend/packages/ui/src/components/DressCard.tsx]] · [[frontend/packages/ui/src/components/SlotPicker.tsx]]
- [[backend/app/storefront/schemas.py]] — the fixture bodies are hand-written copies of these wire models

## Depended On By

- [[.github/workflows/ci.yml]] — the `e2e` job
- [[Makefile]] — the `e2e` target

## Concepts

- [[Accessibility Compliance]] — IS 5568 / WCAG 2.0 AA is legally required here, so these scans gate the merge
- [[Jerusalem Time]] — every rendered time is Jerusalem-zoned; the fixture's UTC instants are chosen to make that visible

## Notes

**The fixture is a hand-maintained mirror of [[backend/app/storefront/schemas.py]] and nothing checks the two agree.** The file already carries the scar: the boutique fixture had to go **flat** when `BoutiqueResponse` did, because the hours adapter walks `boutique.hours` and an `undefined` there throws out of render — a blank page, not a degraded one. A field renamed on the backend will keep this suite green and break production.

Two selectors are structural rather than semantic and will break quietly if the styling changes: `CTA_BAR = ".z-40"` (the one z-index BookingCTA owns — A11yMenu, Toast and SkipLink are `z-50`) and `page.locator(".grid").first()` for the column count. Both are documented in-file as deliberate, but neither is a role or a test id.

The tests interleave under `fullyParallel`, and each installs its own routes — there is no shared server state to corrupt, but also no ordering guarantee to lean on.
