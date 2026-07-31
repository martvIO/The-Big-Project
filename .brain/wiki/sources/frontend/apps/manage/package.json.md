---
tags: [frontend, manage, config, pnpm, vite, vitest, oxlint, dependencies]
sources: [frontend/apps/manage/package.json]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/package.json
blob: a475f27b5d45d23642e01aa4929e4e7daaefd9d4
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: config
applicability: active
---

# frontend/apps/manage/package.json

**Role.** The owner console's workspace manifest — `name: manage`, private, ESM. It declares exactly one workspace dependency ([[frontend/packages/ui/package.json]] as `@boutique/ui`, `workspace:*`) and, notably, **no `@boutique/api-client`**: the console hand-writes its typed fetch layer in [[frontend/apps/manage/src/api.ts]]. The six scripts are what the root `Makefile` fans out to with `pnpm -r`.

**Module.** [[frontend/apps/manage/_index]] · **Layer.** platform

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `dev` | script | `vite` — README documents port 5173 for this app; the storefront is started on 5174 by `make fe-dev` |
| `build` | script | `tsc --noEmit && vite build` — typecheck **gates** the build; a type error fails `make fe-build` |
| `preview` | script | `vite preview` — what [[frontend/e2e/playwright.config.ts]] serves on 4174 |
| `lint` | script | `oxlint -c ../../.oxlintrc.json src` — the explicit `-c` is mandatory (see Behavior) |
| `typecheck` | script | `tsc --noEmit` |
| `test` | script | `TZ=America/New_York vitest run` — a deliberately wrong timezone (see Behavior) |

## Behavior

**`TZ=America/New_York` on the test script is a trap, on purpose.** Every date and time in this product renders through a Jerusalem-zoned `Intl` formatter, and a bare `new Date()` read of "today" is a bug. Running the suite in the machine's own zone would make that bug invisible on an Israeli or CI-UTC box; running it 7 hours behind Jerusalem puts the local calendar day on the *other side* of midnight for a large part of the day, so an unzoned read fails loudly in [[frontend/apps/manage/src/__tests__/jerusalem.test.ts]]. Do not "fix" this by removing the prefix.

**`oxlint -c ../../.oxlintrc.json` must keep its `-c`.** oxlint's zero-config default does not enable the react plugin, so a conditionally-called hook lints clean. The shared [[frontend/.oxlintrc.json]] turns on `react/rules-of-hooks: error` — dropping the flag silently removes that guardrail while the command still exits 0.

`build` runs `tsc --noEmit` *before* `vite build` because Vite's transform strips types without checking them; without the gate an app with type errors ships. The dependency set is small and intentional: React 19 + `i18next`/`react-i18next` for the Hebrew bundle, and `@boutique/ui` for every primitive. `axe-core` is a devDependency **here but not in the storefront** — three manage component tests ([[frontend/apps/manage/src/__tests__/StaffSection.test.tsx]], [[frontend/apps/manage/src/__tests__/BookingsSection.test.tsx]], [[frontend/apps/manage/src/__tests__/BookingDetail.test.tsx]]) run axe inside jsdom rather than deferring every a11y check to Playwright. Tailwind arrives as the `@tailwindcss/vite` plugin (Tailwind 4 has no PostCSS step here).

Versions are pinned by [[frontend/pnpm-lock.yaml]]; the ranges here are caret ranges and are not the installed truth.

## Depends On

- [[frontend/packages/ui/package.json]] — `@boutique/ui`, `workspace:*`
- [[frontend/.oxlintrc.json]] — referenced by relative path in `lint`
- [[React]] · [[Vite]] · [[Vitest]] · [[Tailwind CSS]] · [[TypeScript]] · [[Testing Library]] · [[i18next]] · [[oxlint]] · [[pnpm]]

## Depended On By

- [[frontend/pnpm-workspace.yaml]] — matches this package into the workspace
- [[Makefile]] — `fe-build` / `fe-test` / `lint` fan out over it with `pnpm -r`
- [[frontend/e2e/playwright.config.ts]] — `pnpm --filter manage preview`
- [[.github/workflows/ci.yml]]

## Concepts

- [[Jerusalem Time]]
- [[Accessibility Compliance]]

## Notes

There is no `@boutique/api-client` dependency and there never was — [[frontend/packages/api-client/src/index.ts]] is a deliberately empty stub whose header records why OpenAPI codegen was declined. Both apps hand-write `src/api.ts`.

Spec: [[.planning/specs/repo-scaffolds-and-ci.md]].
