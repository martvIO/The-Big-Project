import { test, expect } from "@playwright/test";
import type { Locator, Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import {
  MANAGE,
  SHIFT_DEADLINE_AT,
  SHIFT_WEEK_START,
  installManageApi,
  ok,
  refuse,
  settingsPayload,
  settleAnimations,
  shiftSubmissionRow,
  shiftSubmissions,
  shiftTemplate,
  shiftTemplatePath,
  shiftWeek,
  staff,
} from "./fixtures/manage";

// F39's four panes, in a real browser (the `waitlist.spec.ts` per-feature
// shape). The FOCUS assertions live here and not in vitest deliberately: jsdom
// has no `<dialog>` and `setup.ts` stubs `showModal()`, so an assertion that
// pre-places focus on its own target is vacuous there. axe-zero is the LEGAL
// floor here (IS 5568 / WCAG 2.0 AA), not a preference.
//
// ⚠ Risk 6, as everywhere in this directory: the harness stubs the API, so these
// prove the UI and not the contract.

const MORNING = "sh-morning";
const EVENING = "sh-evening";
const MICHAL = "st-michal";

const TEMPLATES = [
  shiftTemplate(),
  shiftTemplate({ id: EVENING, day_of_week: 4, label: "משמרת ערב", sort_order: 1 }),
];

// ⚠ 44 px IS THE FLOOR AND IT IS NEVER LOWERED TO MAKE A MEASUREMENT PASS.
// LOOP-STATE's 0032-era finding: `Modal`'s 0.97→1 open animation makes a
// compliant control measure 42.68 px mid-transition, so every measurement in
// this file runs AFTER `settleAnimations(page)`.
const TOUCH_FLOOR = 44;

async function expectTouchTargets(page: Page, scope: Locator): Promise<void> {
  await settleAnimations(page);
  const controls = scope.locator("button, label:has(input[type=radio]), a[href]");
  const count = await controls.count();
  expect(count).toBeGreaterThan(0);
  for (let index = 0; index < count; index += 1) {
    const box = await controls.nth(index).boundingBox();
    if (box === null) {
      continue; // not rendered — a closed dialog's own controls
    }
    expect(box.height, await controls.nth(index).innerText()).toBeGreaterThanOrEqual(TOUCH_FLOOR);
  }
}

async function expectAxeClean(page: Page): Promise<void> {
  await settleAnimations(page);
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .include("#console-main")
    .analyze();
  expect(results.violations).toEqual([]);
}

async function openShifts(page: Page): Promise<void> {
  await page.goto(MANAGE);
  await page.getByRole("button", { name: "זמינות למשמרות" }).click();
  await expect(page.getByRole("heading", { name: "הזמינות שלי" })).toBeVisible();
}

// --- the staffer's journey ---------------------------------------------------

test("a seamstress lands on the floor, opens her week, marks it and saves", async ({ page }) => {
  // ⚠ SHE LANDS ON «הצוות בקומה», NOT ON THE SHIFTS SECTION. The nav row sits
  // AFTER `floor`, so `reachable[0]?.key` is unchanged — put it before and a
  // seamstress opens the console on a form instead of on her floor.
  const recorder = await installManageApi(page, {
    staff: staff({ id: "st-seam", display_name: "מיכל", role: "seamstress" }),
    replies: {
      "/manage/shifts/templates": [ok({ templates: TEMPLATES })],
      "GET /manage/shifts/week": [ok(shiftWeek({ templates: TEMPLATES }))],
      "/manage/shifts/week/availability": [
        ok(
          shiftWeek({
            templates: TEMPLATES,
            entries: [
              {
                id: "e1",
                shift_template_id: MORNING,
                state: "available",
                recorded_by_name: null,
              },
            ],
          }),
        ),
      ],
    },
  });

  await page.goto(MANAGE);
  await expect(page.getByRole("heading", { name: "צוות בקומה" })).toBeVisible();

  await page.getByRole("button", { name: "זמינות למשמרות" }).click();
  await expect(page.getByRole("heading", { name: "הזמינות שלי" })).toBeVisible();
  // The deadline line, and the whole point of `jerusalemIsoDate` before
  // `plainDayMonth`: a raw instant renders «NaN.11» here.
  await expect(page.getByText("מועד ההגשה: יום רביעי, 7.1, 18:00")).toBeVisible();
  await expect(page.getByRole("heading", { name: "ראשון · 11.1" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "חמישי · 15.1" })).toBeVisible();

  await page.getByRole("group").first().getByRole("radio", { name: "זמינה" }).check();
  await page.getByRole("button", { name: "שמירת זמינות" }).click();
  await expect(page.getByText("נשמר לפני רגע")).toBeVisible();

  const saves = recorder.of("/manage/shifts/week/availability");
  expect(saves).toHaveLength(1);
  expect(saves[0].body).toEqual({
    week_start: SHIFT_WEEK_START,
    entries: [{ shift_template_id: MORNING, state: "available" }],
  });

  await expectTouchTargets(page, page.locator("#console-main"));
  await expectAxeClean(page);
});

test("«סימון כל השאר כזמינה» fills only the blanks and announces the result", async ({ page }) => {
  await installManageApi(page, {
    staff: staff({ id: "st-seam", role: "seamstress" }),
    replies: {
      "/manage/shifts/templates": [ok({ templates: TEMPLATES })],
      "GET /manage/shifts/week": [
        ok(
          shiftWeek({
            templates: TEMPLATES,
            entries: [
              {
                id: "e1",
                shift_template_id: MORNING,
                state: "unavailable",
                recorded_by_name: null,
              },
            ],
          }),
        ),
      ],
    },
  });
  await openShifts(page);

  await expect(page.getByText("נענו: 1 מתוך 2")).toBeVisible();
  await page.getByRole("button", { name: "סימון כל השאר כזמינה" }).click();
  // Never overwrites an answer she already gave — non-destructive by
  // construction, which is what removes any need for an undo.
  await expect(
    page.getByRole("group").first().getByRole("radio", { name: "לא זמינה" }),
  ).toBeChecked();
  await expect(page.getByText("נענו: 2 מתוך 2")).toBeVisible();
});

test("a locked week shows her answers as text, with no save button", async ({ page }) => {
  await installManageApi(page, {
    staff: staff({ id: "st-seam", role: "seamstress" }),
    replies: {
      "/manage/shifts/templates": [ok({ templates: TEMPLATES })],
      "GET /manage/shifts/week": [
        ok(
          shiftWeek({
            locked: true,
            templates: TEMPLATES,
            entries: [
              {
                id: "e1",
                shift_template_id: MORNING,
                state: "preferred",
                recorded_by_name: "דנה כהן",
              },
            ],
          }),
        ),
      ],
    },
  });
  await openShifts(page);

  await expect(page.getByText(/מועד ההגשה לשבוע הזה עבר/)).toBeVisible();
  // ⚠ NO DISABLED RADIO ANYWHERE. A disabled control is not focusable, so it
  // would strand a keyboard user from the answers the locked screen exists to
  // show her.
  await expect(page.getByRole("radio")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "שמירת זמינות" })).toHaveCount(0);
  await expect(page.getByText("מעדיפה")).toBeVisible();
  await expect(page.getByText("לא נרשם")).toBeVisible();

  await expectAxeClean(page);
});

