import { test, expect } from "@playwright/test";
import type { Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import {
  MANAGE,
  dressDetail,
  dressList,
  installManageApi,
  ok,
  refuse,
  reservation,
  staff,
} from "./fixtures/manage";

// F28's two surfaces in a real browser: the catalog editor's reservations pane
// and the public dress page's booked-out block, plus the BookPage 409.
//
// ⚠ **THE MODAL AND THE FOCUS MOVE LIVE HERE BECAUSE THE UNIT SUITE CANNOT FAIL
// THEM.** `apps/manage/src/test/setup.ts` stubs `HTMLDialogElement.showModal()`
// as `this.open = true` and nothing else — no focus move, no trap, no top layer
// (`dialog-focus.spec.ts` carries the full argument and the mutation ledger).
// Under that stub the delete confirmation never takes focus, so a jsdom
// assertion that focus LANDED on the list region afterwards would be true before
// the component ran. The pane's post-delete focus move is new behaviour, not
// MediaGallery's inherited native return — which fails silently here precisely
// because the trigger row unmounts with the row it deletes — so it needs a
// browser to mean anything.
//
// ⚠ **Risk 6, as everywhere in this directory: the harness stubs the API, so
// these prove the CONSOLE and not the CONTRACT.**

const STOREFRONT = "http://localhost:4173";

// --- copy, verbatim from the components ---------------------------------------

const NAV_DASHBOARD = "סקירה";
const NAV_CATALOG = "שמלות";
const DRESS_NAME = "שמלת נסיכה";
const PANE_HEADING = "הזמנות לתאריך";
const WEDDING_LABEL = "תאריך החתונה";
const START_LABEL = "מהתאריך";
const END_LABEL = "עד התאריך (כולל)";
const ADD_LABEL = "הוספת הזמנה";
const EMPTY_TITLE = "אין הזמנות לשמלה הזאת.";
const DELETE_LABEL = "מחיקה";
const DELETE_TITLE = "למחוק את ההזמנה?";
const ADDED_CUE = "ההזמנה נוספה.";
const DELETED_CUE = "ההזמנה נמחקה.";
const OVERLAP_LEAD = "התאריכים מתנגשים עם הזמנה קיימת";
const CREATE_HINT = "יש לשמור את השמלה לפני הוספת מידות, תמונות והזמנות";
const NEW_DRESS = "שמלה חדשה";

const OWNER = staff({ role: "owner" });
const DRESS_ID = "dr-1";
const RESERVATIONS_PATH = `/manage/dresses/${DRESS_ID}/reservations`;

// Storefront copy, verbatim from apps/storefront/src/i18n/he.ts.
const RESERVED_DATES_HEADING = "מוזמנת בתאריכים";
const RESERVED_DATES_NOTE = "בשאר התאריכים אפשר לקבוע מדידה.";

async function axeViolations(page: Page): Promise<string[]> {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  return results.violations.map(
    (v) => `${v.id} — ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`,
  );
}

interface PaneOptions {
  /** The GET queue. Default: empty, then one row — "add landed". */
  list?: ReturnType<typeof ok>[];
  create?: ReturnType<typeof ok> | ReturnType<typeof refuse>;
}

async function installPane(page: Page, options: PaneOptions = {}) {
  return installManageApi(page, {
    staff: OWNER,
    replies: {
      "/manage/dresses": [ok(dressList())],
      [`/manage/dresses/${DRESS_ID}`]: [ok(dressDetail())],
      // Method-qualified: GET and POST share this path and answer different
      // shapes, which is exactly what the qualified form exists for.
      [`GET ${RESERVATIONS_PATH}`]: options.list ?? [ok({ items: [] })],
      [`POST ${RESERVATIONS_PATH}`]: [options.create ?? ok(reservation())],
      [`${RESERVATIONS_PATH}/res-1`]: [ok({ ok: true })],
    },
  });
}

async function openEditor(page: Page): Promise<void> {
  await page.goto(MANAGE);
  await expect(page.getByRole("heading", { level: 2, name: NAV_DASHBOARD })).toBeVisible();
  await page
    .getByRole("navigation")
    .getByRole("button", { name: NAV_CATALOG, exact: true })
    .click();
  await page.getByRole("button", { name: new RegExp(DRESS_NAME) }).click();
  await expect(page.getByRole("heading", { name: PANE_HEADING })).toBeVisible();
}

// --- 1. the manage journey -----------------------------------------------------

test("reservations: the owner records a rental from the wedding date alone", async ({ page }) => {
  const api = await installPane(page, {
    list: [ok({ items: [] }), ok({ items: [reservation()] })],
  });
  await openEditor(page);

  await expect(page.getByText(EMPTY_TITLE)).toBeVisible();

  // The prefill is the pane's one piece of real arithmetic: the range fills
  // itself from the wedding day plus the buffer, and both fields stay editable.
  await page.getByLabel(WEDDING_LABEL).fill("2099-08-12");
  await expect(page.getByLabel(START_LABEL)).toHaveValue("2099-08-12");
  await expect(page.getByLabel(END_LABEL)).toHaveValue("2099-08-17");

  await page.getByRole("button", { name: new RegExp(ADD_LABEL) }).click();

  await expect(page.getByText(ADDED_CUE)).toBeVisible();
  await expect(page.getByText("12–18")).toBeVisible();
  await expect(page.getByText(EMPTY_TITLE)).toHaveCount(0);

  const [created] = api.of(RESERVATIONS_PATH).filter((entry) => entry.method === "POST");
  expect(created.body).toEqual({
    starts_on: "2099-08-12",
    ends_on: "2099-08-17",
    customer_id: null,
    notes: null,
  });
});

test("reservations: an overlapping add names the clashing dates and keeps the form", async ({
  page,
}) => {
  await installPane(page, {
    create: refuse(409, "RESERVATION_OVERLAP", {
      starts_on: "2099-08-12",
      ends_on: "2099-08-18",
    }),
  });
  await openEditor(page);

  await page.getByLabel(START_LABEL).fill("2099-08-15");
  await page.getByLabel(END_LABEL).fill("2099-08-20");
  await page.getByRole("button", { name: new RegExp(ADD_LABEL) }).click();

  const alert = page.getByRole("alert").filter({ hasText: OVERLAP_LEAD });
  await expect(alert).toBeVisible();
  // The RANGE, not a generic conflict — the pane says which dates collide so
  // she fixes the form without leaving it.
  await expect(alert).toContainText("12–18");
  // And nothing she typed is thrown away: the fix is editing dates.
  await expect(page.getByLabel(START_LABEL)).toHaveValue("2099-08-15");
  await expect(page.getByLabel(END_LABEL)).toHaveValue("2099-08-20");
});

test("reservations: deleting confirms in a modal and lands focus on the list region", async ({
  page,
}) => {
  await installPane(page, {
    list: [ok({ items: [reservation()] }), ok({ items: [] })],
  });
  await openEditor(page);

  await expect(page.getByText("12–18")).toBeVisible();
  await page.getByRole("button", { name: new RegExp(DELETE_LABEL) }).first().click();

  const dialog = page.getByRole("dialog", { name: DELETE_TITLE });
  await expect(dialog).toBeVisible();
  // The end-early copy IS the modal body — there is no second action for it.
  await expect(dialog).toContainText("מפנה את התאריכים באתר מיד");
  await dialog.getByRole("button", { name: DELETE_LABEL }).click();

  await expect(page.getByText(DELETED_CUE)).toBeVisible();
  await expect(page.getByText(EMPTY_TITLE)).toBeVisible();

  // ⚠ THE ASSERTION THIS FILE EXISTS FOR. The delete trigger unmounted with its
  // row, so the dialog's native focus return lands on <body> — the pane moves
  // focus explicitly to its own status region instead.
  const focusedRole = await page.evaluate(() => document.activeElement?.getAttribute("role"));
  expect(focusedRole).toBe("status");
});

// --- 2. axe, manage ------------------------------------------------------------

test("reservations: zero axe violations across the pane's four states", async ({ page }) => {
  await installPane(page, {
    list: [ok({ items: [reservation({ customer_name: "רותם לוי", notes: "חתונה בקיסריה" })] })],
    create: refuse(409, "RESERVATION_OVERLAP", {
      starts_on: "2099-08-12",
      ends_on: "2099-08-18",
    }),
  });
  await openEditor(page);

  // Loaded.
  expect(await axeViolations(page), "loaded pane").toEqual([]);

  // Overlap error.
  await page.getByLabel(START_LABEL).fill("2099-08-15");
  await page.getByLabel(END_LABEL).fill("2099-08-20");
  await page.getByRole("button", { name: new RegExp(ADD_LABEL) }).click();
  await expect(page.getByRole("alert").filter({ hasText: OVERLAP_LEAD })).toBeVisible();
  expect(await axeViolations(page), "overlap error").toEqual([]);

  // Modal open.
  await page.getByRole("button", { name: new RegExp(DELETE_LABEL) }).first().click();
  await expect(page.getByRole("dialog", { name: DELETE_TITLE })).toBeVisible();
  expect(await axeViolations(page), "delete modal").toEqual([]);
});

test("reservations: the create-mode pane is disabled, explained, and axe-clean", async ({
  page,
}) => {
  await installPane(page);
  await page.goto(MANAGE);
  await expect(page.getByRole("heading", { level: 2, name: NAV_DASHBOARD })).toBeVisible();
  await page
    .getByRole("navigation")
    .getByRole("button", { name: NAV_CATALOG, exact: true })
    .click();
  await page.getByRole("button", { name: NEW_DRESS }).first().click();

  await expect(page.getByRole("heading", { name: PANE_HEADING })).toBeVisible();
  // Three panes now name reservations in the hint — the reword the pane brought.
  await expect(page.getByText(CREATE_HINT)).toHaveCount(3);
  await expect(page.getByRole("button", { name: new RegExp(ADD_LABEL) })).toBeDisabled();
  expect(await axeViolations(page), "create-mode pane").toEqual([]);
});

// --- 3. the storefront ---------------------------------------------------------

const DRESS_WITH_RANGES = {
  id: "d-away",
  name: "טוליפ",
  description: null,
  price_agorot: 420000,
  reserved: false,
  sizes: [{ size_label: "38", available: true }],
  media: [],
  unavailable_ranges: [
    { starts_on: "2099-08-12", ends_on: "2099-08-18" },
    { starts_on: "2099-12-28", ends_on: "2100-01-02" },
  ],
};

async function installStorefront(page: Page): Promise<void> {
  await page.route("**/storefront/**", async (route) => {
    const { pathname } = new URL(route.request().url());
    const send = (body: unknown, status = 200) =>
      route.fulfill({
        status,
        headers: { "content-type": "application/json", "cache-control": "no-store" },
        body: JSON.stringify(body),
      });
    if (pathname === "/storefront/boutique") {
      await send({
        name: "בוטיק אלמה",
        essence: null,
        description: null,
        phone: "052-1234567",
        address: "הרצל 1, תל אביב",
        maps_url: null,
        instagram: null,
        hours: [],
        exceptions: [],
        privacy_notice: null,
        privacy_dpa: null,
        privacy_subprocessors: null,
      });
      return;
    }
    if (pathname === `/storefront/dresses/${DRESS_WITH_RANGES.id}`) {
      await send(DRESS_WITH_RANGES);
      return;
    }
    await send({ error: { code: "NOT_FOUND", message: "Nothing is stubbed here." } }, 404);
  });
}

test("dress page: the booked-out dates read as a statement and the CTA stays live", async ({
  page,
}) => {
  await installStorefront(page);
  await page.goto(`${STOREFRONT}/dress/${DRESS_WITH_RANGES.id}`);

  await expect(page.getByRole("heading", { name: RESERVED_DATES_HEADING })).toBeVisible();
  // Same-month collapses to one numeral island; the cross-year pair splits.
  await expect(page.getByText("12–18")).toBeVisible();
  await expect(page.getByText("28 בדצמבר 2099")).toBeVisible();
  await expect(page.getByText("2 בינואר 2100")).toBeVisible();
  // Q9 spelled as copy — the line that keeps the CTA honest.
  await expect(page.getByText(RESERVED_DATES_NOTE)).toBeVisible();

  // RTL: every numeral run is its own isolated island, or it reorders around
  // the Hebrew month name beside it.
  const isolated = await page.getByText("12–18").evaluate((node) => node.tagName);
  expect(isolated).toBe("BDI");

  // The whole point of D6: a booked-out window does not close the door.
  const cta = page.getByRole("link", { name: "קביעת תור" });
  await expect(cta).toBeVisible();
  await expect(cta).toHaveAttribute("href", `/book/slot/${DRESS_WITH_RANGES.id}`);

  expect(await axeViolations(page), "dress page with ranges").toEqual([]);
});
