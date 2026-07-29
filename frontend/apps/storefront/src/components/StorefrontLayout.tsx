// oxlint-disable react/only-export-components -- the provider, its hook and the
// shell are one unit; the hook cannot live elsewhere without exporting the
// context object itself, which is a wider surface than the hook.
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { A11yMenu, A11yStatementLink, SkipLink, cn, focusRing } from "@boutique/ui";
import { getBoutiqueOnce, resetBoutiqueCache } from "../api";
import type { BoutiqueResponse } from "../api";
import { Link, MAIN_ID, matchRoute, usePathname } from "../router";
import type { RouteMatch } from "../router";

// min-w-0 + overflow-wrap:anywhere is WCAG 1.4.10 (reflow), not cosmetics: an
// Instagram handle and a phone number are single unbreakable Latin tokens, and
// at 200% text-only zoom on a 375px viewport "@some.long.handle" is wider than
// the flex line. Without these the footer pushes the whole document sideways.
// `anywhere` rather than `break-word` because only `anywhere` breaks a token
// that has no break opportunity at all.
const footerLinkClass = cn(
  "min-w-0 rounded-sm text-sm text-gold-text underline [overflow-wrap:anywhere]",
  focusRing,
);

export interface BoutiqueState {
  boutique: BoutiqueResponse | null;
  /** True until the single layout-level fetch settles, either way. */
  loading: boolean;
  /** Set when the boutique block could not be loaded at all. */
  error: unknown;
  /**
   * Re-drive the layout-level fetch.
   *
   * Load-bearing: the fetch runs once on mount, so without this a route that
   * renders a retry button for a FAILED boutique has no way to change the state
   * it is retrying — the button would be permanently inert.
   */
  retry: () => void;
}

const BoutiqueContext = createContext<BoutiqueState>({
  boutique: null,
  loading: true,
  error: null,
  retry: () => undefined,
});

/**
 * The boutique block, fetched ONCE for the whole app.
 *
 * Every route needs it — the footer's phone and Instagram, the booking CTA's
 * ContactPanel, the catalog header, /about's whole body and /accessibility's
 * complaints contact. A per-route fetch would leave /dress/{id}'s footer and
 * its contact panel empty, so the layout owns the call and the routes read it.
 */
export function useBoutique(): BoutiqueState {
  return useContext(BoutiqueContext);
}

// The two routes that carry a fixed BookingCTA bar below 768. /about ships a
// static inline button instead (qa §7) and /accessibility ships none at all —
// claiming a bar on either lifts the A11yMenu 92px over content that reserved
// nothing for it (PRE-2).
function hasBookingBar(route: RouteMatch): boolean {
  return route.name === "catalog" || route.name === "dress";
}

export function StorefrontLayout({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const route = matchRoute(usePathname());
  const [attempt, setAttempt] = useState(0);
  const [fetched, setFetched] = useState<{
    boutique: BoutiqueResponse | null;
    loading: boolean;
    error: unknown;
  }>({ boutique: null, loading: true, error: null });

  const retry = useCallback(() => {
    // getBoutiqueOnce already drops its own rejected promise, but clearing the
    // cache keeps this correct if a future caller memoises a resolved one too.
    resetBoutiqueCache();
    setFetched({ boutique: null, loading: true, error: null });
    setAttempt((n) => n + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;
    getBoutiqueOnce()
      .then((boutique) => {
        if (!cancelled) setFetched({ boutique, loading: false, error: null });
      })
      .catch((error: unknown) => {
        // Recorded, not swallowed. A route can only degrade honestly when
        // identity fails if the failure is observable — a dropped rejection
        // makes "failed" and "still loading" visually identical, forever.
        if (!cancelled) setFetched({ boutique: null, loading: false, error });
      });
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  const state: BoutiqueState = { ...fetched, retry };

  const phone = state.boutique?.phone ?? null;
  const instagram = state.boutique?.instagram ?? null;

  return (
    <BoutiqueContext.Provider value={state}>
      <SkipLink href={`#${MAIN_ID}`}>{t("a11y.skipLink")}</SkipLink>

      {/* The page shell owns the fixed CTA bar's footprint, and it has to,
          because <footer> is a SIBLING of <main>: a reservation on the page div
          inside <main> cannot clear the statutory הצהרת נגישות link that sits
          outside it (qa §7 / PRE-2). The reservation releases at 768, where the
          bar goes inline and a reserved gutter would just be dead space. */}
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
          {children}
        </main>

        {/* Footer links only — the storefront ships no nav component. /about and
            /accessibility are reachable from here and nowhere else.

            padding-block-end is the A11yMenu trigger's footprint, not py-6's 24
            (PRE-2). The trigger is `fixed` at the viewport's block-end
            inline-end corner on EVERY route and at every width, and the footer
            is the last thing in the document — so scrolled to the end it
            painted over the footer's inline-end content, הצהרת נגישות included.
            The reservation belongs HERE and not on a page div: <footer> is a
            sibling of <main>, outside every padded page shell. The shell's own
            --cta-bar-height reservation covers the routes where the trigger is
            lifted to --space-a11y-clearance instead (92 + 44 − 80 = 56 < 68).
            Written as pt-6 + a logical property because cn has no
            tailwind-merge: py-6 and a block-end override would both ship. */}
        <footer className="border-t border-border px-4 pt-6 [padding-block-end:var(--space-a11y-footprint)]">
          <div className="mx-auto flex max-w-[1200px] flex-wrap items-center gap-x-3 gap-y-2">
            <Link to="/about" className={footerLinkClass}>
              {t("footer.about")}
            </Link>
            <span aria-hidden="true" className="text-ink-muted">
              ·
            </span>
            <A11yStatementLink href="/accessibility">{t("a11y.statementLink")}</A11yStatementLink>
            {instagram !== null && (
              <>
                <span aria-hidden="true" className="text-ink-muted">
                  ·
                </span>
                {/* bdi + dir=ltr: a Latin handle inside an RTL line otherwise
                    reorders around neighbouring punctuation. */}
                <a
                  href={`https://instagram.com/${instagram}`}
                  target="_blank"
                  rel="noopener noreferrer external"
                  className={footerLinkClass}
                >
                  <bdi dir="ltr">@{instagram}</bdi>
                </a>
              </>
            )}
            {phone !== null && (
              <>
                <span aria-hidden="true" className="text-ink-muted">
                  ·
                </span>
                <a href={`tel:${phone}`} className={footerLinkClass}>
                  <bdi dir="ltr">{phone}</bdi>
                </a>
              </>
            )}
          </div>
        </footer>
      </div>

      <A11yMenu
        triggerLabel={t("a11y.menuTrigger")}
        controls={{
          contrast: t("a11y.contrast"),
          textSize: t("a11y.textSize"),
          readableFont: t("a11y.readableFont"),
          underlineLinks: t("a11y.underlineLinks"),
          stopMotion: t("a11y.stopMotion"),
        }}
        // The menu button must clear the bar where there IS one (PRE-1) and must
        // NOT be lifted where there is none (PRE-2) — /about's own reservation is
        // sized for the unshifted button.
        hasBookingBar={hasBookingBar(route)}
      />
    </BoutiqueContext.Provider>
  );
}
