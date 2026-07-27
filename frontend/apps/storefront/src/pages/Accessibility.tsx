import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { SectionHeading, cn, focusRing } from "@boutique/ui";
import { getBoutiqueOnce } from "../api";
import type { PublicBoutiqueResponse } from "../api";

// הצהרת נגישות. IS 5568 §35 makes this page — and the named coordinator inside
// it — a legal obligation for a public Israeli site, so it is written to be read
// by a screen reader and audited by a person: one h1, an h2 per section, real
// lists, and no content that exists only as visual arrangement.
//
// TODO(launch blocker): statement.coordinator{Name,Role,Phone,Email} in
// src/i18n/he.ts are still visible placeholders. They are the PLATFORM
// OPERATOR's details — one constant across every tenant, not the boutique
// owner's — and shipping them unfilled to the pilot is itself the compliance
// failure this page declares against.

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
  const coordinatorEmail = t("statement.coordinatorEmail");

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
        <p className={bodyClass}>{t("statement.coordinatorIntro")}</p>
        {/* A description list, not four paragraphs: the label/value pairing is
            what a screen reader announces, and it is the part an auditor looks
            for by name. */}
        <dl className="flex flex-col gap-2 text-base">
          <div className={rowClass}>
            <dt className="text-ink-muted">{t("statement.coordinatorNameLabel")}</dt>
            <dd className="text-ink">{t("statement.coordinatorName")}</dd>
          </div>
          <div className={rowClass}>
            <dt className="text-ink-muted">{t("statement.coordinatorRoleLabel")}</dt>
            <dd className="text-ink">{t("statement.coordinatorRole")}</dd>
          </div>
          <div className={rowClass}>
            <dt className="text-ink-muted">{t("statement.coordinatorPhoneLabel")}</dt>
            {/* A phone number is a strong-LTR digit run dropped into RTL prose;
                dir isolates it so the bidi algorithm cannot reorder it. */}
            <dd dir="ltr" className="text-ink">
              {t("statement.coordinatorPhone")}
            </dd>
          </div>
          <div className={rowClass}>
            <dt className="text-ink-muted">{t("statement.coordinatorEmailLabel")}</dt>
            <dd>
              <a href={`mailto:${coordinatorEmail}`} dir="ltr" className={linkClass}>
                {coordinatorEmail}
              </a>
            </dd>
          </div>
        </dl>
      </div>

      <div className="flex flex-col gap-3">
        <SectionHeading as="h2">{t("statement.reportHeading")}</SectionHeading>
        <p className={bodyClass}>{t("statement.reportBody")}</p>
        {/* Channels, not prose — each one is a link a visitor can act on from
            here. The boutique's phone appears only once the API has answered;
            the coordinator's address is always present, so this list is never
            empty. */}
        <ul className={listClass}>
          <li>
            {t("statement.coordinatorEmailLabel")}:{" "}
            <a href={`mailto:${coordinatorEmail}`} dir="ltr" className={linkClass}>
              {coordinatorEmail}
            </a>
          </li>
          {boutiquePhone !== null && (
            <li>
              {t("contact.call")}:{" "}
              <a href={`tel:${boutiquePhone}`} dir="ltr" className={linkClass}>
                {boutiquePhone}
              </a>
            </li>
          )}
        </ul>
      </div>

      <p className="text-sm text-ink-muted">{t("statement.updated")}</p>
    </div>
  );
}
