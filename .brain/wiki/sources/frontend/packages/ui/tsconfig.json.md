---
tags: [frontend, ui, typescript, config]
sources: [frontend/packages/ui/tsconfig.json]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/tsconfig.json
blob: 564a5990051fdb8cee49fbbaf99734c1a23cf60a
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: config
applicability: active
---

# frontend/packages/ui/tsconfig.json

**Role.** A two-line tsconfig: extend the workspace base and compile `src`. It adds no compiler option of its own, so this package inherits the same `strict`, `noUnusedLocals`/`noUnusedParameters`, `jsx: react-jsx` and `moduleResolution: bundler` settings as both apps.

**Module.** [[frontend/packages/ui/_index]] · **Layer.** frontend / build config

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `extends` | field | `../../tsconfig.base.json` |
| `include` | field | `["src"]` — components, lib, tokens and `__tests__` all live under it |

## Behavior

The absence of overrides is the point: a per-package `compilerOptions` block is how one workspace member silently drifts to laxer `strict` settings than the apps that consume its source. Because [[frontend/packages/ui/package.json]] ships source rather than a build, `noEmit: true` inherited from [[frontend/tsconfig.base.json]] is correct — `tsc` here is a checker only (`scripts.typecheck`), and the app's bundler does the transform. `include: ["src"]` also pulls in `src/__tests__`, so a type error in a test fails `typecheck`.

## Depends On

- [[frontend/tsconfig.base.json]] — every actual option
- [[TypeScript]]

## Depended On By

- [[frontend/packages/ui/package.json]] — `scripts.typecheck`

## Notes

No `references`/project-composite setup anywhere in this monorepo; the apps resolve `@boutique/ui` through the pnpm workspace symlink and typecheck its sources directly.
