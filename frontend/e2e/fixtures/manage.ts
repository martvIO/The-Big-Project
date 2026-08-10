import type { Page } from "@playwright/test";

// The /manage console's Playwright interception harness.
//
// **THIS IS REUSABLE INFRASTRUCTURE, NOT ONE FEATURE'S SCAFFOLD.** Before F58
// the console had FOUR e2e tests and every one of them was the LOGIN SCREEN —
// the gap F34's spec recorded as Risk 8 and nothing closed. Nothing gets past
// `App.tsx`'s `api.me()` bootstrap without a stubbed identity, so twelve shipped
// sections had no authenticated coverage of any kind. Every later console
// feature inherits this module; `manage.spec.ts` is its first consumer and not
// its owner. Adding a surface should mean ADDING A STUB, never forking the
// harness.
//
// **How it authenticates: it does not.** `App.tsx` bootstraps on `api.me()` and
// renders `<LoginForm/>` on a rejection, so fulfilling `GET /manage/auth/me`
// with a 200 `Staff` body is the whole of "signed in" — no cookie, no login
// POST, no session table.
//
// **The default identity is `reception`, and that is deliberate rather than
// arbitrary.** `NAV`'s `floor` row is `FLOOR_ONLY`, so a reception staffer's
// only reachable section IS the floor, `activeKey` lands there with no
// navigation, and no other panel ever mounts — three stubbed GETs and not one
// stray request. `shift_manager` and `owner` land on `dashboard` and reach the
// floor through `board`, which is why `/manage/dashboard` and `/manage/bookings`
// carry defaults too.
//
// ⚠ **RISK 6, stated here so the harness is never trusted for what it cannot
// do: it stubs the API, so it proves the CONSOLE and not the CONTRACT.** A
// backend change that renames a payload key passes every test in this file while
// breaking production. Only `test_floor_api.py`'s set-equality assertions and
// the TypeScript types catch that. This is a journey and accessibility
// instrument. The wire shapes below are hand-mirrored from
// `apps/manage/src/api.ts` on purpose — importing the app's types would drag the
// app's module graph into the e2e typecheck, and `storefront.spec.ts` declares
// its fixtures locally for the same reason.

export const MANAGE = "http://localhost:4174/manage/";

// --- what may be intercepted -------------------------------------------------
//
// ⚠ **THE TRAP THIS SECTION EXISTS TO MAKE UN-STEPPABLE-ON: a route on
// `**​/manage/**` ALSO MATCHES THE APP ITSELF.** `apps/manage` builds with
// `base: "/manage/"`, so `/manage/index.html`, `/manage/assets/*.js` and
// `/manage/favicon.svg` all live under that prefix — and one broad glob serves a
// blank page with no error anywhere.
//
// The guard is the backend's own rule rather than a list of globs per feature: a
// path is an API path exactly when its SECOND SEGMENT is one of the fourteen
// second segments the /manage routers declare. That set is
// `apps/manage/vite.config.ts`'s `MANAGE_API` alternation verbatim, and
// `backend/tests/test_spa_serving.py` derives it from the live route table and
// asserts the two agree — so this line cannot drift from the server without that
// test going red first.
//
// Two things fall out, and both are the reason this is one predicate instead of
// five globs. An asset is never matched at all: `assets`, `index.html` and
// `favicon.svg` are not families. And a later console feature inherits its
// family for free — F41's `/manage/bookings/{id}/…` is already covered, so it
// adds a stub and not a fork.
const API_FAMILIES = new Set([
  "appointment-types",
  // ⚠ F42 ADDS THIS ROW, AND ITS ABSENCE WAS A REAL HOLE. `MANAGE_API` in
  // `apps/manage/vite.config.ts` names FIFTEEN segments and this set had
  // fourteen: F58 built the harness alongside F41 rather than after it. An
  // atelier call therefore fell THROUGH the interception to `vite preview`'s
  // proxy — which serves the SPA shell for an unproxied path — so the board
  // would have rendered its outage line with nothing anywhere saying why.
  "atelier",
  "auth",
  "availability",
  "bookings",
  "checkin-qr",
  "customers",
  "dashboard",
  "dresses",
  "floor",
  "gateway",
  // ⚠ F21 ADDS THIS ROW, AND ITS ABSENCE WAS THE SAME HOLE AS `atelier` ABOVE,
  // one feature later. `MANAGE_API` in `apps/manage/vite.config.ts:19` names
  // SIXTEEN segments and this set had fifteen: F58 built the harness before F20
  // shipped `/manage/privacy`. So every privacy call fell THROUGH the
  // interception to `vite preview`'s proxy — which serves the SPA shell for an
  // unproxied path — and `PrivacySection` rendered its outage line with nothing
  // anywhere saying why. Found by F21's axe sweep, which could not reach the
  // §13 subject-request surface at all until this line existed.
  "privacy",
  "settings",
  "slots",
  "staff",
  "terms",
  // F22's booking waitlist (`/manage/waitlist`). Same rule as `atelier` and
  // `privacy` above: `MANAGE_API` in `apps/manage/vite.config.ts` gains the
  // segment in the same commit, and test_spa_serving.py is what keeps the two
  // sets agreeing with the live route table.
  "waitlist",
]);

