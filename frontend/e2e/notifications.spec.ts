import { test, expect } from "@playwright/test";
import type { Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import {
  MANAGE,
  bellList,
  bellMarked,
  bellNotification,
  installManageApi,
  ok,
  refuse,
  sosPayload,
  staff,
} from "./fixtures/manage";
import type { Reply } from "./fixtures/manage";

// F35, the staff notification bell, in a real browser — on F58's harness rather
// than a parallel one. The `floor` family is ALREADY intercepted (both bell
// paths keep `floor` as their second segment), so this file adds replies and
// forks nothing.
//
// ⚠ **EVERY TEST BELOW EXISTS BECAUSE jsdom CANNOT ANSWER IT.**
// `NotificationBell.test.tsx` already pins every branch these journeys walk.
// What it cannot pin, and what each block here measures instead:
//
//   1. `<dialog>`. jsdom has none — `setup.ts` stubs `showModal()` — so the
//      focus trap, Esc, the focus RETURN to the bell and the move to
//      `#console-main` are unobservable there and are only real here.
//   2. axe's `color-contrast` rule, SKIPPED ENTIRELY in jsdom because Tailwind's
//      stylesheet is never applied. The badge, the «חדש» marker and the muted
//      row times are all small text on a raised surface.
//   3. F-B2: the header now carries THREE chrome controls. Whether a long
//      boutique name wraps or overflows at 375px is a layout fact no unit test
//      can reach.
//
// ⚠ **The harness stubs the API, so these prove the CONSOLE and not the
// CONTRACT.** A renamed payload key passes every test in this file;
// `test_bell_api.py`'s set-equality assertions are what catch that.

// --- copy, verbatim from apps/manage/src/i18n/he.ts --------------------------

const BELL = "התראות";
const BELL_TITLE = "התראות";
const MARK_ALL = "סמני הכל כנקרא";
const CLOSE = "סגירה";
const EMPTY = "אין התראות";
const NEW_MARKER = "חדש";
const LOAD_FAILED = "לא הצלחנו לטעון את ההתראות כרגע.";
const RETRY = "ניסיון נוסף";
const ROOMS_HEADING = "חדרי מדידה";
const NAV_FLOOR = "קומה";

const bellName = (count: number) => (count === 0 ? BELL : `${BELL}, ${count} חדשות`);
const dispatchRow = (name: string) => `${name} הפנתה אליך לקוחה`;
const handoverRow = (name: string) => `${name} העבירה אליך חדר`;
const sosRow = (name: string) => `${name} ביקשה עזרה`;

// --- fixture data ------------------------------------------------------------

const DANA = "דנה";
const MAYA = "מאיה";

const DISPATCH = bellNotification({ id: "nt-dispatch", kind: "dispatch_assigned", actor_name: DANA });
const HANDOVER = bellNotification({ id: "nt-handover", kind: "room_handed_over", actor_name: MAYA });
const SOS = bellNotification({ id: "nt-sos", kind: "sos_targeted", actor_name: MAYA });

const VIEWPORT_375 = { width: 375, height: 812 };
const VIEWPORT_1440 = { width: 1440, height: 900 };

// --- helpers -----------------------------------------------------------------

function bell(page: Page) {
  return page.getByRole("button", { name: new RegExp(BELL) });
}

function panel(page: Page) {
  return page.getByRole("dialog");
}

// Replaces a queue in place: `installManageApi` spreads the options object but
// keeps each queue's array reference, so this is how a test says «from the next
// tick on, the server answers THIS» at a moment of its own choosing.
function retarget(queue: Reply[], next: Reply): void {
  queue.length = 0;
  queue.push(next);
}

async function axeViolations(page: Page): Promise<string[]> {
  // Settle bounded animations BEFORE scanning. The panel fades in, and
  // `toBeVisible()` resolves when it paints, not when the opacity transition
  // ends — scanning inside that window makes axe composite a half-faded layer
  // and report a contrast the page never renders at rest. That is what failed
  // here: `--color-ink-muted` on the panel is 6.2:1 settled, well over the 4.5
  // floor. Third spec in this codebase to need it (waitlist, platform, here).
  // ⚠ Infinite animations are filtered out: `--animate-skeleton` and Button's
  // `animate-spin` never resolve `.finished`, and this panel renders a Skeleton
  // in its loading state — awaiting one hangs the scan until the test times out.
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

// --- the journey -------------------------------------------------------------

test.describe("the bell's whole journey", () => {
  test("counts, opens, navigates on a row, and clears", async ({ page }) => {
    const sos = [ok(sosPayload([], 2))];
    const list = [ok(bellList([DISPATCH, HANDOVER]))];
    const read = [ok(bellMarked(1))];
    await installManageApi(page, {
      staff: staff({ display_name: "רונית", role: "reception" }),
      replies: {
        "/manage/floor/sos": sos,
        "/manage/floor/notifications": list,
        "POST /manage/floor/notifications/read": read,
      },
    });

    await page.goto(MANAGE);
    // The count comes off the SOS tick, which is the console's only app-wide
    // loop — nothing in this file ever waits for a bell-specific request before
    // the panel opens, because there is none.
    await expect(bell(page)).toHaveAccessibleName(bellName(2));

    await bell(page).click();
    await expect(panel(page)).toBeVisible();
    await expect(panel(page).getByRole("heading", { name: BELL_TITLE })).toBeVisible();
    await expect(panel(page).getByText(dispatchRow(DANA))).toBeVisible();

    // Esc dismisses and the platform returns focus to the trigger. This is the
    // assertion jsdom structurally cannot make.
    await page.keyboard.press("Escape");
    await expect(panel(page)).toBeHidden();
    await expect(bell(page)).toBeFocused();

    await bell(page).click();
    retarget(sos, ok(sosPayload([], 1)));
    await panel(page).getByRole("button", { name: dispatchRow(DANA) }).click();

    // The panel closes, the console is on the floor, and focus is parked on the
    // section she was sent to — NOT back on the chrome control she came from.
    await expect(panel(page)).toBeHidden();
    await expect(page.getByRole("heading", { level: 3, name: ROOMS_HEADING })).toBeVisible();
    await expect(page.locator("#console-main")).toBeFocused();
    await expect(bell(page)).toHaveAccessibleName(bellName(1));
  });

  test("«mark all» clears the badge and sends only the rendered page", async ({ page }) => {
    const sos = [ok(sosPayload([], 2))];
    const recorder = await installManageApi(page, {
      replies: {
        "/manage/floor/sos": sos,
        "/manage/floor/notifications": [ok(bellList([DISPATCH, HANDOVER]))],
        "POST /manage/floor/notifications/read": [ok(bellMarked(0))],
      },
    });

    await page.goto(MANAGE);
    await expect(bell(page)).toHaveAccessibleName(bellName(2));
    await bell(page).click();

    retarget(sos, ok(sosPayload([], 0)));
    await panel(page).getByRole("button", { name: MARK_ALL }).click();

    await expect(bell(page)).toHaveAccessibleName(bellName(0));
    // No badge node at all at zero — not a «0».
    await expect(bell(page)).toHaveText(BELL);

    const posted = recorder.of("/manage/floor/notifications/read");
    expect(posted).toHaveLength(1);
    expect(posted[0].body).toEqual({ ids: [DISPATCH.id, HANDOVER.id] });
  });

  test("an SOS row is text and cannot be tapped", async ({ page }) => {
    // The one kind with no destination: the live surface is F37's overlay, which
    // owns itself. A row that looked tappable and only marked itself read would
    // be an affordance that lies.
    await installManageApi(page, {
      replies: {
        "/manage/floor/sos": [ok(sosPayload([], 1))],
        "/manage/floor/notifications": [ok(bellList([SOS]))],
      },
    });

    await page.goto(MANAGE);
    await bell(page).click();
    await expect(panel(page).getByText(sosRow(MAYA))).toBeVisible();
    await expect(panel(page).getByRole("button", { name: sosRow(MAYA) })).toHaveCount(0);
    // It is still clearable — «mark all» reaches it like any other unread row.
    await expect(panel(page).getByRole("button", { name: MARK_ALL })).toBeVisible();
  });

  test("a list failure announces itself and retries into a populated panel", async ({ page }) => {
    const list: Reply[] = [refuse(500, "INTERNAL")];
    await installManageApi(page, {
      replies: {
        "/manage/floor/sos": [ok(sosPayload([], 1))],
        "/manage/floor/notifications": list,
      },
    });

    await page.goto(MANAGE);
    await bell(page).click();
    await expect(panel(page).getByText(LOAD_FAILED)).toBeVisible();

    retarget(list, ok(bellList([HANDOVER])));
    await panel(page).getByRole("button", { name: RETRY }).click();
    await expect(panel(page).getByText(handoverRow(MAYA))).toBeVisible();
    await expect(panel(page).getByText(LOAD_FAILED)).toHaveCount(0);
  });

  test("an owner lands on the board, whose nav has no floor row", async ({ page }) => {
    // F-B1. She is a legitimate handover recipient and her nav does not contain
    // «קומה», so an unconditional setSection("floor") would strand her.
    await installManageApi(page, {
      staff: staff({ display_name: "שרה", role: "owner" }),
      replies: {
        "/manage/floor/sos": [ok(sosPayload([], 1))],
        "/manage/floor/notifications": [ok(bellList([HANDOVER]))],
        "POST /manage/floor/notifications/read": [ok(bellMarked(0))],
      },
    });

    await page.goto(MANAGE);
    await bell(page).click();
    await panel(page).getByRole("button", { name: handoverRow(MAYA) }).click();

    await expect(page.getByRole("navigation").getByRole("button", { name: NAV_FLOOR })).toHaveCount(
      0,
    );
    await expect(page.locator("#console-main")).toBeFocused();
  });
});

// --- F-B2: the third chrome control at 375px ---------------------------------

test.describe("the header at 375px", () => {
  for (const badged of [true, false]) {
    test(`does not scroll horizontally with a long boutique name — ${
      badged ? "badged" : "unbadged"
    }`, async ({ page }) => {
      // ~204px of chrome plus 32px of gutters leaves ~139px for the name. It must
      // degrade by WRAPPING the wordmark to a second line, never by overflowing.
      await page.setViewportSize(VIEWPORT_375);
      await installManageApi(page, {
        staff: staff({ display_name: "בוטיק הכלה של שרה ובנותיה בתל אביב" }),
        replies: { "/manage/floor/sos": [ok(sosPayload([], badged ? 3 : 0))] },
      });

      await page.goto(MANAGE);
      await expect(bell(page)).toBeVisible();

      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(overflow).toBeLessThanOrEqual(0);
    });
  }
});

// --- axe: zero violations, five states, two widths, RTL ----------------------

test.describe("axe", () => {
  for (const [label, viewport] of [
    ["375", VIEWPORT_375],
    ["1440", VIEWPORT_1440],
  ] as const) {
    test(`the header and the panel are clean at ${label}`, async ({ page }) => {
      // The gate is LEGAL (IS 5568 / WCAG 2.0 AA) and zero is the only passing
      // number. Five states in one test because each needs the same page and a
      // fresh navigation per state would triple the run for no more coverage.
      await page.setViewportSize(viewport);
      const sos = [ok(sosPayload([], 3))];
      const list: Reply[] = [ok(bellList([DISPATCH, HANDOVER, SOS]))];
      await installManageApi(page, {
        replies: {
          "/manage/floor/sos": sos,
          "/manage/floor/notifications": list,
        },
      });

      await page.goto(MANAGE);

      // ① header WITH a badge — small text on a bordered pill, the contrast
      // measurement jsdom cannot make.
      await expect(bell(page)).toHaveAccessibleName(bellName(3));
      expect(await axeViolations(page)).toEqual([]);

      // ② the populated panel: rows, «חדש» markers, muted times.
      await bell(page).click();
      await expect(panel(page).getByText(dispatchRow(DANA))).toBeVisible();
      await expect(panel(page).getByText(NEW_MARKER).first()).toBeVisible();
      expect(await axeViolations(page)).toEqual([]);

      // ③ the empty panel, whose sentence is the dialog's description.
      await panel(page).getByRole("button", { name: CLOSE }).click();
      retarget(list, ok(bellList([])));
      await bell(page).click();
      await expect(panel(page).getByText(EMPTY)).toBeVisible();
      expect(await axeViolations(page)).toEqual([]);

      // ④ the panel in its load-failure state, whose line is a role="alert".
      await panel(page).getByRole("button", { name: CLOSE }).click();
      retarget(list, refuse(500, "INTERNAL"));
      await bell(page).click();
      await expect(panel(page).getByText(LOAD_FAILED)).toBeVisible();
      expect(await axeViolations(page)).toEqual([]);

      // ⑤ header WITHOUT a badge — the ordinary state, and the one every other
      // journey in the console renders.
      await panel(page).getByRole("button", { name: CLOSE }).click();
      retarget(sos, ok(sosPayload([], 0)));
      await expect(bell(page)).toHaveAccessibleName(bellName(0));
      expect(await axeViolations(page)).toEqual([]);
    });
  }
});
