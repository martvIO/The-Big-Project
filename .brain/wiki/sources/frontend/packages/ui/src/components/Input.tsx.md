---
tags: [frontend, ui, react, form-primitive, accessibility]
sources: [frontend/packages/ui/src/components/Input.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/components/Input.tsx
blob: a9709f6a73299684eee1eef79f84c0b06c5475a7
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/components/Input.tsx

**Role.** The single text-field primitive, and the most-imported component in the repo. It bundles a **mandatory visible label**, the `useId`-generated label/field/help/error id wiring, `aria-invalid` + `aria-describedby`, a `role="alert"` error line, and the shared focus ring — so that no screen in either app can ship an unlabelled or unannounced field.

**Module.** [[frontend/packages/ui/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `Input` | fn | the labelled field; renders `<label>` + optional help + `<input>` + optional error in a flex column |
| `InputProps` | type | `InputHTMLAttributes<HTMLInputElement>` **minus `id`**, plus required `label`, optional `error`, `help`, `ref` |

## Behavior

`label: string` is required and `id` is `Omit`-ed from the native attributes — together those two type decisions make "a placeholder is the label" unrepresentable, which is the house usage law this component exists to enforce. The id comes from `useId()`, so two instances of the same field on one screen cannot collide, and the caller has no way to override it (and therefore no way to break the `htmlFor` pairing).

`describedBy` is assembled by filtering `[helpId, errorId]` and joining with a space, so a field with both help text and an error announces **both**, in that order, and a field with neither gets `undefined` rather than an empty `aria-describedby` attribute. `aria-invalid` is set to `true` only when `error` is present (never `false`), and the error line carries `role="alert"` so a validation failure is announced the moment it renders — no live region is needed at the call site.

`...rest` is spread **before** `aria-invalid` / `aria-describedby` / `className`, so a caller cannot accidentally clobber the a11y wiring, but *can* pass `dir="ltr"` for an LTR island (a URL, an email, a phone number) — a pattern the test suite pins. `ref` is declared as a plain prop, React 19 style; there is no `forwardRef` wrapper, and callers rely on it to focus a field after a validation failure. Note that `className` lands on the `<input>`, not the wrapper, and `cn()` is a plain join with no Tailwind class-merge — a call-site utility does not reliably override the component's own same-specificity utility, so treat overrides as additive only.

## Depends On

- [[frontend/packages/ui/src/lib/styles.ts]] — `cn`, `focusRing`
- [[React]] — `useId`

## Depended On By

- [[frontend/packages/ui/src/components/DateTimeFields.tsx]] — `TimeField` / `DateField` are `type`-pinned wrappers over this
- [[frontend/apps/manage/src/components/LoginForm.tsx]] · [[frontend/apps/manage/src/components/BookingDetail.tsx]] · [[frontend/apps/manage/src/components/CatalogSection.tsx]] · [[frontend/apps/manage/src/components/DressEditor.tsx]] · [[frontend/apps/manage/src/components/HoursSection.tsx]] · [[frontend/apps/manage/src/components/MediaGallery.tsx]] · [[frontend/apps/manage/src/components/ProfileSection.tsx]] · [[frontend/apps/manage/src/components/StaffSection.tsx]] · [[frontend/apps/manage/src/components/TermsSection.tsx]] · [[frontend/apps/manage/src/components/TypesSection.tsx]] · [[frontend/apps/manage/src/components/VariantMatrix.tsx]]
- [[frontend/apps/storefront/src/routes/BookPage.tsx]]
- [[frontend/packages/ui/src/index.ts]] — barrel re-export

## Concepts

- [[Accessibility Compliance]]

## Tests

- [[frontend/packages/ui/src/__tests__/Input.test.tsx]] — label association, error → `aria-invalid` + `aria-describedby` + `role="alert"`, `dir` passthrough, `ref` exposure

## Notes

The sibling [[frontend/packages/ui/src/components/TextArea.tsx]] mirrors this contract for multi-line input and adds an LTR-isolated `<bdi>` character counter; keep changes to the label/error wiring in step across the two.
