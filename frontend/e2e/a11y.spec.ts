import { test, expect } from "@playwright/test";
import type { Locator, Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import {
  PHOTO_CONFIRMED_AT,
  PHOTO_DATA_URI,
  installManageApi,
  installStorageUpload,
  ok,
  settleAnimations,
  staff,
  staffList,
  staffPath,
  staffPresign,
} from "./fixtures/manage";

const STOREFRONT = "http://localhost:4173";
// Trailing /manage/ because apps/manage builds with base: "/manage/" — `vite
// preview` serves it there, mirroring the API mount at {slug}.{domain}/manage.
const MANAGE = "http://localhost:4174/manage/";

// Nothing here intercepts the API, and that is the point. `vite preview` proxies
// /storefront/* to :8000, where either nothing is listening or a backend that has
// never heard of `localhost` answers 404 TENANT_NOT_FOUND. Both are the same
// thing to the visitor: the boutique's data never arrives. These are the
// no-data pass — the storefront still has to be a valid, navigable, accessible
// document. storefront.spec.ts covers the same routes with data behind them.
//
// Which of the two failures happens depends on the machine, so nothing below
// pins the exact sentence; the Hebrew-only assertion in its own test is what
// pins the copy.
async function gotoCatalogWithNoData(page: Page) {
  await page.goto(STOREFRONT);
  // Wait for the failure to land, so nothing below measures a skeleton.
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page.getByRole("button", { name: "נסי שוב" })).toBeVisible();
}

test("storefront (no data): zero axe A/AA violations", async ({ page }) => {
  await gotoCatalogWithNoData(page);
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(results.violations).toEqual([]);
});

// Every message the backend can return is English — "No active boutique at this
// address.", "Resource not found.", "Too many attempts. Try again later." — so
// the failure copy is selected by the error CODE and rendered from the Hebrew
// bundle. Painting the server's sentence onto a Hebrew-only page is the failure
// mode, and it is invisible to axe and to every layout check in this file.
test("storefront (no data): the failure is Hebrew, never the server's English message", async ({
  page,
}) => {
  await gotoCatalogWithNoData(page);
  const message = await page.getByRole("alert").innerText();
  expect(message, "the alert is empty").toMatch(/[֐-׿]/);
  expect(message, "an English server message reached the page").not.toMatch(/[A-Za-z]{4,}/);
});

test("storefront: Hebrew document title + cream color-scheme (no forced dark)", async ({ page }) => {
  await page.goto(STOREFRONT);
  await expect(page).toHaveTitle(/[֐-׿]/); // contains Hebrew
  // F30: MODRYN brands the platform, not the tenant. The storefront is the
  // boutique's own shop front — the only platform mark it may carry is the
  // favicon. A MODRYN in the title here is the regression this pins.
  await expect(page).not.toHaveTitle(/MODRYN/i);
  const scheme = await page.evaluate(() => getComputedStyle(document.documentElement).colorScheme);
  expect(scheme.trim()).toContain("light");
});

// WCAG 1.4.4: pinch zoom is the resize mechanism on a phone, and a viewport meta
// that disables it takes 200% text away from the visitor who most needs it. Both
// apps, because the two index.html files are edited independently.
test("neither app's index.html disables pinch zoom", async ({ page }) => {
  for (const [name, url] of [
    ["storefront", STOREFRONT],
    ["manage", MANAGE],
  ]) {
    await page.goto(url);
    const content = await page.locator('meta[name="viewport"]').getAttribute("content");
    expect(content, `${name} has no viewport meta`).not.toBeNull();
    expect(content, `${name} viewport meta blocks zoom`).not.toMatch(/user-scalable\s*=\s*(no|0)/i);
    // maximum-scale=1 blocks it just as completely, and reads as harmless.
    expect(content, `${name} viewport meta caps zoom`).not.toMatch(/maximum-scale\s*=\s*1(\.0)?\b/i);
  }
});

