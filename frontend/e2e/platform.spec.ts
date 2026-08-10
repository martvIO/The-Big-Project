import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import {
  PLATFORM,
  installPlatformApi,
  invite,
  ok,
  operator,
  refuse,
  tenant,
} from "./fixtures/platform";
import type { Invite, Recorder, Tenant } from "./fixtures/platform";

// F25's platform console — the operator journeys and the axe gate.
//
// ⚠ **THE FOCUS-TRAP AND FOCUS-RESTORE ASSERTIONS LIVE HERE AND NOWHERE ELSE.**
// jsdom implements `<dialog>` only partially, and `src/test/setup.ts` stubs
// `showModal()` — so a vitest assertion about trapped focus proves the stub,
// not the browser (`.memory/jsdom-has-no-dialog`). A real Chromium is the only
// place that claim can be made.
//
// The axe gate is a LEGAL requirement (IS 5568 / WCAG 2.0 AA, pre-decided #38):
// internal audience changes nothing.

const BELLA = tenant();
const NOA = tenant({ slug: "noa", name: "נועה", created_at: "2026-08-02T09:30:00Z" });

async function signedIn(page: Page, tenants: Tenant[] = [BELLA, NOA]): Promise<Recorder> {
  const recorder = await installPlatformApi(page, { tenants });
  await page.goto(PLATFORM);
  await expect(page.getByRole("heading", { name: "ניהול הפלטפורמה", level: 1 })).toBeVisible();
  return recorder;
}

async function axeClean(page: Page, label: string): Promise<void> {
  // Settle every running animation BEFORE scanning. The shared `Modal` fades in,
  // and `toBeVisible()` resolves the moment the dialog paints — not when the
  // opacity transition finishes. Scanning inside that window makes axe composite
  // the half-faded layer against the page and report a contrast it never renders
  // at rest: the reset dialog failed with foreground #837769, which is
  // `--color-ink-muted` (#6B5D4F) at ~84% opacity over #fdfcfb — 4.26:1. At full
  // opacity the real pair is 6.2:1, comfortably over the 4.5 floor, so the
  // violation was an artefact of WHEN the scan ran, not of the tokens.
  // Same remedy the dialog suites already use (guide.spec.ts `settled`), and the
  // same false red that was fixed in waitlist.spec.ts on main.
  // ⚠ FILTER THE INFINITE ONES. `--animate-skeleton` and Button's `animate-spin`
  // both loop forever, and their `.finished` promise NEVER resolves — awaiting
  // it hangs the scan until the test times out. Only bounded animations can be
  // waited on, and even those get a ceiling so a pathological one degrades into
  // a slightly-early scan rather than a 30s timeout.
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
  expect(results.violations, `${label} has axe violations`).toEqual([]);
}

// --- the login journey -------------------------------------------------------

test("platform: a bad password shows the Hebrew failure and never the server's English", async ({
  page,
}) => {
  await installPlatformApi(page, {
    operator: null,
    replies: { "/platform/auth/login": [refuse(401, "INVALID_CREDENTIALS")] },
  });
  await page.goto(PLATFORM);

  await page.getByLabel("אימייל").fill("dana@modryn.example");
  await page.getByLabel("סיסמה").fill("wrong");
  await page.getByRole("button", { name: "כניסה" }).click();

  const alert = page.getByRole("alert");
  await expect(alert).toHaveText("האימייל או הסיסמה אינם נכונים.");
  // ⚠ THE COPY REGISTER, mechanically. Every backend message is English, so a UI
  // that painted the server's sentence onto a Hebrew-only screen would pass every
  // layout check and every axe run.
  const message = await alert.innerText();
  expect(message, "an English server message reached the page").not.toMatch(/[A-Za-z]{4,}/);
  // #5, program-wide.
  expect(message).not.toContain("!");
});

test("platform: a spent budget says wait, not wrong password", async ({ page }) => {
  // Two different instructions. Collapsing them would tell an operator her
  // password is wrong when it is not, at the moment she can least afford to
  // start guessing.
  await installPlatformApi(page, {
    operator: null,
    replies: { "/platform/auth/login": [refuse(429, "TOO_MANY_ATTEMPTS")] },
  });
  await page.goto(PLATFORM);
  await page.getByLabel("אימייל").fill("dana@modryn.example");
  await page.getByLabel("סיסמה").fill("wrong");
  await page.getByRole("button", { name: "כניסה" }).click();
  await expect(page.getByRole("alert")).toHaveText(
    "יותר מדי ניסיונות כניסה. אפשר לנסות שוב בעוד מספר דקות.",
  );
});

