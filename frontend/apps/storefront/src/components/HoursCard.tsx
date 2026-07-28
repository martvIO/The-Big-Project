import { useTranslation } from "react-i18next";
import { Card, HoursTable, SectionHeading } from "@boutique/ui";
import type { BoutiqueResponse } from "../api";
import { hhmm, shortDate, todayLine, toWeeklyRules } from "../lib/hoursText";

// HoursTable plus the two things the primitive deliberately does not own: the
// composed "today" lead line, and the upcoming-exceptions row underneath it.

export interface HoursCardProps {
  boutique: BoutiqueResponse;
  // Injectable so tests can pin a day without pinning the machine's clock. The
  // hours logic itself is timezone-explicit (Asia/Jerusalem), never the device.
  now?: Date;
  className?: string;
}

export function HoursCard({ boutique, now = new Date(), className }: HoursCardProps) {
  const { t } = useTranslation();
  const weeklyRules = toWeeklyRules(boutique.hours);
  const dayLabels = t("hours.days", { returnObjects: true }) as string[];

  // Closed-today leads the card in plain ink — being closed is not an error, so
  // it never uses the danger colour. null means the boutique has no weekly
  // rules at all, which is not the same as being closed today.
  const todayText = todayLine(boutique, now, t);

  return (
    <Card className={className}>
      <SectionHeading as="h2">{t("about.hoursHeading")}</SectionHeading>
      <p className="mt-2 text-base text-ink">{todayText ?? t("about.hoursUnavailable")}</p>
      <HoursTable
        className="mt-3"
        rules={weeklyRules}
        dayLabels={dayLabels}
        closedLabel={t("hours.closed")}
      />
      {boutique.exceptions.length > 0 && (
        <ul className="mt-3 flex flex-col gap-1">
          {boutique.exceptions.map((exception) => {
            const closed = exception.open_time === null || exception.close_time === null;
            const text = closed
              ? t("about.exceptionClosed", { date: shortDate(exception.date) })
              : t("about.exceptionHours", {
                  date: shortDate(exception.date),
                  open: hhmm(exception.open_time ?? ""),
                  close: hhmm(exception.close_time ?? ""),
                });
            return (
              <li key={exception.date} className="text-base text-ink-muted">
                {/* Marker AND text — an exception is never signalled by colour alone. */}
                <span aria-hidden="true" className="text-gold-strong">
                  ◆
                </span>{" "}
                {t("about.exceptionsLabel")}: {text}
                {exception.note !== null && ` · ${exception.note}`}
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
