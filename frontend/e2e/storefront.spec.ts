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

// FLAT, matching BoutiqueResponse: no `profile` sub-object, and the weekly rules
// are `hours`. The nested shape the earlier fixture used no longer parses — the
// hours adapter walks `boutique.hours` and an undefined there throws out of
// render, which is a blank page, not a degraded one.
const BOUTIQUE = {
  name: "בוטיק ורד",
  essence: "שמלות כלה בעבודת יד",
  description: "בוטיק שמלות כלה בלב תל אביב, בתיאום מראש בלבד.",
  phone: "052-1234567",
  address: "הרצל 1, תל אביב",
  maps_url: "https://maps.google.com/?q=herzl+1",
  instagram: "vered.bridal",
  hours: [
    { day_of_week: 0, open_time: "10:00:00", close_time: "19:00:00" },
    { day_of_week: 1, open_time: "10:00:00", close_time: "19:00:00" },
    { day_of_week: 2, open_time: "10:00:00", close_time: "19:00:00" },
    { day_of_week: 3, open_time: "10:00:00", close_time: "19:00:00" },
    { day_of_week: 4, open_time: "10:00:00", close_time: "19:00:00" },
    { day_of_week: 5, open_time: "09:00:00", close_time: "13:00:00" },
  ],
  exceptions: [{ date: "2026-12-25", open_time: null, close_time: null, note: "חופשה" }],
};

// A tenant who filled in nothing but the name — the state a boutique is in on
// the day it is provisioned. Long enough to wrap the catalog h1 twice at 375,
// which is where a fixed-height header or a truncating utility shows up.
const LONG_NAME_BOUTIQUE = {
  ...BOUTIQUE,
  name: "הבוטיק של ורד — שמלות כלה בעבודת יד, תפירה אישית ומדידות בתיאום מראש בלב תל אביב",
};

// The five variants the storefront has to survive, expressed as five dresses
// rather than five fixture modes — one populated list exercises them all at once,
// and each detail route is reachable on its own.
const GALLERY = { id: "d-gallery", name: "ורד הלבן" }; // >= 3 photos, price shown
const HIDDEN = { id: "d-hidden", name: "ליל כלולות" }; // price_agorot omitted server-side
const RESERVED = { id: "d-reserved", name: "טוליפ" }; // the one badge the storefront renders
const BARE = { id: "d-bare", name: "אגם" }; // no photo -> monogram
const LONG = { id: "d-long", name: "שמלת משי מלכותית עם שובל ארוך במיוחד ורקמת פנינים בעבודת יד" };
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
  {
    id: LONG.id,
    name: LONG.name,
    price_agorot: 1290000,
    reserved: false,
    cover: { url: PHOTOS[0], url_expires_at: EXPIRES_AT },
  },
];

// The server pins a page at 24 and the pilot ships ~60 dresses, so "עוד שמלות"
// is the only route to dress 25. 50 rather than 60 so the last page is a short
// one — that is where an offset computed from a page counter instead of from the
// items already held goes wrong.
const PAGE_LIMIT = 24;
const PAGED_ITEMS = Array.from({ length: 50 }, (_, index) => ({
  id: `d-paged-${String(index + 1)}`,
  name: `שמלה ${String(index + 1)}`,
  price_agorot: 100000 + index,
  reserved: false,
  cover: { url: PHOTOS[index % PHOTOS.length], url_expires_at: EXPIRES_AT },
}));

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
    sizes: [
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
    sizes: [{ size_label: "38", available: true }],
    media: [{ url: PHOTOS[1], url_expires_at: EXPIRES_AT }],
  },
  [RESERVED.id]: {
    id: RESERVED.id,
    name: RESERVED.name,
    description: null,
    price_agorot: 420000,
    reserved: true,
    sizes: [{ size_label: "36", available: false }],
    media: [{ url: PHOTOS[2], url_expires_at: EXPIRES_AT }],
  },
  [BARE.id]: {
    id: BARE.id,
    name: BARE.name,
    description: null,
    price_agorot: null,
    reserved: false,
    sizes: [],
    media: [],
  },
  [LONG.id]: {
    id: LONG.id,
    name: LONG.name,
    description: null,
    price_agorot: 1290000,
    reserved: false,
    sizes: [{ size_label: "38", available: true }],
    media: [{ url: PHOTOS[0], url_expires_at: EXPIRES_AT }],
  },
};

