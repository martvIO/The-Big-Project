import { createContext, useContext } from "react";

export type ToastVariant = "success" | "error";

export interface ToastOptions {
  message: string;
  variant?: ToastVariant;
}

export type ShowToast = (options: ToastOptions) => void;

export const ToastContext = createContext<ShowToast | null>(null);

const noop: ShowToast = () => {};

// Degrades to a no-op outside a ToastProvider so a component that fires a toast
// can be unit-tested in isolation without mounting the provider. In the app the
// provider is always present, so real toasts show.
export function useToast(): ShowToast {
  return useContext(ToastContext) ?? noop;
}
