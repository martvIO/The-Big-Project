import { useTranslation } from "react-i18next";
import { Card, ContactPanel, safeHref } from "@boutique/ui";
import type { BoutiqueResponse } from "../api";
import { contactLabels, waPhone, wazeUrl } from "../lib/contact";

// The contact block in a card. Two screens render it — /about and the catalog's
// empty state, where the design requires the storefront to still feel complete
// with zero dresses — so the four derivations live in one place.
export function ContactCard({
  boutique,
  className,
}: {
  boutique: BoutiqueResponse;
  className?: string;
}) {
  const { t } = useTranslation();

  const phone = boutique.phone ?? undefined;
  const whatsapp = waPhone(boutique.phone);
  // safeHref, not the raw fields: ContactPanel drops an unsafe scheme, so a
  // boutique whose only contact is a `javascript:` maps_url has nothing to show.
  const waze = safeHref(wazeUrl(boutique.address));
  const maps = safeHref(boutique.maps_url);
  const instagram = boutique.instagram ?? undefined;

  // A freshly provisioned tenant has every profile field null. ContactPanel then
  // emits zero children and the Card degrades to a bare paper rectangle on
  // /about and under the catalog empty state.
  if (!phone && !whatsapp && !waze && !maps && !instagram) return null;

  return (
    <Card className={className}>
      <ContactPanel
        phone={phone}
        whatsapp={whatsapp}
        wazeUrl={waze}
        mapsUrl={maps}
        instagram={instagram}
        labels={contactLabels(t)}
      />
    </Card>
  );
}
