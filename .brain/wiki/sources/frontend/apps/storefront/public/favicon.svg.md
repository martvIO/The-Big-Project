---
tags: [frontend, storefront, branding, favicon, svg, static-asset, modryn]
sources: [frontend/apps/storefront/public/favicon.svg]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/public/favicon.svg
blob: 12353b2b22881dac85dba82fe88594259f0bd270
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: generated
applicability: active
---

# frontend/apps/storefront/public/favicon.svg

**Role.** The MODRYN interlocking-diamond mark as a single flat-gold path — the vector favicon, and under F30 the **only** MODRYN artefact permitted to appear on a tenant storefront at all, because a browser-tab icon is chrome rather than content.

**Module.** [[frontend/apps/storefront/public/_index]] · **Layer.** platform / static asset

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `viewBox="0 0 1000 1000"` | attribute | square, scales to any tab size |
| `<title>MODRYN</title>` + `role="img"` | elements | accessible name if the file is ever rendered as an image rather than a favicon |
| one `<path>` | element | `fill="#C5A059"`, `fill-rule="evenodd"` — four disjoint closed rings, 72 vertices, 973 bytes |

## Behavior

**Byte-identical to [[assets/brand/modryn-mark.svg]] and to [[frontend/apps/manage/src/assets/modryn-mark.svg]] and [[frontend/apps/manage/public/favicon.svg]].** Four copies of one file, kept in step by hand — no build step, no script, no test compares them. Re-tracing the mark means updating four paths or leaving three stale.

The geometry is machine-traced from `assets/brand/modryn-mark.jpeg`, not hand-drawn: contours on the pixel lattice, Douglas–Peucker simplification, then every edge snapped to an angle family **measured from the artwork** (0° / 50.6° / 55.7° / 57.7°) rather than to the 45°/90° grid the brief assumed — forcing that grid cost 13 points of fidelity. Final IoU 0.977 against the source mask. The near-mirror asymmetry is left in on purpose: it is the interlace, where one ribbon passes over and the other under.

**The background is transparent and the fill is flat, both deliberately.** Checked at 32px against cream, white, dark and mid-grey tab bars — the gold holds on all four, whereas a cream tile reads as a white box on a dark tab. Flat `#C5A059` instead of the source's metallic gradient is what survives 32px, single-colour print, and the token system's three-gold law; the four rings are already separate subpaths, so per-ribbon shading remains available without re-tracing.

That hex is also a **hardcoded duplicate of `--color-gold` in [[frontend/packages/ui/src/theme.css]]** with nothing keeping the two in sync. [[frontend/scripts/qa-greps.sh]]'s "no raw hex colours" check scans `apps/storefront/src` only, so this file is outside its reach by construction.

## Depends On

- [[assets/brand/modryn-mark.svg]] — the canonical original this is a copy of

## Depended On By

- [[frontend/apps/storefront/index.html]] — `<link rel="icon" type="image/svg+xml" href="/favicon.svg">`

## Notes

Spec: [[.planning/specs/modryn-branding.md]] (F30). `kind: generated` because the geometry is script output — which means `brain-scan.sh` skips this page unless run with `--all`. Copied verbatim into `dist/` by Vite's `publicDir`; never imported as a module, so the storefront needs no `.svg` ambient declaration.
