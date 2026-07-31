---
tags: [frontend, typescript, ui]
sources: [frontend/apps/storefront/src/components/booking]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/components/booking
blob: bd7f25285488916e1248d107a1ea8e283f7f767b
commit: 13d107b8b16f1f2676f1cdb1c994f95822fe2ba0
kind: directory
applicability: active
---

# frontend/apps/storefront/src/components/booking/

**Purpose.** The booking flow's pickers, minus the slot picker, which was promoted into `packages/ui` when the owner console needed it too.

**Parent.** [[frontend/apps/storefront/src/components/_index]]

## Files

- [[frontend/apps/storefront/src/components/booking/SizeChips.tsx]] — The booking flow's size selector: native radios inside a `<fieldset>`, each input `sr-only` with its `<label>` drawn as a pill chip. App-local rather than promoted to `packages/ui` — the unavailable-but-still-selectable rule below is a…
- [[frontend/apps/storefront/src/components/booking/TypePicker.tsx]] — The appointment-type chooser on the slot step: a native `<fieldset>` of radio **rows**, each showing name, duration, an optional brides-only badge, and — when a deposit-required row is selected — an inline "call us" panel with the deposit…
