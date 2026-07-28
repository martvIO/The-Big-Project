import { useState } from "react";
import { useTranslation } from "react-i18next";
import { BookingCTA, Button, ContactPanel, Modal } from "@boutique/ui";
import type { BoutiqueResponse } from "../api";
import { contactLabels, waPhone, wazeUrl } from "../lib/contact";

/**
 * The E3 seam.
 *
 * The button is live, keyboard-reachable and opens a real contact panel — it
 * books nothing, and that is the SHIPPED v1 behaviour, not a placeholder to be
 * improved. E3 #14 replaces the panel's contents behind the same button.
 *
 * `inline` renders the panel trigger as a plain Button with no fixed bar. Two
 * screens need that: /about, where qa §7 requires no bottom bar at ANY width.
 * BookingCTA cannot be talked out of its bar by a className — its base is
 * `fixed inset-x-0 bottom-0` with only `md:static`, and `cn` is a naive joiner
 * with no tailwind-merge, so which rule wins is decided by stylesheet order
 * rather than by the caller.
 */
export interface BookingCTAButtonProps {
  boutique: BoutiqueResponse | null;
  inline?: boolean;
}

export function BookingCTAButton({ boutique, inline = false }: BookingCTAButtonProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);

  const trigger = (
    <Button className={inline ? "w-full" : undefined} onClick={() => { setOpen(true); }}>
      {t("booking.cta")}
    </Button>
  );

  return (
    <>
      {inline ? trigger : <BookingCTA>{trigger}</BookingCTA>}
      <Modal
        open={open}
        onClose={() => { setOpen(false); }}
        title={t("booking.panelTitle")}
        footer={
          <Button variant="secondary" onClick={() => { setOpen(false); }}>
            {t("booking.close")}
          </Button>
        }
      >
        <ContactPanel
          phone={boutique?.phone ?? undefined}
          whatsapp={waPhone(boutique?.phone)}
          wazeUrl={wazeUrl(boutique?.address)}
          mapsUrl={boutique?.maps_url ?? undefined}
          instagram={boutique?.instagram ?? undefined}
          labels={contactLabels(t)}
        />
      </Modal>
    </>
  );
}
