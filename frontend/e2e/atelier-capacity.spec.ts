import { test, expect } from "@playwright/test";
import type { Locator, Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import {
  MANAGE,
  atelierBoard,
  atelierSeamstress,
  atelierTicket,
  capacityPath,
  installManageApi,
  ok,
  refuse,
  staff,
} from "./fixtures/manage";
import type { Reply } from "./fixtures/manage";

// F42's journeys, in a real browser, on F58's `/manage/**` interception
// harness — the first feature to use it, which the plan's Risk 11 names as the
// trigger.
//
// ⚠ **These exist BECAUSE jsdom is not a browser, and three of this feature's
// claims are unprovable there.** jsdom has no layout engine, so every 44 px and
// every bar width in the unit suite is a CLASS assertion and never a
// measurement; jsdom does not blur a `disabled` control, which is exactly how
// this repo shipped a vacuous focus test once; and jsdom's `<dialog>` is a
// simulation of a top-layer element rather than one. The bar's fill EDGE under
// `dir="rtl"` is the sharpest of them: `inlineSize` and `width` both render in
// jsdom and only one of them is right.
//
// ⚠ **Risk 6, restated: the harness stubs the API, so this proves the CONSOLE
// and not the CONTRACT.** A renamed payload key passes every test in this file.

// --- copy, verbatim from apps/manage/src/i18n/he.ts --------------------------

const NAV_ATELIER = "תפירה";
const DASHBOARD_HEADING = "סקירה";
const PANEL_HEADING = "תופרות";
const CAPACITY_TITLE = "שעות שבועיות";
const SETTINGS_TITLE = "הגדרות התפירה";
const SETTINGS_OPEN = "הגדרות — לוח התפירה";
const SAVE = "שמירה";
const CANCEL = "ביטול";
const USE_DEFAULT = "חזרה לברירת המחדל";
const HOURS_LABEL = "שעות בשבוע";
const OVER = "עומס יתר";
const NOT_SET = "לא הוגדרה קיבולת";
const FROM_DEFAULT = "ברירת מחדל של הבוטיק";
const NO_SEAMSTRESSES_OWNER = "אין תופרות רשומות. אפשר להוסיף במסך הצוות.";
const CAPACITY_ERROR = "לא ניתן לשמור את השעות. אפשר לנסות שוב.";
const ACCESS_ENDED = "אין הרשאה לצפות בלוח התפירה כרגע. לבירור אפשר לפנות לבעלת הבוטיק.";

const hoursAria = (name: string) => `שעות — ${name}`;

// --- fixture people ----------------------------------------------------------

const OWNER = staff({ id: "st-owner", display_name: "אורית", role: "owner" });

const DANA = "sm-dana";
const RUTI = "sm-ruti";
const NOA = "sm-noa";

// 12 h = 720 min, and every load below is measured against it.
//   דנה  — 1 h of 12, real headroom          → group 1
//   רותי — no capacity, 4 h held             → group 2
//   נועה — 15 h of 12, over                  → group 3
// Handed to the console in the SERVER's `display_name, id` order, so a missing
// client sort renders THIS order and the first assertion reds.
function roster() {
  return [
    atelierSeamstress({
      id: NOA,
      display_name: "נועה",
      weekly_capacity_hours: 12,
      due_soon_minutes: 900,
      assigned_minutes: 2760,
    }),
    atelierSeamstress({
      id: DANA,
      display_name: "דנה",
      weekly_capacity_hours: 12,
      capacity_is_default: true,
      due_soon_minutes: 60,
      assigned_minutes: 60,
    }),
    atelierSeamstress({ id: RUTI, display_name: "רותי", assigned_minutes: 240 }),
  ];
}

function loadedBoard(overrides: Record<string, unknown> = {}) {
  return atelierBoard({
    tickets: [atelierTicket()],
    seamstresses: roster(),
    unassigned_minutes: 120,
    default_weekly_capacity_hours: 12,
    ...overrides,
  });
}

// --- helpers -----------------------------------------------------------------

async function gotoAtelier(page: Page, replies: Record<string, Reply[]>) {
  const api = await installManageApi(page, { staff: OWNER, replies });
  await page.goto(MANAGE);
  // The owner lands on «סקירה» and reaches the atelier through the nav — there
  // is no direct URL, the console is one page.
  await expect(page.getByRole("heading", { level: 2, name: DASHBOARD_HEADING })).toBeVisible();
  await page.getByRole("navigation").getByRole("button", { name: NAV_ATELIER }).click();
  await expect(panel(page).getByRole("heading", { level: 3 })).toBeVisible();
  return api;
}

function panel(page: Page): Locator {
  return page.getByRole("region", { name: new RegExp(PANEL_HEADING) });
}

function panelRow(page: Page, name: string): Locator {
  return panel(page).getByRole("listitem").filter({ hasText: name });
}

function cue(page: Page): Locator {
  return page.getByTestId("atelier-cue");
}

function dialog(page: Page, title: string): Locator {
  return page.getByRole("dialog").filter({ has: page.getByRole("heading", { name: title }) });
}

async function axeViolations(page: Page): Promise<string[]> {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  return results.violations.map(
    (v) => `${v.id} — ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`,
  );
}

// --- 1. the panel, rendered by a browser -------------------------------------

test("atelier capacity: the roster renders in remaining-capacity order, and overload is never colour-only", async ({
  page,
}) => {
  await gotoAtelier(page, { "/manage/atelier/tickets": [ok(loadedBoard())] });

  // ⚠ RENDER ORDER IS SORT ORDER: headroom → unknown → overloaded. Two groups
  // would put a row at 400 % ahead of an unconfigured one, so the first name a
  // hurried manager reads would be the person the bar beside it draws in red.
  const rows = panel(page).getByRole("listitem");
  await expect(rows).toHaveCount(3);
  await expect(rows.nth(0)).toContainText("דנה");
  await expect(rows.nth(1)).toContainText("רותי");
  await expect(rows.nth(2)).toContainText("נועה");

  // The whole a11y payload is the TEXT beside the bar, in the same words a
  // sighted user reads.
  await expect(panelRow(page, "דנה")).toContainText("1 שעות עד 11.1.2099 מתוך 12");
  await expect(panelRow(page, "דנה")).toContainText(FROM_DEFAULT);
  await expect(panelRow(page, "רותי")).toContainText(NOT_SET);
  await expect(panelRow(page, "נועה")).toContainText(OVER);
  await expect(panelRow(page, "נועה")).toContainText("סה״כ 46 שעות בתור");
  await expect(panel(page).getByText("לא משויך · 2 שעות")).toBeVisible();

  // ⚠ THE BAR CARRIES NO WIDGET SEMANTICS AT ALL — no role, no aria-valuenow,
  // no accessible name — and axe cannot catch a wrongly-roled progressbar
  // whose FORM is correct. This assertion is the only thing that does.
  await expect(page.getByRole("progressbar")).toHaveCount(0);
  await expect(panel(page).locator("[aria-valuenow]")).toHaveCount(0);
  // Three rows, two bars: the unconfigured one has NO track, because an empty
  // track says «she has room» where the truth is «nobody has told this product
  // anything».
  await expect(panel(page).locator("li [aria-hidden='true']")).toHaveCount(2);
  await expect(panelRow(page, "רותי").locator("[aria-hidden='true']")).toHaveCount(0);
});

test("atelier capacity: the bar FILLS FROM THE PHYSICAL RIGHT under dir=rtl, and 140 % is a full bar", async ({
  page,
}) => {
  // ⚠ **THE ONE CLAIM NO UNIT TEST CAN MAKE.** The design deck's diagrams are
  // drawn LTR for legibility and the shipped console is RTL; a builder who
  // implemented the drawn order ships a MIRRORED panel that passes axe, passes
  // every named vitest assertion, and reads backwards to the only users who
  // will ever see it. `inlineSize` is the mechanism and `width` renders too —
  // in jsdom BOTH are just a style string. Here it is measured.
  await gotoAtelier(page, { "/manage/atelier/tickets": [ok(loadedBoard())] });

  const track = panelRow(page, "נועה").locator("[aria-hidden='true']").first();
  const fill = track.locator("> span");
  const trackBox = await track.boundingBox();
  const fillBox = await fill.boundingBox();
  expect(trackBox).not.toBeNull();
  expect(fillBox).not.toBeNull();
  if (trackBox === null || fillBox === null) {
    return;
  }
  // 15 h against 12 is 125 %, clamped to 100 — so the fill IS the track.
  expect(Math.round(fillBox.width)).toBe(Math.round(trackBox.width));
  // Flush with the track's RIGHT edge, which is the inline START of an RTL
  // paragraph. A `width`-based fill that grew from the left would put
  // `fillBox.x` at `trackBox.x` on a PARTIAL bar…
  expect(Math.round(fillBox.x + fillBox.width)).toBe(Math.round(trackBox.x + trackBox.width));

  // …so the partial one is measured too, and this is the assertion a mirrored
  // build fails: דנה is at 1 of 12, a sliver, and it must hug the RIGHT.
  const partialTrack = panelRow(page, "דנה").locator("[aria-hidden='true']").first();
  const partialFill = partialTrack.locator("> span");
  const partialTrackBox = await partialTrack.boundingBox();
  const partialFillBox = await partialFill.boundingBox();
  if (partialTrackBox === null || partialFillBox === null) {
    return;
  }
  expect(partialFillBox.width).toBeLessThan(partialTrackBox.width / 2);
  expect(Math.round(partialFillBox.x + partialFillBox.width)).toBe(
    Math.round(partialTrackBox.x + partialTrackBox.width),
  );
  expect(partialFillBox.x).toBeGreaterThan(partialTrackBox.x);
});

test("atelier capacity: every control clears the 44 px touch floor, MEASURED", async ({ page }) => {
  // jsdom has no layout engine, so the unit suite asserts the CLASS. This is
  // the measurement — and `Input` deliberately is NOT in it: it lands at
  // ≈43.6 px by this repo's own type scale, and WCAG 2.0 AA (the legal bar
  // here) has no target-size criterion at all.
  await gotoAtelier(page, { "/manage/atelier/tickets": [ok(loadedBoard())] });

  const buttons = panel(page).getByRole("button");
  const count = await buttons.count();
  expect(count).toBeGreaterThan(0);
  for (let index = 0; index < count; index += 1) {
    const box = await buttons.nth(index).boundingBox();
    expect(box).not.toBeNull();
    expect(box?.height ?? 0).toBeGreaterThanOrEqual(44);
  }
});

// --- 2. the two empty states a new boutique actually sees --------------------

test("atelier capacity: a boutique with no seamstresses still gets the boutique-wide ruler", async ({
  page,
}) => {
  await gotoAtelier(page, {
    "/manage/atelier/tickets": [ok(atelierBoard({ seamstresses: [] }))],
  });

  await expect(panel(page).getByRole("heading", { level: 3 })).toHaveText("תופרות · 0");
  await expect(panel(page).getByText(NO_SEAMSTRESSES_OWNER)).toBeVisible();
  await expect(panel(page).getByRole("list")).toHaveCount(0);
  // The default is worth setting before the first hire.
  await expect(panel(page).getByRole("button", { name: SETTINGS_OPEN })).toBeVisible();
});

test("atelier capacity: on a board with no tickets and nobody configured, the panel is still the first thing", async ({
  page,
}) => {
  // ⚠ BOTH of the «first thing a new boutique sees» states at once: the
  // zero-ticket branch replaces the columns AND the rail, so a panel rendered
  // only beside the columns would be invisible here.
  await gotoAtelier(page, {
    "/manage/atelier/tickets": [
      ok(
        atelierBoard({
          seamstresses: [
            atelierSeamstress({ id: DANA, display_name: "דנה" }),
            atelierSeamstress({ id: RUTI, display_name: "רותי", assigned_minutes: 240 }),
          ],
        }),
      ),
    ],
  });

  await expect(page.getByText("אין עדיין כרטיסי תפירה")).toBeVisible();
  await expect(panelRow(page, "דנה")).toContainText(NOT_SET);
  await expect(panelRow(page, "רותי")).toContainText("4 שעות");
  await expect(panel(page).locator("li [aria-hidden='true']")).toHaveCount(0);
  // The panel is ABOVE the empty state, not tucked under it.
  const panelBox = await panel(page).boundingBox();
  const emptyBox = await page.getByText("אין עדיין כרטיסי תפירה").boundingBox();
  expect(panelBox?.y ?? 0).toBeLessThan(emptyBox?.y ?? 0);

  expect(await axeViolations(page)).toEqual([]);
});

// --- 3. the capacity write ---------------------------------------------------

test("atelier capacity: setting her hours moves the DENOMINATOR and leaves the load untouched", async ({
  page,
}) => {
  // ⚠ THE ACCEPTANCE CRITERION THE ORIGINAL DESIGN WOULD HAVE FAILED. The write
  // answers capacity facts only; patching a load it does not have would zero
  // the very bar the save just set.
  const api = await gotoAtelier(page, {
    "/manage/atelier/tickets": [ok(loadedBoard())],
    [capacityPath(NOA)]: [
      ok({
        id: NOA,
        display_name: "נועה",
        assignable: true,
        weekly_capacity_hours: 40,
        capacity_is_default: false,
      }),
    ],
  });

  await expect(panelRow(page, "נועה")).toContainText(OVER);
  await panel(page).getByRole("button", { name: hoursAria("נועה") }).click();

  const capacity = dialog(page, CAPACITY_TITLE);
  await expect(capacity).toBeVisible();
  // Her 12 is HERS (capacity_is_default is false), so it prefills.
  await expect(capacity.getByLabel(HOURS_LABEL)).toHaveValue("12");
  await capacity.getByLabel(HOURS_LABEL).fill("40");
  await capacity.getByRole("button", { name: SAVE }).click();

  await expect(capacity).toBeHidden();
  await expect(cue(page)).toHaveText("נועה — עודכנו השעות.");
  // The denominator moved; both load numbers did not; the word is gone because
  // 15 of 40 is not an overload.
  await expect(panelRow(page, "נועה")).toContainText("15 שעות עד 11.1.2099 מתוך 40");
  await expect(panelRow(page, "נועה")).toContainText("סה״כ 46 שעות בתור");
  await expect(panelRow(page, "נועה")).not.toContainText(OVER);

  const written = api.of(capacityPath(NOA));
  expect(written).toHaveLength(1);
  expect(written[0].method).toBe("POST");
  expect(written[0].body).toEqual({ weekly_capacity_hours: 40 });
});

test("atelier capacity: an INHERITED row opens EMPTY, and «חזרה לברירת המחדל» clears back to null", async ({
  page,
}) => {
  const api = await gotoAtelier(page, {
    "/manage/atelier/tickets": [ok(loadedBoard())],
    [capacityPath(DANA)]: [
      ok({
        id: DANA,
        display_name: "דנה",
        assignable: true,
        weekly_capacity_hours: 12,
        capacity_is_default: true,
      }),
    ],
  });

  await panel(page).getByRole("button", { name: hoursAria("דנה") }).click();
  const capacity = dialog(page, CAPACITY_TITLE);

  // ⚠ THE ANTI-CONVERSION GUARD. Her 12 is the boutique's, so the field is
  // EMPTY: saving without typing cannot silently make an inherited number hers.
  await expect(capacity.getByLabel(HOURS_LABEL)).toHaveValue("");
  await expect(capacity.getByText("ריק — חזרה לברירת המחדל של הבוטיק: 12 שעות.")).toBeVisible();

  // F-6: the clear control is in the BODY, and the footer holds exactly two.
  const footer = capacity.locator("div.mt-6");
  await expect(footer.getByRole("button")).toHaveCount(2);
  await expect(footer.getByRole("button", { name: USE_DEFAULT })).toHaveCount(0);
  await expect(capacity.getByRole("button", { name: USE_DEFAULT })).toBeVisible();

  await capacity.getByLabel(HOURS_LABEL).fill("30");
  await capacity.getByRole("button", { name: USE_DEFAULT }).click();
  await expect(capacity.getByLabel(HOURS_LABEL)).toHaveValue("");
  await capacity.getByRole("button", { name: SAVE }).click();

  await expect(cue(page)).toHaveText("דנה — חזרה לברירת המחדל.");
  expect(api.of(capacityPath(DANA))[0].body).toEqual({ weekly_capacity_hours: null });
});

test("atelier capacity: a 403 on the capacity write is handled LOCALLY and never blanks the board", async ({
  page,
}) => {
  // ⚠ The control is role-gated, so this is unreachable from the UI — and it is
  // covered anyway, because `poll.fail`'s {401,403} terminal rule reads a 403 as
  // «her access to THIS BOARD has ended», which is false for a PER-ROUTE
  // tightening. Blanking a board she may still read would be the console
  // punishing her for a button it offered her.
  await gotoAtelier(page, {
    "/manage/atelier/tickets": [ok(loadedBoard())],
    [capacityPath(NOA)]: [refuse(403, "FORBIDDEN")],
  });

  await panel(page).getByRole("button", { name: hoursAria("נועה") }).click();
  const capacity = dialog(page, CAPACITY_TITLE);
  await capacity.getByLabel(HOURS_LABEL).fill("40");
  await capacity.getByRole("button", { name: SAVE }).click();

  // The Hebrew refusal, inside the dialog, focused — and never the server's
  // English, which this console has no way to render.
  const alert = capacity.getByRole("alert");
  await expect(alert).toHaveText(CAPACITY_ERROR);
  await expect(alert).toBeFocused();
  await expect(capacity).toBeVisible();

  // And the board survives the DISMISSAL, which is what distinguishes «handled
  // locally» from «deferred by the open dialog».
  await capacity.getByRole("button", { name: CANCEL }).click();
  await expect(capacity).toBeHidden();
  await expect(page.getByText(ACCESS_ENDED)).toHaveCount(0);
  await expect(panelRow(page, "נועה")).toContainText(OVER);
});

test("atelier capacity: saving after her row has LEFT the payload lands focus on the panel heading", async ({
  page,
}) => {
  // ⚠ **THIS IS THE TEST THAT NEEDS A BROWSER.** A seamstress leaves the
  // `seamstresses` union the moment she is retired AND her last undelivered
  // ticket is delivered. If that repaint lands between opening the dialog and
  // saving, the trigger has UNMOUNTED and native `<dialog>`'s auto-restore has
  // nowhere to go — focus drops to `<body>` and a keyboard user is stranded at
  // the top of the document. This repo has shipped that bug five times and axe
  // walked past every one, because axe cannot see a focus move that never
  // happened.
  await gotoAtelier(page, {
    // Two payloads: the second is the poll tick that removes her.
    "/manage/atelier/tickets": [
      ok(loadedBoard()),
      ok(
        loadedBoard({
          seamstresses: roster().filter((row) => row.id !== NOA),
        }),
      ),
    ],
    [capacityPath(NOA)]: [
      ok({
        id: NOA,
        display_name: "נועה",
        assignable: true,
        weekly_capacity_hours: 40,
        capacity_is_default: false,
      }),
    ],
  });

  await panel(page).getByRole("button", { name: hoursAria("נועה") }).click();
  const capacity = dialog(page, CAPACITY_TITLE);
  await capacity.getByLabel(HOURS_LABEL).fill("40");

  // The tick lands while the dialog is open — the poll is not paused by a
  // dialog, only by a mutation in flight.
  await expect(panelRow(page, "נועה")).toHaveCount(0, { timeout: 15_000 });
  await expect(capacity).toBeVisible();

  await capacity.getByRole("button", { name: SAVE }).click();
  await expect(capacity).toBeHidden();
  // IS the heading — not merely «the heading exists», which is the assertion
  // that cannot tell a restored user from a stranded one.
  await expect(panel(page).getByRole("heading", { level: 3 })).toBeFocused();
});

// --- 4. the effort-band editor ----------------------------------------------

test("atelier capacity: the settings dialog prefills from the envelope and saves the WHOLE block", async ({
  page,
}) => {
  const api = await gotoAtelier(page, {
    "/manage/atelier/tickets": [ok(loadedBoard())],
    "/manage/settings": [ok({ profile: {}, toggles: {}, atelier: {} })],
  });

  await panel(page).getByRole("button", { name: SETTINGS_OPEN }).click();
  const settings = dialog(page, SETTINGS_TITLE);
  await expect(settings).toBeVisible();

  // Prefilled from the BOARD envelope — no second request on open.
  expect(api.of("/manage/settings")).toHaveLength(0);
  await expect(settings.getByLabel("חצי שעה — דקות")).toHaveValue("30");
  await expect(settings.getByLabel("שעה — דקות", { exact: true })).toHaveValue("60");
  await expect(settings.getByLabel("שעתיים — דקות")).toHaveValue("120");
  await expect(settings.getByLabel("חצי יום — דקות", { exact: true })).toHaveValue("240");
  await expect(settings.getByLabel("יום מלא — דקות")).toHaveValue("480");
  await expect(settings.getByLabel("ברירת מחדל: שעות בשבוע", { exact: true })).toHaveValue("12");
  // F-11: D4's silent relabel, said out loud.
  await expect(settings.getByText("שינוי ההערכות משפיע רק על כרטיסים חדשים.")).toBeVisible();
  // No server bound is mirrored, in TypeScript or in a Hebrew sentence.
  await expect(settings).not.toContainText("168");
  await expect(settings).not.toContainText("1440");

  expect(await axeViolations(page)).toEqual([]);

  await settings.getByLabel("חצי יום — דקות", { exact: true }).fill("300");
  await settings.getByRole("button", { name: SAVE }).click();

  await expect(settings).toBeHidden();
  await expect(cue(page)).toHaveText("ההגדרות נשמרו.");

  // ⚠ ONE request carrying BOTH keys. `merge_settings` is one atomic
  // `settings = settings || :patch::jsonb` and `||` merges at the TOP LEVEL
  // ONLY, so a partial `atelier` object would replace the key and delete what
  // it did not name.
  const written = api.of("/manage/settings");
  expect(written).toHaveLength(1);
  expect(written[0].method).toBe("PUT");
  expect(written[0].body).toEqual({
    atelier: {
      effort_bands: {
        thirty_min: 30,
        one_hour: 60,
        two_hours: 120,
        half_day: 300,
        full_day: 480,
      },
      default_weekly_capacity_hours: 12,
    },
  });
});

// --- 5. the assign surface ---------------------------------------------------

test("atelier capacity: the assign picker is sorted and labelled, and overload FLAGS without blocking", async ({
  page,
}) => {
  const api = await gotoAtelier(page, {
    "/manage/atelier/tickets": [ok(loadedBoard())],
    "/manage/atelier/tickets/at-1/assign": [
      ok({ ...atelierTicket(), assigned_staff_user_id: NOA }),
    ],
  });

  const select = page.getByRole("combobox", { name: "תופרת — מיכל לוי" });
  await expect(select.locator("option")).toHaveText([
    "לא משויך",
    "דנה · נותרו 11 שעות",
    "רותי · 4 שעות משויכות",
    "נועה · עומס יתר",
  ]);
  // ⚠ NOTHING IS BLOCKED: the overloaded option is selectable, the write
  // answers 200 and no confirmation appears. Every reallocation is a human
  // action and the console does not overrule the person who can see the room.
  await expect(select.locator("option").last()).not.toBeDisabled();

  await select.selectOption(NOA);
  await page.getByRole("button", { name: "שיוך — מיכל לוי" }).click();

  // ⚠ The overload clause is the ONLY channel a screen-reader user has for this
  // fact: F41's D17 forbids the poll from writing into the announced region, so
  // without it she would watch nothing while a sighted user watches the bar
  // turn red on the next tick.
  await expect(cue(page)).toHaveText("שויך לנועה — עומס יתר.");
  expect(api.of("/manage/atelier/tickets/at-1/assign")[0].body).toEqual({
    staff_user_id: NOA,
  });
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("atelier capacity: assigning to an UNCONFIGURED seamstress announces no overload", async ({
  page,
}) => {
  // ⚠ The null guard. A hand-rolled predicate computes `null * 60 = 0` in JS and
  // announces «עומס יתר» on EVERY assign to an unconfigured seamstress —
  // correct on screen, green under axe, and a legal-accessibility regression on
  // the one channel a screen-reader user has.
  await gotoAtelier(page, {
    "/manage/atelier/tickets": [
      ok(loadedBoard({ tickets: [atelierTicket({ effort_minutes: 480 })] })),
    ],
    "/manage/atelier/tickets/at-1/assign": [
      ok({ ...atelierTicket(), assigned_staff_user_id: RUTI }),
    ],
  });

  await page.getByRole("combobox", { name: "תופרת — מיכל לוי" }).selectOption(RUTI);
  await page.getByRole("button", { name: "שיוך — מיכל לוי" }).click();
  await expect(cue(page)).toHaveText("שויך לרותי.");
});

// --- 6. the keyboard walk, in a browser --------------------------------------

test("atelier capacity: the tab order is pause → the list → each «שעות» → «הגדרות»", async ({
  page,
}) => {
  // The unit suite asserts DOM order; a browser asserts what actually happens.
  // The pause control staying FIRST is F41's D17 / SC 2.2.2 and is
  // non-negotiable: a mechanism to stop a moving surface, placed after the
  // content it governs, is reachable only by walking the list that is
  // repainting under the walk.
  await gotoAtelier(page, { "/manage/atelier/tickets": [ok(loadedBoard())] });

  await page.getByRole("button", { name: "השהיה — לוח התפירה" }).focus();
  const expected = [
    PANEL_HEADING, // the <ul>'s accessible name — the list is the entry stop
    hoursAria("דנה"),
    hoursAria("רותי"),
    hoursAria("נועה"),
    SETTINGS_OPEN,
  ];
  for (const name of expected) {
    await page.keyboard.press("Tab");
    const label = await page.evaluate(() => {
      const active = document.activeElement;
      return active?.getAttribute("aria-label") ?? active?.textContent ?? "";
    });
    expect(label).toBe(name);
  }
  // ⚠ Enter on «שעות» OPENS and writes nothing — the confirm is the writer.
  await page.getByRole("button", { name: hoursAria("דנה") }).focus();
  await page.keyboard.press("Enter");
  await expect(dialog(page, CAPACITY_TITLE)).toBeVisible();
  // Esc dismisses without writing, and `<dialog>` returns focus by itself.
  await page.keyboard.press("Escape");
  await expect(dialog(page, CAPACITY_TITLE)).toBeHidden();
  await expect(page.getByRole("button", { name: hoursAria("דנה") })).toBeFocused();
});
