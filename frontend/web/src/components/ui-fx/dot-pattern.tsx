import { cn } from "@/lib/utils";

/** Subtle dot-grid backdrop tinted with --line. */
export function DotPattern({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cn("dots-bg", className)} />;
}
