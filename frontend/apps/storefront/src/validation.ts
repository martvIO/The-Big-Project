// Client-side mirrors of backend/app/booking/validation.py and the phone
// normalizer in backend/app/notifications/validation.py. The backend is the
// authority — these exist so the bride sees an immediate Hebrew error instead
// of a round-trip 400. backend/tests/test_frontend_constant_parity.py fails if
// a bound drifts from its Python counterpart.
//
// Backend semantics, mirrored exactly: blank checks run on the TRIMMED value,
// length checks on the RAW value, and the raw value is what goes on the wire.

export const MAX_CUSTOMER_NAME_LENGTH = 80;
export const MAX_BOOKING_NOTES_LENGTH = 500;

export function validateName(name: string): string | null {
  if (!name.trim()) {
    return "צריך למלא שם כדי שנוכל לרשום את התור.";
  }
  if (name.length > MAX_CUSTOMER_NAME_LENGTH) {
    return "השם ארוך מדי. עד 80 תווים.";
  }
  return null;
}

export function validateNotes(notes: string): string | null {
  if (notes.length > MAX_BOOKING_NOTES_LENGTH) {
    return "ההערה ארוכה מדי. עד 500 תווים.";
  }
  return null;
}

// The client twin of normalize_israeli_mobile, same steps in the same order:
// charset gate on the trimmed input, strip separators, "05X…" gains 972 in
// place of the zero, final shape +9725XXXXXXXX. The OTP token is keyed on the
// normalized form, so any divergence here surfaces as PHONE_NOT_VERIFIED.
const PHONE_CHARSET = /^\+?[0-9 ()-]+$/;
const NORMALIZED_MOBILE = /^\+9725\d{8}$/;

function normalizeOrNull(raw: string): string | null {
  const candidate = raw.trim();
  if (!candidate || !PHONE_CHARSET.test(candidate)) {
    return null;
  }
  let digits = candidate.replace(/\D/g, "");
  if (digits.startsWith("05")) {
    digits = `972${digits.slice(1)}`;
  }
  const normalized = `+${digits}`;
  return NORMALIZED_MOBILE.test(normalized) ? normalized : null;
}

// Normalization happens exactly once, here, before every call that carries the
// phone (/otp/send, /otp/verify, /bookings). An invalid input passes through
// raw — validatePhone has already refused it, so it never reaches the wire.
export function normalizePhone(raw: string): string {
  return normalizeOrNull(raw) ?? raw;
}

export function validatePhone(raw: string): string | null {
  if (normalizeOrNull(raw) === null) {
    return "המספר לא נראה כמו מספר נייד ישראלי. אפשר להזין עשר ספרות שמתחילות ב-05.";
  }
  return null;
}
