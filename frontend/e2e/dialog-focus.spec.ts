import { test, expect } from "@playwright/test";
import type { Locator, Page } from "@playwright/test";
import {
  MANAGE,
  assignment,
  floorPayload,
  installManageApi,
  ok,
  room,
  staff,
  staffCard,
  SELF_ID,
} from "./fixtures/manage";
import type { Recorder } from "./fixtures/manage";

// The four <dialog> rules, in a browser that actually implements <dialog>.
//
// ⚠ **THESE LIVE HERE BECAUSE THE UNIT SUITE CANNOT FAIL THEM.** Every
// `test/setup.ts` in this workspace stubs `HTMLDialogElement.showModal()` as
// `this.open = true` and nothing else — no focus move, no trap, no top layer,
// no `cancel` on Esc. Under that stub focus never LEAVES the trigger, so a
// jsdom assertion that focus came BACK to the trigger is true before the
// component runs and stays true with its restore effect deleted. Two such
// assertions were removed from `RoomsRegistryDialog.test.tsx` and replaced by
// this file; that describe block names it.
//
// The rules, one named test each, per dialog:
//   1. opening moves focus INTO the dialog, onto a sensible first target
//   2. Tab from the last focusable wraps to the first, Shift+Tab the reverse
//   3. Esc closes it
//   4. closing restores focus to the control that opened it
//
// ⚠ **Rules 1-3 are the PLATFORM's, and that is the point.** `Modal.tsx` buys
// all three with one call — `showModal()` — and every test here was RUN against
// the mutation that takes it away. The ledger, so nobody has to trust the claim:
//
//   M1  `dlg.setAttribute("open", "")` in place of `dlg.showModal()` — the
//       jsdom stub's exact behaviour, rendered in a real browser. SEVEN OF THE
//       EIGHT RED, which is the whole argument for this file: what the unit
//       suite fakes is precisely what these measure. The survivor is the SOS
//       restore, and it survives HONESTLY — `FloorPanel.tsx`'s MOVE G puts
//       focus back itself once the dismissed control drops it to <body>, which
//       is exactly the job that effect exists for. M3 is its proof.
//   M2  `dlg.show()` in place of `dlg.showModal()` — a dialog that renders and
//       takes focus identically but is neither modal nor inert. The two TRAP
//       tests and the two ESC tests red; the two OPEN tests stay green, which is
//       correct — `show()` runs the same focusing steps.
//   M3  the components' own restore effects (`RoomsPanel.tsx` MOVE 4,
//       `FloorPanel.tsx` MOVE G) rewired to focus the panel heading instead of
//       the trigger. EXACTLY ONE test reds — the SOS restore — and nothing else.
//       ⚠ The REGISTRY restore stays green, and that is the correct answer
//       rather than a hole: both effects early-return unless `activeElement` is
//       <body>, and on the registry's ordinary close path the platform has
//       already put focus on the trigger by the time MOVE 4 runs, so rewiring
//       its destination changes nothing. MOVE G reds because the dismissed SOS
//       control drops focus to <body> first, which is the job it exists for.
//   M3b MOVE 4 with that <body> guard REMOVED and aimed at the heading — the
//       mutation that actually reaches the registry's close path. BOTH restore
//       tests red, so both measure the DESTINATION and not merely that
//       something took focus. The registry's own proof of that is M3b; M1 is
//       its proof that a focus return happens at all.
//
// Rule 4 is the platform's too on the ordinary path — a native <dialog> returns
// focus to its opener on close, and MOVE 4 / MOVE G exist for the path it
// cannot serve, where the trigger has UNMOUNTED. `RoomsRegistryDialog.test.tsx`
// DC-10 and `SosRaiseDialog.test.tsx` MOVE G still own that one; M3 shows the
// assertions below can still fail when the app aims focus somewhere else.
//
// ⚠ **Risk 6, as everywhere in this directory: the harness stubs the API, so
// these prove the CONSOLE and not the CONTRACT.**

// --- copy, verbatim from apps/manage/src/i18n/he.ts --------------------------

const NAV_BOARD = "לוח היום";
const DASHBOARD_HEADING = "סקירה";
const ROOMS_HEADING = "חדרי מדידה";
const ROOMS_MANAGE = "ניהול חדרים";
const ROOMS_CLOSE = "סגירה";
const ROOMS_LABEL = "שם החדר";
const ROOMS_TITLE = "חדרי המדידה של הבוטיק";
const SOS_TITLE = "קריאה לעזרה";
const SOS_SEND = "שליחת הקריאה";
const SOS_DISMISS = "ביטול";
const raiseAria = (roomLabel: string) => `קריאה לעזרה — ${roomLabel}`;

const MANAGER = staff({ id: "st-mgr", display_name: "דנה", role: "shift_manager" });
const MANAGER_CARD = staffCard({ id: "st-mgr", display_name: "דנה", role: "shift_manager" });

// --- helpers -----------------------------------------------------------------

// The rooms h3 is written only from a settled floor payload — the same "the
// data landed" tell `manage.spec.ts` and `sos.spec.ts` use.
async function floorSettled(page: Page): Promise<void> {
  await expect(page.getByRole("heading", { level: 3, name: ROOMS_HEADING })).toBeVisible();
}

