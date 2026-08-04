import type { SeamstressRef } from "../api";

/**
 * The capacity folds — pure functions of the wire, shared by the seamstress
 * panel, the assign picker and the assign cue.
 *
 * In `lib/` for `lib/stages.ts`'s reason: three surfaces in two components read
 * them, and a helper living in either component is an import cycle waiting for
 * the second caller. It is also the one part of this feature F40 replaces
 * wholesale when the roster projection lands.
 *
 * ⚠ EVERY FOLD BRANCHES ON `weekly_capacity_hours === null`, NEVER ON
 * FALSINESS. `null` and `0` are opposite states with opposite renderings:
 *
 *   null → nobody has told this product how much she can take. NO BAR AT ALL,
 *          no colour, no overload word, and she sorts in the middle group.
 *   0    → she is configured as unavailable this week. A TRACK RENDERS, and
 *          360 minutes against it is a full red bar, «עומס יתר», and the LAST
 *          place in the picker.
 *
 * `if (!row.weekly_capacity_hours) return null` collapses them and renders the
 * away-and-drowning seamstress as «לא הוגדרה קיבולת» — the alarm silently
 * replaced by the calmest string in the feature.
 */

/**
 * ⚠ THE ONLY `* 60` IN THIS FEATURE, ON EITHER SIDE OF THE WIRE.
 *
 * The database stores hours (`weekly_capacity_hours`) and minutes
 * (`effort_minutes`) and the server never multiplies the two — the load
 * aggregate returns pure minutes, the capacity resolves to pure hours, and both
 * travel under their own names. The conversion happens here, once, so a
 * dimensional mistake is one grep rather than a number that is wrong by 60×
 * and plausible on both sides.
 */
export function capacityMinutes(hours: number | null): number | null {
  return hours === null ? null : hours * 60;
}

/** Her headroom in minutes, or null when no capacity is resolved. Negative when over. */
export function remainingMinutes(row: SeamstressRef): number | null {
  const capacity = capacityMinutes(row.weekly_capacity_hours);
  return capacity === null ? null : capacity - row.due_soon_minutes;
}

/**
 * The bar's width, 0–100, or null when there is no denominator and therefore no
 * bar to draw.
 *
 * ⚠ THE NUMERATOR IS `due_soon_minutes` AND NOT `assigned_minutes`, and that is
 * the whole feature. Dividing her entire undelivered backlog — a STOCK — by one
 * week of capacity — a RATE — is not a utilisation of anything: a 40 h/week
 * seamstress holding six weeks of evenly-spread forward work renders at 600 %,
 * clamped, red, on day one, in any boutique with a book. A bar that is red in
 * the steady state is a bar nobody reads. The backlog rides in the row's
 * sentence instead, in words, so nothing is hidden.
 *
 * ⚠ THE ZERO-CAPACITY BRANCH CANNOT BE LEFT TO THE BAR'S isFinite GUARD. A raw
 * `due_soon / 0 * 100` is Infinity, and the shipped guard answers 0 for a
 * non-finite input — which would draw an EMPTY track for a seamstress who is
 * unavailable and holding six hours, the exact opposite of the designed
 * rendering. The ratio is undefined there; the fact is not.
 *
 * The clamp is here AND in the widget: this one keeps the number a percentage
 * for every reader, and the widget's is the shipped `Bar`'s own line, copied
 * verbatim rather than re-made.
 */
export function loadRatio(row: SeamstressRef): number | null {
  const capacity = capacityMinutes(row.weekly_capacity_hours);
  if (capacity === null) {
    return null;
  }
  if (capacity === 0) {
    return row.due_soon_minutes > 0 ? 100 : 0;
  }
  const ratio = (row.due_soon_minutes / capacity) * 100;
  if (!Number.isFinite(ratio)) {
    return 0;
  }
  return Math.min(Math.max(ratio, 0), 100);
}

/**
 * ⚠ THE ONLY COMPARISON IN THE FEATURE, AND IT HAS THREE CONSUMERS: the bar's
 * colour, the row's «עומס יתר» and — through `wouldOverload` — the assign cue.
 *
 * That is what makes "overload is never colour-only" a STRUCTURAL property
 * rather than a rule somebody has to remember: a build in which the bar is red
 * and the word is missing does not exist, because there is no second boolean to
 * drift.
 *
 * Strictly `>`: exactly a week of work in a week is full and calm, and the
 * colour flips one minute later with no width change at all.
 */
export function overloaded(row: SeamstressRef): boolean {
  const capacity = capacityMinutes(row.weekly_capacity_hours);
  return capacity !== null && row.due_soon_minutes > capacity;
}

/**
 * The minutes THIS ticket adds to `due_soon_minutes` — its effort inside the
 * board's horizon, and ZERO outside it.
 *
 * ⚠ THE SUM THE BAR RENDERS IS FILTERED, SO THE CUE'S HYPOTHETICAL MUST BE.
 * `due_soon_minutes` is `SUM(effort_minutes) FILTER (WHERE due_date <=
 * horizon)`, and `due_soon_through` IS that horizon on the wire. Adding a
 * ticket due after it predicts a number the server will never compute: the cue
 * announces «עומס יתר», the next tick leaves her sum untouched, and the bar
 * (gold, 91.7 %) and the row's sentence (no «עומס יתר») both say she is fine —
 * with no colleague and no race, and D17 forbids the poll from retracting it.
 * Assignment normally happens at intake, when the due date is weeks out, so
 * that is the COMMON case and not the exotic one.
 *
 * ⚠ A LEXICOGRAPHIC COMPARE AND NO `Date`. Both sides are the server's plain
 * `YYYY-MM-DD`, which sorts as a string, so this needs no `lib/jerusalem`
 * arithmetic and cannot read the device clock. An OVERDUE ticket
 * (`due_date < today <= horizon`) counts, exactly as the SQL counts it.
 */
