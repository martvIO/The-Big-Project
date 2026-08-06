import { useTranslation } from "react-i18next";
import { Card, JERusalem } from "@boutique/ui";
import type { ManageBookingResponse } from "../../api";

// EXTRACTED from ManageBookingPage (F24 F-P3), not forked. The portal detail and
// the tokenized page render the SAME `ManageBookingResponse`, and the mirror
// guarantee is that one component renders it — a copy that drifts is the
// guarantee lost the first time either side learns a new fact.
//
// Instants render in the BOUTIQUE's zone. A bride whose phone clock the airline
// changed must still read the boutique's time, and the confirmation screen makes
// the same choice with the same formatters.
export const WEEKDAY = new Intl.DateTimeFormat("he-IL", { timeZone: JERusalem, weekday: "long" });
export const DATE = new Intl.DateTimeFormat("he-IL", {
  timeZone: JERusalem,
  day: "numeric",
  month: "numeric",
  year: "numeric",
});
export const TIME = new Intl.DateTimeFormat("en-GB", {
  timeZone: JERusalem,
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

// The facts, with labels REUSED from the approved confirmation screen (design
// P2) — one label, one Hebrew, no drift between the screens that show the same
// appointment. Labels rather than sentences because interpolation cannot carry
// the <bdi> a numeral needs, and a label/value pair survives being read back off
// a screenshot at 200% zoom.
export function BookingFacts({ booking }: { booking: ManageBookingResponse["booking"] }) {
  const { t } = useTranslation();
  const when = new Date(booking.starts_at);

  return (
    <Card className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <p className="text-sm font-semibold text-ink-muted">{t("booking.confirmWhen")}</p>
        <p className="text-lg text-ink">
          {WEEKDAY.format(when)}, <bdi dir="ltr">{DATE.format(when)}</bdi>{" "}
          <span aria-hidden="true">·</span> <bdi dir="ltr">{TIME.format(when)}</bdi>
        </p>
      </div>

      <span aria-hidden="true" className="h-px bg-border" />

      <div className="flex flex-col gap-1">
        <p className="text-sm font-semibold text-ink-muted">{t("booking.confirmWhat")}</p>
        {/* Owner-authored, so it may be Hebrew or Latin — a bare <bdi> isolates
            it either way. dir="ltr" would itself be a bidi defect on Hebrew. */}
        <p className="text-lg text-ink">
          <bdi>{booking.appointment_type_name}</bdi>
        </p>
        {booking.dress_name !== null && booking.dress_size !== null && (
          <p className="text-base text-ink">
            <bdi>{booking.dress_name}</bdi> <span aria-hidden="true">·</span>{" "}
            {t("booking.confirmDress")} <bdi>{booking.dress_size}</bdi>
          </p>
        )}
      </div>
    </Card>
  );
}

// R19's split shape: the lead, the isolated numeral, the tail. i18next
// interpolation cannot carry the <bdi> the number needs, so the seam moved
// rather than the words.
export function PolicyLine({ hours }: { hours: number }) {
  const { t } = useTranslation();
  return (
    <p className="text-sm text-ink-muted">
      {t("manage.cancelPolicyLead")} <bdi dir="ltr">{hours}</bdi>{" "}
      {t("manage.cancelPolicySuffix")}
    </p>
  );
}
