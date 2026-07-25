import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { BookingCTA } from "../components/BookingCTA";
import { ContactPanel } from "../components/ContactPanel";
import { A11yMenu, A11yStatementLink } from "../components/A11yMenu";

const contactLabels = {
  call: "התקשרו",
  whatsapp: "וואטסאפ",
  waze: "Waze",
  maps: "Google Maps",
  instagram: "אינסטגרם",
};

const a11yControls = {
  contrast: "ניגודיות גבוהה",
  textSize: "טקסט גדול",
  readableFont: "גופן קריא",
  underlineLinks: "קו תחתון לקישורים",
  stopMotion: "עצירת אנימציות",
};

afterEach(() => {
  for (const attr of ["data-a11y-contrast", "data-a11y-text-size"]) {
    document.documentElement.removeAttribute(attr);
  }
});

describe("BookingCTA", () => {
  it("renders as a fixed bottom bar carrying its action", () => {
    const { container } = render(
      <BookingCTA>
        <button>קביעת תור</button>
      </BookingCTA>,
    );
    expect(container.firstElementChild?.className).toContain("fixed");
    expect(screen.getByRole("button", { name: "קביעת תור" })).toBeInTheDocument();
  });
});

describe("ContactPanel", () => {
  it("wires tap-to-call, WhatsApp, Waze, Maps and Instagram", () => {
    render(
      <ContactPanel
        phone="0501234567"
        whatsapp="972501234567"
        wazeUrl="https://waze.com/ul/x"
        mapsUrl="https://maps.google.com/x"
        instagram="bridal_shop"
        labels={contactLabels}
      />,
    );
    expect(screen.getByRole("link", { name: "התקשרו" })).toHaveAttribute("href", "tel:0501234567");
    expect(screen.getByRole("link", { name: "וואטסאפ" })).toHaveAttribute("href", "https://wa.me/972501234567");
    expect(screen.getByRole("link", { name: "Waze" })).toHaveAttribute("href", "https://waze.com/ul/x");
    expect(screen.getByRole("link", { name: /אינסטגרם/ })).toHaveAttribute(
      "href",
      "https://instagram.com/bridal_shop",
    );
  });
});

describe("A11yStatementLink", () => {
  it("links to the accessibility statement", () => {
    render(<A11yStatementLink href="/accessibility">הצהרת נגישות</A11yStatementLink>);
    expect(screen.getByRole("link", { name: "הצהרת נגישות" })).toHaveAttribute("href", "/accessibility");
  });
});

describe("A11yMenu", () => {
  it("opens the menu and toggles a boost attribute on <html>", () => {
    render(<A11yMenu triggerLabel="נגישות" controls={a11yControls} />);
    const trigger = screen.getByRole("button", { name: "נגישות" });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");

    fireEvent.click(screen.getByRole("menuitemcheckbox", { name: "טקסט גדול" }));
    expect(document.documentElement).toHaveAttribute("data-a11y-text-size");
  });

  it("uses the PRE-1 clearance token when a booking bar is present", () => {
    const { container } = render(<A11yMenu triggerLabel="נגישות" controls={a11yControls} hasBookingBar />);
    expect(container.firstElementChild?.className).toContain("var(--space-a11y-clearance)");
  });
});
