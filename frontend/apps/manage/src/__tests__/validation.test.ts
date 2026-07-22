import { describe, expect, it } from "vitest";
import {
  agorotFromIlsInput,
  ilsFromAgorot,
  MAX_DEPOSIT_AMOUNT_AGOROT,
  validateAppointmentType,
  validateExceptionTimes,
  validateTerms,
  validateWeeklyRules,
} from "../validation";

describe("money (agorot <-> ILS)", () => {
  it("parses whole and decimal ILS input into integer agorot", () => {
    expect(agorotFromIlsInput("150")).toBe(15000);
    expect(agorotFromIlsInput("150.5")).toBe(15050);
    expect(agorotFromIlsInput("150.50")).toBe(15050);
    expect(agorotFromIlsInput("0")).toBe(0);
  });

  it("rejects invalid ILS input", () => {
    expect(agorotFromIlsInput("")).toBeNull();
    expect(agorotFromIlsInput("abc")).toBeNull();
    expect(agorotFromIlsInput("1.234")).toBeNull();
    expect(agorotFromIlsInput("-5")).toBeNull();
  });

  it("formats agorot as ILS for display", () => {
    expect(ilsFromAgorot(15050)).toBe("150.50");
    expect(ilsFromAgorot(100)).toBe("1.00");
  });
});

describe("validateAppointmentType", () => {
  const valid = {
    name: "מדידה ראשונה",
    duration_minutes: 60,
    deposit_required: false,
    deposit_amount_agorot: null,
  };

  it("accepts a valid type", () => {
    expect(validateAppointmentType(valid)).toBeNull();
  });

  it("requires a deposit amount when deposit_required is on", () => {
    expect(
      validateAppointmentType({ ...valid, deposit_required: true, deposit_amount_agorot: null }),
    ).not.toBeNull();
    expect(
      validateAppointmentType({ ...valid, deposit_required: true, deposit_amount_agorot: 0 }),
    ).not.toBeNull();
    expect(
      validateAppointmentType({ ...valid, deposit_required: true, deposit_amount_agorot: 5000 }),
    ).toBeNull();
  });

  it("allows an inert amount when deposit_required is off", () => {
    expect(validateAppointmentType({ ...valid, deposit_amount_agorot: 5000 })).toBeNull();
  });

  it("bounds the deposit amount", () => {
    expect(
      validateAppointmentType({
        ...valid,
        deposit_required: true,
        deposit_amount_agorot: MAX_DEPOSIT_AMOUNT_AGOROT + 1,
      }),
    ).not.toBeNull();
  });

  it("rejects blank names and out-of-range durations", () => {
    expect(validateAppointmentType({ ...valid, name: "   " })).not.toBeNull();
    expect(validateAppointmentType({ ...valid, duration_minutes: 0 })).not.toBeNull();
    expect(validateAppointmentType({ ...valid, duration_minutes: 1441 })).not.toBeNull();
  });
});

describe("validateWeeklyRules", () => {
  it("accepts non-overlapping windows including touching ones", () => {
    expect(
      validateWeeklyRules([
        { day_of_week: 0, open_time: "09:00", close_time: "12:00", capacity: 1 },
        { day_of_week: 0, open_time: "12:00", close_time: "17:00", capacity: 2 },
        { day_of_week: 3, open_time: "10:00", close_time: "14:00", capacity: 1 },
      ]),
    ).toBeNull();
  });

  it("rejects close_time not after open_time", () => {
    expect(
      validateWeeklyRules([{ day_of_week: 1, open_time: "12:00", close_time: "12:00", capacity: 1 }]),
    ).not.toBeNull();
    expect(
      validateWeeklyRules([{ day_of_week: 1, open_time: "12:00", close_time: "09:00", capacity: 1 }]),
    ).not.toBeNull();
  });

  it("rejects overlapping windows on the same day", () => {
    expect(
      validateWeeklyRules([
        { day_of_week: 2, open_time: "09:00", close_time: "13:00", capacity: 1 },
        { day_of_week: 2, open_time: "12:00", close_time: "16:00", capacity: 1 },
      ]),
    ).not.toBeNull();
  });

  it("allows identical windows on different days", () => {
    expect(
      validateWeeklyRules([
        { day_of_week: 2, open_time: "09:00", close_time: "13:00", capacity: 1 },
        { day_of_week: 4, open_time: "09:00", close_time: "13:00", capacity: 1 },
      ]),
    ).toBeNull();
  });

  it("rejects non-positive capacity", () => {
    expect(
      validateWeeklyRules([{ day_of_week: 0, open_time: "09:00", close_time: "10:00", capacity: 0 }]),
    ).not.toBeNull();
  });
});

describe("validateExceptionTimes", () => {
  it("accepts closed-all-day (both empty)", () => {
    expect(validateExceptionTimes(null, null)).toBeNull();
  });

  it("accepts special hours (both set, close after open)", () => {
    expect(validateExceptionTimes("10:00", "14:00")).toBeNull();
  });

  it("rejects one-sided times", () => {
    expect(validateExceptionTimes("10:00", null)).not.toBeNull();
    expect(validateExceptionTimes(null, "14:00")).not.toBeNull();
  });

  it("rejects close_time not after open_time", () => {
    expect(validateExceptionTimes("14:00", "10:00")).not.toBeNull();
    expect(validateExceptionTimes("14:00", "14:00")).not.toBeNull();
  });
});

describe("validateTerms", () => {
  const valid = {
    terms_text: "ביטול עד 48 שעות לפני התור — החזר מלא.",
    refundable_until_hours_before: 48,
    forfeit_percent: 100,
  };

  it("accepts valid terms", () => {
    expect(validateTerms(valid)).toBeNull();
  });

  it("rejects blank terms text", () => {
    expect(validateTerms({ ...valid, terms_text: "   " })).not.toBeNull();
  });

  it("enforces the 50 KB byte cap (Hebrew is 2 bytes/char in UTF-8)", () => {
    // 26,000 Hebrew chars = 52,000 bytes > 51,200; 25,000 chars = 50,000 bytes fits.
    expect(validateTerms({ ...valid, terms_text: "א".repeat(26_000) })).not.toBeNull();
    expect(validateTerms({ ...valid, terms_text: "א".repeat(25_000) })).toBeNull();
  });

  it("rejects negative refund windows", () => {
    expect(validateTerms({ ...valid, refundable_until_hours_before: -1 })).not.toBeNull();
  });

  it("bounds forfeit_percent to 0-100", () => {
    expect(validateTerms({ ...valid, forfeit_percent: -1 })).not.toBeNull();
    expect(validateTerms({ ...valid, forfeit_percent: 101 })).not.toBeNull();
    expect(validateTerms({ ...valid, forfeit_percent: 0 })).toBeNull();
  });
});