// Reception's only reachable section IS the floor, so there is no navigation.
async function gotoFloor(page: Page): Promise<void> {
  await page.goto(MANAGE);
  await floorSettled(page);
}

// The registry trigger is `elevated`-only, and the two elevated roles land on
// «סקירה» and reach the floor through «לוח היום».
async function gotoBoardFloor(page: Page): Promise<void> {
  await page.goto(MANAGE);
  await expect(page.getByRole("heading", { level: 2, name: DASHBOARD_HEADING })).toBeVisible();
  await page.getByRole("navigation").getByRole("button", { name: NAV_BOARD }).click();
  await floorSettled(page);
}

// --- the registry dialog: one room, one manager ------------------------------

async function installRegistry(page: Page): Promise<void> {
  await installManageApi(page, {
    staff: MANAGER,
    replies: {
      "/manage/floor": [
        ok(floorPayload({ staff: [MANAGER_CARD], rooms: [room({ id: "rm-1", label: "חדר 1" })] })),
      ],
    },
  });
}

function registryTrigger(page: Page): Locator {
  return page.getByRole("button", { name: ROOMS_MANAGE });
}

// The dialog's FIRST focusable once its rows have SETTLED: the first room row's
// «שם החדר» field. Not `dialog.getByRole("textbox")` bare — the add row carries
// a second field with the same label, and strict mode says so.
//
// ⚠ "Settled" is load-bearing. `Modal` is a CHILD of `RoomsRegistryDialog`, so
// React runs the child's `showModal()` effect BEFORE the parent's seed-on-open
// effect, and the rows arrive one commit LATER than the open. Every test that
// names this control waits for the row first.
function registryFirst(dialog: Locator): Locator {
  return dialog.getByTestId("registry-row").first().getByRole("textbox");
}

// The LAST: `Modal` renders `footer` after `children`, and the registry's
// footer is one ghost dismiss.
function registryLast(dialog: Locator): Locator {
  return dialog.getByRole("button", { name: ROOMS_CLOSE });
}

async function openRegistry(page: Page): Promise<Locator> {
  await gotoBoardFloor(page);
  await registryTrigger(page).click();
  const dialog = page.getByRole("dialog", { name: ROOMS_TITLE });
  await expect(dialog).toBeVisible();
  return dialog;
}

// `document.activeElement` is `<body>` and no control holds focus. What one Tab
// off the end of a top layer produces in Chromium, and the shape that says the
// press went NOWHERE rather than onto the screen behind.
async function focusIsOnNothing(page: Page): Promise<boolean> {
  return page.evaluate(() => document.activeElement === document.body);
}

test("registry dialog: opening it moves focus off the trigger and into a named field", async ({
  page,
}) => {
  await installRegistry(page);
  const dialog = await openRegistry(page);

  // ⚠ ASSERTED BY ACCESSIBLE NAME rather than by node, deliberately. The seed
  // race above means the control the platform lands on is the ADD row's «שם
  // החדר» field; once the rows settle it would be the first ROW's field. BOTH
  // carry that name, so this passes on the shipped ordering and would still
  // pass if the rows were seeded before the open — while a focus that never
  // entered the dialog fails either way.
  //
  // MUTATION PROOF (M1): open the <dialog> by ATTRIBUTE instead of calling
  // `showModal()` — what the jsdom stub does — and this reds. The dialog paints,
  // every control in it is readable, and focus never moves: count 0.
  await expect(dialog.locator(":focus")).toHaveCount(1);
  await expect(dialog.locator(":focus")).toHaveAccessibleName(ROOMS_LABEL);
  await expect(registryTrigger(page)).not.toBeFocused();
});

test("registry dialog: Tab off the last control wraps to the first, and Shift+Tab back", async ({
  page,
}) => {
  await installRegistry(page);
  const dialog = await openRegistry(page);
  await expect(dialog.getByTestId("registry-row")).toHaveCount(1);

  // ⚠ TWO presses per direction, and the middle stop is Chromium's, not a wart
  // in the test: tabbing off the end of a top layer parks on the document
  // before wrapping. THAT is what the assertion in between is for — the floor
  // behind is inert, so the press lands on NOTHING rather than on a control out
  // there.
  //
  // MUTATION PROOF (M2): `dlg.show()` instead of `dlg.showModal()` and this
  // reds. A non-modal <dialog> renders and takes focus identically but makes
  // nothing inert, so the walk leaves the dialog and never comes back.
  await registryLast(dialog).focus();
  await page.keyboard.press("Tab");
  expect(await focusIsOnNothing(page)).toBe(true);
  await page.keyboard.press("Tab");
  await expect(registryFirst(dialog)).toBeFocused();

  await registryFirst(dialog).focus();
  await page.keyboard.press("Shift+Tab");
  expect(await focusIsOnNothing(page)).toBe(true);
  await page.keyboard.press("Shift+Tab");
  await expect(registryLast(dialog)).toBeFocused();
});

