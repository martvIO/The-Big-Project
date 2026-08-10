import { Button, ButtonLink, Card, Input, Skeleton, VisuallyHidden } from "@boutique/ui";
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ApiError, api } from "../api";
import type { BookingCreateResponse, StorefrontTerms, WaitlistOfferView } from "../api";
import { ContactCard } from "../components/ContactCard";
import { useBoutique } from "../components/StorefrontLayout";
import { DATE, TIME, WEEKDAY } from "../components/booking/BookingFacts";
import { TermsConsent } from "../components/booking/TermsConsent";
import { handOff } from "../router";

// F23's tokenized offer page. `/b/{token}`'s sibling and NOT a flow: she arrived
// from a text message, so there is no stepper, no progress and no back-to-step-
// one. Facts first, actions second, boutique contact last, same reading column.
//
// ⚠ R1 — THERE IS NO COUNTDOWN ON THIS PAGE AND THERE MUST NEVER BE ONE.
// The spec asked for one; the design deck removed it over three prior rulings
// and a legal gate. What ships is ONE STATIC ABSOLUTE JERUSALEM TIME: it never
// subtracts, so it is immune to a phone's clock drift, it is readable off a
// screenshot, and it is the same value the SMS already carried.
//
// It is also the SC 2.2.1 audit answer. The offer has a time limit, but NOTHING
// on this page auto-updates — no counter, no poll, no re-render — so the limit
// is a server-side business deadline, essential to the activity (exception (e)),
// stated in advance and in absolute terms, and non-destructive when missed: the
// slot returns to the pool and she may book it directly or rejoin. Add a timer
// and that paragraph stops being true.
const pageClass = "mx-auto flex max-w-[640px] flex-col gap-6 px-4 pt-8 pb-16 md:px-6";

const OFFERED = "offered";
const CLAIMED = "claimed";
const EXPIRED = "expired";
const CANCELLED = "cancelled";

// What the page is showing. Derived from the SERVER's answer, never from what a
// tap hoped for — the `manage` page's rule, and here it is what makes design
// F-O2 correct rather than a bug: a claim that loses the seat race leaves the
// entry `offered`, so a reload re-renders the LIVE offer.
type View =
  | { kind: "loading" }
  | { kind: "loaded"; offer: WaitlistOfferView; terms: StorefrontTerms | null }
  // The token is unknown, dead, or another boutique's — ONE indistinguishable
  // state, no oracle.
  | { kind: "invalid" }
  | { kind: "failed" }
  // 201. `booking` carries the deposit hand-off when one is owed.
  | { kind: "claimed"; booking: BookingCreateResponse }
  | { kind: "declined" };

