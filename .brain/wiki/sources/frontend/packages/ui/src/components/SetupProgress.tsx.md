---
tags: [frontend, ui, component, manage-console, onboarding]
sources: [frontend/packages/ui/src/components/SetupProgress.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/components/SetupProgress.tsx
blob: 105c80304caec631adfb61a99ec3ffebe451fa9c
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/components/SetupProgress.tsx

**Role.** The console's onboarding checklist card: a list of setup sections with a done/not-done tick, a count line, and one button that jumps to the **first incomplete** section. Both the count and the target are *derived* from the `items` array — nothing about "3 of 4" is authored anywhere, so the card cannot drift out of sync with the section responses that feed it.

**Module.** [[frontend/packages/ui/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `SetupProgress` | fn | the checklist card |
| `SetupProgressItem` | interface | `{key, label, done}` — one row |
| `SetupProgressProps` | interface | `{items, headingLabel, countLabel, onGoTo, goToLabel?, className?}` |

## Behavior

`done` is `items.filter(i => i.done).length` and `total` is `items.length`, both recomputed on every render; `firstIncomplete` is the first `!done` item in **array order**, so the caller's ordering of `items` *is* the recommended completion order. `countLabel` is a function `(done, total) => string` rather than a template string, which is how the Hebrew phrasing stays in the app's i18n bundle while the numbers stay derived here — this package holds no Hebrew and has no i18next dependency.

The jump control is a real `<button type="button">` calling `onGoTo(firstIncomplete.key)`, explicitly **not** an anchor — the file comments "Never an `href="#"`", which is also a rule [[frontend/scripts/qa-greps.sh]] greps for mechanically. It renders only when there *is* an incomplete item **and** `goToLabel` was supplied; at 4/4 the card is a plain summary with no dangling call to action.

The ✓ / ○ glyphs are `aria-hidden` decoration. Completion is not carried by that glyph alone — the label's own colour flips between `text-ink` and `text-ink-muted` — but note that neither channel is text a screen reader can read, so the *announced* content of a done and a not-done row is identical. The accessible signal of overall progress is the `countLabel` line, which is why it is required rather than optional.

There is no progress bar, no percentage and no `aria-valuenow`: this is a `<ul>` of `<li>`, which is what a checklist is.

## Depends On

- [[frontend/packages/ui/src/components/Card.tsx]] — the surface it renders into
- [[frontend/packages/ui/src/lib/styles.ts]] — `cn`, `focusRing`

## Depended On By

- [[frontend/packages/ui/src/index.ts]] — re-exports `SetupProgress` + `SetupProgressProps` + `SetupProgressItem`
- **no app mounts it yet** — see Notes

## Concepts

- [[Accessibility Compliance]]

## Tests

- [[frontend/packages/ui/src/__tests__/console-composites.test.tsx]] — asserts the interpolated count (`2/4`), that the button targets the first incomplete key, and that the card renders correctly at both 0/4 and 4/4

## Notes

**Warn a future reader: this component is currently exported and tested but unmounted.** Searching the apps for `SetupProgress` turns up only [[frontend/packages/ui/src/index.ts]] and its own test — [[frontend/apps/manage/src/App.tsx]] does not render it. It is shipped ahead of the console screen that will host it, so treat it as staged rather than dead; deleting it would remove a covered, reviewed component, but do not assume the console shows a setup checklist today.
