"use client";

import { Toaster as SonnerToaster } from "sonner";

/** shadcn-style Toaster, themed from the Vistara tokens (never default grays). */
export function Toaster() {
  return (
    <SonnerToaster
      position="bottom-right"
      toastOptions={{
        style: {
          background: "var(--card)",
          color: "var(--ink)",
          border: "1px solid var(--line)",
          fontFamily: "var(--font-b)",
          borderRadius: "14px",
          backdropFilter: "blur(10px)",
        },
      }}
    />
  );
}
