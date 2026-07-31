---
tags: [frontend, ui, component, form, accessibility, rtl]
sources: [frontend/packages/ui/src/components/TextArea.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/components/TextArea.tsx
blob: d22ef6048fd9752a8fbb1b9b6bca66cf5d2be9f5
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/components/TextArea.tsx

**Role.** The multi-line field: a generated-id label, an optional help line, an optional live "used / max" counter, and an optional `role="alert"` error — with all three optional pieces stitched into one ordered `aria-describedby` so a screen reader hears them in the order they are read on screen.

**Module.** [[frontend/packages/ui/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `TextArea` | fn | labelled `<textarea>` with help / count / error wiring |
| `TextAreaProps` | interface | `TextareaHTMLAttributes<HTMLTextAreaElement>` minus `id`, plus `label` (required), `error?`, `help?`, `showCount?`, `ref?` |

## Behavior

`useId()` produces one base id and three derived ones (`-help`, `-count`, `-error`), each computed only when its piece is present. `describedBy` is `[helpId, countId, errorId].filter(Boolean).join(" ") || undefined` — the `|| undefined` matters: it keeps `aria-describedby` off the element entirely rather than setting it to an empty string, which some AT reads as a described-by target that does not exist. `aria-invalid` is likewise `true` or absent, never `"false"`.

The counter renders only when **both** `showCount` and `maxLength` are set, and `used` is `typeof value === "string" ? value.length : 0` — an uncontrolled `<textarea>` (no `value`) therefore shows a frozen `0 / max` rather than crashing or lying convincingly. That is a real trap: `showCount` is only meaningful on a controlled field.

The counter's content is wrapped in `<bdi dir="ltr">`, and the inline comment states why: bare numerals inside an RTL document reorder against the neighbouring Hebrew without an isolate of their own, so `4 / 100` would render as `100 / 4`. This is the *numeric-run* case where `dir="ltr"` is correct — Hebrew free text takes a bare `<bdi>` instead, and putting `dir="ltr"` on Hebrew is itself a bidi defect. The counter block is positioned with `text-end`, a logical property, not `text-right`.

Note the prop order in the JSX: `value` and `maxLength` are pulled out of the rest-spread and set **before** `{...rest}`, while `aria-invalid`, `aria-describedby` and `className` come **after** — so a caller cannot clobber the accessibility wiring, but the destructured `value`/`maxLength` are re-applied explicitly because the counter needs to read them. `ref` is a plain React 19 prop (no `forwardRef`), forwarded to the native element.

## Depends On

- [[frontend/packages/ui/src/lib/styles.ts]] — `cn`, `focusRing`

## Depended On By

- [[frontend/packages/ui/src/index.ts]] — re-exports `TextArea` + `TextAreaProps`
- [[frontend/apps/manage/src/components/TermsSection.tsx]] — the cancellation-policy text, the `showCount` case
- [[frontend/apps/manage/src/components/DressEditor.tsx]]
- [[frontend/apps/manage/src/components/ProfileSection.tsx]]
- [[frontend/apps/storefront/src/routes/BookPage.tsx]] — the booking notes field

## Concepts

- [[Accessibility Compliance]]

## Tests

- [[frontend/packages/ui/src/__tests__/Input.test.tsx]] — despite the filename, the `TextArea` suite lives here: the `4 / 100` counter, the assertion that its element is a `BDI` carrying `dir="ltr"`, and `ref` yielding an `HTMLTextAreaElement`

## Notes

`help` and `error` are not mutually exclusive; both can be described at once, and the order in `describedBy` is help → count → error, which is also their visual order. No i18n here — every string is a prop.
