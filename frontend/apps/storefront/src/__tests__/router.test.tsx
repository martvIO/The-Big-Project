import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { ReactNode } from "react";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import i18n from "../i18n";
import { BOOK_STEPS, Link, MAIN_ID, Router, matchRoute, navigate, usePathname } from "../router";

// The routes are stubbed on purpose: this file is about the router's own
// contract (matching, interception, title, focus, scroll). Rendering the real
// pages would drag their fetches in and test them a second time.
vi.mock("../routes/CatalogPage", () => ({ CatalogPage: () => "קטלוג" }));
vi.mock("../routes/DressPage", () => ({
  DressPage: ({ dressId }: { dressId: string }) => `שמלה ${dressId}`,
}));
vi.mock("../routes/AboutPage", () => ({ AboutPage: () => "אודות" }));
vi.mock("../routes/AccessibilityPage", () => ({ AccessibilityPage: () => "נגישות" }));
vi.mock("../routes/BookPage", () => ({
  BookPage: ({ step }: { step: string }) => `שלב ${step}`,
}));
vi.mock("../routes/ManageBookingPage", () => ({
  ManageBookingPage: ({ token }: { token: string }) => `ניהול ${token}`,
}));
vi.mock("../routes/CheckinPage", () => ({ CheckinPage: () => "טופס רישום" }));
vi.mock("../routes/QueuePositionPage", () => ({
  QueuePositionPage: ({ ticketId }: { ticketId: string }) => `מקום בתור ${ticketId}`,
}));
vi.mock("../routes/QueueBoardPage", () => ({ QueueBoardPage: () => "לוח" }));
vi.mock("../routes/PrivacyPage", () => ({ PrivacyPage: () => "פרטיות" }));
vi.mock("../routes/PortalPage", () => ({ PortalPage: () => "האזור האישי" }));
vi.mock("../routes/OfferPage", () => ({
  OfferPage: ({ token }: { token: string }) => `הצעה ${token}`,
}));

function go(pathname: string) {
  window.history.replaceState(null, "", pathname);
}

// navigate() drives an external store; act() flushes the resulting render and
// its effects before the assertion reads document.title / activeElement.
function navigateAndFlush(to: string) {
  act(() => {
    navigate(to);
  });
}

// StorefrontLayout owns the real <main id="content" tabindex="-1"> (asserted in
// StorefrontLayout.test.tsx). Reproduced here so the focus target exists
// without pulling the layout's boutique fetch into a router test.
function renderRoute(pathname: string, extra?: ReactNode) {
  go(pathname);
  return render(
    <main id={MAIN_ID} tabIndex={-1}>
      <Router />
      {extra}
    </main>,
  );
}

function mainElement(): HTMLElement {
  const main = document.getElementById(MAIN_ID);
  if (main === null) throw new Error("no #content in the tree");
  return main;
}

// jsdom implements neither window.scrollTo nor a mutable scrollY, so scrollY is
// 0 forever and "the viewport returned to the top" could never fail. Supply the
// missing piece: prime a scrolled viewport and let the stub do what a browser
// does, so only the router's own scrollTo(0, 0) can bring it back.
function primeScroll(offset: number) {
  const setScrollY = (value: number) => {
    Object.defineProperty(window, "scrollY", { configurable: true, writable: true, value });
  };
  setScrollY(offset);
  vi.stubGlobal("scrollTo", (_x: number, y: number) => {
    setScrollY(y);
  });
}

beforeEach(() => {
  go("/");
  document.title = "";
});

afterEach(() => {
  vi.unstubAllGlobals();
  go("/");
});

