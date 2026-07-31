---
tags: [frontend, storefront, branding, favicon, ios, png, static-asset, modryn]
sources: [frontend/apps/storefront/public/apple-touch-icon.png]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/public/apple-touch-icon.png
blob: 9c7d1a33410761b27a1ee3ac8bd1e1ffcd7c8f4f
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: generated
applicability: active
---

# frontend/apps/storefront/public/apple-touch-icon.png

**Role.** The 180×180 home-screen icon iOS uses when a visitor saves the boutique's storefront to her home screen — the same MODRYN mark as the other two icons, but composited onto an opaque cream tile instead of transparency.

**Module.** [[frontend/apps/storefront/public/_index]] · **Layer.** platform / static asset

## Public Surface

Binary. 180×180, 8-bit **RGB** (no alpha channel), non-interlaced PNG, 7778 bytes.

## Behavior

**This is the one icon that is not transparent, and the reason is platform behaviour rather than taste.** iOS composites a transparent touch icon onto black, so the gold mark that reads correctly in a browser tab would sit on a black square on the home screen. The tile is therefore baked in at cream `#FDFBF7` with an 11% inset — hence RGB rather than the RGBA of [[frontend/apps/storefront/public/favicon-32.png]], which keeps its alpha precisely so the tab bar's own colour shows through.

Rendered from [[frontend/apps/storefront/public/favicon.svg]] in headless Chromium, and byte-identical to [[frontend/apps/manage/public/apple-touch-icon.png]]. Nothing regenerates it: change the mark and this file keeps the old geometry in both apps until someone re-runs the render by hand.

**A phone-relevant asset on a phone-first surface.** This app is the customer-facing half of the product and the traffic arrives from Instagram, so "add to home screen" is a real path here in a way it is not for the owner console — but note there is no web-app manifest and no service worker anywhere in the repo, so saving it produces a bookmark, not an installed PWA.

## Depends On

- [[frontend/apps/storefront/public/favicon.svg]] — the source geometry (by provenance, not by build)

## Depended On By

- [[frontend/apps/storefront/index.html]] — `<link rel="apple-touch-icon">`

## Notes

Spec: [[.planning/specs/modryn-branding.md]] (F30, "Favicon background is transparent, not cream"). `kind: generated` because it is machine-rendered output — `brain-scan.sh` skips this page unless run with `--all`.
