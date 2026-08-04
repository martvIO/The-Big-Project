import type { ReactNode } from "react";
import { useEffect, useId, useRef } from "react";
import { cn } from "../lib/styles";

export interface ModalProps {
  open: boolean;
  // Dismiss (Esc, backdrop, cancel button) — never a confirm. The confirm action
  // is a caller-supplied button in `footer` with its own handler.
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  // → aria-describedby on the <dialog>. OPTIONAL, and omitted React writes no
  // attribute at all, so every shipped call site is byte-identical in behaviour.
  //
  // Not cosmetic: showModal() puts focus on the first focusable control, so with
  // aria-labelledby alone a screen-reader user hears the dialog's name and then a
  // button label, and never hears the body. A caller whose body is the point of
  // the dialog points this at the paragraph that carries it.
  describedById?: string;
}

// Native <dialog>: free focus trap, top-layer stacking, Esc handling, and focus
// return to the trigger. Motion is split across two elements — the panel
// (scale 0.97->1 + fade at --motion-base) and the ::backdrop (fade at
// --motion-fast) — per the design.
export function Modal({ open, onClose, title, children, footer, describedById }: ModalProps) {
  const ref = useRef<HTMLDialogElement>(null);
  // useId, not a literal — a screen may mount two Modals at once (e.g. DressEditor
  // + its embedded MediaGallery), and duplicate ids break aria-labelledby.
  const titleId = useId();

  useEffect(() => {
    const dlg = ref.current;
    if (!dlg) return;
    if (open && !dlg.open) {
      dlg.showModal();
    } else if (!open && dlg.open) {
      dlg.close();
    }
  }, [open]);

  return (
    <dialog
      ref={ref}
      onCancel={(e) => {
        // Esc: dismiss only, never confirm.
        e.preventDefault();
        onClose();
      }}
      onClose={onClose}
      aria-labelledby={titleId}
      aria-describedby={describedById}
      className={cn(
        "m-auto w-[min(28rem,calc(100vw-2rem))] rounded-md bg-surface-raised p-6 text-ink shadow-lg",
        "animate-modal-panel backdrop:bg-ink/40 backdrop:animate-modal-backdrop",
      )}
    >
      <h2 id={titleId} className="font-display text-xl text-ink">
        {title}
      </h2>
      <div className="mt-3 text-base text-ink-muted">{children}</div>
      {footer && <div className="mt-6 flex justify-end gap-3">{footer}</div>}
    </dialog>
  );
}
