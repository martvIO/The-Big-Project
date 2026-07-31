---
tags: [frontend, typescript]
sources: [frontend/apps/manage/src]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/src
blob: 61ef21417021e61e109b2325a0f00bd94070041b
commit: 13d107b8b16f1f2676f1cdb1c994f95822fe2ba0
kind: directory
applicability: active
---

# frontend/apps/manage/src/

**Purpose.** The console source. `App.tsx` is the whole navigation model — a single `useState` over section keys, with no router and no URL.

**Parent.** [[frontend/apps/manage/_index]]

## Files

- [[frontend/apps/manage/src/App.tsx]] — The whole console in one component: the session bootstrap (`api.me()` on mount), the login/loading/authenticated three-way branch, the role→nav table, and the section switch. **There is no router** — `section` is a `useState<SectionKey>`…
- [[frontend/apps/manage/src/api.ts]] — The console's entire backend surface in one hand-written file: a `fetch` wrapper (`apiFetch`), the `ApiError` type every section catches, ~30 TypeScript interfaces mirroring the Python schemas **verbatim in snake_case**, and the `api`…
- [[frontend/apps/manage/src/index.css]] — Two `@import` lines and nothing else — Tailwind 4 followed by the shared theme. The console has **no app-local CSS**: every colour, radius, shadow and font in the owner console comes from the design-token `@theme` block in…
- [[frontend/apps/manage/src/main.tsx]] — The console's browser entry point, named by the `<script type="module">` in [[frontend/apps/manage/index.html]]: it mounts [[frontend/apps/manage/src/App.tsx]] into `#root` under `StrictMode`, and pulls in the two side-effect modules the…
- [[frontend/apps/manage/src/validation.ts]] — The console's client-side **mirror** of the backend's bounds and validators, in three blocks (boutique settings, catalog, staff) plus the shekel↔agorot money helpers. Every validator returns `string | null` — a ready-to-render Hebrew…
- [[frontend/apps/manage/src/vite-env.d.ts]] — One line — `/// <reference types="vite/client" />` — which is what makes `import.meta.env`, and imports of `.css` / `.svg` / `?url` assets, typecheck in this app.

## Subdirectories

- [[frontend/apps/manage/src/__tests__/_index]] — Vitest suites for the console, including the axe passes that carry F15's accessibility coverage — the console sits behind a login, so e2e cannot reach it.
- [[frontend/apps/manage/src/assets/_index]] — Brand artwork.
- [[frontend/apps/manage/src/components/_index]] — One component per console section, plus the booking sub-views. Four of the older sections hardcode their Hebrew; the newer ones route every string through i18n.
- [[frontend/apps/manage/src/i18n/_index]] — Hebrew strings, and the Arabic bundle that ships untranslated with the Hebrew standing in as placeholders.
- [[frontend/apps/manage/src/lib/_index]] — Pure helpers: the Jerusalem-zoned formatters and the shared booking view helpers that would otherwise close an import cycle.
- [[frontend/apps/manage/src/test/_index]] — Vitest setup, including the jsdom `<dialog>` stub the confirm modals need.
