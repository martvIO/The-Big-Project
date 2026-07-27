import type { ReactNode } from "react";
import { cn } from "../lib/styles";

export interface DressGridProps {
  children: ReactNode;
  className?: string;
}

// 2 columns @375, 3 @768, 4 @1440. Gap steps 16px -> 24px at 768 and stays 24px
// (it does not step to 48px) — tokens.md's endpoints, honored at the middle too.
export function DressGrid({ children, className }: DressGridProps) {
  return (
    <div className={cn("grid grid-cols-2 gap-4 md:grid-cols-3 md:gap-6 xl:grid-cols-4", className)}>
      {children}
    </div>
  );
}
