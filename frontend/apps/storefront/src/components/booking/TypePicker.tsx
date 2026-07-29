import { useId } from "react";
import type { Ref } from "react";
import { useTranslation } from "react-i18next";
import { Badge, ContactPanel, Price, cn } from "@boutique/ui";
import type { AppointmentTypeRow, BoutiqueResponse } from "../../api";
import { contactChannels, contactLabels } from "../../lib/contact";

export interface TypePickerProps {
  types: AppointmentTypeRow[];
  value: string | null;
  onChange: (typeId: string) => void;
  boutique: BoutiqueResponse | null;
  // A real validation failure — booking.typeRequired. Danger register.
  error?: string;
  /**
   * The recoverable "the thing you picked is gone, pick another" message —
   * booking.typeGoneRepick. Same slot shape and same warning register as
   * SizeChips' `notice`, because it is the same semantic state: the boutique's
   * catalogue moved under her, nothing she did failed. §5.8's measured contrast
   * ledger publishes that register as --color-warning-text. `error` takes
   * precedence when both are set — by then she has pressed forward and the
   * notice is stale.
   */
  notice?: string;
  // Lands on the checked row, or the first when nothing is chosen: R7 moves
  // focus here, and on a deposit row that re-announces the row's description.
  ref?: Ref<HTMLInputElement>;
}

// focus-WITHIN, not focusRing's focus-visible: the ring belongs to the row, and
// the thing that takes focus is the radio inside it. Written out rather than
// derived from focusRing — Tailwind compiles the classes it finds in the
// source, so a string built at runtime would never be generated.
const rowClass = cn(
  "flex min-h-11 cursor-pointer items-start gap-3 rounded-sm border-b border-border py-3 last:border-b-0 hover:bg-surface-raised",
  "focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-focus",
);

// Native fieldset + radios, styled as rows. NOT a Select: the duration, the
// brides-only badge and the deposit branch all have to be visible BEFORE
// choosing, and a <select> collapses every one of them into one line.
//
// No preselection — with a brides-only or deposit-required type first, choosing
// for her would choose wrongly.
export function TypePicker({
  types,
  value,
  onChange,
  boutique,
  error,
  notice,
  ref,
}: TypePickerProps) {
  const { t } = useTranslation();
  const groupId = useId();
  const channels = boutique === null ? null : contactChannels(boutique);
  const checkedIndex = types.findIndex((type) => type.id === value);
  const focusIndex = checkedIndex === -1 ? 0 : checkedIndex;
  const message = error ?? notice;

  return (
    <>
      {/* Outside the fieldset by necessity: a <legend> that is not the first
          element child stops being the caption and stops naming the group. */}
      {message !== undefined && (
        <p
          role="alert"
          className={cn("text-base", error === undefined ? "text-warning-text" : "text-danger")}
        >
          {message}
        </p>
      )}
      <fieldset className="border-0 p-0">
        {/* The legend IS the step's h2 — it cannot be a separate element. */}
        <legend className="mb-3 font-display text-xl font-medium text-ink">
          {t("booking.typeHeading")}
        </legend>
        <div className="flex flex-col">
          {types.map((type, index) => {
            const selected = type.id === value;
            const noticeId = `${groupId}-deposit-${type.id}`;
            return (
              <div key={type.id}>
                <label className={rowClass}>
                  <input
                    type="radio"
                    name={`${groupId}-type`}
                    value={type.id}
                    checked={selected}
                    onChange={() => {
                      onChange(type.id);
                    }}
                    // The reveal is a SIBLING of the label, not a child —
                    // <label> takes phrasing content only, and nesting a panel
                    // of links would fold it into the radio's accessible name.
                    // aria-describedby is the tie.
                    aria-describedby={type.deposit_required && selected ? noticeId : undefined}
                    ref={index === focusIndex ? ref : undefined}
                    className="mt-1 size-5 shrink-0 accent-gold-strong"
                  />
                  <span className="flex min-w-0 flex-1 flex-col gap-1 md:flex-row md:items-center md:justify-between md:gap-3">
                    <span className="text-base font-semibold text-ink">{type.name}</span>
                    <span className="flex items-center gap-2">
                      <span className="text-sm text-ink-muted">
                        {t("booking.typeDuration", { minutes: type.duration_minutes })}
                      </span>
                      {/* D10 — it labels, it does not gate: the row stays
                          selectable. Words, not a dimmed chip. */}
                      {type.audience === "brides_only" && (
                        <Badge variant="muted">{t("booking.audienceBrides")}</Badge>
                      )}
                    </span>
                  </span>
                </label>

                {/* D3 is per ROW. Siblings stay selectable, the date and the
                    grid stay operable, and a time already picked survives a
                    switch back to a bookable type. */}
                {type.deposit_required && selected && (
                  <div id={noticeId} className="flex flex-col gap-3 pb-3">
                    <p className="max-w-[60ch] text-base text-ink">
                      {t("booking.depositByPhone")}{" "}
                      {type.deposit_amount_agorot !== null && (
                        // P4: money renders through Price and nowhere else —
                        // qa-greps.sh bans the glyph in this tree outright.
                        <Price
                          agorot={type.deposit_amount_agorot}
                          visible
                          hiddenLabel={t("catalog.priceOnRequest")}
                        />
                      )}
                    </p>
                    {/* Inline, no Card — it is already on paper inside the
                        picker's Card. D12: the panel with every channel absent
                        is an empty flex box, so the degrade is a branch here. */}
                    {channels === null ? (
                      <p className="max-w-[60ch] text-base text-ink-muted">
                        {t("booking.contactUnavailable")}
                      </p>
                    ) : (
                      <ContactPanel {...channels} labels={contactLabels(t)} />
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </fieldset>
    </>
  );
}
