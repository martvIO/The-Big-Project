---
tags: [frontend, manage, react, bookings, rtl, accessibility, focus-management, f15]
sources: [frontend/apps/manage/src/components/BookingDetail.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/src/components/BookingDetail.tsx
blob: 626db55e69589b9be68ee830f0b51de0fc45452b
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/apps/manage/src/components/BookingDetail.tsx

**Role.** The single-booking screen and the only place in the console where a booking's state machine is driven: it renders the customer/appointment/notes facts, then exposes exactly those transition controls the D3 status graph currently allows — cancel, reschedule, resend link, no-show, complete, reopen — each of which is **absent rather than disabled** when forbidden. It also owns the owner-attested phone correction and every focus-restore rule that keeps a transition from dropping focus to `<body>`.

**Module.** [[frontend/apps/manage/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `BookingDetail` | component | The screen. Props below. |
| `BookingDetailProps` | interface | `{ bookingId: string; onBack: () => void; onBookingChanged: (detail: OwnerBookingDetail) => void }` |
| `Fact` | component (module-private) | Label/value pair; stacked ≤767, `md:grid-cols-[max-content_1fr]` above — the one breakpoint branch in the feature |
| `Instant` | component (module-private) | `d.m.yyyy · HH:MM`, both Jerusalem, one `<bdi dir="ltr">` per numeric run |

## Behavior

Load is a single `api.getBooking(bookingId)` keyed on `[bookingId, t]` with a `cancelled` guard. A `NOT_FOUND` is rendered as the same Hebrew "not found" text a cross-tenant id produces under RLS — the two are indistinguishable by design, so they must read identically.

**Which controls exist is derived from status plus a clock split**, not from a permission: `future` is `starts_at > Date.now()`, and from it `liveConfirmed` / `pastConfirmed` / `isNoShow` / `isCompleted` / `isCancelled` gate the buttons. The clock split is a fact about the appointment; the server stays the authority and a control that races it still answers 409. `cancelled` is terminal — the actions card degrades to one muted sentence, because owner-created bookings are out of scope and the honest remedy is a storefront rebook. Rendering a button that is guaranteed to 409 is treated as a trap, and a disabled button with no explanation as worse.

Every mutation runs through `runAction`, which sets a `pending` key, clears the previous error and cue, awaits a call that always answers the same `OwnerBookingDetail`, then re-renders from that response and forwards it to `onBookingChanged`. `busy` (`pending !== null`) disables every action button. `submitPhone` is separate only because a 400 belongs beside the field: the server's message is put into the `Input`'s own `error` slot, and any non-400 falls back to the shared alert.

**Five focus effects, and the reason they exist is the interesting part.** The heading is focused on `bookingId` change so the owner hears where she landed. `cue` focuses the status region. `actionError` focuses the alert — this one was the missing half: every action button carries `disabled={busy}`, which blurs it the instant it is tapped, and the confirm `Modal`s unmount in the same commit that disables their trigger, so the modal-restore effects call `.focus()` on a disabled element (a no-op) and on a *failure* focus was left on `<body>`, restarting the next Tab at the skip link (WCAG 2.4.3). It is keyed on the error rather than on `pending` so it runs on the render that carries the answer. `phoneError` focuses the phone input. Three `was*Open` refs restore focus to each modal's trigger on close, because native `<dialog>` returns focus to whatever had it — which after a re-render may be nothing.

**Bidi is applied per value, not per block.** Phone, seat index, dates and times are `<bdi dir="ltr">`. Customer name, appointment type name, dress name, `dress_size` and the notes body take a **bare** `<bdi>`: `dress_size` snapshots owner-typed `dress_variants.size_label` with no numeric constraint, so «מידה 36» would render its digits on the wrong side under `dir="ltr"`, while `dir=auto` still resolves a plain `"36"` as LTR. Interpolated strings (terms version, the phone echoed in the confirm modal) go through `isolateLtr` so only the value is isolated.

**Notes render as text and only text** — no `dangerouslySetInnerHTML`, no markdown pass, no linkification; React's default escaping is the whole policy, with `whitespace-pre-wrap` for shape. The heading is `t("booking.detailTitle")` and never the bride's name, because a name in the announced landmark heading is PII. `manage_link_issued` renders as words rather than a chip — one `Badge` per region, and status owns it; the link hash itself never reaches the wire. `size="md"` is used on every `Button` deliberately: `size="sm"`'s `min-h-9` is under the 44px floor. The cancel control is a solid `variant="danger"` rather than `ghost` + `className="text-danger"`, because that override would lose the cascade under the no-merge `cn()`.

The reschedule cue is announced only when `next.starts_at !== detail.starts_at` — the dialog pre-selects the booking's own time, so re-submitting it unchanged short-circuits server-side to a no-op 200 with no audit row and no send, and announcing «המועד עודכן» there would state a state change that did not happen. The comparison is made against the **response**, not against what the dialog asked for.

## Depends On

- [[frontend/apps/manage/src/api.ts]] — `api.getBooking`, `cancelBooking`, `confirmBooking`, `completeBooking`, `noShowBooking`, `resendBookingLink`, `correctBookingPhone`; `ApiError`, `errorMessage`
- [[frontend/apps/manage/src/lib/booking.tsx]] — `statusBadge`, `isolateLtr`, `bookingErrorText`
- [[frontend/apps/manage/src/lib/jerusalem.ts]] — `jerusalemDate`, `jerusalemTime`
- [[frontend/apps/manage/src/components/RescheduleDialog.tsx]] — the reschedule surface
- [[frontend/packages/ui/src/index.ts]] — `Badge`, `Button`, `Card`, `Input`, `Modal`, `Skeleton`
- [[React]] · [[i18next]]

## Depended On By

- [[frontend/apps/manage/src/components/BookingsSection.tsx]]
- [[frontend/apps/manage/src/__tests__/BookingDetail.test.tsx]]

## Tests

- [[frontend/apps/manage/src/__tests__/BookingDetail.test.tsx]] — the largest suite in the app (~60 cases): per-status control presence/absence, focus restoration on success *and* failure, the phone confirm modal, notes-as-text, and the no-op reschedule that must not announce

## Notes

The file's own comments cite `booking-core.md:173` and a line range in `DressEditor.tsx` — both are line citations that will rot; the underlying rules are the notes-are-text rule in [[.planning/plans/booking-core.md]] and the modal focus-restore pattern in [[frontend/apps/manage/src/components/DressEditor.tsx]].

Spec and plan: [[.planning/specs/owner-booking-management.md]] · [[.planning/plans/owner-booking-management.md]]. Copy deck: [[.planning/design/screens/owner-bookings/copy.md]].
