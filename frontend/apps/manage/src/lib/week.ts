// The Israeli week: the seven day names and the one piece of date arithmetic
// this console is allowed to do.
//
// `DAY_NAMES` lived in HoursSection.tsx until F39 needed the same seven, in the
// same order, on three more panes. Two copies of a seven-element array that must
// agree with `availability_rules.day_of_week` is exactly the drift `lib/roles.ts`
// was written to end.
//
// The day INDEX is NOT here: `jerusalemDayIndex` lives in
// `@boutique/ui/lib/hours` and is pinned to the backend's
// `jerusalem_day_index` by `test_frontend_constant_parity.py`. One index, one
// pin, and never re-derived in a component.

// 0=Sunday … 6=Saturday.
export const DAY_NAMES = ["ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת"];

// ⚠ DATE PARTS, NEVER MILLISECONDS. `new Date(ms + n * 86400000)` is off by an
// hour across a DST boundary and can land on the previous day; Date's UTC
// setters do exact calendar arithmetic and month/year/leap rollover for free.
//
// ⚠ AND THE INPUT IS A PLAIN `YYYY-MM-DD`, NEVER AN INSTANT. `new Date("2026-11-08")`
// parses as UTC midnight and reads back as the 7th under this suite's
// TZ=America/New_York, so `new Date(weekStart).getDate() + n` renders «ראשון ·
// 7.11» for a week that starts on the 8th. Parsing with an explicit `T00:00:00Z`
// and reading UTC parts is what makes the arithmetic zone-free.
//
// This helper is private twice already — `ReservationsPane.tsx` and
// `RescheduleDialog.tsx` each carry their own copy with the same header. F39
// declines to be the third and puts it here instead.
// ponytail: those two keep their private copies in this feature — collapsing
// them is a two-file follow-up with its own test surface, and F39 does not need
// to touch either file to stop being the third copy.
export function addDays(dateOnly: string, days: number): string {
  const date = new Date(`${dateOnly}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}
