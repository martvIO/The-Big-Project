---
tags: [frontend, ui, package-manifest, pnpm, workspace, fonts]
sources: [frontend/packages/ui/package.json]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/package.json
blob: 76dca59cc3059431526edebcead460d7330e75d3
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: config
applicability: active
---

# frontend/packages/ui/package.json

**Role.** The manifest for `@boutique/ui`, the shared component library. It publishes **source, not a build** — `main`, `types` and the `.` export all point at `src/index.ts`, so the consuming app's Vite/TS pipeline compiles the TSX. There is no `build` script and no `dist/`.

**Module.** [[frontend/packages/ui/_index]] · **Layer.** frontend / shared library

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `name` | field | `@boutique/ui` — the workspace specifier both apps import |
| `private: true` | field | never published to a registry; it exists only inside the pnpm workspace |
| `exports["."]` | field | `./src/index.ts` — see [[frontend/packages/ui/src/index.ts]] |
| `exports["./theme.css"]` | field | the **second** entry point: [[frontend/packages/ui/src/theme.css]], imported by each app's `index.css` |
| `scripts.lint` | script | `oxlint -c ../../.oxlintrc.json src` — the shared config, not oxlint's zero-config default |
| `scripts.typecheck` | script | `tsc --noEmit` |
| `scripts.test` | script | `TZ=America/New_York vitest run` |
| `peerDependencies` | field | `react`/`react-dom` `^19` — the app owns the React copy |
| `dependencies` | field | `@fontsource/frank-ruhl-libre`, `@fontsource/assistant` — the only runtime deps |

## Behavior

**The two runtime dependencies are the whole story, and one absence is louder than both.** The Fontsource packages are real `dependencies` because [[frontend/packages/ui/src/theme.css]] `@import`s specific per-weight CSS files from them; self-hosting is what keeps Hebrew off a runtime Google Fonts fetch. There is **no i18n dependency**, and that is load-bearing rather than an oversight — every component in this package takes its strings as props, so an i18next import here would be the first step to a component that renders Hebrew it was never given (see [[frontend/packages/ui/src/index.ts]]).

**`TZ=America/New_York` on the test script is deliberate sabotage of the device clock.** The product is Jerusalem-zoned; running the suite in a zone that is a *different calendar day* from Jerusalem for part of every day means an unzoned `new Date()` read produces a wrong assertion instead of a passing one. The same pin appears in [[frontend/apps/storefront/package.json]] and [[frontend/apps/manage/package.json]]. It is the runtime half of the rule that [[frontend/scripts/qa-greps.sh]] enforces statically and [[frontend/packages/ui/src/lib/hours.ts]] implements.

`lint` passes `-c ../../.oxlintrc.json` explicitly: oxlint's zero-config default does **not** enable the react plugin, so a conditionally-called hook would lint clean. React is a peer dependency *and* a devDependency — peer so the app supplies the single React instance (two copies break hooks), dev so `vitest run` and `tsc` have something to resolve here.

## Depends On

- [[React]] — peer, `^19`
- [[Vitest]] — test runner; config in [[frontend/packages/ui/vitest.config.ts]]
- [[Testing Library]] — `@testing-library/react` + `jest-dom`, wired in [[frontend/packages/ui/src/test/setup.ts]]
- [[jsdom]] — test environment
- [[oxlint]] — via [[frontend/.oxlintrc.json]]
- [[TypeScript]] — via [[frontend/packages/ui/tsconfig.json]]
- [[Fontsource]] — self-hosted Hebrew-covering faces

## Depended On By

- [[frontend/apps/storefront/package.json]]
- [[frontend/apps/manage/package.json]]
- [[frontend/pnpm-workspace.yaml]]
- [[frontend/pnpm-lock.yaml]]

## Concepts

- [[Design Tokens]]
- [[Jerusalem Time]]

## Tests

- [[frontend/packages/ui/src/__tests__/tokens.test.ts]] — reads `src/theme.css` via `process.cwd()`, which only resolves because pnpm runs this script with cwd = package root

## Notes

No `build` script by design: a compiled `dist/` would need its own Tailwind pass, and [[frontend/packages/ui/src/theme.css]]'s `@source "../src"` glob points at the TSX sources precisely because the apps compile them.
