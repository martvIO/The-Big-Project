import { test, expect } from "@playwright/test";
import type { Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import {
  MANAGE,
  bookingWaitlist,
  bookingWaitlistRow,
  installManageApi,
  ok,
  offeredWaitlistEntry,
  staff,
} from "./fixtures/manage";

// F23's two surfaces in a real browser (the per-feature file shape, waitlist.spec.ts's
// sibling). The FOCUS assertions live here and not in vitest deliberately: the
// house focus rule ("the mover is the state change that mounted the target") is
// only measurable where focus actually moves. axe-zero is the legal floor
// (IS 5568 / WCAG 2.0 AA).
//
// ⚠ Risk 6, as everywhere in this directory: the harness stubs the API, so
// these prove the UI and not the contract.

const STOREFRONT = "http://localhost:4173";

const TOKEN = "ot-abcdefghijklmnop";

// --- storefront fixtures (declared locally — there is no storefront fixture
// module, the storefront.spec.ts rule) ---------------------------------------

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

const TERMS = {
  version: 1,
  terms_text: "ביטול עד 48 שעות לפני המועד.",
  refundable_until_hours_before: 48,
  forfeit_percent: 50,
};

// ⚠ 20 JANUARY IS WINTER: Asia/Jerusalem is UTC+2 (IST) here, NOT the UTC+3
// (IDT) it keeps from spring to autumn. So 11:30Z is 13:30 Jerusalem and 09:15Z
// is 11:15 — an hour earlier than the same instants would read in July, and an
// hour earlier than WaitlistSection.test.tsx's 14:30/12:15, whose fixture sits
// in AUGUST. Move this date and both expectations below move with it.
//
// A year far enough out that the fixture cannot age into the past and start
// rendering a different state.
const OFFER = {
  status: "offered",
  starts_at: "2099-01-20T11:30:00Z",
  expires_at: "2099-01-20T09:15:00Z",
  appointment_type_name: "מדידה ראשונה",
};

const BOOKED = {
  id: "bk-1",
  starts_at: OFFER.starts_at,
  status: "confirmed",
  appointment_type_name: OFFER.appointment_type_name,
  dress_name: null,
  dress_size: null,
  deposit_due: false,
  redirect_url: null,
  payment_session_id: null,
};

// Copy, verbatim from apps/storefront/src/i18n/he.ts.
const TITLE = "התפנה תור עבורך";
const DEADLINE_LEAD = "אפשר לאשר את התור עד השעה";
const NAME_LABEL = "שם מלא";
const ACCEPT = "קראתי את מדיניות הביטולים ואני מסכימה לה.";
const SUBMIT = "אישור וקביעת התור";
const CLAIMED = "התור נקבע. נתראה.";
const DECLINE_CTA = "ויתור על התור";
const DECLINE_QUESTION = "לוותר על התור הזה?";
const DECLINE_CONSEQUENCE = "הוויתור יסיר אותך גם מרשימת ההמתנה ליום הזה.";
const DECLINE_CONFIRM = "אישור הוויתור";
const DECLINE_KEEP = "השארת התור";
const DECLINED = "ויתרת על התור, והסרנו אותך מרשימת ההמתנה ליום הזה.";
const EXPIRED = "תוקף ההצעה הזו פג.";
const GONE = "התור הזה נתפס בינתיים.";
const REBOOK = "קביעת תור חדש";

// Copy, verbatim from apps/manage/src/i18n/he.ts.
const NAV_WAITLIST = "רשימת המתנה לתורים";
const COL_OFFER = "ההצעה";
const OFFER_UNTIL = "בתוקף עד";
const STATUS_OFFERED = "הוצע תור";
const CANCEL = "ביטול";
const CANCEL_OFFERED_CONFIRM = "אישור — ההצעה תבוטל";

interface OfferStubs {
  lookup?: unknown;
  lookupStatus?: number;
  claim?: unknown;
  claimStatus?: number;
}

// Every call the page makes, recorded — the token-in-the-body assertion reads
// off this and not off a URL, which is the point of the whole route shape.
interface Recorded {
  path: string;
  body: unknown;
}

async function installStorefront(page: Page, stubs: OfferStubs = {}): Promise<Recorded[]> {
  const posted: Recorded[] = [];
  page.on("request", (request) => {
    const { pathname } = new URL(request.url());
    if (pathname.startsWith("/storefront/waitlist/")) {
      posted.push({ path: pathname, body: request.postDataJSON() });
    }
  });
  await page.route("**/storefront/**", async (route) => {
    const { pathname } = new URL(route.request().url());
    const send = (body: unknown, status = 200) =>
      route.fulfill({
        status,
        headers: { "content-type": "application/json", "cache-control": "no-store" },
        body: JSON.stringify(body),
      });
    if (pathname === "/storefront/boutique") return send(BOUTIQUE);
    if (pathname === "/storefront/terms") return send(TERMS);
    if (pathname === "/storefront/waitlist/offer")
      return send(stubs.lookup ?? OFFER, stubs.lookupStatus ?? 200);
    if (pathname === "/storefront/waitlist/claim")
      return send(stubs.claim ?? BOOKED, stubs.claimStatus ?? 201);
    if (pathname === "/storefront/waitlist/decline")
      return send({ ...OFFER, status: "cancelled" });
    return send({ error: { code: "NOT_FOUND", message: "Nothing stubbed here." } }, 404);
  });
  return posted;
}

async function axeViolations(page: Page): Promise<string[]> {
  // Settle every BOUNDED animation before scanning — waitlist.spec.ts's helper
  // verbatim, including its warning: `--animate-skeleton` and Button's
  // `animate-spin` loop forever and their `.finished` never resolves, so
  // awaiting one hangs the scan until the test timeout.
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
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  return results.violations.map(
    (v) => `${v.id} — ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`,
  );
}

// Waits for REAL content, never the skeleton: an axe scan against a skeleton
// passes vacuously.
async function gotoOffer(page: Page, token = TOKEN): Promise<void> {
  await page.goto(`${STOREFRONT}/w/${token}`);
  await expect(page.getByRole("heading", { level: 1, name: TITLE })).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
}

// --- the storefront journey ---------------------------------------------------

test("offer - the link opens the live offer, and the deadline is a STATIC time", async ({
  page,
}) => {
  await installStorefront(page);
  await gotoOffer(page);

  // The facts, in the boutique's calendar: 13:30 Jerusalem from an 11:30Z
  // instant (UTC+2 — see the fixture), under the labels /book and /b/{token}
  // already use.
  await expect(page.getByText(OFFER.appointment_type_name)).toBeVisible();
  await expect(page.getByText("13:30")).toBeVisible();
  await expect(page.getByText(DEADLINE_LEAD)).toBeVisible();
  await expect(page.getByText("11:15")).toBeVisible();

  // ⚠ R1, AND THE SC 2.2.1 AUDIT ANSWER. The page has a deadline and NOTHING
  // that counts toward it. This is the assertion a real browser can make that
  // jsdom cannot: three seconds of wall-clock time pass and the rendered page
  // is byte-identical. Add a timer and the accessibility conformance argument
  // in design §7 stops being true.
  const before = await page.locator("main").innerHTML();
  await page.waitForTimeout(3000);
  expect(await page.locator("main").innerHTML()).toBe(before);
});

test("offer - axe is clean on the live offer (IS 5568)", async ({ page }) => {
  await installStorefront(page);
  await gotoOffer(page);
  await expect(page.getByLabel(NAME_LABEL)).toBeVisible();
  expect(await axeViolations(page)).toEqual([]);
});

test("offer - tick, name, claim: the confirmation replaces the form and takes focus", async ({
  page,
}) => {
  const posted = await installStorefront(page);
  await gotoOffer(page);

  await page.getByLabel(ACCEPT).check();
  await page.getByLabel(NAME_LABEL).fill("נועה כהן");
  await page.getByRole("button", { name: SUBMIT }).click();

  const line = page.getByText(CLAIMED).first();
  await expect(line).toBeVisible();
  await expect(line).toBeFocused();
  // The form is gone whole; the facts she just booked stay.
  await expect(page.getByLabel(NAME_LABEL)).toHaveCount(0);
  await expect(page.getByRole("button", { name: DECLINE_CTA })).toHaveCount(0);
  await expect(page.getByText("13:30")).toBeVisible();
  expect(await axeViolations(page)).toEqual([]);

  // The token travels in the BODY on both calls and never in a URL — a GET
  // would put a live CLAIM credential into every access log on the path.
  expect(posted.map((entry) => entry.path)).toEqual([
    "/storefront/waitlist/offer",
    "/storefront/waitlist/claim",
  ]);
  for (const entry of posted) {
    expect(entry.body).toMatchObject({ token: TOKEN });
  }
  // EXACTLY three keys on the claim. A phone or a verification token appearing
  // here would be a collection point the privacy notice does not declare.
  expect(Object.keys(posted[1].body as Record<string, unknown>).sort()).toEqual([
    "name",
    "terms_version",
    "token",
  ]);
});

test("offer - the decline reveal focuses the question, and Escape returns focus to the trigger", async ({
  page,
}) => {
  const posted = await installStorefront(page);
  await gotoOffer(page);

  await page.getByRole("button", { name: DECLINE_CTA }).click();
  // The mover mounted the question, so focus went with it — a screen reader
  // hears what is being asked, not an anonymous container.
  await expect(page.getByText(DECLINE_QUESTION)).toBeFocused();
  // The load-bearing sentence: declining removes her from the DAY's list, not
  // from one slot.
  await expect(page.getByText(DECLINE_CONSEQUENCE)).toBeVisible();
  expect(await axeViolations(page)).toEqual([]);
  expect(
    posted.map((entry) => entry.path),
    "the reveal must not call the decline endpoint",
  ).not.toContain("/storefront/waitlist/decline");

  await page.keyboard.press("Escape");
  await expect(page.getByText(DECLINE_QUESTION)).toHaveCount(0);
  // Focus returns to the RE-MOUNTED trigger, never to <body> (WCAG 2.4.3).
  await expect(page.getByRole("button", { name: DECLINE_CTA })).toBeFocused();

  // The keep button is the other way out, and it lands in the same place.
  await page.getByRole("button", { name: DECLINE_CTA }).click();
  await page.getByRole("button", { name: DECLINE_KEEP }).click();
  await expect(page.getByRole("button", { name: DECLINE_CTA })).toBeFocused();
});

test("offer - confirming the decline states what it cost her and offers the rebook path", async ({
  page,
}) => {
  const posted = await installStorefront(page);
  await gotoOffer(page);

  await page.getByRole("button", { name: DECLINE_CTA }).click();
  await page.getByRole("button", { name: DECLINE_CONFIRM }).click();

  const line = page.getByText(DECLINED).first();
  await expect(line).toBeVisible();
  await expect(line).toBeFocused();
  await expect(page.getByRole("link", { name: REBOOK })).toHaveAttribute("href", "/book/slot");
  expect(posted.map((entry) => entry.path)).toContain("/storefront/waitlist/decline");
});

test("offer - an expired offer states the fact, offers a rebook, and is axe clean", async ({
  page,
}) => {
  await installStorefront(page, { lookup: { ...OFFER, status: "expired" } });
  await gotoOffer(page);

  await expect(page.getByText(EXPIRED)).toBeVisible();
  await expect(page.getByRole("link", { name: REBOOK })).toHaveAttribute("href", "/book/slot");
  // No form on a dead offer: a tick she could fill in would be a button that
  // can only fail.
  await expect(page.getByLabel(NAME_LABEL)).toHaveCount(0);
  expect(await axeViolations(page)).toEqual([]);
});

test("offer - F-O2: after the seat is lost, a RELOAD re-renders the LIVE offer", async ({
  page,
}) => {
  // ⚠ THIS IS CORRECT BEHAVIOUR AND THE TEST EXISTS SO A LATER READER DOES NOT
  // READ IT AS A BUG. The claim's transaction rolls back whole — including the
  // guarded UPDATE that would have marked her `claimed` — so the entry is still
  // `offered` and the server will keep answering `offered` until the deadline
  // passes. Do NOT "fix" this by expiring the entry client-side: the server is
  // the only clock, and a client that decided otherwise would strand a bride
  // whose race the cascade may yet resolve in her favour.
  await installStorefront(page, {
    claim: { error: { code: "SLOT_UNAVAILABLE", message: "gone" } },
    claimStatus: 409,
  });
  await gotoOffer(page);

  await page.getByLabel(ACCEPT).check();
  await page.getByLabel(NAME_LABEL).fill("נועה כהן");
  await page.getByRole("button", { name: SUBMIT }).click();

  // The same sentence a direct booker meets — she cannot tell a waitlist
  // claimer from another bride, and she is owed no explanation of which.
  const alert = page.getByRole("alert");
  await expect(alert).toContainText(GONE);
  await expect(alert).toBeFocused();
  // The form is STILL THERE: the offer did not die, only this attempt did.
  await expect(page.getByRole("button", { name: SUBMIT })).toBeVisible();

  await page.reload();
  await expect(page.getByRole("heading", { level: 1, name: TITLE })).toBeVisible();
  await expect(page.getByText(DEADLINE_LEAD)).toBeVisible();
  await expect(page.getByLabel(NAME_LABEL)).toBeVisible();
  await expect(page.getByText(GONE)).toHaveCount(0);
});

// --- the manage journey -------------------------------------------------------

const MANAGER = staff({ id: "st-mgr", display_name: "דנה", role: "shift_manager" });

test("offer - the console shows who is holding the slot and until when, axe clean", async ({
  page,
}) => {
  const OFFERED = offeredWaitlistEntry();
  const WAITING = bookingWaitlistRow({ id: "we-waiting", customer_name: "נועה כהן" });
  await installManageApi(page, {
    staff: MANAGER,
    replies: { "/manage/waitlist": [ok(bookingWaitlist([OFFERED, WAITING]))] },
  });
  await page.goto(MANAGE);
  await page.getByRole("button", { name: NAV_WAITLIST }).click();
  await expect(page.getByText("רותם לוי")).toBeVisible();

  // The column, its two runs, and the badge that separates an in-flight row
  // from a merely waiting one (P4).
  await expect(page.getByRole("columnheader", { name: COL_OFFER })).toBeVisible();
  await expect(page.getByText("13:30")).toBeVisible();
  await expect(page.getByText(OFFER_UNTIL)).toBeVisible();
  await expect(page.getByText("11:15")).toBeVisible();
  await expect(page.getByText(STATUS_OFFERED)).toBeVisible();
  expect(await axeViolations(page)).toEqual([]);

  // Arming the OFFERED row names the consequence — this click takes a live
  // offer back off a bride who may be reading her SMS about it right now.
  await page.getByRole("button", { name: CANCEL, exact: true }).first().click();
  await expect(page.getByRole("button", { name: CANCEL_OFFERED_CONFIRM })).toBeVisible();
  expect(await axeViolations(page)).toEqual([]);
});