test("platform: a good password reaches the tenant table", async ({ page }) => {
  await installPlatformApi(page, {
    operator: null,
    tenants: [BELLA, NOA],
    replies: {
      "/platform/auth/login": [ok(operator())],
      // The app refetches `me` only through a fresh mount; the login response IS
      // the identity, so the second `me` is never issued. Stubbed anyway so a
      // future bootstrap change fails on an assertion rather than on a 404.
      "/platform/auth/me": [refuse(401, "NOT_AUTHENTICATED"), ok(operator())],
    },
  });
  await page.goto(PLATFORM);
  await page.getByLabel("אימייל").fill("dana@modryn.example");
  await page.getByLabel("סיסמה").fill("right");
  await page.getByRole("button", { name: "כניסה" }).click();

  await expect(page.getByRole("heading", { name: "ניהול הפלטפורמה", level: 1 })).toBeVisible();
  await expect(page.getByRole("cell", { name: "בלה כלות" })).toBeVisible();
});

test("platform: logout returns to the login panel", async ({ page }) => {
  await installPlatformApi(page, {
    tenants: [BELLA],
    replies: { "/platform/auth/logout": [ok({ ok: true })] },
  });
  await page.goto(PLATFORM);
  await page.getByRole("button", { name: "יציאה" }).click();
  await expect(page.getByRole("button", { name: "כניסה" })).toBeVisible();
  // ⚠ SCOPED TO THE BANNER, and that is the whole assertion. Both screens carry
  // an h1 whose accessible name contains «ניהול הפלטפורמה» — the console's is
  // exactly that, the login lockup's sr-only span is «MODRYN — ניהול
  // הפלטפורמה» — and Playwright matches `name` as a SUBSTRING, so an unscoped
  // heading locator finds the LOGIN heading and reports the console as still
  // mounted. It never was: App.tsx renders LoginPanel or Console, never both.
  //
  // The console's h1 lives in the only <header> in the app (banner) and the
  // login's in the only <main>, so the landmark is what actually separates the
  // two screens. `.first()` would have "fixed" this by coin flip.
  await expect(
    page.getByRole("banner").getByRole("heading", { name: "ניהול הפלטפורמה", level: 1 }),
  ).toBeHidden();
});

// --- provision ---------------------------------------------------------------

async function fillProvision(page: Page, slug: string): Promise<void> {
  await page.getByLabel("כתובת (תת־דומיין)").fill(slug);
  await page.getByLabel("שם הבוטיק").fill("בוטיק של חן");
  await page.getByLabel("אימייל של בעלת הבוטיק").fill("owner@chen.example");
  await page.getByLabel("סיסמה ראשונית").fill("first-owner-pw");
}

test("platform: provisioning appends the row and clears the password", async ({ page }) => {
  // ONE install, before the navigation. Playwright resolves routes LIFO, so a
  // second `installPlatformApi` on the same page would shadow the first — and
  // the first recorder would then miss exactly the calls the assertion below
  // counts.
  const recorder = await installPlatformApi(page, {
    tenants: [BELLA],
    replies: { "/platform/tenants/provision": [ok({ ok: true })] },
  });
  await page.goto(PLATFORM);
  await expect(page.getByRole("heading", { name: "ניהול הפלטפורמה", level: 1 })).toBeVisible();

  await fillProvision(page, "chen");
  await page.getByRole("button", { name: "הקמת בוטיק" }).click();

  await expect(page.getByRole("cell", { name: "בוטיק של חן" })).toBeVisible();
  await expect(page.getByRole("status")).toContainText("הבוטיק הוקם");
  // The console holds no lasting secret: the field is emptied and the done-line
  // never repeats what was typed.
  await expect(page.getByLabel("סיסמה ראשונית")).toHaveValue("");
  await expect(page.getByRole("status")).not.toContainText("first-owner-pw");
  // ⚠ ONE list GET FOR THE WHOLE JOURNEY. Every one writes a TENANTS_LISTED row
  // into the platform's audit book, so a refetch-after-mutation would be visible
  // here as a second call.
  expect(recorder.of("/platform/tenants").filter((r) => r.method === "GET")).toHaveLength(1);
});

