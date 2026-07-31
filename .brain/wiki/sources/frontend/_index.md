---
tags: [frontend, typescript]
sources: [frontend]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend
blob: 1cfc71a3e0a3f9f2dca6bf5809f309c3f237fa39
commit: 13d107b8b16f1f2676f1cdb1c994f95822fe2ba0
kind: directory
applicability: active
---

# frontend/

**Purpose.** The pnpm workspace: two Vite SPAs and the packages they share. No Next.js, despite what `.claude/` claims.

**Parent.** _(repository root)_

## Files

- [[frontend/.oxlintrc.json]]
- [[frontend/package.json]]
- [[frontend/pnpm-lock.yaml]]
- [[frontend/pnpm-workspace.yaml]]
- [[frontend/tsconfig.base.json]]

## Subdirectories

- [[frontend/apps/_index]] — The two shipped applications — the public storefront and the authenticated owner console.
- [[frontend/e2e/_index]] — Playwright: journey specs and the axe accessibility specs, run against `vite preview` of both built apps with no backend.
- [[frontend/packages/_index]] — The shared workspace packages.
- [[frontend/scripts/_index]]
