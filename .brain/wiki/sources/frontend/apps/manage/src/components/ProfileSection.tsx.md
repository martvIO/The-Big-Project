---
tags: [frontend, manage, react, settings, profile, i18n, f7]
sources: [frontend/apps/manage/src/components/ProfileSection.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/src/components/ProfileSection.tsx
blob: 09a592842c89eee981d0234dce4bc5753519f25e
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/apps/manage/src/components/ProfileSection.tsx

**Role.** The boutique-identity form and the console's landing screen: the six public profile fields (essence, phone, address, maps URL, Instagram, description) plus the two behaviour toggles (`deposits_enabled`, `brides_only`), loaded from and saved back to the single settings JSONB in one PATCH.

**Module.** [[frontend/apps/manage/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `ProfileSection` | component | No props |
| `ProfileForm` / `TogglesForm` | interface (module-private) | The two halves of the form state, both non-null strings/booleans |
| `fromSettings` | fn (module-private) | Coalesces every nullable server field to `""` / `false`, so no input is ever uncontrolled |

## Behavior

`fromSettings` is what keeps every field a controlled input: the API returns nullable values, and a `null` handed to a React `value` flips the input to uncontrolled mid-life. It is applied twice — on load, and again on the save response, so the form always re-syncs from the server rather than trusting the submitted draft.

The save is one `api.updateSettings({ profile, toggles })` covering both halves. Failure raises a `useToast` toast rather than an inline alert — this is the only section in the console that reports errors that way. Success shows a transient `common.saved` marker which every field change clears.

**The public-data disclosure is placed structurally, not decoratively.** The profile fields become world-readable on the storefront, so the notice sits under the *profile* heading which covers them — not under the settings heading, whose toggles are never published. `brides_only` and `deposits_enabled` are stored but their storefront semantics land with later features.

`phone`, `maps_url` and `instagram` are `dir="ltr"` LTR islands; the free-text fields inherit the document's RTL. Two `SectionHeading as="h2"` calls split the card, sitting under `ConsoleShell`'s single `sr-only` `h1`.

Unlike the other F7 sections, **this one goes through `useTranslation()`** — every visible string is a key in [[frontend/apps/manage/src/i18n/he.ts]].

## Depends On

- [[frontend/apps/manage/src/api.ts]] — `api.getSettings`, `api.updateSettings`, `errorMessage`, `Settings`
- [[frontend/packages/ui/src/index.ts]] — `Button`, `Card`, `Input`, `SectionHeading`, `Skeleton`, `TextArea`, `Toggle`, `useToast`
- [[React]] · [[i18next]]

## Depended On By

- [[frontend/apps/manage/src/App.tsx]] — the default section (`profile`) and therefore the first screen after login
- [[frontend/apps/manage/src/__tests__/ProfileSection.test.tsx]]

## Tests

- [[frontend/apps/manage/src/__tests__/ProfileSection.test.tsx]] — three cases: load, save round-trip, and the null-coalescing of absent fields

## Notes

The settings payload is a JSONB blob server-side, and this form sends the whole `{ profile, toggles }` object every time — so a field a later feature adds to the blob but not to `ProfileForm` would be dropped on the next save from this screen.

Spec and plan: [[.planning/specs/owner-settings.md]] · [[.planning/plans/owner-settings.md]].
