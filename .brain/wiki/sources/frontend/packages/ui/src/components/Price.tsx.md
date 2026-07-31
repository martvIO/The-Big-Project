---
tags: [frontend, ui, react, money, bidi, intl]
sources: [frontend/packages/ui/src/components/Price.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/components/Price.tsx
blob: c197c8eff58c5852b202792c29c563598c575f36
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/components/Price.tsx

**Role.** The **only** way money is rendered anywhere in the frontend. It converts agorot to shekels exactly once, formats with `he-IL` grouping, emits number-then-glyph (`5,900 ₪`) inside an LTR-isolated `<bdi>`, and swaps in a caller-supplied "price on request" label at the same slot and the same line height so a mixed grid never jumps.

**Module.** [[frontend/packages/ui/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `Price` | fn | `{agorot, visible, hiddenLabel, className?}` |
| `PriceProps` | type | as above; `agorot` is an integer, `hiddenLabel` is Hebrew supplied by the app's i18n |

## Behavior

Fraction digits are chosen from the value, not fixed: `agorot % 100 === 0` renders zero decimals, anything else renders two — so a round price reads `5,900 ₪` rather than `5,900.00 ₪`, and a 5,900.50₪ price is not silently truncated. The formatter is `Intl.NumberFormat("he-IL")` with **no `style: "currency"`**; the ₪ glyph is appended manually because the currency style would place and space the symbol per the locale's own rules rather than the design's number-then-glyph order.

The output is wrapped in `<bdi dir="ltr">` — correct here, and only here, because the run is **numeric**: digits plus a currency glyph must read left-to-right inside RTL page text. Hebrew free text takes a bare `<bdi>` instead; `dir="ltr"` on Hebrew is itself a bidi defect. The hidden branch returns early with the same-size `<span>` carrying `hiddenLabel`, unwrapped, and renders **no ₪ at all** — the test pins that absence.

`visible` is a plain boolean prop with no default, and the call sites all derive it the same way: `visible={item.price_agorot !== null}` with `agorot={item.price_agorot ?? 0}`. That is deliberate — the storefront API never ships a `price_visible` flag, so `null` covers both "the owner hid the price" and "no price was ever recorded", and the two are indistinguishable to the client by design (see [[backend/app/storefront/schemas.py]]). The `?? 0` is therefore dead weight the type system requires, never a rendered zero.

`frontend/scripts/qa-greps.sh` bans the ₪ glyph outright across `apps/storefront/src`, which is what makes "renders through `<Price>` and nowhere else" mechanically enforced rather than aspirational — the glyph lives in this package, outside the grep's path.

## Depends On

- [[frontend/packages/ui/src/lib/styles.ts]] — `cn`
- [[Intl API]] — `Intl.NumberFormat`

## Depended On By

- [[frontend/apps/storefront/src/routes/CatalogPage.tsx]] — passed as the `price` node into each [[frontend/packages/ui/src/components/DressCard.tsx]]
- [[frontend/apps/storefront/src/routes/DressPage.tsx]]
- [[frontend/apps/storefront/src/components/booking/TypePicker.tsx]] — appointment-type deposits
- [[frontend/apps/manage/src/components/CatalogSection.tsx]] · [[frontend/apps/manage/src/components/DressEditor.tsx]]
- [[frontend/packages/ui/src/index.ts]] — barrel re-export

## Concepts

- [[RTL Bidi Isolation]]

## Tests

- [[frontend/packages/ui/src/__tests__/hours-composites.test.tsx]] — the `5,900 ₪` format and the no-₪ hidden branch

## Notes

A new `Intl.NumberFormat` is constructed on every render rather than hoisted to a module constant. Harmless at catalog scale (24 cards), but it is the obvious optimisation if a long list ever profiles hot.
