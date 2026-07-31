---
tags: [frontend, ui, test, vitest]
sources: [frontend/packages/ui/src/__tests__/Card.test.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/__tests__/Card.test.tsx
blob: aa2d90c975f9e9d01f2eaf03578f672774953090
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/__tests__/Card.test.tsx

**Role.** Two tests over [[frontend/packages/ui/src/components/Card.tsx]]: children reach the paper surface, and the hover-elevate affordance is **opt-in** — absent unless `hoverElevate` is passed.

**Module.** [[frontend/packages/ui/src/__tests__/_index]] · **Layer.** test

## Contract Pinned

| Assertion | Why |
|---|---|
| children render | the surface is a passthrough wrapper, not a slot machine |
| default render's root className does **not** contain `hover:shadow-md` | a static card must not signal interactivity it does not have |
| `hoverElevate` render's root className **does** contain it | the affordance is reachable |

## Behavior

The interesting half is the negative assertion. A card that lifts on hover reads as clickable; most cards in the console are not, so elevating by default would be an affordance lie. The test pins the default to *off* and the flag to *on*, in one `rerender` pair, which is exactly the boolean the component encodes as `hoverElevate && "transition-shadow hover:shadow-md"`.

Both assertions read `container.firstElementChild?.className` — a raw class-string grep, because jsdom computes no hover state and resolves no Tailwind. That makes the test structurally coupled to the utility name: renaming the elevation utility breaks it even if the visual result is unchanged. Accepted, because the alternative (asserting computed shadow) is unavailable in this environment.

Not covered: the `className` pass-through and the spread of arbitrary `HTMLAttributes`. Note that `cn()` is a plain join with **no** class merge, so a caller passing `shadow-none` does not reliably beat the component's own `shadow-sm` — same-specificity rules resolve by stylesheet order. Do not read this file as blessing call-site overrides.

## Depends On

- [[frontend/packages/ui/src/components/Card.tsx]] — the subject
- [[Vitest]] — runner (entity)
- [[Testing Library]] — `render` / `rerender` (entity)

## Depended On By

- nothing — a leaf test

## Concepts

- [[Design Tokens]]

## Tests

- this *is* the test

## Notes

Short file, short page. The second test's children are the literal `"x"` — the assertion is entirely about the root element's classes, not content.
