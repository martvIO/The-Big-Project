---
tags: [frontend, storefront, test, vitest, booking-flow, otp, slot-picker, jerusalem, focus-management, fake-timers]
sources: [frontend/apps/storefront/src/__tests__/BookPage.test.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/__tests__/BookPage.test.tsx
blob: ab3d22edd99927b749eaa0b886e4933a528ca51c
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/storefront/src/__tests__/BookPage.test.tsx

**Role.** The largest suite in the repo (~2160 lines) and the spine of the storefront booking feature: the five-step flow walked end to end (slot → details → terms → verify → confirm), the step guards, the OTP sub-states including a cooldown timer race, the full submit error-recovery matrix, and the exact `createBooking` payload. It also renders three pickers **directly** — `SlotPicker`, `TypePicker`, `SizeChips` — to pin their `error`/`notice` slot contract, which is what proved F15's promotion of `SlotPicker` into [[frontend/packages/ui/src/index.ts]] was behaviour-neutral.

**Module.** [[frontend/apps/storefront/src/__tests__/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `TERMS` · `SLOTS` · `appointmentType()` · `dressDetail()` · `booking()` | fixtures | the four wire shapes the flow reads |
| `AUG4_1000` … `AUG5_0000` | const | Jerusalem-anchored instants; `2026-08-04T21:00:00Z` is **00:00 on the 5th** in Jerusalem and 17:00 on the 4th in New York |
| `TYPED_PHONE` / `WIRE_PHONE` | const | `"050-123 4567"` and `"+972501234567"` — one normalisation, three calls |
| `DOWN` · `THROTTLED` · `GONE` · `OTP_WRONG` · `OTP_STALE` · `TOKEN_DEAD` · `SLOT_TAKEN` · `TERMS_MOVED` · `BROKEN` | const | the named `ApiError`s the recovery matrix is written against |
| `renderBook(step, dressId)` | helper | one step rendered **cold**, for shell and empty-state assertions |
| `BookFlow` / `renderFlow(path)` | helper | the route element driven by `matchRoute(usePathname())` — the real router's own composition |
| `walkToDetails` / `walkToTerms` / `walkToVerify` | helpers | cumulative walks; later steps are only honest when the earlier ones filled them |
| `passCooldown()` | helper | flush effects, **then** advance fake timers 60 s |
| `deferred<T>()` | helper | a hand-settled promise, used to hold submit in flight |

## Behavior

The two render helpers encode the file's central discipline. `BookPage` holds the whole flow in memory, so a later step rendered cold has no picked slot, no typed name and no accepted version; `renderFlow` therefore mounts the same element in the same position the Router does and the `walkTo*` helpers *walk* there, which is why state survives a back-navigation. `renderBook` is reserved for cases where cold is the point — the shell headings, the empty/dead-end blocks, and the confirm step's cold-load branch.

**`passCooldown()` is a recorded CI-only failure and its mechanism.** The resend cooldown's `setTimeout` is scheduled by an effect keyed on `cooling`, so a bare `advanceTimersByTime` can run *before* that effect commits — advancing past nothing, after which the timer is scheduled and never fires inside the test. Flushing pending effects first makes the timer exist before the clock moves. Locally the effect usually won the race; on a loaded runner it did not. Fake timers are installed with `shouldAdvanceTime: true` and restored in a `finally`, confined to the two tests that need them.

The three directly-rendered pickers are the F15 seam. `SlotPicker` must place its `error` **above** the `<legend>` (asserted with `compareDocumentPosition`), because a `<legend>` that is not the first element child stops naming its group — and the fieldset/legend/radio contract is exactly what a promotion into `packages/ui` could quietly break. The register is asserted by *colour*, with `themeTokens` painted into a real stylesheet first (jsdom loads no CSS, so an unstyled assertion passes whichever class the node carried) and a probe-vs-probe inequality guarding the guard. `slotUnavailable` is danger; `typeGoneRepick` and `sizeGoneRepick` are **warning**, because they are one semantic state — "the thing you picked is gone, pick another" — in which nothing she did failed; the same components' true validation errors stay danger. The comment records that the spec's register table and its measured contrast ledger disagreed, and that the ledger won as the measured accessibility artifact.

**Time is read from the boutique's calendar throughout.** The suite runs under `TZ=America/New_York`; a `21:00Z` slot must appear on the *next* date in the picker, the confirmation must print «יום שלישי» with `4.8.2026` and `10:00`, and the date input's `min`/`max` are bounded to the window the server actually returned. Every numeric run is checked for `<bdi dir="ltr">` — times, durations, the two refund numbers (`48`, `50%`) — while the tenant name and the dress name on the confirmation take a **bare** `<bdi>`, and one test asserts the absence of `dir` on them: owner text may be Hebrew, and forcing LTR on Hebrew is itself the bidi defect.

R7 — "the forward control is never disabled" — has its own block and recurs at every step: pressing continue with nothing chosen must raise `role="alert"` on *both* unfilled groups, move focus to the first, and stay put. The details step validates a **trimmed** value for blankness and the **raw** value for length (79 characters between two spaces is 81 raw and is refused, because a client validating the trimmed string would send 81 characters the server rejects), and asserts no request was issued — the anti-vacuous half of each boundary test. The terms step renders the policy as text and never as HTML, with an explicit fixture containing `<b>`; on a public anonymous multi-tenant surface any HTML path there is stored XSS reachable by every visitor. It also forbids a scroller and a `tabindex` on the policy: two scroll contexts on a 375px phone is a trap, and a scrollable box would be a tab stop between the text and the consent. Consent survives a back-and-forward because it is keyed on the **version**, which is exactly what `TERMS_STALE` replaces.

The verify step is one screen that *grows*: the phone field never leaves the screen when the code field appears (a mistyped number is the commonest OTP failure and she can only see it if it is still there), the code lives in a single field with `autocomplete="one-time-code"` because several browsers drop a whole code into box 1 of a split widget, and editing the phone collapses the code field while the cooldown — a property of the last send, not of the sub-state — survives. `otpSent` is the field's `aria-describedby` help text rather than a live region, so it is spoken once as focus arrives. Send-side and verify-side 429s are treated differently on purpose: `/otp/send` is 5 per hour, so its exhaustion replaces the form with a contactable dead end rather than saying "try again in a moment", while the verify face is 10 per 5 minutes and leaves everything enabled.

Submit asserts the **whole** `createBooking` object, including `terms_version: 3` and the null dress pair, and that the phone is byte-identical across `/otp/send`, `/otp/verify` and `/bookings` — any divergence answers `PHONE_NOT_VERIFIED` for a correct code. A double tap submits once (React commits `disabled` asynchronously, so the handler's own guard is the layer that catches a fast iOS double tap) while the button keeps its own label and a `role="status"` carries the "submitting" word, because swapping the children re-sizes the button. Two tests protect the verification token: an R13 retry after a 500 re-calls `createBooking` **without** re-minting (the failed create rolled its transaction back), and deleting-and-retyping a digit of the phone must not discard it either — a re-verify would hit a row whose `consumed_at` is set and tell her that her correct code is wrong.

The error-recovery matrix routes each designed failure to the step that owns its recovery, **ahead of** the R13 catch-all: `SLOT_UNAVAILABLE` returns to the slot step with the grid re-read and the taken time gone but the type and date intact (a lost race is not a restart of intent); `TERMS_STALE` returns to terms with the policy re-fetched and consent **reset**; a `NOT_FOUND` on create is probed back to the type picker or the size chips depending on what is actually missing, with the dress-gone case re-issuing the booking exactly once; a rejected body routes to details; and an undiagnosable failure keeps R13. Each of these also has a "the boutique fetch failed too" twin asserting the contact panel degrades to plain copy — `ContactPanel` with every channel absent renders an empty flex box, so the degrade has to be a branch at the call site.

Confirmation is treated as her only record: no `status` string (server-constant on this path, so printing it invites the reader to wonder what the other values are), no success colour (the words and the stated facts are the signal), the name dropped rather than replaced by the generic brand fallback, and a **cold** load rendering a short true statement with no "keep this screen" instruction above a screen holding no appointment.

## Depends On

- [[frontend/apps/storefront/src/routes/BookPage.tsx]] — the subject
- [[frontend/apps/storefront/src/router.tsx]] — `matchRoute` / `usePathname`, used to build the real flow composition
- [[frontend/apps/storefront/src/components/StorefrontLayout.tsx]] · [[frontend/apps/storefront/src/components/booking/SizeChips.tsx]] · [[frontend/apps/storefront/src/components/booking/TypePicker.tsx]]
- [[frontend/packages/ui/src/components/SlotPicker.tsx]] — rendered directly, via the package barrel
- [[frontend/packages/ui/src/tokens.ts]] — `themeTokens`, painted into a stylesheet for the register assertions
- [[frontend/apps/storefront/src/api.ts]] — `ApiError` and the error-message mappers real; seven functions plus `getBoutiqueOnce` mocked
- [[frontend/apps/storefront/src/i18n/index.ts]]
- [[Testing Library]] · [[Vitest]]

## Depended On By

Nothing imports a test file.

## Concepts

- [[Jerusalem Time]] · [[Hebrew RTL Bidi]] · [[IS 5568 Accessibility]]

## Notes

Nothing here fakes the system clock — only the cooldown's timers — so every "now"-dependent assertion is driven by fixture instants instead. The Card-padding test (`.bg-surface.p-6` present, `.p-4` absent) is a `cn()` trap made executable: there is no class-merge, so a caller's `p-4` ships **both** classes and loses on stylesheet order. See [[.planning/specs/storefront-booking-ui.md]] and [[.planning/specs/booking-core.md]].
