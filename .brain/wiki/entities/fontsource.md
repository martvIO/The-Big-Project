---
tags: [frontend, fonts, hebrew, typography, privacy]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: entity
applicability: n/a
---

# Fontsource

**Purpose.** Self-hosted webfonts. `@fontsource/frank-ruhl-libre` 5.3.0 (display) and `@fontsource/assistant` 5.3.0 (body) are the **only two runtime `dependencies` of [[frontend/packages/ui/package.json]]** — everything else there is a peer or a devDependency. No Google Fonts request is made in production.

**Weights are imported one file at a time, and that is not stylistic.** [[frontend/packages/ui/src/theme.css]] imports `400.css`, `500.css`, `700.css` for Frank Ruhl Libre and `400.css`, `600.css`, `700.css` for Assistant. A bare package import ships weight 400 alone, and the browser then **faux-bolds Hebrew**, which looks wrong in a way no test catches.

Each per-weight file carries every subset — including `hebrew` — behind `unicode-range`, so the Hebrew woff2 is fetched only when Hebrew actually renders. Both families are chosen for Hebrew coverage; the `--font-display` and `--font-body` tokens in the same `@theme` block fall back to `"David Libre", serif` and `"Heebo", system-ui, sans-serif`.

Because the imports live in `packages/ui`, both apps get the fonts from the single `@import "@boutique/ui/theme.css"` line in [[frontend/apps/storefront/src/index.css]] and [[frontend/apps/manage/src/index.css]].
