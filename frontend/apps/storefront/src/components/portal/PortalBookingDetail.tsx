import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, ButtonLink, Skeleton, VisuallyHidden } from "@boutique/ui";
import { ApiError, api } from "../../api";
import type { ManageBookingResponse } from "../../api";
import { BookingFacts, PolicyLine } from "../booking/BookingFacts";
import { CancelReveal } from "../booking/CancelReveal";
import { IcsDownload } from "../booking/IcsDownload";

// The portal's booking detail (design §4). It renders the SAME
// `ManageBookingResponse` through the SAME three components the tokenized page
// uses — extracted, not forked (F-P3) — so the manage-booking states table
// applies verbatim: L / L2 / C / P / A / R.
//
// The one thing this page must keep from that one is the state PRECEDENCE: a
// 409 re-renders from the RESPONSE, never from what the tap hoped for.

const CANCELLED = "cancelled";
const PENDING_PAYMENT = "pending_payment";
const COMPLETED = "completed";

type View =
  | { kind: "loading" }
  | { kind: "loaded"; data: ManageBookingResponse }
  // Unknown id or another customer's — the house 404, one body for both, so
  // there is no cross-customer existence oracle.
  | { kind: "notFound" }
  | { kind: "failed" };

interface PortalBookingDetailProps {
  bookingId: string;
  onBack: () => void;
  onExpired: () => void;
  onAnnounce: (key: string) => void;
}

export function PortalBookingDetail({
  bookingId,
  onBack,
  onExpired,
  onAnnounce,
}: PortalBookingDetailProps) {
  const { t } = useTranslation();
  const [view, setView] = useState<View>({ kind: "loading" });
  const [revealed, setRevealed] = useState(false);
  const [busy, setBusy] = useState<"attend" | "cancel" | null>(null);

  const revealRef = useRef<HTMLParagraphElement | null>(null);
  const cancelTriggerRef = useRef<HTMLButtonElement | null>(null);
  const doneRef = useRef<HTMLParagraphElement | null>(null);
  const cancelledRef = useRef<HTMLParagraphElement | null>(null);
  const moveFocusTo = useRef<"done" | "cancelled" | "reveal" | "trigger" | null>(null);

  const load = useCallback(async () => {
    setView({ kind: "loading" });
    try {
      setView({ kind: "loaded", data: await api.portalBooking(bookingId) });
    } catch (error: unknown) {
      if (error instanceof ApiError && error.status === 401) {
        onExpired();
        return;
      }
      setView(
        error instanceof ApiError && error.status === 404
          ? { kind: "notFound" }
          : { kind: "failed" },
      );
    }
  }, [bookingId, onExpired]);

  useEffect(() => {
    void load();
  }, [load]);

  // No dep array on purpose, and the clear is CONDITIONAL on having a node —
  // ManageBookingPage's reasoning verbatim: React runs passive effects after
  // paint, so a render that commits between the tap and this flush arrives
  // while the target is still unmounted, and clearing there LOSES the move
  // permanently instead of delaying it.
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
    call: (id: string) => Promise<ManageBookingResponse>,
    announce: string,
    focus: "done" | "cancelled",
  ) => {
    setBusy(which);
    try {
      const data = await call(bookingId);
      setRevealed(false);
      onAnnounce(announce);
      moveFocusTo.current = focus;
      setView({ kind: "loaded", data });
    } catch (error: unknown) {
      if (error instanceof ApiError && error.status === 401) {
        onExpired();
        return;
      }
      if (error instanceof ApiError && error.status === 409) {
        // The clock or another device won. Re-render from the SERVER's state
        // rather than from what this tap hoped for.
        setRevealed(false);
        await load();
        return;
      }
      setView(
        error instanceof ApiError && error.status === 404
          ? { kind: "notFound" }
          : { kind: "failed" },
      );
    } finally {
      setBusy(null);
    }
  };

  const back = (
    <div className="flex">
      {/* `md` without exception: `sm` is min-h-9 = 36px, under the house 44px
          touch floor (F-W1). */}
      <ButtonLink
        href="/portal"
        variant="ghost"
        size="md"
        onClick={(event) => {
          event.preventDefault();
          onBack();
        }}
      >
        {t("portal.backToList")}
      </ButtonLink>
    </div>
  );

  if (view.kind === "loading") {
    return (
      <div className="flex flex-col gap-6">
        {back}
        <VisuallyHidden>
          <span role="status">{t("portal.loadingBookings")}</span>
        </VisuallyHidden>
        <Skeleton variant="text" lines={3} />
      </div>
    );
  }

  if (view.kind === "notFound") {
    // No facts and no distinction from "never existed" — the anti-oracle rule
    // the server holds, rendered.
    return (
      <div className="flex flex-col gap-6">
        {back}
        <p className="max-w-[60ch] text-lg text-ink">{t("errors.notFound")}</p>
      </div>
    );
  }

  if (view.kind === "failed") {
    return (
      <div className="flex flex-col gap-6">
        {back}
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
      </div>
    );
  }

  const { booking, policy } = view.data;
  const cancelled = booking.status === CANCELLED;
  const awaitingPayment = booking.status === PENDING_PAYMENT;
  const past = !cancelled && !awaitingPayment && new Date(booking.starts_at).getTime() <= Date.now();
  const confirmed = booking.attendance_confirmed_at !== null;
  const actionable = !cancelled && !awaitingPayment && !past;
  // Design §4: the control renders on L and L2, and on a past `completed`.
  // Cancelled and awaiting-payment render nothing — the server 409s regardless.
  const downloadable = actionable || (past && booking.status === COMPLETED);

  return (
    <div className="flex flex-col gap-6">
      {back}
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
          <p className="max-w-[60ch] text-base text-ink-muted">{t("manage.invalidHint")}</p>
        </>
      )}

      {past && <p className="text-base text-ink-muted">{t("manage.past")}</p>}

      {actionable && (
        <>
          <div className="flex flex-col gap-3 sm:flex-row">
            {confirmed ? (
              <p ref={doneRef} tabIndex={-1} className="text-lg font-semibold text-success">
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
                  void act("attend", api.portalConfirmAttendance, "manage.attendanceDone", "done");
                }}
              >
                {t("manage.attendanceCta")}
              </Button>
            )}

            {/* Cancel STAYS available after attendance is confirmed (design
                P3): confirming is a courtesy signal, not a lock-in. */}
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

          {revealed && (
            <CancelReveal
              ref={revealRef}
              policy={policy}
              depositTaken={booking.deposit_taken}
              busy={busy === "cancel"}
              onConfirm={() => {
                void act("cancel", api.portalCancel, "manage.cancelled", "cancelled");
              }}
              onKeep={() => {
                setRevealed(false);
                moveFocusTo.current = "trigger";
              }}
            />
          )}
        </>
      )}

      {downloadable && <IcsDownload source={{ transport: "portal", bookingId }} />}

      {!revealed && actionable && policy !== null && (
        <PolicyLine hours={policy.refundable_until_hours_before} />
      )}
    </div>
  );
}
