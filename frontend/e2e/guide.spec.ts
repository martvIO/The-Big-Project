import { test, expect } from "@playwright/test";
import type { Locator, Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { MANAGE, installManageApi, ok, sosAlert, sosPayload, staff } from "./fixtures/manage";
import type { Reply } from "./fixtures/manage";

// F60, the guided walkthrough, in a real browser.
//
// ⚠ **THIS FILE IS THE ONLY PROOF THE FOCUS TRAP EXISTS, AND THE UNIT SUITE
// CANNOT HELP.** jsdom 29.1.1 ships no `<dialog>` implementation — the impl file
// is an empty subclass — so all three `src/test/setup.ts` files stub BOTH
// `showModal` and `show` with a body that is literally `this.open = true`. No
// focus move, no trap, no top layer, no `cancel` event on Esc. A vitest
// assertion about the dialog's focus, its Tab cycle or its Esc route would
// therefore measure the stub and would stay green with every line of the
// component's focus behaviour deleted — F57's vacuous focus test with a
// different mechanism. Spec DL17 bans one outright, so **if this file is weak,
// F60 has no safety argument at all.**
//
// Each test below names the deletion that must turn it red, and each of those
// deletions was performed, observed red and restored.
//
// ⚠ **LOCATORS.** `Modal` sets NO `role` attribute — a `<dialog>` carries only
// an implicit ARIA role. Use `page.getByRole("dialog")`, which resolves it
// through the accessibility tree, or the CSS `dialog[open]`, which is the
// selector `SosOverlay.tsx:298` itself uses. **`page.locator("[role=dialog]")`
// matches NOTHING** and is the vacuity class this preamble exists to prevent.
// Every focus assertion here is POSITIVE — `expect(<named locator>)
// .toBeFocused()` — and a `not.toBeFocused()` appears only IN ADDITION to one.
//
// ⚠ **THERE IS NO LOGIN BLOCK, and writing one would be dead code.**
// `installManageApi` authenticates by not authenticating, and says so at
// `fixtures/manage.ts:14-17`: `App.tsx` bootstraps on `api.me()` and renders
// `<LoginForm/>` on a rejection, so fulfilling `GET /manage/auth/me` with a 200
// `Staff` body is the whole of «signed in» — no cookie, no login POST, no
// session table. `grep -n LOGIN_SUBMIT e2e/*.ts` returns four hits and every one
// is the NEGATIVE assertion `toHaveCount(0)`.
//
// ⚠ **Risk 6, restated at the point of use: the harness stubs the API, so these
// prove the CONSOLE and not the CONTRACT.** F60 has no contract to prove — it
// calls no endpoint, writes no row and needs no migration.

// --- copy, verbatim from apps/manage/src/i18n/he.ts --------------------------

const GUIDE = "מדריך";
const CLOSE = "סגירה";
const NEXT = "הבא";
const PREV = "הקודם";
const DONE = "סיום";
const LOGOUT = "יציאה";
const ROOMS_HEADING = "חדרי מדידה";
const ACCEPT = "אני מגיעה";
const DISMISS = "הסתרה";
// ⚠ THE ACCESSIBLE NAME IS THE aria-label AND NOT THE VISIBLE TEXT. Both
// controls carry `aria-label={t("sos.…Aria", { name })}` (`SosOverlay:580`,
// `:591`), which OVERRIDES the button's text for `getByRole`, and a locator
// written against the visible «אני מגיעה» matches nothing.
const acceptAria = (name: string) => `${ACCEPT} — הקריאה מ${name}`;
const dismissAria = (name: string) => `${DISMISS} — הקריאה מ${name}`;
// `guide.floor.1`, the sentence the dialog describes itself with on open. Quoted
// rather than derived, so a copy edit that empties the step is NAMED here.
const FLOOR_STEP_1 = "החלק העליון מראה מי מהצוות נמצאת בקומה ובאיזה מצב";

// --- copy, verbatim from apps/storefront/src/i18n/he.ts ----------------------

const STOREFRONT = "http://localhost:4173";
const CHECKIN_TRIGGER = "מה קורה אחרי הרישום?";
const CHECKIN_NAME = "שם מלא";
const CHECKIN_SUBMIT = "הצטרפות לתור";

// --- fixture data ------------------------------------------------------------

const RONIT = "רונית";
const MAYA = "מאיה";
const SECOND_ALERT_ID = "sos-2";

// The storefront's `/checkin` withholds the WHOLE form until this lands — the
// collection notice interpolates the controller's name and may never render
// without it — so T9 has nothing to Tab through until it does.
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
};

