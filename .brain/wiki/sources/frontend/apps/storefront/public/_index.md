---
tags: [frontend, typescript]
sources: [frontend/apps/storefront/public]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/public
blob: cea1f449cf1f75647d2df20a80a8814c29b95ec2
commit: 13d107b8b16f1f2676f1cdb1c994f95822fe2ba0
kind: directory
applicability: active
---

# frontend/apps/storefront/public/

**Purpose.** Static assets, including the `robots.txt` that keeps unlaunched boutiques out of search results.

**Parent.** [[frontend/apps/storefront/_index]]

## Files

- [[frontend/apps/storefront/public/apple-touch-icon.png]] — The 180×180 home-screen icon iOS uses when a visitor saves the boutique's storefront to her home screen — the same MODRYN mark as the other two icons, but composited onto an opaque cream tile instead of transparency.
- [[frontend/apps/storefront/public/favicon-32.png]] — The 32×32 raster fallback favicon for browsers that will not take the SVG. Rendered from [[frontend/apps/storefront/public/favicon.svg]] in headless Chromium — no image dependency was added to the toolchain to produce it.
- [[frontend/apps/storefront/public/favicon.svg]] — The MODRYN interlocking-diamond mark as a single flat-gold path — the vector favicon, and under F30 the **only** MODRYN artefact permitted to appear on a tenant storefront at all, because a browser-tab icon is chrome rather than content.
- [[frontend/apps/storefront/public/robots.txt]] — Two directives — `User-agent: *` / `Disallow: /` — that keep every search engine out of every tenant storefront until E10 ships real SEO. Five lines of comment carry the reasoning, because the file looks like an oversight and is the…
