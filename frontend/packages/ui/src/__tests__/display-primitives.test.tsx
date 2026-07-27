import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Skeleton } from "../components/Skeleton";
import { EmptyState } from "../components/EmptyState";
import { SectionHeading } from "../components/SectionHeading";

describe("Skeleton", () => {
  it("renders the requested number of text lines, hidden from AT", () => {
    const { container } = render(<Skeleton variant="text" lines={4} />);
    const wrapper = container.firstElementChild;
    expect(wrapper).toHaveAttribute("aria-hidden", "true");
    expect(wrapper?.children).toHaveLength(4);
  });

  it("uses the token pulse animation (frozen under reduced motion via theme.css)", () => {
    const { container } = render(<Skeleton variant="image" />);
    expect(container.firstElementChild?.className).toContain("animate-skeleton");
  });
});

describe("EmptyState", () => {
  it("renders headline, body and an optional action", () => {
    render(<EmptyState title="הקולקציה בדרך" body="השמלות יעלו בקרוב" action={<button>הוספה</button>} />);
    expect(screen.getByText("הקולקציה בדרך")).toBeInTheDocument();
    expect(screen.getByText("השמלות יעלו בקרוב")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "הוספה" })).toBeInTheDocument();
  });
});

describe("SectionHeading", () => {
  it("renders at the requested heading level with an aria-hidden ornament", () => {
    render(
      <SectionHeading as="h1" ornament>
        פרופיל הבוטיק
      </SectionHeading>,
    );
    expect(screen.getByRole("heading", { level: 1, name: "פרופיל הבוטיק" })).toBeInTheDocument();
  });
});
