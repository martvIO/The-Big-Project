import { test, expect } from "@playwright/test";
import type { Locator, Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import {
  MANAGE,
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
  ok,
  privacyPayload,
  queuePath,
  refuse,
  room,
  roomPath,
  settingsPayload,
  staff,
  staffCard,
  staffList,
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
    (page) => page.getByRole("textbox", { name: "משפט פתיחה" }),
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
    (page) => page.getByRole("button", { name: "השבתה — דנה כהן" }),
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
