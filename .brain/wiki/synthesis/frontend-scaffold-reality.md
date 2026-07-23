---
tags: [frontend, meta, react, vite]
sources: [frontend/package.json, frontend/pnpm-workspace.yaml, .planning/epics/ROADMAP.md]
created: 2026-07-23
updated: 2026-07-23
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: synthesis
applicability: n/a
---

# Frontend Scaffold Reality

**Purpose.** The frontend looks larger than it is. This page states exactly how much of it
exists, so nobody plans against imaginary code.

## What is actually there

25 tracked files under `frontend/`, of which **8 are TypeScript** and all 8 are scaffold-level:

| File | State |
|---|---|
| [[frontend/apps/storefront/src/App.tsx]] | stub |
| [[frontend/apps/storefront/src/main.tsx]] | Vite entry point |
| [[frontend/apps/storefront/vite.config.ts]] | config |
| [[frontend/apps/manage/src/App.tsx]] | stub |
| [[frontend/apps/manage/src/main.tsx]] | Vite entry point |
| [[frontend/apps/manage/vite.config.ts]] | config |
| [[frontend/packages/ui/src/index.ts]] | essentially empty |
| [[frontend/packages/api-client/src/index.ts]] | essentially empty |

The rest of the 25 is `package.json` files, `pnpm-lock.yaml`, `pnpm-workspace.yaml`, CSS, HTML
entry points, and lint/TS config. **There is no feature code yet.**

## Stack

pnpm 10 workspace · React 19 · Vite 8 · TypeScript 5.7 · Tailwind 4. Two apps (`storefront`,
`manage`) and two shared packages (`ui`, `api-client`).

**Not Next.js.** There is no `next` dependency anywhere and no App Router — see
[[Documented Stack Vs Actual Stack]]. Ignore [[.claude/commands/spartan/next-app.md]] and
[[.claude/commands/spartan/next-feature.md]] entirely.

## The dead scaffold

`frontend/App/` — roughly 747 files including its own `node_modules/` and a `.env` — is a
leftover from an earlier setup. It is git-ignored, absent from `pnpm-workspace.yaml`, and
referenced by no [[Makefile]] target. It is not the frontend. See [[Repo Hazards]] item 4.

## Where the real design lives

Feature 9 (the design system) passed its design gate on 2026-07-23 and is the next frontend
work. The artifacts are in `.planning/design/`:

- [[.planning/design/system/tokens.md]] — the AA-validated design tokens, the largest design doc
- [[.planning/design/system/components.md]] — component inventory
- [[.planning/design/screens/design-system/prototype.html]] — the RTL prototype
- [[.planning/design-config.md]] — brand, palette, fonts, locale, legal

The product is **Hebrew-first and right-to-left**. Any component work has to treat RTL as the
default direction, not as an afterthought.

## Lint guardrail

Per the frontend rules, an `.oxlintrc.json` enabling the `react` plugin with
`react/rules-of-hooks: error` is mandatory — oxlint's zero-config default does **not** catch
hooks violations, so a conditionally-called hook passes silently. Verify this is wired via
`oxlint -c` before trusting `make lint`.

## Related

- [[Documented Stack Vs Actual Stack]]
- [[Repo Hazards]]
- [[Planning Artifacts Vs Implementation]]
