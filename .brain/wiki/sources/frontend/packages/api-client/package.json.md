---
tags: [frontend, api-client, config, pnpm, openapi, stub]
sources: [frontend/packages/api-client/package.json]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/api-client/package.json
blob: 745ff5f6fe46f6581bdaba3b7dd3b78a2536da26
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: config
applicability: active
---

# frontend/packages/api-client/package.json

**Role.** The manifest of a workspace package with no consumers and no runtime code — it exists to keep the *option* of OpenAPI codegen wired up (the `generate` script) while [[frontend/packages/api-client/src/index.ts]] stays an intentional `export {}`.

**Module.** [[frontend/packages/api-client/_index]] · **Layer.** api

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `generate` | script | `openapi-typescript http://localhost:8000/openapi.json -o src/generated/schema.d.ts` — **never run in CI**; needs a live backend and `APP_ENV=dev` |
| `lint` | script | `oxlint -c ../../.oxlintrc.json src` — the shared config, two levels up |
| `typecheck` | script | `tsc --noEmit` against [[frontend/packages/api-client/tsconfig.json]] |

## Behavior

`main` and `types` both point straight at `src/index.ts` — no build step, no `dist`, consumed as TypeScript source by Vite exactly like [[frontend/packages/ui/package.json]]. There are no `dependencies`, only dev ones; `openapi-typescript` is installed so the generate step *could* run, not because anything on the critical path uses it.

The `generate` URL is hardcoded to `localhost:8000` and the output path (`src/generated/schema.d.ts`) is neither committed nor listed in any `.gitignore`, which is a fair summary of the package's status: the machinery is present and unexercised. Running it requires the backend up **with `APP_ENV=dev`**, because F10 disabled `/openapi.json` outside dev so a public storefront origin does not serve the schema to crawlers (see `create_app` in [[backend/app/main.py]]).

## Depends On

- [[openapi-typescript]] — the codegen tool, dev-only (entity)
- [[frontend/.oxlintrc.json]] — the shared lint config
- [[backend/app/main.py]] — the `/openapi.json` route the generate step reads, and the env gate on it

## Depended On By

- [[frontend/pnpm-workspace.yaml]] — via the `packages/*` glob

## Notes

Both `lint` and `typecheck` run in [[.github/workflows/ci.yml]]'s `pnpm -r` sweeps and pass trivially on an empty module. That is the cost of keeping the package: two no-op CI steps in exchange for a decision that stays written down where the next person looks for it.