const NOT_FOUND_BODY = { error: { code: "NOT_FOUND", message: "לא נמצא" } };

type ListVariant = "populated" | "empty" | "paged";

// Every field but the name cleared. The backend collapses "" to null (the manage
// form seeds blanks to "" and submits them verbatim, so this is what an owner who
// saves the form once actually produces). Before that fix this fixture rendered
// `<a href="tel:">` with no accessible name on every route — a WCAG 2.4.4 (A)
// failure the fully-populated fixture could never see.
const CLEARED_BOUTIQUE = {
  ...BOUTIQUE,
  essence: null,
  description: null,
  phone: null,
  address: null,
  maps_url: null,
  instagram: null,
};

async function installApi(
  page: Page,
  list: ListVariant = "populated",
  boutique: unknown = BOUTIQUE,
): Promise<void> {
  await page.route("**/storefront/**", async (route) => {
    const { pathname, searchParams } = new URL(route.request().url());
    const send = (body: unknown, status = 200) =>
      route.fulfill({
        status,
        // no-store mirrors the real endpoint: the media URLs in this body are
        // bearer material with a 900s TTL, so the response must never be cached.
        headers: { "content-type": "application/json", "cache-control": "no-store" },
        body: JSON.stringify(body),
      });

    if (pathname === "/storefront/boutique") {
      await send(boutique);
      return;
    }
    if (pathname === "/storefront/dresses") {
      if (list === "paged") {
        // Honour the offset the page actually sent: a "more" button that keeps
        // asking for offset 0 would still grow the grid against a fixture that
        // ignored the parameter.
        const offset = Number(searchParams.get("offset") ?? "0");
        await send({
          items: PAGED_ITEMS.slice(offset, offset + PAGE_LIMIT),
          total: PAGED_ITEMS.length,
          offset,
          limit: PAGE_LIMIT,
        });
        return;
      }
      const items = list === "empty" ? [] : LIST_ITEMS;
      await send({ items, total: items.length, offset: 0, limit: PAGE_LIMIT });
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
const SKIP_LINK = "דלג לתוכן";
const MORE_LABEL = "עוד שמלות";

// StorefrontLayout's <main tabindex="-1">. The skip link targets it and the
// router moves focus here after every client navigation.
const MAIN_ID = "content";

function ctaBar(page: Page): Locator {
  return page.locator(CTA_BAR);
}

function a11yTrigger(page: Page): Locator {
  return page.getByRole("button", { name: A11Y_TRIGGER });
}

// The gallery's thumbnails are alt="" + aria-hidden, so the detail page exposes
// exactly ONE image to the accessibility tree — the main one. Its alt is the
// position string, which changes as the visitor pages, so it cannot be located
// by name without the locator going stale mid-test.
function galleryImage(page: Page): Locator {
  return page.getByRole("img");
}

// Cards are the only /dress/ links in <main>; the footer carries none. Counting
// them by destination is what makes "the next page appended" measurable.
function dressCards(page: Page): Locator {
  return page.locator(`#${MAIN_ID} a[href^="/dress/"]`);
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
    // arrives late and swaps in over the brand fallback. .first() because the
    // name legitimately appears twice — once as the site the statement covers,
    // once as the named accessibility contact while no platform coordinator is
    // configured (src/lib/coordinator.ts).
    await expect(page.getByText(BOUTIQUE.name).first()).toBeVisible();
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

// Where focus sits relative to the content region, in one round trip: `id` is
// the focused element's own id, `inside` says whether <main> contains it.
async function focusState(page: Page): Promise<{ id: string; inside: boolean; label: string }> {
  return page.evaluate((mainId) => {
    const el = document.activeElement;
    const main = document.getElementById(mainId);
    return {
      id: el?.id ?? "",
      inside: main !== null && el !== null && el !== document.body && main.contains(el),
      label: el?.getAttribute("aria-label") ?? el?.textContent?.trim().slice(0, 40) ?? "",
    };
  }, MAIN_ID);
}

// A box that clips its own text. Catches a fixed height with overflow:hidden, a
// line-clamp that survived a resize and a `truncate` on a heading — all of which
// eat descenders before they eat whole words, so they read as a rendering
// artefact rather than as missing content.
async function expectNotClipped(locator: Locator, name: string): Promise<void> {
  const box = await locator.evaluate((el) => {
    // scrollHeight/clientHeight are rounded integers of a fractional layout, and
    // they round in opposite directions: a 125.6px line box reports client 125
    // and scroll 126. Ceiling the fractional border box is the honest upper
    // bound — real clipping is a whole line or more, never one pixel.
    const rect = el.getBoundingClientRect();
    return {
      scrollHeight: el.scrollHeight,
      height: Math.max(el.clientHeight, Math.ceil(rect.height)),
      scrollWidth: el.scrollWidth,
      width: Math.max(el.clientWidth, Math.ceil(rect.width)),
    };
  });
  // Two pixels of slack: a glyph's ink legitimately extends a pixel past a
  // fractional line box without anything being cut, and scrollHeight rounds up
  // where clientHeight rounds down. Every clipping mechanism that loses actual
  // text — line-clamp, a fixed height with overflow:hidden, `truncate` — costs a
  // whole line or the tail of one, never a pixel.
  const CLIP_TOLERANCE = 2;
  expect(box.scrollHeight, `${name} is clipped vertically (descenders cut)`).toBeLessThanOrEqual(
    box.height + CLIP_TOLERANCE,
  );
  expect(box.scrollWidth, `${name} is clipped horizontally`).toBeLessThanOrEqual(
    box.width + CLIP_TOLERANCE,
  );
}

async function horizontalOverflow(page: Page): Promise<number> {
  return page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
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

const AXE_ROUTES: [name: string, path: string, list: ListVariant, boutique?: unknown][] = [
  ["catalog", "/", "populated"],
  // The >= 3-photo dress on purpose: a single-photo Gallery hides its chrome, so
  // a one-photo detail page passes the gallery half of the audit vacuously.
  ["dress detail (3 photos)", `/dress/${GALLERY.id}`, "populated"],
  ["about", "/about", "populated"],
  ["accessibility statement", "/accessibility", "populated"],
  ["catalog (empty state)", "/", "empty"],
  // A boutique with every profile field cleared — the nameless-link case.
  ["catalog (cleared profile)", "/", "populated", CLEARED_BOUTIQUE],
  ["about (cleared profile)", "/about", "populated", CLEARED_BOUTIQUE],
  ["accessibility statement (cleared profile)", "/accessibility", "populated", CLEARED_BOUTIQUE],
];

for (const [name, path, list, boutique] of AXE_ROUTES) {
  test(`storefront: zero axe A/AA violations — ${name}`, async ({ page }) => {
    await installApi(page, list, boutique ?? BOUTIQUE);
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
      const overflow = await horizontalOverflow(page);
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

// PRE-2: the same measurement on every route that carries the statutory link,
// not just the one with a CTA bar under it. /about and /accessibility reserve
// their own clearance instead of inheriting the bar's, so they are the two
// routes where the reservation can be deleted without any other test noticing.
//
// The bar half only applies where a bar exists; the trial click is the part that
// holds everywhere, and it is the falsifiable one — Playwright's hit-target test
// fails if the fixed A11yMenu, or anything else, is painted over the link.
for (const path of ["/", "/about", "/accessibility"]) {
  test(`storefront PRE-2: הצהרת נגישות clears the fixed chrome and is clickable @375, scrolled to the end — ${path}`, async ({
    page,
  }) => {
    await page.setViewportSize(VIEWPORT_375);
    await installApi(page);
    await gotoSettled(page, path);
    await page.evaluate(() => {
      window.scrollTo(0, document.documentElement.scrollHeight);
    });

    const link = page.getByRole("link", { name: A11Y_STATEMENT });
    const linkRect = await rect(link, "הצהרת נגישות link");
    const trigger = await rect(a11yTrigger(page), "A11yMenu trigger");

    if ((await ctaBar(page).count()) > 0) {
      const bar = await bottomBarRect(page, VIEWPORT_375);
      expect(
        intersectionArea(linkRect, bar),
        `${describe("link", linkRect)} / ${describe("cta bar", bar)}`,
      ).toBe(0);
    }
    expect(
      intersectionArea(linkRect, trigger),
      `${describe("link", linkRect)} / ${describe("a11y trigger", trigger)}`,
    ).toBe(0);

    // trial: true runs Playwright's actionability checks — including the
    // hit-target test — without following the link. A covered link fails here.
    await link.click({ trial: true });
  });
}

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

// The test above enters each route with page.goto, which is a full document load
// — the browser parses index.html, React mounts, and the mount-time title write
// covers for a router that never retitles again. That is precisely the defect
// this walk exists to catch: in a Vite SPA the served <title> is index.html's
// forever unless something rewrites it per navigation, and axe's document-title
// rule is satisfied by the stale one. So every route below is reached by
// CLICKING, and the same walk pins the other two halves of the navigation
// contract that only a browser can observe: focus lands on #content, and the
// viewport is back at the top.
test("storefront: clicking through all four routes retitles, refocuses #content and resets scroll", async ({
  page,
}) => {
  // 375x600 so every route is genuinely taller than the viewport — a scroll
  // reset asserted on a page that cannot scroll proves nothing.
  await page.setViewportSize({ width: 375, height: 600 });
  await installApi(page);
  await gotoSettled(page, "/");
  await expect(page).toHaveTitle("הקולקציה");

  // A marker on the live window: it survives pushState and dies on a reload, so
  // it is the difference between a client navigation and a document swap.
  await page.evaluate(() => {
    (window as unknown as Record<string, unknown>).__sameDocument = true;
  });

  // All four routes, each ENTERED by a click. The catalog is in the list twice
  // over: once as the starting document, once as a destination, because a title
  // that is only ever correct on first paint is exactly the defect.
  //
  // `fromBottom` marks the links that sit low enough to be clicked from a
  // scrolled-down page, which is what makes the scroll-reset assertion mean
  // something. The dress page's back link is at the very top, so clicking it
  // scrolls the page to 0 by itself — that step asserts the title, the focus and
  // the no-reload marker, and says nothing about scrolling rather than asserting
  // a 0 it did not earn.
  const steps = [
    // The last card in the grid, so scrolling to the end of the page does not
    // have to be undone to reach it.
    {
      label: "dress card",
      target: page.getByRole("link", { name: LONG.name }),
      title: new RegExp(LONG.name),
      fromBottom: true,
    },
    {
      label: "חזרה לקולקציה",
      target: page.getByRole("link", { name: "חזרה לקולקציה" }),
      title: "הקולקציה",
      fromBottom: false,
    },
    {
      label: "footer על הבוטיק",
      target: page.getByRole("link", { name: "על הבוטיק" }),
      title: "על הבוטיק",
      fromBottom: true,
    },
    {
      label: "footer הצהרת נגישות",
      target: page.getByRole("link", { name: A11Y_STATEMENT }),
      title: A11Y_STATEMENT,
      fromBottom: true,
    },
  ];

  for (const { label, target, title, fromBottom } of steps) {
    await page.evaluate(() => {
      window.scrollTo(0, document.documentElement.scrollHeight);
    });
    await target.scrollIntoViewIfNeeded();
    const scrolledTo = await page.evaluate(() => window.scrollY);
    if (fromBottom) {
      expect(
        scrolledTo,
        `${label}: the page did not scroll, so the reset below is vacuous`,
      ).toBeGreaterThan(0);
    }

    await target.click();

    await expect(page, `${label} did not retitle the document`).toHaveTitle(title);
    if (fromBottom) {
      await expect
        .poll(() => page.evaluate(() => window.scrollY), {
          message: `${label} left the viewport where it was`,
        })
        .toBe(0);
    }
    expect(await focusState(page), `${label} did not move focus to #${MAIN_ID}`).toMatchObject({
      id: MAIN_ID,
    });
    expect(
      await page.evaluate(() => (window as unknown as Record<string, unknown>).__sameDocument),
      `${label} reloaded the document instead of navigating in place`,
    ).toBe(true);
  }
});

// --- skip link ---------------------------------------------------------------

test("storefront: the skip link actually moves focus into <main>, and the next Tab stays there", async ({
  page,
}) => {
  await installApi(page);
  await gotoSettled(page, "/");

  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: SKIP_LINK })).toBeFocused();

  await page.keyboard.press("Enter");
  const landed = await page.evaluate(() => ({
    tag: document.activeElement?.tagName ?? "",
    id: document.activeElement?.id ?? "",
  }));
  expect(landed).toEqual({ tag: "MAIN", id: MAIN_ID });

  // The half axe cannot see: a skip link that scrolls without moving focus
  // passes every automated audit and still drops the keyboard user back at the
  // top of the tab order, one Tab later. So the next Tab has to land INSIDE the
  // content region, not on the second item of the page chrome.
  await page.keyboard.press("Tab");
  const next = await focusState(page);
  expect(next.inside, `Tab after the skip link landed on "${next.label}", outside #${MAIN_ID}`).toBe(
    true,
  );
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
  const link = page.getByRole("link", { name: SKIP_LINK });
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

  const main = galleryImage(page);
  await expect(main).toHaveAttribute("src", PHOTOS[0]);

  // Reached by Tab + Enter alone — a swipe-only carousel would fail here.
  for (const n of [2, 3, 1]) {
    const label = `תמונה ${String(n)} מתוך 3`;
    await tabTo(page, label);
    await page.keyboard.press("Enter");
    await expect(main).toHaveAttribute("src", PHOTOS[n - 1]);
    // The main image's own label tracks the position too, so the announcement a
    // screen-reader user hears on the image matches the thumbnail they picked.
    await expect(main).toHaveAttribute("alt", label);
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
  const image = await rect(galleryImage(page), "gallery image");
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

test("storefront: a failed boutique keeps its h1, and the retry actually recovers", async ({
  page,
}) => {
  // Identity itself fails. The degraded page must STILL carry exactly one <h1>:
  // it is where the skip link lands, and a page whose only heading vanishes on
  // an API error drops a screen-reader user into an untitled region. axe cannot
  // catch this — page-has-heading-one is best-practice, not an A/AA rule — so
  // it is asserted here or nowhere.
  let boutiqueOk = false;
  await page.route("**/storefront/**", async (route) => {
    const { pathname } = new URL(route.request().url());
    const send = (body: unknown, status = 200) =>
      route.fulfill({
        status,
        headers: { "content-type": "application/json", "cache-control": "no-store" },
        body: JSON.stringify(body),
      });
    if (pathname === "/storefront/boutique") {
      if (!boutiqueOk) {
        await send({ error: { code: "UNKNOWN", message: "boom" } }, 500);
        return;
      }
      await send(BOUTIQUE);
      return;
    }
    await send({ items: LIST_ITEMS, total: LIST_ITEMS.length, offset: 0, limit: PAGE_LIMIT });
  });

  // page.goto, not gotoSettled: gotoSettled waits for the booking CTA bar, and
  // the whole point of this state is that the CTA is deliberately withheld.
  await page.goto(`${STOREFRONT}/`);
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
  // No CTA: opening an empty contact panel is worse than not offering one.
  await expect(page.getByRole("button", { name: "קביעת תור למדידה" })).toHaveCount(0);

  // The retry must re-drive the BOUTIQUE fetch, not only the dress list. The
  // boutique block is fetched once by the layout, so a retry wired to the list
  // alone would look live and never change anything.
  boutiqueOk = true;
  await page.getByRole("button", { name: "נסי שוב" }).click();
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(page.getByRole("heading", { level: 1, name: BOUTIQUE.name })).toBeVisible();
  await expect(page.getByRole("button", { name: "קביעת תור למדידה" })).toBeVisible();
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

// --- alt text: position on the gallery, dress name on the card ---------------

test("storefront: the gallery main image is labelled by position, the card by dress name", async ({
  page,
}) => {
  await installApi(page);
  await gotoSettled(page, "/");
  // The CARD keeps the name: it is the only thing distinguishing one grid tile
  // from the next for a screen-reader user.
  await expect(
    page.getByRole("img", { name: GALLERY.name }),
    "the DressCard's alt is no longer the dress name",
  ).toHaveCount(1);

  await gotoSettled(page, `/dress/${GALLERY.id}`);
  // The GALLERY does not: eight photos all announcing "ורד הלבן" give no way to
  // tell one from another, while the thumbnails right below announce position
  // correctly.
  await expect(
    page.getByRole("img", { name: GALLERY.name }),
    "the gallery main image is announcing the dress name instead of its position",
  ).toHaveCount(0);
  await expect(galleryImage(page)).toHaveAttribute("alt", "תמונה 1 מתוך 3");
});

// --- load more (E2 criterion 3) ----------------------------------------------

test('storefront: "עוד שמלות" appends the next page and disappears at the end', async ({ page }) => {
  await installApi(page, "paged");
  await gotoSettled(page, "/");

  await expect(dressCards(page)).toHaveCount(PAGE_LIMIT);
  // Dress 25 is the whole point: without the button it is unreachable, and the
  // pilot's collection is ~60.
  await expect(page.getByRole("link", { name: "שמלה 25" })).toHaveCount(0);

  const more = page.getByRole("button", { name: MORE_LABEL });
  await expect(more).toBeVisible();
  await more.click();

  await expect(page.getByRole("link", { name: "שמלה 25" })).toBeVisible();
  await expect(dressCards(page)).toHaveCount(PAGE_LIMIT * 2);
  // 48 of 50 held: still short, so the button stays.
  await expect(more).toBeVisible();

  await more.click();
  await expect(dressCards(page)).toHaveCount(PAGED_ITEMS.length);
  await expect(page.getByRole("link", { name: `שמלה ${String(PAGED_ITEMS.length)}` })).toBeVisible();
  // Everything is on screen — a button that still offers "more" here asks for a
  // page the server will answer empty.
  await expect(more, "the load-more button survived the last page").toHaveCount(0);
});

// --- grid geometry: only a browser can measure this --------------------------

test("storefront: a photo-less card and its photographed row-mate are the same height @375", async ({
  page,
}) => {
  await page.setViewportSize(VIEWPORT_375);
  await installApi(page);
  await gotoSettled(page, "/");

  // Two columns at 375, so the fixture's four framed dresses fall as
  // [priced | agreed-price] then [photographed | photo-less].
  const rows: [name: string, a: string, b: string][] = [
    ["priced vs agreed-price", GALLERY.name, HIDDEN.name],
    ["photographed vs photo-less", RESERVED.name, BARE.name],
  ];

  for (const [label, first, second] of rows) {
    const a = await rect(page.getByRole("link", { name: first }), first);
    const b = await rect(page.getByRole("link", { name: second }), second);

    expect(Math.round(a.y), `${label}: the two cards are not in the same row`).toBe(Math.round(b.y));
    expect(
      Math.round(a.height),
      `${label}: ${describe(first, a)} / ${describe(second, b)}`,
    ).toBe(Math.round(b.height));

    // The media box is the half that can collapse without the grid noticing:
    // the row stretches its items, so two cards stay the same height even when
    // one of them has lost its aspect-ratio reservation and left a gap below.
    const media = await Promise.all(
      [first, second].map((name) =>
        page
          .getByRole("link", { name })
          .evaluate((el) => el.firstElementChild?.getBoundingClientRect().height ?? -1),
      ),
    );
    expect(media[0], `${label}: the photo slot and the monogram slot differ in height`).toBe(
      media[1],
    );
  }
});

// --- WCAG 1.4.4: 200% text, by zoom and by text-only resize ------------------

const RESIZE_ROUTES = ["/", `/dress/${GALLERY.id}`, "/about", "/accessibility"];
const WIDTHS = [375, 768, 1440];

// Two routes measurably fail 200% text-only resize at 375 today, both in
// production code this suite does not own:
//
//   /dress  — Gallery's thumbnail strip is three size-14 buttons plus two gaps
//             = 368px, and it does not shrink inside a 311px content box, so the
//             document scrolls 25px sideways.
//   /about  — the footer's <bdi dir="ltr">@handle</bdi> is a single unbreakable
//             Latin token 187px wide and overflows its flex line by 17px.
//
// They are pinned below as expected failures rather than quietly excluded: the
// day either one is fixed its case reports "expected to fail, but passed", and
// the annotation comes off. Every other cell of the matrix is a hard pass.
// Two WCAG 1.4.4 overflows used to live here as expected failures: the Gallery
// thumbnail strip (min-content 368px at 200% text) and the footer's unbreakable
// Instagram handle. Both are fixed — `min-w-0` on the strip so overflow-x-auto
// can engage, and min-w-0 + overflow-wrap:anywhere on the footer links — so the
// exclusion list is empty and every route is held to the same bar.
const TEXT_RESIZE_BROKEN_AT_375: string[] = [];

async function resizeTextTo200Percent(page: Page): Promise<void> {
  await page.evaluate(() => {
    document.documentElement.style.fontSize = "32px";
  });
}

// Text-only resize is the harder half of 1.4.4 and the one that actually breaks
// layouts: the viewport does NOT shrink, so every rem-sized box grows inside a
// container that did not. A px-height clamp, a fixed-height bar or a truncating
// heading all show up here and nowhere else.
test("storefront: 200% text-only resize (root 32px) keeps every route free of horizontal scroll", async ({
  page,
}) => {
  await installApi(page);
  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: 900 });
    for (const path of RESIZE_ROUTES) {
      if (width === 375 && TEXT_RESIZE_BROKEN_AT_375.includes(path)) continue;
      await gotoSettled(page, path);
      await resizeTextTo200Percent(page);
      const overflow = await horizontalOverflow(page);
      expect(
        overflow,
        `${path} overflows by ${String(overflow)}px at ${String(width)}px with 200% text`,
      ).toBeLessThanOrEqual(0);
    }
  }
});

// Browser zoom is not text-only resize: at 200% the CSS viewport HALVES, so a
// 375px layout is what a 750px device window renders when its owner zooms in.
// Driving it that way (rather than halving the design widths, which would demand
// a 187px layout no guideline asks for) is what makes this a real check — it
// catches anything sized against device pixels or a stale visual viewport,
// which a plain width sweep cannot see.
test("storefront: 200% browser zoom reflows to the same three widths without horizontal scroll", async ({
  page,
}) => {
  await installApi(page);
  for (const width of WIDTHS) {
    await page.setViewportSize({ width: width * 2, height: 1600 });
    for (const path of RESIZE_ROUTES) {
      await gotoSettled(page, path);
      await page.evaluate(() => {
        document.documentElement.style.zoom = "2";
      });
      const overflow = await horizontalOverflow(page);
      expect(
        overflow,
        `${path} overflows by ${String(overflow)}px at 200% zoom of ${String(width * 2)}px`,
      ).toBeLessThanOrEqual(0);
    }
  }
});

// The A11yMenu's own boost is a third path to bigger text, and the one a visitor
// who cannot find the browser's zoom will use. 375 only: it is the width where a
// boost has the least room to go anywhere.
test("storefront: the A11yMenu text-size boost keeps every route free of horizontal scroll @375", async ({
  page,
}) => {
  await page.setViewportSize(VIEWPORT_375);
  await installApi(page);
  for (const path of RESIZE_ROUTES) {
    await gotoSettled(page, path);
    await a11yTrigger(page).click();
    await page.getByRole("button", { name: "הגדלת טקסט" }).click();
    await expect(page.locator("html")).toHaveAttribute("data-a11y-text-size", "");

    const overflow = await horizontalOverflow(page);
    expect(
      overflow,
      `${path} overflows by ${String(overflow)}px with the text-size boost on`,
    ).toBeLessThanOrEqual(0);
  }
});

// --- long tenant-supplied strings --------------------------------------------

test("storefront: a long boutique name and a long dress name neither overflow nor clip", async ({
  page,
}) => {
  await installApi(page, "populated", LONG_NAME_BOUTIQUE);
  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: 900 });

    await gotoSettled(page, "/");
    const boutiqueHeading = page.getByRole("heading", { level: 1 });
    await expect(boutiqueHeading).toHaveText(LONG_NAME_BOUTIQUE.name);
    await expectNotClipped(boutiqueHeading, `boutique h1 @${String(width)}`);
    await expectNotClipped(
      page.getByRole("link", { name: LONG.name }),
      `long dress card @${String(width)}`,
    );
    let overflow = await horizontalOverflow(page);
    expect(overflow, `/ overflows by ${String(overflow)}px at ${String(width)}px`).toBeLessThanOrEqual(0);

    await gotoSettled(page, `/dress/${LONG.id}`);
    const dressHeading = page.getByRole("heading", { level: 1 });
    await expect(dressHeading).toHaveText(LONG.name);
    await expectNotClipped(dressHeading, `dress h1 @${String(width)}`);
    overflow = await horizontalOverflow(page);
    expect(
      overflow,
      `/dress overflows by ${String(overflow)}px at ${String(width)}px`,
    ).toBeLessThanOrEqual(0);
  }
});

// --- prefers-reduced-motion ---------------------------------------------------

test("storefront: reduced motion zeroes transitions and leaves scroll-snap alone", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await installApi(page);
  await gotoSettled(page, "/");

  // The DressCard photo is the one element in a populated catalog that declares
  // a transition, so it is the only place the media query can be observed. The
  // h1 has nothing to disable and would pass whatever the stylesheet said.
  const motion = await page.getByRole("img", { name: GALLERY.name }).evaluate((el) => {
    const style = getComputedStyle(el);
    return { transitionDuration: style.transitionDuration, animationName: style.animationName };
  });
  expect(motion).toEqual({ transitionDuration: "0s", animationName: "none" });

  // scroll-snap is a positioning affordance, not motion (qa §8), and the blanket
  // reduced-motion reset is exactly where it gets killed by accident. Nothing
  // ships a snap container today, so this probes the RULE: an inline snap loses
  // to a `scroll-snap-type: none !important` in that block and to nothing else.
  const snap = await page.evaluate((mainId) => {
    const el = document.getElementById(mainId);
    if (el === null) return null;
    el.style.setProperty("scroll-snap-type", "x mandatory");
    const computed = getComputedStyle(el).scrollSnapType;
    el.style.removeProperty("scroll-snap-type");
    return computed;
  }, MAIN_ID);
  expect(snap, "the reduced-motion block is stripping scroll-snap along with motion").toBe(
    "x mandatory",
  );
});
