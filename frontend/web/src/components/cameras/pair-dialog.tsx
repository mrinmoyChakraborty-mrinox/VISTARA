"use client";

/* eslint-disable react-hooks/set-state-in-effect --
   Pair-on-mount fetch: the dialog exists solely to create + show one pairing
   code. Runs once per mount; the parent unmounts on close, so no cascade. */

import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, RefreshCw, Smartphone } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";

import { FormError } from "@/components/auth/form-error";
import {
  createPairing,
  getPairingStatus,
  revokePairing,
  type PairingInfo,
} from "@/lib/apiClient";

/**
 * Desktop phone-pairing dialog: creates a short-lived single-use pairing and
 * renders it as a QR code. The QR carries only the code + camera id — never
 * tokens or secrets. Polls the owner-only status endpoint so the desktop sees
 * the moment the phone pairs. Revokes on close.
 */
export function PairDialog({
  cameraId,
  cameraName,
  open,
  onClose,
}: {
  cameraId: string;
  cameraName: string;
  open: boolean;
  onClose: () => void;
}) {
  const [pairing, setPairing] = useState<PairingInfo | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // Latest code for revoke-on-unmount (refs are safe to sync in effects).
  const codeRef = useRef<string | null>(null);
  useEffect(() => {
    codeRef.current = pairing?.code ?? null;
  }, [pairing]);

  const start = useCallback(async () => {
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      const session = await createPairing(cameraId);
      setPairing(session);
    } catch (err) {
      setError(
        typeof err === "object" && err !== null && "message" in err
          ? String((err as { message: unknown }).message)
          : "Could not create a pairing code.",
      );
    } finally {
      setBusy(false);
    }
  }, [cameraId]);

  // One pairing per dialog mount (the parent unmounts on close, which also
  // revokes the code).
  useEffect(() => {
    void start();
    return () => {
      const code = codeRef.current;
      codeRef.current = null;
      if (code) void revokePairing(code).catch(() => undefined);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Owner-side polling: pending → paired/expired. Stops at a terminal state.
  useEffect(() => {
    if (!open || !pairing || status === "paired" || status === "expired") return;
    let cancelled = false;
    const timer = setInterval(() => {
      void getPairingStatus(pairing.code).then(
        (info) => {
          if (!cancelled) setStatus(info.status);
        },
        () => {
          if (!cancelled) setStatus("expired");
        },
      );
    }, 2000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [open, pairing, status]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const pairUrl =
    pairing && typeof window !== "undefined"
      ? `${window.location.origin}/pair?code=${encodeURIComponent(pairing.code)}&camera=${encodeURIComponent(cameraId)}`
      : "";

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
        aria-labelledby="pair-title"
        className="panel"
        style={{ width: "min(100%, 440px)", padding: 28, display: "grid", gap: 14 }}
      >
        <h3 id="pair-title" style={{ fontSize: "1.35rem" }}>
          Pair phone camera
        </h3>
        <p className="mute" style={{ fontSize: ".92rem" }}>
          <Smartphone size={14} aria-hidden="true" style={{ verticalAlign: -2 }} />{" "}
          {cameraName} — scan with the phone. The code is single-use and
          expires quickly.
        </p>

        {busy && (
          <p role="status" className="mono mute">
            <Loader2 size={14} className="animate-spin" aria-hidden="true" />{" "}
            Creating pairing code…
          </p>
        )}
        <FormError message={error} />

        {pairing && !error && (
          <>
            <div
              style={{
                display: "grid",
                placeItems: "center",
                padding: 16,
                borderRadius: 16,
                border: "1px solid var(--line)",
                background: "#fff",
              }}
            >
              <QRCodeSVG value={pairUrl} size={220} aria-label="Phone pairing QR code" />
            </div>
            <p className="mono mute" style={{ fontSize: ".8rem", overflowWrap: "anywhere" }}>
              {pairUrl}
            </p>
            <p role="status" className="mono" style={{ color: "var(--acc)" }}>
              {status === "paired"
                ? "● Phone paired — it can stream now."
                : status === "expired"
                  ? "○ Code expired or revoked — generate a new one."
                  : "○ Waiting for phone to scan…"}
            </p>
            <div className="flex flex-wrap gap-2">
              <button type="button" className="btn" onClick={() => void start()} disabled={busy}>
                <RefreshCw size={14} aria-hidden="true" />
                New code
              </button>
              <button type="button" className="btn" onClick={onClose}>
                Done
              </button>
            </div>
          </>
        )}

        {!pairing && !busy && !error && (
          <button type="button" className="btn shimmer" onClick={() => void start()}>
            Generate code
          </button>
        )}
      </div>
    </div>
  );
}
