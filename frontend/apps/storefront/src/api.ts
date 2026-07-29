// Typed fetch helper for the public storefront: the catalog/identity GETs plus
// the booking-flow mutations (OTP send/verify, booking create). Wire format is
// the backend's snake_case verbatim; errors arrive in the house shape
// {"error": {"code", "message"}} and are surfaced as ApiError.
//
// Deliberately a local copy of apps/manage's helper rather than a shared
// package: the two differ on credentials and on error rendering, and hoisting
// them into @boutique/api-client is a cleanup with no consumer pressure yet.

export const FALLBACK_ERROR_MESSAGE = "אירעה שגיאה בלתי צפויה. נסי שוב.";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

// An unknown id, an archived (soft-deleted) dress and another tenant's dress are
// all indistinguishable 404s by design — every one of them renders
// "השמלה כבר לא זמינה".
//
// A malformed id is the same miss. /dress/xyz out of a mistyped or truncated
// link fails FastAPI's UUID coercion, which the platform normalises to
// 400 VALIDATION_ERROR — semantically "no such dress", not "the server broke".
// Without this it rendered dress.error plus a Retry button that re-issues the
// same 400 forever.
//
// DRESS-DETAIL ONLY. On the booking POST a 400 VALIDATION_ERROR is a form
// problem, not a vanished dress — the booking flow keys off errorMessageKey
// and must never consult this helper (pinned in api.test.ts).
export function isNotFound(error: unknown): boolean {
  if (!(error instanceof ApiError)) return false;
  return error.status === 404 || (error.status === 400 && error.code === "VALIDATION_ERROR");
}

// Every backend message is English ("No active boutique at this address.",
// "Resource not found.", "Too many attempts. Try again later."). Rendering
// ApiError.message would paint English onto a Hebrew-only page for a suspended
// tenant, an unknown slug, an archived dress or a throttle trip. So the code —
// never the message — selects an i18n key, and anything unmapped falls back to
// real Hebrew.
export function errorMessageKey(error: unknown): string {
  if (!(error instanceof ApiError)) return "errors.unknown";
  switch (error.code) {
    case "TENANT_NOT_FOUND":
      return "errors.tenantNotFound";
    case "NOT_FOUND":
      return "errors.notFound";
    case "TOO_MANY_ATTEMPTS":
      return "errors.tooManyAttempts";
    case "VALIDATION_ERROR":
      return "errors.validation";
    case "SLOT_UNAVAILABLE":
      return "errors.slotUnavailable";
    case "TERMS_STALE":
      return "errors.termsStale";
    case "OTP_INVALID":
      return "errors.otpInvalid";
    case "OTP_EXPIRED":
      return "errors.otpExpired";
    case "PHONE_NOT_VERIFIED":
      return "errors.phoneNotVerified";
    // One string for both codes: to the visitor "misconfigured" and "provider
    // down" are the same dead end, and the way out is the phone either way.
    case "SMS_NOT_CONFIGURED":
    case "SMS_UNAVAILABLE":
      return "errors.smsUnavailable";
    default:
      return "errors.unknown";
  }
}

export function errorMessage(error: unknown, t: (key: string) => string): string {
  return t(errorMessageKey(error));
}

/**
 * The same mapping, but a surface-specific fallback replaces the generic
 * "something went wrong" when the code carries no useful information.
 *
 * A throttle trip should say so; a dropped connection on the catalog should say
 * "we could not load the collection", not a generic apology.
 */
export function errorMessageOr(
  error: unknown,
  t: (key: string) => string,
  fallbackKey: string,
): string {
  const key = errorMessageKey(error);
  return t(key === "errors.unknown" ? fallbackKey : key);
}

function extractError(body: unknown): { code: string; message: string } | null {
  if (typeof body !== "object" || body === null) {
    return null;
  }
  const envelope = (body as { error?: unknown }).error;
  if (typeof envelope !== "object" || envelope === null) {
    return null;
  }
  const { code, message } = envelope as { code?: unknown; message?: unknown };
  if (typeof message !== "string") {
    return null;
  }
  return { code: typeof code === "string" ? code : "UNKNOWN", message };
}

