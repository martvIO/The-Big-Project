---
tags: [frontend, tooling, monorepo, package-manager, ci]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: entity
applicability: n/a
---

# pnpm

**Purpose.** Package manager and workspace runner for the whole frontend. Version pinned as `"packageManager": "pnpm@10.34.5"` in [[frontend/package.json]]; `frontend/pnpm-lock.yaml` is `lockfileVersion: '9.0'`. The backend uses [[uv]] instead — the two halves share nothing but the [[Makefile]].

**The workspace has one non-obvious member.** [[frontend/pnpm-workspace.yaml]] lists `apps/*`, `packages/*`, and then **`e2e` explicitly, not as a glob** — being a member is precisely what puts the Playwright specs under `pnpm -r lint` and `pnpm -r typecheck`. Drop it back into a glob-only list and the e2e suite silently stops being checked.

**Everything runs recursively.** [[Makefile]] and [[.github/workflows/ci.yml]] both drive `pnpm -r lint`, `pnpm -r typecheck`, `pnpm -r --if-present test`, `pnpm -r build`. The `--if-present` is required: `packages/api-client` and `e2e` have no `test` script, and a bare `pnpm -r test` would fail on them. Only the root `frontend/package.json` owns the `e2e` script and the Playwright devDependencies.

Internal deps use the protocol form `"@boutique/ui": "workspace:*"`. That symlink is why [[frontend/packages/ui/src/theme.css]] needs an explicit `@source "../src"` — [[Tailwind CSS]] would otherwise treat the linked package as `node_modules` and scan none of it.
