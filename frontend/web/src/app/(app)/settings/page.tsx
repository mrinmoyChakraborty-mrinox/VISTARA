"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Cpu, Download, LogOut, Plus, Trash2 } from "lucide-react";

import { useAuth } from "@/components/providers/auth-provider";
import { LocalVsCloudExplainer } from "@/components/landing/local-vs-cloud-explainer";
import { useCamerasQuery, useDeleteCamera } from "@/hooks/use-cameras";
import { useCaptureSettings } from "@/hooks/use-capture-settings";
import { useEmbeddingStats } from "@/hooks/use-embedding";
import { getEnv, isEnvConfigured } from "@/lib/env";
import { getHealth } from "@/lib/apiClient";
import { cn } from "@/lib/utils";

type Tab = "account" | "cameras" | "capture" | "embedding" | "privacy" | "health";

const TABS: { key: Tab; label: string }[] = [
  { key: "account", label: "Account" },
  { key: "cameras", label: "Cameras" },
  { key: "capture", label: "Capture" },
  { key: "embedding", label: "Embedding" },
  { key: "privacy", label: "Privacy" },
  { key: "health", label: "Health" },
];

function Slider({
  id,
  label,
  value,
  display,
  min,
  max,
  step,
  onChange,
}: {
  id: string;
  label: string;
  value: number;
  display: string;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="auth-field">
      <label htmlFor={id}>
        {label} · <span className="mono">{display}</span>
      </label>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </div>
  );
}

function AccountSection() {
  const { user, signOut, configured, configError } = useAuth();
  return (
    <div className="panel" style={{ display: "grid", gap: 12, alignContent: "start" }}>
      <b className="mono mute">ACCOUNT</b>
      {!configured && (
        <p role="alert" className="mono" style={{ color: "#c4572f" }}>
          {configError}
        </p>
      )}
      <p>
        Signed in as <b>{user?.email ?? "…"}</b>
      </p>
      <p className="mute" style={{ fontSize: ".9rem" }}>
        Identity is derived server-side from your session token. The app never
        stores or sends your user id.
      </p>
      <div>
        <button type="button" className="btn" onClick={() => void signOut()}>
          <LogOut size={15} aria-hidden="true" />
          Sign out
        </button>
      </div>
    </div>
  );
}

