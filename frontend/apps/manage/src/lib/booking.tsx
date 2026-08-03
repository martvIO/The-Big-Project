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
]);

export function statusBadge(status: string): { variant: BadgeVariant; labelKey: string } {
  // A status outside the four can only come from a backend that grew a fifth
  // one; render the raw value rather than an empty chip.
  return STATUS.get(status) ?? { variant: "neutral", labelKey: status };
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
