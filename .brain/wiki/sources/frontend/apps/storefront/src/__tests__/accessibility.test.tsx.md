---
tags: [frontend, storefront, test, vitest, accessibility, is-5568, legal, hebrew]
sources: [frontend/apps/storefront/src/__tests__/accessibility.test.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/__tests__/accessibility.test.tsx
blob: 407ca5e67a1bf16e7a7d638a1baa6b44727665ba
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/storefront/src/__tests__/accessibility.test.tsx

**Role.** The audit suite for הצהרת נגישות — the accessibility statement page. It guards what an IS 5568 §35 auditor actually checks: real document semantics, the standard named precisely, one entry per tool the A11yMenu ships, the limitations admitted rather than denied, a *reachable* complaints contact, and a review date — plus the degradation ladder for a boutique that published no contact channel at all.

**Module.** [[frontend/apps/storefront/src/__tests__/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `renderStatement()` | helper | renders `AccessibilityPage` inside the real `StorefrontLayout`, waits for the boutique name, returns `{...utils, main}` — **every query is scoped to `main`** |
| `PLACEHOLDER_TEXT` | const | `/[«»]\|TODO\|FIXME\|למילוי\|fill.me/i` — the *class* of defect, not the one string that caused it |
| `MENU_KEYS` | const | the five A11yMenu controls the statement must document one-for-one |
| `document semantics` | suite | exactly one `h1`, no skipped heading level, real `<li>` lists |
| `the required parts` | suite | conformance declaration, menu inventory, limitations, alt-text honesty, review date, no unfilled placeholder |
| `the complaints contact` | suite | both channels · phone-only · no channel · boutique fetch rejected |

## Behavior

**The `main`-scoping is load-bearing, not tidiness.** The layout's own footer and A11yMenu carry the same phone number and the same tool labels, so an unscoped `getAllByRole("link", {name: phone})` would count chrome as if the statement had rendered it, and every count assertion would pass for free.

The module partially mocks `../api` — `importActual` keeps `ApiError` and the real types, while `api` and `getBoutiqueOnce` become spies — so each case can drive the identity fetch to a different outcome without touching `fetch`. `renderStatement()` waits on the boutique's *name* specifically, because the fetch only **upgrades** this page: it renders in full without it, so waiting on anything the statement would draw either way is not a wait at all.

Two assertions exist purely to stop a vacuous pass. The heading-ladder test permits climbing back up any distance and only forbids descending by more than one — a rule a flat `h1 + h2` page satisfies trivially — so it also asserts the levels **contain a 3**. And the placeholder guard checks link *shape*, not just marker absence: any `mailto:` must match a real address and any `tel:` a real number, because a placeholder written without guillemets ("TODO-fill-me") passed the older guillemet-only guard while still rendering a dead `mailto:`.

**The alt-text case is the sharpest one and does not read the statement against itself.** It renders the real [[frontend/apps/storefront/src/routes/DressPage.tsx]] with a three-photo dress, reads the gallery's main-image `alt` off the render, and asserts `statement.limitsAlt` *contains* that string — plus that it no longer claims פעמיים (F10 replaced the dress-name alt with the position, so the name is no longer announced twice) while keeping the still-true half about the card's alt. A statement describing behaviour the site does not have is itself a compliance defect.

The contact ladder covers four tenant states. Both channels → each of phone and Instagram appears **twice** (the `<dl>` contact row and the reporting-channels list), the phone link wrapping a `<bdi dir="ltr">` because a phone number is a strong-LTR digit run inside RTL prose. Phone only → exactly one `<dt>`, and every `<dt>` has a non-empty `<dd>` beside it: a labelled dead end is worse than an omission. No channel → **no `<dl>` and no `<dt>` at all**, and `statement.coordinatorNoChannel` names the boutique instead. Fetch rejected → the whole statement still renders with no `role="alert"`, the site name falls back to `catalog.essenceFallback` exactly **once** (it used to be reused as if it were a phone value, rendering a labelled row a visitor cannot ring), and the reporting list is omitted rather than emitted empty, since an empty `<ul>` announces as "list, 0 items".

## Depends On

- [[frontend/apps/storefront/src/routes/AccessibilityPage.tsx]] — the subject
- [[frontend/apps/storefront/src/components/StorefrontLayout.tsx]] — supplies `<main>` and the boutique context the statement reads
- [[frontend/apps/storefront/src/routes/DressPage.tsx]] — rendered for the alt-text cross-check
- [[frontend/apps/storefront/src/api.ts]] — `ApiError`, `getBoutiqueOnce` (mocked), the wire types
- [[frontend/apps/storefront/src/i18n/index.ts]] — every expected string
- [[Testing Library]] · [[Vitest]] · [[React]]

## Depended On By

Nothing imports a test file. The browser-level counterpart is [[frontend/e2e/a11y.spec.ts]], which runs axe against the rendered page; this suite covers the statutory *content* that axe cannot judge.

## Concepts

- [[IS 5568 Accessibility]]
- [[Accessibility Compliance]]
- [[RTL Bidi Isolation]]

## Notes

The file's header states the compliance stance that shapes every assertion: **the responsible party is the boutique**, not a platform operator — there is no coordinator layer, and the complaints contact is the tenant's own phone and Instagram off the layout-level fetch. That is why a tenant with no published channel is a first-class tested state rather than an edge case. Note also that the newly-provisioned-tenant case and the failed-fetch case converge: the page ships no error state, so `phone: null` covers both.
