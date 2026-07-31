---
tags: [frontend, ui, test, vitest, accessibility, motion-tokens]
sources: [frontend/packages/ui/src/__tests__/Button.test.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/__tests__/Button.test.tsx
blob: c0ea7c38904144979c54403838487639040e577d
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/__tests__/Button.test.tsx

**Role.** Pins the loading contract, the motion-token contract and — uniquely in this suite — a **byte-exact markup snapshot** of `Button`, written as a regression fence around the extraction of `ButtonLink` beside it in [[frontend/packages/ui/src/components/Button.tsx]].

**Module.** [[frontend/packages/ui/src/__tests__/_index]] · **Layer.** test

## Contract Pinned

| Assertion | What it fences off |
|---|---|
| label renders as an accessible `button` name | the basic a11y name |
| `loading` ⇒ `disabled` **and** `aria-busy="true"` **and** the label still in the DOM | the busy state must be announced *and* enforced; the label stays so the button keeps its natural width — no layout jump when a spinner appears |
| `onClick` fires when enabled, does **not** fire while `loading` | double-submit protection is real, not cosmetic |
| className contains `duration-(--motion-fast)` and `ease-out` | a bare `transition-*` would silently fall back to Tailwind's own default duration/curve, neither of which is a project token (qa §2) |
| `container.innerHTML` equals a hard-coded literal string | the `ButtonLink` extraction changed *zero bytes* of Button's render |
| `ButtonLink` class string is `toBe`-identical to the equivalent `Button` | the two stay visually one component |
| `ButtonLink` has no `type`, no `disabled`, no `aria-busy` | an anchor must not inherit the button-only surface |

## Behavior

The loading test is the load-bearing one: it asserts three facts at once (disabled, `aria-busy`, label present) because dropping any one of them is a distinct real bug — a button that is busy but not disabled double-submits, one that is disabled but not `aria-busy` says nothing to a screen reader, and one that swaps its label for a spinner reflows the row. Note that `disabled || loading` means a `loading` button is genuinely disabled, so the "does not fire while loading" assertion is enforced by the DOM, not by a guard in the handler.

The byte-exact snapshot is unusual and worth understanding before touching it: it is a *deliberate* frozen capture taken before `ButtonLink` moved into the same module, so any change to `base`, `variants`, `sizes`, `focusRing` or the child `<span>` wrapper fails it. It is not a general regression net — it covers exactly `variant="primary" size="md" fullWidthMobile`. Legitimate design changes will fail it and the literal must be updated by hand; treat a failure as "did I mean to change Button's markup?", not as a bug.

The motion assertion greps the class string rather than computed style because jsdom resolves no CSS custom properties. Reduced motion is *not* covered here — `theme.css` kills the `transition` property itself under `prefers-reduced-motion`, which is a stylesheet fact outside jsdom's reach.

`ButtonLink`'s two tests are a pair: one says "same look" (class equality), the other says "different semantics" (no button-only attributes). Together they encode why the component exists — a navigation target that must not be a `<button onClick={navigate}>`.

## Depends On

- [[frontend/packages/ui/src/components/Button.tsx]] — the subject, both `Button` and `ButtonLink`
- [[Vitest]] — runner, `vi.fn()` (entity)
- [[Testing Library]] — `render` / `rerender` / `screen` (entity)

## Depended On By

- nothing — a leaf test

## Concepts

- [[Design Tokens]]
- [[Accessibility Compliance]]

## Tests

- this *is* the test

## Notes

Clicks use the DOM's native `.click()` rather than `fireEvent` / `userEvent`; sufficient here because the assertions are about the disabled attribute, not about pointer/keyboard event sequencing.
