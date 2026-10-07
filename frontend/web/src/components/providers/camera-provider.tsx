"use client";

import { useQueryClient } from "@tanstack/react-query";
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { toast } from "sonner";

import { useAuth } from "@/components/providers/auth-provider";
import { useCameraSocket } from "@/hooks/useCameraSocket";
import { queueIndexing } from "@/lib/embeddingQueue";
import type { Memory } from "@/types/domain";
import type {
  LocalGateState,
  ProcessingState,
  WsConnectionState,
} from "@/types/ws";

interface CameraContextValue {
  activeCameraId: string | null;
  setActiveCameraId: (id: string | null) => void;
  connection: WsConnectionState;
  processing: ProcessingState;
  gateState: LocalGateState;
  setGateState: (state: LocalGateState) => void;
  changeScore: number | null;
  lastMemory: Memory | null;
  /** Socket-created memories for the current session, newest first. */
  sessionMemories: Memory[];
  socketError: string | null;
  sendFrame: (data: string, ts: number) => void;
  disconnect: () => void;
}

const CameraContext = createContext<CameraContextValue | null>(null);

export function CameraProvider({ children }: { children: ReactNode }) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const [activeCameraId, setActiveCameraIdState] = useState<string | null>(null);
  const [gateState, setGateState] = useState<LocalGateState>("idle");
  const [sessionMemories, setSessionMemories] = useState<Memory[]>([]);

  const setActiveCameraId = useCallback((id: string | null) => {
    setActiveCameraIdState(id);
    setSessionMemories([]);
  }, []);

  const handleMemory = useCallback(
    (memory: Memory) => {
      setSessionMemories((prev) =>
        prev.some((m) => m.id === memory.id)
          ? prev
          : [memory, ...prev].slice(0, 20),
      );
      toast.success("Memory created", {
        description: memory.scene?.summary ?? "A new memory was saved.",
      });
      void queryClient.invalidateQueries({ queryKey: ["memories"] });
      void queryClient.invalidateQueries({ queryKey: ["events"] });
      // Background search indexing; never blocks memory display or chat.
      void queueIndexing(memory);
    },
    [queryClient],
  );

  const socket = useCameraSocket(activeCameraId, {
    token: accessToken,
    enabled: activeCameraId !== null && accessToken !== null,
    onMemory: handleMemory,
  });

  const value = useMemo<CameraContextValue>(
    () => ({
      activeCameraId,
      setActiveCameraId,
      connection: socket.connection,
      processing: socket.processing,
      gateState,
      setGateState,
      changeScore: socket.changeScore,
      lastMemory: socket.lastMemory,
      sessionMemories,
      socketError: socket.socketError,
      sendFrame: socket.sendFrame,
      disconnect: socket.disconnect,
    }),
    [activeCameraId, gateState, sessionMemories, setActiveCameraId, socket],
  );

  return <CameraContext.Provider value={value}>{children}</CameraContext.Provider>;
}

export function useCamera(): CameraContextValue {
  const ctx = useContext(CameraContext);
  if (!ctx) throw new Error("useCamera must be used inside CameraProvider");
  return ctx;
}
