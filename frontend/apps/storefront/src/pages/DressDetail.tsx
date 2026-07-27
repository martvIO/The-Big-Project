import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Badge,
  BookingCTA,
  Button,
  ContactPanel,
  Gallery,
  Modal,
  Price,
  Skeleton,
  cn,
  focusRing,
  useToast,
} from "@boutique/ui";
import type { GalleryImage } from "@boutique/ui";
import { FALLBACK_ERROR_MESSAGE, api, getBoutiqueOnce, isNotFound } from "../api";
import type { PublicBoutiqueResponse, PublicDressDetailResponse } from "../api";
import { contactLabels, wazeUrl, whatsappDigits } from "../lib/contact";
import { Link } from "../router";

export interface DressDetailProps {
  dressId: string;
}

// ponytail: the clamp expander appears on a character count, not on measured
// overflow — a 6-line clamp is only knowable after layout, and jsdom/SSR have
// none. Ceiling: a description just over the line will show a "עוד" that
// reveals one extra line. Upgrade path if that reads badly in browser QA:
// ResizeObserver + scrollHeight > clientHeight on the paragraph.
const DESCRIPTION_CLAMP_CHARS = 300;

// A dress named in Latin script only ("Bella Rosa") needs its own LTR run,
// or the RTL paragraph direction reorders it around neighbouring punctuation.
const HEBREW = /[\u0590-\u05FF]/;
const LATIN = /[A-Za-z]/;

// The page gutter steps 16 -> 24 -> 48 with the design's three widths. The fixed
// CTA bar's footprint is reserved by App's page shell, which wraps <main> AND
// <footer> — a reservation inside <main> cannot clear content outside it, which
// is how the statutory הצהרת נגישות link ended up under the bar (qa §7).
const pageClass = "mx-auto flex max-w-[1200px] flex-col gap-6 px-4 py-6 md:px-6 xl:px-12";

const backLinkClass = cn("rounded-sm text-sm text-gold-text underline", focusRing);

