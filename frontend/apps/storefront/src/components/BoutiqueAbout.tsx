import { useTranslation } from "react-i18next";
import { Card, ContactPanel, HoursTable, SectionHeading } from "@boutique/ui";
import type { PublicBoutiqueResponse } from "../api";
import { contactLabels, wazeUrl, whatsappDigits } from "../lib/contact";
import { DAY_KEYS, hhmm, shortDate, todayLine, toWeeklyRules } from "../lib/hours-adapter";

// The profile + hours block. It lives here rather than in a page because two
// screens render it: /about, and the catalog's empty state — where the design
// requires the storefront to still feel complete with zero dresses.

export interface BoutiqueAboutProps {
  boutique: PublicBoutiqueResponse;
  // Injectable so tests can pin a day without pinning the machine's clock. The
  // hours logic itself is timezone-explicit (Asia/Jerusalem), never the device.
  now?: Date;
  className?: string;
}

export function BoutiqueAbout({ boutique, now = new Date(), className }: BoutiqueAboutProps) {
  const { t } = useTranslation();
  const { profile, rules, exceptions } = boutique;

  const weeklyRules = toWeeklyRules(rules);
  const dayLabels = DAY_KEYS.map((key) => t(`hours.day.${key}`));

  // Closed-today leads the card in plain ink — being closed is not an error, so
  // it never uses the danger colour.
  const todayText = todayLine(boutique, now, t);

  return (
    <div className={className}>
      {/* text-base carries the design's 1.6 line-height from the theme — adding
          a leading- utility here would override the token. */}
      {profile.description !== null && (
        <p className="text-base text-ink-muted">{profile.description}</p>
      )}

      <Card className="mt-6">
        <SectionHeading as="h2">{t("hours.heading")}</SectionHeading>
        <p className="mt-2 text-base text-ink">{todayText}</p>
        <HoursTable
          className="mt-3"
          rules={weeklyRules}
          dayLabels={dayLabels}
          closedLabel={t("hours.closed")}
        />
        {exceptions.length > 0 && (
          <ul className="mt-3 flex flex-col gap-1">
            {exceptions.map((exception) => {
              const closed = exception.open_time === null || exception.close_time === null;
              const text = closed
                ? t("hours.exceptionClosed", { date: shortDate(exception.date) })
                : t("hours.exceptionHours", {
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
                  {t("hours.exceptionsLabel")}: {text}
                  {exception.note !== null && ` · ${exception.note}`}
                </li>
              );
            })}
          </ul>
        )}
      </Card>

      <Card className="mt-6">
        <ContactPanel
          phone={profile.phone ?? undefined}
          whatsapp={whatsappDigits(profile.phone)}
          wazeUrl={wazeUrl(profile.address)}
          mapsUrl={profile.maps_url ?? undefined}
          labels={contactLabels(t)}
        />
      </Card>
    </div>
  );
}
