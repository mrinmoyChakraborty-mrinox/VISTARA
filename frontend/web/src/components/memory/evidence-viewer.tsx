"use client";

import { useState } from "react";
import { ImageOff, ZoomIn, ZoomOut } from "lucide-react";

import { useEvidenceBlobUrl } from "@/hooks/use-evidence";
import { cn } from "@/lib/utils";

/**
 * Shared evidence viewer: blob-URL fetch with the bearer token (or the
 * signed Evidence.url directly), zoom on open/click, camera + timestamp +
 * description, and a neutral placeholder when evidence is unavailable.
 */
export function EvidenceViewer({
  evidenceId,
  directUrl,
  cameraName,
  timestamp,
  description,
  open,
  onClose,
  title = "Evidence",
}: {
  evidenceId: string | null;
  directUrl?: string;
  cameraName?: string;
  timestamp?: string;
  description?: string;
  open: boolean;
  onClose: () => void;
  title?: string;
}) {
  const url = useEvidenceBlobUrl(open ? evidenceId : null, open ? directUrl : undefined);
  const [zoomed, setZoomed] = useState(false);
  const [failed, setFailed] = useState(false);

  if (!open) return null;

  const unavailable = !evidenceId && !directUrl;

  return (
    <div
      role="presentation"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) {
          setZoomed(false);
          onClose();
        }
      }}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 60,
        display: "grid",
        placeItems: "center",
        padding: 20,
        background: "color-mix(in srgb, var(--ink) 45%, transparent)",
        backdropFilter: "blur(8px)",
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="panel alist-item"
        style={{ width: "min(100%, 560px)", padding: 20, display: "grid", gap: 12 }}
      >
        <div className="flex items-center justify-between" style={{ gap: 12 }}>
          <b className="mono mute">{title.toUpperCase()}</b>
          <div className="flex" style={{ gap: 8 }}>
            {!unavailable && url && !failed && (
              <button
                type="button"
                className="btn"
                style={{ padding: "8px 12px" }}
                onClick={() => setZoomed((z) => !z)}
                aria-pressed={zoomed}
                aria-label={zoomed ? "Zoom out" : "Zoom in"}
              >
                {zoomed ? (
                  <ZoomOut size={15} aria-hidden="true" />
                ) : (
                  <ZoomIn size={15} aria-hidden="true" />
                )}
              </button>
            )}
            <button
              type="button"
              className="btn"
              style={{ padding: "8px 12px" }}
              onClick={() => {
                setZoomed(false);
                onClose();
              }}
            >
              Close
            </button>
          </div>
        </div>

        {unavailable || failed ? (
          <div
            role="img"
            aria-label="Evidence unavailable"
            style={{
              display: "grid",
              placeItems: "center",
              gap: 8,
              padding: 48,
              borderRadius: 14,
              border: "1px dashed var(--line)",
              background: "var(--bg)",
              color: "var(--mute)",
              textAlign: "center",
            }}
          >
            <ImageOff size={24} aria-hidden="true" />
            <span className="mono">Evidence unavailable</span>
          </div>
        ) : !url ? (
          <div className="skel" style={{ height: 280, borderRadius: 14 }} role="status" aria-label="Loading evidence" />
        ) : (
          <div
            style={{
              overflow: zoomed ? "auto" : "hidden",
              borderRadius: 14,
              border: "1px solid var(--line)",
              background: "var(--desk)",
              cursor: "zoom-in",
              maxHeight: zoomed ? "60vh" : undefined,
            }}
            onClick={() => setZoomed((z) => !z)}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={url}
              alt={description ?? "Evidence frame"}
              onError={() => setFailed(true)}
              className={cn(!zoomed && "alist-item")}
              style={{
                display: "block",
                width: "100%",
                height: "auto",
                transform: zoomed ? "scale(1.75)" : "scale(1)",
                transformOrigin: "center",
                transition: "transform .35s",
              }}
            />
          </div>
        )}

        <div className="mono mute" style={{ display: "grid", gap: 2 }}>
          {cameraName && <span>Camera · {cameraName}</span>}
          {timestamp && <span>Time · {timestamp}</span>}
          {description && <span style={{ color: "var(--ink)" }}>{description}</span>}
        </div>
      </div>
    </div>
  );
}
