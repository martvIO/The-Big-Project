import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Badge, Button, Card, Input, Modal, Price, Skeleton } from "@boutique/ui";
import { api, ApiError, errorMessage } from "../api";
import type { OwnerBookingDetail } from "../api";
import {
  bookingErrorText,
  isolateLtr,
  paymentActionKey,
  paymentBadge,
  statusBadge,
} from "../lib/booking";
import { jerusalemDate, jerusalemTime } from "../lib/jerusalem";
import { RescheduleDialog } from "./RescheduleDialog";

export interface BookingDetailProps {
  bookingId: string;
  onBack: () => void;
  onBookingChanged: (detail: OwnerBookingDetail) => void;
}

// Stacked at ≤767 and a two-column grid at ≥768 — the one breakpoint branch in
// the whole feature. `max-content` rather than a fixed width: CSS sizes the
// column from the longest label actually rendered, so it cannot drift when the
// copy is edited and cannot be wrong for the untranslated `ar` column, whose
// glyph metrics differ from the Hebrew.
function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col md:grid md:grid-cols-[max-content_1fr] md:gap-x-4">
      <span className="text-sm text-ink-muted">{label}</span>
      <span className="text-base text-ink">{children}</span>
    </div>
  );
}

// d.m.yyyy · HH:MM, both Jerusalem, one <bdi dir="ltr"> per numeric run.
function Instant({ value }: { value: string }) {
  return (
    <>
      <bdi dir="ltr">{jerusalemDate(value)}</bdi> · <bdi dir="ltr">{jerusalemTime(value)}</bdi>
    </>
  );
}

