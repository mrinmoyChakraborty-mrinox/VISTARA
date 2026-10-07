import * as React from "react";

import { cn } from "@/lib/utils";

type ShimmerButtonProps = React.ComponentPropsWithoutRef<"a">;

export function ShimmerButton({
  className,
  children,
  ...props
}: ShimmerButtonProps) {
  return (
    <a className={cn("btn shimmer", className)} {...props}>
      {children}
    </a>
  );
}

export function ShimmerButtonBase({
  className,
  children,
  ...props
}: React.ComponentPropsWithoutRef<"button">) {
  return (
    <button className={cn("btn shimmer", className)} {...props}>
      {children}
    </button>
  );
}