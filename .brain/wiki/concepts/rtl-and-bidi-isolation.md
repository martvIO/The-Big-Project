---
tags: [frontend, rtl, i18n, ui, design]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: active
---

# RTL And Bidi Isolation

**What it is.** Both apps ship `<html lang="he" dir="rtl">`
([[frontend/apps/storefront/index.html]], [[frontend/apps/manage/index.html]]). RTL is the base
direction of the entire product, so the interesting work is not "flip the layout" — it is
isolating the runs that are *not* Hebrew so their neutral characters stop reordering.

## The rule, in one line

**`<bdi dir="ltr">` when the direction is known. Bare `<bdi>` when it is not. `dir="ltr"` on
Hebrew is the defect.**

| Content | Wrapper | Where |
|---|---|---|
| money, times, counters | `<bdi dir="ltr">` | [[frontend/packages/ui/src/components/Price.tsx]], [[frontend/packages/ui/src/components/HoursTable.tsx]], [[frontend/packages/ui/src/components/TextArea.tsx]] |
| tenant-supplied free text | bare `<bdi>` | [[frontend/packages/ui/src/components/DressCard.tsx]], [[frontend/packages/ui/src/components/BoutiqueHeader.tsx]] |

[[frontend/packages/ui/src/components/BoutiqueHeader.tsx]] states the trap directly in a comment:
*bdi, not `dir="ltr"` — the address is tenant-supplied and may be Hebrew.* A boutique that types a
Hebrew address into a field you forced LTR gets its own address rendered backwards.

## Why bare `<bdi>` is not cosmetic

A Latin-only dress name — `Bella Rosa (Ivory)` — inside an RTL card is a bidi run whose **trailing
neutrals reorder**: the closing bracket or full stop jumps to the wrong end. `<bdi>` resolves each
name's direction on its own and isolates it from the card around it, which is why the *same*
wrapper is correct for a Hebrew name and a Latin one.
[[frontend/packages/ui/src/__tests__/DressCard.bidi.test.tsx]] pins both.

## Money renders through one component

[[frontend/packages/ui/src/components/Price.tsx]] is *the* only way to render money: number-then-
shekel, LTR-isolated, formatted from integer agorot via `Intl.NumberFormat("he-IL")`. The hidden-
price label occupies the same slot at the same height so a mixed grid never jumps.
[[frontend/scripts/qa-greps.sh]] fails the build on a bare `₪` anywhere in the storefront source.

## Physical direction properties are banned mechanically

Everything uses CSS **logical** properties — `ms-` / `me-` / `ps-` / `pe-` / `start-` / `end-` /
`inset-block-end`. `qa-greps.sh` greps for `ml-`, `mr-`, `pl-`, `pr-`, `left-`, `right-`,
`text-left`, `text-right`, `border-l-`, `border-r-` and fails if any is found. Note the deliberate
narrowness: **block-direction** utilities (`mt-`, `mb-`, `pt-`, `pb-`) are direction-agnostic and
legitimate — only the *inline* axis is policed.

## Related

- [[Hebrew First UX]] — Arabic is also RTL, which is why no direction-switching logic exists
- [[Accessibility Compliance]] · [[Design Tokens]]
- [[frontend/packages/ui/src/lib/styles.ts]] · [[.planning/plans/rtl-design-system.md]]
