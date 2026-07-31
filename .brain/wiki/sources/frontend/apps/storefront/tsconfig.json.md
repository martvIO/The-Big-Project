---
tags: [frontend, storefront, typescript, config]
sources: [frontend/apps/storefront/tsconfig.json]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/tsconfig.json
blob: 9f794f9efcea6f62667da5bae28a272d14cfd50b
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: config
applicability: active
---

# frontend/apps/storefront/tsconfig.json

**Role.** A two-line tsconfig: extend the workspace base and compile `src` plus the app's own two config files. It declares no compiler option of its own, so the storefront inherits exactly the `strict`, `noUnusedLocals`/`noUnusedParameters`, `jsx: react-jsx` and `moduleResolution: bundler` settings that the console and the component library use.

**Module.** [[frontend/apps/storefront/_index]] · **Layer.** frontend / build config

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `extends` | field | `../../tsconfig.base.json` |
| `include` | field | `["src", "vite.config.ts", "vitest.config.ts"]` |

## Behavior

The absence of a `compilerOptions` block is the point: a per-app override is how one workspace member silently drifts to laxer `strict` settings than the library whose source it compiles. Byte-for-byte identical to [[frontend/apps/manage/tsconfig.json]], and identical to [[frontend/packages/ui/tsconfig.json]] except for the two extra `include` entries.

Naming `vite.config.ts` and `vitest.config.ts` in `include` is what makes them typechecked at all — they sit outside `src`, so without the entries a broken proxy option or a misspelled Vitest field would only surface when the tool actually loaded the file. `include: ["src"]` also pulls in `src/__tests__`, so a type error in a test fails `pnpm typecheck` and therefore `pnpm build` ([[frontend/apps/storefront/package.json]] runs `tsc --noEmit` ahead of `vite build`).

`noEmit: true` is inherited from [[frontend/tsconfig.base.json]]: `tsc` here is a checker only, and Vite does every transform. `@boutique/ui` resolves through the pnpm workspace symlink and is typechecked **from source** — there is no `references`/project-composite setup anywhere in this monorepo.

## Depends On

- [[frontend/tsconfig.base.json]] — every actual option
- [[TypeScript]]

## Depended On By

- [[frontend/apps/storefront/package.json]] — `scripts.typecheck` and `scripts.build`

## Notes

The storefront has no `vite-env.d.ts`, and does not need one: it imports no `.svg` module. The console does ([[frontend/apps/manage/src/vite-env.d.ts]], added by F30 so `tsc` can resolve its in-app mark import), whereas the storefront's MODRYN mark is a static public asset the browser fetches, never a module.
