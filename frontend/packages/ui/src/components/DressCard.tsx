import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import { cn, focusRing } from "../lib/styles";
import { Badge } from "./Badge";

export interface DressCardProps {
  name: string;
  href: string;
  price: ReactNode; // a <Price/> element
  photoUrl?: string | null;
  reserved?: boolean;
  reservedLabel?: string; // "הוזמן" via prop
  // A failed load means the presigned URL expired, not that the dress has no
  // photo — the page refetches instead of degrading to the monogram.
  onImageError?: () => void;
  className?: string;
}

export function DressCard({
  name,
  href,
  price,
  photoUrl,
  reserved = false,
  reservedLabel,
  onImageError,
  className,
}: DressCardProps) {
  const [loaded, setLoaded] = useState(false);
  const imgRef = useRef<HTMLImageElement>(null);

  // Cached path: if the image already loaded (warm reload), show it immediately
  // instead of leaving it stuck at opacity 0.
  useEffect(() => {
    if (imgRef.current?.complete) setLoaded(true);
  }, []);

  return (
    <a href={href} className={cn("group block", focusRing, className)}>
      {/* aspect-ratio reserves the slot before decode -> CLS 0. Card is never
          dimmed when reserved. */}
      <div className="relative aspect-[3/4] overflow-hidden rounded-md bg-surface shadow-sm">
        {photoUrl ? (
          <img
            ref={imgRef}
            src={photoUrl}
            alt={name}
            // The grid renders up to 24 unprocessed originals — the heaviest
            // egress path in v1. Only fetch what the visitor scrolls to.
            loading="lazy"
            decoding="async"
            onLoad={() => setLoaded(true)}
            onError={onImageError}
            className={cn(
              "h-full w-full object-cover transition-opacity duration-(--motion-base) ease-out",
              loaded ? "opacity-100" : "opacity-0",
            )}
          />
        ) : (
          // No photo -> monogram fills the slot, no <img> emitted at all.
          <div aria-hidden="true" className="flex h-full w-full items-center justify-center">
            <span className="font-display text-3xl text-gold">{name.charAt(0)}</span>
          </div>
        )}

        {reserved && reservedLabel && (
          <Badge variant="muted" className="absolute top-3 start-3 bg-surface-raised">
            {reservedLabel}
          </Badge>
        )}

        {/* Save-for-later slot: reserved layout box only (the feature ships in a
            later epic). No button, no icon, no client storage, not in the tab
            order. Inline-END so it never collides with the reserved badge on the
            inline-start. */}
        <span aria-hidden="true" className="absolute top-3 end-3 size-11" />
      </div>

      <div className="mt-2 flex flex-col gap-1">
        {/* A Latin-only dress name ("Bella Rosa (Ivory)") inside an RTL card is
            a bidi run whose trailing neutrals reorder — the closing bracket or
            full stop jumps to the wrong end. bdi resolves each name's direction
            on its own and isolates it from the card around it. */}
        <span className="font-display text-lg text-ink">
          <bdi>{name}</bdi>
        </span>
        {price}
      </div>
    </a>
  );
}
