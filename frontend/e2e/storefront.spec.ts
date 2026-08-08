import { test, expect } from "@playwright/test";
import type { Locator, Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

// The storefront under `vite preview` has no backend behind it — every
// /storefront/* GET is proxied at :8000 and refused, so each page falls into its
// error state. These specs therefore fulfil the three public endpoints from a
// fixture, which is what makes the *real* screens testable: the grid, the
// gallery, the hours card and the CTA bar only exist once data lands.
//
// a11y.spec.ts deliberately does NOT intercept — those five keep their value as
// the API-is-down pass.

const STOREFRONT = "http://localhost:4173";

// --- fixture -----------------------------------------------------------------

// A 3:4 SVG rather than a presigned S3 URL: it renders, it decodes, and — the
// point — it cannot 404, so the onError-means-refetch path stays out of the way
// of tests that are about something else.
function photo(fill: string): string {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="300" height="400"><rect width="300" height="400" fill="${fill}"/></svg>`;
  return `data:image/svg+xml,${encodeURIComponent(svg)}`;
}

const PHOTOS = [photo("#C5A059"), photo("#6B5D4F"), photo("#2B2118")];

// Far enough out that the presigned-URL TTL is never the reason a test moves.
const EXPIRES_AT = "2099-01-01T00:00:00Z";

// FLAT, matching BoutiqueResponse: no `profile` sub-object, and the weekly rules
// are `hours`. The nested shape the earlier fixture used no longer parses — the
// hours adapter walks `boutique.hours` and an undefined there throws out of
// render, which is a blank page, not a degraded one.
const BOUTIQUE = {
  name: "בוטיק ורד",
  essence: "שמלות כלה בעבודת יד",
  description: "בוטיק שמלות כלה בלב תל אביב, בתיאום מראש בלבד.",
  phone: "052-1234567",
  address: "הרצל 1, תל אביב",
  maps_url: "https://maps.google.com/?q=herzl+1",
  instagram: "vered.bridal",
  hours: [
    { day_of_week: 0, open_time: "10:00:00", close_time: "19:00:00" },
    { day_of_week: 1, open_time: "10:00:00", close_time: "19:00:00" },
    { day_of_week: 2, open_time: "10:00:00", close_time: "19:00:00" },
    { day_of_week: 3, open_time: "10:00:00", close_time: "19:00:00" },
    { day_of_week: 4, open_time: "10:00:00", close_time: "19:00:00" },
    { day_of_week: 5, open_time: "09:00:00", close_time: "13:00:00" },
  ],
  exceptions: [{ date: "2026-12-25", open_time: null, close_time: null, note: "חופשה" }],
  // F20's three privacy documents. REQUIRED on BoutiqueResponse — `resolve_privacy`
  // is total, so the wire always carries them — and the `details` step renders
  // `privacy_notice_text` through `substituteBoutique`, which calls `.split` on
  // it. An absent key here is `undefined.split`, which throws out of render: a
  // BLANK PAGE, exactly like the `hours` note above, and not a degraded one.
  // That is not hypothetical — omitting these three keys is what reds the nine
  // booking-flow tests below.
  //
  // Short, and deliberately NOT the approved Hebrew: `app/privacy/text.py` is the
  // single home for that, and a copy here would be a second place for a legal
  // string to drift. What they do carry are the two shapes the renderer handles —
  // the `{{boutique}}` token, and a blank-line paragraph break.
  // Three SHAPES, not three sentences: the `{{boutique}}` token, a blank-line
  // paragraph break, and a BULLET RUN. The third is what makes the WCAG 1.3.1
  // list assertions below — and every axe scan of this page — real; the three
  // shipped documents carry seventeen `•` lines between them.
  privacy_notice_text:
    "הודעת פרטיות של {{boutique}}.\n\nפסקה שנייה של ההודעה.\n\nהזכויות שלך:\n• לעיין\n• לתקן\n• למחוק",
  privacy_dpa_text: "תנאי עיבוד מידע של {{boutique}}.",
  privacy_subprocessors_text: "ספקי תשתית.",
};

// A tenant who filled in nothing but the name — the state a boutique is in on
// the day it is provisioned. Long enough to wrap the catalog h1 twice at 375,
// which is where a fixed-height header or a truncating utility shows up.
const LONG_NAME_BOUTIQUE = {
  ...BOUTIQUE,
  name: "הבוטיק של ורד — שמלות כלה בעבודת יד, תפירה אישית ומדידות בתיאום מראש בלב תל אביב",
};

// The five variants the storefront has to survive, expressed as five dresses
// rather than five fixture modes — one populated list exercises them all at once,
// and each detail route is reachable on its own.
const GALLERY = { id: "d-gallery", name: "ורד הלבן" }; // >= 3 photos, price shown
const HIDDEN = { id: "d-hidden", name: "ליל כלולות" }; // price_agorot omitted server-side
const RESERVED = { id: "d-reserved", name: "טוליפ" }; // the one badge the storefront renders
const BARE = { id: "d-bare", name: "אגם" }; // no photo -> monogram
const LONG = { id: "d-long", name: "שמלת משי מלכותית עם שובל ארוך במיוחד ורקמת פנינים בעבודת יד" };
const ARCHIVED_ID = "d-archived"; // soft-deleted -> 404 within the tenant

const LIST_ITEMS = [
  {
    id: GALLERY.id,
    name: GALLERY.name,
    price_agorot: 590000,
    reserved: false,
    cover: { url: PHOTOS[0], url_expires_at: EXPIRES_AT },
  },
  {
    // price_visible false server-side: the number is absent, not hidden in CSS.
    id: HIDDEN.id,
    name: HIDDEN.name,
    price_agorot: null,
    reserved: false,
    cover: { url: PHOTOS[1], url_expires_at: EXPIRES_AT },
  },
  {
    id: RESERVED.id,
    name: RESERVED.name,
    price_agorot: 420000,
    reserved: true,
    cover: { url: PHOTOS[2], url_expires_at: EXPIRES_AT },
  },
  { id: BARE.id, name: BARE.name, price_agorot: null, reserved: false, cover: null },
  {
    id: LONG.id,
    name: LONG.name,
    price_agorot: 1290000,
    reserved: false,
    cover: { url: PHOTOS[0], url_expires_at: EXPIRES_AT },
  },
];

// The server pins a page at 24 and the pilot ships ~60 dresses, so "עוד שמלות"
// is the only route to dress 25. 50 rather than 60 so the last page is a short
// one — that is where an offset computed from a page counter instead of from the
// items already held goes wrong.
const PAGE_LIMIT = 24;
const PAGED_ITEMS = Array.from({ length: 50 }, (_, index) => ({
  id: `d-paged-${String(index + 1)}`,
  name: `שמלה ${String(index + 1)}`,
  price_agorot: 100000 + index,
  reserved: false,
  cover: { url: PHOTOS[index % PHOTOS.length], url_expires_at: EXPIRES_AT },
}));

const DETAILS: Record<string, unknown> = {
  [GALLERY.id]: {
    id: GALLERY.id,
    name: GALLERY.name,
    description:
      "שמלת משי בגזרת A עם מחשוף לב עדין וכפתורי צדף לאורך הגב. " +
      "הרכבה נתפרת ידנית ומתאימה למידה מדויקת בפגישת המדידה השנייה. " +
      "השובל ניתן לקיצור, והצעיף נמכר בנפרד. " +
      "כל שמלה נבדקת לפני האיסוף ומגיעה בגיפה מוגנת אבק ובקולב עץ מקורי מהבוטיק.",
    price_agorot: 590000,
    reserved: false,
    sizes: [
      { size_label: "36", available: true },
      { size_label: "38", available: true },
      { size_label: "40", available: false },
    ],
    media: PHOTOS.map((url) => ({ url, url_expires_at: EXPIRES_AT })),
    // F28. Empty on four of the five; the fifth (RESERVED) carries a real
    // window, so this file's own scan renders the block at least once.
    unavailable_ranges: [],
  },
  [HIDDEN.id]: {
    id: HIDDEN.id,
    name: HIDDEN.name,
    description: null,
    price_agorot: null,
    reserved: false,
    sizes: [{ size_label: "38", available: true }],
    media: [{ url: PHOTOS[1], url_expires_at: EXPIRES_AT }],
    unavailable_ranges: [],
  },
  [RESERVED.id]: {
    id: RESERVED.id,
    name: RESERVED.name,
    description: null,
    price_agorot: 420000,
    reserved: true,
    sizes: [{ size_label: "36", available: false }],
    media: [{ url: PHOTOS[2], url_expires_at: EXPIRES_AT }],
    // The manual `reserved` badge AND a dated window on one dress: D5's two
    // states are orthogonal and both render.
    unavailable_ranges: [{ starts_on: "2099-08-12", ends_on: "2099-08-18" }],
  },
  [BARE.id]: {
    id: BARE.id,
    name: BARE.name,
    description: null,
    price_agorot: null,
    reserved: false,
    sizes: [],
    media: [],
    unavailable_ranges: [],
  },
  [LONG.id]: {
    id: LONG.id,
    name: LONG.name,
    description: null,
    price_agorot: 1290000,
    reserved: false,
    sizes: [{ size_label: "38", available: true }],
    media: [{ url: PHOTOS[0], url_expires_at: EXPIRES_AT }],
    unavailable_ranges: [],
  },
};

const NOT_FOUND_BODY = { error: { code: "NOT_FOUND", message: "לא נמצא" } };

type ListVariant = "populated" | "empty" | "paged";

// Every field but the name cleared. The backend collapses "" to null (the manage
// form seeds blanks to "" and submits them verbatim, so this is what an owner who
// saves the form once actually produces). Before that fix this fixture rendered
// `<a href="tel:">` with no accessible name on every route — a WCAG 2.4.4 (A)
// failure the fully-populated fixture could never see.
const CLEARED_BOUTIQUE = {
  ...BOUTIQUE,
  essence: null,
  description: null,
  phone: null,
  address: null,
  maps_url: null,
  instagram: null,
};

// --- booking fixture ---------------------------------------------------------
//
// The six endpoints the /book/* flow speaks to, none of which the catalog specs
// touch. Each is a QUEUE of replies consumed in order, the last entry repeating
// forever — one mechanism, because both mid-flow conflicts need exactly it: the
// terms GET answers v3 and then v4 across a TERMS_STALE recovery, and the
// booking POST answers 409 and then 201 across a SLOT_UNAVAILABLE one. A
// separate "fail once" switch would have been a second thing to keep in step.

interface Reply {
  status: number;
  body: unknown;
}

const ok = (body: unknown): Reply => ({ status: 200, body });

// The message is English on purpose — every backend message is. The flow keys
// off the CODE, so a fixture carrying Hebrew here would hide a UI that painted
// the server's sentence onto the page.
const conflict = (status: number, code: string): Reply => ({
  status,
  body: { error: { code, message: `${code} from the fixture.` } },
});

type BookingEndpoint =
  | "terms"
  | "appointment-types"
  | "slots"
  | "otp/send"
  | "otp/verify"
  | "bookings"
  // F16's tokenized manage surface. All three are POSTs, the lookup included:
  // a GET would put the manage token in the query string.
  | "booking/lookup"
  | "booking/confirm-attendance"
  | "booking/cancel"
  // F33's walk-in create. Its sibling read, /storefront/checkin/position, is
  // deliberately NOT here — see the ticket map below.
  | "checkin"
  // F59's public wall board. A POST like its two check-in siblings but for a
  // different reason: it carries no capability and no body at all. It belongs
  // in this queue map rather than beside the position read because its answer
  // does not depend on anything the caller sent — there is nothing to key on.
  | "queue";

const BOOKING_PATHS: Record<string, BookingEndpoint> = {
  "/storefront/terms": "terms",
  "/storefront/appointment-types": "appointment-types",
  "/storefront/slots": "slots",
  "/storefront/otp/send": "otp/send",
  "/storefront/otp/verify": "otp/verify",
  "/storefront/bookings": "bookings",
  "/storefront/booking/lookup": "booking/lookup",
  "/storefront/booking/confirm-attendance": "booking/confirm-attendance",
  "/storefront/booking/cancel": "booking/cancel",
  "/storefront/checkin": "checkin",
  "/storefront/queue": "queue",
};

type BookingReplies = Record<BookingEndpoint, Reply[]>;

const TYPE_PLAIN = {
  id: "t-fitting",
  name: "מדידה ראשונה",
  duration_minutes: 45,
  audience: "all",
  deposit_required: false,
  deposit_amount_agorot: null,
};

// D10's badge renders on the row unconditionally, so one brides-only sibling
// puts it in front of every axe scan of the slot step at no cost.
const TYPE_BRIDES = {
  id: "t-inspiration",
  name: "פגישת השראה",
  duration_minutes: 30,
  audience: "brides_only",
  deposit_required: false,
  deposit_amount_agorot: null,
};

// 2099 so nothing about these depends on today, on a TTL or on the machine's
// clock. Jerusalem is UTC+2 in January, so 08:00Z reads 10:00 to the bride —
// and the boutique's calendar day, never the device's, is what labels the grid.
const SLOT_1000 = "2099-01-04T08:00:00Z";
const SLOT_1045 = "2099-01-04T08:45:00Z";
const SLOT_1130 = "2099-01-04T09:30:00Z";
const SLOT_NEXT_DAY = "2099-01-05T08:00:00Z";

const TERMS_V3 = {
  version: 3,
  terms_text: "ביטול עד 48 שעות לפני המועד ללא חיוב.",
  refundable_until_hours_before: 48,
  forfeit_percent: 50,
};

// Every number differs from v3's, so "she is looking at the new policy" is
// measurable rather than assumed.
const TERMS_V4 = {
  version: 4,
  terms_text: "ביטול עד 24 שעות לפני המועד ללא חיוב.",
  refundable_until_hours_before: 24,
  forfeit_percent: 70,
};

const VERIFICATION_TOKEN = "vt-e2e";

const BOOKED = {
  id: "bk-e2e",
  starts_at: SLOT_1000,
  status: "confirmed",
  appointment_type_name: TYPE_PLAIN.name,
  dress_name: null,
  dress_size: null,
};

// --- F16 manage fixtures -----------------------------------------------------

const MANAGE_TOKEN = "mt-e2e-0123456789";

const MANAGE_BOUTIQUE = {
  name: BOUTIQUE.name,
  phone: BOUTIQUE.phone,
  address: BOUTIQUE.address,
  maps_url: BOUTIQUE.maps_url,
};

function manageBody(
  overrides: { status?: string; attendance_confirmed_at?: string | null } = {},
): unknown {
  return {
    booking: {
      starts_at: SLOT_1000,
      status: overrides.status ?? "confirmed",
      attendance_confirmed_at: overrides.attendance_confirmed_at ?? null,
      appointment_type_name: TYPE_PLAIN.name,
      dress_name: null,
      dress_size: null,
    },
    policy: {
      refundable_until_hours_before: TERMS_V3.refundable_until_hours_before,
      forfeit_percent: TERMS_V3.forfeit_percent,
    },
    boutique: MANAGE_BOUTIQUE,
  };
}

function slotBody(instants: string[]): unknown {
  return { slots: instants.map((starts_at) => ({ starts_at })) };
}

const ALL_SLOTS = [SLOT_1000, SLOT_1045, SLOT_1130, SLOT_NEXT_DAY];

// --- F33 walk-in queue fixtures ----------------------------------------------
//
// Ruling 3 removed server-side dedup entirely, so there is no null branch, no
// envelope and no already-in-queue reply to fixture: the create always creates
// and always answers a full TicketView. TWO ids because a second submission of
// the same phone mints a SECOND ticket — a one-element queue would answer the
// same id twice and hide the one thing the second journey exists to state.

const TICKET_FIRST = "qt-e2e-first";
const TICKET_SECOND = "qt-e2e-second";

// The whole wire shape of both check-in routes, and it is four fields. Nothing
// here names her, and nothing here is about anybody else's ticket.
function ticketBody(
  id: string,
  overrides: { status?: string; position?: number | null; called_at?: string | null } = {},
): unknown {
  return {
    id,
    status: overrides.status ?? "waiting",
    position: overrides.position === undefined ? 3 : overrides.position,
    called_at: overrides.called_at ?? null,
  };
}

// The position read is the ONE endpoint whose answer depends on WHICH ticket
// asked, so it is keyed off the request body instead of being a reply queue: the
// second journey leaves two live tickets behind it, and a queue consumed in
// order would hand the second ticket's body to the first ticket's page on
// whichever 5s poll tick happened to land first. Consecutive positions on
// purpose — that is exactly what Ruling 3 costs when one phone checks in twice,
// and the e2e should show it rather than smooth it over.
const QUEUE_TICKETS: Record<string, unknown> = {
  [TICKET_FIRST]: ticketBody(TICKET_FIRST, { position: 3 }),
  [TICKET_SECOND]: ticketBody(TICKET_SECOND, { position: 4 }),
};

// --- F59 wall-board fixtures -------------------------------------------------
//
// Five first names, distinct from each other AND from every other Hebrew string
// in this file — CUSTOMER_NAME is «נועה כהן», so «נועה» is deliberately not
// among them. A row that renders the wrong name is then named by the failure
// rather than merely counted.
//
// `called` is false on every entry and NO journey may drive it true: nothing
// writes called_at until F58, so a fixture that flipped it would assert a state
// the product has no path to.
const BOARD_NAMES = ["מיכל", "שירה", "תמר", "יעל", "אביגיל"];

// waitingTotal defaults to the row count, which is the no-overflow case. The
// board's own arithmetic (waiting_total − entries.length) is pinned in the unit
// suite; here the point is that five rows fit on a panel, so the two are equal.
function boardBody(count: number, waitingTotal = count): unknown {
  return {
    entries: BOARD_NAMES.slice(0, count).map((first_name, index) => ({
      position: index + 1,
      first_name,
      called: false,
    })),
    waiting_total: waitingTotal,
  };
}

function bookingFixture(): BookingReplies {
  return {
    terms: [ok(TERMS_V3)],
    "appointment-types": [ok([TYPE_PLAIN, TYPE_BRIDES])],
    slots: [ok(slotBody(ALL_SLOTS))],
    // 204, no body — the endpoint reveals nothing either way, by design.
    "otp/send": [{ status: 204, body: null }],
    "otp/verify": [ok({ verification_token: VERIFICATION_TOKEN, expires_at: SLOT_1000 })],
    bookings: [{ status: 201, body: BOOKED }],
    "booking/lookup": [ok(manageBody())],
    "booking/confirm-attendance": [
      ok(manageBody({ attendance_confirmed_at: "2099-01-03T08:00:00Z" })),
    ],
    "booking/cancel": [ok(manageBody({ status: "cancelled" }))],
    // 201 both times, same shape both times: the create has one outcome and the
    // second submission of one phone is not a different case.
    checkin: [
      { status: 201, body: ticketBody(TICKET_FIRST) },
      { status: 201, body: ticketBody(TICKET_SECOND) },
    ],
    // A constant, so the 5s poll answers the same board on every tick and the
    // route sweeps below get a settled page. The journeys that care about the
    // row count override it.
    queue: [ok(boardBody(3))],
  };
}

// The last entry repeats: a one-element queue is a constant, and a two-element
// one is "this happens once, then that".
function take(queue: Reply[]): Reply {
  return queue.length > 1 ? (queue.shift() as Reply) : queue[0];
}

async function installApi(
  page: Page,
  list: ListVariant = "populated",
  boutique: unknown = BOUTIQUE,
  booking: Partial<BookingReplies> = {},
  tickets: Record<string, unknown> = QUEUE_TICKETS,
): Promise<void> {
  const replies: BookingReplies = { ...bookingFixture(), ...booking };
  await page.route("**/storefront/**", async (route) => {
    const { pathname, searchParams } = new URL(route.request().url());
    const send = (body: unknown, status = 200) =>
      route.fulfill({
        status,
        // no-store mirrors the real endpoint: the media URLs in this body are
        // bearer material with a 900s TTL, so the response must never be cached.
        headers: { "content-type": "application/json", "cache-control": "no-store" },
        body: JSON.stringify(body),
      });

    if (pathname === "/storefront/boutique") {
      await send(boutique);
      return;
    }
    // Before the queue lookup, because it is answered from the body rather than
    // from a queue. An unseeded id is the 404 the page reads as "this ticket is
    // gone" — the same answer an unknown, swept or mistyped one gets.
    if (pathname === "/storefront/checkin/position") {
      const asked = (route.request().postDataJSON() as { ticket_id: string }).ticket_id;
      const seeded = tickets[asked];
      await send(seeded ?? NOT_FOUND_BODY, seeded ? 200 : 404);
      return;
    }
    const endpoint = BOOKING_PATHS[pathname];
    if (endpoint !== undefined) {
      const reply = take(replies[endpoint]);
      await (reply.status === 204
        ? route.fulfill({ status: 204, headers: { "cache-control": "no-store" } })
        : send(reply.body, reply.status));
      return;
    }
    if (pathname === "/storefront/dresses") {
      if (list === "paged") {
        // Honour the offset the page actually sent: a "more" button that keeps
        // asking for offset 0 would still grow the grid against a fixture that
        // ignored the parameter.
        const offset = Number(searchParams.get("offset") ?? "0");
        await send({
          items: PAGED_ITEMS.slice(offset, offset + PAGE_LIMIT),
          total: PAGED_ITEMS.length,
          offset,
          limit: PAGE_LIMIT,
        });
        return;
      }
      const items = list === "empty" ? [] : LIST_ITEMS;
      await send({ items, total: items.length, offset: 0, limit: PAGE_LIMIT });
      return;
    }
    const detail = DETAILS[pathname.slice("/storefront/dresses/".length)];
    // An unknown id, an archived dress and another tenant's dress are one and the
    // same 404 on the wire, by design.
    await send(detail ?? NOT_FOUND_BODY, detail ? 200 : 404);
  });
}

// --- shared locators ---------------------------------------------------------

// z-40 belongs to BookingCTA and to nothing else in either app (A11yMenu, Toast
// and SkipLink are z-50), so it is the one selector that distinguishes the *bar
// component* from a plain booking Button — which is exactly the distinction
// /about turns on: it ships the button and no bar.
const CTA_BAR = ".z-40";

const A11Y_TRIGGER = "תפריט נגישות";
const A11Y_STATEMENT = "הצהרת נגישות";
const CTA_LABEL = "קביעת תור למדידה";
const SKIP_LINK = "דלג לתוכן";
const MORE_LABEL = "עוד שמלות";

// StorefrontLayout's <main tabindex="-1">. The skip link targets it and the
// router moves focus here after every client navigation.
const MAIN_ID = "content";

function ctaBar(page: Page): Locator {
  return page.locator(CTA_BAR);
}

function a11yTrigger(page: Page): Locator {
  return page.getByRole("button", { name: A11Y_TRIGGER });
}

// The gallery's thumbnails are alt="" + aria-hidden, so the detail page exposes
// exactly ONE image to the accessibility tree — the main one. Its alt is the
// position string, which changes as the visitor pages, so it cannot be located
// by name without the locator going stale mid-test.
function galleryImage(page: Page): Locator {
  return page.getByRole("img");
}

// Cards are the only /dress/ links in <main>; the footer carries none. Counting
// them by destination is what makes "the next page appended" measurable.
function dressCards(page: Page): Locator {
  return page.locator(`#${MAIN_ID} a[href^="/dress/"]`);
}

// --- helpers -----------------------------------------------------------------

// The raw violation objects dump ~10 KB of axe internals into the failure. Only
// the rule id and the offending selectors say anything useful.
async function axeViolations(page: Page): Promise<string[]> {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  return results.violations.map(
    (v) => `${v.id} — ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`,
  );
}

// Each route's "the data landed" tell. Running axe against a skeleton passes
// vacuously, so every route waits on real content first.
async function gotoSettled(page: Page, path: string): Promise<void> {
  await page.goto(`${STOREFRONT}${path}`);
  if (path === "/") {
    // Present in both the populated and the empty state: BookingCTA renders as
    // soon as the fetch resolves, whether or not there are dresses.
    await expect(ctaBar(page)).toBeVisible();
  } else if (path.startsWith("/dress/")) {
    // NOT `heading level 1`: the loading state now carries an h1 too (the
    // boutique name, so a failed fetch never leaves the page untitled), which
    // would let this resolve against the skeleton and make the axe scans
    // vacuous — the exact thing this helper exists to prevent.
    await expect(page.getByTestId("dress-detail-loading")).toHaveCount(0);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  } else if (path === "/about") {
    await expect(page.getByRole("heading", { name: "שעות פעילות" })).toBeVisible();
  } else if (path === "/checkin") {
    // The submit, not the h1: the form is WITHHELD while the boutique fetch is
    // in flight and again if it fails, so the heading is up over a skeleton and
    // measuring it would measure nothing. Same trap gotoCheckin exists for —
    // these two constants are declared further down the file and read at call
    // time, which is after module evaluation.
    await expect(page.getByRole("button", { name: CHECKIN_SUBMIT })).toBeVisible();
  } else if (path.startsWith("/q/")) {
    // The number itself, which is the last thing the position read fills in.
    await expect(page.getByTestId("queue-number")).toBeVisible();
  } else if (path === "/queue") {
    // The freshness line and NOT a row: this helper is one if/else chain on the
    // path, so /queue gets exactly ONE tell for every journey that visits it —
    // and the empty board renders no row at all, so a row-based tell would time
    // out on the journey that exists to render it. The freshness line is present
    // in every non-loading state and is written only on a settled response,
    // which is precisely the "the data landed" property this helper asks for.
    await expect(page.getByTestId("queue-board-freshness")).toBeVisible();
  } else {
    // /accessibility has no loading state by design; the boutique name is what
    // arrives late and swaps in over the brand fallback. .first() because the
    // name legitimately appears twice — once as the site the statement covers,
    // once as the named accessibility contact while no platform coordinator is
    // configured (src/lib/coordinator.ts).
    await expect(page.getByText(BOUTIQUE.name).first()).toBeVisible();
  }
  await page.evaluate(() => document.fonts.ready);
}

interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

function intersectionArea(a: Rect, b: Rect): number {
  const w = Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x);
  const h = Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y);
  return w > 0 && h > 0 ? w * h : 0;
}

