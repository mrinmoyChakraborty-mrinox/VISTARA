import Image from "next/image";

/**
 * Futuristic V emblem with the neon halo. Rendered at the same optical size
 * as the old ping dot so it sits correctly inside every `.logo` lockup.
 */
export function VistaraMark({
  size = 26,
  className,
  priority = false,
}: {
  size?: number;
  className?: string;
  priority?: boolean;
}) {
  return (
    <Image
      src="/vistara-emblem.png"
      alt=""
      width={size}
      height={size}
      priority={priority}
      aria-hidden="true"
      className={className}
      style={{
        width: size,
        height: size,
        objectFit: "contain",
        flex: "none",
        display: "block",
      }}
    />
  );
}