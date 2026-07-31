---
tags: [frontend, storefront, vite, config, dev-proxy, tenancy, tailwind]
sources: [frontend/apps/storefront/vite.config.ts]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/vite.config.ts
blob: a47ab8a72c94ae9e4200898fe698cc9d29079ac5
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: config
applicability: active
---

# frontend/apps/storefront/vite.config.ts

**Role.** The build and dev-server config: two plugins (React, Tailwind 4), a host allowlist for the wildcard-DNS dev domain, and a two-entry dev proxy whose `changeOrigin: false` is what makes multi-tenant development work at all. Nothing here affects the test run — that is [[frontend/apps/storefront/vitest.config.ts]].

**Module.** [[frontend/apps/storefront/_index]] · **Layer.** frontend / build config

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| default export | config | `defineConfig` from `vite` |
| `plugins` | field | `react()` and `tailwindcss()` — Tailwind 4 runs as a Vite plugin, not a PostCSS step |
| `server.allowedHosts` | field | `[".localtest.me"]` |
| `server.proxy["/storefront"]` | field | → `http://localhost:8000`, `changeOrigin: false` |
| `server.proxy["/health"]` | field | → `http://localhost:8000`, `changeOrigin: false` |

## Behavior

**`changeOrigin: false` is load-bearing and the file says so.** The backend resolves the tenant from the `Host` header, so letting the proxy rewrite it to `localhost:8000` would make every storefront request answer `404 TENANT_NOT_FOUND` — a failure that looks like a data problem and is actually a proxy setting. Keeping the original `{slug}.localtest.me` Host is also what makes the host-only session cookie behave in dev exactly as in production. `allowedHosts: [".localtest.me"]` is the necessary companion: Vite's dev-server host check accepts only localhost by default and would reject the subdomain before the proxy ever ran.

Both apps are same-origin with the API in production and proxied in dev, which is precisely why **CORS must never be added for either**. `*.localtest.me` resolves to `127.0.0.1` by public wildcard DNS, so tenant subdomains need no `/etc/hosts` editing.

**The absence of a `/manage` proxy entry is an assertion, not an omission** — the file states it in a comment. The storefront is the anonymous public surface; a `/manage` route reaching the owner console API from here would be a privilege boundary crossed in a build config. [[frontend/apps/manage/vite.config.ts]] holds the mirror-image entry and no `/storefront` one.

No `build` block, no `base`, no `server.port`, no `define`: the app builds to the default `dist/` at the default `/` base and takes its port from the caller. `vite preview` inherits the same proxy config, which is why [[frontend/e2e/a11y.spec.ts]] can note that its no-data pass hits a real `:8000` (or nothing) rather than a mock.

## Depends On

- [[Vite]]
- [[React]] — via `@vitejs/plugin-react`
- [[Tailwind CSS]] — via `@tailwindcss/vite`; the stylesheet entry is [[frontend/apps/storefront/src/index.css]]
- [[frontend/apps/storefront/index.html]] — the implicit build entry

## Depended On By

- [[frontend/apps/storefront/package.json]] — `dev`, `build`, `preview`
- [[frontend/apps/storefront/tsconfig.json]] — named in `include`, so this file is typechecked

## Concepts

- [[Tenant Resolution]]

## Notes

**Stale comment.** The header says "Develop at `http://{slug}.localtest.me:5173`", but 5173 is the **console's** documented port: the [[Makefile]] runs this app with `--port 5174`, and [[README.md]] states 5173 for manage / 5174 for the storefront. Since `scripts.dev` sets no port, running `pnpm dev` in this directory really does land on 5173 (or whatever Vite finds free), so the comment is only true when the Makefile is bypassed. Follow the Makefile.
