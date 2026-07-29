import { render, screen } from "@testing-library/react";
import { createRef } from "react";
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

  it("exposes the native input through ref", () => {
    const ref = createRef<HTMLInputElement>();
    render(<Input label="שם מלא" ref={ref} />);
    expect(ref.current).toBeInstanceOf(HTMLInputElement);
  });
});

describe("TextArea", () => {
  it("shows a used/max counter when showCount + maxLength are set", () => {
    render(<TextArea label="תנאים" showCount maxLength={100} value="שלום" onChange={() => {}} />);
    expect(screen.getByText("4 / 100")).toBeInTheDocument();
  });

  it("isolates the counter as an LTR run — it is bare numerals in an RTL page", () => {
    render(<TextArea label="תנאים" showCount maxLength={100} value="שלום" onChange={() => {}} />);
    const counter = screen.getByText("4 / 100");
    expect(counter.tagName).toBe("BDI");
    expect(counter).toHaveAttribute("dir", "ltr");
  });

  it("exposes the native textarea through ref", () => {
    const ref = createRef<HTMLTextAreaElement>();
    render(<TextArea label="הערות" ref={ref} />);
    expect(ref.current).toBeInstanceOf(HTMLTextAreaElement);
  });
});
