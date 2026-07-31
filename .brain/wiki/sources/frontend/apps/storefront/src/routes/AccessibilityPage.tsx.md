---
tags: [frontend, storefront, route, react, accessibility, legal, is-5568]
sources: [frontend/apps/storefront/src/routes/AccessibilityPage.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/routes/AccessibilityPage.tsx
blob: 176ee01ab92d6df66e433c5d0d5d3473d28e598a
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/storefront/src/routes/AccessibilityPage.tsx

**Role.** `/accessibility` — הצהרת נגישות, the statutory accessibility statement. IS 5568 §35 makes this page *and a named, reachable contact inside it* a legal obligation for a public Israeli site, so it is written to be read by a screen reader and audited by a person: one h1, an h2 per section, real `<ul>`/`<dl>` structure, and no content that exists only as visual arrangement.

**Module.** [[frontend/apps/storefront/src/routes/_index]] · **Layer.** api

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `AccessibilityPage` | component | no props; reads the boutique block from context |
| `Bullets` | component (module-private) | `{items}` — maps a key tuple to `<li>`s |

## Behavior

**The responsible party is the boutique**, not the platform operator: it is the service provider, and its own phone and Instagram come from the layout-level fetch. There is deliberately no operator-coordinator layer, because a statement declaring conformance while showing «fill this in» *is* the non-conformance it declares against.

It has **no loading state and no error state**, which is the page's most important property: a statement page that renders a spinner or an error instead of the statement is itself the accessibility failure it exists to declare. The boutique block only ever *upgrades* it — the name replaces `catalog.essenceFallback`, the phone and Instagram add reachable channels.

The three bullet groups (`DONE_KEYS`, `MENU_KEYS`, `LIMIT_KEYS`) are `as const` tuples of **whole** i18n keys, never suffixes composed at render time: a key assembled from a fragment is invisible to the static i18n-keys guard, and i18next answers a miss with the bare key, so a renamed entry would print ASCII into the statement.

The coordinator block is a `<dl>` rather than paragraphs — the label/value pairing is what a screen reader announces and what an auditor looks for by name. A row with no value is **never** rendered: a `<dt>` with nothing behind it is a dead statutory contact, which §35 does not allow. When the boutique published neither channel the whole list is replaced by a `statement.coordinatorNoChannel` sentence, and the reporting `<ul>` below is omitted rather than rendered empty (a bare `<ul>` announces as an empty list). Phone and handle are wrapped in `<bdi dir="ltr">` — both are genuine LTR runs dropped into RTL prose.

`pb-16` clears the fixed A11yMenu trigger's 60px footprint (a 44px button offset by `--space-4`), which this route carries with no CTA bar beneath it to reserve the space — `hasBookingBar()` is deliberately false here.

## Depends On

- [[frontend/apps/storefront/src/components/StorefrontLayout.tsx]] — `useBoutique`; also the source of the footer link that reaches this page
- [[frontend/packages/ui/src/components/SectionHeading.tsx]] · [[frontend/packages/ui/src/lib/styles.ts]] (`cn`, `focusRing`)
- [[i18next]] — every string on the page, `statement.*` plus two `contact.*` keys

## Depended On By

- [[frontend/apps/storefront/src/router.tsx]] — the `/accessibility` route
- [[frontend/packages/ui/src/components/A11y.tsx]] — `A11yStatementLink` points here from the footer

## Concepts

- [[Accessibility Compliance]]
- [[Accessibility Compliance]]
- [[RTL And Bidi Isolation]]

## Tests

- [[frontend/apps/storefront/src/__tests__/accessibility.test.tsx]]
- [[frontend/apps/storefront/src/__tests__/i18n-keys.test.ts]] — the guard the whole-key rule exists for
- [[frontend/e2e/a11y.spec.ts]]

## Notes

`statement.updated` is a static translated string, not a computed date — if the statement's content changes, that key must be edited by hand.
