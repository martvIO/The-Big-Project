// Typed fetch helper for the /manage owner console. Wire format is the
// backend's snake_case verbatim (no case conversion layer — the OpenAPI
// client wrapper is F10 scope). Cookies carry the session, so every call
// sends credentials: "include"; errors arrive in the house shape
// {"error": {"code", "message"}} and are surfaced as ApiError.

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

export function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : FALLBACK_ERROR_MESSAGE;
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
  const { method = "GET", body } = init;
  const response = await fetch(path, {
    method,
    credentials: "include",
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
  return (await response.json()) as T;
}

// --- wire types (mirror backend/app/boutique/schemas.py + app/auth/schemas.py) ---

export interface Staff {
  id: string;
  email: string;
  display_name: string;
  role: string;
}

export interface ProfileSettings {
  phone?: string;
  address?: string;
  description?: string;
  maps_url?: string;
  essence?: string;
  instagram?: string;
}

export interface ToggleSettings {
  deposits_enabled?: boolean;
  brides_only?: boolean;
}

export interface Settings {
  profile: ProfileSettings;
  toggles: ToggleSettings;
}

export interface UpdateSettingsRequest {
  profile?: ProfileSettings;
  toggles?: ToggleSettings;
}

export type AppointmentAudience = "all" | "brides_only";

export interface AppointmentTypeInput {
  name: string;
  duration_minutes: number;
  audience: AppointmentAudience;
  deposit_required: boolean;
  deposit_amount_agorot: number | null;
  sort_order: number;
}

export interface AppointmentType extends AppointmentTypeInput {
  id: string;
}

export interface WeeklyRuleInput {
  day_of_week: number;
  open_time: string;
  close_time: string;
  capacity: number;
}

export interface AvailabilityRule extends WeeklyRuleInput {
  id: string;
}

export interface AvailabilityExceptionInput {
  date: string;
  open_time: string | null;
  close_time: string | null;
  note: string | null;
}

export interface AvailabilityException extends AvailabilityExceptionInput {
  id: string;
}

export interface Availability {
  rules: AvailabilityRule[];
  exceptions: AvailabilityException[];
}

export interface CreateTermsRequest {
  terms_text: string;
  refundable_until_hours_before: number;
  forfeit_percent: number;
}

export interface TermsVersion extends CreateTermsRequest {
  id: string;
  version: number;
  created_by: string;
  created_at: string;
}

export interface TermsHistory {
  current: TermsVersion | null;
  versions: TermsVersion[];
  total: number;
  offset: number;
  limit: number;
}

export interface OkResponse {
  ok: boolean;
}

// --- catalog wire types (mirror backend/app/catalog/schemas.py) ---

export interface Media {
  id: string;
  sort_order: number;
  content_type: string;
  byte_size: number;
  // null when no bucket is configured — reads keep working, only media writes
  // answer 503.
  url: string | null;
  url_expires_at: string | null;
}

export interface VariantInput {
  size_label: string;
  quantity: number;
  sort_order: number;
}

export interface Variant extends VariantInput {
  id: string;
}

export interface DressInput {
  name: string;
  description: string | null;
  price_agorot: number | null;
  price_visible: boolean;
  reserved: boolean;
  sort_order: number;
}

export interface Dress extends DressInput {
  id: string;
  // Derived server-side from the variant rows, never stored.
  out_of_stock: boolean;
  total_quantity: number;
  variant_count: number;
  media_count: number;
  cover: Media | null;
  archived: boolean;
  created_at: string;
  updated_at: string | null;
}

export interface DressDetail extends Dress {
  variants: Variant[];
  media: Media[];
  media_uploads_enabled: boolean;
  media_slots_remaining: number;
}

export interface DressList {
  items: Dress[];
  total: number;
  offset: number;
  limit: number;
}

export interface DressListQuery {
  offset: number;
  limit: number;
  search: string;
  archived: boolean;
}

export interface PresignRequest {
  content_type: string;
  byte_size: number;
}

export interface PresignResponse {
  media_id: string;
  url: string;
  // Bearer material for 300s: never logged, never shown, never persisted.
  fields: Record<string, string>;
  expires_in: number;
  max_bytes: number;
}

/**
 * Post a file straight to object storage under a server-minted POST policy.
 *
 * Deliberately NOT routed through apiFetch: that helper sends the session
 * cookie and parses a JSON error envelope, while this request must send no
 * credentials and never parse a body in either direction (S3 answers 204 with
 * an empty body on success and XML on error).
 *
 * There is no headers object at all — the browser has to set the multipart
 * boundary itself, and Content-Type travels as a form *field*, not a header.
 * Fields go in first in iteration order and `file` goes last, because S3
 * ignores everything after `file`.
 */
export async function uploadToStorage(presign: PresignResponse, file: File): Promise<void> {
  const form = new FormData();
  for (const [name, value] of Object.entries(presign.fields)) {
    form.append(name, value);
  }
  form.append("file", file);

  let response: Response;
  try {
    response = await fetch(presign.url, { method: "POST", body: form, credentials: "omit" });
  } catch {
    // fetch REJECTS with a bare TypeError when the network is down or a CORS
    // preflight fails — it does not return a non-ok Response.
    throw new ApiError(
      0,
      "UPLOAD_BLOCKED",
      "לא ניתן היה להעלות את הקובץ. בדקי את החיבור ונסי שוב.",
    );
  }
  if (!response.ok) {
    throw new ApiError(response.status, "UPLOAD_FAILED", "העלאת הקובץ נכשלה. נסי שוב.");
  }
}

// --- owner booking wire types (mirror backend/app/booking/schemas.py) ---

export interface OwnerBookingRow {
  id: string;
  starts_at: string;
  status: string;
  attendance_confirmed_at: string | null;
  customer_name: string;
  appointment_type_name: string;
  dress_name: string | null;
}

export interface OwnerBookingListResponse {
  items: OwnerBookingRow[];
  total: number;
  offset: number;
  limit: number;
}

// The row's fields plus the ones the owner opened the booking for: the list is
// deliberately without the phone and the free text (D18), so it is not a bulk
// PII export of the boutique's whole day.
export interface OwnerBookingDetail extends OwnerBookingRow {
  customer_phone: string;
  notes: string | null;
  dress_id: string | null;
  dress_size: string | null;
  seat_index: number;
  created_at: string;
  terms_version_accepted: number;
  terms_accepted_at: string;
  cancelled_at: string | null;
  cancelled_by: string | null;
  // `manage_token_hash` is the stored half of a live control credential and
  // never reaches the wire — only whether one exists.
  manage_link_issued: boolean;
}

export interface OwnerSlotRow {
  starts_at: string;
  capacity: number;
  // The owner's grid carries capacity/remaining, which the anonymous storefront
  // grid fences off: she legitimately needs to know whether a reschedule target
  // is about to take the last place (D6).
  remaining: number;
}

export interface OwnerSlotListResponse {
  slots: OwnerSlotRow[];
}

export interface OwnerBookingListQuery {
  // A Jerusalem calendar date, YYYY-MM-DD. Required — the console has no
  // all-bookings view (D17).
  date: string;
  offset: number;
  limit: number;
}

function bookingPath(bookingId: string): string {
  return `/manage/bookings/${encodeURIComponent(bookingId)}`;
}

function dressPath(dressId: string): string {
  return `/manage/dresses/${encodeURIComponent(dressId)}`;
}

function mediaPath(dressId: string, mediaId: string): string {
  return `${dressPath(dressId)}/media/${encodeURIComponent(mediaId)}`;
}

// --- staff wire types (mirror backend/app/auth/schemas.py) ---

export type StaffRole = "owner" | "shift_manager";

export interface StaffMember {
  id: string;
  email: string;
  display_name: string;
  role: StaffRole;
  created_at: string;
}

// mirrors backend/app/payments/schemas.py::GatewayStatusResponse — the WHOLE
// response, in every state. There is no ciphertext, no key_ref, no
// validation_error and no field value on it, ever.
//
// `configured` is PLATFORM-level and `connected` is TENANT-level: two booleans
// because the two facts have different owners and different remedies — the
// operator fixes one, the boutique fixes the other.
//
// `credential_fields` is the adapter's own declared shape. Rendering the form
// from it is what lets a future real-provider adapter change the field set with
// NO frontend change at all.
export interface GatewayStatus {
  provider: string | null;
  configured: boolean;
  connected: boolean;
  status: "valid" | "invalid" | null;
  last_validated_at: string | null;
  credential_fields: string[];
}

export interface CreateStaffRequest {
  email: string;
  display_name: string;
  role: StaffRole;
  password: string;
}

// Every field optional. `email` is absent on purpose: the unique index is
// partial on deleted_at IS NULL, so a typo'd or changed address is fixed by
// deactivate + re-create, and a login identity must not move under a live
// session. `current_password` is required only when the acting owner changes her
// OWN password.
export interface UpdateStaffRequest {
  display_name?: string;
  role?: StaffRole;
  password?: string;
  current_password?: string;
}

function staffPath(staffId: string): string {
  return `/manage/staff/${encodeURIComponent(staffId)}`;
}

// --- endpoints ---

export const api = {
  login(email: string, password: string): Promise<Staff> {
    return apiFetch("/manage/auth/login", { method: "POST", body: { email, password } });
  },
  logout(): Promise<OkResponse> {
    return apiFetch("/manage/auth/logout", { method: "POST" });
  },
  me(): Promise<Staff> {
    return apiFetch("/manage/auth/me");
  },

  getSettings(): Promise<Settings> {
    return apiFetch("/manage/settings");
  },
  updateSettings(body: UpdateSettingsRequest): Promise<Settings> {
    return apiFetch("/manage/settings", { method: "PUT", body });
  },

  listAppointmentTypes(): Promise<AppointmentType[]> {
    return apiFetch("/manage/appointment-types");
  },
  createAppointmentType(body: AppointmentTypeInput): Promise<AppointmentType> {
    return apiFetch("/manage/appointment-types", { method: "POST", body });
  },
  updateAppointmentType(id: string, body: AppointmentTypeInput): Promise<AppointmentType> {
    return apiFetch(`/manage/appointment-types/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body,
    });
  },
  archiveAppointmentType(id: string): Promise<OkResponse> {
    return apiFetch(`/manage/appointment-types/${encodeURIComponent(id)}`, { method: "DELETE" });
  },

  getAvailability(): Promise<Availability> {
    return apiFetch("/manage/availability");
  },
  replaceWeeklyRules(rules: WeeklyRuleInput[]): Promise<AvailabilityRule[]> {
    return apiFetch("/manage/availability/rules", { method: "PUT", body: { rules } });
  },
  addAvailabilityException(body: AvailabilityExceptionInput): Promise<AvailabilityException> {
    return apiFetch("/manage/availability/exceptions", { method: "POST", body });
  },
  removeAvailabilityException(id: string): Promise<OkResponse> {
    return apiFetch(`/manage/availability/exceptions/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
  },

  getTerms(): Promise<TermsHistory> {
    return apiFetch("/manage/terms");
  },
  createTermsVersion(body: CreateTermsRequest): Promise<TermsVersion> {
    return apiFetch("/manage/terms", { method: "POST", body });
  },

  listDresses(query: DressListQuery): Promise<DressList> {
    const params = new URLSearchParams({
      offset: String(query.offset),
      limit: String(query.limit),
      archived: String(query.archived),
    });
    if (query.search.trim() !== "") {
      params.set("search", query.search.trim());
    }
    return apiFetch(`/manage/dresses?${params.toString()}`);
  },
  getDress(dressId: string): Promise<DressDetail> {
    return apiFetch(dressPath(dressId));
  },
  createDress(body: DressInput): Promise<Dress> {
    return apiFetch("/manage/dresses", { method: "POST", body });
  },
  // Full replace: every field is sent, so an omitted key can never silently
  // clear a value server-side.
  updateDress(dressId: string, body: DressInput): Promise<Dress> {
    return apiFetch(dressPath(dressId), { method: "PATCH", body });
  },
  archiveDress(dressId: string): Promise<OkResponse> {
    return apiFetch(dressPath(dressId), { method: "DELETE" });
  },
  restoreDress(dressId: string): Promise<DressDetail> {
    return apiFetch(`${dressPath(dressId)}/restore`, { method: "POST" });
  },
  replaceVariants(dressId: string, variants: VariantInput[]): Promise<DressDetail> {
    return apiFetch(`${dressPath(dressId)}/variants`, { method: "PUT", body: { variants } });
  },
  presignMedia(dressId: string, body: PresignRequest): Promise<PresignResponse> {
    return apiFetch(`${dressPath(dressId)}/media/presign`, { method: "POST", body });
  },
  confirmMedia(dressId: string, mediaId: string): Promise<DressDetail> {
    return apiFetch(`${mediaPath(dressId, mediaId)}/confirm`, { method: "POST" });
  },
  // Accepts a pending row too — that is the client's abort/cleanup path after a
  // failed upload, and it frees the gallery slot immediately.
  deleteMedia(dressId: string, mediaId: string): Promise<DressDetail> {
    return apiFetch(mediaPath(dressId, mediaId), { method: "DELETE" });
  },
  reorderMedia(dressId: string, mediaIds: string[]): Promise<DressDetail> {
    return apiFetch(`${dressPath(dressId)}/media/order`, {
      method: "PUT",
      body: { media_ids: mediaIds },
    });
  },

  listBookings(query: OwnerBookingListQuery): Promise<OwnerBookingListResponse> {
    const params = new URLSearchParams({
      date: query.date,
      offset: String(query.offset),
      limit: String(query.limit),
    });
    return apiFetch(`/manage/bookings?${params.toString()}`);
  },
  getBooking(bookingId: string): Promise<OwnerBookingDetail> {
    return apiFetch(bookingPath(bookingId));
  },
  // Four verb sub-paths rather than one PATCH with a status field (D7): the
  // guards and the side effects differ per transition.
  confirmBooking(bookingId: string): Promise<OwnerBookingDetail> {
    return apiFetch(`${bookingPath(bookingId)}/confirm`, { method: "POST" });
  },
  cancelBooking(bookingId: string): Promise<OwnerBookingDetail> {
    return apiFetch(`${bookingPath(bookingId)}/cancel`, { method: "POST" });
  },
  noShowBooking(bookingId: string): Promise<OwnerBookingDetail> {
    return apiFetch(`${bookingPath(bookingId)}/no-show`, { method: "POST" });
  },
  completeBooking(bookingId: string): Promise<OwnerBookingDetail> {
    return apiFetch(`${bookingPath(bookingId)}/complete`, { method: "POST" });
  },
  rescheduleBooking(bookingId: string, startsAt: string): Promise<OwnerBookingDetail> {
    return apiFetch(`${bookingPath(bookingId)}/reschedule`, {
      method: "POST",
      body: { starts_at: startsAt },
    });
  },
  // The phone travels EXACTLY as typed. There is no client-side normalizer
  // (D20): a third hand-written copy of normalize_israeli_mobile could refuse a
  // legal Israeli number, or show her an E.164 different from the one actually
  // stored on the row whose SMS link is about to rotate. The server's 400 is the
  // only authority.
  correctBookingPhone(bookingId: string, phone: string): Promise<OwnerBookingDetail> {
    return apiFetch(`${bookingPath(bookingId)}/phone`, { method: "POST", body: { phone } });
  },
  resendBookingLink(bookingId: string): Promise<OwnerBookingDetail> {
    return apiFetch(`${bookingPath(bookingId)}/resend-link`, { method: "POST" });
  },
  // `from`/`to` are the router's query aliases, not the Python parameter names.
  listManageSlots(from: string, to: string): Promise<OwnerSlotListResponse> {
    const params = new URLSearchParams({ from, to });
    return apiFetch(`/manage/slots?${params.toString()}`);
  },

  // Owner-only, all four: the server's RoleGate is the control, and a shift
  // manager who reached these would get the generic 403.
  listStaff(): Promise<StaffMember[]> {
    return apiFetch("/manage/staff");
  },
  createStaff(body: CreateStaffRequest): Promise<StaffMember> {
    return apiFetch("/manage/staff", { method: "POST", body });
  },
  // Partial by design — an omitted key means "unchanged", and the server reads
  // an all-unchanged patch as a no-op that writes no audit row.
  updateStaff(staffId: string, body: UpdateStaffRequest): Promise<StaffMember> {
    return apiFetch(staffPath(staffId), { method: "PATCH", body });
  },
  deactivateStaff(staffId: string): Promise<OkResponse> {
    return apiFetch(staffPath(staffId), { method: "DELETE" });
  },

  // Owner-only, all four — the first router in the backend that is owner-only
  // IN FULL, the read included: whether the boutique can take money is itself
  // disclosure. There is deliberately NO read path for a credential value, so
  // the form always starts empty and a save always sends the complete set.
  gatewayStatus(): Promise<GatewayStatus> {
    return apiFetch("/manage/gateway");
  },
  setGatewayCredentials(fields: Record<string, string>): Promise<GatewayStatus> {
    return apiFetch("/manage/gateway/credentials", { method: "PUT", body: { fields } });
  },
  validateGateway(): Promise<GatewayStatus> {
    return apiFetch("/manage/gateway/validate", { method: "POST" });
  },
  disconnectGateway(): Promise<GatewayStatus> {
    return apiFetch("/manage/gateway/credentials", { method: "DELETE" });
  },
};
