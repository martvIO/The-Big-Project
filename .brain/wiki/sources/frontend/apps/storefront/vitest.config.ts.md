---
tags: [frontend, storefront, vitest, test-config, jsdom]
sources: [frontend/apps/storefront/vitest.config.ts]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/vitest.config.ts
blob: f4e60abecde010d596ec48c5d2d9fad7de290104
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: config
applicability: active
---

# frontend/apps/storefront/vitest.config.ts

**Role.** A standalone Vitest config that sets exactly two things — the `jsdom` environment and the setup file — and deliberately does **not** reuse [[frontend/apps/storefront/vite.config.ts]], so the dev proxy and the Tailwind/React dev plugins never enter the test pipeline.

**Module.** [[frontend/apps/storefront/_index]] · **Layer.** frontend / test config

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| default export | config | `defineConfig` from `vitest/config` (not `vite`) |
| `test.environment` | field | `"jsdom"` — the suite renders components |
| `test.setupFiles` | field | `["./src/test/setup.ts"]` |

## Behavior

The file's own comment records why it can be this short: **Vitest 4 peer-supports Vite 8 (rolldown) and transforms TSX without `@vitejs/plugin-react`**, so no JSX plugin is configured here. Importing the app's `vite.config.ts` instead would have dragged the `localhost:8000` proxy into a suite that mocks [[frontend/apps/storefront/src/api.ts]] outright.

`globals` is left off. That is why [[frontend/apps/storefront/src/test/setup.ts]] must register `afterEach(cleanup)` by hand — Testing Library's auto-cleanup binds to a global `afterEach` that only exists under `globals: true` — and why every spec imports `describe`/`it`/`expect`/`vi` explicitly.

**The Jerusalem-vs-device-clock guard is not here.** It lives as `TZ=America/New_York` on `scripts.test` in [[frontend/apps/storefront/package.json]]. Invoking `vitest` directly, bypassing the package script, runs the suite in the machine's local zone and can turn a genuinely unzoned date read green.

Nothing sets `css`, so Tailwind classes are never compiled during tests: assertions go through roles, accessible names and `data-testid`, never computed style.

## Depends On

- [[Vitest]]
- [[jsdom]]
- [[frontend/apps/storefront/src/test/setup.ts]]

## Depended On By

- [[frontend/apps/storefront/package.json]] — `scripts.test`
- [[frontend/apps/storefront/tsconfig.json]] — named in `include`, so this file is typechecked

## Concepts

- [[Jerusalem Time]]

## Tests

Every file under `frontend/apps/storefront/src/__tests__/` runs through this config, e.g. [[frontend/apps/storefront/src/__tests__/router.test.tsx]] and [[frontend/apps/storefront/src/__tests__/accessibility.test.tsx]].

## Notes

Byte-identical to [[frontend/apps/manage/vitest.config.ts]]; [[frontend/packages/ui/vitest.config.ts]] differs only in its comment. There is no root Vitest workspace file, so `pnpm -r --if-present test` runs three independent suites, each with its own setup file — a jsdom gap patched in one is not patched in the others.
