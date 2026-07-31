---
tags: [frontend, ui, react, catalog, bidi, images, performance]
sources: [frontend/packages/ui/src/components/DressCard.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/components/DressCard.tsx
blob: 2b697116510bdae31482f502373b258df9ef8484
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/components/DressCard.tsx

**Role.** One catalog tile: a whole-card `<a>` wrapping a 3:4 photo well, an optional reserved badge, the dress name and a caller-supplied price element. It owns three things nothing else does — the fade-in that survives a warm reload, the no-photo monogram fallback that emits no `<img>` at all, and the `<bdi>` isolation that keeps a Latin dress name from corrupting the RTL card around it.

**Module.** [[frontend/packages/ui/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `DressCard` | fn | the tile; the entire card is the link target |
| `DressCardProps` | type | `{name, href, price, photoUrl?, reserved?, reservedLabel?, onImageError?, className?}` |

## Behavior

**`price` is a `ReactNode`, not a number** — the card never formats money. The caller passes a rendered [[frontend/packages/ui/src/components/Price.tsx]] element, which is what lets the storefront and the console feed the same card different visibility rules without this file learning about agorot. `reservedLabel` is likewise a prop: the package ships no Hebrew, so a `reserved` card with no `reservedLabel` renders **no badge at all** (both conditions are required) rather than an English fallback.

The photo has two paths and they are exclusive. With `photoUrl`, an `<img>` mounts `loading="lazy" decoding="async"` and starts at `opacity-0`, fading in on `onLoad`; a `useEffect` checks `imgRef.current?.complete` on mount so a browser-cached image that fired `load` before React attached the handler is not left permanently invisible. Lazy loading is deliberate and load-bearing — the grid renders up to 24 **unprocessed originals**, the heaviest egress path in v1. Without `photoUrl`, the monogram branch renders the dress name's first character in the display serif under `aria-hidden`, and **no `<img>` element is emitted**, so there is no broken-image glyph and no wasted request.

`onImageError` is not a "hide the photo" hook — it means *the presigned URL expired*. The page is expected to refetch the signed URLs rather than degrade the card to the monogram; a card that silently fell back would make an expiry indistinguishable from a dress with no photo. The 3:4 `aspect-ratio` well reserves the layout box before decode, so the grid scores CLS 0 whichever branch runs, and a reserved card is **never dimmed** — the badge is the only signal.

Two absences are intentional. `<bdi>` around `{name}` is **bare** — a Latin-only name like `Bella Rosa (Ivory)` is a bidi run whose trailing neutrals (the closing bracket, a full stop) otherwise reorder to the wrong end of an RTL line; forcing `dir="ltr"` here would break every Hebrew name instead, so the isolation is direction-agnostic by design. And the inline-end `<span aria-hidden className="size-11" />` is a **reserved layout box for save-for-later**, shipping in a later epic: no button, no icon, no client storage, and not in the tab order. It sits inline-*end* so it can never collide with the reserved badge on the inline-start.

## Depends On

- [[frontend/packages/ui/src/lib/styles.ts]] — `cn`, `focusRing`
- [[frontend/packages/ui/src/components/Badge.tsx]] — the reserved chip
- [[React]] — `useState`, `useEffect`, `useRef`

## Depended On By

- [[frontend/apps/storefront/src/routes/CatalogPage.tsx]] — the only app consumer
- [[frontend/packages/ui/src/index.ts]] — barrel re-export

## Concepts

- [[RTL Bidi Isolation]]
- [[Media Storage]]

## Tests

- [[frontend/packages/ui/src/__tests__/catalog-composites.test.tsx]] — lazy/decoding attributes, the monogram branch, `onImageError`, the reserved badge
- [[frontend/packages/ui/src/__tests__/DressCard.bidi.test.tsx]] — the bare-`<bdi>` contract

## Notes

The card's monogram uses the **dress** name's initial; the dress detail page's [[frontend/apps/storefront/src/components/Monogram.tsx]] deliberately uses the **boutique** name's initial instead, and that divergence is documented in its own docstring. Do not "unify" them.