export function DressDetail({ dressId }: DressDetailProps) {
  const { t } = useTranslation();
  const toast = useToast();
  const [dress, setDress] = useState<PublicDressDetailResponse | null>(null);
  // "notFound" is the archived / unknown / foreign-tenant 404, which the wire
  // makes indistinguishable on purpose; "failed" is everything else.
  const [loadError, setLoadError] = useState<"notFound" | "failed" | null>(null);
  const [boutique, setBoutique] = useState<PublicBoutiqueResponse | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [bookingOpen, setBookingOpen] = useState(false);
  const [reloads, setReloads] = useState(0);

  // ponytail: one retry, ever. A stale presigned URL is fixed by refetching;
  // an object that is genuinely gone errors again on the fresh URL, and without
  // this ceiling that pair would loop the endpoint forever.
  const retried = useRef(false);

  useEffect(() => {
    let cancelled = false;
    api
      .getDress(dressId)
      .then((data) => {
        if (!cancelled) {
          setDress(data);
          setLoadError(null);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setDress(null);
          setLoadError(isNotFound(error) ? "notFound" : "failed");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [dressId, reloads]);

  // A different dress is a different page: its description starts collapsed and
  // it gets its own retry budget. The component itself never unmounts between
  // two /dress/:id routes, so neither resets on its own.
  useEffect(() => {
    retried.current = false;
    setExpanded(false);
  }, [dressId]);

  // WCAG 2.4.2 (Level A): the title has to name THIS dress, or two dresses are
  // indistinguishable in a tab strip, in history and in a bookmark. The name is
  // only knowable here — Router sets doc.dress as the placeholder while the
  // fetch is in flight, and re-runs on every navigation, so this only ever
  // upgrades the current route's title and can never be inherited by the next
  // one. Same string as the gallery alt, deliberately.
  useEffect(() => {
    if (dress !== null) document.title = dress.name;
  }, [dress]);

  useEffect(() => {
    let cancelled = false;
    getBoutiqueOnce()
      .then((data) => {
        if (!cancelled) setBoutique(data);
      })
      .catch(() => {
        // Contact details are the booking panel's content, not the page's. The
        // dress still renders, and App's footer owns the same failure.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleImageError = () => {
    if (retried.current) return;
    retried.current = true;
    setReloads((n) => n + 1);
  };

  const handleShare = () => {
    const url = window.location.href;
    const title = dress?.name ?? "";
    if (typeof navigator.share === "function") {
      void navigator.share({ title, url }).catch(() => {
        // The user dismissed the sheet, or the browser refused. Either way the
        // link is untouched — nothing to report.
      });
      return;
    }
    // No share sheet and no clipboard means an insecure origin. Say so rather
    // than leaving the button inert with no explanation.
    const copied = navigator.clipboard?.writeText(url);
    if (copied === undefined) {
      toast({ message: FALLBACK_ERROR_MESSAGE, variant: "error" });
      return;
    }
    void copied
      .then(() => {
        toast({ message: t("dress.shareCopied") });
      })
      .catch(() => {
        toast({ message: FALLBACK_ERROR_MESSAGE, variant: "error" });
      });
  };

  if (loadError !== null) {
    return (
      <div className={pageClass}>
        <p role="alert" className="font-display text-xl text-ink">
          {loadError === "notFound" ? t("dress.unavailable") : t("dress.error")}
        </p>
        <div className="flex flex-wrap items-center gap-4">
          <Link to="/" className={backLinkClass}>
            {t("dress.backToCatalog")}
          </Link>
          {/* Retrying a 404 just repeats it — an archived dress is gone for good. */}
          {loadError === "failed" && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                setReloads((n) => n + 1);
              }}
            >
              {t("common.retry")}
            </Button>
          )}
        </div>
      </div>
    );
  }

  if (dress === null) {
    return (
      <div className={pageClass} data-testid="dress-detail-loading">
        <Link to="/" className={backLinkClass}>
          {t("nav.backToCatalog")}
        </Link>
        <div className="grid gap-6 md:grid-cols-[55fr_45fr] xl:grid-cols-[60fr_40fr]">
          <Skeleton variant="image" className="rounded-md" />
          <Skeleton variant="text" lines={5} />
        </div>
      </div>
    );
  }

  const images: GalleryImage[] = dress.media.flatMap((item) =>
    item.url === null ? [] : [{ url: item.url, alt: dress.name }],
  );
  const clampable = (dress.description?.length ?? 0) > DESCRIPTION_CLAMP_CHARS;
  const latinOnlyName = !HEBREW.test(dress.name) && LATIN.test(dress.name);

  const phone = boutique?.profile.phone ?? undefined;

  return (
    <div className={pageClass}>
      <Link to="/" className={backLinkClass}>
        {/* In RTL the way back points inline-start-to-end, i.e. rightwards. */}
        <span aria-hidden="true">→</span> {t("nav.backToCatalog")}
      </Link>

      <div className="grid gap-6 md:grid-cols-[55fr_45fr] xl:grid-cols-[60fr_40fr]">
        {images.length > 0 ? (
          <Gallery
            images={images}
            labels={{
              previous: t("gallery.previous"),
              next: t("gallery.next"),
              imageOf: (n, total) => t("gallery.imageOf", { n, total }),
            }}
            onImageError={handleImageError}
          />
        ) : (
          // No photo is a dignified state, not a failure: the initial in the
          // display serif inside a gold hairline. No <img> is emitted at all,
          // so there is no broken-image glyph to fall back to.
          <div
            aria-hidden="true"
            data-testid="dress-monogram"
            className="flex aspect-[3/4] w-full items-center justify-center rounded-md border border-gold bg-surface"
          >
            <span className="font-display text-3xl text-gold">{dress.name.charAt(0)}</span>
          </div>
        )}

        {/* The facts column follows the gallery down only at the widest step —
            below that the gallery is short enough that sticky would fight the
            scroll. */}
        <div className="flex flex-col items-start gap-4 xl:sticky xl:top-6 xl:self-start">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="font-display text-2xl text-ink">
              {latinOnlyName ? <span dir="ltr">{dress.name}</span> : dress.name}
            </h1>
            {dress.reserved && <Badge variant="muted">{t("dress.reserved")}</Badge>}
          </div>

          <Price
            agorot={dress.price_agorot ?? 0}
            visible={dress.price_agorot !== null}
            hiddenLabel={t("price.hidden")}
          />

          <span aria-hidden="true" className="h-px w-full bg-gold" />

          {dress.description !== null && (
            <div className="flex flex-col items-start gap-2">
              <p className={cn("text-base text-ink-muted", clampable && !expanded && "line-clamp-6")}>
                {dress.description}
              </p>
              {/* No disclosure-state ARIA on this button: qa §10 requires the
                  storefront to stay clear of the nav vocabulary entirely, and
                  the label already carries the state — "עוד" while collapsed,
                  "פחות" once open. */}
              {clampable && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setExpanded((open) => !open);
                  }}
                >
                  {expanded ? t("dress.less") : t("dress.more")}
                </Button>
              )}
            </div>
          )}

          {dress.variants.length > 0 && (
            <div className="flex flex-col gap-2">
              <h2 className="font-body text-sm text-ink-muted">{t("dress.sizes")}</h2>
              {/* Informational chips, never buttons — the fitting is where a
                  size gets chosen. Availability is words, not colour. */}
              <ul className="flex flex-wrap gap-2">
                {dress.variants.map((variant) => (
                  <li key={variant.size_label}>
                    <Badge variant={variant.available ? "neutral" : "muted"}>
                      {variant.available
                        ? variant.size_label
                        : `${variant.size_label} · ${t("size.unavailable")}`}
                    </Badge>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Reserved does not disable this: booking a fitting for a dress
              someone else has taken is a boutique conversation, not a wall. */}
          <BookingCTA className="md:w-full">
            <Button
              className="w-full md:w-auto"
              onClick={() => {
                setBookingOpen(true);
              }}
            >
              {t("booking.cta")}
            </Button>
          </BookingCTA>

          <Button variant="ghost" size="sm" onClick={handleShare}>
            {t("dress.share")}
          </Button>
        </div>
      </div>

      <Modal
        open={bookingOpen}
        onClose={() => {
          setBookingOpen(false);
        }}
        title={t("booking.panelTitle")}
        footer={
          <Button
            variant="secondary"
            onClick={() => {
              setBookingOpen(false);
            }}
          >
            {t("booking.close")}
          </Button>
        }
      >
        <ContactPanel
          phone={phone}
          whatsapp={whatsappDigits(phone)}
          wazeUrl={wazeUrl(boutique?.profile.address)}
          mapsUrl={boutique?.profile.maps_url ?? undefined}
          labels={contactLabels(t)}
        />
      </Modal>
    </div>
  );
}
