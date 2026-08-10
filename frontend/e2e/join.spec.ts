import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { JOIN, installPlatformApi, ok, refuse } from "./fixtures/platform";

// F26 Screen B — the boutique owner's redemption journey, and the ONLY screen in
// `apps/platform` a non-operator ever opens.
//
// ⚠ **NO OPERATOR SESSION IS INSTALLED ANYWHERE IN THIS FILE.** `operator: null`
// makes `/platform/auth/me` answer 401, and every test below asserts the journey
// completes anyway. If a future edit made the join path depend on a session,
// these would go red rather than quietly requiring one.
//
// ⚠ **`page.goto(JOIN)` EXERCISES THE SECOND `_serve_file` PATH.** The bundle is
// served at exactly `/platform` and exactly `/platform/join`; a subtree fallback
// was deliberately not added, so this URL loading at all is part of the claim.
//
// The axe gate is a LEGAL requirement (IS 5568 / WCAG 2.0 AA, pre-decided #38).

const PREVIEW = { slug: "chen", name: "בוטיק של חן", owner_email: "chen@x.example" };
// ⚠ THE REDEEM HOST IS DELIBERATELY NOT `chen.modryn.co.il`. The server composes
// `manage_url` from `settings.base_domain` — `localtest.me` in dev, a
// deployment's own domain in staging and production — so a stub that echoes the
// literal production host back cannot tell a panel that RENDERS the server's
// answer from one that rebuilds `https://${slug}.modryn.co.il/manage` itself.
// The two assertions below are the feature's only actionable link; this host
// appears nowhere in `JoinPanel.tsx`, so they now fail if it ever does again.
const REDEEMED = { slug: "chen", manage_url: "https://chen.example.test/manage" };
const CODE = "s3cret-invite-code-value";

