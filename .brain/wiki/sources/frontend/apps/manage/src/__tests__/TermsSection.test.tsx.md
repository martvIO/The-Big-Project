---
tags: [frontend, manage, test, vitest, terms, rbac, immutability]
sources: [frontend/apps/manage/src/__tests__/TermsSection.test.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/src/__tests__/TermsSection.test.tsx
blob: e2e9655a12a17cd6344f78a7487e0b2978581231
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/apps/manage/src/__tests__/TermsSection.test.tsx

**Role.** Pins three properties of the cancellation-policy screen: history is **append-only** (no edit or delete affordance ever renders), the no-policy-yet blocker gates bookings, and the publish form is owner-only while the blocker and the history are not.

**Module.** [[frontend/apps/manage/src/__tests__/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `emptyHistory` | const | `{ current: null, versions: [], total: 0, offset: 0, limit: 50 }` — the first-run shape |
| `version(n)` | helper | a `TermsVersion` fixture; `terms_text` is `נוסח גרסה {n}` so rows are addressable by text |
| `TermsSection setup blocker` | suite | blocker present on empty history, absent once a version exists |
| `TermsSection immutable history` | suite | no edit/delete button; the only mutation is "publish a new version" |
| `TermsSection create flow` | suite | POST body shape, refresh after save, client-side block on invalid input |
| `TermsSection role gating` | suite | F51 — owner sees the form, shift manager does not |

## Behavior

The immutability test is a *negative* query — `queryByRole("button", { name: /עריכה|מחיקה|עדכון/ })` must be null — paired with a positive one for «שמירת גרסה חדשה». That pairing is the point: asserting only the absence would also pass a screen with no controls at all. A published version is a legal artefact a customer accepted by number, so an in-place edit would rewrite what she agreed to; the create flow always POSTs.

The create test asserts the exact structured body (`terms_text`, `refundable_until_hours_before`, `forfeit_percent`) and then that `getTerms` was called **twice** — the list refreshes from the server after a save rather than being patched, which is the conservative choice for an append-only log. Its sibling checks that invalid input raises an inline `role="alert"` with `createTermsVersion` never called.

The role suite (F51) takes `role` as a prop and splits the screen in two. `POST /manage/terms` is one of the epic's two owner-only surfaces, so hiding the publish form from a shift manager is not cosmetic tidying: without it she taps the button and gets the generic 403, **whose message is English** and which `errorMessage()` surfaces verbatim into a Hebrew console. But the blocker stays for her, with its action sentence swapped — she still has to learn that bookings cannot be accepted, and hiding the blocker along with the form would leave the boutique silently unbookable for exactly the persona standing at the front desk. The owner's sentence points at a form («יש ליצור גרסה ראשונה למטה»); hers must not, and the test asserts her copy does **not** contain «למטה». `GET /manage/terms` is not owner-only, so the last case confirms she still reads the current policy and the full history.

The blocker is located by `data-testid="terms-setup-blocker"` rather than by copy, because its copy is exactly what the role tests vary.

## Depends On

- [[frontend/apps/manage/src/components/TermsSection.tsx]] — the subject
- [[frontend/apps/manage/src/api.ts]] — `getTerms` / `createTermsVersion` mocked
- [[Testing Library]] · [[Vitest]]

## Depended On By

Nothing imports a test file.

## Concepts

- [[Fail Closed Defaults]]

## Notes

The API module is mocked wholesale here (no `importActual`), so `ApiError` and `errorMessage` are **not** available in this file — error-path coverage for terms lives with the server suites. See [[.planning/specs/staff-roles-gating.md]] for the owner-only surface list.
