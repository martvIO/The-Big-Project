import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { resetBoutiqueCache } from "../api";
import type { PublicBoutiqueResponse } from "../api";
import i18n from "../i18n";
import { Accessibility } from "../pages/Accessibility";

// הצהרת נגישות is a legal obligation under IS 5568 §35, so these tests guard the
// three things an auditor checks first — real document semantics, a named
// coordinator who can actually be contacted, and the failure mode that would
// turn the compliance page into a compliance breach: the API being down.

const BOUTIQUE: PublicBoutiqueResponse = {
  name: "בוטיק אנבל",
  profile: {
    phone: "052-1234567",
    address: "הרצל 12, תל אביב",
    description: null,
    maps_url: null,
  },
  rules: [],
  exceptions: [],
};

const fetchMock = vi.fn();

beforeEach(() => {
  // The boutique promise is module-level and shared across the page load; without
  // this every test after the first would replay the first one's response.
  resetBoutiqueCache();
  fetchMock.mockReset();
  fetchMock.mockResolvedValue({ ok: true, json: () => Promise.resolve(BOUTIQUE) });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

// The fetch only upgrades the copy, but a state update landing after the test
// body ends is a leak into the next test — so settle it before asserting.
async function renderStatement() {
  const utils = render(<Accessibility />);
  await screen.findByText(BOUTIQUE.name);
  return utils;
}

describe("Accessibility statement page", () => {
  it("has exactly one h1", async () => {
    await renderStatement();

    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(i18n.t("statement.title"));
  });

  it("never skips a heading level", async () => {
    await renderStatement();

    const levels = screen.getAllByRole("heading").map((heading) => Number(heading.tagName.slice(1)));

    expect(levels[0]).toBe(1);
    levels.forEach((level, index) => {
      // Climbing back up any distance is fine; only descending must be one at a time.
      if (index > 0) expect(level).toBeLessThanOrEqual(levels[index - 1] + 1);
    });
    // A flat h1 + h2 page would pass the rule above vacuously.
    expect(levels).toContain(3);
  });

  it("structures the body as real lists, not a wall of paragraphs", async () => {
    await renderStatement();

    expect(screen.getAllByRole("list").length).toBeGreaterThanOrEqual(3);
    expect(screen.getByText(i18n.t("statement.doneKeyboard")).tagName).toBe("LI");
    expect(screen.getByText(i18n.t("statement.menuStopMotion")).tagName).toBe("LI");
    expect(screen.getByText(i18n.t("statement.limitsZoom")).tagName).toBe("LI");
  });

  it("names an accessibility coordinator and links the address as a real mailto", async () => {
    await renderStatement();
    const email = i18n.t("statement.coordinatorEmail");

    expect(
      screen.getByRole("heading", { name: i18n.t("statement.coordinatorHeading") }),
    ).toBeInTheDocument();
    expect(screen.getByText(i18n.t("statement.coordinatorName"))).toBeInTheDocument();
    expect(screen.getByText(i18n.t("statement.coordinatorRole"))).toBeInTheDocument();

    const links = screen.getAllByRole("link", { name: email });
    expect(links.length).toBeGreaterThan(0);
    for (const link of links) {
      expect(link).toHaveAttribute("href", `mailto:${email}`);
    }
  });

  it("isolates the coordinator phone as LTR inside the RTL prose", async () => {
    await renderStatement();

    expect(screen.getByText(i18n.t("statement.coordinatorPhone"))).toHaveAttribute("dir", "ltr");
  });

  it("offers the boutique's own phone as a reachable reporting channel", async () => {
    await renderStatement();
    const phone = BOUTIQUE.profile.phone ?? "";

    const link = screen.getByRole("link", { name: phone });
    expect(link).toHaveAttribute("href", `tel:${phone}`);
    expect(link).toHaveAttribute("dir", "ltr");
  });

  it("renders the whole statement when the boutique fetch rejects", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    render(<Accessibility />);
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });

    // Generic phrasing, never an error: a statement page that fails to render is
    // itself the accessibility failure it exists to declare.
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(i18n.t("statement.title"));
    expect(screen.getByText(i18n.t("brand.title"))).toBeInTheDocument();
    expect(screen.getByText(i18n.t("statement.conformanceBody"))).toBeInTheDocument();
    expect(screen.getByText(i18n.t("statement.limitsAlt"))).toBeInTheDocument();
    expect(screen.getByText(i18n.t("statement.updated"))).toBeInTheDocument();

    // The coordinator stays contactable with no API at all — that is the point.
    const links = screen.getAllByRole("link", { name: i18n.t("statement.coordinatorEmail") });
    expect(links.length).toBeGreaterThan(0);
  });
});
