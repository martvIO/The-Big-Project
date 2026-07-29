import { useTranslation } from "react-i18next";
import { Button, SectionHeading, Skeleton, cn, focusRing, safeHref } from "@boutique/ui";
import { errorMessageOr } from "../api";
import type { BoutiqueResponse } from "../api";
import { BookingCTAButton } from "../components/BookingCTAButton";
import { ContactCard } from "../components/ContactCard";
import { HoursCard } from "../components/HoursCard";
import { useBoutique } from "../components/StorefrontLayout";

// The trust surface (Flow S3): "אמיתי? שווה ביקור? מתי פתוח?". One editorial
// column at every width — this page never goes multi-column.

const pageClass = "mx-auto flex max-w-[640px] flex-col px-4 pt-8 pb-8 md:px-6";

export interface AboutPageProps {
  // Injectable clock, same seam as HoursCard: pins the weekday so the
  // closed-today branch is testable without faking the machine's clock.
  now?: Date;
}

function AboutContent({ boutique, now }: { boutique: BoutiqueResponse; now: Date }) {
  const { t } = useTranslation();
  // Tenant-supplied, so a stored `javascript:` maps_url degrades to plain text
  // rather than executing — React does not neutralise a javascript: href.
  const maps = safeHref(boutique.maps_url ?? undefined);

  return (
    <>
      <SectionHeading as="h1">{boutique.name}</SectionHeading>

      {boutique.essence !== null && (
        <p className="mt-2 text-base text-ink-muted">{boutique.essence}</p>
      )}

      {/* ContactPanel has no address slot and BoutiqueHeader — which owns the
          linked-address treatment — is the catalog's h1, so /about renders the
          address itself, under the name where a first-time visitor looks. */}
      {boutique.address !== null && (
        <p className="mt-3">
          {maps === undefined ? (
            // No maps_url: plain text, never a dead link.
            <bdi className="text-base text-ink-muted">{boutique.address}</bdi>
          ) : (
            <a
              href={maps}
              target="_blank"
              rel="noopener noreferrer external"
              className={cn("text-base text-gold-text underline", focusRing)}
            >
              {/* bdi, not dir="ltr": the address is tenant-supplied and may be
                  Hebrew or Latin. Isolating it beats forcing a direction. */}
              <bdi>{boutique.address}</bdi> <span aria-hidden="true">↗</span>
            </a>
          )}
        </p>
      )}

      {boutique.description !== null && (
        <>
          <SectionHeading as="h2" className="mt-8">
            {t("about.story")}
          </SectionHeading>
          {/* text-base carries the design's 1.6 line-height from the theme —
              adding a leading- utility here would override the token. */}
          <p className="mt-2 text-base text-ink-muted">{boutique.description}</p>
        </>
      )}

      <HoursCard boutique={boutique} now={now} className="mt-6" />
      <ContactCard boutique={boutique} className="mt-6" />

      {/* Static and inline at every width — /about is the one storefront screen
          with no fixed BookingCTA bar (§7). Nothing moves at 768. */}
      <div className="mt-8">
        <BookingCTAButton inline />
      </div>
    </>
  );
}

export function AboutPage({ now = new Date() }: AboutPageProps) {
  const { t } = useTranslation();
  const { boutique, loading, error } = useBoutique();

  // Carried by the degraded states as well as the loaded one. The <h1> is where
  // the skip link lands, so a page whose only heading vanishes on an API error
  // drops a screen-reader user into an untitled region — and axe cannot catch
  // it, page-has-heading-one being best-practice rather than an A/AA rule.
  // Same fallback as the catalog header and the accessibility statement.
  const identity = (
    <SectionHeading as="h1" ornament>
      {boutique?.name ?? t("catalog.essenceFallback")}
    </SectionHeading>
  );

  if (loading) {
    return (
      <div className={pageClass}>
        {identity}
        <Skeleton variant="text" lines={3} className="mt-6" />
        <Skeleton variant="text" lines={6} className="mt-6" />
      </div>
    );
  }

  if (boutique === null) {
    return (
      <div className={pageClass}>
        {identity}
        {/* No contact card here on purpose: the phone, the WhatsApp number and
            the Instagram handle all come from the block that just failed, so
            there is nothing left to offer. Rendering the panel anyway would
            print empty rows — the catalog withholds its CTA for the same
            reason, and the statement page omits its reporting list. */}
        <p role="alert" className="mt-6 text-base text-ink-muted">
          {errorMessageOr(error, t, "about.error")}
        </p>
        <div className="mt-4">
          <Button
            variant="secondary"
            onClick={() => {
              window.location.reload();
            }}
          >
            {t("catalog.retry")}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className={pageClass}>
      <AboutContent boutique={boutique} now={now} />
    </div>
  );
}
