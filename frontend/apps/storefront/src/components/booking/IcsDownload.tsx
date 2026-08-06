import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, ButtonLink } from "@boutique/ui";
import { manageIcsBlobUrl, portalIcsUrl } from "../../api";

// F24 D5's download control — ONE rendering, two transports (design §4).
//
// The portal is a PLAIN LINK: on iOS a direct `text/calendar` response opens the
// add-to-calendar sheet, while a fetch-and-blob download lands a file she then
// has to find. Safe in a URL because the booking id is not the capability
// there — the cookie is.
//
// The tokenized page cannot be a link at all: the manage token is the credential
// and tokens never ride URLs (F14 D7), so it POSTs and turns the answer into a
// blob download.
//
// `md` without exception on both, never `sm`: `sm` is min-h-9 = 36px, under the
// house 44px touch floor (F-W1's resolution).

type IcsSource = { transport: "portal"; bookingId: string } | { transport: "token"; token: string };

export function IcsDownload({ source }: { source: IcsSource }) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const revoke = useRef<(() => void) | null>(null);

  // A blob URL pins the whole document's memory until it is revoked, and the
  // click that consumed it cannot know when the browser is finished — so the
  // unmount is the honest place.
  useEffect(
    () => () => {
      revoke.current?.();
    },
    [],
  );

  const download = async () => {
    if (busy) return;
    setBusy(true);
    try {
      if (source.transport !== "token") return;
      const blob = await manageIcsBlobUrl(source.token);
      revoke.current?.();
      revoke.current = blob.revoke;
      const link = document.createElement("a");
      link.href = blob.url;
      link.download = "appointment.ics";
      link.click();
    } catch {
      // Deliberately silent-but-inert: the control stays operable and a retry
      // is one tap. There is no state to corrupt and nothing to recover — the
      // appointment is unchanged either way, and a failure banner over a
      // calendar convenience would out-shout the page's real content.
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex">
        {source.transport === "portal" ? (
          <ButtonLink
            href={portalIcsUrl(source.bookingId)}
            download="appointment.ics"
            variant="secondary"
            size="md"
            className="w-full sm:w-auto"
          >
            {t("portal.icsDownload")}
          </ButtonLink>
        ) : (
          <Button
            type="button"
            variant="secondary"
            size="md"
            fullWidthMobile
            loading={busy}
            onClick={() => void download()}
          >
            {t("portal.icsDownload")}
          </Button>
        )}
      </div>
      <p className="text-sm text-ink-muted">{t("portal.icsHint")}</p>
    </div>
  );
}
