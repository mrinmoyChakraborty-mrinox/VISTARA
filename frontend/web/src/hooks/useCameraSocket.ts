"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { getEnv, isEnvConfigured } from "@/lib/env";
import { getMemory } from "@/lib/apiClient";
import type { Memory } from "@/types/domain";
import type {
  ProcessingState,
  WsConnectionState,
  WsServerMessage,
} from "@/types/ws";

const MAX_ATTEMPTS = 5;
const BASE_DELAY_MS = 1000;
const MAX_DELAY_MS = 15000;

interface UseCameraSocketOptions {
  token: string | null;
  enabled?: boolean;
  onMemory?: (memory: Memory) => void;
}

export interface CameraSocket {
  connection: WsConnectionState;
  processing: ProcessingState;
  changeScore: number | null;
  lastMemory: Memory | null;
  socketError: string | null;
  sendFrame: (data: string, ts: number) => void;
  disconnect: () => void;
}

/**
 * Exactly one socket per active camera. Sends camera_connected on open, frame
 * messages only for gated frames, and stop before closing. Reconnects with
 * exponential backoff (1s, 2s, 4s, capped 15s, max 5 attempts) and reconnects
 * when the token rotates.
 */
export function useCameraSocket(
  cameraId: string | null,
  { token, enabled = true, onMemory }: UseCameraSocketOptions,
): CameraSocket {
  const [connection, setConnection] = useState<WsConnectionState>("disconnected");
  const [processing, setProcessing] = useState<ProcessingState>("idle");
  const [changeScore, setChangeScore] = useState<number | null>(null);
  const [lastMemory, setLastMemory] = useState<Memory | null>(null);
  const [socketError, setSocketError] = useState<string | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const attemptsRef = useRef(0);
  const retryTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const shouldConnectRef = useRef(false);
  const onMemoryRef = useRef(onMemory);

  useEffect(() => {
    onMemoryRef.current = onMemory;
  }, [onMemory]);

  const clearRetry = useCallback(() => {
    if (retryTimer.current) {
      clearTimeout(retryTimer.current);
      retryTimer.current = null;
    }
  }, []);

  const closeSocket = useCallback(() => {
    const socket = socketRef.current;
    socketRef.current = null;
    if (socket && socket.readyState < WebSocket.CLOSING) {
      try {
        socket.close();
      } catch {
        // Closing is best-effort.
      }
    }
  }, []);

  useEffect(() => {
    if (!enabled || !cameraId || !token || !isEnvConfigured()) {
      const id = requestAnimationFrame(() => setConnection("disconnected"));
      return () => cancelAnimationFrame(id);
    }

    shouldConnectRef.current = true;
    attemptsRef.current = 0;
    // Deferred a frame: marks a fresh connection attempt without a
    // synchronous setState inside the effect body.
    const paint = requestAnimationFrame(() => {
      setSocketError(null);
      setConnection("connecting");
    });

    const connect = () => {
      if (!shouldConnectRef.current) return;
      const { wsUrl } = getEnv();
      const socket = new WebSocket(
        `${wsUrl}/ws/cameras/${cameraId}?token=${encodeURIComponent(token)}`,
      );
      socketRef.current = socket;
      setConnection("connecting");

      socket.onopen = () => {
        if (socketRef.current !== socket) return;
        attemptsRef.current = 0;
        setConnection("connected");
        setSocketError(null);
        socket.send(JSON.stringify({ type: "camera_connected" }));
      };

      socket.onmessage = (event) => {
        let msg: WsServerMessage;
        try {
          msg = JSON.parse(event.data as string) as WsServerMessage;
        } catch {
          return;
        }
        switch (msg.type) {
          case "connection_state":
            setConnection(
              msg.state === "connected" ? "connected" : msg.state,
            );
            break;
          case "processing":
            setProcessing(msg.state);
            break;
          case "change_detected":
            setChangeScore(msg.score);
            break;
          case "memory_created":
            // The socket payload is lightweight (memory_id/summary/baseline).
            // The full memory — objects, events, evidence, is_baseline — comes
            // from the existing REST endpoint. Never fabricate it locally.
            if (!msg.memory_id) {
              setSocketError("The camera reported a memory without an id.");
              setProcessing("idle");
              break;
            }
            setProcessing("idle");
            void getMemory(msg.memory_id)
              .then((memory) => {
                setLastMemory(memory);
                onMemoryRef.current?.(memory);
              })
              .catch(() => {
                setSocketError(
                  "A memory was saved but could not be loaded. Refresh the timeline.",
                );
              });
            break;
          case "error":
            setSocketError(msg.message);
            break;
          default:
            break;
        }
      };

      socket.onerror = () => {
        if (socketRef.current !== socket) return;
        setSocketError("Connection error. Retrying…");
      };

      socket.onclose = () => {
        if (socketRef.current === socket) socketRef.current = null;
        if (!shouldConnectRef.current) {
          setConnection("disconnected");
          return;
        }
        if (attemptsRef.current >= MAX_ATTEMPTS) {
          setConnection("error");
          setSocketError("Could not reach the camera socket after 5 attempts.");
          return;
        }
        const delay = Math.min(
          MAX_DELAY_MS,
          BASE_DELAY_MS * 2 ** attemptsRef.current,
        );
        attemptsRef.current += 1;
        setConnection("connecting");
        retryTimer.current = setTimeout(connect, delay);
      };
    };

    connect();

    return () => {
      shouldConnectRef.current = false;
      cancelAnimationFrame(paint);
      clearRetry();
      closeSocket();
    };
  }, [cameraId, token, enabled, clearRetry, closeSocket]);

  const sendFrame = useCallback((data: string, ts: number) => {
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    socket.send(JSON.stringify({ type: "frame", data, ts }));
  }, []);

  const disconnect = useCallback(() => {
    shouldConnectRef.current = false;
    clearRetry();
    const socket = socketRef.current;
    if (socket && socket.readyState === WebSocket.OPEN) {
      try {
        socket.send(JSON.stringify({ type: "stop" }));
      } catch {
        // The stop message is best-effort; still close below.
      }
    }
    closeSocket();
    setConnection("disconnected");
    setProcessing("idle");
  }, [clearRetry, closeSocket]);

  return {
    connection,
    processing,
    changeScore,
    lastMemory,
    socketError,
    sendFrame,
    disconnect,
  };
}
