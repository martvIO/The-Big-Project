// The two things the bookings list, the detail and the reschedule dialog all
// need. It lives here rather than in one of the three components because
// BookingsSection imports BookingDetail and BookingDetail imports
// RescheduleDialog — hanging shared helpers off either end would close that
// chain into a cycle.
import type { ReactNode } from "react";
import type { BadgeVariant } from "@boutique/ui";
import { ApiError, errorMessage } from "../api";

// Status is NEVER signalled by colour alone: the Hebrew word inside the Badge
// carries the state and the variant is redundant reinforcement, so the mapping
// survives greyscale, colour blindness and forced-colours mode. `danger` is
// deliberately absent — it is reserved for something the owner must fix, and a
// cancelled booking is a settled fact.
const STATUS = new Map<string, { variant: BadgeVariant; labelKey: string }>([
  ["confirmed", { variant: "success", labelKey: "booking.statusConfirmed" }],
  ["completed", { variant: "neutral", labelKey: "booking.statusCompleted" }],
  ["no_show", { variant: "warning", labelKey: "booking.statusNoShow" }],
  ["cancelled", { variant: "muted", labelKey: "booking.statusCancelled" }],
  // F19 D14. The fifth status, and the reason the fallback below was a latent
  // bug rather than a safety net: it rendered the literal LTR "pending_payment"
  // inside a Hebrew RTL console the day the backend grew it. `warning` because
  // the hold is in flight — not `danger`, which stays reserved for something the
  // owner must fix, and a checkout she cannot hurry is not that.
  ["pending_payment", { variant: "warning", labelKey: "booking.statusPendingPayment" }],
]);

export function statusBadge(status: string): { variant: BadgeVariant; labelKey: string } {
  // Now genuinely unreachable — `bookings.status` is pinned to these five by
  // 0008's CHECK — and kept as a chip with Hebrew in it rather than a raw value.
  return STATUS.get(status) ?? { variant: "neutral", labelKey: "booking.statusOther" };
}

// F19 D18: the ONLY owner-facing payment surface in the product. All seven
// values of 0012's CHECK are mapped, not just the four F19 writes — mapping the
// writers-of-today is exactly how `statusBadge` acquired its raw-value hole.
const PAYMENT = new Map<string, { variant: BadgeVariant; labelKey: string }>([
  ["pending", { variant: "warning", labelKey: "booking.paymentPending" }],
  ["paid", { variant: "success", labelKey: "booking.paymentPaid" }],
  // MD4: a `failed` row means the appointment was booked and no deposit was
  // taken, which is real money missing — the one payment state that is the
  // owner's to act on.
  ["failed", { variant: "danger", labelKey: "booking.paymentFailed" }],
  ["expired", { variant: "muted", labelKey: "booking.paymentExpired" }],
  ["refund_due", { variant: "warning", labelKey: "booking.paymentRefundDue" }],
  ["refunded", { variant: "neutral", labelKey: "booking.paymentRefunded" }],
  ["forfeited", { variant: "neutral", labelKey: "booking.paymentForfeited" }],
]);

export function paymentBadge(status: string): { variant: BadgeVariant; labelKey: string } {
  return PAYMENT.get(status) ?? { variant: "neutral", labelKey: "booking.paymentOther" };
}

// D18's action-needed marker: the two combinations that need a human, and
// nothing else. Both are invisible in `status` alone, which is why D18 puts
// `payment_status` on the row the owner already opens every morning.
export function paymentActionKey(status: string, paymentStatus: string | null): string | null {
  if (paymentStatus === "paid" && status === "cancelled") {
    // Her money is held and her appointment is gone. MD1's reschedule is the
    // button behind this sentence.
    return "booking.paymentActionCancelledPaid";
  }
  if (paymentStatus === "failed" && status === "confirmed") {
    // MD4: the provider was unreachable at checkout, so the booking was taken
    // without a deposit and the boutique's forfeit policy has nothing behind it.
    return "booking.paymentActionNoDeposit";
  }
  return null;
}

// i18next interpolates into a flat string, so a {{count}} or {{phone}} run lands
// as bare text inside an RTL paragraph. Split the interpolated result around the
// value and isolate that one run. Unambiguous by construction: the Hebrew around
// these two placeholders carries no digits (copy.md §2, §10).
export function isolateLtr(text: string, value: string): ReactNode {
  const at = value === "" ? -1 : text.indexOf(value);
  if (at < 0) {
    return text;
  }
  return (
    <>
      {text.slice(0, at)}
      <bdi dir="ltr">{value}</bdi>
      {text.slice(at + value.length)}
    </>
  );
}

// The same split for a value that is NOT a numeric run — a person's name.
//
// ⚠ `isolateLtr` is WRONG for a name and this is not a nicety: it emits
// `<bdi dir="ltr">`, and forcing LTR on «נועה לוי» reverses the visual order of
// its Hebrew words. It is a bidi defect that LOOKS DELIBERATE, which is the kind
// nobody files. A bare `<bdi>` isolates the run without asserting a direction,
// so the browser resolves each name's own — which is exactly what is wanted when
// the value may be Hebrew, Arabic or Latin and the surrounding paragraph is RTL.
//
// F57's design deck raises this as F-11. Note what it does NOT cover: an
// `aria-label` takes no markup, so a name interpolated into one needs no
// treatment at all — there is nothing rendered to reorder.
export function isolateBidi(text: string, value: string): ReactNode {
  const at = value === "" ? -1 : text.indexOf(value);
  if (at < 0) {
    return text;
  }
  return (
    <>
      {text.slice(0, at)}
      <bdi>{value}</bdi>
      {text.slice(at + value.length)}
    </>
  );
}

// main.py's *_BODY literals are English, and this console is Hebrew-only —
// IS 5568 makes the language of an error message operationally load-bearing for
// the owner who has to act on it. These four codes are the ones F15 owns, and
// they are pinned by SPEC_ERROR_CODES in test_booking_owner_api.py, so the map
// cannot silently drift. This is NOT a validator and it mirrors no server bound
// (D20 stands: no phone normalizer, no pattern, no length rule).
//
// Every other code falls through to the server's own text — VALIDATION_ERROR
// included, because its message is computed per field and cannot be reproduced
// client-side.
const OWNED_ERROR_CODES = new Set([
  "BOOKING_TRANSITION_INVALID",
  "SLOT_UNAVAILABLE",
  "CUSTOMER_ALREADY_BOOKED",
  "TOO_MANY_ATTEMPTS",
]);

export function bookingErrorText(error: unknown, t: (key: string) => string): string {
  if (error instanceof ApiError && OWNED_ERROR_CODES.has(error.code)) {
    return t(`booking.error.${error.code}`);
  }
  return errorMessage(error);
}
