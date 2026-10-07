/** Three-dot typing indicator (same dt bounce as the landing). */
export function TypingDots({ label = "Loading" }: { label?: string }) {
  return (
    <span className="dots" role="status" aria-label={label}>
      <span />
      <span />
      <span />
    </span>
  );
}
