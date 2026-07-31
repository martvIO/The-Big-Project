---
tags: [frontend, manage, react, catalog, money, rtl, hardcoded-hebrew, f8]
sources: [frontend/apps/manage/src/components/DressEditor.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/src/components/DressEditor.tsx
blob: af4194f34d53c0eedeeb127474b4c77633a29c1e
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/apps/manage/src/components/DressEditor.tsx

**Role.** The one screen that creates and edits a dress, and the host for its two sub-panels — [[frontend/apps/manage/src/components/VariantMatrix.tsx]] and [[frontend/apps/manage/src/components/MediaGallery.tsx]] — which it gates on `creating` / `archived` and feeds a shared `onDetail` so a size or photo mutation refreshes the whole detail in one place. It also owns archive/restore, including the "already done in another tab" convergence.

**Module.** [[frontend/apps/manage/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `DressEditor` | component | `dressId: string \| null` — null means create |
| `DressEditorProps` | interface | `{ dressId, onBack, onDressChanged: (dress: Dress) => void, onArchived: (dressId: string) => void }` |
| `DressDraft` | interface (module-private) | The all-strings form state; price is typed in ILS |
| `toInput` / `draftFromDress` | fn (module-private) | Draft ⇄ wire conversion; `toInput` returns the DTO **or an error string** |
| `isAlreadyDone` | fn (module-private) | `ApiError` with status 404 |
| `CREATE_HINT` / `CREATE_REASON` / `ARCHIVED_HINT` / `ARCHIVED_REASON` | const | The long Card-level explanation and the short suffix each disabled control appends to its own visible label |

## Behavior

`toInput` has a two-valued return by design: a `DressInput` on success, a Hebrew error string on failure, so a caller has to branch on `typeof`. It normalises ILS text to integer agorot, folds an empty or zero price to `null`, trims name and description, and then runs the shared `validateDress`. Money never crosses the wire in ILS.

Create is a two-step: `createDress` then an immediate `getDress`, and the component switches to edit mode in place. That second read is not redundant — `media_uploads_enabled` and `media_slots_remaining` live only on the detail, and the file input must never exist before they are known. On update, the PATCH answers with a `Dress` rather than a `DressDetail`, so the result is spread over the existing detail (`{ ...detail, ...updated }`) to keep the already-loaded variants and media instead of dropping them.

**Archive and restore both converge on 404.** Both are predicated UPDATEs (`deleted_at IS NULL` / `IS NOT NULL`), so a 404 means another tab already did it — that is the outcome the owner asked for, and surfacing the API's English "Resource not found." into an otherwise fully-Hebrew console would be a worse answer. Archive treats it as success; restore re-reads the dress rather than trusting the local copy, because the other tab may have changed more than the archive flag.

The archive trigger and its modal's confirm share the name «העברה לארכיון», so only one may be mounted at a time — the trigger unmounts while the modal is open. Native `<dialog>` focus-return therefore lands on `<body>`, and a `wasConfirming` ref effect sends focus back to the trigger on close. This is the pattern [[frontend/apps/manage/src/components/BookingDetail.tsx]] later generalised to three modals.

Layout follows the house RTL rules: the price and sort-order fields are LTR islands (`dir="ltr"` on the input only, the box keeps its RTL position), the ₪ lives in the label and never in the field, name and description are `dir="auto"` because both scripts occur, and character counters are `<bdi dir="ltr">`. A single preview paragraph resolves price + `price_visible` into one readable outcome through `Price`, so neither field can be misread alone.

**This section hardcodes Hebrew** — no `useTranslation`, no i18n import.

## Depends On

- [[frontend/apps/manage/src/api.ts]] — `api.createDress`, `getDress`, `updateDress`, `archiveDress`, `restoreDress`; `ApiError`, `errorMessage`
- [[frontend/apps/manage/src/validation.ts]] — `agorotFromIlsInput`, `ilsFromAgorot`, `validateDress`, and the length/bound constants
- [[frontend/apps/manage/src/components/VariantMatrix.tsx]] · [[frontend/apps/manage/src/components/MediaGallery.tsx]] — sub-panels
- [[frontend/packages/ui/src/index.ts]] — `Badge`, `Button`, `Card`, `Input`, `Modal`, `Price`, `Skeleton`, `TextArea`, `Toggle`
- [[React]]

## Depended On By

- [[frontend/apps/manage/src/components/CatalogSection.tsx]]
- [[frontend/apps/manage/src/__tests__/CatalogSection.test.tsx]]

## Tests

- [[frontend/apps/manage/src/__tests__/CatalogSection.test.tsx]] — exercised through the list; there is no standalone `DressEditor` suite
- [[frontend/apps/manage/src/__tests__/validation.test.ts]] — the ILS↔agorot and bound rules `toInput` delegates to

## Notes

`creating` is `dressId === null && detail === null`, so it flips to false the moment the post-create `getDress` resolves — which is what re-enables the two sub-panels without a remount. Both sub-panels receive `disabledReason` (short, appended to a control's own label) and `disabledHint` (long, a real `<p>`) because a `disabled` control is out of the tab order and a detached explanation is never read.

Spec and plan: [[.planning/specs/catalog-management.md]] · [[.planning/plans/catalog-management.md]].
