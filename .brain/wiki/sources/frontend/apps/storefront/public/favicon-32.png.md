---
tags: [frontend, storefront, branding, favicon, png, static-asset, modryn]
sources: [frontend/apps/storefront/public/favicon-32.png]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/public/favicon-32.png
blob: af30fa9d2f3f3368c1791efc48bbb905c39d61ac
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: generated
applicability: active
---

# frontend/apps/storefront/public/favicon-32.png

**Role.** The 32×32 raster fallback favicon for browsers that will not take the SVG. Rendered from [[frontend/apps/storefront/public/favicon.svg]] in headless Chromium — no image dependency was added to the toolchain to produce it.

**Module.** [[frontend/apps/storefront/public/_index]] · **Layer.** platform / static asset

## Public Surface

Binary. 32×32, 8-bit RGBA, non-interlaced PNG, 1811 bytes.

## Behavior

**RGBA, and the alpha channel is the decision.** The background is transparent rather than cream: at 32px the gold mark was checked against cream, white, dark and mid-grey tab bars and holds on all four, whereas a cream tile reads as a white box on a dark tab. [[frontend/apps/storefront/public/apple-touch-icon.png]] is the one that goes the other way, and for a platform-specific reason.

Byte-identical to [[frontend/apps/manage/public/favicon-32.png]]. It is a *render* of the SVG, but nothing regenerates it — change the mark and this file stays at the old geometry until someone re-runs the render by hand, in both apps.

## Depends On

- [[frontend/apps/storefront/public/favicon.svg]] — the source geometry (by provenance, not by build)

## Depended On By

- [[frontend/apps/storefront/index.html]] — `<link rel="icon" type="image/png" sizes="32x32">`

## Notes

Spec: [[.planning/specs/modryn-branding.md]] (F30). `kind: generated` because it is machine-rendered output — `brain-scan.sh` skips this page unless run with `--all`.
