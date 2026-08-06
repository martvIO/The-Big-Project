import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import {
  PLATFORM,
  installPlatformApi,
  ok,
  operator,
  refuse,
  tenant,
} from "./fixtures/platform";
import type { Recorder, Tenant } from "./fixtures/platform";

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
  await expect(page.getByRole("heading", { name: "ניהול הפלטפורמה", level: 1 })).toBeHidden();
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
  // Focus is inside the dialog after showModal(), and Tab cannot leave it. The
  // assertion is on ANCESTRY, not on text: an element with no text content would
  // make a `toContainText` check pass vacuously, which is the failure mode this
  // whole test exists to rule out.
  for (let i = 0; i < 6; i += 1) {
    await page.keyboard.press("Tab");
    const trapped = await page.evaluate(
      () => document.activeElement?.closest("dialog") !== null,
    );
    expect(trapped, `Tab #${i + 1} escaped the dialog`).toBe(true);
  }
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
