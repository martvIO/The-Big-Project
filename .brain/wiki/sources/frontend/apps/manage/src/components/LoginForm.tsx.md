---
tags: [frontend, manage, react, auth, accessibility, branding, i18n]
sources: [frontend/apps/manage/src/components/LoginForm.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/src/components/LoginForm.tsx
blob: 7f0d8717fb7f3c641cc965e65654b1fa3e6b5114
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/apps/manage/src/components/LoginForm.tsx

**Role.** The console's unauthenticated screen: a MODRYN-branded email/password form that calls `api.login` and hands the resulting `Staff` up to [[frontend/apps/manage/src/App.tsx]]. It is the only manage screen rendered **outside** `ConsoleShell`, which is why it has its own `<main>` and its own `<h1>` — and why the login screen has no skip link.

**Module.** [[frontend/apps/manage/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `LoginForm` | component | `{ onLogin: (staff: Staff) => void }` — the only prop; there is no `onError` and no redirect concept |

## Behavior

`handleSubmit` prevents default, flips `busy`, awaits `api.login(email, password)` and calls `onLogin` with the result. The failure message is `errorMessage(loginError)` **verbatim from the API** — deliberately, because the auth surface returns one generic credential message for both "no such account" and "wrong password" (anti-enumeration); replacing or refining it client-side would be the leak.

The heading is a lockup rather than text: the SVG mark carries `alt=""` (decorative), the Latin `MODRYN` wordmark is `aria-hidden` and `dir="ltr"`, and the actual Hebrew title rides in an `sr-only` span. Announce either of the first two and the screen reads its own name twice. This is the same construction `ConsoleShell` uses, so exactly one `h1` exists on the page either way.

Both inputs are `dir="ltr"` — an email address and a password are Latin/numeric runs, and only the field *content* flips; the box keeps its RTL position. `autoComplete="email"` / `"current-password"` are set so the browser fills the owner's own credential here (contrast [[frontend/apps/manage/src/components/StaffSection.tsx]], which forces `new-password` precisely to stop that). The submit button uses the `Button` `loading` prop, which also sets `disabled`.

## Depends On

- [[frontend/apps/manage/src/api.ts]] — `api.login`, `errorMessage`, `Staff`
- [[frontend/apps/manage/src/assets/modryn-mark.svg]] — the lockup mark, imported as a URL
- [[frontend/packages/ui/src/index.ts]] — `Button`, `Card`, `Input`
- [[React]] · [[i18next]]

## Depended On By

- [[frontend/apps/manage/src/App.tsx]] — rendered whenever `staff` is null

## Tests

- [[frontend/e2e/a11y.spec.ts]] — "manage: login screen has zero axe A/AA violations + Hebrew title" and "manage: login screen is MODRYN-branded and still has exactly one h1"

## Notes

Because this screen sits outside `ConsoleShell`, anything the shell provides — the skip link, the `#console-main` landmark, the nav — is absent here. That is intended: there is nothing to skip past.

Spec: [[.planning/specs/owner-auth.md]] · [[.planning/specs/modryn-branding.md]].
