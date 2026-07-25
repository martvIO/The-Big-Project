import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Button } from "../components/Button";

describe("Button", () => {
  it("renders its label as an accessible button", () => {
    render(
      <Button variant="primary" size="lg">
        שמירה
      </Button>,
    );
    expect(screen.getByRole("button", { name: "שמירה" })).toBeInTheDocument();
  });

  it("loading keeps the label in the DOM (width lock) and marks the button busy + disabled", () => {
    render(<Button loading>שמירה</Button>);
    const btn = screen.getByRole("button");
    expect(btn).toBeDisabled();
    expect(btn).toHaveAttribute("aria-busy", "true");
    // Label text stays rendered so the button keeps its natural width.
    expect(btn).toHaveTextContent("שמירה");
  });

  it("fires onClick when enabled and not while loading", () => {
    const onClick = vi.fn();
    const { rerender } = render(<Button onClick={onClick}>לחץ</Button>);
    screen.getByRole("button").click();
    expect(onClick).toHaveBeenCalledOnce();

    rerender(
      <Button onClick={onClick} loading>
        לחץ
      </Button>,
    );
    screen.getByRole("button").click();
    expect(onClick).toHaveBeenCalledOnce();
  });
});
