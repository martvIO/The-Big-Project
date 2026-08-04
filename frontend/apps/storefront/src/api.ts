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
    // A confirm-attendance or cancel against an unpaid deposit hold. Its own
    // code on the wire rather than a reuse of BOOKING_CANCELLED, so it gets its
    // own string here: an unpaid hold is neither cancelled nor standing, and the
    // cancelled copy would tell a bride mid-checkout her appointment is gone.
    case "BOOKING_AWAITING_PAYMENT":
      return "errors.bookingAwaitingPayment";
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
  // F20's three statutory documents, already resolved server-side: a boutique's
  // override where she wrote one, the platform Hebrew where she did not.
  //
  // ⚠ NO NEW ENDPOINT, and that is a decision rather than an omission. They ride
  // this response because `/privacy` and the booking form's `details` step render
  // the SAME `privacy_notice_text` — one fetch, one string, so a boutique that
  // edited her notice cannot end up with two versions of it on two surfaces. The
  // cost is ~6.8 KB of Hebrew on every storefront first paint, against a catalogue
  // page that ships dress imagery.
  //
  // ⚠ EACH MAY CONTAIN `{{boutique}}`, unsubstituted. The server ships the raw
  // text; `lib/privacyText.ts` is the only place that fills it in.
  privacy_notice_text: string;
  // The processor clause. Overridable, like the notice.
  privacy_dpa_text: string;
  // The sub-processor list. Platform-owned and structurally un-overridable
  // (Gate 1 Q3): `resolve_privacy` never reads it out of the tenant blob, so a
  // boutique may rewrite what she PROMISES about processing and may not misstate
  // WHO the processors are.
  privacy_subprocessors_text: string;
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
  // F20 / Communications Law §30A. REQUIRED on the wire even though the server
  // defaults it to `false`: an optional field is one a later refactor can drop
  // silently, and the value being sent on every booking is what makes «the box
  // is not pre-ticked» a property of the request rather than of a comment.
  marketing_consent: boolean;
}

export interface BookingCreateResponse {
  id: string;
  starts_at: string;
  // "confirmed" | "pending_payment" — `pending_payment` EXACTLY when
  // `deposit_due`, a seat held with the money not yet in.
  status: string;
  appointment_type_name: string;
  dress_name: string | null;
  dress_size: string | null;
  // Is money owed, and where does she pay it. Both nullable fields stay null
  // unless a deposit is due — including on the path where the gateway was
  // unreachable and the booking stands with no deposit taken, which is why the
  // flow branches on `deposit_due` and never on `deposit_required`.
  deposit_due: boolean;
  redirect_url: string | null;
  // The POLL credential, deliberately NOT the manage token: the token is not in
  // this response, the deposit path suppresses the SMS that would carry it, and
  // confirming rotates its hash — so a token-keyed poll would start 404-ing at
  // precisely the moment it should answer "paid". This id is already
  // client-visible by construction (it is embedded in the hosted-page URL the
  // browser is about to visit) and possession of it authorises nothing but a
  // status read.
  payment_session_id: string | null;
}

export interface PaymentStatusResponse {
  // The BOOKING's status is what makes the confirmation screen true. The
  // webhook settles `payments` in one transaction and confirms the booking in a
  // second, so `payment_status: "paid"` with the booking still held is a real,
  // recoverable state and not a confirmation.
  booking_status: string;
  // "pending" | "paid" | "failed" | "expired" | …
  payment_status: string;
  paid_at: string | null;
  // Her card was refused and the hold is still hers to retry. Its own field
  // because `payment_status` cannot carry it: a declined hold is left `pending`
  // on purpose, so the seat stays held until the sweeper's own clock frees it
  // and a retried card settles the same hold rather than opening a second one.
  declined: boolean;
}

// --- manage wire types (mirror backend/app/booking/schemas.py) ---
//
// NOTE what is absent and must stay absent: the booking id, the customer's name
// and phone, the seat index and the notes. The manage link is possession-auth, so
// the payload carries the appointment's facts and no PII beyond them.

export interface ManageBookingFacts {
  starts_at: string;
  // "confirmed" | "cancelled" | "no_show" | "completed" | "pending_payment".
  // The page branches on cancelled and on pending_payment — an unpaid hold is
  // neither of the other two, and rendering it as an appointment that stands
  // put a live cancel button on a booking the server 409s every verb on.
  status: string;
  // null until she taps אישור הגעה; set once and never moved.
  attendance_confirmed_at: string | null;
  appointment_type_name: string;
  dress_name: string | null;
  dress_size: string | null;
  // Whether this appointment took a deposit. A BOOLEAN and never the sum — the
  // payload is possession-authed and carries no money fact about a person it
  // refuses to name. It is what the cancel consequence branches on, because
  // `status` cannot answer it: a CONFIRMED booking paid weeks ago has a deposit
  // too, and "cancelling is free" is false for it.
  deposit_taken: boolean;
}

export interface ManagePolicy {
  // From the version she ACCEPTED, never the current one — a republished policy
  // must not change the terms of an appointment already agreed to.
  refundable_until_hours_before: number;
  forfeit_percent: number;
}

export interface ManageBoutique {
  name: string;
  phone: string | null;
  address: string | null;
  maps_url: string | null;
}

