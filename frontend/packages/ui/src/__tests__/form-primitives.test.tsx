import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Select } from "../components/Select";
import { Toggle } from "../components/Toggle";
import { DateField, TimeField } from "../components/DateTimeFields";

describe("Select", () => {
  it("labels a native select and renders its options", () => {
    render(
      <Select label="קהל יעד">
        <option value="all">כולם</option>
        <option value="brides">כלות בלבד</option>
      </Select>,
    );
    const select = screen.getByLabelText("קהל יעד");
    expect(select.tagName).toBe("SELECT");
    expect(screen.getByRole("option", { name: "כלות בלבד" })).toBeInTheDocument();
  });
});

describe("Toggle", () => {
  it("exposes a switch that reports changes", () => {
    const onChange = vi.fn();
    render(<Toggle label="דרוש מקדמה" description="חיוב בעת קביעת התור" checked={false} onCheckedChange={onChange} />);
    const sw = screen.getByRole("switch", { name: /דרוש מקדמה/ });
    fireEvent.click(sw);
    expect(onChange).toHaveBeenCalledWith(true);
  });
});

describe("TimeField / DateField", () => {
  it("render native time and date inputs with visible labels", () => {
    render(
      <>
        <TimeField label="פתיחה" />
        <DateField label="תאריך חריג" />
      </>,
    );
    expect(screen.getByLabelText("פתיחה")).toHaveAttribute("type", "time");
    expect(screen.getByLabelText("תאריך חריג")).toHaveAttribute("type", "date");
  });
});
