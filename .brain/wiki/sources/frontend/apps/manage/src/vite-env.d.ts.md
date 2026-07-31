---
tags: [frontend, manage, typescript, ambient-types, vite]
sources: [frontend/apps/manage/src/vite-env.d.ts]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/src/vite-env.d.ts
blob: 11f02fe2a0061d6e6e1f271b21da95423b448b32
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/manage/src/vite-env.d.ts

**Role.** One line — `/// <reference types="vite/client" />` — which is what makes `import.meta.env`, and imports of `.css` / `.svg` / `?url` assets, typecheck in this app.

**Module.** [[frontend/apps/manage/src/_index]] · **Layer.** build

## Behavior

Ambient declarations only; it emits nothing and is never imported. Deleting it does not break the dev server or the production build (Vite transforms those imports regardless) — it breaks `tsc`, which is run as part of the app's build script, so the failure shows up as type errors on asset imports rather than at runtime. The equivalent file exists per app; this one covers only the `manage` compilation unit.

## Depends On

- [[Vite]] — the `vite/client` type package

## Depended On By

Nothing imports it. It is picked up by the `include` glob in [[frontend/apps/manage/tsconfig.json]].