function isManageApi(pathname: string): boolean {
  // ["", "manage", family, …]. A bare "/manage/" splits to a third element of
  // "", which is in no family — the shell's own URL is never intercepted.
  const segments = pathname.split("/");
  return segments[1] === "manage" && API_FAMILIES.has(segments[2] ?? "");
}

// --- replies -----------------------------------------------------------------

export interface Reply {
  status: number;
  body: unknown;
}

export function ok(body: unknown): Reply {
  return { status: 200, body };
}

// The house error envelope, `{"error": {"code", "message", "details"}}`, which
// is what `api.ts`'s `extractError` reads and `ApiError` carries.
//
// The message is ENGLISH on purpose — every backend message is. The console
// selects its Hebrew by CODE, so a fixture carrying Hebrew here would hide a UI
// that painted the server's sentence onto a Hebrew-only screen.
export function refuse(
  status: number,
  code: string,
  details?: Record<string, string>,
): Reply {
  return {
    status,
    body: { error: { code, message: `${code} from the fixture.`, details } },
  };
}

// **The design, not a fallback.** An unstubbed API call must fail LOUDLY — as a
// rendered Hebrew error the test can see — rather than reaching `vite preview`'s
// proxy to a port with nothing on it, where the failure reads as a flake.
const NOT_FOUND: Reply = {
  status: 404,
  body: { error: { code: "NOT_FOUND", message: "Nothing is stubbed at this path." } },
};

// The last entry repeats: a one-element queue is a constant, and a two-element
// one is "this happens once, then that". `storefront.spec.ts`'s idiom verbatim —
// and it is what a mutation journey needs, because a 5s poll tick would
// otherwise re-deliver the pre-mutation floor and put the dispatched row back.
function take(queue: Reply[]): Reply {
  return queue.length > 1 ? (queue.shift() as Reply) : queue[0];
}

// --- the recorder ------------------------------------------------------------

export interface RecordedRequest {
  method: string;
  path: string;
  /** The raw query string including its "?", or "" — the console pages bookings this way. */
  query: string;
  /** The parsed JSON body, or null. What lets a test assert what the app SENT. */
  body: unknown;
}

export interface Recorder {
  all: RecordedRequest[];
  of(path: string): RecordedRequest[];
}

// --- fixtures ----------------------------------------------------------------

export interface Staff {
  id: string;
  email: string;
  display_name: string;
  role: string;
}

export const SELF_ID = "st-self";

export function staff(overrides: Partial<Staff> = {}): Staff {
  return {
    id: SELF_ID,
    email: "reception@example.test",
    display_name: "רונית",
    role: "reception",
    ...overrides,
  };
}

// 2099 so nothing here depends on today, on a TTL or on the machine's clock.
export const SERVER_NOW = "2099-01-04T08:00:00Z";
// Twenty minutes before it, so every row renders a real «ממתינה 20 דק'» rather
// than the just-arrived branch.
export const ARRIVED_AT = "2099-01-04T07:40:00Z";

// A 1x1 PNG, inline. F38's photo fields are on the wire, so a fixture that omits
// them is not merely incomplete — `photo_url === null` is how BOTH renderers
// choose the initial-letter fallback, and `undefined === null` is false, so an
// absent field paints a srcless <img> that exists nowhere in production. Inline
// because `img-src` carries `data:` (see fixtures/csp.txt) and a data URI needs
// no server, no signature and no TTL: the board's pin is keyed on
// `(id, photo_confirmed_at)` and never on the URL, so a constant one is honest.
export const PHOTO_DATA_URI =
  "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==";
export const PHOTO_CONFIRMED_AT = "2099-01-03T10:00:00Z";

export interface StaffCard {
  id: string;
  display_name: string;
  role: string;
  status: string;
  break_started_at: string | null;
  occupancy: unknown;
  photo_url: string | null;
  photo_confirmed_at: string | null;
}

export function staffCard(overrides: Partial<StaffCard> = {}): StaffCard {
  return {
    id: SELF_ID,
    display_name: "רונית",
    role: "reception",
    status: "available",
    break_started_at: null,
    occupancy: null,
    // Default to the fallback branch: every spec that predates F38 asserts a
    // board with no faces on it, and an opt-in keeps those readings true.
    photo_url: null,
    photo_confirmed_at: null,
    ...overrides,
  };
}

export interface RoomAssignment {
  id: string;
  staff_user_id: string;
  staff_display_name: string | null;
  staff_role: string | null;
  client_label: string | null;
  booking_id: string | null;
  assigned_at: string;
  dresses: unknown[];
}

export function assignment(overrides: Partial<RoomAssignment> = {}): RoomAssignment {
  return {
    id: "as-1",
    staff_user_id: SELF_ID,
    staff_display_name: "רונית",
    staff_role: "reception",
    client_label: null,
    booking_id: null,
    assigned_at: ARRIVED_AT,
    dresses: [],
    ...overrides,
  };
}

