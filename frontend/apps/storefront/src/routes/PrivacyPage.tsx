import { useTranslation } from "react-i18next";
import { SectionHeading } from "@boutique/ui";
import { substituteBoutique } from "../lib/privacyText";
import { PrivacyProse } from "../components/PrivacyProse";
import { useBoutique } from "../components/StorefrontLayout";

// הודעת פרטיות. PPL §11 makes a collection notice a legal obligation, and
// Amendment 13 makes the processor relationship and the sub-processor list part
// of what has to be disclosed — so this page is written the way the accessibility
// statement is written, and for the same reason: to be read by a screen reader
// and audited by a person. One h1, an h2 per document, real paragraphs, and no
// content that exists only as visual arrangement.
//
// THE CONTROLLER IS THE BOUTIQUE. «בעל מאגר» is the statute's own term and the
// documents say so in their own first sentences; the boutique's name comes from
// the layout-level fetch and is substituted into them here.
//
// ⚠ THE THREE DOCUMENTS ARE NOT IN THE i18n BUNDLE AND MAY NEVER BE. They ride
// `GET /storefront/boutique`, already resolved: the boutique's override where
// she wrote one, the platform Hebrew where she did not. The booking form's
// `details` step renders the SAME `privacy_notice_text` from the same fetch, so
// there is exactly one copy of each string in the product. A duplicate in
// `he.ts` would be a second place for a legal text to drift — the failure F33's
// `checkin.notice` comment already names.
//
// ⚠ NO `dangerouslySetInnerHTML`, on any branch. The notice and the DPA clause
// are TENANT-AUTHORED text on an anonymous public page: rendering them as HTML
// would make a privacy document the vector for stored XSS. They are rendered as
// text, which is why the backend also asserts that no `<` appears in any of the
// platform constants — belt and braces, in that order.

const bodyClass = "whitespace-pre-line text-base text-ink-muted [overflow-wrap:anywhere]";

// One document: its own <h2>, its blank-line-separated paragraphs and its
// bullet runs as real lists.
//
// Blocks, not one pre-line <div>, because a single scrolling block would give a
// screen-reader user no structure at all. The <h2> comes from a key and is never
// a line inside the string (copy.md R7): baked in, it would render as a <p> — a
// visual heading with no semantics, a WCAG 1.3.1 failure on the twin of the
// accessibility statement.
//
// ⚠ The bullet lists WERE that same failure and shipped that way: seventeen `•`
// lines across the three documents, all inside <p>, with no <ul>/<li> anywhere.
// `PrivacyProse` is now the one renderer both this page and the booking flow's
// §11 notice use, which is what makes D13's «the same text» also «the same
// semantics».
function Document({ testId, heading, text }: { testId: string; heading: string; text: string }) {
  return (
    // `data-testid` because `SectionHeading` wraps its own <h2> in a div, so
    // "the block under this heading" is not reachable from the heading by one
    // parentElement hop — and WHICH document sits under which heading is the
    // assertion D14 needs (the sub-processor list is the one a boutique may not
    // rewrite, so rendering an override in its slot would defeat the whole rule
    // while every heading-count check stayed green).
    <div data-testid={testId} className="flex flex-col gap-3">
      <SectionHeading as="h2">{heading}</SectionHeading>
      <PrivacyProse text={text} className={bodyClass} />
    </div>
  );
}

export function PrivacyPage() {
  const { t } = useTranslation();
  // Deliberately NO loading state and NO error state, exactly as
  // AccessibilityPage refuses one. A statutory document that renders a spinner
  // or an outage message in place of itself is the non-compliance it exists to
  // declare against — and this page is linked from the footer of every route, so
  // it is where a visitor lands precisely when something else is failing.
  //
  // The consequence is real and is accepted: with the fetch in flight or failed
  // there is no text to show, so the page renders its heading and nothing under
  // it. That is a page that is honestly empty rather than one that lies.
  const { boutique } = useBoutique();
  const siteName = boutique?.name ?? null;

  return (
    // pb-16 clears the fixed A11yMenu trigger's 60px footprint, the same
    // reservation AccessibilityPage carries and for the same reason: this route
    // has no CTA bar beneath it to reserve the space (PRE-2).
    <div className="mx-auto flex max-w-[720px] flex-col gap-8 px-4 pt-8 pb-16">
      <div className="flex flex-col gap-2">
        <h1 className="font-display text-2xl text-ink">{t("privacy.title")}</h1>
        {/* Which boutique this notice covers. Bare <bdi> — dir="ltr" on a Hebrew
            name is itself a bidi defect. */}
        {siteName !== null && (
          <p className="text-base text-ink-muted">
            <bdi>{siteName}</bdi>
          </p>
        )}
      </div>

      {boutique !== null && (
        <>
          <Document
            testId="privacy-notice"
            heading={t("privacy.noticeHeading")}
            text={substituteBoutique(boutique.privacy_notice_text, siteName)}
          />
          <Document
            testId="privacy-dpa"
            heading={t("privacy.dpaHeading")}
            text={substituteBoutique(boutique.privacy_dpa_text, siteName)}
          />
          {/* LAST, and the order is load-bearing: the DPA clause above points
              forward at it («למעט ספקי התשתית שרשומים בהמשך»), so a list rendered
              above its own reference would leave that sentence pointing at
              nothing. It is also the one document a boutique cannot edit. */}
          <Document
            testId="privacy-subprocessors"
            heading={t("privacy.subprocessorsHeading")}
            text={substituteBoutique(boutique.privacy_subprocessors_text, siteName)}
          />
        </>
      )}

      <p className="text-sm text-ink-muted">{t("privacy.updated")}</p>
    </div>
  );
}
