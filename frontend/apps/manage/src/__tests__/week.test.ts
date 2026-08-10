import { describe, expect, it } from "vitest";
import { DAY_NAMES, addDays } from "../lib/week";

// These assertions only mean something because apps/manage's `test` script pins
// TZ=America/New_York (the storefront and packages/ui pin the same deliberately
// wrong zone). On a UTC runner a naive `new Date(dateOnly).getDate()` agrees
// with the right answer, so the bug would pass.

describe("DAY_NAMES", () => {
  it("is the Israeli week, Sunday first", () => {
    // The order is `availability_rules.day_of_week`'s encoding — 0=Sunday —
    // which `jerusalem_day_index` produces on the server and
    // `test_frontend_constant_parity.py` pins.
    expect(DAY_NAMES).toHaveLength(7);
    expect(DAY_NAMES[0]).toBe("ראשון");
    expect(DAY_NAMES[6]).toBe("שבת");
  });
});

describe("addDays", () => {
  it("walks a plain wire date without ever entering the device's zone", () => {
    // ⚠ THE ASSERTION WITH THE BITE. Under TZ=America/New_York,
    // `new Date("2026-11-08")` is UTC midnight = 7 November at 19:00 local, so
    // a naive `.getDate() + n` renders the 7th for a week that starts on the
    // 8th — and F39's Sunday heading would read «ראשון · 7.11».
    expect(addDays("2026-11-08", 0)).toBe("2026-11-08");
    expect(addDays("2026-11-08", 1)).toBe("2026-11-09");
    expect(addDays("2026-11-08", 6)).toBe("2026-11-14");
  });

  it("rolls over a month, a year and a leap day", () => {
    expect(addDays("2026-11-29", 6)).toBe("2026-12-05");
    expect(addDays("2026-12-27", 6)).toBe("2027-01-02");
    expect(addDays("2028-02-27", 2)).toBe("2028-02-29");
  });

  it("crosses a DST boundary without losing a day", () => {
    // Israel's clocks go back on the last Sunday of October; a millisecond-based
    // `+ n * 86400000` lands an hour short and can read back as the previous
    // day. UTC date parts cannot.
    expect(addDays("2026-10-25", 6)).toBe("2026-10-31");
    expect(addDays("2027-03-26", 3)).toBe("2027-03-29");
  });

  it("answers an empty string for a value that is not a wire date", () => {
    expect(addDays("not-a-date", 1)).toBe("");
  });
});
