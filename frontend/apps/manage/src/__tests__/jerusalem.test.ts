import { afterEach, describe, expect, it, vi } from "vitest";
import {
  jerusalemDate,
  jerusalemIsoDate,
  jerusalemTime,
  jerusalemWeekday,
  plainDate,
  plainDayMonth,
  todayJerusalem,
} from "../lib/jerusalem";

// These assertions only mean something because apps/manage's `test` script pins
// TZ=America/New_York (the storefront and packages/ui pin the same deliberately
// wrong zone). On a UTC runner an unzoned read agrees with Jerusalem for most of
// the day, so a device-clock bug would pass.

afterEach(() => {
  vi.useRealTimers();
});

describe("jerusalemDate / jerusalemTime", () => {
  it("formats d.m.yyyy and HH:MM, unpadded day and month like the SMS deck", () => {
    // 07:00Z on 4 August is 10:00 in Jerusalem (UTC+3), 03:00 in New York.
    expect(jerusalemDate("2026-08-04T07:00:00Z")).toBe("4.8.2026");
    expect(jerusalemTime("2026-08-04T07:00:00Z")).toBe("10:00");
  });

  it("reads the Jerusalem calendar day, not the device's", () => {
    // 21:30Z is 00:30 on the 5th in Jerusalem and 17:30 on the 4th in New York.
    expect(jerusalemDate("2026-08-04T21:30:00Z")).toBe("5.8.2026");
    expect(jerusalemTime("2026-08-04T21:30:00Z")).toBe("00:30");
  });

  it("pads the hour and keeps a 24h clock past noon", () => {
    expect(jerusalemTime("2026-08-04T04:05:00Z")).toBe("07:05");
    expect(jerusalemTime("2026-08-04T16:00:00Z")).toBe("19:00");
  });
});

describe("plainDate", () => {
  // The dashboard's generated_on, from_date and to_date are PLAIN Jerusalem
  // calendar dates on the wire, not instants — so they must never meet a Date.
  it("formats a wire date d.m.yyyy without constructing a Date", () => {
    expect(plainDate("2026-05-03")).toBe("3.5.2026");
    expect(plainDate("2026-07-25")).toBe("25.7.2026");
  });

  it("does not re-zone a date that was never in a zone", () => {
    // This is the assertion with the bite, and the whole reason the helper
    // exists. Under this suite's TZ=America/New_York, `new Date("2026-05-03")`
    // is UTC midnight = 2 May at 20:00 local, so a device-clock read of the
    // same string prints 2.5.2026 — and jerusalemDate would re-zone a date that
    // was never in a zone. Route a wire date through a Date by either path and
    // this line goes red.
    expect(plainDate("2026-05-03")).toBe("3.5.2026");
    expect(plainDate("2026-01-01")).toBe("1.1.2026");
  });

  // The dashboard's week-row label, under the same never-an-instant rule and in
  // the same file — the year lives once per panel in the range line.
  it("drops the year for the week-row label, still without constructing a Date", () => {
    expect(plainDayMonth("2026-05-03")).toBe("3.5");
    expect(plainDayMonth("2026-01-01")).toBe("1.1");
  });
});

describe("todayJerusalem", () => {
  it("answers an ISO date for <input type=\"date\">", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-04T07:00:00Z"));
    expect(todayJerusalem()).toBe("2026-08-04");
  });

  it("is the Jerusalem calendar date even when the device is a day behind", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-04T21:30:00Z"));
    expect(todayJerusalem()).toBe("2026-08-05");
  });
});

describe("jerusalemWeekday", () => {
  it("names the boutique's weekday, not the device's", () => {
    // 16:00Z on Wednesday 4 November is 18:00 Wednesday in Jerusalem — F39's
    // default deadline instant.
    expect(jerusalemWeekday("2026-11-04T16:00:00Z")).toBe("יום רביעי");
    // 22:00Z on Wednesday is already Thursday in Jerusalem and still Wednesday
    // afternoon in New York.
    expect(jerusalemWeekday("2026-11-04T22:00:00Z")).toBe("יום חמישי");
  });

  it("agrees with plainDayMonth(jerusalemIsoDate(...)) on the same instant", () => {
    // ⚠ THE ASSERTION THAT CATCHES BOTH F39 FAILURES AT ONCE (design F-14).
    //
    // 1. `plainDayMonth(instant)` splits the instant on `-`, so its day part is
    //    "04T16:00:00Z" and `Number(...)` is NaN — «יום רביעי, NaN.11, 18:00» on
    //    the most-viewed line in the feature.
    // 2. Slicing the instant by hand instead reads a UTC calendar day as if it
    //    were Jerusalem's. For a tenant whose deadline is «01:00», Wednesday
    //    01:00 Jerusalem resolves to 23:00Z on TUESDAY — so the slice names
    //    Tuesday beside a weekday that says Wednesday.
    const wednesdayAtOne = "2026-11-03T23:00:00Z";
    expect(jerusalemWeekday(wednesdayAtOne)).toBe("יום רביעי");
    expect(plainDayMonth(jerusalemIsoDate(wednesdayAtOne))).toBe("4.11");
    // And the sliced-by-hand spelling really does disagree — asserted so the
    // shortcut cannot be reintroduced as an equivalent.
    expect(plainDayMonth(wednesdayAtOne.slice(0, 10))).toBe("3.11");
  });
});
