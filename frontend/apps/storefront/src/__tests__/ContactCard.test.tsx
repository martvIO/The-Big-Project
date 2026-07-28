import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { BoutiqueResponse } from "../api";
import { ContactCard } from "../components/ContactCard";
import i18n from "../i18n";

// Importing the app's i18n instance initialises the default one useTranslation
// reads, so the labels below are the production strings.
void i18n;

function boutique(patch: Partial<BoutiqueResponse> = {}): BoutiqueResponse {
  return {
    name: "בוטיק אלמה",
    essence: null,
    description: null,
    phone: null,
    address: null,
    maps_url: null,
    instagram: null,
    hours: [],
    exceptions: [],
    ...patch,
  };
}

describe("ContactCard", () => {
  // The state every tenant is provisioned in. ContactPanel emits zero children,
  // so the Card was painting a bare paper rectangle on /about and under the
  // catalog empty state.
  it("renders nothing when the profile carries no contact field at all", () => {
    const { container } = render(<ContactCard boutique={boutique()} />);
    expect(container).toBeEmptyDOMElement();
  });

  // An unsafe scheme is dropped by ContactPanel before it reaches an href, so it
  // is not something to show — counting it would put the empty card back.
  it("renders nothing when the only contact is a maps_url with an unsafe scheme", () => {
    const { container } = render(
      // eslint-disable-next-line no-script-url
      <ContactCard boutique={boutique({ maps_url: "javascript:alert(1)" })} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("still renders the card as soon as one field is present", () => {
    render(<ContactCard boutique={boutique({ phone: "052-1234567" })} />);
    expect(screen.getByRole("link", { name: i18n.t("contact.call") })).toHaveAttribute("href", "tel:052-1234567");
  });

  it("renders the card for an address alone — Waze needs no phone", () => {
    render(<ContactCard boutique={boutique({ address: "דיזנגוף 99, תל אביב" })} />);
    expect(screen.getByRole("link", { name: i18n.t("contact.waze") })).toBeInTheDocument();
  });
});
