---
tags: [frontend, ui, component, form, accessibility]
sources: [frontend/packages/ui/src/components/Select.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/components/Select.tsx
blob: 32708e86d42a826f92b595a22295bf47ad81bbef
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/components/Select.tsx

**Role.** The console's only dropdown: a **native** `<select>` wrapped in a generated-id label and an optional `role="alert"` error line. There is no custom listbox in v1 — the file's own comment records the reason ("a11y cost not worth it"), and the payoff is that the OS picker, OS locale, mobile wheel UI and the entire platform accessibility stack come for free in an RTL document.

**Module.** [[frontend/packages/ui/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `Select` | fn | labelled native select with error wiring |
| `SelectProps` | interface | `SelectHTMLAttributes<HTMLSelectElement>` minus `id`, plus `label` (required), `error?`, `children`, `ref?` |

## Behavior

`id` is `Omit`-ed from the extended attributes and generated with `useId()` instead, so the `<label htmlFor>` ↔ `<select id>` association can never be broken by a caller passing a duplicate id — this is the same contract [[frontend/packages/ui/src/components/Input.tsx]] and [[frontend/packages/ui/src/components/TextArea.tsx]] ship. `label` is a required `string`, not a `ReactNode`: every select in the product has a visible text label, and there is no unlabelled variant to fall back to.

Error handling is three-channel and conditional. When `error` is set the component adds `aria-invalid={true}` (and `undefined` — i.e. the attribute absent — when it is not, never `aria-invalid="false"`), points `aria-describedby` at a derived `${id}-error`, adds a `border-danger` class, and renders the message in a `role="alert"` span so it is announced on appearance. With no error, `errorId` is `undefined` and `aria-describedby` is simply omitted.

`ref` is a plain prop (React 19 — no `forwardRef` wrapper anywhere in this package), typed `Ref<HTMLSelectElement>`, forwarded to the native element so a caller can focus the field after a failed submit. Note the spread order: `{...rest}` lands **before** `aria-invalid`/`aria-describedby`/`className`, so a caller cannot override the error wiring or the focus ring by passing those props — `className` is folded through `cn()` last instead.

The options themselves are `children`. This component renders no `<option>` of its own, has no "placeholder" concept and no empty-value convention — each call site supplies the full list, so an empty-vs-required decision stays with the form that owns it.

## Depends On

- [[frontend/packages/ui/src/lib/styles.ts]] — `cn`, `focusRing`
- [[Tailwind CSS]] — token utilities `border-border-input`, `bg-surface-raised`, `text-ink`, `border-gold-strong`, `border-danger` (entity)

## Depended On By

- [[frontend/packages/ui/src/index.ts]] — re-exports `Select` + `SelectProps`
- [[frontend/apps/manage/src/components/HoursSection.tsx]]
- [[frontend/apps/manage/src/components/TypesSection.tsx]]
- [[frontend/apps/manage/src/components/StaffSection.tsx]]

## Concepts

- [[Accessibility Compliance]]

## Tests

- [[frontend/packages/ui/src/__tests__/form-primitives.test.tsx]] — asserts the rendered element really is a `SELECT` (not a styled div), that options are reachable by role, and that `ref` yields an `HTMLSelectElement`

## Notes

The storefront deliberately does **not** use this component for its appointment-type chooser: [[frontend/apps/storefront/src/components/booking/TypePicker.tsx]] carries an explicit "NOT a Select" comment, because a collapsed dropdown would hide the duration and deposit a bride needs to compare before choosing. Only the manage console selects.

Also note this component never calls i18n — `label` and `error` arrive as pre-translated strings, and `packages/ui` has no i18next dependency on purpose.
