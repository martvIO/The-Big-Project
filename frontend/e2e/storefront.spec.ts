import { test, expect } from "@playwright/test";
import type { Locator, Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

// The storefront under `vite preview` has no backend behind it — every
// /storefront/* GET is proxied at :8000 and refused, so each page falls into its
// error state. These specs therefore fulfil the three public endpoints from a
// fixture, which is what makes the *real* screens testable: the grid, the
// gallery, the hours card and the CTA bar only exist once data lands.
//
// a11y.spec.ts deliberately does NOT intercept — those five keep their value as
// the API-is-down pass.

const STOREFRONT = "http://localhost:4173";

// --- fixture -----------------------------------------------------------------

// A 3:4 SVG rather than a presigned S3 URL: it renders, it decodes, and — the
// point — it cannot 404, so the onError-means-refetch path stays out of the way
// of tests that are about something else.
function photo(fill: string): string {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="300" height="400"><rect width="300" height="400" fill="${fill}"/></svg>`;
  return `data:image/svg+xml,${encodeURIComponent(svg)}`;
}

const PHOTOS = [photo("#C5A059"), photo("#6B5D4F"), photo("#2B2118")];

// Far enough out that the presigned-URL TTL is never the reason a test moves.
const EXPIRES_AT = "2099-01-01T00:00:00Z";

const BOUTIQUE = {
  name: "בוטיק ורד",
  profile: {
    phone: "052-1234567",
    address: "הרצל 1, תל אביב",
    description: "בוטיק שמלות כלה בלב תל אביב, בתיאום מראש בלבד.",
    maps_url: "https://maps.google.com/?q=herzl+1",
  },
  rules: [
    { day_of_week: 0, open_time: "10:00:00", close_time: "19:00:00" },
    { day_of_week: 1, open_time: "10:00:00", close_time: "19:00:00" },
    { day_of_week: 2, open_time: "10:00:00", close_time: "19:00:00" },
    { day_of_week: 3, open_time: "10:00:00", close_time: "19:00:00" },
    { day_of_week: 4, open_time: "10:00:00", close_time: "19:00:00" },
    { day_of_week: 5, open_time: "09:00:00", close_time: "13:00:00" },
  ],
  exceptions: [{ date: "2026-12-25", open_time: null, close_time: null, note: "חופשה" }],
};

// The five variants the storefront has to survive, expressed as five dresses
// rather than five fixture modes — one populated list exercises them all at once,
// and each detail route is reachable on its own.
const GALLERY = { id: "d-gallery", name: "ורד הלבן" }; // >= 3 photos, price shown
const HIDDEN = { id: "d-hidden", name: "ליל כלולות" }; // price_agorot omitted server-side
const RESERVED = { id: "d-reserved", name: "טוליפ" }; // the one badge the storefront renders
const BARE = { id: "d-bare", name: "אגם" }; // no photo -> monogram
const ARCHIVED_ID = "d-archived"; // soft-deleted -> 404 within the tenant

const LIST_ITEMS = [
  {
    id: GALLERY.id,
    name: GALLERY.name,
    price_agorot: 590000,
    reserved: false,
    cover: { url: PHOTOS[0], url_expires_at: EXPIRES_AT },
  },
  {
    // price_visible false server-side: the number is absent, not hidden in CSS.
    id: HIDDEN.id,
    name: HIDDEN.name,
    price_agorot: null,
    reserved: false,
    cover: { url: PHOTOS[1], url_expires_at: EXPIRES_AT },
  },
  {
    id: RESERVED.id,
    name: RESERVED.name,
    price_agorot: 420000,
    reserved: true,
    cover: { url: PHOTOS[2], url_expires_at: EXPIRES_AT },
  },
  { id: BARE.id, name: BARE.name, price_agorot: null, reserved: false, cover: null },
];

const DETAILS: Record<string, unknown> = {
  [GALLERY.id]: {
    id: GALLERY.id,
    name: GALLERY.name,
    description:
      "שמלת משי בגזרת A עם מחשוף לב עדין וכפתורי צדף לאורך הגב. " +
      "הרכבה נתפרת ידנית ומתאימה למידה מדויקת בפגישת המדידה השנייה. " +
      "השובל ניתן לקיצור, והצעיף נמכר בנפרד. " +
      "כל שמלה נבדקת לפני האיסוף ומגיעה בגיפה מוגנת אבק ובקולב עץ מקורי מהבוטיק.",
    price_agorot: 590000,
    reserved: false,
    variants: [
      { size_label: "36", available: true },
      { size_label: "38", available: true },
      { size_label: "40", available: false },
    ],
    media: PHOTOS.map((url) => ({ url, url_expires_at: EXPIRES_AT })),
  },
  [HIDDEN.id]: {
    id: HIDDEN.id,
    name: HIDDEN.name,
    description: null,
    price_agorot: null,
    reserved: false,
    variants: [{ size_label: "38", available: true }],
    media: [{ url: PHOTOS[1], url_expires_at: EXPIRES_AT }],
  },
  [RESERVED.id]: {
    id: RESERVED.id,
    name: RESERVED.name,
    description: null,
    price_agorot: 420000,
    reserved: true,
    variants: [{ size_label: "36", available: false }],
    media: [{ url: PHOTOS[2], url_expires_at: EXPIRES_AT }],
  },
  [BARE.id]: {
    id: BARE.id,
    name: BARE.name,
    description: null,
    price_agorot: null,
    reserved: false,
    variants: [],
    media: [],
  },
};

const NOT_FOUND_BODY = { error: { code: "NOT_FOUND", message: "לא נמצא" } };

type ListVariant = "populated" | "empty";

async function installApi(page: Page, list: ListVariant = "populated"): Promise<void> {
  await page.route("**/storefront/**", async (route) => {
    const { pathname } = new URL(route.request().url());
    const send = (body: unknown, status = 200) =>
      route.fulfill({
        status,
        // no-store mirrors the real endpoint: the media URLs in this body are
        // bearer material with a 900s TTL, so the response must never be cached.
        headers: { "content-type": "application/json", "cache-control": "no-store" },
        body: JSON.stringify(body),
      });

    if (pathname === "/storefront/boutique") {
      await send(BOUTIQUE);
      return;
    }
    if (pathname === "/storefront/dresses") {
      const items = list === "empty" ? [] : LIST_ITEMS;
      await send({ items, total: items.length, offset: 0, limit: 24 });
      return;
    }
    const detail = DETAILS[pathname.slice("/storefront/dresses/".length)];
    // An unknown id, an archived dress and another tenant's dress are one and the
    // same 404 on the wire, by design.
    await send(detail ?? NOT_FOUND_BODY, detail ? 200 : 404);
  });
}

// --- shared locators ---------------------------------------------------------

// z-40 belongs to BookingCTA and to nothing else in either app (A11yMenu, Toast
// and SkipLink are z-50), so it is the one selector that distinguishes the *bar
// component* from a plain booking Button — which is exactly the distinction
// /about turns on: it ships the button and no bar.
const CTA_BAR = ".z-40";

const A11Y_TRIGGER = "תפריט נגישות";
const A11Y_STATEMENT = "הצהרת נגישות";
const CTA_LABEL = "קביעת תור למדידה";

function ctaBar(page: Page): Locator {
  return page.locator(CTA_BAR);
}

function a11yTrigger(page: Page): Locator {
  return page.getByRole("button", { name: A11Y_TRIGGER });
}

// --- helpers -----------------------------------------------------------------

// The raw violation objects dump ~10 KB of axe internals into the failure. Only
// the rule id and the offending selectors say anything useful.
async function axeViolations(page: Page): Promise<string[]> {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  return results.violations.map(
    (v) => `${v.id} — ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`,
  );
}

// Each route's "the data landed" tell. Running axe against a skeleton passes
// vacuously, so every route waits on real content first.
async function gotoSettled(page: Page, path: string): Promise<void> {
  await page.goto(`${STOREFRONT}${path}`);
  if (path === "/") {
    // Present in both the populated and the empty state: BookingCTA renders as
    // soon as the fetch resolves, whether or not there are dresses.
    await expect(ctaBar(page)).toBeVisible();
  } else if (path.startsWith("/dress/")) {
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  } else if (path === "/about") {
    await expect(page.getByRole("heading", { name: "שעות פעילות" })).toBeVisible();
  } else {
    // /accessibility has no loading state by design; the boutique name is what
    // arrives late and swaps in over the brand fallback.
    await expect(page.getByText(BOUTIQUE.name)).toBeVisible();
  }
  await page.evaluate(() => document.fonts.ready);
}

interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

function intersectionArea(a: Rect, b: Rect): number {
  const w = Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x);
  const h = Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y);
  return w > 0 && h > 0 ? w * h : 0;
}

function describe(name: string, r: Rect): string {
  return `${name} x=${r.x.toFixed(1)} y=${r.y.toFixed(1)} w=${r.width.toFixed(1)} h=${r.height.toFixed(1)}`;
}

async function rect(locator: Locator, name: string): Promise<Rect> {
  const box = await locator.boundingBox();
  expect(box, `${name} has no bounding box`).not.toBeNull();
  return box as Rect;
}

// BookingCTA is only a bar if it is flush to the bottom edge and spans the
// viewport. Every overlap measurement below is vacuous otherwise — two boxes
// that are both in the wrong place trivially fail to intersect — so this is the
// precondition, not a separate nicety.
async function bottomBarRect(page: Page, viewport: { width: number; height: number }): Promise<Rect> {
  const bar = await rect(ctaBar(page), "BookingCTA bar");
  expect(
    { x: Math.round(bar.x), width: Math.round(bar.width), bottom: Math.round(bar.y + bar.height) },
    "BookingCTA is not laid out as a bottom bar",
  ).toEqual({ x: 0, width: viewport.width, bottom: viewport.height });
  return bar;
}

// How far an element sits from the viewport's *inline-start* edge. Stated this
// way rather than as "right", so the offset assertions below read the same under
// both directions and survive the document ever flipping to LTR.
async function inlineStartGap(page: Page, r: Rect): Promise<number> {
  const { dir, width } = await page.evaluate(() => ({
    dir: getComputedStyle(document.documentElement).direction,
    width: document.documentElement.clientWidth,
  }));
  return dir === "rtl" ? width - (r.x + r.width) : r.x;
}

function activeLabel(page: Page): Promise<string> {
  return page.evaluate(() => {
    const el = document.activeElement;
    if (!el || el === document.body) return "";
    return el.getAttribute("aria-label") ?? el.textContent?.trim() ?? "";
  });
}

// Keyboard only — no locator.focus(), which would prove nothing about tab order.
async function tabTo(page: Page, label: string, max = 60): Promise<void> {
  const seen: string[] = [];
  for (let i = 0; i < max; i++) {
    await page.keyboard.press("Tab");
    const current = await activeLabel(page);
    if (current === label) return;
    seen.push(current);
  }
  throw new Error(`Tab never reached "${label}" in ${String(max)} presses. Saw: ${seen.join(" › ")}`);
}

// --- axe: zero A/AA violations on every public route -------------------------

const AXE_ROUTES: [name: string, path: string, list: ListVariant][] = [
  ["catalog", "/", "populated"],
  // The >= 3-photo dress on purpose: a single-photo Gallery hides its chrome, so
  // a one-photo detail page passes the gallery half of the audit vacuously.
  ["dress detail (3 photos)", `/dress/${GALLERY.id}`, "populated"],
  ["about", "/about", "populated"],
  ["accessibility statement", "/accessibility", "populated"],
  ["catalog (empty state)", "/", "empty"],
];

for (const [name, path, list] of AXE_ROUTES) {
  test(`storefront: zero axe A/AA violations — ${name}`, async ({ page }) => {
    await installApi(page, list);
    await gotoSettled(page, path);
    const violations = await axeViolations(page);
    expect(violations).toEqual([]);
  });
}

// --- responsive --------------------------------------------------------------

const ROUTES = ["/", `/dress/${GALLERY.id}`, "/about", "/accessibility"];

test("storefront: no horizontal scroll at 375 / 768 / 1440 on every route", async ({ page }) => {
  await installApi(page);
  for (const width of [375, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    for (const path of ROUTES) {
      await gotoSettled(page, path);
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(overflow, `${path} overflows by ${String(overflow)}px at ${String(width)}px`).toBeLessThanOrEqual(0);
    }
  }
});

// --- PRE-1: fixed-element collision at 375 (qa-checklist §9, Critical) --------
//
// The design fix is the --space-a11y-clearance token; this is the build-time
// zero-overlap check it left open. Measured, not inferred from CSS: the whole
// point of the original defect was that the token looked right and the rects
// still intersected.

const PRE1_ROUTES: [name: string, path: string, list: ListVariant][] = [
  ["catalog", "/", "populated"],
  ["catalog (empty)", "/", "empty"],
  ["dress detail", `/dress/${GALLERY.id}`, "populated"],
];

const VIEWPORT_375 = { width: 375, height: 700 };

for (const [name, path, list] of PRE1_ROUTES) {
  test(`storefront PRE-1: A11yMenu trigger clears the BookingCTA bar @375 — ${name}`, async ({
    page,
  }) => {
    await page.setViewportSize(VIEWPORT_375);
    await installApi(page, list);
    await gotoSettled(page, path);

    const bar = await bottomBarRect(page, VIEWPORT_375);
    await expect(a11yTrigger(page), "the A11yMenu trigger is not on screen").toBeInViewport();
    const trigger = await rect(a11yTrigger(page), "A11yMenu trigger");

    expect(
      intersectionArea(trigger, bar),
      `${describe("trigger", trigger)} / ${describe("cta bar", bar)}`,
    ).toBe(0);
  });
}

// The original PRE-1 defect was a 60×44 bite out of the CTA taken by a button
// that measured right in CSS. So the sizes themselves are the other half of the
// check: a collapsed trigger cannot collide with anything, and cannot be tapped
// either (qa §8 — 44×44 minimum).
test("storefront: the @boutique/ui layout classes reach the built stylesheet @375", async ({
  page,
}) => {
  await page.setViewportSize(VIEWPORT_375);
  await installApi(page);
  await gotoSettled(page, "/");

  await bottomBarRect(page, VIEWPORT_375);

  const trigger = await rect(a11yTrigger(page), "A11yMenu trigger");
  expect(
    { width: Math.round(trigger.width), height: Math.round(trigger.height) },
    "the A11yMenu trigger is not a 44×44 touch target",
  ).toEqual({ width: 44, height: 44 });

  // DressGrid: 2 columns @375, 3 @768, 4 @1440.
  const columns = await page
    .locator(".grid")
    .first()
    .evaluate((el) => getComputedStyle(el).gridTemplateColumns.split(" ").length);
  expect(columns, "DressGrid is not two columns at 375").toBe(2);
});

test("storefront: הצהרת נגישות sits above the CTA bar and is clickable @375, scrolled to the end", async ({
  page,
}) => {
  await page.setViewportSize(VIEWPORT_375);
  await installApi(page);
  await gotoSettled(page, "/");
  await page.evaluate(() => {
    window.scrollTo(0, document.documentElement.scrollHeight);
  });

  const link = page.getByRole("link", { name: A11Y_STATEMENT });
  const linkRect = await rect(link, "הצהרת נגישות link");
  const bar = await bottomBarRect(page, VIEWPORT_375);
  const trigger = await rect(a11yTrigger(page), "A11yMenu trigger");

  expect(
    intersectionArea(linkRect, bar),
    `${describe("link", linkRect)} / ${describe("cta bar", bar)}`,
  ).toBe(0);
  expect(
    intersectionArea(linkRect, trigger),
    `${describe("link", linkRect)} / ${describe("a11y trigger", trigger)}`,
  ).toBe(0);

  // trial: true runs Playwright's actionability checks — including the hit-target
  // test — without following the link. A covered link fails here.
  await link.click({ trial: true });
});

// PRE-2 (/about and /accessibility dropping --space-a11y-clearance) has no test
// here on purpose. Measured at 375x500 with the reservation deleted outright,
// the trigger box is x=16..60 and the leftmost footer item starts at x=103 — the
// footer row is centred and never reaches the trigger's corner, so overlap is 0
// with or without the padding. Any e2e assertion would pass unfalsifiably. The
// reservation is whitespace, not a collision guard; app-shell.test.tsx asserting
// which token each route carries is the right and sufficient level for it.

// --- exactly one BookingCTA per screen (qa-checklist §7) ---------------------

for (const width of [375, 768]) {
  test(`storefront: exactly one BookingCTA on / and /dress, none on /about @${String(width)}`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    await installApi(page);

    for (const path of ["/", `/dress/${GALLERY.id}`]) {
      await gotoSettled(page, path);
      await expect(ctaBar(page), `${path} @${String(width)}`).toHaveCount(1);
      await expect(ctaBar(page)).toBeVisible();
      await expect(page.getByRole("button", { name: CTA_LABEL })).toHaveCount(1);
      // One instance, two treatments: a fixed bottom bar below 768, inline from
      // 768 up. A bar that stays fixed at 768 leaves a dead gutter on desktop.
      const position = await ctaBar(page).evaluate((el) => getComputedStyle(el).position);
      expect(position, `${path} @${String(width)}`).toBe(width < 768 ? "fixed" : "static");
    }

    await gotoSettled(page, "/about");
    // /about ships the booking button as a static inline element and no bar —
    // nothing moves at 768.
    await expect(ctaBar(page), `/about @${String(width)}`).toHaveCount(0);
    await expect(page.getByRole("button", { name: CTA_LABEL })).toHaveCount(1);
  });
}

// --- WCAG 2.4.2 (Level A): per-route title on client navigation --------------

test("storefront: client navigation retitles the document without a reload", async ({ page }) => {
  await installApi(page);
  await gotoSettled(page, "/");
  await expect(page).toHaveTitle("הקולקציה");

  const catalogUrl = page.url();
  // A marker on the live window: it survives pushState and dies on a reload, so
  // it is the difference between a client navigation and a document swap.
  await page.evaluate(() => {
    (window as unknown as Record<string, unknown>).__sameDocument = true;
  });

  await page.getByText(GALLERY.name, { exact: true }).click();

  await expect(page).toHaveTitle(new RegExp(GALLERY.name));
  expect(page.url()).toBe(`${STOREFRONT}/dress/${GALLERY.id}`);
  expect(page.url()).not.toBe(catalogUrl);
  expect(
    await page.evaluate(() => (window as unknown as Record<string, unknown>).__sameDocument),
    "the DressCard click reloaded the document instead of navigating in place",
  ).toBe(true);

  await page.goBack();

  await expect(page).toHaveTitle("הקולקציה");
  expect(page.url()).toBe(catalogUrl);
  await expect(page.getByText(GALLERY.name, { exact: true })).toBeVisible();
  expect(
    await page.evaluate(() => (window as unknown as Record<string, unknown>).__sameDocument),
    "going back reloaded the document",
  ).toBe(true);
});

test("storefront: /about and /accessibility carry their own titles", async ({ page }) => {
  await installApi(page);
  await gotoSettled(page, "/about");
  await expect(page).toHaveTitle("על הבוטיק");
  await gotoSettled(page, "/accessibility");
  await expect(page).toHaveTitle(A11Y_STATEMENT);
});

// --- skip link ---------------------------------------------------------------

test("storefront: the skip link actually moves focus into <main>", async ({ page }) => {
  await installApi(page);
  await gotoSettled(page, "/");

  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "דלג לתוכן" })).toBeFocused();

  await page.keyboard.press("Enter");
  const landed = await page.evaluate(() => ({
    tag: document.activeElement?.tagName ?? "",
    id: document.activeElement?.id ?? "",
  }));
  expect(landed).toEqual({ tag: "MAIN", id: "main" });
});

// The skip link is the first thing a keyboard user meets, and it is positioned
// only while focused — so a dead positioning utility here is invisible to every
// other check in this file, including axe.
test("storefront: the focused skip link is inset from the inline-start edge, not flush against it", async ({
  page,
}) => {
  await page.setViewportSize(VIEWPORT_375);
  await installApi(page);
  await gotoSettled(page, "/");

  await page.keyboard.press("Tab");
  const link = page.getByRole("link", { name: "דלג לתוכן" });
  await expect(link).toBeFocused();

  // `focus:inset-s-2 focus:top-2` — 8px in on both axes. A 0 gap means the
  // utility compiled to nothing and the box fell back to its static position.
  const linkRect = await rect(link, "skip link");
  expect({
    inlineStart: Math.round(await inlineStartGap(page, linkRect)),
    top: Math.round(linkRect.y),
  }).toEqual({ inlineStart: 8, top: 8 });
});

// --- gallery keyboard operability (qa-checklist §8) --------------------------

test("storefront: every gallery image is keyboard-reachable and aria-current tracks it", async ({
  page,
}) => {
  await installApi(page);
  await gotoSettled(page, `/dress/${GALLERY.id}`);

  const main = page.getByRole("img", { name: GALLERY.name });
  await expect(main).toHaveAttribute("src", PHOTOS[0]);

  // Reached by Tab + Enter alone — a swipe-only carousel would fail here.
  for (const n of [2, 3, 1]) {
    const label = `תמונה ${String(n)} מתוך 3`;
    await tabTo(page, label);
    await page.keyboard.press("Enter");
    await expect(main).toHaveAttribute("src", PHOTOS[n - 1]);
    await expect(page.locator('[aria-current="true"]')).toHaveAttribute("aria-label", label);
  }

  // The prev/next pair is the other keyboard route to the same images.
  await tabTo(page, "התמונה הבאה");
  await page.keyboard.press("Enter");
  await expect(main).toHaveAttribute("src", PHOTOS[1]);
  await expect(page.locator('[aria-current="true"]')).toHaveAttribute("aria-label", "תמונה 2 מתוך 3");

  await tabTo(page, "התמונה הקודמת");
  await page.keyboard.press("Enter");
  await expect(main).toHaveAttribute("src", PHOTOS[0]);
  await expect(page.locator('[aria-current="true"]')).toHaveAttribute("aria-label", "תמונה 1 מתוך 3");
});

// The keyboard test above drives the arrows by label, so it passes no matter
// where they are painted — which is how both arrows came to be stacked on the
// same 44×44 rect with `prev` fully buried under `next`, tappable by nobody.
test("storefront: the gallery arrows sit on opposite edges and are each tappable @375", async ({
  page,
}) => {
  await page.setViewportSize(VIEWPORT_375);
  await installApi(page);
  await gotoSettled(page, `/dress/${GALLERY.id}`);

  const prev = page.getByRole("button", { name: "התמונה הקודמת" });
  const next = page.getByRole("button", { name: "התמונה הבאה" });
  const image = await rect(page.getByRole("img", { name: GALLERY.name }), "gallery image");
  const prevRect = await rect(prev, "prev arrow");
  const nextRect = await rect(next, "next arrow");

  expect(
    intersectionArea(prevRect, nextRect),
    `${describe("prev", prevRect)} / ${describe("next", nextRect)}`,
  ).toBe(0);

  // Opposite halves of the image, said without naming a side.
  const centre = (r: Rect) => r.x + r.width / 2;
  const mid = image.x + image.width / 2;
  expect(
    Math.sign(centre(prevRect) - mid),
    `both arrows are on the same side of the image — ${describe("prev", prevRect)} / ${describe("next", nextRect)}`,
  ).toBe(-Math.sign(centre(nextRect) - mid));

  // Only the middle of the set has both arrows enabled; reach it by keyboard so
  // the trial clicks below are the first thing that needs a real hit target.
  await tabTo(page, "תמונה 2 מתוך 3");
  await page.keyboard.press("Enter");
  await prev.click({ trial: true });
  await next.click({ trial: true });
});

// --- A11yMenu: the base experience and the boosted one both pass -------------

test("storefront: A11yMenu text-size boost keeps zero axe A/AA violations", async ({ page }) => {
  await installApi(page);
  await gotoSettled(page, "/");

  const base = await axeViolations(page);
  expect(base, "base experience").toEqual([]);

  await expect(a11yTrigger(page), "the A11yMenu trigger is not on screen").toBeInViewport();
  await a11yTrigger(page).click();
  await page.getByRole("button", { name: "הגדלת טקסט" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-a11y-text-size", "");

  // Selecting a control deliberately leaves the panel open, and this scan is only
  // an open-state scan for as long as that holds. Pinned, because a later
  // close-on-select would otherwise turn the assertion below into a second
  // closed-state scan without changing a line of it.
  await expect(page.getByRole("group"), "the panel closed on select").toBeVisible();

  const boosted = await axeViolations(page);
  expect(boosted, "text-size boost applied").toEqual([]);
});

// The open panel was unreachable by axe until the trigger became tappable, which
// is how a Level-A `aria-required-parent` failure — menuitemcheckbox with no
// enclosing role="menu" — survived every audit. Both scans above run closed; the
// one below is the state that was actually broken. The panel is now a disclosure
// of aria-pressed toggle buttons, which owes no menu keyboard contract at all.
test("storefront: the open A11yMenu keeps zero axe A/AA violations", async ({ page }) => {
  await page.setViewportSize(VIEWPORT_375);
  await installApi(page);
  await gotoSettled(page, "/");

  await a11yTrigger(page).click();
  const panel = page.getByRole("group");
  await expect(panel).toBeVisible();
  await expect(panel.getByRole("button")).toHaveCount(5);
  // A menu role would promise arrow-key roving focus this component never had.
  await expect(page.getByRole("menu")).toHaveCount(0);
  await expect(a11yTrigger(page)).toHaveAttribute("aria-expanded", "true");

  expect(await axeViolations(page), "A11yMenu open").toEqual([]);
});

// --- the states the storefront must not leak ---------------------------------

test("storefront: an archived dress is an unavailable message, not a broken page", async ({
  page,
}) => {
  await installApi(page);
  await page.goto(`${STOREFRONT}/dress/${ARCHIVED_ID}`);
  await expect(page.getByRole("alert")).toHaveText("השמלה כבר לא זמינה");
  // A 404 is terminal — retrying an archived dress just repeats it.
  await expect(page.getByRole("button", { name: "נסי שוב" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "חזרה לקולקציה" })).toBeVisible();
});

test("storefront: renders reserved, never out-of-stock, and never a raw quantity", async ({
  page,
}) => {
  await installApi(page);
  await gotoSettled(page, `/dress/${RESERVED.id}`);
  await expect(page.getByText("הוזמן")).toBeVisible();

  const body = (await page.locator("body").innerText()).toLowerCase();
  for (const banned of ["אזל", "out of stock", "quantity", "מלאי"]) {
    expect(body, `manage-only vocabulary "${banned}" reached the storefront`).not.toContain(banned);
  }
});

test("storefront: a hidden price renders the agreed-price label with no number", async ({ page }) => {
  await installApi(page);
  await gotoSettled(page, `/dress/${HIDDEN.id}`);
  await expect(page.getByText("מחיר בתיאום")).toBeVisible();
  await expect(page.locator("body")).not.toContainText("₪");
});
