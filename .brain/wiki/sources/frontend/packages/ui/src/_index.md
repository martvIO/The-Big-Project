---
tags: [frontend, typescript]
sources: [frontend/packages/ui/src]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src
blob: 7616d7be11a9ef464958e16c41d587e976eb95e6
commit: 13d107b8b16f1f2676f1cdb1c994f95822fe2ba0
kind: directory
applicability: active
---

# frontend/packages/ui/src/

**Purpose.** The package source and its public export surface.

**Parent.** [[frontend/packages/ui/_index]]

## Files

- [[frontend/packages/ui/src/index.ts]] — The entire public surface of `@boutique/ui` — the barrel that both apps import from, and the *only* module path either app is expected to name. It re-exports the tokens, the two lib helpers, twenty-odd components with their prop types, and…
- [[frontend/packages/ui/src/theme.css]] — The design system's single source of truth and the package's second public entry point (`@boutique/ui/theme.css`): it self-hosts the Hebrew-covering fonts, declares the whole `@theme` token block, defines the four keyframe sets, pins the…
- [[frontend/packages/ui/src/tokens.ts]] — A TypeScript **mirror** of the `@theme` block in [[frontend/packages/ui/src/theme.css]], for the consumers that cannot read a CSS custom property — a `<meta name="theme-color">` tag, a canvas fill, any module-scope JS. It is not the source…

## Subdirectories

- [[frontend/packages/ui/src/__tests__/_index]] — Vitest suites pinning each primitive's contract, including the design-token guard that certifies contrast ratios rather than leaving them to the eye.
- [[frontend/packages/ui/src/components/_index]] — Every shared primitive and composite, from `Button` to the promoted `SlotPicker`.
- [[frontend/packages/ui/src/lib/_index]] — Pure helpers: the class joiner, the Jerusalem constant and opening-hours maths, and URL helpers.
- [[frontend/packages/ui/src/test/_index]] — Vitest setup shared by the package's suites.
