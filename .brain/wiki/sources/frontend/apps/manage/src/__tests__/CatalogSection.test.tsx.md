---
tags: [frontend, manage, test, vitest, catalog, pagination, optimistic-update]
sources: [frontend/apps/manage/src/__tests__/CatalogSection.test.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/src/__tests__/CatalogSection.test.tsx
blob: 574e2e8c5ed31d6cbfe99760e9556ecf40e53386
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/apps/manage/src/__tests__/CatalogSection.test.tsx

**Role.** The suite for the dress list screen: empty-vs-filtered-empty states, the three-way stock badge, offset paging, a 300 ms debounced search that resets the offset, the archive filter, the list↔editor hand-off that patches rows **and the total** in place without a refetch, and two already-done 404 races.

**Module.** [[frontend/apps/manage/src/__tests__/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `dress(overrides)` | helper | a `Dress` row with every catalog flag defaulted |
| `page(items, total, offset)` | helper | the `DressList` envelope; `limit` is fixed at 24 |
| `detailOf(row)` | helper | promotes a row to `DressDetail` with uploads disabled |
| `CatalogSection listing` | suite | first-run empty state, filtered dead end, stock badges, reserved chip and hidden price |
| `CatalogSection paging` | suite | offset paging, pager disabling at each end, the count line |
| `CatalogSection search` | suite | 300 ms debounce, offset reset, `maxlength` |
| `CatalogSection archive filter` | suite | archived rows, offset reset |
| `CatalogSection detail hand-off` | suite | in-place patch, blank editor, created-row counting, no double count |
| `CatalogSection already-done races` | suite | 404 from archive and from restore |

## Behavior

**Two different emptinesses render differently.** A first-run catalog gets a designed empty state («אין עדיין שמלות בקטלוג») with *no* `role="alert"`; a search that matches nothing gets a different sentence plus a «ניקוי החיפוש» button. Collapsing the two would tell a brand-new owner she has a broken filter.

The stock badge is three-way and read-only: «במלאי (7)», «אזל מהמלאי», and — the distinction worth keeping — «לא הוגדרו מידות» for a dress with `variant_count: 0`, which is *unconfigured*, not out of stock. The badges are asserted to be text, not controls: each row exposes exactly one button, and that button is the row.

Search uses real fake timers around `act()`: three keystrokes inside 300 ms produce **one** request, at exactly 300 ms (299 ms is asserted to have produced none), and that request carries `offset: 0` — a search that kept the old offset would land the owner on an empty page 2 of her own results. The archive toggle resets the offset for the same reason.

The hand-off suite is where the interesting invariant lives. Editing a dress and returning patches the changed row from the mutation response with `listDresses` still at **one** call for the whole flow. Creating one appends the row locally *and* increments `total`: leaving `total` at 1 would render «מציג 1–1 מתוך 1» above two rows and re-enable «הבא» against a page that does not exist. A separate test saves the same new dress twice and asserts the count does not double-count.

Both race tests describe another tab: `DELETE` is predicated on `deleted_at IS NULL`, so a second archive 404s. The console treats a 404 from archive as **done** — back to the list, row gone, count decremented, and the API's English «Resource not found.» never rendered. A 404 from restore is treated as done too, but converges differently: it re-reads the dress (`getDress` twice) and the restore button disappears because the server says it is no longer archived. Guessing the new state from an error is exactly what neither path does.

## Depends On

- [[frontend/apps/manage/src/components/CatalogSection.tsx]] — the subject (which mounts [[frontend/apps/manage/src/components/DressEditor.tsx]], [[frontend/apps/manage/src/components/VariantMatrix.tsx]] and [[frontend/apps/manage/src/components/MediaGallery.tsx]] behind it)
- [[frontend/apps/manage/src/api.ts]] — catalog + media endpoints mocked; `ApiError` / `errorMessage` real
- [[Testing Library]] · [[Vitest]]

## Depended On By

Nothing imports a test file.

## Concepts

- [[Hebrew RTL Bidi]]

## Notes

The whole editor sub-tree renders inside this suite, so a break in `DressEditor` surfaces here rather than in its own file — there is no `DressEditor.test.tsx`. `afterEach(vi.useRealTimers)` is load-bearing: the debounce test installs fake timers mid-file. See [[.planning/specs/catalog-management.md]].
