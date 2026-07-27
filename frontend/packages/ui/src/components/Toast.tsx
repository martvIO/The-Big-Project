import type { ReactNode } from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import { cn } from "../lib/styles";
import { ToastContext } from "./toast-context";
import type { ShowToast, ToastVariant } from "./toast-context";

interface ActiveToast {
  id: number;
  message: string;
  variant: ToastVariant;
}

export interface ToastProviderProps {
  children: ReactNode;
  autoDismissMs?: number;
}

export function ToastProvider({ children, autoDismissMs = 4000 }: ToastProviderProps) {
  const [toast, setToast] = useState<ActiveToast | null>(null);
  const idRef = useRef(0);

  const show = useCallback<ShowToast>(({ message, variant = "success" }) => {
    idRef.current += 1;
    // One at a time — a new toast replaces the current one, no queue.
    setToast({ id: idRef.current, message, variant });
  }, []);

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => {
      setToast((current) => (current?.id === toast.id ? null : current));
    }, autoDismissMs);
    return () => clearTimeout(timer);
  }, [toast, autoDismissMs]);

  return (
    <ToastContext.Provider value={show}>
      {children}
      {toast && (
        <div className="pointer-events-none fixed top-4 start-0 end-0 z-50 flex justify-center px-4">
          <div
            key={toast.id}
            role={toast.variant === "error" ? "alert" : "status"}
            className={cn(
              "animate-toast pointer-events-auto max-w-md rounded-md px-4 py-3 text-base shadow-md",
              toast.variant === "error"
                ? "bg-danger text-surface-raised"
                : "border border-border bg-surface-raised text-ink",
            )}
          >
            {toast.message}
          </div>
        </div>
      )}
    </ToastContext.Provider>
  );
}
