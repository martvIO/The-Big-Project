# Spec: Feature 30 — MODRYN Platform Branding

**Created**: 2026-07-29 · **Status**: built · **Effort**: S
**Gate 1**: user request, 2026-07-29 — standing approval, no gate prompt. The user supplied the logo artwork (two JPEGs) and the one binding constraint below.
**Depends on**: E2 #9 (`packages/ui` tokens, `@fontsource` self-hosting) · **Feeds**: external-applications rows 2 (domain) and 4 (SMS sender ID)

## Problem

The product had no name. `.planning` carried `*.ourbrand.co.il` as a placeholder, the SMS sender-ID registration was blocked partly on not having a brand string to register, and both Vite apps shipped with no `public/` directory and therefore the browser's default document icon. The user has since settled on **MODRYN** and supplied the artwork: a gold interlocking-diamond monogram over a Didone-ish serif wordmark.

The artwork arrived as two JPEGs. A raster logo cannot be a favicon at 32px, cannot sit in a README, and cannot scale on a login screen, so the mark has to become a vector before anything can consume it.

## Goal

MODRYN is visible wherever the *platform* speaks, and nowhere the *tenant* speaks. The mark exists as a clean SVG that every downstream surface renders from. `modryn.co.il` and the sender ID `MODRYN` are recorded as decisions without anyone pretending they have been purchased.

## The binding constraint

**MODRYN brands the platform, not the boutique.** The user's explicit decision. A tenant storefront is that boutique's shop front: it carries the boutique's name, its own document title, its own hero. The only MODRYN artefact allowed to reach it is the favicon, because a browser tab icon is chrome, not content.

Concretely:

| Surface | Gets MODRYN | Why |
|---|---|---|
| `apps/manage` document title, console title, login screen | yes — lockup + `MODRYN — ` prefix | the owner console *is* the platform |
| `apps/storefront` favicon | yes | tab chrome |
| `apps/storefront` title, header, any page copy | **no** | the boutique's own name lives there |
| domain `*.modryn.co.il`, SMS sender `MODRYN` | yes | platform-level identity |

`e2e/a11y.spec.ts` pins both halves: the manage title must start `MODRYN — `, and the storefront title must never match `/MODRYN/i`.

## Design

### The mark: `assets/brand/modryn-mark.svg`

Traced from `modryn-mark.jpeg` by script (scratch, not committed):

1. Gold mask by chroma + warmth (`sat > 40 && R > B + 20`), 3×3 majority filter, speck/pinhole removal.
2. Crack-following contours on the pixel lattice → four closed rings whose areas sum to the mask's pixel count exactly, i.e. the mark is four disjoint shapes, no holes.
3. Douglas–Peucker (ε = 2.0 px), then every edge snapped to a **data-derived** angle family and every line offset clustered within its family, so parallel ribbon edges land on one line and long edges are genuinely straight.
4. Vertices are the intersections of consecutive snapped lines.

**Fidelity: IoU 0.977** against the source mask, at 72 vertices and 973 bytes. Verified by rendering the SVG in headless Chromium at the source's own pixel geometry and differencing the two masks; the residual is a 1–2px outline everywhere, with no structural error anywhere.

### The brief's 45°/90° premise was wrong — recorded because it changes the artwork

The task assumed "every edge runs at 45° or 90°". The pixels disagree, and forcing that grid cost 13 points of IoU (0.977 → 0.843) with visible wedge-shaped errors. Measured on the convex hull of **both** supplied JPEGs independently, agreeing to <0.5°:

- upper silhouette edges ≈ **55°** from horizontal
- lower silhouette edges ≈ **50°**
- the two long inner ribbons ≈ **58°** (the 239px and 138px edges, so ±0.3° accurate)
- flat top and flat bottom at exactly **0°** — the silhouette is a hexagon, not a diamond

The two source renders share these proportions exactly, so this is the artwork, not scan distortion. The vectorizer therefore *discovers* its angle families (length-weighted KDE over angles folded about the vertical mirror axis) rather than assuming them, and lands on four: **0°, 50.6°, 55.7°, 57.7°** — matching the hull measurement.

### Mirror symmetry is deliberately not enforced

The brief called the mark left-right symmetric. It is *nearly*: the source's own mask scores mirror-IoU **0.930** about x = 333.5. The residual is the interlace — where ribbons cross, one passes over and one under, which is exactly what a woven monogram is for. The traced SVG scores **0.923**, i.e. it reproduces the source's asymmetry rather than adding its own. Folding the geometry to force symmetry would have flattened the weave, so it was not done.

### Surfaces