function describe(name: string, r: Rect): string {
  return `${name} x=${r.x.toFixed(1)} y=${r.y.toFixed(1)} w=${r.width.toFixed(1)} h=${r.height.toFixed(1)}`;
}

async function rect(locator: Locator, name: string): Promise<Rect> {
  const box = await locator.boundingBox();
  expect(box, `${name} has no bounding box`).not.toBeNull();
  return box as Rect;
}

// BookingCTA is only a bar if it is flush to the bottom edge and spans the
// viewport. Every overlap measurement below is vacuous otherwise — two boxes
// that are both in the wrong place trivially fail to intersect — so this is the
// precondition, not a separate nicety.
async function bottomBarRect(page: Page, viewport: { width: number; height: number }): Promise<Rect> {
  const bar = await rect(ctaBar(page), "BookingCTA bar");
  expect(
    { x: Math.round(bar.x), width: Math.round(bar.width), bottom: Math.round(bar.y + bar.height) },
    "BookingCTA is not laid out as a bottom bar",
  ).toEqual({ x: 0, width: viewport.width, bottom: viewport.height });
  return bar;
}

// How far an element sits from the viewport's *inline-start* edge. Stated this
// way rather than as "right", so the offset assertions below read the same under
// both directions and survive the document ever flipping to LTR.
async function inlineStartGap(page: Page, r: Rect): Promise<number> {
  const { dir, width } = await page.evaluate(() => ({
    dir: getComputedStyle(document.documentElement).direction,
    width: document.documentElement.clientWidth,
  }));
  return dir === "rtl" ? width - (r.x + r.width) : r.x;
}

function activeLabel(page: Page): Promise<string> {
  return page.evaluate(() => {
    const el = document.activeElement;
    if (!el || el === document.body) return "";
    return el.getAttribute("aria-label") ?? el.textContent?.trim() ?? "";
  });
}

// Where focus sits relative to the content region, in one round trip: `id` is
// the focused element's own id, `inside` says whether <main> contains it.
async function focusState(page: Page): Promise<{ id: string; inside: boolean; label: string }> {
  return page.evaluate((mainId) => {
    const el = document.activeElement;
    const main = document.getElementById(mainId);
    return {
      id: el?.id ?? "",
      inside: main !== null && el !== null && el !== document.body && main.contains(el),
      label: el?.getAttribute("aria-label") ?? el?.textContent?.trim().slice(0, 40) ?? "",
    };
  }, MAIN_ID);
}

// A box that clips its own text. Catches a fixed height with overflow:hidden, a
// line-clamp that survived a resize and a `truncate` on a heading — all of which
// eat descenders before they eat whole words, so they read as a rendering
// artefact rather than as missing content.
async function expectNotClipped(locator: Locator, name: string): Promise<void> {
  const box = await locator.evaluate((el) => {
    // scrollHeight/clientHeight are rounded integers of a fractional layout, and
    // they round in opposite directions: a 125.6px line box reports client 125
    // and scroll 126. Ceiling the fractional border box is the honest upper
    // bound — real clipping is a whole line or more, never one pixel.
    const rect = el.getBoundingClientRect();
    return {
      scrollHeight: el.scrollHeight,
      height: Math.max(el.clientHeight, Math.ceil(rect.height)),
      scrollWidth: el.scrollWidth,
      width: Math.max(el.clientWidth, Math.ceil(rect.width)),
    };
  });
  // Two pixels of slack: a glyph's ink legitimately extends a pixel past a
  // fractional line box without anything being cut, and scrollHeight rounds up
  // where clientHeight rounds down. Every clipping mechanism that loses actual
  // text — line-clamp, a fixed height with overflow:hidden, `truncate` — costs a
  // whole line or the tail of one, never a pixel.
  const CLIP_TOLERANCE = 2;
  expect(box.scrollHeight, `${name} is clipped vertically (descenders cut)`).toBeLessThanOrEqual(
    box.height + CLIP_TOLERANCE,
  );
  expect(box.scrollWidth, `${name} is clipped horizontally`).toBeLessThanOrEqual(
    box.width + CLIP_TOLERANCE,
  );
}

async function horizontalOverflow(page: Page): Promise<number> {
  return page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
}

// Keyboard only — no locator.focus(), which would prove nothing about tab order.
async function tabTo(page: Page, label: string, max = 60): Promise<void> {
  const seen: string[] = [];
  for (let i = 0; i < max; i++) {
    await page.keyboard.press("Tab");
    const current = await activeLabel(page);
    if (current === label) return;
    seen.push(current);
  }
  throw new Error(`Tab never reached "${label}" in ${String(max)} presses. Saw: ${seen.join(" › ")}`);
}

// --- axe: zero A/AA violations on every public route -------------------------

const AXE_ROUTES: [name: string, path: string, list: ListVariant, boutique?: unknown][] = [
  ["catalog", "/", "populated"],
  // The >= 3-photo dress on purpose: a single-photo Gallery hides its chrome, so
  // a one-photo detail page passes the gallery half of the audit vacuously.
  ["dress detail (3 photos)", `/dress/${GALLERY.id}`, "populated"],
  ["about", "/about", "populated"],
  ["accessibility statement", "/accessibility", "populated"],
  // F20. A statutory document is the one page on the storefront whose READER is
  // most likely to be using a screen reader, and it is three stacked h2 sections
  // of tenant-authored prose — the shape that grows heading-order and
  // contrast defects. This test's own title claims EVERY public route; without
  // this row that claim quietly stopped being true the day /privacy shipped.
  ["privacy notice", "/privacy", "populated"],
  ["catalog (empty state)", "/", "empty"],
  // A boutique with every profile field cleared — the nameless-link case.
  ["catalog (cleared profile)", "/", "populated", CLEARED_BOUTIQUE],
  ["about (cleared profile)", "/about", "populated", CLEARED_BOUTIQUE],
  ["accessibility statement (cleared profile)", "/accessibility", "populated", CLEARED_BOUTIQUE],
];

for (const [name, path, list, boutique] of AXE_ROUTES) {
  test(`storefront: zero axe A/AA violations — ${name}`, async ({ page }) => {
    await installApi(page, list, boutique ?? BOUTIQUE);
    await gotoSettled(page, path);
    const violations = await axeViolations(page);
    expect(violations).toEqual([]);
  });
}

// --- responsive --------------------------------------------------------------

// F33's two public routes are in this sweep and not only in their own block:
// spec D12 puts 375/768/1440-with-no-horizontal-scroll in the a11y floor it
// calls non-negotiable, and the storefront unit tests run in jsdom, which has no
// layout engine. The two shapes at risk are the wrapping visit-type chip row
// under the long Hebrew collection notice on /checkin, and the text-6xl position
// number beside the flex-wrap freshness+pause row on /q/{id}. installApi already
// seeds both; gotoSettled needed a tell for each.
//
// F59's /queue joins for the same reason. "The brief is a viewing distance, not
// a set of breakpoints" says nothing about horizontal overflow: the same public
// URL opens on the phone of every woman in the room, and its rows are a clamped
// number beside a clamped name in one flex line.
const ROUTES = [
  "/",
  `/dress/${GALLERY.id}`,
  "/about",
  "/accessibility",
  "/checkin",
  `/q/${TICKET_FIRST}`,
  "/queue",
  // F20 joins for the reason this list exists: its body is TENANT-AUTHORED text
  // rendered with [overflow-wrap:anywhere], and the one input the boutique fully
  // controls is exactly the one that produces an unbreakable 60-character token.
  // jsdom has no layout engine, so no vitest assertion can see this.
  "/privacy",
];

