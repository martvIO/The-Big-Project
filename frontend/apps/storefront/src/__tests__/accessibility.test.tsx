import { render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, getBoutiqueOnce } from "../api";
import type { BoutiqueResponse } from "../api";
import { StorefrontLayout } from "../components/StorefrontLayout";
import i18n from "../i18n";
import { AccessibilityPage } from "../routes/AccessibilityPage";

// הצהרת נגישות is a legal obligation under IS 5568 §35, so these tests guard
// what an auditor checks: real document semantics, the declared standard, the
// menu the statement claims to ship, the limitations it admits, a reachable
// complaints contact, and a review date.
//
// THE RESPONSIBLE PARTY IS THE BOUTIQUE — there is no platform-operator
// coordinator layer, and the contact block is the boutique's own phone and
// Instagram off the layout-level fetch.

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ...actual,
    api: { listDresses: vi.fn(), getDress: vi.fn(), getBoutique: vi.fn() },
    getBoutiqueOnce: vi.fn(),
  };
});

const loadBoutique = vi.mocked(getBoutiqueOnce);

const BOUTIQUE: BoutiqueResponse = {
  name: "בוטיק אנבל",
  essence: null,
  description: null,
  phone: "052-1234567",
  address: "הרצל 12, תל אביב",
  maps_url: null,
  instagram: "boutique_annabel",
  hours: [],
  exceptions: [],
};

// The class of defect, not the one string that caused it: the removed
// placeholders used guillemets, but "TODO-fill-me" is the same failure and
// passed a guillemet-only guard.
const PLACEHOLDER_TEXT = /[«»]|TODO|FIXME|למילוי|fill.me/i;

const MENU_KEYS = [
  "menuContrast",
  "menuTextSize",
  "menuReadableFont",
  "menuUnderlineLinks",
  "menuStopMotion",
] as const;

beforeEach(() => {
  vi.clearAllMocks();
  loadBoutique.mockResolvedValue(BOUTIQUE);
  window.history.replaceState(null, "", "/accessibility");
});

// The statement is scoped to <main>: the layout's own footer and A11yMenu carry
// the same phone and the same tool labels, and counting those as if the
// statement rendered them would make every count assertion pass for free.
async function renderStatement() {
  const utils = render(
    <StorefrontLayout>
      <AccessibilityPage />
    </StorefrontLayout>,
  );
  // The boutique fetch only UPGRADES this page, so wait for it explicitly
  // rather than for anything the statement would render either way.
  await screen.findByText(BOUTIQUE.name);
  return { ...utils, main: screen.getByRole("main") };
}

