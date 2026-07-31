---
tags: [frontend, typescript, tooling, types]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: entity
applicability: n/a
---

# TypeScript

**Purpose.** The language for the whole frontend. Declared `^5.7.0` in every package, resolved to 5.9.3 in `frontend/pnpm-lock.yaml`.

**There is exactly one real compiler config: [[frontend/tsconfig.base.json]].** Every package `tsconfig.json` is a two-line `extends` plus an `include` — see [[frontend/apps/storefront/tsconfig.json]] and [[frontend/packages/ui/tsconfig.json]]. The base sets `strict`, `noEmit`, `isolatedModules`, `moduleResolution: "bundler"`, `jsx: "react-jsx"`, `forceConsistentCasingInFileNames`, and — the two that bite most often — **`noUnusedLocals` and `noUnusedParameters`**, so a leftover import after a refactor is a build failure, not a lint warning.

**`packages/ui` ships raw source, not a build.** Its `main` and `types` both point at `src/index.ts` and it has no build script, so the apps type-check the library's own `.ts`/`.tsx` through the pnpm workspace symlink. A type error in `packages/ui` surfaces as a failure in every consumer at once.

Type-checking runs as its own step (`pnpm -r typecheck`) *and* as the first half of each app's `build`, because [[Vite]] itself never type-checks. Lint is [[oxlint]], which does not type-check either.

Backend-derived API types are **not** generated: [[frontend/packages/api-client/src/index.ts]] is a deliberate empty stub and each app hand-writes its own `src/api.ts`.
