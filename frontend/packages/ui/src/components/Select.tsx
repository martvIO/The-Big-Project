import type { ReactNode, SelectHTMLAttributes } from "react";
import { useId } from "react";
import { cn, focusRing } from "../lib/styles";

export interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, "id"> {
  label: string;
  error?: string;
  children: ReactNode;
}

// Native <select> — no custom dropdown in v1 (a11y cost not worth it).
export function Select({ label, error, className, children, ...rest }: SelectProps) {
  const id = useId();
  const errorId = error ? `${id}-error` : undefined;

  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-semibold text-ink">
        {label}
      </label>
      <select
        id={id}
        {...rest}
        aria-invalid={error ? true : undefined}
        aria-describedby={errorId}
        className={cn(
          "rounded-sm border border-border-input bg-surface-raised px-3 py-2 text-base text-ink",
          "focus:border-gold-strong",
          error && "border-danger",
          focusRing,
          className,
        )}
      >
        {children}
      </select>
      {error && (
        <span id={errorId} role="alert" className="text-sm text-danger">
          {error}
        </span>
      )}
    </div>
  );
}
