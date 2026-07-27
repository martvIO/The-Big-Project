import { useState } from "react";
import { cn, focusRing } from "../lib/styles";

export interface GalleryImage {
  url: string;
  alt: string;
}

export interface GalleryLabels {
  previous: string;
  next: string;
  // "תמונה {n} מתוך {total}" — supplied by the app's i18n.
  imageOf: (n: number, total: number) => string;
}

export interface GalleryProps {
  images: GalleryImage[];
  labels: GalleryLabels;
  // A failed load means the presigned URLs expired — the whole set signs and
  // expires together, so any one failure asks the page to refetch.
  onImageError?: () => void;
  className?: string;
}

// Keyboard + AT operable: focusable prev/next + thumbnail buttons, current
// position exposed via aria-current. Advances on user input only — no timer,
// no auto-advance. A single image hides the chrome entirely.
export function Gallery({ images, labels, onImageError, className }: GalleryProps) {
  const [index, setIndex] = useState(0);

  if (images.length === 0) return null;
  if (images.length === 1) {
    return (
      <img
        src={images[0].url}
        alt={images[0].alt}
        onError={onImageError}
        className={cn("aspect-[3/4] w-full rounded-md object-cover", className)}
      />
    );
  }

  const current = images[Math.min(index, images.length - 1)];

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      <div className="relative">
        {/* Stays eager: this is the detail page's LCP element. Do not add
            loading="lazy" here — it costs the largest paint. */}
        <img
          src={current.url}
          alt={current.alt}
          onError={onImageError}
          className="aspect-[3/4] w-full rounded-md object-cover"
        />
        <button
          type="button"
          aria-label={labels.previous}
          disabled={index === 0}
          onClick={() => setIndex((i) => Math.max(0, i - 1))}
          className={cn(
            "absolute inset-s-2 top-1/2 flex size-11 -translate-y-1/2 items-center justify-center",
            "rounded-full bg-surface-raised text-ink shadow-md disabled:opacity-40",
            focusRing,
          )}
        >
          ‹
        </button>
        <button
          type="button"
          aria-label={labels.next}
          disabled={index === images.length - 1}
          onClick={() => setIndex((i) => Math.min(images.length - 1, i + 1))}
          className={cn(
            "absolute inset-e-2 top-1/2 flex size-11 -translate-y-1/2 items-center justify-center",
            "rounded-full bg-surface-raised text-ink shadow-md disabled:opacity-40",
            focusRing,
          )}
        >
          ›
        </button>
      </div>
      <div className="flex gap-2 overflow-x-auto pb-2">
        {images.map((img, i) => (
          <button
            key={i}
            type="button"
            aria-label={labels.imageOf(i + 1, images.length)}
            aria-current={i === index ? "true" : undefined}
            onClick={() => setIndex(i)}
            className={cn(
              "size-14 shrink-0 overflow-hidden rounded-sm",
              i === index ? "outline-2 outline-gold-strong" : "opacity-70",
              focusRing,
            )}
          >
            <img
              src={img.url}
              alt=""
              aria-hidden="true"
              loading="lazy"
              onError={onImageError}
              className="h-full w-full object-cover"
            />
          </button>
        ))}
      </div>
    </div>
  );
}
