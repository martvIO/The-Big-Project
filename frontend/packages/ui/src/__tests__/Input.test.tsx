import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Input } from "../components/Input";
import { TextArea } from "../components/TextArea";

describe("Input", () => {
  it("associates its visible label with the field", () => {
    render(<Input label="מספר טלפון" />);
    expect(screen.getByLabelText("מספר טלפון")).toBeInTheDocument();
  });

  it("wires an error through aria-describedby + aria-invalid and announces it", () => {
    render(<Input label="מחיר" error="שדה חובה" />);
    const field = screen.getByLabelText("מחיר");
    expect(field).toHaveAttribute("aria-invalid", "true");
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("שדה חובה");
    expect(field.getAttribute("aria-describedby")).toContain(alert.id);
  });

  it("passes a dir override through for LTR islands", () => {
    render(<Input label="אתר" dir="ltr" defaultValue="example.com" />);
    expect(screen.getByLabelText("אתר")).toHaveAttribute("dir", "ltr");
  });
});

describe("TextArea", () => {
  it("shows a used/max counter when showCount + maxLength are set", () => {
    render(<TextArea label="תנאים" showCount maxLength={100} value="שלום" onChange={() => {}} />);
    expect(screen.getByText("4 / 100")).toBeInTheDocument();
  });
});
