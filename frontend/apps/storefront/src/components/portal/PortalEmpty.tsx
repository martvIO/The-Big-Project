import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { ButtonLink, EmptyState } from "@boutique/ui";

/**
 * ONE screen for two states (design P2): the login's `PORTAL_NO_BOOKINGS`
 * refusal and a signed-in dashboard with no bookings at all.
 *
 * They are byte-identical on purpose. "This phone has no bookings here" is one
 * screen however she reached it — a distinct rendering for the refusal would be
 * an enumeration surface, and it would be a second screen to maintain for a
 * sentence that is already true.
 */
export function PortalEmpty() {
  const { t } = useTranslation();
  const titleRef = useRef<HTMLDivElement | null>(null);

  // The mover is the state change that mounted the target: this component only
  // ever appears as the RESULT of an action (a sign-in that found nothing, or a
  // list that loaded empty), so focus lands on it rather than staying on a
  // control that no longer exists.
  useEffect(() => {
    titleRef.current?.focus();
  }, []);

  return (
    <div ref={titleRef} tabIndex={-1} data-testid="portal-empty">
      <EmptyState
        title={t("portal.emptyTitle")}
        body={t("portal.emptyBody")}
        action={
          // Secondary, an invitation rather than a push.
          <ButtonLink href="/book/slot" variant="secondary" className="w-full sm:w-auto">
            {t("portal.emptyCta")}
          </ButtonLink>
        }
      />
    </div>
  );
}