test("registry dialog: Esc closes it", async ({ page }) => {
  await installRegistry(page);
  const dialog = await openRegistry(page);

  // MUTATION PROOF (M2): `dlg.show()` instead of `dlg.showModal()` and this
  // reds — Esc is a MODAL dialog's behaviour and a non-modal one ignores the
  // key. `Modal`'s `onCancel` is NOT what carries this: with the handler gone
  // the platform still closes and the `onClose` prop still syncs the state,
  // which is why the unit suite's synthetic `cancel` event is a fair test of
  // the handler and no test at all of the key.
  await page.keyboard.press("Escape");

  await expect(dialog).toBeHidden();
});

test("registry dialog: closing it restores focus to «ניהול חדרים»", async ({ page }) => {
  await installRegistry(page);
  const dialog = await openRegistry(page);

  // MUTATION PROOF (M1, M3b). ⚠ NOT M3: MOVE 4 does not run on this path at
  // all — the platform restores focus before the effect fires and its <body>
  // guard sends it home — so redirecting its destination leaves this GREEN.
  // What this measures is the PLATFORM's return, and M1 takes that away.
  // M3b — MOVE 4 with the guard removed and aimed at the rooms heading — is
  // what proves the assertion is about the DESTINATION rather than about
  // something, anything, having taken focus.
  await registryLast(dialog).click();

  await expect(dialog).toBeHidden();
  await expect(registryTrigger(page)).toBeFocused();
});

// --- the SOS raise dialog: reception, standing in her own room ---------------
//
// The one the unit file's own comment points at: `SosRaiseDialog.test.tsx`
// measures the three MOVES the component owns and none of the four below.

async function installRaise(page: Page): Promise<Recorder> {
  return installManageApi(page, {
    replies: {
      "/manage/floor": [
        ok(
          floorPayload({
            staff: [
              staffCard(),
              staffCard({ id: "st-maya", display_name: "מאיה", role: "seamstress" }),
            ],
            rooms: [
              room({
                id: "rm-1",
                label: "חדר 1",
                assignment: assignment({ id: "as-1", staff_user_id: SELF_ID }),
              }),
            ],
          }),
        ),
      ],
    },
  });
}

function raiseTrigger(page: Page): Locator {
  return page.getByRole("button", { name: raiseAria("חדר 1") });
}

// FIRST focusable: the target Select. LAST: the send button, `footer`'s second.
function raiseFirst(dialog: Locator): Locator {
  return dialog.getByRole("combobox");
}

function raiseLast(dialog: Locator): Locator {
  return dialog.getByRole("button", { name: SOS_SEND });
}

async function openRaise(page: Page): Promise<Locator> {
  await gotoFloor(page);
  await raiseTrigger(page).click();
  const dialog = page.getByRole("dialog", { name: SOS_TITLE });
  await expect(dialog).toBeVisible();
  return dialog;
}

test("sos raise dialog: opening it moves focus off the trigger and onto the target picker", async ({
  page,
}) => {
  await installRaise(page);
  const dialog = await openRaise(page);

  // No seed race on this one — the dialog's body is static — so the landing
  // target can be named outright. MUTATION PROOF (M1).
  await expect(raiseFirst(dialog)).toBeFocused();
  await expect(raiseTrigger(page)).not.toBeFocused();
});

test("sos raise dialog: Tab off the send control wraps to the target picker, and Shift+Tab back", async ({
  page,
}) => {
  await installRaise(page);
  const dialog = await openRaise(page);

  // The same two-press shape as the registry, and for the same reason.
  await raiseLast(dialog).focus();
  await page.keyboard.press("Tab");
  expect(await focusIsOnNothing(page)).toBe(true);
  await page.keyboard.press("Tab");
  await expect(raiseFirst(dialog)).toBeFocused();

  await raiseFirst(dialog).focus();
  await page.keyboard.press("Shift+Tab");
  expect(await focusIsOnNothing(page)).toBe(true);
  await page.keyboard.press("Shift+Tab");
  await expect(raiseLast(dialog)).toBeFocused();
});

test("sos raise dialog: Esc closes it without paging anybody", async ({ page }) => {
  const api = await installRaise(page);
  const dialog = await openRaise(page);

  // MUTATION PROOF (M2). And the second assertion is the reason this dialog is
  // worth a named Esc test of its own rather than the registry's: a dismiss that
  // sent the page would be an emergency raised by a mis-tap.
  await page.keyboard.press("Escape");

  await expect(dialog).toBeHidden();
  expect(api.of("/manage/floor/sos").filter((entry) => entry.method === "POST")).toHaveLength(0);
});

test("sos raise dialog: closing it restores focus to the tile's «קריאה לעזרה»", async ({ page }) => {
  await installRaise(page);
  const dialog = await openRaise(page);

  // Dismissed by its own control rather than by Esc, so this test measures the
  // RETURN and not the key the test above owns.
  //
  // MUTATION PROOF (M3): point `FloorPanel.tsx`'s MOVE-G effect at the floor
  // heading instead of the trigger and this reds.
  await dialog.getByRole("button", { name: SOS_DISMISS }).click();

  await expect(dialog).toBeHidden();
  await expect(raiseTrigger(page)).toBeFocused();
});
