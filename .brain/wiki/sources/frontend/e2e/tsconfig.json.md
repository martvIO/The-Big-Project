---
tags: [frontend, e2e, config, typescript]
sources: [frontend/e2e/tsconfig.json]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/e2e/tsconfig.json
blob: 19cea5d34dc3a58280c59482f9df6c9cb054126a
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: config
applicability: active
---

# frontend/e2e/tsconfig.json

**Role.** Four lines: extend the shared base and add `"types": ["node"]`, because [[frontend/e2e/playwright.config.ts]] reads `process.env.CI` and nothing else in this package touches Node globals.

**Module.** [[frontend/e2e/_index]] · **Layer.** test

## Behavior

`include: ["."]` covers the config and both spec files — there is no `src/` here. Everything strict comes from [[frontend/tsconfig.base.json]] (`strict`, `noUnusedLocals`, `noUnusedParameters`), which is why the specs carry explicit return types and `String(n)` casts in template literals rather than relying on implicit coercion. No `jsx` override is needed: the specs are plain `.ts`, they drive a browser and never render a component.

## Depends On

- [[frontend/tsconfig.base.json]] — every compiler option other than `types`

## Depended On By

- [[frontend/e2e/package.json]] — the `typecheck` script runs `tsc --noEmit` against it
