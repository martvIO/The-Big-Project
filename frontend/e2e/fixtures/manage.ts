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
  "auth",
  "availability",
  "bookings",
  "checkin-qr",
  "customers",
  "dashboard",
  "dresses",
  "floor",
  "gateway",
  "settings",
  "slots",
  "staff",
  "terms",
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

export interface StaffCard {
  id: string;
  display_name: string;
  role: string;
  status: string;
  break_started_at: string | null;
  occupancy: unknown;
}

export function staffCard(overrides: Partial<StaffCard> = {}): StaffCard {
  return {
    id: SELF_ID,
    display_name: "רונית",
    role: "reception",
    status: "available",
    break_started_at: null,
    occupancy: null,
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

// --- install -----------------------------------------------------------------

export interface ManageApiOptions {
  /** The identity `GET /manage/auth/me` answers. Default `staff()` — reception. */
  staff?: Staff;
  /**
   * Per-PATHNAME reply queues, merged OVER the defaults below. One mechanism for
   * every route the console speaks to: a later feature adds a key here rather
   * than a switch inside the handler.
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

      const queue = replies[pathname];
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
