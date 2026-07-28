import { useTranslation } from "react-i18next";
import { SectionHeading, cn, focusRing } from "@boutique/ui";
import { useBoutique } from "../components/StorefrontLayout";

// הצהרת נגישות. IS 5568 §35 makes this page — and a named, reachable contact
// inside it — a legal obligation for a public Israeli site, so it is written to
// be read by a screen reader and audited by a person: one h1, an h2 per section,
// real lists, and no content that exists only as visual arrangement.
//
// THE RESPONSIBLE PARTY IS THE BOUTIQUE. It is the service provider, and its
// own phone and Instagram come from the layout-level fetch. There is
// deliberately no platform-operator coordinator layer: the design gate names
// the boutique, and a statement declaring conformance while showing
// «fill this in» is itself the non-conformance it declares against.

const linkClass = cn("rounded-sm text-gold-text underline", focusRing);
const bodyClass = "text-base text-ink-muted";
const listClass = "list-disc space-y-2 ps-6 text-base text-ink-muted";
const rowClass = "flex flex-wrap gap-x-2";

const DONE_KEYS = [
  "doneFonts",
  "doneKeyboard",
  "doneContrast",
  "doneRtl",
  "doneImages",
  "doneMenu",
] as const;

const MENU_KEYS = [
  "menuContrast",
  "menuTextSize",
  "menuReadableFont",
  "menuUnderlineLinks",
  "menuStopMotion",
] as const;

const LIMIT_KEYS = ["limitsZoom", "limitsAlt"] as const;

function Bullets({ items }: { items: readonly string[] }) {
  const { t } = useTranslation();
  return (
    <ul className={listClass}>
      {items.map((key) => (
        <li key={key}>{t(`statement.${key}`)}</li>
      ))}
    </ul>
  );
}

export function AccessibilityPage() {
  const { t } = useTranslation();
  // The boutique block only ever UPGRADES this page — its name replaces the
  // generic one, its phone and Instagram add reachable channels. There is
  // deliberately no loading state and no error state: a statement page that
  // renders a spinner or an error instead of the statement is itself the
  // accessibility failure it exists to declare.
  const { boutique } = useBoutique();
  const siteName = boutique?.name ?? t("catalog.essenceFallback");
  const phone = boutique?.phone ?? null;
  const instagram = boutique?.instagram ?? null;

  return (
    // pb-16 (64px) clears the fixed A11yMenu button's 60px footprint — a 44px
    // button offset by --space-4 — which this route carries with no CTA bar
    // beneath it to reserve the space (PRE-2).
    <div className="mx-auto flex max-w-[720px] flex-col gap-8 px-4 pt-8 pb-16">
      <div className="flex flex-col gap-2">
        <h1 className="font-display text-2xl text-ink">{t("statement.title")}</h1>
        {/* Which site this statement covers. */}
        <p className={bodyClass}>{siteName}</p>
        <p className={bodyClass}>{t("statement.intro")}</p>
      </div>

      <div className="flex flex-col gap-3">
        <SectionHeading as="h2">{t("statement.conformanceHeading")}</SectionHeading>
        <p className={bodyClass}>{t("statement.conformanceBody")}</p>
      </div>

      <div className="flex flex-col gap-3">
        <SectionHeading as="h2">{t("statement.doneHeading")}</SectionHeading>
        <Bullets items={DONE_KEYS} />

        {/* The menu is part of what was done, so it nests under it rather than
            claiming a section of its own. */}
        <h3 className="mt-3 font-display text-lg text-ink">{t("statement.menuHeading")}</h3>
        <Bullets items={MENU_KEYS} />
        <p className={bodyClass}>{t("statement.menuNote")}</p>
      </div>

      <div className="flex flex-col gap-3">
        <SectionHeading as="h2">{t("statement.limitsHeading")}</SectionHeading>
        <Bullets items={LIMIT_KEYS} />
        <p className={bodyClass}>{t("statement.limitsNote")}</p>
      </div>

      <div className="flex flex-col gap-3">
        <SectionHeading as="h2">{t("statement.coordinatorHeading")}</SectionHeading>
        <p className={bodyClass}>{t("statement.coordinatorIntro")}</p>
        {/* A description list, not paragraphs: the label/value pairing is what a
            screen reader announces, and it is the part an auditor looks for by
            name. Rows with no value are omitted entirely rather than rendered
            empty — an unanswered API must not produce a dangling <dt>. */}
        <dl className="flex flex-col gap-2 text-base">
          <div className={rowClass}>
            <dt className="text-ink-muted">{t("statement.coordinatorPhoneLabel")}</dt>
            {phone === null ? (
              <dd className="text-ink">{siteName}</dd>
            ) : (
              <dd>
                {/* A phone number is a strong-LTR digit run dropped into RTL
                    prose; bdi isolates it so bidi cannot reorder it. */}
                <a href={`tel:${phone}`} className={linkClass}>
                  <bdi dir="ltr">{phone}</bdi>
                </a>
              </dd>
            )}
          </div>
          {instagram !== null && (
            <div className={rowClass}>
              <dt className="text-ink-muted">{t("statement.coordinatorInstagramLabel")}</dt>
              <dd>
                <a
                  href={`https://instagram.com/${instagram}`}
                  target="_blank"
                  rel="noopener noreferrer external"
                  className={linkClass}
                >
                  <bdi dir="ltr">@{instagram}</bdi>
                </a>
              </dd>
            </div>
          )}
        </dl>
      </div>

      <div className="flex flex-col gap-3">
        <SectionHeading as="h2">{t("statement.reportHeading")}</SectionHeading>
        <p className={bodyClass}>{t("statement.reportBody")}</p>
        {/* Channels, not prose — each one is a link a visitor can act on from
            here. Omitted rather than rendered empty when the boutique has
            supplied neither (a bare <ul> announces as an empty list). */}
        {(phone !== null || instagram !== null) && (
          <ul className={listClass}>
            {phone !== null && (
              <li>
                {t("contact.call")}:{" "}
                <a href={`tel:${phone}`} className={linkClass}>
                  <bdi dir="ltr">{phone}</bdi>
                </a>
              </li>
            )}
            {instagram !== null && (
              <li>
                {t("contact.instagram")}:{" "}
                <a
                  href={`https://instagram.com/${instagram}`}
                  target="_blank"
                  rel="noopener noreferrer external"
                  className={linkClass}
                >
                  <bdi dir="ltr">@{instagram}</bdi>
                </a>
              </li>
            )}
          </ul>
        )}
      </div>

      <p className="text-sm text-ink-muted">{t("statement.updated")}</p>
    </div>
  );
}
