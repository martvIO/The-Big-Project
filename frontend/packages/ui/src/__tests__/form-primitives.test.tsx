import { fireEvent, render, screen } from "@testing-library/react";
import { createRef } from "react";
import { describe, expect, it, vi } from "vitest";
import { Checkbox } from "../components/Checkbox";
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

  it("exposes the native select through ref", () => {
    const ref = createRef<HTMLSelectElement>();
    render(
      <Select label="מידה" ref={ref}>
        <option value="38">38</option>
      </Select>,
    );
    expect(ref.current).toBeInstanceOf(HTMLSelectElement);
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

describe("Checkbox", () => {
  it("is a real checkbox — no switch role — with the visible label as its accessible name", () => {
    render(<Checkbox label="קראתי ואני מסכימה לתנאים" checked={false} onCheckedChange={() => {}} />);
    const box = screen.getByRole("checkbox", { name: "קראתי ואני מסכימה לתנאים" });
    expect(box).not.toBeChecked();
    expect(box).not.toHaveAttribute("role");
    expect(screen.queryByRole("switch")).toBeNull();
  });

  it("reports toggling through onCheckedChange", () => {
    const onChange = vi.fn();
    render(<Checkbox label="אישור תנאים" checked={false} onCheckedChange={onChange} />);
    fireEvent.click(screen.getByRole("checkbox"));
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it("wires an error through aria-describedby + aria-invalid and announces it", () => {
    render(<Checkbox label="אישור תנאים" error="יש לאשר את התנאים" checked={false} onCheckedChange={() => {}} />);
    const box = screen.getByRole("checkbox");
    expect(box).toHaveAttribute("aria-invalid", "true");
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("יש לאשר את התנאים");
    expect(box.getAttribute("aria-describedby")).toContain(alert.id);
  });

  it("keeps the description out of the accessible name but tied via aria-describedby", () => {
    render(
      <Checkbox label="אישור תנאים" description="ניתן לבטל עד 48 שעות מראש" checked={false} onCheckedChange={() => {}} />,
    );
    const box = screen.getByRole("checkbox", { name: "אישור תנאים" });
    const desc = screen.getByText("ניתן לבטל עד 48 שעות מראש");
    expect(box.getAttribute("aria-describedby")).toContain(desc.id);
  });

  it("ships the ruled touch geometry: 44px label row wrapping a 24px box", () => {
    render(<Checkbox label="אישור תנאים" checked={false} onCheckedChange={() => {}} />);
    const box = screen.getByRole("checkbox");
    expect(box.className).toContain("size-6");
    expect(box.closest("label")?.className).toContain("min-h-11");
  });

  it("exposes the native input through ref", () => {
    const ref = createRef<HTMLInputElement>();
    render(<Checkbox label="אישור תנאים" checked={false} onCheckedChange={() => {}} ref={ref} />);
    expect(ref.current).toBeInstanceOf(HTMLInputElement);
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