// --- helpers, copied from sos.spec.ts (extracting a shared one is out of scope)

// Replaces a queue's contents in place. `installManageApi` spreads the OPTIONS
// OBJECT but keeps each queue's array reference, so this is how a test says
// «from the next tick on, the server answers THIS» at a moment of its own
// choosing — which a fixed queue cannot express.
function retarget(queue: Reply[], next: Reply): void {
  queue.length = 0;
  queue.push(next);
}

// ⚠ THE TAG IS PART OF THE SELECTOR. On the floor section both SOS surfaces are
// mounted and both carry `data-alert-id`, so a bare attribute selector matches
// two nodes for one alert. The overlay renders `<article>`.
function card(page: Page, alertId: string): Locator {
  return page.locator(`article[data-alert-id="${alertId}"]`);
}

// Only the rule id and the offending selectors say anything useful; the raw
// violation objects dump ~10 KB of axe internals into the failure.
async function axeViolations(page: Page): Promise<string[]> {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  return results.violations.map(
    (v) => `${v.id} — ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`,
  );
}

// --- the console under test --------------------------------------------------

// The harness default identity is `reception`, and that is the right default
// here rather than an accident: her only reachable row is `floor`, so `activeKey`
// lands there with no navigation, no other panel mounts, and `floor` carries
// THREE steps — which is what gives step 2 a three-control footer for the Tab
// cycle.
async function gotoConsole(page: Page, alerts?: Reply[]): Promise<void> {
  await installManageApi(page, {
    staff: staff(),
    replies: alerts === undefined ? {} : { "/manage/floor/sos": alerts },
  });
  await page.goto(MANAGE);
  // The rooms h3 and not the h2: the h2 renders over the skeleton while the
  // first fetch is in flight, so measuring it would measure nothing.
  await expect(page.getByRole("heading", { level: 3, name: ROOMS_HEADING })).toBeVisible();
}

function guideTrigger(page: Page): Locator {
  return page.getByRole("button", { name: GUIDE });
}

function dialog(page: Page): Locator {
  return page.getByRole("dialog");
}

function control(page: Page, name: string): Locator {
  return dialog(page).getByRole("button", { name });
}

async function openGuide(page: Page): Promise<void> {
  await guideTrigger(page).click();
  await expect(dialog(page)).toBeVisible();
  await settled(page);
}

// ⚠ THE RED FIELD COVERS THE «מדריך» BUTTON, so with an emergency on screen the
// trigger is reachable by KEYBOARD ONLY — `SosOverlay.tsx:451` is `fixed inset-0
// z-40 … bg-danger`, opaque and full-screen, and Playwright's actionability
// check refuses to click through it exactly as a finger would fail to. This is
// deck F-7 measured rather than asserted: focus still lands on a labelled
// button, and IS 5568 is WCAG 2.0 AA, where focus-not-obscured (SC 2.4.11) does
// not exist. DL13 keeps the trigger mounted and enabled, which is what makes
// this reachable at all.
async function openGuideByKeyboard(page: Page): Promise<void> {
  await guideTrigger(page).focus();
  await expect(guideTrigger(page)).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(dialog(page)).toBeVisible();
  await settled(page);
}

// ⚠ NOT A `waitForTimeout`, AND THE DIFFERENCE MATTERS. `Modal`'s panel carries
// `animate-modal-panel` — `opacity: 0 -> 1` over `--motion-base` (200ms,
// `theme.css:119-128`) — and axe run DURING it measures a half-faded panel:
// it reported `fgColor #84786b` where the computed style is `#6b5d4f`, and
// 4.27:1 for a pair that is 6.35:1 once opaque. That is a WAIT defect in the
// test and not a contrast defect in the design, and `getAnimations()` is the
// exact signal rather than a sleep long enough to hide it.
async function settled(page: Page): Promise<void> {
  await dialog(page).evaluate(async (node) => {
    await Promise.all(node.getAnimations({ subtree: true }).map((a) => a.finished));
  });
}

// --- T1 — focus lands INSIDE the dialog --------------------------------------

