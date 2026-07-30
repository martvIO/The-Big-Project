import { afterEach, describe, expect, it, vi } from "vitest";
import { jerusalemDate, jerusalemTime, todayJerusalem } from "../lib/jerusalem";

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
