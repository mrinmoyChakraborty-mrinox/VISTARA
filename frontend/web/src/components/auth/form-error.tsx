/** Inline form error with an accessible alert role. */
export function FormError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p
      role="alert"
      className="mono"
      style={{
        color: "#c4572f",
        background: "color-mix(in srgb, #c4572f 12%, transparent)",
        border: "1px solid color-mix(in srgb, #c4572f 40%, transparent)",
        borderRadius: 12,
        padding: "10px 14px",
      }}
    >
      {message}
    </p>
  );
}
