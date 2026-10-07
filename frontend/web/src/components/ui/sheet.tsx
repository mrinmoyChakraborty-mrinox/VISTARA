"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { ReactNode } from "react";

/** shadcn-style Sheet (right drawer), themed from the Vistara tokens. */
export function Sheet({
  open,
  onOpenChange,
  labelledBy,
  children,
  width = 420,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  labelledBy: string;
  children: ReactNode;
  width?: number;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 50,
            background: "color-mix(in srgb, var(--ink) 30%, transparent)",
            backdropFilter: "blur(6px)",
          }}
        />
        <Dialog.Content
          aria-describedby={undefined}
          aria-labelledby={labelledBy}
          className="sheet-panel"
          style={{
            position: "fixed",
            top: 0,
            right: 0,
            bottom: 0,
            zIndex: 51,
            width: `min(100vw - 32px, ${width}px)`,
            overflowY: "auto",
            background: "var(--card)",
            backdropFilter: "blur(14px)",
            borderLeft: "1px solid var(--line)",
            boxShadow: "var(--shadow)",
            padding: 24,
          }}
        >
          <Dialog.Close
            aria-label="Close details"
            className="btn"
            style={{
              position: "sticky",
              top: 0,
              float: "right",
              padding: "8px 12px",
            }}
          >
            <X size={16} aria-hidden="true" />
          </Dialog.Close>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export function SheetTitle({ id, children }: { id: string; children: ReactNode }) {
  return (
    <h3 id={id} style={{ fontSize: "1.35rem", paddingRight: 48 }}>
      {children}
    </h3>
  );
}
