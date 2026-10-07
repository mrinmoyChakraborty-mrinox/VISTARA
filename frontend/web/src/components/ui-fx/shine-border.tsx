import type { ReactNode } from "react";

import { BorderBeam } from "@/components/ui-fx/border-beam";

/**
 * ShineBorder: rotating conic border with tunable sweep speed and radius.
 * Built on BorderBeam so both stay in one motion language.
 */
export function ShineBorder({
  children,
  className,
  radius = 22,
  duration = 5,
}: {
  children: ReactNode;
  className?: string;
  radius?: number;
  duration?: number;
}) {
  return (
    <BorderBeam className={className} radius={radius} duration={duration}>
      {children}
    </BorderBeam>
  );
}
