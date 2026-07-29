import { useEffect, useRef, useState } from "react";
import type { FormEvent, Ref } from "react";
import { useTranslation } from "react-i18next";
import {
  Button,
  Card,
  Checkbox,
  Input,
  JERusalem,
  Skeleton,
  TextArea,
  VisuallyHidden,
  cn,
  focusRing,
} from "@boutique/ui";
import { ApiError, api, errorMessageKey, errorMessageOr } from "../api";
import type {
  AppointmentTypeRow,
  BookingCreateRequest,
  BookingCreateResponse,
  SlotRow,
  StorefrontDetail,
  StorefrontTerms,
} from "../api";
import { ContactCard } from "../components/ContactCard";
import { SizeChips } from "../components/booking/SizeChips";
import { SlotPicker } from "../components/booking/SlotPicker";
import type { SlotTime } from "../components/booking/SlotPicker";
import { TypePicker } from "../components/booking/TypePicker";
import { useBoutique } from "../components/StorefrontLayout";
import { Link, navigate } from "../router";
import type { BookStep } from "../router";
import {
  MAX_BOOKING_NOTES_LENGTH,
  MAX_CUSTOMER_NAME_LENGTH,
  normalizePhone,
  validateName,
  validateNotes,
  validatePhone,
} from "../validation";

// The /book flow's shell plus its first step.
//
// The h1 is the STEP, not the boutique: a step label is a static i18n string,
// so it survives the boutique fetch failing, the terms 404 and every empty list
// by construction, with no fallback path to get wrong. The two no-step degrade
// screens take document.book instead — a step heading above "call us" would
// name a step that is not on the page.
//
// pb-16 (64px) clears the fixed A11yMenu button's 60px footprint, which /book
// carries with no CTA bar beneath it to reserve the space — hasBookingBar() is
// deliberately false here.
const pageClass = "mx-auto flex max-w-[640px] flex-col gap-6 px-4 pt-8 pb-16 md:px-6";

const backLinkClass = cn("self-start rounded-sm text-sm text-gold-text underline", focusRing);

// The stepper's four items in flow order. `confirm` is terminal and outside the
// stepper, which is why there is no fifth label.
const STEP_LABEL_KEYS = {
  slot: "booking.stepSlot",
  details: "booking.stepDetails",
  terms: "booking.stepTerms",
  verify: "booking.stepOtp",
} as const;

const STEPPER_STEPS = ["slot", "details", "terms", "verify"] as const;

// The back control's target, one step at a time, as a real <Link> to a known
// route. Never the browser's history stack: a step reached by a forward out of
// an abandoned flow has no entry behind it that means "the step before".
// `slot` takes booking.backToCatalog instead, and `confirm` is terminal.
const PREVIOUS_STEP: Partial<Record<BookStep, BookStep>> = {
  details: "slot",
  terms: "details",
  verify: "terms",
};

const dotClass = "flex size-6 items-center justify-center rounded-full text-xs";

// Boutique-calendar reads, never the device's: New York is a different calendar
// day from Jerusalem for part of every day, and a slot is the boutique's.
const DATE_PARTS = new Intl.DateTimeFormat("en-CA", {
  timeZone: JERusalem,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});
