---
tags: [frontend, storefront, booking, react, forms, accessibility]
sources: [frontend/apps/storefront/src/components/booking/SizeChips.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/components/booking/SizeChips.tsx
blob: 4770163334f452688ef3e9fe5737c7cb95b8b111
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/storefront/src/components/booking/SizeChips.tsx

**Role.** The booking flow's size selector: native radios inside a `<fieldset>`, each input `sr-only` with its `<label>` drawn as a pill chip. App-local rather than promoted to `packages/ui` — the unavailable-but-still-selectable rule below is a booking-flow policy, not a general primitive.

**Module.** [[frontend/apps/storefront/src/components/booking/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `SizeChips` | component | `{sizes, value, onChange, error?, notice?, ref?}` |
| `SizeChipsProps` | interface | `ref` forwards to the **first** radio, which is where `BookPage` sends focus on a validation failure |

## Behavior

**An unavailable size stays selectable (D4)** — this is a fitting, not a purchase — so it gets no stock styling whatsoever: same border, same fill, same weight. The only signal is the word `booking.sizeUnavailable`, rendered **inside that chip's own label**, where it joins the radio's accessible name by construction. A group-level sentence would leave the chips reading "36 / 38 / 40" with nothing marking which one it referred to, and axe would see the text and pass anyway. A muted `booking.sizeUnavailableNote` under the group carries the invitation the chip phrase has no room for, stated once, never in a promo or warning register.

`error` and `notice` share one message slot with `error ?? notice` precedence — by the time an error exists she has pressed forward and the notice is stale. They differ only in register: `error` (`booking.sizeRequired`) is a real validation failure in `text-danger`; `notice` (`booking.sizeGoneRepick`) is the recoverable "this went away, pick another" in `text-warning-text`, because the boutique's stock moved and nothing she did failed. The file records that §3.8's table files this under danger while §4.7 and §5.8's *measured* contrast ledger say `--color-warning-text`, and **the ledger wins**. The message is `role="alert"` and tied to the fieldset via `aria-describedby`.

Each radio is `required`, which is WCAG 3.3.2 for free: `required` on every radio makes the group required to AT, and the storefront uses no `*` convention. Size labels are wrapped in `<bdi dir="ltr">` — sizes are genuine Latin/digit runs.

The class strings are split so that **each branch carries its border and its `padding-inline` exactly once** (`border … px-3` resting, `border-2 … px-[11px]` selected): `cn` has no tailwind-merge, so a shared `px-3` plus a conditional `px-[11px]` would ship both and let stylesheet order decide. The 1px→2px border growth is absorbed by the paired padding so the chip does not jump on selection.

## Depends On

- [[frontend/packages/ui/src/lib/styles.ts]] — `cn`
- [[frontend/apps/storefront/src/api.ts]] — `SizeChip` type
- [[React]] — `useId`, `Ref` · [[i18next]]

## Depended On By

- [[frontend/apps/storefront/src/routes/BookPage.tsx]] — the details step, rendered between the name and notes fields and only when the bound dress has active variants

## Concepts

- [[Accessibility Compliance]]
- [[Accessibility Compliance]]
- [[RTL And Bidi Isolation]]
- [[Design Tokens]]

## Tests

- [[frontend/apps/storefront/src/__tests__/BookPage.test.tsx]]

## Notes

`focus-within` on the chip, not `focus-visible` — the visible box is the `<label>` while the focusable node is the `sr-only` `<input>` inside it. Same trick as [[frontend/apps/storefront/src/components/booking/TypePicker.tsx]]'s rows.
