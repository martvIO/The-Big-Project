import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Badge } from "../components/Badge";

describe("Badge", () => {
  it("renders each variant with its text (word carries the meaning)", () => {
    const { rerender } = render(<Badge variant="muted">במלאי (3)</Badge>);
    expect(screen.getByText("במלאי (3)")).toBeInTheDocument();
    rerender(<Badge variant="warning">אזל מהמלאי</Badge>);
    expect(screen.getByText("אזל מהמלאי")).toBeInTheDocument();
    rerender(<Badge variant="danger">בארכיון</Badge>);
    expect(screen.getByText("בארכיון")).toBeInTheDocument();
  });
});
