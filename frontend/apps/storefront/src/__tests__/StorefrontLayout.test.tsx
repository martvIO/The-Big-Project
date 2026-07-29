import { render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { resetBoutiqueCache } from "../api";
import type { BoutiqueResponse } from "../api";
import { StorefrontLayout, useBoutique } from "../components/StorefrontLayout";
import i18n from "../i18n";

// The shell every route renders inside: the skip link's target, the focus
// target the router moves to, the statutory footer, and the ONE getBoutique()
// call the whole app shares.

const BOUTIQUE: BoutiqueResponse = {
  name: "בוטיק אלמה",
  essence: null,
  description: null,
  phone: "052-1234567",
  address: null,
  maps_url: null,
  instagram: "alma.bridal",
  hours: [],
  exceptions: [],
};

// A brand-new tenant: no phone, no Instagram. The footer must not render an
// orphan separator or an href="tel:null" for either.
const BARE_BOUTIQUE: BoutiqueResponse = { ...BOUTIQUE, phone: null, instagram: null };

const CTA_RESERVATION = "--cta-bar-height";
const A11Y_LIFT = "--space-a11y-clearance";
const A11Y_FOOTPRINT = "--space-a11y-footprint";

// Renders the layout's own load state as a heading, so every test can await a
// settled fetch through the accessibility tree instead of a bare flush.
function LoadProbe() {
  const { boutique, loading } = useBoutique();
  return <h2>{loading ? "טוען" : (boutique?.name ?? "ללא שם")}</h2>;
}

function stubFetch(body: BoutiqueResponse) {
  const fetchMock = vi.fn((_path: string, _init?: RequestInit) =>
    Promise.resolve(
      new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderAt(pathname: string, body: BoutiqueResponse = BOUTIQUE) {
  window.history.replaceState(null, "", pathname);
  const fetchMock = stubFetch(body);
  render(
    <StorefrontLayout>
      <LoadProbe />
    </StorefrontLayout>,
  );
  return fetchMock;
}

// Awaiting the boutique's own name proves the single fetch resolved and the
// context propagated — the footer assertions below run against settled state.
function settled(body: BoutiqueResponse = BOUTIQUE) {
  return screen.findByRole("heading", { name: body.name });
}

function footer(): HTMLElement {
  return screen.getByRole("contentinfo");
}

// The element wrapping BOTH <main> and <footer>. The footer is a sibling of
// <main>, so this is the only element that can reserve space on its behalf.
function pageShell(): HTMLElement {
  const shell = screen.getByRole("main").parentElement;
  if (shell === null) throw new Error("<main> has no page shell around it");
  return shell;
}

function a11yMenuRoot(): HTMLElement {
  const trigger = screen.getByRole("button", { name: i18n.t("a11y.menuTrigger") });
  const root = trigger.parentElement;
  if (root === null) throw new Error("the A11yMenu trigger has no positioned root");
  return root;
}

beforeEach(() => {
  resetBoutiqueCache();
});

afterEach(() => {
  vi.unstubAllGlobals();
  resetBoutiqueCache();
  window.history.replaceState(null, "", "/");
});

describe("skip link and focus target", () => {
  it("points the skip link at the <main> the router focuses", async () => {
    renderAt("/");
    await settled();

    const skip = screen.getByRole("link", { name: i18n.t("a11y.skipLink") });
    const target = skip.getAttribute("href")?.slice(1) ?? "";

    expect(skip).toHaveAttribute("href", "#content");
    // The fragment must resolve to the real <main>, not just look right: a
    // renamed id leaves the link jumping nowhere and the router focusing null.
    expect(document.getElementById(target)).toBe(screen.getByRole("main"));
  });

  it("gives <main> a programmatic focus target", async () => {
    renderAt("/");
    await settled();
    const main = screen.getByRole("main");

    expect(main).toHaveAttribute("id", "content");
    expect(main).toHaveAttribute("tabindex", "-1");
    // The attribute alone is not the behaviour — a <main> without it silently
    // refuses focus() and the post-navigation focus move becomes a no-op.
    main.focus();
    expect(document.activeElement).toBe(main);
  });
});

describe("footer", () => {
  it.each(["/", "/dress/d1", "/about", "/accessibility"])(
    "carries the about and accessibility-statement links on %s",
    async (pathname) => {
      renderAt(pathname);
      await settled();

      const links = within(footer());
      expect(links.getByRole("link", { name: i18n.t("footer.about") })).toHaveAttribute(
        "href",
        "/about",
      );
      // IS 5568 §35: the statement must be reachable from every page, and the
      // footer is the only place the storefront links it from.
      expect(links.getByRole("link", { name: i18n.t("a11y.statementLink") })).toHaveAttribute(
        "href",
        "/accessibility",
      );
    },
  );

  it("shows the boutique's phone and Instagram once the block lands", async () => {
    renderAt("/");
    await settled();

    const links = within(footer());
    expect(links.getByRole("link", { name: "052-1234567" })).toHaveAttribute(
      "href",
      "tel:052-1234567",
    );
    expect(links.getByRole("link", { name: "@alma.bridal" })).toHaveAttribute(
      "href",
      "https://instagram.com/alma.bridal",
    );
  });

  it("omits both cleanly for a tenant that has neither", async () => {
    renderAt("/", BARE_BOUTIQUE);
    await settled(BARE_BOUTIQUE);

    const contacts = within(footer())
      .getAllByRole("link")
      .filter((link) => {
        const href = link.getAttribute("href") ?? "";
        return href.startsWith("tel:") || href.includes("instagram.com");
      });
    expect(contacts).toHaveLength(0);
    // Each contact link owns the "·" before it, so a stray separator is how a
    // missing field leaks visually even when no link renders.
    expect(within(footer()).queryAllByText("·")).toHaveLength(1);
  });
});

describe("the shared boutique fetch", () => {
  it("issues one getBoutique() for the footer and the routes together", async () => {
    const fetchMock = renderAt("/");
    await settled();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe("/storefront/boutique");
    // Same call feeds both consumers: the footer's phone and the child's view
    // of the context come out of that single response.
    expect(within(footer()).getByRole("link", { name: "052-1234567" })).toBeInTheDocument();
  });
});

describe("fixed CTA bar footprint", () => {
  it.each([
    ["/", true],
    ["/dress/d1", true],
    ["/about", false],
    ["/accessibility", false],
    // The booking flow carries no "book a fitting" CTA — putting one inside the
    // flow it leads to is the inverse mistake (spec Risk 6).
    ["/book/slot", false],
    ["/book/verify/d1", false],
  ])("reserves the bar's footprint on %s: %s", async (pathname, reserved) => {
    renderAt(pathname);
    await settled();

    // The reservation must sit OUTSIDE <main>: the statutory הצהרת נגישות link
    // lives in the footer, and padding on a page div inside <main> cannot clear
    // a bar that overlaps its sibling.
    expect(pageShell().className.includes(CTA_RESERVATION)).toBe(reserved);
    expect(screen.getByRole("main").className).not.toContain(CTA_RESERVATION);
    // And it releases at 768, where the bar goes inline — a permanent gutter on
    // desktop is its own defect.
    if (reserved) expect(pageShell().className).toContain("max-md:");
  });
});

describe("A11yMenu footprint over the footer (PRE-2)", () => {
  it.each(["/", "/dress/d1", "/about", "/accessibility", "/book/slot"])(
    "keeps הצהרת נגישות out from under the fixed trigger on %s",
    async (pathname) => {
      renderAt(pathname);
      await settled();

      // The trigger is `fixed` at the viewport's block-end inline-end corner on
      // EVERY route and at every width, and the footer is the last thing in the
      // document — so scrolled to the end it paints over the statutory link
      // unless the footer reserves the trigger's own footprint. Page padding
      // cannot do this job: <footer> is a SIBLING of <main>, outside every
      // padded page div. jsdom has no layout, so the reservation is asserted
      // here and measured for real in e2e's PRE-2 geometry test.
      expect(footer().className).toContain(A11Y_FOOTPRINT);
      // A literal is how /about shipped pb-8 against a 60px footprint; the
      // reservation has to be derived from the trigger's own box.
      expect(footer().className).not.toMatch(/\bpb-\d/);
      expect(
        within(footer()).getByRole("link", { name: i18n.t("a11y.statementLink") }),
      ).toBeInTheDocument();
    },
  );
});

describe("A11yMenu lift", () => {
  it.each([
    ["/", true],
    ["/dress/d1", true],
    ["/about", false],
    ["/accessibility", false],
    ["/book/slot", false],
    ["/book/verify/d1", false],
  ])("lifts the menu above a booking bar on %s: %s", async (pathname, lifted) => {
    renderAt(pathname);
    await settled();

    // /about ships a static inline button and no bar, so lifting the menu 92px
    // there floats it over content that reserved only for the unlifted button
    // (PRE-2). /accessibility ships no CTA at all.
    expect(a11yMenuRoot().className.includes(A11Y_LIFT)).toBe(lifted);
  });
});
