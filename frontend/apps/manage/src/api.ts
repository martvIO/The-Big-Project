// Typed fetch helper for the /manage owner console. Wire format is the
// backend's snake_case verbatim (no case conversion layer — the OpenAPI
// client wrapper is F10 scope). Cookies carry the session, so every call
// sends credentials: "include"; errors arrive in the house shape
// {"error": {"code", "message"}} and are surfaced as ApiError.

export const FALLBACK_ERROR_MESSAGE = "אירעה שגיאה בלתי צפויה. נסי שוב.";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  // F36 / D14. Set on the two occupancy 409s and NOWHERE ELSE — the ruling
  // requires the refusal to name the current occupant, and a second GET would
  // race the release it describes.
  //
  // ⚠ Typed `| undefined`, never `| null`, so the {"staff_display_name": null}
  // shape cannot be constructed at all: the occupant can release between the
  // index violation and the occupant read, and «{{name}} כבר בחדר הזה.»
  // rendering with an empty interpolation on a legally binding surface is worse
  // than a sentence that admits it does not know. The panel selects the
  // *Unknown string on the absence.
  readonly details?: Record<string, string>;

  constructor(status: number, code: string, message: string, details?: Record<string, string>) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : FALLBACK_ERROR_MESSAGE;
}

function extractError(
  body: unknown,
): { code: string; message: string; details?: Record<string, string> } | null {
  if (typeof body !== "object" || body === null) {
    return null;
  }
  const envelope = (body as { error?: unknown }).error;
  if (typeof envelope !== "object" || envelope === null) {
    return null;
  }
  const { code, message, details } = envelope as {
    code?: unknown;
    message?: unknown;
    details?: unknown;
  };
  if (typeof message !== "string") {
    return null;
  }
  return {
    code: typeof code === "string" ? code : "UNKNOWN",
    message,
    details:
      typeof details === "object" && details !== null
        ? (details as Record<string, string>)
        : undefined,
  };
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
    let extracted: ReturnType<typeof extractError> = null;
    try {
      extracted = extractError(await response.json());
    } catch {
      // Non-JSON error body (proxy/HTML page) — fall through to the fallback.
    }
    throw new ApiError(
      response.status,
      extracted?.code ?? "UNKNOWN",
      extracted?.message ?? FALLBACK_ERROR_MESSAGE,
      extracted?.details,
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
  // The arrival timestamp the board writes, null until a staffer taps (F34 D1:
  // a column, not a fifth status — arrival is orthogonal to what the booking
  // BECAME). It is on the ROW rather than the detail because the board only
  // ever reads the list, and OwnerBookingDetail inherits it by extending.
  checked_in_at: string | null;
  customer_name: string;
  appointment_type_name: string;
  dress_name: string | null;
  // F19 D18: the ONLY owner-facing payment surface in the product, on the list
  // she already loads every morning — no new route, no nav row. `paid` on a
  // `cancelled` booking is the action-needed marker (MD1's reschedule is the
  // button behind it), and `failed` is MD4's "booked without a deposit, the
  // provider was unavailable". Null wherever no payment row exists.
  payment_status: string | null;
  // F19 A1/D16: COMPUTED by the server from the accepted terms version against
  // `starts_at`, never stored — F19 writes no refund row anywhere, because the
  // port ships no refund(). Integer agorot on the wire (D15); the division by
  // 100 happens once, inside <Price>, at render.
  refund_due_agorot: number | null;
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

// Every F36 path's second segment is `floor`, which is why vite.config.ts's
// manage proxy alternation needs no edit — mounting the registry at
// /manage/rooms would have cost one.
function roomPath(roomId: string): string {
  return `/manage/floor/rooms/${encodeURIComponent(roomId)}`;
}

function assignmentPath(assignmentId: string): string {
  return `/manage/floor/assignments/${encodeURIComponent(assignmentId)}`;
}

// F58's three row verbs. ⚠ `/manage/FLOOR/queue/...` and not `/manage/queue/...`
// — every path's second segment has to stay `floor` or the manage dev proxy's
// alternation needs an edit, and a mismatch there breaks ONLY a developer's
// machine while production, CI and the whole suite stay green, serving the SPA
// shell where the API should be.
function queuePath(ticketId: string): string {
  return `/manage/floor/queue/${encodeURIComponent(ticketId)}`;
}

// F37's five paths keep the same second segment for the same reason: the manage
// dev proxy's alternation names `floor` and mounting at /manage/sos would have
// cost an edit to vite.config.ts.
function sosPath(alertId: string): string {
  return `/manage/floor/sos/${encodeURIComponent(alertId)}`;
}

// --- staff wire types (mirror backend/app/auth/schemas.py) ---

// F57 widened this to five. StaffMember, CreateStaffRequest and
// UpdateStaffRequest all reference it, so they widen with no edit of their own —
// and ROLE_LABEL_KEY in lib/roles.ts is typed Record<StaffRole, string>, so a
// sixth member added here without a label is a compile error rather than a
// mislabelled row.
export type StaffRole =
  | "owner"
  | "shift_manager"
  | "reception"
  | "sales_assistant"
  | "seamstress";

// --- floor wire types (mirror backend/app/floor/schemas.py) ---

// Derived on read, never stored. `break` comes from break_started_at and
// `occupied` from a live fitting-room assignment, and F36's D12 makes OCCUPIED
// WIN: a staffer standing in room 2 who forgot to end a break reads «תפוסה».
//
// ⚠ `status` is therefore a DISPLAY PRECEDENCE and not the break fact. The
// break fact is `break_started_at !== null` — see FloorPanel's `onBreak`.
export type StaffCardStatus = "available" | "break" | "occupied";

export interface StaffCard {
  id: string;
  display_name: string;
  role: string;
  status: StaffCardStatus;
  break_started_at: string | null;
  // Non-null EXACTLY when `status` is "occupied" — the two are derived from one
  // argument server-side, so they cannot disagree. Denormalised onto the card on
  // purpose: the alternative is a client-side join of `staff` against `rooms`,
  // which would couple the card renderer to a panel it is otherwise independent
  // of.
  occupancy: Occupancy | null;
}

// An ENVELOPE, not a bare array: F36 adds rooms and F58 the waitlist to this
// same payload, so an array would make the first of them a breaking change.
export interface FloorResponse {
  staff: StaffCard[];
  // EVERY live room, active and inactive, in (sort_order, created_at) order. An
  // inactive room ships so the panel can grey it: a room a staffer cannot find
  // is worse than one she can see is out of service.
  rooms: Room[];
  // The server's own instant at serialisation. Elapsed minutes are computed
  // against THIS and not against the device clock, so only the delta of a
  // boutique tablet's clock is trusted and never its absolute value.
  server_now: string;
  // F58's ONE new envelope key, and the reason the read was an envelope from
  // the start. There is no second poll and no second endpoint: the waitlist is
  // two more statements on the tick's existing session, so «עודכן 14:07» stays
  // true of the staff, the rooms AND the queue simultaneously.
  waitlist: Waitlist;
}

// --- F36: the rooms -----------------------------------------------------------

export interface DressBinding {
  id: string;
  dress_id: string;
  // SNAPSHOTS carried on the binding row, not a live catalog read: the owner may
  // rename or archive a dress mid-fitting and the tile must render what actually
  // went into the room.
  dress_name: string;
  dress_size: string | null;
}

export interface RoomAssignment {
  id: string;
  staff_user_id: string;
  // null is D11's GHOST HOLDER — a staffer soft-deleted while holding a room.
  // The tile says so rather than lying about who is in there.
  staff_display_name: string | null;
  staff_role: string | null;
  // null is an anonymous visit, which is the DEFAULT and not an edge case: a
  // staffer prepping a room, a swept booking, or an erased customer.
  client_label: string | null;
  booking_id: string | null;
  assigned_at: string;
  dresses: DressBinding[];
}

// ONE shape for a room, and there is deliberately no RoomCard: every mutation
// answers exactly what the payload's rooms[] elements carry, so a tile patches
// in place from the server's own row and cannot disagree with itself.
export interface Room {
  id: string;
  label: string;
  sort_order: number;
  is_active: boolean;
  assignment: RoomAssignment | null;
}

// The staff card's half of the same fact.
export interface Occupancy {
  assignment_id: string;
  fitting_room_id: string;
  room_label: string;
  client_label: string | null;
  assigned_at: string;
}

// --- F36: the two one-shot pickers, fetched on open and never on the tick -----

export interface FloorDress {
  id: string;
  name: string;
  sizes: string[];
}

export interface FloorDressList {
  dresses: FloorDress[];
  // The dialog renders one line saying the list is partial. It names no count
  // and no limit — both are the server's to change without a copy edit.
  truncated: boolean;
}

export interface FloorClient {
  booking_id: string;
  client_label: string | null;
  starts_at: string;
}

export interface FloorClientList {
  clients: FloorClient[];
  truncated: boolean;
}

// --- F58: the waitlist -------------------------------------------------------

export interface WaitlistEntry {
  // ⚠ The ticket id, and it IS F33's capability: whoever holds it can read that
  // ticket's position page. On THIS surface that is not a disclosure — the
  // caller is a signed-in staffer behind the session cookie and the role gate —
  // and every verb in this feature takes it as the target, so there is no lesser
  // id to send. **The console must never render it as a link to `/q/{id}`.**
  id: string;
  name: string;
  // "bride" | "evening", rendered through waitlist.visitBride /
  // waitlist.visitEvening. Nothing SORTS on it: bride-priority ordering is
  // explicitly not built.
  visit_type: string;
  // 1-based, and the server's own `index + 1` over this list. Never re-derived
  // client-side: two derivations of one number are two chances for the wall
  // board, her phone and this panel to disagree.
  position: number;
  // `created_at`, NOT the sort key. `COALESCE(requeued_at, created_at)` is what
  // a skip rewrites, so anchoring the rendered clock to that would reset a
  // skipped woman's wait to zero and the panel would read «הגיעה זה עתה» about
  // someone who has been standing there forty minutes.
  arrived_at: string;
  // A boolean and not the timestamp: the panel needs to know WHETHER, and the
  // instant would let anyone with the screen time how long a named woman has
  // been standing at a counter.
  called: boolean;
  // What makes the second press's meaning legible BEFORE it is pressed, and
  // what the client sends back as `seen_skip_count`.
  skip_count: number;
  // "Another live ticket today carries the same phone." The phone itself never
  // reaches the wire — the flag is all that survives the grouping.
  duplicate: boolean;
}

export interface Waitlist {
  entries: WaitlistEntry[];
  // FloorDressList's rule verbatim: the panel renders one line saying the list
  // is partial and names NO count and NO limit.
  truncated: boolean;
}

// What the two dispatch verbs answer — the tile AND the queue, because they are
// two halves of one act. A client that patched the tile from the response and
// waited up to five seconds for the row to leave the list would render the same
// woman as both in-service and waiting.
export interface DispatchResult {
  room: Room;
  waitlist: Waitlist;
}

// --- F37: the SOS page (mirror backend/app/floor/schemas.py) ------------------

// The migration's CHECK is the pinned set; the live read answers only the first
// two, which is why the console's tick-rate condition is `{open, accepted}` and
// not `for_me`.
export type SosStatus = "open" | "accepted" | "resolved" | "cancelled";

/**
 * One emergency, and the SAME shape all five routes answer.
 *
 * ⚠ **IT CARRIES STAFF NAMES AND A ROOM LABEL AND NO CUSTOMER DATUM OF ANY
 * KIND, AND THE APP-LEVEL POLL IS EXACTLY WHY.** `Occupancy.client_label` above
 * is a bride's name and is defensible because `/manage/floor` is fetched only
 * while the console is on the board or the floor, by a component that unmounts
 * on navigation. This payload is fetched on EVERY section, every few seconds,
 * for a whole shift. A name here would mean the console holds a customer's name
 * in memory and on the wire while nobody is looking at a floor at all — and it
 * would buy nothing, because an SOS already names the person in the room.
 *
 * `escalated`, `stalled` and `for_me` are DERIVED on the server, per row,
 * against the one `server_now` the envelope carries. Deriving them here would
 * put the audience rule in the product twice, in two languages.
 */
export interface SosAlert {
  id: string;
  status: SosStatus;
  raised_by: string;
  // Null only if her staff row is gone entirely — the joins carry no
  // `deleted_at` filter, so a colleague removed mid-page still has a name.
  raised_by_name: string | null;
  // Null = the shift-manager ROLE. Also null when a named colleague turned out
  // to be unreachable and the raise rerouted.
  target_staff_user_id: string | null;
  target_name: string | null;
  // Null = no room on this page, which is ordinary: a seamstress at her table.
  room_label: string | null;
  note: string | null;
  accepted_by: string | null;
  accepted_by_name: string | null;
  acknowledged_at: string | null;
  created_at: string;
  escalated: boolean;
  stalled: boolean;
  for_me: boolean;
}

// An ENVELOPE for FloorResponse's reason plus a sharper one: `server_now` is the
// instant BOTH derived booleans and the console's elapsed line are computed
// against, so an escalated badge can never render beside «כבר 0 דק'».
export interface SosResponse {
  alerts: SosAlert[];
  server_now: string;
}

// ⚠ `rerouted` is a fact about THIS REQUEST and not about the row, which is why
// it cannot live on SosAlert: nobody reading the alert later can know whether a
// null target means «she asked for the shift manager» or «she asked for Dana and
// Dana was logged out». The dialog renders it and stays open for it.
export interface RaisedAlert {
  alert: SosAlert;
  rerouted: boolean;
}

// Every field optional and all three defaults are the ORDINARY case.
// `target_staff_user_id: null` is the shift-manager ROLE — the FALLBACK route,
// and what a staffer alone with a bride taps. It is not probed for reachability
// and its audience CAN be empty (spec Risk 3(a)): the last-owner invariant
// guarantees an owner ROW exists, not that anyone is signed in.
//
// ⚠ There is deliberately no `raised_by`. The acting identity is the session
// cookie and nothing on this body may stand in for it: nobody raises a page as
// somebody else, not even an owner, because an SOS is a first-person statement.
// The server's model is a ForbidExtraModel, so a key added here that is not
// there answers 400 on the one request that must never fail for a shape reason.
export interface RaiseSosRequest {
  target_staff_user_id?: string | null;
  fitting_room_assignment_id?: string | null;
  note?: string | null;
}

// --- F36: the request bodies (the backend's snake_case, sent verbatim) --------

export interface CreateRoomRequest {
  label: string;
  sort_order?: number;
}

// Every field optional, and an omitted key means UNCHANGED — never "clear it".
// The dialog's three controls are independent, so a reorder must leave the label
// alone.
export interface UpdateRoomRequest {
  label?: string;
  sort_order?: number;
  is_active?: boolean;
}

// ⚠ `staff_user_id` is the TARGET and only ever the target. The acting identity
// is the session cookie, and no code path may read this field as one. Both
// omitted is the one-tap anonymous claim on herself.
export interface ClaimRoomRequest {
  staff_user_id?: string;
  booking_id?: string;
}

export interface HandoverRequest {
  staff_user_id: string;
}

export interface AddDressRequest {
  dress_id: string;
  // Omitted for a sample gown carried in before a size is chosen.
  size_label?: string;
}

// --- F58: the dispatch request bodies ----------------------------------------

// ⚠ `staff_user_id` is the TARGET and only ever the target, exactly as it is on
// ClaimRoomRequest. The acting identity is the session cookie, and there is no
// `booking_id`: take-next's client is the head of the queue and nothing else can
// be bound to it.
export interface TakeNextRequest {
  staff_user_id?: string;
}

export interface AssignRequest {
  // REQUIRED — an assign with no ticket is a claim, and the claim already
  // exists.
  queue_ticket_id: string;
  staff_user_id?: string;
}

export interface SkipRequest {
  // ⚠ The value the CLIENT RENDERED, and the whole of what stops two ordinary
  // single taps removing a customer. Both managers' rows said 0, so neither
  // showed the confirm — it is gated on >= 1 — and without this field the second
  // tap escalates to `removed` on a count nobody saw. The server refuses on a
  // mismatch (409 QUEUE_TICKET_CHANGED) rather than escalating.
  //
  // NOT optional, and the server has no default either: a caller that omits it
  // is a caller that did not read a count.
  seen_skip_count: number;
}

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

// F33's printable check-in code. Two strings and nothing secret — the URL is
// the one printed on a sign in the shop window, which is why the route admits
// both console roles.
export interface CheckinQrResponse {
  checkin_url: string;
  // The SVG SOURCE, not a URL to an image: `apiFetch` unconditionally .json()s,
  // and CheckinQrSection renders it through a `data:` URI in an <img>.
  qr_svg: string;
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

// --- dashboard wire types (mirror backend/app/dashboard/schemas.py) ---
//
// Mirrored field-for-field in SNAKE_CASE. There is no case-conversion layer in
// this repo (see the header above): a camelCase interface compiles fine and
// reads `undefined` at runtime on every field.
//
// `generated_on`, `from_date` and `to_date` are PLAIN Jerusalem calendar dates
// ("2026-05-03"), never instants — they go through lib/jerusalem.ts's
// plainDate(), which is the one helper there that builds no Date.
//
// Nullable rates mirror `float | None`. `null` means NOT COMPUTABLE, never
// zero, and the console renders the two differently (spec D5, D10). The wire
// carries the UNROUNDED quotient; all rounding is the console's.

export interface WeekBucket {
  week_start: string;
  // The seat-slots the boutique HELD — every status except `cancelled`, so a
  // no-show is in this count. The Hebrew label says exactly that.
  bookings: number;
}

export interface StatusTotals {
  // Over a window entirely in the past, `confirmed` is the UNCLASSIFIED count —
  // an appointment whose outcome the owner never recorded — and it renders
  // beside no_show_rate for that reason.
  confirmed: number;
  cancelled: number;
  no_show: number;
  completed: number;
}

export interface AppointmentTypeCount {
  appointment_type_id: string;
  // An appointment TYPE label, never a person's name.
  name: string;
  bookings: number;
}

export interface CustomerMix {
  total: number;
  new: number;
  returning: number;
  repeat_rate: number | null;
}

export interface HistoryPanel {
  from_date: string;
  to_date: string;
  weeks: WeekBucket[];
  status_totals: StatusTotals;
  cancellation_rate: number | null;
  // These two can sum to LESS than status_totals.cancelled: a row cancelled
  // before migration 0010 added the column carries NULL and is in neither.
  // Rendered as two independent tiles, never as a partition.
  cancelled_by_customer: number;
  cancelled_by_owner: number;
  no_show_rate: number | null;
  appointment_types: AppointmentTypeCount[];
  customers: CustomerMix;
}

export interface ForwardPanel {
  from_date: string;
  // INCLUSIVE, matching the slot engine's window.
  to_date: string;
  capacity: number;
  booked: number;
  utilization: number | null;
}

export interface DashboardResponse {
  generated_on: string;
  history: HistoryPanel;
  forward: ForwardPanel;
}

// --- customers wire types (mirror backend/app/customers/schemas.py) ---
//
// Mirrored field-for-field in SNAKE_CASE, same as every block above: there is
// no case-conversion layer in this repo, so a camelCase interface compiles fine
// and reads `undefined` at runtime on every field.
//
// `created_at` is deliberately on neither shape. F52's D7 established that
// `customers.created_at` is meaningless as a "first seen" date after F15's
// phone-correction collision branch re-points a booking at an existing row, so
// a customer's row can post-date her own first booking.

export interface CustomerRow {
  id: string;
  name: string;
  phone: string;
  tags: string[];
}

export interface CustomerListResponse {
  items: CustomerRow[];
  total: number;
  offset: number;
  limit: number;
}

export interface CustomerBookingRow {
  id: string;
  starts_at: string;
  status: string;
  // The snapshot taken when the booking was made, not the live type name:
  // history must render as what the customer agreed to.
  appointment_type_name: string;
}

// Five fields. `provider_message_id`, `error` and `phone` are all on the row
// server-side and none of them ship — `kind` and `status` are the RAW enum
// values and the console maps each through its own key table, falling back to
// the raw value for an unknown one.
export interface SmsLogRow {
  id: string;
  created_at: string;
  kind: string;
  status: string;
  body: string;
}

// Named `…Response`, not `CustomerDetail`, because `CustomerDetail` is the
// COMPONENT in components/CustomerDetail.tsx. The shipped pair avoids exactly
// this: the component is `BookingDetail` and the wire type is
// `OwnerBookingDetail`. Under the workspace's `isolatedModules: true` a
// colliding value import is a hard error, and any file needing both names at
// once could not import them at all. The backend model stays `CustomerDetail`;
// there is no component in Python to collide with.
export interface CustomerDetailResponse {
  id: string;
  name: string;
  phone: string;
  notes: string | null;
  tags: string[];
  bookings: CustomerBookingRow[];
  messages: SmsLogRow[];
  // The send volume the fifty-row window cannot show: OTP rows are written by
  // an anonymous endpoint and are always the newest, so fifty of them evict
  // every confirmation and reminder from the window.
  messages_total: number;
}

// Optional, NOT nullable: an omitted key is "unchanged" on the wire, and the
// client must never send `null` for a field it did not touch. `""` and `[]`
// mean CLEAR.
export interface UpdateCustomerRequest {
  notes?: string;
  tags?: string[];
}

export interface CustomerListQuery {
  q: string;
  offset: number;
  limit: number;
}

function customerPath(customerId: string): string {
  return `/manage/customers/${encodeURIComponent(customerId)}`;
}

// --- atelier wire types (mirror backend/app/atelier/schemas.py) ---

// ⚠ DERIVED, never stored. The server has no status column: a ticket's stage is
// the RIGHTMOST STAMPED of the five nullable timestamps below, floored at
// `intake`. The ORDER of this union is the total order the whole feature is
// spelled from — `lib/stages.ts` owns it, and a member inserted in the middle
// changes the meaning of every advance and every undo.
export type TicketStage = "intake" | "in_progress" | "qc" | "ready" | "delivered";

// The five preset bands. The client sends a BAND KEY and never a number, which
// is what makes "five presets, not a minute field" a property of the wire rather
// than a UI convention; the server resolves it against the tenant's mapping and
// the row stores the minutes.
export type EffortBand = "thirty_min" | "one_hour" | "two_hours" | "half_day" | "full_day";

// One card. `customer_name` ships and `customer_phone` does NOT — the board is
// read by a seamstress and there is no surface in F41 that calls a bride.
export interface AtelierTicket {
  id: string;
  customer_name: string;
  due_date: string;
  // Computed on read against the Jerusalem calendar day, never stored — a
  // stored boolean would need a worker to flip it at midnight and would be stale
  // for up to a tick.
  overdue: boolean;
  effort_minutes: number;
  assigned_staff_user_id: string | null;
  dress_id: string | null;
  dress_name: string | null;
  dress_size: string | null;
  notes: string | null;
  stage: TicketStage;
  intake_at: string | null;
  in_progress_at: string | null;
  qc_at: string | null;
  ready_at: string | null;
  delivered_at: string | null;
}

// `assignable` is not a column — it is the server's pure function of the staff
// row (live AND still a seamstress). It is on the wire so the console's
// «תופרת שאינה פעילה» branch is data-driven instead of inferred from absence:
// F51's staff CRUD can re-role or retire a seamstress and knows nothing about
// this table.
export interface SeamstressRef {
  id: string;
  display_name: string;
  assignable: boolean;
}

export interface EffortBandRef {
  band: EffortBand;
  minutes: number;
}

// An ENVELOPE, not a bare array: F42 adds capacity to `seamstresses` and F43
// fitting counts to a ticket, so an array would make the first of those a
// breaking shape change on a screen that polls every five seconds.
//
// ⚠ `truncated` is a FLAG and not a count, deliberately: the row limit is
// server-only and no client constant mirrors it, so the console can say what was
// cut without being one constant away from lying about how much.
export interface AtelierBoardResponse {
  tickets: AtelierTicket[];
  seamstresses: SeamstressRef[];
  effort_bands: EffortBandRef[];
  truncated: boolean;
}

// ⚠ `dress_id` is ALWAYS null from this console. The catalog picker is cut from
// F41: the board payload carries no dresses, `GET /manage/dresses` refuses a
// seamstress while this dialog admits one, and the card renders no image — so on
// this surface the column has no reader. The SERVER path is kept whole; F43 is
// the caller that will send an id.
export interface CreateTicketRequest {
  customer_name: string;
  customer_phone: string;
  due_date: string;
  effort_band: EffortBand;
  assigned_staff_user_id: string | null;
  dress_id: null;
  dress_name: string | null;
  dress_size: string | null;
  notes: string | null;
}

// ⚠ A FULL REPLACE — every editable field REQUIRED, no optionals anywhere. With
// optional fields an OMITTED key and an explicitly cleared one are the same
// request, so a console that forgot to send `notes` would silently delete a
// bride's measurements. The customer is not editable: a ticket opened for the
// wrong bride is a delete and a re-open.
export interface UpdateTicketRequest {
  due_date: string;
  effort_band: EffortBand;
  dress_id: null;
  dress_name: string | null;
  dress_size: string | null;
  notes: string | null;
}

function ticketPath(ticketId: string): string {
  return `/manage/atelier/tickets/${encodeURIComponent(ticketId)}`;
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
  // F34's two. Both answer the full OwnerBookingDetail, which extends the list
  // row, so a board row patches in place from the response and the two views
  // cannot disagree. Neither is time-boxed on the client because neither is on
  // the server: check-in has no clock bound in either direction (an early
  // arrival is the ordinary case the board exists for) and the undo has no
  // status guard and no clock bound at all.
  checkInBooking(bookingId: string): Promise<OwnerBookingDetail> {
    return apiFetch(`${bookingPath(bookingId)}/check-in`, { method: "POST" });
  },
  undoBookingCheckIn(bookingId: string): Promise<OwnerBookingDetail> {
    return apiFetch(`${bookingPath(bookingId)}/undo-check-in`, { method: "POST" });
  },
  // F57's floor. Both toggles answer ONE card — the whole panel is not re-sent —
  // so the tapped card patches in place from the response and the loop keeps its
  // own beat underneath.
  getFloor(): Promise<FloorResponse> {
    return apiFetch("/manage/floor");
  },
  startStaffBreak(staffId: string): Promise<StaffCard> {
    return apiFetch(`/manage/floor/staff/${encodeURIComponent(staffId)}/break/start`, {
      method: "POST",
    });
  },
  endStaffBreak(staffId: string): Promise<StaffCard> {
    return apiFetch(`/manage/floor/staff/${encodeURIComponent(staffId)}/break/end`, {
      method: "POST",
    });
  },

  // F36's ten. Eight of them answer the SAME `Room` the payload's rooms[]
  // elements carry, so a tile patches in place from the server's own row; the
  // delete answers the shipped OkResponse because there is no tile left to
  // render, and the two pickers are one-shot reads fetched when a dialog opens
  // and never on the tick.
  //
  // The three registry verbs and the handover are owner + shift_manager
  // server-side; the client renders no control a caller may not use, which is
  // what keeps the terminal 403 unreachable by design rather than by luck.
  createRoom(body: CreateRoomRequest): Promise<Room> {
    return apiFetch("/manage/floor/rooms", { method: "POST", body });
  },
  // Partial by design — an omitted key means "unchanged", so a reorder leaves
  // the label alone.
  updateRoom(roomId: string, body: UpdateRoomRequest): Promise<Room> {
    return apiFetch(roomPath(roomId), { method: "PATCH", body });
  },
  deleteRoom(roomId: string): Promise<OkResponse> {
    return apiFetch(roomPath(roomId), { method: "DELETE" });
  },
  // The body always travels, even when it is `{}`: the route's model is
  // required, and `{}` IS the one-tap anonymous claim on herself — the default
  // path, and the only one available before the day's first arrival.
  claimRoom(roomId: string, body: ClaimRoomRequest): Promise<Room> {
    return apiFetch(`${roomPath(roomId)}/claim`, { method: "POST", body });
  },
  // No body: the target is the assignment and there is nothing to say about it.
  releaseAssignment(assignmentId: string): Promise<Room> {
    return apiFetch(`${assignmentPath(assignmentId)}/release`, { method: "POST" });
  },
  handoverAssignment(assignmentId: string, body: HandoverRequest): Promise<Room> {
    return apiFetch(`${assignmentPath(assignmentId)}/handover`, { method: "POST", body });
  },
  addAssignmentDress(assignmentId: string, body: AddDressRequest): Promise<Room> {
    return apiFetch(`${assignmentPath(assignmentId)}/dresses`, { method: "POST", body });
  },
  removeAssignmentDress(assignmentId: string, bindingId: string): Promise<Room> {
    return apiFetch(
      `${assignmentPath(assignmentId)}/dresses/${encodeURIComponent(bindingId)}`,
      { method: "DELETE" },
    );
  },
  // F58's five. The two DISPATCH verbs answer a `DispatchResult` — the tile and
  // the queue together, because they are two halves of one act — and the three
  // ROW verbs answer the whole `Waitlist`: a skip reorders it and a remove
  // shortens it, and a per-entry patch can express neither.
  //
  // The two dispatch bodies always travel even when empty, for `claimRoom`'s
  // reason: the route's model is required, and `{}` IS the one-tap take-next on
  // herself. The two verbs with nothing to say send no body at all.
  takeNext(roomId: string, body: TakeNextRequest): Promise<DispatchResult> {
    return apiFetch(`${roomPath(roomId)}/take-next`, { method: "POST", body });
  },
  assignFromQueue(roomId: string, body: AssignRequest): Promise<DispatchResult> {
    return apiFetch(`${roomPath(roomId)}/assign`, { method: "POST", body });
  },
  callQueueTicket(ticketId: string): Promise<Waitlist> {
    return apiFetch(`${queuePath(ticketId)}/call`, { method: "POST" });
  },
  skipQueueTicket(ticketId: string, body: SkipRequest): Promise<Waitlist> {
    return apiFetch(`${queuePath(ticketId)}/skip`, { method: "POST", body });
  },
  removeQueueTicket(ticketId: string): Promise<Waitlist> {
    return apiFetch(`${queuePath(ticketId)}/remove`, { method: "POST" });
  },
  listFloorDresses(): Promise<FloorDressList> {
    return apiFetch("/manage/floor/dresses");
  },
  listFloorClients(): Promise<FloorClientList> {
    return apiFetch("/manage/floor/clients");
  },

  // F37's five. The read is the app-level poll's ONE statement — it runs on
  // every section of the console, which is what the payload's missing customer
  // datum is for. The three action verbs answer the SAME alert shape the read
  // does, so a card patches in place from the server's own row.
  getSos(): Promise<SosResponse> {
    return apiFetch("/manage/floor/sos");
  },
  raiseSos(body: RaiseSosRequest): Promise<RaisedAlert> {
    return apiFetch("/manage/floor/sos", { method: "POST", body });
  },
  // No body on any of the three: the target is the alert id and there is
  // nothing to say about it (releaseAssignment's reasoning, one router over).
  acceptSos(alertId: string): Promise<SosAlert> {
    return apiFetch(`${sosPath(alertId)}/accept`, { method: "POST" });
  },
  resolveSos(alertId: string): Promise<SosAlert> {
    return apiFetch(`${sosPath(alertId)}/resolve`, { method: "POST" });
  },
  cancelSos(alertId: string): Promise<SosAlert> {
    return apiFetch(`${sosPath(alertId)}/cancel`, { method: "POST" });
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

  // Both roles: a shift manager sees the same card the owner does and edits the
  // same notes. The gate is router-level server-side.
  listCustomers(query: CustomerListQuery): Promise<CustomerListResponse> {
    const params = new URLSearchParams({
      offset: String(query.offset),
      limit: String(query.limit),
    });
    // Omitted rather than sent empty: a blank box means "everyone", and the
    // server drops a whitespace-only term anyway — sending `q=` would put two
    // spellings of one intent in the access log for no gain.
    if (query.q.trim() !== "") {
      params.set("q", query.q.trim());
    }
    return apiFetch(`/manage/customers?${params.toString()}`);
  },
  getCustomer(customerId: string): Promise<CustomerDetailResponse> {
    return apiFetch(customerPath(customerId));
  },
  // Partial by design — an omitted key means "unchanged", and the server reads
  // an all-unchanged patch as a no-op that writes no audit row. The response is
  // the WHOLE detail, panels included, so the caller can replace state with it:
  // a response carrying only the customers row would blank the booking history
  // and the SMS log the instant the owner pressed save.
  updateCustomer(
    customerId: string,
    body: UpdateCustomerRequest,
  ): Promise<CustomerDetailResponse> {
    return apiFetch(customerPath(customerId), { method: "PATCH", body });
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

  // Both roles. No parameters at all — the window is derived server-side from a
  // real clock, which is what keeps its date arithmetic total (spec D2).
  getDashboard(): Promise<DashboardResponse> {
    return apiFetch("/manage/dashboard");
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

  // Both roles, and no parameters: the answer is a total function of the
  // tenant's own slug, which the server takes from the Host header. `slug`
  // appears nowhere in this app, so composing the URL here was never an option.
  getCheckinQr(): Promise<CheckinQrResponse> {
    return apiFetch("/manage/checkin-qr");
  },

  // F41's atelier. One poll and six writes, all three workroom roles on the
  // read — and every mutation answers the FULL ticket rather than {ok: true},
  // so the console patches its card from the server's own row and cannot
  // disagree with itself. On a 200 no-op that renders the FIRST actor's
  // timestamp rather than this request's intent, which is the outcome she
  // wanted either way.
  getAtelierBoard(): Promise<AtelierBoardResponse> {
    return apiFetch("/manage/atelier/tickets");
  },
  createTicket(body: CreateTicketRequest): Promise<AtelierTicket> {
    return apiFetch("/manage/atelier/tickets", { method: "POST", body });
  },
  updateTicket(ticketId: string, body: UpdateTicketRequest): Promise<AtelierTicket> {
    return apiFetch(`${ticketPath(ticketId)}/update`, { method: "POST", body });
  },
  // `null` RELEASES, and it is a value rather than an omission — an optional
  // field would make a malformed request that dropped the key indistinguishable
  // from a deliberate release.
  assignTicket(ticketId: string, staffUserId: string | null): Promise<AtelierTicket> {
    return apiFetch(`${ticketPath(ticketId)}/assign`, {
      method: "POST",
      body: { staff_user_id: staffUserId },
    });
  },
  // ⚠ The stage is the one to ENTER on advance and the one to CLEAR on undo, and
  // the client names it from WHAT ITS LAST POLL SHOWED. That is what makes a
  // stale board harmless: if the ticket moved on between the paint and the tap,
  // the write's predicate matches nothing and the caller gets a 409 rather than
  // stamping — or clearing — a stage that arrived after it last looked.
  advanceStage(ticketId: string, stage: TicketStage): Promise<AtelierTicket> {
    return apiFetch(`${ticketPath(ticketId)}/stage/advance`, {
      method: "POST",
      body: { stage },
    });
  },
  undoStage(ticketId: string, stage: TicketStage): Promise<AtelierTicket> {
    return apiFetch(`${ticketPath(ticketId)}/stage/undo`, { method: "POST", body: { stage } });
  },
  // The one per-route tightening: owner and shift manager only. A seamstress may
  // not remove a garment from the board — it is destructive and there is no
  // un-delete.
  deleteTicket(ticketId: string): Promise<OkResponse> {
    return apiFetch(`${ticketPath(ticketId)}/delete`, { method: "POST" });
  },
};
