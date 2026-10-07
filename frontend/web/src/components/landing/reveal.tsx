"use client";

import { useInView } from "@/hooks/use-motion";
import { cn } from "@/lib/utils";

export function Reveal({
  children,
  className,
  as: Tag = "div",
  ...rest
}: {
  children: React.ReactNode;
  className?: string;
  as?: "div" | "section";
} & React.HTMLAttributes<HTMLDivElement>) {
  const { ref, inView } = useInView<HTMLDivElement>(0.15);

  return (
    <Tag
      ref={ref}
      className={cn("rv", inView && "in", className)}
      {...rest}
    >
      {children}
    </Tag>
  );
}