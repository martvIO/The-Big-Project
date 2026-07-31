---
tags: [frontend, tooling, lint, ci]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: entity
applicability: n/a
---

# oxlint

**Purpose.** The only JavaScript/TypeScript linter here — there is no ESLint, no Prettier and no
`eslint-plugin-react-hooks`. Version `^1.71.0`, a devDependency of all five workspace members,
each with the same script shape: `oxlint -c ../../.oxlintrc.json src` (the `e2e` member uses
`-c ../.oxlintrc.json .`). Run repo-wide by `pnpm -r lint` from [[Makefile]] and
[[.github/workflows/ci.yml]].

**The config is three rules, and one of them is why the file exists.**
[[frontend/.oxlintrc.json]] enables the `react` and `oxc` plugins and sets
`react/rules-of-hooks` to `error`. oxlint's zero-config default does not turn the react plugin
on, so a conditionally-called hook lints clean with no config — the single most expensive class
of React bug in the repo passing silently. The second rule, `react/only-export-components` with
`allowConstantExport`, guards Fast Refresh in [[Vite]].

**Trap.** The `-c` flag is not optional. oxlint looks for its config relative to the working
directory, and each script runs from its own package directory — which contains no
`.oxlintrc.json`. A new package whose `lint` script is a bare `oxlint src` will report zero
problems while enforcing none of the above. Copy the script from
[[frontend/apps/storefront/package.json]] rather than writing it fresh.

Formatting is not oxlint's job here and nothing enforces it on the frontend; the backend's
equivalent is `ruff format --check`.

## Related

- [[Vite]] · [[TypeScript]] · [[React]]
