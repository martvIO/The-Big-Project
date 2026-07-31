---
tags: [frontend, react, ui, spa]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: entity
applicability: n/a
---

# React

**Purpose.** The view layer for both frontend apps. React 19.2.7, rendered as a plain client-side SPA by [[Vite]]. There is **no Next.js here** — no SSR, no App Router, no server components — despite what `.claude/rules/frontend-react/` says; see [[Documented Stack Vs Actual Stack]].

**Neither app uses a routing library.** [[frontend/apps/storefront/src/router.tsx]] hand-rolls one in ~90 lines: a closed `RouteName` union, `useSyncExternalStore` over `popstate` plus a custom `storefront:navigation` event that `pushState` dispatches by hand, and a per-route document-title effect. [[frontend/apps/manage/src/App.tsx]] has no router at all — it swaps sections from a single `useState<SectionKey>`, so the console has one URL.

Mount is identical in both: `createRoot` inside `<StrictMode>` in [[frontend/apps/storefront/src/main.tsx]] and [[frontend/apps/manage/src/main.tsx]], after a hard throw if `#root` is missing.

The surface used is deliberately small — `useState` / `useEffect` / `useCallback` / `useSyncExternalStore`. There is no `forwardRef` anywhere (React 19 passes `ref` as a plain prop), and no `useTransition`, `useOptimistic` or `useActionState`. [[frontend/packages/ui/package.json]] declares `react` and `react-dom` as **peer** dependencies `^19`; only the apps carry the real copy. Strings come from [[i18next]] via `react-i18next` — but never inside `packages/ui`, which takes every string as a prop.