// ⚠ DELETION: reorder the footer so the primary sits first. PERFORMED, OBSERVED
// RED, RESTORED. Invisible to vitest — both jsdom stubs are `this.open = true`
// and are indistinguishable, so this measures the real dialog-focusing steps.
//
// ⚠ THE PLAN AND SPEC NAME `showModal()` → `show()` FOR THIS TEST AND THEY ARE
// WRONG — it was performed and came back GREEN. The HTML dialog-focusing steps
// run for BOTH methods, so a non-modal `<dialog>` moves focus to its first
// focusable descendant exactly as a modal one does. What `showModal()` uniquely
// buys is the top layer, document inertness and the close watcher — which is why
// that same one-token deletion DOES redden T2, T3, T4, T5 and T8 below, and why
// this test's honest deletion is one that changes which control comes first.
test("guide: opening it puts focus INSIDE the dialog, on the first control", async ({ page }) => {
  await gotoConsole(page);
  await openGuide(page);

  await expect(control(page, CLOSE)).toBeFocused();
});

// --- T2, T3 — the Tab cycle --------------------------------------------------

// ⚠ DELETION for both: `Modal.tsx:29` `dlg.showModal()` → `dlg.show()`. Without
// modality Tab leaves the dialog into the console header and lands on «יציאה».
// PERFORMED, OBSERVED RED, RESTORED.

// ⚠ MEASURED, NOT ASSUMED: Chromium's modal cycle is «סגירה» -> «הבא» -> <body>
// -> «סגירה». The document root IS a stop in a modal dialog's sequential focus
// order, so «one Tab from the last returns to the first» is FALSE in a real
// browser and a test written that way would fail for the wrong reason. What is
// true, and what these two measure, is that the cycle NEVER reaches the console
// chrome and always returns into the dialog.
async function expectOutsideTheConsole(page: Page): Promise<void> {
  await expect(page.getByRole("button", { name: LOGOUT })).not.toBeFocused();
  await expect(guideTrigger(page)).not.toBeFocused();
  await expect(page.getByRole("navigation")).not.toBeFocused();
}

test("guide: Tab from the last control returns to the first, never the console", async ({
  page,
}) => {
  await gotoConsole(page);
  await openGuide(page);

  await control(page, NEXT).focus();
  await expect(control(page, NEXT)).toBeFocused();

  await page.keyboard.press("Tab");
  // ⚠ THE LEG THAT REDDENS UNDER `show()`. The dialog sits between the trigger
  // and the logout in `ConsoleShell`'s header, so a NON-modal dialog sends this
  // Tab straight onto «יציאה».
  await expectOutsideTheConsole(page);

  await page.keyboard.press("Tab");
  await expect(control(page, CLOSE)).toBeFocused();
});

test("guide: Shift+Tab from the first control reaches the last, never the console", async ({
  page,
}) => {
  await gotoConsole(page);
  await openGuide(page);

  await expect(control(page, CLOSE)).toBeFocused();

  await page.keyboard.press("Shift+Tab");
  await expectOutsideTheConsole(page);

  await page.keyboard.press("Shift+Tab");
  // Step 1 has no «הקודם» (DL10 — absent, not disabled), so the footer is
  // «סגירה» then «הבא» and the last control IS «הבא».
  await expect(control(page, NEXT)).toBeFocused();
});

// --- T4, T5 — Esc ------------------------------------------------------------

// ⚠ DELETION for both: `Modal.tsx:29` `showModal()` → `show()`. A non-modal
// `<dialog>` has no close watcher, so Esc does not close it at all.
// PERFORMED, OBSERVED RED, RESTORED.
//
// ⚠ TWO OTHER DELETIONS WERE PROPOSED AND BOTH COME BACK GREEN — do not use
// them. Deleting `onCancel` (`Modal.tsx:38-42`) alone leaves `onClose={onClose}`
// (`:43`) wired: Esc closes natively, `close` fires, `onClose()` runs
// `setOpen(false)`, the `[open]` effect's `!open && !dlg.open` branch is a
// no-op, and the browser has already returned focus. Deleting BOTH is no
// better: `open` never changes, so the effect never re-runs and nothing reopens
// the dialog. What `onCancel` uniquely buys is already pinned by
// `packages/ui/src/__tests__/Modal.test.tsx:18-34`.
test("guide: Esc from the step body closes it", async ({ page }) => {
  await gotoConsole(page);
  await openGuide(page);

  // ⚠ THE STEP PARAGRAPH, deliberately: non-focusable dialog content is the
  // exact `activeElement` state D6 refuses to assume anything about, and
  // clicking it is what makes T7 leg (b) a real measurement rather than a
  // restatement of leg (a).
  await dialog(page).getByText(FLOOR_STEP_1).click();
  await page.keyboard.press("Escape");

  await expect(dialog(page)).toBeHidden();
});

