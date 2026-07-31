---
tags: [frontend, testing, vitest, jsdom]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: entity
applicability: n/a
---

# Vitest

**Purpose.** The frontend unit and component test runner. Vitest 4.1.10 with `environment: "jsdom"` ([[jsdom]] 29), driving [[Testing Library]] for component tests. Browser-level tests are [[Playwright]]'s job, not this one.

**Every test script pins `TZ=America/New_York`** — [[frontend/apps/storefront/package.json]], [[frontend/apps/manage/package.json]], [[frontend/packages/ui/package.json]] all run `TZ=America/New_York vitest run`. That is not arbitrary: New York is a different calendar day from Jerusalem for part of every day, so any date read that forgot `timeZone: JERusalem` produces a *wrong* value rather than a coincidentally-right one. See [[Intl API]] and [[Jerusalem Time]].

**Each package carries a standalone `vitest.config.ts`, deliberately not the app's `vite.config.ts`** — [[frontend/apps/storefront/vitest.config.ts]], [[frontend/apps/manage/vitest.config.ts]], [[frontend/packages/ui/vitest.config.ts]]. Vitest 4 peer-supports [[Vite]] 8, so TSX transforms work without the react plugin; `packages/ui` has no `vite.config.ts` at all.

Runs recursively as `pnpm -r --if-present test` (see [[Makefile]] and [[.github/workflows/ci.yml]]) — `--if-present` is required because `packages/api-client` and `e2e` have no `test` script.
