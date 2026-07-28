import { cn, focusRing } from "../lib/styles";
import { safeHref } from "../lib/url";

export interface ContactPanelLabels {
  call: string;
  whatsapp: string;
  waze: string;
  maps: string;
  // Optional: no caller can supply an Instagram handle until the profile carries
  // one, and a required-but-unusable label forces every call site to pass a dead
  // string. The row renders only when both the handle and its label exist.
  instagram?: string;
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
  // Tenant-supplied URLs are scheme-checked so a stored `javascript:` maps_url
  // can't execute — React does not neutralise a javascript: href.
  const waze = safeHref(wazeUrl);
  const maps = safeHref(mapsUrl);
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
      {waze && (
        <a href={waze} className={linkClass} rel="noopener noreferrer" target="_blank">
          {labels.waze}
        </a>
      )}
      {maps && (
        <a href={maps} className={linkClass} rel="noopener noreferrer" target="_blank">
          {labels.maps}
        </a>
      )}
      {instagram && labels.instagram && (
        <a
          href={`https://instagram.com/${instagram}`}
          className={linkClass}
          rel="noopener noreferrer"
          target="_blank"
        >
          <span>{labels.instagram}</span>
          {/* min-w-0 + overflow-wrap:anywhere is WCAG 1.4.10 (reflow), not
              cosmetics: a handle is a single unbreakable Latin token, so at
              200% text on a 375px viewport "@some.long.handle" is wider than
              its line and pushes the whole document sideways. `anywhere`
              rather than `break-word` because only `anywhere` breaks a token
              with no break opportunity at all. */}
          <bdi dir="ltr" className="min-w-0 text-ink-muted [overflow-wrap:anywhere]">
            @{instagram}
          </bdi>
        </a>
      )}
    </div>
  );
}