describe("matchRoute", () => {
  it("maps every designed path to its route", () => {
    expect(matchRoute("/")).toEqual({ name: "catalog" });
    expect(matchRoute("/about")).toEqual({ name: "about" });
    expect(matchRoute("/accessibility")).toEqual({ name: "accessibility" });
  });

  it("extracts the dress id from /dress/:id", () => {
    expect(matchRoute("/dress/11111111-2222-3333-4444-555555555555")).toEqual({
      name: "dress",
      dressId: "11111111-2222-3333-4444-555555555555",
    });
  });

  it("percent-decodes the dress id", () => {
    expect(matchRoute("/dress/d%201")).toEqual({ name: "dress", dressId: "d 1" });
  });

  it("does not throw on a malformed escape — a hand-typed URL must not blank the page", () => {
    expect(matchRoute("/dress/%")).toEqual({ name: "dress", dressId: "%" });
  });

  it("ignores a trailing slash", () => {
    expect(matchRoute("/about/")).toEqual({ name: "about" });
    expect(matchRoute("/dress/abc/")).toEqual({ name: "dress", dressId: "abc" });
  });

  it("falls back to the catalog for anything else — the design ships no 404 page", () => {
    expect(matchRoute("/nope")).toEqual({ name: "catalog" });
    expect(matchRoute("/dress")).toEqual({ name: "catalog" });
    expect(matchRoute("/dress/a/b")).toEqual({ name: "catalog" });
  });

  // F16's tokenized manage link. The path is SHORT on purpose (spec D7): the URL
  // rides inside a UCS-2 Hebrew SMS where every character is segment budget.
  it("extracts the manage token from /b/:token", () => {
    expect(matchRoute("/b/mt-abc123")).toEqual({ name: "manage", token: "mt-abc123" });
  });

  it("accepts every character generate_session_token can emit", () => {
    // token_urlsafe uses [A-Za-z0-9_-]; a route that choked on "-" or "_" would
    // 404 a working link roughly half the time.
    expect(matchRoute("/b/aB0_-xyz")).toEqual({ name: "manage", token: "aB0_-xyz" });
  });

  it("ignores a trailing slash on the manage path too", () => {
    expect(matchRoute("/b/tok/")).toEqual({ name: "manage", token: "tok" });
  });

  it("does not throw on a malformed escape in a token", () => {
    expect(matchRoute("/b/%")).toEqual({ name: "manage", token: "%" });
  });

  it("routes an UNKNOWN token to the page, not to the catalog", () => {
    // Load-bearing (D7/D8): the page owns the invalid-link state, and the
    // catalog fallthrough must never swallow a bad token — a bride whose link
    // was rotated would otherwise land on a dress grid with no explanation.
    expect(matchRoute("/b/anything-at-all")).toEqual({
      name: "manage",
      token: "anything-at-all",
    });
  });

  it("does not read a deeper or bare /b path as a manage route", () => {
    expect(matchRoute("/b")).toEqual({ name: "catalog" });
    expect(matchRoute("/b/tok/extra")).toEqual({ name: "catalog" });
  });

  // F23's offer link. One letter from MANAGE_PATH and for the identical reason:
  // the URL rides inside a UCS-2 Hebrew SMS where every character is budget.
  it("extracts the offer token from /w/:token", () => {
    expect(matchRoute("/w/ot-abc123")).toEqual({ name: "offer", token: "ot-abc123" });
  });

  it("accepts every character mint_manage_token can emit in an offer token", () => {
    expect(matchRoute("/w/aB0_-xyz")).toEqual({ name: "offer", token: "aB0_-xyz" });
  });

  it("ignores a trailing slash on the offer path", () => {
    expect(matchRoute("/w/tok/")).toEqual({ name: "offer", token: "tok" });
  });

  it("routes an UNKNOWN offer token to the page, not to the catalog", () => {
    // The manage rule verbatim, and load-bearing for the SAME reason: an expired
    // or declined offer's token must reach OfferPage so the page renders its own
    // expired/invalid state. Swallowed into the catalogue, a bride who tapped a
    // day-old text lands on a dress grid with no explanation of what happened to
    // the slot she was texted about.
    expect(matchRoute("/w/anything-at-all")).toEqual({
      name: "offer",
      token: "anything-at-all",
    });
  });

  it("does not read a deeper or bare /w path as an offer route", () => {
    expect(matchRoute("/w")).toEqual({ name: "catalog" });
    expect(matchRoute("/w/tok/extra")).toEqual({ name: "catalog" });
  });

  // F33's walk-in queue. /checkin is printed on a physical sign in the shop
  // window, which makes it the most deep-linked URL the product has.
  it("maps /checkin to its own route", () => {
    expect(matchRoute("/checkin")).toEqual({ name: "checkin" });
    expect(matchRoute("/checkin/")).toEqual({ name: "checkin" });
  });

  it("extracts the ticket id from /q/:ticketId", () => {
    expect(matchRoute("/q/11111111-2222-3333-4444-555555555555")).toEqual({
      name: "queuePosition",
      ticketId: "11111111-2222-3333-4444-555555555555",
    });
    expect(matchRoute("/q/tick3t/")).toEqual({ name: "queuePosition", ticketId: "tick3t" });
  });

  it("routes an UNKNOWN ticket to the position page, not to the catalog", () => {
    // Load-bearing, the same reason /b/{token}'s ordering is: an unknown,
    // expired or swept ticket must reach the page's own not-found state. Swallowed
    // into the collection, a woman standing in the doorway gets a dress grid.
    expect(matchRoute("/q/anything-at-all")).toEqual({
      name: "queuePosition",
      ticketId: "anything-at-all",
    });
  });

  it("does not throw on a malformed escape in a ticket id", () => {
    expect(matchRoute("/q/%")).toEqual({ name: "queuePosition", ticketId: "%" });
  });

  it("does not read a deeper or bare /q path as a position route", () => {
    expect(matchRoute("/q")).toEqual({ name: "catalog" });
    expect(matchRoute("/q/tick3t/extra")).toEqual({ name: "catalog" });
  });

  // F59's public wall board. An EXACT match, no path parameter, no regex — the
  // board takes no input of any kind.
  it("maps /queue to the board route", () => {
    expect(matchRoute("/queue")).toEqual({ name: "queueBoard" });
    expect(matchRoute("/queue/")).toEqual({ name: "queueBoard" });
  });

  // F20's statutory privacy notice. An EXACT match beside the other four, and
  // therefore ahead of every regex and the catalogue fallthrough automatically.
  it("maps /privacy to the privacy route", () => {
    expect(matchRoute("/privacy")).toEqual({ name: "privacy" });
    expect(matchRoute("/privacy/")).toEqual({ name: "privacy" });
  });

  it("shadows neither /b/{token} nor the catalogue fallthrough", () => {
    // ⚠ The ordering claim in the plan, made checkable. A `/privacy` literal is
    // harmless; a `/privacy` PREFIX would not be — it would swallow a manage
    // token or a dress id that happened to start with the same characters, and
    // a bride whose link vanished into a legal document has no way to tell what
    // went wrong. The three below are the neighbours it could plausibly eat.
    expect(matchRoute("/b/privacy-token")).toEqual({ name: "manage", token: "privacy-token" });
    expect(matchRoute("/privacy/anything")).toEqual({ name: "catalog" });
    expect(matchRoute("/dress/privacy")).toEqual({ name: "dress", dressId: "privacy" });
  });

  it("keeps /q/… disjoint from /queue, in both directions", () => {
    // The shipped comment on QUEUE_PATH claimed this before /queue existed; it
    // is now simply true. The regex cannot match /queue, and an exact /queue
    // match cannot match a ticket path — including the one that looks closest.
    expect(matchRoute("/q/ueue")).toEqual({ name: "queuePosition", ticketId: "ueue" });
    expect(matchRoute("/queue/anything")).toEqual({ name: "catalog" });
  });

  it.each(BOOK_STEPS)("maps /book/%s to its step", (step) => {
    expect(matchRoute(`/book/${step}`)).toEqual({ name: "book", step });
  });

  it("opens the flow on the slot step for a bare /book", () => {
    expect(matchRoute("/book")).toEqual({ name: "book", step: "slot" });
    expect(matchRoute("/book/")).toEqual({ name: "book", step: "slot" });
  });

  it("carries the dress id on /book/{step}/{dressId}", () => {
    expect(matchRoute("/book/details/d1")).toEqual({
      name: "book",
      step: "details",
      dressId: "d1",
    });
    expect(matchRoute("/book/confirm/d%201")).toEqual({
      name: "book",
      step: "confirm",
      dressId: "d 1",
    });
  });

  it("falls back to the catalog for an unknown step — the step set is closed", () => {
    // The closed set is what stops a dress id being read as a step: there is no
    // /book/{dressId} shape to be ambiguous with.
    expect(matchRoute("/book/d1")).toEqual({ name: "catalog" });
    expect(matchRoute("/book/slot/d1/more")).toEqual({ name: "catalog" });
  });
});

