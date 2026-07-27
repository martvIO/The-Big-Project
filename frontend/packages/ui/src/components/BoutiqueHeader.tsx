import { cn, focusRing } from "../lib/styles";
import { safeHref } from "../lib/url";

export interface BoutiqueHeaderProps {
  name: string;
  essence?: string;
  // Today's hours snippet, composed by the app (Hebrew, i18n). Always rendered in
  // ink/ink-muted — closed-today is NOT an error, so it never uses danger.
  hoursText?: string;
  address?: string;
  mapsUrl?: string | null;
  className?: string;
}

export function BoutiqueHeader({ name, essence, hoursText, address, mapsUrl, className }: BoutiqueHeaderProps) {
  // Scheme-checked so a stored `javascript:` maps_url degrades to plain text.
  const maps = safeHref(mapsUrl);
  return (
    <header className={cn("flex flex-col gap-2", className)}>
      <h1 className="font-display text-3xl text-ink">{name}</h1>
      {essence && <p className="text-base text-ink-muted">{essence}</p>}
      {hoursText && <p className="text-base text-ink-muted">{hoursText}</p>}
      {address &&
        (maps ? (
          <a href={maps} dir="ltr" className={cn("text-base text-gold-text underline", focusRing)}>
            {address} <span aria-hidden="true">↗</span>
          </a>
        ) : (
          <span dir="ltr" className="text-base text-ink-muted">
            {address}
          </span>
        ))}
    </header>
  );
}