export interface Room {
  id: string;
  label: string;
  sort_order: number;
  is_active: boolean;
  assignment: RoomAssignment | null;
}

export function room(overrides: Partial<Room> = {}): Room {
  return { id: "rm-1", label: "חדר 1", sort_order: 1, is_active: true, assignment: null, ...overrides };
}

export interface WaitlistEntry {
  id: string;
  name: string;
  visit_type: string;
  position: number;
  arrived_at: string;
  called: boolean;
  skip_count: number;
  duplicate: boolean;
}

export function waitlistEntry(overrides: Partial<WaitlistEntry> = {}): WaitlistEntry {
  return {
    id: "qt-1",
    name: "נועה כהן",
    visit_type: "bride",
    position: 1,
    arrived_at: ARRIVED_AT,
    called: false,
    skip_count: 0,
    duplicate: false,
    ...overrides,
  };
}

export interface Waitlist {
  entries: WaitlistEntry[];
  truncated: boolean;
}

export function waitlist(entries: WaitlistEntry[], truncated = false): Waitlist {
  return { entries, truncated };
}

export interface FloorPayload {
  staff: StaffCard[];
  rooms: Room[];
  server_now: string;
  waitlist: Waitlist;
}

export function floorPayload(overrides: Partial<FloorPayload> = {}): FloorPayload {
  return {
    staff: [staffCard()],
    rooms: [room()],
    server_now: SERVER_NOW,
    waitlist: waitlist([]),
    ...overrides,
  };
}

// What the two DISPATCH verbs answer: the tile AND the queue, because they are
// two halves of one act.
export function dispatchResult(next: Room, remaining: WaitlistEntry[]): unknown {
  return { room: next, waitlist: waitlist(remaining) };
}

// Every number zero and every list empty. The two elevated roles land on
// «סקירה» before they can navigate anywhere, so this exists purely so that
// journey does not open on somebody else's outage message. Mirrors
// `DashboardResponse`.
export function dashboardPayload(): unknown {
  return {
    generated_on: "2099-01-04",
    history: {
      from_date: "2098-10-06",
      to_date: "2099-01-04",
      weeks: [],
      status_totals: { confirmed: 0, cancelled: 0, no_show: 0, completed: 0 },
      cancellation_rate: null,
      cancelled_by_customer: 0,
      cancelled_by_owner: 0,
      no_show_rate: null,
      appointment_types: [],
      customers: { total: 0, new: 0, returning: 0, repeat_rate: null },
    },
    forward: {
      from_date: "2099-01-04",
      to_date: "2099-01-31",
      capacity: 0,
      booked: 0,
      utilization: null,
    },
  };
}

// --- F21: one populated payload per console section --------------------------
//
// ⚠ POPULATED, NEVER EMPTY, AND THAT IS THE WHOLE POINT. `manage.spec.ts`'s
// `AXE_SECTIONS` sweep scans eleven sections that had no axe coverage at all,
// and a section rendering its zero-row branch has almost no markup to scan: no
// per-row buttons, no table, no badges. `staff`'s per-row «השבתה — {{name}}» is
// exactly where F61's nameless-button defect lived, and it only exists on a row
// that is NOT the signed-in staffer — so `staffList()` ships two.
//
// Wire shapes are hand-mirrored from `apps/manage/src/api.ts`, same rule as the
// rest of this file: importing the app's types would drag its module graph into
// the e2e typecheck. Nullable-but-required fields are sent as `null` rather than
// omitted, because that is what the server does.

export function settingsPayload(): unknown {
  return {
    profile: {
      phone: "03-5551234",
      address: "דיזנגוף 100, תל אביב",
      description: "בוטיק שמלות כלה בלב תל אביב.",
      maps_url: "https://maps.example.test/boutique",
      essence: "השמלה שלך מתחילה כאן",
      instagram: "modryn.boutique",
    },
    // ⚠ THE FULL, DEFAULT-COMPLETE TOGGLES BLOCK — every key the BACKEND
    // registry declares (`Backend/app/boutique/toggles.py`), because F27 D3 puts
    // exactly that on the wire and `TogglesMatrix` renders one row per WIRE key.
    //
    // This object is the cross-tree drift tripwire the two registries have
    // instead of a shared import: a key added on one side only shows up here as
    // an extra or missing row. D8's growth protocol makes that step ④, and it is
    // one line — which is the proof the protocol costs what it claims.
    toggles: { deposits_enabled: true, brides_only: false },
  };
}

// The same block after a single-row flip, for the PUT's response. D2's deep
// merge means the server answers a one-key write with EVERY key's current
// truth, so the matrix re-syncs the whole card from it.
export function settingsAfterToggle(
  key: string,
  value: boolean,
): Record<string, unknown> {
  const base = settingsPayload() as { profile: unknown; toggles: Record<string, boolean> };
  return { profile: base.profile, toggles: { ...base.toggles, [key]: value } };
}

