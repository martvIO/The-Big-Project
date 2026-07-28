import { useTranslation } from "react-i18next";
import { Card, ContactPanel } from "@boutique/ui";
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
  return (
    <Card className={className}>
      <ContactPanel
        phone={boutique.phone ?? undefined}
        whatsapp={waPhone(boutique.phone)}
        wazeUrl={wazeUrl(boutique.address)}
        mapsUrl={boutique.maps_url ?? undefined}
        instagram={boutique.instagram ?? undefined}
        labels={contactLabels(t)}
      />
    </Card>
  );
}
