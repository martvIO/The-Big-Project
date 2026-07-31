---
tags: [frontend, storefront, react, entry-point]
sources: [frontend/apps/storefront/src/main.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/main.tsx
blob: 5a53d9d754f9c400af8e42a67687031ac47cabee
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/storefront/src/main.tsx

**Role.** The public site's browser entry point, named by the `<script type="module">` in [[frontend/apps/storefront/index.html]]: it mounts [[frontend/apps/storefront/src/App.tsx]] into `#root` under `StrictMode` and pulls in the two side-effect modules the app cannot start without.

**Module.** [[frontend/apps/storefront/src/_index]] · **Layer.** app shell

## Public Surface

None — the module is executed for its effects and exports nothing.

## Behavior

The two bare imports carry the weight. `import "./i18n"` runs `i18n.init()` before any component calls `useTranslation` — and before [[frontend/apps/storefront/src/validation.ts]], which calls `i18n.t()` at validation time rather than through a hook, can be reached. `import "./index.css"` is what pulls Tailwind and the shared theme into the bundle.

`document.getElementById("root")` is checked and **throws** rather than being force-unwrapped: a missing `#root` means the HTML shell and this file have diverged, and a thrown error at boot names that instead of surfacing later as a null-deref inside React. `StrictMode` double-invokes effects in development, which is exactly the hazard [[frontend/apps/storefront/src/router.tsx]]'s `handledPath` ref defends against — its navigation effect keys on the pathname rather than a boolean so a double-invoked effect does not read as a navigation and steal focus on first paint.

Nothing here sets `dir` or `lang`. Those are attributes on `<html lang="he" dir="rtl">` in [[frontend/apps/storefront/index.html]], so RTL is established before first paint rather than by a script.

## Depends On

- [[frontend/apps/storefront/src/App.tsx]]
- [[frontend/apps/storefront/src/i18n/index.ts]] — side-effect import; initialises i18next
- [[frontend/apps/storefront/src/index.css]] — side-effect import; Tailwind + theme
- [[React]] — `StrictMode`, `createRoot`

## Depended On By

- [[frontend/apps/storefront/index.html]] — via `<script type="module" src="/src/main.tsx">`

## Tests

None directly. Tests mount individual routes or [[frontend/apps/storefront/src/components/StorefrontLayout.tsx]] and import `../i18n` themselves.

## Notes

**Literally byte-identical** to [[frontend/apps/manage/src/main.tsx]] — same git blob. The relative imports (`./App`, `./i18n`, `./index.css`) resolve to different modules per app, so one file's text serves both entry points without either app depending on the other. Duplication, not a shared module: hoisting it would require a package that imports an app.
