---
tags: [frontend, manage, config, vite, tenancy, dev-proxy, tailwind]
sources: [frontend/apps/manage/vite.config.ts]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/vite.config.ts
blob: ff1b05d851cc0c4b8bdb8ea4e0e08d240c61ab7e
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: config
applicability: active
---

# frontend/apps/manage/vite.config.ts

**Role.** Two plugins (`@vitejs/plugin-react`, `@tailwindcss/vite`) and a dev server whose entire job is to make `http://{slug}.localtest.me:5173` behave in development exactly like the same-origin production deployment: `allowedHosts: [".localtest.me"]` gets past Vite's host check, and a **`changeOrigin: false`** proxy forwards `/manage` and `/health` to `localhost:8000` with the tenant's Host header intact.

**Module.** [[frontend/apps/manage/_index]] · **Layer.** platform

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| default export | config | `defineConfig({ plugins, server })` — no `build`, `resolve`, `test` or `base` overrides |
| `server.allowedHosts` | option | `[".localtest.me"]` — wildcard-DNS dev domain, so `{slug}.localtest.me` resolves to 127.0.0.1 with a real subdomain |
| `server.proxy["/manage"]` | option | `→ http://localhost:8000`, `changeOrigin: false` |
| `server.proxy["/health"]` | option | `→ http://localhost:8000`, `changeOrigin: false` |

## Behavior

**`changeOrigin: false` is the load-bearing setting and the one most likely to be "fixed" by someone who has seen it default to `true` everywhere else.** The backend resolves the tenant from the Host header; rewriting it to `localhost:8000` would strip the slug and every proxied request would answer `TENANT_NOT_FOUND`. The same flag also keeps host-only session cookies scoped to `{slug}.localtest.me`, which is what makes the dev login flow match production. [[frontend/apps/storefront/vite.config.ts]] repeats the pattern for `/storefront` and carries the fuller comment.

The proxy table is an allowlist of exactly the two prefixes this app calls. It does **not** proxy `/storefront`, and the storefront config does not proxy `/manage` — the two consoles never call each other's surface, and the asymmetry is the enforcement. `/health` is proxied so a dev can hit the backend liveness check through the same origin.

Production needs none of this: both apps are served same-origin behind the backend, so there is no CORS configuration anywhere and none must ever be added — a CORS header would be the signal that the same-origin invariant has been broken. No port is pinned here; 5173 is Vite's default and is the console's documented port, while `make fe-dev` starts the storefront on 5174 so both can run at once.

Nothing about tests lives here — [[frontend/apps/manage/vitest.config.ts]] is a separate file on purpose, because the react/tailwind dev plugins and this proxy have no business in the test pipeline.

## Depends On

- [[Vite]] — `defineConfig`
- [[React]] — `@vitejs/plugin-react`
- [[Tailwind CSS]] — `@tailwindcss/vite` (Tailwind 4, no PostCSS step)
- [[frontend/apps/manage/package.json]] — declares all three

## Depended On By

- [[frontend/apps/manage/package.json]] — `dev`, `build`, `preview`
- [[frontend/apps/manage/tsconfig.json]] — explicitly included so this file is typechecked

## Concepts

- [[Tenant Resolution]]
- [[Tenant Isolation]]

## Notes

Same-origin in production is a stated invariant, not an accident — see [[.planning/specs/subdomain-routing.md]] and [[.planning/specs/staging-and-external-apps.md]].
