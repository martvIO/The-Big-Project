---
tags: [frontend, ui, react, catalog, accessibility, reflow, images]
sources: [frontend/packages/ui/src/components/Gallery.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/components/Gallery.tsx
blob: 788439e5b237a33cf22f41411378873ff0a02165
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/components/Gallery.tsx

**Role.** The dress detail page's photo viewer: one eager 3:4 hero image, prev/next buttons, and a horizontally scrollable thumbnail strip. It advances on user input only — no timer, no auto-advance, no carousel library — and it degrades to a bare `<img>` when there is exactly one photo, so the chrome never appears for a single-photo dress.

**Module.** [[frontend/packages/ui/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `Gallery` | fn | `{images, labels, onImageError?, className?}` |
| `GalleryImage` | type | `{url, alt}` |
| `GalleryLabels` | type | `{previous, next, imageOf(n, total)}` — every string, including the interpolated position, arrives from the app's i18n |
| `GalleryProps` | type | as above |

## Behavior

Three arities, three renders: an empty `images` array returns `null` outright; a single image returns one `<img>` with no buttons and no strip; two or more render the full viewer. Internal `index` state is clamped on read (`Math.min(index, images.length - 1)`), so a shorter `images` array arriving after a refetch cannot index past the end. Prev/next are `disabled` at the ends rather than wrapping, and each carries an `aria-label` from `labels`; every thumbnail button is labelled `labels.imageOf(i + 1, total)` and the active one sets `aria-current="true"`, which is how position is exposed to assistive tech — there is no live region and no visible counter.

**`min-w-0` appears three times and every one is a WCAG 1.4.10 reflow fix, not styling.** The gallery root and the single-image `<img>` are grid items on the dress page, and a grid item defaults to `min-width: auto` — which for a replaced element resolves to its *intrinsic* width, so a wide photo pushes the whole document sideways at 200% text zoom no matter what `w-full` says. On the thumbnail strip the same default is what stops `overflow-x-auto` from ever engaging: at 200% text the thumbs are ~112px each, min-content is ~368px, and on a 375px viewport the strip would scroll the document instead of itself. Removing any of the three re-introduces horizontal page scroll — a legal failure under IS 5568, not a cosmetic one.

The strip's `p-2` is padding on **all four sides, not `pb-2`**, and that is also an accessibility constraint: a specified `overflow-x: auto` forces `overflow-y` to `auto` as well, and both the focus ring and the `aria-current` outline paint 4px outside the border box (2px wide at 2px offset), so with no padding they are clipped on the block axis and, at the scroll origin, on the inline-start edge too. The fix is padding, never `outline-offset: 0`.

The hero `<img>` is deliberately **eager** — it is the detail page's LCP element, and adding `loading="lazy"` costs the largest paint directly. Thumbnails are lazy and `aria-hidden` with empty `alt` (their button carries the label, so announcing the image too would double-speak). `onImageError` fires from the hero, the single-image render *and* every thumbnail: the whole set is signed and expires together, so any one failure is the page's cue to refetch the presigned URLs rather than to hide one photo.

## Depends On

- [[frontend/packages/ui/src/lib/styles.ts]] — `cn`, `focusRing`
- [[React]] — `useState`

## Depended On By

- [[frontend/apps/storefront/src/routes/DressPage.tsx]] — the only app consumer
- [[frontend/packages/ui/src/index.ts]] — barrel re-export

## Concepts

- [[Accessibility Compliance]]
- [[Media Storage]]

## Tests

- [[frontend/packages/ui/src/__tests__/catalog-composites.test.tsx]] — single-image chrome suppression, thumbnail labelling, `aria-current`, eager hero, `onImageError` on every image

## Notes

Navigation glyphs are the literal characters `‹` and `›` inside buttons whose accessible name comes entirely from `aria-label` — the glyph is decorative and must not be replaced with translated text. There is no keyboard arrow-key handler: the buttons are natively focusable and that is the whole keyboard contract.