export async function apiFetch<T>(
  path: string,
  init: { method?: string; body?: unknown } = {},
): Promise<T> {
  // credentials: "omit" — on the mutations too, by contract. The booking
  // surface is cookie-blind: the credential is the verification token in the
  // body, and a backend test asserts an owner cookie changes nothing.
  const { method = "GET", body } = init;
  const response = await fetch(path, {
    method,
    credentials: "omit",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    let extracted: { code: string; message: string } | null = null;
    try {
      extracted = extractError(await response.json());
    } catch {
      // Non-JSON error body (proxy/HTML page) — fall through to the fallback.
    }
    throw new ApiError(
      response.status,
      extracted?.code ?? "UNKNOWN",
      extracted?.message ?? FALLBACK_ERROR_MESSAGE,
    );
  }
  // /otp/send answers 204 with no body, deliberately — nothing to parse.
  if (response.status === 204) {
    return undefined as T;
  }
  // A 200 whose body is not JSON must be an ApiError, not a raw SyntaxError.
  // This is not hypothetical: under the SPA history fallback a fetch to
  // /storefront/dresses with no backend behind the proxy answers 200 text/html,
  // and that is exactly the state the blocking e2e job runs in. An unhandled
  // SyntaxError escapes the page's catch and blanks the screen.
  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError(response.status, "UNKNOWN", FALLBACK_ERROR_MESSAGE);
  }
}

// --- wire types (mirror backend/app/storefront/schemas.py) ---
//
// Every field below is always present; nullable ones serialise as null, never
// omitted. NOTE what is absent and must stay absent: price_visible, quantity,
// out_of_stock, total_quantity, variant_count, archived, media_uploads_enabled,
// media_slots_remaining, capacity, sort_order, timestamps, toggles. Those are
// manage-only, and the backend never even computes the stock ones.

export interface StorefrontMedia {
  // Presigned GET, 900s TTL — bearer material. null means no bucket configured
  // or signing failed.
  url: string | null;
  url_expires_at: string | null;
}

export interface StorefrontDress {
  id: string;
  name: string;
  // null = hidden by the owner OR never set. The storefront cannot tell the two
  // apart, by design, and renders both as "מחיר בתיאום".
  price_agorot: number | null;
  // The only badge on the storefront. There is no out-of-stock badge.
  reserved: boolean;
  cover: StorefrontMedia | null;
}

export interface DressListResponse {
  items: StorefrontDress[];
  total: number;
  offset: number;
  limit: number;
}

export interface SizeChip {
  size_label: string;
  // quantity > 0, folded server-side. Raw counts are boutique-confidential and
  // never reach the wire.
  available: boolean;
}

export interface StorefrontDetail {
  id: string;
  name: string;
  description: string | null;
  price_agorot: number | null;
  reserved: boolean;
  sizes: SizeChip[];
  // Ready photos in gallery order; media[0] is the cover.
  media: StorefrontMedia[];
}

export interface HoursRow {
  // 0 = Sunday … 6 = Saturday (Israeli week).
  day_of_week: number;
  open_time: string; // "10:00:00"
  close_time: string; // "19:00:00"
}

export interface ExceptionRow {
  date: string; // "2026-08-26"
  // Both null = closed all day; both set = special hours.
  open_time: string | null;
  close_time: string | null;
  note: string | null;
}

// FLAT, matching the backend: every field here is public identity the design
// renders in one header block.
export interface BoutiqueResponse {
  // The tenant's display name, not the slug. This is the <h1>.
  name: string;
  essence: string | null;
  description: string | null;
  phone: string | null;
  address: string | null;
  maps_url: string | null;
  // Stored without the leading @; ContactPanel builds instagram.com/{handle}.
  instagram: string | null;
  // ONE ROW PER WINDOW, not per day — a boutique may have a lunch break. The
  // client groups by day_of_week; see lib/hoursText.ts.
  hours: HoursRow[];
  exceptions: ExceptionRow[];
}

