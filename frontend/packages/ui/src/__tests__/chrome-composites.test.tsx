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

  // `inset-inline-0` is the CSS property, not a Tailwind utility — it compiles to
  // nothing and shrink-wraps the bar to its content at 375. `inset-x` is the
  // utility that emits `inset-inline`.
  it("spans the full inline axis with a utility Tailwind actually generates", () => {
    const { container } = render(
      <BookingCTA>
        <button>קביעת תור</button>
      </BookingCTA>,
    );
    const className = container.firstElementChild?.className ?? "";
    expect(className).toContain("inset-x-0");
    expect(className).not.toContain("inset-inline");
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

    const boost = screen.getByRole("button", { name: "טקסט גדול" });
    expect(boost).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(boost);
    expect(boost).toHaveAttribute("aria-pressed", "true");
    expect(document.documentElement).toHaveAttribute("data-a11y-text-size");
  });

  // The panel is a disclosure, not a menu. role="menuitemcheckbox" would need a
  // menu/menubar parent (axe aria-required-parent, wcag2a — and a closed-state
  // scan can never see it), and role="menu" would promise an APG keyboard
  // contract this component does not keep. aria-pressed toggle buttons owe
  // nothing beyond native button behaviour, which already works.
  it("exposes its controls as toggle buttons in a labelled group, not a menu", () => {
    render(<A11yMenu triggerLabel="נגישות" controls={a11yControls} />);
    const trigger = screen.getByRole("button", { name: "נגישות" });
    // aria-haspopup is synonymous with "menu" — it must not be here.
    expect(trigger).not.toHaveAttribute("aria-haspopup");
    fireEvent.click(trigger);

    expect(screen.queryByRole("menu")).toBeNull();
    expect(screen.queryAllByRole("menuitemcheckbox")).toHaveLength(0);

    const group = screen.getByRole("group");
    expect(group).toHaveAttribute("aria-labelledby", trigger.id);
    expect(trigger).toHaveAttribute("aria-controls", group.id);
    // Every control must sit inside that group, not merely beside it.
    for (const label of Object.values(a11yControls)) {
      const control = screen.getByRole("button", { name: label });
      expect(control).toHaveAttribute("aria-pressed");
      expect(group).toContainElement(control);
    }
  });

  it("drops aria-controls when closed so it never points at a missing element", () => {
    render(<A11yMenu triggerLabel="נגישות" controls={a11yControls} />);
    expect(screen.getByRole("button", { name: "נגישות" })).not.toHaveAttribute("aria-controls");
  });

  it("uses the PRE-1 clearance token when a booking bar is present", () => {
    const { container } = render(<A11yMenu triggerLabel="נגישות" controls={a11yControls} hasBookingBar />);
    expect(container.firstElementChild?.className).toContain("var(--space-a11y-clearance)");
  });
});