export interface ManageBookingResponse {
  booking: ManageBookingFacts;
  // null only if the accepted terms row has gone; the page then renders the
  // cancel step without the window sentence rather than inventing a number.
  policy: ManagePolicy | null;
  boutique: ManageBoutique;
}

// --- walk-in queue wire types (mirror backend/app/queue/schemas.py) ---

export interface CheckinCreateRequest {
  name: string;
  // Any form normalize_israeli_mobile accepts; validation.ts normalises before
  // this leaves the page.
  phone: string;
  // "bride" | "evening" — a closed two-value set the backend CHECK pins.
  visit_type: string;
  // Absent is false and unchecked is the default on the form: she stays a person
  // in a queue rather than a marketing contact unless she says otherwise.
  marketing_opt_in: boolean;
}

// The WHOLE body of BOTH check-in routes, and it is four fields.
//
// The create answers this and only this, 201, every time — no envelope, no null
// branch. That is the security property, not a simplification: the response is
// identical in shape, status and content whether or not that phone was already
// in this boutique's queue, so a stranger who submits a woman's mobile receives
// a ticket of his own and learns nothing whatsoever about her.
//
// NOTE what is absent and must stay absent: her name, her phone, her visit type,
// created_at, and every operator provenance column — tenant_id, queue_day,
// skip_count, requeued_at. Nothing about any other ticket, ever.
export interface TicketView {
  // The capability. Issued exactly once, at creation, to the creating device.
  id: string;
  // "waiting" | "in_service" | "done" | "removed". The last two are terminal and
  // are what stop the position page's poll.
  status: string;
  // 1-based among this ticket's own queue day's waiting tickets; null unless the
  // ticket is itself waiting.
  position: number | null;
  // Set once a manager calls her forward. The only reason the page reads it: it
  // is what lets the screen say "go to the counter" instead of showing 1 forever.
  called_at: string | null;
}

// One row on a television seen from three to five metres by a room full of
// strangers, on an endpoint anyone on the internet can call.
//
// THREE FIELDS, and there is no ticket id — there must never be one. The id is
// F33's capability, issued exactly once at creation; a board that carried ids
// would hand every passer-by a live, pollable capability over five women's
// visits at a time, refreshed every five seconds, forever.
export interface QueueBoardEntry {
  // 1-based, in the board's own list order. Also the React key: a name would
  // collide on two women called נועה and on one woman holding two tickets.
  position: number;
  // Derived and truncated server-side. The stored name never reaches the wire.
  first_name: string;
  // A boolean, not called_at. The wall needs to know WHETHER, not WHEN —
  // shipping the instant would let anyone watching time how long a named woman
  // has stood at the counter.
  called: boolean;
}

export interface QueueBoardView {
  // Capped server-side. The client asserts no count anywhere, so raising the cap
  // is a backend change with no frontend edit.
  entries: QueueBoardEntry[];
  // The UNTRUNCATED count the overflow line subtracts from. It counts waiting
  // TICKETS rather than women: one woman who re-scanned the code is two rows and
  // counts twice, and the board must not deduplicate — the only key that would
  // is her phone, and no read here is keyed on it.
  waiting_total: number;
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
  // The pay step's poll. POST for a read, the /booking/lookup precedent: a GET
  // would put the session id into every access log, proxy trace and Referer
  // header on the path.
  paymentStatus(paymentSessionId: string): Promise<PaymentStatusResponse> {
    return apiFetch("/storefront/booking/payment-status", {
      method: "POST",
      body: { payment_session_id: paymentSessionId },
    });
  },

  // All three take the manage token in the BODY and answer the SAME shape, so
  // the page re-renders every state from one response type. POST even for the
  // lookup: a GET would put a live credential in the query string, and from
  // there into every access log, proxy trace and Referer header on the path.
  lookupBooking(token: string): Promise<ManageBookingResponse> {
    return apiFetch("/storefront/booking/lookup", { method: "POST", body: { token } });
  },
  confirmAttendance(token: string): Promise<ManageBookingResponse> {
    return apiFetch("/storefront/booking/confirm-attendance", {
      method: "POST",
      body: { token },
    });
  },
  cancelBooking(token: string): Promise<ManageBookingResponse> {
    return apiFetch("/storefront/booking/cancel", { method: "POST", body: { token } });
  },

  // Both check-in routes are POSTs, the read included, and both answer the same
  // TicketView. The read is a POST for the reason the manage lookup is: the
  // ticket id IS the capability, and a GET would put it in the query string and
  // from there into every access log, proxy trace and Referer header on the
  // path — once every five seconds for the length of her visit.
  createCheckin(body: CheckinCreateRequest): Promise<TicketView> {
    return apiFetch("/storefront/checkin", { method: "POST", body });
  },
  getQueuePosition(ticketId: string): Promise<TicketView> {
    return apiFetch("/storefront/checkin/position", {
      method: "POST",
      body: { ticket_id: ticketId },
    });
  },

  // F59's wall board. A POST for a read like its two check-in siblings, but NOT
  // for their reason — this request carries no capability and no secret at all,
  // and takes no body whatsoever. It is a POST because the backend's public-read
  // guard derives its route list over every GET under /storefront and asserts
  // the shared storefront budget throttles each one; the board holds its own
  // budget, so a GET here reddens a guard covering six shipped reads. The two
  // ways out are worse: share the catalog's budget, or weaken that guard.
  getQueueBoard(): Promise<QueueBoardView> {
    return apiFetch("/storefront/queue", { method: "POST" });
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
