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

// Display-only: thousands separated, a zero fraction dropped. The caller wraps
// the result in <bdi dir="ltr"> — the numeric run must never reorder inside
// surrounding Hebrew.
export function formatIlsAmount(agorot: number): string {
  const [whole, fraction] = ilsFromAgorot(agorot).split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return fraction === "00" ? grouped : `${grouped}.${fraction}`;
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

// --- catalog (Feature 8) ---
//
// Mirrors of backend/app/catalog/validation.py. The backend is the authority;
// these exist so the owner sees an immediate Hebrew error instead of a
// round-trip 400 — and, for uploads, so a 10 MB file never leaves her phone
// only to be refused. backend/tests/test_frontend_constant_parity.py fails if
// any of these drifts from its Python counterpart.

export const MAX_DRESS_NAME_LENGTH = 200;
export const MAX_DRESS_DESCRIPTION_LENGTH = 4000;
export const MAX_PRICE_AGOROT = 100_000_000;
export const MAX_VARIANTS_PER_DRESS = 60;
export const MAX_SIZE_LABEL_LENGTH = 32;
export const MAX_VARIANT_QUANTITY = 1000;
export const MAX_MEDIA_PER_DRESS = 12;
export const MAX_UPLOAD_BYTES = 10_485_760;
export const MIN_UPLOAD_BYTES = 1024;
export const MAX_SEARCH_LENGTH = 100;
export const MAX_SORT_ORDER = 1_000_000;

// The extension map is the server's, restated for the client's type check only:
// the storage key's extension is always derived server-side from the declared
// type, never from a filename.
export const ACCEPTED_CONTENT_TYPES: Record<string, string> = {
  "image/jpeg": ".jpg",
  "image/png": ".png",
  "image/webp": ".webp",
};

// Frontend-only quick-entry list. The backend accepts free-text labels and has
// no consumer for this, so defining it server-side too would guarantee drift.
export const EU_SIZE_QUICK_LIST = [32, 34, 36, 38, 40, 42, 44, 46, 48, 50, 52, 54, 56, 58];

// Strip and collapse internal whitespace. Deliberately NOT lowercased — the
// owner's "US 6" is stored as typed; lower() in the DB's partial unique index is
// what stops "US 6" and "us 6" becoming two stock buckets for one size, and
// sizeKey() is how the client predicts that collision.
export function normalizeSizeLabel(label: string): string {
  return label.trim().split(/\s+/).join(" ");
}

// The client-side twin of the index's lower(size_label) expression.
export function sizeKey(label: string): string {
  return normalizeSizeLabel(label).toLowerCase();
}

export interface DressDraft {
  name: string;
  description: string | null;
  price_agorot: number | null;
  sort_order: number;
}

export function validateDress(draft: DressDraft): string | null {
  if (!draft.name.trim()) {
    return "יש להזין שם לשמלה";
  }
  if (draft.name.length > MAX_DRESS_NAME_LENGTH) {
    return "שם השמלה ארוך מדי";
  }
  if (draft.description !== null && draft.description.length > MAX_DRESS_DESCRIPTION_LENGTH) {
    return "התיאור ארוך מדי";
  }
  // NULL price means "no price recorded" — the storefront shows «מחיר בתיאום».
  if (
    draft.price_agorot !== null &&
    (!Number.isInteger(draft.price_agorot) ||
      draft.price_agorot < 1 ||
      draft.price_agorot > MAX_PRICE_AGOROT)
  ) {
    return "המחיר מחוץ לטווח המותר";
  }
  if (!Number.isInteger(draft.sort_order) || Math.abs(draft.sort_order) > MAX_SORT_ORDER) {
    return "סדר בקטלוג מחוץ לטווח המותר";
  }
  return null;
}

export interface VariantDraft {
  size_label: string;
  quantity: number;
}

export function validateVariants(variants: VariantDraft[]): string | null {
  if (variants.length > MAX_VARIANTS_PER_DRESS) {
    return `אפשר עד ${MAX_VARIANTS_PER_DRESS} מידות לשמלה.`;
  }
  const seen = new Set<string>();
  for (const variant of variants) {
    const label = normalizeSizeLabel(variant.size_label);
    if (!label) {
      return "יש להזין שם מידה";
    }
    if (label.length > MAX_SIZE_LABEL_LENGTH) {
      return "שם המידה ארוך מדי";
    }
    if (
      !Number.isInteger(variant.quantity) ||
      variant.quantity < 0 ||
      variant.quantity > MAX_VARIANT_QUANTITY
    ) {
      return `הכמות חייבת להיות בין 0 ל-${MAX_VARIANT_QUANTITY}`;
    }
    const key = sizeKey(label);
    if (seen.has(key)) {
      return `המידה «${label}» כבר קיימת ברשימה.`;
    }
    seen.add(key);
  }
  return null;
}

// Only the properties we actually read, so tests need no File polyfill.
export interface UploadCandidate {
  name: string;
  type: string;
  size: number;
}

export function validateUploadFile(file: UploadCandidate): string | null {
  const type = file.type.toLowerCase();
  const name = file.name.toLowerCase();
  // Safari hands over an empty type for HEIC, so the extension is the fallback.
  // HEIC gets its own message: no browser renders it, but the owner's phone
  // can save as JPG, which is an action she can take.
  if (type === "image/heic" || type === "image/heif" || /\.hei[cf]$/.test(name)) {
    return "HEIC אינו נתמך. שמרי כ-JPG";
  }
  if (!(type in ACCEPTED_CONTENT_TYPES)) {
    return "סוג הקובץ אינו נתמך — JPG, PNG או WebP בלבד";
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    return "הקובץ גדול מ-10MB";
  }
  if (file.size < MIN_UPLOAD_BYTES) {
    return "הקובץ אינו תמונה תקינה.";
  }
  return null;
}

// --- staff (Feature 51) ---
//
// Mirrors of backend/app/auth/schemas.py, and load-bearing beyond the usual
// "immediate Hebrew instead of a round-trip 400": the staff forms render ONE
// field-local Hebrew message for the single 400 the server can answer them (a
// wrong current_password), and that is only honest because every other 400 those
// forms could produce is caught right here. backend/tests/
// test_frontend_constant_parity.py fails if any of these drifts.

export const MIN_STAFF_PASSWORD_LENGTH = 10;
export const MAX_PASSWORD_LENGTH = 4096;
export const MAX_DISPLAY_NAME_LENGTH = 200;

// The shape EmailStr rejects that the browser's own `type="email"` accepts:
// WHATWG's control regex makes the dot in the domain OPTIONAL, so `dana@bella`
// sails through native constraint validation and comes back as an ENGLISH
// pydantic sentence in an RTL console. Deliberately not a fuller RFC 5322
// attempt — the server stays the authority on what is deliverable; this only
// has to cover the gap the browser leaves.
const EMAIL_SHAPE = /^[^\s@]+@[^\s@.]+(\.[^\s@.]+)+$/;

export interface StaffDraft {
  display_name: string;
  // null on the edit form: the address is not editable after creation (spec
  // D5), so only the create form supplies one.
  email: string | null;
  // null on the edit form means "leave the password alone"; the create form
  // supplies its own required-field message before calling this.
  password: string | null;
}

export function validateStaffDraft(draft: StaffDraft): string | null {
  if (!draft.display_name.trim()) {
    return "יש להזין שם לתצוגה";
  }
  if (draft.display_name.length > MAX_DISPLAY_NAME_LENGTH) {
    return "השם לתצוגה ארוך מדי";
  }
  if (draft.email !== null) {
    if (!draft.email.trim()) {
      return "יש להזין כתובת אימייל";
    }
    if (!EMAIL_SHAPE.test(draft.email.trim())) {
      return "כתובת האימייל אינה תקינה";
    }
  }
  // No password strength rule: 800-63B advises against composition rules —
  // they push an owner toward `Boutique1!`, which is worse than the length
  // floor alone.
  if (draft.password !== null) {
    if (draft.password.length < MIN_STAFF_PASSWORD_LENGTH) {
      return `הסיסמה חייבת להכיל לפחות ${MIN_STAFF_PASSWORD_LENGTH} תווים`;
    }
    if (draft.password.length > MAX_PASSWORD_LENGTH) {
      return "הסיסמה ארוכה מדי";
    }
  }
  return null;
}

// --- customers CRM (Feature 53) ---
//
// Mirrors of backend/app/customers/validation.py. backend/tests/
// test_frontend_constant_parity.py fails if any of these drifts.
//
// These return i18n KEYS, not Hebrew. The rest of this file hardcodes its
// strings and the storefront twin's header records what that cost — two copies
// of one sentence held together by luck. F53's copy deck is the single place
// its strings exist (spec D11), so the caller resolves the key with the
// interpolation values it already has in scope.

export const MAX_TAG_LENGTH = 24;
export const MAX_TAGS = 10;
export const MAX_CUSTOMER_NOTES_LENGTH = 2000;
// Not a write bound — it is Query(max_length=…) on GET /manage/customers. It is
// mirrored because it is applied as maxLength on the search box: without it a
// pasted over-long term answers 400 and the list renders an outage message for
// an input error that every retry reproduces.
export const MAX_SEARCH_TERM_LENGTH = 80;

// _CONTROL_CHARS / _CONTROL_CHARS_EXCEPT_WS in app/booking/validation.py,
// character for character — app/customers/validation.py imports those two
// rather than restating them, so one backend module is the authority for both
// consoles. A tag bars the whole C0 set plus DEL: a newline inside a TEXT[]
// element renders a two-line chip and copies wrong. Notes are a paragraph, so
// they keep \t, \n and \r.
// oxlint-disable-next-line no-control-regex -- mirroring a backend charset gate
const CONTROL_CHARS = /[\x00-\x1f\x7f]/;
// oxlint-disable-next-line no-control-regex -- same, minus \t \n \r
const CONTROL_CHARS_EXCEPT_WS = /[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/;

// `existing` is the DRAFT chip list, not the saved one — the cap and the
// duplicate rule both have to see tags added since the last save. A blank tag
// is not an error here: the caller drops it without a message, because typing
// nothing and pressing «הוספה» is not a mistake worth a sentence.
export function validateTag(tag: string, existing: string[]): string | null {
  const trimmed = tag.trim();
  if (trimmed.length > MAX_TAG_LENGTH) {
    return "customers.tagTooLong";
  }
  if (CONTROL_CHARS.test(trimmed)) {
    return "customers.tagInvalid";
  }
  // Case-insensitive, matching normalize_tags' casefold dedup: the server would
  // silently drop a re-cased duplicate and the chip would vanish on save.
  const folded = trimmed.toLocaleLowerCase();
  if (existing.some((current) => current.trim().toLocaleLowerCase() === folded)) {
    return "customers.tagDuplicate";
  }
  if (existing.length >= MAX_TAGS) {
    return "customers.tagsFull";
  }
  return null;
}

// maxLength on a <textarea> bounds length but does NOT filter control
// characters, so a note pasted out of Word carrying U+000B reaches the server,
// raises CustomerValidationError, and its ENGLISH message renders into a Hebrew
// console. This guard is the only thing that makes "the client never produces a
// VALIDATION_ERROR" true rather than hopeful.
export function validateCustomerNotes(notes: string): string | null {
  if (notes.length > MAX_CUSTOMER_NOTES_LENGTH) {
    return "customers.notesTooLong";
  }
  if (CONTROL_CHARS_EXCEPT_WS.test(notes)) {
    return "customers.notesInvalid";
  }
  return null;
}
