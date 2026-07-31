---
tags: [frontend, api-client, config, typescript]
sources: [frontend/packages/api-client/tsconfig.json]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/api-client/tsconfig.json
blob: 564a5990051fdb8cee49fbbaf99734c1a23cf60a
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: config
applicability: active
---

# frontend/packages/api-client/tsconfig.json

**Role.** Two lines: extend [[frontend/tsconfig.base.json]], include `src`. No overrides at all — the package has one file and it is `export {}`.

**Module.** [[frontend/packages/api-client/_index]] · **Layer.** api

## Behavior

Its only real effect today is that `pnpm --filter @boutique/api-client typecheck` has something to point at, so the package participates in the repo-wide `pnpm -r typecheck` sweep without erroring on a missing config. If codegen is ever adopted, the emitted `src/generated/schema.d.ts` falls inside `include` with no change here — which is the one reason to keep the `include` as `src` rather than naming the single file.

## Depends On

- [[frontend/tsconfig.base.json]]

## Depended On By

- [[frontend/packages/api-client/package.json]] — the `typecheck` script
