import { describe, expect, it } from "vitest";
import {
  MAX_BOOKING_NOTES_LENGTH,
  MAX_CUSTOMER_NAME_LENGTH,
  normalizePhone,
  validateName,
  validateNotes,
  validatePhone,
} from "../validation";

describe("booking constants mirror app/booking/validation.py", () => {
  it("carries every mirrored bound at the backend's value", () => {
    expect(MAX_CUSTOMER_NAME_LENGTH).toBe(80);
    expect(MAX_BOOKING_NOTES_LENGTH).toBe(500);
  });
});

describe("validateName", () => {
  it("accepts a plain name", () => {
    expect(validateName("רות לוי")).toBeNull();
  });

  it("rejects a blank name — the blank check runs on the trimmed value", () => {
    expect(validateName("")).toBe("צריך למלא שם כדי שנוכל לרשום את התור.");
    expect(validateName("   ")).toBe("צריך למלא שם כדי שנוכל לרשום את התור.");
  });

  it("measures length on the RAW value, like the backend", () => {
    expect(validateName("א".repeat(MAX_CUSTOMER_NAME_LENGTH))).toBeNull();
    expect(validateName("א".repeat(MAX_CUSTOMER_NAME_LENGTH + 1))).toBe(
      "השם ארוך מדי. עד 80 תווים.",
    );
    // 79 chars trimmed, 81 raw — the backend rejects the raw length, so must we.
    expect(validateName(` ${"א".repeat(MAX_CUSTOMER_NAME_LENGTH - 1)} `)).toBe(
      "השם ארוך מדי. עד 80 תווים.",
    );
  });
});

describe("validateNotes", () => {
  it("accepts empty notes — the field is optional", () => {
    expect(validateNotes("")).toBeNull();
  });

  it("measures length on the RAW value, like the backend", () => {
    expect(validateNotes("א".repeat(MAX_BOOKING_NOTES_LENGTH))).toBeNull();
    expect(validateNotes("א".repeat(MAX_BOOKING_NOTES_LENGTH + 1))).toBe(
      "ההערה ארוכה מדי. עד 500 תווים.",
    );
  });
});

// The contract table, ported from Backend/tests/test_notifications_validation.py
// — validatePhone must accept and reject exactly what normalize_israeli_mobile
// does, or a number the client blesses gets a 400 from /otp/send.
const ACCEPTED_PHONES: ReadonlyArray<readonly [string, string]> = [
  ["0501234567", "+972501234567"],
  ["050-123-4567", "+972501234567"],
  ["050 123 4567", "+972501234567"],
  ["(050) 1234567", "+972501234567"],
  ["+972501234567", "+972501234567"],
  ["+972 50-123-4567", "+972501234567"],
  ["972501234567", "+972501234567"],
  ["0521234567", "+972521234567"],
  ["0581234567", "+972581234567"],
];

const REJECTED_PHONES: readonly string[] = [
  "",
  "   ",
  "031234567", // landline
  "+97231234567", // landline via country code
  "12345", // too short
  "05012345678", // too long
  "050123456", // too short mobile
  "+15551234567", // foreign
  "abc0501234567", // junk charset
  "0501234567;drop", // junk charset
  "9720501234567", // 972 followed by the leading zero
  "++972501234567", // double plus
  "05a1234567", // letter inside
];

describe("validatePhone / normalizePhone", () => {
  it("accepts every format the backend normalizer accepts", () => {
    for (const [raw, expected] of ACCEPTED_PHONES) {
      expect(validatePhone(raw), raw).toBeNull();
      expect(normalizePhone(raw), raw).toBe(expected);
    }
  });

  it("rejects everything else, and normalizePhone passes the raw input through", () => {
    for (const raw of REJECTED_PHONES) {
      expect(validatePhone(raw), JSON.stringify(raw)).toBe(
        "המספר לא נראה כמו מספר נייד ישראלי. אפשר להזין עשר ספרות שמתחילות ב-05.",
      );
      expect(normalizePhone(raw), JSON.stringify(raw)).toBe(raw);
    }
  });
});
