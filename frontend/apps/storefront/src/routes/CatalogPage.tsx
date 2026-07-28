import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  BoutiqueHeader,
  Button,
  DressCard,
  DressGrid,
  EmptyState,
  Price,
  Skeleton,
} from "@boutique/ui";
import { api, errorMessageOr } from "../api";
import type { StorefrontDress } from "../api";
import { BookingCTAButton } from "../components/BookingCTAButton";
import { HoursCard } from "../components/HoursCard";
import { useBoutique } from "../components/StorefrontLayout";
import { ContactCard } from "../components/ContactCard";
import { todayLine } from "../lib/hoursText";

const SKELETON_CARDS = 6;

export interface CatalogPageProps {
  // Injectable clock: pins the weekday so the closed-today branch is testable
  // without faking the machine's clock. The hours logic itself is
  // timezone-explicit (Asia/Jerusalem), never the device.
  now?: Date;
}

export function CatalogPage({ now = new Date() }: CatalogPageProps) {
  const { t } = useTranslation();
  // The identity block comes from the layout's single fetch; only the grid is
  // this route's own. A dress list that 503s (or 429s off the anonymous read
  // budget) must not take a boutique that answered down with it — the visitor
  // still gets the name, the hours, the address and a way to book.
  const {
    boutique,
    loading: boutiqueLoading,
    error: boutiqueError,
    retry: retryBoutique,
  } = useBoutique();
  const [dresses, setDresses] = useState<StorefrontDress[] | null>(null);
  const [total, setTotal] = useState(0);
  const [listError, setListError] = useState<unknown>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [attempt, setAttempt] = useState(0);
  // One refetch per page load. A signed URL that 404s because the object is
  // genuinely gone would otherwise re-sign, re-fail and loop forever.
  const photoRetried = useRef(false);
  // load-more resolves outside the mount effect's cancellation scope, so it
  // needs its own guard against setting state on an unmounted tree.
  const unmounted = useRef(false);

  useEffect(() => {
    unmounted.current = false;
    return () => {
      unmounted.current = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    api
      .listDresses()
      .then((page) => {
        if (cancelled) return;
        setDresses(page.items);
        setTotal(page.total);
        setListError(null);
      })
      .catch((error: unknown) => {
        if (!cancelled) setListError(error);
      });
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  const reload = () => {
    setListError(null);
    setDresses(null);
    setAttempt((n) => n + 1);
  };

  const handlePhotoError = () => {
    if (photoRetried.current) return;
    photoRetried.current = true;
    reload();
  };

  /**
   * "עוד שמלות" — the only path to dress 25 of the pilot's ~60.
   *
   * The server pins the page at 24, so a single un-paged call leaves 36 dresses
   * unreachable and E2's third success criterion fails. Paging advances by the
   * number of items already held rather than by a page counter, so a concurrent
   * insert cannot make the button skip a row.
   *
   * A failed "more" page keeps the dresses already on screen: losing the grid
   * because page two timed out is a worse outcome than a missing page.
   */
  const loadMore = () => {
    if (dresses === null || loadingMore) return;
    setLoadingMore(true);
    api
      .listDresses(dresses.length)
      .then((page) => {
        if (unmounted.current) return;
        setDresses((current) => [...(current ?? []), ...page.items]);
        setTotal(page.total);
        setListError(null);
      })
      .catch((error: unknown) => {
        if (!unmounted.current) setListError(error);
      })
      .finally(() => {
        if (!unmounted.current) setLoadingMore(false);
      });
  };

  const hoursText = boutique === null ? undefined : (todayLine(boutique, now, t) ?? undefined);
  const hasMore = dresses !== null && dresses.length < total;
  const boutiqueFailed = boutiqueError !== null && boutique === null;

  // Retry BOTH surfaces. The boutique block is fetched once by StorefrontLayout,
  // so a retry that only re-ran the dress list would leave a failed identity
  // failed forever — the button would look live and do nothing.
  const retryAll = () => {
    if (boutiqueFailed) retryBoutique();
    reload();
  };

  return (
    // The fixed CTA bar's footprint is reserved by StorefrontLayout's page
    // shell, which wraps <main> AND <footer> — a reservation inside <main>
    // cannot clear content that sits outside it (qa §7: הצהרת נגישות stays
    // tappable).
    <div className="mx-auto flex max-w-[1200px] flex-col gap-8 px-4 pt-8 pb-8 md:gap-12 md:px-6 xl:px-12">
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between md:gap-6">
        {boutiqueLoading ? (
          // A real header with a placeholder name would claim an identity the
          // boutique has not sent yet. Skeleton says "loading" honestly.
          <Skeleton variant="text" lines={2} className="md:max-w-[60%]" />
        ) : (
          // Rendered even when the boutique fetch FAILED, with the fallback
          // name. The degraded page must still have exactly one <h1>: it is
          // where the skip link lands, and a page whose only heading vanishes
          // on an API error leaves a screen-reader user in an untitled region.
          // axe would not catch it — page-has-heading-one is best-practice, not
          // an A/AA rule — so it is asserted in the e2e suite instead.
          <BoutiqueHeader
            name={boutique?.name ?? t("catalog.essenceFallback")}
            essence={boutique?.essence ?? undefined}
            hoursText={hoursText}
            address={boutique?.address ?? undefined}
            mapsUrl={boutique?.maps_url ?? undefined}
          />
        )}

        {/* Gated on the boutique, not on the dresses: booking is a phone call,
            and it stays offerable when only the collection failed to load. The
            CTA is withheld when identity failed rather than opening an empty
            contact panel. */}
        {boutique !== null && <BookingCTAButton boutique={boutique} />}
      </div>

      <div aria-hidden="true" className="h-px bg-gold" />

      {boutiqueFailed ? (
        // ONE alert, not two. When identity fails the dress list has almost
        // certainly failed with it — the same outage — and announcing it twice
        // makes a screen reader read two messages for one problem. The identity
        // failure is the headline, so it is the one that speaks.
        <div className="flex flex-col items-start gap-3">
          <p role="alert" className="text-base text-ink-muted">
            {errorMessageOr(boutiqueError, t, "about.error")}
          </p>
          <Button variant="secondary" onClick={retryAll}>
            {t("catalog.retry")}
          </Button>
        </div>
      ) : listError !== null && dresses === null ? (
        // Ink-muted, not danger: a backend that is down is not the boutique's
        // fault, and the header above still carries the identity.
        <div className="flex flex-col items-start gap-3">
          <p role="alert" className="text-base text-ink-muted">
            {errorMessageOr(listError, t, "catalog.error")}
          </p>
          <Button variant="secondary" onClick={retryAll}>
            {t("catalog.retry")}
          </Button>
        </div>
      ) : dresses === null ? (
        <DressGrid>
          {Array.from({ length: SKELETON_CARDS }, (_, index) => (
            <Skeleton key={index} variant="image" />
          ))}
        </DressGrid>
      ) : dresses.length === 0 ? (
        // The state the pilot goes live in, before a single photo is uploaded:
        // the boutique still has to feel complete, so the identity, hours and
        // contact block come along rather than a bare "nothing here yet".
        <div className="flex flex-col gap-6">
          <EmptyState title={t("catalog.empty")} body={t("catalog.emptyBody")} />
          {boutique !== null && (
            <>
              <HoursCard boutique={boutique} now={now} />
              <ContactCard boutique={boutique} />
            </>
          )}
        </div>
      ) : (
        <div className="flex flex-col items-center gap-8">
          <DressGrid>
            {dresses.map((item) => (
              <DressCard
                key={item.id}
                name={item.name}
                href={`/dress/${encodeURIComponent(item.id)}`}
                photoUrl={item.cover?.url}
                reserved={item.reserved}
                reservedLabel={t("catalog.reserved")}
                onImageError={handlePhotoError}
                // price_agorot is null for both "hidden" and "never set" — the
                // storefront cannot tell them apart, by design, and renders both
                // as the same-height agreed-price label so the grid never jumps.
                price={
                  <Price
                    agorot={item.price_agorot ?? 0}
                    visible={item.price_agorot !== null}
                    hiddenLabel={t("catalog.priceOnRequest")}
                  />
                }
              />
            ))}
          </DressGrid>

          {listError !== null && (
            <p role="alert" className="text-base text-ink-muted">
              {errorMessageOr(listError, t, "catalog.error")}
            </p>
          )}

          {hasMore && (
            <Button variant="secondary" onClick={loadMore} disabled={loadingMore}>
              {loadingMore ? t("catalog.loading") : t("catalog.more")}
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
