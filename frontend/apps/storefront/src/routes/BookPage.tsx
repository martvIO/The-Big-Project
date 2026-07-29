import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Card, JERusalem, Skeleton, VisuallyHidden, cn, focusRing } from "@boutique/ui";
import { ApiError, api, errorMessageOr } from "../api";
import type { AppointmentTypeRow, SlotRow, StorefrontTerms } from "../api";
import { ContactCard } from "../components/ContactCard";
import { SlotPicker } from "../components/booking/SlotPicker";
import type { SlotTime } from "../components/booking/SlotPicker";
import { TypePicker } from "../components/booking/TypePicker";
import { useBoutique } from "../components/StorefrontLayout";
import { Link, navigate } from "../router";
import type { BookStep } from "../router";

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
  const typeRef = useRef<HTMLInputElement>(null);
  const timeRef = useRef<HTMLInputElement>(null);

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
    // Encoded exactly as api.getDress encodes it; router.tsx's decodeId is the
    // matching decoder.
    navigate(`/book/details${dressId === undefined ? "" : `/${encodeURIComponent(dressId)}`}`);
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
      {step === "slot" && (
        <Link to="/" className={backLinkClass}>
          {/* In RTL the way back points inline-start-to-end, i.e. rightwards. */}
          <span aria-hidden="true">→</span> {t("booking.backToCatalog")}
        </Link>
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

            {/* Alone on the last row, inline-end from 768. NEVER disabled, and
                never carrying aria-describedby — disabled drops a control from
                the tab order, which makes a description from it unreadable. */}
            <div className="flex md:justify-end">
              <Button
                variant="primary"
                size="lg"
                onClick={forward}
                className="w-full min-w-[140px] md:w-auto"
              >
                {t("booking.continue")}
              </Button>
            </div>
          </>
        ))}
    </div>
  );
}
