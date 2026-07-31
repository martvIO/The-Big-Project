---
tags: [frontend, ui, tailwind, design-tokens, css, accessibility, rtl, fonts, motion]
sources: [frontend/packages/ui/src/theme.css]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/theme.css
blob: 78e6a1c5f94b3420219e50419b5c06b16d4eb7eb
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/theme.css

**Role.** The design system's single source of truth and the package's second public entry point (`@boutique/ui/theme.css`): it self-hosts the Hebrew-covering fonts, declares the whole `@theme` token block, defines the four keyframe sets, pins the page to a single light scheme, and implements the first-party accessibility boosts that [[frontend/packages/ui/src/components/A11yMenu.tsx]] toggles.

**Module.** [[frontend/packages/ui/src/_index]] · **Layer.** frontend / design system

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `@import "@fontsource/…"` | directive | six per-weight font files: Frank Ruhl Libre 400/500/700, Assistant 400/600/700 |
| `@source "../src"` | directive | tells Tailwind v4 to scan this package's TSX |
| `@theme { … }` | block | every design token — mirrored by [[frontend/packages/ui/src/tokens.ts]] |
| `@keyframes` | rules | `skeleton-pulse`, `toast-in`, `modal-panel`, `modal-backdrop` |
| `:root { color-scheme: only light }` | rule | opts out of forced dark theming |
| `html { … }` | rule | page background, ink, body font, `font-synthesis: none` |
| `@media (prefers-reduced-motion: reduce)` | rule | kills animation + transition, keeps `scroll-behavior` reset |
| `:root[data-a11y-*]` | rules | contrast / text-size / readable-font / underline-links / stop-motion boosts |

## Behavior

**`@source "../src"` is the line without which this package renders unstyled.** Tailwind v4's automatic source detection never scans `node_modules`, and both apps reach `@boutique/ui` through the pnpm workspace symlink — so any class used *only* inside `packages/ui` would compile to nothing. Declaring it here (resolved relative to this file) fixes storefront and manage at once, because both `@import "@boutique/ui/theme.css"` from their own `index.css`. [[frontend/packages/ui/src/__tests__/tokens.test.ts]] resolves the glob for real and asserts a known component file sits under it, because a *wrong* relative path fails in exactly the same silent way.

**The font imports are per-weight for a Hebrew-specific reason.** A bare Fontsource import ships weight 400 alone, and the browser then faux-bolds Hebrew — which looks wrong and is not a real face. Each per-weight file carries all subsets including `hebrew` behind `unicode-range`, so the Hebrew woff2 downloads only when Hebrew actually renders. Nothing is fetched from Google Fonts at runtime. `font-synthesis: none` on `html` is the enforcement half: a missing face fails visibly rather than being synthesised into something that passes review.

**`color-scheme: only light`, not bare `light`.** The product is a single cream theme with hand-verified AA ratios; bare `light` still lets Chrome on Android apply Auto Dark Theme, which force-inverts the page and voids every contrast ratio the tokens were chosen for. `only light` opts out. Given IS 5568 is a legal floor here, that keyword is a compliance control.

**Two of the token values are derived rather than typed, and the comment says why.** `--space-a11y-footprint` is `calc(44px + var(--space-4) + var(--space-2))` — the fixed A11yMenu trigger's own 44px box, its inset, and one step of air — reserved by the footer as `padding-block-end` so the statutory הצהרת נגישות link is never painted over. It is a `calc()` because the literal `pb-8` that shipped on `/about` was 28px short against a 60px footprint. `--space-a11y-clearance` derives the same way from `--cta-bar-height`.

**Reduced motion is handled twice, on purpose, and they are not the same switch.** The `prefers-reduced-motion` media query is the OS-level contract and additionally resets `scroll-behavior` — but it deliberately does **not** disable scroll-snap, which is a positioning affordance rather than motion. The `:root[data-a11y-stop-motion]` rule is the in-product A11yMenu toggle for users whose OS preference is unset. Each `data-a11y-*` attribute lands on `<html>` and works by *re-declaring tokens*, not by restyling components: contrast mode points `--color-ink-muted` at `--color-ink` and `--color-border` at `--color-border-input`; readable-font points `--font-display` at `--font-body`. That is why a component that hardcodes a hex silently opts out of the accessibility menu.

Motion tokens compose rather than repeat: `--animate-toast`, `--animate-modal-panel` and `--animate-modal-backdrop` all resolve their duration and easing from `--motion-*` + `--ease-out`. `--animate-skeleton` (`1.5s ease-in-out infinite`) is the single sanctioned literal-duration exemption. `toast-in` translates on the **block** axis only — no inline translate, which on an RTL page would move in the reader-unexpected direction — and `modal-panel`'s `scale(0.97 → 1)` is the only `scale()` in the system.

## Depends On

- [[Tailwind CSS]] — `@theme` and `@source` are v4 directives
- [[Fontsource]] — the six imported weight files, declared in [[frontend/packages/ui/package.json]]

## Depended On By

- [[frontend/apps/storefront/src/index.css]] — `@import "@boutique/ui/theme.css"`
- [[frontend/apps/manage/src/index.css]] — same
- [[frontend/packages/ui/src/tokens.ts]] — mirrors the `@theme` block
- [[frontend/packages/ui/src/components/A11yMenu.tsx]] — sets the `data-a11y-*` attributes this file styles
- [[frontend/packages/ui/src/components/Skeleton.tsx]] · [[frontend/packages/ui/src/components/Modal.tsx]] · [[frontend/packages/ui/src/components/Toast.tsx]] — consume the `--animate-*` tokens

## Concepts

- [[Design Tokens]]

## Tests

- [[frontend/packages/ui/src/__tests__/tokens.test.ts]] — parses the `@theme` block, asserts parity with `tokens.ts`, the seven paired line-heights, the corrected AA colours, `only light`, `font-synthesis: none`, and that `@source` really covers `src/components/`
- [[frontend/packages/ui/src/__tests__/display-primitives.test.tsx]] — the skeleton pulse token

## Notes

The exported path is `@boutique/ui/theme.css`, declared in the manifest's `exports` map; nothing imports it by relative path from outside this package.