describe("the booking flow's routes", () => {
  it("renders the slot step for a bare /book", () => {
    renderRoute("/book");
    expect(screen.getByText("שלב slot")).toBeInTheDocument();
  });

  it("renders the step named in the path", () => {
    renderRoute("/book/terms/d1");
    expect(screen.getByText("שלב terms")).toBeInTheDocument();
  });
});

// The render switch ends in `default: return <CatalogPage />`, so a route that
// matches, resolves a title and has NO `case` compiles clean, typechecks clean
// and serves the dress grid under its own tab title. `/checkin` shipped exactly
// that way — and every title assertion in this file passed against it, because
// the title comes from DOC_TITLE_KEYS[match.name] and never from the switch.
//
// So each of these asserts the page rendered AND that the catalogue did not.
// The negative half is the one that reddens against the fallthrough; asserting
// the title, or asserting the stub alone against a route that renders both,
// would not.
describe("the walk-in queue's routes", () => {
  it("renders the check-in form at /checkin, never the catalogue", () => {
    renderRoute("/checkin");
    expect(screen.getByText("טופס רישום")).toBeInTheDocument();
    expect(screen.queryByText("קטלוג")).toBeNull();
  });

  it("renders the position page at /q/:ticketId with its ticket id, never the catalogue", () => {
    renderRoute("/q/tick3t");
    expect(screen.getByText("מקום בתור tick3t")).toBeInTheDocument();
    expect(screen.queryByText("קטלוג")).toBeNull();
  });

  it("renders the wall board at /queue, never the catalogue", () => {
    // The negative half is the whole test. `queueBoard` resolves a title from
    // DOC_TITLE_KEYS whether or not the switch has a `case` for it, so a title
    // assertion here would pass against a route serving the dress grid — which
    // is exactly how `checkin` shipped for one commit.
    renderRoute("/queue");
    expect(screen.getByText("לוח")).toBeInTheDocument();
    expect(screen.queryByText("קטלוג")).toBeNull();
  });

  it("titles the board from its own key, carrying no name and no number", () => {
    renderRoute("/queue");
    expect(document.title).toBe(i18n.t("document.queueBoard"));
    expect(document.title).not.toBe("document.queueBoard");
  });

  it("renders the privacy notice at /privacy, never the catalogue", () => {
    // The negative half is the whole test, for the reason the board's twin
    // states: `DOC_TITLE_KEYS` is compiler-forced and the render switch is not,
    // so a missing `case` compiles clean, titles the page correctly and serves
    // the dress grid. `checkin` shipped exactly that way for one commit.
    renderRoute("/privacy");
    expect(screen.getByText("פרטיות")).toBeInTheDocument();
    expect(screen.queryByText("קטלוג")).toBeNull();
  });

  it("titles the privacy page from its own key", () => {
    renderRoute("/privacy");
    expect(document.title).toBe(i18n.t("document.privacy"));
    expect(document.title).not.toBe("document.privacy");
  });
});

