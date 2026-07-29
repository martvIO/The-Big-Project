import { useTranslation } from "react-i18next";
import { cn } from "@boutique/ui";
import type { BookStep } from "../router";

// The /book flow's shell. The steps themselves are not built yet — this renders
// the frame every step shares and nothing else.
//
// The h1 is the STEP, not the boutique: a step label is a static i18n string,
// so it survives the boutique fetch failing, the terms 404 and every empty list
// by construction, with no fallback path to get wrong.
//
// pb-16 (64px) clears the fixed A11yMenu button's 60px footprint, which /book
// carries with no CTA bar beneath it to reserve the space — hasBookingBar() is
// deliberately false here.
const pageClass = "mx-auto flex max-w-[640px] flex-col gap-6 px-4 pt-8 pb-16 md:px-6";

// The stepper's four items in flow order. `confirm` is terminal and outside the
// stepper, which is why there is no fifth label.
const STEP_LABEL_KEYS = {
  slot: "booking.stepSlot",
  details: "booking.stepDetails",
  terms: "booking.stepTerms",
  verify: "booking.stepOtp",
} as const;

const STEPPER_STEPS = ["slot", "details", "terms", "verify"] as const;

const dotClass = "flex size-6 items-center justify-center rounded-full text-xs";

// Inert by design: no item is a link and none is focusable. Completed, current
// and upcoming are told apart by the ✓ glyph, by aria-current plus weight, and
// by the outline dot — three signals, none of them colour alone.
function Stepper({ step }: { step: BookStep }) {
  const { t } = useTranslation();
  const currentIndex = STEPPER_STEPS.findIndex((name) => name === step);

  return (
    <ol aria-label={t("booking.stepsLabel")} className="flex items-start gap-2">
      {STEPPER_STEPS.map((name, index) => {
        const current = index === currentIndex;
        const done = index < currentIndex;
        return (
          <li key={name} className="flex min-w-0 flex-1 flex-col items-center gap-1 text-center">
            <span
              aria-hidden="true"
              className={cn(
                dotClass,
                done && "bg-gold text-ink",
                current && "bg-ink text-bg",
                !done && !current && "border border-border-input bg-surface-raised text-ink-muted",
              )}
            >
              {done ? "✓" : <bdi dir="ltr">{index + 1}</bdi>}
            </span>
            <span
              aria-current={current ? "step" : undefined}
              className={cn("text-xs", current ? "font-semibold text-ink" : "text-ink-muted")}
            >
              {t(STEP_LABEL_KEYS[name])}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

export function BookPage({ step }: { step: BookStep }) {
  const { t } = useTranslation();

  return (
    <div className={pageClass}>
      {step !== "confirm" && <Stepper step={step} />}
      <div className="flex flex-col gap-2">
        <h1 className="font-display text-2xl text-ink">
          {step === "confirm" ? t("booking.confirmTitle") : t(STEP_LABEL_KEYS[step])}
        </h1>
        <span aria-hidden="true" className="h-px w-12 bg-gold" />
      </div>
    </div>
  );
}
