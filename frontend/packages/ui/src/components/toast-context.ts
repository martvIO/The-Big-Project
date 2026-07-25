import { createContext, useContext } from "react";

export type ToastVariant = "success" | "error";

export interface ToastOptions {
  message: string;
  variant?: ToastVariant;
}

export type ShowToast = (options: ToastOptions) => void;

export const ToastContext = createContext<ShowToast | null>(null);

export function useToast(): ShowToast {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return ctx;
}