test("SUBMISSION_CLOSED mid-save locks the screen and moves focus to the banner", async ({
  page,
}) => {
  // ⚠ THE SAVE BUTTON SHE JUST PRESSED IS GONE, so focus falls to <body> and her
  // next Tab restarts at the skip link — after twelve answered shifts, a
  // traverse of the shell and the whole nav (WCAG 2.4.3).
  await installManageApi(page, {
    staff: staff({ id: "st-seam", role: "seamstress" }),
    replies: {
      "/manage/shifts/templates": [ok({ templates: TEMPLATES })],
      "GET /manage/shifts/week": [
        ok(shiftWeek({ templates: TEMPLATES })),
        ok(shiftWeek({ locked: true, templates: TEMPLATES })),
      ],
      "/manage/shifts/week/availability": [refuse(409, "SUBMISSION_CLOSED")],
    },
  });
  await openShifts(page);

  await page.getByRole("group").first().getByRole("radio", { name: "זמינה" }).check();
  await page.getByRole("button", { name: "שמירת זמינות" }).click();

  const banner = page.getByText(/מועד ההגשה לשבוע הזה עבר\. אפשר לפנות/);
  await expect(banner).toBeVisible();
  await expect(banner).toBeFocused();
  await expect(page.getByRole("button", { name: "שמירת זמינות" })).toHaveCount(0);
});

