// Boutique-calendar reads, never the device's — a port of the storefront's
// BookPage.tsx helpers. New York is a different calendar day from Jerusalem for
// part of every day, and a booking belongs to the boutique's day.
//
// EVERY formatter here passes `timeZone: JERusalem`, imported from @boutique/ui
// and never re-declared. Date bounds come from instants the server returned.
import { JERusalem } from "@boutique/ui";

const DATE_PARTS = new Intl.DateTimeFormat("en-CA", {
  timeZone: JERusalem,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});
const TIME_PARTS = new Intl.DateTimeFormat("en-GB", {
  timeZone: JERusalem,
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

function partsOf(formatter: Intl.DateTimeFormat, instant: Date): Record<string, string> {
  return Object.fromEntries(
    formatter.formatToParts(instant).map((part) => [part.type, part.value]),
  );
}

// d.m.yyyy, unpadded — the spelling comms_templates.py already texts the bride,
// so the owner reads one date format across the product.
export function jerusalemDate(instant: string): string {
  const parts = partsOf(DATE_PARTS, new Date(instant));
  return `${Number(parts.day)}.${Number(parts.month)}.${parts.year}`;
}

export function jerusalemTime(instant: string): string {
  const parts = partsOf(TIME_PARTS, new Date(instant));
  return `${parts.hour}:${parts.minute}`;
}

// The same Jerusalem calendar day in the ISO spelling that <input type="date">
// and the API's ?date= both take. Separate from jerusalemDate above, which is
// the human d.m.yyyy the SMS deck already texts the bride.
export function jerusalemIsoDate(instant: string): string {
  const parts = partsOf(DATE_PARTS, new Date(instant));
  return `${parts.year}-${parts.month}-${parts.day}`;
}

// A PLAIN Jerusalem calendar date, NEVER an instant — the one helper here that
// takes no timestamp and builds no Date. The dashboard's `generated_on`,
// `from_date` and `to_date` are `datetime.date` on the wire ("2026-05-03"), so
// splitting the string is the whole job: `new Date("2026-05-03")` parses as UTC
// midnight, and running that through a zoned formatter re-zones a date that was
// never in a zone. It happens to survive today only because Jerusalem is ahead
// of UTC — the exact class of bug this file exists to prevent. Same d.m.yyyy
// spelling as jerusalemDate, so the owner reads one date format product-wide.
export function plainDate(iso: string): string {
  const [year, month, day] = iso.split("-");
  return `${Number(day)}.${Number(month)}.${year}`;
}

// The day filter's default: a JERUSALEM calendar date — it goes through the
// zoned formatter above like everything else, never a bare device-clock read,
// which lands on the wrong calendar day for part of every day.
export function todayJerusalem(): string {
  return jerusalemIsoDate(new Date().toISOString());
}
