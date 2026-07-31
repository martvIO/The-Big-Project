---
tags: [frontend, build, vite, dev-server, tooling]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: entity
applicability: n/a
---

# Vite

**Purpose.** Dev server and production bundler for both apps. Vite 8.1.5 (rolldown-based), with `@vitejs/plugin-react` and `@tailwindcss/vite`.

**Vite never type-checks.** Each app's `build` script is `tsc --noEmit && vite build` — see [[frontend/apps/storefront/package.json]] and [[frontend/apps/manage/package.json]]. Drop the first half and type errors ship.

**`changeOrigin: false` in the dev proxy is load-bearing.** Both [[frontend/apps/storefront/vite.config.ts]] and [[frontend/apps/manage/vite.config.ts]] forward API calls to `localhost:8000` with the **original `Host` header preserved**, because the backend resolves the tenant from that header — rewriting it makes every storefront request answer `404 TENANT_NOT_FOUND`, and breaks host-only cookies for the console. For the same reason `allowedHosts: [".localtest.me"]` is set: development happens at `http://{slug}.localtest.me:5173`, and Vite's host check only permits `localhost` by default. The storefront proxies `/storefront` and `/health` only — it never calls the owner console.

Configuration for [[Tailwind CSS]] is a plugin, not a config file: there is no `tailwind.config.js` and no PostCSS config in this repo.

Note that the app `vite.config.ts` files are **not** used for tests. [[Vitest]] reads its own standalone `vitest.config.ts` per package, on purpose — the dev proxy and dev plugins have no business in the test pipeline.
