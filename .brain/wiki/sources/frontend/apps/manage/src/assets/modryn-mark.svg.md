---
tags: [frontend, manage, branding, svg, asset, accessibility]
sources: [frontend/apps/manage/src/assets/modryn-mark.svg]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/src/assets/modryn-mark.svg
blob: 12353b2b22881dac85dba82fe88594259f0bd270
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/manage/src/assets/modryn-mark.svg

**Role.** The in-app import copy of the MODRYN monogram — the *only* brand asset that reaches a React tree rather than the browser chrome. [[frontend/apps/manage/src/components/LoginForm.tsx]] imports it as a URL (`import markUrl from "../assets/modryn-mark.svg"`) for the login lockup; it lives under `src/` rather than `public/` so Vite hashes and inlines it like any other module.

**Module.** [[frontend/apps/manage/src/assets/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `<svg viewBox="0 0 1000 1000" role="img">` | root | square viewBox, no width/height — the consumer sizes it in CSS |
| `<title>MODRYN</title>` | element | present but inert in practice (see Behavior) |
| single `<path>` | element | `fill="#C5A059"`, `fill-rule="evenodd"` — four disjoint interlocking-ribbon subpaths in one `d` |

## Behavior

One flat gold `#C5A059` and one path. The flatness is a recorded decision, not a shortcut: the source artwork has a metallic top-left-to-bottom-right fold gradient, and a gradient version was rejected because a flat mark is the one that still reads at 32px, in single-colour print, and inside the design system's three-gold rule. The four ribbons are already separate subpaths, so per-ribbon shading remains available later without re-tracing.

`fill-rule="evenodd"` matters — the mark was traced as four closed rings whose areas sum exactly to the source mask, i.e. no holes; change the fill rule and the interlace inverts. The weave is also *not* left-right symmetric (mirror-IoU ≈ 0.92 about the vertical axis), and that asymmetry is faithful to the original: where two ribbons cross, one passes over and one under. Folding the geometry to force symmetry would flatten the weave, and was deliberately not done.

**The `role="img"` + `<title>` pair does nothing at the one call site that exists.** LoginForm renders this through an `<img>` tag with `alt=""` (decorative), so the SVG's internal accessible name is never exposed — the login lockup's real name comes from an `sr-only` Hebrew heading, and announcing "MODRYN" from the mark as well would say the brand twice. The title element is only meaningful if some future caller inlines the SVG instead.

## Depends On

Nothing — it is a leaf asset.

## Depended On By

- [[frontend/apps/manage/src/components/LoginForm.tsx]] — the sole importer, anywhere in the repo

## Concepts

- [[Design Tokens]] — `#C5A059` is the brand gold

## Notes

**Byte-identical to three other tracked files**: [[assets/brand/modryn-mark.svg]] (the canonical original), [[frontend/apps/manage/public/favicon.svg]] and [[frontend/apps/storefront/public/favicon.svg]]. Four copies of the same 973 bytes with no build step keeping them in sync — re-trace the mark and all four must be updated by hand.

Spec: [[.planning/specs/modryn-branding.md]] (F30 — trace method, the gold, the symmetry finding, and the "platform not tenant" rule).
