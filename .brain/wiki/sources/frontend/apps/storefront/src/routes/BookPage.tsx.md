---
tags: [frontend, storefront, route, react, booking, otp, stepper, accessibility]
sources: [frontend/apps/storefront/src/routes/BookPage.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/routes/BookPage.tsx
blob: 85568877e4be501e5bed84bbb680621ca222fc41
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/storefront/src/routes/BookPage.tsx

**Role.** The entire `/book/*` flow in one component: shell, stepper, and all five steps (`slot` → `details` → `terms` → `verify` → `confirm`), plus every degrade and every routed recovery from a failed submit. It is one file on purpose — the flow's state (chosen type, chosen instant, accepted terms version, and above all the OTP **verification token**) lives in this component's `useState` and nowhere else, so it survives step navigation only because the Router re-renders the same element in the same position.

**Module.** [[frontend/apps/storefront/src/routes/_index]] · **Layer.** api

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `BookPage` | component | `{step, dressId?}` — the step comes from `matchRoute`, the dress id from an optional path segment |
| `BookPageProps` | interface | |
| `Stepper` · `PhoneOnly` · `ForwardRow` | components (module-private) | the inert four-item progress list; the "one sentence then a phone number" exit shape; the never-disabled forward button |

## Behavior

**OTP is last, and that ordering is the flow's central constraint.** The verification token is single-use with a 600-second TTL, so putting the code step before the policy step would let it expire mid-consent. The token is held in memory only — device storage is banned outright here, and the TTL could not survive a reload anyway. The `confirm` step exists precisely because there is no public read-a-booking-by-id endpoint: reload it and the cold branch (`booking.confirmCold`) can only say what it knows and offer the phone.

**Entry is three parallel reads plus one detached one.** `api.getTerms()`, `api.listAppointmentTypes()` and `api.listSlots()` go into a single `Promise.all`, because a missing published policy is an *entry-level* decision (D5) and discovering it at the terms step would let her fill two screens first. The terms 404 is branched at this call site, before the shared `errorMessageKey` helper sees it — `NOT_FOUND` means something else on every other call in the flow, so no shared mapper could discriminate. The bound dress read is a **separate** effect and never joins the `Promise.all`: the name and notes fields must stay typeable while it is in flight, and a failed decoration must never stop a bride booking, so both a 404 and a 5xx collapse to `dressGone` with no alert and no retry.

**The guard effect is a bounce, and it checks all three preconditions.** A later step entered without slot, type *or* accepted version has nothing to book, so it `navigate(..., { replace: true })` back — `replace` and never push, because pushing puts the step she was bounced off back under the Back button and bounces forever. `confirm` is exempt (the booking is written and cannot be re-read), and `verify` with a written booking goes **forward** to `confirm`. Checking only the slot was the earlier defect: browser-forward into `/book/verify` with a nulled type or an unticked consent hit `submit()`'s silent `=== null` return — no spinner, no alert, no navigation — after she had already spent an SMS (WCAG 3.3.1).

**Every submit failure has a named destination.** `PHONE_NOT_VERIFIED` collapses to the phone sub-state, keeping the consent (a consent is to a *version*, and the version did not change). `SLOT_UNAVAILABLE` refetches slots and returns to step one with `returnReason="slot"`, keeping the type and the date — a lost race is not a restart of intent. `TERMS_STALE` refetches the policy, which unchecks consent **by construction** because `accepted` is `acceptedVersion === terms.version`; a policy deleted outright mid-session has no flow left to return to and lands on D5's phone-only entry. `NOT_FOUND` is one code with three causes (withdrawn type, archived dress, deleted size variant) and no wire discriminator, so `probeNotFound` re-reads types and the dress *while the submit button is still loading* and routes to whichever step owns the fix — except an archived dress, which drops the binding and **reissues the booking without it** (R20) rather than costing three navigations against a partly-spent token. `VALIDATION_ERROR` returns to `details` because a 400 is deterministic and "try again" would burn the booking budget on every press. Every recovery **keeps the verification token**: `create_booking` runs in one transaction, so a claim that loses a race rolls its own token burn back, and re-verifying would spend one of five hourly sends to re-prove what the server never un-proved.

**Two client-side budgets mirror server behaviour.** `OTP_SEND_BUDGET = 5` mirrors `otp_send_max_per_phone_window` in [[backend/app/core/config.py]]; the server answers a spent personal budget with the same silent 204 as a real send (deliberately, so the endpoint cannot be an oracle for "is this number mid-booking here"), which means past that count every press would be a "code sent" that is false. It is counted per *session*, not per number — the file's own `ponytail:` note says a bride who mistypes four numbers is over-counted and the only cost is that her sixth send offers the phone instead. `OTP_RESEND_COOLDOWN_MS = 60_000` sits past the p95 of Israeli SMS delivery while four resends still fit inside one code's 300-second life, and renders as a **label swap**, never a ticking value.

**Time is Jerusalem's, always.** Four `Intl.DateTimeFormat` instances pinned to `JERusalem` split slot instants into a boutique-calendar date and time (`en-CA`/`en-GB` for parsing shape) and render the confirmation in `he-IL`. Date bounds for the picker come from the instants the server returned, never the browser clock — a bride abroad, or a device with a wrong TZ, must not be offered a date the server will reject.

**Focus and announcements are hand-driven.** `pendingFocus` is a ref consumed in an unkeyed layout effect, because all three verify-step destinations (the code field, the phone field after a collapse, the dead-end block) are mounted *by* the state change that decides to focus them. Inputs are `select()`ed rather than cleared — clearing destroys the evidence of what she typed, and on `OTP_EXPIRED` the digits were probably right. There is exactly one authored polite region, written by two discrete events (cooldown ending, submit starting) and emptied after a failure so a second attempt announces again.

Two register rules run throughout: failures that are *hers* (a mistyped phone) are `text-danger`; failures that are the boutique's or the network's (a spent budget, a republished policy, a vanished dress) are `text-ink-muted` or `text-warning-text`, never danger. And the terms text is rendered as a plain React text child — **no `dangerouslySetInnerHTML`, no markdown renderer, no sanitise-then-inject** — because this is a public, anonymous, multi-tenant surface and any HTML path is stored XSS for every visitor.

## Depends On

- [[frontend/apps/storefront/src/api.ts]] — `api.getTerms/listAppointmentTypes/listSlots/getDress/sendOtp/verifyOtp/createBooking`, `ApiError`, `errorMessageKey`, `errorMessageOr`
- [[frontend/apps/storefront/src/validation.ts]] — `normalizePhone` (called once, and this exact string rides all three calls), `validateName`, `validateNotes`, `validatePhone`, the two length caps
- [[frontend/apps/storefront/src/router.tsx]] — `Link`, `navigate`, `BookStep`
- [[frontend/apps/storefront/src/components/booking/TypePicker.tsx]] · [[frontend/apps/storefront/src/components/booking/SizeChips.tsx]] · [[frontend/apps/storefront/src/components/ContactCard.tsx]] · [[frontend/apps/storefront/src/components/StorefrontLayout.tsx]] (`useBoutique`)
- [[frontend/packages/ui/src/components/SlotPicker.tsx]] · [[frontend/packages/ui/src/components/Input.tsx]] · [[frontend/packages/ui/src/components/TextArea.tsx]] · [[frontend/packages/ui/src/components/Checkbox.tsx]] · [[frontend/packages/ui/src/components/Card.tsx]] · [[frontend/packages/ui/src/components/Button.tsx]] · [[frontend/packages/ui/src/components/A11y.tsx]] (`VisuallyHidden`) · [[frontend/packages/ui/src/components/Skeleton.tsx]]
- [[frontend/packages/ui/src/lib/hours.ts]] — `JERusalem` (the `"Asia/Jerusalem"` constant, re-exported through the package index)
- [[React]] · [[i18next]] · [[Intl API]]

## Depended On By

- [[frontend/apps/storefront/src/router.tsx]] — the `/book/{step}` and `/book/{step}/{dressId}` routes
- [[frontend/apps/storefront/src/components/BookingCTAButton.tsx]] — the only link into the flow

## Concepts

- [[Jerusalem Time]]
- [[Accessibility Compliance]]
- [[Accessibility Compliance]]
- [[RTL And Bidi Isolation]]

## Tests

- [[frontend/apps/storefront/src/__tests__/BookPage.test.tsx]]
- [[frontend/apps/storefront/src/__tests__/router.test.tsx]] — the step/dress-id path shapes
- [[frontend/e2e/storefront.spec.ts]]

## Notes

Server side of this flow: [[backend/app/booking/router.py]] and [[backend/app/booking/service.py]]. Specs: [[.planning/specs/storefront-booking-ui.md]], [[.planning/specs/booking-core.md]]; design and copy in [[.planning/design/screens/booking/booking.md]] and [[.planning/design/screens/booking/copy.md]]. `hasBookingBar()` is deliberately **false** for `/book/*` — the `pb-16` on `pageClass` is what clears the fixed A11yMenu trigger here.
