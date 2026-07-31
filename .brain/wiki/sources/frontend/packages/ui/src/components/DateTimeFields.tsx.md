---
tags: [frontend, ui, react, form-primitive, native-input]
sources: [frontend/packages/ui/src/components/DateTimeFields.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/components/DateTimeFields.tsx
blob: 2a4ecaaea20f29d7a1fb0d7be4d55009c7ece1c3
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/components/DateTimeFields.tsx

**Role.** Two four-line wrappers — `TimeField` and `DateField` — that pin `type` on [[frontend/packages/ui/src/components/Input.tsx]] and nothing else. There is no picker library, no calendar popup, no masked text input: the platform's own `<input type="date">` / `type="time"` is the whole implementation, so the browser supplies the locale-correct calendar, the RTL-aware segment order, and the mobile OS wheel for free.

**Module.** [[frontend/packages/ui/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `TimeField` | fn | `<Input type="time">` — props are `Omit<InputProps, "type">`, so a caller cannot change the type |
| `DateField` | fn | `<Input type="date">` — same contract |

## Behavior

Both spread the caller's props onto `Input` *after* `type`, but the `Omit<InputProps, "type">` signature means a `type` override is a compile error rather than a silent win — the ordering is belt-and-braces, the type is the actual guard. Everything else the field needs comes from `Input`: the required `label`, the `useId`-generated `htmlFor` pairing, `aria-invalid` / `aria-describedby` wiring, the shared focus ring, and `ref` forwarding. Consequently these two functions have no state, no effects and no styling of their own — anything that looks like a bug in a date field is a bug in `Input` or in the caller's props.

The file's own comment records the boundary that keeps it this small: **Israeli-week ordering is a composite concern**, owned by [[frontend/packages/ui/src/components/HoursTable.tsx]] and the console's `HoursSection`, not by the field. A `DateField` renders whatever ISO date string it is given; it does not know that the week starts on Sunday, and it must not learn.

## Depends On

- [[frontend/packages/ui/src/components/Input.tsx]] — the entire implementation, plus the `InputProps` type

## Depended On By

- [[frontend/packages/ui/src/components/SlotPicker.tsx]] — owns the `DateField` that drives slot refetch in both apps
- [[frontend/apps/manage/src/components/BookingsSection.tsx]] — the day picker above the bookings list
- [[frontend/packages/ui/src/index.ts]] — barrel re-export

## Concepts

- [[Design Tokens]]

## Tests

- [[frontend/packages/ui/src/__tests__/form-primitives.test.tsx]]

## Notes

`TimeField` is exported from [[frontend/packages/ui/src/index.ts]] but has **no consumer in either app** — `git grep -w TimeField` outside this package hits only the barrel and the form-primitives test. It exists for the hours editor's window rows; treat it as reserved surface, not dead code, but do not assume it is exercised by the apps' suites.
