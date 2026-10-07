import Link from "next/link";

import { cn } from "@/lib/utils";

/** Small object chip; links to the object history page when href is given. */
export function ObjectChip({
  name,
  href,
  className,
}: {
  name: string;
  href?: string;
  className?: string;
}) {
  if (href) {
    return (
      <Link href={href} className={cn("schip", className)}>
        {name}
      </Link>
    );
  }
  return <span className={cn("schip", className)}>{name}</span>;
}