// --- booking wire types (mirror backend/app/storefront/schemas.py,
// app/notifications/schemas.py and app/booking/schemas.py) ---

export interface StorefrontTerms {
  // Echoed back as terms_version on the booking POST — the version she accepted.
  version: number;
  terms_text: string;
  refundable_until_hours_before: number;
  forfeit_percent: number;
}

export interface AppointmentTypeRow {
  id: string;
  name: string;
  duration_minutes: number;
  // "all" | "brides_only" — disclosed so the UI can label the option; nothing
  // public enforces it (an anonymous visitor cannot be classified as a bride).
  audience: string;
  deposit_required: boolean;
  deposit_amount_agorot: number | null;
}

export interface SlotRow {
  starts_at: string;
}

export interface SlotListResponse {
  // Start times only — no capacity, no remaining. Every slot returned is
  // bookable by construction.
  slots: SlotRow[];
}

export interface OtpVerifyResponse {
  // Bearer material: single-use, phone-bound, 600s TTL. Held in memory only.
  verification_token: string;
  expires_at: string;
}

export interface BookingCreateRequest {
  phone: string;
  verification_token: string;
  name: string;
  appointment_type_id: string;
  starts_at: string;
  terms_version: number;
  dress_id: string | null;
  dress_size: string | null;
  notes: string | null;
}

export interface BookingCreateResponse {
  id: string;
  starts_at: string;
  status: string;
  appointment_type_name: string;
  dress_name: string | null;
  dress_size: string | null;
}

// --- endpoints ---

export const api = {
  listDresses(offset = 0): Promise<DressListResponse> {
    return apiFetch(`/storefront/dresses?offset=${String(offset)}`);
  },
  getDress(dressId: string): Promise<StorefrontDetail> {
    return apiFetch(`/storefront/dresses/${encodeURIComponent(dressId)}`);
  },
  getBoutique(): Promise<BoutiqueResponse> {
    return apiFetch("/storefront/boutique");
  },

  getTerms(): Promise<StorefrontTerms> {
    return apiFetch("/storefront/terms");
  },
  listAppointmentTypes(): Promise<AppointmentTypeRow[]> {
    return apiFetch("/storefront/appointment-types");
  },
  // Boutique-calendar dates ("2026-08-01"), both bounds inclusive. Both are
  // optional and the booking flow sends neither: the server defaults to
  // today..+14d in Jerusalem, which is the window the date control is bounded
  // to. A client-computed window would read the device clock.
  listSlots(from?: string, to?: string): Promise<SlotListResponse> {
    const query = new URLSearchParams();
    if (from !== undefined) query.set("from", from);
    if (to !== undefined) query.set("to", to);
    const search = query.toString();
    return apiFetch(`/storefront/slots${search === "" ? "" : `?${search}`}`);
  },
  sendOtp(phone: string): Promise<void> {
    return apiFetch("/storefront/otp/send", { method: "POST", body: { phone } });
  },
  verifyOtp(phone: string, code: string): Promise<OtpVerifyResponse> {
    return apiFetch("/storefront/otp/verify", { method: "POST", body: { phone, code } });
  },
  createBooking(body: BookingCreateRequest): Promise<BookingCreateResponse> {
    return apiFetch("/storefront/bookings", { method: "POST", body });
  },
};

// The footer needs the boutique block on every page and the body needs it again
// on / and /about. One promise per page load covers both; unlike the dress
// endpoints this response carries no signed URLs, so there is nothing to go
// stale within a session. StorefrontLayout owns the single call — this memo is
// its implementation detail.
let boutiqueOnce: Promise<BoutiqueResponse> | null = null;

export function getBoutiqueOnce(): Promise<BoutiqueResponse> {
  boutiqueOnce ??= api.getBoutique().catch((error: unknown) => {
    // Drop the rejected promise, otherwise every retry replays the same failure.
    boutiqueOnce = null;
    throw error;
  });
  return boutiqueOnce;
}

export function resetBoutiqueCache(): void {
  boutiqueOnce = null;
}