export function OfferPage({ token }: { token: string }) {
  const { t } = useTranslation();
  // The offer payload deliberately carries NO boutique block (backend
  // `WaitlistOfferResponse`) — the layout already resolved it from the host, so
  // the contact card reads it from there rather than from a second copy.
  const { boutique, loading: boutiqueLoading } = useBoutique();
  const [view, setView] = useState<View>({ kind: "loading" });
  const [name, setName] = useState("");
  const [accepted, setAccepted] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const [busy, setBusy] = useState<"claim" | "decline" | null>(null);
  const [fieldError, setFieldError] = useState<{ name?: string; accept?: string }>({});
  // The one-line error ABOVE the form — a lost race, stale terms, a throttle.
  // Not a field error: none of them is about something she typed.
  const [formError, setFormError] = useState<string | null>(null);
  // Written on DISCRETE events only (R16): claiming, claimed, declined, gone.
  // Never on a keystroke and never per render.
  const [announced, setAnnounced] = useState<string | null>(null);

  const revealRef = useRef<HTMLParagraphElement | null>(null);
  const declineTriggerRef = useRef<HTMLButtonElement | null>(null);
  const claimedRef = useRef<HTMLParagraphElement | null>(null);
  const declinedRef = useRef<HTMLParagraphElement | null>(null);
  const goneRef = useRef<HTMLParagraphElement | null>(null);
  const moveFocusTo = useRef<"claimed" | "declined" | "gone" | "reveal" | "trigger" | null>(null);

  const load = useCallback(async () => {
    setView({ kind: "loading" });
    try {
      const offer = await api.lookupOffer(token);
      // The policy comes from the SHIPPED /storefront/terms read, exactly as
      // /book/terms gets it — this page publishes no second copy of the legal
      // text and no second version number.
      const terms = offer.status === OFFERED ? await api.getTerms().catch(() => null) : null;
      setView({ kind: "loaded", offer, terms });
    } catch (error: unknown) {
      // Branch on the CODE here rather than through the shared error map: a dead
      // link is a page STATE with its own copy, not one more sentence.
      setView(error instanceof ApiError && error.status === 404 ? { kind: "invalid" } : { kind: "failed" });
    }
  }, [token]);

  useEffect(() => {
    void load();
  }, [load]);

  // No dep array, and the clear is CONDITIONAL on having a node — the
  // ManageBookingPage hazard verbatim. React runs passive effects after paint,
  // so a render committing between the tap and this flush arrives while the
  // target is still unmounted; clearing there LOSES the move permanently rather
  // than delaying it, and focus drops to <body> (WCAG 2.4.3).
  useEffect(() => {
    const intent = moveFocusTo.current;
    if (intent === null) return;
    const target =
      intent === "claimed"
        ? claimedRef.current
        : intent === "declined"
          ? declinedRef.current
          : intent === "gone"
            ? goneRef.current
            : intent === "reveal"
              ? revealRef.current
              : declineTriggerRef.current;
    if (target === null) return;
    target.focus();
    moveFocusTo.current = null;
  });

  const claim = async (terms: StorefrontTerms) => {
    const trimmed = name.trim();
    const errors: { name?: string; accept?: string } = {};
    if (trimmed === "") errors.name = t("booking.nameRequired");
    if (!accepted) errors.accept = t("booking.acceptRequired");
    setFieldError(errors);
    if (Object.keys(errors).length > 0) return;

    setBusy("claim");
    setFormError(null);
    setAnnounced(t("offer.claiming"));
    try {
      const booking = await api.claimOffer({
        token,
        name: trimmed,
        terms_version: terms.version,
      });
      setAnnounced(t("offer.claimed"));
      moveFocusTo.current = "claimed";
      setView({ kind: "claimed", booking });
      // §2.2 — F19's SHIPPED hand-off, verbatim. Once she leaves for the hosted
      // page, /book/pay's polling surface owns every state after it; this page
      // is not re-entered and must not try to be a second checkout.
      if (booking.redirect_url !== null) handOff.leave(booking.redirect_url);
    } catch (error: unknown) {
      if (error instanceof ApiError && error.code === "TERMS_STALE") {
        // The boutique republished while she was reading. Clear the tick — a
        // box ticked against a superseded policy is not consent — and re-render
        // the current one.
        setAccepted(false);
        setFormError(t("errors.termsStale"));
        void load();
      } else if (error instanceof ApiError && error.code === "SLOT_UNAVAILABLE") {
        // F-O2: the entry is STILL `offered` — the claim's transaction rolled
        // back — so a reload deliberately re-renders the live offer until the
        // deadline passes. Correct, and not to be "fixed" client-side.
        setFormError(t("offer.gone"));
        setAnnounced(t("offer.gone"));
        moveFocusTo.current = "gone";
      } else if (error instanceof ApiError && error.status === 404) {
        setView({ kind: "invalid" });
      } else {
        setFormError(
          error instanceof ApiError && error.status === 429
            ? t("errors.tooManyAttempts")
            : t("errors.unknown"),
        );
      }
    } finally {
      setBusy(null);
    }
  };

  const decline = async () => {
    setBusy("decline");
    setFormError(null);
    try {
      await api.declineOffer(token);
      setAnnounced(t("offer.declined"));
      moveFocusTo.current = "declined";
      setView({ kind: "declined" });
    } catch (error: unknown) {
      setFormError(
        error instanceof ApiError && error.status === 429
          ? t("errors.tooManyAttempts")
          : t("errors.unknown"),
      );
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className={pageClass}>
      <div className="flex flex-col gap-2">
        <h1 className="font-display text-2xl text-ink">{t("offer.title")}</h1>
        <span aria-hidden="true" className="h-px w-12 bg-gold" />
      </div>

      <VisuallyHidden>
        <span role="status">{announced ?? ""}</span>
      </VisuallyHidden>

      {view.kind === "loading" && (
        <Card className="flex flex-col gap-4">
          <VisuallyHidden>
            <span role="status">{t("offer.loading")}</span>
          </VisuallyHidden>
          <Skeleton className="h-6 w-2/3" />
          <Skeleton className="h-6 w-1/2" />
        </Card>
      )}

      {view.kind === "invalid" && (
        <>
          <p className="text-lg text-ink">{t("manage.invalid")}</p>
          <p className="text-base text-ink-muted">{t("manage.invalidHint")}</p>
        </>
      )}

      {view.kind === "failed" && (
        <>
          <p role="alert" className="text-lg text-ink">
            {t("manage.loadFailed")}
          </p>
          <Button variant="secondary" size="md" fullWidthMobile onClick={() => void load()}>
            {t("manage.retry")}
          </Button>
        </>
      )}

      {view.kind === "loaded" && <OfferBody
        offer={view.offer}
        terms={view.terms}
        name={name}
        accepted={accepted}
        revealed={revealed}
        busy={busy}
        fieldError={fieldError}
        formError={formError}
        goneRef={goneRef}
        revealRef={revealRef}
        declineTriggerRef={declineTriggerRef}
        onName={(next) => {
          setName(next);
          setFieldError((current) => ({ ...current, name: undefined }));
        }}
        onAccepted={(next) => {
          setAccepted(next);
          setFieldError((current) => ({ ...current, accept: undefined }));
        }}
        onClaim={claim}
        onReveal={() => {
          setRevealed(true);
          moveFocusTo.current = "reveal";
        }}
        onKeep={() => {
          setRevealed(false);
          moveFocusTo.current = "trigger";
        }}
        onDecline={() => void decline()}
      />}

      {view.kind === "claimed" && (
        <>
          <OfferFacts
            startsAt={view.booking.starts_at}
            appointmentTypeName={view.booking.appointment_type_name}
          />
          {view.booking.deposit_due ? (
            <>
              <p ref={claimedRef} tabIndex={-1} role="status" className="text-lg text-ink">
                {t("booking.payHandoff")}
              </p>
              <p className="text-base text-ink-muted">{t("booking.payManualHint")}</p>
              {view.booking.redirect_url !== null && (
                <ButtonLink href={view.booking.redirect_url} variant="primary" size="lg" fullWidthMobile>
                  {t("booking.payManualCta")}
                </ButtonLink>
              )}
            </>
          ) : (
            <p ref={claimedRef} tabIndex={-1} role="status" className="text-lg text-ink">
              {t("offer.claimed")}
            </p>
          )}
        </>
      )}

      {view.kind === "declined" && (
        <>
          <p ref={declinedRef} tabIndex={-1} role="status" className="text-lg text-ink">
            {t("offer.declined")}
          </p>
          <p className="text-base text-ink-muted">{t("offer.pickAnotherHint")}</p>
          <ButtonLink href="/book/slot" variant="secondary" size="md" fullWidthMobile>
            {t("manage.rebookCta")}
          </ButtonLink>
        </>
      )}

      {!boutiqueLoading && boutique !== null && <ContactCard boutique={boutique} />}
    </div>
  );
}

// The facts card — `BookingFacts`'s SHAPE and its REUSED labels (design P2), not
// the component itself: that one takes a `ManageBookingResponse["booking"]` and
// an offer has no booking to give it. One label, one Hebrew, no drift.
function OfferFacts({
  startsAt,
  appointmentTypeName,
}: {
  startsAt: string | null;
  appointmentTypeName: string | null;
}) {
  const { t } = useTranslation();
  if (startsAt === null) return null;
  const when = new Date(startsAt);
  return (
    <Card className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <p className="text-sm font-semibold text-ink-muted">{t("booking.confirmWhen")}</p>
        <p className="text-lg text-ink">
          {WEEKDAY.format(when)}, <bdi dir="ltr">{DATE.format(when)}</bdi>{" "}
          <span aria-hidden="true">·</span> <bdi dir="ltr">{TIME.format(when)}</bdi>
        </p>
      </div>
      {appointmentTypeName !== null && (
        <div className="flex flex-col gap-1">
          <p className="text-sm font-semibold text-ink-muted">{t("booking.confirmWhat")}</p>
          {/* A BARE <bdi>, never dir="ltr" — the type name is owner-authored and
              usually Hebrew, and forcing LTR on Hebrew is itself a bidi defect. */}
          <p className="text-lg text-ink">
            <bdi>{appointmentTypeName}</bdi>
          </p>
        </div>
      )}
    </Card>
  );
}

/**
 * The deadline, as ONE STATIC LINE (R1).
 *
 * The weekday and date are appended only when the deadline is not today —
 * §2's conditional, the page's half of the SMS body's F-O1 guard. At the
 * shipped two-hour window the branch is never taken; it is what makes an
 * owner-raised window safe rather than silently ambiguous.
 */
function DeadlineLine({ expiresAt }: { expiresAt: string }) {
  const { t } = useTranslation();
  const deadline = new Date(expiresAt);
  const today = DATE.format(new Date()) === DATE.format(deadline);
  return (
    <p className="text-base text-ink">
      {t("offer.deadlineLead")}{" "}
      {!today && (
        <>
          {WEEKDAY.format(deadline)}, <bdi dir="ltr">{DATE.format(deadline)}</bdi>{" "}
        </>
      )}
      <bdi dir="ltr">{TIME.format(deadline)}</bdi>
    </p>
  );
}

function OfferBody({
  offer,
  terms,
  name,
  accepted,
  revealed,
  busy,
  fieldError,
  formError,
  goneRef,
  revealRef,
  declineTriggerRef,
  onName,
  onAccepted,
  onClaim,
  onReveal,
  onKeep,
  onDecline,
}: {
  offer: WaitlistOfferView;
  terms: StorefrontTerms | null;
  name: string;
  accepted: boolean;
  revealed: boolean;
  busy: "claim" | "decline" | null;
  fieldError: { name?: string; accept?: string };
  formError: string | null;
  goneRef: React.Ref<HTMLParagraphElement>;
  revealRef: React.Ref<HTMLParagraphElement>;
  declineTriggerRef: React.Ref<HTMLButtonElement>;
  onName: (next: string) => void;
  onAccepted: (next: boolean) => void;
  onClaim: (terms: StorefrontTerms) => void;
  onReveal: () => void;
  onKeep: () => void;
  onDecline: () => void;
}) {
  const { t } = useTranslation();

  if (offer.status === CLAIMED) {
    return (
      <>
        <OfferFacts startsAt={offer.starts_at} appointmentTypeName={offer.appointment_type_name} />
        <p className="text-lg text-ink">{t("offer.claimedReturning")}</p>
        {/* P3: NOT a delivery claim. The provider can be unconfigured, so
            "the link was sent to you" is a promise the product cannot make —
            the phone always works. */}
        <p className="text-base text-ink-muted">{t("manage.invalidHint")}</p>
      </>
    );
  }

  if (offer.status === EXPIRED || offer.status === CANCELLED) {
    return (
      <>
        <p className="text-lg text-ink">
          {t(offer.status === CANCELLED ? "offer.declined" : "offer.expired")}
        </p>
        <p className="text-base text-ink-muted">{t("offer.pickAnotherHint")}</p>
        <ButtonLink href="/book/slot" variant="secondary" size="md" fullWidthMobile>
          {t("manage.rebookCta")}
        </ButtonLink>
      </>
    );
  }

  return (
    <>
      <OfferFacts startsAt={offer.starts_at} appointmentTypeName={offer.appointment_type_name} />
      {offer.expires_at !== null && <DeadlineLine expiresAt={offer.expires_at} />}

      {formError !== null && (
        <p ref={goneRef} tabIndex={-1} role="alert" className="text-base text-warning-text">
          {formError}
        </p>
      )}

      {terms !== null && (
        <TermsConsent
          terms={terms}
          accepted={accepted}
          error={fieldError.accept}
          onAcceptedChange={onAccepted}
        />
      )}

      <Input
        label={t("booking.name")}
        value={name}
        error={fieldError.name}
        onChange={(event) => onName(event.target.value)}
      />

      {/* size="lg" and size="md" — never "sm", which is 36px and fails the 44px
          touch floor the accessibility gate measures. */}
      <Button
        variant="primary"
        size="lg"
        fullWidthMobile
        loading={busy === "claim"}
        onClick={() => {
          if (terms !== null) onClaim(terms);
        }}
      >
        {t("booking.submit")}
      </Button>

      {revealed ? (
        // Escape backs out, the console's own danger-swap behaviour. The reveal
        // is NOT a dialog, so this is not the WCAG requirement — it is that a
        // destructive two-step control a keyboard user cannot dismiss is a trap
        // in practice. onKeep is the SAME path, so the focus return cannot drift
        // between the two ways out.
        <Card
          className="flex flex-col gap-4 bg-surface-raised"
          onKeyDown={(event) => {
            if (event.key === "Escape") onKeep();
          }}
        >
          {/* The focus destination is the QUESTION, so a screen reader hears
              what is being asked rather than an anonymous container. */}
          <p ref={revealRef} tabIndex={-1} className="text-lg text-ink">
            {t("offer.declineQuestion")}
          </p>
          {/* THE LOAD-BEARING SENTENCE (P2). Declining writes `cancelled` — it
              takes her off the day's list entirely, not past one slot. */}
          <p className="text-base text-ink">{t("offer.declineConsequence")}</p>
          <div className="flex flex-col gap-3 sm:flex-row">
            <Button
              variant="danger"
              size="md"
              fullWidthMobile
              loading={busy === "decline"}
              onClick={onDecline}
            >
              {t("offer.declineConfirm")}
            </Button>
            <Button variant="ghost" size="md" fullWidthMobile onClick={onKeep}>
              {t("manage.cancelKeep")}
            </Button>
          </div>
        </Card>
      ) : (
        // The trigger does NOT call the API — one tap must never take a bride
        // off a waitlist she is still holding a live offer on.
        <Button
          variant="secondary"
          size="md"
          fullWidthMobile
          onClick={onReveal}
          ref={declineTriggerRef}
        >
          {t("offer.declineCta")}
        </Button>
      )}
    </>
  );
}
