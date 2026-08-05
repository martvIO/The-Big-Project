import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ErrorBoundary } from "../components/ErrorBoundary";

// React 19 UNMOUNTS THE WHOLE TREE on an uncaught render error. Neither SPA had
// a boundary anywhere — `grep -rn 'ErrorBoundary|componentDidCatch|
// getDerivedStateFromError' apps packages` returned zero source hits — so any
// render throw left a blank white page with no recovery affordance at all. On
// the manage console that page is ALSO the SOS emergency channel.

function Boom(): never {
  throw new Error("render blew up");
}

const LABELS = { message: "לא הצלחנו לטעון את הנתונים כרגע.", reload: "רענון הדף" };

// React logs the caught error through console.error even when a boundary
// handles it. Silenced per test rather than globally: a stray console.error
// from something else must still be visible in the suite.
let consoleError: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  consoleError.mockRestore();
});

describe("ErrorBoundary", () => {
  it("renders its children untouched when nothing throws", () => {
    render(
      <ErrorBoundary {...LABELS}>
        <p>תוכן</p>
      </ErrorBoundary>,
    );

    expect(screen.getByText("תוכן")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("renders the fallback instead of a blank tree when a child throws", () => {
    render(
      <ErrorBoundary {...LABELS}>
        <Boom />
      </ErrorBoundary>,
    );

    // The whole point: something is on the page. A blank <body> is what shipped.
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(LABELS.message);
    expect(screen.getByRole("button", { name: LABELS.reload })).toBeInTheDocument();
  });

  it("offers a reload control that actually reloads", () => {
    const reload = vi.fn();
    // `location.reload` is not implemented in jsdom and is non-writable, so the
    // whole accessor is replaced. Restored by `vi.restoreAllMocks` via the
    // config's `restoreMocks`, and asserted here rather than left to a comment:
    // a recovery affordance that does not recover is worse than none, because
    // she presses it and concludes the product is dead.
    const original = window.location;
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { ...original, reload },
    });
    try {
      render(
        <ErrorBoundary {...LABELS}>
          <Boom />
        </ErrorBoundary>,
      );

      fireEvent.click(screen.getByRole("button", { name: LABELS.reload }));

      expect(reload).toHaveBeenCalledOnce();
    } finally {
      Object.defineProperty(window, "location", { configurable: true, value: original });
    }
  });

  it("announces the failure — the fallback replaces a tree that had focus in it", () => {
    // She was somewhere in the app when it died, so nothing moves focus for her
    // and no control she can see explains the change. `role="alert"` is the only
    // thing that says anything happened at all.
    render(
      <ErrorBoundary {...LABELS}>
        <Boom />
      </ErrorBoundary>,
    );

    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
});
