import * as React from "react";

import { cn } from "@/lib/utils";

type BeamButtonProps = React.ComponentPropsWithoutRef<"a">;

export function BeamButton({ className, children, ...props }: BeamButtonProps) {
  return (
    <a className={cn("btn beamBtn", className)} {...props}>
      {children}
    </a>
  );
}