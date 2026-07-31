---
tags: [frontend, manage, css, tailwind, design-tokens]
sources: [frontend/apps/manage/src/index.css]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/src/index.css
blob: 73e1a47dd6067946f1d8b31732124cd024b4f360
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/manage/src/index.css

**Role.** Two `@import` lines and nothing else — Tailwind 4 followed by the shared theme. The console has **no app-local CSS**: every colour, radius, shadow and font in the owner console comes from the design-token `@theme` block in [[frontend/packages/ui/src/theme.css]].

**Module.** [[frontend/apps/manage/src/_index]] · **Layer.** styling

## Behavior

Order is not cosmetic. `@import "tailwindcss"` must come first so that `@boutique/ui/theme.css`'s `@theme` block is processed as a Tailwind theme extension — the tokens it declares are what make `bg-bg`, `text-ink`, `text-ink-muted` and the rest resolve to real utilities. Swapping the two lines, or dropping the second, silently degrades every token utility in the app to an unknown class that emits no CSS.

The file's emptiness is the point: adding a rule here would create a second styling authority alongside the tokens, and utilities written at a call site cannot reliably beat a `@boutique/ui` component's own classes anyway (`cn()` is a plain join with no class-merge, so same-specificity rules resolve by stylesheet order). [[frontend/apps/storefront/src/index.css]] is the same two lines for the public site.

## Depends On

- [[frontend/packages/ui/src/theme.css]] — resolved through the package's `theme.css` export
- [[Tailwind CSS]]

## Depended On By

- [[frontend/apps/manage/src/main.tsx]] — side-effect import

## Concepts

- [[Design Tokens]]
