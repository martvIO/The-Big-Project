---
tags: [frontend, ui, test, vitest, forms, accessibility]
sources: [frontend/packages/ui/src/__tests__/form-primitives.test.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/__tests__/form-primitives.test.tsx
blob: 5211393560eb28547ead7fa964a6f355bbbc8d96
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/__tests__/form-primitives.test.tsx

**Role.** The suite for the four non-text form controls — `Select`, `Toggle`, `Checkbox`, and the native `DateField`/`TimeField` wrappers. Its centre of gravity is `Checkbox`, whose six cases pin the legal-consent semantics that separate it from `Toggle`.

**Module.** [[frontend/packages/ui/src/__tests__/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `describe("Select")` | suite | native `<select>` with a wired label; ref forwarding to the real element |
| `describe("Toggle")` | suite | `role="switch"` reports through `onCheckedChange` |
| `describe("Checkbox")` | suite | checkbox role (never switch), error wiring, description wiring, touch geometry, ref |
| `describe("TimeField / DateField")` | suite | the wrappers emit `type="time"` / `type="date"` with visible labels |

## Behavior

**`Checkbox` vs `Toggle` is the distinction this file exists to defend.** A legal consent ("קראתי ואני מסכימה לתנאים") must announce *checked / unchecked*, not *on / off*, so the test asserts `getByRole("checkbox")` succeeds, that the element carries **no** `role` attribute at all (the native role is left alone), and that `queryByRole("switch")` is null. `Toggle` is the mirror image — the same native `<input type="checkbox">` but with `role="switch"` — and its single case confirms that. Copying `Toggle`'s pattern onto a consent field is the regression this pair catches.

Two cases pin the ARIA plumbing that [[frontend/packages/ui/src/components/Checkbox.tsx]] builds by hand from `useId`. The error case asserts `aria-invalid="true"`, an element with `role="alert"` carrying the message, and — critically — that the input's `aria-describedby` *contains* that alert's `id`; `toContain` rather than `toBe` because description and error IDs are joined into one space-separated list, so an assertion on equality would break the moment both are present. The description case checks the complementary property: the description text is reachable via `aria-describedby` but is **not** part of the accessible name (the query is `getByRole("checkbox", { name: "אישור תנאים" })`, which would fail if the description had been placed inside the `<label>`).

The geometry case reads class strings — `size-6` on the box, `min-h-11` on the wrapping `<label>` — because the ruled 44px touch row wrapping a 24px box has no observable effect in jsdom. It encodes the manage-catalog toggle-row ruling; a "tidy-up" that drops `min-h-11` produces a control below the IS 5568 touch-target floor with every other assertion still green.

Both `Select` and `Checkbox` assert ref forwarding by `instanceof HTMLSelectElement` / `HTMLInputElement`, which proves the ref lands on the native element rather than on a wrapper `<div>` — the property a caller needs to `.focus()` the first invalid field. `Select` is deliberately a native `<select>` (no custom dropdown in v1), and `getByLabelText(...).tagName === "SELECT"` is what holds that decision in place.

The date/time case is a two-line smoke test: [[frontend/packages/ui/src/components/DateTimeFields.tsx]] is a pair of one-line wrappers over [[frontend/packages/ui/src/components/Input.tsx]], so all it can get wrong is the `type`.

## Depends On

- [[frontend/packages/ui/src/components/Checkbox.tsx]] — subject
- [[frontend/packages/ui/src/components/Select.tsx]] — subject
- [[frontend/packages/ui/src/components/Toggle.tsx]] — subject
- [[frontend/packages/ui/src/components/DateTimeFields.tsx]] — subject
- [[frontend/packages/ui/src/test/setup.ts]] — jest-dom + RTL cleanup
- [[Vitest]] · [[Testing Library]] · [[React]]

## Depended On By

Nothing imports a test file.

## Concepts

- [[IS 5568 Accessibility]]

## Tests

This is the test. `Input`'s own coverage is [[frontend/packages/ui/src/__tests__/Input.test.tsx]].

## Notes

`Toggle` gets one case where `Checkbox` gets six, and the asymmetry is real rather than an oversight: `Toggle` has no `error` prop and puts its description *inside* the `<label>`, so its description joins the accessible name — the opposite of `Checkbox`'s contract, and currently unasserted. If a `Toggle` ever needs error text, copy `Checkbox`'s wiring, not its own.