test("storefront: the Hebrew woff2 subset is actually fetched (not only Latin)", async ({ page }) => {
  const woff2: string[] = [];
  page.on("requestfinished", (r) => {
    if (r.url().includes(".woff2")) woff2.push(r.url());
  });
  await page.goto(STOREFRONT);
  // font-display: swap fetches the subset asynchronously — wait for the font
  // engine to settle before asserting.
  await page.evaluate(() => document.fonts.ready);
  await page.waitForLoadState("networkidle");
  expect(woff2.some((u) => /hebrew/i.test(u)), `woff2 requested: ${woff2.join(", ")}`).toBe(true);
});

test("storefront (no data): no horizontal scroll at 375 / 768 / 1440", async ({ page }) => {
  for (const width of [375, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await gotoCatalogWithNoData(page);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
    );
    expect(overflow, `horizontal scroll at ${width}px`).toBe(false);
  }
});

test("storefront (no data): keeps the skip link and honours reduced motion", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await gotoCatalogWithNoData(page);

  // The skip link is the first focusable element on every page including this
  // one, and #content is still a real, focusable region — an outage costs the
  // page its collection, never its keyboard entry point.
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "דלג לתוכן" })).toBeFocused();
  await page.keyboard.press("Enter");
  expect(
    await page.evaluate(() => ({
      tag: document.activeElement?.tagName ?? "",
      id: document.activeElement?.id ?? "",
    })),
  ).toEqual({ tag: "MAIN", id: "content" });

  // Measured on the retry Button, the only element in this state that declares a
  // transition at all. The previous assertion read
  // `["0s", "0.001ms", ""].some(v => duration.includes(v))` — every string
  // contains "", so it could not fail; it passed on the h1, which has no
  // transition to disable.
  const motion = await page.getByRole("button", { name: "נסי שוב" }).evaluate((el) => {
    const style = getComputedStyle(el);
    return { transitionDuration: style.transitionDuration, animationName: style.animationName };
  });
  expect(motion).toEqual({ transitionDuration: "0s", animationName: "none" });
});

test("manage: login screen has zero axe A/AA violations + Hebrew title", async ({ page }) => {
  await page.goto(MANAGE);
  await expect(page).toHaveTitle(/[֐-׿]/);
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(results.violations).toEqual([]);
});

// F30: the console IS the platform, so it carries the brand — in the title and
// as the login lockup. The lockup is the h1: the mark is decorative (alt="")
// and the Latin wordmark aria-hidden, so the accessible name is the Hebrew
// sentence and neither "MODRYN" is announced twice.
test("manage: login screen is MODRYN-branded and still has exactly one h1", async ({ page }) => {
  await page.goto(MANAGE);
  await expect(page).toHaveTitle(/^MODRYN — /);
  const h1 = page.getByRole("heading", { level: 1 });
  await expect(h1).toHaveCount(1);
  await expect(h1).toHaveAccessibleName(/^MODRYN — .*[֐-׿]/);
  await expect(page.getByText("MODRYN", { exact: true })).toBeVisible();
});

// F33 shipped a print stylesheet in apps/manage/src/index.css, and index.css is
// imported unconditionally by main.tsx. `.print-sheet` exists in exactly one
// component (CheckinQrSection), so an ungated `body * { visibility: hidden }`
// blanks the PAPER on every other console screen while leaving the layout — and
// therefore the page count — intact: an owner printing the day's bookings gets
// the right number of empty sheets.
//
// Only a real browser can see this. jsdom applies no stylesheet, so the unit
// suite can assert nothing beyond the presence of the class, and no assertion
// about a print dialog is possible either. `emulateMedia` is the mechanism that
// makes the @media block live without one.
//
// The login screen is the console screen this suite can reach unauthenticated,
// and it carries no .print-sheet — which is exactly the case that regressed.
test("manage: printing a screen with no print sheet does not blank the page", async ({ page }) => {
  await page.goto(MANAGE);
  const submit = page.getByRole("button", { name: "כניסה" });
  await expect(submit).toBeVisible();

  await page.emulateMedia({ media: "print" });
  // toBeVisible() fails on `visibility: hidden`, which is the whole defect —
  // the element keeps its box and stops being painted.
  await expect(submit, "the print stylesheet hid a screen that owns no sheet").toBeVisible();
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
});

