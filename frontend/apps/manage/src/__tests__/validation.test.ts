import { describe, expect, it } from "vitest";
import {
  ACCEPTED_CONTENT_TYPES,
  EU_SIZE_QUICK_LIST,
  MAX_CUSTOMER_NOTES_LENGTH,
  MAX_DEPOSIT_AMOUNT_AGOROT,
  MAX_DISPLAY_NAME_LENGTH,
  MAX_DRESS_DESCRIPTION_LENGTH,
  MAX_DRESS_NAME_LENGTH,
  MAX_MEDIA_PER_DRESS,
  MAX_PASSWORD_LENGTH,
  MAX_PRICE_AGOROT,
  MAX_SEARCH_LENGTH,
  MAX_SHIFT_LABEL_LENGTH,
  MAX_SIZE_LABEL_LENGTH,
  MAX_SORT_ORDER,
  MAX_STAFF_PHOTO_BYTES,
  MAX_TAGS,
  MAX_TAG_LENGTH,
  MAX_TEMPLATES_PER_DAY,
  MAX_UPLOAD_BYTES,
  MAX_VARIANTS_PER_DRESS,
  MAX_VARIANT_QUANTITY,
  MIN_STAFF_PASSWORD_LENGTH,
  MIN_UPLOAD_BYTES,
  agorotFromIlsInput,
  formatIlsAmount,
  ilsFromAgorot,
  normalizeSizeLabel,
  validateAppointmentType,
  validateCustomerNotes,
  validateDress,
  validateExceptionTimes,
  validateShiftTemplate,
  validateStaffDraft,
  validateStaffPhotoFile,
  validateTag,
  validateTerms,
  validateUploadFile,
  validateVariants,
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

// --- catalog (Feature 8) ---

describe("catalog constants mirror app/catalog/validation.py", () => {
  it("carries every mirrored bound at the backend's value", () => {
    expect(MAX_DRESS_NAME_LENGTH).toBe(200);
    expect(MAX_DRESS_DESCRIPTION_LENGTH).toBe(4000);
    expect(MAX_PRICE_AGOROT).toBe(100_000_000);
    expect(MAX_VARIANTS_PER_DRESS).toBe(60);
    expect(MAX_SIZE_LABEL_LENGTH).toBe(32);
    expect(MAX_VARIANT_QUANTITY).toBe(1000);
    expect(MAX_MEDIA_PER_DRESS).toBe(12);
    expect(MAX_UPLOAD_BYTES).toBe(10_485_760);
    expect(MIN_UPLOAD_BYTES).toBe(1024);
    expect(MAX_SEARCH_LENGTH).toBe(100);
    expect(MAX_SORT_ORDER).toBe(1_000_000);
  });

  it("accepts exactly the three image types the presign policy pins", () => {
    expect(ACCEPTED_CONTENT_TYPES).toEqual({
      "image/jpeg": ".jpg",
      "image/png": ".png",
      "image/webp": ".webp",
    });
  });

  it("offers the even EU sizes 32-58 as quick entry (frontend-only)", () => {
    expect(EU_SIZE_QUICK_LIST).toEqual([32, 34, 36, 38, 40, 42, 44, 46, 48, 50, 52, 54, 56, 58]);
  });
});

describe("normalizeSizeLabel", () => {
  it("strips and collapses whitespace", () => {
    expect(normalizeSizeLabel(" 38 ")).toBe("38");
    expect(normalizeSizeLabel("US  6")).toBe("US 6");
    expect(normalizeSizeLabel("\tמידה   מיוחדת\n")).toBe("מידה מיוחדת");
  });

  it("does NOT lowercase — casing is preserved as typed", () => {
    expect(normalizeSizeLabel("US 6")).toBe("US 6");
    expect(normalizeSizeLabel("us 6")).toBe("us 6");
  });
});

describe("formatIlsAmount", () => {
  it("groups thousands and drops a zero fraction", () => {
    expect(formatIlsAmount(890000)).toBe("8,900");
    expect(formatIlsAmount(120000)).toBe("1,200");
    expect(formatIlsAmount(1580000)).toBe("15,800");
  });

  it("keeps a non-zero fraction", () => {
    expect(formatIlsAmount(890050)).toBe("8,900.50");
  });

  it("round-trips ILS input through agorot", () => {
    const agorot = agorotFromIlsInput("8900.50");
    expect(agorot).toBe(890050);
    expect(ilsFromAgorot(agorot as number)).toBe("8900.50");
    expect(formatIlsAmount(agorot as number)).toBe("8,900.50");
  });
});

describe("validateDress", () => {
  const valid = { name: "עלמה", description: "שמלה", price_agorot: 890000, sort_order: 0 };

  it("accepts a valid dress", () => {
    expect(validateDress(valid)).toBeNull();
  });

  it("accepts a dress with no price and no description", () => {
    expect(validateDress({ ...valid, description: null, price_agorot: null })).toBeNull();
  });

  it("rejects a blank or over-long name", () => {
    expect(validateDress({ ...valid, name: "   " })).not.toBeNull();
    expect(validateDress({ ...valid, name: "א".repeat(MAX_DRESS_NAME_LENGTH + 1) })).not.toBeNull();
  });

  it("rejects an over-long description", () => {
    expect(
      validateDress({ ...valid, description: "א".repeat(MAX_DRESS_DESCRIPTION_LENGTH + 1) }),
    ).not.toBeNull();
  });

  it("rejects a price outside 1..MAX_PRICE_AGOROT", () => {
    expect(validateDress({ ...valid, price_agorot: 0 })).not.toBeNull();
    expect(validateDress({ ...valid, price_agorot: MAX_PRICE_AGOROT + 1 })).not.toBeNull();
  });

  it("rejects a sort order beyond the cap", () => {
    expect(validateDress({ ...valid, sort_order: MAX_SORT_ORDER + 1 })).not.toBeNull();
  });
});

describe("validateVariants", () => {
  it("accepts a valid matrix", () => {
    expect(validateVariants([{ size_label: "38", quantity: 3 }])).toBeNull();
  });

  it("rejects a blank or over-long size label", () => {
    expect(validateVariants([{ size_label: "  ", quantity: 1 }])).not.toBeNull();
    expect(
      validateVariants([{ size_label: "a".repeat(MAX_SIZE_LABEL_LENGTH + 1), quantity: 1 }]),
    ).not.toBeNull();
  });

  it("rejects a quantity outside 0..MAX_VARIANT_QUANTITY", () => {
    expect(validateVariants([{ size_label: "38", quantity: -1 }])).not.toBeNull();
    expect(
      validateVariants([{ size_label: "38", quantity: MAX_VARIANT_QUANTITY + 1 }]),
    ).not.toBeNull();
    expect(validateVariants([{ size_label: "38", quantity: 0 }])).toBeNull();
  });

  it("rejects duplicate sizes that differ only in case or whitespace", () => {
    expect(
      validateVariants([
        { size_label: "US 6", quantity: 1 },
        { size_label: "us  6", quantity: 2 },
      ]),
    ).not.toBeNull();
  });

  it("rejects more than MAX_VARIANTS_PER_DRESS rows", () => {
    const rows = Array.from({ length: MAX_VARIANTS_PER_DRESS + 1 }, (_, index) => ({
      size_label: String(index),
      quantity: 1,
    }));
    expect(validateVariants(rows)).not.toBeNull();
  });
});

describe("validateUploadFile", () => {
  function file(name: string, type: string, size: number) {
    return { name, type, size };
  }

  it("accepts each accepted content type at a legal size", () => {
    expect(validateUploadFile(file("a.jpg", "image/jpeg", 3_200_000))).toBeNull();
    expect(validateUploadFile(file("a.png", "image/png", 2048))).toBeNull();
    expect(validateUploadFile(file("a.webp", "image/webp", MAX_UPLOAD_BYTES))).toBeNull();
  });

  it("rejects HEIC with the transcode instruction", () => {
    expect(validateUploadFile(file("IMG_4823.heic", "image/heic", 6_000_000))).toBe(
      "HEIC אינו נתמך. שמרי כ-JPG",
    );
    // Safari hands over an empty type for HEIC — the extension is the fallback.
    expect(validateUploadFile(file("IMG_4823.HEIC", "", 6_000_000))).toBe(
      "HEIC אינו נתמך. שמרי כ-JPG",
    );
  });

  it("rejects any other unaccepted type", () => {
    expect(validateUploadFile(file("a.gif", "image/gif", 2048))).toBe(
      "סוג הקובץ אינו נתמך — JPG, PNG או WebP בלבד",
    );
    expect(validateUploadFile(file("a.svg", "image/svg+xml", 2048))).toBe(
      "סוג הקובץ אינו נתמך — JPG, PNG או WebP בלבד",
    );
  });

  it("rejects a file over MAX_UPLOAD_BYTES", () => {
    expect(validateUploadFile(file("a.jpg", "image/jpeg", MAX_UPLOAD_BYTES + 1))).toBe(
      "הקובץ גדול מ-10MB",
    );
  });

  it("rejects a file under MIN_UPLOAD_BYTES", () => {
    expect(validateUploadFile(file("a.jpg", "image/jpeg", MIN_UPLOAD_BYTES - 1))).toBe(
      "הקובץ אינו תמונה תקינה.",
    );
  });
});

// --- F51 staff bounds (mirrors backend/app/auth/schemas.py) ---

describe("validateStaffDraft", () => {
  const good = {
    display_name: "דנה",
    email: "dana@bella.example",
    password: "a-long-enough-pw",
  };

  it("accepts a draft inside every bound", () => {
    expect(validateStaffDraft(good)).toBeNull();
  });

  it("requires a display name", () => {
    expect(validateStaffDraft({ ...good, display_name: "   " })).toBe("יש להזין שם לתצוגה");
  });

  it("rejects a display name over MAX_DISPLAY_NAME_LENGTH", () => {
    expect(
      validateStaffDraft({ ...good, display_name: "x".repeat(MAX_DISPLAY_NAME_LENGTH + 1) }),
    ).toBe("השם לתצוגה ארוך מדי");
    expect(
      validateStaffDraft({ ...good, display_name: "x".repeat(MAX_DISPLAY_NAME_LENGTH) }),
    ).toBeNull();
  });

  it("rejects a password under MIN_STAFF_PASSWORD_LENGTH", () => {
    expect(
      validateStaffDraft({ ...good, password: "x".repeat(MIN_STAFF_PASSWORD_LENGTH - 1) }),
    ).toBe(`הסיסמה חייבת להכיל לפחות ${MIN_STAFF_PASSWORD_LENGTH} תווים`);
    expect(
      validateStaffDraft({ ...good, password: "x".repeat(MIN_STAFF_PASSWORD_LENGTH) }),
    ).toBeNull();
  });

  it("rejects a password over MAX_PASSWORD_LENGTH", () => {
    expect(validateStaffDraft({ ...good, password: "x".repeat(MAX_PASSWORD_LENGTH + 1) })).toBe(
      "הסיסמה ארוכה מדי",
    );
  });

  it("requires an email address on the create form", () => {
    expect(validateStaffDraft({ ...good, email: "   " })).toBe("יש להזין כתובת אימייל");
  });

  // The gap the browser leaves: WHATWG's `type="email"` regex makes the dot in
  // the domain optional, so `dana@bella` passes native constraint validation
  // and pydantic's EmailStr then answers an ENGLISH sentence that the create
  // form would render verbatim into the RTL console.
  it("rejects a domain the server's EmailStr will reject", () => {
    for (const address of ["dana@bella", "dana", "dana@", "@bella.example", "da na@b.example"]) {
      expect(validateStaffDraft({ ...good, email: address })).toBe("כתובת האימייל אינה תקינה");
    }
  });

  it("accepts the addresses EmailStr accepts", () => {
    for (const address of ["dana@bella.example", "d.a+1@mail.co.il", "  dana@bella.example  "]) {
      expect(validateStaffDraft({ ...good, email: address })).toBeNull();
    }
  });

  // An omitted password is the "leave it unchanged" case on the edit form; the
  // create form supplies its own required-field message before calling this.
  it("accepts a null password", () => {
    expect(validateStaffDraft({ ...good, password: null })).toBeNull();
  });

  // The edit form has no email field at all — the address is not editable (D5).
  it("accepts a null email", () => {
    expect(validateStaffDraft({ ...good, email: null })).toBeNull();
  });

  // No email validator and no strength rule, deliberately: the server's EmailStr
  // is the authority, and spec D6 declines composition rules (800-63B advises
  // against them and they push an owner toward `Boutique1!`).
  it("has no opinion about the email or the password's composition", () => {
    expect(validateStaffDraft({ ...good, password: "aaaaaaaaaaaa" })).toBeNull();
  });
});

// --- customers CRM (Feature 53) ---

describe("validateTag", () => {
  it("accepts an ordinary tag against an empty chip list", () => {
    expect(validateTag("VIP", [])).toBeNull();
  });

  it("rejects one character over the cap and accepts the cap exactly", () => {
    expect(validateTag("א".repeat(MAX_TAG_LENGTH), [])).toBeNull();
    expect(validateTag("א".repeat(MAX_TAG_LENGTH + 1), [])).toBe("customers.tagTooLong");
  });

  // The whole C0 set plus DEL, NOT the notes class: \t, \n and \r are the three
  // characters that separate the two, and a newline inside a TEXT[] element
  // renders a two-line chip. Getting the backend import backwards is invisible
  // until exactly these three.
  it("rejects tab, newline and return along with the rest of C0", () => {
    for (const bad of ["\x00", "a\tb", "a\nb", "a\rb", "a\x7fb"]) {
      expect(validateTag(bad, [])).toBe("customers.tagInvalid");
    }
  });

  // Both sides strip before they judge, and BOTH strips count U+000B as
  // whitespace — JS trim() and Python str.strip() agree — so a tag that is
  // nothing but control whitespace is a BLANK tag the server drops silently
  // (normalize_tags: `if not tag: continue`), never an invalid one. The caller
  // drops it with no message for the same reason. Asserted rather than left
  // implicit: the obvious test here says "customers.tagInvalid" and would have
  // forced the client to refuse something the server accepts.
  it("treats a control-whitespace-only tag as blank, the way the server does", () => {
    expect(validateTag("\x0b", [])).toBeNull();
    expect(validateTag("  ", [])).toBeNull();
  });

  // normalize_tags dedups casefolded and keeps the first occurrence, so a
  // re-cased duplicate would silently vanish on save.
  it("rejects a case-insensitive duplicate of an existing chip", () => {
    expect(validateTag(" vip ", ["VIP"])).toBe("customers.tagDuplicate");
  });

  it("reports a full card only once the tag itself is legal", () => {
    const full = Array.from({ length: MAX_TAGS }, (_, i) => `tag${i}`);
    expect(validateTag("חדשה", full)).toBe("customers.tagsFull");
    // Still the length message, not "full" — she gets the fault she can see.
    expect(validateTag("א".repeat(MAX_TAG_LENGTH + 1), full)).toBe("customers.tagTooLong");
    expect(validateTag("חדשה", full.slice(0, MAX_TAGS - 1))).toBeNull();
  });
});

describe("validateCustomerNotes", () => {
  it("accepts the cap exactly and rejects one character over", () => {
    expect(validateCustomerNotes("a".repeat(MAX_CUSTOMER_NOTES_LENGTH))).toBeNull();
    expect(validateCustomerNotes("a".repeat(MAX_CUSTOMER_NOTES_LENGTH + 1))).toBe(
      "customers.notesTooLong",
    );
  });

  // A paragraph keeps its whitespace; the U+000B a paste out of Word carries is
  // the one maxLength cannot catch and the only trigger customers.notesInvalid
  // has in the whole feature.
  it("keeps tab, newline and return but rejects the rest of C0", () => {
    expect(validateCustomerNotes("שורה\nשנייה\tעם\rהחזרה")).toBeNull();
    expect(validateCustomerNotes("הודבק\x0bמ-Word")).toBe("customers.notesInvalid");
    expect(validateCustomerNotes("\x00")).toBe("customers.notesInvalid");
  });

  // Empty string means CLEARED, never an error — boutique/validation.py:110.
  it("accepts an empty string", () => {
    expect(validateCustomerNotes("")).toBeNull();
  });
});

// --- F38: the staff photo cap ---

describe("validateStaffPhotoFile", () => {
  const jpeg = (size: number) => ({ name: "dana.jpg", type: "image/jpeg", size });

  it("accepts a file at exactly the 2MB ceiling and refuses one byte over", () => {
    // Both edges from both sides: a cap that admits everything is not a cap,
    // and one that refuses its own documented maximum is a different bug.
    expect(validateStaffPhotoFile(jpeg(MAX_STAFF_PHOTO_BYTES))).toBeNull();
    expect(validateStaffPhotoFile(jpeg(MAX_STAFF_PHOTO_BYTES + 1))).toBe("התמונה גדולה מ-2MB");
  });

  it("refuses a file the dress gallery would have accepted", () => {
    // THE assertion that makes this function worth existing rather than
    // reusing validateUploadFile: a 5 MiB photo is a legal dress image and an
    // illegal avatar, and only this cap tells them apart before the request.
    expect(validateUploadFile(jpeg(5_000_000))).toBeNull();
    expect(validateStaffPhotoFile(jpeg(5_000_000))).toBe("התמונה גדולה מ-2MB");
  });

  it("keeps the HEIC advice rather than restating it as a size problem", () => {
    // Safari hands over an empty type for HEIC, so the extension is the
    // fallback — and the message names an action the owner can take on her own
    // phone. Reporting it as "too large" would send her to crop a file no
    // browser can render at any size.
    expect(validateStaffPhotoFile({ name: "dana.HEIC", type: "", size: 4096 })).toBe(
      "HEIC אינו נתמך. שמרי כ-JPG",
    );
  });

  it("keeps the shared type and floor rules", () => {
    expect(validateStaffPhotoFile({ name: "d.gif", type: "image/gif", size: 4096 })).toBe(
      "סוג הקובץ אינו נתמך — JPG, PNG או WebP בלבד",
    );
    expect(validateStaffPhotoFile(jpeg(MIN_UPLOAD_BYTES - 1))).toBe("הקובץ אינו תמונה תקינה.");
  });
});

describe("validateShiftTemplate", () => {
  it("accepts an ordinary morning shift", () => {
    expect(validateShiftTemplate("משמרת בוקר", "09:00", "14:00")).toBeNull();
  });

  it("refuses a blank or whitespace-only label", () => {
    expect(validateShiftTemplate("", "09:00", "14:00")).toBe("יש להזין שם למשמרת.");
    expect(validateShiftTemplate("   ", "09:00", "14:00")).toBe("יש להזין שם למשמרת.");
  });

  it("bounds the label at the mirrored length", () => {
    expect(validateShiftTemplate("א".repeat(MAX_SHIFT_LABEL_LENGTH), "09:00", "14:00")).toBeNull();
    expect(validateShiftTemplate("א".repeat(MAX_SHIFT_LABEL_LENGTH + 1), "09:00", "14:00")).toBe(
      "שם המשמרת ארוך מדי.",
    );
  });

  it("refuses an overnight shift and a zero-length one", () => {
    // A bridal boutique does not run an overnight shift, and
    // `shift_templates_order_check` says so in the DDL too.
    expect(validateShiftTemplate("לילה", "22:00", "02:00")).toBe(
      "שעת הסיום חייבת להיות אחרי שעת ההתחלה.",
    );
    expect(validateShiftTemplate("ריק", "09:00", "09:00")).toBe(
      "שעת הסיום חייבת להיות אחרי שעת ההתחלה.",
    );
  });

  it("refuses a missing time rather than comparing an empty string", () => {
    expect(validateShiftTemplate("בוקר", "", "14:00")).toBe(
      "שעת הסיום חייבת להיות אחרי שעת ההתחלה.",
    );
  });

  it("keeps the per-day cap unreachable from the total one", () => {
    // 6 × 7 = 42 exactly, so MAX_TEMPLATES is a server-side guard with no screen
    // — asserted here so nobody mirrors it and builds a meter for it.
    expect(MAX_TEMPLATES_PER_DAY).toBe(6);
  });
});
