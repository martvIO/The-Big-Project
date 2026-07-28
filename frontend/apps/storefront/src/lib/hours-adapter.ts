import { JERusalem, nextOpen, todayHours } from "@boutique/ui";
import type { Exceptions, TimeWindow, WeeklyRule } from "@boutique/ui";
import type { TFunction } from "i18next";
import type { PublicBoutiqueResponse, PublicHoursException, PublicHoursRule } from "../api";

// The wire's hours shape adapted to what @boutique/ui's lib/hours speaks, plus
// the one composed "today" line. Three screens render that line — the catalog
// header, /about and the catalog's empty state — and a second copy of the
// next-open walk is a second place for the closed-today calculation to drift.

export const DAY_KEYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"] as const;

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

export function toWeeklyRules(rules: PublicHoursRule[]): WeeklyRule[] {
  const byDay = new Map<number, TimeWindow[]>();
  for (const rule of rules) {
    const windows = byDay.get(rule.day_of_week) ?? [];
    windows.push({ open: hhmm(rule.open_time), close: hhmm(rule.close_time) });
    byDay.set(rule.day_of_week, windows);
  }
  return [...byDay].map(([dayOfWeek, windows]) => ({ dayOfWeek, windows }));
}

export function toExceptions(exceptions: PublicHoursException[]): Exceptions {
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

// "היום: 10:00–19:00", or "סגור היום · נפתח מחר ב-10:00". Closed is never an
// error state, so the caller renders this in plain ink.
export function todayLine(boutique: PublicBoutiqueResponse, now: Date, t: TFunction): string {
  const weekly = toWeeklyRules(boutique.rules);
  const exceptions = toExceptions(boutique.exceptions);
  const today = todayHours(weekly, now, JERusalem, exceptions);
  if (!today.closed) {
    return t("hours.today", {
      hours: today.windows.map((win) => `${win.open}–${win.close}`).join(", "),
    });
  }

  const upcoming = nextOpen(weekly, now, JERusalem, exceptions);
  if (upcoming === null) {
    return t("hours.closedToday");
  }
  const reopens = upcoming.isTomorrow
    ? t("hours.opensTomorrow", { time: upcoming.open })
    : t("hours.opensOn", {
        day: t(`hours.day.${DAY_KEYS[upcoming.dayIndex]}`),
        time: upcoming.open,
      });
  return `${t("hours.closedToday")} · ${reopens}`;
}
