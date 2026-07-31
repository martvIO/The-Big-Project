---
tags: [frontend, typescript]
sources: [frontend/apps/storefront]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront
blob: 518fc1a88f38b21415cc5cb0b99c789e950f6584
commit: 13d107b8b16f1f2676f1cdb1c994f95822fe2ba0
kind: directory
applicability: active
---

# frontend/apps/storefront/

**Purpose.** The public per-tenant boutique site: catalogue, dress pages, the booking flow, and the tokenized manage-booking page.

**Parent.** [[frontend/apps/_index]]

## Files

- [[frontend/apps/storefront/index.html]] — Vite's entry document for the public boutique site, and the only place three otherwise-invisible contracts are declared: the document is Hebrew RTL (`lang="he" dir="rtl"` on `<html>`, never toggled at runtime), the viewport meta does…
- [[frontend/apps/storefront/package.json]] — The manifest for the public, anonymous, per-tenant boutique site — a private pnpm workspace member named `storefront`, with five runtime dependencies and six scripts. It is the file that decides this app owns the React copy, ships i18next…
- [[frontend/apps/storefront/tsconfig.json]] — A two-line tsconfig: extend the workspace base and compile `src` plus the app's own two config files. It declares no compiler option of its own, so the storefront inherits exactly the `strict`, `noUnusedLocals`/`noUnusedParameters`, `jsx…
- [[frontend/apps/storefront/vite.config.ts]] — The build and dev-server config: two plugins (React, Tailwind 4), a host allowlist for the wildcard-DNS dev domain, and a two-entry dev proxy whose `changeOrigin: false` is what makes multi-tenant development work at all. Nothing here…
- [[frontend/apps/storefront/vitest.config.ts]] — A standalone Vitest config that sets exactly two things — the `jsdom` environment and the setup file — and deliberately does **not** reuse [[frontend/apps/storefront/vite.config.ts]], so the dev proxy and the Tailwind/React dev plugins…

## Subdirectories

- [[frontend/apps/storefront/public/_index]] — Static assets, including the `robots.txt` that keeps unlaunched boutiques out of search results.
- [[frontend/apps/storefront/src/_index]] — The storefront source, including a hand-rolled router — there is no routing library.
