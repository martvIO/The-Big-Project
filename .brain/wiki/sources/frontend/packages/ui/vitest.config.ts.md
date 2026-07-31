---
tags: [frontend, ui, vitest, test-config, jsdom]
sources: [frontend/packages/ui/vitest.config.ts]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/vitest.config.ts
blob: 632442246593623a6c2407660a5b8ea9db378ef9
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: config
applicability: active
---

# frontend/packages/ui/vitest.config.ts

**Role.** The standalone Vitest config for `@boutique/ui` — this package has **no `vite.config.ts`**, because it is never bundled, only consumed as source. It sets exactly two things: the `jsdom` environment and the setup file.

**Module.** [[frontend/packages/ui/_index]] · **Layer.** frontend / test config

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| default export | config | `defineConfig` from `vitest/config` |
| `test.environment` | field | `"jsdom"` — component tests need a DOM |
| `test.setupFiles` | field | `["./src/test/setup.ts"]` |

## Behavior

The file's own comment records the reason it can be this short: **Vitest 4 transforms TSX without the React plugin**, so no `@vitejs/plugin-react` and no JSX config are needed here (the apps' own vitest configs are separate). `globals` is left off — the suite imports `describe`/`it`/`expect` explicitly, which is why [[frontend/packages/ui/src/test/setup.ts]] must register `cleanup()` in a hand-written `afterEach` rather than relying on Testing Library's auto-cleanup.

The Jerusalem-vs-device-clock guard is **not** here: it lives as `TZ=America/New_York` on the `test` script in [[frontend/packages/ui/package.json]]. Running `vitest` directly, bypassing the package script, therefore runs the suite in the machine's local zone and can turn a genuinely unzoned date read green.

## Depends On

- [[Vitest]]
- [[jsdom]]
- [[frontend/packages/ui/src/test/setup.ts]]

## Depended On By

- [[frontend/packages/ui/package.json]] — `scripts.test`

## Tests

Every file under `frontend/packages/ui/src/__tests__/` runs through this config, e.g. [[frontend/packages/ui/src/__tests__/Modal.test.tsx]] and [[frontend/packages/ui/src/__tests__/hours.test.ts]].

## Notes

Sibling configs exist per app ([[frontend/apps/storefront/vitest.config.ts]], [[frontend/apps/manage/vitest.config.ts]]); there is no root Vitest workspace file, so each package is run on its own.