async function axeClean(page: Page, label: string): Promise<void> {
  // Settle bounded animations before scanning; skip the infinite ones, whose
  // `.finished` never resolves and would hang the scan (platform.spec.ts states
  // the whole argument, including the false contrast red it prevents).
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

test("join: no code lands on the code step and fires no request", async ({ page }) => {
  const recorder = await installPlatformApi(page, { operator: null });
  await page.goto(JOIN);
  await expect(page.getByRole("heading", { name: "הזנת קוד הזמנה", level: 2 })).toBeVisible();
  // Not one call — least of all `me()`, which for a redeemer is a guaranteed 401.
  expect(recorder.all).toEqual([]);
});

test("join: a pasted FULL LINK is accepted, not just a bare code", async ({ page }) => {
  // The owner was given a link, so a link is what she pastes. Rejecting it would
  // spend a failures-only limiter attempt on a formatting mistake.
  const recorder = await installPlatformApi(page, {
    operator: null,
    replies: { "POST /platform/join/invite": [ok(PREVIEW)] },
  });
  await page.goto(JOIN);
  await page
    .getByLabel("קוד ההזמנה")
    .fill(`https://admin.modryn.co.il/platform/join#code=${CODE}`);
  await page.getByRole("button", { name: "המשך" }).click();

  await expect(page.getByRole("heading", { name: "הקמת הבוטיק", level: 2 })).toBeVisible();
  const lookups = recorder.of("/platform/join/invite");
  expect(lookups).toHaveLength(1);
});

test("join: an invalid code shows the one Hebrew sentence and never the server's English", async ({
  page,
}) => {
  // D5: unknown / expired / redeemed / revoked are ONE refusal, and the UI must
  // not undo that by distinguishing them.
  await installPlatformApi(page, {
    operator: null,
    replies: { "POST /platform/join/invite": [refuse(404, "invalid_invite")] },
  });
  await page.goto(`${JOIN}#code=nope`);
  await expect(page.getByRole("alert")).toContainText(
    "ההזמנה אינה תקפה. אפשר לבקש מ‑MODRYN הזמנה חדשה.",
  );
  await expect(page.getByRole("heading", { name: "הזנת קוד הזמנה", level: 2 })).toBeVisible();
  expect(await page.locator("body").innerText()).not.toContain("from the fixture");
});

test("join: the three facts are read-only and the only input is the password", async ({ page }) => {
  // ⚠ THE ASSERTION THAT CARRIES D2. A slug or email box here would make a
  // leaked link a bearer token for "become the owner of a boutique of my
  // choosing".
  await installPlatformApi(page, {
    operator: null,
    replies: { "POST /platform/join/invite": [ok(PREVIEW)] },
  });
  await page.goto(`${JOIN}#code=${CODE}`);
  await expect(page.getByRole("heading", { name: "הקמת הבוטיק", level: 2 })).toBeVisible();
  await expect(page.getByText("בוטיק של חן")).toBeVisible();
  await expect(page.getByText("chen.modryn.co.il")).toBeVisible();
  await expect(page.getByText("chen@x.example")).toBeVisible();
  await expect(page.locator("input")).toHaveCount(1);
  await expect(page.locator("input")).toHaveAttribute("type", "password");
  // The Latin runs carry their isolate; the Hebrew name is NOT forced LTR.
  await expect(page.locator("bdi[dir='ltr']", { hasText: "chen.modryn.co.il" })).toBeVisible();
  await expect(page.locator("bdi[dir='ltr']", { hasText: "בוטיק של חן" })).toHaveCount(0);
});

test("join: a weak password is refused INTO the field, then a good one succeeds", async ({
  page,
}) => {
  await installPlatformApi(page, {
    operator: null,
    replies: {
      "POST /platform/join/invite": [ok(PREVIEW)],
      "POST /platform/join/redeem": [refuse(400, "password_too_short"), ok(REDEEMED)],
    },
  });
  await page.goto(`${JOIN}#code=${CODE}`);
  await expect(page.getByRole("heading", { name: "הקמת הבוטיק", level: 2 })).toBeVisible();

  const password = page.getByLabel("בחירת סיסמה");
  // `minLength` is an ATTRIBUTE, never a mirrored constant — the browser's own
  // constraint, and the server is still the authority.
  await expect(password).toHaveAttribute("minlength", "10");
  await expect(password).toHaveAttribute("autocomplete", "new-password");

  await password.fill("shorter-but-past-minlength");
  await page.getByRole("button", { name: "הקמת הבוטיק" }).click();
  // Into the FIELD's error slot, wired by aria-describedby — not the form alert.
  const fieldError = page.getByRole("alert");
  await expect(fieldError).toContainText("הסיסמה חייבת להכיל לפחות 10 תווים.");
  await expect(password).toHaveAttribute("aria-invalid", "true");
  const describedBy = await password.getAttribute("aria-describedby");
  expect(describedBy).toContain(await fieldError.getAttribute("id"));

  await password.fill("a-genuinely-long-password");
  await page.getByRole("button", { name: "הקמת הבוטיק" }).click();

  await expect(page.getByRole("heading", { name: "הבוטיק מוכן", level: 2 })).toBeVisible();
  const manage = page.getByRole("link", { name: "כניסה לניהול הבוטיק" });
  await expect(manage).toHaveAttribute("href", "https://chen.example.test/manage");
  // The host she READS is parsed out of that same string rather than rebuilt, so
  // the sentence and the button can never point at two different boutiques.
  await expect(page.locator("bdi[dir='ltr']", { hasText: "chen.example.test" })).toBeVisible();
  // The password is never repeated back, and no payment copy appears on a screen
  // in a feature that ships no payment code (D7).
  const rendered = await page.locator("body").innerText();
  expect(rendered).not.toContain("a-genuinely-long-password");
  expect(rendered).not.toMatch(/תשלום|מקדמה|סליקה/);
  expect(rendered).not.toContain("!");
});

test("join: the document is Hebrew and RTL on this path too", async ({ page }) => {
  await installPlatformApi(page, { operator: null });
  await page.goto(JOIN);
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.locator("html")).toHaveAttribute("lang", "he");
});

test("join (axe): the code step, the claim step and the success screen", async ({ page }) => {
  await installPlatformApi(page, {
    operator: null,
    replies: {
      "POST /platform/join/invite": [ok(PREVIEW)],
      "POST /platform/join/redeem": [ok(REDEEMED)],
    },
  });

  await page.goto(JOIN);
  await expect(page.getByRole("heading", { name: "הזנת קוד הזמנה", level: 2 })).toBeVisible();
  await axeClean(page, "join code step");

  await page.getByLabel("קוד ההזמנה").fill(CODE);
  await page.getByRole("button", { name: "המשך" }).click();
  await expect(page.getByRole("heading", { name: "הקמת הבוטיק", level: 2 })).toBeVisible();
  await axeClean(page, "join claim step");

  await page.getByLabel("בחירת סיסמה").fill("a-genuinely-long-password");
  await page.getByRole("button", { name: "הקמת הבוטיק" }).click();
  await expect(page.getByRole("heading", { name: "הבוטיק מוכן", level: 2 })).toBeVisible();
  await axeClean(page, "join success");
});

test("join (axe): the code step carrying a refusal", async ({ page }) => {
  await installPlatformApi(page, {
    operator: null,
    replies: { "POST /platform/join/invite": [refuse(429, "TOO_MANY_ATTEMPTS")] },
  });
  await page.goto(`${JOIN}#code=${CODE}`);
  // 429 is matched on STATUS, LoginPanel's shipped precedent for the same
  // refusal — the body's code is a wire constant, not a copy key.
  await expect(page.getByRole("alert")).toContainText(
    "יותר מדי ניסיונות. אפשר לנסות שוב בעוד מספר דקות.",
  );
  await axeClean(page, "join code step refused");
});