export function availabilityPayload(): unknown {
  return {
    rules: [
      { id: "ar-1", day_of_week: 0, open_time: "09:00:00", close_time: "17:00:00", capacity: 3 },
    ],
    // Non-null times on purpose: a closed-all-day exception renders a badge
    // whose label collides with the add-exception toggle, and the settle tell
    // has to be unambiguous.
    exceptions: [
      {
        id: "ae-1",
        date: "2099-04-14",
        open_time: "10:00:00",
        close_time: "13:00:00",
        note: "ערב פסח",
      },
    ],
  };
}

// A bare array, not an envelope.
export function appointmentTypes(): unknown {
  return [
    {
      id: "apt-1",
      name: "מדידה ראשונה",
      duration_minutes: 90,
      audience: "all",
      deposit_required: true,
      deposit_amount_agorot: 25000,
      sort_order: 0,
    },
  ];
}

export function termsHistory(): unknown {
  // The SAME id in `current` and in `versions[0]`, so the «בתוקף» marker renders
  // — the panel compares them by id.
  const version = {
    id: "tv-1",
    version: 1,
    terms_text: "ביטול עד 48 שעות לפני מועד התור מזכה בהחזר מלא של המקדמה.",
    refundable_until_hours_before: 48,
    forfeit_percent: 100,
    created_by: "st-self",
    created_at: "2099-01-02T09:00:00Z",
  };
  return { current: version, versions: [version], total: 1, offset: 0, limit: 50 };
}

export function dressList(): unknown {
  return {
    items: [
      {
        id: "dr-1",
        name: "שמלת נסיכה",
        description: "תחרה צרפתית, שובל קצר.",
        price_agorot: 890000,
        price_visible: true,
        reserved: false,
        sort_order: 0,
        out_of_stock: false,
        total_quantity: 3,
        // > 0 so the row does not fall into its «לא הוגדרו מידות» branch.
        variant_count: 2,
        // No cover: a non-null one needs a presigned URL this harness cannot
        // serve, and a broken <img> would be a defect the scan invented.
        media_count: 0,
        cover: null,
        archived: false,
        created_at: "2099-01-02T09:00:00Z",
        updated_at: null,
      },
    ],
    total: 1,
    offset: 0,
    limit: 24,
  };
}

// --- F28: date-bound reservations ---------------------------------------------

/** The detail `GET /manage/dresses/{id}` answers — dressList()'s row widened
 *  with the three detail-only fields, so the editor opens on a real dress. */
export function dressDetail(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  const [row] = (dressList() as { items: Record<string, unknown>[] }).items;
  return {
    ...row,
    variants: [
      { id: "v-1", size_label: "38", quantity: 2, sort_order: 0 },
      { id: "v-2", size_label: "40", quantity: 1, sort_order: 1 },
    ],
    media: [],
    media_uploads_enabled: true,
    media_slots_remaining: 12,
    ...overrides,
  };
}

export function reservation(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id: "res-1",
    // 2099 so the window is future no matter when the suite runs, and the
    // formatter's "year differs from the current one" branch is the one under
    // test on both surfaces.
    starts_on: "2099-08-12",
    ends_on: "2099-08-18",
    customer_id: null,
    customer_name: null,
    notes: null,
    created_at: "2099-01-02T09:00:00Z",
    ...overrides,
  };
}

export function bookingList(): unknown {
  return {
    items: [
      {
        id: "bk-1",
        starts_at: "2099-01-04T08:30:00Z",
        status: "confirmed",
        attendance_confirmed_at: null,
        checked_in_at: null,
        customer_name: "נועה כהן",
        appointment_type_name: "מדידה ראשונה",
        dress_name: null,
        payment_status: "paid",
        refund_due_agorot: null,
        source: "storefront",
      },
    ],
    total: 1,
    offset: 0,
    limit: 50,
  };
}

export function customerList(): unknown {
  return {
    items: [{ id: "cu-1", name: "מיכל לוי", phone: "+972501234567", tags: ["כלה", "אביב 2099"] }],
    total: 1,
    offset: 0,
    limit: 50,
  };
}

// TWO rows, and the second one matters: the per-row danger control is behind
// `!isSelf`, so a list holding only the signed-in staffer renders no «השבתה» at
// all — and that button is the one F61's nameless-button defect lived on.
//
// The two rows also split F38's photo branch: רונית carries a photo and דנה
// does not, so the section's axe sweep covers BOTH the <img> and the
// initial-letter fallback in one pass rather than only whichever one a
// single-shaped list happens to render.
export function staffList(): unknown {
  return [
    {
      id: SELF_ID,
      email: "owner@example.test",
      display_name: "רונית",
      role: "owner",
      created_at: "2098-06-01T09:00:00Z",
      phone: "+972501234567",
      start_date: "2098-06-01",
      last_day: null,
      shift_manager_eligible: false,
      photo_url: PHOTO_DATA_URI,
      photo_confirmed_at: PHOTO_CONFIRMED_AT,
    },
    {
      id: "st-2",
      email: "dana@example.test",
      display_name: "דנה כהן",
      role: "shift_manager",
      created_at: "2099-01-02T09:00:00Z",
      phone: null,
      start_date: null,
      last_day: null,
      // The muted eligibility word renders only on a row that carries it, so
      // without this the copy is in the bundle and on no screen the sweep sees.
      shift_manager_eligible: true,
      photo_url: null,
      photo_confirmed_at: null,
    },
  ];
}