test("storefront: no horizontal scroll at 375 / 768 / 1440 on every route", async ({ page }) => {
  await installApi(page);
  for (const width of [375, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    for (const path of ROUTES) {
      await gotoSettled(page, path);
      const overflow = await horizontalOverflow(page);
      expect(overflow, `${path} overflows by ${String(overflow)}px at ${String(width)}px`).toBeLessThanOrEqual(0);
    }
  }
});

// --- PRE-1: fixed-element collision at 375 (qa-checklist §9, Critical) --------
//
// The design fix is the --space-a11y-clearance token; this is the build-time
// zero-overlap check it left open. Measured, not inferred from CSS: the whole
// point of the original defect was that the token looked right and the rects
// still intersected.

const PRE1_ROUTES: [name: string, path: string, list: ListVariant][] = [
  ["catalog", "/", "populated"],
  ["catalog (empty)", "/", "empty"],
  ["dress detail", `/dress/${GALLERY.id}`, "populated"],
];

const VIEWPORT_375 = { width: 375, height: 700 };

for (const [name, path, list] of PRE1_ROUTES) {
  test(`storefront PRE-1: A11yMenu trigger clears the BookingCTA bar @375 — ${name}`, async ({
    page,
  }) => {
    await page.setViewportSize(VIEWPORT_375);
    await installApi(page, list);
    await gotoSettled(page, path);

    const bar = await bottomBarRect(page, VIEWPORT_375);
    await expect(a11yTrigger(page), "the A11yMenu trigger is not on screen").toBeInViewport();
    const trigger = await rect(a11yTrigger(page), "A11yMenu trigger");

    expect(
      intersectionArea(trigger, bar),
      `${describe("trigger", trigger)} / ${describe("cta bar", bar)}`,
    ).toBe(0);
  });
}

// The original PRE-1 defect was a 60×44 bite out of the CTA taken by a button
// that measured right in CSS. So the sizes themselves are the other half of the
// check: a collapsed trigger cannot collide with anything, and cannot be tapped
// either (qa §8 — 44×44 minimum).
test("storefront: the @boutique/ui layout classes reach the built stylesheet @375", async ({
  page,
}) => {
  await page.setViewportSize(VIEWPORT_375);
  await installApi(page);
  await gotoSettled(page, "/");

  await bottomBarRect(page, VIEWPORT_375);

  const trigger = await rect(a11yTrigger(page), "A11yMenu trigger");
  expect(
    { width: Math.round(trigger.width), height: Math.round(trigger.height) },
    "the A11yMenu trigger is not a 44×44 touch target",
  ).toEqual({ width: 44, height: 44 });

  // DressGrid: 2 columns @375, 3 @768, 4 @1440.
  const columns = await page
    .locator(".grid")
    .first()
    .evaluate((el) => getComputedStyle(el).gridTemplateColumns.split(" ").length);
  expect(columns, "DressGrid is not two columns at 375").toBe(2);
});

// PRE-2: the same measurement on every route that carries the statutory link,
// not just the one with a CTA bar under it. /about and /accessibility reserve
// their own clearance instead of inheriting the bar's, so they are the two
// routes where the reservation can be deleted without any other test noticing.
//
// The bar half only applies where a bar exists; the trial click is the part that
// holds everywhere, and it is the falsifiable one — Playwright's hit-target test
// fails if the fixed A11yMenu, or anything else, is painted over the link.
for (const path of ["/", "/about", "/accessibility"]) {
  test(`storefront PRE-2: הצהרת נגישות clears the fixed chrome and is clickable @375, scrolled to the end — ${path}`, async ({
    page,
  }) => {
    await page.setViewportSize(VIEWPORT_375);
    await installApi(page);
    await gotoSettled(page, path);
    await page.evaluate(() => {
      window.scrollTo(0, document.documentElement.scrollHeight);
    });

    const link = page.getByRole("link", { name: A11Y_STATEMENT });
    const linkRect = await rect(link, "הצהרת נגישות link");
    const trigger = await rect(a11yTrigger(page), "A11yMenu trigger");

    if ((await ctaBar(page).count()) > 0) {
      const bar = await bottomBarRect(page, VIEWPORT_375);
      expect(
        intersectionArea(linkRect, bar),
        `${describe("link", linkRect)} / ${describe("cta bar", bar)}`,
      ).toBe(0);
    }
    expect(
      intersectionArea(linkRect, trigger),
      `${describe("link", linkRect)} / ${describe("a11y trigger", trigger)}`,
    ).toBe(0);

    // EVERY footer link, not only the statutory one. The footer wraps at 375
    // and the trigger sits at the inline-end block-end corner, so whichever
    // link lands last is the one under it — asserting only הצהרת נגישות passes
    // while the row beneath it is still covered.
    const footerLinks = page.locator("footer a");
    for (let i = 0; i < (await footerLinks.count()); i += 1) {
      const other = footerLinks.nth(i);
      const box = await rect(other, `footer link ${String(i)}`);
      expect(
        intersectionArea(box, trigger),
        `${describe(`footer link ${String(i)}`, box)} / ${describe("a11y trigger", trigger)}`,
      ).toBe(0);
    }

    // trial: true runs Playwright's actionability checks — including the
    // hit-target test — without following the link. A covered link fails here.
    await link.click({ trial: true });
  });
}

// --- exactly one BookingCTA per screen (qa-checklist §7) ---------------------

for (const width of [375, 768]) {
  test(`storefront: exactly one BookingCTA on / and /dress, none on /about @${String(width)}`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    await installApi(page);

    for (const path of ["/", `/dress/${GALLERY.id}`]) {
      await gotoSettled(page, path);
      await expect(ctaBar(page), `${path} @${String(width)}`).toHaveCount(1);
      await expect(ctaBar(page)).toBeVisible();
      await expect(page.getByRole("link", { name: CTA_LABEL })).toHaveCount(1);
      // One instance, two treatments: a fixed bottom bar below 768, inline from
      // 768 up. A bar that stays fixed at 768 leaves a dead gutter on desktop.
      const position = await ctaBar(page).evaluate((el) => getComputedStyle(el).position);
      expect(position, `${path} @${String(width)}`).toBe(width < 768 ? "fixed" : "static");
    }

    await gotoSettled(page, "/about");
    // /about ships the booking button as a static inline element and no bar —
    // nothing moves at 768.
    await expect(ctaBar(page), `/about @${String(width)}`).toHaveCount(0);
    await expect(page.getByRole("link", { name: CTA_LABEL })).toHaveCount(1);
  });
}

// --- WCAG 2.4.2 (Level A): per-route title on client navigation --------------

test("storefront: client navigation retitles the document without a reload", async ({ page }) => {
  await installApi(page);
  await gotoSettled(page, "/");
  await expect(page).toHaveTitle("הקולקציה");

  const catalogUrl = page.url();
  // A marker on the live window: it survives pushState and dies on a reload, so
  // it is the difference between a client navigation and a document swap.
  await page.evaluate(() => {
    (window as unknown as Record<string, unknown>).__sameDocument = true;
  });

  await page.getByText(GALLERY.name, { exact: true }).click();

  await expect(page).toHaveTitle(new RegExp(GALLERY.name));
  expect(page.url()).toBe(`${STOREFRONT}/dress/${GALLERY.id}`);
  expect(page.url()).not.toBe(catalogUrl);
  expect(
    await page.evaluate(() => (window as unknown as Record<string, unknown>).__sameDocument),
    "the DressCard click reloaded the document instead of navigating in place",
  ).toBe(true);

  await page.goBack();

  await expect(page).toHaveTitle("הקולקציה");
  expect(page.url()).toBe(catalogUrl);
  await expect(page.getByText(GALLERY.name, { exact: true })).toBeVisible();
  expect(
    await page.evaluate(() => (window as unknown as Record<string, unknown>).__sameDocument),
    "going back reloaded the document",
  ).toBe(true);
});

test("storefront: /about and /accessibility carry their own titles", async ({ page }) => {
  await installApi(page);
  await gotoSettled(page, "/about");
  await expect(page).toHaveTitle("על הבוטיק");
  await gotoSettled(page, "/accessibility");
  await expect(page).toHaveTitle(A11Y_STATEMENT);
});

// The test above enters each route with page.goto, which is a full document load
// — the browser parses index.html, React mounts, and the mount-time title write
// covers for a router that never retitles again. That is precisely the defect
// this walk exists to catch: in a Vite SPA the served <title> is index.html's
// forever unless something rewrites it per navigation, and axe's document-title
// rule is satisfied by the stale one. So every route below is reached by
// CLICKING, and the same walk pins the other two halves of the navigation
// contract that only a browser can observe: focus lands on #content, and the
// viewport is back at the top.
test("storefront: clicking through all four routes retitles, refocuses #content and resets scroll", async ({
  page,
}) => {
  // 375x600 so every route is genuinely taller than the viewport — a scroll
  // reset asserted on a page that cannot scroll proves nothing.
  await page.setViewportSize({ width: 375, height: 600 });
  await installApi(page);
  await gotoSettled(page, "/");
  await expect(page).toHaveTitle("הקולקציה");

  // A marker on the live window: it survives pushState and dies on a reload, so
  // it is the difference between a client navigation and a document swap.
  await page.evaluate(() => {
    (window as unknown as Record<string, unknown>).__sameDocument = true;
  });

  // All four routes, each ENTERED by a click. The catalog is in the list twice
  // over: once as the starting document, once as a destination, because a title
  // that is only ever correct on first paint is exactly the defect.
  //
  // `fromBottom` marks the links that sit low enough to be clicked from a
  // scrolled-down page, which is what makes the scroll-reset assertion mean
  // something. The dress page's back link is at the very top, so clicking it
  // scrolls the page to 0 by itself — that step asserts the title, the focus and
  // the no-reload marker, and says nothing about scrolling rather than asserting
  // a 0 it did not earn.
  const steps = [
    // The last card in the grid, so scrolling to the end of the page does not
    // have to be undone to reach it.
    {
      label: "dress card",
      target: page.getByRole("link", { name: LONG.name }),
      title: new RegExp(LONG.name),
      fromBottom: true,
    },
    {
      label: "חזרה לקולקציה",
      target: page.getByRole("link", { name: "חזרה לקולקציה" }),
      title: "הקולקציה",
      fromBottom: false,
    },
    {
      label: "footer על הבוטיק",
      target: page.getByRole("link", { name: "על הבוטיק" }),
      title: "על הבוטיק",
      fromBottom: true,
    },
    {
      label: "footer הצהרת נגישות",
      target: page.getByRole("link", { name: A11Y_STATEMENT }),
      title: A11Y_STATEMENT,
      fromBottom: true,
    },
  ];

  for (const { label, target, title, fromBottom } of steps) {
    await page.evaluate(() => {
      window.scrollTo(0, document.documentElement.scrollHeight);
    });
    await target.scrollIntoViewIfNeeded();
    const scrolledTo = await page.evaluate(() => window.scrollY);
    if (fromBottom) {
      expect(
        scrolledTo,
        `${label}: the page did not scroll, so the reset below is vacuous`,
      ).toBeGreaterThan(0);
    }

    await target.click();

    await expect(page, `${label} did not retitle the document`).toHaveTitle(title);
    if (fromBottom) {
      await expect
        .poll(() => page.evaluate(() => window.scrollY), {
          message: `${label} left the viewport where it was`,
        })
        .toBe(0);
    }
    expect(await focusState(page), `${label} did not move focus to #${MAIN_ID}`).toMatchObject({
      id: MAIN_ID,
    });
    expect(
      await page.evaluate(() => (window as unknown as Record<string, unknown>).__sameDocument),
      `${label} reloaded the document instead of navigating in place`,
    ).toBe(true);
  }
});

// --- skip link ---------------------------------------------------------------

test("storefront: the skip link actually moves focus into <main>, and the next Tab stays there", async ({
  page,
}) => {
  await installApi(page);
  await gotoSettled(page, "/");

  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: SKIP_LINK })).toBeFocused();

  await page.keyboard.press("Enter");
  const landed = await page.evaluate(() => ({
    tag: document.activeElement?.tagName ?? "",
    id: document.activeElement?.id ?? "",
  }));
  expect(landed).toEqual({ tag: "MAIN", id: MAIN_ID });

  // The half axe cannot see: a skip link that scrolls without moving focus
  // passes every automated audit and still drops the keyboard user back at the
  // top of the tab order, one Tab later. So the next Tab has to land INSIDE the
  // content region, not on the second item of the page chrome.
  await page.keyboard.press("Tab");
  const next = await focusState(page);
  expect(next.inside, `Tab after the skip link landed on "${next.label}", outside #${MAIN_ID}`).toBe(
    true,
  );
});

// The skip link is the first thing a keyboard user meets, and it is positioned
// only while focused — so a dead positioning utility here is invisible to every
// other check in this file, including axe.
test("storefront: the focused skip link is inset from the inline-start edge, not flush against it", async ({
  page,
}) => {
  await page.setViewportSize(VIEWPORT_375);
  await installApi(page);
  await gotoSettled(page, "/");

  await page.keyboard.press("Tab");
  const link = page.getByRole("link", { name: SKIP_LINK });
  await expect(link).toBeFocused();

  // `focus:inset-s-2 focus:top-2` — 8px in on both axes. A 0 gap means the
  // utility compiled to nothing and the box fell back to its static position.
  const linkRect = await rect(link, "skip link");
  expect({
    inlineStart: Math.round(await inlineStartGap(page, linkRect)),
    top: Math.round(linkRect.y),
  }).toEqual({ inlineStart: 8, top: 8 });
});

// --- gallery keyboard operability (qa-checklist §8) --------------------------

test("storefront: every gallery image is keyboard-reachable and aria-current tracks it", async ({
  page,
}) => {
  await installApi(page);
  await gotoSettled(page, `/dress/${GALLERY.id}`);

  const main = galleryImage(page);
  await expect(main).toHaveAttribute("src", PHOTOS[0]);

  // Reached by Tab + Enter alone — a swipe-only carousel would fail here.
  for (const n of [2, 3, 1]) {
    const label = `תמונה ${String(n)} מתוך 3`;
    await tabTo(page, label);
    await page.keyboard.press("Enter");
    await expect(main).toHaveAttribute("src", PHOTOS[n - 1]);
    // The main image's own label tracks the position too, so the announcement a
    // screen-reader user hears on the image matches the thumbnail they picked.
    await expect(main).toHaveAttribute("alt", label);
    await expect(page.locator('[aria-current="true"]')).toHaveAttribute("aria-label", label);
  }

  // The prev/next pair is the other keyboard route to the same images.
  await tabTo(page, "התמונה הבאה");
  await page.keyboard.press("Enter");
  await expect(main).toHaveAttribute("src", PHOTOS[1]);
  await expect(page.locator('[aria-current="true"]')).toHaveAttribute("aria-label", "תמונה 2 מתוך 3");

  await tabTo(page, "התמונה הקודמת");
  await page.keyboard.press("Enter");
  await expect(main).toHaveAttribute("src", PHOTOS[0]);
  await expect(page.locator('[aria-current="true"]')).toHaveAttribute("aria-label", "תמונה 1 מתוך 3");
});

// The keyboard test above drives the arrows by label, so it passes no matter
// where they are painted — which is how both arrows came to be stacked on the
// same 44×44 rect with `prev` fully buried under `next`, tappable by nobody.
test("storefront: the gallery arrows sit on opposite edges and are each tappable @375", async ({
  page,
}) => {
  await page.setViewportSize(VIEWPORT_375);
  await installApi(page);
  await gotoSettled(page, `/dress/${GALLERY.id}`);

  const prev = page.getByRole("button", { name: "התמונה הקודמת" });
  const next = page.getByRole("button", { name: "התמונה הבאה" });
  const image = await rect(galleryImage(page), "gallery image");
  const prevRect = await rect(prev, "prev arrow");
  const nextRect = await rect(next, "next arrow");

  expect(
    intersectionArea(prevRect, nextRect),
    `${describe("prev", prevRect)} / ${describe("next", nextRect)}`,
  ).toBe(0);

  // Opposite halves of the image, said without naming a side.
  const centre = (r: Rect) => r.x + r.width / 2;
  const mid = image.x + image.width / 2;
  expect(
    Math.sign(centre(prevRect) - mid),
    `both arrows are on the same side of the image — ${describe("prev", prevRect)} / ${describe("next", nextRect)}`,
  ).toBe(-Math.sign(centre(nextRect) - mid));

  // Only the middle of the set has both arrows enabled; reach it by keyboard so
  // the trial clicks below are the first thing that needs a real hit target.
  await tabTo(page, "תמונה 2 מתוך 3");
  await page.keyboard.press("Enter");
  await prev.click({ trial: true });
  await next.click({ trial: true });
});

// --- A11yMenu: the base experience and the boosted one both pass -------------

