---
tags: [frontend, manage, react, catalog, rtl, hardcoded-hebrew, f8]
sources: [frontend/apps/manage/src/components/CatalogSection.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/src/components/CatalogSection.tsx
blob: 4ecbfb726ceb4fc0b362c617929317c7c69c3731
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/apps/manage/src/components/CatalogSection.tsx

**Role.** The dress list screen: debounced search, an archive toggle, offset/limit paging at 24 rows, and an in-place swap to [[frontend/apps/manage/src/components/DressEditor.tsx]] for both create and edit. It owns the list state that the editor mutates back into it, including the `total` bookkeeping that create and archive move.

**Module.** [[frontend/apps/manage/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `CatalogSection` | component | No props |
| `stockBadge` | fn (module-private) | Three-way stock chip derived client-side from `variant_count` / `total_quantity` |
| `PAGE_SIZE` | const (module-private) | `24`, mirroring `DRESS_LIST_DEFAULT_LIMIT`; not parity-guarded because the server clamps |
| `SEARCH_DEBOUNCE_MS` | const (module-private) | `300` |

## Behavior

`stockBadge` is three-way rather than two on purpose: without the `variant_count === 0` case, a boutique that enters sixty dresses before filling any size matrix would see a page of «אזל מהמלאי» on brand-new dresses. Only the third branch shows a number, and it is isolated with `<bdi dir="ltr">`.

Search is debounced into `appliedSearch` and the page resets to `offset = 0` whenever the applied term actually changed. The list effect keys on `[offset, appliedSearch, archived]`; unlike the bookings list it *does* clear `dresses` to `[]` on failure, so an outage renders the alert plus an empty card.

`onDressChanged` patches the row from the mutation response rather than refetching, so the derived badges and the cover can never disagree between list and editor. A **create** is detected as an id not already in the list, and `total` is incremented alongside — otherwise the count line reads «מציג 1–1 מתוך 0» and the «הבא» button is gated on a stale number. `onArchived` filters the row out, floors `total` at zero, and returns to the list.

Three distinct empty states are rendered by the same `EmptyState`, and the distinction matters for what action is offered: archive-view empty gets no action, search-filtered empty offers "clear the search", and a genuinely empty catalog offers "new dress". The row is one `<button>` covering the whole strip — a second «עריכה» button would be two tab stops for one action — and the badge strip is a **sibling** of the name, never a child, because a chip nested inside a clamped box is clipped out of the row on exactly the long-name edge case. Thumbnails carry `alt=""` since the dress name is adjacent accessible text inside the same button.

The search field is `dir="auto"` because Hebrew and Latin dress names both occur. Money renders through the shared `Price` component with `visible={row.price_visible && row.price_agorot !== null}` — the console shows the owner both the hidden state and its label, which is the opposite of the storefront's policy of never shipping the flag at all.

**This is one of the older sections that hardcodes Hebrew** rather than calling `useTranslation()`. The file imports no i18n at all.

## Depends On

- [[frontend/apps/manage/src/api.ts]] — `api.listDresses`, `errorMessage`, `Dress`
- [[frontend/apps/manage/src/validation.ts]] — `MAX_SEARCH_LENGTH`
- [[frontend/apps/manage/src/components/DressEditor.tsx]] — the in-panel editor swap
- [[frontend/packages/ui/src/index.ts]] — `Badge`, `Button`, `Card`, `EmptyState`, `Input`, `Price`, `Skeleton`, `Toggle`
- [[React]]

## Depended On By

- [[frontend/apps/manage/src/App.tsx]] — rendered for the `catalog` nav key
- [[frontend/apps/manage/src/__tests__/CatalogSection.test.tsx]]

## Tests

- [[frontend/apps/manage/src/__tests__/CatalogSection.test.tsx]] — the three empty states, the debounce/page-reset behaviour, and the `total` bookkeeping on create and archive

## Notes

Paging is offset-based and stateless across the editor swap: returning from the editor keeps whatever page was showing, but a create appends to the *current* page regardless of where the server would sort it.

Spec and plan: [[.planning/specs/catalog-management.md]] · [[.planning/plans/catalog-management.md]]. Screen design: [[.planning/design/screens/manage-catalog/manage-catalog.md]].
