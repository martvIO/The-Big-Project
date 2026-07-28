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

  const copyLink = (url: string) => {
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

  const handleShare = () => {
    const url = window.location.href;
    if (typeof navigator.share === "function") {
      void navigator.share({ title, url }).catch((error: unknown) => {
        // AbortError is the visitor closing the sheet — a deliberate no-op.
        // Every other rejection means the share never happened (Chromium on
        // desktop rejects with NotAllowedError when it does not count the
        // click as transient activation), so fall through to the clipboard
        // rather than leaving the visitor with silence and no link.
        if (error instanceof Error && error.name === "AbortError") return;
        copyLink(url);
      });
      return;
    }
    copyLink(url);
  };

  return (
    <Button variant="ghost" size="sm" onClick={handleShare}>
      {t("dress.share")}
    </Button>
  );
}
