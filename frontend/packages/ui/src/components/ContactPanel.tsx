import { cn, focusRing } from "../lib/styles";

export interface ContactPanelLabels {
  call: string;
  whatsapp: string;
  waze: string;
  maps: string;
  instagram: string;
}

export interface ContactPanelProps {
  phone?: string;
  whatsapp?: string; // digits for wa.me
  wazeUrl?: string;
  mapsUrl?: string;
  instagram?: string; // handle without @
  labels: ContactPanelLabels;
  className?: string;
}

const linkClass = cn(
  "inline-flex items-center gap-1 rounded-sm text-base text-gold-text underline",
  focusRing,
);

// Tap-to-call, WhatsApp deep link, Waze + Google Maps, Instagram. Latin/URL runs
// (the Instagram handle) are LTR-isolated inside the RTL panel.
export function ContactPanel({ phone, whatsapp, wazeUrl, mapsUrl, instagram, labels, className }: ContactPanelProps) {
  return (
    <div className={cn("flex flex-col gap-3", className)}>
      {phone && (
        <a href={`tel:${phone}`} className={linkClass}>
          {labels.call}
        </a>
      )}
      {whatsapp && (
        <a href={`https://wa.me/${whatsapp}`} className={linkClass} rel="noopener noreferrer" target="_blank">
          {labels.whatsapp}
        </a>
      )}
      {wazeUrl && (
        <a href={wazeUrl} className={linkClass} rel="noopener noreferrer" target="_blank">
          {labels.waze}
        </a>
      )}
      {mapsUrl && (
        <a href={mapsUrl} className={linkClass} rel="noopener noreferrer" target="_blank">
          {labels.maps}
        </a>
      )}
      {instagram && (
        <a
          href={`https://instagram.com/${instagram}`}
          className={linkClass}
          rel="noopener noreferrer"
          target="_blank"
        >
          <span>{labels.instagram}</span>
          <bdi dir="ltr" className="text-ink-muted">
            @{instagram}
          </bdi>
        </a>
      )}
    </div>
  );
}
