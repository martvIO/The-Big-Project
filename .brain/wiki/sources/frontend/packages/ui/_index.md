---
tags: [frontend, typescript]
sources: [frontend/packages/ui]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui
blob: 458d6dca0119fdc6cf3bce6572522ac24436be6f
commit: 13d107b8b16f1f2676f1cdb1c994f95822fe2ba0
kind: directory
applicability: active
---

# frontend/packages/ui/

**Purpose.** The shared component library. It has no i18next dependency by design — every string arrives as a prop.

**Parent.** [[frontend/packages/_index]]

## Files

- [[frontend/packages/ui/package.json]] — The manifest for `@boutique/ui`, the shared component library. It publishes **source, not a build** — `main`, `types` and the `.` export all point at `src/index.ts`, so the consuming app's Vite/TS pipeline compiles the TSX. There is no…
- [[frontend/packages/ui/tsconfig.json]] — A two-line tsconfig: extend the workspace base and compile `src`.
- [[frontend/packages/ui/vitest.config.ts]] — The standalone Vitest config for `@boutique/ui` — this package has **no `vite.config.ts`**, because it is never bundled, only consumed as source. It sets exactly two things: the `jsdom` environment and the setup file.

## Subdirectories

- [[frontend/packages/ui/src/_index]] — The package source and its public export surface.
