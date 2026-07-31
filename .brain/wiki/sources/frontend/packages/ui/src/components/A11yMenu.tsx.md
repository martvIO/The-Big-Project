---
tags: [frontend, ui, react, accessibility, disclosure, composite]
sources: [frontend/packages/ui/src/components/A11yMenu.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/components/A11yMenu.tsx
blob: e7bdc4483cceb26f9fd48e24036b37e038650dcf
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/components/A11yMenu.tsx

**Role.** The first-party accessibility menu — a fixed floating trigger that discloses five independent toggle buttons, each of which sets or clears a `data-a11y-*` attribute on `<html>` for [[frontend/packages/ui/src/theme.css]] to style. Plus `A11yStatementLink`, the footer link to the legally required `/accessibility` statement (הצהרת נגישות). Deliberately first-party: a third-party overlay widget is exactly what IS 5568 compliance is not.

**Module.** [[frontend/packages/ui/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `A11yMenu` | component | `{triggerLabel, controls, hasBookingBar?, className?}` |
| `A11yMenuControls` | interface | Five label strings: `contrast`, `textSize`, `readableFont`, `underlineLinks`, `stopMotion` — every string arrives as a prop, never from i18n inside the package |
| `A11yStatementLink` | component | `{href, children, className?}` — an underlined `gold-text` anchor with the shared focus ring |
| `A11yStatementLinkProps`, `A11yMenuProps` | interface | |

## Behavior

The panel is a **disclosure, not a menu**, and the source says so at length. `role="group"` + `aria-labelledby` names the set of five toggles without borrowing the APG menu contract (arrow-key roving focus, Escape, focus return) that this component does not implement — and worse, screen readers switch to application mode inside `role="menu"` and can swallow Tab, stranding the keyboard user. Each control is a `<button aria-pressed>`, which is what a toggle actually is. `aria-haspopup` is deliberately absent (it is synonymous with `aria-haspopup="menu"`, and dropping it also clears an axe `controlsWithinPopup` "incomplete" that could never be resolved). `aria-controls` is set **only while open**, because the panel is unmounted when closed and a dangling IDREF is reported by axe as `aria-valid-attr-value`.

Toggling is a genuine DOM side effect: `toggle` flips a key in local `active` state and correspondingly calls `document.documentElement.setAttribute(attr, "")` / `removeAttribute(attr)`. There is no persistence — a reload resets every boost. Both `menuId` and `triggerId` come from `useId`, so multiple instances would not collide.

Positioning carries two distinct fixes. **PRE-1**: the trigger is `fixed` at `inset-block-end: var(--space-4)`, and when `hasBookingBar` is true it lifts to `var(--space-a11y-clearance)` under `max-md` only — that token is defined in [[frontend/packages/ui/src/tokens.ts]] as `--cta-bar-height + --space-3`, so the clearance tracks the bar height rather than duplicating a magic number. **PRE-2** (the trigger painting over a page's last line of content) is explicitly *not* solved here and must not be: a `fixed` element costs a reservation that the scrolling document owes it, paid by the consumer's footer via `--space-a11y-footprint`. Hiding or un-fixing the trigger would be the wrong fix.

## Depends On

- [[frontend/packages/ui/src/lib/styles.ts]] — `cn`, `focusRing`
- [[frontend/packages/ui/src/tokens.ts]] / [[frontend/packages/ui/src/theme.css]] — `--space-a11y-clearance`, and the CSS that reacts to each `data-a11y-*` attribute
- [[React]] — `useId`, `useState`

## Depended On By

- [[frontend/packages/ui/src/index.ts]]
- [[frontend/apps/storefront/src/components/StorefrontLayout.tsx]] — renders both `A11yMenu` and `A11yStatementLink`; also owns the `--space-a11y-footprint` reservation
- [[frontend/apps/storefront/src/routes/AccessibilityPage.tsx]] — the statement page the link targets

## Concepts

- [[IS 5568 Accessibility]]
- [[Design Tokens]]

## Tests

- [[frontend/packages/ui/src/__tests__/chrome-composites.test.tsx]] — opens the menu and asserts the `<html>` attribute flips; asserts the controls are toggle buttons in a labelled *group* rather than a menu; asserts `aria-controls` is dropped when closed; asserts the PRE-1 clearance token is used when `hasBookingBar`
- [[frontend/apps/storefront/src/__tests__/accessibility.test.tsx]], [[frontend/apps/storefront/src/__tests__/StorefrontLayout.test.tsx]]
- [[frontend/e2e/storefront.spec.ts]]

## Notes

The trigger's glyph is a bare `◑` marked `aria-hidden`; the accessible name comes solely from `triggerLabel`. A caller that forgets to pass a translated `triggerLabel` ships an unnamed button — there is no fallback.
