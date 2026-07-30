// The two things the bookings list, the detail and the reschedule dialog all
// need. It lives here rather than in one of the three components because
// BookingsSection imports BookingDetail and BookingDetail imports
// RescheduleDialog — hanging shared helpers off either end would close that
// chain into a cycle.
import type { ReactNode } from "react";
import type { BadgeVariant } from "@boutique/ui";

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
