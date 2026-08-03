import type { ReactNode } from "react";
import type { TFunction } from "i18next";
import { isolateLtr } from "./booking";

// F36. How long the bride has been in the room, and it is arithmetic on two ISO
// instants: no timezone is involved and no date library is needed — "elapsed
// time" invites one and it must not (spec D17).
//
// In `lib/` so RoomsPanel's tile and FloorPanel's occupancy line can both read
// it without an import cycle — `lib/roles.ts`'s header gives the general reason,
// and the specific one is that the rule below is subtle enough (server anchor,
// clamp, sub-minute branch) that two copies would be two things to keep true.

// Computed against the ENVELOPE's server_now, so only the delta of a boutique
// tablet's clock is trusted and never its absolute value, and it is frozen
// exactly when the panel freezes: nothing advances it on an interval. A paused
// panel says «מושהה · עודכן 14:07», and a minute counter still climbing beside a
// stopped stamp would be the panel disagreeing with itself.
//
// Clamped at zero because `created_at` comes from the DATABASE clock while
// `server_now` comes from the service's Python one, so assignedAt > serverNow is
// representable and a raw subtraction can go negative.
export function elapsedMinutes(serverNow: string, assignedAt: string): number {
  return Math.max(0, Math.floor((Date.parse(serverNow) - Date.parse(assignedAt)) / 60_000));
}

// «כבר 42 דק'», or «זה עתה» for the first minute of every fitting in the
// boutique — «כבר 0 דק'» is bad Hebrew and the clamp above makes it reachable.
// No hours branch and no plural: «דק'» is invariant in Hebrew, so one key covers
// 1 and 95, and this must not become the console's first i18next plural rule.
export function elapsedLine(t: TFunction, serverNow: string, assignedAt: string): ReactNode {
  const minutes = elapsedMinutes(serverNow, assignedAt);
  if (minutes < 1) {
    return t("rooms.elapsedJustNow");
  }
  return isolateLtr(t("rooms.elapsed", { minutes }), String(minutes));
}
