---
tags: [frontend, manage, react, catalog, inventory, accessibility, rtl, hardcoded-hebrew, f8]
sources: [frontend/apps/manage/src/components/VariantMatrix.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/src/components/VariantMatrix.tsx
blob: 9ac381ea87462fdc861c391f1067317fbc91c1e0
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/apps/manage/src/components/VariantMatrix.tsx

**Role.** The size-and-stock panel of the dress editor: a quick-add strip of EU sizes plus a custom-label field, a draft list of `{size_label, quantity}` rows with −/+ steppers, and one whole-list `replaceVariants` save. The whole panel is a *draft* — nothing is written until «שמירת מלאי», and sort order is simply the row's position.

**Module.** [[frontend/apps/manage/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `VariantMatrix` | component | see props |
| `VariantMatrixProps` | interface | `{ dressId: string \| null; variants: Variant[]; disabled: boolean; disabledReason: string \| null; disabledHint?: string \| null; onDetail: (detail: DressDetail) => void }` |
| `Row` | interface (module-private) | `{ key, size_label, quantity }` — quantity is a **string**, so a half-typed field is not coerced |
| `rowsFromVariants` / `toInputs` / `totalQuantity` / `sameAsLoaded` | fn (module-private) | draft ⇄ wire, the live total, and the dirty check |

## Behavior

The save is a full **replace**, not a diff: `toInputs` normalises every label and assigns `sort_order` from array index, so reordering is expressed by moving rows. A `loaded` ref compares identity against the incoming `variants` prop and reloads the draft whenever the parent hands down a different set — the server response is the authority after every save. `dirty` is a structural comparison (`sameAsLoaded`), not a flag, so undoing an edit by hand correctly clears the unsaved-changes warning.

Duplicate detection is case/format-insensitive through `sizeKey`, and the quick-add chips render a dot marker plus an `aria-label` of «— כבר ברשימה» for sizes already listed. They are deliberately **not** `aria-pressed`: a second press does not un-press, and the state lives in the accessible name. The dot is a real `<span aria-hidden>` rather than `::before{content}`, because generated content is folded into the accessible name in Chrome and Firefox.

**Every disabled control states its reason on its own visible label.** `disabled` removes an element from the tab order, so a detached explanatory paragraph would never be read — hence `suffix` on the quick-add group label, a parenthetical on the custom-size input's label, and an `aria-label` on the add button. The three reasons are: the parent's `disabledReason` (unsaved dress / archived), the `MAX_VARIANTS_PER_DRESS` cap, or nothing. The Card-level `disabledHint` is a real `<p>` at full contrast, never behind an opacity veil — WCAG's inactive-control contrast exemption does not cover the sentence explaining the state.

The stepper row is an explicit LTR island: `dir="ltr"` plus `unicodeBidi: "isolate"` around `− value +`, while «כמות» stays outside it in the RTL flow. The number input carries `aria-labelledby` pointing at both the visible «כמות» text and the size badge — an `aria-label` would silently replace the visible label rather than extend it. Every icon-only control has `min-w-11`/`min-h-11` for the 44px target floor, and the remove button's accessible name begins with the visible word verbatim.

An all-zero stock draft raises a `role="status"` warning that the dress will read «אזל מהמלאי» in the management catalog — which is precisely the three-way rule [[frontend/apps/manage/src/components/CatalogSection.tsx]]'s `stockBadge` implements.

The quantity input is a raw `<input type="number">` with hand-written token classes rather than the shared `Input`, because it needs `text-end` inside the LTR island and a shared label from two ids. **Hardcoded Hebrew** — no i18n.

## Depends On

- [[frontend/apps/manage/src/api.ts]] — `api.replaceVariants`, `errorMessage`, `Variant` / `VariantInput`
- [[frontend/apps/manage/src/validation.ts]] — `EU_SIZE_QUICK_LIST`, `normalizeSizeLabel`, `sizeKey`, `validateVariants`, `MAX_VARIANTS_PER_DRESS`, `MAX_VARIANT_QUANTITY`, `MAX_SIZE_LABEL_LENGTH`
- [[frontend/packages/ui/src/index.ts]] — `Badge`, `Button`, `Card`, `EmptyState`, `Input`
- [[React]]

## Depended On By

- [[frontend/apps/manage/src/components/DressEditor.tsx]]
- [[frontend/apps/manage/src/__tests__/VariantMatrix.test.tsx]]

## Tests

- [[frontend/apps/manage/src/__tests__/VariantMatrix.test.tsx]] — duplicate rejection, the cap, the disabled-reason labels, and the all-zero warning
- [[frontend/apps/manage/src/__tests__/validation.test.ts]] — `normalizeSizeLabel` / `sizeKey` / `validateVariants`

## Notes

Row `key`s are `variant.id` for saved rows and `new-N` for drafts, so React does not remount a row when a neighbour is removed — which matters because the quantity input holds uncommitted text. `size_label` is unbounded owner-typed text with no numeric constraint, which is why it renders inside a **bare** `<bdi>` here and in [[frontend/apps/manage/src/components/BookingDetail.tsx]].

Spec and plan: [[.planning/specs/catalog-management.md]] · [[.planning/plans/catalog-management.md]].
