import { useEffect, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Modal, cn, focusRing } from "@boutique/ui";
import { GUIDE_STEPS, type SectionKey } from "../lib/guide";
import { useSos } from "../lib/sos-context";

/**
 * The «מדריך» header control and the walkthrough it opens.
 *
 * ⚠ NO DEPENDENCY, AND THE ARGUMENT IS POSITIVE RATHER THAN GRUDGING. The three
 * things a tour library sells are: a focus trap — the platform's, `Modal` is a
 * native `<dialog>` opened with `showModal()` and fifteen call sites have ridden
 * it since F5; a positioning engine — out of scope, because NOTHING HERE IS
 * ANCHORED (the guide describes the section behind it and never touches it); and
 * a step state machine — `useState(0)`. Hand-rolling a Tab/Shift+Tab cycle over a
 * focusable-selector list would be ~60 lines of the exact code this repo has
 * shipped wrong five times.
 *
 * ⚠ NOTHING IN THIS FILE CALLS `.focus()`. `showModal()` puts focus on the first
 * focusable descendant — «סגירה», by the footer's DOM order — and `close()`
 * returns it to the trigger. Adding a manual move on top of the platform's is
 * two engines deciding one thing, which is the defect class the focus contract
 * refuses.
 */
export function GuideOverlay({ section }: { section: SectionKey }) {
  const { t } = useTranslation();
  const steps = GUIDE_STEPS[section];

  const [open, setOpen] = useState(false);
  const [index, setIndex] = useState(0);
  const [announced, setAnnounced] = useState("");
  const bodyId = useId();

  // Armed by the trigger, consumed by the effect below on the commit that opens
  // the dialog. Without it, open announces TWICE — once through
  // aria-describedby and once through the region.
  const skipRef = useRef(false);

  useEffect(() => {
    // Closed, the region is `display:none` inside the dialog and every ATdirected
    // write to it is either silent or a stale sentence waiting to be exposed.
    if (!open) return;
    if (skipRef.current) {
      skipRef.current = false;
      return;
    }
    // ⚠ CONTENT IS STATE, NEVER `t(steps[index])` INLINE IN THE JSX — but the
    // reason this block used to give was FALSE and had the danger backwards. It
    // claimed that writing a byte-identical string still mutates the text node
    // and that `setState` with an equal value is a React no-op that guards
    // against a spurious repeat. What actually happens is the opposite: React
    // compares the text child on re-render and SKIPS the DOM write when the
    // string is unchanged, so a live region rewritten to the same sentence is
    // SILENT. (`AtelierSection.tsx:471-477` carries the corrected statement;
    // F21 T11 found FloorPanel shipping the real bug.)
    //
    // ⚠ THIS REGION IS SAFE, AND NOT BY DESIGN. Two things make a repeat
    // impossible here, and both must survive any edit to this component: the
    // sentence embeds `step` (so two consecutive fires of this effect can never
    // produce the same string, since `index` is the only thing that changes it),
    // and the trigger's `setAnnounced("")` clears the region on every open (so a
    // reopened walkthrough writes step 2 over "" rather than over an identical
    // step 2). Delete either and this region goes silent on a repeat.
    // `GuideOverlay.test.tsx`'s MutationObserver leg is what reds if you do —
    // `toHaveTextContent` cannot see it, because the text is right either way.
    //
    // The state indirection stands on its own merit regardless: it is what lets
    // the open commit be SKIPPED, so the step is announced once by
    // aria-describedby and not twice.
    setAnnounced(
      `${t("guide.progress", { step: index + 1, total: steps.length })} · ${t(steps[index])}`,
    );
    // `t`, `steps` and `section` are read here but are deliberately NOT
    // dependencies: this effect exists to fire on a STEP CHANGE and on the open
    // commit, and nothing else may make the region speak.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index, open]);

  const { alerts } = useSos();

  // ⚠ THE KEY IS THE COMPOSITE `SosOverlay` ALREADY USES (`dismissKey`,
  // SosOverlay.tsx:59-61), NOT THE BARE ID. Escalation and the stall each
  // RE-RISE a dismissed card under the SAME id — that is F37's safety net for
  // «the first responder did not come» — so an id-keyed detector is
  // structurally blind to exactly the alert this guard exists for. A CHANGE TO
  // ONE KEY IS A CHANGE TO BOTH.
  //
  // ⚠ And it reads EVERY for_me alert, dismissed ones included. `dismissed` is
  // SosOverlay's own state and is not on `SosContextValue` — which is correct as
  // well as unavoidable: a dismissed page whose `escalated` flips re-rises the
  // card, and the guide has to get out of its way.
  const forMe = alerts
    .filter((one) => one.for_me)
    .map((one) => `${one.id}:${one.escalated}:${one.stalled}`);

  // SosOverlay:129-136's shape: a joined string is the dependency, a ref carries
  // the live list, because the array is rebuilt on every render.
  const risingKey = forMe.join("|");
  const forMeRef = useRef<readonly string[]>(forMe);
  forMeRef.current = forMe;
  // Seeded with what is ALREADY live at mount (DL12), so an alert this device
  // has been looking at since before the guide existed never closes it.
  const seenRef = useRef<readonly string[]>(forMe);

  useEffect(() => {
    const keys = forMeRef.current;
    // ⚠ A SET DIFFERENCE, NEVER THE HEAD OF THE LIST. `alerts` is oldest-first
    // (`sos-context.ts:18` declares it, `sos_alerts.py:245` is `ORDER BY
    // created_at` ascending, `sos.tsx:128-131` appends), so a NEW page ARRIVES
    // AT THE END: any test on `keys[0]` never fires while an older page is still
    // live — the case where a top-layer dialog is most dangerous.
    //
    // ⚠ And EDGE, never level. `if (forMe.length > 0) setOpen(false)` would
    // close the guide on every 5s tick for as long as a live-but-dismissed alert
    // existed, so a staffer who dismissed a page could never open it again.
    const grew = keys.some((key) => !seenRef.current.includes(key));
    seenRef.current = keys;
    if (grew) {
      // ⚠ `showModal()` INERTS THE DOCUMENT. The red field is `fixed inset-0
      // z-40` (SosOverlay.tsx:451) and the top layer paints above it, so an
      // emergency arriving over an open guide is not merely covered — its
      // «אני מגיעה» is unclickable and unreachable by Tab. There is no z-index,
      // no portal and no stacking context that changes that. Closing IS the
      // mechanism. Measured in Chromium by `e2e/guide.spec.ts` T7, which fails
      // on the CLICK and not merely on a focus assertion.
      setOpen(false);
    }
  }, [risingKey]);

  const close = () => setOpen(false);

  const last = index === steps.length - 1;

  return (
    <>
      {/* Matches the logout button's register exactly — a bare <button>, the
          same `text-sm text-ink-muted hover:text-ink` and the same focusRing —
          plus `min-h-11 px-2` for tokens.md law 7. ⚠ Consequence, deliberate:
          the console header grows from ≈52px to ≈68px on every section. The
          background is transparent, so the 44px box is invisible and it is still
          two text labels side by side.

          NOT a `Button variant="ghost"`: that is `font-semibold text-base` with a
          rounded hover fill and would outrank the logout beside it. The header is
          chrome; a walkthrough is not an action.

          ⚠ NEVER DISABLED AND NEVER HIDDEN, including while an emergency is on
          screen (DL13): removing a control that holds focus is how `close()`
          returns focus to nothing and Chromium drops to <body> — the defect this
          repo has shipped five times.

          No icon, no dot, no aria-label (DL20): the visible «מדריך» IS the
          accessible name, which makes WCAG 2.5.3 true here by construction. */}
      <button
        type="button"
        onClick={() => {
          // IN THIS ORDER: step 1 every time, an empty live region, and a
          // reopen that never resumes mid-walkthrough nor re-announces the
          // previously visited section's last sentence.
          //
          // ⚠ `setAnnounced("")` CARRIES A SECOND JOB IT WAS NOT WRITTEN FOR,
          // and it is the one that keeps this region audible: reopening the same
          // section and stepping to the same step produces a byte-identical
          // sentence, which React would SKIP writing — so without this clear the
          // second walkthrough would be silent. See the announce effect above.
          setIndex(0);
          setAnnounced("");
          skipRef.current = true;
          setOpen(true);
        }}
        className={cn("min-h-11 px-2 text-sm text-ink-muted hover:text-ink", focusRing)}
      >
        {t("guide.trigger")}
      </button>

      <Modal
        open={open}
        onClose={close}
        // The section name is DERIVED here rather than taken as a prop: every
        // NAV row's labelKey is exactly `nav.${key}`, five resolve through the
        // nested `nav:` object and nine through i18next's flat fallback, and
        // i18n.test.ts walks all fourteen. Zero props, zero expressions in
        // App.tsx, zero new keys — and a nav-label edit can never desynchronise
        // the guide's title.
        title={t("guide.title", { section: t(`nav.${section}`) })}
        describedById={bodyId}
        footer={
          <>
            {/* DOM order: dismiss first, primary last — `SosRaiseDialog:196-201`'s
                house pattern. «הקודם» is ABSENT on step 1 rather than disabled. */}
            <Button variant="ghost" size="md" onClick={close}>
              {t("guide.close")}
            </Button>
            {index > 0 && (
              <Button variant="secondary" size="md" onClick={() => setIndex(index - 1)}>
                {t("guide.prev")}
              </Button>
            )}
            <Button
              variant="primary"
              size="md"
              onClick={() => {
                if (last) {
                  close();
                } else {
                  setIndex(index + 1);
                }
              }}
            >
              {/* On the last step the control under her finger changes identity,
                  in the same slot, deliberately: the alternative is a disabled
                  «הבא» beside a «סיום», i.e. a dead control inside a trap. */}
              {last ? t("guide.done") : t("guide.next")}
            </Button>
          </>
        }
      >
        <p className="text-sm text-ink-muted">
          {t("guide.progress", { step: index + 1, total: steps.length })}
        </p>
        {/* ⚠ `text-ink` here is NOT the override trap a reviewer will reach for.
            That trap is a call-site utility losing a same-property fight ON THE
            SAME ELEMENT; `Modal` puts `text-ink-muted` on the wrapper <div> and
            this is a CHILD <p> carrying its own colour. An element's own
            declaration beats an inherited value — no specificity contest, no
            stylesheet-order dependency. The step is the content of this dialog
            and gets the content colour; the counter is chrome and keeps muted. */}
        <p id={bodyId} className="mt-2 text-base text-ink">
          {t(steps[index])}
        </p>
        {/* NEVER CONDITIONALLY MOUNTED. `Modal` renders its children whether
            `open` is true or false, so this lives for the dialog's whole
            lifetime, hidden only by the UA's display:none. Remounting a live
            region re-announces it — on every unrelated re-render of the section
            behind. */}
        <p role="status" className="sr-only">
          {announced}
        </p>
      </Modal>
    </>
  );
}
