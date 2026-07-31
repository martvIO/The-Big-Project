---
tags: [frontend, ui, component, form, accessibility]
sources: [frontend/packages/ui/src/components/Toggle.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/components/Toggle.tsx
blob: 4a6e3acb3f81ef92d449fb7ccc1b3c2c29257ddf
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/components/Toggle.tsx

**Role.** The console's on/off setting control: a native `<input type="checkbox">` carrying `role="switch"`, wrapped in a `<label>` that also holds an optional description tied by `aria-describedby`. Overriding the role rather than building a switch widget is what buys full keyboard and AT support for free — space toggles it, the label click target is the whole row, and the checked state is native.

**Module.** [[frontend/packages/ui/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `Toggle` | fn | labelled switch |
| `ToggleProps` | interface | `{label, description?, checked, onCheckedChange, disabled?}` — `disabled` defaults to `false` |

## Behavior

Fully controlled and deliberately narrow: it does **not** extend `InputHTMLAttributes`, exposes no `ref`, no `name`, no `error` and no `className`. `onCheckedChange(e.target.checked)` hands the caller the new boolean rather than the event, so a call site never touches the DOM node. `useId()` generates the id for `htmlFor`/`id`; the description gets `${id}-desc` and is referenced by `aria-describedby` only when present, which keeps it out of the accessible *name* while still being announced.

`role="switch"` on a checkbox is the intentional divergence from its sibling [[frontend/packages/ui/src/components/Checkbox.tsx]], which is a plain checkbox with **no** role override, an `error` prop and a 44px touch row. The split is semantic, not cosmetic: a switch is a setting that takes effect as a state ("deposit required"), a checkbox is a choice submitted with a form ("I agree to the terms"). `frontend/packages/ui/src/__tests__/form-primitives.test.tsx` pins both halves — it asserts `Toggle` is findable by `role="switch"` and that `Checkbox` has no `role` attribute and produces no `switch` at all.

Visual state comes from `accent-gold-strong` on the native control, so the checked colour follows the OS control rendering rather than a hand-drawn track and thumb. Disabled adds `disabled:cursor-not-allowed disabled:opacity-60` — note that this dims the control but not the label text, and there is no `aria-disabled` beyond the native `disabled` attribute (which is correct: a disabled input is already removed from the tab order and announced as unavailable).

Geometry is `size-5` (20px) on the box with `mt-0.5` optical alignment against the label's first line. That is smaller than the 24px box and `min-h-11` row `Checkbox` ships, so the *box* here is under the 44px touch target — the wrapping `<label>` is the real hit area, and it is only as tall as its content.

## Depends On

- [[frontend/packages/ui/src/lib/styles.ts]] — `cn`, `focusRing`

## Depended On By

- [[frontend/packages/ui/src/index.ts]] — re-exports `Toggle` + `ToggleProps`
- [[frontend/apps/manage/src/components/ProfileSection.tsx]] — the boutique `toggles` settings block
- [[frontend/apps/manage/src/components/CatalogSection.tsx]] · [[frontend/apps/manage/src/components/DressEditor.tsx]] · [[frontend/apps/manage/src/components/HoursSection.tsx]] · [[frontend/apps/manage/src/components/TypesSection.tsx]]

## Concepts

- [[Accessibility Compliance]]

## Tests

- [[frontend/packages/ui/src/__tests__/form-primitives.test.tsx]] — asserts the `switch` role, that the visible label is its accessible name, and that clicking reports `true` through `onCheckedChange`

## Notes

The storefront never mounts this component — it is a console-only control. Do not add an `error` prop here to save a file; that is what `Checkbox` is for, and the two roles must stay distinguishable in the AT tree.

A search for `Toggle` in [[frontend/apps/manage/src/api.ts]] is a false hit: that file's `toggles` is the settings payload key, unrelated to this component.
