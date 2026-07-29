import { useId } from "react";
import type { Ref } from "react";
import { useTranslation } from "react-i18next";
import { cn } from "@boutique/ui";
import type { SizeChip } from "../../api";

export interface SizeChipsProps {
  sizes: SizeChip[];
  value: string | null;
  onChange: (size: string) => void;
  // A real validation failure — booking.sizeRequired. Danger register.
  error?: string;
  /**
   * A recoverable "this went away, pick another" message — booking.sizeGoneRepick.
   * Warning register, because nothing she did failed: the boutique's stock moved.
   * (§3.8's table files it under danger; §4.7 and §5.8's measured contrast ledger
   * both say --color-warning-text, and the ledger wins.) `error` takes precedence
   * when both are set: by then she has pressed forward and the notice is stale.
   */
  notice?: string;
  ref?: Ref<HTMLInputElement>;
}

const chipClass = cn(
  "flex min-h-11 min-w-11 cursor-pointer flex-col items-center justify-center gap-0.5 rounded-full bg-surface-raised py-1 text-sm text-ink",
  "focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-focus",
);

// Each branch carries its border AND its padding-inline exactly once: cn has no
// tailwind-merge, so a shared px-3 plus a conditional px-[11px] would ship both
// and let stylesheet order decide. The 1px→2px growth is absorbed by the pair.
const restingClass = "border border-border-input px-3";
const selectedClass = "border-2 border-gold-strong px-[11px] font-semibold";

// Native radios in a fieldset, the input sr-only and the <label> carrying the
// chip. D4 keeps an unavailable size selectable — this is a fitting, not a
// purchase — so it gets no stock styling at all: same border, same fill, same
// weight. The signal is a word, and the word lives INSIDE that chip's label,
// where it joins the radio's accessible name by construction. A group-level
// sentence would leave the chips reading 36 / 38 / 40 with nothing marking
// which one it was about, and axe would see the text and pass.
export function SizeChips({ sizes, value, onChange, error, notice, ref }: SizeChipsProps) {
  const { t } = useTranslation();
  const groupId = useId();
  const errorId = `${groupId}-error`;
  const anyUnavailable = sizes.some((size) => !size.available);
  const message = error ?? notice;

  return (
    <fieldset
      className="border-0 p-0"
      aria-describedby={message === undefined ? undefined : errorId}
    >
      <legend className="mb-2 text-sm font-semibold text-ink">{t("dress.sizes")}</legend>
      <div className="flex flex-wrap gap-2">
        {sizes.map((size, index) => {
          const selected = size.size_label === value;
          return (
            <label
              key={size.size_label}
              className={cn(chipClass, selected ? selectedClass : restingClass)}
            >
              <input
                type="radio"
                // WCAG 3.3.2 without a new key: required on each radio makes the
                // group required to AT, and the storefront uses no * convention.
                required
                name={`${groupId}-size`}
                value={size.size_label}
                checked={selected}
                onChange={() => {
                  onChange(size.size_label);
                }}
                ref={index === 0 ? ref : undefined}
                className="sr-only"
              />
              <bdi dir="ltr">{size.size_label}</bdi>
              {!size.available && (
                <span className="text-xs text-ink-muted">{t("booking.sizeUnavailable")}</span>
              )}
            </label>
          );
        })}
      </div>
      {message !== undefined && (
        <p
          id={errorId}
          role="alert"
          className={cn("mt-2 text-sm", error === undefined ? "text-warning-text" : "text-danger")}
        >
          {message}
        </p>
      )}
      {/* The invitation the chip phrase has no room for. Muted and stated once,
          under the group — never a promo register, and never a warning. */}
      {anyUnavailable && (
        <p className="mt-2 text-sm text-ink-muted">{t("booking.sizeUnavailableNote")}</p>
      )}
    </fieldset>
  );
}