function CamerasSection() {
  const cameras = useCamerasQuery();
  const del = useDeleteCamera();
  const [confirmId, setConfirmId] = useState<string | null>(null);

  return (
    <div className="panel" style={{ display: "grid", gap: 12, alignContent: "start" }}>
      <div className="flex items-center justify-between" style={{ gap: 12 }}>
        <b className="mono mute">CAMERAS</b>
        <a className="btn shimmer" href="/cameras" style={{ padding: "8px 16px", fontSize: ".85rem" }}>
          <Plus size={14} aria-hidden="true" />
          Manage
        </a>
      </div>
      {cameras.isPending ? (
        <div className="grid" style={{ gap: 8 }} role="status" aria-label="Loading cameras">
          <div className="skel" style={{ height: 56, borderRadius: 14 }} />
          <div className="skel" style={{ height: 56, borderRadius: 14 }} />
        </div>
      ) : cameras.isError ? (
        <div role="alert" style={{ display: "grid", gap: 8, justifyItems: "start" }}>
          <b>Cameras could not be loaded.</b>
          <button type="button" className="btn" onClick={() => cameras.refetch()}>
            Retry
          </button>
        </div>
      ) : (cameras.data ?? []).length === 0 ? (
        <div style={{ display: "grid", gap: 8, justifyItems: "start" }}>
          <b>No cameras yet.</b>
          <a className="btn shimmer" href="/cameras">
            Add camera
          </a>
        </div>
      ) : (
        <div style={{ display: "grid", gap: 8 }}>
          {(cameras.data ?? []).map((camera) => (
            <div
              key={camera.id}
              className="flex flex-wrap items-center justify-between"
              style={{
                gap: 10,
                borderRadius: 14,
                border: "1px solid var(--line)",
                background: "var(--bg)",
                padding: "10px 14px",
              }}
            >
              <span>
                <b>{camera.name}</b>{" "}
                <span className="mono mute">· {camera.status}</span>
              </span>
              {confirmId === camera.id ? (
                <span className="flex" style={{ gap: 8 }}>
                  <button
                    type="button"
                    className="btn"
                    style={{ padding: "6px 12px", fontSize: ".8rem" }}
                    disabled={del.isPending}
                    onClick={() => {
                      setConfirmId(null);
                      del.mutate(camera.id);
                    }}
                  >
                    Confirm
                  </button>
                  <button
                    type="button"
                    className="btn"
                    style={{ padding: "6px 12px", fontSize: ".8rem" }}
                    onClick={() => setConfirmId(null)}
                  >
                    Keep
                  </button>
                </span>
              ) : (
                <button
                  type="button"
                  className="btn"
                  style={{ padding: "6px 12px", fontSize: ".8rem" }}
                  onClick={() => setConfirmId(camera.id)}
                  aria-label={`Delete camera ${camera.name}`}
                >
                  <Trash2 size={14} aria-hidden="true" />
                  Delete
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function CaptureSection() {
  const { settings, update, reset } = useCaptureSettings();
  return (
    <div className="panel" style={{ display: "grid", gap: 16, alignContent: "start" }}>
      <b className="mono mute">CAPTURE + GATE</b>
      <p className="mute" style={{ fontSize: ".9rem" }}>
        Stored only in this browser. Nothing here touches the backend.
      </p>
      <Slider
        id="set-fps"
        label="Sample rate"
        value={settings.fps}
        display={`${settings.fps.toFixed(1)} FPS`}
        min={1}
        max={4}
        step={0.5}
        onChange={(fps) => update({ fps })}
      />
      <Slider
        id="set-maxside"
        label="Downscale max side"
        value={settings.maxSide}
        display={`${settings.maxSide}px`}
        min={256}
        max={1024}
        step={128}
        onChange={(maxSide) => update({ maxSide })}
      />
      <Slider
        id="set-quality"
        label="JPEG quality"
        value={settings.quality}
        display={settings.quality.toFixed(2)}
        min={0.4}
        max={0.95}
        step={0.05}
        onChange={(quality) => update({ quality })}
      />
      <Slider
        id="set-threshold"
        label="Gate threshold"
        value={settings.threshold}
        display={`${Math.round(settings.threshold * 100)}% change`}
        min={0.02}
        max={0.2}
        step={0.01}
        onChange={(threshold) => update({ threshold })}
      />
      <Slider
        id="set-cooldown"
        label="Gate cooldown"
        value={settings.cooldownSeconds}
        display={`${settings.cooldownSeconds}s`}
        min={2}
        max={30}
        step={1}
        onChange={(cooldownSeconds) => update({ cooldownSeconds })}
      />
      <div>
        <button type="button" className="btn" onClick={reset}>
          Reset to defaults
        </button>
      </div>
    </div>
  );
}

function EmbeddingSection() {
  const stats = useEmbeddingStats();
  const badge =
    stats.capability === "webgpu"
      ? { dot: "green", text: "WebGPU" }
      : stats.capability === "wasm"
        ? { dot: "amber", text: "WASM" }
        : stats.capability === "unsupported"
          ? { dot: "red", text: "Unsupported" }
          : { dot: "", text: "Not loaded yet" };

  return (
    <div className="panel" style={{ display: "grid", gap: 12, alignContent: "start" }}>
      <b className="mono mute">EMBEDDING STATUS</b>
      <p>
        <span className="schip">
          <span className={`sdot ${badge.dot}`} aria-hidden="true" />
          {badge.text}
        </span>
      </p>
      <p className="mute" style={{ fontSize: ".9rem" }}>
        Qwen3-Embedding-0.6B runs in a Web Worker and produces 1024-dim
        vectors. Only the vector is uploaded — never frames.
      </p>
      {stats.capability === "wasm" && stats.modelState === "ready" && (
        <p role="status" className="mono" style={{ color: "var(--acc)" }}>
          <Cpu size={13} aria-hidden="true" style={{ verticalAlign: -2 }} /> Embedding
          running on CPU (WebGPU unavailable)
        </p>
      )}
      {stats.modelState === "loading" && (
        <div role="status" aria-label="Embedding model download progress">
          <div className="sbar">
            <b style={{ width: `${stats.progress}%`, animation: "none" }} />
          </div>
          <p className="mono mute">
            {stats.progress >= 100 ? (
              <>Downloaded 100% · initializing model (up to a minute on CPU, then the badge flips to ready)…</>
            ) : (
              <>First load · {stats.progress}%{stats.progressFile ? ` · ${stats.progressFile}` : ""}</>
            )}
          </p>
        </div>
      )}
      {stats.modelState === "ready" && (
        <p role="status" className="mono" style={{ color: "var(--acc)" }}>
          Model ready — memories index automatically.
        </p>
      )}
      {stats.modelState === "error" && (
        <p role="alert" className="mono" style={{ color: "#c4572f" }}>
          The embedding model could not load. Memories and chat keep working
          without search vectors.
          {stats.lastError && (
            <span style={{ display: "block", marginTop: 4, fontSize: ".8rem" }}>
              Reason: {stats.lastError}
            </span>
          )}
        </p>
      )}
      <div className="flex flex-wrap" style={{ gap: 8 }}>
        <button type="button" className="btn shimmer" onClick={() => stats.warm()}>
          <Download size={15} aria-hidden="true" />
          Pre-download model
        </button>
        <button type="button" className="btn" onClick={() => stats.reload()}>
          Re-download model
        </button>
      </div>
      <p className="mute" style={{ fontSize: ".85rem" }}>
        Pre-download once before the demo over good network: the model is
        cached in the browser, so later memories index instantly.
      </p>
    </div>
  );
}

function HealthSection() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    enabled: isEnvConfigured(),
    retry: false,
  });
  let wsUrl = "unconfigured";
  try {
    wsUrl = getEnv().wsUrl;
  } catch {
    // Shown as unconfigured below.
  }

  return (
    <div className="panel" style={{ display: "grid", gap: 12, alignContent: "start" }}>
      <b className="mono mute">BACKEND HEALTH</b>
      {health.isPending ? (
        <div className="skel" style={{ height: 22, maxWidth: 280 }} role="status" aria-label="Checking backend" />
      ) : health.isError ? (
        <div role="alert" style={{ display: "grid", gap: 8, justifyItems: "start" }}>
          <p>
            <span className="sdot red" aria-hidden="true" style={{ display: "inline-block", marginRight: 8 }} />
            Backend unreachable
          </p>
          <button type="button" className="btn" onClick={() => health.refetch()}>
            Retry
          </button>
        </div>
      ) : (
        <p>
          <span className="sdot green" aria-hidden="true" style={{ display: "inline-block", marginRight: 8 }} />
          Backend connected{health.data?.status ? ` · ${health.data.status}` : ""}
        </p>
      )}
      <p className="mono mute" style={{ overflowWrap: "anywhere" }}>
        WS URL · {wsUrl}
      </p>
      <p className="mono mute">Build · Vistara web 0.1.0</p>
    </div>
  );
}

export default function SettingsPage() {
  const [tab, setTab] = useState<Tab>("account");

  return (
    <div style={{ display: "grid", gap: 24 }}>
      <div>
        <h2>Settings</h2>
        <p className="mute" style={{ marginTop: 8 }}>
          Account, capture, search indexing, privacy, and backend health.
        </p>
      </div>
      <div className="tabs" style={{ margin: 0 }} role="tablist" aria-label="Settings sections">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            role="tab"
            aria-selected={tab === t.key}
            className={cn(tab === t.key && "on")}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tab === "account" && <AccountSection />}
      {tab === "cameras" && <CamerasSection />}
      {tab === "capture" && <CaptureSection />}
      {tab === "embedding" && <EmbeddingSection />}
      {tab === "privacy" && <LocalVsCloudExplainer />}
      {tab === "health" && <HealthSection />}
    </div>
  );
}
