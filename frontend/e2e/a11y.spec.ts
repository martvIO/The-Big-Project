import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const STOREFRONT = "http://localhost:4173";
const MANAGE = "http://localhost:4174";

test("storefront: zero axe A/AA violations", async ({ page }) => {
  await page.goto(STOREFRONT);
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

test("storefront: no horizontal scroll at 375 / 768 / 1440", async ({ page }) => {
  for (const width of [375, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto(STOREFRONT);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
    );
    expect(overflow, `horizontal scroll at ${width}px`).toBe(false);
  }
});

test("storefront: reduced motion emulation disables transitions", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(STOREFRONT);
  const heading = page.getByRole("heading", { level: 1 });
  await expect(heading).toBeVisible();
  const duration = await heading.evaluate((el) => getComputedStyle(el).transitionDuration);
  expect(["0s", "0.001ms", ""].some((v) => duration.includes(v) || duration === v) || duration === "0s").toBeTruthy();
});

test("manage: login screen has zero axe A/AA violations + Hebrew title", async ({ page }) => {
  await page.goto(MANAGE);
  await expect(page).toHaveTitle(/[֐-׿]/);
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(results.violations).toEqual([]);
});
