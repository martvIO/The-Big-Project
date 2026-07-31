---
tags: [frontend, manage, react, entry-point]
sources: [frontend/apps/manage/src/main.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/src/main.tsx
blob: 5a53d9d754f9c400af8e42a67687031ac47cabee
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/manage/src/main.tsx

**Role.** The console's browser entry point, named by the `<script type="module">` in [[frontend/apps/manage/index.html]]: it mounts [[frontend/apps/manage/src/App.tsx]] into `#root` under `StrictMode`, and pulls in the two side-effect modules the app cannot start without.

**Module.** [[frontend/apps/manage/src/_index]] · **Layer.** app shell

## Public Surface

None — the module is executed for its effects and exports nothing.

## Behavior

The two bare imports are the load-bearing part. `import "./i18n"` runs `i18n.init()` before any component calls `useTranslation`, and `import "./index.css"` is what pulls Tailwind and the shared theme into the bundle. Import order matters only in that both must precede the `createRoot(...).render(...)` call, which they do by being module-level imports.

`document.getElementById("root")` is checked and **throws** rather than being force-unwrapped: a missing `#root` means the HTML shell and this file have diverged, and a thrown error at boot names that directly instead of surfacing later as a null-deref inside React. `StrictMode` double-invokes effects in development, which is why [[frontend/apps/manage/src/App.tsx]]'s bootstrap `useEffect` has to be idempotent (it is — `api.me()` is a plain read).

Nothing here sets `dir` or `lang`; those are attributes on the `<html>` element in [[frontend/apps/manage/index.html]] (`lang="he" dir="rtl"`), so RTL is established before the first paint rather than by a script.

## Depends On

- [[frontend/apps/manage/src/App.tsx]]
- [[frontend/apps/manage/src/i18n/index.ts]] — side-effect import; initialises i18next
- [[frontend/apps/manage/src/index.css]] — side-effect import; Tailwind + theme
- [[React]] — `StrictMode`, `createRoot`

## Depended On By

- [[frontend/apps/manage/index.html]] — via `<script type="module" src="/src/main.tsx">`

## Tests

None directly. The tests mount [[frontend/apps/manage/src/App.tsx]] or individual sections and import `../i18n` themselves.
