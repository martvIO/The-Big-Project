import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Button, Card, Input, JERusalem, VisuallyHidden } from "@boutique/ui";
import { api, errorMessageKey } from "../../api";
import type { BoutiqueResponse } from "../../api";
import { substituteBoutique } from "../../lib/privacyText";
import { normalizePhone, validatePhone } from "../../validation";
import { ContactCard } from "../ContactCard";

// F22's CTA + inline reveal for the full-day state (design §1-3). Inline
// expand — no Modal, no route change, the flow's step machinery untouched.
//
// ⚠ The OTP block is the verify step's, COPIED not re-derived (design §0):
// single code field, autocomplete="one-time-code", dir="ltr" content with RTL
// labels, 60s resend cooldown, client send-budget mirror, ONE label for first
// send and resend, digits-only input, no auto-submit on the sixth digit.
//
// ⚠ F-W3 lives at the CALL SITE: BookPage keys this component on
// `${date}:${typeId}`, so a date or type change REMOUNTS it — collapsing the
// reveal and clearing codeSent/token by construction, so a stale token for the
// old day cannot survive into a new reveal. Nothing here needs to watch props.

// Past the p95 of Israeli SMS delivery — the verify step's own constant,
// duplicated because BookPage does not export it and a shared module for two
// integers is more code than the risk it retires.
const OTP_RESEND_COOLDOWN_MS = 60_000;
// Mirrors otp_send_max_per_phone_window: past this count every press would be
// a "code sent" that is simply false (the server answers a spent personal
// budget with the same silent 204), so the exit is honest instead.
const OTP_SEND_BUDGET = 5;

// The boutique's calendar, never the device's — the confirmation names the day
// she asked about, and noon UTC is the same Jerusalem calendar day everywhere.
const CONFIRM_WEEKDAY = new Intl.DateTimeFormat("he-IL", {
  timeZone: JERusalem,
  weekday: "long",
});
const CONFIRM_DATE = new Intl.DateTimeFormat("he-IL", {
  timeZone: JERusalem,
  day: "numeric",
  month: "numeric",
  year: "numeric",
});

// i18next replaces a MISSING {{date}} with "" (and warns), so the split rides a
// sentinel: the interpolated NUL can never appear in Hebrew copy, and splitting
// on it is what lets the date live inside a <bdi dir="ltr"> island (R19) —
// which plain interpolation cannot carry.
const DATE_SENTINEL = "\u0000";

interface WaitlistJoinProps {
  /** YYYY-MM-DD, the picked Jerusalem day the entry binds to. */
  day: string;
  typeId: string;
  boutique: BoutiqueResponse | null;
}

