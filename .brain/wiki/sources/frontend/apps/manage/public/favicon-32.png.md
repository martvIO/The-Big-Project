---
tags: [frontend, manage, branding, png, asset, favicon]
sources: [frontend/apps/manage/public/favicon-32.png]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/public/favicon-32.png
blob: af30fa9d2f3f3368c1791efc48bbb905c39d61ac
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/manage/public/favicon-32.png

**Role.** The raster fallback tab icon: 32×32 RGBA PNG of the MODRYN monogram, for browsers that ignore `image/svg+xml` favicons. Declared alongside the SVG in [[frontend/apps/manage/index.html]] with an explicit `sizes="32x32"`.

**Module.** [[frontend/apps/manage/public/_index]] · **Layer.** platform

## Behavior

RGBA with a **transparent** background, matching [[frontend/apps/manage/public/favicon.svg]] — at 32px the flat gold `#C5A059` was verified to hold against cream, white, dark and mid-grey tab bars, and a cream tile would read as a white box on a dark one. Rendered from the one canonical SVG in headless Chromium as a one-off, not by any committed script or build step: nothing regenerates it, so a change to [[assets/brand/modryn-mark.svg]] leaves this raster silently stale.

## Depended On By

- [[frontend/apps/manage/index.html]] — `<link rel="icon" type="image/png" sizes="32x32">`

## Notes

Byte-identical to [[frontend/apps/storefront/public/favicon-32.png]]. Binary — the page can only be checked against the file's dimensions and colour model, never diffed.

Spec: [[.planning/specs/modryn-branding.md]].
