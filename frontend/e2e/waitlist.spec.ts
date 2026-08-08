import { test, expect } from "@playwright/test";
import type { Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import {
  MANAGE,
  bookingWaitlist,
  bookingWaitlistCancelPath,
  bookingWaitlistRow,
  installManageApi,
  ok,
  staff,
} from "./fixtures/manage";

// F22's two surfaces, in a real browser (the walk-in.spec.ts per-feature
// shape). The FOCUS assertions live here and not in vitest deliberately: the
// house focus rule ("the mover is the state change that mounted the target")
// is only measurable where focus actually moves. axe-zero is the legal floor
// (IS 5568 / WCAG 2.0 AA).
//
// ⚠ Risk 6, as everywhere in this directory: the harness stubs the API, so
// these prove the UI and not the contract.

const STOREFRONT = "http://localhost:4173";

// --- storefront fixtures (declared locally, the storefront.spec.ts rule) -----

const EMPTY_DAY = "2099-01-20";

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
  // The three privacy documents are REQUIRED on the wire type, and the reveal
  // renders `privacy_notice_text` through substituteBoutique — the {{boutique}}
  // token is the shape under test, not the approved Hebrew.
  privacy_notice_text: "הודעת פרטיות של {{boutique}}.\n\nהמידע משמש לתיאום התור בלבד.",
  privacy_dpa_text: "סעיף עיבוד.",
  privacy_subprocessors_text: "ספקי תשתית.",
};

const TERMS = {
  version: 1,
  terms_text: "ביטול עד 48 שעות לפני המועד.",
  refundable_until_hours_before: 48,
  forfeit_percent: 50,
};

const TYPE = {
  id: "apt-1",
  name: "מדידה ראשונה",
  duration_minutes: 60,
  audience: "all",
  deposit_required: false,
  deposit_amount_agorot: null,
};

// Copy, verbatim from apps/storefront/src/i18n/he.ts.
const CTA = "הצטרפות לרשימת ההמתנה";
const PHONE_LABEL = "טלפון נייד";
const CODE_LABEL = "קוד האימות";
const SEND = "שליחת קוד אימות";
const JOIN = "אישור והצטרפות לרשימה";
const CONFIRMED_LEAD = "נרשמת לרשימת ההמתנה";
const DATE_LABEL = "תאריך";

// Copy, verbatim from apps/manage/src/i18n/he.ts.
const NAV_WAITLIST = "רשימת המתנה לתורים";
const CANCEL = "ביטול";
const CANCEL_CONFIRM = "אישור הביטול";
const EMPTY_TITLE = "אין כרגע רשומות ברשימת ההמתנה";
const EMPTY_FILTERED = "אין רשומות בתאריך הזה.";

async function installStorefront(page: Page): Promise<void> {
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
    if (pathname === "/storefront/appointment-types") return send([TYPE]);
    // The WHOLE window is empty — every picked day renders the full-day state.
    if (pathname === "/storefront/slots") return send({ slots: [] });
    if (pathname === "/storefront/otp/send")
      return route.fulfill({ status: 204, headers: { "cache-control": "no-store" } });
    if (pathname === "/storefront/otp/verify")
      return send({ verification_token: "vt-1", expires_at: "2099-01-01T00:10:00Z" });
    if (pathname === "/storefront/waitlist")
      return send({ day: EMPTY_DAY, appointment_type_id: TYPE.id, status: "waiting" }, 201);
    if (pathname === "/storefront/dresses")
      return send({ items: [], total: 0, offset: 0, limit: 24 });
    return send({ error: { code: "NOT_FOUND", message: "Nothing stubbed here." } }, 404);
  });
}

