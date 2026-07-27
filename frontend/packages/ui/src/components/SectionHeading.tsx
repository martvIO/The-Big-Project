import type { ReactNode } from "react";
import { cn } from "../lib/styles";

export interface SectionHeadingProps {
  children: ReactNode;
  as?: "h1" | "h2" | "h3";
  // A decorative gold hairline under the heading — aria-hidden ornament.
  ornament?: boolean;
  className?: string;
}

export function SectionHeading({ children, as = "h2", ornament = false, className }: SectionHeadingProps) {
  const Tag = as;
  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <Tag className="font-display text-xl text-ink">{children}</Tag>
      {ornament && <span aria-hidden="true" className="h-px w-12 bg-gold" />}
    </div>
  );
}
