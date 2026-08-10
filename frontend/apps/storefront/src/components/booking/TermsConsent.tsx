import { Card, Checkbox } from "@boutique/ui";
import type { Ref } from "react";
import { useTranslation } from "react-i18next";
import type { StorefrontTerms } from "../../api";

/**
 * The cancellation policy and its consent tick — ONE legal render, two callers.
 *
 * Design F-O4: this prose was inline in `BookPage`'s terms step, and F23's
 * `/w/{token}` needs the identical block. A second, drifting copy of a LEGAL
 * policy render is the one duplication the design deck refuses, so the
 * extraction is the feature's price of admission rather than a tidy-up.
 *
 * Everything about the markup is `BookPage`'s, moved rather than rewritten:
 *
 * - The two numbers sit ABOVE the prose because they are what she is actually
 *   agreeing to, and a paragraph is where numbers hide. Weight and a divider
 *   carry the distinction — never a tinted callout, which would read as an
 *   alert two neutral facts are not.
 * - R19: both numbers are isolated, mid-sentence, which is why each string is a
 *   lead and a tail rather than one interpolation. The `%` rides INSIDE the bdi
 *   — "50%" is one LTR run, not a digit run and a stray neutral.
 * - The owner's text is a React text child and only ever that: no
 *   `dangerouslySetInnerHTML`, no markdown renderer, no sanitise-then-inject.
 *   She is semi-trusted, but this is a public, anonymous, multi-tenant surface,
 *   so any HTML path is stored XSS for every visitor.
 * - The tick is LAST in flow. A consent control reachable before the thing
 *   consented to is how unread consent happens.
 */
export function TermsConsent({
  terms,
  accepted,
  error,
  onAcceptedChange,
  checkboxRef,
}: {
  terms: StorefrontTerms;
  accepted: boolean;
  error?: string;
  onAcceptedChange: (accepted: boolean) => void;
  checkboxRef?: Ref<HTMLInputElement>;
}) {
  const { t } = useTranslation();
  return (
    <Card className="flex flex-col gap-4">
      <p className="text-base font-semibold text-ink">
        {t("booking.refundWindow")} <bdi dir="ltr">{terms.refundable_until_hours_before}</bdi>{" "}
        {t("booking.refundWindowSuffix")}
      </p>
      <p className="text-base font-semibold text-ink">
        {t("booking.forfeit")} <bdi dir="ltr">{terms.forfeit_percent}%</bdi>{" "}
        {t("booking.forfeitSuffix")}
      </p>

      <span aria-hidden="true" className="h-px bg-border" />

      {/* pre-line keeps her line breaks and collapses her stray spaces;
          dir="auto" because owners paste English clauses; anywhere because a
          pasted 200-character URL must not scroll the page sideways. No inner
          scroller at any width — two scroll contexts on a phone is a trap, and
          a scrollable box is a tab stop between the policy and the consent. */}
      <div dir="auto" className="whitespace-pre-line text-base text-ink [overflow-wrap:anywhere]">
        {terms.terms_text}
      </div>

      <span aria-hidden="true" className="h-px bg-border" />

      <Checkbox
        label={t("booking.acceptTerms")}
        checked={accepted}
        error={error}
        onCheckedChange={onAcceptedChange}
        ref={checkboxRef}
      />
    </Card>
  );
}
