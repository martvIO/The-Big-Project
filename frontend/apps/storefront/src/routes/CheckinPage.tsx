import { useEffect, useId, useRef, useState } from "react";
import type { Ref } from "react";
import { useTranslation } from "react-i18next";
import { Button, Checkbox, Input, Skeleton, VisuallyHidden, cn } from "@boutique/ui";
import { api, errorMessageKey, errorMessageOr } from "../api";
import { useBoutique } from "../components/StorefrontLayout";
import { readCheckinTicket, writeCheckinTicket } from "../lib/checkinTicket";
import { Link, navigate } from "../router";
import { normalizePhone, validateName, validatePhone } from "../validation";

// The walk-in check-in form: the page the QR taped to the shop window opens.
//
// She is standing in a doorway on her own phone, so this is three fields and one
// button, with no flow, no stepper and no account. Every well-formed submit
// mints a ticket and goes straight to that ticket's own page — there is no
// second outcome, which is what makes the response say nothing about who is
// already in the queue.
//
// Identical container to /book/* and /b/{token} so the surfaces read as one
// product. hasBookingBar() is catalog-and-dress only, so this route reserves no
// CTA space; pb-16 is the fixed A11y trigger's own footprint.
const pageClass = "mx-auto flex max-w-[640px] flex-col gap-6 px-4 pt-8 pb-16 md:px-6";

const VISIT_TYPES = [
  { value: "bride", labelKey: "checkin.visitBride" },
  { value: "evening", labelKey: "checkin.visitEvening" },
] as const;

type VisitType = (typeof VISIT_TYPES)[number]["value"];

// SizeChips' shape, copied rather than shared: each branch carries its border
// AND its padding-inline exactly once, because cn has no tailwind-merge and a
// shared px-3 plus a conditional px-[11px] would ship both.
const chipClass = cn(
  "flex min-h-11 min-w-11 cursor-pointer items-center justify-center rounded-full bg-surface-raised px-3 py-1 text-base text-ink",
  "focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-focus",
);
const restingClass = "border border-border-input";
const selectedClass = "border-2 border-gold-strong font-semibold";

// Native radios in a fieldset, the input sr-only and the <label> carrying the
// chip — the storefront's established composite. A closed two-value set, so
// there is no "other" and nothing to type.
function VisitTypePicker({
  value,
  onChange,
  error,
  ref,
}: {
  value: VisitType | null;
  onChange: (value: VisitType) => void;
  error?: string;
  ref?: Ref<HTMLInputElement>;
}) {
  const { t } = useTranslation();
  const groupId = useId();
  const errorId = `${groupId}-error`;

  return (
    <fieldset className="border-0 p-0" aria-describedby={error === undefined ? undefined : errorId}>
      <legend className="mb-2 text-sm font-semibold text-ink">{t("checkin.visitType")}</legend>
      <div className="flex flex-wrap gap-2">
        {VISIT_TYPES.map((option, index) => {
          const selected = option.value === value;
          return (
            <label
              key={option.value}
              className={cn(chipClass, selected ? selectedClass : restingClass)}
            >
              <input
                type="radio"
                // WCAG 3.3.2 without a new key: `required` on each radio makes
                // the group required to AT, and this product uses no * marker.
                required
                name={`${groupId}-visit-type`}
                value={option.value}
                checked={selected}
                onChange={() => {
                  onChange(option.value);
                }}
                ref={index === 0 ? ref : undefined}
                className="sr-only"
              />
              {t(option.labelKey)}
            </label>
          );
        })}
      </div>
      {error !== undefined && (
        <p id={errorId} role="alert" className="mt-2 text-sm text-danger">
          {error}
        </p>
      )}
    </fieldset>
  );
}

function Heading() {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-3">
      <h1 className="font-display text-2xl text-ink">{t("checkin.heading")}</h1>
      {/* The gold hairline every non-catalog route carries. */}
      <span aria-hidden="true" className="h-px w-12 bg-gold" />
    </div>
  );
}

