import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge, Button, Gallery, Price, Skeleton, cn, focusRing } from "@boutique/ui";
import type { GalleryImage } from "@boutique/ui";
import { api, errorMessageOr, isNotFound } from "../api";
import type { StorefrontDetail } from "../api";
import { BookingCTAButton } from "../components/BookingCTAButton";
import { DescriptionClamp } from "../components/DescriptionClamp";
import { Monogram } from "../components/Monogram";
import { ShareButton } from "../components/ShareButton";
import { useBoutique } from "../components/StorefrontLayout";
import { Link } from "../router";

export interface DressPageProps {
  dressId: string;
}

// A dress named in Latin script only ("Bella Rosa") needs its own LTR run,
// or the RTL paragraph direction reorders it around neighbouring punctuation.
const HEBREW = /[֐-׿]/;
const LATIN = /[A-Za-z]/;

// The page gutter steps 16 -> 24 -> 48 with the design's three widths. The fixed
// CTA bar's footprint is reserved by StorefrontLayout's page shell, which wraps
// <main> AND <footer> — a reservation inside <main> cannot clear content outside
// it, which is how the statutory הצהרת נגישות link ended up under the bar (§7).
const pageClass = "mx-auto flex max-w-[1200px] flex-col gap-6 px-4 py-6 md:px-6 xl:px-12";

const backLinkClass = cn("rounded-sm text-sm text-gold-text underline", focusRing);

export function DressPage({ dressId }: DressPageProps) {
  const { t } = useTranslation();
  const { boutique } = useBoutique();
  const [dress, setDress] = useState<StorefrontDetail | null>(null);
  // "notFound" is the archived / unknown / foreign-tenant 404, which the wire
  // makes indistinguishable on purpose; "failed" is everything else.
  const [loadError, setLoadError] = useState<"notFound" | "failed" | null>(null);
  const [failure, setFailure] = useState<unknown>(null);
  const [reloads, setReloads] = useState(0);

  // One retry, ever. A stale presigned URL is fixed by refetching; an object
  // that is genuinely gone errors again on the fresh URL, and without this
  // ceiling that pair would loop the endpoint forever.
  const retried = useRef(false);

  useEffect(() => {
    let cancelled = false;
    api
      .getDress(dressId)
      .then((data) => {
        if (!cancelled) {
          setDress(data);
          setLoadError(null);
          setFailure(null);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setDress(null);
          setFailure(error);
          setLoadError(isNotFound(error) ? "notFound" : "failed");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [dressId, reloads]);

  // A different dress is a different page: it gets its own retry budget. The
  // component itself never unmounts between two /dress/:id routes, so this does
  // not reset on its own.
  useEffect(() => {
    retried.current = false;
  }, [dressId]);

  // WCAG 2.4.2 (Level A): the title has to name THIS dress, or two dresses are
  // indistinguishable in a tab strip, in history and in a bookmark. The name is
  // only knowable here — Router sets document.dress as the placeholder while the
  // fetch is in flight, and re-runs on every navigation, so this only ever
  // upgrades the current route's title and can never be inherited by the next.
  useEffect(() => {
    if (dress !== null) document.title = dress.name;
  }, [dress]);

  const handleImageError = () => {
    if (retried.current) return;
    retried.current = true;
    setReloads((n) => n + 1);
  };

  // Carried by the archived, failed and loading states as well as the loaded
  // one, where the dress name takes over. The <h1> is where the skip link lands,
  // so a page whose only heading vanishes on a miss or an outage drops a
  // screen-reader user into an untitled region — and axe cannot catch it,
  // page-has-heading-one being best-practice rather than an A/AA rule.
  const identity = (
    <h1 className="font-display text-2xl text-ink">
      {boutique?.name ?? t("catalog.essenceFallback")}
    </h1>
  );

  if (loadError !== null) {
    return (
      <div className={pageClass}>
        {identity}
        {/* Muted body under the identity, matching the catalog's error block: a
            dress that is gone is not the boutique's fault, and the name above
            is what the page is now about. */}
        <p role="alert" className="text-base text-ink-muted">
          {loadError === "notFound"
            ? t("dress.unavailableDress")
            : errorMessageOr(failure, t, "dress.error")}
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
              {t("catalog.retry")}
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
          {t("dress.back")}
        </Link>
        {identity}
        <div className="grid gap-6 md:grid-cols-[55fr_45fr] xl:grid-cols-[60fr_40fr]">
          <Skeleton variant="image" className="rounded-md" />
          <Skeleton variant="text" lines={5} />
        </div>
      </div>
    );
  }

  // Filter first, then number: a null url (no bucket, or a signing failure) must
  // not consume a position, or the spoken "תמונה 2 מתוך 5" stops matching what
  // the visitor can actually page through.
  const usable = dress.media.filter((item) => item.url !== null);
  const images: GalleryImage[] = usable.map((item, index) => ({
    url: item.url ?? "",
    // The POSITION, not the dress name. Passing the name for all eight photos
    // gives a screen-reader user eight identical strings with no way to tell
    // them apart, while the thumbnails right below already announce position
    // correctly. The CARD's alt stays the dress name — that is F9's, and §6/§8
    // bind it.
    alt: t("gallery.imageOf", { n: index + 1, total: usable.length }),
  }));
  const latinOnlyName = !HEBREW.test(dress.name) && LATIN.test(dress.name);

  return (
    <div className={pageClass}>
      <Link to="/" className={backLinkClass}>
        {/* In RTL the way back points inline-start-to-end, i.e. rightwards. */}
        <span aria-hidden="true">→</span> {t("dress.back")}
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
          <Monogram boutiqueName={boutique?.name ?? dress.name} />
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
            hiddenLabel={t("catalog.priceOnRequest")}
          />

          <span aria-hidden="true" className="h-px w-full bg-gold" />

          {dress.description !== null && <DescriptionClamp text={dress.description} />}

          {dress.sizes.length > 0 && (
            <div className="flex flex-col items-start gap-2">
              <h2 className="text-sm text-ink-muted">{t("dress.sizes")}</h2>
              <ul className="flex flex-wrap gap-2">
                {dress.sizes.map((size) => (
                  <li key={size.size_label}>
                    <Badge variant={size.available ? "neutral" : "muted"}>
                      <bdi dir="ltr">{size.size_label}</bdi>
                      {/* Words, not just a dimmed chip: availability signalled
                          by colour alone fails WCAG 1.4.1. */}
                      <span className="sr-only">
                        {" "}
                        {size.available ? t("dress.available") : t("dress.unavailable")}
                      </span>
                    </Badge>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <ShareButton title={dress.name} />

          {/* Inline in the FACTS COLUMN at >=768, a fixed bar below it — §7
              places the detail page's CTA here, not in the header. */}
          <BookingCTAButton dressId={dressId} />
        </div>
      </div>
    </div>
  );
}
