---
tags: [frontend, storefront, test, vitest, accessibility, layout, footer]
sources: [frontend/apps/storefront/src/__tests__/StorefrontLayout.test.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/__tests__/StorefrontLayout.test.tsx
blob: 3c2033b5d3584b2c58b7d740b2545d85f33e94ca
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/storefront/src/__tests__/StorefrontLayout.test.tsx

**Role.** The contract test for the shell every storefront route renders inside: that the skip link's fragment resolves to the *same* `<main>` the router focuses, that the statutory footer links appear on every route, that the whole app issues exactly **one** `getBoutique()`, and that the two fixed overlays (the booking CTA bar and the A11yMenu trigger) have their footprint reserved on an element **outside** `<main>`.

**Module.** [[frontend/apps/storefront/src/__tests__/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `LoadProbe` | component | renders the layout's own `useBoutique()` load state as an `<h2>`, so every test awaits a settled fetch through the accessibility tree rather than a bare microtask flush |
| `renderAt(pathname, body)` | helper | sets `window.history` state, stubs `fetch` with a canned `BoutiqueResponse`, renders the layout around `LoadProbe`, returns the fetch mock |
| `settled(body)` | helper | `findByRole("heading", {name: body.name})` — proof the single fetch resolved *and* the context propagated |
| `pageShell()` / `footer()` / `a11yMenuRoot()` | helper | the three elements the footprint assertions read; `pageShell` is `getByRole("main").parentElement` and throws rather than returning null |
| `BOUTIQUE` / `BARE_BOUTIQUE` | fixture | a tenant with phone + Instagram, and a brand-new tenant with neither |
| `skip link and focus target` | suite | `href="#content"`, and `document.getElementById(target)` **is** the real `<main>` |
| `footer` | suite | about + accessibility-statement links on four routes; contact links; the bare-tenant degradation |
| `the shared boutique fetch` | suite | one call, to `/storefront/boutique`, feeding both consumers |
| `fixed CTA bar footprint` / `A11yMenu footprint over the footer (PRE-2)` / `A11yMenu lift` | suite | the three class-token reservations, per route |

## Behavior

The focus test does not stop at asserting the attributes. It resolves the skip link's fragment through `document.getElementById` and asserts identity with `getByRole("main")` — a renamed id leaves the link jumping nowhere and the router's post-navigation `focus()` landing on `null`, and both halves would still pass an attribute-only check. It then calls `main.focus()` and reads `document.activeElement`, because `tabindex="-1"` present-but-ignored is the actual failure mode.

**The footprint suites assert class tokens, not geometry, and that is deliberate — jsdom has no layout.** They check that `pageShell()` (the element wrapping *both* `<main>` and `<footer>`) carries `--cta-bar-height` on exactly the two routes with a fixed booking bar, that `<main>` itself never does, and that the reservation is width-scoped (`max-md:`) so desktop gets no dead gutter. The `<footer>` must carry `--space-a11y-footprint` on **every** route, because the A11yMenu trigger is `fixed` at the block-end inline-end corner everywhere and the footer is the last thing in the document — scrolled to the end it paints over the statutory הצהרת נגישות link. A literal `pb-8` is explicitly banned by regex (`/\bpb-\d/`): that is how `/about` once shipped an 8-unit pad against a 60px footprint. The real measurement lives in the PRE-2 geometry test in [[frontend/e2e/a11y.spec.ts]]; this file is the cheap structural half.

The route matrices are the interesting data. `/book/slot` and `/book/verify/d1` reserve **no** CTA footprint and take **no** A11yMenu lift: putting a "book a fitting" CTA inside the booking flow it leads to is the inverse mistake (spec Risk 6). `/about` ships a static inline button and `/accessibility` ships none, so lifting the menu there would float it over content that reserved for the unlifted trigger only.

The bare-tenant footer test asserts not just that no `tel:` or `instagram.com` link renders, but that exactly **one** `·` remains. Each contact link owns the separator before it, so an orphan bullet is precisely how a missing field leaks visually even when the link itself is correctly omitted.

`resetBoutiqueCache()` runs in both `beforeEach` and `afterEach` because `getBoutiqueOnce()` memoises at module scope — without it the "one fetch" assertion would pass for free on every file after the first, and the `BARE_BOUTIQUE` render would silently reuse the previous tenant's data.

## Depends On

- [[frontend/apps/storefront/src/components/StorefrontLayout.tsx]] — the subject: `StorefrontLayout`, `useBoutique`
- [[frontend/apps/storefront/src/api.ts]] — `resetBoutiqueCache`, the `BoutiqueResponse` wire type
- [[frontend/apps/storefront/src/i18n/index.ts]] — label lookup; queries go through `i18n.t(...)`, never a hardcoded Hebrew string
- [[Testing Library]] · [[Vitest]] · [[React]]

## Depended On By

Nothing imports a test file. [[frontend/apps/storefront/src/__tests__/router.test.tsx]] names this file in a comment as the owner of the `<main id="content" tabindex="-1">` assertion, and reproduces the element itself rather than pulling the layout's boutique fetch into a router test.

## Concepts

- [[Accessibility Compliance]]
- [[Accessibility Compliance]]

## Notes

The footprint tokens (`--cta-bar-height`, `--space-a11y-clearance`, `--space-a11y-footprint`) are matched as **substrings of `className`**, so they pin the token name and not the computed value; renaming a token in the theme without updating this file gives a red suite, which is the intent. The A11yMenu root is found via `trigger.parentElement`, which couples this suite to the `@boutique/ui` `A11yMenu` markup shape — a wrapper element added inside that component would break these tests without any storefront change.