// --- F38: the staff directory's five photo states ----------------------------
//
// `.planning/design/screens/hr-directory/design.md` §accessibility names these
// five by name — list with photos, list without, edit panel mid-upload, both
// modals, RTL — and calls the gate LEGAL (IS 5568 / WCAG 2.0 AA). Zero is the
// only passing number, so nothing below carries a `.disableRules()` or an
// `.exclude()`: if one of these reds, the markup is wrong and the component is
// what changes.
//
// ⚠ **THEY LIVE HERE RATHER THAN IN `StaffSection.test.tsx`, WHICH ALREADY RUNS
// axe, BECAUSE jsdom APPLIES NO STYLESHEET AND axe THEREFORE SKIPS
// `color-contrast` ENTIRELY THERE.** Every colour decision this feature makes is
// invisible to that suite: the initial-letter fallback (`--color-ink-muted` on
// `--color-surface`), the muted eligibility word, the danger «הסרת תמונה», the
// retention paragraph and the two dialog bodies on `--color-surface-raised`.
//
// ⚠ **AND THE TWO CONFIRMS ARE NOT REALLY DIALOGS THERE.** `setup.ts` stubs
// `showModal()`, so jsdom's «open» modal is an ordinary element with no top
// layer and no `inert` siblings — a scan of it is a scan of a different DOM.

const STAFF_NAV = "צוות";
const DASHBOARD_HEADING = "סקירה";
const PHOTO_REPLACE_LABEL = "החלפת תמונת פרופיל";
const PHOTO_UPLOADING = "מעלה…";
// REPLACED and not «נוספה»: the row this block edits already carries a photo,
// which is what makes «הסרת תמונה» — and therefore the photo-remove modal —
// reachable at all. The two terminal strings are different keys, and picking
// the wrong one here would have made state ② unreachable.
const PHOTO_REPLACED = "התמונה הוחלפה.";
const PHOTO_REMOVE_CTA = "הסרת תמונה";
const PHOTO_REMOVE_TITLE = "להסיר את התמונה?";
const OFFBOARD_TITLE = "לסיים את ההעסקה?";
const STAFF_CANCEL = "ביטול";

const RONIT = "רונית";
const DANA = "דנה כהן";
const offboardAria = (name: string) => `סיום העסקה — ${name}`;
const editAria = (name: string) => `עריכה — ${name}`;

const OWNER = staff({ role: "owner", display_name: RONIT });

// ≥ MIN_UPLOAD_BYTES (1024), or `validateStaffPhotoFile` refuses it client-side
// and the upload phase this file needs to scan never begins.
const PHOTO_FILE = { name: "photo.png", mimeType: "image/png", buffer: Buffer.alloc(2048, 7) };

const rows = () => staffList() as Record<string, unknown>[];
const withPhotos = () =>
  rows().map((row) => ({
    ...row,
    photo_url: PHOTO_DATA_URI,
    photo_confirmed_at: PHOTO_CONFIRMED_AT,
  }));
const withoutPhotos = () =>
  rows().map((row) => ({ ...row, photo_url: null, photo_confirmed_at: null }));

async function staffAxeViolations(page: Page): Promise<string[]> {
  // ⚠ SETTLE BOUNDED ANIMATIONS BEFORE SCANNING — see `settleAnimations`. The
  // two confirms below are `Modal`s, which fade AND scale their panel on open,
  // and `toBeVisible()` resolves when the panel paints rather than when the
  // transition ends. Scanning there makes axe composite a half-faded layer and
  // report a contrast the page never renders at rest.
  await settleAnimations(page);
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  // The raw violation objects dump ~10 KB of axe internals into the failure;
  // only the rule id and the offending selectors say anything useful.
  return results.violations.map(
    (v) => `${v.id} — ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`,
  );
}

