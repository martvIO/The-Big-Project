import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { StorefrontTerms } from "../api";
import { TermsConsent } from "../components/booking/TermsConsent";
import i18n from "../i18n";

// Importing the app's i18n instance initialises the default one useTranslation
// reads, so every label below is the production Hebrew.
void i18n;

// The legal block has TWO callers now (design F-O4): /book's terms step and
// /w/{token}. This file guards the extraction itself — that one render carries
// the two numbers, the owner's prose and the consent tick, and that the tick is
// what gates consent. BookPage.test.tsx and OfferPage.test.tsx each cover their
// own caller's wiring; neither can catch a drift INSIDE the shared block.

function terms(patch: Partial<StorefrontTerms> = {}): StorefrontTerms {
  return {
    version: 3,
    terms_text: "ביטול עד 48 שעות לפני המועד מזכה בהחזר מלא.",
    refundable_until_hours_before: 48,
    forfeit_percent: 50,
    ...patch,
  };
}

describe("TermsConsent", () => {
  it("renders the two numbers she is actually agreeing to", () => {
    render(<TermsConsent terms={terms()} accepted={false} onAcceptedChange={() => undefined} />);

    expect(screen.getByText("48")).toBeInTheDocument();
    // The % rides INSIDE the same node as the digits — "50%" is ONE LTR run
    // (R19), not a digit run and a stray neutral that bidi reorders.
    expect(screen.getByText("50%")).toBeInTheDocument();
  });

  it("isolates both numbers in an LTR bdi island", () => {
    // R19: each number sits mid-Hebrew-sentence, which is exactly where an
    // un-isolated Latin/digit run gets reordered on a real phone. A plain <span>
    // would render identically in jsdom and wrongly in production.
    render(<TermsConsent terms={terms()} accepted={false} onAcceptedChange={() => undefined} />);

    for (const value of ["48", "50%"]) {
      const node = screen.getByText(value);
      expect(node.tagName).toBe("BDI");
      expect(node).toHaveAttribute("dir", "ltr");
    }
  });

  it("renders the owner's prose as TEXT and never as markup", () => {
    // This is a public, anonymous, multi-tenant surface. The owner is
    // semi-trusted, so any HTML path here is stored XSS for every visitor of
    // her storefront — the assertion is that the tags arrive as characters.
    const injected = '<img src=x onerror="alert(1)"> ביטול חופשי';
    const { container } = render(
      <TermsConsent
        terms={terms({ terms_text: injected })}
        accepted={false}
        onAcceptedChange={() => undefined}
      />,
    );

    expect(screen.getByText(injected)).toBeInTheDocument();
    expect(container.querySelector("img")).toBeNull();
  });

  it("puts the tick LAST in document order, after the prose it consents to", () => {
    // A consent control reachable before the thing consented to is how unread
    // consent happens — and tab order follows document order.
    const { container } = render(
      <TermsConsent terms={terms()} accepted={false} onAcceptedChange={() => undefined} />,
    );

    const prose = screen.getByText(terms().terms_text);
    const tick = screen.getByRole("checkbox");
    // Node.DOCUMENT_POSITION_FOLLOWING === 4.
    expect(prose.compareDocumentPosition(tick) & 4).toBe(4);
    expect(container).not.toBeEmptyDOMElement();
  });

  it("gates its callback on the tick and reports the new value", () => {
    const onAcceptedChange = vi.fn();
    render(
      <TermsConsent terms={terms()} accepted={false} onAcceptedChange={onAcceptedChange} />,
    );

    expect(onAcceptedChange).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("checkbox"));
    expect(onAcceptedChange).toHaveBeenCalledWith(true);
  });

  it("shows the caller's error on the tick", () => {
    // Both callers pass their own message (booking.acceptRequired), so the block
    // renders one it is given rather than owning a second copy of the copy.
    render(
      <TermsConsent
        terms={terms()}
        accepted={false}
        error={i18n.t("booking.acceptRequired")}
        onAcceptedChange={() => undefined}
      />,
    );

    expect(screen.getByText(i18n.t("booking.acceptRequired"))).toBeInTheDocument();
  });
});