test("storefront: A11yMenu text-size boost keeps zero axe A/AA violations", async ({ page }) => {
  await installApi(page);
  await gotoSettled(page, "/");

  const base = await axeViolations(page);
  expect(base, "base experience").toEqual([]);

  await expect(a11yTrigger(page), "the A11yMenu trigger is not on screen").toBeInViewport();
  await a11yTrigger(page).click();
  await page.getByRole("button", { name: "הגדלת טקסט" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-a11y-text-size", "");

  // Selecting a control deliberately leaves the panel open, and this scan is only
  // an open-state scan for as long as that holds. Pinned, because a later
  // close-on-select would otherwise turn the assertion below into a second
  // closed-state scan without changing a line of it.
  await expect(page.getByRole("group"), "the panel closed on select").toBeVisible();

  const boosted = await axeViolations(page);
  expect(boosted, "text-size boost applied").toEqual([]);
});

// The open panel was unreachable by axe until the trigger became tappable, which
// is how a Level-A `aria-required-parent` failure — menuitemcheckbox with no
// enclosing role="menu" — survived every audit. Both scans above run closed; the
// one below is the state that was actually broken. The panel is now a disclosure
// of aria-pressed toggle buttons, which owes no menu keyboard contract at all.
test("storefront: the open A11yMenu keeps zero axe A/AA violations", async ({ page }) => {
  await page.setViewportSize(VIEWPORT_375);
  await installApi(page);
  await gotoSettled(page, "/");

  await a11yTrigger(page).click();
  const panel = page.getByRole("group");
  await expect(panel).toBeVisible();
  await expect(panel.getByRole("button")).toHaveCount(5);
  // A menu role would promise arrow-key roving focus this component never had.
  await expect(page.getByRole("menu")).toHaveCount(0);
  await expect(a11yTrigger(page)).toHaveAttribute("aria-expanded", "true");

  expect(await axeViolations(page), "A11yMenu open").toEqual([]);
});

// --- the states the storefront must not leak ---------------------------------

test("storefront: an archived dress is an unavailable message, not a broken page", async ({
  page,
}) => {
  await installApi(page);
  await page.goto(`${STOREFRONT}/dress/${ARCHIVED_ID}`);
  await expect(page.getByRole("alert")).toHaveText("השמלה כבר לא זמינה");
  // A 404 is terminal — retrying an archived dress just repeats it.
  await expect(page.getByRole("button", { name: "נסי שוב" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "חזרה לקולקציה" })).toBeVisible();
});

test("storefront: a failed boutique keeps its h1, and the retry actually recovers", async ({
  page,
}) => {
  // Identity itself fails. The degraded page must STILL carry exactly one <h1>:
  // it is where the skip link lands, and a page whose only heading vanishes on
  // an API error drops a screen-reader user into an untitled region. axe cannot
  // catch this — page-has-heading-one is best-practice, not an A/AA rule — so
  // it is asserted here or nowhere.
  let boutiqueOk = false;
  await page.route("**/storefront/**", async (route) => {
    const { pathname } = new URL(route.request().url());
    const send = (body: unknown, status = 200) =>
      route.fulfill({
        status,
        headers: { "content-type": "application/json", "cache-control": "no-store" },
        body: JSON.stringify(body),
      });
    if (pathname === "/storefront/boutique") {
      if (!boutiqueOk) {
        await send({ error: { code: "UNKNOWN", message: "boom" } }, 500);
        return;
      }
      await send(BOUTIQUE);
      return;
    }
    await send({ items: LIST_ITEMS, total: LIST_ITEMS.length, offset: 0, limit: PAGE_LIMIT });
  });

  await page.goto(`${STOREFRONT}/`);
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
  // D12: the CTA only navigates, so a failed identity fetch has nothing to make
  // it lie about and it must SURVIVE. Asserted on the href — a role check alone
  // would pass on a CTA that had lost its destination.
  await expect(page.getByRole("link", { name: CTA_LABEL })).toHaveAttribute("href", "/book/slot");

  // The retry must re-drive the BOUTIQUE fetch, not only the dress list. The
  // boutique block is fetched once by the layout, so a retry wired to the list
  // alone would look live and never change anything.
  boutiqueOk = true;
  await page.getByRole("button", { name: "נסי שוב" }).click();
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(page.getByRole("heading", { level: 1, name: BOUTIQUE.name })).toBeVisible();
  await expect(page.getByRole("link", { name: CTA_LABEL })).toBeVisible();
});

test("storefront: renders reserved, never out-of-stock, and never a raw quantity", async ({
  page,
}) => {
  await installApi(page);
  await gotoSettled(page, `/dress/${RESERVED.id}`);
  await expect(page.getByText("הוזמן")).toBeVisible();

  const body = (await page.locator("body").innerText()).toLowerCase();
  for (const banned of ["אזל", "out of stock", "quantity", "מלאי"]) {
    expect(body, `manage-only vocabulary "${banned}" reached the storefront`).not.toContain(banned);
  }
});

test("storefront: a hidden price renders the agreed-price label with no number", async ({ page }) => {
  await installApi(page);
  await gotoSettled(page, `/dress/${HIDDEN.id}`);
  await expect(page.getByText("מחיר בתיאום")).toBeVisible();
  await expect(page.locator("body")).not.toContainText("₪");
});

// --- alt text: position on the gallery, dress name on the card ---------------

test("storefront: the gallery main image is labelled by position, the card by dress name", async ({
  page,
}) => {
  await installApi(page);
  await gotoSettled(page, "/");
  // The CARD keeps the name: it is the only thing distinguishing one grid tile
  // from the next for a screen-reader user.
  await expect(
    page.getByRole("img", { name: GALLERY.name }),
    "the DressCard's alt is no longer the dress name",
  ).toHaveCount(1);

  await gotoSettled(page, `/dress/${GALLERY.id}`);
  // The GALLERY does not: eight photos all announcing "ורד הלבן" give no way to
  // tell one from another, while the thumbnails right below announce position
  // correctly.
  await expect(
    page.getByRole("img", { name: GALLERY.name }),
    "the gallery main image is announcing the dress name instead of its position",
  ).toHaveCount(0);
  await expect(galleryImage(page)).toHaveAttribute("alt", "תמונה 1 מתוך 3");
});

// --- load more (E2 criterion 3) ----------------------------------------------

test('storefront: "עוד שמלות" appends the next page and disappears at the end', async ({ page }) => {
  await installApi(page, "paged");
  await gotoSettled(page, "/");

  await expect(dressCards(page)).toHaveCount(PAGE_LIMIT);
  // Dress 25 is the whole point: without the button it is unreachable, and the
  // pilot's collection is ~60.
  await expect(page.getByRole("link", { name: "שמלה 25" })).toHaveCount(0);

  const more = page.getByRole("button", { name: MORE_LABEL });
  await expect(more).toBeVisible();
  await more.click();

  await expect(page.getByRole("link", { name: "שמלה 25" })).toBeVisible();
  await expect(dressCards(page)).toHaveCount(PAGE_LIMIT * 2);
  // 48 of 50 held: still short, so the button stays.
  await expect(more).toBeVisible();

  await more.click();
  await expect(dressCards(page)).toHaveCount(PAGED_ITEMS.length);
  await expect(page.getByRole("link", { name: `שמלה ${String(PAGED_ITEMS.length)}` })).toBeVisible();
  // Everything is on screen — a button that still offers "more" here asks for a
  // page the server will answer empty.
  await expect(more, "the load-more button survived the last page").toHaveCount(0);
});

// --- grid geometry: only a browser can measure this --------------------------

test("storefront: a photo-less card and its photographed row-mate are the same height @375", async ({
  page,
}) => {
  await page.setViewportSize(VIEWPORT_375);
  await installApi(page);
  await gotoSettled(page, "/");

  // Two columns at 375, so the fixture's four framed dresses fall as
  // [priced | agreed-price] then [photographed | photo-less].
  const rows: [name: string, a: string, b: string][] = [
    ["priced vs agreed-price", GALLERY.name, HIDDEN.name],
    ["photographed vs photo-less", RESERVED.name, BARE.name],
  ];

  for (const [label, first, second] of rows) {
    const a = await rect(page.getByRole("link", { name: first }), first);
    const b = await rect(page.getByRole("link", { name: second }), second);

    expect(Math.round(a.y), `${label}: the two cards are not in the same row`).toBe(Math.round(b.y));
    expect(
      Math.round(a.height),
      `${label}: ${describe(first, a)} / ${describe(second, b)}`,
    ).toBe(Math.round(b.height));

    // The media box is the half that can collapse without the grid noticing:
    // the row stretches its items, so two cards stay the same height even when
    // one of them has lost its aspect-ratio reservation and left a gap below.
    const media = await Promise.all(
      [first, second].map((name) =>
        page
          .getByRole("link", { name })
          .evaluate((el) => el.firstElementChild?.getBoundingClientRect().height ?? -1),
      ),
    );
    expect(media[0], `${label}: the photo slot and the monogram slot differ in height`).toBe(
      media[1],
    );
  }
});

// --- WCAG 1.4.4: 200% text, by zoom and by text-only resize ------------------

// /queue is a NEW member and F33's two routes are still not in it. The board is
// the one page in the product whose every type size is an arbitrary clamp()
// rather than a --text-* token, and each preferred value carries a rem term for
// exactly one reason: without it the A11yMenu's text-size boost is a complete
// no-op on this page. That makes the boost worth sweeping here, and the sweep is
// the only automated check that the rem terms do anything — axe measures no font
// size at all (Risk 4). TEXT_RESIZE_BROKEN_AT_375 stays empty: min-w-0 +
// [overflow-wrap:anywhere] + flex-wrap on the row is what keeps it that way.
const RESIZE_ROUTES = ["/", `/dress/${GALLERY.id}`, "/about", "/accessibility", "/queue"];
const WIDTHS = [375, 768, 1440];

// Two routes measurably fail 200% text-only resize at 375 today, both in
// production code this suite does not own:
//
//   /dress  — Gallery's thumbnail strip is three size-14 buttons plus two gaps
//             = 368px, and it does not shrink inside a 311px content box, so the
//             document scrolls 25px sideways.
//   /about  — the footer's <bdi dir="ltr">@handle</bdi> is a single unbreakable
//             Latin token 187px wide and overflows its flex line by 17px.
//
// They are pinned below as expected failures rather than quietly excluded: the
// day either one is fixed its case reports "expected to fail, but passed", and
// the annotation comes off. Every other cell of the matrix is a hard pass.
// Two WCAG 1.4.4 overflows used to live here as expected failures: the Gallery
// thumbnail strip (min-content 368px at 200% text) and the footer's unbreakable
// Instagram handle. Both are fixed — `min-w-0` on the strip so overflow-x-auto
// can engage, and min-w-0 + overflow-wrap:anywhere on the footer links — so the
// exclusion list is empty and every route is held to the same bar.
const TEXT_RESIZE_BROKEN_AT_375: string[] = [];

async function resizeTextTo200Percent(page: Page): Promise<void> {
  await page.evaluate(() => {
    document.documentElement.style.fontSize = "32px";
  });
}

// Text-only resize is the harder half of 1.4.4 and the one that actually breaks
// layouts: the viewport does NOT shrink, so every rem-sized box grows inside a
// container that did not. A px-height clamp, a fixed-height bar or a truncating
// heading all show up here and nowhere else.
test("storefront: 200% text-only resize (root 32px) keeps every route free of horizontal scroll", async ({
  page,
}) => {
  await installApi(page);
  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: 900 });
    for (const path of RESIZE_ROUTES) {
      if (width === 375 && TEXT_RESIZE_BROKEN_AT_375.includes(path)) continue;
      await gotoSettled(page, path);
      await resizeTextTo200Percent(page);
      const overflow = await horizontalOverflow(page);
      expect(
        overflow,
        `${path} overflows by ${String(overflow)}px at ${String(width)}px with 200% text`,
      ).toBeLessThanOrEqual(0);
    }
  }
});

// Browser zoom is not text-only resize: at 200% the CSS viewport HALVES, so a
// 375px layout is what a 750px device window renders when its owner zooms in.
// Driving it that way (rather than halving the design widths, which would demand
// a 187px layout no guideline asks for) is what makes this a real check — it
// catches anything sized against device pixels or a stale visual viewport,
// which a plain width sweep cannot see.
test("storefront: 200% browser zoom reflows to the same three widths without horizontal scroll", async ({
  page,
}) => {
  await installApi(page);
  for (const width of WIDTHS) {
    await page.setViewportSize({ width: width * 2, height: 1600 });
    for (const path of RESIZE_ROUTES) {
      await gotoSettled(page, path);
      await page.evaluate(() => {
        document.documentElement.style.zoom = "2";
      });
      const overflow = await horizontalOverflow(page);
      expect(
        overflow,
        `${path} overflows by ${String(overflow)}px at 200% zoom of ${String(width * 2)}px`,
      ).toBeLessThanOrEqual(0);
    }
  }
});

// The A11yMenu's own boost is a third path to bigger text, and the one a visitor
// who cannot find the browser's zoom will use. 375 only: it is the width where a
// boost has the least room to go anywhere.
test("storefront: the A11yMenu text-size boost keeps every route free of horizontal scroll @375", async ({
  page,
}) => {
  await page.setViewportSize(VIEWPORT_375);
  await installApi(page);
  for (const path of RESIZE_ROUTES) {
    await gotoSettled(page, path);
    await a11yTrigger(page).click();
    await page.getByRole("button", { name: "הגדלת טקסט" }).click();
    await expect(page.locator("html")).toHaveAttribute("data-a11y-text-size", "");

    const overflow = await horizontalOverflow(page);
    expect(
      overflow,
      `${path} overflows by ${String(overflow)}px with the text-size boost on`,
    ).toBeLessThanOrEqual(0);
  }
});

// --- long tenant-supplied strings --------------------------------------------

test("storefront: a long boutique name and a long dress name neither overflow nor clip", async ({
  page,
}) => {
  await installApi(page, "populated", LONG_NAME_BOUTIQUE);
  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: 900 });

    await gotoSettled(page, "/");
    const boutiqueHeading = page.getByRole("heading", { level: 1 });
    await expect(boutiqueHeading).toHaveText(LONG_NAME_BOUTIQUE.name);
    await expectNotClipped(boutiqueHeading, `boutique h1 @${String(width)}`);
    await expectNotClipped(
      page.getByRole("link", { name: LONG.name }),
      `long dress card @${String(width)}`,
    );
    let overflow = await horizontalOverflow(page);
    expect(overflow, `/ overflows by ${String(overflow)}px at ${String(width)}px`).toBeLessThanOrEqual(0);

    await gotoSettled(page, `/dress/${LONG.id}`);
    const dressHeading = page.getByRole("heading", { level: 1 });
    await expect(dressHeading).toHaveText(LONG.name);
    await expectNotClipped(dressHeading, `dress h1 @${String(width)}`);
    overflow = await horizontalOverflow(page);
    expect(
      overflow,
      `/dress overflows by ${String(overflow)}px at ${String(width)}px`,
    ).toBeLessThanOrEqual(0);
  }
});

// --- prefers-reduced-motion ---------------------------------------------------

test("storefront: reduced motion zeroes transitions and leaves scroll-snap alone", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await installApi(page);
  await gotoSettled(page, "/");

  // The DressCard photo is the one element in a populated catalog that declares
  // a transition, so it is the only place the media query can be observed. The
  // h1 has nothing to disable and would pass whatever the stylesheet said.
  const motion = await page.getByRole("img", { name: GALLERY.name }).evaluate((el) => {
    const style = getComputedStyle(el);
    return { transitionDuration: style.transitionDuration, animationName: style.animationName };
  });
  expect(motion).toEqual({ transitionDuration: "0s", animationName: "none" });

  // scroll-snap is a positioning affordance, not motion (qa §8), and the blanket
  // reduced-motion reset is exactly where it gets killed by accident. Nothing
  // ships a snap container today, so this probes the RULE: an inline snap loses
  // to a `scroll-snap-type: none !important` in that block and to nothing else.
  const snap = await page.evaluate((mainId) => {
    const el = document.getElementById(mainId);
    if (el === null) return null;
    el.style.setProperty("scroll-snap-type", "x mandatory");
    const computed = getComputedStyle(el).scrollSnapType;
    el.style.removeProperty("scroll-snap-type");
    return computed;
  }, MAIN_ID);
  expect(snap, "the reduced-motion block is stripping scroll-snap along with motion").toBe(
    "x mandatory",
  );
});

// =============================================================================
// F14 — the /book/* flow (spec §State matrix, design §11 / §12)
// =============================================================================
//
// The five steps are a state machine, not five URLs: D8's guard sends any step
// past `slot` with no picked time straight back to `slot`, so `details`,
// `terms` and `verify` are unreachable by page.goto and every scan below has to
// arrive there by WALKING. That is the reason for the one `walkBooking` helper
// and its per-step hook — the axe passes, the overflow sweep, the CTA-bar count
// and the Tab-order probe are all the same walk with a different hook.

const BOOK_TYPE = TYPE_PLAIN.name;
const SLOT_LABEL = "10:00";
const REPLACEMENT_SLOT_LABEL = "10:45";
const CONTINUE_LABEL = "המשך";
const SUBMIT_LABEL = "אישור וקביעת התור";
const SEND_CODE_LABEL = "שליחת קוד אימות";
const NAME_LABEL = "שם מלא";
const PHONE_LABEL = "טלפון נייד";
const CODE_LABEL = "קוד האימות";
const CUSTOMER_NAME = "נועה כהן";
const DATE_LABEL = "תאריך";
const NAME_REQUIRED = "צריך למלא שם כדי שנוכל לרשום את התור.";
const TYPED_PHONE = "050-123 4567";
const WIRE_PHONE = "+972501234567";
const OTP_CODE = "123456";

const SLOT_TAKEN_MESSAGE =
  "המועד הזה נתפס בינתיים. אלה המועדים הפנויים המעודכנים — אפשר לבחור מועד אחר.";
const TERMS_STALE_MESSAGE =
  "מדיניות הביטולים התעדכנה בזמן שמילאת את הפרטים. זו הגרסה המעודכנת — נשמח שתקראי ותאשרי אותה שוב.";
// F28, verbatim from apps/storefront/src/i18n/he.ts — a DATE problem, not a time
// one, which is why it does not reuse the slot copy.
const DRESS_UNAVAILABLE_MESSAGE = "השמלה אינה זמינה בתאריך שנבחר. אפשר לבחור תאריך אחר.";

// R1: the h1 is the STEP, never the boutique — a static i18n string, so it
// survives every degraded branch by construction. `confirm` is the one
// exception and takes the boutique's name, which is what makes a screenshot
// self-explanatory three weeks later.
const STEP_TITLES: Record<string, string> = {
  slot: "מועד",
  details: "פרטים",
  terms: "מדיניות ביטולים",
  verify: "אימות טלפון",
  confirm: `התור נקבע ב${BOUTIQUE.name}`,
};

// Which stepper item carries aria-current at each stop of the walk. `confirm`
// is terminal and outside the stepper, so it carries none.
const STEPPER_CURRENT: Record<string, string | null> = {
  slot: STEP_TITLES.slot,
  details: STEP_TITLES.details,
  terms: STEP_TITLES.terms,
  verify: STEP_TITLES.verify,
  "verify-code": STEP_TITLES.verify,
  confirm: null,
};

// Every chip in this flow is a native radio rendered sr-only inside the <label>
// that carries its visible text — so the label is what a finger lands on and
// what these click. Located by the radio it wraps rather than by its own text:
// nested elements with identical text make a bare getByText ambiguous.
function chip(page: Page, name: string): Locator {
  return page.locator("label").filter({ has: page.getByRole("radio", { name, exact: true }) });
}

function forwardButton(page: Page): Locator {
  return page.getByRole("button", { name: CONTINUE_LABEL });
}

// The three entry reads land together, and the slot step paints a skeleton Card
// under a live h1 while they are in flight — so the heading is NOT the tell. A
// scan against the skeleton would pass vacuously, which is the whole reason
// gotoSettled exists for the other routes.
async function gotoBooking(page: Page, path: string): Promise<void> {
  await page.goto(`${STOREFRONT}${path}`);
  await expect(page.getByRole("radio", { name: new RegExp(BOOK_TYPE) })).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
}

