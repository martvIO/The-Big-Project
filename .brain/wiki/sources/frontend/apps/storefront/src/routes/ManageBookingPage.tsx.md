---
tags: [frontend, storefront, route, react, booking, tokenized-link, cancellation]
sources: [frontend/apps/storefront/src/routes/ManageBookingPage.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/routes/ManageBookingPage.tsx
blob: f18fed2f0a77708fff95fce9e61ca1539fe49e4c
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/storefront/src/routes/ManageBookingPage.tsx

**Role.** `/b/{token}` (F16) — the page behind the tokenized manage link that rides the confirmation and reminder SMS. It is the confirmation screen's **sibling, not a flow**: she arrived from a text message, possibly weeks later, so there is no stepper, no progress and no back-to-step-one. Facts first, actions second, boutique contact last.

**Module.** [[frontend/apps/storefront/src/routes/_index]] · **Layer.** api

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `ManageBookingPage` | component | `{token}` — the opaque segment; the router deliberately does not validate it |
| `View` | type (module-private) | `loading` · `loaded` · `invalid` · `failed` |
| `Facts` · `Heading` · `PolicyLine` · `fallbackBoutique` | module-private | |

## Behavior

**Six visible states, not four:** the `View` union covers loading / invalid-link / load-failed / loaded, and the loaded branch splits again into *cancelled*, *past* and *actionable* (`actionable = !cancelled && !past`), with attendance-confirmed a sub-state of actionable. `past` is computed from `starts_at <= Date.now()`, which is the one wall-clock read on the page; everything *displayed* goes through Jerusalem-pinned `Intl` formatters, because a bride whose phone clock the airline changed must still read the boutique's time.

**The two-step cancel is the reason this page exists in this shape.** The secondary "cancel" button calls no API — it sets `revealed`, which mounts an inline `Card` carrying the question, her accepted policy's refund window and the consequence line, and only *that* Card's danger button hits `api.cancelBooking`. One tap must never cancel a wedding-dress appointment. It is an inline reveal rather than a `Modal`: it keeps the whole decision on one surface and spares the focus-trap machinery for a two-button choice. Cancel **stays available after attendance is confirmed** (design P3) — confirming is a courtesy signal, not a lock-in.

**Focus is deferred through a ref, in every direction.** Each successful action removes the control that was just clicked, so `moveFocusTo` names the destination and an unkeyed layout effect performs the move after commit. The "keep it" button is the subtle one: the cancel trigger is *unmounted* while the reveal is open, so focusing it inline would silently drop focus to `<body>`. The reveal's own destination is the **question paragraph**, so a screen reader hears what is being asked rather than an anonymous container.

**State is derived from the server, never from what a tap hoped for.** `busy` records *which* action is in flight rather than merely whether one is, because both controls can be on screen at once and a boolean spun the wrong button. A 409 on confirm or cancel does not guess — it clears the reveal and re-drives `load()`, so `BOOKING_ALREADY_STARTED` lands on the past view and `BOOKING_CANCELLED` on the cancelled one. `BOOKING_LINK_INVALID` is branched on the **code at this call site** rather than through `errorMessageKey`, because an invalid link is a page *state* with its own copy, not one more sentence in the shared error map.

**Contact resolution is layered (F-M2 as corrected at the design gate):** `useBoutique()` is primary, and `fallbackBoutique()` reshapes the lookup payload's four boutique fields into a `BoutiqueResponse` only for the states that *have* a payload. The invalid-link and load-failed states are lookup **failures** whose responses carry the house error shape and no boutique data under any circumstance, so they render the contact block only if the layout fetch succeeded. Nothing renders while the layout read is in flight — flashing a fallback at a panel about to arrive is worse than the small delay. The shim sets `instagram`, `hours` and `exceptions` to empty deliberately: the manage subset carries exactly what the contact block needs and nothing a later `profile` key could smuggle in.

`policy` is nullable and the page **says nothing about a number it cannot justify** — the window line simply disappears if that terms-version row has gone. Pre-E4 both sides of the refund window render the same `manage.cancelConsequenceFree` sentence (design P1): every F16-era booking is deposit-free, and a forfeit warning about a deposit never taken would be a lie; the split ships as structure and E4 swaps the out-of-window key.

Labels are **reused verbatim** from the approved confirmation screen (`booking.confirmWhen`, `booking.confirmWhat`, `booking.confirmDress`) so the two screens showing the same appointment never drift. The facts card is kept in the cancelled state too — she may need the date to rebook.

## Depends On

- [[frontend/apps/storefront/src/api.ts]] — `api.lookupBooking/confirmAttendance/cancelBooking`, `ApiError`, `ManageBookingResponse`, `BoutiqueResponse`
- [[frontend/apps/storefront/src/components/StorefrontLayout.tsx]] — `useBoutique`
- [[frontend/apps/storefront/src/components/ContactCard.tsx]]
- [[frontend/packages/ui/src/components/Button.tsx]] (`Button`, `ButtonLink`) · [[frontend/packages/ui/src/components/Card.tsx]] · [[frontend/packages/ui/src/components/Skeleton.tsx]] · [[frontend/packages/ui/src/components/A11y.tsx]] (`VisuallyHidden`)
- [[frontend/packages/ui/src/lib/hours.ts]] — `JERusalem`
- [[React]] · [[i18next]] · [[Intl API]]

## Depended On By

- [[frontend/apps/storefront/src/router.tsx]] — the `/b/{token}` route, matched **before** the catalog fallthrough so a bad token reaches this page's invalid-link state instead of being swallowed into the collection

## Concepts

- [[Jerusalem Time]]
- [[Accessibility Compliance]]
- [[RTL And Bidi Isolation]]

## Tests

- [[frontend/apps/storefront/src/__tests__/ManageBookingPage.test.tsx]]
- [[frontend/apps/storefront/src/__tests__/router.test.tsx]] — the `/b/` match ordering

## Notes

Server side: [[backend/app/booking/manage.py]]. Spec [[.planning/specs/owner-booking-management.md]]; design and copy in [[.planning/design/screens/manage-booking/manage-booking.md]] and [[.planning/design/screens/manage-booking/copy.md]]. The `/b/` prefix is short on purpose (spec D7): the URL rides inside a UCS-2 Hebrew SMS where every character is segment budget.
