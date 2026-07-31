---
tags: [frontend, ui, test, vitest, forms, accessibility, rtl]
sources: [frontend/packages/ui/src/__tests__/Input.test.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/__tests__/Input.test.tsx
blob: 645abd7b7bc1972b2e2a2e2562935605856ff2e7
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/__tests__/Input.test.tsx

**Role.** Covers **two** components — [[frontend/packages/ui/src/components/Input.tsx]] and [[frontend/packages/ui/src/components/TextArea.tsx]] — pinning the shared field contract: a real label association, an error wired through `aria-invalid` + `aria-describedby` + `role="alert"`, a `dir` escape hatch for LTR islands, and a forwarded ref to the native element.

**Module.** [[frontend/packages/ui/src/__tests__/_index]] · **Layer.** test

## Contract Pinned

| Component | Assertion | Failure it prevents |
|---|---|---|
| `Input` | `getByLabelText("מספר טלפון")` finds the field | placeholder-as-label (tokens.md usage law 3); the `useId`/`htmlFor` pairing actually resolves |
| `Input` | error sets `aria-invalid="true"`, renders a `role="alert"` node with the message, and the field's `aria-describedby` **contains that alert's own `id`** | the error is both announced live and permanently attached to the field — a message rendered next to the input but not referenced is invisible to AT |
| `Input` | `dir="ltr"` passes through to the native input | an LTR island (URL, email) inside an RTL form is authorable without a wrapper |
| `Input` | `ref` is an `HTMLInputElement` | callers can focus the first invalid field |
| `TextArea` | `showCount` + `maxLength` render `"4 / 100"` from a 4-char Hebrew value | the counter counts the value, not the maxLength |
| `TextArea` | the counter's `tagName` is `BDI` **and** it carries `dir="ltr"` | a bare numeric run reorders against neighbouring Hebrew; unlike a name, digits *do* get the explicit `dir="ltr"` |
| `TextArea` | `ref` is an `HTMLTextAreaElement` | same focus contract |

## Behavior

The error test is the sharpest one in the file, and the reason is the third assertion. Asserting `aria-invalid` alone passes on a field whose error text is orphaned; asserting `role="alert"` alone passes on a field with no association. Reading the alert's generated `id` back out and checking it appears in `aria-describedby` closes the loop with no hard-coded id — which matters because both components build their ids from `useId()` and `[helpId, countId, errorId].filter(Boolean).join(" ")`, so the attribute is a *space-joined list*: `toContain`, not `toBe`, is deliberate and must stay that way when `help` is also present.

The two `<bdi>` assertions across this file and [[frontend/packages/ui/src/__tests__/DressCard.bidi.test.tsx]] are the complete statement of the house bidi rule and should be read together: **numeric run ⇒ `<bdi dir="ltr">`, Hebrew free text ⇒ bare `<bdi>`**. This file pins the first half, that file the second, and the negative assertion in each is what stops the two from collapsing into one wrong rule.

`TextArea`'s counter is exercised as a controlled field (`value` + a no-op `onChange`); `used` derives from `typeof value === "string" ? value.length : 0`, so an uncontrolled textarea shows `0 / max` forever — untested here and worth knowing before using `showCount` uncontrolled.

## Depends On

- [[frontend/packages/ui/src/components/Input.tsx]] — subject
- [[frontend/packages/ui/src/components/TextArea.tsx]] — subject
- [[Vitest]] — runner (entity)
- [[Testing Library]] — `render` / `screen` (entity)
- [[React]] — `createRef` (entity)

## Depended On By

- nothing — a leaf test

## Concepts

- [[RTL Bidi Isolation]]
- [[Accessibility Compliance]]

## Tests

- this *is* the test

## Notes

Named `Input.test.tsx` but it owns `TextArea` too — grep for `TextArea` and this is the file. The sibling [[frontend/packages/ui/src/__tests__/form-primitives.test.tsx]] covers the remaining form components (`Select`, `Checkbox`, `Toggle`, `DateTimeFields`).