test("a staffer with no templates reads a fact, not a fault, and is offered no seed", async ({
  page,
}) => {
  await installManageApi(page, {
    staff: staff({ id: "st-seam", role: "seamstress" }),
    replies: {
      "/manage/shifts/templates": [ok({ templates: [] })],
      "GET /manage/shifts/week": [ok(shiftWeek({ templates: [], entries: [] }))],
    },
  });
  await openShifts(page);

  await expect(page.getByText("עדיין לא הוגדרו משמרות לשבוע הזה.")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "יצירת משמרות משעות הפעילות" }),
  ).toHaveCount(0);

  await expectAxeClean(page);
});

// --- the owner's journey -----------------------------------------------------

test("an owner seeds from the opening hours and lands focus on the count", async ({ page }) => {
  // ⚠ FIRST RUN SHOWS ONLY THE TEMPLATES CARD. Three stacked empties above the
  // one button that fixes them is a first-run screen that hides its own next
  // step. Success then unmounts the button she pressed AND releases three more
  // Cards, so focus is moved deliberately.
  await installManageApi(page, {
    staff: staff({ id: "st-owner", display_name: "ורד", role: "owner" }),
    replies: {
      "/manage/shifts/templates": [ok({ templates: [] }), ok({ templates: TEMPLATES })],
      "/manage/shifts/templates/seed": [ok({ created: 3, templates: TEMPLATES })],
      "GET /manage/shifts/week": [ok(shiftWeek({ templates: TEMPLATES }))],
      "/manage/shifts/week/submissions": [ok(shiftSubmissions([shiftSubmissionRow()]))],
      "/manage/settings": [ok(settingsPayload())],
    },
  });

  await page.goto(MANAGE);
  await page.getByRole("button", { name: "זמינות למשמרות" }).click();
  await expect(page.getByRole("heading", { name: "משמרות הבוטיק" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "הזמינות שלי" })).toHaveCount(0);

  await expectAxeClean(page);

  await page.getByRole("button", { name: "יצירת משמרות משעות הפעילות" }).click();
  const done = page.getByText("משמרות שנוצרו משעות הפעילות: 3");
  await expect(done).toBeVisible();
  await expect(done).toBeFocused();
});

test("the seed refusal teaches instead of being pre-checked away", async ({ page }) => {
  // ⚠ THE BUTTON IS RENDERED UNCONDITIONALLY. A pre-check needs a
  // `GET /manage/availability` on every mount purely to hide a control the
  // server already guards — a second reader that can disagree with the writer.
  const recorder = await installManageApi(page, {
    staff: staff({ id: "st-owner", role: "owner" }),
    replies: {
      "/manage/shifts/templates": [ok({ templates: [] })],
      "/manage/shifts/templates/seed": [refuse(409, "NO_OPENING_HOURS")],
    },
  });
  await page.goto(MANAGE);
  await page.getByRole("button", { name: "זמינות למשמרות" }).click();
  await page.getByRole("button", { name: "יצירת משמרות משעות הפעילות" }).click();

  await expect(
    page.getByText("לא הוגדרו שעות פעילות. אפשר להגדיר אותן במסך שעות פעילות."),
  ).toBeVisible();
  expect(recorder.of("/manage/availability")).toHaveLength(0);
});

test("an owner splits a shift, sees the invalidation count, and removes one", async ({ page }) => {
  const withAnswers = [
    shiftTemplate({ future_submission_count: 4 }),
    shiftTemplate({ id: EVENING, day_of_week: 4, label: "משמרת ערב", sort_order: 1 }),
  ];
  await installManageApi(page, {
    staff: staff({ id: "st-owner", role: "owner" }),
    replies: {
      "/manage/shifts/templates": [ok({ templates: withAnswers })],
      "GET /manage/shifts/week": [ok(shiftWeek({ templates: withAnswers }))],
      "/manage/shifts/week/submissions": [ok(shiftSubmissions([shiftSubmissionRow()]))],
      "/manage/settings": [ok(settingsPayload())],
      [shiftTemplatePath(MORNING)]: [
        ok({ template: shiftTemplate(), invalidated_submissions: 4 }),
      ],
    },
  });
  await openShifts(page);

  await page.getByRole("button", { name: "עריכה" }).first().click();
  await page.getByLabel("שעת סיום").fill("21:00");
  await page.getByRole("button", { name: "שמירת המשמרת" }).click();

  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(
    dialog.getByText("שינוי המשמרת ימחק תשובות שכבר נרשמו לשבועות הבאים. תשובות שיימחקו: 4"),
  ).toBeVisible();
  // ⚠ MEASURED AFTER THE OPEN ANIMATION SETTLES. `Modal`'s 0.97→1 scale makes a
  // compliant 44 px control read 42.68 px mid-transition, and the answer is to
  // settle the animation — never to lower the floor.
  await expectTouchTargets(page, dialog);
  await expectAxeClean(page);

  await dialog.getByRole("button", { name: "שמירת המשמרת" }).click();
  await expect(page.getByText("תשובות שנמחקו לשבועות הבאים: 4")).toBeVisible();
});

