---
tags: [frontend, storefront, booking, react, forms, accessibility, deposits]
sources: [frontend/apps/storefront/src/components/booking/TypePicker.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/components/booking/TypePicker.tsx
blob: d2e777bb824e7e6751dc801579d2b4704fa94206
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/storefront/src/components/booking/TypePicker.tsx

**Role.** The appointment-type chooser on the slot step: a native `<fieldset>` of radio **rows**, each showing name, duration, an optional brides-only badge, and — when a deposit-required row is selected — an inline "call us" panel with the deposit amount. Its `<legend>` **is** the step's h2, not a separate heading.

**Module.** [[frontend/apps/storefront/src/components/booking/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `TypePicker` | component | `{types, value, onChange, boutique, error?, notice?, ref?}` |
| `TypePickerProps` | interface | `ref` lands on the **checked** row, or the first when nothing is chosen |

## Behavior

Not a `<select>`, and the file says why: the duration, the brides-only badge and the deposit branch all have to be visible **before** choosing, and a `<select>` collapses every one of them into a single line. There is also **no preselection** — with a brides-only or deposit-required type first in the list, choosing for her would choose wrongly.

The deposit reveal is a **sibling** of the `<label>`, never a child: `<label>` takes phrasing content only, and nesting a panel of links inside would fold the whole thing into the radio's accessible name. `aria-describedby` (pointing at the reveal's id, and set only while that row is both `deposit_required` and selected) is the tie instead. The block is **per row** (D3) — siblings stay selectable, the date and the time grid stay operable, and a time already chosen survives switching back to a bookable type. The deposit amount renders through `Price`, which is the only sanctioned money renderer; [[frontend/scripts/qa-greps.sh]] bans the shekel glyph outright in this tree. When `contactChannels(boutique)` yields `null` the reveal degrades to a `booking.contactUnavailable` sentence rather than an empty `ContactPanel` — the D12 branch has to be at the call site because the panel with no channels is a literally empty box.

`audience === "brides_only"` renders a muted `Badge` and **nothing else** (D10): it labels, it does not gate — the row stays selectable, and the signal is words rather than a dimmed chip. Enforcement waits for a client identity in E5.

`error` / `notice` mirror [[frontend/apps/storefront/src/components/booking/SizeChips.tsx]] exactly — same `error ?? notice` precedence, same danger-vs-`text-warning-text` split for "you failed validation" versus "the boutique's catalogue moved under you" (`booking.typeGoneRepick`). The message renders **outside** the `<fieldset>`, by necessity: a `<legend>` that is not the first element child stops being the caption and stops naming the group.

The duration numeral is isolated with `<bdi dir="ltr">` at this call site, because i18next interpolation cannot carry markup and the approved Hebrew is value-first, so the key is the bare unit. `rowClass` spells out the focus ring with `focus-within:` rather than deriving it from `focusRing` — Tailwind compiles the classes it finds in source, so a string built at runtime would never be generated.

## Depends On

- [[frontend/apps/storefront/src/lib/contact.ts]] — `contactChannels`, `contactLabels`
- [[frontend/packages/ui/src/components/Badge.tsx]] · [[frontend/packages/ui/src/components/ContactPanel.tsx]] · [[frontend/packages/ui/src/components/Price.tsx]]
- [[frontend/packages/ui/src/lib/styles.ts]] — `cn`
- [[frontend/apps/storefront/src/api.ts]] — `AppointmentTypeRow`, `BoutiqueResponse` types
- [[React]] — `useId`, `Ref` · [[i18next]]

## Depended On By

- [[frontend/apps/storefront/src/routes/BookPage.tsx]] — the slot step, above `SlotPicker`

## Concepts

- [[Accessibility Compliance]]
- [[Hebrew RTL Bidi]]
- [[Design Tokens]]

## Tests

- [[frontend/apps/storefront/src/__tests__/BookPage.test.tsx]]

## Notes

The deposit branch is why `BookPage`'s forward button is never disabled: pressing it on a deposit-blocked row re-announces the row's own description (R7) and does nothing else. A `disabled` button would drop out of the tab order and make that description unreadable.
