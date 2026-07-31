---
tags: [frontend, manage, branding, svg, asset, favicon]
sources: [frontend/apps/manage/public/favicon.svg]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/public/favicon.svg
blob: 12353b2b22881dac85dba82fe88594259f0bd270
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/manage/public/favicon.svg

**Role.** The console's primary tab icon — the MODRYN monogram, served verbatim from `public/` (Vite copies `public/` through unhashed, so the `/favicon.svg` href in [[frontend/apps/manage/index.html]] resolves in dev and in the built bundle alike).

**Module.** [[frontend/apps/manage/public/_index]] · **Layer.** platform

## Behavior

Flat gold `#C5A059` on a **transparent** background, `viewBox="0 0 1000 1000"`, one `evenodd` path. Transparency is a tested choice, not a default: at 32px the gold was checked against cream, white, dark and mid-grey tab bars and holds on all four, whereas a cream tile reads as a white box on a dark tab bar. The raster sibling [[frontend/apps/manage/public/apple-touch-icon.png]] does the opposite for the opposite reason.

The file is a byte-identical copy of the canonical [[assets/brand/modryn-mark.svg]], so everything true of [[frontend/apps/manage/src/assets/modryn-mark.svg]] — the four-ring trace, the deliberate interlace asymmetry, why the gradient was dropped — is true here. The two files differ only in role: this one is browser chrome, that one is a React import.

## Depended On By

- [[frontend/apps/manage/index.html]] — `<link rel="icon" type="image/svg+xml" href="/favicon.svg">`

## Notes

The storefront ships this same file at [[frontend/apps/storefront/public/favicon.svg]], and that is the *only* MODRYN artefact allowed on a tenant page: a tab icon is chrome, not content. Four identical copies exist repo-wide with nothing keeping them in sync.

Spec: [[.planning/specs/modryn-branding.md]].