// F24. The SAME trap, stated a fourth time because it has caught this codebase
// once already: `DOC_TITLE_KEYS` is compiler-forced and the render switch is
// not, so `/portal` with a matcher, a title and NO `case` compiles clean,
// typechecks clean and serves the dress grid under «האזור האישי». The negative
// half of each pair is what reddens against that.
describe("the client portal's route", () => {
  it("renders the portal at /portal, never the catalogue", () => {
    renderRoute("/portal");
    expect(screen.getByText("האזור האישי")).toBeInTheDocument();
    expect(screen.queryByText("קטלוג")).toBeNull();
  });

  it("titles the portal from its own key", () => {
    renderRoute("/portal");
    expect(document.title).toBe(i18n.t("document.portal"));
    expect(document.title).not.toBe("document.portal");
  });

  it("is an EXACT literal, so nothing below it is swallowed", () => {
    // `/portal-anything` is not this page, and a prefix match would swallow a
    // link whose id merely started the same way — the /privacy ruling, reused.
    expect(matchRoute("/portal")).toEqual({ name: "portal" });
    expect(matchRoute("/portal/")).toEqual({ name: "portal" });
    expect(matchRoute("/portalx")).toEqual({ name: "catalog" });
    expect(matchRoute("/portal/bookings")).toEqual({ name: "catalog" });
  });
});

