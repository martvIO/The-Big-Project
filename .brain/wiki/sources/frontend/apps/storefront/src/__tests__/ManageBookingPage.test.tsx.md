---
tags: [frontend, storefront, test, vitest, manage-booking, f16, focus-management, jerusalem, tokens]
sources: [frontend/apps/storefront/src/__tests__/ManageBookingPage.test.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/__tests__/ManageBookingPage.test.tsx
blob: 6e1a12e7d39e3c695806b3d59f95f8e423dcdaef
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/storefront/src/__tests__/ManageBookingPage.test.tsx

**Role.** F16's `/b/{token}` suite, organised around the page's six states — S (loading), L (upcoming), L2 (attendance confirmed), C (cancelled), P (past), X (invalid link) plus R (retryable failure) — with the cancel two-step, three focus destinations, state precedence when an action loses a race, and two deliberate absences.

**Module.** [[frontend/apps/storefront/src/__tests__/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `TOKEN` | const | `"mt-abc123"` — passed as the route prop and asserted absent from the DOM |
| `UPCOMING` / `ALREADY_PASSED` | const | `2099-…` and `2000-…`; the past/upcoming split is real clock arithmetic, so the fixtures sit either side of "now" by construction rather than being built from `Date.now()` |
| `answer(overrides)` | helper | a `ManageBookingResponse` — `{booking, policy, boutique}`, with `policy` explicitly nullable |
| `visible(value)` / `findVisible(value)` | helpers | the **one** occurrence of a string outside any `.sr-only` ancestor |
| `renderPage()` | helper | the route inside [[frontend/apps/storefront/src/components/StorefrontLayout.tsx]] |

## Behavior

`visible()` exists because `manage.attendanceDone` and `manage.cancelled` are each rendered twice **by design** — once on the page and once inside the visually-hidden region that announces the outcome — so a bare `getByText` matches both and throws. Filtering by `.sr-only` ancestry keeps those assertions about what she *sees*; the announcement is asserted separately through `role="status"`. `ApiError` is kept real, since the page branches on error **code** and status and a stubbed error class would make every state assertion vacuous.

The boutique-block precedence is pinned in both directions, and the reason is recorded: the layout fetch is **primary** because it carries the full profile (Instagram included, which the manage payload deliberately omits), so when both are present the payload's phone must not win; the payload is a fallback that exists only inside a 200, which is why state X with a failed layout fetch renders **no contact block at all** rather than inventing one.

**Focus is a first-class assertion in three places.** Confirming attendance unmounts the button that was clicked, so the transition rules its own destination and moves focus to the success line it just mounted — otherwise focus drops to `<body>` after the one action the page exists for. Opening the cancel reveal focuses the question itself; choosing "keep" collapses it and returns focus to the trigger.

The cancel two-step is a product decision made executable: one tap must never cancel a wedding-dress appointment, so the first click issues no request and only reveals the question. The policy window shown comes from **her accepted policy row** (a 72-hour fixture proves the page is not printing the 48 in the default), isolated as `<bdi dir="ltr">`; the consequence sentence is the *same* free-cancellation string on both sides of that window, because every F16-era booking is deposit-free and a forfeit warning about a deposit that was never taken would be a lie. With `policy: null` the window sentence disappears and the consequence stays. One test counts `.bg-danger` elements: zero before the reveal, exactly one after — the destructive register is reserved for the click that destroys.

State precedence is asserted from the server's answer, never from what the tap hoped: a 409 `BOOKING_ALREADY_STARTED` on confirm re-renders the **past** state (and specifically not the confirmed line), a 409 `BOOKING_CANCELLED` re-renders cancelled, and a cancel that loses the race closes its own reveal. A cancelled-and-old booking renders cancelled, not past. `BOOKING_LINK_INVALID` is distinguished from a plain `NOT_FOUND` — the dedicated code is what tells a rotated manage token from an archived dress on the same origin — and the plain 404 falls through to the retryable copy. A `TypeError("Failed to fetch")` is treated exactly like a 5xx.

Two tests assert absences. The page ships **no stepper and no reschedule action** — she arrived from a text message, not a flow, and self-serve rescheduling is a bigger product decision than a comms feature should smuggle in. And the token **never enters the DOM**: it is body-carried on the wire, so a stray render into a data attribute or a link would put it back somewhere that gets shared. A third absence test asserts the whole page body contains no `!`, which is mechanically checkable because the storefront's punctuation register bans exclamation marks outright.

The time assertion is `findByText(/10:00/)` against a `07:00Z` fixture — the suite runs in another zone, so a naive `toLocaleString` would print a different hour, which is the bug.

## Depends On

- [[frontend/apps/storefront/src/routes/ManageBookingPage.tsx]] — the subject
- [[frontend/apps/storefront/src/components/StorefrontLayout.tsx]] — the layout boutique fetch whose precedence is under test
- [[frontend/apps/storefront/src/api.ts]] — `ApiError` real; `lookupBooking`, `confirmAttendance`, `cancelBooking`, `getBoutiqueOnce` mocked
- [[frontend/apps/storefront/src/i18n/index.ts]] — wrapped in a local `t()`
- [[Testing Library]] · [[Vitest]]

## Depended On By

Nothing imports a test file.

## Concepts

- [[Jerusalem Time]] · [[Hebrew RTL Bidi]] · [[IS 5568 Accessibility]]

## Notes

`beforeEach` sets the URL to `/b/{TOKEN}` before rendering, so the layout branches into the manage shape; the token still reaches the component as a prop, and the DOM-absence test is about the rendered output rather than the address bar. See [[.planning/specs/booking-comms.md]].
