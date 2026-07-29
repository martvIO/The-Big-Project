import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Button, ButtonLink } from "../components/Button";

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

  // A bare `transition-*` utility falls back to Tailwind's own default duration
  // and curve — neither is a project token (qa §2). Reduced motion still zeroes
  // it: theme.css kills the transition property itself.
  it("takes its transition duration and easing from the motion tokens", () => {
    render(<Button>שמירה</Button>);
    const className = screen.getByRole("button").className;
    expect(className).toContain("duration-(--motion-fast)");
    expect(className).toContain("ease-out");
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

  // Exact markup captured before ButtonLink moved in beside Button — the
  // extraction must not change a single byte of Button's own render.
  it("renders byte-identical markup to the pre-ButtonLink capture", () => {
    const { container } = render(
      <Button variant="primary" size="md" fullWidthMobile>
        קבעי תור
      </Button>,
    );
    expect(container.innerHTML).toBe(
      '<button type="button" class="relative inline-flex items-center justify-center rounded-md font-body font-semibold transition duration-(--motion-fast) ease-out disabled:cursor-not-allowed disabled:opacity-60 bg-gold text-ink hover:shadow-md min-h-11 px-4 text-base focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus w-full sm:w-auto"><span class="inline-flex items-center gap-2">קבעי תור</span></button>',
    );
  });
});

describe("ButtonLink", () => {
  it("renders a link carrying the same classes as the equivalent Button", () => {
    render(
      <>
        <ButtonLink href="/book/slot" variant="primary" size="md" fullWidthMobile>
          קבעי תור
        </ButtonLink>
        <Button variant="primary" size="md" fullWidthMobile>
          קבעי תור
        </Button>
      </>,
    );
    const link = screen.getByRole("link", { name: "קבעי תור" });
    expect(link).toHaveAttribute("href", "/book/slot");
    expect(link.className).toBe(screen.getByRole("button").className);
  });

  it("carries none of Button's button-only surface: no type, no disabled, no busy state", () => {
    render(<ButtonLink href="/about">אודות</ButtonLink>);
    const link = screen.getByRole("link", { name: "אודות" });
    expect(link).not.toHaveAttribute("type");
    expect(link).not.toHaveAttribute("disabled");
    expect(link).not.toHaveAttribute("aria-busy");
  });
});
