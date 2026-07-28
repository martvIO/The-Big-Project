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

// The class of defect, not the one string that caused it: the removed
// placeholders used guillemets, but "TODO-fill-me" is the same failure and
// passed a guillemet-only guard.
const PLACEHOLDER_TEXT = /[«»]|TODO|FIXME|למילוי|fill.me/i;

const COORDINATOR = {
  name: "דנה לוי",
  role: "רכזת נגישות",
  phone: "03-1234567",
  email: "accessibility@example.co.il",
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
  // findAll, not find: the boutique name is the site the statement covers AND —
  // while no platform coordinator is configured — the named accessibility
  // contact, so it legitimately appears more than once.
  await screen.findAllByText(BOUTIQUE.name);
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

  it("names a contact and reaches it, with the boutique standing in for an unset coordinator", async () => {
    await renderStatement();
    const phone = BOUTIQUE.profile.phone ?? "";

    expect(
      screen.getByRole("heading", { name: i18n.t("statement.coordinatorHeading") }),
    ).toBeInTheDocument();
    // ACCESSIBILITY_COORDINATOR is null until the platform operator supplies it,
    // so the boutique is named — a real service provider, not a placeholder.
    // Exactly two: the site the statement covers, and the named contact.
    expect(screen.getAllByText(BOUTIQUE.name)).toHaveLength(2);

    // Exactly two: the <dl> contact row and the reporting-channels list.
    const links = screen.getAllByRole("link", { name: phone });
    expect(links).toHaveLength(2);
    for (const link of links) {
      expect(link).toHaveAttribute("href", `tel:${phone}`);
      // A phone is a strong-LTR digit run in RTL prose; dir isolates it.
      expect(link).toHaveAttribute("dir", "ltr");
    }
  });

  // The failure this guards is specific and was live: the statement shipped
  // «שם רכז הנגישות — למילוי לפני העלייה לאוויר» in the <dl> AND inside two
  // real mailto: hrefs. A page that declares WCAG conformance while showing an
  // unfilled placeholder is itself the non-conformance it declares against, so
  // this asserts on the guillemet marker rather than on any one key.
  it("never renders an unfilled placeholder", async () => {
    const { container } = await renderStatement();

    expect(container.textContent).not.toMatch(PLACEHOLDER_TEXT);
    for (const link of screen.getAllByRole("link")) {
      const href = link.getAttribute("href") ?? "";
      expect(href).not.toMatch(PLACEHOLDER_TEXT);
      // Shape, not just absence-of-marker: a placeholder written without
      // guillemets ("TODO-fill-me") passed the old guard and still rendered a
      // dead mailto:. Every contact href must be a real address or number.
      if (href.startsWith("mailto:")) expect(href).toMatch(/^mailto:[^@\s]+@[^@\s]+\.[^@\s]+$/);
      if (href.startsWith("tel:")) expect(href).toMatch(/^tel:[+\d][\d\-\s()]*\d$/);
    }
  });

  it("renders the whole statement when the boutique fetch rejects", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    const { container } = render(<Accessibility />);
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });

    // Generic phrasing, never an error: a statement page that fails to render is
    // itself the accessibility failure it exists to declare.
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(i18n.t("statement.title"));
    // Twice: the site the statement covers, and — with no configured
    // coordinator and no API — the named accessibility contact.
    expect(screen.getAllByText(i18n.t("brand.title"))).toHaveLength(2);
    expect(screen.getByText(i18n.t("statement.conformanceBody"))).toBeInTheDocument();
    expect(screen.getByText(i18n.t("statement.limitsAlt"))).toBeInTheDocument();
    expect(screen.getByText(i18n.t("statement.updated"))).toBeInTheDocument();

    // With no API and no configured coordinator there is no reachable channel to
    // invent, so the reporting list is OMITTED rather than rendered empty — an
    // empty <ul> announces as "list, 0 items", which is worse than its absence.
    // The content lists (what-was-done, limits) still render, so assert on the
    // links instead of on list count.
    expect(screen.queryAllByRole("link", { name: BOUTIQUE.profile.phone ?? "" })).toHaveLength(
      0,
    );
    expect(container.textContent).not.toMatch(/[«»]/);
  });

  // The launch path. Until this round nothing rendered it, so the day the
  // operator fills in the constant a green suite would have gone red on a test
  // asserting "no links at all" — and the path of least resistance would have
  // been to relax that assertion rather than cover this branch.
  it("renders the configured platform coordinator when one is set", async () => {
    const { container } = render(<Accessibility coordinator={COORDINATOR} />);
    await screen.findByText(BOUTIQUE.name);

    expect(screen.getByText(i18n.t("statement.coordinatorIntro"))).toBeInTheDocument();
    expect(screen.getByText(COORDINATOR.name)).toBeInTheDocument();
    expect(screen.getByText(COORDINATOR.role)).toBeInTheDocument();

    // The phone is a strong-LTR digit run inside RTL prose.
    expect(screen.getByText(COORDINATOR.phone)).toHaveAttribute("dir", "ltr");

    const mailtos = screen.getAllByRole("link", { name: COORDINATOR.email });
    expect(mailtos).toHaveLength(2); // the <dl> row and the reporting list
    for (const link of mailtos) {
      expect(link).toHaveAttribute("href", `mailto:${COORDINATOR.email}`);
    }

    // Same guarantee as the unset branch: real values, never a placeholder.
    expect(container.textContent).not.toMatch(PLACEHOLDER_TEXT);
  });
});
