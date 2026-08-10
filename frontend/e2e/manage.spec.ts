import { test, expect } from "@playwright/test";
import type { Locator, Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import {
  MANAGE,
  PHOTO_CONFIRMED_AT,
  PHOTO_DATA_URI,
  SELF_ID,
  appointmentTypes,
  assignment,
  availabilityPayload,
  bookingList,
  customerList,
  dashboardPopulated,
  dispatchResult,
  dressList,
  floorPayload,
  gatewayStatus,
  installManageApi,
  installStorageUpload,
  ok,
  privacyPayload,
  queuePath,
  refuse,
  room,
  roomPath,
  settingsAfterToggle,
  settingsPayload,
  settleAnimations,
  staff,
  staffCard,
  staffList,
  staffPath,
  staffPresign,
  termsHistory,
  waitlist,
  waitlistEntry,
} from "./fixtures/manage";
import type { Reply, WaitlistEntry } from "./fixtures/manage";

// The console's first coverage BEHIND its login screen. `a11y.spec.ts` keeps
// the three unauthenticated `manage:` tests — they are the login screen's own
// pass and stay valuable as such.
//
// ⚠ **These journeys exist here rather than in the unit suite because jsdom is
// not a browser.** A real browser blurs a `disabled` control the instant a
// request starts and jsdom does not, which is how F57 shipped a focus test that
// asserted nothing. Every focus assertion below is measured in Chromium.
//
// ⚠ **Risk 6, restated at the point of use: the harness stubs the API, so these
// prove the CONSOLE and not the CONTRACT.** A renamed payload key passes every
// test in this file.

// --- copy, verbatim from apps/manage/src/i18n/he.ts --------------------------

const LOGIN_SUBMIT = "כניסה";
const NAV_FLOOR = "הצוות בקומה";
const NAV_BOARD = "לוח היום";
const DASHBOARD_HEADING = "סקירה";
const FLOOR_HEADING = "צוות בקומה";
const ROOMS_HEADING = "חדרי מדידה";
const WAITLIST_HEADING = "ממתינות בתור";
const WAITLIST_EMPTY = "אין ממתינות בתור";
const TAKE_NEXT = "קחי את הבאה";
const CLAIM = "תפיסת החדר";
const ROOM_FREE = "פנוי";
const ROOM_OCCUPIED = "תפוס";
const CALLED_BADGE = "נקראה";
const TRUNCATED = "הרשימה חלקית. הממתינות שהגיעו מאוחר יותר אינן מופיעות כאן.";
const DUPLICATE_LINE = "יש עוד כניסה פעילה היום עם אותו מספר טלפון.";
const SKIPPED_ONCE = "דילגו עליה פעם אחת";
const CONFIRM_YES = "אישור ההסרה";
const CONFIRM_KEEP = "השארה בתור";
const CONFIRM_REMOVE_DUPLICATE =
  "אם הטלפון שלה מציג את הכניסה הזו, המסך שלה יראה שהביקור הסתיים. אפשר לומר לה שהמקום שלה נשמר.";
const ASSIGN_CONFIRM = "שיבוץ";
const REMOVED_CUE = "הוסרה מהתור.";
const SKIPPED_CUE = "הועברה לסוף התור.";
const QUEUE_EMPTY_ALERT = "אין ממתינות בתור.";
const OUTAGE_ALERT = "לא הצלחנו לטעון את רשימת הצוות כרגע.";
const ROW_GONE_ALERT = "הכניסה הזו כבר לא קיימת. הרשימה תתוקן בעדכון הבא.";

const takeNextAria = (label: string) => `${TAKE_NEXT} בתור — ${label}`;
const callAria = (name: string) => `קראי — ${name}`;
const assignAria = (name: string) => `שבצי לחדר — ${name}`;
const skipAria = (name: string) => `דלגי — ${name}`;
const removeAria = (name: string) => `הסרה — ${name}`;
const dispatchedCue = (label: string) => `הלקוחה שובצה: ${label}.`;
const roomOccupied = (name: string) => `${name} כבר בחדר הזה.`;
const confirmRemove = (name: string) => `להסיר את ${name} מהתור?`;
const confirmSkip = (name: string) => `דילוג נוסף יסיר את ${name} מהתור. להמשיך?`;

// --- fixture data ------------------------------------------------------------

// Three names, distinct from each other AND from the two staff names, so a row
// rendered in the wrong place is NAMED by the failure rather than merely
// counted. «נועה כהן» is the harness default and the one every verb acts on.
const NOA = "נועה כהן";
const SHIRA = "שירה לוי";
const TAMAR = "תמר אביב";

const ROOM_ONE = room({ id: "rm-1", label: "חדר 1" });
const ROOM_TWO = room({ id: "rm-2", label: "חדר 2", sort_order: 2 });

const MANAGER = staff({ id: "st-mgr", display_name: "דנה", role: "shift_manager" });
const MANAGER_CARD = staffCard({ id: "st-mgr", display_name: "דנה", role: "shift_manager" });

function threeWaiting(): WaitlistEntry[] {
  return [
    waitlistEntry({ id: "qt-1", name: NOA, position: 1 }),
    waitlistEntry({ id: "qt-2", name: SHIRA, position: 2, visit_type: "evening", called: true }),
    waitlistEntry({ id: "qt-3", name: TAMAR, position: 3, duplicate: true }),
  ];
}

// --- helpers -----------------------------------------------------------------

// The floor's "the data landed" tell. NOT the h2 — it renders over the skeleton
// while the first fetch is in flight, so measuring it would measure nothing.
// The waitlist h3 is written only from a settled payload, which is exactly the
// property every assertion below needs first.
async function floorSettled(page: Page): Promise<void> {
  await expect(page.getByRole("heading", { level: 3, name: WAITLIST_HEADING })).toBeVisible();
}

async function gotoFloor(page: Page): Promise<void> {
  await page.goto(MANAGE);
  await floorSettled(page);
}

// The two elevated roles land on «סקירה» and reach the floor through «לוח היום»
// — there is no second nav row for them (App.tsx's `floor` row is FLOOR_ONLY).
async function gotoBoardFloor(page: Page): Promise<void> {
  await page.goto(MANAGE);
  await expect(page.getByRole("heading", { level: 2, name: DASHBOARD_HEADING })).toBeVisible();
  await page.getByRole("navigation").getByRole("button", { name: NAV_BOARD }).click();
  await floorSettled(page);
}

function tile(page: Page, roomId: string): Locator {
  return page.locator(`[data-room-id="${roomId}"]`);
}

function row(page: Page, entryId: string): Locator {
  return page.locator(`[data-entry-id="${entryId}"]`);
}

function cue(page: Page): Locator {
  return page.getByTestId("floor-cue");
}

// The raw violation objects dump ~10 KB of axe internals into the failure; only
// the rule id and the offending selectors say anything useful.
async function axeViolations(page: Page): Promise<string[]> {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  return results.violations.map(
    (v) => `${v.id} — ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`,
  );
}

// The colour of a text node, as the browser paints it. The register distinction
// this feature turns on — NOTICE (--color-warning-text) vs OUTAGE
// (--color-ink-muted) — is a rendered fact, and comparing two live alerts to
// each other needs no token plumbing and no hex-to-rgb conversion.
function colorOf(locator: Locator): Promise<string> {
  return locator.evaluate((el) => getComputedStyle(el).color);
}

// --- 1. the floor renders behind the login screen ----------------------------

test("manage floor: reception signs in and the floor renders with a populated waitlist", async ({
  page,
}) => {
  const api = await installManageApi(page, {
    replies: {
      "/manage/floor": [
        ok(
          floorPayload({
            rooms: [ROOM_ONE, room({ ...ROOM_TWO, assignment: assignment() })],
            waitlist: waitlist(threeWaiting(), true),
          }),
        ),
      ],
    },
  });

  await gotoFloor(page);

  // The login screen is GONE — the whole point of the harness.
  await expect(page.getByRole("button", { name: LOGIN_SUBMIT })).toHaveCount(0);
  await expect(page.getByRole("heading", { level: 2, name: FLOOR_HEADING })).toBeVisible();
  await expect(page.getByRole("heading", { level: 3, name: ROOMS_HEADING })).toBeVisible();

  // Reception reaches exactly one section, so `activeKey` lands on the floor
  // with no navigation at all.
  const nav = page.getByRole("navigation").getByRole("button");
  await expect(nav).toHaveCount(1);
  await expect(nav).toHaveText(NAV_FLOOR);

  // Three rows, in the server's order, each named.
  const rows = page.locator("[data-entry-id]");
  await expect(rows).toHaveCount(3);
  await expect(rows.nth(0)).toContainText(NOA);
  await expect(rows.nth(1)).toContainText(SHIRA);
  await expect(rows.nth(2)).toContainText(TAMAR);
  await expect(row(page, "qt-2").getByText(CALLED_BADGE)).toBeVisible();
  await expect(row(page, "qt-3").getByText(DUPLICATE_LINE)).toBeVisible();
  await expect(page.getByText(TRUNCATED).first()).toBeVisible();

  // ⚠ A29. The row carries F33's capability — `entry.id` is what /q/{id}
  // authenticates with — and the console must never render it as something a
  // browser will follow.
  await expect(page.locator('a[href*="/q/"]')).toHaveCount(0);
  for (const entry of threeWaiting()) {
    await expect(page.locator(`a[href*="${entry.id}"]`)).toHaveCount(0);
  }

  // Which controls EXIST is the rendered form of the authorization axes: a
  // reception staffer may call and assign, and «דלגי»/«הסרה» are ABSENT rather
  // than disabled.
  await expect(page.getByRole("button", { name: callAria(NOA) })).toBeVisible();
  await expect(page.getByRole("button", { name: assignAria(NOA) })).toBeVisible();
  await expect(page.getByRole("button", { name: skipAria(NOA) })).toHaveCount(0);
  await expect(page.getByRole("button", { name: removeAria(NOA) })).toHaveCount(0);

  // Three GETs and not one stray request: no other panel mounts for reception.
  expect(api.of("/manage/auth/me")).toHaveLength(1);
  expect(api.of("/manage/dashboard")).toHaveLength(0);
  expect(api.of("/manage/bookings")).toHaveLength(0);
  expect(api.of("/manage/floor").length).toBeGreaterThan(0);

  // ⚠ THE HARNESS'S OWN REGRESSION GUARD, and it has to be a live fetch rather
  // than a scan of the recorder — the recorder can only ever hold paths the
  // interceptor matched, so a filter over it would assert nothing at all.
  // `apps/manage` builds with `base: "/manage/"`, so `/manage/index.html`,
  // `/manage/assets/*.js` and `/manage/favicon.svg` all sit under the prefix: a
  // route registered on `**​/manage/**` serves the SHELL from the fixture and
  // the console is a blank page with no error anywhere. Widen the predicate and
  // this returns the house 404's JSON instead of the document.
  const shell = await page.evaluate(async () => (await fetch("/manage/index.html")).text());
  expect(shell.slice(0, 200).toLowerCase(), "the interceptor swallowed the app's own shell").toContain(
    "<!doctype html",
  );
});

// --- 2. the headline act -----------------------------------------------------

test("manage floor: take-next fills the tile, drops the row, and names the ROOM in the cue", async ({
  page,
}) => {
  const seated = room({
    ...ROOM_ONE,
    assignment: assignment({ client_label: NOA, staff_display_name: "רונית" }),
  });
  const after = floorPayload({
    rooms: [seated],
    waitlist: waitlist([waitlistEntry({ id: "qt-2", name: SHIRA, position: 1 })]),
  });

  const api = await installManageApi(page, {
    replies: {
      // TWO entries: the second is what every 5s tick answers from then on. A
      // one-element queue would put the dispatched row back under the assertion.
      "/manage/floor": [
        ok(
          floorPayload({
            rooms: [ROOM_ONE],
            waitlist: waitlist([
              waitlistEntry({ id: "qt-1", name: NOA, position: 1 }),
              waitlistEntry({ id: "qt-2", name: SHIRA, position: 2 }),
            ]),
          }),
        ),
        ok(after),
      ],
      [`${roomPath("rm-1")}/take-next`]: [
        ok(dispatchResult(seated, [waitlistEntry({ id: "qt-2", name: SHIRA, position: 1 })])),
      ],
    },
  });

  await gotoFloor(page);
  await expect(tile(page, "rm-1").getByText(ROOM_FREE)).toBeVisible();

  await page.getByRole("button", { name: takeNextAria("חדר 1") }).click();

  // ONE paint, both halves: the tile fills AND the row leaves. A client that
  // patched only the tile would render the same woman as in-service and waiting.
  await expect(tile(page, "rm-1").getByText(ROOM_OCCUPIED)).toBeVisible();
  await expect(tile(page, "rm-1")).toContainText(NOA);
  await expect(row(page, "qt-1")).toHaveCount(0);
  await expect(row(page, "qt-2")).toBeVisible();

  // ⚠ The cue names the ROOM and NEVER the customer. role="status" here is
  // PERSISTENT — nothing clears it, not a timer, not a tick, not an unmount — so
  // her name in it would outlive her row and, once she has left the shop, be the
  // only place it survives, on a screen five roles can read.
  await expect(cue(page)).toHaveText(dispatchedCue("חדר 1"));
  await expect(cue(page)).not.toContainText(NOA);

  // `{}` IS the one-tap take-next on herself: `staff_user_id` is never sent, and
  // the QUEUE chooses the customer — she does not.
  const sent = api.of(`${roomPath("rm-1")}/take-next`);
  expect(sent).toHaveLength(1);
  expect(sent[0].method).toBe("POST");
  expect(sent[0].body).toEqual({});
});

// --- 3. the refusal a component test cannot stage ----------------------------

test("manage floor: a refused take-next shows the tile's alert, moves focus into it, and keeps the row", async ({
  page,
}) => {
  await installManageApi(page, {
    replies: {
      "/manage/floor": [
        ok(
          floorPayload({
            rooms: [ROOM_ONE],
            waitlist: waitlist([waitlistEntry({ id: "qt-1", name: NOA, position: 1 })]),
          }),
        ),
      ],
      [`${roomPath("rm-1")}/take-next`]: [
        refuse(409, "ROOM_OCCUPIED", { staff_display_name: "מיכל" }),
      ],
    },
  });

  await gotoFloor(page);
  await page.getByRole("button", { name: takeNextAria("חדר 1") }).click();

  const alert = tile(page, "rm-1").getByRole("alert");
  await expect(alert).toHaveText(roomOccupied("מיכל"));

  // ⚠ THE ASSERTION THIS WHOLE FILE EXISTS FOR. @boutique/ui's Button is
  // `disabled={disabled || loading}`, so a REAL browser blurred the tapped
  // control the instant the request started and `document.activeElement` really
  // did drop to <body> — the precondition the panel's focus guard tests for.
  // jsdom does not blur a disabled element, so the unit suite can only reach
  // this by blurring by hand.
  await expect(alert).toBeFocused();

  // The tile stays free and the row stays put: nothing was dispatched.
  await expect(tile(page, "rm-1").getByText(ROOM_FREE)).toBeVisible();
  await expect(row(page, "qt-1")).toBeVisible();
  await expect(cue(page)).not.toContainText(dispatchedCue("חדר 1"));
});

// --- 4. the empty queue is a normal outcome, not a fault ---------------------

test("manage floor: a take-next that loses the race says the queue is empty, in the notice register", async ({
  page,
}) => {
  await installManageApi(page, {
    replies: {
      "/manage/floor": [
        ok(
          floorPayload({
            rooms: [ROOM_ONE, ROOM_TWO],
            waitlist: waitlist([waitlistEntry({ id: "qt-1", name: NOA, position: 1 })]),
          }),
        ),
      ],
      [`${roomPath("rm-1")}/take-next`]: [refuse(409, "QUEUE_EMPTY")],
      // The OUTAGE comparand, on the other tile. `tileError` is one per panel,
      // so the second tap replaces the first alert — which is why the notice
      // colour is read before the second click.
      [`${roomPath("rm-2")}/take-next`]: [refuse(500, "INTERNAL")],
    },
  });

  await gotoFloor(page);

  await page.getByRole("button", { name: takeNextAria("חדר 1") }).click();
  const notice = tile(page, "rm-1").getByRole("alert");
  // «waitlist.empty» plus a full stop: the alert answers her TAP, the EmptyState
  // one panel below answers the screen.
  await expect(notice).toHaveText(QUEUE_EMPTY_ALERT);
  const noticeColor = await colorOf(notice);

  await page.getByRole("button", { name: takeNextAria("חדר 2") }).click();
  const outage = tile(page, "rm-2").getByRole("alert");
  await expect(outage).toHaveText(OUTAGE_ALERT);
  const outageColor = await colorOf(outage);

  // ⚠ Without the QUEUE_EMPTY branch the first tap takes the FALL-THROUGH and
  // tells a manager whose queue is simply empty that the STAFF LIST failed to
  // load — in the muted outage colour on top. Both halves are pinned: the
  // sentence and the register.
  expect(noticeColor, `notice and outage painted the same colour: ${noticeColor}`).not.toBe(
    outageColor,
  );
});

// --- 5. the one irreversible act, behind a two-step confirm ------------------

test("manage board: a shift manager removes a duplicate through the two-step confirm", async ({
  page,
}) => {
  const survivor = waitlistEntry({ id: "qt-1", name: NOA, position: 1 });
  const api = await installManageApi(page, {
    staff: MANAGER,
    replies: {
      "/manage/floor": [
        ok(
          floorPayload({
            staff: [MANAGER_CARD],
            rooms: [ROOM_ONE],
            waitlist: waitlist([
              survivor,
              waitlistEntry({ id: "qt-dup", name: NOA, position: 2, duplicate: true }),
            ]),
          }),
        ),
        ok(
          floorPayload({
            staff: [MANAGER_CARD],
            rooms: [ROOM_ONE],
            waitlist: waitlist([survivor]),
          }),
        ),
      ],
      [`${queuePath("qt-dup")}/remove`]: [ok(waitlist([survivor]))],
    },
  });

  await gotoBoardFloor(page);
  // The board is on the same screen; the floor is beneath it.
  await expect(page.getByRole("heading", { level: 2, name: NAV_BOARD })).toBeVisible();

  const duplicate = row(page, "qt-dup");
  await expect(duplicate.getByText(DUPLICATE_LINE)).toBeVisible();

  await duplicate.getByRole("button", { name: removeAria(NOA) }).click();

  // The reveal is INSIDE the row, not a <dialog>: no second focus trap, no
  // inert, no scroll lock, and axe can see all of it.
  await expect(duplicate.getByRole("dialog")).toHaveCount(0);
  await expect(duplicate.getByText(confirmRemove(NOA))).toBeVisible();
  // The one consequence the manager can repair, and it is only offered when the
  // row is flagged.
  await expect(duplicate.getByText(CONFIRM_REMOVE_DUPLICATE)).toBeVisible();
  // NOTHING has been sent yet. That is the whole of "two-step".
  expect(api.of(`${queuePath("qt-dup")}/remove`)).toHaveLength(0);

  await expect(duplicate.getByRole("button", { name: CONFIRM_KEEP })).toBeVisible();
  await duplicate.getByRole("button", { name: CONFIRM_YES }).click();

  await expect(row(page, "qt-dup")).toHaveCount(0);
  await expect(row(page, "qt-1")).toBeVisible();
  expect(api.of(`${queuePath("qt-dup")}/remove`)).toHaveLength(1);

  // The cue NAMES THE ACT, never the person — the same rule the dispatch cue
  // keeps, and it bites hardest here: after a removal her row is gone and a
  // persistent region would be the last place her name survived.
  await expect(cue(page)).toHaveText(REMOVED_CUE);
  await expect(cue(page)).not.toContainText(NOA);
});

// --- 6. the second skip is a removal, and it says so ------------------------

test("manage board: a skip at skip_count 1 confirms first and sends the count the screen rendered", async ({
  page,
}) => {
  const skipped = waitlistEntry({ id: "qt-1", name: SHIRA, position: 1, skip_count: 1 });
  const api = await installManageApi(page, {
    staff: MANAGER,
    replies: {
      "/manage/floor": [
        ok(
          floorPayload({
            staff: [MANAGER_CARD],
            rooms: [ROOM_ONE],
            waitlist: waitlist([skipped, waitlistEntry({ id: "qt-2", name: TAMAR, position: 2 })]),
          }),
        ),
        ok(
          floorPayload({
            staff: [MANAGER_CARD],
            rooms: [ROOM_ONE],
            waitlist: waitlist([waitlistEntry({ id: "qt-2", name: TAMAR, position: 1 })]),
          }),
        ),
      ],
      [`${queuePath("qt-1")}/skip`]: [
        ok(waitlist([waitlistEntry({ id: "qt-2", name: TAMAR, position: 1 })])),
      ],
    },
  });

  await gotoBoardFloor(page);

  const target = row(page, "qt-1");
  await expect(target.getByText(SKIPPED_ONCE)).toBeVisible();
  await target.getByRole("button", { name: skipAria(SHIRA) }).click();

  // A control that silently changes meaning on its second press is exactly the
  // shape `skip_count` is on the wire to prevent, so the second press ASKS.
  await expect(target.getByText(confirmSkip(SHIRA))).toBeVisible();
  expect(api.of(`${queuePath("qt-1")}/skip`)).toHaveLength(0);

  await target.getByRole("button", { name: CONFIRM_YES }).click();
  await expect(row(page, "qt-1")).toHaveCount(0);

  // ⚠ `seen_skip_count` is the value the CLIENT RENDERED, sent verbatim — the
  // whole of what stops two managers each tapping «דלגי» ONCE on a woman at
  // skip_count 0 and removing her with the confirm shown on neither device. A
  // hardcoded 0 here would be that defect, and the recorder is the only place a
  // test can see what was actually sent.
  const sent = api.of(`${queuePath("qt-1")}/skip`);
  expect(sent).toHaveLength(1);
  expect(sent[0].body).toEqual({ seen_skip_count: 1 });
});

// --- 6b. the FIRST skip travels, and focus must not travel with it ----------

test("manage board: a first skip moves the row to the end and hands focus to the panel heading", async ({
  page,
}) => {
  // ⚠ THE ONE PATH WITH NO REVEAL, which is why it is the one that broke and
  // the one that has to be measured in Chromium. At skip_count 0 there is no
  // confirm, so `loading` lands on the control she TAPPED — a real browser
  // blurs it, `document.activeElement` drops to <body>, and the panel can no
  // longer read which row she was in off the DOM. Every other verb here closes
  // a reveal on its way out and is caught by that reveal's own focus fallback;
  // this one has no fallback at all, so MOVE 3 is the only mechanism and it was
  // standing down. jsdom keeps focus on the disabled button, which is exactly
  // why the unit test for this could pass while the browser scrolled the page
  // to the moved row instead.
  const api = await installManageApi(page, {
    staff: MANAGER,
    replies: {
      "/manage/floor": [
        ok(
          floorPayload({
            staff: [MANAGER_CARD],
            rooms: [ROOM_ONE],
            waitlist: waitlist([
              waitlistEntry({ id: "qt-1", name: SHIRA, position: 1 }),
              waitlistEntry({ id: "qt-2", name: TAMAR, position: 2 }),
            ]),
          }),
        ),
      ],
      [`${queuePath("qt-1")}/skip`]: [
        ok(
          waitlist([
            waitlistEntry({ id: "qt-2", name: TAMAR, position: 1 }),
            waitlistEntry({ id: "qt-1", name: SHIRA, position: 2, skip_count: 1 }),
          ]),
        ),
      ],
    },
  });

  await gotoBoardFloor(page);

  const target = row(page, "qt-1");
  const control = target.getByRole("button", { name: skipAria(SHIRA) });
  await control.focus();
  await expect(control).toBeFocused();
  await control.click();

  // She is STILL LISTED — a first skip moves her, it does not remove her — and
  // the row now carries the line that says so.
  await expect(row(page, "qt-1").getByText(SKIPPED_ONCE)).toBeVisible();
  await expect(cue(page)).toContainText(SKIPPED_CUE);

  // One tap, no confirm — and the count the screen rendered, sent verbatim.
  const sent = api.of(`${queuePath("qt-1")}/skip`);
  expect(sent).toHaveLength(1);
  expect(sent[0].body).toEqual({ seen_skip_count: 0 });

  // ⚠ THE ASSERTION. Not the moved control, which is now below the fold and
  // would have scrolled the page there with no user action — the repaint F-8
  // exists to prevent. The heading is where a rescue belongs.
  await expect(page.getByRole("heading", { level: 3, name: WAITLIST_HEADING })).toBeFocused();
});

// --- 7. an unstubbed call fails loudly, in Hebrew ---------------------------

test("manage floor: an unstubbed request surfaces as a rendered Hebrew sentence, never a hang", async ({
  page,
}) => {
  // No reply is queued for the call verb, so the harness answers its house
  // 404 — which is the design and not a fallback. Reaching `vite preview`'s
  // proxy instead would be a connection error the test could only read as a
  // flake.
  await installManageApi(page, {
    replies: {
      "/manage/floor": [
        ok(
          floorPayload({
            rooms: [ROOM_ONE],
            waitlist: waitlist([waitlistEntry({ id: "qt-1", name: NOA, position: 1 })]),
          }),
        ),
      ],
    },
  });

  await gotoFloor(page);
  await page.getByRole("button", { name: callAria(NOA) }).click();

  const alert = row(page, "qt-1").getByRole("alert");
  await expect(alert).toHaveText(ROW_GONE_ALERT);
  await expect(alert).toBeFocused();

  // The fixture's `message` is English on purpose, exactly as every backend
  // message is. Painting the server's sentence onto a Hebrew-only console is the
  // failure this pins, and it is invisible to axe and to every layout check.
  const text = await alert.innerText();
  expect(text, "the alert is empty").toMatch(/[֐-׿]/);
  expect(text, "an English server message reached the page").not.toMatch(/[A-Za-z]{4,}/);
});

// --- axe, behind the login screen -------------------------------------------

test("manage floor: zero axe A/AA violations on a populated floor with a reveal and an alert open", async ({
  page,
}) => {
  await installManageApi(page, {
    replies: {
      "/manage/floor": [
        ok(
          floorPayload({
            rooms: [ROOM_ONE, room({ ...ROOM_TWO, assignment: assignment() })],
            waitlist: waitlist(
              [
                waitlistEntry({ id: "qt-1", name: NOA, position: 1 }),
                waitlistEntry({ id: "qt-2", name: SHIRA, position: 2, called: true }),
                waitlistEntry({ id: "qt-3", name: TAMAR, position: 3, duplicate: true, skip_count: 1 }),
              ],
              true,
            ),
          }),
        ),
      ],
      [`${roomPath("rm-1")}/take-next`]: [refuse(409, "QUEUE_EMPTY")],
    },
  });

  await gotoFloor(page);

  // Every state reception can reach at once: a called row, a duplicate row, a
  // once-skipped row, the truncation line, an OPEN assign reveal (its <select>
  // and its two buttons) and an open tile alert.
  //
  // The refusal is opened LAST on purpose: a successful tick clears the tile
  // alert about five seconds later, so the shortest possible window between
  // opening it and running axe is the one that keeps this scan's coverage from
  // quietly shrinking to "the alert was already gone".
  await page.getByRole("button", { name: assignAria(NOA) }).click();
  await expect(row(page, "qt-1").getByRole("button", { name: ASSIGN_CONFIRM })).toBeVisible();
  await page.getByRole("button", { name: takeNextAria("חדר 1") }).click();
  await expect(tile(page, "rm-1").getByRole("alert")).toBeVisible();

  expect(await axeViolations(page)).toEqual([]);
});

test("manage board: zero axe A/AA violations with the remove confirm open", async ({ page }) => {
  // The elevated reveal is the one destructive surface in this feature and no
  // other real-browser pass reaches it: reception has no «הסרה» at all, so the
  // reception scan above cannot open it.
  await installManageApi(page, {
    staff: MANAGER,
    replies: {
      "/manage/floor": [
        ok(
          floorPayload({
            staff: [MANAGER_CARD],
            rooms: [ROOM_ONE],
            waitlist: waitlist([waitlistEntry({ id: "qt-1", name: NOA, duplicate: true })]),
          }),
        ),
      ],
    },
  });

  await gotoBoardFloor(page);
  await page.getByRole("button", { name: removeAria(NOA) }).click();
  await expect(row(page, "qt-1").getByRole("button", { name: CONFIRM_YES })).toBeVisible();

  expect(await axeViolations(page)).toEqual([]);
});

// --- the empty queue, which is most of a boutique's day ---------------------

test("manage floor: an empty queue is a quiet designed state and removes every dispatch control", async ({
  page,
}) => {
  const api = await installManageApi(page, {
    replies: {
      "/manage/floor": [ok(floorPayload({ rooms: [ROOM_ONE], waitlist: waitlist([]) }))],
    },
  });

  await gotoFloor(page);

  await expect(page.getByText(WAITLIST_EMPTY).first()).toBeVisible();
  // §3.1: an empty queue REMOVES the tile's control rather than refusing it —
  // and the claim survives, because the two acts serve two populations.
  await expect(page.getByRole("button", { name: takeNextAria("חדר 1") })).toHaveCount(0);
  await expect(page.getByRole("button", { name: CLAIM })).toBeVisible();
  expect(api.of("/manage/floor").length).toBeGreaterThan(0);
});

// --- axe: the eleven console sections that had no scan at all (B6 · R47) -----
//
// D7 item 2, as amended by plan C3. `guide.ts` declares FIFTEEN `SectionKey`s.
// Four were already scanned in a real browser — `floor` and `board` above,
// `atelier` three times in `atelier-capacity.spec.ts`, and `dashboard` only
// INCIDENTALLY, through `guide.spec.ts:625`, where the scan is taken with a
// `dialog:modal` open over it. A scan of a different DOM is not this section's
// scan, so `dashboard` keeps its own row here.
//
// ⚠ **THE LIMIT IS THE ONE THIS FILE'S BANNER ALREADY STATES AT :31-33, AND
// THESE ELEVEN INHERIT IT EXACTLY: the harness stubs the API, so they prove the
// CONSOLE and not the CONTRACT.** A renamed payload key passes every one of
// them. They are markup and accessibility instruments; `test_*_api.py`'s
// set-equality assertions and the TypeScript types are what hold the wire.
//
// ⚠ **EVERY PAYLOAD IS POPULATED, AND EVERY ROW WAITS ON A TELL THAT ONLY THE
// POPULATED STATE RENDERS.** `Skeleton` is `aria-hidden` with no text and an
// outage is a bare `<p role="alert">` — both are nearly empty, and a scan of
// either would pass while proving nothing about the section. The tell is the
// anti-vacuity leg, and for `staff` it is deliberately the per-row «השבתה —
// {{name}}»: that is the control F61's nameless-button defect lived on, and it
// only exists on a row that is not the signed-in staffer.
//
// ⚠ **NO `.disableRules()` AND NO `.exclude()`, HERE OR ANYWHERE IN THIS
// SUITE.** If one of these reds, the markup is wrong and the component is what
// changes.

const NAV_DASHBOARD = "סקירה";
// --- F27's toggle matrix, verbatim from apps/manage/src/i18n/he.ts -----------
const NAV_PROFILE = "פרופיל והגדרות";
const MATRIX_HEADING = "הפעלת תכונות";
const BRIDES_ONLY_LABEL = "בוטיק לכלות בלבד";
const DEPOSITS_LABEL = "גביית מקדמות מופעלת";
const AREA_STOREFRONT = "האתר הפומבי";
const AREA_BOOKING = "תורים ותשלומים";
const PROFILE_SAVE = "שמירת פרופיל";
const SAVED_CUE = "נשמר לפני רגע";
// F-W1's floor. `Button size="sm"` is 36px and fails it — the matrix rows are
// measured against this number rather than eyeballed (F-T2).
const TOUCH_TARGET_MIN = 44;

// The three owner-only rows — `staff`, `gateway`, `privacy` — are unreachable
// as anyone else, and the other eight are `roles: ALL`, so one identity drives
// all eleven.
const OWNER = staff({ role: "owner", display_name: "רונית" });

const AXE_SECTIONS: [
  label: string,
  nav: string,
  replies: Record<string, Reply[]>,
  settled: (page: Page) => Locator,
][] = [
  [
    "dashboard",
    NAV_DASHBOARD,
    { "/manage/dashboard": [ok(dashboardPopulated())] },
    // The <th scope="row"> in the appointment-types card, which exists only when
    // that list is non-empty. The section heading and the role="status" summary
    // line render in the zero state too.
    (page) => page.getByRole("rowheader", { name: "מדידה ראשונה" }),
  ],
  [
    "profile",
    "פרופיל והגדרות",
    { "/manage/settings": [ok(settingsPayload())] },
    // ⚠ A SWITCH IN THE MATRIX CARD, NOT THE PROFILE FORM'S «משפט פתיחה» TEXTBOX
    // — which is what this settled on before F27, and which renders BEFORE the
    // matrix. The axe sweep is the IS 5568 / WCAG 2.0 AA legal floor for this
    // section, so a settle that fires while the card is still absent makes the
    // zero-violation claim vacuous for every control F27 added (plan R-D).
    (page) => page.getByRole("switch", { name: BRIDES_ONLY_LABEL }),
  ],
  [
    "hours",
    "שעות פעילות",
    { "/manage/availability": [ok(availabilityPayload())] },
    // The weekly-rule <Select> — the section's only combobox, and it renders per
    // rule row, so an empty `rules` array cannot satisfy it.
    (page) => page.getByRole("combobox", { name: "יום" }),
  ],
  [
    "types",
    "סוגי תורים",
    { "/manage/appointment-types": [ok(appointmentTypes())] },
    (page) => page.getByRole("button", { name: "עריכה" }),
  ],
  [
    "terms",
    "מדיניות ביטולים",
    { "/manage/terms": [ok(termsHistory())] },
    // NOT the create form: an owner gets that with any payload, including the
    // empty one that renders the setup-blocker panel instead of the history.
    (page) => page.getByRole("heading", { name: "היסטוריית גרסאות (לקריאה בלבד)" }),
  ],
  [
    "catalog",
    "שמלות",
    { "/manage/dresses": [ok(dressList())] },
    (page) => page.getByRole("button", { name: /שמלת נסיכה/ }),
  ],
  [
    "bookings",
    "תורים",
    { "/manage/bookings": [ok(bookingList())] },
    (page) => page.getByRole("button", { name: /נועה כהן/ }),
  ],
  [
    "customers",
    "לקוחות",
    { "/manage/customers": [ok(customerList())] },
    (page) => page.getByRole("button", { name: /מיכל לוי/ }),
  ],
  [
    "staff",
    "צוות",
    { "/manage/staff": [ok(staffList())] },
    // F61's control, by name. `דנה כהן` is the non-self row.
    //
    // ⚠ «סיום העסקה» AND NOT «השבתה». F38 changed the VALUE of
    // `staff.deactivateAria` (design §copy 3 — «השבתה» understated an act that
    // now sets a last working day and deletes her photo) and left this settle
    // tell reading the old string, so this row had been failing since that
    // commit. The tell is the anti-vacuity leg of the whole sweep, so it can
    // never be softened to a role-only match.
    (page) => page.getByRole("button", { name: "סיום העסקה — דנה כהן" }),
  ],
  [
    "gateway",
    "סליקה ותשלומים",
    // BOTH, and settings is not optional: the section loads them in one
    // `Promise.all` inside one `try`, so a house 404 on settings rejects the
    // pair and renders the outage line with no gateway markup at all.
    {
      "/manage/gateway": [ok(gatewayStatus())],
      "/manage/settings": [ok(settingsPayload())],
    },
    (page) => page.getByRole("button", { name: "בדיקה עכשיו" }),
  ],
  [
    "privacy",
    "פרטיות",
    { "/manage/privacy": [ok(privacyPayload())] },
    (page) => page.getByRole("heading", { name: "ספקי התשתית" }),
  ],
];

for (const [label, nav, replies, settled] of AXE_SECTIONS) {
  test(`manage ${label}: zero axe A/AA violations on a populated section`, async ({ page }) => {
    await installManageApi(page, { staff: OWNER, replies });
    await page.goto(MANAGE);
    // The console lands on `dashboard` for both elevated roles, so the nav is
    // only clickable once that first section has rendered.
    await expect(page.getByRole("heading", { level: 2, name: NAV_DASHBOARD })).toBeVisible();
    // `exact` because «תורים» is a substring of «סוגי תורים» and the default
    // accessible-name match is a substring match — without it the bookings row
    // matches two nav buttons and reds on strict mode rather than on anything
    // this test is about.
    await page.getByRole("navigation").getByRole("button", { name: nav, exact: true }).click();

    await expect(settled(page), `${label} never reached its populated state`).toBeVisible();

    expect(await axeViolations(page)).toEqual([]);
  });
}


// --- F27: the feature-toggle matrix ------------------------------------------
//
// ⚠ THESE ARE HERE RATHER THAN IN VITEST BECAUSE jsdom IS NOT A BROWSER, and
// this feature has two claims that only a real one can settle: where focus LANDS
// after a flip (design P1's whole argument — jsdom never blurs anything, which
// is how F57 shipped a focus test that asserted nothing), and the RENDERED hit
// box of a row (F-T2 — the checkbox is 20px and the label is the target).

async function openProfile(page: Page): Promise<void> {
  await page.goto(MANAGE);
  await expect(page.getByRole("heading", { level: 2, name: NAV_DASHBOARD })).toBeVisible();
  await page.getByRole("navigation").getByRole("button", { name: NAV_PROFILE, exact: true }).click();
  await expect(page.getByRole("heading", { name: MATRIX_HEADING })).toBeVisible();
}

test("manage profile: the matrix renders one grouped row per wire toggle", async ({ page }) => {
  await installManageApi(page, {
    staff: OWNER,
    replies: { "/manage/settings": [ok(settingsPayload())] },
  });
  await openProfile(page);

  // One row per key in `settingsPayload().toggles` — the fixture IS the backend
  // registry, so this count is the cross-tree drift assertion.
  await expect(page.getByRole("switch")).toHaveCount(2);
  await expect(page.getByRole("heading", { level: 3, name: AREA_STOREFRONT })).toBeVisible();
  await expect(page.getByRole("heading", { level: 3, name: AREA_BOOKING })).toBeVisible();
  // Wire truth, not defaults: the fixture ships deposits ON and brides OFF.
  await expect(page.getByRole("switch", { name: DEPOSITS_LABEL })).toBeChecked();
  await expect(page.getByRole("switch", { name: BRIDES_ONLY_LABEL })).not.toBeChecked();
});

test("manage profile: a row flip PUTs exactly one key and reflects the response", async ({
  page,
}) => {
  const recorder = await installManageApi(page, {
    staff: OWNER,
    replies: {
      "GET /manage/settings": [ok(settingsPayload())],
      "PUT /manage/settings": [ok(settingsAfterToggle("brides_only", true))],
    },
  });
  await openProfile(page);

  const brides = page.getByRole("switch", { name: BRIDES_ONLY_LABEL });
  await brides.click();

  await expect(brides).toBeChecked();
  const puts = recorder.of("/manage/settings").filter((entry) => entry.method === "PUT");
  expect(puts).toHaveLength(1);
  // ⚠ EXACTLY ONE KEY. Sending the sibling too would pass today and would
  // re-create the stale-bundle clobber D2 exists to abolish the moment the
  // registry grows.
  expect(puts[0].body).toEqual({ toggles: { brides_only: true } });
});

test("manage profile: a failed flip reverts the switch and shows the house toast", async ({
  page,
}) => {
  await installManageApi(page, {
    staff: OWNER,
    replies: {
      "GET /manage/settings": [ok(settingsPayload())],
      "PUT /manage/settings": [refuse(500, "INTERNAL_ERROR")],
    },
  });
  await openProfile(page);

  const deposits = page.getByRole("switch", { name: DEPOSITS_LABEL });
  await expect(deposits).toBeChecked();
  await deposits.click();

  // The fixture's message is ENGLISH by its own design (every backend message
  // is), and the matrix has no per-code Hebrew — so `errorMessage()` paints the
  // server's sentence. What this pins is that the toast FIRED, in the house
  // alert role, and that the revert below happened alongside it.
  await expect(page.getByRole("alert")).toContainText("INTERNAL_ERROR");
  // Back to its PRE-FLIP state, not to false — no optimistic UI survives a
  // failure (design §4 state E).
  await expect(deposits).toBeChecked();
});

test("manage profile: focus stays on the flipped switch through in-flight and saved", async ({
  page,
}) => {
  // ⚠ DESIGN P1, MEASURED IN CHROMIUM. This is the assertion the whole
  // handler-guard-instead-of-`disabled` decision exists for: disabling a focused
  // native checkbox drops focus to <body>, an SC 2.4.3 regression. jsdom cannot
  // see it (it never blurs), so this test is the claim's only real proof.
  await installManageApi(page, {
    staff: OWNER,
    replies: {
      "GET /manage/settings": [ok(settingsPayload())],
      "PUT /manage/settings": [ok(settingsAfterToggle("brides_only", true))],
    },
  });
  await openProfile(page);

  const brides = page.getByRole("switch", { name: BRIDES_ONLY_LABEL });
  await brides.focus();
  await page.keyboard.press("Space");

  await expect(brides).toBeFocused();
  await expect(brides).toBeChecked();
  await expect(brides).toBeFocused();
  await expect(brides).toBeEnabled();
});

test("manage profile: a row flip does NOT light the profile form's saved cue", async ({ page }) => {
  // F-T1. Two save models on one screen share one Hebrew string, so the only
  // thing keeping them apart is that they are separate state. A row cue that
  // also lit the form's would tell the owner her unsaved profile edits were
  // saved.
  await installManageApi(page, {
    staff: OWNER,
    replies: {
      "GET /manage/settings": [ok(settingsPayload())],
      "PUT /manage/settings": [ok(settingsAfterToggle("brides_only", true))],
    },
  });
  await openProfile(page);

  await page.getByRole("switch", { name: BRIDES_ONLY_LABEL }).click();
  await expect(page.getByRole("switch", { name: BRIDES_ONLY_LABEL })).toBeChecked();

  // The cue that DID appear belongs to the matrix card; the form's save button
  // has none beside it.
  const form = page.locator("form").filter({ has: page.getByRole("button", { name: PROFILE_SAVE }) });
  await expect(form.getByText(SAVED_CUE)).toHaveCount(0);
});

test("manage profile: every matrix row meets the 44px touch floor", async ({ page }) => {
  // F-T2, MEASURED not eyeballed: the `Toggle`'s checkbox box is `size-5` (20px)
  // and is NOT the hit target — the wrapping <label> is, which is why `Toggle`
  // takes a className that lands there.
  await installManageApi(page, {
    staff: OWNER,
    replies: { "/manage/settings": [ok(settingsPayload())] },
  });
  await openProfile(page);

  for (const label of [BRIDES_ONLY_LABEL, DEPOSITS_LABEL]) {
    const row = page.getByRole("switch", { name: label }).locator("xpath=ancestor::label[1]");
    const box = await row.boundingBox();
    expect(box, `${label} row has no box`).not.toBeNull();
    expect(box!.height, `${label} row is under the touch floor`).toBeGreaterThanOrEqual(
      TOUCH_TARGET_MIN,
    );
  }
});

test("manage profile: switching deposits on with no gateway adds no new warning", async ({
  page,
}) => {
  // F-T3. Preparing before connecting a gateway is legal and useful. The row's
  // own hint plus the shipped GatewaySection banner already cover it; the matrix
  // must not block, confirm, or nag beyond the hint.
  await installManageApi(page, {
    staff: OWNER,
    replies: {
      "GET /manage/settings": [ok(settingsAfterToggle("deposits_enabled", false))],
      "PUT /manage/settings": [ok(settingsAfterToggle("deposits_enabled", true))],
    },
  });
  await openProfile(page);

  const deposits = page.getByRole("switch", { name: DEPOSITS_LABEL });
  await expect(deposits).not.toBeChecked();
  await deposits.click();
  await expect(deposits).toBeChecked();

  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("manage profile: the matrix lays out RTL — switch inline-start, cue inline-end", async ({
  page,
}) => {
  await installManageApi(page, {
    staff: OWNER,
    replies: {
      "GET /manage/settings": [ok(settingsPayload())],
      "PUT /manage/settings": [ok(settingsAfterToggle("brides_only", true))],
    },
  });
  await openProfile(page);

  const brides = page.getByRole("switch", { name: BRIDES_ONLY_LABEL });
  await brides.click();

  // ⚠ «נשמר לפני רגע» appears TWICE by design — the row cue and the card's
  // VisuallyHidden role="status" region (design P3 reuses one string for both).
  // NEITHER `.first()` NOR `visible=true` disambiguates them: `.first()` is a
  // coin flip on DOM order, and Playwright counts sr-only content as VISIBLE
  // because clip-based hiding still leaves a bounding box — which is why
  // `visible=true` resolved to both and tripped strict mode.
  // Scoping to the row that owns this switch is what actually separates them,
  // and it is also the box this test means to measure.
  const row = page.locator("section").filter({ has: brides });
  const cue = row.getByText(SAVED_CUE);
  await expect(cue).toBeVisible();
  const switchBox = await brides.boundingBox();
  const cueBox = await cue.boundingBox();
  expect(switchBox).not.toBeNull();
  expect(cueBox).not.toBeNull();
  // RTL: inline-start is the RIGHT edge, so the switch sits to the RIGHT of the
  // cue. Asserting the pair rather than a class keeps this true if the layout
  // changes but the reading order does not.
  expect(switchBox!.x).toBeGreaterThan(cueBox!.x);
});

// --- F38: the HR directory's staff journeys ----------------------------------
//
// ⚠ **EVERY TEST BELOW EXISTS BECAUSE jsdom CANNOT ANSWER IT.**
// `StaffSection.test.tsx` already pins each branch these journeys walk — the
// presign→POST→confirm sequence, the failed-replace alert, the send-only-what-
// moved patch, the last-day default. What it structurally cannot reach, and
// what each block here measures instead:
//
//   1. `<dialog>`. jsdom has none — `setup.ts` stubs `showModal()` — so Esc,
//      the focus trap and the focus RETURN to the row control that opened it
//      are unobservable there (`.memory/jsdom-has-no-dialog`).
//   2. A RENDERED BOX. `Button size="sm"` is `min-h-9` (36px) and fails the
//      44px floor; `md` is `min-h-11`. jsdom applies no stylesheet, so every
//      height there is 0 and an `sm` slipped into this section would pass the
//      whole unit suite.
//   3. A DECODED IMAGE. jsdom loads no images, so `naturalWidth` is always 0
//      and «the face actually paints» is not a claim it can make.
//   4. A REAL FILE INPUT and a real multipart POST straight at storage — the
//      one call in this feature that never touches the API.
//
// ⚠ **Risk 6 again: the harness stubs the API, so these prove the CONSOLE and
// not the CONTRACT.** `test_staff_api.py`'s set-equality assertions hold the
// wire. The axe half of H1 lives in `a11y.spec.ts`, where design.md §a11y puts
// it and where `color-contrast` — skipped entirely by axe under jsdom — is a
// measurement a real browser can take.

// --- copy, verbatim from apps/manage/src/i18n/he.ts --------------------------

const NAV_STAFF = "צוות";
const STAFF_HEADING = "צוות";
const PHOTO_UPLOAD_LABEL = "תמונת פרופיל";
const PHOTO_REPLACE_LABEL = "החלפת תמונת פרופיל";
const PHOTO_ADDED = "התמונה נוספה.";
const PHOTO_REMOVE_CTA = "הסרת תמונה";
const PHOTO_RETRY_CTA = "נסי שוב";
const MEDIA_MISMATCH = "הקובץ אינו תמונה תקינה.";
const ELIGIBLE_LABEL = "יכולה לנהל משמרת";
const STAFF_SAVE = "שמירה";
const STAFF_CANCEL = "ביטול";
const OFFBOARD_TITLE = "לסיים את ההעסקה?";
const OFFBOARD_CONFIRM = "סיום העסקה";
const LAST_DAY_LABEL = "יום עבודה אחרון";
const OFFBOARD_RETENTION_NOTE =
  "רישומי העבודה שלה — שיבוצים לחדרים, קריאות ותיקונים — נשמרים כפי שהם. " +
  "הפרטים האישיים שלה יימחקו מהמערכת בתום תקופת השמירה. " +
  "אפשר להוסיף אותה מחדש בעתיד כאשת צוות חדשה.";

const editAria = (name: string) => `עריכה — ${name}`;
const offboardAria = (name: string) => `סיום העסקה — ${name}`;
const offboardDone = (name: string, date: string) =>
  `ההעסקה של ${name} הסתיימה בתאריך ${date}. רישומי העבודה שלה נשמרו.`;

// --- fixture data ------------------------------------------------------------

// `staffList()` ships two rows and the split is load-bearing: רונית IS the
// signed-in owner (SELF_ID) and carries a photo, so she is the only row with a
// replace-and-remove control; דנה is the non-self row, so she is the only one
// with an offboard control at all — and she carries no photo, which is the
// upload-from-empty path.
const [, DANA_ROW] = staffList() as Record<string, unknown>[];
const RONIT = "רונית";
const DANA = "דנה כהן";
const DANA_ID = "st-2";

// ⚠ 2048 bytes and not a token buffer: `validateStaffPhotoFile` refuses
// anything under MIN_UPLOAD_BYTES (1024) client-side, with no request at all,
// so a tiny file would fail these tests as a rendered Hebrew rejection that
// reads like a broken harness.
const PHOTO_FILE = {
  name: "photo.png",
  mimeType: "image/png",
  buffer: Buffer.alloc(2048, 7),
};

// The same Jerusalem calendar day `lib/jerusalem.ts`'s todayJerusalem() builds,
// spelled the same way (en-CA is the ISO spelling) — so this is the default the
// offboard dialog is expected to pre-fill, not a restatement of the device clock.
const JERUSALEM_TODAY = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Asia/Jerusalem",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
}).format(new Date());
// plainDate()'s d.m.yyyy, unpadded — the spelling the status line renders.
const JERUSALEM_TODAY_HUMAN = (() => {
  const [year, month, day] = JERUSALEM_TODAY.split("-");
  return `${Number(day)}.${Number(month)}.${year}`;
})();

// --- helpers -----------------------------------------------------------------

async function openStaff(page: Page): Promise<void> {
  await page.goto(MANAGE);
  await expect(page.getByRole("heading", { level: 2, name: NAV_DASHBOARD })).toBeVisible();
  await page.getByRole("navigation").getByRole("button", { name: NAV_STAFF, exact: true }).click();
  // The settle tell is the per-row offboard control, which only a POPULATED list
  // renders and only on a row that is not the signed-in staffer. The h2 renders
  // over the skeleton while the first fetch is in flight, so waiting on it would
  // wait for nothing.
  await expect(page.getByRole("button", { name: offboardAria(DANA) })).toBeVisible();
}

// ⚠ SCOPED TO <main>, never a bare `getByRole("status")`. GuideOverlay ships an
// sr-only live region of its own inside a `<dialog>` mounted on every console
// screen, and `visible=true` does NOT separate the two — Playwright counts
// sr-only content as visible because clip-based hiding still leaves a box.
// `.first()` would be a coin flip on DOM order. The shell renders the guide in
// its header and the section inside <main>, so the landmark is what actually
// disambiguates them.
function staffStatus(page: Page): Locator {
  return page.getByRole("main").getByRole("status");
}

function staffRow(page: Page, name: string): Locator {
  return page.getByRole("main").getByRole("listitem").filter({ hasText: name });
}

// The open edit panel — identified by the one control only it can contain. Its
// name inputs hold their values as PROPERTIES, so `hasText` cannot find it.
function editPanel(page: Page): Locator {
  return page
    .getByRole("main")
    .getByRole("listitem")
    .filter({ has: page.locator('input[type="file"]') });
}

async function assertTouchFloor(target: Locator, label: string): Promise<void> {
  // ⚠ SETTLE FIRST. `boundingBox()` returns the VISUAL box, transforms included,
  // and `Modal` scales its panel 0.97 → 1 on open — so the two footer buttons
  // measure 42.68px (44 × 0.97) for the length of that animation. Measuring
  // there fails on motion rather than on a defect, and "relax the floor to 42"
  // is the wrong reading of it.
  await settleAnimations(target.page());
  const box = await target.boundingBox();
  expect(box, `${label} has no box`).not.toBeNull();
  expect(box!.height, `${label} is under the ${String(TOUCH_TARGET_MIN)}px touch floor`).toBeGreaterThanOrEqual(
    TOUCH_TARGET_MIN,
  );
}

// --- 1. the photo, end to end ------------------------------------------------

test("manage staff: a photo upload runs presign → storage → confirm and paints a real face", async ({
  page,
}) => {
  const confirmed = {
    ...DANA_ROW,
    photo_url: PHOTO_DATA_URI,
    photo_confirmed_at: PHOTO_CONFIRMED_AT,
  };
  const api = await installManageApi(page, {
    staff: OWNER,
    replies: {
      "/manage/staff": [ok(staffList())],
      [`${staffPath(DANA_ID)}/photo/presign`]: [ok(staffPresign())],
      [`${staffPath(DANA_ID)}/photo/confirm`]: [ok(confirmed)],
    },
  });
  const storage = await installStorageUpload(page);

  await openStaff(page);
  await page.getByRole("button", { name: editAria(DANA) }).click();

  // ⚠ A REAL, VISIBLE, FOCUSABLE `<input type="file">` — design §1's first rule,
  // and the one jsdom cannot settle: visibility there is a string on a style
  // object rather than a rendered box, and `display:none` plus a label shim
  // (which breaks Safari/VoiceOver) reads identically to this in that suite.
  const picker = page.getByLabel(PHOTO_UPLOAD_LABEL);
  await expect(picker).toBeVisible();
  await expect(picker).toBeEnabled();
  await picker.focus();
  await expect(picker).toBeFocused();

  await picker.setInputFiles(PHOTO_FILE);

  // The terminal state lands on the SAME region the running ones used, which is
  // why a failure after «מאמת…» can never be left silent.
  await expect(staffStatus(page)).toHaveText(PHOTO_ADDED);
  // The control relabels and the remove control appears — both keyed off
  // `photo_url`, so both prove the row was patched from the confirm RESPONSE.
  await expect(page.getByLabel(PHOTO_REPLACE_LABEL)).toBeVisible();
  await expect(page.getByRole("button", { name: PHOTO_REMOVE_CTA })).toBeVisible();

  const presigned = api.of(`${staffPath(DANA_ID)}/photo/presign`);
  expect(presigned).toHaveLength(1);
  expect(presigned[0].body).toEqual({
    content_type: PHOTO_FILE.mimeType,
    byte_size: PHOTO_FILE.buffer.length,
  });
  // The middle call is not optional and the recorder cannot see it — it goes
  // straight at storage, past the API interceptor entirely.
  expect(storage.count, "the file never reached storage").toBe(1);
  expect(api.of(`${staffPath(DANA_ID)}/photo/confirm`)).toHaveLength(1);

  await editPanel(page).getByRole("button", { name: STAFF_CANCEL }).click();

  // ⚠ THE IMAGE ACTUALLY DECODED. jsdom fetches nothing, so `naturalWidth` is 0
  // there for a correct <img> and a broken one alike — this is the only place a
  // srcless or unreadable avatar is a failing test rather than a passing one.
  const face = staffRow(page, DANA).locator("img");
  await expect(face).toHaveAttribute("alt", "");
  expect(await face.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBeGreaterThan(0);
});

test("manage staff: a failed confirm keeps the previous photo on screen and offers a retry", async ({
  page,
}) => {
  await installManageApi(page, {
    staff: OWNER,
    replies: {
      "/manage/staff": [ok(staffList())],
      [`${staffPath(SELF_ID)}/photo/presign`]: [ok(staffPresign())],
      [`${staffPath(SELF_ID)}/photo/confirm`]: [refuse(400, "MEDIA_MISMATCH")],
    },
  });
  const storage = await installStorageUpload(page);

  await openStaff(page);
  await page.getByRole("button", { name: editAria(RONIT) }).click();
  await page.getByLabel(PHOTO_REPLACE_LABEL).setInputFiles(PHOTO_FILE);

  const alert = editPanel(page).getByRole("alert");
  await expect(alert).toHaveText(MEDIA_MISMATCH);
  // The fixture's message is ENGLISH on purpose, exactly as every backend
  // message is. Painting the server's sentence onto a Hebrew-only console is
  // the failure this pins, and it is invisible to axe.
  const text = await alert.innerText();
  expect(text, "the alert is empty").toMatch(/[֐-׿]/);
  expect(text, "an English server message reached the page").not.toMatch(/[A-Za-z]{4,}/);

  // ⚠ THE PREVIOUS PHOTO IS STILL SHOWN. Nothing in the failed run touched the
  // live triple, which is the whole reason the pending/live column pair exists —
  // a failed replace must never blank the cell.
  await expect(editPanel(page).locator("img")).toHaveAttribute("src", PHOTO_DATA_URI);
  await expect(page.getByRole("button", { name: PHOTO_RETRY_CTA })).toBeVisible();
  // …and the region is EMPTY rather than still reading «מאמת…», so no terminal
  // failure is left standing under a stale progress message.
  await expect(staffStatus(page)).toBeEmpty();

  expect(storage.count, "the upload itself is not what failed here").toBe(1);
});

// --- 2. eligibility ----------------------------------------------------------

test("manage staff: unchecking eligibility patches that field alone, on a 44px row", async ({
  page,
}) => {
  const api = await installManageApi(page, {
    staff: OWNER,
    replies: {
      "/manage/staff": [ok(staffList())],
      [`PATCH ${staffPath(DANA_ID)}`]: [ok({ ...DANA_ROW, shift_manager_eligible: false })],
    },
  });

  await openStaff(page);
  // MUTED WORDS on the row, never a second Badge — the row already carries the
  // role pill and F36's ruling is one pill per row.
  await expect(staffRow(page, DANA).getByText(ELIGIBLE_LABEL)).toBeVisible();

  await page.getByRole("button", { name: editAria(DANA) }).click();
  // ⚠ SCOPED TO THE PANEL. The create form carries a second Checkbox with the
  // SAME label — design R1 puts the three HR fields on both — so a bare
  // `getByRole("checkbox", { name })` resolves to two elements and trips strict
  // mode. `.first()` would be a coin flip on DOM order rather than a fix.
  const eligible = editPanel(page).getByRole("checkbox", { name: ELIGIBLE_LABEL });
  await expect(eligible).toBeChecked();

  // ⚠ MEASURED HERE AND NOT IN VITEST: `Checkbox`'s box is `size-6` (24px) and
  // is NOT the hit target — the wrapping <label> is, at `min-h-11`. jsdom
  // applies no stylesheet, so that height is 0 there for a compliant row and a
  // broken one alike.
  await assertTouchFloor(eligible.locator("xpath=ancestor::label[1]"), "the eligibility row");

  await eligible.click();
  await expect(eligible).not.toBeChecked();
  await editPanel(page).getByRole("button", { name: STAFF_SAVE }).click();

  const patched = api.of(staffPath(DANA_ID)).filter((entry) => entry.method === "PATCH");
  expect(patched).toHaveLength(1);
  // ⚠ EXACTLY ONE KEY. F51's send-only-what-moved rule is not an optimisation —
  // each field earns its own audit row, so a patch carrying the untouched name
  // and role would write three where the owner changed one.
  expect(patched[0].body).toEqual({ shift_manager_eligible: false });

  // The editor closed and the word is gone from her row.
  await expect(staffRow(page, DANA).getByText(ELIGIBLE_LABEL)).toHaveCount(0);
});

// --- 3. offboarding, in a real <dialog> --------------------------------------

test("manage staff: the offboard dialog defaults to today-Jerusalem, returns focus on Esc, then sends the date", async ({
  page,
}) => {
  const api = await installManageApi(page, {
    staff: OWNER,
    replies: {
      "/manage/staff": [ok(staffList())],
      [`DELETE ${staffPath(DANA_ID)}`]: [ok({ ok: true })],
    },
  });

  await openStaff(page);
  const trigger = page.getByRole("button", { name: offboardAria(DANA) });
  await assertTouchFloor(trigger, "the offboard row control");
  await trigger.click();

  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("heading", { name: OFFBOARD_TITLE })).toBeVisible();
  // <Trans> puts her name inside a bare <bdi> — a Latin display name reorders
  // inside a Hebrew sentence without an isolate, and every founding owner is
  // seeded with display_name = owner_email.
  await expect(dialog.locator("bdi")).toHaveText(DANA);
  await expect(dialog.getByText(OFFBOARD_RETENTION_NOTE)).toBeVisible();

  // ⚠ PRE-FILLED WITH TODAY, and a blank would silently exempt her from the
  // retention clock: the policy's predicate needs `last_day IS NOT NULL`.
  const lastDay = dialog.getByLabel(LAST_DAY_LABEL);
  await expect(lastDay).toHaveValue(JERUSALEM_TODAY);

  // ⚠ THE ASSERTION jsdom STRUCTURALLY CANNOT MAKE. `setup.ts` stubs
  // showModal(), so there is no top layer, no focus trap and no native focus
  // return there — Esc dismissing without acting, and focus landing back on the
  // row control that opened it, are only real in Chromium.
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(trigger).toBeFocused();
  expect(api.of(staffPath(DANA_ID)), "Esc sent something").toHaveLength(0);

  await trigger.click();
  await assertTouchFloor(dialog.getByRole("button", { name: OFFBOARD_CONFIRM }), "the offboard confirm");
  await assertTouchFloor(dialog.getByRole("button", { name: STAFF_CANCEL }), "the offboard cancel");
  await dialog.getByRole("button", { name: OFFBOARD_CONFIRM }).click();

  await expect(staffRow(page, DANA)).toHaveCount(0);
  const sent = api.of(staffPath(DANA_ID));
  expect(sent).toHaveLength(1);
  expect(sent[0].method).toBe("DELETE");
  expect(sent[0].query).toBe(`?last_day=${JERUSALEM_TODAY}`);

  // The row is gone from the list, so this line is the ONLY feedback there is —
  // which is exactly why it names her AND the date.
  await expect(staffStatus(page)).toHaveText(offboardDone(DANA, JERUSALEM_TODAY_HUMAN));
  await expect(staffStatus(page).locator("bdi")).toHaveText(DANA);

  // Her trigger unmounted under the open dialog, so the native focus return
  // lands on <body>; the section's fallback is its own heading.
  await expect(page.getByRole("heading", { level: 2, name: STAFF_HEADING })).toBeFocused();
});

// --- 4. the rest of the section's touch targets ------------------------------

test("manage staff: the photo controls and the editor's own pair clear the 44px floor", async ({
  page,
}) => {
  // F-W1, MEASURED not eyeballed. `size="sm"` is `min-h-9` (36px) and reads as
  // harmless in a diff; the whole unit suite would stay green under it.
  await installManageApi(page, {
    staff: OWNER,
    replies: { "/manage/staff": [ok(staffList())] },
  });

  await openStaff(page);
  await assertTouchFloor(page.getByRole("button", { name: editAria(RONIT) }), "the edit row control");

  await page.getByRole("button", { name: editAria(RONIT) }).click();
  const panel = editPanel(page);
  await assertTouchFloor(panel.getByRole("button", { name: PHOTO_REMOVE_CTA }), PHOTO_REMOVE_CTA);
  await assertTouchFloor(panel.getByRole("button", { name: STAFF_SAVE }), STAFF_SAVE);
  await assertTouchFloor(panel.getByRole("button", { name: STAFF_CANCEL }), STAFF_CANCEL);
});

// --- 5. the board's faces ----------------------------------------------------

test("manage board: a staff card paints a decoded 44px face beside an initial fallback", async ({
  page,
}) => {
  // Two cards, one of each branch. `photo_url === null` is how BOTH renderers
  // choose the fallback, and `undefined === null` is false — which is why the
  // harness sends the field rather than omitting it.
  await installManageApi(page, {
    staff: OWNER,
    replies: {
      "/manage/floor": [
        ok(
          floorPayload({
            staff: [
              staffCard({
                id: "st-1",
                display_name: RONIT,
                photo_url: PHOTO_DATA_URI,
                photo_confirmed_at: PHOTO_CONFIRMED_AT,
              }),
              staffCard({ id: "st-2", display_name: DANA }),
            ],
            rooms: [ROOM_ONE],
          }),
        ),
      ],
    },
  });

  await gotoBoardFloor(page);

  const face = page.locator('[data-staff-id="st-1"]').locator("img");
  // ⚠ alt="" DELIBERATELY. The display name is a text node immediately beside
  // it, so `alt="תמונה של {{name}}"` would announce her name twice per card on
  // a board that lists the whole shift. The photo is decorative by definition.
  await expect(face).toHaveAttribute("alt", "");
  await expect(face).toHaveAttribute("loading", "lazy");
  expect(await face.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBeGreaterThan(0);
  const faceBox = await face.boundingBox();
  expect(faceBox).not.toBeNull();
  expect(faceBox!.width).toBe(TOUCH_TARGET_MIN);
  expect(faceBox!.height).toBe(TOUCH_TARGET_MIN);

  // The fallback: the first GRAPHEME, aria-hidden, holding the same box so a
  // mixed board does not jitter between rows.
  const fallback = page.locator('[data-staff-id="st-2"] span[aria-hidden="true"]').first();
  await expect(fallback).toHaveText("ד");
  const fallbackBox = await fallback.boundingBox();
  expect(fallbackBox).not.toBeNull();
  expect(fallbackBox!.width).toBe(TOUCH_TARGET_MIN);
  expect(fallbackBox!.height).toBe(TOUCH_TARGET_MIN);
});
