// Client-side mirrors of backend/app/booking/validation.py and the phone
// normalizer in backend/app/notifications/validation.py. The backend is the
// authority — these exist so the bride sees an immediate Hebrew error instead
// of a round-trip 400. backend/tests/test_frontend_constant_parity.py fails if
// a bound drifts from its Python counterpart.
//
// Backend semantics, mirrored exactly: blank checks run on the TRIMMED value,
// length checks on the RAW value, control-character checks last, and the raw
// value is what goes on the wire.
//
// The messages come from he.ts through i18n.t() rather than being restated
// here. apps/manage's twin hardcodes its Hebrew, and the cost showed up in
// review: he.ts separately defined booking.nameRequired, nameTooLong,
// notesTooLong and phoneInvalid with byte-identical text that no production
// code referenced, so the two copies were held together by nothing but luck.

import i18n from "./i18n";

export const MAX_CUSTOMER_NAME_LENGTH = 80;
export const MAX_BOOKING_NOTES_LENGTH = 500;

// _CONTROL_CHARS / _CONTROL_CHARS_EXCEPT_WS in app/booking/validation.py,
// character for character. `name` bars the whole C0 set plus DEL — a line break
// in a value F16 will template into an SMS is header-injection material.
// `notes` is a paragraph, so it keeps \t, \n and \r.
//
// Without these the client blessed a value the API then refused with a 400 that
// no retry can clear: a bride pasting notes out of Word carries U+000B or
// U+000C, spends an SMS getting to the submit, and every attempt after that
// fails identically while burning her booking-create budget.
// oxlint-disable-next-line no-control-regex -- mirroring a backend charset gate
const CONTROL_CHARS = /[\x00-\x1f\x7f]/;
// oxlint-disable-next-line no-control-regex -- same, minus \t \n \r
const CONTROL_CHARS_EXCEPT_WS = /[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/;

export function validateName(name: string): string | null {
  if (!name.trim()) {
    return i18n.t("booking.nameRequired");
  }
  if (name.length > MAX_CUSTOMER_NAME_LENGTH) {
    return i18n.t("booking.nameTooLong");
  }
  if (CONTROL_CHARS.test(name)) {
    return i18n.t("booking.invalidCharacters");
  }
  return null;
}

export function validateNotes(notes: string): string | null {
  if (notes.length > MAX_BOOKING_NOTES_LENGTH) {
    return i18n.t("booking.notesTooLong");
  }
  if (CONTROL_CHARS_EXCEPT_WS.test(notes)) {
    return i18n.t("booking.invalidCharacters");
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
    return i18n.t("booking.phoneInvalid");
  }
  return null;
}
