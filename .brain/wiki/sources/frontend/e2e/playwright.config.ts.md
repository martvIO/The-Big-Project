---
tags: [frontend, e2e, playwright, config, vite-preview, rtl]
sources: [frontend/e2e/playwright.config.ts]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/e2e/playwright.config.ts
blob: a73a6fcd6fba6f738981d207663a3979bcbed2c4
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: config
applicability: active
---

# frontend/e2e/playwright.config.ts

**Role.** The whole E2E harness in one file: it starts `vite preview` for **both** built apps on fixed ports, pins the browser locale to `he-IL`, and runs a single chromium project. It is what makes "the built stylesheet, the built bundle" — not the dev server — the thing under test.

**Module.** [[frontend/e2e/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| default export | `defineConfig(...)` | the only export; `playwright test -c e2e/playwright.config.ts` is the entry ([[frontend/package.json]] `e2e` script) |

## Behavior

`testDir: "."` picks up both spec files next to it, and `fullyParallel` means they interleave — every spec therefore installs its own routes and owns its own page, with no shared fixture state. Two `webServer` entries serve the **preview** build: storefront on **:4173** and manage on **:4174**, each with `--strictPort` so a port already taken by something else fails loudly instead of silently serving the wrong app on a shifted port. `reuseExistingServer` is on locally and off under `CI`, and `forbidOnly` flips on under `CI` so a stray `test.only` cannot land a green pipeline that ran one case.

`locale: "he-IL"` is not cosmetic here: the specs assert Hebrew copy and read `Intl`-formatted times, so a default `en-US` browser would change what the page renders before a single assertion runs. Note the dates and times the app prints still come from a Jerusalem-zoned formatter in application code — the locale pins the *language and numbering*, never the zone.

**Neither server has a backend behind it, and that is the harness's defining property.** `/storefront/*` is forwarded to `localhost:8000` — neither vite config sets a `preview.proxy`, so this relies on preview defaulting to the `server.proxy` block, which is what [[frontend/e2e/a11y.spec.ts]]'s header asserts — where, in CI, nothing is listening — [[.github/workflows/ci.yml]]'s `e2e` job builds and serves the apps and starts no API. [[frontend/e2e/storefront.spec.ts]] answers that by fulfilling every request from a fixture; [[frontend/e2e/a11y.spec.ts]] deliberately does not, and keeps its value as the API-is-down pass. The two manage specs can therefore only ever reach the **login screen** — there is no session to be had — which is exactly the surface they assert on.

`trace: "on-first-retry"` and `reporter: "line"` keep a passing run quiet and a failing one debuggable. Only chromium is configured; adding a second project multiplies a suite that already measures layout geometry at three viewport widths.

## Depends On

- [[Playwright]] — `defineConfig`, `devices` (entity)
- [[frontend/apps/storefront/vite.config.ts]] — the proxy `preview` inherits; the storefront's build is what :4173 serves
- [[frontend/apps/manage/vite.config.ts]] — same, for :4174
- [[frontend/package.json]] — the workspace-root `e2e` script that points at this file

## Depended On By

- [[frontend/e2e/storefront.spec.ts]] — hardcodes `http://localhost:4173`
- [[frontend/e2e/a11y.spec.ts]] — hardcodes both ports
- [[.github/workflows/ci.yml]] — `pnpm e2e` in the `e2e` job
- [[Makefile]] — the `e2e` target (build → install chromium → `pnpm e2e`)

## Tests

This file *is* test infrastructure; it has no tests of its own.

## Notes

The port numbers live in three places — here, and as string constants at the top of each spec. Changing one and not the others produces a suite that starts servers nobody talks to and then times out on `page.goto`, which reads as an app failure rather than a config one.

`pnpm -r build` must run before this config is useful: `vite preview` serves `dist/`, and a stale or missing build silently tests yesterday's code. Both the [[Makefile]] target and the CI job encode that ordering.
