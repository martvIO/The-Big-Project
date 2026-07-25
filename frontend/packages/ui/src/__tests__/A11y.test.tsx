import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SkipLink, VisuallyHidden } from "../components/A11y";

describe("A11y utilities", () => {
  it("SkipLink points at the main fragment and is a real link", () => {
    render(<SkipLink href="#main">דלג לתוכן</SkipLink>);
    const link = screen.getByRole("link", { name: "דלג לתוכן" });
    expect(link).toHaveAttribute("href", "#main");
  });

  it("VisuallyHidden keeps content in the accessibility tree", () => {
    render(<VisuallyHidden>הסבר לקורא מסך</VisuallyHidden>);
    expect(screen.getByText("הסבר לקורא מסך")).toBeInTheDocument();
  });
});
