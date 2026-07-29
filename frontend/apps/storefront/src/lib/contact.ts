import { safeHref } from "@boutique/ui";
import type { ContactPanelLabels, ContactPanelProps } from "@boutique/ui";
import type { TFunction } from "i18next";
import type { BoutiqueResponse } from "../api";

// Everything the four ContactPanel call sites used to copy between them.
// Both derivations are pure functions of stored fields — neither whatsapp nor
// wazeUrl is a column.

/**
 * wa.me wants E.164 without the "+". Israeli numbers arrive as "052-1234567",
 * where the leading 0 is the national trunk prefix the country code replaces.
 *
 * A number that is neither already-972 nor 0-prefixed returns UNDEFINED rather
 * than being passed through. Guessing is worse than omitting: "1-800-555" would
 * otherwise mint wa.me/1800555 — a real, reachable, wrong number belonging to
 * someone else. No link beats a link to a stranger.
 */
export function waPhone(phone: string | null | undefined): string | undefined {
  if (phone === null || phone === undefined) return undefined;
  const digits = phone.replace(/\D/g, "");
  if (digits === "") return undefined;
  if (digits.startsWith("972")) return digits;
  if (digits.startsWith("0")) return `972${digits.slice(1)}`;
  return undefined;
}

export function wazeUrl(address: string | null | undefined): string | undefined {
  if (address === null || address === undefined || address === "") return undefined;
  return `https://waze.com/ul?q=${encodeURIComponent(address)}`;
}

/**
 * The panel's channels, or NULL when the boutique publishes none.
 *
 * A freshly provisioned tenant has every profile field null, and ContactPanel
 * then emits zero children — a literally empty flex box. Every call site has to
 * branch on that rather than render it, so the branch lives here once.
 *
 * safeHref, not the raw fields: the panel drops an unsafe scheme, so a boutique
 * whose only contact is a `javascript:` maps_url has nothing to show.
 */
export function contactChannels(
  boutique: BoutiqueResponse,
): Omit<ContactPanelProps, "labels"> | null {
  const phone = boutique.phone ?? undefined;
  const whatsapp = waPhone(boutique.phone);
  const waze = safeHref(wazeUrl(boutique.address));
  const maps = safeHref(boutique.maps_url);
  const instagram = boutique.instagram ?? undefined;

  if (!phone && !whatsapp && !waze && !maps && !instagram) return null;
  return { phone, whatsapp, wazeUrl: waze, mapsUrl: maps, instagram };
}

export function contactLabels(t: TFunction): ContactPanelLabels {
  return {
    call: t("contact.call"),
    whatsapp: t("contact.whatsapp"),
    waze: t("contact.waze"),
    maps: t("contact.maps"),
    instagram: t("contact.instagram"),
  };
}
