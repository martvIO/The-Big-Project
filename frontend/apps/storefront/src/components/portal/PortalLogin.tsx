import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Button, Card, Input, VisuallyHidden } from "@boutique/ui";
import { api, errorMessageKey } from "../../api";
import type { BoutiqueResponse } from "../../api";
import { normalizePhone, validatePhone } from "../../validation";
import { ContactCard } from "../ContactCard";
import { PortalEmpty } from "./PortalEmpty";

// F24's login panel (design §2).
//
// ⚠ The OTP block is the verify step's, COPIED not re-derived — the same ruling
// WaitlistJoin §0 took, for the same reason: single code field (never six
// boxes), autocomplete="one-time-code", dir="ltr" content with RTL labels, 60s
// resend cooldown, client send-budget mirror, ONE label for the first send and
// the resend, digits-only, and no auto-submit on the sixth digit.
//
// ⚠ «כניסה» CHAINS verify + mint on one click (design P1). Two API calls, one
// gesture: a separate "verify" then "enter" pair would make her tap twice for
// one decision. The held `token` is what makes E7 honest — a 429 on the MINT
// leaves the verification unspent, so retrying re-fires the mint alone and
// never a second verify against a burned code.

const OTP_RESEND_COOLDOWN_MS = 60_000;
// Mirrors otp_send_max_per_phone_window. Past this every press would be a "code
// sent" that is simply false — the server answers a spent personal budget with
// the same silent 204 — so the exit is the phone instead.
const OTP_SEND_BUDGET = 5;

interface PortalLoginProps {
  boutique: BoutiqueResponse | null;
  /** Rendered above the card as a muted fact — session expiry, never a fault. */
  notice?: string | null;
  onSignedIn: (customerName: string) => void;
}

