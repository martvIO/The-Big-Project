---
tags: [frontend, manage, branding, png, asset, ios]
sources: [frontend/apps/manage/public/apple-touch-icon.png]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/public/apple-touch-icon.png
blob: 9c7d1a33410761b27a1ee3ac8bd1e1ffcd7c8f4f
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/manage/public/apple-touch-icon.png

**Role.** The iOS home-screen icon: 180×180 PNG of the MODRYN monogram, and the **one brand raster that is deliberately opaque** — cream `#FDFBF7` with an ~11% inset, unlike the two transparent favicons beside it.

**Module.** [[frontend/apps/manage/public/_index]] · **Layer.** platform

## Behavior

The opacity is the whole point and the reason this file exists separately at all. iOS composites a transparent touch icon onto **black**, so shipping the transparent favicon at 180px would put gold on black on the home screen — off-brand and low-contrast. Baking the cream tile in avoids that; the file is RGB with no alpha channel, which is the mechanical confirmation. The 11% inset compensates for iOS's own rounded-rect mask cropping the artwork.

Like its siblings it was rendered once from [[assets/brand/modryn-mark.svg]] in headless Chromium. No committed script regenerates it, so re-tracing the mark leaves this file stale with nothing to catch it.

## Depended On By

- [[frontend/apps/manage/index.html]] — `<link rel="apple-touch-icon" href="/apple-touch-icon.png">`

## Notes

Byte-identical to [[frontend/apps/storefront/public/apple-touch-icon.png]]. Cream `#FDFBF7` is the platform surface colour from the token set, so this raster hard-codes a design token — change the token and the icon does not follow.

Spec: [[.planning/specs/modryn-branding.md]].
