---
tags: [frontend, storefront, react, app-shell]
sources: [frontend/apps/storefront/src/App.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/App.tsx
blob: f59606aed9283438d4626bf594d581ea0c093d56
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/storefront/src/App.tsx

**Role.** Three nested elements and no logic: `ToastProvider` → `StorefrontLayout` → `Router`. The whole file exists to fix that **nesting order**, and the order is load-bearing in both directions.

**Module.** [[frontend/apps/storefront/src/_index]] · **Layer.** app shell

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `App` | component | no props — the root [[frontend/apps/storefront/src/main.tsx]] renders |

## Behavior

`StorefrontLayout` sits **above** `Router`, not inside a route. That is why the hand-rolled router in [[frontend/apps/storefront/src/router.tsx]] never needed nested routes: `/book/{step}` already renders inside the header/footer shell, the `<main id="content" tabindex="-1">` the router focuses after every navigation is mounted once and survives every route change, and the layout's single `/storefront/boutique` fetch runs once per page load rather than per route. Reordering these two would remount the shell (and refetch the boutique) on every client navigation, and would break the router's `document.getElementById(MAIN_ID)?.focus()` on the first navigation after a route swap.

`ToastProvider` is outermost so a toast raised from any page — [[frontend/apps/storefront/src/components/ShareButton.tsx]]'s "הקישור הועתק" is the live case — outlives the route that raised it and is not unmounted by the navigation that follows.

## Depends On

- [[frontend/packages/ui/src/components/Toast.tsx]] — `ToastProvider`, re-exported through [[frontend/packages/ui/src/index.ts]]
- [[frontend/apps/storefront/src/components/StorefrontLayout.tsx]] — header, footer, skip link, `<main>`, boutique context
- [[frontend/apps/storefront/src/router.tsx]] — `Router`

## Depended On By

- [[frontend/apps/storefront/src/main.tsx]]

## Tests

No test mounts `App` itself. [[frontend/apps/storefront/src/__tests__/router.test.tsx]] and [[frontend/apps/storefront/src/__tests__/StorefrontLayout.test.tsx]] cover the two halves separately, and [[frontend/apps/storefront/src/__tests__/accessibility.test.tsx]] runs axe over the composed pages.

## Notes

Contrast with [[frontend/apps/manage/src/App.tsx]], which carries the console's entire session bootstrap and section switch. The storefront's equivalent state lives in `StorefrontLayout` (boutique) and in each route (its own fetch), so this file stays a wiring diagram.