async function expectStep(page: Page, step: string, suffix = ""): Promise<void> {
  await expect(page).toHaveURL(`${STOREFRONT}/book/${step}${suffix}`);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(STEP_TITLES[step]);
}

// The `details` step, WALKED rather than deep-linked.
//
// ⚠ `page.goto("/book/details")` does NOT land on the details step: BookPage
// guards every step but slot/confirm/pay behind a chosen instant and redirects
// to `/book/slot`. The redirect is `replace: true`, so the URL settles silently
// and a test that deep-links is quietly asserting about the SLOT step — where
// there is no notice and no marketing box, which reads as "the element is
// missing" rather than "you are on the wrong screen". `expectStep` at the end is
// what makes that failure honest.
async function gotoDetails(page: Page): Promise<void> {
  await gotoBooking(page, "/book/slot");
  await page.getByRole("radio", { name: new RegExp(BOOK_TYPE) }).check();
  await chip(page, SLOT_LABEL).click();
  await forwardButton(page).click();
  await expectStep(page, "details");
}

// The forward pass, with a hook fired on each stop AFTER the step has rendered
// and BEFORE anything is typed into it. `verify` is visited twice — bare, and
// again once the code field, the polite region and the cooling resend button
// are all up, which is a materially different screen for axe and for layout.
//
// `landsOn` is where the submit is expected to arrive: `confirm` on the happy
// path, and the step a mid-flow conflict routes back to on the other two.
async function walkBooking(
  page: Page,
  options: {
    dressId?: string;
    size?: string;
    landsOn?: string;
    atStep?: (label: string) => Promise<void>;
  } = {},
): Promise<void> {
  const { dressId, size, landsOn = "confirm", atStep } = options;
  const suffix = dressId === undefined ? "" : `/${dressId}`;

  await gotoBooking(page, `/book/slot${suffix}`);
  await expectStep(page, "slot", suffix);
  await atStep?.("slot");
  await page.getByRole("radio", { name: new RegExp(BOOK_TYPE) }).check();
  await chip(page, SLOT_LABEL).click();
  await expect(page.getByRole("radio", { name: SLOT_LABEL, exact: true })).toBeChecked();
  await forwardButton(page).click();

  await expectStep(page, "details", suffix);
  await atStep?.("details");
  await page.getByLabel(NAME_LABEL).fill(CUSTOMER_NAME);
  if (size !== undefined) {
    await chip(page, size).click();
    await expect(page.getByRole("radio", { name: size, exact: true })).toBeChecked();
  }
  await forwardButton(page).click();

  await expectStep(page, "terms", suffix);
  await atStep?.("terms");
  await page.getByRole("checkbox").check();
  await forwardButton(page).click();

  await expectStep(page, "verify", suffix);
  await atStep?.("verify");
  await page.getByLabel(PHONE_LABEL).fill(TYPED_PHONE);
  await page.getByRole("button", { name: SEND_CODE_LABEL }).click();
  await page.getByLabel(CODE_LABEL).fill(OTP_CODE);
  await atStep?.("verify-code");
  await page.getByRole("button", { name: SUBMIT_LABEL }).click();

  await expectStep(page, landsOn, suffix);
  if (landsOn === "confirm") await atStep?.("confirm");
}

// Every POST body the flow put on the wire, in order. The payload is the only
// place the whole flow's accumulated state is observable at once — the picked
// type and instant, the accepted terms VERSION, the normalised phone, the token
// and the dress binding — so it is what the two happy-path tests assert on.
function captureBookings(page: Page): unknown[] {
  const posted: unknown[] = [];
  page.on("request", (request) => {
    if (new URL(request.url()).pathname === "/storefront/bookings") {
      posted.push(request.postDataJSON());
    }
  });
  return posted;
}

// --- §11 rows 1 + 20: the generic happy path ---------------------------------

test("storefront booking: the generic path walks all five steps to a confirmation", async ({
  page,
}) => {
  await installApi(page);
  const posted = captureBookings(page);
  const visited: string[] = [];

  await walkBooking(page, {
    atStep: async (label) => {
      visited.push(label);
      const current = STEPPER_CURRENT[label];
      const marked = page.locator('[aria-current="step"]');
      if (current === null) {
        // R2: the stepper is gone on the terminal screen, so nothing there is
        // still claiming to be a step of a flow she has finished.
        await expect(marked).toHaveCount(0);
      } else {
        await expect(marked).toHaveText(current);
      }
    },
  });

  expect(visited).toEqual(["slot", "details", "terms", "verify", "verify-code", "confirm"]);

  // D6: the record states the appointment in full, in the BOUTIQUE's calendar
  // (10:00 Jerusalem, from an 08:00Z instant), and promises no SMS.
  await expect(page.getByText(TYPE_PLAIN.name)).toBeVisible();
  await expect(page.getByText(SLOT_LABEL, { exact: true })).toBeVisible();
  // REWRITTEN by F16 (pre-decided #3): the screen no longer claims to be her
  // ONLY record, because a confirmation SMS now exists — but the screenshot
  // nudge stays, because at F16 ship time no provider is configured and kosher
  // phones never receive SMS at all.
  await expect(page.getByText("כדאי בכל זאת לצלם את המסך")).toBeVisible();
  const body = await page.locator("body").innerText();
  expect(body, "the confirmation still claims to be her only record").not.toContain("היחיד");
  // Still no delivery claim, in any tense: the copy may not promise a message
  // the product may not send.
  for (const promised of ["SMS", "מסרון"]) {
    expect(body, `the confirmation promises a message it will never send: ${promised}`).not.toContain(
      promised,
    );
  }

  expect(posted).toEqual([
    {
      phone: WIRE_PHONE,
      verification_token: VERIFICATION_TOKEN,
      name: CUSTOMER_NAME,
      appointment_type_id: TYPE_PLAIN.id,
      starts_at: SLOT_1000,
      terms_version: TERMS_V3.version,
      dress_id: null,
      dress_size: null,
      notes: null,
      // §30A default-off, proven ON THE WIRE rather than in the DOM. This walk
      // never touches the marketing checkbox, so `false` here is the whole
      // anti-detriment guarantee: the booking completed, and a consent she was
      // never asked for was not manufactured for her.
      //
      // This is an EXACT object assertion, not `objectContaining` like its four
      // siblings, and that is deliberate — a `useState(true)` slip reds this
      // line and only this line. It is also why the key must be present rather
      // than omitted: a missing key would pass under `objectContaining` and
      // prove nothing.
      marketing_consent: false,
    },
  ]);
});

// --- implicit submission, which only a real browser can measure --------------

// The walkthrough typed a valid name on /book/details and pressed Enter: no
// navigation, no error, no role=alert, no console output. It recorded
// `{hasForm:false, continueBtn:{type:'button', insideForm:false}}` — the flow
// was not a <form> at all, so a phone keyboard's Go key was dead on the last
// field and she had to Tab past the notes textarea AND the marketing checkbox to
// reach «המשך».
//
// ⚠ THIS TEST LIVES HERE AND NOT IN VITEST BECAUSE IT CANNOT LIVE THERE. jsdom
// does not implement implicit form submission, and this workspace ships no
// `@testing-library/user-event` to emulate it — so no jsdom assertion can press
// Enter and watch the step advance. `BookPage.test.tsx` asserts the STRUCTURE
// (a form exists, the control is type=submit, the field and the control share
// it) on every fast run; this is the only place the BEHAVIOUR is real.
//
// Mutation ledger, run against a real build of this file.
// ⚠ M2 AND M3 WERE OVERSTATED WHEN FIRST WRITTEN, and both are now what actually
// reproduced — the review that caught it is the same class of finding as the
// /fake-pay correction in LOOP-STATE.md: a claim nobody re-ran.
//   M1  `<ForwardForm>` reverted to the shipped `<>` fragment + a
//       `type="button"` control — this test reds, and the vitest structural test
//       reds with it.
//   M2  the forward control changed to `type="button" onClick={onForward}` — the
//       click path kept, only implicit submission killed. THIS TEST REDS AT THE
//       SLOT STEP (`/book/slot`, the date field). It does NOT red at details:
//       run in isolation, the second test below still passes under M2, because
//       the details step has exactly ONE field that blocks implicit submission
//       (the name text; a TextArea and a Checkbox block nothing) and HTML submits
//       a button-less form in that case. "All three red" was never true — the
//       first step failing is what stops the other two being reached.
//   M3  `noValidate` removed from ForwardForm — the SECOND test reds, not this
//       one. This test fills a VALID name, so constraint validation has nothing
//       to object to; the refusal case is where the native bubble replaces the
//       authored Hebrew. That is why the two tests are separate.
test("storefront booking: Enter in a field advances the step, on every step that has one", async ({
  page,
}) => {
  await installApi(page);

  // SLOT — Enter in the date field, the only text-shaped control on the step.
  await gotoBooking(page, "/book/slot");
  await page.getByRole("radio", { name: new RegExp(BOOK_TYPE) }).check();
  await chip(page, SLOT_LABEL).click();
  await page.getByLabel(DATE_LABEL).press("Enter");
  await expectStep(page, "details");

  // DETAILS — the step the walkthrough measured, and the one `noValidate`
  // decides: `required` on this very field would otherwise raise a native
  // bubble instead of running `forwardDetails`.
  await page.getByLabel(NAME_LABEL).fill(CUSTOMER_NAME);
  await page.getByLabel(NAME_LABEL).press("Enter");
  await expectStep(page, "terms");

  // TERMS — Enter on the consent checkbox. Space still toggles it; Enter is the
  // platform's «do the form's action», which is the same action «המשך» takes.
  await page.getByRole("checkbox").check();
  await page.getByRole("checkbox").press("Enter");
  await expectStep(page, "verify");
});

test("storefront booking: a bad name pressed through with Enter raises the AUTHORED error, not a native bubble", async ({
  page,
}) => {
  // The half `noValidate` exists for. Without it Chromium's own constraint
  // validation intercepts the submit and shows an untranslated LTR bubble, and
  // `forwardDetails` — which owns the Hebrew message, the role="alert" and the
  // focus move to the first failure — never runs at all.
  await installApi(page);
  await gotoDetails(page);

  await page.getByLabel(NAME_LABEL).press("Enter");

  await expectStep(page, "details");
  await expect(page.getByRole("alert").filter({ hasText: NAME_REQUIRED })).toBeVisible();
  await expect(page.getByLabel(NAME_LABEL)).toHaveAttribute("aria-invalid", "true");
  await expect(page.getByLabel(NAME_LABEL)).toBeFocused();
});

// --- §11 row 2: the item-based path ------------------------------------------

test("storefront booking: the item path carries the dress id through every step and books the size", async ({
  page,
}) => {
  await installApi(page, "populated", BOUTIQUE, {
    bookings: [{ status: 201, body: { ...BOOKED, dress_name: GALLERY.name, dress_size: "36" } }],
  });
  const posted = captureBookings(page);
  const paths: string[] = [];

  await walkBooking(page, {
    dressId: GALLERY.id,
    size: "36",
    atStep: async (label) => {
      paths.push(`${label}: ${new URL(page.url()).pathname}`);
      if (label === "details") {
        // The binding names itself once, where she can still change her mind
        // about the size — and it is NOT a link: leaving discards the draft.
        await expect(page.getByText(`עבור ${GALLERY.name}`)).toBeVisible();
        await expect(page.getByRole("link", { name: GALLERY.name })).toHaveCount(0);
      }
    },
  });

  // D9: the dress rides a path SEGMENT on every step, because the navigation
  // store snapshots pathname only and cannot see a query string.
  expect(paths).toEqual([
    `slot: /book/slot/${GALLERY.id}`,
    `details: /book/details/${GALLERY.id}`,
    `terms: /book/terms/${GALLERY.id}`,
    `verify: /book/verify/${GALLERY.id}`,
    `verify-code: /book/verify/${GALLERY.id}`,
    `confirm: /book/confirm/${GALLERY.id}`,
  ]);

  // dress_id and dress_size are a PAIR at the boundary or neither is sent.
  expect(posted).toEqual([
    expect.objectContaining({ dress_id: GALLERY.id, dress_size: "36" }),
  ]);
  await expect(page.getByText(`${GALLERY.name} · מידה 36`)).toBeVisible();
});

// --- §12.3: axe, per new route -----------------------------------------------

test("storefront booking: zero axe A/AA violations on every step of the flow", async ({ page }) => {
  await installApi(page);
  const failures: string[] = [];

  await walkBooking(page, {
    atStep: async (label) => {
      const violations = await axeViolations(page);
      if (violations.length > 0) failures.push(`${label} — ${violations.join(" | ")}`);
    },
  });

  expect(failures).toEqual([]);
});

// The item path's entry is the sixth pass §12.3 enumerates: it is the only URL
// shape carrying a second segment, and the only slot step that also renders a
// dress read. The cold confirmation is the other document-loadable /book URL —
// guard-exempt by design, so it is reachable by a stale bookmark or by the
// app-switch an iOS screenshot triggers.
test("storefront booking: zero axe A/AA violations on the item entry and the cold confirmation", async ({
  page,
}) => {
  await installApi(page);

  await gotoBooking(page, `/book/slot/${GALLERY.id}`);
  expect(await axeViolations(page), "the item path's entry").toEqual([]);

  await page.goto(`${STOREFRONT}/book/confirm`);
  // R14: no 201 and no way to fetch one, so it may not assert a booking it
  // cannot show — and it must not bounce her to step one either.
  await expect(page.getByText("אם השלמת את קביעת התור", { exact: false })).toBeVisible();
  await expect(page).toHaveURL(`${STOREFRONT}/book/confirm`);
  await page.evaluate(() => document.fonts.ready);
  expect(await axeViolations(page), "the cold confirmation").toEqual([]);
});

// --- responsive ---------------------------------------------------------------

test("storefront booking: no horizontal scroll at 375 / 768 / 1440 on every step", async ({
  page,
}) => {
  await installApi(page);
  const overflows: string[] = [];

  for (const width of [375, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await walkBooking(page, {
      atStep: async (label) => {
        const overflow = await horizontalOverflow(page);
        if (overflow > 0) {
          overflows.push(`${label} @${String(width)} overflows by ${String(overflow)}px`);
        }
      },
    });
  }

  expect(overflows).toEqual([]);
});

// --- skip link + the router's focus contract, on every step -------------------

test("storefront booking: every step lands focus on #content and keeps the skip link first in the tab order", async ({
  page,
}) => {
  await installApi(page);
  const problems: string[] = [];

  await walkBooking(page, {
    atStep: async (label) => {
      // Steps 2-5 are ENTERED by a client navigation, which is exactly when the
      // Router owes the focus move — a step reached with focus still on the
      // button that left the previous one drops a screen-reader user mid-form.
      // `slot` is the document load (the browser owns focus, and the skip link
      // is the first stop) and `verify-code` is a within-step state change that
      // deliberately puts focus in the code field.
      if (label !== "slot" && label !== "verify-code") {
        const landed = await focusState(page);
        if (landed.id !== MAIN_ID) {
          problems.push(`${label}: focus is on "${landed.label}", not #${MAIN_ID}`);
        }
      }

      if (label === "slot") {
        // A real document load, so the plain claim is measurable exactly as it
        // is on every other route: from the top, the first stop is the skip
        // link.
        await page.keyboard.press("Tab");
        const first = await activeLabel(page);
        if (first !== SKIP_LINK) problems.push(`${label}: the first Tab stop is "${first}"`);
        return;
      }

      // The middle steps cannot be document-loaded at all — the D8 guard
      // bounces a cold /book/details to /book/slot — and after a client
      // navigation there is no way back to the top of the tab order: Chromium's
      // sequential-focus starting point is <main>, and blur() does NOT reset it
      // (measured: a forward Tab lands on the back link, not the skip link).
      // So the falsifiable half of §12.3's claim here is the other one —
      // "nothing in this flow renders above it" — and Shift+Tab out of the
      // first content stop is what asks it.
      await page.evaluate((mainId) => {
        document.getElementById(mainId)?.focus();
      }, MAIN_ID);
      await page.keyboard.press("Tab");
      const firstInside = await focusState(page);
      if (!firstInside.inside) {
        problems.push(`${label}: Tab out of <main> landed on "${firstInside.label}", outside it`);
      }
      await page.keyboard.press("Shift+Tab");
      const above = await activeLabel(page);
      if (above !== SKIP_LINK) {
        problems.push(`${label}: "${above}" sits between the skip link and the content`);
      }
    },
  });

  expect(problems).toEqual([]);
});

// --- prefers-reduced-motion ---------------------------------------------------

test("storefront booking: reduced motion zeroes the flow's transitions", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await installApi(page);
  await gotoBooking(page, "/book/slot");

  // The forward Button is the one element on this step that declares a
  // transition at all, so it is the only place the media query is observable —
  // the h1 has nothing to disable and would pass whatever the stylesheet said.
  const motion = await forwardButton(page).evaluate((el) => {
    const style = getComputedStyle(el);
    return { transitionDuration: style.transitionDuration, animationName: style.animationName };
  });
  expect(motion).toEqual({ transitionDuration: "0s", animationName: "none" });
});

// --- Risk 6: /book/* ships no BookingCTA bar ----------------------------------
//
// hasBookingBar() is false for the whole flow, and until now that was asserted
// by reading the function rather than by looking at a rendered page. A bar here
// would be a control offering to start a booking she is three steps into, and
// it would lift the A11yMenu 92px over a page that reserved nothing for it.

