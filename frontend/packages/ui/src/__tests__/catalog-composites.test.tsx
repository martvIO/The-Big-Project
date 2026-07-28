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

  it("reveals the photo once it loads", () => {
    render(<DressCard name="שמלה ה" href="/dress/5" photoUrl="/e.jpg" price={<span>5</span>} />);
    const img = screen.getByRole("img");
    expect(img.className).toContain("opacity-0");
    fireEvent.load(img);
    expect(img.className).toContain("opacity-100");
  });

  // A load failure means the presigned URL expired, not that the dress has no
  // photo — the page refetches rather than falling back to the monogram.
  it("reports a photo load failure so the page can refetch", () => {
    const onImageError = vi.fn();
    render(<DressCard name="שמלה ו" href="/dress/6" photoUrl="/f.jpg" price={<span>6</span>} onImageError={onImageError} />);
    fireEvent.error(screen.getByRole("img"));
    expect(onImageError).toHaveBeenCalledTimes(1);
  });

  it("survives a load failure when no handler is supplied", () => {
    render(<DressCard name="שמלה ז" href="/dress/7" photoUrl="/g.jpg" price={<span>7</span>} />);
    expect(() => fireEvent.error(screen.getByRole("img"))).not.toThrow();
  });

  it("defers grid photos off-screen", () => {
    render(<DressCard name="שמלה ח" href="/dress/8" photoUrl="/h.jpg" price={<span>8</span>} />);
    const img = screen.getByRole("img");
    expect(img).toHaveAttribute("loading", "lazy");
    expect(img).toHaveAttribute("decoding", "async");
  });

  it("emits no <img> to fail when there is no photo", () => {
    const onImageError = vi.fn();
    render(<DressCard name="שמלה ט" href="/dress/9" photoUrl={null} price={<span>9</span>} onImageError={onImageError} />);
    expect(screen.queryByRole("img")).toBeNull();
    expect(onImageError).not.toHaveBeenCalled();
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

  it("reports a main-image load failure so the page can refetch", () => {
    const onImageError = vi.fn();
    render(<Gallery images={images} labels={galleryLabels} onImageError={onImageError} />);
    fireEvent.error(screen.getByRole("img", { name: "שמלה תמונה 1" }));
    expect(onImageError).toHaveBeenCalledTimes(1);
  });

  it("reports a thumbnail load failure too — the whole set expires together", () => {
    const onImageError = vi.fn();
    const { container } = render(<Gallery images={images} labels={galleryLabels} onImageError={onImageError} />);
    const thumb = container.querySelectorAll("button img")[1];
    fireEvent.error(thumb);
    expect(onImageError).toHaveBeenCalledTimes(1);
  });

  it("reports a load failure from the lone image of a single-image gallery", () => {
    const onImageError = vi.fn();
    render(<Gallery images={[images[0]]} labels={galleryLabels} onImageError={onImageError} />);
    fireEvent.error(screen.getByRole("img", { name: "שמלה תמונה 1" }));
    expect(onImageError).toHaveBeenCalledTimes(1);
  });

  it("survives a load failure when no handler is supplied", () => {
    render(<Gallery images={images} labels={galleryLabels} />);
    expect(() => fireEvent.error(screen.getByRole("img", { name: "שמלה תמונה 1" }))).not.toThrow();
  });

  it("keeps the main image eager and defers only the thumbnails", () => {
    const { container } = render(<Gallery images={images} labels={galleryLabels} />);
    expect(screen.getByRole("img", { name: "שמלה תמונה 1" })).not.toHaveAttribute("loading", "lazy");
    for (const thumb of container.querySelectorAll("button img")) {
      expect(thumb).toHaveAttribute("loading", "lazy");
    }
  });

  it("keeps the single-image main image eager", () => {
    render(<Gallery images={[images[0]]} labels={galleryLabels} />);
    expect(screen.getByRole("img", { name: "שמלה תמונה 1" })).not.toHaveAttribute("loading", "lazy");
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
