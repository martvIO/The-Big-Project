import { afterEach, describe, expect, it, vi } from "vitest";
import { jerusalemDate, jerusalemTime, plainDate, todayJerusalem } from "../lib/jerusalem";

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
