import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { formatDateRange } from "@boutique/ui";
import { RangeText } from "../lib/dateRange";

// ⚠ BOTH SHAPES ARE REAL, roughly once a month. A Sunday-start week that crosses
// a month boundary is `formatDateRange`'s `split` case with different bidi
// isolation from the `same-month` one, and a component that renders only the
// first is correct for three weeks in four.
const NOW = new Date("2026-11-01T00:00:00Z");

describe("RangeText", () => {
  it("puts the numeral run in one LTR island for a same-month week", () => {
    render(<RangeText range={formatDateRange("2026-11-08", "2026-11-14", NOW)} />);
    const island = screen.getByText("8–14");
    expect(island.tagName).toBe("BDI");
    expect(island).toHaveAttribute("dir", "ltr");
    expect(screen.getByText("בנובמבר")).toBeInTheDocument();
  });

  it("gives each whole date its own BARE island when the week splits a month", () => {
    // ⚠ NO dir="ltr" ON A SPLIT PART. Each carries its own Hebrew month, and an
    // LTR base direction reorders it — «29 בנובמבר» would render «בנובמבר 29».
    const { container } = render(
      <RangeText range={formatDateRange("2026-11-29", "2026-12-05", NOW)} />,
    );
    const islands = Array.from(container.querySelectorAll("bdi"));
    expect(islands).toHaveLength(2);
    for (const island of islands) {
      expect(island).not.toHaveAttribute("dir");
    }
    expect(islands[0].textContent).toBe("29 בנובמבר");
    expect(islands[1].textContent).toBe("5 בדצמבר");
  });
});