| File | Change |
|---|---|
| `assets/brand/` | `modryn-mark.svg` (canonical), `modryn-mark.jpeg` + `modryn-lockup.jpeg` (provenance originals) |
| `apps/{manage,storefront}/public/` | `favicon.svg`, `favicon-32.png`, `apple-touch-icon.png` — all rendered from the one SVG in headless Chromium, no new dependency. Both apps' `public/` is new except storefront's, which already held `robots.txt` |
| `apps/manage/src/assets/modryn-mark.svg` | in-app import copy; `src/vite-env.d.ts` added so `tsc` resolves the `.svg` module |
| `apps/manage/index.html` | three favicon links, title → `MODRYN — ניהול הבוטיק` |
| `apps/storefront/index.html` | favicon links only |
| `apps/manage/src/i18n/he.ts` | `document.title`, `console.title`, `login.title` gain the `MODRYN — ` prefix |
| `apps/manage/src/components/LoginForm.tsx` | brand lockup above the card |
| `README.md`, `.planning/{architecture,epics/ROADMAP,epics/e1-platform-foundation}.md` | `ourbrand` → `modryn` |
| `.planning/external-applications.md` | records sender ID + domain as *decided*, not *registered* |

**Favicon background is transparent, not cream.** Checked at 32px against cream, white, dark and mid-grey tab bars: the gold holds on all four, whereas a cream tile reads as a white box on a dark tab bar. `apple-touch-icon` does use cream `#FDFBF7` with an 11% inset, because iOS composites a transparent icon onto black.

### The login lockup is the `<h1>`

`ConsoleShell` already puts its `<h1>` in an `sr-only` span; the login screen now does the same thing for the same reason. The mark is `alt=""` (decorative), the Latin `MODRYN` wordmark is `aria-hidden`, and `t("login.title")` sits in an `sr-only` span. Result: exactly one `h1`, accessible name `MODRYN — כניסה לניהול הבוטיק`, the brand announced once rather than three times, and no second visible "MODRYN" competing with the Hebrew heading two lines below it. Zero axe A/AA violations.

## Deliberate simplifications

| Simplification | Ceiling | Upgrade path |
|---|---|---|
| **Flat gold `#C5A059`** instead of the source's top-left-to-bottom gradient | the mark loses the metallic fold shading; where two ribbons are separated in the source by a light fold highlight, the flat version shows a ~1px hairline instead of a tonal seam | add a `<linearGradient>` to `modryn-mark.svg` — the four rings are already separate subpaths, so per-ribbon shading is available without re-tracing. Deferred because a flat mark is the one that survives 32px, single-colour print, and the token system's "three-gold law" |
| **Wordmark set in Frank Ruhl Libre**, not the logo's own Didone serif | close in feel (high-contrast serif), not the exact face; the real logotype has tighter, more dramatic thick/thin contrast | license the actual display face and either add a webfont or ship the wordmark as a second traced SVG. Frank Ruhl Libre is already self-hosted via `@fontsource` and covers both Latin and Hebrew, so this costs zero bytes today |
| Mark traced at IoU 0.977, not redrawn from the designer's source | ~1–2px of edge deviation at 660px | ask the designer for the original vector; drop it in as `assets/brand/modryn-mark.svg` and nothing downstream changes |

## Out of scope

- Buying `modryn.co.il` or filing the Twilio sender-ID registration — both remain the user's actions, and `external-applications.md` rows 2 and 4 stay open on purpose.
- Any storefront-visible branding beyond the favicon.
- Wiring `BASE_DOMAIN` / bucket CORS to the real domain — blocked on the domain actually existing.
- `backend/tests/test_config.py` still uses `ourbrand.co.il` as an arbitrary fixture domain. It is a test value, not a claim about production, so it was left alone.

## Testing

- `pnpm -r lint`, `pnpm -r typecheck`, `pnpm -r build` — green.
- `make e2e` — 59/59 green, including `manage: login screen has zero axe A/AA violations` (IS 5568 / WCAG 2.0 AA is a legal floor here, not a target) and the two new branding-boundary guards.
- Vectorization verified by rendering to a mask and differencing against the source, not by eye alone; both the 600px and 32px renders were inspected.

## Decisions Log

| Date | Decision |
|---|---|
| 2026-07-29 | Brand name **MODRYN**; Gate 1 by direct user request (standing approval). |
| 2026-07-29 | MODRYN brands the platform only. Storefronts get the favicon and nothing else. Pinned by e2e. |
| 2026-07-29 | Production domain `modryn.co.il`; SMS alphanumeric sender ID `MODRYN` (6 Latin chars, within Twilio's ≤11). Decided, not registered. |
| 2026-07-29 | Mark shipped flat `#C5A059`, wordmark shipped as Frank Ruhl Libre text — see simplifications above. |
| 2026-07-29 | The mark is not on a 45°/90° grid; angle families are measured from the artwork (0 / 50.6 / 55.7 / 57.7°). |
| 2026-07-29 | Mirror symmetry left un-enforced — the asymmetry is the interlace, and the trace matches the source's own 0.93 mirror score. |
