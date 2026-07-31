---
tags: [frontend, manage, test, vitest, catalog, inventory, accessibility]
sources: [frontend/apps/manage/src/__tests__/VariantMatrix.test.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/src/__tests__/VariantMatrix.test.tsx
blob: 1be91cbb6e2a98d5504e5b125864cd8dfce33546
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/apps/manage/src/__tests__/VariantMatrix.test.tsx

**Role.** The suite for the per-dress size/quantity matrix: EU quick-entry chips, case- and whitespace-insensitive duplicate refusal *before* any request, one full-replace PUT for the whole matrix, and a disabled (create-mode) state whose reason lives on every control's **visible** label.

**Module.** [[frontend/apps/manage/src/__tests__/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `variant(id, sizeLabel, quantity, sortOrder)` | helper | a `Variant` row |
| `detail(variants)` | helper | the `DressDetail` a successful `replaceVariants` resolves with |
| `renderMatrix(variants)` | helper | mounts with `dressId="d1"`, enabled, and returns the `onDetail` spy |
| `VariantMatrix quick entry` | suite | chip adds a row; an already-listed chip is marked in its accessible name |
| `VariantMatrix duplicate detection` | suite | inline refusal, typed text preserved, case/whitespace folding |
| `VariantMatrix save` | suite | the single full-replace PUT, and the all-zero «אזל» warning |
| `VariantMatrix disabled (create mode)` | suite | reason on visible labels, never `aria-hidden` |

## Behavior

Two accessibility contracts are pinned by name rather than by class. First, a row's quantity input is named from its **visible** «כמות» label plus the visible size chip (`getByLabelText("כמות 38")`) — never an `aria-label` that replaces visible text, which is the WCAG 2.5.3 label-in-name trap. Second, an already-listed chip announces itself as «38 — כבר ברשימה» in its accessible name and carries **no `aria-pressed`**, because it is not a toggle; it stays enabled so tapping it is a no-op rather than a dead control.

Duplicate detection runs client-side and refuses before any network call: the alert names the offending label, exactly one row remains, and — the load-bearing bit — the typed text stays in the field so the owner can correct it rather than retype. Folding is asserted through `"US 6"` vs `"us  6"`, i.e. case *and* collapsed internal whitespace, matching `normalizeSizeLabel` in [[frontend/apps/manage/src/validation.ts]].

The save test proves the matrix is written as **one full replacement**, not a per-row diff: `replaceVariants("d1", [...])` receives every row with recomputed `sort_order`, and `onDetail` fires once with the server's response. The all-zero case renders a `role="status"` (not an alert) explaining that the dress will read «אזל מהמלאי» in the console catalog — a consequence, not an error.

Create mode is the interesting disabled state. The reason string is appended to every control's own **visible** label («הוספה מהירה (מידות אירופאיות) — יש לשמור את השמלה תחילה», and the custom-size input labelled with the reason in parentheses), and the group is explicitly **not** `aria-hidden` — the owner must still see that sizes exist and learn why she cannot use them yet.

Unlike its siblings this file mocks `../api` **without** `importActual`, supplying its own two-line `errorMessage`; there is no `ApiError` in scope, so no server-error path is exercised here.

## Depends On

- [[frontend/apps/manage/src/components/VariantMatrix.tsx]] — the subject
- [[frontend/apps/manage/src/api.ts]] — `replaceVariants` mocked; `Variant` / `DressDetail` types real
- [[Testing Library]] · [[Vitest]]

## Depended On By

Nothing imports a test file. The constants it exercises are asserted against the backend's values in [[frontend/apps/manage/src/__tests__/validation.test.ts]].

## Concepts

- [[Accessibility Compliance]]

## Notes

No i18n import: this component's copy is literal Hebrew in the component, not keys. See [[.planning/specs/catalog-management.md]].
