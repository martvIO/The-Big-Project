---
tags: [frontend, ui, test, vitest, rtl, hours, money]
sources: [frontend/packages/ui/src/__tests__/hours-composites.test.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/__tests__/hours-composites.test.tsx
blob: fa622cb23a0a5528188bfbb7e6177cbf097a5e40
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/__tests__/hours-composites.test.tsx

**Role.** The suite for the three storefront-header composites: `Price` (the only money renderer in the product), `HoursTable` (the Sun-first Israeli week), and `BoutiqueHeader`. Every case here guards a *tone or omission* rule rather than a mechanism — closed is not an error, Saturday is not a missing row, and a hidden price shows no shekel sign.

**Module.** [[frontend/packages/ui/src/__tests__/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `describe("Price")` | suite | agorot → `"5,900 ₪"` number-then-shekel, converted once; hidden label occupies the same slot |
| `describe("HoursTable")` | suite | a Saturday closed row appears even when no rule mentions Saturday |
| `describe("BoutiqueHeader")` | suite | closed-today renders in `ink-muted` never `danger`; address degrades to text without a maps URL |
| `DAY_LABELS` | const | seven Hebrew day labels, index 0 = Sunday |

## Behavior

**`Price` is asserted on both its output string and its absence.** `agorot={590000}` must render `"5,900 ₪"` — the ₪ trails the number, the thousands separator comes from the `he-IL` `Intl.NumberFormat`, and the division by 100 happens exactly once inside [[frontend/packages/ui/src/components/Price.tsx]]. The hidden case asserts the label appears *and* `queryByText(/₪/)` is null: when the owner hides a price the currency glyph must not survive as a lone decoration. Neither case inspects the `<bdi dir="ltr">` wrapper, though it is the reason the digits and the ₪ read correctly inside RTL prose — that isolation is checked by the bidi suite instead.

**The `HoursTable` case is one row of a much larger contract, chosen because it is the one that regresses.** The fixture opens Sun–Fri identically and simply *omits* Saturday; the assertion walks from the `"שבת"` cell up to its `<tr>` and requires the closed label inside it. The naive implementation — map over the supplied rules — drops Saturday entirely and produces a six-row table that looks plausible. The grouping logic itself lives in [[frontend/packages/ui/src/lib/hours.ts]] and is exercised exhaustively by [[frontend/packages/ui/src/__tests__/hours.test.ts]]; this case only proves `HoursTable` renders what the grouper returns.

**`BoutiqueHeader` gets a colour assertion, deliberately.** "סגור היום" is a fact about a boutique's week, not a fault: the test reads the class string for `text-ink-muted` and asserts `text-danger` is absent. Nothing else in the suite can see a colour choice, and "closed → red" is the reflex a future contributor will have. The second case covers the security degrade path — `mapsUrl={null}` must yield no link at all while the address still renders — which is the visible half of the [[frontend/packages/ui/src/lib/url.ts]] allowlist: a rejected scheme returns `undefined`, and the component falls back to a bare `<bdi>`. Note the address is wrapped in a **bare** `<bdi>` with no `dir`, because a tenant address may be Hebrew and forcing LTR would mangle it.

## Depends On

- [[frontend/packages/ui/src/components/Price.tsx]] — subject
- [[frontend/packages/ui/src/components/HoursTable.tsx]] — subject
- [[frontend/packages/ui/src/components/BoutiqueHeader.tsx]] — subject
- [[frontend/packages/ui/src/lib/hours.ts]] — `WeeklyRule` fixture type
- [[frontend/packages/ui/src/test/setup.ts]] — jest-dom + RTL cleanup
- [[Vitest]] · [[Testing Library]] · [[React]]

## Depended On By

Nothing imports a test file.

## Concepts

- [[RTL Bidi Isolation]]
- [[Design Tokens]]

## Tests

This is the test. Bidi isolation of money and dates is covered by [[frontend/packages/ui/src/__tests__/DressCard.bidi.test.tsx]]; the week-grouping algorithm by [[frontend/packages/ui/src/__tests__/hours.test.ts]].

## Notes

`Price`'s fractional path (`agorot % 100 !== 0` → two decimals) is unasserted, as is `HoursTable`'s multi-window lunch-break row — both are real behaviors of their components. The mechanical ban on hand-formatted shekels anywhere outside `Price` is enforced by [[frontend/scripts/qa-greps.sh]], not by this file.
