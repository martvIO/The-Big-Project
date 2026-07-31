---
tags: [frontend, manage, config, typescript]
sources: [frontend/apps/manage/tsconfig.json]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/tsconfig.json
blob: 9f794f9efcea6f62667da5bae28a272d14cfd50b
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: config
applicability: active
---

# frontend/apps/manage/tsconfig.json

**Role.** A four-line manifest that adds nothing but an `include` list: every compiler option comes from [[frontend/tsconfig.base.json]], so the console cannot quietly relax `strict`, `noUnusedLocals` or `noUnusedParameters` for itself.

**Module.** [[frontend/apps/manage/_index]] · **Layer.** platform

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `extends` | field | `../../tsconfig.base.json` — the only source of `compilerOptions` |
| `include` | field | `["src", "vite.config.ts", "vitest.config.ts"]` |

## Behavior

The two config files are named explicitly because they sit outside `src` and would otherwise be unchecked — `tsc --noEmit` is the build gate in [[frontend/apps/manage/package.json]], so anything not included is code that ships without a typecheck. `index.html` and `public/` are not TypeScript and are correctly absent.

`noEmit` and `isolatedModules` are inherited: Vite does the transform, `tsc` only judges. Nothing here teaches `tsc` about asset imports — the `.svg` import in [[frontend/apps/manage/src/components/LoginForm.tsx]] typechecks only because [[frontend/apps/manage/src/vite-env.d.ts]] is inside `src` and pulls in `vite/client`'s ambient `*.svg` module declaration. Delete that one-line file and `typecheck` fails while the app still runs, which is a confusing failure worth knowing about.

## Depends On

- [[frontend/tsconfig.base.json]] — all compiler options
- [[TypeScript]]

## Depended On By

- [[frontend/apps/manage/package.json]] — `build` and `typecheck` scripts

## Notes

There is no `references`/project-references setup and no separate `tsconfig.node.json`; the single include list covers both app and tooling code.
