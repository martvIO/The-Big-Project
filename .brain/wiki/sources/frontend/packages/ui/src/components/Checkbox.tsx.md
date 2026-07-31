---
tags: [frontend, ui, react, form, accessibility, forwarded-ref]
sources: [frontend/packages/ui/src/components/Checkbox.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/components/Checkbox.tsx
blob: b3f134c8803f8bb9bb2933a458c2ea91615f31ef
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/components/Checkbox.tsx

**Role.** A controlled native checkbox with its native role left alone, plus the three satellite strings a consent control needs — visible `label`, optional `description`, optional `error` — wired to the input with `useId`-generated ids. It is the control the booking flow's terms consent runs through.

**Module.** [[frontend/packages/ui/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `Checkbox` | component | `{label, description?, error?, checked, onCheckedChange, disabled = false, ref?}` |
| `CheckboxProps` | interface | Closed prop set — it does **not** extend `InputHTMLAttributes`, so arbitrary input attributes cannot be passed through |

## Behavior

Fully controlled: `checked` in, `onCheckedChange(boolean)` out. There is no uncontrolled mode and no `name` prop — this component is not meant to be read out of a native form submission.

**The native `checkbox` role is deliberate and load-bearing.** A legal consent must announce *checked/unchecked*; [[frontend/packages/ui/src/components/Toggle.tsx]]'s `role="switch"` announces on/off, which is the wrong semantic for agreeing to terms. Picking Toggle for a consent is the specific mistake this component exists to prevent.

The `<label htmlFor>` wraps the box and the label text at `min-h-11` with a `size-6` box, so the **whole row is the 44px hit target** around a 24px control — the ruled touch geometry, asserted in the test suite. The `description` sits **outside** the `<label>`, tied by `aria-describedby`: inside, it would be concatenated into the accessible name. `error` renders `role="alert"` (so a validation failure is announced without moving focus) and additionally sets `aria-invalid` and a `border-danger` on the box — colour is never the only signal. `aria-describedby` is composed from the description id and the error id, joined by space, and collapses to `undefined` when neither exists rather than emitting an empty attribute.

`ref` is a plain prop forwarded to the native `<input>`. That is what makes focus-to-first-invalid work: a form can focus the offending checkbox directly on submit.

## Depends On

- [[frontend/packages/ui/src/lib/styles.ts]] — `cn`, `focusRing`
- [[React]] — `useId`, `Ref`

## Depended On By

- [[frontend/packages/ui/src/index.ts]]
- [[frontend/apps/storefront/src/routes/BookPage.tsx]] — the cancellation-terms consent

## Concepts

- [[IS 5568 Accessibility]]

## Tests

- [[frontend/packages/ui/src/__tests__/form-primitives.test.tsx]] — asserts it is a real checkbox with **no switch role** and the visible label as its accessible name; that `onCheckedChange` reports toggling; that `error` wires `aria-describedby` + `aria-invalid` and announces; that the description stays out of the accessible name; the 44px-row / 24px-box geometry; and that the native input is reachable through `ref`

## Notes

`accent-gold-strong` is used for the checked fill. That token fails the 4.5:1 *text* floor and so must never carry text (see [[frontend/packages/ui/src/components/Badge.tsx]]'s missing gold variant) — as a non-text control fill against the 3:1 UI-component floor it is fine.
