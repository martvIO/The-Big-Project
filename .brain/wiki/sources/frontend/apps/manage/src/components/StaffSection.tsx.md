---
tags: [frontend, manage, react, staff, roles, auth, i18n, rtl, accessibility]
sources: [frontend/apps/manage/src/components/StaffSection.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/src/components/StaffSection.tsx
blob: 45941a172dee8c0bfe8b7dd5677b39859c3da989
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/apps/manage/src/components/StaffSection.tsx

**Role.** Staff administration: list, inline-edit (display name, role, password), create, and deactivate — with every rule that differs for the *signed-in* staffer baked into the render rather than left to the server's refusal. It sends a minimal PATCH body on purpose, because an all-unchanged patch writes no audit row.

**Module.** [[frontend/apps/manage/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `StaffSection` | component | `{ staffId: string }` — the signed-in staffer's id, used for every `isSelf` branch |
| `EditDraft` | interface (module-private) | `{ displayName, role, password, currentPassword }` |
| `MAPPED_CODES` | const (module-private) | The four error codes this section speaks Hebrew for |
| `EMPTY_CREATE` | const (module-private) | New-staffer defaults; role defaults to `shift_manager` |

## Behavior

**Self differs in three places.** The role `Select` is not rendered for yourself (you cannot demote yourself out of ownership); the deactivate button is not rendered for yourself, because the server refuses it with a 409 and drawing a door that always refuses is worse than not drawing it; and a self password change additionally requires `current_password`. The edit form has no email field at all — the address is not editable.

`handleSave` builds an `UpdateStaffRequest` containing **only fields that actually moved**. This is not a payload optimisation: an all-unchanged patch is a no-op the server answers 200 without writing an audit row, so sending less is what keeps the audit table meaningful. The one 400 these forms can produce is a wrong `current_password` — every other 400 is caught client-side by a mirrored bound — so a 400 on a self-edit is rendered as field-local Hebrew in the current-password `Input`'s `error` slot, and everything else goes to the shared alert.

Error text goes through a `message()` helper that translates only `MAPPED_CODES` (`DUPLICATE_EMAIL`, `LAST_OWNER_REQUIRED`, `STAFF_SELF_MANAGE`, `NOT_AUTHORIZED`) and otherwise shows the server's own text. **That set is pinned by nothing.** `SPEC_ERROR_CODES` in [[backend/tests/test_staff_api.py]] is a Python set checked against a Python module; no test reads this file. A fifth staff error code would render in English with a fully green build, and the only remedy is to add it here by hand.

Focus after a confirm: the deactivate trigger lives in the row it acts on, so a *successful* deactivate unmounts it and native `<dialog>` focus-return lands on `<body>`. The effect restores the trigger when it is still `isConnected` (cancel) and falls back to the section heading when it is not (removal). The trigger ref is captured from `event.currentTarget` at click time rather than bound per row.

The create form's password input is `autoComplete="new-password"` deliberately: without it the owner's browser offers **her own console credential** for the new staffer's account — a real way to create an account nobody can sign into. The email input is `autoComplete="off"` for the same reason.

Bidi follows the house rule: `display_name` takes a **bare** `<bdi>` (a `dir="ltr"` on a Hebrew name is itself a defect), the email gets `<bdi dir="ltr">`. The role `Badge` carries the **word**; colour is redundant reinforcement only. The deactivate modal uses `<Trans>` with a `bdi` component rather than `t()` with interpolation, so the name lands inside a bare `<bdi>` exactly as the list row does — every founding owner is seeded with `display_name = owner_email`, so a Latin run with neutral edge characters inside a Hebrew sentence is the norm here, not the exception.

This section uses `useTranslation()` throughout.

## Depends On

- [[frontend/apps/manage/src/api.ts]] — `api.listStaff`, `createStaff`, `updateStaff`, `deactivateStaff`; `ApiError`, `errorMessage`, the `StaffMember` / `StaffRole` / request types
- [[frontend/apps/manage/src/validation.ts]] — `validateStaffDraft`
- [[frontend/apps/manage/src/i18n/he.ts]] — the `staff.*` keys, including `staff.error.<CODE>`
- [[frontend/packages/ui/src/index.ts]] — `Badge`, `Button`, `Card`, `Input`, `Modal`, `Select`, `Skeleton`
- [[React]] · [[i18next]] — `useTranslation` and `Trans`

## Depended On By

- [[frontend/apps/manage/src/App.tsx]] — rendered for the `staff` nav key, with `staffId={staff.id}`
- [[frontend/apps/manage/src/__tests__/StaffSection.test.tsx]]

## Tests

- [[frontend/apps/manage/src/__tests__/StaffSection.test.tsx]] — ~38 cases: the three self-branches, the minimal-PATCH body, the mapped error codes, the current-password 400, and focus restoration after cancel vs. removal

## Notes

The Hebrew/English boundary is the thing to watch in this file. `errorMessage()` surfaces the API's English verbatim, so any staff error code outside `MAPPED_CODES` reaches the owner in English. Adding a backend staff error code is therefore a two-repo change even though nothing enforces it.

Spec and plan: [[.planning/specs/staff-management.md]] · [[.planning/plans/staff-management.md]] · [[.planning/specs/staff-roles-gating.md]]. Screen design and copy: [[.planning/design/screens/manage-staff/manage-staff.md]] · [[.planning/design/screens/manage-staff/copy.md]].
