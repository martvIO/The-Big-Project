import type { EffortBandRef, TicketStage } from "../api";

/**
 * The client half of a state machine that has NO status column.
 *
 * The server derives a ticket's stage from the RIGHTMOST STAMPED of five
 * nullable timestamps, floored at `intake`. A NULL earlier stamp means "never
 * separately recorded", not "impossible" — forward skips are legal and audited.
 * So the order below is not decoration: it is the only place the console knows
 * what "later" means, and it must agree member-for-member with
 * `TicketStage`'s DECLARATION ORDER on the server, which is what the conditional
 * writes' `AND <every column after the target> IS NULL` predicate is spelled
 * from.
 *
 * In `lib/` so this section and F42's capacity picker share it with no import
 * cycle — `lib/booking.tsx`'s header gives the general reason.
 */
export const STAGE_ORDER: readonly TicketStage[] = [
  "intake",
  "in_progress",
  "qc",
  "ready",
  "delivered",
];

/**
 * The stage word for every member of the union.
 *
 * ⚠ `Record<TicketStage, string>` IS THE POINT, and it is why this is a record
 * rather than a function with a `default`. A sixth stage added to the union
 * without a key here is a COMPILE error; a switch with a fallback is a wrong
 * label that ships silently — the defect `lib/roles.ts` exists to record.
 *
 * The type catches a missing MEMBER; `i18n.test.ts` resolves every value so a
 * member pointing at a key absent from `he.ts` is caught too. The two halves
 * catch different bugs: a column rendering the raw slug `in_progress` and a
 * column rendering the wrong Hebrew word are not the same failure.
 */
export const STAGE_LABEL_KEY: Record<TicketStage, string> = {
  intake: "atelier.stage.intake",
  in_progress: "atelier.stage.inProgress",
  qc: "atelier.stage.qc",
  ready: "atelier.stage.ready",
  delivered: "atelier.stage.delivered",
};

/**
 * The skip `Select`'s options: stages STRICTLY later than the card's current
 * one, in board order, and the empty array at `delivered`.
 *
 * Strictly later, because a backwards skip is a 409 the server refuses and
 * re-entering the current stage is a 200 no-op that would announce a move that
 * did not happen. Offering either would be the console inviting a refusal.
 */
export function laterStages(current: TicketStage): TicketStage[] {
  return STAGE_ORDER.slice(STAGE_ORDER.indexOf(current) + 1);
}

/**
 * The stored minutes read back as a band word — a reverse lookup, because what
 * persists is `effort_minutes` and never the label.
 *
 * The fallback is the visible consequence of that rule: a boutique that
 * re-tuned «חצי יום» from 240 to 300 leaves every ticket estimated under the old
 * mapping matching no live band, and the card says «240 דק׳» rather than
 * silently re-valuing the garment. F41 ships no editor for the mapping (F42
 * owns it), so the fallback is reachable the day after F42 ships and not before.
 *
 * First match wins. The server bounds each band to 1..1440 and forbids no
 * duplicate, so an owner may flatten her two longest bands onto one number.
 */
export function bandLabel(
  minutes: number,
  bands: readonly EffortBandRef[],
  t: (key: string, options?: Record<string, unknown>) => string,
): string {
  const match = bands.find((band) => band.minutes === minutes);
  return match === undefined
    ? t("atelier.effortMinutes", { minutes })
    : t(`atelier.band.${BAND_KEY_SUFFIX[match.band]}`);
}

// The wire's snake_case band keys spelled as the camelCase tail of their i18n
// key. A `Record<EffortBand, string>` for the reason STAGE_LABEL_KEY is one: a
// sixth band without a suffix here is a compile error, not «atelier.band.xl»
// rendering its own key into a card.
const BAND_KEY_SUFFIX: Record<EffortBandRef["band"], string> = {
  thirty_min: "thirtyMin",
  one_hour: "oneHour",
  two_hours: "twoHours",
  half_day: "halfDay",
  full_day: "fullDay",
};
