---
tags: [frontend, manage, config, vitest, testing, jsdom]
sources: [frontend/apps/manage/vitest.config.ts]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/vitest.config.ts
blob: f4e60abecde010d596ec48c5d2d9fad7de290104
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: config
applicability: active
---

# frontend/apps/manage/vitest.config.ts

**Role.** A deliberately standalone test config — `jsdom` environment plus one setup file — that does **not** extend [[frontend/apps/manage/vite.config.ts]], because that file carries the tenant dev proxy and the react/tailwind dev plugins, none of which belong in a test run.

**Module.** [[frontend/apps/manage/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| default export | config | `defineConfig` from `vitest/config` (not `vite`) |
| `test.environment` | option | `"jsdom"` |
| `test.setupFiles` | option | `["./src/test/setup.ts"]` |

## Behavior

There is no `plugins: [react()]` and that is not an omission: Vitest 4 peer-supports Vite 8 (rolldown), whose transform handles TSX on its own, so the react plugin would only add Fast Refresh machinery a test run never uses.

`globals` is left at its default `false`, so `describe`/`it`/`expect` must be imported in every test file — and, more consequentially, Testing Library's auto-cleanup never registers itself, which is why [[frontend/apps/manage/src/test/setup.ts]] calls `cleanup()` in an explicit `afterEach`. Turning `globals: true` on would make that block redundant but would also silently change how every existing test file resolves its imports.

No `include` glob is set, so the default picks up `src/__tests__/*.test.ts{,x}`. No `coverage`, no `pool` and no `testTimeout` overrides. The timezone the suite runs in is **not** configured here — it is the `TZ=America/New_York` prefix on the `test` script in [[frontend/apps/manage/package.json]], which is how unzoned `new Date()` reads are made to fail.

## Depends On

- [[Vitest]] — `defineConfig` from `vitest/config`
- [[frontend/apps/manage/src/test/setup.ts]] — the sole setup file
- [[jsdom]]

## Depended On By

- [[frontend/apps/manage/package.json]] — the `test` script
- [[frontend/apps/manage/tsconfig.json]] — explicitly included so this file is typechecked

## Tests

Every file under `frontend/apps/manage/src/__tests__/` runs through this config, including [[frontend/apps/manage/src/__tests__/BookingDetail.test.tsx]] and [[frontend/apps/manage/src/__tests__/jerusalem.test.ts]].

## Notes

jsdom is not a browser: real focus-trap, layout and pinch-zoom behavior are covered by [[frontend/e2e/a11y.spec.ts]] instead. The `<dialog>` stub in the setup file exists precisely because of that gap.