export function PortalLogin({ boutique, notice = null, onSignedIn }: PortalLoginProps) {
  const { t } = useTranslation();
  const [phone, setPhone] = useState("");
  const [phoneError, setPhoneError] = useState<string | undefined>(undefined);
  const [code, setCode] = useState("");
  const [codeError, setCodeError] = useState<string | undefined>(undefined);
  const [codeSentFor, setCodeSentFor] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [sends, setSends] = useState(0);
  const [sending, setSending] = useState(false);
  const [cooling, setCooling] = useState(false);
  const [signingIn, setSigningIn] = useState(false);
  // State N: the phone is verified and this boutique has no bookings for it.
  const [noBookings, setNoBookings] = useState(false);
  // `deadEnd` REPLACES the form (E5-send / E6); `stepLine` sits inside it (E1,
  // E2, E3, E5-verify, E7). The split is booking.md's blame rule: only what she
  // typed renders danger, and only a spent send budget or a dead provider takes
  // the form away.
  const [deadEnd, setDeadEnd] = useState<string | null>(null);
  const [stepLine, setStepLine] = useState<string | null>(null);
  const [polite, setPolite] = useState<string | null>(null);

  const codeRef = useRef<HTMLInputElement | null>(null);
  const deadEndRef = useRef<HTMLDivElement | null>(null);
  const pendingFocus = useRef<"code" | "deadEnd" | null>(null);

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

  // The house focus rule: the mover is the state change that mounted the
  // target, and the intent is held until that render actually commits it.
  useEffect(() => {
    if (pendingFocus.current === "code" && codeSent) {
      pendingFocus.current = null;
      codeRef.current?.focus();
    }
    if (pendingFocus.current === "deadEnd" && deadEnd !== null) {
      pendingFocus.current = null;
      deadEndRef.current?.focus();
    }
  });

  const send = async () => {
    const invalid = validatePhone(phone);
    if (invalid !== null) {
      setPhoneError(invalid);
      return;
    }
    setPhoneError(undefined);
    if (sends >= OTP_SEND_BUDGET) {
      // E4's honest exit. Her own budget is spent and the server would say so
      // by saying nothing.
      setDeadEnd("errors.otpSendBudget");
      pendingFocus.current = "deadEnd";
      return;
    }
    setStepLine(null);
    setSending(true);
    setPolite("portal.sending");
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
      if (key === "errors.tooManyAttempts" || key === "errors.smsUnavailable") {
        // E5-send and E6: the window is an hour and a dead provider is dead —
        // "try again in a moment" would be a lie that makes her hammer it.
        setDeadEnd(key === "errors.tooManyAttempts" ? "errors.otpSendBudget" : key);
        pendingFocus.current = "deadEnd";
      } else {
        setStepLine("errors.unknown");
      }
    }
    setPolite(null);
    setSending(false);
  };

  const signIn = async () => {
    // Required, not decorative: React commits `disabled` asynchronously and a
    // fast double-tap fires two clicks inside one frame.
    if (signingIn) return;
    setSigningIn(true);
    setStepLine(null);
    setCodeError(undefined);
    setPolite("portal.loggingIn");

    let current = token;
    if (current === null) {
      try {
        current = (await api.verifyOtp(normalizedPhone, code)).verification_token;
        setToken(current);
      } catch (error: unknown) {
        const key = errorMessageKey(error);
        // E1 / E2 — she typed it, so it renders as a field error in danger.
        if (key === "errors.otpInvalid" || key === "errors.otpExpired") {
          setCodeError(t(key));
        } else {
          // E5-verify: the form stays fully intact, because that window is
          // short and self-clearing.
          setStepLine(key === "errors.tooManyAttempts" ? key : "errors.unknown");
        }
        setPolite(null);
        setSigningIn(false);
        return;
      }
    }

    try {
      const session = await api.portalLogin({
        phone: normalizedPhone,
        verification_token: current,
      });
      onSignedIn(session.customer_name);
    } catch (error: unknown) {
      const key = errorMessageKey(error);
      if (key === "errors.portalNoBookings") {
        // State N. The SAME screen the empty dashboard renders (design P2):
        // "this phone has no bookings here" must look identical however she
        // reached it, or the difference is an enumeration surface.
        setNoBookings(true);
      } else if (key === "errors.phoneNotVerified") {
        // ⚠ F-P1: `portal.verifyExpired`, NEVER `errors.phoneNotVerified` —
        // that row's tail ("הפרטים שמילאת נשמרו") is booking-flow-specific and
        // there is no form here to have saved. The code the dead token minted
        // is worthless, so the panel collapses to the phone phase.
        setCodeSentFor(null);
        setCode("");
        setToken(null);
        setStepLine("portal.verifyExpired");
      } else if (key === "errors.tooManyAttempts") {
        // E7: the tenant's mint brake, not her mistake and not her typing. The
        // form stays intact and `token` is UNSPENT, so pressing כניסה again
        // re-fires the mint alone.
        setStepLine(key);
      } else {
        setStepLine("errors.unknown");
      }
      setPolite(null);
    }
    setSigningIn(false);
  };

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void (codeSent ? signIn() : send());
  };

  if (noBookings) return <PortalEmpty />;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3">
        <h1 className="font-display text-2xl text-ink">{t("portal.loginTitle")}</h1>
        <span aria-hidden="true" className="h-px w-12 bg-gold" />
      </div>

      {/* State X. Muted and announced through the status region — a fact about
          a session that ended, not a fault of hers. */}
      {notice !== null && (
        <p className="max-w-[60ch] text-base text-ink-muted">{t(notice)}</p>
      )}

      {deadEnd !== null ? (
        // E5-send / E6: the block REPLACES the form. No role="alert" — it is
        // reached BY the focus move, which is the booking dead-end ruling, and
        // announcing it twice is worse than once.
        <div ref={deadEndRef} tabIndex={-1} className="flex flex-col gap-4">
          <p className="max-w-[60ch] text-base text-ink-muted">{t(deadEnd)}</p>
          {boutique === null ? (
            <p className="max-w-[60ch] text-base text-ink-muted">
              {t("booking.contactUnavailable")}
            </p>
          ) : (
            <ContactCard boutique={boutique} />
          )}
        </div>
      ) : (
        <form onSubmit={onSubmit}>
          <Card className="flex flex-col gap-6">
            <p className="max-w-[60ch] text-base text-ink">{t("portal.loginIntro")}</p>

            {stepLine !== null && (
              // Muted, never danger: nothing here is something she typed.
              <p role="alert" className="max-w-[60ch] text-base text-ink-muted">
                {t(stepLine)}
              </p>
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
                if (pendingFocus.current === "code") pendingFocus.current = null;
                // Editing away from the number the code was minted for
                // collapses the code field AND clears the held token: this
                // panel's token is the credential for a MINT keyed on the
                // phone, so carrying it across an edit is carrying a
                // credential for somebody else's number.
                if (normalizePhone(next) !== codeSentFor) {
                  setCode("");
                  setCodeError(undefined);
                  setToken(null);
                }
              }}
            />

            {codeSent && (
              <>
                <span aria-hidden="true" className="h-px bg-border" />
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
                <Button
                  type="submit"
                  variant="primary"
                  size="lg"
                  fullWidthMobile
                  loading={signingIn}
                >
                  {t("portal.loginSubmit")}
                </Button>
              )}
              {/* ONE label for the first send and the resend. While cooling the
                  label IS the explanation — `disabled` drops the control from
                  the tab order, which makes any description on it inert. */}
              <Button
                type={codeSent ? "button" : "submit"}
                variant={codeSent ? "secondary" : "primary"}
                size="md"
                fullWidthMobile
                loading={sending}
                disabled={cooling || signingIn}
                onClick={codeSent ? () => void send() : undefined}
              >
                {t(cooling ? "booking.otpResendWait" : "booking.otpResend")}
              </Button>
            </div>
          </Card>
        </form>
      )}

      {/* R30's nested shape: aria-busy on a plain div is announced by neither
          VoiceOver nor NVDA. */}
      <VisuallyHidden>
        <span role="status">{polite === null ? "" : t(polite)}</span>
      </VisuallyHidden>
    </div>
  );
}
