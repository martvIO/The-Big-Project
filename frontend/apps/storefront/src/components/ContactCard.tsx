import { useTranslation } from "react-i18next";
import { Card, ContactPanel } from "@boutique/ui";
import type { BoutiqueResponse } from "../api";
import { contactChannels, contactLabels } from "../lib/contact";

// The contact block in a card. Three screens render it — /about, the catalog's
// empty state, and the booking flow's phone-only exits — so the derivations
// live in lib/contact.ts and the Card is the only thing this adds.
export function ContactCard({
  boutique,
  className,
}: {
  boutique: BoutiqueResponse;
  className?: string;
}) {
  const { t } = useTranslation();

  const channels = contactChannels(boutique);
  // A freshly provisioned tenant has every profile field null; the Card would
  // otherwise degrade to a bare paper rectangle.
  if (channels === null) return null;

  return (
    <Card className={className}>
      <ContactPanel {...channels} labels={contactLabels(t)} />
    </Card>
  );
}