test("platform: a taken slug gets its own sentence and keeps the typed values", async ({
  page,
}) => {
  await installPlatformApi(page, {
    tenants: [BELLA],
    replies: { "/platform/tenants/provision": [refuse(409, "slug_taken")] },
  });
  await page.goto(PLATFORM);
  await expect(page.getByRole("heading", { name: "ניהול הפלטפורמה", level: 1 })).toBeVisible();

  await fillProvision(page, "chen");
  await page.getByRole("button", { name: "הקמת בוטיק" }).click();

  await expect(page.getByRole("alert")).toHaveText("הכתובת הזו כבר תפוסה.");
  await expect(page.getByLabel("שם הבוטיק")).toHaveValue("בוטיק של חן");
});

test("platform: a reserved slug is refused client-side before any request", async ({ page }) => {
  const recorder = await signedIn(page, [BELLA]);
  await fillProvision(page, "admin");
  await expect(page.getByText("הכתובת הזו שמורה למערכת ואינה זמינה.")).toBeVisible();
  await page.getByRole("button", { name: "הקמת בוטיק" }).click();
  expect(recorder.of("/platform/tenants/provision")).toHaveLength(0);
});

// --- row actions -------------------------------------------------------------

test("platform: the suspend dialog is red on the final confirm only, and flips the row", async ({
  page,
}) => {
  await installPlatformApi(page, {
    tenants: [BELLA, NOA],
    replies: { "/platform/tenants/suspend": [ok({ ok: true })] },
  });
  await page.goto(PLATFORM);
  const row = page.getByRole("row", { name: /בלה כלות/ });
  const trigger = row.getByRole("button", { name: "השהיה" });

  // ⚠ THE DECLARED DEVIATION, asserted rather than described: the row trigger is
  // PLAIN. StaffSection and DressEditor put `danger` on the trigger too; at 50+
  // rows that is a column of red buttons and the salience red exists for is
  // gone. This is a table-density exception, not the house pattern.
  await expect(trigger).not.toHaveClass(/bg-danger/);
  await trigger.click();

  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("button", { name: "השהיה" })).toHaveClass(/bg-danger/);
  // The body states BOTH facts that make the tap informed.
  await expect(dialog).toContainText("מיד");
  await expect(dialog).toContainText("אין בקונסולה פעולת הפעלה מחדש");

  await dialog.getByRole("button", { name: "השהיה" }).click();
  await expect(page.getByRole("dialog")).toBeHidden();
  await expect(row.getByText("מושהה")).toBeVisible();
  // A suspended row loses its suspend action — there is no un-suspend here.
  await expect(row.getByRole("button", { name: "השהיה" })).toHaveCount(0);
});

