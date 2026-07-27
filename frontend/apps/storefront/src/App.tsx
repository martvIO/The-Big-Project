import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { A11yMenu, A11yStatementLink, SkipLink, ToastProvider, cn, focusRing } from "@boutique/ui";
import { getBoutiqueOnce } from "./api";
import { Link, MAIN_ID, Router, matchRoute, usePathname } from "./router";
import type { RouteMatch } from "./router";

const footerLinkClass = cn("rounded-sm text-sm text-gold-text underline", focusRing);

// The two routes that carry a fixed BookingCTA bar below 768. /about ships a
// static inline button instead (qa §7) and /accessibility ships none at all —
// claiming a bar on either lifts the A11yMenu 92px over content that reserved
// nothing for it (PRE-2).
function hasBookingBar(route: RouteMatch): boolean {
  return route.name === "catalog" || route.name === "dress";
}

export function App() {
  const { t } = useTranslation();
  const route = matchRoute(usePathname());
  const [phone, setPhone] = useState<string | null>(null);

  // The footer's tap-to-call is the only thing App itself needs from the API.
  // getBoutiqueOnce shares the request with whichever page also wants the block.
  useEffect(() => {
    let cancelled = false;
    getBoutiqueOnce()
      .then((boutique) => {
        if (!cancelled) setPhone(boutique.profile.phone);
      })
      .catch(() => {
        // The page body owns the error surface; a footer without a phone link is
        // a degraded footer, not a failure worth a second error message.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <ToastProvider>
      <SkipLink href={`#${MAIN_ID}`}>{t("skip.toContent")}</SkipLink>

      {/* The page shell owns the fixed CTA bar's footprint, and it has to,
          because <footer> is a SIBLING of <main>: a reservation on the page div
          inside <main> cannot clear the statutory הצהרת נגישות link that sits
          outside it (qa §7 / PRE-2). The reservation releases at 768, where the
          bar goes inline and a reserved gutter would just be dead space (§145). */}
      <div
        className={cn(
          // flex-col + flex-1 on <main> keeps the footer at the bottom of a
          // short page instead of a screenful below it — the הצהרת נגישות link
          // should not cost a scroll past dead space.
          "flex min-h-screen flex-col bg-bg text-ink",
          hasBookingBar(route) &&
            "max-md:[padding-block-end:calc(var(--cta-bar-height)+env(safe-area-inset-bottom))]",
        )}
      >
        {/* tabIndex -1 so the router can move focus here after a client
            navigation, and so the skip link has somewhere to land. */}
        <main id={MAIN_ID} tabIndex={-1} className="flex-1">
          <Router />
        </main>

        {/* Footer links only — the storefront ships no nav component. /about and
            /accessibility are reachable from here and nowhere else. */}
        <footer className="border-t border-border px-4 py-6">
          <div className="mx-auto flex max-w-[1200px] flex-wrap items-center gap-x-3 gap-y-2">
            <Link to="/about" className={footerLinkClass}>
              {t("about.heading")}
            </Link>
            <span aria-hidden="true" className="text-ink-muted">
              ·
            </span>
            <A11yStatementLink href="/accessibility">{t("a11y.statement")}</A11yStatementLink>
            {phone !== null && (
              <>
                <span aria-hidden="true" className="text-ink-muted">
                  ·
                </span>
                <a href={`tel:${phone}`} dir="ltr" className={footerLinkClass}>
                  {phone}
                </a>
              </>
            )}
          </div>
        </footer>
      </div>

      <A11yMenu
        triggerLabel={t("a11y.menu.trigger")}
        controls={{
          contrast: t("a11y.menu.contrast"),
          textSize: t("a11y.menu.textSize"),
          readableFont: t("a11y.menu.readableFont"),
          underlineLinks: t("a11y.menu.underlineLinks"),
          stopMotion: t("a11y.menu.stopMotion"),
        }}
        // The menu button must clear the bar where there IS one (PRE-1) and must
        // NOT be lifted where there is none (PRE-2) — /about's own reservation is
        // sized for the unshifted button.
        hasBookingBar={hasBookingBar(route)}
      />
    </ToastProvider>
  );
}
