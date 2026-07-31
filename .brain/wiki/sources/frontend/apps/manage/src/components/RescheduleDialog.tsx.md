---
tags: [frontend, manage, react, bookings, slots, rtl, i18n, f15]
sources: [frontend/apps/manage/src/components/RescheduleDialog.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/src/components/RescheduleDialog.tsx
blob: 9a98a378320829026ff16dba3fbe8ac245edaade
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/apps/manage/src/components/RescheduleDialog.tsx

**Role.** The modal that moves a confirmed booking to another slot: a 14-day slot fetch filtered in memory by the selected date, fed to the shared `SlotPicker`, pre-selected on the booking's own instant, and submitted as one `api.rescheduleBooking`. It is deliberately its own confirm — there is no second modal over it.

**Module.** [[frontend/apps/manage/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `RescheduleDialog` | component | The modal |
| `RescheduleDialogProps` | interface | `{ booking: OwnerBookingDetail; onClose: () => void; onRescheduled: (detail: OwnerBookingDetail) => void }` |
| `WINDOW_DAYS` | const (module-private) | `14` — one fetch covers the window, matching the storefront's shape and `SlotPicker`'s contract |
| `addDays` | fn (module-private) | Calendar arithmetic on a bare `YYYY-MM-DD`, done in **UTC** |

## Behavior

`addDays` parses `${isoDate}T00:00:00Z` and steps `setUTCDate`, precisely so no DST transition can shift the result by an hour and roll the date. It is not a formatter — its output is an API bound, never something a human reads.

One fetch per `[windowFrom, windowTo, t, attempt]`; the date control then filters `slots` in memory rather than refetching. Moving outside the current window resets `windowFrom`, which triggers a new fetch. Changing the date always clears `value`, because a time chosen on another day is not a time on this one.

**The injected current-time option is the subtle part.** The slot engine drops full slots, so a capacity-1 target the booking itself occupies never comes back in the grid — and "change my mind" must have a way back. When the selected date is the booking's own date and its instant is missing from `times`, it is pushed in and the list re-sorted. The injected option carries the **bare** time and nothing else: `SlotPicker` wraps every label in `<bdi dir="ltr">`, so appending «(המועד הנוכחי)» would place Hebrew inside an LTR isolate. The fact is stated in the sentence above the picker instead.

`min` is `todayJerusalem()` because a past date can never hold a target. There is deliberately **no `max`** — the bookable horizon is a server bound, and this feature mirrors no server bound client-side, so a date past it simply materialises no slots.

The load-failure path owns the only retry control in the feature, and the reason is structural: the day list can decline one because its `DateField` sits *above* its alert and re-selecting the date refetches, whereas here the alert **replaces** `SlotPicker`, which owns the `DateField` — without `attempt` the dialog would hold one disabled submit and a close button and nothing able to clear the error. A submit failure, by contrast, leaves the dialog **open**: closing it would throw away the fetch she needs in order to pick again.

This dialog *is* the confirm step (design P-2). The consequence sentence sits directly above the single submit rather than stacking a second focus trap over a focus trap for a decision already on screen. Focus return to the trigger is handled by the caller, [[frontend/apps/manage/src/components/BookingDetail.tsx]].

## Depends On

- [[frontend/apps/manage/src/api.ts]] — `api.listManageSlots`, `api.rescheduleBooking`, `OwnerSlotRow`
- [[frontend/apps/manage/src/lib/booking.tsx]] — `bookingErrorText`
- [[frontend/apps/manage/src/lib/jerusalem.ts]] — `jerusalemDate`, `jerusalemIsoDate`, `jerusalemTime`, `todayJerusalem`
- [[frontend/packages/ui/src/components/SlotPicker.tsx]] — the date+time grid and its `SlotTime` shape
- [[frontend/packages/ui/src/index.ts]] — `Button`, `Modal`, `Skeleton`, `SlotPicker`
- [[React]] · [[i18next]]

## Depended On By

- [[frontend/apps/manage/src/components/BookingDetail.tsx]]

## Tests

- [[frontend/apps/manage/src/__tests__/BookingDetail.test.tsx]] — exercised through its parent; there is no standalone `RescheduleDialog` suite

## Notes

Submitting the pre-selected instant unchanged is one tap away by design: the server short-circuits it to a no-op 200 with no audit row and no send. The caller compares the response's `starts_at` before announcing anything, so that path stays silent.

Spec and plan: [[.planning/specs/owner-booking-management.md]] · [[.planning/plans/owner-booking-management.md]].