test("guide: Esc returns focus to the «מדריך» button", async ({ page }) => {
  await gotoConsole(page);
  await openGuide(page);

  await page.keyboard.press("Escape");

  await expect(dialog(page)).toBeHidden();
  await expect(guideTrigger(page)).toBeFocused();
});

// --- T6, T6b — the two pointer routes out ------------------------------------

// ⚠ DELETION: in `GuideOverlay`, replace `setOpen(false)` with an unmount of the
// whole component. Focus drops to `<body>` — the exact defect class this repo
// has shipped FIVE times, and the reason DL13 keeps the trigger mounted and
// enabled even while an emergency is on screen.
test("guide: «סיום» on the last step returns focus to the «מדריך» button", async ({ page }) => {
  await gotoConsole(page);
  await openGuide(page);

  await control(page, NEXT).click();
  await expect(control(page, PREV)).toBeVisible();
  await control(page, NEXT).click();

  // The primary control changes identity in the same slot on the last step.
  await expect(control(page, NEXT)).toHaveCount(0);
  await control(page, DONE).click();

  await expect(dialog(page)).toBeHidden();
  await expect(guideTrigger(page)).toBeFocused();
});

// ⚠ DELETION: remove «סגירה» from `GuideOverlay`'s footer. This test then has
// nothing to click — which is the exact state a keyboard-less tablet is left in,
// because `Modal` binds NO backdrop click and the chrome has no X. Without it
// the only way out of step 1 is tapping «הבא» to the end.
test("guide: a pointer-only user can leave from step 1, without pressing any key", async ({
  page,
}) => {
  await gotoConsole(page);
  await openGuide(page);

  await control(page, CLOSE).click();

  await expect(dialog(page)).toBeHidden();
  await expect(guideTrigger(page)).toBeFocused();
});

// --- T7 — the SOS collision, in three legs -----------------------------------

// ⚠ THE ONE INTERACTION IN THIS FEATURE THAT CAN HURT SOMEBODY. `showModal()`
// promotes the dialog to the browser's TOP LAYER, which paints above every
// z-index in the document — including `SosOverlay.tsx:451`'s `fixed inset-0
// z-40` — and makes every node outside it INERT: unclickable, unreachable by
// Tab, invisible to hit-testing. So with the guide open an arriving emergency
// page is not merely covered, it is UNANSWERABLE. There is no z-index, no portal
// and no stacking context that changes this.
//
// ⚠ DELETION for all three legs: delete `GuideOverlay`'s D6 effect. PERFORMED,
// OBSERVED RED, RESTORED — all three go red.
//
// ⚠ AND THE INERTNESS ITSELF WAS MEASURED RATHER THAN ASSERTED, because it is
// the single claim this whole feature rests on. With the effect neutered and the
// guide left open, in this exact harness: the card RENDERS and reports
// `isVisible() === true` — so a «the emergency is covered» framing understates
// it — while `locator.click()` on «אני מגיעה» TIMES OUT (pointer events blocked)
// and a direct `element.focus()` leaves `document.activeElement` on something
// else. Visible, unclickable and unfocusable at once: that is what the top layer
// does, and it is why no z-index, portal or stacking context is an alternative
// to closing the guide.
test("guide: an arriving SOS page closes it, returns focus, and its ack is CLICKABLE", async ({
  page,
}) => {
  const alerts: Reply[] = [ok(sosPayload([]))];
  await gotoConsole(page, alerts);
  await openGuide(page);

  retarget(alerts, ok(sosPayload([sosAlert({ raised_by_name: RONIT })])));

  // ⚠ WAIT ON THE CARD FIRST, AND FIX THE WAIT RATHER THAN RAISE THE TIMEOUT.
  // With no live alert the poll beat is `SOS_INTERVAL_MS` (5 000ms) — exactly
  // Playwright's default expect timeout — so asserting the dialog hidden first
  // races the tick that delivers the page. The card appearing IS the tick
  // landing; `toBeVisible` measures a box and not hit-testing, so it resolves
  // even while the guide still covers it.
  await expect(card(page, "sos-1")).toBeVisible({ timeout: 15_000 });
  await expect(dialog(page)).toBeHidden();
  await expect(guideTrigger(page)).toBeFocused();
  // ⚠ THE CLICK IS THE ASSERTION. Playwright's actionability check requires the
  // element to be visible, stable and RECEIVING POINTER EVENTS — which is
  // exactly what an inert node under a top-layer dialog is not.
  await card(page, "sos-1").getByRole("button", { name: acceptAria(RONIT) }).click();
});

