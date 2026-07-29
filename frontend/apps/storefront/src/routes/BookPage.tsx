import { useEffect, useRef, useState } from "react";
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
import { ApiError, api, errorMessageOr } from "../api";
import type {
  AppointmentTypeRow,
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
  validateName,
  validateNotes,
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
function PhoneOnly({ messageKey }: { messageKey: string }) {
  const { t } = useTranslation();
  const { boutique } = useBoutique();

  return (
    <div className="flex flex-col gap-6">
      {/* Ink, not ink-muted: this is an instruction she must act on, not an
          outage report. */}
      <p className="max-w-[60ch] text-base text-ink">{t(messageKey)}</p>
      {boutique === null ? (
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
  const typeRef = useRef<HTMLInputElement>(null);
  const timeRef = useRef<HTMLInputElement>(null);
  const nameRef = useRef<HTMLInputElement>(null);
  const sizeRef = useRef<HTMLInputElement>(null);
  const notesRef = useRef<HTMLTextAreaElement>(null);
  const acceptRef = useRef<HTMLInputElement>(null);

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

  // D8: a later step entered with no picked slot has nothing to book. `confirm`
  // is exempt — the booking is already written, and there is no public endpoint
  // to re-read it, so bouncing her to step one would lose the only record.
  useEffect(() => {
    if (step === "slot" || step === "confirm" || flow.startsAt !== null) return;
    navigate(`/book/slot${suffix}`);
  }, [step, flow.startsAt, suffix]);

  const clearError = (field: keyof FieldErrors) => {
    setFieldErrors((current) => ({ ...current, [field]: undefined }));
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
              ? t("booking.confirmTitle")
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
              <span role="status">{t("catalog.loading")}</span>
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
                onChange={(typeId) => {
                  setFlow((current) => ({ ...current, typeId }));
                  setMissing((current) => ({ ...current, type: false }));
                }}
                ref={typeRef}
              />
              <SlotPicker
                date={date}
                min={min}
                max={max}
                times={times}
                value={flow.startsAt}
                error={missing.time ? t("booking.timeRequired") : undefined}
                onDateChange={(next) => {
                  setPickedDate(next);
                  // A time picked on another date is not a time on this one.
                  setFlow((current) => ({ ...current, startsAt: null }));
                }}
                onChange={(startsAt) => {
                  setFlow((current) => ({ ...current, startsAt }));
                  setMissing((current) => ({ ...current, time: false }));
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
                onChange={(picked) => {
                  setSize(picked);
                  clearError("size");
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
              }}
              ref={acceptRef}
            />
          </Card>

          <ForwardRow onClick={forwardTerms} />
        </>
      )}
    </div>
  );
}
