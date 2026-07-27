import type { ReactNode } from "react";
import { cn } from "../lib/styles";

export interface EmptyStateProps {
  title: string;
  body?: string;
  // Optional CTA (a Button, a link) — icon-less by default (restraint).
  action?: ReactNode;
  className?: string;
}

export function EmptyState({ title, body, action, className }: EmptyStateProps) {
  return (
    <div className={cn("flex flex-col items-center gap-3 py-12 text-center", className)}>
      <p className="font-display text-xl text-ink">{title}</p>
      {body && <p className="max-w-prose text-base text-ink-muted">{body}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
