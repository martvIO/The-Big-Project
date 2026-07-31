---
tags: [frontend, typescript]
sources: [frontend/apps/manage]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage
blob: bfaaaa7bccce3b6bc6f7a951b399cc76b5bcfb15
commit: 13d107b8b16f1f2676f1cdb1c994f95822fe2ba0
kind: directory
applicability: active
---

# frontend/apps/manage/

**Purpose.** The owner and shift-manager console. Cookie-authenticated against `/manage`, Hebrew-only, and deliberately router-less.

**Parent.** [[frontend/apps/_index]]

## Files

- [[frontend/apps/manage/index.html]] — Vite's entry document for the owner console — and the only place four otherwise-invisible contracts are declared: the document is Hebrew RTL (`lang="he" dir="rtl"` on `<html>`, not toggled at runtime), the viewport meta does **not**…
- [[frontend/apps/manage/package.json]] — The owner console's workspace manifest — `name: manage`, private, ESM. It declares exactly one workspace dependency ([[frontend/packages/ui/package.json]] as `@boutique/ui`, `workspace:*`) and, notably, **no `@boutique/api-client`**: the…
- [[frontend/apps/manage/tsconfig.json]] — A four-line manifest that adds nothing but an `include` list: every compiler option comes from [[frontend/tsconfig.base.json]], so the console cannot quietly relax `strict`, `noUnusedLocals` or `noUnusedParameters` for itself.
- [[frontend/apps/manage/vite.config.ts]] — Two plugins (`@vitejs/plugin-react`, `@tailwindcss/vite`) and a dev server whose entire job is to make `http://{slug}.localtest.me:5173` behave in development exactly like the same-origin production deployment: `allowedHosts…
- [[frontend/apps/manage/vitest.config.ts]] — A deliberately standalone test config — `jsdom` environment plus one setup file — that does **not** extend [[frontend/apps/manage/vite.config.ts]], because that file carries the tenant dev proxy and the react/tailwind dev plugins, none of…

## Subdirectories

- [[frontend/apps/manage/public/_index]] — Static assets served as-is.
- [[frontend/apps/manage/src/_index]] — The console source. `App.tsx` is the whole navigation model — a single `useState` over section keys, with no router and no URL.