test("storefront booking: /book/* renders no BookingCTA bar and no booking CTA @375", async ({
  page,
}) => {
  await page.setViewportSize(VIEWPORT_375);
  await installApi(page);
  const found: string[] = [];

  const assertNoBar = async (label: string) => {
    if ((await ctaBar(page).count()) > 0) found.push(`${label}: a z-40 bar`);
    if ((await page.getByRole("link", { name: CTA_LABEL }).count()) > 0) {
      found.push(`${label}: a booking CTA link`);
    }
  };

  await walkBooking(page, { atStep: assertNoBar });

  await gotoBooking(page, `/book/slot/${GALLERY.id}`);
  await assertNoBar("item entry");

  // The flow pays for the A11yMenu's footprint itself (BookPage's pb-16), since
  // there is no bar under it doing the reserving. Measured scrolled to the end,
  // which is where a too-small reservation shows up.
  await page.evaluate(() => {
    window.scrollTo(0, document.documentElement.scrollHeight);
  });
  const trigger = await rect(a11yTrigger(page), "A11yMenu trigger");
  const forwardRect = await rect(forwardButton(page), "forward button");
  expect(
    intersectionArea(forwardRect, trigger),
    `${describe("forward button", forwardRect)} / ${describe("a11y trigger", trigger)}`,
  ).toBe(0);

  expect(found).toEqual([]);
});

// --- D8: the browser back button walks the steps in reverse -------------------

test("storefront booking: the browser back button walks the steps in reverse, then leaves the flow", async ({
  page,
}) => {
  await installApi(page);
  await gotoSettled(page, "/");

  // Entered by the CTA rather than by goto, so the entry the back button
  // eventually walks out to is the catalog she actually came from.
  await page.getByRole("link", { name: CTA_LABEL }).click();
  await expect(page.getByRole("radio", { name: new RegExp(BOOK_TYPE) })).toBeVisible();
  await expectStep(page, "slot");

  await page.getByRole("radio", { name: new RegExp(BOOK_TYPE) }).check();
  await chip(page, SLOT_LABEL).click();
  await forwardButton(page).click();
  await expectStep(page, "details");
  await page.getByLabel(NAME_LABEL).fill(CUSTOMER_NAME);
  await forwardButton(page).click();
  await expectStep(page, "terms");
  await page.getByRole("checkbox").check();
  await forwardButton(page).click();
  await expectStep(page, "verify");

  // R26's caveat, honoured deliberately: navigate() is pushState-only, so a
  // mid-flow error RECOVERY grows the history stack and a clean back-out is not
  // promised after one. This is the plain forward walk, where every step pushed
  // exactly one entry — and that is the case D8 rules on.
  for (const step of ["terms", "details", "slot"]) {
    await page.goBack();
    await expectStep(page, step);
  }

  // The guard did not fire on the way back: her picked slot, her name and her
  // consent are all still held, so this was a walk and not three redirects to
  // step one wearing the right URLs.
  await expect(page.getByRole("radio", { name: SLOT_LABEL, exact: true })).toBeChecked();
  await forwardButton(page).click();
  await expectStep(page, "details");
  await expect(page.getByLabel(NAME_LABEL)).toHaveValue(CUSTOMER_NAME);
  await page.goBack();
  await expectStep(page, "slot");

  // Back out of the first step leaves the flow, and lands where she started.
  await page.goBack();
  await expect(page).toHaveURL(`${STOREFRONT}/`);
  await expect(page.getByRole("heading", { level: 1, name: BOUTIQUE.name })).toBeVisible();
});

// --- §11 row 10: the slot was taken while she typed ---------------------------

test("storefront booking: a slot taken mid-flow returns her to a fresh grid and books the replacement", async ({
  page,
}) => {
  await installApi(page, "populated", BOUTIQUE, {
    // The claim loses the race once; the second one wins.
    bookings: [
      conflict(409, "SLOT_UNAVAILABLE"),
      { status: 201, body: { ...BOOKED, starts_at: SLOT_1045 } },
    ],
    // The recovery's re-read must be the one that DROPS the taken time. A
    // fixture answering the same grid twice would pass against a UI that never
    // re-fetched anything.
    slots: [ok(slotBody(ALL_SLOTS)), ok(slotBody([SLOT_1045, SLOT_1130, SLOT_NEXT_DAY]))],
  });
  const posted = captureBookings(page);
  let otpSends = 0;
  page.on("request", (request) => {
    if (new URL(request.url()).pathname === "/storefront/otp/send") otpSends += 1;
  });

  // The submit does not reach the confirmation: the 409 routes her back to the
  // step that owns the fix, which is the picker she came from.
  await walkBooking(page, { landsOn: "slot" });

  await expect(page.getByRole("alert")).toHaveText(SLOT_TAKEN_MESSAGE);
  await expect(chip(page, SLOT_LABEL)).toHaveCount(0);
  // A lost race is not a restart of intent: the type she chose survives.
  await expect(page.getByRole("radio", { name: new RegExp(BOOK_TYPE) })).toBeChecked();

  await chip(page, REPLACEMENT_SLOT_LABEL).click();
  await forwardButton(page).click();
  await expectStep(page, "details");
  await expect(page.getByLabel(NAME_LABEL)).toHaveValue(CUSTOMER_NAME);
  await forwardButton(page).click();
  await expectStep(page, "terms");
  // The version did not change, so the consent she already gave still stands.
  await expect(page.getByRole("checkbox")).toBeChecked();
  await forwardButton(page).click();
  await expectStep(page, "verify");
  await page.getByRole("button", { name: SUBMIT_LABEL }).click();
  await expectStep(page, "confirm");

  expect(posted).toEqual([
    expect.objectContaining({ starts_at: SLOT_1000, verification_token: VERIFICATION_TOKEN }),
    expect.objectContaining({ starts_at: SLOT_1045, verification_token: VERIFICATION_TOKEN }),
  ]);
  // The token survived the failed claim — create_booking runs in one
  // transaction, so a claim that loses the race rolls its own token burn back
  // with it. Re-verifying would burn one of five hourly sends to re-prove what
  // the server never un-proved.
  expect(otpSends, "the recovery spent a second OTP send").toBe(1);
  await expect(page.getByText(REPLACEMENT_SLOT_LABEL, { exact: true })).toBeVisible();
});

// --- §11 row 11: the terms were republished mid-session -----------------------

test("storefront booking: republished terms are re-shown and re-accepted before the booking lands", async ({
  page,
}) => {
  await installApi(page, "populated", BOUTIQUE, {
    bookings: [conflict(409, "TERMS_STALE"), { status: 201, body: BOOKED }],
    terms: [ok(TERMS_V3), ok(TERMS_V4)],
  });
  const posted = captureBookings(page);

  await walkBooking(page, { landsOn: "terms" });

  await expect(page.getByRole("alert")).toHaveText(TERMS_STALE_MESSAGE);
  // The NEW text and the NEW numbers, not the ones she agreed to.
  await expect(page.getByText(TERMS_V4.terms_text)).toBeVisible();
  await expect(page.getByText(TERMS_V3.terms_text)).toHaveCount(0);
  // Unchecked by construction, not by an effect somebody remembered to write:
  // `accepted` is acceptedVersion === terms.version, and the version moved.
  // Carrying the tick forward would record agreement to text she never saw.
  await expect(page.getByRole("checkbox")).not.toBeChecked();

  await page.getByRole("checkbox").check();
  await forwardButton(page).click();
  await expectStep(page, "verify");
  await page.getByRole("button", { name: SUBMIT_LABEL }).click();
  await expectStep(page, "confirm");

  expect(posted).toEqual([
    expect.objectContaining({ terms_version: TERMS_V3.version }),
    expect.objectContaining({ terms_version: TERMS_V4.version }),
  ]);
});

// --- F28: the gown is booked out on that date ---------------------------------
//
// The THIRD create-time 409 and the only one that moves her NOWHERE. It lives
// here rather than in dress-reservation.spec.ts because the /book/* harness —
// six stubbed endpoints and the five-step walk — is here, beside its two sibling
// 409 branches; duplicating it into the feature file to keep the four surfaces
// in one place would be the deviation, not this. It is design §8's fourth
// axe-checked surface, and the axe pass is the reason it is a browser test:
// BookPage.test.tsx already pins the LOGIC in jsdom, which computes neither
// contrast nor accessible names.
test("storefront booking: a dress booked out on that date holds her on verify with its own copy", async ({
  page,
}) => {
  await installApi(page, "populated", BOUTIQUE, {
    bookings: [conflict(409, "DRESS_UNAVAILABLE")],
  });
  let slotReads = 0;
  let readsBeforeSubmit = -1;
  page.on("request", (request) => {
    if (new URL(request.url()).pathname === "/storefront/slots") slotReads += 1;
  });

  await walkBooking(page, {
    dressId: GALLERY.id,
    size: "36",
    landsOn: "verify",
    atStep: async (label) => {
      // The last hook before the submit click.
      if (label === "verify-code") readsBeforeSubmit = slotReads;
    },
  });

  await expect(page.getByRole("alert")).toHaveText(DRESS_UNAVAILABLE_MESSAGE);
  expect(await axeViolations(page), "the dress-unavailable error state").toEqual([]);

  // ⚠ DELIBERATELY NOT recoverSlot, and this is what proves it: D4's slot engine
  // has zero awareness of reservation windows, so a re-read would hand back the
  // same blocked day with the same times and every pick would fail identically.
  expect(slotReads, "the 409 refetched a grid that cannot fix this").toBe(readsBeforeSubmit);
  await expect(page).toHaveURL(`${STOREFRONT}/book/verify/${GALLERY.id}`);
});

// --- F16: the tokenized manage page `/b/{token}` ------------------------------
//
// The SMS is the only way in, so every spec below starts at a URL a bride pastes
// out of a text message. `installApi` fulfils the three manage POSTs; nothing
// here depends on the booking flow having run first, which is the point — she
// arrives weeks later, on a different device.

const MANAGE_TITLE = "התור שלך";
const CONFIRM_ATTENDANCE = "אישור הגעה";
const ATTENDANCE_DONE = "ההגעה אושרה. נתראה.";
const CANCEL_TRIGGER = "ביטול התור";
const CANCEL_QUESTION = "לבטל את התור?";
const CANCEL_CONFIRM = "אישור הביטול";
const CANCEL_KEEP = "השארת התור";
const CANCELLED_LINE = "התור בוטל.";
const REBOOK = "קביעת תור חדש";
const INVALID_LINE = "הקישור הזה כבר לא תקף.";
const MANAGE_RETRY = "ניסיון נוסף";

async function gotoManage(page: Page, token = MANAGE_TOKEN): Promise<void> {
  await page.goto(`${STOREFRONT}/b/${token}`);
  // Waits for real content, never the skeleton: an axe scan against a skeleton
  // passes vacuously, which is the same trap gotoSettled exists for.
  await expect(page.getByRole("heading", { level: 1, name: MANAGE_TITLE })).toBeVisible();
  await expect(page.getByRole("button", { name: CONFIRM_ATTENDANCE })).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
}

test("storefront manage: the link opens the appointment, confirms attendance and cancels", async ({
  page,
}) => {
  await installApi(page);
  const posted: { path: string; body: unknown }[] = [];
  page.on("request", (request) => {
    const { pathname } = new URL(request.url());
    if (pathname.startsWith("/storefront/booking/")) {
      posted.push({ path: pathname, body: request.postDataJSON() });
    }
  });

  await gotoManage(page);

  // The facts, in the BOUTIQUE's calendar: 10:00 Jerusalem from an 08:00Z
  // instant, exactly as the confirmation screen renders it.
  await expect(page.getByText(TYPE_PLAIN.name)).toBeVisible();
  await expect(page.getByText(SLOT_LABEL, { exact: true })).toBeVisible();
  // The accepted policy's window, not the current one.
  await expect(page.getByText(String(TERMS_V3.refundable_until_hours_before))).toBeVisible();

  await page.getByRole("button", { name: CONFIRM_ATTENDANCE }).click();
  await expect(page.getByText(ATTENDANCE_DONE).first()).toBeVisible();
  // Cancel STAYS available after attendance is confirmed (design P3).
  await expect(page.getByRole("button", { name: CANCEL_TRIGGER })).toBeVisible();

  // The two-step: the first tap reveals, and only the second cancels.
  await page.getByRole("button", { name: CANCEL_TRIGGER }).click();
  await expect(page.getByText(CANCEL_QUESTION)).toBeVisible();
  expect(
    posted.map((entry) => entry.path),
    "the reveal must not call the cancel endpoint",
  ).not.toContain("/storefront/booking/cancel");

  await page.getByRole("button", { name: CANCEL_CONFIRM }).click();
  await expect(page.getByText(CANCELLED_LINE).first()).toBeVisible();
  // The seat she freed is bookable again, and she is the likeliest person to
  // want it (design P4).
  await expect(page.getByRole("link", { name: REBOOK })).toHaveAttribute("href", "/book/slot");

  // The token travels in the BODY on all three calls, and never in a URL.
  expect(posted.map((entry) => entry.path)).toEqual([
    "/storefront/booking/lookup",
    "/storefront/booking/confirm-attendance",
    "/storefront/booking/cancel",
  ]);
  for (const entry of posted) {
    expect(entry.body).toEqual({ token: MANAGE_TOKEN });
    expect(entry.path, "the token reached the URL").not.toContain(MANAGE_TOKEN);
  }
});

test("storefront manage: the cancel reveal can be backed out of without cancelling", async ({
  page,
}) => {
  await installApi(page);
  await gotoManage(page);

  await page.getByRole("button", { name: CANCEL_TRIGGER }).click();
  await page.getByRole("button", { name: CANCEL_KEEP }).click();

  await expect(page.getByText(CANCEL_QUESTION)).toHaveCount(0);
  await expect(page.getByRole("button", { name: CANCEL_TRIGGER })).toBeFocused();
});

test("storefront manage: an already-cancelled appointment reads as cancelled, with no actions", async ({
  page,
}) => {
  await installApi(page, "populated", BOUTIQUE, {
    "booking/lookup": [ok(manageBody({ status: "cancelled" }))],
  });
  await page.goto(`${STOREFRONT}/b/${MANAGE_TOKEN}`);

  await expect(page.getByText(CANCELLED_LINE).first()).toBeVisible();
  // The facts stay — she may need the date to rebook.
  await expect(page.getByText(TYPE_PLAIN.name)).toBeVisible();
  await expect(page.getByRole("button", { name: CONFIRM_ATTENDANCE })).toHaveCount(0);
  await expect(page.getByRole("button", { name: CANCEL_TRIGGER })).toHaveCount(0);
});

test("storefront manage: an invalid link explains itself instead of dumping her on the catalog", async ({
  page,
}) => {
  // D7/D8: the page owns the invalid-link state, and the catalog fallthrough
  // must never swallow a bad token — a bride whose link was rotated would
  // otherwise land on a dress grid with no explanation.
  await installApi(page, "populated", BOUTIQUE, {
    "booking/lookup": [conflict(404, "BOOKING_LINK_INVALID")],
  });
  await page.goto(`${STOREFRONT}/b/no-such-token`);

  await expect(page.getByText(INVALID_LINE)).toBeVisible();
  await expect(page.getByRole("heading", { level: 1, name: MANAGE_TITLE })).toBeVisible();
  // No facts, no actions, no retry — an invalid link is not a transient failure.
  await expect(page.getByRole("button", { name: CONFIRM_ATTENDANCE })).toHaveCount(0);
  await expect(page.getByRole("button", { name: MANAGE_RETRY })).toHaveCount(0);
  // And never the server's English sentence on a Hebrew page.
  const body = await page.locator("body").innerText();
  expect(body).toMatch(/[֐-׿]/);
  expect(body, "the fixture's English error message reached the page").not.toContain(
    "BOOKING_LINK_INVALID",
  );
});

test("storefront manage: a throttled lookup offers a retry that recovers", async ({ page }) => {
  await installApi(page, "populated", BOUTIQUE, {
    "booking/lookup": [conflict(429, "TOO_MANY_ATTEMPTS"), ok(manageBody())],
  });
  await page.goto(`${STOREFRONT}/b/${MANAGE_TOKEN}`);

  await expect(page.getByRole("alert")).toBeVisible();
  await page.getByRole("button", { name: MANAGE_RETRY }).click();
  await expect(page.getByRole("button", { name: CONFIRM_ATTENDANCE })).toBeVisible();
});

test("storefront manage: zero axe A/AA violations in every state that has content", async ({
  page,
}) => {
  await installApi(page);
  await gotoManage(page);
  expect(await axeViolations(page), "loaded").toEqual([]);

  // The revealed cancel block is a materially different screen: a danger control
  // makes its first storefront appearance in it (design P5).
  await page.getByRole("button", { name: CANCEL_TRIGGER }).click();
  await expect(page.getByText(CANCEL_QUESTION)).toBeVisible();
  expect(await axeViolations(page), "cancel revealed").toEqual([]);

  await page.getByRole("button", { name: CANCEL_CONFIRM }).click();
  await expect(page.getByText(CANCELLED_LINE).first()).toBeVisible();
  expect(await axeViolations(page), "cancelled").toEqual([]);
});

test("storefront manage: the invalid-link state has zero axe A/AA violations", async ({ page }) => {
  await installApi(page, "populated", BOUTIQUE, {
    "booking/lookup": [conflict(404, "BOOKING_LINK_INVALID")],
  });
  await page.goto(`${STOREFRONT}/b/no-such-token`);
  await expect(page.getByText(INVALID_LINE)).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  expect(await axeViolations(page)).toEqual([]);
});

