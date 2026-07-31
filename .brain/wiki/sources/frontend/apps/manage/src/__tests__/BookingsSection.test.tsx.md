---
tags: [frontend, manage, test, vitest, bookings, axe, accessibility, bidi, jerusalem]
sources: [frontend/apps/manage/src/__tests__/BookingsSection.test.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/src/__tests__/BookingsSection.test.tsx
blob: d7831448c2e7f965e0c0a04e0c7d7b89504c0a75
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/apps/manage/src/__tests__/BookingsSection.test.tsx

**Role.** The F15 day-list suite: the date filter defaults to the **Jerusalem** calendar date, the four load states render as designed, statuses are carried by the Hebrew *word* rather than colour, bidi isolation is correct per field, and two real `axe.run()` passes must report **zero** violations.

**Module.** [[frontend/apps/manage/src/__tests__/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `row(overrides)` | helper | an `OwnerBookingRow`; `starts_at` is `2026-08-04T07:00:00Z` = 10:00 Jerusalem, 03:00 New York |
| `day(items, total)` | helper | the `OwnerBookingListResponse` envelope, `limit: 50` |
| `renderInShell(node)` | helper | wraps the section in `<main>` + the console's single sr-only `<h1>`, reproducing `ConsoleShell` for axe |
| `BookingsSection day filter` | suite | Jerusalem default, refetch on change, LTR island |
| `BookingsSection states` | suite | L-load, L-fail, L-empty, the loaded list, time/bidi/attendance rendering |
| `BookingsSection status badges` | suite | the four status words; cancelled rows stay in the list |
| `BookingsSection accessibility` | suite | axe on the loaded list and the empty day; heading level |

## Behavior

**IS 5568 / WCAG 2.0 AA is a legal requirement in this product**, and the two `axe.run(container)` assertions are the statutory floor expressed mechanically: `expect(results.violations).toEqual([])`, no allowlist, no severity filter. They are given a 20 s timeout because axe is slow, and they run against `renderInShell` rather than a headless fragment — scanning the section alone would trip a spurious "page must have one main landmark / h1" family of rules and, worse, would let a *real* heading-order break pass because the `<h1>` it skips past is not in the tree.

The day filter defaults through the Jerusalem-zoned helper, and the test proves it with `21:30Z` on the 4th — 00:30 on the **5th** in Jerusalem, 17:30 on the 4th on this runner's pinned `TZ=America/New_York` clock. Both the request (`{ date: "2026-08-05", … }`) and the field's value are asserted, so a component that formatted correctly but queried the device date would still fail. The field itself is a `type="date"` with `dir="ltr"` and a visible label — an LTR island inside an RTL page.

Bidi is asserted per field and the two rules are opposite: a **time** is `<bdi dir="ltr">`, while a customer or dress name is a **bare** `<bdi>` with no `dir` attribute at all, because `dir="ltr"` on Hebrew free text is itself a bidi defect.

The state suite pins the register as well as the content. `L-fail` is an alert in the **outage** register — `text-ink-muted`, never `text-danger` — with no retry control, no half-loaded list and no empty state stacked underneath. `L-empty` is an `EmptyState` with no CTA, because the owner cannot create a booking at all (spec Q6), so an action prompt would point at nothing; the shared `role="status"` count line doubles as the loading announcement («טוען תורים…») because the shipped console otherwise announces nothing while loading. Cancelled rows stay in the list (D17) and are demoted no further than the badge — a cancelled row is the owner's evidence that the slot re-opened — and attendance renders as muted words on the meta line so that each row still carries exactly **one** Badge.

Statuses are asserted by their Hebrew word, never by class: the mapping has to survive greyscale, which is the same reason colour is never the sole signal.

## Depends On

- [[frontend/apps/manage/src/components/BookingsSection.tsx]] — the subject
- [[frontend/apps/manage/src/api.ts]] — `listBookings` mocked; `ApiError` / `errorMessage` real
- [[frontend/apps/manage/src/i18n/index.ts]] — side-effect import
- [[axe-core]] · [[Testing Library]] · [[Vitest]]

## Depended On By

Nothing imports a test file. [[frontend/apps/manage/src/__tests__/BookingDetail.test.tsx]] re-mounts this component to exercise the list↔detail hand-off.

## Concepts

- [[RTL And Bidi Isolation]] · [[Jerusalem Time]] · [[Accessibility Compliance]]

## Notes

The list deliberately prints no date — the date *is* the filter — which is why a cross-day reschedule has to refetch rather than patch; that consequence is tested in the detail suite, not here. See [[.planning/specs/owner-booking-management.md]].
