"use client";

import { useEffect, useState, type FormEvent } from "react";
import { Loader2, Plus } from "lucide-react";

import { FormError } from "@/components/auth/form-error";
import { useCreateCamera } from "@/hooks/use-cameras";

function DialogContent({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState("");
  const [sourceType, setSourceType] = useState("browser");
  const localMode =
    typeof process !== "undefined" &&
    (process.env.NEXT_PUBLIC_VISTARA_MODE ?? "local") !== "live";
  // Live deployments create browser/phone cameras (phone pairs via QR);
  // local mode additionally offers the recorded demo video.
  const options = localMode
    ? [
        { value: "browser", label: "browser — this device camera" },
        { value: "phone", label: "phone — pair via QR code" },
        { value: "video_file", label: "video_file — recorded demo video" },
      ]
    : [
        { value: "browser", label: "browser — this device camera" },
        { value: "phone", label: "phone — pair via QR code" },
      ];
  const create = useCreateCamera();

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate(
      { name: name.trim(), source_type: sourceType },
      { onSuccess: () => onClose() },
    );
  };

  return (
    <div
      role="presentation"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 40,
        display: "grid",
        placeItems: "center",
        padding: 20,
        background: "color-mix(in srgb, var(--ink) 30%, transparent)",
        backdropFilter: "blur(6px)",
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="new-camera-title"
        className="panel"
        style={{ width: "min(100%, 440px)", padding: 28 }}
      >
        <h3 id="new-camera-title" style={{ fontSize: "1.35rem" }}>
          New camera
        </h3>
        <p className="mute" style={{ marginTop: 6, fontSize: ".92rem" }}>
          {sourceType === "video_file"
            ? "Recorded demo video plays on the server through the same watch–notice–remember loop."
            : sourceType === "phone"
              ? "Creates a phone camera. After adding, open Pair to show a QR code for the phone to scan."
              : "Browser cameras stream from this device. Nothing leaves the browser until the local gate sees motion."}
        </p>
        <form onSubmit={onSubmit} style={{ display: "grid", gap: 14, marginTop: 18 }}>
          <div className="auth-field">
            <label htmlFor="camera-name">Name</label>
            <input
              id="camera-name"
              required
              maxLength={60}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Desk camera"
              autoFocus
            />
          </div>
          <div className="auth-field">
            <label htmlFor="camera-source">Source type</label>
            <select
              id="camera-source"
              value={sourceType}
              onChange={(e) => setSourceType(e.target.value)}
            >
              {options.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
          <FormError
            message={
              create.error && typeof create.error === "object" && "message" in create.error
                ? String((create.error as { message: unknown }).message)
                : null
            }
          />
          <div className="flex flex-wrap gap-2">
            <button
              type="submit"
              className="btn shimmer"
              disabled={create.isPending || !name.trim()}
            >
              {create.isPending ? (
                <Loader2 size={15} className="animate-spin" aria-hidden="true" />
              ) : (
                <Plus size={15} aria-hidden="true" />
              )}
              {create.isPending ? "Adding…" : "Add camera"}
            </button>
            <button type="button" className="btn" onClick={onClose}>
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function NewCameraDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  // Fresh mount per open, so the form always starts empty.
  return <DialogContent onClose={onClose} />;
}
