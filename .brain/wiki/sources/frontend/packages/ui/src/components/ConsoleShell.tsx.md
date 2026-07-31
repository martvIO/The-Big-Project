---
tags: [frontend, ui, react, manage, composite, navigation, accessibility]
sources: [frontend/packages/ui/src/components/ConsoleShell.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/components/ConsoleShell.tsx
blob: 480f656dd11759260781be850643d9c2089525de
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/components/ConsoleShell.tsx

**Role.** The entire frame of the owner/shift-manager console: skip link, header lockup with a logout button, the section nav, and a single `#console-main` panel capped at 720px that every section renders into. It owns the console's one `<h1>` (screen-reader only) and holds slots for a banner and a setup-progress card above the section content.

**Module.** [[frontend/packages/ui/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `ConsoleShell` | component | `{boutiqueName, title, logoutLabel, onLogout, skipLinkLabel, nav, activeKey, onNavigate, banner?, progress?, children}` |
| `ConsoleNavItem` | interface | `{key, label}` — `key` is the app's own section identifier, matched against `activeKey` |
| `ConsoleShellProps` | interface | |

## Behavior

**Navigation is "contract (b)": a plain `<nav>` of `<button>`s with `aria-current="page"`, and it is NOT `role="tab"`.** Tabs would promise the full ARIA tabs keyboard contract — roving `tabindex`, arrow-key movement between tabs, one tab stop for the set — which this component does not implement; declaring the role without keeping the contract is worse than not declaring it. Each button also carries `aria-controls="console-main"` because clicking swaps the content of that one panel; `aria-expanded` would be the disclosure pattern and is an anti-pattern on nav links. The active item is signalled twice — a `gold-strong` bottom border **and** `aria-current` plus `font-semibold` — so state is never carried by colour alone. Layout stacks full-width at ≤767 (`flex-col`, `w-full`, `text-start`) and becomes a horizontal row at ≥768 (`md:flex-row md:flex-wrap`).

The `<h1>` is `sr-only`. The visible header lockup is the boutique name in display type, which is not the page title — so the accessible heading is supplied separately via `title` and hidden. [[frontend/apps/manage/src/components/LoginForm.tsx]] reuses the same trick for the pre-auth screen, which is why the console never has two h1s across the login boundary.

`<main id="console-main" tabIndex={-1}>` is the skip link's target, and the `tabIndex={-1}` is what makes the jump actually move focus rather than only scroll. The 720px cap is repeated on the header row, the nav and the main — three separate `max-w-[720px]` containers, so the border-bottom of the header still spans the full viewport while its contents align with the content column.

Nothing here is stateful: `activeKey` and every callback are the app's. Focus is **not** moved to `#console-main` on navigation — a keyboard user who changes section stays on the nav button, which is correct for a nav (not a tab) but means a screen-reader user is not automatically taken to the new content.

## Depends On

- [[frontend/packages/ui/src/components/A11y.tsx]] — `SkipLink`
- [[frontend/packages/ui/src/lib/styles.ts]] — `cn`, `focusRing`
- [[React]] — `ReactNode`

## Depended On By

- [[frontend/packages/ui/src/index.ts]]
- [[frontend/apps/manage/src/App.tsx]] — the only consumer; supplies the nav list, the active key, the banner and the progress card

## Concepts

- [[Accessibility Compliance]]

## Tests

- [[frontend/packages/ui/src/__tests__/console-composites.test.tsx]] — asserts the active nav item is marked with `aria-current="page"` **and not `role="tab"`**, and that nav clicks and logout route through their callbacks
- [[frontend/apps/manage/src/__tests__/BookingsSection.test.tsx]], [[frontend/apps/manage/src/__tests__/BookingDetail.test.tsx]], [[frontend/apps/manage/src/__tests__/StaffSection.test.tsx]] — mount sections inside the shell

## Notes

`banner` and `progress` are unconstrained `ReactNode` slots rendered in fixed order above `children` — in practice [[frontend/packages/ui/src/components/PolicyBlockerBanner.tsx]] and [[frontend/packages/ui/src/components/SetupProgress.tsx]]. The shell does not check what it is handed.
