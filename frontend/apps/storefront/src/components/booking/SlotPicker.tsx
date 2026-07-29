import { useId } from "react";
import type { Ref } from "react";
import { useTranslation } from "react-i18next";
import { DateField, cn } from "@boutique/ui";

export interface SlotTime {
  // The slot's raw starts_at instant — what the booking POST carries.
  value: string;
  // "10:45", already read in the boutique's calendar, never the device's.
  label: string;
}

export interface SlotPickerProps {
  date: string;
  min?: string;
  max?: string;
  onDateChange: (date: string) => void;
  times: SlotTime[];
  value: string | null;
  onChange: (startsAt: string) => void;
  // The mid-flow return reason (errors.slotUnavailable) and the R7 "no time
  // chosen" message share this slot.
  error?: string;
  ref?: Ref<HTMLInputElement>;
}

const chipClass = cn(
  "flex min-h-11 cursor-pointer items-center justify-center rounded-full border border-border-input bg-surface-raised px-3 text-base text-ink",
  "focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-focus",
);

// Native <input type="date"> plus a chip grid with radio semantics. No calendar
// library and no custom popover: the native control gets the OS picker, the OS
// locale and the OS accessibility stack for free.
//
// ONE fetch covers the whole window; changing the date filters in memory rather
// than spending fourteen round trips against a throttled read budget.
export function SlotPicker({
  date,
  min,
  max,
  onDateChange,
  times,
  value,
  onChange,
  error,
  ref,
}: SlotPickerProps) {
  const { t } = useTranslation();
  const groupId = useId();

  return (
    <div className="flex flex-col gap-6">
      <DateField
        label={t("booking.pickDate")}
        // A date control is a numeric run.
        dir="ltr"
        value={date}
        min={min}
        max={max}
        onChange={(event) => {
          onDateChange(event.target.value);
        }}
        className="max-w-[200px]"
      />

      {/* Outside the fieldset: a <legend> that is not the first element child
          stops being the caption and stops naming the group. */}
      {error !== undefined && (
        <p role="alert" className="text-base text-danger">
          {error}
        </p>
      )}

      <fieldset className="border-0 p-0">
        <legend className="mb-2 text-sm font-semibold text-ink">{t("booking.pickTime")}</legend>
        {times.length === 0 ? (
          // The state every new tenant ships in, so it reads as a fact, not a
          // fault: no icon, no border, no danger colour, no retry — there is
          // nothing to retry. Whole-window-empty and this-date-empty are the
          // same block and the same string.
          <p className="mx-auto max-w-[40ch] py-8 text-center text-base text-ink-muted">
            {t("booking.noSlots")}
          </p>
        ) : (
          // ONE auto-fill rule, no breakpoints: the column count is a
          // consequence of the rule and the Card padding it sits inside.
          <div className="grid gap-2 [grid-template-columns:repeat(auto-fill,minmax(104px,1fr))]">
            {times.map((slot, index) => (
              <label
                key={slot.value}
                className={cn(
                  chipClass,
                  // Selection is carried by the native :checked state, by fill
                  // AND by weight — three channels, none of them hue alone.
                  slot.value === value && "border-gold-strong bg-gold font-semibold",
                )}
              >
                <input
                  type="radio"
                  name={`${groupId}-slot`}
                  value={slot.value}
                  checked={slot.value === value}
                  onChange={() => {
                    onChange(slot.value);
                  }}
                  ref={index === 0 ? ref : undefined}
                  className="sr-only"
                />
                {/* A Latin/numeric run inside Hebrew. The legend and the date
                    control above already scope the group, so the bare time is
                    the whole accessible name. */}
                <bdi dir="ltr">{slot.label}</bdi>
              </label>
            ))}
          </div>
        )}
      </fieldset>
    </div>
  );
}
