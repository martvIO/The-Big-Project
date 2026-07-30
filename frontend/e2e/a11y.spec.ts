import { test, expect } from "@playwright/test";
import type { Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const STOREFRONT = "http://localhost:4173";
const MANAGE = "http://localhost:4174";

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
