---
tags: [frontend, css, tailwind, design-tokens, rtl]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: entity
applicability: n/a
---

# Tailwind CSS

**Purpose.** The styling system for both apps and the shared component package. Tailwind 4.3.3, CSS-first: there is **no `tailwind.config.js` and no PostCSS config in this repo**. Configuration is the `@tailwindcss/vite` plugin plus one `@theme` block in [[frontend/packages/ui/src/theme.css]], which both apps pull in through a two-line [[frontend/apps/storefront/src/index.css]] / [[frontend/apps/manage/src/index.css]].

**The single most useful fact here: `cn()` is a plain join.** [[frontend/packages/ui/src/lib/styles.ts]] is `values.filter(Boolean).join(" ")` — no `clsx`, no `tailwind-merge`. Conflicting utilities of equal specificity resolve by **stylesheet order, not argument order**, so passing `className="p-2"` to a component whose base class is `p-6` may or may not win. Call-site utility overriding is not a supported pattern in this package; extend the component instead.

**`@source "../src"` in `theme.css` is load-bearing.** v4 auto source-detection skips `node_modules`, and `@boutique/ui` is reached only through the [[pnpm]] workspace symlink — without that line, no class used solely inside `packages/ui` is ever compiled, in either app.

`@theme` is the single source of truth for colour, type scale, spacing and radius; [[frontend/packages/ui/src/tokens.ts]] mirrors it for non-CSS consumers and [[frontend/packages/ui/src/__tests__/tokens.test.ts]] parses the CSS and fails on drift. See [[Design Tokens]].

RTL is enforced mechanically, not by convention: [[frontend/scripts/qa-greps.sh]] fails the storefront on any physical inline-direction utility (`ml-`, `pr-`, `text-left`, `border-r-`…) and on any raw hex colour outside the token block. See [[RTL And Bidi Isolation]].