const TIME_PARTS = new Intl.DateTimeFormat("en-GB", {
  timeZone: JERusalem,
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

function partsOf(formatter: Intl.DateTimeFormat, instant: string): Record<string, string> {
  return Object.fromEntries(
    formatter.formatToParts(new Date(instant)).map((part) => [part.type, part.value]),
  );
}

function jerusalemDate(instant: string): string {
  const parts = partsOf(DATE_PARTS, instant);
  return `${parts.year}-${parts.month}-${parts.day}`;
}

function jerusalemTime(instant: string): string {
  const parts = partsOf(TIME_PARTS, instant);
  return `${parts.hour}:${parts.minute}`;
}

// Past the p95 of Israeli SMS delivery, and four resends still fit inside one
// code's own 300-second life. Renders as a label swap, never as a ticking value.
const OTP_RESEND_COOLDOWN_MS = 60_000;

// The confirmation renders the instant in the BOUTIQUE's zone: a bride whose
// phone clock the airline changed must still read the boutique's time.
// hoursText.ts's ban on locale formatting does not reach this — its stated
// reason is an implicit timezone, and this one is explicit and converts a UTC
// instant that hand-rolling would get wrong.
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

interface EntryData {
  // null = the boutique has published no policy — D5, the phone-only entry.
  terms: StorefrontTerms | null;
  types: AppointmentTypeRow[];
  slots: SlotRow[];
}

// What the flow carries between steps. BookPage keeps its identity across a
// step navigation (the Router renders the same element in the same position),
// so this survives in memory alone — which is the point: the verification
// token, when it joins this object, may never reach any device storage.
interface BookingFlow {
  typeId: string | null;
  startsAt: string | null;
}

// Why the submit sent her back, carried to the step that owns the fix. ONE slot
// is enough: the backend raises one conflict at a time, checked in a fixed
// order, so two of these can never be live together.
type ReturnReason = "slot" | "type" | "size" | "terms" | "dress";

type Binding = Pick<BookingCreateRequest, "dress_id" | "dress_size">;

const NO_BINDING: Binding = { dress_id: null, dress_size: null };

// Inert by design: no item is a link and none is focusable. Completed, current
// and upcoming are told apart by the ✓ glyph, by aria-current plus weight, and
// by the outline dot — three signals, none of them colour alone.
function Stepper({ step }: { step: BookStep }) {
  const { t } = useTranslation();
  const currentIndex = STEPPER_STEPS.findIndex((name) => name === step);

  return (
    <ol aria-label={t("booking.stepsLabel")} className="flex items-start gap-2">
      {STEPPER_STEPS.map((name, index) => {
        const current = index === currentIndex;
        const done = index < currentIndex;
        return (
          <li key={name} className="flex min-w-0 flex-1 flex-col items-center gap-1 text-center">
            <span
              aria-hidden="true"
              className={cn(
                dotClass,
                done && "bg-gold text-ink",
                current && "bg-ink text-bg",
                !done && !current && "border border-border-input bg-surface-raised text-ink-muted",
              )}
            >
              {done ? "✓" : <bdi dir="ltr">{index + 1}</bdi>}
            </span>
            <span
              aria-current={current ? "step" : undefined}
              className={cn("text-xs", current ? "font-semibold text-ink" : "text-ink-muted")}
            >
              {t(STEP_LABEL_KEYS[name])}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

// One sentence, then the contact block — the shape every exit in this flow
// takes. Under D12 the Card and panel are not rendered at all: ContactPanel
// with no channels is a literally empty <div>, so the degrade has to be a
// branch at the call site (AboutPage.tsx is the shipped precedent).
//
// `muted` is the split between the two voices: the entry degrades tell her to
// do something, and the verify dead ends and the cold confirmation report a
// state that is nobody's fault. Deliberately NO role="alert" in either: these
// blocks are reached by a focus move, and the assertive region is reserved for
// errors that appear without one.
function PhoneOnly({
  messageKey,
  muted = false,
  ref,
}: {
  messageKey: string;
  muted?: boolean;
  ref?: Ref<HTMLDivElement>;
}) {
  const { t } = useTranslation();
  const { boutique, loading } = useBoutique();

  return (
    <div ref={ref} tabIndex={-1} className="flex flex-col gap-6">
      <p className={cn("max-w-[60ch] text-base", muted ? "text-ink-muted" : "text-ink")}>
        {t(messageKey)}
      </p>
      {/* Nothing while the boutique read is in flight: flashing "we could not
          load the contact details" at a panel that is about to arrive is worse
          than the small delay. */}
      {loading ? null : boutique === null ? (
        <p className="max-w-[60ch] text-base text-ink-muted">{t("booking.contactUnavailable")}</p>
      ) : (
        <ContactCard boutique={boutique} />
      )}
    </div>
  );
}

// Alone on the last row, inline-end from 768. NEVER disabled and never carrying
// aria-describedby — disabled drops a control from the tab order, which makes a
// description from it unreadable. It submits, and it fails visibly.
function ForwardRow({ onClick }: { onClick: () => void }) {
  const { t } = useTranslation();

  return (
    <div className="flex md:justify-end">
      <Button
        variant="primary"
        size="lg"
        onClick={onClick}
        className="w-full min-w-[140px] md:w-auto"
      >
        {t("booking.continue")}
      </Button>
    </div>
  );
}

interface FieldErrors {
  name?: string;
  size?: string;
  notes?: string;
  accept?: string;
}

export interface BookPageProps {
  step: BookStep;
  dressId?: string;
}

export function BookPage({ step, dressId }: BookPageProps) {
  const { t } = useTranslation();
  const { boutique } = useBoutique();
  const [entry, setEntry] = useState<EntryData | null>(null);
  const [entryError, setEntryError] = useState<unknown>(null);
  const [attempt, setAttempt] = useState(0);
  const [flow, setFlow] = useState<BookingFlow>({ typeId: null, startsAt: null });
  const [pickedDate, setPickedDate] = useState("");
  const [missing, setMissing] = useState<{ type: boolean; time: boolean }>({
    type: false,
    time: false,
  });
  const [name, setName] = useState("");
  const [notes, setNotes] = useState("");
  const [size, setSize] = useState<string | null>(null);
  // The version she accepted, not a boolean. TERMS_STALE replaces the version,
  // and consent to superseded text is exactly what terms_version exists to
  // prevent recording — so the reset is a consequence of the shape, not an
  // effect somebody has to remember to write.
  const [acceptedVersion, setAcceptedVersion] = useState<number | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  // Only ever a decoration on this flow: it names the binding and offers the
  // sizes, and it can drop without stopping a booking.
  const [dress, setDress] = useState<StorefrontDetail | null>(null);
  const [dressGone, setDressGone] = useState(false);
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  // The normalized number the last code was minted for. The sub-state is
  // DERIVED from it rather than stored, which buys the right behaviour for
  // free: editing the number collapses the code field, because a code minted
  // for number A cannot verify number B.
  const [codeSentFor, setCodeSentFor] = useState<string | null>(null);
  // Bearer material, single-use, 600s TTL — memory only. Device storage is
  // banned outright here, and the TTL could not survive a reload anyway.
  const [token, setToken] = useState<string | null>(null);
  const [cooling, setCooling] = useState(false);
  const [sending, setSending] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [phoneError, setPhoneError] = useState<string | undefined>(undefined);
  const [codeError, setCodeError] = useState<string | undefined>(undefined);
  // Above the Card, muted: a spent budget, a dead token and a carrier that lost
  // an SMS are none of them her mistake. `contact` is R13's addition — a failure
  // whose face can last an hour needs a phone number under it.
  const [stepAlert, setStepAlert] = useState<{ key: string; contact: boolean } | null>(null);
  // Replaces the whole form. The only two states with no way forward.
  const [deadEnd, setDeadEnd] = useState<string | null>(null);
  const [returnReason, setReturnReason] = useState<ReturnReason | null>(null);
  // The step's one authored polite region, written by exactly two discrete
  // events: the cooldown ending and the submit starting.
  const [polite, setPolite] = useState<string | null>(null);
  const [booked, setBooked] = useState<BookingCreateResponse | null>(null);
  const typeRef = useRef<HTMLInputElement>(null);
  const timeRef = useRef<HTMLInputElement>(null);
  const nameRef = useRef<HTMLInputElement>(null);
  const sizeRef = useRef<HTMLInputElement>(null);
  const notesRef = useRef<HTMLTextAreaElement>(null);
  const acceptRef = useRef<HTMLInputElement>(null);
  const phoneRef = useRef<HTMLInputElement>(null);
  const codeRef = useRef<HTMLInputElement>(null);
  const deadEndRef = useRef<HTMLDivElement>(null);
  // The three verify-step destinations name themselves before the render that
  // creates them: the code field, the phone field after a collapse and the dead
  // -end block are all mounted BY the state change that decides to focus them,
  // so the move has to wait for the commit.
  const pendingFocus = useRef<"phone" | "code" | "deadEnd" | null>(null);

  // All three fire on flow ENTRY, in parallel: a missing policy is an
  // entry-level decision (D5), and finding it out at the terms step would let
  // her fill two screens before hitting a dead end.
  useEffect(() => {
    let cancelled = false;
    // The 404 is branched HERE, before the shared errorMessageKey helper ever
    // sees it: NOT_FOUND means something else on every other call in this flow,
    // so no shared mapper can discriminate. isNotFound is never called from
    // this flow either — it folds 400 VALIDATION_ERROR into "not found".
    const terms = api.getTerms().catch((error: unknown) => {
      if (error instanceof ApiError && error.status === 404) return null;
      throw error;
    });
    Promise.all([terms, api.listAppointmentTypes(), api.listSlots()])
      .then(([published, types, slots]) => {
        if (!cancelled) setEntry({ terms: published, types, slots: slots.slots });
      })
      .catch((error: unknown) => {
        if (!cancelled) setEntryError(error);
      });
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  // Fires on flow entry too, but in its own effect: §4.7 keeps the name and the
  // notes typeable while this is in flight, so it may never join the Promise.all
  // that gates the slot step.
  useEffect(() => {
    if (dressId === undefined) return;
    let cancelled = false;
    api
      .getDress(dressId)
      .then((detail) => {
        if (!cancelled) setDress(detail);
      })
      // ONE rule for a read that only DECORATES: drop the binding and say so.
      // A 404 and a 5xx are the same outcome here — no blocking alert, no
      // retry, because a failed decoration must never stop a bride booking.
      .catch(() => {
        if (!cancelled) setDressGone(true);
      });
    return () => {
      cancelled = true;
    };
  }, [dressId]);

  useEffect(() => {
    const target = pendingFocus.current;
    if (target === null) return;
    pendingFocus.current = null;
    const node =
      target === "phone"
        ? phoneRef.current
        : target === "code"
          ? codeRef.current
          : deadEndRef.current;
    node?.focus();
    // Selected, never cleared: clearing destroys the evidence of what she typed,
    // and on OTP_EXPIRED the digits were probably right.
    if (node instanceof HTMLInputElement) node.select();
  });

  useEffect(() => {
    if (!cooling) return;
    const timer = setTimeout(() => {
      setCooling(false);
      // Nothing announces on ENTRY into the cooldown — entry is a direct
      // consequence of a button she just pressed.
      setPolite("booking.otpResend");
    }, OTP_RESEND_COOLDOWN_MS);
    return () => {
      clearTimeout(timer);
    };
  }, [cooling]);

  const retry = () => {
    setEntryError(null);
    setEntry(null);
    setAttempt((n) => n + 1);
  };

  const slots: SlotTime[] =
    entry?.slots.map((slot) => ({ value: slot.starts_at, label: jerusalemTime(slot.starts_at) })) ??
    [];
  const dates = entry?.slots.map((slot) => jerusalemDate(slot.starts_at)) ?? [];
  // Bounds come from the instants the server returned, never from the browser
  // clock — a bride abroad, or a device with a wrong TZ, must not be offered a
  // date the server will reject.
  const min = dates[0];
  const max = dates[dates.length - 1];
  const date = pickedDate || min || "";
  const times = slots.filter((_, index) => dates[index] === date);

  const selectedType = entry?.types.find((type) => type.id === flow.typeId) ?? null;
  const depositBlocked = selectedType?.deposit_required === true;

  // Encoded exactly as api.getDress encodes it; router.tsx's decodeId is the
  // matching decoder. The segment rides every step's URL, and F4 keeps it there
  // even when the binding dies — navigate() is pushState-only, so rewriting it
  // would push an entry the back button walks straight back into.
  const suffix = dressId === undefined ? "" : `/${encodeURIComponent(dressId)}`;
  const previousStep = PREVIOUS_STEP[step];

  const terms = entry?.terms ?? null;
  const accepted = terms !== null && acceptedVersion === terms.version;
  // A bound dress with no active sizes cannot produce a valid payload — the
  // backend takes dress_id and dress_size as a pair or not at all — so it drops
  // the binding rather than sending half of one.
  const sizes = dress !== null && dress.sizes.length > 0 ? dress.sizes : null;
  const bindingLoading = dressId !== undefined && dress === null && !dressGone;

  // Normalized ONCE, here, and this exact string is what /otp/send, /otp/verify
  // and /bookings all carry. A client that normalises differently across the
  // three answers PHONE_NOT_VERIFIED for a correct code.
  const normalizedPhone = normalizePhone(phone);
  const codeSent = codeSentFor !== null && codeSentFor === normalizedPhone;

  // D8: a later step entered with no picked slot has nothing to book. `confirm`
  // is exempt — the booking is already written, and there is no public endpoint
  // to re-read it, so bouncing her to step one would lose the only record. And
  // `verify` reached with a spent token but a written booking goes FORWARD.
  useEffect(() => {
    if (step === "verify" && booked !== null) {
      navigate(`/book/confirm${suffix}`);
      return;
    }
    if (step === "slot" || step === "confirm" || flow.startsAt !== null) return;
    navigate(`/book/slot${suffix}`);
  }, [step, flow.startsAt, suffix, booked]);

  const clearError = (field: keyof FieldErrors) => {
    setFieldErrors((current) => ({ ...current, [field]: undefined }));
  };

  // Answering the question the message asked retires it — otherwise a return
  // reason outlives its step and greets her again on a later visit to it.
  const clearReturn = (reason: ReturnReason) => {
    setReturnReason((current) => (current === reason ? null : current));
  };

  const forward = () => {
    if (selectedType === null) {
      setMissing({ type: true, time: flow.startsAt === null });
      typeRef.current?.focus();
      return;
    }
    if (depositBlocked) {
      // R7: the button is never disabled. Pressing it re-announces the deposit
      // block — the selected radio's own description — and does nothing else.
      setMissing({ type: false, time: false });
      typeRef.current?.focus();
      return;
    }
    if (flow.startsAt === null) {
      setMissing({ type: false, time: true });
      timeRef.current?.focus();
      return;
    }
    setMissing({ type: false, time: false });
    navigate(`/book/details${suffix}`);
  };

  // Errors surface HERE and nowhere else — not on blur, which fires the moment
  // she tabs out of a field she means to come back to, and not on input, which
  // calls her name required before she has finished the first letter. Every
  // validator runs, every failure renders, focus lands on the first one, and no
  // request is issued.
  const forwardDetails = () => {
    const nameError = validateName(name);
    const notesError = validateNotes(notes);
    const sizeError = sizes !== null && size === null ? t("booking.sizeRequired") : null;
    setFieldErrors({
      name: nameError ?? undefined,
      size: sizeError ?? undefined,
      notes: notesError ?? undefined,
    });
    if (nameError !== null) {
      nameRef.current?.focus();
      return;
    }
    if (sizeError !== null) {
      sizeRef.current?.focus();
      return;
    }
    if (notesError !== null) {
      notesRef.current?.focus();
      return;
    }
    navigate(`/book/terms${suffix}`);
  };

  const forwardTerms = () => {
    if (!accepted) {
      setFieldErrors((current) => ({ ...current, accept: t("booking.acceptRequired") }));
      acceptRef.current?.focus();
      return;
    }
    clearError("accept");
    navigate(`/book/verify${suffix}`);
  };

  // Every failure that leaves her on this step with no way to learn whether she
  // is booked ends here: the controls come back, and a phone number appears.
  const unknownFailure = () => {
    setStepAlert({ key: "errors.unknown", contact: true });
  };

  const send = async () => {
    if (sending) return;
    const invalid = validatePhone(phone);
    if (invalid !== null) {
      setPhoneError(invalid);
      pendingFocus.current = "phone";
      return;
    }
    setPhoneError(undefined);
    setStepAlert(null);
    setSending(true);
    try {
      await api.sendOtp(normalizedPhone);
      setCodeSentFor(normalizedPhone);
      setCode("");
      setCodeError(undefined);
      setToken(null);
      setCooling(true);
      pendingFocus.current = "code";
    } catch (error: unknown) {
      const key = errorMessageKey(error);
      // The discriminator is the CALL SITE, never the code: this budget is 5 per
      // HOUR, so errors.tooManyAttempts ("try again in a moment") would be a lie
      // that makes her hammer the same 429.
      if (key === "errors.tooManyAttempts" || key === "errors.smsUnavailable") {
        setDeadEnd(key === "errors.tooManyAttempts" ? "errors.otpSendBudget" : key);
        pendingFocus.current = "deadEnd";
      } else {
        unknownFailure();
      }
    }
    setSending(false);
  };

  // The three routed recoveries. Every one of them keeps her verification
  // token: create_booking runs in one transaction, so a claim that loses a race
  // rolls its own token burn back with it, and re-verifying would burn one of
  // five hourly sends to re-prove what the server never un-proved.
  const recoverSlot = async () => {
    const fresh = await api.listSlots().catch(() => null);
    if (fresh === null) {
      unknownFailure();
      return;
    }
    setEntry((current) => (current === null ? current : { ...current, slots: fresh.slots }));
    // The type and the date survive: a lost race is not a restart of intent.
    setFlow((current) => ({ ...current, startsAt: null }));
    setReturnReason("slot");
    navigate(`/book/slot${suffix}`);
  };

  const recoverTerms = async () => {
    let fresh: StorefrontTerms | null;
    try {
      fresh = await api.getTerms();
    } catch (error: unknown) {
      if (errorMessageKey(error) !== "errors.notFound") {
        unknownFailure();
        return;
      }
      fresh = null;
    }
    // The held version is replaced, which unchecks the consent by construction:
    // `accepted` is acceptedVersion === terms.version, and carrying it forward
    // would record agreement to text she never saw.
    setEntry((current) => (current === null ? current : { ...current, terms: fresh }));
    if (fresh === null) {
      // The boutique deleted its policy outright mid-session. F13 cannot accept
      // a booking without a terms version, so there is no flow left to return
      // her to: D5's phone-only entry, reached from a second trigger point.
      navigate(`/book/slot${suffix}`);
      return;
    }
    setReturnReason("terms");
    navigate(`/book/terms${suffix}`);
  };

  // ONE code, three causes, and the wire carries no discriminator: a withdrawn
  // type, an archived dress and a deleted size variant all answer 404. The two
  // reads that can tell them apart run while the submit button is still
  // `loading` — the probe is part of the submit, not a second interaction.
  const probeNotFound = async (
    bound: string | null,
    reissue: () => Promise<BookingCreateResponse>,
  ) => {
    const probed = await Promise.all([
      api.listAppointmentTypes(),
      bound === null
        ? Promise.resolve<StorefrontDetail | null>(null)
        : api.getDress(bound).catch((error: unknown) => {
            if (errorMessageKey(error) === "errors.notFound") return null;
            throw error;
          }),
    ]).catch(() => null);
    // Every read shares the per-tenant throttle, so the probe's own 429 is
    // realistic — and it is evidence of nothing. R13's face, and she stays here
    // with everything intact rather than being walked back on a guess.
    if (probed === null) {
      unknownFailure();
      return;
    }
    const [types, detail] = probed;
    setEntry((current) => (current === null ? current : { ...current, types }));

    if (!types.some((type) => type.id === flow.typeId)) {
      setFlow((current) => ({ ...current, typeId: null }));
      setReturnReason("type");
      navigate(`/book/slot${suffix}`);
      return;
    }
    if (bound === null) {
      unknownFailure();
      return;
    }
    if (detail !== null) {
      // The type and the dress both stand, so it was the size variant.
      setDress(detail);
      setSize(null);
      setReturnReason("size");
      navigate(`/book/details${suffix}`);
      return;
    }
    // R20: drop the binding and CONTINUE. Walking her back two steps for a
    // decoration she did not choose costs three navigations against a
    // 600-second token that is already partly spent.
    setDress(null);
    setDressGone(true);
    const created = await reissue().catch(() => null);
    if (created === null) {
      unknownFailure();
      return;
    }
    setBooked(created);
    setReturnReason("dress");
    navigate(`/book/confirm${suffix}`);
  };

  const submit = async () => {
    // Required, not decorative: React commits `disabled` asynchronously, and a
    // fast double-tap on iOS fires two clicks inside one frame.
    if (submitting) return;
    // Read out before the closures below: TypeScript keeps a narrowing across a
    // closure boundary for consts, and not for the state object's properties.
    const typeId = flow.typeId;
    const startsAt = flow.startsAt;
    const termsVersion = acceptedVersion;
    if (typeId === null || startsAt === null || termsVersion === null) return;
    setSubmitting(true);
    setStepAlert(null);
    setCodeError(undefined);
    setPolite("booking.submitting");

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
          pendingFocus.current = "code";
        } else if (key === "errors.tooManyAttempts") {
          // 10 per 5 minutes — short and self-clearing, so the form survives
          // whole and both controls stay live.
          setStepAlert({ key, contact: false });
        } else {
          unknownFailure();
        }
        setPolite(null);
        setSubmitting(false);
        return;
      }
    }

    // A dress and its size are a PAIR at the boundary or neither is sent, so a
    // dropped binding sends nothing rather than half of one.
    const binding: Binding =
      sizes !== null && size !== null && dressId !== undefined
        ? { dress_id: dressId, dress_size: size }
        : NO_BINDING;
    const verified = current;
    const book = (bound: Binding) =>
      api.createBooking({
        phone: normalizedPhone,
        verification_token: verified,
        name,
        appointment_type_id: typeId,
        starts_at: startsAt,
        terms_version: termsVersion,
        ...bound,
        notes: notes === "" ? null : notes,
      });
    try {
      const created = await book(binding);
      setBooked(created);
      navigate(`/book/confirm${suffix}`);
    } catch (error: unknown) {
      const key = errorMessageKey(error);
      if (key === "errors.phoneNotVerified") {
        // Collapse to sub-state A. The token is gone, so the code it minted is
        // worthless — but nothing else she entered is touched, including the
        // consent: a consent is a consent to a VERSION, and the version did not
        // change.
        setCodeSentFor(null);
        setCode("");
        setToken(null);
        setStepAlert({ key, contact: false });
        pendingFocus.current = "phone";
      } else if (key === "errors.slotUnavailable") {
        await recoverSlot();
      } else if (key === "errors.termsStale") {
        await recoverTerms();
      } else if (key === "errors.notFound") {
        await probeNotFound(binding.dress_id, () => book(NO_BINDING));
      } else {
        // R13, and it stays the LAST branch: everything the design named has a
        // destination above, and everything else lands here. Retry is genuinely
        // safe — create_booking runs in one transaction and a failure at any
        // step rolls the token burn back with it.
        unknownFailure();
      }
      // Emptied so a second attempt is a change the region announces again.
      setPolite(null);
    }
    setSubmitting(false);
  };

  const onVerifySubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void (codeSent ? submit() : send());
  };

  // R14: the cold branch has no 201 and no way to fetch one, so it may not
  // assert a booking it cannot show. It takes the flow's own name — the R12
  // precedent, and zero new keys. Warm, the boutique's name makes a screenshot
  // self-explanatory three weeks later; without it the nameless title, never
  // the generic "חנות הכלות" on her only record.
  const confirmHeading =
    booked === null
      ? t("document.book")
      : boutique === null
        ? t("booking.confirmTitle")
        : t("booking.confirmTitleNamed", { name: boutique.name });

  // No terms and no types are the two exits that replace the whole step: there
  // is no flow to be a step of, so no stepper and no forward control.
  const exitKey =
    step !== "slot" || entry === null
      ? null
      : entry.terms === null
        ? "booking.noTermsByPhone"
        : entry.types.length === 0
          ? "booking.noTypes"
          : null;

  return (
    <div className={pageClass}>
      {/* Block-start on every step, so a control that reverses a step never
          relocates between screens (WCAG 3.2.3). Step 1's target is always the
          catalog, never the bound dress. */}
      {step === "slot" ? (
        <Link to="/" className={backLinkClass}>
          {/* In RTL the way back points inline-start-to-end, i.e. rightwards. */}
          <span aria-hidden="true">→</span> {t("booking.backToCatalog")}
        </Link>
      ) : (
        previousStep !== undefined && (
          <Link to={`/book/${previousStep}${suffix}`} className={backLinkClass}>
            <span aria-hidden="true">→</span> {t("booking.backStep")}
          </Link>
        )
      )}

      {step !== "confirm" && exitKey === null && <Stepper step={step} />}

      <div className="flex flex-col gap-2">
        <h1 className="font-display text-2xl text-ink">
          {exitKey !== null
            ? t("document.book")
            : step === "confirm"
              ? confirmHeading
              : t(STEP_LABEL_KEYS[step])}
        </h1>
        <span aria-hidden="true" className="h-px w-12 bg-gold" />
      </div>

      {step === "slot" &&
        (exitKey !== null ? (
          <PhoneOnly messageKey={exitKey} />
        ) : entryError !== null ? (
          // ONE alert, not three. A single outage announced three times makes a
          // screen reader read three messages for one problem. Muted, not
          // danger: a backend that is down is not the boutique's fault, and a
          // spent read budget already maps to errors.tooManyAttempts here.
          <Card className="flex flex-col items-start gap-3">
            <p role="alert" className="text-base text-ink-muted">
              {errorMessageOr(entryError, t, "booking.slotsError")}
            </p>
            <Button variant="secondary" onClick={retry}>
              {t("catalog.retry")}
            </Button>
          </Card>
        ) : entry === null ? (
          <Card className="flex flex-col gap-6">
            {/* aria-busy on a plain div is announced by neither VoiceOver nor
                NVDA, so a slow connection was the h1, then silence. */}
            <VisuallyHidden>
              <span role="status">{t("booking.loading")}</span>
            </VisuallyHidden>
            <Skeleton variant="text" lines={1} />
            <Skeleton variant="text" lines={3} className="h-11" />
            <Skeleton variant="text" lines={2} className="h-11" />
          </Card>
        ) : (
          <>
            <Card className="flex flex-col gap-6">
              <TypePicker
                types={entry.types}
                value={flow.typeId}
                boutique={boutique}
                error={missing.type ? t("booking.typeRequired") : undefined}
                notice={returnReason === "type" ? t("booking.typeGoneRepick") : undefined}
                onChange={(typeId) => {
                  setFlow((current) => ({ ...current, typeId }));
                  setMissing((current) => ({ ...current, type: false }));
                  clearReturn("type");
                }}
                ref={typeRef}
              />
              <SlotPicker
                date={date}
                min={min}
                max={max}
                times={times}
                value={flow.startsAt}
                error={
                  missing.time
                    ? t("booking.timeRequired")
                    : returnReason === "slot"
                      ? t("errors.slotUnavailable")
                      : undefined
                }
                onDateChange={(next) => {
                  setPickedDate(next);
                  // A time picked on another date is not a time on this one.
                  setFlow((current) => ({ ...current, startsAt: null }));
                }}
                onChange={(startsAt) => {
                  setFlow((current) => ({ ...current, startsAt }));
                  setMissing((current) => ({ ...current, time: false }));
                  clearReturn("slot");
                }}
                ref={timeRef}
              />
            </Card>

            <ForwardRow onClick={forward} />
          </>
        ))}

      {step === "details" && (
        <>
          <Card className="flex flex-col gap-6">
            {dressId !== undefined && (
              <div className="flex flex-col gap-4">
                {bindingLoading ? (
                  <div className="flex items-center gap-3">
                    <Skeleton variant="image" className="w-16" />
                    <Skeleton variant="text" lines={1} className="w-40" />
                  </div>
                ) : dressGone ? (
                  // The whole binding block is gone with it — cover, name and
                  // fieldset — and the line takes its place. Cautionary, never
                  // danger: nothing she did failed.
                  <p role="alert" className="text-sm text-warning-text">
                    {t("booking.dressGoneGeneric")}
                  </p>
                ) : (
                  dress !== null && (
                    <>
                      <div className="flex items-center gap-3">
                        {/* alt="" — the dress name is the adjacent visible text.
                            NOT a link: leaving the flow discards the draft, and
                            there is no draft persistence to come back to. */}
                        {dress.media[0]?.url != null && (
                          <img
                            src={dress.media[0].url}
                            alt=""
                            loading="lazy"
                            decoding="async"
                            className="w-16 shrink-0 rounded-md bg-surface object-cover shadow-sm aspect-[3/4]"
                          />
                        )}
                        <p className="font-display text-lg text-ink">
                          {t("booking.forDress", { dress: dress.name })}
                        </p>
                      </div>
                      {sizes === null && (
                        // Polite, not an alert: nothing failed and nothing
                        // vanished — the dress simply has no bookable variants.
                        <p role="status" className="text-sm text-warning-text">
                          {t("booking.dressGoneGeneric")}
                        </p>
                      )}
                    </>
                  )
                )}
                <span aria-hidden="true" className="h-px bg-border" />
              </div>
            )}

            <Input
              label={t("booking.name")}
              type="text"
              // A Latin name is ordinary on a Hebrew form.
              dir="auto"
              autoComplete="name"
              enterKeyHint="next"
              required
              maxLength={MAX_CUSTOMER_NAME_LENGTH}
              value={name}
              error={fieldErrors.name}
              onChange={(event) => {
                setName(event.target.value);
                clearError("name");
              }}
              ref={nameRef}
            />

            {/* Between the two text fields on purpose: it is the only control
                here a mid-flow answer can invalidate, and a returning bride
                should not scroll past her own typed answers to reach it. */}
            {sizes !== null && (
              <SizeChips
                sizes={sizes}
                value={size}
                error={fieldErrors.size}
                notice={returnReason === "size" ? t("booking.sizeGoneRepick") : undefined}
                onChange={(picked) => {
                  setSize(picked);
                  clearError("size");
                  clearReturn("size");
                }}
                ref={sizeRef}
              />
            )}

            <TextArea
              label={t("booking.notes")}
              help={t("booking.notesHint")}
              dir="auto"
              rows={4}
              showCount
              maxLength={MAX_BOOKING_NOTES_LENGTH}
              value={notes}
              error={fieldErrors.notes}
              onChange={(event) => {
                setNotes(event.target.value);
                clearError("notes");
              }}
              // Logical: the default `resize: both` lets a drag widen the field
              // past the column and produce horizontal scroll at 375.
              className="[resize:block]"
              ref={notesRef}
            />
          </Card>

          <ForwardRow onClick={forwardDetails} />
        </>
      )}

      {step === "terms" && terms !== null && (
        <>
          {/* Above the Card, so it is the first thing in the content region
              after the h1 the Router's focus move lands on. Cautionary, never
              danger: nothing she did failed — the boutique republished. */}
          {returnReason === "terms" && (
            <p role="alert" className="max-w-[60ch] text-base text-warning-text">
              {t("errors.termsStale")}
            </p>
          )}
          <Card className="flex flex-col gap-4">
            {/* The two numbers sit ABOVE the prose because they are what she is
                actually agreeing to, and a paragraph is where numbers hide.
                Weight and a divider carry the distinction — never a tinted
                callout, which would read as an alert two neutral facts are not. */}
            <p className="text-base font-semibold text-ink">
              {t("booking.refundWindow", { hours: terms.refundable_until_hours_before })}
            </p>
            <p className="text-base font-semibold text-ink">
              {t("booking.forfeit", { percent: terms.forfeit_percent })}
            </p>

            <span aria-hidden="true" className="h-px bg-border" />

            {/* A React text child, and only ever that: no dangerouslySetInnerHTML,
                no markdown renderer, no sanitise-then-inject. The owner is
                semi-trusted but this is a public, anonymous, multi-tenant
                surface, so any HTML path is stored XSS for every visitor.
                pre-line keeps her line breaks and collapses her stray spaces;
                dir="auto" because owners paste English clauses; anywhere because
                a pasted 200-character URL must not scroll the page sideways. No
                inner scroller at any width — two scroll contexts on a phone is a
                trap, and a scrollable box is a tab stop between the policy and
                the consent. */}
            <div dir="auto" className="whitespace-pre-line text-base text-ink [overflow-wrap:anywhere]">
              {terms.terms_text}
            </div>

            <span aria-hidden="true" className="h-px bg-border" />

            {/* Last in flow, below the prose: a consent control reachable before
                the thing consented to is how unread consent happens. */}
            <Checkbox
              label={t("booking.acceptTerms")}
              checked={accepted}
              error={fieldErrors.accept}
              onCheckedChange={(next) => {
                setAcceptedVersion(next ? terms.version : null);
                clearError("accept");
                clearReturn("terms");
              }}
              ref={acceptRef}
            />
          </Card>

          <ForwardRow onClick={forwardTerms} />
        </>
      )}

      {step === "verify" &&
        (deadEnd !== null ? (
          <PhoneOnly messageKey={deadEnd} muted ref={deadEndRef} />
        ) : (
          <>
            {stepAlert !== null && (
              <div className="flex flex-col gap-4">
                {/* Muted, not danger. The field-level errors are danger because
                    the phone is the only thing here she can type wrong; a token
                    that expired and a spent budget are not her mistake. */}
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

            {/* A real form, so Enter in either field does the step's one forward
                action once — and the handler's own guard covers key repeat. */}
            <form onSubmit={onVerifySubmit}>
              <Card className="flex flex-col gap-6">
                <Input
                  label={t("booking.phone")}
                  help={t("booking.phoneHint")}
                  type="tel"
                  // The label and the box stay in the RTL flow; only the field's
                  // CONTENT direction flips, so the caret rests at the physical
                  // left of an empty box and the value grows rightwards.
                  // text-align is left unset on purpose — `end` would park the
                  // caret against the label and read deletion backwards.
                  dir="ltr"
                  inputMode="tel"
                  autoComplete="tel"
                  value={phone}
                  error={phoneError}
                  onChange={(event) => {
                    const next = event.target.value;
                    setPhone(next);
                    setPhoneError(undefined);
                    // Editing away from the number the code was minted for
                    // collapses the field AND discards what it bought.
                    if (normalizePhone(next) !== codeSentFor) {
                      setCode("");
                      setCodeError(undefined);
                      setToken(null);
                    }
                  }}
                  ref={phoneRef}
                />

                {codeSent && (
                  <>
                    <span aria-hidden="true" className="h-px bg-border" />
                    {/* ONE field. Six boxes are six tab stops and six labels for
                        one value, they need bespoke split-on-paste logic Safari
                        breaks, autocomplete="one-time-code" fills a SINGLE
                        field, and forwarding focus per keystroke steals it six
                        times from a bride who is still typing. */}
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
                        // Digits-only makes a short submit a deliberate act
                        // rather than a stray space, in two lines instead of a
                        // validator. No auto-submit on the sixth digit: it fires
                        // on a paste of a WRONG code and spends a verify budget.
                        setCode(event.target.value.replace(/\D/g, "").slice(0, 6));
                        setCodeError(undefined);
                      }}
                      ref={codeRef}
                    />
                  </>
                )}

                {/* R27 puts the forward control at the inline-end from 768;
                    row-reverse gets it there while the DOM keeps the primary
                    action first, which is the order §6.3 stacks them in at 375. */}
                <div className="flex flex-col gap-3 md:flex-row-reverse md:justify-start">
                  {codeSent && (
                    <Button
                      type="submit"
                      variant="primary"
                      size="lg"
                      fullWidthMobile
                      loading={submitting}
                    >
                      {t("booking.submit")}
                    </Button>
                  )}
                  {/* One label for the first send and the resend: a screen
                      reader arriving at an empty form must not hear a button
                      offering to resend something that never happened. While
                      cooling the label IS the explanation — `disabled` drops the
                      control from the tab order, which makes any description on
                      it inert. */}
                  <Button
                    type="button"
                    variant={codeSent ? "secondary" : "primary"}
                    size="md"
                    fullWidthMobile
                    loading={sending}
                    disabled={cooling || submitting}
                    onClick={() => {
                      void send();
                    }}
                  >
                    {t(cooling ? "booking.otpResendWait" : "booking.otpResend")}
                  </Button>
                </div>

                <VisuallyHidden>
                  <span role="status">{polite === null ? "" : t(polite)}</span>
                </VisuallyHidden>
              </Card>
            </form>
          </>
        ))}

      {step === "confirm" &&
        (booked === null ? (
          // Cold: a reload, or the app-switch a screenshot triggers on iOS.
          // There is no public read-a-booking-by-id endpoint, so this states
          // what it can and offers the phone — no Card, because the Card's job
          // is to hold facts and with none it would frame an absence, and no
          // confirmKeepScreen, because keeping a record this branch does not
          // have is an instruction to preserve nothing.
          <PhoneOnly messageKey="booking.confirmCold" muted />
        ) : (
          <>
            <Card className="flex flex-col gap-4">
              <div className="flex flex-col gap-1">
                {/* Labels, not sentences: interpolation cannot carry the <bdi>
                    the numerals need, and a label/value pair survives being read
                    back off a screenshot at 200% zoom. */}
                <p className="text-sm font-semibold text-ink-muted">{t("booking.confirmWhen")}</p>
                <p className="text-lg text-ink">
                  {CONFIRM_WEEKDAY.format(new Date(booked.starts_at))},{" "}
                  <bdi dir="ltr">{CONFIRM_DATE.format(new Date(booked.starts_at))}</bdi>{" "}
                  <span aria-hidden="true">·</span>{" "}
                  <bdi dir="ltr">{jerusalemTime(booked.starts_at)}</bdi>
                </p>
              </div>

              <span aria-hidden="true" className="h-px bg-border" />

              <div className="flex flex-col gap-1">
                <p className="text-sm font-semibold text-ink-muted">{t("booking.confirmWhat")}</p>
                {/* Owner-authored, so it may be Hebrew or Latin — a bare <bdi>
                    isolates it either way. `status` is deliberately not printed:
                    it is server-constant on this path. */}
                <p className="text-lg text-ink">
                  <bdi>{booked.appointment_type_name}</bdi>
                </p>
                {booked.dress_name !== null && booked.dress_size !== null && (
                  <p className="text-base text-ink">
                    {t("booking.confirmDress", {
                      dress: booked.dress_name,
                      size: booked.dress_size,
                    })}
                  </p>
                )}
              </div>
            </Card>

            {/* R20's landing: the binding was dropped and the booking went
                through without it, so the record is honest and this line says
                what is missing from it. Outside the Card — the dress is not a
                fact of the appointment she got. */}
            {returnReason === "dress" && (
              <p role="alert" className="max-w-[60ch] text-base text-warning-text">
                {t("booking.dressGoneGeneric")}
              </p>
            )}

            {/* Outside the Card: an instruction ABOUT the record, not a fact IN
                it — a screenshot cropped to the Card should carry only facts. */}
            <p className="max-w-[60ch] text-base text-ink-muted">
              {t("booking.confirmKeepScreen")}
            </p>
          </>
        ))}

      {step === "confirm" && (
        <Link to="/" className={backLinkClass}>
          <span aria-hidden="true">→</span> {t("booking.backToCatalog")}
        </Link>
      )}
    </div>
  );
}
