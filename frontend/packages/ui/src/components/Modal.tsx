import type { ReactNode } from "react";
import { useEffect, useRef } from "react";
import { cn } from "../lib/styles";

export interface ModalProps {
  open: boolean;
  // Dismiss (Esc, backdrop, cancel button) — never a confirm. The confirm action
  // is a caller-supplied button in `footer` with its own handler.
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
}

// Native <dialog>: free focus trap, top-layer stacking, Esc handling, and focus
// return to the trigger. Motion is split across two elements — the panel
// (scale 0.97->1 + fade at --motion-base) and the ::backdrop (fade at
// --motion-fast) — per the design.
export function Modal({ open, onClose, title, children, footer }: ModalProps) {
  const ref = useRef<HTMLDialogElement>(null);

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
      aria-labelledby="modal-title"
      className={cn(
        "m-auto w-[min(28rem,calc(100vw-2rem))] rounded-md bg-surface-raised p-6 text-ink shadow-lg",
        "animate-modal-panel backdrop:bg-ink/40 backdrop:animate-modal-backdrop",
      )}
    >
      <h2 id="modal-title" className="font-display text-xl text-ink">
        {title}
      </h2>
      <div className="mt-3 text-base text-ink-muted">{children}</div>
      {footer && <div className="mt-6 flex justify-end gap-3">{footer}</div>}
    </dialog>
  );
}
