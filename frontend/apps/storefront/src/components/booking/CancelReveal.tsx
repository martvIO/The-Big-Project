import { forwardRef } from "react";
import { useTranslation } from "react-i18next";
import { Button, Card } from "@boutique/ui";
import type { ManageBookingResponse } from "../../api";
import { PolicyLine } from "./BookingFacts";

// THE TWO-STEP, extracted from ManageBookingPage (F24 F-P3) so the portal runs
// the same one rather than a copy of it. The secondary trigger that opens this
// does not call the API; one tap must never cancel a wedding-dress appointment.
// An inline reveal rather than a Modal: the whole decision stays on one surface
// and the focus-trap machinery is spared for a two-button choice.

interface CancelRevealProps {
  policy: ManageBookingResponse["policy"];
  depositTaken: boolean;
  busy: boolean;
  onConfirm: () => void;
  onKeep: () => void;
}

export const CancelReveal = forwardRef<HTMLParagraphElement, CancelRevealProps>(
  function CancelReveal({ policy, depositTaken, busy, onConfirm, onKeep }, questionRef) {
    const { t } = useTranslation();
    return (
      <Card className="flex flex-col gap-4 bg-surface-raised">
        {/* The focus destination for the reveal — the QUESTION itself, so a
            screen reader hears what is being asked rather than an anonymous
            container. */}
        <p ref={questionRef} tabIndex={-1} className="text-lg text-ink">
          {t("manage.cancelQuestion")}
        </p>
        {/* The window fact from HER accepted policy. Absent only if that version
            row has gone — the page then says nothing about a number it cannot
            justify. */}
        {policy !== null && <PolicyLine hours={policy.refundable_until_hours_before} />}
        {/* MD3. The branch is `deposit_taken`, NOT status: a CONFIRMED booking
            paid weeks ago has a deposit too, so status cannot answer this —
            which is the entire reason that boolean is on the wire. */}
        <p className="text-base text-ink">
          {t(depositTaken ? "manage.cancelConsequenceDeposit" : "manage.cancelConsequenceFree")}
        </p>
        <div className="flex flex-col gap-3 sm:flex-row">
          {/* danger on the SECOND click only — the trigger that revealed this
              was secondary. */}
          <Button variant="danger" size="md" fullWidthMobile loading={busy} onClick={onConfirm}>
            {t("manage.cancelConfirm")}
          </Button>
          <Button variant="ghost" size="md" fullWidthMobile onClick={onKeep}>
            {t("manage.cancelKeep")}
          </Button>
        </div>
      </Card>
    );
  },
);
