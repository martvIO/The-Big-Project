import type { ContactPanelLabels } from "@boutique/ui";
import type { TFunction } from "i18next";

// Everything the four ContactPanel call sites used to copy between them.

// wa.me wants E.164 without the "+". Israeli numbers arrive as "052-1234567",
// where the leading 0 is the national trunk prefix the country code replaces.
export function whatsappDigits(phone: string | null | undefined): string | undefined {
  if (phone === null || phone === undefined) return undefined;
  const digits = phone.replace(/\D/g, "");
  if (digits === "") return undefined;
  if (digits.startsWith("972")) return digits;
  return digits.startsWith("0") ? `972${digits.slice(1)}` : digits;
}

export function wazeUrl(address: string | null | undefined): string | undefined {
  if (address === null || address === undefined || address === "") return undefined;
  return `https://waze.com/ul?q=${encodeURIComponent(address)}`;
}

// No `instagram` label: no storefront call site can supply an Instagram HANDLE,
// because PublicProfileResponse carries no such field, so the row can never
// render. Adding the field is an F7 schema change, out of scope here (same
// reasoning as `essence`). The catalog design's footer
// ("הצהרת נגישות · אינסטגרם · טלפון") therefore needs either that backend field
// or a design amendment before an Instagram link can exist at all.
export function contactLabels(t: TFunction): ContactPanelLabels {
  return {
    call: t("contact.call"),
    whatsapp: t("contact.whatsapp"),
    waze: t("contact.waze"),
    maps: t("contact.maps"),
  };
}
