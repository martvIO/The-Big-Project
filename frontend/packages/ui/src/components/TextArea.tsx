import type { Ref, TextareaHTMLAttributes } from "react";
import { useId } from "react";
import { cn, focusRing } from "../lib/styles";

export interface TextAreaProps extends Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "id"> {
  label: string;
  error?: string;
  help?: string;
  // When set with maxLength, renders a "used / max" counter tied to the field.
  showCount?: boolean;
  ref?: Ref<HTMLTextAreaElement>;
}

export function TextArea({ label, error, help, showCount, className, value, maxLength, ...rest }: TextAreaProps) {
  const id = useId();
  const helpId = help ? `${id}-help` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const countId = showCount && maxLength ? `${id}-count` : undefined;
  const describedBy = [helpId, countId, errorId].filter(Boolean).join(" ") || undefined;
  const used = typeof value === "string" ? value.length : 0;

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
      <textarea
        id={id}
        value={value}
        maxLength={maxLength}
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
      {countId && (
        <span id={countId} className="text-xs text-ink-muted text-end">
          {/* A bare numeric run inside an RTL document reorders against the
              neighbouring Hebrew without an isolate of its own. */}
          <bdi dir="ltr">
            {used} / {maxLength}
          </bdi>
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
