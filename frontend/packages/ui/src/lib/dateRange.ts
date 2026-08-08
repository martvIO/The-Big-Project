// Booked-out date ranges, formatted once for both apps (F28 §5). The manage
// pane and the public dress page state the same windows in the same words, and
// two implementations of "12–18 באוגוסט" is how they stop agreeing.
//
// ⚠ EVERY FORMATTER HERE PASSES `timeZone: "UTC"` AND THE RANGE IS NEVER ROUTED
// THROUGH THE JERUSALEM DATETIME FORMATTERS. `starts_on`/`ends_on` are
// date-only strings; `new Date("2026-08-12")` is UTC MIDNIGHT, so formatting it
// in the viewer's zone renders the 11th for anyone west of UTC. These are
// calendar days the boutique named, not instants — there is no zone to convert
// between, only a parse to undo. The unit suite runs under TZ=America/New_York
// precisely so a naive implementation reds there instead of shipping green from
// Israel.

// U+2013. An ASCII hyphen reads as a minus sign beside numerals.
const EN_DASH = "–";

// The two shapes exist because bidi isolation differs, not because the copy
// does. `same-month` is ONE numeral run — «12–18» — so it is one `<bdi>` island
// inside the month name. `split` is two whole dates that each carry their own
// numerals, so each gets its own island and the dash sits in RTL flow between
// them (R19's split shape).
export type FormattedDateRange =
  | { kind: "same-month"; days: string; month: string }
  | { kind: "split"; start: string; end: string };

// Constructed per call rather than hoisted to module scope, so a test can spy
// on the constructor and prove the UTC option is still passed. These render a
// handful of rows on two screens; a cache would be a premature one.
function format(date: Date, options: Intl.DateTimeFormatOptions): string {
  return new Intl.DateTimeFormat("he-IL", { timeZone: "UTC", ...options }).format(date);
}

function parseUtc(dateOnly: string): Date {
  return new Date(`${dateOnly}T00:00:00Z`);
}

function utcYear(date: Date): string {
  return format(date, { year: "numeric" });
}

// «12 באוגוסט» minus its day, i.e. «באוגוסט». Derived from the day+month
// formatter rather than asking Intl for `month: "long"` alone, which answers the
// bare «אוגוסט» — the preposition lives in the pattern's literal, and the copy
// this ships is «12–18 באוגוסט».
function monthOf(date: Date, withYear: boolean): string {
  const whole = format(date, {
    day: "numeric",
    month: "long",
    ...(withYear ? { year: "numeric" } : {}),
  });
  return whole.replace(/^\d+\s*/u, "");
}

export function formatDateRange(
  startsOn: string,
  endsOn: string,
  now: Date = new Date(),
): FormattedDateRange {
  const start = parseUtc(startsOn);
  const end = parseUtc(endsOn);
  const currentYear = utcYear(now);
  const startYear = utcYear(start);
  const endYear = utcYear(end);

  if (startYear === endYear && startsOn.slice(0, 7) === endsOn.slice(0, 7)) {
    const startDay = format(start, { day: "numeric" });
    const endDay = format(end, { day: "numeric" });
    return {
      kind: "same-month",
      // A one-day hold is «12 באוגוסט», not «12–12».
      days: startDay === endDay ? startDay : `${startDay}${EN_DASH}${endDay}`,
      month: monthOf(start, endYear !== currentYear),
    };
  }
  return {
    kind: "split",
    start: format(start, {
      day: "numeric",
      month: "long",
      ...(startYear === currentYear ? {} : { year: "numeric" }),
    }),
    end: format(end, {
      day: "numeric",
      month: "long",
      ...(endYear === currentYear ? {} : { year: "numeric" }),
    }),
  };
}
