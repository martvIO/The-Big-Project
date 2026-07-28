import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DressCard } from "../components/DressCard";

// A Latin-only dress name is a left-to-right run inside a right-to-left card.
// Neutral characters at its edges — brackets, a full stop, a hyphen — belong to
// whichever run wins the bidi resolution, so without isolation they jump to the
// wrong end: "Bella Rosa (Ivory)" renders as "(Bella Rosa (Ivory". The dress
// page already isolates its <h1>; the card is the same string in the same
// document direction.

describe("DressCard — bidi isolation of the dress name", () => {
  it.each([
    ["Bella Rosa (Ivory)", "trailing bracket"],
    ["Aria Blanc.", "trailing full stop"],
  ])("isolates %s (%s)", (name) => {
    render(<DressCard name={name} href="/dress/1" price={<span>1</span>} photoUrl="/a.jpg" />);

    expect(screen.getByText(name).tagName).toBe("BDI");
  });

  it("leaves a Hebrew name to the card's own direction", () => {
    render(<DressCard name="ורד" href="/dress/2" price={<span>2</span>} photoUrl="/b.jpg" />);

    // bdi resolves direction per name, so the same wrapper is correct for both
    // scripts — no locale sniffing, no dir="ltr" forced onto Hebrew.
    const isolated = screen.getByText("ורד");
    expect(isolated.tagName).toBe("BDI");
    expect(isolated).not.toHaveAttribute("dir", "ltr");
  });
});
