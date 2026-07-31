---
tags: [frontend, manage, react, availability, settings, hardcoded-hebrew, timezone-defect, f7]
sources: [frontend/apps/manage/src/components/HoursSection.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/src/components/HoursSection.tsx
blob: 6e0ab5b272a3d217591fe9511d82b9623046df53
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/apps/manage/src/components/HoursSection.tsx

**Role.** The availability screen: the weekly opening-window list (one row per *window*, so a lunch break is two rows on the same day) edited as a whole-list draft and saved with `replaceWeeklyRules`, plus a separate append-only list of dated exceptions — closed-all-day or special hours — each added and removed one at a time.

**Module.** [[frontend/apps/manage/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `HoursSection` | component | No props |
| `DAY_NAMES` | const (module-private) | Sunday-first Israeli week, index 0–6 matching `day_of_week` |
| `toInputTime` | fn (module-private) | Trims the backend's `HH:MM:SS` to the `HH:MM` that `<input type="time">` accepts |
| `formatDate` | fn (module-private) | `he-IL` medium date for the exception list — see the defect below |

## Behavior

Two independent save models sit in one screen, and the difference is visible in the UI. The weekly rules are a **draft**: add-window, remove and every field edit only mutate local state and clear `rulesSaved`, and nothing reaches the server until «שמירת שעות פעילות», which validates through `validateWeeklyRules` and then reloads the list from the response. Exceptions are **immediate**: the add form POSTs and prepends the created row, and removal is a `Modal`-confirmed DELETE that filters the row out. There is no dirty warning on the weekly list — only a transient «נשמר לפני רגע».

A new window defaults to Sunday 09:00–17:00, capacity 1. `capacity` is edited here and is the fitting-room throughput number the storefront's `HoursRow` deliberately never publishes. Row keys are array indices, which is safe only because rows are edited in place and appended or removed at known positions.

Load failure is terminal for the screen: with `rules === null` the component returns a bare `role="alert"` paragraph and no form at all, so there is no retry short of remounting the section. Exception errors are shown inline and do not take the screen down.

**Hardcoded Hebrew** — no `useTranslation`. Day names, labels, validation copy and modal text are all literals.

## Depends On

- [[frontend/apps/manage/src/api.ts]] — `api.getAvailability`, `replaceWeeklyRules`, `addAvailabilityException`, `removeAvailabilityException`; `errorMessage`
- [[frontend/apps/manage/src/validation.ts]] — `validateWeeklyRules`, `validateExceptionTimes`
- [[frontend/packages/ui/src/index.ts]] — `Badge`, `Button`, `Card`, `Input`, `Modal`, `Select`, `Skeleton`, `Toggle`
- [[React]]

## Depended On By

- [[frontend/apps/manage/src/App.tsx]] — rendered for the `hours` nav key

## Tests

None. There is no `HoursSection.test.tsx`; the validators it delegates to are covered by [[frontend/apps/manage/src/__tests__/validation.test.ts]], and the zoned-hours helpers in [[frontend/packages/ui/src/lib/hours.ts]] have their own suite — but this component's own behaviour is untested.

## Notes

**Timezone defect worth knowing about.** `formatDate` builds `new Intl.DateTimeFormat("he-IL", { dateStyle: "medium" })` with **no `timeZone`**, and formats `new Date(\`${isoDate}T00:00:00\`)` — a date-time literal with no offset, which JS parses in the *device* zone. So an exception date renders in the viewer's zone, not Jerusalem, and on a device behind Israel it can display the previous calendar day. Every other date read in the app goes through [[frontend/apps/manage/src/lib/jerusalem.ts]] or [[frontend/packages/ui/src/lib/hours.ts]], both of which pass `timeZone: JERusalem` explicitly. [[frontend/scripts/qa-greps.sh]] does list this construction, but only in its advisory "review" block — that block prints and never sets a non-zero exit — so it does not gate.

Spec and plan: [[.planning/specs/owner-settings.md]] · [[.planning/plans/owner-settings.md]] · [[.planning/plans/availability-slot-engine.md]].
