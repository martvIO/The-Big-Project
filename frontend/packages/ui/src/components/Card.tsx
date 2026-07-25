import type { HTMLAttributes } from "react";
import { cn } from "../lib/styles";

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  hoverElevate?: boolean;
}

export function Card({ hoverElevate = false, className, ...rest }: CardProps) {
  return (
    <div
      {...rest}
      className={cn(
        "rounded-md bg-surface p-6 shadow-sm",
        hoverElevate && "transition-shadow hover:shadow-md",
        className,
      )}
    />
  );
}
