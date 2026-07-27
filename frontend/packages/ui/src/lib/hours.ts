// Israeli-week opening-hours logic. Pure and timezone-explicit: every day/date
// is derived through Intl with an explicit timeZone (default Asia/Jerusalem),
// never the device clock. Day indices are 0=Sunday .. 6=Saturday (Israeli week
// starts Sunday). This module holds NO Hebrew — day labels and the "closed" /
// "opens tomorrow" copy are supplied by the app's i18n at render time.

export const JERusalem = "Asia/Jerusalem";

export interface TimeWindow {
  open: string; // "HH:MM"
  close: string; // "HH:MM"
}

export interface WeeklyRule {
  dayOfWeek: number; // 0=Sun .. 6=Sat
  windows: TimeWindow[]; // empty => closed
}

// A grouped, display-ready row spanning startDay..endDay (inclusive).
export interface HoursRow {
  startDay: number;
  endDay: number;
  windows: TimeWindow[];
  closed: boolean;
}

export interface DayHours {
  dayIndex: number;
  windows: TimeWindow[];
  closed: boolean;
}

export interface NextOpen {
  dayIndex: number;
  daysAhead: number;
  isTomorrow: boolean;
  open: string;
}

// Exceptions override a specific ISO date (YYYY-MM-DD, Jerusalem calendar):
// [] means closed that day, a window list means special hours.
export type Exceptions = Record<string, TimeWindow[]>;

function windowsKey(windows: TimeWindow[]): string {
  if (windows.length === 0) return "closed";
  return windows.map((w) => `${w.open}-${w.close}`).join("|");
}

// Groups the seven-day week into rows, collapsing only days that are BOTH
// adjacent in the Sun-first week AND have an identical window set. Every day is
// accounted for, Saturday included; a day with no rule is a closed row.
export function groupWeeklyRules(rules: WeeklyRule[]): HoursRow[] {
  const byDay = new Map<number, TimeWindow[]>();
  for (const rule of rules) byDay.set(rule.dayOfWeek, rule.windows ?? []);
  const windowsFor = (day: number) => byDay.get(day) ?? [];

  const rows: HoursRow[] = [];
  let start = 0;
  for (let day = 0; day <= 6; day++) {
    const sameAsNext = day < 6 && windowsKey(windowsFor(day)) === windowsKey(windowsFor(day + 1));
    if (!sameAsNext) {
      const windows = windowsFor(start);
      rows.push({ startDay: start, endDay: day, windows, closed: windows.length === 0 });
      start = day + 1;
    }
  }
  return rows;
}

const WEEKDAY_INDEX: Record<string, number> = {
  Sun: 0,
  Mon: 1,
  Tue: 2,
  Wed: 3,
  Thu: 4,
  Fri: 5,
  Sat: 6,
};

interface JerusalemDate {
  iso: string; // YYYY-MM-DD in the target zone
  dayIndex: number;
}

function partsInZone(instant: Date, timeZone: string): JerusalemDate {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    weekday: "short",
  }).formatToParts(instant);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  return {
    iso: `${get("year")}-${get("month")}-${get("day")}`,
    dayIndex: WEEKDAY_INDEX[get("weekday")] ?? 0,
  };
}

// Noon-UTC anchoring keeps the Jerusalem calendar day stable across DST when
// stepping day-to-day (noon UTC is ~14:00–15:00 in Jerusalem, never near midnight).
function addDays(base: JerusalemDate, offset: number, timeZone: string): JerusalemDate {
  const [y, m, d] = base.iso.split("-").map(Number);
  const anchored = new Date(Date.UTC(y, m - 1, d + offset, 12, 0, 0));
  return partsInZone(anchored, timeZone);
}

export function jerusalemDayIndex(now: Date, timeZone: string = JERusalem): number {
  return partsInZone(now, timeZone).dayIndex;
}

function resolve(rules: WeeklyRule[], exceptions: Exceptions | undefined, date: JerusalemDate): TimeWindow[] {
  const exception = exceptions?.[date.iso];
  if (exception !== undefined) return exception;
  return rules.find((r) => r.dayOfWeek === date.dayIndex)?.windows ?? [];
}

export function todayHours(
  rules: WeeklyRule[],
  now: Date,
  timeZone: string = JERusalem,
  exceptions?: Exceptions,
): DayHours {
  const today = partsInZone(now, timeZone);
  const windows = resolve(rules, exceptions, today);
  return { dayIndex: today.dayIndex, windows, closed: windows.length === 0 };
}

// The next day (searching forward up to a week) that has an open window. Returns
// null if the boutique is never open. `isTomorrow` is true ONLY when that day is
// literally the next calendar day — a closed Saturday or a closed exception
// pushes it further out and this stays false.
export function nextOpen(
  rules: WeeklyRule[],
  now: Date,
  timeZone: string = JERusalem,
  exceptions?: Exceptions,
): NextOpen | null {
  const today = partsInZone(now, timeZone);
  for (let offset = 1; offset <= 7; offset++) {
    const date = addDays(today, offset, timeZone);
    const windows = resolve(rules, exceptions, date);
    if (windows.length > 0) {
      return {
        dayIndex: date.dayIndex,
        daysAhead: offset,
        isTomorrow: offset === 1,
        open: windows[0].open,
      };
    }
  }
  return null;
}
