---
tags: [frontend, storefront, package-manifest, pnpm, workspace, vite, i18n]
sources: [frontend/apps/storefront/package.json]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/package.json
blob: 778ed96f3db29e4ca261defbfcdbfe947cc11c0a
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: config
applicability: active
---

# frontend/apps/storefront/package.json

**Role.** The manifest for the public, anonymous, per-tenant boutique site — a private pnpm workspace member named `storefront`, with five runtime dependencies and six scripts. It is the file that decides this app owns the React copy, ships i18next, and does **not** consume the api-client package.

**Module.** [[frontend/apps/storefront/_index]] · **Layer.** frontend / app manifest

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `name` | field | `storefront` — the `pnpm --filter storefront` selector used by the [[Makefile]] and [[frontend/e2e/playwright.config.ts]] |
| `private: true` · `type: module` | fields | never published; ESM everywhere |
| `scripts.dev` | script | bare `vite` — the port comes from the caller, not from here |
| `scripts.build` | script | `tsc --noEmit && vite build` — the typecheck gates the bundle |
| `scripts.preview` | script | `vite preview`, what the e2e suite serves |
| `scripts.lint` | script | `oxlint -c ../../.oxlintrc.json src` — the shared config, never oxlint's default |
| `scripts.typecheck` | script | `tsc --noEmit` |
| `scripts.test` | script | `TZ=America/New_York vitest run` |
| `dependencies` | field | `@boutique/ui` (workspace), `i18next`, `react-i18next`, `react`, `react-dom` |
| `devDependencies` | field | Vite 8 + `@vitejs/plugin-react`, Tailwind 4 + `@tailwindcss/vite`, Vitest 4 + jsdom, Testing Library, oxlint, TypeScript |

## Behavior

**`TZ=America/New_York` on the test script is deliberate sabotage of the device clock.** The product is Jerusalem-zoned; running the suite in a zone that is a *different calendar day* from Jerusalem for part of every day means an unzoned `new Date()` read produces a failing assertion instead of a quietly passing one. The same pin appears in [[frontend/packages/ui/package.json]] and [[frontend/apps/manage/package.json]]. It is the runtime half of a rule [[frontend/scripts/qa-greps.sh]] also enforces statically — and running `vitest` directly instead of through `pnpm test` bypasses it entirely.

**This app depends on i18next while [[frontend/packages/ui/_index]] deliberately does not.** Every string a UI component renders arrives as a prop; the translation lookup happens here, in the app, against [[frontend/apps/storefront/src/i18n/he.ts]]. That split is the reason `@boutique/ui` has no i18next entry of its own, and adding one to the library would be the first step to a component rendering Hebrew it was never handed.

**`@boutique/api-client` is absent from the dependency list, and that absence is the design.** The workspace does contain [[frontend/packages/api-client/src/index.ts]], but it is an empty stub whose header records why codegen was declined; this app hand-writes its typed fetch layer in [[frontend/apps/storefront/src/api.ts]]. Adding the dependency here would be the visible half of reversing that decision.

`lint` passes `-c ../../.oxlintrc.json` explicitly because oxlint's zero-config default does **not** enable the react plugin — a conditionally-called hook would lint clean without it. `build` runs `tsc --noEmit` first so a type error fails the build rather than shipping a bundle Vite happily produced. Unlike [[frontend/apps/manage/package.json]], there is no `axe-core` devDependency: this app's [[frontend/apps/storefront/src/__tests__/accessibility.test.tsx]] asserts document semantics with Testing Library, and the axe scan for the storefront lives in [[frontend/e2e/a11y.spec.ts]] against a real browser.

The `dev` script carries no `--port`, so `pnpm dev` here would take Vite's default 5173 — the same port the console documents as its own. The [[Makefile]] target is what supplies `--port 5174`.

## Depends On

- [[frontend/packages/ui/package.json]] — `workspace:*`
- [[React]] · [[Vite]] · [[Tailwind CSS]] · [[Vitest]] · [[jsdom]] · [[Testing Library]] · [[TypeScript]]
- [[i18next]] — plus `react-i18next`
- [[oxlint]] — via [[frontend/.oxlintrc.json]]

## Depended On By

- [[frontend/pnpm-workspace.yaml]] — matched by the `apps/*` glob
- [[frontend/pnpm-lock.yaml]]
- [[frontend/e2e/playwright.config.ts]] — `pnpm --filter storefront preview --port 4173`
- [[Makefile]] — the dev target
- [[.github/workflows/ci.yml]] — reached through `pnpm -r lint|typecheck|test|build`

## Concepts

- [[Jerusalem Time]]

## Tests

- Everything under `frontend/apps/storefront/src/__tests__/` runs through `scripts.test`, e.g. [[frontend/apps/storefront/src/__tests__/router.test.tsx]]

## Notes

CI runs `pnpm -r --if-present test`, so deleting the `test` script here would drop the whole storefront suite from CI without turning anything red.
