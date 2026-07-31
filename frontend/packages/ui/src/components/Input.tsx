import type { InputHTMLAttributes, ReactNode, Ref } from "react";
import { useId } from "react";
import { cn, focusRing } from "../lib/styles";

export interface InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "id"> {
  // Label is required — a placeholder is never the label (tokens.md usage law 3).
  //
  // ReactNode, not string: F17's gateway form renders a field name the platform
  // has no translation for, and an untranslated LTR snake_case run inside an RTL
  // Hebrew form needs `<bdi dir="ltr" lang="en">` around it — both the bidi
  // isolation this repo already applies to non-numeric labels and the WCAG 3.1.2
  // language mark. `label` is only ever rendered as children of the <label>, so
  // this widening is backwards-compatible with every string caller.
  label: ReactNode;
  error?: string;
  help?: string;
  ref?: Ref<HTMLInputElement>;
}

export function Input({ label, error, help, className, ...rest }: InputProps) {
  const id = useId();
  const helpId = help ? `${id}-help` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [helpId, errorId].filter(Boolean).join(" ") || undefined;

  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-semibold text-ink">
        {label}
      </label>
      {help && (
        <span id={helpId} className="text-xs text-ink-muted">
          {help}
        </span>
      )}
      <input
        id={id}
        {...rest}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        className={cn(
          "rounded-sm border border-border-input bg-surface-raised px-3 py-2 text-base text-ink",
          "focus:border-gold-strong",
          error && "border-danger",
          focusRing,
          className,
        )}
      />
      {error && (
        <span id={errorId} role="alert" className="text-sm text-danger">
          {error}
        </span>
      )}
    </div>
  );
}
