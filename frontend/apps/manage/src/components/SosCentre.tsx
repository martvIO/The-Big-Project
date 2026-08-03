import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge, Button, Card } from "@boutique/ui";
import { ApiError } from "../api";
import type { SosAlert } from "../api";
import { isolateBidi } from "../lib/booking";
import { elapsedLine } from "../lib/elapsed";
import { useSos } from "../lib/sos-context";

/**
 * F37. The SOS centre — a panel that is a TRIGGER 99% of the time and a list the
 * rest, rendered above the rooms because an active emergency outranks a room
 * list.
 *
 * **A CHILD of `FloorPanel`, not a sibling**, for three reasons that each rule
 * out the alternatives: it needs the staff list for the raise dialog's target
 * `Select` and `FloorPanel` already holds it; it needs `paused`, so
 * `FloorPanel`'s pause control does not lie; and it uses `FloorPanel`'s ONE
 * role="status" cue and its ONE SC 2.2.2 control, so the board gains no third
 * pause button.
 *
 * It takes its alerts from `useSos()` and not from a prop — the one place this
 * feature deliberately reaches past `FloorPanel`, because the alerts belong to
 * the app-level poll and there is exactly one of them.
 */

const ELEVATED = new Set(["owner", "shift_manager"]);

interface SosCentreProps {
  selfId: string;
  /** Cosmetics only: the control that exists is the server's own check. */
  role: string;
  /** `FloorPanel`'s `mode !== "running"`. Freezes the rendered list. */
  paused: boolean;
  onCue: (cue: { text: string; name: string | null }) => void;
  /** ⚠ The trigger ELEMENT travels up, because `FloorPanel` owns MOVE G. */
  onRaise: (trigger: HTMLButtonElement) => void;
}

