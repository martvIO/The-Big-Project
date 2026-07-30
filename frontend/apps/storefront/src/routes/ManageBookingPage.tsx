import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, ButtonLink, Card, JERusalem, Skeleton, VisuallyHidden } from "@boutique/ui";
import { ApiError, api } from "../api";
import type { BoutiqueResponse, ManageBookingResponse } from "../api";
import { ContactCard } from "../components/ContactCard";
import { useBoutique } from "../components/StorefrontLayout";

// The page behind the tokenized manage link that rides the confirmation and
// reminder SMS. It is the confirmation screen's SIBLING, not a flow: she arrived
// from a text message, possibly weeks later, so there is no stepper, no progress
// and no back-to-step-one. Facts first, actions second, boutique contact last.
//
// Instants render in the BOUTIQUE's zone. A bride whose phone clock the airline
// changed must still read the boutique's time, and the confirmation screen makes
// the same choice with the same formatters.
const WEEKDAY = new Intl.DateTimeFormat("he-IL", { timeZone: JERusalem, weekday: "long" });
const DATE = new Intl.DateTimeFormat("he-IL", {
  timeZone: JERusalem,
  day: "numeric",
  month: "numeric",
  year: "numeric",
});
const TIME = new Intl.DateTimeFormat("en-GB", {
  timeZone: JERusalem,
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

// Identical to /book/* so the two surfaces read as one product. The column stays
// 640 and centred at every width — a luxury reading column, not a dashboard, and
// there is deliberately no two-column desktop layout for five facts and two
// buttons. pb-16 clears the fixed A11yMenu trigger, which this route carries with
// no CTA bar beneath it to reserve the space.
const pageClass = "mx-auto flex max-w-[640px] flex-col gap-6 px-4 pt-8 pb-16 md:px-6";

const CANCELLED = "cancelled";

// What the page is showing. Derived from the response, never from what an action
// optimistically hoped: a 409 on confirm or cancel re-drives the lookup so the
// screen re-renders from the server's answer.
type View =
  | { kind: "loading" }
  | { kind: "loaded"; data: ManageBookingResponse }
  // The token is unknown or was rotated. No facts to show.
  | { kind: "invalid" }
  // 429 / network / 5xx — recoverable, so it offers a retry and the phone.
  | { kind: "failed" };

/**
 * The lookup payload's four boutique fields, shaped as the response the contact
 * block reads.
 *
 * FALLBACK ONLY, and only for the states that have a payload at all (F-M2 as
 * corrected at the design gate): `useBoutique()` is the primary source, and the
 * invalid-link and load-failed states are lookup FAILURES whose responses are the
 * house error shape and carry no boutique data under any circumstance.
 */
function fallbackBoutique(block: ManageBookingResponse["boutique"]): BoutiqueResponse {
  return {
    name: block.name,
    essence: null,
    description: null,
    phone: block.phone,
    address: block.address,
    maps_url: block.maps_url,
    // Not in the manage subset: the payload carries the four fields the contact
    // block needs and nothing a later `profile` key could smuggle in.
    instagram: null,
    hours: [],
    exceptions: [],
  };
}

function Heading() {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-3">
      <h1 className="font-display text-2xl text-ink">{t("manage.title")}</h1>
      {/* Identical to every /book/* heading: the gold hairline is the brand's
          voice on an otherwise utilitarian screen. */}
      <span aria-hidden="true" className="h-px w-12 bg-gold" />
    </div>
  );
}

// The facts, with labels REUSED from the approved confirmation screen (design
// P2) — one label, one Hebrew, no drift between the two screens that show the
// same appointment. Labels rather than sentences because interpolation cannot
// carry the <bdi> a numeral needs, and a label/value pair survives being read
// back off a screenshot at 200% zoom.
function Facts({ booking }: { booking: ManageBookingResponse["booking"] }) {
  const { t } = useTranslation();
  const when = new Date(booking.starts_at);

  return (
    <Card className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <p className="text-sm font-semibold text-ink-muted">{t("booking.confirmWhen")}</p>
        <p className="text-lg text-ink">
          {WEEKDAY.format(when)}, <bdi dir="ltr">{DATE.format(when)}</bdi>{" "}
          <span aria-hidden="true">·</span> <bdi dir="ltr">{TIME.format(when)}</bdi>
        </p>
      </div>

      <span aria-hidden="true" className="h-px bg-border" />

      <div className="flex flex-col gap-1">
        <p className="text-sm font-semibold text-ink-muted">{t("booking.confirmWhat")}</p>
        {/* Owner-authored, so it may be Hebrew or Latin — a bare <bdi> isolates
            it either way. dir="ltr" would itself be a bidi defect on Hebrew. */}
        <p className="text-lg text-ink">
          <bdi>{booking.appointment_type_name}</bdi>
        </p>
        {booking.dress_name !== null && booking.dress_size !== null && (
          <p className="text-base text-ink">
            <bdi>{booking.dress_name}</bdi> <span aria-hidden="true">·</span>{" "}
            {t("booking.confirmDress")} <bdi>{booking.dress_size}</bdi>
          </p>
        )}
      </div>
    </Card>
  );
}

// R19's split shape: the lead, the isolated numeral, the tail. i18next
// interpolation cannot carry the <bdi> the number needs, so the seam moved
// rather than the words.
function PolicyLine({ hours }: { hours: number }) {
  const { t } = useTranslation();
  return (
    <p className="text-sm text-ink-muted">
      {t("manage.cancelPolicyLead")} <bdi dir="ltr">{hours}</bdi>{" "}
      {t("manage.cancelPolicySuffix")}
    </p>
  );
}

export function ManageBookingPage({ token }: { token: string }) {
  const { t } = useTranslation();
  const { boutique: layoutBoutique, loading: boutiqueLoading } = useBoutique();
  const [view, setView] = useState<View>({ kind: "loading" });
  const [revealed, setRevealed] = useState(false);
  // WHICH action is in flight, not merely whether one is. Both controls can be
  // on screen at once (cancel stays available once attendance is confirmed, and
  // the reveal does not remove the primary button), so a boolean spun the wrong
  // button.
  const [busy, setBusy] = useState<"attend" | "cancel" | null>(null);
  // Written on DISCRETE events only (R16): attendance confirmed, cancellation
  // completed. Never on a keystroke or a render.
  const [announced, setAnnounced] = useState<string | null>(null);

  // Each success transition removes the control that was just clicked, so each
  // rules its own focus destination — the house rule is that the mover is the
  // state change which mounted the target. Focus must never drop to <body> after
  // the one action this page exists for.
  const revealRef = useRef<HTMLParagraphElement | null>(null);
  const cancelTriggerRef = useRef<HTMLButtonElement | null>(null);
  const doneRef = useRef<HTMLParagraphElement | null>(null);
  const cancelledRef = useRef<HTMLParagraphElement | null>(null);
  const moveFocusTo = useRef<"done" | "cancelled" | "reveal" | "trigger" | null>(null);

  const load = useCallback(async () => {
    setView({ kind: "loading" });
    try {
      setView({ kind: "loaded", data: await api.lookupBooking(token) });
    } catch (error: unknown) {
      // Branch on the CODE at this call site rather than through
      // errorMessageKey: an invalid link is a page STATE with its own copy, not
      // one more sentence in the shared error map.
      setView(
        error instanceof ApiError && error.code === "BOOKING_LINK_INVALID"
          ? { kind: "invalid" }
          : { kind: "failed" },
      );
    }
  }, [token]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const target = moveFocusTo.current;
    if (target === null) return;
    moveFocusTo.current = null;
    if (target === "reveal") revealRef.current?.focus();
    if (target === "trigger") cancelTriggerRef.current?.focus();
    if (target === "done") doneRef.current?.focus();
    if (target === "cancelled") cancelledRef.current?.focus();
  });

  const act = async (
    which: "attend" | "cancel",
    call: (value: string) => Promise<ManageBookingResponse>,
    announce: string,
    focus: "done" | "cancelled",
  ) => {
    setBusy(which);
    try {
      const data = await call(token);
      setRevealed(false);
      setAnnounced(announce);
      moveFocusTo.current = focus;
      setView({ kind: "loaded", data });
    } catch (error: unknown) {
      if (error instanceof ApiError && error.status === 409) {
        // The clock or another device won. Re-render from the SERVER's state —
        // BOOKING_ALREADY_STARTED lands on the past view, BOOKING_CANCELLED on
        // the cancelled one — rather than from what this tap hoped for.
        setRevealed(false);
        await load();
        return;
      }
      setView(
        error instanceof ApiError && error.code === "BOOKING_LINK_INVALID"
          ? { kind: "invalid" }
          : { kind: "failed" },
      );
    } finally {
      setBusy(null);
    }
  };

  // Primary source is the layout fetch; the payload is the fallback for the
  // states that HAVE a payload (F-M2). Nothing renders while the layout read is
  // in flight — flashing a fallback at a panel that is about to arrive is worse
  // than the small delay.
  const payloadBoutique = view.kind === "loaded" ? fallbackBoutique(view.data.boutique) : null;
  const contact = boutiqueLoading ? null : (layoutBoutique ?? payloadBoutique);

  if (view.kind === "loading") {
    return (
      <div className={pageClass}>
        <Heading />
        {/* R30: a visually-hidden status region, because aria-busy on a plain div
            is announced by neither VoiceOver nor NVDA. */}
        <VisuallyHidden>
          <span role="status">{t("manage.loading")}</span>
        </VisuallyHidden>
        <Card className="flex flex-col gap-4" data-testid="manage-loading">
          <Skeleton variant="text" lines={2} />
          <Skeleton variant="text" lines={2} />
        </Card>
      </div>
    );
  }

  if (view.kind === "invalid") {
    return (
      <div className={pageClass}>
        <Heading />
        {/* No Card: its job is to hold facts, and with none it would frame an
            absence. */}
        <p className="max-w-[60ch] text-lg text-ink">{t("manage.invalid")}</p>
        <p className="max-w-[60ch] text-base text-ink-muted">{t("manage.invalidHint")}</p>
        {/* A lookup FAILURE carries no boutique data, so this state depends
            solely on the layout fetch and renders without the block when that
            failed too — the copy above stands on its own. */}
        {!boutiqueLoading && layoutBoutique !== null && <ContactCard boutique={layoutBoutique} />}
      </div>
    );
  }

  if (view.kind === "failed") {
    return (
      <div className={pageClass}>
        <Heading />
        <p role="alert" className="max-w-[60ch] text-base text-ink-muted">
          {t("manage.loadFailed")}
        </p>
        <div className="flex">
          <Button
            variant="secondary"
            size="md"
            fullWidthMobile
            onClick={() => {
              void load();
            }}
          >
            {t("manage.retry")}
          </Button>
        </div>
        {!boutiqueLoading && layoutBoutique !== null && <ContactCard boutique={layoutBoutique} />}
      </div>
    );
  }

  const { booking, policy } = view.data;
  const cancelled = booking.status === CANCELLED;
  const past = !cancelled && new Date(booking.starts_at).getTime() <= Date.now();
  const confirmed = booking.attendance_confirmed_at !== null;
  const actionable = !cancelled && !past;

  return (
    <div className={pageClass}>
      <Heading />

      {/* Kept in the cancelled state too: she may need the date to rebook. */}
      <Facts booking={booking} />

      {cancelled && (
        <>
          <p ref={cancelledRef} tabIndex={-1} className="text-lg text-ink">
            {t("manage.cancelled")}
          </p>
          <div className="flex">
            <ButtonLink href="/book/slot" className="w-full sm:w-auto">
              {t("manage.rebookCta")}
            </ButtonLink>
          </div>
        </>
      )}

      {past && <p className="text-base text-ink-muted">{t("manage.past")}</p>}

      {actionable && (
        <>
          <div className="flex flex-col gap-3 sm:flex-row">
            {confirmed ? (
              // The success line REPLACES the primary button — the control it
              // describes is gone, so this is the focus destination for the
              // transition that mounted it.
              <p
                ref={doneRef}
                tabIndex={-1}
                className="text-lg font-semibold text-success"
              >
                <span aria-hidden="true">✓ </span>
                {t("manage.attendanceDone")}
              </p>
            ) : (
              <Button
                variant="primary"
                size="lg"
                fullWidthMobile
                loading={busy === "attend"}
                onClick={() => {
                  void act("attend", api.confirmAttendance, "manage.attendanceDone", "done");
                }}
              >
                {t("manage.attendanceCta")}
              </Button>
            )}

            {/* Cancel STAYS available after attendance is confirmed (design P3):
                confirming is a courtesy signal, not a lock-in, and plans change. */}
            {!revealed && (
              <Button
                ref={cancelTriggerRef}
                variant="secondary"
                size="md"
                fullWidthMobile
                onClick={() => {
                  setRevealed(true);
                  moveFocusTo.current = "reveal";
                }}
              >
                {t("manage.cancelCta")}
              </Button>
            )}
          </div>

          {/* THE TWO-STEP. The secondary button above does not call the API; it
              reveals this. One tap must never cancel a wedding-dress
              appointment. An inline reveal rather than a Modal: it keeps the
              whole decision on one surface and spares the focus-trap machinery
              for a two-button choice. */}
          {revealed && (
            <Card className="flex flex-col gap-4 bg-surface-raised">
              {/* The focus destination for the reveal — the QUESTION itself, so a
                  screen reader hears what is being asked rather than an anonymous
                  container. Card takes no ref, and adding one to a gate-passed
                  component to focus a wrapper would buy nothing over this. */}
              <p ref={revealRef} tabIndex={-1} className="text-lg text-ink">
                {t("manage.cancelQuestion")}
              </p>
              {/* The window fact from HER accepted policy. Absent only if that
                  version row has gone — the page then says nothing about a
                  number it cannot justify. */}
              {policy !== null && (
                <PolicyLine hours={policy.refundable_until_hours_before} />
              )}
              {/* Pre-E4 both window sides render the SAME sentence (design P1 /
                  pre-decided #4): every F16-era booking is deposit-free, and a
                  forfeit warning about a deposit that was never taken would be a
                  lie. The split ships as structure; E4 swaps the out-of-window
                  key. */}
              <p className="text-base text-ink">{t("manage.cancelConsequenceFree")}</p>
              <div className="flex flex-col gap-3 sm:flex-row">
                <Button
                  variant="danger"
                  size="md"
                  fullWidthMobile
                  loading={busy === "cancel"}
                  onClick={() => {
                    void act("cancel", api.cancelBooking, "manage.cancelled", "cancelled");
                  }}
                >
                  {t("manage.cancelConfirm")}
                </Button>
                <Button
                  variant="ghost"
                  size="md"
                  fullWidthMobile
                  onClick={() => {
                    setRevealed(false);
                    // Deferred to the layout effect: the trigger is UNMOUNTED
                    // while the reveal is open, so its ref is null until the
                    // collapse has rendered. Focusing it here would silently
                    // drop focus to <body>.
                    moveFocusTo.current = "trigger";
                  }}
                >
                  {t("manage.cancelKeep")}
                </Button>
              </div>
            </Card>
          )}

          {/* Outside the reveal too, so the window is readable before she opens
              the cancel step at all. */}
          {!revealed && policy !== null && (
            <PolicyLine hours={policy.refundable_until_hours_before} />
          )}
        </>
      )}

      {contact !== null && <ContactCard boutique={contact} />}

      <VisuallyHidden>
        <span role="status">{announced === null ? "" : t(announced)}</span>
      </VisuallyHidden>
    </div>
  );
}