import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { SectionHeading, cn, focusRing } from "@boutique/ui";
import { getBoutiqueOnce } from "../api";
import type { PublicBoutiqueResponse } from "../api";
import { ACCESSIBILITY_COORDINATOR } from "../lib/coordinator";

// הצהרת נגישות. IS 5568 §35 makes this page — and a named, reachable contact
// inside it — a legal obligation for a public Israeli site, so it is written to
// be read by a screen reader and audited by a person: one h1, an h2 per section,
// real lists, and no content that exists only as visual arrangement.
//
// The contact block has two shapes. When the platform operator's coordinator is
// configured (src/lib/coordinator.ts) it renders those details. Until then it
// falls back to the boutique's own channels — the boutique is the service
// provider, so that is a real contact, and it is the reason this page never
// renders a placeholder: a statement declaring conformance while showing
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

export function Accessibility() {
  const { t } = useTranslation();
  const [boutique, setBoutique] = useState<PublicBoutiqueResponse | null>(null);

  // This fetch only ever UPGRADES the page — the boutique's own name replaces the
  // generic brand name, and its phone adds a second reachable channel. There is
  // deliberately no loading state and no error state: a statement page that
  // renders a spinner or an error instead of the statement is itself the
  // accessibility failure it exists to declare. So the rejection is swallowed.
  useEffect(() => {
    let cancelled = false;
    getBoutiqueOnce()
      .then((data) => {
        if (!cancelled) setBoutique(data);
      })
      .catch(() => {
        // Intentionally silent — see above.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const siteName = boutique?.name ?? t("brand.title");
  const boutiquePhone = boutique?.profile.phone ?? null;
  const coordinator = ACCESSIBILITY_COORDINATOR;

  return (
    // pb-16 (64px) clears the fixed A11yMenu button's 60px footprint — a 44px
    // button offset by --space-4 — which this route carries with no CTA bar
    // beneath it to reserve the space (qa-checklist PRE-2).
    <div className="mx-auto flex max-w-[720px] flex-col gap-8 px-4 pt-8 pb-16">
      <div className="flex flex-col gap-2">
        <h1 className="font-display text-2xl text-ink">{t("statement.title")}</h1>
        {/* Which site this statement covers. brand.title stands in until — or if
            — /storefront/boutique answers. */}
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
        <p className={bodyClass}>
          {coordinator !== null
            ? t("statement.coordinatorIntro")
            : t("statement.coordinatorIntroBoutique")}
        </p>
        {/* A description list, not paragraphs: the label/value pairing is what a
            screen reader announces, and it is the part an auditor looks for by
            name. Rows with no value are omitted entirely rather than rendered
            empty — an unanswered API must not produce a dangling <dt>. */}
        <dl className="flex flex-col gap-2 text-base">
          {coordinator !== null ? (
            <>
              <div className={rowClass}>
                <dt className="text-ink-muted">{t("statement.coordinatorNameLabel")}</dt>
                <dd className="text-ink">{coordinator.name}</dd>
              </div>
              <div className={rowClass}>
                <dt className="text-ink-muted">{t("statement.coordinatorRoleLabel")}</dt>
                <dd className="text-ink">{coordinator.role}</dd>
              </div>
              <div className={rowClass}>
                <dt className="text-ink-muted">{t("statement.coordinatorPhoneLabel")}</dt>
                {/* A phone number is a strong-LTR digit run dropped into RTL
                    prose; dir isolates it so bidi cannot reorder it. */}
                <dd dir="ltr" className="text-ink">
                  {coordinator.phone}
                </dd>
              </div>
              <div className={rowClass}>
                <dt className="text-ink-muted">{t("statement.coordinatorEmailLabel")}</dt>
                <dd>
                  <a href={`mailto:${coordinator.email}`} dir="ltr" className={linkClass}>
                    {coordinator.email}
                  </a>
                </dd>
              </div>
            </>
          ) : (
            <>
              <div className={rowClass}>
                <dt className="text-ink-muted">{t("statement.coordinatorNameLabel")}</dt>
                <dd className="text-ink">{siteName}</dd>
              </div>
              {boutiquePhone !== null && (
                <div className={rowClass}>
                  <dt className="text-ink-muted">{t("statement.coordinatorPhoneLabel")}</dt>
                  <dd>
                    <a href={`tel:${boutiquePhone}`} dir="ltr" className={linkClass}>
                      {boutiquePhone}
                    </a>
                  </dd>
                </div>
              )}
            </>
          )}
        </dl>
      </div>

      <div className="flex flex-col gap-3">
        <SectionHeading as="h2">{t("statement.reportHeading")}</SectionHeading>
        <p className={bodyClass}>{t("statement.reportBody")}</p>
        {/* Channels, not prose — each one is a link a visitor can act on from
            here. Both entries are conditional, so the list is omitted rather
            than rendered empty when neither a coordinator nor a boutique phone
            is available (a bare <ul> announces as an empty list). */}
        {(coordinator !== null || boutiquePhone !== null) && (
          <ul className={listClass}>
            {coordinator !== null && (
              <li>
                {t("statement.coordinatorEmailLabel")}:{" "}
                <a href={`mailto:${coordinator.email}`} dir="ltr" className={linkClass}>
                  {coordinator.email}
                </a>
              </li>
            )}
            {boutiquePhone !== null && (
              <li>
                {t("contact.call")}:{" "}
                <a href={`tel:${boutiquePhone}`} dir="ltr" className={linkClass}>
                  {boutiquePhone}
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
