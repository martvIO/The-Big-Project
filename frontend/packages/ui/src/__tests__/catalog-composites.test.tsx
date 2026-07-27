import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DressCard } from "../components/DressCard";
import { DressGrid } from "../components/DressGrid";
import { Gallery } from "../components/Gallery";

const galleryLabels = {
  previous: "הקודם",
  next: "הבא",
  imageOf: (n: number, total: number) => `תמונה ${n} מתוך ${total}`,
};

describe("DressCard", () => {
  it("shows the reserved badge inline-start and does not dim the card", () => {
    const { container } = render(
      <DressCard name="שמלה א" href="/dress/1" photoUrl="/a.jpg" reserved reservedLabel="הוזמן" price={<span>1</span>} />,
    );
    expect(screen.getByText("הוזמן")).toBeInTheDocument();
    expect(container.innerHTML).not.toContain("opacity-50");
  });

  it("renders no <img> when there is no photo, keeping the dress name accessible", () => {
    render(<DressCard name="שמלת ערב" href="/dress/2" photoUrl={null} price={<span>2</span>} />);
    expect(screen.queryByRole("img")).toBeNull();
    expect(screen.getByText("שמלת ערב")).toBeInTheDocument();
  });

  it("takes the photo alt from the dress name", () => {
    render(<DressCard name="שמלה ג" href="/dress/3" photoUrl="/c.jpg" price={<span>3</span>} />);
    expect(screen.getByRole("img", { name: "שמלה ג" })).toBeInTheDocument();
  });

  it("shows a cached image immediately instead of leaving it invisible", () => {
    const spy = vi.spyOn(HTMLImageElement.prototype, "complete", "get").mockReturnValue(true);
    render(<DressCard name="שמלה ד" href="/dress/4" photoUrl="/d.jpg" price={<span>4</span>} />);
    expect(screen.getByRole("img").className).toContain("opacity-100");
    spy.mockRestore();
  });
});

describe("DressGrid", () => {
  it("lays its cards out in a grid", () => {
    const { container } = render(
      <DressGrid>
        <div>a</div>
        <div>b</div>
      </DressGrid>,
    );
    expect(container.firstElementChild?.className).toContain("grid");
  });
});

describe("Gallery", () => {
  const images = [
    { url: "/1.jpg", alt: "שמלה תמונה 1" },
    { url: "/2.jpg", alt: "שמלה תמונה 2" },
    { url: "/3.jpg", alt: "שמלה תמונה 3" },
  ];

  it("hides the chrome for a single image", () => {
    render(<Gallery images={[images[0]]} labels={galleryLabels} />);
    expect(screen.queryByRole("button", { name: "הבא" })).toBeNull();
    expect(screen.getByRole("img", { name: "שמלה תמונה 1" })).toBeInTheDocument();
  });

  it("exposes keyboard-reachable prev/next + thumbnails with aria-current", () => {
    render(<Gallery images={images} labels={galleryLabels} />);
    expect(screen.getByRole("button", { name: "הקודם" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "הבא" })).toBeInTheDocument();
    const thumb3 = screen.getByRole("button", { name: "תמונה 3 מתוך 3" });
    fireEvent.click(thumb3);
    expect(thumb3).toHaveAttribute("aria-current", "true");
  });
});

// A11yMenu writes to document.documentElement; keep tests isolated.
afterEach(() => {
  for (const attr of [
    "data-a11y-contrast",
    "data-a11y-text-size",
    "data-a11y-readable-font",
    "data-a11y-underline-links",
    "data-a11y-stop-motion",
  ]) {
    document.documentElement.removeAttribute(attr);
  }
});