async function openStaffSection(page: Page): Promise<void> {
  await page.goto(MANAGE);
  await expect(page.getByRole("heading", { level: 2, name: DASHBOARD_HEADING })).toBeVisible();
  await page.getByRole("navigation").getByRole("button", { name: STAFF_NAV, exact: true }).click();
  // The per-row offboard control, which only a POPULATED list renders and only
  // on a row that is not the signed-in staffer. A scan taken over the skeleton —
  // `aria-hidden`, no text — would pass while proving nothing.
  await expect(page.getByRole("button", { name: offboardAria(DANA) })).toBeVisible();
}

// The open edit panel, identified by the one control only it can contain. Its
// text inputs hold their values as PROPERTIES, so `hasText` cannot find it.
function editPanel(page: Page): Locator {
  return page
    .getByRole("main")
    .getByRole("listitem")
    .filter({ has: page.locator('input[type="file"]') });
}

for (const [label, list] of [
  ["with photos on every row", withPhotos],
  ["with no photo anywhere", withoutPhotos],
] as const) {
  test(`manage staff: zero axe A/AA violations on a list ${label}`, async ({ page }) => {
    await installManageApi(page, {
      staff: OWNER,
      replies: { "/manage/staff": [ok(list())] },
    });
    await openStaffSection(page);

    // Makes «all RTL» a claim rather than an assumption: every scan in this
    // block is taken on a document whose direction is the product's own, and a
    // build that lost `dir` on <html> would otherwise pass all of them.
    expect(await page.evaluate(() => document.documentElement.dir)).toBe("rtl");

    expect(await staffAxeViolations(page)).toEqual([]);
  });
}

test("manage staff: zero axe A/AA violations mid-upload and with either confirm open", async ({
  page,
}) => {
  // Three states on ONE navigation: each needs the same page, and a fresh
  // navigation per state would triple the run for no more coverage.
  let release = () => {};
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  await installManageApi(page, {
    staff: OWNER,
    replies: {
      "/manage/staff": [ok(withPhotos())],
      [`${staffPath(OWNER.id)}/photo/presign`]: [ok(staffPresign())],
      [`${staffPath(OWNER.id)}/photo/confirm`]: [ok(withPhotos()[0])],
    },
  });
  await installStorageUpload(page, { hold: held });

  await openStaffSection(page);
  await page.getByRole("button", { name: editAria(RONIT) }).click();

  // ① MID-UPLOAD. The phase lasts exactly as long as the storage POST does,
  // which is why the fixture holds it: the disabled file input, its two
  // description lines and the live «מעלה…» region are only on screen here.
  await page.getByLabel(PHOTO_REPLACE_LABEL).setInputFiles(PHOTO_FILE);
  await expect(page.getByRole("main").getByRole("status")).toHaveText(PHOTO_UPLOADING);
  await expect(page.getByLabel(PHOTO_REPLACE_LABEL)).toBeDisabled();
  expect(await staffAxeViolations(page)).toEqual([]);

  release();
  await expect(page.getByRole("main").getByRole("status")).toHaveText(PHOTO_REPLACED);

  // ② THE PHOTO-REMOVE CONFIRM — a real <dialog> in the top layer, with its
  // danger footer button on a raised surface.
  await page.getByRole("button", { name: PHOTO_REMOVE_CTA }).click();
  await expect(page.getByRole("dialog").getByRole("heading", { name: PHOTO_REMOVE_TITLE })).toBeVisible();
  expect(await staffAxeViolations(page)).toEqual([]);

  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toBeHidden();
  await editPanel(page).getByRole("button", { name: STAFF_CANCEL }).click();

  // ③ THE OFFBOARD CONFIRM — the same one <Modal>, second body (design R3): a
  // <Trans> paragraph with a bare <bdi>, a labelled date field with its own
  // help line, and the retention paragraph in the muted register.
  await page.getByRole("button", { name: offboardAria(DANA) }).click();
  await expect(page.getByRole("dialog").getByRole("heading", { name: OFFBOARD_TITLE })).toBeVisible();
  expect(await staffAxeViolations(page)).toEqual([]);
});
