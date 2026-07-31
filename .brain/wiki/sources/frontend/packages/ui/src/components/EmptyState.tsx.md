---
tags: [frontend, ui, react, display-primitive, empty-state]
sources: [frontend/packages/ui/src/components/EmptyState.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/components/EmptyState.tsx
blob: f2851b72b829d6bf09fcf47ebce92d23e48e9226
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/components/EmptyState.tsx

**Role.** The console's in-card "nothing here yet" block: a display-serif title, an optional body clamped to `max-w-prose`, and an optional caller-supplied action node, centred with `py-12`. Icon-less on purpose — restraint is the house style, so there is no illustration slot and no variant axis.

**Module.** [[frontend/packages/ui/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `EmptyState` | fn | `{title, body?, action?, className?}` |
| `EmptyStateProps` | type | as above; `action` is a `ReactNode` (a Button, a link — never a label the component renders itself) |

## Behavior

`title` is required and `body`/`action` are conditionally rendered, so an empty state with only a title collapses cleanly rather than leaving reserved whitespace. Every string arrives as a prop: the package carries no i18next dependency, and callers pass either `t(...)` output ([[frontend/apps/manage/src/components/BookingsSection.tsx]]) or literal Hebrew ([[frontend/apps/manage/src/components/CatalogSection.tsx]]). No `role="status"` and no live region — this is static page content, not an announcement; a caller that needs the empty state *announced* on a data change must wrap it.

The title is pinned to `text-ink`, and that colour choice is why the **storefront's catalog empty state does not use this component**. [[frontend/apps/storefront/src/routes/CatalogPage.tsx]] renders its own markup instead, with a comment saying so explicitly: the public design wants a softer treatment than the console's ink title, and `className` cannot fix it — `cn()` is a plain join with no class-merge, so a call-site `text-ink-muted` does not reliably beat the component's own `text-ink`. Treat this as a console primitive that the storefront declines, not as a component the storefront forgot.

## Depends On

- [[frontend/packages/ui/src/lib/styles.ts]] — `cn`
- [[Tailwind CSS]]

## Depended On By

- [[frontend/apps/manage/src/components/BookingsSection.tsx]] — the empty-day state
- [[frontend/apps/manage/src/components/CatalogSection.tsx]] — empty catalog and empty archive
- [[frontend/apps/manage/src/components/MediaGallery.tsx]]
- [[frontend/apps/manage/src/components/VariantMatrix.tsx]]
- [[frontend/packages/ui/src/index.ts]] — barrel re-export

## Concepts

- [[Design Tokens]]

## Tests

- [[frontend/packages/ui/src/__tests__/display-primitives.test.tsx]]
