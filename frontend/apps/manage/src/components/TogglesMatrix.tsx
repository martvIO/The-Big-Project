import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Card, SectionHeading, Toggle, VisuallyHidden, useToast } from "@boutique/ui";
import { api, errorMessage } from "../api";
import type { ToggleKey } from "../lib/toggles";
import { TOGGLE_AREAS, TOGGLES } from "../lib/toggles";

interface TogglesMatrixProps {
  // The parent's `getSettings()` answer. Default-complete per D3 — every
  // registry key with a concrete bool — so there is no `?? false` anywhere here.
  // Passed down rather than fetched: one GET for the whole profile section.
  toggles: Record<string, boolean>;
}

interface Cue {
  // ⚠ A NONCE, and it is what makes a REPEATED cue audible. React skips the
  // text write when a node re-renders to the same string, so a second «נשמר
  // לפני רגע» would mutate NOTHING inside role="status" and announce nothing.
  // FloorPanel's trick: key the inner span on this, so every write replaces the
  // node and the region always sees a childList mutation.
  nonce: number;
  key: ToggleKey;
}

export function TogglesMatrix({ toggles }: TogglesMatrixProps) {
  const { t } = useTranslation();
  const toast = useToast();
  const [values, setValues] = useState<Record<string, boolean>>(toggles);
  // ⚠ PER ROW, NOT ONE FLAG FOR THE CARD (design §4 state F). A card-wide lock
  // would be simpler and wrong: it freezes a row the owner has not touched, for
  // a request that has nothing to do with it. Two rows saving at once is safe
  // precisely because D2 made single-key writes deep-merge in SQL — the db
  // concurrency test is that claim.
  const [pending, setPending] = useState<readonly ToggleKey[]>([]);
  const [cue, setCue] = useState<Cue | null>(null);

  const flip = async (key: ToggleKey, next: boolean) => {
    // ⚠ THE IN-FLIGHT LOCK IS THIS GUARD, NOT THE `disabled` ATTRIBUTE (design
    // P1). Disabling a just-flipped — therefore focused — native checkbox drops
    // focus to <body>, an SC 2.4.3 regression the spec's word "disabled" did not
    // intend. Same observable lock, no focus loss.
    if (pending.includes(key)) {
      return;
    }
    const previous = values[key] ?? false;
    setPending((current) => [...current, key]);
    setCue(null);
    try {
      const updated = await api.updateSettings({ toggles: { [key]: next } });
      // Re-sync from the RESPONSE — server truth, never the optimistic value
      // (FloorPanel's no-optimistic-patch discipline). Safe as a single-key PUT
      // only because D2 gave the toggles key a real deep merge in SQL, so the
      // answer to a one-key write carries every OTHER row's current truth too.
      setValues(updated.toggles);
      setCue({ nonce: Date.now(), key });
    } catch (error) {
      // Revert to the pre-flip state and let the house toast carry the message.
      // No inline row error: two error surfaces for one failure is design §8's
      // named non-feature.
      setValues((current) => ({ ...current, [key]: previous }));
      toast({ message: errorMessage(error), variant: "error" });
    } finally {
      setPending((current) => current.filter((busy) => busy !== key));
    }
  };

  return (
    <Card>
      <div className="flex flex-col gap-4">
        <SectionHeading as="h2">{t("togglesMatrix.heading")}</SectionHeading>
        {/* The one line that tells the owner this card and the profile form
            above it save differently. */}
        <p className="text-sm text-ink-muted">{t("togglesMatrix.hint")}</p>

        {TOGGLE_AREAS.map((area) => (
          <section key={area} className="flex flex-col gap-2">
            <h3 className="text-sm font-medium text-ink">{t(`togglesMatrix.area.${area}`)}</h3>
            {TOGGLES.filter((toggle) => toggle.area === area).map(({ key }) => (
              <div
                key={key}
                // `min-h-11` on the ROW, and it is the 44px floor (F-W1 / F-T2):
                // the Toggle's checkbox box is 20px and is NOT the hit target —
                // the wrapping <label> is, so the class has to reach it.
                className="flex items-center gap-3"
                data-busy={pending.includes(key) ? "true" : undefined}
              >
                <Toggle
                  className={`min-h-11 flex-1 py-1 ${pending.includes(key) ? "opacity-60" : ""}`}
                  label={t(`togglesMatrix.${key}.label`)}
                  description={t(`togglesMatrix.${key}.hint`)}
                  checked={values[key] ?? false}
                  onCheckedChange={(next) => void flip(key, next)}
                />
                {cue?.key === key && (
                  <span className="ms-auto shrink-0 text-xs text-ink-muted">
                    {t("common.saved")}
                  </span>
                )}
              </div>
            ))}
          </section>
        ))}

        {/* ONE status region per CARD, never one per row (FloorPanel's one-cue
            precedent). ⚠ THE <span role="status"> IS NEVER REMOUNTED — only the
            keyed node inside it is. A live region ADDED to the document is not
            announced; a childList mutation inside one that was already there
            is. */}
        <VisuallyHidden>
          <span role="status">
            {cue !== null && <span key={cue.nonce}>{t("common.saved")}</span>}
          </span>
        </VisuallyHidden>
      </div>
    </Card>
  );
}
