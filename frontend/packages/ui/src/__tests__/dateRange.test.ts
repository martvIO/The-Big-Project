import { describe, expect, it, vi } from "vitest";
import { formatDateRange } from "../lib/dateRange";

// ⚠ THE SUITE RUNS UNDER TZ=America/New_York (see package.json) AND THAT IS THE
// WHOLE POINT OF THIS FILE. `new Date("2026-08-12")` is UTC midnight, which in
// New York is 20:00 on the ELEVENTH — every assertion below is off by one day
// unless the formatter pins `timeZone: "UTC"`. In Israel (UTC+2/+3) the naive
// implementation passes, so a suite that ran locally would ship the bug.

describe("formatDateRange", () => {
  it("renders a same-month range as one numeral island inside the month name", () => {
    expect(formatDateRange("2026-08-12", "2026-08-18", new Date("2026-08-08T00:00:00Z"))).toEqual({
      kind: "same-month",
      days: "12–18",
      month: "באוגוסט",
    });
  });

  it("keeps a one-day hold readable rather than repeating the number", () => {
    expect(formatDateRange("2026-08-12", "2026-08-12", new Date("2026-08-08T00:00:00Z"))).toEqual({
      kind: "same-month",
      days: "12",
      month: "באוגוסט",
    });
  });

  it("splits a cross-month range into two whole dates", () => {
    expect(formatDateRange("2026-08-28", "2026-09-03", new Date("2026-08-08T00:00:00Z"))).toEqual({
      kind: "split",
      start: "28 באוגוסט",
      end: "3 בספטמבר",
    });
  });

  it("appends the year only on the parts whose year is not the current one", () => {
    expect(formatDateRange("2026-12-28", "2027-01-02", new Date("2026-08-08T00:00:00Z"))).toEqual({
      kind: "split",
      start: "28 בדצמבר",
      end: "2 בינואר 2027",
    });
  });

  it("appends the year to both parts when the whole range is in another year", () => {
    expect(formatDateRange("2027-03-01", "2027-03-04", new Date("2026-08-08T00:00:00Z"))).toEqual({
      kind: "same-month",
      days: "1–4",
      month: "במרץ 2027",
    });
  });

  it("formats in UTC, not the viewer's zone", () => {
    // The output assertions above already fail west of UTC if this is wrong.
    // This one pins the CALL, so a refactor that happens to produce the same
    // strings under this one zone cannot quietly drop the option.
    const original = Intl.DateTimeFormat;
    const seen: (Intl.DateTimeFormatOptions | undefined)[] = [];
    const spy = vi.spyOn(Intl, "DateTimeFormat").mockImplementation(function (
      this: unknown,
      locales?: Intl.LocalesArgument,
      options?: Intl.DateTimeFormatOptions,
    ) {
      seen.push(options);
      return original(locales, options);
    } as unknown as typeof Intl.DateTimeFormat);
    try {
      formatDateRange("2026-08-12", "2026-08-18", new Date("2026-08-08T00:00:00Z"));
    } finally {
      spy.mockRestore();
    }
    expect(seen.length).toBeGreaterThan(0);
    for (const options of seen) {
      expect(options).toMatchObject({ timeZone: "UTC" });
    }
  });
});
