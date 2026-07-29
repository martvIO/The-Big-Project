import { useTranslation } from "react-i18next";
import { BookingCTA, ButtonLink } from "@boutique/ui";

/**
 * The entry into /book/* (D1).
 *
 * An anchor, not a button: router.tsx's root delegation turns any same-origin
 * <a> into a client navigation while shouldIntercept lets modifier-, middle-
 * and target-clicks fall through to the browser — so open-in-new-tab and "copy
 * link address" keep working, which onClick + navigate() destroys on a page
 * brides reach from an Instagram deep link.
 *
 * The href MUST be absolute. The delegated handler pushes the anchor's raw
 * getAttribute("href"), not the resolved .href, so a relative value would be
 * pushed verbatim.
 *
 * It takes NO boutique data (D12): a control that only navigates has nothing to
 * degrade, so it renders on a page whose boutique fetch failed.
 *
 * `inline` renders it as a plain full-width link with no fixed bar. One screen
 * needs that: /about, where qa §7 requires no bottom bar at ANY width.
 * BookingCTA cannot be talked out of its bar by a className — its base is
 * `fixed inset-x-0 bottom-0` with only `md:static`, and `cn` is a naive joiner
 * with no tailwind-merge, so which rule wins is decided by stylesheet order
 * rather than by the caller.
 */
export interface BookingCTAButtonProps {
  /**
   * Binds the flow to a dress. A path SEGMENT, not a query string (D9): the
   * navigation store snapshots `pathname` only and would never see a query.
   * Encoded exactly as api.getDress encodes it, which router.tsx's decodeId is
   * the matching decoder for.
   */
  dressId?: string;
  inline?: boolean;
}

export function BookingCTAButton({ dressId, inline = false }: BookingCTAButtonProps) {
  const { t } = useTranslation();
  const href =
    dressId === undefined ? "/book/slot" : `/book/slot/${encodeURIComponent(dressId)}`;

  const cta = (
    <ButtonLink href={href} className={inline ? "w-full" : undefined}>
      {t("booking.cta")}
    </ButtonLink>
  );

  return inline ? cta : <BookingCTA>{cta}</BookingCTA>;
}