describe("usePathname", () => {
  function Probe() {
    return <span data-testid="pathname">{usePathname()}</span>;
  }

  it("re-renders on popstate (browser back)", () => {
    go("/about");
    render(<Probe />);
    expect(screen.getByTestId("pathname")).toHaveTextContent("/about");

    go("/accessibility");
    fireEvent.popState(window);
    expect(screen.getByTestId("pathname")).toHaveTextContent("/accessibility");
  });

  it("re-renders on a programmatic navigate", () => {
    render(<Probe />);
    navigateAndFlush("/about");
    expect(screen.getByTestId("pathname")).toHaveTextContent("/about");
  });
});

describe("Link", () => {
  it("renders a real href so the browser can open it directly", () => {
    render(<Link to="/dress/abc">שמלה</Link>);
    expect(screen.getByRole("link", { name: "שמלה" })).toHaveAttribute("href", "/dress/abc");
  });

  it("intercepts a plain left click and pushes history", () => {
    render(<Link to="/about">אודות</Link>);
    const clicked = fireEvent.click(screen.getByRole("link", { name: "אודות" }), { button: 0 });
    expect(clicked).toBe(false); // preventDefault() ran
    expect(window.location.pathname).toBe("/about");
    expect(window.history.state).toBe(null);
  });

  it("lets a meta-click through so the link opens in a new tab", () => {
    render(<Link to="/about">אודות</Link>);
    const clicked = fireEvent.click(screen.getByRole("link", { name: "אודות" }), {
      button: 0,
      metaKey: true,
    });
    expect(clicked).toBe(true); // not prevented — the browser handles it
    expect(window.location.pathname).toBe("/");
  });

  it("lets ctrl/shift/alt clicks and non-primary buttons through too", () => {
    render(<Link to="/about">אודות</Link>);
    const link = screen.getByRole("link", { name: "אודות" });
    for (const modifier of [{ ctrlKey: true }, { shiftKey: true }, { altKey: true }, { button: 1 }]) {
      expect(fireEvent.click(link, { button: 0, ...modifier })).toBe(true);
      expect(window.location.pathname).toBe("/");
    }
  });
});