test("guide: the same, after a click on non-focusable dialog content", async ({ page }) => {
  // ⚠ LEG (b), AND IT IS THE MEASUREMENT THAT REPLACES THE REJECTED
  // LAYOUT-EFFECT FIX. `SosOverlay` is mounted at `App.tsx:236`, BEFORE
  // `ConsoleShell`, so its effects flush first — in the commit in which the
  // alert arrives, while the guide is still open. Whether `document.activeElement`
  // can degrade to `<body>` after a click on non-focusable dialog content is
  // ENGINE-DEPENDENT and the spec refuses to assume it either way, so MOVE A's
  // `activeElement === document.body` guard (`SosOverlay:203-205`) may read true
  // and fire `.focus()` at a node `showModal()` has made inert — a no-op, with
  // `hadCardsRef` already consumed. That outcome is ACCEPTED rather than
  // engineered around: focus is not lost, `close()` returns it to the labelled
  // «מדריך» button, and Esc reaches «אני מגיעה» in one keypress the moment
  // `dialog[open]` stops matching. This test is what makes «accepted» a
  // measurement rather than a hope.
  const alerts: Reply[] = [ok(sosPayload([]))];
  await gotoConsole(page, alerts);
  await openGuide(page);

  await dialog(page).getByText(FLOOR_STEP_1).click();
  retarget(alerts, ok(sosPayload([sosAlert({ raised_by_name: RONIT })])));

  await expect(card(page, "sos-1")).toBeVisible({ timeout: 15_000 });
  await expect(dialog(page)).toBeHidden();
  await expect(guideTrigger(page)).toBeFocused();
  await card(page, "sos-1").getByRole("button", { name: acceptAria(RONIT) }).click();
});

test("guide: a SECOND page arriving over a reopened guide closes it and stays answerable", async ({
  page,
}) => {
  // ⚠ LEG (c), AND IT ADDITIONALLY REDDENS IF THE DETECTOR TESTS ONLY THE HEAD
  // OF THE ALERT LIST. `alerts` is oldest-first on every path —
  // `sos-context.ts:18` declares it, `sos_alerts.py:245` is `ORDER BY
  // created_at` ascending, `sos.tsx:128-131` appends — so a new page arrives at
  // the END. That is precisely where a top-layer dialog is most dangerous: the
  // second emergency lands under a dialog the first one already failed to close.
  const first = sosAlert({ raised_by_name: RONIT });
  const alerts: Reply[] = [ok(sosPayload([first]))];
  await gotoConsole(page, alerts);
  await expect(card(page, "sos-1")).toBeVisible();

  // Dismissed, so the red field clears and the trigger is reachable again. The
  // alert stays LIVE — the dismiss is per-device and in-memory
  // (`SosOverlay:322-330`) — which is exactly the state DL12 exists for: the
  // close is edge-triggered, so a persisting page must not lock the guide shut.
  await card(page, "sos-1").getByRole("button", { name: dismissAria(RONIT) }).click();
  await expect(card(page, "sos-1")).toHaveCount(0);
  await openGuide(page);

  retarget(
    alerts,
    ok(sosPayload([first, sosAlert({ id: SECOND_ALERT_ID, raised_by_name: MAYA })])),
  );

  await expect(card(page, SECOND_ALERT_ID)).toBeVisible({ timeout: 15_000 });
  await expect(dialog(page)).toBeHidden();
  await expect(guideTrigger(page)).toBeFocused();
  await card(page, SECOND_ALERT_ID).getByRole("button", { name: acceptAria(MAYA) }).click();
});

// --- T8 — Esc means one thing at a time --------------------------------------

