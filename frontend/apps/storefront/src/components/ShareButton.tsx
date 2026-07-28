import { useTranslation } from "react-i18next";
import { Button, useToast } from "@boutique/ui";
import { FALLBACK_ERROR_MESSAGE } from "../api";

/**
 * Native share sheet where the platform has one, clipboard copy where it does
 * not, and a spoken confirmation either way.
 *
 * The confirmation goes through the toast, which renders role="status" — a
 * silent clipboard write looks broken to a screen-reader user, who gets no
 * visual cue that anything happened.
 */
export function ShareButton({ title }: { title: string }) {
  const { t } = useTranslation();
  const toast = useToast();

  const handleShare = () => {
    const url = window.location.href;
    if (typeof navigator.share === "function") {
      void navigator.share({ title, url }).catch(() => {
        // The user dismissed the sheet, or the browser refused. Either way the
        // link is untouched — nothing to report.
      });
      return;
    }
    // No share sheet and no clipboard means an insecure origin. Say so rather
    // than leaving the button inert with no explanation.
    const copied = navigator.clipboard?.writeText(url);
    if (copied === undefined) {
      toast({ message: FALLBACK_ERROR_MESSAGE, variant: "error" });
      return;
    }
    void copied
      .then(() => {
        toast({ message: t("dress.shareCopied") });
      })
      .catch(() => {
        toast({ message: FALLBACK_ERROR_MESSAGE, variant: "error" });
      });
  };

  return (
    <Button variant="ghost" size="sm" onClick={handleShare}>
      {t("dress.share")}
    </Button>
  );
}