test("storefront manage: no horizontal scroll at 375 / 768 / 1440, reveal open", async ({
  page,
}) => {
  await installApi(page);
  for (const width of [375, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await gotoManage(page);
    await page.getByRole("button", { name: CANCEL_TRIGGER }).click();
    await expect(page.getByText(CANCEL_QUESTION)).toBeVisible();
    expect(await horizontalOverflow(page), `overflow at ${width}px`).toBe(0);
  }
});

test("storefront manage: the skip link is still the first Tab stop and lands in #content", async ({
  page,
}) => {
  await installApi(page);
  await gotoManage(page);

  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: SKIP_LINK })).toBeFocused();
  await page.keyboard.press("Enter");
  expect(
    await page.evaluate(() => ({
      tag: document.activeElement?.tagName ?? "",
      id: document.activeElement?.id ?? "",
    })),
  ).toEqual({ tag: "MAIN", id: MAIN_ID });
});

test("storefront manage: renders no BookingCTA bar @375", async ({ page }) => {
  // hasBookingBar() is catalog||dress, so the manage page reserves no gutter —
  // and a bar here would put a "book" CTA on a screen about an existing booking.
  await installApi(page);
  await page.setViewportSize({ width: 375, height: 900 });
  await gotoManage(page);
  await expect(ctaBar(page)).toHaveCount(0);
});

// =============================================================================
// F33 — the walk-in queue: /checkin and /q/{ticket_id}
// =============================================================================
//
// The QR taped to the shop window opens /checkin, and every well-formed submit
// mints a ticket and navigates straight to that ticket's own page. There is no
// second outcome — Ruling 3 deleted server-side dedup, so a phone that is
// already in the queue is answered exactly like one that is not — which is why
// the second journey below asserts a SECOND ticket rather than a refusal.

const CHECKIN_HEADING = "רישום לתור";
const VISIT_BRIDE = "מדידת כלה";
const CHECKIN_SUBMIT = "הצטרפות לתור";
const VISIT_TYPE_REQUIRED = "צריך לבחור סוג ביקור כדי להמשיך";
const LAST_FROM_DEVICE = "הרישום האחרון שנעשה מהמכשיר הזה";
const POSITION_HEADING = "מקומך בתור";
const WAITING = "ממתינה";
const UPDATED_AT = "עודכן";
const PAUSE = "השהיית העדכון";
const VISIT_CLOSED = "הביקור הזה הסתיים.";
const BACK_TO_CHECKIN = "רישום לתור חדש";

// The form is WITHHELD while the boutique fetch is in flight and again if it
// fails — both counsel-gated strings interpolate the controller's name — so the
// submit button, not the h1, is the tell that real content and not a skeleton is
// on screen. Same trap gotoSettled and gotoManage exist for.
async function gotoCheckin(page: Page): Promise<void> {
  await page.goto(`${STOREFRONT}/checkin`);
  await expect(page.getByRole("button", { name: CHECKIN_SUBMIT })).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
}

// Three fields and one button, located the way a woman standing in a doorway
// finds them: by their visible Hebrew labels. NAME_LABEL and PHONE_LABEL are the
// booking flow's own constants because they are the same two strings — if the
// surfaces ever diverge, this is where it shows.
async function fillCheckin(page: Page): Promise<void> {
  await page.getByLabel(NAME_LABEL).fill(CUSTOMER_NAME);
  await page.getByLabel(PHONE_LABEL).fill(TYPED_PHONE);
  await chip(page, VISIT_BRIDE).click();
  await expect(page.getByRole("radio", { name: VISIT_BRIDE, exact: true })).toBeChecked();
}

// The submit and the create's own response together. waitForResponse is armed
// BEFORE the click, so nothing here depends on how fast the fixture answers.
async function submitCheckin(page: Page): Promise<{ status: number; body: unknown }> {
  const [response] = await Promise.all([
    page.waitForResponse((r) => new URL(r.url()).pathname === "/storefront/checkin"),
    page.getByRole("button", { name: CHECKIN_SUBMIT }).click(),
  ]);
  return { status: response.status(), body: (await response.json()) as unknown };
}

function captureCheckins(page: Page): unknown[] {
  const posted: unknown[] = [];
  page.on("request", (request) => {
    if (new URL(request.url()).pathname === "/storefront/checkin") {
      posted.push(request.postDataJSON());
    }
  });
  return posted;
}

// --- journey 1: the happy path ------------------------------------------------

test("storefront check-in: the form mints a ticket and lands on that ticket's own position page", async ({
  page,
}) => {
  await installApi(page);
  const posted = captureCheckins(page);

  await gotoCheckin(page);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(CHECKIN_HEADING);
  await fillCheckin(page);
  const created = await submitCheckin(page);

  expect(created.status, "the create is a 201 with a ticket, always").toBe(201);
  await expect(page).toHaveURL(`${STOREFRONT}/q/${TICKET_FIRST}`);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(POSITION_HEADING);
  await expect(page.getByTestId("queue-number")).toHaveText("3");
  await expect(page.getByText(WAITING)).toBeVisible();
  // SC 2.2.2's mechanism, and the freshness line it belongs to, are both on
  // screen — axe has no rule for either, so a browser has to look.
  await expect(page.getByTestId("queue-freshness")).toContainText(UPDATED_AT);
  await expect(page.getByRole("button", { name: PAUSE })).toBeVisible();
  // hasBookingBar() is catalog-and-dress, so this route reserves no CTA gutter.
  await expect(ctaBar(page)).toHaveCount(0);

  // Four fields on the wire, the phone normalised on the client, and no fifth
  // thing — nothing about the device, the tab or any earlier visit.
  expect(posted).toEqual([
    { name: CUSTOMER_NAME, phone: WIRE_PHONE, visit_type: "bride", marketing_opt_in: false },
  ]);
  // The pointer is the ticket id and nothing else: no phone number ever reaches
  // the device's store (D8).
  expect(await page.evaluate(() => sessionStorage.getItem("checkin:ticket"))).toBe(TICKET_FIRST);
});

// ⚠ THE BEHAVIOURAL HALF OF `/checkin`'s <form>, and it can only live here.
// jsdom implements no implicit form submission, so `CheckinPage.test.tsx` can
// assert the structure and dispatch a synthetic `submit` — it can never press
// the key. And this is the ONE surface that is only ever used on a phone: the QR
// taped to the shop window, a woman standing in the doorway, the keyboard's Go
// key sitting where the submit button would be. It was dead until this branch.
//
// The booking flow got its <form> and this page did not, which is the drift the
// pair of tests below closes: same shape, same two proofs, one per surface.
//
// Mutation ledger, run against a real build of this file:
//   MC1  `type="submit"` on «הצטרפות לתור» -> `type="button" onClick={forward}`,
//        the <form> left in place — BOTH tests below red. The form then has no
//        submit button and TWO fields that block implicit submission (the name
//        text and the tel), which per HTML is the case where Enter does nothing
//        at all. The click path still works, so only these two catch it.
//   MC2  `noValidate` removed from the form — the SECOND test reds: the unchecked
//        `required` radios make Chromium raise its own untranslated bubble and
//        `forward` never runs, so the authored Hebrew, the role="alert" and the
//        focus move all vanish together. The first test stays green, because a
//        fully-filled form satisfies constraint validation — which is exactly
//        why the refusal case is asserted separately.
test("storefront check-in: Enter in the phone field mints the ticket, with no tap on the button", async ({
  page,
}) => {
  await installApi(page);
  const posted = captureCheckins(page);

  await gotoCheckin(page);
  await fillCheckin(page);

  // The last field she fills on a phone, and the one whose keyboard shows «Go».
  const [response] = await Promise.all([
    page.waitForResponse((r) => new URL(r.url()).pathname === "/storefront/checkin"),
    page.getByLabel(PHONE_LABEL).press("Enter"),
  ]);

  expect(response.status()).toBe(201);
  await expect(page).toHaveURL(`${STOREFRONT}/q/${TICKET_FIRST}`);
  // One create, not two: the implicit submission and the click must not both
  // fire, which is what `type="submit"` with no onClick buys.
  expect(posted).toEqual([
    { name: CUSTOMER_NAME, phone: WIRE_PHONE, visit_type: "bride", marketing_opt_in: false },
  ]);
});

test("storefront check-in: Enter with no visit type raises the AUTHORED refusal, not a native bubble", async ({
  page,
}) => {
  // The half `noValidate` exists for, and the reason it is not decoration: both
  // visit-type radios carry `required` on WCAG 3.3.2 grounds (no `*` marker), so
  // Chromium's own constraint validation would intercept this submit and show an
  // untranslated LTR bubble instead of running `forward`.
  await installApi(page);
  await gotoCheckin(page);

  await page.getByLabel(NAME_LABEL).fill(CUSTOMER_NAME);
  await page.getByLabel(PHONE_LABEL).fill(TYPED_PHONE);
  await page.getByLabel(PHONE_LABEL).press("Enter");

  await expect(page.getByRole("alert").filter({ hasText: VISIT_TYPE_REQUIRED })).toBeVisible();
  // Still on the form, and no request was ever issued.
  await expect(page).toHaveURL(`${STOREFRONT}/checkin`);
  await expect(page.getByRole("button", { name: CHECKIN_SUBMIT })).toBeVisible();
});

test("storefront check-in: zero axe A/AA violations — the form, the form in error, and the live position", async ({
  page,
}) => {
  await installApi(page);
  await gotoCheckin(page);
  expect(await axeViolations(page), "the form").toEqual([]);

  // Errors surface on submit and nowhere else, so this is the state she
  // actually meets: three live alerts wired to their own fields at once.
  await page.getByRole("button", { name: CHECKIN_SUBMIT }).click();
  await expect(page.getByText(VISIT_TYPE_REQUIRED)).toBeVisible();
  expect(await axeViolations(page), "the form in error").toEqual([]);

  await fillCheckin(page);
  await submitCheckin(page);
  await expect(page.getByTestId("queue-number")).toHaveText("3");
  await page.evaluate(() => document.fonts.ready);
  expect(await axeViolations(page), "the live position").toEqual([]);
});

test("storefront check-in: a finished visit says so, drops the pause control and offers a fresh check-in", async ({
  page,
}) => {
  // SEEDED, never driven. F33 ships no way to close a ticket — every status
  // transition is F58's — so a test written as "poll until it goes done" would
  // hang rather than fail.
  await installApi(
    page,
    "populated",
    BOUTIQUE,
    {},
    { [TICKET_FIRST]: ticketBody(TICKET_FIRST, { status: "done", position: null }) },
  );
  await page.goto(`${STOREFRONT}/q/${TICKET_FIRST}`);

  await expect(page.getByText(VISIT_CLOSED)).toBeVisible();
  await expect(page.getByTestId("queue-number")).toHaveCount(0);
  // Offering a pause for a loop that can never run again is a lie about the
  // page, so the whole freshness row goes with the terminal.
  await expect(page.getByRole("button", { name: PAUSE })).toHaveCount(0);
  await expect(page.getByTestId("queue-freshness")).toHaveCount(0);
  await expect(page.getByRole("link", { name: BACK_TO_CHECKIN })).toHaveAttribute(
    "href",
    "/checkin",
  );
  await page.evaluate(() => document.fonts.ready);
  expect(await axeViolations(page)).toEqual([]);
});

// --- journey 2: Ruling 3, the second check-in ---------------------------------

test("storefront check-in: a second check-in with the same phone mints a SECOND ticket and reads exactly like the first", async ({
  page,
}) => {
  await installApi(page);
  const posted = captureCheckins(page);

  await gotoCheckin(page);
  await fillCheckin(page);
  const first = await submitCheckin(page);
  await expect(page).toHaveURL(`${STOREFRONT}/q/${TICKET_FIRST}`);
  await expect(page.getByTestId("queue-number")).toHaveText("3");

  // Back to the form in the SAME tab, which is the only case the courtesy
  // pointer covers. It offers the last check-in made from this device — never a
  // claim to know where she is — and the form stays fully usable under it.
  await gotoCheckin(page);
  await expect(page.getByRole("link", { name: LAST_FROM_DEVICE })).toHaveAttribute(
    "href",
    `/q/${TICKET_FIRST}`,
  );

  // The same phone, deliberately. Under Ruling 3 this is not a duplicate to be
  // refused, de-duplicated or answered differently — it is a second walk-in.
  await fillCheckin(page);
  const second = await submitCheckin(page);

  await expect(page).toHaveURL(`${STOREFRONT}/q/${TICKET_SECOND}`);
  // A live ticket of its own, one place behind the first. That is the honest
  // cost of the ruling, on screen, rather than a state that says "you are
  // already in the queue" and hands over somebody's position.
  await expect(page.getByTestId("queue-number")).toHaveText("4");
  await expect(page.getByRole("button", { name: PAUSE })).toBeVisible();
  // Nothing refused anything, on either screen.
  await expect(page.getByRole("alert")).toHaveCount(0);

  // The two submissions carried the identical phone...
  expect(posted).toHaveLength(2);
  expect(posted[0], "the second submission changed something").toEqual(posted[1]);
  // ...and the two responses are indistinguishable on the wire: same status,
  // same key set, differing only in the id that was minted. THAT identity is the
  // security property — a stranger who submits a woman's mobile receives a
  // ticket of his own and learns nothing whatsoever about her. An `existing`
  // flag, a `ticket` envelope or a second status code all redden here.
  const keys = (body: unknown) => Object.keys(body as Record<string, unknown>).sort();
  expect(second.status).toBe(first.status);
  expect(keys(first.body)).toEqual(["called_at", "id", "position", "status"]);
  expect(keys(second.body)).toEqual(keys(first.body));
  expect((second.body as { id: string }).id).not.toBe((first.body as { id: string }).id);

  // Every create overwrites the pointer, so it names the most recent check-in
  // from this tab and never an older one.
  expect(await page.evaluate(() => sessionStorage.getItem("checkin:ticket"))).toBe(TICKET_SECOND);
});

// =============================================================================
// F59 — the public wall board: /queue
// =============================================================================
//
// A television on the wall of a boutique, read from three to five metres by a
// room of strangers, on an anonymous unauthenticated endpoint. It is the most
// privacy-sensitive surface in the product, so these journeys are as much about
// what the page does NOT put in the DOM as about what it renders.
//
// ⚠ NOTHING IS EVER HIGHLIGHTED. called_at has no writer until F58, so `called`
// is false on every fixture entry here and no journey may drive it true — a
// journey that did would assert a state the product cannot reach, which is the
// class of vacuous test the whole spec was reviewed against.
//
// ⚠ "no surname appears anywhere on the page" is DELIBERATELY NOT ASSERTED. The
// wire is {position, first_name, called}; there is no field a surname could ride
// on, the truncation is server-side, and installApi supplies the board body
// directly — so the derivation under test never runs in a browser. Its real
// homes are the two backend tests (the fast board_display_name table and the
// db-marked name="NOA COHEN" case). An assertion that cannot fail is worse than
// no assertion, because it reads like coverage.

const BOARD_HEADING = "ממתינות בתור";
const BOARD_EMPTY = "אין כרגע ממתינות";
const BOARD_EMPTY_HINT = "אפשר להצטרף לתור בסריקת הקוד שבבוטיק.";
const BOARD_PAUSED_AT = "העדכון מושהה. עודכן";

// A 1080p panel, which is the only geometry the deck's millimetre arithmetic is
// written against and the one the kiosk checklist requires (a 4K panel must
// present this CSS viewport, via DPR 2 or 200% zoom).
const VIEWPORT_1080P = { width: 1920, height: 1080 };

// Every title, aria-label and data-* across the row subtrees, deduplicated. The
// board's whole risk is a field the eye cannot see: a title carrying the full
// name, an aria-label built from more than the row shows, a data-ticket-id left
// behind by a debugging session. All three are invisible on a wall and all three
// are readable by anyone who opens the same public URL.
async function rowMetadata(rows: Locator): Promise<string[]> {
  const found = await rows.evaluateAll((els) =>
    els.flatMap((el) =>
      [el, ...el.querySelectorAll("*")].flatMap((node) =>
        [...node.attributes]
          .filter(
            (a) => a.name === "title" || a.name === "aria-label" || a.name.startsWith("data-"),
          )
          .map((a) => `${a.name}=${a.value}`),
      ),
    ),
  );
  return [...new Set(found)].sort();
}

// --- journey 1: the live board ------------------------------------------------

test("storefront wall board: three waiting rows, their positions, and nothing else about the women in them", async ({
  page,
}) => {
  await installApi(page, "populated", BOUTIQUE, { queue: [ok(boardBody(3))] });
  await gotoSettled(page, "/queue");

  await expect(page.getByRole("heading", { level: 1 })).toHaveText(BOARD_HEADING);

  const rows = page.getByTestId("queue-board-row");
  await expect(rows).toHaveCount(3);

  for (const [index, name] of BOARD_NAMES.slice(0, 3).entries()) {
    const row = rows.nth(index);
    // The position gutter is the <bdi dir="ltr">; the name is the bare one, and
    // dir="ltr" on a Hebrew name would itself be the bidi defect.
    await expect(row.locator("bdi[dir='ltr']")).toHaveText(String(index + 1));
    // toHaveText is a FULL-string match after whitespace normalisation, so a row
    // that rendered anything beside the first name reddens here.
    await expect(row.locator("bdi:not([dir])")).toHaveText(name);
  }

  expect(await rowMetadata(rows), "a row carries text the room cannot see").toEqual([
    "data-testid=queue-board-row",
  ]);

  // hasBookingBar() is catalog-and-dress, so this route reserves no CTA gutter —
  // and a "book a fitting" bar fixed across a television is a control nobody in
  // the room can press.
  await expect(ctaBar(page)).toHaveCount(0);

  // SC 2.2.2 in a real browser. Axe has no rule for any of it, and the pause is
  // also what makes the axe scan below deterministic — a 5s poll repainting
  // under an analyze() run is the one flake this file could grow.
  const freshness = page.getByTestId("queue-board-freshness");
  const live = (await freshness.textContent()) ?? "";
  await page.getByRole("button", { name: PAUSE }).click();
  await expect(freshness).toContainText(BOARD_PAUSED_AT);
  expect(
    (await freshness.textContent()) ?? "",
    "pausing did not change the freshness SENTENCE — a state carried by styling alone",
  ).not.toBe(live);

  expect(await axeViolations(page)).toEqual([]);
});

