---
tags: [frontend, ui, test, vitest, rtl, bidi]
sources: [frontend/packages/ui/src/__tests__/DressCard.bidi.test.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/__tests__/DressCard.bidi.test.tsx
blob: 1f0fc3fbb6cab3f375a14f0d58b9c63851363a35
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/__tests__/DressCard.bidi.test.tsx

**Role.** The bidi-isolation contract for the dress name, split out of the main catalog suite into its own file because it is a *correctness* rule of the RTL product rather than a card feature: the name is always wrapped in a bare `<bdi>`, for Latin and Hebrew alike, and never carries a forced `dir="ltr"`.

**Module.** [[frontend/packages/ui/src/__tests__/_index]] · **Layer.** test

## Contract Pinned

| Assertion | Failure it prevents |
|---|---|
| `"Bella Rosa (Ivory)"` renders inside an element whose `tagName` is `BDI` | trailing neutral (the closing bracket) joins the surrounding RTL run and jumps to the wrong end: `(Bella Rosa (Ivory` |
| `"Aria Blanc."` likewise | same defect with a trailing full stop |
| a Hebrew name `"ורד"` is **also** in a `BDI` | one wrapper serves both scripts — no locale sniffing, no per-name branch |
| that Hebrew `BDI` does **not** have `dir="ltr"` | forcing LTR onto Hebrew is itself a bidi defect — `<bdi>` must stay bare and resolve direction from content |

## Behavior

The first two cases run through `it.each` with a table of `[name, why]`, so the failure message names the neutral character class at fault. The assertion is on `tagName`, not on a class or a `dir` attribute, because `<bdi>`'s isolation comes from the element itself (`unicode-bidi: isolate` in the UA stylesheet) — a `<span dir="auto">` would be a near-equivalent that this test correctly rejects, since it isolates direction but not the surrounding run.

The Hebrew case is the one that makes the rule cheap to hold: because `<bdi>` resolves direction per name, the component needs no script detection at all. The negative assertion (`not.toHaveAttribute("dir", "ltr")`) is the house rule made executable — numeric runs such as prices and times *do* get `<bdi dir="ltr">` (see the counter in [[frontend/packages/ui/src/components/TextArea.tsx]]), but Hebrew free text must get a bare `<bdi>`, and the two must never be conflated.

The file's own header comment records the scope argument: the dress page's `<h1>` already isolates the same string in the same document direction, so the card is the identical problem one component over. This is a jsdom-level structural check — the actual visual reordering is a browser behavior nothing here can observe.

## Depends On

- [[frontend/packages/ui/src/components/DressCard.tsx]] — the subject
- [[Vitest]] — runner, `it.each` (entity)
- [[Testing Library]] — `render` / `screen` (entity)

## Depended On By

- nothing — a leaf test

## Concepts

- [[RTL Bidi Isolation]]

## Tests

- this *is* the test

## Notes

The rest of `DressCard` (photo states, reserved badge, lazy loading, error reporting) is covered in [[frontend/packages/ui/src/__tests__/catalog-composites.test.tsx]] — this file is intentionally single-subject. [[frontend/scripts/qa-greps.sh]] mechanically bans the sibling defects (physical-direction props, raw hex, hand-formatted shekels, unzoned date reads) that no unit test can see.