// The CONNECTED branch, which is the one with controls: a validate button, a
// disconnect button, three credential inputs and a save. `provider` is not
// "fake" so the sandbox note stays out of the way of the section's own markup.
export function gatewayStatus(): unknown {
  return {
    provider: "lemonsqueezy",
    configured: true,
    connected: true,
    status: "valid",
    last_validated_at: "2099-01-03T12:00:00Z",
    credential_fields: ["merchant_id", "api_key", "webhook_secret"],
  };
}

// One default section and one tenant-authored one, so BOTH badge variants and
// the single revert control render from one payload.
export function privacyPayload(): unknown {
  return {
    notice_text: "הבוטיק אוסף שם, טלפון והעדפות מדידה לצורך ניהול התורים בלבד.",
    notice_is_default: true,
    dpa_text: "המידע מעובד על ידי ספקי התשתית המפורטים למטה בלבד.",
    dpa_is_default: false,
    subprocessors_text: "אחסון: Hetzner (גרמניה)\nמסרונים: Twilio (אירלנד)",
    disclaimer_text: "הנוסחים כאן לא נבדקו על ידי עורך דין מטעם הבוטיק.",
    erase_reason_hint: "יש לתעד למה נמחק המידע, בלי לציין את פרטי הלקוחה.",
  };
}

// `dashboardPayload()` above stays every-number-zero: it is the OTHER journeys'
// default and exists so they do not open on somebody else's outage. This one is
// the axe sweep's, because the zero payload renders the day-one state — no
// `<table>`, no `<dl>`, no utilization bar, four cards saying «אין עדיין מספיק
// נתונים». Scanning that would be scanning almost nothing.
export function dashboardPopulated(): unknown {
  return {
    generated_on: "2099-01-04",
    history: {
      from_date: "2098-10-06",
      to_date: "2099-01-04",
      weeks: [
        { week_start: "2098-12-21", bookings: 4 },
        { week_start: "2098-12-28", bookings: 7 },
      ],
      status_totals: { confirmed: 2, cancelled: 3, no_show: 1, completed: 5 },
      cancellation_rate: 0.2727,
      cancelled_by_customer: 2,
      cancelled_by_owner: 1,
      no_show_rate: 0.1667,
      appointment_types: [{ appointment_type_id: "apt-1", name: "מדידה ראשונה", bookings: 9 }],
      customers: { total: 8, new: 3, returning: 5, repeat_rate: 0.625 },
    },
    forward: {
      from_date: "2099-01-04",
      to_date: "2099-01-31",
      capacity: 40,
      booked: 11,
      utilization: 0.275,
    },
  };
}

// --- F37: the SOS channel ----------------------------------------------------
//
// ⚠ THE DEFAULT STUB BELOW IS NOT THIS FEATURE'S CONVENIENCE, IT IS EVERY OTHER
// JOURNEY'S. F37 mounts `SosProvider` above `ConsoleShell` in `App.tsx`, so
// `GET /manage/floor/sos` now runs on ALL FOURTEEN sections, every few seconds,
// for the whole of every test in this directory. Without a default the harness
// answers its house 404 and each of those ticks fails — two failures put a
// persistent «ערוץ הקריאות אינו פעיל.» strip over the bottom of the screen, in a
// `role="alert"`, which reds every `getByRole("alert")` and every axe scan in
// this directory. Adding a surface means ADDING A STUB.

export interface SosAlert {
  id: string;
  status: string;
  raised_by: string;
  raised_by_name: string | null;
  target_staff_user_id: string | null;
  target_name: string | null;
  room_label: string | null;
  note: string | null;
  accepted_by: string | null;
  accepted_by_name: string | null;
  acknowledged_at: string | null;
  created_at: string;
  // Derived on the SERVER, per row, against the one `server_now` the envelope
  // carries — so a fixture sets them directly and no test has to sleep 30s or
  // freeze a clock to reach an escalated card.
  escalated: boolean;
  stalled: boolean;
  for_me: boolean;
}

// Five minutes before SERVER_NOW, so «מאז hh:mm» renders a real time and the
// centre's elapsed line renders «כבר 5 דק'» rather than the just-now branch.
export const RAISED_AT = "2099-01-04T07:55:00Z";

export function sosAlert(overrides: Partial<SosAlert> = {}): SosAlert {
  return {
    id: "sos-1",
    status: "open",
    raised_by: "st-raiser",
    raised_by_name: "רונית",
    target_staff_user_id: null,
    target_name: null,
    room_label: "חדר 2",
    note: null,
    accepted_by: null,
    accepted_by_name: null,
    acknowledged_at: null,
    created_at: RAISED_AT,
    escalated: false,
    stalled: false,
    // The default is TRUE because a fixture alert that does not rise proves
    // nothing: `for_me` is the whole audience rule and every journey here is
    // about a device the page reached.
    for_me: true,
    ...overrides,
  };
}

