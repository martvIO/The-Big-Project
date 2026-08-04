import { useEffect, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Modal, cn, focusRing } from "@boutique/ui";
import { GUIDE_STEPS, type SectionKey } from "../lib/guide";

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
    // ⚠ CONTENT IS STATE, NEVER `t(steps[index])` INLINE IN THE JSX.
    // `AtelierSection.tsx:445-449` records the mechanism: assigning a string to a
    // text node is a real childList mutation inside role="status" EVEN WHEN THE
    // TWO STRINGS ARE BYTE-IDENTICAL, and `setState` with an equal value is a
    // React no-op — so the `setState` is the guard.
    setAnnounced(
      `${t("guide.progress", { step: index + 1, total: steps.length })} · ${t(steps[index])}`,
    );
    // `t`, `steps` and `section` are read here but are deliberately NOT
    // dependencies: this effect exists to fire on a STEP CHANGE and on the open
    // commit, and nothing else may make the region speak.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index, open]);

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