test("removing a shift returns focus to that weekday's add button", async ({ page }) => {
  // ⚠ `Modal` RETURNS FOCUS TO ITS TRIGGER — which is the `[הסרה]` button on the
  // row that was just deleted. On the success path only, focus moves to the
  // nearest surviving control in the same group.
  await installManageApi(page, {
    staff: staff({ id: "st-owner", role: "owner" }),
    replies: {
      "/manage/shifts/templates": [
        ok({ templates: TEMPLATES }),
        ok({ templates: [TEMPLATES[1]] }),
      ],
      "GET /manage/shifts/week": [ok(shiftWeek({ templates: TEMPLATES }))],
      "/manage/shifts/week/submissions": [ok(shiftSubmissions([shiftSubmissionRow()]))],
      "/manage/settings": [ok(settingsPayload())],
      [shiftTemplatePath(MORNING)]: [ok({ template: null, invalidated_submissions: 0 })],
    },
  });
  await openShifts(page);

  const sunday = page.locator("section", { has: page.getByRole("heading", { name: "ראשון" }) });
  await page.getByRole("button", { name: "הסרה" }).first().click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "הסרה" }).click();

  await expect(sunday.getByRole("button", { name: "הוספת משמרת" })).toBeFocused();
});

test("an owner reads the readiness list and records on a staffer's behalf", async ({ page }) => {
  const recorder = await installManageApi(page, {
    staff: staff({ id: "st-owner", role: "owner" }),
    replies: {
      "/manage/shifts/templates": [ok({ templates: TEMPLATES })],
      "GET /manage/shifts/week": [ok(shiftWeek({ templates: TEMPLATES }))],
      "/manage/shifts/week/submissions": [
        ok(
          shiftSubmissions([
            shiftSubmissionRow({
              staff_user_id: MICHAL,
              display_name: "מיכל ברזילי",
              submitted: false,
            }),
            shiftSubmissionRow({
              staff_user_id: "st-dana",
              display_name: "דנה כהן",
              submitted: true,
              entries: [
                {
                  id: "e1",
                  shift_template_id: MORNING,
                  state: "available",
                  recorded_by_name: null,
                },
              ],
            }),
          ]),
        ),
      ],
      "/manage/settings": [ok(settingsPayload())],
      "/manage/shifts/week/availability": [
        ok(
          shiftWeek({
            templates: TEMPLATES,
            entries: [
              {
                id: "e2",
                shift_template_id: MORNING,
                state: "available",
                recorded_by_name: "ורד",
              },
            ],
          }),
        ),
      ],
    },
  });
  await openShifts(page);

  await expect(page.getByText("הגישו 1 מתוך 2")).toBeVisible();
  await expect(page.getByText("טרם הגישה")).toBeVisible();

  await page.getByRole("button", { name: /רישום עבור מיכל ברזילי/ }).click();
  // ⚠ THE WEEKDAY GROUPING IS WHAT STOPS A `recorded_by`-STAMPED WRITE AGAINST
  // THE WRONG DAY: `label` is free operator text with no uniqueness rule.
  await expect(page.getByText("הזמינות תירשם על שמך כמי שרשמה אותה.")).toBeVisible();
  const expanded = page.locator("li", { hasText: "מיכל ברזילי" });
  await expect(expanded.getByRole("heading", { name: "ראשון · 11.1" })).toBeVisible();
  await expect(expanded.getByRole("heading", { name: "חמישי · 15.1" })).toBeVisible();

  await expanded.getByRole("group").first().getByRole("radio", { name: "זמינה" }).check();
  await expectAxeClean(page);

  await page.getByRole("button", { name: /שמירה עבור מיכל ברזילי/ }).click();
  await expect(page.getByText(/הזמינות של/)).toBeVisible();

  // ONE request, never one per tap.
  const saves = recorder.of("/manage/shifts/week/availability");
  expect(saves).toHaveLength(1);
  expect(saves[0].body).toMatchObject({ week_start: SHIFT_WEEK_START, staff_user_id: MICHAL });
  // And exactly ONE readiness read: the badge flips from the write's own
  // response, never from a second read that could race it.
  expect(recorder.of("/manage/shifts/week/submissions")).toHaveLength(1);
});

