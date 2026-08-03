import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Card, SectionHeading, Skeleton } from "@boutique/ui";
import { api } from "../api";
import type { CheckinQrResponse } from "../api";

// The SVG source arrives as JSON and is displayed through a `data:` URI in an
// <img> — an IMAGE context, so no scripts and no external references, which is
// strictly safer than an inline <svg> or dangerouslySetInnerHTML. The manage
// bundle therefore grows by nothing: no QR library ships to the browser.
const DATA_PREFIX = "data:image/svg+xml;utf8,";

export function CheckinQrSection() {
  const { t } = useTranslation();
  const [qr, setQr] = useState<CheckinQrResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getCheckinQr()
      .then((loaded) => {
        if (!cancelled) {
          setQr(loaded);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setLoadError(t("checkinQr.loadFailed"));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [t]);

  // No ref and no tabIndex={-1} on the heading, unlike StaffSection: nothing
  // here moves focus, and a programmatic focus target with no caller is dead
  // weight (DashboardSection states the same rule at its own heading).
  if (qr === null) {
    return loadError !== null ? (
      <p role="alert" className="text-sm text-ink-muted">
        {loadError}
      </p>
    ) : (
      <Skeleton variant="text" lines={4} />
    );
  }

  return (
    <div className="space-y-6">
      <SectionHeading as="h2">{t("checkinQr.heading")}</SectionHeading>

      <Card className="space-y-4">
        <p className="text-sm text-ink-muted">{t("checkinQr.intro")}</p>

        {/* `print-sheet` is the hook the @media print block in index.css keys
            off: on paper this subtree is the whole page and the console's
            header, nav and the explanatory line above are hidden. Everything a
            reader of the POSTER needs must live inside it. */}
        <div className="print-sheet space-y-4 border border-border p-6 text-center">
          <p className="font-display text-xl text-ink">{t("checkinQr.posterLine")}</p>
          <img
            src={DATA_PREFIX + encodeURIComponent(qr.qr_svg)}
            alt={t("checkinQr.imageAlt")}
            className="mx-auto block h-56 w-56"
          />
          <p className="text-sm text-ink-muted">
            {t("checkinQr.urlLabel")}{" "}
            {/* select-all so one click copies the whole address, and dir="ltr"
                because a Latin URL sitting in a Hebrew paragraph otherwise
                reorders around its own slashes and dots. */}
            <bdi dir="ltr" className="select-all">
              {qr.checkin_url}
            </bdi>
          </p>
          <p className="text-xs text-ink-muted">{t("checkinQr.urlHint")}</p>
        </div>

        <Button type="button" onClick={() => window.print()}>
          {t("checkinQr.printCta")}
        </Button>
      </Card>
    </div>
  );
}
