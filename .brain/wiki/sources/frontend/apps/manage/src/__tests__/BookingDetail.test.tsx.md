---
tags: [frontend, manage, test, vitest, bookings, axe, accessibility, focus-management, bidi]
sources: [frontend/apps/manage/src/__tests__/BookingDetail.test.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/src/__tests__/BookingDetail.test.tsx
blob: c96fb0fa0d175e812ca458c65b00233600b5d741
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/apps/manage/src/__tests__/BookingDetail.test.tsx

**Role.** The largest suite in the console (~1000 lines) and F15's centre of gravity: the booking detail panel's facts, its state-dependent transition controls, three confirm surfaces, the reschedule dialog, an unusually thorough focus-management contract, and four `axe.run()` passes at zero violations.

**Module.** [[frontend/apps/manage/src/__tests__/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `FUTURE` / `PAST` | const | `2099-08-04T07:00:00Z` and `2020-08-04T05:00:00Z` — fixtures either side of "now" *by construction*, so the clock is never faked |
| `slot(startsAt, remaining)` | helper | an owner slot row (`capacity`, `remaining` — the manage grid, unlike the storefront's) |
| `detail(overrides)` / `listRow(overrides)` | helpers | `OwnerBookingDetail` and a one-row `OwnerBookingListResponse` |
| `mount(overrides)` | helper | resolves `getBooking` and renders `BookingDetail` with spy callbacks |
| `renderInShell(node)` | helper | `<main>` + the console's sr-only `<h1>`, for axe |
| `dialogOf(title)` | helper | finds the `<dialog>` around a heading, throwing a named error if absent |

Suites: load states · facts · transition controls · destructive trigger · cancel Modal · attendance outcomes · resend · phone correction · error rendering · list hand-off · `RescheduleDialog` · accessibility.

## Behavior

**Three of the four transitions are clock-guarded, and the suite refuses to fake the clock.** Fixtures sit in 2099 and 2020 instead — the same trick `backend/tests/test_booking_repositories.py` plays with its 2099 constants — so the tests never depend on timer mocking interacting with React effects.

The control matrix is asserted as an ordered array of *present* button names per state, and the rule is **absent, never disabled**: confirmed+future offers reschedule/resend/phone/cancel; confirmed+past offers only the two attendance outcomes (and explicitly **no** `role="alert"` — "confirmed and past, never marked" is not an error state per D3/Risk 8, so it is rendered as silence); `no_show` and `completed` each offer the other outcome plus the undo; `cancelled` offers nothing at all and names the storefront as the remedy. Where actions exist, the standing "we cannot verify delivery" notice is present; where none do, it is asserted **absent**, because nothing will be sent.

The destructive trigger test is a Tailwind trap made executable: `cn()` is a plain join with no class-merge, and the built stylesheet emits `.text-danger` before `.text-ink`, so a ghost Button with a `text-danger` className would silently lose to ghost's own `text-ink` and the cancel affordance would disappear. The test therefore demands a solid `bg-danger` Button and forbids `text-danger` / `bg-transparent`.

**Focus management is the deepest seam here**, and each case names the bug it prevents. A successful transition can unmount the control that was clicked, so focus moves to the announced `role="status"` cue. On *failure* nothing rescued it — `disabled={busy}` blurs the button the instant it is tapped — so the failing path moves focus to the alert (WCAG 2.4.3); the worst instance is the cancel modal, where `setConfirmingCancel(false)` and `setPending("cancel")` batch into one commit, the `<dialog>` unmounts (focus → `<body>`) and the trigger it would restore to is `disabled` in that same commit, making `.focus()` a no-op. A phone 400 renders in the Input's own error slot rather than the shared alert, so *that* path focuses the field instead. Modal dismissals restore focus to their trigger, because native `<dialog>` return lands on `<body>` under the jsdom stub.

Free text is rendered as **text and only text**: the notes test feeds `<script>alert(1)</script>` and a URL and asserts the tags are characters (`notes.textContent` is the literal string), no `<script>` or `<a>` element exists, line breaks survive via `whitespace-pre-wrap`, and the content sits in a bare `<bdi>`. `dress_size` gets a **bare** bdi too, and the comment explains why: it is a snapshot of `dress_variants.size_label`, unbounded owner-typed TEXT with no numeric constraint, so «מידה 36» is ordinary and `dir="ltr"` would render the digits on the wrong side — while a plain "36" still renders LTR under a bare bdi because there is no strong character to disagree with. Genuinely numeric runs (phone, date, time, seat, terms version) do take `<bdi dir="ltr">`.

`RescheduleDialog` **is** the confirm — one dialog, the consequence stated directly above a single submit, with no second Modal stacked on it. It fetches a 14-day window anchored at the booking's date and refetches **only** when the chosen date leaves that window (an in-window change filters in memory). The booking's own time is injected and pre-selected even when the engine drops it (a capacity-1 target the booking itself occupies never comes back), carrying the bare time because `SlotPicker` wraps every label in `<bdi dir="ltr">`; the current date is named above the picker instead. The date field has a `min` but deliberately **no `max`** — the horizon is a server bound, and a date past it simply materialises no slots. A 409 keeps the dialog open with the grid intact, and a slot-fetch outage renders in the muted register **with a retry button** — the list's `L-fail` declines a retry because re-selecting its date refetches, but here the alert *replaces* `SlotPicker` and the date field lives inside it, so without the button the dialog has one disabled control and «חזרה».

Two hand-off tests reach for [[frontend/apps/manage/src/components/BookingsSection.tsx]]. A cancel patches the row from the mutation response with one list fetch total. A **reschedule refetches the day** — `starts_at` is the field list membership, the server `total` and the server's `(starts_at, seat_index)` order all derive from, so a patched object stays parked at its old index; the cross-day case is the dangerous one, since the list prints no date and a stranded row is indistinguishable from a real appointment. The refetch is asserted to use the *same* arguments as the first call: the filter did not change, the booking left it. A re-submit of the unchanged pre-selected time announces **nothing**, because the server short-circuits to a no-op 200 and «המועד עודכן» would claim a state change that did not happen.

Error rendering maps four codes F15 owns to Hebrew (`BOOKING_TRANSITION_INVALID`, `TOO_MANY_ATTEMPTS`, `CUSTOMER_ALREADY_BOOKED`, `SLOT_UNAVAILABLE`) in the `text-danger` "fix this" register, and falls through to the server's own message for everything else — `VALIDATION_ERROR` is deliberately *not* in the map because its message is computed per field and cannot be reproduced client-side. A 409 leaves every previously-rendered fact exactly where it was: the console never guesses a new state from an error.

The four axe passes cover a live booking, the revealed phone field, a cancelled booking and the open reschedule dialog. Zero violations, no allowlist — this is the IS 5568 floor, not a style preference.

## Depends On

- [[frontend/apps/manage/src/components/BookingDetail.tsx]] — the subject (which mounts [[frontend/apps/manage/src/components/RescheduleDialog.tsx]])
- [[frontend/apps/manage/src/components/BookingsSection.tsx]] — for the hand-off suites
- [[frontend/apps/manage/src/api.ts]] — ten booking endpoints mocked; `ApiError` / `errorMessage` real
- [[frontend/apps/manage/src/i18n/index.ts]] · [[frontend/apps/manage/src/test/setup.ts]] — the `<dialog>` stub every Modal assertion needs
- [[axe-core]] · [[Testing Library]] · [[Vitest]]

## Depended On By

Nothing imports a test file.

## Concepts

- [[RTL And Bidi Isolation]] · [[Jerusalem Time]] · [[Accessibility Compliance]]

## Notes

The error-code loop calls `cleanup()` **inside** the iteration; without it the second render would find two of every button. Every `dialogOf(...)` assertion depends on the jsdom `<dialog>` stub in `test/setup.ts` — jsdom implements `showModal`/`close` only partially, and real focus-trap behaviour is a browser-QA concern, not covered here. See [[.planning/specs/owner-booking-management.md]].