export function WaitlistJoin({ day, typeId, boutique }: WaitlistJoinProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [phone, setPhone] = useState("");
  const [phoneError, setPhoneError] = useState<string | undefined>(undefined);
  const [code, setCode] = useState("");
  const [codeError, setCodeError] = useState<string | undefined>(undefined);
  const [codeSentFor, setCodeSentFor] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [sends, setSends] = useState(0);
  const [sending, setSending] = useState(false);
  const [cooling, setCooling] = useState(false);
  const [joining, setJoining] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [stepAlert, setStepAlert] = useState<{ key: string; contact: boolean } | null>(null);
  const [polite, setPolite] = useState<string | null>(null);

  const phoneRef = useRef<HTMLInputElement | null>(null);
  const codeRef = useRef<HTMLInputElement | null>(null);
  const confirmedRef = useRef<HTMLParagraphElement | null>(null);
  // The house focus rule: the mover is the state change that mounted the
  // target. Held as an intent and consumed when the target exists, so a
  // resolve landing while she is typing cannot steal focus mid-edit
  // (BookPage's own WCAG 3.2.2 note, in miniature).
  const pendingFocus = useRef<"phone" | "code" | null>(null);

  const normalizedPhone = normalizePhone(phone);
  const codeSent = codeSentFor !== null && codeSentFor === normalizedPhone;

  useEffect(() => {
    if (!cooling) return;
    const timer = setTimeout(() => {
      setCooling(false);
    }, OTP_RESEND_COOLDOWN_MS);
    return () => {
      clearTimeout(timer);
    };
  }, [cooling]);

  useEffect(() => {
    if (pendingFocus.current === "phone" && open) {
      pendingFocus.current = null;
      phoneRef.current?.focus();
    }
    if (pendingFocus.current === "code" && codeSent) {
      pendingFocus.current = null;
      codeRef.current?.focus();
    }
  });

  useEffect(() => {
    if (confirmed) confirmedRef.current?.focus();
  }, [confirmed]);

  const send = async () => {
    const invalid = validatePhone(phone);
    if (invalid !== null) {
      setPhoneError(invalid);
      return;
    }
    setPhoneError(undefined);
    // Her own budget is spent, and the server would say so by saying nothing —
    // the honest exit is the phone (the verify step's dead-end shape).
    if (sends >= OTP_SEND_BUDGET) {
      setStepAlert({ key: "errors.otpSendBudget", contact: true });
      return;
    }
    setStepAlert(null);
    setSending(true);
    setPolite("waitlist.sending");
    try {
      await api.sendOtp(normalizedPhone);
      setSends((n) => n + 1);
      setCodeSentFor(normalizedPhone);
      setCode("");
      setCodeError(undefined);
      setToken(null);
      setCooling(true);
      pendingFocus.current = "code";
    } catch (error: unknown) {
      const key = errorMessageKey(error);
      if (key === "errors.tooManyAttempts") {
        // The send budget's window is an hour — "try again in a moment" would
        // be a lie that makes her hammer the same 429.
        setStepAlert({ key: "errors.otpSendBudget", contact: true });
      } else if (key === "errors.smsUnavailable") {
        setStepAlert({ key, contact: true });
      } else {
        setStepAlert({ key: "errors.unknown", contact: false });
      }
    }
    setPolite(null);
    setSending(false);
  };

  const join = async () => {
    // Required, not decorative: React commits `disabled` asynchronously, and a
    // fast double-tap fires two clicks inside one frame.
    if (joining) return;
    setJoining(true);
    setStepAlert(null);
    setCodeError(undefined);
    setPolite("waitlist.joining");

    let current = token;
    if (current === null) {
      try {
        const session = await api.verifyOtp(normalizedPhone, code);
        current = session.verification_token;
        setToken(current);
      } catch (error: unknown) {
        const key = errorMessageKey(error);
        if (key === "errors.otpInvalid" || key === "errors.otpExpired") {
          setCodeError(t(key));
        } else if (key === "errors.tooManyAttempts") {
          setStepAlert({ key, contact: false });
        } else {
          setStepAlert({ key: "errors.unknown", contact: false });
        }
        setPolite(null);
        setJoining(false);
        return;
      }
    }

    try {
      // EXACTLY four keys — the wire contract the test pins by key-set
      // equality. The idempotent duplicate arrives as the same 201: the
      // already-joined state IS the confirmed state, one rendering.
      await api.joinWaitlist({
        phone: normalizedPhone,
        verification_token: current,
        day,
        appointment_type_id: typeId,
      });
      setConfirmed(true);
    } catch (error: unknown) {
      const key = errorMessageKey(error);
      if (key === "errors.phoneNotVerified") {
        // The token is gone, so the code it minted is worthless — collapse to
        // the phone phase with everything else intact.
        setCodeSentFor(null);
        setCode("");
        setToken(null);
        setStepAlert({ key, contact: false });
      } else if (key === "errors.tooManyAttempts" || key === "errors.validation") {
        setStepAlert({ key, contact: false });
      } else {
        setStepAlert({ key: "errors.unknown", contact: false });
      }
      setPolite(null);
    }
    setJoining(false);
  };

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void (codeSent ? join() : send());
  };

  if (confirmed) {
    const instant = new Date(`${day}T12:00:00Z`);
    const dateLabel = `${CONFIRM_WEEKDAY.format(instant)}, ${CONFIRM_DATE.format(instant)}`;
    const [lead, tail] = t("waitlist.confirmed", { date: DATE_SENTINEL }).split(DATE_SENTINEL);
    return (
      <p
        ref={confirmedRef}
        tabIndex={-1}
        role="status"
        data-testid="waitlist-confirmed"
        className="max-w-[60ch] text-lg text-ink"
      >
        {lead}
        <bdi dir="ltr">{dateLabel}</bdi>
        {tail}
      </p>
    );
  }

  if (!open) {
    // Secondary, not primary (design P2): on a full day the honest first
    // advice is still another date or a phone call.
    return (
      <div className="flex">
        <Button
          type="button"
          variant="secondary"
          size="md"
          fullWidthMobile
          onClick={() => {
            pendingFocus.current = "phone";
            setOpen(true);
          }}
        >
          {t("waitlist.cta")}
        </Button>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit}>
      <Card className="flex flex-col gap-6">
        {stepAlert !== null && (
          <div className="flex flex-col gap-4">
            {/* Muted, not danger: a spent budget and a dead provider are not
                her mistake — only what she typed takes the danger colour. */}
            <p role="alert" className="max-w-[60ch] text-base text-ink-muted">
              {t(stepAlert.key)}
            </p>
            {stepAlert.contact &&
              (boutique === null ? (
                <p className="max-w-[60ch] text-base text-ink-muted">
                  {t("booking.contactUnavailable")}
                </p>
              ) : (
                <ContactCard boutique={boutique} />
              ))}
          </div>
        )}

        <Input
          label={t("booking.phone")}
          help={t("booking.phoneHint")}
          type="tel"
          dir="ltr"
          inputMode="tel"
          autoComplete="tel"
          value={phone}
          error={phoneError}
          onChange={(event) => {
            const next = event.target.value;
            setPhone(next);
            setPhoneError(undefined);
            // Typing here means she is driving — a deferred focus move to the
            // code field is stale by definition.
            if (pendingFocus.current === "code") pendingFocus.current = null;
            // Editing away from the number the code was minted for collapses
            // the field. The token is left alone for the verify step's own
            // reason: consume_verification predicates on the phone, so a token
            // minted for A structurally cannot join B.
            if (normalizePhone(next) !== codeSentFor) {
              setCode("");
              setCodeError(undefined);
            }
          }}
          ref={phoneRef}
        />

        {/* The §11 collection-point notice (D4): the SHIPPED text verbatim —
            `boutique.privacy_notice_text`, the same string /privacy and the
            details step render — never an i18n key, never clamped. Above the
            send control: a notice she meets after sending is one she was not
            given. */}
        {boutique !== null && (
          <p
            data-testid="waitlist-privacy-notice"
            className="max-w-[60ch] whitespace-pre-line text-sm text-ink-muted [overflow-wrap:anywhere]"
          >
            {substituteBoutique(boutique.privacy_notice_text, boutique.name)}
          </p>
        )}

        {codeSent && (
          <>
            <span aria-hidden="true" className="h-px bg-border" />
            {/* ONE field — the verify step's shipped conventions, copied. */}
            <Input
              label={t("booking.otpCode")}
              help={t("booking.otpSent")}
              dir="ltr"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              pattern="[0-9]*"
              className="max-w-[10ch]"
              value={code}
              error={codeError}
              onChange={(event) => {
                setCode(event.target.value.replace(/\D/g, "").slice(0, 6));
                setCodeError(undefined);
              }}
              ref={codeRef}
            />
          </>
        )}

        <div className="flex flex-col gap-3 md:flex-row-reverse md:justify-start">
          {codeSent && (
            <Button type="submit" variant="primary" size="lg" fullWidthMobile loading={joining}>
              {t("waitlist.join")}
            </Button>
          )}
          {/* One label for the first send and the resend; while cooling the
              label IS the explanation — `disabled` drops the control from the
              tab order, which makes any description on it inert. */}
          <Button
            type={codeSent ? "button" : "submit"}
            variant={codeSent ? "secondary" : "primary"}
            size="md"
            fullWidthMobile
            loading={sending}
            disabled={cooling || joining}
            onClick={codeSent ? () => void send() : undefined}
          >
            {t(cooling ? "waitlist.sendWait" : "waitlist.send")}
          </Button>
        </div>

        <VisuallyHidden>
          <span role="status">{polite === null ? "" : t(polite)}</span>
        </VisuallyHidden>
      </Card>
    </form>
  );
}
