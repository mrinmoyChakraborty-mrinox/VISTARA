"use client";

import { useEffect, useRef, useState } from "react";
import { Camera as CameraIcon, RotateCcw } from "lucide-react";

import { useCamera } from "@/components/providers/camera-provider";
import { ChangeScoreGauge } from "@/components/cameras/change-score-gauge";
import { FrameStats } from "@/components/cameras/frame-stats";
import { Ripple } from "@/components/ui-fx/ripple";
import { ScanLine } from "@/components/ui-fx/scan-line";
import { ViewfinderCorners } from "@/components/ui-fx/viewfinder-corners";
import { useCaptureSettings } from "@/hooks/use-capture-settings";
import { ChangeGate } from "@/lib/changeGate";
import { sampleFrame, toGrayscaleThumbnail } from "@/lib/frameSampler";
import type { Camera } from "@/types/domain";

type StreamState = "idle" | "requesting" | "live" | "denied" | "unavailable" | "recorded";

/** Unconditional frames sent right after connect to seed the backend baseline. */
const BASELINE_SEED_FRAMES = 8;

export function CameraPreview({ camera }: { camera: Camera }) {
  const { connection, sendFrame, setGateState, changeScore, processing } =
    useCamera();
  const { settings } = useCaptureSettings();
  const videoRef = useRef<HTMLVideoElement>(null);
  const gateRef = useRef<ChangeGate | null>(null);
  const sentRef = useRef<{ t: number; bytes: number }[]>([]);
  const totalRef = useRef(0);
  const [streamState, setStreamState] = useState<StreamState>("idle");
  const [stats, setStats] = useState({ fps: 0, kb: 0, sent: 0 });
  const [pulseKey, setPulseKey] = useState(0);
  const [retry, setRetry] = useState(0);
  const lastScore = useRef<number | null>(null);
  const settingsRef = useRef(settings);
  // Frames still to send unconditionally after (re)connect. The backend
  // needs >=5 frames over >=3s to establish the initial visual baseline
  // (backend/app/perception/baseline.py); a static scene would otherwise
  // never pass the local gate and the baseline would starve. The backend
  // gate stays authoritative — extra frames on an already-ready camera are
  // dropped server-side.
  const seedLeftRef = useRef(BASELINE_SEED_FRAMES);
  const connectionRef = useRef(connection);

  useEffect(() => {
    if (connection === "connected" && connectionRef.current !== "connected") {
      seedLeftRef.current = BASELINE_SEED_FRAMES;
    }
    connectionRef.current = connection;
  }, [connection]);

  useEffect(() => {
    settingsRef.current = settings;
  }, [settings]);

  useEffect(() => {
    gateRef.current = new ChangeGate({
      threshold: settings.threshold,
      persistenceFrames: 2,
      cooldownSeconds: settings.cooldownSeconds,
    });
  }, [settings.threshold, settings.cooldownSeconds]);

  useEffect(() => {
    if (changeScore === null || changeScore === lastScore.current) return;
    lastScore.current = changeScore;
    setPulseKey((k) => k + 1);
  }, [changeScore]);

  useEffect(() => {
    let cancelled = false;
    let stream: MediaStream | null = null;
    let timer: ReturnType<typeof setInterval> | null = null;
    const video = videoRef.current;
    seedLeftRef.current = BASELINE_SEED_FRAMES;

    async function start() {
      if (!video || cancelled) return;
      // Recorded demo sources play on the server; the browser only watches
      // status + memories over the socket. No getUserMedia here.
      if (camera.source_type === "video_file") {
        if (cancelled) return;
        setStreamState("recorded");
        return;
      }
      if (!navigator.mediaDevices?.getUserMedia) {
        setStreamState("unavailable");
        return;
      }
      setStreamState("requesting");
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: true,
          audio: false,
        });
      } catch (err) {
        if (cancelled) return;
        const name = err instanceof DOMException ? err.name : "";
        setStreamState(
          name === "NotAllowedError" || name === "SecurityError"
            ? "denied"
            : "unavailable",
        );
        return;
      }
      if (cancelled) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      video.srcObject = stream;
      try {
        await video.play();
      } catch {
        // Autoplay is best-effort; sampling still works once frames flow.
      }
      if (cancelled) return;
      setStreamState("live");

      const intervalMs = Math.round(
        1000 / Math.max(1, settingsRef.current.fps),
      );
      const tick = () => {
        const v = videoRef.current;
        const gate = gateRef.current;
        if (!v || !gate || v.readyState < 2) return;
        const frame = sampleFrame(v, settingsRef.current.maxSide, settingsRef.current.quality);
        if (!frame) return;
        const thumb = toGrayscaleThumbnail(v);
        if (thumb) {
          const res = gate.push(thumb.pixels);
          setGateState(gate.state);
          const seeding = seedLeftRef.current > 0;
          if (res.changed || seeding) {
            if (seeding) seedLeftRef.current -= 1;
            sendFrame(frame.data, Date.now());
            const now = Date.now();
            totalRef.current += 1;
            sentRef.current.push({ t: now, bytes: frame.bytes });
          }
        }
        const cutoff = Date.now() - 5000;
        sentRef.current = sentRef.current.filter((s) => s.t >= cutoff);
        const n = sentRef.current.length;
        const avg = n
          ? sentRef.current.reduce((a, s) => a + s.bytes, 0) / n / 1024
          : 0;
        setStats({ fps: n / 5, kb: avg, sent: totalRef.current });
      };
      timer = setInterval(tick, intervalMs);
    }

    void start();

    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
      stream?.getTracks().forEach((track) => track.stop());
      if (video) video.srcObject = null;
      gateRef.current?.reset();
      setGateState("idle");
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [camera.id, retry]);

  return (
    <div className="panel">
      <div
        style={{
          position: "relative",
          borderRadius: 16,
          overflow: "hidden",
          border: "1px solid var(--line)",
          background: "var(--desk)",
        }}
      >
        <video
          ref={videoRef}
          muted
          autoPlay
          playsInline
          aria-label={`Live preview of ${camera.name}`}
          style={{
            display: "block",
            width: "100%",
            aspectRatio: "16 / 10",
            objectFit: "cover",
            background: "var(--desk)",
          }}
        />
        <ViewfinderCorners className="absolute inset-0 pointer-events-none" />
        {streamState === "live" && <ScanLine />}
        {pulseKey > 0 && (
          <Ripple
            key={pulseKey}
            size={72}
            style={{
              position: "absolute",
              left: "50%",
              top: "50%",
              marginLeft: -36,
              marginTop: -36,
            }}
          />
        )}
        <span className="tag">
          {streamState === "live"
            ? `● live · ${processing}`
            : streamState === "recorded"
              ? `● recorded source · ${processing}`
              : streamState}
        </span>
      </div>

      {streamState === "recorded" ? (
        <p className="mono mute" style={{ marginTop: 12 }}>
          Recorded video plays on the server. Memories and events arrive live
          below — no camera permission needed.
        </p>
      ) : streamState === "denied" || streamState === "unavailable" ? (
        <div
          role="alert"
          style={{
            display: "grid",
            gap: 10,
            justifyItems: "start",
            marginTop: 16,
            padding: 16,
            borderRadius: 16,
            border: "1px dashed var(--line)",
            background: "var(--bg)",
          }}
        >
          <CameraIcon size={22} aria-hidden="true" style={{ color: "var(--mute)" }} />
          <b>
            {streamState === "denied"
              ? "Camera access was denied."
              : "No camera is available."}
          </b>
          <p className="mute" style={{ fontSize: ".9rem" }}>
            {streamState === "denied"
              ? "Allow camera access in the browser site settings, then try again. The preview never leaves this device."
              : "Plug in a camera or use a device with one, then try again."}
          </p>
          <button
            type="button"
            className="btn"
            onClick={() => setRetry((r) => r + 1)}
          >
            <RotateCcw size={15} aria-hidden="true" />
            Retry camera
          </button>
        </div>
      ) : (
        <p className="mono mute" style={{ marginTop: 12 }}>
          {streamState === "requesting" || streamState === "idle"
            ? "Requesting camera permission…"
            : "Sampling ~2 FPS through the local gate. Only changed frames are sent."}
        </p>
      )}

      <div
        className="flex flex-wrap items-center"
        style={{ gap: 24, marginTop: 16 }}
      >
        <ChangeScoreGauge score={changeScore} />
        <FrameStats fps={stats.fps} kbPerFrame={stats.kb} sent={stats.sent} />
        <p className="mono mute" style={{ flex: 1, minWidth: 180 }}>
          Sampling {settings.fps.toFixed(1)} FPS · {settings.maxSide}px ·
          q{settings.quality.toFixed(2)} · gate{" "}
          {Math.round(settings.threshold * 100)}% · cooldown{" "}
          {settings.cooldownSeconds}s. Tune it in Settings.
        </p>
      </div>
    </div>
  );
}
