import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Card } from "../components/Card";

describe("Card", () => {
  it("renders children on a paper surface", () => {
    render(<Card>תוכן</Card>);
    expect(screen.getByText("תוכן")).toBeInTheDocument();
  });

  it("adds a hover-elevate transition only when asked", () => {
    const { container, rerender } = render(<Card>x</Card>);
    expect(container.firstElementChild?.className).not.toContain("hover:shadow-md");
    rerender(<Card hoverElevate>x</Card>);
    expect(container.firstElementChild?.className).toContain("hover:shadow-md");
  });
});
