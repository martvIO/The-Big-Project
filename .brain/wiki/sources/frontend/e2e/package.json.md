---
tags: [frontend, e2e, config, pnpm, workspace]
sources: [frontend/e2e/package.json]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/e2e/package.json
blob: f70ab067e10acaf4305392ffe355a89a1b0104c0
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: config
applicability: active
---

# frontend/e2e/package.json

**Role.** Makes `e2e/` a pnpm workspace member — which is the entire point of the file. Membership is what puts the two spec files under the repo-wide `pnpm -r lint` and `pnpm -r typecheck` sweeps; a bare directory of `.ts` files would be linted and type-checked by nothing.

**Module.** [[frontend/e2e/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `lint` | script | `oxlint -c ../.oxlintrc.json .` — the shared config, never oxlint's zero-config default |
| `typecheck` | script | `tsc --noEmit` against [[frontend/e2e/tsconfig.json]] |

## Behavior

There is deliberately **no `test` script**: the suite is driven from the workspace root (`pnpm e2e` in [[frontend/package.json]]) so that Playwright runs once for the whole monorepo with both preview servers up, rather than once per package under `pnpm -r test`. `@playwright/test` and `@axe-core/playwright` are declared here as well as at the root — here so `tsc` and `oxlint` resolve the imports in the spec files, at the root so the runner exists for the `e2e` script.

`-c ../.oxlintrc.json` is load-bearing for the same reason it is everywhere else in this monorepo: oxlint's default config does not enable the `react` plugin, so a hooks violation passes silently. `@types/node` is present because [[frontend/e2e/playwright.config.ts]] reads `process.env.CI`.

## Depends On

- [[Playwright]] · [[axe-core]] — the two testing entities (entities)
- [[frontend/.oxlintrc.json]] — the shared lint config referenced by relative path
- [[frontend/pnpm-workspace.yaml]] — lists `e2e` explicitly, not by glob

## Depended On By

- [[frontend/pnpm-workspace.yaml]]

## Notes

`frontend/pnpm-workspace.yaml` names `e2e` as a literal entry rather than folding it into a glob, because it is the only member outside `apps/*` and `packages/*`.
