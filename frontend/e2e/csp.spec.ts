import { readFileSync } from "node:fs";
import { test, expect } from "@playwright/test";
import type { Page } from "@playwright/test";

// B2's ACCEPTANCE CRITERION — the real built bundle, in a real Chromium, under
// the real policy. Not the header assertions in
// `Backend/tests/test_security_headers.py`, which prove the string and nothing
// about whether the app survives it.
//
// ⚠ **WHY THE POLICY ARRIVES BY ROUTE INTERCEPTION AND NOT FROM THE SERVER.**
// `playwright.config.ts` serves both apps through `vite preview`, so FastAPI —
// and therefore `SecurityHeadersMiddleware` — is never in the e2e request path.
// A spec that simply loaded the page and asserted on a `Content-Security-Policy`
// header would assert the ABSENCE of one and pass vacuously forever. So the
// document response is intercepted and the header is injected from
// `fixtures/csp.txt`, whose single policy line
// `test_the_e2e_fixture_matches_the_emitted_policy` pins BYTE-FOR-BYTE against
// `build_csp(Settings(...))`. Drift between what the browser is tested under and
// what the middleware emits is a red backend test, not a silent divergence.
//
// ⚠ **THE TRIPWIRE THIS FILE EXISTS TO BE.** `assetsInlineLimit` defaults to
// 4096, so the day someone imports a small SVG it becomes a `data:` URI inside
// the emitted CSS and `img-src` needs `data:`. A header-string test cannot see
// that. This one can, because a browser applies the policy to the artifact. If
// it reds on an inlined asset, the fix is to widen the policy by ONE source with
// a comment naming the asset — never to weaken the assertions below.
//
// ⚠ **THE LIMIT, STATED SO IT IS NEVER OVERCLAIMED.** Neither app reaches its
// API here: `/storefront/*` and `/manage/*` proxy to :8000 and fail, exactly as
// in `a11y.spec.ts`'s no-data pass. What IS exercised is the whole of what the
// BUNDLE loads — the module script and its chunks (`script-src`), the emitted
// stylesheet (`style-src`), the woff2 subsets (`font-src`) and every image the
// shell paints (`img-src`). Dress photos from the media bucket are out of reach
// of any e2e harness, real header or not, because there is no bucket to serve
// them.

const STOREFRONT = "http://localhost:4173";
// Trailing /manage/ because apps/manage builds with base: "/manage/".
const MANAGE = "http://localhost:4174/manage/";

// The fixture is a commented file with exactly one policy line. Reading it
// strictly — and THROWING rather than falling back to a default — is what stops
// a mangled fixture from quietly turning both tests below into a scan under no
// policy at all.
function readPolicy(): string {
  const raw = readFileSync(new URL("./fixtures/csp.txt", import.meta.url), "utf8");
  const lines = raw
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line !== "" && !line.startsWith("#"));
  if (lines.length !== 1) {
    throw new Error(
      `fixtures/csp.txt must hold exactly one policy line; found ${String(lines.length)}.`,
    );
  }
  return lines[0];
}

const POLICY = readPolicy();

interface CspProbe {
  violations: () => Promise<string[]>;
  consoleErrors: string[];
}

// Installs the instrument BEFORE any page script runs, which is the same
// discipline F61's MutationObserver finding forced: a listener attached after
// the action observes nothing. `addInitScript` runs at document creation, so a
// violation raised while the very first `<script type="module">` is being
// evaluated is still caught.
async function armCsp(page: Page): Promise<CspProbe> {
  await page.addInitScript(() => {
    const collected: string[] = [];
    (window as unknown as { __cspViolations: string[] }).__cspViolations = collected;
    document.addEventListener("securitypolicyviolation", (event) => {
      collected.push(`${event.effectiveDirective} ← ${event.blockedURI}`);
    });
  });

  // A CSP refusal also logs to the console with the directive that refused it,
  // which is the fastest read on what to widen. Carried into the failure
  // message rather than left in a terminal nobody sees on CI.
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  // Only the DOCUMENT response carries the policy, because that is the only
  // response a browser reads it from. Every other request falls through
  // untouched, so a failing API proxy stays the ordinary outage the app already
  // handles rather than a thrown `route.fetch()`.
  await page.route("**/*", async (route) => {
    if (route.request().resourceType() !== "document") {
      await route.fallback();
      return;
    }
    const response = await route.fetch();
    await route.fulfill({
      response,
      headers: { ...response.headers(), "content-security-policy": POLICY },
    });
  });

  return {
    violations: () =>
      page.evaluate(() => (window as unknown as { __cspViolations: string[] }).__cspViolations),
    consoleErrors,
  };
}

// **ANTI-VACUITY LEG 2, and it is not optional either.** If the injection
// silently failed — a route that never matched, a header name the browser
// ignored — the page loads perfectly, raises zero violations and this file
// passes while testing nothing. An inline `<script>` is refused by
// `script-src 'self'` under the real policy and RUNS under no policy, so it is a
// direct measurement that the header took effect. Called AFTER the violation
// snapshot is taken, since the probe deliberately raises one of its own.
async function inlineScriptRan(page: Page): Promise<boolean> {
  return page.evaluate(() => {
    const script = document.createElement("script");
    script.textContent = "window.__cspProbeRan = true;";
    document.head.appendChild(script);
    return (window as unknown as { __cspProbeRan?: boolean }).__cspProbeRan === true;
  });
}

async function assertCleanUnderPolicy(page: Page, probe: CspProbe): Promise<void> {
  const violations = await probe.violations();
  const enforced = !(await inlineScriptRan(page));

  expect(
    enforced,
    "the injected Content-Security-Policy never took effect — every assertion in this test was vacuous",
  ).toBe(true);
  expect(
    violations,
    `console errors: ${probe.consoleErrors.join(" | ") || "(none)"}`,
  ).toEqual([]);
}

test("csp: the storefront bundle raises zero violations under the real policy", async ({
  page,
}) => {
  const probe = await armCsp(page);
  await page.goto(STOREFRONT);

  // **ANTI-VACUITY LEG 1.** A policy that blocks the module script leaves an
  // empty `<div id="root">`, and a blank page raises zero FURTHER violations —
  // without this the test would pass hardest exactly when the policy is most
  // broken. CatalogPage renders its h1 even when the boutique fetch fails
  // (`CatalogPage.tsx:141-147`), so this measures React, not the API.
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  // Forces the woff2 subsets to be requested and settled, so `font-src` is
  // actually exercised rather than merely declared.
  await page.evaluate(() => document.fonts.ready);

  await assertCleanUnderPolicy(page, probe);
});

test("csp: the manage shell raises zero violations under the real policy", async ({ page }) => {
  const probe = await armCsp(page);
  await page.goto(MANAGE);

  // The login screen is what the console renders when `api.me()` rejects, and
  // its h1 is the MODRYN lockup — which carries an <img>, so `img-src` is
  // exercised on this shell and not only asserted.
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByRole("button", { name: "כניסה" })).toBeVisible();
  await page.evaluate(() => document.fonts.ready);

  await assertCleanUnderPolicy(page, probe);
});
