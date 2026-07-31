---
tags: [frontend, ui, component, booking, accessibility, rtl, shared]
sources: [frontend/packages/ui/src/components/SlotPicker.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/components/SlotPicker.tsx
blob: a60b2403e11b59028b16023792306396bd5b1874
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/components/SlotPicker.tsx

**Role.** The one date-plus-time chooser both apps mount: a native `<input type="date">` above a `<fieldset><legend>`-captioned grid of visually-hidden radios styled as chips. It is a **pure presenter over a pre-filtered list** — it never fetches, never filters by date, and above all never reads a clock; the `label` on every `SlotTime` arrives already formatted in the boutique's calendar.

**Module.** [[frontend/packages/ui/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `SlotPicker` | fn | the date field + radio chip grid |
| `SlotTime` | interface | `{value, label}` — `value` is the raw `starts_at` the booking POST carries; `label` is the display time (e.g. `"10:45"`) |
| `SlotPickerLabels` | interface | `{pickDate, pickTime, noSlots}` — **required**, no default |
| `SlotPickerProps` | interface | `labels`, `date`, `min?`, `max?`, `onDateChange`, `times`, `value`, `onChange`, `error?`, `ref?` |

## Behavior

The component is fully controlled: `date` and `value` come in, `onDateChange(date)` and `onChange(startsAt)` go out, and it holds no state beyond a `useId()` used to namespace the radio `name` so two pickers on one page cannot share a group. `ref` is forwarded to the **first** radio only (`index === 0 ? ref : undefined`), which is exactly what a "focus the time group after the type is chosen" flow needs; there is no ref to the date input.

Three details of the markup are load-bearing and pinned by tests. First, the `error` paragraph renders **outside and above** the `<fieldset>` — the file's comment states the reason: a `<legend>` that is not the fieldset's first element child stops being the caption and stops naming the group, so an error slipped inside would silently destroy the group's accessible name. Second, each chip is a `<label>` wrapping an `sr-only` `<input type="radio">`, so the chips are a real radio group with native arrow-key roving, `:checked` state and form semantics — [[frontend/apps/manage/src/__tests__/BookingDetail.test.tsx]] and [[frontend/apps/storefront/src/__tests__/BookPage.test.tsx]] both address them by `getByRole("radio", { name: "10:00" })`. Third, selection is signalled on three channels at once (native `:checked`, `bg-gold` fill, `font-semibold` weight), never hue alone.

Each chip's text is a `<bdi dir="ltr">` around the bare time — a Latin/numeric run inside an RTL document. That makes the chip's whole accessible name the time itself, which is why [[frontend/apps/manage/src/components/RescheduleDialog.tsx]] injects the booking's current slot with a **bare** label and names it in prose above the picker instead: appending Hebrew inside that `dir="ltr"` isolate would be a bidi defect. The date control likewise gets `dir="ltr"` because a date control is a numeric run.

`times.length === 0` renders the `noSlots` string in a plain centred muted paragraph — no icon, no border, no danger colour, no retry control. The file's comment explains the design: this is the state every new tenant ships in, so it must read as a fact, not a fault; whole-window-empty and this-date-empty deliberately share one block and one string. The chip grid itself is one `auto-fill minmax(104px, 1fr)` rule with **no breakpoints** — the column count follows from the rule and the padding of whatever `Card` it sits in.

## Depends On

- [[frontend/packages/ui/src/components/DateTimeFields.tsx]] — `DateField`
- [[frontend/packages/ui/src/lib/styles.ts]] — `cn`

## Depended On By

- [[frontend/packages/ui/src/index.ts]] — re-exported with a comment recording *why* it lives here
- [[frontend/apps/storefront/src/routes/BookPage.tsx]] — the public booking flow
- [[frontend/apps/manage/src/components/RescheduleDialog.tsx]] — the console's reschedule dialog

## Concepts

- [[Accessibility Compliance]]
- [[Jerusalem Time]]

## Tests

- [[frontend/apps/storefront/src/__tests__/BookPage.test.tsx]] — the canonical contract: radios by name, the error rendered *before* the legend in document order (`compareDocumentPosition`), and `text-danger` proven distinct from `text-ink-muted` against the real stylesheet
- [[frontend/apps/manage/src/__tests__/BookingDetail.test.tsx]] — the reuse side: injected current slot, no duplicate, and `SlotPicker`'s own empty block with no second empty message stacked on it

## Notes

**This component was promoted out of `apps/storefront` by F15 so the manage console could reuse it, and the promotion changed its contract.** Its three Hebrew strings became the required `labels` prop; the file's comment is explicit that they are "required, never optional-with-a-default", because a default would be the first Hebrew string in a package that deliberately holds none and carries no i18next dependency. `frontend/packages/ui/src/index.ts` records the same reasoning at the export site — both apps show the same grid from the same materializer, so the fieldset/legend/radio contract lives in one place rather than two.

The comment block also records a data-fetching contract the component cannot enforce: **one fetch covers the whole window and changing the date filters in memory**, rather than fourteen round trips against a throttled read budget. Both call sites honour it (`RescheduleDialog` fetches a 14-day window once and filters by `jerusalemIsoDate`), but nothing here would stop a third call site from refetching per date.

Never make this component compute a time. It has no formatter, no `Intl` call and no `new Date()`, and that absence is the reason a device in a different timezone still shows Jerusalem times — the zoned helpers live in the callers ([[frontend/apps/manage/src/lib/jerusalem.ts]], [[frontend/packages/ui/src/lib/hours.ts]]) and `frontend/scripts/qa-greps.sh` bans unzoned date reads mechanically.
