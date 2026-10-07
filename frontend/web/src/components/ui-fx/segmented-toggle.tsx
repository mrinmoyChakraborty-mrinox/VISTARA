"use client";

import { cn } from "@/lib/utils";

/**
 * Two-option sliding toggle. The indicator uses the same overshoot easing as
 * the landing's segmented control.
 */
export function SegmentedToggle({
  options,
  value,
  onChange,
  label,
}: {
  options: [string, string];
  value: 0 | 1;
  onChange: (next: 0 | 1) => void;
  label?: string;
}) {
  return (
    <div className="seg" data-m={value} role="group" aria-label={label}>
      <i aria-hidden="true" />
      {options.map((option, i) => (
        <button
          key={option}
          type="button"
          className={cn(value === i && "on")}
          aria-pressed={value === i}
          onClick={() => onChange(i as 0 | 1)}
        >
          {option}
        </button>
      ))}
    </div>
  );
}
