import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Button,
  Card,
  ContactPanel,
  Modal,
  SectionHeading,
  Skeleton,
  cn,
  focusRing,
  safeHref,
} from "@boutique/ui";
import { getBoutiqueOnce } from "../api";
import type { PublicBoutiqueResponse } from "../api";
import { BoutiqueAbout } from "../components/BoutiqueAbout";
import { contactLabels, whatsappDigits } from "../lib/contact";

// The trust surface (Flow S3): "אמיתי? שווה ביקור? מתי פתוח?". One editorial
// column at every width — this page never goes multi-column. The hours and
// contact block itself is BoutiqueAbout, shared with the catalog's empty state;
// this page is the wrapper that gives it an identity, an address and a CTA.

function AboutContent({ boutique }: { boutique: PublicBoutiqueResponse }) {
  const { t } = useTranslation();
  const [bookingOpen, setBookingOpen] = useState(false);
  const { profile } = boutique;
  // Tenant-supplied, so a stored `javascript:` maps_url degrades to plain text
  // rather than executing — React does not neutralise a javascript: href.
  const maps = safeHref(profile.maps_url);

  return (
    <>
      {/* ContactPanel has no address slot and BoutiqueHeader — which owns the
          linked-address treatment — is the catalog's h1, so /about renders the
          address itself, under the name where a first-time visitor looks. */}
      {profile.address !== null && (
        <p className="mt-3">
          {maps === undefined ? (
            // No maps_url: plain text, never a dead link.
            <bdi className="text-base text-ink-muted">{profile.address}</bdi>
          ) : (
            <a href={maps} className={cn("text-base text-gold-text underline", focusRing)}>
              {/* bdi, not dir="ltr": the address is tenant-supplied and may be
                  Hebrew or Latin. Isolating it beats forcing a direction. */}
              <bdi>{profile.address}</bdi> <span aria-hidden="true">↗</span>
            </a>
          )}
        </p>
      )}

      <BoutiqueAbout boutique={boutique} className="mt-6" />

      {/* Static and inline at every width — /about is the one storefront screen
          with no fixed BookingCTA bar (qa §7). Nothing moves at 768. */}
      <Button fullWidthMobile className="mt-8" onClick={() => setBookingOpen(true)}>
        {t("booking.cta")}
      </Button>

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
        {/* Booking is a conversation in v1: call or WhatsApp. Waze and Maps stay
            in the contact card — they answer "how do I get there", not "how do
            I book". */}
        <ContactPanel
          phone={profile.phone ?? undefined}
          whatsapp={whatsappDigits(profile.phone)}
          labels={contactLabels(t)}
        />
      </Modal>
    </>
  );
}

export function About() {
  const { t } = useTranslation();
  const [boutique, setBoutique] = useState<PublicBoutiqueResponse | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setFailed(false);
    getBoutiqueOnce()
      .then((data) => {
        if (!cancelled) setBoutique(data);
      })
      .catch(() => {
        // The message is ours, not the backend's — the public surface speaks one
        // Hebrew voice, and a 503 body is not copy anyone should read.
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  let body;
  if (failed) {
    body = (
      <div className="mt-6 flex flex-col items-start gap-3">
        {/* ink, not danger: a failed load is not the visitor's mistake. */}
        <p role="alert" className="text-base text-ink">
          {t("about.error")}
        </p>
        <Button variant="secondary" onClick={() => setAttempt((n) => n + 1)}>
          {t("common.retry")}
        </Button>
      </div>
    );
  } else if (boutique === null) {
    body = (
      <div className="mt-6 flex flex-col gap-6">
        <Card>
          <Skeleton variant="text" lines={4} />
        </Card>
        <Card>
          <Skeleton variant="text" lines={3} />
        </Card>
      </div>
    );
  } else {
    body = <AboutContent boutique={boutique} />;
  }

  return (
    // padding-block-end clears the fixed A11yMenu button so it never rests on
    // the Waze link. /about ships no BookingCTA bar (see App.tsx's hasBookingBar),
    // so the button sits at its unshifted inset and the arithmetic is:
    //   --space-4 (16px inset) + 44px touch target = 60px footprint
    //   --space-16 + --space-4 = 80px reserved, i.e. 20px of clearance.
    // Deliberately NOT --space-a11y-clearance (92px + 44px = 136px): that token
    // reserves the booking bar's footprint, and this page ships no bar.
    <div className="mx-auto max-w-[640px] px-4 pt-8 md:px-6 xl:px-12 [padding-block-end:calc(var(--space-16)+var(--space-4))]">
      {/* The name arrives with the rest of the block, so the heading falls back
          to the brand title — the identity paints before the data lands. */}
      <SectionHeading as="h1" ornament>
        {boutique?.name ?? t("brand.title")}
      </SectionHeading>
      {body}
    </div>
  );
}