// DressCard renders a raw <a href> and takes no onNavigate prop, so the grid can
// only go client-side through the document-level listener. Every anchor below is
// one the router never rendered.
describe("root click delegation", () => {
  it("upgrades a plain left click on any same-origin anchor to a client navigation", () => {
    renderRoute("/", <a href="/dress/d1">שמלת ורד</a>);

    const clicked = fireEvent.click(screen.getByRole("link", { name: "שמלת ורד" }), { button: 0 });

    expect(clicked).toBe(false); // preventDefault() ran — no document reload
    expect(window.location.pathname).toBe("/dress/d1");
    expect(screen.getByText("שמלה d1")).toBeInTheDocument();
  });

  it("leaves a modified click to the browser", () => {
    renderRoute("/", <a href="/about">אודות</a>);
    const link = screen.getByRole("link", { name: "אודות" });

    for (const modifier of [{ metaKey: true }, { ctrlKey: true }, { shiftKey: true }]) {
      expect(fireEvent.click(link, { button: 0, ...modifier })).toBe(true);
      expect(window.location.pathname).toBe("/");
    }
  });

  it("does NOT intercept a hash-only link — this is the skip link", () => {
    // Load-bearing: preventDefault() here means the browser never performs the
    // fragment navigation, focus never reaches #content, and the WCAG skip-link
    // behaviour the e2e suite asserts breaks silently with a green unit suite.
    renderRoute("/", <a href={`#${MAIN_ID}`}>דלג לתוכן</a>);

    const clicked = fireEvent.click(screen.getByRole("link", { name: "דלג לתוכן" }), { button: 0 });

    expect(clicked).toBe(true);
    expect(window.location.pathname).toBe("/");
  });

  it("does NOT intercept a tel: link — the OS owns the dialer", () => {
    renderRoute("/", <a href="tel:052-1234567">חיוג</a>);

    expect(fireEvent.click(screen.getByRole("link", { name: "חיוג" }), { button: 0 })).toBe(true);
    expect(window.location.pathname).toBe("/");
  });

  it("does NOT intercept target=_blank or rel=external", () => {
    renderRoute(
      "/",
      <>
        <a href="/about" target="_blank" rel="noopener noreferrer">
          לשונית חדשה
        </a>
        <a href="/about" rel="external">
          חיצוני
        </a>
      </>,
    );

    for (const name of ["לשונית חדשה", "חיצוני"]) {
      expect(fireEvent.click(screen.getByRole("link", { name }), { button: 0 })).toBe(true);
      expect(window.location.pathname).toBe("/");
    }
  });
});

