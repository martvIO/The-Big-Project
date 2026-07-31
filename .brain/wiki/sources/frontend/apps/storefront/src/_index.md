---
tags: [frontend, typescript]
sources: [frontend/apps/storefront/src]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src
blob: 7a10f1301933f8a650f40e1751d35fd15c995274
commit: 13d107b8b16f1f2676f1cdb1c994f95822fe2ba0
kind: directory
applicability: active
---

# frontend/apps/storefront/src/

**Purpose.** The storefront source, including a hand-rolled router — there is no routing library.

**Parent.** [[frontend/apps/storefront/_index]]

## Files

- [[frontend/apps/storefront/src/App.tsx]] — Three nested elements and no logic: `ToastProvider` → `StorefrontLayout` → `Router`.
- [[frontend/apps/storefront/src/api.ts]] — The storefront's whole backend contract in one file: a `fetch` wrapper that normalises the house error envelope into `ApiError`, two error→i18n-key mappers, the TypeScript mirror of every `/storefront/*` response shape, the thirteen…
- [[frontend/apps/storefront/src/index.css]] — Two `@import` lines and nothing else — Tailwind 4 followed by the shared theme. The public site has **no app-local CSS**: every colour, radius, shadow and font a bride sees comes from the design-token `@theme` block in…
- [[frontend/apps/storefront/src/main.tsx]] — The public site's browser entry point, named by the `<script type="module">` in [[frontend/apps/storefront/index.html]]: it mounts [[frontend/apps/storefront/src/App.tsx]] into `#root` under `StrictMode` and pulls in the two side-effect…
- [[frontend/apps/storefront/src/router.tsx]] — The entire routing layer of the public site, hand-rolled: a pure `matchRoute` path→`RouteMatch` function, a `useSyncExternalStore` binding over `history`, a `navigate()` with an explicit push/replace contract, a `<Link>`, **one delegated…
- [[frontend/apps/storefront/src/validation.ts]] — The client-side mirror of the booking form's server bounds — two length caps, two control-character classes, and the Israeli-mobile normalizer — so the bride sees an immediate Hebrew error instead of a round-trip 400. **The backend is the…

## Subdirectories

- [[frontend/apps/storefront/src/__tests__/_index]] — Vitest suites for the storefront, and the largest test surface in the repo.
- [[frontend/apps/storefront/src/components/_index]] — Storefront-only presentational components — the ones too site-specific to earn a place in `packages/ui`.
- [[frontend/apps/storefront/src/i18n/_index]] — Hebrew strings plus the untranslated Arabic bundle.
- [[frontend/apps/storefront/src/lib/_index]] — Pure helpers for contact links and opening-hours prose.
- [[frontend/apps/storefront/src/routes/_index]] — One component per route, wired by the hand-rolled router.
- [[frontend/apps/storefront/src/test/_index]] — Vitest setup.
