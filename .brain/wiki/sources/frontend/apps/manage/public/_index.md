---
tags: [frontend, typescript]
sources: [frontend/apps/manage/public]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/public
blob: 6bd7782c882163ce28f9a136744b11ae4c5c32e7
commit: 13d107b8b16f1f2676f1cdb1c994f95822fe2ba0
kind: directory
applicability: active
---

# frontend/apps/manage/public/

**Purpose.** Static assets served as-is.

**Parent.** [[frontend/apps/manage/_index]]

## Files

- [[frontend/apps/manage/public/apple-touch-icon.png]] — The iOS home-screen icon: 180×180 PNG of the MODRYN monogram, and the **one brand raster that is deliberately opaque** — cream `#FDFBF7` with an ~11% inset, unlike the two transparent favicons beside it.
- [[frontend/apps/manage/public/favicon-32.png]] — The raster fallback tab icon: 32×32 RGBA PNG of the MODRYN monogram, for browsers that ignore `image/svg+xml` favicons. Declared alongside the SVG in [[frontend/apps/manage/index.html]] with an explicit `sizes="32x32"`.
- [[frontend/apps/manage/public/favicon.svg]] — The console's primary tab icon — the MODRYN monogram, served verbatim from `public/` (Vite copies `public/` through unhashed, so the `/favicon.svg` href in [[frontend/apps/manage/index.html]] resolves in dev and in the built bundle alike).