// ⚠ `unread` is F35's BELL COUNT and it rides THIS payload — the console's only
// app-wide tick. Defaulted to 0 so every shipped call site here is unchanged;
// `notifications.spec.ts` is the one that passes a number.
export function sosPayload(alerts: SosAlert[], unread = 0): unknown {
  return { alerts, server_now: SERVER_NOW, unread_notifications: unread };
}

// --- F35: the staff notification bell ----------------------------------------
//
// ⚠ NO NEW API FAMILY AND NO EDIT TO `API_FAMILIES`. Both bell paths keep
// `floor` as their second segment, which is already intercepted — so this block
// adds REPLIES and does not fork the harness. `test_spa_serving.py` is what
// keeps that true against the live route table.
//
// ⚠ NO CUSTOMER DATUM ON THIS SHAPE, EVER, and there is no field that could
// carry one: the wire row is two timestamps, a kind and a colleague's name.

export interface BellNotification {
  id: string;
  kind: string;
  actor_name: string | null;
  created_at: string;
  read_at: string | null;
}

export function bellNotification(
  overrides: Partial<BellNotification> = {},
): BellNotification {
  return {
    id: "nt-1",
    kind: "dispatch_assigned",
    actor_name: "דנה",
    created_at: ARRIVED_AT,
    read_at: null,
    ...overrides,
  };
}

export function bellList(items: BellNotification[]): unknown {
  return { items };
}

export function bellMarked(unread: number): unknown {
  return { unread };
}

// `rerouted` is a fact about THE REQUEST and not about the row, which is why the
// raise answers an envelope and the other three answer a bare alert.
export function raisedAlert(alert: SosAlert, rerouted = false): unknown {
  return { alert, rerouted };
}

// --- the atelier board (F41 + F42) -------------------------------------------

export interface AtelierSeamstress {
  id: string;
  display_name: string;
  assignable: boolean;
  weekly_capacity_hours: number | null;
  capacity_is_default: boolean;
  assigned_minutes: number;
  due_soon_minutes: number;
}

// The state every boutique is in on day one: nobody configured, nothing held.
export function atelierSeamstress(
  overrides: Partial<AtelierSeamstress> = {},
): AtelierSeamstress {
  return {
    id: "sm-1",
    display_name: "דנה",
    assignable: true,
    weekly_capacity_hours: null,
    capacity_is_default: false,
    assigned_minutes: 0,
    due_soon_minutes: 0,
    ...overrides,
  };
}

export interface AtelierTicket {
  id: string;
  customer_name: string;
  due_date: string;
  overdue: boolean;
  effort_minutes: number;
  assigned_staff_user_id: string | null;
  dress_id: string | null;
  dress_name: string | null;
  dress_size: string | null;
  notes: string | null;
  stage: string;
  intake_at: string | null;
  in_progress_at: string | null;
  qc_at: string | null;
  ready_at: string | null;
  delivered_at: string | null;
}

export function atelierTicket(overrides: Partial<AtelierTicket> = {}): AtelierTicket {
  return {
    id: "at-1",
    customer_name: "מיכל לוי",
    due_date: "2099-01-20",
    overdue: false,
    effort_minutes: 120,
    assigned_staff_user_id: null,
    dress_id: null,
    dress_name: null,
    dress_size: null,
    notes: null,
    stage: "intake",
    intake_at: "2099-01-04T07:00:00Z",
    in_progress_at: null,
    qc_at: null,
    ready_at: null,
    delivered_at: null,
    ...overrides,
  };
}

// The platform's five, resolved. ⚠ `due_soon_through` is the SERVER's horizon
// and the client cannot compute it: `lib/jerusalem.ts` ships zero date
// arithmetic, and a browser that has crossed Jerusalem midnight while the
// payload was held would print a date the SQL never filtered on.
export function atelierBoard(overrides: Record<string, unknown> = {}): unknown {
  return {
    tickets: [],
    seamstresses: [atelierSeamstress()],
    effort_bands: [
      { band: "thirty_min", minutes: 30 },
      { band: "one_hour", minutes: 60 },
      { band: "two_hours", minutes: 120 },
      { band: "half_day", minutes: 240 },
      { band: "full_day", minutes: 480 },
    ],
    truncated: false,
    unassigned_minutes: 0,
    default_weekly_capacity_hours: null,
    due_soon_through: "2099-01-11",
    ...overrides,
  };
}

// --- install -----------------------------------------------------------------

export interface ManageApiOptions {
  /** The identity `GET /manage/auth/me` answers. Default `staff()` — reception. */
  staff?: Staff;
  /**
   * Reply queues, merged OVER the defaults below. One mechanism for every route
   * the console speaks to: a later feature adds a key here rather than a switch
   * inside the handler.
   *
   * A key is a PATHNAME, or a method-qualified `"POST /manage/floor/sos"` which
   * wins over the bare pathname when both are present. ⚠ The qualified form is
   * not decoration: F37 is the first feature whose READ and whose CREATE share
   * one path, so a pathname-only table cannot answer a `SosResponse` to the poll
   * and a `RaisedAlert` to the raise.
   */
  replies?: Record<string, Reply[]>;
}