// --- journey 2: the empty board -----------------------------------------------

test("storefront wall board: the empty board is a designed state with its own axe pass", async ({
  page,
}) => {
  // Post-F58 this is the state the screen is in for most of the day; pre-F58 it
  // is the first hour, because nothing ever leaves the queue.
  await installApi(page, "populated", BOUTIQUE, { queue: [ok(boardBody(0))] });
  await gotoSettled(page, "/queue");

  await expect(page.getByTestId("queue-board-row")).toHaveCount(0);
  await expect(page.getByTestId("queue-board-empty")).toBeVisible();
  await expect(page.getByText(BOARD_EMPTY)).toBeVisible();
  await expect(page.getByText(BOARD_EMPTY_HINT)).toBeVisible();
  // Both render here too, and they have to: without the freshness line an empty
  // board and a crashed board are the same blank screen, and a 2.2.2 mechanism
  // that disappears with the content is not a mechanism.
  await expect(page.getByTestId("queue-board-freshness")).toBeVisible();
  await expect(page.getByRole("button", { name: PAUSE })).toBeVisible();
  await expect(ctaBar(page)).toHaveCount(0);

  expect(await axeViolations(page)).toEqual([]);
});

// --- journeys 2b and 2c: the board's REMAINING render branches (F21 B6) -------
//
// Plan C1. `public-queue-board.md`'s A29 asks for zero violations on every
// MATERIALLY DIFFERENT state, and the spec's claim that /queue had none was
// half wrong: journeys 1 and 2 above already close the populated and the empty
// board, both through this file's shared `axeViolations` with no
// `.disableRules()` and no `.exclude()`. So the residual was DERIVED from
// `QueueBoardPage.tsx`'s own render branches rather than assumed, and it is
// exactly two — the same two the plan predicted:
//
//   loading   — transient, a role="status" line with no controls; the page is
//               never in it once `gotoSettled` has resolved, so it is not a
//               scannable state.
//   populated — journey 1.  ✔ shipped
//   empty     — journey 2.  ✔ shipped
//   overflow  — `hidden > 0` adds the «ועוד N בתור» line, which NO other state
//               renders.  ← below
//   failed    — `view.kind === "failed"` adds a role="alert" AND a retry button,
//               and it is the only branch on this route with an interactive
//               control that is not the pause.  ← below
//
// A third scan of the populated DOM would have been coverage theatre; these two
// are not the same DOM.

const BOARD_OVERFLOW = "ועוד 35 בתור";
const BOARD_FAILED = "לא הצלחנו להציג את לוח התור כרגע.";
const BOARD_RETRY = "ניסיון נוסף";
const BOARD_RESUME = "חידוש העדכון";

test("storefront wall board: the overflow line is a state of its own and has its own axe pass", async ({
  page,
}) => {
  // Five rows fit a panel; forty women are in the queue. The board must say so
  // without scrolling, paging or moving — and the count is COMPUTED
  // (waiting_total − entries.length), so 40 − 5 = 35.
  await installApi(page, "populated", BOUTIQUE, { queue: [ok(boardBody(5, 40))] });
  await gotoSettled(page, "/queue");

  await expect(page.getByTestId("queue-board-row")).toHaveCount(5);
  await expect(page.getByTestId("queue-board-overflow")).toHaveText(BOARD_OVERFLOW);

  // The same 2.2.2 pause journey 1 takes, and for the same reason: a 5s poll
  // repainting under an analyze() run is the one flake this file could grow.
  await page.getByRole("button", { name: PAUSE }).click();
  await expect(page.getByTestId("queue-board-freshness")).toContainText(BOARD_PAUSED_AT);

  expect(await axeViolations(page)).toEqual([]);
});

test("storefront wall board: the outage arm is a designed state with its own axe pass", async ({
  page,
}) => {
  // The FIRST request fails and nothing ever loaded, which is the arm that
  // renders the alert and the retry control. A constant reply queue means every
  // 5-60s retry fails too, so the state is stable under the scan rather than
  // flipping mid-analyze.
  await installApi(page, "populated", BOUTIQUE, {
    queue: [{ status: 503, body: { error: { code: "SERVICE_UNAVAILABLE", message: "down" } } }],
  });

  // ⚠ NOT `gotoSettled`, and the reason is a property of the page rather than a
  // convenience. That helper's ONE /queue tell is the freshness line, and in
  // THIS arm the freshness line is deliberately EMPTY: `updatedAt` is null until
  // the first success, and `freshness()` returns null rather than rendering the
  // bare lead «עודכן » — «the page's only honesty signal claiming an update that
  // never happened, at the name scale, on a wall, for as long as the server is
  // down» (QueueBoardPage.tsx:275-288). The <span> is present and zero-sized, so
  // `toBeVisible` times out. The alert is this state's own tell.
  await page.goto(`${STOREFRONT}/queue`);

  // ⚠ THE ANTI-VACUITY LEG. A board that rendered nothing at all would also
  // score zero violations — and «a blank screen reads as אין ממתינות and a woman
  // acts on it» is the exact failure QueueBoardPage.tsx:456-462 exists to
  // prevent. So the alert and the retry control are asserted present before
  // anything is scanned.
  await expect(page.getByRole("alert")).toHaveText(BOARD_FAILED);
  await expect(page.getByTestId("queue-board-row")).toHaveCount(0);
  await expect(page.getByRole("button", { name: BOARD_RETRY })).toBeVisible();
  await page.evaluate(() => document.fonts.ready);

  // The retry loop backs off to 5-60s and every attempt answers the same 503, so
  // the DOM is already stable — the pause is taken anyway, for the same reason
  // journey 1 takes it, and because the 2.2.2 control has to be there in the arm
  // where the wall is most likely to be left alone.
  await page.getByRole("button", { name: PAUSE }).click();
  await expect(page.getByRole("button", { name: BOARD_RESUME })).toBeVisible();

  expect(await axeViolations(page)).toEqual([]);
});

// --- journey 3: the panel it is designed for ----------------------------------

test("storefront wall board: the wall board fits a 1080p screen", async ({ page }) => {
  await page.setViewportSize(VIEWPORT_1080P);
  await installApi(page, "populated", BOUTIQUE, { queue: [ok(boardBody(5))] });
  await gotoSettled(page, "/queue");

  const rows = page.getByTestId("queue-board-row");
  await expect(rows).toHaveCount(5);

  // ⚠ toBeInViewport, NEVER toBeVisible. A row 300px below the fold has a
  // non-empty box and is not display:none, so toBeVisible passes on exactly the
  // failure this test exists for — and nobody scrolls a television.
  await expect(
    rows.nth(4),
    "the fifth row is below the fold on a 1080p panel",
  ).toBeInViewport();

  // The other half: scrollHeight catches the DOCUMENT growing past the panel,
  // toBeInViewport names the row that did it. Both are needed — under the
  // A11yMenu text-size boost the fifth row sits ~57px below the fold while the
  // document is still short enough that a scrollHeight check alone says nothing.
  const doc = await page.evaluate(() => ({
    scrollHeight: document.documentElement.scrollHeight,
    innerHeight: window.innerHeight,
  }));
  expect(
    doc.scrollHeight,
    `the board is ${String(doc.scrollHeight - doc.innerHeight)}px taller than a 1080p panel`,
  ).toBeLessThanOrEqual(doc.innerHeight);
});

// --- F20: the statutory privacy notice ---------------------------------------
//
// The plan's E2E row, which is the half of F20 that neither vitest nor pytest
// can reach. Three properties, and each is only observable in a real browser:
// that the footer link REACHES the document from every surface a bride actually
// lands on, that the §11(b) notice on the booking form is the SAME string
// /privacy renders, and that the §30A box is what decides the flag on the wire.

const PRIVACY_LINK = "הודעת פרטיות";
const PRIVACY_NOTICE_HEAD = "המידע שאנחנו אוספות ומה אנחנו עושות בו";
const PRIVACY_DPA_HEAD = "מי מעבד את המידע ואיך הוא נשמר";
const PRIVACY_SUBPROCESSORS_HEAD = "ספקי התשתית";
const COLLECTION_NOTICE_HEAD = "המידע שאת מוסרת לנו";
const MARKETING_LABEL = /אני מאשרת קבלת הודעות SMS/;

// The fixture's two blocks, as SUBSTRINGS that exclude the {{boutique}} token
// and the FSI/PDI isolates wrapped around the name — this asserts the document
// arrived and was split into paragraphs, not how the isolate is spelled.
const NOTICE_BLOCK_1 = "הודעת פרטיות של";
const NOTICE_BLOCK_2 = "פסקה שנייה של ההודעה.";

// The four surfaces the plan enumerates. Each is a DIFFERENT shell state — the
// catalogue and a dress page render the CTA bar, /b/{token} and /checkin do not
// — and the footer is a sibling of <main>, so "the layout renders it" is exactly
// the claim that a single-route test cannot make.
const PRIVACY_ENTRIES: [name: string, open: (page: Page) => Promise<void>][] = [
  ["catalog", (page) => gotoSettled(page, "/")],
  ["dress page", (page) => gotoSettled(page, `/dress/${GALLERY.id}`)],
  ["manage link", (page) => gotoManage(page)],
  ["check-in", (page) => gotoCheckin(page)],
];

for (const [name, open] of PRIVACY_ENTRIES) {
  test(`storefront privacy: the footer link reaches the notice from ${name}`, async ({ page }) => {
    await installApi(page);
    await open(page);

    // CLICKED, not navigated to. `page.goto("/privacy")` would prove the route
    // resolves — which router.test.tsx already proves in jsdom — and would say
    // nothing about whether a bride on this screen can GET there. §11 wants the
    // document reachable, and reachable is a link she can press.
    await page.getByRole("link", { name: PRIVACY_LINK }).click();

    await expect(page).toHaveURL(`${STOREFRONT}/privacy`);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(PRIVACY_LINK);
    // All three documents, because a footer link that lands on a page rendering
    // only its own heading is the failure mode this page deliberately courts:
    // PrivacyPage has NO loading and NO error state, so an unfetched boutique
    // renders an h1 over nothing at all.
    for (const heading of [PRIVACY_NOTICE_HEAD, PRIVACY_DPA_HEAD, PRIVACY_SUBPROCESSORS_HEAD]) {
      await expect(page.getByRole("heading", { name: heading })).toBeVisible();
    }
  });
}

test("storefront privacy: the three documents render in their statutory order, each under its own heading", async ({
  page,
}) => {
  await installApi(page);
  await gotoSettled(page, "/privacy");

  // WHICH text sits under WHICH heading, via the testids the page carries for
  // exactly this. The sub-processor list is the one document a boutique may not
  // override, so rendering her notice in its slot would defeat the whole rule
  // while every heading-count assertion stayed green.
  await expect(page.getByTestId("privacy-notice")).toContainText(NOTICE_BLOCK_1);
  await expect(page.getByTestId("privacy-dpa")).toContainText("תנאי עיבוד מידע של");
  await expect(page.getByTestId("privacy-subprocessors")).toContainText("ספקי תשתית.");

  // Order is load-bearing: the DPA clause points FORWARD at the sub-processor
  // list, so a list rendered above its own reference leaves that sentence
  // pointing at nothing. Asserted as document order, which is what a screen
  // reader walks.
  const headings = await page.getByRole("heading", { level: 2 }).allInnerTexts();
  expect(headings).toEqual([
    PRIVACY_NOTICE_HEAD,
    PRIVACY_DPA_HEAD,
    PRIVACY_SUBPROCESSORS_HEAD,
  ]);

  // The blank lines in the fixture became separate <p>, rather than one block of
  // text with newlines in it: two prose blocks plus the third block's lead line.
  await expect(page.getByTestId("privacy-notice").locator("p")).toHaveCount(3);

  // ⚠ WCAG 1.3.1, and it shipped broken: the three documents put their bullet
  // lines inside <p class="whitespace-pre-line"> with zero <ul>/<ol>/<li>
  // anywhere. axe passes that and CANNOT DO OTHERWISE — it has no way to know
  // text beginning with «•» was meant to be a list — so this is the assertion
  // that has to be written by hand, on the page whose entire purpose is
  // communicating an enumerated set of rights and recipients.
  await expect(page.getByTestId("privacy-notice").getByRole("listitem")).toHaveCount(3);
  await expect(page.getByTestId("privacy-notice").getByRole("listitem").first()).toHaveText(
    "לעיין",
  );

  // {{boutique}} was filled in, and the literal token never reaches the page.
  await expect(page.getByTestId("privacy-notice")).toContainText(BOUTIQUE.name);
  await expect(page.locator("body")).not.toContainText("{{boutique}}");
});

test("storefront privacy: the details step carries the §11 notice, and it is the same text /privacy renders", async ({
  page,
}) => {
  await installApi(page);

  // Walked to, not deep-linked — see gotoDetails. The three steps behind it are
  // already walked five times over, so this one only needs to arrive.
  await gotoDetails(page);

  const notice = page.getByTestId("collection-notice");
  await expect(notice).toBeVisible();
  await expect(page.getByRole("heading", { name: COLLECTION_NOTICE_HEAD })).toBeVisible();

  // BOTH blocks. §11(b) is a notice given at the moment of collection, and a
  // notice silently truncated to its first paragraph is the failure the page's
  // «no clamp, no read-more» rule exists to prevent — a clamp would leave this
  // element visible, non-empty and passing every count assertion.
  await expect(notice).toContainText(NOTICE_BLOCK_1);
  await expect(notice).toContainText(NOTICE_BLOCK_2);
  await expect(notice).toContainText(BOUTIQUE.name);

  // ABOVE the Card she types into — the notice has to precede the collection,
  // not follow it.
  const noticeBox = await rect(notice, "collection notice");
  const nameBox = await rect(page.getByLabel(NAME_LABEL), "name field");
  expect(
    noticeBox.y,
    "the collection notice sits below the field it is a notice about",
  ).toBeLessThan(nameBox.y);

  // D13, the property the whole «not in he.ts» rule exists for: the booking form
  // and /privacy render ONE string from ONE fetch. Compared as actual rendered
  // text, so a second copy pasted into the bundle would have to match byte for
  // byte to survive — which is the point.
  const onForm = (await notice.innerText()).replace(COLLECTION_NOTICE_HEAD, "");
  // …and on the same SEMANTICS. One renderer serves both surfaces, so the
  // bullet run is a real list on the §11 screen too — it was a paragraph on
  // both, which is the half D13 could not see.
  const itemsOnForm = await notice.getByRole("listitem").allInnerTexts();
  expect(itemsOnForm).toEqual(["לעיין", "לתקן", "למחוק"]);
  await gotoSettled(page, "/privacy");
  const onPage = await page.getByTestId("privacy-notice").innerText();
  expect(await page.getByTestId("privacy-notice").getByRole("listitem").allInnerTexts()).toEqual(
    itemsOnForm,
  );
  for (const block of [NOTICE_BLOCK_1, NOTICE_BLOCK_2]) {
    expect(onForm, `the booking form dropped: ${block}`).toContain(block);
    expect(onPage, `/privacy dropped: ${block}`).toContain(block);
  }
});

test("storefront booking: the ticked marketing box is what puts consent on the wire", async ({
  page,
}) => {
  await installApi(page);
  const posted = captureBookings(page);

  await walkBooking(page, {
    atStep: async (label) => {
      if (label !== "details") return;
      const box = page.getByRole("checkbox", { name: MARKETING_LABEL });
      // DEFAULT-OFF, asserted before the click rather than assumed. §30A's
      // affirmative-consent requirement is this assertion; the click after it
      // only proves the control is wired.
      await expect(box).not.toBeChecked();
      await box.check();
    },
  });

  // The flag, and only it, moved. Everything else on this body is identical to
  // the generic path's — so if a future change made the checkbox alter the
  // phone, the type or the terms version, this is where it surfaces.
  expect(posted).toEqual([
    {
      phone: WIRE_PHONE,
      verification_token: VERIFICATION_TOKEN,
      name: CUSTOMER_NAME,
      appointment_type_id: TYPE_PLAIN.id,
      starts_at: SLOT_1000,
      terms_version: TERMS_V3.version,
      dress_id: null,
      dress_size: null,
      notes: null,
      marketing_consent: true,
    },
  ]);
});

test("storefront booking: the marketing box is separate from the terms box and gates nothing", async ({
  page,
}) => {
  await installApi(page);

  await gotoDetails(page);
  // UNBUNDLED: the required terms consent is two navigations away, so no single
  // gesture can collect both. If the terms checkbox were ever moved onto this
  // step, this count becomes 2 and the §30A separation is gone.
  await expect(page.getByRole("checkbox")).toHaveCount(1);

  // NOT A CONDITION: the step advances with the box untouched. That is the
  // anti-detriment rule — a consent a bride fears will cost her the appointment
  // is not free consent — and it is a claim about the FORWARD BUTTON, which is
  // why it cannot be read off the payload.
  await page.getByLabel(NAME_LABEL).fill(CUSTOMER_NAME);
  await expect(page.getByRole("checkbox", { name: MARKETING_LABEL })).not.toBeChecked();
  await forwardButton(page).click();
  await expect(page).toHaveURL(`${STOREFRONT}/book/terms`);
});
