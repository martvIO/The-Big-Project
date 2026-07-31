---
tags: [frontend, manage, react, terms, legal, roles, hardcoded-hebrew, timezone-defect, f7]
sources: [frontend/apps/manage/src/components/TermsSection.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/src/components/TermsSection.tsx
blob: 8647637ba8ea03b3dec41ed781a81de6e65e544b
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/apps/manage/src/components/TermsSection.tsx

**Role.** The cancellation-policy screen: shows the version currently in force, an append-only read-only history, and — for owners only — the form that publishes a new immutable version. It also carries the setup blocker that tells the boutique it cannot accept a single booking until a policy exists.

**Module.** [[frontend/apps/manage/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `TermsSection` | component | `{ role: string }` — the signed-in staffer's role, passed down from [[frontend/apps/manage/src/App.tsx]]'s already-fetched `Staff` |
| `formatDate` | fn (module-private) | `he-IL` medium date + short time for a history entry — see the defect below |

## Behavior

**The `role` prop exists to avoid a specific 403.** `POST /manage/terms` is one of the shift-manager-console epic's two owner-only surfaces, but `GET /manage/terms` is not — so the nav item stays visible for both roles and only the publish form is withheld. Without the gate a shift manager taps «שמירת גרסה חדשה» and receives the generic 403, whose message is **English** and which `errorMessage()` surfaces verbatim into an otherwise fully-Hebrew console. The gate is presentational; the server is still the authority.

The setup blocker (`data-testid="terms-setup-blocker"`) renders for **both** roles when `history.versions` is empty — a shift manager must know the boutique cannot take bookings — but its action sentence swaps, because for her the form below is not there to point at. Its Hebrew is hardcoded to match the rest of the file, and that is a deliberate standing decision: these older sections are not retrofitted to i18n.

Every save creates a new permanent version; nothing is ever edited. The form validates through `validateTerms` before POSTing and then re-runs `load()` rather than patching, so "current" and the history list are always the server's answer. Defaults are 48 hours and 100% forfeit. A load failure is terminal for the screen — the component returns only a `role="alert"` paragraph, with no retry.

Only the latest page (50 versions) is fetched; the API supports offset paging when a deeper history view is wanted.

## Depends On

- [[frontend/apps/manage/src/api.ts]] — `api.getTerms`, `api.createTermsVersion`, `errorMessage`, `TermsHistory`
- [[frontend/apps/manage/src/validation.ts]] — `validateTerms`
- [[frontend/packages/ui/src/index.ts]] — `Button`, `Card`, `Input`, `Skeleton`, `TextArea`
- [[React]]

## Depended On By

- [[frontend/apps/manage/src/App.tsx]] — rendered for the `terms` nav key, with `role={staff.role}`
- [[frontend/apps/manage/src/__tests__/TermsSection.test.tsx]]

## Tests

- [[frontend/apps/manage/src/__tests__/TermsSection.test.tsx]] — the owner/shift-manager split on the publish form, and the blocker's two action sentences

## Notes

**Timezone defect worth knowing about.** `formatDate` constructs `new Intl.DateTimeFormat("he-IL", { dateStyle: "medium", timeStyle: "short" })` with **no `timeZone`**, so a version's `created_at` renders in the *device* zone rather than Jerusalem. Same class of bug as [[frontend/apps/manage/src/components/HoursSection.tsx]]; [[frontend/scripts/qa-greps.sh]] lists it only in its advisory, non-gating "review" block. The zoned helpers already exist in [[frontend/apps/manage/src/lib/jerusalem.ts]].

The two numbers published here are what the storefront shows a bride before she accepts, and `forfeit_percent` is a percentage **of the deposit**, not of the booking total.

Spec and plan: [[.planning/specs/owner-settings.md]] · [[.planning/plans/owner-settings.md]] · [[.planning/specs/staff-roles-gating.md]].
