---
tags: [frontend, storefront, react, fallback, decoration]
sources: [frontend/apps/storefront/src/components/Monogram.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/components/Monogram.tsx
blob: 329e4750d4b5e3ddd7ab123bcace3ccb0c7cdb34
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/storefront/src/components/Monogram.tsx

**Role.** The dress detail page's no-photo art: the **boutique's** first character in the display serif, on paper, inside a gold hairline at a 3:4 aspect box.

**Module.** [[frontend/apps/storefront/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `Monogram` | component | `{boutiqueName}` — decorative placeholder where the `Gallery` would be |

## Behavior

It takes the **boutique** name, not the dress name, and that differs on purpose from `DressCard`'s built-in monogram, which uses the dress name's first character. A card is one of many in a grid where the dress name is what distinguishes it from its neighbours; the detail page is the boutique's own room, and repeating the dress name as decorative art directly beside the `<h1>` that already says it adds nothing.

`aria-hidden="true"` because the adjacent `<h1>` carries the name — this is decoration with no informational content. No `<img>` element is emitted at all, so there is no broken-image glyph to degrade into. `data-testid="dress-monogram"` is the hook the detail-page tests use to assert the no-photo branch.

## Depends On

Nothing. No imports — a plain styled `<div>` over theme tokens (`border-gold`, `bg-surface`, `font-display`, `text-gold`).

## Depended On By

- [[frontend/apps/storefront/src/routes/DressPage.tsx]] — the only consumer, rendered when no media item has a usable URL; falls back to `dress.name` if the boutique block itself failed

## Concepts

- [[Design Tokens]]
- [[Media Storage]]

## Tests

- [[frontend/apps/storefront/src/__tests__/DressPage.test.tsx]]

## Notes

`charAt(0)` on a Hebrew name yields the first Hebrew letter, which is the intended result; there is no direction handling because a single decorative glyph has no bidi run.
