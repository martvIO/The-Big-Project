import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import { resetBoutiqueCache } from "../api";
import type { PublicBoutiqueResponse } from "../api";
import i18n from "../i18n";

// The chrome around the router outlet: who reserves the fixed CTA bar's
// footprint, and which routes claim one at all.
//
// Both are measured through the design tokens the layout is derived from rather
// than through a rendered pixel — jsdom lays nothing out, and the tokens are the
// contract these two files share with packages/ui.

const BOUTIQUE: PublicBoutiqueResponse = {
  name: "בוטיק אלמה",
  profile: { phone: "052-1234567", address: null, description: null, maps_url: null },
  rules: [],
  exceptions: [],
};

const CTA_RESERVATION = "--cta-bar-height";
const A11Y_LIFT = "--space-a11y-clearance";

// The element wrapping BOTH <main> and <footer>. The footer is a sibling of
// <main>, so this is the only element that can reserve space on its behalf.
function pageShell(): HTMLElement {
  const shell = screen.getByRole("main").parentElement;
  if (shell === null) throw new Error("<main> has no page shell around it");
  return shell;
}

function a11yMenuRoot(): HTMLElement {
  const trigger = screen.getByRole("button", { name: i18n.t("a11y.menu.trigger") });
  const root = trigger.parentElement;
  if (root === null) throw new Error("the A11yMenu trigger has no positioned root");
  return root;
}

function renderAt(pathname: string) {
  window.history.replaceState(null, "", pathname);
  return render(<App />);
}

beforeEach(() => {
  resetBoutiqueCache();
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve(BOUTIQUE) })),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  window.history.replaceState(null, "", "/");
});

describe("App page shell — fixed CTA bar footprint", () => {
  it.each([
    ["/", true],
    ["/dress/d1", true],
    ["/about", false],
    ["/accessibility", false],
  ])("reserves the bar's footprint on %s: %s", (pathname, reserved) => {
    renderAt(pathname);

    // The reservation must sit OUTSIDE <main>: the statutory הצהרת נגישות link
    // lives in the footer, and padding on a page div inside <main> cannot clear
    // a bar that overlaps its sibling.
    expect(pageShell().className.includes(CTA_RESERVATION)).toBe(reserved);
    expect(screen.getByRole("main").className).not.toContain(CTA_RESERVATION);
    // And it releases at 768, where the bar goes inline — a permanent gutter on
    // desktop is its own defect.
    if (reserved) expect(pageShell().className).toContain("max-md:");
  });

  it("keeps the accessibility statement link inside the shell that reserves for it", () => {
    renderAt("/");

    const link = screen.getByRole("link", { name: i18n.t("a11y.statement") });
    expect(pageShell().contains(link)).toBe(true);
  });
});

describe("App page shell — A11yMenu lift", () => {
  it.each([
    ["/", true],
    ["/dress/d1", true],
    ["/about", false],
    ["/accessibility", false],
  ])("lifts the menu above a booking bar on %s: %s", (pathname, lifted) => {
    renderAt(pathname);

    // /about ships a static inline button and no bar, so lifting the menu 92px
    // there floats it over content that reserved only for the unlifted button
    // (PRE-2). /accessibility ships no CTA at all.
    expect(a11yMenuRoot().className.includes(A11Y_LIFT)).toBe(lifted);
  });
});
