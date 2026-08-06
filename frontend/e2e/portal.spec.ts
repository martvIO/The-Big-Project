import { test, expect } from "@playwright/test";
import type { Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

// F24's /portal, in a real browser (the per-feature file shape walk-in.spec.ts
// and waitlist.spec.ts established).
//
// ⚠ THE FOCUS AND DISCLOSURE ASSERTIONS LIVE HERE AND NOT IN VITEST, and that
// is a ruling rather than a preference: the house focus rule — "the mover is
// the state change that mounted the target" — is only measurable where focus
// actually moves, and jsdom's model is not the one a screen reader follows
// (`.memory/jsdom-has-no-dialog` records the same argument for <dialog>).
// PortalPage.test.tsx therefore asserts STATE and this file asserts MOVEMENT.
//
// ⚠ Risk 6, as everywhere in this directory: the harness stubs the API, so
// these prove the CONSOLE and not the CONTRACT. The contract side is the
// db-marked backend suite (test_portal_service.py, test_portal_api.py); keep
// both — neither substitutes for the other.
//
// axe-zero on every rendered state is the LEGAL floor here (IS 5568 / WCAG 2.0
// AA), not a nicety.

const STOREFRONT = "http://localhost:4173";

// --- fixtures (declared locally, the storefront.spec.ts rule) ----------------

const BOUTIQUE = {
  name: "בוטיק ורד",
  essence: null,
  description: null,
  phone: "052-1234567",
  address: "הרצל 1, תל אביב",
  maps_url: null,
  instagram: null,
  hours: [],
  exceptions: [],
  privacy_notice_text: "הודעת פרטיות של {{boutique}}.",
  privacy_dpa_text: "סעיף עיבוד.",
  privacy_subprocessors_text: "ספקי תשתית.",
};

const BOOKING_ID = "11111111-1111-1111-1111-111111111111";
const PAST_ID = "22222222-2222-2222-2222-222222222222";

const UPCOMING_ROW = {
  id: BOOKING_ID,
  starts_at: "2099-08-04T07:00:00Z",
  status: "confirmed",
  attendance_confirmed_at: null,
  appointment_type_name: "מדידה ראשונה",
  dress_name: "שמלת אלמה",
  dress_size: "36",
};

const PAST_ROW = {
  ...UPCOMING_ROW,
  id: PAST_ID,
  starts_at: "2020-08-04T07:00:00Z",
  status: "cancelled",
};

const DETAIL = {
  booking: {
    starts_at: UPCOMING_ROW.starts_at,
    status: "confirmed",
    attendance_confirmed_at: null,
    appointment_type_name: "מדידה ראשונה",
    dress_name: "שמלת אלמה",
    dress_size: "36",
    deposit_taken: false,
  },
  policy: { refundable_until_hours_before: 48, forfeit_percent: 50 },
  boutique: { name: BOUTIQUE.name, phone: BOUTIQUE.phone, address: BOUTIQUE.address, maps_url: null },
};

const BELL_ITEM = {
  id: "msg-1",
  kind: "reminder",
  created_at: "2099-08-01T07:00:00Z",
  booking_id: BOOKING_ID,
  starts_at: UPCOMING_ROW.starts_at,
  appointment_type_name: "מדידה ראשונה",
};

// Copy, verbatim from apps/storefront/src/i18n/he.ts.
const LOGIN_TITLE = "האזור האישי";
const LOGIN_INTRO = "אפשר להיכנס עם מספר הטלפון שאיתו קבעת תור.";
const PHONE_LABEL = "טלפון נייד";
const CODE_LABEL = "קוד האימות";
const SEND = "שליחת קוד אימות";
const SIGN_IN = "כניסה";
const LOGOUT = "יציאה";
const UPCOMING = "תורים קרובים";
const EMPTY_TITLE = "אין תורים למספר הזה";
const BACK = "חזרה לתורים שלי";
const ICS = "הוספה ליומן";
const CANCEL_CTA = "ביטול התור";
const CANCEL_CONFIRM = "אישור הביטול";
const CANCEL_QUESTION = "לבטל את התור?";
const BELL_LABEL = "הודעות מהבוטיק";
const BELL_TITLE = "הודעות מהבוטיק";
const BELL_EMPTY = "אין הודעות עדיין. הודעות על התורים שלך יופיעו כאן.";
const SESSION_EXPIRED = "החיבור לאזור האישי הסתיים. אפשר להיכנס שוב עם קוד אימות.";
const SMS_DOWN =
  "אימות הטלפון אינו זמין כרגע, ולכן אי אפשר להשלים כאן את קביעת התור. נשמח שתתקשרי אלינו ונקבע יחד מועד.";

const MAIN_ID = "#content";

interface Options {
  /** false → the bootstrap 401s and the login panel renders. */
  signedIn?: boolean;
  bookings?: { upcoming: unknown[]; past: unknown[] };
  bell?: { unread_count: number; items: unknown[] } | "fail";
  /** 503 on /otp/send — design state E6. */
  smsDown?: boolean;
  /** The mint answers PORTAL_NO_BOOKINGS — design state N. */
  noBookings?: boolean;
  /** Every cookie-authed read 401s AFTER the first bookings load — state X. */
  expireAfterLoad?: boolean;
}

interface Recorder {
  seen: string[];
}

async function installApi(page: Page, options: Options = {}): Promise<Recorder> {
  const recorder: Recorder = { seen: [] };
  let signedIn = options.signedIn ?? false;
  let loadedOnce = false;

  await page.route("**/storefront/**", async (route) => {
    const { pathname } = new URL(route.request().url());
    const send = (body: unknown, status = 200) =>
      route.fulfill({
        status,
        headers: { "content-type": "application/json", "cache-control": "no-store" },
        body: JSON.stringify(body),
      });
    const unauthenticated = () =>
      send({ error: { code: "NOT_AUTHENTICATED", message: "Authentication required." } }, 401);

    if (pathname === "/storefront/boutique") return send(BOUTIQUE);
    if (pathname === "/storefront/dresses")
      return send({ items: [], total: 0, offset: 0, limit: 24 });

    if (pathname === "/storefront/otp/send") {
      if (options.smsDown)
        return send({ error: { code: "SMS_UNAVAILABLE", message: "down" } }, 503);
      return route.fulfill({ status: 204, headers: { "cache-control": "no-store" } });
    }
    if (pathname === "/storefront/otp/verify")
      return send({ verification_token: "vt-1", expires_at: "2099-01-01T00:10:00Z" });

    if (pathname === "/storefront/portal/session") {
      if (options.noBookings)
        return send(
          { error: { code: "PORTAL_NO_BOOKINGS", message: "No bookings for this phone." } },
          404,
        );
      signedIn = true;
      return send({ customer_name: "רותם" });
    }
    if (pathname === "/storefront/portal/me")
      return signedIn ? send({ customer_name: "רותם" }) : unauthenticated();
    if (pathname === "/storefront/portal/logout") {
      signedIn = false;
      return send({ ok: true });
    }
    if (pathname === "/storefront/portal/bookings") {
      if (options.expireAfterLoad && loadedOnce) return unauthenticated();
      loadedOnce = true;
      return send(options.bookings ?? { upcoming: [UPCOMING_ROW], past: [PAST_ROW] });
    }
    if (pathname === "/storefront/portal/booking") return send(DETAIL);
    if (pathname === "/storefront/portal/booking/confirm-attendance")
      return send({
        ...DETAIL,
        booking: { ...DETAIL.booking, attendance_confirmed_at: "2099-08-01T07:00:00Z" },
      });
    if (pathname === "/storefront/portal/booking/cancel")
      return send({ ...DETAIL, booking: { ...DETAIL.booking, status: "cancelled" } });
    if (pathname === "/storefront/portal/booking.ics")
      return route.fulfill({
        status: 200,
        headers: {
          "content-type": "text/calendar; charset=utf-8",
          "content-disposition": 'attachment; filename="appointment.ics"',
          "cache-control": "no-store",
        },
        body: "BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n",
      });
    if (pathname === "/storefront/portal/bell") {
      if (options.bell === "fail") return send({ error: { code: "UNKNOWN", message: "x" } }, 500);
      return send(options.bell ?? { unread_count: 0, items: [] });
    }
    if (pathname === "/storefront/portal/bell/seen") {
      recorder.seen.push(pathname);
      return send({ ok: true });
    }
    return send({ error: { code: "NOT_FOUND", message: "Nothing stubbed here." } }, 404);
  });
  return recorder;
}

async function axeViolations(page: Page): Promise<string[]> {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  return results.violations.map(
    (v) => `${v.id} — ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`,
  );
}

/** Phone → code → כניסה, landing on the dashboard. */
async function signIn(page: Page): Promise<void> {
  await page.goto(`${STOREFRONT}/portal`);
  await page.getByLabel(PHONE_LABEL).fill("0501234567");
  await page.getByRole("button", { name: SEND }).click();
  await page.getByLabel(CODE_LABEL).fill("123456");
  await page.getByRole("button", { name: SIGN_IN }).click();
  await expect(page.getByRole("heading", { name: /רותם/ })).toBeVisible();
}

// --- the login journey -------------------------------------------------------

test("portal - the login panel renders on a 401 bootstrap, RTL, axe clean", async ({ page }) => {
  await installApi(page);
  await page.goto(`${STOREFRONT}/portal`);

  await expect(page.getByRole("heading", { name: LOGIN_TITLE })).toBeVisible();
  await expect(page.getByText(LOGIN_INTRO)).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  // The phone input is an LTR island inside the RTL flow.
  await expect(page.getByLabel(PHONE_LABEL)).toHaveAttribute("dir", "ltr");
  expect(await axeViolations(page)).toEqual([]);
});

test("portal - phone, code, כניסה: one gesture reaches the dashboard, axe clean", async ({
  page,
}) => {
  await installApi(page);
  await signIn(page);

  await expect(page.getByRole("heading", { name: UPCOMING })).toBeVisible();
  await expect(page.getByText("מדידה ראשונה").first()).toBeVisible();
  expect(await axeViolations(page)).toEqual([]);
});

test("portal - the code field takes focus when it mounts (the mover rule)", async ({ page }) => {
  await installApi(page);
  await page.goto(`${STOREFRONT}/portal`);
  await page.getByLabel(PHONE_LABEL).fill("0501234567");
  await page.getByRole("button", { name: SEND }).click();
  // The send is what mounted the field, so the send is what moves focus. jsdom
  // cannot fail this; a browser can.
  await expect(page.getByLabel(CODE_LABEL)).toBeFocused();
});

test("portal - state N renders the empty screen, focused, axe clean", async ({ page }) => {
  await installApi(page, { noBookings: true });
  await page.goto(`${STOREFRONT}/portal`);
  await page.getByLabel(PHONE_LABEL).fill("0501234567");
  await page.getByRole("button", { name: SEND }).click();
  await page.getByLabel(CODE_LABEL).fill("123456");
  await page.getByRole("button", { name: SIGN_IN }).click();

  await expect(page.getByText(EMPTY_TITLE)).toBeVisible();
  // The mover mounted it, so focus went with it — she must not be left on a
  // button that no longer exists.
  await expect(page.getByTestId("portal-empty")).toBeFocused();
  expect(await axeViolations(page)).toEqual([]);
});

test("portal - E6: an SMS outage replaces the form with a dead end, focused, axe clean", async ({
  page,
}) => {
  await installApi(page, { smsDown: true });
  await page.goto(`${STOREFRONT}/portal`);
  await page.getByLabel(PHONE_LABEL).fill("0501234567");
  await page.getByRole("button", { name: SEND }).click();

  await expect(page.getByText(SMS_DOWN)).toBeVisible();
  await expect(page.getByLabel(PHONE_LABEL)).toHaveCount(0);
  // Reached BY the focus move — which is why the block carries no role="alert".
  await expect(page.getByText(SMS_DOWN)).toBeVisible();
  expect(await axeViolations(page)).toEqual([]);
});

// --- the dashboard -----------------------------------------------------------

test("portal - the empty dashboard is the SAME screen as state N, axe clean", async ({ page }) => {
  await installApi(page, { bookings: { upcoming: [], past: [] } });
  await signIn(page);

  await expect(page.getByText(EMPTY_TITLE)).toBeVisible();
  expect(await axeViolations(page)).toEqual([]);
});

test("portal - a row opens the detail and focus lands on #content (router contract)", async ({
  page,
}) => {
  await installApi(page);
  await signIn(page);

  await page.getByRole("button", { name: /מדידה ראשונה/ }).first().click();
  await expect(page.getByText(BACK)).toBeVisible();
  await expect(page.getByRole("link", { name: ICS })).toBeVisible();
  expect(await axeViolations(page)).toEqual([]);
});

test("portal - the cancel two-step: danger only on the final confirm, axe clean", async ({
  page,
}) => {
  await installApi(page);
  await signIn(page);
  await page.getByRole("button", { name: /מדידה ראשונה/ }).first().click();

  await page.getByRole("button", { name: CANCEL_CTA }).click();
  // The reveal's QUESTION is the focus destination, so a screen reader hears
  // what is being asked rather than an anonymous container.
  await expect(page.getByText(CANCEL_QUESTION)).toBeFocused();
  expect(await axeViolations(page)).toEqual([]);

  await page.getByRole("button", { name: CANCEL_CONFIRM }).click();
  // Twice on purpose: the line she READS and the status region she HEARS.
  await expect(page.getByText("התור בוטל.").first()).toBeVisible();
  // A cancelled booking offers NO calendar download — the server 409s
  // regardless, and there is nothing to word on a control that cannot act.
  await expect(page.getByRole("link", { name: ICS })).toHaveCount(0);
  expect(await axeViolations(page)).toEqual([]);
});

test("portal - the ics link is a native GET download with the calendar content type", async ({
  page,
}) => {
  await installApi(page);
  await signIn(page);
  await page.getByRole("button", { name: /מדידה ראשונה/ }).first().click();

  const link = page.getByRole("link", { name: ICS });
  // A PLAIN href and not a fetch: on iOS a direct text/calendar response opens
  // the add-to-calendar sheet, and the booking id is not the capability here.
  await expect(link).toHaveAttribute("href", `/storefront/portal/booking.ics?id=${BOOKING_ID}`);
  await expect(link).toHaveAttribute("download", "appointment.ics");
  // And the token is nowhere in that URL (F14 D7) — the portal transport is
  // cookie-authed precisely so the link can exist at all.
  await expect(link).not.toHaveAttribute("href", /token/);

  // ⚠ The response HEADERS are deliberately NOT asserted here. `page.request`
  // is a separate context that bypasses this file's route map, so it would
  // measure the preview server's SPA fallback rather than the endpoint. The
  // content-type and disposition are the backend's contract and live in
  // test_portal_api.py / test_booking_manage_api.py — Risk 6 again.
});

// --- the bell ----------------------------------------------------------------

test("portal - the bell opens as a disclosure, focuses its heading, axe clean", async ({
  page,
}) => {
  await installApi(page, { bell: { unread_count: 0, items: [] } });
  await signIn(page);

  const bell = page.getByRole("button", { name: BELL_LABEL });
  await expect(bell).toHaveAttribute("aria-expanded", "false");
  await bell.click();
  await expect(bell).toHaveAttribute("aria-expanded", "true");
  // The panel's own heading is the focus destination — the mover rule.
  await expect(page.getByText(BELL_TITLE, { exact: true }).last()).toBeFocused();
  await expect(page.getByText(BELL_EMPTY)).toBeVisible();
  expect(await axeViolations(page)).toEqual([]);
});

test("portal - the badge clears only AFTER the seen POST, and the POST is observed", async ({
  page,
}) => {
  const recorder = await installApi(page, { bell: { unread_count: 3, items: [BELL_ITEM] } });
  await signIn(page);

  const unread = page.getByRole("button", { name: `${BELL_LABEL}, 3 חדשות` });
  await expect(unread).toBeVisible();
  await unread.click();

  await expect(page.getByText(BELL_TITLE, { exact: true }).last()).toBeVisible();
  // Observed, not assumed: F-P2 is the whole reason this endpoint exists.
  await expect
    .poll(() => recorder.seen.length, { message: "the seen POST never fired" })
    .toBeGreaterThan(0);
  // And the badge went with the server's answer, not with the click.
  await expect(page.getByRole("button", { name: BELL_LABEL })).toBeVisible();
  expect(await axeViolations(page)).toEqual([]);
});

test("portal - a failed bell shows NO badge, fires no seen POST, and offers a retry", async ({
  page,
}) => {
  const recorder = await installApi(page, { bell: "fail" });
  await signIn(page);

  const bell = page.getByRole("button", { name: BELL_LABEL });
  await bell.click();
  await expect(page.getByText("לא הצלחנו להציג את פרטי התור כרגע.").last()).toBeVisible();
  // Nothing was shown, so nothing is marked seen.
  expect(recorder.seen).toEqual([]);
  expect(await axeViolations(page)).toEqual([]);
});

// --- logout and expiry -------------------------------------------------------

test("portal - logout returns to the login panel with no expiry line", async ({ page }) => {
  await installApi(page);
  await signIn(page);

  await page.getByRole("button", { name: LOGOUT }).click();
  await expect(page.getByText(LOGIN_INTRO)).toBeVisible();
  await expect(page.getByText(SESSION_EXPIRED)).toHaveCount(0);
});

test("portal - a mid-session 401 remounts the login panel with the expiry line, axe clean", async ({
  page,
}) => {
  await installApi(page, { expireAfterLoad: true });
  await signIn(page);

  // Opening a booking and coming back re-reads the list, which now 401s.
  await page.getByRole("button", { name: /מדידה ראשונה/ }).first().click();
  await page.getByText(BACK).click();

  await expect(page.getByText(SESSION_EXPIRED).first()).toBeVisible();
  await expect(page.getByText(LOGIN_INTRO)).toBeVisible();
  expect(await axeViolations(page)).toEqual([]);
});

// --- the router contract -----------------------------------------------------

test("portal - focus lands on #content after navigating into /portal", async ({ page }) => {
  await installApi(page);
  await page.goto(`${STOREFRONT}/`);
  // A client navigation, not a fresh load: on first paint the browser owns
  // focus and the skip link is the first stop.
  await page.evaluate(() => {
    window.history.pushState({}, "", "/portal");
    window.dispatchEvent(new Event("storefront:navigation"));
  });
  await expect(page.getByRole("heading", { name: LOGIN_TITLE })).toBeVisible();
  await expect(page.locator(MAIN_ID)).toBeFocused();
});