export function CheckinPage() {
  const { t } = useTranslation();
  const { boutique, loading, error: boutiqueError, retry } = useBoutique();

  // Read ONCE, in a lazy initialiser rather than an effect. Zero server
  // round-trip on mount is the property the whole design rests on: an effect
  // that "checked" this pointer against the server would reintroduce exactly
  // the lookup that made a stranger's guess into a presence oracle.
  const [pointer] = useState<string | null>(readCheckinTicket);

  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [visitType, setVisitType] = useState<VisitType | null>(null);
  const [optIn, setOptIn] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<{
    name?: string;
    phone?: string;
    visitType?: string;
  }>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  // A COUNTER, not the message: two identical failures in a row must each move
  // focus, and an effect keyed on the message alone would not re-run for the
  // second one.
  const [failures, setFailures] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  // F60's disclosure, and the WHOLE of its state. No ref, no effect, no
  // onKeyDown, no Esc handler, no focus move — see the JSX below.
  const [hintRevealed, setHintRevealed] = useState(false);
  const hintId = useId();

  const nameRef = useRef<HTMLInputElement | null>(null);
  const phoneRef = useRef<HTMLInputElement | null>(null);
  const visitRef = useRef<HTMLInputElement | null>(null);
  const alertRef = useRef<HTMLParagraphElement | null>(null);
  // Required, not decorative: React commits `disabled` asynchronously, and a
  // fast double-tap on iOS fires two clicks inside one frame.
  const sending = useRef(false);

  // The failure-path focus move, as an EFFECT and never a .focus() in the catch:
  // the alert node does not exist yet when setState runs, so the call in the
  // catch would be a no-op on nothing. Button disables itself the instant the
  // request starts, so the browser has already blurred the control she tapped
  // and the sentence she needs would otherwise be nowhere near her focus.
  useEffect(() => {
    if (failures > 0) alertRef.current?.focus();
  }, [failures]);

  const send = async (type: VisitType) => {
    sending.current = true;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const ticket = await api.createCheckin({
        name,
        phone: normalizePhone(phone),
        visit_type: type,
        marketing_opt_in: optIn,
      });
      // Every successful create OVERWRITES the pointer, so it always names the
      // most recent check-in from this tab. The ticket id and nothing else — no
      // phone number is ever stored on the device.
      writeCheckinTicket(ticket.id);
      navigate(`/q/${encodeURIComponent(ticket.id)}`);
    } catch (failure: unknown) {
      // The throttle gets its OWN copy. The shared errors.tooManyAttempts says
      // "try again in a moment" and the create budget's window is an hour, so
      // that sentence would be a lie — and the 429 body carries no duration for
      // it to be honest with.
      setSubmitError(
        errorMessageKey(failure) === "errors.tooManyAttempts"
          ? t("checkin.budgetSpent")
          : errorMessageOr(failure, t, "checkin.createFailed"),
      );
      setFailures((n) => n + 1);
    } finally {
      sending.current = false;
      setSubmitting(false);
    }
  };

  // Errors surface HERE and nowhere else — not on blur, which fires the moment
  // she tabs out of a field she means to come back to, and not on input, which
  // calls her name required before she has finished the first letter. Every
  // validator runs, every failure renders, focus lands on the first one, and no
  // request is issued.
  const forward = () => {
    if (sending.current) return;
    const nameError = validateName(name);
    const phoneError = validatePhone(phone);
    setFieldErrors({
      name: nameError ?? undefined,
      phone: phoneError ?? undefined,
      visitType: visitType === null ? t("checkin.visitTypeRequired") : undefined,
    });
    if (nameError !== null) {
      nameRef.current?.focus();
      return;
    }
    if (phoneError !== null) {
      phoneRef.current?.focus();
      return;
    }
    if (visitType === null) {
      visitRef.current?.focus();
      return;
    }
    void send(visitType);
  };

  if (loading) {
    return (
      <div className={pageClass}>
        <Heading />
        {/* A visually-hidden status region, because aria-busy on a plain div is
            announced by neither VoiceOver nor NVDA. */}
        <VisuallyHidden>
          <span role="status">{t("checkin.loading")}</span>
        </VisuallyHidden>
        <Skeleton variant="text" lines={3} />
        <Skeleton variant="text" lines={3} />
      </div>
    );
  }

  // THE FORM IS WITHHELD IN BOTH DEGRADED ARMS, and that is a privacy
  // requirement rather than polish. Both gated strings interpolate the data
  // controller's name from the layout's single fetch, and a collection notice
  // with a hole where the controller belongs is not the notice Amendment 13
  // requires. No form, no collection point, nothing to give notice about.
  if (boutique === null) {
    return (
      <div className={pageClass}>
        <Heading />
        <p role="alert" className="max-w-[60ch] text-base text-ink-muted">
          {errorMessageOr(boutiqueError, t, "checkin.boutiqueUnavailable")}
        </p>
        <div className="flex">
          <Button variant="secondary" size="md" fullWidthMobile onClick={retry}>
            {t("checkin.retry")}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className={pageClass}>
      <Heading />

      {/* An OFFER, above the form, never a redirect. A mount-time navigation
          would be a context change she did not request — and on a shared phone,
          into someone else's ticket. The form below stays fully usable. */}
      {pointer !== null && (
        <p className="text-base">
          <Link
            to={`/q/${encodeURIComponent(pointer)}`}
            className="rounded-sm text-gold-text underline"
          >
            {t("checkin.lastFromDevice")}
          </Link>
        </p>
      )}

      {/* F60's orientation hint, as the APG DISCLOSURE and nothing more:
          `aria-expanded` announces the state and the reader's very next item IS
          the hint, because the <p> follows the button in DOM order.

          ⚠ NO ref, NO effect, NO onKeyDown, NO Esc handler, NO focus move, and
          this is the THIRD deck to decline `ManageBookingPage`'s reveal-focus
          move. (1) That file has no Esc handler anywhere — its close is a ghost
          «ביטול» at :469-483 — and an Esc handler is only needed BECAUSE focus
          moved. (2) That move is the only frontend entry on LOOP-STATE's
          `known_flaky` list and has already parked a green PR. (3) There is
          nothing to move focus TO: this reveals one sentence with nothing
          focusable in it, and a tabIndex={-1} paragraph is a destination
          invented so an Esc handler has something to close from.

          ⚠ `aria-controls` is CONDITIONAL: while collapsed the <p> does not
          exist, and a dangling IDREF is what axe reports as
          `aria-valid-attr-value` (`A11yMenu.tsx:120-122`'s reason).

          ⚠ THE CONTENT FENCE IS POSITIVE AND LOAD-BEARING ON GATE 1. The hint
          names THE QUEUE and only the queue. `checkin.notice` below is the
          notice AT THE MOMENT OF COLLECTION, always visible and never behind a
          disclosure; a collapsed «מה קורה עם הפרטים שלי?» beside it would be a
          second, unapproved notice at the same collection point.

          Below the recovery offer and above the first field: an orientation hint
          above a live «resume your ticket» link would bury the more useful
          control. `size="md"` (min-h-11), matching the retry, the submit and the
          chips' explicit min-h-11 min-w-11 — a public phone surface with a 44px
          floor F60 does not lower. */}
      <div className="flex">
        <Button
          variant="ghost"
          size="md"
          aria-expanded={hintRevealed}
          aria-controls={hintRevealed ? hintId : undefined}
          onClick={() => {
            setHintRevealed(!hintRevealed);
          }}
        >
          {t("checkin.guideTrigger")}
        </Button>
      </div>
      {hintRevealed && (
        <p id={hintId} className="max-w-[60ch] text-base text-ink-muted">
          {t("checkin.guideHint")}
        </p>
      )}

      <Input
        ref={nameRef}
        label={t("checkin.name")}
        value={name}
        error={fieldErrors.name}
        onChange={(event) => {
          setName(event.target.value);
        }}
      />

      <Input
        ref={phoneRef}
        label={t("checkin.phone")}
        type="tel"
        inputMode="tel"
        autoComplete="tel"
        value={phone}
        help={t("checkin.phoneHint")}
        error={fieldErrors.phone}
        onChange={(event) => {
          setPhone(event.target.value);
        }}
      />

      <VisitTypePicker
        ref={visitRef}
        value={visitType}
        onChange={setVisitType}
        error={fieldErrors.visitType}
      />

      {/* The notice sits ABOVE the box it describes, and is never behind a
          disclosure: notice at the moment of collection means visible at the
          moment of collection. Both strings are counsel-gated in he.ts; nothing
          here may hardcode any part of either. */}
      <p className="max-w-[60ch] text-sm text-ink-muted">
        {t("checkin.notice", { boutique: boutique.name })}
      </p>

      {/* UNBUNDLED, and a native checkbox rather than a Toggle: a legal consent
          announces checked/unchecked, and role="switch" announces on/off. */}
      <Checkbox
        label={t("checkin.optIn", { boutique: boutique.name })}
        checked={optIn}
        onCheckedChange={setOptIn}
      />

      <div className="flex">
        <Button
          variant="primary"
          size="md"
          fullWidthMobile
          loading={submitting}
          onClick={forward}
        >
          {t("checkin.submit")}
        </Button>
      </div>

      {submitError !== null && (
        <p ref={alertRef} tabIndex={-1} role="alert" className="max-w-[60ch] text-base text-danger">
          {submitError}
        </p>
      )}

      <VisuallyHidden>
        <span role="status">{submitting ? t("checkin.submitting") : ""}</span>
      </VisuallyHidden>
    </div>
  );
}
