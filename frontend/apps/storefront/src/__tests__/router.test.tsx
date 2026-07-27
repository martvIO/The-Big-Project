import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import i18n from "../i18n";
import { Link, MAIN_ID, Router, matchRoute, navigate, usePathname } from "../router";

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

// The <main tabindex="-1"> App.tsx wraps the router outlet in. The focus
// assertions below depend on it existing, exactly as it does in the real tree.
function renderRoute(pathname: string) {
  go(pathname);
  return render(
    <main id={MAIN_ID} tabIndex={-1}>
      <Router />
    </main>,
  );
}

beforeEach(() => {
  go("/");
  document.title = "";
});

afterEach(() => {
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

describe("Router document title and focus", () => {
  it("titles each route from the i18n catalog", () => {
    renderRoute("/");
    expect(document.title).toBe(i18n.t("doc.catalog"));
    expect(document.title).not.toBe("doc.catalog");
  });

  it("retitles on navigation", () => {
    renderRoute("/");
    navigateAndFlush("/about");
    expect(document.title).toBe(i18n.t("doc.about"));
  });

  it("replaces a dress name on the next navigation rather than letting it stick", () => {
    renderRoute("/dress/d1");
    // DressDetail upgrades the title to the dress's own name once its fetch
    // lands (WCAG 2.4.2). The router owns every other route, so that name must
    // not survive the hop — a stale dress in the tab strip is the same defect
    // as a shared one.
    document.title = "ורד";

    navigateAndFlush("/about");

    expect(document.title).toBe(i18n.t("doc.about"));
  });

  it("does not steal focus on first paint — the skip link is the first stop", () => {
    renderRoute("/");
    expect(document.activeElement).not.toBe(document.getElementById(MAIN_ID));
  });

  it("moves focus into <main> after a client navigation (WCAG 2.4.2)", () => {
    renderRoute("/");
    navigateAndFlush("/about");
    expect(document.activeElement).toBe(document.getElementById(MAIN_ID));
  });
});