describe("Accessibility statement — document semantics", () => {
  it("has exactly one h1", async () => {
    const { main } = await renderStatement();

    expect(within(main).getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(within(main).getByRole("heading", { level: 1 })).toHaveTextContent(
      i18n.t("statement.title"),
    );
  });

  it("never skips a heading level", async () => {
    const { main } = await renderStatement();

    const levels = within(main)
      .getAllByRole("heading")
      .map((heading) => Number(heading.tagName.slice(1)));

    expect(levels[0]).toBe(1);
    levels.forEach((level, index) => {
      // Climbing back up any distance is fine; only descending must be one at a time.
      if (index > 0) expect(level).toBeLessThanOrEqual(levels[index - 1] + 1);
    });
    // A flat h1 + h2 page would pass the rule above vacuously.
    expect(levels).toContain(3);
  });

  it("structures the body as real lists, not a wall of paragraphs", async () => {
    const { main } = await renderStatement();

    expect(within(main).getAllByRole("list").length).toBeGreaterThanOrEqual(3);
    expect(within(main).getByText(i18n.t("statement.doneKeyboard")).tagName).toBe("LI");
    expect(within(main).getByText(i18n.t("statement.menuStopMotion")).tagName).toBe("LI");
    expect(within(main).getByText(i18n.t("statement.limitsZoom")).tagName).toBe("LI");
  });
});

describe("Accessibility statement — the required parts", () => {
  it("names the standard it conforms to", async () => {
    const { main } = await renderStatement();

    expect(
      within(main).getByRole("heading", { name: i18n.t("statement.conformanceHeading") }),
    ).toBeInTheDocument();
    // The standard has to be named, and named precisely: "accessible" is not a
    // declaration, "ת״י 5568 ברמת AA / WCAG 2.0" is.
    const conformance = within(main).getByText(i18n.t("statement.conformanceBody"));
    expect(conformance).toHaveTextContent(/5568/);
    expect(conformance).toHaveTextContent(/AA/);
    expect(conformance).toHaveTextContent(/WCAG 2\.0/);
  });

  it("explains every tool in the accessibility menu", async () => {
    const { main } = await renderStatement();

    expect(
      within(main).getByRole("heading", { name: i18n.t("statement.menuHeading") }),
    ).toBeInTheDocument();
    // One entry per A11yMenu control — a statement that claims a menu and then
    // documents four of its five tools is a statement with a gap in it.
    for (const key of MENU_KEYS) {
      expect(within(main).getByText(i18n.t(`statement.${key}`)).tagName).toBe("LI");
    }
    expect(within(main).getByText(i18n.t("statement.menuNote"))).toBeInTheDocument();
  });

  it("admits the known limitations instead of claiming none", async () => {
    const { main } = await renderStatement();

    expect(
      within(main).getByRole("heading", { name: i18n.t("statement.limitsHeading") }),
    ).toBeInTheDocument();
    expect(within(main).getByText(i18n.t("statement.limitsZoom"))).toBeInTheDocument();
    expect(within(main).getByText(i18n.t("statement.limitsAlt"))).toBeInTheDocument();
    expect(within(main).getByText(i18n.t("statement.limitsNote"))).toBeInTheDocument();
  });

  it("carries a review date", async () => {
    const { main } = await renderStatement();

    expect(within(main).getByText(i18n.t("statement.updated"))).toHaveTextContent(/\d{4}/);
  });

  it("never renders an unfilled placeholder", async () => {
    const { main } = await renderStatement();

    expect(main.textContent).not.toMatch(PLACEHOLDER_TEXT);
    for (const link of within(main).getAllByRole("link")) {
      const href = link.getAttribute("href") ?? "";
      expect(href).not.toMatch(PLACEHOLDER_TEXT);
      // Shape, not just absence-of-marker: a placeholder written without
      // guillemets ("TODO-fill-me") passed the old guard and still rendered a
      // dead mailto:. Every contact href must be a real address or number.
      if (href.startsWith("mailto:")) expect(href).toMatch(/^mailto:[^@\s]+@[^@\s]+\.[^@\s]+$/);
      if (href.startsWith("tel:")) expect(href).toMatch(/^tel:[+\d][\d\-\s()]*\d$/);
    }
  });
});

describe("Accessibility statement — the complaints contact", () => {
  it("reaches the BOUTIQUE on its own phone and Instagram", async () => {
    const { main } = await renderStatement();
    const phone = BOUTIQUE.phone ?? "";
    const instagram = BOUTIQUE.instagram ?? "";

    expect(
      within(main).getByRole("heading", { name: i18n.t("statement.coordinatorHeading") }),
    ).toBeInTheDocument();
    expect(within(main).getByText(i18n.t("statement.coordinatorIntro"))).toBeInTheDocument();

    // Twice each: the <dl> contact row, and the reporting-channels list.
    const phoneLinks = within(main).getAllByRole("link", { name: phone });
    expect(phoneLinks).toHaveLength(2);
    for (const link of phoneLinks) {
      expect(link).toHaveAttribute("href", `tel:${phone}`);
      // A phone number is a strong-LTR digit run in RTL prose; bdi isolates it.
      expect(link.querySelector("bdi")).toHaveAttribute("dir", "ltr");
    }

    const instagramLinks = within(main).getAllByRole("link", { name: `@${instagram}` });
    expect(instagramLinks).toHaveLength(2);
    for (const link of instagramLinks) {
      expect(link).toHaveAttribute("href", `https://instagram.com/${instagram}`);
    }

    // Which site the statement covers — the boutique's real name, not a generic one.
    expect(within(main).getByText(BOUTIQUE.name)).toBeInTheDocument();
  });

  it("still renders the whole statement when the boutique fetch rejects", async () => {
    loadBoutique.mockRejectedValue(new ApiError(503, "UNKNOWN", "Service unavailable."));
    render(
      <StorefrontLayout>
        <AccessibilityPage />
      </StorefrontLayout>,
    );
    await waitFor(() => {
      expect(loadBoutique).toHaveBeenCalled();
    });
    const main = screen.getByRole("main");

    // A statement page that renders a spinner or an error instead of the
    // statement is itself the accessibility failure it exists to declare.
    expect(screen.queryByRole("alert")).toBeNull();
    expect(within(main).getByRole("heading", { level: 1 })).toHaveTextContent(
      i18n.t("statement.title"),
    );
    expect(within(main).getByText(i18n.t("statement.conformanceBody"))).toBeInTheDocument();
    expect(within(main).getByText(i18n.t("statement.limitsAlt"))).toBeInTheDocument();
    expect(within(main).getByText(i18n.t("statement.updated"))).toBeInTheDocument();

    // Twice: the site the statement covers, and — with no reachable number to
    // name — the contact row falls back to the same generic name.
    expect(within(main).getAllByText(i18n.t("catalog.essenceFallback"))).toHaveLength(2);
    // With no channel to offer, the reporting list is OMITTED rather than
    // rendered empty: an empty <ul> announces as "list, 0 items".
    expect(within(main).queryAllByRole("link", { name: BOUTIQUE.phone ?? "" })).toHaveLength(0);
    expect(main.textContent).not.toMatch(PLACEHOLDER_TEXT);
  });
});
