"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Camera as CameraIcon } from "lucide-react";

import { useCameraSocket } from "@/hooks/useCameraSocket";
import { ChangeGate } from "@/lib/changeGate";
import { isEnvConfigured } from "@/lib/env";
import { sampleFrame, toGrayscaleThumbnail } from "@/lib/frameSampler";

type PairState = "need-code" | "ready" | "requesting" | "live" | "denied" | "unavailable";

/** First frames bypass the gate so the backend baseline can establish. */
const SEED_FRAMES = 8;

/**
 * Public phone route (no login): opened from the desktop QR code as
 * /pair?code=<single-use>&camera=<id>. Streams this phone's camera over the
 * pairing-authenticated WebSocket using the same gate + sampling as desktop.
 */
function PairBody() {
  const searchParams = useSearchParams();
  const code = searchParams.get("code") ?? "";
  const cameraId = searchParams.get("camera") ?? "";

  const [pairState, setPairState] = useState<PairState>(
    code && cameraId ? "ready" : "need-code",
  );
  const [started, setStarted] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const gateRef = useRef<ChangeGate | null>(null);
  const seedLeftRef = useRef(SEED_FRAMES);
  const streamRef = useRef<MediaStream | null>(null);

  const socket = useCameraSocket(code && cameraId ? cameraId : null, {
    token: null,
    pairingCode: code || null,
    enabled: started && !!code && !!cameraId,
  });

  useEffect(() => {
    if (!started) return;
    let cancelled = false;
    let timer: ReturnType<typeof setInterval> | null = null;
    gateRef.current = new ChangeGate({ threshold: 0.06, persistenceFrames: 2, cooldownSeconds: 8 });
    seedLeftRef.current = SEED_FRAMES;

    async function start() {
      const video = videoRef.current;
      if (!video || cancelled) return;
      if (!navigator.mediaDevices?.getUserMedia) {
        setPairState("unavailable");
        return;
      }
      setPairState("requesting");
      let stream: MediaStream;
      try {
        // Rear camera first on phones; falls back to any camera.
        try {
          stream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: { ideal: "environment" } },
            audio: false,
          });
        } catch {
          stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        }
      } catch (err) {
        if (cancelled) return;
        const name = err instanceof DOMException ? err.name : "";
        setPairState(
          name === "NotAllowedError" || name === "SecurityError" ? "denied" : "unavailable",
        );
        return;
      }
      if (cancelled) {
        stream.getTracks().forEach((t) => t.stop());
        return;
      }
      streamRef.current = stream;
      video.srcObject = stream;
      try {
        await video.play();
      } catch {
        // Sampling works once frames flow.
      }
      if (cancelled) return;
      setPairState("live");

      timer = setInterval(() => {
        const v = videoRef.current;
        const gate = gateRef.current;
        if (!v || !gate || v.readyState < 2) return;
        const frame = sampleFrame(v);
        if (!frame) return;
        const thumb = toGrayscaleThumbnail(v);
        if (!thumb) return;
        const res = gate.push(thumb.pixels);
        const seeding = seedLeftRef.current > 0;
        if (res.changed || seeding) {
          if (seeding) seedLeftRef.current -= 1;
          socket.sendFrame(frame.data, Date.now());
        }
      }, 500);
    }

    void start();
    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
      streamRef.current?.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
      gateRef.current?.reset();
    };
    // Socket handle is stable; started/code/cameraId drive re-runs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [started]);

  useEffect(() => () => {
    socket.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!isEnvConfigured()) {
    return (
      <main className="wrap" style={{ paddingTop: 48 }}>
        <div className="panel" role="alert">
          <b>This Vistara app is not configured.</b>
          <p className="mute">The backend URL is missing from the deployment.</p>
        </div>
      </main>
    );
  }

  if (pairState === "need-code") {
    return (
      <main className="wrap" style={{ paddingTop: 48 }}>
        <div className="panel" role="alert">
          <b>Invalid pairing link.</b>
          <p className="mute">Ask the desktop to show a fresh QR code and scan it again.</p>
        </div>
      </main>
    );
  }

  return (
    <main className="wrap" style={{ paddingTop: 28, paddingBottom: 48, display: "grid", gap: 16 }}>
      <div>
        <h2>Vistara phone camera</h2>
        <p className="mute" style={{ marginTop: 8 }}>
          {socket.connection === "connected"
            ? "● paired and streaming"
            : socket.connection === "connecting"
              ? "○ connecting…"
              : socket.connection === "error"
                ? "○ connection failed — the code may be expired; scan a fresh QR."
                : "○ ready"}
          {socket.socketError ? ` · ${socket.socketError}` : ""}
        </p>
      </div>

      {!started ? (
        <div className="panel" style={{ display: "grid", gap: 12, justifyItems: "start" }}>
          <CameraIcon size={22} aria-hidden="true" style={{ color: "var(--mute)" }} />
          <b>Stream this phone as a Vistara camera.</b>
          <p className="mute" style={{ fontSize: ".9rem" }}>
            The browser will ask for camera permission. Only gated frames are
            sent to your Vistara backend.
          </p>
          <button type="button" className="btn shimmer" onClick={() => setStarted(true)}>
            Start streaming
          </button>
        </div>
      ) : (
        <div className="panel">
          <video
            ref={videoRef}
            muted
            autoPlay
            playsInline
            aria-label="Phone camera preview"
            style={{ display: "block", width: "100%", borderRadius: 16, background: "var(--desk)" }}
          />
          {(pairState === "denied" || pairState === "unavailable") && (
            <div role="alert" style={{ marginTop: 12 }}>
              <b>
                {pairState === "denied"
                  ? "Camera access was denied."
                  : "No camera is available."}
              </b>
              <p className="mute" style={{ fontSize: ".9rem" }}>
                Allow camera access in the browser site settings (HTTPS required),
                then reload this page.
              </p>
            </div>
          )}
          {pairState !== "denied" && pairState !== "unavailable" && (
            <p className="mono mute" style={{ marginTop: 12 }}>
              {socket.processing === "analyzing" ? "● analyzing" : "○ watching"}
              {socket.changeScore !== null ? ` · change ${Math.round(socket.changeScore * 100)}%` : ""}
            </p>
          )}
        </div>
      )}
    </main>
  );
}

export default function PairPage() {
  return (
    <Suspense fallback={<p className="mute" role="status">Loading pairing…</p>}>
      <PairBody />
    </Suspense>
  );
}
