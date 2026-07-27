import { test, expect } from "@playwright/test";
import type { Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const STOREFRONT = "http://localhost:4173";
const MANAGE = "http://localhost:4174";

// Nothing here intercepts the API, and that is the point. `vite preview` proxies
// /storefront/* to :8000 with no backend listening, so these are the API-is-down
// pass: the storefront still has to be a valid, navigable, accessible document
// when the boutique's data never arrives. storefront.spec.ts covers the same
// routes with data behind them.
async function gotoCatalogWithApiDown(page: Page) {
  await page.goto(STOREFRONT);
  // Wait for the failure to land, so nothing below measures a skeleton.
  await expect(page.getByRole("alert")).toContainText("לא הצלחנו לטעון את הקולקציה כרגע.");
}

test("storefront (API down): zero axe A/AA violations", async ({ page }) => {
  await gotoCatalogWithApiDown(page);
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(results.violations).toEqual([]);
});

test("storefront: Hebrew document title + cream color-scheme (no forced dark)", async ({ page }) => {
  await page.goto(STOREFRONT);
  await expect(page).toHaveTitle(/[֐-׿]/); // contains Hebrew
  const scheme = await page.evaluate(() => getComputedStyle(document.documentElement).colorScheme);
  expect(scheme.trim()).toContain("light");
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

test("storefront (API down): no horizontal scroll at 375 / 768 / 1440", async ({ page }) => {
  for (const width of [375, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await gotoCatalogWithApiDown(page);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
    );
    expect(overflow, `horizontal scroll at ${width}px`).toBe(false);
  }
});

test("storefront (API down): keeps its h1 and honours reduced motion", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await gotoCatalogWithApiDown(page);

  // BoutiqueHeader renders unconditionally and falls back to the brand title, so
  // an outage costs the page its dresses, never its h1 — which axe's
  // page-has-heading-one wants and the skip link needs somewhere to land in.
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("חנות הכלות");

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
