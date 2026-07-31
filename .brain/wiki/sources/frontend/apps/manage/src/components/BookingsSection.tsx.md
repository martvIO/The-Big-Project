---
tags: [frontend, manage, react, bookings, rtl, i18n, f15]
sources: [frontend/apps/manage/src/components/BookingsSection.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/src/components/BookingsSection.tsx
blob: 06096d9e30403e1151560bed5cbaf5fa177a031b
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/apps/manage/src/components/BookingsSection.tsx

**Role.** The owner console's bookings screen: one Jerusalem calendar day at a time, fetched by `date`, rendered as a row list, with an in-place swap to [[frontend/apps/manage/src/components/BookingDetail.tsx]] when a row is opened. It is also the state owner for the day — the detail view hands mutated bookings back up through `onBookingChanged`, and this file decides whether that can be patched in place or has to refetch the day.

**Module.** [[frontend/apps/manage/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `BookingsSection` | component | No props. Self-contained day list; reads the signed-in tenant's bookings via `api.listBookings`. |
| `PAGE_LIMIT` | const (module-private) | `50`, mirroring the server's `BOOKING_LIST_DEFAULT_LIMIT`. Deliberately *not* parity-guarded — the server clamps, so a stale client can only ask for less. |

## Behavior

The date filter is **required**: there is no all-bookings view, so a cleared native picker is ignored rather than sent as `date=`. `todayJerusalem()` seeds it, so "today" is the boutique's calendar day and never the device's. The fetch effect keys on `[date, reload]` and guards with a `cancelled` flag; on failure it sets `loadError` and deliberately does **not** set `rows` to `[]`, because an empty array under the alert would stack the empty-day `EmptyState` on top of an outage message.

`onBookingChanged` carries the one non-obvious rule in the file. Every mutation except a reschedule is absorbed by replacing the matching row with the response object — two views rendering the same object cannot disagree, and no refetch flashes the list. A reschedule is different: list *membership*, the server's `total`, and the server's `(starts_at, seat_index)` ordering are all derived from `starts_at`, so a cross-day move patched in place would leave a phantom row on a list that prints no date and an announced count that is silently wrong. The comparison is made against the *previous* row's `starts_at`, and when it differs the `reload` counter is bumped to refetch the whole day.

There is exactly one announced region, a `role="status"` paragraph (`data-testid="bookings-count"`) that carries the loading text, then the count, then blank on an outage — and it is `tabIndex={-1}` so it doubles as the post-mutation focus destination. The count string is interpolated by i18next and then re-split by `isolateLtr` so the numeral lands inside `<bdi dir="ltr">` inside RTL Hebrew. Row content follows the house bidi rule precisely: times get `<bdi dir="ltr">`, the customer name and dress name get a **bare** `<bdi>` (a `dir="ltr"` on a Hebrew name is itself a bidi defect). Attendance is rendered as muted words rather than a second `Badge`, so nothing competes with the status chip.

The whole row is one `<button>` — one affordance, one tab stop — sized by `py-4` + `text-base` rather than a `min-h-[44px]` literal. There are no prev/next controls at all: a Jerusalem day at pilot volume fits fifty rows. The list `Card` is used with its baked-in `p-6` intact, because `cn()` in [[frontend/packages/ui/src/lib/styles.ts]] is a plain join with no class-merge, so a consumer `p-0` would be a same-specificity rule the built stylesheet resolves the wrong way.

Unlike the older console sections, F15's components go through `useTranslation()` — every visible string is a key.

## Depends On

- [[frontend/apps/manage/src/api.ts]] — `api.listBookings`, `errorMessage`, `OwnerBookingRow` / `OwnerBookingDetail` types
- [[frontend/apps/manage/src/lib/booking.tsx]] — `statusBadge`, `isolateLtr`
- [[frontend/apps/manage/src/lib/jerusalem.ts]] — `jerusalemTime`, `todayJerusalem`
- [[frontend/apps/manage/src/components/BookingDetail.tsx]] — the in-panel detail swap
- [[frontend/packages/ui/src/index.ts]] — `Badge`, `Card`, `DateField`, `EmptyState`, `Skeleton`
- [[React]] · [[i18next]] — hooks and `useTranslation`

## Depended On By

- [[frontend/apps/manage/src/App.tsx]] — rendered for the `bookings` nav key
- [[frontend/apps/manage/src/__tests__/BookingsSection.test.tsx]]

## Tests

- [[frontend/apps/manage/src/__tests__/BookingsSection.test.tsx]] — day fetch, the outage path that keeps the list unrendered, the count region, and the reschedule-triggers-refetch branch

## Notes

`apps/manage` has no router, and F15 deliberately did not introduce one for a single view — the detail is an in-component state swap, mirroring the [[frontend/apps/manage/src/components/CatalogSection.tsx]] → [[frontend/apps/manage/src/components/DressEditor.tsx]] shape. A consequence worth knowing: opening a booking is not a URL, so it survives neither reload nor browser back.

Spec and plan: [[.planning/specs/owner-booking-management.md]] · [[.planning/plans/owner-booking-management.md]]. Screen design and copy: [[.planning/design/screens/owner-bookings/owner-bookings.md]] · [[.planning/design/screens/owner-bookings/copy.md]].
