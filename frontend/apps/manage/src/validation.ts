// Client-side mirrors of backend/app/boutique/validation.py. The backend is
// the authority — these exist so the owner sees an immediate Hebrew error
// instead of a round-trip 400. Bounds must stay in sync with the migration
// CHECK constraints.

export const MAX_APPOINTMENT_TYPE_NAME_LENGTH = 200;
export const MAX_DURATION_MINUTES = 24 * 60;
// 1,000,000 ILS in agorot — same sanity cap as the backend.
export const MAX_DEPOSIT_AMOUNT_AGOROT = 100_000_000;
export const MAX_TERMS_TEXT_BYTES = 50 * 1024;

const ILS_INPUT_PATTERN = /^\d+(\.\d{1,2})?$/;

export function agorotFromIlsInput(input: string): number | null {
  const trimmed = input.trim();
  if (!ILS_INPUT_PATTERN.test(trimmed)) {
    return null;
  }
  // Integer math, not parseFloat * 100 — float rounding must never touch money.
  const [whole, fraction = ""] = trimmed.split(".");
  return Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
}

export function ilsFromAgorot(agorot: number): string {
  const whole = Math.trunc(agorot / 100);
  const fraction = Math.abs(agorot % 100);
  return `${whole}.${String(fraction).padStart(2, "0")}`;
}

function toMinutes(time: string): number {
  const [hours = "0", minutes = "0"] = time.split(":");
  return Number(hours) * 60 + Number(minutes);
}

export interface AppointmentTypeDraft {
  name: string;
  duration_minutes: number;
  deposit_required: boolean;
  deposit_amount_agorot: number | null;
}

export function validateAppointmentType(draft: AppointmentTypeDraft): string | null {
  if (!draft.name.trim()) {
    return "יש להזין שם לסוג התור";
  }
  if (draft.name.length > MAX_APPOINTMENT_TYPE_NAME_LENGTH) {
    return "שם סוג התור ארוך מדי";
  }
  if (
    !Number.isInteger(draft.duration_minutes) ||
    draft.duration_minutes < 1 ||
    draft.duration_minutes > MAX_DURATION_MINUTES
  ) {
    return "משך התור חייב להיות בין דקה אחת ל-1440 דקות";
  }
  if (
    draft.deposit_required &&
    (draft.deposit_amount_agorot === null || draft.deposit_amount_agorot <= 0)
  ) {
    return "כשנדרשת מקדמה יש להזין סכום מקדמה";
  }
  if (
    draft.deposit_amount_agorot !== null &&
    (draft.deposit_amount_agorot < 0 || draft.deposit_amount_agorot > MAX_DEPOSIT_AMOUNT_AGOROT)
  ) {
    return "סכום המקדמה מחוץ לטווח המותר";
  }
  return null;
}

export interface WeeklyRuleDraft {
  day_of_week: number;
  open_time: string;
  close_time: string;
  capacity: number;
}

export function validateWeeklyRules(rules: WeeklyRuleDraft[]): string | null {
  for (const rule of rules) {
    if (!Number.isInteger(rule.day_of_week) || rule.day_of_week < 0 || rule.day_of_week > 6) {
      return "יום בשבוע אינו תקין";
    }
    if (!rule.open_time || !rule.close_time) {
      return "יש להזין שעת פתיחה ושעת סגירה";
    }
    if (toMinutes(rule.close_time) <= toMinutes(rule.open_time)) {
      return "שעת הסגירה חייבת להיות אחרי שעת הפתיחה";
    }
    if (!Number.isInteger(rule.capacity) || rule.capacity < 1) {
      return "קיבולת חייבת להיות לפחות 1";
    }
  }
  const byDay = new Map<number, WeeklyRuleDraft[]>();
  for (const rule of rules) {
    const dayRules = byDay.get(rule.day_of_week) ?? [];
    dayRules.push(rule);
    byDay.set(rule.day_of_week, dayRules);
  }
  for (const dayRules of byDay.values()) {
    const ordered = [...dayRules].sort(
      (a, b) => toMinutes(a.open_time) - toMinutes(b.open_time),
    );
    for (let index = 1; index < ordered.length; index += 1) {
      // Touching windows (close == next open) are fine; overlap is not.
      if (toMinutes(ordered[index].open_time) < toMinutes(ordered[index - 1].close_time)) {
        return "חלונות באותו יום אינם יכולים לחפוף";
      }
    }
  }
  return null;
}

export function validateExceptionTimes(
  openTime: string | null,
  closeTime: string | null,
): string | null {
  if ((openTime === null) !== (closeTime === null)) {
    return "יש להזין גם שעת פתיחה וגם שעת סגירה, או להשאיר את שתיהן ריקות (סגור כל היום)";
  }
  if (openTime !== null && closeTime !== null && toMinutes(closeTime) <= toMinutes(openTime)) {
    return "שעת הסגירה חייבת להיות אחרי שעת הפתיחה";
  }
  return null;
}

export interface TermsDraft {
  terms_text: string;
  refundable_until_hours_before: number;
  forfeit_percent: number;
}

export function validateTerms(draft: TermsDraft): string | null {
  if (!draft.terms_text.trim()) {
    return "יש להזין את נוסח מדיניות הביטולים";
  }
  // Byte cap, not char count — Hebrew is 2 bytes/char in UTF-8.
  if (new TextEncoder().encode(draft.terms_text).length > MAX_TERMS_TEXT_BYTES) {
    return "נוסח המדיניות חורג מהגודל המרבי (50KB)";
  }
  if (
    !Number.isInteger(draft.refundable_until_hours_before) ||
    draft.refundable_until_hours_before < 0
  ) {
    return "חלון ההחזר חייב להיות 0 שעות או יותר";
  }
  if (
    !Number.isInteger(draft.forfeit_percent) ||
    draft.forfeit_percent < 0 ||
    draft.forfeit_percent > 100
  ) {
    return "אחוז החילוט חייב להיות בין 0 ל-100";
  }
  return null;
}