export function SosCentre({
  selfId,
  role,
  paused,
  onCue,
  onRaise,
}: SosCentreProps) {
  const { t } = useTranslation();
  const sos = useSos();

  // ⚠ A LIST AND NOT ONE ID, which is F57's and F36's shipped shape and is here
  // for a reason the mutation regime found rather than a stylistic one: an
  // `if (busyId !== null) return;` guard turns a tap on a SECOND emergency,
  // while the first is still in flight, into a silent no-op — and a tap that
  // does nothing at all is the worst outcome this screen can produce. The
  // control's own `loading` → `disabled` is what stops a double tap on the SAME
  // row, and the provider's `mutate` counts rather than latches, so two rows in
  // flight is a supported state.
  const [busyIds, setBusyIds] = useState<readonly string[]>([]);
  // ⚠ ITS OWN PAIR (MOVE H). `FloorPanel` has exactly one `cardError`, one
  // `cardAlertRef` and one UNCONDITIONAL focus move on every non-null
  // transition — correct there, because its Button is disabled={disabled||
  // loading} so the browser already blurred the control. Shared, an SOS 409
  // would steal focus into a STAFF CARD's alert node through that guard-less
  // effect, and `cardError.id` is a staff-card id, so the render predicate would
  // collide semantically as well.
  const [rowError, setRowError] = useState<{
    id: string;
    text: string;
    name: string | null;
  } | null>(null);
  const rowAlertRef = useRef<HTMLParagraphElement>(null);
  const actedRef = useRef<string | null>(null);
  // ⚠ THE CUE IS FIRED FROM AN EFFECT AND NOT FROM THE HANDLER, and the reason
  // is a real hole rather than style. The provider's `mutate` returns `null` on
  // a SUCCESS **and** on a terminal 401/403 — «both mean the caller has nothing
  // left to render» — so a handler that announced on `failure === null` would
  // write «הקריאה נסגרה.» into a live region over a channel that had just died.
  // The provider's own setTerminal and this setState batch into ONE render, so
  // by the time the effect runs `sos.terminal` is the post-action truth.
  const [pendingCue, setPendingCue] = useState<string | null>(null);

  // ⚠ THE PAUSED FREEZE, and it is three lines that make the pause control's
  // claim true. `FloorPanel`'s control is named «השהיה — עדכון הצוות» and
  // governs the region it sits in — which after this feature contains a list fed
  // by a loop the pause does NOT stop. The overlay keeps rising while the board
  // is paused, and that is the safety property: pausing a VIEW must never
  // disable the CHANNEL.
  //
  // `serverNow` is snapshotted WITH the list, so a frozen row's «כבר 3 דק'»
  // freezes too — a minute counter still climbing beside a stopped freshness
  // stamp would be the panel disagreeing with itself.
  const snapshotRef = useRef<{ alerts: SosAlert[]; serverNow: string | null }>({
    alerts: sos.alerts,
    serverNow: sos.serverNow,
  });
  if (!paused) {
    snapshotRef.current = { alerts: sos.alerts, serverNow: sos.serverNow };
  }
  // (The snapshot stops advancing the moment `paused` turns on, which is what
  // the freeze IS: delete the guard above and the list keeps moving under a
  // control that says it stopped.)
  const frozen = snapshotRef.current;
  // ⚠ ONE EXEMPTION: an alert THIS STAFFER just raised. Both raise triggers are
  // on the floor section, the overlay never rises for her own page, and a frozen
  // list will not add it — so a staffer who paused the board and then raised
  // would see her own new alert NOWHERE, with a transient cue as her only
  // feedback. Keyed on `raised_by` rather than on a device-local set of ids,
  // which needs no plumbing and also covers her raising from a second device.
  const alerts = paused
    ? [
        ...frozen.alerts,
        ...sos.alerts.filter(
          (alert) =>
            alert.raised_by === selfId &&
            !frozen.alerts.some((seen) => seen.id === alert.id),
        ),
      ]
    : frozen.alerts;
  const serverNow = paused ? frozen.serverNow : sos.serverNow;

  // Oldest first — the same order as the overlay, so the two screens never
  // disagree about which emergency is next.
  const ordered = [...alerts].sort((a, b) =>
    a.created_at.localeCompare(b.created_at),
  );

  useEffect(() => {
    // MOVE H — the row's own alert takes focus, and ONLY when she is the one who
    // acted on that row. Keyed on the error state rather than raised in the
    // handler, because the alert node does not exist yet when setRowError runs.
    //
    // The two branches are one condition read on two engines: a real browser has
    // blurred the disabled control to <body>, jsdom has not and leaves it inside
    // the row. Anything else means she has moved on, and a 409 landing while she
    // is typing must not pull her out.
    if (rowError === null) {
      return;
    }
    if (actedRef.current !== rowError.id) {
      return;
    }
    const active = document.activeElement;
    const inside =
      active instanceof Element &&
      active.closest("[data-alert-id]")?.getAttribute("data-alert-id") ===
        rowError.id;
    if (active === document.body || inside) {
      rowAlertRef.current?.focus();
    }
  }, [rowError]);

  const refuse = (alert: SosAlert, failure: unknown, cancelling: boolean) => {
    if (failure instanceof ApiError) {
      const name = failure.details?.staff_display_name;
      if (failure.code === "SOS_ALREADY_ACCEPTED") {
        // ⚠ The asymmetry with resolve is the point: a colleague is already
        // walking to that curtain, and silently cancelling would send her to an
        // empty room and teach her that accepting means nothing. So the cancel's
        // sentence carries the remedy, and the remedy is one word over.
        const known = cancelling
          ? "sos.error.cancelAfterAccept"
          : "sos.error.SOS_ALREADY_ACCEPTED";
        const unknown = cancelling
          ? "sos.error.cancelAfterAcceptUnknown"
          : "sos.error.alreadyAcceptedUnknown";
        setRowError(
          name === undefined
            ? { id: alert.id, text: t(unknown), name: null }
            : { id: alert.id, text: t(known, { name }), name },
        );
        return;
      }
      if (failure.code === "SOS_CLOSED") {
        setRowError({
          id: alert.id,
          text: t("sos.error.SOS_CLOSED"),
          name: null,
        });
        return;
      }
      if (failure.status === 404) {
        // NOT terminal: an alert vanishing is a fact about the alert, not about
        // the viewer's access.
        setRowError({
          id: alert.id,
          text: t("sos.error.notFound"),
          name: null,
        });
        return;
      }
    }
    setRowError({
      id: alert.id,
      text: t("sos.error.actionFailed"),
      name: null,
    });
  };

  const act = async (
    alert: SosAlert,
    run: (alertId: string) => Promise<unknown>,
    cueKey: string,
    cancelling = false,
  ) => {
    setBusyIds((current) => [...current, alert.id]);
    setRowError(null);
    actedRef.current = alert.id;
    const failure = await run(alert.id);
    setBusyIds((current) => current.filter((id) => id !== alert.id));
    if (failure !== null) {
      refuse(alert, failure, cancelling);
      return;
    }
    setPendingCue(cueKey);
  };

  useEffect(() => {
    if (pendingCue === null) {
      return;
    }
    setPendingCue(null);
    if (sos.terminal !== null) {
      return;
    }
    onCue({ text: t(pendingCue), name: null });
  }, [pendingCue, sos.terminal, onCue, t]);

  const heading = (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h3 className="text-base font-semibold text-ink">
        {t("sos.centreHeading")}
      </h3>
      {/* ⚠ ALL FIVE ROLES, ALWAYS. Unlike every other control in this program it
          encodes NO permission: any of the five may raise, and the raise has
          exactly three failure modes, none of which is about the state of the
          boutique. */}
      <Button
        variant="danger"
        size="md"
        fullWidthMobile={false}
        onClick={(event) => onRaise(event.currentTarget)}
      >
        {t("sos.raise")}
      </Button>
    </div>
  );

  if (ordered.length === 0) {
    // ⚠ NO `Card` AND NO `EmptyState` — a deliberate divergence from the house
    // rule. `EmptyState` is `py-12` around a `font-display text-xl` centred
    // title: ≈140px of the visually loudest block on the floor screen saying
    // THERE IS NO EMERGENCY, on a screen a staffer reads fifty times a shift.
    // The condition `EmptyState` exists for is content that SHOULD be here and
    // is not; no alerts is the desired state. One muted line, ≈64px, and the
    // `Card` appears only when there is something to put in it.
    return (
      <section className="space-y-2">
        {heading}
        <p className="text-sm text-ink-muted">{t("sos.centreEmpty")}</p>
      </section>
    );
  }

  return (
    <section className="space-y-2">
      {heading}
      <Card>
        <ul className="divide-y divide-border">
          {ordered.map((alert) => {
            const open = alert.status === "open";
            const elevated = ELEVATED.has(role);
            // Which control EXISTS is the rendered form of the permission rules,
            // and it matters more here than anywhere: a 403 is TERMINAL for the
            // whole floor screen, and for the three floor roles that is the
            // entire product going dark. No disabled buttons, no lock glyphs —
            // absence.
            const mayAccept =
              open && (alert.target_staff_user_id === selfId || elevated);
            const mayResolve =
              alert.raised_by === selfId ||
              alert.accepted_by === selfId ||
              elevated;
            const mayCancel = open && (alert.raised_by === selfId || elevated);
            const name = alert.raised_by_name ?? t("sos.raiserGone");
            const busy = busyIds.includes(alert.id);
            return (
              <li
                key={alert.id}
                data-alert-id={alert.id}
                className="flex flex-col gap-3 py-4 sm:flex-row sm:items-start"
              >
                <div className="min-w-0 grow space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <bdi className="font-semibold break-words text-ink">
                      {name}
                    </bdi>
                    {/* ONE Badge per row and it is the STATUS WORD. Escalation
                        and the stall are words beside it, never a second pill
                        and never a colour change on the first. */}
                    <Badge variant={open ? "danger" : "neutral"}>
                      {t(open ? "sos.statusOpen" : "sos.statusAccepted")}
                    </Badge>
                  </div>
                  <p className="text-sm text-ink">
                    {alert.room_label === null ? (
                      t("sos.noRoom")
                    ) : (
                      <bdi>{alert.room_label}</bdi>
                    )}
                  </p>
                  {alert.note !== null && (
                    <p className="text-sm text-ink">
                      <bdi>{alert.note}</bdi>
                    </p>
                  )}
                  {serverNow !== null && (
                    // F36's shipped helper, reused unchanged — `rooms.elapsed` /
                    // `rooms.elapsedJustNow` across namespaces, deliberately,
                    // because `lib/elapsed.ts` hardcodes those keys and a second
                    // elapsed implementation is what the no-date-library rule
                    // forbids.
                    <p className="text-sm text-ink-muted">
                      {elapsedLine(t, serverNow, alert.created_at)}
                    </p>
                  )}
                  {!open && (
                    <p className="text-sm text-ink">
                      {alert.accepted_by_name === null
                        ? t("sos.acceptedByUnknown")
                        : isolateBidi(
                            t("sos.acceptedBy", {
                              name: alert.accepted_by_name,
                            }),
                            alert.accepted_by_name,
                          )}
                    </p>
                  )}
                  {alert.escalated && (
                    <p className="text-sm font-semibold text-danger">
                      {t("sos.escalated")}
                    </p>
                  )}
                  {alert.stalled && (
                    <p className="text-sm font-semibold text-danger">
                      {t("sos.stalled")}
                    </p>
                  )}
                  {rowError?.id === alert.id && (
                    <p
                      ref={rowAlertRef}
                      role="alert"
                      tabIndex={-1}
                      className="text-sm font-semibold text-warning-text"
                    >
                      {rowError.name === null
                        ? rowError.text
                        : isolateBidi(rowError.text, rowError.name)}
                    </p>
                  )}
                </div>
                <div className="flex flex-wrap justify-end gap-3">
                  {mayAccept && (
                    <Button
                      variant="secondary"
                      size="md"
                      fullWidthMobile={false}
                      loading={busy}
                      aria-label={t("sos.acceptAria", { name })}
                      onClick={() =>
                        void act(alert, sos.accept, "sos.acceptedCue")
                      }
                    >
                      {t("sos.accept")}
                    </Button>
                  )}
                  {mayResolve && (
                    <Button
                      variant="ghost"
                      size="md"
                      fullWidthMobile={false}
                      loading={busy}
                      aria-label={t("sos.resolveAria", { name })}
                      onClick={() =>
                        void act(alert, sos.resolve, "sos.resolvedCue")
                      }
                    >
                      {t("sos.resolve")}
                    </Button>
                  )}
                  {mayCancel && (
                    <Button
                      variant="ghost"
                      size="md"
                      fullWidthMobile={false}
                      loading={busy}
                      aria-label={t("sos.cancelAria", { name })}
                      onClick={() =>
                        void act(alert, sos.cancel, "sos.cancelledCue", true)
                      }
                    >
                      {t("sos.cancel")}
                    </Button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      </Card>
    </section>
  );
}
