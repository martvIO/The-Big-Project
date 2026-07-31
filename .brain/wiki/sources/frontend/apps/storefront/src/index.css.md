---
tags: [frontend, storefront, css, tailwind, design-tokens]
sources: [frontend/apps/storefront/src/index.css]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/index.css
blob: 73e1a47dd6067946f1d8b31732124cd024b4f360
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/storefront/src/index.css

**Role.** Two `@import` lines and nothing else — Tailwind 4 followed by the shared theme. The public site has **no app-local CSS**: every colour, radius, shadow and font a bride sees comes from the design-token `@theme` block in [[frontend/packages/ui/src/theme.css]].

**Module.** [[frontend/apps/storefront/src/_index]] · **Layer.** styling

## Behavior

Order is not cosmetic. `@import "tailwindcss"` must come first so that `@boutique/ui/theme.css`'s `@theme` block is processed as a Tailwind theme extension — that is what makes `bg-bg`, `text-ink`, `text-gold-text` and the rest resolve to real utilities. Swapping the two lines, or dropping the second, silently degrades every token utility in the app to an unknown class that emits no CSS.

The file's emptiness is the enforcement point for the storefront's brand rule: the boutique's look is the tokens, and there is no app-level escape hatch to override them per screen. A rule added here would also be futile at a call site — `cn()` is a plain join with no class-merge, so a consumer utility does not reliably beat a `@boutique/ui` component's own class; same-specificity rules resolve by stylesheet order. `frontend/scripts/qa-greps.sh` separately bans raw hex colours across `apps/storefront/src`.

Same git blob as [[frontend/apps/manage/src/index.css]] — both apps consume the identical two lines.

## Depends On

- [[frontend/packages/ui/src/theme.css]] — resolved through the package's `theme.css` export
- [[Tailwind CSS]]

## Depended On By

- [[frontend/apps/storefront/src/main.tsx]] — side-effect import

## Concepts

- [[Design Tokens]]