export async function installManageApi(
  page: Page,
  options: ManageApiOptions = {},
): Promise<Recorder> {
  const identity = options.staff ?? staff();
  const replies: Record<string, Reply[]> = {
    "/manage/auth/me": [ok(identity)],
    "/manage/floor": [ok(floorPayload())],
    // Fetched once on RoomsPanel's mount. An empty list is not an error state:
    // the arrivals picker is simply ABSENT, which is the ordinary early tile.
    "/manage/floor/clients": [ok({ clients: [], truncated: false })],
    "/manage/floor/dresses": [ok({ dresses: [], truncated: false })],
    // See the F37 block above: this one runs on every section of the console,
    // so its absence is a rendered alert on every other journey in this file.
    "/manage/floor/sos": [ok(sosPayload([]))],
    "/manage/dashboard": [ok(dashboardPayload())],
    "/manage/bookings": [ok({ items: [], total: 0, offset: 0, limit: 100 })],
    ...options.replies,
  };

  const all: RecordedRequest[] = [];

  await page.route(
    (url) => isManageApi(url.pathname),
    async (route) => {
      const request = route.request();
      const { pathname, search } = new URL(request.url());
      const raw = request.postData();
      let body: unknown = null;
      if (raw !== null) {
        try {
          body = JSON.parse(raw);
        } catch {
          body = raw;
        }
      }
      all.push({ method: request.method(), path: pathname, query: search, body });

      // The method-qualified key first, so a path whose GET and POST answer
      // different shapes can say so; the bare pathname is what every other
      // route uses and stays the default.
      const queue =
        replies[`${request.method()} ${pathname}`] ?? replies[pathname];
      const reply = queue === undefined ? NOT_FOUND : take(queue);
      await route.fulfill({
        status: reply.status,
        headers: { "content-type": "application/json", "cache-control": "no-store" },
        body: JSON.stringify(reply.body),
      });
    },
  );

  return { all, of: (path: string) => all.filter((entry) => entry.path === path) };
}

// --- path builders, mirroring apps/manage/src/api.ts -------------------------
//
// ⚠ `/manage/FLOOR/queue/…` and not `/manage/queue/…`: every console path's
// second segment has to stay one of the fourteen families above, or the dev
// proxy hands the call to the SPA and the response is `index.html`.

export function roomPath(roomId: string): string {
  return `/manage/floor/rooms/${encodeURIComponent(roomId)}`;
}

export function queuePath(ticketId: string): string {
  return `/manage/floor/queue/${encodeURIComponent(ticketId)}`;
}

// --- F22: the booking waitlist ------------------------------------------------
//
// `bookingWaitlistRow`, NOT `waitlistEntry` — that factory (above) is F58's
// walk-in queue row, a different table on a different surface (F-W2).

export interface BookingWaitlistRow {
  id: string;
  day: string;
  appointment_type_id: string;
  appointment_type_name: string | null;
  phone: string;
  customer_name: string | null;
  status: string;
  created_at: string;
  // F23. Null on every row that is not `offered` — the column renders «—» from
  // that, so an absent field would make the em dash a client guess.
  offer_starts_at: string | null;
  offer_expires_at: string | null;
}

export function bookingWaitlistRow(
  overrides: Partial<BookingWaitlistRow> = {},
): BookingWaitlistRow {
  return {
    id: "we-1",
    day: "2099-01-20",
    appointment_type_id: "apt-1",
    appointment_type_name: "מדידה ראשונה",
    phone: "+972501234567",
    customer_name: "נועה כהן",
    status: "waiting",
    created_at: ARRIVED_AT,
    offer_starts_at: null,
    offer_expires_at: null,
    ...overrides,
  };
}

// F23. A row the cascade has offered and a bride is holding right now: the slot
// at 13:30 Jerusalem, held until 11:15. ⚠ 20 January is WINTER — Asia/Jerusalem
// is UTC+2 (IST) on these instants, not the UTC+3 (IDT) it keeps in summer, so
// they read an hour earlier than the same UTC times would in July. Built ON
// bookingWaitlistRow rather than beside it, so a wire field added to one can
// never be missing from the other.
//
// The instants are UTC because the wire is UTC; the console renders them in
// Jerusalem, which is the whole point of asserting the rendered strings in the
// spec rather than these.
export function offeredWaitlistEntry(
  overrides: Partial<BookingWaitlistRow> = {},
): BookingWaitlistRow {
  return bookingWaitlistRow({
    id: "we-offered",
    customer_name: "רותם לוי",
    status: "offered",
    offer_starts_at: "2099-01-20T11:30:00Z",
    offer_expires_at: "2099-01-20T09:15:00Z",
    ...overrides,
  });
}

export function bookingWaitlist(entries: BookingWaitlistRow[]): unknown {
  return { entries };
}

