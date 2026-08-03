import { useEffect, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, useToast } from "@boutique/ui";
import { ApiError } from "../api";
import type { SosAlert } from "../api";
import { isolateBidi, isolateLtr } from "../lib/booking";
import { jerusalemTime } from "../lib/jerusalem";
import { useSos } from "../lib/sos-context";

/**
 * F37. The full-screen emergency alert — the only surface in this console that
 * appears UNBIDDEN, on all thirteen sections, over whatever the staffer was
 * doing.
 *
 * ⚠ IT IS VISUALLY BLOCKING AND INTERACTIVELY NON-BLOCKING, and that asymmetry
 * is the whole resolution of «impossible to miss» against «must not steal
 * focus». It is NOT a <dialog>, NOT showModal() and NOT `inert` on the console —
 * each of those moves focus BY DEFINITION and would destroy a receptionist's
 * half-typed phone number. A pointer user's next tap lands on the overlay and
 * she dismisses it in one tap with no state lost; a keyboard user's caret never
 * moves and her form is intact. Nobody loses work; nobody misses the alert.
 *
 * ⚠ AND THE HAZARD THAT ASYMMETRY CREATES, named rather than left implicit: she
 * is now typing into a field she cannot see. The trade is taken deliberately —
 * the ruling says full-screen red, a band is missable on a 375px phone held
 * inside a curtain, and losing her keystrokes is worse than obscuring them for
 * the seconds it takes to press Esc twice or tap «הסתרה».
 *
 * ⚠ THE RED IS THE FIELD; EACH CARD IS PAPER, and the reason is four measured
 * numbers rather than a preference. On --color-danger #A03232: --color-focus is
 * 1.22:1 — and `focusRing` is drawn at outline-offset-2, i.e. ON WHATEVER IS
 * BEHIND THE CONTROL, so the console's only focus indicator would be invisible
 * on an emergency ack (WCAG 2.4.7, legally binding, and axe cannot report it
 * because its contrast rule computes an element against its OWN background);
 * --color-ink is 2.25:1 (every shipped secondary/ghost label, every Badge);
 * `Button danger`'s own fill is 1.00:1. Only --color-surface-raised passes, at
 * 7.01:1. Full-screen red survives literally — the field fills the viewport —
 * and the words move onto paper where the whole shipped vocabulary works.
 */

// Whether the alert should be RISING on this device. `for_me` is derived on the
// server, per row, against the one `server_now` the envelope carries — deriving
// it here would put the audience rule in the product twice, in two languages.
function isRising(alert: SosAlert): boolean {
  return alert.for_me;
}

/**
 * ⚠ THE DISMISS KEY IS COMPOSITE AND NOT THE BARE ID.
 *
 * A role-targeted page is `for_me` for an elevated caller from t=0, so a shift
 * manager can dismiss at t=2s — and with a bare id the card would still be
 * hidden when `escalated` flips at t=30s and would NEVER re-rise, defeating the
 * safety net for the exact audience escalation targets. In a boutique with one
 * shift manager on the floor that is the whole audience gone on one tap, before
 * the net can fire. With this key, escalation and the stall each re-rise the
 * card exactly once and a second dismiss silences it again.
 */
function dismissKey(alert: SosAlert): string {
  return `${alert.id}:${alert.escalated}:${alert.stalled}`;
}

// Which card, if any, currently holds focus.
function focusedCardId(): string | null {
  const active = document.activeElement;
  if (!(active instanceof Element)) {
    return null;
  }
  return active.closest("[data-alert-id]")?.getAttribute("data-alert-id") ?? null;
}

