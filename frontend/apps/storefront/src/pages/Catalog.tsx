import { useEffect, useRef, useState } from "react";
import type { MouseEvent as ReactMouseEvent } from "react";
import { useTranslation } from "react-i18next";
import {
  BookingCTA,
  BoutiqueHeader,
  Button,
  ContactPanel,
  DressCard,
  DressGrid,
  EmptyState,
  Modal,
  Price,
  Skeleton,
} from "@boutique/ui";
import { api, getBoutiqueOnce } from "../api";
import type { PublicBoutiqueResponse, PublicDress } from "../api";
import { BoutiqueAbout } from "../components/BoutiqueAbout";
import { contactLabels, whatsappDigits } from "../lib/contact";
import { todayLine } from "../lib/hours-adapter";
import { navigate } from "../router";

const SKELETON_CARDS = 6;

// DressCard is itself the <a> — the whole card is the hit area — so there is no
// element left to hand a <Link>. Delegating from the grid upgrades every card to
// a client navigation while leaving the anchor, and cmd/middle-click with it,
// exactly as the browser found it: storefront links live in an Instagram bio and
// get opened in a new tab constantly.
function handleCardClick(event: ReactMouseEvent<HTMLDivElement>): void {
  if (
    event.defaultPrevented ||
    event.button !== 0 ||
    event.metaKey ||
    event.ctrlKey ||
    event.shiftKey ||
    event.altKey
  ) {
    return;
  }
  const anchor = event.target instanceof Element ? event.target.closest("a") : null;
  const href = anchor?.getAttribute("href");
  // Only same-origin paths; the header's maps link and the contact panel's
  // tel:/https: links must reach the browser untouched.
  if (href?.startsWith("/") !== true) return;
  event.preventDefault();
  navigate(href);
}

export interface CatalogProps {
  // Same injectable-clock seam as BoutiqueAbout: pins the weekday so the
  // closed-today branch is testable without faking the machine's clock.
  now?: Date;
}

export function Catalog({ now = new Date() }: CatalogProps) {
  const { t } = useTranslation();
  // Two independent surfaces, two pieces of state. The identity block and the
  // grid come from different endpoints, and a dress list that 503s (or 429s off
  // the anonymous read budget) must not take a boutique that answered down with
  // it — the visitor still gets the name, the hours, the address and a way to
  // book.
  const [dresses, setDresses] = useState<PublicDress[] | null>(null);
  const [boutique, setBoutique] = useState<PublicBoutiqueResponse | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [bookingOpen, setBookingOpen] = useState(false);
  // One refetch per page load. A signed URL that 404s because the object is
  // genuinely gone would otherwise re-sign, re-fail and loop forever.
  // ponytail: hard ceiling of one; if expiry-during-scroll turns out to be
  // common, replace with a re-sign keyed on url_expires_at rather than a counter.
  const photoRetried = useRef(false);

  useEffect(() => {
    let cancelled = false;
    // allSettled, never all: Promise.all rejects on the FIRST rejection and
    // discards a boutique response that already succeeded. getBoutiqueOnce
    // shares App.tsx's in-flight request rather than issuing a second GET.
    void Promise.allSettled([api.listDresses(), getBoutiqueOnce()]).then(([list, profile]) => {
      if (cancelled) return;
      if (list.status === "fulfilled") {
        setDresses(list.value.items);
        setFailed(false);
      } else {
        // The copy is fixed rather than the server's message: a fetch failure is
        // not the boutique's fault and the visitor cannot act on a status code.
        setFailed(true);
      }
      if (profile.status === "fulfilled") setBoutique(profile.value);
    });
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  const reload = () => {
    setFailed(false);
    setAttempt((n) => n + 1);
  };

  const handlePhotoError = () => {
    if (photoRetried.current) return;
    photoRetried.current = true;
    reload();
  };

  const profile = boutique?.profile;
  const hoursText = boutique === null ? undefined : todayLine(boutique, now, t);

  return (
    // The fixed CTA bar's footprint is reserved by App's page shell, which wraps
    // <main> AND <footer> — a reservation inside <main> cannot clear content
    // that sits outside it (qa §7: הצהרת נגישות stays tappable).
    <div className="mx-auto flex max-w-[1200px] flex-col gap-8 px-4 pt-8 pb-8 md:gap-12 md:px-6 xl:px-12">
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between md:gap-6">
        {/* No `essence`: the design's "משפט מהות אחד" has no column behind it —
            the public profile is exactly {phone, address, description, maps_url}.
            Adding one is an F7 schema change, out of scope here. Until the
            boutique's own name arrives, brand.title stands in for it. */}
        <BoutiqueHeader
          name={boutique?.name ?? t("brand.title")}
          hoursText={hoursText}
          address={profile?.address ?? undefined}
          mapsUrl={profile?.maps_url}
        />

        {/* Gated on the boutique, not on the dresses: booking is a phone call,
            and it stays offerable when only the collection failed to load.
            One instance for both breakpoints — BookingCTA is `fixed` below 768
            and `md:static`, so it lands in the header row on desktop by itself. */}
        {boutique !== null && (
          <BookingCTA>
            <Button size="lg" className="w-full md:w-auto" onClick={() => setBookingOpen(true)}>
              {t("booking.cta")}
            </Button>
          </BookingCTA>
        )}
      </div>

      <div aria-hidden="true" className="h-px bg-gold" />

      {failed ? (
        // Ink, not danger: a backend that is down is not the boutique's fault,
        // and the header above still carries the identity.
        <div role="alert" className="flex flex-col items-start gap-3">
          <p className="text-base text-ink">{t("catalog.error")}</p>
          <Button variant="secondary" onClick={reload}>
            {t("common.retry")}
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
        // the boutique still has to feel complete, so the whole about block comes
        // along rather than a bare "nothing here yet".
        <div>
          <EmptyState title={t("catalog.empty.title")} body={t("catalog.empty.body")} />
          {boutique !== null && <BoutiqueAbout boutique={boutique} now={now} />}
        </div>
      ) : (
        <div onClick={handleCardClick}>
          <DressGrid>
            {dresses.map((item) => (
              <DressCard
                key={item.id}
                name={item.name}
                href={`/dress/${encodeURIComponent(item.id)}`}
                photoUrl={item.cover?.url}
                reserved={item.reserved}
                reservedLabel={t("dress.reserved")}
                onPhotoError={handlePhotoError}
                // price_agorot is null for both "hidden" and "never set" — the
                // storefront cannot tell them apart, by design, and renders both
                // as the same-height agreed-price label so the grid never jumps.
                price={
                  <Price
                    agorot={item.price_agorot ?? 0}
                    visible={item.price_agorot !== null}
                    hiddenLabel={t("price.hidden")}
                  />
                }
              />
            ))}
          </DressGrid>
          {/* ponytail: first page only — the server pins limit to 24 and the
              design ships no pagination control. Add one when a pilot boutique
              passes 24 dresses; the seam is api.listDresses(offset). */}
        </div>
      )}

      {/* v1 booking seam: the CTA opens the contact panel until E3 replaces it
          with the real booking flow behind the same button. */}
      <Modal
        open={bookingOpen}
        onClose={() => setBookingOpen(false)}
        title={t("booking.panelTitle")}
        footer={
          <Button variant="secondary" onClick={() => setBookingOpen(false)}>
            {t("booking.close")}
          </Button>
        }
      >
        <ContactPanel
          phone={profile?.phone ?? undefined}
          whatsapp={whatsappDigits(profile?.phone)}
          labels={contactLabels(t)}
        />
      </Modal>
    </div>
  );
}