describe("Router document title, focus and scroll", () => {
  it("titles each route from the i18n catalog", () => {
    renderRoute("/");
    expect(document.title).toBe(i18n.t("document.catalog"));
    expect(document.title).not.toBe("document.catalog");
  });

  it("retitles on navigation", () => {
    renderRoute("/");
    navigateAndFlush("/about");
    expect(document.title).toBe(i18n.t("document.about"));
  });

  it("replaces a dress name on the next navigation rather than letting it stick", () => {
    renderRoute("/dress/d1");
    // The dress page upgrades the title to the dress's own name once its fetch
    // lands (WCAG 2.4.2). The router owns every other route, so that name must
    // not survive the hop — a stale dress in the tab strip is the same defect
    // as a shared one.
    document.title = "ורד";

    navigateAndFlush("/about");

    expect(document.title).toBe(i18n.t("document.about"));
  });

  // ONE title for the whole booking flow: the steps are not separate pages, and
  // a per-step title written from inside BookPage would lose the race anyway —
  // React flushes a child's passive effects before its parent's, so this effect
  // would run last and overwrite it.
  it.each(["/book", ...BOOK_STEPS.map((step) => `/book/${step}`), "/book/details/d1"])(
    "titles %s with the flow's single title",
    (pathname) => {
      renderRoute(pathname);
      expect(document.title).toBe(i18n.t("document.book"));
      expect(document.title).not.toBe("document.book");
    },
  );

  it("titles the manage route with its own single title", () => {
    // One title for all six manage states: she arrived from a text message, and
    // an outcome ("cancelled") does not belong in the tab strip.
    renderRoute("/b/mt-abc123");
    expect(document.title).toBe(i18n.t("document.manageTitle"));
    expect(document.title).not.toBe("document.manageTitle");
  });

  it("never puts the manage token in the document title", () => {
    renderRoute("/b/mt-secret-token");
    expect(document.title).not.toContain("mt-secret-token");
  });

  it("titles the offer route with its own single title", () => {
    // One title for all ten states of /w/{token}, the manage rule verbatim.
    renderRoute("/w/ot-abc123");
    expect(document.title).toBe(i18n.t("document.offer"));
    expect(document.title).not.toBe("document.offer");
  });

  it("never puts the offer token in the document title", () => {
    // The token is a live CLAIM credential, not just a lookup key — a tab strip
    // is read over a shoulder and a title lands in browser history.
    renderRoute("/w/ot-secret-token");
    expect(document.title).not.toContain("ot-secret-token");
  });

  it("titles the check-in route from the catalogue", () => {
    renderRoute("/checkin");
    expect(document.title).toBe(i18n.t("document.checkin"));
    expect(document.title).not.toBe("document.checkin");
  });

  it("titles the position route from the catalogue", () => {
    renderRoute("/q/tick3t");
    expect(document.title).toBe(i18n.t("document.queuePosition"));
    expect(document.title).not.toBe("document.queuePosition");
  });

  it("never puts the ticket id in the document title", () => {
    // F33 ESTABLISHES this rule — no shipped comment states it, and this
    // assertion is the only thing holding it. The id is the capability, and a
    // tab strip is read over a shoulder in a shop.
    renderRoute("/q/tick3t-secret");
    expect(document.title).not.toContain("tick3t-secret");
  });

  it("does not steal focus on first paint — the skip link is the first stop", () => {
    renderRoute("/");
    // Deliberately NOT wrapped in expectFocus()/waitFor(): this is a negative
    // assertion, and polling one passes the instant it is first evaluated —
    // which would stop it noticing a focus grab that lands a tick later. The
    // synchronous read is the strict version. render() has already flushed
    // effects, so there is no race to lose here anyway.
    expect(document.activeElement).not.toBe(mainElement());
  });

  it("lands focus in #content, returns to the top and retitles on a client navigation", () => {
    primeScroll(1200);
    renderRoute("/");
    const titleBefore = document.title;

    navigateAndFlush("/about");

    // WCAG 2.4.2 + focus management: new page, new title, focus at the top of
    // the new content. The scroll reset is what stops a bride who tapped a card
    // in grid row 5 from landing on the dress page still scrolled to row 5.
    expect(document.activeElement).toBe(mainElement());
    expect(window.scrollY).toBe(0);
    expect(document.title).not.toBe(titleBefore);
    expect(document.title).toBe(i18n.t("document.about"));
  });
});


// --- the root error boundary's WIRING ---------------------------------------

describe("the root error boundary is mounted around <App/>", () => {
  it("wraps App in main.tsx, with nothing between them", () => {
    // ⚠ THE SOURCE IS READ, and that is the honest instrument rather than a
    // clever one. The boundary's BEHAVIOUR is tested in
    // `packages/ui/src/__tests__/ErrorBoundary.test.tsx`; what no rendering test
    // in this app can reach is `main.tsx`, which calls `createRoot` at module
    // scope against a real `#root` — importing it mounts the whole app into the
    // test DOM. So the WIRING is asserted the way this repo already asserts
    // `vite.config.ts` and `ci.yml` in `test_spa_serving.py`: by reading the file.
    //
    // Without this, deleting the wrapper is a change that every test, every lint
    // and every build passes — which is exactly how the product came to have no
    // boundary at all.
    // `import.meta.url` is a vite:// URL under vitest, so it is resolved from
    // the project root instead — which is `apps/<app>` for every runner here.
    const source = readFileSync(resolve(process.cwd(), "src/main.tsx"), "utf8");

    expect(source).toMatch(/<ErrorBoundary[^>]*>\s*<App\s*\/>\s*<\/ErrorBoundary>/);
    expect(source).toContain('from "@boutique/ui"');
  });
});