test("the deadline card saves both fields in one request", async ({ page }) => {
  // ⚠ `merge_settings` merges at the TOP LEVEL ONLY, so a patch naming one of
  // the two DELETES the other — which is why this Card has one save button.
  const recorder = await installManageApi(page, {
    staff: staff({ id: "st-owner", role: "owner" }),
    replies: {
      "/manage/shifts/templates": [ok({ templates: TEMPLATES })],
      "GET /manage/shifts/week": [ok(shiftWeek({ templates: TEMPLATES }))],
      "/manage/shifts/week/submissions": [ok(shiftSubmissions([shiftSubmissionRow()]))],
      "/manage/settings": [ok(settingsPayload())],
    },
  });
  await openShifts(page);

  await expect(page.getByRole("heading", { name: "מועד ההגשה" })).toBeVisible();
  await page.getByLabel("שעת ההגשה").fill("17:30");
  await page.getByRole("button", { name: "שמירת מועד ההגשה" }).click();
  await expect(page.getByText("נשמר לפני רגע")).toBeVisible();

  const puts = recorder.all.filter(
    (entry) => entry.method === "PUT" && entry.path === "/manage/settings",
  );
  expect(puts).toHaveLength(1);
  expect(puts[0].body).toEqual({
    scheduling: { submission_deadline_day_of_week: 3, submission_deadline_time: "17:30" },
  });
});

// --- the four panes' loading and failure renders -----------------------------

test("every pane's load failure is axe-clean and offers a retry", async ({ page }) => {
  // ⚠ A `Skeleton` AND A `role="alert"` + retry PAIR ARE AS MUCH A RENDER AS THE
  // POPULATED ONE, and three of the four panes only got them at design rev 2. A
  // 500 on the readiness read was previously indistinguishable from «nobody has
  // submitted», which is the correct and informative Monday render.
  await installManageApi(page, {
    staff: staff({ id: "st-owner", role: "owner" }),
    replies: {
      "/manage/shifts/templates": [ok({ templates: TEMPLATES })],
      "GET /manage/shifts/week": [refuse(500, "SERVER_ERROR")],
      "/manage/shifts/week/submissions": [refuse(500, "SERVER_ERROR")],
      "/manage/settings": [refuse(500, "SERVER_ERROR")],
    },
  });
  await openShifts(page);

  await expect(page.getByText("לא הצלחנו לטעון את הנתונים כרגע.")).toHaveCount(3);
  await expect(page.getByRole("button", { name: "ניסיון נוסף" })).toHaveCount(3);
  // The `h2`s survive every failure, so the heading order never changes.
  await expect(page.getByRole("heading", { level: 2 })).toHaveCount(4);

  await expectTouchTargets(page, page.locator("#console-main"));
  await expectAxeClean(page);
});

// --- responsive --------------------------------------------------------------

test("nothing scrolls sideways at 375, 768 or 1440", async ({ page }) => {
  await installManageApi(page, {
    staff: staff({ id: "st-owner", role: "owner" }),
    replies: {
      "/manage/shifts/templates": [ok({ templates: TEMPLATES })],
      "GET /manage/shifts/week": [ok(shiftWeek({ templates: TEMPLATES }))],
      "/manage/shifts/week/submissions": [
        ok(
          shiftSubmissions([
            shiftSubmissionRow({ display_name: "מיכל ברזילי אברמוביץ' לוינשטיין" }),
          ]),
        ),
      ],
      "/manage/settings": [ok(settingsPayload())],
    },
  });
  await openShifts(page);

  for (const width of [375, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await settleAnimations(page);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow, `${width}px`).toBeLessThanOrEqual(0);
  }

  await page.setViewportSize({ width: 375, height: 900 });
  await expectTouchTargets(page, page.locator("#console-main"));
  await expectAxeClean(page);
});

// The deadline instant is a CONSTANT in the fixtures, so this file's rendered
// «יום רביעי, 7.1» is a fact about the console's formatting rather than about
// the machine's clock. Asserted once, out of band, so a fixture edit that broke
// the pairing would name itself.
test("the fixture deadline really is the Wednesday before the fixture week", () => {
  expect(SHIFT_DEADLINE_AT.startsWith("2099-01-07")).toBe(true);
  expect(SHIFT_WEEK_START).toBe("2099-01-11");
});