// ⚠ DELETION: `SosOverlay.tsx:298`, the `document.querySelector("dialog[open]")
// !== null` early return. The capture listener then reaches
// `event.preventDefault()` (`:312`), which SUPPRESSES the dialog's own close
// request — so the first Esc focuses the ack and the guide stays open, and this
// goes red on its first assertion. (Any claim that it «fires both» is wrong; the
// capture listener's preventDefault is why.) PERFORMED, OBSERVED RED, RESTORED.
test("guide: Esc closes the guide first and reaches the SOS ack only on the second press", async ({
  page,
}) => {
  // ⚠ THE SETUP IS EXPLICIT BECAUSE D6 MAKES THE NAIVE ONE UNREACHABLE. The
  // alert is in the FIRST poll response, so the D6 edge is consumed by that
  // arrival — then the guide is opened OVER the live page, which DL13 (trigger
  // never disabled) and DL12 (close edge-triggered) between them allow.
  await gotoConsole(page, [ok(sosPayload([sosAlert({ raised_by_name: RONIT })]))]);
  await expect(card(page, "sos-1")).toBeVisible();

  await openGuideByKeyboard(page);

  await page.keyboard.press("Escape");
  await expect(dialog(page)).toBeHidden();
  await expect(card(page, "sos-1").getByRole("button", { name: acceptAria(RONIT) })).not.toBeFocused();
  await expect(guideTrigger(page)).toBeFocused();

  await page.keyboard.press("Escape");
  await expect(card(page, "sos-1").getByRole("button", { name: acceptAria(RONIT) })).toBeFocused();
});

// --- T9 — the storefront's disclosure traps nothing ---------------------------

// ⚠ DELETION: convert `CheckinPage`'s disclosure to a `Modal`. Tab is then
// trapped inside the dialog and never reaches the name field.
// PERFORMED, OBSERVED RED, RESTORED.
test("checkin: the queue hint reveals in place and traps nothing", async ({ page }) => {
  await page.route("**/storefront/boutique", async (route) => {
    await route.fulfill({
      status: 200,
      headers: { "content-type": "application/json", "cache-control": "no-store" },
      body: JSON.stringify(BOUTIQUE),
    });
  });

  await page.goto(`${STOREFRONT}/checkin`);
  // The submit and not the h1: the form is WITHHELD while the boutique fetch is
  // in flight and again if it fails, so the heading is up over a skeleton.
  await expect(page.getByRole("button", { name: CHECKIN_SUBMIT })).toBeVisible();

  const trigger = page.getByRole("button", { name: CHECKIN_TRIGGER });
  await expect(trigger).toHaveAttribute("aria-expanded", "false");
  await trigger.click();
  await expect(trigger).toHaveAttribute("aria-expanded", "true");

  // ⚠ NO FOCUS MOVE, and that is the third deck to decline `ManageBookingPage`'s
  // reveal-focus-move. APG's disclosure moves no focus, and there is nothing in
  // one revealed sentence to move it to.
  await expect(trigger).toBeFocused();

  await page.keyboard.press("Tab");
  await expect(page.getByLabel(CHECKIN_NAME)).toBeFocused();
});

// --- the two axe passes -------------------------------------------------------

// ⚠ THEY ARE THE FLOOR AND NOT THE PROOF. axe reports NONE of the focus class
// above and was green all five times this repo shipped a focus-drops-to-<body>
// defect. T1-T9 are the accessibility work; these two catch the IDREF and
// contrast classes that only a real stylesheet can answer.
test("guide: zero axe A/AA violations with the dialog open", async ({ page }) => {
  await gotoConsole(page);
  await openGuide(page);

  expect(await axeViolations(page)).toEqual([]);
});

test("checkin: zero axe A/AA violations with the hint revealed", async ({ page }) => {
  await page.route("**/storefront/boutique", async (route) => {
    await route.fulfill({
      status: 200,
      headers: { "content-type": "application/json", "cache-control": "no-store" },
      body: JSON.stringify(BOUTIQUE),
    });
  });

  await page.goto(`${STOREFRONT}/checkin`);
  await expect(page.getByRole("button", { name: CHECKIN_SUBMIT })).toBeVisible();
  await page.getByRole("button", { name: CHECKIN_TRIGGER }).click();
  await expect(page.getByRole("button", { name: CHECKIN_TRIGGER })).toHaveAttribute(
    "aria-expanded",
    "true",
  );

  // No animation on this surface, but the same rule: measure a settled page.
  expect(await axeViolations(page)).toEqual([]);
});
