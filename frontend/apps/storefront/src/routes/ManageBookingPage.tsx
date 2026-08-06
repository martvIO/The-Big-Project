import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, ButtonLink, Card, Skeleton, VisuallyHidden } from "@boutique/ui";
import { ApiError, api } from "../api";
import type { BoutiqueResponse, ManageBookingResponse } from "../api";
import { ContactCard } from "../components/ContactCard";
import { useBoutique } from "../components/StorefrontLayout";
// ⚠ EXTRACTED, NOT FORKED (F24 F-P3). The portal detail renders the same
// `ManageBookingResponse` through these same three components, so the two
// surfaces cannot drift into two products. This page's own tests are the
// extraction's contract and were not edited for it.
import { BookingFacts, PolicyLine } from "../components/booking/BookingFacts";
import { CancelReveal } from "../components/booking/CancelReveal";
import { IcsDownload } from "../components/booking/IcsDownload";

// The page behind the tokenized manage link that rides the confirmation and
// reminder SMS. It is the confirmation screen's SIBLING, not a flow: she arrived
// from a text message, possibly weeks later, so there is no stepper, no progress
// and no back-to-step-one. Facts first, actions second, boutique contact last.
//
// Identical to /book/* so the two surfaces read as one product. The column stays
// 640 and centred at every width — a luxury reading column, not a dashboard, and
// there is deliberately no two-column desktop layout for five facts and two
// buttons. pb-16 clears the fixed A11yMenu trigger, which this route carries with
// no CTA bar beneath it to reserve the space.
const pageClass = "mx-auto flex max-w-[640px] flex-col gap-6 px-4 pt-8 pb-16 md:px-6";

const CANCELLED = "cancelled";
// An unpaid deposit hold: the seat IS claimed and the money is not in. Neither
// cancelled nor standing, which is why it is its own branch and not a widening
// of either — the server carries a separate 409 code for the same reason.
const PENDING_PAYMENT = "pending_payment";

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
    // F20's three documents are NOT in the manage lookup payload, and empty
    // strings are the honest shape rather than a gap: this value only ever
    // reaches `ContactCard`, which reads the four contact fields above and
    // nothing else. `/privacy` and the booking form take their text from
    // `useBoutique()`, whose source is the real storefront fetch — a blank
    // legal document can never reach a reader from here.
    privacy_notice_text: "",
    privacy_dpa_text: "",
    privacy_subprocessors_text: "",
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

  // No dep array on purpose: the render that mounts a pending intent's target is
  // not one this effect can name in a dep list, so it has to get a look after
  // every commit.
  //
  // Which is exactly why the clear is CONDITIONAL on having a node, and must
  // stay that way. React runs passive effects in a task of their own, after
  // paint, so any render that commits between the tap and this flush arrives
  // while the target is still unmounted. Clearing there and calling `?.focus()`
  // on the null ref LOSES the move permanently — it does not delay it — and the
  // bride is left on a button that no longer exists (WCAG 2.4.3). Declining
  // costs one no-op pass and lets the render that does mount the node honour it.
  //
  // Deliberately unbounded, and safe for a narrower reason than "it cannot be
  // stranded". It can: tapping `keep` while an act() is in flight sets
  // `trigger`, a non-409 failure then swaps in the failed view and unmounts it,
  // and Retry can bring the trigger back. What holds is that an intent is only
  // ever honoured by a render that mounts the node SHE ASKED FOR, so the worst
  // case is a delayed correct move, never a wrong one — in that path focus was
  // on the Retry button that just unmounted, so the trigger is where it should
  // go anyway. Contrast /book, where the code field's mount condition is
  // derived from live input she keeps editing: there a held intent CAN become a
  // steal, and it is bounded in two places. Weigh the two failures: a lost move
  // ships silently and axe cannot see it; a delayed correct one is inert.
  useEffect(() => {
    const target = moveFocusTo.current;
    if (target === null) return;
    const node = {
      reveal: revealRef,
      trigger: cancelTriggerRef,
      done: doneRef,
      cancelled: cancelledRef,
    }[target].current;
    if (node === null) return;
    moveFocusTo.current = null;
    node.focus();
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
  const awaitingPayment = booking.status === PENDING_PAYMENT;
  // An unpaid hold whose time has gone is still an unpaid hold: "this has
  // passed" would be true and useless beside money that may still move.
  const past = !cancelled && !awaitingPayment && new Date(booking.starts_at).getTime() <= Date.now();
  const confirmed = booking.attendance_confirmed_at !== null;
  // Both verbs 409 BOOKING_AWAITING_PAYMENT on a hold, so the controls are
  // ABSENT rather than disabled — a disabled button still promises an action,
  // and there is nothing to word on one that cannot act.
  const actionable = !cancelled && !awaitingPayment && !past;

  return (
    <div className={pageClass}>
      <Heading />

      {/* Kept in the cancelled state too: she may need the date to rebook. */}
      <BookingFacts booking={booking} />

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

      {awaitingPayment && (
        <>
          <p className="max-w-[60ch] text-lg text-ink">{t("manage.awaitingPayment")}</p>
          {/* The hint is `invalidHint`'s, reused rather than duplicated (design
              P2): the lookup payload carries no checkout link — it is
              possession-authed and holds the appointment's facts and nothing
              else — so the phone is the whole of the way forward, and that is
              the sentence that already says so. */}
          <p className="max-w-[60ch] text-base text-ink-muted">{t("manage.invalidHint")}</p>
        </>
      )}

      {past && (
        <>
          <p className="text-base text-ink-muted">{t("manage.past")}</p>
          {/* A past appointment that really happened is still a calendar record
              worth keeping — design §4's P state. */}
          <IcsDownload source={{ transport: "token", token }} />
        </>
      )}

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
            <CancelReveal
              ref={revealRef}
              policy={policy}
              depositTaken={booking.deposit_taken}
              busy={busy === "cancel"}
              onConfirm={() => {
                void act("cancel", api.cancelBooking, "manage.cancelled", "cancelled");
              }}
              onKeep={() => {
                setRevealed(false);
                // Deferred to the layout effect: the trigger is UNMOUNTED while
                // the reveal is open, so its ref is null until the collapse has
                // rendered. Focusing it here would silently drop focus to <body>.
                moveFocusTo.current = "trigger";
              }}
            />
          )}

          {/* F24 D5's control, in the design's position: under the actions and
              above the policy line, and only on a state that CAN be added to a
              calendar. Cancelled and awaiting-payment render nothing — the
              server 409s regardless, and there is nothing to word on a control
              that cannot act (the manage A-state ruling). */}
          <IcsDownload source={{ transport: "token", token }} />

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