async function axeViolations(page: Page): Promise<string[]> {
  // Settle every running animation BEFORE scanning. `Button` carries
  // `transition duration-(--motion-fast)`, so the two-click cancel swap
  // (secondary → danger) animates its background-color, and `toBeVisible()`
  // resolves the moment the node is painted — not when the colour arrives.
  // Scanning inside that window measures an intermediate pink against white
  // ink and reports `color-contrast — .bg-danger > .gap-2`, which is a FALSE
  // red: the resting pair is 7.01:1 and the hover pair 5.72:1, both over the
  // 4.5 floor. It reproduced only under full-suite parallelism, where the
  // render lands late enough that the scan catches the transition mid-flight.
  // Same remedy the dialog suites already use (guide.spec.ts `settled`).
  // ⚠ FILTER THE INFINITE ONES. `--animate-skeleton` and Button's `animate-spin`
  // loop forever, and their `.finished` promise NEVER resolves — awaiting one
  // hangs the scan until the 30s test timeout. Neither is on this page today,
  // which is why the unfiltered version passed; that is a fact about the current
  // markup, not a property of the helper. Bounded animations only, under a
  // ceiling, so a pathological one degrades into a slightly-early scan.
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

// Walks the slot step to the open reveal: type picked, empty day picked, CTA
// clicked.
async function openReveal(page: Page): Promise<void> {
  await installStorefront(page);
  await page.goto(`${STOREFRONT}/book/slot`);
  await page.getByRole("radio", { name: /מדידה ראשונה/ }).click();
  await page.getByLabel(DATE_LABEL).fill(EMPTY_DAY);
  await page.getByRole("button", { name: CTA }).click();
}

// --- the storefront journey --------------------------------------------------

test("waitlist - the CTA waits for a type, and focus lands on the phone input at open", async ({
  page,
}) => {
  await installStorefront(page);
  await page.goto(`${STOREFRONT}/book/slot`);
  // An empty day with NO type picked: the empty state stands alone — the CTA
  // must not invite a join it cannot bind.
  await page.getByLabel(DATE_LABEL).fill(EMPTY_DAY);
  await expect(page.getByText("אין מועדים פנויים בתאריך הזה", { exact: false })).toBeVisible();
  await expect(page.getByRole("button", { name: CTA })).toHaveCount(0);

  await page.getByRole("radio", { name: /מדידה ראשונה/ }).click();
  await page.getByRole("button", { name: CTA }).click();
  // The mover mounted the phone input; focus went with it.
  await expect(page.getByLabel(PHONE_LABEL)).toBeFocused();
  // The §11 notice, substituted, before anything is sent.
  await expect(page.getByTestId("waitlist-privacy-notice")).toContainText("בוטיק ורד");
});

test("waitlist - axe is clean on the open reveal (IS 5568)", async ({ page }) => {
  await openReveal(page);
  await expect(page.getByLabel(PHONE_LABEL)).toBeVisible();
  expect(await axeViolations(page)).toEqual([]);
});

test("waitlist - phone, code, join: the confirmation replaces the reveal, focused, axe clean", async ({
  page,
}) => {
  await openReveal(page);
  await page.getByLabel(PHONE_LABEL).fill("0501234567");
  await page.getByRole("button", { name: SEND }).click();
  // send -> code mounts, focus moves there (the mover rule).
  await expect(page.getByLabel(CODE_LABEL)).toBeFocused();
  await page.getByLabel(CODE_LABEL).fill("123456");
  await page.getByRole("button", { name: JOIN }).click();

  const confirmation = page.getByTestId("waitlist-confirmed");
  await expect(confirmation).toContainText(CONFIRMED_LEAD);
  await expect(confirmation).toBeFocused();
  // The reveal is gone whole — both phases of it.
  await expect(page.getByLabel(PHONE_LABEL)).toHaveCount(0);
  await expect(page.getByLabel(CODE_LABEL)).toHaveCount(0);
  expect(await axeViolations(page)).toEqual([]);
});

// --- the manage journey -------------------------------------------------------

const MANAGER = staff({ id: "st-mgr", display_name: "דנה", role: "shift_manager" });

const ROW_NOA = bookingWaitlistRow();
const ROW_STRANGER = bookingWaitlistRow({
  id: "we-2",
  customer_name: null,
  phone: "+972529998877",
});

test("waitlist - the manager cancels an entry with the two-click swap and the row leaves", async ({
  page,
}) => {
  const recorder = await installManageApi(page, {
    staff: MANAGER,
    replies: {
      // The list before the cancel, then the refetch after it.
      "/manage/waitlist": [
        ok(bookingWaitlist([ROW_NOA, ROW_STRANGER])),
        ok(bookingWaitlist([ROW_STRANGER])),
      ],
      [bookingWaitlistCancelPath(ROW_NOA.id)]: [ok({ ...ROW_NOA, status: "cancelled" })],
    },
  });
  await page.goto(MANAGE);
  await page.getByRole("button", { name: NAV_WAITLIST }).click();
  await expect(page.getByText("נועה כהן")).toBeVisible();
  // The stranger's row shows her phone — the only handle the boutique has.
  await expect(page.getByText("+972529998877")).toBeVisible();
  expect(await axeViolations(page)).toEqual([]);

  // Two clicks on one control: secondary -> danger, in place.
  await page.getByRole("button", { name: CANCEL, exact: true }).first().click();
  await expect(page.getByRole("button", { name: CANCEL_CONFIRM })).toBeVisible();
  expect(await axeViolations(page)).toEqual([]);
  await page.getByRole("button", { name: CANCEL_CONFIRM }).click();

  await expect(page.getByText("נועה כהן")).toHaveCount(0);
  await expect(page.getByText("+972529998877")).toBeVisible();
  const cancels = recorder.of(bookingWaitlistCancelPath(ROW_NOA.id));
  expect(cancels).toHaveLength(1);
  expect(cancels[0].method).toBe("POST");
});

test("waitlist - Escape disarms the confirm without cancelling", async ({ page }) => {
  const recorder = await installManageApi(page, {
    staff: MANAGER,
    replies: { "/manage/waitlist": [ok(bookingWaitlist([ROW_NOA]))] },
  });
  await page.goto(MANAGE);
  await page.getByRole("button", { name: NAV_WAITLIST }).click();
  await page.getByRole("button", { name: CANCEL, exact: true }).click();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("button", { name: CANCEL_CONFIRM })).toHaveCount(0);
  await expect(page.getByRole("button", { name: CANCEL, exact: true })).toBeVisible();
  expect(recorder.of(bookingWaitlistCancelPath(ROW_NOA.id))).toHaveLength(0);
});

test("waitlist - both empty states render designed, axe clean", async ({ page }) => {
  await installManageApi(page, {
    staff: MANAGER,
    replies: { "/manage/waitlist": [ok(bookingWaitlist([]))] },
  });
  await page.goto(MANAGE);
  await page.getByRole("button", { name: NAV_WAITLIST }).click();
  // A date filter is set by default, so the day may simply have no entries.
  await expect(page.getByText(EMPTY_FILTERED)).toBeVisible();
  expect(await axeViolations(page)).toEqual([]);
  // Cleared filter = all upcoming = the day-one empty state.
  await page.getByLabel(DATE_LABEL).fill("");
  await expect(page.getByText(EMPTY_TITLE)).toBeVisible();
  expect(await axeViolations(page)).toEqual([]);
});
