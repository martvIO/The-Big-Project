import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Price } from "../components/Price";
import { HoursTable } from "../components/HoursTable";
import { BoutiqueHeader } from "../components/BoutiqueHeader";
import type { WeeklyRule } from "../lib/hours";

const DAY_LABELS = ["א׳", "ב׳", "ג׳", "ד׳", "ה׳", "ו׳", "שבת"];

describe("Price", () => {
  it("formats agorot as number-then-shekel, converting once", () => {
    render(<Price agorot={590000} visible hiddenLabel="מחיר בתיאום" />);
    expect(screen.getByText("5,900 ₪")).toBeInTheDocument();
  });

  it("shows the hidden label in the same slot when price is hidden", () => {
    render(<Price agorot={590000} visible={false} hiddenLabel="מחיר בתיאום" />);
    expect(screen.getByText("מחיר בתיאום")).toBeInTheDocument();
    expect(screen.queryByText(/₪/)).toBeNull();
  });
});

describe("HoursTable", () => {
  it("renders a Saturday closed row even when the rules omit Saturday", () => {
    // Sun–Fri open (identical, so they collapse), Saturday omitted -> Saturday
    // stands alone as a closed row rather than being dropped.
    const rules: WeeklyRule[] = [0, 1, 2, 3, 4, 5].map((dayOfWeek) => ({
      dayOfWeek,
      windows: [{ open: "10:00", close: "19:00" }],
    }));
    render(<HoursTable rules={rules} dayLabels={DAY_LABELS} closedLabel="סגור" />);
    const satRow = screen.getByText("שבת").closest("tr");
    expect(satRow).toHaveTextContent("סגור");
  });
});

describe("BoutiqueHeader", () => {
  it("renders closed-today in ink, never danger", () => {
    render(<BoutiqueHeader name="בוטיק כלה" hoursText="סגור היום · נפתח מחר ב-10:00" />);
    const snippet = screen.getByText("סגור היום · נפתח מחר ב-10:00");
    expect(snippet.className).toContain("text-ink-muted");
    expect(snippet.className).not.toContain("text-danger");
  });

  it("degrades the location to plain text when there is no maps URL", () => {
    render(<BoutiqueHeader name="בוטיק" address="הרצל 1, תל אביב" mapsUrl={null} />);
    expect(screen.queryByRole("link")).toBeNull();
    expect(screen.getByText("הרצל 1, תל אביב")).toBeInTheDocument();
  });
});
