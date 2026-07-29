import type { Ref } from "react";
import { useId } from "react";
import { cn, focusRing } from "../lib/styles";

export interface CheckboxProps {
  label: string;
  description?: string;
  error?: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
  ref?: Ref<HTMLInputElement>;
}

// Native checkbox with its role left alone — a legal consent announces
// checked/unchecked, never on/off (Toggle's role="switch" is the wrong semantic).
export function Checkbox({ label, description, error, checked, onCheckedChange, disabled = false, ref }: CheckboxProps) {
  const id = useId();
  const descId = description ? `${id}-desc` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [descId, errorId].filter(Boolean).join(" ") || undefined;

  return (
    <div className="flex flex-col">
      {/* The whole row is the hit target: the label wraps box + text at the
          44px floor with a 24px box (manage-catalog §3.4's Toggle-row ruling). */}
      <label htmlFor={id} className="flex min-h-11 cursor-pointer items-start gap-3 py-2">
        <input
          id={id}
          ref={ref}
          type="checkbox"
          checked={checked}
          disabled={disabled}
          onChange={(e) => onCheckedChange(e.target.checked)}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className={cn(
            "size-6 shrink-0 rounded-sm border border-border-input bg-surface-raised accent-gold-strong",
            "disabled:cursor-not-allowed disabled:opacity-60",
            error && "border-danger",
            focusRing,
          )}
        />
        <span className="text-base text-ink">{label}</span>
      </label>
      {/* Outside the <label> so it describes without joining the accessible name. */}
      {description && (
        <span id={descId} className="ps-9 text-sm text-ink-muted">
          {description}
        </span>
      )}
      {error && (
        <span id={errorId} role="alert" className="text-sm text-danger">
          {error}
        </span>
      )}
    </div>
  );
}