export function loadMinutes(
  ticket: { effort_minutes: number; due_date: string },
  dueSoonThrough: string,
): number {
  return ticket.due_date <= dueSoonThrough ? ticket.effort_minutes : 0;
}

/**
 * "Would THIS ticket push her over?" — the hypothetical `overloaded(row)` cannot
 * answer because it takes a row.
 *
 * ⚠ `extraMinutes` MUST ALREADY BE FILTERED — it is added to a filtered sum, so
 * it is `loadMinutes(ticket, board.due_soon_through)` and never a raw
 * `effort_minutes`. Both live here so the filter and the comparison cannot
 * drift apart at the one call site.
 *
 * ⚠ NO ARITHMETIC AND NO `60` HERE OR AT ITS CALL SITE. Hand-rolled at the
 * assign handler, this is where drift is most expensive: a `>=` on one side, or
 * one of the two forgetting the null guard and computing `null * 60 = 0` in JS,
 * so EVERY assign to an unconfigured seamstress announces «עומס יתר» — on the
 * one channel a screen-reader user has for this fact, while the sighted surface
 * stays correct and axe passes.
 */
export function wouldOverload(row: SeamstressRef, extraMinutes: number): boolean {
  return overloaded({ ...row, due_soon_minutes: row.due_soon_minutes + extraMinutes });
}

/**
 * Minutes to hours for display, one decimal at most.
 *
 * ⚠ IT ROUNDS UP, AND THE DIRECTION IS LOAD-BEARING. `overloaded` compares raw
 * minutes, so with `Math.round` a 721-minute load against a 12 h capacity
 * renders «12 שעות … מתוך 12 · עומס יתר» — displayed numbers saying EQUAL beside
 * a word saying OVER, in the one string that is this feature's entire
 * accessibility payload. With `ceil`: 721 → «12.1 … מתוך 12 · עומס יתר», and
 * 719 → «12 … מתוך 12» with no word.
 *
 * It never fires with the five shipped bands — all multiples of 30 — which is
 * exactly why it is easy to miss: the settings dialog makes a band any integer
 * in 1..1440 and does not require the five to be distinct or increasing.
 */
export function hoursFromMinutes(minutes: number): number {
  return Math.ceil(minutes / 6) / 10;
}

function group(row: SeamstressRef): 1 | 2 | 3 {
  const remaining = remainingMinutes(row);
  if (remaining === null) {
    return 2;
  }
  return remaining > 0 ? 1 : 3;
}

/**
 * The panel's row order and the assign picker's option order, from one call.
 *
 * ```
 * 1. capacity resolved AND remaining > 0   — by `remaining` DESC   (real headroom)
 * 2. NO capacity resolved                  — by `assigned_minutes` ASC (unknown)
 * 3. capacity resolved AND remaining <= 0  — by `remaining` DESC   (least over first)
 *    tiebreak throughout: display_name ASC, then id ASC
 * ```
 *
 * ⚠ THREE GROUPS, AND THE MIDDLE ONE IS THE CORRECTION. Two groups put every
 * capacity-set row ahead of every capacity-less one — INCLUDING A ROW AT 400 %.
 * On the state every boutique starts in (some configured, most not) the first
 * option in the control, the one a hurried shift manager takes, would be the
 * person the panel three inches above is drawing in red. "Unknown" and
 * "certainly worse than everyone" are not the same rank, and the feature's own
 * title is BALANCED assignment.
 *
 * ⚠ Group 2 keys on `assigned_minutes`, not on `due_soon_minutes`, because
 * «{{hours}} שעות משויכות» is the number that group's option and panel row
 * actually display. Ordering a group by a number neither surface shows is the
 * invisible rule this sort exists to avoid.
 *
 * ⚠ Nothing is hidden and nothing is disabled: the overloaded seamstress is
 * LAST, labelled, and one tap away. Overload flags, never blocks.
 *
 * Sorted on the CLIENT and never in the SQL: `remaining` is a pure function of
 * two fields already on the wire, so a server sort would be a second ordering
 * to keep in step, and changing the repository's ORDER BY would reorder the
 * payload for every other consumer. A NEW array, for the same reason — the
 * console keeps holding the server's order.
 */
export function sortByRemainingCapacity(rows: SeamstressRef[]): SeamstressRef[] {
  return [...rows].sort((a, b) => {
    const groupDelta = group(a) - group(b);
    if (groupDelta !== 0) {
      return groupDelta;
    }
    if (group(a) === 2) {
      const assignedDelta = a.assigned_minutes - b.assigned_minutes;
      if (assignedDelta !== 0) {
        return assignedDelta;
      }
    } else {
      // Both are in the same capacity-resolved group, so neither remaining is
      // null — the `?? 0`s are the narrowing TS cannot do across `group()`,
      // never fallbacks that can fire.
      const remainingDelta = (remainingMinutes(b) ?? 0) - (remainingMinutes(a) ?? 0);
      if (remainingDelta !== 0) {
        return remainingDelta;
      }
    }
    if (a.display_name !== b.display_name) {
      // A plain comparison and not `localeCompare`: the requirement is a
      // DETERMINISTIC tiebreak, not a linguistic collation, and this fold runs
      // on every paint of a five-second poll. An ICU-dependent order would also
      // make the assertion below environment-dependent.
      return a.display_name < b.display_name ? -1 : 1;
    }
    if (a.id === b.id) {
      return 0;
    }
    return a.id < b.id ? -1 : 1;
  });
}