export function BookingDetail({ bookingId, onBack, onBookingChanged }: BookingDetailProps) {
  const { t } = useTranslation();
  const [detail, setDetail] = useState<OwnerBookingDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [cue, setCue] = useState<string | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [confirmingCancel, setConfirmingCancel] = useState(false);
  const [phoneEditing, setPhoneEditing] = useState(false);
  const [phoneDraft, setPhoneDraft] = useState("");
  const [phoneError, setPhoneError] = useState<string | null>(null);
  const [confirmingPhone, setConfirmingPhone] = useState(false);
  const [rescheduling, setRescheduling] = useState(false);

  const headingRef = useRef<HTMLHeadingElement | null>(null);
  const statusRef = useRef<HTMLParagraphElement | null>(null);
  const actionAlertRef = useRef<HTMLParagraphElement | null>(null);
  const phoneInputRef = useRef<HTMLInputElement | null>(null);
  const cancelTriggerRef = useRef<HTMLButtonElement | null>(null);
  const phoneTriggerRef = useRef<HTMLButtonElement | null>(null);
  const rescheduleTriggerRef = useRef<HTMLButtonElement | null>(null);
  const wasCancelOpen = useRef(false);
  const wasPhoneOpen = useRef(false);
  const wasRescheduleOpen = useRef(false);

  useEffect(() => {
    let cancelled = false;
    api
      .getBooking(bookingId)
      .then((loaded) => {
        if (!cancelled) {
          setDetail(loaded);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          // A 404 is also what another tenant's id answers under RLS — the two
          // are indistinguishable by design, so they read the same.
          setLoadError(
            error instanceof ApiError && error.code === "NOT_FOUND"
              ? t("booking.notFound")
              : errorMessage(error),
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, [bookingId, t]);

  // The owner hears where she landed when a row opens the detail.
  useEffect(() => {
    headingRef.current?.focus();
  }, [bookingId]);

  // A successful transition can unmount the very control that was clicked, so
  // focus must never be allowed to drop to <body>.
  useEffect(() => {
    if (cue !== null) {
      statusRef.current?.focus();
    }
  }, [cue]);

  // The symmetric half, and the one that was missing. Only the SUCCESS path had
  // a rescue: every action button carries `disabled={busy}`, which blurs it the
  // instant it is tapped, and the cancel/phone Modals unmount in the very commit
  // that disables their trigger — so the restore effects below call .focus() on
  // a disabled element, which is a no-op. On failure focus therefore sat on
  // <body>: the next Tab restarted at the skip link (WCAG 2.4.3). Keyed on the
  // error rather than on `pending`, so it runs on the render that carries the
  // answer, after `busy` has cleared.
  useEffect(() => {
    if (actionError !== null) {
      actionAlertRef.current?.focus();
    }
  }, [actionError]);

  // The server's 400 on the number renders in the Input's own error slot, not
  // in the shared alert, so this path needs its own destination.
  useEffect(() => {
    if (phoneError !== null) {
      phoneInputRef.current?.focus();
    }
  }, [phoneError]);

  // Native <dialog> returns focus to whatever had it, which after a re-render
  // may be nothing at all — DressEditor.tsx:130-136 records the same fix.
  useEffect(() => {
    if (wasCancelOpen.current && !confirmingCancel) {
      cancelTriggerRef.current?.focus();
    }
    wasCancelOpen.current = confirmingCancel;
  }, [confirmingCancel]);

  useEffect(() => {
    if (wasPhoneOpen.current && !confirmingPhone) {
      phoneTriggerRef.current?.focus();
    }
    wasPhoneOpen.current = confirmingPhone;
  }, [confirmingPhone]);

  useEffect(() => {
    if (wasRescheduleOpen.current && !rescheduling) {
      rescheduleTriggerRef.current?.focus();
    }
    wasRescheduleOpen.current = rescheduling;
  }, [rescheduling]);

  const runAction = async (
    key: string,
    call: () => Promise<OwnerBookingDetail>,
    cueKey: string,
  ) => {
    setPending(key);
    setActionError(null);
    setCue(null);
    try {
      const next = await call();
      // Every mutation answers the same OwnerBookingDetail, so the screen
      // re-renders from the response and never from what the client hoped.
      setDetail(next);
      onBookingChanged(next);
      setCue(t(cueKey));
    } catch (error) {
      setActionError(bookingErrorText(error, t));
    } finally {
      setPending(null);
    }
  };

  const submitPhone = async () => {
    setConfirmingPhone(false);
    setPending("phone");
    setActionError(null);
    setPhoneError(null);
    setCue(null);
    try {
      // Exactly as typed: there is no client-side normalizer (D20).
      const next = await api.correctBookingPhone(bookingId, phoneDraft);
      setDetail(next);
      onBookingChanged(next);
      setPhoneEditing(false);
      setPhoneDraft("");
      setCue(t("booking.phoneDone"));
    } catch (error) {
      if (error instanceof ApiError && error.status === 400) {
        // The server's 400 is the only authority on the number, and its message
        // belongs beside the field it is about.
        setPhoneError(errorMessage(error));
      } else {
        setActionError(bookingErrorText(error, t));
      }
    } finally {
      setPending(null);
    }
  };

  const badge = detail === null ? null : statusBadge(detail.status);
  // The clock split is a fact about the appointment, not a permission — the
  // server stays the authority and an action that races it still 409s.
  const future = detail !== null && new Date(detail.starts_at).getTime() > Date.now();
  const liveConfirmed = detail?.status === "confirmed" && future;
  const pastConfirmed = detail?.status === "confirmed" && !future;
  const isNoShow = detail?.status === "no_show";
  const isCompleted = detail?.status === "completed";
  const isCancelled = detail?.status === "cancelled";
  // The sixth branch. A `pending_payment` booking satisfied none of the five
  // above, so this panel used to render with no state and no action set at all.
  const isAwaitingPayment = detail?.status === "pending_payment";
  // MD1: the deposit is held and the appointment is gone. This is the one
  // cancelled booking that is not a dead end — `owner.reschedule` is widened to
  // admit it, restoring the booking in the same UPDATE that moves it.
  const cancelledPaid = isCancelled && detail?.payment_status === "paid";
  const paymentAction =
    detail === null ? null : paymentActionKey(detail.status, detail.payment_status);
  const busy = pending !== null;

  return (
    <div className="space-y-6">
      {/* First in reading order. size="md" deliberately: size="sm"'s min-h-9 is
          under the 44px floor. */}
      <Button variant="ghost" size="md" onClick={onBack}>
        {t("booking.back")}
      </Button>

      <div className="flex flex-wrap items-center gap-3">
        {/* Never the bride's name: a name in the announced heading is PII in the
            landmark, and it is the first fact row one line below anyway. */}
        <h2 ref={headingRef} tabIndex={-1} className="text-lg font-semibold text-ink">
          {t("booking.detailTitle")}
        </h2>
        {badge !== null && (
          <Badge variant={badge.variant} data-testid="booking-status">
            {t(badge.labelKey)}
          </Badge>
        )}
      </div>

      {/* The ONE announced region: the loading text, then the success cues, then
          empty again. Also the focus destination after a transition. */}
      <p
        role="status"
        tabIndex={-1}
        ref={statusRef}
        data-testid="booking-cue"
        className="text-sm text-ink-muted"
      >
        {detail === null && loadError === null ? t("booking.detailLoading") : (cue ?? "")}
      </p>

      {loadError !== null && (
        <p role="alert" className="text-sm text-ink-muted">
          {loadError}
        </p>
      )}

      {detail === null && loadError === null && <Skeleton variant="text" lines={4} />}

      {detail !== null && (
        <>
          <Card className="space-y-4">
            <h3 className="text-base font-semibold text-ink">{t("booking.customerHeading")}</h3>
            <Fact label={t("booking.customerName")}>
              {/* Bare bdi: dir="ltr" on Hebrew free text is itself a bidi
                  defect, and it is the worse one because it looks deliberate. */}
              <bdi>{detail.customer_name}</bdi>
            </Fact>
            <Fact label={t("booking.customerPhone")}>
              <bdi dir="ltr">{detail.customer_phone}</bdi>
            </Fact>

            {liveConfirmed &&
              (phoneEditing ? (
                <div className="space-y-3">
                  <Input
                    ref={phoneInputRef}
                    label={t("booking.phoneFieldLabel")}
                    dir="ltr"
                    type="tel"
                    inputMode="tel"
                    className="max-w-[240px]"
                    // Opens EMPTY on purpose: a pre-filled wrong number invites
                    // a one-character edit of the value she is replacing.
                    value={phoneDraft}
                    error={phoneError ?? undefined}
                    disabled={busy}
                    onChange={(event) => setPhoneDraft(event.target.value)}
                  />
                  <div className="flex flex-wrap gap-2">
                    <Button
                      ref={phoneTriggerRef}
                      variant="secondary"
                      size="md"
                      disabled={busy}
                      onClick={() => setConfirmingPhone(true)}
                    >
                      {t("booking.phoneSaveCta")}
                    </Button>
                    <Button
                      variant="ghost"
                      size="md"
                      disabled={busy}
                      onClick={() => {
                        setPhoneEditing(false);
                        setPhoneError(null);
                      }}
                    >
                      {t("booking.phoneEditCancel")}
                    </Button>
                  </div>
                </div>
              ) : (
                <Button
                  variant="secondary"
                  size="md"
                  disabled={busy}
                  onClick={() => {
                    setPhoneEditing(true);
                    setPhoneDraft("");
                    setPhoneError(null);
                  }}
                >
                  {t("booking.phoneEditCta")}
                </Button>
              ))}

            <div className="space-y-4 border-t border-border pt-4">
              <h3 className="text-base font-semibold text-ink">
                {t("booking.appointmentHeading")}
              </h3>
              <Fact label={t("booking.when")}>
                <Instant value={detail.starts_at} />
              </Fact>
              <Fact label={t("booking.type")}>
                <bdi>{detail.appointment_type_name}</bdi>
              </Fact>
              {detail.dress_name !== null && (
                <Fact label={t("booking.dress")}>
                  <bdi>{detail.dress_name}</bdi>
                  {detail.dress_size !== null && (
                    <>
                      {" · "}
                      {/* Bare bdi, with the free text and not the numeric runs:
                          `dress_size` snapshots `dress_variants.size_label`,
                          unbounded owner-typed TEXT with no numeric constraint,
                          so «מידה 36» renders its digits on the wrong side under
                          dir="ltr". dir=auto still resolves a plain "36" LTR.
                          The storefront already reads it this way. */}
                      {t("booking.dressSize")} <bdi>{detail.dress_size}</bdi>
                    </>
                  )}
                </Fact>
              )}
              <Fact label={t("booking.seat")}>
                <bdi dir="ltr">{String(detail.seat_index)}</bdi>
              </Fact>
              <Fact label={t("booking.createdAt")}>
                <Instant value={detail.created_at} />
              </Fact>
              {/* ONE Fact, TWO bodies. F50 made both terms columns nullable, as
                  a PAIR, so a walk-in has no evidence to show — and the honest
                  answer is a sentence naming the absence, not a Fact rendering
                  «גרסה null» beside jerusalemDate(null). The row is not dropped:
                  a missing label would read as "the screen forgot", which is the
                  ambiguity `source` exists to remove. */}
              <Fact label={t("booking.terms")}>
                {detail.terms_version_accepted === null || detail.terms_accepted_at === null ? (
                  t("booking.termsNone")
                ) : (
                  <>
                    {isolateLtr(
                      t("booking.termsVersion", { version: detail.terms_version_accepted }),
                      String(detail.terms_version_accepted),
                    )}
                    {" · "}
                    <bdi dir="ltr">{jerusalemDate(detail.terms_accepted_at)}</bdi>
                  </>
                )}
              </Fact>
              <Fact label={t("booking.manageLink")}>
                {/* Words, never a chip — one Badge per screen region, and the
                    status owns it. The hash itself never reaches the wire. */}
                {detail.manage_link_issued
                  ? t("booking.manageLinkIssued")
                  : t("booking.manageLinkMissing")}
              </Fact>
              {detail.checked_in_at !== null && (
                // F34 D6. The detail STATES the arrival; the action lives on
                // the board, one place. Spelled «נרשמה הגעה» rather than
                // «הגיעה» so a booking marked no_show after a check-in — which
                // D5 permits, since a status transition never clears the
                // column — reads as two true facts about different things.
                <Fact label={t("booking.checkedInAt")}>
                  <Instant value={detail.checked_in_at} />
                </Fact>
              )}
              {detail.cancelled_at !== null && (
                <Fact label={t("booking.cancelledAt")}>
                  <Instant value={detail.cancelled_at} />
                </Fact>
              )}
              {detail.cancelled_by !== null && (
                <Fact label={t("booking.cancelledBy")}>
                  {detail.cancelled_by === "owner"
                    ? t("booking.cancelledByOwner")
                    : t("booking.cancelledByCustomer")}
                </Fact>
              )}
              {/* D18. A second Badge on the screen, in a different region from
                  the status chip that owns the heading — the money fact is not
                  a restatement of the appointment's state, and on exactly the
                  two rows below the two disagree. */}
              {detail.payment_status !== null && (
                <Fact label={t("booking.payment")}>
                  <Badge
                    variant={paymentBadge(detail.payment_status).variant}
                    data-testid="booking-payment"
                  >
                    {t(paymentBadge(detail.payment_status).labelKey)}
                  </Badge>
                </Fact>
              )}
              {/* A1/D15: integer agorot on the wire, divided by 100 exactly
                  once, inside <Price>, which already isolates the run. */}
              {detail.refund_due_agorot !== null && (
                <Fact label={t("booking.refundDue")}>
                  <Price agorot={detail.refund_due_agorot} visible hiddenLabel="" />
                </Fact>
              )}
              {paymentAction !== null && (
                // Not role="alert": nothing just happened, this is a standing
                // fact about the row. Colour is not the signal either — the
                // sentence opens «דרושה פעולה».
                <p data-testid="booking-payment-action" className="text-sm text-danger">
                  {t(paymentAction)}
                </p>
              )}
            </div>

            <div className="space-y-2 border-t border-border pt-4">
              {/* Kept last: the only free-text block, and it may be long. */}
              <h3 className="text-base font-semibold text-ink">{t("booking.notesHeading")}</h3>
              {detail.notes === null ? (
                <p className="text-sm text-ink-muted">{t("booking.notesEmpty")}</p>
              ) : (
                // booking-core.md:173 names F15: text, and only text. React
                // escapes by default and the rule is that F15 never opts out —
                // no dangerouslySetInnerHTML, no markdown pass, no linkification.
                <p
                  data-testid="booking-notes"
                  className="whitespace-pre-wrap text-base text-ink"
                >
                  <bdi>{detail.notes}</bdi>
                </p>
              )}
            </div>
          </Card>

          <Card className="space-y-4">
            <h3 className="text-base font-semibold text-ink">{t("booking.actionsHeading")}</h3>

            {cancelledPaid ? (
              // MD1. «תור שבוטל אינו ניתן לשחזור» is FALSE on this one row from
              // the day the widened writer merges, and it would otherwise render
              // directly above the button that disproves it.
              <>
                <p className="text-sm text-ink-muted">{t("booking.cancelledPaidActions")}</p>
                <p className="text-sm text-ink-muted">{t("booking.deliveryNotice")}</p>
                <Button
                  // The same ref as the live-confirmed trigger below, on
                  // purpose: the two branches are mutually exclusive, and after
                  // a successful restore the ref follows the control that
                  // replaces this one — so the dialog's focus return lands on a
                  // real button instead of <body>.
                  ref={rescheduleTriggerRef}
                  variant="secondary"
                  size="md"
                  fullWidthMobile
                  disabled={busy}
                  onClick={() => setRescheduling(true)}
                >
                  {t("booking.rescheduleRestoreCta")}
                </Button>
              </>
            ) : isCancelled ? (
              // `cancelled` with no deposit held is terminal and owner-created
              // bookings are out of scope, so the honest remedy is the
              // storefront rebook.
              <p className="text-sm text-ink-muted">{t("booking.cancelledNoActions")}</p>
            ) : isAwaitingPayment ? (
              // The sixth branch. NO owner actions: confirm-attendance, cancel,
              // no-show, complete, reschedule and resend all 409 on an unpaid
              // hold, and the sweeper frees the seat on its own clock — so a
              // control here would be a trap and a disabled one an unexplained
              // wall.
              <p className="text-sm text-ink-muted">{t("booking.awaitingPaymentNoActions")}</p>
            ) : (
              <>
                {/* The Risk 3(a) discharge, stated positively once. Muted, not
                    warning colour: a permanent property of the platform is not
                    an alarm about something that happened. */}
                <p className="text-sm text-ink-muted">{t("booking.deliveryNotice")}</p>

                {actionError !== null && (
                  <p
                    role="alert"
                    tabIndex={-1}
                    ref={actionAlertRef}
                    className="text-sm text-danger"
                  >
                    {actionError}
                  </p>
                )}

                {/* Controls are ABSENT, not disabled, for transitions the D3
                    graph forbids: rendering buttons that answer 409 is a trap,
                    and a disabled button with no explanation is worse. */}
                <div className="flex flex-col gap-3">
                  {liveConfirmed && (
                    <>
                      <Button
                        ref={rescheduleTriggerRef}
                        variant="secondary"
                        size="md"
                        fullWidthMobile
                        disabled={busy}
                        onClick={() => setRescheduling(true)}
                      >
                        {t("booking.rescheduleCta")}
                      </Button>
                      <div className="space-y-1">
                        <Button
                          variant="secondary"
                          size="md"
                          fullWidthMobile
                          disabled={busy}
                          onClick={() =>
                            void runAction(
                              "resend",
                              () => api.resendBookingLink(bookingId),
                              "booking.resendDone",
                            )
                          }
                        >
                          {t("booking.resendCta")}
                        </Button>
                        {/* Pre-tap, because resend gets no confirm Modal and
                            D9 requires the Hebrew to say the old link dies. */}
                        <p className="text-xs text-ink-muted">{t("booking.resendHint")}</p>
                      </div>
                    </>
                  )}

                  {(pastConfirmed || isCompleted) && (
                    <Button
                      variant="secondary"
                      size="md"
                      fullWidthMobile
                      disabled={busy}
                      onClick={() =>
                        void runAction(
                          "no_show",
                          () => api.noShowBooking(bookingId),
                          "booking.noShowDone",
                        )
                      }
                    >
                      {t("booking.noShowCta")}
                    </Button>
                  )}

                  {(pastConfirmed || isNoShow) && (
                    <Button
                      variant="secondary"
                      size="md"
                      fullWidthMobile
                      disabled={busy}
                      onClick={() =>
                        void runAction(
                          "complete",
                          () => api.completeBooking(bookingId),
                          "booking.completeDone",
                        )
                      }
                    >
                      {t("booking.completeCta")}
                    </Button>
                  )}

                  {(isNoShow || isCompleted) && (
                    <Button
                      variant="secondary"
                      size="md"
                      fullWidthMobile
                      disabled={busy}
                      onClick={() =>
                        void runAction(
                          "confirm",
                          () => api.confirmBooking(bookingId),
                          "booking.reopenDone",
                        )
                      }
                    >
                      {t("booking.reopenCta")}
                    </Button>
                  )}
                </div>

                {liveConfirmed && (
                  // Visually separated, last, and a SOLID danger Button — never
                  // ghost + className="text-danger": no such variant exists and
                  // the override loses the cascade (design F-6).
                  <div className="border-t border-border pt-4">
                    <Button
                      ref={cancelTriggerRef}
                      variant="danger"
                      size="md"
                      fullWidthMobile
                      disabled={busy}
                      onClick={() => setConfirmingCancel(true)}
                    >
                      {t("booking.cancelCta")}
                    </Button>
                  </div>
                )}
              </>
            )}
          </Card>

          {confirmingCancel && (
            <Modal
              open
              onClose={() => setConfirmingCancel(false)}
              title={t("booking.cancelModalTitle")}
              footer={
                <>
                  <Button variant="ghost" size="md" onClick={() => setConfirmingCancel(false)}>
                    {t("booking.modalKeep")}
                  </Button>
                  <Button
                    variant="danger"
                    size="md"
                    onClick={() => {
                      setConfirmingCancel(false);
                      void runAction(
                        "cancel",
                        () => api.cancelBooking(bookingId),
                        "booking.cancelDone",
                      );
                    }}
                  >
                    {t("booking.cancelConfirm")}
                  </Button>
                </>
              }
            >
              {t("booking.cancelModalBody")}
            </Modal>
          )}

          {confirmingPhone && (
            <Modal
              open
              onClose={() => setConfirmingPhone(false)}
              title={t("booking.phoneModalTitle")}
              footer={
                <>
                  <Button variant="ghost" size="md" onClick={() => setConfirmingPhone(false)}>
                    {t("booking.modalKeep")}
                  </Button>
                  <Button size="md" onClick={() => void submitPhone()}>
                    {t("booking.phoneModalConfirm")}
                  </Button>
                </>
              }
            >
              {/* The number is echoed AS TYPED so the Modal is a proofreading
                  step, and the body states that the platform does not verify
                  it — owner-attested, no OTP (D8). */}
              {isolateLtr(t("booking.phoneModalBody", { phone: phoneDraft }), phoneDraft)}
            </Modal>
          )}

          {rescheduling && (
            <RescheduleDialog
              booking={detail}
              onClose={() => setRescheduling(false)}
              onRescheduled={(next) => {
                setRescheduling(false);
                setDetail(next);
                onBookingChanged(next);
                // MD1: off `cancelled` the same UPDATE also restores the
                // booking, so a restore at the SAME time is a real change that
                // the starts_at comparison below cannot see — and the branch
                // that renders the trigger unmounts with it, so without a cue
                // the focus rescue has nothing to move to and lands on <body>.
                if (next.status !== detail.status) {
                  setCue(t("booking.rescheduleRestoreDone"));
                  return;
                }
                // The booking's own time is always present and pre-selected
                // (D6), so re-submitting it unchanged is one tap away and the
                // server short-circuits it to a no-op 200 — no audit row, no
                // send. Announcing «המועד עודכן» there would state a state
                // change that did not happen. Compared against the RESPONSE,
                // not against what the dialog asked for.
                if (next.starts_at !== detail.starts_at) {
                  setCue(t("booking.rescheduleDone"));
                }
              }}
            />
          )}
        </>
      )}
    </div>
  );
}
