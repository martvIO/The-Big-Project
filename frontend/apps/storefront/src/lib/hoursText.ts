import { JERusalem, nextOpen, todayHours } from "@boutique/ui";
import type { Exceptions, TimeWindow, WeeklyRule } from "@boutique/ui";
import type { TFunction } from "i18next";
import type { BoutiqueResponse, ExceptionRow, HoursRow } from "../api";

// The wire's hours shape adapted to what @boutique/ui's lib/hours speaks, plus
// the one composed "today" line. Three screens render that line — the catalog
// header, /about and the catalog's empty state — and a second copy of the
// next-open walk is a second place for the closed-today calculation to drift.
//
// No Hebrew literal lives here: keys in, string out.

// The wire carries "HH:MM:SS"; lib/hours.ts and the design both speak "HH:MM".
export function hhmm(time: string): string {
  return time.slice(0, 5);
}

// "2026-12-25" -> "25.12". Locale date formatting is banned here — it reads an
// implicit timezone, and the wire date is already a Jerusalem calendar date.
export function shortDate(isoDate: string): string {
  const [, month, day] = isoDate.split("-");
  return `${String(Number(day))}.${String(Number(month))}`;
}

// The wire carries ONE ROW PER WINDOW so a boutique can have a lunch break.
// Grouping by day is what makes that survive: a naive one-to-one map would keep
// only the last window and render half the boutique's hours.
export function toWeeklyRules(rules: HoursRow[]): WeeklyRule[] {
  const byDay = new Map<number, TimeWindow[]>();
  for (const rule of rules) {
    const windows = byDay.get(rule.day_of_week) ?? [];
    windows.push({ open: hhmm(rule.open_time), close: hhmm(rule.close_time) });
    byDay.set(rule.day_of_week, windows);
  }
  return [...byDay].map(([dayOfWeek, windows]) => ({ dayOfWeek, windows }));
}

export function toExceptions(exceptions: ExceptionRow[]): Exceptions {
  const byDate: Exceptions = {};
  for (const item of exceptions) {
    const windows = byDate[item.date] ?? [];
    // Both times null means closed all day, which lib/hours reads as an empty
    // window list — so the key must exist even when nothing is pushed.
    if (item.open_time !== null && item.close_time !== null) {
      windows.push({ open: hhmm(item.open_time), close: hhmm(item.close_time) });
    }
    byDate[item.date] = windows;
  }
  return byDate;
}

/**
 * "היום: 10:00–19:00", or "סגור היום · נפתח מחר ב-10:00".
 *
 * Returns NULL when the boutique has no weekly rules at all — the state every
 * newly provisioned tenant ships in. That case is NOT "closed today": saying so
 * would advertise a closure the owner never entered. The catalog header omits
 * the line entirely (a header line reading "hours unknown" is worse than no
 * line) and /about renders about.hoursUnavailable above an all-closed table.
 *
 * Closed is never an error state, so the caller renders this in plain ink.
 */
export function todayLine(boutique: BoutiqueResponse, now: Date, t: TFunction): string | null {
  const weekly = toWeeklyRules(boutique.hours);
  if (weekly.length === 0) {
    return null;
  }
  const exceptions = toExceptions(boutique.exceptions);
  const today = todayHours(weekly, now, JERusalem, exceptions);
  if (!today.closed) {
    return t("about.today", {
      hours: today.windows.map((win) => `${win.open}–${win.close}`).join(", "),
    });
  }

  const upcoming = nextOpen(weekly, now, JERusalem, exceptions);
  if (upcoming === null) {
    return t("about.closedToday");
  }
  const dayLabels = t("hours.days", { returnObjects: true }) as string[];
  const reopens = upcoming.isTomorrow
    ? t("about.opensTomorrow", { time: upcoming.open })
    : t("about.opensOn", {
        day: dayLabels[upcoming.dayIndex],
        time: upcoming.open,
      });
  return `${t("about.closedToday")} · ${reopens}`;
}