export function SosOverlay() {
  const { t } = useTranslation();
  const toast = useToast();
  const { alerts, terminal, channelDown, accept } = useSos();

  const [dismissed, setDismissed] = useState<readonly string[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);
  // Carries the interpolated NAME beside its text: the name renders inside a
  // bare <bdi> and a flat string cannot say where it starts.
  const [cardError, setCardError] = useState<{ id: string; text: string; name: string | null } | null>(
    null,
  );

  const baseId = useId();
  const cardRefs = useRef(new Map<string, HTMLElement | null>());
  const acceptRefs = useRef(new Map<string, HTMLButtonElement | null>());
  const alertRef = useRef<HTMLParagraphElement>(null);
  const overlayRef = useRef<HTMLDivElement>(null);
  // Set by the accept handler, read by MOVE D. «She tapped THIS card's control»
  // is a fact about an intent and cannot be recovered from the DOM afterwards,
  // because Button is disabled={disabled||loading} and the browser has already
  // blurred it by the time the response lands.
  const actedRef = useRef<string | null>(null);
  const renderedIdsRef = useRef<readonly string[]>([]);
  const departingRef = useRef<{ nextId: string | null } | null>(null);
  const hadCardsRef = useRef(false);

  // Oldest first — the longest-waiting emergency is the one to answer, and
  // escalated cards are therefore at the top of the stack with no second sort
  // and no special case. ISO instants compare lexicographically.
  const rising = alerts
    .filter((alert) => isRising(alert) && !dismissed.includes(dismissKey(alert)))
    .sort((a, b) => a.created_at.localeCompare(b.created_at));
  const hiddenLive = alerts.filter(
    (alert) => isRising(alert) && dismissed.includes(dismissKey(alert)),
  );

  const risingIds = rising.map((alert) => alert.id);
  // The three effects below key on the IDENTITY OF THE LIST and never on the
  // array object, which is rebuilt every render. Mirrored through a ref so the
  // dependency array stays one statically-checkable value — and so the Esc
  // listener reads the CURRENT first card rather than the one it closed over.
  const risingKey = risingIds.join();
  const risingIdsRef = useRef<readonly string[]>(risingIds);
  risingIdsRef.current = risingIds;

  // ⚠ THIS RUNS DURING RENDER, because this is the only moment the old DOM and
  // the new list exist together: by the time an effect runs the departing card
  // is already gone, activeElement has dropped to <body>, and the question
  // «was focus inside the card that left?» cannot be asked any more.
  // RoomsPanel.tsx and FloorPanel.load do exactly this, for exactly this reason.
  if (renderedIdsRef.current.join() !== risingIds.join()) {
    const previous = renderedIdsRef.current;
    const held = focusedCardId();
    if (held !== null && previous.includes(held) && !risingIds.includes(held)) {
      // MOVE C's destination is the card now occupying the departing card's
      // place — «the next remaining» — falling through to MOVE B when the
      // overlay empties.
      const at = previous.indexOf(held);
      departingRef.current = {
        nextId: risingIds.length === 0 ? null : (risingIds[Math.min(at, risingIds.length - 1)] ?? null),
      };
    }
    renderedIdsRef.current = risingIds;
  }

  useEffect(() => {
    // MOVE A — the FIRST rising alert appears, and focus moves IFF nothing holds
    // it. Otherwise it does not move at all: the caret does not jump, no
    // keystroke is lost, and the alert is STILL announced, because role="alert"
    // interrupts a screen reader WITHOUT taking focus. That is the whole reason
    // that role exists and why it, and not alertdialog, is correct here.
    //
    // ⚠ THE DESTINATION IS THE CARD CONTAINER AND NOT «אני מגיעה». MOVE A fires
    // exactly when activeElement is <body> — precisely the state in which the
    // next Space is a page scroll — so landing on the ack control would convert
    // that keypress into an IRREVERSIBLE accept (there is no un-accept verb)
    // sitting on top of the two-minute stall hole. Accept stays FIRST IN DOM
    // inside the card, so reach costs one Tab, and the default outcome of a
    // keypress on the container is nothing.
    //
    // ⚠ It fires on the FIRST card only. A second page arriving must not move
    // focus out from under a reader mid-sentence on the emergency she is
    // already answering.
    const ids = risingIdsRef.current;
    const had = hadCardsRef.current;
    hadCardsRef.current = ids.length > 0;
    if (had || ids.length === 0) {
      return;
    }
    if (document.activeElement === document.body) {
      cardRefs.current.get(ids[0] ?? "")?.focus();
    }
  }, [risingKey]);

  useEffect(() => {
    // MOVES B and C — a card left WHILE HOLDING FOCUS. The intent was captured
    // during the render that dropped it (above) and is consumed here, in the
    // effect of that same commit, so it can never fire against a later one and
    // steal focus back from wherever the user has since put it.
    //
    // Unconditional once the intent is set, deliberately: the intent is only
    // ever set when focus was inside the departing card, and where the browser
    // left it afterwards differs by engine (real browsers drop to <body>).
    // Guarding on <body> here would make the whole move VACUOUS in jsdom, which
    // is precisely how this repo shipped a dead restore effect once already.
    const departing = departingRef.current;
    if (departing === null) {
      return;
    }
    departingRef.current = null;
    if (departing.nextId !== null) {
      cardRefs.current.get(departing.nextId)?.focus();
      return;
    }
    // MOVE B — never <body>. The <main tabIndex={-1}> ConsoleShell already
    // renders and the skip link already targets.
    document.getElementById("console-main")?.focus();
  }, [risingKey]);

  useEffect(() => {
    // MOVE D — a failed accept's in-card alert appears, and focus moves into it
    // IFF she is the one who tapped that card's control.
    //
    // ⚠ THIS COPIES FloorPanel's SHAPE AND NOT ITS GUARD. The shipped effect
    // there fires cardAlertRef.current?.focus() UNCONDITIONALLY — correct
    // THERE, because the panel's Button is disabled={disabled||loading} so the
    // browser already blurred it. Copied here it becomes an unguarded focus move
    // on an error path, in the one component whose whole premise is that it
    // never moves focus uninvited: a 409 landing while she is typing behind the
    // overlay would pull her out of a field she cannot see.
    //
    // The two branches are ONE condition read on two engines: a real browser has
    // blurred the disabled control to <body>, jsdom has not and leaves it inside
    // the card. Either way she is the actor; anything else means she has moved
    // on and the alert is not hers to be interrupted by.
    if (cardError === null) {
      return;
    }
    if (actedRef.current !== cardError.id) {
      return;
    }
    const inside = focusedCardId() === cardError.id;
    if (document.activeElement === document.body || inside) {
      alertRef.current?.focus();
    }
  }, [cardError]);

  useEffect(() => {
    // ⚠ THE KEYBOARD ROUTE IN, WHICH MOVE A ALONE DOES NOT PROVIDE.
    //
    // An alert announced perfectly to a user who cannot reach the ack control is
    // not an accessible alert. MOVE A deliberately does not move focus when
    // something holds it, and an Esc bound to the container fires only when
    // focus is already inside — so for the exact user this design protects,
    // someone mid-form in <main>, «אני מגיעה» sits behind a Shift+Tab run past
    // every preceding focusable in her section PLUS the whole ConsoleShell
    // chrome. Forward Tab is worse. «First in DOM is first reached by Tab» is
    // true only in the <body> case, i.e. only where focus moved anyway.
    //
    //   Esc from OUTSIDE moves focus INTO the first card's «אני מגיעה».
    //   Esc from INSIDE keeps its meaning: dismiss.
    //
    // Two guards, each preserving a SHIPPED behaviour rather than being
    // defensive padding.
    if (risingIdsRef.current.length === 0) {
      return;
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") {
        return;
      }
      const target = event.target;
      // Inside the overlay Esc means dismiss, and the container's own handler
      // owns it — this listener is the route IN and nothing else.
      if (target instanceof Node && overlayRef.current?.contains(target) === true) {
        return;
      }
      // F36's three shipped <dialog>s and SosRaiseDialog own their own Esc
      // (Modal's onCancel). Modal renders its <dialog> unconditionally and
      // toggles `open` via showModal()/close(), so this matches only while one
      // is genuinely open.
      if (document.querySelector("dialog[open]") !== null) {
        return;
      }
      // RoomsPanel renders a bare Select on the free tile, OUTSIDE any dialog,
      // and Esc closing an open native dropdown is browser behaviour a capture
      // listener would pre-empt. Two characters of condition; jsdom would never
      // have caught it.
      if (target instanceof HTMLSelectElement) {
        return;
      }
      const first = risingIdsRef.current[0];
      if (first === undefined) {
        return;
      }
      event.preventDefault();
      // ⚠ THE CONTROL, not the container. Esc from outside is a DELIBERATE
      // keypress and not an involuntary arrival — that distinction is the whole
      // of DC-1, and a builder «unifying» this with MOVE A reverts it.
      acceptRefs.current.get(first)?.focus();
    };
    document.addEventListener("keydown", onKeyDown, true);
    return () => document.removeEventListener("keydown", onKeyDown, true);
  }, [risingKey]);

  const hide = (alert: SosAlert) => {
    // Per-device, in-memory, and nothing is sent: the alert stays open, keeps
    // escalating and comes back on reload, because if it is still open it is
    // still an emergency. It is also the SC 2.2.2 «hide» mechanism for the one
    // region of this feature that has content.
    setDismissed((current) => [...current, dismissKey(alert)]);
    setCardError(null);
    toast({ message: t("sos.dismissedCue") });
  };

  const onEscInside = (event: { key: string; target: EventTarget | null }) => {
    if (event.key !== "Escape") {
      return;
    }
    const target = event.target;
    const held = target instanceof Element ? target.closest("[data-alert-id]") : null;
    const id = held?.getAttribute("data-alert-id") ?? rising[0]?.id;
    const alert = rising.find((one) => one.id === id);
    if (alert !== undefined) {
      hide(alert);
    }
  };

  const refuse = (alert: SosAlert, failure: unknown) => {
    if (failure instanceof ApiError) {
      const name = failure.details?.staff_display_name;
      if (failure.code === "SOS_ALREADY_ACCEPTED") {
        // ⚠ `details` is optional and typed `| undefined`, never `| null`,
        // precisely so «‎ כבר מגיעה.» is unconstructible: a sentence that admits
        // it does not know beats an empty interpolation on this surface.
        setCardError(
          name === undefined
            ? { id: alert.id, text: t("sos.error.alreadyAcceptedUnknown"), name: null }
            : { id: alert.id, text: t("sos.error.SOS_ALREADY_ACCEPTED", { name }), name },
        );
        return;
      }
      if (failure.code === "SOS_CLOSED") {
        setCardError({ id: alert.id, text: t("sos.error.SOS_CLOSED"), name: null });
        return;
      }
      if (failure.status === 404) {
        setCardError({ id: alert.id, text: t("sos.error.notFound"), name: null });
        return;
      }
    }
    // ⚠ NEVER FALLBACK_ERROR_MESSAGE. A failed ACCEPT means only that SHE did
    // not claim it — the alert is still open, still rising on every other
    // targeted device and still escalating — so «נסי שוב» is exactly right and
    // naming the manual fallback would be wrong. That distinction is real and
    // is why the raise has a different string.
    setCardError({ id: alert.id, text: t("sos.error.actionFailed"), name: null });
  };

  const answer = async (alert: SosAlert) => {
    if (busyId !== null) {
      return;
    }
    setBusyId(alert.id);
    setCardError(null);
    actedRef.current = alert.id;
    const failure = await accept(alert.id);
    setBusyId(null);
    if (failure !== null) {
      refuse(alert, failure);
      return;
    }
    // ⚠ THROUGH THE SHIPPED APP-LEVEL TOAST AND NOT FloorPanel's REGION. An
    // accept removes the card and MOVE B parks focus on <main id="console-main">
    // — an UNLABELLED container — and on any of the eleven sections with no
    // SosCentre there is no role="status" region at all. Without this she gets:
    // the red vanishes, focus jumps to the top of an unnamed main, and nothing
    // is announced or shown.
    toast({ message: t("sos.acceptedCue") });
  };

  // A 401 renders NEITHER surface, deliberately: the loop has stopped,
  // onSessionEnded has fired once and App is dropping the console to LoginForm.
  // A strip saying the channel is down over a login screen would be true and
  // useless.
  if (terminal === "session") {
    return null;
  }

  const bottom = channelDown || hiddenLive.length > 0;
  if (rising.length === 0 && !bottom) {
    return null;
  }

  return (
    <>
      {rising.length > 0 && (
        // ⚠ NO HANDLER, NO onClick, NO BACKDROP-DISMISS. «Tap the backdrop to
        // dismiss» is the reflex every modal library teaches, and here it would
        // let a pocket press close an emergency. `overscroll-contain` so a flick
        // at the end of the stack does not scroll the console BEHIND the
        // overlay, which she cannot see and would have to undo.
        <div
          ref={overlayRef}
          onKeyDown={onEscInside}
          className="fixed inset-0 z-40 overflow-y-auto overscroll-contain bg-danger p-4"
        >
          {/* No extra bottom padding: the third card's white top edge showing
              over the red IS the «more below» cue, and it is arithmetic rather
              than a chrome element. */}
          <div className="mx-auto flex w-full max-w-[720px] flex-col gap-4">
            {rising.map((alert) => {
              const whoId = `${baseId}-${alert.id}`;
              const name = alert.raised_by_name ?? t("sos.raiserGone");
              const time = jerusalemTime(alert.created_at);
              return (
                <article
                  key={alert.id}
                  data-alert-id={alert.id}
                  ref={(node) => {
                    cardRefs.current.set(alert.id, node);
                  }}
                  // ⚠ NAMED by the WHO line's own node rather than left a bare
                  // tabIndex={-1}: focusing an unnamed <article> makes some ATs
                  // re-read the whole subtree the alert just announced. It
                  // points at an element that already exists, so there is no new
                  // string and nothing that can drift.
                  tabIndex={-1}
                  aria-labelledby={whoId}
                  className="rounded-md bg-surface-raised p-6 shadow-lg"
                >
                  {/* ⚠ ONE role="alert" PER CARD, never one wrapping the list.
                      The role carries implicit aria-live="assertive" AND
                      implicit aria-atomic="true", so with a wrapper a second
                      page would re-announce EVERY card and the seamstress would
                      hear again about the emergency she already answered.

                      ⚠ ITS TEXT IS WRITE-ONCE. The time, the escalation clause
                      and the stall clause are SIBLINGS AFTER IT: any childList
                      change inside re-announces the entire card, assertively,
                      interrupting whatever the screen reader was saying — for a
                      fact that changes nothing about what she has to do. */}
                  <div role="alert" className="space-y-2">
                    <p id={whoId} className="text-xl font-semibold text-ink">
                      {isolateBidi(t("sos.calling", { name }), name)}
                    </p>
                    <p className="text-xl font-semibold text-ink">
                      {alert.room_label === null ? (
                        t("sos.noRoom")
                      ) : (
                        <>
                          {/* ⚠ A VISUALLY-HIDDEN LABEL INSIDE THE REGION, and
                              NOT an aria-label on the <p>: ARIA prohibits
                              naming role=paragraph, so the em-dash-value-last
                              shape used elsewhere is unavailable here and would
                              have shipped a name nothing reads.

                              The room label is otherwise BARE — the boutique
                              types the room's own noun, so «בחדר {{room}}»
                              renders «בחדר חדר 2» — and it carries no Field
                              bound at all, so «2» is fully supported and the
                              atomic utterance needs the prefix to parse. */}
                          <span className="sr-only">{t("sos.roomA11yPrefix")}</span>{" "}
                          <bdi>{alert.room_label}</bdi>
                        </>
                      )}
                    </p>
                    {/* ABSENT when she typed nothing — never an empty line and
                        never a placeholder. */}
                    {alert.note !== null && (
                      <p className="text-lg text-ink">
                        <bdi>{alert.note}</bdi>
                      </p>
                    )}
                  </div>

                  {/* An ABSOLUTE instant through jerusalemTime, which never
                      subtracts and is immune to a boutique tablet's clock
                      drift. No countdown and no live counter anywhere in this
                      overlay — that is what keeps the SC 2.2.2 argument true
                      rather than merely claimed. */}
                  <p className="mt-2 text-sm text-ink-muted">
                    {isolateLtr(t("sos.since", { time }), time)}
                  </p>

                  {/* ⚠ A WORD, NEVER A COLOUR, and never a number: `escalated`
                      is an unbounded boolean, so «ללא מענה כבר 30 שניות» would
                      state a flat thirty seconds to the shift manager deciding
                      whether to walk or run. Remove every colour from this
                      feature and nothing is lost but emphasis. */}
                  {alert.escalated && (
                    <p className="mt-2 text-base font-semibold text-danger">
                      {t("sos.escalated")}
                    </p>
                  )}
                  {alert.stalled && (
                    <p className="mt-2 text-base font-semibold text-danger">{t("sos.stalled")}</p>
                  )}

                  {cardError?.id === alert.id && (
                    // The NOTICE register and not text-danger: a 409 is two
                    // people reaching for one emergency and a 404 is a screen
                    // one tick behind. Nothing that can go wrong here is her
                    // fault.
                    <p
                      ref={alertRef}
                      role="alert"
                      tabIndex={-1}
                      className="mt-2 text-sm font-semibold text-warning-text"
                    >
                      {cardError.name === null
                        ? cardError.text
                        : isolateBidi(cardError.text, cardError.name)}
                    </p>
                  )}

                  {/* ⚠ FIRST IN DOM, and `primary` rather than `danger`:
                      red-on-red is invisible on the field and, on the card, red
                      is this product's DESTRUCTIVE register. The most
                      affirmative act on the floor must not wear the colour of
                      the most destructive one. Gold on ink is 6.41:1 at 48px. */}
                  <div className="mt-4">
                    <Button
                      ref={(node) => {
                        acceptRefs.current.set(alert.id, node);
                      }}
                      variant="primary"
                      size="lg"
                      fullWidthMobile
                      loading={busyId === alert.id}
                      aria-label={t("sos.acceptAria", { name })}
                      onClick={() => void answer(alert)}
                    >
                      {t("sos.accept")}
                    </Button>
                  </div>
                  <div className="mt-3 flex justify-end">
                    <Button
                      variant="ghost"
                      size="md"
                      fullWidthMobile={false}
                      aria-label={t("sos.dismissAria", { name })}
                      onClick={() => hide(alert)}
                    >
                      {t("sos.dismiss")}
                    </Button>
                  </div>
                </article>
              );
            })}
          </div>
        </div>
      )}

      {bottom && (
        // ONE fixed container, so the strip and the affordance can never collide
        // and no offset arithmetic exists.
        <div className="fixed inset-x-0 bottom-0 z-40 flex flex-col items-end gap-2 p-4">
          {hiddenLive.length > 0 && (
            // ⚠ WITHOUT THIS, A DISMISSAL ON ANY OF THE ELEVEN SECTIONS WITH NO
            // SosCentre IS TOTAL AND PERMANENT for a live emergency — and the
            // role-targeted route is the raise dialog's first and default
            // option, so that is the common path and not an edge.
            <Button
              variant="danger"
              size="md"
              fullWidthMobile={false}
              onClick={() => setDismissed([])}
            >
              {isolateLtr(
                t("sos.dismissedCount", { count: hiddenLive.length }),
                String(hiddenLive.length),
              )}
            </Button>
          )}
          {channelDown && (
            <div className="w-full rounded-md border border-danger bg-surface-raised p-3">
              {/* ⚠ THE ONLY APP-LEVEL SURFACE THIS FEATURE HAS, so it is the
                  only thing that can say the channel is dead on the eleven
                  sections with no panel of their own. «Nothing renders» is not
                  an acceptable state for an emergency receiver that has stopped
                  receiving. */}
              <p role="alert" className="text-sm text-ink">
                {t("sos.channelDown")}
              </p>
              <div className="mt-2 flex justify-end">
                <Button
                  variant="secondary"
                  size="md"
                  fullWidthMobile={false}
                  onClick={() => window.location.reload()}
                >
                  {/* «רענון הדף» and NOT «רענון»: the strip's only remedy is a
                      page reload, and «רענון» is floor.refresh — a different
                      act, offered by a different control. */}
                  {t("sos.channelReload")}
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
    </>
  );
}
