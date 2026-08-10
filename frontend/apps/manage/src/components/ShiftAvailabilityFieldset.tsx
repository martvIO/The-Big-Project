import { useId } from "react";
import { Trans, useTranslation } from "react-i18next";
import { cn } from "@boutique/ui";
import type { AvailabilityState } from "../api";

// One shift, four options: the three stored states plus «לא נרשם» (D13 / design
// P9).
//
// ⚠ A NATIVE RADIO CANNOT BE UN-CHECKED, so three options would make D8's clear
// path unreachable from every surface in this feature. A staffer thumbs
// «מעדיפה» on the wrong row on a phone: with three options she can overwrite it
// but never withdraw it, so an answer she never meant to give ships to F40 as
// advisory input, «נענו» only ever climbs, and a shift manager's mis-recorded
// row carries `recorded_by` forever. The fourth option is the whole fix and
// NOTHING ON THE WIRE CHANGES — it is the rendered NAME of "no entry", and
// selecting it omits the template from the PUT, which is D8's own clear path.
//
// It is DEFAULT-CHECKED, and that is not the same as pre-checking an answer.
// Pre-checking «זמינה» would let a save assert something she never said, which
// is the dishonesty `recorded_by` exists to prevent one decision earlier;
// pre-checking «לא נרשם» asserts precisely the truth. It also fixes a second
// thing for free: an all-unchecked native radio group has no home for the
// initial arrow key.
//
// This is `SlotPicker.tsx`'s shipped contract reduced to four options — the same
// `sr-only` input, the same chip label, the same `focus-within` ring so it is
// visible on the label the eye can see. NOTHING IS PROMOTED TO `@boutique/ui`
// (D13): one control, two mounts, one app. `SlotPicker` is already the
// extraction template when a third consumer appears.
// ponytail: inline segmented radios; promote to packages/ui when a second app
// needs them.
export const UNANSWERED = null;

export interface ShiftAvailabilityFieldsetProps {
  templateId: string;
  // «משמרת בוקר · 09:00–14:00» — the legend, so a screen reader announces
  // «חמישי 16:00–21:00, זמינה» rather than three unlabelled radios.
  legend: string;
  value: AvailabilityState | null;
  onChange: (state: AvailabilityState | null) => void;
  // Rendered only when an elevated actor recorded this answer (D5). It goes on
  // the FIELDSET's `aria-describedby`, so it is announced once on entering the
  // group rather than repeated on each of the four radios — and never dropped,
  // which a plain <p> after the radios would be for anyone arrowing through.
  recordedByName?: string | null;
  disabled?: boolean;
}

// ⚠ ALL FOUR OPTIONS SHARE ONE SELECTED TREATMENT, AND THAT IS A DELIBERATE
// KILL. The obvious design colours «זמינה» green, «לא זמינה» red, «מעדיפה»
// gold. Rejected twice over: `--color-danger` is reserved for something the
// owner must FIX and «לא זמינה» is a settled fact, not a fault
// (`lib/booking.tsx`'s shipped statement of that rule); and four hues would make
// hue the carrier of meaning inside a group whose options are already four
// words. The word is the meaning; the fill only says which one she picked.
//
// Giving «לא נרשם» a weaker fill would be the same defect wearing a different
// hat — "unanswered" would look like "nothing is selected", which is the exact
// ambiguity the fourth option exists to remove.
const OPTION = cn(
  "flex min-h-11 cursor-pointer items-center justify-center rounded-full",
  "border border-border-input bg-surface-raised px-2 text-base text-ink",
  "focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-focus",
);
const SELECTED = "border-gold-strong bg-gold font-semibold";

const OPTIONS: { value: AvailabilityState | null; labelKey: string }[] = [
  { value: "available", labelKey: "shifts.states.available" },
  { value: "unavailable", labelKey: "shifts.states.unavailable" },
  { value: "preferred", labelKey: "shifts.states.preferred" },
  { value: UNANSWERED, labelKey: "shifts.stateUnanswered" },
];

export function ShiftAvailabilityFieldset({
  templateId,
  legend,
  value,
  onChange,
  recordedByName = null,
  disabled = false,
}: ShiftAvailabilityFieldsetProps) {
  const { t } = useTranslation();
  const groupId = useId();
  const describedById = `${groupId}-recorded`;

  return (
    <fieldset
      className="border-0 p-0"
      aria-describedby={recordedByName === null ? undefined : describedById}
    >
      <legend className="mb-2 text-sm font-semibold text-ink">{legend}</legend>
      {/* 2×2 at 375px, four-up from `sm`. ⚠ NOT grid-cols-4 on a phone: the
          longest label «לא זמינה» needs ~78px and a four-up row leaves 68px, so
          the fourth option is exactly what makes the single row impossible —
          and a truncated state word on the control that carries the meaning is
          not a trade this surface can make. */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {OPTIONS.map((option) => (
          <label
            key={option.labelKey}
            className={cn(OPTION, option.value === value && SELECTED, disabled && "opacity-60")}
          >
            <input
              type="radio"
              // ⚠ KEYED ON THE TEMPLATE, NEVER THE WEEKDAY. Two shifts on one
              // weekday are legal and expected (D2 — a morning and an afternoon
              // sharing the changeover hour is an ordinary split shift), and a
              // weekday-keyed `name` would FUSE them into one group so that
              // answering the afternoon silently clears the morning. This is the
              // cheapest bug in the feature and the key choice is the only thing
              // preventing it.
              name={`${groupId}-${templateId}`}
              value={option.value ?? ""}
              checked={option.value === value}
              disabled={disabled}
              onChange={() => {
                onChange(option.value);
              }}
              className="sr-only"
            />
            {t(option.labelKey)}
          </label>
        ))}
      </div>
      {recordedByName !== null && (
        <p id={describedById} className="mt-2 text-sm text-ink-muted">
          {/* The <bdi> lives in the copy VALUE and renders through <Trans>: a
              name interpolated by t() cannot be isolated any other way, and this
              line ends with a full stop IMMEDIATELY after the name — «נרשם על
              ידי .Ronit Bar» without the island. BARE <bdi>, never dir="ltr". */}
          <Trans i18nKey="shifts.recordedBy" values={{ name: recordedByName }} components={{ bdi: <bdi /> }} />
        </p>
      )}
    </fieldset>
  );
}
