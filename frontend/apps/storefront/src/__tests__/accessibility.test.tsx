import { render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, api, getBoutiqueOnce } from "../api";
import type { BoutiqueResponse, StorefrontDetail } from "../api";
import { StorefrontLayout } from "../components/StorefrontLayout";
import i18n from "../i18n";
import { AccessibilityPage } from "../routes/AccessibilityPage";
import { DressPage } from "../routes/DressPage";

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

  it("describes the alt text the dress page actually renders", async () => {
    const dress: StorefrontDetail = {
      id: "d1",
      name: "ורד",
      description: null,
      price_agorot: null,
      reserved: false,
      sizes: [],
      media: [
        { url: "/1.jpg", url_expires_at: null },
        { url: "/2.jpg", url_expires_at: null },
        { url: "/3.jpg", url_expires_at: null },
      ],
    };
    vi.mocked(api.getDress).mockResolvedValue(dress);
    render(
      <StorefrontLayout>
        <DressPage dressId="d1" />
      </StorefrontLayout>,
    );

    // What the gallery's main photo really announces, read off the render — not
    // asserted from the statement's own wording.
    const image = await screen.findByAltText(i18n.t("gallery.imageOf", { n: 1, total: 3 }));
    const spokenAlt = image.getAttribute("alt") ?? "";
    const limitsAlt = i18n.t("statement.limitsAlt");

    // A statement that describes behaviour the site does not have is itself a
    // compliance defect: F10 replaced the dress-name alt with the position, so
    // the name is no longer announced twice.
    expect(limitsAlt).toContain(spokenAlt);
    expect(limitsAlt).not.toMatch(/פעמיים/);
    // The honest half stays: the card's alt is still only the dress name.
    expect(limitsAlt).toMatch(/שם השמלה/);
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

  it("offers a phone-only boutique its phone, and no empty second row", async () => {
    loadBoutique.mockResolvedValue({ ...BOUTIQUE, instagram: null });
    const { main } = await renderStatement();

    expect(within(main).getAllByRole("link", { name: BOUTIQUE.phone ?? "" })).toHaveLength(2);
    // A <dt> with nothing behind it is a labelled dead end: the Instagram row
    // must be absent, not present and empty.
    expect(main.querySelectorAll("dt")).toHaveLength(1);
    expect(
      within(main).queryByText(i18n.t("statement.coordinatorInstagramLabel")),
    ).toBeNull();
    for (const term of main.querySelectorAll("dt")) {
      expect(term.parentElement?.querySelector("dd")?.textContent?.trim()).toBeTruthy();
    }
  });

  it("names a real channel when the boutique published none", async () => {
    // A newly provisioned tenant: phone is str | None on the wire, and this
    // page has no error state, so this is also every failed boutique fetch.
    loadBoutique.mockResolvedValue({ ...BOUTIQUE, phone: null, instagram: null });
    const { main } = await renderStatement();

    // IS 5568 §35 wants a reachable contact. With nothing to link, the
    // statement says so and points at the boutique — it never renders a
    // statutory contact section that is empty, nor a <dt> with no value.
    expect(
      within(main).getByText(
        i18n.t("statement.coordinatorNoChannel", { name: BOUTIQUE.name }),
      ),
    ).toBeInTheDocument();
    expect(main.querySelectorAll("dt")).toHaveLength(0);
    expect(main.querySelectorAll("dl")).toHaveLength(0);
    expect(within(main).queryAllByRole("link", { name: BOUTIQUE.phone ?? "" })).toHaveLength(0);
    expect(main.textContent).not.toMatch(PLACEHOLDER_TEXT);
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

    // Once: the site the statement covers. The contact block used to reuse the
    // same generic name as if it were a phone value, which rendered a labelled
    // phone row a visitor cannot ring — a dead statutory contact.
    expect(within(main).getAllByText(i18n.t("catalog.essenceFallback"))).toHaveLength(1);
    expect(main.querySelectorAll("dt")).toHaveLength(0);
    // Instead the section names where to turn, in Hebrew, with no dangling label.
    expect(
      within(main).getByText(
        i18n.t("statement.coordinatorNoChannel", { name: i18n.t("catalog.essenceFallback") }),
      ),
    ).toBeInTheDocument();
    // With no channel to offer, the reporting list is OMITTED rather than
    // rendered empty: an empty <ul> announces as "list, 0 items".
    expect(within(main).queryAllByRole("link", { name: BOUTIQUE.phone ?? "" })).toHaveLength(0);
    expect(main.textContent).not.toMatch(PLACEHOLDER_TEXT);
  });
});
