---
tags: [frontend, testing, e2e, accessibility]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: entity
applicability: n/a
---

# Playwright

**Purpose.** The only real-browser test layer in the repo. `@playwright/test` 1.62 plus
`@axe-core/playwright` 4.12, declared at the monorepo root in [[frontend/package.json]] and again
in the `e2e` workspace member [[frontend/e2e/package.json]]. Config:
[[frontend/e2e/playwright.config.ts]]. Two spec files only —
[[frontend/e2e/storefront.spec.ts]] and [[frontend/e2e/a11y.spec.ts]].

**It tests the built apps, not the dev server.** `webServer` starts `vite preview` for
storefront on `:4173` and manage on `:4174` with `--strictPort`, so `pnpm -r build` must have run
first; the `e2e` target in [[Makefile]] and the `e2e` job in [[.github/workflows/ci.yml]] both do
build → `playwright install --with-deps chromium` → `pnpm e2e`. One project, chromium only, and
`locale: "he-IL"` — the Hebrew locale is part of the fixture, not a nicety.

`e2e` is listed explicitly (not by glob) in [[frontend/pnpm-workspace.yaml]], which is what puts
its specs under `pnpm -r lint` and `pnpm -r typecheck`.

**Trap.** Nothing in [[frontend/e2e/a11y.spec.ts]] intercepts the API, deliberately: with no
backend on `:8000` the storefront must still be a valid, navigable, accessible document, and the
suite asserts the failure copy is Hebrew rather than the server's English sentence. Which of the
two upstream failures occurs depends on the machine, so no test may pin the exact message.

## Related

- [[Accessibility Compliance]] · [[Vitest]] · [[RTL And Bidi Isolation]] · [[Vite]]
