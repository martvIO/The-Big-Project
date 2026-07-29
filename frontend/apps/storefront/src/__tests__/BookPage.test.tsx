import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import i18n from "../i18n";
import { BookPage } from "../routes/BookPage";

// The flow's shell only — the steps themselves are not built yet.

describe("BookPage", () => {
  it.each([
    ["slot", "booking.stepSlot"],
    ["details", "booking.stepDetails"],
    ["terms", "booking.stepTerms"],
    ["verify", "booking.stepOtp"],
    ["confirm", "booking.confirmTitle"],
  ] as const)("titles the %s step with its own h1", (step, key) => {
    render(<BookPage step={step} />);

    // The h1 is the step, never the boutique: a static string has no state
    // where a failed fetch leaves the page untitled.
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(i18n.t(key));
  });

  it("marks the current step in an inert stepper", () => {
    render(<BookPage step="terms" />);

    const stepper = screen.getByRole("list", { name: i18n.t("booking.stepsLabel") });
    expect(within(stepper).queryAllByRole("link")).toHaveLength(0);
    expect(stepper.querySelectorAll('[aria-current="step"]')).toHaveLength(1);
    expect(stepper.querySelector('[aria-current="step"]')).toHaveTextContent(
      i18n.t("booking.stepTerms"),
    );
  });

  it("drops the stepper on confirm — it is terminal, outside the flow", () => {
    render(<BookPage step="confirm" />);
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
  });
});
