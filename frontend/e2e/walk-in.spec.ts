import { test, expect } from "@playwright/test";
import type { Locator, Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { MANAGE, installManageApi, ok, refuse, staff, staffCard, floorPayload } from "./fixtures/manage";
import type { Recorder } from "./fixtures/manage";

// F50's walk-in booking, in a browser that actually implements <dialog>.
//
// ⚠ **THE FOUR FOCUS RULES AT THE BOTTOM LIVE HERE BECAUSE THE UNIT SUITE
// CANNOT FAIL THEM.** `apps/manage/src/test/setup.ts` stubs
// `HTMLDialogElement.showModal()` as `this.open = true` and nothing else — no
// focus move, no trap, no top layer, no `cancel` on Esc. Under that stub focus
// never LEAVES the trigger, so a jsdom assertion that focus came BACK to
// «תור חדש» is true before the component runs and stays true with every line of
// it deleted. `dialog-focus.spec.ts` is the shipped home of that argument and
// carries the full mutation ledger; F50's dialog joins it here rather than there
// only because its fixtures (a customer search and a type list) are this file's.
//
// The four rules, one named test each:
//   1. opening moves focus INTO the dialog, onto the search field
//   2. Tab from the last focusable wraps to the first, Shift+Tab the reverse
//   3. Esc closes it — and creates nothing
//   4. closing restores focus to «תור חדש»
//
// MUTATION LEDGER, so nobody has to trust the claim:
//   M1  `dlg.setAttribute("open", "")` in place of `dlg.showModal()` in
//       `packages/ui/src/components/Modal.tsx` — the jsdom stub's exact
//       behaviour, rendered in a real browser. ALL FOUR RULES RED, which is the
//       whole argument for putting them here: what the unit suite fakes is
//       precisely what they measure. The dialog paints, every control in it is
//       readable, and focus never moves. The three journeys above stay green,
//       which is correct — they are about state, and state is what jsdom
//       reports honestly.
//   M2  `dlg.show()` in place of `dlg.showModal()` — a dialog that renders and
//       takes focus identically but is neither modal nor inert. Rules 2 and 3
//       red; rules 1 and 4 stay green, which is correct — `show()` runs the same
//       focusing steps and the same focus restore.
//   M3  the `walkin.empty` render replaced by `{null}` — EXACTLY ONE test reds,
//       the empty-state journey, which is what says that assertion is about the
//       SENTENCE and not about the dialog having opened.
//
// ⚠ **Risk 6, as everywhere in this directory: the harness stubs the API, so
// these prove the CONSOLE and not the CONTRACT.**

// --- copy, verbatim from apps/manage/src/i18n/he.ts --------------------------

const NAV_BOARD = "לוח היום";
const DASHBOARD_HEADING = "סקירה";
const BOARD_HEADING = "לוח היום";
const NEW_WALK_IN = "תור חדש";
const WALK_IN_TITLE = "תור חדש בבוטיק";
const SEARCH_LABEL = "לקוחה";
const TYPE_LABEL = "סוג הפגישה";
const CONFIRM = "יצירת התור";
const DISMISS = "ביטול";
const EMPTY_HEAD = "לא נמצאה לקוחה עם השם או הטלפון האלה.";
const CHECKIN_NAV = "קוד סריקה";
const CHECKED_IN_AT = "נרשמה הגעה";
const SOURCE_WALK_IN = "נכנסה";

const MICHAL = "מיכל לוי";
const MANAGER = staff({ id: "st-mgr", display_name: "דנה", role: "shift_manager" });
const MANAGER_CARD = staffCard({ id: "st-mgr", display_name: "דנה", role: "shift_manager" });

// 08:20Z is 11:20 in Jerusalem. The board renders Jerusalem time and the config
// pins the locale, not the zone, so the literal below is what a staffer reads.
const CREATED_AT = "2099-01-04T08:20:00Z";

const CUSTOMER = { id: "c-michal", name: MICHAL, phone: "+972501234567", tags: [] };

const TYPE = {
  id: "at-1",
  name: "מדידה ראשונה",
  duration_minutes: 60,
  audience: "brides_only",
  deposit_required: false,
  deposit_amount_agorot: null,
  sort_order: 1,
};

// The row the server answers AFTER the create — already checked in, which is the
// whole point: `starts_at === checked_in_at === now`.
const WALK_IN_ROW = {
  id: "b-walk",
  starts_at: CREATED_AT,
  status: "confirmed",
  attendance_confirmed_at: null,
  checked_in_at: CREATED_AT,
  customer_name: MICHAL,
  appointment_type_name: TYPE.name,
  dress_name: null,
  payment_status: null,
  refund_due_agorot: null,
  source: "walk_in",
};

const WALK_IN_DETAIL = {
  ...WALK_IN_ROW,
  customer_phone: CUSTOMER.phone,
  notes: null,
  dress_id: null,
  dress_size: null,
  seat_index: 1,
  created_at: CREATED_AT,
  // The pair F50 made nullable. A walk-in has no terms evidence because nobody
  // accepted anything.
  terms_version_accepted: null,
  terms_accepted_at: null,
  cancelled_at: null,
  cancelled_by: null,
  manage_link_issued: false,
};

function bookings(items: unknown[]) {
  return { items, total: items.length, offset: 0, limit: 50 };
}

// --- helpers -----------------------------------------------------------------

interface InstallOptions {
  customers?: unknown[];
  after?: unknown[];
  create?: Parameters<typeof ok>[0] | ReturnType<typeof refuse>;
}

async function installWalkIn(page: Page, options: InstallOptions = {}): Promise<Recorder> {
  const customers = options.customers ?? [CUSTOMER];
  const after = options.after ?? [WALK_IN_ROW];
  return installManageApi(page, {
    staff: MANAGER,
    replies: {
      "/manage/floor": [ok(floorPayload({ staff: [MANAGER_CARD], rooms: [] }))],
      // Two entries: the day is empty until the create lands, and the poll's
      // next tick answers the row. `take()` repeats the last one forever.
      "/manage/bookings": [ok(bookings([])), ok(bookings(after))],
      "/manage/customers": [
        ok({ items: customers, total: customers.length, offset: 0, limit: 10 }),
      ],
      "/manage/appointment-types": [ok([TYPE])],
      "/manage/bookings/walk-in": [
        (options.create as { status: number; body: unknown } | undefined) ?? ok(WALK_IN_DETAIL),
      ],
    },
  });
}

// The board's h2 is written only from a settled list — the "the data landed"
// tell every other spec in this directory uses.
async function gotoBoard(page: Page): Promise<void> {
  await page.goto(MANAGE);
  await expect(page.getByRole("heading", { level: 2, name: DASHBOARD_HEADING })).toBeVisible();
  await page.getByRole("navigation").getByRole("button", { name: NAV_BOARD }).click();
  await expect(page.getByRole("heading", { level: 2, name: BOARD_HEADING })).toBeVisible();
}

function trigger(page: Page): Locator {
  return page.getByRole("button", { name: NEW_WALK_IN });
}

async function openDialog(page: Page): Promise<Locator> {
  await gotoBoard(page);
  await expect(trigger(page)).toBeVisible();
  await trigger(page).click();
  const dialog = page.getByRole("dialog", { name: WALK_IN_TITLE });
  await expect(dialog).toBeVisible();
  return dialog;
}

// FIRST focusable: the search field. LAST: the confirm, `footer`'s second.
function first(dialog: Locator): Locator {
  return dialog.getByLabel(SEARCH_LABEL);
}

function last(dialog: Locator): Locator {
  return dialog.getByRole("button", { name: CONFIRM });
}

// `document.activeElement` is `<body>` and no control holds focus — what one Tab
// off the end of a top layer produces in Chromium, and the shape that says the
// press went NOWHERE rather than onto the screen behind.
async function focusIsOnNothing(page: Page): Promise<boolean> {
  return page.evaluate(() => document.activeElement === document.body);
}

async function pickBoth(dialog: Locator): Promise<void> {
  await first(dialog).fill("מיכל");
  await dialog.getByRole("radio", { name: new RegExp(MICHAL) }).click();
  await dialog.getByLabel(TYPE_LABEL).selectOption(TYPE.id);
}

// --- 1. the journey ----------------------------------------------------------

test("walk-in: a shift manager creates a booking for a customer the boutique already holds", async ({
  page,
}) => {
  const api = await installWalkIn(page);
  const dialog = await openDialog(page);

  await pickBoth(dialog);
  await last(dialog).click();

  await expect(dialog).toBeHidden();

  // EXACTLY TWO KEYS on the wire, and the absences are the feature: no name, no
  // phone, no marketing_consent, no starts_at.
  const created = api.of("/manage/bookings/walk-in");
  expect(created).toHaveLength(1);
  expect(created[0].method).toBe("POST");
  expect(created[0].body).toEqual({ customer_id: CUSTOMER.id, appointment_type_id: TYPE.id });

  // The row lands ALREADY CHECKED IN — the board's whole job is answering "is
  // she here yet", and the answer for a bride at the counter is yes.
  const row = page.locator('[data-booking-id="b-walk"]');
  await expect(row).toBeVisible();
  await expect(row.getByTestId("board-arrival")).toContainText(CHECKED_IN_AT);
  // One muted word for the source, never a second Badge.
  await expect(row).toContainText(SOURCE_WALK_IN);
  await expect(row.getByTestId("board-status")).toHaveCount(1);

  // The announced cue names the bride: after one tap on a busy board a nameless
  // confirmation is useless exactly when it is needed.
  await expect(page.getByTestId("board-cue")).toContainText(MICHAL);
});

// --- 2. the ruling, at the counter -------------------------------------------

test("walk-in: an unknown customer is routed to the check-in form, not to a create", async ({
  page,
}) => {
  // ⚠ D3 AS A RENDERED SENTENCE. A walk-in for a customer the boutique does not
  // yet hold is refused on purpose — a `customers` row is proof of phone
  // possession because it is written only after an OTP, and a dialog that typed
  // a name and a number would be a fourth §11 collection point whose notice
  // could only be delivered by asking a staffer to recite it aloud.
  // MUTATION PROOF (M3).
  const api = await installWalkIn(page, { customers: [] });
  const dialog = await openDialog(page);

  await first(dialog).fill("שם שלא קיים");

  const empty = dialog.getByTestId("walkin-empty");
  await expect(empty).toContainText(EMPTY_HEAD);
  await expect(empty).toContainText(CHECKIN_NAV);
  // The confirm never arms, and nothing was sent.
  await expect(last(dialog)).toBeDisabled();
  expect(api.of("/manage/bookings/walk-in")).toHaveLength(0);
});

// --- 3. axe ------------------------------------------------------------------

test("walk-in: zero axe A/AA violations with the dialog open and results on screen", async ({
  page,
}) => {
  await installWalkIn(page);
  const dialog = await openDialog(page);
  await first(dialog).fill("מיכל");
  await expect(dialog.getByRole("radio", { name: new RegExp(MICHAL) })).toBeVisible();

  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(
    results.violations.map((v) => `${v.id} — ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`),
  ).toEqual([]);
});

// --- 4. the four <dialog> rules ----------------------------------------------

test("walk-in dialog: opening it moves focus off «תור חדש» and into the search field", async ({
  page,
}) => {
  await installWalkIn(page);
  const dialog = await openDialog(page);

  // The body is static at open — no seed race — so the landing target can be
  // named outright. MUTATION PROOF (M1): open the <dialog> by ATTRIBUTE instead
  // of calling showModal() and this reds; the dialog paints and focus never
  // moves.
  await expect(first(dialog)).toBeFocused();
  await expect(trigger(page)).not.toBeFocused();
});

test("walk-in dialog: Tab off the confirm wraps to the search field, and Shift+Tab back", async ({
  page,
}) => {
  await installWalkIn(page);
  const dialog = await openDialog(page);
  // The confirm is `disabled` until both fields are chosen, and a disabled
  // control is not in the tab order — so the walk is measured on the ARMED
  // dialog, which is also the state a staffer is in when she reaches for it.
  await pickBoth(dialog);

  // TWO presses per direction, and the middle stop is Chromium's rather than a
  // wart in the test: tabbing off the end of a top layer parks on the document
  // before wrapping. THAT is what the assertion in between is for — the board
  // behind is inert, so the press lands on NOTHING.
  //
  // MUTATION PROOF (M2): `dlg.show()` instead of `dlg.showModal()` and this
  // reds — a non-modal <dialog> renders and takes focus identically but makes
  // nothing inert, so the walk leaves the dialog and never comes back.
  await last(dialog).focus();
  await page.keyboard.press("Tab");
  expect(await focusIsOnNothing(page)).toBe(true);
  await page.keyboard.press("Tab");
  await expect(first(dialog)).toBeFocused();

  await first(dialog).focus();
  await page.keyboard.press("Shift+Tab");
  expect(await focusIsOnNothing(page)).toBe(true);
  await page.keyboard.press("Shift+Tab");
  await expect(last(dialog)).toBeFocused();
});

test("walk-in dialog: Esc closes it without creating a booking", async ({ page }) => {
  const api = await installWalkIn(page);
  const dialog = await openDialog(page);
  await pickBoth(dialog);

  // MUTATION PROOF (M2). And the second assertion is why this dialog earns a
  // named Esc test rather than inheriting the registry's: a dismiss that created
  // the booking would put a real appointment on the board by a mis-key, on a
  // fully armed form.
  await page.keyboard.press("Escape");

  await expect(dialog).toBeHidden();
  expect(api.of("/manage/bookings/walk-in")).toHaveLength(0);
});

test("walk-in dialog: closing it restores focus to «תור חדש»", async ({ page }) => {
  await installWalkIn(page);
  const dialog = await openDialog(page);

  // Dismissed by its own control rather than by Esc, so this measures the RETURN
  // and not the key the test above owns. MUTATION PROOF (M1): the platform's own
  // return is what carries this — the board's trigger does NOT unmount, which is
  // exactly why `create()` deliberately moves focus nowhere on success.
  await dialog.getByRole("button", { name: DISMISS }).click();

  await expect(dialog).toBeHidden();
  await expect(trigger(page)).toBeFocused();
});
