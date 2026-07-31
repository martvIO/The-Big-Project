---
tags: [frontend, ui, test, vitest, catalog, media, accessibility, motion-tokens]
sources: [frontend/packages/ui/src/__tests__/catalog-composites.test.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/__tests__/catalog-composites.test.tsx
blob: e6b0f36df4efea75bd7468d688a79dac207b673c
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/__tests__/catalog-composites.test.tsx

**Role.** The largest test file in the package: the full image-lifecycle contract for the three catalog components — [[frontend/packages/ui/src/components/DressCard.tsx]], [[frontend/packages/ui/src/components/DressGrid.tsx]] and [[frontend/packages/ui/src/components/Gallery.tsx]]. Its through-line is that **a photo load failure means an expired presigned URL, not a missing photo**, so every image path must report the error upward instead of degrading.

**Module.** [[frontend/packages/ui/src/__tests__/_index]] · **Layer.** test

## Contract Pinned

**`DressCard`** — reserved badge renders and the card is **not** dimmed (`opacity-50` absent from the markup: reserved is information, not deactivation); `photoUrl={null}` emits **no `<img>` at all** while the name stays readable (the monogram is `aria-hidden`); `alt` is taken from the dress name; a cached image (`HTMLImageElement.prototype.complete` stubbed `true`) shows at `opacity-100` on first paint rather than staying stuck invisible; an uncached one starts `opacity-0` and reaches `opacity-100` on `load`; the fade uses `duration-(--motion-base)` + `ease-out` (qa §6 — a bare `transition-opacity` would inherit Tailwind's own default duration and curve, neither a project token); `onImageError` fires exactly once on `error`, does not throw when omitted, and is **never** called when there is no `<img>` to fail; grid photos carry `loading="lazy"` and `decoding="async"`.

**`DressGrid`** — one assertion: the root className contains `grid`.

**`Gallery`** — a single-image gallery hides prev/next chrome entirely; the lone image carries **both** `min-w-0` and `max-w-full`; the thumbnail scroller carries `p-2`; prev/next are keyboard-reachable buttons and thumbnails expose `aria-current="true"` when selected; `onImageError` fires from the main image, from a thumbnail, and from a single-image gallery's lone image, and is safe when unsupplied; the main image is **eager** while every thumbnail is `loading="lazy"`.

## Behavior

Two `Gallery` assertions carry reasoning that is not recoverable from the code and is the most valuable thing in this file. The `min-w-0` / `max-w-full` pair exists because on the dress page the lone image *is* the grid item, and a grid item's default `min-width: auto` resolves to a replaced element's **intrinsic** width — so a wide photo pushes the document sideways at 200% text zoom no matter how `w-full` is written, breaking WCAG 1.4.10 reflow. The Playwright reflow spec only ever visits a three-photo dress, so this branch is invisible to it; the unit test is the only guard. Separately, the thumbnail strip's `p-2` is there because a specified `overflow-x: auto` forces `overflow-y` to `auto` too, clipping anything painted outside the border box — which is exactly where the 2px focus ring at 2px offset and the `aria-current` outline live. Padding on all four sides is the fix; `outline-offset: 0` is not. Both assertions use anchored regexes (`/(^| )p-2( |$)/`) so a substring like `p-24` cannot satisfy them.

The eager-main / lazy-thumbnails split is a deliberate asymmetry: the dress page's hero image is the LCP element and must not be deferred, while the strip below the fold should be. The `DressCard` counterpart is the opposite (all lazy) because the grid renders up to 24 unprocessed originals — the heaviest egress path in v1.

The cached-image test stubs a **prototype getter** (`vi.spyOn(HTMLImageElement.prototype, "complete", "get")`) and restores it inline. jsdom never loads images, so `complete` is otherwise always `false` and the warm-reload branch — the `useEffect` that sets `loaded` when `imgRef.current?.complete` — would be dead code under test. Leave the `mockRestore()` in place; it is not scoped to an `afterEach`.

## Depends On

- [[frontend/packages/ui/src/components/DressCard.tsx]] — subject
- [[frontend/packages/ui/src/components/DressGrid.tsx]] — subject
- [[frontend/packages/ui/src/components/Gallery.tsx]] — subject
- [[Vitest]] — runner, `vi.spyOn` (entity)
- [[Testing Library]] — `render` / `fireEvent` / `screen` (entity)

## Depended On By

- nothing — a leaf test

## Concepts

- [[Media Storage]]
- [[Design Tokens]]
- [[Accessibility Compliance]]

## Tests

- this *is* the test

## Notes

**Stale cleanup hook.** The file ends with a top-level `afterEach` that strips five `data-a11y-*` attributes from `document.documentElement`, commented "A11yMenu writes to document.documentElement; keep tests isolated" — but this file neither imports nor renders [[frontend/packages/ui/src/components/A11yMenu.tsx]]. It is a leftover from a split; harmless (it removes attributes nothing here sets) but misleading. The live version of that hook belongs with whichever suite actually mounts `A11yMenu`.

`Gallery`'s labels arrive as a `labels` prop object including an `imageOf(n, total)` formatter — the package has no i18next dependency and never will; every string is caller-supplied. Bidi isolation of the dress name is covered separately in [[frontend/packages/ui/src/__tests__/DressCard.bidi.test.tsx]].
