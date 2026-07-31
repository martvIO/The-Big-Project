---
tags: [frontend, manage, react, appointment-types, settings, money, hardcoded-hebrew, f7]
sources: [frontend/apps/manage/src/components/TypesSection.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/src/components/TypesSection.tsx
blob: de715801ef7491dbc763b50e9cf57a59440035c1
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/apps/manage/src/components/TypesSection.tsx

**Role.** CRUD for appointment types — name, duration, audience (`all` / `brides_only`), deposit requirement and amount, sort order — with edit performed **inline inside the list row** rather than on a separate screen, and archive behind a confirm modal. It is the screen that defines what a customer can book.

**Module.** [[frontend/apps/manage/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `TypesSection` | component | No props |
| `TypeDraft` | interface (module-private) | All-strings form state; deposit typed in ILS |
| `DraftFields` | component (module-private) | The one field row, shared verbatim by the create form and every inline edit |
| `toInput` / `draftFromType` | fn (module-private) | Draft ⇄ wire; `toInput` returns the DTO **or a Hebrew error string** |

## Behavior

`DraftFields` existing once is the point of the file's shape: create and edit render the identical control set, so the two forms cannot drift in labels, bounds or ordering. Only one row may be in edit mode (`editingId`), and cancelling discards the draft without touching the row.

`toInput` converts the ILS deposit to integer agorot, folds `0` and empty to `null`, trims the name, and runs `validateAppointmentType`; a bad decimal returns a Hebrew string the caller branches on by `typeof`. Money never travels in ILS. Note that `deposit_required` and `deposit_amount_agorot` are independent inputs here — the shared validator is what couples them.

Every mutation patches list state from the response (`setTypes` with the returned row) rather than refetching. Archive removes the row from the list entirely; there is no archive view for types, so an archived type is simply gone from this screen. The three error slots are separate on purpose — `createError` under the create form, `editError` inside the row being edited, `listError` above the list for archive failures — so a failure is always adjacent to the control that caused it.

Duration is bounded `1..1440` on the input, audience is a two-option `Select`, and the deposit field is `dir="ltr"` with `inputMode="decimal"` (an LTR island; the ₪ lives in the label). In the read-only row the deposit renders through `ilsFromAgorot` with a literal `₪` — the ban on hand-formatted shekels in [[frontend/scripts/qa-greps.sh]] is scoped to `apps/storefront/src` only, so the console is not covered by it.

**Hardcoded Hebrew** — no `useTranslation`.

## Depends On

- [[frontend/apps/manage/src/api.ts]] — `api.listAppointmentTypes`, `createAppointmentType`, `updateAppointmentType`, `archiveAppointmentType`; `errorMessage`
- [[frontend/apps/manage/src/validation.ts]] — `agorotFromIlsInput`, `ilsFromAgorot`, `validateAppointmentType`
- [[frontend/packages/ui/src/index.ts]] — `Badge`, `Button`, `Card`, `Input`, `Modal`, `Select`, `Skeleton`, `Toggle`
- [[React]]

## Depended On By

- [[frontend/apps/manage/src/App.tsx]] — rendered for the `types` nav key

## Tests

None. There is no `TypesSection.test.tsx`; only `validateAppointmentType` is covered, in [[frontend/apps/manage/src/__tests__/validation.test.ts]].

## Notes

`audience` is set here but is disclosure-only on the storefront — an anonymous visitor cannot be classified as a bride, so the public booking surface *labels* a brides-only type without enforcing it. Enforcement waits on a customer identity.

Spec and plan: [[.planning/specs/owner-settings.md]] · [[.planning/plans/owner-settings.md]].