test("platform: Esc closes the suspend dialog without suspending", async ({ page }) => {
  const recorder = await signedIn(page, [BELLA]);
  await page.getByRole("row", { name: /בלה כלות/ }).getByRole("button", { name: "השהיה" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toBeHidden();
  expect(recorder.of("/platform/tenants/suspend")).toHaveLength(0);
});

test("platform: the modal traps focus and restores it to the trigger", async ({ page }) => {
  // ⚠ THE CLAIM THAT ONLY A REAL BROWSER CAN MAKE. jsdom's `<dialog>` stub in
  // src/test/setup.ts sets `open = true` and nothing else — no top layer, no
  // trap, no restore — so the vitest suite deliberately asserts none of this.
  await signedIn(page, [BELLA]);
  const trigger = page
    .getByRole("row", { name: /בלה כלות/ })
    .getByRole("button", { name: "השהיה" });
  await trigger.click();

  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();

  // Opening moves focus INTO the dialog and off the trigger — `showModal()`'s
  // first job, and the one the jsdom stub skips entirely.
  await expect(dialog.locator(":focus")).toHaveCount(1);
  await expect(trigger).not.toBeFocused();

  // ⚠ TWO presses per direction, and the middle stop is CHROMIUM's, not a wart
  // in the test: tabbing off the end of a top layer parks on the DOCUMENT before
  // wrapping. `dialog-focus.spec.ts` — the shipped manage suite, with mutation
  // proofs — measures every dialog in this workspace exactly this way, and the
  // `activeElement === body` assertion in between is the load-bearing one: the
  // screen behind is inert, so the press landed on NOTHING rather than on a
  // control out there. An ancestry probe (`activeElement.closest("dialog")`)
  // reads that legitimate park as an escape and reds a dialog that traps
  // correctly, which is what this test used to do.
  const first = dialog.getByRole("button", { name: "ביטול" });
  const last = dialog.getByRole("button", { name: "השהיה" });
  const onNothing = () => page.evaluate(() => document.activeElement === document.body);

  await last.focus();
  await page.keyboard.press("Tab");
  expect(await onNothing()).toBe(true);
  await page.keyboard.press("Tab");
  await expect(first).toBeFocused();

  await first.focus();
  await page.keyboard.press("Shift+Tab");
  expect(await onNothing()).toBe(true);
  await page.keyboard.press("Shift+Tab");
  await expect(last).toBeFocused();

  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(trigger).toBeFocused();
});

test("platform: the reset dialog keeps its values on a refusal and repeats no password", async ({
  page,
}) => {
  await installPlatformApi(page, {
    tenants: [BELLA],
    replies: {
      "/platform/tenants/reset-owner-password": [
        refuse(404, "owner_not_found"),
        ok({ ok: true }),
      ],
    },
  });
  await page.goto(PLATFORM);
  await page
    .getByRole("row", { name: /בלה כלות/ })
    .getByRole("button", { name: "איפוס סיסמת בעלים" })
    .click();

  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("אימייל של בעלת הבוטיק").fill("wrong@bella.example");
  await dialog.getByLabel("סיסמה חדשה").fill("a-new-owner-pw");
  await dialog.getByRole("button", { name: "איפוס סיסמה" }).click();

  await expect(dialog.getByRole("alert")).toHaveText("האימייל אינו תואם את בעלת הבוטיק הרשומה.");
  await expect(dialog.getByLabel("סיסמה חדשה")).toHaveValue("a-new-owner-pw");

  await dialog.getByLabel("אימייל של בעלת הבוטיק").fill("owner@bella.example");
  await dialog.getByRole("button", { name: "איפוס סיסמה" }).click();
  await expect(page.getByRole("dialog")).toBeHidden();
  const done = page.getByRole("status");
  await expect(done).toContainText("הסיסמה אופסה");
  await expect(done).not.toContainText("a-new-owner-pw");
});

// --- RTL and the axe gate ----------------------------------------------------

test("platform: the document is Hebrew and RTL", async ({ page }) => {
  await installPlatformApi(page, { operator: null });
  await page.goto(PLATFORM);
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.locator("html")).toHaveAttribute("lang", "he");
  await expect(page).toHaveTitle(/[֐-׿]/);
});

test("platform: the slug renders LTR inside the RTL table", async ({ page }) => {
  // A Latin run inside RTL text without isolation reorders on screen. The NAME
  // gets a bare <bdi> and never dir="ltr" — a Hebrew boutique name forced LTR is
  // the BookPage lesson.
  await signedIn(page, [BELLA]);
  const slug = page.locator("bdi[dir='ltr']", { hasText: "bella" });
  await expect(slug).toBeVisible();
});

test("platform (axe): the login screen, including its error state", async ({ page }) => {
  await installPlatformApi(page, {
    operator: null,
    replies: { "/platform/auth/login": [refuse(401, "INVALID_CREDENTIALS")] },
  });
  await page.goto(PLATFORM);
  await axeClean(page, "login");

  await page.getByLabel("אימייל").fill("dana@modryn.example");
  await page.getByLabel("סיסמה").fill("wrong");
  await page.getByRole("button", { name: "כניסה" }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await axeClean(page, "login error");
});

test("platform (axe): the populated table", async ({ page }) => {
  await signedIn(page, [BELLA, NOA, tenant({ slug: "ruth", name: "רות", status: "suspended" })]);
  await axeClean(page, "table");
});

test("platform (axe): the empty platform", async ({ page }) => {
  await installPlatformApi(page, { tenants: [] });
  await page.goto(PLATFORM);
  await expect(page.getByText("אין עדיין בוטיקים במערכת. אפשר להקים את הראשון בטופס שלמטה.")).toBeVisible();
  await axeClean(page, "empty");
});

test("platform (axe): a filter that matches nothing", async ({ page }) => {
  await signedIn(page, [BELLA, NOA]);
  await page.getByLabel("סינון לפי שם או כתובת").fill("zzz");
  await expect(page.getByText("אף בוטיק אינו תואם את הסינון.")).toBeVisible();
  await axeClean(page, "filter no match");
});

test("platform (axe): the provision form, including its invalid-slug state", async ({ page }) => {
  await signedIn(page, [BELLA]);
  await axeClean(page, "provision form");
  await page.getByLabel("כתובת (תת־דומיין)").fill("Not A Slug");
  await expect(page.getByText("הכתובת יכולה להכיל אותיות לטיניות קטנות, ספרות ומקפים בלבד.")).toBeVisible();
  await axeClean(page, "provision form invalid");
});

test("platform (axe): the suspend dialog", async ({ page }) => {
  await signedIn(page, [BELLA]);
  await page.getByRole("row", { name: /בלה כלות/ }).getByRole("button", { name: "השהיה" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await axeClean(page, "suspend dialog");
});

test("platform (axe): the reset dialog", async ({ page }) => {
  await signedIn(page, [BELLA]);
  await page
    .getByRole("row", { name: /בלה כלות/ })
    .getByRole("button", { name: "איפוס סיסמת בעלים" })
    .click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await axeClean(page, "reset dialog");
});

// --- F26: invites, the one-time link, and revoke ------------------------------
//
// ⚠ THE FOCUS-RESTORE AND FOCUS-TRAP CLAIMS FOR THE REVOKE MODAL LIVE HERE, for
// the reason stated at the top of this file: jsdom has no real `<dialog>` and
// `src/test/setup.ts` stubs `showModal()`, so a vitest assertion about trapped
// focus proves the stub (`.memory/jsdom-has-no-dialog`).

const INVITE_CODE = "s3cret-invite-code-value";
const CREATED = {
  code: INVITE_CODE,
  join_url: `https://admin.modryn.co.il/platform/join?code=${INVITE_CODE}`,
  invite: invite(),
};

async function signedInWithInvites(page: Page, invites: Invite[] = []): Promise<Recorder> {
  const recorder = await installPlatformApi(page, { tenants: [BELLA], invites });
  await page.goto(PLATFORM);
  await expect(page.getByRole("heading", { name: "ניהול הפלטפורמה", level: 1 })).toBeVisible();
  return recorder;
}

async function createOne(page: Page): Promise<void> {
  const form = page.getByRole("form", { name: "הזמנה חדשה" });
  await form.getByLabel("כתובת (תת־דומיין)").fill("chen");
  await form.getByLabel("שם הבוטיק").fill("בוטיק של חן");
  await form.getByLabel("אימייל של בעלת הבוטיק").fill("chen@x.example");
  await form.getByRole("button", { name: "יצירת הזמנה" }).click();
}

test("platform: the link is shown once, copied, and gone after dismiss", async ({
  page,
  context,
}) => {
  // The whole point of A2: after the dismiss there is no path back to the code —
  // not in the DOM, not in the table, not in storage.
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await installPlatformApi(page, {
    tenants: [BELLA],
    invites: [],
    replies: { "POST /platform/invites": [ok(CREATED)] },
  });
  await page.goto(PLATFORM);
  await expect(page.getByRole("heading", { name: "ניהול הפלטפורמה", level: 1 })).toBeVisible();

  await createOne(page);
  await expect(page.getByRole("heading", { name: "ההזמנה נוצרה", level: 3 })).toBeVisible();
  // The create form is NOT rendered while the panel is open (A2 r3).
  await expect(page.getByRole("form", { name: "הזמנה חדשה" })).toHaveCount(0);

  const link = page.getByLabel("קישור ההזמנה");
  await expect(link).toHaveValue(CREATED.join_url);
  await expect(link).toHaveAttribute("readonly", "");

  await page.getByRole("button", { name: "העתקת הקישור" }).click();
  await expect(page.getByRole("status")).toContainText("הקישור הועתק.");
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(CREATED.join_url);

  await page.getByRole("button", { name: "שמרתי את הקישור — סגירה" }).click();
  await expect(page.getByRole("form", { name: "הזמנה חדשה" })).toBeVisible();
  expect(await page.content()).not.toContain(INVITE_CODE);
  expect(
    await page.evaluate(() => [window.sessionStorage.length, window.localStorage.length]),
  ).toEqual([0, 0]);
  // Focus moved to the field she types into next, not to the top of the page.
  await expect(page.getByRole("form", { name: "הזמנה חדשה" }).getByLabel("כתובת (תת־דומיין)")).toBeFocused();
});

test("platform: the invites table renders no code column and only open rows can be revoked", async ({
  page,
}) => {
  await signedInWithInvites(page, [
    invite(),
    invite({ id: "22222222-2222-4222-8222-222222222222", slug: "noa", name: "נועה", redeemed_at: "2026-08-07T10:00:00Z" }),
    invite({ id: "33333333-3333-4333-8333-333333333333", slug: "gal", name: "גל", expires_at: "2020-01-01T09:00:00Z" }),
  ]);
  const table = page.getByRole("table", { name: /רשימת ההזמנות/ });
  await expect(table.getByText("פתוחה")).toBeVisible();
  await expect(table.getByText("נוצלה")).toBeVisible();
  await expect(table.getByText("פג תוקף")).toBeVisible();
  await expect(table.getByRole("columnheader")).toHaveCount(6);
  await expect(table.getByRole("button", { name: "ביטול ההזמנה" })).toHaveCount(1);
  // The Latin runs are isolated; the Hebrew boutique name is NOT forced LTR.
  await expect(page.locator("bdi[dir='ltr']", { hasText: "chen@x.example" })).toBeVisible();
});

test("platform: the revoke dialog traps focus, restores it, and reds only the confirm", async ({
  page,
}) => {
  const recorder = await signedInWithInvites(page, [invite()]);
  const trigger = page.getByRole("row", { name: /בוטיק של חן/ }).getByRole("button", {
    name: "ביטול ההזמנה",
  });
  await trigger.click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();

  // Trapped: tabbing round the dialog never lands outside it. Evaluated in ONE
  // page call so the check reads `document.activeElement` in the same frame the
  // browser just moved it — a handle round-trip would sample it a tick late.
  for (let step = 0; step < 8; step += 1) {
    await page.keyboard.press("Tab");
    const inside = await page.evaluate(() => {
      const open = document.querySelector("dialog[open]");
      return open !== null && open.contains(document.activeElement);
    });
    expect(inside, `focus escaped the revoke dialog after ${step + 1} tabs`).toBe(true);
  }

  const cancel = dialog.getByRole("button", { name: "חזרה" });
  const confirm = dialog.getByRole("button", { name: "ביטול ההזמנה" });
  await expect(cancel).toBeVisible();
  await expect(confirm).toHaveClass(/bg-danger/);
  await expect(cancel).not.toHaveClass(/bg-danger/);

  await cancel.click();
  await expect(dialog).toBeHidden();
  // Restored to the row trigger, not dropped at the document top.
  await expect(trigger).toBeFocused();

  await trigger.click();
  await page.getByRole("dialog").getByRole("button", { name: "ביטול ההזמנה" }).click();
  await expect(page.getByText("בוטיק של חן")).toHaveCount(0);
  // Patched locally: exactly ONE list GET for the whole journey.
  expect(recorder.of("/platform/invites").filter((r) => r.method === "GET")).toHaveLength(1);
});

test("platform (axe): the invites table, the create form, the link panel and the revoke dialog", async ({
  page,
}) => {
  await installPlatformApi(page, {
    tenants: [BELLA],
    invites: [invite()],
    replies: { "POST /platform/invites": [ok(CREATED)] },
  });
  await page.goto(PLATFORM);
  await expect(page.getByRole("table", { name: /רשימת ההזמנות/ })).toBeVisible();
  await axeClean(page, "invites table and create form");

  await page.getByRole("row", { name: /בוטיק של חן/ }).getByRole("button", { name: "ביטול ההזמנה" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await axeClean(page, "revoke dialog");
  await page.getByRole("dialog").getByRole("button", { name: "חזרה" }).click();
  await expect(page.getByRole("dialog")).toBeHidden();

  await createOne(page);
  await expect(page.getByRole("heading", { name: "ההזמנה נוצרה", level: 3 })).toBeVisible();
  await axeClean(page, "one-time link panel");
});

test("platform: the invites surface carries no exclamation mark", async ({ page }) => {
  // The shipped register rule (#5), asserted on RENDERED text rather than only
  // in the bundle — a string assembled at runtime would pass the i18n guard.
  await installPlatformApi(page, {
    tenants: [BELLA],
    invites: [invite()],
    replies: { "POST /platform/invites": [ok(CREATED)] },
  });
  await page.goto(PLATFORM);
  await createOne(page);
  await expect(page.getByRole("heading", { name: "ההזמנה נוצרה", level: 3 })).toBeVisible();
  expect(await page.locator("body").innerText()).not.toContain("!");
});
