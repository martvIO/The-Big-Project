---
tags: [frontend, typescript, test]
sources: [frontend/apps/manage/src/__tests__]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/src/__tests__
blob: 0a9a1c20876eec0cf3ee0b60b809e2c3b7277c61
commit: 13d107b8b16f1f2676f1cdb1c994f95822fe2ba0
kind: directory
applicability: active
---

# frontend/apps/manage/src/__tests__/

**Purpose.** Vitest suites for the console, including the axe passes that carry F15's accessibility coverage — the console sits behind a login, so e2e cannot reach it.

**Parent.** [[frontend/apps/manage/src/_index]]

## Files

- [[frontend/apps/manage/src/__tests__/BookingDetail.test.tsx]] — The largest suite in the console (~1000 lines) and F15's centre of gravity: the booking detail panel's facts, its state-dependent transition controls, three confirm surfaces, the reschedule dialog, an unusually thorough focus-management…
- [[frontend/apps/manage/src/__tests__/BookingsSection.test.tsx]] — The F15 day-list suite: the date filter defaults to the **Jerusalem** calendar date, the four load states render as designed, statuses are carried by the Hebrew *word* rather than colour, bidi isolation is correct per field, and two real…
- [[frontend/apps/manage/src/__tests__/CatalogSection.test.tsx]] — The suite for the dress list screen: empty-vs-filtered-empty states, the three-way stock badge, offset paging, a 300 ms debounced search that resets the offset, the archive filter, the list↔editor hand-off that patches rows **and the…
- [[frontend/apps/manage/src/__tests__/MediaGallery.test.tsx]] — The suite for the three-step photo upload orchestration (presign → upload → confirm) and the gallery around it: strict sequencing, per-file failure isolation with two *different* recovery paths depending on the failure, slot budgeting…
- [[frontend/apps/manage/src/__tests__/Nav.test.tsx]] — The suite for the console's role-filtered section nav — that an owner sees seven items and a shift manager six, that an *unknown* role yields an empty nav instead of a white screen, and that a role handover mid-session cannot strand the…
- [[frontend/apps/manage/src/__tests__/ProfileSection.test.tsx]] — The smallest component suite in the console, and the only one whose main assertion is about **DOM order**: the "these fields are published" notice must sit under the profile heading and *above* the fields it describes.
- [[frontend/apps/manage/src/__tests__/StaffSection.test.tsx]] — The F51 staff-management suite: list states, bidi per field, create with the "you deliver the password yourself" notice, inline edit that sends only what moved, the self-row's two special cases (no role control, current-password required)…
- [[frontend/apps/manage/src/__tests__/TermsSection.test.tsx]] — Pins three properties of the cancellation-policy screen: history is **append-only** (no edit or delete affordance ever renders), the no-policy-yet blocker gates bookings, and the publish form is owner-only while the blocker and the history…
- [[frontend/apps/manage/src/__tests__/VariantMatrix.test.tsx]] — The suite for the per-dress size/quantity matrix: EU quick-entry chips, case- and whitespace-insensitive duplicate refusal *before* any request, one full-replace PUT for the whole matrix, and a disabled (create-mode) state whose reason…
- [[frontend/apps/manage/src/__tests__/api.test.ts]] — The wire-contract suite for the console's hand-written fetch client: error extraction from the house error envelope, request mechanics (cookies, JSON, id encoding), the S3 direct-POST upload, and the exact path/method/body of every…
- [[frontend/apps/manage/src/__tests__/i18n.test.ts]] — The proof that every dotted-literal copy key F15 (bookings) and F51 (staff) added actually *resolves* through i18next — plus two mechanical register checks over the Hebrew values and a completeness check over the Arabic bundle.
- [[frontend/apps/manage/src/__tests__/jerusalem.test.ts]] — The unit suite that pins the console's three Jerusalem-zoned date helpers to the *boutique's* calendar rather than the device's — the smallest file in the batch and the one every other date assertion in the console leans on.
- [[frontend/apps/manage/src/__tests__/validation.test.ts]] — The pure-function suite for the console's client-side validators, and — more importantly — the place where every **mirrored** bound is asserted against the literal value the backend uses, so a limit that drifts on one side fails here…