export function bookingWaitlistCancelPath(entryId: string): string {
  return `/manage/waitlist/${encodeURIComponent(entryId)}/cancel`;
}

export function sosPath(alertId: string): string {
  return `/manage/floor/sos/${encodeURIComponent(alertId)}`;
}

export function capacityPath(staffUserId: string): string {
  return `/manage/atelier/seamstresses/${encodeURIComponent(staffUserId)}/capacity`;
}

// --- settling motion before a measurement ------------------------------------

/**
 * Waits for every BOUNDED animation on the page to finish.
 *
 * ⚠ **REQUIRED BEFORE ANY axe SCAN OR ANY `boundingBox()` TAKEN ON SOMETHING
 * THAT JUST APPEARED.** `Modal` fades and SCALES its panel (0.97 → 1) and fades
 * its `::backdrop`, and `toBeVisible()` resolves when the panel paints, not when
 * the transition ends. Scanning inside that window makes axe composite a
 * half-faded layer and report a contrast the page never renders at rest;
 * MEASURING inside it returns the transformed box, so a compliant 44px control
 * reads as 42.68px (44 × 0.97) and a touch-floor assertion fails on motion
 * rather than on a defect.
 *
 * ⚠ **INFINITE ANIMATIONS ARE FILTERED OUT.** `--animate-skeleton` and Button's
 * `animate-spin` never resolve `.finished`, and the console renders a Skeleton
 * in every section's loading state — awaiting one hangs until the test times
 * out. The 1s race is the belt to that braces.
 *
 * The same shape `notifications.spec.ts`, `waitlist.spec.ts` and
 * `platform.spec.ts` each inline; it lives here because F38 is the first feature
 * to need it in two files at once.
 */
export async function settleAnimations(page: Page): Promise<void> {
  await page.evaluate(async () => {
    const bounded = document
      .getAnimations()
      .filter((a) => a.effect?.getComputedTiming().iterations !== Infinity)
      .map((a) => a.finished);
    await Promise.race([
      Promise.allSettled(bounded),
      new Promise((resolve) => setTimeout(resolve, 1000)),
    ]);
  });
}

// --- F38: the staff photo pipeline -------------------------------------------

/** `/manage/staff/{id}`. The three photo routes hang off it: `/photo/presign`,
 *  `/photo/confirm` and `/photo` — the same composition `api.ts`'s staffPath
 *  does, so a reply key and the app's URL cannot spell the id differently. */
export function staffPath(staffId: string): string {
  return `/manage/staff/${encodeURIComponent(staffId)}`;
}

// ⚠ **THE PRESIGN URL IS SAME-ORIGIN, AND THAT IS A DECISION RATHER THAN A
// SHORTCUT.** `uploadToStorage` (apps/manage/src/api.ts) POSTs a FormData
// straight at whatever `url` the presign answered, with `credentials: "omit"`,
// no headers of its own, and it reads `response.ok` and never a body. Pointing
// it at a bucket origin would drag CORS into a test about the CONSOLE — a
// fulfilled cross-origin response has to carry its own ACAO header before
// `fetch` will even let the app see `ok` — and the app cannot tell the two
// apart. `/fixture-storage/…` is not a `/manage` path, so `isManageApi` leaves
// it alone and `installStorageUpload` below owns it outright.
export const STORAGE_UPLOAD_URL = "http://localhost:4174/fixture-storage/staff-photo";

export function staffPresign(overrides: Record<string, unknown> = {}): unknown {
  return {
    url: STORAGE_UPLOAD_URL,
    // Bearer material for its whole TTL in production. Non-empty here on
    // purpose: `uploadToStorage` appends every field to the FormData BEFORE
    // `file` (S3 ignores everything after it), and an empty object would leave
    // that loop unexercised.
    fields: { key: "tenants/t-1/staff/st-2/photo/ph-1.png", policy: "fixture-policy" },
    expires_in: 300,
    max_bytes: 2_097_152,
    ...overrides,
  };
}

export interface StorageUpload {
  /** How many multipart POSTs actually reached the fixture bucket. */
  count: number;
}

/**
 * Intercepts the presigned POST the browser makes DIRECTLY to storage — the one
 * call in this feature that never touches the API and is therefore invisible to
 * `installManageApi`'s recorder.
 *
 * `hold` is how a test parks the upload in flight: the «מעלה…» phase lasts
 * exactly as long as this request does, so an axe scan of it has no other way
 * to exist. Resolve the promise to let the upload finish.
 */
export async function installStorageUpload(
  page: Page,
  options: { hold?: Promise<unknown>; status?: number } = {},
): Promise<StorageUpload> {
  const record: StorageUpload = { count: 0 };
  await page.route(STORAGE_UPLOAD_URL, async (route) => {
    record.count += 1;
    if (options.hold !== undefined) {
      await options.hold;
    }
    // S3 answers 204 with an EMPTY body on success and XML on error, and
    // `uploadToStorage` parses neither — it reads `response.ok` and stops.
    await route.fulfill({ status: options.status ?? 204 });
  });
  return record;
}
