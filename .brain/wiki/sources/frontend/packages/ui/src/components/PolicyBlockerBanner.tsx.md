---
tags: [frontend, ui, react, console, banner, policy]
sources: [frontend/packages/ui/src/components/PolicyBlockerBanner.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/components/PolicyBlockerBanner.tsx
blob: 02960b024de8fe376f1fffa9f601f85a5ee3e4df
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/components/PolicyBlockerBanner.tsx

**Role.** The console's "you cannot proceed until you set this up" notice — warning-text on paper with a gold-strong inline-start stripe and a single underlined text button that routes the owner to the missing setting. Deliberately **not red and icon-less**: this is a blocked precondition (no cancellation policy yet), not an error or an alarm.

**Module.** [[frontend/packages/ui/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `PolicyBlockerBanner` | fn | `{message, actionLabel, onAction, className?}` |
| `PolicyBlockerBannerProps` | type | as above; all three content props are required |

## Behavior

Stateless and unconditional — it renders whenever the caller mounts it, so the "is the policy missing?" decision lives entirely at the call site. The stripe uses the logical `border-s-4`, never `border-l`/`border-r`, so it sits on the inline-start edge under RTL as intended; `frontend/scripts/qa-greps.sh` bans the physical variants mechanically.

The action is a real `<button type="button">` styled as a link rather than an `<a>`, because it triggers in-app navigation through `onAction` rather than a URL — correct for the keyboard and for screen readers, and it carries the shared `focusRing`. The banner has **no `role="alert"` and no live region**: it is a standing page condition, not something announced on change, and announcing it would fight the "cautionary restraint, not an alarm" intent. All copy arrives as props — the package ships no Hebrew and has no i18next dependency.

## Depends On

- [[frontend/packages/ui/src/lib/styles.ts]] — `cn`, `focusRing`
- [[Tailwind CSS]]

## Depended On By

- [[frontend/packages/ui/src/index.ts]] — barrel re-export

## Concepts

- [[Design Tokens]]

## Tests

- [[frontend/packages/ui/src/__tests__/console-composites.test.tsx]] — renders the message and routes the action

## Notes

**No app imports this yet.** `git grep -w PolicyBlockerBanner` outside this package hits only the barrel and its own test — the manage console's terms/policy gate has not been wired to it. It is exported, styled and tested surface awaiting a call site, not dead code; do not delete it, but do not assume any screen currently shows it either.
