import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { DescriptionClamp } from "../components/DescriptionClamp";
import "../i18n";

// jsdom has no layout, so the two numbers the clamp measures are stubbed and
// driven by hand — that is the only way to express "the same text now overflows
// six lines because the root font grew".
let scrollHeight = 0;
let clientHeight = 0;

beforeAll(() => {
  for (const [name, read] of [
    ["scrollHeight", () => scrollHeight],
    ["clientHeight", () => clientHeight],
  ] as const) {
    Object.defineProperty(HTMLParagraphElement.prototype, name, {
      configurable: true,
      get: read,
    });
  }
});

afterEach(() => {
  document.documentElement.removeAttribute("data-a11y-text-size");
});

const TEXT = "שמלת משי בגזרת A עם מחשוף לב עדין וכפתורי צדף לאורך הגב.";

describe("DescriptionClamp", () => {
  it("offers no toggle while the description fits inside the clamp", () => {
    scrollHeight = 160;
    clientHeight = 160;
    render(<DescriptionClamp text={TEXT} />);
    expect(screen.queryByRole("button", { name: "עוד" })).toBeNull();
  });

  it("grows a toggle when the A11yMenu text-size boost pushes the text past six lines", async () => {
    scrollHeight = 160;
    clientHeight = 160;
    render(<DescriptionClamp text={TEXT} />);
    expect(screen.queryByRole("button", { name: "עוד" })).toBeNull();

    // What the boost does: :root[data-a11y-text-size] sets font-size: 1.2rem.
    // No resize event fires — the visitor who needs big text would otherwise
    // lose the tail of the description with no way to reveal it.
    scrollHeight = 200;
    await act(async () => {
      document.documentElement.setAttribute("data-a11y-text-size", "");
    });

    expect(screen.getByRole("button", { name: "עוד" })).toHaveAttribute("aria-expanded", "false");
  });

  it("drops the toggle again when the boost is turned back off", async () => {
    scrollHeight = 200;
    clientHeight = 160;
    render(<DescriptionClamp text={TEXT} />);
    expect(screen.getByRole("button", { name: "עוד" })).toBeInTheDocument();

    scrollHeight = 160;
    await act(async () => {
      document.documentElement.setAttribute("data-a11y-text-size", "");
      document.documentElement.removeAttribute("data-a11y-text-size");
    });

    expect(screen.queryByRole("button", { name: "עוד" })).toBeNull();
  });
});
